#!/usr/bin/env python3
"""
Phase 6b vectorisation lane: before/after timing of cnls_fitting_solver,
xrd_peak_deconvolution and dft_property_calculator.

"before" is the faa6684 blob (git show, executed from a temp module), "after" is
the working tree. Two measurements per case, each the median of --repeat runs:
  * kernel: the solver function called in-process (imports already done);
  * spawn:  the app's ad-hoc spawn path, ``python -B <solver>.py`` with the JSON
            payload on stdin (interpreter start + imports + solve + JSON).
Besides the golden payloads a few larger synthetic payloads show how the
vectorised kernels scale with the number of frequencies / parameters.

Usage (from python/):  python -B tools/phase6b_vector_benchmark.py [--repeat 5] [--json out.json]
Timings are machine dependent; the report prints the machine it ran on.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path
from typing import Any, Callable, Dict, List

PYTHON_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PYTHON_DIR))
sys.path.insert(0, str(PYTHON_DIR / "tools"))

import capture_phase6a_golden as golden  # noqa: E402
import phase6b_vector_golden_cases as cases  # noqa: E402


def load_blob_module(solver: str, revision: str = cases.BASE_REVISION) -> types.ModuleType:
    source = golden.solver_bytes(solver, revision)
    module = types.ModuleType(f"_phase6b_before_{solver}")
    module.__file__ = str(PYTHON_DIR / f"{solver}.py")
    sys.modules[module.__name__] = module
    exec(compile(source, f"{solver}.py@{revision}", "exec"), module.__dict__)
    return module


def dispatch(module: types.ModuleType, solver: str, data: Dict[str, Any]) -> Any:
    """In-process equivalent of the solver's stdin dispatch for the benchmarked actions."""
    if solver == "cnls_fitting_solver":
        topology = data.get("topology", data.get("topologyId", "standard_randles"))
        if data.get("action") == "validate_dataset":
            points = data.get("points", [])
            return {"linKK": module.perform_lin_kk_stationarity_test(points),
                    "inductance": module.analyze_and_deembed_high_freq_inductance(points),
                    "cpeCapacitances": module.calculate_cpe_effective_capacitances(
                        data.get("parameters", []), topology, float(data.get("electrodeAreaCm2", 1.0)))}
        return module.run_cnls_fit(topology, data.get("points", []), data.get("parameters", []),
                                   data.get("weighting", "modulus"), int(data.get("maxIterations", 80)))
    if solver == "xrd_peak_deconvolution":
        return module.deconvolve_peak_roi(
            data.get("points", []), data.get("center", 43.68), data.get("intensity", 4000.0),
            data.get("fwhm", 0.25), data.get("profileType", "pseudo-voigt"), data.get("eta", 0.5),
            data.get("pearsonM", 2.0), data.get("enableKa2", True), data.get("ka2Ratio", 0.5))
    if solver == "dft_property_calculator":
        return module.calculate_dft_properties(data)
    raise KeyError(solver)


def median_seconds(fn: Callable[[], Any], repeat: int) -> float:
    samples = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - t0)
    return statistics.median(samples)


def spawn_seconds(solver: str, payload: Any, repeat: int, script: Path = None) -> float:
    return median_seconds(lambda: golden.run_solver(solver, payload, script=script), repeat)


def _large_payloads() -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Larger synthetic payloads (scaling only; not goldens)."""
    two_rc = cases.CASES["cnls_fitting_solver"]["custom_two_rc_modulus_fit"]
    points = cases._eis_points(cases._two_rc, 1e6, 1e-3, 40, 0.0015)  # 361 frequencies
    return {
        "cnls_fitting_solver": {
            "scale_custom_two_rc_F361_P6": dict(two_rc, points=points),
            "scale_linkk_F361": {"action": "validate_dataset", "topology": "standard_randles",
                                 "electrodeAreaCm2": 1.0, "points": points},
        },
        "xrd_peak_deconvolution": {
            "scale_pv_ka2_N651": dict(cases.CASES["xrd_peak_deconvolution"]["pv_ka2_cu111"],
                                      points=cases._xrd_points(40.0, cases._pv, 43.30, 4000.0, 0.20, 0.4,
                                                               210.0, 5.0, n=651)),
        },
    }


def run(repeat: int) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "machine": {"platform": platform.platform(), "processor": platform.processor(),
                    "cpuCount": os.cpu_count(), "python": sys.version.split()[0],
                    "numpy": __import__("numpy").__version__, "scipy": __import__("scipy").__version__},
        "repeat": repeat, "statistic": "median", "rows": []}
    large = _large_payloads()
    with tempfile.TemporaryDirectory() as tmp:
        for solver in cases.SOLVERS:
            before_mod = load_blob_module(solver)
            after_mod = __import__(solver)
            blob = Path(tmp) / f"{solver}.py"
            blob.write_bytes(golden.solver_bytes(solver, cases.BASE_REVISION))
            table = dict(cases.CASES[solver])
            table.update(large.get(solver, {}))
            for case, payload in table.items():
                if solver == "xrd_peak_deconvolution" and not payload.get("points"):
                    continue
                row = {"solver": solver, "case": case}
                row["kernelBeforeMs"] = 1e3 * median_seconds(lambda: dispatch(before_mod, solver, payload), repeat)
                row["kernelAfterMs"] = 1e3 * median_seconds(lambda: dispatch(after_mod, solver, payload), repeat)
                row["spawnBeforeMs"] = 1e3 * spawn_seconds(solver, payload, repeat, script=blob)
                row["spawnAfterMs"] = 1e3 * spawn_seconds(solver, payload, repeat)
                row["kernelSpeedup"] = row["kernelBeforeMs"] / row["kernelAfterMs"]
                row["spawnSpeedup"] = row["spawnBeforeMs"] / row["spawnAfterMs"]
                report["rows"].append(row)
    return report


def render(report: Dict[str, Any]) -> str:
    m = report["machine"]
    lines = [f"machine: {m['platform']} | {m['processor']} | {m['cpuCount']} logical CPUs | "
             f"Python {m['python']} numpy {m['numpy']} scipy {m['scipy']} | median of {report['repeat']}",
             "| solver | case | kernel before ms | kernel after ms | kernel x | spawn before ms | spawn after ms | spawn x |",
             "|---|---|---|---|---|---|---|---|"]
    for r in report["rows"]:
        lines.append(f"| {r['solver']} | {r['case']} | {r['kernelBeforeMs']:.3f} | {r['kernelAfterMs']:.3f} | "
                     f"{r['kernelSpeedup']:.2f} | {r['spawnBeforeMs']:.0f} | {r['spawnAfterMs']:.0f} | "
                     f"{r['spawnSpeedup']:.2f} |")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--json", type=Path, help="also write the raw report as JSON")
    args = parser.parse_args(argv)
    report = run(args.repeat)
    print(render(report))
    if args.json:
        args.json.write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
