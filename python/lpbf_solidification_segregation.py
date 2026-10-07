#!/usr/bin/env python3
"""Nb microsegregation and terminal gamma/Laves screening for Nb-bearing Ni superalloys (stdlib only).

Literature estimate (screening), not CALPHAD. The model is the pseudo-ternary gamma-Nb-C
solidification model of DuPont, Robino and Marder, implemented as written in the source that was
read for this module:

  [D97] J.N. DuPont, C.V. Robino, A.R. Marder, "Solidification modeling of Nb bearing
        superalloys", Superalloys 718, 625, 706 and Derivatives (TMS, Pittsburgh PA,
        June 15-18 1997); Sandia report SAND97-1669C / CONF-970605-3, OSTI 515586.

The journal versions of the same model (Acta Mater 46 (1998) 4781-4790; Weld J 77 (1998)
417s-431s) and the alloy 625 overlay study (DuPont, Metall Mater Trans A 27 (1996) 3612-3620)
were NOT read here; no constant is taken from them.

Model ([D97] Eqs. 1-8):
  * Primary L -> gamma. Nb: Scheil, no diffusion in the solid (Eq. 1)
        f_l = (C_l,Nb / C_0,Nb) ** (1 / (k_Nb - 1)).
    C: equilibrium lever rule, fast diffusion in the solid (Eq. 2). Solidification path Eq. 3.
  * The primary path meets the line of twofold saturation gamma/NbC, C_l,C = a + b C_l,Nb
    (Eqs. 4-6, solved here for C_l,C by bisection).
  * Eutectic-type L -> (gamma + NbC) along that line: Eq. 7, integrated with the forward step of
    Eq. 8 in C_l,Nb. NbC is stoichiometric at 90.5 wt% Nb / 9.5 wt% C, k_NbC,Nb = 90.5 / C_l,Nb.
  * When C_l,Nb reaches the class II point C_Nb,L->(gamma+Laves) the remaining liquid is reported
    as gamma/Laves eutectic-type constituent ([D97] text after Eq. 8). The tabulated class II
    point (23.1 wt% Nb, 0.03 wt% C for the Ni-base set) does not lie exactly on the regressed
    line (a + b * 23.1 = 0.056 wt% C); this module stops on the Nb coordinate and says so.
  * C = 0 limit: the gamma-Nb binary Scheil result f_e = (C_e / C_0) ** (1 / (k - 1)) with
    C_e = C_Nb,L->(gamma+Laves). Carbon ties Nb up as NbC, so the binary value is an upper bound
    on the Laves fraction within this model (stated in the output).

What is NOT modelled (so the numbers are an upper bound on segregation only with respect to
these effects, which all reduce it): solid-state back-diffusion of Nb, solute trapping at
LPBF solidification rates, dendrite-tip undercooling ([D97] Eq. 1 assumes it negligible). No
kinetic constant (Aziz V_D or similar) is introduced. The constants come from GTA welds and
DTA samples of experimental alloys (no Mo, Ti, Al), so LPBF is always outside the source regime.

Every constant is a CONSTANTS entry {value, unit, source, locator, verified}. An entry that was
not confirmed against a source actually read has verified=False and value None; an alloy that
needs such an entry is reported as "unavailable" (never a guessed number).
"""
from __future__ import annotations

import copy
import math
from typing import Any, Dict, List, Mapping, Optional, Tuple

SCHEMA = "lpbf-solidification-segregation-1"
MODEL_ID = "dupont1997-pseudo-ternary-gamma-nb-c-v1"

EVIDENCE_LABEL = (
    "Literature estimate (screening): Scheil-type pseudo-ternary gamma-Nb-C model, constants from "
    "DuPont, Robino & Marder 1997 (GTA welds of experimental alloys); not CALPHAD; LPBF is outside "
    "the source regime"
)

SOURCES: Dict[str, Dict[str, Any]] = {
    "D97": {
        "citation": ("J.N. DuPont, C.V. Robino, A.R. Marder, 'Solidification modeling of Nb bearing superalloys', "
                     "Superalloys 718, 625, 706 and Derivatives, TMS, Pittsburgh PA, June 15-18 1997; "
                     "Sandia report SAND97-1669C / CONF-970605-3"),
        "url": "https://www.osti.gov/biblio/515586",
        "read": True,
        "note": "full text (scanned report, OSTI servlets/purl/515586) read for this module",
    },
    "SMC045": {
        "citation": ("Special Metals Corporation, INCONEL alloy 718 technical bulletin, Publication Number SMC-045 "
                     "(2007), Table 1 - Limiting Chemical Composition (conforms to AMS specifications)"),
        "url": "https://www.specialmetals.com/documents/technical-bulletins/inconel/inconel-alloy-718.pdf",
        "read": True,
        "note": ("composition limits for UNS N07718; ASTM F3055 (LPBF IN718) itself was not read, its Table 1 is "
                 "not quoted here"),
    },
    "D96": {
        "citation": ("J.N. DuPont, 'Solidification of an alloy 625 weld overlay', Metall. Mater. Trans. A 27 (1996) "
                     "3612-3620"),
        "url": "https://www.osti.gov/biblio/413291",
        "read": False,
        "note": ("only the abstract was available (it states that an experimentally determined k_Nb was used with "
                 "the Scheil equation but gives no value); full text not read"),
    },
}


def _c(value, unit, source, locator, verified=True):
    return {"value": value, "unit": unit, "source": source, "locator": locator, "verified": verified}


# Constant sets of [D97]. "ni-base" (Fe about 10-11 wt%) is the primary set; "fe-base" (Fe about
# 44-47 wt%) is reported for IN718 only as a bracketing sensitivity, never interpolated.
CONSTANTS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "ni-base": {
        "k_gamma_Nb": _c(0.46, "-", "D97", "Table 2 (Ni-Base) and Table 3 (k_gamma,Nb, Ni Base Alloys)"),
        "k_gamma_C": _c(0.27, "-", "D97", "Table 2 (Ni-Base) and Table 3 (k_gamma,C, Ni Base Alloys)"),
        "a_wtC": _c(0.98, "wt% C", "D97", "Table 3 (a, Ni Base Alloys); Eq. 4"),
        "b_wtC_per_wtNb": _c(-0.04, "wt% C / wt% Nb", "D97", "Table 3 (b, Ni Base Alloys); Eq. 4"),
        "C_Nb_laves": _c(23.1, "wt% Nb", "D97", "Table 3 (C_Nb,L->(gamma+Laves), Ni Base Alloys)"),
        "C_C_laves": _c(0.03, "wt% C", "D97", "Table 3 (C_C,L->(gamma+Laves), Ni Base Alloys)"),
        "C_NbC_Nb": _c(90.5, "wt% Nb", "D97", "text after Eq. 7 (NbC stoichiometric, 90.5 wt% Nb)"),
        "C_NbC_C": _c(9.5, "wt% C", "D97", "text after Eq. 7 (NbC stoichiometric, 9.5 wt% C)"),
    },
    "fe-base": {
        "k_gamma_Nb": _c(0.25, "-", "D97", "Table 2 (Fe-Base) and Table 3 (k_gamma,Nb, Fe Base Alloys)"),
        "k_gamma_C": _c(0.27, "-", "D97", "Table 2 (Fe-Base, footnote: estimated from the Ni base alloy data); "
                                          "Table 3"),
        "a_wtC": _c(1.24, "wt% C", "D97", "Table 3 (a, Fe Base Alloys); Eq. 4"),
        "b_wtC_per_wtNb": _c(-0.06, "wt% C / wt% Nb", "D97", "Table 3 (b, Fe Base Alloys); Eq. 4"),
        "C_Nb_laves": _c(20.4, "wt% Nb", "D97", "Table 3 (C_Nb,L->(gamma+Laves), Fe Base Alloys)"),
        "C_C_laves": _c(0.03, "wt% C", "D97", "Table 3 (C_C,L->(gamma+Laves), Fe Base Alloys)"),
        "C_NbC_Nb": _c(90.5, "wt% Nb", "D97", "text after Eq. 7 (NbC stoichiometric, 90.5 wt% Nb)"),
        "C_NbC_C": _c(9.5, "wt% C", "D97", "text after Eq. 7 (NbC stoichiometric, 9.5 wt% C)"),
    },
    # Alloy 625 specific k_Nb (DuPont 1996): not read -> unverified, no value.
    "in625-d96": {
        "k_gamma_Nb": _c(None, "-", "D96", "not located: full text not read (abstract only)", verified=False),
        "C_Nb_laves": _c(None, "wt% Nb", "D96", "not located: full text not read (abstract only)", verified=False),
    },
}

# Composition limits (wt%) used for the Nb band. "max" only -> min None.
COMPOSITION_LIMITS: Dict[str, Dict[str, Any]] = {
    "in718": {
        "source": "SMC045",
        "locator": "Table 1 - Limiting Chemical Composition, %",
        "limits": {
            "Ni": (50.00, 55.00), "Cr": (17.00, 21.00), "Nb": (4.75, 5.50), "Mo": (2.80, 3.30),
            "Ti": (0.65, 1.15), "Al": (0.20, 0.80), "Co": (None, 1.00), "C": (None, 0.08),
            "Mn": (None, 0.35), "Si": (None, 0.35), "P": (None, 0.015), "S": (None, 0.015),
            "B": (None, 0.006), "Cu": (None, 0.30),
        },
        "balance": "Fe",
        "nbNote": "Niobium (plus Tantalum)",
    },
}

# Composition range of the source experiments ([D97] Table 1, wt%), per constant set.
SOURCE_COMPOSITION_RANGE: Dict[str, Dict[str, Any]] = {
    "ni-base": {
        "locator": "D97 Table 1, alloys 1-8 (Ni base)",
        "range": {"Fe": (10.39, 11.12), "Ni": (63.93, 68.53), "Cr": (18.54, 19.30), "Nb": (1.82, 5.17),
                  "Si": (0.03, 0.52), "C": (0.010, 0.170)},
        "absentElements": ["Mo", "Ti", "Al", "Co"],
    },
    "fe-base": {
        "locator": "D97 Table 1, alloys 9-16 (Fe base)",
        "range": {"Fe": (44.05, 47.38), "Ni": (30.03, 33.56), "Cr": (19.31, 19.89), "Nb": (1.66, 4.88),
                  "Si": (0.01, 0.67), "C": (0.003, 0.216)},
        "absentElements": ["Mo", "Ti", "Al", "Co"],
    },
}

# The app's own alloy_registry composition carries no cited source; the band uses the read specification instead.
APP_NOMINAL_NOTE: Dict[str, str] = {
    "in718": ("The app's alloy_registry in718 composition_wt (Nb 5.1, C 0.04 wt%) has no cited source, so the band "
              "uses the SMC-045 specification limits instead. Nb 5.1 lies inside the band (4.75-5.50) and C 0.04 inside "
              "the C range covered by the C = 0 and C max columns."),
}

SOURCE_PROCESS = ("gas tungsten arc (GTA) autogenous welds and DTA samples of investment-cast experimental alloys "
                  "(D97 Experimental Procedure)")

NB_ALLOYS = ("in718", "in625")
NOT_APPLICABLE_REASON = "no Nb-bearing gamma/Laves model for this alloy"
UNVERIFIED_REASON = "constant not verified against primary source"

# Forward step of D97 Eq. 8 (wt% Nb). The source says "a very small amount"; the step is a numerical
# choice (convergence checked in test_lpbf_solidification_segregation against a 10x finer step).
EUTECTIC_STEP_WT_NB = 0.005
FS_SEGREGATION_POINTS = (0.9, 0.95)

UPPER_BOUND_NOTE = (
    "Upper bound with respect to effects that are not modelled and that all reduce segregation: solid-state "
    "back-diffusion of Nb, solute trapping at high solidification rate and dendrite-tip undercooling. It is not a "
    "bound with respect to the choice of k_Nb (see validity), and it is not an upper bound on measured Laves content "
    "(see sourceAgreementNote)."
)
SOURCE_AGREEMENT_NOTE = (
    "Not conservative against measurement, even in the source's own weld regime: D97 Fig. 9b (measured vs calculated "
    "gamma/Laves) shows several alloys with measured gamma/Laves above the calculated value, including alloys for "
    "which the model predicts no gamma/Laves (measured about 0.5-1.5 vol%, e.g. Ni-base alloy 8 in Fig. 3), and "
    "low-C Ni-base alloys where the model is about 2-3x high (alloys 5 and 7: measured about 2-3 vol% in Fig. 3). "
    "D97 also reports that Fe and Si raise the gamma/Laves amount; IN718 contains about 18 wt% Fe plus Mo, which the "
    "source alloys do not."
)
QUANTITY_NOTE = (
    "fGammaLavesConstituent and fGammaNbCConstituent are fractions of the gamma/Laves and gamma/NbC eutectic-type "
    "constituents (remaining liquid that transforms, eutectic gamma included; D97 terminology), not phase fractions "
    "of Laves or NbC."
)
BINARY_BOUND_NOTE = (
    "Binary gamma-Nb Scheil (C = 0): carbon ties Nb up as NbC, so within this model the binary value is an upper "
    "bound over carbon content on the gamma/Laves constituent fraction (a model statement, not a bound on "
    "measurement)."
)


class SegregationModelError(ValueError):
    """Invalid model input (k outside (0, 1), non-positive composition)."""


def _value(cset: Mapping[str, Dict[str, Any]], key: str) -> float:
    entry = cset[key]
    if not entry.get("verified") or entry.get("value") is None:
        raise LookupError(f"{key}: {UNVERIFIED_REASON}")
    return float(entry["value"])


def _check_k(k: float) -> None:
    if not (isinstance(k, (int, float)) and math.isfinite(k)):
        raise SegregationModelError("k must be finite")
    if abs(k - 1.0) < 1e-9:
        raise SegregationModelError("k = 1: no segregation, the Scheil exponent 1/(k-1) is undefined")
    if not 0.0 < k < 1.0:
        raise SegregationModelError("k must lie in (0, 1) for a solute rejected to the liquid")


def _check_positive(name: str, value: float) -> None:
    if not (isinstance(value, (int, float)) and math.isfinite(value) and value > 0.0):
        raise SegregationModelError(f"{name} must be a finite positive number")


def scheil_liquid_composition(c0: float, k: float, fs: float) -> float:
    """Scheil liquid composition C_L = C0 (1 - fs)^(k - 1) (D97 Eq. 1 rearranged), 0 <= fs < 1."""
    _check_k(k)
    _check_positive("c0", c0)
    if not (0.0 <= fs < 1.0):
        raise SegregationModelError("fs must lie in [0, 1)")
    return c0 * (1.0 - fs) ** (k - 1.0)


def scheil_eutectic_fraction(c0: float, ce: float, k: float) -> float:
    """Remaining liquid when the Scheil liquid reaches the eutectic composition: (Ce/C0)^(1/(k-1)), capped at 1."""
    _check_k(k)
    _check_positive("c0", c0)
    _check_positive("ce", ce)
    if c0 >= ce:
        return 1.0
    return (ce / c0) ** (1.0 / (k - 1.0))


def pseudo_ternary_path(c0_nb: float, c0_c: float, cset: Mapping[str, Dict[str, Any]],
                        step_wt_nb: float = EUTECTIC_STEP_WT_NB) -> Dict[str, Any]:
    """D97 Eqs. 1-8 for one composition. Fractions are fraction of the liquid (D97 compares them with volume %)."""
    k_nb = _value(cset, "k_gamma_Nb")
    k_c = _value(cset, "k_gamma_C")
    a = _value(cset, "a_wtC")
    b = _value(cset, "b_wtC_per_wtNb")
    ce_nb = _value(cset, "C_Nb_laves")
    c_nbc_nb = _value(cset, "C_NbC_Nb")
    c_nbc_c = _value(cset, "C_NbC_C")
    _check_k(k_nb)
    _check_k(k_c)
    _check_positive("c0_nb", c0_nb)
    _check_positive("c0_c", c0_c)
    _check_positive("step_wt_nb", step_wt_nb)
    if c0_nb >= ce_nb:
        return {"status": "computed", "primaryEnd": "nominal Nb at or above the gamma/Laves point",
                "fLiquidPrimaryEnd": 1.0, "fGammaNbCConstituent": 0.0, "fGammaLavesConstituent": 1.0, "fEutecticTotal": 1.0,
                "terminatedBy": "nominal-composition"}
    if c0_c >= a + b * c0_nb:
        return {"status": "outside-model",
                "reason": "nominal composition lies in the primary NbC field of the D97 solidification surface"}

    def path_nb(clc: float) -> float:  # Eq. 3
        return c0_nb * ((c0_c - k_c * clc) / ((1.0 - k_c) * clc)) ** (k_nb - 1.0)

    def gap(clc: float) -> float:  # Eq. 6 as (Eq. 5) - (Eq. 3)
        return (clc - a) / b - path_nb(clc)

    lo, hi = c0_c, c0_c / k_c
    lo_eps, hi_eps = lo * (1.0 + 1e-12), hi * (1.0 - 1e-12)
    g_lo = gap(lo_eps)
    for _ in range(200):
        mid = 0.5 * (lo_eps + hi_eps)
        g_mid = gap(mid)
        if (g_lo > 0) == (g_mid > 0):
            lo_eps, g_lo = mid, g_mid
        else:
            hi_eps = mid
    clc = 0.5 * (lo_eps + hi_eps)
    clnb = (clc - a) / b  # Eq. 5
    if clnb >= ce_nb:
        # The primary path reaches the gamma/Laves point before the gamma/NbC line: no NbC.
        f_laves = scheil_eutectic_fraction(c0_nb, ce_nb, k_nb)
        return {"status": "computed", "primaryEnd": "gamma/Laves point (primary path stays below the NbC line)",
                "fLiquidPrimaryEnd": f_laves, "liquidAtPrimaryEnd": {"Nb_wt": ce_nb, "C_wt": None},
                "fGammaNbCConstituent": 0.0, "fGammaLavesConstituent": f_laves, "fEutecticTotal": f_laves, "terminatedBy": "laves-point"}
    fl = (clnb / c0_nb) ** (1.0 / (k_nb - 1.0))  # Eq. 1
    f_primary_end = fl
    liquid_primary_end = {"Nb_wt": clnb, "C_wt": clc}
    terminated = "laves-point"
    while clnb < ce_nb:
        k_nbc_nb = c_nbc_nb / clnb
        dfl = (-(1.0 / (1.0 - k_nb)) * fl / clnb
               - ((k_nbc_nb - k_nb) / (1.0 - k_nb))
               * ((b * k_c * c0_c - b * c_nbc_c * (fl + k_c * (1.0 - fl))) / (c_nbc_c - k_c * clc) ** 2))  # Eq. 7
        step = min(step_wt_nb, ce_nb - clnb)
        fl_next = fl + dfl * step  # Eq. 8
        clnb += step
        clc = a + b * clnb  # Eq. 4
        if fl_next <= 0.0:
            fl = 0.0
            terminated = "liquid-exhausted-on-NbC-line"
            break
        fl = fl_next
    f_laves = fl if terminated == "laves-point" else 0.0
    return {"status": "computed", "primaryEnd": "gamma/NbC line of twofold saturation",
            "fLiquidPrimaryEnd": f_primary_end, "liquidAtPrimaryEnd": liquid_primary_end,
            "fGammaNbCConstituent": f_primary_end - f_laves, "fGammaLavesConstituent": f_laves, "fEutecticTotal": f_primary_end,
            "terminatedBy": terminated, "stepWtNb": step_wt_nb,
            "liquidAtTermination": {"Nb_wt": clnb, "C_wt": clc}}


def laves_risk_class(f_laves: Optional[float]) -> Optional[str]:
    """Two classes, no fitted threshold: any terminal gamma/Laves fraction > 0 under the Scheil-type model."""
    if f_laves is None:
        return None
    return "eutectic Laves expected (Scheil)" if f_laves > 0.0 else "no terminal eutectic under Scheil"


def _r(x: Optional[float], nd: int = 4) -> Optional[float]:
    return None if x is None else round(float(x), nd)


def _band_point(label: str, nb: float, c_max: Optional[float], cset) -> Dict[str, Any]:
    k_nb = _value(cset, "k_gamma_Nb")
    ce = _value(cset, "C_Nb_laves")
    f_bin = scheil_eutectic_fraction(nb, ce, k_nb)
    point: Dict[str, Any] = {
        "label": label, "Nb_wt": nb,
        "binaryUpperBound": {"C_wt": 0.0, "fGammaLavesConstituent": _r(f_bin), "riskClass": laves_risk_class(f_bin)},
    }
    if c_max is not None:
        tern = pseudo_ternary_path(nb, c_max, cset)
        if tern["status"] == "computed":
            point["pseudoTernaryAtCmax"] = {
                "C_wt": c_max, "fGammaNbCConstituent": _r(tern["fGammaNbCConstituent"]), "fGammaLavesConstituent": _r(tern["fGammaLavesConstituent"]),
                "fEutecticTotal": _r(tern["fEutecticTotal"]), "fLiquidPrimaryEnd": _r(tern["fLiquidPrimaryEnd"]),
                "terminatedBy": tern["terminatedBy"], "riskClass": laves_risk_class(tern["fGammaLavesConstituent"]),
            }
        else:
            point["pseudoTernaryAtCmax"] = {"C_wt": c_max, "status": tern["status"], "reason": tern.get("reason")}
    return point


def _segregation_ratios(nb: float, cset) -> Dict[str, Any]:
    k_nb = _value(cset, "k_gamma_Nb")
    ce = _value(cset, "C_Nb_laves")
    f_e = scheil_eutectic_fraction(nb, ce, k_nb)
    rows = []
    for fs in FS_SEGREGATION_POINTS:
        reached = (1.0 - fs) <= f_e
        cl = ce if reached else scheil_liquid_composition(nb, k_nb, fs)
        rows.append({"fs": fs, "liquidNb_wt": _r(cl, 3), "ratioToNominal": _r(cl / nb, 3),
                     "atEutecticComposition": reached})
    return {
        "Nb_wt": nb, "basis": "binary gamma-Nb Scheil (D97 Eq. 1), C = 0",
        "coreNb_wt": _r(k_nb * nb, 3), "coreRatioToNominal": _r(k_nb, 3),
        "interdendritic": rows,
        "note": ("When the remaining liquid at fs is below the eutectic fraction the liquid has reached the gamma/Laves "
                 "composition and the ratio is capped there (atEutecticComposition = true)."),
    }


def _spec_band(alloy_id: str) -> Tuple[Dict[str, float], Optional[float], Dict[str, Any]]:
    spec = COMPOSITION_LIMITS[alloy_id]
    nb_lo, nb_hi = spec["limits"]["Nb"]
    c_max = spec["limits"]["C"][1]
    others_max = sum(hi for el, (lo, hi) in spec["limits"].items() if hi is not None)
    others_min = sum(lo for el, (lo, hi) in spec["limits"].items() if lo is not None)
    band = {"min": nb_lo, "nominal": round(0.5 * (nb_lo + nb_hi), 4), "max": nb_hi}
    info = {
        "source": SOURCES[spec["source"]]["citation"], "locator": spec["locator"],
        "Nb_wt": {"min": nb_lo, "max": nb_hi, "nominal": band["nominal"],
                  "nominalIs": "midpoint of the specification range (not a measured composition)",
                  "note": spec["nbNote"]},
        "C_wt": {"min": None, "max": c_max, "note": "maximum only; C = 0 is the binary upper-bound end"},
        "balanceElement": spec["balance"],
        "balanceByDifference_wt": {"min": round(100.0 - others_max, 2), "max": round(100.0 - others_min, 2)},
        "appNominalNote": APP_NOMINAL_NOTE.get(alloy_id),
    }
    return band, c_max, info


def _validity(alloy_id: str, spec_info: Dict[str, Any], set_id: str) -> Dict[str, Any]:
    src = SOURCE_COMPOSITION_RANGE[set_id]
    spec = COMPOSITION_LIMITS[alloy_id]["limits"]
    outside: List[str] = []
    fe = spec_info["balanceByDifference_wt"]
    fe_lo, fe_hi = src["range"]["Fe"]
    if fe["min"] < fe_lo or fe["max"] > fe_hi:
        outside.append(f"Fe (balance, {fe['min']}-{fe['max']} wt% by difference) extends outside the source "
                       f"{fe_lo}-{fe_hi} wt%")
    nb_lo, nb_hi = src["range"]["Nb"]
    s_lo, s_hi = spec["Nb"]
    if s_hi > nb_hi or s_lo < nb_lo:
        outside.append(f"Nb specification {s_lo}-{s_hi} wt% extends outside the source {nb_lo}-{nb_hi} wt%")
    for el in src["absentElements"]:
        lo, hi = spec.get(el, (None, None))
        if (lo or 0.0) > 0.0:
            outside.append(f"{el} ({lo}-{hi} wt% in the specification) is absent from the source alloys")
    return {
        "sourceCompositionRange_wt": {el: list(v) for el, v in src["range"].items()},
        "sourceCompositionLocator": src["locator"],
        "sourceAbsentElements": list(src["absentElements"]),
        "outsideSourceComposition": bool(outside),
        "outsideSourceCompositionReasons": outside,
        "sourceRegime": SOURCE_PROCESS,
        "outsideSourceRegime": True,
        "outsideSourceRegimeReason": ("LPBF is not among the source processes (GTA welds, DTA samples); the k values "
                                      "and the Scheil assumption were not established at LPBF solidification rates"),
        "kTransferNote": ("D97 reports k_Nb = 0.46 for its Ni base alloys (Fe about 11 wt%) and 0.25 for its Fe base "
                          "alloys (Fe about 45 wt%) and attributes the drop to Fe. The source gives no k_Nb(Fe) relation "
                          "here, so no interpolation is made; the Fe-base result is shown as a bracketing sensitivity."),
    }


def _process_coupling(microstructure: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    keys = ("G_K_m", "R_m_s", "coolingRate_K_s", "morphology", "PDAS_um")
    base = {"source": "build job microstructure block (copied, not recomputed)",
            "usedInCalculation": False,
            "note": ("G and R are copied for context only: the Scheil-type result depends on composition alone. "
                     "Solute trapping and back-diffusion at this solidification rate are not modelled.")}
    if not isinstance(microstructure, Mapping):
        return {"status": "unavailable", "reason": "no microstructure block", **{k: None for k in keys}, **base}
    status = microstructure.get("status")
    if status in ("unavailable", "degenerate-floor") or status not in ("available", "screening-fallback"):
        why = microstructure.get("reason") or f"microstructure status {status!r}"
        return {"status": "unavailable", "reason": f"microstructure {status}: {why}",
                **{k: None for k in keys}, **base}
    out = {"status": status, "reason": microstructure.get("reason") if status == "screening-fallback" else None,
           **{k: copy.deepcopy(microstructure.get(k)) for k in keys}, **base}
    return out


def _unavailable(alloy_id: str, reason: str, status: str = "unavailable") -> Dict[str, Any]:
    return {"schema": SCHEMA, "modelId": MODEL_ID, "status": status, "alloyId": alloy_id, "reason": reason,
            "evidenceLabel": EVIDENCE_LABEL if status == "unavailable" else None}


def _constants_view(set_id: str) -> Dict[str, Any]:
    return {key: dict(entry, sourceCitation=SOURCES[entry["source"]]["citation"])
            for key, entry in CONSTANTS[set_id].items()}


def segregation_estimate(alloy_id: str, microstructure: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Segregation block for one alloy id. in718: computed; in625: unavailable (unverified constants); others n/a."""
    aid = str(alloy_id or "").strip().lower()
    if aid not in NB_ALLOYS:
        return _unavailable(aid, NOT_APPLICABLE_REASON, status="not-applicable")
    if aid == "in625":
        missing = [k for k, e in CONSTANTS["in625-d96"].items() if not e["verified"]]
        return _unavailable(aid, (f"{UNVERIFIED_REASON}: alloy 625 constants ({', '.join(missing)}) are in "
                                  f"{SOURCES['D96']['citation']}, which was not read; the D97 alloys contain no Mo, "
                                  "a major alloying element of alloy 625 (calphad_solver.COVERAGE_REFERENCE_SYSTEMS), so "
                                  "the D97 constants are not transferred"))
    set_id = "ni-base"
    try:
        band, c_max, spec_info = _spec_band(aid)
        points = [_band_point(lbl, band[lbl], c_max, CONSTANTS[set_id]) for lbl in ("min", "nominal", "max")]
        sensitivity = _band_point("nominal", band["nominal"], c_max, CONSTANTS["fe-base"])
        ratios = _segregation_ratios(band["nominal"], CONSTANTS[set_id])
    except LookupError as exc:
        return _unavailable(aid, str(exc))
    any_laves = any((p["binaryUpperBound"]["fGammaLavesConstituent"] or 0) > 0
                    or (p.get("pseudoTernaryAtCmax", {}).get("fGammaLavesConstituent") or 0) > 0 for p in points)
    return {
        "schema": SCHEMA,
        "modelId": MODEL_ID,
        "status": "available",
        "alloyId": aid,
        "evidenceLabel": EVIDENCE_LABEL,
        "source": SOURCES["D97"],
        "constantSet": set_id,
        "constants": _constants_view(set_id),
        "k_Nb": {"value": CONSTANTS[set_id]["k_gamma_Nb"]["value"],
                 "citation": SOURCES["D97"]["citation"], "locator": CONSTANTS[set_id]["k_gamma_Nb"]["locator"]},
        "composition": spec_info,
        "band": points,
        "bandNote": ("gamma/Laves constituent fraction at C = 0 (binary; model upper bound over C only) and at the "
                     "specification maximum C with the pseudo-ternary model; fractions are of the liquid, which D97 "
                     "compares with measured volume %"),
        "quantity": QUANTITY_NOTE,
        "feBaseSensitivity": {"constantSet": "fe-base", "constants": _constants_view("fe-base"),
                              "point": sensitivity,
                              "note": "bracketing sensitivity with the D97 Fe-base constants; not an interpolation"},
        "segregation": ratios,
        "riskClass": laves_risk_class(1.0 if any_laves else 0.0),
        "riskClassRule": ("gamma/Laves constituent > 0 at any band point under the Scheil-type model; no fitted "
                          "threshold. Binary Scheil without back-diffusion predicts a terminal gamma/Laves eutectic for "
                          "any Nb > 0, so this class is positive by construction for every Nb-bearing composition and "
                          "does not discriminate between compositions."),
        "riskClassPositiveByConstruction": True,
        "processCoupling": _process_coupling(microstructure),
        "upperBoundNote": UPPER_BOUND_NOTE,
        "sourceAgreementNote": SOURCE_AGREEMENT_NOTE,
        "binaryBoundNote": BINARY_BOUND_NOTE,
        "notModelled": ["solid-state back-diffusion of Nb", "solute trapping (no kinetic constant is introduced)",
                        "dendrite-tip undercooling", "Mo, Ti, Al and Si effects on the Laves reaction",
                        "mechanical consequences of Laves"],
        "classIINote": ("D97 Table 3 class II point (C_Nb, C_C) is not exactly on the regressed gamma/NbC line "
                        "(a + b * C_Nb gives about 0.056 wt% C at 23.1 wt% Nb); the eutectic-type integration stops "
                        "when C_l,Nb reaches C_Nb,L->(gamma+Laves)."),
        "validity": _validity(aid, spec_info, set_id),
    }


def build_job_segregation(alloy_id: str, microstructure: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Build-job entry point: composition-only estimate plus G/R/morphology copied from the microstructure block."""
    return segregation_estimate(alloy_id, microstructure)


if __name__ == "__main__":  # pragma: no cover - manual inspection
    import json
    print(json.dumps(segregation_estimate("in718", None), indent=1))
