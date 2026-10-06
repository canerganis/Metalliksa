#!/usr/bin/env python3
"""Run a provenance-rich, synthetic IN718 LPBF solver-branch sensitivity pilot."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import math
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lpbf_thermal_solver import calculate_meltpool_physics, thermal_props


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_BASE = REPO_ROOT / "data" / "synthetic"
EXISTING_DATASET = REPO_ROOT / "data" / "synthetic_process_map.csv"
PROCESS_CASE_SOURCE = "python/benchmark_phase7_microstructure.py"
SOURCE_FILES = (
    "python/lpbf_thermal_solver.py",
    "python/four_alloy_materials.py",
    "python/powder_bed_raytracer.py",
    PROCESS_CASE_SOURCE,
)
PROCESS_CASES = (
    {"case_id": "repo_case_220w_900mms", "laser_power_W": 220.0, "scan_speed_mm_s": 900.0},
    {"case_id": "repo_case_285w_960mms", "laser_power_W": 285.0, "scan_speed_mm_s": 960.0},
    {"case_id": "repo_case_150w_1500mms", "laser_power_W": 150.0, "scan_speed_mm_s": 1500.0},
)
ABSORPTIVITY_SCALES = (0.9, 1.0, 1.1)
HEAT_SOURCES = ("rosenthal", "eagar-tsai")
COMMON_INPUTS = {
    "beam_diameter_um": 80.0,
    "preheat_temp_C": 80.0,
    "layer_thickness_um": 40.0,
    "hatch_spacing_um": 100.0,
    "laser_wavelength": "IR_1064nm",
    "process_seed_metadata_only": 42,
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_revision() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _git_worktree_dirty() -> bool | None:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        return bool(result.stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        return None


def build_design(base_absorptivity: float) -> list[dict[str, Any]]:
    if not math.isfinite(base_absorptivity) or not 0.0 < base_absorptivity < 1.0:
        raise ValueError("IN718 IR absorptivity must be finite and between 0 and 1")
    rows = []
    for case in PROCESS_CASES:
        for scale in ABSORPTIVITY_SCALES:
            for heat_source in HEAT_SOURCES:
                rows.append(
                    {
                        "run_id": f"{case['case_id']}__eta{scale:.1f}__{heat_source}",
                        "process_case": dict(case),
                        "absorptivity_scale": scale,
                        "absorptivity_IR_override": base_absorptivity * scale,
                        "heat_source": heat_source,
                        "inputs": {
                            **COMMON_INPUTS,
                            "material_name": "Inconel 718",
                            "laser_power_W": case["laser_power_W"],
                            "scan_speed_mm_s": case["scan_speed_mm_s"],
                        },
                    }
                )
    return rows


def summarize_result(result: dict[str, Any], *, warnings: str, runtime_s: float) -> dict[str, Any]:
    process = result.get("processParameters") or {}
    geometry = result.get("meltPoolGeometry") or {}
    thermal = result.get("thermal") or {}
    recoil = result.get("hydrodynamicsAndRecoil") or {}
    metrics = {
        "melt_pool_width_um": geometry.get("width_um"),
        "melt_pool_depth_um": geometry.get("depth_um"),
        "melt_pool_length_um": geometry.get("length_um"),
        # The current solver names this field peakTemperature_C, but it samples
        # T_field(0, 0, 0); report its implementation meaning, not a spatial max.
        "centerline_temperature_C_reported_as_peak": recoil.get("peakTemperature_C"),
        "normalized_enthalpy": process.get("normalizedEnthalpy"),
        "effective_absorptivity": process.get("effectiveAbsorptivity"),
        "conduction_absorptivity": process.get("conductionAbsorptivity"),
        "fabbro_absorptivity": process.get("fabbroAbsorptivity"),
        "geometry_regime": geometry.get("regime"),
        "depth_to_width_ratio": geometry.get("depthToWidthRatio_D_over_W"),
        "thermal_output_present": bool(thermal),
    }
    finite_numeric_metrics = {}
    for key, value in list(metrics.items()):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            is_finite = math.isfinite(float(value))
            finite_numeric_metrics[key] = is_finite
            if not is_finite:
                metrics[key] = None
    return {
        "solver_success": result.get("success") is True,
        "engine": result.get("engine"),
        "model_id": result.get("modelId"),
        "reported_heat_source": result.get("heatSourceModel"),
        "metrics": metrics,
        "finite_numeric_metrics": finite_numeric_metrics,
        "raytrace_fallback_warning_seen": "GPU Powder Bed Ray Tracing failed" in warnings,
        "runtime_s": round(runtime_s, 6),
    }


def _stable_result_projection(row: dict[str, Any]) -> str:
    result = row["result"]
    stable = {
        "solver_success": result["solver_success"],
        "engine": result["engine"],
        "model_id": result["model_id"],
        "reported_heat_source": result["reported_heat_source"],
        "metrics": result["metrics"],
        "finite_numeric_metrics": result["finite_numeric_metrics"],
        "raytrace_fallback_warning_seen": result["raytrace_fallback_warning_seen"],
    }
    return json.dumps(stable, sort_keys=True, separators=(",", ":"), allow_nan=False)


def run_pilot(output_dir: Path | None = None) -> dict[str, Any]:
    material_properties = thermal_props("Inconel 718")
    if not material_properties:
        raise RuntimeError("IN718 thermal properties are unavailable")
    base_absorptivity = float(material_properties["absorptivity_IR"])
    design = build_design(base_absorptivity)

    if output_dir is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_dir = OUTPUT_BASE / f"in718_solver_branch_sensitivity_v2_{timestamp}"
    output_dir = output_dir.resolve()
    output_dir.relative_to(REPO_ROOT.resolve())
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing pilot output: {output_dir}")

    source_hashes = {name: _sha256(REPO_ROOT / name) for name in SOURCE_FILES}
    original_csv_hash = _sha256(EXISTING_DATASET) if EXISTING_DATASET.exists() else None
    revision = _git_revision()
    dirty = _git_worktree_dirty()
    rows: list[dict[str, Any]] = []
    baseline_repeat_id = "repo_case_285w_960mms__eta1.0__rosenthal"

    for design_row in design:
        for repeat_index in (1, 2) if design_row["run_id"] == baseline_repeat_id else (1,):
            captured = io.StringIO()
            started = time.perf_counter()
            try:
                with contextlib.redirect_stdout(captured):
                    result = calculate_meltpool_physics(
                        material_name="Inconel 718",
                        laser_power_W=design_row["inputs"]["laser_power_W"],
                        scan_speed_mm_s=design_row["inputs"]["scan_speed_mm_s"],
                        beam_diameter_um=COMMON_INPUTS["beam_diameter_um"],
                        preheat_temp_C=COMMON_INPUTS["preheat_temp_C"],
                        layer_thickness_um=COMMON_INPUTS["layer_thickness_um"],
                        hatch_spacing_um=COMMON_INPUTS["hatch_spacing_um"],
                        laser_wavelength=COMMON_INPUTS["laser_wavelength"],
                        process_seed=COMMON_INPUTS["process_seed_metadata_only"],
                        prop_overrides={"absorptivity_IR": design_row["absorptivity_IR_override"]},
                        heat_source=design_row["heat_source"],
                    )
                summary = summarize_result(
                    result, warnings=captured.getvalue(), runtime_s=time.perf_counter() - started
                )
                row = {
                    **design_row,
                    "evaluation_id": f"{design_row['run_id']}__rep{repeat_index:02d}",
                    "repeat_index": repeat_index,
                    "status": "completed",
                    "result": summary,
                }
            except Exception as exc:  # Keep failed runs visible; never silently drop a DOE row.
                row = {
                    **design_row,
                    "evaluation_id": f"{design_row['run_id']}__rep{repeat_index:02d}",
                    "repeat_index": repeat_index,
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "warning_text": captured.getvalue(),
                    "runtime_s": round(time.perf_counter() - started, 6),
                }
            row["row_sha256"] = hashlib.sha256(
                json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
            ).hexdigest()
            rows.append(row)

    baseline_rows = [row for row in rows if row["run_id"] == baseline_repeat_id]
    deterministic_repeat = (
        len(baseline_rows) == 2
        and all(row["status"] == "completed" for row in baseline_rows)
        and _stable_result_projection(baseline_rows[0]) == _stable_result_projection(baseline_rows[1])
    )
    failure_count = sum(row["status"] != "completed" or not row["result"]["solver_success"] for row in rows)
    nonfinite_count = sum(
        not all(row["result"]["finite_numeric_metrics"].values())
        for row in rows
        if row["status"] == "completed"
    )
    required_metrics = ("melt_pool_width_um", "melt_pool_depth_um", "melt_pool_length_um")
    missing_required_metric_count = sum(
        any(row["result"]["metrics"].get(key) is None for key in required_metrics)
        for row in rows
        if row["status"] == "completed"
    )
    current_csv_hash = _sha256(EXISTING_DATASET) if EXISTING_DATASET.exists() else None

    manifest = {
        "schema_version": 2,
        "dataset_kind": "synthetic_solver_branch_sensitivity",
        "interpretation": (
            "Solver-internal sensitivity only. Rosenthal and Eagar-Tsai branches bundle different "
            "absorptivity and depth corrections; results do not isolate a pure heat-source model-form effect."
        ),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository_revision": revision,
        "repository_worktree_dirty_at_start": dirty,
        "source_files_sha256": source_hashes,
        "material_id": "in718",
        "material_name": "Inconel 718",
        "material_property_source": "python/four_alloy_materials.py",
        "base_absorptivity_IR": base_absorptivity,
        "process_case_source": PROCESS_CASE_SOURCE,
        "common_inputs": COMMON_INPUTS,
        "design_rows": len(design),
        "evaluations_including_repeat": len(rows),
        "evaluation_ids_unique": len({row["evaluation_id"] for row in rows}) == len(rows),
        "absorptivity_scales": ABSORPTIVITY_SCALES,
        "heat_source_branches": HEAT_SOURCES,
        "omitted_metrics": {
            "cooling_rate": "not included: current result thermal field was null in baseline; legacy generator reads a different key",
            "defect_and_fatigue_targets": "not included: legacy generator supplies heuristic values",
        },
        "dataset_integrity": {
            "preexisting_synthetic_process_map_sha256": original_csv_hash,
            "postrun_synthetic_process_map_sha256": current_csv_hash,
        },
        "acceptance_checks": {
            "all_solver_rows_completed": failure_count == 0,
            "all_numeric_metrics_finite": nonfinite_count == 0,
            "required_geometry_metrics_present": missing_required_metric_count == 0,
            "baseline_repeat_stable_projection_matches": deterministic_repeat,
            "evaluation_ids_unique": len({row["evaluation_id"] for row in rows}) == len(rows),
            "preexisting_dataset_unchanged": original_csv_hash == current_csv_hash,
        },
        "claim_boundary": "Synthetic solver output; not experimental validation, qualification, or an ML benchmark.",
    }

    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "observations.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in rows), encoding="utf-8"
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
    return {"output_dir": str(output_dir), "manifest": manifest}


def main() -> int:
    try:
        report = run_pilot()
    except Exception as exc:
        print(f"Pilot failed before output: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    checks = report["manifest"]["acceptance_checks"]
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
