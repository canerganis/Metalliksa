"""tools/lpbf_balling_calibration.py reproduces the committed calibration table from the records."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
sys.path.insert(0, HERE)

import lpbf_balling_calibration as cal  # noqa: E402

DOCS = os.path.join(HERE, "..", "docs")
AFTER = os.path.join(DOCS, "LPBF_DATASET_COMPARISON_2026-10-07_waveb-physics.json")
BEFORE = os.path.join(DOCS, "LPBF_DATASET_COMPARISON_2026-10-06_tier2-physics.json")
TABLE = os.path.join(DOCS, "LPBF_BALLING_CALIBRATION_2026-10-07.md")


@unittest.skipUnless(all(os.path.isfile(p) for p in (AFTER, BEFORE, TABLE)), "records not present")
class CalibrationTool(unittest.TestCase):
    def test_committed_table_is_reproduced(self):
        out = os.path.join(HERE, ".tmp-balling-calibration.md")
        try:
            self.assertEqual(cal.main(["--before", BEFORE, "--record", AFTER, "--out", out]), 0)
            with open(out, encoding="utf-8") as a, open(TABLE, encoding="utf-8") as b:
                self.assertEqual(a.read(), b.read())
        finally:
            if os.path.exists(out):
                os.remove(out)

    def test_threshold_shift_from_wave_b(self):
        import json
        with open(BEFORE, encoding="utf-8") as fh:
            before = cal.analyse(json.load(fh))
        with open(AFTER, encoding="utf-8") as fh:
            after = cal.analyse(json.load(fh))
        rule = lambda r, name: next(t for t in r["rules"] if t["rule"] == name)  # noqa: E731
        # The spec's 5.0 threshold (pre-Wave-B 68 TP / 2 FP) loses precision on the Wave B geometry; 5.5 restores it.
        self.assertEqual((rule(before, "ET L/W > 5")["tp"], rule(before, "ET L/W > 5")["fp"]), (68, 2))
        self.assertEqual((rule(after, "ET L/W > 5")["tp"], rule(after, "ET L/W > 5")["fp"]), (109, 14))
        self.assertEqual((rule(after, "ET L/W > 5.5")["tp"], rule(after, "ET L/W > 5.5")["fp"]), (69, 2))
        self.assertEqual(after["youden"]["threshold"], 4.161)
        self.assertEqual(rule(after, "ET L/W > 5.5")["laneFlagged"], "0/23")


if __name__ == "__main__":
    unittest.main()
