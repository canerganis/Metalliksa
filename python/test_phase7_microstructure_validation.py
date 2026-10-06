import unittest
from lpbf_solidification_microstructure import (
    hunt_lu_pdas_um,
    kirkwood_sdas_um,
    hunt_morphology,
    morphology_fractions
)
from kinetics_ttt_cct_solver import solve_phase_transformation_kinetics

class TestPhase7MicrostructureValidation(unittest.TestCase):
    def test_01_hunt_lu_pdas_lpbf_regime(self):
        # Typical LPBF: G ~ 1e6 K/m, R ~ 1.0 m/s
        # pdas = 80 * G^(-0.5) * R^(-0.25)
        # pdas = 80 * (1e6)^(-0.5) * (1)^(-0.25) = 80 * 1e-3 * 1 = 0.08 um (bounded by 0.1 um)
        G = 1.0e6
        R = 1.0
        pdas = hunt_lu_pdas_um(G, R)
        self.assertGreaterEqual(pdas, 0.1) # Minimum bound
        self.assertLess(pdas, 2.0)         # Expect sub-micron or low-micron
        
        # Slower casting regime: G ~ 1e4 K/m, R ~ 0.01 m/s
        # pdas = 80 * (1e4)^(-0.5) * (1e-2)^(-0.25) = 80 * 1e-2 * 10^0.5 = 0.8 * 3.16 = 2.53 um
        G_slow = 1.0e4
        R_slow = 0.01
        pdas_slow = hunt_lu_pdas_um(G_slow, R_slow)
        self.assertGreater(pdas_slow, pdas, "Slower cooling must result in larger primary dendrite arm spacing")

    def test_02_kirkwood_sdas(self):
        # Typical LPBF cooling rate: 1e6 K/s
        # sdas = 64.5 * Tdot^(-0.33)
        # sdas = 64.5 * (1e6)^(-0.33) = 64.5 * 10^(-1.98) ~ 0.67 um
        tdot = 1.0e6
        sdas = kirkwood_sdas_um(tdot)
        self.assertAlmostEqual(sdas, 0.67, delta=0.05)
        
        # Casting cooling rate: 1e2 K/s
        tdot_slow = 1.0e2
        sdas_slow = kirkwood_sdas_um(tdot_slow)
        self.assertAlmostEqual(sdas_slow, 14.1, delta=0.2)
        self.assertGreater(sdas_slow, sdas)

    def test_03_hunt_morphology(self):
        # Columnar: G/R > 1e8 K s/m^2
        self.assertEqual(hunt_morphology(1e6, 0.005), "columnar")
        # Equiaxed: G/R < 1e6
        self.assertEqual(hunt_morphology(1e5, 0.2), "equiaxed")
        # Mixed: G/R between 1e6 and 1e8
        self.assertEqual(hunt_morphology(1e6, 0.1), "mixed")
        
        fracs = morphology_fractions(1e6, 0.1)
        self.assertGreater(fracs["columnar"], 0.0)
        self.assertGreater(fracs["equiaxed"], 0.0)
        self.assertAlmostEqual(fracs["columnar"] + fracs["equiaxed"] + fracs["mixed"], 1.0)

    def test_04_kinetics_lpbf_quench(self):
        # LPBF Cooling Rate (1e6 K/s) for AISI 4140 should suppress diffusion completely.
        # Martensite fraction should be very high (or 100% within metastable limit).
        res = solve_phase_transformation_kinetics(
            alloy_name="AISI 4140",
            cooling_rate_c_s=1e5, # Very fast cooling
            grain_size_um=25.0
        )
        self.assertTrue(res["success"])
        gap = res["calphadVsKineticsGap"]["kineticRealityAtSelectedCooling"]
        self.assertTrue(gap["isSuppressedEquilibrium"])
        # Lane kin-li (Li 1998 model): no diffusional start above Ms; Koistinen-Marburger fraction at 25 C
        self.assertIn("No diffusional start above Ms", gap["verdict"])
        self.assertGreaterEqual(gap["predictedMartensite_pct"], 90.0)

    def test_05_kinetics_slow_cooling(self):
        # Slow cooling (furnace anneal) for AISI 4140 should result in Pearlite/Bainite.
        res = solve_phase_transformation_kinetics(
            alloy_name="AISI 4140",
            cooling_rate_c_s=0.5, # Slow cool
            grain_size_um=25.0
        )
        gap = res["calphadVsKineticsGap"]["kineticRealityAtSelectedCooling"]
        self.assertFalse(gap["isSuppressedEquilibrium"])
        # Lane kin-li: a diffusional (ferrite) start is reached; fractions are not computed, so no martensite %
        self.assertIn("Ferrite start at", gap["verdict"])
        self.assertIsNone(gap["predictedMartensite_pct"])

if __name__ == '__main__':
    unittest.main()
