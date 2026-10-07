"""Cell pipeline of the LPBF calibration scorecard: rung selection (training data only), P1 within-source and
P2 leave-one-source-out evaluation, leak-free intervals, physics-compensation flags and gate evidence.

Pure numpy on ``FineKernel`` arrays (no solver). A "cell" is (kernel, alloy, quantity). Every fit sees only
trainable (non-catalog) rows (``assert_trainable``); catalog sentinels are evaluated through ``predict_rung`` on a
separate FineKernel and never reach a fit, a final fit, ``s_source`` or the gate (R1).

HELD-OUT CALIBRATION OF NUISANCE PARAMETERS, NOT EXPERIMENTAL VALIDATION.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

import lpbf_calibration_stats as st

QUANTITIES = ("width", "depth")
RUNGS_FOR = {"width": ("eta", "eta2"), "depth": ("eta", "eta2", "eta2+dOffset")}


def _cfg_prior(cfg: Dict[str, Any], material: str) -> float:
    return float(cfg["materialDefaults"][material])


def alloy_of(fk: st.FineKernel, i: int) -> str:
    return fk.rows[i]["material"]


def alloy_idx(fk: st.FineKernel, material: str, sources: Optional[Sequence[str]] = None) -> np.ndarray:
    m = np.array([r["material"] == material for r in fk.rows])
    if sources is not None:
        m &= np.isin(fk.source_idx, [fk.sources.index(s) for s in sources if s in fk.sources])
    return np.flatnonzero(m)


def sources_of(fk: st.FineKernel, idx: np.ndarray) -> List[str]:
    return [fk.sources[s] for s in np.unique(fk.source_idx[np.asarray(idx, int)])]


def _guard(fk: st.FineKernel, idx: np.ndarray, cfg: Dict[str, Any]) -> None:
    st.assert_trainable([fk.rows[i] for i in np.asarray(idx, int)], cfg["dataRoles"]["catalogSentinels"])


# ---------------------------------------------------------------------------------------------
# rung selection inside the training data only (R3)
# ---------------------------------------------------------------------------------------------
def select_rung(fk: st.FineKernel, train_idx: np.ndarray, q: str, cfg: Dict[str, Any], prior: float) -> Dict[str, Any]:
    """Pick the ladder rung that serves quantity q from the TRAINING rows alone (inner LOSO when >= 2 training
    sources, else inner grouped k-fold over parameter sets). Held-out measurements are never read."""
    train_idx = np.asarray(train_idx, dtype=int)
    _guard(fk, train_idx, cfg)
    sel_cfg = cfg["rungSelection"]
    srcs = np.unique(fk.source_idx[train_idx])
    n_sets_src = {int(s): int(len(np.unique(fk.set_idx[train_idx[fk.source_idx[train_idx] == s]]))) for s in srcs}
    sw = st.source_weights(n_sets_src, cfg["sourceWeight"]["nSetsFull"])
    folds_by_seed: List[List] = []
    if len(srcs) >= 2:
        scheme = "inner leave-one-source-out"
        folds_by_seed.append([(train_idx[fk.source_idx[train_idx] != s], train_idx[fk.source_idx[train_idx] == s]) for s in srcs])
    else:
        scheme = f"inner grouped {sel_cfg['innerKFold']}-fold, seeds {sel_cfg['innerSeeds']}"
        for seed in sel_cfg["innerSeeds"]:
            folds_by_seed.append(st.kfold_idx(fk, train_idx, sel_cfg["innerKFold"], seed))
    rungs = RUNGS_FOR[q]
    rel = {r: [] for r in rungs}
    worse = {r: False for r in rungs}
    for folds in folds_by_seed:
        te_all, pred = [], {r: [] for r in ("default",) + tuple(rungs)}
        oks = {r: [] for r in pred}
        for tr, te in folds:
            fit = st.fit_ladder(fk, tr, cfg, prior)
            te_all.append(te)
            for r in pred:
                p, ok = st.predict_rung(fk, te, r, fit, q)
                pred[r].append(p)
                oks[r].append(ok)
        te_cat = np.concatenate(te_all)
        meas = fk.meas(q)[te_cat]
        src_of = fk.source_idx[te_cat]
        P = {r: np.concatenate(pred[r]) for r in pred}
        K = {r: np.concatenate(oks[r]) for r in pred}
        for r in rungs:
            common = K["default"] & K[r]
            if K[r].sum() < K["default"].sum():
                worse[r] = True
            if not common.any():
                rel[r].append(-1.0)
                continue
            num = den = 0.0
            for s, w in sw.items():
                m = common & (src_of == s)
                if not m.any():
                    continue
                num += w * float(np.mean(np.abs(P[r][m] - meas[m]) / meas[m]))
                den += w * float(np.mean(np.abs(P["default"][m] - meas[m]) / meas[m]))
            rel[r].append(1.0 - num / den if den > 0 else 0.0)
    relm = {r: float(np.mean(v)) for r, v in rel.items()}
    margin = cfg["rungMarginRel"]
    eligible = {r: (relm[r] > margin and not worse[r]) for r in rungs}
    if "eta" in eligible and not (relm.get("eta2", -1.0) > 0 and not worse.get("eta2", True)):
        eligible["eta"] = False  # R3: the joint eta may not serve q unless the q-specific fit also improves q
    cand = [r for r in rungs if eligible[r]]
    chosen = "default"
    if cand:
        best = max(relm[r] for r in cand)
        chosen = next(r for r in rungs if eligible[r] and relm[r] >= best - margin)
    return {"rung": chosen, "innerRelativeGain": relm, "eligible": eligible, "unresolvedWorse": worse,
            "scheme": scheme, "margin": margin}


def serve(fk: st.FineKernel, train_idx: np.ndarray, cfg: Dict[str, Any], prior: float, bootstrap: bool = False,
          seed: int = 0) -> Dict[str, Any]:
    train_idx = np.asarray(train_idx, dtype=int)
    _guard(fk, train_idx, cfg)
    fit = st.fit_ladder(fk, train_idx, cfg, prior, bootstrap=bootstrap, seed=seed)
    sel = {q: select_rung(fk, train_idx, q, cfg, prior) for q in QUANTITIES}
    return {"fit": fit, "sel": sel, "trainSources": sources_of(fk, train_idx)}


# ---------------------------------------------------------------------------------------------
# residuals and intervals (R6)
# ---------------------------------------------------------------------------------------------
def oof_residuals(fk: st.FineKernel, idx: np.ndarray, rung: str, q: str, cfg: Dict[str, Any], prior: float,
                  seed: int = 0) -> np.ndarray:
    """ln(meas / pred) of the served rung on out-of-fold rows of ONE training source (rung fixed, theta refit)."""
    idx = np.asarray(idx, dtype=int)
    k = min(cfg["p1"]["k"], max(2, len(np.unique(fk.set_idx[idx]))))
    out = []
    for tr, te in st.kfold_idx(fk, idx, k, seed):
        fit = st.fit_ladder(fk, tr, cfg, prior)
        p, ok = st.predict_rung(fk, te, rung, fit, q)
        out.append(fk.lnmeas(q)[te][ok] - np.log(p[ok]))
    return np.concatenate(out) if out else np.array([])


def source_mean_residual(fk: st.FineKernel, source: str, rung: str, q: str, cfg: Dict[str, Any],
                         exclude: Sequence[str]) -> Optional[float]:
    """Mean ln(meas/pred) of ``source`` at a theta fitted WITHOUT that source and WITHOUT ``exclude`` (default eta
    when no training source of its alloy is left)."""
    idx = fk.subset_idx(source=source)
    if idx.size == 0:
        return None
    material = fk.rows[int(idx[0])]["material"]
    banned = set(exclude) | {source} | set(cfg["dataRoles"]["catalogSentinels"])
    pool_sources = [s for s in sources_of(fk, alloy_idx(fk, material)) if s not in banned]
    pool = fk.subset_idx(sources=pool_sources) if pool_sources else np.array([], int)
    pool = pool[np.isin(pool, alloy_idx(fk, material))] if pool.size else pool
    r_use = rung
    fit = None
    if pool.size:
        _guard(fk, pool, cfg)
        fit = st.fit_ladder(fk, pool, cfg, _cfg_prior(cfg, material))
    else:
        r_use = "default"
    p, ok = st.predict_rung(fk, idx, r_use, fit, q)
    if not ok.any():
        return None
    return float(np.mean(fk.lnmeas(q)[idx][ok] - np.log(p[ok])))


def interval_params(fk: st.FineKernel, train_idx: np.ndarray, rung: str, q: str, cfg: Dict[str, Any], prior: float,
                    exclude_sources: Sequence[str]) -> Dict[str, Any]:
    """m, s_within from out-of-fold residuals inside the training sources; s_source from the OTHER trainable
    sources (never the held-out one, never residuals at a theta fitted with it), chi-square inflated."""
    train_idx = np.asarray(train_idx, dtype=int)
    res = []
    for s in sources_of(fk, train_idx):
        sidx = train_idx[fk.source_idx[train_idx] == fk.sources.index(s)]
        r = oof_residuals(fk, sidx, rung, q, cfg, prior)
        if r.size:
            res.append(r)
    allr = np.concatenate(res) if res else np.array([])
    m = float(np.median(allr)) if allr.size else 0.0
    s_within = st.robust_sd(allr) if allr.size else 0.0
    others = [s for s in cfg["dataRoles"]["trainable"] if s in fk.sources and s not in set(exclude_sources)]
    means = {}
    for o in others:
        v = source_mean_residual(fk, o, rung, q, cfg, exclude_sources)
        if v is not None:
            means[o] = v
    ic = cfg["interval"]
    ssrc = st.source_sd_inflated(list(means.values()), ic["chi2Level"] if "chi2Level" in ic else 0.10,
                                 ic["minSourcesForSSource"])
    return {"m": m, "sWithin": s_within, "nOofResiduals": int(allr.size),
            "sSource": None if ssrc is None else ssrc["sdUpper"], "sSourceRaw": None if ssrc is None else ssrc["sd"],
            "sSourceInflation": None if ssrc is None else ssrc["inflation"],
            "nSourcesForSSource": len(means), "sourceMeanResiduals": means, "excludedSources": sorted(exclude_sources)}


def interval_factors(ip: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if ip["sSource"] is None:
        return {"available": False, "reason": f"fewer than {cfg['interval']['minSourcesForSSource']} other sources "
                                              "for the between-source term"}
    z_table = {float(k): v for k, v in cfg["interval"]["z"].items()}
    for level in cfg["interval"]["levels"]:
        lo, hi = st.conformal_interval(ip["m"], ip["sWithin"], ip["sSource"], level, z_table)
        out[f"{int(round(level * 100))}"] = {"lo": lo, "hi": hi, "widthRatio": hi / lo,
                                             "notInformative": (hi / lo) > cfg["interval"]["notInformativeRatio"]}
    out["available"] = True
    return out


# ---------------------------------------------------------------------------------------------
# held-out evaluation of the ladder on a test row set
# ---------------------------------------------------------------------------------------------
def evaluate_rungs(fk: st.FineKernel, test_idx: np.ndarray, train_idx: np.ndarray, fit: Optional[Dict[str, Any]],
                   served_rung: str, q: str, cfg: Dict[str, Any], seed: int = 0, fk_test: Optional[st.FineKernel] = None,
                   with_powerlaw: bool = True) -> Dict[str, Any]:
    """Metrics of default, every ladder rung and the physics-free power law on ``test_idx`` (of ``fk_test``, default
    ``fk``). MAPE is on the rows resolved by default AND the rung; unresolved rows are counted (and scored as a
    100 % failure in ``mapeUnresolvedAsFail``). Skill vs default / power law is a paired test-set cluster bootstrap
    with theta fixed."""
    ft = fk_test or fk
    test_idx = np.asarray(test_idx, dtype=int)
    meas = ft.meas(q)[test_idx]
    cluster = ft.set_idx[test_idx]
    B = cfg["bootstrap"]["skillReplicates"]
    pd_, ok_d = st.predict_rung(ft, test_idx, "default", None, q)
    pl = None
    if with_powerlaw and len(train_idx):
        pl_model = st.fit_power_law(fk, train_idx, q)
        pl = st.predict_power_law(ft, test_idx, pl_model)
    out: Dict[str, Any] = {"n": int(test_idx.size), "nParameterSets": int(len(np.unique(cluster))),
                           "rungs": {}, "servedRung": served_rung}
    names = ("default",) + RUNGS_FOR[q]
    for r in names:
        p, ok = st.predict_rung(ft, test_idx, r, fit, q)
        common = ok & ok_d
        mm = st.metrics(p, meas, common)
        rec = {"metrics": mm, "nResolved": int(ok.sum()), "unresolved": int((~ok).sum()),
               "mapeUnresolvedAsFail": st.mape_unresolved_as_fail(p, meas, ok)}
        if r == "default":
            rec["skillVsDefault"] = None
        else:
            sk = st.paired_skill(p, pd_, meas, common, cluster, B, seed)
            sk["verdict"] = st.verdict_from_ci(sk["ci95"])
            rec["skillVsDefault"] = sk
        if pl is not None and r != "default":
            skp = st.paired_skill(p, pl, meas, ok, cluster, B, seed)
            skp["verdict"] = st.verdict_from_ci(skp["ci95"])
            rec["skillVsPowerlaw"] = skp
        out["rungs"][r] = rec
    if pl is not None:
        out["rungs"]["powerlaw"] = {"metrics": st.metrics(pl, meas, np.ones(test_idx.size, dtype=bool)),
                                    "nResolved": int(test_idx.size), "unresolved": 0, "referenceOnly": True}
    return out


def class_cut(fk: st.FineKernel, test_idx: np.ndarray, fit: Optional[Dict[str, Any]], served_rung: str, q: str) -> Dict[str, Any]:
    out = {}
    test_idx = np.asarray(test_idx, dtype=int)
    for ci, name in enumerate(st.CLASSES):
        sub = test_idx[fk.cls[test_idx] == ci]
        if sub.size == 0:
            continue
        pd_, okd = st.predict_rung(fk, sub, "default", None, q)
        ps, oks = st.predict_rung(fk, sub, served_rung, fit, q)
        common = okd & oks
        meas = fk.meas(q)[sub]
        out[name] = {"n": int(sub.size), "mapeDefault": st.metrics(pd_, meas, common)["mapePct"],
                     "mapeServed": st.metrics(ps, meas, common)["mapePct"], "unresolvedServed": int((~oks).sum())}
    return out


def served_block(fk: st.FineKernel, test_idx: np.ndarray, fit: Optional[Dict[str, Any]], rung: str, q: str,
                 ip: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Coverage of the source-aware interval for the served rung on the test rows."""
    test_idx = np.asarray(test_idx, dtype=int)
    p, ok = st.predict_rung(fk, test_idx, rung, fit, q)
    meas = fk.meas(q)[test_idx]
    fac = interval_factors(ip, cfg)
    out: Dict[str, Any] = {"interval": fac, "coverage": {}}
    if fac.get("available"):
        for lvl in ("80", "90"):
            out["coverage"][lvl] = st.coverage(meas, p, fac[lvl]["lo"], fac[lvl]["hi"], ok)
    return out


# ---------------------------------------------------------------------------------------------
# physics-compensation flags (R5)
# ---------------------------------------------------------------------------------------------
def physics_flags(fit: Optional[Dict[str, Any]], rung: str, q: str, cfg: Dict[str, Any], class_sets: Dict[str, int],
                  material: str) -> Dict[str, Any]:
    """Physics-compensation diagnostics (R5), computed for EVERY fitted cell, also when the served rung is `default`.

    ``diagnosticFlags`` always reflect the fit (bound hit, eta_W/eta_D divergence, dominant class offset, eta vs measured
    absorptance). ``flags`` keeps the gate semantics: a flag only counts for the gate when the served rung actually uses
    the offending parameter (``gateRelevant`` is False for a `default` rung, where the diagnostics are shown but cannot
    veto anything because nothing is served)."""
    g = cfg["gate"]
    names = ("boundHit", "etaSplit", "offsetDominant", "etaInconsistentWithMeasuredAbsorptance")
    dflags = {n: False for n in names}
    gflags = {n: False for n in names}
    notes: List[str] = []
    diag: Dict[str, Any] = {}
    if fit is None:
        return {"flags": gflags, "diagnosticFlags": dflags, "gateRelevant": False, "notes": notes, "diagnostics": diag}
    uses = rung != "default"
    boot = fit.get("boot") or {}
    key = "J" if rung == "eta" else ("W" if q == "width" else "D")
    eta_key = "etaJ" if key == "J" else "eta" + key
    bf = (boot.get(key) or {}).get("boundHitFraction") or 0.0
    diag["boundHitBootstrapFraction"] = bf
    if fit["boundHit"][key] or bf > g["boundHitBootstrapFraction"]:
        dflags["boundHit"] = True
        gflags["boundHit"] = uses
        notes.append(f"boundHit: eta ({key}) {fit[eta_key]:.3f} within {g['boundHitSteps']} fine-grid step "
                     f"of a bound or in > {int(100 * g['boundHitBootstrapFraction'])} % of bootstrap replicates"
                     + ("" if uses else " (diagnostic only: default rung served)"))
    ew, ed = fit.get("etaW"), fit.get("etaD")
    if ew and ed:
        ratio = abs(math.log(ed / ew))
        diag["etaSplitLn"] = ratio
        if ratio > math.log(g["etaSplitRatio"]):
            dflags["etaSplit"] = True
            two_etas = rung in ("eta2", "eta2+dOffset")
            gflags["etaSplit"] = two_etas
            notes.append(f"etaSplit: |ln(eta_D/eta_W)| = {ratio:.2f} > ln {g['etaSplitRatio']} "
                         f"(eta_W {ew:.3f}, eta_D {ed:.3f}): one physical absorptivity cannot be both"
                         + ("" if two_etas else " (diagnostic only: the served rung does not use two separate etas)"))
    cd = fit.get("cd") or {}
    if cd:
        worst = max(abs(v) for v in cd.values())
        diag["maxAbsCd"] = worst
        if worst > math.log(g["offsetDominantRatio"]) and q == "depth":
            dflags["offsetDominant"] = True
            used = rung == "eta2+dOffset"
            gflags["offsetDominant"] = used
            notes.append(f"offsetDominant: |c_D| {worst:.2f} > ln {g['offsetDominantRatio']} for a class"
                         + ("" if used else " (diagnostic only: the served rung has no class offset)"))
    eta_q = fit.get("etaJ") if rung == "eta" else (ew if q == "width" else ed)
    if eta_q is not None and material in cfg["absorptanceBands"]:
        mism = st.absorptance_disagreement(eta_q, class_sets, cfg["absorptanceBands"][material] | {
            "widenFactor": cfg["absorptanceBands"]["widenFactor"]}, cfg["minSetsPerClass"])
        if mism:
            dflags["etaInconsistentWithMeasuredAbsorptance"] = True
            gflags["etaInconsistentWithMeasuredAbsorptance"] = uses
            notes.append("etaInconsistentWithMeasuredAbsorptance: fitted effective eta disagrees with measured "
                         "absorptance (" + "; ".join(f"{m['class']} band {m['band'][0]:.2f}-{m['band'][1]:.2f}, "
                                                     f"eta {m['eta']:.3f}" for m in mism) +
                         ") -> eta is absorbing model error (diagnostic, not a validation claim)"
                         + ("" if uses else " (diagnostic only: default rung served)"))
        diag["absorptanceMismatch"] = mism
    return {"flags": gflags, "diagnosticFlags": dflags, "gateRelevant": uses, "notes": notes, "diagnostics": diag}


def class_set_counts(fk: st.FineKernel, idx: np.ndarray) -> Dict[str, int]:
    idx = np.asarray(idx, dtype=int)
    out = {}
    for ci, name in enumerate(st.CLASSES):
        out[name] = int(len(np.unique(fk.set_idx[idx[fk.cls[idx] == ci]])))
    return out


def eta_of(fit: Optional[Dict[str, Any]], rung: str, q: str):
    if fit is None or rung == "default":
        return None, None
    key = "J" if rung == "eta" else ("W" if q == "width" else "D")
    eta = fit["etaJ"] if key == "J" else fit["eta" + key]
    ci = ((fit.get("boot") or {}).get(key) or {}).get("ci90")
    return eta, ci


# ---------------------------------------------------------------------------------------------
# P1 within-source grouped k-fold (nested rung selection) and P2 leave-one-source-out
# ---------------------------------------------------------------------------------------------
def run_p1(fk: st.FineKernel, source: str, cfg: Dict[str, Any], prior: float) -> Dict[str, Any]:
    """Out-of-fold served-rung predictions inside ONE source: the rung is selected from each fold's training part
    only (nested), then scored on the fold's test part."""
    idx = fk.subset_idx(source=source)
    n_sets = int(len(np.unique(fk.set_idx[idx])))
    p1 = cfg["p1"]
    B = cfg["bootstrap"]["skillReplicates"]
    out: Dict[str, Any] = {"source": source, "nRows": int(idx.size), "nParameterSets": n_sets, "k": p1["k"],
                           "seeds": p1["seeds"], "byQuantity": {}}
    for q in QUANTITIES:
        per_seed = []
        for si, seed in enumerate(p1["seeds"]):
            P, OK, PD, OKD, rows, rung_counts = [], [], [], [], [], {}
            for tr, te in st.kfold_idx(fk, idx, p1["k"], seed):
                sv = serve(fk, tr, cfg, prior)
                rung = sv["sel"][q]["rung"]
                rung_counts[rung] = rung_counts.get(rung, 0) + 1
                p, ok = st.predict_rung(fk, te, rung, sv["fit"], q)
                pd_, okd = st.predict_rung(fk, te, "default", None, q)
                P.append(p)
                OK.append(ok)
                PD.append(pd_)
                OKD.append(okd)
                rows.append(te)
            te_all = np.concatenate(rows)
            p, ok, pd_, okd = (np.concatenate(x) for x in (P, OK, PD, OKD))
            meas = fk.meas(q)[te_all]
            common = ok & okd
            sk = st.paired_skill(p, pd_, meas, common, fk.set_idx[te_all], B if si == 0 else 1, seed)
            rec = {"seed": seed, "skill": sk["skill"], "ci95": sk["ci95"] if si == 0 else None,
                   "mapeServed": sk["mapeA"], "mapeDefault": sk["mapeB"], "nCommon": sk["n"],
                   "unresolvedServed": int((~ok).sum()), "unresolvedDefault": int((~okd).sum()),
                   "rungChoices": rung_counts,
                   "mapeUnresolvedAsFailServed": st.mape_unresolved_as_fail(p, meas, ok),
                   "mapeUnresolvedAsFailDefault": st.mape_unresolved_as_fail(pd_, meas, okd)}
            per_seed.append(rec)
        out["byQuantity"][q] = {"primary": per_seed[0], "seeds": per_seed}
    return out


def run_p2_fold(fk: st.FineKernel, alloy: str, held_out: str, cfg: Dict[str, Any], seed: int) -> Dict[str, Any]:
    prior = _cfg_prior(cfg, alloy)
    train_sources = [s for s in sources_of(fk, alloy_idx(fk, alloy)) if s != held_out]
    train = fk.subset_idx(sources=train_sources)
    train = train[np.isin(train, alloy_idx(fk, alloy))]
    test = fk.subset_idx(source=held_out)
    st.assert_no_leak([fk.rows[i] for i in train], [fk.rows[i] for i in test], by_source=True)
    sv = serve(fk, train, cfg, prior, bootstrap=True, seed=seed)
    fit = sv["fit"]
    rec: Dict[str, Any] = {"heldOutSource": held_out, "trainSources": train_sources, "nTestRows": int(test.size),
                           "nTestSets": int(len(np.unique(fk.set_idx[test]))), "nTrainRows": int(train.size),
                           "nTrainSets": int(len(np.unique(fk.set_idx[train]))), "fit": fit, "selection": sv["sel"],
                           "byQuantity": {}}
    class_sets = class_set_counts(fk, train)
    for q in QUANTITIES:
        rung = sv["sel"][q]["rung"]
        ev = evaluate_rungs(fk, test, train, fit, rung, q, cfg, seed)
        ip = interval_params(fk, train, rung, q, cfg, prior, exclude_sources=[held_out])
        sb = served_block(fk, test, fit, rung, q, ip, cfg)
        ev["servedRung"] = rung
        ev["intervalParams"] = ip
        ev["served"] = sb
        ev["byRegimeClass"] = class_cut(fk, test, fit, rung, q)
        ev["flags"] = physics_flags(fit, rung, q, cfg, class_sets, alloy)
        rec["byQuantity"][q] = ev
    # label cut (Hofmann balling flag): reported only, never used for fitting the width
    bal = test[fk.balling[test] == 1]
    if bal.size:
        rec["ballingLabelCut"] = {}
        for q in QUANTITIES:
            rung = sv["sel"][q]["rung"]
            rec["ballingLabelCut"][q] = {}
            for name, sub in (("balling-flagged", bal), ("not-flagged", test[fk.balling[test] == 0])):
                if sub.size == 0:
                    continue
                pd_, okd = st.predict_rung(fk, sub, "default", None, q)
                ps, oks = st.predict_rung(fk, sub, rung, fit, q)
                common = okd & oks
                meas = fk.meas(q)[sub]
                rec["ballingLabelCut"][q][name] = {
                    "n": int(sub.size), "mapeDefault": st.metrics(pd_, meas, common)["mapePct"],
                    "mapeServed": st.metrics(ps, meas, common)["mapePct"]}
    return rec


def analyze_kernel_alloy(fk: st.FineKernel, alloy: str, cfg: Dict[str, Any], seed: int = 0) -> Dict[str, Any]:
    """Everything for one (kernel, alloy): final fit on ALL trainable sources, P1, P2 (both directions when the
    alloy has two or more sources) and the gate evidence/status per quantity."""
    prior = _cfg_prior(cfg, alloy)
    a_idx = alloy_idx(fk, alloy)
    sources = sources_of(fk, a_idx)
    final_sv = serve(fk, a_idx, cfg, prior, bootstrap=True, seed=seed)
    fit = final_sv["fit"]
    res: Dict[str, Any] = {"alloy": alloy, "sources": sources,
                           "nRowsBySource": {s: int(len(fk.subset_idx(source=s))) for s in sources},
                           "nSetsBySource": {s: int(len(np.unique(fk.set_idx[fk.subset_idx(source=s)]))) for s in sources},
                           "final": {"fit": fit, "selection": final_sv["sel"]}, "p1": {}, "p2": {}, "cells": {}}
    # sensitivity: do the balling-flagged Hofmann rows change eta_W when they are allowed to train width?
    if int(fk.balling[a_idx].sum()) > 0:
        cfg_alt = dict(cfg, ballingFlaggedRowsTrainWidth=True)
        alt = st.fit_ladder(fk, a_idx, cfg_alt, prior)
        res["ballingSensitivity"] = {"etaW_excludingBalling": fit["etaW"] if fit else None,
                                     "etaW_includingBalling": alt["etaW"] if alt else None,
                                     "nBallingRows": int(fk.balling[a_idx].sum())}
    res["p1Skipped"] = []
    for s in sources:
        if res["nSetsBySource"][s] >= cfg["p1"]["minSetsPerSource"]:
            res["p1"][s] = run_p1(fk, s, cfg, prior)
        else:
            res["p1Skipped"].append({"source": s, "nSets": res["nSetsBySource"][s],
                                     "reason": f"fewer than {cfg['p1']['minSetsPerSource']} parameter sets: no within-source "
                                               f"grouped {cfg['p1']['k']}-fold"})
    two = len(sources) >= 2
    if two:
        for s in sources:
            res["p2"][s] = run_p2_fold(fk, alloy, s, cfg, seed)
    class_sets = class_set_counts(fk, a_idx)
    for q in QUANTITIES:
        rung = final_sv["sel"][q]["rung"]
        ip = interval_params(fk, a_idx, rung, q, cfg, prior, exclude_sources=[])
        fl = physics_flags(fit, rung, q, cfg, class_sets, alloy)
        eta, ci = eta_of(fit, rung, q)
        cell: Dict[str, Any] = {"servedRung": rung, "selection": final_sv["sel"][q], "eta": eta, "etaCi90": ci,
                                "interval": interval_factors(ip, cfg), "intervalParams": ip, "flags": fl}
        p2ev, fold_etas = [], {}
        unresolved_worse = bool(final_sv["sel"][q]["unresolvedWorse"].get(rung, False)) if rung != "default" else False
        for s, rec in res["p2"].items():
            qe = rec["byQuantity"][q]
            served = qe["rungs"].get(qe["servedRung"], {})
            if qe["servedRung"] != "default":
                sk = served.get("skillVsDefault") or {}
            else:
                sk = {"skill": 0.0, "ci95": [0.0, 0.0]}
            cov90 = qe["served"]["coverage"].get("90") if qe["served"]["coverage"] else None
            un_r = served.get("unresolved", 0) if qe["servedRung"] != "default" else 0
            un_d = qe["rungs"]["default"]["unresolved"]
            p2ev.append({"source": s, "skillLb95": (sk.get("ci95") or [None])[0], "skill": sk.get("skill"),
                         "coverage90N": cov90["n"] if cov90 else 0,
                         "coverage90WilsonUpper": cov90["wilson95"][1] if cov90 and cov90.get("wilson95") else None,
                         "unresolvedRung": un_r, "unresolvedDefault": un_d})
            if un_r > un_d:
                unresolved_worse = True
            e, c = eta_of(rec["fit"], qe["servedRung"], q)
            fold_etas[s] = {"eta": e, "ci90": c, "rung": qe["servedRung"]}
        p1ev = []
        for s, rec in res["p1"].items():
            pr = rec["byQuantity"][q]["primary"]
            p1ev.append({"source": s, "lb": (pr["ci95"] or [None])[0], "skill": pr["skill"]})
            if pr["unresolvedServed"] > pr["unresolvedDefault"]:
                unresolved_worse = True
        consistent = None
        if len(fold_etas) == 2:
            (_, a), (_, b) = sorted(fold_etas.items())
            if a["eta"] and b["eta"]:
                consistent = st.eta_consistent(a["eta"], a["ci90"], b["eta"], b["ci90"], cfg["gate"]["etaConsistencyDLn"])
        cell["foldEtas"] = fold_etas
        cell["etaConsistent"] = consistent
        ev = {"noData": False, "hasSecondSource": two, "servedRung": rung, "p2": p2ev, "p1": p1ev,
              "flags": fl["flags"], "etaConsistent": consistent, "unresolvedWorse": unresolved_worse}
        cell["evidence"] = ev
        cell["gate"] = st.gate_cell(ev, cfg["gate"])
        res["cells"][q] = cell
    return res
