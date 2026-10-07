#!/usr/bin/env python3
"""Keyhole regime / keyhole-porosity screening of the app vs published x-ray measurements (comparison, not validation).

Reads only committed data (python/lpbf_keyhole_literature.py, pinned CSVs) and evaluates the app's EXISTING screening
WITHOUT changing it:

* the normalised-enthalpy index dH/hs with the 15 / 30 thresholds (lpbf_public_datasets.classify_regime, the
  process-map regime label; same formula and thresholds as lpbf_thermal_solver.classify_enthalpy_regime),
* the solver's keyholePorosityRisk (Negligible / Low-Moderate / High, keyed to the same 15 / 30),
* the King D/W > 0.5 keyhole-mode indicator of the geometric defect screen, per kernel (rosenthal, eagar-tsai),
* the Fabbro keyhole depth (keyholeModel.fabbroDepth_um) and the melt-pool depth of each kernel.

against Cunningham 2019 (Ti-6Al-4V vapor-depression depth and Fig. 3A regime lines) and Zhao 2020 (Ti-6Al-4V
keyhole-porosity boundary and pore observations), and puts the published scaling laws (Gan 2021 keyhole number,
Huang 2022 normalised enthalpy product, Hann 2011 vaporization-enthalpy transition) on the same cases. Gan, Huang and
Hann measured cases are not app materials and are only used for relation checks.

Usage (from python/, locked interpreter):
    python -B tools/lpbf_keyhole_benchmark.py [--out ../docs/LPBF_KEYHOLE_BENCHMARK_2026-10-07.json] [--no-kernels]
Writes <out>.json, <out>.md and <out stem>.view.json. Deterministic: no timestamps, fixed rounding.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

PYTHON_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PYTHON_DIR))

import lpbf_keyhole_literature as kl  # noqa: E402
import lpbf_public_datasets as pds  # noqa: E402

SCHEMA = "lpbf-keyhole-benchmark-1"
GENERATED_AT = "2026-10-07"
DEFAULT_OUT = PYTHON_DIR.parent / "docs" / "LPBF_KEYHOLE_BENCHMARK_2026-10-07.json"
KERNELS = ("rosenthal", "eagar-tsai")
LAYER_UM, HATCH_UM = 30.0, 100.0  # irrelevant to the single-track keyhole quantities; recorded
REGIMES3 = ("conduction", "transition", "keyhole")
LINE_SPEEDS = tuple(range(400, 1201, 100))
HONESTY = ("Comparison of the app's existing screening with published Ti-6Al-4V x-ray measurements; digitized figure "
           "values (read uncertainty recorded per row); app thermophysical properties and flat absorptivity are the "
           "app's estimates, not the papers' values; not experimental validation; nothing in the app was changed.")


def r3(x: Optional[float]) -> Optional[float]:
    return None if x is None else round(float(x), 3)


# ---------------------------------------------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------------------------------------------
def confusion(truth: Sequence[str], pred: Sequence[str], classes: Sequence[str]) -> Dict[str, Any]:
    m = {t: {p: 0 for p in classes} for t in classes}
    for t, p in zip(truth, pred):
        m[t][p] += 1
    n = len(truth)
    correct = sum(m[c][c] for c in classes)
    recall = {c: (r3(m[c][c] / sum(m[c].values())) if sum(m[c].values()) else None) for c in classes}
    return {"rowsAreReported_columnsArePredicted": m, "n": n, "correct": correct,
            "accuracy": r3(correct / n) if n else None, "recallPerReportedClass": recall}


def depth_stats(pairs: Iterable[tuple]) -> Optional[Dict[str, Any]]:
    """pairs of (predicted, measured, tolerance)."""
    pairs = [(p, m, t) for p, m, t in pairs if p is not None and m is not None]
    if not pairs:
        return None
    err = [p - m for p, m, _ in pairs]
    rel = [abs(p - m) / m for p, m, _ in pairs if m > 0]
    ratio = [p / m for p, m, _ in pairs if m > 0]
    return {"n": len(pairs), "bias_um": r3(statistics.fmean(err)), "mae_um": r3(statistics.fmean(abs(e) for e in err)),
            "rmse_um": r3(math.sqrt(statistics.fmean(e * e for e in err))),
            "mape_pct": r3(100 * statistics.fmean(rel)) if rel else None,
            "medianRatioPredOverMeas": r3(statistics.median(ratio)) if ratio else None,
            "withinTolerance": sum(1 for p, m, t in pairs if abs(p - m) <= t),
            "underpredicted": sum(1 for e in err if e < 0)}


def summary(values: Sequence[float]) -> Optional[Dict[str, float]]:
    v = [x for x in values if x is not None]
    if not v:
        return None
    return {"n": len(v), "min": r3(min(v)), "median": r3(statistics.median(v)), "max": r3(max(v))}


def ti64_props() -> Dict[str, Any]:
    p = pds.screening_props(kl.APP_MATERIAL_TI64)
    return {k: p[k] for k in ("density_kg_m3", "thermal_conductivity_W_mK", "specific_heat_J_kgK", "liquidus_C",
                              "boiling_C", "absorptivity_IR")}


def ye_eta_min_ti64() -> Dict[str, Any]:
    import lpbf_literature_datasets as lit
    d = lit.load_ye_min_absorptivity()
    row = next(r for r in d["rows"] if r["material"] == kl.APP_MATERIAL_TI64)
    return {"value": row["absorptivity"], "locator": row["locator"], "dataset": d["provenance"]["id"],
            "fileSha256": d["provenance"]["fileSha256"]}


def index_block(P: float, v: float, spot: float, preheat: float, props: Dict[str, Any], eta_min: float) -> Dict[str, Any]:
    reg = pds.classify_regime(kl.APP_MATERIAL_TI64, P, v, spot, preheat, None)
    gan = kl.gan_keyhole_number(P, v, spot, props["density_kg_m3"], props["specific_heat_J_kgK"],
                                props["thermal_conductivity_W_mK"], props["liquidus_C"], preheat, eta_min)
    return {"appIndex_dHhs": r3(reg["normalizedEnthalpy"]), "appRegime": reg["label"],
            "appPorosityRiskByIndex": ("High" if reg["normalizedEnthalpy"] >= pds.ENTHALPY_KEYHOLE else
                                       "Low-Moderate" if reg["normalizedEnthalpy"] >= pds.ENTHALPY_TRANSITION
                                       else "Negligible"),
            "ganKe": r3(gan["Ke"]), "ganEta": r3(gan["eta"]), "ganRegime": kl.gan_regime(gan["Ke"]),
            "ganKeyholeDepth_um": r3(kl.gan_keyhole_depth_um(gan["Ke"], spot)),
            "huangProduct_betaYe": r3(kl.huang_enthalpy_product(P, v, spot, eta_min)),
            "huangProduct_betaAppFlat": r3(kl.huang_enthalpy_product(P, v, spot, props["absorptivity_IR"])),
            "hannRegime": kl.hann_regime(reg["normalizedEnthalpy"])}


def kernel_block(P: float, v: float, spot: float, preheat: float) -> Dict[str, Any]:
    from lpbf_thermal_solver import calculate_meltpool_physics
    out: Dict[str, Any] = {}
    for k in KERNELS:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            res = calculate_meltpool_physics(kl.APP_MATERIAL_TI64, P, v, spot, preheat, LAYER_UM, HATCH_UM,
                                             heat_source=k, absorption_model="flat-plate")
        g = res["meltPoolGeometry"]
        gs = res.get("geometricDefectScreen") or {}
        out[k] = {"depth_um": r3(g["depth_um"]), "width_um": r3(g["width_um"]),
                  "dOverW": r3(g["depth_um"] / g["width_um"]) if g["width_um"] else None,
                  "extentStatus": g.get("extentStatus"), "solverRegime": g.get("regime"),
                  "kingModeIndicator": (gs.get("keyhole") or {}).get("kingModeIndicator"),
                  "keyholeVaporCavityDepth_um": r3(g.get("keyholeVaporCavityDepth_um")),
                  "fabbroDepth_um": r3(res["keyholeModel"]["fabbroDepth_um"]),
                  "solverIndex_dHhs": r3(res["processParameters"]["normalizedEnthalpy"]),
                  "keyholePorosityRisk": res["defectDiagnostics"]["keyholePorosityRisk"]}
    return out


# ---------------------------------------------------------------------------------------------------------------
# evaluation
# ---------------------------------------------------------------------------------------------------------------
def evaluate(run_kernels: bool = True) -> Dict[str, Any]:
    props = ti64_props()
    ye = ye_eta_min_ti64()
    eta_min = ye["value"]
    cun = kl.load_cunningham_depths()
    zb = kl.load_zhao_boundary()
    zp = kl.load_zhao_pores()
    lines = kl.cunningham_lines()

    def case(row: Dict[str, Any]) -> Dict[str, Any]:
        out = {k: row[k] for k in ("dataset", "rowId", "power_W", "speed_mm_s", "beamDiameter_um", "preheat_C",
                                   "regimeReported", "locator", "digitized")}
        out.update(index_block(row["power_W"], row["speed_mm_s"], row["beamDiameter_um"], row["preheat_C"], props,
                               eta_min))
        if run_kernels:
            out["kernels"] = kernel_block(row["power_W"], row["speed_mm_s"], row["beamDiameter_um"], row["preheat_C"])
        return out

    cun_cases = []
    for r in cun["rows"]:
        c = case(r)
        c.update(vaporDepressionDepth_um=r["vaporDepressionDepth_um"], depthSd_um=r["depthSd_um"],
                 readUncertainty_um=r["readUncertainty_um"], regimeNearBoundary=r["regimeNearBoundary"])
        cun_cases.append(c)
    zb_cases = []
    for r in zb["rows"]:
        c = case(r)
        c.update(setting=r["setting"], keyholeDepth_um=r["keyholeDepth_um"],
                 depthReadUncertainty_um=r["depthReadUncertainty_um"])
        zb_cases.append(c)
    zp_cases = []
    for r in zp["rows"]:
        c = case(r)
        c.update(barePlatePores=r["barePlatePores"], powderBedPores=r["powderBedPores"])
        zp_cases.append(c)

    # ---- regime confusion on Cunningham 95 um (Fig. 3A labels) ----
    lab = [c for c in cun_cases if c["regimeReported"]]
    truth = [c["regimeReported"] for c in lab]
    conf = {"appIndex_15_30": confusion(truth, [c["appRegime"] for c in lab], REGIMES3),
            "ganKe_1.4_6": confusion(truth, [c["ganRegime"] for c in lab], REGIMES3)}
    t2 = ["keyhole" if t == "keyhole" else "not-keyhole" for t in truth]
    conf["appIndex_keyholeOnly"] = confusion(t2, ["keyhole" if c["appRegime"] == "keyhole" else "not-keyhole"
                                                  for c in lab], ("keyhole", "not-keyhole"))
    conf["hann_HvHs_12.34"] = confusion(t2, [c["hannRegime"] for c in lab], ("keyhole", "not-keyhole"))
    if run_kernels:
        for k in KERNELS:
            conf[f"kingDW05_{k}"] = confusion(
                t2, ["keyhole" if c["kernels"][k]["kingModeIndicator"] == "keyhole-mode" else "not-keyhole"
                     for c in lab], ("keyhole", "not-keyhole"))
    clear = [c for c in lab if not c["regimeNearBoundary"]]
    conf["appIndex_15_30_excludingNearBoundary"] = confusion(
        [c["regimeReported"] for c in clear], [c["appRegime"] for c in clear], REGIMES3)

    # ---- boundary lines: app index / Ke / Huang along the Cunningham lines ----
    line_rows = []
    for v in LINE_SPEEDS:
        row = {"speed_mm_s": v}
        for name in ("blue-dashed", "red-dashed"):
            P = lines[name]["slope"] * v + lines[name]["intercept"]
            ib = index_block(P, v, 95.0, kl.ASSUMED_PREHEAT_C, props, eta_min)
            row[name] = {"power_W": r3(P), "appIndex_dHhs": ib["appIndex_dHhs"], "ganKe": ib["ganKe"],
                         "huangProduct_betaYe": ib["huangProduct_betaYe"]}
        h_blue = row["blue-dashed"]["appIndex_dHhs"] / row["blue-dashed"]["power_W"]
        row["appPowerAt_dHhs15_W"] = r3(pds.ENTHALPY_TRANSITION / h_blue)
        row["appPowerAt_dHhs30_W"] = r3(pds.ENTHALPY_KEYHOLE / h_blue)
        row["ratio_appKeyholePower_over_redLine"] = r3(row["appPowerAt_dHhs30_W"] / row["red-dashed"]["power_W"])
        row["ratio_appTransitionPower_over_blueLine"] = r3(row["appPowerAt_dHhs15_W"] / row["blue-dashed"]["power_W"])
        line_rows.append(row)

    # ---- Zhao: pores and boundary ----
    def pore_counts(cs):
        n = len(cs)
        return {"n": n,
                "appHigh_dHhs_ge_30": sum(c["appPorosityRiskByIndex"] == "High" for c in cs),
                "appLowModerate_15_30": sum(c["appPorosityRiskByIndex"] == "Low-Moderate" for c in cs),
                "appNegligible_lt_15": sum(c["appPorosityRiskByIndex"] == "Negligible" for c in cs),
                "ganKe_gt_16": sum(c["ganKe"] > kl.GAN_KE_STABLE_MAX for c in cs),
                "ganKe_gt_30": sum(c["ganKe"] > kl.GAN_KE_CHAOTIC_MIN for c in cs),
                "huangBetaYe_gt_5": sum(c["huangProduct_betaYe"] > kl.HUANG_TI64_THRESHOLD -
                                        kl.HUANG_TI64_THRESHOLD_HALFWIDTH for c in cs),
                "huangBetaYe_gt_8": sum(c["huangProduct_betaYe"] > kl.HUANG_TI64_THRESHOLD for c in cs),
                "appIndex": summary([c["appIndex_dHhs"] for c in cs]),
                "ganKe": summary([c["ganKe"] for c in cs]),
                "huangProduct_betaYe": summary([c["huangProduct_betaYe"] for c in cs])}
    pores = {"all": pore_counts(zp_cases),
             "barePlatePores": pore_counts([c for c in zp_cases if c["barePlatePores"]]),
             "powderBedPores": pore_counts([c for c in zp_cases if c["powderBedPores"]])}
    boundary = {}
    for s in ("bare", "powder"):
        cs = sorted([c for c in zb_cases if c["setting"] == s], key=lambda c: c["speed_mm_s"])
        boundary[s] = {"n": len(cs), "appIndex": summary([c["appIndex_dHhs"] for c in cs]),
                       "ganKe": summary([c["ganKe"] for c in cs]),
                       "huangProduct_betaYe": summary([c["huangProduct_betaYe"] for c in cs]),
                       "huangProduct_betaAppFlat": summary([c["huangProduct_betaAppFlat"] for c in cs]),
                       "appIndexAlongBoundary": [[c["speed_mm_s"], c["power_W"], c["appIndex_dHhs"]] for c in cs],
                       "boundaryPointsAppAlreadyHigh": sum(c["appPorosityRiskByIndex"] == "High" for c in cs),
                       "boundaryPointsAppBelow15": sum(c["appIndex_dHhs"] < pds.ENTHALPY_TRANSITION for c in cs)}

    # ---- depth ----
    depth: Dict[str, Any] = {}
    def tol(c, key_unc, sd_key=None):
        return (c.get(key_unc) or 0.0) + ((c.get(sd_key) or 0.0) if sd_key else 0.0)
    for name, cs, meas, unc, sd in (("cunningham95", [c for c in cun_cases if c["beamDiameter_um"] == 95.0],
                                     "vaporDepressionDepth_um", "readUncertainty_um", "depthSd_um"),
                                    ("cunningham140", [c for c in cun_cases if c["beamDiameter_um"] == 140.0],
                                     "vaporDepressionDepth_um", "readUncertainty_um", "depthSd_um"),
                                    ("zhaoBoundaryBare", [c for c in zb_cases if c["setting"] == "bare"],
                                     "keyholeDepth_um", "depthReadUncertainty_um", None),
                                    ("zhaoBoundaryPowder", [c for c in zb_cases if c["setting"] == "powder"],
                                     "keyholeDepth_um", "depthReadUncertainty_um", None)):
        block = {"ganEq2": depth_stats((c["ganKeyholeDepth_um"], c[meas], tol(c, unc, sd)) for c in cs)}
        if run_kernels:
            block["appFabbro"] = depth_stats((c["kernels"]["eagar-tsai"]["fabbroDepth_um"], c[meas], tol(c, unc, sd))
                                             for c in cs)
            for k in KERNELS:
                block[f"appMeltPoolDepth_{k}_vsVaporDepth"] = depth_stats(
                    (c["kernels"][k]["depth_um"], c[meas], tol(c, unc, sd)) for c in cs)
        # Diagnostic only: factor s on the app-property Ke that would put each measured depth on Gan Eq. (2),
        # s = (e/r0 / 0.4 + 1.4) / Ke. A spread around one value means a property-set offset; a trend means more.
        block["ganKeScaleToFitEq2"] = summary(
            [((c[meas] / (c["beamDiameter_um"] / 2.0)) / kl.GAN_ASPECT_SLOPE + kl.GAN_ASPECT_OFFSET) / c["ganKe"]
             for c in cs if c[meas] is not None])
        depth[name] = block

    # ---- Hann self-consistency (printed relation vs printed tables) ----
    hann = kl.load_hann_welds()
    hann_rows = []
    for r in hann["rows"]:
        pred = kl.hann_depth_relation_as_printed(r["dHhsPrinted"])
        hann_rows.append({"rowId": r["rowId"], "dHhsPrinted": r["dHhsPrinted"], "deltaStarPrinted": r["deltaStarPrinted"],
                          "deltaStarFromPrintedRelation": r3(pred),
                          "relErrorPct": r3(100 * (pred - r["deltaStarPrinted"]) / r["deltaStarPrinted"])})
    hann_check = {"rows": hann_rows,
                  "withinClaimed10pct": sum(abs(x["relErrorPct"]) <= 10 for x in hann_rows), "n": len(hann_rows)}

    # ---- automatic findings (numbers only; the narrative is in the .md) ----
    red = [row["red-dashed"]["appIndex_dHhs"] for row in line_rows]
    blue = [row["blue-dashed"]["appIndex_dHhs"] for row in line_rows]
    findings = {
        "appIndexAtCunninghamRedLine": summary(red), "appIndexAtCunninghamBlueLine": summary(blue),
        "appKeyholeThreshold": pds.ENTHALPY_KEYHOLE, "appTransitionThreshold": pds.ENTHALPY_TRANSITION,
        "appIndexAtZhaoBoundary": summary([c["appIndex_dHhs"] for c in zb_cases]),
        "zhaoPoreCasesAppHigh": f"{pores['all']['appHigh_dHhs_ge_30']}/{pores['all']['n']}",
        "keyholeThresholdTooHighForTi64": bool(max(red) < pds.ENTHALPY_KEYHOLE),
        "singleIndexThresholdFitsZhaoBoundary": False if (max(c["appIndex_dHhs"] for c in zb_cases) /
                                                           min(c["appIndex_dHhs"] for c in zb_cases)) > 1.5 else True,
    }
    if run_kernels:
        ix_agree = all(abs(c["kernels"][k]["solverIndex_dHhs"] - c["appIndex_dHhs"]) < 0.05
                       for c in cun_cases + zb_cases + zp_cases for k in KERNELS)
        findings["solverIndexEqualsProcessMapIndex"] = ix_agree
        risk_agree = all(c["kernels"][k]["keyholePorosityRisk"].startswith(c["appPorosityRiskByIndex"])
                         for c in cun_cases + zb_cases + zp_cases for k in KERNELS)
        findings["solverPorosityRiskEqualsIndexBands"] = risk_agree

    from lpbf_simulation import implementation_fingerprint
    doc = {
        "schema": SCHEMA, "generatedAt": GENERATED_AT, "honesty": HONESTY,
        "implementationHash": implementation_fingerprint(),
        "appScreening": {
            "index": "lpbf_public_datasets.classify_regime / lpbf_thermal_solver.classify_enthalpy_regime",
            "rule": pds.REGIME_RULE, "transitionThreshold": pds.ENTHALPY_TRANSITION,
            "keyholeThreshold": pds.ENTHALPY_KEYHOLE,
            "porosityRisk": "lpbf_thermal_solver keyholePorosityRisk: <15 Negligible, 15-30 Low-Moderate, >=30 High",
            "geometricIndicator": "lpbf_defect_diagnostics King D/W > 0.5 kingModeIndicator (label only)",
            "keyholeDepth": "keyholeModel.fabbroDepth_um (Fabbro 2020 eq. 2, flat absorptivity, 15->30 ramp)",
            "kernels": list(KERNELS) if run_kernels else [], "layer_um": LAYER_UM, "hatch_um": HATCH_UM,
            "material": kl.APP_MATERIAL_TI64, "materialProperties": props, "absorptionModel": "flat-plate"},
        "publishedRelationInputs": {
            "ganEtaMin": ye, "ganProperties": "app Ti-6Al-4V properties (Gan's values are SI-only)",
            "huangHm_J_mm3": kl.HUANG_HM_TI64_J_MM3, "huangBeta": {"ye": eta_min, "appFlat": props["absorptivity_IR"]},
            "hannHvHsTi64": kl.HANN_HV_HS_TI64},
        "datasets": {name: {k: v for k, v in fn()["provenance"].items()}
                     for name, fn in kl.LOADERS.items()},
        "relations": kl.load_relations()["rows"],
        "confusion": conf, "cunninghamLines": line_rows, "zhaoPores": pores, "zhaoBoundary": boundary,
        "depth": depth, "hannRelationCheck": hann_check, "findings": findings,
        "notEvaluatedByApp": {
            "gan-keyhole-2021": "Al6061 not in the app material authority",
            "huang-al7a77-2022": "Al7A77 / pure Al not in the app material authority",
            "hann-ss304-2011": "AISI 304 not in the app material authority; welding scale"},
        "cases": {"cunningham": cun_cases, "zhaoBoundary": zb_cases, "zhaoPores": zp_cases},
    }
    return doc


def view(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Read-only summary a scorecard / process-window panel could show (not wired to any UI)."""
    f = doc["findings"]
    c = doc["confusion"]["appIndex_15_30"]
    return {
        "schema": "lpbf-keyhole-benchmark-view-1", "generatedAt": doc["generatedAt"], "readOnly": True,
        "evidenceKind": "Literature comparison (screening only; digitized published measurements)",
        "label": "Keyhole regime screening vs published Ti-6Al-4V x-ray data",
        "honesty": doc["honesty"], "implementationHash": doc["implementationHash"],
        "sources": [{"id": k, "doi": v.get("doi"), "rows": v.get("rows")} for k, v in doc["datasets"].items()],
        "regimeConfusion": {"rule": "app dH/hs 15/30 vs Cunningham 2019 Fig. 3A (95 um, Ti-6Al-4V)",
                            "matrix": c["rowsAreReported_columnsArePredicted"], "accuracy": c["accuracy"], "n": c["n"]},
        "keyholeThreshold": {"app": f["appKeyholeThreshold"],
                             "appIndexAtPublishedKeyholeLine": f["appIndexAtCunninghamRedLine"]},
        "porosity": {"zhaoPoreCasesFlaggedHigh": f["zhaoPoreCasesAppHigh"],
                     "appIndexAlongPublishedPorosityBoundary": f["appIndexAtZhaoBoundary"]},
        "depth": {k: (v.get("appFabbro") or {}).get("mape_pct") for k, v in doc["depth"].items()},
        "physicsBumpProposed": bool(f["keyholeThresholdTooHighForTi64"] or not f["singleIndexThresholdFitsZhaoBoundary"]),
        "evidenceNote": "docs/LPBF_KEYHOLE_THRESHOLD_EVIDENCE_2026-10-07.md",
    }


# ---------------------------------------------------------------------------------------------------------------
# markdown
# ---------------------------------------------------------------------------------------------------------------
def _matrix_md(conf: Dict[str, Any], classes: Sequence[str]) -> List[str]:
    m = conf["rowsAreReported_columnsArePredicted"]
    L = ["| reported \\ predicted | " + " | ".join(classes) + " |", "|---|" + "---|" * len(classes)]
    for t in classes:
        L.append(f"| {t} | " + " | ".join(str(m[t][p]) for p in classes) + " |")
    L.append(f"\nn = {conf['n']}, correct = {conf['correct']}, accuracy = {conf['accuracy']}, recall per reported "
             f"class = {conf['recallPerReportedClass']}.")
    return L


def to_markdown(doc: Dict[str, Any]) -> str:
    f = doc["findings"]
    L = [f"# LPBF keyhole screening vs published x-ray measurements ({doc['generatedAt']})", "",
         f"**{doc['honesty']}**", "",
         f"Schema `{doc['schema']}`; implementation fingerprint `{doc['implementationHash']}`. Generated by "
         "`python/tools/lpbf_keyhole_benchmark.py` from the pinned CSVs of `python/lpbf_keyhole_literature.py`.", "",
         "## Data", "", "| dataset | rows | file | digitized | SI needed |", "|---|---|---|---|---|"]
    for name, p in doc["datasets"].items():
        dig = "yes" if "digitized" in p["file"] else "no (printed values)"
        L.append(f"| {name} (doi:{p['doi']}) | {p['rows']} | `{p['file']}` | {dig} | {p.get('supplementaryNeeded', '')} |")
    L += ["", f"Published relations transcribed: {len(doc['relations'])} (`published_relations.csv`, each with a "
          "locator). Gan's and Huang's Ti-6Al-4V points are Cunningham/Zhao data and were not ingested again.", "",
          "App screening evaluated (unchanged): " + doc["appScreening"]["rule"], "",
          "## Regime confusion: Cunningham 2019 Fig. 3B cases (Ti-6Al-4V, 95 um), labels from the Fig. 3A lines", ""]
    c = doc["confusion"]
    L += ["### App dH/hs 15 / 30 (process-map label)", ""] + _matrix_md(c["appIndex_15_30"], REGIMES3)
    L += ["", "Excluding cases within the read uncertainty of a line:", ""] + \
        _matrix_md(c["appIndex_15_30_excludingNearBoundary"], REGIMES3)
    L += ["", "### Gan 2021 keyhole number (Ke < 1.4 / 1.4-6 / > 6), app properties, eta from Eq. 6 with Ye 2019 Am", ""] + \
        _matrix_md(c["ganKe_1.4_6"], REGIMES3)
    L += ["", "### Keyhole vs not-keyhole", "", "| rule | n | correct | accuracy | keyhole recall | not-keyhole recall |",
          "|---|---|---|---|---|---|"]
    for k in [k for k in c if k.startswith(("appIndex_keyholeOnly", "hann", "kingDW05"))]:
        x = c[k]
        L.append(f"| {k} | {x['n']} | {x['correct']} | {x['accuracy']} | {x['recallPerReportedClass']['keyhole']} | "
                 f"{x['recallPerReportedClass']['not-keyhole']} |")
    L += ["", "## Published transition lines vs the app thresholds (95 um, Ti-6Al-4V, 20 C)", "",
          "| v mm/s | blue P W | app dH/hs at blue | red P W | app dH/hs at red | Gan Ke at red | app P at dH/hs=30 | "
          "app P30 / red P |", "|---|---|---|---|---|---|---|---|"]
    for r in doc["cunninghamLines"]:
        L.append(f"| {r['speed_mm_s']} | {r['blue-dashed']['power_W']} | {r['blue-dashed']['appIndex_dHhs']} | "
                 f"{r['red-dashed']['power_W']} | {r['red-dashed']['appIndex_dHhs']} | {r['red-dashed']['ganKe']} | "
                 f"{r['appPowerAt_dHhs30_W']} | {r['ratio_appKeyholePower_over_redLine']} |")
    L += ["", f"App index at the red (keyhole-domain) line: {f['appIndexAtCunninghamRedLine']}; app keyhole "
          f"threshold {f['appKeyholeThreshold']}. At the blue (conduction-limit) line: {f['appIndexAtCunninghamBlueLine']}; "
          f"app transition threshold {f['appTransitionThreshold']}.", "",
          "## Keyhole porosity: Zhao 2020 (Ti-6Al-4V, ~100 um)", "",
          "| subset | n | app High (>=30) | app 15-30 | app <15 | Gan Ke>16 | Gan Ke>30 | Huang(beta=Am)>5 | >8 |",
          "|---|---|---|---|---|---|---|---|---|"]
    for k, x in doc["zhaoPores"].items():
        L.append(f"| pores observed: {k} | {x['n']} | {x['appHigh_dHhs_ge_30']} | {x['appLowModerate_15_30']} | "
                 f"{x['appNegligible_lt_15']} | {x['ganKe_gt_16']} | {x['ganKe_gt_30']} | {x['huangBetaYe_gt_5']} | "
                 f"{x['huangBetaYe_gt_8']} |")
    L += ["", "Index values ON the published porosity boundary (a single threshold of any index would be constant here):",
          "", "| setting | n | app dH/hs min/median/max | Gan Ke min/median/max | Huang (beta=Am) min/median/max | "
          "boundary points app already calls High |", "|---|---|---|---|---|---|"]
    for s, x in doc["zhaoBoundary"].items():
        fmt = lambda d: f"{d['min']} / {d['median']} / {d['max']}"
        L.append(f"| {s} | {x['n']} | {fmt(x['appIndex'])} | {fmt(x['ganKe'])} | {fmt(x['huangProduct_betaYe'])} | "
                 f"{x['boundaryPointsAppAlreadyHigh']} |")
    L += ["", "## Depth", "", "Measured quantity is the vapor-depression (keyhole) depth. The app melt-pool depth is "
          "listed only as a consistency check (a melt pool must contain the vapor depression).", "",
          "| set | predictor | n | bias um | MAE um | MAPE % | median pred/meas | within tolerance | underpredicted |",
          "|---|---|---|---|---|---|---|---|---|"]
    for s, block in doc["depth"].items():
        for k, x in block.items():
            if x and k != "ganKeScaleToFitEq2":
                L.append(f"| {s} | {k} | {x['n']} | {x['bias_um']} | {x['mae_um']} | {x['mape_pct']} | "
                         f"{x['medianRatioPredOverMeas']} | {x['withinTolerance']} | {x['underpredicted']} |")
    L += ["", "Gan Eq. (2) with app properties: factor on Ke that would put each measured depth on the published line "
          "(diagnostic of the property-set offset; Gan's own property values are SI-only):", ""]
    for s, block in doc["depth"].items():
        L.append(f"- {s}: {block['ganKeScaleToFitEq2']}")
    h = doc["hannRelationCheck"]
    L += ["", "## Hann 2011 depth relation, as printed, vs Hann's own Tables 3-4", "",
          f"{h['withinClaimed10pct']} of {h['n']} printed (dH/hs, delta*) pairs are within the claimed +/-10% of the "
          "printed piecewise relation; the printed form cannot be the curve the tables follow (likely a typesetting "
          "error). It is recorded, not used for a verdict.", "",
          "| case | dH/hs | delta* printed | delta* from printed relation | error % |", "|---|---|---|---|---|"]
    for r in h["rows"]:
        L.append(f"| {r['rowId']} | {r['dHhsPrinted']} | {r['deltaStarPrinted']} | {r['deltaStarFromPrintedRelation']} | "
                 f"{r['relErrorPct']} |")
    L += ["", "## Findings (computed)", "", "```json", json.dumps(f, indent=2, sort_keys=True), "```", "",
          "Narrative, limits and the proposed planned physics bump: `docs/LPBF_KEYHOLE_THRESHOLD_EVIDENCE_2026-10-07.md`.",
          ""]
    return "\n".join(L)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--no-kernels", action="store_true", help="index-only (no solver calls)")
    a = ap.parse_args(argv)
    text = json.dumps(evaluate(run_kernels=not a.no_kernels), indent=1, sort_keys=True) + "\n"
    doc = json.loads(text)  # .md and .view.json are rendered from the committed (key-sorted) JSON
    out = Path(a.out)
    out.write_text(text, encoding="utf-8", newline="\n")
    out.with_suffix(".md").write_text(to_markdown(doc), encoding="utf-8", newline="\n")
    out.with_name(out.stem + ".view.json").write_text(json.dumps(view(doc), indent=1, sort_keys=True) + "\n",
                                                      encoding="utf-8", newline="\n")
    print(json.dumps(doc["findings"], indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
