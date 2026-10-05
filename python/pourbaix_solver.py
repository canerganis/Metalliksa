#!/usr/bin/env python3
"""
MetalliX single-element M-H2O Pourbaix (E-pH) solver, 25 C only.

Engine: minimum Gibbs energy per metal atom over a sourced species table
(pourbaix_species_25c.py), fixed activities, ideal solution (gamma = 1). The stable
species at (pH, E) is argmin g_i with

    g_i = [dfG_i - o_i*dfG(H2O) + RT ln a_i] / x_i - m_i ln10 RT pH - n_i F E,
    m_i = (2 o_i - h_i)/x_i,   n_i = (z_i + 2 o_i - h_i)/x_i,   a_i = 1 for solids,

(exact one-element Gibbs minimisation, Persson et al., Phys. Rev. B 85, 235438 (2012)).
Every g_i is affine in (pH, E), so each domain is a convex polygon and each boundary an
exact line g_i = g_j; no E0 or slope is entered by hand. Temperature is limited to 25 C:
the table has no consistent entropies or heat capacities for the atlas-sourced species.
The chloride/Epit model was removed (no sourced generic Epit exists).
"""

import sys
import json
import math
import time

import physical_constants
import pourbaix_species_25c as species_table
from input_validation import (MISSING_PROPERTY, NON_FINITE, OUT_OF_RANGE, UNKNOWN_ELEMENT, ValidationError,
                              require_finite, require_range, validation_envelope)

# Phase 6a value step (b): R and F are the exact SI 2019 products N_A*k and N_A*e
# from physical_constants (they replaced the CODATA printed truncations
# 8.314462618 / 96485.33212; relative change 1.8e-11 / 3.4e-11).
R_GAS = physical_constants.GAS_CONSTANT_R.value  # J / (mol * K), exact
F_FARADAY = physical_constants.FARADAY.value  # C / mol, exact
ZERO_CELSIUS_K = physical_constants.ZERO_CELSIUS_K.value  # 273.15 K
# Not in physical_constants: its CIAAW abridged Cl value is not registered and
# would be 35.45, not the 35.453 used here, so this stays local until step (b).
CHLORIDE_MOLAR_MASS_G_MOL = 35.453

ENGINE_ID = "pourbaix-gibbs-25c-v6"
SUPPORTED_TEMPERATURE_C = 25.0
TEMPERATURE_TOLERANCE_C = 0.5
T_KELVIN = ZERO_CELSIUS_K + SUPPORTED_TEMPERATURE_C
LN10 = math.log(10.0)
RT = R_GAS * T_KELVIN  # J/mol

# Error codes of this engine. input_validation.ERROR_CODES is pinned to seven design codes
# (test_input_validation), so these are raised through a subclass that carries the same
# envelope shape (validation_envelope reads only .to_json()).
TEMPERATURE_UNSUPPORTED = "TEMPERATURE_UNSUPPORTED"
POURBAIX_DATA_UNAVAILABLE = "POURBAIX_DATA_UNAVAILABLE"
UNKNOWN_REFERENCE_ELECTRODE = "UNKNOWN_REFERENCE_ELECTRODE"
POURBAIX_ERROR_CODES = frozenset({TEMPERATURE_UNSUPPORTED, POURBAIX_DATA_UNAVAILABLE,
                                  UNKNOWN_REFERENCE_ELECTRODE})


class PourbaixValidationError(ValidationError):
    """ValidationError with a Pourbaix-specific code (same code/field/message/detail contract)."""

    def __init__(self, code, field, message, detail=None):
        if code not in POURBAIX_ERROR_CODES:
            raise ValueError(f"Unknown Pourbaix validation error code {code!r}")
        ValueError.__init__(self, f"[{code}] {field}: {message}")
        self.code = code
        self.field = field
        self.message = message
        self.detail = dict(detail or {})


# Reference Electrode Standard Offsets vs SHE at 25°C
REF_ELECTRODE_OFFSETS = {
    "SHE": 0.000,
    "SCE": 0.241,               # Saturated Calomel Electrode (Sat. KCl)
    "Ag/AgCl (3M KCl)": 0.207,   # Silver/Silver Chloride (3M KCl)
    "Ag/AgCl (Sat KCl)": 0.197,  # Sat. Ag/AgCl
    "CSE": 0.316,               # Copper/Copper Sulfate Electrode
    "MMS": 0.640,               # Mercury/Mercurous Sulfate (Sat. K2SO4)
}

# Elements the engine knows. ``available`` follows the species table; the numbers come
# from the table, never from this dictionary. (standardE0_V is the unit-activity E0 of the
# metal / reference-cation couple derived from the table, None when unavailable.)
POURBAIX_ELEMENT_SYSTEMS = {
    "Fe": {"name": species_table.NAMES["Fe"], "atomicMass": physical_constants.atomic_weight("Fe")},
    "Cr": {"name": species_table.NAMES["Cr"], "atomicMass": physical_constants.atomic_weight("Cr")},
    "Ni": {"name": species_table.NAMES["Ni"], "atomicMass": physical_constants.atomic_weight("Ni")},
    "Ti": {"name": species_table.NAMES["Ti"], "atomicMass": physical_constants.atomic_weight("Ti")},
    "Al": {"name": species_table.NAMES["Al"], "atomicMass": physical_constants.atomic_weight("Al")},
    "Cu": {"name": species_table.NAMES["Cu"], "atomicMass": physical_constants.atomic_weight("Cu")},
    "Zn": {"name": species_table.NAMES["Zn"], "atomicMass": physical_constants.atomic_weight("Zn")},
    "Mg": {"name": species_table.NAMES["Mg"], "atomicMass": physical_constants.atomic_weight("Mg")},
    "Mo": {"name": species_table.NAMES["Mo"], "atomicMass": physical_constants.atomic_weight("Mo")},
}
# Elements without a Python system entry that the lab still names: reported as unavailable (none since v5).
UNAVAILABLE_ONLY_ELEMENTS = ()

# ---------------------------------------------------------------------------------------
# Fixed category texts (one text per category; no rate, protectiveness or pitting claims).
# ---------------------------------------------------------------------------------------
CATEGORY_IMMUNITY = species_table.CATEGORY_BY_ROLE["metal"]
CATEGORY_ACID = species_table.CATEGORY_BY_ROLE["cation"]
CATEGORY_ALKALINE = species_table.CATEGORY_BY_ROLE["anion_low"]
CATEGORY_PASSIVATION = species_table.CATEGORY_BY_ROLE["oxide"]
CATEGORY_TRANSPASSIVE = species_table.CATEGORY_BY_ROLE["anion_high"]
OUTSIDE_WATER_LABEL = "outside water stability (metastable)"
INSIDE_WATER_LABEL = "inside water stability"

CATEGORY_TEXTS = {
    CATEGORY_IMMUNITY: {
        "mechanismId": "metal_stable",
        "mechanismTitle": "Metal is the stable phase (thermodynamic immunity)",
        "mechanismDetails": "The metal has the lowest Gibbs energy of all tabulated species at this "
                            "pH, potential and dissolved activity; oxidation is not thermodynamically favoured.",
        "riskLevel": "Immune",
        "color": "#0284c7",
    },
    CATEGORY_ACID: {
        "mechanismId": "cation_stable",
        "mechanismTitle": "Dissolved cation is the stable phase (acidic corrosion domain)",
        "mechanismDetails": "A dissolved metal cation has the lowest Gibbs energy at this pH, potential and "
                            "dissolved activity; the metal is thermodynamically unstable. The map gives no "
                            "corrosion rate.",
        "riskLevel": "Severe Corrosion",
        "color": "#ef4444",
    },
    CATEGORY_ALKALINE: {
        "mechanismId": "anion_stable",
        "mechanismTitle": "Dissolved oxyanion is the stable phase (alkaline corrosion domain)",
        "mechanismDetails": "A dissolved hydroxo/oxo anion has the lowest Gibbs energy at this pH, potential and "
                            "dissolved activity; the metal and its oxides are thermodynamically unstable. The map "
                            "gives no corrosion rate.",
        "riskLevel": "High Risk",
        "color": "#f97316",
    },
    CATEGORY_PASSIVATION: {
        "mechanismId": "solid_oxide_stable",
        "mechanismTitle": "Solid oxide or hydroxide is the stable phase (thermodynamic passivation domain)",
        "mechanismDetails": "A solid oxide or hydroxide has the lowest Gibbs energy at this pH, potential and "
                            "dissolved activity. This is an equilibrium statement: it does not establish that a "
                            "film forms, is protective, or resists chloride breakdown.",
        "riskLevel": "Stable Passivity",
        "color": "#10b981",
    },
    CATEGORY_TRANSPASSIVE: {
        "mechanismId": "oxyanion_high_potential_stable",
        "mechanismTitle": "High-valence oxyanion or oxyacid is the stable phase (transpassive domain)",
        "mechanismDetails": "A high-valence dissolved oxyanion (or its neutral oxyacid, e.g. H₂MoO₄) has the lowest "
                            "Gibbs energy at this pH, potential and dissolved activity; the solid oxide is "
                            "thermodynamically unstable.",
        "riskLevel": "High Risk",
        "color": "#e11d48",
    },
}

CATEGORY_MITIGATION = {
    CATEGORY_ACID: [
        "Pourbaix map: polarising below the computed metal-domain boundary at this pH would place the point in the metal-stability domain.",
        "Changing pH moves the point across the computed boundaries (see analyticalBoundaries); inhibitors and kinetics are not assessed by this map.",
    ],
    CATEGORY_ALKALINE: [
        "Lowering pH moves the point out of the dissolved-anion domain (see analyticalBoundaries); stress-corrosion susceptibility is alloy- and stress-dependent and is not assessed by this map.",
    ],
    CATEGORY_TRANSPASSIVE: [
        "Lowering the potential below the passivation/transpassive boundary removes the thermodynamic drive to form the high-valence oxyanion (see analyticalBoundaries).",
    ],
    CATEGORY_PASSIVATION: [
        "A solid oxide/hydroxide is the equilibrium phase here. Film protectiveness, chloride breakdown (pitting) and kinetics are not assessed by this map.",
    ],
}

# ---------------------------------------------------------------------------------------
# Thermodynamics
# ---------------------------------------------------------------------------------------


def calculate_nernst_slope(temperature_C=25.0):
    t_kelvin = ZERO_CELSIUS_K + float(temperature_C)
    r_gas = R_GAS
    f_faraday = F_FARADAY
    return (2.302585093 * r_gas * t_kelvin) / f_faraday # 0.05916 V/pH at 25°C


_E0_O2_H2O_V = -species_table.WATER_DFG_NBS_KJ_MOL * 1000.0 / (2.0 * F_FARADAY)  # 1.2288 V


def generate_water_stability_lines(temperature_C=25.0):
    """Water lines at 25 C: E(H+/H2) = -k pH, E(O2/H2O) = 1.2288 - k pH (k = ln10 RT/F)."""
    nernst_slope = calculate_nernst_slope(SUPPORTED_TEMPERATURE_C)
    e0_oer = _E0_O2_H2O_V
    line_a = []
    line_b = []
    for ph_i in range(16):  # 0 to 15
        ph = float(ph_i)
        line_a.append({"pH": ph, "E_V_SHE": round(0.0 - nernst_slope * ph, 4)})
        line_b.append({"pH": ph, "E_V_SHE": round(e0_oer - nernst_slope * ph, 4)})
    return {
        "nernstSlope": round(nernst_slope, 5),
        "e0_OER": round(e0_oer, 4),
        "line_a_hydrogen_HER": line_a,
        "line_b_oxygen_OER": line_b,
        "equation_HER": f"E = 0.000 - {nernst_slope:.4f}·pH (Line a: 2H⁺ + 2e⁻ ⇌ H₂)",
        "equation_OER": f"E = {e0_oer:.4f} - {nernst_slope:.4f}·pH (Line b: O₂ + 4H⁺ + 4e⁻ ⇌ 2H₂O)",
    }


def _water_lines_at(ph):
    k = RT * LN10 / F_FARADAY
    return 0.0 - k * ph, _E0_O2_H2O_V - k * ph


class _Species:
    __slots__ = ("id", "formula", "x", "o", "h", "z", "phase", "dfG_kJ", "role", "category",
                 "c0", "cpH", "cE", "n", "m")


_COEFF_CACHE = {}


def _coefficients(element, log_a):
    """[(species, c0 J, cpH J/pH, cE J/V)] for g per metal atom, in table order."""
    key = (element, float(log_a))
    cached = _COEFF_CACHE.get(key)
    if cached is not None:
        return cached
    out = _coefficients_of(species_table.species_rows(element), species_table.water_dfg_kj_mol(element), log_a)
    _COEFF_CACHE[key] = out
    return out


def _coefficients_of(rows, h2o_kj, log_a):
    """Same as ``_coefficients`` for explicit species rows (used for the withheld candidate sets)."""
    h2o = h2o_kj * 1000.0
    out = []
    for row in rows:
        sp = _Species()
        for name in ("id", "formula", "x", "o", "h", "z", "phase", "role", "category"):
            setattr(sp, name, row[name])
        sp.dfG_kJ = row["dfG_kJ_mol"]
        ln_a = 0.0 if row["phase"] == "s" else log_a * LN10
        sp.m = (2 * row["o"] - row["h"]) / row["x"]
        sp.n = (row["z"] + 2 * row["o"] - row["h"]) / row["x"]
        sp.c0 = (sp.dfG_kJ * 1000.0 - row["o"] * h2o + RT * ln_a) / row["x"]
        sp.cpH = -sp.m * LN10 * RT
        sp.cE = -sp.n * F_FARADAY
        out.append(sp)
    return out


def _argmin(coeffs, ph, e_she):
    best = None
    best_g = None
    for sp in coeffs:  # strict < keeps the earlier table row on an exact tie
        g = sp.c0 + sp.cpH * ph + sp.cE * e_she
        if best is None or g < best_g:
            best, best_g = sp, g
    return best


def _metal_boundary_E(coeffs, ph):
    """Highest E (V SHE) at which the metal is still the argmin at this pH (None if unbounded)."""
    bound = None
    for sp in coeffs:
        if sp.n > 0:  # g_i >= 0 (metal g = 0)  <=>  E <= (c0 + cpH pH) / (n F)
            e = (sp.c0 + sp.cpH * ph) / (sp.n * F_FARADAY)
            bound = e if bound is None else min(bound, e)
    return bound


def _clip_polygon(poly, a, b, c):
    """Sutherland-Hodgman: keep points with c + a*pH + b*E <= 0."""
    out = []
    for k in range(len(poly)):
        p, q = poly[k], poly[(k + 1) % len(poly)]
        fp, fq = c + a * p[0] + b * p[1], c + a * q[0] + b * q[1]
        if fp <= 0:
            out.append(p)
        if (fp < 0 < fq) or (fq < 0 < fp):
            t = fp / (fp - fq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out


def _polygon_area(poly):
    return 0.5 * abs(sum(poly[k][0] * poly[(k + 1) % len(poly)][1] - poly[(k + 1) % len(poly)][0] * poly[k][1]
                         for k in range(len(poly))))


def compute_domains(element, log_a, coeffs=None):
    """species id -> convex polygon [(pH, E)] clipped to the box (species with area > 1e-9 only)."""
    box = species_table.BOX
    coeffs = _coefficients(element, log_a) if coeffs is None else coeffs
    domains = {}
    for sp in coeffs:
        poly = [(box["pH_min"], box["E_min_V_SHE"]), (box["pH_max"], box["E_min_V_SHE"]),
                (box["pH_max"], box["E_max_V_SHE"]), (box["pH_min"], box["E_max_V_SHE"])]
        for other in coeffs:
            if other is sp:
                continue
            poly = _clip_polygon(poly, sp.cpH - other.cpH, sp.cE - other.cE, sp.c0 - other.c0)
            if not poly:
                break
        if poly and _polygon_area(poly) > 1e-9:
            domains[sp.id] = poly
    return domains


def _line_between(a, b):
    """Boundary g_a = g_b as ('sloped', E0, slope) or ('vertical', pH); None when identical."""
    d0, dp, de = a.c0 - b.c0, a.cpH - b.cpH, a.cE - b.cE
    if abs(de) < 1e-9:
        if abs(dp) < 1e-9:
            return None
        return ("vertical", -d0 / dp + 0.0)
    return ("sloped", -d0 / de + 0.0, -dp / de + 0.0)  # + 0.0 turns -0.0 into 0.0


def boundary_line(element, id_a, id_b, log_a=-6.0):
    """Exact line g_a = g_b of two table species: {'type': 'sloped', 'E_V_SHE_at_pH0', 'slope_V_per_pH'}
    or {'type': 'vertical', 'pH'} (None when the species are identical). The couple need not be
    a boundary of the diagram."""
    by_id = {sp.id: sp for sp in _coefficients(element, float(log_a))}
    line = _line_between(by_id[id_a], by_id[id_b])
    if line is None:
        return None
    if line[0] == "vertical":
        return {"type": "vertical", "pH": line[1]}
    return {"type": "sloped", "E_V_SHE_at_pH0": line[1], "slope_V_per_pH": line[2]}


def _equation(a, b):
    """Balanced reaction text A + w H2O <=> B + p H+ + q e- on a common metal count."""
    m_atoms = a.x * b.x // math.gcd(a.x, b.x)
    ca, cb = m_atoms // a.x, m_atoms // b.x
    w = b.o * cb - a.o * ca
    p = round(b.m * m_atoms - a.m * m_atoms)
    q = round(b.n * m_atoms - a.n * m_atoms)
    left, right = [], []

    def term(n, label):
        return label if n == 1 else f"{n}{label}"
    left.append(term(ca, a.formula))
    right.append(term(cb, b.formula))
    for n, label in ((w, "H₂O"), (p, "H⁺"), (q, "e⁻")):
        if n > 0:
            (left if label == "H₂O" else right).append(term(n, label))
        elif n < 0:
            (right if label == "H₂O" else left).append(term(-n, label))
    return " + ".join(left) + " ⇌ " + " + ".join(right)


def compute_boundaries(element, log_a):
    """Shared polygon edges with exact line equations, clipped to the box and to the region
    where both species are minimal (g_a = g_b <= g_k for every other species k)."""
    box = species_table.BOX
    coeffs = _coefficients(element, log_a)
    result = []
    for ia in range(len(coeffs)):
        for ib in range(ia + 1, len(coeffs)):
            a, b = coeffs[ia], coeffs[ib]
            line = _line_between(a, b)
            if line is None:
                continue
            if line[0] == "vertical":
                ph0 = line[1]
                if not box["pH_min"] <= ph0 <= box["pH_max"]:
                    continue
                lo, hi = box["E_min_V_SHE"], box["E_max_V_SHE"]

                def point(t, ph0=ph0):
                    return ph0, t
                slope_of = lambda k, a=a: (a.cE - k.cE)
                const_of = lambda k, a=a, ph0=ph0: (a.c0 - k.c0) + (a.cpH - k.cpH) * ph0
            else:
                e0, slope = line[1], line[2]
                # parameter t = pH, E = e0 + slope * pH, with E kept inside the box
                lo, hi = box["pH_min"], box["pH_max"]
                if abs(slope) > 1e-12:
                    t_a = (box["E_min_V_SHE"] - e0) / slope
                    t_b = (box["E_max_V_SHE"] - e0) / slope
                    lo, hi = max(lo, min(t_a, t_b)), min(hi, max(t_a, t_b))
                elif not box["E_min_V_SHE"] <= e0 <= box["E_max_V_SHE"]:
                    continue

                def point(t, e0=e0, slope=slope):
                    return t, e0 + slope * t
                const_of = lambda k, a=a, e0=e0: (a.c0 - k.c0) + (a.cE - k.cE) * e0
                slope_of = lambda k, a=a, slope=slope: (a.cpH - k.cpH) + (a.cE - k.cE) * slope
            # keep g_a <= g_k: const + slope_coeff * t <= 0
            for k in coeffs:
                if k is a or k is b or lo >= hi:
                    continue
                c, s = const_of(k), slope_of(k)
                if abs(s) < 1e-12:
                    if c > 0:
                        lo = hi
                    continue
                t_cross = -c / s
                if s > 0:
                    hi = min(hi, t_cross)
                else:
                    lo = max(lo, t_cross)
            if hi - lo <= 1e-9:
                continue
            p_lo, p_hi = point(lo), point(hi)
            entry = {
                "id": f"{a.id}__{b.id}",
                "name": f"{a.formula} / {b.formula}",
                "equation": _equation(a, b),
                "boundaryType": f"{a.category} / {b.category}" if a.category != b.category
                else f"{a.category}: {a.formula} / {b.formula}",
                "speciesA": a.formula,
                "speciesB": b.formula,
                "speciesAId": a.id,
                "speciesBId": b.id,
                "points": [{"pH": p_lo[0], "E_V_SHE": p_lo[1]}, {"pH": p_hi[0], "E_V_SHE": p_hi[1]}],
            }
            entry["line"] = boundary_line(element, a.id, b.id, log_a)
            result.append(entry)
    return result


# ---------------------------------------------------------------------------------------
# Data validity: where a withheld candidate set would change the stable species
# ---------------------------------------------------------------------------------------

_CANDIDATE_CACHE = {}


def _candidate_coefficients(element, log_a):
    """[(set id, served + set coefficients, set member ids)] in the table's candidate-set order."""
    key = (element, float(log_a))
    cached = _CANDIDATE_CACHE.get(key)
    if cached is not None:
        return cached
    served = species_table.species_rows(element)
    h2o = species_table.water_dfg_kj_mol(element)
    out = []
    for cset in species_table.candidate_sets(element):
        rows = species_table.candidate_rows(element, cset["id"])
        out.append((cset["id"], _coefficients_of(served + rows, h2o, log_a), frozenset(cset["speciesIds"])))
    _CANDIDATE_CACHE[key] = out
    return out


def withheld_species_at(element, ph, e_she, log_a):
    """[(candidate set id, species id)] of every candidate set whose own species would be the argmin here."""
    hits = []
    for set_id, coeffs, members in _candidate_coefficients(element, log_a):
        sp = _argmin(coeffs, ph, e_she)
        if sp.id in members:
            hits.append((set_id, sp.id))
    return hits


def compute_withheld_regions(element, log_a):
    """Domains (convex polygons) that the species of each candidate set would take when that set alone is added
    to the served table: [{candidateSet, speciesId, formula, category, polygon}]. The map is not valid there."""
    regions = []
    for set_id, coeffs, members in _candidate_coefficients(element, log_a):
        by_id = {sp.id: sp for sp in coeffs}
        for sid, poly in compute_domains(element, log_a, coeffs).items():
            if sid in members:
                regions.append({"candidateSet": set_id, "speciesId": sid, "formula": by_id[sid].formula,
                                "category": by_id[sid].category,
                                "polygon": [{"pH": p[0], "E_V_SHE": p[1]} for p in poly]})
    return regions


def free_ph_windows(regions):
    """pH intervals of the box in which no withheld region touches the water stability window (area > 1e-9)."""
    box = species_table.BOX
    k = RT * LN10 / F_FARADAY
    blocked = []
    for r in regions:
        poly = [(q["pH"], q["E_V_SHE"]) for q in r["polygon"]]
        poly = _clip_polygon(poly, -k, -1.0, 0.0)  # E >= -k pH (line a)
        if poly:
            poly = _clip_polygon(poly, k, 1.0, -_E0_O2_H2O_V)  # E <= 1.2288 - k pH (line b)
        if poly and _polygon_area(poly) > 1e-9:
            blocked.append((min(p[0] for p in poly), max(p[0] for p in poly)))
    blocked.sort()
    free, start = [], box["pH_min"]
    for lo, hi in blocked:
        if lo > start:
            free.append([start, lo])
        start = max(start, hi)
    if start < box["pH_max"]:
        free.append([start, box["pH_max"]])
    return free


def _data_validity_block(element, log_a):
    regions = compute_withheld_regions(element, log_a)
    sets = species_table.candidate_sets(element)
    return {
        "status": "withheld-species-regions" if regions else (
            "withheld-candidates-without-region" if sets else "no-withheld-candidates"),
        "activityRange_log10": list(species_table.activity_range(element)),
        "rule": "a region is the domain that a withheld candidate species would take if its candidate set alone were "
                "added to the served table; the map is not valid inside any region",
        "candidateSets": sets,
        "regions": regions,
        "pHWindowsFreeOfRegionsInsideWater": free_ph_windows(regions),
        "unsourcedSpecies": species_table.unsourced_species(element),
    }


# ---------------------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------------------


def _check_element(element):
    if isinstance(element, str) and element in UNAVAILABLE_ONLY_ELEMENTS:
        return  # reported as unavailable after the temperature check
    if not isinstance(element, str) or element not in POURBAIX_ELEMENT_SYSTEMS:
        # Phase 6a: no silent substitution of the Fe system for an unknown element.
        supported = list(POURBAIX_ELEMENT_SYSTEMS)
        raise ValidationError(
            UNKNOWN_ELEMENT, "element",
            f"No Pourbaix system for element {element!r}; supported: {', '.join(supported)}.",
            {"element": repr(element), "supported": supported},
        )


def _check_temperature(temperature_C):
    t = require_finite("temperature_C", temperature_C)
    if abs(t - SUPPORTED_TEMPERATURE_C) > TEMPERATURE_TOLERANCE_C:
        raise PourbaixValidationError(
            TEMPERATURE_UNSUPPORTED, "temperature_C",
            f"The Pourbaix engine supports 25 °C only (|T - 25| <= {TEMPERATURE_TOLERANCE_C} °C); "
            f"received {t} °C. No temperature extrapolation is performed: the species table has no "
            "consistent entropies or heat capacities.",
            {"requested": t, "supported": [SUPPORTED_TEMPERATURE_C], "toleranceC": TEMPERATURE_TOLERANCE_C},
        )
    return t


def _check_availability(element):
    if element in species_table.available_elements():
        return
    reason = species_table.UNAVAILABLE_ELEMENTS.get(element, "No verified data.")
    raise PourbaixValidationError(
        POURBAIX_DATA_UNAVAILABLE, "element",
        f"No verified {element}-H₂O data: {reason}",
        {"element": element, "reason": reason, "available": species_table.available_elements()},
    )


def _ref_offset(ref_electrode):
    if not isinstance(ref_electrode, str) or ref_electrode not in REF_ELECTRODE_OFFSETS:
        raise PourbaixValidationError(
            UNKNOWN_REFERENCE_ELECTRODE, "refElectrode",
            f"Unknown reference electrode {ref_electrode!r}; supported: {', '.join(REF_ELECTRODE_OFFSETS)}.",
            {"refElectrode": repr(ref_electrode), "supported": list(REF_ELECTRODE_OFFSETS)},
        )
    return REF_ELECTRODE_OFFSETS[ref_electrode]


# ---------------------------------------------------------------------------------------
# Point classification
# ---------------------------------------------------------------------------------------


def _depolarizer(e_she, e_her, e_oer):
    if e_she < e_her:
        return "H⁺ reduction possible (E below water line a)"
    if e_she < e_oer:
        return "O₂ reduction possible (E between water lines a and b)"
    return "Above water line b (water oxidation region)"


def _classify(element, ph, e_she, log_a):
    coeffs = _coefficients(element, log_a)
    sp = _argmin(coeffs, ph, e_she)
    e_her, e_oer = _water_lines_at(ph)
    inside = e_her <= e_she <= e_oer
    e_imm = _metal_boundary_E(coeffs, ph)
    return sp, inside, e_her, e_oer, e_imm


def _check_point(ph, e_she, name="point"):
    """pH and E (V vs SHE) must be finite and inside the map box; nothing is classified outside it."""
    box = species_table.BOX
    ph = require_range(f"{name}.pH", ph, box["pH_min"], box["pH_max"], "pH")
    e_she = require_range(f"{name}.potential_V_SHE", e_she, box["E_min_V_SHE"], box["E_max_V_SHE"], "V vs SHE")
    return ph, e_she


def _point_number(pt, idx, keys, label):
    """Required numeric input of an experimental point (no silent defaults, no strings, no NaN)."""
    for key in keys:
        if key in pt:
            return require_finite(f"experimentalPoints[{idx}].{label}", pt[key])
    raise ValidationError(MISSING_PROPERTY, f"experimentalPoints[{idx}].{label}",
                          f"is required (one of {', '.join(keys)})", {"index": idx, "keys": list(keys)})


def evaluate_point_mechanism(element, ph, e_she, temperature_C=25.0, ion_act_log10=-6.0, chloride_ppm=0.0):
    """
    Thermodynamic phase at an (E, pH) point from the minimum-Gibbs-energy species table
    (25 C only). The category text is fixed per category; no rate or protectiveness claim.
    """
    _check_temperature(temperature_C)
    ph, e_she = _check_point(ph, e_she)
    sp, inside, e_her, e_oer, e_imm = _classify(element, ph, e_she, ion_act_log10)
    hits = withheld_species_at(element, ph, e_she, ion_act_log10)
    text = CATEGORY_TEXTS[sp.category]
    delta_imm = None if e_imm is None else round(e_she - e_imm, 3)
    regime = sp.category if inside else f"{sp.category} — {OUTSIDE_WATER_LABEL}"

    mitigations = []
    if sp.category == CATEGORY_IMMUNITY:
        if e_she < e_her:
            mitigations.append("E is below water line a: hydrogen evolution is thermodynamically possible; hydrogen uptake can matter for susceptible alloys.")
        else:
            mitigations.append("The metal is the equilibrium phase at this point; the map makes no statement about rates or protection.")
    else:
        if sp.category == CATEGORY_ACID and e_imm is not None:
            mitigations.append(f"Cathodic protection: polarise below the computed metal-domain boundary (E < {round(e_imm, 2)} V vs SHE at pH {ph:g}).")
        elif sp.category != CATEGORY_ACID and e_imm is not None:
            mitigations.append(f"The metal-domain boundary at pH {ph:g} lies at {round(e_imm, 2)} V vs SHE.")
        mitigations.extend(CATEGORY_MITIGATION[sp.category])

    return {
        "regime": regime,
        "category": sp.category,
        "dominantSpecies": sp.formula,
        "dominantSpeciesId": sp.id,
        "mechanismId": text["mechanismId"],
        "mechanismTitle": text["mechanismTitle"],
        "mechanismDetails": text["mechanismDetails"],
        "riskLevel": text["riskLevel"],
        "color": text["color"],
        "depolarizer": _depolarizer(e_she, e_her, e_oer),
        "deltaE_Immunity_V": delta_imm,
        "deltaE_Pitting_V": None,
        "isInsideWaterStability": inside,
        "waterStabilityLabel": INSIDE_WATER_LABEL if inside else OUTSIDE_WATER_LABEL,
        "insideWithheldDataRegion": bool(hits),
        "withheldDataSpeciesIds": [sid for _, sid in hits],
        "e_HER_V_SHE": round(e_her, 3),
        "e_OER_V_SHE": round(e_oer, 3),
        "engineeringMitigations": mitigations,
    }


# ---------------------------------------------------------------------------------------
# Diagram
# ---------------------------------------------------------------------------------------


def _species_inventory(element):
    inventory = {"immunity": [], "corrosion_acid": [], "passivation": [], "corrosion_alkaline": [],
                 "transpassive": []}
    key_by_role = {"metal": "immunity", "cation": "corrosion_acid", "oxide": "passivation",
                   "anion_low": "corrosion_alkaline", "anion_high": "transpassive"}
    for row in species_table.species_rows(element):
        label = row["formula"] + ("(s)" if row["phase"] == "s" else "(aq)")
        inventory[key_by_role[row["role"]]].append(label)
    return inventory


def _model_block(log_a, element):
    return {
        "temperature_C": SUPPORTED_TEMPERATURE_C,
        "temperature_K": T_KELVIN,
        "method": "minimum Gibbs energy per metal atom over the sourced species table (argmin); "
                  "domains are exact convex polygons, boundaries exact lines g_i = g_j",
        "reference": "Persson et al., Phys. Rev. B 85, 235438 (2012)",
        "activityConvention": f"every dissolved metal species has activity 10^{log_a:g}; solids and water "
                              "have unit activity; gases 1 bar",
        "activityCoefficients": "ideal (γ=1), no ionic-strength correction",
        "dissolvedActivityRange_log10": list(species_table.activity_range(element)),
        "excludedSpecies": [
            "polynuclear aqueous species (e.g. Cr₂O₇²⁻): the per-species activity convention is ill-defined; the Cr "
            "and Mo activities are limited (10⁻⁶ to 10⁻² M and 10⁻⁶ to 10⁻⁴ M) so that Cr₂O₇²⁻ (from 10^-1.55 M) and "
            "the heptamolybdates (from 10^-3.53 M) would not take a domain even under that convention",
            "chloro and other complexes: the equilibrium contains no chloride species",
            "mononuclear hydrolysis species (MOH⁺, M(OH)₂(aq) and the like) of Fe, Ni, Cu, Zn, Mg and Al: omitted. "
            "Checked with open-database constants they change at most about 0.6 % of the water-window cells at "
            "10⁻⁶ M and above for Fe, Ni, Cu, Mg and Al, but several % at 10⁻⁸ M (MgOH⁺ about 5 %, Cu(OH)₂(aq) "
            "up to about 14 %), which is why the dissolved activity is limited to 10⁻⁶ M to 1 M. Zn is "
            "constant-dependent at 10⁻⁶ M: with the IUPAC 2013 Zn(OH)₂(aq) constant ZnO keeps its domain, with "
            "the wateq4f / Baes & Mesmer constant Zn(OH)₂(aq) would replace the whole ZnO domain",
            "withheld candidate species (Cr(III)/Cr(II) with hydrolysis, Mo(III), Ti(II)/Ti(III)/Ti(IV) with "
            "hydrolysis, TiO, TiH₂): not in the served table because the compilations contradict each other or the "
            "phase is outside the oxide/ion table; dataValidity.regions marks where any candidate set would be "
            "stable, and the map is not valid there",
        ],
        "chloride": "chloride_ppm is echoed only; the equilibrium has no chloro-complexes and no sourced "
                    "generic pitting potential exists (chloridePittingBoundary.status)",
        "temperatureScope": "25 °C only; |T - 25| > 0.5 °C raises TEMPERATURE_UNSUPPORTED",
        "waterLines": "E(H⁺/H₂) = -k pH; E(O₂/H₂O) = 1.2288 - k pH, 1.2288 = -dfG(H₂O, NBS -237.129 kJ/mol)/2F",
        "tieBreak": "exact ties go to the earlier row of the species table (metal, cations, solids, anions)",
        "riskLevelNote": "riskLevel is a display label derived from the thermodynamic category; it makes no rate claim",
        "gasConstantR_J_molK": R_GAS,
        "faraday_C_mol": F_FARADAY,
        "box": dict(species_table.BOX),
        "engine": ENGINE_ID,
    }


def solve_pourbaix_diagram(element="Fe", temperature_C=25.0, ion_activity_log10=-6.0, chloride_ppm=0.0, experimental_points=None):
    """
    Solves the single-element M-H2O E-pH equilibrium (25 C): water lines, exact domain
    boundaries, a classified stability grid and the classification of user E-pH points.
    """
    start_time = time.perf_counter()
    _check_element(element)
    _check_temperature(temperature_C)
    if element in UNAVAILABLE_ONLY_ELEMENTS:
        raise PourbaixValidationError(
            POURBAIX_DATA_UNAVAILABLE, "element",
            f"No verified {element}-H₂O data: {species_table.UNAVAILABLE_ELEMENTS[element]}",
            {"element": element, "reason": species_table.UNAVAILABLE_ELEMENTS[element],
             "available": species_table.available_elements()})
    _check_availability(element)
    lo, hi = species_table.activity_range(element)
    log_a = require_range("ionActivity_log10", ion_activity_log10, lo, hi, "log10 activity")
    chloride_ppm = require_finite("chloride_ppm", chloride_ppm)
    sys_data = POURBAIX_ELEMENT_SYSTEMS[element]
    nernst_slope = calculate_nernst_slope(SUPPORTED_TEMPERATURE_C)
    chloride_molar = max(chloride_ppm, 0.0) * 1e-3 / CHLORIDE_MOLAR_MASS_G_MOL
    rows = species_table.species_rows(element)

    # 1. Water stability boundaries
    water_stability = generate_water_stability_lines(SUPPORTED_TEMPERATURE_C)

    # 2. Chloride: no sourced generic Epit exists
    pitting_boundary = {
        "pittingActive": False,
        "status": "unavailable-no-sourced-epit",
        "chloride_ppm": chloride_ppm,
        "chloride_Molar": round(chloride_molar, 5),
        "nominal_Epit_V_SHE": None,
        "points": [],
        "note": "No sourced generic pitting potential exists for a pure element (Epit depends on alloy, "
                "surface and test method); the equilibrium contains no chloro-complexes.",
    }

    # 3. 2D stability field grid (315 cells: pH 0-14 x E -2.0..+2.0 V in 0.2 V steps)
    stability_grid = []
    for p_idx in range(15):  # pH 0 to 14
        ph = float(p_idx)
        for e_idx in range(21):
            e_she = -2.0 + e_idx * 0.2
            sp, inside, _, _, _ = _classify(element, ph, e_she, log_a)
            text = CATEGORY_TEXTS[sp.category]
            hits = withheld_species_at(element, ph, e_she, log_a)
            stability_grid.append({
                "pH": ph,
                "E_V_SHE": round(e_she, 2),
                "regime": sp.category if inside else f"{sp.category} — {OUTSIDE_WATER_LABEL}",
                "category": sp.category,
                "dominantSpecies": sp.formula,
                "dominantSpeciesId": sp.id,
                "mechanismTitle": text["mechanismTitle"],
                "color": text["color"],
                "isInsideWaterStability": inside,
                "insideWithheldDataRegion": bool(hits),
            })

    # 4. Exact boundaries and domains
    analytical_boundaries = compute_boundaries(element, log_a)
    domains = [{
        "speciesId": sid,
        "category": next(r["category"] for r in rows if r["id"] == sid),
        "polygon": [{"pH": p[0], "E_V_SHE": p[1]} for p in poly],
    } for sid, poly in compute_domains(element, log_a).items()]

    # 5. Test points (user or illustrative inputs; never described as measured)
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
            if not isinstance(pt, dict):
                raise ValidationError(MISSING_PROPERTY, f"experimentalPoints[{idx}]", "must be an object",
                                      {"index": idx, "type": type(pt).__name__})
            pt_id = pt.get("id", f"exp_pt_{idx+1}")
            pt_name = pt.get("name", f"Test Point #{idx+1}")
            ph_val = _point_number(pt, idx, ("ph", "pH"), "pH")
            pot_input = _point_number(pt, idx, ("potential_V", "potential", "E_V"), "potential_V")
            ref_elec = pt.get("refElectrode", "SHE")
            ref_offset = _ref_offset(ref_elec)

            # Convert measured potential to E vs SHE
            e_she = pot_input + ref_offset
            _check_point(ph_val, e_she, f"experimentalPoints[{idx}]")

            eval_res = evaluate_point_mechanism(
                element, ph_val, e_she, SUPPORTED_TEMPERATURE_C, log_a, chloride_ppm
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
                "category": eval_res["category"],
                "dominantSpecies": eval_res["dominantSpecies"],
                "dominantSpeciesId": eval_res["dominantSpeciesId"],
                "mechanismId": eval_res["mechanismId"],
                "mechanismTitle": eval_res["mechanismTitle"],
                "mechanismDetails": eval_res["mechanismDetails"],
                "riskLevel": eval_res["riskLevel"],
                "color": eval_res["color"],
                "depolarizer": eval_res["depolarizer"],
                "deltaE_Immunity_V": eval_res["deltaE_Immunity_V"],
                "deltaE_Pitting_V": eval_res["deltaE_Pitting_V"],
                "isInsideWaterStability": eval_res["isInsideWaterStability"],
                "waterStabilityLabel": eval_res["waterStabilityLabel"],
                "insideWithheldDataRegion": eval_res["insideWithheldDataRegion"],
                "withheldDataSpeciesIds": eval_res["withheldDataSpeciesIds"],
                "engineeringMitigations": eval_res["engineeringMitigations"]
            })

    # Trajectory synthesis (equilibrium statements only)
    trajectory_diagnosis = "No experimental data provided."
    if analyzed_experimental_points:
        total_pts = len(analyzed_experimental_points)
        counts = {}
        for p in analyzed_experimental_points:
            counts[p["category"]] = counts.get(p["category"], 0) + 1
        parts = ", ".join(f"{n} in {c}" for c, n in sorted(counts.items()))
        outside = sum(1 for p in analyzed_experimental_points if not p["isInsideWaterStability"])
        trajectory_diagnosis = (
            f"Equilibrium classification of {total_pts} test point(s) in the {element}–H₂O map at 25 °C "
            f"(dissolved activity 10^{log_a:g}): {parts}."
        )
        if outside:
            trajectory_diagnosis += f" {outside} point(s) lie outside the water stability window (metastable)."
        withheld = sum(1 for p in analyzed_experimental_points if p["insideWithheldDataRegion"])
        if withheld:
            trajectory_diagnosis += (f" {withheld} point(s) lie in a withheld-data region, where the map is not "
                                     "valid (dataValidity).")
        trajectory_diagnosis += " This is a thermodynamic statement; it makes no claim about rates, film protectiveness or pitting."

    compute_time_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    standard_e0 = _standard_e0(element)

    return {
        "success": True,
        "engine": ENGINE_ID,
        "computeTimeMs": compute_time_ms,
        "element": element,
        "systemName": sys_data["name"],
        "parameters": {
            "temperature_C": SUPPORTED_TEMPERATURE_C,
            "requestedTemperature_C": float(temperature_C),
            "nernstSlope_V_pH": round(nernst_slope, 5),
            "ionActivity_log10": log_a,
            "chlorideConcentration_ppm": chloride_ppm,
            "chloride_Molar": round(chloride_molar, 5),
            "pittingPotential_V_SHE": None,
            "pittingRisk": "Not assessed (no sourced pitting potential)",
            "standardE0_V": standard_e0,
        },
        "temperatureStatus": {
            "status": "supported-25C-only",
            "temperature_C": SUPPORTED_TEMPERATURE_C,
            "supported_C": [SUPPORTED_TEMPERATURE_C],
            "toleranceC": TEMPERATURE_TOLERANCE_C,
            "note": "No temperature extrapolation: the table has no consistent entropies or heat capacities.",
        },
        "model": _model_block(log_a, element),
        "dataValidity": _data_validity_block(element, log_a),
        "speciesTable": {
            "sourceSet": species_table.ELEMENT_SET[element][0],
            "sourceSetNote": species_table.ELEMENT_SET[element][2],
            "waterDfG_kJ_mol": species_table.water_dfg_kj_mol(element),
            "schema": species_table.SCHEMA,
            "species": rows,
            "withheldSpecies": [{"id": r[0], "verification": r[10], "reason": r[11]}
                                for r in species_table.WITHHELD_SPECIES.get(element, ())],
        },
        "waterStabilityLines": water_stability,
        "chloridePittingBoundary": pitting_boundary,
        "analyticalBoundaries": analytical_boundaries,
        "domains": domains,
        "speciesInventory": _species_inventory(element),
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
            "constantsNote": "Exact SI 2019 R = N_A*k and F = N_A*e (Phase 6a value step); "
                             "they replaced the CODATA printed truncations 8.314462618 / 96485.33212.",
        },
    }


def _standard_e0(element):
    """Unit-activity E0 (V SHE) of metal / reference cation, derived from the table (informational)."""
    coeffs = {sp.id: sp for sp in _coefficients(element, 0.0)}
    if species_table.REFERENCE_CATION[element] is None:
        return None
    cation = coeffs[species_table.REFERENCE_CATION[element]]
    line = _line_between(coeffs[next(iter(coeffs))], cation)
    return None if line is None or line[0] != "sloped" else round(line[1], 4)


def _element_standard_e0(element):
    return _standard_e0(element) if element in species_table.available_elements() else None


for _symbol, _entry in POURBAIX_ELEMENT_SYSTEMS.items():
    _entry["available"] = _symbol in species_table.available_elements()
    _entry["standardE0_V"] = _element_standard_e0(_symbol)
    if not _entry["available"]:
        _entry["unavailableReason"] = species_table.UNAVAILABLE_ELEMENTS[_symbol]


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        print(json.dumps({
            "status": "ready",
            "engine": "MetalliX single-element M–H₂O Pourbaix E-pH solver (25 °C, ΔfG minimisation)",
            "engineId": ENGINE_ID,
            "availableElements": species_table.available_elements(),
            "unavailableElements": {k: v for k, v in species_table.UNAVAILABLE_ELEMENTS.items()},
            "capabilities": [
                "Single-element M–H₂O equilibrium by minimum Gibbs energy (25 °C only)",
                "Water stability lines a and b (HER, OER)",
                "Exact domain polygons and boundary lines derived from a sourced species table",
                "Experimental E-pH point overlay classified by thermodynamic category",
                "Withheld-data regions (dataValidity) where contradictory or excluded candidate species would be stable",
                "No chloride/pitting model (no sourced generic Epit)"
            ]
        }))
        sys.exit(0)

    try:
        # UTF-8 explicitly: the locale code page (cp1254 on Turkish Windows) would garble notes such as "Fe²⁺"
        # (the persistent IPC relay replaces sys.stdin by a text stream without .buffer: use it as is)
        stdin_bytes = getattr(sys.stdin, "buffer", None)
        raw_input = stdin_bytes.read().decode("utf-8") if stdin_bytes is not None else sys.stdin.read()
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
