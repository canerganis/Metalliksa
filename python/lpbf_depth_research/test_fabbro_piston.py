#!/usr/bin/env python3
"""Tests for the Fabbro 2020 GPM research module (self-contained: every target is a number printed in the paper or
an internal conservation check; the only external inputs are Fabbro's own Ti-6Al-4V constants held in the module).

Run: python python/lpbf_depth_research/test_fabbro_piston.py
"""

from __future__ import annotations

import math
import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fabbro_piston as fp  # noqa: E402


class FresnelAndThreshold(unittest.TestCase):
    def test_fresnel_pi4_matches_fabbro(self):
        # Sec. 3.3: A_F(1) ~ 0.32 for alpha = pi/4 with steel n = 3.6, k = 5.0
        self.assertAlmostEqual(fp.fresnel_absorptivity(math.pi / 4.0), 0.32, delta=0.01)
        # normal incidence closed form (n-1)^2+k^2 / (n+1)^2+k^2
        n, k = 3.6, 5.0
        r0 = ((n - 1) ** 2 + k ** 2) / ((n + 1) ** 2 + k ** 2)
        self.assertAlmostEqual(fp.fresnel_absorptivity(0.0), 1.0 - r0, places=9)
        # grazing incidence -> zero absorption
        self.assertLess(fp.fresnel_absorptivity(math.radians(89.9)), 0.02)

    def test_threshold_temperature(self):
        # Appendix A remark: Pr(Tth) = Pamb gives Tth ~ 1.041 Tv0 (beta = 0.2); the closed form with c = 15.8 gives
        # 1.033, within the pre-declared 1 %
        ratio = fp.threshold_temperature_K(fp.FABBRO_TI64) / fp.FABBRO_TI64.Tv0
        self.assertAlmostEqual(ratio, 1.041, delta=0.0105)
        Tth = fp.threshold_temperature_K(fp.FABBRO_TI64)
        self.assertAlmostEqual(fp.recoil_pressure_Pa(Tth, fp.FABBRO_TI64), fp.FABBRO_TI64.Pamb, delta=1e-3)
        self.assertEqual(fp.ejection_speed(Tth * 0.999, fp.FABBRO_TI64), 0.0)


class ConservationClosure(unittest.TestCase):
    def test_energy_and_mass_residuals_below_one_percent(self):
        p = fp.FABBRO_TI64
        for Vw in (0.25, 0.5, 1.0):
            for d in (60e-6, 120e-6, 180e-6):
                for P in (150.0, 300.0, 600.0, 1200.0):
                    s = fp.solve_power(P, Vw, d, p)
                    if s["status"] != "solved":
                        continue
                    self.assertLess(s["energyResidual"], 1e-2)
                    self.assertLess(s["massResidual"], 1e-2)
                    # recomputed energy balance from the pieces
                    total = s["Pm_W"] + s["Pvap_W"] + s["Pcond_W"] + s["Pkin_W"]
                    self.assertAlmostEqual(total / (s["A_F"] * P), 1.0, places=6)
                    self.assertGreater(s["fracVap"], 0.0)
                    self.assertGreater(s["fracCond"], 0.0)
                    self.assertGreater(s["fracFus"], 0.0)
                    self.assertLess(s["fracKin"], 0.005)  # Appendix A: Pkin < 0.1 % (0.5 % declared)

    def test_power_monotonic_in_aspect_ratio_and_round_trip(self):
        p = fp.FABBRO_TI64
        Rs = [0.3, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 5.0]
        Ps = [fp.state_for_aspect_ratio(R, 0.5, 120e-6, p)["P_W"] for R in Rs]
        self.assertTrue(all(a < b for a, b in zip(Ps, Ps[1:])), Ps)
        for R, P in zip(Rs, Ps):
            s = fp.solve_power(P, 0.5, 120e-6, p)
            self.assertAlmostEqual(s["R"], R, delta=1e-6)
        # below the depression threshold P* the depth is zero
        s = fp.solve_power(0.5 * fp.threshold_powers(0.5, 120e-6, p)["Pstar_W"], 0.5, 120e-6, p)
        self.assertEqual(s["status"], "below-threshold")
        self.assertEqual(s["depth_m"], 0.0)

    def test_cos_alpha_closed_form_equals_mass_balance(self):
        p = fp.FABBRO_TI64
        s = fp.state_for_aspect_ratio(1.7, 0.8, 90e-6, p)
        self.assertAlmostEqual(math.cos(s["alpha_rad"]), fp.cos_alpha(s["Ts_K"], 0.8, 90e-6, p), places=9)
        self.assertAlmostEqual(s["Vd_m_s"], 0.8 * math.cos(s["alpha_rad"]), places=12)  # Eq. 9
        self.assertAlmostEqual(s["R"], 1.0 / math.tan(s["alpha_rad"]), places=12)      # Eq. 8
        self.assertLess(s["massResidual"], 1e-9)


class ReproductionOfFabbro2020(unittest.TestCase):
    """Published numbers, tolerances as pre-declared in docs/research/PREDECLARED_fabbro_piston.md."""

    @classmethod
    def setUpClass(cls):
        cls.rep = fp.reproduce_fabbro()
        cls.ver = fp.reproduction_verdict(cls.rep)

    def test_eq11_constants(self):
        r3 = self.rep["R3"]
        self.assertAlmostEqual(r3["b1"] / 1.2e10, 1.0, delta=0.20)
        self.assertAlmostEqual(r3["a1"] / 2.1e5, 1.0, delta=0.40)
        self.assertAlmostEqual(r3["m1"], 2.1, delta=0.4)
        self.assertAlmostEqual(r3["n1"], 2.2, delta=0.9)
        self.assertGreater(r3["r2"], 0.95)

    def test_fig4_thresholds_and_linearity(self):
        for Vw, f in self.rep["R4"].items():
            self.assertAlmostEqual(f["Pt_W"] / f["Pt_read_W"], 1.0, delta=0.15, msg=f"Vw {Vw}: {f}")
            self.assertGreater(f["r2"], 0.98)
            self.assertGreater(f["Pprime_W"], 0.0)

    def test_power_shares_and_absorptivity_range(self):
        sh = self.rep["R5"]
        self.assertGreaterEqual(sh["fracCond"][0], 0.20); self.assertLessEqual(sh["fracCond"][1], 0.55)
        self.assertGreaterEqual(sh["fracVap"][0], 0.10); self.assertLessEqual(sh["fracVap"][1], 0.45)
        self.assertGreaterEqual(sh["fracFus"][0], 0.20); self.assertLessEqual(sh["fracFus"][1], 0.50)
        self.assertLess(sh["fracKin"][1], 0.005)
        self.assertGreaterEqual(self.rep["R6"]["A_F_min"], 0.30)
        self.assertLessEqual(self.rep["R6"]["A_F_max"], 0.37)

    def test_appendix_remark_300um(self):
        r7 = self.rep["R7"]
        self.assertAlmostEqual(r7["1bar|0.05"]["P_W"] / 1200.0, 1.0, delta=0.20)
        self.assertAlmostEqual(r7["1bar|0.5"]["P_W"] / 3700.0, 1.0, delta=0.20)
        self.assertAlmostEqual(r7["0.01bar-curve-unchanged|0.05"]["P_W"] / 571.0, 1.0, delta=0.20)
        self.assertAlmostEqual(r7["1bar|0.5"]["Ts_K"] / 3600.0, 1.0, delta=0.05)
        self.assertAlmostEqual(r7["1bar|0.5"]["Vm_m_s"] / 6.0, 1.0, delta=0.30)
        self.assertAlmostEqual(r7["1bar|0.5"]["recoil_bar"] / 2.0, 1.0, delta=0.30)

    def test_required_targets_pass(self):
        self.assertTrue(self.ver["requiredPass"], self.ver)

    def test_fig7_offset_is_documented(self):
        # Fig. 7 as labelled (Vm/Vw - 1) is NOT reproduced: every point sits about 1.0 below the reading, i.e. the
        # figure plots Vm/Vw. This pins the finding so a later change that silently "fixes" it is noticed.
        offs = sorted(f["read"][1] - f["dVm_R25"] for f in self.rep["R8"].values())
        self.assertTrue(all(0.3 <= o <= 1.4 for o in offs), offs)   # figure-reading uncertainty ~0.5
        self.assertTrue(0.8 <= offs[len(offs) // 2] <= 1.2, offs)
        self.assertFalse(self.ver["R8"])


class AppPropertyVariants(unittest.TestCase):
    def test_variants_build_and_solve(self):
        for material in ("Ti-6Al-4V", "316L Stainless Steel", "Inconel 718"):
            for variant in ("P-EFF", "P-SL"):
                p = fp.props_from_app(material, variant, 20.0)
                self.assertGreater(p.K_s, 0.0)
                self.assertGreater(p.c, 5.0)
                s = fp.keyhole_depth(285.0, 960.0, 67.0, p)
                self.assertEqual(s["status"], "solved")
                self.assertLess(s["energyResidual"], 1e-2)
                self.assertLess(s["massResidual"], 1e-2)
                self.assertAlmostEqual(s["d_eff_um"], 67.0 * fp.FWHM_OVER_1E2, places=9)
        with self.assertRaises(ValueError):
            fp.props_from_app("Inconel 718", "P-FAB")
        self.assertEqual(fp.props_from_app("Ti-6Al-4V", "P-FAB", 20.0).T0, 293.15)

    def test_pinned_cunningham_case_fabbro_set(self):
        # Cunningham 2019 Fig. 3B case 95 um, 400 mm/s, 130 W (measured vapour depth 86 um, digitized) with
        # Fabbro's own Ti-6Al-4V set and his FWHM convention: regression pin of this implementation.
        s = fp.keyhole_depth(130.0, 400.0, 95.0, replace(fp.FABBRO_TI64, T0=293.15))
        self.assertEqual(s["status"], "solved")
        self.assertAlmostEqual(s["depth_m"] * 1e6, 95.0, delta=12.0)
        self.assertTrue(0.30 < s["A_F"] < 0.37)


if __name__ == "__main__":
    unittest.main(verbosity=2)
