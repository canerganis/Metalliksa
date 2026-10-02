"""Bounded local-history probe for the existing 5 um / 50 and 25 ns states.

The CLI defaults to preflight. ``--execute`` recomputes the two frozen cases,
records scalar cell histories, and requires exact agreement with prior fields.
Outputs are numerical diagnostics, never experimental validation.
"""

import argparse
import contextlib
import datetime
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

import numpy as np

import lpbf_simulation
from lpbf_core_physics import calculate_mesh_domain, scan_segments


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "docs/LPBF_FIXED_EVENT_TIME_HISTORY_2026-10-02_PROTOCOL.json"
PROTOCOL_ID = "lpbf-fixed-event-local-history-5um-2026-10-02-v1"
FIELD_NAMES = ("coordinates_m", "temperature_K", "enthalpy_J_m3",
               "density_kg_m3", "accepted_dt_s")
VALUES = ("temperature_K", "enthalpy_J_m3", "effectiveConductivity_W_mK",
          "sourceRate_W_m3", "conductionRate_W_m3", "passiveRate_W_m3")


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_path(relative):
    if (not isinstance(relative, str) or Path(relative).is_absolute()
            or ".." in Path(relative).parts):
        raise ValueError("Artifact path must stay inside the repository")
    path = ROOT / relative
    for ancestor in (path, *path.parents):
        if ancestor == ROOT:
            break
        if ancestor.is_symlink() or (hasattr(ancestor, "is_junction") and ancestor.is_junction()):
            raise ValueError("Artifact path contains a symlink or junction")
    if not path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("Artifact path escapes repository")
    return path


def validate_protocol(p):
    fixed = {
        "schemaVersion": 1, "protocolId": PROTOCOL_ID,
        "status": "diagnostic-only", "experimentalValidation": False,
        "convergenceConclusion": "inconclusive", "mesh_um": 5,
        "scenarioFile": "docs/LPBF_P4_CURRENT_MODEL_40W_SCENARIO_2026-09-25.json",
        "scenarioOverrides": {"mesh_um": 5, "cooling_s": 0},
        "priorReport": "docs/LPBF_FIXED_EVENT_5UM_TIME_2026-10-02.json",
        "priorFieldDirectory": "docs/LPBF_FIXED_EVENT_5UM_TIME_FIELDS_2026-10-02",
        "levels": [5e-8, 2.5e-8], "expectedEventTime_s": 0.00024999999999999995,
        "expectedEventEndpoint_m": [9.999999999999999e-5, 0., 4e-5],
        "expectedDomain": {"nx": 88, "ny": 88, "nz": 68, "dx_um": 5.},
        "expectedCells": 526592,
        "expectedStepsByMaxDt": {"5e-08": 5000, "2.5e-08": 10000},
        "maximumStepsByMaxDt": {"5e-08": 5500, "2.5e-08": 11000},
        "maximumTotalCellSteps": 8688768000,
        "maximumCells": 600000, "maximumSampledRssBytes": 805306368,
        "maximumWallTimeByMaxDt_s": {"5e-08": 1200, "2.5e-08": 2400},
        "maximumHistoryBytes": 50000000, "maximumPriorFieldBytes": 40000000,
        "centers_um": [[-67.5, -2.5, 2.5], [77.5, -2.5, 7.5],
                       [77.5, 2.5, 7.5]],
        "neighborRule": "center-and-six-face-neighbors",
        "output": "docs/LPBF_FIXED_EVENT_TIME_HISTORY_2026-10-02.json",
        "partial": "docs/LPBF_FIXED_EVENT_TIME_HISTORY_2026-10-02.partial.json",
        "historyDirectory": "docs/LPBF_FIXED_EVENT_TIME_HISTORY_FIELDS_2026-10-02",
    }
    extra = {"scope", "scenarioSha256", "priorReportSha256", "priorImplementationFingerprint",
             "expectedImplementationFingerprint", "materialRevisionSha256",
             "expectedInputSha256ByMaxDt", "priorFieldSha256ByMaxDt", "resourceAssumptions"}
    if not isinstance(p, dict) or set(p) != set(fixed) | extra:
        raise ValueError("Unexpected local-history protocol schema")
    for key, expected in fixed.items():
        if p[key] != expected or isinstance(expected, bool) and type(p[key]) is not bool:
            raise ValueError(f"Frozen local-history protocol differs: {key}")
    for name in ("scenarioFile", "priorReport", "priorFieldDirectory", "output",
                 "partial", "historyDirectory"):
        safe_path(p[name])
    for key in ("scenarioSha256", "priorReportSha256", "priorImplementationFingerprint",
                "expectedImplementationFingerprint", "materialRevisionSha256"):
        if not isinstance(p[key], str) or len(p[key]) != 64:
            raise ValueError(f"Invalid {key}")
    if (set(p["priorFieldSha256ByMaxDt"]) != {"5e-08", "2.5e-08"}
            or set(p["expectedInputSha256ByMaxDt"]) != {"5e-08", "2.5e-08"}):
        raise ValueError("Frozen field/input identities are incomplete")


def selected_cells(domain, centers_um):
    dx = domain["dx"]
    axes = ((np.arange(domain["nx"])+.5)*dx-domain["span"]/2,
            (np.arange(domain["ny"])+.5)*dx-domain["ny"]*dx/2,
            (np.arange(domain["nz"])+.5)*dx-domain["substrate_depth"])
    indices = set()
    centers = []
    for coordinates_um in centers_um:
        index = tuple(int(np.argmin(np.abs(axis-coordinate*1e-6)))
                      for axis, coordinate in zip(axes, coordinates_um))
        actual = [float(axis[i]) for axis, i in zip(axes, index)]
        if any(abs(a-b*1e-6) > 1e-12 for a, b in zip(actual, coordinates_um)):
            raise ValueError("Selected physical point does not map to a grid-cell center")
        centers.append(index)
        indices.add(index)
        for dimension in range(3):
            for offset in (-1, 1):
                neighbor = list(index)
                neighbor[dimension] += offset
                if not 0 <= neighbor[dimension] < len(axes[dimension]):
                    raise ValueError("Selected face neighbor leaves the grid")
                indices.add(tuple(neighbor))
    ordered = sorted(indices)
    if len(ordered) > 32:
        raise ValueError("Selected cell count exceeds observer bound")
    positions = [[float(axis[i]) for axis, i in zip(axes, index)] for index in ordered]
    return ordered, positions, centers


def fresh_destinations(p):
    if any(safe_path(p[name]).exists() for name in ("output", "partial", "historyDirectory")):
        raise FileExistsError("Local-history destination exists; use a new protocol identity")


def preflight():
    raw = PROTOCOL_PATH.read_bytes()
    p = json.loads(raw)
    validate_protocol(p)
    fresh_destinations(p)
    if lpbf_simulation.implementation_fingerprint() != p["expectedImplementationFingerprint"]:
        raise ValueError("Current solver implementation differs from the frozen observer protocol")
    scenario_bytes = safe_path(p["scenarioFile"]).read_bytes()
    if hashlib.sha256(scenario_bytes).hexdigest() != p["scenarioSha256"]:
        raise ValueError("Frozen scenario changed")
    scenario = json.loads(scenario_bytes)["scenario"]
    scenario.update(p["scenarioOverrides"])
    segments, end = scan_segments(scenario)
    if (len(segments) != 1 or end != p["expectedEventTime_s"]
            or segments[0]["end"] != p["expectedEventEndpoint_m"][:2]
            or not math.isclose(scenario["layer_um"]*1e-6,
                                p["expectedEventEndpoint_m"][2], rel_tol=0., abs_tol=1e-15)):
        raise ValueError("Scenario no longer reaches the frozen scan-end event")
    report_path = safe_path(p["priorReport"])
    if sha256_file(report_path) != p["priorReportSha256"]:
        raise ValueError("Prior time report hash changed")
    prior = json.loads(report_path.read_bytes())
    if (prior["stage"] != "completed" or prior["experimentalValidation"] is not False
            or prior["implementationFingerprint"] != p["priorImplementationFingerprint"]
            or prior["scenarioSha256"] != p["scenarioSha256"]):
        raise ValueError("Prior time report identity differs")
    cases = []
    for dt in p["levels"]:
        key = str(dt)
        resolved, material = lpbf_simulation.validate({**scenario, "maxDt_s": dt})
        domain = calculate_mesh_domain(resolved)
        cells = math.prod(domain[name] for name in ("nx", "ny", "nz"))
        input_sha = hashlib.sha256(json.dumps(resolved, sort_keys=True, allow_nan=False).encode()).hexdigest()
        if (cells != p["expectedCells"] or cells > p["maximumCells"]
                or any(domain[name] != p["expectedDomain"][name] for name in ("nx", "ny", "nz"))
                or not math.isclose(domain["dx"]*1e6, p["expectedDomain"]["dx_um"], abs_tol=1e-12)
                or input_sha != p["expectedInputSha256ByMaxDt"][key]
                or material["materialRevisionSha256"] != p["materialRevisionSha256"]):
            raise ValueError("Resolved solver input, material or grid changed")
        rows = [row for row in prior["rows"] if row.get("maxDt_s") == dt]
        if len(rows) != 1:
            raise ValueError("Prior case is missing or ambiguous")
        row = rows[0]
        artifact = row["fieldArtifact"]
        field_path = safe_path(p["priorFieldDirectory"] + "/" + artifact["path"])
        if (artifact["sha256"] != p["priorFieldSha256ByMaxDt"][key]
                or sha256_file(field_path) != artifact["sha256"]
                or field_path.stat().st_size > p["maximumPriorFieldBytes"]
                or row["resolvedInputSha256"] != input_sha
                or row["acceptedSteps"] != p["expectedStepsByMaxDt"][key]):
            raise ValueError("Prior field or case identity changed")
        indices, positions, centers = selected_cells(domain, p["centers_um"])
        cases.append({"dt": dt, "key": key, "payload": resolved, "material": material,
                      "domain": domain, "cells": cells, "inputSha256": input_sha,
                      "priorRow": row, "priorField": field_path,
                      "indices": indices, "positions": positions, "centerIndices": centers})
    count = len(cases[0]["indices"])
    worst_bytes = sum(p["maximumStepsByMaxDt"][case["key"]] *
                      (8 + 8 + count*len(VALUES)*8 + count*2) for case in cases)
    if worst_bytes > p["maximumHistoryBytes"]:
        raise ValueError("Local-history arrays exceed the frozen memory/disk budget")
    return {"protocol": p, "protocolSha256": hashlib.sha256(raw).hexdigest(),
            "prior": prior, "cases": cases, "historyMaximumUncompressedBytes": worst_bytes}


class HistoryBuffer:
    def __init__(self, case, maximum_steps):
        self.case = case
        self.count = 0
        shape = (maximum_steps, len(case["indices"]))
        self.time = np.empty(maximum_steps, dtype="<f8")
        self.dt = np.empty(maximum_steps, dtype="<f8")
        self.values = np.empty((*shape, len(VALUES)), dtype="<f8")
        self.ever = np.empty((*shape, 2), dtype=np.bool_)

    def observe(self, record):
        index = self.count
        if index >= len(self.time) or record["step"] != index+1:
            raise RuntimeError("Local history exceeded the accepted-step bound or sequence")
        if record["cell_indices_ijk"] != [list(item) for item in self.case["indices"]]:
            raise RuntimeError("Local-history cell identity changed")
        dt, clock = float(record["acceptedDt_s"]), float(record["time_s"])
        if (not 0 < dt <= self.case["dt"]*(1+1e-12) or not math.isfinite(clock)
                or abs(clock-(self.time[index-1]+dt if index else dt)) > 1e-14):
            raise RuntimeError("Local history accepted clock is inconsistent")
        self.time[index], self.dt[index] = clock, dt
        for column, (cell, coordinate) in enumerate(zip(record["cells"], self.case["positions"])):
            if not np.allclose(cell["coordinate_m"], coordinate, rtol=0., atol=1e-15):
                raise RuntimeError("Local-history physical coordinate changed")
            values = [float(cell[name]) for name in VALUES]
            if not np.isfinite(values).all() or values[0] <= 0 or values[2] <= 0:
                raise RuntimeError("Local-history scalar is invalid")
            self.values[index, column] = values
            self.ever[index, column] = [cell["everLiquidusBefore"], cell["everLiquidusAfter"]]
            previous_h = self.values[index-1, column, 1] if index else 0.
            computed_h = previous_h + dt*(values[3]+values[5])
            if not math.isclose(values[1], computed_h, rel_tol=1e-10, abs_tol=1e-4):
                raise RuntimeError("Local enthalpy increment differs from source plus passive rate")
        self.count += 1

    def arrays(self):
        return {"time_s": self.time[:self.count].copy(), "accepted_dt_s": self.dt[:self.count].copy(),
                "values": self.values[:self.count].copy(), "ever": self.ever[:self.count].copy(),
                "cell_indices_ijk": np.asarray(self.case["indices"], dtype="<i4"),
                "coordinates_m": np.asarray(self.case["positions"], dtype="<f8")}


@contextlib.contextmanager
def step_budget(counters, case, p):
    original = lpbf_simulation.source_limited_step
    started = time.perf_counter()
    try:
        import psutil
        process = psutil.Process()
    except ImportError:
        process = None

    def guarded(*args, **kwargs):
        if counters["caseSteps"] >= p["maximumStepsByMaxDt"][case["key"]]:
            raise RuntimeError("Local-history per-case accepted-step ceiling reached")
        if counters["acceptedCellSteps"] + case["cells"] > p["maximumTotalCellSteps"]:
            raise RuntimeError("Local-history cell-step ceiling reached")
        if time.perf_counter()-started > p["maximumWallTimeByMaxDt_s"][case["key"]]:
            raise RuntimeError("Local-history wall-time ceiling reached")
        if process is not None:
            rss = process.memory_info().rss
            counters["maximumSampledRssBytes"] = max(counters["maximumSampledRssBytes"], rss)
            if rss > p["maximumSampledRssBytes"]:
                raise RuntimeError("Local-history sampled RSS ceiling reached")
        result = original(*args, **kwargs)
        return result

    with contextlib.ExitStack() as stack:
        from unittest.mock import patch
        stack.enter_context(patch.object(lpbf_simulation, "source_limited_step", guarded))
        yield


def read_prior_field(case, p):
    import zipfile
    with zipfile.ZipFile(case["priorField"]) as archive:
        if sum(item.file_size for item in archive.infolist()) > p["maximumPriorFieldBytes"]+4096:
            raise ValueError("Prior field decompression exceeds bound")
    with np.load(case["priorField"], allow_pickle=False) as arrays:
        if set(arrays.files) != set(FIELD_NAMES):
            raise ValueError("Prior field member set differs")
        state = {name: arrays[name].copy() for name in FIELD_NAMES}
    artifact = case["priorRow"]["fieldArtifact"]
    for name, field in state.items():
        if (field.dtype != np.dtype("<f8") or not np.isfinite(field).all()
                or hashlib.sha256(np.ascontiguousarray(field).tobytes()).hexdigest()
                != artifact["fieldSha256"][name]):
            raise ValueError("Prior field array hash changed")
    expected_clock = np.cumsum(state["accepted_dt_s"], dtype=np.float64)[-1]
    if (not math.isclose(expected_clock, p["expectedEventTime_s"], abs_tol=1e-14)
            or len(state["accepted_dt_s"]) != case["priorRow"]["acceptedSteps"]):
        raise ValueError("Prior accepted clock differs")
    return state


def compare_histories(first, second, event_time):
    a, b = first.arrays(), second.arrays()
    if (not np.array_equal(a["cell_indices_ijk"], b["cell_indices_ijk"])
            or not np.array_equal(a["coordinates_m"], b["coordinates_m"])):
        raise ValueError("Local-history physical grids differ")
    if (abs(a["time_s"][-1]-event_time) > 1e-14
            or abs(b["time_s"][-1]-event_time) > 1e-14):
        raise ValueError("Local histories miss the common event")
    positions = np.searchsorted(b["time_s"], a["time_s"])
    positions = np.clip(positions, 0, len(b["time_s"])-1)
    before = np.maximum(positions-1, 0)
    choose_before = abs(b["time_s"][before]-a["time_s"]) < abs(b["time_s"][positions]-a["time_s"])
    positions = np.where(choose_before, before, positions)
    if np.max(np.abs(b["time_s"][positions]-a["time_s"])) > 1e-14:
        raise ValueError("Accepted-step histories lack common physical checkpoint times")
    difference = b["values"][positions, :, 0]-a["values"][:, :, 0]
    changed = a["ever"][:, :, 1] != b["ever"][positions, :, 1]
    max_flat = int(np.argmax(np.abs(difference)))
    row, col = np.unravel_index(max_flat, difference.shape)
    def local_state(arrays, step, column):
        return {**{name: float(arrays["values"][step, column, value_index])
                   for value_index, name in enumerate(VALUES)},
                "everLiquidusBefore": bool(arrays["ever"][step, column, 0]),
                "everLiquidusAfter": bool(arrays["ever"][step, column, 1])}
    return {"matchedPhysicalCheckpoints": int(len(positions)),
            "maximumAbsoluteTemperatureDifference_K": float(abs(difference[row, col])),
            "maximumDifferenceAt": {"time_s": float(a["time_s"][row]),
                                    "coordinates_m": a["coordinates_m"][col].tolist(),
                                    "state50ns": local_state(a, row, col),
                                    "state25ns": local_state(b, positions[row], col)},
            "firstEverMismatchTime_s": float(a["time_s"][np.argwhere(changed)[0, 0]]) if changed.any() else None,
            "everMismatchCheckpointCells": int(changed.sum()),
            "comparisonRule": "exact same physical accepted-step times; no step-index pairing"}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def execute():
    plan = preflight()
    p = plan["protocol"]
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()
    report = {"schemaVersion": 1, "protocolId": PROTOCOL_ID,
              "protocolSha256": plan["protocolSha256"], "executionHeadCommit": head,
              "scope": p["scope"], "status": "diagnostic-only", "stage": "running",
              "experimentalValidation": False, "convergenceConclusion": "inconclusive",
              "implementationFingerprint": p["expectedImplementationFingerprint"],
              "priorImplementationFingerprint": p["priorImplementationFingerprint"],
              "priorReportSha256": p["priorReportSha256"],
              "selectedCells": [{"indices_ijk": list(index), "coordinate_m": position}
                                for index, position in zip(plan["cases"][0]["indices"],
                                                           plan["cases"][0]["positions"])],
              "centerIndices_ijk": [list(index) for index in plan["cases"][0]["centerIndices"]],
              "rows": [], "runtimeWork": {"acceptedSteps": 0, "acceptedCellSteps": 0},
              "startedAt": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    partial = safe_path(p["partial"])
    out = safe_path(p["output"])
    directory = safe_path(p["historyDirectory"])
    write_json(partial, report)
    directory.mkdir()
    counters = {"caseSteps": 0, "acceptedSteps": 0, "acceptedCellSteps": 0,
                "maximumSampledRssBytes": 0}
    histories = []
    try:
        for case in plan["cases"]:
            if lpbf_simulation.implementation_fingerprint() != p["expectedImplementationFingerprint"]:
                raise RuntimeError("Solver implementation changed during local-history probe")
            prior = read_prior_field(case, p)
            history = HistoryBuffer(case, p["maximumStepsByMaxDt"][case["key"]])
            states = []
            counters["caseSteps"] = 0

            def observe(record):
                history.observe(record)
                counters["caseSteps"] += 1
                counters["acceptedSteps"] += 1
                counters["acceptedCellSteps"] += case["cells"]

            started = time.perf_counter()
            with step_budget(counters, case, p):
                result = lpbf_simulation.run(
                    case["payload"], selected_time_observer=states.append,
                    selected_time_s=p["expectedEventTime_s"],
                    local_history_observer=observe,
                    local_history_indices_ijk=case["indices"])
            if (len(states) != 1 or history.count != p["expectedStepsByMaxDt"][case["key"]]
                    or result["provenance"]["executionInputHash"] != case["inputSha256"]
                    or result["provenance"]["implementationHash"] != p["expectedImplementationFingerprint"]):
                raise RuntimeError("Executed case identity, event capture or history count differs")
            state = states[0]
            for name in FIELD_NAMES:
                observed = (state["accepted_dt_s"] if name == "accepted_dt_s"
                            else state[name])
                if not np.array_equal(observed, prior[name]):
                    raise RuntimeError(f"Observed final {name} differs from prior fixed-event field")
            arrays = history.arrays()
            if (not np.array_equal(arrays["accepted_dt_s"], prior["accepted_dt_s"])
                    or abs(arrays["time_s"][-1]-p["expectedEventTime_s"]) > 1e-14):
                raise RuntimeError("Local history accepted dt or event time differs from prior field")
            path = directory / f"maxdt-{case['dt']:.4e}.npz"
            np.savez_compressed(path, **arrays)
            if path.stat().st_size > p["maximumHistoryBytes"]:
                raise RuntimeError("History archive exceeds disk budget")
            report["rows"].append({
                "maxDt_s": case["dt"], "resolvedInputSha256": case["inputSha256"],
                "priorFieldSha256": p["priorFieldSha256ByMaxDt"][case["key"]],
                "acceptedSteps": history.count, "acceptedCellSteps": history.count*case["cells"],
                "wallTime_s": time.perf_counter()-started,
                "priorFieldExactMatch": True,
                "historyArtifact": {"path": path.relative_to(ROOT).as_posix(),
                                    "sha256": sha256_file(path), "byteSize": path.stat().st_size},
                "everSwitchEvents": [{"step": int(i+1), "time_s": float(arrays["time_s"][i]),
                                       "indices_ijk": list(case["indices"][j])}
                                      for i, j in np.argwhere(~arrays["ever"][:, :, 0]
                                                               & arrays["ever"][:, :, 1])],
            })
            report["runtimeWork"] = {"acceptedSteps": counters["acceptedSteps"],
                                     "acceptedCellSteps": counters["acceptedCellSteps"],
                                     "maximumSampledRssBytes": counters["maximumSampledRssBytes"]}
            write_json(partial, report)
            histories.append(history)
        report["physicalCheckpointComparison"] = compare_histories(
            histories[0], histories[1], p["expectedEventTime_s"])
        report["stage"] = "completed"
        report["finishedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        write_json(out, report)
        partial.unlink()
        return report
    except Exception as exc:
        report["stage"] = "failed"
        report["failure"] = f"{type(exc).__name__}: {exc}"
        report["finishedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        write_json(partial, report)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Run two bounded solver cases")
    args = parser.parse_args()
    if args.execute:
        result = execute()
        print(json.dumps({"stage": result["stage"], "rows": len(result["rows"]),
                          "comparison": result["physicalCheckpointComparison"]}, indent=2))
    else:
        plan = preflight()
        print(json.dumps({"stage": "preflight-only", "protocolSha256": plan["protocolSha256"],
                          "cells": plan["cases"][0]["cells"],
                          "selectedCellCount": len(plan["cases"][0]["indices"]),
                          "centerIndices_ijk": [list(item) for item in plan["cases"][0]["centerIndices"]],
                          "steps": [plan["protocol"]["expectedStepsByMaxDt"][case["key"]]
                                    for case in plan["cases"]],
                          "maximumUncompressedHistoryBytes": plan["historyMaximumUncompressedBytes"],
                          "solverLaunched": False}, indent=2))


if __name__ == "__main__":
    main()
