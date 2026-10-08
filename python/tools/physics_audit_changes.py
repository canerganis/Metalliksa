"""Documented output changes of the physics-audit lane tafel-uq (EUQ-3/4/5/6/11/13).

Golden expectations (python/golden/phase6a/<solver>/step_b/*.json) may record these changes only
because each one is checked exactly here, never by a tolerance:

- tafel_corrosion_rate_solver (EUQ-6, EUQ-3): the 'standards' list loses "NACE SP0169" and "ISO 8044",
  the severity block gains the pinned scaleSource / textBasis texts, the fit result gains currentInput.
  EUQ-5 (supplied 0 kept) and EUQ-13 (0.15 V intersection limit) do not change any golden case.
- stochastic_uq_mmpds_solver (EUQ-4, EUQ-11): the oracle of the existing norm_ppf documented change
  (the pinned f41e316 solver blob with scipy's ndtri) additionally runs with the Joe & Kuo
  new-joe-kuo-6.21201 direction numbers read from scipy's own copy of the table, and its document is
  rewritten by uq_reliability_and_text_changes (generalized reliability index, design factor, censored
  bounds, two description strings; all texts pinned here, not imported from the solver).
"""

from __future__ import annotations

import copy
import os
import re
from statistics import NormalDist
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------------------------------------
# Tafel (EUQ-3, EUQ-6)
# ---------------------------------------------------------------------------------------------------------
TAFEL_STANDARDS = ["ASTM G102-89(2015)", "ASTM G59-97(2020)"]
TAFEL_REMOVED_STANDARDS = {"standards[2]": "NACE SP0169", "standards[3]": "ISO 8044"}
TAFEL_SEVERITY_SCALE_SOURCE = (
    "Fontana, Corrosion Engineering, 3rd ed., relative corrosion resistance scale (mm/y equivalents): "
    "Outstanding < 0.02, Excellent 0.02-0.1, Good 0.1-0.5, Fair 0.5-1, Poor 1-5, Unacceptable > 5 mm/y"
)
TAFEL_SEVERITY_TEXT_BASIS = (
    "In-house engineering guidance: the description and recommendation texts are not taken from Fontana or "
    "from any standard"
)
TAFEL_DENSITY_INPUT = {"keys": ["currentDensity_uA_cm2"], "currentUnit": None, "currentIsDensity": None,
                       "densityUnit": "uA/cm2"}
_TAFEL_ROW = re.compile(r"standards\[\d+\]|severity\.(scaleSource|textBasis)|currentInput(\..+)?")


def is_tafel_audit_row(key: str) -> bool:
    return bool(_TAFEL_ROW.fullmatch(key))


def tafel_row_problem(row: Dict[str, Any], new_stdout: Optional[Dict[str, Any]]) -> Optional[str]:
    """None when ``row`` is exactly one of the documented tafel changes."""
    key, kind = row["key"], row["kind"]
    if new_stdout is None:
        return f"{key}: documented tafel change needs the re-blessed document"
    if key in TAFEL_REMOVED_STANDARDS:
        if kind != "removed" or row["old"] != TAFEL_REMOVED_STANDARDS[key] or new_stdout.get("standards") != TAFEL_STANDARDS:
            return f"{key}: expected the removal of {TAFEL_REMOVED_STANDARDS[key]!r} leaving {TAFEL_STANDARDS!r}"
        return None
    if key == "severity.scaleSource" or key == "severity.textBasis":
        expected = TAFEL_SEVERITY_SCALE_SOURCE if key.endswith("scaleSource") else TAFEL_SEVERITY_TEXT_BASIS
        if kind != "added" or row["new"] != expected or (new_stdout.get("severity") or {}).get(key.split(".")[1]) != expected:
            return f"{key}: expected the pinned text as an added row"
        return None
    if key.startswith("currentInput"):
        if kind != "added" or new_stdout.get("currentInput") != TAFEL_DENSITY_INPUT:
            return f"{key}: expected currentInput {TAFEL_DENSITY_INPUT!r} (density-keyed points) as added rows"
        return None
    return f"{key}: no documented tafel change for this row"


# ---------------------------------------------------------------------------------------------------------
# Stochastic UQ (EUQ-4, EUQ-11)
# ---------------------------------------------------------------------------------------------------------
UQ_SAMPLING_DESCRIPTION = ("Local Sobol sequence (Joe & Kuo 2008 new-joe-kuo-6.21201 direction numbers) with "
                           "optional random digital shift.")
UQ_SENSITIVITY_METHOD = ("Centered Saltelli first-order / Jansen total-order pick-freeze on a digitally shifted "
                         "Joe-Kuo Sobol design (A and B from one 2k-dimensional sequence)")
UQ_LIMIT_STATE = "g = Rp0.2 - 1.5 * max(50 MPa, service stress); Pf = P(g < 0) at design factor 1.5"
UQ_RELIABILITY_INDEX_METHOD = (
    "Generalized reliability index beta_G = Phi^-1(1 - Pf) (Ditlevsen 1979) from the sampled failure count; "
    "not the Hasofer-Lind / FORM index (no design-point search is run)"
)
UQ_CENSORED_BOUND_METHOD = (
    "No sampled point (or every point) failed, so Pf and beta_G are censored: the bound uses the rule of three "
    "(95 %, Pf < 3/N or Pf > 1 - 3/N), which assumes independent samples; the QMC points are not independent, so "
    "the bound is approximate"
)
# Drift-row patterns of the UQ audit change (checked by whole-document equality with the oracle).
UQ_AUDIT_ROW_PATTERNS = (
    r"samplingMetadata\.(centeredL2Discrepancy|discrepancyReductionPct|samplingDescription)",
    r"sensitivityMetadata\.method",
    r"aerospaceReliability\.(yieldFailureProbability_Pf|hasoferLindBetaIndex|limitState|designFactor|failureCount|"
    r"probabilityYieldBelowDesignStress_Pf|generalizedReliabilityIndex(Status|BoundMethod|Bound(\..+)?)?|"
    r"reliabilityIndexMethod)",
)


def joe_kuo_poly(dims: int = 32) -> List[tuple]:
    """(s, a, [m]) rows of new-joe-kuo-6.21201 from scipy's copy of the Joe & Kuo table; row 0 is van der Corput."""
    import numpy as np
    import scipy.stats
    data = np.load(os.path.join(os.path.dirname(scipy.stats.__file__), "_sobol_direction_numbers.npz"))
    rows = [(1, 0, [1])]
    for d in range(1, dims):
        poly = int(data["poly"][d])
        s = poly.bit_length() - 1
        a = (poly >> 1) & ((1 << (s - 1)) - 1)
        rows.append((s, a, [int(v) for v in data["vinit"][d][:s]]))
    return rows


def uq_reliability_and_text_changes(doc: Dict[str, Any]) -> Dict[str, Any]:
    """A pre-audit UQ document with the EUQ-11 reliability block and the EUQ-4 description strings.

    Pf and N come from the document; beta_G = Phi^-1(1 - Pf) is recomputed with the stdlib NormalDist;
    0 or N failures give null + a rule-of-three bound instead of the former +/-4.75 clamp value.
    """
    out = copy.deepcopy(doc)
    n = out["sampleSizeN"]
    rel = out["aerospaceReliability"]
    pf = rel.pop("yieldFailureProbability_Pf")
    rel.pop("hasoferLindBetaIndex")
    failures = round(pf * n)
    inv = NormalDist().inv_cdf
    if 0 < failures < n:
        beta, status, bound = round(inv(1.0 - pf), 2), "estimated", None
    elif failures == 0:
        beta, status = None, "censored_no_failures"
        bound = {"type": "lower", "beta": round(inv(1.0 - 3.0 / n), 2) if n > 3 else None, "pfUpper": min(1.0, 3.0 / n)}
    else:
        beta, status = None, "censored_all_failures"
        bound = {"type": "upper", "beta": round(inv(3.0 / n), 2) if n > 3 else None, "pfLower": 1.0 - min(1.0, 3.0 / n)}
    rel.update({
        "limitState": UQ_LIMIT_STATE,
        "designFactor": 1.5,
        "failureCount": failures,
        "probabilityYieldBelowDesignStress_Pf": pf,
        "generalizedReliabilityIndex": beta,
        "generalizedReliabilityIndexStatus": status,
        "generalizedReliabilityIndexBound": bound,
        "generalizedReliabilityIndexBoundMethod": None if bound is None else UQ_CENSORED_BOUND_METHOD,
        "reliabilityIndexMethod": UQ_RELIABILITY_INDEX_METHOD,
    })
    out["samplingMetadata"]["samplingDescription"] = UQ_SAMPLING_DESCRIPTION
    out["sensitivityMetadata"]["method"] = UQ_SENSITIVITY_METHOD
    return out


def leaf(doc: Any, key: str) -> Any:
    """Value of a drift_report key ('a.b[2].c') in ``doc``; KeyError when absent."""
    import drift_report  # noqa: E402
    flat = dict(drift_report.flatten(doc))
    return flat[key]
