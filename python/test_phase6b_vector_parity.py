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
    "xrd_peak_deconvolution": "minimiser",
    "dft_property_calculator": "tolerance",
}
# xrd: cases with no observations never reach the minimiser and must stay bit-exact.
# Deliberate behaviour changes (review fix round): goldens whose faa6684 "success"
# is now a validation envelope -> (code, field). The empty ROI returned the guess
# with SSE 0.0 and success true; a 6-parameter fit needs >= 7 points.
VALIDATION_CHANGES = {("xrd_peak_deconvolution", "edge_missing_points"): ("OUT_OF_RANGE", "points")}
# The only differences the minimiser rule tolerates besides numbers: the engine
# string (version bump) and the additive fitDiagnostics block with exactly these keys.
XRD_ENGINE_OLD, XRD_ENGINE_NEW = "MetalliX-Python-HPC-XRD-v3.10", "MetalliX-Python-HPC-XRD-v4.1"
# v4.1 adds the honest goodness-of-fit reporting keys (r_wp_pct is no longer clipped at 15 %).
XRD_DIAGNOSTIC_KEYS = {"minimiser", "start", "status", "message", "nfev", "dof", "accepted",
                       "rWpDefinition", "rWpPoorFitThresholdPct", "poorFit"}


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


def _display_unit(value):
    """10**-d when ``value`` was evidently rounded for display (repr has d <= 6
    fractional digits, no exponent), else None."""
    text = repr(value)
    if "e" in text or "E" in text or "." not in text:
        return None
    digits = len(text.split(".")[1])
    return 10.0 ** -digits if digits <= 6 else None


# Documented change (cnls_fitting_solver, fx-xrd lane): the faa6684 "Hirschorn" capacitance
# was algebraically identical to the Hsu-Mansfeld one, so cHirschorn_F / cHirschorn_uF are
# removed. A removal is tolerated ONLY for these two leaves, and only when the old golden
# value equals its sibling Hsu-Mansfeld value to 1e-12 relative (the duplicate claim holds on
# the data).
HIRSCHORN_REMOVED_LEAVES = {"cHirschorn_F": "cHsuMansfeld_F", "cHirschorn_uF": "cHsuMansfeld_uF"}


def _is_documented_hirschorn_removal(row, old_flat):
    leaf = row["key"].rsplit(".", 1)[-1]
    sibling = HIRSCHORN_REMOVED_LEAVES.get(leaf)
    if sibling is None:
        return False
    sibling_key = row["key"][: -len(leaf)] + sibling
    # the two formulas are algebraically equal but not bit-identical in floating point
    return (sibling_key in old_flat and isinstance(row["old"], float)
            and abs(old_flat[sibling_key] - row["old"]) <= 1e-12 * abs(row["old"]))


def tolerance_violations(old, new, rel_tol=REL_TOL, display_unit=False):
    """Rows of drift_report.diff that break the "tolerance" rule (empty == parity).

    display_unit=True (only for spawn runs compared with the committed goldens,
    which CI repeats on other platforms/BLAS builds): a leaf that was rounded for
    display (round(x, d) with d <= 6) may also differ by one unit in its last
    decimal, the size of a rounding flip caused by ulp-level differences. The
    in-process kernel comparisons (old blob vs new on the same machine) never
    use this allowance."""
    bad = []
    old_flat = dict(drift_report.flatten(old))
    for row in drift_report.diff(old, new):
        if row["kind"] == "removed" and _is_documented_hirschorn_removal(row, old_flat):
            continue
        if row["kind"] == "numeric" and isinstance(row["old"], float) and isinstance(row["new"], float):
            if row["old"] != 0 and abs(row["rel"]) <= rel_tol:
                continue
            unit = _display_unit(row["old"]) if display_unit else None
            if unit is not None and abs(row["abs"]) <= unit * (1 + 1e-9):
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
        # dft gained tetragonal_c11_eq_c12_marginal in the review fix round
        expected = {"cnls_fitting_solver": 5, "xrd_peak_deconvolution": 5, "dft_property_calculator": 6}
        self.assertEqual({s: len(cases.CASES[s]) for s in cases.SOLVERS}, expected)

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
            # Tolerance, not bytes: the old cnls blob also uses NumPy complex arithmetic, so
            # a recapture on another platform/BLAS can differ at ulp level (CI: Linux,
            # Python 3.11/3.12). Same rule as GoldenParityTest.
            rows = tolerance_violations(old["stdout"], fresh["stdout"], display_unit=True)
            self.assertEqual(rows, [], drift_report.render(f"{solver}/{case}", rows, 20))

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
        # display-unit allowance: only with display_unit=True, only for rounded leaves
        self.assertEqual(len(tolerance_violations({"a": 12.34}, {"a": 12.35})), 1)
        self.assertEqual(tolerance_violations({"a": 12.34}, {"a": 12.35}, display_unit=True), [])
        self.assertEqual(len(tolerance_violations({"a": 12.34}, {"a": 12.36}, display_unit=True)), 1)
        self.assertEqual(len(tolerance_violations({"a": 0.1234567891}, {"a": 0.1234567901}, display_unit=True)), 1)


class GoldenParityTest(unittest.TestCase):
    """Spawn-path run of every case against its faa6684 golden (rule: PARITY_MODE)."""
    maxDiff = None

    def _run(self, solver):
        for case in cases.CASES[solver]:
            with self.subTest(case=case):
                doc = load(solver, case)
                fresh = golden.run_solver(solver, cases.CASES[solver][case])
                if (solver, case) in VALIDATION_CHANGES:
                    code, field = VALIDATION_CHANGES[(solver, case)]
                    self.assertEqual((doc["exitCode"], doc["stdout"].get("success")), (0, True))
                    self.assertEqual(fresh["exitCode"], 2, fresh["stderr"])
                    self.assertEqual(fresh["stdout"]["errorKind"], "validation")
                    self.assertEqual((fresh["stdout"]["error"]["code"], fresh["stdout"]["error"]["field"]), (code, field))
                    continue
                self.assertEqual(fresh["exitCode"], doc["exitCode"], fresh["stderr"])
                self.assertEqual(fresh["stderr"], "")
                mode = PARITY_MODE[solver]
                if mode == "minimiser":
                    XrdParityTest.assert_minimiser_parity(self, case, doc["stdout"], fresh["stdout"])
                    continue
                rows = (tolerance_violations(doc["stdout"], fresh["stdout"], display_unit=True) if mode == "tolerance"
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


class HirschornRemovalGuardTest(unittest.TestCase):
    """The documented cHirschorn_* removal is tolerated exactly, nothing more."""

    def test_documented_removal_is_tolerated(self):
        old = {"c": [{"cHirschorn_F": 1.5e-6, "cHirschorn_uF": 1.5, "cHsuMansfeld_F": 1.5e-6 * (1 + 1e-15),
                      "cHsuMansfeld_uF": 1.5}]}
        new = {"c": [{"cHsuMansfeld_F": 1.5e-6 * (1 + 1e-15), "cHsuMansfeld_uF": 1.5}]}
        self.assertEqual(tolerance_violations(old, new), [])

    def test_removal_is_refused_when_the_values_are_not_duplicates(self):
        old = {"c": [{"cHirschorn_F": 1.5e-6, "cHsuMansfeld_F": 1.6e-6}]}
        self.assertEqual(len(tolerance_violations(old, {"c": [{"cHsuMansfeld_F": 1.6e-6}]})), 1)

    def test_other_removed_keys_and_changed_values_are_still_violations(self):
        old = {"c": [{"cHirschorn_F": 1.5e-6, "cHsuMansfeld_F": 1.5e-6, "cBrug_F": 2.0e-6}]}
        self.assertEqual(len(tolerance_violations(old, {"c": [{"cHsuMansfeld_F": 1.5e-6}]})), 1)
        changed = {"c": [{"cHsuMansfeld_F": 1.5e-6, "cBrug_F": 2.1e-6}]}
        self.assertEqual([r["key"] for r in tolerance_violations(old, changed)], ["c[0].cBrug_F"])


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

    @staticmethod
    def _random_start_payloads(count=100, seed=11):
        import random
        rng = random.Random(seed)
        fits = [k for k, v in cases.CASES["cnls_fitting_solver"].items() if v["action"] == "fit"]
        out = []
        for i in range(count):
            base = cases.CASES["cnls_fitting_solver"][fits[i % len(fits)]]
            params = []
            for p in base["parameters"]:
                q = dict(p)
                if p["field"] == "exponent":
                    q["value"] = min(p["max"], max(p["min"], p["value"] + rng.uniform(-0.1, 0.1)))
                else:
                    q["value"] = min(p["max"], max(p["min"], p["value"] * math.exp(rng.uniform(-1.2, 1.2))))
                params.append(q)
            out.append(dict(base, parameters=params))
        return out

    def test_random_starts_reach_the_same_optimum(self):
        """Iteration counts are NOT guaranteed equal. Near the optimum the LM
        accept/stop tests (relative step <= 1e-8 with reduction <= 1e-12, scaled
        gradient <= 1e-10) act on rounding-level quantities of an ill-conditioned
        J^T J, so LAPACK vs Gauss-Jordan rounding changes how many iterations run
        (Windows capture machine, these 100 starts: 70 identical, 26 differ in
        iteration count only, 4 differ in termination - in 2 the old run hit
        maxIterations and the new converged, in 1 the reverse, in 1 both converged by
        different stopping rules). The optimum agrees:
        chi-square within 1e-9 relative, every fitted value within 1e-8 relative
        (observed max 2.2e-9). Diagonal column scaling of the damped system was
        tried and did not improve agreement (68 identical), so it was not added."""
        old = blob_module("cnls_fitting_solver")
        import cnls_fitting_solver as cnls
        for i, payload in enumerate(self._random_start_payloads()):
            with self.subTest(start=i):
                args = (payload["topology"], payload["points"], payload["parameters"], payload["weighting"],
                        int(payload["maxIterations"]))
                with np.errstate(all="ignore"):
                    a, b = old.run_cnls_fit(*args), cnls.run_cnls_fit(*args)
                self.assertLessEqual(abs(b["chiSquare"] - a["chiSquare"]), REL_TOL * a["chiSquare"])
                for pa, pb in zip(a["parameters"], b["parameters"]):
                    self.assertLessEqual(abs(pb["fittedValue"] - pa["fittedValue"]), 1e-8 * abs(pa["fittedValue"]))

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


class XrdParityTest(unittest.TestCase):
    """xrd: coordinate search -> bounded scipy least_squares (different minimiser)."""

    # (output section, key, decimals the old value was rounded to) for the 6 fitted parameters
    PARAMS = (("ka1Peak", "twoTheta", 4), ("ka1Peak", "intensity", 1), ("ka1Peak", "fwhm_deg", 4),
              ("ka1Peak", "shapeParameter", 3), ("background", "intercept", 2), ("background", "slope", 4))
    NONLINEARITY_MARGIN = 1.10  # quadratic-model bound below, plus 10 %

    @staticmethod
    def _structure(doc):
        return [(k, v) if not drift_report._is_number(v) else (k, type(v).__name__)
                for k, v in drift_report.flatten(doc)]

    @classmethod
    def assert_minimiser_parity(cls, test, case, old, new):
        # exactly two allowed non-numeric differences: engine version, additive block
        test.assertEqual(old["engine"], XRD_ENGINE_OLD)
        test.assertEqual(new["engine"], XRD_ENGINE_NEW)
        test.assertEqual(set(new) - set(old), {"fitDiagnostics"})
        test.assertEqual(set(new["fitDiagnostics"]), XRD_DIAGNOSTIC_KEYS)
        test.assertEqual(new["fitDiagnostics"]["dof"], len(new["deconvolutionProfile"]) - 6)
        stripped = {k: v for k, v in new.items() if k != "fitDiagnostics"}
        stripped["engine"] = XRD_ENGINE_OLD
        # otherwise identical structure and non-numeric leaves; profile echoed unchanged
        test.assertEqual(cls._structure(old), cls._structure(stripped))
        for o, n in zip(old["deconvolutionProfile"], new["deconvolutionProfile"]):
            test.assertEqual((o["twoTheta"], o["rawIntensity"]), (n["twoTheta"], n["rawIntensity"]))
        # Fit quality, as asserted: SSE_new <= SSE_old * (1 + 1e-9) and r_wp_new <= r_wp_old
        # (not "strictly lower"). Observed on the 4 fitted goldens: strictly lower,
        # by 3.0 %, 10.1 %, 22.0 % and 1.0 % (Windows capture machine).
        test.assertLessEqual(new["goodnessOfFit"]["residualSumSquares"],
                             old["goodnessOfFit"]["residualSumSquares"] * (1 + REL_TOL), case)
        test.assertLessEqual(new["goodnessOfFit"]["r_wp_pct"], old["goodnessOfFit"]["r_wp_pct"], case)

    def _fit(self, case):
        """Run the case in-process, capturing the least-squares problem and solution."""
        import xrd_peak_deconvolution as xrd
        captured = {}
        original = xrd._fit_profile_least_squares

        def spy(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            captured["x"] = original(*args, **kwargs)
            return captured["x"]

        with patch.object(xrd, "_fit_profile_least_squares", spy):
            out = _in_process("xrd_peak_deconvolution", case)
        return xrd, captured, out

    @staticmethod
    def _residual_fn(xrd, args):
        tt, y, _x0, profile, ka2, ratio, fwhm_ratio, wl1, wl2 = args
        tt, y = np.asarray(tt, dtype=float), np.asarray(y, dtype=float)

        def res(v):
            c1, i1, w1, s, b0, b1 = v
            model = b0 + b1 * tt + xrd._profile_array(tt, c1, i1, w1, s, profile)
            if ka2:
                model = model + xrd._profile_array(tt, xrd.calculate_ka2_two_theta(c1, wl1, wl2), i1 * ratio,
                                                   w1 * fwhm_ratio, s, profile)
            return y - model
        return res

    def _sigma(self, res, x):
        jac = np.empty((res(x).size, 6))
        for k in range(6):
            h = 1e-6 * max(1.0, abs(x[k]))
            e = np.zeros(6)
            e[k] = h
            jac[:, k] = (res(x + e) - res(x - e)) / (2 * h)
        rss = float(res(x) @ res(x))
        s2 = rss / (res(x).size - 6)
        return rss, s2, np.sqrt(np.diag(np.linalg.inv(jac.T @ jac)) * s2)

    def test_solution_is_a_local_minimum_and_shifts_are_explained(self):
        for case, payload in cases.CASES["xrd_peak_deconvolution"].items():
            if ("xrd_peak_deconvolution", case) in VALIDATION_CHANGES:
                continue
            with self.subTest(case=case):
                xrd, cap, out = self._fit(case)
                res = self._residual_fn(xrd, cap["args"])
                x = np.array(cap["x"][0])
                rss, s2, sigma = self._sigma(res, x)
                # the minimiser's answer was accepted and is what the output reports
                self.assertLessEqual(abs(out["goodnessOfFit"]["residualSumSquares"] - rss), 0.0051)
                # local minimum: +-5 % of one standard error in any free coordinate raises the SSR
                lower, upper = (0.0, 1.0) if payload.get("profileType") == "pseudo-voigt" else (0.8, 10.0)
                for k in range(6):
                    for sign in (-1.0, 1.0):
                        trial = x.copy()
                        trial[k] += sign * 0.05 * sigma[k]
                        if k == 3 and not lower <= trial[k] <= upper:
                            continue
                        self.assertGreater(float(res(trial) @ res(trial)), rss, (case, k, sign))
                # Gauss-Newton bound: for SSR(x_old) - SSR* = s2 * d^2 every coordinate
                # obeys |x_old_k - x*_k| <= sigma_k * d. The old point is rounded in the
                # output, so add half a unit of its last decimal.
                old = load("xrd_peak_deconvolution", case)["stdout"]
                gain = old["goodnessOfFit"]["residualSumSquares"] - rss
                self.assertGreaterEqual(gain, -1e-9 * rss)
                d = math.sqrt(max(0.0, gain) / s2)
                for k, (section, key, decimals) in enumerate(self.PARAMS):
                    shift = abs(old[section][key] - x[k])
                    bound = self.NONLINEARITY_MARGIN * sigma[k] * d + 0.5 * 10.0 ** -decimals
                    self.assertLessEqual(shift, bound, (case, key, shift / sigma[k], d))

    def test_mutation_truncated_minimiser_is_detected(self):
        import xrd_peak_deconvolution as xrd
        original = xrd.least_squares
        with patch.object(xrd, "least_squares", lambda *a, **k: original(*a, **dict(k, max_nfev=2))):
            mutated = _in_process("xrd_peak_deconvolution", "pv_ka2_cu111")
        old = load("xrd_peak_deconvolution", "pv_ka2_cu111")["stdout"]
        with self.assertRaises(AssertionError):
            self.assert_minimiser_parity(self, "pv_ka2_cu111", old, mutated)

    def test_peak_centre_stays_inside_the_roi(self):
        # Review fix: the centre was unbounded (a far guess reported 2theta 73.75 for
        # a 42-44.6 deg ROI with success true). Guesses outside / at the edges.
        base = cases.CASES["xrd_peak_deconvolution"]["pv_ka2_cu111"]
        lo, hi = base["points"][0]["twoTheta"], base["points"][-1]["twoTheta"]
        for guess in (10.0, 41.99, 44.61, 73.75):
            with self.subTest(guess=guess):
                out = _in_process("xrd_peak_deconvolution", dict(base, center=guess))
                self.assertGreaterEqual(out["ka1Peak"]["twoTheta"], lo)
                self.assertLessEqual(out["ka1Peak"]["twoTheta"], hi)

    def _off_guess_regressions(self):
        """Starts away from the peak (centre, fwhm): cases where the new fit's SSE is
        above the faa6684 coordinate search's. Needs the faa6684 blob."""
        old = blob_module("xrd_peak_deconvolution")
        import xrd_peak_deconvolution as xrd
        worse = []
        for case in ("pv_ka2_cu111", "pearson7_ka2"):
            base = cases.CASES["xrd_peak_deconvolution"][case]
            lo, hi = base["points"][0]["twoTheta"], base["points"][-1]["twoTheta"]
            for centre in (lo, 43.0, 0.5 * (lo + hi), hi):
                for fwhm in (0.1, 0.25):
                    payload = dict(base, center=centre, fwhm=fwhm)
                    a = bench.dispatch(old, "xrd_peak_deconvolution", payload)["goodnessOfFit"]["residualSumSquares"]
                    b = bench.dispatch(xrd, "xrd_peak_deconvolution", payload)["goodnessOfFit"]["residualSumSquares"]
                    if b > a * (1 + REL_TOL):
                        worse.append((case, centre, fwhm, a, b))
        return worse

    @unittest.skipUnless(GIT, f"git or revision {BASE} unavailable")
    def test_off_peak_guesses_never_fit_worse_than_old(self):
        # Review-round finding: from a guess 0.3 deg off the peak the bounded trf fit
        # stalled in a zero-intensity local minimum (SSE 9.6e7 vs 9.3e5). The second,
        # data-driven start (_grid_start) removes that; 504 starts were swept for the
        # handoff, this is the CI-sized subset.
        self.assertEqual(self._off_guess_regressions(), [])

    @unittest.skipUnless(GIT, f"git or revision {BASE} unavailable")
    def test_mutation_without_grid_start_is_detected(self):
        import xrd_peak_deconvolution as xrd
        with patch.object(xrd, "_grid_start", lambda *a, **k: None):
            self.assertGreater(len(self._off_guess_regressions()), 0)

    def test_module_import_preloads_scipy_optimize(self):
        # The IPC daemon pre-imports the module, so its warm-up (not the first fit)
        # pays the scipy.optimize import; input_validation stays lazy.
        import subprocess
        probe = ("import json, sys; import xrd_peak_deconvolution; "
                 "print(json.dumps(['scipy.optimize' in sys.modules, 'input_validation' in sys.modules]))")
        out = subprocess.run([sys.executable, "-B", "-c", probe], cwd=str(HERE), capture_output=True, check=True)
        self.assertEqual(json.loads(out.stdout), [True, False])


class NewValidationTest(unittest.TestCase):
    """Deliberate behaviour changes, all typed validation envelopes (exit 2):
    - NON_FINITE: non-finite inputs the old loops turned into NaN/inf-laden
      "successful" output. Most of them would make LAPACK/scipy raise; inf xrd fwhm
      and inf eta/m would not (the new fit would clip them, the old one clamped
      inf fwhm and emitted non-standard JSON (Infinity) for eta=inf) and are
      rejected anyway as one consistent "finite start" rule.
    - OUT_OF_RANGE "points": xrd ROIs with < 7 points or a zero 2theta span
      (underdetermined 6-parameter fit; the old code returned SSE 0.0, success true).
    Nothing else changed."""

    def _envelope(self, solver, payload, field, code="NON_FINITE"):
        fresh = golden.run_solver(solver, payload)
        self.assertEqual(fresh["exitCode"], 2, fresh["stderr"])
        out = fresh["stdout"]
        self.assertEqual(set(out), {"success", "error", "errorKind"})
        self.assertIs(out["success"], False)
        self.assertEqual(out["errorKind"], "validation")
        self.assertEqual(out["error"]["code"], code)
        self.assertEqual(out["error"]["field"], field)

    def test_xrd_non_finite_start_or_observation(self):
        base = cases.CASES["xrd_peak_deconvolution"]["pv_ka2_cu111"]
        for key in ("center", "intensity", "fwhm", "eta"):
            for bad in (float("nan"), float("inf")):
                if (key, bad) == ("center", float("inf")):
                    continue  # pre-existing internal error, see below
                with self.subTest(key=key, bad=bad):
                    self._envelope("xrd_peak_deconvolution", dict(base, **{key: bad}), key)
        # center=inf already failed before the minimiser (Ka2 angle: math domain error,
        # exit 1) in faa6684; that pre-existing behaviour is unchanged.
        fresh = golden.run_solver("xrd_peak_deconvolution", dict(base, center=float("inf")))
        self.assertEqual((fresh["exitCode"], fresh["stdout"]), (1, {"error": "math domain error"}))
        points = [dict(p) for p in base["points"]]
        points[7]["sampleIntensity"] = float("nan")
        self._envelope("xrd_peak_deconvolution", dict(base, points=points), "points[7].sampleIntensity")

    def test_xrd_underdetermined_roi_and_ka2_ratio(self):
        base = cases.CASES["xrd_peak_deconvolution"]["pv_ka2_cu111"]
        for count in (0, 1, 6):
            with self.subTest(count=count):
                self._envelope("xrd_peak_deconvolution", dict(base, points=base["points"][:count]), "points",
                               code="OUT_OF_RANGE")
        flat = [dict(p, twoTheta=43.3) for p in base["points"][:20]]
        self._envelope("xrd_peak_deconvolution", dict(base, points=flat), "points", code="OUT_OF_RANGE")
        # 7 points (dof 1) is accepted
        fresh = golden.run_solver("xrd_peak_deconvolution", dict(base, points=base["points"][60:67]))
        self.assertEqual(fresh["exitCode"], 0, fresh["stderr"])
        self.assertEqual(fresh["stdout"]["fitDiagnostics"]["dof"], 1)
        for bad in (float("nan"), float("inf")):
            with self.subTest(ka2Ratio=bad):
                self._envelope("xrd_peak_deconvolution", dict(base, ka2Ratio=bad), "ka2Ratio")
        # ka2Ratio is unused (and not checked) without Ka2
        no_ka2 = cases.CASES["xrd_peak_deconvolution"]["pv_single_no_ka2"]
        self.assertEqual(golden.run_solver("xrd_peak_deconvolution", dict(no_ka2, ka2Ratio=float("nan")))["exitCode"], 0)

    def test_dft_non_finite_stiffness(self):
        custom = {"formula": "X", "crystal_system": "Cubic", "custom_c_ij": {"c11": float("nan"), "c12": 100.0, "c44": 50.0}}
        self._envelope("dft_property_calculator", custom, "custom_c_ij")
        iso = {"formula": "Zz", "crystal_system": "Isotropic", "k_vrh": float("inf"), "g_vrh": 50.0}
        self._envelope("dft_property_calculator", iso, "k_vrh")

    def test_cnls_non_finite_lin_kk_is_unchanged_nan(self):
        points = [dict(p) for p in cases._RANDLES_POINTS]
        points[5]["zReal"] = float("nan")
        fresh = golden.run_solver("cnls_fitting_solver", {"action": "validate_dataset", "points": points})
        self.assertEqual((fresh["exitCode"], fresh["stderr"]), (0, ""))
        self.assertTrue(math.isnan(fresh["stdout"]["linKK"]["kkChiSquare"]))


@require_git_revision(GIT, f"git or revision {BASE} unavailable")
class DftKernelParityTest(unittest.TestCase):
    """numpy/scipy inverse and eigenvalues against the faa6684 Gauss-Jordan / Jacobi."""

    def _matrices(self):
        import dft_property_calculator as dft
        out = []
        for bench_key, data in dft.AUTHENTIC_ELASTIC_BENCHMARKS.items():
            for system in ("Cubic", "Hexagonal", "Tetragonal", "Orthorhombic", "Trigonal", "Isotropic"):
                out.append((f"{bench_key}/{system}", dft.build_stiffness_matrix(system, 100.0, 50.0, data["formula"])[0]))
        rng = np.random.default_rng(6)
        for i in range(20):
            a = rng.normal(size=(6, 6))
            out.append((f"random_spd_{i}", (a @ a.T + 6 * np.eye(6)).tolist()))
        for system in ("Cubic", "Isotropic"):  # singular normal block (C11 == C12)
            out.append((f"singular/{system}", dft.build_stiffness_matrix(
                system, 0, 0, "", {"c11": 150.0, "c12": 150.0, "c44": 60.0})[0]))
        # near-singular: smallest pivot ~5.6e-17 (> 0, < 1e-12) -> still the fallback
        out.append(("singular/near_cubic", dft.build_stiffness_matrix(
            "Cubic", 0, 0, "", {"c11": 0.1 + 0.2, "c12": 0.3, "c44": 60.0})[0]))
        return out

    @staticmethod
    def _normwise(a, b):
        a, b = np.asarray(a), np.asarray(b)
        return float(np.max(np.abs(a - b)) / np.max(np.abs(a)))

    def test_inverse_and_eigenvalues_match_old_loops(self):
        import dft_property_calculator as dft
        old = blob_module("dft_property_calculator")
        fallbacks = 0
        for name, c in self._matrices():
            with self.subTest(matrix=name):
                old_inv, new_inv = old.invert_6x6_matrix(c), dft.invert_6x6_matrix(c)
                old_fb = all(old_inv[i][j] == 0.0 for i in range(6) for j in range(6) if i != j)
                new_fb = all(new_inv[i][j] == 0.0 for i in range(6) for j in range(6) if i != j)
                if name.startswith("singular"):
                    fallbacks += 1
                    self.assertTrue(old_fb and new_fb)
                    self.assertEqual(old_inv, new_inv)  # same diagonal fallback, bit-identical
                self.assertLessEqual(self._normwise(old_inv, new_inv), REL_TOL)
                self.assertLessEqual(self._normwise(old.jacobi_eigenvalues_symmetric(c),
                                                    dft.jacobi_eigenvalues_symmetric(c)), REL_TOL)
                self.assertTrue(all(type(v) is float for row in new_inv for v in row))
        self.assertEqual(fallbacks, 3)

    @staticmethod
    def _marginal_payloads(count=300, seed=7):
        """Tensors on the stability boundary (c11 == c12, or c12 == -c11 for the
        hexagonal family) plus ordinary ones, over every crystal-system branch."""
        import random
        rng = random.Random(seed)
        out = []
        while len(out) < count:
            system = rng.choice(["Cubic", "Hexagonal", "Tetragonal", "Orthorhombic", "Trigonal", "Isotropic"])
            c11 = round(rng.uniform(50, 400), 1)
            kind = rng.choice(["equal", "negative", "random"])
            if kind == "negative" and system not in ("Hexagonal", "Trigonal"):
                continue
            c12 = c11 if kind == "equal" else (-c11 if kind == "negative" else round(rng.uniform(10, c11), 1))
            out.append({"formula": "Zq", "crystal_system": system, "custom_c_ij": {
                "c11": c11, "c12": c12, "c13": round(rng.uniform(10, 200), 1),
                "c33": round(rng.uniform(50, 400), 1), "c44": round(rng.uniform(10, 150), 1)}})
        return out

    @staticmethod
    def _exactly_positive_definite(c):
        """Sylvester's criterion in exact rational arithmetic on the float matrix."""
        from fractions import Fraction
        a = [[Fraction(v) for v in row] for row in c]
        n = len(a)
        for k in range(n):  # Gaussian elimination without pivoting = leading minors ratio
            if a[k][k] <= 0:
                return False
            for i in range(k + 1, n):
                f = a[i][k] / a[k][k]
                for j in range(k, n):
                    a[i][j] -= f * a[k][j]
        return True

    def _verdicts(self, module):
        """(payload, module verdict, exact verdict) with the exact eigenvalue test and
        the module's own float Born checks."""
        out = []
        for payload in self._marginal_payloads():
            born = module.calculate_dft_properties(payload)["bornStability"]
            c = module.build_stiffness_matrix(payload["crystal_system"], 0, 0, "Zq", payload["custom_c_ij"])[0]
            exact = self._exactly_positive_definite(c) and all(chk["passed"] for chk in born["criteriaChecks"])
            out.append((payload, born["isMechanicallyStable"], exact))
        return out

    def test_stability_verdict_is_exact_on_marginal_tensors(self):
        # A zero eigenvalue is not positive definite: eigvalsh rounding noise must not
        # report "stable". (The faa6684 Jacobi loop got this wrong on some tensors too,
        # see test_old_jacobi_misjudged_marginal_tensors.)
        import dft_property_calculator as dft
        wrong = [p for p, verdict, exact in self._verdicts(dft) if verdict != exact]
        self.assertEqual(wrong, [])

    def test_old_jacobi_misjudged_marginal_tensors(self):
        # Documentation of the old behaviour, not a requirement on the new code: the
        # faa6684 loop can leave +O(1e-15) noise on an exactly singular tensor and call
        # it stable (1 of these 300 on the Windows capture machine; the count depends
        # on the platform libm, so only its character is asserted here).
        wrong = [p for p, verdict, exact in self._verdicts(blob_module("dft_property_calculator")) if verdict != exact]
        self.assertTrue(all(p["custom_c_ij"]["c11"] == p["custom_c_ij"]["c12"] for p in wrong), wrong)

    def test_mutation_zero_eigenvalue_tolerance_is_detected(self):
        import dft_property_calculator as dft
        with patch.object(dft, "EIGENVALUE_POSITIVE_RTOL", 0.0):
            wrong = [p for p, verdict, exact in self._verdicts(dft) if verdict != exact]
        self.assertGreater(len(wrong), 0)

    def test_common_path_does_not_import_scipy(self):
        # scipy.linalg (exact LU pivots) loads only when the det certificate fails.
        import subprocess
        probe = ("import json, sys; import dft_property_calculator as d; "
                 "d.calculate_dft_properties({}); d.calculate_dft_properties({'formula': 'Ni3Al', 'crystal_system': 'Cubic'}); "
                 "a = sorted(m for m in ('scipy', 'input_validation') if m in sys.modules); "
                 "d.invert_6x6_matrix(d.build_stiffness_matrix('Cubic', 0, 0, '', {'c11': 150.0, 'c12': 150.0, 'c44': 60.0})[0]); "
                 "print(json.dumps([a, 'scipy' in sys.modules]))")
        out = subprocess.run([sys.executable, "-B", "-c", probe], cwd=str(HERE), capture_output=True, check=True)
        self.assertEqual(json.loads(out.stdout), [[], True])

    def test_mutation_perturbed_inverse_is_detected(self):
        import dft_property_calculator as dft
        old = blob_module("dft_property_calculator")
        c = dft.build_stiffness_matrix("Cubic", 0, 0, "Ni3Al")[0]
        inv = np.linalg.inv
        with patch.object(dft.np.linalg, "inv", lambda a: inv(a) * (1 + 1e-6)):
            self.assertGreater(self._normwise(old.invert_6x6_matrix(c), dft.invert_6x6_matrix(c)), REL_TOL)

    def test_mutation_perturbed_eigenvalues_is_detected(self):
        import dft_property_calculator as dft
        eigvalsh = np.linalg.eigvalsh
        with patch.object(dft.np.linalg, "eigvalsh", lambda a: eigvalsh(a) + 0.01):
            mutated = _in_process("dft_property_calculator", "ni3al_cubic_benchmark")
        rows = tolerance_violations(load("dft_property_calculator", "ni3al_cubic_benchmark")["stdout"], mutated)
        self.assertTrue(any(r["key"].startswith("bornStability.allEigenvaluesGPa") for r in rows))


if __name__ == "__main__":
    unittest.main()
