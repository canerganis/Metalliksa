"""Focused contract for phase-resolved OpenFOAM thermal advection flux."""

from pathlib import Path
import re
import unittest


SOLVER_SOURCE = (
    Path(__file__).resolve().parent
    / "openfoam"
    / "meltPoolFoam"
    / "metalliksaMeltPoolFoam.C"
)


def phase_resolved_heat_capacity_flux(
    alpha_phi1, alpha_phi2, rho1, rho2, cp_eff_metal, cp_gas
):
    """Mass-specific-heat flux [W/K] from signed phase volume fluxes [m^3/s]."""
    return rho1 * cp_eff_metal * alpha_phi1 + rho2 * cp_gas * alpha_phi2


class TestOpenFoamThermalAdvectionFlux(unittest.TestCase):
    def test_solver_uses_phase_resolved_mass_heat_capacity_flux(self):
        source = SOLVER_SOURCE.read_text(encoding="utf-8")
        match = re.search(
            r"surfaceScalarField\s+rhoCpPhi\s*\((.*?)\);",
            source,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(match, "rhoCpPhi production field was not found")
        expression = re.sub(r"\s+", "", match.group(1))
        self.assertEqual(
            expression,
            '"rhoCpPhi",mixture.rho1()*fvc::interpolate(cpEffMetal)*alphaPhi1'
            '+mixture.rho2()*cpGas_*alphaPhi2',
        )
        self.assertIn("cpEffMetal[cellI] += Lf / deltaTsl;", source)
        self.assertNotIn("rhoPhi", expression)
        self.assertNotIn("cpEff", expression.replace("cpEffMetal", ""))

    def test_phase_endpoints_mushy_capacity_and_signed_flux(self):
        rho_metal, rho_gas = 8000.0, 2.0
        cp_metal, cp_gas = 600.0, 1000.0
        latent_heat, mushy_interval_K = 270_000.0, 100.0
        cp_eff_metal = cp_metal + latent_heat / mushy_interval_K

        # Pure-metal and pure-gas faces reduce to each phase's own rho*cp flux.
        metal_only = phase_resolved_heat_capacity_flux(
            2e-6, 0.0, rho_metal, rho_gas, cp_eff_metal, cp_gas
        )
        gas_only = phase_resolved_heat_capacity_flux(
            0.0, 3e-6, rho_metal, rho_gas, cp_eff_metal, cp_gas
        )
        self.assertAlmostEqual(metal_only, rho_metal * cp_eff_metal * 2e-6)
        self.assertAlmostEqual(gas_only, rho_gas * cp_gas * 3e-6)
        self.assertAlmostEqual(
            metal_only, rho_metal * (cp_metal + latent_heat / mushy_interval_K) * 2e-6
        )

        # At a mixed interface the separate phase fluxes retain their own rho and cp.
        mixed = phase_resolved_heat_capacity_flux(
            2e-6, 1e-6, rho_metal, rho_gas, cp_eff_metal, cp_gas
        )
        self.assertAlmostEqual(
            mixed,
            rho_metal * cp_eff_metal * 2e-6 + rho_gas * cp_gas * 1e-6,
        )

        # Phase fluxes are signed; reversing both must reverse the heat-capacity flux.
        opposed = phase_resolved_heat_capacity_flux(
            1e-6, -0.25e-6, rho_metal, rho_gas, cp_eff_metal, cp_gas
        )
        reversed_opposed = phase_resolved_heat_capacity_flux(
            -1e-6, 0.25e-6, rho_metal, rho_gas, cp_eff_metal, cp_gas
        )
        self.assertAlmostEqual(reversed_opposed, -opposed)
        self.assertAlmostEqual(
            opposed,
            rho_metal * cp_eff_metal * 1e-6 - rho_gas * cp_gas * 0.25e-6,
        )


if __name__ == "__main__":
    unittest.main()
