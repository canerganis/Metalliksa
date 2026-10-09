"""Machine (single-source) melt-pool DEPTH calibration from the user's own tracks. SCREENING ONLY, NOT VALIDATION.

Scope (maintainer decisions over SPEC_machine_calibration_2026-10-09): only Rosenthal depth for 316L Stainless Steel
is eligible; every other cell is ``not-eligible`` with its reason. The nuisance is a plain machine depth factor
``f = exp(c)``, an empirical machine offset, never an absorptivity or a physical quantity. The frozen solver is called
only at the material default absorptivity (flat-plate path, the path the calibration kernels use).

Label rule: a served cell carries evidence kind ``calibrated-simulation`` with scope "this machine, user data" only if
gate G6 passes AND every one of the user's tracks has the five method fields filled; otherwise it is ``screening-only``
and the missing fields are listed. A refused or not-eligible cell is always ``screening-only``. Never "validated";
``experimentalValidation`` stays false; the global calibration and scorecard are untouched. The Build Job verdict
never uses the calibrated depth.

Nothing here edits, or is imported by, the frozen physics (``IMPLEMENTATION_SOURCE_FILES``).
"""

from __future__ import annotations

import datetime as _dt
import json
import math
import random
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

import lpbf_calibration_stats as st
import lpbf_machine_calibration_config as mcfg
from lpbf_machine_calibration_config import MACHINE_CALIBRATION_CONFIG, MACHINE_SCHEMA, canonical_json, config_sha256

ROWS_SCHEMA = "lpbf-user-measurements-1"
ROW_LABEL = "Measured (user-supplied)"
QUANTITIES = ("depth", "width")
KERNELS = ("eagar-tsai", "goldak", "rosenthal")
DEFAULT_HATCH_UM = 100.0
NOMINAL_LAYER_UM = 30.0

ARTEFACT_KEYS = frozenset({
    "schema", "machineCalibrationId", "userSourceId", "generatedAt", "implementationHash", "codeRevision", "toolSha256",
    "configSha256", "userRowsSha256", "planSha256", "material", "nTracks", "nRows", "nResolved", "regimeClasses",
    "cells", "methodFields", "experimentalValidation", "labelPromotionProposed", "nuisance", "honesty", "contentSha256"})
CELL_KEYS = frozenset({
    "kernel", "quantity", "status", "reasons", "reasonText", "c", "factor", "cCi90", "factorCi90", "lossDefault",
    "lossCal", "gate", "looResiduals", "band", "perRegimeMedianLoo", "envelope", "evidenceKind", "evidenceScope",
    "evidenceLabel", "methodComplete", "missingMethodFields"})


class MachineCalibrationError(Exception):
    """The input or the artefact is malformed, tampered with or inconsistent with the compiled-in configuration."""


class MachineCalibrationStale(MachineCalibrationError):
    """The artefact was fitted against a different frozen-physics fingerprint (re-fit after the physics bump)."""


# --------------------------------------------------------------------------------------------------------------
# solver access (injectable): solver_call(args, kernel) -> (width_um, depth_um, extentStatus, normalizedEnthalpy)
# --------------------------------------------------------------------------------------------------------------
SolverCall = Callable[[Tuple, str], Tuple[Optional[float], Optional[float], str, Optional[float]]]


def default_solver_call(args: Tuple, kernel: str) -> Tuple[Optional[float], Optional[float], str, Optional[float]]:
    """The frozen solver at the material default absorptivity on the flat-plate path (no overrides at all)."""
    import contextlib
    import io
    st.pin_flat_plate()
    from lpbf_thermal_solver import calculate_meltpool_physics
    material, P, v, d, preheat, layer, hatch = args
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            res = calculate_meltpool_physics(material, P, v, d, preheat, layer, hatch, heat_source=kernel,
                                             absorption_model="flat-plate")
        g = res["meltPoolGeometry"]
        h = (res.get("processParameters") or {}).get("normalizedEnthalpy")
        return float(g["width_um"]), float(g["depth_um"]), str(g.get("extentStatus")), (None if h is None else float(h))
    except Exception as exc:  # recorded as data, never swallowed silently
        return None, None, f"error: {type(exc).__name__}", None


# --------------------------------------------------------------------------------------------------------------
# small numerics
# --------------------------------------------------------------------------------------------------------------
def _betacf(a: float, b: float, x: float) -> float:
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-14:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_cdf(t: float, df: int) -> float:
    x = df / (df + t * t)
    tail = 0.5 * _betainc(df / 2.0, 0.5, x)
    return 1.0 - tail if t >= 0 else tail


def t_ppf(p: float, df: int) -> float:
    """Student-t quantile by bisection on the exact CDF (no scipy dependency)."""
    if not (0.5 <= p < 1.0) or df < 1:
        raise ValueError("t_ppf needs 0.5 <= p < 1 and df >= 1")
    lo, hi = 0.0, 10.0
    while t_cdf(hi, df) < p:
        hi *= 2.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def c_grid(cfg: Dict[str, Any] = MACHINE_CALIBRATION_CONFIG) -> np.ndarray:
    g = cfg["fit"]["cGrid"]
    n = int(round((g["hi"] - g["lo"]) / g["step"])) + 1
    grid = np.round(g["lo"] + g["step"] * np.arange(n), 10)
    return grid


def fit_c(resid: Sequence[float], cfg: Dict[str, Any] = MACHINE_CALIBRATION_CONFIG,
          grid: Optional[np.ndarray] = None) -> Tuple[float, float]:
    """Minimise mean |r_j - c| + lambda * c^2 on the fine grid; ties go to the smaller |c|. Returns (c, loss)."""
    r = np.asarray(resid, dtype=float)
    g = c_grid(cfg) if grid is None else grid
    loss = np.abs(r[:, None] - g[None, :]).mean(axis=0) + cfg["fit"]["lambda"] * g * g
    mn = float(loss.min())
    cand = np.flatnonzero(loss <= mn + 1e-12)
    j = int(cand[np.argmin(np.abs(g[cand]))])
    return float(g[j]), float(loss[j])


def loo_residuals(resid: Sequence[float], cfg: Dict[str, Any] = MACHINE_CALIBRATION_CONFIG) -> List[float]:
    """e_i = r_i - c_{-i}, with c_{-i} fitted without track i."""
    r = list(resid)
    grid = c_grid(cfg)
    out = []
    for i in range(len(r)):
        c_i, _ = fit_c(r[:i] + r[i + 1:], cfg, grid)
        out.append(r[i] - c_i)
    return out


def bootstrap_c(resid: Sequence[float], cfg: Dict[str, Any] = MACHINE_CALIBRATION_CONFIG) -> List[float]:
    f = cfg["fit"]
    rng = random.Random(f["bootstrapSeed"])
    r = list(resid)
    n = len(r)
    grid = c_grid(cfg)
    cs = sorted(fit_c([r[rng.randrange(n)] for _ in range(n)], cfg, grid)[0] for _ in range(f["bootstrapReplicates"]))
    a = (1.0 - f["bootstrapLevel"]) / 2.0
    lo = cs[int(math.floor(a * (len(cs) - 1)))]
    hi = cs[int(math.ceil((1.0 - a) * (len(cs) - 1)))]
    return [lo, hi]


def user_band(loo: Sequence[float], c: float, cfg: Dict[str, Any] = MACHINE_CALIBRATION_CONFIG) -> Dict[str, Any]:
    """80 % band from the LOO residuals of the factor fit: factors exp(mu -/+ t * s * sqrt(1 + 1/m)) on the value."""
    m = len(loo)
    b = cfg["band"]
    if m < 2:
        return {"level": b["level"], "m": m, "mu": None, "s": None, "t": None, "factors": None, "informative": False}
    mu = float(np.mean(loo))
    s = float(np.std(loo, ddof=1))
    t = t_ppf(0.5 + b["level"] / 2.0, m - 1)
    half = t * s * math.sqrt(1.0 + 1.0 / m)
    lo, hi = math.exp(mu - half), math.exp(mu + half)
    return {"level": b["level"], "m": m, "mu": mu, "s": s, "t": t, "factors": [lo, hi],
            "informative": (hi / lo) <= b["notInformativeRatio"], "statement": b["statement"]}


# --------------------------------------------------------------------------------------------------------------
# user rows -> tracks
# --------------------------------------------------------------------------------------------------------------
def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def validate_user_doc(doc: Any) -> Dict[str, Any]:
    if not isinstance(doc, dict) or doc.get("schema") != ROWS_SCHEMA:
        raise MachineCalibrationError(f"user rows schema must be {ROWS_SCHEMA}")
    material = doc.get("material")
    sid = doc.get("sourceId")
    rows = doc.get("rows")
    if not isinstance(material, str) or not material or not isinstance(sid, str) or not sid:
        raise MachineCalibrationError("user rows need a material and a source id")
    if not isinstance(rows, list) or not rows:
        raise MachineCalibrationError("user rows are empty")
    for r in rows:
        if not isinstance(r, dict) or r.get("label") != ROW_LABEL or r.get("source") != sid or r.get("catalog") is not False:
            raise MachineCalibrationError(f"row {r.get('rowId') if isinstance(r, dict) else r!r} is not a user-supplied row")
        if r.get("material") != material:
            raise MachineCalibrationError(f"row {r.get('rowId')!r} material differs from the document material")
        for k in ("power_W", "speed_mm_s", "beamDiameter_um", "preheat_C", "layer_um", "width_um", "depth_um"):
            if not _is_num(r.get(k)) or r[k] < 0:
                raise MachineCalibrationError(f"row {r.get('rowId')!r} has a bad {k}")
        if not (r["depth_um"] > 0 and r["width_um"] > 0 and r["power_W"] > 0 and r["speed_mm_s"] > 0
                and r["beamDiameter_um"] > 0):
            raise MachineCalibrationError(f"row {r.get('rowId')!r}: power, speed, spot, width and depth must be positive")
    return doc


def row_missing_method_fields(row: Dict[str, Any], cfg: Dict[str, Any] = MACHINE_CALIBRATION_CONFIG) -> List[str]:
    """The required method fields that are absent or empty on this row (in the declared order)."""
    mf = cfg["methodFields"]
    block = row.get(mf["rowKey"])
    block = block if isinstance(block, dict) else {}
    missing = []
    for k in mf["required"]:
        v = block.get(k)
        if k == "measuredPowerW":
            ok = _is_num(v) and v > 0
        elif k == "replicates":
            ok = isinstance(v, int) and not isinstance(v, bool) and v >= 1
        else:
            ok = isinstance(v, str) and v.strip() != ""
        if not ok:
            missing.append(k)
    return missing


def build_tracks(doc: Dict[str, Any], cfg: Dict[str, Any] = MACHINE_CALIBRATION_CONFIG) -> List[Dict[str, Any]]:
    """One track per parameter set (power, speed, spot); replicate rows are averaged in ln space (as ``set_key``)."""
    groups: Dict[tuple, List[Dict[str, Any]]] = {}
    for r in doc["rows"]:
        groups.setdefault((float(r["power_W"]), float(r["speed_mm_s"]), float(r["beamDiameter_um"])), []).append(r)
    tracks = []
    for key in sorted(groups):
        rs = groups[key]
        first = rs[0]
        layer = float(first["layer_um"]) if first["layer_um"] and first["layer_um"] > 0 else NOMINAL_LAYER_UM
        tracks.append({
            "key": key, "trackIds": [r.get("trackId", r.get("rowId")) for r in rs], "nRows": len(rs),
            "args": (doc["material"], key[0], key[1], key[2], float(first["preheat_C"]), layer,
                     float(first.get("hatch_um") or DEFAULT_HATCH_UM)),
            "lnMeasured": float(np.mean([math.log(r["depth_um"]) for r in rs])),
            "missingMethod": sorted({f for r in rs for f in row_missing_method_fields(r, cfg)},
                                    key=cfg["methodFields"]["required"].index)})
    return tracks


def _in_bounds(args: Tuple) -> bool:
    from lpbf_simulation import BOUNDS
    _, P, v, d, preheat, layer, _h = args
    return all(BOUNDS[k][0] <= x <= BOUNDS[k][1] for k, x in (
        ("power_W", P), ("speed_mm_s", v), ("beamDiameter_um", d), ("preheat_C", preheat), ("layer_um", layer)))


# --------------------------------------------------------------------------------------------------------------
# gate G6 (factor form) and one cell
# --------------------------------------------------------------------------------------------------------------
def gate_cell(resid: Sequence[float], c: float, loo: Sequence[float], cfg: Dict[str, Any] = MACHINE_CALIBRATION_CONFIG,
              *, eligible: bool = True, n_unresolved: int = 0) -> Dict[str, Any]:
    """Evaluate G6 (conditions 1, 2, 3, 6 and the factor range). Every failed condition is listed with its number."""
    g = cfg["gate"]
    r = np.asarray(resid, dtype=float)
    m = int(r.size)
    n_pos, n_neg = int((r > 0).sum()), int((r < 0).sum())
    sign_frac = (max(n_pos, n_neg) / m) if m else 0.0
    mean_r = float(r.mean()) if m else 0.0
    mae_def = float(np.abs(r).mean()) if m else 0.0
    mae_loo = float(np.abs(np.asarray(loo)).mean()) if len(loo) else None
    skill = (1.0 - mae_loo / mae_def) if (mae_loo is not None and mae_def > 0) else None
    reasons: List[str] = []
    if not eligible:
        reasons.append("notEligible")
    if m < g["minTracks"] or n_unresolved > 0:
        reasons.append("tooFewTracks")
    if m >= 1 and sign_frac < g["uniformSignFraction"]:
        reasons.append("uniformSign")
    if m >= 1 and abs(mean_r) < g["minAbsMeanLnResidual"]:
        reasons.append("offsetTooSmall")
    if skill is None or not skill > 0:
        reasons.append("looSkill")
    if abs(c) > g["maxAbsC"]:
        reasons.append("factorOutOfRange")
    return {"nTracks": m, "nUnresolved": n_unresolved, "nOver": n_neg, "nUnder": n_pos,
            "uniformSignFraction": sign_frac, "meanLnResidualDefault": mean_r, "looSkill": skill,
            "factorInRange": abs(c) <= g["maxAbsC"], "eligible": eligible, "passed": not reasons, "reasons": reasons}


_REASON_TEXT = {
    "notEligible": "this cell is not eligible for machine calibration",
    "tooFewTracks": "fewer than {minTracks} resolved tracks inside the solver bounds",
    "uniformSign": "your tracks do not show a uniform offset ({over} over, {under} under, mean {mean:+.0%}); a single "
                   "machine factor cannot represent this",
    "offsetTooSmall": "the mean offset ({mean:+.0%}) is smaller than the {min:.0%} the gate requires",
    "looSkill": "leave-one-track-out refits do not beat the uncalibrated prediction",
    "factorOutOfRange": "the fitted machine factor ({f:.2f}) is outside 1/3 to 3",
}


def _reason_texts(gate: Dict[str, Any], f: Optional[float], cfg: Dict[str, Any]) -> List[str]:
    out = []
    for code in gate["reasons"]:
        out.append(_REASON_TEXT[code].format(
            minTracks=cfg["gate"]["minTracks"], over=gate["nOver"], under=gate["nUnder"],
            mean=math.expm1(gate["meanLnResidualDefault"]), min=cfg["gate"]["minAbsMeanLnResidual"],
            f=f if f is not None else float("nan")))
    return out


def _evidence(status: str, method_missing: List[Dict[str, Any]], cfg: Dict[str, Any]) -> Dict[str, Any]:
    ev = cfg["evidence"]
    complete = not method_missing
    if status == "served" and complete:
        return {"evidenceKind": ev["calibrated"], "evidenceScope": ev["scope"], "evidenceLabel": ev["labelCalibrated"],
                "methodComplete": True, "missingMethodFields": []}
    return {"evidenceKind": ev["screening"], "evidenceScope": None, "evidenceLabel": ev["labelScreening"],
            "methodComplete": complete, "missingMethodFields": method_missing}


def _missing_list(tracks: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{"trackIds": t["trackIds"], "fields": t["missingMethod"]} for t in tracks if t["missingMethod"]]


def _not_eligible_cell(kernel: str, quantity: str, material: str, tracks: Sequence[Dict[str, Any]],
                       cfg: Dict[str, Any]) -> Dict[str, Any]:
    cell = {k: None for k in CELL_KEYS}
    cell.update({"kernel": kernel, "quantity": quantity, "status": "not-eligible", "reasons": ["notEligible"],
                 "reasonText": [mcfg.not_eligible_reason(kernel, material, quantity, cfg)]})
    cell.update(_evidence("not-eligible", _missing_list(tracks), cfg))
    return cell


def evaluate_depth_cell(kernel: str, material: str, tracks: Sequence[Dict[str, Any]], solver_call: SolverCall,
                        cfg: Dict[str, Any] = MACHINE_CALIBRATION_CONFIG) -> Tuple[Dict[str, Any], Dict[str, int]]:
    preds: List[Optional[float]] = []
    regimes: Dict[str, int] = {"conduction": 0, "transition": 0, "keyhole": 0}
    cls: List[Optional[str]] = []
    for t in tracks:
        if not _in_bounds(t["args"]):
            preds.append(None)
            cls.append(None)
            continue
        _w, d, status, h = solver_call(t["args"], kernel)
        ok = status == "computed" and d is not None and math.isfinite(d) and d > 0
        preds.append(d if ok else None)
        cls.append(st.regime_class_from_enthalpy(h) if (ok and h is not None) else None)
    use = [i for i, p in enumerate(preds) if p is not None]
    n_unres = len(tracks) - len(use)
    for i in use:
        if cls[i]:
            regimes[cls[i]] += 1
    resid = [tracks[i]["lnMeasured"] - math.log(preds[i]) for i in use]
    cell = {k: None for k in CELL_KEYS}
    cell.update({"kernel": kernel, "quantity": "depth"})
    if len(resid) < 2:
        gate = gate_cell(resid, 0.0, [], cfg, n_unresolved=n_unres)
        cell.update({"status": "refused", "gate": gate, "reasons": gate["reasons"],
                     "reasonText": _reason_texts(gate, None, cfg), "looResiduals": []})
        cell.update(_evidence("refused", _missing_list(tracks), cfg))
        return cell, regimes
    c, loss_cal = fit_c(resid, cfg)
    loo = loo_residuals(resid, cfg)
    gate = gate_cell(resid, c, loo, cfg, n_unresolved=n_unres)
    f = math.exp(c)
    cci = bootstrap_c(resid, cfg)
    per_regime: Dict[str, Optional[float]] = {}
    for name in ("conduction", "transition", "keyhole"):
        vals = [loo[k] for k, i in enumerate(use) if cls[i] == name]
        per_regime[name] = float(np.median(vals)) if vals else None
    status = "served" if gate["passed"] else "refused"
    used = [tracks[i] for i in use]
    cell.update({
        "status": status, "reasons": gate["reasons"], "reasonText": _reason_texts(gate, f, cfg),
        "c": c, "factor": f, "cCi90": cci, "factorCi90": [math.exp(cci[0]), math.exp(cci[1])],
        "lossDefault": float(np.abs(resid).mean()), "lossCal": loss_cal, "gate": gate, "looResiduals": loo,
        "band": user_band(loo, c, cfg), "perRegimeMedianLoo": per_regime,
        "envelope": {"power_W": [min(t["args"][1] for t in used), max(t["args"][1] for t in used)],
                     "speed_mm_s": [min(t["args"][2] for t in used), max(t["args"][2] for t in used)],
                     "beamDiameter_um": [min(t["args"][3] for t in used), max(t["args"][3] for t in used)]}})
    cell.update(_evidence(status, _missing_list(tracks), cfg))
    return cell, regimes


def fit_machine(doc: Dict[str, Any], *, solver_call: Optional[SolverCall] = None,
                cfg: Dict[str, Any] = MACHINE_CALIBRATION_CONFIG) -> Dict[str, Any]:
    """Pure fit: evaluate every kernel x quantity cell. The solver is called only for eligible cells."""
    doc = validate_user_doc(doc)
    solver_call = solver_call or default_solver_call
    material = doc["material"]
    tracks = build_tracks(doc, cfg)
    cells: List[Dict[str, Any]] = []
    regimes: Dict[str, int] = {"conduction": 0, "transition": 0, "keyhole": 0}
    n_resolved = 0
    for kernel in KERNELS:
        for q in QUANTITIES:
            if mcfg.is_eligible(kernel, material, q, cfg):
                cell, reg = evaluate_depth_cell(kernel, material, tracks, solver_call, cfg)
                cells.append(cell)
                regimes = reg
                n_resolved = cell["gate"]["nTracks"]
            else:
                cells.append(_not_eligible_cell(kernel, q, material, tracks, cfg))
    return {"material": material, "tracks": tracks, "cells": cells, "regimeClasses": regimes, "nResolved": n_resolved}


# --------------------------------------------------------------------------------------------------------------
# artefact
# --------------------------------------------------------------------------------------------------------------
def artefact_content_sha256(art: Dict[str, Any]) -> str:
    probe = dict(art)
    probe["contentSha256"] = ""
    probe["machineCalibrationId"] = ""
    return st.canonical_sha256(probe)


def build_artefact(doc: Dict[str, Any], *, solver_call: Optional[SolverCall] = None,
                   cfg: Dict[str, Any] = MACHINE_CALIBRATION_CONFIG, implementation_hash: Optional[str] = None,
                   code_revision: str = "unknown", tool_sha256: str = "", generated_at: Optional[str] = None
                   ) -> Dict[str, Any]:
    fit = fit_machine(doc, solver_call=solver_call, cfg=cfg)
    if implementation_hash is None:
        from lpbf_simulation import implementation_fingerprint
        implementation_hash = implementation_fingerprint()
    ev = cfg["evidence"]
    art = {
        "schema": MACHINE_SCHEMA, "machineCalibrationId": "", "userSourceId": doc["sourceId"],
        "generatedAt": generated_at or _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "implementationHash": implementation_hash, "codeRevision": code_revision, "toolSha256": tool_sha256,
        "configSha256": config_sha256(cfg), "userRowsSha256": st.canonical_sha256(doc),
        "planSha256": (doc.get("provenance") or {}).get("planSha256"),
        "material": fit["material"], "nTracks": len(fit["tracks"]), "nRows": len(doc["rows"]),
        "nResolved": fit["nResolved"], "regimeClasses": fit["regimeClasses"], "cells": fit["cells"],
        "methodFields": {"required": cfg["methodFields"]["required"],
                         "missing": _missing_list(fit["tracks"])},
        "experimentalValidation": ev["experimentalValidation"], "labelPromotionProposed": ev["labelPromotionProposed"],
        "nuisance": cfg["nuisance"], "honesty": cfg["honesty"], "contentSha256": ""}
    art["contentSha256"] = artefact_content_sha256(art)
    art["machineCalibrationId"] = "mc-" + art["contentSha256"][:12]
    return art


def write_artefact(art: Dict[str, Any], path: Any) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(art, sort_keys=True, indent=1, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    return p


def _check_evidence(art: Dict[str, Any], cfg: Dict[str, Any]) -> None:
    ev = cfg["evidence"]
    if art.get("experimentalValidation") is not False or art.get("labelPromotionProposed") != "none":
        raise MachineCalibrationError("artefact must keep experimentalValidation false and no label promotion")
    for c in art.get("cells", []):
        if set(c) != CELL_KEYS:
            raise MachineCalibrationError(f"unexpected cell keys {sorted(set(c) ^ CELL_KEYS)}")
        if c["status"] not in ("served", "refused", "not-eligible"):
            raise MachineCalibrationError(f"unknown cell status {c['status']!r}")
        eligible = mcfg.is_eligible(c["kernel"], art.get("material"), c["quantity"], cfg)
        if c["status"] == "served":
            gate = c["gate"]
            if not eligible:
                raise MachineCalibrationError("a served cell must be an eligible cell for the artefact material")
            if not (isinstance(gate, dict) and gate.get("passed") is True and c["reasons"] == []):
                raise MachineCalibrationError("a served cell needs a passed gate and no refusal reasons")
        elif c["status"] == "not-eligible" and eligible:
            raise MachineCalibrationError("an eligible cell must not be marked not-eligible")
        full = c["status"] == "served" and c["methodComplete"] is True and not c["missingMethodFields"]
        if c["evidenceKind"] == ev["calibrated"]:
            if not full or c["evidenceScope"] != ev["scope"]:
                raise MachineCalibrationError("calibrated-simulation needs a served cell, complete method fields and "
                                              "the scope 'this machine, user data'")
        elif c["evidenceKind"] != ev["screening"] or full:
            raise MachineCalibrationError("evidence kind is inconsistent with the cell status and method fields")
        if "validated" in json.dumps(c).lower():
            raise MachineCalibrationError("a cell must never carry the word validated")


def load_machine_calibration(path: Any, *, expected_impl_hash: Optional[str] = None,
                             cfg: Dict[str, Any] = MACHINE_CALIBRATION_CONFIG) -> Dict[str, Any]:
    """Load and verify. Refuses unknown keys, content hash, config hash, bad evidence fields and a stale fingerprint."""
    p = Path(path)
    try:
        art = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MachineCalibrationError(f"machine calibration artefact missing: {p}") from exc
    except json.JSONDecodeError as exc:
        raise MachineCalibrationError(f"machine calibration artefact is not valid JSON: {exc}") from exc
    if not isinstance(art, dict) or art.get("schema") != MACHINE_SCHEMA:
        raise MachineCalibrationError("unexpected machine calibration schema")
    unknown = sorted(set(art) - ARTEFACT_KEYS)
    if unknown:
        raise MachineCalibrationError(f"unknown artefact keys rejected: {unknown}")
    if art.get("contentSha256") != artefact_content_sha256(art):
        raise MachineCalibrationError("contentSha256 does not match the artefact content (tampered or hand-edited)")
    if art.get("configSha256") != config_sha256(cfg):
        raise MachineCalibrationError("MACHINE_CALIBRATION_CONFIG sha256 differs from the artefact's: a config change "
                                      "needs a re-fit")
    _check_evidence(art, cfg)
    live = expected_impl_hash
    if live is None:
        from lpbf_simulation import implementation_fingerprint
        live = implementation_fingerprint()
    if art.get("implementationHash") != live:
        raise MachineCalibrationStale("machine calibration stale for this physics version: re-fit after the physics "
                                      f"bump (artefact {str(art.get('implementationHash'))[:12]}, live {str(live)[:12]})")
    return art


def try_load_machine_calibration(path: Any, **kw: Any) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """Never raises for a bad or stale artefact: returns (artefact or None, {'available': bool, 'reason': str|None})."""
    try:
        art = load_machine_calibration(path, **kw)
    except MachineCalibrationStale as exc:
        return None, {"available": False, "stale": True, "reason": str(exc)}
    except MachineCalibrationError as exc:
        return None, {"available": False, "stale": False, "reason": str(exc)}
    return art, {"available": True, "stale": False, "reason": None}


# --------------------------------------------------------------------------------------------------------------
# apply
# --------------------------------------------------------------------------------------------------------------
def _solver_kwargs(inputs: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "args": (inputs.get("material", "Inconel 718"), float(inputs.get("laserPower_W", 285.0)),
                 float(inputs.get("scanSpeed_mm_s", 960.0)), float(inputs.get("beamDiameter_um", 80.0)),
                 float(inputs.get("preheatTemp_C", 80.0)), float(inputs.get("layerThickness_um", 40.0)),
                 float(inputs.get("hatchSpacing_um", 110.0)), inputs.get("laserWavelength", "IR_1064nm")),
        "kwargs": {"sulfur_ppm": float(inputs.get("sulfur_ppm", inputs.get("sulfurPpm", 15.0))),
                   "absorption_model": inputs.get("absorptionModel"),
                   "thermal_slice_backend": inputs.get("thermalSliceBackend")}}


def _default_apply_solver() -> Callable[..., Dict[str, Any]]:
    from lpbf_thermal_solver import calculate_meltpool_physics
    return calculate_meltpool_physics


def _cell_for(art: Dict[str, Any], kernel: str, quantity: str) -> Optional[Dict[str, Any]]:
    for c in art.get("cells", []):
        if c["kernel"] == kernel and c["quantity"] == quantity:
            return c
    return None


def apply_machine_calibration(inputs: Dict[str, Any], kernel: str, art: Optional[Dict[str, Any]], *,
                              solver: Optional[Callable[..., Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Screening result unchanged + a ``machineCalibrated`` block. The calibrated depth is f * the frozen flat-plate depth
    at the default absorptivity. Width is never served; no ratio is derived from a mix of values; the Build Job verdict
    never reads this block."""
    solver = solver or _default_apply_solver()
    spec = _solver_kwargs(inputs)
    material = spec["args"][0]
    screening = solver(*spec["args"], heat_source=kernel, **spec["kwargs"])
    ev = MACHINE_CALIBRATION_CONFIG["evidence"]
    block: Dict[str, Any] = {"available": False, "kernel": kernel, "material": material, "quantity": "depth",
                             "depth_um": None, "depthBand_um": None, "width_um": None,
                             "widthReason": "width is not part of machine calibration",
                             "evidenceKind": ev["screening"], "evidenceScope": None, "evidenceLabel": ev["labelScreening"],
                             "missingMethodFields": [], "reasons": [], "reasonText": [],
                             "usedForBuildJobVerdict": False,
                             "note": ("empirical machine offset fitted to the user's own tracks; it absorbs model "
                                      "error and is not an absorptivity; reported next to the screening value")}
    out: Dict[str, Any] = {"screening": screening, "machineCalibrated": block, "experimentalValidation": False}
    if art is None:
        block["reasonText"] = ["no machine calibration artefact selected"]
        return out
    block["machineCalibrationId"] = art["machineCalibrationId"]
    cell = _cell_for(art, kernel, "depth")
    if cell is None or art.get("material") != material:
        block["reasonText"] = ["the artefact has no cell for this kernel and material"]
        return out
    block.update({"status": cell["status"], "reasons": cell["reasons"], "reasonText": cell["reasonText"],
                  "evidenceKind": cell["evidenceKind"], "evidenceScope": cell["evidenceScope"],
                  "evidenceLabel": cell["evidenceLabel"], "missingMethodFields": cell["missingMethodFields"],
                  "userResidualSummary": {"nTracks": cell["gate"]["nTracks"] if cell["gate"] else None,
                                          "meanLnResidualDefault": cell["gate"]["meanLnResidualDefault"] if cell["gate"] else None,
                                          "perRegimeMedianLoo": cell["perRegimeMedianLoo"]}})
    if cell["status"] != "served":
        return out
    basis = MACHINE_CALIBRATION_CONFIG["fit"]["basis"]
    wl = spec["args"][-1]
    if wl != basis["laserWavelength"]:
        block.update({"available": False, "evidenceKind": ev["screening"], "evidenceScope": None,
                      "evidenceLabel": ev["labelScreening"]})
        block["reasonText"] = [f"fitted on the {basis['laserWavelength']} default; not applied to {wl}"]
        return out
    # the served base call runs at the fit basis (default wavelength, default thermal backend), as the fit did
    res = solver(*spec["args"][:-1], basis["laserWavelength"], heat_source=kernel,
                 sulfur_ppm=spec["kwargs"]["sulfur_ppm"], absorption_model="flat-plate", thermal_slice_backend=None)
    base = float(res["meltPoolGeometry"]["depth_um"])
    f = cell["factor"]
    block["available"] = True
    block["factor"] = f
    block["depth_um"] = base * f
    band = cell["band"]
    block["band"] = band
    if band["factors"]:
        block["depthBand_um"] = [base * f * band["factors"][0], base * f * band["factors"][1]]
        block["bandNotInformative"] = not band["informative"]
    env = cell["envelope"] or {}
    notes = []
    for key, label in (("laserPower_W", "power"), ("scanSpeed_mm_s", "speed"), ("beamDiameter_um", "beam diameter")):
        rng = env.get({"laserPower_W": "power_W", "scanSpeed_mm_s": "speed_mm_s", "beamDiameter_um": "beamDiameter_um"}[key])
        v = float(inputs.get(key, float("nan")))
        if rng and not (rng[0] <= v <= rng[1]):
            notes.append(f"{label} {v:g} outside the range of your tracks [{rng[0]:g}, {rng[1]:g}]")
    block["outsideUserTrackRange"] = bool(notes)
    block["userTrackRangeNotes"] = notes
    return out
