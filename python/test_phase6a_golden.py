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
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "tools"))

import capture_phase6a_golden as golden  # noqa: E402
import drift_report  # noqa: E402
from phase6a_test_support import require_git_revision  # noqa: E402

# (solver, case) -> expected validation error code (exit 2, errorKind "validation").
# Both were silent defaults before the Phase 6a structural migration:
# - tafel alloyId "unobtainium-x" was solved with the AISI 316L preset;
# - pourbaix element "Unobtainium" was drawn with the Fe system (Ni point branch).
EXPECTED_BEHAVIOUR_CHANGES = {
    ("tafel_corrosion_rate_solver", "edge_unknown_alloy_zero_icorr"): "UNKNOWN_ALLOY",
    ("pourbaix_solver", "edge_unknown_element_badvals"): "UNKNOWN_ELEMENT",
}
# ---- BEGIN phase6a-t2b block: kinetics / fatigue unknown alloy (was AISI 4140 / Ti-6Al-4V) ----
EXPECTED_BEHAVIOUR_CHANGES.update(golden._t2b_cases.EXPECTED_BEHAVIOUR_CHANGES)
# ---- END phase6a-t2b block ----


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
            # N2: the stored input is exactly the key-sorted payload (same text, same
            # order), so the regression re-run sends what the sorted payload says.
            self.assertEqual(json.dumps(doc["input"], ensure_ascii=False),
                             json.dumps(golden.CASES[solver][case], sort_keys=True, ensure_ascii=False),
                             f"{solver}/{case}")

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
        # Design step (b): a re-blessed expectation (step_b/<case>.json) replaces the
        # d33b6f5 golden for the comparison; StepBGoldenTest checks its recorded drift.
        expected = golden.load_expected(solver, case)
        # Run the CASES payload, not doc["input"]: golden files store the input with
        # sorted keys, and key order is significant for some solvers (stochastic UQ maps
        # composition elements to Sobol dimensions in insertion order).
        # GoldenFilesTest asserts both are canonically equal.
        fresh = golden.run_solver(solver, golden.CASES[solver][case])
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
            self.assertEqual(set(out), {"success", "error", "errorKind"})
            # The old golden is still the pre-migration record of the silent default.
            self.assertEqual(doc["exitCode"], 0)
            # (the fatigue driver output has no "success" key; it must not be an error)
            self.assertIsNot(doc["stdout"].get("success"), False)
            self.assertNotIn("error", doc["stdout"])
            return
        self.assertEqual(fresh["exitCode"], expected["exitCode"], fresh["stderr"])
        rows = drift_report.diff(expected["stdout"], fresh["stdout"])
        self.assertEqual(rows, [], drift_report.render(f"{solver}/{case}", rows, 20))
        self.assertEqual(golden.canonical(fresh["stdout"]), golden.canonical(expected["stdout"]))

    def test_tafel_corrosion_rate_solver(self):
        for case in golden.CASES["tafel_corrosion_rate_solver"]:
            with self.subTest(case=case):
                self._check("tafel_corrosion_rate_solver", case)

    def test_pourbaix_solver(self):
        for case in golden.CASES["pourbaix_solver"]:
            with self.subTest(case=case):
                self._check("pourbaix_solver", case)


def _git_available() -> bool:
    try:
        golden.solver_bytes("pourbaix_solver", golden.BASE_REVISION)
        return True
    except Exception:
        return False


@require_git_revision(_git_available(), f"git or revision {golden.BASE_REVISION} unavailable")
class GoldenBindingTest(unittest.TestCase):
    """Golden files are bound to the immutable solver blobs they were captured from."""

    def _blob_sha(self, solver):
        return golden.normalised_sha256(golden.solver_bytes(solver, golden.BASE_REVISION))

    def test_every_golden_records_the_base_blob_sha256(self):
        for solver, case in golden.iter_golden_cases():
            doc = golden.load_golden(solver, case)
            self.assertEqual(doc["solverSha256"], self._blob_sha(solver), f"{solver}/{case}")
            self.assertEqual(doc["solverFile"], f"python/{solver}.py")
            self.assertIn(doc["solverSource"], {f"git:{golden.BASE_REVISION}", "worktree"})
        for solver in golden._TABLE_TARGETS:
            path = golden.GOLDEN_DIR / solver / golden.SOURCE_TABLES_FILE
            doc = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(doc["solverSha256"], self._blob_sha(solver), solver)

    def test_normalised_sha256_ignores_only_crlf(self):
        self.assertEqual(golden.normalised_sha256(b"a\r\nb\n"), golden.normalised_sha256(b"a\nb\n"))
        self.assertNotEqual(golden.normalised_sha256(b"a\nb\n"), golden.normalised_sha256(b"a\nc\n"))

    def _in_temp_golden_dir(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        original = golden.GOLDEN_DIR
        golden.GOLDEN_DIR = Path(tmp.name)
        self.addCleanup(setattr, golden, "GOLDEN_DIR", original)
        return Path(tmp.name)

    def test_force_capture_of_changed_solver_is_refused(self):
        # The migrated working-tree solvers differ from the d33b6f5 blobs.
        tmp = self._in_temp_golden_dir()
        for solver in golden.CASES:
            self.assertNotEqual(golden.normalised_sha256(golden.solver_bytes(solver)), self._blob_sha(solver))
            case = next(iter(golden.CASES[solver]))
            with self.assertRaises(golden.CaptureRefused):
                golden.capture(solver, case, force=True)
        with self.assertRaises(golden.CaptureRefused):
            golden.capture_source_tables(force=True)
        self.assertEqual(list(tmp.rglob("*.json")), [])

    def test_capture_from_base_blob_reproduces_committed_golden(self):
        committed = {(s, c): golden.load_golden(s, c) for s, c in golden.iter_golden_cases()}
        tmp = self._in_temp_golden_dir()
        for solver, case in golden.iter_golden_cases():
            golden.capture(solver, case, force=True, from_revision=golden.BASE_REVISION)
            fresh = json.loads((tmp / solver / f"{case}.json").read_text(encoding="utf-8"))
            old = committed[(solver, case)]
            self.assertEqual(fresh["exitCode"], old["exitCode"], f"{solver}/{case}")
            self.assertEqual(golden.canonical(fresh["stdout"]), golden.canonical(old["stdout"]), f"{solver}/{case}")
            self.assertEqual(fresh["solverSha256"], old["solverSha256"])
        golden.capture_source_tables(force=True, from_revision=golden.BASE_REVISION)
        for solver in golden._TABLE_TARGETS:
            fresh = json.loads((tmp / solver / golden.SOURCE_TABLES_FILE).read_text(encoding="utf-8"))
            old = json.loads((HERE / "golden" / "phase6a" / solver / golden.SOURCE_TABLES_FILE).read_text(encoding="utf-8"))
            self.assertEqual(golden.canonical(fresh["values"]), golden.canonical(old["values"]), solver)

    def test_from_revision_other_than_base_is_refused(self):
        self._in_temp_golden_dir()
        with self.assertRaises(golden.CaptureRefused):
            golden.capture("pourbaix_solver", "cu_nochloride", force=True, from_revision="HEAD")


class StepBGoldenTest(unittest.TestCase):
    """Re-blessed expectations of design step (b) carry their full drift against d33b6f5."""

    def _step_b_files(self):
        return sorted(golden.GOLDEN_DIR.glob(f"*/{golden.STEP_B_DIR}/*.json"))

    def test_every_step_b_file_belongs_to_a_known_case(self):
        for path in self._step_b_files():
            solver, case = path.parent.parent.name, path.stem
            with self.subTest(file=f"{solver}/{case}"):
                self.assertIn(solver, golden.CASES)
                self.assertIn(case, golden.CASES[solver])
                # A validation-envelope case is a behaviour change, never a re-bless.
                self.assertNotIn((solver, case), EXPECTED_BEHAVIOUR_CHANGES)
                self.assertNotIn((solver, case), golden._t2a_cases.EXPECTED_BEHAVIOUR_CHANGES)

    def test_step_b_metadata_and_recorded_drift(self):
        for path in self._step_b_files():
            solver, case = path.parent.parent.name, path.stem
            with self.subTest(file=f"{solver}/{case}"):
                doc = json.loads(path.read_text(encoding="utf-8"))
                base = golden.load_golden(solver, case)
                self.assertEqual(doc["schema"], golden.STEP_B_SCHEMA)
                self.assertEqual(doc["label"], golden.STEP_B_LABEL)
                self.assertEqual((doc["solver"], doc["case"]), (solver, case))
                self.assertEqual(doc["solverFile"], f"python/{solver}.py")
                self.assertEqual(len(doc["solverSha256"]), 64)
                self.assertEqual(golden.canonical(doc["input"]), golden.canonical(golden.CASES[solver][case]))
                self.assertEqual(doc["exitCode"], base["exitCode"])
                rows = drift_report.diff(base["stdout"], doc["stdout"])
                # A re-bless exists only for a real drift, and the recorded table is complete.
                self.assertTrue(rows)
                self.assertEqual(golden.canonical(doc["driftVsBase"]), golden.canonical(rows))
                self.assertTrue(text_ends_with_newline(path))

    def test_load_expected_prefers_step_b(self):
        for path in self._step_b_files():
            solver, case = path.parent.parent.name, path.stem
            self.assertEqual(golden.load_expected(solver, case)["label"], golden.STEP_B_LABEL)
        solver, case = "pourbaix_solver", "cu_nochloride"
        if not golden.step_b_path(solver, case).exists():
            self.assertEqual(golden.load_expected(solver, case), golden.load_golden(solver, case))

    def test_bless_dry_run_reports_no_drift_for_the_committed_state(self):
        import bless_step_b
        before = sorted(p.as_posix() for p in golden.GOLDEN_DIR.rglob("*.json"))
        drift, log = bless_step_b.bless("pourbaix_solver", dry_run=True)
        self.assertEqual([rows for _, rows in drift if rows], [])
        self.assertTrue(any("validation envelope" in line for line in log))
        self.assertEqual(sorted(p.as_posix() for p in golden.GOLDEN_DIR.rglob("*.json")), before)


def text_ends_with_newline(path: Path) -> bool:
    return path.read_text(encoding="utf-8").endswith("\n")


class ProvenanceTest(unittest.TestCase):
    """Provenance is stripped from the bit-exact comparison, so pin it here."""

    def _fresh(self, solver, case):
        return golden.run_solver(solver, golden.CASES[solver][case])

    def test_tafel_provenance(self):
        import alloy_registry
        import physical_constants as pc
        expected_ids = {
            "solve_316l_default_fields": "ss316l",
            "solve_1018_custom_composition": "steel1018",
            "fit_curve_synthetic_bv": "al6061",
            # every preset-derived field was supplied: the alloy is never resolved
            "solve_unknown_alloy_full_overrides": None,
        }
        for case, registry_id in expected_ids.items():
            with self.subTest(case=case):
                prov = self._fresh("tafel_corrosion_rate_solver", case)["provenance"]["provenance"]
                self.assertEqual(prov["registryVersion"], alloy_registry.REGISTRY_VERSION)
                self.assertEqual(prov["constantsVersion"], pc.CONSTANTS_VERSION)
                self.assertEqual(prov["registryAlloyId"], registry_id)
                self.assertEqual(prov["gasConstantR_J_molK"], pc.TRUNCATED_GAS_CONSTANT_R)
                self.assertEqual(prov["faraday_C_mol"], pc.TRUNCATED_FARADAY)

    def test_pourbaix_provenance(self):
        import physical_constants as pc
        prov = self._fresh("pourbaix_solver", "fe_chloride_points")["provenance"]["provenance"]
        self.assertEqual(prov["constantsVersion"], pc.CONSTANTS_VERSION)
        self.assertEqual(prov["gasConstantR_J_molK"], pc.TRUNCATED_GAS_CONSTANT_R)
        self.assertEqual(prov["faraday_C_mol"], pc.TRUNCATED_FARADAY)

    def test_validation_envelope_has_no_provenance(self):
        for solver, case in EXPECTED_BEHAVIOUR_CHANGES:
            self.assertIsNone(self._fresh(solver, case)["provenance"])


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

    def test_empty_containers_are_kept(self):
        rows = {r["key"]: r["kind"] for r in drift_report.diff({"a": {}, "b": []}, {"c": {}})}
        self.assertEqual(rows, {"a": "removed", "b": "removed", "c": "added"})
        self.assertEqual(drift_report.diff({"a": {}}, {"a": {}}), [])
        rows = drift_report.diff({"a": {}}, {"a": {"x": 1}})
        self.assertEqual({r["key"] for r in rows}, {"a", "a.x"})

    def test_zero_old_value_has_no_relative_delta(self):
        rows = drift_report.diff({"x": 0.0}, {"x": 1e-9})
        self.assertIsNone(rows[0]["rel"])

    def test_strip_volatile_is_recursive(self):
        doc = {"durationMs": 1, "a": {"timestamp": "t", "b": [{"computeTimeMs": 2, "c": 3}]},
               "pythonVersion": "3.12"}
        self.assertEqual(golden.strip_volatile(doc), {"a": {"b": [{"c": 3}]}})


if __name__ == "__main__":
    unittest.main()
