import json
import math
import unittest

from lpbf_defect_diagnostics import defect_diagnostics


class DefectDiagnosticsTests(unittest.TestCase):
    def test_individually_sufficient_dimensions_can_fail_ellipse(self):
        result = defect_diagnostics(120, 60, 200, 100, 40)
        lof = result["lackOfFusion"]
        self.assertGreater(lof["ellipseIndex"], 1)
        self.assertLess(lof["signedMargin"], 0)
        self.assertTrue(lof["riskScreened"])
        self.assertLess(lof["overlapDepth_um"], 40)
        self.assertLess(lof["maximumHatch_um"], 100)

    def test_analytic_boundary_and_neighbors(self):
        boundary = defect_diagnostics(100, 100, 200, 60, 80)["lackOfFusion"]
        self.assertEqual(boundary["ellipseIndex"], 1)
        self.assertEqual(boundary["status"], "marginal")
        self.assertAlmostEqual(boundary["overlapDepth_um"], 80)
        self.assertAlmostEqual(boundary["maximumHatch_um"], 60)
        self.assertEqual(defect_diagnostics(100, 100, 200, 59, 80)["lackOfFusion"]["status"], "covered-geometrically")
        self.assertEqual(defect_diagnostics(100, 100, 200, 61, 80)["lackOfFusion"]["status"], "lack-of-fusion-screened")

    def test_hatch_and_layer_monotonicity(self):
        base = defect_diagnostics(120, 60, 200, 50, 20)["lackOfFusion"]
        for hatch, layer in [(60, 20), (50, 30)]:
            changed = defect_diagnostics(120, 60, 200, hatch, layer)["lackOfFusion"]
            self.assertGreater(changed["ellipseIndex"], base["ellipseIndex"])
            self.assertLess(changed["signedMargin"], base["signedMargin"])

    def test_homothetic_scaling(self):
        base = defect_diagnostics(120, 60, 200, 50, 20)
        for scale in [0.001, 1000]:
            scaled = defect_diagnostics(*(v * scale for v in (120, 60, 200, 50, 20)))
            for key in ["ellipseIndex", "signedMargin"]:
                self.assertAlmostEqual(base["lackOfFusion"][key], scaled["lackOfFusion"][key])
            for key in ["overlapDepth_um", "maximumHatch_um"]:
                self.assertAlmostEqual(base["lackOfFusion"][key] * scale, scaled["lackOfFusion"][key])

    def test_zero_melt_is_explicit_and_finite(self):
        for width, depth, status in [(0, 0, "no-melt"), (0, 50, "no-melt"), (50, 0, "inadequate-penetration")]:
            result = defect_diagnostics(width, depth, 0, 50, 20)
            self.assertEqual(result["lackOfFusion"]["status"], status)
            self.assertIsNone(result["lackOfFusion"]["ellipseIndex"])
            self.assertTrue(result["lackOfFusion"]["riskScreened"])
            json.dumps(result, allow_nan=False)

    def test_aggregate_is_unresolved(self):
        result = defect_diagnostics(500, 200, 1000, 50, 20, aggregate=True)
        self.assertEqual(result["status"], "unresolved")
        self.assertIsNone(result["lackOfFusion"]["ellipseIndex"])
        self.assertIsNone(result["keyhole"]["depthToWidth"])
        self.assertIsNone(result["balling"]["lengthToWidth"])

    def test_indicators_do_not_invent_pore_risks(self):
        result = defect_diagnostics(100, 150, 1000, 50, 20)
        self.assertEqual(result["keyhole"]["depthToWidth"], 1.5)
        # Wave B LA-3: D/W alone gives no keyhole risk; King et al. 2014 sec. 5.2 mode label only.
        self.assertIsNone(result["keyhole"]["risk"])
        self.assertEqual(result["keyhole"]["kingModeIndicator"], "keyhole-mode")
        for name in ["balling", "gasPore"]:
            self.assertIsNone(result[name]["risk"])
            self.assertTrue(result[name]["reason"])
        self.assertIsNone(result["porosity"]["value"])
        self.assertEqual(result["modelId"], "elliptic-overlap-screening-v2")
        from lpbf_defect_diagnostics import BALLING_SCREEN_SOURCES
        self.assertIn("Yadroitsev", BALLING_SCREEN_SOURCES[0])
        self.assertIn("Eq. (12)-(13)", BALLING_SCREEN_SOURCES[0])
        self.assertIn("10.1016/j.apsusc.2007.08.074", BALLING_SCREEN_SOURCES[1])
        self.assertFalse(any("Phys. Procedia" in source for source in BALLING_SCREEN_SOURCES))
        json.dumps(result, allow_nan=False)

    def test_invalid_dimensions(self):
        for index in range(5):
            for invalid in [-1, math.nan, math.inf, -math.inf, True, "10", None]:
                args = [120, 60, 200, 50, 20]
                args[index] = invalid
                with self.subTest(index=index, invalid=invalid), self.assertRaises(ValueError):
                    defect_diagnostics(*args)
        for index in [3, 4]:
            args = [120, 60, 200, 50, 20]
            args[index] = 0
            with self.assertRaises(ValueError):
                defect_diagnostics(*args)
        with self.assertRaises(ValueError):
            defect_diagnostics(120, 60, 200, 50, 20, aggregate=1)

    def test_extreme_finite_dimensions_never_emit_nonfinite_json(self):
        for args in [(1e-300, 1e-300, 1e300, 1e300, 1e300), (1e300, 1e300, 1e300, 1e-300, 1e-300)]:
            result = defect_diagnostics(*args)
            json.dumps(result, allow_nan=False)
        self.assertEqual(defect_diagnostics(1e-300, 1, 1, 1e300, 1)["status"], "unresolved")


if __name__ == "__main__":
    unittest.main()
