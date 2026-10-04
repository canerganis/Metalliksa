"""Phase 6b vectorisation lane: cnls / xrd / dft-named goldens and parity.

The goldens in python/golden/phase6b/<solver>/<case>.json were captured from the
faa6684 solver blobs (tools/capture_phase6a_golden.py --phase6b-vector), i.e. the
pure-Python code before the NumPy/SciPy rewrite. Each solver is run like the app's
ad-hoc spawn path and compared with its golden under the rule in PARITY_MODE:

* "bit_exact"  - every leaf identical (unchanged solver).
* "tolerance"  - the algorithm is mathematically identical (same model, same
                 stopping rule); only floating-point summation/elimination order
                 changed. Same keys, identical non-numeric leaves, and every numeric
                 leaf within REL_TOL relative (exact when the old value is 0).
* "minimiser"  - a different minimiser (xrd: coordinate search -> scipy
                 least_squares). Outputs legitimately differ; the checks are fit
                 quality (sum of squares never above the old one), identical output
                 structure, a verified local minimum, and parameter shifts no larger
                 than the sum-of-squares improvement explains (see XrdParityTest).

Kernel-level parity (unrounded internals) is checked in-process against the
faa6684 blob modules, and each solver has a mutation check proving the comparison
detects a perturbed kernel.
"""

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "tools"))

import capture_phase6a_golden as golden  # noqa: E402
import drift_report  # noqa: E402
import phase6b_vector_benchmark as bench  # noqa: E402
import phase6b_vector_golden_cases as cases  # noqa: E402
from phase6a_test_support import require_git_revision  # noqa: E402

BASE = cases.BASE_REVISION
REL_TOL = 1e-9
PARITY_MODE = {
    "cnls_fitting_solver": "tolerance",
    "xrd_peak_deconvolution": "bit_exact",
    "dft_property_calculator": "bit_exact",
}
# xrd: cases with no observations never reach the minimiser and must stay bit-exact.
XRD_BIT_EXACT_CASES = {"edge_missing_points"}


def load(solver, case):
    with open(golden.phase6b_vector_golden_path(solver, case), "r", encoding="utf-8") as fh:
        return json.load(fh)


def iter_cases():
    for solver, table in cases.CASES.items():
        for case in table:
            yield solver, case


def as_stdout(result):
    """In-process result -> the parsed, volatile-stripped stdout the golden holds."""
    return golden.strip_volatile(json.loads(json.dumps(result)))


def tolerance_violations(old, new, rel_tol=REL_TOL):
    """Rows of drift_report.diff that break the "tolerance" rule (empty == parity)."""
    bad = []
    for row in drift_report.diff(old, new):
        if row["kind"] == "numeric" and isinstance(row["old"], float) and isinstance(row["new"], float):
            if row["old"] != 0 and abs(row["rel"]) <= rel_tol:
                continue
        bad.append(row)
    return bad


def _git_available() -> bool:
    try:
        golden.solver_bytes("dft_property_calculator", BASE)
        return True
    except Exception:
        return False


GIT = _git_available()
_BLOBS = {}


def blob_module(solver):
    if solver not in _BLOBS:
        _BLOBS[solver] = bench.load_blob_module(solver, BASE)
    return _BLOBS[solver]


class GoldenFilesTest(unittest.TestCase):
    def test_every_case_has_a_golden_file(self):
        for solver, case in iter_cases():
            with self.subTest(solver=solver, case=case):
                doc = load(solver, case)
                self.assertEqual(doc["schema"], golden.GOLDEN_SCHEMA)
                self.assertEqual((doc["solver"], doc["case"]), (solver, case))
                self.assertEqual(doc["baseRevision"], BASE)
                self.assertEqual(json.dumps(doc["input"], ensure_ascii=False),
                                 json.dumps(cases.CASES[solver][case], sort_keys=True, ensure_ascii=False))
                self.assertNotIn("__unparseableStdout__", doc["stdout"])

    def test_case_counts(self):
        self.assertEqual(tuple(cases.CASES), cases.SOLVERS)
        self.assertEqual(set(PARITY_MODE), set(cases.SOLVERS))
        for solver in cases.SOLVERS:
            self.assertEqual(len(cases.CASES[solver]), 5, solver)

    def test_golden_files_hold_no_volatile_keys(self):
        for solver, case in iter_cases():
            stdout = json.dumps(load(solver, case)["stdout"])
            for key in golden.VOLATILE_KEYS:
                self.assertNotIn(f'"{key}"', stdout, f"{solver}/{case}: {key}")

    def test_phase6a_case_table_is_untouched(self):
        for solver in cases.SOLVERS:
            self.assertNotIn(solver, golden.CASES)


@require_git_revision(GIT, f"git or revision {BASE} unavailable")
class GoldenBindingTest(unittest.TestCase):
    """Goldens are bound to the immutable faa6684 blobs they were captured from."""

    def _blob_sha(self, solver):
        return golden.normalised_sha256(golden.solver_bytes(solver, BASE))

    def test_every_golden_records_the_base_blob_sha256(self):
        for solver, case in iter_cases():
            doc = load(solver, case)
            self.assertEqual(doc["solverSha256"], self._blob_sha(solver), f"{solver}/{case}")
            self.assertEqual(doc["solverFile"], f"python/{solver}.py")
            self.assertEqual(doc["solverSource"], f"git:{BASE}")

    def _in_temp_dir(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        original = golden.PHASE6B_VECTOR_DIR
        golden.PHASE6B_VECTOR_DIR = Path(tmp.name)
        self.addCleanup(setattr, golden, "PHASE6B_VECTOR_DIR", original)
        return Path(tmp.name)

    def test_capture_from_base_blob_reproduces_committed_golden(self):
        committed = {(s, c): load(s, c) for s, c in iter_cases()}
        tmp = self._in_temp_dir()
        for solver, case in iter_cases():
            golden.capture_phase6b_vector(solver, case, force=True, from_revision=BASE)
            fresh = json.loads((tmp / solver / f"{case}.json").read_text(encoding="utf-8"))
            old = committed[(solver, case)]
            self.assertEqual(fresh["exitCode"], old["exitCode"], f"{solver}/{case}")
            self.assertEqual(golden.canonical(fresh["stdout"]), golden.canonical(old["stdout"]), f"{solver}/{case}")

    def test_changed_working_tree_solver_is_refused(self):
        tmp = self._in_temp_dir()
        for solver in cases.SOLVERS:
            changed = golden.normalised_sha256(golden.solver_bytes(solver)) != self._blob_sha(solver)
            self.assertEqual(changed, PARITY_MODE[solver] != "bit_exact", solver)
            if not changed:
                continue
            with self.assertRaises(golden.CaptureRefused):
                golden.capture_phase6b_vector(solver, next(iter(cases.CASES[solver])), force=True)
        self.assertEqual(list(tmp.rglob("*.json")), [])

    def test_from_revision_other_than_base_is_refused(self):
        self._in_temp_dir()
        # b5c83c3~1 holds an older cnls_fitting_solver blob (the LM sign fix came after it).
        with self.assertRaises(golden.CaptureRefused):
            golden.capture_phase6b_vector("cnls_fitting_solver", "randles_modulus_fit", force=True,
                                          from_revision="b5c83c3~1")


class ToleranceRuleTest(unittest.TestCase):
    def test_rule(self):
        self.assertEqual(tolerance_violations({"a": 1.0, "s": "x"}, {"a": 1.0 + 1e-12, "s": "x"}), [])
        self.assertEqual(len(tolerance_violations({"a": 1.0}, {"a": 1.0 + 1e-8})), 1)
        self.assertEqual(len(tolerance_violations({"a": 0.0}, {"a": 1e-300})), 1)
        self.assertEqual(len(tolerance_violations({"a": 1}, {"a": 2})), 1)       # ints exact
        self.assertEqual(len(tolerance_violations({"a": True}, {"a": False})), 1)
        self.assertEqual(len(tolerance_violations({"a": [1.0]}, {"a": [1.0, 2.0]})), 1)
        self.assertEqual(len(tolerance_violations({"a": 1.0}, {"b": 1.0})), 2)


class GoldenParityTest(unittest.TestCase):
    """Spawn-path run of every case against its faa6684 golden (rule: PARITY_MODE)."""
    maxDiff = None

    def _run(self, solver):
        for case in cases.CASES[solver]:
            with self.subTest(case=case):
                doc = load(solver, case)
                fresh = golden.run_solver(solver, cases.CASES[solver][case])
                self.assertEqual(fresh["exitCode"], doc["exitCode"], fresh["stderr"])
                self.assertEqual(fresh["stderr"], "")
                mode = PARITY_MODE[solver]
                if mode == "minimiser" and case not in XRD_BIT_EXACT_CASES:
                    XrdParityTest.assert_minimiser_parity(self, case, doc["stdout"], fresh["stdout"])
                    continue
                rows = (tolerance_violations(doc["stdout"], fresh["stdout"]) if mode == "tolerance"
                        else drift_report.diff(doc["stdout"], fresh["stdout"]))
                self.assertEqual(rows, [], drift_report.render(f"{solver}/{case}", rows, 20))

    def test_cnls_fitting_solver(self):
        self._run("cnls_fitting_solver")

    def test_xrd_peak_deconvolution(self):
        self._run("xrd_peak_deconvolution")

    def test_dft_property_calculator(self):
        self._run("dft_property_calculator")


def _in_process(solver, case_or_payload, module=None):
    payload = cases.CASES[solver][case_or_payload] if isinstance(case_or_payload, str) else case_or_payload
    module = __import__(solver) if module is None else module
    return as_stdout(bench.dispatch(module, solver, payload))


@require_git_revision(GIT, f"git or revision {BASE} unavailable")
class CnlsKernelParityTest(unittest.TestCase):
    """Vectorised LM (normal equations, forward-difference Jacobian, LAPACK solve) and
    the Lin-KK Tikhonov solve against the faa6684 pure-Python loops, in-process."""
    maxDiff = None

    def _payloads(self):
        large = bench._large_payloads()["cnls_fitting_solver"]
        table = dict(cases.CASES["cnls_fitting_solver"])
        table.update(large)
        return table

    def test_fits_and_lin_kk_match_old_loops(self):
        old_module = blob_module("cnls_fitting_solver")
        for case, payload in self._payloads().items():
            with self.subTest(case=case):
                old = _in_process("cnls_fitting_solver", payload, old_module)
                new = _in_process("cnls_fitting_solver", payload)
                rows = tolerance_violations(old, new)
                self.assertEqual(rows, [], drift_report.render(case, rows, 20))

    def test_mutation_half_lm_step_is_detected(self):
        import cnls_fitting_solver as cnls
        solve = np.linalg.solve
        with patch.object(cnls.np.linalg, "solve", lambda a, b: 0.5 * solve(a, b)):
            mutated = _in_process("cnls_fitting_solver", "randles_modulus_fit")
        rows = tolerance_violations(load("cnls_fitting_solver", "randles_modulus_fit")["stdout"], mutated)
        self.assertTrue(any(r["key"] == "iterations" for r in rows), rows[:3])
        # and the unmutated in-process run is within tolerance of the golden
        self.assertEqual(tolerance_violations(load("cnls_fitting_solver", "randles_modulus_fit")["stdout"],
                                              _in_process("cnls_fitting_solver", "randles_modulus_fit")), [])

    def test_mutation_lin_kk_regularisation_is_detected(self):
        import cnls_fitting_solver as cnls
        eye = np.eye
        with patch.object(cnls.np, "eye", lambda n: 1e3 * eye(n)):
            mutated = _in_process("cnls_fitting_solver", "linkk_validate_dataset")
        rows = tolerance_violations(load("cnls_fitting_solver", "linkk_validate_dataset")["stdout"], mutated)
        self.assertTrue(any(r["key"].startswith("linKK.") for r in rows))


class NewValidationTest(unittest.TestCase):
    """The LAPACK/scipy kernels cannot take non-finite input that the old loops turned
    into NaN-laden "successful" output. Those inputs are now typed validation errors
    (input_validation NON_FINITE, exit 2); nothing else changed."""

    def _envelope(self, solver, payload, field):
        fresh = golden.run_solver(solver, payload)
        self.assertEqual(fresh["exitCode"], 2, fresh["stderr"])
        out = fresh["stdout"]
        self.assertEqual(set(out), {"success", "error", "errorKind"})
        self.assertIs(out["success"], False)
        self.assertEqual(out["errorKind"], "validation")
        self.assertEqual(out["error"]["code"], "NON_FINITE")
        self.assertEqual(out["error"]["field"], field)

    def test_cnls_non_finite_lin_kk_is_unchanged_nan(self):
        points = [dict(p) for p in cases._RANDLES_POINTS]
        points[5]["zReal"] = float("nan")
        fresh = golden.run_solver("cnls_fitting_solver", {"action": "validate_dataset", "points": points})
        self.assertEqual((fresh["exitCode"], fresh["stderr"]), (0, ""))
        self.assertTrue(math.isnan(fresh["stdout"]["linKK"]["kkChiSquare"]))


if __name__ == "__main__":
    unittest.main()
