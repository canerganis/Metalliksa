#!/usr/bin/env python3
"""Powder-layer model evidence for LPBF (plan item 5, batch 2): ANALYSIS, not a model change.

COMPARISON / ANALYSIS, NOT VALIDATION. Four blocks:

1. matchedSets      Hofmann 2026 316L: rows grouped by (P, v, d_laser); sets that have >= 2 of the powder
                    thicknesses 0 / 30 / 60 um give paired width/depth differences and ratios (30 vs 0, 60 vs 0,
                    60 vs 30). One value per (set, level) = the mean over that set's replicate rows; the
                    statistic across sets is the median (IQR alongside) with a cluster bootstrap 95 % CI
                    (parameter sets resampled with random.Random(0), 1000 replicates).
2. kernelSensitivity  calculate_meltpool_physics (flat-plate pin as in lpbf_dataset_comparison.py) at layer
                    10/30/60 um for all three screening kernels: the layer is ignored, W/D/L must be identical.
3. referenceTransient  BOUNDED (<= 6 cases, total/per-case wall budgets): enthalpy-FV reference transient on 2
                    Hofmann parameter sets at layer 0 (bare plate) / 30 / 60 um (homogenised powder layer).
                    Reported as completed / boiling-stop / meshLimited, nothing loosened.
4. literature       Cited effective-conductivity laws for packed beds and what the Zehner-Schlunder form gives;
                    a PROPOSAL for a reviewed bump of powderConductivityRatio (0.12, uncited), not a change.

Usage (from python/, locked interpreter, PYTHONDONTWRITEBYTECODE=1):
    python -B tools/lpbf_powder_layer_analysis.py --out ../docs/LPBF_POWDER_LAYER_ANALYSIS_2026-10-05.json
Options: --skip-reference, --ref-budget-s S (default 900), --reuse-reference <record.json>, --generated-at.
The companion .md is written next to the json. Nothing is written under python/golden.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import multiprocessing
import random
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

PYTHON_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PYTHON_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

SCHEMA = "lpbf-powder-layer-analysis-1"
GENERATED_AT_DEFAULT = "2026-10-05"
LEVELS = (0.0, 30.0, 60.0)
PAIRS = ((30.0, 0.0), (60.0, 0.0), (60.0, 30.0))
KERNELS = ("rosenthal", "eagar-tsai", "goldak")
KERNEL_LAYERS_UM = (10.0, 30.0, 60.0)
CI_REPLICATES = 1000
CI_SEED = 0
LOW_N = 8
RAYTRACER_MODULE = "powder_bed_raytracer"
HONESTY_STATEMENT = ("analysis of published single-track measurements and of model sensitivity; not experimental "
                     "validation; no fitted constants; estimated material laws; the powder packing of the "
                     "measurements is not stated")
REF_SOURCE_PENETRATION_UM = 40.0
REF_MESH_UM = 20.0
REF_TRACK_LENGTH_UM = 600.0
REF_PREHEAT_C = 20.0
REF_LAYERS_UM = (0.0, 30.0, 60.0)
REF_SETS = ((100.0, 900.0, 80.0), (50.0, 300.0, 50.0))  # (P_W, v_mm_s, d_um)
REF_PER_CASE_S = 240.0
CONDUCTIVITY_RATIO_CODE = 0.12
PACKING_CODE = 0.55


def pin_flat_plate() -> None:
    """Same flat-plate pin as tools/lpbf_dataset_comparison.py (solver is not edited)."""
    sys.modules[RAYTRACER_MODULE] = None


# ---------------------------------------------------------------------------------------------
# pure statistics
# ---------------------------------------------------------------------------------------------
def percentile(sorted_vals: Sequence[float], q: float) -> float:
    pos = (len(sorted_vals) - 1) * q / 100.0
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def median(vals: Sequence[float]) -> float:
    return percentile(sorted(vals), 50.0)


def iqr(vals: Sequence[float]) -> List[float]:
    s = sorted(vals)
    return [percentile(s, 25.0), percentile(s, 75.0)]


def cluster_bootstrap_medians(columns: Sequence[Sequence[float]], replicates: int = CI_REPLICATES,
                              seed: int = CI_SEED) -> List[List[float]]:
    """columns[j][i] = statistic j of cluster (parameter set) i. Resamples clusters with replacement with
    random.Random(seed) (same draws for every column); returns [2.5, 97.5] percentiles of each column's median."""
    k = len(columns[0])
    rng = random.Random(seed)
    idx = range(k)
    boots: List[List[float]] = [[] for _ in columns]
    for _ in range(replicates):
        pick = rng.choices(idx, k=k)
        for j, col in enumerate(columns):
            boots[j].append(median([col[i] for i in pick]))
    return [[percentile(sorted(b), 2.5), percentile(sorted(b), 97.5)] for b in boots]


def group_sets(rows: Sequence[Dict[str, Any]]) -> Dict[Tuple[float, float, float], Dict[float, List[Dict[str, Any]]]]:
    """(P_W, v_mm_s, d_um) -> {layer_um: [rows]} (replicates stay together)."""
    sets: Dict[Tuple[float, float, float], Dict[float, List[Dict[str, Any]]]] = {}
    for r in rows:
        sets.setdefault((r["power_W"], r["speed_mm_s"], r["beamDiameter_um"]), {}).setdefault(r["layer_um"], []).append(r)
    return sets


def _mean(vals: Sequence[float]) -> float:
    return sum(vals) / len(vals)


def paired_values(sets: Dict[Any, Dict[float, List[Dict[str, Any]]]], hi: float, lo: float,
                  keys: Optional[Sequence[Any]] = None) -> List[Dict[str, Any]]:
    """Per matched set (both levels present): replicate-mean width/depth at each level."""
    out = []
    for key in sorted(sets if keys is None else keys):
        lv = sets[key]
        if hi in lv and lo in lv:
            rec = {"key": key}
            for q, name in (("width_um", "w"), ("depth_um", "d")):
                a = _mean([r[q] for r in lv[hi]])
                b = _mean([r[q] for r in lv[lo]])
                rec[name + "_hi"], rec[name + "_lo"] = a, b
            out.append(rec)
    return out


def paired_summary(sets: Dict[Any, Dict[float, List[Dict[str, Any]]]], hi: float, lo: float,
                   keys: Optional[Sequence[Any]] = None) -> Dict[str, Any]:
    pv = paired_values(sets, hi, lo, keys)
    n_hi = sum(len(sets[p["key"]][hi]) for p in pv)
    n_lo = sum(len(sets[p["key"]][lo]) for p in pv)
    out: Dict[str, Any] = {"pair": f"{hi:g} vs {lo:g}", "nSets": len(pv), "nRowsHigh": n_hi, "nRowsLow": n_lo,
                           "lowN": len(pv) < LOW_N}
    if not pv:
        return out
    cols = {"widthRatio": [p["w_hi"] / p["w_lo"] for p in pv], "widthDiff_um": [p["w_hi"] - p["w_lo"] for p in pv],
            "depthRatio": [p["d_hi"] / p["d_lo"] for p in pv], "depthDiff_um": [p["d_hi"] - p["d_lo"] for p in pv]}
    names = list(cols)
    cis = cluster_bootstrap_medians([cols[n] for n in names]) if len(pv) >= 2 else [[None, None]] * len(names)
    for n, ci in zip(names, cis):
        out[n] = {"median": median(cols[n]), "iqr": iqr(cols[n]), "ci95": ci,
                  "fractionAbove1" if n.endswith("Ratio") else "fractionPositive":
                      sum(1 for v in cols[n] if v > (1.0 if n.endswith("Ratio") else 0.0)) / len(pv)}
    out["levelMedians_um"] = {
        "width": {f"{hi:g}": median([p["w_hi"] for p in pv]), f"{lo:g}": median([p["w_lo"] for p in pv])},
        "depth": {f"{hi:g}": median([p["d_hi"] for p in pv]), f"{lo:g}": median([p["d_lo"] for p in pv])}}
    out["levelIqr_um"] = {
        "width": {f"{hi:g}": iqr([p["w_hi"] for p in pv]), f"{lo:g}": iqr([p["w_lo"] for p in pv])},
        "depth": {f"{hi:g}": iqr([p["d_hi"] for p in pv]), f"{lo:g}": iqr([p["d_lo"] for p in pv])}}
    return out


def balling_fractions(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    out = {}
    for L in LEVELS:
        sel = [r for r in rows if r["layer_um"] == L and r["balling"] is not None]
        out[f"{L:g}"] = {"rows": len(sel), "ballingFlagged": sum(1 for r in sel if r["balling"] == 1),
                         "fraction": (sum(1 for r in sel if r["balling"] == 1) / len(sel)) if sel else None}
    return out


def analyse_matched_sets(rows: Sequence[Dict[str, Any]], set_regime: Dict[Any, str]) -> Dict[str, Any]:
    """rows: Hofmann rows. set_regime: set key -> inputs-only regime label."""
    sets = group_sets(rows)
    multi = {k: v for k, v in sets.items() if len(v) >= 2}
    splits: Dict[str, Dict[str, Any]] = {"all": {}, "byRegime": {}, "bySpot_um": {}}

    def block(keys: Sequence[Any]) -> Dict[str, Any]:
        rows_in = [r for k in keys for lv in sets[k].values() for r in lv]
        return {"nSets": len(keys), "nRows": len(rows_in),
                "pairs": {f"{h:g}_vs_{l:g}": paired_summary(sets, h, l, keys) for h, l in PAIRS},
                "ballingFractionByLevel": balling_fractions(rows_in)}

    splits["all"] = block(sorted(multi))
    for lab in sorted({set_regime[k] for k in multi}):
        splits["byRegime"][lab] = block(sorted(k for k in multi if set_regime[k] == lab))
    for d in sorted({k[2] for k in multi}):
        splits["bySpot_um"][f"{d:g}"] = block(sorted(k for k in multi if k[2] == d))
    levels_present = {}
    for L in LEVELS:
        levels_present[f"{L:g}"] = {"sets": sum(1 for v in sets.values() if L in v),
                                    "rows": sum(len(v[L]) for v in sets.values() if L in v)}
    return {"grouping": "rows grouped by (power_W, speed_mm_s, d_laser_um); a set is 'matched' if it has >= 2 of "
                        "the thickness levels 0/30/60 um",
            "statistic": "per set and level: mean over replicate rows; per pair: ratio = high/low and difference "
                         "= high - low per matched set; across sets: median, IQR (25/75 %, linear interpolation), "
                         "cluster-bootstrap 95 % CI of the median (sets resampled, random.Random(0), 1000 reps); "
                         "lowN = true when fewer than 8 sets",
            "regimeLabel": "inputs-only screening label (classify_regime with balling = 0), so a set keeps one "
                           "label across thickness levels; balling flags are reported separately, per level",
            "datasetTotals": {"sets": len(sets), "matchedSets": len(multi), "rows": len(rows),
                              "levels": levels_present,
                              "setsWithAllThreeLevels": sum(1 for v in sets.values() if len(v) == 3)},
            "ballingFractionByLevelAllRows": balling_fractions(rows),
            **splits}


# ---------------------------------------------------------------------------------------------
# kernel sensitivity (calls the solver, flat-plate pin)
# ---------------------------------------------------------------------------------------------
def kernel_sensitivity(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    pin_flat_plate()
    from lpbf_thermal_solver import calculate_meltpool_physics
    cases = []
    max_rel = 0.0
    fallback = 0
    for r in rows:
        for kernel in KERNELS:
            res = {}
            for layer in KERNEL_LAYERS_UM:
                cap = io.StringIO()
                with contextlib.redirect_stdout(cap):
                    out = calculate_meltpool_physics(r["material"], r["power_W"], r["speed_mm_s"],
                                                     r["beamDiameter_um"], r["preheat_C"], layer, 100.0,
                                                     heat_source=kernel)
                fallback += cap.getvalue().count("GPU Powder Bed Ray Tracing failed")
                g = out["meltPoolGeometry"]
                res[f"{layer:g}"] = {k: float(g[k]) for k in ("width_um", "depth_um", "length_um")}
            base = res[f"{KERNEL_LAYERS_UM[0]:g}"]
            rel = 0.0
            for lv in res.values():
                for k in base:
                    denom = abs(base[k])
                    d = abs(lv[k] - base[k])
                    rel = max(rel, d / denom if denom > 0 else (0.0 if d == 0 else float("inf")))
            max_rel = max(max_rel, rel)
            cases.append({"rowId": r["rowId"], "power_W": r["power_W"], "speed_mm_s": r["speed_mm_s"],
                          "beamDiameter_um": r["beamDiameter_um"], "kernel": kernel, "byLayer_um": res,
                          "maxRelativeDifference": rel})
    return {"method": "calculate_meltpool_physics at layer 10/30/60 um, hatch 100 um, preheat 20 C, flat-plate pin "
                      "(sys.modules['powder_bed_raytracer'] = None); relative difference = |x(layer) - x(10)| / x(10)",
            "layers_um": list(KERNEL_LAYERS_UM), "kernels": list(KERNELS), "cases": cases,
            "maxRelativeDifference": max_rel, "layerIgnored": max_rel == 0.0, "fallbackWarnings": fallback,
            "solverCalls": len(rows) * len(KERNELS) * len(KERNEL_LAYERS_UM)}


# ---------------------------------------------------------------------------------------------
# bounded reference transient
# ---------------------------------------------------------------------------------------------
def reference_input(material: str, P: float, v: float, d: float, layer_um: float) -> Dict[str, Any]:
    raw = {"mode": "standard", "backend": "reference", "material": material, "power_W": P, "speed_mm_s": v,
           "beamDiameter_um": d, "preheat_C": REF_PREHEAT_C, "mesh_um": REF_MESH_UM,
           "trackLength_um": REF_TRACK_LENGTH_UM}
    if layer_um == 0.0:   # same bare-plate settings as lpbf_dataset_comparison.py
        raw.update(surfaceMode="bare-plate", barePlateGeometry="square", sourcePenetration_um=REF_SOURCE_PENETRATION_UM)
    else:                 # homogenised powder layer with the DEFAULTS packing 0.55 / ratio 0.12
        raw.update(surfaceMode="powder-layer", layer_um=layer_um)
    return raw


def reference_settings(budget_s: float, per_case_s: float = REF_PER_CASE_S) -> Dict[str, Any]:
    """Identity-bearing settings for the bounded reference block."""
    return {"mode": "standard", "backend": "reference", "material": "316L Stainless Steel",
            "mesh_um": REF_MESH_UM, "trackLength_um": REF_TRACK_LENGTH_UM, "preheat_C": REF_PREHEAT_C,
            "layer_um 0": f"bare-plate, square, sourcePenetration_um {REF_SOURCE_PENETRATION_UM:g} "
                          "(as lpbf_dataset_comparison.py)",
            "layer_um 30/60": f"powder-layer, packingFraction {PACKING_CODE}, powderConductivityRatio "
                              f"{CONDUCTIVITY_RATIO_CODE} (DEFAULTS), sourcePenetration_um default",
            "totalBudget_s": budget_s, "perCaseBudget_s": per_case_s}


def validate_reused_reference(src: Any, expected_hash: str, expected_dataset_hash: str,
                              expected_settings: Dict[str, Any]) -> Dict[str, Any]:
    """Reject malformed or stale records before reusing a reference result block."""
    if not isinstance(src, dict):
        raise ValueError("reference record must be a JSON object")
    if src.get("schema") != SCHEMA:
        raise ValueError("reference record schema is missing or incompatible")
    if src.get("implementationHash") != expected_hash:
        raise ValueError("reference record implementation fingerprint is stale or missing")
    datasets = src.get("datasets")
    if not isinstance(datasets, list) or not datasets or not isinstance(datasets[0], dict):
        raise ValueError("reference record datasets block is malformed")
    if datasets[0].get("sha256") != expected_dataset_hash:
        raise ValueError("reference record dataset hash is stale or missing")
    block = src.get("referenceTransient")
    if not isinstance(block, dict) or not isinstance(block.get("settings"), dict):
        raise ValueError("referenceTransient block or its settings are malformed")
    if block.get("settings") != expected_settings:
        raise ValueError("referenceTransient settings are incompatible with this report")
    if not isinstance(block.get("rows"), list) or not isinstance(block.get("counts"), dict):
        raise ValueError("referenceTransient results are malformed")
    return block


def _ref_worker(raw: Dict[str, Any], result_path: str) -> None:
    import lpbf_simulation
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            res = lpbf_simulation.run(raw)
        m = res["metrics"]
        out = {"status": "completed", "width_um": m["width_um"], "depth_um": m["depth_um"],
               "length_um": m["length_um"], "peakTemperature_K": m["peakTemperature_K"]}
    except ValueError as exc:
        msg = str(exc)
        out = {"status": "boiling-stop" if "boiling" in msg.lower() else "other-error", "message": msg[:400]}
    except Exception as exc:
        out = {"status": "other-error", "message": f"{type(exc).__name__}: {exc}"[:400]}
    Path(result_path).write_text(json.dumps(out), encoding="utf-8")


def reference_transient(rows: Sequence[Dict[str, Any]], budget_s: float, per_case_s: float = REF_PER_CASE_S) -> Dict[str, Any]:
    ctx = multiprocessing.get_context("spawn")
    started = time.perf_counter()
    out_rows = []
    for (P, v, d) in REF_SETS:
        meas = {}
        for L in LEVELS:
            sel = [r for r in rows if (r["power_W"], r["speed_mm_s"], r["beamDiameter_um"], r["layer_um"]) == (P, v, d, L)]
            meas[f"{L:g}"] = ({"rows": len(sel), "width_um": _mean([r["width_um"] for r in sel]),
                               "depth_um": _mean([r["depth_um"] for r in sel])} if sel else None)
        for L in REF_LAYERS_UM:
            left = budget_s - (time.perf_counter() - started)
            raw = reference_input("316L Stainless Steel", P, v, d, L)
            rec = {"power_W": P, "speed_mm_s": v, "beamDiameter_um": d, "layer_um": L, "measured": meas[f"{L:g}"]}
            if left <= 5.0:
                rec.update(status="not-run (budget)")
                out_rows.append(rec)
                continue
            result_path = Path(tempfile.mkdtemp(prefix="lpbf-powder-ref-")) / "result.json"
            p = ctx.Process(target=_ref_worker, args=(raw, str(result_path)))
            t0 = time.perf_counter()
            p.start()
            p.join(min(per_case_s, left))
            if p.is_alive():
                p.terminate()
                p.join()
                rec.update(status="not-run (budget)", message="case exceeded the per-case/total wall budget")
            else:
                try:
                    rec.update(json.loads(result_path.read_text(encoding="utf-8")))
                except Exception:
                    rec.update(status="other-error", message="no result returned")
            rec["wall_s"] = round(time.perf_counter() - t0, 1)
            shutil.rmtree(result_path.parent, ignore_errors=True)
            if rec.get("status") == "completed":
                rec["meshLimited"] = bool(rec["depth_um"] < 2.5 * REF_MESH_UM)
            out_rows.append(rec)
    counts = {"cases": len(out_rows)}
    for key, st in (("completed", "completed"), ("boilingStop", "boiling-stop"), ("otherError", "other-error")):
        counts[key] = sum(1 for x in out_rows if x["status"] == st)
    counts["notRun"] = sum(1 for x in out_rows if x["status"].startswith("not-run"))
    powder = [x for x in out_rows if x["layer_um"] > 0]
    return {
        "settings": reference_settings(budget_s, per_case_s),
        "selection": ("2 Hofmann parameter sets with P <= 100 W that have a bare-plate row and whose bare-plate "
                      "row completed (100 W, 900 mm/s, 80 um) or hit the boiling stop (50 W, 300 mm/s, 50 um, "
                      "three thickness levels in the data) in lpbf_dataset_comparison; x layer 0/30/60 um."),
        "counts": counts,
        "powderCasesCompleted": sum(1 for x in powder if x["status"] == "completed"),
        "rows": out_rows,
        "note": ("layer 0 differs from 30/60 not only by the powder layer but also by the surface mode and the "
                 "arbitrary bare-plate sourcePenetration_um; 20 um mesh is coarse: any completed case with depth "
                 "< 2.5 cells is meshLimited (cell-quantised). completed/boiling-stop is the reference "
                 "transient's own validity stop, not loosened; a boiling stop on powder is a finding about the "
                 "homogenised powder model, not a failure of this analysis. Not validation."),
    }


# ---------------------------------------------------------------------------------------------
# literature (pure formulas)
# ---------------------------------------------------------------------------------------------
def zehner_schlunder(porosity: float, k_gas: float, k_solid: float, shape_c: float = 1.25) -> float:
    """Zehner-Schlunder (1970) stagnant effective conductivity of a bed of monosized spheres, gas conduction
    only (no radiation, no contact conduction, no Smoluchowski effect), in the VDI Heat Atlas form:

        k_e/k_g = 1 - sqrt(1-e) + 2 sqrt(1-e)/N *
                  [ (1-1/kappa) B/N^2 ln(kappa/B) - (B+1)/2 - (B-1)/N ],
        kappa = k_s/k_g, N = 1 - B/kappa,
        B = C ((1-e)/e)^(10/9), C = 1.25 for spheres; e is porosity.

    The logarithmic term has N^2 in its denominator. Equivalently, for solid packing fraction
    p = 1-e, B = C (p/(1-p))^(10/9); p -> 1 is the solid limit and e -> 1 is the gas limit.

    Returns k_e in W/m/K. The tests check equal phase conductivities and both phase-fraction limits.
    """
    e = porosity
    kappa = k_solid / k_gas
    B = shape_c * ((1.0 - e) / e) ** (10.0 / 9.0)
    N = 1.0 - B / kappa
    bracket = ((1.0 - 1.0 / kappa) * B / (N * N)) * math.log(kappa / B) - (B + 1.0) / 2.0 - (B - 1.0) / N
    ratio = 1.0 - math.sqrt(1.0 - e) + (2.0 * math.sqrt(1.0 - e) / N) * bracket
    return ratio * k_gas


def literature_block() -> Dict[str, Any]:
    from four_alloy_materials import thermal_props
    k_s = float(thermal_props("316L Stainless Steel")["thermal_conductivity_W_mK"])
    k_g = 0.0177
    cases = []
    for packing in (0.55, 0.60):
        for ks_label, ks in (("repo estimated 316L k_solid (room-temperature value)", k_s),):
            ke = zehner_schlunder(1.0 - packing, k_g, ks)
            cases.append({"packing": packing, "porosity": round(1.0 - packing, 4), "k_gas_W_mK": k_g,
                          "k_solid_W_mK": ks, "k_solidSource": ks_label, "shapeFactorC": 1.25,
                          "B": round(1.25 * (packing / (1.0 - packing)) ** (10.0 / 9.0), 4),
                          "kappa": round(ks / k_g, 2), "k_eff_W_mK": round(ke, 4), "k_eff_over_k_solid": round(ke / ks, 5),
                          "ratioVsCode0p12": round((ke / ks) / CONDUCTIVITY_RATIO_CODE, 3)})
    sens = []
    for kg in (0.0177 * 0.75, 0.0177 * 1.25):
        ke = zehner_schlunder(1.0 - 0.55, kg, k_s)
        sens.append({"k_gas_W_mK": round(kg, 5), "k_eff_over_k_solid": round(ke / k_s, 5),
                     "note": "symmetric +/-25 % on k_gas, ILLUSTRATIVE sensitivity only, not an uncertainty"})
    return {
        "status": "PROPOSAL for a reviewed `literature`-tagged law; nothing in the model was changed",
        "codeValue": {"powderConductivityRatio": CONDUCTIVITY_RATIO_CODE, "packingFraction": PACKING_CODE,
                      "source": "none cited (lpbf_simulation.py DEFAULTS line 86; applied at line 575; bounds line 98)"},
        "laws": [
            {"name": "Zehner-Schlunder", "citation": "Zehner & Schlunder (1970), Chem. Ing. Tech. 42(14), 933-941",
             "equationSource": "VDI Heat Atlas form reproduced as Eq. 7 in Particle-Resolved Computational Fluid Dynamics as the Basis for Thermal Process Intensification of Fixed-Bed Reactors on Multiple Scales (2021), https://www.mdpi.com/1996-1073/14/10/2913",
             "form": "gas-conduction-only stagnant bed of spheres; published VDI Heat Atlas form with "
                     "kappa = k_solid/k_gas, N = 1 - B/kappa and the logarithmic term denominator N^2; "
                     "B = C ((1-porosity)/porosity)^(10/9), C = 1.25. The expression was independently "
                     "re-derived from its published form and checked against an independent oracle and limits.",
             "computed": True},
            {"name": "Sih & Barlow", "citation": "Sih & Barlow (2004), Particulate Sci. Technol. 22(3), 427-440",
             "form": "ZS-type bed model extended with radiation and a particle emissivity model, up to high temperature",
             "computed": False, "ratio": "unsourced",
             "reason": "formula not retrieved or verified in this run; no number is quoted"},
            {"name": "Yagi-Kunii", "citation": "Yagi & Kunii (1957), AIChE J. 3(3), 373-381",
             "form": "stagnant bed with gas, contact and radiation paths in series/parallel",
             "computed": False, "ratio": "unsourced",
             "reason": "needs void-structure constants (phi, beta, gamma) and radiation coefficients that were "
                       "not retrieved or verified in this run; no number is quoted"},
            {"name": "Gusarov et al.", "citation": "Gusarov, Laoui, Froyen, Titov (2003), Int. J. Heat Mass Transfer 46(6), 1103-1109",
             "form": "contact (neck) conductivity of a sintered/packed powder bed, gas conduction treated as "
                     "secondary at ambient pressure",
             "computed": False, "ratio": "unsourced",
             "reason": "the contact-conductivity expression and the neck-size input are not available here; the "
                       "page read in this run states the qualitative conclusion only; no number is quoted"},
        ],
        "zehnerSchlunderComputed": {
            "inputs": {"gas": "argon, 1 bar, about 300 K", "k_gas_W_mK": k_g,
                       "k_gasSource": "unsourced (handbook value recalled, not looked up in this run)",
                       "k_solid_W_mK": k_s,
                       "k_solidSource": "repo estimated 316L value (four_alloy_materials.thermal_props), not measured",
                       "radiation": "not included", "contactConduction": "not included",
                       "temperature": "about 300 K; the bed conductivity at melt-relevant temperature is unsourced"},
            "cases": cases, "k_gasSensitivity_packing_0p55": sens,
            "reading": ("The computed gas-conduction-only ratios are 0.01342-0.01653 (0.112-0.138 times the "
                        "uncited code value 0.12) for these two room-temperature inputs. Contact conduction and "
                        "radiation are excluded, so this calculation is not a complete packed-bed estimate and "
                        "does not establish the suitability of 0.12. These inputs are illustrative; the gas "
                        "conductivity is unsourced and the solid conductivity is a repository estimate.")},
        "measuredSnippet": {"source": "PMC7448231 (laser-flash inverse study of IN625 powder)",
                            "value": "powder conductivity 0.65-1.02 W/m/K reported for IN625 (other alloy; "
                                     "solid conductivity and conditions unsourced here, so no ratio is computed)"},
        "proposal": ("A later reviewed change may replace the uncited 0.12 by a `literature`-tagged "
                     "temperature-dependent law (Zehner-Schlunder/Sih-Barlow with radiation and contact terms "
                     "from their cited sources) and report the delta in the validity envelope; that needs the "
                     "unsourced inputs above to be sourced first. This record changes no code and no default."),
    }


# ---------------------------------------------------------------------------------------------
# document
# ---------------------------------------------------------------------------------------------
def _round(o: Any) -> Any:
    if isinstance(o, float):
        return None if not math.isfinite(o) else round(o, 5)
    if isinstance(o, dict):
        return {k: _round(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_round(v) for v in o]
    return o


def build_document(budget_s: float, skip_reference: bool, generated_at: str,
                   reuse_reference: Optional[Path] = None) -> Dict[str, Any]:
    pin_flat_plate()
    import lpbf_public_datasets as pd
    from lpbf_simulation import implementation_fingerprint
    h = pd.load_hofmann_316l()
    rows = h["rows"]
    set_regime = {}
    for r in rows:
        k = (r["power_W"], r["speed_mm_s"], r["beamDiameter_um"])
        if k not in set_regime:
            set_regime[k] = pd.classify_regime(r["material"], r["power_W"], r["speed_mm_s"], r["beamDiameter_um"],
                                               r["preheat_C"], 0)["label"]
    p = h["provenance"]
    doc: Dict[str, Any] = {
        "schema": SCHEMA, "generatedAt": generated_at, "implementationHash": implementation_fingerprint(),
        "honesty": {"experimentalValidation": False, "statement": HONESTY_STATEMENT},
        "datasets": [{"id": p["id"], "doi": p["doi"], "license": p["license"], "url": p["url"],
                      "sha256": p["fileSha256"], "rows": len(rows), "citation": p["citation"],
                      "notes": p["caveats"], "source": p["source"], "materialKey": p["material"]}],
        "matchedSets": analyse_matched_sets(rows, set_regime),
    }
    picked = [rows[i] for i in (0, 120, 260, 400, 600)]  # fixed spread over the table, mixed layers/spots
    doc["kernelSensitivity"] = kernel_sensitivity(picked)
    if reuse_reference is not None:
        try:
            src = json.loads(reuse_reference.read_bytes().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"reference record is not valid UTF-8 JSON: {exc}") from exc
        block = dict(validate_reused_reference(
            src, doc["implementationHash"], doc["datasets"][0]["sha256"], reference_settings(budget_s)))
        block["reusedFrom"] = {"file": reuse_reference.name, "schema": src["schema"],
                               "implementationHash": src["implementationHash"],
                               "datasetSha256": src["datasets"][0]["sha256"],
                               "settings": dict(block["settings"])}
        doc["referenceTransient"] = block
    elif skip_reference:
        doc["referenceTransient"] = {"status": "skipped (--skip-reference)"}
    else:
        doc["referenceTransient"] = reference_transient(rows, budget_s)
    doc["literature"] = literature_block()
    doc["limits"] = [
        "Replicates: 677 rows contain 623 distinct (P, v, d, t) cells; replicates are averaged per set and level, "
        "the scatter between replicates is not propagated separately.",
        "The spot-diameter definition of d_laser is unknown (1/e^2 assumed); 'spot' splits are by the stated value.",
        "Where along the track and at what steady-state criterion width/depth were measured is unknown; the depth "
        "reference surface (substrate vs powder surface) is also not stated, which matters for the powder-vs-bare depth difference.",
        "No uncertainty budget for the measurements: the bootstrap CI covers parameter-set sampling only, not "
        "measurement error or confounding.",
        "Single material (316L, one machine): nothing here transfers to other alloys.",
        "Balling-flagged rows are kept (their share per thickness level is reported); regime labels are an "
        "inputs-only screening classifier, not the paper's definition.",
        "The powder packing, particle size distribution and layer deposition of the measurements are not stated "
        "by Hofmann; a model packing of 0.55 is not a measured value.",
        "Thickness is not randomised within a set: differences between levels can include run-order, plate or "
        "re-coating effects, so the ratios are descriptive, not causal.",
        "The kernel sensitivity is a check of the code path (the layer argument is ignored), not of physics.",
        "The reference-transient block is bounded (<= 6 cases) at a coarse 20 um mesh; layer 0 uses a different "
        "surface mode and an arbitrary source penetration, so it is not a clean powder-on/off contrast.",
        "Literature: only the published Zehner-Schlunder gas-only form was computed; Sih-Barlow, "
        "Yagi-Kunii and Gusarov ratios are `unsourced`.",
    ]
    return _round(doc)


def _f(x: Any, nd: int = 2) -> str:
    return "n/a" if x is None else f"{x:.{nd}f}"


def _pair_row(label: str, s: Dict[str, Any]) -> str:
    if not s.get("nSets"):
        return f"| {label} | {s['pair']} | 0 | | | | | |"

    def cell(m: Dict[str, Any]) -> str:
        return f"{_f(m['median'])} [{_f(m['ci95'][0])}, {_f(m['ci95'][1])}]"
    low = " (low n)" if s["lowN"] else ""
    return (f"| {label} | {s['pair']} | {s['nSets']}{low} | {s['nRowsHigh']}/{s['nRowsLow']} | "
            f"{cell(s['widthRatio'])} | {cell(s['depthRatio'])} | "
            f"{_f(s['widthDiff_um']['median'], 1)} | {_f(s['depthDiff_um']['median'], 1)} |")


def render_markdown(doc: Dict[str, Any]) -> str:
    L: List[str] = []
    a = L.append
    a("# LPBF powder-layer model evidence (2026-10-05)")
    a("")
    a("**Analysis of published single-track measurements and of model sensitivity; not experimental validation; "
      "no fitted constants; estimated material laws.** Implementation fingerprint "
      f"`{doc['implementationHash']}`. Schema `{doc['schema']}`. Generated by "
      "`python/tools/lpbf_powder_layer_analysis.py`.")
    a("")
    ms = doc["matchedSets"]
    t = ms["datasetTotals"]
    a("## 1. Matched-set analysis (Hofmann 316L)")
    a("")
    a(f"{t['rows']} rows form {t['sets']} (P, v, d_laser) sets; {t['matchedSets']} have >= 2 thickness levels "
      f"and {t['setsWithAllThreeLevels']} have all three. {ms['statistic']}.")
    a("")
    a("Ratios are high/low powder thickness (cell: median [95 % cluster-bootstrap CI]). A ratio above 1 means "
      "the track measured wider/deeper with the thicker layer. Rows column: rows at high/low level.")
    a("")
    hdr = ("| split | pair | matched sets | rows | width ratio | depth ratio | width diff um (median) | depth diff um (median) |\n"
           "|---|---|---|---|---|---|---|---|")

    def table(title: str, blocks: Dict[str, Any]) -> None:
        a(f"### {title}")
        a("")
        a(hdr)
        for lab, b in blocks.items():
            for key in b["pairs"]:
                a(_pair_row(lab, b["pairs"][key]))
        a("")
    table("All matched sets", {"all": ms["all"]})
    table("By regime (inputs-only screening label)", ms["byRegime"])
    table("By spot size (um)", ms["bySpot_um"])
    a("### Balling-flagged fraction per thickness level")
    a("")
    a("| scope | 0 um | 30 um | 60 um |")
    a("|---|---|---|---|")

    def bf(d: Dict[str, Any]) -> str:
        return " | ".join(f"{d[k]['ballingFlagged']}/{d[k]['rows']} ({_f(100 * d[k]['fraction'], 1)} %)"
                          if d[k]["fraction"] is not None else "n/a" for k in ("0", "30", "60"))
    a(f"| all {t['rows']} rows | {bf(ms['ballingFractionByLevelAllRows'])} |")
    a(f"| rows in matched sets | {bf(ms['all']['ballingFractionByLevel'])} |")
    a("")
    a("## 2. Kernel sensitivity to the layer thickness")
    a("")
    ks = doc["kernelSensitivity"]
    a(f"{ks['method']}. {len(ks['cases'])} (row, kernel) cases, {ks['solverCalls']} solver calls; flat-plate "
      f"fallback warnings counted: {ks['fallbackWarnings']}. Max relative difference across layers: "
      f"**{ks['maxRelativeDifference']:g}** -> layer ignored by all three kernels: **{ks['layerIgnored']}**.")
    a("")
    a("## 3. Reference-transient sensitivity (bounded)")
    a("")
    rt = doc["referenceTransient"]
    if "rows" not in rt:
        a(str(rt.get("status")))
    else:
        c = rt["counts"]
        a(f"Cases {c['cases']}: completed {c['completed']}, boiling-stop {c['boilingStop']}, other-error "
          f"{c['otherError']}, not-run {c['notRun']}. Powder cases completed: {rt['powderCasesCompleted']}. "
          f"{rt['selection']}")
        a("")
        a("| P W | v mm/s | d um | layer um | status | width um | depth um | meshLimited | wall s | measured w/d um (mean) |")
        a("|---|---|---|---|---|---|---|---|---|---|")
        for r in rt["rows"]:
            m = r.get("measured")
            a(f"| {r['power_W']:g} | {r['speed_mm_s']:g} | {r['beamDiameter_um']:g} | {r['layer_um']:g} | "
              f"{r['status']} | {_f(r.get('width_um'), 1)} | {_f(r.get('depth_um'), 1)} | "
              f"{r.get('meshLimited', '')} | {r.get('wall_s', '')} | "
              f"{(_f(m['width_um'], 1) + ' / ' + _f(m['depth_um'], 1)) if m else 'no row'} |")
        a("")
        a(rt["note"])
    a("")
    lit = doc["literature"]
    a("## 4. Literature: effective conductivity of packed powder beds")
    a("")
    a(f"**{lit['status']}.** Current code: `powderConductivityRatio` = {lit['codeValue']['powderConductivityRatio']}, "
      f"`packingFraction` = {lit['codeValue']['packingFraction']}; source: {lit['codeValue']['source']}.")
    a("")
    for law in lit["laws"]:
        a(f"- **{law['name']}** - {law['citation']}. {law['form']}. "
          + (f"Equation source: {law['equationSource']}. " if law.get("equationSource") else "")
          + ("Computed below." if law["computed"] else f"Ratio: `{law['ratio']}` ({law['reason']})."))
    a("")
    z = lit["zehnerSchlunderComputed"]
    a(f"Zehner-Schlunder inputs: {z['inputs']['gas']}; k_gas = {z['inputs']['k_gas_W_mK']} W/m/K "
      f"({z['inputs']['k_gasSource']}); k_solid = {z['inputs']['k_solid_W_mK']} W/m/K ({z['inputs']['k_solidSource']}); "
      f"radiation: {z['inputs']['radiation']}; contact conduction: {z['inputs']['contactConduction']}.")
    a("")
    a("| packing | porosity | B | kappa | k_eff W/m/K | k_eff / k_solid | vs code 0.12 |")
    a("|---|---|---|---|---|---|---|")
    for c in z["cases"]:
        a(f"| {c['packing']} | {c['porosity']} | {c['B']} | {c['kappa']} | {c['k_eff_W_mK']} | "
          f"{c['k_eff_over_k_solid']} | x{c['ratioVsCode0p12']} |")
    a("")
    a("k_gas sensitivity at packing 0.55 (symmetric +/-25 %, illustrative only): "
      + "; ".join(f"k_gas {s['k_gas_W_mK']} -> {s['k_eff_over_k_solid']}" for s in z["k_gasSensitivity_packing_0p55"]) + ".")
    a("")
    a(z["reading"])
    a("")
    a(f"Measured snippet: {lit['measuredSnippet']['value']} ({lit['measuredSnippet']['source']}).")
    a("")
    a(lit["proposal"])
    a("")
    a("## Limits")
    a("")
    for x in doc["limits"]:
        a(f"- {x}")
    a("")
    a("## Provenance")
    a("")
    d = doc["datasets"][0]
    a(f"{d['citation']} DOI {d['doi']}, {d['license']}, table sha256 `{d['sha256']}`.")
    a("")
    return "\n".join(L)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--ref-budget-s", type=float, default=900.0)
    ap.add_argument("--skip-reference", action="store_true")
    ap.add_argument("--reuse-reference", default=None)
    ap.add_argument("--generated-at", default=GENERATED_AT_DEFAULT)
    a = ap.parse_args(argv)
    out = Path(a.out).resolve()
    if "golden" in out.parts:
        raise SystemExit("refusing to write under golden/")
    t0 = time.perf_counter()
    doc = build_document(a.ref_budget_s, a.skip_reference, a.generated_at,
                         Path(a.reuse_reference).resolve() if a.reuse_reference else None)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, sort_keys=True, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    out.with_suffix(".md").write_text(render_markdown(doc), encoding="utf-8", newline="\n")
    print(f"wrote {out} and .md in {time.perf_counter() - t0:.0f} s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
