#!/usr/bin/env python3
"""
MetalliX Corrosion EIS & Kinetics Solver (corrosion_kinetics action)
Stern-Geary polarization resistance (ASTM G59 formulation), ASTM G102 penetration rate and
the pitting-potential margin for the electrochem-suite corrosion sublab. The former coating
water-uptake timeline and coating Nyquist spectra were removed: they came from fixed constants
(no input of the request changed them), so they were not a computation of the user's system. The battery DRT, P2D, LLI/LAM, Bernardi thermal, SEI
degradation, Nernst-Planck-Poisson, uploaded-EIS and Bisquert TLM actions were
removed on 2026-10-04 (no UI consumer).
"""

import sys
import json
import math
import time

import physical_constants
from alloy_data_calphad_battery_icme import provenance as _domain_data_provenance
from input_validation import ValidationError, validation_envelope
from tafel_corrosion_rate_solver import (
    LN10 as _LN10,
    MILS_PER_MM as _MILS_PER_MM,
    _supplied_positive,
    corrosion_preset as _corrosion_preset,
)

# Phase 6a value step (b): every R/F site uses the exact SI 2019 products N_A*k and
# N_A*e. Before, the four sites used four different printings: p2d 8.314/96485.332,
# degradation 8.314, Nernst-Planck-Poisson 8.314462618/96485.33212 and uploaded EIS
# 8.31446/96485.33. Those four sites were removed with their actions on 2026-10-04;
# R_GAS stays as the exported exact constant (provenance below, test_phase6a_t2a_migration).
R_GAS = physical_constants.GAS_CONSTANT_R.value  # J/(mol*K), exact
F_FARADAY = physical_constants.FARADAY.value  # C/mol, exact
# ASTM G102 K1 = 1e-6 * (s/yr = 365.25 * 86400) * 10 / F = 0.0032707148 mm*g/(uA*cm*yr),
# derived from the exact F (fix round item 6; was the printed 3.27e-3 / 0.00327).
ASTM_G102_K1_MM_G_UA_CM_YR = (1e-6 * 31557600.0 * 10.0) / F_FARADAY
ZERO_CELSIUS_K = physical_constants.ZERO_CELSIUS_K.value  # 273.15 K

# ==========================================
# 3. Corrosion kinetics: Stern-Geary Rp, ASTM G102 rate, pitting margin
# ==========================================

def _supplied_number(raw, label):
    """(value, None) for a supplied finite number (any sign, e.g. a potential in V), else (None, reason)."""
    if raw is None:
        return None, f"{label} was not supplied"
    if isinstance(raw, bool):
        return None, f"{label} must be a number, not a boolean"
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None, f"{label} must be a number (received {raw!r})"
    if not math.isfinite(value):
        return None, f"{label} must be finite (received {raw!r})"
    return value, None


def simulate_corrosion_eis_and_kinetics(metal_id, beta_a, beta_c, i0_corr_ua_cm2, e_pit_v, e0_v):
    """
    Computes the Stern-Geary polarization resistance, the Faraday penetration rate (ASTM G102)
    and the pitting-potential margin.

    The substrate is resolved exactly through alloy_registry (domain "corrosion"), the same
    resolution and the same computed ASTM G102 equivalent weight (elements >= 1 wt %,
    renormalised) the Tafel solver uses. An unknown alloy raises ValidationError(UNKNOWN_ALLOY);
    the former substring match ("al" in the id -> aluminium, "ti" -> titanium, anything else
    -> steel EW 27.9 / 7.87 g/cm3) is gone.

    Every input is required: metalId, betaA, betaC, i0Corr_uA (> 0), ePit and e0 (finite, V). The former
    defaults (steel-316l, betaA 0.12, betaC 0.11, i0 0.18, ePit 0.42, e0 0.08) were invented numbers. A missing
    or invalid input makes only the outputs that need it unavailable (null + reason, `status` "partial", or
    "unavailable" when nothing can be computed): Stern-Geary B and Rp need betaA, betaC, i0; the Faraday rate
    needs i0 and metalId; the pitting margin needs ePit and e0. A metalId that is
    sent but unknown still raises ValidationError(UNKNOWN_ALLOY). exposureDays is no longer an input: no output depends on it.
    Corrosion rates are rounded to 6 significant digits (a fixed 5 decimals printed 9e-5 mm/yr with one).
    """
    unavailable = {}
    preset = None
    if metal_id is None or metal_id == "":
        unavailable["metalId"] = "metalId was not supplied (no default substrate)"
    else:
        try:
            preset = _corrosion_preset(metal_id)
        except ValidationError as exc:  # same refusal, reported against the field this action receives
            raise ValidationError(exc.code, "metalId", exc.message, exc.detail) from exc
    beta_a, reason = _supplied_positive(beta_a, "betaA")
    if reason:
        unavailable["betaA"] = reason
    beta_c, reason = _supplied_positive(beta_c, "betaC")
    if reason:
        unavailable["betaC"] = reason
    i0_corr_ua_cm2, reason = _supplied_positive(i0_corr_ua_cm2, "i0Corr_uA")
    if reason:
        unavailable["i0Corr_uA"] = reason
    e_pit_v, reason = _supplied_number(e_pit_v, "ePit")
    if reason:
        unavailable["ePit"] = reason
    e0_v, reason = _supplied_number(e0_v, "e0")
    if reason:
        unavailable["e0"] = reason

    # Stern-Geary constant B (V) = (beta_a * beta_c) / (ln(10) * (beta_a + beta_c)); needs betaA, betaC
    # Polarization Resistance R_p = B / i_corr (i0 converted from uA/cm2 to A/cm2); needs i0 as well
    b_val = r_p_ohm_cm2 = None
    if beta_a is not None and beta_c is not None:
        b_val = (beta_a * beta_c) / (_LN10 * (beta_a + beta_c))
        if i0_corr_ua_cm2 is not None:
            r_p_ohm_cm2 = b_val / max(1e-12, i0_corr_ua_cm2 * 1e-6)

    # Faraday's Law Corrosion Penetration Rate (ASTM G102); needs i0 and the substrate
    # CR (mm/year) = K1 * (i_corr_uA_cm2 * EW) / density_g_cm3, K1 = 0.0032707148 (exact F)
    # EW and density come from the registry record the metal id resolved to (see docstring)
    ew = density = cr_mm_per_year = cr_mpy = None
    if preset is not None:
        ew = preset["ew"]  # g/eq
        density = preset["density_g_cm3"]  # g/cm3
        if i0_corr_ua_cm2 is not None:
            cr_mm_per_year = (ASTM_G102_K1_MM_G_UA_CM_YR * i0_corr_ua_cm2 * ew) / density
            cr_mpy = cr_mm_per_year * _MILS_PER_MM  # mils per year (1 mil = 0.0254 mm exactly)

    # Pitting Potential Breakdown Margin; needs ePit and e0
    delta_e_pit = pitting_status = None
    if e_pit_v is not None and e0_v is not None:
        delta_e_pit = e_pit_v - e0_v
        pitting_status = "Wide passivity margin (dE_pit >= 0.30 V, in-house threshold)"
        if delta_e_pit < 0.10:
            pitting_status = "Severe Chloride Pitting Susceptibility"
        elif delta_e_pit < 0.30:
            pitting_status = "Moderate Passivity / Pitting Risk"
        
    def _round_sig(value, digits=6):
        if value is None or value == 0 or not math.isfinite(value):
            return value
        return round(value, digits - 1 - int(math.floor(math.log10(abs(value)))))

    result = {
        "metalId": metal_id,
        "alloyId": None if preset is None else preset["registry_id"],
        "equivalentWeight_g_eq": ew,
        "density_g_cm3": density,
        "equivalentWeightNote": ("ASTM G102 EW computed in alloy_registry (corrosion domain) from the alloy "
                                 "composition: elements >= 1 wt % counted, mass fractions renormalised, "
                                 "in-house valences (no per-value citation)."),
        "sternGeary_B_V": None if b_val is None else round(b_val, 4),
        "polarizationResistance_Rp_Ohm_cm2": None if r_p_ohm_cm2 is None else round(r_p_ohm_cm2, 1),
        "corrosionRate_mm_yr": _round_sig(cr_mm_per_year),
        "corrosionRate_mpy": _round_sig(cr_mpy),
        "deltaE_pit_V": None if delta_e_pit is None else round(delta_e_pit, 3),
        "pittingAssessment": pitting_status,
    }
    if unavailable:
        groups_ok = (b_val is not None and r_p_ohm_cm2 is not None, cr_mm_per_year is not None,
                     delta_e_pit is not None)
        result["status"] = "partial" if any(groups_ok) else "unavailable"
        result["unavailable"] = unavailable
        result["unavailableReason"] = "Unavailable: " + "; ".join(unavailable.values()) + "."
        result["unavailableNote"] = ("Values reported as null are unavailable because a required input was not "
                                     "supplied; no default value was substituted.")
    return result



if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        print(json.dumps({
            "status": "ready",
            "engine": "MetalliX CPython Corrosion EIS & Kinetics Solver",
            "capabilities": [
                "Stern-Geary Polarization Resistance, ASTM G102 Penetration Rate & Pitting Margin"
            ]
        }))
        sys.exit(0)

    try:
        raw = sys.stdin.read()
        if not raw.strip():
            print(json.dumps({"error": "Empty input payload", "errorKind": "internal"}))
            sys.exit(1)

        data = json.loads(raw)
        action = data.get("action")
        start_time = time.perf_counter()

        if action == "corrosion_kinetics":
            metal_id = data.get("metalId")
            beta_a = data.get("betaA")
            beta_c = data.get("betaC")
            i0_corr = data.get("i0Corr_uA")
            e_pit = data.get("ePit")
            e0 = data.get("e0")
            res = simulate_corrosion_eis_and_kinetics(metal_id, beta_a, beta_c, i0_corr, e_pit, e0)

        else:
            res = {"error": f"Unknown action '{action}'"}

        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        res["pythonDurationMs"] = elapsed_ms
        # An error return (unknown action, insufficient points, ...) is reported as
        # success:false with the unchanged error message. Successful outputs are unchanged.
        res["success"] = "error" not in res
        if "error" not in res:
            # Phase 6a provenance (constants version and domain-data version)
            res["provenance"] = {
                "constantsVersion": physical_constants.CONSTANTS_VERSION,
                **_domain_data_provenance(),
                "gasConstantR_J_molK": R_GAS,
                "faraday_C_mol": F_FARADAY,
                "constantsNote": "Exact SI 2019 R = N_A*k and F = N_A*e at every site (Phase 6a "
                                 "value step); they replaced the per-site printings 8.314, "
                                 "8.31446, 8.314462618 / 96485.332, 96485.33, 96485.33212.",
            }
        print(json.dumps(res))
        
    except ValidationError as e:
        # Phase 6a envelope: invalid input (e.g. unknown alloy), not a solver failure (HTTP 422).
        print(json.dumps(validation_envelope(e)))
        sys.exit(2)
    except Exception as e:
        print(json.dumps({"error": str(e), "success": False, "errorKind": "internal"}))
        sys.exit(1)
