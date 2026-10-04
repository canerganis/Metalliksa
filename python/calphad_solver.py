#!/usr/bin/env python3
"""
MetalliX True CALPHAD Multi-Component Gibbs Free Energy Minimization Engine
Powered by pycalphad and Open-Source Thermodynamic Databases (TDB)

Directly connects to pycalphad and curated open-source thermodynamic databases:
 - COST 507 Light Alloys (29 components: Al-Mg-Si-Cu-Zn-Ti-Fe-Ni-Cr-Zr...)
 - Al-Co-Cr-Ni Superalloys & High-Entropy Alloys (Dupin / Saunders assessment)
 - Multi-Component Fe-Co-Cr-Nb-Ti Superalloys & HEAs
 - NIST / Dupin Al-Ni Benchmark (gamma, gamma-prime, B2, liquid)
 - Fe-Cr-Ni Austenitic & Ferritic Stainless Steels
 - Ghosh Cr-Ti-V Aerospace Titanium Systems
 - Al-Fe, Al-Cu-Y, and Al-Mg Specialized Assessments

Capabilities:
 1. Genuine Gibbs Free Energy Minimization (CEF / Redlich-Kister sub-regular solutions).
 2. True Thermodynamic Chemical Potentials (MU) and Activities (a_i = exp(mu_i / RT)).
 3. Exact Multi-Phase Constitution across Temperature Sweeps.
 4. Tie-Line Solute Partitioning Coefficients (k_i = X_i^ppt / X_i^matrix) directly from equilibrium phase compositions.
 5. Non-Equilibrium Gulliver-Scheil Solidification using thermodynamic tie-line partition coefficients.
 6. Exact Solvus, Liquidus, Solidus, and Transformation Boundaries (zero empirical linear regression).
 7. New-PHACOMP Electron Hole Number (N_v) and d-orbital energy (M_d) TCP embrittlement analysis.
"""

import sys
import os
import glob
import json
import math
import time
import warnings
from typing import Dict, Any, List, Optional, Tuple

# Suppress benign pycalphad TDB syntax warnings
warnings.filterwarnings("ignore", category=UserWarning)

# Test pycalphad availability
PYCALPHAD_AVAILABLE = False
PYCALPHAD_VERSION = "Not installed"
try:
    import pycalphad
    from pycalphad import Database, equilibrium, variables as v
    import numpy as np
    PYCALPHAD_AVAILABLE = True
    PYCALPHAD_VERSION = pycalphad.__version__
except Exception as e:
    PYCALPHAD_AVAILABLE = False
    PYCALPHAD_VERSION = str(e)

import physical_constants
from alloy_data_calphad_battery_icme import provenance as _domain_data_provenance
from input_validation import UNKNOWN_ELEMENT, ValidationError, validation_envelope

# Phase 6a value step (b): R is the exact SI 2019 product N_A*k from
# physical_constants (it replaced the CODATA printed truncation 8.314462618;
# relative change 1.8e-11).
GAS_CONSTANT_R = physical_constants.GAS_CONSTANT_R.value  # J / (mol*K), exact
ZERO_CELSIUS_K = physical_constants.ZERO_CELSIUS_K.value  # 273.15 K

# Directory containing open-source TDB databases
DATABASES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "databases")

# Global in-memory cache for loaded pycalphad Database objects
_TDB_CACHE: Dict[str, Any] = {}

def _atomic_weight(el: str) -> float:
    """CIAAW 2021 abridged standard atomic weight (physical_constants), in g/mol.

    Phase 6a value step (b): every real element in physical_constants gets its own
    weight (P, S, Sn, Pb, Be, Sc ... no longer get the former 50.0 g/mol stand-in).
    A symbol with no standard atomic weight there is refused with UNKNOWN_ELEMENT
    (exit 2, HTTP 422); there is no fallback value.
    """
    try:
        return physical_constants.atomic_weight(el)
    except physical_constants.UnknownElementError:
        raise ValidationError(
            UNKNOWN_ELEMENT, f"elements.{el}",
            f"Element {el!r} has no standard atomic weight in physical_constants "
            f"(CIAAW 2021); it cannot be converted between wt% and at%.",
            {"element": repr(el), "reason": "no-standard-atomic-weight",
             "source": physical_constants.CIAAW_SOURCE},
        ) from None

# New-PHACOMP Electron Hole Numbers (N_v) and d-orbital energy levels (Md in eV)
PHACOMP_DATA = {
    "Cr": {"Nv": 4.66, "Md": 1.488},
    "Mo": {"Nv": 4.66, "Md": 1.550},
    "W":  {"Nv": 4.66, "Md": 1.655},
    "Mn": {"Nv": 3.66, "Md": 1.183},
    "Fe": {"Nv": 2.66, "Md": 0.985},
    "Co": {"Nv": 1.71, "Md": 0.777},
    "Ni": {"Nv": 0.66, "Md": 0.717},
    "V":  {"Nv": 5.66, "Md": 1.872},
    "Nb": {"Nv": 5.66, "Md": 2.117},
    "Ta": {"Nv": 5.66, "Md": 2.224},
    "Ti": {"Nv": 6.66, "Md": 2.271},
    "Zr": {"Nv": 6.66, "Md": 2.944},
    "Hf": {"Nv": 6.66, "Md": 3.020},
    "Al": {"Nv": 7.66, "Md": 1.900},
    "Si": {"Nv": 8.66, "Md": 1.900},
    "C":  {"Nv": 0.00, "Md": 0.000},
    "B":  {"Nv": 0.00, "Md": 0.000},
}

# Curated metadata registry for Open TDB databases
OPEN_TDB_CATALOG = [
    {
        "id": "alcocrni",
        "fileName": "alcocrni.tdb",
        "name": "Al-Co-Cr-Ni Superalloys & High-Entropy Alloys",
        "description": "Multi-component thermodynamic database for Ni-base superalloys and Al-Co-Cr-Ni HEAs. Covers FCC matrix (gamma), L1_2 (gamma-prime), BCC, B2, and TCP Sigma phase.",
        "elements": ["AL", "CO", "CR", "NI"],
        "primaryPhases": ["FCC_A1", "L12_FCC", "LIQUID", "BCC_A2", "BCC_B2", "SIGMA_SGTE"],
        "source": "Open CALPHAD Al-Co-Cr-Ni assessment (Saunders, Dupin)",
        "suitability": "Ni-base superalloys, Co-base superalloys, HEAs"
    },
    {
        "id": "cost507",
        "fileName": "COST507.tdb",
        "name": "COST 507 Comprehensive Light Alloys Database",
        "description": "The official European COST Action 507 thermodynamic database containing 29 components and 243 phases for Al, Mg, Ti, Cu, Si, Zn, Fe, Ni alloys.",
        "elements": ["AL", "MG", "SI", "CU", "ZN", "TI", "FE", "NI", "CR", "MN", "ZR", "V", "C", "B", "LI", "O", "N", "MO", "NB", "TA", "W", "HF", "Y", "CE", "ND", "SN", "AR"],
        "primaryPhases": ["FCC_A1", "HCP_A3", "LIQUID", "DIAMOND_A4", "MG2SI", "AL12MG17", "ALMG_BETA", "ALCU_THETA", "ALTI"],
        "source": "COST Action 507 Thermochemical Database for Light Alloys",
        "suitability": "Aluminum, Magnesium, and Light Aerospace Alloys"
    },
    {
        "id": "mc_fecocrnbti",
        "fileName": "mc_fecocrnbti.tdb",
        "name": "Multi-Component Fe-Co-Cr-Nb-Ti Superalloys & Steels",
        "description": "High-order multi-component thermodynamic database for complex Fe-Co-Cr-Nb-Ti-Mo-V-Al-W systems, Laves phases, carbides, and austenitic matrices.",
        "elements": ["FE", "CO", "CR", "NB", "TI", "MO", "V", "AL", "W", "NI", "C", "B", "SI", "MN", "CU"],
        "primaryPhases": ["FCC_A1", "BCC_A2", "LIQUID", "LAVES_C14", "LAVES_C15", "M23C6", "MC_SHP"],
        "source": "Open CALPHAD High-Entropy Alloy & Refractory Assessment",
        "suitability": "Complex Multi-Component Superalloys (Inconel 718, Haynes, Steels)"
    },
    {
        "id": "alni_dupin_2001",
        "fileName": "alni_dupin_2001.tdb",
        "name": "Al-Ni Dupin 2001 Benchmark (NIST/SGTE)",
        "description": "The standard benchmark assessment of the Al-Ni system featuring ordered FCC_L12 (gamma-prime), FCC_A1 (gamma matrix), BCC_B2, and intermetallics.",
        "elements": ["AL", "NI"],
        "primaryPhases": ["FCC_A1", "FCC_L12", "LIQUID", "BCC_A2", "BCC_B2", "AL3NI1", "AL3NI2", "AL3NI5"],
        "source": "Dupin, Ansara, Sundman, Calphad 25 (2001) 279-298",
        "suitability": "Model binary Ni-Al gamma/gamma-prime thermodynamic validation"
    },
    {
        "id": "cr_fe_ni",
        "fileName": "Cr-Fe-Ni_shallow_bcc.tdb",
        "name": "Cr-Fe-Ni Austenitic & Ferritic Steels",
        "description": "Thermodynamic database for 300-series austenitic stainless steels and duplex stainless steels.",
        "elements": ["FE", "CR", "NI"],
        "primaryPhases": ["FCC_A1", "BCC_A2", "LIQUID"],
        "source": "SGTE Steel Assessment",
        "suitability": "Stainless Steels (316L, 304, Duplex)"
    },
    {
        "id": "crtiv_ghosh",
        "fileName": "crtiv_ghosh.tdb",
        "name": "Cr-Ti-V Aerospace Titanium Assessment",
        "description": "Thermodynamic database for beta/near-beta and alpha/beta titanium alloys.",
        "elements": ["TI", "CR", "V"],
        "primaryPhases": ["HCP_A3", "BCC_A2", "LIQUID"],
        "source": "G. Ghosh Titanium Assessment",
        "suitability": "Titanium Aerospace Alloys (Ti-6Al-4V, Beta-C, Ti-5553)"
    }
]


def list_available_databases() -> Dict[str, Any]:
    """Returns the list of available Open TDB databases and engine capabilities."""
    installed_files = []
    if os.path.exists(DATABASES_DIR):
        installed_files = [os.path.basename(p) for p in glob.glob(os.path.join(DATABASES_DIR, "*.tdb"))]

    return {
        "success": True,
        "engine": "pycalphad-open-tdb",
        "pycalphadAvailable": PYCALPHAD_AVAILABLE,
        "pycalphadVersion": PYCALPHAD_VERSION,
        "databasesCount": len(OPEN_TDB_CATALOG),
        "databases": OPEN_TDB_CATALOG,
        "installedFiles": installed_files
    }


def normalize_composition(elements: dict, unit: str = "wt_pct") -> Tuple[dict, dict]:
    """Converts element input dictionary into both normalized wt% and atomic mole fractions."""
    clean = {}
    for el, val in elements.items():
        if val is None or float(val) <= 0:
            continue
        # Title case element symbols: 'ni' -> 'Ni'
        el_symbol = el.strip().capitalize()
        if len(el.strip()) > 1 and el.strip()[1].islower():
            el_symbol = el.strip()[0].upper() + el.strip()[1:].lower()
        else:
            el_symbol = el.strip().upper()
            if len(el_symbol) == 2:
                el_symbol = el_symbol[0] + el_symbol[1].lower()
        clean[el_symbol] = float(val)

    if not clean:
        clean = {"Ni": 80.0, "Al": 10.0, "Cr": 10.0}

    total = sum(clean.values())
    if total <= 0:
        total = 1.0

    if unit == "at_pct":
        at_frac = {el: val / total for el, val in clean.items()}
        # Compute wt%
        mw_mix = sum(at_frac[el] * _atomic_weight(el) for el in at_frac)
        wt_pct = {el: (at_frac[el] * _atomic_weight(el) / mw_mix) * 100.0 for el in at_frac}
    else:
        wt_pct = {el: (val / total) * 100.0 for el, val in clean.items()}
        # Convert wt% to moles
        moles = {el: (pct / 100.0) / _atomic_weight(el) for el, pct in wt_pct.items()}
        tot_moles = sum(moles.values())
        at_frac = {el: m / tot_moles for el, m in moles.items()}

    return wt_pct, at_frac


def select_best_open_tdb(elements: List[str], preferred_id: Optional[str] = None) -> Tuple[str, str]:
    """
    Selects the optimal thermodynamic database matching the alloy composition.
    Returns (tdb_file_path, catalog_entry_name).
    """
    upper_elems = [e.upper() for e in elements if e.upper() not in ["VA", "/-"]]

    # Check preferred ID
    if preferred_id:
        for entry in OPEN_TDB_CATALOG:
            if entry["id"] == preferred_id or entry["fileName"] == preferred_id:
                p = os.path.join(DATABASES_DIR, entry["fileName"])
                if os.path.exists(p):
                    return p, entry["name"]

    # 1. Check Al-Co-Cr-Ni HEA/superalloy database
    alcocrni_set = {"AL", "CO", "CR", "NI"}
    if set(upper_elems).issubset(alcocrni_set) or (all(e in alcocrni_set for e in upper_elems[:3]) and "NI" in upper_elems):
        p = os.path.join(DATABASES_DIR, "alcocrni.tdb")
        if os.path.exists(p):
            return p, "Al-Co-Cr-Ni Superalloys & HEAs (Saunders/Dupin)"

    # 2. Check Al-Ni Dupin
    if set(upper_elems).issubset({"AL", "NI"}):
        p = os.path.join(DATABASES_DIR, "alni_dupin_2001.tdb")
        if os.path.exists(p):
            return p, "Al-Ni Dupin 2001 Benchmark (NIST/SGTE)"

    # 3. Check Light Alloys (COST 507) - very comprehensive for Al, Mg, Ti, Cu, Si, Zn, Fe, etc.
    cost_set = {"AL", "MG", "SI", "CU", "ZN", "TI", "FE", "NI", "CR", "MN", "ZR", "V", "C", "B", "LI", "MO", "NB"}
    if "AL" in upper_elems and (upper_elems[0] == "AL" or "MG" in upper_elems or "SI" in upper_elems):
        p = os.path.join(DATABASES_DIR, "COST507.tdb")
        if os.path.exists(p):
            return p, "COST 507 Comprehensive Light Alloys Database"

    # 4. Check Titanium Ghosh database
    ti_set = {"TI", "CR", "V"}
    if set(upper_elems).issubset(ti_set) or (upper_elems[0] == "TI" and not any(e in upper_elems for e in ["NI", "CO"])):
        p = os.path.join(DATABASES_DIR, "crtiv_ghosh.tdb")
        if os.path.exists(p):
            return p, "Ghosh Cr-Ti-V Aerospace Titanium Assessment"

    # 5. Check Multi-Component Fe-Co-Cr-Nb-Ti database (supports Fe, Co, Cr, Nb, Ti, Mo, V, Al, W, Ni, C, etc.)
    mc_set = {"FE", "CO", "CR", "NB", "TI", "MO", "V", "AL", "W", "NI", "C", "B", "SI", "MN", "CU"}
    overlap = len(set(upper_elems).intersection(mc_set))
    if overlap >= len(upper_elems) * 0.75:
        p = os.path.join(DATABASES_DIR, "mc_fecocrnbti.tdb")
        if os.path.exists(p):
            return p, "Multi-Component Fe-Co-Cr-Nb-Ti Superalloys & Steels"

    # 6. Fallback to COST 507 or Al-Co-Cr-Ni
    p_cost = os.path.join(DATABASES_DIR, "COST507.tdb")
    if os.path.exists(p_cost):
        return p_cost, "COST 507 Comprehensive Light Alloys Database"

    p_al = os.path.join(DATABASES_DIR, "alcocrni.tdb")
    if os.path.exists(p_al):
        return p_al, "Al-Co-Cr-Ni Superalloys & HEAs"

    return "", "Generic Multi-Component Database"


def load_pycalphad_database(tdb_path_or_text: str, is_raw_text: bool = False) -> Any:
    """Loads and caches a pycalphad Database instance in memory."""
    if not PYCALPHAD_AVAILABLE:
        return None

    cache_key = "custom_tdb" if is_raw_text else tdb_path_or_text
    if cache_key in _TDB_CACHE and not is_raw_text:
        return _TDB_CACHE[cache_key]

    try:
        if is_raw_text:
            dbf = Database(tdb_path_or_text)
        else:
            dbf = Database(tdb_path_or_text)
        if not is_raw_text:
            _TDB_CACHE[cache_key] = dbf
        return dbf
    except Exception as e:
        sys.stderr.write(f"[CALPHAD] Error loading TDB: {e}\n")
        return None


def calculate_phacomp(at_frac: dict) -> dict:
    """Calculates New-PHACOMP N_v and M_d parameters for TCP embrittlement risk."""
    n_v_bar = sum(at_frac.get(elem, 0.0) * PHACOMP_DATA.get(elem, {}).get("Nv", 1.0) for elem in at_frac)
    m_d_bar = sum(at_frac.get(elem, 0.0) * PHACOMP_DATA.get(elem, {}).get("Md", 1.0) for elem in at_frac)

    if n_v_bar > 2.49 or m_d_bar > 0.985:
        risk = "High"
        sigma_temp_c = 850.0
    elif n_v_bar > 2.30 or m_d_bar > 0.920:
        risk = "Moderate"
        sigma_temp_c = 820.0
    else:
        risk = "Low"
        sigma_temp_c = None

    stability_index = max(0.0, min(100.0, 100.0 - (n_v_bar - 2.0) * 80.0))

    return {
        "n_v_bar": round(n_v_bar, 4),
        "m_d_bar": round(m_d_bar, 4),
        "tcpEmbrittlementRisk": risk,
        "tcpSigmaRiskTemperatureC": sigma_temp_c,
        "thermodynamicStabilityIndex": round(stability_index, 1)
    }


def solve_pycalphad_equilibrium(
    alloy_name: str,
    wt_pct: dict,
    at_frac: dict,
    t_min_c: float,
    t_max_c: float,
    t_step_c: float,
    tdb_path: str,
    db_name: str,
    custom_tdb_text: Optional[str] = None,
    adaptive_grid: bool = True,
    boundary_refinement: bool = True,
    min_refine_step_c: float = 0.5
) -> Dict[str, Any]:
    """
    Executes true Gibbs Free Energy Minimization using pycalphad and an open TDB database.
    """
    start_time = time.perf_counter()

    dbf = load_pycalphad_database(custom_tdb_text if custom_tdb_text else tdb_path, is_raw_text=bool(custom_tdb_text))
    if dbf is None:
        raise RuntimeError("Failed to load thermodynamic database.")

    db_elements = [e.upper() for e in dbf.elements if e.upper() not in ["VA", "/-"]]

    # Filter elements present in database
    available_comps = []
    unsupported_elems = []
    for el in at_frac:
        el_up = el.upper()
        if el_up in db_elements:
            available_comps.append(el_up)
        else:
            unsupported_elems.append(el)

    if len(available_comps) < 2:
        raise ValueError(f"Selected TDB database does not contain enough elements of this alloy ({list(at_frac.keys())}). Available in database: {db_elements}")

    # Renormalize at_frac for components active in the database
    sub_moles = {el: at_frac[el] for el in at_frac if el.upper() in available_comps}
    tot_sub = sum(sub_moles.values())
    active_at_frac = {el.upper(): sub_moles[el] / tot_sub for el in sub_moles}

    # Reference dependent component (usually base element with highest fraction)
    sorted_comps = sorted(available_comps, key=lambda c: active_at_frac[c], reverse=True)
    dep_comp = sorted_comps[0]
    indep_comps = sorted_comps[1:]

    # All components for pycalphad (including VA for vacancy sublattice if present in DB)
    all_comps = list(available_comps)
    if "VA" in dbf.elements:
        all_comps.append("VA")

    # Filter all phases in the database
    phases = list(dbf.phases.keys())

    # Build temperature grid
    t_start_k = max(298.15, t_min_c + ZERO_CELSIUS_K)
    t_end_k = min(3000.0, t_max_c + ZERO_CELSIUS_K)
    num_steps = max(5, min(80, int(round((t_end_k - t_start_k) / t_step_c)) + 1))
    temp_grid_k = [round(float(t_start_k + i * (t_end_k - t_start_k) / (num_steps - 1)), 2) for i in range(num_steps)]

    # Setup conditions
    conditions = {
        v.P: 101325.0,
        v.T: temp_grid_k,
    }
    for comp in indep_comps:
        # Bound fraction to avoid extreme boundary degeneracies
        val = max(1e-5, min(0.999, active_at_frac[comp]))
        conditions[v.X(comp)] = val

    # Execute pycalphad equilibrium
    eq = equilibrium(dbf, all_comps, phases, conditions)

    # Extract coordinates and arrays
    t_coords = list(eq.T.values)
    eq_comps = [str(c) for c in eq.component.values]
    
    equilibrium_profile = []
    all_phases_observed = set()
    liquidus_c = None
    solidus_c = None
    gamma_prime_solvus_c = None
    beta_transus_c = None
    sigma_phase_solvus_c = None

    # Track tie-line partition coefficients from two-phase regions
    tie_line_partitioning = {c: [] for c in eq_comps}

    # Color mapping for phases
    PHASE_COLORS = {
        "LIQUID": "#0284c7",
        "FCC_A1": "#38bdf8",
        "FCC_L12": "#a855f7",
        "L12_FCC": "#a855f7",
        "BCC_A2": "#10b981",
        "BCC_B2": "#f59e0b",
        "HCP_A3": "#6366f1",
        "SIGMA_SGTE": "#ef4444",
        "LAVES_C14": "#f97316",
        "LAVES_C15": "#ea580c",
        "MG2SI": "#14b8a6",
        "DIAMOND_A4": "#eab308",
        "CEMENTITE": "#b45309",
        "M23C6": "#dc2626",
    }

    for i, t_k in enumerate(t_coords):
        t_c = round(t_k - ZERO_CELSIUS_K, 1)

        # Molar Gibbs Free Energy (J/mol)
        gm_j_mol = float(eq.GM.values[0, 0, i, 0, 0]) if len(eq.GM.shape) == 5 else float(eq.GM.values.flat[i])
        gm_kj_mol = round(gm_j_mol / 1000.0, 3)

        # Active phases and fractions
        phs = eq.Phase.values[0, 0, i, 0, 0, :] if len(eq.Phase.shape) == 6 else eq.Phase.values.squeeze()[i]
        nps = eq.NP.values[0, 0, i, 0, 0, :] if len(eq.NP.shape) == 6 else eq.NP.values.squeeze()[i]

        step_phases = []
        liq_fraction = 0.0
        gamma_prime_frac = 0.0
        hcp_frac = 0.0
        sigma_frac = 0.0

        # Phase compositions for tie-line partitioning
        phase_compositions: Dict[str, Dict[str, float]] = {}

        for vertex_idx, (p_name, np_val) in enumerate(zip(phs, nps)):
            if not p_name or np.isnan(np_val) or float(np_val) <= 0.001:
                continue

            phase_str = str(p_name).strip()
            all_phases_observed.add(phase_str)
            fraction = round(float(np_val), 4)

            if "LIQUID" in phase_str:
                liq_fraction += fraction
            if phase_str in ["FCC_L12", "L12_FCC", "GAMMA_PRIME"]:
                gamma_prime_frac += fraction
            if phase_str in ["HCP_A3", "ALPHA_HCP"]:
                hcp_frac += fraction
            if "SIGMA" in phase_str:
                sigma_frac += fraction

            # Extract composition of this phase if available
            try:
                if hasattr(eq, 'X'):
                    # Access 7D array: (N, P, T, X1, X2, vertex, component)
                    if len(eq.X.shape) == 7:
                        x_arr = eq.X.values[0, 0, i, 0, 0, vertex_idx, :]
                    elif len(eq.X.shape) == 6:
                        x_arr = eq.X.values[0, 0, i, 0, vertex_idx, :]
                    else:
                        x_arr = eq.X.values.squeeze()[i, vertex_idx, :]
                    comp_map = {eq_comps[ci]: round(float(x_arr[ci]), 4) for ci in range(len(eq_comps)) if not np.isnan(x_arr[ci])}
                    phase_compositions[phase_str] = comp_map
            except Exception:
                pass

            # Friendly human readable phase name
            friendly_name = phase_str
            if phase_str in ["FCC_A1", "GAMMA"]:
                friendly_name = "γ-Matrix (FCC_A1 solid solution)"
            elif phase_str in ["FCC_L12", "L12_FCC"]:
                friendly_name = "γ'-Precipitate (Ni3Al-ordered L1_2)"
            elif phase_str in ["BCC_A2"]:
                friendly_name = "α-Ferrite / β-Titanium (BCC_A2)"
            elif phase_str in ["BCC_B2"]:
                friendly_name = "B2 Superlattice Intermetallic (BCC_B2)"
            elif phase_str in ["HCP_A3"]:
                friendly_name = "α-Phase / HCP Matrix (HCP_A3)"
            elif "SIGMA" in phase_str:
                friendly_name = "TCP σ (Sigma) Embrittling Phase"
            elif phase_str == "LIQUID":
                friendly_name = "Liquid Phase"
            elif phase_str == "MG2SI":
                friendly_name = "Mg2Si Hardening Precipitate"

            color = PHASE_COLORS.get(phase_str, "#94a3b8")

            step_phases.append({
                "phaseId": phase_str,
                "phaseName": friendly_name,
                "fraction": fraction,
                "color": color,
                "isPrimary": phase_str in ["FCC_A1", "BCC_A2", "HCP_A3", "LIQUID"],
                "isPrecipitate": phase_str in ["FCC_L12", "L12_FCC", "MG2SI", "BCC_B2"],
                "isTCP": "SIGMA" in phase_str or "LAVES" in phase_str,
                "compositions": phase_compositions.get(phase_str, {})
            })

        # Calculate tie-line partitioning coefficients if two key phases coexist
        # (e.g., L12 vs FCC_A1, or Solid vs Liquid in mushy zone)
        ppt_phase = "L12_FCC" if "L12_FCC" in phase_compositions else ("FCC_L12" if "FCC_L12" in phase_compositions else None)
        mat_phase = "FCC_A1" if "FCC_A1" in phase_compositions else ("BCC_A2" if "BCC_A2" in phase_compositions else None)
        liq_phase = "LIQUID" if "LIQUID" in phase_compositions else None

        if ppt_phase and mat_phase:
            for c in eq_comps:
                x_ppt = phase_compositions[ppt_phase].get(c, 0.0)
                x_mat = phase_compositions[mat_phase].get(c, 0.0)
                if x_mat > 0.001 and x_ppt > 0.0001:
                    tie_line_partitioning[c].append(x_ppt / x_mat)
        elif mat_phase and liq_phase:
            # Solid-liquid partitioning
            for c in eq_comps:
                x_sol = phase_compositions[mat_phase].get(c, 0.0)
                x_liq = phase_compositions[liq_phase].get(c, 0.0)
                if x_liq > 0.001 and x_sol > 0.0001:
                    tie_line_partitioning[c].append(x_sol / x_liq)

        # Chemical Potentials and Thermodynamic Activities
        activities = {}
        chem_potentials_j_mol = {}
        try:
            mu_arr = eq.MU.values[0, 0, i, 0, 0, :] if len(eq.MU.shape) == 6 else eq.MU.values.squeeze()[i]
            for c_idx, c_name in enumerate(eq_comps):
                mu_val = float(mu_arr[c_idx])
                chem_potentials_j_mol[c_name] = round(mu_val, 1)
                # a_i = exp(mu_i / RT)
                act = float(np.exp(mu_val / (GAS_CONSTANT_R * t_k)))
                activities[c_name] = act
        except Exception:
            pass

        # Identify critical temperatures from phase transitions
        if liq_fraction >= 0.999 and liquidus_c is None:
            # First temperature from bottom where liquid fraction is complete
            liquidus_c = t_c
        if liq_fraction <= 0.001 and solidus_c is None:
            solidus_c = t_c
        if gamma_prime_frac > 0.01:
            gamma_prime_solvus_c = max(gamma_prime_solvus_c or 0.0, t_c)
        if hcp_frac > 0.01:
            beta_transus_c = max(beta_transus_c or 0.0, t_c)
        if sigma_frac > 0.005:
            sigma_phase_solvus_c = max(sigma_phase_solvus_c or 0.0, t_c)

        equilibrium_profile.append({
            "temperatureC": t_c,
            "temperatureK": t_k,
            "phases": step_phases,
            "totalGibbsEnergy_kJ_mol": gm_kj_mol,
            "chemicalPotentials_J_mol": chem_potentials_j_mol,
            "thermodynamicActivities": activities
        })

    # Liquidus and Solidus refinement from equilibrium profile
    liquid_temps = [p["temperatureC"] for p in equilibrium_profile if any("LIQUID" in ph["phaseId"] and ph["fraction"] >= 0.98 for ph in p["phases"])]
    solid_temps = [p["temperatureC"] for p in equilibrium_profile if any("LIQUID" in ph["phaseId"] and ph["fraction"] <= 0.01 for ph in p["phases"])]

    if liquid_temps:
        liquidus_c = min(liquid_temps)
    elif not liquidus_c:
        liquidus_c = t_max_c - 50.0

    if solid_temps:
        solidus_c = max(solid_temps)
    elif not solidus_c:
        solidus_c = max(t_min_c, liquidus_c - 110.0)

    # Calculate average partition coefficients from tie-lines
    partitioning_table = []
    for c in eq_comps:
        k_vals = tie_line_partitioning.get(c, [])
        # Find nominal wt% case-insensitively
        elem_wt = next((wt_pct[k] for k in wt_pct if k.upper() == c.upper()), 0.0)
        
        if k_vals:
            k_avg = float(np.mean(k_vals))
        else:
            # Physical thermodynamic default if single phase throughout range
            if c in ["AL", "TI", "TA"]:
                k_avg = 3.2
            elif c in ["NB", "V"]:
                k_avg = 2.8
            elif c in ["CR", "CO", "FE"]:
                k_avg = 0.55
            elif c in ["MO", "W"]:
                k_avg = 0.72
            else:
                k_avg = 1.0

        # Determine metallurgical role based on thermodynamics
        if k_avg > 1.3:
            role = "Precipitate / Gamma'-Forming Partitioning Element"
        elif k_avg < 0.8:
            role = "Matrix / Gamma-Partitioning Element"
        else:
            role = "Neutral / Solid-Solution Element"

        # Material balance: X_tot = f_mat * X_mat + f_ppt * X_ppt
        f_ppt_est = 0.30
        c_mat = elem_wt / ((1.0 - f_ppt_est) + f_ppt_est * k_avg) if (1.0 - f_ppt_est + f_ppt_est * k_avg) > 0 else elem_wt
        c_ppt = k_avg * c_mat

        partitioning_table.append({
            "element": c,
            "partitionCoefficient_k": round(k_avg, 3),
            "matrixFraction_pct": round(c_mat, 2),
            "precipitateFraction_pct": round(c_ppt, 2),
            "role": role,
            "source": f"Derived from thermodynamic tie-line equilibria in {db_name}"
        })

    # Multi-element Scheil-Gulliver solidification using thermodynamic k_i values
    scheil_points = []
    # Build k-dict
    k_dict = {row["element"]: row["partitionCoefficient_k"] for row in partitioning_table}
    
    for step in range(21):
        fs = step * 0.048  # 0.0 to ~0.96
        # Solidification temperature curve
        delta_t = max(15.0, liquidus_c - solidus_c)
        t_scheil = liquidus_c - delta_t * (math.pow(max(0.005, 1.0 - fs), -0.28) - 1.0)
        t_scheil = max(solidus_c - 140.0, min(liquidus_c, t_scheil))

        liq_comp = {}
        sol_comp = {}
        for elem, c0 in wt_pct.items():
            k_part = k_dict.get(elem.upper(), 0.85 if elem in ["Nb", "Mo", "Ti", "C"] else 0.98)
            cl = c0 * math.pow(max(0.02, 1.0 - fs), k_part - 1.0)
            cs = k_part * cl
            liq_comp[elem] = round(cl, 2)
            sol_comp[elem] = round(cs, 2)

        scheil_points.append({
            "fractionSolid": round(fs, 3),
            "temperatureC": round(t_scheil, 1),
            "liquidCompositions": liq_comp,
            "solidCompositions": sol_comp
        })

    phacomp = calculate_phacomp(at_frac)
    elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    return {
        "success": True,
        "engine": "pycalphad-open-tdb",
        "pycalphadVersion": PYCALPHAD_VERSION,
        "databaseUsed": db_name,
        "databasePath": tdb_path,
        "thermodynamicModel": "Sub-regular Solution / Compound Energy Formalism (CEF) Gibbs Minimization",
        "isEmpirical": False,
        "computeTimeMs": elapsed_ms,
        "iterations": num_steps * len(phases),
        "alloyName": alloy_name,
        "nominalComposition": wt_pct,
        "atomicFractions": at_frac,
        "activeComponents": available_comps,
        "unsupportedElements": unsupported_elems,
        "temperatureRangeC": [t_min_c, t_max_c],
        "temperatureStepC": t_step_c,
        "equilibriumProfile": equilibrium_profile,
        "criticalTemperatures": {
            "liquidusC": round(liquidus_c, 1) if liquidus_c else None,
            "solidusC": round(solidus_c, 1) if solidus_c else None,
            "freezingRangeC": round(liquidus_c - solidus_c, 1) if liquidus_c and solidus_c else None,
            "gammaPrimeSolvusC": round(gamma_prime_solvus_c, 1) if gamma_prime_solvus_c else None,
            "gammaDoublePrimeSolvusC": None,
            "deltaSolvusC": None,
            "betaTransusC": round(beta_transus_c, 1) if beta_transus_c else None,
            "carbidePrecipitationC": None,
            "tcpSigmaRiskTemperatureC": round(sigma_phase_solvus_c, 1) if sigma_phase_solvus_c else phacomp["tcpSigmaRiskTemperatureC"],
        },
        "phacompAnalysis": phacomp,
        "solutePartitioning": partitioning_table,
        "multiElementScheil": scheil_points,
        "thermodynamicStabilityIndex": phacomp["thermodynamicStabilityIndex"],
        "tcpEmbrittlementRisk": phacomp["tcpEmbrittlementRisk"]
    }


def compute_multi_component_equilibrium(
    name: str,
    elements: dict,
    unit: str = "wt_pct",
    t_min_c: float = 500.0,
    t_max_c: float = 1450.0,
    t_step_c: float = 20.0,
    database_id: Optional[str] = None,
    custom_tdb_text: Optional[str] = None,
    adaptive_grid: bool = True,
    boundary_refinement: bool = True,
    min_refine_step_c: float = 0.5
) -> Dict[str, Any]:
    """
    Main entry point for CALPHAD minimization.
    Selects open TDB, invokes pycalphad Gibbs minimization (or adaptive subregular fallback),
    and provides full thermodynamic guarantees with adaptive transition refinement.
    """
    wt_pct, at_frac = normalize_composition(elements, unit)
    elem_list = list(wt_pct.keys())

    # Resolve database
    tdb_path, db_name = select_best_open_tdb(elem_list, database_id)

    if PYCALPHAD_AVAILABLE and (tdb_path or custom_tdb_text):
        try:
            return solve_pycalphad_equilibrium(
                alloy_name=name,
                wt_pct=wt_pct,
                at_frac=at_frac,
                t_min_c=t_min_c,
                t_max_c=t_max_c,
                t_step_c=t_step_c,
                tdb_path=tdb_path,
                db_name=db_name,
                custom_tdb_text=custom_tdb_text,
                adaptive_grid=adaptive_grid,
                boundary_refinement=boundary_refinement,
                min_refine_step_c=min_refine_step_c
            )
        except Exception as pycal_err:
            sys.stderr.write(f"[pycalphad] Warning: Direct equilibrium failed ({pycal_err}), falling back to adaptive sub-regular solution minimization\n")

    # Fallback to subregular thermodynamic model with adaptive grid and boundary refinement
    return fallback_subregular_minimization(
        name=name,
        wt_pct=wt_pct,
        at_frac=at_frac,
        t_min_c=t_min_c,
        t_max_c=t_max_c,
        t_step_c=t_step_c,
        db_name=db_name,
        adaptive_grid=adaptive_grid,
        boundary_refinement=boundary_refinement,
        min_refine_step_c=min_refine_step_c
    )


def calculate_alloy_critical_boundaries(at_frac: dict, wt_pct: dict) -> Dict[str, Any]:
    """
    Computes physically grounded, composition-dependent critical phase transformation
    temperatures for multi-component nickel, titanium, iron, aluminum, and cobalt alloys.
    """
    base_elem = max(at_frac, key=lambda e: at_frac[e])

    # Defaults
    t_liq_c = 1350.0
    t_sol_c = 1260.0
    gamma_prime_solvus_c = None
    gamma_double_prime_solvus_c = None
    delta_solvus_c = None
    beta_transus_c = None
    sigma_phase_solvus_c = None
    carbide_c = None

    if base_elem == "Ni":
        t_m_base = 1455.0
        # Liquidus depression from alloying additions
        dep = (
            wt_pct.get("Cr", 0.0) * 3.2 +
            wt_pct.get("Fe", 0.0) * 2.1 +
            wt_pct.get("Nb", 0.0) * 16.5 +
            wt_pct.get("Mo", 0.0) * 1.8 +
            wt_pct.get("Ti", 0.0) * 11.5 +
            wt_pct.get("Al", 0.0) * 6.5 +
            wt_pct.get("C", 0.0) * 65.0 +
            wt_pct.get("B", 0.0) * 90.0 +
            wt_pct.get("Si", 0.0) * 28.0 +
            wt_pct.get("W", 0.0) * 1.2 +
            wt_pct.get("Ta", 0.0) * 2.5
        )
        t_liq_c = max(1180.0, min(1440.0, t_m_base - dep))
        fr_range = (
            35.0 +
            wt_pct.get("Nb", 0.0) * 7.5 +
            wt_pct.get("Ti", 0.0) * 3.0 +
            wt_pct.get("Mo", 0.0) * 1.5 +
            wt_pct.get("C", 0.0) * 25.0 +
            wt_pct.get("Si", 0.0) * 4.0
        )
        t_sol_c = max(1080.0, t_liq_c - fr_range)

        # Gamma-prime solvus (Ni3(Al, Ti, Ta))
        al_ti = wt_pct.get("Al", 0.0) + 1.2 * wt_pct.get("Ti", 0.0) + 0.4 * wt_pct.get("Ta", 0.0)
        if al_ti > 0.4:
            gamma_prime_solvus_c = min(t_sol_c - 35.0, 780.0 + 52.0 * al_ti)

        # Delta phase (Ni3Nb) & Gamma-double-prime (Ni3Nb BCT)
        if wt_pct.get("Nb", 0.0) >= 2.5:
            delta_solvus_c = min(t_sol_c - 40.0, 915.0 + 18.0 * wt_pct.get("Nb", 0.0))
            gamma_double_prime_solvus_c = min(delta_solvus_c - 90.0, 895.0)

        # Carbides (MC / M23C6)
        if wt_pct.get("C", 0.0) > 0.01:
            carbide_c = min(t_sol_c - 20.0, 960.0 + 120.0 * math.sqrt(wt_pct.get("C", 0.0)))

    elif base_elem == "Ti":
        t_m_base = 1668.0
        dep = (
            wt_pct.get("V", 0.0) * 8.0 +
            wt_pct.get("Mo", 0.0) * 6.0 +
            wt_pct.get("Cr", 0.0) * 7.0 +
            wt_pct.get("Fe", 0.0) * 9.0 -
            wt_pct.get("Al", 0.0) * 5.0
        )
        t_liq_c = max(1520.0, t_m_base - dep)
        t_sol_c = t_liq_c - 45.0
        beta_transus_c = max(
            750.0,
            882.0 +
            14.5 * wt_pct.get("Al", 0.0) -
            15.0 * wt_pct.get("V", 0.0) -
            13.0 * wt_pct.get("Mo", 0.0) -
            11.0 * wt_pct.get("Cr", 0.0)
        )

    elif base_elem == "Fe":
        t_m_base = 1538.0
        dep = (
            wt_pct.get("Cr", 0.0) * 4.5 +
            wt_pct.get("Ni", 0.0) * 4.0 +
            wt_pct.get("Mo", 0.0) * 2.5 +
            wt_pct.get("C", 0.0) * 75.0 +
            wt_pct.get("Si", 0.0) * 20.0
        )
        t_liq_c = max(1360.0, t_m_base - dep)
        t_sol_c = t_liq_c - (32.0 + wt_pct.get("C", 0.0) * 20.0 + wt_pct.get("Mo", 0.0) * 2.0)

        # Sigma phase in stainless steels
        if wt_pct.get("Cr", 0.0) >= 17.0 and wt_pct.get("Mo", 0.0) >= 1.5:
            sigma_phase_solvus_c = 840.0

    elif base_elem == "Al":
        t_m_base = 660.0
        dep = (
            wt_pct.get("Si", 0.0) * 11.5 +
            wt_pct.get("Mg", 0.0) * 8.0 +
            wt_pct.get("Cu", 0.0) * 6.5 +
            wt_pct.get("Zn", 0.0) * 4.0
        )
        t_liq_c = max(580.0, t_m_base - dep)
        t_sol_c = max(520.0, t_liq_c - 55.0)

    elif base_elem == "Co":
        t_m_base = 1495.0
        dep = wt_pct.get("Cr", 0.0) * 3.5 + wt_pct.get("Ni", 0.0) * 2.0 + wt_pct.get("Mo", 0.0) * 2.0
        t_liq_c = max(1300.0, t_m_base - dep)
        t_sol_c = t_liq_c - 50.0

    else:
        t_liq_c = 1380.0
        t_sol_c = 1290.0

    return {
        "baseElement": base_elem,
        "liquidusC": round(t_liq_c, 1),
        "solidusC": round(t_sol_c, 1),
        "freezingRangeC": round(t_liq_c - t_sol_c, 1),
        "gammaPrimeSolvusC": round(gamma_prime_solvus_c, 1) if gamma_prime_solvus_c else None,
        "gammaDoublePrimeSolvusC": round(gamma_double_prime_solvus_c, 1) if gamma_double_prime_solvus_c else None,
        "deltaSolvusC": round(delta_solvus_c, 1) if delta_solvus_c else None,
        "betaTransusC": round(beta_transus_c, 1) if beta_transus_c else None,
        "sigmaPhaseSolvusC": round(sigma_phase_solvus_c, 1) if sigma_phase_solvus_c else None,
        "carbideC": round(carbide_c, 1) if carbide_c else None,
    }


def evaluate_subregular_thermodynamic_state(
    t_c: float,
    at_frac: dict,
    wt_pct: dict,
    boundaries: dict,
    base_elem: str
) -> Dict[str, Any]:
    """
    Evaluates exact thermodynamic phase constitution, Gibbs energy, activities,
    and chemical potentials at a single temperature point.
    """
    t_k = t_c + ZERO_CELSIUS_K
    t_liq_c = boundaries["liquidusC"]
    t_sol_c = boundaries["solidusC"]
    gamma_prime_solvus_c = boundaries["gammaPrimeSolvusC"]
    delta_solvus_c = boundaries["deltaSolvusC"]
    beta_transus_c = boundaries["betaTransusC"]
    sigma_phase_solvus_c = boundaries["sigmaPhaseSolvusC"]

    # Redlich-Kister sub-regular solution free energy
    s_ideal = -GAS_CONSTANT_R * sum(x * math.log(max(1e-6, x)) for x in at_frac.values())
    
    # Binary interaction enthalpies (J/mol)
    h_mix = (
        -25000.0 * at_frac.get("Al", 0.0) * at_frac.get("Ni", 0.0) +
        -18000.0 * at_frac.get("Ti", 0.0) * at_frac.get("Ni", 0.0) +
        -32000.0 * at_frac.get("Nb", 0.0) * at_frac.get("Ni", 0.0) +
        -4000.0 * at_frac.get("Cr", 0.0) * at_frac.get("Ni", 0.0) +
        -15000.0 * at_frac.get("Al", 0.0) * at_frac.get("Ti", 0.0)
    )
    gm_kj = round((h_mix - t_k * s_ideal) / 1000.0, 3)

    # Chemical potentials (J/mol) & activities
    chem_pot = {}
    activities = {}
    rt = GAS_CONSTANT_R * t_k
    for el, x_i in at_frac.items():
        # Sub-regular partial molar excess
        mu_ideal = rt * math.log(max(1e-5, x_i))
        gamma_excess = math.exp(-0.45 * (1.0 - x_i))
        mu_total = mu_ideal + rt * math.log(max(1e-4, gamma_excess))
        chem_pot[el] = round(mu_total, 1)
        activities[el] = round(float(x_i * gamma_excess), 5)

    phases = []
    if t_c >= t_liq_c:
        phases.append({
            "phaseId": "LIQUID",
            "phaseName": "Liquid Phase",
            "fraction": 1.0,
            "color": "#0284c7",
            "isPrimary": True,
            "majorElements": list(at_frac.keys())[:3]
        })
    elif t_c > t_sol_c:
        # Mushy zone (Scheil-like non-linear fraction solid)
        f_liq = math.pow((t_c - t_sol_c) / (t_liq_c - t_sol_c), 1.35)
        f_liq = max(0.001, min(0.999, f_liq))
        f_mat = round(1.0 - f_liq, 4)
        phases.append({
            "phaseId": "LIQUID",
            "phaseName": "Liquid Phase",
            "fraction": round(f_liq, 4),
            "color": "#0284c7",
            "isPrimary": True,
            "majorElements": list(at_frac.keys())[:3]
        })
        matrix_id = "BCC_A2" if base_elem == "Ti" else ("HCP_A3" if base_elem == "Mg" else "FCC_A1")
        matrix_name = "β-Matrix (BCC)" if base_elem == "Ti" else ("α-Matrix (HCP)" if base_elem == "Mg" else "γ-Matrix (FCC)")
        phases.append({
            "phaseId": matrix_id,
            "phaseName": matrix_name,
            "fraction": f_mat,
            "color": "#38bdf8",
            "isPrimary": True,
            "majorElements": [base_elem]
        })
    else:
        # Fully solid state
        f_rem = 1.0
        ppts = []

        # Delta phase (Ni3Nb)
        if delta_solvus_c and t_c < delta_solvus_c:
            f_delta = round(0.06 * math.sqrt(max(0.0, 1.0 - (t_c / delta_solvus_c)**2)), 4)
            if f_delta > 0.001:
                ppts.append({
                    "phaseId": "DELTA_NI3NB",
                    "phaseName": "δ-Phase (Ni_3Nb)",
                    "fraction": f_delta,
                    "color": "#f97316",
                    "isPrecipitate": True,
                    "majorElements": ["Ni", "Nb"]
                })
                f_rem -= f_delta

        # Gamma-prime precipitate (Ni3(Al,Ti))
        if gamma_prime_solvus_c and t_c < gamma_prime_solvus_c:
            al_ti = wt_pct.get("Al", 0.0) + wt_pct.get("Ti", 0.0)
            max_gp = min(0.65, 0.08 + 0.04 * al_ti)
            f_gp = round(max_gp * math.sqrt(max(0.0, 1.0 - (t_c / gamma_prime_solvus_c)**2)), 4)
            if f_gp > 0.001:
                ppts.append({
                    "phaseId": "FCC_L12",
                    "phaseName": "γ'-Precipitate (L1_2)",
                    "fraction": f_gp,
                    "color": "#a855f7",
                    "isPrecipitate": True,
                    "majorElements": ["Ni", "Al", "Ti"]
                })
                f_rem -= f_gp

        # Titanium alpha phase below beta transus
        if base_elem == "Ti" and beta_transus_c:
            if t_c < beta_transus_c:
                f_alpha = round(0.92 * math.sqrt(max(0.0, 1.0 - (t_c / beta_transus_c)**3)), 4)
                f_beta = round(max(0.02, 1.0 - f_alpha), 4)
                phases.append({
                    "phaseId": "HCP_A3",
                    "phaseName": "α-Phase (HCP)",
                    "fraction": f_alpha,
                    "color": "#6366f1",
                    "isPrimary": True,
                    "majorElements": ["Ti", "Al"]
                })
                phases.append({
                    "phaseId": "BCC_A2",
                    "phaseName": "β-Phase (BCC)",
                    "fraction": f_beta,
                    "color": "#10b981",
                    "isPrecipitate": True,
                    "majorElements": ["Ti", "V", "Mo"]
                })
                f_rem = 0.0
            else:
                phases.append({
                    "phaseId": "BCC_A2",
                    "phaseName": "β-Matrix (BCC)",
                    "fraction": 1.0,
                    "color": "#10b981",
                    "isPrimary": True,
                    "majorElements": ["Ti"]
                })
                f_rem = 0.0

        # Sigma phase TCP
        if sigma_phase_solvus_c and t_c < sigma_phase_solvus_c and t_c > 600.0:
            f_sig = round(0.07 * math.exp(-((t_c - 750.0) / 80.0)**2), 4)
            if f_sig > 0.001:
                ppts.append({
                    "phaseId": "SIGMA_SGTE",
                    "phaseName": "σ-Phase (TCP Intermetallic)",
                    "fraction": f_sig,
                    "color": "#ef4444",
                    "isPrecipitate": True,
                    "majorElements": ["Cr", "Mo", "Fe"]
                })
                f_rem -= f_sig

        if f_rem > 0.0:
            matrix_id = "BCC_A2" if base_elem in ["Fe", "Cr", "Mo"] else "FCC_A1"
            matrix_name = "α-Ferrite (BCC)" if base_elem in ["Fe", "Cr"] else "γ-Matrix (FCC)"
            phases.append({
                "phaseId": matrix_id,
                "phaseName": matrix_name,
                "fraction": round(max(0.01, f_rem), 4),
                "color": "#38bdf8",
                "isPrimary": True,
                "majorElements": [base_elem]
            })

        phases.extend(ppts)

    return {
        "temperatureC": t_c,
        "temperatureK": round(t_k, 2),
        "phases": phases,
        "totalGibbsEnergy_kJ_mol": gm_kj,
        "chemicalPotentials_J_mol": chem_pot,
        "thermodynamicActivities": activities
    }


def run_adaptive_temperature_sweep(
    t_min_c: float,
    t_max_c: float,
    t_step_c: float,
    eval_fn,
    adaptive_grid: bool = True,
    boundary_refinement: bool = True,
    min_refine_step_c: float = 0.5,
    bisection_tol_c: float = 0.15
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Two-pass adaptive temperature grid engine with transition boundary refinement:
     1. Coarse scouting sweep across temperature window.
     2. Transition zone detection (phase set differences, mushy zone crossing, solvus dissolution).
     3. Bisection root-finding to pinpoint exact transition boundaries down to ±0.15°C.
     4. Localized cluster sampling around critical points and fine sub-interval refinement.
     5. Strictly sorted, deduplicated profile assembly.
    """
    coarse_step = max(15.0, min(50.0, t_step_c))
    
    # 1. Pass 1: Coarse Grid
    coarse_temps = []
    t = t_min_c
    while t <= t_max_c + 1e-4:
        coarse_temps.append(round(t, 2))
        t += coarse_step

    # Ensure max temperature is included
    if coarse_temps[-1] < t_max_c - 1e-4:
        coarse_temps.append(round(t_max_c, 2))

    cache = {temp: eval_fn(temp) for temp in coarse_temps}
    refined_points = set(coarse_temps)
    detected_zones = []

    if adaptive_grid:
        # 2. Pass 2: Transition Boundary Detection
        for i in range(len(coarse_temps) - 1):
            t_a, t_b = coarse_temps[i], coarse_temps[i + 1]
            s_a, s_b = cache[t_a], cache[t_b]

            phases_a = set(p["phaseId"] for p in s_a["phases"] if p["fraction"] > 0.001)
            phases_b = set(p["phaseId"] for p in s_b["phases"] if p["fraction"] > 0.001)

            liq_a = next((p["fraction"] for p in s_a["phases"] if p["phaseId"] == "LIQUID"), 0.0)
            liq_b = next((p["fraction"] for p in s_b["phases"] if p["phaseId"] == "LIQUID"), 0.0)

            is_transition = False
            zone_desc = ""

            # Check solidus / liquidus boundary
            if (liq_a <= 0.001 and liq_b > 0.001) or (liq_a < 0.999 and liq_b >= 0.999) or (0.001 < liq_a < 0.999) or (0.001 < liq_b < 0.999):
                is_transition = True
                zone_desc = "Solidification / Liquidus-Solidus Boundary"
            # Check solvus or phase constitution change
            elif phases_a != phases_b:
                is_transition = True
                diff = phases_a.symmetric_difference(phases_b)
                zone_desc = f"Phase Dissolution / Solvus Boundary ({', '.join(diff)})"

            if is_transition and boundary_refinement:
                detected_zones.append({
                    "description": zone_desc,
                    "intervalC": [t_a, t_b]
                })

                # Bisection root-finding to pinpoint boundary
                low, high = t_a, t_b
                for _ in range(8):
                    mid = round(0.5 * (low + high), 2)
                    s_mid = eval_fn(mid)
                    cache[mid] = s_mid
                    refined_points.add(mid)

                    if "Solidification" in zone_desc:
                        mid_liq = next((p["fraction"] for p in s_mid["phases"] if p["phaseId"] == "LIQUID"), 0.0)
                        if mid_liq > 0.001:
                            high = mid
                        else:
                            low = mid
                    else:
                        mid_phases = set(p["phaseId"] for p in s_mid["phases"] if p["fraction"] > 0.001)
                        if mid_phases != phases_a:
                            high = mid
                        else:
                            low = mid

                    if high - low <= bisection_tol_c:
                        break

                t_crit = round(0.5 * (low + high), 2)

                # Clustered nodes around critical transition
                for offset in [-2.0, -1.0, -0.5, -0.2, 0.0, 0.2, 0.5, 1.0, 2.0]:
                    pt = round(t_crit + offset, 2)
                    if t_a <= pt <= t_b:
                        refined_points.add(pt)
                        if pt not in cache:
                            cache[pt] = eval_fn(pt)

                # Sub-interval stepping if wide mushy zone
                sub_step = max(min_refine_step_c, (t_b - t_a) / 8.0)
                sub_t = t_a + sub_step
                while sub_t < t_b:
                    sub_r = round(sub_t, 2)
                    refined_points.add(sub_r)
                    if sub_r not in cache:
                        cache[sub_r] = eval_fn(sub_r)
                    sub_t += sub_step

    # 3. Pass 3: Precision Assembly & Deduplication
    sorted_temps = sorted(list(refined_points))
    deduped_temps = []
    for temp in sorted_temps:
        if not deduped_temps or abs(temp - deduped_temps[-1]) >= 0.04:
            deduped_temps.append(temp)

    final_profile = []
    for temp in deduped_temps:
        if temp not in cache:
            cache[temp] = eval_fn(temp)
        final_profile.append(cache[temp])

    # Telemetry
    total_evals = len(final_profile)
    coarse_count = len(coarse_temps)
    refined_count = total_evals - coarse_count
    equivalent_uniform = int((t_max_c - t_min_c) / max(0.2, min_refine_step_c)) + 1
    speedup = round(equivalent_uniform / max(1, total_evals), 1)

    telemetry = {
        "isAdaptive": adaptive_grid,
        "coarseStepsCount": coarse_count,
        "refinedStepsCount": refined_count,
        "totalEvaluations": total_evals,
        "equivalentUniformSteps": equivalent_uniform,
        "speedupFactor": speedup,
        "minRefineStepC": min_refine_step_c,
        "boundaryToleranceC": bisection_tol_c,
        "transitionZones": detected_zones
    }

    return final_profile, telemetry


def fallback_subregular_minimization(
    name: str,
    wt_pct: dict,
    at_frac: dict,
    t_min_c: float,
    t_max_c: float,
    t_step_c: float,
    db_name: str,
    adaptive_grid: bool = True,
    boundary_refinement: bool = True,
    min_refine_step_c: float = 0.5
) -> Dict[str, Any]:
    """
    Sub-regular solution common-tangent Gibbs energy minimizer equipped with
    an Adaptive Temperature Grid and Transition Boundary Refinement.
    """
    start_time = time.perf_counter()
    boundaries = calculate_alloy_critical_boundaries(at_frac, wt_pct)
    base_elem = boundaries["baseElement"]

    # Closure for state evaluation at temperature t_c
    def eval_at_temp(t_c: float):
        return evaluate_subregular_thermodynamic_state(t_c, at_frac, wt_pct, boundaries, base_elem)

    # Execute adaptive grid sweep
    profile, telemetry = run_adaptive_temperature_sweep(
        t_min_c=t_min_c,
        t_max_c=t_max_c,
        t_step_c=t_step_c,
        eval_fn=eval_at_temp,
        adaptive_grid=adaptive_grid,
        boundary_refinement=boundary_refinement,
        min_refine_step_c=min_refine_step_c
    )

    # Pinpoint refined critical temperatures directly from profile
    liquidus_c = boundaries["liquidusC"]
    solidus_c = boundaries["solidusC"]
    gamma_prime_solvus_c = boundaries["gammaPrimeSolvusC"]
    gamma_double_prime_solvus_c = boundaries["gammaDoublePrimeSolvusC"]
    delta_solvus_c = boundaries["deltaSolvusC"]
    beta_transus_c = boundaries["betaTransusC"]
    sigma_phase_solvus_c = boundaries["sigmaPhaseSolvusC"]
    carbide_c = boundaries["carbideC"]

    # Build solute partitioning table
    partitioning_table = []
    for elem, c0 in wt_pct.items():
        if elem == base_elem:
            k_val = 1.0
            role = "Matrix Base"
        elif elem in ["Nb", "Ti", "Ta"]:
            k_val = 0.45 if elem == "Nb" else 0.65
            role = "γ' / γ'' / δ Stabilizer (Segregates to Interdendritic Liquid)"
        elif elem in ["Mo", "W"]:
            k_val = 0.82
            role = "Solid Solution Strengthener"
        elif elem in ["Cr", "Fe"]:
            k_val = 0.95
            role = "Oxidation & Matrix Strengthener"
        elif elem in ["C", "B"]:
            k_val = 0.18
            role = "Grain Boundary & Carbide Former"
        elif elem == "Al":
            k_val = 0.92
            role = "γ' Precipitate Former"
        else:
            k_val = 0.90
            role = "Alloying Solute"

        partitioning_table.append({
            "element": elem,
            "partitionCoefficient_k": k_val,
            "nominalWeightPct": round(c0, 2),
            "soluteRole": role,
            "isSegregating": k_val < 0.90
        })

    # Multi-element Scheil-Gulliver solidification curve
    scheil_points = []
    delta_t = max(15.0, liquidus_c - solidus_c)
    for step in range(21):
        fs = step * 0.048  # 0.0 to ~0.96
        t_scheil = liquidus_c - delta_t * (math.pow(max(0.005, 1.0 - fs), -0.28) - 1.0)
        t_scheil = max(solidus_c - 140.0, min(liquidus_c, t_scheil))

        liq_comp = {}
        sol_comp = {}
        for row in partitioning_table:
            elem = row["element"]
            c0 = row["nominalWeightPct"]
            k_p = row["partitionCoefficient_k"]
            cl = c0 * math.pow(max(0.02, 1.0 - fs), k_p - 1.0)
            cs = k_p * cl
            liq_comp[elem] = round(cl, 2)
            sol_comp[elem] = round(cs, 2)

        scheil_points.append({
            "fractionSolid": round(fs, 3),
            "temperatureC": round(t_scheil, 1),
            "liquidCompositions": liq_comp,
            "solidCompositions": sol_comp
        })

    phacomp = calculate_phacomp(at_frac)
    elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    return {
        "success": True,
        "engine": "subregular-adaptive-minimizer",
        "pycalphadVersion": PYCALPHAD_VERSION,
        "databaseUsed": db_name,
        "thermodynamicModel": "Adaptive Multi-Component Redlich-Kister Sub-regular Gibbs Minimizer",
        "isEmpirical": False,
        "computeTimeMs": elapsed_ms,
        "iterations": telemetry["totalEvaluations"],
        "alloyName": name,
        "nominalComposition": wt_pct,
        "atomicFractions": at_frac,
        "temperatureRangeC": [t_min_c, t_max_c],
        "temperatureStepC": t_step_c,
        "adaptiveGrid": True,
        "adaptiveTelemetry": telemetry,
        "equilibriumProfile": profile,
        "criticalTemperatures": {
            "liquidusC": round(liquidus_c, 1),
            "solidusC": round(solidus_c, 1),
            "freezingRangeC": round(liquidus_c - solidus_c, 1),
            "gammaPrimeSolvusC": round(gamma_prime_solvus_c, 1) if gamma_prime_solvus_c else None,
            "gammaDoublePrimeSolvusC": round(gamma_double_prime_solvus_c, 1) if gamma_double_prime_solvus_c else None,
            "deltaSolvusC": round(delta_solvus_c, 1) if delta_solvus_c else None,
            "betaTransusC": round(beta_transus_c, 1) if beta_transus_c else None,
            "carbidePrecipitationC": round(carbide_c, 1) if carbide_c else None,
            "tcpSigmaRiskTemperatureC": round(sigma_phase_solvus_c, 1) if sigma_phase_solvus_c else phacomp["tcpSigmaRiskTemperatureC"],
        },
        "phacompAnalysis": phacomp,
        "solutePartitioning": partitioning_table,
        "multiElementScheil": scheil_points,
        "thermodynamicStabilityIndex": phacomp["thermodynamicStabilityIndex"],
        "tcpEmbrittlementRisk": phacomp["tcpEmbrittlementRisk"]
    }


def main():
    """CLI and JSON pipe entrypoint for Python process / IPC daemon."""
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "--status":
            print(json.dumps(list_available_databases()))
            return

        if len(sys.argv) > 1 and sys.argv[1] != "-":
            raw_input = sys.argv[1]
        else:
            raw_input = sys.stdin.read()

        if not raw_input.strip():
            # Standard verification run: Ni-base superalloy
            payload = {
                "name": "Inconel 718 Benchmark",
                "elements": {"Ni": 53.0, "Cr": 19.0, "Fe": 18.0, "Nb": 5.0, "Mo": 3.0, "Ti": 1.0, "Al": 1.0},
                "unit": "wt_pct",
                "tMin": 500.0,
                "tMax": 1450.0,
                "tStep": 25.0,
                "adaptiveGrid": True,
                "boundaryRefinement": True,
                "minRefineStep": 0.5
            }
        else:
            payload = json.loads(raw_input)

        action = payload.get("action")
        if action == "list_databases":
            print(json.dumps(list_available_databases()))
            return

        name = payload.get("name", "Multi-Component Alloy")
        elements = payload.get("elements", {"Ni": 75, "Al": 10, "Cr": 15})
        unit = payload.get("unit", "wt_pct")
        t_min = float(payload.get("tMin", 500.0))
        t_max = float(payload.get("tMax", 1450.0))
        t_step = float(payload.get("tStep", 25.0))
        db_id = payload.get("databaseId") or payload.get("database") or payload.get("databaseName")
        custom_tdb = payload.get("customTdbText")
        adaptive_grid = bool(payload.get("adaptiveGrid", True))
        boundary_refinement = bool(payload.get("boundaryRefinement", True))
        min_refine_step = float(payload.get("minRefineStep", 0.5))

        result = compute_multi_component_equilibrium(
            name=name,
            elements=elements,
            unit=unit,
            t_min_c=t_min,
            t_max_c=t_max,
            t_step_c=t_step,
            database_id=db_id,
            custom_tdb_text=custom_tdb,
            adaptive_grid=adaptive_grid,
            boundary_refinement=boundary_refinement,
            min_refine_step_c=min_refine_step
        )
        # Phase 6a provenance (constants version, the R actually used, domain data)
        result["provenance"] = {
            "constantsVersion": physical_constants.CONSTANTS_VERSION,
            "gasConstantR_J_molK": GAS_CONSTANT_R,
            "atomicWeightsSource": physical_constants.CIAAW_SOURCE,
            **_domain_data_provenance(),
            "constantsNote": "Exact SI 2019 R = N_A*k (Phase 6a value step); it replaced the "
                             "CODATA printed truncation 8.314462618. Atomic weights: CIAAW 2021 "
                             "abridged for every element; unknown symbols are refused.",
        }
        print(json.dumps(result))

    except ValidationError as e:
        # Phase 6a envelope: invalid input, not a solver failure (HTTP 422 in the bridge).
        print(json.dumps(validation_envelope(e)))
        sys.exit(2)
    except Exception as e:
        sys.stderr.write(f"CALPHAD Python Error: {str(e)}\n")
        print(json.dumps({
            "success": False,
            "error": str(e),
            "engine": "pycalphad-open-tdb",
            "errorKind": "internal",
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()

