#!/usr/bin/env python3
"""Opt-in calibrated melt-pool mode (screening only, not validation): JSON CLI behind
POST /api/python/lpbf-calibrated-meltpool.

Input keys mirror ``lpbf_thermal_solver.py`` (material, laserPower_W, scanSpeed_mm_s, beamDiameter_um, preheatTemp_C,
layerThickness_um, hatchSpacing_um, laserWavelength, heatSource, sulfur_ppm, absorptionModel, thermalSliceBackend) plus
``"calibrationMode": true``. The output is the contract of ``lpbf_calibration_layer.apply_calibration``: the unchanged
screening result, and a calibrated block that exists only for cells whose gate status is ``enabled``. A missing or
stale artefact never fails the request: the screening result is returned with ``calibrated.available = false`` and
the reason.

``--status`` prints the artefact state and the enabled cells without running a solver.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict

import lpbf_calibration_layer as layer


def _read_input() -> Dict[str, Any]:
    if len(sys.argv) > 1 and sys.argv[1].strip().startswith("{"):
        return json.loads(sys.argv[1])
    if not sys.stdin.isatty():
        raw = sys.stdin.read()
        if raw.strip():
            return json.loads(raw)
    return {}


def status() -> Dict[str, Any]:
    try:
        calib = layer.load_calibration()
    except layer.CalibrationStale as exc:
        return {"status": "stale", "calibrationAvailable": False, "reason": str(exc), "enabledCells": []}
    except layer.CalibrationError as exc:
        return {"status": "unavailable", "calibrationAvailable": False, "reason": str(exc), "enabledCells": []}
    return {"status": "ready", "calibrationAvailable": True, "calibrationId": calib["calibrationId"],
            "enabledCells": layer.enabled_cells(calib), "evidenceKind": layer.EVIDENCE_KIND,
            "label": layer.LABEL}


def run(data: Dict[str, Any]) -> Dict[str, Any]:
    kernel = data.get("heatSource") or data.get("heat_source") or "rosenthal"
    reason = None
    calib = None
    if data.get("calibrationMode") is not True:
        reason = "calibrationMode was not requested"
    else:
        try:
            calib = layer.load_calibration()
        except layer.CalibrationStale:
            reason = "calibration stale for this physics version"
        except layer.CalibrationError as exc:
            reason = f"calibration artefact unavailable: {exc}"
    if calib is not None:
        return layer.apply_calibration(data, kernel, calib)
    spec = layer.solver_kwargs(data)
    screening = layer._default_solver()(*spec["args"], heat_source=kernel, **spec["kwargs"])
    return {"screening": screening, "evidenceKind": layer.EVIDENCE_KIND,
            "calibrated": {"available": False, "reason": reason, "width_um": None, "depth_um": None},
            "calibration": None, "outsideTrainingEnvelope": False, "envelopeNotes": []}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        print(json.dumps(status()))
        sys.exit(0)
    try:
        print(json.dumps(run(_read_input()), indent=2))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)
