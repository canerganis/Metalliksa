"""Pure statistics for the LPBF melt-pool calibration scorecard (no solver import, numpy only).

HELD-OUT CALIBRATION OF NUISANCE PARAMETERS, NOT EXPERIMENTAL VALIDATION. This module holds the one leakage rule
(parameter-set grouping, shared with python/tools/lpbf_calibration_heldout.py, which imports it from here), the
vectorised estimator (absorptivity grid scans on precomputed log residuals), the cluster bootstraps, the
source-aware interval, coverage with Wilson intervals, the regime confusion matrix, and the gate.

Kernel values enter only as arrays (``FineKernel``); the kernel table itself is built by
python/tools/lpbf_calibration_fit.py. Nothing here may be imported by a frozen physics file.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

RAYTRACER_MODULE = "powder_bed_raytracer"
CLASSES = ("conduction", "transition", "keyhole")
ENTHALPY_TRANSITION = 15.0
ENTHALPY_KEYHOLE = 30.0


# ---------------------------------------------------------------------------------------------
# keys, splits, leakage (the single rule)
# ---------------------------------------------------------------------------------------------
def pin_flat_plate() -> None:
    """The solver's optional ray tracer import fails -> flat-plate absorption path (same pin as the harnesses)."""
    sys.modules[RAYTRACER_MODULE] = None


def row_source(row: Dict[str, Any]) -> str:
    return str(row.get("source", row.get("dataset", "")) or "")


def set_key(row: Dict[str, Any]) -> tuple:
    """Parameter set = (source, material, power_W, speed_mm_s, beamDiameter_um). The powder layer is deliberately
    NOT part of the key: replicates and layer variants of one laser setting stay on one side of every split."""
    return (row_source(row), row["material"], float(row["power_W"]), float(row["speed_mm_s"]),
            float(row["beamDiameter_um"]))


def regime_class_from_enthalpy(h: float) -> str:
    if h < ENTHALPY_TRANSITION:
        return "conduction"
    if h < ENTHALPY_KEYHOLE:
        return "transition"
    return "keyhole"


def fold_assignment(keys: Sequence[tuple], k: int, seed: int) -> Dict[tuple, int]:
    """The ONE fold rule: sorted set keys shuffled with random.Random(seed), dealt round-robin into k folds."""
    ks = sorted(set(keys))
    rng = random.Random(seed)
    rng.shuffle(ks)
    return {key: i % k for i, key in enumerate(ks)}


def grouped_kfold(rows: Sequence[Dict[str, Any]], k: int, seed: int) -> List[Tuple[list, list]]:
    """[(train_rows, test_rows)] with whole parameter sets on one side; deterministic for a seed."""
    fold_of = fold_assignment([set_key(r) for r in rows], k, seed)
    folds = []
    for f in range(k):
        test = [r for r in rows if fold_of[set_key(r)] == f]
        train = [r for r in rows if fold_of[set_key(r)] != f]
        folds.append((train, test))
    return folds


def leave_one_source_out(rows: Sequence[Dict[str, Any]]) -> List[Tuple[str, list, list]]:
    """[(held_out_source, train_rows, test_rows)] over the distinct sources of ``rows`` (sorted)."""
    out = []
    for s in sorted({row_source(r) for r in rows}):
        out.append((s, [r for r in rows if row_source(r) != s], [r for r in rows if row_source(r) == s]))
    return out


def assert_no_leak(train: Sequence[Dict[str, Any]], test: Sequence[Dict[str, Any]], by_source: bool = False) -> None:
    """Raise when a parameter set (or, for a source-level split, a source) appears on both sides."""
    overlap = {set_key(r) for r in train} & {set_key(r) for r in test}
    if overlap:
        raise AssertionError(f"parameter sets straddle train and test: {sorted(overlap)[:3]}")
    if by_source:
        shared = {row_source(r) for r in train} & {row_source(r) for r in test}
        if shared:
            raise AssertionError(f"sources straddle train and test: {sorted(shared)}")


def assert_trainable(rows: Sequence[Dict[str, Any]], catalog_sources: Sequence[str]) -> None:
    """R1: no catalog (development) row may reach any fit."""
    bad = sorted({row_source(r) for r in rows if row_source(r) in set(catalog_sources) or r.get("catalog")})
    if bad:
        raise AssertionError(f"catalog sentinel rows reached a fit: {bad}")


# ---------------------------------------------------------------------------------------------
# numeric helpers, hashing, rounding
# ---------------------------------------------------------------------------------------------
def round_sig(obj: Any, digits: int = 6) -> Any:
    """Round every float to ``digits`` significant digits (deterministic serialisation); non-finite -> None."""
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (np.floating,)):
        obj = float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, float):
        if not math.isfinite(obj):
            return None
        if obj == 0.0:
            return 0.0
        return float(f"{obj:.{digits - 1}e}")
    if isinstance(obj, dict):
        return {str(k): round_sig(v, digits) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [round_sig(v, digits) for v in obj]
    if isinstance(obj, np.ndarray):
        return round_sig(obj.tolist(), digits)
    return obj


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_sha256(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def robust_sd(x: Sequence[float]) -> float:
    a = np.asarray(list(x), dtype=float)
    if a.size == 0:
        return float("nan")
    return float(1.4826 * np.median(np.abs(a - np.median(a))))


def _gammainc_lower_reg(a: float, x: float) -> float:
    """Regularised lower incomplete gamma P(a, x) (series / continued fraction)."""
    if x <= 0:
        return 0.0
    gln = math.lgamma(a)
    if x < a + 1.0:
        ap, s, d = a, 1.0 / a, 1.0 / a
        for _ in range(500):
            ap += 1.0
            d *= x / ap
            s += d
            if abs(d) < abs(s) * 1e-14:
                break
        return s * math.exp(-x + a * math.log(x) - gln)
    b = x + 1.0 - a
    c = 1.0 / 1e-300
    d = 1.0 / b
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-14:
            break
    return 1.0 - math.exp(-x + a * math.log(x) - gln) * h


def chi2_ppf(p: float, df: int) -> float:
    """Chi-square quantile by bisection on the exact CDF (no scipy dependency)."""
    lo, hi = 0.0, max(10.0, 10.0 * df)
    while _gammainc_lower_reg(df / 2.0, hi / 2.0) < p:
        hi *= 2.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if _gammainc_lower_reg(df / 2.0, mid / 2.0) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def wilson(k: int, n: int, conf: float = 0.95) -> Optional[List[float]]:
    """Wilson score interval for a binomial proportion; None when n == 0."""
    if n <= 0:
        return None
    z = {0.95: 1.959964, 0.90: 1.644854, 0.99: 2.575829}.get(conf, 1.959964)
    p = k / n
    den = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [max(0.0, centre - half), min(1.0, centre + half)]


def source_weights(n_sets_by_source: Dict[Any, int], n_full: int = 20) -> Dict[Any, float]:
    """R2: w_s = min(1, nSets_s / n_full), normalised to sum 1 (a 4-row source cannot carry half the loss)."""
    raw = {s: min(1.0, n / float(n_full)) for s, n in n_sets_by_source.items() if n > 0}
    tot = sum(raw.values())
    return {s: v / tot for s, v in raw.items()} if tot > 0 else {}


# ---------------------------------------------------------------------------------------------
# log interpolation on kernel nodes
# ---------------------------------------------------------------------------------------------
def interp_log(nodes: Sequence[float], values: Sequence[float], eta: float) -> float:
    """Value at ``eta`` interpolated linearly in ln(eta) on ln(values); raises outside the node range."""
    nodes = list(nodes)
    for j, n in enumerate(nodes):
        if abs(n - eta) < 1e-9:
            return float(values[j])
    if eta < nodes[0] or eta > nodes[-1]:
        raise ValueError(f"eta {eta} outside the node range [{nodes[0]}, {nodes[-1]}]")
    hi = next(j for j, n in enumerate(nodes) if n > eta)
    lo = hi - 1
    w = (math.log(eta) - math.log(nodes[lo])) / (math.log(nodes[hi]) - math.log(nodes[lo]))
    return float(math.exp((1 - w) * math.log(values[lo]) + w * math.log(values[hi])))


def fine_weights(nodes: Sequence[float], eta_fine: Sequence[float]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    nodes = np.asarray(nodes, dtype=float)
    lo = np.zeros(len(eta_fine), dtype=int)
    hi = np.zeros(len(eta_fine), dtype=int)
    w = np.zeros(len(eta_fine))
    for i, e in enumerate(eta_fine):
        exact = np.flatnonzero(np.abs(nodes - e) < 1e-9)
        if exact.size:
            lo[i] = hi[i] = int(exact[0])
            continue
        if e < nodes[0] or e > nodes[-1]:
            raise ValueError(f"eta {e} outside the node range")
        h = int(np.searchsorted(nodes, e))
        lo[i], hi[i] = h - 1, h
        w[i] = (math.log(e) - math.log(nodes[h - 1])) / (math.log(nodes[h]) - math.log(nodes[h - 1]))
    return lo, hi, w


def eta_fine_grid(cfg: Dict[str, Any]) -> np.ndarray:
    g = cfg["fitGrid"]
    n = int(round((g["stop"] - g["start"]) / g["step"])) + 1
    return np.array([round(g["start"] + i * g["step"], 6) for i in range(n)])


class FineKernel:
    """Kernel log-widths/depths of a row set on the fine absorptivity grid, plus the measurements.

    rows: list of row dicts (width_um/depth_um measured; ``regimeClass``; ``balling`` 0/1/None).
    nodes: kernel absorptivity nodes (K). lnW_nodes/lnD_nodes/ok_nodes: (n, K). defW/defD/defOk: (n,) the
    screening result with NO override (the served default).
    """

    def __init__(self, rows: Sequence[Dict[str, Any]], nodes: Sequence[float], lnW_nodes: np.ndarray,
                 lnD_nodes: np.ndarray, ok_nodes: np.ndarray, defW: np.ndarray, defD: np.ndarray,
                 defOk: np.ndarray, eta_fine: Sequence[float]):
        self.rows = list(rows)
        self.n = len(self.rows)
        self.eta = np.asarray(eta_fine, dtype=float)
        lo, hi, w = fine_weights(nodes, self.eta)
        self.lnW = (1 - w) * lnW_nodes[:, lo] + w * lnW_nodes[:, hi]
        self.lnD = (1 - w) * lnD_nodes[:, lo] + w * lnD_nodes[:, hi]
        self.ok = ok_nodes[:, lo] & ok_nodes[:, hi]
        self.defW = np.asarray(defW, dtype=float)
        self.defD = np.asarray(defD, dtype=float)
        self.defOk = np.asarray(defOk, dtype=bool)
        self.measW = np.array([float(r["width_um"]) for r in self.rows])
        self.measD = np.array([float(r["depth_um"]) for r in self.rows])
        self.lnWm = np.log(self.measW)
        self.lnDm = np.log(self.measD)
        keys = [set_key(r) for r in self.rows]
        uniq = sorted(set(keys))
        pos = {k: i for i, k in enumerate(uniq)}
        self.set_keys = uniq
        self.set_idx = np.array([pos[k] for k in keys], dtype=int)
        srcs = sorted({row_source(r) for r in self.rows})
        spos = {s: i for i, s in enumerate(srcs)}
        self.sources = srcs
        self.source_idx = np.array([spos[row_source(r)] for r in self.rows], dtype=int)
        self.set_source = np.zeros(len(uniq), dtype=int)
        for i, k in enumerate(keys):
            self.set_source[self.set_idx[i]] = self.source_idx[i]
        self.cls = np.array([CLASSES.index(r["regimeClass"]) if r.get("regimeClass") in CLASSES else -1
                             for r in self.rows], dtype=int)
        self.balling = np.array([1 if r.get("balling") == 1 else 0 for r in self.rows], dtype=int)

    def subset_idx(self, source: Optional[str] = None, sources: Optional[Sequence[str]] = None) -> np.ndarray:
        if source is not None:
            return np.flatnonzero(self.source_idx == self.sources.index(source)) if source in self.sources else np.array([], int)
        if sources is not None:
            ids = [self.sources.index(s) for s in sources if s in self.sources]
            return np.flatnonzero(np.isin(self.source_idx, ids))
        return np.arange(self.n)

    def meas(self, q: str) -> np.ndarray:
        return self.measW if q == "width" else self.measD

    def lnmeas(self, q: str) -> np.ndarray:
        return self.lnWm if q == "width" else self.lnDm

    def lnpred(self, q: str) -> np.ndarray:
        return self.lnW if q == "width" else self.lnD

    def default_pred(self, q: str) -> np.ndarray:
        return self.defW if q == "width" else self.defD


# ---------------------------------------------------------------------------------------------
# estimator
# ---------------------------------------------------------------------------------------------
class SetTable:
    """Per-parameter-set mean |ln(pred/meas)| on the fine grid for one quantity and one training row set."""

    def __init__(self, fk: FineKernel, idx: np.ndarray, q: str, use: Optional[np.ndarray] = None):
        self.fk, self.q = fk, q
        idx = np.asarray(idx, dtype=int)
        use_mask = np.ones(len(idx), dtype=bool) if use is None else np.asarray(use, dtype=bool)
        sets, inv = np.unique(fk.set_idx[idx], return_inverse=True)
        self.global_sets = sets
        self.S = len(sets)
        self.set_source = fk.set_source[sets]
        ok = fk.ok[idx] & use_mask[:, None]
        res = np.abs(fk.lnpred(q)[idx] - fk.lnmeas(q)[idx][:, None]) * ok
        M = np.zeros((self.S, len(idx)))
        M[inv, np.arange(len(idx))] = 1.0
        s_sum = M @ res
        s_cnt = M @ ok.astype(float)
        self.valid = s_cnt > 0
        self.loss = np.where(self.valid, s_sum / np.maximum(s_cnt, 1.0), 0.0)
        n_use = int(use_mask.sum())
        self.cover = (ok.sum(axis=0) / n_use) if n_use else np.zeros(fk.eta.size)
        self.n_rows = n_use
        self.n_sets_by_source = {int(s): int(np.sum(self.set_source == s)) for s in np.unique(self.set_source)}
        self.rows_idx = idx
        self.inv = inv


def _loss_curve(st: SetTable, set_w: Optional[np.ndarray], src_w: Dict[int, float], min_coverage: float) -> np.ndarray:
    """(R, J) loss: weighted mean over sources of per-source mean over sets; inf where coverage < minimum."""
    J = st.fk.eta.size
    W = np.ones((1, st.S)) if set_w is None else np.atleast_2d(set_w).astype(float)
    R = W.shape[0]
    num_tot = np.zeros((R, J))
    den_tot = np.zeros((R, J))
    for s, ws in src_w.items():
        m = st.set_source == s
        if not m.any():
            continue
        w = W[:, m][:, :, None] * st.valid[m][None, :, :]
        den = w.sum(axis=1)
        num = (w * st.loss[m][None, :, :]).sum(axis=1)
        present = den > 0
        Ls = np.where(present, num / np.maximum(den, 1e-300), 0.0)
        num_tot += np.where(present, ws * Ls, 0.0)
        den_tot += np.where(present, ws, 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(den_tot > 0, num_tot / np.maximum(den_tot, 1e-300), np.inf)
    out = np.where((st.cover >= min_coverage)[None, :], out, np.inf)
    return out


def _argmin_row(total: np.ndarray) -> np.ndarray:
    """Per-row argmin with ties to the smaller eta; -1 when the whole row is inf."""
    mn = total.min(axis=1)
    out = np.full(total.shape[0], -1, dtype=int)
    for r in range(total.shape[0]):
        if np.isfinite(mn[r]):
            out[r] = int(np.flatnonzero(total[r] <= mn[r] + 1e-12)[0])
    return out


def fit_ladder(fk: FineKernel, idx: np.ndarray, cfg: Dict[str, Any], eta_prior: float, bootstrap: bool = False,
               seed: int = 0) -> Optional[Dict[str, Any]]:
    """Fit eta_W, eta_D, joint eta and c_D[class] on the training rows ``idx`` (all one alloy).

    Returns None when no absorptivity reaches the coverage floor for any quantity. With ``bootstrap`` the
    stratified cluster bootstrap (sets resampled within source, theta refit) adds ci90 and bound-hit fractions."""
    idx = np.asarray(idx, dtype=int)
    if idx.size == 0:
        return None
    min_cov = cfg["minCoverage"]
    lam = cfg["prior"]["lambda"]
    pen = lam * np.log(fk.eta / eta_prior) ** 2
    use_w = np.array([not (cfg["ballingFlaggedRowsTrainWidth"] is False and fk.balling[i] == 1) for i in idx])
    use_d = np.array([not (cfg["ballingFlaggedRowsTrainDepth"] is False and fk.balling[i] == 1) for i in idx])
    stW = SetTable(fk, idx, "width", use_w)
    stD = SetTable(fk, idx, "depth", use_d)
    n_sets_src = {}
    for st in (stW, stD):
        for s, n in st.n_sets_by_source.items():
            n_sets_src[s] = max(n_sets_src.get(s, 0), n)
    sw = source_weights(n_sets_src, cfg["sourceWeight"]["nSetsFull"])
    LW = _loss_curve(stW, None, sw, min_cov)
    LD = _loss_curve(stD, None, sw, min_cov)
    LJ = 0.5 * (LW + LD)
    jW, jD, jJ = (int(_argmin_row(L + pen[None, :])[0]) for L in (LW, LD, LJ))
    J = fk.eta.size
    step = cfg["gate"]["boundHitSteps"]

    def hit(j: int) -> bool:
        return j >= 0 and (j <= step - 1 or j >= J - step)

    out: Dict[str, Any] = {
        "jW": jW, "jD": jD, "jJ": jJ,
        "etaW": float(fk.eta[jW]) if jW >= 0 else None, "etaD": float(fk.eta[jD]) if jD >= 0 else None,
        "etaJ": float(fk.eta[jJ]) if jJ >= 0 else None,
        "lossW": float(LW[0, jW]) if jW >= 0 else None, "lossD": float(LD[0, jD]) if jD >= 0 else None,
        "boundHit": {"W": hit(jW), "D": hit(jD), "J": hit(jJ)},
        "nTrainRows": int(idx.size), "nTrainSets": int(len(stW.global_sets)),
        "sourceWeights": {fk.sources[s]: w for s, w in sw.items()},
        "etaPrior": float(eta_prior),
    }
    out["cd"], out["cdSource"], out["cdNSets"] = _fit_cd(fk, idx, jD, cfg) if jD >= 0 else ({}, {}, {})
    if bootstrap:
        out["boot"] = _bootstrap_fit(fk, idx, stW, stD, sw, pen, cfg, seed, jD)
    return out


def _set_values_cd(fk: FineKernel, idx: np.ndarray, jD: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-set mean ln(D_meas / D(eta_D)) over resolved rows, and the set's class (-1 unknown)."""
    ok = fk.ok[idx, jD]
    res = fk.lnDm[idx] - fk.lnD[idx, jD]
    sets, inv = np.unique(fk.set_idx[idx], return_inverse=True)
    sums = np.bincount(inv, weights=res * ok, minlength=len(sets))
    cnt = np.bincount(inv, weights=ok.astype(float), minlength=len(sets))
    cls = np.full(len(sets), -1)
    cls[inv] = fk.cls[idx]
    valid = cnt > 0
    return sums[valid] / cnt[valid], cls[valid], sets[valid]


def _cd_from_values(vals: np.ndarray, cls: np.ndarray, cfg: Dict[str, Any]) -> Tuple[Dict[str, float], Dict[str, str], Dict[str, int]]:
    clip = cfg["cdClipLn"]
    min_sets = cfg["minSetsPerClass"]
    alloy = float(np.clip(np.median(vals), -clip, clip)) if vals.size >= min_sets else None
    cd, src, nsets = {}, {}, {}
    for ci, name in enumerate(CLASSES):
        m = cls == ci
        nsets[name] = int(m.sum())
        if m.sum() >= min_sets:
            cd[name] = float(np.clip(np.median(vals[m]), -clip, clip))
            src[name] = "class"
        elif alloy is not None:
            cd[name] = alloy
            src[name] = "alloy"
        else:
            cd[name] = 0.0
            src[name] = "zero"
    return cd, src, nsets


def _fit_cd(fk: FineKernel, idx: np.ndarray, jD: int, cfg: Dict[str, Any]):
    vals, cls, _ = _set_values_cd(fk, idx, jD)
    return _cd_from_values(vals, cls, cfg)


def _bootstrap_fit(fk: FineKernel, idx: np.ndarray, stW: SetTable, stD: SetTable, sw: Dict[int, float],
                   pen: np.ndarray, cfg: Dict[str, Any], seed: int, jD0: int) -> Dict[str, Any]:
    B = cfg["bootstrap"]["paramReplicates"]
    rng = np.random.default_rng(seed)
    S = stW.S
    W = np.zeros((B, S))
    for s in np.unique(stW.set_source):
        m = np.flatnonzero(stW.set_source == s)
        n = len(m)
        W[:, m] = rng.multinomial(n, np.full(n, 1.0 / n), size=B)
    min_cov = cfg["minCoverage"]
    LW = _loss_curve(stW, W, sw, min_cov)
    LD = _loss_curve(stD, W, sw, min_cov)
    LJ = 0.5 * (LW + LD)
    J = fk.eta.size
    step = cfg["gate"]["boundHitSteps"]
    res = {}
    for name, L in (("W", LW), ("D", LD), ("J", LJ)):
        j = _argmin_row(L + pen[None, :])
        okj = j >= 0
        eta = fk.eta[j[okj]] if okj.any() else np.array([])
        res[name] = {
            "ci90": [float(np.percentile(eta, 5)), float(np.percentile(eta, 95))] if eta.size else None,
            "boundHitFraction": float(np.mean((j[okj] <= step - 1) | (j[okj] >= J - step))) if eta.size else None,
            "n": int(okj.sum()),
        }
    # c_D bootstrap at the point-estimate eta_D (set values resampled with the same multiplicities)
    cd_ci: Dict[str, Any] = {}
    if jD0 >= 0:
        vals, cls, gsets = _set_values_cd(fk, idx, jD0)
        pos = {int(g): i for i, g in enumerate(stW.global_sets)}
        cols = np.array([pos[int(g)] for g in gsets])
        draws = {name: [] for name in CLASSES}
        for b in range(B):
            counts = W[b, cols].astype(int)
            v = np.repeat(vals, counts)
            c = np.repeat(cls, counts)
            cd, _, _ = _cd_from_values(v, c, cfg)
            for name in CLASSES:
                draws[name].append(cd[name])
        for name in CLASSES:
            d = np.array(draws[name])
            cd_ci[name] = [float(np.percentile(d, 5)), float(np.percentile(d, 95))]
    res["cd"] = cd_ci
    res["replicates"] = B
    return res


# ---------------------------------------------------------------------------------------------
# prediction and metrics
# ---------------------------------------------------------------------------------------------
RUNG_ORDER = ("default", "eta", "eta2", "eta2+dOffset")


def predict_rung(fk: FineKernel, idx: np.ndarray, rung: str, fit: Optional[Dict[str, Any]], q: str
                 ) -> Tuple[np.ndarray, np.ndarray]:
    """(prediction, resolved mask) for quantity q on rows ``idx`` for a ladder rung; unavailable fit -> unresolved."""
    idx = np.asarray(idx, dtype=int)
    if rung == "default":
        return fk.default_pred(q)[idx], fk.defOk[idx].copy()
    if fit is None:
        return np.full(idx.size, np.nan), np.zeros(idx.size, dtype=bool)
    if rung == "eta":
        j = fit["jJ"]
    else:
        j = fit["jW"] if q == "width" else fit["jD"]
    if j is None or j < 0:
        return np.full(idx.size, np.nan), np.zeros(idx.size, dtype=bool)
    ln = fk.lnpred(q)[idx, j].copy()
    if rung == "eta2+dOffset" and q == "depth":
        cd = np.array([fit["cd"].get(CLASSES[c], 0.0) if c >= 0 else 0.0 for c in fk.cls[idx]])
        ln = ln + cd
    return np.exp(ln), fk.ok[idx, j].copy()


def metrics(pred: np.ndarray, meas: np.ndarray, ok: np.ndarray) -> Dict[str, Any]:
    ok = np.asarray(ok, dtype=bool)
    n_all = int(ok.size)
    if not ok.any():
        return {"n": 0, "nRows": n_all, "unresolved": n_all, "biasPct": None, "mapePct": None, "rmse_um": None,
                "within30": None, "withinFactor2": None}
    p, m = pred[ok], meas[ok]
    rel = (p - m) / m
    return {"n": int(ok.sum()), "nRows": n_all, "unresolved": int(n_all - ok.sum()),
            "biasPct": float(100.0 * np.mean(rel)), "mapePct": float(100.0 * np.mean(np.abs(rel))),
            "rmse_um": float(math.sqrt(np.mean((p - m) ** 2))),
            "within30": float(np.mean(np.abs(rel) <= 0.30)),
            "withinFactor2": float(np.mean((p / m >= 0.5) & (p / m <= 2.0)))}


def mape_unresolved_as_fail(pred: np.ndarray, meas: np.ndarray, ok: np.ndarray, fail_rel: float = 1.0) -> Optional[float]:
    """R7 convention: an unresolved test row counts as a 100 % relative error."""
    if ok.size == 0:
        return None
    rel = np.where(ok, np.abs(np.where(ok, pred, meas) - meas) / meas, fail_rel)
    return float(100.0 * np.mean(rel))


# ---------------------------------------------------------------------------------------------
# bootstraps and skill
# ---------------------------------------------------------------------------------------------
def cluster_bootstrap(values: np.ndarray, counts: np.ndarray, B: int, seed: int) -> np.ndarray:
    """Cluster-bootstrap distribution of sum(values)/sum(counts) with whole clusters resampled."""
    rng = np.random.default_rng(seed)
    S = len(values)
    if S == 0:
        return np.array([])
    draws = rng.integers(0, S, size=(B, S))
    return values[draws].sum(axis=1) / np.maximum(counts[draws].sum(axis=1), 1e-300)


def paired_skill(pred_a: np.ndarray, pred_b: np.ndarray, meas: np.ndarray, ok: np.ndarray, cluster: np.ndarray,
                 B: int, seed: int) -> Dict[str, Any]:
    """Skill of model A over baseline B: 1 - MAPE_A/MAPE_B on the common resolved rows; paired cluster bootstrap
    over test sets with theta fixed (no refit). ``ok`` is the common resolved mask."""
    ok = np.asarray(ok, dtype=bool)
    if not ok.any():
        return {"skill": None, "ci95": None, "mapeA": None, "mapeB": None, "n": 0, "nClusters": 0}
    a = np.abs(pred_a[ok] - meas[ok]) / meas[ok]
    b = np.abs(pred_b[ok] - meas[ok]) / meas[ok]
    cl = np.asarray(cluster)[ok]
    ids, inv = np.unique(cl, return_inverse=True)
    sa = np.bincount(inv, weights=a)
    sb = np.bincount(inv, weights=b)
    cn = np.bincount(inv).astype(float)
    mape_a, mape_b = float(a.mean()), float(b.mean())
    skill = None if mape_b <= 0 else 1.0 - mape_a / mape_b
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(ids), size=(B, len(ids)))
    ma = sa[draws].sum(axis=1) / cn[draws].sum(axis=1)
    mb = sb[draws].sum(axis=1) / cn[draws].sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        sk = np.where(mb > 0, 1.0 - ma / mb, np.nan)
    sk = sk[np.isfinite(sk)]
    ci = [float(np.percentile(sk, 2.5)), float(np.percentile(sk, 97.5))] if sk.size else None
    return {"skill": skill, "ci95": ci, "mapeA": 100 * mape_a, "mapeB": 100 * mape_b, "n": int(ok.sum()),
            "nClusters": int(len(ids))}


def verdict_from_ci(ci: Optional[Sequence[float]]) -> str:
    if ci is None:
        return "not bootstrapped"
    if ci[0] > 0:
        return "beats"
    if ci[1] < 0:
        return "does-not-beat"
    return "inconclusive"


# ---------------------------------------------------------------------------------------------
# intervals and coverage
# ---------------------------------------------------------------------------------------------
Z_LEVEL = {0.8: 1.2816, 0.9: 1.6449}


def source_sd_inflated(means: Sequence[float], chi2_level: float = 0.10, min_sources: int = 3) -> Optional[Dict[str, float]]:
    """SD of per-source mean residuals (ddof 1) with the chi-square one-sided upper bound; None below min_sources."""
    a = np.asarray(list(means), dtype=float)
    n = a.size
    if n < min_sources:
        return None
    sd = float(np.std(a, ddof=1))
    infl = math.sqrt((n - 1) / chi2_ppf(chi2_level, n - 1))
    return {"sd": sd, "inflation": infl, "sdUpper": sd * infl, "nSources": n}


def conformal_interval(m: float, s_within: float, s_source: float, level: float,
                       z_table: Optional[Dict[Any, float]] = None) -> Tuple[float, float]:
    """Multiplicative interval factors (lo, hi): PI = q_cal * [lo, hi], s = sqrt(s_within^2 + s_source^2)."""
    z = (z_table or Z_LEVEL)[level]
    s = math.sqrt(s_within ** 2 + s_source ** 2)
    return math.exp(m - z * s), math.exp(m + z * s)


def coverage(meas: np.ndarray, pred: np.ndarray, lo_f: float, hi_f: float, ok: np.ndarray) -> Dict[str, Any]:
    ok = np.asarray(ok, dtype=bool)
    n = int(ok.sum())
    if n == 0:
        return {"k": 0, "n": 0, "coverage": None, "wilson95": None}
    inside = (meas[ok] >= pred[ok] * lo_f) & (meas[ok] <= pred[ok] * hi_f)
    k = int(inside.sum())
    return {"k": k, "n": n, "coverage": k / n, "wilson95": wilson(k, n, 0.95)}


# ---------------------------------------------------------------------------------------------
# regime confusion
# ---------------------------------------------------------------------------------------------
def confusion(published: Sequence[str], predicted: Sequence[str], labels: Sequence[str] = CLASSES,
              positive: str = "keyhole") -> Dict[str, Any]:
    matrix = {p: {c: 0 for c in labels} for p in labels}
    for p, c in zip(published, predicted):
        if p in matrix and c in matrix[p]:
            matrix[p][c] += 1
    n = sum(sum(r.values()) for r in matrix.values())
    correct = sum(matrix[l][l] for l in labels)
    tp = matrix[positive][positive] if positive in matrix else 0
    fn = sum(v for c, v in matrix[positive].items() if c != positive) if positive in matrix else 0
    fp = sum(matrix[p][positive] for p in labels if p != positive)
    tn = n - tp - fn - fp
    return {"labels": list(labels), "matrix": matrix, "n": n, "accuracy": (correct / n) if n else None,
            f"{positive}Only": {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
                                "precision": tp / (tp + fp) if (tp + fp) else None,
                                "recall": tp / (tp + fn) if (tp + fn) else None}}


# ---------------------------------------------------------------------------------------------
# eta consistency (R4), absorptance disagreement (R5)
# ---------------------------------------------------------------------------------------------
def eta_consistent(eta_a: float, ci_a: Optional[Sequence[float]], eta_b: float, ci_b: Optional[Sequence[float]],
                   dln: float = 0.15) -> bool:
    """R4: each fold's eta inside the other's bootstrap CI90, or |ln(eta_a/eta_b)| <= dln."""
    if abs(math.log(eta_a / eta_b)) <= dln:
        return True
    in_b = ci_b is not None and ci_b[0] <= eta_a <= ci_b[1]
    in_a = ci_a is not None and ci_a[0] <= eta_b <= ci_a[1]
    return bool(in_a and in_b)


def absorptance_disagreement(eta: float, classes_with_sets: Dict[str, int], bands: Dict[str, Any],
                             min_sets: int = 8) -> List[Dict[str, Any]]:
    """Classes of the training data whose measured-absorptance band (widened) excludes the fitted effective eta.
    A DIAGNOSTIC of 'eta absorbs model error', not a validation or a match claim."""
    widen = bands.get("widenFactor", 1.3)
    out = []
    for name, rng_ in bands.items():
        if name in ("basis", "widenFactor") or not isinstance(rng_, (list, tuple)):
            continue
        if classes_with_sets.get(name, 0) < min_sets:
            continue
        lo, hi = rng_[0] / widen, rng_[1] * widen
        if not (lo <= eta <= hi):
            out.append({"class": name, "band": [lo, hi], "eta": eta})
    return out


# ---------------------------------------------------------------------------------------------
# gate
# ---------------------------------------------------------------------------------------------
STATUSES = ("enabled", "within-source-only", "rejected", "no-data")
HARD_FLAGS = ("boundHit", "etaSplit", "offsetDominant", "etaInconsistentWithMeasuredAbsorptance")


def gate_cell(ev: Dict[str, Any], gate: Dict[str, Any]) -> Dict[str, Any]:
    """Status of one (kernel, alloy, quantity) cell from an evidence dict (see lpbf_calibration_cells)."""
    reasons: List[str] = []
    if ev.get("noData"):
        return {"status": "no-data", "reasons": ["no non-catalog measured source for this alloy"]}
    hard: List[str] = []
    for f in HARD_FLAGS:
        if ev.get("flags", {}).get(f):
            hard.append(f)
    if ev.get("etaConsistent") is False:
        hard.append("sourceDependentEta")
    if ev.get("unresolvedWorse"):
        hard.append("unresolvedRows")
    p2 = ev.get("p2") or []
    p1 = ev.get("p1") or []
    p2_fail: List[str] = []
    if ev.get("servedRung") == "default":
        # blocks `enabled` (a default rung serves nothing) but is not a physics fault: a within-source gain may still exist
        p2_fail.append("noRungImprovesAcrossSources: no ladder rung beats default on the inner training score")
    floor = gate["skillLbFloor"]
    for rec in p2:
        lb = rec.get("skillLb95")
        if lb is None or lb < floor:
            p2_fail.append(f"held-out source {rec['source']}: skill CI95 lower bound "
                           f"{'n/a' if lb is None else format(lb, '.3f')} < {floor}")
        if rec.get("coverage90N", 0) >= gate["minRowsForCoverage"]:
            wu = rec.get("coverage90WilsonUpper")
            if wu is None or wu < gate["coverageWilsonUpperMin"]:
                p2_fail.append(f"held-out source {rec['source']}: 90 % PI coverage Wilson upper bound "
                               f"{'n/a' if wu is None else format(wu, '.3f')} < {gate['coverageWilsonUpperMin']}")
        if rec.get("unresolvedRung", 0) > rec.get("unresolvedDefault", 0):
            p2_fail.append(f"held-out source {rec['source']}: rung leaves more rows unresolved than default")
    if p2 and not any((r.get("skillLb95") is not None and r["skillLb95"] > 0) for r in p2):
        p2_fail.append("no held-out source with skill CI95 lower bound > 0")
    if not ev.get("hasSecondSource"):
        p2_fail.append("single source: no leave-one-source-out available")
    if hard:
        return {"status": "rejected", "reasons": hard + p2_fail}
    if ev.get("hasSecondSource") and not p2_fail:
        return {"status": "enabled", "reasons": []}
    reasons = p2_fail
    p1_ok = any((r.get("lb") is not None and r["lb"] > gate["p1WithinSourceSkillLbMin"]) for r in p1)
    if p1_ok:
        return {"status": "within-source-only", "reasons": reasons}
    if not p1:
        return {"status": "rejected", "reasons": reasons + [
            "no within-source evaluation possible: no source has enough parameter sets for grouped k-fold"]}
    return {"status": "rejected", "reasons": reasons + ["within-source skill CI95 lower bound not > 0 on any source"]}


def combine_beam_variants(variants: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """R8: the gate decision must be identical under every KU beam reading, else rejected: unresolved input."""
    statuses = {k: v["status"] for k, v in variants.items()}
    primary_key = sorted(variants)[0]
    if len(set(statuses.values())) > 1:
        return {"status": "rejected", "reasons": ["unresolvedInput: decision differs between beam readings "
                                                  + ", ".join(f"{k}={v}" for k, v in sorted(statuses.items()))],
                "beamStatuses": statuses}
    out = dict(variants[primary_key])
    out["beamStatuses"] = statuses
    return out


def kfold_idx(fk: "FineKernel", idx: np.ndarray, k: int, seed: int) -> List[Tuple[np.ndarray, np.ndarray]]:
    """grouped_kfold on row indices of a FineKernel (same fold rule, whole parameter sets per side)."""
    idx = np.asarray(idx, dtype=int)
    keys = [fk.set_keys[g] for g in fk.set_idx[idx]]
    fold_of = fold_assignment(keys, k, seed)
    fid = np.array([fold_of[kk] for kk in keys])
    return [(idx[fid != f], idx[fid == f]) for f in range(k) if (fid == f).any()]


def fit_power_law(fk: "FineKernel", idx: np.ndarray, q: str) -> Dict[str, Any]:
    """Physics-free reference: ln q = c + a ln P + b ln v + e ln d on per-set mean ln q (constant features dropped)."""
    idx = np.asarray(idx, dtype=int)
    sets, inv = np.unique(fk.set_idx[idx], return_inverse=True)
    y = np.bincount(inv, weights=fk.lnmeas(q)[idx]) / np.bincount(inv)
    feats = []
    for name in ("power_W", "speed_mm_s", "beamDiameter_um"):
        col = np.array([float(fk.rows[i][name]) for i in idx])
        first = np.zeros(len(sets))
        first[inv] = col
        feats.append((name, first))
    used = [(n, f) for n, f in feats if np.ptp(f) > 0]
    X = np.column_stack([np.ones(len(sets))] + [np.log(f) for _, f in used])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    return {"intercept": float(coef[0]), "exponents": {n: float(c) for (n, _), c in zip(used, coef[1:])},
            "nTrainSets": int(len(sets))}


def predict_power_law(fk: "FineKernel", idx: np.ndarray, model: Dict[str, Any]) -> np.ndarray:
    idx = np.asarray(idx, dtype=int)
    ln = np.full(idx.size, model["intercept"])
    for name, e in model["exponents"].items():
        ln += e * np.log(np.array([float(fk.rows[i][name]) for i in idx]))
    return np.exp(ln)
