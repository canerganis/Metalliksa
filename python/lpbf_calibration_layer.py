"""Runtime layer of the opt-in LPBF "calibrated mode": loads the versioned, hashed calibration artefact and, only for
cells whose gate status is ``enabled``, re-runs the frozen screening solver with a fitted effective absorptivity.

SCREENING ONLY, NOT VALIDATION. Nothing here edits or is imported by the frozen physics (the manifest files of
``lpbf_simulation.IMPLEMENTATION_SOURCE_FILES``); the solver is reached through its public argument
``prop_overrides={"absorptivity_IR": eta}`` (flat-plate path, the path the fit used). The default screening result
is always returned unchanged next to the calibrated block. The evidence kind stays ``screening-only``; no code path
derives a label from scores.

Honesty rules enforced here:
- an artefact whose implementation hash, content hash or config hash does not match is refused (stale/tampered);
- a quantity is served only from an ``enabled`` cell; the other quantity is ``null`` with a reason;
- no depth/width ratio, L/W or regime is derived from a mix of calibrated and screening values;
- the regime label is the screening label at the default absorptivity (unchanged); "regime at eta_D" is a
  sensitivity only;
- inputs outside the training envelope are flagged.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import lpbf_calibration_stats as st
from lpbf_calibration_config import (CALIBRATION_CONFIG, CALIBRATION_SCHEMA, canonical_json, config_sha256)

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "calibration" / "lpbf-meltpool-calibration-v1.json"
EVIDENCE_KIND = "screening-only"
LABEL = "Screening only: calibrated mode (nuisance absorptivity fitted to published tracks; not validation)"

ARTEFACT_KEYS = frozenset({
    "schema", "calibrationId", "generatedAt", "implementationHash", "codeRevision", "tool", "configSha256", "config",
    "trainingData", "catalogSentinelSources", "heldOutSources", "priors", "cells", "scorecardRecord", "scorecardSha256",
    "evidenceKind", "proposedEvidenceKind", "evidenceLabel", "labelPromotionProposed", "honesty", "contentSha256",
    "envelope"})
STATUSES = ("enabled", "within-source-only", "rejected", "no-data")


class CalibrationError(Exception):
    """The artefact is malformed, tampered with or inconsistent with the compiled-in configuration."""


class CalibrationStale(CalibrationError):
    """The artefact was fitted against a different frozen-physics fingerprint."""


def artefact_content_sha256(art: Dict[str, Any]) -> str:
    probe = dict(art)
    probe["contentSha256"] = ""
    probe["calibrationId"] = ""
    return st.canonical_sha256(probe)


def load_calibration(path: Any = DEFAULT_PATH, *, expected_impl_hash: Optional[str] = None) -> Dict[str, Any]:
    """Load and verify the artefact. ``expected_impl_hash`` defaults to the live implementation fingerprint."""
    p = Path(path)
    try:
        art = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CalibrationError(f"calibration artefact missing: {p}") from exc
    except json.JSONDecodeError as exc:
        raise CalibrationError(f"calibration artefact is not valid JSON: {exc}") from exc
    if not isinstance(art, dict) or art.get("schema") != CALIBRATION_SCHEMA:
        raise CalibrationError(f"unexpected schema {art.get('schema') if isinstance(art, dict) else type(art).__name__}")
    unknown = sorted(set(art) - ARTEFACT_KEYS)
    if unknown:
        raise CalibrationError(f"unknown artefact keys rejected: {unknown}")
    if art.get("contentSha256") != artefact_content_sha256(art):
        raise CalibrationError("contentSha256 does not match the artefact content (tampered or hand-edited)")
    if st.canonical_sha256(art.get("config")) != art.get("configSha256"):
        raise CalibrationError("configSha256 does not match the config stored in the artefact")
    if art.get("configSha256") != config_sha256(CALIBRATION_CONFIG):
        raise CalibrationError("CALIBRATION_CONFIG sha256 differs from the artefact's: a config change needs a new "
                               "calibration version")
    if art.get("evidenceKind") != EVIDENCE_KIND or art.get("proposedEvidenceKind") is not None:
        raise CalibrationError("artefact evidence fields must be screening-only with no proposed promotion")
    for c in art.get("cells", []):
        if c.get("status") not in STATUSES:
            raise CalibrationError(f"unknown cell status {c.get('status')!r}")
    live = expected_impl_hash
    if live is None:
        from lpbf_simulation import implementation_fingerprint
        live = implementation_fingerprint()
    if art.get("implementationHash") != live:
        raise CalibrationStale("calibration stale for this physics version "
                               f"(artefact {str(art.get('implementationHash'))[:12]}, live {str(live)[:12]})")
    return art


def cell_for(calib: Dict[str, Any], kernel: str, material: str, quantity: str) -> Optional[Dict[str, Any]]:
    """The cell, only when its status is ``enabled``; every other status is not served."""
    for c in calib.get("cells", []):
        if c["kernel"] == kernel and c["material"] == material and c["quantity"] == quantity:
            return c if c["status"] == "enabled" else None
    return None


def status_of(calib: Dict[str, Any], kernel: str, material: str, quantity: str) -> Optional[str]:
    for c in calib.get("cells", []):
        if c["kernel"] == kernel and c["material"] == material and c["quantity"] == quantity:
            return c["status"]
    return None


def enabled_cells(calib: Dict[str, Any]) -> List[Dict[str, str]]:
    return [{"kernel": c["kernel"], "material": c["material"], "quantity": c["quantity"], "rung": c.get("rung")}
            for c in calib.get("cells", []) if c["status"] == "enabled"]


def solver_kwargs(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """The arguments lpbf_thermal_solver.__main__ passes to calculate_meltpool_physics (same defaults)."""
    return {
        "args": (inputs.get("material", "Inconel 718"), float(inputs.get("laserPower_W", 285.0)),
                 float(inputs.get("scanSpeed_mm_s", 960.0)), float(inputs.get("beamDiameter_um", 80.0)),
                 float(inputs.get("preheatTemp_C", 80.0)), float(inputs.get("layerThickness_um", 40.0)),
                 float(inputs.get("hatchSpacing_um", 110.0)), inputs.get("laserWavelength", "IR_1064nm")),
        "kwargs": {"sulfur_ppm": float(inputs.get("sulfur_ppm", inputs.get("sulfurPpm", 15.0))),
                   "absorption_model": inputs.get("absorptionModel"),
                   "thermal_slice_backend": inputs.get("thermalSliceBackend")},
    }


def _default_solver() -> Callable[..., Dict[str, Any]]:
    from lpbf_thermal_solver import calculate_meltpool_physics
    return calculate_meltpool_physics


def _envelope_check(calib: Dict[str, Any], material: str, inputs: Dict[str, Any], enthalpy_default: Optional[float]):
    env = (calib.get("envelope") or {}).get(material)
    notes: List[str] = []
    if env is None:
        return True, [f"no training envelope recorded for {material}"]
    for key, label in (("laserPower_W", "power"), ("scanSpeed_mm_s", "speed"), ("beamDiameter_um", "beam diameter")):
        lo, hi = env[key]
        v = float(inputs.get(key, math.nan))
        if not (lo <= v <= hi):
            notes.append(f"{label} {v:g} outside the training range [{lo:g}, {hi:g}]")
    if enthalpy_default is not None:
        lo, hi = env["normalizedEnthalpyDefault"]
        if not (lo <= enthalpy_default <= hi):
            notes.append(f"normalised enthalpy at the default absorptivity {enthalpy_default:.1f} outside the training "
                         f"range [{lo:.1f}, {hi:.1f}]")
    return bool(notes), notes


def _held_out_text(cell: Dict[str, Any]) -> str:
    parts = []
    for r in cell.get("heldOutScore") or []:
        cov = r.get("coverage90") or {}
        ci = r.get("skillCi95") or [None, None]
        w = cov.get("wilson95") or [None, None]
        parts.append(f"{r['heldOut']}: MAPE {r['mapeDefault']:.1f} -> {r['mapeServed']:.1f} % (n={r['nRows']} rows, "
                     f"{r['nSets']} sets), skill CI95 [{ci[0]:.2f}, {ci[1]:.2f}], 90 % PI coverage {cov.get('coverage')} "
                     f"(Wilson [{w[0]}, {w[1]}])")
    return "; ".join(parts) + ("; rung selected in training only" if parts else "")


def apply_calibration(inputs: Dict[str, Any], kernel: str, calib: Dict[str, Any], *,
                      solver: Optional[Callable[..., Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Screening result unchanged + a calibrated block for the ``enabled`` cells (see module docstring)."""
    solver = solver or _default_solver()
    spec = solver_kwargs(inputs)
    material = spec["args"][0]
    screening = solver(*spec["args"], heat_source=kernel, **spec["kwargs"])
    out: Dict[str, Any] = {"screening": screening, "evidenceKind": EVIDENCE_KIND}
    cw = cell_for(calib, kernel, material, "width")
    cd = cell_for(calib, kernel, material, "depth")
    cells_status = {q: {"status": status_of(calib, kernel, material, q) or "no-data"} for q in ("width", "depth")}
    for q, cell in (("width", cw), ("depth", cd)):
        if cell:
            cells_status[q].update({"rung": cell["rung"], "params": cell["params"]})
    prop = screening.get("processParameters", {}) if isinstance(screening, dict) else {}
    h_default = prop.get("normalizedEnthalpy")
    calibrated: Dict[str, Any] = {"available": bool(cw or cd), "cells": cells_status, "width_um": None, "depth_um": None,
                                  "absorptionPath": "flat-plate (the path the calibration was fitted on)",
                                  "regimeLabel": (st.regime_class_from_enthalpy(h_default) if h_default is not None
                                                  else None),
                                  "regimeLabelNote": "screening label at the default absorptivity, unchanged",
                                  "regimeAtEtaD_sensitivity": None,
                                  "depthOverWidth": None, "depthOverWidthReason": None}
    if not (cw or cd):
        calibrated["reason"] = "no enabled calibration cell for this kernel and alloy"
    out_of_env = False
    env_notes: List[str] = []
    if cw or cd:
        out_of_env, env_notes = _envelope_check(calib, material, inputs, h_default)
        ev = {}
        for q, cell in (("width", cw), ("depth", cd)):
            if not cell:
                calibrated[f"{q}Reason"] = f"cell status {cells_status[q]['status']}: not served"
                continue
            p = cell["params"]
            rung = cell["rung"]
            eta = p["etaJoint"] if rung == "eta" else (p["etaW"] if q == "width" else p["etaD"])
            res = solver(*spec["args"], heat_source=kernel, sulfur_ppm=spec["kwargs"]["sulfur_ppm"],
                         absorption_model="flat-plate", thermal_slice_backend=spec["kwargs"]["thermal_slice_backend"],
                         prop_overrides={"absorptivity_IR": eta})
            g = res["meltPoolGeometry"]
            val = float(g["width_um"] if q == "width" else g["depth_um"])
            if rung == "eta2+dOffset" and q == "depth":
                val *= math.exp(p["cD"].get(st.regime_class_from_enthalpy(h_default) if h_default is not None else "conduction", 0.0))
            calibrated[f"{q}_um"] = val
            iv = cell["interval"]
            if iv and iv.get("sSource") is not None:
                for lvl in iv["levels"]:
                    lo, hi = st.conformal_interval(iv["m"], iv["sWithin"], iv["sSource"], lvl,
                                                   {float(k): v for k, v in CALIBRATION_CONFIG["interval"]["z"].items()})
                    calibrated[f"{q}_pi{int(round(lvl * 100))}_um"] = [val * lo, val * hi]
                    if int(round(lvl * 100)) == 90:
                        calibrated[f"{q}_pi90_notInformative"] = (hi / lo) > CALIBRATION_CONFIG["interval"]["notInformativeRatio"]
            ev[q] = eta
        if cw and cd:
            calibrated["depthOverWidth"] = calibrated["depth_um"] / calibrated["width_um"]
        else:
            calibrated["depthOverWidthReason"] = ("only one quantity is served: no depth/width, length/width, regime or "
                                                  "aspect ratio is derived from a mix of calibrated and screening values")
        if cd and h_default is not None and "depth" in ev:
            calibrated["regimeAtEtaD_sensitivity"] = st.regime_class_from_enthalpy(
                h_default * ev["depth"] / float(calib["config"]["materialDefaults"][material]))
    out["calibrated"] = calibrated
    out["calibration"] = {
        "calibrationId": calib["calibrationId"], "contentSha256": calib["contentSha256"],
        "fittedOn": [f"{t['source']} ({t['rowsUsed']} rows)" for t in calib["trainingData"] if t["material"] == material],
        "heldOutScore": {q: _held_out_text(c) for q, c in (("width", cw), ("depth", cd)) if c},
        "scorecardRecord": calib["scorecardRecord"], "evidenceKind": EVIDENCE_KIND, "label": LABEL,
        "labelPromotionProposed": calib.get("labelPromotionProposed")}
    out["outsideTrainingEnvelope"] = bool(out_of_env)
    out["envelopeNotes"] = env_notes
    return out
