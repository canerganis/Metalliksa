"""Tests for tools/lpbf_nist_2525_absorptance_comparison.py.

Run from python/:  python -B test_lpbf_nist_2525_absorptance_comparison.py
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PYTHON_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PYTHON_DIR))
sys.path.insert(0, str(PYTHON_DIR / "tools"))

import lpbf_nist_2525_absorptance_comparison as tool  # noqa: E402

REQUIRED_TOP = {"schema", "generatedAt", "implementationFingerprint", "honesty", "dataset", "experiment", "measured",
                "measuredOnly", "models", "comparison", "labels", "limits", "checks"}


class ComparisonToolTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="nist2525-")
        cls.out = Path(cls.tmp) / "cmp.json"
        tool.main(["--quick", "--out", str(cls.out)])
        cls.doc = json.loads(cls.out.read_text(encoding="utf-8"))
        cls.rows = {r["id"]: r for r in cls.doc["comparison"]["rows"]}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_a_hash_gate_refuses_tampered_byte(self):
        root = Path(tempfile.mkdtemp(prefix="nist2525-tamper-"))
        try:
            for name in tool.PINNED:
                shutil.copy2(tool.SOURCE_DIR / name, root / name)
            tool.verify_inputs(root)  # untouched copy passes
            target = root / tool.AL_SPOT_AA
            data = bytearray(target.read_bytes())
            data[-2] ^= 0x01
            target.write_bytes(bytes(data))
            with self.assertRaises(ValueError):
                tool.verify_inputs(root)
            with self.assertRaises(ValueError):
                tool.build_document(True, "x", root)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_b_quick_record_shape_and_labels(self):
        self.assertTrue(REQUIRED_TOP <= set(self.doc))
        self.assertEqual(self.doc["schema"], "lpbf-nist-2525-absorptance-comparison-1")
        for r in self.doc["comparison"]["rows"]:
            self.assertIn(r["status"], tool.ALLOWED_STATUS)
            if r["status"] == "unavailable":
                self.assertTrue(r["reason"])
        self.assertEqual(self.doc["labels"], tool.LABELS)
        self.assertIs(self.doc["labels"]["nistResidual"], None)
        self.assertIs(self.doc["labels"]["experimentalValidation"], False)
        self.assertIs(self.doc["checks"]["inputHashesVerified"], True)
        self.assertIs(self.doc["checks"]["fingerprintCheckPassed"], True)
        self.assertNotIn("ray_paths", json.dumps(self.doc))
        md = self.out.with_suffix(".md").read_bytes()
        self.assertNotIn(b"\r", md)
        self.assertNotIn(b"\r", self.out.read_bytes())

    def test_c_flat_plate_difference(self):
        row = self.rows["ti64-spot-pre-keyhole-flat-plate"]
        self.assertEqual(row["status"], "compared")
        self.assertAlmostEqual(row["difference"], row["model"] - row["measured"], delta=1e-4)
        flat = self.doc["models"]["flatPlateAbsorptivity"]
        self.assertAlmostEqual(flat["difference_pp"], 100.0 * flat["value_fraction"] - flat["comparedWith"]["measuredMean_pct"], delta=1e-4)

    def test_d_depth_zero_matches_base(self):
        rt = self.doc["models"]["keyholeRayTracing"]
        self.assertEqual(rt["status"], "success")
        self.assertEqual(rt["sweep"][0]["keyhole_depth_um"], 0.0)
        self.assertLess(abs(rt["sweep"][0]["absorbed_fraction"] - rt["params"]["base_absorption"]), 0.02)
        self.assertEqual(len(rt["sweep"]), len(tool.DEPTHS_UM))

    def test_e_aluminium_rows_unavailable(self):
        al = [r for r in self.doc["comparison"]["rows"] if r["id"].startswith("al-")]
        self.assertGreaterEqual(len(al), 7)
        for r in al:
            self.assertEqual(r["status"], "unavailable")
            self.assertIn("SRM 1241c", r["reason"])
            self.assertIn("SRM 1241c", r["material"])
        self.assertIn("SRM 1241c", self.doc["measuredOnly"]["material"])

    def test_f_ti64_scan_unavailable_when_absent(self):
        if (tool.SOURCE_DIR / tool.SCAN_NAME).is_file():
            self.skipTest("scan CSV is present; branch exercised instead")
        row = self.rows["ti64-scan-before-during-keyhole"]
        self.assertEqual(row["status"], "unavailable")
        self.assertIn("not acquired", row["reason"])
        self.assertEqual(self.doc["models"]["thermalSolverEtaEff"]["ti64Scan"]["status"], "unavailable")
        self.assertEqual(self.doc["models"]["thermalSolverEtaEff"]["ti64Spot"]["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
