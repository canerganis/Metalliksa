"""Bounded numerical convergence study for the CPU LPBF reference solver.

This is numerical evidence for one process vector, never experimental validation.
The acceptance targets below are frozen from DIGITAL_TWIN_MASTER_PLAN_2026-09-21,
section 11, before any result is inspected.
"""

import argparse
import copy
import json
import math
from pathlib import Path

from lpbf_simulation import run
from lpbf_verification import convergence


SCHEMA_VERSION = 1
ACCEPTANCE = {
    "source": "docs/DIGITAL_TWIN_MASTER_PLAN_2026-09-21.md#11",
    "energyRelativeErrorMax": 0.01,
    "finestPairWidthDepthRelativeChangeMax": 0.05,
    "minimumLevelsPerAxis": 3,
    "maximumLevelsPerAxis": 6,
    "trend": "three finest levels must satisfy lpbf_verification.convergence using actual spacings",
}


def _levels(values, name):
    if not isinstance(values, (list, tuple)) or len(values) < ACCEPTANCE["minimumLevelsPerAxis"]:
        raise ValueError(f"{name} requires at least three levels")
    if len(values) > ACCEPTANCE["maximumLevelsPerAxis"]:
        raise ValueError(f"{name} permits at most six levels")
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError(f"{name} levels must be positive finite numbers")
    if any(a <= b for a, b in zip(values, values[1:])):
        raise ValueError(f"{name} levels must be strictly descending, coarse to fine")
    return list(values)


def _case_result(scenario, key, requested):
    payload = copy.deepcopy(scenario)
    payload[key] = requested
    row = {"requested": requested, "status": "failed"}
    try:
        result = run(payload)
        core = result["coreContract"]
        expected_model = ("stationary-enthalpy-conduction-layer-conforming-v1"
                          if payload.get("powderGridPolicy") == "layer-conforming"
                          else "stationary-enthalpy-conduction-v1")
        if (result["effectiveMode"] != "standard"
                or result["solver"]["id"] != "enthalpy-fv-6"
                or core["actualBackend"] != "numpy-reference"
                or core["modelId"] != expected_model
                or core["solverId"] != result["solver"]["id"]):
            raise ValueError("CPU transient reference backend was not executed")
        if (not result["material"].get("materialId")
                or not result["material"].get("materialRevisionSha256")):
            raise ValueError("Resolved material identity or revision is missing")
        disc = result["discretization"]
        energy = result["energyBalance"]
        input_j, losses_j, stored_j = (energy[k] for k in ("input_J", "losses_J", "stored_J"))
        closure = abs(input_j - losses_j - stored_j) / max(input_j, 1e-30)
        row.update(status="completed", actualMesh_m=disc["mesh_m"], cells=disc["cells"],
                   actualMeanDt_s=disc["meanDt_s"], actualMinimumDt_s=disc["minimumDt_s"],
                   acceptedTimestepDistribution=copy.deepcopy(
                       result.get("numericalDiagnostics", {}).get("acceptedTimestepDistribution")),
                   steps=disc["steps"], width_um=result["metrics"]["width_um"],
                   depth_um=result["metrics"]["depth_um"],
                   volume_um3=result["metrics"].get("volume_um3"),
                   peakTemperature_K=result["metrics"]["peakTemperature_K"],
                   peakSelection={key: result.get("numericalDiagnostics", {}).get(key) for key in (
                       "meltPoolExtraction", "peakMeltTime_s", "peakMeltStep",
                       "peakMeltCellCount", "equalMaximumEndpointCount",
                       "firstEqualMaximumTime_s", "lastEqualMaximumTime_s")},
                   interpolatedMidTrackCrossSection=copy.deepcopy(
                       result.get("midTrackInterpolatedCrossSection")),
                   interpolatedPeakMeltPool=copy.deepcopy(result.get("peakInterpolatedMeltPool")),
                   energyBalance={"input_J": input_j, "losses_J": losses_j,
                                  "stored_J": stored_j, "relativeError": closure,
                                  "denominator": "input_J", "reference": "initial enthalpy at preheat"},
                   solver=result["solver"],
                   model={"modelId": core["modelId"], "actualBackend": core["actualBackend"],
                          "solverId": core["solverId"]},
                   material={"name": result["material"]["name"],
                             "materialId": result["material"].get("materialId"),
                             "materialRevisionSha256": result["material"].get("materialRevisionSha256"),
                             "version": result["material"]["version"]},
                   provenance={"inputHash": result["provenance"]["inputHash"],
                               "implementationHash": result["provenance"]["implementationHash"]})
    except Exception as exc:
        row["reason"] = f"{type(exc).__name__}: {exc}"
    return row


def _axis(rows, actual_key):
    checks = {}
    if any(row["status"] != "completed" for row in rows):
        return {"status": "failed", "reason": "One or more solver runs failed", "metrics": checks}
    energy_limit = ACCEPTANCE["energyRelativeErrorMax"]
    energy_errors = [row["energyBalance"]["relativeError"] for row in rows]
    energy_status = "pass" if all(error <= energy_limit for error in energy_errors) else "failed"
    identity = lambda row: (row["model"]["modelId"], row["model"]["actualBackend"],
                            row["model"]["solverId"], row["material"]["materialId"],
                            row["material"]["materialRevisionSha256"])
    if any(identity(row) != identity(rows[0]) for row in rows[1:]):
        return {"status": "failed", "reason": "Model or material revision changed between levels",
                "energyStatus": energy_status, "maximumEnergyRelativeError": max(energy_errors),
                "metrics": checks}
    actual = [row[actual_key] for row in rows]
    if any(a <= b for a, b in zip(actual, actual[1:])):
        return {"status": "failed" if energy_status == "failed" else "inconclusive",
                "reason": "Actual resolution did not strictly refine", "energyStatus": energy_status,
                "maximumEnergyRelativeError": max(energy_errors), "metrics": checks}
    for key in ("width_um", "depth_um"):
        values = [row[key] for row in rows[-3:]]
        if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in values):
            checks[key] = {"status": "inconclusive", "reason": "No positive finite melt geometry at all three finest levels"}
            continue
        change = abs(values[-1] - values[-2]) / values[-1]
        numerical = convergence(values, actual[-3:])
        status = "failed" if change > ACCEPTANCE["finestPairWidthDepthRelativeChangeMax"] else (
            "pass" if numerical["status"] == "numerically-converging" else "inconclusive")
        entry = {"status": status, "finestPairRelativeChange": change,
                 "convergence": numerical}
        if numerical["status"] != "numerically-converging":
            entry["reason"] = numerical["reason"]
        checks[key] = entry
    statuses = [energy_status, *(check["status"] for check in checks.values())]
    status = "failed" if "failed" in statuses else "inconclusive" if "inconclusive" in statuses else "pass"
    return {"status": status, "energyStatus": energy_status,
            "maximumEnergyRelativeError": max(energy_errors), "metrics": checks}


def study(scenario, mesh_levels_um, timestep_levels_s):
    """Run independent mesh and time refinements for a fixed CPU process vector."""
    mesh_levels = _levels(mesh_levels_um, "mesh")
    time_levels = _levels(timestep_levels_s, "timestep")
    if not isinstance(scenario, dict):
        raise ValueError("scenario must be an object")
    if scenario.get("mode") != "standard" or scenario.get("backend") != "reference":
        raise ValueError("Only explicit standard/reference CPU scenarios are supported")
    if scenario.get("study", "none") != "none" or "measurements" in scenario:
        raise ValueError("Built-in studies and experimental measurements are outside this numerical study")
    if "mesh_um" not in scenario or "maxDt_s" not in scenario:
        raise ValueError("scenario must fix mesh_um and maxDt_s for the opposite axis")
    report = {"schemaVersion": SCHEMA_VERSION, "scope": "CPU reference numerical convergence only",
              "experimentalValidation": False, "acceptance": copy.deepcopy(ACCEPTANCE),
              "supplementaryMetric": {
                  "sources": ["interpolatedPeakMeltPool", "interpolatedMidTrackCrossSection"],
                  "usedForAcceptance": False,
                  "reason": "Exploratory liquidus contours; frozen cell-extent acceptance is unchanged"},
              "scenario": copy.deepcopy(scenario),
              "meshStudy": {"fixedMaxDt_s": scenario["maxDt_s"],
                            "levels": [_case_result(scenario, "mesh_um", level) for level in mesh_levels]},
              "timestepStudy": {"fixedMesh_um": scenario["mesh_um"],
                                "levels": [_case_result(scenario, "maxDt_s", level) for level in time_levels]}}
    for name, key in (("meshStudy", "actualMesh_m"), ("timestepStudy", "actualMeanDt_s")):
        report[name]["assessment"] = _axis(report[name]["levels"], key)
    states = [report[name]["assessment"]["status"] for name in ("meshStudy", "timestepStudy")]
    report["status"] = "failed" if "failed" in states else "inconclusive" if "inconclusive" in states else "pass"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", type=Path, help="JSON object with fixed CPU scenario")
    parser.add_argument("output", type=Path, help="JSON report path")
    parser.add_argument("--mesh-levels-um", nargs="+", type=float, required=True)
    parser.add_argument("--timestep-levels-s", nargs="+", type=float, required=True)
    args = parser.parse_args()
    report = study(json.loads(args.scenario.read_text(encoding="utf-8")),
                   args.mesh_levels_um, args.timestep_levels_s)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Numerical convergence: {report['status']} ({args.output})")


if __name__ == "__main__":
    main()
