"""Tests for the public single-track dataset loaders, regime screen and comparison statistics.

No solver is run here (the comparison summary is exercised on a tiny synthetic prediction set).
"""

import json
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))

import lpbf_public_datasets as pds  # noqa: E402
import lpbf_dataset_comparison as cmp  # noqa: E402

COMMITTED_JSON = Path(__file__).resolve().parent.parent / "docs" / "LPBF_DATASET_COMPARISON_2026-10-05.json"


class LoaderTests(unittest.TestCase):
    def test_hofmann_rows_units_and_ranges(self):
        d = pds.load_hofmann_316l()
        rows = d["rows"]
        self.assertEqual(len(rows), 677)
        self.assertEqual(d["provenance"]["fileSha256"], pds.HOFMANN_TABLE_SHA256)
        self.assertEqual(d["provenance"]["doi"], "10.5281/zenodo.16979848")
        self.assertEqual(d["provenance"]["license"], "CC BY 4.0")
        self.assertTrue(all(r["material"] == "316L Stainless Steel" for r in rows))
        self.assertEqual({r["beamDiameter_um"] for r in rows}, {50.0, 80.0, 110.0, 140.0})
        self.assertEqual({r["layer_um"] for r in rows}, {0.0, 30.0, 60.0})
        self.assertTrue(all(50.0 <= r["power_W"] <= 500.0 for r in rows))
        self.assertTrue(all(225.0 <= r["speed_mm_s"] <= 1500.0 for r in rows))
        self.assertTrue(all(50.0 < r["width_um"] < 400.0 and 10.0 < r["depth_um"] < 600.0 for r in rows))
        self.assertEqual(sum(r["balling"] for r in rows), 216)
        self.assertEqual(len({r["rowId"] for r in rows}), 677)
        self.assertTrue(all(r["preheat_C"] == 20.0 for r in rows))
        self.assertEqual(rows[0]["rowId"], "hofmann-0001")
        self.assertEqual((rows[0]["power_W"], rows[0]["speed_mm_s"], rows[0]["width_um"]), (500.0, 900.0, 211.662))

    def test_totis_rows_units_and_ranges(self):
        d = pds.load_totis_ti64()
        rows = d["rows"]
        self.assertEqual(len(rows), 80)
        self.assertEqual(d["provenance"]["fileSha256"], pds.TOTIS_TABLE_SHA256)
        self.assertEqual(d["provenance"]["doi"], "10.17632/s9438vb5xd.1")
        self.assertTrue(all(r["material"] == "Ti-6Al-4V" and r["beamDiameter_um"] == 50.0
                            and r["layer_um"] == 25.0 for r in rows))
        self.assertEqual(sorted({r["power_W"] for r in rows}), [50.0 * i for i in range(1, 9)])
        self.assertEqual(sorted({r["speed_mm_s"] for r in rows}), [250.0 * i for i in range(1, 11)])
        self.assertTrue(all(r["width_um"] > 30 and r["depth_um"] > 3 for r in rows))
        cell = next(r for r in rows if r["power_W"] == 400 and r["speed_mm_s"] == 250)
        self.assertAlmostEqual(cell["depth_um"], 1076.27118644068, places=6)
        self.assertAlmostEqual(cell["width_um"], 242.017874875869, places=6)

    def test_material_keys_exist_in_authority(self):
        from four_alloy_materials import thermal_props
        for m in ("316L Stainless Steel", "Ti-6Al-4V"):
            self.assertIsNotNone(thermal_props(m))

    def test_non_committed_path_reports_its_own_digest(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "meltpool_geometry.csv"
            bad.write_bytes(pds.HOFMANN_TABLE.read_bytes() + b"\n")
            # a non-committed path is not pinned, but the digest reported must differ
            d = pds.load_hofmann_316l(bad)
            self.assertNotEqual(d["provenance"]["fileSha256"], pds.HOFMANN_TABLE_SHA256)


class RegimeTests(unittest.TestCase):
    def test_hand_computed_enthalpy_and_labels(self):
        # 316L (rho 7990, k 16.3, cp 500, T_liq 1400 C, eta 0.42), 100 W, 1000 mm/s, d 50 um, T0 20 C:
        # alpha = 4.080e-6 m2/s; denom = rho cp 1380 sqrt(pi alpha v r^3) = 2.467e-3 W; dH/hs = 42/2.467e-3/1e3... = 17.02
        a = pds.classify_regime("316L Stainless Steel", 100, 1000, 50, 20.0, 0)
        self.assertAlmostEqual(a["normalizedEnthalpy"], 17.02, delta=0.02)
        self.assertEqual(a["label"], "transition")
        b = pds.classify_regime("Ti-6Al-4V", 50, 2500, 50, 20.0, None)
        self.assertLess(b["normalizedEnthalpy"], 15.0)
        self.assertEqual(b["label"], "conduction")
        c = pds.classify_regime("Ti-6Al-4V", 400, 250, 50, 20.0, None)
        self.assertGreater(c["normalizedEnthalpy"], 30.0)
        self.assertEqual(c["label"], "keyhole")

    def test_balling_flag_overrides(self):
        r = pds.classify_regime("316L Stainless Steel", 100, 1000, 50, 20.0, 1)
        self.assertEqual(r["label"], "balling-flagged")
        self.assertAlmostEqual(r["normalizedEnthalpy"], 17.02, delta=0.02)


class SummaryTests(unittest.TestCase):
    @staticmethod
    def _row(i, label, meas_w, meas_d, preds):
        return {"rowId": f"r{i}", "regime": {"label": label},
                "measured": {"width_um": meas_w, "depth_um": meas_d},
                "predictions": {"rosenthal": preds}}

    def test_synthetic_summary(self):
        ok = lambda w, d: {"width_um": w, "depth_um": d, "included": True}  # noqa: E731
        rows = [
            self._row(1, "conduction", 100.0, 50.0, ok(110.0, 40.0)),    # +10 %, -20 %
            self._row(2, "conduction", 100.0, 50.0, ok(70.0, 100.0)),    # -30 %, +100 %
            self._row(3, "conduction", 100.0, 50.0, {"width_um": 1.0, "depth_um": 1.0, "included": False}),
            self._row(4, "keyhole", 200.0, 300.0, ok(250.0, 100.0)),
        ]
        s = cmp.summarize(rows, kernels=("rosenthal",))["rosenthal"]
        c = s["conduction"]
        self.assertEqual((c["n"], c["nExcluded"]), (2, 1))
        self.assertAlmostEqual(c["width"]["bias_pct"], -10.0)
        self.assertAlmostEqual(c["width"]["mape_pct"], 20.0)
        self.assertAlmostEqual(c["width"]["rmse_um"], math.sqrt((100 + 900) / 2))
        self.assertEqual(c["width"]["within30pct"], 1.0)      # |-30 %| <= 30 %
        self.assertAlmostEqual(c["depth"]["bias_pct"], 40.0)
        self.assertEqual(c["depth"]["within30pct"], 0.5)  # -20 % in, +100 % out
        self.assertEqual(c["depth"]["withinFactor2"], 1.0)    # ratios 0.8 and 2.0 inside [0.5, 2]
        self.assertEqual((s["all"]["n"], s["all"]["nExcluded"]), (3, 1))
        self.assertEqual(s["keyhole"]["depth"]["withinFactor2"], 0.0)  # 100/300 < 0.5

    def test_empty_slot_has_null_stats(self):
        rows = [self._row(1, "conduction", 100.0, 50.0, {"width_um": None, "depth_um": None, "included": False})]
        s = cmp.summarize(rows, kernels=("rosenthal",))["rosenthal"]["conduction"]
        self.assertEqual((s["n"], s["nExcluded"], s["width"], s["depth"]), (0, 1, None, None))


class CommittedComparisonTests(unittest.TestCase):
    def test_committed_json_honesty_and_shape(self):
        self.assertTrue(COMMITTED_JSON.exists(), "run tools/lpbf_dataset_comparison.py first")
        doc = json.loads(COMMITTED_JSON.read_text(encoding="utf-8"))
        self.assertEqual(doc["schema"], "lpbf-dataset-comparison-1")
        self.assertIs(doc["honesty"]["experimentalValidation"], False)
        self.assertIn("not validation", doc["honesty"]["statement"])
        self.assertEqual(doc["kernels"], ["rosenthal", "eagar-tsai", "goldak"])
        self.assertEqual({d["sha256"] for d in doc["datasets"]}, {pds.HOFMANN_TABLE_SHA256, pds.TOTIS_TABLE_SHA256})
        if not doc["quick"]:
            self.assertEqual(len(doc["rows"]), 757)
        for r in doc["rows"]:
            for k in doc["kernels"]:
                p = r["predictions"][k]
                self.assertEqual(p["included"], p["extentStatus"] == "computed")
        self.assertEqual(doc["absorptivitySensitivity"]["values"], [0.3, 0.4, 0.5, 0.6])


if __name__ == "__main__":
    unittest.main()
