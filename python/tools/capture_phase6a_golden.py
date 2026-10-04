#!/usr/bin/env python3
"""
Phase 6a golden harness: capture fixed solver payloads as bit-exact baselines.

Each case runs the solver exactly as the app's ad-hoc spawn path does
(server/processOrchestrator.ts executeViaAdHocSpawn): ``python -B <solver>.py``
with the JSON payload on stdin, cwd = python/. The stdout JSON is parsed, volatile
keys are stripped (wall-clock durations, timestamps and the interpreter version)
and the result is written to ``python/golden/phase6a/<solver>/<case>.json``.

None of the captured solvers uses an RNG, so no seed is needed; every case is
deterministic once the volatile keys are removed.

Golden files are only (re)written with ``--force``. Re-blessing after a value
change (design step (b)) must attach the drift report (tools/drift_report.py) to
the commit body.

Usage (from python/):
    python -B tools/capture_phase6a_golden.py [--force] [--solver NAME]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

PYTHON_DIR = Path(__file__).resolve().parent.parent
GOLDEN_DIR = PYTHON_DIR / "golden" / "phase6a"
BASE_REVISION = "d33b6f5"
GOLDEN_SCHEMA = "phase6a-golden-1"

# Keys removed at any depth before comparison. durationMs/computeTimeMs are
# time.perf_counter wall times, timestamp is wall-clock UTC, pythonVersion is the
# interpreter that ran the capture. Nothing else is stripped.
VOLATILE_KEYS = frozenset({"durationMs", "computeTimeMs", "timestamp", "pythonVersion"})

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


def run_solver(solver: str, payload: Any, python: str = sys.executable, timeout: float = 180.0) -> Dict[str, Any]:
    """Run ``<solver>.py`` like the app's ad-hoc spawn; return exit code and parsed stdout."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run(
        [python, "-B", f"{solver}.py"], input=json.dumps(payload).encode("utf-8"),
        capture_output=True, timeout=timeout, env=env, cwd=str(PYTHON_DIR),
    )
    stdout = proc.stdout.decode("utf-8")
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        parsed = {"__unparseableStdout__": stdout}
    return {"exitCode": proc.returncode, "stdout": strip_volatile(parsed),
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


def capture(solver: str, case: str, force: bool) -> str:
    path = golden_path(solver, case)
    if path.exists() and not force:
        return f"skip {solver}/{case} (exists; use --force to re-bless)"
    payload = CASES[solver][case]
    result = run_solver(solver, payload)
    doc = {
        "schema": GOLDEN_SCHEMA,
        "solver": solver,
        "case": case,
        "baseRevision": BASE_REVISION,
        "invocation": f"python -B {solver}.py < input (cwd python/)",
        "volatileKeysStripped": sorted(VOLATILE_KEYS),
        "input": payload,
        "exitCode": result["exitCode"],
        "stdout": result["stdout"],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True, ensure_ascii=False)
        fh.write("\n")
    return f"wrote {solver}/{case} exit={result['exitCode']}"


SOURCE_TABLES_FILE = "_source_tables.json"


def capture_source_tables(force: bool) -> List[str]:
    """Snapshot the solver-local tables at BASE_REVISION (before migration).

    The structural migration removes these tables from the solvers; the snapshot
    lets the tests keep proving that the registry/constants values are the old ones.
    """
    sys.path.insert(0, str(PYTHON_DIR))
    out: List[str] = []
    targets = {
        "tafel_corrosion_rate_solver": ("ALLOY_LIBRARY", lambda t: t),
        "pourbaix_solver": ("POURBAIX_ELEMENT_SYSTEMS", lambda t: {
            el: {"atomicMass": d["atomicMass"], "standardE0_V": d["standardE0_V"], "name": d["name"]}
            for el, d in t.items()}),
    }
    for solver, (attr, project) in targets.items():
        path = GOLDEN_DIR / solver / SOURCE_TABLES_FILE
        if path.exists() and not force:
            out.append(f"skip {solver}/{SOURCE_TABLES_FILE} (exists)")
            continue
        module = __import__(solver)
        table = getattr(module, attr, None)
        if table is None:
            out.append(f"skip {solver}/{SOURCE_TABLES_FILE} ({attr} missing)")
            continue
        doc = {"schema": GOLDEN_SCHEMA, "solver": solver, "baseRevision": BASE_REVISION,
               "table": attr, "values": project(table)}
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(doc, fh, indent=1, sort_keys=True, ensure_ascii=False)
            fh.write("\n")
        out.append(f"wrote {solver}/{SOURCE_TABLES_FILE}")
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--force", action="store_true", help="overwrite existing golden files")
    parser.add_argument("--solver", choices=sorted(CASES), help="capture one solver only")
    args = parser.parse_args(argv)
    for solver, case in iter_golden_cases():
        if args.solver and solver != args.solver:
            continue
        print(capture(solver, case, args.force))
    if not args.solver:
        for line in capture_source_tables(args.force):
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
