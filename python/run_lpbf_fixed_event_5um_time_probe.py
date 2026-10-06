"""Bounded 5um fixed-event temporal diagnostic; preflight is the CLI default.

Reuse of the adaptive 100ns field requires its immutable report, input, material,
implementation, array hashes and accepted clock. New 50/25ns states are numerical
thermal proxies. No physics, acceptance threshold or historical result is changed.
"""
import argparse
import contextlib
import copy
import datetime
import hashlib
import json
import math
import subprocess
import time
import zipfile
from pathlib import Path

import numpy as np

import lpbf_simulation
from lpbf_core_physics import calculate_mesh_domain, scan_segments
from lpbf_fixed_scan_end_observation import FIELD_NAMES, write_selected_state_artifact
from lpbf_peak import fixed_event_liquidus_cross_section
from run_lpbf_fixed_event_mesh_refinement_probe import _validate_completed_case

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "docs/LPBF_FIXED_EVENT_5UM_TIME_2026-10-02_PROTOCOL.json"
PROTOCOL_ID = "lpbf-fixed-event-5um-time-2026-10-02-v1"


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def input_sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def safe_path(relative):
    """Reject escaping paths and symlink/junction ancestors before any I/O."""
    path = ROOT / relative
    if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("Artifact path must stay inside the repository")
    for parent in (path, *path.parents):
        if parent == ROOT:
            break
        if parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction()):
            raise ValueError("Artifact path contains a symlink or junction")
    if not path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("Artifact path escapes repository")
    return path


def validate_protocol(p):
    fixed = {"schemaVersion": 1, "protocolId": PROTOCOL_ID, "status": "diagnostic-only",
             "experimentalValidation": False, "convergenceConclusion": "inconclusive",
             "scenarioFile": "docs/LPBF_P4_CURRENT_MODEL_40W_SCENARIO_2026-09-25.json",
             "scenarioOverrides": {"mesh_um": 5, "cooling_s": 0}, "mesh_um": 5, "cooling_s": 0,
             "levels": [5e-8, 2.5e-8], "eventRule": "first-scan-segment-end",
             "expectedEventTime_s": 0.00024999999999999995,
             "expectedEventEndpoint_m": [9.999999999999999e-5, 0., 4e-5],
             "expectedDomain": {"nx": 88, "ny": 88, "nz": 68, "dx_um": 5.},
             "expectedCells": 526592, "predictedStepsByMaxDt": {"5e-08": 5000, "2.5e-08": 10000},
             "predictedTotalSteps": 15000, "predictedTotalCellSteps": 7_898_880_000,
             "maximumStepsByMaxDt": {"5e-08": 5500, "2.5e-08": 11000},
             "maximumTotalCellSteps": 8_688_768_000, "maximumCells": 600000,
             "maximumUncompressedFieldBytes": 40_000_000,
             "estimatedWorkingSetBytes": 539_230_208, "maximumSampledRssBytes": 805_306_368,
             "maximumWallTimeByMaxDt_s": {"5e-08": 1200, "2.5e-08": 2400},
             "commonZPlane_m": 20e-6, "substrateInterfaceZ_m": 0., "surface_m": 40e-6,
             "output": "docs/LPBF_FIXED_EVENT_5UM_TIME_2026-10-02.json",
             "partial": "docs/LPBF_FIXED_EVENT_5UM_TIME_2026-10-02.partial.json",
             "fieldDirectory": "docs/LPBF_FIXED_EVENT_5UM_TIME_FIELDS_2026-10-02"}
    extra = {"scope", "scenarioSha256", "expectedInputSha256ByMaxDt", "expectedImplementationFingerprint",
             "materialRevisionSha256", "baseline", "supportSourceSha256", "resourceAssumptions"}
    if not isinstance(p, dict) or set(p) != set(fixed) | extra:
        raise ValueError("Unexpected protocol schema")
    for key, expected in fixed.items():
        if p[key] != expected or isinstance(expected, bool) and type(p[key]) is not bool:
            raise ValueError(f"Frozen protocol differs: {key}")
    baseline = p["baseline"]
    if (set(baseline) != {"report", "reportSha256", "field", "fieldSha256", "inputSha256",
                          "materialRevisionSha256", "requestedMaxDt_s"}
            or baseline["report"] != "docs/LPBF_FIXED_EVENT_MESH_REFINEMENT_V2_2026-10-02.json"
            or baseline["field"] != "docs/LPBF_FIXED_EVENT_MESH_REFINEMENT_V2_FIELDS_2026-10-02/mesh-05um.npz"
            or baseline["requestedMaxDt_s"] != 1e-7):
        raise ValueError("Baseline identity differs from the registered historical artifact")
    if set(p["expectedInputSha256ByMaxDt"]) != {"1e-07", "5e-08", "2.5e-08"}:
        raise ValueError("Missing resolved input identities")
    if set(p["supportSourceSha256"]) != {
            "python/run_lpbf_fixed_event_mesh_refinement_probe.py", "python/lpbf_fixed_scan_end_observation.py"}:
        raise ValueError("Missing observer/support source identity")
    for name in ("output", "partial", "fieldDirectory"):
        safe_path(p[name])


def replay_steps(steps, target_time_s, requested_max_dt_s, tolerance_s):
    dt = np.asarray(steps, dtype=np.float64)
    if (dt.ndim != 1 or not dt.size or not np.isfinite(dt).all() or np.any(dt <= 0)
            or np.any(dt > requested_max_dt_s * (1+1e-12))
            or not math.isfinite(tolerance_s) or tolerance_s <= 0):
        raise ValueError("Invalid accepted timestep vector or replay tolerance")
    clock = 0.
    for value in dt:
        following = clock + float(value)
        if following <= clock or not math.isfinite(following):
            raise ValueError("Accepted steps do not advance the clock")
        clock = following
    if abs(clock-target_time_s) > tolerance_s:
        raise ValueError("Accepted timestep replay misses the fixed event")
    return {"count": int(dt.size), "replayedTime_s": clock, "targetTime_s": target_time_s,
            "targetMinusReplay_s": target_time_s-clock, "roundoffTolerance_s": tolerance_s}


def field_difference(reference, candidate, cell_volume_m3):
    reference, candidate = np.asarray(reference, dtype=float), np.asarray(candidate, dtype=float)
    if (reference.shape != candidate.shape or not reference.size or not np.isfinite(reference).all()
            or not np.isfinite(candidate).all() or not math.isfinite(cell_volume_m3) or cell_volume_m3 <= 0):
        raise ValueError("Field comparison requires matching finite fields and positive cell volume")
    difference = candidate-reference
    l2 = float(np.linalg.norm(difference.ravel()) * math.sqrt(cell_volume_m3))
    ref_l2 = float(np.linalg.norm(reference.ravel()) * math.sqrt(cell_volume_m3))
    return {"volumeL2Difference": l2, "relativeL2Difference": l2/ref_l2 if ref_l2 else (0. if l2 == 0 else None),
            "rmsDifference": float(np.sqrt(np.mean(difference**2))),
            "maximumAbsoluteDifference": float(np.max(np.abs(difference)))}


def phase_plane_audit(snapshot, dx_m, material, x_position_m=100e-6, surface_m=40e-6, z_plane_m=20e-6):
    xyz, temperature = snapshot["coordinates_m"], snapshot["temperature_K"]
    liquidus, solidus = material["liquidus_K"], material["solidus_K"]
    section = fixed_event_liquidus_cross_section(xyz, temperature, x_position_m, dx_m, liquidus, 0.)
    surface_section = fixed_event_liquidus_cross_section(xyz, temperature, x_position_m, dx_m, liquidus, surface_m)
    regions = {}
    for name, mask in (("substrate", xyz[:, 2] < 0.), ("powder", xyz[:, 2] > 0.)):
        values = temperature[mask]
        regions[name] = {"cells": int(mask.sum()), "maximumTemperature_K": float(values.max()) if values.size else None,
                         "solidusCells": int(np.count_nonzero(values >= solidus)),
                         "liquidusCells": int(np.count_nonzero(values >= liquidus)),
                         "liquidusVolume_m3": float(np.count_nonzero(values >= liquidus)*dx_m**3)}
    axes = [np.unique(xyz[:, dimension]) for dimension in range(3)]
    shape = tuple(len(axis) for axis in axes)
    if (section["status"] == "inconclusive" or math.prod(shape) != len(xyz)
            or not axes[0][0] <= x_position_m <= axes[0][-1]
            or not axes[2][0] <= z_plane_m <= axes[2][-1]):
        raise ValueError("Common plane requires ordered Cartesian cell-center support; no extrapolation")
    values = temperature.reshape(shape)

    def interpolate(axis, coordinate, array, dimension):
        upper = int(np.searchsorted(axis, coordinate))
        if axis[upper] == coordinate:
            return np.take(array, upper, axis=dimension)
        lower = upper-1
        f = (coordinate-axis[lower])/(axis[upper]-axis[lower])
        return (1-f)*np.take(array, lower, axis=dimension)+f*np.take(array, upper, axis=dimension)

    yz = interpolate(axes[0], x_position_m, values, 0)
    y_values = interpolate(axes[2], z_plane_m, yz, 1)
    molten = y_values >= liquidus
    common = {"operator": "fixed-x-z-linear-liquidus-width-v1", "status": "no-melt",
              "xPosition_m": x_position_m, "zPosition_m": z_plane_m, "width_um": None,
              "surfaceTreatment": "no-extrapolation", "acceptanceMetric": False}
    if molten[0] or molten[-1]:
        common.update(status="inconclusive", reason="Liquidus line reaches lateral domain support")
    elif molten.any():
        pair = molten[:-1] != molten[1:]
        lo, hi = y_values[:-1][pair], y_values[1:][pair]
        crossings = axes[1][:-1][pair] + (liquidus-lo)/(hi-lo)*np.diff(axes[1])[pair]
        if len(crossings) >= 2:
            common.update(status="thermal-proxy", width_um=float(np.ptp(crossings)*1e6))
    return {**regions, "solidus_K": solidus, "liquidus_K": liquidus,
            "lowestMoltenCellZ_m": float(xyz[temperature >= liquidus, 2].min()) if np.any(temperature >= liquidus) else None,
            "fixedEventCrossSection": section,
            "surfaceReferencedMeltDepth_um": surface_section["depth_um"],
            "substratePenetration_um": section["depth_um"],
            "surfaceReferenceZ_m": surface_m, "substrateReferenceZ_m": 0., "commonZWidth": common,
            "evidenceScope": "Same-time thermal proxy; powder melt and substrate penetration are distinct; no experimental validation"}


def check_sources(p):
    if lpbf_simulation.implementation_fingerprint() != p["expectedImplementationFingerprint"]:
        raise ValueError("Current implementation fingerprint differs from frozen diagnostic")
    for name, digest in p["supportSourceSha256"].items():
        if file_sha256(safe_path(name)) != digest:
            raise ValueError("Observer/support source fingerprint changed")


def make_case(scenario, dt, p):
    resolved, material = lpbf_simulation.validate({**scenario, "maxDt_s": dt})
    domain = calculate_mesh_domain(resolved)
    cells = math.prod(domain[k] for k in ("nx", "ny", "nz"))
    if (cells != p["expectedCells"] or cells > p["maximumCells"]
            or any(domain[k] != p["expectedDomain"][k] for k in ("nx", "ny", "nz"))
            or not math.isclose(domain["dx"]*1e6, 5., abs_tol=1e-12)
            or input_sha256(resolved) != p["expectedInputSha256ByMaxDt"][str(dt)]
            or material["materialRevisionSha256"] != p["materialRevisionSha256"]):
        raise ValueError("Resolved input/material/domain fingerprint differs from frozen diagnostic")
    return {"maxDt_s": dt, "payload": resolved, "material": material, "domain": domain, "cells": cells,
            "inputSha256": input_sha256(resolved), "predictedSteps": p["predictedStepsByMaxDt"].get(str(dt), 2920)}


def load_baseline(p, case):
    check_sources(p)
    identity = p["baseline"]
    report_path, field_path = safe_path(identity["report"]), safe_path(identity["field"])
    if file_sha256(report_path) != identity["reportSha256"] or file_sha256(field_path) != identity["fieldSha256"]:
        raise ValueError("Baseline report/field SHA differs from frozen identity")
    report = json.loads(report_path.read_bytes())
    candidates = [r for r in report["rows"] if r["mesh_um"] == 5 and r["requestedMaxDt_s"] == 1e-7]
    if len(candidates) != 1:
        raise ValueError("Baseline row is missing or ambiguous")
    row = candidates[0]
    if (report["stage"] != "completed" or report["experimentalValidation"] is not False
            or report["implementationFingerprintAtStart"] != p["expectedImplementationFingerprint"]
            or report["scenarioSha256"] != p["scenarioSha256"]
            or report["event"]["time_s"] != p["expectedEventTime_s"]
            or report["event"]["endpoint_m"] != p["expectedEventEndpoint_m"]
            or row["resolvedInputSha256"] != identity["inputSha256"]
            or row["resolvedInputSha256"] != case["inputSha256"]
            or row["material"]["materialRevisionSha256"] != identity["materialRevisionSha256"]
            or identity["materialRevisionSha256"] != case["material"]["materialRevisionSha256"]
            or row["material"]["materialId"] != "in718"
            or row["model"]["actualBackend"] != "numpy-reference"
            or row["model"]["modelId"] != "stationary-enthalpy-conduction-layer-conforming-v1"
            or row["solver"]["id"] != "enthalpy-fv-6"):
        raise ValueError("Baseline implementation/input/material/event identity is inconsistent")
    artifact = row["fieldArtifact"]
    if (artifact["sha256"] != identity["fieldSha256"] or field_path.stat().st_size != artifact["byteSize"]
            or artifact["uncompressedBytes"] > p["maximumUncompressedFieldBytes"]
            or artifact["byteSize"] > p["maximumUncompressedFieldBytes"]):
        raise ValueError("Baseline field byte/hash bound differs")
    with zipfile.ZipFile(field_path) as archive:
        if sum(item.file_size for item in archive.infolist()) > p["maximumUncompressedFieldBytes"] + 4096:
            raise ValueError("Baseline NPZ decompression exceeds field bound")
    with np.load(field_path, allow_pickle=False) as arrays:
        if set(arrays.files) != set(FIELD_NAMES):
            raise ValueError("Baseline field array names differ")
        snapshot = {name: arrays[name].copy() for name in FIELD_NAMES}
    for name, array in snapshot.items():
        if (array.dtype != np.dtype("<f8") or not np.isfinite(array).all()
                or hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest() != artifact["fieldSha256"][name]):
            raise ValueError("Baseline array hash/dtype/finite check failed")
    snapshot.update(target_time_s=artifact["targetTime_s"], time_s=artifact["actualTime_s"],
                    scheduler_time_s=artifact["schedulerTime_s"], time_difference_s=artifact["targetMinusActualTime_s"],
                    roundoff_tolerance_s=artifact["roundoffTolerance_s"], step=artifact["steps"],
                    initial_temperature_K=case["payload"]["preheat_C"]+273.15,
                    cell_volume_m3=case["domain"]["dx"]**3)
    validate_state(snapshot, row, case, p)
    return snapshot, row


def validate_state(snapshot, row, case, p):
    xyz, dt = snapshot["coordinates_m"], snapshot["accepted_dt_s"]
    cells, domain = case["cells"], case["domain"]
    if xyz.shape != (cells, 3) or any(snapshot[n].shape != (cells,) for n in FIELD_NAMES[1:4]):
        raise ValueError("Field dimensions differ from exact grid")
    axes = [(np.arange(domain["nx"])+.5)*domain["dx"]-domain["span"]/2,
            (np.arange(domain["ny"])+.5)*domain["dx"]-domain["ny"]*domain["dx"]/2,
            (np.arange(domain["nz"])+.5)*domain["dx"]-domain["substrate_depth"]]
    grid = xyz.reshape(domain["nx"], domain["ny"], domain["nz"], 3)
    for dimension, axis in enumerate(axes):
        shape = [1, 1, 1]
        shape[dimension] = len(axis)
        if not np.array_equal(grid[..., dimension], np.broadcast_to(axis.reshape(shape), grid.shape[:3])):
            raise ValueError("Field coordinates do not share the exact resolved grid")
    if (not all(np.isfinite(snapshot[n]).all() for n in FIELD_NAMES)
            or np.any(snapshot["temperature_K"] <= 0) or np.any(snapshot["density_kg_m3"] <= 0)):
        raise ValueError("Invalid finite field or density")
    if snapshot["cell_volume_m3"] != domain["dx"]**3:
        raise ValueError("Field cell volume differs from the resolved grid")
    initial_rho = float(lpbf_simulation.property_at(case["material"], snapshot["initial_temperature_K"], 1))
    expected_rho = initial_rho*np.where(xyz[:, 2] > 0., case["payload"]["packingFraction"], 1.)
    if not np.array_equal(snapshot["density_kg_m3"], expected_rho):
        raise ValueError("Field density differs from the fixed-reference powder/substrate partition")
    tolerance = min(1e-14, 2*math.ulp(p["expectedEventTime_s"])*(len(dt)+1))
    if snapshot["roundoff_tolerance_s"] > tolerance or snapshot["step"] != len(dt):
        raise ValueError("Field event roundoff/step bound differs")
    replay = replay_steps(dt, p["expectedEventTime_s"], case["maxDt_s"], snapshot["roundoff_tolerance_s"])
    if replay["replayedTime_s"] != snapshot["time_s"]:
        raise ValueError("Field state time differs from sequential replay")
    distribution = lpbf_simulation.summarize_accepted_timesteps(
        dt, case["maxDt_s"], row["sourceLimitedStepCount"], row["sourceTimestepRetries"])
    for key, value in distribution.items():
        reported = row["acceptedTimestepDistribution"].get(key)
        if isinstance(value, float):
            if reported is None or not math.isclose(value, reported, rel_tol=1e-10, abs_tol=1e-25):
                raise ValueError("Accepted timestep distribution differs from field history")
        elif value != reported:
            raise ValueError("Accepted timestep distribution differs from field history")
    stored = float(np.sum(snapshot["enthalpy_J_m3"], dtype=np.float64)*snapshot["cell_volume_m3"])
    energy = row["energyBalance"]
    input_energy = float(energy["input_J"])
    closure = abs(input_energy-energy["losses_J"]-stored)/max(input_energy, 1e-30)
    ledger_closure = abs(input_energy-energy["losses_J"]-energy["stored_J"])/max(input_energy, 1e-30)
    if (not math.isfinite(closure) or input_energy <= 0
            or not math.isclose(stored, energy["stored_J"], rel_tol=1e-10, abs_tol=1e-15)
            or not math.isclose(ledger_closure, energy["relativeError"], rel_tol=1e-8, abs_tol=1e-15)):
        raise ValueError("Field enthalpy/ledger energy closure is inconsistent")
    return {"acceptedClockReplay": replay, "independentFieldEnergy": {"storedFromField_J": stored,
            "ledgerStored_J": energy["stored_J"], "relativeClosureFromField": closure}}


def fresh_destinations(p):
    if any(safe_path(p[key]).exists() for key in ("output", "partial", "fieldDirectory")):
        raise FileExistsError("Diagnostic destinations already exist; use a new protocol identity")


def preflight():
    raw = PROTOCOL_PATH.read_bytes()
    p = json.loads(raw)
    validate_protocol(p)
    check_sources(p)
    scenario_bytes = safe_path(p["scenarioFile"]).read_bytes()
    if hashlib.sha256(scenario_bytes).hexdigest() != p["scenarioSha256"]:
        raise ValueError("Frozen scenario fingerprint changed")
    scenario = json.loads(scenario_bytes)["scenario"]
    scenario.update(p["scenarioOverrides"])
    segments, end = scan_segments(scenario)
    if len(segments) != 1 or end != p["expectedEventTime_s"] or segments[0]["end_s"] != end:
        raise ValueError("Scenario does not end at the frozen first scan event")
    baseline_case = make_case(scenario, 1e-7, p)
    baseline, row = load_baseline(p, baseline_case)
    cases = [make_case(scenario, dt, p) for dt in p["levels"]]
    fresh_destinations(p)
    return {"protocol": p, "protocolSha256": hashlib.sha256(raw).hexdigest(), "baseline": baseline,
            "baselineRow": row, "baselineCase": baseline_case, "cases": cases}


@contextlib.contextmanager
def step_budget(counters, case, p, clock=time.perf_counter, rss_reader=None):
    original = lpbf_simulation.source_limited_step
    started = clock()
    key = str(case["maxDt_s"])

    def guard(*args, **kwargs):
        if counters["caseSteps"] >= p["maximumStepsByMaxDt"][key]:
            raise RuntimeError("Per-case accepted-step ceiling reached")
        if counters["acceptedCellSteps"]+case["cells"] > p["maximumTotalCellSteps"]:
            raise RuntimeError("Total accepted cell-step ceiling reached")
        if clock()-started > p["maximumWallTimeByMaxDt_s"][key]:
            raise RuntimeError("Per-case wall-time ceiling reached at source-step guard")
        if rss_reader is not None:
            rss = int(rss_reader())
            counters["maximumSampledRssBytes"] = max(counters.get("maximumSampledRssBytes", 0), rss)
            if rss > p["maximumSampledRssBytes"]:
                raise RuntimeError("Sampled RSS ceiling reached")
        result = original(*args, **kwargs)
        counters["acceptedSteps"] += 1
        counters["caseSteps"] += 1
        counters["acceptedCellSteps"] += case["cells"]
        return result

    lpbf_simulation.source_limited_step = guard
    try:
        yield
    finally:
        lpbf_simulation.source_limited_step = original


def write_report(path, report, exclusive=False):
    with path.open("x" if exclusive else "w", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")


def execute():
    plan = preflight()
    p, baseline = plan["protocol"], plan["baseline"]
    runner_sha = file_sha256(__file__)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    report = {"schemaVersion": 1, "protocolId": PROTOCOL_ID, "protocolSha256": plan["protocolSha256"],
              "executionHeadCommit": head, "runnerSha256": runner_sha,
              "implementationFingerprint": p["expectedImplementationFingerprint"],
              "supportSourceSha256": p["supportSourceSha256"], "scenarioSha256": p["scenarioSha256"],
              "scope": p["scope"], "status": "diagnostic-only", "experimentalValidation": False,
              "convergenceConclusion": "inconclusive", "stage": "running", "rows": [],
              "resourcePreflight": {key: p[key] for key in p if key.startswith(("maximum", "predicted", "estimated"))},
              "resourceAssumptions": p["resourceAssumptions"],
              "baselineReuse": copy.deepcopy(p["baseline"]),
              "startedAt": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    counters = {"acceptedSteps": 0, "caseSteps": 0, "acceptedCellSteps": 0, "maximumSampledRssBytes": 0}
    snapshots = [baseline]
    baseline_row = copy.deepcopy(plan["baselineRow"])
    baseline_row.update(reused=True, freshRuntimeCellSteps=0,
                        phasePlaneAudit=phase_plane_audit(baseline, 5e-6, plan["baselineCase"]["material"]))
    baseline_row.update(validate_state(baseline, baseline_row, plan["baselineCase"], p))
    report["rows"].append(baseline_row)
    partial, output, fields = (safe_path(p[k]) for k in ("partial", "output", "fieldDirectory"))
    fresh_destinations(p)
    write_report(partial, report, exclusive=True)
    fields.mkdir()
    try:
        import psutil
        rss_reader = lambda: psutil.Process().memory_info().rss
        report["rssMeasurement"] = "process RSS sampled at source-step guards; not hard OS peak"
    except ImportError:
        rss_reader = None
        report["rssMeasurement"] = "unavailable; working set is a preflight estimate, no RSS cap enforcement"
    started = time.perf_counter()
    try:
        for case in plan["cases"]:
            check_sources(p)
            if file_sha256(__file__) != runner_sha or file_sha256(PROTOCOL_PATH) != plan["protocolSha256"]:
                raise ValueError("Runner/protocol identity changed")
            counters["caseSteps"] = 0
            selected, final = [], []
            case_started = time.perf_counter()
            with step_budget(counters, case, p, rss_reader=rss_reader):
                result = lpbf_simulation.run(case["payload"], selected_time_observer=selected.append,
                                             selected_time_s=p["expectedEventTime_s"], final_state_observer=final.append)
            if len(selected) != 1 or len(final) != 1:
                raise ValueError("Each run must capture exactly one selected and final state")
            snapshot = selected[0]
            row = _validate_completed_case(result, snapshot, final[0], case, p["expectedEventTime_s"])
            if (row["material"]["materialRevisionSha256"] != p["materialRevisionSha256"]
                    or row["material"]["materialId"] != "in718" or snapshot["step"] != counters["caseSteps"]
                    or not np.array_equal(snapshot["coordinates_m"], baseline["coordinates_m"])):
                raise ValueError("Run material/grid/guard identity differs")
            row.update(maxDt_s=case["maxDt_s"], cells=case["cells"], acceptedSteps=snapshot["step"],
                       reused=False, resolvedInputSha256=case["inputSha256"],
                       acceptedCellSteps=snapshot["step"]*case["cells"], wallTime_s=time.perf_counter()-case_started)
            row.update(validate_state(snapshot, row, case, p))
            row["phasePlaneAudit"] = phase_plane_audit(snapshot, case["domain"]["dx"], case["material"])
            row["fieldArtifact"] = write_selected_state_artifact(snapshot, fields/f"maxdt-{case['maxDt_s']:.4e}.npz",
                                                                   p["maximumUncompressedFieldBytes"])
            report["rows"].append(row)
            snapshots.append(snapshot)
            report["runtimeWork"] = dict(counters)
            write_report(partial, report)
        for row, snapshot in zip(report["rows"], snapshots):
            row["fieldDifferences"] = {
                label: {name: field_difference(reference[name], snapshot[name], snapshot["cell_volume_m3"])
                        for name in ("temperature_K", "enthalpy_J_m3")}
                for label, reference in (("verified100nsBaseline", baseline), ("25nsReference", snapshots[-1]))}
        check_sources(p)
        if file_sha256(__file__) != runner_sha or file_sha256(PROTOCOL_PATH) != plan["protocolSha256"]:
            raise ValueError("Runner/protocol identity changed before completion")
        report.update(stage="completed", runtimeWork=dict(counters), wallTime_s=time.perf_counter()-started,
                      finishedAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
        write_report(output, report, exclusive=True)
        write_report(partial, report)
        return report
    except Exception as error:
        report.update(stage="failed", runtimeWork=dict(counters), wallTime_s=time.perf_counter()-started,
                      failure={"type": type(error).__name__, "message": str(error)},
                      finishedAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
        write_report(partial, report)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Explicitly run the two expensive CPU cases")
    args = parser.parse_args()
    if args.execute:
        report = execute()
        print(json.dumps({"stage": report["stage"], "runtimeWork": report["runtimeWork"]}))
    else:
        plan = preflight()
        p = plan["protocol"]
        print(json.dumps({"status": "preflight-only", "protocolSha256": plan["protocolSha256"],
                          "verifiedBaselineSteps": plan["baseline"]["step"],
                          "newCases": [{k: c[k] for k in ("maxDt_s", "cells", "predictedSteps", "inputSha256")}
                                       for c in plan["cases"]], "predictedTotalCellSteps": p["predictedTotalCellSteps"],
                          "maximumTotalCellSteps": p["maximumTotalCellSteps"],
                          "baselinePhasePlaneAudit": phase_plane_audit(plan["baseline"], 5e-6,
                                                                       plan["baselineCase"]["material"]),
                          "resourceAssumptions": p["resourceAssumptions"]}, indent=2))


if __name__ == "__main__":
    main()
