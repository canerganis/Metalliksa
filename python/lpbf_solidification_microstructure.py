"""
lpbf_solidification_microstructure.py  — Phase 8
================================================
Python-side solidification microstructure helpers for LPBF.

Provides:
  compute_solidification_microstructure(params, material, cfd_result)
    → RPC route "solidification-microstructure". Uses the CFD
      solidificationMicrostructure sub-dict (meanG_K_m, meanR_m_s, ...) when
      present. Without CFD data it returns status "unavailable": G and R are
      never estimated from default constants.
  project_build_job_microstructure(thermal)
    → Build-job projection of thermal["solidificationKinetics"] (the conduction
      field G/R from solidification_front); numbers are copied, not recomputed.

Legacy CFD-path correlations (unreachable today: no caller supplies a CFD result;
they are NOT the model of record for any displayed number):
    λ₁ [µm] = 80 · G^(-0.5) · R^(-0.25)        ("Hunt-Lu 1996" label; prefactor
                                                 differs from solidification_front,
                                                 see the S4 follow-up in the N1 handoff)
    λ₂ [µm] = 64.5 · Ṫ^(-0.33)                 (Kirkwood 1985)
The numbers shown by the build job and by the Microstructure Lab come from
solidification_front via thermal["solidificationKinetics"].

Hunt G/R morphology criterion:
    G/R > 1×10⁸  K·s/m²  → columnar
    G/R < 1×10⁶  K·s/m²  → equiaxed
    in between             → mixed (columnar+equiaxed coexistence)
"""

import math
from typing import Any, Dict


# ---------------------------------------------------------------------------
# Hunt-Lu / Kirkwood microstructure correlations
# ---------------------------------------------------------------------------

PDAS_COEFFICIENT = 80.0   # µm · (K/m)^0.5 · (m/s)^0.25
SDAS_COEFFICIENT = 64.5   # µm · (K/s)^0.33
G_OVER_R_COLUMNAR = 1.0e8   # K·s/m²  — above this: columnar
G_OVER_R_EQUIAXED = 1.0e6   # K·s/m²  — below this: equiaxed


def hunt_lu_pdas_um(G_Km: float, R_ms: float) -> float:
    """Primary dendrite arm spacing [µm] via Hunt-Lu 1996."""
    G_safe = max(G_Km, 1.0)
    R_safe = max(R_ms, 1.0e-6)
    pdas = PDAS_COEFFICIENT * (G_safe ** -0.5) * (R_safe ** -0.25)
    return float(max(0.1, min(pdas, 500.0)))


def kirkwood_sdas_um(cooling_rate_Ks: float) -> float:
    """Secondary dendrite arm spacing [µm] via Kirkwood 1985."""
    Tdot_safe = max(cooling_rate_Ks, 1.0)
    sdas = SDAS_COEFFICIENT * (Tdot_safe ** -0.33)
    return float(max(0.05, min(sdas, 200.0)))


def hunt_morphology(G_Km: float, R_ms: float) -> str:
    """Return 'columnar', 'equiaxed', or 'mixed' based on Hunt G/R criterion."""
    R_safe = max(R_ms, 1.0e-9)
    ratio = G_Km / R_safe
    if ratio > G_OVER_R_COLUMNAR:
        return "columnar"
    elif ratio < G_OVER_R_EQUIAXED:
        return "equiaxed"
    return "mixed"


def morphology_fractions(G_Km: float, R_ms: float) -> Dict[str, float]:
    """Return columnar/equiaxed/mixed fractions as a soft transition model."""
    R_safe = max(R_ms, 1.0e-9)
    log_gr = math.log10(max(1.0, G_Km / R_safe))
    log_col = math.log10(G_OVER_R_COLUMNAR)   # 8
    log_eq  = math.log10(G_OVER_R_EQUIAXED)   # 6
    # Soft sigmoid transition across the 2-decade window
    if log_gr >= log_col:
        f_col, f_eq = 1.0, 0.0
    elif log_gr <= log_eq:
        f_col, f_eq = 0.0, 1.0
    else:
        t = (log_gr - log_eq) / (log_col - log_eq)   # 0→equiaxed, 1→columnar
        f_col = t
        f_eq  = 1.0 - t
    f_mix = 1.0 - f_col - f_eq
    return {"columnar": round(f_col, 4), "equiaxed": round(f_eq, 4), "mixed": round(max(0.0, f_mix), 4)}


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------

_UNAVAILABLE_NO_CFD_REASON = (
    "no CFD solidification data (solidificationMicrostructure.meanG_K_m); "
    "G and R are not estimated from default constants"
)

_MICROSTRUCTURE_DOI = {
    "pdas": "10.1016/S1359-6454(96)00096-5",     # Hunt-Lu 1996
    "sdas": "10.1007/BF02649565",                 # Kirkwood 1985
    "morphology": "10.1016/0001-6160(84)90147-8", # Hunt 1984
}

_FALLBACK_REASON = (
    "thermal.solidificationKinetics used the tail-length heuristic (G = ΔT/x_rear, R = v·cosθ), "
    "not the liquidus field map; treat G/R/PDAS/SDAS as screening only"
)

_KEYHOLE_REGIME_NOTE = "Keyhole Mode: outside the conduction regime of the G/R field"

_MICROSTRUCTURE_DISCLAIMER = (
    "G from grad(T) at mushy-zone front; R from U·n_front. "
    "PDAS/SDAS are semi-empirical correlations validated for LPBF dendrite scale. "
    "Morphology is Hunt G/R criterion with soft transition band."
)


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def project_build_job_microstructure(thermal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Project thermal["solidificationKinetics"] into the build-job microstructure block.

    The numbers are copied from the thermal block (conduction-field G/R from
    solidification_front.evaluate_solidification); no second Hunt-Lu / Kirkwood
    estimate is made here. When the thermal block carries no finite G/R/cooling
    rate the block is reported as unavailable instead of falling back to constants.

    status:
      "available"          usedFieldMap is True (liquidus field-map G/R).
      "screening-fallback" usedFieldMap is not True or gradientSource is
                           "tail-length-fallback" (G = ΔT/x_rear, R = v·cosθ
                           heuristic); the numbers are still copied, never
                           recomputed, and carry the reason.
    R is taken from solidificationRate_R_mm_s / 1e3 when present (the thermal
    block rounds R_m_s to 3 decimals, about 1 % at 0.03 m/s); this is a unit
    conversion of the same thermal value, not a second estimate.
    """
    kin = thermal.get("solidificationKinetics") if isinstance(thermal, dict) else None
    if (
        isinstance(kin, dict)
        and _finite_number(kin.get("thermalGradient_G_K_m"))
        and _finite_number(kin.get("solidificationRate_R_m_s"))
        and _finite_number(kin.get("coolingRate_K_s"))
    ):
        base_disclaimer = kin.get("disclaimer") or ""
        note = (
            "Build-job microstructure is a projection of the thermal block's "
            "conduction-field G/R; no second estimate."
        )
        gradient_source = kin.get("gradientSource")
        used_field_map = kin.get("usedFieldMap")
        is_fallback = used_field_map is not True or gradient_source == "tail-length-fallback"
        r_mm_s = kin.get("solidificationRate_R_mm_s")
        r_m_s = r_mm_s / 1.0e3 if _finite_number(r_mm_s) else kin["solidificationRate_R_m_s"]
        geometry = thermal.get("meltPoolGeometry") if isinstance(thermal.get("meltPoolGeometry"), dict) else {}
        params = thermal.get("processParameters") if isinstance(thermal.get("processParameters"), dict) else {}
        regime = geometry.get("regime")
        regime_note = _KEYHOLE_REGIME_NOTE if isinstance(regime, str) and regime.startswith("Keyhole") else None
        block = {
            "status": "screening-fallback" if is_fallback else "available",
            "source": "thermal.solidificationKinetics",
            "modelId": kin.get("modelId"),
            "gradientSource": gradient_source,
            "usedFieldMap": used_field_map,
            "regime": regime,
            "normalizedEnthalpy": params.get("normalizedEnthalpy"),
            "regimeNote": regime_note,
            "G_K_m": kin["thermalGradient_G_K_m"],
            "R_m_s": r_m_s,
            "coolingRate_K_s": kin["coolingRate_K_s"],
            "PDAS_um": kin.get("primaryDendriteArmSpacing_PDAS_um"),
            "SDAS_um": kin.get("secondaryDendriteArmSpacing_SDAS_um"),
            "morphology": kin.get("microstructureMorphology"),
            "g_over_r_ratio": kin.get("g_over_r_ratio"),
            "doi": kin.get("doi"),
            "disclaimer": (base_disclaimer + " " + note).strip(),
        }
        if is_fallback:
            block["reason"] = _FALLBACK_REASON
            block["disclaimer"] = (
                block["disclaimer"]
                + " This operating point used the tail-length heuristic, not the liquidus field map "
                "(see reason): the G,R wording above does not apply."
            ).strip()
        return block
    return {
        "status": "unavailable",
        "reason": "thermal.solidificationKinetics missing or non-finite",
        "G_K_m": None,
        "R_m_s": None,
        "coolingRate_K_s": None,
        "PDAS_um": None,
        "SDAS_um": None,
        "morphology": None,
    }


def compute_solidification_microstructure(
    params: Dict[str, Any],
    material: Dict[str, Any],
    cfd_result: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Compute solidification microstructure metrics from CFD solidification data.

    Parameters
    ----------
    params   : LPBF process parameters (kept for the RPC signature; not used to
               estimate G/R)
    material : Alloy properties (kept for the RPC signature; not used to
               estimate G/R)
    cfd_result : Optional output from cfd_multiphysics(); the
                 solidificationMicrostructure sub-dict from the OpenFOAM JSON
                 supplies G and R.

    Returns
    -------
    With CFD data: status "available" and keys
        source, G_K_m, maxG_K_m, R_m_s, maxR_m_s, coolingRate_K_s,
        PDAS_um, SDAS_um, morphology, morphologyFractions,
        frontCellCount, graftAnnotation
    Without CFD data: status "unavailable", source "none", a reason, and None
    for every numeric field (no default-constant estimate is ever returned).
    """
    cfd_solid = {}
    if cfd_result and isinstance(cfd_result.get("solidificationMicrostructure"), dict):
        cfd_solid = cfd_result["solidificationMicrostructure"]

    if not bool(cfd_solid.get("meanG_K_m")):
        return {
            "status": "unavailable",
            "source": "none",
            "reason": _UNAVAILABLE_NO_CFD_REASON,
            "G_K_m": None,
            "maxG_K_m": None,
            "R_m_s": None,
            "maxR_m_s": None,
            "coolingRate_K_s": None,
            "PDAS_um": None,
            "SDAS_um": None,
            "morphology": None,
            "morphologyFractions": None,
            "frontCellCount": None,
            "doi": dict(_MICROSTRUCTURE_DOI),
            "disclaimer": _MICROSTRUCTURE_DISCLAIMER,
            "graftAnnotation": "covers: python/lpbf_solidification_microstructure.py",
        }

    G    = float(cfd_solid["meanG_K_m"])
    R    = float(cfd_solid["meanR_m_s"])
    Tdot = float(cfd_solid.get("meanCoolingRate_K_s", G * R))
    maxG = float(cfd_solid.get("maxG_K_m", G))
    maxR = float(cfd_solid.get("maxR_m_s", R))
    front_cells = int(cfd_solid.get("frontCellCount", 0))
    source = "openfoam-solidification-model-v1"

    # ---- Microstructure correlations ---------------------------------------
    pdas = hunt_lu_pdas_um(G, R)
    sdas = kirkwood_sdas_um(Tdot)
    morph = hunt_morphology(G, R)
    fracs = morphology_fractions(G, R)

    # ---- Validate physical bounds (unit-test oracle; CFD path only) --------
    assert 1.0e3 <= G <= 1.0e10, f"G={G:.3e} K/m out of physical range [1e3, 1e10]"
    assert 1.0e-6 <= R <= 2.0,   f"R={R:.3e} m/s out of physical range [1e-6, 2]"
    assert 0.05 <= pdas <= 500.0, f"PDAS={pdas:.2f} µm outside [0.05, 500]"
    assert 0.01 <= sdas <= 200.0, f"SDAS={sdas:.2f} µm outside [0.01, 200]"
    total_frac = fracs["columnar"] + fracs["equiaxed"] + fracs["mixed"]
    assert abs(total_frac - 1.0) < 0.01, f"Morphology fractions sum {total_frac:.4f} ≠ 1"

    return {
        "status": "available",
        "source": source,
        "G_K_m": round(G, 2),
        "maxG_K_m": round(maxG, 2),
        "R_m_s": round(R, 6),
        "maxR_m_s": round(maxR, 6),
        "coolingRate_K_s": round(Tdot, 2),
        "PDAS_um": round(pdas, 3),
        "SDAS_um": round(sdas, 3),
        "morphology": morph,
        "morphologyFractions": fracs,
        "frontCellCount": front_cells,
        "doi": dict(_MICROSTRUCTURE_DOI),
        "disclaimer": _MICROSTRUCTURE_DISCLAIMER,
        "graftAnnotation": "covers: python/lpbf_solidification_microstructure.py",
    }
