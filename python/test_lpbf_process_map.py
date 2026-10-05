"""Tests for tools/lpbf_process_map.py (stdlib unittest; screening-kernel sweep, not validation)."""

import sys
import unittest
from pathlib import Path

PY = Path(__file__).resolve().parent
sys.path.insert(0, str(PY))
sys.path.insert(0, str(PY / "tools"))

import lpbf_process_map as pm  # noqa: E402
import lpbf_public_datasets as pd  # noqa: E402

MATERIAL = "316L Stainless Steel"
_DOC = {}


def tiny_doc():
    """2 x 2 grid, 2 kernels, with overlay; built once (solver calls are the expensive part)."""
    if not _DOC:
        _DOC["d"] = pm.build_document(MATERIAL, 80.0, 30.0, 100.0, 20.0, [100.0, 400.0], [300.0, 1500.0],
                                      ["rosenthal", "eagar-tsai"], jobs=1, overlay=True, probe_raytracer=False)
    return _DOC["d"]


class RangeParsing(unittest.TestCase):
    def test_inclusive_range(self):
        p = pm.parse_range("50:500:25")
        self.assertEqual(len(p), 19)
        self.assertEqual((p[0], p[-1]), (50.0, 500.0))
        self.assertEqual(len(pm.parse_range("200:1600:100")), 15)

    def test_float_step_has_no_drift(self):
        self.assertEqual(pm.parse_range("0:1:0.1")[-1], 1.0)
        self.assertEqual(len(pm.parse_range("0:1:0.1")), 11)

    def test_list_and_errors(self):
        self.assertEqual(pm.parse_range("100, 200,300"), [100.0, 200.0, 300.0])
        self.assertEqual(pm.parse_range("75:75:10"), [75.0])
        for bad in ("1:2", "5:1:1", "1:5:0", ""):
            with self.assertRaises(ValueError):
                pm.parse_range(bad)

    def test_kernels(self):
        self.assertEqual(pm.parse_kernels("rosenthal,goldak"), ["rosenthal", "goldak"])
        with self.assertRaises(ValueError):
            pm.parse_kernels("rosenthal,bogus")


class TinyGrid(unittest.TestCase):
    def test_shape_and_schema(self):
        d = tiny_doc()
        self.assertEqual(d["schema"], "lpbf-process-map-1")
        self.assertIs(d["honesty"]["experimentalValidation"], False)
        self.assertEqual(d["grid"], {"powers_W": [100.0, 400.0], "speeds_mm_s": [300.0, 1500.0]})
        self.assertEqual(len(d["cells"]), 2 * 2 * 2)
        for key in ("implementationHash", "absorption", "inputs", "regimeBoundaries", "heuristicZones", "overlay",
                    "limits", "generatedAt"):
            self.assertIn(key, d)
        self.assertTrue(d["absorption"]["pinned"])
        self.assertEqual(d["absorption"]["fallbackWarnings"], d["absorption"]["solverCalls"])
        for c in d["cells"]:
            for key in ("width_um", "depth_um", "length_um", "extentStatus", "extentNote", "normalizedEnthalpy",
                        "regime", "defectDiagnostics", "geometricDefectScreen", "computed"):
                self.assertIn(key, c)
            self.assertIn("lackOfFusionStatus", c["defectDiagnostics"])
            self.assertIn("keyholePorosityRisk", c["defectDiagnostics"])
            self.assertIn("ballingInstabilityRisk", c["defectDiagnostics"])

    def test_non_computed_cells_are_marked(self):
        d = tiny_doc()
        for k, z in d["heuristicZones"].items():
            cells = [c for c in d["cells"] if c["kernel"] == k]
            bad = [c for c in cells if c["extentStatus"] != "computed"]
            self.assertEqual(z["nonComputed"], len(bad))
            self.assertEqual(z["computed"] + z["nonComputed"], len(cells))
            self.assertEqual(len(z["list"]), len(bad))
            for c in cells:
                self.assertEqual(c["computed"], c["extentStatus"] == "computed")
        # the fast slow-speed corner of the low-power / high-speed Rosenthal cell is a heuristic fallback
        ros = [c for c in d["cells"] if c["kernel"] == "rosenthal" and c["power_W"] == 100.0 and c["speed_mm_s"] == 1500.0]
        self.assertFalse(ros[0]["computed"])
        md = pm.render_markdown(d)
        self.assertIn(pm.NON_COMPUTED_MARK, md)
        self.assertIn("not computed", md)

    def test_marker_rendering_synthetic(self):
        d = {"schema": pm.SCHEMA, "generatedAt": "x", "implementationHash": "h",
             "honesty": {"statement": "s"},
             "inputs": {"material": "m", "beamDiameter_um": 80, "layer_um": 30, "hatch_um": 100, "preheat_C": 20,
                        "kernels": ["rosenthal"], "overlayDatasets": False},
             "regimeFilter": {"rule": "r"}, "grid": {"powers_W": [1.0], "speeds_mm_s": [1.0, 2.0]},
             "cells": [{"kernel": "rosenthal", "power_W": 1.0, "speed_mm_s": 1.0, "regime": "conduction", "computed": True},
                       {"kernel": "rosenthal", "power_W": 1.0, "speed_mm_s": 2.0, "regime": "keyhole", "computed": False}],
             "regimeBoundaries": {"rosenthal": []},
             "heuristicZones": {"rosenthal": {"cells": 2, "computed": 1, "nonComputed": 1,
                                              "byExtentStatus": {"heuristic-width-fallback": 1}, "list": []}},
             "overlay": [], "absorption": {"path": "p", "pinned": True, "howPinned": "h", "absorptivity_by_material": {},
                                           "fallbackWarnings": 0, "solverCalls": 0, "note": "n"},
             "limits": []}
        self.assertIn("| 1 | C | K* |", pm.render_markdown(d))

    def test_regime_matches_comparison_classifier(self):
        for c in tiny_doc()["cells"]:
            ref = pd.classify_regime(MATERIAL, c["power_W"], c["speed_mm_s"], 80.0, 20.0, None)
            self.assertEqual(c["regime"], ref["label"])
            self.assertAlmostEqual(c["normalizedEnthalpy"], ref["normalizedEnthalpy"], places=3)
        # the comparison tool applies the same function (no duplicated thresholds)
        self.assertIs(pm.dc.pin_flat_plate.__module__, "lpbf_dataset_comparison")
        self.assertNotIn("ENTHALPY_TRANSITION", (PY / "tools" / "lpbf_process_map.py").read_text(encoding="utf-8"))

    def test_boundaries_derived_from_labels(self):
        d = tiny_doc()
        for k, edges in d["regimeBoundaries"].items():
            lab = {(c["power_W"], c["speed_mm_s"]): c["regime"] for c in d["cells"] if c["kernel"] == k}
            expect = sum(1 for p in (100.0, 400.0) if lab[(p, 300.0)] != lab[(p, 1500.0)])
            expect += sum(1 for v in (300.0, 1500.0) if lab[(100.0, v)] != lab[(400.0, v)])
            self.assertEqual(len(edges), expect)
            for e in edges:
                self.assertNotEqual(e["from"]["regime"], e["to"]["regime"])

    def test_boundary_function_synthetic(self):
        cells = [{"kernel": "k", "power_W": p, "speed_mm_s": v, "regime": r}
                 for (p, v, r) in ((1.0, 1.0, "keyhole"), (1.0, 2.0, "conduction"),
                                   (2.0, 1.0, "keyhole"), (2.0, 2.0, "conduction"))]
        e = pm.regime_boundaries(cells, [1.0, 2.0], [1.0, 2.0], ["k"])["k"]
        self.assertEqual([x["axis"] for x in e], ["speed", "speed"])


class Overlay(unittest.TestCase):
    def test_overlay_matches_material_and_beam(self):
        rows = [
            {"dataset": "a", "rowId": "r1", "material": MATERIAL, "power_W": 200.0, "speed_mm_s": 800.0,
             "beamDiameter_um": 80.0, "layer_um": 0.0, "preheat_C": 20.0, "width_um": 100.0, "depth_um": 50.0, "balling": 0},
            {"dataset": "a", "rowId": "r2", "material": MATERIAL, "power_W": 200.0, "speed_mm_s": 800.0,
             "beamDiameter_um": 110.0, "layer_um": 0.0, "preheat_C": 20.0, "width_um": 100.0, "depth_um": 50.0, "balling": 0},
            {"dataset": "b", "rowId": "r3", "material": "Ti-6Al-4V", "power_W": 200.0, "speed_mm_s": 800.0,
             "beamDiameter_um": 80.0, "layer_um": 25.0, "preheat_C": 20.0, "width_um": 100.0, "depth_um": 50.0, "balling": None},
            {"dataset": "a", "rowId": "r4", "material": MATERIAL, "power_W": 200.0, "speed_mm_s": 800.0,
             "beamDiameter_um": 80.4, "layer_um": 30.0, "preheat_C": 20.0, "width_um": 100.0, "depth_um": 50.0, "balling": 1},
        ]
        out = pm.overlay_rows(MATERIAL, 80.0, 1.0, rows)
        self.assertEqual([r["rowId"] for r in out], ["r1", "r4"])
        self.assertEqual(out[0]["dOverW"], 0.5)
        self.assertEqual(out[1]["regime"], "balling-flagged")
        self.assertEqual(pm.overlay_rows(MATERIAL, 80.0, 0.1, rows)[-1]["rowId"], "r1")

    def test_overlay_in_document(self):
        ov = tiny_doc()["overlay"]
        self.assertGreater(len(ov), 0)
        for r in ov:
            self.assertEqual(r["beamDiameter_um"], 80.0)
            self.assertIn(r["regime"], ("conduction", "transition", "keyhole", "balling-flagged"))
            self.assertIn("width_um", r)
            self.assertIn("depth_um", r)


if __name__ == "__main__":
    unittest.main()
