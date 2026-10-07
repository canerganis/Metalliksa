"""Keyhole benchmark report (docs/LPBF_KEYHOLE_BENCHMARK_2026-10-07.*): the committed report is reproducible from the
committed data and pins the headline numbers.

Self-contained and fast: the index-only evaluation (no solver) is recomputed in full and compared with the committed
JSON; the .md and .view.json are regenerated from the committed JSON and compared byte-for-byte; three cases are
re-run through the frozen kernels when the implementation fingerprint matches the report (else skipped, with reason).
"""

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "tools"))

import lpbf_keyhole_benchmark as kb  # noqa: E402
import lpbf_keyhole_literature as kl  # noqa: E402

REPORT = HERE.parent / "docs" / "LPBF_KEYHOLE_BENCHMARK_2026-10-07.json"
INDEX_KEYS = ("appIndex_dHhs", "appRegime", "appPorosityRiskByIndex", "ganKe", "ganEta", "ganRegime",
              "ganKeyholeDepth_um", "huangProduct_betaYe", "huangProduct_betaAppFlat", "hannRegime")


class CommittedReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(REPORT.read_text(encoding="utf-8"))
        cls.idx = kb.evaluate(run_kernels=False)

    def test_schema_and_data_pins(self):
        self.assertEqual(self.doc["schema"], kb.SCHEMA)
        self.assertEqual(self.doc["generatedAt"], "2026-10-07")
        for name, prov in self.doc["datasets"].items():
            self.assertEqual(prov["fileSha256"], kl.LOADERS[name]()["provenance"]["fileSha256"], name)
        self.assertEqual(len(self.doc["cases"]["cunningham"]), 69)
        self.assertEqual(len(self.doc["cases"]["zhaoBoundary"]), 20)
        self.assertEqual(len(self.doc["cases"]["zhaoPores"]), 35)

    def test_index_evaluation_is_reproduced_exactly(self):
        for group in ("cunningham", "zhaoBoundary", "zhaoPores"):
            for a, b in zip(self.doc["cases"][group], self.idx["cases"][group]):
                self.assertEqual(a["rowId"], b["rowId"])
                for k in INDEX_KEYS:
                    self.assertEqual(a[k], b[k], (group, a["rowId"], k))
        for key in ("cunninghamLines", "zhaoPores", "zhaoBoundary", "hannRelationCheck"):
            self.assertEqual(self.doc[key], self.idx[key], key)
        for k in ("appIndex_15_30", "ganKe_1.4_6", "appIndex_keyholeOnly", "hann_HvHs_12.34",
                  "appIndex_15_30_excludingNearBoundary"):
            self.assertEqual(self.doc["confusion"][k], self.idx["confusion"][k], k)
        for name, block in self.idx["depth"].items():
            self.assertEqual(self.doc["depth"][name]["ganEq2"], block["ganEq2"], name)
            self.assertEqual(self.doc["depth"][name]["ganKeScaleToFitEq2"], block["ganKeScaleToFitEq2"], name)

    def test_headline_numbers(self):
        c = self.doc["confusion"]["appIndex_15_30"]
        self.assertEqual(c["rowsAreReported_columnsArePredicted"],
                         {"conduction": {"conduction": 1, "transition": 0, "keyhole": 0},
                          "transition": {"conduction": 1, "transition": 3, "keyhole": 0},
                          "keyhole": {"conduction": 0, "transition": 15, "keyhole": 26}})
        self.assertEqual((c["n"], c["correct"], c["accuracy"]), (46, 30, 0.652))
        f = self.doc["findings"]
        self.assertEqual(f["appIndexAtCunninghamRedLine"], {"n": 9, "min": 17.293, "median": 17.662, "max": 20.005})
        self.assertEqual(f["appIndexAtCunninghamBlueLine"], {"n": 9, "min": 12.962, "median": 13.922, "max": 16.928})
        self.assertEqual(f["appIndexAtZhaoBoundary"], {"n": 20, "min": 15.0, "median": 24.942, "max": 62.424})
        self.assertEqual(f["zhaoPoreCasesAppHigh"], "19/35")
        self.assertTrue(f["keyholeThresholdTooHighForTi64"])
        self.assertFalse(f["singleIndexThresholdFitsZhaoBoundary"])
        self.assertTrue(f["solverIndexEqualsProcessMapIndex"])
        self.assertTrue(f["solverPorosityRiskEqualsIndexBands"])
        self.assertEqual(self.doc["depth"]["cunningham95"]["appFabbro"]["mape_pct"], 44.785)
        self.assertEqual(self.doc["hannRelationCheck"]["withinClaimed10pct"], 3)

    def test_markdown_and_view_are_regenerated_byte_for_byte(self):
        md = REPORT.with_suffix(".md").read_text(encoding="utf-8")
        self.assertEqual(md, kb.to_markdown(self.doc))
        view = json.loads(REPORT.with_name(REPORT.stem + ".view.json").read_text(encoding="utf-8"))
        self.assertEqual(view, json.loads(json.dumps(kb.view(self.doc))))
        self.assertTrue(view["readOnly"])
        self.assertIn("not experimental validation", view["honesty"])

    def test_three_cases_reproduce_through_the_frozen_kernels(self):
        from lpbf_simulation import implementation_fingerprint
        if implementation_fingerprint() != self.doc["implementationHash"]:
            self.skipTest("frozen LPBF implementation changed since the report; regenerate it with "
                          "tools/lpbf_keyhole_benchmark.py (kernel spot-check skipped, index checks still ran)")
        cases = [self.doc["cases"]["cunningham"][0], self.doc["cases"]["cunningham"][-1],
                 self.doc["cases"]["zhaoBoundary"][5]]
        for c in cases:
            got = json.loads(json.dumps(kb.kernel_block(c["power_W"], c["speed_mm_s"], c["beamDiameter_um"],
                                                        c["preheat_C"])))
            self.assertEqual(got, c["kernels"], c["rowId"])


if __name__ == "__main__":
    unittest.main()
