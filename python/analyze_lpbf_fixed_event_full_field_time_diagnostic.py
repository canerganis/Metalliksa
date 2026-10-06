#!/usr/bin/env python3
"""Hash-verified full-field comparison of the archived 50/25/12.5 ns runs.

This reads historical NPZ artifacts only. It does not import or run a solver.
The output is a numerical diagnostic, not a convergence or validation claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
CELLS = 526_592
GRID_SHAPE = (88, 88, 68)
SPACING_M = 5e-6
EVENT_TIME_S = 250e-6
CURRENT_CANDIDATE = "ec3a5fcbeb1c5aa1b250ed31a4e812796c5d17ce"
SOLIDUS_K = 1533.15
LIQUIDUS_K = 1609.15
DISCLAIMER = (
    "Historical synthetic numerical diagnostic only. These archived fields do not "
    "represent the ec3a5fc/current solver run and do not establish time or mesh "
    "convergence, physical accuracy, or experimental validation. Overall convergence "
    "remains inconclusive; NIST comparison unavailable; experimental validity unvalidated."
)

BASE_REPORT = Path("docs/LPBF_FIXED_EVENT_5UM_TIME_2026-10-02.json")
BASE_PROTOCOL = Path("docs/LPBF_FIXED_EVENT_5UM_TIME_2026-10-02_PROTOCOL.json")
REFINEMENT_REPORT = Path("docs/LPBF_FIXED_EVENT_TIME_REFINEMENT_2026-10-02.json")
REFINEMENT_PROTOCOL = Path("docs/LPBF_FIXED_EVENT_TIME_REFINEMENT_2026-10-02_PROTOCOL.json")
HISTORY_REPORT = Path("docs/LPBF_FIXED_EVENT_TIME_HISTORY_2026-10-02.json")

LEVELS: tuple[dict[str, Any], ...] = (
    {
        "label": "50ns",
        "max_dt_s": 50e-9,
        "steps": 5_000,
        "path": Path("docs/LPBF_FIXED_EVENT_5UM_TIME_FIELDS_2026-10-02/maxdt-5.0000e-08.npz"),
        "sha256": "1a771da9f6f873a27bd68fadd2a43eb3671bc67549acc253171aea0c1812bd23",
    },
    {
        "label": "25ns",
        "max_dt_s": 25e-9,
        "steps": 10_000,
        "path": Path("docs/LPBF_FIXED_EVENT_5UM_TIME_FIELDS_2026-10-02/maxdt-2.5000e-08.npz"),
        "sha256": "eeda2dca62f823ed250f6818de5bf1afd6b6a4cf9362a2ccd60fa29ef66bfacd",
    },
    {
        "label": "12.5ns",
        "max_dt_s": 12.5e-9,
        "steps": 20_000,
        "path": Path("docs/LPBF_FIXED_EVENT_TIME_REFINEMENT_2026-10-02_FIELDS/finalstate-maxdt-1.2500e-08.npz"),
        "sha256": "db7fc10d052764db456f19f7f10c5756f830af6dfa952f99426e27fbce1979d8",
    },
)

COMMON_ARRAYS = {"coordinates_m", "temperature_K", "enthalpy_J_m3", "density_kg_m3", "accepted_dt_s"}
EXPECTED_ARRAYS = {
    "50ns": COMMON_ARRAYS,
    "25ns": COMMON_ARRAYS,
    "12.5ns": COMMON_ARRAYS | {"time_s", "local_final_ever_observer_derived"},
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_array(value: np.ndarray) -> str:
    return sha256_bytes(np.ascontiguousarray(value).tobytes(order="C"))


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"Expected JSON object: {path}")
    return value


def verify_provenance() -> dict[str, Any]:
    paths = {
        "base_report": BASE_REPORT,
        "base_protocol": BASE_PROTOCOL,
        "refinement_report": REFINEMENT_REPORT,
        "refinement_protocol": REFINEMENT_PROTOCOL,
        "history_report": HISTORY_REPORT,
    }
    hashes = {key: sha256_file(ROOT / path) for key, path in paths.items()}
    base, base_protocol = read_json(ROOT / BASE_REPORT), read_json(ROOT / BASE_PROTOCOL)
    refined = read_json(ROOT / REFINEMENT_REPORT)
    refined_protocol = read_json(ROOT / REFINEMENT_PROTOCOL)
    history = read_json(ROOT / HISTORY_REPORT)

    require(base.get("stage") == "completed" and base.get("experimentalValidation") is False,
            "50/25 ns source report is not a completed non-experimental diagnostic")
    require(refined.get("stage") == "completed" and refined.get("diagnosticOnly") is True
            and refined.get("experimentalValidation") is False,
            "12.5 ns source report is not a completed non-experimental diagnostic")
    require(base.get("convergenceConclusion") == "inconclusive"
            and refined.get("convergenceStatus") == "inconclusive"
            and refined.get("NIST") == "unavailable"
            and refined.get("solverValidationStatus") == "unvalidated",
            "Historical records no longer carry the expected scientific evidence limits")
    require(base.get("protocolSha256") == hashes["base_protocol"],
            "50/25 ns report does not bind the current protocol bytes")
    require(refined.get("protocolSha256") == hashes["refinement_protocol"],
            "12.5 ns report does not bind the current protocol bytes")
    require(refined.get("priorReportSha256") == hashes["base_report"],
            "12.5 ns report does not bind the 50/25 ns report bytes")
    require(refined.get("historyReportSha256") == hashes["history_report"],
            "12.5 ns report does not bind the bridge report bytes")
    require(refined_protocol.get("priorReportSha256") == hashes["base_report"]
            and refined_protocol.get("historyReportSha256") == hashes["history_report"],
            "12.5 ns protocol does not bind both historical reports")

    scenario_sha = base.get("scenarioSha256")
    require(scenario_sha and scenario_sha == refined.get("scenarioSha256")
            == base_protocol.get("scenarioSha256") == refined_protocol.get("scenarioSha256"),
            "Scenario identities differ across reports/protocols")
    base_event_time = float(base_protocol.get("expectedEventTime_s"))
    refined_event_time = float(refined_protocol.get("expectedEventTime_s"))
    require(abs(base_event_time - refined_event_time) <= 1e-18
            and abs(base_event_time - EVENT_TIME_S) <= 1e-18,
            "Protocols do not describe the same 250 us event")
    require(base_protocol.get("expectedCells") == CELLS
            and refined_protocol.get("expectedCells") == CELLS,
            "Protocol cell count differs from the pinned field archive")
    require(tuple(base_protocol.get("levels", [])) == (50e-9, 25e-9)
            and tuple(refined_protocol.get("levels", [])) == (50e-9, 25e-9, 12.5e-9),
            "Protocols do not declare the archived timestep levels")
    require(base_protocol.get("materialRevisionSha256") == refined.get("materialRevisionSha256")
            == refined_protocol.get("materialRevisionSha256"),
            "Material revision identity differs across the run chain")
    require(base.get("implementationFingerprint") == refined.get("priorImplementationFingerprint"),
            "The historical implementation fingerprint bridge is inconsistent")
    require(history.get("implementationFingerprint") == refined.get("implementationFingerprint")
            and history.get("priorImplementationFingerprint") == base.get("implementationFingerprint"),
            "History report does not bridge the historical implementations")

    history_rows = {float(row["maxDt_s"]): row for row in history.get("rows", [])}
    for level in LEVELS[:2]:
        row = history_rows.get(level["max_dt_s"])
        require(row is not None and row.get("priorFieldExactMatch") is True,
                f"Historical observer bridge lacks exact field match for {level['label']}")
        require(row.get("priorFieldSha256") == level["sha256"],
                f"Historical observer bridge archive hash differs for {level['label']}")

    material_rows = [row for row in base.get("rows", []) if row.get("maxDt_s") in (50e-9, 25e-9)]
    require(len(material_rows) == 2, "Expected both 50 ns and 25 ns material rows")
    for row in material_rows:
        phase = row.get("phasePlaneAudit", {})
        require(phase.get("solidus_K") == SOLIDUS_K and phase.get("liquidus_K") == LIQUIDUS_K,
                "Phase classification thresholds differ from the archived IN718 record")

    return {
        "record_hashes": hashes,
        "event_time_s": base_event_time,
        "scenario_sha256": scenario_sha,
        "material_revision_sha256": refined.get("materialRevisionSha256"),
        "historical_execution": {
            "50ns_25ns_commit": base.get("executionHeadCommit"),
            "50ns_25ns_implementation_fingerprint": base.get("implementationFingerprint"),
            "12_5ns_commit": refined.get("executionHeadCommit"),
            "12_5ns_implementation_fingerprint": refined.get("implementationFingerprint"),
            "current_candidate_commit": CURRENT_CANDIDATE,
            "field_identity_bridge": "priorFieldExactMatch=true for 50 ns and 25 ns",
            "current_candidate_binding": False,
        },
    }


def artifact_for_level(report: dict[str, Any], level: dict[str, Any]) -> dict[str, Any]:
    wanted = level["sha256"]
    rows = report.get("rows", [])
    for row in rows:
        artifact = row.get("fieldArtifact")
        if artifact and artifact.get("sha256") == wanted:
            require(row.get("maxDt_s") == level["max_dt_s"],
                    f"Report level does not match {level['label']}")
            return artifact
    raise ValueError(f"No report-bound field artifact found for {level['label']}")


def load_archive(level: dict[str, Any], artifact: dict[str, Any]) -> dict[str, np.ndarray]:
    path = ROOT / level["path"]
    require(path.is_file(), f"Missing field archive: {path}")
    require(sha256_file(path) == level["sha256"] == artifact.get("sha256"),
            f"Field archive SHA-256 mismatch: {path}")
    require(path.stat().st_size == artifact.get("byteSize"), f"Field archive byte size mismatch: {path}")

    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        expected_members = {f"{key}.npy" for key in EXPECTED_ARRAYS[level["label"]]}
        require({member.filename for member in members} == expected_members,
                f"Unexpected NPZ members: {path}")
        require(sum(member.file_size for member in members) <= 32_000_000,
                f"Uncompressed NPZ exceeds the diagnostic size limit: {path}")
    with np.load(path, allow_pickle=False) as archive:
        arrays = {key: archive[key] for key in archive.files}

    expected_hashes = artifact.get("fieldSha256", artifact.get("arraySha256", {}))
    require(set(expected_hashes) == set(arrays), f"Report array-hash keys differ: {level['label']}")
    for key, array in arrays.items():
        require(array.dtype != object, f"Object array rejected: {level['label']}/{key}")
        if np.issubdtype(array.dtype, np.number):
            require(bool(np.isfinite(array).all()), f"Non-finite data: {level['label']}/{key}")
        require(sha256_array(array) == expected_hashes[key],
                f"Array SHA-256 mismatch: {level['label']}/{key}")
    require(arrays["coordinates_m"].shape == (CELLS, 3), "Unexpected coordinate shape")
    for key in ("temperature_K", "enthalpy_J_m3", "density_kg_m3"):
        require(arrays[key].shape == (CELLS,), f"Unexpected field shape: {key}")
    require(arrays["accepted_dt_s"].shape == (level["steps"],), "Unexpected timestep count")
    require(arrays["coordinates_m"].dtype == np.float64, "Coordinates must be float64")
    return arrays


def audit_grid(coordinates: np.ndarray) -> dict[str, Any]:
    axes = [np.unique(coordinates[:, index]) for index in range(3)]
    shape = tuple(int(axis.size) for axis in axes)
    require(shape == GRID_SHAPE and math.prod(shape) == CELLS, f"Unexpected Cartesian grid shape: {shape}")
    spacings = [np.diff(axis) for axis in axes]
    for name, values in zip(("x", "y", "z"), spacings):
        require(values.size > 0 and np.allclose(values, SPACING_M, rtol=0.0, atol=1e-16),
                f"Grid is not uniformly spaced at 5 um on {name}")
    require(np.unique(coordinates, axis=0).shape[0] == CELLS, "Coordinate rows are not unique")
    return {
        "shape_xyz": shape,
        "cell_count": CELLS,
        "uniform_spacing_m": SPACING_M,
        "equal_cell_volume_m3": SPACING_M ** 3,
        "weighting": "equal-cell RMS is volume-weighted because the verified grid is uniform",
        "substrate_side_cells_z_lt_0": int(np.count_nonzero(coordinates[:, 2] < 0.0)),
        "powder_side_cells_z_ge_0": int(np.count_nonzero(coordinates[:, 2] >= 0.0)),
    }


def field_metrics(coarse: np.ndarray, fine: np.ndarray, coordinates: np.ndarray,
                  mask: np.ndarray, temperature: bool) -> dict[str, Any]:
    difference = fine[mask] - coarse[mask]
    selected_coordinates = coordinates[mask]
    absolute = np.abs(difference)
    local_max = int(np.argmax(absolute))
    fine_norm = float(np.linalg.norm(fine[mask].astype(np.float64)))
    relative_l2 = float(np.linalg.norm(difference.astype(np.float64)) / fine_norm) if fine_norm else None
    result: dict[str, Any] = {
        "cell_count": int(mask.sum()),
        "equal_volume_rms_absolute_difference": float(np.sqrt(np.mean(np.square(difference, dtype=np.float64)))),
        "absolute_volume_l2_difference": float(
            math.sqrt(float(np.sum(np.square(difference, dtype=np.float64))) * SPACING_M ** 3)),
        "absolute_volume_l2_unit": "K m^(3/2)" if temperature else "J m^(-3/2)",
        "relative_l2_normalized_by_fine_field": relative_l2,
        "maximum_absolute_difference": float(absolute[local_max]),
        "signed_fine_minus_coarse_at_maximum": float(difference[local_max]),
        "maximum_coordinate_m": [float(value) for value in selected_coordinates[local_max]],
    }
    if temperature:
        coarse_t, fine_t = coarse[mask], fine[mask]
        coarse_class = np.where(coarse_t < SOLIDUS_K, 0, np.where(coarse_t < LIQUIDUS_K, 1, 2))
        fine_class = np.where(fine_t < SOLIDUS_K, 0, np.where(fine_t < LIQUIDUS_K, 1, 2))
        result.update({
            "cells_abs_difference_gt_10_K": int(np.count_nonzero(absolute > 10.0)),
            "cells_abs_difference_gt_50_K": int(np.count_nonzero(absolute > 50.0)),
            "phase_class_mismatch_cells": int(np.count_nonzero(coarse_class != fine_class)),
        })
    return result


def compare_pair(coarse: dict[str, np.ndarray], fine: dict[str, np.ndarray],
                 coordinates: np.ndarray, label: str) -> dict[str, Any]:
    masks = {
        "all_cells": np.ones(CELLS, dtype=bool),
        "substrate_side_z_lt_0": coordinates[:, 2] < 0.0,
        "powder_side_z_ge_0": coordinates[:, 2] >= 0.0,
    }
    output: dict[str, Any] = {"pair": label, "direction": "fine minus coarse", "fields": {}}
    for key, unit, temperature in (("temperature_K", "K", True), ("enthalpy_J_m3", "J/m^3", False)):
        output["fields"][key] = {
            "unit": unit,
            "regions": {
                name: field_metrics(coarse[key], fine[key], coordinates, mask, temperature)
                for name, mask in masks.items()
            },
        }
    return output


def timestep_row(report: dict[str, Any], level: dict[str, Any]) -> dict[str, Any]:
    for row in report.get("rows", []):
        if row.get("maxDt_s") == level["max_dt_s"]:
            return row
    raise ValueError(f"Missing source timestep row for {level['label']}")


def write_new_file(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="xb", prefix=f".{path.name}.", suffix=".tmp", dir=path.parent,
                                     delete=False) as stream:
        temp_path = Path(stream.name)
        payload = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        # A hard link publishes the complete file and fails rather than replacing an existing result.
        os.link(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def run(output_arg: str) -> dict[str, Any]:
    output = Path(output_arg)
    if not output.is_absolute():
        output = ROOT / output
    output = output.resolve()
    require(output != ROOT and ROOT in output.parents, "Output must be inside the repository")
    require(not output.exists(), f"Refusing to overwrite existing output: {output}")

    provenance = verify_provenance()
    base_report = read_json(ROOT / BASE_REPORT)
    refinement_report = read_json(ROOT / REFINEMENT_REPORT)
    artifacts: dict[str, dict[str, Any]] = {}
    for level in LEVELS[:2]:
        artifacts[level["label"]] = artifact_for_level(base_report, level)
    row_12_5 = next((row for row in refinement_report.get("rows", [])
                     if row.get("maxDt_s") == LEVELS[2]["max_dt_s"]), None)
    require(row_12_5 is not None, "Missing 12.5 ns refinement row")
    artifacts["12.5ns"] = row_12_5["finalstateArtifact"]

    loaded = {level["label"]: load_archive(level, artifacts[level["label"]]) for level in LEVELS}
    coordinates = loaded["50ns"]["coordinates_m"]
    for label in ("25ns", "12.5ns"):
        require(np.array_equal(coordinates, loaded[label]["coordinates_m"]), f"Coordinates differ at {label}")
        require(np.array_equal(loaded["50ns"]["density_kg_m3"], loaded[label]["density_kg_m3"]),
                f"Density differs at {label}")

    grid = audit_grid(coordinates)
    base_rows = {level["label"]: timestep_row(base_report, level) for level in LEVELS[:2]}
    event_audit: dict[str, Any] = {}
    for level in LEVELS:
        arrays = loaded[level["label"]]
        dt = arrays["accepted_dt_s"]
        target = float(provenance["event_time_s"])
        require(bool(np.all(dt > 0.0)), f"Non-positive accepted timestep in {level['label']}")
        max_dt_tolerance = 8.0 * float(np.spacing(np.float64(level["max_dt_s"])))
        require(float(np.max(dt)) <= level["max_dt_s"] + max_dt_tolerance,
                f"Accepted timestep exceeds requested maximum in {level['label']}")
        sequential_time = 0.0
        for accepted_dt in dt:
            sequential_time += float(accepted_dt)
        sum_dt = float(np.sum(dt, dtype=np.float64))
        tolerance = len(dt) * np.finfo(np.float64).eps * float(np.sum(np.abs(dt), dtype=np.float64))
        if level["label"] in ("50ns", "25ns"):
            artifact = artifacts[level["label"]]
            target = float(artifact["targetTime_s"])
            clock_record = base_rows[level["label"]]["acceptedClockReplay"]
            tolerance = max(tolerance, float(clock_record["roundoffTolerance_s"]))
            require(abs(sequential_time - float(clock_record["replayedTime_s"])) <= tolerance,
                    f"Sequential timestep replay differs from source clock for {level['label']}")
            actual = float(artifact["actualTime_s"])
        else:
            actual = float(arrays["time_s"])
        require(abs(target - float(provenance["event_time_s"])) <= 1e-18,
                f"Unexpected event target for {level['label']}")
        require(abs(sequential_time - actual) <= tolerance and abs(actual - target) <= tolerance,
                f"Accepted timestep clock does not reach the event for {level['label']}")
        event_audit[level["label"]] = {
            "accepted_step_count": int(dt.size),
            "requested_max_dt_s": level["max_dt_s"],
            "maximum_accepted_dt_s": float(np.max(dt)),
            "sum_accepted_dt_s": sum_dt,
            "sequential_replayed_time_s": sequential_time,
            "recorded_or_derived_roundoff_tolerance_s": tolerance,
            "actual_event_time_s": actual,
            "target_event_time_s": target,
            "passed": True,
        }

    pairs = [
        compare_pair(loaded["50ns"], loaded["25ns"], coordinates, "50ns_to_25ns"),
        compare_pair(loaded["25ns"], loaded["12.5ns"], coordinates, "25ns_to_12.5ns"),
    ]
    hot_index = int(np.argmax(np.abs(loaded["25ns"]["temperature_K"] - loaded["50ns"]["temperature_K"])))
    hotspot = {
        "selected_by": "maximum absolute temperature difference in 50ns_to_25ns pair",
        "coordinate_m": [float(value) for value in coordinates[hot_index]],
        "temperature_K_by_level": {
            level["label"]: float(loaded[level["label"]]["temperature_K"][hot_index]) for level in LEVELS
        },
        "enthalpy_J_m3_by_level": {
            level["label"]: float(loaded[level["label"]]["enthalpy_J_m3"][hot_index]) for level in LEVELS
        },
        "historical_50ns_to_25ns_abs_temperature_difference_K": float(
            abs(loaded["25ns"]["temperature_K"][hot_index] - loaded["50ns"]["temperature_K"][hot_index])) ,
        "scope": "tracks the archived pairwise maximum cell across all three historical levels; not a physical hotspot claim",
    }
    coarse_metrics = pairs[0]["fields"]
    fine_metrics = pairs[1]["fields"]
    compared = [
        coarse_metrics[field]["regions"]["all_cells"][metric]
        for field in ("temperature_K", "enthalpy_J_m3")
        for metric in ("equal_volume_rms_absolute_difference", "maximum_absolute_difference")
    ]
    refined = [
        fine_metrics[field]["regions"]["all_cells"][metric]
        for field in ("temperature_K", "enthalpy_J_m3")
        for metric in ("equal_volume_rms_absolute_difference", "maximum_absolute_difference")
    ]
    all_metrics_decreased = all(right < left for left, right in zip(compared, refined))

    return {
        "schema_version": 1,
        "status": "diagnostic-only",
        "statement": DISCLAIMER,
        "input_artifacts": {
            level["label"]: {
                "path": level["path"].as_posix(),
                "sha256": level["sha256"],
                "bytes": (ROOT / level["path"]).stat().st_size,
                "steps": level["steps"],
                "max_dt_s": level["max_dt_s"],
                "report_array_sha256": artifacts[level["label"]].get(
                    "fieldSha256", artifacts[level["label"]].get("arraySha256")),
            }
            for level in LEVELS
        },
        "provenance": provenance,
        "grid_audit": grid,
        "event_clock_audit": event_audit,
        "tracked_50ns_to_25ns_temperature_hotspot": hotspot,
        "phase_classification": {
            "solidus_K": SOLIDUS_K,
            "liquidus_K": LIQUIDUS_K,
            "classes": {"solid": "T < solidus", "mushy": "solidus <= T < liquidus", "liquid": "T >= liquidus"},
            "scope": "diagnostic classification from the recorded IN718 values; not experimental evidence",
        },
        "pairwise_full_field_diagnostics": pairs,
        "trend_summary": {
            "all_global_T_H_rms_and_max_differences_decrease_on_refinement": all_metrics_decreased,
            "interpretation": "local full-field temporal diagnostic decrease" if all_metrics_decreased
            else "nonmonotonic or not-decreasing full-field temporal diagnostic",
            "does_not_establish_convergence": True,
        },
        "validation_checks": {
            "archive_and_array_hashes_match_source_reports": True,
            "report_protocol_and_historical_bridge_hashes_match": True,
            "all_coordinates_bit_identical": True,
            "all_density_arrays_bit_identical": True,
            "uniform_cartesian_grid_verified": True,
            "accepted_dt_replayed_sequentially_with_positive_and_max_dt_bounds": True,
            "historical_run_data_not_current_candidate": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="New JSON output path inside this repository; existing paths are refused")
    args = parser.parse_args()
    try:
        report = run(args.output)
        output = Path(args.output)
        if not output.is_absolute():
            output = ROOT / output
        output = output.resolve()
        write_new_file(output, report)
        print(json.dumps({
            "status": report["status"],
            "output": output.relative_to(ROOT).as_posix(),
            "cells": report["grid_audit"]["cell_count"],
            "trend": report["trend_summary"]["interpretation"],
            "disclaimer": report["statement"],
        }, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:  # diagnostic CLI: fail closed with no partial report publication
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
