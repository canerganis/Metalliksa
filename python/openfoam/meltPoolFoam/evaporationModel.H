#ifndef evaporationModel_H
#define evaporationModel_H

#include "volFields.H"
#include "surfaceFields.H"
#include "fvcGrad.H"
#include "dictionary.H"
#include <cmath>

namespace Foam
{

struct EvaporationDiagnostics
{
    scalar maxRecoilPressure_Pa;
    scalar maxEvaporationFlux_kgpm2s;
    scalar maxRecoilForce_Npm3;
    scalar activeCells;
};

class EvaporationModel
{
    const fvMesh& mesh_;
    bool active_;
    scalar latentHeatVap_;      // [J/kg] e.g. 8.9e6 for Ti64
    scalar boilingT_;           // [K] e.g. 3560 for Ti64
    scalar molarMass_;          // [kg/mol] e.g. 0.0459 for Ti64
    scalar evapCoeff_;          // accommodation coefficient beta (e.g. 0.82)
    scalar P0_;                 // ambient reference pressure [Pa] (101325.0)
    scalar R_univ_;             // universal gas constant [J/(mol K)] (8.314462618)
    scalar interfaceThreshold_; // |grad(alpha)| threshold [1/m]
    scalar plumeMomentumScale_; // Tuning factor for plume momentum force

public:
    EvaporationModel(const fvMesh& mesh, const dictionary& dict)
    :
        mesh_(mesh),
        // VOF mass-transfer closure is not implemented; require explicit opt-in.
        active_(dict.lookupOrDefault<bool>("active", false)),
        latentHeatVap_(dict.lookupOrDefault<scalar>("latentHeatVap", 8.9e6)),
        boilingT_(dict.lookupOrDefault<scalar>("boiling_T", 3560.0)),
        molarMass_(dict.lookupOrDefault<scalar>("molarMass", 0.0459)),
        evapCoeff_(dict.lookupOrDefault<scalar>("evapCoeff", 0.82)),
        P0_(dict.lookupOrDefault<scalar>("P0", 101325.0)),
        R_univ_(8.314462618),
        interfaceThreshold_(dict.lookupOrDefault<scalar>("interfaceThreshold", 1e3)),
        plumeMomentumScale_(dict.lookupOrDefault<scalar>("plumeMomentumScale", 1.0))
    {}

    bool active() const { return active_; }

    void read(const dictionary& dict)
    {
        active_ = dict.lookupOrDefault<bool>("active", active_);
        latentHeatVap_ = dict.lookupOrDefault<scalar>("latentHeatVap", latentHeatVap_);
        boilingT_ = dict.lookupOrDefault<scalar>("boiling_T", boilingT_);
        molarMass_ = dict.lookupOrDefault<scalar>("molarMass", molarMass_);
        evapCoeff_ = dict.lookupOrDefault<scalar>("evapCoeff", evapCoeff_);
        P0_ = dict.lookupOrDefault<scalar>("P0", P0_);
        interfaceThreshold_ = dict.lookupOrDefault<scalar>("interfaceThreshold", interfaceThreshold_);
        plumeMomentumScale_ = dict.lookupOrDefault<scalar>("plumeMomentumScale", plumeMomentumScale_);
    }

    // Saturation vapor pressure via Clausius-Clapeyron:
    // P_sat(T) = P0 * exp( (Lv * M / R_univ) * (1/Tb - 1/T) )
    scalar computePsat(scalar T) const
    {
        if (T < 1000.0) return 0.0;
        scalar Rs = R_univ_ / molarMass_;
        scalar exponent = (latentHeatVap_ / Rs) * (1.0 / boilingT_ - 1.0 / T);
        if (exponent > 80.0) exponent = 80.0;
        if (exponent < -80.0) return 0.0;
        return P0_ * std::exp(exponent);
    }

    // Knight (1979) recoil pressure: P_recoil = 0.54 * P_sat(T)
    scalar computePrecoil(scalar T) const
    {
        return 0.54 * computePsat(T);
    }

    // Hertz-Knudsen evaporation mass flux:
    // j_evap = beta * sqrt(M / (2 * pi * R_univ * T)) * P_sat(T) [kg/(m^2 s)]
    scalar computeEvapFlux(scalar T) const
    {
        if (T < 1000.0) return 0.0;
        scalar Psat = computePsat(T);
        if (Psat <= 0.0) return 0.0;
        const scalar pi = 3.14159265358979323846;
        scalar factor = evapCoeff_ * std::sqrt(molarMass_ / (2.0 * pi * R_univ_ * T));
        return factor * Psat;
    }

    // Recoil body force: f_recoil = P_recoil * grad(alpha1) [N/m^3]
    // In VOF, grad(alpha1) points into the metal phase, so this naturally exerts normal
    // compressive pressure pushing into the melt pool.
    tmp<volVectorField> computeRecoilForce
    (
        const volScalarField& alpha1,
        const volScalarField& T
    ) const
    {
        tmp<volVectorField> tFrecoil
        (
            new volVectorField
            (
                IOobject
                (
                    "fRecoil",
                    mesh_.time().name(),
                    mesh_,
                    IOobject::NO_READ,
                    IOobject::NO_WRITE
                ),
                mesh_,
                dimensionedVector("zero", dimForce/dimVolume, vector::zero)
            )
        );
        volVectorField& Frecoil = tFrecoil.ref();

        if (!active_) return tFrecoil;

        volVectorField gradAlpha(fvc::grad(alpha1));

        forAll(alpha1, cellI)
        {
            scalar magGa = mag(gradAlpha[cellI]);
            if (magGa < interfaceThreshold_)
            {
                Frecoil[cellI] = vector::zero;
                continue;
            }

            scalar Precoil = computePrecoil(T[cellI]);
            Frecoil[cellI] = Precoil * gradAlpha[cellI];
        }

        return tFrecoil;
    }

    // Phase 7: Plume Momentum Force
    // S_plume = -(j_evap^2 / rho_gas) * grad(alpha1) * scale
    // This pushes the gas phase away from the evaporating surface.
    tmp<volVectorField> computePlumeMomentumSource
    (
        const volScalarField& alpha1,
        const volScalarField& T,
        const dimensionedScalar& rhoGas
    ) const
    {
        tmp<volVectorField> tFplume
        (
            new volVectorField
            (
                IOobject
                (
                    "fPlume",
                    mesh_.time().name(),
                    mesh_,
                    IOobject::NO_READ,
                    IOobject::NO_WRITE
                ),
                mesh_,
                dimensionedVector("zero", dimForce/dimVolume, vector::zero)
            )
        );
        volVectorField& Fplume = tFplume.ref();

        if (!active_ || plumeMomentumScale_ <= 0.0) return tFplume;

        volVectorField gradAlpha(fvc::grad(alpha1));

        forAll(alpha1, cellI)
        {
            scalar magGa = mag(gradAlpha[cellI]);
            if (magGa < interfaceThreshold_)
            {
                Fplume[cellI] = vector::zero;
                continue;
            }

            scalar jEvap = computeEvapFlux(T[cellI]);
            // F_plume = - (j^2 / rho_gas) * grad(alpha1) * scale
            // grad(alpha1) points into liquid, so -grad points into gas.
            scalar plumeP = plumeMomentumScale_ * (jEvap * jEvap) / rhoGas.value();
            Fplume[cellI] = -plumeP * gradAlpha[cellI];
        }

        return tFplume;
    }

    // Evaporation cooling heat sink: S_h,evap = - Lv * j_evap * |grad(alpha1)| [W/m^3]
    tmp<volScalarField> computeEvaporativeCooling
    (
        const volScalarField& alpha1,
        const volScalarField& T
    ) const
    {
        tmp<volScalarField> tShEvap
        (
            new volScalarField
            (
                IOobject
                (
                    "ShEvap",
                    mesh_.time().name(),
                    mesh_,
                    IOobject::NO_READ,
                    IOobject::NO_WRITE
                ),
                mesh_,
                dimensionedScalar("zero", dimPower/dimVolume, 0.0)
            )
        );
        volScalarField& ShEvap = tShEvap.ref();

        if (!active_) return tShEvap;

        volVectorField gradAlpha(fvc::grad(alpha1));

        forAll(alpha1, cellI)
        {
            scalar magGa = mag(gradAlpha[cellI]);
            if (magGa < interfaceThreshold_)
            {
                ShEvap[cellI] = 0.0;
                continue;
            }

            scalar jEvap = computeEvapFlux(T[cellI]);
            ShEvap[cellI] = - latentHeatVap_ * jEvap * magGa;
        }

        return tShEvap;
    }

    EvaporationDiagnostics evaluateDiagnostics
    (
        const volScalarField& alpha1,
        const volScalarField& T
    ) const
    {
        EvaporationDiagnostics diag;
        diag.maxRecoilPressure_Pa = 0.0;
        diag.maxEvaporationFlux_kgpm2s = 0.0;
        diag.maxRecoilForce_Npm3 = 0.0;
        diag.activeCells = 0.0;

        if (!active_) return diag;

        volVectorField gradAlpha(fvc::grad(alpha1));
        label count = 0;

        forAll(alpha1, cellI)
        {
            scalar magGa = mag(gradAlpha[cellI]);
            if (magGa >= interfaceThreshold_)
            {
                scalar P_rec = computePrecoil(T[cellI]);
                scalar j_evap = computeEvapFlux(T[cellI]);
                scalar f_rec = P_rec * magGa;

                diag.maxRecoilPressure_Pa = max(diag.maxRecoilPressure_Pa, P_rec);
                diag.maxEvaporationFlux_kgpm2s = max(diag.maxEvaporationFlux_kgpm2s, j_evap);
                diag.maxRecoilForce_Npm3 = max(diag.maxRecoilForce_Npm3, f_rec);
                if (P_rec > 1.0) count++;
            }
        }
        diag.activeCells = scalar(count);
        return diag;
    }
};

} // End namespace Foam

#endif
