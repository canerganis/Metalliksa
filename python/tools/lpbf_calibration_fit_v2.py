#!/usr/bin/env python3
"""LPBF melt-pool calibration v2 scorecard (``npm run lpbf:calibration:v2``). Pre-registered protocol:
``python/lpbf_calibration_config_v2.py`` and docs/LPBF_CALIBRATION_V2_PREREGISTRATION_2026-10-07.md.

HELD-OUT CALIBRATION OF NUISANCE PARAMETERS, NOT EXPERIMENTAL VALIDATION. The v1 pipeline
(``lpbf_calibration_fit``, ``lpbf_calibration_cells``) is reused unchanged on the v1 trainable sources; v2 adds:

* test-only literature sources (Ghosh IN625, Trapp 316L) scored with the alloy's FINAL served fit, rung and interval
  (trained on all trainable sources of the alloy), entering the gate as extra held-out sources (block-only);
* the Ghosh spot-size nuisance (140 / 100 um) next to the KU beam nuisance (37.5 / 75 um): one decision under every
  reading, else ``rejected: unresolved input``;
* an external absorptivity sanity envelope on fitted eta (diagnostic only, never a target, never in the gate);
* a per-cell before/after comparison against the committed v1 record.

Outputs (new file names; the v1 records are never written by this tool):
  data/calibration/lpbf-meltpool-calibration-v2.json (+ .summary.json)
  docs/LPBF_CALIBRATION_SCORECARD_v2_<date>.json / .view.json / .md

Usage (repo root, PYTHONDONTWRITEBYTECODE=1):
    python -B python/tools/lpbf_calibration_fit_v2.py --table-cache .runtime/cache/lpbf_calib_table.json --jobs 12
    python -B python/tools/lpbf_calibration_fit_v2.py --check
"""

from __future__ import annotations

import argparse
import copy
import datetime
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np

TOOLS_DIR = Path(__file__).resolve().parent
PYTHON_DIR = TOOLS_DIR.parent
REPO_ROOT = PYTHON_DIR.parent
sys.path.insert(0, str(PYTHON_DIR))
sys.path.insert(0, str(TOOLS_DIR))

import lpbf_calibration_cells as cl  # noqa: E402
import lpbf_calibration_fit as F  # noqa: E402
import lpbf_calibration_stats as st  # noqa: E402
from lpbf_calibration_config import ARTEFACT_REL_PATH as V1_ARTEFACT_REL_PATH  # noqa: E402
from lpbf_calibration_config_v2 import (  # noqa: E402
    ARTEFACT_V2_REL_PATH, CALIBRATION_CONFIG_V2, CALIBRATION_SCHEMA_V2, GHOSH_SPOT_READINGS_UM, KERNELS,
    PREREGISTRATION_DOC, SCORECARD_SCHEMA_V2, SCORECARD_V2_STEM, TEST_ONLY_SOURCES, config_sha256, envelope_check,
    second_source_credit)

CFG = CALIBRATION_CONFIG_V2
QS = F.QS
SUMMARY_V2_REL_PATH = ARTEFACT_V2_REL_PATH.replace(".json", ".summary.json")
SUMMARY_V2_SCHEMA = "lpbf-meltpool-calibration-summary-2"
CALIBRATION_VERSION = "v2"
TEST_ONLY_ROLE = "test-only (held out, never trained)"


# ---------------------------------------------------------------------------------------------
# rows
# ---------------------------------------------------------------------------------------------
def _lit_row(r: Dict[str, Any], sid: str) -> Dict[str, Any]:
    row = {"rowId": r["rowId"], "source": sid, "material": r["material"], "power_W": float(r["power_W"]),
           "speed_mm_s": float(r["speed_mm_s"]), "beamDiameter_um": float(r["beamDiameter_um"]),
           "preheat_C": float(r["preheat_C"]), "layer_um": r.get("layer_um"), "hatch_um": r.get("hatch_um"),
           "width_um": float(r["width_um"]), "depth_um": float(r["depth_um"]), "balling": None,
           "publishedLabel": None, "catalog": False, "testOnly": True, "digitized": bool(r.get("digitized"))}
    F._classify(row)
    return row


def load_test_only_rows(quick: bool = False) -> Dict[str, Any]:
    """{'rows': {source: {readingKey: [rows]}}, 'excluded': [...], 'provenance': {source: {...}}}."""
    import lpbf_literature_datasets as L
    rows: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    excluded: List[Dict[str, str]] = []
    prov: Dict[str, Any] = {}
    for spot in GHOSH_SPOT_READINGS_UM:
        g = L.load_ghosh_in625(beam_diameter_um=spot)
        rows.setdefault("ghosh-in625-2018", {})[f"{spot:g}"] = [_lit_row(r, "ghosh-in625-2018") for r in g["rows"]]
        if spot == GHOSH_SPOT_READINGS_UM[0]:
            p = g["provenance"]
            prov["ghosh-in625-2018"] = {"doi": p["doi"], "tableSha256": p["fileSha256"], "license": p["license"],
                                        "citation": p["citation"], "loaderRows": len(g["rows"]), "loaderExcluded": [],
                                        "beamDiameter_um": spot, "beamDiameterStatus":
                                            "ASSUMED (not stated in the paper); nuisance readings "
                                            + " / ".join(f"{x:g}" for x in GHOSH_SPOT_READINGS_UM) + " um",
                                        "role": TEST_ONLY_ROLE}
    t = L.load_trapp_316l_tracks()
    keep = []
    for r in t["rows"]:
        if r["depth_um"] is None:
            excluded.append({"rowId": r["rowId"], "reason": "no plotted depth in Trapp Fig. 3(a): excluded from both "
                                                            "quantities (pre-registered)"})
            continue
        keep.append(_lit_row(r, "trapp-316l-2017"))
    rows["trapp-316l-2017"] = {"stated": keep}
    p = t["provenance"]
    prov["trapp-316l-2017"] = {"doi": p["doi"], "tableSha256": p["fileSha256"], "license": p["license"],
                               "citation": p["citation"], "loaderRows": len(t["rows"]),
                               "loaderExcluded": [x for x in excluded if x["rowId"].startswith("trapp")],
                               "digitized": True, "role": TEST_ONLY_ROLE}
    if quick:
        rows = {s: {k: v[:40] for k, v in d.items()} for s, d in rows.items()}
    return {"rows": rows, "excluded": excluded, "provenance": prov}


# ---------------------------------------------------------------------------------------------
# test-only evaluation (the alloy's FINAL served fit, rung and interval; theta fixed)
# ---------------------------------------------------------------------------------------------
def evaluate_test_only(fk_train: st.FineKernel, res: Dict[str, Any], alloy: str, source: str,
                       test_rows: List[Dict[str, Any]], kernel: str, table: Dict[str, Any],
                       cfg: Dict[str, Any] = CFG) -> Dict[str, Any]:
    for r in test_rows:
        if r["source"] != source or not r.get("testOnly") or r["material"] != alloy:
            raise AssertionError(f"test-only evaluation got a foreign row {r['rowId']}")
    train_idx = cl.alloy_idx(fk_train, alloy)
    banned = set(TEST_ONLY_SOURCES) | set(cfg["dataRoles"]["catalogSentinels"])
    leaked = sorted({fk_train.sources[s] for s in set(fk_train.source_idx[train_idx].tolist())} & banned)
    if leaked:
        raise AssertionError(f"test-only or sentinel source in the training rows: {leaked}")
    fk_t = F.fine_kernel(test_rows, kernel, table)
    test_idx = np.arange(len(test_rows))
    fit = res["final"]["fit"]
    sel = res["final"]["selection"]
    rec: Dict[str, Any] = {"heldOutSource": source, "trainSources": list(res["sources"]),
                           "nTestRows": int(test_idx.size), "nTestSets": int(len(np.unique(fk_t.set_idx))),
                           "fit": fit, "selection": sel, "byQuantity": {},
                           "fitFrom": "final fit + served rung + final interval of the alloy (all trainable sources)"}
    for q in QS:
        rung = sel[q]["rung"]
        ev = cl.evaluate_rungs(fk_train, test_idx, train_idx, fit, rung, q, cfg, 0, fk_test=fk_t)
        ip = res["cells"][q]["intervalParams"]
        ev["servedRung"] = rung
        ev["intervalParams"] = ip
        ev["served"] = cl.served_block(fk_t, test_idx, fit, rung, q, ip, cfg)
        ev["byRegimeClass"] = cl.class_cut(fk_t, test_idx, fit, rung, q)
        ev["flags"] = res["cells"][q]["flags"]
        rec["byQuantity"][q] = ev
    rec["unresolvedAtDefault"] = int((~fk_t.defOk).sum())
    rec["statusAtDefault"] = dict(sorted(Counter(fk_t.default_status).items()))
    return rec


def test_only_gate_entry(rec: Dict[str, Any], q: str) -> Dict[str, Any]:
    qe = rec["byQuantity"][q]
    rung = qe["servedRung"]
    served = qe["rungs"].get(rung, {})
    sk = (served.get("skillVsDefault") or {}) if rung != "default" else {"skill": 0.0, "ci95": [0.0, 0.0]}
    cov90 = qe["served"]["coverage"].get("90") if qe["served"]["coverage"] else None
    return {"source": rec["heldOutSource"], "skillLb95": (sk.get("ci95") or [None])[0], "skill": sk.get("skill"),
            "coverage90N": cov90["n"] if cov90 else 0,
            "coverage90WilsonUpper": cov90["wilson95"][1] if cov90 and cov90.get("wilson95") else None,
            "unresolvedRung": served.get("unresolved", 0) if rung != "default" else 0,
            "unresolvedDefault": qe["rungs"]["default"]["unresolved"], "role": "test-only"}


def v2_gate(cell_ev: Dict[str, Any], entries: Sequence[Dict[str, Any]], cfg: Dict[str, Any] = CFG) -> Dict[str, Any]:
    """The unchanged v1 gate on the v1 evidence plus test-only held-out entries (pre-registered rules 3-5)."""
    ev = copy.deepcopy(cell_ev)
    ev["p2"] = list(ev.get("p2") or []) + [dict(e) for e in entries]
    credit = [e["source"] for e in entries if second_source_credit(e["source"], e.get("nRows", 0), cfg)]
    ev["hasSecondSource"] = bool(ev.get("hasSecondSource")) or bool(credit)
    if any(e.get("unresolvedRung", 0) > e.get("unresolvedDefault", 0) for e in entries):
        ev["unresolvedWorse"] = True
    g = st.gate_cell(ev, cfg["gate"])
    g["secondSourceCredit"] = credit
    return g


def combine_readings(statuses: Dict[str, Dict[str, Any]], primary: str) -> Dict[str, Any]:
    """One decision under every nuisance reading (KU beam x Ghosh spot), else rejected: unresolved input."""
    st_map = {k: v["status"] for k, v in statuses.items()}
    if len(set(st_map.values())) > 1:
        return {"status": "rejected", "reasons": ["unresolvedInput: decision differs between nuisance readings "
                                                  + ", ".join(f"{k}={v}" for k, v in sorted(st_map.items()))],
                "readingStatuses": st_map}
    out = dict(statuses[primary])
    out["readingStatuses"] = st_map
    return out


def _test_only_for(alloy: str, test: Dict[str, Any]) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    return {s: d for s, d in test["rows"].items() if any(r["material"] == alloy for v in d.values() for r in v)}


# ---------------------------------------------------------------------------------------------
# document
# ---------------------------------------------------------------------------------------------
def _envelope_block(res: Dict[str, Any], alloy: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    fit = res["final"]["fit"]
    out: Dict[str, Any] = {"finalFit": envelope_check(alloy, {} if not fit else {
        "etaW": fit["etaW"], "etaD": fit["etaD"], "etaJoint": fit["etaJ"]}, cfg), "folds": {}}
    for s, rec in sorted(res["p2"].items()):
        f = rec["fit"]
        out["folds"][s] = envelope_check(alloy, {} if not f else {"etaW": f["etaW"], "etaD": f["etaD"],
                                                                  "etaJoint": f["etaJ"]}, cfg)
    out["flag"] = bool(out["finalFit"]["flag"] or any(v["flag"] for v in out["folds"].values()))
    return out


def v1_record(repo_root: Path) -> Optional[Dict[str, Any]]:
    ap = repo_root / V1_ARTEFACT_REL_PATH
    if not ap.is_file():
        return None
    art = json.loads(ap.read_text(encoding="utf-8"))
    rp = repo_root / art["scorecardRecord"]
    if not rp.is_file():
        return None
    doc = json.loads(rp.read_text(encoding="utf-8"))
    return {"record": art["scorecardRecord"], "configSha256": art["configSha256"], "calibrationId": art["calibrationId"],
            "cells": {(c["kernel"], c["material"], c["quantity"]): c for c in doc["cells"]}}


def preregistration_info() -> Dict[str, Any]:
    return {"doc": PREREGISTRATION_DOC, "config": "python/lpbf_calibration_config_v2.py",
            "configCommit": F._git(["log", "-1", "--format=%H", "--", ":(top)python/lpbf_calibration_config_v2.py"]),
            "statement": "roles, nuisance readings, test-only gate rules and the absorptivity envelope were committed "
                         "before the first v2 run"}


def build_document(quick: bool, jobs: int, generated_at: str, table_cache: Optional[Path] = None,
                   solver: Optional[Callable] = None, rows_override: Optional[Dict[float, Dict[str, Any]]] = None,
                   test_override: Optional[Dict[str, Any]] = None, fp_override: Optional[str] = None,
                   revision: Optional[Dict[str, Any]] = None, log: Optional[Callable[[str], None]] = None,
                   v1_override: Optional[Dict[str, Any]] = None, prereg_override: Optional[Dict[str, Any]] = None,
                   cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = CFG if cfg is None else cfg
    st.pin_flat_plate()
    if fp_override is None:
        from lpbf_simulation import implementation_fingerprint
        fp = implementation_fingerprint()
    else:
        fp = fp_override
    loads = rows_override or {b: F.load_rows(quick, b) for b in F.BEAM_VARIANTS}
    test = test_override or load_test_only_rows(quick)
    for d in test["rows"].values():
        for rr in d.values():
            for r in rr:
                if r["source"] in cfg["dataRoles"]["trainable"] or not r.get("testOnly"):
                    raise AssertionError(f"row {r['rowId']} is not a test-only row")
    primary = sorted(loads)[0]
    rows_by_variant = {b: loads[b]["trainable"] for b in loads}
    for b, rows in rows_by_variant.items():
        bad = sorted({r["source"] for r in rows if r["source"] in TEST_ONLY_SOURCES or r.get("testOnly")})
        if bad:
            raise AssertionError(f"test-only source in the trainable rows: {bad}")
    catalog = loads[primary]["catalog"]
    provenance = dict(loads[primary]["provenance"])
    provenance.update(test["provenance"])
    all_rows: Dict[str, Dict[str, Any]] = {}
    for b in loads:
        for r in loads[b]["trainable"] + loads[b]["catalog"]:
            all_rows[F.input_key(r)] = r
    for d in test["rows"].values():
        for rr in d.values():
            for r in rr:
                all_rows[F.input_key(r)] = r
    nodes = F.node_grid(sorted({r["defaultAbsorptivity"] for r in all_rows.values()}))
    table, table_source = F.load_or_build_table(list(all_rows.values()), fp, jobs, table_cache, nodes, solver)
    if log:
        log(f"kernel table: {table_source}")
    for m, v in cfg["materialDefaults"].items():
        live = {r["material"]: r["defaultAbsorptivity"] for r in all_rows.values()}
        if m in live and abs(live[m] - v) > 1e-9:
            raise SystemExit(f"CALIBRATION_CONFIG_V2 materialDefaults[{m}]={v} != live default {live[m]}")
    analysis = F.run_analysis(rows_by_variant, table, log=log, cfg=cfg)
    base_cells = F.build_cells(analysis, rows_by_variant)
    results = analysis["results"]
    v1 = v1_override if v1_override is not None else v1_record(REPO_ROOT)

    cells: List[Dict[str, Any]] = []
    test_only_records: List[Dict[str, Any]] = []
    envelope_rows: List[Dict[str, Any]] = []
    for c in base_cells:
        c = copy.deepcopy(c)
        k, alloy, q = c["kernel"], c["material"], c["quantity"]
        c["statusTrainableOnly"] = c["status"]
        c["reasonsTrainableOnly"] = c["reasons"]
        c["headlineTrainableOnly"] = c["headline"]
        old = (v1 or {}).get("cells", {}).get((k, alloy, q))
        c["v1Status"] = old["status"] if old else None
        if c["status"] == "no-data":
            c.update(testOnly=[], readingStatuses=None, absorptivityEnvelope=None)
            cells.append(c)
            continue
        tsrc = _test_only_for(alloy, test)
        per_reading: Dict[str, Dict[str, Any]] = {}
        primary_entries: List[Dict[str, Any]] = []
        primary_key = None
        for b in sorted(results):
            res = results[b][k].get(alloy)
            if res is None:
                continue
            readings: List[Dict[str, Any]] = [{}]
            for s, d in sorted(tsrc.items()):
                readings = [dict(x, **{s: key}) for x in readings for key in d]
            for rd in readings:
                key = f"ku{b:g}" + "".join(f"|{s.split('-')[0]}{rk}" for s, rk in sorted(rd.items()) if rk != "stated")
                entries, recs = [], []
                for s, rk in sorted(rd.items()):
                    rec = evaluate_test_only(analysis["fks"][b][k], res, alloy, s, test["rows"][s][rk], k, table, cfg)
                    e = test_only_gate_entry(rec, q)
                    e["nRows"] = rec["nTestRows"]
                    entries.append(e)
                    recs.append((s, rk, rec))
                per_reading[key] = {"gate": v2_gate(res["cells"][q]["evidence"], entries, cfg), "recs": recs}
                if primary_key is None:
                    primary_key = key
        gate = combine_readings({kk: v["gate"] for kk, v in per_reading.items()}, primary_key)
        c["status"], c["reasons"] = gate["status"], gate["reasons"]
        c["readingStatuses"] = gate.get("readingStatuses")
        c["secondSourceCredit"] = gate.get("secondSourceCredit", [])
        prim = per_reading[primary_key]
        t_rows = []
        for s, rk, rec in prim["recs"]:
            pr = F.p2_rows({"p2": {s: rec}}, q)[0]
            pr.update(role="test-only", reading=rk, fitFrom=rec["fitFrom"])
            t_rows.append(pr)
            test_only_records.append({"kernel": k, "material": alloy, "quantity": q, "source": s, "reading": rk,
                                      "nRows": pr["nRows"], "rung": pr["rung"], "mapeDefault": pr["mapeDefault"],
                                      "mapeServed": pr["mapeServed"], "skill": pr["skill"],
                                      "skillCi95": pr["skillCi95"], "coverage90": pr["coverage90"],
                                      "unresolvedDefault": pr["unresolvedDefault"],
                                      "unresolvedServed": pr["unresolvedServed"], "byRegimeClass": pr["byRegimeClass"],
                                      "biasDefault": pr["biasDefault"], "biasServed": pr["biasServed"],
                                      "mapeUnresolvedAsFailDefault": pr["mapeUnresolvedAsFailDefault"]})
        sens = {}
        for kk, v in per_reading.items():
            if kk == primary_key:
                continue
            sens[kk] = {"status": v["gate"]["status"], "reasons": v["gate"]["reasons"],
                        "testOnly": [dict(F.p2_rows({"p2": {s: rec}}, q)[0], role="test-only", reading=rk)
                                     for s, rk, rec in v["recs"]]}
        c["readingSensitivity"] = sens or None
        for r in c["p2"]:
            r.setdefault("role", "trainable fold")
        c["p2"] = list(c["p2"]) + t_rows
        c["testOnly"] = t_rows
        c["headline"] = F.equal_weight_headline(c["p2"]) if c["p2"] else None
        res_p = results[primary][k][alloy]
        env = _envelope_block(res_p, alloy, cfg)
        c["absorptivityEnvelope"] = env
        if q == "width":
            for b in sorted(results):
                res_b = results[b][k].get(alloy)
                if res_b is None:
                    continue
                env_b = env if b == primary else _envelope_block(res_b, alloy, cfg)
                fit_b = res_b["final"]["fit"] or {}
                envelope_rows.append({"kernel": k, "material": alloy, "kuBeam_um": b if alloy != "Inconel 625" else None,
                                      "envelope": env_b["finalFit"]["envelope"],
                                      "finalFit": {"etaW": fit_b.get("etaW"), "etaD": fit_b.get("etaD"),
                                                   "etaJoint": fit_b.get("etaJ")},
                                      "finalOutside": env_b["finalFit"]["outside"],
                                      "foldsOutside": {s: v["outside"] for s, v in env_b["folds"].items() if v["outside"]},
                                      "flag": env_b["flag"]})
        cells.append(c)

    sources_info = []
    primary_rows = rows_by_variant[primary]
    for s in list(cfg["dataRoles"]["trainable"]) + list(cfg["dataRoles"]["catalogSentinels"]):
        rr = [r for r in primary_rows + catalog if r["source"] == s]
        if not rr:
            continue
        info = dict(provenance.get(s, {}))
        info.update({"source": s, "role": "trainable" if s in cfg["dataRoles"]["trainable"] else "catalog-sentinel (test-only)",
                     "material": rr[0]["material"], "rowsUsed": len(rr), "parameterSets": len({st.set_key(r) for r in rr})})
        sources_info.append(info)
    for s in TEST_ONLY_SOURCES:
        d = test["rows"].get(s)
        if not d:
            continue
        rr = next(iter(d.values()))
        info = dict(provenance.get(s, {}))
        info.update({"source": s, "role": TEST_ONLY_ROLE, "material": rr[0]["material"], "rowsUsed": len(rr),
                     "parameterSets": len({st.set_key(r) for r in rr}), "readings": sorted(d)})
        sources_info.append(info)

    unresolved = F.unresolved_accounting(analysis, provenance, catalog, table)
    for kern in KERNELS:
        for s, d in sorted(test["rows"].items()):
            for rk, rr in sorted(d.items()):
                fk_t = F.fine_kernel(rr, kern, table)
                unresolved["perKernelSource"].append({
                    "kernel": kern, "source": s if rk == "stated" else f"{s} (spot {rk} um)", "rowsUsed": len(rr),
                    "resolvedAtDefault": int(fk_t.defOk.sum()), "unresolvedAtDefault": int((~fk_t.defOk).sum()),
                    "statusAtDefault": dict(sorted(Counter(fk_t.default_status).items())), "role": "test-only"})
    for s in TEST_ONLY_SOURCES:
        p = provenance.get(s)
        if p:
            unresolved["loader"].append({"source": s, "loaderRows": p["loaderRows"], "excludedByLoader": p["loaderExcluded"]})
    unresolved["loader"] = sorted(unresolved["loader"], key=lambda x: x["source"])
    unresolved["notGeometrySources"] = list(unresolved["notGeometrySources"]) + [
        {"source": k2, "reason": v} for k2, v in sorted(cfg["notUsedReferences"].items())] + [
        {"source": "trapp absorptivity, ye 2019, rubenchik 2015", "reason": "absorptivity references: external sanity "
                                                                          "envelope on fitted eta only"}]

    counts = Counter(c["status"] for c in cells)
    counts_tr = Counter(c["statusTrainableOnly"] for c in cells)
    comparison = [{"kernel": c["kernel"], "material": c["material"], "quantity": c["quantity"], "v1": c["v1Status"],
                   "v2TrainableOnly": c["statusTrainableOnly"], "v2": c["status"],
                   "changed": c["v1Status"] is not None and c["v1Status"] != c["status"]} for c in cells]
    reproduces = all(x["v1"] == x["v2TrainableOnly"] for x in comparison) if v1 else None
    doc = {
        "schema": SCORECARD_SCHEMA_V2, "calibrationVersion": CALIBRATION_VERSION, "generatedAt": generated_at,
        "quick": bool(quick), "implementationHash": fp, "codeRevision": revision or F.code_revision(),
        "tool": {"path": "python/tools/lpbf_calibration_fit_v2.py", "sha256": tool_sha256(),
                 "reuses": {"path": "python/tools/lpbf_calibration_fit.py", "sha256": F.tool_sha256()}},
        "config": cfg, "configSha256": config_sha256(cfg),
        "preRegistration": prereg_override if prereg_override is not None else preregistration_info(),
        "supersedes": {"record": (v1 or {}).get("record"), "configSha256": (v1 or {}).get("configSha256"),
                       "calibrationId": (v1 or {}).get("calibrationId"),
                       "note": "v1 is kept unchanged and still verifies; calibrated mode still reads the v1 artefact"},
        "evidence": {"kind": F.EVIDENCE_KIND, "label": F.EVIDENCE_LABEL, "labelPromotionProposed": F.LABEL_PROMOTION,
                     "experimentalValidation": False, "opticalOperatorMatched": False, "statement": F.HONESTY},
        "kernel": {"entryPoint": "lpbf_thermal_solver.calculate_meltpool_physics(heat_source=<kernel>)",
                   "absorptionPath": "flat-plate (absorption_model='flat-plate'; powder_bed_raytracer pinned unimportable)",
                   "varied": "prop_overrides={'absorptivity_IR': eta}; the default call has no override",
                   "nodes": nodes, "uniqueInputs": len(table["entries"]),
                   "tableSha256": st.canonical_sha256({k2: table[k2] for k2 in ("nodes", "kernels", "statuses", "entries")}),
                   "tableNote": "content-hashed kernel table; two runs on the same table are byte-identical"},
        "sources": sources_info,
        "gateSummary": dict(sorted(counts.items())),
        "gateSummaryTrainableOnly": dict(sorted(counts_tr.items())),
        "v1Comparison": comparison, "reproducesV1TrainableOnly": reproduces,
        "testOnlySummary": test_only_records,
        "absorptivityEnvelope": {"rule": cfg["absorptivityReferences"]["rule"],
                                 "role": cfg["absorptivityReferences"]["role"],
                                 "weakness": cfg["absorptivityReferences"]["weakness"], "rows": envelope_rows},
        "envelope": F.training_envelope(primary_rows),
        "cells": cells,
        "regimeConfusion": F.confusion_block(analysis, rows_by_variant),
        "catalogSentinels": F.sentinel_block(analysis, catalog, table),
        "unresolved": unresolved,
        "coverage": F.coverage_table(cells),
        "betweenSource": F.between_source_summary(analysis),
        "whatThisDoesNotShow": what_this_does_not_show(),
    }
    return st.round_sig(doc, cfg["rounding"]["significantDigits"])


def what_this_does_not_show() -> List[str]:
    return F.what_this_does_not_show() + [
        "v2 adds two test-only literature sources (Ghosh IN625: 7 rows, spot size assumed; Trapp 316L: 10 rows "
        "digitized from a figure, thin discs). They can block a cell but cannot enable one, and they never train.",
        "The absorptivity envelope (Trapp 2017, Ye 2019) is a sanity check on fitted effective eta, not a target; the "
        "316L envelope spans almost the whole fit bound and the Ti-6Al-4V / Inconel 625 envelopes are one-sided.",
        "Calibrated mode still reads the v1 artefact; the runtime layer refuses the v2 config hash.",
    ]


def tool_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


# ---------------------------------------------------------------------------------------------
# artefact, view, markdown
# ---------------------------------------------------------------------------------------------
def build_artefact(doc: Dict[str, Any], scorecard_rel: str, scorecard_sha: str) -> Dict[str, Any]:
    cells = []
    for c in doc["cells"]:
        p = c["params"]
        cells.append({
            "kernel": c["kernel"], "material": c["material"], "quantity": c["quantity"], "status": c["status"],
            "statusTrainableOnly": c["statusTrainableOnly"], "v1Status": c.get("v1Status"),
            "rung": c["rung"], "reasons": c["reasons"],
            "params": None if p is None else {k: p.get(k) for k in (
                "etaW", "etaD", "etaJoint", "etaW_ci90", "etaD_ci90", "etaJoint_ci90", "cD", "cDSource", "etaPrior")},
            "interval": None if c["interval"] is None else {k: c["interval"][k] for k in ("m", "sWithin", "sSource", "levels")},
            "heldOutScore": [{k: r.get(k) for k in ("heldOut", "trainedOn", "rung", "nRows", "nSets", "mapeDefault",
                                                    "mapeServed", "skill", "skillCi95", "coverage90", "role", "reading")}
                             for r in c["p2"]],
            "withinSourceScore": [{k: r.get(k) for k in ("source", "nRows", "nSets", "skill", "skillCi95")} for r in c["p1"]],
            "flags": c["flags"], "readingStatuses": c.get("readingStatuses"),
            "absorptivityEnvelopeFlag": (c.get("absorptivityEnvelope") or {}).get("flag")})
    cfg = doc["config"]
    art = {
        "schema": CALIBRATION_SCHEMA_V2, "calibrationVersion": CALIBRATION_VERSION,
        "calibrationId": "", "generatedAt": doc["generatedAt"], "implementationHash": doc["implementationHash"],
        "codeRevision": doc["codeRevision"], "tool": doc["tool"], "configSha256": doc["configSha256"], "config": cfg,
        "preRegistration": doc["preRegistration"], "supersedes": doc["supersedes"],
        "trainingData": [{k: s.get(k) for k in ("source", "doi", "tableSha256", "rowsUsed", "parameterSets", "material")}
                         for s in doc["sources"] if s["role"] == "trainable"],
        "testOnlySources": [{k: s.get(k) for k in ("source", "doi", "tableSha256", "rowsUsed", "parameterSets", "material",
                                                   "readings")} for s in doc["sources"] if s["role"] == TEST_ONLY_ROLE],
        "catalogSentinelSources": [s["source"] for s in doc["sources"] if s["role"].startswith("catalog")],
        "heldOutSources": ("leave-one-source-out inside each alloy over the trainable sources, plus every test-only "
                           "source scored with the alloy's final served fit"),
        "priors": {m: {"eta": v, "lambda": cfg["prior"]["lambda"], "bounds": cfg["bounds"],
                       "basis": "material default absorptivity_IR; measured absorptance only as bands / envelope"}
                   for m, v in cfg["materialDefaults"].items()},
        "envelope": doc["envelope"], "cells": cells, "scorecardRecord": scorecard_rel, "scorecardSha256": scorecard_sha,
        "evidenceKind": F.EVIDENCE_KIND, "proposedEvidenceKind": None, "evidenceLabel": F.EVIDENCE_LABEL,
        "labelPromotionProposed": F.LABEL_PROMOTION, "experimentalValidation": False,
        "servedByRuntime": False, "servedByRuntimeNote": ("lpbf_calibration_layer accepts only the v1 config hash; "
                                                          "exposing any v2 cell needs maintainer approval"),
        "honesty": F.HONESTY, "contentSha256": "",
    }
    art = st.round_sig(art, cfg["rounding"]["significantDigits"])
    sha = st.canonical_sha256(art)
    art["contentSha256"] = sha
    art["calibrationId"] = f"lpbf-meltpool-calib-v2-{doc['generatedAt']}-{sha[:12]}"
    return art


def build_summary(art: Dict[str, Any]) -> Dict[str, Any]:
    return {"schema": SUMMARY_V2_SCHEMA, "calibrationId": art["calibrationId"], "contentSha256": art["contentSha256"],
            "artefact": ARTEFACT_V2_REL_PATH, "evidenceKind": art["evidenceKind"], "servedByRuntime": False,
            "cells": [{"kernel": c["kernel"], "material": c["material"], "quantity": c["quantity"], "status": c["status"],
                       "v1Status": c["v1Status"]} for c in art["cells"]]}


def make_view(doc: Dict[str, Any]) -> Dict[str, Any]:
    view = F.make_view(doc)
    for h, c in zip(view["headline"], doc["cells"]):
        for r, src in zip(h["p2"], c["p2"]):
            r["role"] = src.get("role")
            r["reading"] = src.get("reading")
        h["statusTrainableOnly"] = c["statusTrainableOnly"]
        h["v1Status"] = c.get("v1Status")
        h["readingStatuses"] = c.get("readingStatuses")
        h["absorptivityEnvelopeFlag"] = (c.get("absorptivityEnvelope") or {}).get("flag")
    view.update({
        "calibrationVersion": doc["calibrationVersion"], "preRegistration": doc["preRegistration"],
        "supersedes": doc["supersedes"], "v1Comparison": doc["v1Comparison"],
        "gateSummaryTrainableOnly": doc["gateSummaryTrainableOnly"],
        "reproducesV1TrainableOnly": doc["reproducesV1TrainableOnly"],
        "testOnlySummary": doc["testOnlySummary"], "absorptivityEnvelope": doc["absorptivityEnvelope"]})
    return view


def render_markdown(doc: Dict[str, Any]) -> str:
    pr = doc["preRegistration"]
    sup = doc["supersedes"]
    L = [f"# LPBF melt-pool calibration scorecard v2 ({doc['generatedAt']})", "",
         f"**{F.EVIDENCE_LABEL}.** Calibration version 2, pre-registered in `{pr['doc']}` (config "
         f"`{pr['config']}`, commit `{pr.get('configCommit')}`, config sha256 `{doc['configSha256']}`). Supersedes the v1 "
         f"record `{sup.get('record')}` (config sha256 `{sup.get('configSha256')}`), which is unchanged and still "
         "verifies. Calibrated mode still reads the v1 artefact; the runtime layer refuses the v2 config hash. "
         "`experimentalValidation` = false; label promotion proposed: **none**.", "",
         "## v1 -> v2 per cell", "",
         "`v2 trainable-only` re-runs the v1 protocol inside v2 (it must equal v1: "
         f"{'yes' if doc['reproducesV1TrainableOnly'] else ('NO' if doc['reproducesV1TrainableOnly'] is False else 'n/a')}). "
         "`v2` adds the test-only held-out sources to the unchanged gate.", "",
         "| kernel | alloy | quantity | v1 | v2 trainable-only | v2 |", "|---|---|---|---|---|---|"]
    for x in doc["v1Comparison"]:
        L.append(f"| {x['kernel']} | {x['material']} | {x['quantity']} | {x['v1'] or '-'} | {x['v2TrainableOnly']} | "
                 f"**{x['v2']}**{' (changed)' if x['changed'] else ''} |")
    L += ["", "Status counts v2: " + ", ".join(f"{k} {v}" for k, v in doc["gateSummary"].items())
          + "; v2 trainable-only: " + ", ".join(f"{k} {v}" for k, v in doc["gateSummaryTrainableOnly"].items()) + ".", "",
          "## Test-only held-out sources (final served fit of the alloy, theta fixed)", "",
          "| kernel | alloy | q | source | reading | rows | served rung | MAPE default -> served % | bias default -> served % "
          "| skill CI95 | PI90 coverage | unresolved default / served |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for t in doc["testOnlySummary"]:
        cov = t.get("coverage90") or {}
        L.append(f"| {t['kernel']} | {t['material']} | {t['quantity']} | {t['source']} | {t['reading']} | {t['nRows']} | "
                 f"{t['rung']} | {F._f(t['mapeDefault'])} -> {F._f(t['mapeServed'])} | {F._f(t['biasDefault'])} -> "
                 f"{F._f(t['biasServed'])} | {F._f(t['skill'], 2)}{F._ci(t['skillCi95'])} | "
                 f"{F._f(cov.get('coverage'), 2)} n={cov.get('n', 0)} | {t['unresolvedDefault']} / {t['unresolvedServed']} |")
    sens = [(c, kk, v) for c in doc["cells"] for kk, v in (c.get("readingSensitivity") or {}).items()]
    if sens:
        L += ["", "Nuisance-reading sensitivity (decision per reading; must agree, else rejected: unresolved input):", ""]
        for c in doc["cells"]:
            if c.get("readingStatuses"):
                L.append(f"- {c['kernel']} / {c['material']} / {c['quantity']}: "
                         + ", ".join(f"{k} {v}" for k, v in sorted(c["readingStatuses"].items())))
    ae = doc["absorptivityEnvelope"]
    L += ["", "## Fitted effective absorptivity vs the measured envelope (diagnostic only)", "", ae["rule"], "",
          f"Weakness: {ae['weakness']}.", "",
          "| kernel | alloy | KU beam um | envelope | final eta_W / eta_D / eta joint | outside (final) | outside (LOSO folds) |",
          "|---|---|---|---|---|---|---|"]
    for r in ae["rows"]:
        e = r["envelope"]
        env = "-" if not e else (f"{e['lower']:.3f} - {e['upper']:.3f}" if e["upper"] is not None else f">= {e['lower']:.3f}")
        ff = r["finalFit"]
        out_f = "; ".join(f"{o['param']} {o['eta']:.3f} {o['side']}" for o in r["finalOutside"]) or "none"
        out_l = "; ".join(f"{s}: " + ", ".join(f"{o['param']} {o['eta']:.3f} {o['side']}" for o in v)
                          for s, v in r["foldsOutside"].items()) or "none"
        L.append(f"| {r['kernel']} | {r['material']} | {r['kuBeam_um'] if r['kuBeam_um'] is not None else '-'} | {env} | {F._f(ff['etaW'], 3)} / {F._f(ff['etaD'], 3)} / "
                 f"{F._f(ff['etaJoint'], 3)} | {out_f} | {out_l} |")
    body = F.render_markdown(doc).split("\n")
    body = ["# Full v2 scorecard (v1 layout; held-out tables include the test-only rows)"] + body[1:]
    return "\n".join(L + [""] + body).rstrip("\n") + "\n"


# ---------------------------------------------------------------------------------------------
# io
# ---------------------------------------------------------------------------------------------
def write_all(doc: Dict[str, Any], repo_root: Path) -> Dict[str, Path]:
    stem = f"{SCORECARD_V2_STEM}{doc['generatedAt']}"
    docs = repo_root / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    paths = {"json": docs / f"{stem}.json", "view": docs / f"{stem}.view.json", "md": docs / f"{stem}.md",
             "artefact": repo_root / ARTEFACT_V2_REL_PATH, "summary": repo_root / SUMMARY_V2_REL_PATH}
    body = F.dump_json(doc)
    doc = json.loads(body)
    paths["json"].write_text(body, encoding="utf-8", newline="\n")
    sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    paths["view"].write_text(F.dump_json(make_view(doc)), encoding="utf-8", newline="\n")
    paths["md"].write_text(render_markdown(doc), encoding="utf-8", newline="\n")
    art = build_artefact(doc, f"docs/{stem}.json", sha)
    paths["artefact"].parent.mkdir(parents=True, exist_ok=True)
    paths["artefact"].write_text(F.dump_json(art), encoding="utf-8", newline="\n")
    paths["summary"].write_text(F.dump_json(build_summary(art)), encoding="utf-8", newline="\n")
    return paths


def verify_artefact_hash(art: Dict[str, Any]) -> bool:
    return F.verify_artefact_hash(art)


def check_outputs(repo_root: Path, date: str, cfg: Optional[Dict[str, Any]] = None) -> List[str]:
    stem = f"{SCORECARD_V2_STEM}{date}"
    docs = repo_root / "docs"
    problems: List[str] = []
    jpath = docs / f"{stem}.json"
    if not jpath.is_file():
        return [f"missing {jpath}"]
    raw = jpath.read_text(encoding="utf-8")
    doc = json.loads(raw)
    if F.dump_json(doc) != raw:
        problems.append("full v2 scorecard JSON is not in canonical form")
    for suffix, want in ((".view.json", F.dump_json(make_view(doc))), (".md", render_markdown(doc))):
        p = docs / f"{stem}{suffix}"
        if not p.is_file() or p.read_text(encoding="utf-8") != want:
            problems.append(f"{p.name} drifts from the re-rendered text")
    if doc.get("configSha256") != config_sha256(CFG if cfg is None else cfg):
        problems.append("v2 record config sha256 differs from the compiled-in CALIBRATION_CONFIG_V2")
    if doc.get("evidence", {}).get("experimentalValidation") is not False:
        problems.append("experimentalValidation must be false")
    ap = repo_root / ARTEFACT_V2_REL_PATH
    if not ap.is_file():
        problems.append(f"missing {ARTEFACT_V2_REL_PATH}")
        return problems
    art = json.loads(ap.read_text(encoding="utf-8"))
    if not verify_artefact_hash(art):
        problems.append("v2 artefact contentSha256 does not match its content")
    sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    if art.get("scorecardSha256") != sha:
        problems.append("v2 artefact scorecardSha256 does not match the scorecard JSON")
    if ap.read_text(encoding="utf-8") != F.dump_json(build_artefact(doc, f"docs/{stem}.json", sha)):
        problems.append("v2 artefact drifts from the one re-built from the scorecard JSON")
    sp = repo_root / SUMMARY_V2_REL_PATH
    if not sp.is_file() or sp.read_text(encoding="utf-8") != F.dump_json(build_summary(art)):
        problems.append(f"{SUMMARY_V2_REL_PATH} is missing or drifts from the v2 artefact")
    return problems


def committed_record_date(repo_root: Path) -> Optional[str]:
    ap = repo_root / ARTEFACT_V2_REL_PATH
    return json.loads(ap.read_text(encoding="utf-8")).get("generatedAt") if ap.is_file() else None


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--table-cache", default=None)
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--date", default=None)
    ap.add_argument("--quick", action="store_true", help="first 40 rows per source (smoke run; not for records)")
    ap.add_argument("--check", action="store_true", help="re-render from the written v2 JSON and fail on drift")
    ap.add_argument("--repo-root", default=str(REPO_ROOT))
    a = ap.parse_args(argv)
    root = Path(a.repo_root).resolve()
    if a.check:
        date = a.date or committed_record_date(root)
        problems = check_outputs(root, date) if date else [f"no committed v2 artefact at {ARTEFACT_V2_REL_PATH}"]
        for p in problems:
            print("DRIFT:", p, file=sys.stderr)
        print("check", "FAILED" if problems else "PASSED", file=sys.stderr)
        return 1 if problems else 0
    if a.quick and root == REPO_ROOT:
        raise SystemExit("--quick writes smoke output; pass --repo-root <scratch dir> so no record is overwritten")
    a.date = a.date or datetime.date.today().isoformat()
    t0 = time.perf_counter()
    cache = Path(a.table_cache).resolve() if a.table_cache else None
    doc = build_document(a.quick, a.jobs, a.date, table_cache=cache, log=lambda m: print(m, file=sys.stderr, flush=True))
    paths = write_all(doc, root)
    print(f"wrote {', '.join(p.name for p in paths.values())} in {time.perf_counter() - t0:.0f} s", file=sys.stderr)
    print("v2 gate:", doc["gateSummary"], "trainable-only:", doc["gateSummaryTrainableOnly"],
          "reproduces v1:", doc["reproducesV1TrainableOnly"], file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
