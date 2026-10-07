"""Sourced evaporation constants per alloy and the Hertz-Knudsen-Langmuir heat sink.

Every number here carries its source. Nothing is estimated from memory.

Sources (Crossref-verified DOIs, 2026-10-07):
- [KIM75]   C. S. Kim, "Thermophysical properties of stainless steels", ANL-75-55 (1975),
            DOI 10.2172/4152287. 316L: heat of vaporization 1770 cal/g by elemental additivity
            (p. 3-4), boiling point 3090 K from the vapour-pressure fit log10 P[atm] = 6.1127 - 18868/T
            (Eq. 14, p. 7).
- [GAN21]   Z. Gan et al., "Universal scaling laws of keyhole stability and porosity in 3D printing
            of metals", Nat. Commun. 12 (2021) 2379, DOI 10.1038/s41467-021-22704-0.
            SI Supplementary Table 1: Ti64 T_v 3560 K, L_v 9.255e6 J/kg, M_l 48 g/mol;
            SS316 T_v 3122 K, L_v 6.336e6 J/kg, M_l 56 g/mol. SI Supplementary Table 2:
            retro-diffusion coefficient beta_R = 0.18. SI Eq. (12): m_dot = (1-beta_R) sqrt(M/(2 pi R T)) P_sat;
            SI Eq. (13): P_sat = P_atm exp[M L_v/(R T_v) (1 - T_v/T)]; SI Eq. (31): P_evaporate = integral L_v m_dot dS.
- [FAB20]   R. Fabbro, "Depth dependence and keyhole stability at threshold, for different laser
            welding regimes", Appl. Sci. 10 (2020) 1487, DOI 10.3390/app10041487. Appendix A Eqs.
            (A11)-(A12): the same Clausius-Clapeyron / modified-Langmuir pair, with (1 - beta), beta = 0.2,
            citing Knight 1979 (AIAA J. 17, 519) and Anisimov. Used as the cross-check of [GAN21]'s form.
- [KNA19]   G. L. Knapp et al., "Experiments and simulations on solidification microstructure for
            Inconel 718 in powder bed fusion electron beam additive manufacturing", Addit. Manuf. 25
            (2019) 511-521, DOI 10.1016/j.addma.2018.12.001. Table 1: IN718 boiling point 3120 K.
            Table 3: IN718 composition (wt.%) and elemental boiling points (K) / heats of vaporization
            (kJ/mol) used for the Langmuir vaporization heat loss (their refs [37], [40]).
- [LAS17]   E. A. Lass et al., "Formation of the Ni3Nb delta-phase in stress-relieved Inconel 625 produced
            via laser powder-bed fusion additive manufacturing", Metall. Mater. Trans. A 48 (2017),
            DOI 10.1007/s11661-017-4304-6. Table I: IN625 powder feedstock composition (mass fraction).
- Atomic masses: IUPAC conventional values (CIAAW), rounded to 0.01 g/mol.

Derived (stated as derived, not measured):
- IN718 and IN625 L_v [J/kg] and mean molar mass [kg/mol] are mass-weighted additivity sums over the
  cited composition and the [KNA19] Table 3 elemental data (the same additivity rule [KIM75] used for
  316L). IN625 boiling point: temperature at which the Raoult-ideal mixture pressure
  sum_i x_i P_i(T) reaches 1 atm, with each elemental P_i(T) a Clausius-Clapeyron curve anchored at
  (T_b,i, 1 atm) with the [KNA19] heat of vaporization. The same procedure applied to IN718 and
  316L is reported next to the published [KNA19] 3120 K / [KIM75] 3090 K as a check of the method.
"""
from __future__ import annotations

import math

R_GAS = 8.314  # J/(mol K)  [GAN21] SI Table 2
P_ATM = 1.0e5  # Pa         [GAN21] SI Table 2 (P_atm = 1e5 Pa); [FAB20] P0 = 1e5 Pa
BETA_R = 0.18  # retro-diffusion (recondensation) coefficient, [GAN21] SI Table 2 (Knight 1979 / Anisimov)
CAL_TO_J = 4.184

# IUPAC conventional atomic weights, g/mol
ATOMIC_MASS_G_MOL = {"Ni": 58.69, "Cr": 52.00, "Fe": 55.85, "Mo": 95.95, "Nb": 92.91, "Ti": 47.87,
                     "Al": 26.98, "Co": 58.93, "Mn": 54.94, "Cu": 63.55, "Si": 28.09, "V": 50.94}

# [KNA19] Table 3: element -> (boiling point K, heat of vaporization kJ/mol); verified on the PDF page image.
KNAPP_TABLE3_ELEMENTS = {
    "Ti": (3558.0, 425.8), "Al": (2793.0, 290.9), "Fe": (3133.0, 340.4), "Cr": (2945.0, 342.1),
    "Ni": (3183.0, 374.3), "Mn": (2333.0, 231.1), "Cu": (2833.0, 304.8), "Si": (3543.0, 384.8),
    "Mo": (4883.0, 590.3), "Nb": (5013.0, 683.7), "Co": (2930.0, 375.0),
}
# [KNA19] Table 3 composition, wt.%
IN718_COMPOSITION_WT = {"Ti": 0.90, "Al": 0.50, "Fe": 16.85, "Cr": 19.0, "Ni": 52.5, "Mn": 0.35,
                        "Cu": 0.30, "Si": 0.35, "Mo": 3.05, "Nb": 5.20, "Co": 1.00}
# [LAS17] Table I, mass fraction x 100 (Ni balance; C, P, S < 0.02 % dropped: no elemental data)
IN625_COMPOSITION_WT = {"Cr": 20.70, "Mo": 8.83, "Nb": 3.75, "Fe": 0.72, "Ti": 0.35, "Al": 0.28,
                        "Co": 0.18, "Mn": 0.03, "Si": 0.13}
IN625_COMPOSITION_WT["Ni"] = 100.0 - sum(IN625_COMPOSITION_WT.values())
# [KIM75] p. 3: Type 316L taken as 69 % Fe, 17 % Cr, 12 % Ni, 2 % Mo by weight
SS316L_COMPOSITION_WT_KIM = {"Fe": 69.0, "Cr": 17.0, "Ni": 12.0, "Mo": 2.0}


def additivity(composition_wt):
    """Mass-weighted L_v [J/kg] and harmonic-mean molar mass [kg/mol] from elemental data ([KIM75] rule)."""
    total = sum(composition_wt.values())
    lv = 0.0
    inv_m = 0.0
    for el, wt in composition_wt.items():
        w = wt / total
        tb, dh_kj_mol = KNAPP_TABLE3_ELEMENTS[el]
        m_kg_mol = ATOMIC_MASS_G_MOL[el] * 1e-3
        lv += w * dh_kj_mol * 1e3 / m_kg_mol
        inv_m += w / m_kg_mol
    return lv, 1.0 / inv_m


def mole_fractions(composition_wt):
    moles = {el: wt / ATOMIC_MASS_G_MOL[el] for el, wt in composition_wt.items()}
    s = sum(moles.values())
    return {el: n / s for el, n in moles.items()}


def elemental_psat(el, T):
    """Clausius-Clapeyron curve of one element anchored at (T_b,i, 1 atm) with the [KNA19] dH_vap."""
    tb, dh_kj_mol = KNAPP_TABLE3_ELEMENTS[el]
    return P_ATM * math.exp(dh_kj_mol * 1e3 / R_GAS * (1.0 / tb - 1.0 / T))


def raoult_boiling_point(composition_wt, lo=1500.0, hi=6000.0):
    """T at which sum_i x_i P_i(T) = 1 atm (ideal-solution estimate; bisection)."""
    x = mole_fractions(composition_wt)

    def excess(T):
        return sum(xi * elemental_psat(el, T) for el, xi in x.items()) - P_ATM

    if excess(lo) > 0 or excess(hi) < 0:
        raise ValueError("Raoult boiling point not bracketed")
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if excess(mid) > 0:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def alloy_evaporation_constants(material_name):
    """Return dict(T_b_K, L_v_J_kg, M_kg_mol, beta_R, sources, derivation) for the four alloys."""
    name = material_name.strip().lower()
    if "316" in name:
        # Primary: one consistent source ([GAN21] SI Table 1 SS316). [KIM75] gives T_b 3090 K (1 % lower) and
        # L_v 1770 cal/g = 7.41e6 J/kg (17 % higher); the [KNA19]-elemental additivity over Kim's own 316L
        # composition gives 6.21e6 J/kg, i.e. two of three sources agree near 6.3e6. Kim is the recorded
        # alternative (sensitivity not run in this pass).
        return dict(alloy="316L", T_b_K=3122.0, L_v_J_kg=6.336e6, M_kg_mol=56e-3, beta_R=BETA_R,
                    sources={"T_b_K": "[GAN21] SI Table 1 SS316 T_v = 3122 K",
                             "L_v_J_kg": "[GAN21] SI Table 1 SS316 L_v = 6.336e6 J/kg",
                             "M_kg_mol": "[GAN21] SI Table 1 SS316 M_l = 56 g/mol",
                             "beta_R": "[GAN21] SI Table 2 (Knight 1979 / Anisimov)"},
                    alternative={"T_b_K": 3090.0, "L_v_J_kg": 1770.0 * CAL_TO_J * 1e3,
                                 "source": "[KIM75] Eq. 14 (3090 K) and 1770 cal/g additivity (not run)"},
                    derivation="direct")
    if "ti" in name and "6al" in name.replace("-", "") or "ti64" in name.replace("-", ""):
        return dict(alloy="Ti-6Al-4V", T_b_K=3560.0, L_v_J_kg=9.255e6, M_kg_mol=48e-3, beta_R=BETA_R,
                    sources={"T_b_K": "[GAN21] SI Table 1 Ti64 T_v", "L_v_J_kg": "[GAN21] SI Table 1 Ti64 L_v",
                             "M_kg_mol": "[GAN21] SI Table 1 Ti64 M_l", "beta_R": "[GAN21] SI Table 2"},
                    derivation="direct")
    if "718" in name:
        lv, m = additivity(IN718_COMPOSITION_WT)
        return dict(alloy="IN718", T_b_K=3120.0, L_v_J_kg=lv, M_kg_mol=m, beta_R=BETA_R,
                    sources={"T_b_K": "[KNA19] Table 1 boiling point 3120 K",
                             "L_v_J_kg": "mass-weighted additivity of [KNA19] Table 3 dH_vap over the [KNA19] Table 3 composition",
                             "M_kg_mol": "harmonic mean over the [KNA19] Table 3 composition (IUPAC atomic masses)",
                             "beta_R": "[GAN21] SI Table 2"},
                    derivation="additivity",
                    raoult_T_b_check_K=raoult_boiling_point(IN718_COMPOSITION_WT))
    if "625" in name:
        lv, m = additivity(IN625_COMPOSITION_WT)
        return dict(alloy="IN625", T_b_K=raoult_boiling_point(IN625_COMPOSITION_WT), L_v_J_kg=lv, M_kg_mol=m,
                    beta_R=BETA_R,
                    sources={"T_b_K": "Raoult-ideal mixture of [KNA19] Table 3 elemental Clausius-Clapeyron curves over the [LAS17] Table I composition (derived estimate)",
                             "L_v_J_kg": "mass-weighted additivity of [KNA19] Table 3 dH_vap over the [LAS17] Table I composition",
                             "M_kg_mol": "harmonic mean over the [LAS17] Table I composition (IUPAC atomic masses)",
                             "beta_R": "[GAN21] SI Table 2"},
                    derivation="additivity+raoult")
    raise ValueError(f"no sourced evaporation constants for {material_name!r}; nothing is substituted")


def method_checks():
    """Raoult boiling points of IN718 and 316L vs the published values (method check, reported in RESULTS)."""
    return {"IN718_raoult_K": raoult_boiling_point(IN718_COMPOSITION_WT), "IN718_published_K": 3120.0,
            "316L_raoult_K": raoult_boiling_point(SS316L_COMPOSITION_WT_KIM), "316L_published_K": 3090.0,
            "316L_additivity_L_v_J_kg": additivity(SS316L_COMPOSITION_WT_KIM)[0],
            "316L_published_L_v_J_kg": 1770.0 * CAL_TO_J * 1e3}


def saturation_pressure(T, c):
    """[GAN21] SI Eq. 13 / [FAB20] Eq. A11: P_sat = P_atm exp[M L_v/(R T_b) (1 - T_b/T)]. T may be an array."""
    import numpy as np
    T = np.asarray(T, dtype=float)
    return P_ATM * np.exp(c["M_kg_mol"] * c["L_v_J_kg"] / (R_GAS * c["T_b_K"]) * (1.0 - c["T_b_K"] / T))


def mass_flux(T, c):
    """[GAN21] SI Eq. 12 high-intensity branch / [FAB20] Eq. A12: m_dot = (1-beta_R) sqrt(M/(2 pi R T)) P_sat [kg/(m2 s)].
    Applied at every surface temperature (no low-intensity polynomial bridge); below T_b the flux is small."""
    import numpy as np
    T = np.asarray(T, dtype=float)
    return (1.0 - c["beta_R"]) * np.sqrt(c["M_kg_mol"] / (2.0 * math.pi * R_GAS * T)) * saturation_pressure(T, c)


def heat_flux(T, c):
    """Evaporative heat sink q = L_v m_dot [W/m2] ([GAN21] SI Eq. 31). No vapour sensible heat, no recoil."""
    return c["L_v_J_kg"] * mass_flux(T, c)


def heat_flux_derivative(T, c):
    """dq/dT = q (M L_v/(R T^2) - 1/(2T)), the row-sum bound of the explicit scheme."""
    import numpy as np
    T = np.asarray(T, dtype=float)
    return heat_flux(T, c) * (c["M_kg_mol"] * c["L_v_J_kg"] / (R_GAS * T * T) - 0.5 / T)


if __name__ == "__main__":
    import json
    for n in ("316L Stainless Steel", "Ti-6Al-4V", "Inconel 718", "Inconel 625"):
        print(json.dumps(alloy_evaporation_constants(n), indent=1, default=float))
    print(json.dumps(method_checks(), indent=1))
