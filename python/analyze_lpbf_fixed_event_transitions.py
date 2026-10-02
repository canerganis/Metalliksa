"""Compare accepted-step liquidus transitions in frozen 5/2.5/1.25e-8 s histories.

This is a read-only archive analysis. Reported times are sampled accepted-step
right endpoints; the bracket is (previous accepted time, endpoint], not a
continuous physical crossing estimate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
HISTORY_PROTOCOL = ROOT / "docs/LPBF_FIXED_EVENT_TIME_HISTORY_2026-10-02_PROTOCOL.json"
REFINEMENT_PROTOCOL = ROOT / "docs/LPBF_FIXED_EVENT_TIME_REFINEMENT_2026-10-02_PROTOCOL.json"
OUTPUT_JSON = ROOT / "docs/LPBF_FIXED_EVENT_TRANSITIONS_2026-10-02.json"
OUTPUT_MARKDOWN = ROOT / "docs/LPBF_FIXED_EVENT_TRANSITIONS_2026-10-02.md"
LEVELS_S = (5e-8, 2.5e-8, 1.25e-8)
LEVEL_KEYS = ("5e-08", "2.5e-08", "1.25e-08")
LEVEL_LABELS = {"5e-08": "50 ns", "2.5e-08": "25 ns", "1.25e-08": "12.5 ns"}
ARRAY_NAMES = {"time_s", "accepted_dt_s", "values", "ever", "cell_indices_ijk", "coordinates_m"}
ROUND_OFF_TOLERANCE_S = 1e-14
MAX_REPORT_BYTES = 2_000_000
EXPECTED_REFINEMENT_PROTOCOL_SHA256 = "9599b5bf434bafa58e7f42764043bdb99e725a8257e37495b52c7f72735f4484"
EXPECTED_REFINEMENT_REPORT_SHA256 = "a6ab30df9253f5eabc2bfe75248579c4d61d1c582ed28073460cc33c9631ea4b"
INTERVAL_CONVENTION = "(previousAcceptedTime_s, crossingTime_s]"
DIAGNOSTIC_STATUS = {
    "diagnosticOnly": True,
    "experimentalValidation": False,
    "solverValidationStatus": "unvalidated",
    "convergenceConclusion": "inconclusive",
    "NIST": "unavailable",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def array_sha256(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def _require_sha256(actual: str, expected: str, label: str) -> None:
    if (not isinstance(expected, str) or len(expected) != 64
            or any(c not in "0123456789abcdef" for c in expected)
            or actual != expected):
        raise ValueError(f"{label} hash mismatch")


def _parse_pinned_json(raw: bytes, expected_sha256: str, label: str) -> dict[str, Any]:
    if len(raw) > MAX_REPORT_BYTES:
        raise ValueError(f"{label} exceeds the report size bound")
    _require_sha256(sha256_bytes(raw), expected_sha256, label)
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return data


def _read_pinned_json(path: Path, expected_sha256: str, label: str) -> tuple[dict[str, Any], bytes]:
    path = Path(path)
    if path.stat().st_size > MAX_REPORT_BYTES:
        raise ValueError(f"{label} exceeds the report size bound")
    raw = path.read_bytes()
    return _parse_pinned_json(raw, expected_sha256, label), raw


def _finite_float_arrays(arrays: Mapping[str, np.ndarray], label: str) -> None:
    for name, array in arrays.items():
        if array.dtype.kind == "f" and not np.isfinite(array).all():
            raise ValueError(f"{label}: non-finite values in {name}")


def validate_history_arrays(arrays: Mapping[str, np.ndarray], max_dt_s: float,
                            event_time_s: float) -> None:
    """Validate one history archive without assuming a fixed selected-cell count."""
    if not isinstance(arrays, Mapping) or set(arrays) != ARRAY_NAMES:
        raise ValueError("History array names do not match the registered schema")
    if any(not isinstance(value, np.ndarray) for value in arrays.values()):
        raise ValueError("History values must be NumPy arrays")
    time = np.asarray(arrays["time_s"])
    dt = np.asarray(arrays["accepted_dt_s"])
    values = np.asarray(arrays["values"])
    ever = np.asarray(arrays["ever"])
    indices = np.asarray(arrays["cell_indices_ijk"])
    coordinates = np.asarray(arrays["coordinates_m"])
    if time.ndim != 1 or len(time) == 0:
        raise ValueError("History time vector is empty or not one-dimensional")
    steps, cells = len(time), len(indices)
    expected = {
        "accepted_dt_s": (steps,), "values": (steps, cells, 6),
        "ever": (steps, cells, 2), "cell_indices_ijk": (cells, 3),
        "coordinates_m": (cells, 3),
    }
    if cells == 0:
        raise ValueError("History must contain at least one selected cell")
    for name, shape in expected.items():
        if np.asarray(arrays[name]).shape != shape:
            raise ValueError(f"History shape differs for {name}")
    if time.dtype != np.dtype("<f8") or dt.dtype != np.dtype("<f8"):
        raise ValueError("History clocks must use float64")
    if values.dtype != np.dtype("<f8") or coordinates.dtype != np.dtype("<f8"):
        raise ValueError("History values and coordinates must use float64")
    if indices.dtype != np.dtype("<i4") or ever.dtype != np.dtype("bool"):
        raise ValueError("History cell identity or ever-state dtype differs")
    if len({tuple(row) for row in indices.tolist()}) != cells:
        raise ValueError("History cell indices are duplicated")
    _finite_float_arrays(arrays, "History")
    if (not np.isfinite(max_dt_s) or max_dt_s <= 0 or not np.isfinite(event_time_s)
            or event_time_s <= 0):
        raise ValueError("History timestep/event bound is invalid")
    if (np.any(dt <= 0) or np.any(dt > max_dt_s * (1 + 1e-12))
            or np.any(time <= 0) or np.any(np.diff(time) <= 0)
            or not np.allclose(time, np.cumsum(dt), rtol=0, atol=ROUND_OFF_TOLERANCE_S)
            or abs(float(time[-1]) - event_time_s) > ROUND_OFF_TOLERANCE_S):
        raise ValueError("History clock chain must be positive and reach the event endpoint")
    before, after = ever[:, :, 0], ever[:, :, 1]
    if (before[0].any() or np.any(before & ~after)
            or not np.array_equal(before[1:], after[:-1])):
        raise ValueError("History ever-state chain is inconsistent")
    if np.any(values[:, :, 0] <= 0) or np.any(values[:, :, 2] <= 0):
        raise ValueError("History temperature or conductivity is invalid")


def load_history_archive(path: Path, expected_archive_sha256: str,
                         expected_array_sha256: Mapping[str, str], max_dt_s: float,
                         event_time_s: float, *, max_uncompressed_bytes: int = 50_000_000
                         ) -> dict[str, np.ndarray]:
    """Read one hash-bound NPZ and validate its arrays, clock, and state chain."""
    path = Path(path)
    if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        raise ValueError("History archive path cannot be a symlink or junction")
    _require_sha256(sha256_file(path), expected_archive_sha256, "History archive")
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if ({member.filename for member in members} != {name + ".npy" for name in ARRAY_NAMES}
                or len(members) != len(ARRAY_NAMES)
                or sum(member.file_size for member in members) > max_uncompressed_bytes + 4096
                or any(member.flag_bits & 1 for member in members)):
            raise ValueError("History archive members or uncompressed size differ")
    if not isinstance(expected_array_sha256, Mapping) or set(expected_array_sha256) != ARRAY_NAMES:
        raise ValueError("History array hash manifest differs")
    with np.load(path, allow_pickle=False) as archive:
        arrays = {name: archive[name].copy() for name in ARRAY_NAMES}
    validate_history_arrays(arrays, max_dt_s, event_time_s)
    for name, array in arrays.items():
        _require_sha256(array_sha256(array), expected_array_sha256[name], f"History array {name}")
    if sum(array.nbytes for array in arrays.values()) > max_uncompressed_bytes:
        raise ValueError("History arrays exceed the uncompressed size bound")
    return arrays


def _level_key(value: Any) -> str:
    try:
        key = str(float(value))
    except (TypeError, ValueError):
        raise ValueError("History mapping keys must be timestep levels") from None
    if key not in LEVEL_KEYS:
        raise ValueError(f"Unexpected timestep level: {value}")
    return key


def _transition(arrays: Mapping[str, np.ndarray], column: int, event_time_s: float) -> dict[str, Any]:
    ever = arrays["ever"][:, column, :]
    crossed = np.flatnonzero(~ever[:, 0] & ever[:, 1])
    if not len(crossed):
        return {
            "firstEverStep": None, "crossingTime_s": None, "acceptedInterval_s": None,
            "intervalConvention": INTERVAL_CONVENTION, "rightCensored": True,
            "rightCensoredAt_s": float(event_time_s), "terminalCrossing": False,
            "boundarySensitive": False,
        }
    index = int(crossed[0])
    endpoint = float(arrays["time_s"][index])
    lower = float(arrays["time_s"][index - 1]) if index else 0.0
    terminal = index == len(arrays["time_s"]) - 1
    return {
        "firstEverStep": index + 1, "crossingTime_s": endpoint,
        "acceptedInterval_s": [lower, endpoint], "intervalConvention": INTERVAL_CONVENTION,
        "rightCensored": False, "rightCensoredAt_s": None,
        "terminalCrossing": terminal, "boundarySensitive": terminal,
    }


def _comparison(coarse: Mapping[str, Any], fine: Mapping[str, Any], tolerance_s: float) -> dict[str, Any]:
    coarse_time, fine_time = coarse["crossingTime_s"], fine["crossingTime_s"]
    if coarse_time is None and fine_time is None:
        status, delta = "both_absent", None
    elif coarse_time is None or fine_time is None:
        status, delta = "one_sided_crossing", None
    else:
        status = "both_present"
        delta = float(fine_time - coarse_time)
    equivalent = None if delta is None else abs(delta) <= tolerance_s
    return {
        "status": status, "rawDelta_s": delta,
        "deltaDefinition": "finer accepted-step endpoint minus coarser accepted-step endpoint",
        "roundoffEquivalent": equivalent,
        "roundoffTolerance_s": float(tolerance_s),
    }


def analyze_transition_histories(histories_by_dt: Mapping[float, Mapping[str, np.ndarray]],
                                 event_time_s: float, *,
                                 roundoff_tolerance_s: float = ROUND_OFF_TOLERANCE_S
                                 ) -> dict[str, Any]:
    """Summarize first-ever transitions at three levels using accepted-step intervals."""
    if not isinstance(histories_by_dt, Mapping):
        raise ValueError("Histories must be mapped by requested timestep")
    normalized: dict[str, Mapping[str, np.ndarray]] = {}
    for raw_level, arrays in histories_by_dt.items():
        key = _level_key(raw_level)
        if key in normalized:
            raise ValueError("Duplicate timestep level")
        normalized[key] = arrays
    if set(normalized) != set(LEVEL_KEYS):
        raise ValueError("Exactly the 50 ns, 25 ns, and 12.5 ns histories are required")
    if not np.isfinite(event_time_s) or event_time_s <= 0:
        raise ValueError("Event time must be finite and positive")
    if not np.isfinite(roundoff_tolerance_s) or roundoff_tolerance_s < 0:
        raise ValueError("Roundoff tolerance must be finite and non-negative")
    for level, key in zip(LEVELS_S, LEVEL_KEYS):
        validate_history_arrays(normalized[key], level, event_time_s)
    base = normalized[LEVEL_KEYS[0]]
    for key in LEVEL_KEYS[1:]:
        other = normalized[key]
        if (not np.array_equal(base["cell_indices_ijk"], other["cell_indices_ijk"])
                or not np.array_equal(base["coordinates_m"], other["coordinates_m"])):
            raise ValueError("History cell grid or order differs between timestep levels")
    cells = []
    for column, (indices, coordinates) in enumerate(zip(base["cell_indices_ijk"], base["coordinates_m"])):
        per_level = {key: _transition(normalized[key], column, event_time_s) for key in LEVEL_KEYS}
        cells.append({
            "indices_ijk": indices.tolist(), "coordinate_m": coordinates.tolist(),
            "byLevel": {key: per_level[key] for key in LEVEL_KEYS},
            "comparisons": {
                "50nsTo25ns": _comparison(per_level[LEVEL_KEYS[0]], per_level[LEVEL_KEYS[1]], roundoff_tolerance_s),
                "25nsTo12_5ns": _comparison(per_level[LEVEL_KEYS[1]], per_level[LEVEL_KEYS[2]], roundoff_tolerance_s),
            },
        })
    return {
        **DIAGNOSTIC_STATUS, "analysisStatus": "accepted-step-transition-diagnostic",
        "eventTime_s": float(event_time_s), "roundoffTolerance_s": float(roundoff_tolerance_s),
        "intervalConvention": INTERVAL_CONVENTION,
        "transitionTimeMeaning": "first accepted-step endpoint where ever-liquidus changes false to true; bracket uses the stored previous accepted clock and endpoint, not dt subtraction or a continuous physical crossing time",
        "cells": cells,
        "epistemicLimits": [
            "Each discrete detection is bracketed by the stored previous accepted clock and crossing endpoint; no continuous within-step crossing is established.",
            "Crossings on the event's final accepted step are boundary-sensitive at the fixed observation endpoint.",
            "Right-censored cells have no observed crossing by the event time; absence is not evidence of no later crossing.",
            "Roundoff-equivalent deltas retain their raw signed value and are only labeled using the stated tolerance.",
        ],
    }


def _safe_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("Artifact path must remain inside the repository")
    root = Path(root).resolve()
    path = root / relative
    for ancestor in (path, *path.parents):
        if ancestor == root:
            break
        if ancestor.is_symlink() or (hasattr(ancestor, "is_junction") and ancestor.is_junction()):
            raise ValueError("Artifact path contains symlink or junction")
    if not path.resolve().is_relative_to(root):
        raise ValueError("Artifact path escapes repository")
    return path


def _check_report_states(report: Mapping[str, Any], label: str, *, refinement: bool = False) -> None:
    expected = {"experimentalValidation": False, "convergenceConclusion": "inconclusive"}
    if refinement:
        expected.update(solverValidationStatus="unvalidated", NIST="unavailable")
    if report.get("stage") != "completed" or report.get("status") != "diagnostic-only":
        raise ValueError(f"{label} report is not a completed diagnostic report")
    for key, value in expected.items():
        if report.get(key) != value:
            raise ValueError(f"{label} report diagnostic state differs: {key}")


def load_frozen_bundle(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Verify frozen provenance and load the three existing archives without solving."""
    root = Path(root).resolve()
    history_protocol_path = _safe_path(root, "docs/LPBF_FIXED_EVENT_TIME_HISTORY_2026-10-02_PROTOCOL.json")
    refinement_protocol_path = _safe_path(root, "docs/LPBF_FIXED_EVENT_TIME_REFINEMENT_2026-10-02_PROTOCOL.json")
    if history_protocol_path.stat().st_size > MAX_REPORT_BYTES:
        raise ValueError("Frozen local-history protocol exceeds the report size bound")
    history_protocol_raw = history_protocol_path.read_bytes()
    hp = json.loads(history_protocol_raw)
    rp, refinement_protocol_raw = _read_pinned_json(
        refinement_protocol_path, EXPECTED_REFINEMENT_PROTOCOL_SHA256, "Frozen refinement protocol")
    history_report_path = _safe_path(root, rp["historyReport"])
    refinement_report_path = _safe_path(root, rp["output"])
    history_report, history_report_raw = _read_pinned_json(
        history_report_path, rp["historyReportSha256"], "Frozen local-history report")
    refinement_report, refinement_report_raw = _read_pinned_json(
        refinement_report_path, EXPECTED_REFINEMENT_REPORT_SHA256, "Frozen refinement report")
    _check_report_states(history_report, "Local-history")
    _check_report_states(refinement_report, "Refinement", refinement=True)
    if (hp.get("protocolId") != "lpbf-fixed-event-local-history-5um-2026-10-02-v1"
            or rp.get("protocolId") != "lpbf-fixed-event-time-refinement-5um-12_5ns-2026-10-02-v1"
            or history_report.get("protocolId") != hp.get("protocolId")
            or refinement_report.get("protocolId") != rp.get("protocolId")):
        raise ValueError("Protocol/report identifiers differ")
    if (history_report.get("protocolSha256") != sha256_bytes(history_protocol_raw)
            or refinement_report.get("protocolSha256") != sha256_bytes(refinement_protocol_raw)
            or refinement_report.get("historyReportSha256") != rp["historyReportSha256"]):
        raise ValueError("Report-to-protocol provenance hash differs")
    fingerprint = rp["expectedImplementationFingerprint"]
    if (history_report.get("implementationFingerprint") != fingerprint
            or refinement_report.get("implementationFingerprint") != fingerprint
            or history_report.get("priorImplementationFingerprint") != rp["priorImplementationFingerprint"]):
        raise ValueError("Historical solver fingerprints disagree across bound reports")
    if (refinement_report.get("resolvedInputSha256") != rp["expectedInputSha256ByMaxDt"]["1.25e-08"]
            or hp.get("scenarioSha256") != rp["scenarioSha256"]
            or history_report.get("priorReportSha256") != rp["priorReportSha256"]):
        raise ValueError("Frozen input or ancestry identity differs")
    old_rows = history_report.get("rows", [])
    new_rows = refinement_report.get("rows", [])
    if len(old_rows) != 2 or len(new_rows) != 1:
        raise ValueError("Expected two reused histories and one new 12.5 ns history")
    rows_by_level = {str(float(row["maxDt_s"])): row for row in old_rows}
    if set(rows_by_level) != {"5e-08", "2.5e-08"} or float(new_rows[0]["maxDt_s"]) != 1.25e-8:
        raise ValueError("History report timestep rows differ")
    expected_names = {"5e-08": "maxdt-5.0000e-08.npz", "2.5e-08": "maxdt-2.5000e-08.npz"}
    arrays_by_dt: dict[float, dict[str, np.ndarray]] = {}
    lineage = []
    import sys
    sys.path.insert(0, str(root / "python"))
    # Import only the existing reader; its __main__ guard keeps this a read-only path.
    import run_lpbf_fixed_event_time_refinement_probe as refinement_reader

    for key, dt, steps in (("5e-08", 5e-8, 5000), ("2.5e-08", 2.5e-8, 10000)):
        row = rows_by_level[key]
        artifact = row.get("historyArtifact", {})
        expected_path = f"docs/LPBF_FIXED_EVENT_TIME_HISTORY_FIELDS_2026-10-02/{expected_names[key]}"
        if (artifact.get("path") != expected_path or artifact.get("sha256") != rp["historyArchiveSha256ByMaxDt"][key]
                or row.get("resolvedInputSha256") != rp["expectedInputSha256ByMaxDt"][key]
                or row.get("acceptedSteps") != steps or row.get("priorFieldExactMatch") is not True):
            raise ValueError(f"Frozen old history row identity differs: {key}")
        path = _safe_path(root, expected_path)
        if path.stat().st_size != artifact.get("byteSize"):
            raise ValueError(f"Frozen old archive byte size differs: {key}")
        arrays = refinement_reader._read_history(
            path, artifact["sha256"], rp["historyArraySha256ByMaxDt"][key], dt,
            rp["expectedEventTime_s"], steps, rp["maximumHistoryBytes"])
        arrays_by_dt[dt] = arrays
        lineage.append({"level_s": dt, "archiveSha256": artifact["sha256"],
                        "arraySha256": rp["historyArraySha256ByMaxDt"][key],
                        "archivePath": artifact["path"]})
    new_row = new_rows[0]
    new_artifact = new_row.get("historyArtifact", {})
    expected_new_path = "docs/LPBF_FIXED_EVENT_TIME_REFINEMENT_2026-10-02_FIELDS/history-maxdt-1.2500e-08.npz"
    if (new_artifact.get("path") != expected_new_path
            or new_row.get("resolvedInputSha256") != rp["expectedInputSha256ByMaxDt"]["1.25e-08"]
            or new_row.get("acceptedSteps", rp["maximumStepsByMaxDt"]["1.25e-08"] + 1)
                > rp["maximumStepsByMaxDt"]["1.25e-08"]
            or new_row.get("acceptedCellSteps") != new_row.get("acceptedSteps") * rp["expectedCells"]
            or new_row.get("acceptedCellSteps", rp["maximumTotalCellSteps"] + 1)
                > rp["maximumTotalCellSteps"]):
        raise ValueError("Frozen new history row identity differs")
    new_path = _safe_path(root, expected_new_path)
    if new_path.stat().st_size != new_artifact.get("byteSize"):
        raise ValueError("Frozen new archive byte size differs")
    arrays_by_dt[1.25e-8] = refinement_reader._read_history(
        new_path, new_artifact["sha256"],
        new_artifact["arraySha256"], 1.25e-8, rp["expectedEventTime_s"],
        new_row["acceptedSteps"], rp["maximumHistoryBytes"])
    lineage.append({"level_s": 1.25e-8, "archiveSha256": new_artifact["sha256"],
                    "arraySha256": new_artifact["arraySha256"], "archivePath": expected_new_path})
    selected = rp["orderedSelectedCells"]
    expected_indices = np.asarray([item["indices_ijk"] for item in selected], dtype="<i4")
    expected_coordinates = np.asarray([item["coordinate_m"] for item in selected], dtype="<f8")
    for dt, arrays in arrays_by_dt.items():
        if (not np.array_equal(arrays["cell_indices_ijk"], expected_indices)
                or not np.array_equal(arrays["coordinates_m"], expected_coordinates)):
            raise ValueError(f"Archived cell identity differs at level {dt}")
    provenance = {
        "historyReaderSha256": sha256_file(Path(refinement_reader.__file__)),
        "historyProtocolSha256": sha256_bytes(history_protocol_raw),
        "refinementProtocolSha256": sha256_bytes(refinement_protocol_raw),
        "historyReportSha256": sha256_file(history_report_path),
        "refinementReportSha256": sha256_file(refinement_report_path),
        "historicalImplementationFingerprint": fingerprint,
        "executionHeadCommit": refinement_report.get("executionHeadCommit"),
        "runnerSha256": refinement_report.get("runnerSha256"),
        "historyHelperSha256": refinement_report.get("historyHelperSha256"),
        "archiveLineage": lineage,
    }
    return arrays_by_dt, provenance, rp


def _fmt_time(value: float | None) -> str:
    return "censored" if value is None else f"{value:.9g} s"


def _fmt_bracket(item: Mapping[str, Any]) -> str:
    interval = item["acceptedInterval_s"]
    if interval is None:
        return f"right-censored at {_fmt_time(item['rightCensoredAt_s'])}"
    suffix = "; terminal/boundary-sensitive" if item["terminalCrossing"] else ""
    return f"({_fmt_time(interval[0])}, {_fmt_time(interval[1])}]{suffix}"


def render_markdown(analysis: Mapping[str, Any]) -> str:
    lines = [
        "# LPBF Fixed-Event Liquidus Transition Analysis",
        "",
        f"Event time: `{analysis['eventTime_s']:.17g} s`. This is a diagnostic comparison of accepted-step observations.",
        "",
        "| Cell (i, j, k) | 50 ns endpoint / interval | 25 ns endpoint / interval | 12.5 ns endpoint / interval | Δ 50→25 (fine−coarse) | Δ 25→12.5 (fine−coarse) |",
        "|---|---|---|---|---|---|",
    ]
    for cell in analysis["cells"]:
        by_level = cell["byLevel"]
        c1 = cell["comparisons"]["50nsTo25ns"]
        c2 = cell["comparisons"]["25nsTo12_5ns"]
        def delta(item: Mapping[str, Any]) -> str:
            if item["rawDelta_s"] is None:
                return item["status"]
            text = f"{item['rawDelta_s']:+.9g} s"
            return text + (" (roundoff-equivalent)" if item["roundoffEquivalent"] else "")
        lines.append(
            f"| `{tuple(cell['indices_ijk'])}` | {_fmt_time(by_level['5e-08']['crossingTime_s'])}; {_fmt_bracket(by_level['5e-08'])} | "
            f"{_fmt_time(by_level['2.5e-08']['crossingTime_s'])}; {_fmt_bracket(by_level['2.5e-08'])} | "
            f"{_fmt_time(by_level['1.25e-08']['crossingTime_s'])}; {_fmt_bracket(by_level['1.25e-08'])} | {delta(c1)} | {delta(c2)} |"
        )
    lines.extend(["", "## Interpretation limits", ""])
    lines.extend(f"- {limit}" for limit in analysis["epistemicLimits"])
    lines.extend(["", f"Roundoff-equivalence threshold: `{analysis['roundoffTolerance_s']:.1e} s`; raw signed deltas are retained.", ""])
    return "\n".join(lines)


def write_outputs(json_path: Path, markdown_path: Path, report: Mapping[str, Any], markdown: str) -> None:
    """Publish both reports atomically per file and refuse all overwrites."""
    destinations = (Path(json_path), Path(markdown_path))
    if destinations[0] == destinations[1] or any(path.exists() for path in destinations):
        raise FileExistsError("Analysis output already exists")
    if any(not path.parent.is_dir() for path in destinations):
        raise FileNotFoundError("Output directory must already exist")
    contents = (json.dumps(report, indent=2, allow_nan=False) + "\n", markdown)
    temporary: list[Path] = []
    linked: list[tuple[Path, Path]] = []
    try:
        for destination, content in zip(destinations, contents):
            fd, name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
            temp = Path(name)
            temporary.append(temp)
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        for temp, destination in zip(temporary, destinations):
            os.link(temp, destination)
            linked.append((temp, destination))
    except Exception:
        for temp, path in linked:
            try:
                if path.exists() and os.path.samefile(temp, path):
                    path.unlink()
            except OSError:
                pass
        raise
    finally:
        for temp in temporary:
            try:
                temp.unlink()
            except OSError:
                pass


def run_analysis(root: Path = ROOT) -> tuple[dict[str, Any], str]:
    histories, provenance, protocol = load_frozen_bundle(root)
    analysis = analyze_transition_histories(histories, protocol["expectedEventTime_s"])
    report = {**analysis, "provenance": {**provenance,
              "analysisSource": "python/analyze_lpbf_fixed_event_transitions.py",
              "analysisSourceSha256": sha256_file(Path(__file__))}}
    return report, render_markdown(report)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-markdown", type=Path, default=OUTPUT_MARKDOWN)
    args = parser.parse_args()
    report, markdown = run_analysis()
    write_outputs(args.output_json, args.output_markdown, report, markdown)
    print(json.dumps({"status": report["analysisStatus"], "cells": len(report["cells"]),
                      "outputs": [str(args.output_json), str(args.output_markdown)]}, indent=2))


if __name__ == "__main__":
    main()
