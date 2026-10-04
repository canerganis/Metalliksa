#!/usr/bin/env python3
"""
Murakami √area fatigue screening + Gumbel extreme-value fit + qualification template.

No defect sizes → data_not_supplied (nothing invented).
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional

import murakami_constants

# Screening defaults when HV not supplied (literature-typical as-built / STA ranges).
ALLOY_HV_DEFAULTS = {
    "ti6al4v": 340.0,
    "ss316l": 210.0,
    "alsi10mg": 120.0,
    "in718": 380.0,
}

PASTE_HINT = (
    "Paste √area values in µm: one per line, or CSV / whitespace / semicolon separated. "
    "Example: 40, 55, 62, 48, 70"
)


def parse_defect_sqrt_areas_text(text: Optional[str]) -> List[float]:
    """Parse pasted CSV / whitespace / line-separated √area (µm). Empty → []."""
    if not text or not str(text).strip():
        return []
    parts = re.split(r"[\s,;|/]+", str(text).strip())
    out: List[float] = []
    for p in parts:
        if not p:
            continue
        try:
            v = float(p)
        except ValueError:
            continue
        if v > 0:
            out.append(v)
    return out


def resolve_hardness_HV(hardness_HV: Optional[float], alloy_id: Optional[str] = None) -> tuple[Optional[float], str]:
    if hardness_HV is not None:
        return float(hardness_HV), "user_override"
    if alloy_id and alloy_id in ALLOY_HV_DEFAULTS:
        return ALLOY_HV_DEFAULTS[alloy_id], "alloy_default"
    return None, "none"


def gumbel_fit_maxima(samples: List[float]) -> Optional[Dict[str, float]]:
    vals = [float(x) for x in samples if x is not None and float(x) > 0]
    n = len(vals)
    if n < 3:
        return None
    mu = sum(vals) / n
    var = sum((v - mu) ** 2 for v in vals) / max(1, n - 1)
    sigma = math.sqrt(max(var, 1e-12))
    scale = sigma * math.sqrt(6.0) / math.pi
    loc = mu - 0.5772156649 * scale
    x_char = loc - scale * math.log(-math.log(1.0 - 1.0 / max(n, 2)))
    return {
        "n": float(n),
        "loc_um": round(loc, 4),
        "scale_um": round(scale, 4),
        "mean_um": round(mu, 4),
        "std_um": round(sigma, 4),
        "characteristicLargest_um": round(x_char, 4),
    }


def murakami_fatigue_limit_MPa(sqrt_area_um: float, hardness_HV: float, location: str = "internal") -> float:
    """Murakami sigma_w = C (HV + 120) / sqrt(area)^(1/6) [MPa].

    C comes from murakami_constants (surface 1.43, sub-surface 1.41, internal 1.56;
    this function used 1.43 for internal and 1.41 for everything else, which is wrong
    for both). Non-positive / non-finite sqrt_area or HV, or an unknown location,
    raise input_validation.ValidationError instead of being clamped.
    """
    return murakami_constants.murakami_sqrt_area_limit_MPa(sqrt_area_um, hardness_HV, location)


def evaluate_murakami_block(
    defect_sqrt_areas_um: Optional[List[float]],
    hardness_HV: Optional[float] = None,
    ct_detection_threshold_um: Optional[float] = None,
    alloy_id: Optional[str] = None,
    defect_paste: Optional[str] = None,
) -> Dict[str, Any]:
    defects = list(defect_sqrt_areas_um or [])
    if not defects and defect_paste:
        defects = parse_defect_sqrt_areas_text(defect_paste)

    if not defects:
        return {
            "status": "data_not_supplied",
            "fatigueLimit_MPa": None,
            "gumbel": None,
            "ctDetectionThreshold_um": ct_detection_threshold_um,
            "pasteHint": PASTE_HINT,
            "alloyHvDefaults": dict(ALLOY_HV_DEFAULTS),
            "note": (
                "Murakami √area screening requires measured defect √area list (µm). "
                "No sizes invented. SCREENING ONLY when supplied."
            ),
            "references": [
                "Murakami Y., Metal Fatigue: Effects of Small Defects and Nonmetallic Inclusions",
                "Gumbel extreme-value distribution for largest defect screening",
            ],
        }

    gumbel = gumbel_fit_maxima(defects)
    hv, hv_source = resolve_hardness_HV(hardness_HV, alloy_id)
    if hv is None:
        hv, hv_source = 350.0, "generic_fallback"
    if gumbel is None:
        char = max(float(x) for x in defects)
        gumbel = {"n": float(len(defects)), "characteristicLargest_um": char, "fit": "max-only"}
    else:
        char = gumbel["characteristicLargest_um"]

    return {
        "status": "screening_estimate",
        "hardness_HV": hv,
        "hardnessSource": hv_source,
        "nDefects": len(defects),
        "gumbel": gumbel,
        "sqrtAreaUsed_um": round(float(char), 4),
        "fatigueLimit_internal_MPa": round(murakami_fatigue_limit_MPa(char, hv, "internal"), 2),
        "fatigueLimit_surface_MPa": round(murakami_fatigue_limit_MPa(char, hv, "surface"), 2),
        "ctDetectionThreshold_um": ct_detection_threshold_um,
        "pasteHint": PASTE_HINT,
        "note": (
            "SCREENING ONLY — Murakami empirical √area model; not a certified allowable. "
            "Supply CT/metallography √area in µm."
        ),
        "references": [
            "Murakami Y., Metal Fatigue: Effects of Small Defects and Nonmetallic Inclusions",
            "Gumbel extreme-value distribution for largest defect screening",
        ],
    }


QUALIFICATION_BY_ALLOY = {
    "ti6al4v": {
        "standards": ["AMS 4999 / ASTM F2924 (Ti-6Al-4V LPBF)", "ASTM F3001 (ELI)", "AMS 7003 (process)"],
        "oContentLimit_wt_pct": 0.20,
        "couponPlan": ["0° tensile", "90° tensile", "density Archimedes ASTM B962", "CT porosity"],
    },
    "ss316l": {
        "standards": ["ASTM F3184", "ASTM F3303 (LPBF process)", "AMS 7003"],
        "oContentLimit_wt_pct": None,
        "couponPlan": ["0° tensile", "90° tensile", "density", "intergranular corrosion screen"],
    },
    "alsi10mg": {
        "standards": ["AMS 4215 / ASTM F3318", "ASTM F3303", "AMS 7003"],
        "oContentLimit_wt_pct": None,
        "couponPlan": ["0° tensile", "90° tensile", "density", "HIP vs as-built cohort"],
    },
    "in718": {
        "standards": ["AMS 5662 / ASTM F3055", "AMS 7003", "AMS 7032 (machine qualification context)"],
        "oContentLimit_wt_pct": None,
        "couponPlan": ["0° tensile", "90° tensile", "STA cohort", "density", "CT"],
    },
}


def build_qualification_block(alloy_id: str, input_hash: str, git_sha: Optional[str] = None) -> Dict[str, Any]:
    tmpl = QUALIFICATION_BY_ALLOY.get(alloy_id, QUALIFICATION_BY_ALLOY["in718"])
    return {
        "status": "not_executed",
        "screeningOnly": True,
        "alloyId": alloy_id,
        "standards": tmpl["standards"],
        "oContentLimit_wt_pct": tmpl["oContentLimit_wt_pct"],
        "couponPlan": tmpl["couponPlan"],
        "traceability": {
            "inputHash": input_hash,
            "gitSha": git_sha,
            "note": "Hash + SHA for report binding; not a digital signature / CoC.",
        },
        "note": (
            "SCREENING ONLY — standards listed for traceability. Protocol rows are Not executed; "
            "not a flight / MMPDS allowable release."
        ),
    }
