#!/usr/bin/env python3
"""
MetalliX Python LPBF Thermal, Melt Pool Geometry & Multi-Defect Physics Solver
Author: MetalliX Additive Manufacturing HPC Subsystem

Simulates:
1. 3D Goldak double-ellipsoid moving laser heat source & Eagar-Tsai / Rosenthal thermal fields
2. Multi-regime melt pool geometry (Conduction, Transition, Keyhole Vapor Cavity)
3. 3-View geometric contours (Top-Down X-Y, Longitudinal X-Z, Transverse Y-Z with Hatch Overlap)
4. Hydrodynamic Marangoni convection, Knudsen recoil vapor pressure, & multiple-reflection absorptivity
5. Comprehensive defect analytics: Lack of Fusion (LoF), Keyhole Porosity, Plateau-Rayleigh Balling, Spatter Denudation
6. Solidification kinetics: G(x,y,z), R(x,y,z), Cooling Rate G*R, Hunt CET morphology, PDAS & SDAS
7. Full 2D Power-Velocity (P-V) Process Window map generation
"""

import sys
import json
import math
import time

import numpy as np

from eagar_tsai_solver import EagarTsaiField, MODEL_ID as EAGAR_TSAI_MODEL_ID
from fabbro_keyhole import MODEL_ID as FABBRO_MODEL_ID, fabbro_keyhole_depth_m
from four_alloy_materials import four_alloy_thermophysical_db, thermal_props
from goldak_solver import GoldakField, MODEL_ID as GOLDAK_MODEL_ID, seed_goldak_axes
from solidification_front import MODEL_ID as SOLIDIFICATION_MODEL_ID, evaluate_solidification
from marangoni_screening import MODEL_ID as MARANGONI_MODEL_ID, marangoni_screening
from lpbf_defect_diagnostics import defect_diagnostics

# Secondary alloys only. Ti-6Al-4V, 316L, AlSi10Mg, IN718 live in four_alloy_materials.py.
SECONDARY_THERMOPHYSICAL_DB = {
    "Inconel 625": {
        "base": "Ni",
        "liquidus_C": 1350.0,
        "solidus_C": 1290.0,
        "boiling_C": 2880.0,
        "M_molar_kg_mol": 0.0585,
        "density_kg_m3": 8440.0,
        "density_liquid_kg_m3": 7600.0,
        "thermal_conductivity_W_mK": 9.8,
        "thermal_conductivity_liquid_W_mK": 30.0,
        "specific_heat_J_kgK": 410.0,
        "specific_heat_liquid_J_kgK": 750.0,
        "latent_heat_fusion_J_kg": 260000.0,
        "latent_heat_vap_J_kg": 6300000.0,
        "absorptivity_IR": 0.38,
        "absorptivity_Green": 0.58,
        "surface_tension_N_m": 1.76,
        "d_gamma_dT_N_mK": -0.00045,
        "viscosity_Pa_s": 0.0055,
        "thermal_expansion_1_K": 12.8e-6,
        "youngs_modulus_GPa": 205.0,
        "poissons_ratio": 0.31,
        "pdas_A1": 80.0,
        "sdas_B1": 42.0
    },
    "CoCrMo": {
        "base": "Co",
        "liquidus_C": 1395.0,
        "solidus_C": 1330.0,
        "boiling_C": 2870.0,
        "M_molar_kg_mol": 0.0585,
        "density_kg_m3": 8300.0,
        "density_liquid_kg_m3": 7500.0,
        "thermal_conductivity_W_mK": 14.8,
        "thermal_conductivity_liquid_W_mK": 28.0,
        "specific_heat_J_kgK": 450.0,
        "specific_heat_liquid_J_kgK": 740.0,
        "latent_heat_fusion_J_kg": 275000.0,
        "latent_heat_vap_J_kg": 6300000.0,
        "absorptivity_IR": 0.40,
        "absorptivity_Green": 0.60,
        "surface_tension_N_m": 1.75,
        "d_gamma_dT_N_mK": -0.00038,
        "viscosity_Pa_s": 0.0052,
        "thermal_expansion_1_K": 14.2e-6,
        "youngs_modulus_GPa": 230.0,
        "poissons_ratio": 0.30,
        "pdas_A1": 85.0,
        "sdas_B1": 44.0
    },
    "Scalmalloy (Al-Mg-Sc-Zr)": {
        "base": "Al",
        "liquidus_C": 645.0,
        "solidus_C": 580.0,
        "boiling_C": 2470.0,
        "M_molar_kg_mol": 0.0272,
        "density_kg_m3": 2670.0,
        "density_liquid_kg_m3": 2380.0,
        "thermal_conductivity_W_mK": 115.0,
        "thermal_conductivity_liquid_W_mK": 78.0,
        "specific_heat_J_kgK": 920.0,
        "specific_heat_liquid_J_kgK": 1200.0,
        "latent_heat_fusion_J_kg": 405000.0,
        "latent_heat_vap_J_kg": 10500000.0,
        "absorptivity_IR": 0.22,
        "absorptivity_Green": 0.42,
        "surface_tension_N_m": 0.88,
        "d_gamma_dT_N_mK": -0.00032,
        "viscosity_Pa_s": 0.0014,
        "thermal_expansion_1_K": 22.0e-6,
        "youngs_modulus_GPa": 72.0,
        "poissons_ratio": 0.33,
        "pdas_A1": 38.0,
        "sdas_B1": 18.0
    },
    "Hastelloy X": {
        "base": "Ni",
        "liquidus_C": 1355.0,
        "solidus_C": 1260.0,
        "boiling_C": 2880.0,
        "M_molar_kg_mol": 0.0580,
        "density_kg_m3": 8220.0,
        "density_liquid_kg_m3": 7480.0,
        "thermal_conductivity_W_mK": 12.0,
        "thermal_conductivity_liquid_W_mK": 30.0,
        "specific_heat_J_kgK": 485.0,
        "specific_heat_liquid_J_kgK": 760.0,
        "latent_heat_fusion_J_kg": 265000.0,
        "latent_heat_vap_J_kg": 6450000.0,
        "absorptivity_IR": 0.39,
        "absorptivity_Green": 0.59,
        "surface_tension_N_m": 1.76,
        "d_gamma_dT_N_mK": -0.00042,
        "viscosity_Pa_s": 0.0058,
        "thermal_expansion_1_K": 14.5e-6,
        "youngs_modulus_GPa": 205.0,
        "poissons_ratio": 0.30,
        "pdas_A1": 82.0,
        "sdas_B1": 43.0
    },
    "Pure Copper (Cu-OF)": {
        "base": "Cu",
        "liquidus_C": 1083.0,
        "solidus_C": 1083.0,
        "boiling_C": 2562.0,
        "M_molar_kg_mol": 0.0635,
        "density_kg_m3": 8960.0,
        "density_liquid_kg_m3": 8020.0,
        "thermal_conductivity_W_mK": 390.0,
        "thermal_conductivity_liquid_W_mK": 160.0,
        "specific_heat_J_kgK": 385.0,
        "specific_heat_liquid_J_kgK": 540.0,
        "latent_heat_fusion_J_kg": 205000.0,
        "latent_heat_vap_J_kg": 4730000.0,
        "absorptivity_IR": 0.08,   # Very low IR absorption
        "absorptivity_Green": 0.45, # High Green 515nm absorption
        "surface_tension_N_m": 1.30,
        "d_gamma_dT_N_mK": -0.00028,
        "viscosity_Pa_s": 0.0040,
        "thermal_expansion_1_K": 16.5e-6,
        "youngs_modulus_GPa": 120.0,
        "poissons_ratio": 0.34,
        "pdas_A1": 50.0,
        "sdas_B1": 25.0
    }
}

THERMOPHYSICAL_DB = {**four_alloy_thermophysical_db(), **SECONDARY_THERMOPHYSICAL_DB}

# King et al. (2014) / Rubenchik: keyhole onset typically ΔH/hs ≈ 25–30.
ENTHALPY_TRANSITION = 15.0
ENTHALPY_KEYHOLE = 30.0


def classify_enthalpy_regime(normalized_enthalpy: float) -> str:
    if normalized_enthalpy >= ENTHALPY_KEYHOLE:
        return "Keyhole Mode (Deep Vapor Cavity)"
    if normalized_enthalpy >= ENTHALPY_TRANSITION:
        return "Transition Mode"
    return "Conduction Mode (Stable)"


def rosenthal_temperature_C(x_m, y_m, z_m, T0_C, P_eff, k_th, v_scan, alpha_th, r_reg):
    """3D Rosenthal moving point source, regularized at the origin (beam radius)."""
    R = math.sqrt(x_m * x_m + y_m * y_m + z_m * z_m + r_reg * r_reg)
    arg = -v_scan * (R + x_m) / max(1e-16, 2.0 * alpha_th)
    arg = max(-45.0, min(20.0, arg))
    return T0_C + (P_eff / (2.0 * math.pi * k_th * R)) * math.exp(arg)


def _binary_extent(pred, lo, hi, iters=18):
    """Largest value in [lo, hi] where pred is True (pred monotonic True→False)."""
    if not pred(lo):
        return 0.0
    if pred(hi):
        return hi
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if pred(mid):
            lo = mid
        else:
            hi = mid
    return lo


def sample_thermal_slice(eval_T, axis_a, axis_b, na, nb):
    temps = []
    for ia in range(na):
        a = axis_a[0] + (axis_a[1] - axis_a[0]) * ia / max(1, na - 1)
        for ib in range(nb):
            b = axis_b[0] + (axis_b[1] - axis_b[0]) * ib / max(1, nb - 1)
            temps.append(round(float(eval_T(a, b)), 1))
    return temps


def _normalize_heat_source(heat_source: str | None) -> str:
    if heat_source is None or (isinstance(heat_source, str) and not heat_source.strip()):
        return "rosenthal"
    if not isinstance(heat_source, str):
        raise ValueError(f"Unsupported LPBF heat source: {heat_source!r}")
    key = heat_source.strip().lower().replace("_", "-")
    if key in ("rosenthal", "rosenthal-screening", "rosenthal-screening-v1"):
        return "rosenthal"
    if key in ("eagar-tsai", "eagar-tsai-v1", "eagar-tsai-v2", "et", "eager-tsai"):
        return "eagar-tsai"
    if key in ("goldak", "goldak-v1", "goldak-double-ellipsoid", "goldak-half-space-v3"):
        return "goldak"
    raise ValueError(f"Unsupported LPBF heat source: {heat_source!r}")


def calculate_meltpool_physics(
    material_name: str,
    laser_power_W: float,
    scan_speed_mm_s: float,
    beam_diameter_um: float,
    preheat_temp_C: float = 80.0,
    layer_thickness_um: float = 40.0,
    hatch_spacing_um: float = 100.0,
    laser_wavelength: str = "IR_1064nm",
    incline_angle_deg: float = 0.0,
    process_seed: int = 42,
    prop_overrides: dict | None = None,
    heat_source: str | None = None,
    sulfur_ppm: float = 15.0,
):
    """
    Evaluates 3D multi-regime melt pool physics, geometry, defects, and microstructure.
    Optional prop_overrides merge onto the resolved thermophysical dict (UQ / AM-Bench).
    heat_source: "rosenthal" (Build Job default), "eagar-tsai", or "goldak" (Melt Pool lab).
    sulfur_ppm: Heiple–Roper screening only (does not refit W/D or re-score Build Job).
    """
    if not isinstance(material_name, str) or not material_name.strip():
        raise ValueError(f"Unsupported LPBF material identity: {material_name!r}")
    source = _normalize_heat_source(heat_source)
    base = thermal_props(material_name) or SECONDARY_THERMOPHYSICAL_DB.get(material_name)
    if base is None:
        raise ValueError(f"Unsupported LPBF material identity: {material_name!r}")
    props = dict(base)
    if prop_overrides:
        props.update(prop_overrides)
    
    process_values = {}
    for name, value in (
        ("laser_power_W", laser_power_W),
        ("scan_speed_mm_s", scan_speed_mm_s),
        ("beam_diameter_um", beam_diameter_um),
        ("layer_thickness_um", layer_thickness_um),
        ("hatch_spacing_um", hatch_spacing_um),
    ):
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be finite and positive") from exc
        if not math.isfinite(numeric_value) or numeric_value <= 0:
            raise ValueError(f"{name} must be finite and positive")
        process_values[name] = numeric_value

    P_laser = process_values["laser_power_W"]
    scan_speed_mm_s = process_values["scan_speed_mm_s"]
    beam_diameter_um = process_values["beam_diameter_um"]
    layer_thickness_um = process_values["layer_thickness_um"]
    hatch_spacing_um = process_values["hatch_spacing_um"]
    v_scan = scan_speed_mm_s * 1e-3  # m/s
    d_beam = beam_diameter_um * 1e-6  # m
    r_beam = d_beam / 2.0
    T_preheat = float(preheat_temp_C)
    t_layer_m = float(layer_thickness_um) * 1e-6
    hatch_m = float(hatch_spacing_um) * 1e-6
    theta_rad = math.radians(float(incline_angle_deg))
    cos_theta = max(0.05, math.cos(theta_rad))  # avoid zero R on vertical walls

    T_liq = props["liquidus_C"]
    T_sol = props["solidus_C"]
    T_vap = props["boiling_C"]
    rho = props["density_kg_m3"]
    k_s = props["thermal_conductivity_W_mK"]
    k_l = float(props.get("thermal_conductivity_liquid_W_mK", k_s))
    cp_s = props["specific_heat_J_kgK"]
    cp_l = float(props.get("specific_heat_liquid_J_kgK", cp_s))
    # Effective mushy-zone k/Cp for Rosenthal geometry (equal-weight solid↔liquid blend).
    k_th = 0.5 * (k_s + k_l)
    cp = 0.5 * (cp_s + cp_l)
    alpha_th = k_th / (rho * cp)  # Thermal diffusivity (m^2/s)
    # King ΔH/hs stays on solid props (literature onset ~30 is solid-based).
    alpha_solid = k_s / (rho * cp_s)

    # Use only wavelength/property pairs that exist in the material snapshot.
    wavelength_property = {
        "IR_1064nm": "absorptivity_IR",
        "Green_515nm": "absorptivity_Green",
    }.get(laser_wavelength)
    if wavelength_property is None:
        raise ValueError(f"Unsupported LPBF laser wavelength: {laser_wavelength!r}")
    if wavelength_property not in props:
        raise ValueError(
            f"Material {material_name!r} has no absorptivity for {laser_wavelength}"
        )
    eta_base_flat = float(props[wavelength_property])

    try:
        from powder_bed_raytracer import calculate_powder_bed_absorptivity
        powder_metrics = calculate_powder_bed_absorptivity(
            beam_radius_um=r_beam * 1e6,
            base_absorptivity=eta_base_flat
        )
        eta_base = powder_metrics["effective_absorptivity"]
    except Exception as e:
        print(f"Warning: GPU Powder Bed Ray Tracing failed, using flat plate absorptivity. {e}")
        eta_base = eta_base_flat

    # 1. Volumetric and Linear Energy Densities
    ved_J_mm3 = P_laser / (
        scan_speed_mm_s
        * (hatch_spacing_um * 1e-3)
        * (layer_thickness_um * 1e-3)
    )
    led_J_m = P_laser / v_scan

    # 2. Normalized Enthalpy (King / Rubenchik) + peak intensity I0 — solid k, Cp
    # ΔH/hs = (η P) / (ρ cp (Tliq-T0) sqrt(π α v r^3))
    enthalpy_denom = rho * cp_s * max(50.0, T_liq - T_preheat) * math.sqrt(math.pi * alpha_solid * v_scan * (r_beam ** 3))
    normalized_enthalpy = (eta_base * P_laser) / max(1e-9, enthalpy_denom)
    # Gaussian 1/e² diameter d=2w: I0 = 2P/(πw²) = 8P/(πd²).
    peak_intensity_W_m2 = (8.0 * P_laser) / (math.pi * d_beam ** 2)
    peak_intensity_MW_cm2 = peak_intensity_W_m2 * 1e-10

    # 3. Multi-reflection absorptivity once a vapor depression can form (ΔH/hs > 15)
    if normalized_enthalpy > ENTHALPY_TRANSITION:
        cavity_aspect = min(4.0, (normalized_enthalpy - ENTHALPY_TRANSITION) / 8.0)
        n_reflections = 1.0 + 1.8 * cavity_aspect
        eta_eff = 1.0 - (1.0 - eta_base) ** n_reflections
    else:
        eta_eff = eta_base
        cavity_aspect = 0.0

    effective_power = eta_eff * P_laser
    # Latent-heat (Stefan) correction so the liquidus is not an over-hot Rosenthal tail.
    Lf = props["latent_heat_fusion_J_kg"]
    stefan = Lf / max(1.0, cp * max(50.0, T_liq - T_preheat))
    # ET/Goldak are conduction fields: Fresnel A only. Fabbro already carries keyhole A(R)
    # (Appl. Sci. 2020 eq. 2). Stacking eta_eff on both double-counts Trapp multiple reflections.
    if source in ("eagar-tsai", "goldak"):
        P_absorbed = eta_base * P_laser
        A_fabbro = eta_base_flat
    else:
        P_absorbed = effective_power
        A_fabbro = eta_base_flat
    P_geom = P_absorbed / (1.0 + 0.55 * stefan)
    r_reg = max(r_beam / math.sqrt(2.0), 8e-6)

    goldak_seed = seed_goldak_axes(r_beam)
    if source == "eagar-tsai":
        et_field = EagarTsaiField(T_preheat, P_geom, k_th, alpha_th, r_beam).bind_speed(v_scan)

        def T_field(x_m, y_m, z_m):
            return et_field.temperature_C(x_m, y_m, z_m)

        heat_source_id = EAGAR_TSAI_MODEL_ID
    elif source == "goldak":
        gk_field = GoldakField(
            T_preheat, P_geom, rho, cp, alpha_th,
            goldak_seed["af_m"], goldak_seed["ar_m"], goldak_seed["b_m"], goldak_seed["c_m"],
        ).bind_speed(v_scan)

        def T_field(x_m, y_m, z_m):
            return gk_field.temperature_C(x_m, y_m, z_m)

        heat_source_id = GOLDAK_MODEL_ID
    else:
        def T_field(x_m, y_m, z_m):
            return rosenthal_temperature_C(x_m, y_m, z_m, T_preheat, P_geom, k_th, v_scan, alpha_th, r_reg)

        heat_source_id = "rosenthal-screening-v1"

    fabbro = fabbro_keyhole_depth_m(
        P_laser, v_scan, d_beam, k_s, alpha_solid, T_vap, T_preheat, A_fabbro, normalized_enthalpy
    )

    # Seed search box from the high-speed Rosenthal width scale
    denom_thermal = rho * cp * max(50.0, T_liq - T_preheat) * v_scan
    w_analytical = math.sqrt(max(1e-12, (8.0 / (math.pi * math.e)) * (P_geom / denom_thermal)))
    search_half_w = max(d_beam * 1.8, w_analytical * 1.8, 50e-6)
    search_len = max(d_beam * 3.0, w_analytical * 4.5, 80e-6)
    search_depth = max(d_beam * 2.2, w_analytical * 2.0, 40e-6, fabbro["depth_m"] * 1.35)

    t_peak_C = float(T_field(0.0, 0.0, 0.0))
    # No artificial 3900 °C display ceiling — report the field peak (may exceed boiling).

    # 4. Liquidus extents from the conduction field (Rosenthal or Eagar–Tsai)
    x_front = _binary_extent(lambda x: T_field(x, 0.0, 0.0) >= T_liq, 0.0, search_len)
    x_rear = _binary_extent(lambda s: T_field(-s, 0.0, 0.0) >= T_liq, 0.0, search_len * 1.4)
    half_w = 0.0
    for x_probe in (-x_rear * 0.35, -x_rear * 0.15, -x_rear * 0.05, 0.0, x_front * 0.35):
        half_w = max(half_w, _binary_extent(lambda y: T_field(x_probe, y, 0.0) >= T_liq, 0.0, search_half_w))
    d_iso = 0.0
    for x_probe in (-x_rear * 0.25, -x_rear * 0.1, -x_rear * 0.04, 0.0):
        d_iso = max(d_iso, _binary_extent(lambda z: T_field(x_probe, 0.0, z) >= T_liq, 0.0, search_depth))

    if half_w < 8e-6 or d_iso < 3e-6:
        w_fb = math.sqrt(max(1e-12, w_analytical ** 2 + (0.65 * d_beam) ** 2))
        half_w = max(half_w, w_fb / 2.0)
        d_iso = max(d_iso, half_w * (0.38 + 0.10 * min(1.0, normalized_enthalpy / ENTHALPY_TRANSITION)))
        if x_front < 1e-6:
            x_front = r_beam * 0.45
        if x_rear < 1e-6:
            x_rear = max(w_fb, half_w * 2.2)

    w_melt_m = max(2.0 * half_w, d_beam * 0.55)
    d_iso = max(d_iso, 4e-6)
    # Uncapped Rosenthal length (no Peclet fake ceiling). Floor only for numerical sanity.
    l_melt_m = max(x_front + x_rear, d_beam)
    x_front = max(x_front, r_beam * 0.35)
    x_rear = max(r_beam * 0.8, l_melt_m - x_front)
    l_melt_m = x_front + x_rear

    # Keyhole extra: Fabbro on Melt Pool lab fields; Rosenthal Build Job keeps the King increment.
    if source in ("eagar-tsai", "goldak"):
        extra = max(0.0, fabbro["depth_m"] - d_iso)
        keyhole_depth_um = extra * 1e6
    elif normalized_enthalpy < ENTHALPY_TRANSITION:
        extra = 0.0
        keyhole_depth_um = 0.0
    elif normalized_enthalpy < ENTHALPY_KEYHOLE:
        trans = (normalized_enthalpy - ENTHALPY_TRANSITION) / (ENTHALPY_KEYHOLE - ENTHALPY_TRANSITION)
        extra = d_iso * (0.15 + 0.55 * trans)
        keyhole_depth_um = extra * 1e6
    else:
        over = (normalized_enthalpy - ENTHALPY_KEYHOLE) / 10.0
        extra = d_iso * (0.85 + 0.55 * math.log10(1.0 + max(0.0, over)))
        keyhole_depth_um = extra * 1e6

    if normalized_enthalpy < ENTHALPY_TRANSITION:
        keyhole_porosity_risk = "Negligible (<0.01%)"
    elif normalized_enthalpy < ENTHALPY_KEYHOLE:
        keyhole_porosity_risk = "Low-Moderate (Occasional Fluctuations)"
    else:
        keyhole_porosity_risk = "High (Vapor Bubble Entrapment / Pore Defect Risk)"

    d_melt_m = d_iso + extra
    regime = classify_enthalpy_regime(normalized_enthalpy)

    w_melt_um = w_melt_m * 1e6
    d_melt_um = d_melt_m * 1e6
    l_melt_um = l_melt_m * 1e6
    peclet_number = (v_scan * w_melt_m) / (2.0 * alpha_th)

    goldak_af_um = max(4.0, x_front * 1e6)
    goldak_ar_um = max(4.0, x_rear * 1e6)
    goldak_b_um = w_melt_um / 2.0
    goldak_c_um = d_melt_um

    # 8. Recoil from evaporative surface T (Anisimov/Knight 0.54 Psat). Field peak stays
    # uncapped (PROOF 015). Conduction singularities of 10^4 °C are not a wall temperature.
    R_gas = 8.314
    M_molar = float(props.get("M_molar_kg_mol", 0.055))
    delta_H_vap = props["latent_heat_vap_J_kg"] * M_molar
    t_surface_C = min(float(t_peak_C), float(T_vap))
    T_surf_K = t_surface_C + 273.15
    T_vap_K = T_vap + 273.15

    if t_surface_C >= T_vap * 0.8:
        recoil_exp = (delta_H_vap / R_gas) * (1.0 / T_vap_K - 1.0 / max(500.0, T_surf_K))
        if recoil_exp > 700.0:
            p_recoil_atm = 1.0e200
        elif recoil_exp < -700.0:
            p_recoil_atm = 0.0
        else:
            p_recoil_atm = 0.54 * math.exp(recoil_exp)
        p_recoil_kPa = min(1.0e12, p_recoil_atm * 101.325)
    else:
        p_recoil_kPa = 0.1

    ma = marangoni_screening(
        props["d_gamma_dT_N_mK"],
        props["viscosity_Pa_s"],
        alpha_th,
        float(props.get("density_liquid_kg_m3", rho)),
        w_melt_m / 2.0,
        t_surface_C,
        T_liq,
        sulfur_ppm=float(sulfur_ppm),
    )
    marangoni_number = ma["marangoniNumber"]

    # 9. Defect Diagnostics
    # A) Lack of Fusion — Tang et al.: (h/W)^2 + (t/D)^2 ≤ 1 for full consolidation
    h_um = max(1.0, float(hatch_spacing_um))
    t_um = max(1.0, float(layer_thickness_um))
    h_over_w = h_um / max(1.0, w_melt_um)
    t_over_d = t_um / max(1.0, d_melt_um)
    lof_criterion_val = (h_over_w ** 2) + (t_over_d ** 2)
    w_over_h = w_melt_um / h_um
    d_over_t = d_melt_um / t_um

    if lof_criterion_val > 1.0:
        lof_risk = "Severe Lack of Fusion (Tang index > 1 — inter-track/layer unmelt)"
        lof_status = "Fail"
    elif lof_criterion_val > 0.80:
        lof_risk = "Marginal Overlap (Tang index approaching 1)"
        lof_status = "Warning"
    else:
        lof_risk = "Full Fusion Bonding (Tang (h/W)^2+(t/D)^2 ≤ 0.80)"
        lof_status = "Pass"

    # B) Plateau-Rayleigh Capillary Balling Defect (L / W > pi)
    aspect_L_over_W = l_melt_um / max(1.0, w_melt_um)
    if aspect_L_over_W > 3.8:
        balling_risk = "High Balling Risk (Capillary Pinch-Off & Humping)"
    elif aspect_L_over_W > 3.1416:
        balling_risk = "Moderate (Melt Bead Undulation)"
    else:
        balling_risk = "Stable Continuous Track (No Balling)"

    # C) Powder Denudation & Spatter Entrainment Width
    # Denudation width w_denude ~ W * (1 + 0.45 * (P_recoil / 50))
    denudation_width_um = w_melt_um * (1.0 + 0.35 * min(3.0, min(1e6, p_recoil_kPa) / 30.0))

    # 10. Solidification kinetics from the liquidus isotherm (G = |∇T|, R = v n_x).
    sol = evaluate_solidification(
        T_field,
        T_liq=T_liq,
        T_sol=T_sol,
        t_surface=t_surface_C,
        v_scan=v_scan,
        x_rear=x_rear,
        x_front=x_front,
        search_depth=search_depth,
        r_beam=r_beam,
        cos_theta=cos_theta,
        pdas_A1=float(props.get("pdas_A1", 75.0)),
        sdas_B1=float(props.get("sdas_B1", 40.0)),
        material_name=material_name,
    )
    thermal_gradient_G_K_m = float(sol["thermalGradient_G_K_m"])
    solidification_rate_R_m_s = float(sol["solidificationRate_R_m_s"])
    cooling_rate_K_s = float(sol["coolingRate_K_s"])
    g_over_r = float(sol["g_over_r_ratio"])
    morphology = str(sol["microstructureMorphology"])
    pdas_um = float(sol["primaryDendriteArmSpacing_PDAS_um"])
    sdas_um = float(sol["secondaryDendriteArmSpacing_SDAS_um"])

    # 11. Residual Stress & Recoater Crash Upper Bound (no artificial 1200 MPa ceiling)
    e_gpa = props["youngs_modulus_GPa"]
    alpha_exp = props["thermal_expansion_1_K"]
    nu = props["poissons_ratio"]
    delta_t_stress = max(10.0, T_sol - T_preheat)
    elastic_stress_max_mpa = (e_gpa * 1e3 * alpha_exp * delta_t_stress) / max(0.01, 1.0 - nu)
    effective_residual_stress_mpa = elastic_stress_max_mpa * 0.72
    distortion_index = (effective_residual_stress_mpa * (float(layer_thickness_um) / 40.0)) / 420.0
    
    if distortion_index > 2.0:
        recoater_risk = "High (Blade Collision & Part Curl Risk)"
    elif distortion_index > 1.2:
        recoater_risk = "Moderate (Anchor Support Structures Required)"
    else:
        recoater_risk = "Low (Safe Thermal Stress Window)"

    # 12. Geometric 2D contours from liquidus isolines (plus keyhole extra depth)
    depth_scale = d_melt_m / max(1e-9, d_iso)
    num_pts = 48
    top_down_contour = []
    for i in range(num_pts + 1):
        s = i / num_pts
        x_m = goldak_af_um * 1e-6 - (goldak_af_um + goldak_ar_um) * 1e-6 * s
        y_half = _binary_extent(lambda y: T_field(x_m, y, 0.0) >= T_liq, 0.0, search_half_w)
        x_um = x_m * 1e6
        y_um = y_half * 1e6
        top_down_contour.append({"x_um": round(float(x_um), 1), "y_um": round(float(y_um), 1)})
    # Close teardrop with the opposite (+y then walk back already one-sided; mirror)
    mirrored = [{"x_um": pt["x_um"], "y_um": -pt["y_um"]} for pt in reversed(top_down_contour[1:-1])]
    top_down_contour = top_down_contour + mirrored

    longitudinal_contour = []
    for i in range(num_pts + 1):
        s = i / num_pts
        x_m = goldak_af_um * 1e-6 - (goldak_af_um + goldak_ar_um) * 1e-6 * s
        z_iso = _binary_extent(lambda z: T_field(x_m, 0.0, z) >= T_liq, 0.0, search_depth)
        z_depth = z_iso * depth_scale * 1e6
        longitudinal_contour.append({
            "x_um": round(float(x_m * 1e6), 1),
            "z_depth_um": round(float(z_depth), 1),
            "isKeyhole": keyhole_depth_um > 0 and abs(x_m) < (r_beam * 0.9)
        })

    transverse_contour = []
    for i in range(33):
        phi = (math.pi * i) / 32.0
        y_m = (goldak_b_um * 1e-6) * math.cos(phi)
        z_iso = _binary_extent(lambda z: T_field(0.0, y_m, z) >= T_liq, 0.0, search_depth)
        if regime.startswith("Keyhole"):
            z_pt = z_iso * depth_scale * (max(0.05, math.sin(phi)) ** 0.75)
        else:
            z_pt = z_iso * depth_scale
        transverse_contour.append({
            "y_um": round(float(y_m * 1e6), 1),
            "z_depth_um": round(float(z_pt * 1e6), 1)
        })

    T_haz = T_sol * 0.70
    nx_s, nz_s, ny_s = 36, 24, 28
    x_span = (-goldak_ar_um * 1.15, goldak_af_um * 1.15)
    y_span = (-goldak_b_um * 1.25, goldak_b_um * 1.25)
    z_span = (0.0, d_melt_um * 1.25)

    def T_xz(x_um, z_um):
        return T_field(x_um * 1e-6, 0.0, z_um * 1e-6)

    def T_yz(y_um, z_um):
        return T_field(0.0, y_um * 1e-6, z_um * 1e-6)

    if source not in ("eagar-tsai", "goldak"):
        try:
            from warp_thermal_solver import compute_rosenthal_slice_warp
            x_span_m = (x_span[0] * 1e-6, x_span[1] * 1e-6)
            z_span_m = (z_span[0] * 1e-6, z_span[1] * 1e-6)
            y_span_m = (y_span[0] * 1e-6, y_span[1] * 1e-6)
            
            slice_xz = compute_rosenthal_slice_warp(x_span_m, z_span_m, nx_s, nz_s, 1, 0.0, T_preheat, P_geom, k_th, v_scan, alpha_th, r_reg)
            slice_yz = compute_rosenthal_slice_warp(y_span_m, z_span_m, ny_s, nz_s, 2, 0.0, T_preheat, P_geom, k_th, v_scan, alpha_th, r_reg)
        except Exception as e:
            print(f"Warp thermal slice failed: {e}")
            slice_xz = sample_thermal_slice(T_xz, x_span, z_span, nx_s, nz_s)
            slice_yz = sample_thermal_slice(T_yz, y_span, z_span, ny_s, nz_s)
    else:
        slice_xz = sample_thermal_slice(T_xz, x_span, z_span, nx_s, nz_s)
        slice_yz = sample_thermal_slice(T_yz, y_span, z_span, ny_s, nz_s)

    thermal_slices = {
        "liquidus_C": T_liq,
        "solidus_C": T_sol,
        "haz_C": round(T_haz, 1),
        "xz": {
            "nx": nx_s,
            "nz": nz_s,
            "xMin_um": round(x_span[0], 1),
            "xMax_um": round(x_span[1], 1),
            "zMin_um": 0.0,
            "zMax_um": round(z_span[1], 1),
            "T_C": slice_xz
        },
        "yz": {
            "ny": ny_s,
            "nz": nz_s,
            "yMin_um": round(y_span[0], 1),
            "yMax_um": round(y_span[1], 1),
            "zMin_um": 0.0,
            "zMax_um": round(z_span[1], 1),
            "T_C": slice_yz
        }
    }

    # Transverse Multi-Track Overlap with left & right hatch lines
    hatch_val_um = float(hatch_spacing_um)
    overlap_tracks = [
        {"trackId": "Left Track (-1)", "y_center_um": -hatch_val_um, "contour": [{"y_um": round(pt["y_um"] - hatch_val_um, 1), "z_depth_um": pt["z_depth_um"]} for pt in transverse_contour]},
        {"trackId": "Current Track (0)", "y_center_um": 0.0, "contour": transverse_contour},
        {"trackId": "Right Track (+1)", "y_center_um": hatch_val_um, "contour": [{"y_um": round(pt["y_um"] + hatch_val_um, 1), "z_depth_um": pt["z_depth_um"]} for pt in transverse_contour]}
    ]

    # 13. Dynamic P-V Process Window Map (2D Grid: Power 50-600W, Speed 200-2500 mm/s)
    process_map_grid = []
    p_steps = np.array([80, 150, 220, 300, 380, 460, 540], dtype=np.float64)
    v_steps = np.array([300, 600, 900, 1200, 1600, 2000, 2400], dtype=np.float64)

    for p_val in p_steps:
        for v_val in v_steps:
            # Quick evaluation of regime
            v_m = float(v_val) * 1e-3
            denom_th = rho * cp_s * (T_liq - T_preheat) * math.sqrt(math.pi * alpha_solid * v_m * (r_beam ** 3))
            enth = (eta_base * float(p_val)) / max(1e-9, denom_th)
            
            # Width & Depth proxy
            eff_p = (1.0 - (1.0 - eta_base) ** 2.2) * float(p_val) if enth > ENTHALPY_TRANSITION else eta_base * float(p_val)
            w_m = math.sqrt(max(1e-12, (8.0 / (math.pi * math.e)) * (eff_p / (rho * cp * max(50.0, T_liq - T_preheat) * v_m))) + d_beam ** 2)
            w_um = w_m * 1e6
            
            if enth < ENTHALPY_TRANSITION:
                d_um = w_um * 0.45
                pt_regime = "Optimal Conduction"
                color_code = "#10b981"  # Emerald
            elif enth > ENTHALPY_KEYHOLE:
                d_um = w_um * 1.15
                pt_regime = "Keyhole Defect Zone"
                color_code = "#ef4444"  # Red
            else:
                d_um = w_um * 0.70
                pt_regime = "Transition"
                color_code = "#38bdf8"  # Sky

            # Check Lack of Fusion — Tang (h/W)^2+(t/D)^2
            tang_pt = (float(hatch_spacing_um) / max(1.0, w_um)) ** 2 + (
                float(layer_thickness_um) / max(1.0, d_um)
            ) ** 2
            if tang_pt > 1.0:
                pt_regime = "Lack of Fusion Zone"
                color_code = "#f59e0b"  # Amber
            # Check Balling
            elif (w_um * (1.6 + 0.55 * min(6.0, (v_m * w_m) / (2.0 * alpha_th)))) / max(1.0, w_um) > 3.8:
                pt_regime = "Balling Instability Zone"
                color_code = "#a855f7"  # Purple

            process_map_grid.append({
                "power_W": int(p_val),
                "speed_mm_s": int(v_val),
                "normalizedEnthalpy": round(enth, 2),
                "regime": pt_regime,
                "color": color_code,
                "width_um": round(w_um, 1),
                "depth_um": round(d_um, 1)
            })

    result = {
        "success": True,
        "engine": "MetalliX-Python-HPC-LPBF-MeltPool-v6.0",
        "modelId": heat_source_id,
        "heatSourceModel": heat_source_id,
        "material": material_name,
        "baseMetal": props["base"],
        "laserWavelength": laser_wavelength,
        "processParameters": {
            "laserPower_W": P_laser,
            "scanSpeed_mm_s": float(scan_speed_mm_s),
            "beamDiameter_um": float(beam_diameter_um),
            "preheatTemp_C": T_preheat,
            "layerThickness_um": float(layer_thickness_um),
            "hatchSpacing_um": float(hatch_spacing_um),
            "inclineAngle_deg": round(float(incline_angle_deg), 2),
            "processSeed": int(process_seed),
            "effectiveAbsorptivity": round(eta_eff, 3),
            "conductionAbsorptivity": round(eta_base, 3),
            "fabbroAbsorptivity": round(A_fabbro, 3),
            "effectiveConductivity_W_mK": round(k_th, 3),
            "effectiveSpecificHeat_J_kgK": round(cp, 1),
            "solidConductivity_W_mK": round(k_s, 3),
            "liquidConductivity_W_mK": round(k_l, 3),
            "kingUsesSolidThermophysics": True,
            "volumetricEnergyDensity_J_mm3": round(ved_J_mm3, 2),
            "linearEnergyDensity_J_m": round(led_J_m, 1),
            "peakIntensity_MW_cm2": round(peak_intensity_MW_cm2, 3),
            "normalizedEnthalpy": round(normalized_enthalpy, 2),
            "heatSource": source,
        },
        "meltPoolGeometry": {
            "length_um": round(l_melt_um, 1),
            "width_um": round(w_melt_um, 1),
            "depth_um": round(d_melt_um, 1),
            "aspectRatio_L_over_W": round(aspect_L_over_W, 2),
            "depthToWidthRatio_D_over_W": round(d_melt_um / max(1.0, w_melt_um), 2),
            "keyholeVaporCavityDepth_um": round(keyhole_depth_um, 1),
            "regime": regime,
            "goldakParameters": {
                "semiAxis_af_front_um": round(goldak_af_um, 1),
                "semiAxis_ar_rear_um": round(goldak_ar_um, 1),
                "semiAxis_b_halfwidth_um": round(goldak_b_um, 1),
                "semiAxis_c_depth_um": round(goldak_c_um, 1),
                "seed_af_um": round(goldak_seed["af_m"] * 1e6, 1),
                "seed_ar_um": round(goldak_seed["ar_m"] * 1e6, 1),
            }
        },
        "keyholeModel": {
            "modelId": FABBRO_MODEL_ID if source in ("eagar-tsai", "goldak") else "king-increment",
            "fabbroDepth_um": round(fabbro["depth_m"] * 1e6, 1),
            "aspectRatio_e_over_d": round(fabbro["aspectRatio_e_over_d"], 2),
            "peclet": round(fabbro["peclet"], 2),
            "absorptivity": round(A_fabbro, 3),
            "doi": fabbro["doi"],
        },
        "marangoniModel": {
            "modelId": MARANGONI_MODEL_ID,
            "flowDirection": ma["flowDirection"],
            "dGamma_dT_N_mK": round(ma["dGamma_dT_N_mK"], 6),
            "sulfur_ppm": round(ma["sulfur_ppm"], 1),
            "surfaceVelocity_m_s": round(ma["surfaceVelocity_m_s"], 3),
            "pecletMarangoni": round(ma["pecletMarangoni"], 2),
            "aspectNote": ma["aspectNote"],
            "doi": ma["doi"],
        },
        "hydrodynamicsAndRecoil": {
            "peakTemperature_C": round(t_peak_C, 1),
            "surfaceTemperature_C": round(t_surface_C, 1),
            "knudsenRecoilPressure_kPa": round(p_recoil_kPa, 2),
            "marangoniNumber": round(marangoni_number, 0),
            "marangoniGeometrySource": "thermal",
            "molarMass_kg_mol": round(M_molar, 5),
            "pecletThermalNumber": round(peclet_number, 2),
            "powderDenudationWidth_um": round(denudation_width_um, 1)
        },
        "geometricDefectScreen": defect_diagnostics(
            w_melt_um, d_melt_um, l_melt_um, float(hatch_spacing_um), float(layer_thickness_um)),
        "defectDiagnostics": {
            "lackOfFusionStatus": lof_status,
            "lackOfFusionRisk": lof_risk,
            "lackOfFusionOverlapIndex": round(lof_criterion_val, 3),
            "tangIndex_hW_tD": round(lof_criterion_val, 3),
            "hOverW": round(h_over_w, 3),
            "tOverD": round(t_over_d, 3),
            "keyholePorosityRisk": keyhole_porosity_risk,
            "ballingInstabilityRisk": balling_risk,
            "recoaterCrashRisk": recoater_risk,
            "effectiveResidualStress_MPa": round(effective_residual_stress_mpa, 1),
            "distortionIndex": round(distortion_index, 2)
        },
        "solidificationKinetics": {
            "modelId": SOLIDIFICATION_MODEL_ID,
            "gradientSource": sol.get("gradientSource"),
            "usedFieldMap": bool(sol.get("usedFieldMap")),
            "thermalGradient_G_K_m": round(thermal_gradient_G_K_m, 0),
            "thermalGradient_G_K_um": round(thermal_gradient_G_K_m * 1e-6, 3),
            "thermalGradientTail_G_K_m": round(float(sol.get("G_tail_K_m") or thermal_gradient_G_K_m), 0),
            "solidificationRate_R_m_s": round(solidification_rate_R_m_s, 3),
            "solidificationRate_R_mm_s": round(solidification_rate_R_m_s * 1e3, 1),
            "solidificationCosTheta": round(cos_theta, 4),
            "coolingRate_K_s": round(cooling_rate_K_s, 0),
            "coolingRate_log10": round(math.log10(max(10.0, cooling_rate_K_s)), 2),
            "g_over_r_ratio": round(g_over_r, 0),
            "microstructureMorphology": morphology,
            "primaryDendriteArmSpacing_PDAS_um": round(pdas_um, 2),
            "secondaryDendriteArmSpacing_SDAS_um": round(sdas_um, 2),
            "phaseTransformation": sol.get("phaseTransformation"),
            "frontPointCount": sol.get("frontPointCount"),
            "tail": sol.get("tail"),
            "bottom": sol.get("bottom"),
            "doi": sol.get("doi"),
            "disclaimer": sol.get("disclaimer"),
        },
        "geometricContours": {
            "topDownXY": top_down_contour,
            "longitudinalXZ": longitudinal_contour,
            "transverseYZ": transverse_contour,
            "multiTrackHatchOverlap": overlap_tracks
        },
        "thermalSlices": thermal_slices,
        "processWindowMap": {
            "currentOperatingPoint": {
                "power_W": P_laser,
                "speed_mm_s": float(scan_speed_mm_s),
                "regime": regime,
                "lofStatus": lof_status
            },
            "grid": process_map_grid
        }
    }
    if material_name == "Inconel 625":
        result["materialEvidence"] = {
            "propertySource": "lpbf_thermal_solver.SECONDARY_THERMOPHYSICAL_DB.Inconel 625",
            "provenanceClass": "legacy-estimated-secondary",
            "validationStatus": "unvalidated",
            "scope": "direct-meltpool-screening",
            "usesBoundedIN625Snapshot": False,
        }
    return result

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        print(json.dumps({
            "status": "ready",
            "engine": "MetalliX Python LPBF Thermal & Solidification Solver v4.0",
            "materials": list(THERMOPHYSICAL_DB.keys())
        }))
        sys.exit(0)
        
    try:
        if len(sys.argv) > 1 and sys.argv[1].strip().startswith("{"):
            data = json.loads(sys.argv[1])
        elif not sys.stdin.isatty():
            raw_input = sys.stdin.read()
            if raw_input.strip():
                data = json.loads(raw_input)
            else:
                data = {}
        else:
            data = {}
            
        mat = data.get("material", "Inconel 718")
        power = float(data.get("laserPower_W", 285.0))
        speed = float(data.get("scanSpeed_mm_s", 960.0))
        beam = float(data.get("beamDiameter_um", 80.0))
        preheat = float(data.get("preheatTemp_C", 80.0))
        layer = float(data.get("layerThickness_um", 40.0))
        hatch = float(data.get("hatchSpacing_um", 110.0))
        wavelength = data.get("laserWavelength", "IR_1064nm")
        heat_source = data.get("heatSource") or data.get("heat_source") or "rosenthal"
        sulfur_ppm = float(data.get("sulfur_ppm", data.get("sulfurPpm", 15.0)))
        
        t0 = time.time()
        result = calculate_meltpool_physics(
            mat, power, speed, beam, preheat, layer, hatch, wavelength,
            heat_source=heat_source,
            sulfur_ppm=sulfur_ppm,
        )
        result["computeTimeMs"] = round((time.time() - t0) * 1000.0, 1)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)
