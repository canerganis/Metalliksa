"""Phase 6a golden regression: migrated solvers must stay bit-exact.

Every case in python/golden/phase6a/<solver>/<case>.json was captured at the
pre-migration revision (tools/capture_phase6a_golden.py). The current solver is
run exactly like the app's ad-hoc spawn path and its stdout, with only the
volatile keys stripped, must serialise to the identical canonical JSON text.

Deliberate behaviour changes (silent default -> validation error) are listed in
EXPECTED_BEHAVIOUR_CHANGES; for those cases the old golden stays on disk as the
record of the old behaviour and the test asserts the new validation envelope.
"""

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "tools"))

import capture_phase6a_golden as golden  # noqa: E402
import drift_report  # noqa: E402

# (solver, case) -> expected validation error code (exit 2, errorKind "validation").
EXPECTED_BEHAVIOUR_CHANGES = {}


class GoldenFilesTest(unittest.TestCase):
    def test_every_case_has_a_golden_file(self):
        for solver, case in golden.iter_golden_cases():
            path = golden.golden_path(solver, case)
            self.assertTrue(path.is_file(), str(path))
            doc = golden.load_golden(solver, case)
            self.assertEqual(doc["schema"], golden.GOLDEN_SCHEMA)
            self.assertEqual(doc["solver"], solver)
            self.assertEqual(doc["case"], case)
            self.assertEqual(doc["baseRevision"], golden.BASE_REVISION)
            self.assertEqual(golden.canonical(doc["input"]), golden.canonical(golden.CASES[solver][case]))

    def test_case_counts(self):
        for solver, cases in golden.CASES.items():
            self.assertGreaterEqual(len(cases), 3, solver)
            self.assertLessEqual(len(cases), 5, solver)

    def test_golden_files_hold_no_volatile_keys(self):
        for solver, case in golden.iter_golden_cases():
            text = golden.golden_path(solver, case).read_text(encoding="utf-8")
            stdout = json.dumps(golden.load_golden(solver, case)["stdout"])
            for key in golden.VOLATILE_KEYS:
                self.assertNotIn(f'"{key}"', stdout, f"{solver}/{case}: {key}")
            self.assertTrue(text.endswith("\n"))


class GoldenRegressionTest(unittest.TestCase):
    maxDiff = None

    def _check(self, solver: str, case: str):
        doc = golden.load_golden(solver, case)
        fresh = golden.run_solver(solver, doc["input"])
        expected_code = EXPECTED_BEHAVIOUR_CHANGES.get((solver, case))
        if expected_code is not None:
            self.assertEqual(fresh["exitCode"], 2, fresh["stderr"])
            out = fresh["stdout"]
            self.assertIs(out.get("success"), False)
            self.assertEqual(out.get("errorKind"), "validation")
            self.assertEqual(out["error"]["code"], expected_code)
            self.assertTrue(out["error"]["field"])
            self.assertTrue(out["error"]["message"])
            self.assertIsInstance(out["error"]["detail"], dict)
            return
        self.assertEqual(fresh["exitCode"], doc["exitCode"], fresh["stderr"])
        rows = drift_report.diff(doc["stdout"], fresh["stdout"])
        self.assertEqual(rows, [], drift_report.render(f"{solver}/{case}", rows, 20))
        self.assertEqual(golden.canonical(fresh["stdout"]), golden.canonical(doc["stdout"]))

    def test_tafel_corrosion_rate_solver(self):
        for case in golden.CASES["tafel_corrosion_rate_solver"]:
            with self.subTest(case=case):
                self._check("tafel_corrosion_rate_solver", case)

    def test_pourbaix_solver(self):
        for case in golden.CASES["pourbaix_solver"]:
            with self.subTest(case=case):
                self._check("pourbaix_solver", case)


class DriftReportTest(unittest.TestCase):
    def test_identical_documents_have_no_rows(self):
        doc = {"a": 1.5, "b": [1, {"c": "x"}], "d": None}
        self.assertEqual(drift_report.diff(doc, json.loads(json.dumps(doc))), [])

    def test_numeric_row_has_abs_and_rel(self):
        rows = drift_report.diff({"x": {"y": 2.0}}, {"x": {"y": 2.5}})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["key"], "x.y")
        self.assertEqual(rows[0]["kind"], "numeric")
        self.assertEqual(rows[0]["abs"], 0.5)
        self.assertEqual(rows[0]["rel"], 0.25)

    def test_type_change_is_detected_even_when_equal(self):
        rows = drift_report.diff({"x": 1}, {"x": 1.0})
        self.assertEqual(len(rows), 1)

    def test_added_removed_changed(self):
        rows = {r["key"]: r["kind"] for r in drift_report.diff(
            {"a": 1, "b": "s", "l": [1, 2]}, {"b": "t", "c": 3, "l": [1]})}
        self.assertEqual(rows, {"a": "removed", "b": "changed", "c": "added", "l[1]": "removed"})

    def test_zero_old_value_has_no_relative_delta(self):
        rows = drift_report.diff({"x": 0.0}, {"x": 1e-9})
        self.assertIsNone(rows[0]["rel"])

    def test_strip_volatile_is_recursive(self):
        doc = {"durationMs": 1, "a": {"timestamp": "t", "b": [{"computeTimeMs": 2, "c": 3}]},
               "pythonVersion": "3.12"}
        self.assertEqual(golden.strip_volatile(doc), {"a": {"b": [{"c": 3}]}})


if __name__ == "__main__":
    unittest.main()
