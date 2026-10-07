"""Empirical depth / width error bands of the frozen LPBF melt-pool screening kernels, measured on published single
tracks (REPORTING ONLY; SCREENING ONLY; NOT VALIDATION).

What this module is: the pre-declared statistics (``build_cells``), the loader that refuses a stale or tampered
artefact (``load_bands``), the lookup (``band_for``) and the one wording of the display sentence (``band_sentence``)
that every surface reuses through the committed JSON. Method pre-declared before the first run in
``PREDECLARED_depth_bands_machinecal.md`` (section A): relative error r = pred / meas - 1; equal source weight;
eligibility (>= 2 sources, >= 10 rows, >= 3 rows per source); leave-one-source-out (LOSO) coverage of the 10-90 %
band; coverage floor 0.70 (nominal 0.80).

What it is not: it reads no solver and edits no physics. It is NOT part of
``lpbf_simulation.IMPLEMENTATION_SOURCE_FILES`` and no frozen file may import it (test_lpbf_calibration_frozen.py
scans for that). No code path reads a band to change a label, a verdict or a gate; the evidence kind of every
result stays ``screening-only`` and ``experimentalValidation`` stays false.

Honest reading: the per-source medians are the finding. The between-source offset is as large as the band
half-width, so a band built from some published sources does not predict the error on another lab's machine
(measured LOSO coverage). The display therefore always prints n, the sources, the per-source medians and the
measured held-out coverage, and never a bare "+/- x %".
"""

from __future__ import annotations

import collections
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

BANDS_SCHEMA = "lpbf-meltpool-error-bands-1"
SUMMARY_SCHEMA = "lpbf-meltpool-error-bands-summary-1"
ROWS_SCHEMA = "lpbf-meltpool-error-bands-rows-1"
ARTEFACT_REL_PATH = "data/calibration/lpbf-meltpool-error-bands-v1.json"
SUMMARY_REL_PATH = "data/calibration/lpbf-meltpool-error-bands-v1.summary.json"
ROWS_REL_PATH = "data/calibration/lpbf-meltpool-error-bands-v1.rows.json"
DEFAULT_PATH = Path(__file__).resolve().parent.parent / ARTEFACT_REL_PATH

KERNELS = ("eagar-tsai", "goldak", "rosenthal")
QUANTITIES = ("depth", "width")
STATES = ("band", "band-under-covers", "insufficient-data")
EVIDENCE_KIND = "screening-only"
EVIDENCE_LABEL = "Screening only"
# Maintainer-approved wording (2026-10-07) of the label line printed after every band sentence.
LABEL_LINE = "Screening only · typical published-data error shown; transfer to another lab not established"
HONESTY = ("typical error of the frozen screening kernels on published single tracks, per kernel, alloy family and "
           "screening regime class; reporting text only: it is not a tolerance, not a prediction interval for any "
           "other machine and not experimental validation; the leave-one-source-out coverage is reported next to "
           "every band and shows that a band built from some published sources does not transfer to another; "
           "no per-row measurement uncertainty exists in any source; digitized figures (Trapp, Ghosh) and a "
           "development sentinel (NIST AMB2022-03 IN718) are flagged; experimentalValidation=false")

BANDS_CONFIG: Dict[str, Any] = {
    "version": "lpbf-meltpool-error-bands-config-1",
    "kernels": list(KERNELS),
    "thresholds": [15.0, 30.0],
    "thresholdBasis": "input-only normalised enthalpy at the material default absorptivity; < 15 conduction, < 30 "
                      "transition, else keyhole (the app's screening class, not the papers' regime definition)",
    "quantiles": [0.1, 0.5, 0.9],
    "relativeError": "pred / meas - 1 (positive = the model over-predicts)",
    "sourceWeight": "equal",
    "minSources": 2,
    "minRows": 10,
    "minRowsPerSource": 3,
    "coverageFloor": 0.70,
    "nominalCoverage": 0.80,
    "notInformativeRatio": 2.5,
    "widening": "naive 10/90 +/- z80 * SD of per-source medians (z80 = 1.2816); a 2-source cell takes the SD from the "
                "full cell (optimistic, flagged sdLeak)",
    "z80": 1.2816,
    "families": {"316L Stainless Steel": "316L", "Ti-6Al-4V": "Ti64", "Inconel 625": "Ni", "Inconel 718": "Ni"},
    "sourceNames": {
        "hofmann-316l-2026": "Hofmann", "ku-leuven-316l-2021": "KU Leuven", "ku-leuven-ti64-2021": "KU Leuven",
        "trapp-316l-2017": "Trapp", "totis-ti64-2021": "Totis", "ghosh-in625-2018": "Ghosh",
        "lane-in625-2020": "Lane", "nist-amb2022-03": "NIST AMB2022-03"},
    "sourceRoles": {
        "hofmann-316l-2026": "trainable", "ku-leuven-316l-2021": "trainable", "ku-leuven-ti64-2021": "trainable",
        "totis-ti64-2021": "trainable", "lane-in625-2020": "trainable",
        "trapp-316l-2017": "test-only", "ghosh-in625-2018": "test-only", "nist-amb2022-03": "catalog-sentinel"},
    "digitizedSources": ["trapp-316l-2017", "ghosh-in625-2018"],
    "sentinelSources": ["nist-amb2022-03"],
    "rowsUsed": "extentStatus == computed and measured value finite and > 0; balling-flagged rows stay in their "
                "enthalpy class; vapour-depression depths (keyhole benchmark) are a different quantity and are never pooled",
    "rounding": {"significantDigits": 6},
}
FAMILIES = BANDS_CONFIG["families"]
ARTEFACT_KEYS = frozenset({
    "schema", "bandsId", "generatedAt", "implementationHash", "codeRevision", "toolSha256", "configSha256", "config",
    "sources", "rowsSha256", "rowCount", "excluded", "cells", "evidenceKind", "evidenceLabel", "experimentalValidation",
    "labelPromotionProposed", "honesty", "whatThisDoesNotShow", "contentSha256"})


class BandsError(Exception):
    """The artefact is malformed, tampered with or inconsistent with the compiled-in configuration."""


class BandsStale(BandsError):
    """The artefact was measured against a different frozen-physics fingerprint."""


# ---------------------------------------------------------------------------------------------
# hashing
# ---------------------------------------------------------------------------------------------
def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def canonical_sha256(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def config_sha256(config: Dict[str, Any] = BANDS_CONFIG) -> str:
    return canonical_sha256(config)


def artefact_content_sha256(art: Dict[str, Any]) -> str:
    probe = dict(art)
    probe["contentSha256"] = ""
    probe["bandsId"] = ""
    return canonical_sha256(probe)


def round_sig(x: Any, digits: int = 6) -> Any:
    """Round every float in a nested structure to ``digits`` significant digits (ints, strings, bools untouched)."""
    if isinstance(x, bool) or x is None or isinstance(x, (int, str)):
        return x
    if isinstance(x, float):
        if x == 0.0 or not math.isfinite(x):
            return x
        return float(f"{x:.{digits - 1}e}")
    if isinstance(x, dict):
        return {k: round_sig(v, digits) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [round_sig(v, digits) for v in x]
    return x


# ---------------------------------------------------------------------------------------------
# statistics (pre-declared; same arithmetic as the exploratory bands_eval.py)
# ---------------------------------------------------------------------------------------------
def regime_class(enthalpy: float) -> str:
    lo, hi = BANDS_CONFIG["thresholds"]
    return "conduction" if enthalpy < lo else ("transition" if enthalpy < hi else "keyhole")


def wquant(vals: Sequence[float], weights: Sequence[float], q: float) -> float:
    """Weighted quantile by cumulative weight: the first value whose cumulative weight reaches q * total."""
    pairs = sorted(zip(vals, weights))
    total = sum(weights)
    cum = 0.0
    for v, w in pairs:
        cum += w
        if cum >= q * total - 1e-12:
            return v
    return pairs[-1][0]


def band_stats(cell_rows: Sequence[Dict[str, Any]]) -> Dict[str, float]:
    """Equal-source-weight median and 10/90 % of the relative error (each row weighted 1 / rows of its source)."""
    per_src = collections.Counter(r["src"] for r in cell_rows)
    w = [1.0 / per_src[r["src"]] for r in cell_rows]
    v = [r["r"] for r in cell_rows]
    ones = [1.0] * len(v)
    return {"median": wquant(v, w, 0.5), "p10": wquant(v, w, 0.1), "p90": wquant(v, w, 0.9),
            "pooledMedian": wquant(v, ones, 0.5), "pooledP10": wquant(v, ones, 0.1),
            "pooledP90": wquant(v, ones, 0.9)}


def _sd(values: Sequence[float]) -> float:
    mu = sum(values) / len(values)
    return math.sqrt(sum((x - mu) ** 2 for x in values) / max(1, len(values) - 1))


def _informative(p10: float, p90: float) -> bool:
    lo, hi = 1.0 + p10, 1.0 + p90
    return lo > 0.0 and (hi / lo) <= BANDS_CONFIG["notInformativeRatio"]


def _cell(quantity: str, kernel: str, family: str, regime: str, cr: List[Dict[str, Any]]) -> Dict[str, Any]:
    cfg = BANDS_CONFIG
    sources = sorted({x["src"] for x in cr})
    per_src = collections.Counter(x["src"] for x in cr)
    digit = [s for s in sources if s in cfg["digitizedSources"]]
    sentinel_only = all(s in cfg["sentinelSources"] for s in sources)
    eligible = (len(sources) >= cfg["minSources"] and len(cr) >= cfg["minRows"]
                and min(per_src.values()) >= cfg["minRowsPerSource"])
    b = band_stats(cr)
    src_median = {s: wquant([x["r"] for x in cr if x["src"] == s], [1.0] * per_src[s], 0.5) for s in sources}
    cell: Dict[str, Any] = {
        "quantity": quantity, "kernel": kernel, "family": family, "regime": regime,
        "alloys": sorted({x["alloy"] for x in cr}), "n": len(cr),
        "nSets": len({(x["src"],) + x["set"] for x in cr}), "nSources": len(sources), "sources": sources,
        "rowsPerSource": dict(sorted(per_src.items())), "nBalling": sum(1 for x in cr if x["balling"]),
        "sentinelOnly": sentinel_only, "digitizedSources": digit, "eligible": eligible,
        "median": b["median"], "p10": b["p10"], "p90": b["p90"], "pooledP10": b["pooledP10"],
        "pooledP90": b["pooledP90"], "pooledMedian": b["pooledMedian"], "sourceMedian": src_median,
        "envelope": {
            "laserPower_W": [min(x["set"][0] for x in cr), max(x["set"][0] for x in cr)],
            "scanSpeed_mm_s": [min(x["set"][1] for x in cr), max(x["set"][1] for x in cr)],
            "beamDiameter_um": [min(x["set"][2] for x in cr), max(x["set"][2] for x in cr)]},
        "sourceMedianSd": None, "loso": None, "widened": None}
    if not eligible:
        cell["state"] = "insufficient-data"
        return cell
    cov: Dict[str, float] = {}
    loso_bands: Dict[str, Dict[str, float]] = {}
    for s in sources:
        train = [x for x in cr if x["src"] != s]
        test = [x for x in cr if x["src"] == s]
        tb = band_stats(train)
        cov[s] = sum(tb["p10"] <= x["r"] <= tb["p90"] for x in test) / len(test)
        loso_bands[s] = {"p10": tb["p10"], "p90": tb["p90"]}
    cov_eq = sum(cov.values()) / len(cov)
    cov_pooled = sum(cov[s] * per_src[s] for s in sources) / len(cr)
    sd = _sd(list(src_median.values()))
    z = cfg["z80"]
    w_lo, w_hi = b["p10"] - z * sd, b["p90"] + z * sd
    covw: Dict[str, float] = {}
    for s in sources:
        train = [x for x in cr if x["src"] != s]
        tb = band_stats(train)
        meds_t = [src_median[t] for t in sources if t != s]
        sd_t = _sd(meds_t) if len(meds_t) >= 2 else sd
        lo, hi = tb["p10"] - z * sd_t, tb["p90"] + z * sd_t
        test = [x for x in cr if x["src"] == s]
        covw[s] = sum(lo <= x["r"] <= hi for x in test) / len(test)
    cell["sourceMedianSd"] = sd
    cell["loso"] = {"coverageBySource": cov, "coverageEqualWeight": cov_eq, "coveragePooled": cov_pooled,
                    "bands": loso_bands}
    cell["widened"] = {"p10": w_lo, "p90": w_hi, "coverageEqualWeight": sum(covw.values()) / len(covw),
                       "informative": _informative(w_lo, w_hi), "sdLeak": len(sources) == 2}
    cell["state"] = "band" if cov_eq >= cfg["coverageFloor"] else "band-under-covers"
    return cell


def build_cells(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Cells for every quantity x kernel x (alloy family | Ni alloy) x regime class (+ 'all') from solved rows.

    A row is ``{"source", "rowId", "material", "power_W", "speed_mm_s", "beamDiameter_um", "width_um", "depth_um",
    "balling", "enthalpy", "pred": {kernel: {"W", "D", "status"}}}``. Returns ``{"cells": [...], "excluded": {...}}``.
    """
    excluded: collections.Counter = collections.Counter()
    cells: List[Dict[str, Any]] = []
    for quantity in QUANTITIES:
        key_meas = "depth_um" if quantity == "depth" else "width_um"
        key_pred = "D" if quantity == "depth" else "W"
        for kernel in KERNELS:
            groups: Dict[Any, List[Dict[str, Any]]] = collections.defaultdict(list)
            for r in rows:
                p = (r.get("pred") or {}).get(kernel) or {}
                m = r.get(key_meas)
                if p.get("status") != "computed" or not p.get(key_pred) or m is None or not m > 0 \
                        or r.get("enthalpy") is None:
                    excluded[f"{quantity}|{kernel}"] += 1
                    continue
                rec = {"src": r["source"], "r": p[key_pred] / m - 1.0,
                       "set": (r["power_W"], r["speed_mm_s"], r["beamDiameter_um"]),
                       "balling": r.get("balling") == 1, "alloy": r["material"]}
                family = FAMILIES[r["material"]]
                cls = regime_class(r["enthalpy"])
                groups[(family, cls)].append(rec)
                groups[(family, "all")].append(rec)
                if family == "Ni":  # per-alloy view of the Ni family, so the pooling can be judged
                    groups[(r["material"], cls)].append(rec)
            for (family, regime), cr in sorted(groups.items()):
                cells.append(_cell(quantity, kernel, family, regime, cr))
    return {"cells": round_sig(cells, BANDS_CONFIG["rounding"]["significantDigits"]),
            "excluded": dict(sorted(excluded.items()))}


# ---------------------------------------------------------------------------------------------
# loader and lookup
# ---------------------------------------------------------------------------------------------
def load_bands(path: Any = DEFAULT_PATH, *, expected_impl_hash: Optional[str] = None) -> Dict[str, Any]:
    """Load and verify the artefact. ``expected_impl_hash`` defaults to the live implementation fingerprint."""
    p = Path(path)
    try:
        art = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BandsError(f"error-band artefact missing: {p}") from exc
    except json.JSONDecodeError as exc:
        raise BandsError(f"error-band artefact is not valid JSON: {exc}") from exc
    if not isinstance(art, dict) or art.get("schema") != BANDS_SCHEMA:
        raise BandsError(f"unexpected schema {art.get('schema') if isinstance(art, dict) else type(art).__name__}")
    unknown = sorted(set(art) - ARTEFACT_KEYS)
    if unknown:
        raise BandsError(f"unknown artefact keys rejected: {unknown}")
    if art.get("contentSha256") != artefact_content_sha256(art):
        raise BandsError("contentSha256 does not match the artefact content (tampered or hand-edited)")
    if canonical_sha256(art.get("config")) != art.get("configSha256"):
        raise BandsError("configSha256 does not match the config stored in the artefact")
    if art.get("configSha256") != config_sha256(BANDS_CONFIG):
        raise BandsError("BANDS_CONFIG sha256 differs from the artefact's: a config change needs a new bands version")
    if (art.get("evidenceKind") != EVIDENCE_KIND or art.get("labelPromotionProposed") != "none"
            or art.get("experimentalValidation") is not False):
        raise BandsError("artefact evidence fields must be screening-only, no promotion, experimentalValidation false")
    for c in art.get("cells", []):
        if c.get("state") not in STATES:
            raise BandsError(f"unknown cell state {c.get('state')!r}")
    live = expected_impl_hash
    if live is None:
        from lpbf_simulation import implementation_fingerprint
        live = implementation_fingerprint()
    if art.get("implementationHash") != live:
        raise BandsStale("error bands stale for this physics version "
                         f"(artefact {str(art.get('implementationHash'))[:12]}, live {str(live)[:12]})")
    return art


def load_bands_or_reason(path: Any = DEFAULT_PATH, *, expected_impl_hash: Optional[str] = None) -> Dict[str, Any]:
    """A missing, tampered or stale artefact never fails a request: the caller gets ``{"available": False, ...}``."""
    try:
        art = load_bands(path, expected_impl_hash=expected_impl_hash)
    except BandsStale as exc:
        return {"available": False, "reason": str(exc), "stale": True}
    except BandsError as exc:
        return {"available": False, "reason": str(exc), "stale": False}
    return {"available": True, "bands": art, "bandsId": art["bandsId"], "contentSha256": art["contentSha256"]}


def band_for(bands: Dict[str, Any], kernel: str, material: str, regime_cls: str, quantity: str) -> Optional[Dict[str, Any]]:
    """The alloy-family cell for (kernel, alloy, screening regime class of the input, quantity), or None."""
    family = FAMILIES.get(material)
    if family is None:
        return None
    for c in bands.get("cells", []):
        if (c["kernel"] == kernel and c["family"] == family and c["regime"] == regime_cls
                and c["quantity"] == quantity):
            return c
    return None


# ---------------------------------------------------------------------------------------------
# the one wording (ported to src/data/lpbfErrorBands.ts; tests/fixtures/lpbf-error-band-sentences.json is the shared golden)
# ---------------------------------------------------------------------------------------------
def _round_half_up(x: float) -> int:
    return int(math.floor(abs(x) + 0.5)) * (1 if x >= 0 else -1)


def _signed(n: int) -> str:
    return f"+{n}" if n > 0 else (f"−{-n}" if n < 0 else "0")


def fmt_pct(rel: float) -> str:
    """Relative error (fraction) as a signed whole percent with a true minus sign."""
    return _signed(_round_half_up(rel * 100.0))


def fmt_cov(cov: float) -> str:
    return str(_round_half_up(cov * 100.0))


def source_label(source: str, cell: Dict[str, Any]) -> str:
    name = BANDS_CONFIG["sourceNames"].get(source, source)
    if source in cell.get("digitizedSources", []):
        name += " (digitized)"
    if source in BANDS_CONFIG["sentinelSources"]:
        name += " (catalog sentinel)"
    return name


def _per_source(cell: Dict[str, Any]) -> str:
    return ", ".join(f"{source_label(s, cell)} {fmt_pct(cell['sourceMedian'][s])} %" for s in cell["sources"])


def outside_envelope(cell: Dict[str, Any], inputs: Optional[Dict[str, Any]]) -> bool:
    if not inputs or not cell.get("envelope"):
        return False
    for key in ("laserPower_W", "scanSpeed_mm_s", "beamDiameter_um"):
        v = inputs.get(key)
        lo, hi = cell["envelope"][key]
        if isinstance(v, (int, float)) and math.isfinite(v) and not (lo <= v <= hi):
            return True
    return False


def band_sentence(cell: Optional[Dict[str, Any]], value_um: float, quantity: str,
                  inputs: Optional[Dict[str, Any]] = None, *, material: Optional[str] = None) -> str:
    """The display sentence of the three states (band / band-under-covers / insufficient-data). Never a bare +/- x %."""
    q = quantity
    head = f"{q} ≈ {_round_half_up(value_um)} µm"
    cfg = BANDS_CONFIG
    nominal = fmt_cov(cfg["nominalCoverage"])
    if cell is None or cell["state"] == "insufficient-data":
        n = 0 if cell is None else cell["n"]
        k = 0 if cell is None else cell["nSources"]
        detail = f"published-track error: insufficient data ({k} source{'' if k == 1 else 's'}, {n} rows"
        if cell is not None and cell["sources"]:
            detail += ": " + _per_source(cell) + " median"
        detail += ")"
        body = detail
    else:
        n, k = cell["n"], cell["nSources"]
        lo, hi, med = fmt_pct(cell["p10"]), fmt_pct(cell["p90"]), fmt_pct(cell["median"])
        cov = fmt_cov(cell["loso"]["coverageEqualWeight"])
        nb = f"{n} rows, {k} sources"
        if cell["state"] == "band":
            body = (f"typical error on published tracks, 10–90 % range {lo} / {hi} % (median {med} %; {nb}; "
                    f"per-source median error {_per_source(cell)}; a held-out source fell inside the band {cov} % "
                    f"of the time, nominal {nominal} %)")
        else:
            w = cell["widened"]
            wide = (f"Widened by the between-source spread: {fmt_pct(w['p10'])} / {fmt_pct(w['p90'])} %."
                    if w and w["informative"] else "No informative bound from published data.")
            body = (f"published-track error 10–90 % range {lo} / {hi} % (median {med} %; {nb}) — this band does "
                    f"NOT transfer between sources: a held-out source fell inside only {cov} % of the time (nominal "
                    f"{nominal} %); per-source median error {_per_source(cell)}. {wide} Only measurements on your own "
                    f"machine can bound this.")
    if cell is not None and material and cell["alloys"] and cell["alloys"] != [material]:
        body += f" Pooled alloys in this cell: {', '.join(cell['alloys'])}."
    out = f"{head} · {body}"
    if cell is not None and outside_envelope(cell, inputs):
        out += " · input outside the published range of this cell"
    return f"{out} · {LABEL_LINE}"


def band_short(cell: Optional[Dict[str, Any]], quantity: str) -> str:
    """Tile-sized form; the full sentence is the tooltip and the visible detail."""
    tag = "D" if quantity == "depth" else "W"
    if cell is None or cell["state"] == "insufficient-data":
        n = 0 if cell is None else cell["n"]
        k = 0 if cell is None else cell["nSources"]
        return f"{tag} err. n/a ({k} src, {n} rows)"
    cov = fmt_cov(cell["loso"]["coverageEqualWeight"])
    return f"{tag} err. {fmt_pct(cell['p10'])}/{fmt_pct(cell['p90'])} % (cov {cov} %)"


def summary_of(art: Dict[str, Any]) -> Dict[str, Any]:
    """What the frontend imports: the artefact without row-level LOSO bands, plus the wording constants."""
    cells = []
    for c in art["cells"]:
        cc = dict(c)
        if cc.get("loso"):
            cc["loso"] = {k: v for k, v in cc["loso"].items() if k != "bands"}
        cells.append(cc)
    return {"schema": SUMMARY_SCHEMA, "bandsId": art["bandsId"], "contentSha256": art["contentSha256"],
            "implementationHash": art["implementationHash"], "generatedAt": art["generatedAt"],
            "evidenceKind": art["evidenceKind"], "evidenceLabel": art["evidenceLabel"],
            "experimentalValidation": art["experimentalValidation"],
            "labelPromotionProposed": art["labelPromotionProposed"], "labelLine": LABEL_LINE,
            "config": {k: art["config"][k] for k in ("thresholds", "coverageFloor", "nominalCoverage",
                                                    "notInformativeRatio", "families", "sourceNames",
                                                    "digitizedSources", "sentinelSources")},
            "sources": art["sources"], "cells": cells, "honesty": art["honesty"]}
