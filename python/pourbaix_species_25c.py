#!/usr/bin/env python3
"""Species table for the single-element M-H2O Pourbaix engine (25 C only).

One row per species with its formula bookkeeping (x metal atoms, o O atoms, h H atoms,
charge z), standard Gibbs energy of formation at 298.15 K (kJ/mol), the phase, the
category role, the source set, the verification level and the evidence for that level.
``pourbaix_solver`` derives every boundary from these rows (SPEC-pourbaix-opus.md
sections 1 and 2); no E0 or slope is entered by hand anywhere.

Source sets (one primary set per element, each with its own H2O value):
  A  Pourbaix, Atlas of Electrochemical Equilibria in Aqueous Solutions, 2nd Engl. ed.,
     NACE/CEBELCOR 1974: mu0 in cal/mol, converted with 4.184 J/cal (H2O -56690 cal).
  N  Wagman et al., NBS tables, J. Phys. Chem. Ref. Data 11, Suppl. 2 (1982) (H2O -237.129).
  L  Latimer, Oxidation Potentials (1952): E0(FeO4 2-/Fe3+) = 2.20 V (derived row).
  E  NEA-TDB, Gamsjager et al., Chemical Thermodynamics of Nickel, OECD NEA vol. 6 (2005), Table III-1
     (open PDF oecd-nea.org/dbtdb/pubs/vol6-nickel.pdf; same selection in PSI/Nagra TM-44-14-05):
     Ni2+ -45.773, beta-Ni(OH)2(cr) -457.100, Ni(OH)3- -590.519 kJ/mol, H2O(l) -237.140 kJ/mol.
  O  CHNOSZ OBIGT database (github.com/jedick/CHNOSZ, GPL-3; only the cited numbers are used):
     Al3+ and Al(OH)4- from Tagirov & Schott, Geochim. Cosmochim. Acta 65 (2001) 3965 (cal/mol),
     gibbsite from Robie, Hemingway & Fisher, USGS Bull. 1452 (1978) (J/mol); H2O is the SUPCRT92
     value used with those aqueous species (-56687 cal/mol). Consistency is checked through the
     reaction constants (gibbsite solubility, Al(OH)4- formation), not assumed.
     For Cr it supplies only the withheld SSWS97 (Shock, Sassani, Willis & Sverjensky 1997) candidate.
  X  log K at infinite dilution, 298 K, from the COST NECTAR WG1 tables of critical compilations
     (cost-nectar.eu/docs/wg1_pt/{CrIII,CrVI,Mo,TiIV}.pdf): Brown & Ekberg 2016 (Cr(III), Ti(IV)
     hydrolysis), Ball & Nordstrom 1998 (Cr), Crea et al. 2017 (Mo(VI) protonation). Rows derived
     from an NBS species with such a constant carry source X.
  P  PHREEQC llnl.dat (LLNL thermo.com.V8.R6, USGS distribution): log K of the Cr and Ti phases and
     species (withheld candidates only; O2 in its reactions is O2(aq), OBIGT 3954 cal, and its water is
     the SUPCRT92 -56687 cal).
  C  E0 from the Wikipedia "Standard electrode potential (data page)" (CC BY-SA; CRC / Bratsch 1989 /
     Bard-Parsons-Jordan lineage): withheld candidates only.
  J  NIST-JANAF Thermochemical Tables (janaf.nist.gov, Chase 1998): verification, and the withheld TiO
     candidate.
Verification levels (reached by this module, not by the table author):
  V1  equals an open table value within 0.5 kJ/mol (OpenStax Chemistry 2e App. G, CC BY 4.0;
      CHNOSZ OBIGT; SKI 95:73 Table 3).
  V2  reproduces a published E0 within 10 mV, or an independently published open equilibrium
      quantity (reaction free energy) within 2.5 kJ/mol.
  V3  not confirmed, or contradicted by another reputable compilation: the row is NOT used; its
      element or row is withheld (see WITHHELD_SPECIES / UNAVAILABLE_ELEMENTS). For Cr, Mo and Ti the
      withheld rows are grouped into CANDIDATE_SETS: the solver reports, as dataValidity regions, where
      any candidate set would change the stable species (the map is not valid there).

CLI (from python/):
  python pourbaix_species_25c.py --emit    write src/generated/pourbaixSpecies25C.json (LF)
  python pourbaix_species_25c.py --check   exit 1 when the committed JSON differs from a fresh emit
"""

import json
import math
import sys
from pathlib import Path

import physical_constants

SCHEMA = "pourbaix-species-25c-v2"
REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATED_JSON = REPO_ROOT / "src" / "generated" / "pourbaixSpecies25C.json"

CAL_J = 4.184  # J per thermochemical calorie (Atlas mu0 values are in cal/mol)
TEMPERATURE_C = 25.0
TEMPERATURE_K = physical_constants.ZERO_CELSIUS_K.value + TEMPERATURE_C
LN10 = math.log(10.0)

# Lower limit 10^-6 M: the mononuclear hydrolysis species (MOH+, M(OH)2(aq)) are not in the table for any
# element. At 10^-6 M and above they change at most about 0.6 % of the water-window cells for Fe, Ni, Cu, Mg
# and Al; Zn is constant-dependent (IUPAC 2013 Zn(OH)2(aq) keeps ZnO, the wateq4f / Baes & Mesmer constant
# would replace the whole ZnO domain, see the ZnO row). At 10^-8 M several % (MgOH+ about 5 %). Lower
# activities are refused instead of mapped without these species.
ACTIVITY_LOG10_RANGE = (-6.0, 0.0)
ACTIVITY_LOG10_DEFAULT = -6.0
# Narrower ranges where an excluded polynuclear species would otherwise take a domain even under the
# per-species activity convention: Cr2O7 2- from 10^-1.55 (NBS) / 10^-1.75 (Ball & Nordstrom 1998 constant on the NBS
# CrO4 2- / HCrO4- pair),
# the heptamolybdates from 10^-3.53 (Crea et al. 2017 constants). Requests outside are refused.
ACTIVITY_LOG10_RANGE_BY_ELEMENT = {"Cr": (-6.0, -2.0), "Mo": (-6.0, -4.0)}
BOX = {"pH_min": -2.0, "pH_max": 16.0, "E_min_V_SHE": -3.0, "E_max_V_SHE": 2.5}

WATER_DFG_NBS_KJ_MOL = -237.129  # also fixes the O2/H2O water line (1.2288 V)

ROLES = ("metal", "cation", "anion_low", "oxide", "anion_high")
CATEGORY_BY_ROLE = {
    "metal": "Immunity",
    "cation": "Corrosion (acid)",
    "anion_low": "Corrosion (alkaline)",
    "oxide": "Passivation (thermodynamic, film-forming)",
    "anion_high": "Transpassive",
}


def _atlas(cal_per_mol):
    """Atlas mu0 (cal/mol) -> kJ/mol."""
    return cal_per_mol * CAL_J / 1000.0


def _obigt_cal(cal_per_mol):
    """CHNOSZ OBIGT G (E_units cal) -> kJ/mol."""
    return cal_per_mol * CAL_J / 1000.0


# Derived row: FeO4 2- from Fe3+ + 4 H2O -> FeO4 2- + 8 H+ + 3 e-, E0 = 2.20 V (Latimer).
_FE_H2O = _atlas(-56690.0)
_FEO4_DFG = _atlas(-2530.0) + 4.0 * _FE_H2O + 3.0 * physical_constants.FARADAY.value * 2.20 / 1000.0

# Ni set E: NEA-TDB (CODATA) water used with the Gamsjager et al. 2005 Ni species.
_NI_H2O = -237.140
_NI2P = -45.773           # Ni2+
_NI_OH2 = -457.100        # beta-Ni(OH)2(cr); = Ni2+ + 2 H2O + RT ln10 * 11.02 (log *Ks,0) within 0.05 kJ/mol
_NI_OH3M = -590.519       # Ni(OH)3-; = Ni2+ + 3 H2O + RT ln10 * 29.2 (log *beta3 = -29.2 +/- 1.7)
_NI_HNIO2M = _NI_OH3M - _NI_H2O   # HNiO2- = Ni(OH)3- - H2O
# NiO2: not in the NEA volume. Anchored to Ni2+ through E0(NiO2 + 4H+ + 2e- = Ni2+ + 2H2O) = 1.593 V
# (atlas / CRC value), so that couple stays where it was relative to Ni2+.
_NI_NIO2 = _NI2P + 2.0 * _NI_H2O + 2.0 * physical_constants.FARADAY.value * 1.593 / 1000.0

# Al set O: SUPCRT92 water used with the Tagirov & Schott 2001 aqueous species.
_AL_H2O = _obigt_cal(-56687.0)

# ---- Cr, Mo, Ti (NBS set N, H2O -237.129; values read from the NIST-hosted scan of Wagman et al. 1982,
# Tables 51 (Cr, p. 2-197), 52 (Mo, p. 2-201) and 57 (Ti, p. 2-209)) ---------------------------------
_F_KJ = physical_constants.FARADAY.value / 1000.0           # kJ/(mol V)
_K_LOG = LN10 * physical_constants.GAS_CONSTANT_R.value * TEMPERATURE_K / 1000.0  # kJ/mol per log10 unit
_W = WATER_DFG_NBS_KJ_MOL

_CR2O3 = -1058.1          # Cr2O3(cr), NBS
_CRO4 = -727.75           # CrO4 2-(ao), NBS
_HCRO4 = -764.7           # HCrO4-(ao), NBS
_CR2O7 = -1301.1          # Cr2O7 2-(ao), NBS (polynuclear: withheld)
_MOO2 = -533.01           # MoO2(cr), NBS
_MOO3 = -667.97           # MoO3(cr), NBS
_MOO4 = -836.3            # MoO4 2-(ao), NBS
_RUTILE = -889.5          # TiO2 rutile (cr3), NBS
_ANATASE = -884.5         # TiO2 anatase (cr), NBS
_TI2O3 = -1434.2          # Ti2O3(cr), NBS
_TI3O5 = -2317.4          # Ti3O5(cr), NBS
_TIO_NBS = -495.0         # TiO alpha (cr), NBS
_TIH2 = -80.3             # TiH2(cr), NBS

# Mo(VI) protonation, Crea et al. 2017 (NECTAR Mo table, I = 0): MoO4 2- + H+ = HMoO4- 4.47 +/- 0.02,
# MoO4 2- + 2H+ = H2MoO4 8.12 +/- 0.03.
_HMOO4 = _MOO4 - _K_LOG * 4.47
_H2MOO4 = _MOO4 - _K_LOG * 8.12


def _from_e0_metal(n, e0):
    """dfG of M^n+ from E0(M^n+/M) = e0 V."""
    return n * _F_KJ * e0


def _hydrolysis(parent_dfg, n_water, log_k):
    """dfG of M(OH)_n (charge from the parent) from parent + n H2O = product + n H+, log K."""
    return parent_dfg + n_water * _W - _K_LOG * log_k


# Cr(III) and Cr(II) candidate sets (withheld: the four compilations put Cr3+ between -214.2 and -195.1 kJ/mol).
# C: Wikipedia data page E0 Cr3+/Cr -0.74 V, Cr2+/Cr -0.9 V (their difference implies Cr3+/Cr2+ -0.42 V, the
#    listed -0.407 V is 13 mV away: rounding of the printed values).
_CR3_C = _from_e0_metal(3, -0.74)
_CR2_C = _from_e0_metal(2, -0.9)
# O: OBIGT SSWS97 Cr+3 -49300 cal, Cr+2 -39400 cal.
_CR3_O = _obigt_cal(-49300.0)
_CR2_O = _obigt_cal(-39400.0)
# P: llnl.dat  Cr + 3H+ + 0.75 O2(aq) = Cr3+ + 1.5 H2O        log K 98.6784
#              5H+ + CrO4 2- = Cr3+ + 2.5 H2O + 0.75 O2(aq)    log K 8.3842
#              4H+ + CrO4 2- = Cr2+ + 2 H2O + O2(aq)          log K -21.6373
_LLNL_H2O = _obigt_cal(-56687.0)
_LLNL_O2AQ = _obigt_cal(3954.0)
_CR3_P = -_K_LOG * 98.6784 + 0.75 * _LLNL_O2AQ - 1.5 * _LLNL_H2O
_CRO4_P = _CR3_P + 2.5 * _LLNL_H2O + 0.75 * _LLNL_O2AQ + _K_LOG * 8.3842
_CR2_P = _K_LOG * 21.6373 - 2.0 * _LLNL_H2O - _LLNL_O2AQ + _CRO4_P
# X: Ball & Nordstrom 1998 Cr2O3(s) + 6H+ = 2Cr3+ + 3H2O log K 8.52 (NECTAR CrIII table), on the NBS Cr2O3;
#    Cr2+ from it with E0(Cr3+/Cr2+) = -0.407 V (Wikipedia data page).
_CR3_X = (-_K_LOG * 8.52 - 3.0 * _W + _CR2O3) / 2.0
_CR2_X = _CR3_X + _F_KJ * 0.407
# Cr(III) hydrolysis, Brown & Ekberg 2016 (NECTAR CrIII table, shaded 'best' values): Cr3+ + nH2O = ...
_CR_HYDROLYSIS = (("CrOH2+", "CrOH²⁺", 1, 1, 2, 1, -3.60), ("Cr(OH)2+", "Cr(OH)₂⁺", 2, 2, 1, 2, -9.65),
                  ("Cr(OH)3(aq)", "Cr(OH)₃(aq)", 3, 3, 0, 3, -16.25), ("Cr(OH)4-", "Cr(OH)₄⁻", 4, 4, -1, 4, -27.56))
# H2CrO4: Ball & Nordstrom 1998 CrO4 2- + 2H+ = H2CrO4 log K 6.31 (NECTAR CrVI table), on the NBS CrO4 2-.
_H2CRO4_X = _CRO4 - _K_LOG * 6.31

# Ti candidates. C: Wikipedia data page E0 Ti2+/Ti -1.63, Ti3+/Ti -1.37, TiO2+/Ti -0.93 (TiO2+ + 2H+ + 4e-),
# TiO2+/Ti3+ +0.19, TiO/Ti -1.31 V (TiO + 2H+ + 2e-).
_TI2_C = _from_e0_metal(2, -1.63)
_TI3_C = _from_e0_metal(3, -1.37)
_TIO2P_C = _W + 4.0 * _F_KJ * (-0.93)          # -596.05: from TiO2+/Ti
_TIO2P_C2 = _TI3_C + _W + _F_KJ * 0.19          # -615.35: from TiO2+/Ti3+ with Ti3+/Ti (same table)
_TIO_C = _W + 2.0 * _F_KJ * (-1.31)
# J: NIST-JANAF TiO alpha (O-018) dfG(298.15 K) -513.278 kJ/mol.
_TIO_J = -513.278
# X: Brown & Ekberg 2016 (NECTAR TiIV table) on NBS rutile (the table writes TiO2(s); rutile is assumed):
#    TiO2 + 4H+ = Ti4+ + 2H2O -3.56; TiO2 + H+ = TiOOH+ -6.06; TiO2 + H2O = TiO(OH)2 -9.02;
#    TiO(OH)2 + H2O = TiO(OH)3- + H+ -11.9.
_TI4_X = _RUTILE - 2.0 * _W - _K_LOG * (-3.56)
_TIOOH_X = _RUTILE - _K_LOG * (-6.06)
_TIOOH2_X = _RUTILE + _W - _K_LOG * (-9.02)
_TIOOH3_X = _TIOOH2_X + _W - _K_LOG * (-11.9)
# P: llnl.dat rutile + 2 H2O = Ti(OH)4(aq) log K -9.6452, on NBS rutile.
_TIOH4_P = _RUTILE + 2.0 * _W - _K_LOG * (-9.6452)
# Mo(III): Wikipedia data page E0(H2MoO4 + 6H+ + 3e- = Mo3+ + 4H2O) = +0.43 V on the table's H2MoO4.
_MO3_C = _H2MOO4 - 4.0 * _W - 3.0 * _F_KJ * 0.43
# Heptamolybdates (Crea et al. 2017, NECTAR Mo table): 7 MoO4 2- + p H+ = species + 4 H2O, log K.
_MO7 = (("Mo7O24^6-", "Mo₇O₂₄⁶⁻", 0, -6, 51.93), ("HMo7O24^5-", "HMo₇O₂₄⁵⁻", 1, -5, 58.90),
        ("H2Mo7O24^4-", "H₂Mo₇O₂₄⁴⁻", 2, -4, 64.63), ("H3Mo7O24^3-", "H₃Mo₇O₂₄³⁻", 3, -3, 68.68))

# (id, formula, x, o, h, z, phase, dfG_kJ_mol, role, source, level, evidence)
# phase: "s" solid (activity 1), "aq" dissolved (activity = 10**ionActivity_log10).
# Table order is the tie-break order: metal, cations, solids, anions.
_ROWS = {
    "Fe": (
        ("Fe", "Fe", 1, 0, 0, 0, "s", 0.0, "metal", "ref", "V1", "reference state"),
        ("Fe2+", "Fe²⁺", 1, 0, 0, 2, "aq", _atlas(-20300.0), "cation", "A", "V2",
         "E0(Fe2+/Fe) table -0.4401 V vs -0.447 V (CRC) / -0.44 V (Wikipedia data page): +7 mV"),
        ("Fe3+", "Fe³⁺", 1, 0, 0, 3, "aq", _atlas(-2530.0), "cation", "A", "V2",
         "E0(Fe3+/Fe2+) table 0.7706 V vs 0.771 V (Wikipedia data page / CRC)"),
        ("Fe3O4", "Fe₃O₄", 3, 4, 0, 0, "s", _atlas(-242400.0), "oxide", "A", "V2",
         "OpenStax App. G -1015.4 kJ/mol (delta +1.2); E0(Fe3O4/Fe) -0.0848 vs -0.085 V; "
         "E0(Fe3O4/Fe2+) 0.9813 vs 0.98 V"),
        ("Fe2O3", "Fe₂O₃", 2, 3, 0, 0, "s", _atlas(-177100.0), "oxide", "A", "V2",
         "OpenStax App. G -742.2 kJ/mol (delta +1.2); E0(Fe2O3/Fe2+) 0.7279 vs 0.728 V; "
         "E0(Fe2O3/Fe3O4) 0.2209 vs 0.22 V"),
        ("HFeO2-", "HFeO₂⁻", 1, 2, 1, -1, "aq", _atlas(-90627.0), "anion_low", "A", "V2",
         "NBS (Wagman 1982) -377.7 kJ/mol as transcribed in the open CHNOSZ iron documentation "
         "(chnosz.net/vignettes/multi-metal.html): delta -1.5 kJ/mol"),
        ("FeO4^2-", "FeO₄²⁻", 1, 4, 0, -2, "aq", _FEO4_DFG, "anion_high", "L", "V2",
         "E0(FeO4 2-/Fe3+) = 2.20 V (Wikipedia data page); derived row, an estimate whose "
         "domain lies above the O2 line"),
    ),
    "Ni": (
        ("Ni", "Ni", 1, 0, 0, 0, "s", 0.0, "metal", "ref", "V1", "reference state"),
        ("Ni2+", "Ni²⁺", 1, 0, 0, 2, "aq", _NI2P, "cation", "E", "V1",
         "NEA-TDB (Gamsjaeger 2005) -45.773 +/- 0.771 kJ/mol; CHNOSZ OBIGT (SH88) Ni+2 -10900 cal = -45.606 "
         "kJ/mol (delta 0.17 kJ/mol). E0(Ni2+/Ni) = -0.2372 V; the older electrochemical value -0.257 V "
         "(CRC / Wikipedia data page) is 20 mV lower: documented exception, the calorimetric NEA/NBS value is used"),
        ("Ni(OH)2", "Ni(OH)₂", 1, 2, 2, 0, "s", _NI_OH2, "oxide", "E", "V2",
         "beta-Ni(OH)2(cr) + 2H+ = Ni2+ + 2H2O: table log K 11.02 = NEA-TDB selection (+/- 0.20, from "
         "Gamsjaeger et al. 2002 solubility measurements; PSI/Nagra TM-44-14-05 adopts the same value); "
         "wateq4f.dat (Nordstrom 1990) 10.8 (delta 1.3 kJ/mol). Open databases spread 10.8 to 12.7 "
         "(llnl.dat 12.75: 9.9 kJ/mol above NEA). E0(Ni(OH)2/Ni, alkaline) -0.739 V vs -0.72 V (CRC, "
         "older solubility constants): documented exception"),
        ("HNiO2-", "HNiO₂⁻", 1, 2, 1, -1, "aq", _NI_HNIO2M, "anion_low", "E", "V2",
         "Ni(OH)2(cr) + H2O = Ni(OH)3- + H+ (Ni(OH)3- = HNiO2- + H2O): table log K 11.02 - 29.2 = -18.18 "
         "(NEA log *beta3 -29.2 +/- 1.7); llnl.dat 12.7485 - 30.9852 = -18.24 (delta 0.3 kJ/mol); "
         "wateq4f.dat 10.8 - 30 = -19.2 (outside 2.5 kJ/mol: the data spread is real)"),
    ),
    "Cu": (
        ("Cu", "Cu", 1, 0, 0, 0, "s", 0.0, "metal", "ref", "V1", "reference state"),
        ("Cu+", "Cu⁺", 1, 0, 0, 1, "aq", 49.98, "cation", "N", "V1",
         "CHNOSZ OBIGT (AZ23) 11945 cal = 49.98 kJ/mol; E0(Cu+/Cu) 0.518 V vs 0.521 V"),
        ("Cu2+", "Cu²⁺", 1, 0, 0, 2, "aq", 65.49, "cation", "N", "V1",
         "OpenStax App. G 65.49 kJ/mol; E0(Cu2+/Cu) 0.3394 V vs 0.3419 V (CRC)"),
        ("Cu2O", "Cu₂O", 2, 1, 0, 0, "s", -146.0, "oxide", "N", "V1",
         "OpenStax App. G -146.0 kJ/mol; E0(Cu2O/Cu, alkaline) -0.356 V vs -0.36 V"),
        ("CuO", "CuO", 1, 1, 0, 0, "s", -129.7, "oxide", "N", "V1",
         "OpenStax App. G -129.7 kJ/mol"),
        ("HCuO2-", "HCuO₂⁻", 1, 2, 1, -1, "aq", -258.5, "anion_low", "N", "V2",
         "SKI Report 95:73 (Beverskog & Puigdomenech) Table 3: Cu(OH)3- -493.98 kJ/mol "
         "(the OCR of the open PDF shows '-^93.98'; -493.98 is the value consistent with "
         "log K = -19 of CuO + 2H2O = Cu(OH)3- + H+), so HCuO2- = -256.85 (Cu(OH)3- = HCuO2- + H2O): "
         "delta -1.65 kJ/mol"),
        ("CuO2^2-", "CuO₂²⁻", 1, 2, 0, -2, "aq", -183.6, "anion_low", "N", "V2",
         "SKI Report 95:73 Table 3: Cu(OH)4 2- -657.48 kJ/mol, so CuO2 2- = -183.22 "
         "(Cu(OH)4 2- = CuO2 2- + 2 H2O): delta -0.38 kJ/mol"),
    ),
    "Zn": (
        ("Zn", "Zn", 1, 0, 0, 0, "s", 0.0, "metal", "ref", "V1", "reference state"),
        ("Zn2+", "Zn²⁺", 1, 0, 0, 2, "aq", -147.06, "cation", "N", "V1",
         "OpenStax App. G -147.1 kJ/mol; E0(Zn2+/Zn) -0.7621 V vs -0.7618 V"),
        ("ZnO", "ZnO", 1, 1, 0, 0, "s", -318.30, "oxide", "N", "V2",
         "OpenStax App. G -320.5 kJ/mol (CHNOSZ zincite -76596 cal): table is 2.2 kJ/mol less "
         "negative; known sensitivity (Zn2+/ZnO pH 8.77 here, 8.58 with -320.5); sets not mixed. The omitted "
         "Zn(OH)2(aq) is constant-dependent at the default 1e-6 M: with IUPAC 2013 (Powell & Brown, log *beta2 "
         "-17.82) ZnO + H2O = Zn(OH)2(aq) has log K -6.28 and ZnO keeps its domain (0.28 log margin); with the "
         "wateq4f / Baes & Mesmer constant (-16.9) log K is -5.36 and Zn(OH)2(aq) would replace the whole ZnO "
         "domain"),
        ("HZnO2-", "HZnO₂⁻", 1, 2, 1, -1, "aq", -457.09, "anion_low", "N", "V2",
         "ZnO + H2O = HZnO2- + H+: table log K -17.23; CHNOSZ OBIGT (AT14 HZnO2- -110156 cal, "
         "SSWS97.1 zincite -76596 cal) -16.95: delta 1.6 kJ/mol"),
        ("ZnO2^2-", "ZnO₂²⁻", 1, 2, 0, -2, "aq", -384.2, "anion_low", "N", "V2",
         "E0(Zn(OH)4 2-/Zn, alkaline) table -1.190 V vs -1.199 V (Wikipedia data page): 9 mV"),
    ),
    "Mg": (
        ("Mg", "Mg", 1, 0, 0, 0, "s", 0.0, "metal", "ref", "V1", "reference state"),
        ("Mg2+", "Mg²⁺", 1, 0, 0, 2, "aq", -454.8, "cation", "N", "V1",
         "OpenStax App. G -454.8 kJ/mol; E0(Mg2+/Mg) -2.3568 V vs -2.372 V (CRC/Bratsch): "
         "+15 mV, documented NBS-vs-Bratsch exception"),
        ("Mg(OH)2", "Mg(OH)₂", 1, 2, 2, 0, "s", -833.51, "oxide", "N", "V2",
         "E0(Mg(OH)2/Mg, alkaline) table -2.690 V vs -2.69 V (Wikipedia data page)"),
    ),
    "Al": (
        ("Al", "Al", 1, 0, 0, 0, "s", 0.0, "metal", "ref", "V1", "reference state"),
        ("Al3+", "Al³⁺", 1, 0, 0, 3, "aq", _obigt_cal(-116510.0), "cation", "O", "V2",
         "OBIGT Al+3 (TS01) -116510 cal. E0(Al3+/Al) -1.6841 V: NBS -485.0 kJ/mol (OpenStax App. G) "
         "gives -1.6756 V (delta -8.6 mV, -2.5 kJ/mol); CODATA 1989 key values (dfH -538.4 +/- 1.5, "
         "S -325 +/- 10) give -491.5 +/- 3.3 kJ/mol = -1.6980 V (delta +14 mV, 1.2 sigma); the "
         "CRC/Wikipedia -1.662 V is the older Latimer/atlas value (-115000 cal) and lies 22 mV above: "
         "documented exception like Mg2+/Mg"),
        ("Al(OH)3", "Al(OH)₃ (gibbsite)", 1, 3, 3, 0, "s", -1154.889, "oxide", "O", "V2",
         "OBIGT gibbsite (Robie, Hemingway & Fisher 1978) -1154889 J. Gibbsite + 3H+ = Al3+ + 3H2O: "
         "set log K 7.730; LLNL thermo.com.V8.R6 (PHREEQC llnl.dat) 7.756 (0.15 kJ/mol); Nordstrom "
         "et al. 1990 (PHREEQC phreeqc.dat/wateq4f.dat) 8.11 (2.2 kJ/mol). Hydrargillite is the old "
         "name of gibbsite; the atlas hydrargillite value is 5.3 kJ/mol per Al more negative and is "
         "not used"),
        ("Al(OH)4-", "Al(OH)₄⁻", 1, 4, 4, -1, "aq", _obigt_cal(-312087.0), "anion_low", "O", "V2",
         "OBIGT Al(OH)4- (TS01) -312087 cal (aluminate; AlO2- + 2H2O, the engine counts the water). "
         "Al3+ + 4H2O = Al(OH)4- + 4H+: set log K -22.849; llnl.dat -22.883 (0.2 kJ/mol), "
         "phreeqc.dat -22.7 (0.85 kJ/mol). E0(Al(OH)4-/Al, alkaline) -2.338 V vs -2.33 V "
         "(Wikipedia data page, 'H2AlO3-' notation, CRC): 8 mV"),
    ),
    "Cr": (
        ("Cr", "Cr", 1, 0, 0, 0, "s", 0.0, "metal", "ref", "V1", "reference state"),
        ("Cr2O3", "Cr₂O₃", 2, 3, 0, 0, "s", _CR2O3, "oxide", "N", "V2",
         "NBS (Wagman 1982, Table 51) -1058.1 kJ/mol; LLNL thermo.com.V8.R6 eskolaite (llnl.dat log K -9.1306 "
         "with its CrO4 2-) -1058.10. NIST-JANAF (Chase 1998, Cr-014) -1053.07 and Ziemniak et al. (KAPL "
         "LM-06K145, 2007) -1049.96 are 5.0 and 8.1 kJ/mol less negative: E0(Cr2O3/Cr) -0.5989 V (NBS) vs "
         "-0.5902 V (JANAF), 8.7 mV; -0.5848 V (KAPL), 14 mV"),
        ("HCrO4-", "HCrO₄⁻", 1, 4, 1, -1, "aq", _HCRO4, "anion_high", "N", "V1",
         "NBS -764.7 kJ/mol; LLNL thermo.com.V8.R6 -764.83 (0.13 kJ/mol). CrO4 2- + H+ = HCrO4-: table log K "
         "6.473 vs Ball & Nordstrom 1998 6.55 +/- 0.04 and Baes & Mesmer 1976 6.51 (COST NECTAR CrVI table)"),
        ("CrO4^2-", "CrO₄²⁻", 1, 4, 0, -2, "aq", _CRO4, "anion_high", "N", "V1",
         "NBS -727.75 kJ/mol; LLNL thermo.com.V8.R6 (llnl.dat, Cr3+ and CrO4 2- through Cr(s)) -727.76 "
         "(0.01 kJ/mol); OBIGT SSWS97 -174800 cal = -731.36 (3.6 kJ/mol)"),
    ),
    "Mo": (
        ("Mo", "Mo", 1, 0, 0, 0, "s", 0.0, "metal", "ref", "V1", "reference state"),
        ("MoO2", "MoO₂", 1, 2, 0, 0, "s", _MOO2, "oxide", "N", "V2",
         "NBS (Wagman 1982, Table 52) -533.01 kJ/mol; NIST-JANAF (Mo-009) -532.01 (1.0 kJ/mol). "
         "E0(MoO2/Mo) -0.1522 V vs -0.15 V (Wikipedia data page)"),
        ("MoO3", "MoO₃", 1, 3, 0, 0, "s", _MOO3, "oxide", "N", "V1",
         "NBS -667.97 kJ/mol; NIST-JANAF (Mo-014) -668.08 (0.11 kJ/mol). MoO3 + H2O = MoO4 2- + 2H+: table "
         "log K -12.05 vs Baes & Mesmer -12.06 (3 M NaClO4, NECTAR Mo table); MoO3 + H2O = H2MoO4(aq) -3.93, so "
         "MoO3 has a domain only above 10^-3.93 M (outside the Mo activity range)"),
        ("H2MoO4", "H₂MoO₄(aq)", 1, 4, 2, 0, "aq", _H2MOO4, "anion_high", "X", "V2",
         "NBS MoO4 2- with MoO4 2- + 2H+ = H2MoO4 log K 8.12 +/- 0.03 (Crea et al. 2017, NECTAR Mo table); "
         "NIST46 4.24 + 4.0 = 8.24 (0.7 kJ/mol). E0(H2MoO4/MoO2) 0.6458 V vs 0.65 V and E0(H2MoO4/Mo) "
         "0.1138 V vs 0.11 V (Wikipedia data page). Neutral Mo(VI) oxo species: category of the high-valence "
         "dissolved species (transpassive)"),
        ("HMoO4-", "HMoO₄⁻", 1, 4, 1, -1, "aq", _HMOO4, "anion_high", "X", "V2",
         "NBS MoO4 2- with MoO4 2- + H+ = HMoO4- log K 4.47 +/- 0.02 (Crea et al. 2017, NECTAR Mo table); "
         "NIST46 4.24 (1.3 kJ/mol), OBIGT SSWS97 4.40 (0.4 kJ/mol)"),
        ("MoO4^2-", "MoO₄²⁻", 1, 4, 0, -2, "aq", _MOO4, "anion_high", "N", "V2",
         "NBS -836.3 kJ/mol; OBIGT SSWS97 -200400 cal = -838.47 (2.2 kJ/mol). High-valence Mo(VI) oxyanion: "
         "transpassive category (at neutral and alkaline pH its domain begins directly above MoO2)"),
    ),
    "Ti": (
        ("Ti", "Ti", 1, 0, 0, 0, "s", 0.0, "metal", "ref", "V1", "reference state"),
        ("Ti2O3", "Ti₂O₃", 2, 3, 0, 0, "s", _TI2O3, "oxide", "N", "V1",
         "NBS (Wagman 1982, Table 57) -1434.2 kJ/mol; NIST-JANAF (O-059) -1433.83 (0.37 kJ/mol). "
         "E0(2TiO2/Ti2O3) -0.5580 V vs -0.56 V (Wikipedia data page)"),
        ("Ti3O5", "Ti₃O₅", 3, 5, 0, 0, "s", _TI3O5, "oxide", "N", "V1",
         "NBS -2317.4 kJ/mol; NIST-JANAF (O-080) -2317.29 (0.11 kJ/mol). It has no domain with these values "
         "(Ti2O3 + TiO2 is lower)"),
        ("TiO2", "TiO₂ (rutile)", 1, 2, 0, 0, "s", _RUTILE, "oxide", "N", "V1",
         "NBS rutile -889.5 kJ/mol; NIST-JANAF (O-043) -889.41 (0.09 kJ/mol). E0(TiO2/Ti) -1.0759 V"),
    ),
}

ELEMENT_SET = {
    "Fe": ("A", _FE_H2O, "Atlas set (Pourbaix 1974); FeO4 2- derived from Latimer E0 (L)"),
    "Ni": ("E", _NI_H2O, "NEA-TDB set (Gamsjaeger et al. 2005, Chemical Thermodynamics of Nickel, Table III-1) with "
                         "CODATA water; Ni3O4 and Ni2O3 (atlas rows) and the NiO2 estimate are withheld"),
    "Cu": ("N", WATER_DFG_NBS_KJ_MOL, "NBS set (Wagman 1982)"),
    "Zn": ("N", WATER_DFG_NBS_KJ_MOL, "NBS set (Wagman 1982), ZnO see row evidence"),
    "Mg": ("N", WATER_DFG_NBS_KJ_MOL, "NBS set (Wagman 1982)"),
    "Al": ("O", _AL_H2O, "CHNOSZ OBIGT set: Al3+ and Al(OH)4- (Tagirov & Schott 2001) with gibbsite "
                         "(Robie, Hemingway & Fisher 1978) and SUPCRT92 water. The solid is gibbsite; "
                         "boehmite and corundum are listed under withheldSpecies (metastable/excluded). "
                         "The mononuclear hydrolysis species AlOH2+, Al(OH)2+ and Al(OH)3(aq) (TS01) are "
                         "omitted as for the other elements: they have no domain for log a >= -7.16; at "
                         "log a = -8 AlOH2+ would take pH 4.96-5.38 from Al3+ and gibbsite"),
    "Cr": ("N", WATER_DFG_NBS_KJ_MOL, "NBS set (Wagman 1982): Cr, Cr2O3, HCrO4-, CrO4 2-. The Cr(III)/Cr(II) aqueous "
                                      "species are WITHHELD: four reputable compilations put Cr3+ between -214.2 and "
                                      "-195.1 kJ/mol (66 mV in E0(Cr3+/Cr)); they are carried as candidate sets and "
                                      "the map is not valid where any of them would be stable (dataValidity)"),
    "Mo": ("N", WATER_DFG_NBS_KJ_MOL, "NBS set (Wagman 1982) for Mo, MoO2, MoO3 and MoO4 2-; HMoO4- and H2MoO4(aq) from "
                                      "the NBS MoO4 2- with the Crea et al. 2017 constants (NECTAR). Mo(III) is a "
                                      "withheld candidate; Mo(VI) cations and the polymolybdates are not represented "
                                      "(dissolved activity limited to 10^-6..10^-4)"),
    "Ti": ("N", WATER_DFG_NBS_KJ_MOL, "NBS set (Wagman 1982): Ti, Ti2O3, Ti3O5, TiO2 (rutile), each within 0.4 kJ/mol "
                                      "of NIST-JANAF. TiO (NBS and JANAF 18 kJ/mol apart), the Ti(II)/Ti(III)/Ti(IV) "
                                      "aqueous species (mutually inconsistent) and the hydride TiH2 are WITHHELD "
                                      "candidates; the map is not valid where any of them would be stable "
                                      "(dataValidity)"),
}

# Couple used for the informational standardE0_V (unit activity, pH independent); None when the element
# has no verified cation in the table (its standardE0_V is then null).
REFERENCE_CATION = {"Fe": "Fe2+", "Ni": "Ni2+", "Cu": "Cu2+", "Zn": "Zn2+", "Mg": "Mg2+", "Al": "Al3+",
                    "Cr": None, "Mo": None, "Ti": None}

NAMES = {
    "Fe": "Iron (Fe-H₂O System)", "Cr": "Chromium (Cr-H₂O System)", "Ni": "Nickel (Ni-H₂O System)",
    "Ti": "Titanium (Ti-H₂O System)", "Al": "Aluminum (Al-H₂O Amphoteric System)",
    "Cu": "Copper (Cu-H₂O System)", "Zn": "Zinc (Zn-H₂O System Amphoteric)",
    "Mg": "Magnesium (Mg-H₂O System)", "Mo": "Molybdenum (Mo-H₂O System)",
}

# Rows NOT used by the engine: kept with their values so a reviewer can see what was withheld.
WITHHELD_SPECIES = {
    "Ni": (
        ("Ni3O4", "Ni₃O₄", 3, 4, 0, 0, "s", _atlas(-170150.0), "oxide", "A", "V3",
         "no open source found for the atlas value, which the atlas itself calls uncertain; not used. "
         "Withholding Ni3O4 and Ni2O3 changes the category (Ni2+ or HNiO2- instead of Passivation) of "
         "about 2 % of the Ni cells inside the water window (4 % on the atlas set, measured with the atlas rows "
         "anchored to the NEA Ni2+ and CODATA water). The value shown is the atlas one"),
        ("Ni2O3", "Ni₂O₃", 2, 3, 0, 0, "s", _atlas(-112270.0), "oxide", "A", "V3",
         "no open source found for the atlas value (an E0 of 1.753 V is only reproduced by the same "
         "table); the atlas calls it uncertain; not used"),
        ("NiO2", "NiO₂", 1, 2, 0, 0, "s", _NI_NIO2, "oxide", "E", "V3",
         "WITHHELD estimate (it was served as V2 until the second re-review): anchored to the NEA Ni2+ through "
         "E0(NiO2/Ni2+, acid) = 1.593 V (atlas / CRC / Wikipedia data page: one lineage, so the E0 check is "
         "tautological); the NEA volume has no Ni(III/IV) oxide and the atlas calls the higher nickel oxides "
         "uncertain. Its domain would lie above the O2 line, at least 38 mV above it (minimum at pH 8.5), so "
         "withholding it leaves the water-window map unchanged; above the O2 line the map shows Ni(OH)2, Ni2+ "
         "and HNiO2- instead of a NiO2 passivation domain"),
    ),
    "Al": (
        ("AlO2-(atlas)", "AlO₂⁻ (atlas)", 1, 2, 0, -1, "aq", _atlas(-200710.0), "anion_low", "A", "V3",
         "REJECTED atlas row (atlas set, H2O -237.19): CHNOSZ OBIGT (TS01) Al(OH)4- -312087 cal gives "
         "AlO2- = -831.3 kJ/mol; the Wikipedia E0 of H2AlO3-/Al (-2.33 V) implies -831.0; PourPy -827.5: "
         "the atlas value is 8-12 kJ/mol more negative (30 mV). Replaced by Al(OH)4- (set O)"),
        ("Al2O3.3H2O(atlas)", "Al₂O₃·3H₂O (hydrargillite, atlas)", 2, 6, 6, 0, "s", _atlas(-554600.0), "oxide",
         "A", "V3",
         "REJECTED atlas row (atlas set, H2O -237.19): -1160.2 kJ/mol per Al vs gibbsite -1154.9 (Robie, "
         "Hemingway & Fisher 1978); with it the Al3+/hydroxide boundary is pH 3.90 instead of 4.58 at "
         "a = 1e-6. Replaced by Al(OH)3 gibbsite (set O)"),
        ("AlO(OH)", "AlO(OH) (boehmite)", 1, 2, 1, 0, "s", -918.400, "oxide", "O", "V2",
         "EXCLUDED (metastable by convention): OBIGT boehmite (Hemingway, Robie & Apps 1991) -918400 J; "
         "AlOOH + 3H+ = Al3+ + 2H2O set log K 7.609 vs llnl.dat 7.564. Boehmite + H2O lies 0.69 kJ/mol "
         "below gibbsite in this set, but the sign differs between open databases (llnl.dat boehmite "
         "1.1 kJ/mol lower; wateq4f.dat and minteq.v4.dat gibbsite 2.7 and 1.6 kJ/mol lower). The 25 C "
         "map uses gibbsite, the Al(OH)3 phase of the conventional diagram; with boehmite the "
         "Al3+/solid boundary moves to pH 4.54 and the solid/Al(OH)4- boundary to pH 9.24 at a = 1e-6 "
         "(same categories)"),
        ("Al2O3", "Al₂O₃ (corundum)", 2, 3, 0, 0, "s",
         -1675.7 - TEMPERATURE_K * (50.92 - 2 * 28.30 - 1.5 * 205.152) / 1000.0, "oxide", "O", "V2",
         "EXCLUDED (metastable): dfG from the CODATA 1989 key values (dfH -1675.7 kJ/mol, S 50.92; Al 28.30, "
         "O2 205.152 J/mol/K) = -1582.26 kJ/mol (OpenStax App. G -1582). Per Al it lies 8.0 kJ/mol above "
         "gibbsite + water, so it never has a domain"),
    ),
}

_CR_SETS = (
    # (tag, Cr3+ dfG, Cr2+ dfG, source, provenance of the two cations)
    ("CRC", _CR3_C, _CR2_C, "C", "Wikipedia data page E0 Cr3+/Cr -0.74 V and Cr2+/Cr -0.9 V (CRC / Bratsch lineage)"),
    ("SSWS97", _CR3_O, _CR2_O, "O", "CHNOSZ OBIGT SSWS97 Cr+3 -49300 cal and Cr+2 -39400 cal"),
    ("LLNL", _CR3_P, _CR2_P, "P", "PHREEQC llnl.dat (LLNL thermo.com.V8.R6) log K 98.6784 (Cr(s) -> Cr3+), 8.3842 "
                                  "and -21.6373 (CrO4 2- -> Cr3+, Cr2+), SUPCRT92 water and OBIGT O2(aq); its "
                                  "E0(Cr3+/Cr2+) is -0.504 V against the measured -0.407 V"),
    ("BN98", _CR3_X, _CR2_X, "X", "Ball & Nordstrom 1998 Cr2O3 + 6H+ = 2Cr3+ + 3H2O log K 8.52 (NECTAR CrIII "
                                  "table) on the NBS Cr2O3, Cr2+ by E0(Cr3+/Cr2+) = -0.407 V"),
)


def _cr_candidate_rows():
    rows = []
    for tag, cr3, cr2, src, prov in _CR_SETS:
        why = (f"WITHHELD candidate ({prov}): Cr3+ from -214.2 to -195.1 kJ/mol across the four compilations "
               "consulted (CRC, SSWS97, LLNL, Ball & Nordstrom 1998), contradictory by 66 mV in E0(Cr3+/Cr)")
        rows.append((f"Cr2+[{tag}]", f"Cr²⁺ ({tag})", 1, 0, 0, 2, "aq", cr2, "cation", src, "V3", why))
        rows.append((f"Cr3+[{tag}]", f"Cr³⁺ ({tag})", 1, 0, 0, 3, "aq", cr3, "cation", src, "V3", why))
        rows.append((f"CrOH+[{tag}]", f"CrOH⁺ ({tag})", 1, 1, 1, 1, "aq", _hydrolysis(cr2, 1, -5.5), "cation", "X", "V3",
                     f"WITHHELD candidate: Cr2+ + H2O = CrOH+ + H+ log K -5.5 (NIST46, NECTAR CrII table, which says "
                     f"the reliability of the Cr(II) data is in doubt) on the {tag} Cr2+, which is itself withheld"))
        for sid, formula, o, h, z, n_w, log_k in _CR_HYDROLYSIS:
            rows.append((f"{sid}[{tag}]", f"{formula} ({tag})", 1, o, h, z, "aq", _hydrolysis(cr3, n_w, log_k),
                         "anion_low" if z < 0 else "cation", "X", "V3",
                         f"WITHHELD candidate: Cr3+ + {n_w} H2O hydrolysis log K {log_k} (Brown & Ekberg 2016, NECTAR "
                         f"CrIII table) on the {tag} Cr3+, which is itself withheld"
                         + ("; neutral species, role 'cation' is bookkeeping only" if z == 0 else "")))
    return tuple(rows)


WITHHELD_SPECIES.update({
    "Cr": _cr_candidate_rows() + (
        ("H2CrO4[BN98]", "H₂CrO₄(aq) (BN98)", 1, 4, 2, 0, "aq", _H2CRO4_X, "anion_high", "X", "V3",
         "WITHHELD candidate: CrO4 2- + 2H+ = H2CrO4 log K 6.31 (Ball & Nordstrom 1998, NECTAR CrVI table) on the NBS "
         "CrO4 2-; HCrO4- + H+ = H2CrO4 -0.16 here, -0.20 Baes & Mesmer, but llnl.dat -1.32 and minteq.v4.dat -0.09. "
         "Its region (pH below about -0.2, above 1.2 V) has the same category as HCrO4- (transpassive)"),
        ("Cr2O7^2-", "Cr₂O₇²⁻", 2, 7, 0, -2, "aq", _CR2O7, "anion_high", "N", "V2",
         "EXCLUDED (polynuclear): NBS -1301.1 kJ/mol; 2HCrO4- = Cr2O7 2- + H2O log K 1.55 (NBS), 1.6 (Ball & "
         "Nordstrom 1998), 1.523 (Baes & Mesmer). Under the per-species activity convention it would take a domain "
         "from 10^-1.55 M (10^-1.75 M with the Ball & Nordstrom 2CrO4 2- + 2H+ constant 14.7 on the NBS CrO4 2- and "
         "HCrO4-), so the Cr activity is limited to 10^-6..10^-2 M"),
    ),
    "Mo": (
        ("Mo3+[CRC]", "Mo³⁺ (CRC)", 1, 0, 0, 3, "aq", _MO3_C, "cation", "C", "V3",
         "WITHHELD candidate: E0(H2MoO4 + 6H+ + 3e- = Mo3+ + 4H2O) = 0.43 V (Wikipedia data page, single "
         "atlas / Latimer lineage, no second compilation found) on the table's H2MoO4; E0(Mo3+/Mo) -0.200 V"),
    ) + tuple(
        (sid, formula, 7, 24, h, z, "aq", 7.0 * _MOO4 - 4.0 * _W - _K_LOG * log_k, "anion_high", "X", "V2",
         f"EXCLUDED (polynuclear): 7 MoO4 2- + {8 + h} H+ = {sid} + 4H2O log K {log_k} (Crea et al. 2017, NECTAR Mo "
         "table). Under the per-species activity convention the heptamolybdates take a domain from 10^-3.53 M, "
         "so the Mo activity is limited to 10^-6..10^-4 M")
        for sid, formula, h, z, log_k in _MO7),
    "Ti": (
        ("Ti2+[CRC]", "Ti²⁺ (CRC)", 1, 0, 0, 2, "aq", _TI2_C, "cation", "C", "V3",
         "WITHHELD candidate: E0(Ti2+/Ti) -1.63 V (Wikipedia data page); the same table's Ti(II)/Ti(III)/Ti(IV) "
         "couples are mutually inconsistent (TiO2+ -596.05 from TiO2+/Ti, -615.35 from TiO2+/Ti3+)"),
        ("Ti3+[CRC]", "Ti³⁺ (CRC)", 1, 0, 0, 3, "aq", _TI3_C, "cation", "C", "V3",
         "WITHHELD candidate: E0(Ti3+/Ti) -1.37 V (Wikipedia data page); no second compilation consulted gives a "
         "Ti3+ value"),
        ("TiOH2+[CRC]", "TiOH²⁺ (CRC)", 1, 1, 1, 2, "aq", _hydrolysis(_TI3_C, 1, -1.65), "cation", "X", "V3",
         "WITHHELD candidate: Ti3+ + H2O = TiOH2+ + H+ log K -1.65 +/- 0.11 (Brown & Ekberg 2016, NECTAR TiIII "
         "table; Perrin 1969 -1.29, Baes & Mesmer -2.2) on the CRC Ti3+, which is itself withheld"),
        ("TiO2+[CRC]", "TiO²⁺ (CRC, TiO²⁺/Ti)", 1, 1, 0, 2, "aq", _TIO2P_C, "cation", "C", "V3",
         "WITHHELD candidate: E0(TiO2+ + 2H+ + 4e- = Ti + H2O) -0.93 V (Wikipedia data page) gives -596.05 kJ/mol"),
        ("TiO[CRC]", "TiO (CRC)", 1, 1, 0, 0, "s", _TIO_C, "oxide", "C", "V3",
         "WITHHELD candidate: E0(TiO + 2H+ + 2e- = Ti + H2O) -1.31 V (Wikipedia data page) gives -489.92 kJ/mol"),
        ("TiO2+[CRC-b]", "TiO²⁺ (CRC, TiO²⁺/Ti³⁺)", 1, 1, 0, 2, "aq", _TIO2P_C2, "cation", "C", "V3",
         "WITHHELD candidate: E0(TiO2+/Ti3+) +0.19 V with E0(Ti3+/Ti) -1.37 V (same table) gives -615.35 kJ/mol, "
         "19 kJ/mol below the TiO2+/Ti route"),
        ("TiO[NBS]", "TiO (NBS)", 1, 1, 0, 0, "s", _TIO_NBS, "oxide", "N", "V3",
         "WITHHELD candidate: NBS TiO alpha -495.0 kJ/mol; NIST-JANAF (O-018) -513.28: 18.3 kJ/mol apart "
         "(95 mV in E0(TiO/Ti)). Both values give TiO a band between Ti and Ti2O3"),
        ("TiO[JANAF]", "TiO (JANAF)", 1, 1, 0, 0, "s", _TIO_J, "oxide", "J", "V3",
         "WITHHELD candidate: NIST-JANAF TiO alpha (O-018) -513.278 kJ/mol; NBS -495.0"),
        ("Ti4+[BE16]", "Ti⁴⁺ (BE16)", 1, 0, 0, 4, "aq", _TI4_X, "cation", "X", "V3",
         "WITHHELD candidate: TiO2(s) + 4H+ = Ti4+ + 2H2O log K -3.56 +/- 0.10 (Brown & Ekberg 2016, NECTAR TiIV "
         "table) on NBS rutile (the table does not name the polymorph); Baes & Mesmer give only Ti(OH)2 2+ based "
         "constants"),
        ("TiOOH+[BE16]", "TiO(OH)⁺ (BE16)", 1, 2, 1, 1, "aq", _TIOOH_X, "cation", "X", "V3",
         "WITHHELD candidate: TiO2(s) + H+ = TiOOH+ log K -6.06 +/- 0.30 (Brown & Ekberg 2016) on NBS rutile"),
        ("TiO(OH)2[BE16]", "TiO(OH)₂(aq) (BE16)", 1, 3, 2, 0, "aq", _TIOOH2_X, "cation", "X", "V3",
         "WITHHELD candidate: TiO2(s) + H2O = TiO(OH)2 log K -9.02 +/- 0.02 (Brown & Ekberg 2016) on NBS rutile; "
         "Baes & Mesmer about -4.8 (TiO2(c) + 2H2O = Ti(OH)4); neutral species, role 'cation' is bookkeeping only"),
        ("TiO(OH)3-[BE16]", "TiO(OH)₃⁻ (BE16)", 1, 4, 3, -1, "aq", _TIOOH3_X, "anion_low", "X", "V3",
         "WITHHELD candidate: TiO(OH)2 + H2O = TiO(OH)3- + H+ log K -11.9 +/- 0.5 (Brown & Ekberg 2016)"),
        ("Ti(OH)4[LLNL]", "Ti(OH)₄(aq) (LLNL)", 1, 4, 4, 0, "aq", _TIOH4_P, "cation", "P", "V3",
         "WITHHELD candidate: rutile + 2H2O = Ti(OH)4 log K -9.6452 (llnl.dat) on NBS rutile (anatase -8.5586); no "
         "domain for log a >= -6; neutral species, role 'cation' is bookkeeping only"),
        ("TiH2", "TiH₂", 1, 0, 2, 0, "s", _TIH2, "metal", "N", "V2",
         "EXCLUDED (scope: hydride): NBS TiH2 -80.3 kJ/mol. Ti + 2H+ + 2e- = TiH2 lies at E = 0.416 - 0.0592 pH, "
         "above the Ti/oxide lines, so the hydride, not the metal, is the equilibrium phase wherever the map shows "
         "Ti; role 'metal' is bookkeeping only (a reduced solid, not immunity)"),
        ("TiO2(anatase)", "TiO₂ (anatase)", 1, 2, 0, 0, "s", _ANATASE, "oxide", "N", "V2",
         "EXCLUDED (metastable): NBS anatase -884.5 kJ/mol, 5.0 kJ/mol above rutile (JANAF O-042 -883.27, 6.1 "
         "above); it never has a domain"),
    ),
})

# Alternative datasets whose domains, when added to the served table one set at a time, mark where the map is
# not valid (pourbaix_solver dataValidity). Each set is (id, label, member ids of WITHHELD_SPECIES).
CANDIDATE_SETS = {
    "Cr": tuple((f"Cr-{tag}", f"Cr(III)/Cr(II) with hydrolysis, {tag} values",
                 tuple(r[0] for r in WITHHELD_SPECIES["Cr"]
                       if r[0].endswith(f"[{tag}]") and not r[0].startswith("H2CrO4")))
                for tag, *_ in _CR_SETS),
    "Mo": (("Mo-CRC", "Mo(III): Mo3+ (CRC E0)", ("Mo3+[CRC]",)),),
    "Ti": (("Ti-CRC", "Ti(II)/Ti(III)/Ti(IV) and TiO, CRC E0 (TiO2+ from TiO2+/Ti)",
            ("Ti2+[CRC]", "Ti3+[CRC]", "TiOH2+[CRC]", "TiO2+[CRC]", "TiO[CRC]")),
           ("Ti-CRC-b", "TiO2+ from TiO2+/Ti3+ (CRC E0)", ("TiO2+[CRC-b]",)),
           ("Ti-TiO-NBS", "TiO (NBS)", ("TiO[NBS]",)),
           ("Ti-TiO-JANAF", "TiO (NIST-JANAF)", ("TiO[JANAF]",)),
           ("Ti-BE16", "Ti(IV) hydrolysis (Brown & Ekberg 2016)",
            ("Ti4+[BE16]", "TiOOH+[BE16]", "TiO(OH)2[BE16]", "TiO(OH)3-[BE16]")),
           ("Ti-LLNL", "Ti(OH)4(aq) (llnl.dat)", ("Ti(OH)4[LLNL]",)),
           ("Ti-hydride", "TiH2 (NBS; hydride outside the oxide/ion table)", ("TiH2",))),
}
# The Cr set made of BN98 rows also carries H2CrO4 (same compilation).
CANDIDATE_SETS["Cr"] = CANDIDATE_SETS["Cr"] + (("Cr-H2CrO4", "H2CrO4 (Ball & Nordstrom 1998)", ("H2CrO4[BN98]",)),)

# Species that matter for the element but have no value in any compilation consulted (not represented).
UNSOURCED_SPECIES = {
    "Mo": (("MoO₂²⁺", "cationic Mo(VI) species of strongly acid solution: no constant in NBS 1982, the NECTAR Mo "
                      "table, llnl.dat or minteq.v4.dat; below about pH 1 the dissolved Mo(VI) domain is shown as "
                      "H2MoO4(aq)"),
           ("Mo(V)", "no aqueous Mo(V) species with a sourced value"),),
    "Cr": (("Cr(OH)₃ (amorphous)", "metastable solid: Cr(OH)3(s) + 3H+ = Cr3+ + 3H2O log K 9.41 (Brown & Ekberg "
                                   "2016) / 9.35 (Ball & Nordstrom 1998) against 4.26 per Cr for Cr2O3 (Ball & "
                                   "Nordstrom): more soluble than Cr2O3, and its value depends on the withheld Cr3+"),),
}

UNAVAILABLE_ELEMENTS = {}

ROW_KEYS = ("id", "formula", "x", "o", "h", "z", "phase", "dfG_kJ_mol", "role", "source",
            "verification", "evidence")


def _row_dict(row):
    out = dict(zip(ROW_KEYS, row))
    out["category"] = CATEGORY_BY_ROLE[out["role"]]
    return out


def available_elements():
    return list(_ROWS)


def species_rows(element):
    """Rows (list of dicts) used by the engine for ``element`` (KeyError when unavailable)."""
    return [_row_dict(r) for r in _ROWS[element]]


def water_dfg_kj_mol(element):
    return ELEMENT_SET[element][1]


def activity_range(element):
    """(lo, hi) log10 dissolved activity accepted for ``element``."""
    return ACTIVITY_LOG10_RANGE_BY_ELEMENT.get(element, ACTIVITY_LOG10_RANGE)


def withheld_rows(element):
    return [_row_dict(r) for r in WITHHELD_SPECIES.get(element, ())]


def candidate_sets(element):
    """[{id, label, speciesIds}] of the withheld alternative datasets of ``element`` (empty for most)."""
    return [{"id": sid, "label": label, "speciesIds": list(ids)} for sid, label, ids in CANDIDATE_SETS.get(element, ())]


def candidate_rows(element, set_id):
    """Rows (dicts) of one candidate set, in the set's order."""
    by_id = {r[0]: r for r in WITHHELD_SPECIES.get(element, ())}
    ids = next(ids for sid, _, ids in CANDIDATE_SETS[element] if sid == set_id)
    return [_row_dict(by_id[i]) for i in ids]


def unsourced_species(element):
    return [{"formula": f, "reason": r} for f, r in UNSOURCED_SPECIES.get(element, ())]


def build_document():
    elements = {}
    for symbol in NAMES:
        entry = {"name": NAMES[symbol]}
        if symbol in _ROWS:
            set_id, h2o, note = ELEMENT_SET[symbol]
            entry.update({
                "available": True,
                "sourceSet": set_id,
                "sourceSetNote": note,
                "waterDfG_kJ_mol": h2o,
                "referenceCation": REFERENCE_CATION[symbol],
                "activityLog10Range": list(activity_range(symbol)),
                "species": [_row_dict(r) for r in _ROWS[symbol]],
                "candidateSets": candidate_sets(symbol),
                "unsourcedSpecies": unsourced_species(symbol),
            })
        else:
            entry.update({"available": False, "reason": UNAVAILABLE_ELEMENTS[symbol]})
        if symbol in WITHHELD_SPECIES:
            entry["withheldSpecies"] = [_row_dict(r) for r in WITHHELD_SPECIES[symbol]]
        elements[symbol] = entry
    return {
        "schema": SCHEMA,
        "generatedBy": "python/pourbaix_species_25c.py",
        "temperature_C": TEMPERATURE_C,
        "temperature_K": TEMPERATURE_K,
        "constants": {
            "gasConstantR_J_molK": physical_constants.GAS_CONSTANT_R.value,
            "faraday_C_mol": physical_constants.FARADAY.value,
            "ln10": LN10,
            "calorie_J": CAL_J,
        },
        "activity": {
            "log10Range": list(ACTIVITY_LOG10_RANGE),
            "log10Default": ACTIVITY_LOG10_DEFAULT,
            "coefficients": "ideal (γ=1), no ionic-strength correction",
        },
        "box": dict(BOX),
        "water": {
            "dfG_NBS_kJ_mol": WATER_DFG_NBS_KJ_MOL,
            "e0_O2_H2O_V": -WATER_DFG_NBS_KJ_MOL * 1000.0 / (2.0 * physical_constants.FARADAY.value),
        },
        "roles": dict(CATEGORY_BY_ROLE),
        "tieBreak": "table order: metal, cations, solids, anions (first species wins an exact tie)",
        "formulaBookkeeping": (
            "per species: x metal atoms, o O atoms, h H atoms, charge z; m=(2o-h)/x H+ released and "
            "n=(z+2o-h)/x electrons per metal atom; g=[dfG-o*dfG(H2O)+RT ln a]/x - m ln10 RT pH - nFE"),
        "elements": elements,
    }


def render_json(document=None):
    document = build_document() if document is None else document
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def emit(path=GENERATED_JSON):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(render_json())
    return path


def is_stale(path=GENERATED_JSON):
    """True when the committed file is not byte-identical to a fresh render."""
    if not path.exists():
        return True
    return path.read_bytes() != render_json().encode("utf-8")


def main(argv):
    if "--emit" in argv:
        print(f"wrote {emit()}")
        return 0
    if "--check" in argv:
        if is_stale():
            print(f"stale: {GENERATED_JSON}", file=sys.stderr)
            return 1
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
