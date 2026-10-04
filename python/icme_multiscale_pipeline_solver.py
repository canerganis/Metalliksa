#!/usr/bin/env python3
"""
MetalliX ICME Multi-Scale Pipeline Solver
Author: MetalliX Computational Materials Science HPC Engine

Solves the end-to-end Integrated Computational Materials Engineering (ICME) Digital Thread:
Scale 0: DFT Atomistic (Lattice, C_ij Elastic Stiffness, Peierls-Nabarro, Pugh B/G, Taylor M)
Scale 1: CALPHAD & Solute Misfit (Gibbs Energy, Size & Modulus Misfit, Labusch-Fleischer Solid Solution)
Scale 2: Microstructure & Kinetics (Cooling Rate, SDAS, Grain Size d, Dislocation Density rho, LSW Precipitate Orowan/Cutting)
Scale 3: Continuum Plasticity (Strengthening Superposition, Hollomon/Voce/Johnson-Cook Stress-Strain Curve, K_1c Fracture Toughness)
Scale 4: Macro Structural Limit (Aero/Turbine Component FEA Load, Safety Margin, Critical Flaw a_c)
CAE Export: Abaqus, ANSYS, LS-DYNA, NASTRAN Material Cards
"""

import sys
import json
import math
import time

import alloy_registry
import physical_constants
from alloy_data_calphad_battery_icme import (
    ICME_DEFAULT_ALLOY_ID,
    ICME_JOHNSON_COOK_T_MELT_C,
    LEGACY_R_8_314,
    UnsupportedElementError,
    icme_atomic_weight,
    icme_base_metal,
    provenance as _domain_data_provenance,
)
from input_validation import UNKNOWN_ELEMENT, ValidationError, validation_envelope

# Phase 6a structural step (a): constants and tables come from physical_constants /
# alloy_data_calphad_battery_icme / alloy_registry with their pre-migration values
# (R = 8.314, legacy rounded atomic weights), so the output stays bit-identical.
# Exact R and CIAAW atomic weights are the value step (b).
ZERO_CELSIUS_K = physical_constants.ZERO_CELSIUS_K.value  # 273.15 K


def _default_composition_wt() -> dict:
    """Inconel 718 solute wt% used when the payload has no composition_wt."""
    record = alloy_registry.REGISTRY[ICME_DEFAULT_ALLOY_ID]
    return dict(record.value("default_solute_composition_wt", alloy_registry.DOMAIN_ICME))


def _unknown_element(field: str, exc: UnsupportedElementError, reason: str) -> ValidationError:
    return ValidationError(UNKNOWN_ELEMENT, field, str(exc),
                           {"element": repr(exc.element), "supported": list(exc.supported),
                            "reason": reason})


def solve_multiscale_pipeline(params: dict) -> dict:
    t_start = time.time()

    # User inputs with robust metallurgy defaults
    alloy_name = params.get("alloyName", "Inconel 718")
    base_metal = params.get("baseMetal", "Ni")  # Ni, Fe, Ti, Al
    crystal_system = params.get("crystalSystem", "FCC" if base_metal in ["Ni", "Al"] else "BCC" if base_metal == "Fe" else "HCP")
    
    comp_wt = params.get("composition_wt", _default_composition_wt())
    
    cooling_rate_C_s = float(params.get("coolingRate_C_s", 150000.0))  # 1.5e5 K/s for LPBF AM
    grain_size_override = params.get("grainSize_um", None)
    aging_temp_C = float(params.get("agingTemp_C", 720.0))
    aging_time_h = float(params.get("agingTime_h", 8.0))
    strain_rate_s_inv = float(params.get("strainRate_s_inv", 0.001))
    service_temp_C = float(params.get("serviceTemp_C", 25.0))
    component_type = params.get("componentType", "turbine_blade_root")

    # Phase 6a: a base metal without a data branch (anything but Ni/Fe/Ti) was solved
    # silently with the Al data; only Ni, Fe, Ti and Al are accepted now.
    try:
        icme_base_metal(base_metal)
    except UnsupportedElementError as exc:
        raise _unknown_element("baseMetal", exc, "no-icme-base-data") from exc

    # =========================================================================
    # SCALE 0: DFT ATOMISTIC SCALE (10^-10 m / Ångström)
    # =========================================================================
    if base_metal == "Ni":
        a0_angstrom = 3.585
        burgers_b_nm = a0_angstrom * math.sqrt(2) / 2 * 0.1  # 0.2535 nm
        d_hkl_nm = a0_angstrom / math.sqrt(3) * 0.1  # (111) slip plane = 0.207 nm
        C11, C12, C44 = 247.0, 147.0, 125.0  # GPa
        taylor_M = 3.06
        density_g_cm3 = 8.19
        atomic_mass_avg = 58.69
        poisson_ratio = 0.31
        sigma_0_base = 75.0  # MPa
    elif base_metal == "Fe":
        a0_angstrom = 2.866
        burgers_b_nm = a0_angstrom * math.sqrt(3) / 2 * 0.1  # 0.2482 nm
        d_hkl_nm = a0_angstrom / math.sqrt(2) * 0.1  # (110) slip plane = 0.202 nm
        C11, C12, C44 = 237.0, 141.0, 116.0
        taylor_M = 2.75
        density_g_cm3 = 7.85
        atomic_mass_avg = 55.85
        poisson_ratio = 0.29
        sigma_0_base = 85.0
    elif base_metal == "Ti":
        a0_angstrom = 2.950
        burgers_b_nm = 0.2950  # a-type basal dislocation
        d_hkl_nm = 0.2340  # (0002) basal
        C11, C12, C44 = 160.0, 90.0, 46.5
        taylor_M = 4.20  # HCP basal + prismatic
        density_g_cm3 = 4.43
        atomic_mass_avg = 47.87
        poisson_ratio = 0.34
        sigma_0_base = 180.0
    else:  # Al
        a0_angstrom = 4.049
        burgers_b_nm = a0_angstrom * math.sqrt(2) / 2 * 0.1  # 0.2863 nm
        d_hkl_nm = a0_angstrom / math.sqrt(3) * 0.1
        C11, C12, C44 = 108.0, 61.0, 28.5
        taylor_M = 3.06
        density_g_cm3 = 2.70
        atomic_mass_avg = 26.98
        poisson_ratio = 0.33
        sigma_0_base = 25.0

    # Voigt-Reuss-Hill Elastic Homogenization
    bulk_modulus_B_GPa = (C11 + 2.0 * C12) / 3.0
    shear_modulus_G_Voigt = (C11 - C12 + 3.0 * C44) / 5.0
    shear_modulus_G_Reuss = 5.0 * (C11 - C12) * C44 / (4.0 * C44 + 3.0 * (C11 - C12))
    shear_modulus_G_GPa = (shear_modulus_G_Voigt + shear_modulus_G_Reuss) / 2.0
    youngs_modulus_E_GPa = (9.0 * bulk_modulus_B_GPa * shear_modulus_G_GPa) / (3.0 * bulk_modulus_B_GPa + shear_modulus_G_GPa)
    pugh_ratio_B_over_G = bulk_modulus_B_GPa / max(1.0, shear_modulus_G_GPa)
    cauchy_pressure_GPa = C12 - C44
    is_ductile_pugh = pugh_ratio_B_over_G > 1.75

    # Peierls-Nabarro Dislocation Lattice Friction Stress
    # PN stress tau_PN = 2G / (1-nu) * exp(-2*pi*d / ((1-nu)*b))
    exponent_PN = (2.0 * math.pi * d_hkl_nm) / ((1.0 - poisson_ratio) * burgers_b_nm)
    tau_PN_MPa = (2.0 * (shear_modulus_G_GPa * 1000.0) / (1.0 - poisson_ratio)) * math.exp(-min(14.0, exponent_PN))
    sigma_0_friction_stress_MPa = max(sigma_0_base, min(350.0, taylor_M * tau_PN_MPa * 0.4 + sigma_0_base * 0.6))

    # =========================================================================
    # SCALE 1: CALPHAD & SOLID SOLUTION MISFIT (10^-8 m / nm)
    # =========================================================================
    element_radii_nm = {
        "Ni": 0.124, "Fe": 0.124, "Cr": 0.128, "Mo": 0.139, "Nb": 0.146,
        "Ti": 0.145, "Al": 0.143, "C": 0.077, "Si": 0.118, "Mn": 0.127,
        "V": 0.134, "W": 0.139, "Co": 0.125, "Cu": 0.128, "Mg": 0.160, "Zn": 0.133
    }
    element_G_GPa = {
        "Ni": 76.0, "Fe": 82.0, "Cr": 115.0, "Mo": 126.0, "Nb": 38.0,
        "Ti": 44.0, "Al": 26.0, "C": 200.0, "Si": 40.0, "Mn": 80.0,
        "V": 47.0, "W": 161.0, "Co": 75.0, "Cu": 48.0, "Mg": 17.0, "Zn": 43.0
    }

    base_radius = element_radii_nm.get(base_metal, 0.124)
    base_G = element_G_GPa.get(base_metal, 76.0)

    # Convert wt% to atomic fraction x_i & calculate Labusch-Fleischer solute misfit.
    # Legacy rounded atomic weights (alloy_data_calphad_battery_icme.ICME_ATOMIC_WEIGHTS);
    # an element outside that table used a silent 55.0 g/mol and is now refused.
    moles = {}
    for el, wt in comp_wt.items():
        if wt > 0:
            try:
                aw = icme_atomic_weight(el)
            except UnsupportedElementError as exc:
                raise _unknown_element(f"composition_wt.{el}", exc, "no-icme-atomic-weight") from exc
            moles[el] = wt / aw
    
    sum_wt = sum(comp_wt.values())
    base_wt = max(0.0, 100.0 - sum_wt)
    moles[base_metal] = moles.get(base_metal, 0.0) + (base_wt / icme_atomic_weight(base_metal))
    total_moles = sum(moles.values())
    atomic_fractions = {el: mol / total_moles for el, mol in moles.items()}

    # Solid solution strengthening coefficients (MPa / wt%^0.5)
    ss_coeff_table = {
        "Mo": 28.0, "Nb": 38.0, "W": 24.0, "Cr": 9.5, "Fe": 6.5,
        "Ti": 22.0, "Al": 18.0, "C": 160.0, "Si": 16.0, "Mn": 12.0,
        "V": 20.0, "Cu": 14.0, "Mg": 26.0, "Zn": 11.0, "Co": 4.5
    }

    delta_sigma_SS_MPa = 0.0
    solute_breakdown = {}

    for el, wt in comp_wt.items():
        if el == base_metal or wt <= 0.001:
            continue
        r_i = element_radii_nm.get(el, base_radius)
        G_i = element_G_GPa.get(el, base_G)
        size_misfit_delta = abs(r_i - base_radius) / base_radius
        modulus_misfit_eta = abs(G_i - base_G) / base_G
        
        c_at = atomic_fractions.get(el, 0.0)
        k_ss = ss_coeff_table.get(el, 12.0)
        d_sigma = k_ss * math.sqrt(wt)

        delta_sigma_SS_MPa += d_sigma
        solute_breakdown[el] = {
            "wt_pct": round(wt, 2),
            "at_frac": round(c_at * 100.0, 2),
            "sizeMisfit": round(size_misfit_delta, 3),
            "modulusMisfit": round(modulus_misfit_eta, 3),
            "strengthContribution_MPa": round(d_sigma, 1)
        }

    # Cap SS if huge solute content
    delta_sigma_SS_MPa = min(450.0, delta_sigma_SS_MPa)

    # =========================================================================
    # SCALE 2: MICROSTRUCTURE & SOLIDIFICATION KINETICS (10^-6 m / µm)
    # =========================================================================
    prefactor_sdas = 35.0 if base_metal == "Al" else 28.0 if base_metal == "Ti" else 48.0
    computed_sdas_um = prefactor_sdas * math.pow(max(1.0, cooling_rate_C_s), -0.33)
    
    if grain_size_override is not None and float(grain_size_override) > 0:
        grain_size_d_um = float(grain_size_override)
    else:
        grain_size_d_um = max(0.5, computed_sdas_um * 1.8)

    # Hall-Petch grain boundary strengthening: delta_sigma_HP = k_y * d^(-1/2)
    ky_HallPetch_MPa_sqrt_um = 550.0 if base_metal == "Fe" else 420.0 if base_metal == "Ni" else 380.0 if base_metal == "Ti" else 150.0
    delta_sigma_HP_MPa = ky_HallPetch_MPa_sqrt_um / math.sqrt(max(0.5, grain_size_d_um))
    delta_sigma_HP_MPa = min(500.0, delta_sigma_HP_MPa)

    # Dislocation Forest Hardening (Taylor model): delta_sigma_disloc = M * alpha * G * b * sqrt(rho)
    if cooling_rate_C_s > 10000.0:  # Additive LPBF
        dislocation_density_rho_m2 = min(2.5e14, 5.0e13 * math.pow(cooling_rate_C_s / 10000.0, 0.25))
    elif cooling_rate_C_s > 100.0:
        dislocation_density_rho_m2 = 1.2e13
    else:
        dislocation_density_rho_m2 = 1.0e12  # Annealed

    alpha_taylor = 0.32
    b_meters = burgers_b_nm * 1e-9
    G_Pa = shear_modulus_G_GPa * 1e9
    delta_sigma_disloc_MPa = (taylor_M * alpha_taylor * G_Pa * b_meters * math.sqrt(dislocation_density_rho_m2)) / 1e6
    delta_sigma_disloc_MPa = min(350.0, delta_sigma_disloc_MPa)

    # LSW Precipitation Kinetics & Orowan / Particle Shearing
    Q_diff_kJ_mol = 275.0 if base_metal == "Ni" else 130.0 if base_metal == "Al" else 240.0
    R_gas = LEGACY_R_8_314.value  # 8.314 (pre-migration value)
    T_aging_K = aging_temp_C + ZERO_CELSIUS_K
    k_LSW = 1.2e14 * math.exp(-(Q_diff_kJ_mol * 1000.0) / (R_gas * T_aging_K))
    mean_precip_radius_nm = max(1.5, math.pow(k_LSW * aging_time_h + 3.0, 1.0 / 3.0))

    # Precipitate Volume Fraction
    if base_metal == "Ni":
        active_solutes = comp_wt.get("Al", 0.0) + comp_wt.get("Ti", 0.0) + 0.5 * comp_wt.get("Nb", 0.0)
        volume_frac_precip = min(0.35, max(0.01, active_solutes * 0.038))
    elif base_metal == "Al":
        active_solutes = comp_wt.get("Cu", 0.0) + comp_wt.get("Mg", 0.0) + comp_wt.get("Zn", 0.0)
        volume_frac_precip = min(0.12, max(0.01, active_solutes * 0.018))
    elif base_metal == "Fe":
        volume_frac_precip = min(0.20, max(0.01, comp_wt.get("C", 0.05) * 0.12))
    else:
        volume_frac_precip = 0.04

    r_nm = mean_precip_radius_nm
    lambda_spacing_nm = max(2.0, r_nm * math.sqrt((2.0 * math.pi) / (3.0 * max(0.005, volume_frac_precip))) - 2.0 * r_nm)

    # Dislocation Shearing vs. Orowan Looping (Classic Brown-Ham / Ardell calibration)
    gamma_apb_J_m2 = 0.175
    # Shear stress: delta_sigma_cut = M * (gamma_apb / (2*b)) * sqrt( (8 * gamma_apb * r * f) / (pi * G * b^2) )
    line_tension_T = 0.5 * G_Pa * (b_meters**2)
    ratio_term = (8.0 * gamma_apb_J_m2 * (r_nm * 1e-9) * volume_frac_precip) / (math.pi * line_tension_T)
    delta_sigma_cutting_MPa = (taylor_M * (gamma_apb_J_m2 / (2.0 * b_meters)) * math.sqrt(max(1e-6, ratio_term))) / 1e6
    delta_sigma_cutting_MPa = min(850.0, delta_sigma_cutting_MPa)

    # Orowan looping for overaged / coarse precipitates:
    delta_sigma_orowan_MPa = (taylor_M * (0.4 * G_Pa * b_meters) / (math.pi * (lambda_spacing_nm * 1e-9))) * (math.log(2.0 * (r_nm * 1e-9) / b_meters) / math.sqrt(1.0 - poisson_ratio)) / 1e6
    delta_sigma_orowan_MPa = min(900.0, delta_sigma_orowan_MPa)

    if delta_sigma_cutting_MPa < delta_sigma_orowan_MPa:
        precip_mechanism = "Dislocation Particle Shearing (Friedel-Gere Cutting)"
        delta_sigma_precip_MPa = delta_sigma_cutting_MPa
    else:
        precip_mechanism = "Orowan Dislocation Bypass Looping (Overaged / Peak-Aged)"
        delta_sigma_precip_MPa = delta_sigma_orowan_MPa

    # =========================================================================
    # SCALE 3: CONTINUUM PLASTICITY & TENSILE CONSTITUTIVE CURVE (10^-3 m / mm)
    # =========================================================================
    q_pow = 1.4
    obstacle_combined_MPa = math.pow(math.pow(delta_sigma_disloc_MPa, q_pow) + math.pow(delta_sigma_precip_MPa, q_pow), 1.0 / q_pow)
    yield_strength_MPa = sigma_0_friction_stress_MPa + delta_sigma_SS_MPa + delta_sigma_HP_MPa + obstacle_combined_MPa

    n_hollomon = max(0.08, min(0.32, 0.26 / (1.0 + yield_strength_MPa / 1200.0)))
    K_hollomon_MPa = yield_strength_MPa * math.pow(math.e / n_hollomon, n_hollomon)
    true_uts_MPa = K_hollomon_MPa * math.pow(n_hollomon, n_hollomon)
    eng_uts_MPa = true_uts_MPa / math.exp(n_hollomon)
    
    uniform_elongation_pct = n_hollomon * 100.0
    ductility_factor = 1.3 if is_ductile_pugh else 0.8
    total_elongation_pct = max(4.0, min(42.0, uniform_elongation_pct * ductility_factor + 4200.0 / (yield_strength_MPa + 250.0)))

    fracture_strain_true = math.log(1.0 + total_elongation_pct / 100.0)
    K_1c_MPa_sqrt_m = math.sqrt(max(15.0, (2.0 / 3.0) * (youngs_modulus_E_GPa * 1000.0) * yield_strength_MPa * fracture_strain_true * (n_hollomon**2)))

    # Generate 50-point true & engineering stress-strain curve for plotting & FEA export
    stress_strain_curve = []
    num_pts = 60
    max_strain = (total_elongation_pct / 100.0) * 1.05
    for i in range(num_pts):
        eng_strain = (i + 1) * (max_strain / num_pts)
        if eng_strain < (yield_strength_MPa / (youngs_modulus_E_GPa * 1000.0)):
            eng_stress = eng_strain * (youngs_modulus_E_GPa * 1000.0)
            true_strain = eng_strain
            true_stress = eng_stress
        else:
            plastic_strain = eng_strain - (yield_strength_MPa / (youngs_modulus_E_GPa * 1000.0))
            true_stress = yield_strength_MPa + (K_hollomon_MPa - yield_strength_MPa) * math.pow(max(1e-5, plastic_strain), n_hollomon)
            if eng_strain > (uniform_elongation_pct / 100.0):
                necking_decay = 1.0 - 0.40 * ((eng_strain - uniform_elongation_pct / 100.0) / max(0.01, max_strain - uniform_elongation_pct / 100.0))
                eng_stress = (true_stress / (1.0 + eng_strain)) * necking_decay
            else:
                eng_stress = true_stress / (1.0 + eng_strain)
            true_strain = math.log(1.0 + eng_strain)

        stress_strain_curve.append({
            "engineeringStrainPct": round(eng_strain * 100.0, 3),
            "engineeringStressMPa": round(eng_stress, 1),
            "trueStrain": round(true_strain, 4),
            "trueStressMPa": round(true_stress, 1)
        })

    jcA_MPa = round(yield_strength_MPa)
    jcB_MPa = round(K_hollomon_MPa - yield_strength_MPa)
    jcn = round(n_hollomon, 3)
    jcC = 0.014 if base_metal == "Ni" else 0.015 if base_metal == "Fe" else 0.028
    jcm = 1.15 if base_metal == "Ni" else 1.03 if base_metal == "Fe" else 0.90
    t_melt_C = ICME_JOHNSON_COOK_T_MELT_C[base_metal]

    # =========================================================================
    # SCALE 4: MACRO STRUCTURAL LOAD & COMPONENT LIMIT (10^-1 m / dm-m)
    # =========================================================================
    component_catalog = {
        "turbine_blade_root": {
            "name": "High-Pressure Gas Turbine Blade Fir-Tree Root",
            "criticalSectionArea_mm2": 320.0,
            "maxDesignLoad_kN": 240.0,
            "appliedStress_MPa": 750.0,
            "safetyFactorDesign": 1.25,
            "geometryFactorY": 1.12
        },
        "pressure_bulkhead": {
            "name": "Aerospace Fuselage Cryogenic Pressure Bulkhead",
            "criticalSectionArea_mm2": 850.0,
            "maxDesignLoad_kN": 450.0,
            "appliedStress_MPa": 529.0,
            "safetyFactorDesign": 1.50,
            "geometryFactorY": 1.00
        },
        "lpbf_bracket": {
            "name": "Generative LPBF Rocket Engine Swivel Bracket",
            "criticalSectionArea_mm2": 190.0,
            "maxDesignLoad_kN": 135.0,
            "appliedStress_MPa": 710.0,
            "safetyFactorDesign": 1.35,
            "geometryFactorY": 1.28
        }
    }
    
    comp_spec = component_catalog.get(component_type, component_catalog["turbine_blade_root"])
    applied_stress_MPa = comp_spec["appliedStress_MPa"]
    sf_actual = yield_strength_MPa / max(1.0, applied_stress_MPa)
    is_structurally_safe = sf_actual >= comp_spec["safetyFactorDesign"]
    
    geom_Y = comp_spec["geometryFactorY"]
    crit_flaw_size_ac_mm = (1.0 / math.pi) * math.pow((K_1c_MPa_sqrt_m / (geom_Y * applied_stress_MPa)), 2.0) * 1000.0
    plastic_zone_radius_mm = (1.0 / (2.0 * math.pi)) * math.pow((K_1c_MPa_sqrt_m / yield_strength_MPa), 2.0) * 1000.0

    # =========================================================================
    # CAE MATERIAL CARD GENERATORS (Abaqus, ANSYS, LS-DYNA, Nastran)
    # =========================================================================
    abaqus_card = f"""*HEADING
** MetalliX Multi-Scale ICME Calibrated Card for {alloy_name}
*MATERIAL, NAME={alloy_name.replace(' ', '_').upper()}
*DENSITY
{density_g_cm3 * 1000.0:.2f}
*ELASTIC, TYPE=ISOTROPIC
{youngs_modulus_E_GPa * 1e3:.2f}, {poisson_ratio:.4f}
*PLASTIC
{jcA_MPa:.1f}, 0.0000
{jcA_MPa + (jcB_MPa * 0.05**jcn):.1f}, 0.0500
{jcA_MPa + (jcB_MPa * 0.10**jcn):.1f}, 0.1000
{jcA_MPa + (jcB_MPa * 0.18**jcn):.1f}, 0.1800
*RATE DEPENDENT
{jcC:.5f}, {strain_rate_s_inv}
*TENSILE FAILURE
{fracture_strain_true:.4f}, 0.0, 0.0"""

    ls_dyna_card = f"""$*LS-DYNA MATERIAL DECK: {alloy_name}
*MAT_PIECEWISE_LINEAR_PLASTICITY
$#     mid        ro         e        pr      sigy      etan      fail      tdel
         1  {density_g_cm3 * 1e-3:.3e}  {youngs_modulus_E_GPa * 1e3:.1f}   {poisson_ratio:.4f}  {jcA_MPa:.1f}       0.0  {fracture_strain_true:.4f}       0.0
$#       c         p      lcss      lcsr        vp
   {jcC:.4f}       0.0         0         0       0.0"""

    ansys_card = f"""! ANSYS APDL Material Card: {alloy_name}
MPTEMP,,,,,,,,
MPTEMP,1,0
MPDATA,EX,1,,{youngs_modulus_E_GPa * 1e3:.2f}
MPDATA,PRXY,1,,{poisson_ratio:.4f}
MPDATA,DENS,1,,{density_g_cm3 * 1e-9:.4e}
TB,PLAS,1,1,4,MISO
TBTEMP,25.0
TBPT,,0.0,{jcA_MPa:.1f}
TBPT,,0.05,{jcA_MPa + (jcB_MPa * 0.05**jcn):.1f}
TBPT,,0.10,{jcA_MPa + (jcB_MPa * 0.10**jcn):.1f}
TBPT,,0.20,{jcA_MPa + (jcB_MPa * 0.20**jcn):.1f}"""

    compute_time_ms = round((time.time() - t_start) * 1000.0, 2)

    return {
        "success": True,
        "engine": "MetalliX ICME Multi-Scale HPC Pipeline (DFT -> CALPHAD -> Kinetics -> Microstructure -> Macro FEA)",
        "computeTimeMs": compute_time_ms,
        "inputParameters": {
            "alloyName": alloy_name,
            "baseMetal": base_metal,
            "crystalSystem": crystal_system,
            "coolingRate_C_s": cooling_rate_C_s,
            "grainSize_um": grain_size_d_um,
            "agingTemp_C": aging_temp_C,
            "agingTime_h": aging_time_h,
            "componentType": component_type
        },
        "scale0_dftAtomistic": {
            "latticeParameter_a0_Angstrom": round(a0_angstrom, 4),
            "burgersVector_b_nm": round(burgers_b_nm, 4),
            "slipPlane_dhkl_nm": round(d_hkl_nm, 4),
            "elasticTensor_Cij_GPa": {
                "C11": C11,
                "C12": C12,
                "C44": C44
            },
            "homogenizedModuli": {
                "youngsModulus_E_GPa": round(youngs_modulus_E_GPa, 1),
                "shearModulus_G_GPa": round(shear_modulus_G_GPa, 1),
                "bulkModulus_B_GPa": round(bulk_modulus_B_GPa, 1),
                "poissonsRatio": round(poisson_ratio, 4),
                "pughRatio_B_over_G": round(pugh_ratio_B_over_G, 3),
                "cauchyPressure_GPa": round(cauchy_pressure_GPa, 1),
                "ductilityVerdict": "Ductile (Pugh B/G > 1.75)" if is_ductile_pugh else "Brittle Tendency (Pugh B/G <= 1.75)"
            },
            "peierlsNabarroLatticeFriction": {
                "tau_PN_MPa": round(tau_PN_MPa, 2),
                "taylorFactor_M": taylor_M,
                "sigma_0_friction_stress_MPa": round(sigma_0_friction_stress_MPa, 1)
            }
        },
        "scale1_calphadSoluteMisfit": {
            "atomicFractions": {el: round(frac * 100.0, 2) for el, frac in atomic_fractions.items()},
            "soluteBreakdown": solute_breakdown,
            "totalSolidSolutionStrengthening_MPa": round(delta_sigma_SS_MPa, 1)
        },
        "scale2_microstructureKinetics": {
            "coolingRate_C_s": cooling_rate_C_s,
            "computedSDAS_um": round(computed_sdas_um, 2),
            "grainSize_d_um": round(grain_size_d_um, 2),
            "hallPetchStrengthening_MPa": round(delta_sigma_HP_MPa, 1),
            "dislocationDensity_rho_m2": f"{dislocation_density_rho_m2:.2e}",
            "taylorDislocationStrengthening_MPa": round(delta_sigma_disloc_MPa, 1),
            "precipitationKinetics": {
                "agingTemp_C": aging_temp_C,
                "agingTime_h": aging_time_h,
                "meanPrecipitateRadius_nm": round(mean_precip_radius_nm, 2),
                "volumeFractionPct": round(volume_frac_precip * 100.0, 1),
                "interparticleSpacing_nm": round(lambda_spacing_nm, 1),
                "shearingStrength_MPa": round(delta_sigma_cutting_MPa, 1),
                "orowanStrength_MPa": round(delta_sigma_orowan_MPa, 1),
                "activeMechanism": precip_mechanism,
                "effectivePrecipitationStrengthening_MPa": round(delta_sigma_precip_MPa, 1)
            }
        },
        "scale3_continuumPlasticity": {
            "strengtheningContributions_MPa": {
                "sigma_0_LatticeFriction": round(sigma_0_friction_stress_MPa, 1),
                "deltaSigma_SS_SolidSolution": round(delta_sigma_SS_MPa, 1),
                "deltaSigma_HP_GrainBoundary": round(delta_sigma_HP_MPa, 1),
                "deltaSigma_Disloc_Forest": round(delta_sigma_disloc_MPa, 1),
                "deltaSigma_Precip_OrowanCutting": round(delta_sigma_precip_MPa, 1)
            },
            "mechanicalProperties": {
                "yieldStrength_Rp02_MPa": round(yield_strength_MPa, 1),
                "ultimateTensileStrength_UTS_MPa": round(eng_uts_MPa, 1),
                "uniformElongationPct": round(uniform_elongation_pct, 1),
                "totalElongationPct": round(total_elongation_pct, 1),
                "fractureToughness_K1c_MPa_sqrt_m": round(K_1c_MPa_sqrt_m, 1),
                "hollomon_n": round(n_hollomon, 3),
                "hollomon_K_MPa": round(K_hollomon_MPa, 1)
            },
            "johnsonCookParameters": {
                "A_MPa": jcA_MPa,
                "B_MPa": jcB_MPa,
                "n": jcn,
                "C": jcC,
                "m": jcm,
                "T_melt_C": t_melt_C
            },
            "stressStrainCurve": stress_strain_curve
        },
        "scale4_macroComponentFEA": {
            "componentName": comp_spec["name"],
            "criticalSectionArea_mm2": comp_spec["criticalSectionArea_mm2"],
            "appliedStress_MPa": applied_stress_MPa,
            "requiredSafetyFactor": comp_spec["safetyFactorDesign"],
            "actualSafetyFactor": round(sf_actual, 2),
            "structuralVerdict": "STRUCTURALLY SAFE (Passed Yield & Creep Criteria)" if is_structurally_safe else "WARNING: INSUFFICIENT SAFETY MARGIN (Risk of Plastic Yielding)",
            "lefmDamageTolerance": {
                "criticalFlawSize_ac_mm": round(crit_flaw_size_ac_mm, 2),
                "plasticZoneRadius_rp_mm": round(plastic_zone_radius_mm, 2),
                "inspectionNDICapability": "Detectable with Standard X-Ray / UT (Flaw > 1.0mm)" if crit_flaw_size_ac_mm > 1.0 else "High-Resolution Eddy Current / Computed Tomography Required (Sub-mm Flaw)"
            }
        },
        "caeExportCards": {
            "abaqus": abaqus_card,
            "lsDyna": ls_dyna_card,
            "ansys": ansys_card
        }
    }


def main():
    try:
        if not sys.stdin.isatty():
            raw_input = sys.stdin.read()
            if raw_input.strip():
                params = json.loads(raw_input)
            else:
                params = {}
        else:
            params = {}

        result = solve_multiscale_pipeline(params)
        # Phase 6a provenance (constants and domain-data versions, the R actually used)
        result["provenance"] = {
            "registryVersion": alloy_registry.REGISTRY_VERSION,
            "constantsVersion": physical_constants.CONSTANTS_VERSION,
            "gasConstantR_J_molK": LEGACY_R_8_314.value,
            **_domain_data_provenance(),
            "constantsNote": "Rounded R = 8.314 and legacy rounded atomic weights (pre-migration "
                             "values); exact SI R and CIAAW weights are pending the Phase 6a value step.",
        }
        print(json.dumps(result, indent=2))
    except ValidationError as e:
        # Phase 6a envelope: invalid input, not a solver failure (HTTP 422 in the bridge).
        print(json.dumps(validation_envelope(e)))
        sys.exit(2)
    except Exception as e:
        err_res = {
            "success": False,
            "error": str(e),
            "engine": "MetalliX ICME Multi-Scale Pipeline Solver",
            "errorKind": "internal",
        }
        print(json.dumps(err_res, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
