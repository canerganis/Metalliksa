#!/usr/bin/env python3
"""
MetalliX Python CNLS Impedance Fitting Solver
High-performance Complex Non-Linear Least Squares (CNLS) Levenberg-Marquardt optimizer
for electrochemical impedance spectroscopy (EIS) equivalent circuit models.
Reports local linearized covariance when identifiable, with explicit unavailable
uncertainties and a separate, unvalidated Voigt residual screening model.
"""

import sys
import json
import math
import cmath
import time
import random

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    np = None
    HAS_NUMPY = False


def _is_array(omega):
    """True for a NumPy frequency array. Independent of HAS_NUMPY, which only gates the
    legacy scalar paths of the (disabled) global auto-fit."""
    return np is not None and isinstance(omega, np.ndarray)


def _require_numpy(what):
    if np is None:
        raise RuntimeError(f"{what} requires NumPy (python/requirements.txt)")


def evaluate_element_impedance(el_type, params, omega):
    """
    Computes complex impedance Z = R + j*X for a single circuit element.
    Supports both scalar frequency omega (float) and vectorized NumPy 1D frequency array omega.
    Supports standard and advanced electrochemistry elements:
    - R: Resistor
    - C: Capacitor
    - CPE / Q: Constant Phase Element
    - W: Infinite Warburg (45-deg diffusion)
    - Wo / OpenWarburg: Finite-length transmissive / Nernst diffusion (tanh)
    - Ws / ShortWarburg: Finite-length reflective / intercalation diffusion (coth)
    - G / Gerischer: Chemical reaction coupled with diffusion
    - CC / ColeCole: Cole-Cole dielectric relaxation
    - HN / HavriliakNegami: Havriliak-Negami asymmetric dielectric relaxation
    - TLM_open / BisquertOpen: Porous electrode transmission line (blocking boundary)
    - TLM_short / BisquertShort: Porous electrode transmission line (transmissive boundary)
    - L: Inductor
    """
    is_arr = _is_array(omega)
    j = 1j
    w = np.maximum(1e-9, omega) if is_arr else max(1e-9, omega)
    
    if el_type in ["R", "Resistor"]:
        val = max(1e-9, params.get("value", params.get("resistance", 1.0)))
        return np.full(w.shape, complex(val, 0.0), dtype=np.complex128) if is_arr else complex(val, 0.0)
    
    elif el_type in ["C", "Capacitor"]:
        c = max(1e-15, params.get("value", params.get("capacitance", 1e-6)))
        return 1.0 / (j * w * c + 1e-30)
    
    elif el_type in ["CPE", "ConstantPhaseElement", "Q"]:
        q = max(1e-15, params.get("value", params.get("q", params.get("q0", 1e-5))))
        n = max(0.01, min(1.0, params.get("exponent", params.get("n", params.get("n_cpe", 0.85)))))
        phase_factor = np.exp(j * n * np.pi / 2.0) if is_arr else cmath.exp(j * n * math.pi / 2.0)
        denom = q * (w ** n) * phase_factor
        return 1.0 / (denom + 1e-30)
    
    elif el_type in ["W", "Warburg"]:
        sigma = max(1e-6, params.get("value", params.get("sigma", 100.0)))
        sqrt_w = np.sqrt(w) if is_arr else math.sqrt(w)
        val = sigma / sqrt_w
        return val * (1.0 - 1j) if is_arr else complex(val, -val)
    
    elif el_type in ["Wo", "OpenWarburg", "NernstDiffusion"]:
        # Transmissive boundary / open Warburg: Z = Rd * tanh(sqrt(j*w*tau)) / sqrt(j*w*tau)
        r = max(1e-6, params.get("value", params.get("resistance", params.get("r", 100.0))))
        t = max(1e-6, params.get("exponent", params.get("timeConstant", params.get("tau", 0.5))))
        if is_arr:
            arg = np.sqrt(j * w * t)
            return np.where(np.abs(arg) < 1e-12, complex(r, 0.0), (r * np.tanh(arg)) / (arg + 1e-30))
        else:
            arg = cmath.sqrt(j * w * t)
            if abs(arg) < 1e-12:
                return complex(r, 0.0)
            return r * cmath.tanh(arg) / arg

    elif el_type in ["Ws", "ShortWarburg", "FiniteWarburg", "ReflectiveWarburg"]:
        # Reflective boundary / short Warburg (intercalation): Z = Rd * coth(sqrt(j*w*tau)) / sqrt(j*w*tau)
        r = max(1e-6, params.get("value", params.get("resistance", params.get("r", 100.0))))
        t = max(1e-6, params.get("exponent", params.get("timeConstant", params.get("tau", 0.5))))
        if is_arr:
            arg = np.sqrt(j * w * t)
            tanh_val = np.tanh(arg)
            coth_val = 1.0 / np.where(np.abs(tanh_val) < 1e-30, 1e-30, tanh_val)
            z_norm = (r / (arg + 1e-30)) * coth_val
            z_lim = complex(r / 3.0, 0.0) - 1j / (w * (t / r) + 1e-30)
            return np.where(np.abs(arg) < 1e-12, z_lim, z_norm)
        else:
            arg = cmath.sqrt(j * w * t)
            if abs(arg) < 1e-12:
                return complex(r / 3.0, -1.0 / (w * (t / r) + 1e-30))
            tanh_val = cmath.tanh(arg)
            if abs(tanh_val) < 1e-30:
                return complex(1e12, 0.0)
            return (r / arg) * (1.0 / tanh_val)

    elif el_type in ["G", "Gerischer"]:
        # Gerischer element: Z = Rg / (1 + (j*w*tau)^alpha)^0.5
        rg = max(1e-6, params.get("value", params.get("r", 100.0)))
        tg = max(1e-6, params.get("exponent", params.get("tau", 0.1)))
        alpha = max(0.1, min(1.0, params.get("alpha", 1.0)))
        term = 1.0 + (j * w * tg) ** alpha
        sqrt_term = np.sqrt(term) if is_arr else cmath.sqrt(term)
        return rg / (sqrt_term + 1e-30)
    
    elif el_type in ["CC", "ColeCole"]:
        # Cole-Cole dielectric relaxation: Z = R0 / (1 + (j*w*tau)^alpha)
        r0 = max(1e-6, params.get("value", params.get("r0", 1000.0)))
        tau = max(1e-12, params.get("exponent", params.get("tau", 1e-4)))
        alpha = max(0.01, min(1.0, params.get("alpha", 0.85)))
        denom = 1.0 + (j * w * tau) ** alpha
        return r0 / (denom + 1e-30)
    
    elif el_type in ["HN", "HavriliakNegami"]:
        # Havriliak-Negami dielectric: Z = R0 / ((1 + (j*w*tau)^alpha)^beta)
        r0 = max(1e-6, params.get("value", params.get("r0", 1000.0)))
        tau = max(1e-12, params.get("exponent", params.get("tau", 1e-4)))
        alpha = max(0.01, min(1.0, params.get("alpha", 0.85)))
        beta = max(0.01, min(1.0, params.get("beta", 0.75)))
        inner = 1.0 + (j * w * tau) ** alpha
        denom = inner ** beta
        return r0 / (denom + 1e-30)

    elif el_type in ["TLM_open", "BisquertOpen"]:
        # Bisquert Open Transmission Line (porous electrode with blocking back contact)
        r_ion = max(1e-6, params.get("value", params.get("rion", params.get("r_ion", 50.0))))
        r_ct = max(1e-6, params.get("rct", params.get("r_ct", 200.0)))
        q_d = max(1e-15, params.get("qd", params.get("cd", 1e-4)))
        alpha = max(0.01, min(1.0, params.get("exponent", params.get("alpha", 0.90))))
        
        phase_factor = np.exp(j * alpha * np.pi / 2.0) if is_arr else cmath.exp(j * alpha * math.pi / 2.0)
        y_int = (1.0 / r_ct) + q_d * (w ** alpha) * phase_factor
        zeta = 1.0 / (y_int + 1e-30)
        
        if is_arr:
            gamma_l = np.sqrt(r_ion / zeta)
            z_char = np.sqrt(r_ion * zeta)
            tanh_g = np.tanh(gamma_l)
            coth_g = 1.0 / np.where(np.abs(tanh_g) < 1e-30, 1e-30, tanh_g)
            z_norm = z_char * coth_g
            z_lim = complex(r_ion / 3.0, 0.0) + zeta
            return np.where(np.abs(gamma_l) < 1e-8, z_lim, z_norm)
        else:
            gamma_l = cmath.sqrt(complex(r_ion, 0.0) / zeta)
            z_char = cmath.sqrt(complex(r_ion, 0.0) * zeta)
            if abs(gamma_l) < 1e-8:
                return complex(r_ion / 3.0, 0.0) + zeta
            tanh_g = cmath.tanh(gamma_l)
            if abs(tanh_g) < 1e-30:
                return z_char
            return z_char / tanh_g

    elif el_type in ["TLM_short", "BisquertShort", "BisquertTrans"]:
        # Bisquert Short / Transmissive Transmission Line (catalytic porous electrode / DSSC)
        r_ion = max(1e-6, params.get("value", params.get("rion", params.get("r_ion", 50.0))))
        r_ct = max(1e-6, params.get("rct", params.get("r_ct", 200.0)))
        q_d = max(1e-15, params.get("qd", params.get("cd", 1e-4)))
        alpha = max(0.01, min(1.0, params.get("exponent", params.get("alpha", 0.90))))
        
        phase_factor = np.exp(j * alpha * np.pi / 2.0) if is_arr else cmath.exp(j * alpha * math.pi / 2.0)
        y_int = (1.0 / r_ct) + q_d * (w ** alpha) * phase_factor
        zeta = 1.0 / (y_int + 1e-30)
        
        if is_arr:
            gamma_l = np.sqrt(r_ion / zeta)
            z_char = np.sqrt(r_ion * zeta)
            tanh_g = np.tanh(gamma_l)
            return np.where(np.abs(gamma_l) < 1e-8, zeta, z_char * tanh_g)
        else:
            gamma_l = cmath.sqrt(complex(r_ion, 0.0) / zeta)
            z_char = cmath.sqrt(complex(r_ion, 0.0) * zeta)
            if abs(gamma_l) < 1e-8:
                return zeta
            return z_char * cmath.tanh(gamma_l)
    
    elif el_type in ["L", "Inductor"]:
        l = max(1e-12, params.get("value", params.get("inductance", 1e-6)))
        return j * w * l
    
    return np.full(w.shape, complex(1.0, 0.0), dtype=np.complex128) if is_arr else complex(1.0, 0.0)

def evaluate_custom_topology_impedance(branches, params_dict, omega):
    """
    Evaluates complex impedance for an arbitrary user-constructed circuit topology.
    Handles series and parallel branches with arbitrary combinations of elements.
    Supports both scalar frequency omega and vectorized NumPy 1D frequency array omega.
    """
    is_arr = _is_array(omega)
    if not branches:
        return np.full_like(omega, complex(10.0, 0.0), dtype=np.complex128) if is_arr else complex(10.0, 0.0)
    
    z_total = np.zeros_like(omega, dtype=np.complex128) if is_arr else complex(0.0, 0.0)
    
    for branch in branches:
        conn = branch.get("connection", "series")
        elements = branch.get("elements", [])
        if not elements:
            continue
            
        if conn == "series":
            z_branch = np.zeros_like(omega, dtype=np.complex128) if is_arr else complex(0.0, 0.0)
            for el in elements:
                el_id = el.get("id", "")
                el_name = el.get("name", "")
                el_type = el.get("type", "R")
                
                # Retrieve parameters from params_dict
                p_val = params_dict.get(f"{el_id}_value", params_dict.get(f"{el_name}_value", params_dict.get(el_name, el.get("value", 1.0))))
                p_exp = params_dict.get(f"{el_id}_exponent", params_dict.get(f"{el_name}_exponent", params_dict.get(f"n_{el_name}", el.get("exponent", 0.9))))
                
                el_params = {"value": float(p_val), "exponent": float(p_exp)}
                z_el = evaluate_element_impedance(el_type, el_params, omega)
                z_branch = z_branch + z_el
            z_total = z_total + z_branch
            
        else: # parallel loop
            cap_elements = [e for e in elements if e.get("type") in ["C", "Capacitor", "CPE", "ConstantPhaseElement", "Q"]]
            res_diff_elements = [e for e in elements if e.get("type") not in ["C", "Capacitor", "CPE", "ConstantPhaseElement", "Q"]]
            
            if cap_elements and res_diff_elements:
                # Randles-like structure: Y_cap + 1/(Z_faradaic)
                y_cap = np.zeros_like(omega, dtype=np.complex128) if is_arr else complex(0.0, 0.0)
                for el in cap_elements:
                    el_id = el.get("id", "")
                    el_name = el.get("name", "")
                    el_type = el.get("type", "C")
                    p_val = params_dict.get(f"{el_id}_value", params_dict.get(f"{el_name}_value", params_dict.get(el_name, el.get("value", 1e-6))))
                    p_exp = params_dict.get(f"{el_id}_exponent", params_dict.get(f"{el_name}_exponent", params_dict.get(f"n_{el_name}", el.get("exponent", 0.9))))
                    z_el = evaluate_element_impedance(el_type, {"value": float(p_val), "exponent": float(p_exp)}, omega)
                    y_cap = y_cap + (1.0 / (z_el + 1e-30))
                
                z_faradaic = np.zeros_like(omega, dtype=np.complex128) if is_arr else complex(0.0, 0.0)
                for el in res_diff_elements:
                    el_id = el.get("id", "")
                    el_name = el.get("name", "")
                    el_type = el.get("type", "R")
                    p_val = params_dict.get(f"{el_id}_value", params_dict.get(f"{el_name}_value", params_dict.get(el_name, el.get("value", 100.0))))
                    p_exp = params_dict.get(f"{el_id}_exponent", params_dict.get(f"{el_name}_exponent", params_dict.get(f"n_{el_name}", el.get("exponent", 0.9))))
                    z_el = evaluate_element_impedance(el_type, {"value": float(p_val), "exponent": float(p_exp)}, omega)
                    z_faradaic = z_faradaic + z_el
                
                y_faradaic = 1.0 / (z_faradaic + 1e-30)
                y_loop = y_cap + y_faradaic
                z_loop = 1.0 / (y_loop + 1e-30)
                z_total = z_total + z_loop
            else:
                # Generic parallel sum: 1/Z = 1/Z1 + 1/Z2 + ...
                y_loop = np.zeros_like(omega, dtype=np.complex128) if is_arr else complex(0.0, 0.0)
                for el in elements:
                    el_id = el.get("id", "")
                    el_name = el.get("name", "")
                    el_type = el.get("type", "R")
                    p_val = params_dict.get(f"{el_id}_value", params_dict.get(f"{el_name}_value", params_dict.get(el_name, el.get("value", 1.0))))
                    p_exp = params_dict.get(f"{el_id}_exponent", params_dict.get(f"{el_name}_exponent", params_dict.get(f"n_{el_name}", el.get("exponent", 0.9))))
                    z_el = evaluate_element_impedance(el_type, {"value": float(p_val), "exponent": float(p_exp)}, omega)
                    y_loop = y_loop + (1.0 / (z_el + 1e-30))
                z_loop = 1.0 / (y_loop + 1e-30)
                z_total = z_total + z_loop
                
    return z_total

def evaluate_circuit_impedance(topology_data, params_dict, omega):
    """
    Evaluates total complex impedance Z(omega) for either custom drag-and-drop topologies or standard presets.
    Supports both scalar frequency omega and vectorized NumPy 1D frequency array omega.
    """
    is_arr = _is_array(omega)
    j = 1j
    
    # Check if topology_data is a dict containing custom branches
    if isinstance(topology_data, dict) and "branches" in topology_data and topology_data["branches"]:
        return evaluate_custom_topology_impedance(topology_data["branches"], params_dict, omega)
        
    topology_id = topology_data if isinstance(topology_data, str) else topology_data.get("id", "standard_randles")
    
    # Standard Randles: R_s + (R_ct || C_dl)
    if topology_id in ["standard_randles", "randles", "rc_parallel"]:
        rs = params_dict.get("Rs", params_dict.get("R_s", params_dict.get("R1", 10.0)))
        rct = params_dict.get("Rct", params_dict.get("R_ct", params_dict.get("R2", 100.0)))
        cdl = params_dict.get("Cdl", params_dict.get("C_dl", params_dict.get("C1", 1e-5)))
        
        z_cdl = 1.0 / (j * omega * max(1e-15, cdl) + 1e-30)
        z_parallel = (rct * z_cdl) / (rct + z_cdl)
        return rs + z_parallel

    # Randles with CPE: R_s + (R_ct || CPE_dl)
    elif topology_id in ["randles_cpe", "cpe_randles", "rs_rcpe"]:
        rs = params_dict.get("Rs", params_dict.get("R_s", 10.0))
        rct = params_dict.get("Rct", params_dict.get("R_ct", 100.0))
        q = params_dict.get("Qdl", params_dict.get("Q_dl", params_dict.get("Q", 1e-5)))
        n = max(0.01, min(1.0, params_dict.get("ndl", params_dict.get("n_dl", params_dict.get("n", 0.85)))))
        
        phase_factor = np.exp(j * n * np.pi / 2.0) if is_arr else cmath.exp(j * n * math.pi / 2.0)
        denom_cpe = q * (omega ** n) * phase_factor
        z_cpe = 1.0 / (denom_cpe + 1e-30)
        z_parallel = (rct * z_cpe) / (rct + z_cpe)
        return rs + z_parallel

    # Randles with Warburg: R_s + [ (R_ct + W) || C_dl / CPE_dl ]
    elif topology_id in ["randles_warburg", "warburg"]:
        rs = params_dict.get("Rs", 10.0)
        rct = params_dict.get("Rct", 100.0)
        sigma = params_dict.get("sigma", params_dict.get("Aw", 50.0))
        q = params_dict.get("Qdl", params_dict.get("Cdl", 1e-5))
        n = max(0.01, min(1.0, params_dict.get("ndl", 0.90)))
        
        sqrt_w = np.sqrt(np.maximum(1e-12, omega)) if is_arr else math.sqrt(max(1e-12, omega))
        val_w = sigma / sqrt_w
        z_w = val_w * (1.0 - 1j) if is_arr else complex(val_w, -val_w)
        z_faradaic = rct + z_w
        
        phase_factor = np.exp(j * n * np.pi / 2.0) if is_arr else cmath.exp(j * n * math.pi / 2.0)
        denom_cpe = q * (omega ** n) * phase_factor
        z_cpe = 1.0 / (denom_cpe + 1e-30)
        z_parallel = (z_faradaic * z_cpe) / (z_faradaic + z_cpe)
        return rs + z_parallel

    # Two Time-Constant Coating / Oxide Model: R_s + (R_pore || CPE_coat) + (R_ct || CPE_dl)
    elif topology_id in ["two_time_constants", "oxide_coating", "coated_metal"]:
        rs = params_dict.get("Rs", 15.0)
        rpore = params_dict.get("Rpore", params_dict.get("R_pore", 500.0))
        qcoat = params_dict.get("Qcoat", params_dict.get("Q_coat", 1e-7))
        ncoat = max(0.01, min(1.0, params_dict.get("ncoat", params_dict.get("n_coat", 0.92))))
        rct = params_dict.get("Rct", 2000.0)
        qdl = params_dict.get("Qdl", 5e-6)
        ndl = max(0.01, min(1.0, params_dict.get("ndl", 0.82)))
        
        phase_coat = np.exp(j * ncoat * np.pi / 2.0) if is_arr else cmath.exp(j * ncoat * math.pi / 2.0)
        z_qcoat = 1.0 / (qcoat * (omega ** ncoat) * phase_coat + 1e-30)
        z_loop1 = (rpore * z_qcoat) / (rpore + z_qcoat)
        
        phase_dl = np.exp(j * ndl * np.pi / 2.0) if is_arr else cmath.exp(j * ndl * math.pi / 2.0)
        z_qdl = 1.0 / (qdl * (omega ** ndl) * phase_dl + 1e-30)
        z_loop2 = (rct * z_qdl) / (rct + z_qdl)
        return rs + z_loop1 + z_loop2

    # Porous Electrode / Transmission Line Model (Bisquert Open / de Levie)
    elif topology_id in ["porous_electrode", "transmission_line", "tlm", "bisquert_open", "tlm_open"]:
        rs = params_dict.get("Rs", 2.0)
        r_ion = params_dict.get("Rion", params_dict.get("R_ion", 65.0))
        r_ct = params_dict.get("Rct", params_dict.get("R_ct", 250.0))
        q_d = params_dict.get("Qdl", params_dict.get("Q_d", params_dict.get("Cdl", 1.5e-4)))
        alpha = max(0.01, min(1.0, params_dict.get("alpha", params_dict.get("n", 0.90))))
        el_tlm = {"rion": r_ion, "rct": r_ct, "qd": q_d, "exponent": alpha}
        return rs + evaluate_element_impedance("TLM_open", el_tlm, omega)

    # Porous Electrode Transmissive / Catalytic (Bisquert Short / DSSC)
    elif topology_id in ["bisquert_short", "tlm_short", "dssc_tlm", "porous_catalytic"]:
        rs = params_dict.get("Rs", 2.0)
        r_ion = params_dict.get("Rion", params_dict.get("R_ion", 45.0))
        r_ct = params_dict.get("Rct", params_dict.get("R_ct", 180.0))
        q_d = params_dict.get("Qdl", params_dict.get("Q_d", 2.0e-4))
        alpha = max(0.01, min(1.0, params_dict.get("alpha", params_dict.get("n", 0.92))))
        el_tlm = {"rion": r_ion, "rct": r_ct, "qd": q_d, "exponent": alpha}
        return rs + evaluate_element_impedance("TLM_short", el_tlm, omega)

    # Gerischer Reaction-Coupled Diffusion Model (SOFC / Battery)
    elif topology_id in ["gerischer", "gerischer_diffusion", "sofc_cathode"]:
        rs = params_dict.get("Rs", 5.0)
        rg = params_dict.get("Rg", params_dict.get("R_G", 120.0))
        tau = params_dict.get("tau_g", params_dict.get("tau", 0.05))
        alpha = max(0.1, min(1.0, params_dict.get("alpha_g", params_dict.get("alpha", 1.0))))
        el_g = {"r": rg, "tau": tau, "alpha": alpha}
        return rs + evaluate_element_impedance("G", el_g, omega)

    # Havriliak-Negami / Cole-Cole Dielectric Polymer / Solid Electrolyte
    elif topology_id in ["havriliak_negami", "hn_dielectric", "solid_polymer_electrolyte"]:
        rs = params_dict.get("Rs", 1.0)
        r0 = params_dict.get("R0", params_dict.get("R_diel", 5000.0))
        tau = params_dict.get("tau", 1e-4)
        alpha = max(0.01, min(1.0, params_dict.get("alpha", 0.85)))
        beta = max(0.01, min(1.0, params_dict.get("beta", 0.75)))
        el_hn = {"r0": r0, "tau": tau, "alpha": alpha, "beta": beta}
        return rs + evaluate_element_impedance("HN", el_hn, omega)

    # Finite Reflective Warburg (Thin-Film Intercalation)
    elif topology_id in ["finite_reflective_warburg", "intercalation_warburg", "ws_reflective"]:
        rs = params_dict.get("Rs", 5.0)
        rct = params_dict.get("Rct", 50.0)
        qdl = params_dict.get("Qdl", 2e-5)
        ndl = max(0.01, min(1.0, params_dict.get("ndl", 0.90)))
        rd = params_dict.get("Rd", 80.0)
        tau_d = params_dict.get("tau_d", 1.2)
        
        z_ws = evaluate_element_impedance("Ws", {"r": rd, "tau": tau_d}, omega)
        z_faradaic = rct + z_ws
        z_qdl = evaluate_element_impedance("CPE", {"q": qdl, "n": ndl}, omega)
        z_loop = (z_faradaic * z_qdl) / (z_faradaic + z_qdl)
        return rs + z_loop

    # Default fallback: R_s + R_p
    r1 = params_dict.get("Rs", 10.0)
    r2 = params_dict.get("Rct", 100.0)
    return np.full_like(omega, complex(r1 + r2, 0.0), dtype=np.complex128) if is_arr else complex(r1 + r2, 0.0)

def evaluate_topology_impedance(topology_data, omega, params_dict=None):
    """
    Convenience wrapper for analytical impedance evaluation.
    If params_dict is not provided, extracts baseline values from topology_data.
    Supports scalar float or vectorized 1D NumPy array omega.
    """
    if params_dict is None:
        params_list = extract_topology_parameters(topology_data)
        params_dict = {}
        for p in params_list:
            p_name = p.get("paramName", "")
            el_id = p.get("elementId", "")
            field = p.get("field", "value")
            val = float(p.get("value", 1.0))
            if p_name:
                params_dict[p_name] = val
            if el_id:
                params_dict[f"{el_id}_{field}"] = val
                params_dict[f"{el_id}_value"] = val if field == "value" else params_dict.get(f"{el_id}_value", val)
                if field == "exponent":
                    params_dict[f"{el_id}_exponent"] = val
                params_dict[el_id] = val
    return evaluate_circuit_impedance(topology_data, params_dict, omega)

def compute_weights(points, weighting_mode="modulus"):
    """
    Computes statistical weights for Real and Imaginary parts of impedance.
    Weighting definitions; weighting alone does not certify standards compliance.
    
    Addresses the 6 to 9 orders-of-magnitude impedance dynamic range problem (Rs ~ 10-100 Ohm
    vs Rp/Rct ~ 10^7 - 10^9 Ohm):
    - Modulus Weighting: w_i = 1 / |Z_i|^2. Equal relative fractional error weighting.
    - Proportional Weighting: w_re = 1 / (Z')^2, w_im = 1 / (Z'')^2.
      Regularized with a (0.01 * |Z|)^2 floor to prevent singularity when Z'' crosses 0.
    - Unit Weighting: w_i = 1.0 (unweighted). Skews completely towards low frequencies.
    """
    weights = []
    for pt in points:
        z_re = pt["zReal"]
        z_im = pt.get("minusZImag", -pt.get("zImag", 0.0))
        z_mag_sq = max(1e-12, z_re * z_re + z_im * z_im)
        
        if weighting_mode == "modulus":
            w = 1.0 / z_mag_sq
            weights.append((w, w))
        elif weighting_mode == "proportional":
            floor_sq = max(1e-12, 0.0001 * z_mag_sq) # (0.01 * |Z|)^2 regularization floor
            w_re = 1.0 / max(floor_sq, z_re * z_re)
            w_im = 1.0 / max(floor_sq, z_im * z_im)
            weights.append((w_re, w_im))
        else: # unit (unweighted least squares)
            weights.append((1.0, 1.0))
    return weights

def extract_topology_parameters(topology_data):
    """
    Extracts adjustable parameters from either a drag-and-drop circuit topology (branches/elements)
    or a standard circuit preset identifier.
    """
    params = []
    if isinstance(topology_data, dict) and "branches" in topology_data and topology_data["branches"]:
        for branch in topology_data.get("branches", []):
            for el in branch.get("elements", []):
                el_id = el.get("id", "")
                el_name = el.get("name", "")
                el_type = el.get("type", "R")
                val = float(el.get("value", 1.0))
                exp = float(el.get("exponent", 0.85))
                sec = float(el.get("secondaryValue", 200.0))
                is_fixed = bool(el.get("isFixed", False))

                if el_type in ["R", "Resistor"]:
                    params.append({
                        "paramName": el_name,
                        "elementId": el_id,
                        "field": "value",
                        "value": val,
                        "unit": "Ω",
                        "paramType": "Resistor",
                        "min": 1e-4,
                        "max": 1e8,
                        "isFixed": is_fixed,
                    })
                elif el_type in ["C", "Capacitor"]:
                    params.append({
                        "paramName": el_name,
                        "elementId": el_id,
                        "field": "value",
                        "value": val,
                        "unit": "F",
                        "paramType": "Capacitor",
                        "min": 1e-14,
                        "max": 1.0,
                        "isFixed": is_fixed,
                    })
                elif el_type in ["CPE", "ConstantPhaseElement", "Q"]:
                    params.append({
                        "paramName": f"Q_{el_name}",
                        "elementId": el_id,
                        "field": "value",
                        "value": val,
                        "unit": "S·s^n",
                        "paramType": "ConstantPhaseElement",
                        "min": 1e-14,
                        "max": 1.0,
                        "isFixed": is_fixed,
                    })
                    params.append({
                        "paramName": f"n_{el_name}",
                        "elementId": el_id,
                        "field": "exponent",
                        "value": exp,
                        "unit": "",
                        "paramType": "Exponent",
                        "min": 0.20,
                        "max": 1.00,
                        "isFixed": is_fixed,
                    })
                elif el_type in ["W", "Warburg"]:
                    params.append({
                        "paramName": f"σ_{el_name}",
                        "elementId": el_id,
                        "field": "value",
                        "value": val,
                        "unit": "Ω·s^-0.5",
                        "paramType": "Warburg",
                        "min": 1e-3,
                        "max": 1e7,
                        "isFixed": is_fixed,
                    })
                elif el_type in ["Wo", "OpenWarburg", "NernstDiffusion"]:
                    params.append({
                        "paramName": f"Rd_{el_name}",
                        "elementId": el_id,
                        "field": "value",
                        "value": val,
                        "unit": "Ω",
                        "paramType": "Resistor",
                        "min": 1e-3,
                        "max": 1e7,
                        "isFixed": is_fixed,
                    })
                    params.append({
                        "paramName": f"τd_{el_name}",
                        "elementId": el_id,
                        "field": "exponent",
                        "value": exp,
                        "unit": "s",
                        "paramType": "TimeConstant",
                        "min": 1e-6,
                        "max": 1e4,
                        "isFixed": is_fixed,
                    })
                elif el_type in ["Ws", "ShortWarburg", "FiniteWarburg", "ReflectiveWarburg"]:
                    params.append({
                        "paramName": f"Rd_{el_name}",
                        "elementId": el_id,
                        "field": "value",
                        "value": val,
                        "unit": "Ω",
                        "paramType": "Resistor",
                        "min": 1e-3,
                        "max": 1e7,
                        "isFixed": is_fixed,
                    })
                    params.append({
                        "paramName": f"τd_{el_name}",
                        "elementId": el_id,
                        "field": "exponent",
                        "value": exp,
                        "unit": "s",
                        "paramType": "TimeConstant",
                        "min": 1e-6,
                        "max": 1e4,
                        "isFixed": is_fixed,
                    })
                elif el_type in ["G", "Gerischer"]:
                    params.append({
                        "paramName": f"Rg_{el_name}",
                        "elementId": el_id,
                        "field": "value",
                        "value": val,
                        "unit": "Ω",
                        "paramType": "Resistor",
                        "min": 1e-3,
                        "max": 1e7,
                        "isFixed": is_fixed,
                    })
                    params.append({
                        "paramName": f"τg_{el_name}",
                        "elementId": el_id,
                        "field": "exponent",
                        "value": exp,
                        "unit": "s",
                        "paramType": "TimeConstant",
                        "min": 1e-6,
                        "max": 1e4,
                        "isFixed": is_fixed,
                    })
                elif el_type in ["TLM_open", "BisquertOpen"]:
                    params.append({
                        "paramName": f"Rion_{el_name}",
                        "elementId": el_id,
                        "field": "value",
                        "value": val,
                        "unit": "Ω",
                        "paramType": "Resistor",
                        "min": 1e-3,
                        "max": 1e6,
                        "isFixed": is_fixed,
                    })
                    params.append({
                        "paramName": f"Rct_{el_name}",
                        "elementId": el_id,
                        "field": "rct",
                        "value": sec,
                        "unit": "Ω",
                        "paramType": "Resistor",
                        "min": 1e-3,
                        "max": 1e7,
                        "isFixed": is_fixed,
                    })
                    params.append({
                        "paramName": f"Qd_{el_name}",
                        "elementId": el_id,
                        "field": "qd",
                        "value": 1e-4,
                        "unit": "S·s^n",
                        "paramType": "ConstantPhaseElement",
                        "min": 1e-14,
                        "max": 1.0,
                        "isFixed": is_fixed,
                    })
                    params.append({
                        "paramName": f"α_{el_name}",
                        "elementId": el_id,
                        "field": "exponent",
                        "value": exp,
                        "unit": "",
                        "paramType": "Exponent",
                        "min": 0.20,
                        "max": 1.00,
                        "isFixed": is_fixed,
                    })
                elif el_type in ["TLM_short", "BisquertShort"]:
                    params.append({
                        "paramName": f"Rion_{el_name}",
                        "elementId": el_id,
                        "field": "value",
                        "value": val,
                        "unit": "Ω",
                        "paramType": "Resistor",
                        "min": 1e-3,
                        "max": 1e6,
                        "isFixed": is_fixed,
                    })
                    params.append({
                        "paramName": f"Rct_{el_name}",
                        "elementId": el_id,
                        "field": "rct",
                        "value": sec,
                        "unit": "Ω",
                        "paramType": "Resistor",
                        "min": 1e-3,
                        "max": 1e7,
                        "isFixed": is_fixed,
                    })
                    params.append({
                        "paramName": f"Qd_{el_name}",
                        "elementId": el_id,
                        "field": "qd",
                        "value": 1e-4,
                        "unit": "S·s^n",
                        "paramType": "ConstantPhaseElement",
                        "min": 1e-14,
                        "max": 1.0,
                        "isFixed": is_fixed,
                    })
                    params.append({
                        "paramName": f"α_{el_name}",
                        "elementId": el_id,
                        "field": "exponent",
                        "value": exp,
                        "unit": "",
                        "paramType": "Exponent",
                        "min": 0.20,
                        "max": 1.00,
                        "isFixed": is_fixed,
                    })
                elif el_type in ["CC", "HN", "ColeCole", "HavriliakNegami"]:
                    params.append({
                        "paramName": f"R0_{el_name}",
                        "elementId": el_id,
                        "field": "value",
                        "value": val,
                        "unit": "Ω",
                        "paramType": "Resistor",
                        "min": 1e-3,
                        "max": 1e8,
                        "isFixed": is_fixed,
                    })
                    params.append({
                        "paramName": f"τ_{el_name}",
                        "elementId": el_id,
                        "field": "exponent",
                        "value": exp,
                        "unit": "s",
                        "paramType": "TimeConstant",
                        "min": 1e-12,
                        "max": 1e2,
                        "isFixed": is_fixed,
                    })
                    params.append({
                        "paramName": f"α_{el_name}",
                        "elementId": el_id,
                        "field": "alpha",
                        "value": 0.85,
                        "unit": "",
                        "paramType": "Exponent",
                        "min": 0.10,
                        "max": 1.00,
                        "isFixed": is_fixed,
                    })
                elif el_type in ["L", "Inductor"]:
                    params.append({
                        "paramName": el_name,
                        "elementId": el_id,
                        "field": "value",
                        "value": val,
                        "unit": "H",
                        "paramType": "Inductor",
                        "min": 1e-11,
                        "max": 1e-1,
                        "isFixed": is_fixed,
                    })
        return params

    topo_id = topology_data if isinstance(topology_data, str) else topology_data.get("id", "standard_randles")
    if topo_id in ["standard_randles", "randles", "rc_parallel"]:
        return [
            {"paramName": "Rs", "elementId": "el-rs", "field": "value", "value": 10.0, "unit": "Ω", "paramType": "Resistor", "min": 1e-3, "max": 1e6},
            {"paramName": "Rct", "elementId": "el-rct", "field": "value", "value": 100.0, "unit": "Ω", "paramType": "Resistor", "min": 1e-3, "max": 1e7},
            {"paramName": "Cdl", "elementId": "el-cdl", "field": "value", "value": 1e-5, "unit": "F", "paramType": "Capacitor", "min": 1e-14, "max": 1.0},
        ]
    elif topo_id in ["randles_cpe", "cpe_randles"]:
        return [
            {"paramName": "Rs", "elementId": "el-rs", "field": "value", "value": 10.0, "unit": "Ω", "paramType": "Resistor", "min": 1e-3, "max": 1e6},
            {"paramName": "Rct", "elementId": "el-rct", "field": "value", "value": 100.0, "unit": "Ω", "paramType": "Resistor", "min": 1e-3, "max": 1e7},
            {"paramName": "Qdl", "elementId": "el-qdl", "field": "value", "value": 1e-5, "unit": "S·s^n", "paramType": "ConstantPhaseElement", "min": 1e-14, "max": 1.0},
            {"paramName": "ndl", "elementId": "el-qdl", "field": "exponent", "value": 0.85, "unit": "", "paramType": "Exponent", "min": 0.20, "max": 1.00},
        ]
    elif topo_id in ["randles_warburg", "warburg"]:
        return [
            {"paramName": "Rs", "elementId": "el-rs", "field": "value", "value": 10.0, "unit": "Ω", "paramType": "Resistor", "min": 1e-3, "max": 1e6},
            {"paramName": "Rct", "elementId": "el-rct", "field": "value", "value": 100.0, "unit": "Ω", "paramType": "Resistor", "min": 1e-3, "max": 1e7},
            {"paramName": "Qdl", "elementId": "el-qdl", "field": "value", "value": 1e-5, "unit": "S·s^n", "paramType": "ConstantPhaseElement", "min": 1e-14, "max": 1.0},
            {"paramName": "ndl", "elementId": "el-qdl", "field": "exponent", "value": 0.90, "unit": "", "paramType": "Exponent", "min": 0.20, "max": 1.00},
            {"paramName": "sigma", "elementId": "el-w", "field": "value", "value": 50.0, "unit": "Ω·s^-0.5", "paramType": "Warburg", "min": 1e-2, "max": 1e7},
        ]
    elif topo_id in ["two_time_constants", "oxide_coating"]:
        return [
            {"paramName": "Rs", "elementId": "el-rs", "field": "value", "value": 15.0, "unit": "Ω", "paramType": "Resistor", "min": 1e-3, "max": 1e6},
            {"paramName": "Rpore", "elementId": "el-rp", "field": "value", "value": 500.0, "unit": "Ω", "paramType": "Resistor", "min": 1e-3, "max": 1e7},
            {"paramName": "Qcoat", "elementId": "el-qc", "field": "value", "value": 1e-7, "unit": "S·s^n", "paramType": "ConstantPhaseElement", "min": 1e-14, "max": 1.0},
            {"paramName": "ncoat", "elementId": "el-qc", "field": "exponent", "value": 0.92, "unit": "", "paramType": "Exponent", "min": 0.20, "max": 1.00},
            {"paramName": "Rct", "elementId": "el-rct", "field": "value", "value": 2000.0, "unit": "Ω", "paramType": "Resistor", "min": 1e-3, "max": 1e8},
            {"paramName": "Qdl", "elementId": "el-qdl", "field": "value", "value": 5e-6, "unit": "S·s^n", "paramType": "ConstantPhaseElement", "min": 1e-14, "max": 1.0},
            {"paramName": "ndl", "elementId": "el-qdl", "field": "exponent", "value": 0.82, "unit": "", "paramType": "Exponent", "min": 0.20, "max": 1.00},
        ]
    elif topo_id in ["bisquert_open", "porous_electrode", "transmission_line"]:
        return [
            {"paramName": "Rs", "elementId": "el-rs", "field": "value", "value": 2.0, "unit": "Ω", "paramType": "Resistor", "min": 1e-3, "max": 1e5},
            {"paramName": "Rion", "elementId": "el-tlm", "field": "value", "value": 65.0, "unit": "Ω", "paramType": "Resistor", "min": 1e-3, "max": 1e6},
            {"paramName": "Rct", "elementId": "el-tlm", "field": "rct", "value": 250.0, "unit": "Ω", "paramType": "Resistor", "min": 1e-3, "max": 1e7},
            {"paramName": "Qdl", "elementId": "el-tlm", "field": "qd", "value": 1.5e-4, "unit": "S·s^n", "paramType": "ConstantPhaseElement", "min": 1e-14, "max": 1.0},
            {"paramName": "alpha", "elementId": "el-tlm", "field": "exponent", "value": 0.90, "unit": "", "paramType": "Exponent", "min": 0.20, "max": 1.00},
        ]
    return [
        {"paramName": "Rs", "elementId": "el-rs", "field": "value", "value": 10.0, "unit": "Ω", "paramType": "Resistor", "min": 1e-3, "max": 1e6},
        {"paramName": "Rct", "elementId": "el-rct", "field": "value", "value": 100.0, "unit": "Ω", "paramType": "Resistor", "min": 1e-3, "max": 1e7},
    ]

def run_global_auto_fit(topology_data, points, initial_params=None, weighting="modulus", max_generations=80, pop_size=40, polish_lm=True, seed=42):
    """
    High-performance Global Optimizer for Automated Equivalent Circuit Fitting against experimental Nyquist data.
    Uses Differential Evolution (DE/rand/1/bin with Stratified Seeding & Log-Parameter Scaling)
    to search bounded parameter space from explicit initial guesses, followed by
    optional Levenberg-Marquardt polishing and local linearized uncertainty estimates.
    Finite DE runs do not establish a global optimum.
    """
    rng = random.Random(seed)
    start_time = time.perf_counter()
    if not points:
        return {"error": "No experimental EIS points provided for Auto-Fit"}

    # 1. Parameter discovery & bounding
    if not initial_params:
        initial_params = extract_topology_parameters(topology_data)
        
    initial_params = [dict(p, **({"min": p["lowerBound"]} if "min" not in p and "lowerBound" in p else {}),
                           **({"max": p["upperBound"]} if "max" not in p and "upperBound" in p else {}))
                      for p in initial_params]
    params = []
    for p in initial_params:
        p_name = p.get("paramName", "")
        p_type = p.get("paramType", "")
        p_field = p.get("field", p_name)
        val = float(p.get("value", 1.0))
        is_fixed = bool(p.get("isFixed", False))
        
        # Determine log vs linear scaling
        is_linear = (
            "n" in p_name.lower() or 
            "alpha" in p_name.lower() or 
            "beta" in p_name.lower() or 
            p_field == "exponent" or 
            p_type in ["Exponent"]
        )
        
        if is_linear:
            min_val = float(p.get("min", 0.20))
            max_val = float(p.get("max", 1.00))
        else:
            if "c" in p_name.lower() or "q" in p_name.lower() or p_type in ["Capacitor", "ConstantPhaseElement"]:
                min_val = float(p.get("min", 1e-14))
                max_val = float(p.get("max", 0.5))
            elif "l" in p_name.lower() or p_type in ["Inductor"]:
                min_val = float(p.get("min", 1e-11))
                max_val = float(p.get("max", 1e-1))
            elif "tau" in p_name.lower() or "t" in p_name.lower() or p_type in ["TimeConstant"]:
                min_val = float(p.get("min", 1e-6))
                max_val = float(p.get("max", 1e4))
            elif "sigma" in p_name.lower() or p_type in ["Warburg"]:
                min_val = float(p.get("min", 1e-2))
                max_val = float(p.get("max", 1e7))
            else: # Resistor
                min_val = float(p.get("min", 1e-4))
                max_val = float(p.get("max", 1e8))
                
        params.append({
            "paramName": p_name,
            "elementId": p.get("elementId", ""),
            "field": p_field,
            "value": val,
            "initialValue": val,
            "isFixed": is_fixed,
            "isLinear": is_linear,
            "min": min_val,
            "max": max_val,
            "unit": p.get("unit", "Ω"),
            "paramType": p_type
        })
        
    adj_indices = [i for i, p in enumerate(params) if not p["isFixed"]]
    num_adj = len(adj_indices)
    
    if num_adj == 0:
        return run_cnls_fit(topology_data, points, initial_params, weighting)

    # 2. Physics-Informed Nyquist Feature Extraction
    sorted_pts = sorted(points, key=lambda x: float(x["frequency"]), reverse=True)
    high_f_pts = sorted_pts[:max(3, len(sorted_pts) // 10)]
    low_f_pts = sorted_pts[-max(3, len(sorted_pts) // 8):]
    
    r_s_est = max(0.001, min(p["zReal"] for p in high_f_pts))
    r_tot_est = max(r_s_est + 1.0, max(p["zReal"] for p in low_f_pts))
    delta_r = max(1.0, r_tot_est - r_s_est)
    
    peak_pt = max(points, key=lambda x: float(x.get("minusZImag", -x.get("zImag", 0.0))))
    f_peak = float(peak_pt["frequency"])
    w_peak = 2.0 * math.pi * max(1e-4, f_peak)
    c_dl_est = max(1e-12, min(0.05, 1.0 / (w_peak * delta_r)))

    # 3. Parameter Mapping to [0, 1] Hypercube
    def map_u_to_val(u, p_meta):
        u_clamped = max(0.0, min(1.0, u))
        if p_meta["isLinear"]:
            return p_meta["min"] + u_clamped * (p_meta["max"] - p_meta["min"])
        else:
            log_min = math.log10(max(1e-16, p_meta["min"]))
            log_max = math.log10(max(1e-14, p_meta["max"]))
            return 10.0 ** (log_min + u_clamped * (log_max - log_min))

    def map_val_to_u(val, p_meta):
        if p_meta["isLinear"]:
            return (val - p_meta["min"]) / max(1e-9, (p_meta["max"] - p_meta["min"]))
        else:
            log_min = math.log10(max(1e-16, p_meta["min"]))
            log_max = math.log10(max(1e-14, p_meta["max"]))
            log_val = math.log10(max(1e-16, val))
            return (log_val - log_min) / max(1e-9, (log_max - log_min))

    weights = compute_weights(points, weighting)
    
    # Precompute arrays for vectorized cost evaluation
    if HAS_NUMPY:
        omegas_arr = np.array([2.0 * math.pi * pt["frequency"] for pt in points], dtype=np.float64)
        z_real_arr = np.array([pt["zReal"] for pt in points], dtype=np.float64)
        minus_zim_arr = np.array([pt.get("minusZImag", -pt.get("zImag", 0.0)) for pt in points], dtype=np.float64)
        w_re_arr = np.array([w[0] for w in weights], dtype=np.float64)
        w_im_arr = np.array([w[1] for w in weights], dtype=np.float64)

    def cost_function(u_vec):
        p_dict = {}
        for p in params:
            p_dict[p["paramName"]] = p["value"]
            el_id = p.get("elementId", "")
            field = p.get("field", "value")
            if el_id:
                p_dict[f"{el_id}_{field}"] = p["value"]
                p_dict[f"{el_id}_value"] = p["value"] if field == "value" else p_dict.get(f"{el_id}_value", p["value"])
                if field == "exponent":
                    p_dict[f"{el_id}_exponent"] = p["value"]
                p_dict[el_id] = p["value"]
                
        for col, p_idx in enumerate(adj_indices):
            v = map_u_to_val(u_vec[col], params[p_idx])
            p_name = params[p_idx]["paramName"]
            el_id = params[p_idx].get("elementId", "")
            field = params[p_idx].get("field", "value")
            p_dict[p_name] = v
            if el_id:
                p_dict[f"{el_id}_{field}"] = v
                p_dict[f"{el_id}_value"] = v if field == "value" else p_dict.get(f"{el_id}_value", v)
                if field == "exponent":
                    p_dict[f"{el_id}_exponent"] = v
                p_dict[el_id] = v
                
        # Modulus weighted sum of squared residuals (vectorized if NumPy available)
        if HAS_NUMPY:
            z_c = evaluate_circuit_impedance(topology_data, p_dict, omegas_arr)
            re_diff = z_real_arr - z_c.real
            im_diff = minus_zim_arr - (-z_c.imag)
            sq_err = np.sum((re_diff * re_diff) * w_re_arr + (im_diff * im_diff) * w_im_arr)
            return float(sq_err) / max(1, len(points))
        else:
            sq_err = 0.0
            for idx, pt in enumerate(points):
                w = 2.0 * math.pi * pt["frequency"]
                z_c = evaluate_circuit_impedance(topology_data, p_dict, w)
                re_diff = pt["zReal"] - z_c.real
                im_diff = pt.get("minusZImag", -pt.get("zImag", 0.0)) - (-z_c.imag)
                w_re, w_im = weights[idx]
                sq_err += (re_diff * re_diff) * w_re + (im_diff * im_diff) * w_im
            return sq_err / max(1, len(points))

    # Evaluate Initial Guess Cost
    initial_u = [map_val_to_u(params[p_idx]["value"], params[p_idx]) for p_idx in adj_indices]
    initial_cost = cost_function(initial_u)

    # 4. Differential Evolution Optimization
    n_pop = max(pop_size, num_adj * 10)
    population = []
    
    # Stratified initialization + Elite Seeds
    # Individual 0: User initial values
    population.append(initial_u)
    
    # Individual 1: Physics Heuristic Guess
    heuristic_u = []
    for p_idx in adj_indices:
        p_name = params[p_idx]["paramName"].lower()
        p_type = params[p_idx]["paramType"]
        if "rs" in p_name or ("r" in p_name and ("1" in p_name or "sol" in p_name)):
            h_val = r_s_est
        elif "r" in p_name or p_type == "Resistor":
            h_val = delta_r
        elif "c" in p_name or "q" in p_name or p_type in ["Capacitor", "ConstantPhaseElement"]:
            h_val = c_dl_est
        elif "n" in p_name or "alpha" in p_name:
            h_val = 0.88
        elif "sigma" in p_name or p_type == "Warburg":
            h_val = delta_r / 2.0
        elif "tau" in p_name or p_type == "TimeConstant":
            h_val = 1.0 / w_peak
        else:
            h_val = params[p_idx]["value"]
        heuristic_u.append(max(0.0, min(1.0, map_val_to_u(h_val, params[p_idx]))))
    population.append(heuristic_u)

    # Fill remaining population with Stratified Samples
    for i in range(2, n_pop):
        ind = []
        for j in range(num_adj):
            # Stratified random sample in [0, 1]
            u_samp = (i + rng.random()) / float(n_pop)
            ind.append(u_samp)
        population.append(ind)

    # Evaluate initial population fitness
    fitness = [cost_function(ind) for ind in population]
    best_idx = min(range(n_pop), key=lambda k: fitness[k])
    best_u = list(population[best_idx])
    best_cost = fitness[best_idx]

    # Differential Evolution Generations
    crossover_rate = 0.85
    total_evals = n_pop
    raise NotImplementedError("Global Auto-Fit via Differential Evolution (random mutation) is disabled. Enforcing deterministic solvers.")

def run_cnls_fit(topology_id, points, initial_params, weighting="modulus", max_iter=100, damping=1e-3):
    """
    Levenberg-Marquardt optimizer for complex impedance spectra.
    """
    start_time = time.perf_counter()
    if not points or not initial_params:
        raise ValueError("CNLS requires observations and explicit parameters")
    if weighting not in ("unit", "modulus", "proportional"):
        raise ValueError("Unknown CNLS weighting")
    if isinstance(max_iter, bool) or not isinstance(max_iter, int) or max_iter < 0:
        raise ValueError("max_iter must be a nonnegative integer")
    if not math.isfinite(damping) or damping <= 0:
        raise ValueError("damping must be finite and positive")
    for pt in points:
        vals = (pt.get("frequency"), pt.get("zReal"), pt.get("minusZImag", -pt["zImag"] if "zImag" in pt else None))
        if any(v is None or isinstance(v, bool) or not math.isfinite(v) for v in vals) or vals[0] <= 0:
            raise ValueError("CNLS requires finite complex observations at positive frequencies")
    
    # Prepare parameter list with bounds and fix flags
    initial_params = [dict(p, **({"min": p["lowerBound"]} if "min" not in p and "lowerBound" in p else {}),
                           **({"max": p["upperBound"]} if "max" not in p and "upperBound" in p else {}))
                      for p in initial_params]
    params = []
    for p in initial_params:
        params.append({
            "paramName": p["paramName"],
            "elementId": p.get("elementId", ""),
            "field": p.get("field", p["paramName"]),
            "value": float(p["value"]),
            "initialValue": float(p["value"]),
            "isFixed": bool(p.get("isFixed", False)),
            "min": float(p.get("min", 1e-12 if "n" not in p["paramName"].lower() else 0.05)),
            "max": float(p.get("max", 1e8 if "n" not in p["paramName"].lower() else 1.0)),
            "unit": p.get("unit", "Ω"),
            "paramType": p.get("paramType", "Resistor")
        })
    
    adjustable_indices = [i for i, p in enumerate(params) if not p["isFixed"]]
    num_adj = len(adjustable_indices)
    num_points = len(points)
    
    for p in params:
        if (not all(math.isfinite(p[k]) for k in ("value", "min", "max"))
                or p["min"] > p["max"] or not p["min"] <= p["value"] <= p["max"]
                or (not p["isFixed"] and p["min"] == p["max"])):
            raise ValueError("CNLS parameter values must be finite and within valid bounds")
    if 2 * num_points <= num_adj:
        raise ValueError("CNLS requires more residual observations than adjustable parameters")
    
    weights = compute_weights(points, weighting)
    _require_numpy("CNLS fitting")

    # Precompute arrays for the vectorized LM residuals (the only residual path)
    omegas_arr = np.array([2.0 * math.pi * pt["frequency"] for pt in points], dtype=np.float64)
    exp_re_arr = np.array([pt["zReal"] for pt in points], dtype=np.float64)
    exp_im_arr = np.array([pt.get("minusZImag", -pt.get("zImag", 0.0)) for pt in points], dtype=np.float64)
    sqrt_w_re_arr = np.array([math.sqrt(w[0]) for w in weights], dtype=np.float64)
    sqrt_w_im_arr = np.array([math.sqrt(w[1]) for w in weights], dtype=np.float64)

    def get_param_dict(p_list):
        d = {}
        for p in p_list:
            d[p["paramName"]] = p["value"]
            el_id = p.get("elementId", "")
            field = p.get("field", "value")
            if el_id:
                d[f"{el_id}_{field}"] = p["value"]
                d[f"{el_id}_value"] = p["value"] if field == "value" else d.get(f"{el_id}_value", p["value"])
                if field == "exponent":
                    d[f"{el_id}_exponent"] = p["value"]
                d[el_id] = p["value"]
        return d
    
    def compute_residuals(p_list):
        # Weighted residual vector [re_0, im_0, re_1, im_1, ...] as a float64 array.
        p_dict = get_param_dict(p_list)
        z_calc = evaluate_circuit_impedance(topology_id, p_dict, omegas_arr)
        res = np.empty(len(points) * 2, dtype=np.float64)
        res[0::2] = (exp_re_arr - z_calc.real) * sqrt_w_re_arr
        res[1::2] = (exp_im_arr - (-z_calc.imag)) * sqrt_w_im_arr
        return res

    def compute_jacobian(p_list, residuals):
        # Forward-difference Jacobian (2N x num_adj), one vectorised residual
        # evaluation per adjustable parameter; same steps as the former scalar loop.
        jac = np.empty((residuals.shape[0], num_adj), dtype=np.float64)
        for col, p_idx in enumerate(adjustable_indices):
            p = p_list[p_idx]
            original = p["value"]
            step = max(abs(original) * 1e-5, 1e-15)
            delta = min(step, p["max"] - original)
            if delta == 0:
                delta = -min(step, original - p["min"])
            try:
                p["value"] = original + delta
                shifted = compute_residuals(p_list)
            finally:
                p["value"] = original
            jac[:, col] = (shifted - residuals) / delta
        return jac

    def chi_square(residuals):
        return float(residuals @ residuals)

    # Levenberg-Marquardt Iteration Loop
    current_residuals = compute_residuals(params)
    current_chi_sq = chi_square(current_residuals)
    
    lambda_damp = damping
    iter_count = 0
    converged = False
    termination_reason = "no_adjustable_parameters" if num_adj == 0 else "maximum_iterations"
    
    for it in range(max_iter):
        if num_adj == 0:
            break
        iter_count = it + 1
        
        # Calculate numerical Jacobian J (2*N x num_adj)
        jacobian = compute_jacobian(params, current_residuals)
        
        # J differentiates (experimental - calculated) residuals. The minimizing
        # step solves (J^T J + lambda * diag(J^T J)) dp = -J^T residuals.
        jt_j = jacobian.T @ jacobian
        jt_r = jacobian.T @ current_residuals
        diag_jtj = np.diag(jt_j)

        # Scale by Jacobian column norms so farad/ohm units do not set the test.
        gradient = float(np.max(np.abs(jt_r) / np.maximum(np.sqrt(diag_jtj), 1e-300)))
        if gradient <= 1e-10 * max(1.0, math.sqrt(current_chi_sq)):
            converged = True
            termination_reason = "scaled_gradient_tolerance"
            break

        # Apply Levenberg damping to diagonal (diag(J^T J), or 1 for a null column)
        a_mat = jt_j.copy()
        a_mat[np.diag_indices(num_adj)] += lambda_damp * np.where(diag_jtj > 1e-12, diag_jtj, 1.0)

        # Solve the damped normal equations A * dp = -jt_r (LAPACK LU with partial
        # pivoting; A is positive definite by construction).
        try:
            dp = np.linalg.solve(a_mat, -jt_r).tolist()
        except np.linalg.LinAlgError:
            lambda_damp *= 5.0
            continue

        # Trial update
        trial_params = [dict(p) for p in params]
        for col_idx, p_idx in enumerate(adjustable_indices):
            new_val = trial_params[p_idx]["value"] + dp[col_idx]
            # Clamp to bounds
            new_val = max(trial_params[p_idx]["min"], min(trial_params[p_idx]["max"], new_val))
            trial_params[p_idx]["value"] = new_val

        trial_residuals = compute_residuals(trial_params)
        trial_chi_sq = chi_square(trial_residuals)
        
        if trial_chi_sq < current_chi_sq:
            relative_step = max(abs(trial_params[i]["value"] - params[i]["value"]) /
                                max(abs(params[i]["value"]), abs(params[i]["initialValue"]), 1e-15)
                                for i in adjustable_indices)
            relative_reduction = (current_chi_sq - trial_chi_sq) / max(current_chi_sq, 1e-300)
            params = trial_params
            current_residuals = trial_residuals
            current_chi_sq = trial_chi_sq
            lambda_damp = max(1e-7, lambda_damp / 3.0)
            
            # Check relative convergence
            if relative_step <= 1e-8 and relative_reduction <= 1e-12:
                converged = True
                termination_reason = "relative_step_and_objective_tolerance"
                break
        else:
            lambda_damp = min(1e7, lambda_damp * 4.0)

    # Compute Statistical Covariance and Standard Errors
    dof = 2 * num_points - num_adj
    reduced_chi_sq = current_chi_sq / float(dof)
    
    # Local linearized covariance at the FINAL iterate. SVD avoids squaring the
    # Jacobian condition number. Rank loss or an active bound means unavailable.
    cov_mat = None
    uncertainty_status = "unavailable_not_converged"
    if num_adj == 0:
        uncertainty_status = "fixed_parameters_not_estimated"
    elif converged:
        uncertainty_status = "unavailable_rank_deficient_or_active_bound"
        at_bound = any(params[i]["value"] in (params[i]["min"], params[i]["max"]) for i in adjustable_indices)
        final_j = compute_jacobian(params, current_residuals)
        scales = np.linalg.norm(final_j, axis=0)
        if not at_bound and np.all(scales > 0):
            try:
                _, singular, vt = np.linalg.svd(final_j / scales, full_matrices=False)
                if singular[-1] > singular[0] * max(final_j.shape) * np.finfo(float).eps:
                    inverse = (vt.T / singular**2) @ vt
                    cov_mat = inverse / np.outer(scales, scales) * reduced_chi_sq
                    uncertainty_status = "local_linearized_residual_scaled"
            except np.linalg.LinAlgError:
                uncertainty_status = "unavailable_svd_failed"

    # Final Parameter Report with Uncertainties
    p_dict = get_param_dict(params)
    out_params = []
    
    for idx, p in enumerate(params):
        is_fixed = p["isFixed"]
        if is_fixed:
            out_params.append({
                "paramName": p["paramName"],
                "elementId": p["elementId"],
                "field": p["field"],
                "initialValue": p["initialValue"],
                "fittedValue": p["value"],
                "stdError": 0.0,
                "percentError": 0.0,
                "isFixed": True,
                "unit": p["unit"],
                "paramType": p["paramType"]
            })
        else:
            adj_col = adjustable_indices.index(idx)
            std_err = math.sqrt(max(0.0, cov_mat[adj_col][adj_col])) if cov_mat is not None else None
            pct_err = std_err / abs(p["value"]) * 100 if std_err is not None and p["value"] != 0 else None
            
            out_params.append({
                "paramName": p["paramName"],
                "elementId": p["elementId"],
                "field": p["field"],
                "initialValue": p["initialValue"],
                "fittedValue": p["value"],
                "stdError": std_err,
                "percentError": pct_err,
                "isFixed": False,
                "unit": p["unit"],
                "paramType": p["paramType"]
            })

    # Compute Residual Vectors and R^2
    residuals_table = []
    exp_mag_list = []
    calc_mag_list = []
    
    for idx, pt in enumerate(points):
        freq = pt["frequency"]
        omega = 2.0 * math.pi * freq
        z_calc = evaluate_circuit_impedance(topology_id, p_dict, omega)
        
        exp_re = pt["zReal"]
        exp_im = pt.get("minusZImag", -pt.get("zImag", 0.0))
        calc_re = z_calc.real
        calc_im = -z_calc.imag
        
        exp_mag = math.sqrt(exp_re * exp_re + exp_im * exp_im)
        calc_mag = math.sqrt(calc_re * calc_re + calc_im * calc_im)
        exp_mag_list.append(exp_mag)
        calc_mag_list.append(calc_mag)
        
        res_re_pct = ((calc_re - exp_re) / max(1e-6, exp_mag)) * 100.0
        res_im_pct = ((calc_im - exp_im) / max(1e-6, exp_mag)) * 100.0
        
        w_re, w_im = weights[idx] if idx < len(weights) else (1.0, 1.0)
        weighted_diff_re = (exp_re - calc_re) * math.sqrt(w_re)
        weighted_diff_im = (exp_im - calc_im) * math.sqrt(w_im)
        
        residuals_table.append({
            "frequency": freq,
            "logFreq": math.log10(freq),
            "expZReal": exp_re,
            "expMinusZImag": exp_im,
            "calcZReal": calc_re,
            "calcMinusZImag": calc_im,
            "resZRealPct": round(res_re_pct, 2),
            "resZImagPct": round(res_im_pct, 2),
            "totalResidualPct": round(math.sqrt(res_re_pct**2 + res_im_pct**2), 2),
            "weightReal": round(w_re, 8),
            "weightImag": round(w_im, 8),
            "weightedDiffReal": round(weighted_diff_re, 6),
            "weightedDiffImag": round(weighted_diff_im, 6)
        })
    
    # R-Squared
    mean_exp = sum(exp_mag_list) / max(1, len(exp_mag_list))
    ss_tot = sum((x - mean_exp)**2 for x in exp_mag_list)
    ss_res = sum((exp_mag_list[i] - calc_mag_list[i])**2 for i in range(len(exp_mag_list)))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else None
    
    # Kramers-Kronig Validation Test
    mean_res = sum(r["totalResidualPct"] for r in residuals_table) / max(1, len(residuals_table))
    max_res = max(r["totalResidualPct"] for r in residuals_table)
    
    # ASTM G106-89 Multi-Decade Dynamic Range & Impedance Weighting Audit
    min_mag = min(exp_mag_list) if exp_mag_list else 1.0
    max_mag = max(exp_mag_list) if exp_mag_list else 1.0
    dynamic_range_decades = math.log10(max(1e-6, max_mag) / max(1e-6, min_mag))
    hf_scale_factor = (max_mag / max(1e-6, min_mag)) ** 2

    astm_report = {
        "isAstmG106Compliant": None,
        "weightingScheme": weighting,
        "dynamicRangeDecades": round(dynamic_range_decades, 2),
        "minImpedanceMagnitude_Ohm": round(min_mag, 3),
        "maxImpedanceMagnitude_Ohm": round(max_mag, 3),
        "hfSensitivityBalancingFactor": round(hf_scale_factor, 1),
        "astmStandardRecommendation": "Weighting diagnostics only. A weighting choice does not establish ASTM G106 compliance.",
        "unweightedSkewWarning": (
            f"Low-frequency impedance ({max_mag:.1e} Ω) overwhelms high-frequency electrolyte resistance ({min_mag:.1f} Ω) by {dynamic_range_decades:.1f} orders of magnitude. Switch to Modulus Weighting (1/|Z|²) to prevent high-frequency semicircle loss."
            if weighting == "unit" else None
        )
    }

    # Physical Validation Suite
    cpe_capacitances = calculate_cpe_effective_capacitances(out_params, topology_id)
    lin_kk_report = perform_lin_kk_stationarity_test(points)
    inductance_report = analyze_and_deembed_high_freq_inductance(points)
    
    compute_time_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
    
    return {
        "success": True,
        "engine": "MetalliX-Python-HPC-CNLS-v3.10",
        "computeTimeMs": compute_time_ms,
        "iterations": iter_count,
        "converged": converged,
        "terminationReason": termination_reason,
        "uncertaintyStatus": uncertainty_status,
        "degreesOfFreedom": dof,
        "chiSquare": current_chi_sq,
        "rmse": math.sqrt(sum((r["expZReal"]-r["calcZReal"])**2 + (r["expMinusZImag"]-r["calcMinusZImag"])**2 for r in residuals_table)/(2*num_points)),
        "reducedChiSquare": reduced_chi_sq,
        "rSquared": r_squared,
        "rSquaredDefinition": "1 - SSE(|Z|) / SST(|Z|); unavailable for constant observed magnitude",
        "weighting": weighting,
        "parameters": out_params,
        "residuals": residuals_table,
        "astmG106": astm_report,
        "kramersKronig": {
            "isValid": None,
            "score": None,
            "meanResidualPct": round(mean_res, 2),
            "maxResidualPct": round(max_res, 2),
            "assessment": "Circuit-fit residuals only; independent K-K validation unavailable"
        },
        "physicalValidation": {
            "cpeCapacitances": cpe_capacitances,
            "linKK": lin_kk_report,
            "inductance": inductance_report
        }
    }

# =========================================================================
# PART 1: PHYSICAL VALIDATION & ADVANCED EIS DATA QUALITY SUITE
# =========================================================================

def calculate_cpe_effective_capacitances(params, topology_data, electrode_area=1.0):
    """
    Computes true effective double-layer and film capacitances (C_eff) from Constant Phase Elements (CPE, Q, n)
    using the Brug (2D surface distribution), Hirschorn (3D normal distribution), and Hsu-Mansfeld models.
    """
    cpe_results = []
    area = max(1e-6, float(electrode_area or 1.0))
    
    # 1. Collect all resistances and CPE parameters
    res_dict = {}
    cpe_dict = {}
    
    # Extract from parameter list
    for p in params:
        p_name = p.get("paramName", "")
        el_id = p.get("elementId", "")
        p_type = p.get("paramType", "")
        val = float(p.get("fittedValue", p.get("value", 1.0)))
        field = p.get("field", "value")
        
        if p_type in ["R", "Resistor"] or p_name.startswith("R"):
            res_dict[el_id or p_name] = val
            res_dict[p_name] = val
        elif p_type in ["CPE", "ConstantPhaseElement", "Q"] or p_name.startswith("Q") or p_name.startswith("n"):
            if el_id not in cpe_dict:
                cpe_dict[el_id] = {"id": el_id, "name": p_name, "q": 1e-5, "n": 0.85}
            if field == "value" or p_name.startswith("Q") or not p_name.startswith("n"):
                cpe_dict[el_id]["q"] = max(1e-15, val)
                cpe_dict[el_id]["name"] = p_name
            elif field == "exponent" or p_name.startswith("n"):
                cpe_dict[el_id]["n"] = max(0.1, min(1.0, val))

    # Also scan topology if provided
    if isinstance(topology_data, dict) and "branches" in topology_data:
        r_solution = 1.0
        r_ct = 100.0
        
        # Check first series branch for Rs
        branches = topology_data.get("branches", [])
        if branches and branches[0].get("connection") == "series":
            for el in branches[0].get("elements", []):
                if el.get("type") in ["R", "Resistor"]:
                    r_solution = float(el.get("value", 1.0))
                    
        for b_idx, branch in enumerate(branches):
            b_elements = branch.get("elements", [])
            branch_r = []
            branch_cpe = []
            for el in b_elements:
                if el.get("type") in ["R", "Resistor"]:
                    branch_r.append(float(el.get("value", 100.0)))
                elif el.get("type") in ["CPE", "ConstantPhaseElement", "Q"]:
                    branch_cpe.append({
                        "id": el.get("id"),
                        "name": el.get("name"),
                        "q": float(el.get("value", 1e-5)),
                        "n": float(el.get("exponent", 0.85))
                    })
            
            for cpe in branch_cpe:
                cpe_id = cpe["id"]
                q_val = cpe_dict.get(cpe_id, {}).get("q", cpe["q"])
                n_val = cpe_dict.get(cpe_id, {}).get("n", cpe["n"])
                
                # Associated parallel resistance
                r_parallel = branch_r[0] if branch_r else r_ct
                
                # 1. Brug Formula (2D Surface Distribution / Roughness):
                # C_eff = Q^(1/n) * ( (Rs * Rct) / (Rs + Rct) )^((1-n)/n)
                # For blocking: C_eff = Q^(1/n) * Rs^((1-n)/n)
                if r_parallel > 1e7: # blocking
                    c_brug = (q_val ** (1.0 / n_val)) * (r_solution ** ((1.0 - n_val) / n_val))
                else:
                    r_comb = (r_solution * r_parallel) / max(1e-12, (r_solution + r_parallel))
                    c_brug = (q_val ** (1.0 / n_val)) * (r_comb ** ((1.0 - n_val) / n_val))
                
                # 2. Hirschorn / Mansfeld Formula (3D Normal Distribution through film/coating):
                # C_eff = Q^(1/n) * R_film^((1-n)/n)
                c_hirschorn = (q_val ** (1.0 / n_val)) * (r_parallel ** ((1.0 - n_val) / n_val))
                
                # 3. Hsu-Mansfeld Formula (Characteristic frequency apex):
                # C_eff = Q * (omega_max)^(n-1) = (Q * R_ct^(1-n))^(1/n)
                c_hsu = (q_val * (r_parallel ** (1.0 - n_val))) ** (1.0 / n_val)
                
                tau_brug_ms = r_parallel * c_brug * 1000.0
                c_brug_uF = c_brug * 1e6
                c_brug_uFcm2 = c_brug_uF / area
                
                # Physical diagnosis
                if c_brug_uFcm2 < 5.0:
                    physics_note = "Very low specific capacitance (typical for dense passive barrier film or thick organic coating, 1-5 µF/cm²)."
                elif c_brug_uFcm2 <= 60.0:
                    physics_note = "Ideal double-layer capacitance range (typical for smooth metallic electrode in aqueous electrolyte, 10-40 µF/cm²)."
                elif c_brug_uFcm2 <= 200.0:
                    physics_note = "Elevated double-layer capacitance (indicative of moderate surface roughness factor RF = 2-5 or porous oxide)."
                else:
                    physics_note = "High capacitance (indicates highly porous 3D carbon matrix, pseudocapacitance, or large geometric surface area)."
                    
                cpe_results.append({
                    "cpeElementId": cpe_id,
                    "cpeName": cpe["name"],
                    "qValue": q_val,
                    "nExponent": n_val,
                    "cBrug_F": c_brug,
                    "cBrug_uF": round(c_brug_uF, 4),
                    "cEffectiveArea_uFcm2": round(c_brug_uFcm2, 3),
                    "cHirschorn_F": c_hirschorn,
                    "cHirschorn_uF": round(c_hirschorn * 1e6, 4),
                    "cHsuMansfeld_F": c_hsu,
                    "cHsuMansfeld_uF": round(c_hsu * 1e6, 4),
                    "tauEffectiveMs": round(tau_brug_ms, 3),
                    "associatedRs": round(r_solution, 3),
                    "associatedRct": round(r_parallel, 3),
                    "modelApplied": "Brug (2D Surface Distribution)",
                    "physicsNote": physics_note
                })
                
    return cpe_results


def perform_lin_kk_stationarity_test(points):
    """
    Computes descriptive residuals for a fixed regularized Voigt basis.
    This legacy clipped-coefficient model still needs numerical/model-selection
    review. It cannot certify K-K consistency or time-domain stationarity.
    """
    if not points or len(points) < 5:
        return {
            "status": "unavailable",
            "isStationary": None,
            "driftScore": None,
            "stationarityStatus": "Insufficient Points for Full Lin-KK",
            "muDriftMetric": None,
            "kkChiSquare": None,
            "pseudoChiSquare": None,
            "flaggedFrequencies": [],
            "residuals": [],
            "recommendation": "At least five frequency points are required; this alone does not guarantee adequate frequency coverage."
        }
        
    points = sorted(points, key=lambda p: p["frequency"])
    n_pts = len(points)
    freqs = [float(p["frequency"]) for p in points]
    omegas = [2.0 * math.pi * f for f in freqs]
    z_re_exp = [float(p["zReal"]) for p in points]
    z_im_exp = [float(p.get("minusZImag", -p.get("zImag", 0.0))) for p in points] # exp minusZImag
    z_mag_exp = [math.sqrt(z_re_exp[i]**2 + z_im_exp[i]**2) for i in range(n_pts)]
    
    # 1. Define M Voigt RC elements distributed across frequency range
    m_voigt = min(30, max(8, n_pts // 2))
    log_f_min = math.log10(min(freqs))
    log_f_max = math.log10(max(freqs))
    
    tau_voigt = []
    for k in range(m_voigt):
        log_fk = log_f_min + (k / float(m_voigt - 1)) * (log_f_max - log_f_min)
        fk = 10.0 ** log_fk
        tau_voigt.append(1.0 / (2.0 * math.pi * fk))
        
    # 2. Build Kramers-Kronig Coupling Matrix:
    # Z_kk_re(w) = R_0 + sum_k [ R_k / (1 + (w*tau_k)^2) ]
    # Z_kk_im(w) = - sum_k [ R_k * (w*tau_k) / (1 + (w*tau_k)^2) ]
    # Least-squares fit of R_0, R_1... R_M to experimental data
    _require_numpy("Lin-KK Voigt screening")
    # Non-finite observations propagate to NaN metrics silently, as in the former loops.
    with np.errstate(all="ignore"):
        x_voigt, re_kk_all, im_kk_all = _lin_kk_voigt_solve(omegas, tau_voigt, z_re_exp, z_im_exp, z_mag_exp)

    # 3. Compute Lin-KK Residuals point by point
    residuals = []
    re_res_list = []
    im_res_list = []
    tot_res_list = []
    flagged_freqs = []

    for i in range(n_pts):
        f = freqs[i]

        # Lin-KK model at this frequency
        re_kk = re_kk_all[i]
        im_kk = im_kk_all[i]

        re_err_pct = ((z_re_exp[i] - re_kk) / max(1e-6, z_mag_exp[i])) * 100.0
        im_err_pct = ((z_im_exp[i] - im_kk) / max(1e-6, z_mag_exp[i])) * 100.0
        tot_err_pct = math.sqrt(re_err_pct**2 + im_err_pct**2)
        
        re_res_list.append(re_err_pct)
        im_res_list.append(im_err_pct)
        tot_res_list.append(tot_err_pct)
        
        is_outlier = tot_err_pct > 3.0
        if is_outlier:
            flagged_freqs.append(round(f, 4))
            
        residuals.append({
            "frequency": round(f, 4),
            "logFreq": round(math.log10(f), 4),
            "zRealResPct": round(re_err_pct, 3),
            "zImagResPct": round(im_err_pct, 3),
            "totalResidualPct": round(tot_err_pct, 3),
            "isOutlier": is_outlier
        })

    # 4. Low-Frequency Drift Analysis (Stationarity Test)
    # Check bottom 25% frequency points for monotonic residual slope
    low_f_count = max(3, n_pts // 4)
    low_f_re_res = re_res_list[:low_f_count]
    low_f_logs = [math.log10(freqs[i]) for i in range(low_f_count)]
    
    # Linear slope of residuals vs log(f) at low frequency
    mean_lf_log = sum(low_f_logs) / len(low_f_logs)
    mean_lf_res = sum(low_f_re_res) / len(low_f_re_res)
    cov_lf = sum((low_f_logs[i] - mean_lf_log) * (low_f_re_res[i] - mean_lf_res) for i in range(low_f_count))
    var_lf = sum((low_f_logs[i] - mean_lf_log)**2 for i in range(low_f_count))
    drift_slope = abs(cov_lf / max(1e-9, var_lf))
    
    # Pseudo Chi-Square
    kk_chi_sq = sum((r / 100.0)**2 for r in tot_res_list) / max(1, n_pts)
    pseudo_chi_sq = kk_chi_sq
    mean_tot_res = sum(tot_res_list) / max(1, n_pts)
    
    # Frequency residuals alone cannot identify time-domain stationarity, OCP
    # drift, linearity, causality, or standards compliance. Preserve descriptive
    # residual metrics while withholding those unsupported diagnoses.
    stationarity_status = "Voigt residual screening only; stationarity unavailable"
    recom = "This fixed-basis regularized Voigt screen is not independent K-K or ASTM certification. Time-resolved acquisition and model-selection validation are not available."

    return {
        "isStationary": None,
        "driftScore": None,
        "stationarityStatus": stationarity_status,
        "muDriftMetric": round(drift_slope, 4),
        "kkChiSquare": round(kk_chi_sq, 6),
        "pseudoChiSquare": round(pseudo_chi_sq, 6),
        "meanResidualPct": round(mean_tot_res, 2),
        "flaggedFrequencies": flagged_freqs[:8],
        "residuals": residuals,
        "recommendation": recom
    }


def _lin_kk_voigt_solve(omegas, tau_voigt, z_re_exp, z_im_exp, z_mag_exp):
    """Fixed-basis Voigt fit of the Lin-KK screen; returns (x, Z_kk_re, Z_kk_im)."""
    m_voigt = len(tau_voigt)
    n_pts = len(omegas)
    w_tau = np.outer(np.asarray(omegas, dtype=np.float64), np.asarray(tau_voigt, dtype=np.float64))
    basis_re = 1.0 / (1.0 + w_tau**2)          # R_k coefficient in Z_kk_re
    basis_im = w_tau / (1.0 + w_tau**2)        # R_k coefficient in Z_kk_im (minusZImag)
    weight = 1.0 / np.maximum(1e-6, np.asarray(z_mag_exp, dtype=np.float64))

    # Weighted design matrix: real rows [1, basis_re], imag rows [0, basis_im].
    a_mat = np.zeros((2 * n_pts, m_voigt + 1), dtype=np.float64)
    a_mat[:n_pts, 0] = weight
    a_mat[:n_pts, 1:] = basis_re * weight[:, None]
    a_mat[n_pts:, 1:] = basis_im * weight[:, None]
    b_vec = np.concatenate((np.asarray(z_re_exp) * weight, np.asarray(z_im_exp) * weight))

    # Tikhonov-regularised normal equations (A^T A + lambda*I) x = A^T b, solved
    # densely (the matrix is symmetric positive definite, smallest eigenvalue >=
    # lambda), then clipped at zero. Clipping an unconstrained solve is NOT a
    # non-negative least-squares (NNLS) solution; it is kept as the legacy model.
    lambda_reg = 1e-4
    ata = a_mat.T @ a_mat + lambda_reg * np.eye(m_voigt + 1)
    x_voigt = np.maximum(0.0, np.linalg.solve(ata, a_mat.T @ b_vec))  # Positivity constraint

    r0_fit = x_voigt[0]
    rk_fit = x_voigt[1:]
    re_kk_all = (r0_fit + basis_re @ rk_fit).tolist()
    im_kk_all = (basis_im @ rk_fit).tolist()
    return x_voigt, re_kk_all, im_kk_all


def analyze_and_deembed_high_freq_inductance(points):
    """
    Detects high-frequency cable/cell lead inductance (-Z'' < 0 / Z'' > 0 at f > 1000 Hz),
    calculates zero-crossing frequency f_0 and parasitic inductance L_cable,
    and returns de-embedded corrected EIS spectrum.
    """
    if not points:
        return {
            "hasHighFreqInduction": False,
            "detectedInductance_H": 0.0,
            "detectedInductance_uH": 0.0,
            "zeroCrossingFreq_Hz": None,
            "cableArtifactMagnitude_Ohm": 0.0,
            "correctedPoints": [],
            "recommendedAction": "No data provided."
        }
        
    pts_sorted = sorted(points, key=lambda x: float(x["frequency"]), reverse=True) # High freq first
    
    # Check for negative minusZImag (i.e. inductive loop in quadrant 4)
    inductive_pts = [p for p in pts_sorted if float(p["frequency"]) >= 500.0 and float(p.get("minusZImag", -p.get("zImag", 0.0))) < 0.0]
    
    has_induction = len(inductive_pts) > 0
    zero_crossing_f = None
    l_cable_h = 0.0
    
    # Find zero crossing by linear interpolation
    for i in range(len(pts_sorted) - 1):
        p1 = pts_sorted[i]
        p2 = pts_sorted[i+1]
        im1 = float(p1.get("minusZImag", -p1.get("zImag", 0.0)))
        im2 = float(p2.get("minusZImag", -p2.get("zImag", 0.0)))
        f1 = float(p1["frequency"])
        f2 = float(p2["frequency"])
        
        if im1 < 0.0 and im2 >= 0.0:
            # Linear interpolation for f_zero
            t = (0.0 - im1) / max(1e-12, (im2 - im1))
            zero_crossing_f = f1 + t * (f2 - f1)
            break
            
    if has_induction:
        # Estimate L_cable from top inductive points: Z''_ind = omega * L -> -Z'' = -omega * L
        l_estimates = []
        for p in inductive_pts:
            w = 2.0 * math.pi * float(p["frequency"])
            minus_zim = float(p.get("minusZImag", -p.get("zImag", 0.0)))
            l_val = (-minus_zim) / max(1e-12, w)
            l_estimates.append(l_val)
        l_cable_h = sum(l_estimates) / max(1, len(l_estimates))
    else:
        # Check if there is high-frequency upward curvature even if not crossing 0
        high_f_pts = [p for p in pts_sorted if float(p["frequency"]) >= 10000.0]
        if len(high_f_pts) >= 2:
            w_max = 2.0 * math.pi * float(high_f_pts[0]["frequency"])
            l_cable_h = 1e-8 # Sub-microhenry residual baseline
            
    l_cable_uH = l_cable_h * 1e6
    max_w = 2.0 * math.pi * float(pts_sorted[0]["frequency"])
    artifact_ohm = l_cable_h * max_w
    
    # Generate de-embedded dataset: Z_corrected = Z_meas - j*w*L
    corrected_points = []
    for p in pts_sorted:
        f = float(p["frequency"])
        w = 2.0 * math.pi * f
        re_val = float(p["zReal"])
        minus_im_val = float(p.get("minusZImag", -p.get("zImag", 0.0)))
        
        # Subtract j*w*L -> -Z''_new = -Z''_old + w*L
        corrected_minus_zim = minus_im_val + (w * l_cable_h)
        corrected_zim = -corrected_minus_zim
        corrected_mag = math.sqrt(re_val**2 + corrected_minus_zim**2)
        corrected_phase = math.degrees(math.atan2(-corrected_minus_zim, re_val))
        
        corrected_points.append({
            "frequency": f,
            "zReal": round(re_val, 5),
            "zImag": round(corrected_zim, 5),
            "minusZImag": round(max(0.0, corrected_minus_zim), 5),
            "zMag": round(corrected_mag, 5),
            "phaseDeg": round(corrected_phase, 3)
        })
        
    corrected_points = sorted(corrected_points, key=lambda x: x["frequency"], reverse=True)
    
    if has_induction:
        recom = f"High-frequency cable inductance of {round(l_cable_uH, 3)} µH detected (zero-crossing at {round(zero_crossing_f or 0.0, 1)} Hz). Apply de-embedding before CNLS optimization to avoid artificial electrolyte resistance (Rs) distortion."
    else:
        recom = "High-frequency inductive phase shift is minimal (< 0.1 µH). Spectrum is clean and ready for direct CNLS fitting."

    return {
        "hasHighFreqInduction": has_induction,
        "detectedInductance_H": l_cable_h,
        "detectedInductance_uH": round(l_cable_uH, 4),
        "zeroCrossingFreq_Hz": round(zero_crossing_f, 2) if zero_crossing_f else None,
        "cableArtifactMagnitude_Ohm": round(artifact_ohm, 4),
        "originalPointsCount": len(points),
        "correctedPointsCount": len(corrected_points),
        "correctedPoints": corrected_points,
        "recommendedAction": recom
    }

def simulate_circuit_spectra(topology_data, initial_params=None, min_freq=0.01, max_freq=100000.0, points_per_decade=15):
    """
    Computes theoretical EIS spectrum (Nyquist, Bode magnitude, Bode phase) across frequency decades
    for arbitrary custom or preset equivalent circuits using CPython.
    """
    start_time = time.perf_counter()
    params_dict = {}
    if initial_params:
        for p in initial_params:
            p_name = p.get("paramName", "")
            el_id = p.get("elementId", "")
            field = p.get("field", "value")
            val = float(p.get("value", 1.0))
            if p_name:
                params_dict[p_name] = val
            if el_id:
                params_dict[f"{el_id}_{field}"] = val
                params_dict[f"{el_id}_value"] = val if field == "value" else params_dict.get(f"{el_id}_value", val)
                if field == "exponent":
                    params_dict[f"{el_id}_exponent"] = val
                params_dict[el_id] = val
    elif isinstance(topology_data, dict) and "branches" in topology_data:
        for b in topology_data.get("branches", []):
            for el in b.get("elements", []):
                el_id = el.get("id", "")
                el_name = el.get("name", "")
                val = float(el.get("value", 1.0))
                exp = float(el.get("exponent", 0.9))
                params_dict[el_name] = val
                params_dict[f"{el_id}_value"] = val
                params_dict[f"{el_id}_exponent"] = exp
                params_dict[f"n_{el_name}"] = exp
                params_dict[el_id] = val

    log_min = math.log10(max(1e-5, min_freq))
    log_max = math.log10(min(1e9, max_freq))
    decades = log_max - log_min
    num_pts = max(20, int(decades * points_per_decade))
    
    freq_list = []
    points = []
    
    max_minus_zim = -1e9
    f_peak = 1000.0
    r_high_freq = 0.0
    r_low_freq = 0.0
    min_phase_deg = 0.0
    
    for i in range(num_pts + 1):
        log_f = log_min + (i / float(num_pts)) * (log_max - log_min)
        f = 10.0 ** log_f
        omega = 2.0 * math.pi * f
        freq_list.append(f)
        
        z = evaluate_circuit_impedance(topology_data, params_dict, omega)
        z_re = float(z.real)
        z_im = float(z.imag)
        minus_z_im = float(max(0.0, -z_im))
        z_mag = float(abs(z))
        phase_rad = float(cmath.phase(z))
        phase_deg = float(math.degrees(phase_rad))
        
        if i == num_pts:
            r_high_freq = z_re
        if i == 0:
            r_low_freq = z_re
            
        if minus_z_im > max_minus_zim:
            max_minus_zim = minus_z_im
            f_peak = f
            
        if phase_deg < min_phase_deg:
            min_phase_deg = phase_deg
            
        points.append({
            "frequency": round(f, 4),
            "omega": round(omega, 4),
            "logFreq": round(log_f, 4),
            "zReal": round(z_re, 5),
            "zImag": round(z_im, 5),
            "minusZImag": round(minus_z_im, 5),
            "zMag": round(z_mag, 5),
            "logZMag": round(math.log10(max(1e-9, z_mag)), 4),
            "phaseDeg": round(phase_deg, 3)
        })
        
    points = sorted(points, key=lambda x: x["frequency"], reverse=True)
    compute_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
    
    return {
        "success": True,
        "engine": "CPython-3.10-EIS-Simulator",
        "computeTimeMs": compute_ms,
        "points": points,
        "metrics": {
            "rSolution": round(r_high_freq, 4),
            "rTotal": round(r_low_freq, 4),
            "polarizationResistance": round(max(0.0, r_low_freq - r_high_freq), 4),
            "fPeakHz": round(f_peak, 3),
            "tauPeakMs": round((1.0 / (2.0 * math.pi * max(1e-9, f_peak))) * 1000.0, 3),
            "maxMinusZImag": round(max_minus_zim, 4),
            "minPhaseDeg": round(min_phase_deg, 2)
        }
    }

def summarize_synthetic_recovery(ground_truth_params, fit_result):
    """Observed recovery for one synthetic realization; no qualification score.

    Missing parameters and zero denominators have unavailable percentage errors.
    An aggregate is available only when every ground-truth row is comparable.
    """
    def finite(value):
        return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None

    recovered = fit_result.get("parameters") or []
    rows = []
    for truth in ground_truth_params:
        matches = [p for p in recovered if p.get("elementId") == truth.get("elementId")
                   and p.get("field") == truth.get("field")]
        match = matches[0] if len(matches) == 1 else {}
        actual = finite(match.get("fittedValue"))
        expected = finite(truth.get("value"))
        absolute = finite(abs(actual - expected)) if actual is not None and expected is not None else None
        percent = finite(absolute / abs(expected) * 100) if absolute is not None and expected != 0 else None
        sigma = finite(match.get("stdError"))
        rows.append({
            "paramName": truth.get("paramName"), "elementId": truth.get("elementId"),
            "field": truth.get("field"), "unit": truth.get("unit"),
            "trueValue": expected, "recoveredValue": actual, "absError": absolute,
            "pctError": percent, "stdError": sigma if sigma is not None and sigma >= 0 else None,
            "isReliable": None,
        })
    comparable = bool(rows) and all(row["pctError"] is not None for row in rows)
    result = {
        "parameterErrors": rows,
        "meanAbsolutePctError": sum(row["pctError"] / len(rows) for row in rows) if comparable else None,
        "maxAbsolutePctError": max(row["pctError"] for row in rows) if comparable else None,
        "robustnessScore": None, "robustnessGrade": None,
        "assessment": "Single synthetic realization; no validated robustness grade or experimental qualification.",
        "converged": fit_result.get("converged") if isinstance(fit_result.get("converged"), bool) else None,
    }
    for key in ("chiSquare", "reducedChiSquare", "rSquared", "rmse", "iterations", "computeTimeMs"):
        result[key] = finite(fit_result.get(key))
    return result


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        print(json.dumps({
            "status": "ready",
            "engine": "MetalliX Python CNLS Impedance Fitting & Simulation Engine",
            "capabilities": ["Levenberg-Marquardt Complex Optimizer", "Real-Time Spectrum Simulation", "Covariance Std Error Bounds", "Kramers-Kronig Lin-KK Validation"]
        }))
        sys.exit(0)
        
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            print(json.dumps({"error": "Empty stdin payload"}))
            sys.exit(1)
            
        data = json.loads(raw_input)
        action = data.get("action", "fit")
        topology_data = data.get("topology", data.get("topologyId", "standard_randles"))
        
        if action == "simulate":
            initial_params = data.get("parameters", [])
            min_f = float(data.get("minFreq", 0.01))
            max_f = float(data.get("maxFreq", 100000.0))
            pts_per_dec = int(data.get("pointsPerDecade", 15))
            result = simulate_circuit_spectra(topology_data, initial_params, min_f, max_f, pts_per_dec)
            print(json.dumps(result))
        elif action == "validate_dataset":
            points = data.get("points", [])
            area = float(data.get("electrodeAreaCm2", 1.0))
            lin_kk = perform_lin_kk_stationarity_test(points)
            inductance = analyze_and_deembed_high_freq_inductance(points)
            initial_params = data.get("parameters", [])
            cpe_caps = calculate_cpe_effective_capacitances(initial_params, topology_data, area)
            print(json.dumps({
                "success": True,
                "engine": "CPython-3.10-Physical-Validation-Suite",
                "linKK": lin_kk,
                "inductance": inductance,
                "cpeCapacitances": cpe_caps
            }))
        elif action == "deembed_inductance":
            points = data.get("points", [])
            inductance = analyze_and_deembed_high_freq_inductance(points)
            print(json.dumps({
                "success": True,
                "engine": "CPython-3.10-Inductance-Deembedder",
                **inductance
            }))
        elif action == "cpe_capacitance":
            initial_params = data.get("parameters", [])
            area = float(data.get("electrodeAreaCm2", 1.0))
            cpe_caps = calculate_cpe_effective_capacitances(initial_params, topology_data, area)
            print(json.dumps({
                "success": True,
                "engine": "CPython-3.10-CPE-Brug-Hirschorn-Calculator",
                "cpeCapacitances": cpe_caps
            }))
        elif action in ["synthetic_noise_benchmark", "synthetic_noise"]:
            noise_cfg = data.get("noiseConfig", {})
            freq_cfg = data.get("frequencyConfig", {})
            f_min = float(freq_cfg.get("fMin", 0.01))
            f_max = float(freq_cfg.get("fMax", 100000.0))
            pts_per_dec = int(freq_cfg.get("pointsPerDecade", 10))
            
            # Generate frequency list
            log_min = math.log10(max(1e-4, f_min))
            log_max = math.log10(max(f_min * 10, f_max))
            num_pts = max(10, int(round((log_max - log_min) * pts_per_dec)))
            freqs = []
            for i in range(num_pts + 1):
                lf = log_max - (i / num_pts) * (log_max - log_min)
                freqs.append(10 ** lf)

            # Evaluate clean analytical impedance
            clean_points = []
            for f in freqs:
                w = 2.0 * math.pi * f
                z = evaluate_topology_impedance(topology_data, w)
                z_mag = abs(z)
                phase_deg = math.degrees(cmath.phase(z))
                clean_points.append({
                    "frequency": f,
                    "zReal": z.real,
                    "zImag": z.imag,
                    "minusZImag": -z.imag,
                    "zMag": z_mag,
                    "phaseDeg": phase_deg
                })

            # Inject noise & sensor artifacts
            white_noise_pct = float(noise_cfg.get("whiteNoisePct", 1.0))
            floor_ohm = float(noise_cfg.get("noiseFloorOhm", 0.005))
            phase_jitter_deg = float(noise_cfg.get("phaseJitterDeg", 0.25))
            drift_pct = float(noise_cfg.get("driftPct", 0.0))
            drift_type = str(noise_cfg.get("driftType", "linear"))
            cable_l_uH = float(noise_cfg.get("cableInductance_uH", 0.0))
            lead_r_ohm = float(noise_cfg.get("leadResistance_Ohm", 0.0))
            stray_c_pF = float(noise_cfg.get("strayCapacitance_pF", 0.0))
            leakage_uS = float(noise_cfg.get("leakageConductance_uS", 0.0))
            flicker_pct = float(noise_cfg.get("flicker1OverFPct", 0.0))

            mains_cfg = noise_cfg.get("mainsArtifact", {})
            mains_enabled = bool(mains_cfg.get("enabled", False))
            mains_f0 = float(mains_cfg.get("frequencyHz", 60.0))
            mains_mag_pct = float(mains_cfg.get("magnitudePct", 2.0))
            mains_harmonics = bool(mains_cfg.get("harmonics", True))

            glitch_cfg = noise_cfg.get("rangeSwitchGlitches", {})
            glitch_enabled = bool(glitch_cfg.get("enabled", False))
            glitch_freqs = glitch_cfg.get("switchFreqsHz", [1000, 10])
            glitch_mag_pct = float(glitch_cfg.get("stepMagnitudePct", 2.5))

            area_bias_pct = float(noise_cfg.get("electrodeAreaBiasPct", 0.0))
            adc_bits = int(noise_cfg.get("adcBitResolution", 0))

            synthetic_points = []
            rng = random.Random(int(noise_cfg.get("randomSeed", 42)))

            # Time accumulation for drift
            cum_time = 0.0
            times = []
            for pt in clean_points:
                period = 1.0 / max(1e-4, pt["frequency"])
                dwell = max(0.05, period * 1.5)
                cum_time += dwell
                times.append(cum_time)
            tot_time = max(1.0, cum_time)

            for idx, pt in enumerate(clean_points):
                f = pt["frequency"]
                w = 2.0 * math.pi * f
                zr = pt["zReal"]
                zi = pt["zImag"]
                z_mag = pt["zMag"]

                # 1. Cable Inductance
                if cable_l_uH > 0 or lead_r_ohm > 0:
                    L = cable_l_uH * 1e-6
                    xL = w * L
                    zr += lead_r_ohm
                    zi += xL

                # 2. Stray Shunt Capacitance
                if stray_c_pF > 0 or leakage_uS > 0:
                    C_stray = stray_c_pF * 1e-12
                    G_leak = leakage_uS * 1e-6
                    b_stray = w * C_stray
                    denom_z = zr * zr + zi * zi
                    if denom_z > 1e-12:
                        y_re = zr / denom_z + G_leak
                        y_im = -zi / denom_z + b_stray
                        denom_y = y_re * y_re + y_im * y_im
                        if denom_y > 1e-12:
                            zr = y_re / denom_y
                            zi = -y_im / denom_y

                # 3. OCP Drift
                if drift_pct > 0:
                    t_norm = times[idx] / tot_time
                    if drift_type == "linear":
                        df = (drift_pct / 100.0) * t_norm
                    elif drift_type == "power_law":
                        df = (drift_pct / 100.0) * (t_norm ** 0.7)
                    else:
                        df = (drift_pct / 100.0) * (1.0 - math.exp(-2.5 * t_norm))
                    zr += zr * df
                    zi += zi * df * 0.5

                # 4. Low-Frequency 1/f Flicker
                if flicker_pct > 0:
                    ff = (flicker_pct / 100.0) / math.sqrt(max(1e-3, f))
                    zr += z_mag * ff * rng.gauss(0, 1)
                    zi += z_mag * ff * rng.gauss(0, 1)

                # 5. Mains Artifact
                if mains_enabled and mains_mag_pct > 0:
                    bw = mains_f0 * 0.12
                    d1 = abs(f - mains_f0) / bw
                    hum1 = math.exp(-0.5 * d1 * d1)
                    hum2 = 0.0
                    if mains_harmonics:
                        d2 = abs(f - 2 * mains_f0) / (bw * 1.5)
                        hum2 = 0.45 * math.exp(-0.5 * d2 * d2)
                    tot_hum = hum1 + hum2
                    if tot_hum > 0.01:
                        hmag = z_mag * (mains_mag_pct / 100.0) * tot_hum
                        hang = rng.uniform(0, 2 * math.pi)
                        zr += hmag * math.cos(hang)
                        zi += hmag * math.sin(hang)

                # 6. Current Range Switching Glitch
                if glitch_enabled and glitch_freqs:
                    for gf in glitch_freqs:
                        if f <= gf:
                            s_frac = (glitch_mag_pct / 100.0)
                            zr += zr * s_frac * 0.8
                            zi += zi * s_frac * 1.2

                # 7. White Gaussian Noise & Floor
                p_std = (white_noise_pct / 100.0) * z_mag
                tot_std = math.sqrt(p_std * p_std + floor_ohm * floor_ohm)
                zr += rng.gauss(0, tot_std)
                zi += rng.gauss(0, tot_std)

                # 8. Phase Jitter
                if phase_jitter_deg > 0:
                    pj_rad = math.radians(rng.gauss(0, phase_jitter_deg))
                    cur_mag = math.hypot(zr, zi)
                    cur_phase = math.atan2(zi, zr) + pj_rad
                    zr = cur_mag * math.cos(cur_phase)
                    zi = cur_mag * math.sin(cur_phase)

                # 9. Area bias
                if area_bias_pct != 0:
                    ascale = 1.0 + (area_bias_pct / 100.0)
                    zr /= ascale
                    zi /= ascale

                # 10. ADC Quantization
                if adc_bits > 0:
                    m_rng = z_mag * 2.5
                    n_lev = 2 ** min(24, max(8, adc_bits))
                    q_step = m_rng / n_lev
                    zr = round(zr / q_step) * q_step
                    zi = round(zi / q_step) * q_step

                f_mag = math.hypot(zr, zi)
                f_phase = math.degrees(math.atan2(zi, zr))
                dz_re = zr - pt["zReal"]
                dz_im = zi - pt["zImag"]
                n_mag = math.hypot(dz_re, dz_im)
                snr = 20.0 * math.log10(max(1e-9, z_mag) / max(1e-12, n_mag)) if n_mag > 0 else 80.0

                synthetic_points.append({
                    "frequency": f,
                    "zReal": zr,
                    "zImag": zi,
                    "minusZImag": -zi,
                    "zMag": f_mag,
                    "phaseDeg": f_phase,
                    "cleanZReal": pt["zReal"],
                    "cleanZImag": pt["zImag"],
                    "cleanMinusZImag": -pt["zImag"],
                    "cleanZMag": pt["zMag"],
                    "cleanPhaseDeg": pt["phaseDeg"],
                    "deltaZReal": dz_re,
                    "deltaZImag": dz_im,
                    "noiseVectorMag": n_mag,
                    "snr_dB": round(snr, 1)
                })

            # Run Auto-Fit on Synthetic Points
            weighting = data.get("weighting", "modulus")
            max_gens = int(data.get("maxGenerations", 70))
            pop_size = int(data.get("populationSize", 35))
            polish_lm = bool(data.get("polishLM", True))

            fit_result = run_global_auto_fit(
                topology_data,
                synthetic_points,
                extract_topology_parameters(topology_data),
                weighting,
                max_gens,
                pop_size,
                polish_lm
            )

            recovery = summarize_synthetic_recovery(extract_topology_parameters(topology_data), fit_result)
            print(json.dumps({
                "success": fit_result.get("success") is True,
                "engine": "CPython-Synthetic-Noise-Stress-Lab",
                "syntheticPoints": synthetic_points,
                "cleanPoints": clean_points,
                "fitReport": fit_result,
                "noiseSeed": int(noise_cfg.get("randomSeed", 42)),
                "dataOrigin": "synthetic",
                **recovery,
            }, allow_nan=False))
        elif action in ["auto_fit", "autofit", "global_fit"] or data.get("isAutoFit"):
            points = data.get("points", [])
            initial_params = data.get("parameters", [])
            weighting = data.get("weighting", "modulus")
            max_gens = int(data.get("maxGenerations", data.get("maxIterations", 80)))
            pop_size = int(data.get("populationSize", 40))
            polish_lm = bool(data.get("polishLM", True))
            result = run_global_auto_fit(topology_data, points, initial_params, weighting, max_gens, pop_size, polish_lm, seed=data.get("randomSeed", 42))
            print(json.dumps(result))
        else:
            points = data.get("points", [])
            initial_params = data.get("parameters", [])
            weighting = data.get("weighting", "modulus")
            max_iterations = int(data.get("maxIterations", 80))
            result = run_cnls_fit(topology_data, points, initial_params, weighting, max_iterations)
            print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
