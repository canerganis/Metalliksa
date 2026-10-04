#!/usr/bin/env python3
"""
MetalliX Python Pourbaix E-pH Stability & Electrochemical Equilibrium Solver
Evaluates multi-element Nernst electrochemical equilibria, water stability limits,
corrosion, passivation, and immunity phase domains across pH (0 to 14) and E (-2.5V to +2.5V).
Includes overlay analysis for experimental E-pH test data to identify specific corrosion mechanisms.
"""

import sys
import json
import math
import time

import physical_constants
from input_validation import UNKNOWN_ELEMENT, ValidationError, validation_envelope

# Phase 6a structural step (a): R, F and the Celsius offset come from
# physical_constants but keep the CODATA printed truncations used before the
# migration (8.314462618, 96485.33212) so the output stays bit-identical. The
# switch to the exact SI products is the separate value step (b).
R_GAS = physical_constants.TRUNCATED_GAS_CONSTANT_R  # J / (mol * K)
F_FARADAY = physical_constants.TRUNCATED_FARADAY  # C / mol
ZERO_CELSIUS_K = physical_constants.ZERO_CELSIUS_K.value  # 273.15 K
# Not in physical_constants: its CIAAW abridged Cl value is not registered and
# would be 35.45, not the 35.453 used here, so this stays local until step (b).
CHLORIDE_MOLAR_MASS_G_MOL = 35.453

# Reference Electrode Standard Offsets vs SHE at 25°C
REF_ELECTRODE_OFFSETS = {
    "SHE": 0.000,
    "SCE": 0.241,               # Saturated Calomel Electrode (Sat. KCl)
    "Ag/AgCl (3M KCl)": 0.207,   # Silver/Silver Chloride (3M KCl)
    "Ag/AgCl (Sat KCl)": 0.197,  # Sat. Ag/AgCl
    "CSE": 0.316,               # Copper/Copper Sulfate Electrode
    "MMS": 0.640,               # Mercury/Mercurous Sulfate (Sat. K2SO4)
}

# Standard Thermodynamic Electrochemical Equilibrium Systems
POURBAIX_ELEMENT_SYSTEMS = {
    "Fe": {
        "name": "Iron (Fe-H₂O System)",
        "atomicMass": physical_constants.atomic_weight("Fe"),
        "standardE0_V": -0.440,
        "reactions": [
            {
                "id": "fe_imm_act",
                "name": "Fe / Fe²⁺",
                "equation": "Fe(s) ⇌ Fe²⁺ + 2e⁻",
                "type": "redox",
                "e0": -0.440,
                "slope_pH": 0.0,
                "domain": "immunity_vs_active",
                "boundaryType": "Immunity / Active Dissolution",
                "speciesA": "Fe (Metallic Immunity)",
                "speciesB": "Fe²⁺ (aq)"
            },
            {
                "id": "fe_act_fe3",
                "name": "Fe²⁺ / Fe³⁺",
                "equation": "Fe²⁺ ⇌ Fe³⁺ + e⁻",
                "type": "redox",
                "e0": 0.771,
                "slope_pH": 0.0,
                "domain": "active",
                "boundaryType": "Acid Redox Fe(II)/Fe(III)",
                "speciesA": "Fe²⁺ (aq)",
                "speciesB": "Fe³⁺ (aq)"
            },
            {
                "id": "fe_act_pass",
                "name": "2Fe²⁺ + 3H₂O / Fe₂O₃",
                "equation": "2Fe²⁺ + 3H₂O ⇌ Fe₂O₃(s) + 6H⁺ + 2e⁻",
                "type": "redox_ph",
                "e0": 0.728,
                "slope_pH": -0.1773, # (6 * 0.05916 / 2) = -0.1775
                "domain": "active_vs_passive",
                "boundaryType": "Active Dissolution / Passivation",
                "speciesA": "Fe²⁺ (aq)",
                "speciesB": "Fe₂O₃ (Hematite Passive)"
            },
            {
                "id": "fe_imm_magnetite",
                "name": "3Fe + 4H₂O / Fe₃O₄",
                "equation": "3Fe(s) + 4H₂O ⇌ Fe₃O₄(s) + 8H⁺ + 8e⁻",
                "type": "redox_ph",
                "e0": -0.085,
                "slope_pH": -0.0592,
                "domain": "immunity_vs_passive",
                "boundaryType": "Immunity / Magnetite Passivation",
                "speciesA": "Fe(s)",
                "speciesB": "Fe₃O₄ (Magnetite)"
            },
            {
                "id": "fe_pass_trans",
                "name": "Fe₂O₃ + 5H₂O / 2FeO₄²⁻",
                "equation": "Fe₂O₃(s) + 5H₂O ⇌ 2FeO₄²⁻ + 10H⁺ + 6e⁻",
                "type": "transpassive",
                "e0": 2.20,
                "slope_pH": -0.0986,
                "domain": "transpassive",
                "boundaryType": "Passivation / Transpassive Dissolution",
                "speciesA": "Fe₂O₃",
                "speciesB": "FeO₄²⁻ (Ferryl Anion)"
            },
            {
                "id": "fe_alkaline",
                "name": "Fe + 2H₂O / HFeO₂⁻",
                "equation": "Fe(s) + 2H₂O ⇌ HFeO₂⁻ + 3H⁺ + 2e⁻",
                "type": "redox_ph",
                "e0": 0.493,
                "slope_pH": -0.0886,
                "domain": "alkaline_corrosion",
                "boundaryType": "Alkaline Caustic Dissolution",
                "speciesA": "Fe₃O₄",
                "speciesB": "HFeO₂⁻ (Hypoferrite)"
            }
        ],
        "species": {
            "immunity": ["Fe(s) (Metallic Zero-Valence)"],
            "corrosion_acid": ["Fe²⁺(aq)", "Fe³⁺(aq)", "FeOH²⁺(aq)"],
            "passivation": ["Fe₂O₃(s) (Hematite)", "Fe₃O₄(s) (Magnetite)", "FeOOH(s) (Goethite)"],
            "corrosion_alkaline": ["HFeO₂⁻(aq) (Bihypoferrite)", "FeO₄²⁻(aq) (Ferryl VI)"]
        }
    },
    "Cr": {
        "name": "Chromium (Cr-H₂O System)",
        "atomicMass": physical_constants.atomic_weight("Cr"),
        "standardE0_V": -0.913,
        "reactions": [
            {
                "id": "cr_imm_act",
                "name": "Cr / Cr²⁺",
                "equation": "Cr(s) ⇌ Cr²⁺ + 2e⁻",
                "type": "redox",
                "e0": -0.913,
                "slope_pH": 0.0,
                "domain": "immunity_vs_active",
                "boundaryType": "Immunity / Active Dissolution",
                "speciesA": "Cr (Metallic)",
                "speciesB": "Cr²⁺ (aq)"
            },
            {
                "id": "cr_act_pass",
                "name": "2Cr²⁺ + 3H₂O / Cr₂O₃",
                "equation": "2Cr²⁺ + 3H₂O ⇌ Cr₂O₃(s) + 6H⁺ + 2e⁻",
                "type": "redox_ph",
                "e0": -0.580,
                "slope_pH": -0.1773,
                "domain": "active_vs_passive",
                "boundaryType": "Active / Passivation",
                "speciesA": "Cr²⁺ (aq)",
                "speciesB": "Cr₂O₃ (Chromia Barrier)"
            },
            {
                "id": "cr_pass_trans",
                "name": "Cr₂O₃ + 4H₂O / 2CrO₄²⁻",
                "equation": "Cr₂O₃(s) + 4H₂O ⇌ 2CrO₄²⁻ + 8H⁺ + 6e⁻",
                "type": "transpassive",
                "e0": 1.350,
                "slope_pH": -0.0788,
                "domain": "passive_vs_transpassive",
                "boundaryType": "Passivation / Transpassive (Chromate)",
                "speciesA": "Cr₂O₃",
                "speciesB": "CrO₄²⁻ / Cr₂O₇²⁻ (aq)"
            }
        ],
        "species": {
            "immunity": ["Cr(s)"],
            "corrosion_acid": ["Cr²⁺(aq)", "Cr³⁺(aq)"],
            "passivation": ["Cr₂O₃(s) (Chromia Passive Film)", "Cr(OH)₃(s)"],
            "corrosion_alkaline": ["CrO₄²⁻(aq) (Chromate VI)", "Cr₂O₇²⁻(aq) (Dichromate VI)"]
        }
    },
    "Ni": {
        "name": "Nickel (Ni-H₂O System)",
        "atomicMass": physical_constants.atomic_weight("Ni"),
        "standardE0_V": -0.257,
        "reactions": [
            {
                "id": "ni_imm_act",
                "name": "Ni / Ni²⁺",
                "equation": "Ni(s) ⇌ Ni²⁺ + 2e⁻",
                "type": "redox",
                "e0": -0.257,
                "slope_pH": 0.0,
                "domain": "immunity_vs_active",
                "boundaryType": "Immunity / Active Dissolution",
                "speciesA": "Ni(s)",
                "speciesB": "Ni²⁺ (aq)"
            },
            {
                "id": "ni_act_pass",
                "name": "Ni²⁺ + H₂O / NiO",
                "equation": "Ni²⁺ + H₂O ⇌ NiO(s) + 2H⁺",
                "type": "hydrolysis",
                "pH_trans": 6.8,
                "domain": "active_vs_passive",
                "boundaryType": "Active Hydrolysis / NiO Passivation",
                "speciesA": "Ni²⁺ (aq)",
                "speciesB": "NiO / Ni(OH)₂"
            },
            {
                "id": "ni_pass_trans",
                "name": "Ni(OH)₂ / NiO₂",
                "equation": "Ni(OH)₂(s) ⇌ NiO₂(s) + 2H⁺ + 2e⁻",
                "type": "redox_ph",
                "e0": 1.434,
                "slope_pH": -0.0592,
                "domain": "passive",
                "boundaryType": "Ni(II) / Ni(IV) Higher Oxide",
                "speciesA": "Ni(OH)₂",
                "speciesB": "NiO₂ (s)"
            }
        ],
        "species": {
            "immunity": ["Ni(s)"],
            "corrosion_acid": ["Ni²⁺(aq)"],
            "passivation": ["NiO(s)", "Ni(OH)₂(s)", "Ni₂O₃(s)", "NiO₂(s)"],
            "corrosion_alkaline": ["HNiO₂⁻(aq)"]
        }
    },
    "Ti": {
        "name": "Titanium (Ti-H₂O System)",
        "atomicMass": physical_constants.atomic_weight("Ti"),
        "standardE0_V": -1.630,
        "reactions": [
            {
                "id": "ti_imm_act",
                "name": "Ti / Ti²⁺",
                "equation": "Ti(s) ⇌ Ti²⁺ + 2e⁻",
                "type": "redox",
                "e0": -1.630,
                "slope_pH": 0.0,
                "domain": "immunity_vs_active",
                "boundaryType": "Immunity / Ti²⁺",
                "speciesA": "Ti(s)",
                "speciesB": "Ti²⁺"
            },
            {
                "id": "ti_imm_pass",
                "name": "Ti + 2H₂O / TiO₂",
                "equation": "Ti(s) + 2H₂O ⇌ TiO₂(s) + 4H⁺ + 4e⁻",
                "type": "redox_ph",
                "e0": -0.860,
                "slope_pH": -0.0592,
                "domain": "immunity_vs_passive",
                "boundaryType": "Immunity / Titania Barrier",
                "speciesA": "Ti(s)",
                "speciesB": "TiO₂ (Rutile/Anatase)"
            },
            {
                "id": "ti_pass_acid",
                "name": "TiO₂ + 2H⁺ / TiO²⁺",
                "equation": "TiO₂(s) + 2H⁺ ⇌ TiO²⁺ + H₂O",
                "type": "acid_dissolution",
                "pH_trans": 1.2,
                "domain": "active_vs_passive",
                "boundaryType": "Concentrated Acid Dissolution",
                "speciesA": "TiO₂",
                "speciesB": "TiO²⁺ (Titanyl)"
            }
        ],
        "species": {
            "immunity": ["Ti(s)"],
            "corrosion_acid": ["Ti²⁺(aq)", "Ti³⁺(aq)", "TiO²⁺(Titanyl)"],
            "passivation": ["TiO₂(s) (Rutile/Anatase Titania)", "Ti₂O₃(s)", "TiO(s)"],
            "corrosion_alkaline": ["HTiO₃⁻(aq)"]
        }
    },
    "Al": {
        "name": "Aluminum (Al-H₂O Amphoteric System)",
        "atomicMass": physical_constants.atomic_weight("Al"),
        "standardE0_V": -1.662,
        "reactions": [
            {
                "id": "al_imm_act",
                "name": "Al / Al³⁺",
                "equation": "Al(s) ⇌ Al³⁺ + 3e⁻",
                "type": "redox",
                "e0": -1.662,
                "slope_pH": 0.0,
                "domain": "immunity_vs_active",
                "boundaryType": "Immunity / Acid Active",
                "speciesA": "Al(s)",
                "speciesB": "Al³⁺ (aq)"
            },
            {
                "id": "al_act_pass",
                "name": "2Al³⁺ + 3H₂O / Al₂O₃",
                "equation": "2Al³⁺ + 3H₂O ⇌ Al₂O₃(s) + 6H⁺",
                "type": "hydrolysis",
                "pH_trans": 3.9,
                "domain": "active_vs_passive",
                "boundaryType": "Acid Active / Passivation",
                "speciesA": "Al³⁺ (aq)",
                "speciesB": "Al₂O₃·3H₂O (Bayerite)"
            },
            {
                "id": "al_pass_alkaline",
                "name": "Al₂O₃ + 2OH⁻ / 2AlO₂⁻",
                "equation": "Al₂O₃(s) + 2OH⁻ ⇌ 2AlO₂⁻ + H₂O",
                "type": "alkaline_dissolution",
                "pH_trans": 8.8,
                "domain": "passive_vs_alkaline",
                "boundaryType": "Passivity / Alkaline Aluminate Dissolution",
                "speciesA": "Al₂O₃",
                "speciesB": "AlO₂⁻ / Al(OH)₄⁻ (Aluminate)"
            }
        ],
        "species": {
            "immunity": ["Al(s)"],
            "corrosion_acid": ["Al³⁺(aq)", "AlOH²⁺(aq)"],
            "passivation": ["Al₂O₃·3H₂O (Bayerite/Boehmite Barrier Oxide)"],
            "corrosion_alkaline": ["AlO₂⁻(aq)", "Al(OH)₄⁻(aq) (Aluminate)"]
        }
    },
    "Cu": {
        "name": "Copper (Cu-H₂O System)",
        "atomicMass": physical_constants.atomic_weight("Cu"),
        "standardE0_V": +0.342,
        "reactions": [
            {
                "id": "cu_imm_act",
                "name": "Cu / Cu²⁺",
                "equation": "Cu(s) ⇌ Cu²⁺ + 2e⁻",
                "type": "redox",
                "e0": 0.342,
                "slope_pH": 0.0,
                "domain": "immunity_vs_active",
                "boundaryType": "Immunity / Cu²⁺ Acid Active",
                "speciesA": "Cu(s)",
                "speciesB": "Cu²⁺ (aq)"
            },
            {
                "id": "cu_act_cu2o",
                "name": "2Cu + H₂O / Cu₂O",
                "equation": "2Cu(s) + H₂O ⇌ Cu₂O(s) + 2H⁺ + 2e⁻",
                "type": "redox_ph",
                "e0": 0.471,
                "slope_pH": -0.0592,
                "domain": "immunity_vs_passive",
                "boundaryType": "Immunity / Cuprite (Cu₂O) Passivity",
                "speciesA": "Cu(s)",
                "speciesB": "Cu₂O (Cuprite)"
            },
            {
                "id": "cu_cu2o_cuo",
                "name": "Cu₂O + H₂O / 2CuO",
                "equation": "Cu₂O(s) + H₂O ⇌ 2CuO(s) + 2H⁺ + 2e⁻",
                "type": "redox_ph",
                "e0": 0.669,
                "slope_pH": -0.0592,
                "domain": "passive",
                "boundaryType": "Cu₂O / Tenorite (CuO) Passivity",
                "speciesA": "Cu₂O",
                "speciesB": "CuO (Tenorite)"
            },
            {
                "id": "cu_alkaline",
                "name": "CuO + H₂O / HCuO₂⁻",
                "equation": "CuO(s) + H₂O ⇌ HCuO₂⁻ + H⁺",
                "type": "alkaline_dissolution",
                "pH_trans": 12.8,
                "domain": "passive_vs_alkaline",
                "boundaryType": "Alkaline Dissolution",
                "speciesA": "CuO",
                "speciesB": "HCuO₂⁻ / CuO₂²⁻"
            }
        ],
        "species": {
            "immunity": ["Cu(s) (Noble Element Immunity)"],
            "corrosion_acid": ["Cu⁺(aq)", "Cu²⁺(aq)"],
            "passivation": ["Cu₂O(s) (Cuprite)", "CuO(s) (Tenorite)", "Cu(OH)₂(s)"],
            "corrosion_alkaline": ["HCuO₂⁻(aq)", "CuO₂²⁻(aq)"]
        }
    },
    "Zn": {
        "name": "Zinc (Zn-H₂O System Amphoteric)",
        "atomicMass": physical_constants.atomic_weight("Zn"),
        "standardE0_V": -0.763,
        "reactions": [
            {
                "id": "zn_imm_act",
                "name": "Zn / Zn²⁺",
                "equation": "Zn(s) ⇌ Zn²⁺ + 2e⁻",
                "type": "redox",
                "e0": -0.763,
                "slope_pH": 0.0,
                "domain": "immunity_vs_active",
                "boundaryType": "Immunity / Acid Active Zn²⁺",
                "speciesA": "Zn(s)",
                "speciesB": "Zn²⁺ (aq)"
            },
            {
                "id": "zn_act_pass",
                "name": "Zn²⁺ + H₂O / ZnO",
                "equation": "Zn²⁺ + H₂O ⇌ ZnO(s) + 2H⁺",
                "type": "hydrolysis",
                "pH_trans": 6.0,
                "domain": "active_vs_passive",
                "boundaryType": "Acid Active / Zincite Passivation",
                "speciesA": "Zn²⁺ (aq)",
                "speciesB": "ZnO / Zn(OH)₂"
            },
            {
                "id": "zn_pass_alkaline",
                "name": "ZnO + H₂O / ZnO₂²⁻",
                "equation": "ZnO(s) + H₂O ⇌ ZnO₂²⁻ + 2H⁺",
                "type": "alkaline_dissolution",
                "pH_trans": 11.5,
                "domain": "passive_vs_alkaline",
                "boundaryType": "Alkaline Zincate Dissolution",
                "speciesA": "ZnO",
                "speciesB": "ZnO₂²⁻ / HZnO₂⁻ (Zincate)"
            }
        ],
        "species": {
            "immunity": ["Zn(s)"],
            "corrosion_acid": ["Zn²⁺(aq)"],
            "passivation": ["ZnO(s) (Zincite)", "Zn(OH)₂(s) (Wülfingite)"],
            "corrosion_alkaline": ["HZnO₂⁻(aq)", "ZnO₂²⁻(aq) (Zincate)"]
        }
    },
    "Mg": {
        "name": "Magnesium (Mg-H₂O System)",
        "atomicMass": physical_constants.atomic_weight("Mg"),
        "standardE0_V": -2.372,
        "reactions": [
            {
                "id": "mg_imm_act",
                "name": "Mg / Mg²⁺",
                "equation": "Mg(s) ⇌ Mg²⁺ + 2e⁻",
                "type": "redox",
                "e0": -2.372,
                "slope_pH": 0.0,
                "domain": "immunity_vs_active",
                "boundaryType": "Immunity / Active Dissolution",
                "speciesA": "Mg(s)",
                "speciesB": "Mg²⁺ (aq)"
            },
            {
                "id": "mg_act_pass",
                "name": "Mg²⁺ + 2H₂O / Mg(OH)₂",
                "equation": "Mg²⁺ + 2H₂O ⇌ Mg(OH)₂(s) + 2H⁺",
                "type": "hydrolysis",
                "pH_trans": 10.5,
                "domain": "active_vs_passive",
                "boundaryType": "Active Acid / Brucite Passivity",
                "speciesA": "Mg²⁺ (aq)",
                "speciesB": "Mg(OH)₂ (Brucite)"
            }
        ],
        "species": {
            "immunity": ["Mg(s) (Extreme Negative Potential)"],
            "corrosion_acid": ["Mg²⁺(aq) (Aggressive HER Self-Dissolution)"],
            "passivation": ["Mg(OH)₂(s) (Brucite Alkaline Passive Layer)"],
            "corrosion_alkaline": ["Mg(OH)₂(s)"]
        }
    }
}

def calculate_nernst_slope(temperature_C=25.0):
    t_kelvin = ZERO_CELSIUS_K + float(temperature_C)
    r_gas = R_GAS
    f_faraday = F_FARADAY
    return (2.302585093 * r_gas * t_kelvin) / f_faraday # 0.05916 V/pH at 25°C

def generate_water_stability_lines(temperature_C=25.0):
    nernst_slope = calculate_nernst_slope(temperature_C)
    t_k = temperature_C + ZERO_CELSIUS_K
    # Standard O2 potential temperature dependence: E0(T) = 1.229 - 0.000845*(T - 298.15)
    e0_oer = 1.229 - 0.000845 * (t_k - 298.15)
    
    line_a = []
    line_b = []
    for ph_i in range(16): # 0 to 15
        ph = float(ph_i)
        e_her = 0.0 - nernst_slope * ph
        e_oer = e0_oer - nernst_slope * ph
        line_a.append({"pH": ph, "E_V_SHE": round(e_her, 4)})
        line_b.append({"pH": ph, "E_V_SHE": round(e_oer, 4)})
        
    return {
        "nernstSlope": round(nernst_slope, 5),
        "e0_OER": round(e0_oer, 4),
        "line_a_hydrogen_HER": line_a,
        "line_b_oxygen_OER": line_b,
        "equation_HER": f"E = 0.000 - {nernst_slope:.4f}·pH (Line a: 2H⁺ + 2e⁻ ⇌ H₂)",
        "equation_OER": f"E = {e0_oer:.3f} - {nernst_slope:.4f}·pH (Line b: O₂ + 4H⁺ + 4e⁻ ⇌ 2H₂O)"
    }

def calculate_chloride_pitting_boundary(element="Fe", temperature_C=25.0, chloride_ppm=0.0):
    """
    Computes pitting breakdown threshold Epit vs pH in presence of Cl-
    """
    base_epit = {
        "Fe": 0.45,
        "Cr": 0.85,
        "Ni": 0.55,
        "Ti": 1.85,
        "Al": -0.45,
        "Cu": 0.25,
        "Zn": -0.65,
        "Mg": -1.35
    }.get(element, 0.50)
    
    if chloride_ppm <= 0:
        return {"pittingActive": False, "pittingPotential_V_SHE": None, "points": []}
        
    cl_mol_l = (chloride_ppm * 1e-3) / CHLORIDE_MOLAR_MASS_G_MOL
    # Shift: delta_Epit = k * log10([Cl-] / 0.001 M)
    k_sensitivity = 0.088
    if element == "Al":
        k_sensitivity = 0.120
    elif element == "Ti":
        k_sensitivity = 0.020 # highly resistant
        
    delta_epit = k_sensitivity * math.log10(max(1e-5, cl_mol_l) / 1e-3)
    e_pit_she = base_epit - delta_epit
    
    pitting_line = []
    nernst_slope = calculate_nernst_slope(temperature_C)
    for ph_i in range(15):
        ph = float(ph_i)
        # Epit often slopes slightly with pH in passive regions
        e_val = e_pit_she - 0.02 * ph
        pitting_line.append({"pH": ph, "E_V_SHE": round(e_val, 3)})
        
    return {
        "pittingActive": True,
        "chloride_ppm": chloride_ppm,
        "chloride_Molar": round(cl_mol_l, 5),
        "nominal_Epit_V_SHE": round(e_pit_she, 3),
        "pittingThresholdLine": pitting_line
    }

def evaluate_point_mechanism(element, ph, e_she, temperature_C=25.0, ion_act_log10=-6.0, chloride_ppm=0.0):
    """
    Evaluates exact thermodynamic phase and identifies active corrosion mechanism for an (E, pH) point.
    """
    nernst = calculate_nernst_slope(temperature_C)
    e_her = 0.0 - nernst * ph
    e_oer = (1.229 - 0.000845 * (temperature_C + ZERO_CELSIUS_K - 298.15)) - nernst * ph
    
    # Calculate pitting potential
    pitting_data = calculate_chloride_pitting_boundary(element, temperature_C, chloride_ppm)
    e_pit = pitting_data.get("nominal_Epit_V_SHE")
    
    # Default variables
    regime = "Active Corrosion"
    dominant_species = "M²⁺(aq)"
    mechanism_id = "general_acid_dissolution"
    mechanism_title = "Active Acid Dissolution"
    mechanism_details = "Metallic dissolution with ionic discharge into aqueous electrolyte."
    risk_level = "Severe Corrosion"
    color = "#ef4444"
    depolarizer = "H⁺ (HER)" if e_she < e_her else ("O₂ (ORR)" if e_she < e_oer else "Anodic Overpotential")
    delta_imm = 0.0
    delta_pit = None if e_pit is None else round(e_pit - e_she, 3)
    
    if element == "Fe":
        e_imm = -0.440 + (nernst / 2.0) * ion_act_log10
        e_magnetite = -0.085 - nernst * ph
        e_passive_line = 0.728 - (nernst * 1.5) * ph
        delta_imm = round(e_she - e_imm, 3)
        
        if e_she < min(e_imm, e_magnetite):
            regime = "Immunity"
            dominant_species = "Fe(s) (Zero-Valence Metal)"
            mechanism_id = "cathodic_immunity"
            mechanism_title = "Cathodic Immunity Protection"
            mechanism_details = "Fe is thermodynamically immune to oxidation. No Faraday metal loss occurs."
            risk_level = "Immune"
            color = "#0284c7"
            if e_she < e_her - 0.35:
                mechanism_details += " Caution: Significant overpotential for Hydrogen Evolution Reaction (HER); check for Hydrogen Embrittlement (HE) / HIC risk."
        elif ph < 3.8 and e_she > e_imm and e_she < 1.8:
            regime = "Active Corrosion (Acid Dissolution)"
            dominant_species = "Fe²⁺ / Fe³⁺ (aq)"
            mechanism_id = "active_acid_attack"
            mechanism_title = "Active Acid Corrosion (Uniform Rusting)"
            mechanism_details = f"Spontaneous anodic oxidation: Fe → Fe²⁺ + 2e⁻ driven by {depolarizer} depolarization."
            risk_level = "Severe Corrosion"
            color = "#ef4444"
        elif ph > 13.0 and e_she > -0.7:
            regime = "Alkaline Corrosion"
            dominant_species = "HFeO₂⁻ (Hypoferrite Anion)"
            mechanism_id = "caustic_alkaline_attack"
            mechanism_title = "Alkaline Caustic Etching / Caustic Embrittlement"
            mechanism_details = "High-pH caustic dissolution forming soluble bihypoferrite HFeO₂⁻. High risk of Caustic Stress Corrosion Cracking (SCC)."
            risk_level = "High Risk"
            color = "#f97316"
        elif e_she > 1.8 - nernst * ph:
            regime = "Transpassive Dissolution"
            dominant_species = "FeO₄²⁻ (Ferryl VI Oxyanion)"
            mechanism_id = "transpassive_overoxidation"
            mechanism_title = "Transpassive Anodic Dissolution"
            mechanism_details = "Overpotential breaks the passive hematite film, oxidizing solid iron into highly soluble hexavalent FeO₄²⁻ ferryl ions."
            risk_level = "High Risk"
            color = "#e11d48"
        else:
            # Passive domain
            if e_pit is not None and e_she >= e_pit:
                regime = "Chloride Pitting Breakdown"
                dominant_species = "Fe²⁺ (Local Pit Anode) + Fe₂O₃ (Cathode Matrix)"
                mechanism_id = "chloride_pitting"
                mechanism_title = "Chloride-Induced Localized Pitting Attack"
                mechanism_details = f"Electrochemical potential ({e_she:.2f}V) exceeds pitting threshold Epit ({e_pit:.2f}V). Cl⁻ anions penetrate passive film to initiate autocatalytic crevice/pitting cells."
                risk_level = "Pitting Hazard"
                color = "#dc2626"
            else:
                regime = "Passivation (Oxide Barrier)"
                dominant_species = "Fe₂O₃ (Hematite) / Fe₃O₄ (Magnetite)"
                mechanism_id = "stable_passivation"
                mechanism_title = "Protective Passive Oxide Film"
                mechanism_details = "Spontaneous formation of dense, protective Fe₂O₃/Fe₃O₄ barrier film. Corrosion rate is stifled to negligible passivation current density."
                risk_level = "Stable Passivity"
                color = "#10b981"
                
    elif element == "Al":
        e_imm = -1.662 + (nernst / 3.0) * ion_act_log10
        delta_imm = round(e_she - e_imm, 3)
        if e_she < e_imm:
            regime = "Immunity"
            dominant_species = "Al(s)"
            mechanism_id = "cathodic_immunity"
            mechanism_title = "Cathodic Immunity"
            mechanism_details = "Al metal is thermodynamically immune."
            risk_level = "Immune"
            color = "#0284c7"
        elif ph < 4.0:
            regime = "Active Acid Corrosion"
            dominant_species = "Al³⁺ (aq)"
            mechanism_id = "acid_aluminate_corrosion"
            mechanism_title = "Acidic Active Dissolution"
            mechanism_details = f"Al → Al³⁺ + 3e⁻ active dissolution. Rapid hydrogen gas evolution ({depolarizer})."
            risk_level = "Severe Corrosion"
            color = "#ef4444"
        elif ph > 8.5:
            regime = "Alkaline Corrosion (Amphoteric Dissolution)"
            dominant_species = "AlO₂⁻ / Al(OH)₄⁻ (Aluminate)"
            mechanism_id = "amphoteric_caustic_attack"
            mechanism_title = "Amphoteric Caustic Dissolution"
            mechanism_details = "Hydroxide ions dissolve the alumina passive film: Al + 4OH⁻ → Al(OH)₄⁻ + 3e⁻."
            risk_level = "Severe Corrosion"
            color = "#f97316"
        else:
            if e_pit is not None and e_she >= e_pit:
                regime = "Chloride Pitting Breakdown"
                dominant_species = "Al³⁺ (Pits) + Al₂O₃·3H₂O"
                mechanism_id = "chloride_pitting"
                mechanism_title = "Severe Chloride Pitting Attack"
                mechanism_details = f"Potential exceeds Epit ({e_pit:.2f}V). Aggressive localized pitting in Al alloy matrix."
                risk_level = "Pitting Hazard"
                color = "#dc2626"
            else:
                regime = "Passivation (Al₂O₃ Barrier)"
                dominant_species = "Al₂O₃·3H₂O (Bayerite/Boehmite)"
                mechanism_id = "stable_passivation"
                mechanism_title = "Dense Barrier Alumina Passive Film"
                mechanism_details = "Dense self-healing ceramic alumina layer provides corrosion resistance."
                risk_level = "Stable Passivity"
                color = "#10b981"
                
    elif element == "Cr":
        e_imm = -0.913 + (nernst / 2.0) * ion_act_log10
        e_trans = 1.350 - (nernst * 1.33) * ph
        delta_imm = round(e_she - e_imm, 3)
        if e_she < e_imm:
            regime = "Immunity"
            dominant_species = "Cr(s)"
            mechanism_id = "cathodic_immunity"
            mechanism_title = "Cathodic Immunity"
            mechanism_details = "Cr is cathodically protected in zero-valence metallic state."
            risk_level = "Immune"
            color = "#0284c7"
        elif ph < 3.2 and e_she < 0.2:
            regime = "Active Acid Corrosion"
            dominant_species = "Cr²⁺ / Cr³⁺ (aq)"
            mechanism_id = "active_acid_attack"
            mechanism_title = "Active Acid Dissolution"
            mechanism_details = "Acidic dissolution of chromium into divalent/trivalent ions."
            risk_level = "Severe Corrosion"
            color = "#ef4444"
        elif e_she > e_trans:
            regime = "Transpassive Dissolution"
            dominant_species = "CrO₄²⁻ / Cr₂O₇²⁻ (Hexavalent Chromate)"
            mechanism_id = "transpassive_overoxidation"
            mechanism_title = "Transpassive Hexavalent Chromate Dissolution"
            mechanism_details = "Passive Cr₂O₃ oxidizes into highly soluble chromate/dichromate oxyanions."
            risk_level = "High Risk"
            color = "#e11d48"
        else:
            if e_pit is not None and e_she >= e_pit:
                regime = "Chloride Pitting Breakdown"
                dominant_species = "Cr³⁺ + Cr₂O₃"
                mechanism_id = "chloride_pitting"
                mechanism_title = "Pitting Breakdown in Chromia Barrier"
                mechanism_details = f"Chloride ions penetrate passive Cr₂O₃ above Epit ({e_pit:.2f}V)."
                risk_level = "Pitting Hazard"
                color = "#dc2626"
            else:
                regime = "Passivation (Cr₂O₃ Barrier)"
                dominant_species = "Cr₂O₃ (Chromia Passive Film)"
                mechanism_id = "stable_passivation"
                mechanism_title = "Ultra-Protective Chromia Passive Barrier"
                mechanism_details = "High-stability passive chromium(III) oxide film; standard stainless steel passivity."
                risk_level = "Stable Passivity"
                color = "#10b981"

    elif element == "Ti":
        e_imm = -1.630 + (nernst / 2.0) * ion_act_log10
        delta_imm = round(e_she - e_imm, 3)
        if e_she < e_imm:
            regime = "Immunity"
            dominant_species = "Ti(s)"
            mechanism_id = "cathodic_immunity"
            mechanism_title = "Cathodic Immunity"
            mechanism_details = "Metallic titanium immune region."
            risk_level = "Immune"
            color = "#0284c7"
        elif ph < 1.0 and e_she > 0.0:
            regime = "Active Acid Corrosion"
            dominant_species = "TiO²⁺ (Titanyl)"
            mechanism_id = "acid_titanyl_corrosion"
            mechanism_title = "Aggressive Non-Oxidizing Acid Attack"
            mechanism_details = "Dissolution into titanyl ions in concentrated reducing acids (e.g. concentrated HCl/H₂SO₄)."
            risk_level = "High Risk"
            color = "#ef4444"
        else:
            regime = "Passivation (TiO₂ Titania)"
            dominant_species = "TiO₂ (Rutile/Anatase)"
            mechanism_id = "stable_passivation"
            mechanism_title = "Immense Rutile/Anatase Passive Oxide Protection"
            mechanism_details = "Exceptionally dense, chemically inert TiO₂ barrier oxide. Practically immune to seawater chloride pitting."
            risk_level = "Stable Passivity"
            color = "#10b981"
            
    elif element == "Cu":
        e_imm = 0.342 + (nernst / 2.0) * ion_act_log10
        delta_imm = round(e_she - e_imm, 3)
        if e_she < 0.342 - nernst * ph and e_she < 0.471 - nernst * ph:
            regime = "Immunity"
            dominant_species = "Cu(s) (Metallic Copper)"
            mechanism_id = "cathodic_immunity"
            mechanism_title = "Thermodynamic Noble Immunity"
            mechanism_details = "Metallic copper is noble; immune to deaerated acid dissolution (E > E_HER)."
            risk_level = "Immune"
            color = "#0284c7"
        elif ph < 6.5 and e_she > 0.342:
            regime = "Active Acid Corrosion"
            dominant_species = "Cu²⁺ (aq)"
            mechanism_id = "aerated_acid_copper_corrosion"
            mechanism_title = "Oxygen-Reduction Driven Copper Dissolution"
            mechanism_details = "In presence of dissolved oxygen (ORR), Cu spontaneously dissolves into cupric Cu²⁺ ions."
            risk_level = "Severe Corrosion"
            color = "#ef4444"
        elif ph > 12.8:
            regime = "Alkaline Corrosion"
            dominant_species = "HCuO₂⁻ / CuO₂²⁻"
            mechanism_id = "caustic_alkaline_attack"
            mechanism_title = "Alkaline Cuprate Dissolution"
            mechanism_details = "Dissolution in concentrated alkaline caustic electrolytes forming soluble cuprate complexes."
            risk_level = "High Risk"
            color = "#f97316"
        else:
            regime = "Passivation (Cu₂O / CuO)"
            dominant_species = "Cu₂O (Cuprite) / CuO (Tenorite)"
            mechanism_id = "stable_passivation"
            mechanism_title = "Cuprite / Tenorite Passive Patina"
            mechanism_details = "Protective Cu₂O/CuO film (patina) formation stifling metal loss."
            risk_level = "Stable Passivity"
            color = "#10b981"
            
    elif element == "Zn":
        e_imm = -0.763 + (nernst / 2.0) * ion_act_log10
        delta_imm = round(e_she - e_imm, 3)
        if e_she < e_imm:
            regime = "Immunity"
            dominant_species = "Zn(s)"
            mechanism_id = "cathodic_immunity"
            mechanism_title = "Cathodic Immunity"
            mechanism_details = "Zinc metallic immunity state."
            risk_level = "Immune"
            color = "#0284c7"
        elif ph < 6.0:
            regime = "Active Acid Corrosion"
            dominant_species = "Zn²⁺ (aq)"
            mechanism_id = "active_acid_attack"
            mechanism_title = "Rapid Acidic Zinc Dissolution"
            mechanism_details = "Fast active dissolution: Zn → Zn²⁺ + 2e⁻ accompanied by hydrogen gas evolution."
            risk_level = "Severe Corrosion"
            color = "#ef4444"
        elif ph > 11.5:
            regime = "Alkaline Corrosion"
            dominant_species = "ZnO₂²⁻ / HZnO₂⁻ (Zincate)"
            mechanism_id = "caustic_alkaline_attack"
            mechanism_title = "Alkaline Zincate Dissolution"
            mechanism_details = "Zinc amphoteric dissolution in strong alkalis forming soluble zincates."
            risk_level = "High Risk"
            color = "#f97316"
        else:
            regime = "Passivation (ZnO / Zn(OH)₂)"
            dominant_species = "ZnO (Zincite) / Zn(OH)₂"
            mechanism_id = "stable_passivation"
            mechanism_title = "Zinc Oxide / Hydroxide Passivation"
            mechanism_details = "Protective zincite film passivation (typical of galvanized atmospheric exposure)."
            risk_level = "Stable Passivity"
            color = "#10b981"

    elif element == "Mg":
        e_imm = -2.372 + (nernst / 2.0) * ion_act_log10
        delta_imm = round(e_she - e_imm, 3)
        if e_she < e_imm:
            regime = "Immunity"
            dominant_species = "Mg(s)"
            mechanism_id = "cathodic_immunity"
            mechanism_title = "Cathodic Immunity"
            mechanism_details = "Metallic magnesium immunity (requires extreme cathodic polarization)."
            risk_level = "Immune"
            color = "#0284c7"
        elif ph < 10.5:
            regime = "Active Acid / Neutral Corrosion"
            dominant_species = "Mg²⁺ (aq)"
            mechanism_id = "intense_her_galvanic_attack"
            mechanism_title = "Aggressive Self-Dissolution & Negative Difference Effect"
            mechanism_details = "Extreme thermodynamic drive for Mg → Mg²⁺ + 2e⁻ with vigorous hydrogen evolution even in neutral water."
            risk_level = "Severe Corrosion"
            color = "#ef4444"
        else:
            regime = "Passivation (Mg(OH)₂ Brucite)"
            dominant_species = "Mg(OH)₂ (Brucite)"
            mechanism_id = "stable_passivation"
            mechanism_title = "Brucite Alkaline Passivation"
            mechanism_details = "Precipitation of protective Mg(OH)₂ layer in alkaline environments (pH > 10.5)."
            risk_level = "Stable Passivity"
            color = "#10b981"

    else: # Default Ni / other
        e_imm = -0.257 + (nernst / 2.0) * ion_act_log10
        delta_imm = round(e_she - e_imm, 3)
        if e_she < e_imm:
            regime = "Immunity"
            dominant_species = "Ni(s)"
            mechanism_id = "cathodic_immunity"
            mechanism_title = "Cathodic Immunity"
            mechanism_details = "Metallic nickel immunity state."
            risk_level = "Immune"
            color = "#0284c7"
        elif ph < 6.8 and e_she > e_imm and e_she < 1.6:
            regime = "Active Acid Corrosion"
            dominant_species = "Ni²⁺ (aq)"
            mechanism_id = "active_acid_attack"
            mechanism_title = "Active Nickel Dissolution"
            mechanism_details = "Anodic dissolution into Ni²⁺ in acidic solutions."
            risk_level = "Severe Corrosion"
            color = "#ef4444"
        else:
            regime = "Passivation (NiO / Ni(OH)₂)"
            dominant_species = "NiO / Ni(OH)₂ (s)"
            mechanism_id = "stable_passivation"
            mechanism_title = "Nickel Oxide / Hydroxide Passive Barrier"
            mechanism_details = "Formation of stable, protective NiO/Ni(OH)₂ passive film."
            risk_level = "Stable Passivity"
            color = "#10b981"
            
    # Generate tailored engineering mitigation recommendations
    mitigations = []
    if regime.startswith("Active Acid"):
        mitigations.append("Apply Cathodic Protection (CP) to depress potential below immunity boundary (E < " + str(round(e_she - delta_imm, 2)) + " V vs SHE).")
        mitigations.append("Add anodic passivation inhibitors (e.g. chromates, nitrites, molybdates) or neutralizers to shift pH > 7.0.")
    elif regime.startswith("Chloride Pitting"):
        mitigations.append(f"Chloride concentration ({chloride_ppm} ppm) breaches Epit. Upgrade to higher PREN alloy (e.g., Duplex 2205 or Super Austenitic 254SMO).")
        mitigations.append("Deaerate electrolyte to lower Mixed Corrosion Potential (Ecorr) safely below Epit.")
    elif regime.startswith("Alkaline"):
        mitigations.append("Buffer pH down to neutral regime (pH 6 - 9) to prevent amphoteric/caustic dissolution.")
        mitigations.append("Inspect for Caustic Stress Corrosion Cracking (SCC) in weld heat-affected zones.")
    elif regime.startswith("Transpassive"):
        mitigations.append("Reduce oxidizer concentration or eliminate stray anodic currents to prevent transpassive breakdown.")
    elif regime.startswith("Immunity"):
        if e_she < e_her - 0.3:
            mitigations.append("Reduce CP over-polarization to avoid hydrogen evolution and atomic hydrogen embrittlement.")
        else:
            mitigations.append("Maintain current cathodic polarization settings for 100% corrosion protection.")
    else:
        mitigations.append("Conditions maintain a stable passive barrier. Monitor pH and chloride levels to avoid sudden local acidification.")

    return {
        "regime": regime,
        "dominantSpecies": dominant_species,
        "mechanismId": mechanism_id,
        "mechanismTitle": mechanism_title,
        "mechanismDetails": mechanism_details,
        "riskLevel": risk_level,
        "color": color,
        "depolarizer": depolarizer,
        "deltaE_Immunity_V": delta_imm,
        "deltaE_Pitting_V": delta_pit,
        "isInsideWaterStability": (e_she >= e_her and e_she <= e_oer),
        "e_HER_V_SHE": round(e_her, 3),
        "e_OER_V_SHE": round(e_oer, 3),
        "engineeringMitigations": mitigations
    }

def solve_pourbaix_diagram(element="Fe", temperature_C=25.0, ion_activity_log10=-6.0, chloride_ppm=0.0, experimental_points=None):
    """
    Solves 2D Pourbaix E-pH equilibrium boundaries, water stability limits,
    and overlays user measured experimental test data to classify active corrosion mechanisms.
    """
    start_time = time.perf_counter()
    if not isinstance(element, str) or element not in POURBAIX_ELEMENT_SYSTEMS:
        # Phase 6a: no silent substitution of the Fe system for an unknown element.
        supported = list(POURBAIX_ELEMENT_SYSTEMS)
        raise ValidationError(
            UNKNOWN_ELEMENT, "element",
            f"No Pourbaix system for element {element!r}; supported: {', '.join(supported)}.",
            {"element": repr(element), "supported": supported},
        )
    sys_data = POURBAIX_ELEMENT_SYSTEMS[element]
    nernst_slope = calculate_nernst_slope(temperature_C)
    
    # 1. Water stability boundaries
    water_stability = generate_water_stability_lines(temperature_C)
    
    # 2. Chloride Pitting boundary
    pitting_boundary = calculate_chloride_pitting_boundary(element, temperature_C, chloride_ppm)
    
    # 3. 2D Stability Field Grid (for smooth rendering / surface plots)
    stability_grid = []
    for p_idx in range(15): # pH 0 to 14
        ph = float(p_idx)
        for e_idx in range(21): # E -2.0 to +2.0 V (0.2V step)
            e_she = -2.0 + e_idx * 0.2
            point_eval = evaluate_point_mechanism(element, ph, e_she, temperature_C, ion_activity_log10, chloride_ppm)
            stability_grid.append({
                "pH": ph,
                "E_V_SHE": round(e_she, 2),
                "regime": point_eval["regime"],
                "dominantSpecies": point_eval["dominantSpecies"],
                "mechanismTitle": point_eval["mechanismTitle"],
                "color": point_eval["color"]
            })
            
    # 4. Analytical Phase Boundaries Lines
    analytical_boundaries = []
    for rxn in sys_data["reactions"]:
        rxn_type = rxn["type"]
        line_points = []
        if rxn_type == "redox":
            e_val = rxn["e0"] + (nernst_slope / 2.0) * ion_activity_log10
            for ph_i in range(15):
                line_points.append({"pH": float(ph_i), "E_V_SHE": round(e_val, 4)})
        elif rxn_type in ["redox_ph", "transpassive"]:
            e0_adj = rxn["e0"]
            slope_adj = rxn.get("slope_pH", -0.0592)
            for ph_i in range(15):
                ph_v = float(ph_i)
                e_val = e0_adj + slope_adj * ph_v
                line_points.append({"pH": ph_v, "E_V_SHE": round(e_val, 4)})
        elif rxn_type in ["hydrolysis", "acid_dissolution", "alkaline_dissolution"]:
            ph_trans = rxn.get("pH_trans", 7.0)
            for e_step in range(9): # -2.0 to +2.0
                e_v = -2.0 + e_step * 0.5
                line_points.append({"pH": ph_trans, "E_V_SHE": e_v})
                
        analytical_boundaries.append({
            "id": rxn["id"],
            "name": rxn["name"],
            "equation": rxn["equation"],
            "boundaryType": rxn.get("boundaryType", "Phase Boundary"),
            "speciesA": rxn.get("speciesA", ""),
            "speciesB": rxn.get("speciesB", ""),
            "points": line_points
        })
        
    # 5. Process Experimental Points Overlay
    analyzed_experimental_points = []
    risk_breakdown = {
        "Immune": 0,
        "Stable Passivity": 0,
        "Caution": 0,
        "Pitting Hazard": 0,
        "Severe Corrosion": 0,
        "High Risk": 0
    }
    
    if experimental_points and isinstance(experimental_points, list):
        for idx, pt in enumerate(experimental_points):
            pt_id = pt.get("id", f"exp_pt_{idx+1}")
            pt_name = pt.get("name", f"Test Point #{idx+1}")
            ph_val = float(pt.get("ph", pt.get("pH", 7.0)))
            pot_input = float(pt.get("potential_V", pt.get("potential", pt.get("E_V", 0.0))))
            ref_elec = pt.get("refElectrode", "SHE")
            ref_offset = REF_ELECTRODE_OFFSETS.get(ref_elec, 0.0)
            
            # Convert measured potential to E vs SHE
            e_she = pot_input + ref_offset
            
            # Mechanism evaluation
            eval_res = evaluate_point_mechanism(
                element, ph_val, e_she, temperature_C, ion_activity_log10, chloride_ppm
            )
            
            risk_level = eval_res["riskLevel"]
            risk_breakdown[risk_level] = risk_breakdown.get(risk_level, 0) + 1
            
            analyzed_experimental_points.append({
                "id": pt_id,
                "name": pt_name,
                "pH": ph_val,
                "potential_Input_V": pot_input,
                "refElectrode": ref_elec,
                "potential_V_SHE": round(e_she, 4),
                "currentDensity_uA_cm2": pt.get("currentDensity_uA_cm2", pt.get("i_corr", None)),
                "timeHours": pt.get("timeHours", None),
                "stageName": pt.get("stageName", f"Stage {idx+1}"),
                "notes": pt.get("notes", ""),
                "regime": eval_res["regime"],
                "dominantSpecies": eval_res["dominantSpecies"],
                "mechanismId": eval_res["mechanismId"],
                "mechanismTitle": eval_res["mechanismTitle"],
                "mechanismDetails": eval_res["mechanismDetails"],
                "riskLevel": eval_res["riskLevel"],
                "color": eval_res["color"],
                "depolarizer": eval_res["depolarizer"],
                "deltaE_Immunity_V": eval_res["deltaE_Immunity_V"],
                "deltaE_Pitting_V": eval_res["deltaE_Pitting_V"],
                "isInsideWaterStability": eval_res["isInsideWaterStability"],
                "engineeringMitigations": eval_res["engineeringMitigations"]
            })
            
    # Trajectory Synthesis Diagnosis
    trajectory_diagnosis = "No experimental data provided."
    if analyzed_experimental_points:
        total_pts = len(analyzed_experimental_points)
        severe_count = risk_breakdown["Severe Corrosion"] + risk_breakdown["Pitting Hazard"] + risk_breakdown["High Risk"]
        pass_count = risk_breakdown["Stable Passivity"]
        immune_count = risk_breakdown["Immune"]
        
        if severe_count == 0 and pass_count > 0:
            trajectory_diagnosis = f"OPTIMAL PASSIVE STATE: All {total_pts} measured test points reside securely inside the protective passive oxide boundary. Metal degradation rate is stifled by a dense barrier film."
        elif severe_count == 0 and immune_count == total_pts:
            trajectory_diagnosis = f"COMPLETE CATHODIC IMMUNITY: All {total_pts} test points operate at potentials below the Nernst equilibrium dissolution limit. Zero Faraday metal loss occurs."
        elif risk_breakdown["Pitting Hazard"] > 0:
            pitting_pts = [p["name"] for p in analyzed_experimental_points if p["riskLevel"] == "Pitting Hazard"]
            trajectory_diagnosis = f"CRITICAL PITTING HAZARD: {len(pitting_pts)} measured point(s) ({', '.join(pitting_pts[:3])}) exceed the chloride pitting breakdown potential (Epit). Localized autocatalytic pitting is thermodynamically favored."
        elif risk_breakdown["Severe Corrosion"] > 0:
            corrosive_pts = [p["name"] for p in analyzed_experimental_points if p["riskLevel"] == "Severe Corrosion"]
            trajectory_diagnosis = f"ACTIVE DISSOLUTION DETECTED: {len(corrosive_pts)} test point(s) ({', '.join(corrosive_pts[:3])}) are located in the active acid corrosion domain with rapid uniform metal loss driven by cathodic depolarization."
        else:
            trajectory_diagnosis = f"MIXED REGIME EXPOSURE: Experimental trajectory traverses across multiple thermodynamic domains ({severe_count} hazardous points, {pass_count} passivated, {immune_count} immune)."

    compute_time_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    return {
        "success": True,
        "engine": "MetalliX-Python-HPC-Pourbaix-v3.10",
        "computeTimeMs": compute_time_ms,
        "element": element,
        "systemName": sys_data["name"],
        "parameters": {
            "temperature_C": temperature_C,
            "nernstSlope_V_pH": round(nernst_slope, 5),
            "ionActivity_log10": ion_activity_log10,
            "chlorideConcentration_ppm": chloride_ppm,
            "chloride_Molar": pitting_boundary.get("chloride_Molar", 0.0),
            "pittingPotential_V_SHE": pitting_boundary.get("nominal_Epit_V_SHE"),
            "pittingRisk": "High Pitting Risk" if chloride_ppm > 500 else ("Moderate Localized Attack" if chloride_ppm > 0 else "Low (Chloride Free)")
        },
        "waterStabilityLines": water_stability,
        "chloridePittingBoundary": pitting_boundary,
        "analyticalBoundaries": analytical_boundaries,
        "speciesInventory": sys_data["species"],
        "stabilityFieldGrid": stability_grid,
        "experimentalOverlay": {
            "totalPointsCount": len(analyzed_experimental_points),
            "riskBreakdown": risk_breakdown,
            "overallTrajectoryDiagnosis": trajectory_diagnosis,
            "points": analyzed_experimental_points
        },
        # Phase 6a provenance (constants version and the R/F values actually used)
        "provenance": {
            "constantsVersion": physical_constants.CONSTANTS_VERSION,
            "gasConstantR_J_molK": R_GAS,
            "faraday_C_mol": F_FARADAY,
            "constantsNote": "CODATA printed truncations of R and F (pre-migration values); "
                             "exact SI values are pending the Phase 6a value step.",
        },
    }

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        print(json.dumps({
            "status": "ready",
            "engine": "MetalliX Python Pourbaix E-pH Stability & Experimental Overlay Solver",
            "capabilities": [
                "Multi-Element Nernst Equilibria (Fe, Cr, Ni, Ti, Al, Cu, Zn, Mg)",
                "Water Stability Line A & B (HER & OER)",
                "Analytical Reaction Lines & Exact Polygons",
                "Chloride Pitting Breakdown Boundary (Epit)",
                "Experimental E-pH Test Data Overlay & Trajectory Tracking",
                "Automated Corrosion Mechanism Identification & Mitigation Rules"
            ]
        }))
        sys.exit(0)
        
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            print(json.dumps({"error": "Empty stdin payload", "errorKind": "internal"}))
            sys.exit(1)
            
        data = json.loads(raw_input)
        el = data.get("element", "Fe")
        temp = float(data.get("temperature_C", 25.0))
        act = float(data.get("ionActivity_log10", -6.0))
        cl_ppm = float(data.get("chloride_ppm", 0.0))
        exp_pts = data.get("experimentalPoints", data.get("points", []))
        
        result = solve_pourbaix_diagram(el, temp, act, cl_ppm, exp_pts)
        print(json.dumps(result))
    except ValidationError as e:
        # Phase 6a envelope: invalid input, not a solver failure (HTTP 422 in the bridge).
        print(json.dumps(validation_envelope(e)))
        sys.exit(2)
    except Exception as e:
        print(json.dumps({"error": str(e), "errorKind": "internal"}))
        sys.exit(1)
