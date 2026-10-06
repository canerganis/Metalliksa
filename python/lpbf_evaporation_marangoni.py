"""Boiling cap and isotropic liquid-conductivity multiplier for the LPBF reference transient.

This is NOT an evaporation model. With ``evaporationModel=True`` the transient:

1. multiplies the liquid-phase conductivity by ``1 + (lambda - 1) * f_liq`` (an isotropic
   surrogate for melt-pool convection; the default lambda = 2.2 is an estimated, uncited knob
   that the archived V1 input carries), and
2. above the boiling enthalpy clips the inverted temperature at ``T_boil`` and keeps the excess
   enthalpy in the cell. Nothing leaves the domain: no mass flux, no latent-heat sink, no recoil.
   The returned "vapor fraction" ``excess_h / L_v`` is a diagnostic proxy, not a mass loss, and
   it is not conserved. Such a run is labelled "boiling-capped" and carries a ``boilingCap``
   block in the result (``isReferenceSolution: false``, ``isEvaporationModel: false``): it is labelled
   as not a reference solution and not an evaporation model.

The former ``langmuir_evaporation_flux`` helper was never called by any solver and was removed
so that this module does not advertise physics the transient does not solve.
"""

import numpy as np


def calculate_keff_marangoni(k_base, liquid_fraction, lambda_marangoni=2.2):
    """Effective conductivity ``k_base * (1 + (lambda - 1) * clip(f_liq, 0, 1))``.

    Isotropic surrogate for convective mixing in the melt (estimated, uncited; lambda >= 1).
    """
    if lambda_marangoni < 1.0:
        raise ValueError("Marangoni enhancement factor must be >= 1.0")
    enhancement = 1.0 + (lambda_marangoni - 1.0) * np.clip(liquid_fraction, 0.0, 1.0)
    return k_base * enhancement


def invert_enthalpy_with_boiling_cap(h_array, h_table, t_table, boiling_k, latent_heat_vap_j_kg):
    """Invert specific enthalpy to temperature, capping T at ``boiling_k``.

    Returns ``(T, vapor_fraction_proxy)``: T is the table inversion of ``min(h, h_boil)``, so
    cells above the boiling enthalpy report exactly ``boiling_k``; the proxy is
    ``clip((h - h_boil) / L_v, 0, 1)`` and only measures how far the cap was exceeded. The
    excess enthalpy stays in the cell and conducts back later; no energy or mass is removed.
    """
    h_boil = float(np.interp(boiling_k, t_table, h_table))
    T = np.interp(np.minimum(h_array, h_boil), h_table, t_table)
    excess_h = np.maximum(0.0, h_array - h_boil)
    vapor_fraction_proxy = np.clip(excess_h / latent_heat_vap_j_kg, 0.0, 1.0)
    return T, vapor_fraction_proxy
