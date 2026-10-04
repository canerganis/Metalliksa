#!/usr/bin/env python3
"""
MetalliX Advanced Battery & Corrosion EIS, DRT, and Degradation Solver
High-performance CPython 3.10+ electrochemistry engine for:
1. Distribution of Relaxation Times (DRT) Tikhonov-regularized continuous deconvolution
2. Multi-Cycle Battery EIS Aging, SEI Growth & Fast-Charge Lithium Plating Boundary
3. Corrosion EIS, ASTM G59 / G102 Polarization Resistance & Coating Degradation (Brasher-Kingsbury)
"""

import sys
import json
import math
import cmath
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
# 8.31446/96485.33.
R_GAS = physical_constants.GAS_CONSTANT_R.value  # J/(mol*K), exact
F_FARADAY = physical_constants.FARADAY.value  # C/mol, exact
# ASTM G102 K1 = 1e-6 * (s/yr = 365.25 * 86400) * 10 / F = 0.0032707148 mm*g/(uA*cm*yr),
# derived from the exact F (fix round item 6; was the printed 3.27e-3 / 0.00327).
ASTM_G102_K1_MM_G_UA_CM_YR = (1e-6 * 31557600.0 * 10.0) / F_FARADAY
ZERO_CELSIUS_K = physical_constants.ZERO_CELSIUS_K.value  # 273.15 K

# ==========================================
# 1. DRT (Distribution of Relaxation Times) Engine
# ==========================================

def compute_drt_spectrum(frequencies, z_real, z_imag, num_tau=60, lambda_reg=1e-3):
    """
    Deconvolves continuous distribution function gamma(ln tau) from complex impedance:
    Z(w) = R_inf + R_pol * integral[ gamma(ln tau) / (1 + j*w*tau) d(ln tau) ]
    Uses Tikhonov 1st-derivative regularization.
    """
    num_f = len(frequencies)
    if num_f < 5:
        return {"error": "Insufficient frequency points for DRT"}
    
    # Tau grid spanning 1/(2*pi*f_max) to 1/(2*pi*f_min)
    f_min = min(frequencies)
    f_max = max(frequencies)
    tau_min = 1.0 / (2.0 * math.pi * f_max)
    tau_max = 1.0 / (2.0 * math.pi * f_min)
    
    log_tau_min = math.log10(tau_min) - 0.5
    log_tau_max = math.log10(tau_max) + 0.5
    
    log_tau_grid = [log_tau_min + (log_tau_max - log_tau_min) * i / (num_tau - 1) for i in range(num_tau)]
    tau_grid = [10.0 ** lt for lt in log_tau_grid]
    d_log_tau = (log_tau_max - log_tau_min) / (num_tau - 1)
    
    # Estimate R_inf from highest frequency real impedance
    sorted_pairs = sorted(zip(frequencies, z_real, z_imag), key=lambda x: x[0], reverse=True)
    r_inf = max(0.0, sorted_pairs[0][1])
    
    # Build kernel matrices A_real and A_imag
    # Z_im(w) = -w * sum[ tau_k * gamma_k / (1 + (w*tau_k)^2) ] * d_ln_tau
    a_imag = []
    y_imag = []
    
    for f, zr, zi in zip(frequencies, z_real, z_imag):
        omega = 2.0 * math.pi * f
        minus_zi = -zi  # typically positive
        row = []
        for tau in tau_grid:
            wt = omega * tau
            denom = 1.0 + wt * wt
            kernel = (wt / denom) * math.log(10.0) * d_log_tau
            row.append(kernel)
        a_imag.append(row)
        y_imag.append(minus_zi)
        
    # Tikhonov Regularization Normal Equations: (A^T * A + lambda * L^T * L) * gamma = A^T * y
    # L is 1st-derivative matrix
    ata = [[0.0] * num_tau for _ in range(num_tau)]
    aty = [0.0] * num_tau
    
    for i in range(num_f):
        for k in range(num_tau):
            aty[k] += a_imag[i][k] * y_imag[i]
            for m in range(num_tau):
                ata[k][m] += a_imag[i][k] * a_imag[i][m]
                
    # Add 1st-order roughness penalty matrix L^T * L
    for k in range(num_tau):
        if k == 0:
            ata[k][k] += lambda_reg * 1.0
            if num_tau > 1:
                ata[k][k+1] += lambda_reg * (-1.0)
        elif k == num_tau - 1:
            ata[k][k] += lambda_reg * 1.0
            ata[k][k-1] += lambda_reg * (-1.0)
        else:
            ata[k][k] += lambda_reg * 2.0
            ata[k][k-1] += lambda_reg * (-1.0)
            ata[k][k+1] += lambda_reg * (-1.0)
            
    # Simple Gauss-Seidel / Positive Least Squares solver
    gamma = [0.1] * num_tau
    for _ in range(250):
        for k in range(num_tau):
            sum_other = sum(ata[k][m] * gamma[m] for m in range(num_tau) if m != k)
            diag = ata[k][k] + 1e-12
            val = (aty[k] - sum_other) / diag
            gamma[k] = max(0.0, val) # enforce non-negative distribution
            
    # Identify Peaks & Assign Physical Electrochemistry Mechanisms
    peaks = []
    for k in range(1, num_tau - 1):
        if gamma[k] > gamma[k-1] and gamma[k] > gamma[k+1] and gamma[k] > max(gamma) * 0.05:
            tau_p = tau_grid[k]
            f_p = 1.0 / (2.0 * math.pi * tau_p)
            height = gamma[k]
            
            # Physical classification based on relaxation time
            if tau_p < 1e-4:
                process = "High-Freq Interphase / SEI Migration / Bulk Electrolyte"
                domain = "Interphase Transport"
            elif 1e-4 <= tau_p < 0.1:
                process = "Mid-Freq Charge Transfer (Faradaic Kinetics & Double Layer)"
                domain = "Charge Transfer (R_ct || C_dl)"
            else:
                process = "Low-Freq Solid-State Li+ Diffusion / Mass Transport"
                domain = "Warburg / Porous Diffusion"
                
            peaks.append({
                "tau_s": tau_p,
                "logTau": log_tau_grid[k],
                "charFreq_Hz": f_p,
                "gammaHeight_Ohm": round(height, 4),
                "process": process,
                "domain": domain
            })
            
    # Format DRT Curve points
    drt_curve = []
    for lt, tau, g in zip(log_tau_grid, tau_grid, gamma):
        drt_curve.append({
            "logTau": round(lt, 3),
            "tau_s": tau,
            "charFreq_Hz": 1.0 / (2.0 * math.pi * tau),
            "gamma_Ohm": round(g, 4)
        })
        
    return {
        "r_inf": round(r_inf, 4),
        "lambda_reg": lambda_reg,
        "drtCurve": drt_curve,
        "identifiedPeaks": peaks
    }

# ==========================================
# 2. Battery Multi-Cycle Degradation & Fast-Charging Plating Model
# ==========================================

def simulate_p2d_continuum_profiles(chemistry_id, c_rate, temp_c, soc=0.5, custom_params=None):
    """
    Solves 1D through-thickness continuum transport (P2D framework):
    - Liquid electrolyte salt concentration c_e(x)
    - Liquid potential Phi_e(x)
    - Solid particle surface stoichiometry theta_surf(x)
    - Local overpotential and through-plane lithium plating risk eta_plating(x)
    """
    if custom_params is None:
        custom_params = {}
        
    t_k = temp_c + ZERO_CELSIUS_K
    f_const = F_FARADAY # C/mol, exact (was 96485.332)
    r_gas = R_GAS # J/(mol*K), exact (was 8.314)
    
    # Standard cell geometry (microns)
    l_neg = custom_params.get("l_neg_um", 85.0) # Anode thickness
    l_sep = custom_params.get("l_sep_um", 20.0) # Separator thickness
    l_pos = custom_params.get("l_pos_um", 75.0) # Cathode thickness
    l_total = l_neg + l_sep + l_pos
    
    # Porosity & Bruggeman
    eps_neg = custom_params.get("eps_neg", 0.32)
    eps_sep = custom_params.get("eps_sep", 0.45)
    eps_pos = custom_params.get("eps_pos", 0.28)
    
    # Diffusion coefficients (m^2/s) with Arrhenius
    d_e_bulk = 3.5e-10 * math.exp(2400.0 * (1.0/298.15 - 1.0/t_k)) # Liquid electrolyte
    d_s_neg = 3.0e-14 * math.exp(4200.0 * (1.0/298.15 - 1.0/t_k))  # Solid graphite
    d_s_pos = 1.2e-14 * math.exp(4500.0 * (1.0/298.15 - 1.0/t_k))  # Solid cathode
    
    # Electrolyte conductivity (S/m)
    kappa_bulk = 1.1 * math.exp(1600.0 * (1.0/298.15 - 1.0/t_k))
    t_plus = 0.38 # Li+ transference number
    
    # Effective properties via Bruggeman: prop_eff = prop * eps^1.5
    d_e_eff_neg = d_e_bulk * (eps_neg ** 1.5)
    d_e_eff_sep = d_e_bulk * (eps_sep ** 1.5)
    d_e_eff_pos = d_e_bulk * (eps_pos ** 1.5)
    
    kappa_eff_neg = kappa_bulk * (eps_neg ** 1.5)
    kappa_eff_sep = kappa_bulk * (eps_sep ** 1.5)
    kappa_eff_pos = kappa_bulk * (eps_pos ** 1.5)
    
    # Current density (A/m^2)
    # 1C approx = 30 A/m^2 for standard 3 mAh/cm^2 loading
    nominal_areal_cap = custom_params.get("areal_cap_mah_cm2", 3.2) # mAh/cm^2
    j_app = (c_rate * nominal_areal_cap * 10.0) # A/m^2 (positive for charge, negative for discharge)
    
    # Spatial mesh points
    n_pts_neg = 25
    n_pts_sep = 10
    n_pts_pos = 25
    
    x_coords = []
    zones = []
    c_e_profiles = []
    phi_e_profiles = []
    theta_surf_profiles = []
    eta_plating_profiles = []
    j_loc_profiles = []
    
    c_e_bulk = 1000.0 # mol/m^3 (1.0 M)
    
    # Approximate steady-state analytical/finite difference continuum solution
    # Liquid salt concentration gradient: grad(c_e) = - (1 - t+) * i / (F * D_e_eff)
    
    # 1. Anode Region (0 to L_neg)
    for i in range(n_pts_neg):
        x = (i / (n_pts_neg - 1)) * l_neg
        x_m = x * 1e-6
        x_coords.append(round(x, 2))
        zones.append("Anode (Graphite/Si)")
        
        # Current in electrolyte increases from 0 at current collector (x=0) to j_app at separator (x=L_neg)
        i_e = j_app * (x / l_neg)
        j_loc_profiles.append(round(j_app / (l_neg * 1e-6) * 1e-6, 3)) # A/cm^3
        
        # Delta c_e in anode
        # Integrated: c_e(x) = c_e(0) - (1 - t+) * j_app * x^2 / (2 * L_neg * F * D_e_eff)
        delta_c = - (1.0 - t_plus) * j_app * (x_m ** 2) / (2.0 * (l_neg * 1e-6) * f_const * d_e_eff_neg + 1e-20)
        c_val = max(50.0, min(2800.0, c_e_bulk + delta_c))
        c_e_profiles.append(round(c_val / 1000.0, 3)) # in M (mol/L)
        
        # Phi_e potential
        delta_phi_e = - (j_app * (x_m ** 2) / (2.0 * (l_neg * 1e-6) * kappa_eff_neg + 1e-20))
        phi_e_profiles.append(round(delta_phi_e, 4))
        
        # Solid surface stoichiometry during charge
        # Higher intercalation near separator
        theta_local = min(0.98, max(0.02, soc + (j_app / 30.0) * 0.15 * (x / l_neg)))
        theta_surf_profiles.append(round(theta_local, 3))
        
        # Anode equilibrium potential (Graphite stages)
        u_eq_anode = 0.063 + 0.08 * math.exp(-35.0 * theta_local) + 0.05 * (1.0 - theta_local) ** 2
        
        # Local overpotential for lithium plating during charge
        # eta_plating = Phi_s - Phi_e - U_eq(Li/Li+)
        # Solid phase Phi_s ~ 0 (ground at anode current collector)
        # Activation overpotential (Butler-Volmer): eta_act ~ asinh(...)
        eta_act = (r_gas * t_k / (0.5 * f_const)) * math.asinh(abs(j_app) / (2.0 * 25.0 + 1e-10))
        if j_app > 0: # Charging
            local_anode_pot = u_eq_anode - delta_phi_e - (eta_act if j_app > 0 else -eta_act)
        else: # Discharging
            local_anode_pot = u_eq_anode - delta_phi_e + eta_act
            
        eta_plating_profiles.append(round(local_anode_pot, 4))
        
    c_e_at_sep_left = c_e_profiles[-1] * 1000.0
    phi_e_at_sep_left = phi_e_profiles[-1]
    
    # 2. Separator Region (L_neg to L_neg + L_sep)
    for i in range(1, n_pts_sep):
        x = l_neg + (i / n_pts_sep) * l_sep
        x_m_rel = (i / n_pts_sep) * l_sep * 1e-6
        x_coords.append(round(x, 2))
        zones.append("Separator")
        j_loc_profiles.append(0.0)
        
        # Full current passes through separator
        delta_c_sep = - (1.0 - t_plus) * j_app * x_m_rel / (f_const * d_e_eff_sep + 1e-20)
        c_val = max(50.0, min(2800.0, c_e_at_sep_left + delta_c_sep))
        c_e_profiles.append(round(c_val / 1000.0, 3))
        
        delta_phi_sep = phi_e_at_sep_left - (j_app * x_m_rel / (kappa_eff_sep + 1e-20))
        phi_e_profiles.append(round(delta_phi_sep, 4))
        theta_surf_profiles.append(None)
        eta_plating_profiles.append(None)
        
    c_e_at_sep_right = c_e_profiles[-1] * 1000.0
    phi_e_at_sep_right = phi_e_profiles[-1]
    
    # 3. Cathode Region (L_neg + L_sep to L_total)
    for i in range(1, n_pts_pos + 1):
        x = l_neg + l_sep + (i / n_pts_pos) * l_pos
        x_rel = (i / n_pts_pos) * l_pos
        x_m_rel = x_rel * 1e-6
        x_coords.append(round(x, 2))
        zones.append("Cathode (NMC/LFP)")
        j_loc_profiles.append(round(-j_app / (l_pos * 1e-6) * 1e-6, 3))
        
        # Current in electrolyte decreases from j_app at separator to 0 at cathode current collector
        delta_c_pos = - (1.0 - t_plus) * j_app * (x_m_rel - (x_m_rel**2)/(2.0 * (l_pos * 1e-6))) / (f_const * d_e_eff_pos + 1e-20)
        c_val = max(50.0, min(2800.0, c_e_at_sep_right + delta_c_pos))
        c_e_profiles.append(round(c_val / 1000.0, 3))
        
        delta_phi_pos = phi_e_at_sep_right - (j_app * (x_m_rel - (x_m_rel**2)/(2.0 * (l_pos * 1e-6))) / (kappa_eff_pos + 1e-20))
        phi_e_profiles.append(round(delta_phi_pos, 4))
        
        # Cathode de-intercalation during charge
        theta_pos = min(0.98, max(0.15, (1.0 - soc) - (j_app / 30.0) * 0.12 * (1.0 - x_rel / l_pos)))
        theta_surf_profiles.append(round(theta_pos, 3))
        
        # Cathode equilibrium potential vs Li
        u_eq_pos = 4.15 - 0.5 * (1.0 - theta_pos) ** 1.8
        eta_plating_profiles.append(round(u_eq_pos - delta_phi_pos, 4))
        
    # Analysis & Key Plating Metrics
    min_anode_potential = min([p for p in eta_plating_profiles[:n_pts_neg] if p is not None])
    min_anode_loc_idx = eta_plating_profiles[:n_pts_neg].index(min_anode_potential)
    min_anode_x_um = x_coords[min_anode_loc_idx]
    
    plating_status = "Safe (No Plating)"
    if min_anode_potential < 0.0:
        plating_status = "CRITICAL: Active Lithium Dendrite Plating"
    elif min_anode_potential < 0.030:
        plating_status = "Warning: Approaching Plating Nucleation Limit"
        
    salt_depletion_risk = "Optimal"
    min_c_e = min(c_e_profiles)
    if min_c_e < 0.2:
        salt_depletion_risk = "Severe Liquid Salt Depletion (< 0.2 M)"
    elif min_c_e < 0.5:
        salt_depletion_risk = "Moderate Mass-Transfer Limitation (< 0.5 M)"
        
    return {
        "x_coords_um": x_coords,
        "zones": zones,
        "c_e_M": c_e_profiles,
        "phi_e_V": phi_e_profiles,
        "theta_surf": theta_surf_profiles,
        "eta_plating_V": eta_plating_profiles,
        "j_loc_A_cm3": j_loc_profiles,
        "summary": {
            "c_rate": c_rate,
            "temp_c": temp_c,
            "soc": soc,
            "min_anode_potential_V": min_anode_potential,
            "min_anode_x_um": min_anode_x_um,
            "plating_status": plating_status,
            "salt_depletion_risk": salt_depletion_risk,
            "min_c_e_M": min_c_e,
            "max_c_e_M": max(c_e_profiles),
            "electrolyte_ir_drop_V": round(abs(phi_e_profiles[-1] - phi_e_profiles[0]), 4)
        }
    }


# ==========================================
# 3. Mechanistic Degradation Mode Deconvolution (LLI / LAM_PE / LAM_NE)
# ==========================================

def deconvolve_lli_lam_degradation(chemistry_id, initial_cap_ah, degraded_cap_ah, lli_pct=None, lam_pe_pct=None, lam_ne_pct=None):
    """
    Deconvolves battery aging into fundamental thermodynamic degradation modes:
    - LLI: Loss of Lithium Inventory (SEI formation, Li plating)
    - LAM_PE: Loss of Active Material at Positive Electrode (Cracking, TM dissolution)
    - LAM_NE: Loss of Active Material at Negative Electrode (Exfoliation, isolation)
    Generates synthetic high-resolution dQ/dV and V(Q) full-cell & half-cell curves.
    """
    # If parameters not provided, estimate based on realistic aging trajectories
    cap_retention = degraded_cap_ah / initial_cap_ah
    tot_loss_pct = max(0.0, (1.0 - cap_retention) * 100.0)
    
    if lli_pct is None:
        # Typical commercial Li-ion: LLI dominates early life (60%), LAM_PE (25%), LAM_NE (15%)
        lli_pct = min(100.0, tot_loss_pct * 0.65)
    if lam_pe_pct is None:
        lam_pe_pct = min(100.0, tot_loss_pct * 0.22)
    if lam_ne_pct is None:
        lam_ne_pct = min(100.0, tot_loss_pct * 0.13)
        
    # Baseline Capacities
    q_pe_fresh = initial_cap_ah * 1.12 # Positive electrode oversized ~ 12%
    q_ne_fresh = initial_cap_ah * 1.22 # Negative electrode oversized (N/P ratio ~ 1.10 - 1.20)
    q_li_fresh = initial_cap_ah * 1.05 # Initial cyclable lithium
    
    # Degraded Capacities
    q_pe_aged = q_pe_fresh * (1.0 - lam_pe_pct / 100.0)
    q_ne_aged = q_ne_fresh * (1.0 - lam_ne_pct / 100.0)
    q_li_aged = q_li_fresh * (1.0 - lli_pct / 100.0)
    
    # Synthetic OCV curve functions (Half-cells vs Li/Li+)
    def ocv_pe(theta):
        # Positive electrode (NMC-like)
        t = max(0.01, min(0.99, theta))
        return 4.28 - 0.45 * (1.0 - t)**1.2 - 0.12 * math.exp(-30.0 * (1.0 - t)) + 0.08 * math.sin(math.pi * t)
        
    def ocv_ne(theta):
        # Negative electrode (Graphite stages: Stage 1, 2, 3, 4)
        t = max(0.01, min(0.99, theta))
        # Staging transitions in graphite
        v_base = 0.075 + 0.05 * math.exp(-40.0 * t) + 0.04 * (1.0 - t)**3.0
        v_stage1 = 0.035 / (1.0 + math.exp((t - 0.52) / 0.025))
        v_stage2 = 0.045 / (1.0 + math.exp((t - 0.22) / 0.03))
        return v_base + v_stage1 + v_stage2
        
    # Generate full-cell discharge curves for Fresh and Aged
    q_grid = [initial_cap_ah * (i / 199.0) for i in range(200)]
    
    fresh_curves = []
    aged_curves = []
    
    for q in q_grid:
        # Fresh
        theta_pe_fresh = max(0.02, min(0.98, 1.0 - q / q_pe_fresh))
        theta_ne_fresh = max(0.02, min(0.98, (q_li_fresh - q) / q_ne_fresh))
        v_pe_f = ocv_pe(theta_pe_fresh)
        v_ne_f = ocv_ne(theta_ne_fresh)
        v_cell_f = max(2.5, min(4.35, v_pe_f - v_ne_f))
        
        fresh_curves.append({
            "q_ah": round(q, 3),
            "v_cell": round(v_cell_f, 4),
            "v_pe": round(v_pe_f, 4),
            "v_ne": round(v_ne_f, 4)
        })
        
        # Aged
        # Slippage from LLI causes misalignment between PE and NE stoichiometry windows
        theta_pe_aged = max(0.02, min(0.98, 1.0 - q / q_pe_aged))
        theta_ne_aged = max(0.02, min(0.98, (q_li_aged - q) / q_ne_aged))
        v_pe_a = ocv_pe(theta_pe_aged)
        v_ne_a = ocv_ne(theta_ne_aged)
        v_cell_a = max(2.5, min(4.35, v_pe_a - v_ne_a - 0.035)) # with IR drop
        
        aged_curves.append({
            "q_ah": round(q, 3),
            "v_cell": round(v_cell_a, 4),
            "v_pe": round(v_pe_a, 4),
            "v_ne": round(v_ne_a, 4)
        })
        
    # Calculate dQ/dV spectra for Fresh and Aged
    dq_dv_fresh = []
    dq_dv_aged = []
    
    for i in range(2, len(fresh_curves) - 2):
        dq_f = fresh_curves[i+1]["q_ah"] - fresh_curves[i-1]["q_ah"]
        dv_f = fresh_curves[i-1]["v_cell"] - fresh_curves[i+1]["v_cell"] # discharge
        if abs(dv_f) > 1e-4:
            dq_dv_val_f = dq_f / dv_f
            if 0 < dq_dv_val_f < 35.0:
                dq_dv_fresh.append({
                    "v_cell": fresh_curves[i]["v_cell"],
                    "dq_dv": round(dq_dv_val_f, 3)
                })
                
    for i in range(2, len(aged_curves) - 2):
        dq_a = aged_curves[i+1]["q_ah"] - aged_curves[i-1]["q_ah"]
        dv_a = aged_curves[i-1]["v_cell"] - aged_curves[i+1]["v_cell"]
        if abs(dv_a) > 1e-4:
            dq_dv_val_a = dq_a / dv_a
            if 0 < dq_dv_val_a < 35.0:
                dq_dv_aged.append({
                    "v_cell": aged_curves[i]["v_cell"],
                    "dq_dv": round(dq_dv_val_a, 3)
                })
                
    # Sort by voltage ascending for chart plotting
    dq_dv_fresh = sorted(dq_dv_fresh, key=lambda p: p["v_cell"])
    dq_dv_aged = sorted(dq_dv_aged, key=lambda p: p["v_cell"])
    
    return {
        "chemistryId": chemistry_id,
        "initialCap_Ah": initial_cap_ah,
        "degradedCap_Ah": degraded_cap_ah,
        "modes": {
            "lli_pct": round(lli_pct, 2),
            "lam_pe_pct": round(lam_pe_pct, 2),
            "lam_ne_pct": round(lam_ne_pct, 2),
            "np_ratio_fresh": round(q_ne_fresh / q_pe_fresh, 3),
            "np_ratio_aged": round(q_ne_aged / q_pe_aged, 3)
        },
        "freshCurves": fresh_curves,
        "agedCurves": aged_curves,
        "dqDvFresh": dq_dv_fresh,
        "dqDvAged": dq_dv_aged,
        "diagnosis": {
            "primaryDegradationMode": "Loss of Lithium Inventory (LLI)" if lli_pct > max(lam_pe_pct, lam_ne_pct) else ("Loss of Positive Active Material (LAM_PE)" if lam_pe_pct > lam_ne_pct else "Loss of Negative Active Material (LAM_NE)"),
            "mechanism": "Thickening SEI passivation crust and dead lithium trapping" if lli_pct > 15.0 else "Electrode particle lattice fatigue and micro-cracking",
            "recommendedMitigation": "Reduce maximum charging upper cutoff voltage by 50 mV or decrease fast-charge C-rate at low temperatures (<15°C)"
        }
    }


# ==========================================
# 4. Bernardi Multiphysics Thermal & Heat Generation Model
# ==========================================

def simulate_bernardi_thermal_multiphysics(cell_format, nominal_cap_ah, c_rate, cooling_type, temp_ambient_c=25.0, internal_r_mohm=18.0):
    """
    Multiphysics thermal solver using the Bernardi equation:
    Q_dot = I^2 * R_ohm + I * T * (dU_ocv / dT) + I * eta_pol
    Computes core temperature, surface temperature, radial gradient, and cooling requirements.
    """
    current_a = c_rate * nominal_cap_ah
    r_internal = internal_r_mohm * 1e-3 # Ohms
    
    # Cell Geometry & Mass Specifications based on Form Factor
    specs = {
        "21700-cylindrical": {"mass_kg": 0.070, "radius_m": 0.0105, "height_m": 0.070, "cp_j_kgk": 950.0, "k_radial": 1.2, "k_axial": 28.0, "area_m2": 0.0053},
        "4680-tabless": {"mass_kg": 0.355, "radius_m": 0.023, "height_m": 0.080, "cp_j_kgk": 980.0, "k_radial": 1.5, "k_axial": 45.0, "area_m2": 0.0148},
        "prismatic-60ah": {"mass_kg": 1.850, "width_m": 0.148, "height_m": 0.098, "depth_m": 0.040, "cp_j_kgk": 1020.0, "k_radial": 1.1, "k_axial": 25.0, "area_m2": 0.048},
        "pouch-40ah": {"mass_kg": 0.920, "width_m": 0.220, "height_m": 0.150, "depth_m": 0.008, "cp_j_kgk": 1100.0, "k_radial": 0.8, "k_axial": 32.0, "area_m2": 0.072}
    }
    
    cell_spec = specs.get(cell_format, specs["21700-cylindrical"])
    mass = cell_spec["mass_kg"]
    cp = cell_spec["cp_j_kgk"]
    area = cell_spec["area_m2"]
    
    # Heat transfer coefficient h (W / (m^2 * K))
    h_cooling = {
        "natural_air": 12.0,
        "forced_air": 45.0,
        "bottom_cold_plate": 280.0,
        "direct_dielectric_immersion": 850.0
    }.get(cooling_type, 15.0)
    
    # Entropic coefficient dU/dT (V/K)
    # Typically negative during discharge (-0.15 to -0.30 mV/K) -> Endothermic early, Exothermic late
    du_dt = -0.22e-3 # V/K
    
    # Time discretization for full discharge
    discharge_time_s = (3600.0 / c_rate) if c_rate > 0 else 3600.0
    num_steps = 60
    dt = discharge_time_s / num_steps
    
    t_core = temp_ambient_c + ZERO_CELSIUS_K
    t_surf = temp_ambient_c + ZERO_CELSIUS_K
    
    thermal_timeline = []
    
    q_joule_total_wh = 0.0
    q_rev_total_wh = 0.0
    q_pol_total_wh = 0.0
    
    for step in range(num_steps + 1):
        t_sec = step * dt
        soc = max(0.0, 1.0 - (step / num_steps))
        
        # 1. Ohmic Heat: Q_joule = I^2 * R
        q_dot_joule = (current_a ** 2) * r_internal # Watts
        
        # 2. Reversible Entropic Heat: Q_rev = - I * T * (dU/dT)
        # Note: I > 0 for discharge
        q_dot_rev = - current_a * t_core * du_dt # Watts
        
        # 3. Polarization Overpotential Heat: Q_pol = I * eta_pol
        # Overpotential rises at low SOC and high C-rate
        eta_pol = (0.02 + 0.08 * (1.0 - soc)**2.5) * (c_rate / 1.0)
        q_dot_pol = current_a * eta_pol
        
        q_dot_total = q_dot_joule + q_dot_rev + q_dot_pol
        
        # Heat dissipation to ambient: Q_out = h * A * (T_surf - T_amb)
        q_dot_dissipated = h_cooling * area * (t_surf - (temp_ambient_c + ZERO_CELSIUS_K))
        
        # Internal thermal conduction resistance (core to surface)
        r_th_internal = 0.45 / (cell_spec["k_radial"] * area + 1e-6) # K/W
        
        # Differential equations
        # Core: (m * Cp / 2) * dT_core/dt = Q_total - (T_core - T_surf)/R_th
        # Surface: (m * Cp / 2) * dT_surf/dt = (T_core - T_surf)/R_th - Q_dissipated
        q_conduction = (t_core - t_surf) / r_th_internal
        
        dT_core = (q_dot_total - q_conduction) / (mass * cp * 0.6) * dt
        dT_surf = (q_conduction - q_dot_dissipated) / (mass * cp * 0.4) * dt
        
        t_core += dT_core
        t_surf += dT_surf
        
        q_joule_total_wh += (q_dot_joule * dt) / 3600.0
        q_rev_total_wh += (q_dot_rev * dt) / 3600.0
        q_pol_total_wh += (q_dot_pol * dt) / 3600.0
        
        thermal_timeline.append({
            "time_s": round(t_sec, 1),
            "soc": round(soc, 3),
            "t_core_c": round(t_core - ZERO_CELSIUS_K, 2),
            "t_surface_c": round(t_surf - ZERO_CELSIUS_K, 2),
            "delta_t_c": round(t_core - t_surf, 2),
            "q_joule_w": round(q_dot_joule, 2),
            "q_rev_w": round(q_dot_rev, 2),
            "q_pol_w": round(q_dot_pol, 2),
            "q_total_w": round(q_dot_total, 2),
            "q_dissipated_w": round(q_dot_dissipated, 2)
        })
        
    max_t_core = max(p["t_core_c"] for p in thermal_timeline)
    max_delta_t = max(p["delta_t_c"] for p in thermal_timeline)
    peak_heat_w = max(p["q_total_w"] for p in thermal_timeline)
    
    thermal_risk = "Safe Thermal Zone (< 45°C)"
    if max_t_core > 75.0:
        thermal_risk = "CRITICAL: Accelerated Thermal Runaway Risk (> 75°C)"
    elif max_t_core > 55.0:
        thermal_risk = "Warning: Accelerated SEI Decomposition & Aging (> 55°C)"
    elif max_delta_t > 8.0:
        thermal_risk = "Warning: High Core-to-Surface Temperature Gradient (> 8°C)"
        
    return {
        "cellFormat": cell_format,
        "nominalCap_Ah": nominal_cap_ah,
        "cRate": c_rate,
        "coolingType": cooling_type,
        "ambientTemp_C": temp_ambient_c,
        "peakHeatGen_W": round(peak_heat_w, 2),
        "maxCoreTemp_C": round(max_t_core, 2),
        "maxSurfaceTemp_C": round(max(p["t_surface_c"] for p in thermal_timeline), 2),
        "maxDeltaT_C": round(max_delta_t, 2),
        "totalHeatGenerated_Wh": round(q_joule_total_wh + q_rev_total_wh + q_pol_total_wh, 2),
        "jouleHeatSharePct": round((q_joule_total_wh / (q_joule_total_wh + q_rev_total_wh + q_pol_total_wh + 1e-9)) * 100.0, 1),
        "thermalRiskAssessment": thermal_risk,
        "timeline": thermal_timeline
    }

def simulate_battery_degradation_and_eis(chemistry_id, initial_params, cycles, temp_c, charge_c_rate):
    """
    Simulates multi-cycle SEI growth, transition metal dissolution, impedance rise,
    and fast-charging lithium plating risk over cycling.
    """
    t_kelvin = temp_c + ZERO_CELSIUS_K
    r_gas = R_GAS # J/(mol*K), exact (was 8.314)
    
    # Baseline Parameters
    r0_base = initial_params.get("r0_ohm", 0.12)
    r_sei_base = initial_params.get("rSei_ohm", 0.35)
    r_ct_base = initial_params.get("rCt_ohm", 0.85)
    c_sei_base = initial_params.get("cSei_uF", 12.0)
    c_dl_base = initial_params.get("cDl_uF", 45.0)
    sigma_base = initial_params.get("warburgSigma", 5.0)
    
    # Activation energies (J/mol)
    ea_sei = 42000.0 # SEI growth activation energy
    ea_ct = 55000.0  # Charge transfer activation energy
    ea_r0 = 15000.0  # Ohmic ionic transport activation energy
    
    # Temperature scaling factors (Arrhenius)
    arrh_r0 = math.exp((ea_r0 / r_gas) * (1.0 / t_kelvin - 1.0 / 298.15))
    arrh_ct = math.exp((ea_ct / r_gas) * (1.0 / t_kelvin - 1.0 / 298.15))
    
    # Cycles timeline
    cycle_checkpoints = [1, 50, 100, 200, 500, 1000, 1500, max(2000, cycles)]
    cycle_checkpoints = sorted(list(set([c for c in cycle_checkpoints if c <= max(cycles, 2000)])))
    if cycles not in cycle_checkpoints:
        cycle_checkpoints.append(cycles)
        cycle_checkpoints.sort()
        
    evolution_data = []
    
    for n in cycle_checkpoints:
        # SEI Parabolic Growth Law: delta_R_sei ~ k * sqrt(n)
        k_sei = 0.018 * math.exp(-(ea_sei / r_gas) * (1.0 / t_kelvin - 1.0 / 298.15))
        r_sei_n = (r_sei_base + k_sei * math.sqrt(n)) * arrh_r0
        
        # Charge transfer resistance rise from cathode microcracking & CEI
        alpha_ct = 0.0012
        r_ct_n = (r_ct_base * (1.0 + alpha_ct * (n ** 0.72))) * arrh_ct
        
        # Ohmic growth from electrolyte dry-out
        r0_n = (r0_base * (1.0 + 0.00015 * n)) * arrh_r0
        
        # Capacity loss & SOH
        k_loss = 0.0042 * math.exp(0.035 * (temp_c - 25.0))
        cap_retention_pct = max(0.0, 100.0 - (k_loss * math.sqrt(n) + 0.012 * (n / 100.0) ** 1.3))
        soh_pct = max(0.0, min(100.0, cap_retention_pct))
        
        # Total internal DC resistance
        r_internal_total = r0_n + r_sei_n + r_ct_n
        
        # Fast-Charge Lithium Plating Risk Analysis
        # Anode overpotential: eta_anode = E_eq,anode - I_charge * (R_SEI + R_ct)
        # In Li-ion graphite anode, E_eq ~ 0.08 - 0.12 V vs Li/Li+ at 50% SOC
        e_eq_anode = 0.095 # V vs Li/Li+
        i_charge_norm = charge_c_rate * 1.5 # normalized current density proxy
        eta_anode_overpotential = i_charge_norm * (r_sei_n * 0.4 + r_ct_n * 0.6)
        e_anode_potential = e_eq_anode - eta_anode_overpotential
        
        plating_risk = "Safe (No Plating)"
        if e_anode_potential <= 0.0:
            plating_risk = "CRITICAL: Active Lithium Dendrite Plating"
        elif e_anode_potential < 0.035:
            plating_risk = "Warning: High Nucleation Plating Risk"
            
        evolution_data.append({
            "cycle": n,
            "sohPct": round(soh_pct, 2),
            "r0_ohm": round(r0_n, 4),
            "rSei_ohm": round(r_sei_n, 4),
            "rCt_ohm": round(r_ct_n, 4),
            "rTotal_ohm": round(r_internal_total, 4),
            "anodePotential_V": round(e_anode_potential, 4),
            "platingRisk": plating_risk
        })
        
    # Generate Synthetic Multi-Cycle Nyquist Spectra for Cycle 1, 500, 1500
    nyquist_multi_cycle = []
    test_freqs = [10.0 ** (4.0 - 6.0 * i / 49.0) for i in range(50)] # 10 kHz down to 10 mHz
    
    for cp in [1, min(500, cycles), min(1500, cycles)]:
        target_stage = next((ev for ev in evolution_data if ev["cycle"] == cp), evolution_data[0])
        r0 = target_stage["r0_ohm"]
        r_sei = target_stage["rSei_ohm"]
        r_ct = target_stage["rCt_ohm"]
        c_sei = c_sei_base * 1e-6
        c_dl = c_dl_base * 1e-6
        sigma = sigma_base * (1.0 + 0.0003 * cp)
        
        spectrum = []
        for f in test_freqs:
            omega = 2.0 * math.pi * f
            j = 1j
            z_r0 = complex(r0, 0.0)
            
            # SEI RC loop
            z_sei_c = 1.0 / (j * omega * c_sei + 1e-30)
            z_sei = (complex(r_sei, 0.0) * z_sei_c) / (complex(r_sei, 0.0) + z_sei_c)
            
            # Charge transfer + Warburg
            sqrt_w = math.sqrt(omega)
            z_w = complex(sigma / sqrt_w, -sigma / sqrt_w)
            z_faradaic = complex(r_ct, 0.0) + z_w
            z_dl_c = 1.0 / (j * omega * c_dl + 1e-30)
            z_ct_loop = (z_faradaic * z_dl_c) / (z_faradaic + z_dl_c)
            
            z_total = z_r0 + z_sei + z_ct_loop
            spectrum.append({
                "frequency": round(f, 3),
                "zReal": round(z_total.real, 4),
                "minusZImag": round(-z_total.imag, 4)
            })
            
        nyquist_multi_cycle.append({
            "cycle": cp,
            "soh": target_stage["sohPct"],
            "spectrum": spectrum
        })
        
    return {
        "chemistryId": chemistry_id,
        "temperatureC": temp_c,
        "chargeCRate": charge_c_rate,
        "evolution": evolution_data,
        "nyquistMultiCycle": nyquist_multi_cycle,
        "maxSafeCRate": round(max(0.2, (0.095 / (r_sei_base * 0.4 + r_ct_base * 0.6)) / 1.5), 2)
    }

# ==========================================
# 3. Corrosion EIS, ASTM G59 & Coating Degradation Model
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


def simulate_corrosion_eis_and_kinetics(metal_id, beta_a, beta_c, i0_corr_ua_cm2, e_pit_v, e0_v, exposure_days=90):
    """
    Simulates electrochemical corrosion polarization resistance (ASTM G59),
    Faraday penetration rate (ASTM G102), and protective coating EIS water uptake.

    The substrate is resolved exactly through alloy_registry (domain "corrosion"), the same
    resolution and the same computed ASTM G102 equivalent weight (elements >= 1 wt %,
    renormalised) the Tafel solver uses. An unknown alloy raises ValidationError(UNKNOWN_ALLOY);
    the former substring match ("al" in the id -> aluminium, "ti" -> titanium, anything else
    -> steel EW 27.9 / 7.87 g/cm3) is gone.

    Every input is required: metalId, betaA, betaC, i0Corr_uA (> 0), ePit and e0 (finite, V). The former
    defaults (steel-316l, betaA 0.12, betaC 0.11, i0 0.18, ePit 0.42, e0 0.08) were invented numbers. A missing
    or invalid input makes only the outputs that need it unavailable (null + reason, `status` "partial", or
    "unavailable" when nothing can be computed): Stern-Geary B and Rp need betaA, betaC, i0; the Faraday rate
    needs i0 and metalId; the pitting margin needs ePit and e0; the coating Nyquist needs Rp. A metalId that is
    sent but unknown still raises ValidationError(UNKNOWN_ALLOY). exposureDays keeps its documented default of
    90 (a scenario setting); the coating constants below are model parameters, not inputs.
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
    if exposure_days is None:
        exposure_days = 90

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
        pitting_status = "Immune / Wide Passivity Margin"
        if delta_e_pit < 0.10:
            pitting_status = "Severe Chloride Pitting Susceptibility"
        elif delta_e_pit < 0.30:
            pitting_status = "Moderate Passivity / Pitting Risk"
        
    # Coating Degradation & Water Uptake (Brasher-Kingsbury Model)
    # C_t = C_0 * 80^(volume_fraction_water)
    # R_pore(t) decays exponentially with moisture ingress
    c_coat_0 = 1.2e-9 # F/cm2 (intact epoxy)
    r_pore_0 = 5.0e7  # Ohm*cm2
    
    coating_timeline = []
    day_steps = [0, 1, 7, 14, 30, 60, exposure_days]
    day_steps = sorted(list(set(day_steps)))
    
    for d in day_steps:
        # Moisture absorption saturation function
        phi_water_pct = min(4.8, 4.8 * (1.0 - math.exp(-d / 12.0)))
        c_coat_t = c_coat_0 * (80.0 ** (phi_water_pct / 100.0))
        r_pore_t = r_pore_0 * math.exp(-0.065 * d) + 800.0 # pore resistance drops
        
        coating_status = "Intact Dielectric Barrier"
        if phi_water_pct > 3.0:
            coating_status = "Severe Electrolyte Infiltration & Blistering"
        elif phi_water_pct > 1.2:
            coating_status = "Moisture Absorption & Pore Formation"
            
        coating_timeline.append({
            "day": d,
            "waterUptakePct": round(phi_water_pct, 2),
            "coatingCapacitance_nF_cm2": round(c_coat_t * 1e9, 3),
            "poreResistance_kOhm_cm2": round(r_pore_t / 1000.0, 1),
            "status": coating_status
        })
        
    # Synthetic Coating Nyquist Spectrum over Time (Day 0 vs Day 30 vs Day 90)
    coating_nyquist = []
    test_freqs = [10.0 ** (5.0 - 7.0 * i / 49.0) for i in range(50)] # 100 kHz to 10 mHz
    
    for d_target in ([0, min(30, exposure_days), exposure_days] if r_p_ohm_cm2 is not None else []):
        stage = next((s for s in coating_timeline if s["day"] == d_target), coating_timeline[0])
        r_s = 20.0
        r_pore = stage["poreResistance_kOhm_cm2"] * 1000.0
        c_coat = stage["coatingCapacitance_nF_cm2"] * 1e-9
        r_ct = r_p_ohm_cm2
        c_dl = 20.0e-6
        
        spectrum = []
        for f in test_freqs:
            omega = 2.0 * math.pi * f
            j = 1j
            z_rs = complex(r_s, 0.0)
            
            # Coating pore loop
            z_c_coat = 1.0 / (j * omega * c_coat + 1e-30)
            z_loop1 = (complex(r_pore, 0.0) * z_c_coat) / (complex(r_pore, 0.0) + z_c_coat)
            
            # Substrate charge transfer loop
            z_c_dl = 1.0 / (j * omega * c_dl + 1e-30)
            z_loop2 = (complex(r_ct, 0.0) * z_c_dl) / (complex(r_ct, 0.0) + z_c_dl)
            
            z_total = z_rs + z_loop1 + z_loop2
            spectrum.append({
                "frequency": round(f, 3),
                "zReal": round(z_total.real, 2),
                "minusZImag": round(-z_total.imag, 2)
            })
            
        coating_nyquist.append({
            "day": d_target,
            "spectrum": spectrum
        })
        
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
        "coatingTimeline": coating_timeline,
        "coatingNyquist": coating_nyquist
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

# ==========================================
# 6. Nernst-Planck-Poisson (NPP) Electrolyte Transport Solver
# ==========================================

ELECTROLYTE_FORMULATIONS = {
    "lipf6_ec_emc": {
        "name": "1.0 M LiPF6 in EC:EMC (3:7 vol%) + 2% VC",
        "cation": "Li+",
        "anion": "PF6-",
        "c_bulk_M": 1.0,
        "d_plus": 2.4e-10, # m^2/s
        "d_minus": 3.9e-10, # m^2/s
        "epsilon_r": 18.5,
        "t_plus_base": 0.38,
        "sigma_mS_cm": 10.5,
        "viscosity_mPas": 2.8,
        "type": "Standard Carbonate Liquid"
    },
    "lifsi_dme_dol": {
        "name": "1.2 M LiFSI in DME:DOL (1:1 vol%) - High Rate Ether",
        "cation": "Li+",
        "anion": "FSI-",
        "c_bulk_M": 1.2,
        "d_plus": 4.8e-10,
        "d_minus": 4.1e-10,
        "epsilon_r": 12.0,
        "t_plus_base": 0.54,
        "sigma_mS_cm": 14.2,
        "viscosity_mPas": 1.4,
        "type": "High-Transference Ether"
    },
    "litfsi_peo_solid": {
        "name": "LiTFSI in Poly(ethylene oxide) (PEO) Solid (70°C)",
        "cation": "Li+",
        "anion": "TFSI-",
        "c_bulk_M": 1.5,
        "d_plus": 0.35e-10,
        "d_minus": 1.25e-10,
        "epsilon_r": 8.5,
        "t_plus_base": 0.22,
        "sigma_mS_cm": 1.1,
        "viscosity_mPas": 450.0,
        "type": "Solid Polymer Electrolyte"
    },
    "single_ion_gel": {
        "name": "Single-Ion Conducting Gel Polymer (Li-PSTFSI)",
        "cation": "Li+",
        "anion": "Polymer-bound TFSI-",
        "c_bulk_M": 0.9,
        "d_plus": 1.8e-10,
        "d_minus": 0.15e-10,
        "epsilon_r": 25.0,
        "t_plus_base": 0.92,
        "sigma_mS_cm": 2.8,
        "viscosity_mPas": 85.0,
        "type": "Single-Ion Conductor"
    },
    "napf6_pc_ec": {
        "name": "1.0 M NaPF6 in PC:EC (1:1 vol%) - Sodium Ion",
        "cation": "Na+",
        "anion": "PF6-",
        "c_bulk_M": 1.0,
        "d_plus": 3.1e-10,
        "d_minus": 4.3e-10,
        "epsilon_r": 45.0,
        "t_plus_base": 0.42,
        "sigma_mS_cm": 8.9,
        "viscosity_mPas": 3.6,
        "type": "Sodium-Ion Carbonate"
    },
    "ionic_liquid_emim": {
        "name": "1.0 M LiTFSI in [EMIM][TFSI] Room-Temp Ionic Liquid",
        "cation": "Li+",
        "anion": "TFSI-",
        "c_bulk_M": 1.0,
        "d_plus": 0.8e-10,
        "d_minus": 4.5e-10,
        "epsilon_r": 14.0,
        "t_plus_base": 0.15,
        "sigma_mS_cm": 5.2,
        "viscosity_mPas": 32.0,
        "type": "Ionic Liquid"
    }
}

def simulate_nernst_planck_poisson_transport(formulation_id="lipf6_ec_emc", current_density_mA_cm2=8.0, gap_um=50.0, temp_c=25.0, custom_t_plus=None, custom_c_bulk=None):
    """
    Solves 1D Nernst-Planck-Poisson (NPP) & Stefan-Maxwell concentrated transport equations
    across the electrolyte gap L between working and counter electrodes under applied high-C-rate current.
    """
    form = ELECTROLYTE_FORMULATIONS.get(formulation_id, ELECTROLYTE_FORMULATIONS["lipf6_ec_emc"])
    
    # Constants
    F = F_FARADAY # C/mol, exact (was 96485.33212)
    R = R_GAS # J/(mol*K), exact (was 8.314462618)
    T = temp_c + ZERO_CELSIUS_K # Kelvin
    EPS_0 = 8.8541878128e-12 # F/m
    
    c_bulk_M = custom_c_bulk if custom_c_bulk is not None else form["c_bulk_M"]
    c_bulk_mol_m3 = c_bulk_M * 1000.0
    
    d_plus = form["d_plus"] * math.exp(-18000.0 / (R * T) * (1.0 - T / 298.15))
    d_minus = form["d_minus"] * math.exp(-18000.0 / (R * T) * (1.0 - T / 298.15))
    
    if custom_t_plus is not None:
        t_plus = max(0.01, min(0.99, custom_t_plus))
        # Rebalance d_minus relative to d_plus
        d_minus = d_plus * (1.0 - t_plus) / t_plus
    else:
        t_plus = d_plus / (d_plus + d_minus)
        
    t_minus = 1.0 - t_plus
    
    # Ambipolar effective binary diffusion coefficient
    d_ambipolar = 2.0 * d_plus * d_minus / (d_plus + d_minus) # m^2/s
    
    L_m = gap_um * 1e-6 # m
    j_app_A_m2 = current_density_mA_cm2 * 10.0 # mA/cm^2 -> A/m^2
    
    # Limiting Current Density J_lim [A/m^2] and [mA/cm^2]
    # At steady-state when c_anode drops to 0:
    j_lim_A_m2 = (2.0 * F * d_ambipolar * c_bulk_mol_m3) / ((1.0 - t_plus) * L_m + 1e-15)
    j_lim_mA_cm2 = j_lim_A_m2 / 10.0
    
    # Sand's Transition Time tau_Sand [seconds]
    # tau_sand = (pi * d_ambipolar / 4) * (F * c_bulk / (J * (1 - t_+)))^2
    if abs(j_app_A_m2) > 1e-6:
        tau_sand_s = (math.pi * d_ambipolar / 4.0) * ((F * c_bulk_mol_m3) / (j_app_A_m2 * (1.0 - t_plus))) ** 2
    else:
        tau_sand_s = 999999.0
        
    # Debye Screening Length lambda_D [nm]
    # lambda_D = sqrt( (eps_r * eps_0 * R * T) / (2 * F^2 * c_bulk) )
    eps_r = form["epsilon_r"]
    eps_eff = eps_r * EPS_0
    lambda_d_m = math.sqrt((eps_eff * R * T) / (2.0 * F * F * c_bulk_mol_m3 + 1e-15))
    lambda_d_nm = lambda_d_m * 1e9
    
    # Grid generation across gap [0, L]
    num_nodes = 80
    spatial_profiles = []
    
    # Concentration gradient slope: dc/dx = - J * (1 - t_+) / (2 * F * D_amb)
    delta_c_slope = - (j_app_A_m2 * (1.0 - t_plus)) / (2.0 * F * d_ambipolar + 1e-20)
    
    # Delta c across half cell: delta_c = slope * (L/2)
    delta_c_mol_m3 = (j_app_A_m2 * (1.0 - t_plus) * L_m) / (4.0 * F * d_ambipolar + 1e-20)
    
    c_depleted_mol_m3 = max(1.0, c_bulk_mol_m3 - delta_c_mol_m3)
    c_enriched_mol_m3 = c_bulk_mol_m3 + delta_c_mol_m3
    
    is_limiting_exceeded = j_app_A_m2 >= j_lim_A_m2
    
    # Total potential drop (Ohmic + Liquid Diffusion Potential)
    # Delta Phi_diff = (R*T/F) * (1 - 2*t_+) * ln(c_enriched / c_depleted)
    # Delta Phi_ohmic = J * L / kappa
    kappa_S_m = form["sigma_mS_cm"] * 0.1 # mS/cm -> S/m
    eta_ohmic_V = (j_app_A_m2 * L_m) / (kappa_S_m + 1e-15)
    
    ratio_c = max(0.001, c_enriched_mol_m3 / (c_depleted_mol_m3 + 1e-15))
    eta_diff_V = (R * T / F) * (1.0 - 2.0 * t_plus) * math.log(ratio_c)
    eta_total_liquid_mV = (eta_ohmic_V + eta_diff_V) * 1000.0
    
    for i in range(num_nodes):
        x_frac = i / (num_nodes - 1)
        x_um = x_frac * gap_um
        x_m = x_frac * L_m
        
        # Linear bulk continuum solution
        # x=0 is counter/anode, x=L is working/cathode
        c_continuum_mol_m3 = c_bulk_mol_m3 + (1.0 - 2.0 * x_frac) * delta_c_mol_m3
        c_continuum_M = max(0.005, c_continuum_mol_m3 / 1000.0)
        
        # Poisson space charge boundary layer at x ~ 0 and x ~ L (Debye sheath effect)
        # In the double layer, space charge rho_e = F*(c_+ - c_-) is non-zero
        x_dist_anode_nm = x_m * 1e9
        x_dist_cathode_nm = (L_m - x_m) * 1e9
        
        # Poisson boundary exponential layer decay
        charge_decay_anode = math.exp(-min(50.0, x_dist_anode_nm / (max(0.2, lambda_d_nm) * 2.0)))
        charge_decay_cathode = math.exp(-min(50.0, x_dist_cathode_nm / (max(0.2, lambda_d_nm) * 2.0)))
        
        # Local space charge density [C/m^3]
        zeta_potential_V = 0.035 # 35 mV typical zeta potential
        rho_e_C_m3 = (2.0 * F * c_bulk_mol_m3 * math.sinh((F * zeta_potential_V) / (2.0 * R * T))) * (charge_decay_anode - charge_decay_cathode)
        
        # Local Cation & Anion concentrations with Poisson layer perturbation
        delta_c_charge = rho_e_C_m3 / (2.0 * F * 1000.0) # M
        c_plus_M = max(0.001, c_continuum_M + delta_c_charge)
        c_minus_M = max(0.001, c_continuum_M - delta_c_charge)
        
        # Local Electric Field E(x) [V/m]
        # In bulk: E_bulk = J / kappa - (R*T/F)*(1 - 2*t_+)* (dlnc/dx)
        dlnc_dx = (delta_c_slope) / (c_continuum_mol_m3 + 1e-15)
        e_bulk_V_m = (j_app_A_m2 / (kappa_S_m + 1e-15)) - (R * T / F) * (1.0 - 2.0 * t_plus) * dlnc_dx
        
        # Space-charge field amplification near boundary
        e_space_charge_V_m = (zeta_potential_V / (lambda_d_m + 1e-15)) * (charge_decay_anode + charge_decay_cathode)
        e_total_kV_m = (e_bulk_V_m + e_space_charge_V_m) / 1000.0 # kV/m
        
        # Liquid Potential phi_e(x) [mV]
        phi_mV = (eta_total_liquid_mV * (1.0 - x_frac)) + (zeta_potential_V * 1000.0 * charge_decay_anode) - (zeta_potential_V * 1000.0 * charge_decay_cathode)
        
        # Flux decomposition for Cation: Diffusion Flux vs Migration Flux [mol/(m^2*s)]
        j_diff_plus = - d_plus * delta_c_slope
        j_migr_plus = (t_plus * j_app_A_m2) / F
        
        spatial_profiles.append({
            "x_um": round(x_um, 2),
            "c_plus_M": round(c_plus_M, 4),
            "c_minus_M": round(c_minus_M, 4),
            "c_total_salt_M": round((c_plus_M + c_minus_M) / 2.0, 4),
            "space_charge_rho_C_m3": round(rho_e_C_m3, 2),
            "e_field_kV_m": round(e_total_kV_m, 3),
            "phi_liquid_mV": round(phi_mV, 2),
            "j_diffusion_mol_m2s": round(j_diff_plus * 1e4, 4), # scaled for readability
            "j_migration_mol_m2s": round(j_migr_plus * 1e4, 4)
        })
        
    # Concentration-dependent transference number curve t_+(c)
    c_sweep_M = [0.1, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0]
    t_plus_curve = []
    for c_val in c_sweep_M:
        # In concentrated electrolytes, ion pairing reduces t_+ at high salt concentrations
        t_c = t_plus * (1.0 - 0.12 * (c_val - c_bulk_M))
        t_c = max(0.05, min(0.98, t_c))
        # Thermodynamic activity factor (1 + d ln gamma / d ln c)
        thermo_factor = 1.0 + 0.45 * math.sqrt(c_val) - 0.08 * c_val
        t_plus_curve.append({
            "c_M": c_val,
            "t_plus": round(t_c, 3),
            "t_minus": round(1.0 - t_c, 3),
            "thermodynamicFactor": round(thermo_factor, 3),
            "ionicConductivity_mS_cm": round(form["sigma_mS_cm"] * (c_val / c_bulk_M) * math.exp(-0.3 * (c_val - 1.0)), 2)
        })
        
    # Sand's Time vs Applied Current Curve
    sand_curve = []
    j_test_rates = [1.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 15.0, 20.0, 25.0, 30.0]
    for j_t in j_test_rates:
        j_test_A_m2 = j_t * 10.0
        t_sand = (math.pi * d_ambipolar / 4.0) * ((F * c_bulk_mol_m3) / (j_test_A_m2 * (1.0 - t_plus))) ** 2
        sand_curve.append({
            "currentDensity_mA_cm2": j_t,
            "sandTime_s": round(t_sand, 2) if t_sand < 10000.0 else 10000.0,
            "isLimitingExceeded": j_t >= j_lim_mA_cm2
        })
        
    # Safety and Limiting Transport Diagnosis
    if is_limiting_exceeded:
        status = "CRITICAL: Current exceeds Limiting Current Density J_lim. Severe salt depletion and dendritic short-circuit imminent."
        risk_level = "CRITICAL"
    elif j_app_A_m2 >= 0.75 * j_lim_A_m2:
        status = "WARNING: Operating near limiting current boundary (75%+ J_lim). Heavy concentration polarization and high liquid IR drop."
        risk_level = "WARNING"
    else:
        status = "STABLE: Homogeneous ion transport without salt exhaustion. Liquid concentration gradient within safe boundaries."
        risk_level = "OPTIMAL"
        
    return {
        "formulation": form,
        "formulationId": formulation_id,
        "appliedCurrentDensity_mA_cm2": current_density_mA_cm2,
        "limitingCurrentDensity_mA_cm2": round(j_lim_mA_cm2, 2),
        "sandsTime_seconds": round(tau_sand_s, 2),
        "debyeLength_nm": round(lambda_d_nm, 3),
        "cationTransferenceNumber_tPlus": round(t_plus, 3),
        "anionTransferenceNumber_tMinus": round(t_minus, 3),
        "ambipolarDiffusivity_m2_s": f"{d_ambipolar:.3e}",
        "ohmicDrop_mV": round(eta_ohmic_V * 1000.0, 2),
        "diffusionPotential_mV": round(eta_diff_V * 1000.0, 2),
        "totalLiquidOverpotential_mV": round(eta_total_liquid_mV, 2),
        "status": status,
        "riskLevel": risk_level,
        "minElectrolyteConc_M": round(c_depleted_mol_m3 / 1000.0, 4),
        "maxElectrolyteConc_M": round(c_enriched_mol_m3 / 1000.0, 4),
        "spatialProfiles": spatial_profiles,
        "tPlusConcentrationCurve": t_plus_curve,
        "sandsTimeCurve": sand_curve
    }


# ==========================================
# 7. Bisquert Transmission Line Model (TLM) Component Identification
# ==========================================

def evaluate_bisquert_tlm_impedance(model_type, omega, rs, rion, rct, qd, alpha):
    """
    Computes complex impedance of Bisquert Transmission Line Model:
    Z(w) = Rs + Z_TLM(w)
    where:
      1 / zeta(w) = (1 / Rct) + Qd * (j * w)^alpha
      Lambda = sqrt(Rion / zeta)
      Z_char = sqrt(Rion * zeta)
    For Open (blocking back contact / battery porous electrode / supercapacitor):
      Z_TLM = Z_char * coth(Lambda) = Z_char / tanh(Lambda)
    For Short (transmissive back contact / DSSC / catalytic layer / fuel cell):
      Z_TLM = Z_char * tanh(Lambda)
    """
    j = 1j
    w = max(1e-9, omega)
    rs_val = max(0.0, rs)
    rion_val = max(1e-6, rion)
    rct_val = max(1e-6, rct)
    qd_val = max(1e-15, qd)
    al = max(0.05, min(1.0, alpha))
    
    y_int = (1.0 / rct_val) + qd_val * (w ** al) * cmath.exp(j * al * math.pi / 2.0)
    zeta = 1.0 / (y_int + 1e-30)
    
    gamma_l = cmath.sqrt(complex(rion_val, 0.0) / zeta)
    z_char = cmath.sqrt(complex(rion_val, 0.0) * zeta)
    
    if model_type == "short":
        if abs(gamma_l) < 1e-8:
            return complex(rs_val, 0.0) + zeta
        tanh_g = cmath.tanh(gamma_l)
        return complex(rs_val, 0.0) + z_char * tanh_g
    else:  # "open" (blocking current collector)
        if abs(gamma_l) < 1e-8:
            return complex(rs_val + rion_val / 3.0, 0.0) + zeta
        tanh_g = cmath.tanh(gamma_l)
        if abs(tanh_g) < 1e-30:
            return complex(rs_val, 0.0) + z_char
        return complex(rs_val, 0.0) + z_char / tanh_g


def evaluate_classical_randles(omega, rs, rct, cdl, alpha):
    """Classical Randles circuit with CPE double layer for comparative model discrimination."""
    j = 1j
    w = max(1e-9, omega)
    rs_val = max(0.0, rs)
    rct_val = max(1e-6, rct)
    cdl_val = max(1e-15, cdl)
    al = max(0.1, min(1.0, alpha))
    z_cpe = 1.0 / (cdl_val * (w ** al) * cmath.exp(j * al * math.pi / 2.0) + 1e-30)
    z_parallel = (rct_val * z_cpe) / (rct_val + z_cpe)
    return complex(rs_val, 0.0) + z_parallel


def identify_bisquert_tlm_circuit_components(frequencies, z_real, z_imag, application_domain="battery", cell_temperature_c=25.0, nominal_capacity_ah=5.0, user_boundary_condition="auto"):
    """
    Utilizes the Bisquert Transmission Line Model (TLM) to automatically identify,
    discriminate, and extract the most likely equivalent circuit components from uploaded impedance data.
    
    Key Physics:
    1. High-frequency intercept R_s (electrolyte and contact resistance).
    2. High-to-intermediate frequency 45-degree slope inspection: checks for de Levie / Bisquert
       interfacial distributed ionic transport signature (porous electrode vs planar semi-circle).
    3. Low-frequency boundary deconvolution:
       - Bisquert Open (blocking substrate: battery cathode/anode, supercapacitors):
         Z_LF -> R_s + R_ion/3 + R_ct (or capacitive upturn).
       - Bisquert Short (transmissive substrate: DSSC, catalytic GDL, fuel cell membranes):
         Z_LF -> R_s + R_ion * tanh(...)
    4. Multi-parameter Nelder-Mead optimization on modulus-weighted residual metric.
    5. Information-theoretic discrimination (Akaike AIC & Bayesian BIC) comparing Bisquert Open,
       Bisquert Short, and Classical Randles.
    6. Identification of distinct circuit components: R_s, R_ion, R_ct, Q_dl (C_dl), alpha, and C_int.
    """
    if not frequencies or len(frequencies) < 4:
        return {"error": "At least 4 frequency points are required for Bisquert TLM component identification."}

    # Filter and sort descending by frequency
    points = []
    for f, zr, zi in zip(frequencies, z_real, z_imag):
        if not (math.isnan(f) or math.isnan(zr) or math.isnan(zi)) and f > 0:
            z_mag = math.sqrt(zr * zr + zi * zi)
            phase_rad = math.atan2(zi, zr)
            phase_deg = math.degrees(phase_rad)
            points.append({
                "f": float(f),
                "zr": float(zr),
                "zi": float(zi),
                "minus_zi": -float(zi),
                "z_mag": z_mag,
                "phase_deg": phase_deg
            })
            
    points.sort(key=lambda p: p["f"], reverse=True)
    num_pts = len(points)
    if num_pts < 4:
        return {"error": "No valid impedance points for TLM analysis."}

    freqs = [p["f"] for p in points]
    omegas = [2.0 * math.pi * f for f in freqs]
    z_meas = [complex(p["zr"], p["zi"]) for p in points]
    
    # 1. Series resistance Rs (HF intercept)
    hf_count = max(3, int(num_pts * 0.15))
    hf_pts = points[:hf_count]
    best_hf = min(hf_pts, key=lambda p: abs(p["zi"]))
    rs_init = max(0.0001, best_hf["zr"])
    
    # 2. Transmission line 45-degree regime detection
    mid_hf_pts = points[:max(4, int(num_pts * 0.70))]
    tlm_phase_hits = 0
    slope_45_sum = 0.0
    slope_count = 0
    
    for i in range(1, len(mid_hf_pts)):
        p_curr = mid_hf_pts[i]
        p_prev = mid_hf_pts[i - 1]
        delta_zr = p_curr["zr"] - p_prev["zr"]
        delta_minus_zi = p_curr["minus_zi"] - p_prev["minus_zi"]
        
        # In a transmission line: phase ~ -45 * alpha (typically -32 to -55 deg)
        if -55.0 <= p_curr["phase_deg"] <= -32.0:
            tlm_phase_hits += 1
            
        if abs(delta_zr) > 1e-6 and delta_zr > 0:
            local_slope = delta_minus_zi / delta_zr
            if 0.5 <= local_slope <= 1.8:
                slope_45_sum += local_slope
                slope_count += 1
                
    avg_slope_45 = (slope_45_sum / max(1, slope_count)) if slope_count > 0 else 1.0
    tlm_phase_fraction = tlm_phase_hits / max(1, len(mid_hf_pts))
    
    tlm_signature_score = min(1.0, max(0.0, tlm_phase_fraction * 0.7 + (1.0 if slope_count >= 2 else 0.3) * 0.3))
    is_porous_tlm = tlm_signature_score >= 0.38 or (application_domain in ["battery", "fuel_cell", "supercapacitor"] and tlm_signature_score >= 0.25)
    
    # 3. Detect transition / knee frequency
    knee_idx = max(1, int(num_pts * 0.40))
    for i in range(1, num_pts - 2):
        if points[i]["phase_deg"] < -55.0 or (points[i]["zr"] - rs_init) > 0.3 * (max(p["zr"] for p in points) - rs_init):
            knee_idx = i
            break
            
    f_knee = points[knee_idx]["f"]
    zr_knee = points[knee_idx]["zr"]
    
    # 4. Boundary condition detection (Open vs Short)
    lf_pts = points[max(1, int(num_pts * 0.75)):]
    lf_mean_phase = sum(p["phase_deg"] for p in lf_pts) / len(lf_pts)
    last_pt = points[-1]
    
    detected_boundary = "blocking"
    if lf_mean_phase > -28.0 and last_pt["minus_zi"] < points[knee_idx]["minus_zi"] * 1.5:
        detected_boundary = "transmissive"
    else:
        detected_boundary = "blocking"
        
    if user_boundary_condition in ["open", "blocking"]:
        chosen_boundary = "blocking"
    elif user_boundary_condition in ["short", "transmissive"]:
        chosen_boundary = "transmissive"
    else:
        chosen_boundary = detected_boundary

    # 5. Parameter initial guesses
    z_span = max(p["zr"] for p in points) - rs_init
    if chosen_boundary == "blocking":
        rion_init = max(0.01, 3.0 * max(0.001, zr_knee - rs_init))
        rct_init = max(0.01, z_span - (rion_init / 3.0))
    else:
        rion_init = max(0.01, z_span * 0.35)
        rct_init = max(0.01, z_span * 0.65)
        
    w_knee = 2.0 * math.pi * max(1e-3, f_knee)
    c_dl_init = max(1e-8, 1.0 / (rion_init * w_knee + 1e-15))
    alpha_init = min(0.98, max(0.70, abs(points[1]["phase_deg"]) / 50.0))

    # 6. Optimization Routine (Nelder-Mead)
    def fit_model(model_type, rs_g, rion_g, rct_g, qd_g, al_g, max_iter=140):
        p0 = [
            math.log(max(1e-4, rs_g)),
            math.log(max(1e-4, rion_g)),
            math.log(max(1e-4, rct_g)),
            math.log(max(1e-12, qd_g)),
            math.log(al_g / (1.0 - al_g))
        ]
        
        def cost_fn(p):
            rs_val = math.exp(p[0])
            rion_val = math.exp(p[1])
            rct_val = math.exp(p[2])
            qd_val = math.exp(p[3])
            al_val = 1.0 / (1.0 + math.exp(-p[4]))
            chi2 = 0.0
            for w, zm in zip(omegas, z_meas):
                zc = evaluate_bisquert_tlm_impedance(model_type, w, rs_val, rion_val, rct_val, qd_val, al_val)
                mag2 = zm.real * zm.real + zm.imag * zm.imag + 1e-12
                res2 = (zm.real - zc.real) ** 2 + (zm.imag - zc.imag) ** 2
                chi2 += res2 / mag2
            return chi2

        n = len(p0)
        sim = [list(p0)]
        for i in range(n):
            y = list(p0)
            y[i] += 0.25
            sim.append(y)
            
        for _ in range(max_iter):
            sim.sort(key=cost_fn)
            c = [sum(sim[k][j] for k in range(n)) / n for j in range(n)]
            xr = [c[j] + 1.0 * (c[j] - sim[-1][j]) for j in range(n)]
            fr = cost_fn(xr)
            if fr < cost_fn(sim[0]):
                xe = [c[j] + 2.0 * (xr[j] - c[j]) for j in range(n)]
                sim[-1] = xe if cost_fn(xe) < fr else xr
            elif fr < cost_fn(sim[-2]):
                sim[-1] = xr
            else:
                xc = [c[j] + 0.5 * (sim[-1][j] - c[j]) for j in range(n)]
                if cost_fn(xc) < cost_fn(sim[-1]):
                    sim[-1] = xc
                else:
                    for k in range(1, n + 1):
                        sim[k] = [sim[0][j] + 0.5 * (sim[k][j] - sim[0][j]) for j in range(n)]
                        
        sim.sort(key=cost_fn)
        best = sim[0]
        best_cost = cost_fn(best)
        rs_opt = math.exp(best[0])
        rion_opt = math.exp(best[1])
        rct_opt = math.exp(best[2])
        qd_opt = math.exp(best[3])
        al_opt = 1.0 / (1.0 + math.exp(-best[4]))
        
        k = 5
        n_samples = max(k + 2, num_pts)
        rss = max(1e-12, best_cost)
        aic = n_samples * math.log(rss / n_samples) + 2 * k + (2 * k * (k + 1)) / (n_samples - k - 1)
        bic = n_samples * math.log(rss / n_samples) + k * math.log(n_samples)
        
        return {
            "rs": rs_opt,
            "rion": rion_opt,
            "rct": rct_opt,
            "qd": qd_opt,
            "alpha": al_opt,
            "chi2": best_cost,
            "red_chi2": best_cost / max(1, num_pts - k),
            "aic": aic,
            "bic": bic
        }

    # Fit Bisquert Open and Bisquert Short
    fit_open = fit_model("open", rs_init, rion_init, rct_init, c_dl_init, alpha_init)
    fit_short = fit_model("short", rs_init, rion_init, rct_init, c_dl_init, alpha_init)
    
    # Baseline comparison against Classical Randles
    def fit_randles():
        p0 = [math.log(rs_init), math.log(z_span), math.log(c_dl_init), math.log(0.9 / 0.1)]
        def cost_randles(p):
            rs_v = math.exp(p[0])
            rct_v = math.exp(p[1])
            cdl_v = math.exp(p[2])
            al_v = 1.0 / (1.0 + math.exp(-p[3]))
            c = 0.0
            for w, zm in zip(omegas, z_meas):
                zc = evaluate_classical_randles(w, rs_v, rct_v, cdl_v, al_v)
                mag2 = zm.real ** 2 + zm.imag ** 2 + 1e-12
                c += ((zm.real - zc.real) ** 2 + (zm.imag - zc.imag) ** 2) / mag2
            return c
        n = 4
        sim = [list(p0)]
        for i in range(n):
            y = list(p0)
            y[i] += 0.25
            sim.append(y)
        for _ in range(80):
            sim.sort(key=cost_randles)
            cent = [sum(sim[k][j] for k in range(n)) / n for j in range(n)]
            xr = [cent[j] + 1.0 * (cent[j] - sim[-1][j]) for j in range(n)]
            fr = cost_randles(xr)
            if fr < cost_randles(sim[0]):
                xe = [cent[j] + 2.0 * (xr[j] - cent[j]) for j in range(n)]
                sim[-1] = xe if cost_randles(xe) < fr else xr
            else:
                xc = [cent[j] + 0.5 * (sim[-1][j] - cent[j]) for j in range(n)]
                sim[-1] = xc if cost_randles(xc) < fr else xr
        sim.sort(key=cost_randles)
        best = sim[0]
        cost_val = cost_randles(best)
        k = 4
        n_samples = max(k + 2, num_pts)
        rss = max(1e-12, cost_val)
        aic = n_samples * math.log(rss / n_samples) + 2 * k + (2 * k * (k + 1)) / (n_samples - k - 1)
        bic = n_samples * math.log(rss / n_samples) + k * math.log(n_samples)
        return {"chi2": cost_val, "aic": aic, "bic": bic}

    fit_randles_res = fit_randles()

    # Determine winning model
    if user_boundary_condition == "open":
        active_fit = fit_open
        active_model = "open"
        active_topology = "BisquertOpen"
    elif user_boundary_condition == "short":
        active_fit = fit_short
        active_model = "short"
        active_topology = "BisquertShort"
    else:
        if fit_open["aic"] <= fit_short["aic"] + 2.0:
            active_fit = fit_open
            active_model = "open"
            active_topology = "BisquertOpen"
        else:
            active_fit = fit_short
            active_model = "short"
            active_topology = "BisquertShort"

    preferred_name = "Bisquert Open Porous TLM (Blocking)" if active_model == "open" else "Bisquert Short TLM (Transmissive)"
    if fit_randles_res["aic"] < active_fit["aic"] - 10.0 and not is_porous_tlm:
        preferred_name = "Classical Randles with CPE (Non-porous planar)"

    rs_final = active_fit["rs"]
    rion_final = active_fit["rion"]
    rct_final = active_fit["rct"]
    qd_final = active_fit["qd"]
    alpha_final = active_fit["alpha"]

    # 7. Generate Fitted Spectrum & Residuals
    fitted_spectrum = []
    for p in points:
        w = 2.0 * math.pi * p["f"]
        z_fit = evaluate_bisquert_tlm_impedance(active_model, w, rs_final, rion_final, rct_final, qd_final, alpha_final)
        z_meas_mag = p["z_mag"]
        diff_r = p["zr"] - z_fit.real
        diff_i = p["zi"] - z_fit.imag
        res_pct = (math.sqrt(diff_r * diff_r + diff_i * diff_i) / max(1e-9, z_meas_mag)) * 100.0
        fitted_spectrum.append({
            "frequency": round(p["f"], 3),
            "zRealMeas": round(p["zr"], 5),
            "zImagMeas": round(p["zi"], 5),
            "zRealFit": round(z_fit.real, 5),
            "zImagFit": round(z_fit.imag, 5),
            "residualPct": round(res_pct, 2)
        })

    # 8. Physical Diagnostics
    accessibility_pct = min(100.0, max(5.0, (1.0 / (1.0 + rion_final / (3.0 * max(1e-4, rct_final)))) * 100.0))
    tortuosity_metric = rion_final / max(1e-4, rs_final)
    w_ref = 2.0 * math.pi * 1000.0
    lambda_ratio_1k = min(1.0, max(0.01, 1.0 / (math.sqrt(max(1e-6, w_ref * rion_final * qd_final)) + 1e-12)))

    # 9. Identified Circuit Components
    circuit_components = [
        {
            "id": "el-rs",
            "element": "R_s",
            "name": "Electrolyte Solution & Hardware Resistance",
            "value": round(rs_final, 5),
            "unit": "Ω",
            "error_percent": round(max(0.2, min(5.0, active_fit["red_chi2"] * 500.0)), 2),
            "physicalMeaning": "Bulk ionic resistance of the liquid electrolyte and current collector contact foil.",
            "confidence": 0.98
        },
        {
            "id": "el-rion",
            "element": "R_ion",
            "name": "Pore Channel Ionic Transport Resistance",
            "value": round(rion_final, 5),
            "unit": "Ω",
            "error_percent": round(max(0.5, min(8.0, active_fit["red_chi2"] * 800.0)), 2),
            "physicalMeaning": "Distributed ionic migration resistance inside the porous electrode channels along thickness L (de Levie transmission rail).",
            "confidence": round(min(0.99, max(0.70, tlm_signature_score)), 2)
        },
        {
            "id": "el-rct",
            "element": "R_ct",
            "name": "Interfacial Pore-Wall Charge Transfer Resistance",
            "value": round(rct_final, 5),
            "unit": "Ω",
            "error_percent": round(max(0.5, min(8.0, active_fit["red_chi2"] * 750.0)), 2),
            "physicalMeaning": "Activation overpotential barrier for electrochemical Faradaic ion transfer along internal active surface.",
            "confidence": 0.95
        },
        {
            "id": "el-qdl",
            "element": "Q_dl",
            "name": "Pore-Wall Double-Layer Capacitance (CPE)",
            "value": round(qd_final * 1e6, 3),
            "unit": "μF·s^(α-1)",
            "error_percent": round(max(0.8, min(10.0, active_fit["red_chi2"] * 1000.0)), 2),
            "physicalMeaning": "Electrostatic Helmholtz double-layer capacitance across the solid-electrolyte porous interface.",
            "confidence": 0.93
        },
        {
            "id": "el-alpha",
            "element": "alpha",
            "name": "Pore Heterogeneity & Dispersion Exponent",
            "value": round(alpha_final, 4),
            "unit": "",
            "error_percent": round(max(0.2, min(3.0, active_fit["red_chi2"] * 300.0)), 2),
            "physicalMeaning": "Geometric roughness and non-uniform current distribution factor (1.0 = smooth cylindrical pores).",
            "confidence": 0.96
        }
    ]

    if active_model == "open" and points[-1]["phase_deg"] < -45.0:
        c_int_est = 1.0 / (2.0 * math.pi * points[-1]["f"] * max(1e-4, points[-1]["minus_zi"]))
        circuit_components.append({
            "id": "el-cint",
            "element": "C_int",
            "name": "Solid-State Intercalation / Chemical Capacitance",
            "value": round(c_int_est * 1000.0, 3),
            "unit": "mF",
            "error_percent": 3.2,
            "physicalMeaning": "Low-frequency chemical capacitance reflecting active material lithium storage or blocking pseudocapacitance.",
            "confidence": 0.88
        })

    if active_model == "open":
        circuit_code = f"R_s + TLM_open(R_ion={round(rion_final, 3)}Ω, R_ct={round(rct_final, 3)}Ω, Q_dl={round(qd_final * 1e6, 1)}μF, α={round(alpha_final, 2)})"
        circuit_name = "Bisquert Open Porous Electrode Transmission Line (Blocking Current Collector)"
    else:
        circuit_code = f"R_s + TLM_short(R_ion={round(rion_final, 3)}Ω, R_ct={round(rct_final, 3)}Ω, Q_dl={round(qd_final * 1e6, 1)}μF, α={round(alpha_final, 2)})"
        circuit_name = "Bisquert Short Porous Electrode Transmission Line (Transmissive / Catalytic Front)"

    interpretation = (
        f"Bisquert TLM deconvolution reveals a pore ionic resistance R_ion = {rion_final:.2f} Ω "
        f"paired with an interfacial charge-transfer resistance R_ct = {rct_final:.2f} Ω. "
        f"The electrode demonstrates {accessibility_pct:.1f}% effective active material accessibility, "
        f"with a pore-to-solution resistance ratio of {tortuosity_metric:.2f}. "
        f"The boundary condition conforms to {active_model.upper()} ({'blocking substrate with capacitive low-frequency polarization' if active_model == 'open' else 'transmissive catalytic boundary'})."
    )

    return {
        "success": True,
        "isPythonEngine": True,
        "engine": "MetalliX CPython Bisquert TLM Optimization Engine",
        "circuitModel": circuit_name,
        "circuitCode": circuit_code,
        "topology": active_topology,
        "boundaryCondition": active_model,
        "confidence": round(min(0.99, max(0.60, 1.0 - active_fit["red_chi2"] * 10.0)), 3),
        "isPorousTransmissionLine": is_porous_tlm,
        "components": circuit_components,
        "diagnostics": {
            "r_s_ohm": round(rs_final, 5),
            "r_ion_ohm": round(rion_final, 5),
            "r_ct_ohm": round(rct_final, 5),
            "c_dl_uF": round(qd_final * 1e6, 3),
            "alpha": round(alpha_final, 4),
            "transitionFrequency_Hz": round(f_knee, 3),
            "penetrationDepthRatio": round(lambda_ratio_1k, 4),
            "effectivePorosityAccessibilityPct": round(accessibility_pct, 2),
            "porosityTortuosityMetric": round(tortuosity_metric, 3),
            "highFrequencySlope45Deg": round(avg_slope_45, 3),
            "isPorousTransmissionLine": is_porous_tlm
        },
        "modelComparison": {
            "preferredModel": preferred_name,
            "aicBisquertOpen": round(fit_open["aic"], 2),
            "aicBisquertShort": round(fit_short["aic"], 2),
            "aicClassicalRandles": round(fit_randles_res["aic"], 2),
            "bicBisquertOpen": round(fit_open["bic"], 2),
            "bicBisquertShort": round(fit_short["bic"], 2),
            "bicClassicalRandles": round(fit_randles_res["bic"], 2)
        },
        "reducedChiSquare": round(active_fit["red_chi2"], 6),
        "physicalInterpretation": interpretation,
        "fittedSpectrum": fitted_spectrum
    }


# ==========================================
# 8. Automated EIS Upload & Deep Insights Engine
# ==========================================

def analyze_uploaded_eis_dataset(frequencies, z_real, z_imag, application_domain="battery", cell_temperature_c=25.0, nominal_capacity_ah=5.0):
    """
    Automated electrochemical impedance spectroscopy (EIS) comprehensive deconvolution:
    - High-frequency intercept R_0 / R_s (electrolyte bulk resistance) and inductance L
    - Semi-circle apexes, relaxation time constants tau = 1/(2*pi*f_apex), charge transfer (R_ct) & SEI / film resistance (R_sei)
    - Low-frequency Warburg solid-state diffusion coefficient (sigma_W) and solid diffusion time constant
    - Kramers-Kronig (K-K) causality and linearity validation with residuals
    - DRT (Distribution of Relaxation Times) Tikhonov continuous deconvolution
    - Automated Equivalent Electric Circuit (EEC) topology recommendation with initial parameter estimates
    - Battery SOH% / degradation diagnosis or Corrosion penetration rate (ASTM G102)
    """
    if not frequencies or len(frequencies) < 4:
        return {"error": "At least 4 frequency points are required for EIS analysis."}
        
    # Filter valid numeric points and sort descending by frequency
    points = []
    for f, zr, zi in zip(frequencies, z_real, z_imag):
        if not (math.isnan(f) or math.isnan(zr) or math.isnan(zi)) and f > 0:
            z_mag = math.sqrt(zr * zr + zi * zi)
            phase_rad = math.atan2(zi, zr)
            phase_deg = math.degrees(phase_rad)
            points.append({
                "f": float(f),
                "zr": float(zr),
                "zi": float(zi),
                "minus_zi": -float(zi),
                "z_mag": z_mag,
                "phase_deg": phase_deg
            })
            
    points.sort(key=lambda p: p["f"], reverse=True)
    num_pts = len(points)
    if num_pts < 4:
        return {"error": "No valid numeric impedance data found."}
        
    f_min = points[-1]["f"]
    f_max = points[0]["f"]
    decades = math.log10(max(1e-5, f_max) / max(1e-5, f_min))
    
    # 1. High-Frequency Intercept R_0 / R_s & Inductance L
    # Check highest frequency points (top 5 or f > 1000 Hz)
    hf_subset = points[:max(3, int(num_pts * 0.15))]
    # Check if there is an inductive tail (zi > 0)
    inductance_nH = 0.0
    if points[0]["zi"] > 0:
        inductance_nH = (points[0]["zi"] / (2.0 * math.pi * points[0]["f"])) * 1e9
        
    # Find minimum minus_zi or zero crossing in HF region
    best_hf = min(hf_subset, key=lambda p: abs(p["zi"]))
    r_0_ohm = max(0.0001, best_hf["zr"])
    
    # 2. Semi-Circle Arc Detection & Apex Frequencies
    # Detect local maxima in minus_zi
    apex_peaks = []
    # 3-point moving average to avoid local single-frequency spikes
    smoothed_minus_zi = []
    for i in range(num_pts):
        i_prev = max(0, i - 1)
        i_next = min(num_pts - 1, i + 1)
        smoothed = (points[i_prev]["minus_zi"] + points[i]["minus_zi"] + points[i_next]["minus_zi"]) / 3.0
        smoothed_minus_zi.append(smoothed)
        
    max_minus_zi = max(p["minus_zi"] for p in points)
    for i in range(1, num_pts - 1):
        if smoothed_minus_zi[i] > smoothed_minus_zi[i-1] and smoothed_minus_zi[i] > smoothed_minus_zi[i+1]:
            if smoothed_minus_zi[i] > 0.08 * max_minus_zi:
                f_apex = points[i]["f"]
                peak_minus_zi = points[i]["minus_zi"]
                tau_s = 1.0 / (2.0 * math.pi * f_apex)
                r_arc_est = 2.0 * peak_minus_zi
                c_eff_est = 1.0 / (2.0 * math.pi * f_apex * r_arc_est + 1e-15)
                
                # Classify physical domain based on frequency and time constant
                if f_apex > 500.0 or tau_s < 3e-4:
                    label = "SEI / Surface Passive Film Interphase"
                    kind = "film"
                elif 0.5 <= f_apex <= 500.0 or (3e-4 <= tau_s <= 0.3):
                    label = "Electrode Charge-Transfer Kinetics & Double Layer"
                    kind = "charge_transfer"
                else:
                    label = "Low-Frequency Mass Transport / Adsorption"
                    kind = "diffusion_adsorption"
                    
                apex_peaks.append({
                    "frequency_Hz": round(f_apex, 3),
                    "minus_z_imag_Ohm": round(peak_minus_zi, 5),
                    "tau_seconds": f"{tau_s:.3e}",
                    "estimated_r_Ohm": round(r_arc_est, 5),
                    "estimated_c_uF": round(c_eff_est * 1e6, 3),
                    "process": label,
                    "kind": kind
                })
                
    # Extract R_sei and R_ct from peaks or fallback
    film_peaks = [p for p in apex_peaks if p["kind"] == "film"]
    ct_peaks = [p for p in apex_peaks if p["kind"] == "charge_transfer"]
    
    if film_peaks:
        r_sei_ohm = film_peaks[0]["estimated_r_Ohm"]
        c_sei_uF = film_peaks[0]["estimated_c_uF"]
        f_apex_sei_Hz = film_peaks[0]["frequency_Hz"]
    else:
        r_sei_ohm = 0.0
        c_sei_uF = 0.0
        f_apex_sei_Hz = 0.0
        
    if ct_peaks:
        r_ct_ohm = ct_peaks[0]["estimated_r_Ohm"]
        c_dl_uF = ct_peaks[0]["estimated_c_uF"]
        f_apex_ct_Hz = ct_peaks[0]["frequency_Hz"]
    elif apex_peaks:
        r_ct_ohm = apex_peaks[0]["estimated_r_Ohm"]
        c_dl_uF = apex_peaks[0]["estimated_c_uF"]
        f_apex_ct_Hz = apex_peaks[0]["frequency_Hz"]
    else:
        # Fallback: estimate from max minus_zi
        r_ct_ohm = max(0.001, 2.0 * max_minus_zi)
        c_dl_uF = 25.0
        f_apex_ct_Hz = 10.0
        
    total_polarization_ohm = r_sei_ohm + r_ct_ohm
    
    # 3. Exchange Current Density I_0
    # I_0 = (R * T) / (n * F * R_ct)
    R_gas = R_GAS  # exact (was 8.31446)
    F_const = F_FARADAY  # exact (was 96485.33)
    T_kelvin = cell_temperature_c + ZERO_CELSIUS_K
    i_0_A = (R_gas * T_kelvin) / (1.0 * F_const * max(1e-6, r_ct_ohm))
    
    # 4. Low-Frequency Warburg Diffusion Analysis
    # Low frequency points f < 2.0 Hz
    lf_subset = [p for p in points if p["f"] <= 2.5]
    warburg_sigma = 0.0
    warburg_r2 = 0.0
    has_warburg = False
    
    if len(lf_subset) >= 3:
        x_vals = [1.0 / math.sqrt(2.0 * math.pi * p["f"]) for p in lf_subset]
        y_vals = [p["minus_zi"] for p in lf_subset]
        n_lf = len(x_vals)
        mean_x = sum(x_vals) / n_lf
        mean_y = sum(y_vals) / n_lf
        
        cov_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_vals, y_vals))
        var_x = sum((x - mean_x) ** 2 for x in x_vals)
        var_y = sum((y - mean_y) ** 2 for y in y_vals)
        
        if var_x > 1e-12 and var_y > 1e-12:
            slope = cov_xy / var_x
            r2 = (cov_xy ** 2) / (var_x * var_y)
            if slope > 0:
                warburg_sigma = round(slope, 5)
                warburg_r2 = round(r2, 4)
                has_warburg = r2 >= 0.70 and points[-1]["phase_deg"] < -30.0
                
    # A computed Voigt-fit consistency diagnostic, not proof of stationarity,
    # linearity, ASTM compliance, or independent experimental validation.
    from cnls_fitting_solver import perform_lin_kk_stationarity_test
    kk = perform_lin_kk_stationarity_test([
        {"frequency": p["f"], "zReal": p["zr"], "minusZImag": -p["zi"]}
        for p in points
    ])
    kk_residuals = [
        {"f": p["f"], "delta_real_pct": r["zRealResPct"],
         "delta_imag_pct": -r["zImagResPct"], "z_mag": p["z_mag"]}
        for p, r in zip(points, kk["residuals"])
    ]
    chi_sq_kk = kk["pseudoChiSquare"] if kk_residuals else None
    kk_status = "Voigt-fit residual screening; measurement validity is not established"
    kk_grade = "SCREENING" if kk_residuals else "NOT_EVALUATED"

    # 6. DRT Deconvolution
    drt_out = compute_drt_spectrum([p["f"] for p in points], [p["zr"] for p in points], [p["zi"] for p in points], num_tau=60, lambda_reg=1e-3)
    
    # 7. Automated Bisquert Transmission Line Model (TLM) & Equivalent Electric Circuit (EEC) Recommendation
    tlm_id = identify_bisquert_tlm_circuit_components(frequencies, z_real, z_imag, application_domain, cell_temperature_c, nominal_capacity_ah)

    circuit_code = ""
    circuit_name = ""
    circuit_elements = []
    
    if tlm_id.get("isPorousTransmissionLine") and tlm_id.get("confidence", 0) >= 0.50:
        circuit_code = tlm_id.get("circuitCode", "R_s + TLM_open(R_ion, R_ct, Q_dl, alpha)")
        circuit_name = tlm_id.get("circuitModel", "Bisquert Porous Electrode Transmission Line")
        circuit_elements = [
            {"element": c["element"], "value": c["value"], "unit": c["unit"], "meaning": c["physicalMeaning"]}
            for c in tlm_id.get("components", [])
        ]
    elif r_sei_ohm > 0.001 and has_warburg:
        circuit_code = "R_s + (R_sei || C_sei) + (R_ct + W) || C_dl"
        circuit_name = "Dual-Interphase Randles with Warburg (ASTM / Battery Standard)"
        circuit_elements = [
            {"element": "R_s", "value": round(r_0_ohm, 5), "unit": "Ω", "meaning": "Bulk electrolyte / Ohmic solution resistance"},
            {"element": "R_sei", "value": round(r_sei_ohm, 5), "unit": "Ω", "meaning": "SEI / Passive surface film resistance"},
            {"element": "C_sei", "value": round(c_sei_uF, 3), "unit": "μF", "meaning": "SEI / Surface film capacitance"},
            {"element": "R_ct", "value": round(r_ct_ohm, 5), "unit": "Ω", "meaning": "Interfacial charge transfer resistance"},
            {"element": "C_dl", "value": round(c_dl_uF, 3), "unit": "μF", "meaning": "Electrochemical double layer capacitance"},
            {"element": "W_sigma", "value": round(warburg_sigma, 5), "unit": "Ω·s^-0.5", "meaning": "Warburg solid-state mass diffusion coefficient"}
        ]
    elif has_warburg:
        circuit_code = "R_s + (R_ct + W) || C_dl"
        circuit_name = "Standard Classical Randles Cell with Warburg"
        circuit_elements = [
            {"element": "R_s", "value": round(r_0_ohm, 5), "unit": "Ω", "meaning": "Bulk electrolyte / Ohmic solution resistance"},
            {"element": "R_ct", "value": round(r_ct_ohm, 5), "unit": "Ω", "meaning": "Charge transfer resistance"},
            {"element": "C_dl", "value": round(c_dl_uF, 3), "unit": "μF", "meaning": "Double layer capacitance"},
            {"element": "W_sigma", "value": round(warburg_sigma, 5), "unit": "Ω·s^-0.5", "meaning": "Warburg diffusion coefficient"}
        ]
    elif r_sei_ohm > 0.001:
        circuit_code = "R_s + (R_film || C_film) + (R_ct || C_dl)"
        circuit_name = "Two-Time-Constant Porous / Coating Interphase Model"
        circuit_elements = [
            {"element": "R_s", "value": round(r_0_ohm, 5), "unit": "Ω", "meaning": "Solution resistance"},
            {"element": "R_film", "value": round(r_sei_ohm, 5), "unit": "Ω", "meaning": "Pore / Film resistance"},
            {"element": "C_film", "value": round(c_sei_uF, 3), "unit": "μF", "meaning": "Film dielectric capacitance"},
            {"element": "R_ct", "value": round(r_ct_ohm, 5), "unit": "Ω", "meaning": "Charge transfer / polarization resistance"},
            {"element": "C_dl", "value": round(c_dl_uF, 3), "unit": "μF", "meaning": "Double layer capacitance"}
        ]
    else:
        circuit_code = "R_s + (R_ct || C_dl)"
        circuit_name = "Single-Arc Simplified Randles Cell"
        circuit_elements = [
            {"element": "R_s", "value": round(r_0_ohm, 5), "unit": "Ω", "meaning": "Solution resistance"},
            {"element": "R_ct", "value": round(r_ct_ohm, 5), "unit": "Ω", "meaning": "Charge transfer resistance"},
            {"element": "C_dl", "value": round(c_dl_uF, 3), "unit": "μF", "meaning": "Double layer capacitance"}
        ]
        
    # 8. Domain-Specific Engineering Insights & Health Prognosis
    insights = []
    
    if application_domain == "battery":
        # Estimate State-of-Health (SOH)
        # Reference fresh baseline for high-power commercial cell (~ 0.02 - 0.05 Ohm total)
        baseline_ohm = 0.035
        total_internal_r = r_0_ohm + total_polarization_ohm
        soh_pct = max(35.0, min(100.0, 100.0 - (max(0.0, total_internal_r - baseline_ohm) / baseline_ohm) * 20.0))
        
        # Power Fade vs Capacity Fade Breakdown
        # Ohmic rise = current collector tab degradation / electrolyte dry-out
        # R_ct rise = active material loss (LAM)
        # R_sei rise = loss of lithium inventory (LLI)
        soh_soh_category = "OPTIMAL (Fresh Cell)" if soh_pct > 90.0 else ("GOOD (Mild Aging)" if soh_pct > 78.0 else "DEGRADED (High Resistance)")
        
        insights.append({
            "title": "State of Health (SOH) & Impedance Metric",
            "value": f"{soh_pct:.1f}%",
            "status": soh_soh_category,
            "description": f"Calculated from aggregate AC impedance (R_total = {total_internal_r * 1000.0:.1f} mΩ) combining Ohmic ({r_0_ohm * 1000.0:.1f} mΩ) and polarization ({total_polarization_ohm * 1000.0:.1f} mΩ)."
        })
        
        insights.append({
            "title": "SEI Interfacial Passivation Layer",
            "value": f"{r_sei_ohm * 1000.0:.1f} mΩ" if r_sei_ohm > 0 else "Negligible / Merged",
            "status": "Healthy Passivation" if r_sei_ohm < 0.025 else "Thickened / LLI Degradation",
            "description": f"Apex at {f_apex_sei_Hz:.1f} Hz. SEI film thickness & resistivity indicates solid electrolyte interphase stability."
        })
        
        # Lithium Plating Vulnerability
        plating_risk = "LOW"
        plating_score = 15
        if cell_temperature_c < 10.0 or r_ct_ohm > 0.05:
            plating_risk = "HIGH"
            plating_score = 82
        elif cell_temperature_c < 20.0 or r_ct_ohm > 0.03:
            plating_risk = "MODERATE"
            plating_score = 48
            
        insights.append({
            "title": "Lithium Plating Vulnerability Score",
            "value": f"{plating_score}/100 ({plating_risk})",
            "status": plating_risk,
            "description": f"At {cell_temperature_c}°C, high charge-transfer polarization (R_ct = {r_ct_ohm*1000.0:.1f} mΩ) risks pushing negative electrode overpotential below 0V vs Li/Li+ during fast-charging."
        })
        
        if has_warburg:
            insights.append({
                "title": "Solid-State Li+ Diffusion (Warburg)",
                "value": f"σ = {warburg_sigma:.3f} Ω·s^-0.5",
                "status": "Normal Mass Transport",
                "description": f"Linear Warburg slope (R² = {warburg_r2}) confirmed in the low-frequency range ({points[-1]['f']:.3f} Hz - {lf_subset[0]['f']:.2f} Hz)."
            })
            
    else: # Corrosion / Coating Domain
        # ASTM G102 Corrosion Rate: CR = (0.00327 * i_corr * EW) / rho
        # i_corr = B / R_p, where B ~ 0.026 V (Stern-Geary)
        r_p_ohm_cm2 = max(1.0, r_ct_ohm * 1.0) # assume 1 cm^2 sample
        b_constant = 0.026 # V
        i_corr_A_cm2 = b_constant / r_p_ohm_cm2
        i_corr_uA_cm2 = i_corr_A_cm2 * 1e6
        
        # Carbon steel reference: EW = 27.92, rho = 7.87 g/cm3
        ew_ref = 27.92
        rho_ref = 7.87
        cr_mm_year = (ASTM_G102_K1_MM_G_UA_CM_YR * i_corr_uA_cm2 * ew_ref) / rho_ref
        cr_mpy = cr_mm_year * 39.37
        
        corrosion_state = "PASSIVE / EXCELLENT" if cr_mm_year < 0.02 else ("MODERATE CORROSION" if cr_mm_year < 0.15 else "SEVERE UNSTABLE CORROSION")
        
        insights.append({
            "title": "Polarization Resistance (R_p)",
            "value": f"{r_p_ohm_cm2:.1f} Ω·cm²",
            "status": corrosion_state,
            "description": "Determined from the low-to-mid frequency charge-transfer diameter via Stern-Geary approximation."
        })
        
        insights.append({
            "title": "Corrosion Penetration Rate (ASTM G102)",
            "value": f"{cr_mm_year:.4f} mm/yr ({cr_mpy:.2f} mpy)",
            "status": corrosion_state,
            "description": f"Calculated corrosion current i_corr = {i_corr_uA_cm2:.2f} μA/cm²."
        })
        
        if r_sei_ohm > 0:
            insights.append({
                "title": "Protective Film / Coating Pore Resistance",
                "value": f"{r_sei_ohm:.1f} Ω·cm²",
                "status": "Barrier Intact" if r_sei_ohm > 1000 else "Degraded / Porous",
                "description": f"Coating pore resistance at {f_apex_sei_Hz:.1f} Hz indicates electrolyte penetration through protective layer."
            })
            
    # Formulate clean output package
    return {
        "datasetSummary": {
            "numPoints": num_pts,
            "fMin_Hz": round(f_min, 4),
            "fMax_Hz": round(f_max, 2),
            "frequencyDecades": round(decades, 2),
            "maxImpedance_Ohm": round(max(p["z_mag"] for p in points), 4),
            "minImpedance_Ohm": round(min(p["z_mag"] for p in points), 4)
        },
        "extractedParameters": {
            "r0_ohm": round(r_0_ohm, 5),
            "inductance_nH": round(inductance_nH, 3),
            "rSei_ohm": round(r_sei_ohm, 5),
            "cSei_uF": round(c_sei_uF, 3),
            "fApexSei_Hz": round(f_apex_sei_Hz, 2),
            "rCt_ohm": round(r_ct_ohm, 5),
            "cDl_uF": round(c_dl_uF, 3),
            "fApexCt_Hz": round(f_apex_ct_Hz, 2),
            "totalPolarization_ohm": round(total_polarization_ohm, 5),
            "exchangeCurrent_mA": round(i_0_A * 1000.0, 3),
            "warburgSigma": warburg_sigma,
            "warburgR2": warburg_r2,
            "hasWarburg": has_warburg
        },
        "kramersKronigValidation": {
            "status": kk_status,
            "grade": kk_grade,
            "pseudoChiSq": chi_sq_kk,
            "residuals": kk_residuals
        },
        "apexPeaks": apex_peaks,
        "recommendedCircuit": {
            "name": circuit_name,
            "topologyCode": circuit_code,
            "elements": circuit_elements
        },
        "bisquertTLM": tlm_id,
        "drtAnalysis": drt_out,
        "engineeringInsights": insights,
        "cleanedPoints": points
    }


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        print(json.dumps({
            "status": "ready",
            "engine": "MetalliX CPython 3.10+ Advanced Battery & Corrosion EIS / DRT Solver",
            "capabilities": [
                "DRT Continuous Deconvolution (Tikhonov Regularization)",
                "Battery SEI Aging & Multi-Cycle EIS Simulation",
                "Fast-Charge Lithium Plating Risk & Critical C-rate Boundary",
                "Corrosion ASTM G59 Polarization Resistance & Penetration Rate",
                "Brasher-Kingsbury Protective Coating Water Uptake & Degradation"
            ]
        }))
        sys.exit(0)
        
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            print(json.dumps({"error": "Empty input payload", "errorKind": "internal"}))
            sys.exit(1)
            
        data = json.loads(raw)
        action = data.get("action", "drt")
        start_time = time.perf_counter()
        
        if action == "drt":
            freqs = data.get("frequencies", [])
            z_real = data.get("zReal", [])
            z_imag = data.get("zImag", [])
            lambda_reg = data.get("lambdaReg", 1e-3)
            num_tau = data.get("numTau", 60)
            res = compute_drt_spectrum(freqs, z_real, z_imag, num_tau, lambda_reg)
            
        elif action == "battery_degradation":
            chem_id = data.get("chemistryId", "nmc811")
            init_params = data.get("initialParams", {})
            cycles = data.get("cycles", 1000)
            temp_c = data.get("tempC", 25.0)
            c_rate = data.get("chargeCRate", 1.0)
            res = simulate_battery_degradation_and_eis(chem_id, init_params, cycles, temp_c, c_rate)
            
        elif action == "p2d_continuum":
            chem_id = data.get("chemistryId", "nmc811")
            c_rate = data.get("cRate", 2.0)
            temp_c = data.get("tempC", 25.0)
            soc = data.get("soc", 0.5)
            custom_params = data.get("customParams", {})
            res = simulate_p2d_continuum_profiles(chem_id, c_rate, temp_c, soc, custom_params)
            
        elif action == "lli_lam_deconvolution":
            chem_id = data.get("chemistryId", "nmc811")
            init_cap = data.get("initialCapAh", 5.0)
            deg_cap = data.get("degradedCapAh", 4.1)
            lli_pct = data.get("lliPct", None)
            lam_pe_pct = data.get("lamPePct", None)
            lam_ne_pct = data.get("lamNePct", None)
            res = deconvolve_lli_lam_degradation(chem_id, init_cap, deg_cap, lli_pct, lam_pe_pct, lam_ne_pct)
            
        elif action == "bernardi_thermal":
            cell_format = data.get("cellFormat", "21700-cylindrical")
            nom_cap = data.get("nominalCapAh", 5.0)
            c_rate = data.get("cRate", 3.0)
            cooling = data.get("coolingType", "forced_air")
            temp_amb = data.get("tempAmbientC", 25.0)
            r_mohm = data.get("internalRMohm", 18.0)
            res = simulate_bernardi_thermal_multiphysics(cell_format, nom_cap, c_rate, cooling, temp_amb, r_mohm)
            
        elif action == "transport_kinetics" or action == "nernst_planck_poisson":
            form_id = data.get("formulationId", "lipf6_ec_emc")
            j_app = data.get("currentDensity_mA_cm2", 8.0)
            gap_um = data.get("gap_um", 50.0)
            temp_c = data.get("tempC", 25.0)
            custom_t_plus = data.get("customTPlus", None)
            custom_c_bulk = data.get("customCBulk", None)
            res = simulate_nernst_planck_poisson_transport(form_id, j_app, gap_um, temp_c, custom_t_plus, custom_c_bulk)
            
        elif action == "corrosion_kinetics":
            metal_id = data.get("metalId")
            beta_a = data.get("betaA")
            beta_c = data.get("betaC")
            i0_corr = data.get("i0Corr_uA")
            e_pit = data.get("ePit")
            e0 = data.get("e0")
            days = data.get("exposureDays", 90)
            res = simulate_corrosion_eis_and_kinetics(metal_id, beta_a, beta_c, i0_corr, e_pit, e0, days)
            
        elif action == "analyze_uploaded_eis":
            freqs = data.get("frequencies", [])
            z_real = data.get("zReal", [])
            z_imag = data.get("zImag", [])
            domain = data.get("applicationDomain", "battery")
            temp_c = data.get("cellTemperatureC", 25.0)
            cap_ah = data.get("nominalCapacityAh", 5.0)
            res = analyze_uploaded_eis_dataset(freqs, z_real, z_imag, domain, temp_c, cap_ah)
            
        elif action in ["identify_bisquert_tlm", "bisquert_tlm_components"]:
            freqs = data.get("frequencies", [])
            z_real = data.get("zReal", [])
            z_imag = data.get("zImag", [])
            domain = data.get("applicationDomain", "battery")
            temp_c = data.get("cellTemperatureC", 25.0)
            cap_ah = data.get("nominalCapacityAh", 5.0)
            bcond = data.get("boundaryCondition", "auto")
            res = identify_bisquert_tlm_circuit_components(freqs, z_real, z_imag, domain, temp_c, cap_ah, bcond)
            
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
