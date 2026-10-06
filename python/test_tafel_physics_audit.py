"""Physics-audit regressions for python/tafel_corrosion_rate_solver.py (EUQ-3, EUQ-5, EUQ-6, EUQ-13).

Each test reproduces the number the old code produced and asserts the corrected one. Fixtures are
self-contained (synthetic Butler-Volmer data; tests/fixtures/tafel-intersection-offset.json is shared
with tests/tafel-intersection-parity.test.ts).
"""

import json
import math
import unittest
from pathlib import Path

import tafel_corrosion_rate_solver as tafel
from input_validation import ValidationError

FIXTURE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "tafel-intersection-offset.json"


def _bv_points(icorr_uA, beta_a=0.12, beta_c=0.12, e_corr=-0.3, lo=-0.6, hi=0.0, step=0.005):
    """Butler-Volmer |i| = icorr*|10^(eta/ba) - 10^(-eta/bc)| on a grid, under the unit-less 'current' key."""
    n = int(round((hi - lo) / step))
    pts = []
    for k in range(n + 1):
        e = lo + k * step
        eta = e - e_corr
        pts.append({"potential": round(e, 4),
                    "current": icorr_uA * abs(10 ** (eta / beta_a) - 10 ** (-eta / beta_c))})
    return pts


def _old_per_point_unit_rule(points, area=1.0):
    """The removed heuristic (line 653 at b0d77480), decided point by point."""
    peak = max(abs(p["current"]) for p in points)
    out = []
    for p in points:
        c = p["current"]
        dens = abs(c) * 1e6 / area if (abs(c) < 0.1 and peak < 0.5) else abs(c) / area
        out.append({"potential": p["potential"], "currentDensity_uA_cm2": dens})
    return out


class CurrentUnitTests(unittest.TestCase):
    """EUQ-3: the A-vs-uA unit of 'current' was guessed per point."""

    def test_low_current_uA_scan_was_inflated_by_1e6_and_is_now_exact(self):
        pts = _bv_points(0.0006)  # max |i| = 0.19 uA, given in uA
        self.assertLess(max(p["current"] for p in pts), 0.5)
        old = tafel.fit_tafel_curve({"points": _old_per_point_unit_rule(pts), "alloyId": "ss316l"})
        self.assertGreater(old["iCorr_uA_cm2"], 100.0)  # ~550 uA/cm2: the reported wrong value
        self.assertGreater(old["corrosionRateMmYr"], 1.0)  # ~5.6 mm/y, reported as critical
        new = tafel.fit_tafel_curve({"points": pts, "alloyId": "ss316l", "currentUnit": "uA"})
        self.assertAlmostEqual(new["iCorr_uA_cm2"], 0.0006, places=4)
        self.assertLess(new["corrosionRateMmYr"], 1e-4)
        self.assertEqual(new["severity"]["code"], "OUTSTANDING")
        self.assertEqual(new["currentInput"], {"keys": ["current"], "currentUnit": "uA",
                                               "currentIsDensity": False, "densityUnit": "uA/cm2"})

    def test_mixed_scale_dataset_is_one_scale_now(self):
        # max between 0.1 and 0.5: the old rule scaled the points below 0.1 by 1e6 and left the rest,
        # so the branch slopes had the wrong sign; one stated unit fits both branches.
        pts = _bv_points(0.003, lo=-0.55, hi=-0.05)
        peak = max(p["current"] for p in pts)
        self.assertTrue(0.1 < peak < 0.5, peak)
        old = tafel.fit_tafel_curve({"points": _old_per_point_unit_rule(pts), "alloyId": "ss316l"})
        self.assertEqual(old.get("fitStatus"), "unavailable")  # anodic slope -27.7, cathodic +36.0
        self.assertIsNone(old["anodicSlope_dLogI_dE"])
        new = tafel.fit_tafel_curve({"points": pts, "alloyId": "ss316l", "currentUnit": "uA"})
        self.assertIsNone(new.get("fitStatus"))
        self.assertLess(abs(new["iCorr_uA_cm2"] / 0.003 - 1.0), 0.15)

    def test_ampere_data_and_area_division(self):
        pts = [{"potential": p["potential"], "current": p["current"] * 1e-6 * 2.0} for p in _bv_points(1.5)]
        r = tafel.fit_tafel_curve({"points": pts, "alloyId": "ss316l", "currentUnit": "A", "electrodeAreaCm2": 2.0})
        # symmetric 0.12 V/dec slopes: the fit window still feels the opposing branch (~8 % low bias)
        self.assertLess(abs(r["iCorr_uA_cm2"] / 1.5 - 1.0), 0.15)
        dens = tafel.fit_tafel_curve({"points": [{"potential": p["potential"], "current": p["current"] / 2.0}
                                                 for p in pts],
                                      "alloyId": "ss316l", "currentUnit": "A", "currentIsDensity": True,
                                      "electrodeAreaCm2": 2.0})
        self.assertAlmostEqual(dens["iCorr_uA_cm2"], r["iCorr_uA_cm2"], places=6)

    def test_unit_less_current_without_unit_is_refused(self):
        with self.assertRaises(ValidationError) as ctx:
            tafel.fit_tafel_curve({"points": _bv_points(1.0), "alloyId": "ss316l"})
        self.assertEqual((ctx.exception.code, ctx.exception.field), ("BAD_UNIT", "currentUnit"))
        with self.assertRaises(ValidationError) as ctx:
            tafel.fit_tafel_curve({"points": _bv_points(1.0), "currentUnit": "amp"})
        self.assertEqual(ctx.exception.code, "BAD_UNIT")
        text = "\n".join(f"{p['potential']},{p['current']}" for p in _bv_points(1.0))
        with self.assertRaises(ValidationError):
            tafel.fit_tafel_curve({"fileContent": text})
        r = tafel.fit_tafel_curve({"fileContent": text, "currentUnit": "uA", "alloyId": "ss316l"})
        self.assertLess(abs(r["iCorr_uA_cm2"] - 1.0), 0.15)

    def test_density_keys_need_no_unit(self):
        pts = [{"potential": p["potential"], "currentDensity_uA_cm2": p["current"]} for p in _bv_points(1.0)]
        r = tafel.fit_tafel_curve({"points": pts, "alloyId": "ss316l"})
        self.assertEqual(r["currentInput"]["keys"], ["currentDensity_uA_cm2"])
        self.assertIsNone(r["currentInput"]["currentUnit"])


class ScenarioInputTests(unittest.TestCase):
    """EUQ-5: a supplied 0 was replaced by the default (temperatureC = 0 -> 25 C)."""

    def test_zero_celsius_is_the_arrhenius_reference(self):
        at_25 = tafel.solve_tafel_corrosion_rate({"iCorr_uA_cm2": 1, "alloyId": "ss316l", "temperatureC": 25})
        at_0 = tafel.solve_tafel_corrosion_rate({"iCorr_uA_cm2": 1, "alloyId": "ss316l", "temperatureC": 0})
        row_25 = at_25["temperatureSensitivity"][0]
        row_0 = at_0["temperatureSensitivity"][0]
        self.assertEqual(row_25["tempC"], 5)
        self.assertEqual(row_25["arrheniusFactor"], 0.395)  # what temperatureC = 0 used to report
        self.assertEqual(at_0["temperatureC"], 0.0)
        ea = tafel.corrosion_preset("ss316l")["activation_energy_j_mol"]
        expected = math.exp(-ea / tafel.R_GAS * (1.0 / 278.15 - 1.0 / 273.15))
        self.assertEqual(row_0["arrheniusFactor"], round(expected, 3))
        self.assertEqual(row_0["arrheniusFactor"], 1.288)
        self.assertEqual(tafel.solve_tafel_corrosion_rate(
            {"iCorr_uA_cm2": 1, "alloyId": "ss316l", "tempC": 0})["temperatureC"], 0.0)

    def test_absent_inputs_keep_documented_defaults(self):
        r = tafel.solve_tafel_corrosion_rate({"iCorr_uA_cm2": 1, "alloyId": "ss316l"})
        self.assertEqual((r["temperatureC"], r["specimenAreaCm2"], r["initialThicknessMm"], r["allowableLossMm"]),
                         (25.0, 1.0, 5.0, 1.5))

    def test_invalid_supplied_values_are_refused_not_defaulted(self):
        cases = [({"temperatureC": -300}, "OUT_OF_RANGE", "temperatureC"),
                 ({"temperatureC": float("nan")}, "NON_FINITE", "temperatureC"),
                 ({"initialThicknessMm": 0}, "NON_POSITIVE", "initialThicknessMm"),
                 ({"allowableLossMm": 0}, "NON_POSITIVE", "allowableLossMm"),
                 ({"specimenAreaCm2": 0}, "NON_POSITIVE", "specimenAreaCm2")]
        for extra, code, field in cases:
            with self.subTest(extra=extra):
                with self.assertRaises(ValidationError) as ctx:
                    tafel.solve_tafel_corrosion_rate({"iCorr_uA_cm2": 1, "alloyId": "ss316l", **extra})
                self.assertEqual((ctx.exception.code, ctx.exception.field), (code, field))


class SeverityScaleTests(unittest.TestCase):
    """EUQ-6: Fontana's Poor band (1-5 mm/y) was merged into 'Unacceptable / Critical'; NACE SP0169 / ISO 8044 cited."""

    def test_fontana_bands(self):
        levels = [(0.01, "Outstanding"), (0.05, "Excellent"), (0.2, "Good"), (0.7, "Fair"),
                  (2.0, "Poor"), (4.99, "Poor"), (5.0, "Unacceptable"), (20.0, "Unacceptable")]
        for rate, level in levels:
            with self.subTest(rate=rate):
                band = tafel.classify_corrosion_severity(rate)
                self.assertEqual(band["level"], level)
                self.assertIn("Fontana", band["scaleSource"])
                self.assertIn("In-house", band["textBasis"])
        self.assertNotIn("imminent", tafel.classify_corrosion_severity(2.0)["description"])

    def test_no_nace_or_iso_citation(self):
        src = Path(tafel.__file__).read_text(encoding="utf-8")
        self.assertNotIn("Fontana-Greene", src)
        r = tafel.solve_tafel_corrosion_rate({"iCorr_uA_cm2": 1, "alloyId": "ss316l"})
        self.assertEqual(r["standards"], ["ASTM G102-89(2015)", "ASTM G59-97(2020)"])
        none = tafel.solve_tafel_corrosion_rate({"alloyId": "ss316l"})
        self.assertEqual(none["standards"], ["ASTM G102-89(2015)", "ASTM G59-97(2020)"])


class IntersectionLimitTests(unittest.TestCase):
    """EUQ-13: Python accepted the Evans intersection up to 0.25 V from the valley, TypeScript up to 0.15 V."""

    def test_shared_fixture(self):
        doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(doc["intersectionMaxOffsetV"], tafel.INTERSECTION_MAX_OFFSET_V)
        for name, case in doc["cases"].items():
            with self.subTest(case=name):
                r = tafel.fit_tafel_curve({"points": case["points"], "alloyId": "ss316l"})
                exp = case["expected"]
                self.assertAlmostEqual(r["eCorr"], exp["eCorr"], places=4)
                self.assertLess(abs(r["iCorr_uA_cm2"] / exp["iCorr_uA_cm2"] - 1.0), 1e-3)
                self.assertEqual(r.get("intersectionStatus"), exp["intersectionStatus"])

    def test_old_limit_gave_the_46x_icorr(self):
        # The 0.20 V case under the old 0.25 V limit: E_corr = 0.20 V and i_corr = 10^(0.2/0.12) = 46.4 uA/cm2.
        case = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]["offset_0p20_V"]
        saved = tafel.INTERSECTION_MAX_OFFSET_V
        try:
            tafel.INTERSECTION_MAX_OFFSET_V = 0.25
            old = tafel.fit_tafel_curve({"points": case["points"], "alloyId": "ss316l"})
        finally:
            tafel.INTERSECTION_MAX_OFFSET_V = saved
        self.assertAlmostEqual(old["eCorr"], 0.2, places=4)
        self.assertAlmostEqual(old["iCorr_uA_cm2"], 10 ** (0.2 / 0.12), delta=0.1)
        new = tafel.fit_tafel_curve({"points": case["points"], "alloyId": "ss316l"})
        self.assertAlmostEqual(new["iCorr_uA_cm2"], 1.0, places=3)


class GoldenGuardTests(unittest.TestCase):
    """The step_b guard accepts only the exact documented tafel rows (tools/physics_audit_changes.py)."""

    def test_documented_rows_are_exact(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
        import copy
        import capture_phase6a_golden as golden
        import drift_report
        solver, case = "tafel_corrosion_rate_solver", "solve_316l_default_fields"
        base = golden.load_golden(solver, case)["stdout"]
        new = golden.load_expected(solver, case)["stdout"]
        rows = drift_report.diff(base, new)
        self.assertEqual(golden.step_b_violations(solver, rows, new), [])
        forged = copy.deepcopy(new)
        forged["severity"]["textBasis"] = "Validated against NACE"
        self.assertTrue(golden.step_b_violations(solver, drift_report.diff(base, forged), forged))
        kept = copy.deepcopy(new)
        kept["standards"].append("NACE SP0169")
        self.assertTrue(golden.step_b_violations(solver, drift_report.diff(base, kept), kept))
        self.assertTrue(golden.step_b_violations(solver, rows, None))


if __name__ == "__main__":
    unittest.main()
