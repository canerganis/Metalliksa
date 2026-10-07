#!/usr/bin/env python3
"""LPBF melt-pool calibration scorecard and calibration artefact (one command: ``npm run lpbf:calibration``).

HELD-OUT CALIBRATION OF NUISANCE PARAMETERS, NOT EXPERIMENTAL VALIDATION. The three frozen screening kernels
(eagar-tsai, goldak, rosenthal; ``calculate_meltpool_physics`` on the CPU flat-plate path, read-only) are evaluated
on an absorptivity grid for every measured track; effective absorptivity (and an optional depth log-offset per
input-only regime class) is fitted OUTSIDE the frozen files and scored on rows and sources the fit never saw.

Outputs (written together, byte-deterministic for one kernel table):
  data/calibration/lpbf-meltpool-calibration-v1.json   versioned, hashed artefact (cells carry a gate status)
  docs/LPBF_CALIBRATION_SCORECARD_<date>.json          full scorecard record
  docs/LPBF_CALIBRATION_SCORECARD_<date>.view.json     slim record read by the scorecard view in the app
  docs/LPBF_CALIBRATION_SCORECARD_<date>.md            rendered text

Data roles (R1): trainable sources fit/score/gate; catalog sentinels (Guo, NIST IN718: used while the physics was
developed, so NOT blind) are test-only and reported in a separate block. The evidence label of everything stays
``screening-only``; this tool derives no label from scores.

Usage (from the repo root; PYTHONDONTWRITEBYTECODE=1):
    python -B python/tools/lpbf_calibration_fit.py --table-cache .runtime/cache/lpbf_calib_table.json --jobs 12 --date 2026-10-07
    python -B python/tools/lpbf_calibration_fit.py --quick ...     # first 40 rows per source, smoke run
    python -B python/tools/lpbf_calibration_fit.py --check ...     # re-render from the written JSON, fail on drift
"""

from __future__ import annotations

import argparse
import datetime
import contextlib
import hashlib
import io
import json
import math
import multiprocessing
import platform
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

PYTHON_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = PYTHON_DIR.parent
sys.path.insert(0, str(PYTHON_DIR))

import lpbf_calibration_cells as cl  # noqa: E402
import lpbf_calibration_stats as st  # noqa: E402
from lpbf_calibration_config import (  # noqa: E402
    ARTEFACT_REL_PATH, CALIBRATION_CONFIG as CFG, CALIBRATION_SCHEMA, CATALOG_SOURCES, KERNELS, SCORECARD_SCHEMA,
    SCORECARD_VIEW_SCHEMA, TRAINABLE_SOURCES, canonical_json, config_sha256)

TABLE_SCHEMA = "lpbf-calibration-kernel-table-1"
DEFAULT_HATCH_UM = 100.0
NOMINAL_LAYER_FOR_BARE_UM = 30.0
GENERATED_AT_DEFAULT = None  # None = today; a record is never silently rewritten under an older date
EVIDENCE_KIND = "screening-only"
EVIDENCE_LABEL = "Screening only: nuisance parameters fitted to published tracks; not validation"
LABEL_PROMOTION = "none"
HONESTY = ("calibration of nuisance parameters against published single tracks; not experimental validation; the "
           "frozen screening kernels are read-only; absorptivity is a fitted effective parameter that absorbs model "
           "error, not a measured one; estimated material laws; no per-row measurement uncertainty exists in any "
           "source; experimentalValidation=false, opticalOperatorMatched=false")
SENTINEL_TITLE = "catalog sentinels (used during physics development, not blind)"
BEAM_VARIANTS = (37.5, 75.0)
QS = ("width", "depth")
RUNG_LIST = ("default", "eta", "eta2", "eta2+dOffset")
SCORECARD_STEM = "LPBF_CALIBRATION_SCORECARD_"


# ---------------------------------------------------------------------------------------------
# rows
# ---------------------------------------------------------------------------------------------
def _classify(row: Dict[str, Any]) -> None:
    import lpbf_public_datasets as pd
    reg = pd.classify_regime(row["material"], row["power_W"], row["speed_mm_s"], row["beamDiameter_um"],
                             row["preheat_C"], row.get("balling"))
    row["normalizedEnthalpyDefault"] = reg["normalizedEnthalpy"]
    row["regimeClass"] = st.regime_class_from_enthalpy(reg["normalizedEnthalpy"])
    row["defaultAbsorptivity"] = float(pd.screening_props(row["material"])["absorptivity_IR"])


def load_rows(quick: bool = False, ku_beam_um: float = 37.5) -> Dict[str, Any]:
    """{'trainable': [...], 'catalog': [...], 'provenance': {source: {...}}} from the pinned loaders."""
    import lpbf_public_datasets as pd
    from meltpool_literature_catalog import TRACKS

    h = pd.load_hofmann_316l()
    t = pd.load_totis_ti64()
    ku = pd.load_ku_leuven_316l_ti64(beam_diameter_um=ku_beam_um)
    lane = pd.load_lane_in625()
    groups = {"hofmann-316l-2026": h["rows"], "totis-ti64-2021": t["rows"], "lane-in625-2020": lane["rows"]}
    for r in ku["rows"]:
        groups.setdefault(r["dataset"], []).append(r)
    trainable: List[Dict[str, Any]] = []
    prov: Dict[str, Any] = {}
    for sid in TRAINABLE_SOURCES:
        rows = groups[sid][:40] if quick else groups[sid]
        for r in rows:
            row = {"rowId": r["rowId"], "source": sid, "material": r["material"], "power_W": float(r["power_W"]),
                   "speed_mm_s": float(r["speed_mm_s"]), "beamDiameter_um": float(r["beamDiameter_um"]),
                   "preheat_C": float(r["preheat_C"]), "layer_um": r.get("layer_um"), "hatch_um": r.get("hatch_um"),
                   "width_um": float(r["width_um"]), "depth_um": float(r["depth_um"]), "balling": r.get("balling"),
                   "publishedLabel": r.get("publishedRegime"), "catalog": False}
            _classify(row)
            trainable.append(row)
    catalog: List[Dict[str, Any]] = []
    for c in TRACKS:
        if c.get("kind") != "measured":
            continue
        sid = "guo-316l-2024" if c["id"].startswith("guo") else ("nist-amb2022-03-in718" if c["id"].startswith("nist") else None)
        if sid is None:
            continue
        row = {"rowId": c["id"], "source": sid, "material": c["material"], "power_W": float(c["laserPower_W"]),
               "speed_mm_s": float(c["scanSpeed_mm_s"]), "beamDiameter_um": float(c["beamDiameter_um"]),
               "preheat_C": float(c["preheatTemp_C"]), "layer_um": 0.0, "hatch_um": None,
               "width_um": float(c["width_um"]), "depth_um": float(c["depth_um"]), "balling": None,
               "publishedLabel": None, "catalog": True, "doi": c.get("doi"), "citation": c.get("source")}
        _classify(row)
        catalog.append(row)
    sources = {
        "hofmann-316l-2026": {"doi": h["provenance"]["doi"], "tableSha256": h["provenance"]["fileSha256"],
                              "license": h["provenance"]["license"], "citation": h["provenance"]["citation"],
                              "loaderRows": len(h["rows"]), "loaderExcluded": []},
        "totis-ti64-2021": {"doi": t["provenance"]["doi"], "tableSha256": t["provenance"]["fileSha256"],
                            "license": t["provenance"]["license"], "citation": t["provenance"]["citation"],
                            "loaderRows": len(t["rows"]), "loaderExcluded": []},
        "lane-in625-2020": {"doi": lane["provenance"]["doi"], "tableSha256": lane["provenance"]["fileSha256"],
                            "license": lane["provenance"]["license"], "citation": lane["provenance"]["citation"],
                            "loaderRows": len(lane["rows"]), "loaderExcluded": []},
    }
    for sid in ("ku-leuven-316l-2021", "ku-leuven-ti64-2021"):
        files = [f for f in ku["provenance"]["sourceFiles"] if f["alloy"] == ("316L" if "316l" in sid else "Ti-6Al-4V")]
        sources[sid] = {"doi": " + ".join(f["doi"] for f in files), "tableSha256": ku["provenance"]["fileSha256"],
                        "license": ku["provenance"]["license"], "citation": ku["provenance"]["citation"],
                        "loaderRows": len(groups[sid]),
                        "loaderExcluded": [x for x in ku["provenance"]["notCompared"] if x["rowId"].startswith(sid)],
                        "beamDiameter_um": ku_beam_um, "beamDiameterStatus": ku["provenance"]["beamDiameterStatus"]}
    for sid, doi in (("guo-316l-2024", "10.3390/mi15020170"), ("nist-amb2022-03-in718", "10.1007/s40192-024-00355-5")):
        sources[sid] = {"doi": doi, "tableSha256": None, "license": "literature table (catalog)", "citation": None,
                        "loaderRows": sum(1 for r in catalog if r["source"] == sid), "loaderExcluded": [],
                        "role": "catalog-sentinel"}
    return {"trainable": trainable, "catalog": catalog, "provenance": sources}


# ---------------------------------------------------------------------------------------------
# kernel table (the expensive part; cached; byte-stable)
# ---------------------------------------------------------------------------------------------
def node_grid(defaults: Sequence[float]) -> List[float]:
    g = CFG["kernelGrid"]
    n = int(round((g["stop"] - g["start"]) / g["step"])) + 1
    vals = {round(g["start"] + i * g["step"], 6) for i in range(n)}
    vals.update(round(float(d), 6) for d in defaults)
    return sorted(vals)


def input_args(row: Dict[str, Any]) -> Tuple[str, float, float, float, float, float, float]:
    layer = row.get("layer_um")
    layer = layer if layer and layer > 0 else NOMINAL_LAYER_FOR_BARE_UM
    return (row["material"], float(row["power_W"]), float(row["speed_mm_s"]), float(row["beamDiameter_um"]),
            float(row["preheat_C"]), float(layer), float(row.get("hatch_um") or DEFAULT_HATCH_UM))


def input_key(row: Dict[str, Any]) -> str:
    a = input_args(row)
    return "|".join([a[0]] + [f"{x:g}" for x in a[1:]])


def _solver_call(args: Tuple, kernel: str, eta: Optional[float]) -> Tuple[Optional[float], Optional[float], str]:
    st.pin_flat_plate()
    from lpbf_thermal_solver import calculate_meltpool_physics
    material, P, v, d, preheat, layer, hatch = args
    kw: Dict[str, Any] = {}
    if eta is not None:
        kw["prop_overrides"] = {"absorptivity_IR": eta}
    captured = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured):
            res = calculate_meltpool_physics(material, P, v, d, preheat, layer, hatch, heat_source=kernel,
                                             absorption_model="flat-plate", **kw)
        g = res["meltPoolGeometry"]
        return float(g["width_um"]), float(g["depth_um"]), str(g.get("extentStatus"))
    except Exception as exc:  # recorded as data, never swallowed silently
        return None, None, f"error: {type(exc).__name__}"


def _worker(task: Tuple) -> Tuple[Optional[float], Optional[float], str]:
    return _solver_call(*task)


def build_table(inputs: Dict[str, Tuple], kernels: Sequence[str], nodes: Sequence[float], jobs: int = 1,
                solver: Optional[Callable[[Tuple, str, Optional[float]], Tuple]] = None,
                existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """{'entries': {inputKey: {kernel: {'W','D','s','dW','dD','ds'}}}, 'statuses': [...]}. ``solver`` is injected in
    offline tests (serial). Values are rounded to 6 significant digits so the cache is byte-stable."""
    entries: Dict[str, Any] = dict((existing or {}).get("entries", {}))
    statuses: List[str] = list((existing or {}).get("statuses", []))
    todo = [k for k in sorted(inputs) if k not in entries]
    tasks, index = [], []
    for key in todo:
        for k in kernels:
            for eta in list(nodes) + [None]:
                tasks.append((inputs[key], k, eta))
                index.append((key, k, eta))
    if solver is not None or jobs <= 1:
        fn = solver or _solver_call
        outs = [fn(*t) for t in tasks]
    else:
        ctx = multiprocessing.get_context("spawn")
        with ctx.Pool(jobs) as pool:
            outs = pool.map(_worker, tasks, chunksize=16)

    def code(s: str) -> int:
        if s not in statuses:
            statuses.append(s)
        return statuses.index(s)

    acc: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for (key, k, eta), (W, D, s) in zip(index, outs):
        a = acc.setdefault((key, k), {"W": [], "D": [], "s": []})
        wv = None if W is None else st.round_sig(W, 6)
        dv = None if D is None else st.round_sig(D, 6)
        if eta is None:
            a["dW"], a["dD"], a["ds"] = wv, dv, code(s)
        else:
            a["W"].append(wv)
            a["D"].append(dv)
            a["s"].append(code(s))
    for (key, k), a in acc.items():
        entries.setdefault(key, {})[k] = a
    return {"schema": TABLE_SCHEMA, "nodes": list(nodes), "kernels": list(kernels), "statuses": statuses,
            "entries": entries, "solverCalls": len(tasks) + int((existing or {}).get("solverCalls", 0))}


def load_or_build_table(rows_all: Sequence[Dict[str, Any]], fp: str, jobs: int, cache: Optional[Path],
                        nodes: Sequence[float], solver: Optional[Callable] = None) -> Tuple[Dict[str, Any], str]:
    inputs = {input_key(r): input_args(r) for r in rows_all}
    existing = None
    source = "computed"
    if cache and cache.is_file():
        cand = json.loads(cache.read_text(encoding="utf-8"))
        if cand.get("implementationHash") != fp:
            raise SystemExit(f"kernel table cache {cache} was built for implementation hash "
                             f"{cand.get('implementationHash')}, current {fp}: refused (delete it to rebuild)")
        if cand.get("nodes") != list(nodes) or cand.get("kernels") != list(KERNELS):
            raise SystemExit(f"kernel table cache {cache} has a different grid or kernel set: refused")
        existing = cand
        source = f"cache {cache.name}"
    missing = [k for k in inputs if not existing or k not in existing["entries"]]
    if missing:
        table = build_table({k: inputs[k] for k in missing}, KERNELS, nodes, jobs, solver, existing)
        table["implementationHash"] = fp
        source = "computed" if existing is None else f"{source} + {len(missing)} new inputs computed"
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(table, sort_keys=True, separators=(",", ":")), encoding="utf-8", newline="\n")
    else:
        table = existing
    return table, source


def fine_kernel(rows: Sequence[Dict[str, Any]], kernel: str, table: Dict[str, Any]) -> st.FineKernel:
    nodes = table["nodes"]
    K = len(nodes)
    statuses = table["statuses"]
    comp = np.array([s == "computed" for s in statuses])
    n = len(rows)
    lnW, lnD, ok = np.zeros((n, K)), np.zeros((n, K)), np.zeros((n, K), dtype=bool)
    dW, dD, dok = np.zeros(n), np.zeros(n), np.zeros(n, dtype=bool)
    dstat: List[str] = []
    for i, r in enumerate(rows):
        e = table["entries"][input_key(r)][kernel]
        w = np.array([np.nan if x is None else x for x in e["W"]], dtype=float)
        d = np.array([np.nan if x is None else x for x in e["D"]], dtype=float)
        s = np.array(e["s"], dtype=int)
        good = comp[s] & np.isfinite(w) & np.isfinite(d) & (w > 0) & (d > 0)
        ok[i] = good
        lnW[i] = np.where(good, np.log(np.where(good, w, 1.0)), 0.0)
        lnD[i] = np.where(good, np.log(np.where(good, d, 1.0)), 0.0)
        gd = comp[e["ds"]] and e["dW"] and e["dD"] and e["dW"] > 0 and e["dD"] > 0
        dok[i] = bool(gd)
        dW[i] = e["dW"] if gd else np.nan
        dD[i] = e["dD"] if gd else np.nan
        dstat.append(statuses[e["ds"]])
    fk = st.FineKernel(rows, nodes, lnW, lnD, ok, dW, dD, dok, st.eta_fine_grid(CFG))
    fk.default_status = dstat
    return fk


# ---------------------------------------------------------------------------------------------
# analysis driver
# ---------------------------------------------------------------------------------------------
def alloys_present(rows: Sequence[Dict[str, Any]]) -> List[str]:
    order = ["316L Stainless Steel", "Ti-6Al-4V", "Inconel 625"]
    have = {r["material"] for r in rows}
    return [a for a in order if a in have]


def run_analysis(rows_by_variant: Dict[float, List[Dict[str, Any]]], table: Dict[str, Any],
                 kernels: Sequence[str] = KERNELS, log: Optional[Callable[[str], None]] = None,
                 cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """{variant: {kernel: {alloy: analysis}}} (alloys without KU rows are analysed once, under the first variant)."""
    cfg = CFG if cfg is None else cfg
    out: Dict[float, Dict[str, Any]] = {}
    fks: Dict[float, Dict[str, st.FineKernel]] = {}
    for vi, (beam, rows) in enumerate(sorted(rows_by_variant.items())):
        out[beam] = {}
        fks[beam] = {}
        for k in kernels:
            fk = fine_kernel(rows, k, table)
            fks[beam][k] = fk
            out[beam][k] = {}
            for alloy in alloys_present(rows):
                uses_ku = any(r["material"] == alloy and r["source"].startswith("ku-leuven") for r in rows)
                if vi > 0 and not uses_ku:
                    continue
                t0 = time.perf_counter()
                out[beam][k][alloy] = cl.analyze_kernel_alloy(fk, alloy, cfg)
                if log:
                    log(f"analysed beam={beam:g} {k} {alloy} in {time.perf_counter() - t0:.1f}s")
    return {"results": out, "fks": fks}


NO_DATA_ALLOYS = ("Inconel 718", "AlSi10Mg")


def _served_params(res: Dict[str, Any], q: str) -> Dict[str, Any]:
    fit = res["final"]["fit"]
    cell = res["cells"][q]
    rung = cell["servedRung"]
    boot = (fit or {}).get("boot") or {}
    p: Dict[str, Any] = {"rung": rung, "servedAsDefaultUnchanged": rung == "default"}
    if fit:
        p.update({"etaW": fit["etaW"], "etaD": fit["etaD"], "etaJoint": fit["etaJ"],
                  "etaW_ci90": (boot.get("W") or {}).get("ci90"), "etaD_ci90": (boot.get("D") or {}).get("ci90"),
                  "etaJoint_ci90": (boot.get("J") or {}).get("ci90"),
                  "boundHitFractionW": (boot.get("W") or {}).get("boundHitFraction"),
                  "boundHitFractionD": (boot.get("D") or {}).get("boundHitFraction"),
                  "boundHitFractionJoint": (boot.get("J") or {}).get("boundHitFraction"),
                  "atBound": fit["boundHit"], "cD": fit["cd"], "cDSource": fit["cdSource"], "cDNSets": fit["cdNSets"],
                  "cD_ci90": boot.get("cd"), "etaPrior": fit["etaPrior"], "sourceWeights": fit["sourceWeights"],
                  "nTrainRows": fit["nTrainRows"], "nTrainSets": fit["nTrainSets"]})
    return p


def p2_rows(res: Dict[str, Any], q: str) -> List[Dict[str, Any]]:
    out = []
    for s, rec in sorted(res["p2"].items()):
        qe = rec["byQuantity"][q]
        rung = qe["servedRung"]
        dflt = qe["rungs"]["default"]
        srv = qe["rungs"].get(rung, dflt)
        sk = (srv.get("skillVsDefault") or {}) if rung != "default" else {}
        skp = (srv.get("skillVsPowerlaw") or {}) if rung != "default" else {}
        cov = qe["served"]["coverage"]
        fac = qe["served"]["interval"]
        pl = qe["rungs"].get("powerlaw", {}).get("metrics", {})
        out.append({
            "heldOut": s, "trainedOn": rec["trainSources"], "rung": rung, "nRows": rec["nTestRows"],
            "nSets": rec["nTestSets"],
            "unresolvedDefault": dflt["unresolved"], "unresolvedServed": srv["unresolved"],
            "mapeDefault": dflt["metrics"]["mapePct"] if rung == "default" else sk.get("mapeB"),
            "mapeServed": srv["metrics"]["mapePct"] if rung == "default" else sk.get("mapeA"),
            "nCommon": sk.get("n"),
            "biasDefault": dflt["metrics"]["biasPct"], "biasServed": srv["metrics"]["biasPct"],
            "rmseDefault_um": dflt["metrics"]["rmse_um"], "rmseServed_um": srv["metrics"]["rmse_um"],
            "within30Default": dflt["metrics"]["within30"], "within30Served": srv["metrics"]["within30"],
            "withinFactor2Default": dflt["metrics"]["withinFactor2"], "withinFactor2Served": srv["metrics"]["withinFactor2"],
            "mapeUnresolvedAsFailDefault": dflt["mapeUnresolvedAsFail"], "mapeUnresolvedAsFailServed": srv["mapeUnresolvedAsFail"],
            "skill": sk.get("skill") if rung != "default" else 0.0, "skillCi95": sk.get("ci95") if rung != "default" else [0.0, 0.0],
            "verdictVsDefault": sk.get("verdict", "no-change") if rung != "default" else "no-change",
            "skillVsPowerlaw": skp.get("skill"), "skillVsPowerlawCi95": skp.get("ci95"),
            "verdictVsPowerlaw": skp.get("verdict"), "mapePowerlaw": pl.get("mapePct"),
            "rungMetrics": {r: {"mapePct": v["metrics"]["mapePct"], "biasPct": v["metrics"]["biasPct"],
                                "unresolved": v["unresolved"],
                                "skill": (v.get("skillVsDefault") or {}).get("skill"),
                                "skillCi95": (v.get("skillVsDefault") or {}).get("ci95")}
                            for r, v in qe["rungs"].items() if r != "powerlaw"},
            "coverage80": cov.get("80"), "coverage90": cov.get("90"),
            "widthRatio80": (fac.get("80") or {}).get("widthRatio"), "widthRatio90": (fac.get("90") or {}).get("widthRatio"),
            "intervalNotInformative90": (fac.get("90") or {}).get("notInformative"),
            "byRegimeClass": qe["byRegimeClass"],
            "selection": rec["selection"][q]["rung"], "selectionInnerGain": rec["selection"][q]["innerRelativeGain"],
            "selectionScheme": rec["selection"][q]["scheme"],
            "foldFit": {"etaW": rec["fit"]["etaW"] if rec["fit"] else None, "etaD": rec["fit"]["etaD"] if rec["fit"] else None,
                        "etaJoint": rec["fit"]["etaJ"] if rec["fit"] else None},
            "flagNotes": qe["flags"]["notes"],
        })
    return out


def p1_rows(res: Dict[str, Any], q: str) -> List[Dict[str, Any]]:
    out = []
    for s, rec in sorted(res["p1"].items()):
        pr = rec["byQuantity"][q]["primary"]
        out.append({"source": s, "nRows": rec["nRows"], "nSets": rec["nParameterSets"], "skill": pr["skill"],
                    "skillCi95": pr["ci95"], "mapeDefault": pr["mapeDefault"], "mapeServed": pr["mapeServed"],
                    "unresolvedDefault": pr["unresolvedDefault"], "unresolvedServed": pr["unresolvedServed"],
                    "rungChoices": pr["rungChoices"],
                    "skillBySeed": [x["skill"] for x in rec["byQuantity"][q]["seeds"]]})
    return out


def equal_weight_headline(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    d = [r["mapeDefault"] for r in rows if r.get("mapeDefault") is not None]
    s = [r["mapeServed"] for r in rows if r.get("mapeServed") is not None]
    n = sum(r["nRows"] for r in rows)
    pd_ = sum(r["mapeDefault"] * r["nRows"] for r in rows if r.get("mapeDefault") is not None)
    ps = sum(r["mapeServed"] * r["nRows"] for r in rows if r.get("mapeServed") is not None)
    return {"equalSourceWeight": {"mapeDefault": float(np.mean(d)) if d else None, "mapeServed": float(np.mean(s)) if s else None},
            "rowWeighted": {"mapeDefault": pd_ / n if n and d else None, "mapeServed": ps / n if n and s else None}}


def build_cells(analysis: Dict[str, Any], rows_by_variant: Dict[float, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    cells: List[Dict[str, Any]] = []
    beams = list(rows_by_variant)
    primary = sorted(beams)[0]
    results = analysis["results"]
    for k in KERNELS:
        for alloy in alloys_present(rows_by_variant[primary]):
            res = results[primary][k][alloy]
            variants = {}
            for b in sorted(beams):
                rb = results[b][k].get(alloy) if b in results else None
                if rb is not None:
                    variants_q = {q: rb["cells"][q]["gate"] for q in QS}
                    variants[b] = variants_q
            for q in QS:
                cell = res["cells"][q]
                per_var = {f"{b:g}": variants[b][q] for b in variants}
                gate = st.combine_beam_variants(per_var) if len(per_var) > 1 else dict(cell["gate"], beamStatuses=None)
                prow = p2_rows(res, q)
                heads = equal_weight_headline(prow) if prow else None
                cells.append({
                    "kernel": k, "material": alloy, "quantity": q, "status": gate["status"], "reasons": gate["reasons"],
                    "rung": cell["servedRung"], "params": _served_params(res, q),
                    "interval": {"m": cell["intervalParams"]["m"], "sWithin": cell["intervalParams"]["sWithin"],
                                 "sSource": cell["intervalParams"]["sSource"], "sSourceRaw": cell["intervalParams"]["sSourceRaw"],
                                 "nSourcesForSSource": cell["intervalParams"]["nSourcesForSSource"],
                                 "levels": CFG["interval"]["levels"], "factors": cell["interval"],
                                 "sourceMeanResiduals": cell["intervalParams"]["sourceMeanResiduals"]},
                    "flags": cell["flags"]["diagnosticFlags"], "gateFlags": cell["flags"]["flags"],
                    "gateRelevant": cell["flags"]["gateRelevant"], "flagNotes": cell["flags"]["notes"],
                    "diagnostics": cell["flags"]["diagnostics"],
                    "etaConsistent": cell["etaConsistent"], "foldEtas": cell["foldEtas"],
                    "selection": cell["selection"], "p2": prow, "p1": p1_rows(res, q),
                    "headline": heads, "beamStatuses": gate.get("beamStatuses"),
                    "beamSensitivity": {f"{b:g}": {"status": variants[b][q]["status"], "reasons": variants[b][q]["reasons"],
                                                   "p2": p2_rows(results[b][k][alloy], q) if b != primary else None}
                                        for b in variants if b != primary} or None,
                    "ballingSensitivity": res.get("ballingSensitivity") if q == "width" else None,
                    "trainSources": res["sources"], "nSetsBySource": res["nSetsBySource"],
                    "nRowsBySource": res["nRowsBySource"], "p1Skipped": res.get("p1Skipped", []),
                })
        for alloy in NO_DATA_ALLOYS:
            for q in QS:
                cells.append({"kernel": k, "material": alloy, "quantity": q, "status": "no-data",
                              "reasons": ["no trainable measured source for this alloy"], "rung": None, "params": None,
                              "interval": None, "flags": {}, "gateFlags": {}, "gateRelevant": False, "flagNotes": [],
                              "diagnostics": {}, "etaConsistent": None,
                              "foldEtas": {}, "selection": None, "p2": [], "p1": [], "headline": None,
                              "beamStatuses": None, "beamSensitivity": None, "ballingSensitivity": None,
                              "trainSources": [], "nSetsBySource": {}, "nRowsBySource": {}, "p1Skipped": []})
    return cells


def confusion_block(analysis: Dict[str, Any], rows_by_variant: Dict[float, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Regime confusion vs the KU Leuven published labels (316L, Ti64). Columns: the input-only screening class at the
    default eta (the served label). Sensitivities: at the eta_D of the leave-KU-out fold fit (out-of-sample), and the geometry-based keyhole call (D/W > 1)
    from each rung's OWN width and depth (never measured D with calibrated W)."""
    out: Dict[str, Any] = {"labelSource": "KU Leuven published regime labels (verbatim, Coen 2021)", "byAlloy": {}}
    primary = sorted(rows_by_variant)[0]
    for alloy in ("316L Stainless Steel", "Ti-6Al-4V"):
        blk: Dict[str, Any] = {}
        for beam, rows in sorted(rows_by_variant.items()):
            ku = [r for r in rows if r["source"].startswith("ku-leuven") and r["material"] == alloy and r.get("publishedLabel")]
            if not ku:
                continue
            pub = [r["publishedLabel"] for r in ku]
            at_default = [r["regimeClass"] for r in ku]
            blk[f"beam{beam:g}"] = {"n": len(ku), "atDefaultEta": st.confusion(pub, at_default)}
            if beam == primary:
                per_kernel = {}
                for k in KERNELS:
                    res = analysis["results"][beam][k].get(alloy)
                    fk = analysis["fks"][beam][k]
                    if res is None:
                        continue
                    ku_src = next(s for s in res["sources"] if s.startswith("ku-leuven"))
                    p2 = res["p2"].get(ku_src)
                    fit = p2["fit"] if p2 else None  # trained WITHOUT the KU geometry the labels are scored on
                    ids = fk.subset_idx(source=ku_src)
                    kk: Dict[str, Any] = {}
                    if fit and fit["etaD"]:
                        scale = fit["etaD"] / float(fk.rows[int(ids[0])]["defaultAbsorptivity"])
                        cls_d = [st.regime_class_from_enthalpy(fk.rows[int(i)]["normalizedEnthalpyDefault"] * scale) for i in ids]
                        kk["atEtaD"] = st.confusion([fk.rows[int(i)]["publishedLabel"] for i in ids], cls_d)
                        kk["etaD"] = fit["etaD"]
                        kk["etaDFit"] = "leave-KU-out fold fit (P2, trained without the KU Leuven rows)"
                    geo = {}
                    meas_kh = [fk.measD[i] / fk.measW[i] > 1.0 for i in ids]
                    for rung in ("default", "eta", "eta2", "eta2+dOffset"):
                        fitp = p2["fit"] if p2 else None
                        pw, okw = st.predict_rung(fk, ids, rung, fitp, "width")
                        pdp, okd = st.predict_rung(fk, ids, rung, fitp, "depth")
                        ok = okw & okd
                        if not ok.any():
                            geo[rung] = None
                            continue
                        pred_kh = (pdp[ok] / pw[ok]) > 1.0
                        mk = np.array(meas_kh)[ok]
                        tp = int(np.sum(pred_kh & mk))
                        fp = int(np.sum(pred_kh & ~mk))
                        fn = int(np.sum(~pred_kh & mk))
                        tn = int(np.sum(~pred_kh & ~mk))
                        geo[rung] = {"n": int(ok.sum()), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                                     "precision": tp / (tp + fp) if tp + fp else None,
                                     "recall": tp / (tp + fn) if tp + fn else None,
                                     "accuracy": (tp + tn) / int(ok.sum())}
                    kk["geometryKeyholeDoverW"] = {"measuredKeyholeByAspectRatio": int(sum(meas_kh)), "nRows": int(len(ids)),
                                                   "rung": geo, "fitFrom": f"trained without {ku_src} (leave-one-source-out)"}
                    per_kernel[k] = kk
                blk["perKernelSensitivity"] = per_kernel
        out["byAlloy"][alloy] = blk
    return out


def sentinel_block(analysis: Dict[str, Any], catalog_rows: List[Dict[str, Any]], table: Dict[str, Any]) -> Dict[str, Any]:
    """Test-only catalog sentinels: predictions with the FINAL served fit of the alloy (316L for Guo) or the Inconel
    625 fit as a cross-alloy transfer (NIST IN718). Never trained on, never in the gate."""
    primary = sorted(analysis["results"])[0]
    out: Dict[str, Any] = {"title": SENTINEL_TITLE, "kernels": {}, "n01": [], "note": (
        "Guo N01/N04-N06 and NIST AMB2022-03 Table 4 were used while the frozen physics was developed (PROOF 023, "
        "the Goldak fix, test_goldak_fabbro bands): they are development data, not blind held-out data. N01 "
        "(260 W, 520 mm/s, keyhole, D_meas 180 um) is a documented keyhole-depth failure: it is NOT fitted, it is in no "
        "training split, and calibration does not fix it.")}
    for k in KERNELS:
        fk_c = fine_kernel(catalog_rows, k, table)
        kk: Dict[str, Any] = {}
        for alloy, src_alloy, label in (("316L Stainless Steel", "316L Stainless Steel", "calibration (316L fit from Hofmann + KU)"),
                                        ("Inconel 718", "Inconel 625", "TRANSFER, not calibration (Inconel 625 fit applied to IN718)")):
            res = analysis["results"][primary][k].get(src_alloy)
            if res is None:
                continue
            ids = np.flatnonzero(np.array([r["material"] == alloy for r in catalog_rows]))
            if ids.size == 0:
                continue
            fit = res["final"]["fit"]
            sel = res["final"]["selection"]
            rows_out = []
            for i in ids:
                r = catalog_rows[int(i)]
                row_rec: Dict[str, Any] = {"rowId": r["rowId"], "source": r["source"], "P_W": r["power_W"],
                                           "v_mm_s": r["speed_mm_s"], "measured": {"width_um": r["width_um"], "depth_um": r["depth_um"]},
                                           "rungs": {}}
                for rung in RUNG_LIST:
                    pw, okw = st.predict_rung(fk_c, np.array([i]), rung, fit, "width")
                    pdp, okd = st.predict_rung(fk_c, np.array([i]), rung, fit, "depth")
                    wv = float(pw[0]) if okw[0] else None
                    dv = float(pdp[0]) if okd[0] else None
                    fw = wv / r["width_um"] if wv else None
                    fd = dv / r["depth_um"] if dv else None
                    row_rec["rungs"][rung] = {"width_um": wv, "depth_um": dv, "widthFactor": fw, "depthFactor": fd,
                                              "insideFactor2": bool(fw and fd and 0.5 <= fw <= 2 and 0.5 <= fd <= 2),
                                              "depthInsideFactor2": bool(fd and 0.5 <= fd <= 2)}
                rows_out.append(row_rec)
                if r["rowId"] == "guo-316l-n01":
                    out["n01"].append({"kernel": k, "measured": row_rec["measured"], "rungs": row_rec["rungs"],
                                       "servedRungWidth": sel["width"]["rung"], "servedRungDepth": sel["depth"]["rung"],
                                       "statement": "known keyhole-depth failure; not fitted; N01 never in training"})
            ev_rows = {}
            for q in QS:
                rung = sel[q]["rung"]
                pd_, okd = st.predict_rung(fk_c, ids, "default", None, q)
                ps, oks = st.predict_rung(fk_c, ids, rung, fit, q)
                meas = fk_c.meas(q)[ids]
                common = okd & oks
                ev_rows[q] = {"servedRung": rung, "n": int(ids.size),
                              "mapeDefault": st.metrics(pd_, meas, common)["mapePct"],
                              "mapeServed": st.metrics(ps, meas, common)["mapePct"],
                              "unresolvedDefault": int((~okd).sum()), "unresolvedServed": int((~oks).sum())}
            kk[alloy] = {"label": label, "fitFrom": src_alloy, "rows": rows_out, "summary": ev_rows}
        out["kernels"][k] = kk
    return out


def unresolved_accounting(analysis: Dict[str, Any], provenance: Dict[str, Any], catalog_rows: List[Dict[str, Any]],
                          table: Dict[str, Any]) -> Dict[str, Any]:
    primary = sorted(analysis["results"])[0]
    rows: List[Dict[str, Any]] = []
    for k in KERNELS:
        fk = analysis["fks"][primary][k]
        for s in fk.sources:
            ids = fk.subset_idx(source=s)
            stat = Counter(fk.default_status[int(i)] for i in ids)
            rows.append({"kernel": k, "source": s, "rowsUsed": int(ids.size), "resolvedAtDefault": int(fk.defOk[ids].sum()),
                         "unresolvedAtDefault": int((~fk.defOk[ids]).sum()), "statusAtDefault": dict(sorted(stat.items())),
                         "role": "trainable"})
        fk_c = fine_kernel(catalog_rows, k, table)
        for s in sorted({r["source"] for r in catalog_rows}):
            ids = np.flatnonzero(np.array([r["source"] == s for r in catalog_rows]))
            stat = Counter(fk_c.default_status[int(i)] for i in ids)
            rows.append({"kernel": k, "source": s, "rowsUsed": int(ids.size), "resolvedAtDefault": int(fk_c.defOk[ids].sum()),
                         "unresolvedAtDefault": int((~fk_c.defOk[ids]).sum()), "statusAtDefault": dict(sorted(stat.items())),
                         "role": "catalog-sentinel"})
    loader = [{"source": s, "loaderRows": p["loaderRows"], "excludedByLoader": p["loaderExcluded"]} for s, p in sorted(provenance.items())]
    not_geometry = [
        {"source": "cmu-ti64-2026", "reason": "no power / no beam diameter in the source rows: not a geometry row set"},
        {"source": "ku-leuven-in718-2021", "reason": "width/depth units and width operator unresolved: excluded everywhere"},
        {"source": "simonds-316l-2018, nist-mds2-2525", "reason": "stationary-spot absorptance: used as R5 bands and bounds only"},
        {"source": "nist thermal targets", "reason": "thermal-history targets, not melt-pool geometry: out of scope"}]
    return {"perKernelSource": rows, "loader": loader, "notGeometrySources": not_geometry,
            "rule": "unresolved test rows count as failures (mapeUnresolvedAsFail, a rung that resolves fewer rows than "
                    "default fails the gate); MAPE columns are on the common resolved subset and always listed with the "
                    "unresolved count"}


def coverage_table(cells: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for c in cells:
        for r in c["p2"]:
            for lvl in ("80", "90"):
                cov = r.get(f"coverage{lvl}")
                if cov:
                    out.append({"kernel": c["kernel"], "material": c["material"], "quantity": c["quantity"],
                                "heldOut": r["heldOut"], "level": int(lvl), "k": cov["k"], "n": cov["n"],
                                "coverage": cov["coverage"], "wilson95": cov["wilson95"],
                                "widthRatio": r.get(f"widthRatio{lvl}"),
                                "notInformative": bool(r.get("intervalNotInformative90")) if lvl == "90" else None})
    return out


# ---------------------------------------------------------------------------------------------
# document
# ---------------------------------------------------------------------------------------------
def _git(args: List[str]) -> Optional[str]:
    try:
        res = subprocess.run(["git"] + args, capture_output=True, text=True, cwd=str(PYTHON_DIR), timeout=30)
        return res.stdout.strip() if res.returncode == 0 else None
    except Exception:
        return None


def code_revision() -> Dict[str, Any]:
    status = _git(["status", "--porcelain", "-uno", "--", "python", "data/calibration"])
    return {"gitHead": _git(["rev-parse", "HEAD"]), "gitBranch": _git(["rev-parse", "--abbrev-ref", "HEAD"]),
            "dirtyTrackedPaths": None if status is None else len([ln for ln in status.splitlines() if ln.strip()]),
            "python": platform.python_version()}


def tool_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def what_this_does_not_show() -> List[str]:
    return [
        "It is not experimental validation. Effective absorptivity is a fitted nuisance parameter that absorbs every "
        "other model error (material laws, the Fabbro keyhole term, the flat-plate path, spot definition, assumed 20 C "
        "preheat); it must not be read as a measured absorptivity of any alloy.",
        "No source reports per-row measurement uncertainty, sectioning position or replicate scatter; intervals cover "
        "parameter-set resampling and the between-source offset only, not measurement error.",
        "Between-source offsets (machine, powder, atmosphere, operator) are larger than anything a per-alloy "
        "absorptivity removes; a calibration that helps inside one source usually does not transfer to the next.",
        "Only two 316L sources and two Ti-6Al-4V sources are available for leave-one-source-out; Inconel 625 has one "
        "source (within-source only); Inconel 718 and AlSi10Mg have no trainable source (no-data).",
        "KU Leuven's beam diameter (37.5 vs 75 um) is unresolved; the gate decision is required to be identical under "
        "both readings, otherwise the cell is rejected as 'unresolved input'.",
        "The catalog sentinels (Guo, NIST IN718) were used while the frozen physics was developed; they are reported "
        "separately and are not blind held-out data.",
        "The served default screening output, the Build Job verdict and the balling screen are unchanged by this work; "
        "calibration never re-scores a Build Job.",
    ]


def build_document(quick: bool, jobs: int, generated_at: str, table_cache: Optional[Path] = None,
                   solver: Optional[Callable] = None, rows_override: Optional[Dict[float, Dict[str, Any]]] = None,
                   fp_override: Optional[str] = None, revision: Optional[Dict[str, Any]] = None,
                   log: Optional[Callable[[str], None]] = None,
                   user_sources: Optional[Sequence[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """``user_sources`` (additive hook, default None = unchanged output): documents from
    ``lpbf_user_measurements.load_user_rows``. Each joins as ONE extra trainable source in a COPY of the config
    (``dataRoles.userSources``; the copy's sha256 is the recorded configSha256); LOSO, gate, rungs and intervals are
    the production ones, and a user source is never a catalog sentinel."""
    st.pin_flat_plate()
    cfg = CFG
    user_docs = list(user_sources or [])
    if user_docs:
        from lpbf_calibration_config import config_with_user_sources
        cfg = config_with_user_sources(CFG, [d["sourceId"] for d in user_docs])
    if fp_override is None:
        from lpbf_simulation import implementation_fingerprint
        fp = implementation_fingerprint()
    else:
        fp = fp_override
    loads = rows_override or {b: load_rows(quick, b) for b in BEAM_VARIANTS}
    if user_docs:
        loads = {b: dict(v) for b, v in loads.items()}
        for b in loads:
            extra = []
            for d in user_docs:
                for r in d["rows"]:
                    row = dict(r)
                    if "normalizedEnthalpyDefault" not in row:
                        _classify(row)
                    extra.append(row)
            loads[b]["trainable"] = list(loads[b]["trainable"]) + extra
        have = {r["material"] for r in loads[sorted(loads)[0]]["trainable"] if r["source"] not in
                {d["sourceId"] for d in user_docs}}
        for d in user_docs:
            if d["material"] not in have:
                raise SystemExit(f"user source {d['sourceId']}: no trainable source of {d['material']} exists, so "
                                 "the scorecard would have nothing to hold it out against")
    primary = sorted(loads)[0]
    rows_by_variant = {b: loads[b]["trainable"] for b in loads}
    catalog = loads[primary]["catalog"]
    provenance = loads[primary]["provenance"]
    all_rows: Dict[str, Dict[str, Any]] = {}
    for b in loads:
        for r in loads[b]["trainable"] + loads[b]["catalog"]:
            all_rows[f"{input_key(r)}"] = r
    defaults = sorted({r["defaultAbsorptivity"] for r in all_rows.values()})
    nodes = node_grid(defaults)
    table, table_source = load_or_build_table(list(all_rows.values()), fp, jobs, table_cache, nodes, solver)
    if log:
        log(f"kernel table: {table_source}")
    mat_defaults = {r["material"]: r["defaultAbsorptivity"] for r in all_rows.values()}
    for m, v in CFG["materialDefaults"].items():
        if m in mat_defaults and abs(mat_defaults[m] - v) > 1e-9:
            raise SystemExit(f"CALIBRATION_CONFIG materialDefaults[{m}]={v} != live default {mat_defaults[m]}")
    analysis = run_analysis(rows_by_variant, table, log=log, cfg=cfg)
    cells = build_cells(analysis, rows_by_variant)
    primary_rows = rows_by_variant[primary]
    sources_info = []
    for s in list(cfg["dataRoles"]["trainable"]) + list(CATALOG_SOURCES):
        rr = [r for r in primary_rows + catalog if r["source"] == s]
        if not rr:
            continue
        info = dict(provenance.get(s, {}))
        info.update({"source": s, "role": "trainable" if s in cfg["dataRoles"]["trainable"] else "catalog-sentinel (test-only)",
                     "material": rr[0]["material"], "rowsUsed": len(rr),
                     "parameterSets": len({st.set_key(r) for r in rr})})
        sources_info.append(info)
    counts = Counter(c["status"] for c in cells)
    doc = {
        "schema": SCORECARD_SCHEMA, "generatedAt": generated_at, "quick": bool(quick),
        "implementationHash": fp, "codeRevision": revision or code_revision(),
        "tool": {"path": "python/tools/lpbf_calibration_fit.py", "sha256": tool_sha256()},
        "config": cfg, "configSha256": config_sha256(cfg),
        "evidence": {"kind": EVIDENCE_KIND, "label": EVIDENCE_LABEL, "labelPromotionProposed": LABEL_PROMOTION,
                     "experimentalValidation": False, "opticalOperatorMatched": False, "statement": HONESTY},
        "kernel": {"entryPoint": "lpbf_thermal_solver.calculate_meltpool_physics(heat_source=<kernel>)",
                   "absorptionPath": "flat-plate (absorption_model='flat-plate'; powder_bed_raytracer pinned unimportable)",
                   "varied": "prop_overrides={'absorptivity_IR': eta}; the default call has no override",
                   "nodes": nodes, "uniqueInputs": len(table["entries"]),
                   "tableSha256": st.canonical_sha256({k: table[k] for k in ("nodes", "kernels", "statuses", "entries")}),
                   "tableNote": "the kernel table (cached under .runtime/cache) is content-hashed; two runs on the same "
                                "table are byte-identical"},
        "sources": sources_info,
        "gateSummary": dict(sorted(counts.items())),
        "envelope": training_envelope(primary_rows),
        "cells": cells,
        "regimeConfusion": confusion_block(analysis, rows_by_variant),
        "catalogSentinels": sentinel_block(analysis, catalog, table),
        "unresolved": unresolved_accounting(analysis, provenance, catalog, table),
        "coverage": coverage_table(cells),
        "betweenSource": between_source_summary(analysis),
        "whatThisDoesNotShow": what_this_does_not_show(),
    }
    if user_docs:
        doc["userSources"] = [{"source": d["sourceId"], "label": d["label"], "material": d["material"],
                               "nRows": d["nRows"], "nExcluded": d["nExcluded"], "provenance": d["provenance"],
                               "role": "extra trainable source (user-supplied), private run",
                               "statement": "the user's own measurements; never a catalog sentinel; the evidence "
                                            "label stays screening-only"} for d in user_docs]
        doc["privateRun"] = ("scorecard computed with user-supplied measurements as an extra trainable source; it is "
                             "not a committed record and its artefact is refused by the runtime loader (config sha)")
    return st.round_sig(doc, CFG["rounding"]["significantDigits"])


def training_envelope(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Per-alloy box of the trainable inputs and of the input-only normalised enthalpy at the DEFAULT absorptivity
    (the served regime label)."""
    out: Dict[str, Any] = {}
    for m in sorted({r["material"] for r in rows}):
        sub = [r for r in rows if r["material"] == m]
        out[m] = {"laserPower_W": [min(r["power_W"] for r in sub), max(r["power_W"] for r in sub)],
                  "scanSpeed_mm_s": [min(r["speed_mm_s"] for r in sub), max(r["speed_mm_s"] for r in sub)],
                  "beamDiameter_um": [min(r["beamDiameter_um"] for r in sub), max(r["beamDiameter_um"] for r in sub)],
                  "normalizedEnthalpyDefault": [min(r["normalizedEnthalpyDefault"] for r in sub),
                                                max(r["normalizedEnthalpyDefault"] for r in sub)],
                  "sources": sorted({r["source"] for r in sub}), "rows": len(sub)}
    return out


def between_source_summary(analysis: Dict[str, Any]) -> Dict[str, Any]:
    primary = sorted(analysis["results"])[0]
    out: Dict[str, Any] = {}
    for k in KERNELS:
        per = {}
        for alloy, res in analysis["results"][primary][k].items():
            for q in QS:
                ip = res["cells"][q]["intervalParams"]
                per[f"{alloy}|{q}"] = {"sSourceRaw": ip["sSourceRaw"], "sSourceUpper": ip["sSource"],
                                      "nSources": ip["nSourcesForSSource"], "sourceMeanLogResidual": ip["sourceMeanResiduals"]}
        out[k] = per
    out["note"] = ("ln(meas/pred) per-source mean at a theta fitted without that source; SD over sources is the "
                   "between-source offset the intervals carry (chi-square inflated).")
    return out


# ---------------------------------------------------------------------------------------------
# artefact
# ---------------------------------------------------------------------------------------------
def build_artefact(doc: Dict[str, Any], scorecard_rel: str, scorecard_sha: str) -> Dict[str, Any]:
    cells = []
    for c in doc["cells"]:
        p = c["params"]
        cells.append({
            "kernel": c["kernel"], "material": c["material"], "quantity": c["quantity"], "status": c["status"],
            "rung": c["rung"], "reasons": c["reasons"],
            "params": None if p is None else {k: p.get(k) for k in (
                "etaW", "etaD", "etaJoint", "etaW_ci90", "etaD_ci90", "etaJoint_ci90", "cD", "cDSource", "etaPrior")},
            "interval": None if c["interval"] is None else {k: c["interval"][k] for k in ("m", "sWithin", "sSource", "levels")},
            "heldOutScore": [{k: r.get(k) for k in ("heldOut", "trainedOn", "rung", "nRows", "nSets", "mapeDefault", "mapeServed",
                                                    "skill", "skillCi95", "coverage90")} for r in c["p2"]],
            "withinSourceScore": [{k: r.get(k) for k in ("source", "nRows", "nSets", "skill", "skillCi95")} for r in c["p1"]],
            "flags": c["flags"], "beamStatuses": c.get("beamStatuses")})
    art = {
        "schema": CALIBRATION_SCHEMA,
        "calibrationId": "", "generatedAt": doc["generatedAt"], "implementationHash": doc["implementationHash"],
        "codeRevision": doc["codeRevision"], "tool": doc["tool"],
        "configSha256": doc["configSha256"], "config": doc["config"] if doc.get("userSources") else CFG,
        "trainingData": [{k: s.get(k) for k in ("source", "doi", "tableSha256", "rowsUsed", "parameterSets", "material")}
                         for s in doc["sources"] if s["role"] == "trainable"],
        "catalogSentinelSources": [s["source"] for s in doc["sources"] if s["role"] != "trainable"],
        "heldOutSources": "leave-one-source-out inside each alloy (every trainable source of a 2-source alloy is held out once)",
        "priors": {m: {"eta": v, "lambda": CFG["prior"]["lambda"], "bounds": CFG["bounds"],
                       "basis": "material default absorptivity_IR; measured absorptance only as R5 bands"}
                   for m, v in CFG["materialDefaults"].items()},
        "envelope": doc["envelope"],
        "cells": cells, "scorecardRecord": scorecard_rel, "scorecardSha256": scorecard_sha,
        "evidenceKind": EVIDENCE_KIND, "proposedEvidenceKind": None, "evidenceLabel": EVIDENCE_LABEL,
        "labelPromotionProposed": LABEL_PROMOTION, "honesty": HONESTY, "contentSha256": "",
    }
    art = st.round_sig(art, CFG["rounding"]["significantDigits"])
    sha = st.canonical_sha256(art)  # contentSha256 and calibrationId are blank while hashing (as the loader does)
    art["contentSha256"] = sha
    art["calibrationId"] = f"lpbf-meltpool-calib-{doc['generatedAt']}-{sha[:12]}"
    return art


SUMMARY_REL_PATH = ARTEFACT_REL_PATH.replace(".json", ".summary.json")
SUMMARY_SCHEMA = "lpbf-meltpool-calibration-summary-1"


def build_summary(art: Dict[str, Any]) -> Dict[str, Any]:
    """Small file the app imports instead of the whole artefact: id, hash and the per-cell gate status only."""
    return {"schema": SUMMARY_SCHEMA, "calibrationId": art["calibrationId"], "contentSha256": art["contentSha256"],
            "artefact": ARTEFACT_REL_PATH, "evidenceKind": art["evidenceKind"],
            "cells": [{"kernel": c["kernel"], "material": c["material"], "quantity": c["quantity"], "status": c["status"]}
                      for c in art["cells"]]}


def verify_artefact_hash(art: Dict[str, Any]) -> bool:
    probe = dict(art)
    probe["contentSha256"] = ""
    probe["calibrationId"] = ""
    return st.canonical_sha256(probe) == art["contentSha256"]


# ---------------------------------------------------------------------------------------------
# view record and markdown
# ---------------------------------------------------------------------------------------------
def make_view(doc: Dict[str, Any]) -> Dict[str, Any]:
    head = []
    for c in doc["cells"]:
        p = c["params"] or {}
        head.append({
            "kernel": c["kernel"], "material": c["material"], "quantity": c["quantity"], "status": c["status"],
            "reasons": c["reasons"], "servedRung": c["rung"], "flags": [k for k, v in (c["flags"] or {}).items() if v],
            "gateRelevant": c.get("gateRelevant", False), "diagnostics": c.get("diagnostics") or {},
            "flagNotes": c["flagNotes"], "headline": c["headline"],
            "p2": [{k: r.get(k) for k in ("heldOut", "trainedOn", "rung", "nRows", "nSets", "mapeDefault", "mapeServed",
                                          "skill", "skillCi95", "verdictVsDefault", "unresolvedDefault", "unresolvedServed",
                                          "coverage90", "widthRatio90", "intervalNotInformative90", "mapePowerlaw",
                                          "verdictVsPowerlaw")} for r in c["p2"]],
            "p1": [{k: r.get(k) for k in ("source", "nRows", "nSets", "skill", "skillCi95", "mapeDefault", "mapeServed")}
                   for r in c["p1"]],
            "params": {k: p.get(k) for k in ("etaW", "etaD", "etaJoint", "etaW_ci90", "etaD_ci90", "etaJoint_ci90", "cD",
                                              "boundHitFractionW", "boundHitFractionD", "etaPrior") if k in p} if p else None,
            "beamStatuses": c.get("beamStatuses")})
    return {
        "schema": SCORECARD_VIEW_SCHEMA, "generatedAt": doc["generatedAt"], "implementationHash": doc["implementationHash"],
        "configSha256": doc["configSha256"], "evidence": doc["evidence"], "gateSummary": doc["gateSummary"],
        "headline": head, "sources": doc["sources"], "regimeConfusion": doc["regimeConfusion"],
        "n01": doc["catalogSentinels"]["n01"], "catalogSentinels": doc["catalogSentinels"], "coverage": doc["coverage"],
        "unresolved": doc["unresolved"], "betweenSource": doc["betweenSource"],
        "notes": doc["whatThisDoesNotShow"], "quick": doc["quick"],
        "provenance": {"codeRevision": doc["codeRevision"], "tool": doc["tool"], "kernel": {k: doc["kernel"][k] for k in (
            "absorptionPath", "tableSha256", "uniqueInputs")}}}


def _f(x: Any, d: int = 1) -> str:
    return "-" if x is None else f"{x:.{d}f}"


def _ci(ci: Any, d: int = 2) -> str:
    return "" if not ci else f" [{ci[0]:.{d}f}, {ci[1]:.{d}f}]"


def _user_source_lines(doc: Dict[str, Any]) -> List[str]:
    """Empty unless the record came from a private --user-source run (the committed record is unchanged)."""
    us = doc.get("userSources")
    if not us:
        return []
    out = ["## User-supplied sources (private run)", "",
           f"{doc.get('privateRun')}", ""]
    for u in us:
        out.append(f"- `{u['source']}`: {u['label']}, {u['material']}, {u['nRows']} rows used, {u['nExcluded']} "
                   "excluded; an extra trainable source, never a catalog sentinel.")
    return out + [""]


def render_markdown(doc: Dict[str, Any]) -> str:
    ev = doc["evidence"]
    cr = doc["codeRevision"]
    L = [f"# LPBF melt-pool calibration scorecard ({doc['generatedAt']})", "",
         f"**{EVIDENCE_LABEL}.** Evidence kind `{ev['kind']}`; label promotion proposed: **{ev['labelPromotionProposed']}**; "
         "`experimentalValidation` = false; `opticalOperatorMatched` = false.", "",
         f"Schema `{doc['schema']}`; implementation fingerprint `{doc['implementationHash']}`; config sha256 "
         f"`{doc['configSha256']}`; code revision `{cr.get('gitHead')}` ({cr.get('gitBranch')}; dirty tracked paths: "
         f"{cr.get('dirtyTrackedPaths')}); tool sha256 `{doc['tool']['sha256']}`; quick mode: {doc['quick']}.", "",
         f"Honesty: {ev['statement']}.", "",
         *_user_source_lines(doc),
         "## Gate outcome", "",
         "Calibrated mode may serve a cell only when its status is `enabled`: held-out skill CI95 lower bound >= "
         f"{CFG['gate']['skillLbFloor']} on every held-out source (and > 0 on at least one), 90 % interval coverage "
         "Wilson upper bound >= 0.90, no physics-compensation flag, fold-wise eta agreement, same decision under both KU "
         "beam readings, no rung that resolves fewer rows than default. Status counts: "
         + ", ".join(f"{k} {v}" for k, v in doc["gateSummary"].items()) + ".", "",
         "| kernel | alloy | quantity | status | served rung | reasons |", "|---|---|---|---|---|---|"]
    for c in doc["cells"]:
        L.append(f"| {c['kernel']} | {c['material']} | {c['quantity']} | **{c['status']}** | {c['rung'] or '-'} | "
                 f"{'; '.join(c['reasons']) if c['reasons'] else '-'} |")
    L += ["", "## Held-out errors (leave-one-source-out, rung selected inside training only)", "",
          "MAPE on the rows resolved by default and the rung; both directions of every two-source alloy. Equal source "
          "weight is the headline; unresolved rows are counted (and score as failures in the gate).", "",
          "| kernel | alloy | q | held out | trained on | rung | n rows / sets | unresolved default / rung | MAPE default -> served % | "
          "skill CI95 | vs powerlaw | PI90 coverage (Wilson) | PI90 width x |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in doc["cells"]:
        for r in c["p2"]:
            cov = r.get("coverage90") or {}
            L.append(f"| {c['kernel']} | {c['material']} | {c['quantity']} | {r['heldOut']} | {', '.join(r['trainedOn'])} | "
                     f"{r['rung']} | {r['nRows']} / {r['nSets']} | {r['unresolvedDefault']} / {r['unresolvedServed']} | "
                     f"{_f(r['mapeDefault'])} -> {_f(r['mapeServed'])} | {_f(r['skill'], 2)}{_ci(r['skillCi95'])} "
                     f"({r['verdictVsDefault']}) | {r.get('verdictVsPowerlaw') or '-'} | "
                     f"{_f(cov.get('coverage'), 2)}{_ci(cov.get('wilson95'))} n={cov.get('n', 0)} | "
                     f"{_f(r.get('widthRatio90'), 2)}{' (not informative)' if r.get('intervalNotInformative90') else ''} |")
    L += ["", "### Equal-source-weight headline", "", "| kernel | alloy | q | status | MAPE default -> served % (equal source weight) | row-weighted |",
          "|---|---|---|---|---|---|"]
    for c in doc["cells"]:
        h = c.get("headline")
        if h:
            L.append(f"| {c['kernel']} | {c['material']} | {c['quantity']} | {c['status']} | "
                     f"{_f(h['equalSourceWeight']['mapeDefault'])} -> {_f(h['equalSourceWeight']['mapeServed'])} | "
                     f"{_f(h['rowWeighted']['mapeDefault'])} -> {_f(h['rowWeighted']['mapeServed'])} |")
    L += ["", "## Within-source grouped 5-fold (nested rung selection, seeds 0/1/2)", "",
          "| kernel | alloy | q | source | rows / sets | MAPE default -> served % | skill (seed 0) CI95 | skill seeds 0/1/2 |",
          "|---|---|---|---|---|---|---|---|"]
    for c in doc["cells"]:
        for r in c["p1"]:
            L.append(f"| {c['kernel']} | {c['material']} | {c['quantity']} | {r['source']} | {r['nRows']} / {r['nSets']} | "
                     f"{_f(r['mapeDefault'])} -> {_f(r['mapeServed'])} | {_f(r['skill'], 2)}{_ci(r['skillCi95'])} | "
                     f"{', '.join(_f(x, 2) for x in r['skillBySeed'])} |")
    skipped = sorted({(x["source"], x["nSets"], x["reason"]) for c in doc["cells"] for x in c.get("p1Skipped", [])})
    if skipped:
        L += ["", "Sources without a within-source evaluation (not silently dropped):", ""]
        L += [f"- {src}: {n} parameter sets; {why}" for src, n, why in skipped]
    L += ["", "## Fitted parameters (final fit on all trainable sources of the alloy; bootstrap CI90)", "",
          "| kernel | alloy | q | rung | eta_W | eta_D | eta joint | c_D by class | flags |", "|---|---|---|---|---|---|---|---|---|"]
    for c in doc["cells"]:
        p = c["params"]
        if not p:
            continue
        cd = ", ".join(f"{k} {v:+.2f}" for k, v in (p.get("cD") or {}).items())
        flags = ", ".join(k for k, v in c["flags"].items() if v) or "-"
        L.append(f"| {c['kernel']} | {c['material']} | {c['quantity']} | {c['rung']} | "
                 f"{_f(p.get('etaW'), 3)}{_ci(p.get('etaW_ci90'), 3)} | {_f(p.get('etaD'), 3)}{_ci(p.get('etaD_ci90'), 3)} | "
                 f"{_f(p.get('etaJoint'), 3)}{_ci(p.get('etaJoint_ci90'), 3)} | {cd} | {flags} |")
    L += ["", "Parameters are listed for every cell for diagnosis; the `rung` column says what would be served, and nothing is "
          "served unless the status is `enabled`. A `default` rung means no ladder rung beat the unchanged screening "
          "result on the training-only inner score.", "", "### Physics-compensation diagnostics", "",
          "Computed for every fitted cell, including cells whose served rung is `default` (where they cannot veto anything "
          "because nothing is served; `gate` = no). They show where a kernel is wrong and the fit compensates with an "
          "unphysical absorptivity or offset.", "",
          "| kernel | alloy | q | gate relevant | bound-hit fraction (bootstrap) | ln(eta_D/eta_W) | max abs c_D | "
          "measured-absorptance mismatch | diagnostic flags |", "|---|---|---|---|---|---|---|---|---|"]
    for c in doc["cells"]:
        if not c["params"]:
            continue
        d = c.get("diagnostics") or {}
        mm = "; ".join(f"{m['class']} (eta {m['eta']:.3f} vs {m['band'][0]:.2f}-{m['band'][1]:.2f})"
                       for m in d.get("absorptanceMismatch") or []) or "none"
        L.append(f"| {c['kernel']} | {c['material']} | {c['quantity']} | {'yes' if c.get('gateRelevant') else 'no'} | "
                 f"{_f(d.get('boundHitBootstrapFraction'), 2)} | {_f(d.get('etaSplitLn'), 2)} | {_f(d.get('maxAbsCd'), 2)} | "
                 f"{mm} | {', '.join(k for k, v in c['flags'].items() if v) or '-'} |")
    L += ["", "### Physics-compensation notes", ""]
    for c in doc["cells"]:
        for n in c["flagNotes"]:
            L.append(f"- {c['kernel']} / {c['material']} / {c['quantity']}: {n}")
    L += ["", "## Regime confusion vs KU Leuven published labels", ""]
    for alloy, blk in doc["regimeConfusion"]["byAlloy"].items():
        for key, b in blk.items():
            if not key.startswith("beam"):
                continue
            cf = b["atDefaultEta"]
            L += [f"**{alloy}, KU beam reading {key[4:]} um (screening class at default eta, input-only)** n={cf['n']}, "
                  f"accuracy {_f(cf['accuracy'], 2)}; keyhole precision {_f(cf['keyholeOnly']['precision'], 2)}, recall "
                  f"{_f(cf['keyholeOnly']['recall'], 2)}", "",
                  "| published \\ screening | " + " | ".join(cf["labels"]) + " |", "|---|" + "---|" * len(cf["labels"])]
            for p_ in cf["labels"]:
                L.append(f"| {p_} | " + " | ".join(str(cf["matrix"][p_][c_]) for c_ in cf["labels"]) + " |")
            L.append("")
    geo_rows = []
    for alloy, blk in doc["regimeConfusion"]["byAlloy"].items():
        for k, kk in (blk.get("perKernelSensitivity") or {}).items():
            g = kk.get("geometryKeyholeDoverW") or {}
            for rung, v in (g.get("rung") or {}).items():
                if v:
                    geo_rows.append(f"| {alloy} | {k} | {rung} | {v['n']} | {v['tp']} / {v['fp']} / {v['fn']} / {v['tn']} | "
                                    f"{_f(v['precision'], 2)} | {_f(v['recall'], 2)} |")
    if geo_rows:
        L += ["**Geometry-based keyhole call (predicted D/W > 1 vs measured D/W > 1), KU rows held out; each rung's OWN width and "
              "depth, never measured D with calibrated W**", "",
              "| alloy | kernel | rung | n | tp / fp / fn / tn | precision | recall |", "|---|---|---|---|---|---|---|"] + geo_rows + [""]
    L += ["## Guo N01 (red card) and catalog sentinels", "", doc["catalogSentinels"]["note"], "",
          "| kernel | rung | W pred / meas um | D pred / meas um | D factor | inside x0.5-2 |", "|---|---|---|---|---|---|"]
    for n in doc["catalogSentinels"]["n01"]:
        for rung, v in n["rungs"].items():
            L.append(f"| {n['kernel']} | {rung} | {_f(v['width_um'])} / {n['measured']['width_um']:.0f} | {_f(v['depth_um'])} / "
                     f"{n['measured']['depth_um']:.0f} | {_f(v['depthFactor'], 2)} | {'yes' if v['insideFactor2'] else 'NO'} |")
    L += ["", "## Unresolved-row accounting (no silent drops)", "", doc["unresolved"]["rule"], "",
          "| kernel | source | role | rows | resolved at default | unresolved at default | statuses |", "|---|---|---|---|---|---|---|"]
    for r in doc["unresolved"]["perKernelSource"]:
        L.append(f"| {r['kernel']} | {r['source']} | {r['role']} | {r['rowsUsed']} | {r['resolvedAtDefault']} | "
                 f"{r['unresolvedAtDefault']} | {r['statusAtDefault']} |")
    L += ["", "Rows excluded by the loaders:", ""]
    for r in doc["unresolved"]["loader"]:
        if r["excludedByLoader"]:
            L.append(f"- {r['source']}: " + "; ".join(f"{x['rowId']} ({x['reason']})" for x in r["excludedByLoader"]))
    for r in doc["unresolved"]["notGeometrySources"]:
        L.append(f"- not a geometry source: {r['source']}: {r['reason']}")
    L += ["", "## Sources", "", "| source | role | alloy | rows used | parameter sets | DOI | table sha256 |", "|---|---|---|---|---|---|---|"]
    for s in doc["sources"]:
        L.append(f"| {s['source']} | {s['role']} | {s['material']} | {s['rowsUsed']} | {s['parameterSets']} | {s.get('doi')} | "
                 f"{('`' + s['tableSha256'] + '`') if s.get('tableSha256') else 'n/a (literature catalog table, not file-hashed)'} |")
    L += ["", "## What this does not show", ""] + [f"- {x}" for x in doc["whatThisDoesNotShow"]]
    return "\n".join(L).rstrip("\n") + "\n"


# ---------------------------------------------------------------------------------------------
# io
# ---------------------------------------------------------------------------------------------
def dump_json(obj: Any, indent: Optional[int] = 1) -> str:
    return json.dumps(obj, sort_keys=True, indent=indent, ensure_ascii=False, allow_nan=False) + "\n"


def write_all(doc: Dict[str, Any], repo_root: Path) -> Dict[str, Path]:
    stem = f"{SCORECARD_STEM}{doc['generatedAt']}"
    docs = repo_root / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    paths = {"json": docs / f"{stem}.json", "view": docs / f"{stem}.view.json", "md": docs / f"{stem}.md",
             "artefact": repo_root / ARTEFACT_REL_PATH}
    body = dump_json(doc)
    doc = json.loads(body)  # render everything from the round-tripped record, exactly as --check does
    paths["json"].write_text(body, encoding="utf-8", newline="\n")
    sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    paths["view"].write_text(dump_json(make_view(doc)), encoding="utf-8", newline="\n")
    paths["md"].write_text(render_markdown(doc), encoding="utf-8", newline="\n")
    art = build_artefact(doc, f"docs/{stem}.json", sha)
    paths["artefact"].parent.mkdir(parents=True, exist_ok=True)
    paths["artefact"].write_text(dump_json(art), encoding="utf-8", newline="\n")
    paths["summary"] = repo_root / SUMMARY_REL_PATH
    paths["summary"].write_text(dump_json(build_summary(art)), encoding="utf-8", newline="\n")
    return paths


def check_outputs(repo_root: Path, date: str) -> List[str]:
    """Re-render view + markdown + artefact consistency from the committed full JSON; list every drift."""
    stem = f"{SCORECARD_STEM}{date}"
    docs = repo_root / "docs"
    problems: List[str] = []
    jpath = docs / f"{stem}.json"
    if not jpath.is_file():
        return [f"missing {jpath}"]
    raw = jpath.read_text(encoding="utf-8")
    doc = json.loads(raw)
    if dump_json(doc) != raw:
        problems.append("full scorecard JSON is not in canonical form")
    for suffix, want in ((".view.json", dump_json(make_view(doc))), (".md", render_markdown(doc))):
        p = docs / f"{stem}{suffix}"
        if not p.is_file() or p.read_text(encoding="utf-8") != want:
            problems.append(f"{p.name} drifts from the re-rendered text")
    ap = repo_root / ARTEFACT_REL_PATH
    if not ap.is_file():
        problems.append(f"missing {ARTEFACT_REL_PATH}")
    else:
        art = json.loads(ap.read_text(encoding="utf-8"))
        if not verify_artefact_hash(art):
            problems.append("artefact contentSha256 does not match its content")
        if art.get("scorecardSha256") != hashlib.sha256(raw.encode("utf-8")).hexdigest():
            problems.append("artefact scorecardSha256 does not match the scorecard JSON")
        if art.get("configSha256") != config_sha256(CFG) or doc.get("configSha256") != config_sha256(CFG):
            problems.append("config sha256 differs from the compiled-in CALIBRATION_CONFIG")
        want_art = dump_json(build_artefact(doc, f"docs/{stem}.json", hashlib.sha256(raw.encode('utf-8')).hexdigest()))
        if ap.read_text(encoding="utf-8") != want_art:
            problems.append("artefact drifts from the one re-built from the scorecard JSON")
        sp = repo_root / SUMMARY_REL_PATH
        if not sp.is_file() or sp.read_text(encoding="utf-8") != dump_json(build_summary(art)):
            problems.append(f"{SUMMARY_REL_PATH} is missing or drifts from the artefact (id/hash/cell statuses)")
    return problems


def refuse_record_dir(out_dir: Path, root: Path) -> None:
    """A user-source run must never write into a committed record location (docs/, data/calibration/) or the repo
    root itself (whose docs/ and data/calibration/ it would overwrite)."""
    o, r = out_dir.resolve(), root.resolve()
    for forbidden in (r, r / "docs", r / "data" / "calibration"):
        if o == forbidden or (forbidden != r and forbidden in o.parents):
            raise SystemExit(f"--out-dir {out_dir} is a committed record location; pick a scratch directory "
                             "(for example under .runtime/)")


def committed_record_date(repo_root: Path) -> Optional[str]:
    """generatedAt of the committed artefact: the record --check verifies when no --date is given."""
    ap = repo_root / ARTEFACT_REL_PATH
    if not ap.is_file():
        return None
    return json.loads(ap.read_text(encoding="utf-8")).get("generatedAt")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--table-cache", default=None)
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--date", default=GENERATED_AT_DEFAULT,
                    help="record date (default: today for a fresh run; --check defaults to the committed artefact's date)")
    ap.add_argument("--quick", action="store_true", help="first 40 rows per source (smoke run; not for records)")
    ap.add_argument("--check", action="store_true", help="re-render from the written JSON and fail on drift")
    ap.add_argument("--repo-root", default=str(REPO_ROOT))
    ap.add_argument("--user-source", action="append", default=[], metavar="ROWS_JSON",
                    help="rows.json written by lpbf_next_experiment.py import; repeatable; joins as one extra "
                         "trainable source in a private run (requires --out-dir)")
    ap.add_argument("--out-dir", default=None,
                    help="where a --user-source run writes its outputs; refuses docs/ and data/calibration/")
    a = ap.parse_args(argv)
    root = Path(a.repo_root).resolve()
    if a.out_dir and not a.user_source:
        ap.error("--out-dir is only for a --user-source run")
    if a.user_source:
        if not a.out_dir:
            ap.error("--user-source requires --out-dir (a private run never writes the committed records)")
        if a.check:
            ap.error("--check verifies the committed records and cannot be combined with --user-source")
        refuse_record_dir(Path(a.out_dir), root)
    if a.check:
        date = a.date or committed_record_date(root)
        problems = check_outputs(root, date) if date else [f"no committed artefact at {ARTEFACT_REL_PATH}"]
        for p in problems:
            print("DRIFT:", p, file=sys.stderr)
        print("check", "FAILED" if problems else "PASSED", file=sys.stderr)
        return 1 if problems else 0
    if a.quick and root == REPO_ROOT:
        raise SystemExit("--quick writes smoke output; pass --repo-root <scratch dir> so no record is overwritten")
    a.date = a.date or datetime.date.today().isoformat()
    t0 = time.perf_counter()
    cache = Path(a.table_cache).resolve() if a.table_cache else None
    if a.user_source:
        import lpbf_user_measurements as um
        try:
            user_docs = [um.load_user_rows(p) for p in a.user_source]
        except um.UserMeasurementError as exc:
            raise SystemExit(f"error: {exc}")
        doc = build_document(a.quick, a.jobs, a.date, table_cache=cache, log=lambda m: print(m, file=sys.stderr),
                             user_sources=user_docs)
        paths = write_all(doc, Path(a.out_dir).resolve())
        print(f"private run with user sources {', '.join(d['sourceId'] for d in user_docs)}: config sha256 "
              f"{doc['configSha256']} (production {config_sha256(CFG)})", file=sys.stderr)
        print(f"wrote {', '.join(p.name for p in paths.values())} to {a.out_dir} in {time.perf_counter() - t0:.0f} s",
              file=sys.stderr)
        return 0
    doc = build_document(a.quick, a.jobs, a.date, table_cache=cache, log=lambda m: print(m, file=sys.stderr))
    paths = write_all(doc, root)
    print(f"wrote {', '.join(p.name for p in paths.values())} in {time.perf_counter() - t0:.0f} s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
