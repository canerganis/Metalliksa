"""Run one resource-bounded 20 um P4 CPU scan-end diagnostic (v2).

This is a single numerical observation, not a convergence study or experiment.
The selected scan-end state and final energy ledger are captured independently.
"""

import argparse
from contextlib import contextmanager
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lpbf_simulation
from lpbf_core_physics import calculate_mesh_domain, scan_segments
from lpbf_fixed_scan_end_observation import (
    MAX_UNCOMPRESSED_FIELD_BYTES,
    OBSERVATION_OPERATOR,
    TEMPORAL_SELECTION,
    write_selected_state_artifact,
)
from lpbf_peak import interpolated_peak_melt_pool
from lpbf_simulation import IMPLEMENTATION_SOURCE_FILES, implementation_fingerprint, validate


PROTOCOL_PATH = ROOT / "docs" / "LPBF_P4_FIXED_SCAN_COARSE_V2_PROTOCOL_2026-09-28.json"
SCENARIO_PATH = ROOT / "docs" / "LPBF_P4_CURRENT_MODEL_40W_SCENARIO_2026-09-25.json"
PROTOCOL_ID = "lpbf-p4-fixed-scan-coarse-v2-2026-09-28"
MODEL_ID = "stationary-enthalpy-conduction-layer-conforming-v1"
SOLVER_ID = "enthalpy-fv-6"
BACKEND_ID = "numpy-reference"
RESOURCE_LIMITS = {
    "maximumCells": 100000,
    "estimatedBytesPerCell": 4096,
    "maximumEstimatedBytes": 536870912,
    "maximumSteps": 40000,
    "maximumCellSteps": 300000000,
    "maximumWallSeconds": 300,
    "maximumPeakRssBytes": 1073741824,
    "maximumUncompressedFieldBytes": MAX_UNCOMPRESSED_FIELD_BYTES,
}
RESOURCE_MONITORING = {
    "peakRss": "psutil RSS maximum sampled every 100 ms; sampled peak is not a hard OS memory limit; unmeasured if psutil is unavailable",
    "wallTime": "wall cap is checked at source-limiter boundaries; it is not a hard OS watchdog",
}
FROZEN_ACCEPTANCE = {
    "energyRelativeErrorMax": 0.01,
    "finestPairWidthDepthRelativeChangeMax": 0.05,
    "minimumLevelsPerAxis": 3,
    "maximumLevelsPerAxis": 6,
    "status": "inconclusive",
    "reason": "insufficient levels: protocol contains exactly one mesh and one timestep level",
    "existingThresholdsChanged": False,
}
FROZEN_DESTINATIONS = {
    "output": "docs/LPBF_P4_FIXED_SCAN_COARSE_V2_2026-09-28.json",
    "partial": "docs/LPBF_P4_FIXED_SCAN_COARSE_V2_2026-09-28.partial.json",
    "fieldDirectory": "docs/LPBF_P4_FIXED_SCAN_COARSE_V2_FIELDS_2026-09-28",
}


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _repo_path(relative, label):
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError(f"Invalid {label} path")
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"Invalid {label} path")
    path = ROOT / candidate
    current = ROOT
    for part in candidate.parts:
        current = current / part
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
            raise ValueError(f"{label} path contains a link")
    resolved = path.resolve()
    if ROOT not in resolved.parents:
        raise ValueError(f"{label} path is outside the repository")
    return resolved


def _read_protocol(protocol_path=PROTOCOL_PATH):
    protocol_path = Path(protocol_path).resolve(strict=True)
    if protocol_path != PROTOCOL_PATH.resolve():
        raise ValueError("Only the registered P4 fixed-scan coarse v2 protocol is accepted")
    raw = protocol_path.read_bytes()
    protocol = json.loads(raw)
    required = {
        "schemaVersion", "protocolId", "status", "scope", "experimentalValidation",
        "scenarioFile", "scenarioDocumentProtocolId", "scenarioSha256", "scenarioOverride",
        "expectedResolvedInputSha256", "expectedImplementationFingerprint", "runnerFile",
        "runnerSha256", "observationModuleFile", "observationModuleSha256", "resourceMonitoring",
        "expectedModelId", "expectedSolverId", "expectedActualBackend",
        "expectedMaterialId", "expectedMaterialRevisionSha256", "nominalScanEndTime_s",
        "finalTime_s", "temporalSelection", "observationOperator", "spatialOperator",
        "acceptance", "resourceLimits", "output", "partial", "fieldDirectory",
    }
    if (not isinstance(protocol, dict) or set(protocol) != required
            or type(protocol.get("schemaVersion")) is not int or protocol["schemaVersion"] != 1
            or protocol.get("protocolId") != PROTOCOL_ID
            or protocol.get("status") != "frozen-before-execution"
            or protocol.get("experimentalValidation") is not False
            or protocol.get("scenarioOverride") != {"mesh_um": 20, "maxDt_s": 2.5e-8}
            or protocol.get("temporalSelection") != TEMPORAL_SELECTION
            or protocol.get("observationOperator") != OBSERVATION_OPERATOR
            or protocol.get("spatialOperator") != "peak-liquidus-cell-edge-linear-contour-v1"
            or protocol.get("resourceLimits") != RESOURCE_LIMITS
            or protocol.get("resourceMonitoring") != RESOURCE_MONITORING
            or protocol.get("acceptance") != FROZEN_ACCEPTANCE
            or any(protocol.get(key) != value for key, value in FROZEN_DESTINATIONS.items())):
        raise ValueError("Unsupported, altered, or unfrozen P4 coarse v2 protocol")
    runner_rel = Path(__file__).resolve().relative_to(ROOT).as_posix()
    runner_sha = _sha256(Path(__file__).read_bytes())
    if protocol["runnerFile"] != runner_rel or protocol["runnerSha256"] != runner_sha:
        raise ValueError("P4 coarse v2 runner identity differs from protocol")
    _verify_observation_module(protocol)
    scenario_path = _repo_path(protocol["scenarioFile"], "Scenario")
    scenario_bytes = scenario_path.read_bytes()
    document = json.loads(scenario_bytes)
    if (scenario_path != SCENARIO_PATH.resolve()
            or _sha256(scenario_bytes) != protocol["scenarioSha256"]
            or not isinstance(document, dict)
            or document.get("protocolId") != protocol["scenarioDocumentProtocolId"]
            or not isinstance(document.get("scenario"), dict)):
        raise ValueError("Frozen P4 source scenario identity differs")
    baseline = document["scenario"]
    if (baseline.get("mode") != "standard" or baseline.get("backend") != "reference"
            or baseline.get("study") != "none" or baseline.get("surfaceMode") != "powder-layer"
            or baseline.get("material") != "Inconel 718" or baseline.get("power_W") != 40
            or baseline.get("mesh_um") != 5 or baseline.get("maxDt_s") != 2.5e-8
            or "measurements" in baseline):
        raise ValueError("Source scenario no longer matches the frozen 40 W CPU case")
    resolved_request = dict(baseline, **protocol["scenarioOverride"])
    p, material = validate(resolved_request)
    resolved_sha = _sha256(json.dumps(p, sort_keys=True, allow_nan=False).encode("utf-8"))
    if resolved_sha != protocol["expectedResolvedInputSha256"]:
        raise ValueError("Resolved 20 um scenario input identity differs")
    fingerprint = implementation_fingerprint()
    if fingerprint != protocol["expectedImplementationFingerprint"]:
        raise ValueError("Current solver source fingerprint differs from protocol")
    if (protocol["expectedModelId"] != MODEL_ID or protocol["expectedSolverId"] != SOLVER_ID
            or protocol["expectedActualBackend"] != BACKEND_ID
            or material.get("materialId") != protocol["expectedMaterialId"]
            or material.get("materialRevisionSha256") != protocol["expectedMaterialRevisionSha256"]):
        raise ValueError("Resolved solver or material identity differs from protocol")
    segments, final_time = scan_segments(p)
    selected_time = segments[0]["end_s"] if segments else None
    if (selected_time is None or selected_time != protocol["nominalScanEndTime_s"]
            or final_time != protocol["finalTime_s"]):
        raise ValueError("Frozen scan-end or final-energy capture time differs from resolved scan schedule")
    domain = calculate_mesh_domain(p)
    cells = int(domain["nx"] * domain["ny"] * domain["nz"])
    limits = protocol["resourceLimits"]
    lower_bound_steps = math.ceil(final_time / p["maxDt_s"])
    estimated_bytes = cells * limits["estimatedBytesPerCell"]
    lower_bound_cell_steps = cells * lower_bound_steps
    if (cells > limits["maximumCells"] or estimated_bytes > limits["maximumEstimatedBytes"]
            or lower_bound_steps > limits["maximumSteps"]
            or lower_bound_cell_steps > limits["maximumCellSteps"]):
        raise ValueError("P4 coarse v2 resource preflight exceeds a frozen limit")
    destinations = {}
    for key in ("output", "partial", "fieldDirectory"):
        destinations[key] = _repo_path(protocol[key], key)
    if (destinations["partial"] != destinations["output"].with_name(destinations["output"].stem + ".partial.json")
            or destinations["output"] == destinations["fieldDirectory"]
            or destinations["partial"] == destinations["fieldDirectory"]):
        raise ValueError("Output, partial and field destinations are not paired and distinct")
    temp = destinations["partial"].with_name(destinations["partial"].name + ".tmp")
    if any(path.exists() for path in (*destinations.values(), temp)):
        raise FileExistsError("P4 coarse v2 destinations already exist; evidence is never overwritten")
    return protocol, raw, scenario_bytes, p, material, segments, final_time, selected_time, domain, {
        "cells": cells,
        "estimatedBytes": estimated_bytes,
        "lowerBoundSteps": lower_bound_steps,
        "lowerBoundCellSteps": lower_bound_cell_steps,
        "maxDt_s": p["maxDt_s"],
    }, destinations


def _verify_observation_module(protocol):
    expected_path = "python/lpbf_fixed_scan_end_observation.py"
    if protocol.get("observationModuleFile") != expected_path:
        raise ValueError("Selected-state observation module path differs from protocol")
    path = _repo_path(expected_path, "Observation module")
    actual = _sha256(path.read_bytes())
    if actual != protocol.get("observationModuleSha256"):
        raise ValueError("Selected-state observation module hash differs from protocol")
    return actual


def preflight(protocol_path=PROTOCOL_PATH):
    """Check frozen identities, exact event times, output exclusivity and resource bounds only."""
    return _read_protocol(protocol_path)


def _write_new(path, payload):
    encoded = (json.dumps(payload, indent=2, allow_nan=False) + "\n").encode("utf-8")
    with Path(path).open("xb") as stream:
        stream.write(encoded)


def _replace_partial(path, payload):
    temporary = Path(path).with_name(Path(path).name + ".tmp")
    encoded = (json.dumps(payload, indent=2, allow_nan=False) + "\n").encode("utf-8")
    with temporary.open("xb") as stream:
        stream.write(encoded)
    temporary.replace(path)


def _resource_sampler(maximum_rss_bytes):
    """Best-effort peak RSS sampler; returns unmeasured when psutil is unavailable."""
    try:
        import psutil
        process = psutil.Process(os.getpid())
    except Exception:
        return None
    state = {"peakBytes": 0, "exceeded": False, "stop": threading.Event()}

    def sample():
        while not state["stop"].is_set():
            try:
                rss = int(process.memory_info().rss)
                state["peakBytes"] = max(state["peakBytes"], rss)
                if rss > maximum_rss_bytes:
                    state["exceeded"] = True
            except Exception:
                pass
            state["stop"].wait(.1)
    state["thread"] = threading.Thread(target=sample, daemon=True)
    state["thread"].start()
    return state


def _runtime_guard(counters, *, cells, limits, start, rss_state):
    original = lpbf_simulation.source_limited_step

    def guarded(*args, **kwargs):
        next_steps = counters["acceptedSteps"] + 1
        if next_steps > limits["maximumSteps"]:
            raise RuntimeError("P4 coarse v2 accepted-step limit reached before update")
        if next_steps * cells > limits["maximumCellSteps"]:
            raise RuntimeError("P4 coarse v2 cell-step limit reached before update")
        if time.perf_counter() - start > limits["maximumWallSeconds"]:
            raise TimeoutError("P4 coarse v2 wall-time limit reached before update")
        if rss_state is not None and rss_state["exceeded"]:
            raise MemoryError("P4 coarse v2 measured peak RSS limit reached")
        result = original(*args, **kwargs)
        counters["acceptedSteps"] = next_steps
        return result

    return guarded


@contextmanager
def _install_runtime_guard(counters, *, cells, limits, start, rss_state):
    original = lpbf_simulation.source_limited_step
    lpbf_simulation.source_limited_step = _runtime_guard(
        counters, cells=cells, limits=limits, start=start, rss_state=rss_state)
    try:
        yield
    finally:
        lpbf_simulation.source_limited_step = original


def _replay_clock(accepted_dt_s):
    clock = 0.0
    for dt in accepted_dt_s:
        dt = float(dt)
        next_clock = clock + dt
        if not math.isfinite(dt) or dt <= 0 or not math.isfinite(next_clock) or next_clock <= clock:
            raise ValueError("Selected capture contains an invalid accepted timestep sequence")
        clock = next_clock
    return clock


def run_protocol(protocol_path=PROTOCOL_PATH):
    (protocol, protocol_bytes, scenario_bytes, resolved, material, segments, final_time,
     selected_time, domain, resources, destinations) = preflight(protocol_path)
    fingerprint = protocol["expectedImplementationFingerprint"]
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()
    report = {
        "schemaVersion": 1,
        "protocolId": PROTOCOL_ID,
        "protocolSha256": _sha256(protocol_bytes),
        "runnerSha256": protocol["runnerSha256"],
        "observationModuleFile": protocol["observationModuleFile"],
        "observationModuleSha256AtStart": protocol["observationModuleSha256"],
        "resourceMonitoring": RESOURCE_MONITORING,
        "scenarioFile": protocol["scenarioFile"],
        "scenarioSha256": _sha256(scenario_bytes),
        "executionHeadCommit": head,
        "scope": protocol["scope"],
        "experimentalValidation": False,
        "validationStatus": "unvalidated",
        "convergenceStatus": "inconclusive",
        "convergenceReason": "insufficient levels: one coarse mesh/timestep case cannot establish convergence",
        "acceptance": protocol["acceptance"],
        "implementationFingerprintAtStart": fingerprint,
        "implementationSourceManifest": list(IMPLEMENTATION_SOURCE_FILES),
        "resolvedIdentity": {
            "inputSha256": protocol["expectedResolvedInputSha256"],
            "modelId": protocol["expectedModelId"],
            "solverId": protocol["expectedSolverId"],
            "actualBackend": protocol["expectedActualBackend"],
            "materialId": protocol["expectedMaterialId"],
            "materialRevisionSha256": protocol["expectedMaterialRevisionSha256"],
        },
        "resolvedOverrides": protocol["scenarioOverride"],
        "resourcePreflight": resources,
        "temporalSelection": TEMPORAL_SELECTION,
        "observationOperator": OBSERVATION_OPERATOR,
        "spatialOperator": protocol["spatialOperator"],
        "selectedTime_s": selected_time,
        "finalEnergyTime_s": final_time,
        "fieldDirectory": protocol["fieldDirectory"],
        "output": protocol["output"],
        "partial": protocol["partial"],
        "runtimeWork": {"acceptedSteps": 0, "acceptedCellSteps": 0},
        "wallTime_s": None,
        "peakRssBytes": "unmeasured",
        "rows": [],
        "stage": "running",
        "startedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    _write_new(destinations["partial"], report)
    selected_captures, final_energy_captures = [], []
    counters = {"acceptedSteps": 0}
    original_limiter = lpbf_simulation.source_limited_step
    rss = _resource_sampler(protocol["resourceLimits"]["maximumPeakRssBytes"])
    started = time.perf_counter()
    try:
        destinations["fieldDirectory"].mkdir()
        if implementation_fingerprint() != fingerprint:
            raise RuntimeError("Numerical source fingerprint changed before solve")

        def capture_final_energy(state):
            # This is the final 350 us state. It is distinct from the selected 250 us field,
            # whose callback occurs before that step's energy-ledger increment.
            final_energy_captures.append({
                "time_s": float(state["time_s"]),
                "steps": int(len(state["accepted_dt_s"])),
                "acceptedClock_s": _replay_clock(state["accepted_dt_s"]),
                "storedFromFinalEnthalpy_J": float(np.asarray(state["enthalpy_J_m3"]).sum())
                    * float(state["cell_volume_m3"]),
            })

        def capture_selected(snapshot):
            selected_captures.append(snapshot)

        payload = dict(resolved)
        with _install_runtime_guard(
                counters, cells=resources["cells"], limits=protocol["resourceLimits"],
                start=started, rss_state=rss):
            result = lpbf_simulation.run(payload, selected_time_observer=capture_selected,
                                         selected_time_s=selected_time,
                                         final_state_observer=capture_final_energy)
        report["wallTime_s"] = time.perf_counter() - started
        if rss is not None:
            rss["stop"].set()
            rss["thread"].join(timeout=2)
            report["peakRssBytes"] = rss["peakBytes"] or "unmeasured"
            if rss["exceeded"]:
                raise MemoryError("Measured peak RSS exceeded protocol limit")
        if (report["wallTime_s"] > protocol["resourceLimits"]["maximumWallSeconds"]
                or counters["acceptedSteps"] == 0
                or counters["acceptedSteps"] > protocol["resourceLimits"]["maximumSteps"]
                or counters["acceptedSteps"] * resources["cells"] > protocol["resourceLimits"]["maximumCellSteps"]):
            raise RuntimeError("P4 coarse v2 runtime work exceeded a frozen limit")
        if len(selected_captures) != 1 or len(final_energy_captures) != 1:
            raise ValueError("Expected exactly one selected-time and one final-energy capture")
        selected = selected_captures[0]
        replayed = _replay_clock(selected["accepted_dt_s"])
        if (selected["target_time_s"] != segments[0]["end_s"]
                or selected["target_time_s"] != selected_time
                or replayed != selected["time_s"]
                or abs(selected["time_difference_s"]) > selected["roundoff_tolerance_s"]):
            raise ValueError("Selected state does not replay to the first physical scan-segment end")

        actual_settings = result.get("settings", {})
        core = result.get("coreContract", {})
        result_material = result.get("material", {})
        if (actual_settings.get("mesh_um") != 20 or actual_settings.get("maxDt_s") != 2.5e-8
                or result.get("solver", {}).get("id") != SOLVER_ID
                or core.get("actualBackend") != BACKEND_ID
                or core.get("modelId") != MODEL_ID
                or result_material.get("materialId") != protocol["expectedMaterialId"]
                or result_material.get("materialRevisionSha256") != protocol["expectedMaterialRevisionSha256"]
                or result.get("provenance", {}).get("inputHash") != protocol["expectedResolvedInputSha256"]
                or result.get("provenance", {}).get("implementationHash") != fingerprint):
            raise ValueError("Executed solver, input, material or source identity differs from preflight")

        contour = interpolated_peak_melt_pool(
            selected["coordinates_m"], selected["temperature_K"],
            resolved["layer_um"] * 1e-6, resolved["scanAngle_deg"], domain["dx"],
            material["liquidus_K"],
        )
        contour["operator"] = protocol["spatialOperator"]
        contour["observationOperator"] = OBSERVATION_OPERATOR
        contour["temporalSelection"] = TEMPORAL_SELECTION
        contour["selectedTime_s"] = selected_time
        contour["evidenceScope"] = "Single CPU numerical thermal proxy; no convergence or experimental validation"
        field = write_selected_state_artifact(
            selected, destinations["fieldDirectory"] / "first-scan-end-250us.npz",
            protocol["resourceLimits"]["maximumUncompressedFieldBytes"],
        )
        field["path"] = f"{protocol['fieldDirectory']}/{field['path']}"
        final_capture = final_energy_captures[0]
        energy = result["energyBalance"]
        final_energy = {
            "captureTime_s": final_capture["time_s"],
            "requestedFinalTime_s": final_time,
            "acceptedSteps": final_capture["steps"],
            "acceptedClock_s": final_capture["acceptedClock_s"],
            "acceptedClockTolerance_s": min(1e-14, 2 * math.ulp(float(final_time)) * (final_capture["steps"] + 1)),
            "input_J": float(energy["input_J"]),
            "losses_J": float(energy["losses_J"]),
            "storedFromResult_J": float(energy["stored_J"]),
            "storedFromFinalEnthalpy_J": final_capture["storedFromFinalEnthalpy_J"],
            "relativeClosureError": float(energy["relativeError"]),
            "accountingConsistency": "pass" if math.isclose(
                final_capture["storedFromFinalEnthalpy_J"], float(energy["stored_J"]),
                rel_tol=1e-10, abs_tol=1e-12) else "failed",
            "scope": "Final-state solver accounting consistency; not convergence or physical validation",
        }
        if (final_capture["time_s"] != final_time
                or abs(final_capture["acceptedClock_s"] - final_time) > final_energy["acceptedClockTolerance_s"]):
            raise ValueError("Separate final-energy capture did not end at 350 us")
        if final_energy["accountingConsistency"] != "pass":
            raise ValueError("Final-state enthalpy disagrees with solver energy ledger")

        row = {
            "case": {"mesh_um": 20, "requestedMaxDt_s": 2.5e-8,
                     "targetRule": "first real scan-segment end from scan_segments(resolved)[0]"},
            "status": "completed",
            "settings": {key: actual_settings[key] for key in (
                "power_W", "speed_mm_s", "beamDiameter_um", "preheat_C", "layer_um",
                "hatch_um", "mesh_um", "maxDt_s", "tracks", "layers", "strategy")},
            "resolvedIdentity": report["resolvedIdentity"],
            "selectedObservation": contour,
            "selectedFieldArtifact": field,
            "finalEnergyCapture": final_energy,
            "runtimeWork": {"acceptedSteps": counters["acceptedSteps"],
                            "acceptedCellSteps": counters["acceptedSteps"] * resources["cells"]},
            "numericalDiagnostics": result.get("numericalDiagnostics"),
            "energyBalance": energy,
            "convergenceStatus": "inconclusive",
            "convergenceReason": "insufficient levels: exactly one 20 um mesh and one fixed timestep were executed",
            "experimentalValidation": False,
        }
        report["rows"] = [row]
        report["runtimeWork"] = row["runtimeWork"]
        if implementation_fingerprint() != fingerprint:
            raise RuntimeError("Numerical source fingerprint changed during solve")
        final_protocol_bytes = PROTOCOL_PATH.read_bytes()
        final_scenario_bytes = SCENARIO_PATH.read_bytes()
        final_runner_sha = _sha256(Path(__file__).read_bytes())
        final_observation_module_sha = _verify_observation_module(protocol)
        report.update({
            "implementationFingerprintAtEnd": implementation_fingerprint(),
            "sourceFingerprintStable": implementation_fingerprint() == fingerprint,
            "scenarioBytesStable": _sha256(final_scenario_bytes) == _sha256(scenario_bytes),
            "protocolBytesStable": _sha256(final_protocol_bytes) == _sha256(protocol_bytes),
            "runnerSha256AtEnd": final_runner_sha,
            "runnerBytesStable": final_runner_sha == protocol["runnerSha256"],
            "observationModuleSha256AtEnd": final_observation_module_sha,
            "observationModuleBytesStable": final_observation_module_sha == protocol["observationModuleSha256"],
            "status": "inconclusive",
            "integrityStatus": "pass" if (
                implementation_fingerprint() == fingerprint
                and _sha256(final_scenario_bytes) == _sha256(scenario_bytes)
                and _sha256(final_protocol_bytes) == _sha256(protocol_bytes)
                and final_runner_sha == protocol["runnerSha256"]
                and final_observation_module_sha == protocol["observationModuleSha256"]
            ) else "failed",
            "stage": "completed",
            "completedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })
        if report["integrityStatus"] != "pass":
            report["status"] = "failed"
        _replace_partial(destinations["partial"], report)
        _write_new(destinations["output"], report)
        return report
    except BaseException as error:
        report["wallTime_s"] = report["wallTime_s"] or time.perf_counter() - started
        report["runtimeWork"] = {"acceptedSteps": counters["acceptedSteps"],
                                 "acceptedCellSteps": counters["acceptedSteps"] * resources["cells"]}
        report.update(stage="failed", status="failed", integrityStatus="not-completed",
                      error=f"{type(error).__name__}: {error}"[:1000],
                      implementationFingerprintAtFailure=implementation_fingerprint(),
                      sourceFingerprintStableAtFailure=implementation_fingerprint() == fingerprint,
                      scenarioBytesStableAtFailure=_sha256(SCENARIO_PATH.read_bytes()) == _sha256(scenario_bytes),
                      protocolBytesStableAtFailure=_sha256(PROTOCOL_PATH.read_bytes()) == _sha256(protocol_bytes),
                      observationModuleSha256AtFailure=_sha256(_repo_path(
                          protocol["observationModuleFile"], "Observation module").read_bytes()),
                      observationModuleBytesStableAtFailure=_sha256(_repo_path(
                          protocol["observationModuleFile"], "Observation module").read_bytes())
                          == protocol["observationModuleSha256"],
                      failedAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
        try:
            _replace_partial(destinations["partial"], report)
        except Exception:
            pass
        raise
    finally:
        lpbf_simulation.source_limited_step = original_limiter
        if rss is not None:
            rss["stop"].set()
            rss["thread"].join(timeout=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight-only", action="store_true", help="validate frozen inputs and bounds without solving")
    args = parser.parse_args()
    if args.preflight_only:
        preflight()
        print(json.dumps({"status": "preflight-pass", "solveStarted": False}, indent=2))
    else:
        report = run_protocol()
        print(json.dumps({"status": report["status"], "integrityStatus": report["integrityStatus"],
                          "output": report["output"]}, indent=2))
