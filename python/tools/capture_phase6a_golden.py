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
    "_f = os.environ['PHASE6A_BLOB_AS_FILE']\n"
    "sys.argv = [_f]\n"
    "with open(os.environ['PHASE6A_BLOB_SCRIPT'], 'rb') as _h:\n"
    "    _code = compile(_h.read(), _f, 'exec')\n"
    "exec(_code, {'__name__': '__main__', '__file__': _f, '__builtins__': __builtins__})\n"
)


def run_solver(solver: str, payload: Any, python: str = sys.executable, timeout: float = 180.0,
               script: Optional[Path] = None) -> Dict[str, Any]:
    """Run ``<solver>.py`` like the app's ad-hoc spawn; return exit code and parsed stdout.

    ``script`` runs another copy of the solver (e.g. a git blob extracted to a temp
    dir) with the same cwd, and python/ on PYTHONPATH for its local imports.
    """
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
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
STEP_B_DEFAULT_MAX_REL = 1e-2
# tafel: the drift follows the equivalent-weight change (EW rel r): rates and losses
# move by r, and remaining wall/pitting thickness (thickness - loss) amplifies it by
# loss/remaining, which stays below 3 in the golden cases; plus 1e-2 for last-digit
# rounding of small printed values. Without an EW row the default bound applies.
STEP_B_TAFEL_EW_AMPLIFICATION = 3.0


def step_b_max_rel(solver: str, rows: List[Dict[str, Any]]) -> float:
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


def _documented_change_patterns(solver: str) -> Dict[str, str]:
    if not EXPECTED_DOCUMENTED_VALUE_CHANGES:
        _load_documented_value_changes()
    return dict(EXPECTED_DOCUMENTED_VALUE_CHANGES.get(solver, {}))


def _is_documented_change_row(solver: str, key: str) -> bool:
    return any(re.fullmatch(p, key) for p in _documented_change_patterns(solver))


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

        original = module.norm_ppf
        module.norm_ppf = oracle
        try:
            result = module.solve_stochastic_uq(copy.deepcopy(payload))
        finally:
            module.norm_ppf = original
        _UQ_ORACLE_CACHE[cache_key] = strip_volatile(json.loads(json.dumps(result)))
    return _UQ_ORACLE_CACHE[cache_key]


def _uq_sampler_violation(row: Dict[str, Any], new_stdout: Optional[Dict[str, Any]],
                          payload: Optional[Dict[str, Any]]) -> Optional[str]:
    """None when the row belongs to the norm_ppf sign fix and the whole new document is the oracle run."""
    key = row["key"]
    if new_stdout is None or payload is None:
        return f"{key}: documented change needs the re-blessed document and the case payload to be verified"
    if row["kind"] not in ("numeric", "changed"):
        return f"{key}: {row['kind']} row is not a value change of the sampler fix"
    try:
        expected = _uq_scipy_oracle_stdout(payload)
    except (ImportError, RuntimeError) as exc:
        return f"{key}: UQ oracle unavailable ({exc})"
    if canonical(new_stdout) != canonical(expected):
        return (f"{key}: re-blessed document differs from the pinned {UQ_ORACLE_REVISION} solver run with "
                "scipy.special.ndtri as inverse normal")
    return None


_ICME_OLD_ENGINE = ("MetalliX ICME Multi-Scale HPC Pipeline "
                    "(DFT -> CALPHAD -> Kinetics -> Microstructure -> Macro FEA)")
_ICME_OLD_VERDICT = {
    "STRUCTURALLY SAFE (Passed Yield & Creep Criteria)":
        "YIELD CHECK PASSED (yield strength vs fixed catalogue stress only; no creep, fatigue or fracture check)",
    "WARNING: INSUFFICIENT SAFETY MARGIN (Risk of Plastic Yielding)":
        "WARNING: INSUFFICIENT YIELD SAFETY MARGIN (Risk of Plastic Yielding; yield-only check)",
}
_ICME_OLD_NDI = frozenset({
    "Detectable with Standard X-Ray / UT (Flaw > 1.0mm)",
    "High-Resolution Eddy Current / Computed Tomography Required (Sub-mm Flaw)",
})
_ICME_NEW_NDI = "Unavailable (no critical flaw size without K_Ic)"
# Fixed texts of the illustrative ICME engine, pinned literally (independent of the solver constants):
# a re-bless may only record exactly these (fx-icme fix round, review S2).
_ICME_EXACT_TEXT = {
    'modelStatusNote':
        'Illustrative closed-form estimate; it is not calibrated to measurements or validated. '
        "Every scale is a formula on hard-coded tabulated constants. The 'DFT' scale is a table of "
        'elastic constants (C11, C12, C44), lattice parameters and Taylor factors with a '
        "Peierls-Nabarro friction estimate; no DFT is run. The 'CALPHAD' scale is a table of "
        'atomic radii, shear moduli and solid-solution coefficients (k * sqrt(wt%)); no '
        'thermodynamic calculation is run, and the size and modulus misfit values are reported but '
        'do not enter the strength. The microstructure scale uses empirical SDAS, Hall-Petch, '
        'Taylor and LSW/Orowan relations. The stress-strain curve and the Johnson-Cook and '
        'CAE-card parameters come from a schematic hardening law with a placeholder '
        "strain-hardening exponent n. The 'macro FEA' scale is a yield-only comparison of Rp0.2 "
        'with a fixed catalogue stress, not a finite-element analysis. The model is '
        'room-temperature only: serviceTemp_C does not change any value and strainRate_s_inv only '
        'appears in a card line. Ultimate tensile strength and fracture toughness (K_Ic, critical '
        'flaw size, plastic zone radius) are unavailable; see the status fields next to them.',
    'engine':
        'MetalliX ICME Multi-Scale Closed-Form Estimator (illustrative; tabulated constants, no '
        'DFT/CALPHAD/FEA run)',
    'scale3_continuumPlasticity.mechanicalProperties.ultimateTensileStrength_UTS_status':
        'unavailable: n is a placeholder correlation of the yield strength and the Hollomon K was '
        'set so that the engineering UTS equals Rp0.2, so the Considere relation UTS = K*(n/e)^n '
        'would only return the yield strength; an independent measured n and K are required',
    'scale3_continuumPlasticity.mechanicalProperties.fractureToughness_K1c_status':
        'unavailable: the former estimate sqrt(2/3*E*sigma_y*eps_f*n^2) has the unit MPa, not '
        'MPa*sqrt(m), and no dimensionally valid, cited toughness relation applies to this model; '
        'supply a measured K_Ic',
    'scale4_macroComponentFEA.structuralVerdictBasis':
        'Yield-only check at room temperature: Rp0.2 divided by the catalogue appliedStress_MPa '
        'against requiredSafetyFactor. No creep, fatigue, fracture, buckling or '
        'service-temperature check exists.',
    'scale4_macroComponentFEA.lefmDamageTolerance.status':
        'unavailable: the critical flaw size and the plastic zone radius need a fracture toughness '
        'K_Ic, which this model does not provide',
    'modelParts[0]':
        'scale0_dftAtomistic: tabulated elastic constants and Peierls-Nabarro estimate (no DFT)',
    'modelParts[1]':
        'scale1_calphadSoluteMisfit: tabulated radii, moduli and k*sqrt(wt%) coefficients (no '
        'CALPHAD)',
    'modelParts[2]':
        'scale2_microstructureKinetics: empirical SDAS, Hall-Petch, Taylor and LSW/Orowan relations',
    'modelParts[3]':
        'scale3_continuumPlasticity: Rp0.2 by power-law superposition; schematic curve with '
        'placeholder n',
    'modelParts[4]':
        'scale4_macroComponentFEA: yield-only check against a fixed catalogue stress (no FEA)',
    'modelParts[5]':
        'caeExportCards: uncalibrated illustrative cards',
}
_ICME_DOCUMENTED_KEYS = frozenset(_ICME_EXACT_TEXT) | frozenset({
    'modelStatus',
    'scale3_continuumPlasticity.mechanicalProperties.ultimateTensileStrength_UTS_MPa',
    'scale3_continuumPlasticity.mechanicalProperties.fractureToughness_K1c_MPa_sqrt_m',
    'scale4_macroComponentFEA.structuralVerdict',
    'scale4_macroComponentFEA.lefmDamageTolerance.criticalFlawSize_ac_mm',
    'scale4_macroComponentFEA.lefmDamageTolerance.plasticZoneRadius_rp_mm',
    'scale4_macroComponentFEA.lefmDamageTolerance.inspectionNDICapability',
    'caeExportCards.abaqus',
    'caeExportCards.lsDyna',
    'caeExportCards.ansys',
})

_ICME_MECH = "scale3_continuumPlasticity.mechanicalProperties."
_ICME_LEFM = "scale4_macroComponentFEA.lefmDamageTolerance."
_ICME_CARD_ROW = re.compile(r"caeExportCards\.(abaqus|lsDyna|ansys)")
_ICME_CARD_LINE = {  # card -> (old header prefix, new header prefix); lines 0 and 2.. are unchanged
    "abaqus": ("** MetalliX Multi-Scale ICME Calibrated Card for ",
               "** MetalliX Multi-Scale ICME ILLUSTRATIVE Card (uncalibrated, not validated) for "),
}


def _icme_documented_violation(row: Dict[str, Any], rows: Optional[List[Dict[str, Any]]],
                               new_stdout: Optional[Dict[str, Any]]) -> Optional[str]:
    """None when ``row`` is exactly one of the documented icme changes (fx-icme, lane 9).

    UTS: the old value must be the old yield strength (the UTS == Rp0.2 identity of the K
    choice, to the 0.1 MPa print rounding) and the new value null with an 'unavailable' status.
    K_Ic, a_c and r_p: old numeric, new null. Verdict: the old text maps to the matching
    yield-only text of the same pass/fail decision and never mentions creep. NDI text: one of
    the two old texts -> the fixed unavailable text. Cards: the new card is the old card with
    only the header line replaced / one comment line inserted. New keys are added rows with the
    expected text shape. Nothing is accepted by tolerance except the 0.1 MPa UTS/yield rounding.
    """
    key, kind, old, new = row["key"], row["kind"], row["old"], row["new"]
    is_num = lambda v: type(v) is float  # noqa: E731

    def exact_added():
        if kind != "added" or new != _ICME_EXACT_TEXT.get(key):
            return f"{key}: expected the pinned text as an added row, got {kind} {new!r}"
        return None

    def nulled(label):
        if kind != "changed" or not is_num(old) or new is not None:
            return f"{key}: {label} must change a number to null, got {kind} {old!r} -> {new!r}"
        return None

    if key == "modelStatus":
        return None if (kind == "added" and new == "illustrative") else f"{key}: expected added 'illustrative'"
    if key == "modelStatusNote":
        return exact_added()
    if re.fullmatch(r"modelParts\[\d+\]", key):
        return exact_added()
    if key == "engine":
        if kind != "changed" or old != _ICME_OLD_ENGINE or new != _ICME_EXACT_TEXT["engine"]:
            return f"{key}: not the documented engine relabel ({old!r} -> {new!r})"
        return None
    if key == _ICME_MECH + "ultimateTensileStrength_UTS_MPa":
        problem = nulled("UTS")
        if problem:
            return problem
        if new_stdout is None:
            return f"{key}: documented change needs the re-blessed document to be verified"
        yield_row = next((r for r in (rows or []) if r["key"] == _ICME_MECH + "yieldStrength_Rp02_MPa"), None)
        old_yield = yield_row["old"] if yield_row is not None else new_stdout[
            "scale3_continuumPlasticity"]["mechanicalProperties"]["yieldStrength_Rp02_MPa"]
        if abs(old - old_yield) > 0.11:
            return f"{key}: old UTS {old!r} is not the old yield strength {old_yield!r}"
        return None
    if key == _ICME_MECH + "ultimateTensileStrength_UTS_status":
        return exact_added()
    if key == _ICME_MECH + "fractureToughness_K1c_MPa_sqrt_m":
        return nulled("K_Ic")
    if key == _ICME_MECH + "fractureToughness_K1c_status":
        return exact_added()
    if key == "scale4_macroComponentFEA.structuralVerdict":
        if kind != "changed" or old not in _ICME_OLD_VERDICT or new != _ICME_OLD_VERDICT[old] or "Creep" in new:
            return f"{key}: not the documented verdict relabel ({old!r} -> {new!r})"
        return None
    if key == "scale4_macroComponentFEA.structuralVerdictBasis":
        return exact_added()
    if key in (_ICME_LEFM + "criticalFlawSize_ac_mm", _ICME_LEFM + "plasticZoneRadius_rp_mm"):
        return nulled("LEFM value")
    if key == _ICME_LEFM + "inspectionNDICapability":
        if kind != "changed" or old not in _ICME_OLD_NDI or new != _ICME_NEW_NDI:
            return f"{key}: not the documented NDI text change ({old!r} -> {new!r})"
        return None
    if key == _ICME_LEFM + "status":
        return exact_added()
    card = _ICME_CARD_ROW.fullmatch(key)
    if card:
        if kind != "changed" or not isinstance(old, str) or not isinstance(new, str):
            return f"{key}: card must be a changed text"
        o, n = old.split("\n"), new.split("\n")
        name = card.group(1)
        if name == "abaqus":
            prefix_old, prefix_new = _ICME_CARD_LINE["abaqus"]
            if len(o) != len(n) or o[1].startswith(prefix_old) is False or n[1] != prefix_new + o[1][len(prefix_old):] \
                    or o[0] != n[0] or o[2:] != n[2:]:
                return f"{key}: abaqus card differs from the old card by more than the header relabel"
            return None
        marker = "$ ILLUSTRATIVE estimate (uncalibrated, not validated)" if name == "lsDyna" else \
            "! ILLUSTRATIVE estimate (uncalibrated, not validated)"
        if n != o[:1] + [marker] + o[1:]:
            return f"{key}: {name} card differs from the old card by more than one inserted comment line"
        return None
    return f"{key}: no documented-change check for this row"


def _icme_missing_rule_violations(rows: List[Dict[str, Any]],
                                  new_stdout: Optional[Dict[str, Any]]) -> List[str]:
    """Every documented icme rule must occur in the drift table, and the unavailable values must
    be null in the re-blessed document (so reverting UTS/K_Ic to the old value cannot re-bless)."""
    present = {r["key"] for r in rows}
    out = [f"{key}: documented icme change missing from the drift table"
           for key in sorted(_ICME_DOCUMENTED_KEYS - present)]
    if new_stdout is None:
        return out + ["icme: the re-blessed document is needed to verify the unavailable values"]
    try:
        mech = new_stdout["scale3_continuumPlasticity"]["mechanicalProperties"]
        lefm = new_stdout["scale4_macroComponentFEA"]["lefmDamageTolerance"]
        values = {"ultimateTensileStrength_UTS_MPa": mech["ultimateTensileStrength_UTS_MPa"],
                  "fractureToughness_K1c_MPa_sqrt_m": mech["fractureToughness_K1c_MPa_sqrt_m"],
                  "criticalFlawSize_ac_mm": lefm["criticalFlawSize_ac_mm"],
                  "plasticZoneRadius_rp_mm": lefm["plasticZoneRadius_rp_mm"]}
    except (KeyError, TypeError):
        return out + ["icme: re-blessed document lacks the unavailable-value keys"]
    out += [f"{name}: must be null (unavailable) in the re-blessed document, got {value!r}"
            for name, value in values.items() if value is not None]
    return out


def documented_change_violation(solver: str, row: Dict[str, Any],
                                new_stdout: Optional[Dict[str, Any]],
                                payload: Optional[Dict[str, Any]] = None,
                                rows: Optional[List[Dict[str, Any]]] = None,
                                old_stdout: Optional[Dict[str, Any]] = None,
                                pourbaix_context: Any = None) -> Optional[str]:
    """None when ``row`` is exactly the documented change (EXPECTED_DOCUMENTED_VALUE_CHANGES).

    icme_multiscale_pipeline_solver rows are checked by _icme_documented_violation (``rows`` is
    the whole drift table, needed to read the old yield strength).
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
    if solver == "stochastic_uq_mmpds_solver":
        return _uq_sampler_violation(row, new_stdout, payload)
    if solver == "icme_multiscale_pipeline_solver":
        return _icme_documented_violation(row, rows, new_stdout)
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
        if _is_documented_change_row(solver, r["key"]):
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
        elif not (r["kind"] == "changed" and leaf in STEP_B_ALLOWED_STRING_KEYS
                  and isinstance(r["old"], str) and isinstance(r["new"], str)):
            out.append(f"{r['key']}: {r['kind']} row is not a value drift")
    if solver == "icme_multiscale_pipeline_solver":
        out += _icme_missing_rule_violations(rows, new_stdout)
    return out


def step_b_excluded_cases() -> set:
    """Cases that are behaviour changes, never value re-blesses."""
    excluded = set()
    for module in ("_t2a_cases", "_t2b_cases"):
        cases = globals().get(module)
        if cases is not None:
            excluded |= set(getattr(cases, "EXPECTED_BEHAVIOUR_CHANGES", {}))
            excluded |= set(getattr(cases, "EXPECTED_SUCCESS_FLAG_CHANGES", ()))
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
        result = run_solver(solver, payload, script=script)
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


# ---- BEGIN Phase 6a tranche 2a (calphad, battery EIS, icme) ----
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


# ---- BEGIN phase6b-vector block: cnls / xrd / dft-named cases (base faa6684) ----
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
