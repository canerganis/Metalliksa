"""tools/lpbf_dataset_common_subset.py: only rows computed in BOTH records enter the comparison."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))

import lpbf_dataset_common_subset as cs  # noqa: E402


def _row(dataset, row_id, w, d, status="computed", mw=100.0, md=50.0):
    return {"dataset": dataset, "rowId": row_id, "measured": {"width_um": mw, "depth_um": md},
            "predictions": {k: {"width_um": w, "depth_um": d, "extentStatus": status} for k in cs.KERNELS}}


def _doc(rows, h):
    return {"implementationHash": h, "generatedAt": "2026-10-07", "summaryScope": {"datasets": ["a"]}, "rows": rows}


class CommonSubset(unittest.TestCase):
    def test_rows_must_be_computed_in_both_records(self):
        before = _doc([_row("a", 1, 110, 60), _row("a", 2, 90, 40), _row("b", 3, 100, 50, status="width-floor-applied")], "x" * 64)
        after = _doc([_row("a", 1, 120, 70), _row("a", 2, 90, 40, status="heuristic-width-fallback"), _row("b", 3, 100, 50)], "y" * 64)
        doc = cs.compare(before, after)
        groups = doc["kernels"]["rosenthal"]["groups"]
        self.assertEqual(set(groups), {"a", "all-datasets", "pooled-summary-scope"})
        self.assertEqual(groups["all-datasets"]["n"], 1)  # only row 1 is computed in both
        self.assertEqual(groups["a"]["width"], {"before": {"mape_pct": 10.0, "bias_pct": 10.0},
                                                "after": {"mape_pct": 20.0, "bias_pct": 20.0}})
        self.assertEqual(groups["a"]["depth"]["after"]["mape_pct"], 40.0)
        self.assertEqual(doc["kernels"]["goldak"]["computedRowsInSummaryScope"], {"before": 2, "after": 1})
        self.assertIs(doc["honesty"]["experimentalValidation"], False)
        self.assertIn("| rosenthal | a | 1 | 10.0 -> 20.0 |", cs.render_markdown(doc))


if __name__ == "__main__":
    unittest.main()
