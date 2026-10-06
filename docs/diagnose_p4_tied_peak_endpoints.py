"""Opt-in, diagnostic-only P4 tied-peak contour spread runner.

This runs the preregistered 75 W mesh axis without changing or replacing its
frozen acceptance report. Captured tied peak fields are postprocessed with an
independent offline edge-crossing implementation.
"""

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

import lpbf_peak
import lpbf_simulation


def offline_contour_oracle(coordinates, temperature, surface, angle_deg, dx, liquidus_K):
    """Independently walk all active cell-center edges for liquidus crossings."""
    xyz = np.asarray(coordinates, dtype=float)
    temp = np.asarray(temperature, dtype=float).ravel()
    axes = [np.unique(xyz[:, index]) for index in range(3)]
    shape = tuple(len(axis) for axis in axes)
    if (xyz.shape != (len(temp), 3) or np.prod(shape) != len(temp)
            or any(len(axis) < 2 for axis in axes)
            or any(not np.allclose(np.diff(axis), dx, rtol=1e-8, atol=1e-12)
                   for axis in axes)):
        return {"status": "unsupported", "reason": "Field is not a complete uniform Cartesian grid"}
    field = temp.reshape(shape)
    coordinate_grids = np.meshgrid(*axes, indexing="ij")
    active = np.broadcast_to(axes[2][None, None, :] < surface, shape)
    molten = (field >= liquidus_K) & active
    if (molten[0].any() or molten[-1].any() or molten[:, 0].any()
            or molten[:, -1].any() or molten[:, :, 0].any()):
        return {"status": "unsupported", "reason": "Liquidus contour touches a lateral or bottom boundary"}

    theta = math.radians(angle_deg)
    projections, heights = [], []
    for dimension in range(3):
        low_slice = [slice(None)]*3
        high_slice = [slice(None)]*3
        low_slice[dimension] = slice(None, -1)
        high_slice[dimension] = slice(1, None)
        low_slice, high_slice = tuple(low_slice), tuple(high_slice)
        low_values, high_values = field[low_slice], field[high_slice]
        crosses = ((low_values >= liquidus_K) != (high_values >= liquidus_K))
        crosses &= active[low_slice] & active[high_slice]
        if not crosses.any():
            continue
        fraction = ((liquidus_K-low_values[crosses]) /
                    (high_values[crosses]-low_values[crosses]))
        low_coordinates = [grid[low_slice] for grid in coordinate_grids]
        high_coordinates = [grid[high_slice] for grid in coordinate_grids]
        x0, y0, z0 = (grid[crosses] for grid in low_coordinates)
        x1, y1, z1 = (grid[crosses] for grid in high_coordinates)
        x = x0 + fraction*(x1-x0)
        y = y0 + fraction*(y1-y0)
        z = z0 + fraction*(z1-z0)
        projections.append(-math.sin(theta)*x+math.cos(theta)*y)
        heights.append(z)
    if not projections:
        return {"status": "unsupported", "reason": "No resolved liquidus edge crossings"}
    lateral = np.concatenate(projections)
    vertical = np.concatenate(heights)
    width = float((lateral.max()-lateral.min())*1e6)
    depth = float((surface-vertical.min())*1e6)
    if not (math.isfinite(width) and math.isfinite(depth) and width > 0 and depth > 0):
        return {"status": "unsupported", "reason": "Crossings do not define positive width and depth"}
    return {"status": "thermal-proxy", "width_um": width, "depth_um": depth}


def _stats(values):
    return ({"min": float(min(values)), "median": float(np.median(values)), "max": float(max(values))}
            if values else None)


def diagnose(scenario, mesh_levels_um):
    if scenario.get("mode") != "standard" or scenario.get("backend") != "reference":
        raise ValueError("Only the preregistered explicit CPU reference scenario is supported")
    runs = []
    original_tracker = lpbf_simulation.PeakMeltTracker

    class CapturingPeakMeltTracker(original_tracker):
        instances = []

        def __init__(self, coordinates, dx, material):
            super().__init__(coordinates, dx, material, track_tied_contours=True,
                             capture_tied_fields=True)
            self.instances.append(self)

    lpbf_simulation.PeakMeltTracker = CapturingPeakMeltTracker
    try:
        for requested_mesh in mesh_levels_um:
            payload = dict(scenario, mesh_um=requested_mesh)
            started = time.perf_counter()
            CapturingPeakMeltTracker.instances = []
            result = lpbf_simulation.run(payload)
            if len(CapturingPeakMeltTracker.instances) != 1:
                raise RuntimeError("Expected exactly one opt-in peak tracker for one solver run")
            tracker = CapturingPeakMeltTracker.instances[0]
            production = result["numericalDiagnostics"]["tiedPeakContourSpread"]
            oracle = []
            for temperature, surface, angle, endpoint_time, endpoint_step in tracker._tied_fields:
                row = offline_contour_oracle(tracker.xyz, temperature, surface, angle,
                                             tracker.dx, tracker.m["liquidus_K"])
                row.update(time_s=endpoint_time, step=endpoint_step)
                oracle.append(row)
            valid = [row for row in oracle if row["status"] == "thermal-proxy"]
            width = [row["width_um"] for row in valid]
            depth = [row["depth_um"] for row in valid]
            comparisons = {}
            for key, values in (("width_um", width), ("depth_um", depth)):
                observed = production.get(key)
                independent = _stats(values)
                comparisons[key] = dict(
                    productionTracker=observed,
                    independentOfflineOracle=independent,
                    agrees=bool(observed == independent if observed is None or independent is None
                                else all(math.isclose(observed[name], independent[name],
                                                      rel_tol=1e-10, abs_tol=1e-10)
                                         for name in ("min", "median", "max"))))
            runs.append(dict(
                requestedMesh_um=requested_mesh,
                actualMesh_m=result["discretization"]["mesh_m"],
                cells=result["discretization"]["cells"],
                steps=result["discretization"]["steps"],
                elapsed_s=time.perf_counter()-started,
                solver=result["solver"], model=result["coreContract"],
                materialRevisionSha256=result["material"].get("materialRevisionSha256"),
                peakMeltCellCount=result["numericalDiagnostics"]["peakMeltCellCount"],
                peakSelection=dict(
                    first=production["first"], last=production["last"],
                    endpointCount=production["endpointCount"],
                    observedContourCount=production["observedContourCount"],
                    validContourCount=production["validContourCount"],
                    invalidContourCount=production["invalidContourCount"]),
                productionContourSpread={"width_um":production["width_um"],
                                         "depth_um":production["depth_um"]},
                independentOfflineOracle=dict(
                    width_um=_stats(width), depth_um=_stats(depth),
                    first=valid[0] if valid else None, last=valid[-1] if valid else None),
                oracleAgreement=comparisons,
                discreteFirstEndpoint=dict(
                    width_um=result["metrics"]["width_um"],
                    depth_um=result["metrics"]["depth_um"],
                    peakTime_s=result["numericalDiagnostics"]["peakMeltTime_s"],
                    peakStep=result["numericalDiagnostics"]["peakMeltStep"])))
    finally:
        lpbf_simulation.PeakMeltTracker = original_tracker

    return dict(
        schemaVersion=1,
        diagnosticId="p4-tied-peak-endpoint-contour-spread-v1",
        scope="Diagnostic only; not numerical convergence acceptance or experimental validation",
        acceptanceStatus="not-assessed",
        frozenReportsUnaffected=True,
        scenario=scenario,
        requestedMeshLevels_um=list(mesh_levels_um),
        temporalAxis="not-run",
        observationOperator="peak-liquidus-cell-edge-linear-contour-v1",
        temporalSelection="accepted-step-molten-volume-v1; first maximum state remains the reported state",
        oracle="Separate offline structured-edge traversal over captured tied maximum fields",
        runs=runs,
        limitations=[
            "A tie is an equal maximum count of liquidus cells, not proof that the physical pool is stationary.",
            "Contour width/depth are cell-center linear thermal proxies with no surface extrapolation.",
            "The conduction-only reference model does not resolve melt flow, evaporation, recoil or keyhole physics.",
            "This diagnostic characterizes endpoint sensitivity and does not change the frozen P4 outcome."])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path,
                        default=ROOT/"docs/LPBF_P4_CONTOUR_SCENARIO_75W_2026-09-24.json")
    parser.add_argument("--output", type=Path,
                        default=ROOT/"docs/LPBF_P4_TIED_ENDPOINT_DIAGNOSTIC_75W_2026-09-24.json")
    parser.add_argument("--mesh-levels-um", nargs="+", type=float, default=[20., 10., 5.])
    args = parser.parse_args()
    scenario_bytes = args.scenario.read_bytes()
    report = diagnose(json.loads(scenario_bytes), args.mesh_levels_um)
    report["scenarioSha256"] = hashlib.sha256(scenario_bytes).hexdigest()
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(f"Diagnostic report written: {args.output}")
    for run in report["runs"]:
        print(json.dumps({key: run[key] for key in (
            "requestedMesh_um", "peakSelection", "productionContourSpread",
            "independentOfflineOracle", "oracleAgreement")}, allow_nan=False))


if __name__ == "__main__":
    main()
