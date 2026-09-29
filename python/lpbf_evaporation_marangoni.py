"""Evaporation heat sink and Marangoni effective conductivity (k_eff) for LPBF.

Solves the 280 W boiling lock by incorporating:
1. Liquid-phase Marangoni convective enhancement: k_eff = lambda_marangoni * k_L
   (DebRoy et al. 2018, Paul et al. 2014; lambda in 2.0..2.5 range).
2. Evaporative latent heat buffering and Langmuir mass vaporization:
   q_evap = j_evap * L_v, where excess thermal energy above boiling enthalpy
   is consumed by vaporization latent heat rather than triggering non-physical runaway.
"""

import math
import numpy as np

# Universal gas constant [J/(mol K)]
R_GAS = 8.314462618


def calculate_keff_marangoni(k_base, liquid_fraction, lambda_marangoni=2.2):
    """Calculate effective thermal conductivity accounting for Marangoni melt circulation.
    
    Parameters:
        k_base: Base thermal conductivity (array or scalar) [W/(m K)]
        liquid_fraction: Molten fraction [0, 1] (array or scalar)
        lambda_marangoni: Convective multiplier for pure liquid phase (default 2.2)
        
    Returns:
        k_eff: Enhanced thermal conductivity [W/(m K)]
    """
    if lambda_marangoni < 1.0:
        raise ValueError("Marangoni enhancement factor must be >= 1.0")
    enhancement = 1.0 + (lambda_marangoni - 1.0) * np.clip(liquid_fraction, 0.0, 1.0)
    return k_base * enhancement


def langmuir_evaporation_flux(temperature_k, boiling_k, molar_mass_kg_mol,
                              latent_heat_vap_j_kg, sticking_coeff=0.82):
    """Calculate mass vaporization flux [kg/(m^2 s)] via Langmuir Hertz-Knudsen relation.
    
    Parameters:
        temperature_k: Surface temperature [K]
        boiling_k: Normal boiling temperature at 1 atm [K]
        molar_mass_kg_mol: Molar mass [kg/mol] (e.g. 0.0587 for IN718/IN625)
        latent_heat_vap_j_kg: Latent heat of vaporization [J/kg] (e.g. 6.4e6)
        sticking_coeff: Condensation/evaporation accommodation factor (0.82 typical)
        
    Returns:
        j_evap: Mass loss flux [kg/(m^2 s)]
        q_evap: Evaporation heat sink flux [W/m^2]
    """
    if temperature_k < 0.7 * boiling_k:
        return 0.0, 0.0
    
    t = float(temperature_k)
    p_atm = 101325.0  # Pa
    # Clausius-Clapeyron saturation pressure
    exponent = (latent_heat_vap_j_kg * molar_mass_kg_mol / R_GAS) * (1.0 / boiling_k - 1.0 / t)
    # Clip exponent to prevent overflow
    exponent = min(exponent, 50.0)
    p_sat = p_atm * math.exp(exponent)
    
    # Langmuir vaporization rate
    # j = sticking_coeff * p_sat * sqrt(M / (2 * pi * R * T))
    j_evap = sticking_coeff * p_sat * math.sqrt(molar_mass_kg_mol / (2.0 * math.pi * R_GAS * t))
    q_evap = j_evap * latent_heat_vap_j_kg
    return j_evap, q_evap


def invert_enthalpy_with_evaporation(h_array, h_table, t_table, boiling_k, latent_heat_vap_j_kg):
    """Invert specific enthalpy to temperature with evaporative latent heat buffering.
    
    Prevents artificial solver explosion at high powers (e.g. 280 W NIST Case 0).
    When specific enthalpy exceeds boiling enthalpy h_boil, temperature is capped
    at T_boil and the excess energy enters vapor latent phase buffering:
    h = h_boil + f_vap * L_vap.
    
    Parameters:
        h_array: Specific enthalpy array [J/kg]
        h_table: 1D monotonic enthalpy points [J/kg]
        t_table: Corresponding temperature points [K]
        boiling_k: Material boiling temperature [K]
        latent_heat_vap_j_kg: Vaporization latent heat [J/kg]
        
    Returns:
        T: Inverted temperature array [K]
        vapor_fraction: Fraction of mass vaporized in cell [0, 1]
    """
    h_boil = float(np.interp(boiling_k, t_table, h_table))
    
    # Standard interpolation where h <= h_boil
    T = np.interp(np.minimum(h_array, h_boil), h_table, t_table)
    
    # Excess enthalpy above boiling converted to vapor fraction
    excess_h = np.maximum(0.0, h_array - h_boil)
    vapor_fraction = np.clip(excess_h / latent_heat_vap_j_kg, 0.0, 1.0)
    
    return T, vapor_fraction
