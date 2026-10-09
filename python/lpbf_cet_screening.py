#!/usr/bin/env python3
"""
Columnar-to-equiaxed transition (CET) screening criterion, Gäumann form of Hunt 1984 (stdlib only).

Screening only, not validation. The module ships the equation and an honest constants registry. No CET constants
(a, n, N0) for IN718 or IN625 have been read from a primary source, so for both alloys the registry status is
"unavailable" and no band is ever computed from invented numbers. Synthetic constants may be passed to
`critical_gradient_K_m`, `cet_band` and `cet_block(constants_override=...)` by tests only.

Equation (E3), nucleation undercooling neglected:

    G^n / V = a * [ (1 / (n + 1)) * (-4 pi N0 / (3 ln(1 - phi)))^(1/3) ]^n

so the boundary is

    G_crit(V, phi) = (a V)^(1/n) / (n + 1) * (-4 pi N0 / (3 ln(1 - phi)))^(1/3).

phi_columnar = 0.0066 and phi_equiaxed = 0.49 are Hunt's equiaxed-fraction thresholds (H84). G >= G_crit(V, 0.0066)
is "columnar", G <= G_crit(V, 0.49) is "equiaxed", anything between is "mixed". V is the local growth rate R.

Sources
  GA01  M. Gäumann, C. Bezençon, P. Canalis, W. Kurz, Acta Mater. 49 (2001) 1051-1062,
        DOI 10.1016/S1359-6454(00)00367-0. The DOI was confirmed against a Crossref-cited record. The paper was NOT
        read for this design: EQUATION_VERIFIED is False and the equation number (locator) is unset until the
        maintainer reads the PDF.
  H84   J. D. Hunt, Mater. Sci. Eng. 65 (1984) 75-83, DOI 10.1016/0025-5416(84)90201-5.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional, Tuple

MODEL_ID = "gaumann2001-hunt1984-cet-screening-v1"
PHI_COLUMNAR = 0.0066
PHI_EQUIAXED = 0.49

SOURCES: Dict[str, Dict[str, str]] = {
    "GA01": {
        "citation": "M. Gäumann, C. Bezençon, P. Canalis, W. Kurz, Acta Mater. 49 (2001) 1051-1062 "
                    "(single-crystal laser deposition of CMSX-4; CET model)",
        "doi": "10.1016/S1359-6454(00)00367-0",
    },
    "H84": {
        "citation": "J. D. Hunt, Mater. Sci. Eng. 65 (1984) 75-83 (steady-state columnar and equiaxed growth of dendrites "
                    "and eutectic)",
        "doi": "10.1016/0025-5416(84)90201-5",
    },
}

EQUATION = "G^n/V = a*[(1/(n+1))*(-4*pi*N0/(3*ln(1-phi)))^(1/3)]^n"
EQUATION_VERIFIED = False  # form not checked against the GA01 PDF in this lane
EQUATION_LOCATOR: Optional[str] = None  # equation number in GA01, to be filled by the maintainer after reading the PDF

CRITERION_NOTE = (
    "Nucleation undercooling dTn is neglected in this form. The model is single-component-like: multicomponent "
    "solutal effects are not in the equation. N0 (nucleant density) depends on the process and powder and is not "
    "a material constant. Screening only; not a grain-structure prediction."
)


def _c(value: Optional[float], unit: str, source: Optional[str], locator: Optional[str], *, verified: bool) -> Dict[str, Any]:
    return {"value": value, "unit": unit, "source": source, "locator": locator, "verified": verified}


UNVERIFIED_ENTRY = "not read from a primary source"

CET_CONSTANTS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "in718": {
        "a": _c(None, "K^n s/m", None, UNVERIFIED_ENTRY, verified=False),
        "n": _c(None, "-", None, UNVERIFIED_ENTRY, verified=False),
        "N0": _c(None, "m^-3", None, UNVERIFIED_ENTRY, verified=False),
    },
    "in625": {
        "a": _c(None, "K^n s/m", None, UNVERIFIED_ENTRY, verified=False),
        "n": _c(None, "-", None, UNVERIFIED_ENTRY, verified=False),
        "N0": _c(None, "m^-3", None, UNVERIFIED_ENTRY, verified=False),
    },
}

CANDIDATE_SOURCES: Dict[str, List[Dict[str, Any]]] = {
    "in718": [
        {"citation": "M. Haines, A. Plotkowski, C.L. Frederick, E.J. Schwalbach, S.S. Babu, Comput. Mater. Sci. (2018), "
                     "CET sensitivity analysis for Ni superalloys in EBM", "osti": "1474534", "read": False},
        {"citation": "N. Raghavan et al., Acta Mater. (2016), IN718 EBM grain morphology", "osti": "1252143", "read": False},
    ],
    "in625": [],
}

UNAVAILABLE_REASONS: Dict[str, str] = {
    "in718": ("No CET constants (a, n, N0) for IN718 have been read from a primary source; Gäumann 2001 gives constants "
              "for CMSX-4 only. Candidate sources (EBM IN718, not read) are listed; their N0 is process-specific."),
    "in625": "No published CET constants for IN625 are known to this module.",
}
UNKNOWN_ALLOY_REASON = "No CET constants registry entry for this alloy."


def cet_constants(alloy_id: str) -> Dict[str, Any]:
    """{"status": "available"|"unavailable", "reason", "entries", "candidateSources"}.

    Available only when a, n, N0 are all verified with a value, a source and a locator."""
    entries = CET_CONSTANTS.get(alloy_id)
    candidates = [dict(c) for c in CANDIDATE_SOURCES.get(alloy_id, [])]
    if entries is None:
        return {"status": "unavailable", "reason": UNKNOWN_ALLOY_REASON, "entries": {}, "candidateSources": candidates}
    complete = all(
        entries.get(k) is not None
        and entries[k].get("verified") is True
        and entries[k].get("value") is not None
        and entries[k].get("source")
        and entries[k].get("locator")
        for k in ("a", "n", "N0")
    )
    copied = {k: dict(v) for k, v in entries.items()}
    if complete:
        return {"status": "available", "reason": None, "entries": copied, "candidateSources": candidates}
    return {"status": "unavailable", "reason": UNAVAILABLE_REASONS.get(alloy_id, UNKNOWN_ALLOY_REASON),
            "entries": copied, "candidateSources": candidates}


def critical_gradient_K_m(v_m_s: float, phi: float, *, a: float, n: float, n0_m3: float) -> float:
    """E3 solved for G. ValueError on v <= 0, n <= 0, a <= 0, n0 <= 0, phi not in (0, 1)."""
    for name, value in (("v_m_s", v_m_s), ("a", a), ("n", n), ("n0_m3", n0_m3), ("phi", phi)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{name} must be a finite number")
    if not v_m_s > 0:
        raise ValueError("v_m_s must be > 0")
    if not n > 0:
        raise ValueError("n must be > 0")
    if not a > 0:
        raise ValueError("a must be > 0")
    if not n0_m3 > 0:
        raise ValueError("n0_m3 must be > 0")
    if not 0.0 < phi < 1.0:
        raise ValueError("phi must lie in (0, 1)")
    nucleus = (-4.0 * math.pi * n0_m3 / (3.0 * math.log(1.0 - phi))) ** (1.0 / 3.0)
    return (a * v_m_s) ** (1.0 / n) / (n + 1.0) * nucleus


def cet_band(g_K_m: float, v_m_s: float, constants: Mapping[str, float]) -> Dict[str, Any]:
    """{"band": "columnar"|"mixed"|"equiaxed", "G_columnar_K_m", "G_equiaxed_K_m"}; constants keys a, n, N0."""
    kw = {"a": constants["a"], "n": constants["n"], "n0_m3": constants["N0"]}
    g_col = critical_gradient_K_m(v_m_s, PHI_COLUMNAR, **kw)
    g_eq = critical_gradient_K_m(v_m_s, PHI_EQUIAXED, **kw)
    if g_K_m >= g_col:
        band = "columnar"
    elif g_K_m <= g_eq:
        band = "equiaxed"
    else:
        band = "mixed"
    return {"band": band, "G_columnar_K_m": g_col, "G_equiaxed_K_m": g_eq}


def cet_block(alloy_id: str, points: Mapping[str, Optional[Tuple[float, float]]], *,
              constants_override: Optional[Mapping[str, float]] = None) -> Dict[str, Any]:
    """Per location (bottom/median/tail) band, or status unavailable with the registry reason.

    points maps a location name to (G_K_m, R_m_s) or None. constants_override (keys a, n, N0) is for tests only."""
    if constants_override is not None:
        constants: Optional[Mapping[str, float]] = constants_override
        status: Dict[str, Any] = {"status": "available", "reason": None}
    else:
        status = cet_constants(alloy_id)
        constants = None
        if status["status"] == "available":
            constants = {k: status["entries"][k]["value"] for k in ("a", "n", "N0")}
    if constants is None:
        return {"status": "unavailable", "reason": status["reason"], "locations": {k: None for k in points}}
    locations: Dict[str, Optional[Dict[str, Any]]] = {}
    for name, gr in points.items():
        if gr is None:
            locations[name] = None
            continue
        g, r = gr
        try:
            locations[name] = cet_band(g, r, constants)
        except ValueError:
            locations[name] = None
    return {"status": "available", "reason": None, "locations": locations}


def criterion_view() -> Dict[str, Any]:
    return {
        "modelId": MODEL_ID,
        "equation": EQUATION,
        "equationVerified": EQUATION_VERIFIED,
        "equationLocator": EQUATION_LOCATOR,
        "phiColumnar": PHI_COLUMNAR,
        "phiEquiaxed": PHI_EQUIAXED,
        "sources": {k: dict(v) for k, v in SOURCES.items()},
        "note": CRITERION_NOTE,
    }
