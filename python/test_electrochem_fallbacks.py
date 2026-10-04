"""Engine-fix lane (audit defect 6): no invented numbers in the Tafel and corrosion-EIS engines.

Oracles are analytic or independent of the solver code:
- a Butler-Volmer scan (i = i_corr * |10^(eta/beta_a) - 10^(-eta/beta_c)|) with known
  i_corr / beta_a / beta_c, cut so that one Tafel branch is missing: the old code answered with
  an invented beta_a = 100 mV/dec (or beta_c = 120) and "R2 = 0.85";
- Faraday's law CR = i * EW / (rho * F) in explicit SI units;
- the corrosion-EIS equivalent weight: the registry's ASTM G102 EW of the resolved alloy (the old
  substring match gave Ti-6Al-4V the aluminium constants and AZ31B the steel constants).

Run from python/:  python -B -m unittest test_electrochem_fallbacks
"""

import json
import math
import os
import subprocess
import sys
import unittest
from pathlib import Path

import alloy_registry
import battery_corrosion_eis_solver as battery
import input_validation as iv
import tafel_corrosion_rate_solver as tafel

HERE = Path(__file__).parent

FARADAY = 96485.33212  # C/mol (exact SI 2019 value N_A * e, printed)
SECONDS_PER_YEAR = 31557600.0


def faraday_rate_mm_yr(i_ua_cm2: float, ew: float, density: float) -> float:
    """CR in mm/yr from i in uA/cm2: (i*1e-6 A/cm2) * EW / (F * rho) cm/s -> mm/yr."""
    return i_ua_cm2 * 1e-6 * ew / (FARADAY * density) * SECONDS_PER_YEAR * 10.0


def butler_volmer(e_corr, i_corr, beta_a, beta_c, offsets):
    pts = []
    for eta in offsets:
        i = i_corr * abs(10 ** (eta / beta_a) - 10 ** (-eta / beta_c))
        pts.append({"potential": round(e_corr + eta, 5), "currentDensity_uA_cm2": i})
    return pts


E_CORR, I_CORR, BETA_A, BETA_C = -0.30, 2.0, 0.060, 0.120
# 5 mV grid shifted so that no point sits exactly at E_corr (i = 0 there)
FULL_OFFSETS = [-0.30 + 0.01 * k + 0.0025 for k in range(61)]
CATHODIC_ONLY = [eta for eta in FULL_OFFSETS if eta < 0.0]
ANODIC_ONLY = [eta for eta in FULL_OFFSETS if eta > 0.0]


def fit(offsets, **extra):
    payload = {"action": "fit_curve", "alloyId": "steel-316l",
               "points": butler_volmer(E_CORR, I_CORR, BETA_A, BETA_C, offsets)}
    payload.update(extra)
    return tafel.fit_tafel_curve(payload)


def run_script(script, payload):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run([sys.executable, "-B", script], input=json.dumps(payload).encode(),
                          capture_output=True, cwd=str(HERE), env=env, timeout=180)
    return proc.returncode, json.loads(proc.stdout.decode("utf-8"))


class TafelFitBothBranchesTest(unittest.TestCase):
    def test_full_scan_recovers_the_analytic_parameters_and_has_no_unavailable_block(self):
        out = fit(FULL_OFFSETS)
        self.assertNotIn("fitStatus", out)
        self.assertNotIn("unavailable", out)
        self.assertAlmostEqual(out["iCorr_uA_cm2"] / I_CORR, 1.0, delta=0.10)
        self.assertAlmostEqual(out["betaA_mV_dec"] / (BETA_A * 1000), 1.0, delta=0.10)
        self.assertAlmostEqual(out["betaC_mV_dec"] / (BETA_C * 1000), 1.0, delta=0.10)
        self.assertGreater(out["anodicR2"], 0.99)
        self.assertGreater(out["cathodicR2"], 0.99)
        self.assertEqual(len(out["fittedButlerVolmer"]), 70)
        self.assertIsNotNone(out["corrosionRateMmYr"])
        self.assertIsNotNone(out["rp_ohm_cm2"])
        json.dumps(out, allow_nan=False)


class TafelFitMissingBranchTest(unittest.TestCase):
    """The old fit_tafel_curve returned beta_a = 100 mV/dec with R2 = 0.85 for a cathodic-only scan."""

    def assert_nothing_invented(self, out, missing, present):
        json.dumps(out, allow_nan=False)
        self.assertIs(out["success"], True)
        self.assertEqual(out["fitStatus"], "unavailable")
        self.assertIn(f"{missing}Branch", out["unavailable"])
        self.assertNotIn(f"{present}Branch", out["unavailable"])
        self.assertIn(missing.capitalize(), out["unavailableReason"])
        for key in (f"beta{missing[0].upper()}_mV_dec", f"beta{missing[0].upper()}_V_dec",
                    f"{missing}R2", f"{missing}Slope_dLogI_dE"):
            self.assertIsNone(out[key], key)
        # Evans intersection and everything derived from it cannot be computed
        for key in ("eCorr", "iCorr_uA_cm2", "logIcorr", "sternGearyB_V", "rp_ohm_cm2", "corrosionRateMmYr",
                    "corrosionRateMpy", "corrosionRateUmYr", "massLoss_g_m2_day", "severity"):
            self.assertIsNone(out[key], key)
        self.assertEqual(out["fittedButlerVolmer"], [])
        # the measured valley is still reported, labelled as such
        self.assertIsNotNone(out["rawEcorrValley"])
        self.assertIsNotNone(out["rawIcorrValley"])
        # the invented constants of the old fallback do not appear anywhere in the result
        flat = json.dumps({k: v for k, v in out.items() if k not in ("tangentLines", "timestamp", "provenance")})
        self.assertNotIn("0.85", flat)
        self.assertNotIn("100.0", flat)

    def test_cathodic_only_scan_has_no_invented_anodic_branch(self):
        out = fit(CATHODIC_ONLY)
        self.assert_nothing_invented(out, "anodic", "cathodic")
        # the fitted cathodic branch is a real fit of the data
        self.assertAlmostEqual(out["betaC_mV_dec"] / (BETA_C * 1000), 1.0, delta=0.15)
        self.assertGreater(out["cathodicR2"], 0.99)
        self.assertNotEqual(out["cathodicR2"], 0.85)
        self.assertTrue(any(t["logI_cathodic"] is not None for t in out["tangentLines"]))
        self.assertTrue(all(t["logI_anodic"] is None for t in out["tangentLines"]))

    def test_anodic_only_scan_has_no_invented_cathodic_branch(self):
        out = fit(ANODIC_ONLY)
        self.assert_nothing_invented(out, "cathodic", "anodic")
        self.assertAlmostEqual(out["betaA_mV_dec"] / (BETA_A * 1000), 1.0, delta=0.15)
        self.assertGreater(out["anodicR2"], 0.99)
        self.assertTrue(all(t["logI_cathodic"] is None for t in out["tangentLines"]))

    def test_wrong_sign_slope_is_unavailable_not_replaced(self):
        # Cathodic window where current falls with decreasing potential (slope > 0): not Tafel behaviour.
        pts = butler_volmer(E_CORR, I_CORR, BETA_A, BETA_C, ANODIC_ONLY)
        flipped = [{"potential": p["potential"] - 0.6, "currentDensity_uA_cm2": p["currentDensity_uA_cm2"]}
                   for p in pts]
        out = tafel.fit_tafel_curve({"action": "fit_curve", "alloyId": "steel-316l",
                                     "points": pts + flipped,
                                     "customCathodicRange": [min(p["potential"] for p in flipped),
                                                             min(p["potential"] for p in flipped) + 0.15]})
        self.assertEqual(out["fitStatus"], "unavailable")
        self.assertIn("cathodicBranch", out["unavailable"])
        self.assertIn("not < 0", out["unavailable"]["cathodicBranch"])
        self.assertIsNone(out["cathodicR2"])

    def test_too_few_points_in_a_custom_window_is_unavailable(self):
        out = fit(FULL_OFFSETS, customAnodicRange=[E_CORR + 0.0, E_CORR + 0.005])
        self.assertEqual(out["fitStatus"], "unavailable")
        self.assertIn("anodicBranch", out["unavailable"])
        self.assertIn("at least 3", out["unavailable"]["anodicBranch"])
        self.assertIsNone(out["betaA_mV_dec"])

    def test_manual_icorr_override_still_gives_the_faraday_rate_but_never_rp(self):
        out = fit(CATHODIC_ONLY, manualIcorrOverride=3.0)
        self.assertEqual(out["fitStatus"], "unavailable")  # the anodic branch is still unavailable
        self.assertNotIn("iCorr_uA_cm2", out["unavailable"])
        self.assertAlmostEqual(out["iCorr_uA_cm2"], 3.0, places=4)
        expected = faraday_rate_mm_yr(3.0, out["equivalentWeight"], out["density_g_cm3"])
        self.assertAlmostEqual(out["corrosionRateMmYr"] / expected, 1.0, delta=1e-4)
        self.assertIsNone(out["sternGearyB_V"])
        self.assertIsNone(out["rp_ohm_cm2"])
        self.assertIsNone(out["betaA_mV_dec"])

    def test_a_point_without_potential_or_current_is_refused_not_filled(self):
        good = butler_volmer(E_CORR, I_CORR, BETA_A, BETA_C, FULL_OFFSETS)
        with self.assertRaises(iv.ValidationError) as ctx:
            tafel.fit_tafel_curve({"points": good + [{"potential": -0.2}], "alloyId": "steel-316l"})
        self.assertEqual(ctx.exception.field, f"points[{len(good)}].current")
        with self.assertRaises(iv.ValidationError) as ctx:
            tafel.fit_tafel_curve({"points": good + [{"currentDensity_uA_cm2": 1.0}], "alloyId": "steel-316l"})
        self.assertEqual(ctx.exception.field, f"points[{len(good)}].potential")


class TafelSolveRequiredIcorrTest(unittest.TestCase):
    BASE = {"alloyId": "steel-316l", "specimenAreaCm2": 1.0}

    def test_missing_icorr_is_unavailable_not_1_25(self):
        out = tafel.solve_tafel_corrosion_rate(dict(self.BASE))
        self.assertIs(out["success"], True)
        self.assertEqual(out["status"], "unavailable")
        self.assertIn("iCorr_uA_cm2 was not supplied", out["unavailableReason"])
        for key in ("corrosionRateMmYr", "corrosionRateMpy", "corrosionRateUmYr", "massLoss_g_m2_day",
                    "sternGearyB_V", "rp_ohm_cm2", "iCorr_uA_cm2", "eCorr_V", "betaA", "betaC",
                    "rulUniformYears", "rulPittingYears", "severity", "pythonCode"):
            self.assertIsNone(out[key], key)
        self.assertEqual(out["timelineProjections"], [])
        self.assertEqual(out["temperatureSensitivity"], [])
        json.dumps(out, allow_nan=False)

    def test_zero_negative_and_non_numeric_icorr_are_unavailable_not_defaulted(self):
        for bad in (0, 0.0, -2.0, "abc", True, float("inf")):
            with self.subTest(icorr=bad):
                out = tafel.solve_tafel_corrosion_rate(dict(self.BASE, iCorr_uA_cm2=bad))
                self.assertEqual(out["status"], "unavailable")
                self.assertIsNone(out["corrosionRateMmYr"])
                self.assertIn("iCorr_uA_cm2", out["unavailable"])

    def test_aliases_are_still_accepted(self):
        for key in ("icorr", "i_corr"):
            out = tafel.solve_tafel_corrosion_rate(dict(self.BASE, betaA=0.12, betaC=0.10, **{key: 2.0}))
            self.assertNotIn("status", out)
            self.assertEqual(out["iCorr_uA_cm2"], 2.0)

    def test_missing_betas_leave_rp_unavailable_and_the_faraday_rate_intact(self):
        out = tafel.solve_tafel_corrosion_rate(dict(self.BASE, iCorr_uA_cm2=1.25))
        self.assertEqual(out["status"], "partial")
        self.assertEqual(set(out["unavailable"]), {"betaA", "betaC"})
        self.assertIsNone(out["sternGearyB_V"])
        self.assertIsNone(out["rp_ohm_cm2"])
        self.assertIsNone(out["rp_apparent_ohm"])
        self.assertIsNone(out["betaA"])
        self.assertIsNone(out["betaC"])
        self.assertAlmostEqual(out["corrosionRateMmYr"] / faraday_rate_mm_yr(1.25, 24.8205, 7.98), 1.0, delta=1e-3)
        self.assertNotIn("sternGeary", out["pythonCode"].replace("Stern-Geary B and Rp are unavailable", ""))
        json.dumps(out, allow_nan=False)

    def test_complete_input_is_unchanged(self):
        out = tafel.solve_tafel_corrosion_rate(dict(self.BASE, iCorr_uA_cm2=1.25, eCorr_V=-0.35,
                                                    betaA=0.12, betaC=0.10))
        self.assertNotIn("status", out)
        self.assertNotIn("unavailable", out)
        b = 0.12 * 0.10 / (2.302585 * 0.22)
        self.assertEqual(out["sternGearyB_V"], round(b, 5))
        self.assertEqual(out["rp_ohm_cm2"], round(b / 1.25e-6, 1))
        self.assertEqual(out["eCorr_V"], -0.35)

    def test_alloy_is_still_validated_before_the_unavailable_result(self):
        with self.assertRaises(iv.ValidationError) as ctx:
            tafel.solve_tafel_corrosion_rate({"alloyId": "unobtainium-x"})
        self.assertEqual(ctx.exception.code, iv.UNKNOWN_ALLOY)

    def test_cli_exit_codes(self):
        code, out = run_script("tafel_corrosion_rate_solver.py", dict(self.BASE))
        self.assertEqual(code, 0)
        self.assertEqual(out["status"], "unavailable")
        code, out = run_script("tafel_corrosion_rate_solver.py", {"alloyId": "unobtainium-x"})
        self.assertEqual(code, 2)
        self.assertEqual(out["error"]["code"], "UNKNOWN_ALLOY")


class CorrosionEISEquivalentWeightTest(unittest.TestCase):
    """simulate_corrosion_eis_and_kinetics: registry EW/density, never a substring guess."""

    I0 = 1.0
    # the ids CorrosionEISKineticsStudio sends (after the option values were fixed to resolvable ids)
    UI_IDS = ("steel-316l", "al-7075", "az31b", "ti-6al-4v", "steel-1018")

    def run_kinetics(self, metal_id):
        return battery.simulate_corrosion_eis_and_kinetics(metal_id, 0.12, 0.10, self.I0, 0.4, 0.0)

    def test_each_ui_alloy_uses_the_registry_ew_and_density(self):
        k1 = (1e-6 * SECONDS_PER_YEAR * 10.0) / FARADAY
        for metal_id in self.UI_IDS:
            with self.subTest(metal_id=metal_id):
                out = self.run_kinetics(metal_id)
                record = alloy_registry.resolve_alloy(metal_id, alloy_registry.DOMAIN_CORROSION)
                table = record.domains[alloy_registry.DOMAIN_CORROSION]
                self.assertEqual(out["alloyId"], record.id)
                self.assertEqual(out["equivalentWeight_g_eq"], table["ew"].value)
                self.assertEqual(out["density_g_cm3"], table["density_g_cm3"].value)
                self.assertAlmostEqual(out["corrosionRate_mm_yr"] / (k1 * self.I0 * table["ew"].value
                                                                    / table["density_g_cm3"].value), 1.0,
                                       delta=2e-3)

    def test_ti64_no_longer_matches_aluminium_and_az31b_no_longer_gets_steel(self):
        # Audit numbers: Ti-6Al-4V was +19 % (its id contains "al"), AZ31B -48 % (no substring: steel).
        old_al = faraday_rate_mm_yr(self.I0, 9.0, 2.81)
        old_steel = faraday_rate_mm_yr(self.I0, 27.9, 7.87)
        ti = self.run_kinetics("ti-6al-4v")
        mg = self.run_kinetics("az31b")
        ti_true = faraday_rate_mm_yr(self.I0, 11.8715, 4.43)
        mg_true = faraday_rate_mm_yr(self.I0, 12.101, 1.77)
        self.assertAlmostEqual(ti["corrosionRate_mm_yr"], ti_true, delta=2e-4 * ti_true + 1e-5)
        self.assertAlmostEqual(mg["corrosionRate_mm_yr"], mg_true, delta=2e-4 * mg_true + 1e-5)
        self.assertGreater(old_al / ti_true - 1.0, 0.15)      # the old Ti error was about +19 %
        self.assertLess(old_steel / mg_true - 1.0, -0.45)     # the old Mg error was about -48 %
        self.assertGreater(abs(ti["corrosionRate_mm_yr"] - old_al), 0.1 * old_al)
        self.assertGreater(abs(mg["corrosionRate_mm_yr"] - old_steel), 0.4 * old_steel)

    def test_az31b_ew_matches_a_hand_calculation_of_the_g102_rule(self):
        # AZ31B 96 Mg / 3 Al / 1 Zn (all >= 1 %): EW = 1 / sum(f n / W), valences 2/3/2, CIAAW weights.
        w = {"Mg": 24.305, "Al": 26.9815385, "Zn": 65.38}
        f = {"Mg": 0.96, "Al": 0.03, "Zn": 0.01}
        n = {"Mg": 2, "Al": 3, "Zn": 2}
        ew = 1.0 / sum(f[e] * n[e] / w[e] for e in f)
        self.assertAlmostEqual(self.run_kinetics("az31b")["equivalentWeight_g_eq"], ew, delta=2e-3)

    def test_unknown_or_partial_ids_are_refused_with_a_validation_error(self):
        for bad in ("unknown-alloy", "Inconel", "steel", "mg-az31b", "", "xyz"):
            with self.subTest(metal_id=bad):
                with self.assertRaises(iv.ValidationError) as ctx:
                    self.run_kinetics(bad)
                self.assertEqual(ctx.exception.code, iv.UNKNOWN_ALLOY)
                self.assertEqual(ctx.exception.field, "metalId")

    def test_titanium_variants_without_a_corrosion_preset_are_refused(self):
        for bad in ("Ti-6Al-4V ELI", "ti-6al4v"):
            with self.subTest(metal_id=bad):
                with self.assertRaises(iv.ValidationError) as ctx:
                    self.run_kinetics(bad)
                self.assertEqual(ctx.exception.detail["reason"], "variant-without-preset")

    def test_cli_returns_the_validation_envelope_with_exit_2(self):
        code, out = run_script("battery_corrosion_eis_solver.py",
                               {"action": "corrosion_kinetics", "metalId": "unknown-alloy"})
        self.assertEqual(code, 2)
        self.assertEqual(out["errorKind"], "validation")
        self.assertEqual(out["error"]["code"], "UNKNOWN_ALLOY")
        code, out = run_script("battery_corrosion_eis_solver.py",
                               {"action": "corrosion_kinetics", "metalId": "az31b"})
        self.assertEqual(code, 0)
        self.assertTrue(out["success"])
        self.assertEqual(out["equivalentWeight_g_eq"], 12.101)

    def test_every_substrate_option_of_the_corrosion_eis_studio_resolves_exactly(self):
        """The studio sends the option value as metalId: "mg-az31b" and "ti-6al4v" used to reach the
        substring match; they must now be ids the registry resolves (or the UI would show an error)."""
        import re
        studio = (HERE.parent / "src" / "components" / "CorrosionEISKineticsStudio.tsx").read_text(encoding="utf-8")
        select = studio[studio.index('aria-label="Substrate Alloy"'):]
        select = select[:select.index("</select>")]
        values = re.findall(r'<option value="([^"]+)"', select)
        self.assertGreaterEqual(len(values), 5)
        for value in values:
            with self.subTest(option=value):
                self.assertIsNotNone(tafel.corrosion_preset(value)["ew"])
                self.assertEqual(self.run_kinetics(value)["alloyId"], tafel.corrosion_preset(value)["registry_id"])

    def test_source_has_no_substring_alloy_match_left(self):
        source = (HERE / "battery_corrosion_eis_solver.py").read_text(encoding="utf-8")
        for pattern in ('"al" in metal_id', '"ti" in metal_id', '"ni" in metal_id', "ew = 27.9"):
            self.assertNotIn(pattern, source)


class TafelSourceGuardTest(unittest.TestCase):
    def test_the_invented_defaults_are_gone(self):
        source = (HERE / "tafel_corrosion_rate_solver.py").read_text(encoding="utf-8")
        for pattern in ("or 1.25", "or -0.35", "or 0.120", "or 0.100", "\"r2\": 0.85", "m_fall = -8.33",
                        "m_fall = 10.0", "curr_uA = 1.0"):
            self.assertNotIn(pattern, source)


if __name__ == "__main__":
    unittest.main()
