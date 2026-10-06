/*---------------------------------------------------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Copyright (C) Metalliksa Multiphysics CFD
     \\/     M anipulation  |
-------------------------------------------------------------------------------
Application
    metalliksaMeltPoolFoam

Description
    Multiphysics CFD solver for LPBF melt pool simulation:
    - 2-phase metal-gas VOF with Continuum Surface Force (CSF)
    - Enthalpy-based phase change (solid-mushy-liquid)
    - Carman-Kozeny Darcy momentum sink in mushy/solid zones
\*---------------------------------------------------------------------------*/

#include "argList.H"
#include "Time.H"
#include "fvMesh.H"
#include "pimpleSingleRegionControl.H"
#include "metalliksaMeltPoolFoam.H"
#include <fstream>
#include <iomanip>

using namespace Foam;

namespace Foam
{
namespace solvers
{
    defineTypeNameAndDebug(metalliksaMeltPoolFoam, 0);
}
}

// * * * * * * * * * * * * * * * * Constructors  * * * * * * * * * * * * * * //

Foam::solvers::metalliksaMeltPoolFoam::metalliksaMeltPoolFoam(fvMesh& mesh)
:
    incompressibleVoF(mesh),

    T_
    (
        IOobject
        (
            "T",
            mesh.time().name(),
            mesh,
            IOobject::READ_IF_PRESENT,
            IOobject::AUTO_WRITE
        ),
        mesh,
        dimensionedScalar("T0", dimTemperature, 300.0)
    ),

    H_
    (
        IOobject
        (
            "H",
            mesh.time().name(),
            mesh,
            IOobject::READ_IF_PRESENT,
            IOobject::AUTO_WRITE
        ),
        mesh,
        dimensionedScalar("H0", dimEnergy/dimVolume, 0.0)
    ),

    liquidFraction_
    (
        IOobject
        (
            "liquidFraction",
            mesh.time().name(),
            mesh,
            IOobject::READ_IF_PRESENT,
            IOobject::AUTO_WRITE
        ),
        mesh,
        dimensionedScalar("fl0", dimless, 0.0)
    ),

    SDarcy_
    (
        IOobject
        (
            "SDarcy",
            mesh.time().name(),
            mesh,
            IOobject::NO_READ,
            IOobject::NO_WRITE
        ),
        mesh,
        dimensionedScalar("zero", dimDensity/dimTime, 0.0)
    ),

    SMarangoni_
    (
        IOobject
        (
            "fMarangoni",
            mesh.time().name(),
            mesh,
            IOobject::NO_READ,
            IOobject::NO_WRITE
        ),
        mesh,
        dimensionedVector("zero", dimForce/dimVolume, vector::zero)
    ),

    SRecoil_
    (
        IOobject
        (
            "fRecoil",
            mesh.time().name(),
            mesh,
            IOobject::NO_READ,
            IOobject::NO_WRITE
        ),
        mesh,
        dimensionedVector("zero", dimForce/dimVolume, vector::zero)
    ),

    SPlume_
    (
        IOobject
        (
            "fPlume",
            mesh.time().name(),
            mesh,
            IOobject::NO_READ,
            IOobject::NO_WRITE
        ),
        mesh,
        dimensionedVector("zero", dimForce/dimVolume, vector::zero)
    ),

    ShEvap_
    (
        IOobject
        (
            "ShEvap",
            mesh.time().name(),
            mesh,
            IOobject::NO_READ,
            IOobject::NO_WRITE
        ),
        mesh,
        dimensionedScalar("zero", dimPower/dimVolume, 0.0)
    ),

    kMetal_("kMetal", dimPower/dimLength/dimTemperature, 30.0),
    kGas_(  "kGas",   dimPower/dimLength/dimTemperature, 0.026),
    cpMetal_("cpMetal", dimEnergy/dimMass/dimTemperature, 500.0),
    cpGas_(  "cpGas",   dimEnergy/dimMass/dimTemperature, 1000.0),
    solidus_T_( "solidus_T",  dimTemperature, 1650.0),
    liquidus_T_("liquidus_T", dimTemperature, 1700.0),
    latentHeat_("latentHeat", dimEnergy/dimMass, 2.7e5),
    Cmush_("Cmush", dimDensity/dimTime, 1e6),

    // Phase 2: Marangoni / surface-tension parameters
    // Default: Ti-6Al-4V at 1700 K: sigma0~1.52 N/m, dSigma/dT~-2.6e-4 N/(m K)
    sigma0_(    "sigma0",    dimForce/dimLength,             1.52),
    dSigmaDT_(  "dSigmaDT",  dimForce/dimLength/dimTemperature, -2.6e-4),
    Tref_sigma_("Tref_sigma", dimTemperature,                1700.0),
    interfaceThreshold_(1e3),   // 1/m — tuned per mesh; read from dict if present

    laser_(mesh, dictionary::null),
    evaporation_(mesh, dictionary::null),
    initialMetalVolume_(0.0)
{
    IOdictionary thermalDict
    (
        IOobject
        (
            "thermalProperties",
            mesh.time().constant(),
            mesh,
            IOobject::READ_IF_PRESENT,
            IOobject::NO_WRITE
        )
    );

    if (thermalDict.headerOk())
    {
        kMetal_.value() = thermalDict.lookupOrDefault<scalar>("kMetal", kMetal_.value());
        kGas_.value() = thermalDict.lookupOrDefault<scalar>("kGas", kGas_.value());
        cpMetal_.value() = thermalDict.lookupOrDefault<scalar>("cpMetal", cpMetal_.value());
        cpGas_.value() = thermalDict.lookupOrDefault<scalar>("cpGas", cpGas_.value());
        solidus_T_.value() = thermalDict.lookupOrDefault<scalar>("solidus_T", solidus_T_.value());
        liquidus_T_.value() = thermalDict.lookupOrDefault<scalar>("liquidus_T", liquidus_T_.value());
        latentHeat_.value() = thermalDict.lookupOrDefault<scalar>("latentHeat", latentHeat_.value());
        Cmush_.value() = thermalDict.lookupOrDefault<scalar>("Cmush", Cmush_.value());

        // Phase 2: Marangoni parameters
        sigma0_.value()      = thermalDict.lookupOrDefault<scalar>("sigma0",      sigma0_.value());
        dSigmaDT_.value()    = thermalDict.lookupOrDefault<scalar>("dSigmaDT",    dSigmaDT_.value());
        Tref_sigma_.value()  = thermalDict.lookupOrDefault<scalar>("Tref_sigma",  Tref_sigma_.value());
        interfaceThreshold_  = thermalDict.lookupOrDefault<scalar>("interfaceThreshold", interfaceThreshold_);

        // Phase 3: Evaporation and recoil parameters
        evaporation_.read(thermalDict);
        
        // Phase 4: Laser model parameters
        laser_.read(thermalDict);
    }

    updateEnthalpyAndPhaseFraction();
    updateDarcySink();
    updateMarangoniForce();         // Phase 2: compute initial Marangoni force field
    updateEvaporationAndRecoil();   // Phase 3: compute initial recoil and evaporation

    // Phase 8: zero-init solidification diagnostics
    solidificationDiag_ = SolidificationDiagnostics{0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
}

Foam::solvers::metalliksaMeltPoolFoam::~metalliksaMeltPoolFoam()
{}

void Foam::solvers::metalliksaMeltPoolFoam::updateEnthalpyAndPhaseFraction()
{
    const scalar rho1 = mixture.rho1().value();
    const scalar rho2 = mixture.rho2().value();
    const scalar cp1 = cpMetal_.value();
    const scalar cp2 = cpGas_.value();
    const scalar Lf = latentHeat_.value();
    const scalar Ts = solidus_T_.value();
    const scalar Tl = liquidus_T_.value();

    forAll(T_, cellI)
    {
        scalar temp = T_[cellI];
        if (temp <= Ts)
        {
            liquidFraction_[cellI] = 0.0;
        }
        else if (temp >= Tl)
        {
            liquidFraction_[cellI] = 1.0;
        }
        else
        {
            liquidFraction_[cellI] = (temp - Ts) / max(Tl - Ts, scalar(1e-4));
        }

        scalar rhoCp = alpha1[cellI] * (rho1 * cp1) + alpha2[cellI] * (rho2 * cp2);
        H_[cellI] = rhoCp * (temp - 273.15)
                  + alpha1[cellI] * (rho1 * Lf) * liquidFraction_[cellI];
    }
}

void Foam::solvers::metalliksaMeltPoolFoam::updateDarcySink()
{
    const scalar cm = Cmush_.value();
    forAll(liquidFraction_, cellI)
    {
        scalar fl = liquidFraction_[cellI];
        scalar aM = alpha1[cellI];
        if (fl < 0.999 && aM > 0.01)
        {
            scalar flClamped = max(fl, scalar(1e-4));
            SDarcy_[cellI] = aM * cm * sqr(1.0 - fl) / (pow3(flClamped) + 1e-3);
        }
        else
        {
            SDarcy_[cellI] = 0.0;
        }
    }
}

// Phase 2: Marangoni tangential stress
// Delegates to computeMarangoniForce() in interfaceForces.H.
// Only active in liquid-metal cells at the metal-gas interface.
void Foam::solvers::metalliksaMeltPoolFoam::updateMarangoniForce()
{
    tmp<volVectorField> tFma = computeMarangoniForce
    (
        alpha1,
        T_,
        dSigmaDT_.value(),
        interfaceThreshold_
    );
    SMarangoni_ = tFma();
}

// Phase 3 & 7: Recoil normal body force, evaporation cooling, and gas plume
void Foam::solvers::metalliksaMeltPoolFoam::updateEvaporationAndRecoil()
{
    tmp<volVectorField> tFrec = evaporation_.computeRecoilForce(alpha1, T_);
    SRecoil_ = tFrec();

    // Phase 7 Plume expansion force
    const dimensionedScalar rhoGas("rhoGas", dimDensity, mixture.rho2().value());
    tmp<volVectorField> tFplume = evaporation_.computePlumeMomentumSource(alpha1, T_, rhoGas);
    SPlume_ = tFplume();

    tmp<volScalarField> tShEvap = evaporation_.computeEvaporativeCooling(alpha1, T_);
    ShEvap_ = tShEvap();
}

void Foam::solvers::metalliksaMeltPoolFoam::momentumPredictor()
{
    updateDarcySink();
    updateMarangoniForce();         // Phase 2
    updateEvaporationAndRecoil();   // Phase 3 & 7

    volVectorField& U = U_;

    tUEqn =
    (
        fvm::ddt(rho, U) + fvm::div(rhoPhi, U)
      + MRF.DDt(rho, U)
      + divDevTau(U)
      + fvm::Sp(SDarcy_, U)
     ==
        fvModels().source(rho, U)
    );
    fvVectorMatrix& UEqn = tUEqn.ref();

    UEqn.relax();
    fvConstraints().constrain(UEqn);

    if (pimple.momentumPredictor())
    {
        solve
        (
            UEqn
         ==
            fvc::reconstruct
            (
                (
                    surfaceTensionForce()
                  - buoyancy.ghf*fvc::snGrad(rho)
                  - fvc::snGrad(p_rgh)
                ) * mesh.magSf()
            )
          + SMarangoni_    // Phase 2: Marangoni body force [N/m^3]
          + SRecoil_       // Phase 3: Recoil normal body force [N/m^3]
          + SPlume_        // Phase 7: Plume gas expansion force [N/m^3]
        );

        fvConstraints().constrain(U);
    }
}

void Foam::solvers::metalliksaMeltPoolFoam::thermophysicalPredictor()
{
    const scalar Ts = solidus_T_.value();
    const scalar Tl = liquidus_T_.value();
    const scalar deltaTsl = max(Tl - Ts, scalar(1e-4));
    const scalar Lf = latentHeat_.value();

    volScalarField cpEffMetal
    (
        IOobject("cpEffMetal", runTime.name(), mesh),
        mesh,
        cpMetal_
    );

    forAll(T_, cellI)
    {
        scalar temp = T_[cellI];
        if (temp >= Ts && temp <= Tl)
        {
            cpEffMetal[cellI] += Lf / deltaTsl;
        }
    }

    volScalarField rhoCp
    (
        IOobject("rhoCp", runTime.name(), mesh),
        alpha1 * (mixture.rho1() * cpEffMetal) + alpha2 * (mixture.rho2() * cpGas_)
    );

    volScalarField kEff
    (
        IOobject("kEff", runTime.name(), mesh),
        alpha1 * kMetal_ + alpha2 * kGas_
    );

    surfaceScalarField rhoCpPhi
    (
        "rhoCpPhi",
        mixture.rho1() * fvc::interpolate(cpEffMetal) * alphaPhi1
      + mixture.rho2() * cpGas_ * alphaPhi2
    );

    fvScalarMatrix TEqn
    (
        fvm::ddt(rhoCp, T_)
      + fvm::div(rhoCpPhi, T_)
      - fvm::laplacian(kEff, T_)
     ==
        laser_.heatSource(alpha1)
      + ShEvap_    // Phase 3: Evaporative cooling sink [W/m^3]
    );

    TEqn.relax();
    TEqn.solve();

    updateEnthalpyAndPhaseFraction();

    // Phase 8: update in-situ solidification microstructure tracking
    updateSolidificationMetrics();
}

// Phase 8: In-situ solidification front microstructure tracker
void Foam::solvers::metalliksaMeltPoolFoam::updateSolidificationMetrics()
{
    solidificationDiag_ = solidification_.compute(T_, liquidFraction_, U());
}

void Foam::solvers::metalliksaMeltPoolFoam::postSolve()
{
    incompressibleVoF::postSolve();

    InterfaceDiagnostics diag = evaluateInterfaceDiagnostics
    (
        alpha1,
        p,
        initialMetalVolume_
    );

    if (initialMetalVolume_ <= 0.0)
    {
        initialMetalVolume_ = diag.totalMetalVolume_m3;
        diag.initialMetalVolume_m3 = initialMetalVolume_;
    }

    // Phase 2: Marangoni diagnostics
    MarangoniDiagnostics maDiag = evaluateMarangoniDiagnostics
    (
        SMarangoni_,
        alpha1,
        interfaceThreshold_
    );

    // Phase 3: Evaporation and recoil diagnostics
    EvaporationDiagnostics evapDiag = evaporation_.evaluateDiagnostics
    (
        alpha1,
        T_
    );

    scalar maxU = gMax(mag(U_)().primitiveField());
    scalar maxUSolid = 0.0;
    scalar maxT = gMax(T_().primitiveField());
    scalar minT = gMin(T_().primitiveField());

    scalar spatterVolume = 0.0;
    scalar maxSpatterVel = 0.0;
    const volVectorField& C = mesh.C();

    forAll(liquidFraction_, cellI)
    {
        if (liquidFraction_[cellI] < 0.01 && alpha1[cellI] > 0.5)
        {
            maxUSolid = max(maxUSolid, mag(U_[cellI]));
        }
        
        // Phase 7: Spatter Diagnostics (liquid droplets ejected high into the gas)
        if (alpha1[cellI] > 0.5 && C[cellI].z() > 150e-6)
        {
            spatterVolume += alpha1[cellI] * mesh.V()[cellI];
            maxSpatterVel = max(maxSpatterVel, mag(U_[cellI]));
        }
    }
    
    reduce(spatterVolume, sumOp<scalar>());
    reduce(maxSpatterVel, maxOp<scalar>());

    std::ofstream diagFile((runTime.path()/"cfd-diagnostics.json").c_str());
    diagFile << std::setprecision(12)
        << "{\n"
        << "  \"solver\": \"metalliksaMeltPoolFoam-OpenFOAM14-4\",\n"
        << "  \"vofModel\": \"multiphase-vof-csf-v1\",\n"
        << "  \"marangoniModel\": \"tangential-dsigmadT-interface-v1\",\n"
        << "  \"recoilModel\": \"recoil-knight-clausius-v1\",\n"
        << "  \"evaporationEnabled\": " << (evaporation_.active() ? "true" : "false") << ",\n"
        << "  \"evaporativeMassTransferClosure\": \"absent\",\n"
        << "  \"evaporativeMassTransferClosureAvailable\": false,\n"
        << "  \"evaporativeModelQualification\": \"unqualified-mass-transfer-closure-absent\",\n"
        << "  \"laserModel\": \"moving-gaussian-surface-flux-v1\",\n"
        << "  \"time_s\": " << runTime.value() << ",\n"
        << "  \"deltaP_Pa\": " << diag.deltaP_Pa << ",\n"
        << "  \"dropletPressureInside_Pa\": " << diag.dropletPressureInside << ",\n"
        << "  \"dropletPressureOutside_Pa\": " << diag.dropletPressureOutside << ",\n"
        << "  \"totalMetalVolume_m3\": " << diag.totalMetalVolume_m3 << ",\n"
        << "  \"initialMetalVolume_m3\": " << diag.initialMetalVolume_m3 << ",\n"
        << "  \"volumeConservationError\": " << diag.volumeConservationError << ",\n"
        << "  \"maxVelocity_mps\": " << maxU << ",\n"
        << "  \"maxSolidVelocity_mps\": " << maxUSolid << ",\n"
        << "  \"maxTemperature_K\": " << maxT << ",\n"
        << "  \"minTemperature_K\": " << minT << ",\n"
        << "  \"maxMarangoniForce_Npm3\": " << maDiag.maxMarangoniMagnitude_Npm2 << ",\n"
        << "  \"rmsMarangoniForce_Npm3\": " << maDiag.rmsMarangoniMagnitude_Npm2 << ",\n"
        << "  \"marangoniInterfaceCells\": " << maDiag.interfaceCellCount << ",\n"
        << "  \"dSigmaDT_NpmK\": " << dSigmaDT_.value() << ",\n"
        << "  \"maxRecoilPressure_Pa\": " << evapDiag.maxRecoilPressure_Pa << ",\n"
        << "  \"maxEvaporationFlux_kgpm2s\": " << evapDiag.maxEvaporationFlux_kgpm2s << ",\n"
        << "  \"maxRecoilForce_Npm3\": " << evapDiag.maxRecoilForce_Npm3 << ",\n"
        << "  \"recoilActiveCells\": " << evapDiag.activeCells << ",\n"
        << "  \"spatterVolume_m3\": " << spatterVolume << ",\n"
        << "  \"maxSpatterVelocity_mps\": " << maxSpatterVel << ",\n"
        << "  \"solidification_meanG_K_m\": " << solidificationDiag_.meanG_K_m << ",\n"
        << "  \"solidification_meanR_m_s\": " << solidificationDiag_.meanR_m_s << ",\n"
        << "  \"solidification_meanPDAS_um\": " << solidificationDiag_.meanPDAS_um << ",\n"
        << "  \"solidification_meanSDAS_um\": " << solidificationDiag_.meanSDAS_um << ",\n"
        << "  \"solidification_frontCellCount\": " << solidificationDiag_.frontCellCount << "\n"
        << "}\n";
    diagFile.close();

    // Phase 8: write solidification-microstructure.json
    std::ofstream solidFile("solidification-microstructure.json");
    if (solidFile.is_open())
    {
        solidFile << std::setprecision(12)
            << "{\n"
            << "  \"model\": \"hunt-lu-pdas-kirkwood-sdas-v1\",\n"
            << "  \"time_s\": " << runTime.value() << ",\n"
            << "  \"frontCellCount\": " << solidificationDiag_.frontCellCount << ",\n"
            << "  \"meanG_K_m\": " << solidificationDiag_.meanG_K_m << ",\n"
            << "  \"maxG_K_m\": " << solidificationDiag_.maxG_K_m << ",\n"
            << "  \"meanR_m_s\": " << solidificationDiag_.meanR_m_s << ",\n"
            << "  \"maxR_m_s\": " << solidificationDiag_.maxR_m_s << ",\n"
            << "  \"meanCoolingRate_K_s\": " << solidificationDiag_.meanCoolingRate_K_s << ",\n"
            << "  \"meanPDAS_um\": " << solidificationDiag_.meanPDAS_um << ",\n"
            << "  \"meanSDAS_um\": " << solidificationDiag_.meanSDAS_um << ",\n"
            << "  \"morphologyFraction_columnar\": " << solidificationDiag_.fracColumnar << ",\n"
            << "  \"morphologyFraction_equiaxed\": " << solidificationDiag_.fracEquiaxed << ",\n"
            << "  \"morphologyFraction_mixed\": " << (1.0 - solidificationDiag_.fracColumnar - solidificationDiag_.fracEquiaxed) << "\n"
            << "}\n";
        solidFile.close();
    }
}

// * * * * * * * * * * * * * * * * Main Driver * * * * * * * * * * * * * * * //

int main(int argc, char *argv[])
{
    #include "setRootCase.H"
    #include "createTime.H"
    #include "createMesh.H"

    Foam::solvers::metalliksaMeltPoolFoam solver(mesh);
    Foam::pimpleSingleRegionControl pimple(solver.pimple);

    Info<< nl << "Starting time loop: metalliksaMeltPoolFoam (VOF + Enthalpy + Darcy)" << endl;

    while (pimple.run(runTime))
    {
        solver.preSolve();

        runTime++;
        Info<< "Time = " << runTime.userTimeName() << nl << endl;

        while (pimple.loop())
        {
            solver.prePredictor();
            solver.momentumPredictor();
            solver.thermophysicalPredictor();
            solver.pressureCorrector();
            solver.momentumTransportCorrector();
        }

        solver.postSolve();
        runTime.write();

        Info<< "ExecutionTime = " << runTime.elapsedCpuTime() << " s"
            << "  ClockTime = " << runTime.elapsedClockTime() << " s"
            << nl << endl;
    }

    Info<< "End\n" << endl;
    return 0;
}
