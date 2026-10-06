"""Bounded, diagnostic-only fixed-event mesh probe for the 40 W CPU scenario."""

import argparse
import contextlib
import copy
import datetime
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lpbf_simulation
from lpbf_core_physics import calculate_mesh_domain, scan_segments
from lpbf_fixed_scan_end_observation import MAX_UNCOMPRESSED_FIELD_BYTES, write_selected_state_artifact
from lpbf_peak import fixed_event_liquidus_cross_section

PROTOCOL_PATH = ROOT / "docs" / "LPBF_FIXED_EVENT_MESH_PROBE_2026-10-02_PROTOCOL.json"
SCENARIO_PATH = ROOT / "docs" / "LPBF_P4_CURRENT_MODEL_40W_SCENARIO_2026-09-25.json"
OUTPUT_PATH = ROOT / "docs" / "LPBF_FIXED_EVENT_MESH_PROBE_2026-10-02.json"
PARTIAL_PATH = OUTPUT_PATH.with_name(OUTPUT_PATH.stem + ".partial.json")
FIELD_DIRECTORY = ROOT / "docs" / "LPBF_FIXED_EVENT_MESH_PROBE_FIELDS_2026-10-02"
PROTOCOL_ID = "lpbf-fixed-event-mesh-probe-2026-10-02-v1"
LEVELS_S = (1e-7, 5e-8, 2.5e-8)


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _canonical_sha256(value):
    return _sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode("utf-8"))


def _field_difference(reference, candidate, cell_volume_m3):
    """Return volume-weighted L2 and maximum absolute field differences."""
    ref = np.asarray(reference, dtype=np.float64)
    current = np.asarray(candidate, dtype=np.float64)
    if (ref.shape != current.shape or ref.size == 0 or not np.isfinite(ref).all()
            or not np.isfinite(current).all()):
        raise ValueError("Field arrays must have matching nonempty finite shapes")
    if (isinstance(cell_volume_m3, bool) or not isinstance(cell_volume_m3, (int, float))
            or not math.isfinite(cell_volume_m3) or cell_volume_m3 <= 0):
        raise ValueError("Cell volume must be finite and positive")
    difference = current - ref
    l2 = float(np.linalg.norm(difference.ravel()) * math.sqrt(cell_volume_m3))
    reference_l2 = float(np.linalg.norm(ref.ravel()) * math.sqrt(cell_volume_m3))
    relative_l2 = (0.0 if l2 == 0.0 else None) if reference_l2 == 0.0 else l2 / reference_l2
    return {
        "volumeL2Difference": l2,
        "relativeL2Difference": relative_l2,
        "maximumAbsoluteDifference": float(np.max(np.abs(difference))),
    }


def _validate_completed_case(result, selected, final_state, case, target_time_s):
    """Validate run summary, accepted-step history, and selected/final-state identity."""
    try:
        discretization = result["discretization"]
        diagnostics = result["numericalDiagnostics"]
        distribution = diagnostics["acceptedTimestepDistribution"]
        energy = result["energyBalance"]
        selected_steps = np.asarray(selected["accepted_dt_s"], dtype=np.float64)
        final_steps = np.asarray(final_state["accepted_dt_s"], dtype=np.float64)
    except (KeyError, TypeError) as error:
        raise ValueError("Run result is missing discretization, timestep, energy, or final-state evidence") from error
    if (selected_steps.ndim != 1 or final_steps.ndim != 1 or not selected_steps.size
            or not np.isfinite(selected_steps).all() or not np.isfinite(final_steps).all()):
        raise ValueError("Selected and final accepted-timestep histories must be finite nonempty vectors")
    tolerance = float(selected["roundoff_tolerance_s"])
    if (not math.isclose(float(selected["time_s"]), target_time_s, rel_tol=0., abs_tol=tolerance)
            or not math.isclose(float(final_state["time_s"]), target_time_s, rel_tol=0., abs_tol=tolerance)
            or int(selected["step"]) != int(discretization["steps"])
            or int(discretization["steps"]) != len(final_steps)
            or not np.array_equal(selected_steps, final_steps)):
        raise ValueError("selected event must be the final run state and step")
    if (int(discretization["cells"]) != case["cells"]
            or not math.isclose(float(discretization["mesh_m"]), float(case["domain"]["dx"]),
                                rel_tol=0., abs_tol=1e-15)):
        raise ValueError("Run discretization differs from the exact preflight mesh")
    requested_dt = float(case["maxDt_s"])
    if (distribution.get("methodId") != "accepted-timestep-distribution-v1"
            or int(distribution["count"]) != len(final_steps)
            or float(distribution["requestedMaxDt_s"]) != requested_dt
            or not math.isclose(float(distribution["total_s"]), float(final_state["time_s"]),
                                rel_tol=0., abs_tol=tolerance)):
        raise ValueError("Accepted timestep distribution does not verify the requested level and final event")
    if (not math.isclose(float(distribution["mean_s"]), float(np.mean(final_steps)),
                         rel_tol=1e-10, abs_tol=1e-18)
            or float(distribution["maximum_s"]) > requested_dt * (1. + 1e-12)
            or not math.isclose(float(discretization["meanDt_s"]), float(distribution["mean_s"]),
                                rel_tol=1e-10, abs_tol=1e-18)
            or not math.isclose(float(discretization["minimumDt_s"]), float(distribution["minimum_s"]),
                                rel_tol=1e-10, abs_tol=1e-18)):
        raise ValueError("Accepted timestep statistics differ from the realized step history")
    for key in ("sourceLimitedStepCount", "sourceTimestepRetries"):
        value = distribution.get(key)
        if type(value) is not int or value < 0:
            raise ValueError(f"Accepted timestep distribution has invalid {key}")
    energy_keys = ("input_J", "losses_J", "stored_J", "relativeError")
    try:
        energy_values = {key: float(energy[key]) for key in energy_keys}
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Run result is missing finite energy-balance terms") from error
    if (not all(math.isfinite(value) for value in energy_values.values())
            or energy_values["input_J"] <= 0 or energy_values["losses_J"] < 0
            or energy_values["stored_J"] < 0 or energy_values["relativeError"] < 0):
        raise ValueError("Run energy-balance terms are outside their valid finite range")
    measured_closure = abs(energy_values["input_J"] - energy_values["losses_J"]
                           - energy_values["stored_J"]) / max(energy_values["input_J"], 1e-30)
    if not math.isclose(measured_closure, energy_values["relativeError"], rel_tol=1e-8, abs_tol=1e-15):
        raise ValueError("Reported energy closure differs from the run energy ledger")
    return {
        "discretization": copy.deepcopy(discretization),
        "acceptedTimestepDistribution": copy.deepcopy(distribution),
        "sourceLimitedStepCount": distribution["sourceLimitedStepCount"],
        "sourceTimestepRetries": distribution["sourceTimestepRetries"],
        "energyBalance": copy.deepcopy(energy),
    }


def _validate_protocol(protocol):
    required = {
        "schemaVersion", "protocolId", "status", "scope", "experimentalValidation",
        "convergenceConclusion", "scenarioFile", "scenarioDocumentProtocolId", "scenarioSha256",
        "scenarioOverrides", "levels", "mesh_um", "cooling_s", "eventRule", "expectedEventTime_s",
        "expectedEventEndpoint_m", "expectedDomain", "expectedCells", "expectedInputSha256ByMaxDt",
        "expectedImplementationFingerprint", "predictedStepsByMaxDt", "predictedTotalSteps",
        "predictedTotalCellSteps", "maximumStepsPerCase", "maximumTotalCellSteps",
        "fieldFormat", "fieldScope", "maximumUncompressedFieldBytes", "output", "partial", "fieldDirectory",
    }
    if not isinstance(protocol, dict) or set(protocol) != required:
        raise ValueError("Probe protocol fields do not match the registered schema")
    if (protocol["schemaVersion"] != 1 or protocol["protocolId"] != PROTOCOL_ID
            or protocol["status"] != "diagnostic-only"
            or protocol["experimentalValidation"] is not False
            or protocol["convergenceConclusion"] != "inconclusive"):
        raise ValueError("Probe must remain diagnostic-only, unvalidated, and inconclusive")
    if (protocol["scenarioFile"] != "docs/LPBF_P4_CURRENT_MODEL_40W_SCENARIO_2026-09-25.json"
            or protocol["scenarioDocumentProtocolId"] != "lpbf-p4-current-layer-conforming-40w-2026-09-25-v1"
            or protocol["mesh_um"] != 10 or protocol["cooling_s"] != 0
            or protocol["levels"] != list(LEVELS_S)):
        raise ValueError("Probe scenario or fixed timestep levels differ from the frozen plan")
    if protocol["scenarioOverrides"] != {"mesh_um": 10, "cooling_s": 0}:
        raise ValueError("Probe scenario overrides differ from the frozen plan")
    if (protocol["eventRule"] != "first-scan-segment-end"
            or protocol["expectedEventTime_s"] != 0.00024999999999999995
            or protocol["expectedEventEndpoint_m"] != [9.999999999999999e-05, 0.0, 4e-05]):
        raise ValueError("Probe event does not identify the expected first scan endpoint")
    domain = protocol["expectedDomain"]
    if domain != {"nx": 44, "ny": 44, "nz": 34, "dx_um": 10.0} or protocol["expectedCells"] != 65_824:
        raise ValueError("Probe exact-cell/domain preflight differs from the frozen plan")
    predicted_steps = {"1e-07": 2500, "5e-08": 5000, "2.5e-08": 10000}
    if (protocol["predictedStepsByMaxDt"] != predicted_steps
            or protocol["predictedTotalSteps"] != 17_500
            or protocol["predictedTotalCellSteps"] != 1_151_920_000):
        raise ValueError("Probe predicted work differs from the fixed-event plan")
    if (type(protocol["maximumStepsPerCase"]) is not int
            or protocol["maximumStepsPerCase"] < max(predicted_steps.values())
            or type(protocol["maximumTotalCellSteps"]) is not int
            or protocol["maximumTotalCellSteps"] < protocol["predictedTotalCellSteps"]):
        raise ValueError("Probe cell-step ceiling is below predicted work")
    if protocol["maximumTotalCellSteps"] != 1_300_000_000:
        raise ValueError("Probe cell-step ceiling differs from the approved bound")
    if (protocol["fieldFormat"] != "numpy-npz-compressed-little-endian-float64-v1"
            or protocol["fieldScope"] != "CPU numerical diagnostic fields only; not a run archive or experimental evidence"
            or protocol["maximumUncompressedFieldBytes"] != MAX_UNCOMPRESSED_FIELD_BYTES):
        raise ValueError("Probe field artifact format or bound differs from the existing observer contract")
    if not isinstance(protocol["expectedImplementationFingerprint"], str) or len(protocol["expectedImplementationFingerprint"]) != 64:
        raise ValueError("Probe implementation fingerprint is missing")
    if protocol["output"] != OUTPUT_PATH.relative_to(ROOT).as_posix() \
            or protocol["partial"] != PARTIAL_PATH.relative_to(ROOT).as_posix() \
            or protocol["fieldDirectory"] != FIELD_DIRECTORY.relative_to(ROOT).as_posix():
        raise ValueError("Probe artifact destinations differ from the registered fresh paths")


def preflight(protocol_path=PROTOCOL_PATH):
    protocol_path = Path(protocol_path).resolve(strict=True)
    if protocol_path != PROTOCOL_PATH.resolve():
        raise ValueError("Only the registered fixed-event mesh probe protocol is accepted")
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    _validate_protocol(protocol)
    scenario_bytes = SCENARIO_PATH.read_bytes()
    if _sha256(scenario_bytes) != protocol["scenarioSha256"]:
        raise ValueError("Reference scenario bytes differ from the frozen probe protocol")
    scenario_document = json.loads(scenario_bytes)
    if scenario_document.get("protocolId") != protocol["scenarioDocumentProtocolId"]:
        raise ValueError("Reference scenario document identity differs")
    scenario = copy.deepcopy(scenario_document["scenario"])
    scenario.update(protocol["scenarioOverrides"])
    if (scenario.get("mode") != "standard" or scenario.get("backend") != "reference"
            or scenario.get("material") != "Inconel 718" or scenario.get("power_W") != 40
            or scenario.get("speed_mm_s") != 800 or scenario.get("trackLength_um") != 200
            or scenario.get("tracks") != 1 or scenario.get("layers") != 1
            or scenario.get("scanAngle_deg") != 0 or scenario.get("study") != "none"):
        raise ValueError("Probe scenario is outside the fixed 40 W single-track CPU reference scope")
    if lpbf_simulation.implementation_fingerprint() != protocol["expectedImplementationFingerprint"]:
        raise ValueError("Current solver implementation fingerprint differs from the frozen protocol")
    segments, final_time = scan_segments(scenario)
    event = segments[0]
    endpoint = [float(event["end"][0]), float(event["end"][1]), float(scenario["layer_um"] * 1e-6)]
    if (not math.isclose(event["end_s"], protocol["expectedEventTime_s"], rel_tol=0., abs_tol=1e-18)
            or any(not math.isclose(actual, expected, rel_tol=0., abs_tol=1e-15)
                   for actual, expected in zip(endpoint, protocol["expectedEventEndpoint_m"]))
            or final_time != event["end_s"]):
        raise ValueError("Resolved simulation horizon does not end at the frozen first scan event")
    cases = []
    for requested_dt in protocol["levels"]:
        payload = copy.deepcopy(scenario)
        payload["maxDt_s"] = requested_dt
        resolved, material = lpbf_simulation.validate(payload)
        domain = calculate_mesh_domain(resolved)
        exact_domain = {"nx": domain["nx"], "ny": domain["ny"], "nz": domain["nz"],
                        "dx_um": float(domain["dx"] * 1e6)}
        cells = int(domain["nx"] * domain["ny"] * domain["nz"])
        input_hash = _canonical_sha256(resolved)
        dt_key = str(requested_dt)
        expected_domain = protocol["expectedDomain"]
        if (any(exact_domain[key] != expected_domain[key] for key in ("nx", "ny", "nz"))
                or not math.isclose(exact_domain["dx_um"], expected_domain["dx_um"], rel_tol=0., abs_tol=1e-12)
                or cells != protocol["expectedCells"]
                or input_hash != protocol["expectedInputSha256ByMaxDt"].get(dt_key)):
            raise ValueError(f"Resolved input or exact mesh domain differs for timestep {dt_key}")
        cases.append({"maxDt_s": requested_dt, "payload": resolved, "material": material,
                      "domain": domain, "cells": cells, "inputSha256": input_hash,
                      "predictedSteps": protocol["predictedStepsByMaxDt"][dt_key]})
    if OUTPUT_PATH.exists() or PARTIAL_PATH.exists() or FIELD_DIRECTORY.exists():
        raise FileExistsError("Probe output already exists; create a new protocol identity for another attempt")
    return protocol, protocol_bytes, scenario_bytes, event, cases


@contextlib.contextmanager
def _step_budget(counters, cells, limits):
    original = lpbf_simulation.source_limited_step

    def guarded(*args, **kwargs):
        if counters["acceptedSteps"] >= limits["maximumTotalSteps"]:
            raise RuntimeError("Probe accepted-step ceiling reached")
        if counters["caseSteps"] >= limits["maximumStepsPerCase"]:
            raise RuntimeError("Probe per-case accepted-step ceiling reached")
        if (counters["acceptedSteps"] + 1) * cells > limits["maximumTotalCellSteps"]:
            raise RuntimeError("Probe total cell-step ceiling reached")
        result = original(*args, **kwargs)
        counters["acceptedSteps"] += 1
        counters["caseSteps"] += 1
        return result

    lpbf_simulation.source_limited_step = guarded
    try:
        yield
    finally:
        lpbf_simulation.source_limited_step = original


def _write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def execute(protocol_path=PROTOCOL_PATH):
    protocol, protocol_bytes, scenario_bytes, event, cases = preflight(protocol_path)
    fingerprint = protocol["expectedImplementationFingerprint"]
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()
    cells = protocol["expectedCells"]
    maximum_steps = protocol["maximumTotalCellSteps"] // cells
    report = {
        "schemaVersion": 1, "protocolId": protocol["protocolId"],
        "protocolSha256": _sha256(protocol_bytes), "scenarioFile": protocol["scenarioFile"],
        "scenarioSha256": _sha256(scenario_bytes), "executionHeadCommit": head,
        "scope": protocol["scope"], "status": "diagnostic-only",
        "experimentalValidation": False, "convergenceConclusion": "inconclusive",
        "implementationFingerprintAtStart": fingerprint,
        "implementationSourceManifest": list(lpbf_simulation.IMPLEMENTATION_SOURCE_FILES),
        "event": {"rule": protocol["eventRule"], "time_s": float(event["end_s"]),
                  "endpoint_m": protocol["expectedEventEndpoint_m"]},
        "resourcePreflight": {"domain": protocol["expectedDomain"], "cells": cells,
            "predictedStepsByMaxDt": protocol["predictedStepsByMaxDt"],
            "predictedTotalSteps": protocol["predictedTotalSteps"],
            "predictedTotalCellSteps": protocol["predictedTotalCellSteps"],
            "maximumTotalCellSteps": protocol["maximumTotalCellSteps"]},
        "runtimeWork": {"acceptedSteps": 0, "acceptedCellSteps": 0},
        "output": protocol["output"], "partial": protocol["partial"],
        "fieldDirectory": protocol["fieldDirectory"], "rows": [], "stage": "running",
        "startedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    _write_json(PARTIAL_PATH, report)
    FIELD_DIRECTORY.mkdir(parents=True)
    counters = {"acceptedSteps": 0, "caseSteps": 0}
    snapshots = []
    case_results = []
    started = time.perf_counter()
    limits = {"maximumStepsPerCase": protocol["maximumStepsPerCase"],
              "maximumTotalSteps": maximum_steps,
              "maximumTotalCellSteps": protocol["maximumTotalCellSteps"]}
    try:
        for index, case in enumerate(cases):
            if lpbf_simulation.implementation_fingerprint() != fingerprint:
                raise RuntimeError("Solver implementation changed during probe")
            counters["caseSteps"] = 0
            observed = []
            final_states = []
            with _step_budget(counters, cells, limits):
                result = lpbf_simulation.run(case["payload"], selected_time_observer=observed.append,
                                             selected_time_s=protocol["expectedEventTime_s"],
                                             final_state_observer=final_states.append)
            if len(observed) != 1 or len(final_states) != 1:
                raise RuntimeError("Each probe case must capture exactly one fixed-event and final state")
            snapshot = observed[0]
            final_state = final_states[0]
            realized = _validate_completed_case(result, snapshot, final_state, case,
                                                protocol["expectedEventTime_s"])
            if int(snapshot["step"]) != counters["caseSteps"]:
                raise RuntimeError("Runtime step guard count differs from the captured accepted-step history")
            if index and not np.array_equal(snapshot["coordinates_m"], snapshots[0]["coordinates_m"]):
                raise RuntimeError("Timestep cases do not share the exact same cell grid")
            snapshots.append(snapshot)
            cross_section = fixed_event_liquidus_cross_section(
                snapshot["coordinates_m"], snapshot["temperature_K"],
                x_position_m=float(event["end"][0]), dx_m=float(case["domain"]["dx"]),
                liquidus_K=float(result["material"]["liquidus_K"]),
                substrate_interface_z_m=0.0)
            artifact_path = FIELD_DIRECTORY / f"maxdt-{case['maxDt_s']:.4e}.npz"
            field_artifact = write_selected_state_artifact(
                snapshot, artifact_path, protocol["maximumUncompressedFieldBytes"])
            row = {
                "maxDt_s": case["maxDt_s"], "cells": case["cells"],
                "acceptedSteps": int(snapshot["step"]),
                "acceptedCellSteps": int(snapshot["step"] * cells),
                "finalRunTime_s": float(final_state["time_s"]),
                "finalRunStep": len(final_state["accepted_dt_s"]),
                "resolvedInputSha256": case["inputSha256"],
                "actualEventTime_s": float(snapshot["time_s"]),
                "discretization": realized["discretization"],
                "acceptedTimestepDistribution": realized["acceptedTimestepDistribution"],
                "sourceLimitedStepCount": realized["sourceLimitedStepCount"],
                "sourceTimestepRetries": realized["sourceTimestepRetries"],
                "energyBalance": realized["energyBalance"],
                "fieldArtifact": field_artifact,
                "crossSectionThermalProxy": cross_section,
                "reportedSolver": result.get("solver"), "reportedModel": result.get("coreContract"),
            }
            case_results.append((row, snapshot))
            report["rows"].append(row)
            report["runtimeWork"] = {"acceptedSteps": counters["acceptedSteps"],
                                     "acceptedCellSteps": counters["acceptedSteps"] * cells}
            _write_json(PARTIAL_PATH, report)
        fine_snapshot = snapshots[-1]
        for row, snapshot in case_results:
            if (not np.array_equal(snapshot["coordinates_m"], fine_snapshot["coordinates_m"])
                    or snapshot["cell_volume_m3"] != fine_snapshot["cell_volume_m3"]):
                raise RuntimeError("Timestep cases do not share the exact same cell grid and volume")
            row["fieldDifferenceFromFine"] = {
                "referenceMaxDt_s": LEVELS_S[-1],
                "temperature_K": _field_difference(fine_snapshot["temperature_K"],
                                                    snapshot["temperature_K"], snapshot["cell_volume_m3"]),
                "enthalpy_J_m3": _field_difference(fine_snapshot["enthalpy_J_m3"],
                                                    snapshot["enthalpy_J_m3"], snapshot["cell_volume_m3"]),
            }
            _write_json(PARTIAL_PATH, report)
        if lpbf_simulation.implementation_fingerprint() != fingerprint:
            raise RuntimeError("Solver implementation changed before probe completion")
        report["stage"] = "completed"
        report["wallTime_s"] = time.perf_counter() - started
        report["finishedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        _write_json(OUTPUT_PATH, report)
        _write_json(PARTIAL_PATH, report)
        return report
    except Exception as error:
        report["stage"] = "failed"
        report["failure"] = {"type": type(error).__name__, "message": str(error)}
        report["runtimeWork"] = {"acceptedSteps": counters["acceptedSteps"],
                                 "acceptedCellSteps": counters["acceptedSteps"] * cells}
        report["wallTime_s"] = time.perf_counter() - started
        _write_json(PARTIAL_PATH, report)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight-only", action="store_true",
                        help="Validate frozen identity and exact work/domain bounds without solving")
    args = parser.parse_args()
    if args.preflight_only:
        protocol, protocol_bytes, _scenario, event, cases = preflight()
        print(json.dumps({"protocolSha256": _sha256(protocol_bytes), "eventTime_s": event["end_s"],
                          "cells": protocol["expectedCells"], "cases": len(cases),
                          "predictedTotalCellSteps": protocol["predictedTotalCellSteps"]}, indent=2))
    else:
        report = execute()
        print(json.dumps({"stage": report["stage"], "rows": len(report["rows"]),
                          "output": str(OUTPUT_PATH)}, indent=2))


if __name__ == "__main__":
    main()
