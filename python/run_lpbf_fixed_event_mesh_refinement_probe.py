"""Diagnostic-only fixed-event mesh refinement probe using one shared CPU timestep."""

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

PROTOCOL_PATH = ROOT / "docs" / "LPBF_FIXED_EVENT_MESH_REFINEMENT_V2_2026-10-02_PROTOCOL.json"
SCENARIO_PATH = ROOT / "docs" / "LPBF_P4_CURRENT_MODEL_40W_SCENARIO_2026-09-25.json"
OUTPUT_PATH = ROOT / "docs" / "LPBF_FIXED_EVENT_MESH_REFINEMENT_V2_2026-10-02.json"
PARTIAL_PATH = OUTPUT_PATH.with_name(OUTPUT_PATH.stem + ".partial.json")
FIELD_DIRECTORY = ROOT / "docs" / "LPBF_FIXED_EVENT_MESH_REFINEMENT_V2_FIELDS_2026-10-02"
PROTOCOL_ID = "lpbf-fixed-event-mesh-refinement-2026-10-02-v2"
MESH_LEVELS_UM = (20, 10, 5)
MAX_DT_S = 1e-7


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _canonical_sha256(value):
    return _sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode("utf-8"))


def _validate_protocol(protocol):
    required = {
        "schemaVersion", "protocolId", "status", "scope", "experimentalValidation",
        "convergenceConclusion", "scenarioFile", "scenarioDocumentProtocolId", "scenarioSha256",
        "scenarioOverrides", "meshLevels_um", "maxDt_s", "eventRule", "expectedEventTime_s",
        "expectedEventEndpoint_m", "expectedPhysicalDomain_um", "expectedDomainByMesh_um",
        "expectedInputSha256ByMesh_um", "expectedImplementationFingerprint", "stepsPerCase",
        "predictedTotalSteps", "predictedTotalCellSteps", "maximumCells", "maximumStepsPerCase",
        "maximumTotalCellSteps", "fieldFormat", "fieldScope", "maximumUncompressedFieldBytes",
        "output", "partial", "fieldDirectory",
    }
    if not isinstance(protocol, dict) or set(protocol) != required:
        raise ValueError("Refinement protocol fields do not match the registered schema")
    if (protocol["schemaVersion"] != 1 or protocol["protocolId"] != PROTOCOL_ID
            or protocol["status"] != "diagnostic-only"
            or protocol["experimentalValidation"] is not False
            or protocol["convergenceConclusion"] != "inconclusive"):
        raise ValueError("Refinement probe must remain diagnostic-only, unvalidated, and inconclusive")
    if (protocol["scenarioFile"] != "docs/LPBF_P4_CURRENT_MODEL_40W_SCENARIO_2026-09-25.json"
            or protocol["scenarioDocumentProtocolId"] != "lpbf-p4-current-layer-conforming-40w-2026-09-25-v1"
            or protocol["scenarioOverrides"] != {"cooling_s": 0}
            or protocol["meshLevels_um"] != list(MESH_LEVELS_UM)
            or protocol["maxDt_s"] != MAX_DT_S):
        raise ValueError("Refinement probe requires the frozen scenario, mesh levels, and common fixed timestep")
    if (protocol["eventRule"] != "first-scan-segment-end"
            or protocol["expectedEventTime_s"] != 0.00024999999999999995
            or protocol["expectedEventEndpoint_m"] != [9.999999999999999e-05, 0.0, 4e-05]):
        raise ValueError("Refinement event differs from the frozen first scan endpoint")
    expected_domains = {
        "20": {"nx": 22, "ny": 22, "nz": 17, "cells": 8228, "dx_um": 20},
        "10": {"nx": 44, "ny": 44, "nz": 34, "cells": 65824, "dx_um": 10},
        "5": {"nx": 88, "ny": 88, "nz": 68, "cells": 526592, "dx_um": 5},
    }
    if (protocol["expectedDomainByMesh_um"] != expected_domains
            or protocol["expectedPhysicalDomain_um"] != [440, 440, 340]):
        raise ValueError("Refinement exact domains or physical domain sizes differ from the frozen plan")
    predicted = sum(protocol["stepsPerCase"] * expected_domains[str(mesh)]["cells"]
                    for mesh in MESH_LEVELS_UM)
    if (protocol["stepsPerCase"] != 3000 or protocol["predictedTotalSteps"] != 9000
            or protocol["predictedTotalCellSteps"] != predicted or predicted != 1_801_932_000):
        raise ValueError("Refinement predicted work differs from the frozen shared-timestep plan")
    if (type(protocol["maximumCells"]) is not int or protocol["maximumCells"] != 600_000
            or max(value["cells"] for value in expected_domains.values()) > protocol["maximumCells"]
            or type(protocol["maximumStepsPerCase"]) is not int
            or protocol["maximumStepsPerCase"] < protocol["stepsPerCase"]):
        raise ValueError("Refinement cell or per-case step ceiling is below the frozen plan")
    if (type(protocol["maximumTotalCellSteps"]) is not int
            or protocol["maximumTotalCellSteps"] < predicted):
        raise ValueError("Refinement total cell-step ceiling is below predicted work")
    if protocol["maximumTotalCellSteps"] != 1_900_000_000:
        raise ValueError("Refinement total cell-step ceiling differs from the approved bound")
    if (protocol["fieldFormat"] != "numpy-npz-compressed-little-endian-float64-v1"
            or protocol["fieldScope"] != "CPU numerical diagnostic fields only; not a run archive or experimental evidence"
            or protocol["maximumUncompressedFieldBytes"] != MAX_UNCOMPRESSED_FIELD_BYTES):
        raise ValueError("Refinement field artifact format or byte bound differs from the observer contract")
    if (not isinstance(protocol["expectedImplementationFingerprint"], str)
            or len(protocol["expectedImplementationFingerprint"]) != 64):
        raise ValueError("Refinement solver implementation fingerprint is missing")
    if (protocol["output"] != OUTPUT_PATH.relative_to(ROOT).as_posix()
            or protocol["partial"] != PARTIAL_PATH.relative_to(ROOT).as_posix()
            or protocol["fieldDirectory"] != FIELD_DIRECTORY.relative_to(ROOT).as_posix()):
        raise ValueError("Refinement artifact destinations differ from the fresh registered paths")


def preflight(protocol_path=PROTOCOL_PATH):
    protocol_path = Path(protocol_path).resolve(strict=True)
    if protocol_path != PROTOCOL_PATH.resolve():
        raise ValueError("Only the registered mesh refinement protocol is accepted")
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    _validate_protocol(protocol)
    scenario_bytes = SCENARIO_PATH.read_bytes()
    if _sha256(scenario_bytes) != protocol["scenarioSha256"]:
        raise ValueError("Reference scenario bytes differ from the frozen refinement protocol")
    scenario_document = json.loads(scenario_bytes)
    if scenario_document.get("protocolId") != protocol["scenarioDocumentProtocolId"]:
        raise ValueError("Reference scenario document identity differs")
    base = copy.deepcopy(scenario_document["scenario"])
    base.update(protocol["scenarioOverrides"])
    if (base.get("mode") != "standard" or base.get("backend") != "reference"
            or base.get("material") != "Inconel 718" or base.get("power_W") != 40
            or base.get("speed_mm_s") != 800 or base.get("trackLength_um") != 200
            or base.get("tracks") != 1 or base.get("layers") != 1
            or base.get("scanAngle_deg") != 0 or base.get("study") != "none"):
        raise ValueError("Refinement scenario is outside the fixed IN718 40 W CPU reference scope")
    if lpbf_simulation.implementation_fingerprint() != protocol["expectedImplementationFingerprint"]:
        raise ValueError("Current solver implementation fingerprint differs from frozen refinement protocol")
    segments, final_time = scan_segments(base)
    event = segments[0]
    endpoint = [float(event["end"][0]), float(event["end"][1]), float(base["layer_um"] * 1e-6)]
    if (not math.isclose(float(event["end_s"]), protocol["expectedEventTime_s"], rel_tol=0., abs_tol=1e-18)
            or any(not math.isclose(actual, expected, rel_tol=0., abs_tol=1e-15)
                   for actual, expected in zip(endpoint, protocol["expectedEventEndpoint_m"]))
            or final_time != event["end_s"]):
        raise ValueError("Refinement run horizon does not end at the frozen first scan event")
    cases = []
    physical_lengths = None
    for mesh in MESH_LEVELS_UM:
        raw = copy.deepcopy(base)
        raw.update(mesh_um=mesh, maxDt_s=protocol["maxDt_s"])
        resolved, material = lpbf_simulation.validate(raw)
        domain = calculate_mesh_domain(resolved)
        cells = int(domain["nx"] * domain["ny"] * domain["nz"])
        actual_domain = {"nx": domain["nx"], "ny": domain["ny"], "nz": domain["nz"],
                         "cells": cells, "dx_um": float(domain["dx"] * 1e6)}
        lengths = [float(domain["span_x"] * 1e6), float(domain["span_y"] * 1e6),
                   float(domain["nz"] * domain["dx"] * 1e6)]
        expected = protocol["expectedDomainByMesh_um"][str(mesh)]
        key = str(mesh)
        if (any(actual_domain[k] != expected[k] for k in ("nx", "ny", "nz", "cells"))
                or not math.isclose(actual_domain["dx_um"], expected["dx_um"], rel_tol=0., abs_tol=1e-12)
                or _canonical_sha256(resolved) != protocol["expectedInputSha256ByMesh_um"].get(key)):
            raise ValueError(f"Resolved input or exact domain differs at {mesh} um")
        if physical_lengths is None:
            physical_lengths = lengths
        elif any(not math.isclose(actual, expected_length, rel_tol=0., abs_tol=1e-9)
                 for actual, expected_length in zip(lengths, physical_lengths)):
            raise ValueError("Mesh cases do not cover the same physical domain")
        if any(not math.isclose(actual, expected_length, rel_tol=0., abs_tol=1e-9)
               for actual, expected_length in zip(lengths, protocol["expectedPhysicalDomain_um"])):
            raise ValueError(f"Resolved physical domain differs from the frozen plan at {mesh} um")
        cases.append({"mesh_um": mesh, "payload": resolved, "material": material, "domain": domain,
                      "cells": cells, "inputSha256": _canonical_sha256(resolved)})
    return protocol, protocol_bytes, scenario_bytes, event, cases


def _validate_completed_case(result, selected, final_state, case, target_time_s):
    try:
        solver = result["solver"]
        model = result["coreContract"]
        material = result["material"]
        discretization = result["discretization"]
        distribution = result["numericalDiagnostics"]["acceptedTimestepDistribution"]
        energy = result["energyBalance"]
        selected_steps = np.asarray(selected["accepted_dt_s"], dtype=np.float64)
        final_steps = np.asarray(final_state["accepted_dt_s"], dtype=np.float64)
        tolerance = float(selected["roundoff_tolerance_s"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Run result lacks discretization, timestep, energy, or final-state evidence") from error
    if (result.get("effectiveMode") != "standard" or solver.get("id") != "enthalpy-fv-6"
            or model.get("actualBackend") != "numpy-reference"
            or model.get("modelId") != "stationary-enthalpy-conduction-layer-conforming-v1"
            or model.get("solverId") != solver.get("id")
            or not material.get("materialId") or not material.get("materialRevisionSha256")):
        raise ValueError("Run did not resolve the expected standard CPU reference solver and material")
    if (selected_steps.ndim != 1 or final_steps.ndim != 1 or not selected_steps.size
            or not np.isfinite(selected_steps).all() or not np.isfinite(final_steps).all()):
        raise ValueError("Selected and final accepted-timestep histories must be finite nonempty vectors")
    if (not math.isclose(float(selected["time_s"]), target_time_s, rel_tol=0., abs_tol=tolerance)
            or not math.isclose(float(final_state["time_s"]), target_time_s, rel_tol=0., abs_tol=tolerance)
            or int(selected["step"]) != int(discretization["steps"])
            or int(discretization["steps"]) != len(final_steps)
            or not np.array_equal(selected_steps, final_steps)):
        raise ValueError("selected event must be the final run state and step")
    if (int(discretization["cells"]) != case["cells"]
            or not math.isclose(float(discretization["mesh_m"]), float(case["domain"]["dx"]),
                                rel_tol=0., abs_tol=1e-15)):
        raise ValueError("Run discretization differs from exact mesh preflight")
    requested_dt = float(case.get("maxDt_s", case["payload"]["maxDt_s"]
                                 if "payload" in case else math.nan))
    if (distribution.get("methodId") != "accepted-timestep-distribution-v1"
            or int(distribution["count"]) != len(final_steps)
            or float(distribution["requestedMaxDt_s"]) != requested_dt
            or not math.isclose(float(distribution["total_s"]), float(final_state["time_s"]),
                                rel_tol=0., abs_tol=tolerance)):
        raise ValueError("Accepted timestep distribution does not verify the common requested level")
    if (not math.isclose(float(distribution["mean_s"]), float(np.mean(final_steps)),
                         rel_tol=1e-10, abs_tol=1e-18)
            or float(distribution["maximum_s"]) > requested_dt * (1. + 1e-12)
            or not math.isclose(float(discretization["meanDt_s"]), float(distribution["mean_s"]),
                                rel_tol=1e-10, abs_tol=1e-18)
            or not math.isclose(float(discretization["minimumDt_s"]), float(distribution["minimum_s"]),
                                rel_tol=1e-10, abs_tol=1e-18)):
        raise ValueError("Accepted timestep statistics differ from the realized step history")
    for key in ("sourceLimitedStepCount", "sourceTimestepRetries"):
        if type(distribution.get(key)) is not int or distribution[key] < 0:
            raise ValueError(f"Accepted timestep distribution has invalid {key}")
    try:
        energy_values = {key: float(energy[key]) for key in ("input_J", "losses_J", "stored_J", "relativeError")}
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Run energy balance is incomplete") from error
    if (not all(math.isfinite(value) for value in energy_values.values()) or energy_values["input_J"] <= 0
            or energy_values["losses_J"] < 0 or energy_values["stored_J"] < 0
            or energy_values["relativeError"] < 0):
        raise ValueError("Run energy balance has invalid finite terms")
    closure = abs(energy_values["input_J"] - energy_values["losses_J"] - energy_values["stored_J"])
    closure /= max(energy_values["input_J"], 1e-30)
    if not math.isclose(closure, energy_values["relativeError"], rel_tol=1e-8, abs_tol=1e-15):
        raise ValueError("Reported energy closure differs from the run energy ledger")
    return {
        "discretization": copy.deepcopy(discretization),
        "solver": copy.deepcopy(solver),
        "model": {key: model[key] for key in ("modelId", "actualBackend", "solverId")},
        "material": {key: material[key] for key in (
            "name", "materialId", "materialRevisionSha256", "version") if key in material},
        "acceptedTimestepDistribution": copy.deepcopy(distribution),
        "sourceLimitedStepCount": distribution["sourceLimitedStepCount"],
        "sourceTimestepRetries": distribution["sourceTimestepRetries"],
        "energyBalance": copy.deepcopy(energy),
    }


@contextlib.contextmanager
def _step_budget(counters, cells, limits):
    original = lpbf_simulation.source_limited_step

    def guarded(*args, **kwargs):
        if counters["caseSteps"] >= limits["maximumStepsPerCase"]:
            raise RuntimeError("Refinement per-case step ceiling reached")
        if counters["totalCellSteps"] + cells > limits["maximumTotalCellSteps"]:
            raise RuntimeError("Refinement total cell-step ceiling reached")
        result = original(*args, **kwargs)
        counters["caseSteps"] += 1
        counters["totalSteps"] += 1
        counters["totalCellSteps"] += cells
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


def _assert_fresh_destinations():
    if OUTPUT_PATH.exists() or PARTIAL_PATH.exists() or FIELD_DIRECTORY.exists():
        raise FileExistsError("Refinement output already exists; use a fresh protocol identity for another attempt")


def execute(protocol_path=PROTOCOL_PATH):
    protocol, protocol_bytes, scenario_bytes, event, cases = preflight(protocol_path)
    _assert_fresh_destinations()
    fingerprint = protocol["expectedImplementationFingerprint"]
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()
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
        "resourcePreflight": {"physicalDomain_um": protocol["expectedPhysicalDomain_um"],
            "domainByMesh_um": protocol["expectedDomainByMesh_um"],
            "maximumCells": protocol["maximumCells"],
            "stepsPerCase": protocol["stepsPerCase"],
            "predictedTotalSteps": protocol["predictedTotalSteps"],
            "predictedTotalCellSteps": protocol["predictedTotalCellSteps"],
            "maximumTotalCellSteps": protocol["maximumTotalCellSteps"]},
        "requestedMaxDt_s": protocol["maxDt_s"],
        "runtimeWork": {"acceptedSteps": 0, "acceptedCellSteps": 0},
        "output": protocol["output"], "partial": protocol["partial"],
        "fieldDirectory": protocol["fieldDirectory"], "rows": [], "stage": "running",
        "startedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    _write_json(PARTIAL_PATH, report)
    FIELD_DIRECTORY.mkdir(parents=True)
    counters = {"caseSteps": 0, "totalSteps": 0, "totalCellSteps": 0}
    started = time.perf_counter()
    limits = {"maximumStepsPerCase": protocol["maximumStepsPerCase"],
              "maximumTotalCellSteps": protocol["maximumTotalCellSteps"]}
    try:
        for case in cases:
            if lpbf_simulation.implementation_fingerprint() != fingerprint:
                raise RuntimeError("Solver implementation changed during refinement probe")
            counters["caseSteps"] = 0
            observed, final_states = [], []
            with _step_budget(counters, case["cells"], limits):
                result = lpbf_simulation.run(case["payload"], selected_time_observer=observed.append,
                    selected_time_s=protocol["expectedEventTime_s"], final_state_observer=final_states.append)
            if len(observed) != 1 or len(final_states) != 1:
                raise RuntimeError("Each mesh case must capture one scan-end and one final state")
            snapshot, final_state = observed[0], final_states[0]
            realized = _validate_completed_case(result, snapshot, final_state, case,
                                                protocol["expectedEventTime_s"])
            if counters["caseSteps"] != int(snapshot["step"]):
                raise RuntimeError("Runtime step guard differs from captured accepted-step history")
            section = fixed_event_liquidus_cross_section(
                snapshot["coordinates_m"], snapshot["temperature_K"],
                x_position_m=float(event["end"][0]), dx_m=float(case["domain"]["dx"]),
                liquidus_K=float(result["material"]["liquidus_K"]), substrate_interface_z_m=0.0)
            field_path = FIELD_DIRECTORY / f"mesh-{case['mesh_um']:02d}um.npz"
            field_artifact = write_selected_state_artifact(
                snapshot, field_path, protocol["maximumUncompressedFieldBytes"])
            report["rows"].append({
                "mesh_um": case["mesh_um"], "requestedMaxDt_s": protocol["maxDt_s"],
                "cells": case["cells"], "acceptedSteps": int(snapshot["step"]),
                "acceptedCellSteps": int(snapshot["step"] * case["cells"]),
                "resolvedInputSha256": case["inputSha256"],
                "actualEventTime_s": float(snapshot["time_s"]),
                "finalRunTime_s": float(final_state["time_s"]),
                "finalRunStep": len(final_state["accepted_dt_s"]),
                "discretization": realized["discretization"],
                "acceptedTimestepDistribution": realized["acceptedTimestepDistribution"],
                "sourceLimitedStepCount": realized["sourceLimitedStepCount"],
                "sourceTimestepRetries": realized["sourceTimestepRetries"],
                "energyBalance": realized["energyBalance"],
                "fixedEventCrossSectionThermalProxy": section,
                "fieldArtifact": field_artifact,
                "solver": realized["solver"], "model": realized["model"],
                "material": realized["material"],
            })
            report["runtimeWork"] = {"acceptedSteps": counters["totalSteps"],
                                     "acceptedCellSteps": counters["totalCellSteps"]}
            _write_json(PARTIAL_PATH, report)
        if lpbf_simulation.implementation_fingerprint() != fingerprint:
            raise RuntimeError("Solver implementation changed before refinement completion")
        report["stage"] = "completed"
        report["wallTime_s"] = time.perf_counter() - started
        report["finishedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        _write_json(OUTPUT_PATH, report)
        _write_json(PARTIAL_PATH, report)
        return report
    except Exception as error:
        report["stage"] = "failed"
        report["failure"] = {"type": type(error).__name__, "message": str(error)}
        report["runtimeWork"] = {"acceptedSteps": counters["totalSteps"],
                                 "acceptedCellSteps": counters["totalCellSteps"]}
        report["wallTime_s"] = time.perf_counter() - started
        _write_json(PARTIAL_PATH, report)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight-only", action="store_true",
                        help="Verify protocol, exact mesh domains, and identities without solving")
    args = parser.parse_args()
    if args.preflight_only:
        protocol, protocol_bytes, _scenario, event, cases = preflight()
        print(json.dumps({"protocolSha256": _sha256(protocol_bytes), "eventTime_s": event["end_s"],
            "meshes_um": [case["mesh_um"] for case in cases],
            "cells": [case["cells"] for case in cases],
            "predictedTotalCellSteps": protocol["predictedTotalCellSteps"]}, indent=2))
    else:
        report = execute()
        print(json.dumps({"stage": report["stage"], "rows": len(report["rows"]),
                          "output": str(OUTPUT_PATH)}, indent=2))


if __name__ == "__main__":
    main()
