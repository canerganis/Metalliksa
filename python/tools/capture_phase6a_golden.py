#!/usr/bin/env python3
"""
Phase 6a golden harness: capture fixed solver payloads as bit-exact baselines.

Each case runs the solver exactly as the app's ad-hoc spawn path does
(server/processOrchestrator.ts executeViaAdHocSpawn): ``python -B <solver>.py``
with the JSON payload on stdin, cwd = python/. The stdout JSON is parsed, volatile
keys are stripped (wall-clock durations, timestamps and the interpreter version)
and the result is written to ``python/golden/phase6a/<solver>/<case>.json``.

Only stochastic_uq_mmpds_solver uses an RNG; its cases pass a fixed seed (42), so
every case is deterministic once the volatile keys are removed. Library modules
without a __main__ (lpbf_fatigue_fracture) run through a driver (MODULE_DRIVERS).

Golden files are only (re)written with ``--force``. Re-blessing after a value
change (design step (b)) must attach the drift report (tools/drift_report.py) to
the commit body.

Usage (from python/):
    python -B tools/capture_phase6a_golden.py [--force] [--solver NAME] [--from-revision REV]

Binding: every golden records the sha256 (CRLF->LF normalised, i.e. git blob form)
of the solver that produced it plus git HEAD. A capture labelled d33b6f5 is refused
unless the solver bytes it runs equal the d33b6f5 blob; after the migration use
--from-revision d33b6f5, which runs the immutable blob from a temp dir.

Optional imports: the d33b6f5 goldens were captured on an interpreter WITHOUT
pycalphad (the locked LPBF interpreter; python/requirements-lpbf*.lock has no
pycalphad), so the calphad_solver goldens record the base blob's no-pycalphad branch
("pycalphadVersion": "No module named 'pycalphad'"). The base blob imports pycalphad
when it can and then takes a different path (engine "pycalphad-open-tdb"), so a
blob re-capture on an interpreter that has pycalphad (python/requirements.txt pins
pycalphad>=0.11.2,<0.13) would not reproduce the goldens. Blob runs therefore hide
GOLDEN_HIDDEN_MODULES: importing them raises the same ModuleNotFoundError an
interpreter without the package raises, so the capture is identical on both.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import types
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PYTHON_DIR = Path(__file__).resolve().parent.parent
GOLDEN_DIR = PYTHON_DIR / "golden" / "phase6a"
BASE_REVISION = "d33b6f5"
GOLDEN_SCHEMA = "phase6a-golden-1"
# Optional packages that were absent when the d33b6f5 goldens were captured (see the
# module docstring). Hidden from every base-blob run made by capture().
GOLDEN_HIDDEN_MODULES: Tuple[str, ...] = ("pycalphad",)

# Keys removed at any depth before comparison. durationMs/computeTimeMs are
# time.perf_counter wall times, timestamp is wall-clock UTC, pythonVersion is the
# interpreter that ran the capture. Nothing else is stripped.
VOLATILE_KEYS = frozenset({"durationMs", "computeTimeMs", "timestamp", "pythonVersion"})
# Top-level keys added by the Phase 6a migration that carry provenance, not results.
# They are removed from the bit-exact comparison explicitly and checked separately
# (test_phase6a_golden.ProvenanceTest), so a golden captured before the migration
# still compares equal.
PROVENANCE_KEYS = frozenset({"provenance"})

# Synthetic Butler-Volmer polarisation curve (Ecorr -0.30 V, icorr 2.0 uA/cm2,
# ba 0.08, bc 0.12 V/dec), 41 points. Synthetic, not experimental data.
_SYNTHETIC_BV_POINTS: List[Tuple[float, float]] = [
    (-0.55, 242.305032), (-0.5375, 190.631227), (-0.525, 149.976762), (-0.5125, 117.991512),
    (-0.5, 92.826452), (-0.4875, 73.026762), (-0.475, 57.447709), (-0.4625, 45.188449),
    (-0.45, 35.539918), (-0.4375, 27.943787), (-0.425, 21.960115), (-0.4125, 17.241803),
    (-0.4, 13.514373), (-0.3875, 10.559878), (-0.375, 8.203974), (-0.3625, 6.305379),
    (-0.35, 4.74704), (-0.3375, 3.428408), (-0.325, 2.258261), (-0.3125, 1.147462),
    (-0.3, 0.001), (-0.2875, 1.293538), (-0.275, 2.870118), (-0.2625, 4.912519),
    (-0.25, 7.668693), (-0.2375, 11.484095), (-0.225, 16.846012), (-0.2125, 24.446622),
    (-0.2, 35.273028), (-0.1875, 50.735979), (-0.175, 72.854122), (-0.1625, 104.517869),
    (-0.15, 149.867374), (-0.1375, 214.834082), (-0.125, 307.916691), (-0.1125, 441.293045),
    (-0.1, 632.413443), (-0.0875, 906.283828), (-0.075, 1298.737593), (-0.0625, 1861.124099),
    (-0.05, 2667.027356),
]

# Payloads. The first four of each solver are the pre-refactor baselines in
# .orchestra/golden/{tafel,pourbaix} (same inputs); the fifth adds coverage.
CASES: Dict[str, Dict[str, Dict[str, Any]]] = {
    "tafel_corrosion_rate_solver": {
        "solve_316l_default_fields": {
            "iCorr_uA_cm2": 1.25, "eCorr_V": -0.35, "betaA": 0.12, "betaC": 0.1,
            "specimenAreaCm2": 1.0, "initialThicknessMm": 5.0, "allowableLossMm": 1.5,
            "temperatureC": 25.0, "alloyId": "steel-316l",
        },
        "solve_1018_custom_composition": {
            "iCorr_uA_cm2": 15.0, "eCorr_V": -0.62, "betaA": 0.09, "betaC": 0.15,
            "specimenAreaCm2": 2.5, "initialThicknessMm": 8.0, "allowableLossMm": 3.0,
            "temperatureC": 40.0, "alloyId": "steel-1018",
            "customComposition": {"Fe": 0.985, "Mn": 0.008, "C": 0.002, "Si": 0.005},
        },
        "fit_curve_synthetic_bv": {
            "action": "fit_curve",
            "points": [{"potential": e, "currentDensity_uA_cm2": i} for e, i in _SYNTHETIC_BV_POINTS],
            "electrodeAreaCm2": 1.0, "alloyId": "al-6061",
        },
        # Silent defaults today: unknown alloyId -> steel-316l, zero -> default, abs().
        "edge_unknown_alloy_zero_icorr": {
            "alloyId": "unobtainium-x", "iCorr_uA_cm2": 0, "betaA": -0.12, "betaC": 0,
            "specimenAreaCm2": -3, "temperatureC": 0,
        },
        # Unknown alloyId, but every preset-derived value is supplied by the caller,
        # so no preset value is consumed (this is what TafelPolarizationLab sends
        # for its "duplex2205" option when the dataset metadata is filled).
        "solve_unknown_alloy_full_overrides": {
            "alloyId": "duplex2205", "alloyName": "2205 Duplex Stainless Steel",
            "density_g_cm3": 7.80, "equivalentWeight": 25.40, "activationEnergyJ_mol": 33000.0,
            "iCorr_uA_cm2": 3.0, "eCorr_V": -0.28, "betaA": 0.11, "betaC": 0.13,
            "specimenAreaCm2": 1.5, "initialThicknessMm": 6.0, "allowableLossMm": 2.0,
            "temperatureC": 35.0,
        },
    },
    "pourbaix_solver": {
        "fe_chloride_points": {
            "element": "Fe", "temperature_C": 25, "ionActivity_log10": -6, "chloride_ppm": 1000,
            "experimentalPoints": [
                {"id": "p1", "name": "Acid", "ph": 2, "potential_V": -0.2, "refElectrode": "SCE"},
                {"id": "p2", "name": "Neutral", "ph": 7, "potential_V": 0.1, "refElectrode": "Ag/AgCl (3M KCl)"},
                {"id": "p3", "name": "Alkaline", "ph": 12, "potential_V": 0.3, "refElectrode": "SHE"},
                {"id": "p4", "name": "Cathodic", "ph": 7, "potential_V": -0.9, "refElectrode": "CSE"},
            ],
        },
        "al_hot_chloride": {
            "element": "Al", "temperature_C": 60, "ionActivity_log10": -4, "chloride_ppm": 200,
            "experimentalPoints": [
                {"ph": 3, "potential_V": -1.0},
                {"ph": 9, "potential_V": -0.5, "refElectrode": "MMS"},
            ],
        },
        "cu_nochloride": {
            "element": "Cu", "temperature_C": 25, "ionActivity_log10": -6, "chloride_ppm": 0,
            "experimentalPoints": [{"ph": 5, "potential_V": 0.4, "refElectrode": "SHE"}],
        },
        # Silent defaults today: unknown element -> Fe systems + Ni point branch.
        "edge_unknown_element_badvals": {
            "element": "Unobtainium", "temperature_C": -300, "ionActivity_log10": 3, "chloride_ppm": -50,
            "experimentalPoints": [
                {"ph": 20, "potential_V": 0, "refElectrode": "NotARef"},
                {"name": "missing fields"},
            ],
        },
        "ni_acid_points": {
            "element": "Ni", "temperature_C": 80, "ionActivity_log10": -5, "chloride_ppm": 600,
            "experimentalPoints": [
                {"id": "n1", "name": "Acid", "ph": 1.5, "potential_V": 0.1, "refElectrode": "Ag/AgCl (Sat KCl)"},
                {"id": "n2", "name": "Caustic", "ph": 13, "potential_V": 0.5, "refElectrode": "SHE"},
            ],
        },
    },
}


def strip_volatile(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: strip_volatile(v) for k, v in value.items() if k not in VOLATILE_KEYS}
    if isinstance(value, list):
        return [strip_volatile(v) for v in value]
    return value


def canonical(value: Any) -> str:
    """Canonical JSON text; float repr round-trips exactly, so equal text == bit-exact."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=True)


class CaptureRefused(RuntimeError):
    """Raised when a capture would label output with a revision it did not come from."""


def _git(*args: str) -> bytes:
    return subprocess.run(["git", "-C", str(PYTHON_DIR), *args], capture_output=True, check=True).stdout


def normalised_sha256(data: bytes) -> str:
    """sha256 of the bytes with CRLF folded to LF, i.e. of the git blob form.

    The working tree uses core.autocrlf (CRLF on disk, LF in git), so raw working
    bytes never equal the blob; the normalised digest is equal exactly when the
    content is identical to the committed blob.
    """
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def solver_bytes(solver: str, revision: Optional[str] = None) -> bytes:
    if revision is None:
        return (PYTHON_DIR / f"{solver}.py").read_bytes()
    return _git("show", f"{revision}:python/{solver}.py")


def git_head() -> Optional[str]:
    try:
        return _git("rev-parse", "HEAD").decode().strip()
    except (OSError, subprocess.CalledProcessError):
        return None


_BLOB_RUNNER = (
    "import os, sys\n"
    "_hidden = tuple(n for n in os.environ.get('PHASE6A_HIDE_MODULES', '').split(',') if n)\n"
    "class _HideFinder:\n"
    "    def find_spec(self, name, path=None, target=None):\n"
    "        if name.split('.')[0] in _hidden:\n"
    "            raise ModuleNotFoundError(f\"No module named '{name}'\", name=name)\n"
    "        return None\n"
    "if _hidden:\n"
    "    sys.meta_path.insert(0, _HideFinder())\n"
    "_f = os.environ['PHASE6A_BLOB_AS_FILE']\n"
    "sys.argv = [_f]\n"
    "with open(os.environ['PHASE6A_BLOB_SCRIPT'], 'rb') as _h:\n"
    "    _code = compile(_h.read(), _f, 'exec')\n"
    "exec(_code, {'__name__': '__main__', '__file__': _f, '__builtins__': __builtins__})\n"
)


def run_solver(solver: str, payload: Any, python: str = sys.executable, timeout: float = 180.0,
               script: Optional[Path] = None, hide_modules: Tuple[str, ...] = ()) -> Dict[str, Any]:
    """Run ``<solver>.py`` like the app's ad-hoc spawn; return exit code and parsed stdout.

    ``script`` runs another copy of the solver (e.g. a git blob extracted to a temp
    dir) with the same cwd, and python/ on PYTHONPATH for its local imports.
    ``hide_modules`` (only with ``script``, not with a module driver) makes importing
    those top-level packages raise ModuleNotFoundError("No module named '<name>'"),
    as on an interpreter where they are not installed.
    """
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("PHASE6A_HIDE_MODULES", None)
    if hide_modules and (script is None or solver in MODULE_DRIVERS):
        raise ValueError("hide_modules needs a base-blob script run (not the working tree or a module driver)")
    cmd = [python, "-B", f"{solver}.py"]
    driver = MODULE_DRIVERS.get(solver)
    if driver is not None:
        # Library module: run its driver; the module under test comes first on the path.
        cmd = [python, "-B", driver]
        search = ([str(script.parent)] if script is not None else []) + [str(PYTHON_DIR)]
        env["PYTHONPATH"] = os.pathsep.join(search + [env.get("PYTHONPATH", "")])
    elif script is not None:
        env["PYTHONPATH"] = str(PYTHON_DIR) + os.pathsep + env.get("PYTHONPATH", "")
        # Execute the copied bytes as if they were python/<solver>.py: solvers that
        # locate data next to __file__ (calphad_solver's databases/) must see the
        # real directory, and sys.argv must look like a plain script run.
        env["PHASE6A_BLOB_SCRIPT"] = str(script)
        env["PHASE6A_BLOB_AS_FILE"] = str(PYTHON_DIR / f"{solver}.py")
        if hide_modules:
            env["PHASE6A_HIDE_MODULES"] = ",".join(hide_modules)
        cmd = [python, "-B", "-c", _BLOB_RUNNER]
    proc = subprocess.run(
        cmd, input=json.dumps(payload).encode("utf-8"),
        capture_output=True, timeout=timeout, env=env, cwd=str(PYTHON_DIR),
    )
    stdout = proc.stdout.decode("utf-8")
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        parsed = {"__unparseableStdout__": stdout}
    provenance = None
    if isinstance(parsed, dict):
        provenance = {k: parsed.pop(k) for k in PROVENANCE_KEYS if k in parsed} or None
    return {"exitCode": proc.returncode, "stdout": strip_volatile(parsed),
            "provenance": provenance,
            "stderr": proc.stderr.decode("utf-8", errors="replace")}


def golden_path(solver: str, case: str) -> Path:
    return GOLDEN_DIR / solver / f"{case}.json"


def load_golden(solver: str, case: str) -> Dict[str, Any]:
    with open(golden_path(solver, case), "r", encoding="utf-8") as fh:
        return json.load(fh)


def iter_golden_cases():
    for solver, cases in CASES.items():
        for case in cases:
            yield solver, case


# ---- Phase 6a value step (b): re-blessed expectations ----
# The d33b6f5 goldens above stay on disk unchanged as the pre-migration record (the
# binding tests keep re-capturing them from the immutable blobs). A value commit of
# design step (b) that changes a solver output re-blesses the case into
# <solver>/step_b/<case>.json (tools/bless_step_b.py), which records the drift
# against the d33b6f5 golden key by key; the regression tests then compare against
# that file. Cases whose output did not change keep no step_b file.
STEP_B_DIR = "step_b"
STEP_B_SCHEMA = "phase6a-step-b-golden-1"
STEP_B_LABEL = "phase6a-step-b"


def step_b_path(solver: str, case: str) -> Path:
    return GOLDEN_DIR / solver / STEP_B_DIR / f"{case}.json"


def load_expected(solver: str, case: str) -> Dict[str, Any]:
    """The current expectation: the step-(b) re-blessed golden if present, else the d33b6f5 golden."""
    path = step_b_path(solver, case)
    if path.exists():
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return load_golden(solver, case)


# Guard on what a step_b re-bless may record (fix round item 7). Design step (b) only
# changes values: every drift row against the d33b6f5 golden must be numeric, except
# changed strings under the keys below (generated code snippets that print a value).
# Exception, listed per row pattern: EXPECTED_DOCUMENTED_VALUE_CHANGES below (kinetics
# predictedHardness_HV -> ASTM E140 and the UQ norm_ppf sign fix from phase6a_t2b_golden_cases; pourbaix
# WP-E equilibrium engine from pourbaix_golden_check), each row verified exactly by
# documented_change_violation; it does not widen the bound for any other row.
STEP_B_ALLOWED_STRING_KEYS = frozenset({"pythonCode"})
# The tafel solverMethod string was made truthful (linear regression, not "Evans Optimization"); scoped to that solver.
STEP_B_ALLOWED_STRING_KEYS_BY_SOLVER = {"tafel_corrosion_rate_solver": frozenset({"solverMethod"})}
# Eyewash removal (fix/eyewash-labels-dead-ui): the tafel annual-rate output no longer carries the template
# "pythonCode" script (it was not the code that ran) nor the unsourced x3.5 pitting heuristic. Only these leaf keys
# of the tafel solver may be absent from a re-blessed stdout; any other removed row is still a violation.
STEP_B_ALLOWED_REMOVED_KEYS = {"tafel_corrosion_rate_solver": frozenset(
    {"pythonCode", "rulPittingYears", "lossPittingMm", "remainingPittingMm"})}
STEP_B_DEFAULT_MAX_REL = 1e-2
# tafel: the drift follows the equivalent-weight change (EW rel r): rates and losses
# move by r, and remaining wall/pitting thickness (thickness - loss) amplifies it by
# loss/remaining, which stays below 3 in the golden cases; plus 1e-2 for last-digit
# rounding of small printed values. Without an EW row the default bound applies.
STEP_B_TAFEL_EW_AMPLIFICATION = 3.0


def step_b_max_rel(solver: str, rows: List[Dict[str, Any]]) -> float:
    if solver == "pourbaix_solver":
        # Every numeric Pourbaix drift row is a documented change verified exactly (pourbaix_golden_check);
        # there is no generic percentage bound that an undocumented number (Nernst slope, water line, a
        # measured input potential) could hide under.
        return 0.0
    if solver == "tafel_corrosion_rate_solver":
        ew = [r for r in rows if r["key"] == "equivalentWeight" and r.get("rel") is not None]
        if ew:
            return STEP_B_TAFEL_EW_AMPLIFICATION * abs(ew[0]["rel"]) + STEP_B_DEFAULT_MAX_REL
    return STEP_B_DEFAULT_MAX_REL


# Documented value changes of every solver: the tranche-2b table (kinetics HV) plus the pourbaix
# entry (WP-G). Pourbaix rows are verified by documented_change_violation against
# tools/pourbaix_oracle.py (pourbaix_golden_check), never by a bound.
EXPECTED_DOCUMENTED_VALUE_CHANGES: Dict[str, Dict[str, str]] = {}


def _load_documented_value_changes() -> None:
    cases = globals().get("_t2b_cases")
    EXPECTED_DOCUMENTED_VALUE_CHANGES.clear()
    EXPECTED_DOCUMENTED_VALUE_CHANGES.update(
        {k: dict(v) for k, v in getattr(cases, "EXPECTED_DOCUMENTED_VALUE_CHANGES", {}).items()})
    import pourbaix_golden_check  # noqa: E402 (python/tools module)
    EXPECTED_DOCUMENTED_VALUE_CHANGES["pourbaix_solver"] = dict(pourbaix_golden_check.DOCUMENTED_VALUE_CHANGES)
    # Physics audit lane tafel-uq (tools/physics_audit_changes.py): EUQ-4 Joe-Kuo Sobol table and EUQ-11
    # generalized reliability index; verified by the same whole-document oracle as the norm_ppf fix.
    import physics_audit_changes as audit  # noqa: E402 (python/tools module)
    uq = EXPECTED_DOCUMENTED_VALUE_CHANGES.setdefault("stochastic_uq_mmpds_solver", {})
    for pattern in audit.UQ_AUDIT_ROW_PATTERNS:
        uq[pattern] = "EUQ-4 Joe-Kuo direction numbers / EUQ-11 generalized reliability index (physics audit)"


def _documented_change_patterns(solver: str) -> Dict[str, str]:
    if not EXPECTED_DOCUMENTED_VALUE_CHANGES:
        _load_documented_value_changes()
    return dict(EXPECTED_DOCUMENTED_VALUE_CHANGES.get(solver, {}))


def _is_documented_change_row(solver: str, key: str, kind: Optional[str] = None) -> bool:
    if solver == "tafel_corrosion_rate_solver":
        import physics_audit_changes as audit  # noqa: E402 (python/tools module)
        return audit.is_tafel_audit_row(key)
    if not any(re.fullmatch(p, key) for p in _documented_change_patterns(solver)):
        return False
    if solver == "kinetics_ttt_cct_solver" and not _KINETICS_HV_ROW.fullmatch(key):
        # fx-kinetics patterns only apply to the row kinds they document (other kinds, e.g. the
        # bounded numeric R drift of a steel TTT time, stay under the default guard).
        import kinetics_documented_changes as kdc  # noqa: E402 (tools/ module)
        return kdc.is_documented_row(key, kind)
    return True


# HRC values of the old kinetics CCT lookup bands (kinetics_ttt_cct_solver at 7f3f803).
_OLD_KINETICS_HRC_BANDS = (18.0, 28.0, 42.0, 54.0, 58.0, 64.0)
_KINETICS_HV_ROW = re.compile(r"cctContinuousCoolingMap\[(\d+)\]\.predictedHardness_HV(_status)?")


def pourbaix_documented_change_violation(row: Dict[str, Any], old_stdout: Optional[Dict[str, Any]],
                                         new_stdout: Optional[Dict[str, Any]],
                                         context: Any = None) -> Optional[str]:
    """Pourbaix hook (WP-G): None when ``row`` is exactly the documented WP-E change.

    The row's old value must be the d33b6f5 golden's leaf (``old_stdout``), its new value the
    re-blessed document's leaf, and the section of the re-blessed document it lives in must equal
    the independent oracle (tools/pourbaix_golden_check.document_problems: categories, species
    and texts equal, boundary/polygon coordinates <= 1e-4 V). Nothing is accepted by tolerance.
    """
    key = row["key"]
    if old_stdout is None or new_stdout is None:
        return f"{key}: documented change needs the d33b6f5 golden and the re-blessed document"
    import pourbaix_golden_check as check  # noqa: E402 (python/tools module)
    if context is None:
        context = check.Context(old_stdout, new_stdout)
    return check.row_problem(row, context)


_UQ_ORACLE_CACHE: Dict[str, Any] = {}
# The oracle solver is the PINNED pre-fix blob (the last solver with the norm_ppf sign error),
# never the working-tree solver: a later edit of stochastic_uq_mmpds_solver.py must not be able to
# match its own "oracle". The blob is bound by git revision AND content digest.
UQ_ORACLE_REVISION = "f41e316"
UQ_ORACLE_SHA256 = "2b28829be3f974f81f547b62f4c0abd59bb32c42fcf0cfbf838e64d0f99061ce"


def _uq_pinned_solver_module() -> types.ModuleType:
    """The pre-fix solver blob executed as a throwaway module (imports resolve against python/)."""
    if "module" not in _UQ_ORACLE_CACHE:
        solver = "stochastic_uq_mmpds_solver"
        try:
            source = solver_bytes(solver, UQ_ORACLE_REVISION)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise RuntimeError(f"cannot read python/{solver}.py at {UQ_ORACLE_REVISION} from git ({exc})")
        if normalised_sha256(source) != UQ_ORACLE_SHA256:
            raise RuntimeError(f"python/{solver}.py at {UQ_ORACLE_REVISION} does not match the pinned sha256")
        if str(PYTHON_DIR) not in sys.path:
            sys.path.insert(0, str(PYTHON_DIR))
        module = types.ModuleType(f"_uq_oracle_{solver}")
        sys.modules[module.__name__] = module
        try:
            exec(compile(source, f"{solver}.py@{UQ_ORACLE_REVISION}", "exec"), module.__dict__)
        finally:
            sys.modules.pop(module.__name__, None)
        _UQ_ORACLE_CACHE["module"] = module
    return _UQ_ORACLE_CACHE["module"]


def _uq_scipy_oracle_stdout(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Stdout (volatile keys stripped) of the PINNED pre-fix UQ solver with scipy.special.ndtri
    substituted for its broken norm_ppf.

    The payload keeps its key order: composition elements map to Sobol dimensions in insertion
    order. ndtri is the independent oracle; everything else is the f41e316 code, so any change of
    the solver other than the inverse normal is not covered by the documented change.
    """
    cache_key = json.dumps(payload)
    if cache_key not in _UQ_ORACLE_CACHE:
        import copy
        from scipy.special import ndtri
        module = _uq_pinned_solver_module()

        def oracle(p: float) -> float:
            if p <= 0.0:
                return -8.0
            if p >= 1.0:
                return 8.0
            return float(ndtri(p))

        import physics_audit_changes as audit  # noqa: E402 (python/tools module)
        original = module.norm_ppf
        original_poly = module.SobolSequenceGenerator.POLY
        module.norm_ppf = oracle
        # EUQ-4: Joe & Kuo new-joe-kuo-6.21201 direction numbers from scipy's copy of the table.
        module.SobolSequenceGenerator.POLY = audit.joe_kuo_poly()
        try:
            result = module.solve_stochastic_uq(copy.deepcopy(payload))
        finally:
            module.norm_ppf = original
            module.SobolSequenceGenerator.POLY = original_poly
        _UQ_ORACLE_CACHE[cache_key] = strip_volatile(json.loads(json.dumps(result)))
    return _UQ_ORACLE_CACHE[cache_key]


# Unsupported-output removal (lane uqlab): the pinned pre-fix solver computed UTS = YS*(1+2.15n), a clamped
# K_Ic and a critical flaw size from invented laws. The current solver reports them as null with a status
# string. The strings are pinned here literally (not imported from the solver) so a later solver edit cannot
# match its own oracle.
_UQ_UTS_STATUS = ("unavailable: no sourced UTS / work-hardening law (the former UTS = YS*(1+2.15n) was invented); "
                  "see the ICME solver")
_UQ_K1C_STATUS = ("unavailable: no sourced fracture-toughness law (the former K_Ic clamp of 18-160 MPa*sqrt(m) "
                  "was invented); see the ICME solver")
_UQ_FLAW_STATUS = ("unavailable: critical flaw size needs a sourced K_Ic; the former estimate was dimensionally "
                   "unsupported")
_UQ_REMOVED_ROW = re.compile(r"stochasticProperties\.(ultimateTensileStrength_UTS|fractureToughness_K1c|"
                             r"criticalFlawSize_ac)(_status|\..+)?|"
                             r"aerospaceReliability\.criticalFlaw(Median_mm|_P10_mm|_status)")


def _uq_without_unsupported_outputs(doc: Dict[str, Any]) -> Dict[str, Any]:
    """The oracle document with the three invented-law outputs replaced by null + status, and the
    physics-audit EUQ-11 reliability block / EUQ-4 description strings (tools/physics_audit_changes.py)."""
    import copy
    import physics_audit_changes as audit  # noqa: E402 (python/tools module)
    out = audit.uq_reliability_and_text_changes(copy.deepcopy(doc))
    props = out["stochasticProperties"]
    props["ultimateTensileStrength_UTS"] = None
    props["ultimateTensileStrength_UTS_status"] = _UQ_UTS_STATUS
    props["fractureToughness_K1c"] = None
    props["fractureToughness_K1c_status"] = _UQ_K1C_STATUS
    props["criticalFlawSize_ac"] = None
    props["criticalFlawSize_ac_status"] = _UQ_FLAW_STATUS
    rel = out["aerospaceReliability"]
    rel["criticalFlawMedian_mm"] = None
    rel["criticalFlaw_P10_mm"] = None
    rel["criticalFlaw_status"] = _UQ_FLAW_STATUS
    return out


def _uq_sampler_violation(row: Dict[str, Any], new_stdout: Optional[Dict[str, Any]],
                          payload: Optional[Dict[str, Any]]) -> Optional[str]:
    """None when the row belongs to the norm_ppf sign fix (or the removal of the invented-law outputs)
    and the whole new document is the oracle run with those outputs replaced by null + status."""
    key = row["key"]
    if new_stdout is None or payload is None:
        return f"{key}: documented change needs the re-blessed document and the case payload to be verified"
    import physics_audit_changes as audit  # noqa: E402 (python/tools module)
    removal_row = bool(_UQ_REMOVED_ROW.fullmatch(key))
    audit_row = any(re.fullmatch(p, key) for p in audit.UQ_AUDIT_ROW_PATTERNS)
    if row["kind"] not in ("numeric", "changed") and not ((removal_row or audit_row)
                                                          and row["kind"] in ("added", "removed")):
        return f"{key}: {row['kind']} row is not a value change of the sampler fix"
    try:
        expected = _uq_without_unsupported_outputs(_uq_scipy_oracle_stdout(payload))
    except (ImportError, RuntimeError) as exc:
        return f"{key}: UQ oracle unavailable ({exc})"
    if canonical(new_stdout) != canonical(expected):
        return (f"{key}: re-blessed document differs from the pinned {UQ_ORACLE_REVISION} solver run with "
                "scipy.special.ndtri as inverse normal, the Joe-Kuo direction numbers, the invented-law outputs "
                "replaced by null + status and the EUQ-11 reliability block")
    # The row itself must be the document's leaf (a forged row next to a valid document is refused).
    try:
        value = audit.leaf(new_stdout, key)
    except KeyError:
        return None if row["kind"] == "removed" else f"{key}: row is not in the re-blessed document"
    if row["kind"] == "removed":
        return f"{key}: removed row still present in the re-blessed document"
    if value != row["new"] or type(value) is not type(row["new"]):
        return f"{key}: row new value {row['new']!r} is not the document's {value!r}"
    return None


def documented_change_violation(solver: str, row: Dict[str, Any],
                                new_stdout: Optional[Dict[str, Any]],
                                payload: Optional[Dict[str, Any]] = None,
                                rows: Optional[List[Dict[str, Any]]] = None,
                                old_stdout: Optional[Dict[str, Any]] = None,
                                pourbaix_context: Any = None) -> Optional[str]:
    """None when ``row`` is exactly the documented change (EXPECTED_DOCUMENTED_VALUE_CHANGES).

    pourbaix_solver: see pourbaix_documented_change_violation (needs ``old_stdout``, the
    d33b6f5 golden's stdout; ``pourbaix_context`` caches the oracle recomputation).

    kinetics_ttt_cct_solver predictedHardness_HV: the old value must be the old formula
    round(10.5 * HRC + 40) of the row's (unchanged) HRC, and the new value must be the
    ASTM E140 Table 1 value (hardness_conversion_e140) when the alloy type is a steel, or
    null with the matching status otherwise. The status key may only be added, with the
    status that belongs to that HV. Nothing is accepted by tolerance.

    stochastic_uq_mmpds_solver (norm_ppf sign fix): a row matching the listed patterns is
    accepted only if the complete re-blessed stdout equals a fresh run, for the
    case ``payload``, of the PINNED pre-fix solver blob (UQ_ORACLE_REVISION) with
    scipy.special.ndtri as the inverse normal (_uq_sampler_violation); the working-tree solver
    is never used as its own oracle.
    """
    key = row["key"]
    if solver == "pourbaix_solver":
        return pourbaix_documented_change_violation(row, old_stdout, new_stdout, pourbaix_context)
    if solver == "tafel_corrosion_rate_solver":
        import physics_audit_changes as audit  # noqa: E402 (python/tools module)
        return audit.tafel_row_problem(row, new_stdout)
    if solver == "kinetics_ttt_cct_solver" and not _KINETICS_HV_ROW.fullmatch(key):
        # Engine-fix lane fx-kinetics changes (steel-only model, placeholders, TTT floor, LSW units).
        if new_stdout is None:
            return f"{key}: documented change needs the re-blessed document to be verified"
        import kinetics_documented_changes as kdc  # noqa: E402 (tools/ module)
        return kdc.row_violation(row, new_stdout)
    if solver == "stochastic_uq_mmpds_solver":
        return _uq_sampler_violation(row, new_stdout, payload)
    if solver == "lpbf_fatigue_fracture":
        # Physics audit KS-2 / KS-3: independent oracle in tools/fatigue_documented_changes.py.
        import fatigue_documented_changes as fdc  # noqa: E402 (tools/ module)
        return fdc.row_violation(row, new_stdout, payload, old_stdout)
    if solver != "kinetics_ttt_cct_solver" or not _KINETICS_HV_ROW.fullmatch(key):
        return f"{key}: no documented-change check for this row"
    if new_stdout is None:
        return f"{key}: documented change needs the re-blessed document to be verified"
    if str(PYTHON_DIR) not in sys.path:
        sys.path.insert(0, str(PYTHON_DIR))
    import hardness_conversion_e140 as e140  # noqa: E402 (python/ module)
    match = _KINETICS_HV_ROW.fullmatch(key)
    try:
        entry = new_stdout["cctContinuousCoolingMap"][int(match.group(1))]
        hrc = entry["predictedHardness_HRC"]
        alloy_type = new_stdout["alloyMetadata"]["type"]
    except (KeyError, IndexError, TypeError):
        return f"{key}: re-blessed document lacks the row, its HRC or the alloy type"
    if hrc is None and "alloy" in new_stdout:
        # Lane kin-li: the Li (1998) model computes no HRC (steels) and non-steels are unavailable; the old HV
        # must be the old formula of an old lookup band, the new HV null with the alloy-class status.
        import kinetics_documented_changes as kdc  # noqa: E402 (tools/ module)
        try:
            return kdc.hv_violation(row, new_stdout)
        except Exception as exc:  # noqa: BLE001 - any malformed document is a violation, never accepted
            return f"{key}: cannot verify against the re-blessed document ({exc!r})"
    # Classified from the registry descriptor "type", independently of the solver's id set.
    if "Steel" in alloy_type:
        expected_hv, expected_status = e140.hrc_to_hv_non_austenitic_steel(hrc)
    else:
        expected_hv, expected_status = None, e140.STATUS_UNAVAILABLE_ALLOY_CLASS
    if match.group(2):  # the status key
        if row["kind"] != "added" or row["new"] != expected_status:
            return f"{key}: expected an added status {expected_status!r}, got {row['kind']} {row['new']!r}"
        return None
    if row["kind"] not in ("numeric", "changed"):
        return f"{key}: {row['kind']} row is not the documented HV change"
    if hrc is None:
        # fx-kinetics: a non-steel row's HRC is now null too (steel-only model); the old HRC is not in
        # this row, so the old HV must be the old formula applied to one of the old lookup bands.
        if "Steel" in alloy_type:
            return f"{key}: a steel row has no HRC"
        allowed = {round(h * 10.5 + 40.0, 0) for h in _OLD_KINETICS_HRC_BANDS}
        if type(row["old"]) is not float or row["old"] not in allowed:
            return f"{key}: old {row['old']!r} is not round(10.5 * HRC + 40) of an old HRC band {sorted(allowed)!r}"
    else:
        old_formula = round(hrc * 10.5 + 40.0, 0)
        if type(row["old"]) is not float or row["old"] != old_formula:
            return f"{key}: old {row['old']!r} is not round(10.5 * {hrc} + 40) = {old_formula!r}"
    if type(row["new"]) is not type(expected_hv) or row["new"] != expected_hv:
        return f"{key}: new {row['new']!r} is not the E140 value {expected_hv!r} ({expected_status})"
    if entry.get("predictedHardness_HV_status") != expected_status:
        return f"{key}: status {entry.get('predictedHardness_HV_status')!r} != {expected_status!r}"
    return None


def step_b_violations(solver: str, rows: List[Dict[str, Any]],
                      new_stdout: Optional[Dict[str, Any]] = None,
                      payload: Optional[Dict[str, Any]] = None,
                      old_stdout: Optional[Dict[str, Any]] = None) -> List[str]:
    """Rows a step_b re-bless must not contain (empty list = acceptable drift).

    ``new_stdout`` is the re-blessed stdout (and ``payload`` the CASES payload, key order
    included) and ``old_stdout`` the d33b6f5 golden's stdout; they are needed only to verify
    rows listed in EXPECTED_DOCUMENTED_VALUE_CHANGES (pourbaix needs both stdouts; without
    them those rows are violations).
    """
    bound = step_b_max_rel(solver, rows)
    out = []
    pourbaix_context = None
    for r in rows:
        leaf = r["key"].rsplit(".", 1)[-1].split("[", 1)[0]
        if _is_documented_change_row(solver, r["key"], r["kind"]):
            if (solver == "pourbaix_solver" and pourbaix_context is None
                    and old_stdout is not None and new_stdout is not None):
                import pourbaix_golden_check  # noqa: E402 (python/tools module)
                pourbaix_context = pourbaix_golden_check.Context(old_stdout, new_stdout)
            problem = documented_change_violation(solver, r, new_stdout, payload, rows, old_stdout,
                                                  pourbaix_context)
            if problem:
                out.append(problem)
        elif r["kind"] == "numeric":
            if r.get("rel") is not None and abs(r["rel"]) > bound:
                out.append(f"{r['key']}: |rel| {abs(r['rel']):.3g} > {bound:.3g}")
        elif r["kind"] == "removed" and leaf in STEP_B_ALLOWED_REMOVED_KEYS.get(solver, frozenset()):
            continue
        elif not (r["kind"] == "changed"
                  and leaf in (STEP_B_ALLOWED_STRING_KEYS | STEP_B_ALLOWED_STRING_KEYS_BY_SOLVER.get(solver, frozenset()))
                  and isinstance(r["old"], str) and isinstance(r["new"], str)):
            out.append(f"{r['key']}: {r['kind']} row is not a value drift")
    return out


def step_b_document_violations(solver: str, new_stdout: Optional[Dict[str, Any]]) -> List[str]:
    """Whole-document checks of a re-blessed stdout (kinetics: LSW oracle, steel-only consistency)."""
    if solver != "kinetics_ttt_cct_solver" or not isinstance(new_stdout, dict):
        return []
    import kinetics_documented_changes as kdc  # noqa: E402 (tools/ module)
    return kdc.document_violations(new_stdout)


def step_b_excluded_cases() -> set:
    """Cases that are behaviour changes, never value re-blesses."""
    excluded = set()
    for module in ("_t2a_cases", "_t2b_cases"):
        cases = globals().get(module)
        if cases is not None:
            excluded |= set(getattr(cases, "EXPECTED_BEHAVIOUR_CHANGES", {}))
            excluded |= set(getattr(cases, "EXPECTED_SUCCESS_FLAG_CHANGES", ()))
            excluded |= set(getattr(cases, "EXPECTED_UNAVAILABLE_CHANGES", {}))
    # pourbaix al_hot_chloride / ni_acid_points: 80 C and 60 C requests now give the
    # TEMPERATURE_UNSUPPORTED envelope (WP-E, 25 C engine); old goldens stay as the record.
    excluded |= {("tafel_corrosion_rate_solver", "edge_unknown_alloy_zero_icorr"),
                 ("pourbaix_solver", "edge_unknown_element_badvals"),
                 ("pourbaix_solver", "al_hot_chloride"),
                 ("pourbaix_solver", "ni_acid_points")}
    return excluded


def _write(path: Path, doc: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True, ensure_ascii=False)
        fh.write("\n")


def _binding(solver: str, label: str, from_revision: Optional[str]) -> Tuple[Dict[str, Any], bytes]:
    """Return the immutable-source metadata for a capture labelled ``label``.

    Refuses (CaptureRefused) unless the solver bytes that will run are identical to
    the ``label`` blob, so a re-capture can never relabel other code as ``label``.
    """
    source = solver_bytes(solver, from_revision)
    digest = normalised_sha256(source)
    try:
        label_digest = normalised_sha256(solver_bytes(solver, label))
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CaptureRefused(f"{solver}: cannot read python/{solver}.py at {label!r} from git ({exc})")
    if digest != label_digest:
        where = f"git {from_revision}" if from_revision else "the working tree"
        raise CaptureRefused(
            f"{solver}: the solver in {where} (sha256 {digest[:12]}) is not the {label} blob "
            f"(sha256 {label_digest[:12]}); refusing to label its output as {label}. "
            f"Use --from-revision {label} to capture from the immutable blob.")
    meta = {
        "baseRevision": label,
        "solverFile": f"python/{solver}.py",
        "solverSha256": digest,
        "solverSha256Normalization": "CRLF->LF (git blob form)",
        "solverSource": f"git:{from_revision}" if from_revision else "worktree",
        "gitHead": git_head(),
    }
    return meta, source


def capture(solver: str, case: str, force: bool, label: str = BASE_REVISION,
            from_revision: Optional[str] = None, cases: Optional[Dict[str, Dict[str, Any]]] = None,
            path: Optional[Path] = None) -> str:
    # ``cases``/``path`` default to the Phase 6a set; other case sets (the phase6b
    # block below) pass their own table, label and golden path.
    path = golden_path(solver, case) if path is None else path
    if path.exists() and not force:
        return f"skip {solver}/{case} (exists; use --force to re-bless)"
    meta, source = _binding(solver, label, from_revision)
    payload = (CASES if cases is None else cases)[solver][case]
    with tempfile.TemporaryDirectory() as tmp:
        script = None
        if from_revision is not None:
            script = Path(tmp) / f"{solver}.py"
            script.write_bytes(source)
        hidden = GOLDEN_HIDDEN_MODULES if script is not None and solver not in MODULE_DRIVERS else ()
        result = run_solver(solver, payload, script=script, hide_modules=hidden)
    doc = dict(meta)
    doc.update({
        "schema": GOLDEN_SCHEMA,
        "solver": solver,
        "case": case,
        "invocation": f"python -B {solver}.py < input (cwd python/)",
        "volatileKeysStripped": sorted(VOLATILE_KEYS),
        "input": payload,
        "exitCode": result["exitCode"],
        "stdout": result["stdout"],
    })
    _write(path, doc)
    return f"wrote {solver}/{case} exit={result['exitCode']} sha256={meta['solverSha256'][:12]}"


SOURCE_TABLES_FILE = "_source_tables.json"
_TABLE_TARGETS = {
    "tafel_corrosion_rate_solver": ("ALLOY_LIBRARY", lambda t: t),
    "pourbaix_solver": ("POURBAIX_ELEMENT_SYSTEMS", lambda t: {
        el: {"atomicMass": d["atomicMass"], "standardE0_V": d["standardE0_V"], "name": d["name"]}
        for el, d in t.items()}),
}
# Solvers without a __main__: solver -> driver script relative to python/ (see run_solver).
MODULE_DRIVERS: Dict[str, str] = {}

# ---- BEGIN phase6a-t2b block: kinetics / stochastic UQ / fatigue cases ----
sys.path.insert(0, str(Path(__file__).resolve().parent))
import phase6a_t2b_golden_cases as _t2b_cases  # noqa: E402

CASES.update(_t2b_cases.CASES)
_TABLE_TARGETS.update(_t2b_cases.TABLE_TARGETS)
MODULE_DRIVERS.update(_t2b_cases.MODULE_DRIVERS)
# ---- END phase6a-t2b block ----
_load_documented_value_changes()  # tranche-2b kinetics entry + pourbaix (WP-G)


def capture_source_tables(force: bool, label: str = BASE_REVISION,
                          from_revision: Optional[str] = None) -> List[str]:
    """Snapshot the solver-local tables of the ``label`` blob (before migration).

    The structural migration removes these tables from the solvers; the snapshot
    lets the tests keep proving that the registry/constants values are the old ones.
    The module source is executed from the bound bytes (not imported), so it is
    the same code the metadata names.
    """
    out: List[str] = []
    if str(PYTHON_DIR) not in sys.path:
        sys.path.insert(0, str(PYTHON_DIR))
    for solver, (attr, project) in _TABLE_TARGETS.items():
        path = GOLDEN_DIR / solver / SOURCE_TABLES_FILE
        if path.exists() and not force:
            out.append(f"skip {solver}/{SOURCE_TABLES_FILE} (exists)")
            continue
        meta, source = _binding(solver, label, from_revision)
        # A registered module object: @dataclass resolves its class module via sys.modules.
        module = types.ModuleType(f"_phase6a_snapshot_{solver}")
        sys.modules[module.__name__] = module
        try:
            exec(compile(source, f"{solver}.py@{label}", "exec"), module.__dict__)
        finally:
            sys.modules.pop(module.__name__, None)
        namespace: Dict[str, Any] = module.__dict__
        table = namespace.get(attr)
        if table is None:
            out.append(f"skip {solver}/{SOURCE_TABLES_FILE} ({attr} missing)")
            continue
        doc = dict(meta)
        doc.update({"schema": GOLDEN_SCHEMA, "solver": solver, "table": attr, "values": project(table)})
        _write(path, doc)
        out.append(f"wrote {solver}/{SOURCE_TABLES_FILE}")
    return out


# ---- BEGIN Phase 6a tranche 2a (calphad, battery EIS) ----
# Cases and source-table snapshots live in tools/phase6a_cases_t2a.py. These three
# solvers are byte-identical at d33b6f5 and 7f3f803, so the BASE_REVISION binding
# above applies to them unchanged.
import phase6a_cases_t2a as _t2a_cases  # noqa: E402

CASES.update(_t2a_cases.CASES)
VOLATILE_KEYS = VOLATILE_KEYS | _t2a_cases.EXTRA_VOLATILE_KEYS
_t2a_base_capture_source_tables = capture_source_tables


def capture_source_tables(force: bool, label: str = BASE_REVISION,  # noqa: F811
                          from_revision: Optional[str] = None) -> List[str]:
    out = _t2a_base_capture_source_tables(force, label, from_revision)
    return out + _t2a_cases.capture_source_tables(sys.modules[__name__], force, label, from_revision)
# ---- END Phase 6a tranche 2a ----


# ---- BEGIN phase6b-vector block: cnls / xrd cases (base faa6684) ----
# The Phase 6b NumPy/SciPy rewrite of these three solvers is compared against goldens
# captured from the faa6684 blobs (not the d33b6f5 label above). They live in
# golden/phase6b/ and in their own case table, so the Phase 6a bit-exact tests never
# iterate them; test_phase6b_vector_parity.py applies the stated tolerances.
# Capture: python -B tools/capture_phase6a_golden.py --phase6b-vector [--force]
#          [--solver NAME] [--from-revision faa6684]
import phase6b_vector_golden_cases as _p6b_vector  # noqa: E402

PHASE6B_VECTOR_DIR = PYTHON_DIR / "golden" / _p6b_vector.GOLDEN_SUBDIR


def phase6b_vector_golden_path(solver: str, case: str) -> Path:
    return PHASE6B_VECTOR_DIR / solver / f"{case}.json"


def capture_phase6b_vector(solver: str, case: str, force: bool,
                           from_revision: Optional[str] = None) -> str:
    return capture(solver, case, force, label=_p6b_vector.BASE_REVISION, from_revision=from_revision,
                   cases=_p6b_vector.CASES, path=phase6b_vector_golden_path(solver, case))
# ---- END phase6b-vector block ----


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--force", action="store_true", help="overwrite existing golden files")
    parser.add_argument("--solver", choices=sorted(set(CASES) | set(_p6b_vector.CASES)),
                        help="capture one solver only")
    parser.add_argument("--from-revision", metavar="REV",
                        help=f"run the solver blob from git REV instead of the working tree "
                             f"(it must equal the {BASE_REVISION} blob; "
                             f"{_p6b_vector.BASE_REVISION} with --phase6b-vector)")
    parser.add_argument("--phase6b-vector", action="store_true",
                        help=f"capture the phase6b vectorisation cases (bound to {_p6b_vector.BASE_REVISION})")
    args = parser.parse_args(argv)
    if args.phase6b_vector:
        try:
            for solver, cases in _p6b_vector.CASES.items():
                if args.solver and solver != args.solver:
                    continue
                for case in cases:
                    print(capture_phase6b_vector(solver, case, args.force, from_revision=args.from_revision))
        except CaptureRefused as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 2
        return 0
    try:
        for solver, case in iter_golden_cases():
            if args.solver and solver != args.solver:
                continue
            print(capture(solver, case, args.force, from_revision=args.from_revision))
        if not args.solver:
            for line in capture_source_tables(args.force, from_revision=args.from_revision):
                print(line)
    except CaptureRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
