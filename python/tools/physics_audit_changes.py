"""Documented output changes of the physics-audit lane tafel-uq-icme (EUQ-3/4/5/6/9/10/11/13).

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
- icme_multiscale_pipeline_solver (EUQ-9, EUQ-10): the oracle is the pinned pre-fix solver blob
  (ICME_ORACLE_REVISION, bound by sha256) with exactly the source replacements in ICME_SOURCE_PATCH
  (Brown-Ham '- f' term, Abaqus density in tonne/mm^3 + units line, mechanism label; review follow-up: a
  weak-coupling bracket <= 0 gives shearingStrength_MPa null + cuttingContributionStatus, never 0 MPa cutting). A drift row is an
  audit row when its key differs between the unpatched and the patched blob run; it is accepted only if the
  whole re-blessed document equals the patched run and the row's new value is that document's leaf.
"""

from __future__ import annotations

import copy
import os
import re
import tempfile
from pathlib import Path
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


# ---------------------------------------------------------------------------------------------------------
# ICME (EUQ-9, EUQ-10)
# ---------------------------------------------------------------------------------------------------------
ICME_SOLVER = "icme_multiscale_pipeline_solver"
# Last revision of the solver before the audit fix (fix(icme): illustrative model status ...).
ICME_ORACLE_REVISION = "ee431db3"
ICME_ORACLE_SHA256 = "305d1324a6e5e3f8ddc9e321ce64bb6842eeedc3996f2ba5969ecfda58b7f87b"
# (old source text, new source text): the documented physics change, applied to the pinned blob.
ICME_SOURCE_PATCH = (
    ("    # Shear stress: delta_sigma_cut = M * (gamma_apb / (2*b)) * sqrt( (8 * gamma_apb * r * f) / (pi * G * b^2) )\n",
     ""),
    ("    delta_sigma_cutting_MPa = (taylor_M * (gamma_apb_J_m2 / (2.0 * b_meters)) * math.sqrt(max(1e-6, ratio_term))) / 1e6\n"
     "    delta_sigma_cutting_MPa = min(850.0, delta_sigma_cutting_MPa)\n",
     # Brown-Ham weak pair coupling (Ardell 1985): (gamma/2b) * [sqrt(8 gamma f r / (pi T)) - f], T = G b^2 / 2;
     # a bracket <= 0 (weak coupling not applicable) gives no cutting estimate (null + status), never 0 MPa.
     "    brown_ham_bracket = math.sqrt(ratio_term) - volume_frac_precip\n"
     "    cutting_estimated = brown_ham_bracket > 0.0\n"
     "    cutting_status = None\n"
     "    if cutting_estimated:\n"
     "        delta_sigma_cutting_MPa = (taylor_M * (gamma_apb_J_m2 / (2.0 * b_meters)) * brown_ham_bracket) / 1e6\n"
     "        delta_sigma_cutting_MPa = min(850.0, delta_sigma_cutting_MPa)\n"
     "    else:\n"
     "        delta_sigma_cutting_MPa = None\n"
     "        cutting_status = (\n"
     "            \"unavailable_weak_coupling_not_applicable: sqrt(8*gamma*f*r/(pi*T)) <= f at \"\n"
     "            f\"r = {r_nm:.2f} nm, f = {volume_frac_precip:.3f}; the Brown-Ham weak pair-coupling expression is \"\n"
     "            \"<= 0 here, so the cutting contribution is not estimated and the precipitation term is left out \"\n"
     "            \"of the yield strength (0 MPa added, not a cutting estimate)\")\n"),
    ('    if delta_sigma_cutting_MPa < delta_sigma_orowan_MPa:\n'
     '        precip_mechanism = "Dislocation Particle Shearing (Friedel-Gere Cutting)"\n',
     '    if not cutting_estimated:\n'
     '        precip_mechanism = "Not estimated (weak pair-coupling cutting expression <= 0; see cuttingContributionStatus)"\n'
     '        delta_sigma_precip_MPa = 0.0\n'
     '    elif delta_sigma_cutting_MPa < delta_sigma_orowan_MPa:\n'
     '        precip_mechanism = "Dislocation Particle Shearing (Brown-Ham weak pair-coupling cutting)"\n'),
    ('                "shearingStrength_MPa": round(delta_sigma_cutting_MPa, 1),\n',
     '                "shearingStrength_MPa": None if delta_sigma_cutting_MPa is None else round(delta_sigma_cutting_MPa, 1),\n'
     '                "cuttingContributionStatus": cutting_status,\n'),
    ("** MetalliX Multi-Scale ICME ILLUSTRATIVE Card (uncalibrated, not validated) for {alloy_name}\n"
     "*MATERIAL, NAME={alloy_name.replace(' ', '_').upper()}\n*DENSITY\n{density_g_cm3 * 1000.0:.2f}\n",
     # Abaqus without built-in units: mm-N-s-tonne-MPa needs the density in tonne/mm^3
     "** MetalliX Multi-Scale ICME ILLUSTRATIVE Card (uncalibrated, not validated) for {alloy_name}\n"
     "** Units: mm, N, s, tonne, MPa (density in tonne/mm^3)\n"
     "*MATERIAL, NAME={alloy_name.replace(' ', '_').upper()}\n*DENSITY\n{density_g_cm3 * 1e-9:.4e}\n"),
)
_ICME_CACHE: Dict[str, Any] = {}


def _icme_blob(patched: bool) -> bytes:
    import capture_phase6a_golden as golden  # noqa: E402 (tools/ module)
    source = golden.solver_bytes(ICME_SOLVER, ICME_ORACLE_REVISION)
    if golden.normalised_sha256(source) != ICME_ORACLE_SHA256:
        raise RuntimeError(f"python/{ICME_SOLVER}.py at {ICME_ORACLE_REVISION} does not match the pinned sha256")
    text = source.decode("utf-8").replace("\r\n", "\n")
    if patched:
        for old, new in ICME_SOURCE_PATCH:
            if text.count(old) != 1:
                raise RuntimeError(f"ICME oracle patch does not apply exactly once: {old[:60]!r}")
            text = text.replace(old, new)
    return text.encode("utf-8")


def icme_oracle_stdout(payload: Dict[str, Any], patched: bool = True) -> Dict[str, Any]:
    """Stdout (volatile and provenance keys stripped) of the pinned pre-fix ICME blob, with or without the
    documented EUQ-9/EUQ-10 source patch, run exactly like run_solver runs a base blob."""
    import json
    import capture_phase6a_golden as golden  # noqa: E402
    cache_key = json.dumps([payload, patched])
    if cache_key not in _ICME_CACHE:
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / f"{ICME_SOLVER}.py"
            script.write_bytes(_icme_blob(patched))
            result = golden.run_solver(ICME_SOLVER, payload, script=script)
        if result["exitCode"] != 0:
            raise RuntimeError(f"ICME oracle run failed: {result['stderr']}")
        _ICME_CACHE[cache_key] = result["stdout"]
    return _ICME_CACHE[cache_key]


def icme_audit_keys(payload: Dict[str, Any]) -> set:
    """Drift keys whose value the EUQ-9/EUQ-10 patch changes for ``payload``."""
    import drift_report  # noqa: E402 (tools/ module)
    return {r["key"] for r in drift_report.diff(icme_oracle_stdout(payload, False), icme_oracle_stdout(payload, True))}


def leaf(doc: Any, key: str) -> Any:
    """Value of a drift_report key ('a.b[2].c') in ``doc``; KeyError when absent."""
    import drift_report  # noqa: E402
    flat = dict(drift_report.flatten(doc))
    return flat[key]


def icme_row_problem(row: Dict[str, Any], new_stdout: Optional[Dict[str, Any]],
                     payload: Optional[Dict[str, Any]]) -> Optional[str]:
    """None when ``row`` is an EUQ-9/EUQ-10 audit row of a document equal to the patched oracle run."""
    import capture_phase6a_golden as golden  # noqa: E402
    key = row["key"]
    if new_stdout is None or payload is None:
        return f"{key}: the ICME audit change needs the re-blessed document and the case payload"
    try:
        expected = icme_oracle_stdout(payload, True)
    except (RuntimeError, OSError) as exc:
        return f"{key}: ICME audit oracle unavailable ({exc})"
    if golden.canonical(new_stdout) != golden.canonical(expected):
        return (f"{key}: re-blessed document differs from the pinned {ICME_ORACLE_REVISION} ICME solver with the "
                "documented EUQ-9/EUQ-10 patch")
    if row["kind"] == "removed":
        try:
            leaf(new_stdout, key)
            return f"{key}: removed row still present in the re-blessed document"
        except KeyError:
            return None
    try:
        value = leaf(new_stdout, key)
    except KeyError:
        return f"{key}: row is not in the re-blessed document"
    if value != row["new"] or type(value) is not type(row["new"]):
        return f"{key}: row new value {row['new']!r} is not the document's {value!r}"
    return None
