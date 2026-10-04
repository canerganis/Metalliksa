#!/usr/bin/env python3
"""Independent brute-force oracle for the Pourbaix engine (standard library only).

Adapted from the SPEC-pourbaix-opus.md author's scratch oracle. It shares NO code with
``pourbaix_solver`` or ``pourbaix_species_25c``: it carries its own copy of the species
numbers (atlas and CHNOSZ OBIGT values as cal/mol, NBS/CRC/Robie values as kJ/mol, so a
transcription slip in the engine's table shows up as a mismatch), its own constants (CODATA 2018 printed values,
not physical_constants) and its own argmin/polygon code.

Dominance is the minimum Gibbs energy per metal atom at 25 C and fixed activities,

    g_i(pH, E) = [dfG_i - o_i*dfG(H2O) + RT ln a_i] / x_i - m_i ln10 RT pH - n_i F E,
    m_i = (2 o_i - h_i)/x_i,  n_i = (z_i + 2 o_i - h_i)/x_i.

``dominant`` is the brute-force check: it evaluates EVERY species at the point and takes the
minimum, so no species can have a lower g than the answer by construction.

Cr, Mo and Ti (engine v5): the served rows are typed again here from the NBS 1982 scan (kJ/mol) and the
NECTAR log K values; the withheld candidate sets are rebuilt from their primary numbers (E0 in V, log K,
OBIGT cal/mol), never read from the engine. ``withheld_hits`` / ``withheld_polygons`` are the oracle's own
version of the engine's dataValidity regions.

Usage:  python tools/pourbaix_oracle.py [Fe|Ni|Cu|Zn|Mg|Al|Cr|Mo|Ti ...]    # prints the domain areas
"""

import math
import sys

R = 8.314462618  # J/mol/K (CODATA 2018 printed value)
F = 96485.33212  # C/mol
T = 298.15
LN10 = math.log(10.0)
CAL = 4.184
BOX = (-2.0, 16.0, -3.0, 2.5)  # pH_min, pH_max, E_min, E_max


def atlas(cal):
    return cal * CAL / 1000.0


# name: (x, o, h, z, dfG kJ/mol, phase, role, category source)
_FE_H2O_KJ = atlas(-56690)
_FEO4 = atlas(-2530) + 4 * _FE_H2O_KJ + 3 * F * 2.20 / 1000.0  # Latimer E0 = 2.20 V
# Al: CHNOSZ OBIGT rows (cal/mol: Al+3 and Al(OH)4- from Tagirov & Schott 2001; H2O is the
# SUPCRT92 value -56687 cal) and gibbsite from Robie, Hemingway & Fisher 1978 (J/mol).
_AL_H2O_KJ = -56687 * CAL / 1000.0
_NI_H2O_KJ = -237.140  # NEA-TDB water used with the Ni set

# Species used by the engine (verified rows only).
DATA = {
    "Fe": {"H2O": _FE_H2O_KJ, "sp": {
        "Fe": (1, 0, 0, 0, 0.0, "s", "metal"),
        "Fe2+": (1, 0, 0, 2, atlas(-20300), "aq", "cation"),
        "Fe3+": (1, 0, 0, 3, atlas(-2530), "aq", "cation"),
        "Fe3O4": (3, 4, 0, 0, atlas(-242400), "s", "oxide"),
        "Fe2O3": (2, 3, 0, 0, atlas(-177100), "s", "oxide"),
        "HFeO2-": (1, 2, 1, -1, atlas(-90627), "aq", "anion_low"),
        "FeO4^2-": (1, 4, 0, -2, _FEO4, "aq", "anion_high"),
    }},
    # Ni: NEA-TDB (Gamsjager et al. 2005, Table III-1), CODATA water. NiO2 (anchored estimate) is withheld.
    "Ni": {"H2O": _NI_H2O_KJ, "sp": {
        "Ni": (1, 0, 0, 0, 0.0, "s", "metal"),
        "Ni2+": (1, 0, 0, 2, -45.773, "aq", "cation"),
        "Ni(OH)2": (1, 2, 2, 0, -457.100, "s", "oxide"),
        "HNiO2-": (1, 2, 1, -1, -590.519 - _NI_H2O_KJ, "aq", "anion_low"),
    }},
    "Cu": {"H2O": -237.129, "sp": {
        "Cu": (1, 0, 0, 0, 0.0, "s", "metal"),
        "Cu+": (1, 0, 0, 1, 49.98, "aq", "cation"),
        "Cu2+": (1, 0, 0, 2, 65.49, "aq", "cation"),
        "Cu2O": (2, 1, 0, 0, -146.0, "s", "oxide"),
        "CuO": (1, 1, 0, 0, -129.7, "s", "oxide"),
        "HCuO2-": (1, 2, 1, -1, -258.5, "aq", "anion_low"),
        "CuO2^2-": (1, 2, 0, -2, -183.6, "aq", "anion_low"),
    }},
    "Zn": {"H2O": -237.129, "sp": {
        "Zn": (1, 0, 0, 0, 0.0, "s", "metal"),
        "Zn2+": (1, 0, 0, 2, -147.06, "aq", "cation"),
        "ZnO": (1, 1, 0, 0, -318.30, "s", "oxide"),
        "HZnO2-": (1, 2, 1, -1, -457.09, "aq", "anion_low"),
        "ZnO2^2-": (1, 2, 0, -2, -384.2, "aq", "anion_low"),
    }},
    "Mg": {"H2O": -237.129, "sp": {
        "Mg": (1, 0, 0, 0, 0.0, "s", "metal"),
        "Mg2+": (1, 0, 0, 2, -454.8, "aq", "cation"),
        "Mg(OH)2": (1, 2, 2, 0, -833.51, "s", "oxide"),
    }},
    "Al": {"H2O": _AL_H2O_KJ, "sp": {
        "Al": (1, 0, 0, 0, 0.0, "s", "metal"),
        "Al3+": (1, 0, 0, 3, -116510 * CAL / 1000.0, "aq", "cation"),
        "Al(OH)3": (1, 3, 3, 0, -1154889 / 1000.0, "s", "oxide"),
        "Al(OH)4-": (1, 4, 4, -1, -312087 * CAL / 1000.0, "aq", "anion_low"),
    }},
}

# Al species deliberately NOT in the engine (same OBIGT set and water as DATA["Al"]), kept so the
# effect of the exclusion can be measured: metastable solids (boehmite, Hemingway, Robie & Apps
# 1991; corundum from the CODATA 1989 key values dfH -1675.7 kJ/mol, S 50.92 J/mol/K) and the
# mononuclear hydrolysis species of Tagirov & Schott 2001 (all roles as they would be used).
AL_EXCLUDED = {
    "AlO(OH)": (1, 2, 1, 0, -918400 / 1000.0, "s", "oxide"),
    "Al2O3": (2, 3, 0, 0, -1675.7 - T * (50.92 - 2 * 28.30 - 1.5 * 205.152) / 1000.0, "s", "oxide"),
}
AL_HYDROLYSIS_OMITTED = {
    "AlOH2+": (1, 1, 1, 2, -166425 * CAL / 1000.0, "aq", "cation"),
    "Al(OH)2+": (1, 2, 2, 1, -214987 * CAL / 1000.0, "aq", "cation"),
}

# Rows withheld from the engine (unverified V3). Kept so the effect of withholding can be measured.
# Ni3O4 / Ni2O3 are atlas rows; they are transferred to the NEA Ni set by keeping their atlas energy
# relative to the atlas Ni2+ (-11530 cal) and atlas water (-56690 cal), so that the withholding effect
# is measured on the same footing as the served map.
_NI_SHIFT_PER_NI = -45.773 - atlas(-11530)
_NI_SHIFT_PER_O = _NI_H2O_KJ - _FE_H2O_KJ
WITHHELD = {
    "Ni": {"Ni3O4": (3, 4, 0, 0, atlas(-170150) + 3 * _NI_SHIFT_PER_NI + 4 * _NI_SHIFT_PER_O, "s", "oxide"),
           "Ni2O3": (2, 3, 0, 0, atlas(-112270) + 2 * _NI_SHIFT_PER_NI + 3 * _NI_SHIFT_PER_O, "s", "oxide"),
           # NiO2: anchored to the NEA Ni2+ by E0(NiO2/Ni2+) = 1.593 V (typed here again, not read from the engine)
           "NiO2": (1, 2, 0, 0, -45.773 + 2 * _NI_H2O_KJ + 2 * F * 1.593 / 1000.0, "s", "oxide")},
    "Al": {"H2O": _FE_H2O_KJ, "sp": {
        "Al": (1, 0, 0, 0, 0.0, "s", "metal"),
        "Al3+": (1, 0, 0, 3, atlas(-115000), "aq", "cation"),
        "AlO2-": (1, 2, 0, -1, atlas(-200710), "aq", "anion_low"),
        "Al2O3.3H2O": (2, 6, 6, 0, atlas(-554600), "s", "oxide"),
    }},
}

# ---- Cr, Mo, Ti (engine v5) --------------------------------------------------------------------------
_K = LN10 * R * T / 1000.0  # kJ/mol per log10 unit
_FK = F / 1000.0
_W_NBS = -237.129


def _e0_cation(n, e0):
    return n * _FK * e0


DATA.update({
    "Cr": {"H2O": _W_NBS, "sp": {
        "Cr": (1, 0, 0, 0, 0.0, "s", "metal"),
        "Cr2O3": (2, 3, 0, 0, -1058.1, "s", "oxide"),
        "HCrO4-": (1, 4, 1, -1, -764.7, "aq", "anion_high"),
        "CrO4^2-": (1, 4, 0, -2, -727.75, "aq", "anion_high"),
    }},
    "Mo": {"H2O": _W_NBS, "sp": {
        "Mo": (1, 0, 0, 0, 0.0, "s", "metal"),
        "MoO2": (1, 2, 0, 0, -533.01, "s", "oxide"),
        "MoO3": (1, 3, 0, 0, -667.97, "s", "oxide"),
        "H2MoO4": (1, 4, 2, 0, -836.3 - 8.12 * _K, "aq", "anion_high"),
        "HMoO4-": (1, 4, 1, -1, -836.3 - 4.47 * _K, "aq", "anion_high"),
        "MoO4^2-": (1, 4, 0, -2, -836.3, "aq", "anion_high"),
    }},
    "Ti": {"H2O": _W_NBS, "sp": {
        "Ti": (1, 0, 0, 0, 0.0, "s", "metal"),
        "Ti2O3": (2, 3, 0, 0, -1434.2, "s", "oxide"),
        "Ti3O5": (3, 5, 0, 0, -2317.4, "s", "oxide"),
        "TiO2": (1, 2, 0, 0, -889.5, "s", "oxide"),
    }},
})

ACTIVITY_RANGE = {"Cr": (-6.0, -2.0), "Mo": (-6.0, -4.0)}  # others (-6, 0)


def _cr_set(tag, cr3, cr2):
    """Cr2+, Cr3+ and the hydrolysis species of one candidate set (Brown & Ekberg 2016 / NIST46 log K)."""
    def hyd(parent, n_w, lk):
        return parent + n_w * _W_NBS - _K * lk
    return {
        f"Cr2+[{tag}]": (1, 0, 0, 2, cr2, "aq", "cation"),
        f"Cr3+[{tag}]": (1, 0, 0, 3, cr3, "aq", "cation"),
        f"CrOH+[{tag}]": (1, 1, 1, 1, hyd(cr2, 1, -5.5), "aq", "cation"),
        f"CrOH2+[{tag}]": (1, 1, 1, 2, hyd(cr3, 1, -3.60), "aq", "cation"),
        f"Cr(OH)2+[{tag}]": (1, 2, 2, 1, hyd(cr3, 2, -9.65), "aq", "cation"),
        f"Cr(OH)3(aq)[{tag}]": (1, 3, 3, 0, hyd(cr3, 3, -16.25), "aq", "cation"),
        f"Cr(OH)4-[{tag}]": (1, 4, 4, -1, hyd(cr3, 4, -27.56), "aq", "anion_low"),
    }


_SUPCRT_H2O = -56687 * CAL / 1000.0
_O2_AQ = 3954 * CAL / 1000.0
_CR3_LLNL = -98.6784 * _K + 0.75 * _O2_AQ - 1.5 * _SUPCRT_H2O
_CRO4_LLNL = _CR3_LLNL + 2.5 * _SUPCRT_H2O + 0.75 * _O2_AQ + 8.3842 * _K
_CR3_BN = (-8.52 * _K - 3 * _W_NBS - 1058.1) / 2.0
_TI3_CRC = _e0_cation(3, -1.37)

# Candidate sets in the engine's order: {set id: {species: row}}.
CANDIDATES = {
    "Cr": {
        "Cr-CRC": _cr_set("CRC", _e0_cation(3, -0.74), _e0_cation(2, -0.9)),
        "Cr-SSWS97": _cr_set("SSWS97", -49300 * CAL / 1000.0, -39400 * CAL / 1000.0),
        "Cr-LLNL": _cr_set("LLNL", _CR3_LLNL, 21.6373 * _K - 2 * _SUPCRT_H2O - _O2_AQ + _CRO4_LLNL),
        "Cr-BN98": _cr_set("BN98", _CR3_BN, _CR3_BN + _FK * 0.407),
        "Cr-H2CrO4": {"H2CrO4[BN98]": (1, 4, 2, 0, -727.75 - 6.31 * _K, "aq", "anion_high")},
    },
    "Mo": {
        # H2MoO4 + 6H+ + 3e- = Mo3+ + 4H2O, E0 = 0.43 V
        "Mo-CRC": {"Mo3+[CRC]": (1, 0, 0, 3, -836.3 - 8.12 * _K - 4 * _W_NBS - 3 * _FK * 0.43, "aq", "cation")},
    },
    "Ti": {
        "Ti-CRC": {
            "Ti2+[CRC]": (1, 0, 0, 2, _e0_cation(2, -1.63), "aq", "cation"),
            "Ti3+[CRC]": (1, 0, 0, 3, _TI3_CRC, "aq", "cation"),
            "TiOH2+[CRC]": (1, 1, 1, 2, _TI3_CRC + _W_NBS + 1.65 * _K, "aq", "cation"),
            "TiO2+[CRC]": (1, 1, 0, 2, _W_NBS - 4 * _FK * 0.93, "aq", "cation"),
            "TiO[CRC]": (1, 1, 0, 0, _W_NBS - 2 * _FK * 1.31, "s", "oxide"),
        },
        "Ti-CRC-b": {"TiO2+[CRC-b]": (1, 1, 0, 2, _TI3_CRC + _W_NBS + _FK * 0.19, "aq", "cation")},
        "Ti-TiO-NBS": {"TiO[NBS]": (1, 1, 0, 0, -495.0, "s", "oxide")},
        "Ti-TiO-JANAF": {"TiO[JANAF]": (1, 1, 0, 0, -513.278, "s", "oxide")},
        "Ti-BE16": {
            "Ti4+[BE16]": (1, 0, 0, 4, -889.5 - 2 * _W_NBS + 3.56 * _K, "aq", "cation"),
            "TiOOH+[BE16]": (1, 2, 1, 1, -889.5 + 6.06 * _K, "aq", "cation"),
            "TiO(OH)2[BE16]": (1, 3, 2, 0, -889.5 + _W_NBS + 9.02 * _K, "aq", "cation"),
            "TiO(OH)3-[BE16]": (1, 4, 3, -1, -889.5 + 2 * _W_NBS + (9.02 + 11.9) * _K, "aq", "anion_low"),
        },
        "Ti-LLNL": {"Ti(OH)4[LLNL]": (1, 4, 4, 0, -889.5 + 2 * _W_NBS + 9.6452 * _K, "aq", "cation")},
        "Ti-hydride": {"TiH2": (1, 0, 2, 0, -80.3, "s", "metal")},
    },
}
# Excluded (V2) rows that are in no candidate set: polynuclear Cr2O7 2- and heptamolybdates, anatase.
EXCLUDED = {
    "Cr": {"Cr2O7^2-": (2, 7, 0, -2, -1301.1, "aq", "anion_high")},
    "Mo": {n: (7, 24, h, z, 7 * -836.3 - 4 * _W_NBS - lk * _K, "aq", "anion_high")
           for n, h, z, lk in (("Mo7O24^6-", 0, -6, 51.93), ("HMo7O24^5-", 1, -5, 58.90),
                               ("H2Mo7O24^4-", 2, -4, 64.63), ("H3Mo7O24^3-", 3, -3, 68.68))},
    "Ti": {"TiO2(anatase)": (1, 2, 0, 0, -884.5, "s", "oxide")},
}


def withheld_hits(element, pH, E, log_a=-6.0):
    """[(set id, species)] of every candidate set whose own species is the brute-force minimum here."""
    hits = []
    for set_id, members in CANDIDATES.get(element, {}).items():
        sp = dict(DATA[element]["sp"])
        sp.update(members)
        c = coeffs_of(sp, DATA[element]["H2O"], log_a)
        best = None
        for name, v in c.items():
            g = v[0] + v[1] * pH + v[2] * E
            if best is None or g < best[1]:
                best = (name, g)
        if best[0] in members:
            hits.append((set_id, best[0]))
    return hits


def withheld_polygons(element, log_a=-6.0, box=BOX):
    """[(set id, species, polygon)] of the candidate species' domains, one candidate set at a time."""
    out = []
    for set_id, members in CANDIDATES.get(element, {}).items():
        sp = dict(DATA[element]["sp"])
        sp.update(members)
        polys = _polygons_of(coeffs_of(sp, DATA[element]["H2O"], log_a), box)
        for name, (poly, _) in polys.items():
            if name in members:
                out.append((set_id, name, poly))
    return out


CATEGORY = {"metal": "Immunity", "cation": "Corrosion (acid)", "anion_low": "Corrosion (alkaline)",
            "oxide": "Passivation (thermodynamic)", "anion_high": "Transpassive"}


def dataset(element, include_withheld=False):
    base = DATA[element]
    sp = dict(base["sp"])
    if include_withheld and element in WITHHELD and "sp" not in WITHHELD[element]:
        sp.update(WITHHELD[element])
    return {"H2O": base["H2O"], "sp": sp}


def coeffs(element, log_a=-6.0, include_withheld=False):
    """species -> (c0 [J], cpH [J/pH], cE [J/V]) of g per metal atom (table order kept)."""
    d = dataset(element, include_withheld)
    return coeffs_of(d["sp"], d["H2O"], log_a)


def coeffs_of(species, h2o_kj, log_a=-6.0):
    """Same as ``coeffs`` for an explicit species dict {name: (x, o, h, z, dfG kJ, phase, role)}."""
    h2o = h2o_kj * 1000.0
    out = {}
    for name, (x, o, h, z, g, phase, role) in species.items():
        ln_a = 0.0 if phase == "s" else log_a * LN10
        m = (2 * o - h) / x
        n = (z + 2 * o - h) / x
        out[name] = ((g * 1000.0 - o * h2o + R * T * ln_a) / x, -m * LN10 * R * T, -n * F)
    return out


def g_values(element, pH, E, log_a=-6.0, include_withheld=False):
    c = coeffs(element, log_a, include_withheld)
    return {k: v[0] + v[1] * pH + v[2] * E for k, v in c.items()}


def dominant(element, pH, E, log_a=-6.0, include_withheld=False):
    """Brute force: evaluate every species, return the first minimum (table order on a tie)."""
    g = g_values(element, pH, E, log_a, include_withheld)
    best = None
    for name, val in g.items():
        if best is None or val < g[best]:
            best = name
    return best


def category(element, pH, E, log_a=-6.0, include_withheld=False):
    return CATEGORY[dataset(element, include_withheld)["sp"][dominant(element, pH, E, log_a, include_withheld)][6]]


def margin_V(element, pH, E, log_a=-6.0, include_withheld=False):
    """Smallest distance (V, along E) from the point to a boundary of the winning species."""
    c = coeffs(element, log_a, include_withheld)
    g = {k: v[0] + v[1] * pH + v[2] * E for k, v in c.items()}
    best = dominant(element, pH, E, log_a, include_withheld)
    margin = float("inf")
    for k in c:
        if k == best:
            continue
        dE = abs(c[k][2] - c[best][2])
        gap = g[k] - g[best]
        margin = min(margin, gap / dE if dE > 1e-9 else (gap / 1e-9 if gap > 0 else 0.0))
    return margin


def boundary(element, a, b, log_a=-6.0):
    """E(pH) = e0 + slope*pH of g_a = g_b as ('E', e0, slope), or ('pH', value) if vertical."""
    c = coeffs(element, log_a)
    d0, dp, dE = c[a][0] - c[b][0], c[a][1] - c[b][1], c[a][2] - c[b][2]
    if abs(dE) < 1e-9:
        return ("pH", -d0 / dp)
    return ("E", -d0 / dE, -dp / dE)


def polygons(element, log_a=-6.0, box=BOX, include_withheld=False):
    """species -> (polygon, area) by Sutherland-Hodgman clipping (domains with area > 1e-9)."""
    return _polygons_of(coeffs(element, log_a, include_withheld), box)


def _polygons_of(c, box=BOX):
    res = {}
    for i in c:
        poly = [(box[0], box[2]), (box[1], box[2]), (box[1], box[3]), (box[0], box[3])]
        for j in c:
            if i == j:
                continue
            A, B, C = c[i][1] - c[j][1], c[i][2] - c[j][2], c[i][0] - c[j][0]
            new = []
            for k in range(len(poly)):
                P, Q = poly[k], poly[(k + 1) % len(poly)]
                fp, fq = C + A * P[0] + B * P[1], C + A * Q[0] + B * Q[1]
                if fp <= 0:
                    new.append(P)
                if (fp < 0 < fq) or (fq < 0 < fp):
                    t = fp / (fp - fq)
                    new.append((P[0] + t * (Q[0] - P[0]), P[1] + t * (Q[1] - P[1])))
            poly = new
            if not poly:
                break
        if poly:
            area = 0.5 * abs(sum(poly[k][0] * poly[(k + 1) % len(poly)][1]
                                 - poly[(k + 1) % len(poly)][0] * poly[k][1] for k in range(len(poly))))
            if area > 1e-9:
                res[i] = (poly, area)
    return res


def point_in_polygon(poly, pH, E):
    inside = False
    n = len(poly)
    for k in range(n):
        (x1, y1), (x2, y2) = poly[k], poly[(k + 1) % n]
        if (y1 > E) != (y2 > E) and pH < (x2 - x1) * (E - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def water_lines(pH):
    """(E_HER, E_OER) at 25 C: -k pH and 1.2288 - k pH."""
    k = LN10 * R * T / F
    return -k * pH, 237.129e3 / (2 * F) - k * pH


def main(argv):
    for el in (argv or list(DATA)):
        print("==", el)
        for name, (_, area) in polygons(el).items():
            print(f"  {name:12s} area={area:8.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
