"""Incremental 12.5 ns local diagnostic; default CLI performs preflight only."""
import argparse
import datetime
import hashlib
import json
import math
import os
import subprocess
import time
import uuid
import zipfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import lpbf_simulation
import run_lpbf_fixed_event_time_history_probe as old
from lpbf_core_physics import calculate_mesh_domain, scan_segments

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "docs/LPBF_FIXED_EVENT_TIME_REFINEMENT_2026-10-02_PROTOCOL.json"
PROTOCOL_ID = "lpbf-fixed-event-time-refinement-5um-12_5ns-2026-10-02-v1"
IMPLEMENTATION = "d7e5c4e3d5f0a59c4b955e0e1ca29f624fe6249c4e7cd1522e84ed1a87249315"
VALUES = old.VALUES
HISTORY_NAMES = ("time_s", "accepted_dt_s", "values", "ever", "cell_indices_ijk", "coordinates_m")
DIAGNOSTIC = {"diagnosticOnly": True, "experimentalValidation": False,
              "solverValidationStatus": "unvalidated", "convergenceStatus": "inconclusive",
              "convergenceConclusion": "inconclusive", "NIST": "unavailable"}


def _load_psutil():
    try:
        import psutil
    except ImportError as exc:
        raise RuntimeError("psutil is required for fail-closed sampled RSS guards") from exc
    return psutil


def safe_path(relative):
    if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("Artifact path must stay inside repository")
    path = ROOT / relative
    for ancestor in (path, *path.parents):
        if ancestor == ROOT:
            break
        if ancestor.is_symlink() or (hasattr(ancestor, "is_junction") and ancestor.is_junction()):
            raise ValueError("Artifact path contains symlink or junction")
    if not path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("Artifact path escapes repository")
    return path


def _validate_protocol(p):
    fixed = {"schemaVersion": 1, "protocolId": PROTOCOL_ID, "status": "diagnostic-only",
             "experimentalValidation": False, "convergenceConclusion": "inconclusive",
             "scenarioFile": "docs/LPBF_P4_CURRENT_MODEL_40W_SCENARIO_2026-09-25.json",
             "scenarioOverrides": {"mesh_um": 5, "cooling_s": 0}, "mesh_um": 5,
             "levels": [5e-8, 2.5e-8, 1.25e-8],
             "expectedImplementationFingerprint": IMPLEMENTATION,
             "expectedEventTime_s": .00024999999999999995,
             "expectedEventEndpoint_m": [9.999999999999999e-5, 0., 4e-5],
             "expectedDomain": {"nx": 88, "ny": 88, "nz": 68, "dx_um": 5.},
             "expectedCells": 526592, "maximumCells": 600000,
             "expectedStepsByMaxDt": {"5e-08": 5000, "2.5e-08": 10000, "1.25e-08": 20000},
             "maximumStepsByMaxDt": {"5e-08": 5500, "2.5e-08": 11000, "1.25e-08": 22788},
             "maximumTotalCellSteps": 12000000000, "maximumSampledRssBytes": 805306368,
             "maximumWallTimeByMaxDt_s": {"5e-08": 1200, "2.5e-08": 2400, "1.25e-08": 3000},
             "maximumHistoryBytes": 50000000, "maximumPriorFieldBytes": 40000000,
             "centers_um": [[-67.5, -2.5, 2.5], [77.5, -2.5, 7.5], [77.5, 2.5, 7.5]],
             "neighborRule": "center-and-six-face-neighbors", "canonicalCheckpointCount": 5000,
             "baselineEverMismatchCheckpointCells": 2695,
             "historyReport": "docs/LPBF_FIXED_EVENT_TIME_HISTORY_2026-10-02.json",
             "output": "docs/LPBF_FIXED_EVENT_TIME_REFINEMENT_2026-10-02.json",
             "partial": "docs/LPBF_FIXED_EVENT_TIME_REFINEMENT_2026-10-02.partial.json",
             "historyDirectory": "docs/LPBF_FIXED_EVENT_TIME_REFINEMENT_2026-10-02_FIELDS"}
    fixed.update({
        "scenarioSha256": "2abec47f9d35c02158ea2e06876e3ca06c3ba5ba9243f1ddccaa94ef64752ea6",
        "priorReport": "docs/LPBF_FIXED_EVENT_5UM_TIME_2026-10-02.json",
        "priorReportSha256": "a509d8e8e67021956414be013aae54c52569f0c43c0db04dbad17a6423738a4d",
        "priorImplementationFingerprint": "d5eae56b9bd1ef0ab241153eb44efe7a1652c41f1aa50a7b652ee5a9e11ac2fe",
        "priorFieldDirectory": "docs/LPBF_FIXED_EVENT_5UM_TIME_FIELDS_2026-10-02",
        "priorFieldSha256ByMaxDt": {"5e-08": "1a771da9f6f873a27bd68fadd2a43eb3671bc67549acc253171aea0c1812bd23",
                                   "2.5e-08": "eeda2dca62f823ed250f6818de5bf1afd6b6a4cf9362a2ccd60fa29ef66bfacd"},
        "materialRevisionSha256": "5c9179e947ca19c3128e78e6ab9ce005c9b0ee6f86a8e6b579d368077b909749",
        "historyReportSha256": "b5adeb9582b29b4c2d9def01695ccf780763ef4925032c5d02ee6209babd954b",
        "historyArchiveSha256ByMaxDt": {"5e-08": "d82faa7c1eaad34600707ca1619fd8848b9223feee55757104be4b7a35ce434b",
                                        "2.5e-08": "74a6f40a17e8833ea63e065426807be0ec60184beb75438481c5c95e5b8f05b6"},
        "expectedInputSha256ByMaxDt": {"5e-08": "eb428f6741a6803fd3705526801c5a12255861a7aa9db0a66b3edafd9b099a28",
                                      "2.5e-08": "a1ef98548edfd1aee7ec9386fe8f3b034917fdc887492b316c226e654c4a403e",
                                      "1.25e-08": "14728b27c42faadecd6beb315b2c20cc473ba7b1e787b18c3cd715910fd7d4fd"}})
    extra = {"scope", "scenarioSha256", "priorReport", "priorReportSha256",
             "priorImplementationFingerprint", "priorFieldDirectory", "priorFieldSha256ByMaxDt",
             "materialRevisionSha256", "expectedInputSha256ByMaxDt", "resourceAssumptions",
             "historyReportSha256", "historyArchiveSha256ByMaxDt", "historyArraySha256ByMaxDt",
             "orderedSelectedCells"}
    if not isinstance(p, dict) or set(p) != set(fixed) | extra:
        raise ValueError("Unexpected refinement protocol schema")
    for key, value in fixed.items():
        if p[key] != value or isinstance(value, bool) and type(p[key]) is not bool:
            label = "fixed timestep" if key == "levels" else "cell-step" if key == "maximumTotalCellSteps" else key
            raise ValueError(f"Frozen refinement protocol differs: {label}")
    for key in ("scenarioSha256", "priorReportSha256", "priorImplementationFingerprint",
                "materialRevisionSha256", "historyReportSha256"):
        _hash_string(p[key])
    for key, keys in (("expectedInputSha256ByMaxDt", {"5e-08", "2.5e-08", "1.25e-08"}),
                      ("priorFieldSha256ByMaxDt", {"5e-08", "2.5e-08"}),
                      ("historyArchiveSha256ByMaxDt", {"5e-08", "2.5e-08"})):
        if set(p[key]) != keys:
            raise ValueError("Incomplete frozen identities")
        for value in p[key].values():
            _hash_string(value)
    if set(p["historyArraySha256ByMaxDt"]) != {"5e-08", "2.5e-08"}:
        raise ValueError("Incomplete history array identities")
    for hashes in p["historyArraySha256ByMaxDt"].values():
        if set(hashes) != set(HISTORY_NAMES):
            raise ValueError("Incomplete history array identities")
        for value in hashes.values():
            _hash_string(value)
    for name in ("scenarioFile", "priorReport", "priorFieldDirectory", "historyReport",
                 "output", "partial", "historyDirectory"):
        safe_path(p[name])


def _hash_string(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("Invalid frozen sha256")


def _array_hash(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def fresh_destinations(p):
    if any(safe_path(p[name]).exists() for name in ("output", "partial", "historyDirectory")):
        raise FileExistsError("Refinement destinations already exist")


def _validate_history(a, max_dt, event_time, expected_steps=None):
    n = len(a["time_s"])
    shapes = {"time_s": (n,), "accepted_dt_s": (n,), "values": (n, 19, 6),
              "ever": (n, 19, 2), "cell_indices_ijk": (19, 3), "coordinates_m": (19, 3)}
    if n == 0 or expected_steps is not None and n != expected_steps:
        raise ValueError("History accepted-step count differs")
    for name, shape in shapes.items():
        dtype = np.dtype("bool") if name == "ever" else np.dtype("<i4") if name == "cell_indices_ijk" else np.dtype("<f8")
        if a[name].shape != shape or a[name].dtype != dtype or not np.isfinite(a[name]).all():
            raise ValueError(f"History dtype, shape or finite validity differs: {name}")
    clocks, dt = a["time_s"], a["accepted_dt_s"]
    if (np.any(dt <= 0) or np.any(dt > max_dt*(1+1e-12)) or np.any(np.diff(clocks) <= 0)
            or not np.allclose(clocks, np.cumsum(dt), atol=1e-14, rtol=0)
            or abs(clocks[-1]-event_time) > 1e-14):
        raise ValueError("History accepted-step clock chain differs")
    ever = a["ever"]
    if (ever[0, :, 0].any() or np.any(ever[:, :, 0] & ~ever[:, :, 1])
            or not np.array_equal(ever[1:, :, 0], ever[:-1, :, 1])
            or np.any(a["values"][:, :, 0] <= 0) or np.any(a["values"][:, :, 2] <= 0)):
        raise ValueError("History ever-liquidus chain or physical scalars invalid")


def _read_history(path, archive_hash, array_hashes, max_dt, event_time, expected_steps, limit):
    if path.stat().st_size > limit or old.sha256_file(path) != archive_hash:
        raise ValueError("Frozen history archive changed")
    with zipfile.ZipFile(path) as z:
        members = z.infolist()
        if (len(members) != 6 or set(i.filename for i in members) != {n+'.npy' for n in HISTORY_NAMES}
                or sum(i.file_size for i in members) > limit + 4096
                or any(i.flag_bits & 1 for i in members)):
            raise ValueError("History archive members or decompression exceeds bound")
    with np.load(path, allow_pickle=False) as archive:
        a = {name: archive[name].copy() for name in HISTORY_NAMES}
    _validate_history(a, max_dt, event_time, expected_steps)
    if any(_array_hash(a[name]) != array_hashes[name] for name in HISTORY_NAMES):
        raise ValueError("Frozen history array hash changed")
    return a


def _matches(canonical, clock):
    if len(clock) == 0 or np.any(np.diff(clock) <= 0) or np.any(np.diff(canonical) <= 0):
        return None
    right = np.clip(np.searchsorted(clock, canonical), 0, len(clock)-1)
    left = np.maximum(right-1, 0)
    if np.any((left != right) & (abs(clock[left]-canonical) == abs(clock[right]-canonical))):
        return None
    index = np.where(abs(clock[left]-canonical) < abs(clock[right]-canonical), left, right)
    if np.any(abs(clock[index]-canonical) > 1e-14) or np.any(np.diff(index) <= 0):
        return None
    return index


def transition_summary(arrays, event_time):
    rows = []
    for col, index in enumerate(arrays["cell_indices_ijk"]):
        crossings = np.flatnonzero(arrays["ever"][:, col, 1])
        crossing = float(arrays["time_s"][crossings[0]]) if len(crossings) else None
        rows.append({"indices_ijk": index.tolist(), "crossingTime_s": crossing,
                     "censoredAtEvent": crossing is None, "eventTime_s": float(event_time)})
    return rows


def compare_canonical_histories(old50_arrays, old25_arrays, new_arrays, event_time):
    a, b, c = old50_arrays, old25_arrays, new_arrays
    for other in (b, c):
        if not np.array_equal(a["cell_indices_ijk"], other["cell_indices_ijk"]) or not np.array_equal(a["coordinates_m"], other["coordinates_m"]):
            raise ValueError("Local history physical grids differ")
    ib, ic = _matches(a["time_s"], b["time_s"]), _matches(a["time_s"], c["time_s"])
    if any(len(x["time_s"]) == 0 or abs(x["time_s"][-1]-event_time) > 1e-14 for x in (a, b, c)):
        ib, ic = None, None
    result = {**DIAGNOSTIC, "comparisonStatus": "inconclusive", "primaryMetricStatus": "inconclusive",
              "baselineEverMismatchCheckpointCells": None, "refinementEverMismatchCheckpointCells": None,
              "baselineEverMismatchFraction": None, "refinementEverMismatchFraction": None,
              "matchedPhysicalCheckpoints": 0, "possibleCheckpointCellPairs": int(len(a["time_s"])*len(a["cell_indices_ijk"])),
              "missingCanonicalTimestamp": ib is None or ic is None,
              "finalEverMismatchCells": int(np.count_nonzero(b["ever"][-1, :, 1] != c["ever"][-1, :, 1])),
              "comparisonRule": "unique monotonic nearest accepted timestamps; atol=1e-14 rtol=0; no interpolation or dropped checkpoints"}
    transitions = []
    for left, right in zip(transition_summary(b, event_time), transition_summary(c, event_time)):
        l, r = left["crossingTime_s"], right["crossingTime_s"]
        transitions.append({"indices_ijk": left["indices_ijk"], "crossing25ns": left,
                            "crossing12_5ns": right,
                            "status": "both_absent" if l is None and r is None else "one_sided_crossing" if l is None or r is None else "both_present",
                            "timeDelta_s": r-l if l is not None and r is not None else None})
    result["transitionComparison"] = transitions
    if ib is None or ic is None:
        return result
    baseline = int(np.count_nonzero(a["ever"][:, :, 1] != b["ever"][ib, :, 1]))
    refined = int(np.count_nonzero(b["ever"][ib, :, 1] != c["ever"][ic, :, 1]))
    result.update(comparisonStatus="comparable", baselineEverMismatchCheckpointCells=baseline,
                  refinementEverMismatchCheckpointCells=refined,
                  matchedPhysicalCheckpoints=int(len(ib)),
                  primaryMetricStatus="localDiagnosticDecrease" if refined < baseline else "noDecrease",
                  baselineEverMismatchFraction=baseline/result["possibleCheckpointCellPairs"],
                  refinementEverMismatchFraction=refined/result["possibleCheckpointCellPairs"],
                  maximumAbsoluteEnthalpyDifference25vs12_5_J_m3=float(np.max(abs(b["values"][ib, :, 1]-c["values"][ic, :, 1]))),
                  maximumAbsoluteTemperatureDifference25vs12_5_K=float(np.max(abs(b["values"][ib, :, 0]-c["values"][ic, :, 0]))))
    return result


def preflight(protocol_path=PROTOCOL_PATH):
    psutil = _load_psutil()
    psutil.Process().memory_info()  # unavailable process monitoring fails before solving
    raw = Path(protocol_path).read_bytes()
    p = json.loads(raw)
    _validate_protocol(p)
    fresh_destinations(p)
    if lpbf_simulation.implementation_fingerprint() != IMPLEMENTATION:
        raise ValueError("Frozen numerical implementation changed")
    for file_key, hash_key in (("scenarioFile", "scenarioSha256"), ("priorReport", "priorReportSha256"), ("historyReport", "historyReportSha256")):
        if old.sha256_file(safe_path(p[file_key])) != p[hash_key]:
            raise ValueError(f"Frozen file identity changed: {file_key}")
    scenario = json.loads(safe_path(p["scenarioFile"]).read_bytes())["scenario"]
    scenario.update(p["scenarioOverrides"])
    segments, end = scan_segments(scenario)
    if len(segments) != 1 or end != p["expectedEventTime_s"] or segments[0]["end"] != p["expectedEventEndpoint_m"][:2] or abs(scenario["layer_um"]*1e-6-p["expectedEventEndpoint_m"][2]) > 1e-15:
        raise ValueError("Frozen event changed")
    prior = json.loads(safe_path(p["historyReport"]).read_bytes())
    if (prior["stage"] != "completed" or prior["experimentalValidation"] is not False
            or prior["implementationFingerprint"] != IMPLEMENTATION
            or prior["priorImplementationFingerprint"] != p["priorImplementationFingerprint"]
            or prior["priorReportSha256"] != p["priorReportSha256"]
            or prior["selectedCells"] != p["orderedSelectedCells"]):
        raise ValueError("Frozen history report identity differs")
    ancestry = json.loads(safe_path(p["priorReport"]).read_bytes())
    if (ancestry["stage"] != "completed" or ancestry["experimentalValidation"] is not False
            or ancestry["implementationFingerprint"] != p["priorImplementationFingerprint"]
            or ancestry["scenarioSha256"] != p["scenarioSha256"]):
        raise ValueError("Frozen ancestry report identity differs")
    histories = []
    case = None
    for dt in p["levels"]:
        key = str(dt)
        payload, material = lpbf_simulation.validate({**scenario, "maxDt_s": dt})
        domain = calculate_mesh_domain(payload)
        cells = math.prod(domain[k] for k in ("nx", "ny", "nz"))
        input_sha = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
        indices, positions, centers = old.selected_cells(domain, p["centers_um"])
        selected = [{"indices_ijk": list(i), "coordinate_m": c} for i, c in zip(indices, positions)]
        if (cells != p["expectedCells"] or cells > p["maximumCells"]
                or any(domain[k] != p["expectedDomain"][k] for k in ("nx", "ny", "nz"))
                or abs(domain["dx"]*1e6-5) > 1e-12 or len(indices) != 19
                or selected != p["orderedSelectedCells"] or input_sha != p["expectedInputSha256ByMaxDt"][key]
                or material["materialRevisionSha256"] != p["materialRevisionSha256"]):
            raise ValueError("Frozen input, material, grid or ordered cells changed")
        if dt == 1.25e-8:
            case = {"dt": dt, "key": key, "payload": payload, "material": material,
                    "domain": domain, "cells": cells, "indices": indices, "positions": positions,
                    "centerIndices": centers, "inputSha256": input_sha}
            continue
        rows = [r for r in prior["rows"] if r["maxDt_s"] == dt]
        if len(rows) != 1 or rows[0]["resolvedInputSha256"] != input_sha or rows[0]["acceptedSteps"] != p["expectedStepsByMaxDt"][key]:
            raise ValueError("Frozen prior history row changed")
        artifact = rows[0]["historyArtifact"]
        expected_path = f"docs/LPBF_FIXED_EVENT_TIME_HISTORY_FIELDS_2026-10-02/maxdt-{dt:.4e}.npz"
        if artifact["path"] != expected_path or artifact["sha256"] != p["historyArchiveSha256ByMaxDt"][key]:
            raise ValueError("Frozen archive report identity changed")
        a = _read_history(safe_path(expected_path), artifact["sha256"], p["historyArraySha256ByMaxDt"][key], dt, end, p["expectedStepsByMaxDt"][key], p["maximumHistoryBytes"])
        if not np.array_equal(a["cell_indices_ijk"], np.asarray(indices, dtype="<i4")) or not np.array_equal(a["coordinates_m"], np.asarray(positions)):
            raise ValueError("Archive ordered cells changed")
        histories.append(a)
    baseline = compare_canonical_histories(histories[0], histories[1], histories[1], end)
    if baseline["matchedPhysicalCheckpoints"] != 5000 or baseline["baselineEverMismatchCheckpointCells"] != 2695:
        raise ValueError("Frozen canonical baseline differs from 2695 mismatches")
    size = 22788*(16+19*6*8+19*2)+19*3*12
    if size > p["maximumHistoryBytes"]:
        raise ValueError("Preallocated history exceeds bound")
    final_size = 526592*6*8+22788*8+19+8
    if final_size > p["maximumPriorFieldBytes"] or 20000*526592 > p["maximumTotalCellSteps"]:
        raise ValueError("Expected final fields or accepted cell-step work exceed bound")
    if 2218.463331600011 > p["maximumWallTimeByMaxDt_s"]["1.25e-08"]:
        raise ValueError("Estimated wall time exceeds bound")
    return {"protocol": p, "protocolSha256": hashlib.sha256(raw).hexdigest(), "case": case,
            "histories": histories, "historyMaximumUncompressedBytes": size,
            "baseline": baseline, "solverLaunched": False}


def _write_json(path, report, exclusive=False):
    content = json.dumps(report, indent=2, allow_nan=False)+"\n"
    if not exclusive:
        temporary = path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
        try:
            with temporary.open("x", encoding="utf-8") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()
        return
    created = False
    try:
        with path.open("x", encoding="utf-8") as stream:
            created = True
            stream.write(content)
    except Exception:
        if created:
            path.unlink()
        raise


def execute(protocol_path=PROTOCOL_PATH):
    plan = preflight(protocol_path)
    p, case = plan["protocol"], plan["case"]
    partial, out, directory = (safe_path(p[k]) for k in ("partial", "output", "historyDirectory"))
    counters = {"acceptedSteps": 0, "acceptedCellSteps": 0, "sourceTimestepRetries": 0,
                "sourceLimitedSteps": 0, "maximumSampledRssBytes": 0, "lastTime_s": 0.}
    report = {**DIAGNOSTIC, "schemaVersion": 1, "protocolId": PROTOCOL_ID,
              "status": "diagnostic-only", "stage": "running", "scope": p["scope"],
              "protocolSha256": plan["protocolSha256"], "runnerSha256": old.sha256_file(Path(__file__)),
              "historyHelperSha256": old.sha256_file(Path(old.__file__)),
              "executionHeadCommit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                                     check=True, capture_output=True, text=True).stdout.strip(),
              "implementationFingerprint": IMPLEMENTATION,
              "historyReportSha256": p["historyReportSha256"],
              "historyArchiveSha256ByMaxDt": p["historyArchiveSha256ByMaxDt"],
              "priorReportSha256": p["priorReportSha256"],
              "priorImplementationFingerprint": p["priorImplementationFingerprint"],
              "scenarioSha256": p["scenarioSha256"], "resolvedInputSha256": case["inputSha256"],
              "materialRevisionSha256": p["materialRevisionSha256"],
              "selectedCells": p["orderedSelectedCells"], "maxDt_s": case["dt"],
              "expectedAcceptedStepsEstimate": 20000, "expectedAcceptedCellStepsEstimate": 10531840000,
              "expectedWallTimeEstimate_s": 2218.463331600011,
              "budgetEnforcement": "sampled soft wall/RSS guards; no OS hard kill; accepted cell steps exclude retries",
              "finalEverCheckStatus": "unavailable",
              "finalEverCheckReason": "Frozen final_state_observer exposes no independent ever-liquidus mask",
              "runtimeWork": counters.copy(), "rows": [],
              "startedAt": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    _write_json(partial, report, exclusive=True)
    started = time.perf_counter()  # Includes allocation, run, post-run validation and artifact writes.
    process = None
    last_progress = [started, 0]
    output_created = False

    def guard(next_step=False):
        elapsed = time.perf_counter()-started
        rss = process.memory_info().rss
        counters["maximumSampledRssBytes"] = max(counters["maximumSampledRssBytes"], int(rss))
        if elapsed > p["maximumWallTimeByMaxDt_s"][case["key"]]:
            raise RuntimeError("Refinement wall-time ceiling reached")
        if rss > p["maximumSampledRssBytes"]:
            raise RuntimeError("Refinement sampled RSS ceiling reached")
        increment = 1 if next_step else 0
        if counters["acceptedSteps"]+increment > p["maximumStepsByMaxDt"][case["key"]]:
            raise RuntimeError("Refinement accepted-step ceiling reached")
        if counters["acceptedCellSteps"]+increment*case["cells"] > p["maximumTotalCellSteps"]:
            raise RuntimeError("Refinement accepted cell-step ceiling reached")

    def snapshot(progress=False):
        report["runtimeWork"] = {**counters, "wallTime_s": time.perf_counter()-started}
        report["runtimeWork"]["estimatedSourceAttemptCellSteps"] = (
            counters["acceptedSteps"]+counters["sourceTimestepRetries"])*case["cells"]
        _write_json(partial, report)
        if progress:
            print(json.dumps({"stage": "running", **report["runtimeWork"]}), flush=True)
        last_progress[:] = [time.perf_counter(), counters["acceptedSteps"]]

    try:
        process = _load_psutil().Process()
        directory.mkdir()
        guard()
        history = old.HistoryBuffer(case, p["maximumStepsByMaxDt"][case["key"]])
        guard()
        states = []
        source_original = lpbf_simulation.source_limited_step

        def guarded_source(*args, **kwargs):
            guard(next_step=True)
            result = source_original(*args, **kwargs)
            retries = int(result[4])
            counters["sourceTimestepRetries"] += retries
            counters["sourceLimitedSteps"] += int(retries > 0)
            guard()
            return result

        def observe(record):
            counters["acceptedSteps"] += 1
            counters["acceptedCellSteps"] += case["cells"]
            observed_time = float(record["time_s"])
            if math.isfinite(observed_time):
                counters["lastTime_s"] = observed_time
            history.observe(record)
            guard()
            if (counters["acceptedSteps"]-last_progress[1] >= 1000
                    or time.perf_counter()-last_progress[0] >= 30):
                snapshot(progress=True)
                guard()

        with patch.object(lpbf_simulation, "source_limited_step", guarded_source):
            result = lpbf_simulation.run(case["payload"], final_state_observer=states.append,
                                         local_history_observer=observe,
                                         local_history_indices_ijk=case["indices"])
        guard()
        if lpbf_simulation.implementation_fingerprint() != IMPLEMENTATION:
            raise RuntimeError("Frozen numerical implementation changed during run")
        if (len(states) != 1 or result["provenance"]["executionInputHash"] != case["inputSha256"]
                or result["provenance"]["implementationHash"] != IMPLEMENTATION):
            raise RuntimeError("Executed case identity or final capture differs")
        arrays, state = history.arrays(), states[0]
        _validate_history(arrays, case["dt"], p["expectedEventTime_s"])
        report["acceptedTimestepDistribution"] = lpbf_simulation.summarize_accepted_timesteps(
            arrays["accepted_dt_s"], case["dt"], counters["sourceLimitedSteps"], counters["sourceTimestepRetries"])
        numerical = result.get("numericalDiagnostics", {})
        solver_dt = numerical.get("acceptedTimestepDistribution")
        if solver_dt is not None and solver_dt != report["acceptedTimestepDistribution"]:
            raise RuntimeError("Solver timestep/retry diagnostics differ from observed counters")
        if abs(float(state["time_s"])-p["expectedEventTime_s"]) > 1e-14:
            raise RuntimeError("Final observer misses frozen event")
        final = {}
        for name in old.FIELD_NAMES:
            field = np.asarray(state[name])
            shape = (case["cells"], 3) if name == "coordinates_m" else (history.count,) if name == "accepted_dt_s" else (case["cells"],)
            if field.shape != shape or field.dtype != np.dtype("<f8") or not np.isfinite(field).all():
                raise RuntimeError(f"Final field dtype, shape or finite validity differs: {name}")
            final[name] = field
        if not np.array_equal(final["accepted_dt_s"], arrays["accepted_dt_s"]):
            raise RuntimeError("Final and local observer accepted dt differ")
        flat = np.ravel_multi_index(np.asarray(case["indices"]).T,
                                   tuple(case["domain"][k] for k in ("nx", "ny", "nz")))
        if (not np.array_equal(final["coordinates_m"][flat], arrays["coordinates_m"])
                or not np.array_equal(final["temperature_K"][flat], arrays["values"][-1, :, 0])
                or not np.array_equal(final["enthalpy_J_m3"][flat], arrays["values"][-1, :, 1])):
            raise RuntimeError("Independent final observer differs from last local T/H/coordinates")
        # Liquidus memory derives from the local observer, not an independent final field.
        above = arrays["values"][:, :, 0] >= case["material"]["liquidus_K"]
        if not np.array_equal(np.logical_or.accumulate(above, axis=0), arrays["ever"][:, :, 1]):
            raise RuntimeError("Local ever-liquidus memory differs from temperature threshold chain")
        final["time_s"] = np.asarray(float(state["time_s"]), dtype="<f8")
        final["local_final_ever_observer_derived"] = arrays["ever"][-1, :, 1].copy()
        if sum(a.nbytes for a in final.values()) > p["maximumPriorFieldBytes"]:
            raise RuntimeError("Final field uncompressed byte ceiling reached")
        if sum(a.nbytes for a in arrays.values()) > p["maximumHistoryBytes"]:
            raise RuntimeError("History uncompressed byte ceiling reached")
        guard()
        artifacts = {}
        for label, fields, limit in (("history", arrays, p["maximumHistoryBytes"]),
                                     ("finalstate", final, p["maximumPriorFieldBytes"])):
            path = directory / f"{label}-maxdt-{case['dt']:.4e}.npz"
            np.savez_compressed(path, **fields)
            guard()
            if path.stat().st_size > limit:
                raise RuntimeError(f"{label} archive disk ceiling reached")
            artifacts[label+"Artifact"] = {"path": path.relative_to(ROOT).as_posix(),
                                           "sha256": old.sha256_file(path), "byteSize": path.stat().st_size,
                                           "arraySha256": {name: _array_hash(a) for name, a in fields.items()}}
            guard()
        comparison = compare_canonical_histories(*plan["histories"], arrays, p["expectedEventTime_s"])
        report.update(physicalCheckpointComparison=comparison,
                      primaryMetricStatus=comparison["primaryMetricStatus"],
                      transitions=transition_summary(arrays, p["expectedEventTime_s"]),
                      localFinalTemperatureEnthalpyCoordinatesExactMatch=True)
        report["rows"] = [{"maxDt_s": case["dt"], "acceptedSteps": history.count,
                           "acceptedCellSteps": counters["acceptedCellSteps"],
                           "resolvedInputSha256": case["inputSha256"], **artifacts}]
        guard()
        snapshot()
        guard()
        report["stage"] = "completed"
        report["finishedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        _write_json(out, report, exclusive=True)
        output_created = True
        try:
            guard()
        except Exception:
            out.unlink()
            raise
        partial.unlink()
        return report
    except Exception as exc:
        if output_created and out.exists():
            out.unlink()
        report["stage"] = "partial"
        report["failure"] = f"{type(exc).__name__}: {exc}"
        report["exceptionType"] = type(exc).__name__
        report["reason"] = str(exc)
        report["finishedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        snapshot()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL_PATH)
    parser.add_argument("--execute", action="store_true", help="Run only the new bounded 12.5 ns case")
    args = parser.parse_args()
    if args.execute:
        report = execute(args.protocol)
        print(json.dumps({"stage": report["stage"], "comparison": report["physicalCheckpointComparison"]}, indent=2))
    else:
        plan = preflight(args.protocol)
        print(json.dumps({"stage": "preflight-only", **DIAGNOSTIC,
                          "protocolSha256": plan["protocolSha256"],
                          "cells": plan["case"]["cells"], "selectedCellCount": 19,
                          "newMaxDt_s": 1.25e-8, "expectedStepsEstimate": 20000,
                          "maximumAcceptedSteps": 22788,
                          "maximumUncompressedHistoryBytes": plan["historyMaximumUncompressedBytes"],
                          "baselineEverMismatchCheckpointCells": 2695, "solverLaunched": False}, indent=2))


if __name__ == "__main__":
    main()
