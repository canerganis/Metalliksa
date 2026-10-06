import unittest
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from lpbf_fatigue_fracture import (
    AlloyFatigueConstants,
    MurakamiFatigueEngine,
    ALLOY_FATIGUE_DATABASE
)

class TestPhase13FatigueFracture(unittest.TestCase):

    def setUp(self):
        self.engine_ti64 = MurakamiFatigueEngine("Ti-6Al-4V")
        self.engine_in718 = MurakamiFatigueEngine("Inconel 718")

    def test_small_crack_el_haddad_asymptotic_limit(self):
        # When defect sqrt_area is extremely small (0.01 um),
        # fatigue limit must NOT diverge to infinity, but must converge to smooth sigma_e0
        res = self.engine_ti64.calculate_fatigue_limit(sqrt_area_um=0.01)
        sigma_e0 = ALLOY_FATIGUE_DATABASE["Ti-6Al-4V"].smooth_fatigue_limit_MPa
        self.assertLessEqual(res["fatigue_limit_corrected_MPa"], sigma_e0)
        self.assertGreater(res["fatigue_limit_corrected_MPa"], sigma_e0 * 0.95)

    def test_defect_location_severity(self):
        # Surface defects are more critical (lower fatigue limit) than internal pores
        res_surface = self.engine_ti64.calculate_fatigue_limit(sqrt_area_um=50.0, location="surface")
        res_internal = self.engine_ti64.calculate_fatigue_limit(sqrt_area_um=50.0, location="internal")
        self.assertLess(res_surface["fatigue_limit_corrected_MPa"], res_internal["fatigue_limit_corrected_MPa"])

    def test_stress_ratio_effect(self):
        # Tension-tension fatigue (R = 0.1) is more severe than fully reversed (R = -1)
        res_R_neg1 = self.engine_ti64.calculate_fatigue_limit(sqrt_area_um=50.0, stress_ratio_R=-1.0)
        res_R_pos01 = self.engine_ti64.calculate_fatigue_limit(sqrt_area_um=50.0, stress_ratio_R=0.1)
        self.assertLess(res_R_pos01["fatigue_limit_corrected_MPa"], res_R_neg1["fatigue_limit_corrected_MPa"])

    def test_kitagawa_takahashi_curve_generation(self):
        curve = self.engine_ti64.generate_kitagawa_takahashi_curve(location="internal", n_points=20)
        self.assertEqual(len(curve), 20)
        # Verify monotonic decrease of fatigue limit with defect size
        for i in range(len(curve) - 1):
            self.assertGreaterEqual(curve[i]["fatigue_limit_MPa"], curve[i+1]["fatigue_limit_MPa"])

    def test_paris_crack_propagation_threshold(self):
        # Very small stress range should be below Delta_K_th (infinite life)
        res = self.engine_ti64.simulate_paris_crack_growth(
            initial_defect_sqrt_area_um=20.0,
            cyclic_stress_amplitude_MPa=20.0,  # Very low stress
            stress_ratio_R=0.1
        )
        self.assertEqual(res["status"], "non_propagating")

    def test_paris_crack_propagation_failure(self):
        # High cyclic stress amplitude should cause crack growth and fracture
        res = self.engine_ti64.simulate_paris_crack_growth(
            initial_defect_sqrt_area_um=80.0,
            cyclic_stress_amplitude_MPa=280.0,
            stress_ratio_R=0.1
        )
        self.assertEqual(res["status"], "fractured")
        self.assertGreater(res["final_crack_size_um"], res["initial_crack_size_um"])
        self.assertGreater(len(res["crack_growth_curve"]), 5)

class TestPhysicsAuditKS2ElHaddadGeometryFactor(unittest.TestCase):
    """KS-2: a0 = (1/pi)(dKth/(Y sigma_e0))^2 with Murakami Y (El Haddad, Topper & Smith 1979; Murakami 2002).

    Self-contained fixture: Ti-6Al-4V-like constants (HV 340, sigma_e0 510 MPa, dKth 3.2 MPa m^0.5).
    Before the fix the code used Y = 1 plus a factor C_loc/1.56 and returned 170.2 MPa (internal) and
    156.0 MPa (surface) at sqrt(area) = 100 um, about half the Murakami value of the same defect.
    """

    def setUp(self):
        self.engine = MurakamiFatigueEngine(custom_alloy=AlloyFatigueConstants(
            "fixture-ti64", 340.0, 510.0, 3.2, 55.0, 1.8e-11, 3.3))

    def test_internal_100um(self):
        res = self.engine.calculate_fatigue_limit(100.0, "internal", -1.0)
        self.assertEqual(res["el_haddad_geometry_factor_Y"], 0.5)
        self.assertAlmostEqual(res["el_haddad_a0_um"], 3.2 ** 2 / (math.pi * (0.5 * 510.0) ** 2) * 1e6, places=2)
        self.assertEqual(res["el_haddad_a0_um"], 50.13)           # was 12.53 (Y = 1)
        self.assertEqual(res["murakami_raw_MPa"], 333.1)
        self.assertEqual(res["fatigue_limit_R_minus_1_MPa"], 294.7)  # was 170.2
        self.assertNotEqual(res["fatigue_limit_R_minus_1_MPa"], 170.2)

    def test_surface_and_subsurface_100um(self):
        res = self.engine.calculate_fatigue_limit(100.0, "surface", -1.0)
        self.assertEqual((res["el_haddad_a0_um"], res["fatigue_limit_R_minus_1_MPa"]), (29.66, 243.9))  # was 156.0
        sub = self.engine.calculate_fatigue_limit(100.0, "sub-surface", -1.0)
        self.assertEqual(sub["el_haddad_geometry_factor_Y"], 0.65)
        self.assertEqual(sub["el_haddad_a0_um"], 29.66)

    def test_long_crack_asymptote_is_murakami_threshold(self):
        # For sqrt(area) >> a0 the El-Haddad limit tends to dKth / (Y sqrt(pi sqrt(area))), i.e. the
        # threshold of Murakami's K_I,max = Y sigma sqrt(pi sqrt(area)); with Y = 1 it was 2x too low.
        for loc, y in (("internal", 0.5), ("surface", 0.65)):
            d_um = 1.0e5
            res = self.engine.calculate_fatigue_limit(d_um, loc, -1.0)
            asymptote = 3.2 / (y * math.sqrt(math.pi * d_um * 1e-6))
            self.assertAlmostEqual(res["fatigue_limit_R_minus_1_MPa"] / asymptote, 1.0, delta=2e-3)


class TestPhysicsAuditKS3ParisMurakamiSif(unittest.TestCase):
    """KS-3: Paris growth of x = sqrt(area) from x0 = sqrt(area), Delta_K = Y_loc dsigma_eff sqrt(pi x),
    dsigma_eff = sigma_max for R <= 0 (ASTM E647), closed-form life. Same self-contained fixture as KS-2."""

    C, M, KIC, DKTH = 1.8e-11, 3.3, 55.0, 3.2

    def setUp(self):
        self.engine = MurakamiFatigueEngine(custom_alloy=AlloyFatigueConstants(
            "fixture-ti64", 340.0, 510.0, self.DKTH, self.KIC, self.C, self.M))

    def _numeric_life(self, y, dse, x0, xf, n=20000):
        # independent check: midpoint rule in ln x
        u0, u1 = math.log(x0), math.log(xf)
        h = (u1 - u0) / n
        total = 0.0
        for i in range(n):
            x = math.exp(u0 + (i + 0.5) * h)
            total += x / (self.C * (y * dse * math.sqrt(math.pi * x)) ** self.M)
        return total * h

    def test_surface_defect_above_threshold_now_propagates(self):
        # Before: a = sqrt(area)/2 gave dK0 = 2.44 < 3.2 and 'non_propagating' (1e7 cycles).
        res = self.engine.simulate_paris_crack_growth(100.0, 150.0, 0.1, location="surface")
        self.assertEqual(res["status"], "fractured")
        self.assertAlmostEqual(res["delta_K_initial_MPa_m"], 0.65 * 300.0 * math.sqrt(math.pi * 100e-6), places=3)
        xf = (self.KIC / (0.65 * 300.0 / 0.9)) ** 2 / math.pi
        expected = self._numeric_life(0.65, 300.0, 100e-6, xf)
        self.assertAlmostEqual(res["cycles_to_failure"] / expected, 1.0, delta=1e-5)
        self.assertEqual(res["cycles_to_failure"], 138209)

    def test_surface_life_at_200MPa(self):
        res = self.engine.simulate_paris_crack_growth(100.0, 200.0, 0.1, location="surface")
        self.assertEqual(res["cycles_to_failure"], 52699)  # was 87,573 (1.66x optimistic)
        # The last curve point is exactly the critical size (no Euler overshoot).
        self.assertEqual(res["crack_growth_curve"][-1]["crack_length_um"], res["critical_sqrt_area_um"])
        self.assertEqual(res["final_crack_size_um"], res["critical_sqrt_area_um"])

    def test_internal_r_minus_1_uses_kmax_and_y_half(self):
        # R = -1: dsigma_eff = sigma_max = sigma_a (E647), Y = 0.5. The old code used 0.65 * 2 sigma_a at
        # sqrt(area)/2, 1.84x too high.
        res = self.engine.simulate_paris_crack_growth(400.0, 300.0, -1.0, location="internal")
        self.assertEqual((res["geometry_factor_Y"], res["delta_sigma_eff_MPa"]), (0.5, 300.0))
        dk0 = 0.5 * 300.0 * math.sqrt(math.pi * 400e-6)
        self.assertAlmostEqual(res["delta_K_initial_MPa_m"], dk0, places=3)
        self.assertEqual(res["status"], "fractured")
        xf = (self.KIC / (0.5 * 300.0)) ** 2 / math.pi
        self.assertAlmostEqual(res["critical_sqrt_area_um"], xf * 1e6, places=1)
        self.assertAlmostEqual(res["cycles_to_failure"] / self._numeric_life(0.5, 300.0, 400e-6, xf), 1.0,
                               delta=1e-5)

    def test_compressive_part_excluded_for_negative_r(self):
        # Same sigma_max (300 MPa): R = 0 and R = -1 both give dsigma_eff = sigma_max -> same life.
        r0 = self.engine.simulate_paris_crack_growth(400.0, 150.0, 0.0, location="internal")
        rm1 = self.engine.simulate_paris_crack_growth(400.0, 300.0, -1.0, location="internal")
        self.assertEqual(r0["delta_sigma_eff_MPa"], rm1["delta_sigma_eff_MPa"])
        self.assertEqual(r0["cycles_to_failure"], rm1["cycles_to_failure"])

    def test_runout_reports_the_size_at_the_cycle_limit(self):
        res = self.engine.simulate_paris_crack_growth(400.0, 300.0, -1.0, cycles_max=1000, location="internal")
        self.assertEqual((res["status"], res["cycles_to_failure"]), ("runout", 1000))
        self.assertGreater(res["final_crack_size_um"], 400.0)
        self.assertLess(res["final_crack_size_um"], res["critical_sqrt_area_um"])

    def test_static_fracture_checked_before_threshold_at_high_r(self):
        # R = 0.99, sigma_a = 10 MPa, 3000 um surface defect: dK0 = 0.65*20*sqrt(pi*3e-3) = 1.26 < dKth
        # but K_max = 0.65*2000*sqrt(pi*3e-3) = 126 MPa sqrt(m) > K_IC. Before the reorder the engine
        # returned 'non_propagating' with cycles_max (infinite life for a defect already above K_IC).
        res = self.engine.simulate_paris_crack_growth(3000.0, 10.0, 0.99, location="surface")
        self.assertLess(res["delta_K_initial_MPa_m"], self.DKTH)
        self.assertGreater(0.65 * 2000.0 * math.sqrt(math.pi * 3000e-6), self.KIC)
        self.assertEqual((res["status"], res["cycles_to_failure"]), ("fractured", 0))
        self.assertLess(res["critical_sqrt_area_um"], 3000.0)

    def test_unknown_location_is_rejected(self):
        import input_validation
        with self.assertRaises(input_validation.ValidationError):
            self.engine.simulate_paris_crack_growth(100.0, 200.0, 0.1, location="nowhere")


if __name__ == "__main__":
    unittest.main()
