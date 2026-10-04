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


def run_solver(solver: str, payload: Any, python: str = sys.executable, timeout: float = 180.0,
               script: Optional[Path] = None) -> Dict[str, Any]:
    """Run ``<solver>.py`` like the app's ad-hoc spawn; return exit code and parsed stdout.

    ``script`` runs another copy of the solver (e.g. a git blob extracted to a temp
    dir) with the same cwd, and python/ on PYTHONPATH for its local imports.
    """
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    target = f"{solver}.py"
    driver = MODULE_DRIVERS.get(solver)
    if driver is not None:
        # Library module: run its driver; the module under test comes first on the path.
        target = driver
        search = ([str(script.parent)] if script is not None else []) + [str(PYTHON_DIR)]
        env["PYTHONPATH"] = os.pathsep.join(search + [env.get("PYTHONPATH", "")])
    elif script is not None:
        target = str(script)
        env["PYTHONPATH"] = str(PYTHON_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [python, "-B", target], input=json.dumps(payload).encode("utf-8"),
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
            from_revision: Optional[str] = None) -> str:
    path = golden_path(solver, case)
    if path.exists() and not force:
        return f"skip {solver}/{case} (exists; use --force to re-bless)"
    meta, source = _binding(solver, label, from_revision)
    payload = CASES[solver][case]
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--force", action="store_true", help="overwrite existing golden files")
    parser.add_argument("--solver", choices=sorted(CASES), help="capture one solver only")
    parser.add_argument("--from-revision", metavar="REV",
                        help=f"run the solver blob from git REV instead of the working tree "
                             f"(it must equal the {BASE_REVISION} blob)")
    args = parser.parse_args(argv)
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
