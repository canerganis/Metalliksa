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
Verification levels (reached by this module, not by the table author):
  V1  equals an open table value within 0.5 kJ/mol (OpenStax Chemistry 2e App. G, CC BY 4.0;
      CHNOSZ OBIGT; SKI 95:73 Table 3).
  V2  reproduces a published E0 within 10 mV, or an independently published open equilibrium
      quantity (reaction free energy) within 2.5 kJ/mol.
  V3  not confirmed: the row is NOT used; its element or row is withheld (see
      WITHHELD_SPECIES / UNAVAILABLE_ELEMENTS).

CLI (from python/):
  python pourbaix_species_25c.py --emit    write src/generated/pourbaixSpecies25C.json (LF)
  python pourbaix_species_25c.py --check   exit 1 when the committed JSON differs from a fresh emit
"""

import json
import math
import sys
from pathlib import Path

import physical_constants

SCHEMA = "pourbaix-species-25c-v1"
REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATED_JSON = REPO_ROOT / "src" / "generated" / "pourbaixSpecies25C.json"

CAL_J = 4.184  # J per thermochemical calorie (Atlas mu0 values are in cal/mol)
TEMPERATURE_C = 25.0
TEMPERATURE_K = physical_constants.ZERO_CELSIUS_K.value + TEMPERATURE_C
LN10 = math.log(10.0)

ACTIVITY_LOG10_RANGE = (-8.0, 0.0)
ACTIVITY_LOG10_DEFAULT = -6.0
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
        ("NiO2", "NiO₂", 1, 2, 0, 0, "s", _NI_NIO2, "oxide", "E", "V2",
         "ESTIMATE anchored to Ni2+: E0(NiO2/Ni2+, acid) = 1.593 V (atlas / CRC / Wikipedia data page: one "
         "lineage, not independent); the NEA volume has no Ni(III/IV) oxide and the atlas calls the higher "
         "nickel oxides uncertain. The domain lies above the O2 line (about 5 mV) at every pH"),
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
         "negative; known sensitivity (Zn2+/ZnO pH 8.77 here, 8.58 with -320.5); sets not mixed"),
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
}

ELEMENT_SET = {
    "Fe": ("A", _FE_H2O, "Atlas set (Pourbaix 1974); FeO4 2- derived from Latimer E0 (L)"),
    "Ni": ("E", _NI_H2O, "NEA-TDB set (Gamsjaeger et al. 2005, Chemical Thermodynamics of Nickel, Table III-1) with "
                         "CODATA water; NiO2 is an estimate anchored to Ni2+ (see its row). Ni3O4 and Ni2O3 are "
                         "withheld atlas rows"),
    "Cu": ("N", WATER_DFG_NBS_KJ_MOL, "NBS set (Wagman 1982)"),
    "Zn": ("N", WATER_DFG_NBS_KJ_MOL, "NBS set (Wagman 1982), ZnO see row evidence"),
    "Mg": ("N", WATER_DFG_NBS_KJ_MOL, "NBS set (Wagman 1982)"),
    "Al": ("O", _AL_H2O, "CHNOSZ OBIGT set: Al3+ and Al(OH)4- (Tagirov & Schott 2001) with gibbsite "
                         "(Robie, Hemingway & Fisher 1978) and SUPCRT92 water. The solid is gibbsite; "
                         "boehmite and corundum are listed under withheldSpecies (metastable/excluded). "
                         "The mononuclear hydrolysis species AlOH2+, Al(OH)2+ and Al(OH)3(aq) (TS01) are "
                         "omitted as for the other elements: they have no domain for log a >= -7.16; at "
                         "log a = -8 AlOH2+ would take pH 4.96-5.38 from Al3+ and gibbsite"),
}

# Couple used for the informational standardE0_V (unit activity, pH independent).
REFERENCE_CATION = {"Fe": "Fe2+", "Ni": "Ni2+", "Cu": "Cu2+", "Zn": "Zn2+", "Mg": "Mg2+", "Al": "Al3+"}

NAMES = {
    "Fe": "Iron (Fe-H₂O System)", "Cr": "Chromium (Cr-H₂O System)", "Ni": "Nickel (Ni-H₂O System)",
    "Ti": "Titanium (Ti-H₂O System)", "Al": "Aluminum (Al-H₂O Amphoteric System)",
    "Cu": "Copper (Cu-H₂O System)", "Zn": "Zinc (Zn-H₂O System Amphoteric)",
    "Mg": "Magnesium (Mg-H₂O System)",
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

UNAVAILABLE_ELEMENTS = {
    "Cr": ("Blocked until WP-Cr: alkaline Cr(III) (CrO2-/Cr(OH)4-) has no verified value; close from "
           "Ball & Nordstrom, J. Chem. Eng. Data 43 (1998) 895."),
    "Ti": ("Published aqueous Ti data are mutually inconsistent (TiO2+ -596 or -615 kJ/mol from the "
           "same E0 table; Ti/TiO2 -1.076 V with rutile vs -0.86 V with the atlas oxide). No verified "
           "Ti-H2O data."),
    "Mo": "No sourced Mo-H2O data.",
}

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
                "species": [_row_dict(r) for r in _ROWS[symbol]],
            })
        else:
            entry.update({"available": False, "reason": UNAVAILABLE_ELEMENTS[symbol]})
        if symbol in WITHHELD_SPECIES:
            entry["withheldSpecies"] = [_row_dict(r) for r in WITHHELD_SPECIES[symbol]]
        elements[symbol] = entry
    elements_unavailable = {"Mo": {"name": "Molybdenum", "available": False,
                                   "reason": UNAVAILABLE_ELEMENTS["Mo"]}}
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
        "elements": {**elements, **elements_unavailable},
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
