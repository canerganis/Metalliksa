"""Independent, read-only audit for the frozen fixed-event refinement run.

Run only after the owner confirms that the completed or partial report and its
archives are ready. This script never calls the solver or imports the runner.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
import zipfile
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "docs/LPBF_FIXED_EVENT_TIME_REFINEMENT_2026-10-02_PROTOCOL.json"
COMPLETE_PATH = ROOT / "docs/LPBF_FIXED_EVENT_TIME_REFINEMENT_2026-10-02.json"
PARTIAL_PATH = ROOT / "docs/LPBF_FIXED_EVENT_TIME_REFINEMENT_2026-10-02.partial.json"
AUDIT_PATH = Path(__file__).with_suffix(".json")
ARRAYS = ("time_s", "accepted_dt_s", "values", "ever", "cell_indices_ijk", "coordinates_m")
EVENT_TOL = 1e-14


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_npz(path: Path, expected_names: set[str]) -> dict[str, np.ndarray]:
    with zipfile.ZipFile(path) as archive:
        members = {item.filename for item in archive.infolist()}
        require(members == {name + ".npy" for name in expected_names},
                f"Unexpected NPZ members: {path}")
    with np.load(path, allow_pickle=False) as archive:
        require(set(archive.files) == expected_names, f"Unexpected array names: {path}")
        return {name: archive[name].copy() for name in expected_names}


def array_hash(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def verify_hashes(arrays: dict[str, np.ndarray], expected: dict[str, str], label: str) -> None:
    require(set(arrays) == set(expected), f"{label}: array hash manifest names differ")
    for name, array in arrays.items():
        require(array_hash(array) == expected[name], f"{label}: SHA-256 differs for {name}")


def validate_history(arrays: dict[str, np.ndarray], max_dt: float, event: float,
                     expected_steps: int, label: str) -> None:
    n = expected_steps
    expected = {"time_s": (n,), "accepted_dt_s": (n,), "values": (n, 19, 6),
                "ever": (n, 19, 2), "cell_indices_ijk": (19, 3),
                "coordinates_m": (19, 3)}
    require(set(arrays) == set(expected), f"{label}: wrong history arrays")
    for name, shape in expected.items():
        a = arrays[name]
        require(a.shape == shape, f"{label}: wrong shape for {name}: {a.shape}")
        want = np.dtype("bool") if name == "ever" else np.dtype("<i4") if name == "cell_indices_ijk" else np.dtype("<f8")
        require(a.dtype == want, f"{label}: wrong dtype for {name}: {a.dtype}")
        if a.dtype.kind in "f":
            require(bool(np.isfinite(a).all()), f"{label}: nonfinite {name}")
    t, dt = arrays["time_s"], arrays["accepted_dt_s"]
    require(bool(np.all(dt > 0)) and bool(np.all(dt <= max_dt * (1 + 1e-12))),
            f"{label}: timestep outside bounds")
    require(bool(np.all(np.diff(t) > 0)), f"{label}: non-monotonic time")
    require(bool(np.allclose(t, np.cumsum(dt), rtol=0, atol=EVENT_TOL)),
            f"{label}: accepted timestep clock chain differs")
    require(abs(float(t[-1]) - event) <= EVENT_TOL, f"{label}: event endpoint differs")
    ever = arrays["ever"]
    require(not bool(ever[0, :, 0].any()), f"{label}: first before-state is not false")
    require(not bool(np.any(ever[:, :, 0] & ~ever[:, :, 1])), f"{label}: impossible ever-state")
    require(bool(np.array_equal(ever[1:, :, 0], ever[:-1, :, 1])),
            f"{label}: ever-state transition chain differs")
    require(bool(np.all(arrays["values"][:, :, 0] > 0)) and
            bool(np.all(arrays["values"][:, :, 2] > 0)), f"{label}: invalid physical scalars")


def exact_matches(canonical: np.ndarray, candidate: np.ndarray, label: str) -> np.ndarray:
    require(bool(np.all(np.diff(canonical) > 0)) and bool(np.all(np.diff(candidate) > 0)),
            f"{label}: timestamps must be strictly increasing")
    right = np.clip(np.searchsorted(candidate, canonical), 0, len(candidate) - 1)
    left = np.maximum(right - 1, 0)
    dl, dr = np.abs(candidate[left] - canonical), np.abs(candidate[right] - canonical)
    require(not bool(np.any((left != right) & (dl == dr))), f"{label}: ambiguous nearest timestamp")
    idx = np.where(dl < dr, left, right)
    require(bool(np.all(np.abs(candidate[idx] - canonical) <= EVENT_TOL)),
            f"{label}: missing canonical timestamp within 1e-14; interpolation forbidden")
    require(len(np.unique(idx)) == len(idx), f"{label}: timestamp mapping is not one-to-one")
    return idx


def run_audit() -> dict:
    require(PROTOCOL_PATH.is_file(), "Frozen protocol is missing")
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    require(protocol["experimentalValidation"] is False, "Protocol experimental flag changed")
    require(protocol["convergenceConclusion"] == "inconclusive", "Protocol conclusion changed")
    require(protocol["expectedImplementationFingerprint"] ==
            "d7e5c4e3d5f0a59c4b955e0e1ca29f624fe6249c4e7cd1522e84ed1a87249315",
            "Protocol implementation identity changed")

    report_path = COMPLETE_PATH if COMPLETE_PATH.is_file() else PARTIAL_PATH
    require(report_path.is_file(), "Neither completed nor partial refinement report exists")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    require(report.get("protocolId") == protocol["protocolId"], "Report protocol identity differs")
    protocol_sha = sha256(PROTOCOL_PATH)
    require(report.get("protocolSha256") == protocol_sha, "Report protocol SHA-256 differs")
    require(report.get("implementationFingerprint") == protocol["expectedImplementationFingerprint"],
            "Report implementation fingerprint differs")
    require(report.get("resolvedInputSha256") == protocol["expectedInputSha256ByMaxDt"]["1.25e-08"],
            "New solver-input identity differs")
    runner_path = ROOT / "python/run_lpbf_fixed_event_time_refinement_probe.py"
    helper_path = ROOT / "python/run_lpbf_fixed_event_time_history_probe.py"
    runner_sha, helper_sha = sha256(runner_path), sha256(helper_path)
    require(report.get("runnerSha256") == runner_sha, "Frozen runner SHA-256 differs")
    require(report.get("historyHelperSha256") == helper_sha, "Frozen history helper SHA-256 differs")
    sys.path.insert(0, str(ROOT / "python"))
    import lpbf_simulation  # fingerprint only; no simulation is launched
    current_implementation = lpbf_simulation.implementation_fingerprint()
    require(current_implementation == protocol["expectedImplementationFingerprint"],
            "Current implementation fingerprint differs from frozen fingerprint")

    common = {
        "auditStatus": "PASS",
        "reportStage": report.get("stage"),
        "reportSha256": sha256(report_path),
        "protocolSha256": protocol_sha,
        "runnerSha256": runner_sha,
        "historyHelperSha256": helper_sha,
        "implementationFingerprint": current_implementation,
        "experimentalValidation": report.get("experimentalValidation"),
        "convergenceConclusion": report.get("convergenceConclusion"),
        "solverValidationStatus": report.get("solverValidationStatus"),
        "NIST": report.get("NIST"),
        "finalEverCheckStatus": report.get("finalEverCheckStatus"),
    }
    require(report.get("experimentalValidation") is False, "Report must remain unvalidated")
    require(report.get("convergenceConclusion") == "inconclusive", "Report conclusion must remain inconclusive")
    require(report.get("solverValidationStatus") == "unvalidated", "Solver status must remain unvalidated")
    require(report.get("NIST") == "unavailable", "NIST state must remain unavailable")
    require(report.get("finalEverCheckStatus") == "unavailable",
            "Independent final ever-liquidus state must remain unavailable")
    require(report.get("status") == "diagnostic-only", "Report status must remain diagnostic-only")

    if report.get("stage") != "completed":
        counters = report.get("runtimeWork", {})
        steps = int(counters.get("acceptedSteps", -1))
        cells = int(protocol["expectedCells"])
        require(report.get("stage") == "partial", "Unexpected noncompleted report stage")
        require(0 <= steps <= protocol["maximumStepsByMaxDt"]["1.25e-08"],
                "Partial accepted step count exceeds ceiling")
        require(counters.get("acceptedCellSteps") == steps * cells,
                "Partial accepted cell-step count differs")
        require(0 <= float(counters.get("lastTime_s", -1)) <= protocol["expectedEventTime_s"] + EVENT_TOL,
                "Partial observed clock is outside event bounds")
        require(not COMPLETE_PATH.exists(), "Partial run unexpectedly has a completed report")
        result = {**common, "scientificComparison": "unavailable-partial-run",
                  "acceptedSteps": steps, "acceptedCellSteps": counters["acceptedCellSteps"],
                  "lastTime_s": counters["lastTime_s"]}
        return result

    rows = report.get("rows", [])
    require(len(rows) == 1 and rows[0].get("maxDt_s") == 1.25e-8,
            "Completed report must contain only the 12.5 ns new row")
    row = rows[0]
    counters = report.get("runtimeWork", {})
    steps = int(counters.get("acceptedSteps", -1))
    cells = int(protocol["expectedCells"])
    require(steps == protocol["expectedStepsByMaxDt"]["1.25e-08"] or
            abs(float(counters.get("lastTime_s", 0)) - protocol["expectedEventTime_s"]) <= EVENT_TOL,
            "Completed run misses expected event")
    require(steps <= protocol["maximumStepsByMaxDt"]["1.25e-08"], "Accepted-step ceiling exceeded")
    require(counters.get("acceptedCellSteps") == steps * cells, "Accepted cell-step counter differs")
    require(row.get("acceptedSteps") == steps and row.get("acceptedCellSteps") == steps * cells,
            "Completed row counters differ from runtime counters")
    require(int(counters.get("acceptedCellSteps", math.inf)) <= protocol["maximumTotalCellSteps"],
            "Total accepted cell-step ceiling exceeded")
    require(float(counters.get("wallTime_s", math.inf)) <= protocol["maximumWallTimeByMaxDt_s"]["1.25e-08"],
            "Wall-time ceiling exceeded")
    require(int(counters.get("maximumSampledRssBytes", math.inf)) <= protocol["maximumSampledRssBytes"],
            "Sampled RSS ceiling exceeded")
    require(abs(float(counters.get("lastTime_s", 0)) - protocol["expectedEventTime_s"]) <= EVENT_TOL,
            "Observed final time differs from frozen event")

    old_report_path = ROOT / protocol["historyReport"]
    require(sha256(old_report_path) == protocol["historyReportSha256"], "Prior history report changed")
    old_report = json.loads(old_report_path.read_text(encoding="utf-8"))
    selected = protocol["orderedSelectedCells"]
    indices = np.asarray([x["indices_ijk"] for x in selected], dtype="<i4")
    coordinates = np.asarray([x["coordinate_m"] for x in selected], dtype="<f8")
    histories = {}
    history_dir = ROOT / "docs/LPBF_FIXED_EVENT_TIME_HISTORY_FIELDS_2026-10-02"
    for key, dt, count, filename in (("5e-08", 5e-8, 5000, "maxdt-5.0000e-08.npz"),
                                     ("2.5e-08", 2.5e-8, 10000, "maxdt-2.5000e-08.npz")):
        archive = history_dir / filename
        require(sha256(archive) == protocol["historyArchiveSha256ByMaxDt"][key],
                f"Old archive hash changed: {key}")
        arrays = load_npz(archive, set(ARRAYS))
        verify_hashes(arrays, protocol["historyArraySha256ByMaxDt"][key], f"old {key}")
        validate_history(arrays, dt, protocol["expectedEventTime_s"], count, f"old {key}")
        histories[key] = arrays

    outdir = ROOT / protocol["historyDirectory"]
    history_artifact = row["historyArtifact"]
    final_artifact = row["finalstateArtifact"]
    new_history_path = ROOT / history_artifact["path"]
    final_path = ROOT / final_artifact["path"]
    require(new_history_path.parent == outdir and final_path.parent == outdir,
            "New artifacts are outside the frozen output directory")
    new_history = load_npz(new_history_path, set(ARRAYS))
    verify_hashes(new_history, history_artifact["arraySha256"], "new history")
    require(sha256(new_history_path) == history_artifact["sha256"], "New history archive SHA-256 differs")
    require(new_history_path.stat().st_size == history_artifact["byteSize"], "New history archive byte size differs")
    validate_history(new_history, 1.25e-8, protocol["expectedEventTime_s"], steps, "new history")
    final_arrays = load_npz(final_path, set(final_artifact["arraySha256"]))
    verify_hashes(final_arrays, final_artifact["arraySha256"], "final state")
    require(sha256(final_path) == final_artifact["sha256"], "Final-state archive SHA-256 differs")
    require(final_path.stat().st_size == final_artifact["byteSize"], "Final-state archive byte size differs")
    final_shapes = {"coordinates_m": (protocol["expectedCells"], 3),
                    "temperature_K": (protocol["expectedCells"],),
                    "enthalpy_J_m3": (protocol["expectedCells"],),
                    "density_kg_m3": (protocol["expectedCells"],),
                    "accepted_dt_s": (steps,), "time_s": (),
                    "local_final_ever_observer_derived": (19,)}
    require(set(final_arrays) == set(final_shapes), "Final-state array manifest differs")
    for name, shape in final_shapes.items():
        a = final_arrays[name]
        require(a.shape == shape, f"Final-state shape differs for {name}")
        want = np.dtype("bool") if name == "local_final_ever_observer_derived" else np.dtype("<f8")
        require(a.dtype == want, f"Final-state dtype differs for {name}")
        if a.dtype.kind == "f":
            require(bool(np.isfinite(a).all()), f"Final-state contains nonfinite {name}")
    require(new_history["cell_indices_ijk"].shape == (19, 3) and
            np.array_equal(new_history["cell_indices_ijk"], indices), "Ordered selected indices differ")
    require(np.array_equal(new_history["coordinates_m"], coordinates), "New-history selected coordinates differ")
    domain = protocol["expectedDomain"]
    flat = np.ravel_multi_index(indices.T, (domain["nx"], domain["ny"], domain["nz"]))
    require(np.array_equal(final_arrays["coordinates_m"][flat], new_history["coordinates_m"]),
            "Final and local coordinates differ")
    require(np.array_equal(final_arrays["temperature_K"][flat], new_history["values"][-1, :, 0]),
            "Final and local temperatures differ")
    require(np.array_equal(final_arrays["enthalpy_J_m3"][flat], new_history["values"][-1, :, 1]),
            "Final and local enthalpies differ")
    require(abs(float(final_arrays["time_s"]) - protocol["expectedEventTime_s"]) <= EVENT_TOL,
            "Final field time differs from event")

    t50, t25, tnew = histories["5e-08"]["time_s"], histories["2.5e-08"]["time_s"], new_history["time_s"]
    idx25 = exact_matches(t50, t25, "50ns->25ns")
    try:
        idxnew = exact_matches(t50, tnew, "50ns->12.5ns")
    except AssertionError:
        idxnew = None
    require(len(t50) == protocol["canonicalCheckpointCount"] == 5000,
            "Canonical checkpoint count differs")
    ever50 = histories["5e-08"]["ever"][:, :, 1]
    ever25 = histories["2.5e-08"]["ever"][idx25, :, 1]
    baseline_mismatch = int(np.count_nonzero(ever50 != ever25))
    require(baseline_mismatch == protocol["baselineEverMismatchCheckpointCells"],
            "Recomputed frozen baseline mismatch count differs")
    comparison = report["physicalCheckpointComparison"]
    possible = 5000 * 19
    if idxnew is None:
        refined_mismatch = None
        require(comparison["comparisonStatus"] == "inconclusive" and
                comparison["primaryMetricStatus"] == "inconclusive" and
                comparison["refinementEverMismatchCheckpointCells"] is None and
                comparison["missingCanonicalTimestamp"] is True,
                "Missing timestamp must leave the comparison inconclusive")
        require(report["primaryMetricStatus"] == "inconclusive",
                "Top-level metric status must remain inconclusive")
    else:
        evernew = new_history["ever"][idxnew, :, 1]
        refined_mismatch = int(np.count_nonzero(ever25 != evernew))
        primary = "localDiagnosticDecrease" if refined_mismatch < baseline_mismatch else "noDecrease"
        require(comparison["comparisonStatus"] == "comparable", "Matched timestamp comparison is not comparable")
        require(comparison["baselineEverMismatchCheckpointCells"] == baseline_mismatch,
                "Report baseline mismatch count differs from independent recomputation")
        require(comparison["refinementEverMismatchCheckpointCells"] == refined_mismatch,
                "Report refinement mismatch count differs from independent recomputation")
        require(comparison["matchedPhysicalCheckpoints"] == 5000,
                "Report matched canonical checkpoint count differs")
        require(comparison["primaryMetricStatus"] == primary and report["primaryMetricStatus"] == primary,
                "Reported local diagnostic decrease status differs from independent recomputation")
        require(math.isclose(comparison["baselineEverMismatchFraction"], baseline_mismatch / possible,
                             rel_tol=0, abs_tol=1e-15), "Reported baseline mismatch fraction differs")
        require(math.isclose(comparison["refinementEverMismatchFraction"], refined_mismatch / possible,
                             rel_tol=0, abs_tol=1e-15), "Reported refinement mismatch fraction differs")
    result = {**common, "scientificComparison": "diagnostic-local-history-only",
              "acceptedSteps": steps, "acceptedCellSteps": counters["acceptedCellSteps"],
              "lastTime_s": counters["lastTime_s"], "wallTime_s": counters["wallTime_s"],
              "maximumSampledRssBytes": counters["maximumSampledRssBytes"],
              "historyArchiveBytes": new_history_path.stat().st_size,
              "finalStateArchiveBytes": final_path.stat().st_size,
              "canonicalCheckpoints": 5000, "possibleCheckpointCellPairs": possible,
              "baselineEverMismatchCheckpointCells": baseline_mismatch,
              "baselineMismatchFraction": baseline_mismatch / possible,
              "refinementEverMismatchCheckpointCells": refined_mismatch,
              "refinementMismatchFraction": refined_mismatch / possible if refined_mismatch is not None else None,
              "strictDecrease": refined_mismatch < baseline_mismatch if refined_mismatch is not None else None,
              "canonicalTimestampMatch": idxnew is not None}
    return result


def main() -> None:
    result = run_audit()
    AUDIT_PATH.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
