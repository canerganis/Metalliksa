"""Next-experiment proposal for the LPBF melt-pool screening stack (the "calibration kit").

Screening: experiment proposal; not a print recommendation. The module ranks candidate single-track settings by how
much a measurement there would teach the calibration, and lays the chosen tracks out on a plate. It runs the three
frozen screening kernels (read-only, exactly like ``lpbf_calibration_fit._solver_call``: flat-plate, default
absorptivity) and reads the committed calibration artefact and the training tables. It changes nothing in the frozen
physics and derives no evidence label.

Information score of one candidate (P, v, spot) -- three documented terms, each in [0, 1] before weighting:

1. kernel disagreement: the sample SD (ddof 1) of ln W and of ln D across the frozen kernels (at least two must
   resolve with status ``computed``; a candidate with fewer is excluded and counted, never scored), averaged over the
   two quantities and divided by the largest value among the candidates;
2. calibration interval width: ln(hi / lo) of the 90 % conformal interval of the matching ENABLED scorecard cells
   (``lpbf_calibration_layer.cell_for``), averaged over the enabled kernel x quantity cells of the material and
   divided by ln(notInformativeRatio) (capped at 1). It is ``null`` when no enabled cell with an interval exists, and
   the plan says so. It is a property of the material, so it is the same for every candidate of one plan: it
   documents how uncertain the calibrated mode is and does not change the ranking inside a plan;
3. coverage: 0.5 if the candidate's input-only regime class has fewer than ``minSetsPerClass`` training parameter
   sets (the training sets plus the existing points the user lists), plus 0.5 x min(1, d / distanceCap) where d is
   the distance to the nearest training or existing point in standardised ln P, ln v, ln spot.

Greedy batch selection: base score = weighted sum of the terms; after each pick every remaining candidate is
multiplied by prod_j (1 - exp(-d_ij^2 / (2 L^2))) over the already chosen points (and the user's existing points),
with d_ij in unit-range ln coordinates of the candidate grid and the one documented length scale ``L`` below. Ties go
to the lowest candidate index (sorted by P, v, spot). The seed only drives the plate-order shuffle; selection is a
pure function of the inputs, the calibration artefact and the training tables.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import random
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

import lpbf_calibration_stats as st
from lpbf_calibration_config import CALIBRATION_CONFIG, KERNELS, canonical_json

PLAN_SCHEMA = "lpbf-next-experiment-plan-1"
LABEL = "Screening: experiment proposal; not a print recommendation"
EVIDENCE_KIND = "screening-only"
REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON_DIR = Path(__file__).resolve().parent
DEFAULT_HATCH_UM = 100.0  # the value lpbf_calibration_fit.input_args uses for a bare single track

# Every number that shapes the ranking or the layout lives here and is hashed into plan.json.
NEXT_EXPERIMENT_CONFIG: Dict[str, Any] = {
    "version": "lpbf-next-experiment-config-1",
    "gridMaxPerAxis": 15,
    "gridDefaultPerAxis": 9,
    "maxSpots": 8,
    "nRange": [1, 48],
    "weights": {"disagreement": 1.0, "interval": 0.5, "coverage": 1.0},
    "coverage": {"classGapValue": 0.5, "distanceValue": 0.5, "distanceCapStd": 3.0, "minStd": 0.05},
    "neighbourLengthScale": 0.25,
    "neighbourLengthScaleUnit": "unit-range ln(P), ln(v), ln(spot) coordinates of the candidate grid",
    "intervalLevel": 0.9,
    "intervalNormaliser": "ln(CALIBRATION_CONFIG.interval.notInformativeRatio)",
    "plate": {"trackLength_mm": 10.0, "minSpacing_mm": 3.0, "spacingSpotMultiple": 10.0,
              "edgeMargin": "one pitch", "order": "seeded shuffle of the track ranks over the plate slots"},
    "resolvedStatus": "computed",
    "kernels": list(KERNELS),
}


class PlanError(ValueError):
    """The request cannot be turned into a plan (bad inputs, no resolvable candidates, plate too small)."""


def next_experiment_config_sha256() -> str:
    return hashlib.sha256(canonical_json(NEXT_EXPERIMENT_CONFIG).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------------------------
def _bounds() -> Dict[str, Tuple[float, float]]:
    from lpbf_simulation import BOUNDS  # read-only
    return dict(BOUNDS)


def _finite(x: Any, name: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(float(x)):
        raise PlanError(f"{name} must be a finite number, got {x!r}")
    return float(x)


def _in_bounds(x: float, key: str, name: str, bounds: Dict[str, Tuple[float, float]]) -> float:
    lo, hi = bounds[key]
    if not (lo <= x <= hi):
        raise PlanError(f"{name} {x:g} is outside the solver bounds [{lo:g}, {hi:g}]")
    return x


def validate_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Return the normalised request; raise PlanError for every missing or out-of-range input."""
    cfg = NEXT_EXPERIMENT_CONFIG
    b = _bounds()
    material = spec.get("material")
    if not isinstance(material, str) or not material.strip():
        raise PlanError("material is required")
    n = spec.get("n")
    if isinstance(n, bool) or not isinstance(n, int) or not (cfg["nRange"][0] <= n <= cfg["nRange"][1]):
        raise PlanError(f"n must be an integer in [{cfg['nRange'][0]}, {cfg['nRange'][1]}], got {n!r}")
    seed = spec.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise PlanError("seed must be an integer")
    plate = spec.get("plate")
    if not isinstance(plate, dict) or "x_mm" not in plate or "y_mm" not in plate:
        raise PlanError("the plate size is required (plate.x_mm and plate.y_mm); there is no default plate")
    px, py = _finite(plate["x_mm"], "plate.x_mm"), _finite(plate["y_mm"], "plate.y_mm")
    if px <= 0 or py <= 0:
        raise PlanError("plate size must be positive")
    out: Dict[str, Any] = {"material": material.strip(), "n": n, "seed": seed, "plate": {"x_mm": px, "y_mm": py}}
    for key, label, bkey in (("power_W", "power", "power_W"), ("speed_mm_s", "speed", "speed_mm_s")):
        rng = spec.get(key)
        if not isinstance(rng, (list, tuple)) or len(rng) != 2:
            raise PlanError(f"{key} must be a [min, max] range")
        lo, hi = _finite(rng[0], f"{key} min"), _finite(rng[1], f"{key} max")
        if lo > hi:
            raise PlanError(f"{key} min exceeds max")
        out[key] = [_in_bounds(lo, bkey, f"{label} min", b), _in_bounds(hi, bkey, f"{label} max", b)]
    spots = spec.get("spots_um")
    if not isinstance(spots, (list, tuple)) or not spots:
        raise PlanError("spots_um must be a non-empty list of spot diameters")
    sp = sorted({_in_bounds(_finite(s, "spot diameter"), "beamDiameter_um", "spot diameter", b) for s in spots})
    if len(sp) > cfg["maxSpots"]:
        raise PlanError(f"at most {cfg['maxSpots']} distinct spot diameters")
    out["spots_um"] = sp
    out["layer_um"] = _in_bounds(_finite(spec.get("layer_um"), "layer_um"), "layer_um", "layer", b)
    out["preheat_C"] = _in_bounds(_finite(spec.get("preheat_C"), "preheat_C"), "preheat_C", "preheat", b)
    grid = spec.get("grid", cfg["gridDefaultPerAxis"])
    if isinstance(grid, bool) or not isinstance(grid, int) or not (1 <= grid <= cfg["gridMaxPerAxis"]):
        raise PlanError(f"grid must be an integer in [1, {cfg['gridMaxPerAxis']}]")
    out["grid"] = grid
    ex_out = []
    for i, e in enumerate(spec.get("existing") or []):
        if not isinstance(e, dict):
            raise PlanError(f"existing point {i} must be an object")
        ex_out.append({"power_W": _in_bounds(_finite(e.get("power_W"), "existing power"), "power_W", "existing power", b),
                       "speed_mm_s": _in_bounds(_finite(e.get("speed_mm_s"), "existing speed"), "speed_mm_s",
                                                "existing speed", b),
                       "beamDiameter_um": _in_bounds(_finite(e.get("beamDiameter_um"), "existing spot"),
                                                     "beamDiameter_um", "existing spot", b)})
    out["existing"] = ex_out
    return out


def _axis(lo: float, hi: float, g: int) -> List[float]:
    if lo == hi or g == 1:
        return [lo] if lo == hi else [round(math.exp(0.5 * (math.log(lo) + math.log(hi))), 1)]
    vals = {lo, hi}
    for i in range(1, g - 1):
        vals.add(min(hi, max(lo, round(math.exp(math.log(lo) + (math.log(hi) - math.log(lo)) * i / (g - 1)), 1))))
    return sorted(vals)


def candidate_grid(req: Dict[str, Any]) -> List[Dict[str, float]]:
    """At most grid x grid x spots candidates, log-spaced in power and speed, sorted by (P, v, spot)."""
    ps = _axis(req["power_W"][0], req["power_W"][1], req["grid"])
    vs = _axis(req["speed_mm_s"][0], req["speed_mm_s"][1], req["grid"])
    out = [{"power_W": p, "speed_mm_s": v, "beamDiameter_um": s} for p in ps for v in vs for s in req["spots_um"]]
    if len(out) < req["n"]:
        raise PlanError(f"only {len(out)} distinct candidates for n={req['n']}; widen the ranges, add spots or raise grid")
    return out


# ---------------------------------------------------------------------------------------------
# information terms
# ---------------------------------------------------------------------------------------------
def _tools_on_path() -> None:
    """python/tools holds a CLI with the same module name as this file: append (never prepend) so it cannot shadow it."""
    t = str(PYTHON_DIR / "tools")
    if t not in sys.path:
        sys.path.append(t)


def default_solver_call() -> Callable[[Tuple, str, Optional[float]], Tuple]:
    _tools_on_path()
    import lpbf_calibration_fit as fit
    return fit._solver_call


def kernel_disagreement(args: Tuple, solver_call: Callable) -> Dict[str, Any]:
    resolved = {}
    for k in KERNELS:
        W, D, status = solver_call(args, k, None)
        ok = (status == NEXT_EXPERIMENT_CONFIG["resolvedStatus"] and W is not None and D is not None
              and math.isfinite(W) and math.isfinite(D) and W > 0 and D > 0)
        if ok:
            resolved[k] = (math.log(W), math.log(D))
    rec: Dict[str, Any] = {"nResolved": len(resolved), "resolvedKernels": sorted(resolved), "sdLnW": None,
                           "sdLnD": None, "value": None}
    if len(resolved) >= 2:
        sw = float(np.std([v[0] for v in resolved.values()], ddof=1))
        sd = float(np.std([v[1] for v in resolved.values()], ddof=1))
        rec.update(sdLnW=sw, sdLnD=sd, value=0.5 * (sw + sd))
    return rec


def interval_width(calib: Optional[Dict[str, Any]], material: str, calib_note: Optional[str] = None) -> Dict[str, Any]:
    """ln(hi/lo) of the 90 % interval of the enabled cells of this material, or null with the reason."""
    if calib is None:
        return {"value": None, "cells": [], "note": calib_note or "no calibration artefact: interval width is null"}
    import lpbf_calibration_layer as layer
    z = {float(k): v for k, v in CALIBRATION_CONFIG["interval"]["z"].items()}
    level = NEXT_EXPERIMENT_CONFIG["intervalLevel"]
    widths, cells = [], []
    for k in KERNELS:
        for q in ("width", "depth"):
            c = layer.cell_for(calib, k, material, q)
            iv = (c or {}).get("interval")
            if not c or not iv or iv.get("sSource") is None:
                continue
            lo, hi = st.conformal_interval(iv["m"], iv["sWithin"], iv["sSource"], level, z)
            widths.append(math.log(hi / lo))
            cells.append({"kernel": k, "quantity": q, "lnHiOverLo": math.log(hi / lo)})
    if not widths:
        return {"value": None, "cells": [],
                "note": f"no enabled calibration cell with a 90 % interval for {material}: interval width is null "
                        "and contributes nothing to the score"}
    return {"value": float(np.mean(widths)), "cells": cells,
            "note": "mean over the enabled kernel x quantity cells; the same for every candidate of this material"}


def default_training_loader(material: str) -> List[Dict[str, Any]]:
    _tools_on_path()
    import lpbf_calibration_fit as fit
    return [r for r in fit.load_rows()["trainable"] if same_material(r["material"], material)]


def same_material(a: str, b: str) -> bool:
    """True when two names denote one material: identical, or the same alloy id in four_alloy_materials (so the
    alias '316L' matches the canonical training name '316L Stainless Steel')."""
    if a == b:
        return True
    from four_alloy_materials import resolve_alloy_id
    ia = resolve_alloy_id(a)
    return ia is not None and ia == resolve_alloy_id(b)


def regime_class(material: str, P: float, v: float, spot: float, preheat: float) -> str:
    import lpbf_public_datasets as pd
    return st.regime_class_from_enthalpy(pd.normalized_enthalpy(material, P, v, spot, preheat))


def _ln_point(p: Dict[str, float]) -> Tuple[float, float, float]:
    return (math.log(p["power_W"]), math.log(p["speed_mm_s"]), math.log(p["beamDiameter_um"]))


# ---------------------------------------------------------------------------------------------
# the plan
# ---------------------------------------------------------------------------------------------
def plan_experiment(spec: Dict[str, Any], *, calibration: Any = "default", solver_call: Optional[Callable] = None,
                    training_loader: Optional[Callable[[str], List[Dict[str, Any]]]] = None,
                    regime_fn: Optional[Callable[..., str]] = None) -> Dict[str, Any]:
    """The full plan document (JSON-serialisable, deterministic for one request). See the module docstring."""
    cfg = NEXT_EXPERIMENT_CONFIG
    req = validate_spec(spec)
    material = req["material"]
    solver_call = solver_call or default_solver_call()
    regime_fn = regime_fn or regime_class
    cands = candidate_grid(req)

    # training points of this material (plus the user's existing points)
    train_rows = (training_loader or default_training_loader)(material)
    # canonical name: the one the training rows and calibration cells use (an alias must not zero the coverage term)
    if train_rows:
        material = train_rows[0]["material"]
        req["material"] = material
    training_note = (None if train_rows else
                     f"no training rows for {material}: the coverage term has no training data to measure against "
                     "(every candidate counts as under-covered with no nearest-point distance)")
    # calibration artefact (optional: its absence is stated, never hidden)
    calib, calib_note = None, None
    if isinstance(calibration, dict):
        calib = calibration
    elif calibration == "default":
        import lpbf_calibration_layer as layer
        try:
            calib = layer.load_calibration()
        except layer.CalibrationError as exc:
            calib_note = f"calibration artefact unavailable ({exc}): interval width is null"
    iv = interval_width(calib, material, calib_note)

    train_pts = [{"power_W": r["power_W"], "speed_mm_s": r["speed_mm_s"], "beamDiameter_um": r["beamDiameter_um"]}
                 for r in train_rows]
    sets_by_class: Dict[str, set] = {"conduction": set(), "transition": set(), "keyhole": set()}
    for r in train_rows:
        sets_by_class[r["regimeClass"]].add(st.set_key(r))
    for e in req["existing"]:
        c = regime_fn(material, e["power_W"], e["speed_mm_s"], e["beamDiameter_um"], req["preheat_C"])
        sets_by_class[c].add(("existing", material, e["power_W"], e["speed_mm_s"], e["beamDiameter_um"]))
    known = train_pts + req["existing"]
    min_sets = CALIBRATION_CONFIG["minSetsPerClass"]

    # per-candidate raw terms
    raw: List[Dict[str, Any]] = []
    excluded = {"fewerThanTwoKernelsResolved": 0}
    for c in cands:
        args = (material, c["power_W"], c["speed_mm_s"], c["beamDiameter_um"], req["preheat_C"], req["layer_um"],
                DEFAULT_HATCH_UM)
        dis = kernel_disagreement(args, solver_call)
        if dis["value"] is None:
            excluded["fewerThanTwoKernelsResolved"] += 1
            continue
        raw.append({"cand": c, "dis": dis, "regime": regime_fn(material, c["power_W"], c["speed_mm_s"],
                                                                c["beamDiameter_um"], req["preheat_C"])})
    if len(raw) < req["n"]:
        raise PlanError(f"only {len(raw)} of {len(cands)} candidates have at least two resolved kernels; "
                        f"cannot propose n={req['n']} (excluded: {excluded['fewerThanTwoKernelsResolved']})")

    # coverage distance in standardised ln coordinates of the known points
    if known:
        kz = np.array([_ln_point(p) for p in known])
        sd = np.maximum(kz.std(axis=0), cfg["coverage"]["minStd"])
    for rec in raw:
        z = np.array(_ln_point(rec["cand"]))
        if known:
            dist = float(np.min(np.sqrt((((kz - z) / sd) ** 2).sum(axis=1))))
        else:
            dist = None
        n_sets = len(sets_by_class[rec["regime"]])
        gap = n_sets < min_sets
        cov_val = cfg["coverage"]["classGapValue"] * (1.0 if gap else 0.0)
        cov_val += cfg["coverage"]["distanceValue"] * (1.0 if dist is None else min(1.0, dist / cfg["coverage"]["distanceCapStd"]))
        rec["cov"] = {"regimeClass": rec["regime"], "classTrainingSets": n_sets, "minSetsPerClass": min_sets,
                      "classUnderCovered": gap, "nearestDistanceStd": dist, "value": cov_val}

    # normalise and combine
    dmax = max(r["dis"]["value"] for r in raw)
    w = cfg["weights"]
    ln_norm = math.log(CALIBRATION_CONFIG["interval"]["notInformativeRatio"])
    int_term = 0.0 if iv["value"] is None else min(1.0, iv["value"] / ln_norm)
    for r in raw:
        r["disN"] = r["dis"]["value"] / dmax if dmax > 0 else 0.0
        r["base"] = w["disagreement"] * r["disN"] + w["interval"] * int_term + w["coverage"] * r["cov"]["value"]

    # greedy selection with a Gaussian neighbour down-weight
    zs = np.array([_ln_point(r["cand"]) for r in raw])
    span = np.where(zs.max(axis=0) - zs.min(axis=0) > 0, zs.max(axis=0) - zs.min(axis=0), 1.0)
    zu = (zs - zs.min(axis=0)) / span
    two_l2 = 2.0 * cfg["neighbourLengthScale"] ** 2
    factor = np.ones(len(raw))
    zmin = zs.min(axis=0)
    for e in req["existing"]:
        ez = (np.array(_ln_point(e)) - zmin) / span
        factor *= 1.0 - np.exp(-((zu - ez) ** 2).sum(axis=1) / two_l2)
    base = np.array([r["base"] for r in raw])
    chosen: List[int] = []
    adjusted_at_pick: List[float] = []
    taken = np.zeros(len(raw), dtype=bool)
    for _ in range(req["n"]):
        adj = np.round(base * factor, 12)
        adj[taken] = -np.inf
        i = int(np.argmax(adj))  # first maximum = lowest candidate index: deterministic ties
        chosen.append(i)
        adjusted_at_pick.append(float(base[i] * factor[i]))
        taken[i] = True
        factor *= 1.0 - np.exp(-((zu - zu[i]) ** 2).sum(axis=1) / two_l2)

    points = []
    for rank, i in enumerate(chosen, start=1):
        r = raw[i]
        c = r["cand"]
        points.append({
            "trackId": f"T{rank:02d}", "rank": rank, "power_W": c["power_W"], "speed_mm_s": c["speed_mm_s"],
            "beamDiameter_um": c["beamDiameter_um"], "layer_um": req["layer_um"], "preheat_C": req["preheat_C"],
            "regimeClass": r["regime"],
            "score": st.round_sig({
                "total": adjusted_at_pick[rank - 1], "base": r["base"], "weights": dict(w),
                "disagreement": {"sdLnW": r["dis"]["sdLnW"], "sdLnD": r["dis"]["sdLnD"], "raw": r["dis"]["value"],
                                 "normalised": r["disN"], "nResolvedKernels": r["dis"]["nResolved"],
                                 "resolvedKernels": r["dis"]["resolvedKernels"]},
                "intervalWidth": {"lnHiOverLo": iv["value"], "term": int_term if iv["value"] is not None else None,
                                  "note": iv["note"]},
                "coverage": r["cov"]}, 6)})
    layout = plate_layout(points, req["plate"], req["seed"])
    for p in points:
        p["layout"] = layout["slots"][p["trackId"]]
    plan = {
        "schema": PLAN_SCHEMA, "label": LABEL, "evidenceKind": EVIDENCE_KIND, "material": material,
        "inputs": {"power_W": req["power_W"], "speed_mm_s": req["speed_mm_s"], "spots_um": req["spots_um"],
                   "layer_um": req["layer_um"], "preheat_C": req["preheat_C"], "n": req["n"], "seed": req["seed"],
                   "grid": req["grid"], "plate": req["plate"], "existing": req["existing"]},
        "config": NEXT_EXPERIMENT_CONFIG, "configSha256": next_experiment_config_sha256(),
        "calibration": ({"available": True, "calibrationId": calib["calibrationId"],
                         "contentSha256": calib["contentSha256"], "configSha256": calib["configSha256"],
                         "implementationHash": calib["implementationHash"]} if calib else
                        {"available": False, "reason": calib_note or "no calibration artefact supplied"}),
        "intervalWidth": {"lnHiOverLo": iv["value"], "cells": st.round_sig(iv["cells"], 6), "note": iv["note"]},
        "candidates": {"total": len(cands), "scored": len(raw), "excluded": excluded,
                       "trainingPoints": len(train_pts), "existingPoints": len(req["existing"]),
                       "trainingNote": training_note},
        "plate": layout["plate"], "points": points,
        "commands": [
            "python -B python/tools/lpbf_next_experiment.py import --plan <plan-dir>/plan.json "
            "--measurements <plan-dir>/measurement_template.csv --source-id user-<your-id>",
            "python -B python/tools/lpbf_calibration_fit.py --user-source .runtime/user-calibration/user-<your-id>/rows.json "
            "--out-dir <scratch-dir> --table-cache .runtime/cache/lpbf_calib_table.json"],
        "limits": ("a proposal ranked by kernel disagreement, calibration interval width and training coverage; it is "
                   "not a print recommendation, does not check printability, and nothing here is validated"),
    }
    return plan


# ---------------------------------------------------------------------------------------------
# plate layout
# ---------------------------------------------------------------------------------------------
def plate_layout(points: Sequence[Dict[str, Any]], plate: Dict[str, float], seed: int) -> Dict[str, Any]:
    pc = NEXT_EXPERIMENT_CONFIG["plate"]
    spot_max = max(p["beamDiameter_um"] for p in points)
    pitch = max(pc["minSpacing_mm"], pc["spacingSpotMultiple"] * spot_max / 1000.0)
    length = pc["trackLength_mm"]
    margin = pitch
    n = len(points)
    ux, uy = plate["x_mm"] - 2 * margin, plate["y_mm"] - 2 * margin
    cols = int(math.floor((ux + pitch) / (length + pitch) + 1e-9)) if ux >= length else 0
    rows = int(math.floor(uy / pitch + 1e-9)) + 1 if uy >= 0 else 0
    if cols < 1 or rows < 1 or cols * rows < n:
        # smallest plate that fits n tracks in a near-square arrangement, so the message is actionable
        best = None
        for c in range(1, n + 1):
            r = math.ceil(n / c)
            wx, wy = 2 * margin + c * length + (c - 1) * pitch, 2 * margin + (r - 1) * pitch
            area = wx * wy
            if best is None or area < best[0]:
                best = (area, wx, wy)
        raise PlanError(f"plate {plate['x_mm']:g} x {plate['y_mm']:g} mm is too small for {n} tracks at a pitch of "
                        f"{pitch:g} mm with {length:g} mm tracks and a {margin:g} mm edge margin (about "
                        f"{best[1]:.0f} x {best[2]:.0f} mm is needed)")
    slots = [(margin + c * (length + pitch), margin + r * pitch) for r in range(rows) for c in range(cols)][:n]
    ranks = [p["trackId"] for p in points]
    order = list(range(n))
    random.Random(seed).shuffle(order)  # slot k receives the track ranks[order[k]]
    out: Dict[str, Any] = {}
    for k, idx in enumerate(order):
        x, y = slots[k]
        out[ranks[idx]] = {"printOrder": k + 1, "x_start_mm": x, "x_end_mm": x + length, "y_mm": y}
    return {"slots": out, "plate": {"x_mm": plate["x_mm"], "y_mm": plate["y_mm"], "pitch_mm": pitch,
                                    "trackLength_mm": length, "edgeMargin_mm": margin, "columns": cols, "rows": rows,
                                    "seed": seed, "rule": "spacing >= max(3 mm, 10 x largest spot); seeded random order"}}


def _csv(header: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


def _fmt(x: Any) -> str:
    return repr(float(x)) if isinstance(x, (int, float)) and not isinstance(x, bool) else str(x)


def print_plan_csv(plan: Dict[str, Any]) -> str:
    pts = sorted(plan["points"], key=lambda p: p["layout"]["printOrder"])
    return _csv(["print_order", "track_id", "rank", "power_W", "speed_mm_s", "spot_um", "layer_um", "preheat_C",
                 "regime_class", "note"],
                [[p["layout"]["printOrder"], p["trackId"], p["rank"], _fmt(p["power_W"]), _fmt(p["speed_mm_s"]),
                  _fmt(p["beamDiameter_um"]), _fmt(p["layer_um"]), _fmt(p["preheat_C"]), p["regimeClass"],
                  "screening experiment proposal; not a print recommendation"] for p in pts])


def plate_layout_csv(plan: Dict[str, Any]) -> str:
    pts = sorted(plan["points"], key=lambda p: p["layout"]["printOrder"])
    return _csv(["print_order", "track_id", "x_start_mm", "x_end_mm", "y_mm", "power_W", "speed_mm_s", "spot_um"],
                [[p["layout"]["printOrder"], p["trackId"], _fmt(p["layout"]["x_start_mm"]), _fmt(p["layout"]["x_end_mm"]),
                  _fmt(p["layout"]["y_mm"]), _fmt(p["power_W"]), _fmt(p["speed_mm_s"]), _fmt(p["beamDiameter_um"])]
                 for p in pts])


def measurement_template_csv(plan: Dict[str, Any]) -> str:
    pts = sorted(plan["points"], key=lambda p: p["layout"]["printOrder"])
    return _csv(["track_id", "power_W", "speed_mm_s", "spot_um", "width_um", "depth_um", "notes"],
                [[p["trackId"], _fmt(p["power_W"]), _fmt(p["speed_mm_s"]), _fmt(p["beamDiameter_um"]), "", "", ""]
                 for p in pts])


def plate_layout_svg(plan: Dict[str, Any]) -> str:
    pl = plan["plate"]
    X, Y = pl["x_mm"], pl["y_mm"]
    s = 4.0
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {X * s:g} {Y * s:g}" width="{X * s:g}" '
             f'height="{Y * s:g}" role="img" aria-label="Plate layout of {len(plan["points"])} proposed tracks">',
             f'<rect x="0" y="0" width="{X * s:g}" height="{Y * s:g}" fill="none" stroke="#444" stroke-width="1"/>']
    for p in sorted(plan["points"], key=lambda q: q["layout"]["printOrder"]):
        L = p["layout"]
        parts.append(f'<line x1="{L["x_start_mm"] * s:g}" y1="{L["y_mm"] * s:g}" x2="{L["x_end_mm"] * s:g}" '
                     f'y2="{L["y_mm"] * s:g}" stroke="#1f6feb" stroke-width="2"/>')
        parts.append(f'<text x="{L["x_start_mm"] * s:g}" y="{L["y_mm"] * s - 4:g}" font-size="9" fill="#222">'
                     f'{p["trackId"]} (#{L["printOrder"]})</text>')
    parts.append("</svg>\n")
    return "\n".join(parts)


def write_outputs(plan: Dict[str, Any], out_dir: Any) -> Dict[str, Path]:
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    files = {"plan.json": json.dumps(plan, sort_keys=True, indent=1, allow_nan=False) + "\n",
             "print_plan.csv": print_plan_csv(plan), "plate_layout.csv": plate_layout_csv(plan),
             "plate_layout.svg": plate_layout_svg(plan), "measurement_template.csv": measurement_template_csv(plan)}
    out = {}
    for name, text in files.items():
        p = d / name
        p.write_text(text, encoding="utf-8", newline="\n")
        out[name] = p
    return out
