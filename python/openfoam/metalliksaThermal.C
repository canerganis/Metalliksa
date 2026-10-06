/* OpenFOAM Foundation 14: conservative explicit enthalpy on an orthogonal FV mesh.
 * This is a THERMAL solver, not VOF CFD. No fabricated free-surface capability.
 * Stationary reference mass, harmonic face conductivity, exact opposite face fluxes.
 */
#include "argList.H"
#include "Time.H"
#include "fvMesh.H"
#include "volFields.H"
#include "surfaceFields.H"
#include <fstream>
#include <vector>
#include <array>
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <map>
using namespace Foam;
using Row = std::array<double, 6>;
struct Segment { double a,b,x0,y0,x1,y1,surface; int track,layer; };
// Probability mass of a normalized 1/e^2 Gaussian. erfc preserves tail mass.
double gaussianMass(double lower, double upper, double centre, double radius)
{
    if(upper<=lower) return 0;
    const double a=std::sqrt(2.)*(lower-centre)/radius;
    const double b=std::sqrt(2.)*(upper-centre)/radius;
    if(a>=0) return .5*(std::erfc(a)-std::erfc(b));
    if(b<=0) return .5*(std::erfc(-b)-std::erfc(-a));
    return .5*(std::erf(b)-std::erf(a));
}
double interp(const std::vector<Row>& rows, double x, int xcol, int ycol)
{
    auto it = std::lower_bound(rows.begin(), rows.end(), x,
        [xcol](const Row& r,double v){ return r[xcol]<v; });
    if (it==rows.begin()) return (*it)[ycol];
    if (it==rows.end()) return rows.back()[ycol];
    const Row& a=*(it-1); const Row& b=*it;
    return a[ycol]+(b[ycol]-a[ycol])*(x-a[xcol])/(b[xcol]-a[xcol]);
}
int main(int argc, char *argv[])
{
    #include "setRootCase.H"
    #include "createTime.H"
    #include "createMesh.H"
    std::ifstream input((runTime.path()/"thermalInput.dat").c_str());
    double end,maxDt,t0,solidus,liquidus,boiling,power,radius,penetration,packing,powderK,conv,emissivity,dx,speed;
    input>>end>>maxDt>>t0>>solidus>>liquidus>>boiling>>power>>radius>>penetration>>packing>>powderK>>conv>>emissivity>>dx>>speed;
    int nrows; input>>nrows;
    std::vector<Row> table(nrows);
    for(auto& row:table) for(auto& value:row) input>>value;
    int ns; input>>ns; std::vector<Segment> scans(ns);
    for(auto& s:scans) input>>s.a>>s.b>>s.x0>>s.y0>>s.x1>>s.y1>>s.surface>>s.track>>s.layer;
    if(!input || nrows<2 || ns<1) FatalErrorInFunction<<"Invalid thermal input"<<exit(FatalError);
    const vectorField& centres=mesh.C(); const scalarField& volumes=mesh.V();
    const labelUList& owners=mesh.owner(); const labelUList& neighbours=mesh.neighbour();
    const surfaceScalarField& areas=mesh.magSf();
    const int n=mesh.nCells();
    std::vector<double> T(n,t0),H(n,0),rho(n),k(n),rate(n),source(n),old(n),conductance(n),cp(n),zMass(n),nodeSource(n);
    std::vector<bool> ever(n,false),active(n,false),wasMelt(n,false),remelt(n,false);
    std::vector<std::vector<bool>> segmentMelt(ns, std::vector<bool>(n, false));
    int lastActiveSegment = 0;
    const double h0=interp(table,t0,0,1), hmax=interp(table,boiling,0,1);
    double cpFloor=GREAT;
    for(const auto& row:table) cpFloor=std::min(cpFloor,row[4]);
    if(!(cpFloor>0) || !(radius>0) || !(penetration>0))
        FatalErrorInFunction<<"Invalid thermal capacity or source radius"<<exit(FatalError);
    for(int i=0;i<n;++i) rho[i]=interp(table,t0,0,2)*(centres[i].z()>0?packing:1.);
    std::ofstream coords((runTime.path()/"coordinates.csv").c_str());
    coords<<std::setprecision(17);
    for(int i=0;i<n;++i) coords<<centres[i].x()<<","<<centres[i].y()<<","<<centres[i].z()<<","<<volumes[i]<<"\n";
    coords.close();
    std::ofstream snapshots((runTime.path()/"snapshots.dat").c_str());
    snapshots<<std::setprecision(17);
    double time=0,ein=0,eout=0,nextSample=0,minDt=maxDt,peak=t0;
    unsigned step=0, peakMeltStep=0;
    int peakMeltCount=0;
    double peakMeltTime=0, peakMeltSurface=0;
    std::vector<double> peakMeltField;
    double sumG=0,sumR=0,sumCooling=0,frontCount=0;
    double minimumCaptured=1,maximumSurfaceOffset=0,maximumDt=0,maximumIncrement=0;
    unsigned sourceTimestepRetries=0;
    while(time<end-1e-15)
    {
        const Segment* laser=nullptr; double surface=scans.front().surface;
        int activeSegment = -1;
        double dt=std::min({maxDt,end-time,radius/(4*speed)});
        for(int s=0;s<ns;++s)
        {
            if(scans[s].a<=time+1e-14) surface=scans[s].surface;
            if(scans[s].a<=time+1e-14 && time<scans[s].b-1e-14) { laser=&scans[s]; activeSegment=s; }
            if(scans[s].a>time+1e-14) dt=std::min(dt,scans[s].a-time);
            if(scans[s].b>time+1e-14) dt=std::min(dt,scans[s].b-time);
        }
        if(activeSegment >= 0) lastActiveSegment = activeSegment;
        std::fill(rate.begin(),rate.end(),0); std::fill(source.begin(),source.end(),0);
        std::fill(conductance.begin(),conductance.end(),0);
        for(int i=0;i<n;++i)
        {
            active[i]=centres[i].z()<surface;
            k[i]=interp(table,T[i],0,3)*(centres[i].z()>0 && !ever[i]?powderK:1.);
            cp[i]=interp(table,T[i],0,4);
            dt=std::min(dt,.12*dx*dx*rho[i]*cp[i]/k[i]);
        }
        // Flux is power [W]. Internal exchange cancels to machine precision.
        forAll(neighbours,face)
        {
            int a=owners[face], b=neighbours[face];
            if(!active[a] || !active[b]) continue;
            const double distance=mag(centres[a]-centres[b]);
            const double faceConductance=2*k[a]*k[b]/(k[a]+k[b])/distance*areas[face];
            const double flux=faceConductance*(T[b]-T[a]);
            rate[a]+=flux; rate[b]-=flux;
            conductance[a]+=faceConductance; conductance[b]+=faceConductance;
        }
        double loss=0;
        double zmin=GREAT, ztop=-GREAT;
        for(int i=0;i<n;++i) if(active[i]) ztop=std::max(ztop,double(centres[i].z()));
        for(int i=0;i<n;++i) zmin=std::min(zmin,double(centres[i].z()));
        maximumSurfaceOffset=std::max(maximumSurfaceOffset,std::abs(ztop+dx*.5-surface));
        std::map<double,double> zCache;
        for(int i=0;i<n;++i)
        {
            if(!active[i]) continue;
            const double area=volumes[i]/dx;
            if(centres[i].z()<zmin+.1*dx)
            {
                const double q=2*k[i]*(T[i]-t0)/dx*area;
                rate[i]-=q; loss+=q;
                conductance[i]+=2*k[i]/dx*area;
            }
            if(centres[i].z()>ztop-.1*dx)
            {
                const double boundaryConductance=(conv+emissivity*5.670374419e-8*(T[i]+t0)*(T[i]*T[i]+t0*t0))*area;
                const double q=boundaryConductance*(T[i]-t0);
                rate[i]-=q; loss+=q;
                conductance[i]+=boundaryConductance;
            }
            if(laser)
            {
                const double z=centres[i].z();
                auto cached=zCache.find(z);
                if(cached==zCache.end()) cached=zCache.emplace(z,gaussianMass(z-dx*.5,std::min(z+dx*.5,surface),surface,penetration)).first;
                zMass[i]=cached->second;
            }
            if(conductance[i]>0) dt=std::min(dt,.9*rho[i]*cpFloor*volumes[i]/conductance[i]);
        }
        // Loss/exchange rates remain at step start. Rebuild the moving source
        // whenever the sensible-equivalent enthalpy cap shortens this step.
        bool accepted=false;
        for(int attempt=0;attempt<12;++attempt)
        {
            std::fill(source.begin(),source.end(),0);
            double captured=1;
            if(laser) for(int node=0;node<2;++node)
            {
                const double nodeTime=time+dt*(.5+(node==0?-1:1)*.5/std::sqrt(3.));
                const double f=(nodeTime-laser->a)/(laser->b-laser->a);
                const double x=(1-f)*laser->x0+f*laser->x1,y=(1-f)*laser->y0+f*laser->y1;
                std::map<double,double> xCache,yCache;
                double shapeSum=0;
                for(int i=0;i<n;++i) if(active[i])
                {
                    const double cx=centres[i].x(),cy=centres[i].y();
                    auto xm=xCache.find(cx),ym=yCache.find(cy);
                    if(xm==xCache.end()) xm=xCache.emplace(cx,gaussianMass(cx-dx*.5,cx+dx*.5,x,radius)).first;
                    if(ym==yCache.end()) ym=yCache.emplace(cy,gaussianMass(cy-dx*.5,cy+dx*.5,y,radius)).first;
                    nodeSource[i]=xm->second*ym->second*zMass[i];
                    shapeSum+=nodeSource[i];
                }
                if(!std::isfinite(shapeSum) || shapeSum<=0)
                    FatalErrorInFunction<<"Gaussian source has no captured mass; refine or extend mesh"<<exit(FatalError);
                captured=std::min(captured,2*shapeSum);
                // Match the NumPy reference's maximum 1% source renormalization.
                // Reject before normalization so a truncated domain cannot
                // silently amplify deposited energy.
                if(captured<1.0/1.01)
                    FatalErrorInFunction<<"Gaussian source capture "<<captured
                        <<" is below the 1/1.01 minimum; expand or refine the represented domain"
                        <<exit(FatalError);
                for(int i=0;i<n;++i) if(active[i]) source[i]+=.5*power*nodeSource[i]/shapeSum;
            }
            double allowed=dt;
            for(int i=0;i<n;++i)
                allowed=std::min(allowed,25*rho[i]*cp[i]*volumes[i]/std::max(std::abs(rate[i]+source[i]),1e-30));
            if(allowed<dt*(1-1e-12))
            {
                dt=.95*allowed; ++sourceTimestepRetries;
                continue;
            }
            minimumCaptured=std::min(minimumCaptured,captured);
            accepted=true; break;
        }
        if(!accepted || !std::isfinite(dt) || dt<=0)
            FatalErrorInFunction<<"Moving-source timestep failed to converge"<<exit(FatalError);
        for(int i=0;i<n;++i)
        {
            rate[i]+=source[i];
            maximumIncrement=std::max(maximumIncrement,dt*std::abs(rate[i])/(rho[i]*cp[i]*volumes[i]));
        }
        maximumDt=std::max(maximumDt,dt);
        minDt=std::min(minDt,dt); old=T;
        double stored=0;
        int moltenCount=0;
        for(int i=0;i<n;++i)
        {
            H[i]+=dt*rate[i]/volumes[i];
            const double h=H[i]/rho[i]+h0;
            if(!std::isfinite(h) || h<table.front()[1]-1e-8 || h>=hmax)
                FatalErrorInFunction<<"Boiling/nonphysical enthalpy: thermal model invalid; free-surface CFD required"<<exit(FatalError);
            T[i]=interp(table,h,1,0);
            const bool molten=T[i]>=liquidus && active[i];
            if(molten)
            {
                ++moltenCount;
                segmentMelt[lastActiveSegment][i] = true;
            }
            remelt[i]=remelt[i] || (molten && ever[i] && !wasMelt[i]);
            ever[i]=ever[i] || molten; wasMelt[i]=molten;
            peak=std::max(peak,T[i]); stored+=H[i]*volumes[i];
        }
        time+=dt; ++step; ein+=(laser?power:0)*dt; eout+=loss*dt;
        // Uniform Cartesian mesh: count avoids floating summation tie drift.
        if(moltenCount>peakMeltCount)
        {
            peakMeltCount=moltenCount; peakMeltStep=step;
            peakMeltTime=time; peakMeltSurface=surface; peakMeltField=T;
        }
        bool crossing=false;
        for(int i=0;i<n;++i) if(active[i] && old[i]>=liquidus && T[i]<liquidus) crossing=true;
        if(crossing)
        {
            std::vector<std::array<double,3>> gradient(n,{{0,0,0}}), oldGradient(n,{{0,0,0}}), counts(n,{{0,0,0}});
            forAll(neighbours,face)
            {
                const int a=owners[face], b=neighbours[face];
                if(!active[a] || !active[b]) continue;
                const vector delta=centres[b]-centres[a];
                for(int axis=0;axis<3;++axis) if(std::abs(delta[axis])>dx*.5)
                {
                    const double g=(T[b]-T[a])/delta[axis];
                    const double oldG=(old[b]-old[a])/delta[axis];
                    gradient[a][axis]+=g; gradient[b][axis]+=g;
                    oldGradient[a][axis]+=oldG; oldGradient[b][axis]+=oldG;
                    counts[a][axis]+=1; counts[b][axis]+=1;
                }
            }
            for(int i=0;i<n;++i) if(active[i] && old[i]>=liquidus && T[i]<liquidus)
            {
                const double theta=(old[i]-liquidus)/(old[i]-T[i]);
                double g2=0;
                for(int axis=0;axis<3;++axis)
                {
                    const double component=(oldGradient[i][axis]+theta*(gradient[i][axis]-oldGradient[i][axis]))/std::max(counts[i][axis],1.);
                    g2+=component*component;
                }
                const double g=std::sqrt(g2), cooling=(old[i]-T[i])/dt;
                if(g>1e-6) { sumG+=g; sumR+=cooling/g; sumCooling+=cooling; frontCount+=1; }
            }
        }
        if(time>=nextSample || time>=end-1e-15)
        {
            snapshots<<time<<" "<<ein<<" "<<eout<<" "<<stored<<" "<<minDt<<" "<<step<<" "<<surface<<" "<<peak
                <<" "<<sumG<<" "<<sumR<<" "<<sumCooling<<" "<<frontCount
                <<" "<<std::count(ever.begin(),ever.end(),true)<<" "<<std::count(remelt.begin(),remelt.end(),true);
            for(double t:T) snapshots<<" "<<t;
            snapshots<<"\n"; snapshots.flush();
            Info<<"THERMAL_PROGRESS "<<time/end<<" peak_K="<<peak<<" steps="<<step<<endl;
            nextSample=time+end/60;
        }
        if(step>250000) FatalErrorInFunction<<"Step budget exceeded"<<exit(FatalError);
    }
    std::ofstream peakState((runTime.path()/"peak-state.dat").c_str());
    peakState<<std::setprecision(17)<<peakMeltTime<<" "<<peakMeltSurface<<" "<<peakMeltStep<<" "<<peakMeltCount;
    for(double t:peakMeltField) peakState<<" "<<t;
    peakState<<"\n";
    peakState.close();
    if(!peakState) FatalErrorInFunction<<"Could not write peak melt field"<<exit(FatalError);
    std::ofstream trackMeltFile((runTime.path()/"track-melt.dat").c_str());
    trackMeltFile << ns << " " << n << "\n";
    for(int s=0;s<ns;++s)
    {
        std::vector<int> meltedIndices;
        for(int i=0;i<n;++i) if(segmentMelt[s][i]) meltedIndices.push_back(i);
        trackMeltFile << scans[s].track << " " << scans[s].layer << " " << meltedIndices.size();
        for(int idx : meltedIndices) trackMeltFile << " " << idx;
        trackMeltFile << "\n";
    }
    trackMeltFile.close();
    if(!trackMeltFile) FatalErrorInFunction<<"Could not write track melt field"<<exit(FatalError);
    std::ofstream diagnostics((runTime.path()/"numerical-diagnostics.json").c_str());
    diagnostics<<std::setprecision(17)
        <<"{\n  \"sourceIntegration\": \"cell-integrated-gaussian-gl2-v1\",\n"
        <<"  \"solidificationExtraction\": \"linear-liquidus-crossing-v1\",\n"
        <<"  \"meltPoolExtraction\": \"accepted-step-molten-volume-v1\",\n"
        <<"  \"overlapExtraction\": \"field-inter-track-overlap-v1\",\n"
        <<"  \"stabilityLimit\": \"local-conductance-row-sum\",\n"
        <<"  \"minimumCapturedSourceFraction\": "<<minimumCaptured<<",\n"
        <<"  \"maximumSourceRenormalization\": "<<1/minimumCaptured<<",\n"
        <<"  \"maximumSurfaceOffset_um\": "<<maximumSurfaceOffset*1e6<<",\n"
        <<"  \"maximumTimestep_s\": "<<maximumDt<<",\n"
        <<"  \"maximumEnthalpyIncrement_K\": "<<maximumIncrement<<",\n"
        <<"  \"sourceTimestepRetries\": "<<sourceTimestepRetries<<"\n}\n";
    if(!diagnostics) FatalErrorInFunction<<"Could not write numerical diagnostics"<<exit(FatalError);
    Info<<"Thermal calculation complete; NOT free-surface CFD or validated LPBF"<<endl;
    return 0;
}
