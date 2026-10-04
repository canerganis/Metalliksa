#!/usr/bin/env python3
"""
MetalliX Python JMAK & Diffusion Phase Transformation Kinetics Solver
Computes TTT (Time-Temperature-Transformation), CCT (Continuous Cooling Transformation via Scheil Additivity),
isothermal kinetics (Johnson-Mehl-Avrami-Kolmogorov), LSW precipitate coarsening, and CALPHAD vs. Kinetics gap.
"""

import sys
import json
import math
import time

import alloy_data_kinetics_uq_fatigue as _kinetics_data
import alloy_registry
import hardness_conversion_e140
import input_validation
import physical_constants

# Alloy kinetics data (Phase 6a structural migration, design step (a)): the numeric
# columns of the former local ALLOY_KINETICS_DB come from alloy_registry (domain
# "kinetics"), the labels from alloy_data_kinetics_uq_fatigue. Values and the
# "alloyMetadata" key order are unchanged. An unknown alloy name now raises
# input_validation.ValidationError (UNKNOWN_ALLOY) instead of silently using AISI 4140.
# Phase 6a value step (b): exact SI 2019 R = N_A*k (was the 4-significant-figure 8.314).
R_GAS = physical_constants.GAS_CONSTANT_R.value  # J/(mol*K), exact
ZERO_C_K = physical_constants.ZERO_CELSIUS_K.value

# predictedHardness_HV: ASTM E140 Table 1 HRC -> HV (hardness_conversion_e140), which applies
# to non-austenitic steels only. Of the six kinetics alloys these are the three steels
# (AISI 4140, AISI 4340, AISI D2); Inconel 718, Ti-6Al-4V and Al 7075 get HV None with
# STATUS_UNAVAILABLE_ALLOY_CLASS. It replaced the unsourced HV = 10.5 * HRC + 40.
E140_NON_AUSTENITIC_STEEL_IDS = frozenset({"aisi4140", "aisi4340", "aisid2"})


# The TTT/CCT/hardness model is a STEEL template (steel nose temperatures, Avrami constants,
# a CCT phase-fraction/HRC lookup by cooling-rate band, Pearlite/Bainite/Martensite labels).
# For the other alloy classes in the registry (Inconel 718, Ti-6Al-4V, Al 7075) none of it is
# a model of that alloy, so every such output is None with an explicit status and this reason.
STEEL_ONLY_REASON = "kinetics model is steel-only"
STATUS_UNAVAILABLE_STEEL_ONLY = "unavailable-kinetics-model-steel-only"
STATUS_UNAVAILABLE_PLACEHOLDER = "unavailable-registry-placeholder"
STATUS_REGISTRY_VALUE = "registry-screening-value"
STATUS_START_SCHEIL = "diffusional-start-scheil-additivity"
STATUS_START_FLOOR = "unavailable-ttt-incubation-floor-or-step-limited"
STATUS_START_ATHERMAL = "athermal-martensite-no-diffusional-start-above-ms"
STATUS_STEEL_LOOKUP = "steel-lookup-by-ccr-band-not-computed"
STATUS_STATIC_TEXT = "static-text-not-a-calphad-calculation"
STATUS_STEEL_ILLUSTRATIVE = "steel-illustrative-correlation"
NON_STEEL_MODEL_NOTE = (
    "The TTT/CCT numeric curves of non-steel alloys come from unsourced alloy-class constants "
    "(nose temperature, rate prefactor, Avrami exponent) and steel-template phase labels, not from a "
    "sourced model of this alloy, so they are not reported."
)
# TTT incubation law: t_start = max(TTT_INCUBATION_FLOOR_S, c * ...). The law has no Ae3
# asymptote, so over most of the range it falls below the floor and the reported time is the
# floor itself (audit D4: 32 of 40 TTT points for AISI 4140). Such a point is flagged floorHit.
TTT_INCUBATION_FLOOR_S = 0.001
TTT_FLOOR_NOTE = (
    "tStart_s is clamped to a 1 ms floor where the unsourced incubation law (no Ae3 asymptote) gives "
    "less; a point with floorHit true is that floor, not a model value, and its t50_s and tFinish_s "
    "are derived from it. A CCT start that the floor drives is reported unavailable."
)
CCT_FLOOR_ROW_REASON = (
    "the Scheil-additivity start is not a model result: the TTT incubation time at the start temperature "
    "is on the 1 ms floor or shorter than one integration step, so the start is set by the first "
    "admissible step below Ae3 (the incubation law has no Ae3 asymptote)"
)


def is_steel_alloy(alloy):
    """Whether the kinetics descriptor 'type' of this alloy is a steel (the only modelled class)."""
    return "Steel" in alloy["type"]


def placeholder_keys(registry_id):
    """Registry keys of this alloy that alloy_registry.KINETICS_PLACEHOLDERS flags as non-physical."""
    return sorted(key for alloy_id, key in alloy_registry.KINETICS_PLACEHOLDERS if alloy_id == registry_id)


def predicted_hardness_hv(hrc, registry_id):
    """(HV or None, status) for the solver's predicted HRC; see hardness_conversion_e140."""
    if registry_id not in E140_NON_AUSTENITIC_STEEL_IDS:
        return None, hardness_conversion_e140.STATUS_UNAVAILABLE_ALLOY_CLASS
    return hardness_conversion_e140.hrc_to_hv_non_austenitic_steel(hrc)


def resolve_kinetics_alloy(alloy_name):
    """Return (registry id, legacy table name, alloy metadata dict) for ``alloy_name``.

    The metadata dict has the legacy ALLOY_KINETICS_DB layout and key order.
    Raises ValidationError(UNKNOWN_ALLOY) for names without kinetics data.
    """
    record = input_validation.require_known_alloy(alloy_name, alloy_registry.DOMAIN_KINETICS, field="alloy")
    labels = _kinetics_data.KINETICS_DESCRIPTORS[record.id]
    metadata = {}
    for key in _kinetics_data.KINETICS_METADATA_KEYS:
        if key == "phases":
            metadata[key] = list(labels[key])
        elif key in _kinetics_data.KINETICS_DESCRIPTOR_KEYS:
            metadata[key] = labels[key]
        elif key == "composition_wt":
            metadata[key] = dict(record.value(key, alloy_registry.DOMAIN_KINETICS))
        else:
            metadata[key] = record.value(key, alloy_registry.DOMAIN_KINETICS)
    return record.id, _kinetics_data.KINETICS_LEGACY_NAMES[record.id], metadata


def provenance(registry_id):
    out = {
        "registryVersion": alloy_registry.REGISTRY_VERSION,
        "constantsVersion": physical_constants.CONSTANTS_VERSION,
        "registryAlloyId": registry_id,
        "gasConstantR_J_molK": R_GAS,
        "constantsNote": "Exact SI 2019 R = N_A*k (Phase 6a value step); it replaced the "
                         "4-significant-figure R = 8.314.",
    }
    out.update(_kinetics_data.provenance())
    out["hardnessConversion"] = dict(
        hardness_conversion_e140.provenance(),
        appliesToRegistryIds=sorted(E140_NON_AUSTENITIC_STEEL_IDS),
        appliedToThisAlloy=registry_id in E140_NON_AUSTENITIC_STEEL_IDS,
    )
    return out

def calculate_jmak_isothermal_kinetics(t_c, alloy_data, grain_size_um, phase_type="Pearlite"):
    """
    Computes JMAK time for 1% (start), 50%, and 99% (finish) transformation at isothermal temperature T.
    Using classic nucleation and growth driving force:
    tau(T) = A * (d_grain)^p * (Delta T)^(-m) * exp(Q / (R * T))
    """
    t_k = t_c + ZERO_C_K
    r_gas = R_GAS # J/(mol*K)
    
    t_eq = alloy_data["Ae3_C"] if phase_type in ["Ferrite", "Pearlite", "Equiaxed Alpha"] else (alloy_data["Ae1_C"] + 150.0)
    delta_t = t_eq - t_c
    
    if delta_t <= 5.0 or t_c < 100.0:
        return None # No driving force or frozen kinetics
        
    q_act = alloy_data["Q_diff_kJ_mol"] * 1000.0 # J/mol
    
    # Nose temperature calibration (C-curve)
    # At high T, delta_t is small -> slow nucleation.
    # At low T, exp(Q/RT) is huge -> slow diffusion.
    # Nose occurs where d(tau)/dT = 0, usually around 500-600 C for steels.
    
    if "Steel" in alloy_data["type"]:
        if phase_type == "Pearlite":
            t_nose = 560.0
            n_avrami = 3.0
            c_factor = 0.00045 * (grain_size_um / 25.0) ** 0.8
        elif phase_type == "Bainite":
            t_nose = 420.0
            n_avrami = 2.0
            c_factor = 0.00085 * (grain_size_um / 25.0) ** 0.5
        else: # Ferrite
            t_nose = 650.0
            n_avrami = 2.5
            c_factor = 0.00030 * (grain_size_um / 25.0) ** 1.0
    elif "Superalloy" in alloy_data["type"]:
        t_nose = 750.0
        n_avrami = 1.5
        c_factor = 0.0080
    elif "Titanium" in alloy_data["type"]:
        t_nose = 820.0
        n_avrami = 2.2
        c_factor = 0.00012
    else: # Al alloy
        t_nose = 320.0
        n_avrami = 2.0
        c_factor = 0.00015

    # Phenomenological incubation & transformation time
    # tau_nose is typically 0.5s to 50s depending on hardenability
    tau_geom = math.exp(((t_c - t_nose) / 85.0) ** 2)
    diff_term = math.exp((q_act / r_gas) * (1.0 / t_k - 1.0 / (t_nose + ZERO_C_K)))
    
    # Incubation time for 1% transformed (start)
    t_incubation_s = c_factor * tau_geom * diff_term * (100.0 / max(10.0, delta_t)) ** 1.2
    floor_hit = t_incubation_s < TTT_INCUBATION_FLOOR_S
    t_start_s = max(TTT_INCUBATION_FLOOR_S, t_incubation_s)
    
    # 50% transformed time: t_50 = t_start * [ ln(2) / -ln(0.99) ]^(1/n)
    ratio_50 = (math.log(2.0) / -math.log(0.99)) ** (1.0 / n_avrami)
    t_50_s = t_start_s * ratio_50
    
    # 99% transformed time: t_99 = t_start * [ -ln(0.01) / -ln(0.99) ]^(1/n)
    ratio_99 = (-math.log(0.01) / -math.log(0.99)) ** (1.0 / n_avrami)
    t_finish_s = t_start_s * ratio_99
    
    return {
        "temperature_C": t_c,
        "phase": phase_type,
        "tStart_s": round(t_start_s, 4),
        "t50_s": round(t_50_s, 4),
        "tFinish_s": round(t_finish_s, 4),
        "avramiExponent_n": n_avrami,
        "drivingForce_DeltaT_C": round(delta_t, 1),
        # True: tStart_s is the 1 ms floor (TTT_INCUBATION_FLOOR_S), not the law's value.
        "floorHit": floor_hit,
    }

def solve_phase_transformation_kinetics(alloy_name="AISI 4140", cooling_rate_c_s=10.0,
                                       grain_size_um=25.0, aust_temp_c=860.0,
                                       aging_time_h=8.0, aging_temp_c=720.0):
    """
    Solves TTT curves, CCT cooling trajectory via Scheil additivity, room temp phase constituents, and LSW coarsening.

    The TTT/CCT/phase-fraction/hardness model is a steel template: for alloys whose registry class is
    not a steel those outputs are None with an explicit status and the reason STEEL_ONLY_REASON
    (see ``kineticsModel``). Registry parameters flagged in alloy_registry.KINETICS_PLACEHOLDERS are
    never reported as results.
    """
    start_time = time.perf_counter()

    registry_id, legacy_name, alloy = resolve_kinetics_alloy(alloy_name)
    steel = is_steel_alloy(alloy)
    placeholders = placeholder_keys(registry_id)

    ae3 = alloy["Ae3_C"]
    ae1 = alloy["Ae1_C"]
    ms = alloy["Ms_C"]
    mf = alloy["Mf_C"]
    ccr = alloy["critical_cooling_rate_C_s"]

    # 1. GENERATE ISOTHERMAL TTT DIAGRAM CURVES (steel template only)
    ttt_curves = [] if steel else None
    temp_steps = 45
    t_min = max(50.0, ms - 50.0)
    t_max = ae3 - 5.0

    for i in range(temp_steps + 1 if steel else 0):
        tc = t_min + (t_max - t_min) * (i / temp_steps)

        # Decide primary active transformation regime
        if tc >= ae1 - 30.0:
            pt = "Ferrite"
        elif tc >= 480.0:
            pt = "Pearlite"
        elif tc >= ms:
            pt = "Bainite"
        else:
            pt = "Sub-Ms"

        if pt != "Sub-Ms":
            res = calculate_jmak_isothermal_kinetics(tc, alloy, grain_size_um, pt)
            if res and res["tStart_s"] < 1.0e6:
                ttt_curves.append(res)

    if steel:
        floor_hits = sum(1 for point in ttt_curves if point["floorHit"])
        ttt_floor = {
            "status": "floor-hit-points-flagged" if floor_hits else "no-floor-hit-points",
            "floorValue_s": TTT_INCUBATION_FLOOR_S,
            "pointCount": len(ttt_curves),
            "floorHitCount": floor_hits,
            "note": TTT_FLOOR_NOTE,
        }
    else:
        ttt_floor = {
            "status": STATUS_UNAVAILABLE_STEEL_ONLY,
            "floorValue_s": TTT_INCUBATION_FLOOR_S,
            "pointCount": None,
            "floorHitCount": None,
            "note": STEEL_ONLY_REASON + ": " + NON_STEEL_MODEL_NOTE,
        }

    # 2. CONTINUOUS COOLING TRANSFORMATION (CCT) & SCHEIL ADDITIVITY
    # Scheil integral: Sum( dt / tau(T) ) >= 1.0
    # Cooling path: T(t) = T_aust - cooling_rate * t
    cooling_rates_to_test = [0.05, 0.2, 1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 500.0, 2000.0]
    cct_transformation_map = []

    for cr in cooling_rates_to_test:
        if not steel:
            cct_transformation_map.append({
                "coolingRate_C_s": cr,
                "transformedStartTemp_C": None,
                "transformedStartTime_s": None,
                "primaryMicrostructure": None,
                "phaseFractions": {
                    "Martensite_pct": None,
                    "Bainite_pct": None,
                    "Pearlite_Ferrite_pct": None,
                    "RetainedAustenite_pct": None
                },
                "predictedHardness_HRC": None,
                "predictedHardness_HV": None,
                "predictedHardness_HV_status": hardness_conversion_e140.STATUS_UNAVAILABLE_ALLOY_CLASS,
                "transformedStart_status": STATUS_UNAVAILABLE_STEEL_ONLY,
                "phaseFractions_status": STATUS_UNAVAILABLE_STEEL_ONLY,
                "predictedHardness_HRC_status": STATUS_UNAVAILABLE_STEEL_ONLY,
                "unavailableReason": STEEL_ONLY_REASON,
            })
            continue

        curr_t = aust_temp_c
        dt = 0.05 / max(1.0, cr * 0.01)
        cum_time = 0.0
        scheil_sum = 0.0
        floor_sum = 0.0  # part of scheil_sum that comes from floor-hit incubation times
        crossing_step_sum = 0.0  # contribution of the step that reached scheil_sum >= 1
        trans_start_temp = None
        trans_start_time = None
        trans_phase = "Martensite"

        while curr_t > ms and curr_t > 50.0 and cum_time < 50000.0:
            cum_time += dt
            curr_t = aust_temp_c - cr * cum_time
            if curr_t < ms:
                break

            pt = "Pearlite" if curr_t > 520.0 else "Bainite"
            pt_kin = calculate_jmak_isothermal_kinetics(curr_t, alloy, grain_size_um, pt)
            if pt_kin:
                tau_start = pt_kin["tStart_s"]
                step_sum = dt / max(1e-4, tau_start)
                scheil_sum += step_sum
                if pt_kin["floorHit"]:
                    floor_sum += step_sum
                if scheil_sum >= 1.0 and trans_start_temp is None:
                    crossing_step_sum = step_sum
                    trans_start_temp = curr_t
                    trans_start_time = cum_time
                    trans_phase = pt
                    break

        # A diffusional start is not reported when it is driven by the 1 ms clamp (the Scheil sum
        # includes floor-hit incubation times) or when one integration step alone reaches the sum
        # (incubation time shorter than the step, i.e. at or near the floor): the start is then the
        # first admissible step below Ae3, not an accumulated incubation (audit D4: "Pearlite
        # starts at ~770 C at every cooling rate"). The model itself is not changed.
        floor_driven = trans_start_temp is not None and (floor_sum > 0.0 or crossing_step_sum >= 1.0)
        if trans_start_temp is None:
            start_status = STATUS_START_ATHERMAL
            row_start_temp = ms
            row_start_time = round((aust_temp_c - ms)/cr, 2)
            primary = "Martensite (Athermal)"
            start_reason = None
        elif floor_driven:
            start_status = STATUS_START_FLOOR
            row_start_temp = None
            row_start_time = None
            primary = None
            start_reason = CCT_FLOOR_ROW_REASON
        else:
            start_status = STATUS_START_SCHEIL
            row_start_temp = round(trans_start_temp, 1)
            row_start_time = round(trans_start_time, 2)
            primary = trans_phase
            start_reason = None

        # Calculate phase fractions at room temperature for this cooling rate
        if cr >= ccr * 1.5:
            pct_martensite = 98.0
            pct_bainite = 1.0
            pct_pearlite = 0.5
            pct_austenite = 0.5
            hard_hrc = 58.0 if "4140" in legacy_name or "4340" in legacy_name else 64.0
        elif cr >= ccr * 0.7:
            pct_martensite = 85.0
            pct_bainite = 12.0
            pct_pearlite = 2.0
            pct_austenite = 1.0
            hard_hrc = 54.0
        elif cr >= ccr * 0.15:
            pct_martensite = 25.0
            pct_bainite = 55.0
            pct_pearlite = 18.0
            pct_austenite = 2.0
            hard_hrc = 42.0
        elif cr >= 0.5:
            pct_martensite = 0.0
            pct_bainite = 20.0
            pct_pearlite = 78.0
            pct_austenite = 2.0
            hard_hrc = 28.0
        else: # Furnace slow cool (Anneal)
            pct_martensite = 0.0
            pct_bainite = 0.0
            pct_pearlite = 98.5
            pct_austenite = 1.5
            hard_hrc = 18.0

        hard_hv, hard_hv_status = predicted_hardness_hv(hard_hrc, registry_id)
        cct_transformation_map.append({
            "coolingRate_C_s": cr,
            "transformedStartTemp_C": row_start_temp,
            "transformedStartTime_s": row_start_time,
            "primaryMicrostructure": primary,
            "phaseFractions": {
                "Martensite_pct": pct_martensite,
                "Bainite_pct": pct_bainite,
                "Pearlite_Ferrite_pct": pct_pearlite,
                "RetainedAustenite_pct": pct_austenite
            },
            "predictedHardness_HRC": round(hard_hrc, 1),
            # ASTM E140 Table 1 estimate (non-austenitic steels, HRC 20-68), else None.
            "predictedHardness_HV": hard_hv,
            "predictedHardness_HV_status": hard_hv_status,
            # The fractions and HRC are a lookup by cooling-rate band (multiples of the registry
            # critical cooling rate), not the result of the Scheil path above.
            "transformedStart_status": start_status,
            "phaseFractions_status": STATUS_STEEL_LOOKUP,
            "predictedHardness_HRC_status": STATUS_STEEL_LOOKUP,
            "unavailableReason": start_reason,
        })

    # 3. CURRENT EVALUATION AT USER-SELECTED COOLING RATE
    user_cr = float(cooling_rate_c_s)
    # Koistinen-Marburger Martensite Kinetics: f_M = 1 - exp( -alpha_KM * (Ms - T) )
    alpha_km = 0.011 # 1/K
    if steel:
        martensite_fraction_at_rt = max(0.0, 1.0 - math.exp(-alpha_km * max(0.0, ms - 25.0))) if user_cr >= ccr * 0.8 else (user_cr / ccr) * 0.95
        martensite_fraction_at_rt = min(0.99, max(0.0, martensite_fraction_at_rt))

    # 4. LIFSHITZ-SLYOZOV-WAGNER (LSW) PRECIPITATE COARSENING
    # r^3(t) - r_0^3 = K_LSW * t
    # K_LSW = (8 * gamma * D * C_e * Vm^2) / (9 * R * T)   [Lifshitz & Slyozov 1961, Wagner 1961]
    # Units (SI): gamma J/m^2, D m^2/s, Vm m^3/mol, R*T J/mol and C_e the equilibrium solute
    # concentration in mol/m^3 give K in m^3/s. The solver holds C_e as a mole fraction x_e, so
    # C_e = x_e / Vm (before the fix x_e was used as C_e: K was too small by 1/Vm = 9.1e4).
    # gamma, x_e, Vm and D0 are generic constants shared by every alloy (only Q is per alloy).
    aging_t_k = aging_temp_c + ZERO_C_K
    q_precip = alloy["Q_diff_kJ_mol"] * 1000.0
    gamma_interface = 0.045   # J/m^2
    x_e = 0.02                # mole fraction of the rate-limiting solute in equilibrium
    v_molar = 1.1e-5          # m^3/mol
    c_e_mol_m3 = x_e / v_molar
    d_diff = 1.2e-4 * math.exp(-q_precip / (R_GAS * aging_t_k))
    k_lsw = (8.0 * gamma_interface * d_diff * c_e_mol_m3 * (v_molar ** 2)) / (9.0 * R_GAS * aging_t_k) # m^3/s
    k_lsw_nm3_h = k_lsw * (1e9 ** 3) * 3600.0 # nm^3/h

    r0_nm = 1.5 # Initial nucleus radius
    aging_time_steps = [0.1, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 24.0, 48.0, 100.0]
    lsw_coarsening_profile = []

    for t_h in aging_time_steps:
        r_cube = (r0_nm ** 3) + k_lsw_nm3_h * t_h
        r_mean_nm = r_cube ** (1.0 / 3.0)

        # Orowan looping strengthening contribution (MPa) vs Cutting
        # Cutting: Delta sigma ~ sqrt(r)
        # Orowan looping: Delta sigma ~ 1 / r
        # Peak strength occurs around r_crit ~ 6-12 nm
        r_crit_nm = 9.0
        if r_mean_nm <= r_crit_nm:
            orowan_boost_mpa = 280.0 * math.sqrt(r_mean_nm / r_crit_nm)
            regime = "Weak-Pair / Strong-Pair Cutting"
        else:
            orowan_boost_mpa = 280.0 * (r_crit_nm / r_mean_nm)
            regime = "Orowan Dislocation Looping (Over-aged)"

        lsw_coarsening_profile.append({
            "agingTime_h": t_h,
            "meanRadius_nm": round(r_mean_nm, 2),
            "precipitationHardening_MPa": round(orowan_boost_mpa, 1),
            "strengtheningMechanism": regime
        })

    # 5. CALPHAD (Equilibrium) vs KINETICS (Non-Equilibrium) Gap Metrics
    if steel:
        calphad_vs_kinetics_gap = {
            "equilibriumPrediction": {
                "stablePhasesAtRT": "Ferrite + Cementite / Equilibrium intermetallics",
                "martensiteFraction": "0.0% (Thermodynamically Forbidden in Equilibrium)",
                "soluteSupersaturation": "Near Zero (<0.01 wt% C in ferrite)",
                "status": STATUS_STATIC_TEXT,
                "reason": "fixed steel text; no equilibrium (CALPHAD) calculation is performed here",
            },
            "kineticRealityAtSelectedCooling": {
                "coolingRate_C_s": user_cr,
                "criticalCoolingRate_C_s": ccr,
                "isSuppressedEquilibrium": user_cr >= 2.0,
                "predictedMartensite_pct": round(martensite_fraction_at_rt * 100.0, 1),
                "diffusionSuppressionIndex": round(min(1.0, user_cr / max(1e-2, ccr)), 3),
                "verdict": "Full Martensitic / Metastable Quench" if user_cr >= ccr else (
                    "Mixed Microstructure (Martensite + Bainite)" if user_cr >= ccr * 0.2 else "Diffusional Equilibrium Decomposition"
                ),
                "status": STATUS_STEEL_ILLUSTRATIVE,
                "reason": "steel template with unsourced registry critical cooling rate; screening only",
            }
        }
    else:
        calphad_vs_kinetics_gap = {
            "equilibriumPrediction": {
                "stablePhasesAtRT": None,
                "martensiteFraction": None,
                "soluteSupersaturation": None,
                "status": STATUS_UNAVAILABLE_STEEL_ONLY,
                "reason": STEEL_ONLY_REASON,
            },
            "kineticRealityAtSelectedCooling": {
                "coolingRate_C_s": user_cr,
                "criticalCoolingRate_C_s": None,
                "isSuppressedEquilibrium": None,
                "predictedMartensite_pct": None,
                "diffusionSuppressionIndex": None,
                "verdict": None,
                "status": STATUS_UNAVAILABLE_STEEL_ONLY,
                "reason": STEEL_ONLY_REASON,
            }
        }

    # Registry placeholders (alloy_registry.KINETICS_PLACEHOLDERS) are never reported as results.
    alloy_out = dict(alloy)
    for key in placeholders:
        alloy_out[key] = None

    def critical_status(key):
        return STATUS_UNAVAILABLE_PLACEHOLDER if key in placeholders else STATUS_REGISTRY_VALUE

    kinetics_model = {
        "status": "available" if steel else "unavailable",
        "reason": None if steel else STEEL_ONLY_REASON,
        "scope": "steel-only",
        "registryAlloyId": registry_id,
        "illustrativeOnly": True,
        "note": (
            "Steel template with unsourced class constants: the TTT nose/prefactor/Avrami constants are "
            "not fitted to published data, and the CCT phase fractions and HRC are a lookup by "
            "cooling-rate band, not computed." if steel else
            STEEL_ONLY_REASON + ": " + NON_STEEL_MODEL_NOTE
        ),
        "placeholderParameters": placeholders,
        "lswPrecipitateCoarsening": {
            "status": "generic-constants-illustrative",
            "note": "K_LSW uses generic gamma, equilibrium concentration, molar volume and D0 shared by every "
                    "alloy (only the activation energy is per alloy); the strengthening column is an "
                    "unsourced screening curve.",
        },
    }

    compute_time_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    return {
        "success": True,
        "engine": "MetalliX-Python-HPC-JMAK-Kinetics-v3.10",
        "computeTimeMs": compute_time_ms,
        "alloy": alloy_name,
        "alloyMetadata": alloy_out,
        "inputParameters": {
            "selectedCoolingRate_C_s": user_cr,
            "austSolutionTemp_C": aust_temp_c,
            "priorGrainSize_um": grain_size_um,
            "agingTemp_C": aging_temp_c,
            "agingTime_h": aging_time_h
        },
        "criticalTransformationTemperatures": {
            "Ae3_BetaTransus_GammaSolvus_C": ae3,
            "Ae1_C": ae1,
            "Ms_C": None if "Ms_C" in placeholders else ms,
            "Mf_C": None if "Mf_C" in placeholders else mf,
            "CriticalCoolingRate_CCR_C_s": ccr if steel else None,
            "Ms_C_status": critical_status("Ms_C"),
            "Mf_C_status": critical_status("Mf_C"),
            "CriticalCoolingRate_CCR_status": STATUS_REGISTRY_VALUE if steel else STATUS_UNAVAILABLE_STEEL_ONLY,
        },
        "tttIsothermalCurves": ttt_curves,
        "cctContinuousCoolingMap": cct_transformation_map,
        "lswPrecipitateCoarsening": lsw_coarsening_profile,
        "calphadVsKineticsGap": calphad_vs_kinetics_gap,
        "kineticsModel": kinetics_model,
        "tttIncubationFloor": ttt_floor,
    }

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        print(json.dumps({
            "status": "ready",
            "engine": "MetalliX Python JMAK & Diffusion Transformation Kinetics Solver",
            "capabilities": ["JMAK TTT C-Curves (1%, 50%, 99%)", "Scheil Additivity CCT Map", "Koistinen-Marburger Martensite", "LSW Precipitate Coarsening", "CALPHAD vs Kinetics Gap"]
        }))
        sys.exit(0)
        
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            print(json.dumps({"error": "Empty stdin payload", "errorKind": "internal"}))
            sys.exit(1)
            
        data = json.loads(raw_input)
        mat = data.get("alloy", "AISI 4140")
        cr = data.get("coolingRate_C_s", 10.0)
        d_grain = data.get("grainSize_um", 25.0)
        t_aust = data.get("austTemp_C", 860.0)
        t_aging = data.get("agingTemp_C", 720.0)
        time_aging = data.get("agingTime_h", 8.0)
        
        result = solve_phase_transformation_kinetics(mat, cr, d_grain, t_aust, time_aging, t_aging)
        result["provenance"] = provenance(resolve_kinetics_alloy(mat)[0])
        print(json.dumps(result))
    except input_validation.ValidationError as err:
        print(json.dumps(input_validation.validation_envelope(err)))
        sys.exit(2)
    except Exception as e:
        print(json.dumps({"error": str(e), "errorKind": "internal"}))
        sys.exit(1)
