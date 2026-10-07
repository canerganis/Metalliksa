#!/usr/bin/env python3
"""Held-out calibration of the Eagar-Tsai screening kernel's absorptivity against two public datasets.

HELD-OUT CALIBRATION, NOT EXPERIMENTAL VALIDATION. The Eagar-Tsai screening kernel of
``calculate_meltpool_physics`` (same entry point, CPU flat-plate absorption path and material laws as
python/tools/lpbf_dataset_comparison.py; the kernel itself is read-only) is evaluated on the Hofmann 2026
316L table (677 tracks) and the Totis/Vaglio 2021 Ti-6Al-4V table (80 tracks). ONE nuisance parameter,
the flat-plate absorptivity ``absorptivity_IR``, is fitted on a training split and the error is reported on
rows the fit never saw:

* grouped k-fold cross-validation per dataset (replicate rows of one (material, P, v, d) set never
  straddle train and test; fixed seeds), and
* leave-one-dataset-out: fit on Hofmann (316L), test on Totis (Ti-6Al-4V) and the reverse. That is a
  CROSS-MATERIAL transfer of a fitted 316L absorptivity to Ti-6Al-4V (and vice versa) and is labelled so.

Two calibrations are fitted: ``const`` (one absorptivity per training material) and ``regime`` (one per
input-only normalised-enthalpy class computed at the material's default absorptivity; the dataset's balling
flag is a measured outcome and is NOT used for class assignment). No second scalar is fitted. Both are
compared against the uncalibrated harness default and a physics-free power law W ~ P^a v^-b d^c fitted on
the same training fold. Absorptivity is a fitted nuisance parameter, not a measured quantity; the result is
at most 'Calibrated simulation' for the tested regime and ``experimentalValidation`` stays false.

The kernel is evaluated once per row on a fixed absorptivity grid (``--table-cache`` stores that table so
the statistics can be re-run without the kernel); every fit is a grid argmin, so the procedure is
deterministic and the offline test exercises it with a synthetic kernel.

Usage (from python/, PYTHONDONTWRITEBYTECODE=1):
    python -B tools/lpbf_calibration_heldout.py --out ../docs/LPBF_CALIBRATION_HELDOUT_2026-10-06.json \
        --table-cache <scratch>/et_grid_table.json --jobs 12
    python -B tools/lpbf_calibration_heldout.py --quick --out <json>   # first 40 rows of each dataset
Nothing is written under python/golden; the committed derived tables in data/benchmark/ are read.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import multiprocessing
import platform
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

PYTHON_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PYTHON_DIR))

SCHEMA = "lpbf-calibration-heldout-1"
KERNEL = "eagar-tsai"
GRID_START, GRID_STOP, GRID_STEP = 0.20, 0.90, 0.02
K_FOLDS = 5
CV_SEEDS = (0, 1, 2)
BOOT_REPLICATES = 1000
BOOT_SEED = 0
MIN_SETS_PER_CLASS = 8
MIN_COVERAGE = 0.98
DEFAULT_HATCH_UM = 100.0
NOMINAL_LAYER_FOR_BARE_UM = 30.0
GENERATED_AT_DEFAULT = "2026-10-06"
RAYTRACER_MODULE = "powder_bed_raytracer"
FALLBACK_WARNING_TEXT = "GPU Powder Bed Ray Tracing failed"
ENTHALPY_TRANSITION = 15.0
# legacy 15/30 kept for the preregistered v2 protocol; the solver regime uses 15/20 since the keyhole-regime bump
ENTHALPY_KEYHOLE = 30.0
CLASSES = ("conduction", "transition", "keyhole")
MODELS = ("default", "const", "regime", "powerlaw")
EVIDENCE_LABEL = ("Calibrated simulation (held-out calibration of one nuisance parameter against published "
                  "single-track data; tested regime only)")
HONESTY_STATEMENT = ("held-out calibration, not experimental validation; the Eagar-Tsai screening kernel is "
                     "read-only; absorptivity is a fitted nuisance parameter, not a measured one; estimated "
                     "material laws; published single-track measurements without an uncertainty model; a "
                     "calibration that does not beat the physics-free baseline is reported as such")
HEADER_MD = ("**Held-out calibration of the Eagar-Tsai screening kernel's absorptivity against published "
             "single-track measurements; not experimental validation; absorptivity fitted, not measured; "
             "estimated material laws.**")
LOSS_DEFINITION = ("per row 0.5 * (|ln(W_pred/W_meas)| + |ln(D_pred/D_meas)|); rows of one parameter set are "
                   "averaged first, then the mean over the training parameter sets is minimised on the "
                   "absorptivity grid (argmin, ties to the smaller value). A grid value is a candidate only when "
                   f"the kernel resolves an extent (extentStatus == 'computed') for at least {MIN_COVERAGE:.0%} "
                   "of the training rows.")
SPLIT_RULE = ("parameter set = (source, material, power_W, speed_mm_s, beamDiameter_um) (the shared key of lpbf_calibration_stats; "
              "identical to the earlier 4-field key inside one source); powder-layer thickness is "
              "deliberately NOT part of the key, so replicates and layer variants of one laser setting are "
              "always on the same side of a split. Folds: the sorted set keys are shuffled with "
              "random.Random(seed) and dealt round-robin into k folds.")


def absorptivity_grid(defaults: Sequence[float] = ()) -> List[float]:
    n = int(round((GRID_STOP - GRID_START) / GRID_STEP)) + 1
    vals = {round(GRID_START + i * GRID_STEP, 4) for i in range(n)}
    vals.update(round(float(d), 4) for d in defaults)
    return sorted(vals)


def a_key(a: float) -> str:
    return f"{a:.4f}"


# ---------------------------------------------------------------------------------------------
# rows and splits (pure)
# ---------------------------------------------------------------------------------------------
# The leakage rule (set_key / grouped_kfold / assert_no_leak), pin_flat_plate and the regime classes live in ONE place,
# python/lpbf_calibration_stats.py, so the held-out tool and the scorecard cannot drift apart.
from lpbf_calibration_stats import (  # noqa: E402,F401
    assert_no_leak, grouped_kfold, pin_flat_plate, regime_class_from_enthalpy, set_key)


# ---------------------------------------------------------------------------------------------
# kernel table
# ---------------------------------------------------------------------------------------------
def _predict(task: Dict[str, Any]) -> Dict[str, Any]:
    """Worker: one row at one absorptivity through the harness entry point (CPU, flat plate pinned)."""
    pin_flat_plate()
    from lpbf_thermal_solver import calculate_meltpool_physics
    row, a = task["row"], task["a"]
    layer = row["layer_um"] if row.get("layer_um") and row["layer_um"] > 0 else NOMINAL_LAYER_FOR_BARE_UM
    captured = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured):
            res = calculate_meltpool_physics(
                row["material"], row["power_W"], row["speed_mm_s"], row["beamDiameter_um"],
                row["preheat_C"], layer, row.get("hatch_um") or DEFAULT_HATCH_UM,
                heat_source=KERNEL, prop_overrides={"absorptivity_IR": a}, absorption_model="flat-plate")
        g = res["meltPoolGeometry"]
        status = g.get("extentStatus")
        return {"width_um": round(float(g["width_um"]), 3), "depth_um": round(float(g["depth_um"]), 3),
                "extentStatus": status, "included": status == "computed",
                "flatPlateCalls": int(res["processParameters"].get("absorptionModel") == "flat-plate")}
    except Exception as exc:  # recorded as data
        return {"width_um": None, "depth_um": None, "extentStatus": f"error: {type(exc).__name__}",
                "included": False, "flatPlateCalls": 0}


def build_table(rows: Sequence[Dict[str, Any]], grid: Sequence[float], jobs: int = 1,
                kernel: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None) -> Dict[str, Any]:
    """{'grid': [...], 'predictions': {a_key: {rowId: {width_um, depth_um, included, extentStatus}}}, ...}.

    kernel(task) with task = {'row': row, 'a': a} may be injected (offline tests); default = the solver worker.
    """
    tasks = [{"row": r, "a": a} for a in grid for r in rows]
    if kernel is not None or jobs <= 1:
        fn = kernel or _predict
        preds = [fn(t) for t in tasks]
    else:
        ctx = multiprocessing.get_context("spawn")
        with ctx.Pool(jobs) as pool:
            preds = pool.map(_predict, tasks, chunksize=16)
    table: Dict[str, Dict[str, Any]] = {a_key(a): {} for a in grid}
    warnings = 0
    for t, p in zip(tasks, preds):
        warnings += int(p.pop("flatPlateCalls", 0) or 0)
        table[a_key(t["a"])][t["row"]["rowId"]] = p
    return {"grid": list(grid), "predictions": table, "solverCalls": len(tasks), "flatPlateCalls": warnings}


# ---------------------------------------------------------------------------------------------
# fitting (pure table lookups)
# ---------------------------------------------------------------------------------------------
def _row_loss(pred: Dict[str, Any], row: Dict[str, Any]) -> Optional[float]:
    if not pred.get("included") or pred.get("width_um") in (None, 0) or pred.get("depth_um") in (None, 0):
        return None
    return 0.5 * (abs(math.log(pred["width_um"] / row["width_um"])) + abs(math.log(pred["depth_um"] / row["depth_um"])))


def _grid_loss(train: Sequence[Dict[str, Any]], table: Dict[str, Any], a: float) -> Tuple[Optional[float], float]:
    """(mean loss over parameter sets, coverage of training rows); loss None when coverage is too low."""
    preds = table["predictions"][a_key(a)]
    per_set: Dict[tuple, list] = {}
    n_ok = 0
    for r in train:
        loss = _row_loss(preds[r["rowId"]], r)
        if loss is None:
            continue
        n_ok += 1
        per_set.setdefault(set_key(r), []).append(loss)
    coverage = n_ok / len(train) if train else 0.0
    if not per_set or coverage < MIN_COVERAGE:
        return None, coverage
    return sum(sum(v) / len(v) for v in per_set.values()) / len(per_set), coverage


def fit_constant(train: Sequence[Dict[str, Any]], table: Dict[str, Any]) -> Dict[str, Any]:
    grid = table["grid"]
    curve = {}
    best = None
    for a in grid:
        loss, cov = _grid_loss(train, table, a)
        curve[a_key(a)] = {"loss": loss, "coverage": cov}
        if loss is not None and (best is None or loss < best[1]):
            best = (a, loss)
    if best is None:  # no candidate reached the coverage floor: take the best-covered value, flagged
        a = max(grid, key=lambda x: curve[a_key(x)]["coverage"])
        return {"a": a, "trainLoss": None, "coverage": curve[a_key(a)]["coverage"], "atGridEdge": True,
                "nTrainRows": len(train), "nTrainSets": len({set_key(r) for r in train}),
                "note": "no grid value reached the coverage floor; absorptivity set to the best-covered value",
                "lossCurve": curve}
    a = best[0]
    return {"a": a, "trainLoss": best[1], "coverage": curve[a_key(a)]["coverage"],
            "atGridEdge": a in (grid[0], grid[-1]), "nTrainRows": len(train),
            "nTrainSets": len({set_key(r) for r in train}), "lossCurve": curve}


def fit_regime(train: Sequence[Dict[str, Any]], table: Dict[str, Any], min_sets: int = MIN_SETS_PER_CLASS) -> Dict[str, Any]:
    """One absorptivity per enthalpy class; a class with fewer than min_sets training sets inherits the constant fit."""
    const = fit_constant(train, table)
    out: Dict[str, Any] = {"fallbackConst": {k: v for k, v in const.items() if k != "lossCurve"}, "classes": {}}
    for c in CLASSES:
        sub = [r for r in train if r["regimeClass"] == c]
        n_sets = len({set_key(r) for r in sub})
        if n_sets < min_sets:
            out["classes"][c] = {"a": const["a"], "trainLoss": None, "coverage": None, "atGridEdge": const["atGridEdge"],
                                 "nTrainRows": len(sub), "nTrainSets": n_sets, "fellBackToConst": True}
            continue
        fit = fit_constant(sub, table)
        fit.pop("lossCurve", None)
        fit["fellBackToConst"] = False
        out["classes"][c] = fit
    return out


def _solve(A: List[List[float]], b: List[float]) -> List[float]:
    """Gaussian elimination with partial pivoting (small dense systems)."""
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[piv][col]) < 1e-12:
            raise ValueError("singular normal equations")
        M[col], M[piv] = M[piv], M[col]
        for r in range(n):
            if r != col:
                f = M[r][col] / M[col][col]
                for c in range(col, n + 1):
                    M[r][c] -= f * M[col][c]
    return [M[i][n] / M[i][i] for i in range(n)]


POWERLAW_FEATURES = ("power_W", "speed_mm_s", "beamDiameter_um")


def fit_power_law(train: Sequence[Dict[str, Any]], field: str) -> Dict[str, Any]:
    """Least squares of ln(field) on ln P, ln v, ln d (features constant in the training fold are dropped).
    Rows of one parameter set are averaged first so a replicate-rich set does not dominate the fit."""
    per_set: Dict[tuple, list] = {}
    for r in train:
        per_set.setdefault(set_key(r), []).append(math.log(r[field]))
    keys = sorted(per_set)
    y = [sum(per_set[k]) / len(per_set[k]) for k in keys]
    rows = [dict(zip(("source", "material", "power_W", "speed_mm_s", "beamDiameter_um"), k)) for k in keys]
    used = [f for f in POWERLAW_FEATURES if len({r[f] for r in rows}) > 1]
    X = [[1.0] + [math.log(r[f]) for f in used] for r in rows]
    p = len(X[0])
    AtA = [[sum(X[i][j] * X[i][l] for i in range(len(X))) for l in range(p)] for j in range(p)]
    Atb = [sum(X[i][j] * y[i] for i in range(len(X))) for j in range(p)]
    coef = _solve(AtA, Atb)
    out = {"intercept": coef[0], "exponents": {f: coef[1 + i] for i, f in enumerate(used)},
           "droppedConstantFeatures": [f for f in POWERLAW_FEATURES if f not in used], "nTrainSets": len(keys)}
    out["note"] = (f"ln {field} = c + sum(e_f ln f); {len(keys)} training sets, replicate rows averaged per set; "
                   "no material term and no physics: this is the trivial baseline.")
    return out


def predict_power_law(model: Dict[str, Any], row: Dict[str, Any]) -> float:
    v = model["intercept"] + sum(e * math.log(row[f]) for f, e in model["exponents"].items())
    return math.exp(v)


# ---------------------------------------------------------------------------------------------
# prediction and metrics
# ---------------------------------------------------------------------------------------------
def predict_rows(test: Sequence[Dict[str, Any]], model: str, fit: Any, table: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for r in test:
        if model == "powerlaw":
            p = {"width_um": predict_power_law(fit["width"], r), "depth_um": predict_power_law(fit["depth"], r),
                 "included": True, "a": None}
        else:
            if model == "default":
                a = r["defaultAbsorptivity"]
            elif model == "const":
                a = fit["a"]
            else:
                a = fit["classes"][r["regimeClass"]]["a"]
            src = table["predictions"][a_key(a)][r["rowId"]]
            p = {"width_um": src["width_um"], "depth_um": src["depth_um"], "included": bool(src["included"]), "a": a}
        p["rowId"] = r["rowId"]
        out.append(p)
    return out


def _agg(preds: Sequence[Dict[str, Any]], rows_by_id: Dict[str, Dict[str, Any]]) -> Dict[tuple, list]:
    """per set: [n, sumAbsErrW, sumAbsRelW, sumRelW, sumSqW, sumAbsErrD, sumAbsRelD, sumRelD, sumSqD]."""
    agg: Dict[tuple, list] = {}
    for p in preds:
        r = rows_by_id[p["rowId"]]
        c = agg.setdefault(set_key(r), [0] + [0.0] * 8)
        c[0] += 1
        for off, (pv, mv) in ((1, (p["width_um"], r["width_um"])), (5, (p["depth_um"], r["depth_um"]))):
            e = pv - mv
            c[off] += abs(e)
            c[off + 1] += abs(e) / mv
            c[off + 2] += e / mv
            c[off + 3] += e * e
    return agg


def _stats_from_cells(cells: Sequence[list]) -> Dict[str, Any]:
    n = sum(c[0] for c in cells)
    if n == 0:
        return {"width": None, "depth": None}
    out = {}
    for name, off in (("width", 1), ("depth", 5)):
        out[name] = {"mae_um": sum(c[off] for c in cells) / n,
                     "mape_pct": 100.0 * sum(c[off + 1] for c in cells) / n,
                     "bias_pct": 100.0 * sum(c[off + 2] for c in cells) / n,
                     "rmse_um": math.sqrt(sum(c[off + 3] for c in cells) / n)}
    return out


def _percentile(sorted_vals: Sequence[float], q: float) -> float:
    pos = (len(sorted_vals) - 1) * q / 100.0
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def _ci(vals: List[float]) -> Optional[List[float]]:
    if not vals:  # every paired skill draw undefined (baseline error exactly 0): no interval, not a crash
        return None
    vals.sort()
    return [_percentile(vals, 2.5), _percentile(vals, 97.5)]


def skill(model_val: float, base_val: float) -> Optional[float]:
    return None if base_val <= 0 else 1.0 - model_val / base_val


def evaluate(test: Sequence[Dict[str, Any]], preds_by_model: Dict[str, List[Dict[str, Any]]],
             replicates: int = BOOT_REPLICATES, seed: int = BOOT_SEED,
             baselines: Sequence[str] = ("default", "powerlaw")) -> Dict[str, Any]:
    """Held-out metrics per model on the rows every compared model resolves, with a cluster bootstrap by
    parameter set (same draws for every model -> paired skill intervals)."""
    rows_by_id = {r["rowId"]: r for r in test}
    ids = [r["rowId"] for r in test]
    by_id = {m: {p["rowId"]: p for p in preds} for m, preds in preds_by_model.items()}
    ok = {i for i in ids if all(i in by_id[m] and by_id[m][i]["included"] for m in by_id)}
    included = [i for i in ids if i in ok]
    aggs = {m: _agg([p for p in preds if p["rowId"] in ok], rows_by_id) for m, preds in preds_by_model.items()}
    keys = sorted({set_key(rows_by_id[i]) for i in included})
    out: Dict[str, Any] = {"n": len(included), "nExcluded": len(ids) - len(included), "n_parameterSets": len(keys),
                           "models": {}}
    for m in preds_by_model:
        st = _stats_from_cells([aggs[m][k] for k in keys]) if keys else {"width": None, "depth": None}
        out["models"][m] = st
        for b in baselines:
            if b in preds_by_model and b != m and st["width"]:
                bst = _stats_from_cells([aggs[b][k] for k in keys])
                st[f"skillVs_{b}"] = {q: {"mape": skill(st[q]["mape_pct"], bst[q]["mape_pct"]),
                                          "mae": skill(st[q]["mae_um"], bst[q]["mae_um"])} for q in ("width", "depth")}
    if not keys or replicates <= 0:
        return out
    rng = random.Random(seed)
    boot: Dict[str, Dict[str, Dict[str, list]]] = {m: {q: {"bias_pct": [], "mae_um": [], "mape_pct": []} for q in ("width", "depth")}
                                                   for m in preds_by_model}
    sboot: Dict[str, Dict[str, Dict[str, Dict[str, list]]]] = {m: {b: {q: {"mape": [], "mae": []} for q in ("width", "depth")}
                                                                   for b in baselines if b in preds_by_model and b != m}
                                                               for m in preds_by_model}
    k = len(keys)
    for _ in range(replicates):
        draw = [keys[i] for i in rng.choices(range(k), k=k)]
        st = {m: _stats_from_cells([aggs[m][key] for key in draw]) for m in preds_by_model}
        for m in preds_by_model:
            for q in ("width", "depth"):
                for name in ("bias_pct", "mae_um", "mape_pct"):
                    boot[m][q][name].append(st[m][q][name])
                for b in sboot[m]:
                    sboot[m][b][q]["mape"].append(skill(st[m][q]["mape_pct"], st[b][q]["mape_pct"]))
                    sboot[m][b][q]["mae"].append(skill(st[m][q]["mae_um"], st[b][q]["mae_um"]))
    for m in preds_by_model:
        for q in ("width", "depth"):
            for name, vals in boot[m][q].items():
                out["models"][m][q][f"{name}_ci95"] = _ci(vals)
            for b in sboot[m]:
                for name, vals in sboot[m][b][q].items():
                    out["models"][m][f"skillVs_{b}"][q][f"{name}_ci95"] = _ci([v for v in vals if v is not None])
    out["bootstrap"] = {"replicates": replicates, "seed": seed, "unit": "parameter set (cluster)",
                        "note": "same resamples for every model, so the skill intervals are paired"}
    return out


def breakdown_by_label(test: Sequence[Dict[str, Any]], preds_by_model: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Point metrics per harness regime label (incl. balling-flagged), no bootstrap."""
    out = {}
    for label in sorted({r["regimeLabel"] for r in test}):
        sub = [r for r in test if r["regimeLabel"] == label]
        ids = {r["rowId"] for r in sub}
        ev = evaluate(sub, {m: [p for p in preds if p["rowId"] in ids] for m, preds in preds_by_model.items()},
                      replicates=0)
        out[label] = ev
    return out


# ---------------------------------------------------------------------------------------------
# evaluations
# ---------------------------------------------------------------------------------------------
def fit_all(train: Sequence[Dict[str, Any]], table: Dict[str, Any]) -> Dict[str, Any]:
    const = fit_constant(train, table)
    return {"const": const, "regime": fit_regime(train, table),
            "powerlaw": {"width": fit_power_law(train, "width_um"), "depth": fit_power_law(train, "depth_um")}}


def _fit_summary(fits: Dict[str, Any]) -> Dict[str, Any]:
    c = {k: v for k, v in fits["const"].items() if k != "lossCurve"}
    return {"const": c, "regime": fits["regime"], "powerlaw": fits["powerlaw"]}


def run_cv(rows: Sequence[Dict[str, Any]], table: Dict[str, Any], k: int = K_FOLDS,
           seeds: Sequence[int] = CV_SEEDS, replicates: int = BOOT_REPLICATES) -> Dict[str, Any]:
    """Grouped k-fold CV on one dataset; out-of-fold predictions pooled, then scored once per seed."""
    out: Dict[str, Any] = {"k": k, "seeds": list(seeds), "bySeed": {}}
    for seed in seeds:
        folds = grouped_kfold(rows, k, seed)
        oof: Dict[str, List[Dict[str, Any]]] = {m: [] for m in MODELS}
        fold_recs = []
        for i, (train, test) in enumerate(folds):
            assert_no_leak(train, test)
            fits = fit_all(train, table)
            for m in MODELS:
                oof[m].extend(predict_rows(test, m, fits.get(m), table))
            fold_recs.append({"fold": i, "nTrainRows": len(train), "nTestRows": len(test),
                              "nTrainSets": len({set_key(r) for r in train}),
                              "nTestSets": len({set_key(r) for r in test}), "fits": _fit_summary(fits)})
        primary = seed == seeds[0]
        ev = evaluate(rows, oof, replicates=replicates if primary else 0)
        rec = {"folds": fold_recs, "heldOut": ev, "primary": primary}
        if primary:
            rec["byRegimeLabel"] = breakdown_by_label(rows, oof)
            rec["outOfFoldPredictions"] = {m: [{k2: v for k2, v in p.items()} for p in preds] for m, preds in oof.items()}
        out["bySeed"][str(seed)] = rec
    return out


def run_lodo(a_rows: Sequence[Dict[str, Any]], b_rows: Sequence[Dict[str, Any]], table: Dict[str, Any],
             replicates: int = BOOT_REPLICATES) -> Dict[str, Any]:
    assert_no_leak(a_rows, b_rows)
    out = {}
    for train, test in ((a_rows, b_rows), (b_rows, a_rows)):
        fits = fit_all(train, table)
        preds = {m: predict_rows(test, m, fits.get(m), table) for m in MODELS}
        tr_ds, te_ds = train[0]["dataset"], test[0]["dataset"]
        out[f"train={tr_ds};test={te_ds}"] = {
            "trainDataset": tr_ds, "testDataset": te_ds, "trainMaterial": train[0]["material"],
            "testMaterial": test[0]["material"],
            "crossMaterial": train[0]["material"] != test[0]["material"],
            "note": (f"absorptivity fitted on {train[0]['material']} ({tr_ds}) and applied to "
                     f"{test[0]['material']} ({te_ds}): a cross-material transfer of a nuisance parameter; "
                     "the power-law baseline is likewise fitted on one material and applied to the other"),
            "fits": _fit_summary(fits), "heldOut": evaluate(test, preds, replicates=replicates),
            "byRegimeLabel": breakdown_by_label(test, preds),
            "predictions": preds}
    return out


def run_in_sample(rows: Sequence[Dict[str, Any]], table: Dict[str, Any]) -> Dict[str, Any]:
    """Fit and score on the same rows: OPTIMISTIC reference, reported only to show the held-out gap."""
    fits = fit_all(rows, table)
    preds = {m: predict_rows(rows, m, fits.get(m), table) for m in MODELS}
    return {"fits": _fit_summary(fits), "inSample": evaluate(rows, preds, replicates=0),
            "note": "fit and score on the same rows; optimistic by construction; not a held-out result"}


def verdicts(ev: Dict[str, Any]) -> Dict[str, Any]:
    """'beats' / 'does not beat' / 'inconclusive' from the paired skill CI sign, per model x baseline x quantity."""
    out = {}
    for m, st in ev["models"].items():
        for key, sk in st.items():
            if not key.startswith("skillVs_"):
                continue
            for q in ("width", "depth"):
                ci = sk[q].get("mape_ci95")
                if ci is None:
                    v = "not bootstrapped"
                elif ci[0] > 0:
                    v = "beats"
                elif ci[1] < 0:
                    v = "does not beat"
                else:
                    v = "inconclusive"
                out[f"{m} vs {key[8:]} ({q})"] = {"skill_mape": sk[q]["mape"], "ci95": ci, "verdict": v}
    return out


# ---------------------------------------------------------------------------------------------
# data and document
# ---------------------------------------------------------------------------------------------
def load_rows(quick: bool = False) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    import lpbf_public_datasets as pd
    from four_alloy_materials import thermal_props

    h = pd.load_hofmann_316l()
    t = pd.load_totis_ti64()
    rows_h = h["rows"][:40] if quick else h["rows"]
    rows_t = t["rows"][:40] if quick else t["rows"]
    for r in rows_h + rows_t:
        reg = pd.classify_regime(r["material"], r["power_W"], r["speed_mm_s"], r["beamDiameter_um"], r["preheat_C"], r["balling"])
        r["normalizedEnthalpyDefault"] = reg["normalizedEnthalpy"]
        r["regimeLabel"] = reg["label"]  # harness label, uses the measured balling flag: reporting only
        r["regimeClass"] = regime_class_from_enthalpy(reg["normalizedEnthalpy"])  # input-only: used for fitting
        r["defaultAbsorptivity"] = float(thermal_props(r["material"])["absorptivity_IR"])
    meta = {"datasets": [{"id": p["id"], "doi": p["doi"], "license": p["license"], "url": p["url"],
                          "tableSha256": p["fileSha256"], "rows": n, "material": p["material"], "citation": p["citation"]}
                         for p, n in ((h["provenance"], len(rows_h)), (t["provenance"], len(rows_t)))],
            "regimeRule": pd.REGIME_RULE}
    return rows_h, rows_t, meta


def _git(args: List[str]) -> Optional[str]:
    try:
        res = subprocess.run(["git"] + args, capture_output=True, text=True, cwd=str(PYTHON_DIR), timeout=30)
        return res.stdout.strip() if res.returncode == 0 else None
    except Exception:
        return None


def code_revision() -> Dict[str, Any]:
    status = _git(["status", "--porcelain", "--", "python", "docs", "data"])
    return {"gitHead": _git(["rev-parse", "HEAD"]), "gitBranch": _git(["rev-parse", "--abbrev-ref", "HEAD"]),
            "dirtyTrackedPaths": None if status is None else [ln for ln in status.splitlines() if ln.strip()],
            "python": platform.python_version(), "executable": sys.executable}


def _round(o: Any) -> Any:
    if isinstance(o, float):
        return None if not math.isfinite(o) else round(o, 5)
    if isinstance(o, dict):
        return {k: _round(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_round(v) for v in o]
    return o


def what_this_does_not_show(rows_h: Sequence[Dict[str, Any]], rows_t: Sequence[Dict[str, Any]]) -> List[str]:
    n_ball = sum(1 for r in rows_h if r["regimeLabel"] == "balling-flagged")
    return [
        "It is not experimental validation and it does not establish the kernel as a general model of melt-pool "
        "geometry: one nuisance parameter was fitted to published cross-section measurements and the error on rows "
        "the fit did not see is reported. The evidence label is at most 'Calibrated simulation' for the tested regime; "
        "experimentalValidation stays false.",
        "There is no uncertainty model for the measurements: neither dataset gives per-row measurement uncertainty, "
        "sectioning position or replicate scatter (Totis has one track per cell). The bootstrap intervals cover "
        "resampling of parameter sets only, not measurement error, the estimated material laws or the regime rule.",
        "Absorptivity is a fitted nuisance parameter, not a measured one. The fitted value absorbs every other model "
        "error (material laws, the Fabbro keyhole term, the flat-plate path, the assumed 1/e^2 spot definition, the "
        "20 C preheat assumption) and must not be read as the physical absorptivity of 316L or Ti-6Al-4V.",
        "Conduction and keyhole regimes are mixed: the 'regime' calibration assigns classes from an input-only "
        "normalised-enthalpy screen at the default absorptivity, not from the papers' regime definitions; the "
        f"{n_ball} balling-flagged Hofmann rows stay inside the headline numbers (the flag is a measured outcome and "
        "is not used for fitting); the Totis depth reference line is not stated by the source.",
        f"The datasets are small: {len(rows_h)} Hofmann rows ({len({set_key(r) for r in rows_h})} distinct "
        f"(P, v, d) sets) and {len(rows_t)} Totis rows; a 5-fold split leaves one fifth of each for testing, and "
        "the leave-one-dataset-out transfer rests on a single pair of datasets.",
        "Laser, powder, atmosphere and machine differ between the datasets (Aconity Midi, bare plate and 30/60 um "
        "316L powder layers vs Concept Laser M2, 25 um Ti-6Al-4V layer over a printed base); the kernel ignores the "
        "powder layer entirely, and a cross-material transfer of a fitted absorptivity has no physical justification. "
        "It is reported because it is the only out-of-distribution test available here.",
        "The grid search is bounded (absorptivity 0.20 to 0.90); a fit at the grid edge is flagged, not extrapolated.",
        "The kernel's own inclusion rule (extentStatus == 'computed') selects the scored rows; rows any compared model "
        "does not resolve are excluded and counted, not estimated.",
    ]


def build_document(quick: bool, jobs: int, generated_at: str, table_cache: Optional[Path] = None,
                   replicates: int = BOOT_REPLICATES) -> Dict[str, Any]:
    pin_flat_plate()
    from lpbf_simulation import implementation_fingerprint

    fp = implementation_fingerprint()
    rows_h, rows_t, meta = load_rows(quick)
    rows = rows_h + rows_t
    grid = absorptivity_grid({r["defaultAbsorptivity"] for r in rows})
    t0 = time.perf_counter()
    table = None
    table_source = "computed"
    if table_cache and table_cache.is_file():
        cand = json.loads(table_cache.read_text(encoding="utf-8"))
        same = (cand.get("implementationHash") == fp and cand.get("grid") == grid
                and set(cand["predictions"][a_key(grid[0])]) >= {r["rowId"] for r in rows})
        if same:
            table = cand
            table_source = f"cache {table_cache.name}"
    if table is None:
        table = build_table(rows, grid, jobs)
        table["implementationHash"] = fp
        table["kernel"] = KERNEL
        if table_cache:
            table_cache.parent.mkdir(parents=True, exist_ok=True)
            table_cache.write_text(json.dumps(table, sort_keys=True), encoding="utf-8")
    table_s = time.perf_counter() - t0
    return assemble_document(rows_h, rows_t, meta, table, fp, generated_at, quick, replicates,
                             table_source=table_source, table_seconds=table_s, revision=code_revision())


def assemble_document(rows_h: Sequence[Dict[str, Any]], rows_t: Sequence[Dict[str, Any]], meta: Dict[str, Any],
                      table: Dict[str, Any], fp: str, generated_at: str, quick: bool, replicates: int,
                      table_source: str = "computed", table_seconds: float = 0.0,
                      revision: Optional[Dict[str, Any]] = None, seeds: Sequence[int] = CV_SEEDS) -> Dict[str, Any]:
    """Pure assembly from classified rows and a kernel table (no dataset or solver access)."""
    rows = list(rows_h) + list(rows_t)
    ds_h, ds_t = rows_h[0]["dataset"], rows_t[0]["dataset"]
    cv = {ds_h: run_cv(rows_h, table, seeds=seeds, replicates=replicates),
          ds_t: run_cv(rows_t, table, seeds=seeds, replicates=replicates)}
    lodo = run_lodo(rows_h, rows_t, table, replicates=replicates)
    in_sample = {ds_h: run_in_sample(rows_h, table), ds_t: run_in_sample(rows_t, table)}
    verdict = {"cv": {ds: verdicts(cv[ds]["bySeed"][str(seeds[0])]["heldOut"]) for ds in cv},
               "lodo": {k: verdicts(v["heldOut"]) for k, v in lodo.items()}}
    n_sets_with_layer = len({(r["dataset"], r["power_W"], r["speed_mm_s"], r["beamDiameter_um"], r["layer_um"]) for r in rows_h})
    doc = {
        "schema": SCHEMA, "generatedAt": generated_at, "quick": bool(quick),
        "implementationHash": fp, "codeRevision": revision or {},
        "kernel": {"name": KERNEL, "entryPoint": "lpbf_thermal_solver.calculate_meltpool_physics(heat_source='eagar-tsai')",
                   "absorptionPath": "flat-plate (absorption_model='flat-plate'; sys.modules['powder_bed_raytracer'] = None as well)",
                   "variedParameter": "prop_overrides={'absorptivity_IR': a}; nothing else is changed",
                   "secondScalar": "none fitted (the regime variant is a class-wise absorptivity, not a second physical parameter)",
                   "flatPlateCalls": table.get("flatPlateCalls", table.get("fallbackWarnings")), "solverCalls": table.get("solverCalls"),
                   "tableSource": table_source, "tableSeconds": round(table_seconds, 1)},
        "datasets": meta["datasets"], "regimeRule": meta["regimeRule"],
        "assumptions": {"hatch_um": DEFAULT_HATCH_UM, "layerForBarePlate_um": NOMINAL_LAYER_FOR_BARE_UM,
                        "preheat_C": "20 C assumed (not given by either dataset)",
                        "regimeClassForFitting": "input-only normalised enthalpy at the material default absorptivity, "
                                                 "thresholds 15/30; the balling flag is NOT used",
                        "defaultAbsorptivity": {m: a for m, a in sorted({(r["material"], r["defaultAbsorptivity"]) for r in rows})}},
        "protocol": {"grid": list(table["grid"]), "lossDefinition": LOSS_DEFINITION, "splitRule": SPLIT_RULE,
                     "kFolds": K_FOLDS, "cvSeeds": list(seeds), "bootstrap": {"replicates": replicates, "seed": BOOT_SEED},
                     "minSetsPerClass": MIN_SETS_PER_CLASS, "minCoverage": MIN_COVERAGE,
                     "models": {"default": "uncalibrated harness absorptivity ("
                                           + ", ".join(f"{m} {a}" for m, a in sorted({(r["material"], r["defaultAbsorptivity"]) for r in rows}))
                                           + "); no fitting",
                                "const": "one absorptivity per training fold (grid argmin of the loss)",
                                "regime": "one absorptivity per input-only enthalpy class; a class with fewer than "
                                          f"{MIN_SETS_PER_CLASS} training sets inherits the const value",
                                "powerlaw": "ln W (and ln D) = c + a ln P + b ln v + e ln d fitted on the training fold; no physics"},
                     "skill": "1 - metric(model)/metric(baseline) on the same held-out rows; paired cluster-bootstrap CI; "
                              "verdict 'beats' only when the whole 95 % interval is above 0"},
        "counts": {"hofmannRows": len(rows_h), "hofmannSets_P_v_d": len({set_key(r) for r in rows_h}),
                   "hofmannSets_P_v_d_layer": n_sets_with_layer, "totisRows": len(rows_t),
                   "totisSets_P_v_d": len({set_key(r) for r in rows_t}),
                   "rowsByRegimeClass": {c: sum(1 for r in rows if r["regimeClass"] == c) for c in CLASSES},
                   "rowsByRegimeLabel": {lab: sum(1 for r in rows if r["regimeLabel"] == lab) for lab in sorted({r["regimeLabel"] for r in rows})}},
        "crossValidation": cv, "leaveOneDatasetOut": lodo, "inSampleReference": in_sample, "verdicts": verdict,
        "whatThisDoesNotShow": what_this_does_not_show(rows_h, rows_t),
        "evidence": {"label": EVIDENCE_LABEL, "experimentalValidation": False, "opticalOperatorMatched": False,
                     "measuredVsEstimated": "measured: dataset widths/depths; fitted: absorptivity (nuisance); "
                                            "estimated: all material laws; computed: kernel outputs",
                     "statement": HONESTY_STATEMENT},
    }
    return _round(doc)


# ---------------------------------------------------------------------------------------------
# markdown
# ---------------------------------------------------------------------------------------------
def _f(x: Any, d: int = 1) -> str:
    return "-" if x is None else f"{x:.{d}f}"


def _cistr(ci: Any, d: int = 1) -> str:
    return "" if not ci else f" [{ci[0]:.{d}f}, {ci[1]:.{d}f}]"


def _model_table(ev: Dict[str, Any]) -> List[str]:
    L = [f"n = {ev['n']} held-out rows ({ev['n_parameterSets']} parameter sets), {ev['nExcluded']} excluded "
         "(not resolved by every compared model). Bias = mean((pred-meas)/meas); MAE in um; 95 % intervals = cluster "
         "bootstrap by parameter set.", "",
         "| model | W bias % | W MAE um | W MAPE % | D bias % | D MAE um | D MAPE % | W skill vs default / powerlaw | D skill vs default / powerlaw |",
         "|---|---|---|---|---|---|---|---|---|"]
    for m in MODELS:
        st = ev["models"].get(m)
        if not st or not st.get("width"):
            L.append(f"| {m} | - | - | - | - | - | - | - | - |")
            continue
        w, d = st["width"], st["depth"]

        def sk(q):
            parts = []
            for b in ("default", "powerlaw"):
                s = st.get(f"skillVs_{b}")
                parts.append("-" if not s else f"{s[q]['mape']:+.2f}{_cistr(s[q].get('mape_ci95'), 2)}")
            return " / ".join(parts)
        L.append(f"| {m} | {w['bias_pct']:+.1f}{_cistr(w.get('bias_pct_ci95'))} | {_f(w['mae_um'])}{_cistr(w.get('mae_um_ci95'))} | "
                 f"{_f(w['mape_pct'])}{_cistr(w.get('mape_pct_ci95'))} | {d['bias_pct']:+.1f}{_cistr(d.get('bias_pct_ci95'))} | "
                 f"{_f(d['mae_um'])}{_cistr(d.get('mae_um_ci95'))} | {_f(d['mape_pct'])}{_cistr(d.get('mape_pct_ci95'))} | "
                 f"{sk('width')} | {sk('depth')} |")
    L.append("")
    return L


def _fits_line(fits: Dict[str, Any]) -> str:
    c = fits["const"]
    reg = ", ".join(f"{k} {v['a']:.2f}{'*' if v.get('fellBackToConst') else ''}" for k, v in fits["regime"]["classes"].items())
    pw = fits["powerlaw"]["width"]["exponents"]
    pd_ = fits["powerlaw"]["depth"]["exponents"]
    pl = "W: " + ", ".join(f"{k[0]}^{v:+.2f}" for k, v in pw.items()) + "; D: " + ", ".join(f"{k[0]}^{v:+.2f}" for k, v in pd_.items())
    return (f"const a = {c['a']:.2f}{' (grid edge)' if c.get('atGridEdge') else ''} (train loss {_f(c.get('trainLoss'), 3)}, "
            f"{c['nTrainSets']} sets); regime a = {reg}; power law {pl}")


def _label_table(by_label: Dict[str, Any]) -> List[str]:
    L = ["| regime label (harness) | n | model | W bias % | W MAPE % | D bias % | D MAPE % |", "|---|---|---|---|---|---|---|"]
    for label, ev in by_label.items():
        for m in MODELS:
            st = ev["models"].get(m)
            if not st or not st.get("width"):
                continue
            L.append(f"| {label} | {ev['n']} | {m} | {st['width']['bias_pct']:+.1f} | {_f(st['width']['mape_pct'])} | "
                     f"{st['depth']['bias_pct']:+.1f} | {_f(st['depth']['mape_pct'])} |")
    L.append("")
    return L


def _verdict_lines(v: Dict[str, Any]) -> List[str]:
    L = []
    for key, x in v.items():
        if key.startswith("default") or key.startswith("powerlaw vs default"):
            continue
        L.append(f"- {key}: skill (MAPE) {_f(x['skill_mape'], 2)}{_cistr(x['ci95'], 2)} -> **{x['verdict']}**")
    return L


def render_markdown(doc: Dict[str, Any]) -> str:
    cr = doc["codeRevision"]
    p = doc["protocol"]
    L = [f"# LPBF held-out absorptivity calibration ({doc['generatedAt']})", "", HEADER_MD, "",
         f"Schema `{doc['schema']}`; implementation fingerprint `{doc['implementationHash']}`; code revision "
         f"`{cr.get('gitHead')}` ({cr.get('gitBranch')}; dirty tracked paths: {len(cr.get('dirtyTrackedPaths') or [])}); "
         f"Python {cr.get('python')}; quick mode: {doc['quick']}. Evidence label: **{doc['evidence']['label']}**; "
         f"`experimentalValidation` = false; `opticalOperatorMatched` = false.", "",
         f"Honesty: {doc['evidence']['statement']}.", "",
         "## What was done", "",
         f"- Kernel: {doc['kernel']['entryPoint']}, {doc['kernel']['absorptionPath']}; varied: {doc['kernel']['variedParameter']}; "
         f"second scalar: {doc['kernel']['secondScalar']}. Solver calls {doc['kernel']['solverCalls']}, flat-plate "
         f"calls {doc['kernel']['flatPlateCalls']} (table source: {doc['kernel']['tableSource']}).",
         f"- Grid: {len(p['grid'])} absorptivity values from {p['grid'][0]:.2f} to {p['grid'][-1]:.2f} (step {GRID_STEP}, plus the material defaults).",
         f"- Loss: {p['lossDefinition']}",
         f"- Split: {p['splitRule']} k = {p['kFolds']}, seeds {p['cvSeeds']}; bootstrap {p['bootstrap']['replicates']} replicates, seed {p['bootstrap']['seed']}.",
         f"- Models: " + "; ".join(f"**{k}** = {v}" for k, v in p["models"].items()) + ".",
         f"- Skill: {p['skill']}.", "",
         "## Datasets", ""]
    for d in doc["datasets"]:
        L.append(f"- **{d['id']}** ({d['material']}): DOI {d['doi']}, {d['license']}, {d['rows']} rows, table sha256 `{d['tableSha256']}`. {d['citation']}")
    c = doc["counts"]
    L += ["", f"Counts: Hofmann {c['hofmannRows']} rows = {c['hofmannSets_P_v_d']} distinct (P, v, d) sets "
          f"({c['hofmannSets_P_v_d_layer']} with the powder layer in the key); Totis {c['totisRows']} rows = {c['totisSets_P_v_d']} sets. "
          f"Rows by input-only class: {c['rowsByRegimeClass']}; by harness label: {c['rowsByRegimeLabel']}.", "",
          "## Headline verdicts (held-out, paired bootstrap)", ""]
    for ds, v in doc["verdicts"]["cv"].items():
        L.append(f"**Grouped {p['kFolds']}-fold CV, {ds} (seed {p['cvSeeds'][0]})**")
        L += _verdict_lines(v) + [""]
    for key, v in doc["verdicts"]["lodo"].items():
        L.append(f"**Leave-one-dataset-out, {key} (cross-material transfer)**")
        L += _verdict_lines(v) + [""]
    L += ["## Grouped k-fold cross-validation (per dataset, no cross-material mixing)", ""]
    for ds, cv in doc["crossValidation"].items():
        for seed, rec in cv["bySeed"].items():
            L += [f"### {ds}, seed {seed}{' (primary: bootstrap intervals, breakdown)' if rec['primary'] else ' (stability repeat, point values)'}", ""]
            L += _model_table(rec["heldOut"])
            L += ["Fits per fold (train side only; `*` = class fell back to the const value for lack of training sets):", ""]
            for f in rec["folds"]:
                L.append(f"- fold {f['fold']} (train {f['nTrainSets']} sets / test {f['nTestSets']} sets): {_fits_line(f['fits'])}")
            L.append("")
            if rec["primary"]:
                L += ["Held-out breakdown by harness regime label (point values, no intervals; the balling flag enters the label only):", ""]
                L += _label_table(rec["byRegimeLabel"])
    L += ["## Leave-one-dataset-out (cross-material transfer)", ""]
    for key, rec in doc["leaveOneDatasetOut"].items():
        L += [f"### {key}", "", rec["note"] + ".", "", f"Fits: {_fits_line(rec['fits'])}", ""]
        L += _model_table(rec["heldOut"])
        L += ["Breakdown by harness regime label:", ""] + _label_table(rec["byRegimeLabel"])
    L += ["## In-sample reference (optimistic, not held-out)", "",
          "Fit and score on the same rows; shown only so the held-out gap is visible.", "",
          "| dataset | const a | regime a | W MAPE % default / const / regime / powerlaw | D MAPE % default / const / regime / powerlaw |",
          "|---|---|---|---|---|"]
    for ds, rec in doc["inSampleReference"].items():
        ev = rec["inSample"]["models"]
        reg = ", ".join(f"{k} {v['a']:.2f}" for k, v in rec["fits"]["regime"]["classes"].items())

        def line(q):
            return " / ".join(_f(ev[m][q]["mape_pct"]) if ev.get(m) and ev[m].get(q) else "-" for m in MODELS)
        L.append(f"| {ds} | {rec['fits']['const']['a']:.2f} | {reg} | {line('width')} | {line('depth')} |")
    L += ["", "## What this does not show", ""]
    for x in doc["whatThisDoesNotShow"]:
        L.append(f"- {x}")
    L += ["", "## Assumptions", ""]
    for k, v in doc["assumptions"].items():
        L.append(f"- **{k}**: {v}")
    L += ["", f"Regime rule (harness): {doc['regimeRule']}", ""]
    return "\n".join(L).rstrip("\n") + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True, help="output JSON path (the .md goes next to it)")
    ap.add_argument("--quick", action="store_true", help="first 40 rows of each dataset")
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--table-cache", default=None, help="JSON file holding the kernel grid table (read if valid, else written)")
    ap.add_argument("--bootstrap", type=int, default=BOOT_REPLICATES)
    ap.add_argument("--generated-at", default=GENERATED_AT_DEFAULT)
    a = ap.parse_args(argv)
    out = Path(a.out).resolve()
    if "golden" in out.parts:
        raise SystemExit("refusing to write under golden/")
    t0 = time.perf_counter()
    doc = build_document(a.quick, a.jobs, a.generated_at,
                         table_cache=Path(a.table_cache).resolve() if a.table_cache else None, replicates=a.bootstrap)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, sort_keys=True, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    out.with_suffix(".md").write_text(render_markdown(doc), encoding="utf-8", newline="\n")
    print(f"wrote {out} and .md in {time.perf_counter() - t0:.0f} s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
