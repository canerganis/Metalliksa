#!/usr/bin/env python3
"""
MetalliX Continuum Elasticity & Crystal Symmetry Homogenization Engine
Author: MetalliX Computational Materials Science Suite

THIS IS NOT A DFT CALCULATION. No electronic-structure code runs here. The module takes single-crystal
elastic constants C_ij that are SUPPLIED (custom_c_ij), looked up in a small built-in library (exact
formula match only) or built as an isotropic tensor from supplied K_VRH / G_VRH, and then applies
standard continuum elasticity to them. (The file name dft_property_calculator.py and the route
/api/python/dft-properties are historical; they are kept so that no consumer breaks.)

Scientific Scope:
- Crystal-symmetry-governed 6x6 Elastic Stiffness Tensor (C_ij) construction across crystal systems
  (Cubic, Hexagonal, Trigonal [-3m / 32 / 3m: C11 C12 C13 C14 C33 C44], Tetragonal, Orthorhombic and
  Isotropic). Every constant the symmetry class needs must be supplied; nothing is filled in.
- Matrix inversion (LAPACK LU with partial pivoting, numpy.linalg.inv) for the Compliance
  Tensor (S_ij = C_ij^-1), with the near-singular diagonal fallback.
- Born Mechanical Stability Criteria validation (Mouhat & Coudert, Phys. Rev. B 2014) with
  eigenvalues from the LAPACK symmetric eigensolver (numpy.linalg.eigvalsh).
- Voigt, Reuss, and Hill (VRH) bounds for bulk (K) and shear (G) moduli.
- Ranganathan-Ostoja-Starzewski Universal Elastic Anisotropy Index (A^U); Zener anisotropy (A_Z, cubic only).
- Directional Young's modulus E(n) = 1 / (n n : S : n n), the full compliance contraction.
- Ductility, brittleness, and bonding character evaluation via Pugh's ratio (B/G), Cauchy pressure (C_12 - C_44),
  and Frantsevich Poisson's ratio criterion.
- Acoustic velocities (longitudinal, transverse, mean) and the Anderson Debye temperature, per ATOM:
  theta_D = (h/k_B) * [3 n N_A rho / (4 pi M)]^(1/3) * v_m, with n the atoms per formula unit and M the
  formula-unit molar mass, both derived from the composition (CIAAW 2021 atomic weights in
  physical_constants). O. L. Anderson, J. Phys. Chem. Solids 24 (1963) 909-917. The cell site count
  (nsites) is NOT used: it is not the atoms-per-formula-unit the formula needs.
"""

import sys
import json
import math
import re
import time
import warnings

import numpy as np

import physical_constants

# Fundamental Physical Constants (CODATA 2018 / SI 2019, exact)
PLANCK_CONSTANT_H = 6.62607015e-34  # J*s (SI defining constant; physical_constants does not carry h)
BOLTZMANN_CONSTANT_KB = physical_constants.BOLTZMANN.value  # J/K
AVOGADRO_CONSTANT_NA = physical_constants.AVOGADRO.value  # mol^-1

ENGINE_NAME = "MetalliX-Continuum-Elasticity-Homogenizer-v4.1"
MODEL_LABEL = ("Continuum elasticity: Voigt-Reuss-Hill homogenisation and Born stability of supplied "
               "single-crystal elastic constants C_ij (not a DFT calculation)")
DEBYE_REFERENCE = ("Anderson, J. Phys. Chem. Solids 24 (1963) 909: theta_D = (h/k_B) [3 n N_A rho / (4 pi M)]^(1/3) v_m, "
                   "n atoms per formula unit, M formula-unit molar mass")

# Built-in single-crystal elastic-constants library (GPa). This is a lookup table, not a calculation and
# not a DFT result. Entries are served ONLY for an exact formula match (see lookup_library_entry).
# "reference_status":
#   "experimental-single-crystal"  measured single-crystal constants (ultrasonic / resonance), cited below;
#   "experimental-polycrystal-neutron-diffraction"  derived from neutron diffraction of a polycrystal;
#   "dft-calculation"  first-principles values (no single-crystal measurement exists); never read as measured.
# "reference" names the primary source and, where the value was read in a secondary table, that table.
# "reference_note" states a caveat (state, temperature, conflicting sources) and is shown with the result.
# "density_basis" says where "density" (g/cm^3, used only when the caller sends none) comes from.
# Sourcing was verified against the downloaded papers in .orchestra/external-data/review-fxb-sci
# (SOURCES.txt); the entries marked "read online" were checked in the reviewer's session only.
ELASTIC_CONSTANTS_LIBRARY = {
    "fe3c": {
        "match": "Fe3C",
        "formula": "Fe3C (Cementite)",
        "crystal_system": "Orthorhombic",
        "space_group": "Pnma (62)",
        # Voigt axes 1, 2, 3 = a, b, c of the Pnma setting (a=5.08, b=6.73, c=4.51 A); c44 is the soft
        # (010)[001] shear. Order in Jiang's Table III: c11 c22 c33 c12 c23 c13 c44 c55 c66.
        "c_ij": {
            "c11": 388.0, "c22": 345.0, "c33": 322.0,
            "c12": 156.0, "c13": 164.0, "c23": 162.0,
            "c44": 15.0,  "c55": 134.0, "c66": 134.0
        },
        "density": 7.68,
        "density_basis": "unverified (the experimental lattice of Wood et al., a=5.08 b=6.73 c=4.51 A, gives 7.73)",
        "reference_status": "dft-calculation",
        "reference": ("Jiang, Srinivasan, Caro, Maloy, J. Appl. Phys. 103, 043502 (2008), Table III, "
                      "energy-strain method (DFT-GGA, relaxed)"),
        "reference_note": ("first-principles values; no experimental single crystal of cementite exists; "
                           "c44 = 15 GPa is anomalously soft (82 GPa unrelaxed)"),
        "notes": "Metastable orthorhombic carbide; high hardness, directional Fe-C covalent-metallic bonding."
    },
    "ni3al": {
        "match": "Ni3Al",
        "formula": "Ni3Al (γ' Precipitate)",
        "crystal_system": "Cubic",
        "space_group": "Pm-3m (221)",
        "c_ij": {
            "c11": 224.3, "c12": 148.6, "c44": 125.8
        },
        "density": 7.42,
        "density_basis": "unverified",
        "reference_status": "experimental-single-crystal",
        "reference": ("Kayser & Stassis, Phys. Status Solidi A 64, 335 (1981), room temperature, as quoted in "
                      "Luan et al., Crystals 8, 307 (2018), Table 2"),
        "reference_note": None,
        "notes": "L1_2 ordered superalloy strengthener; high Zener anisotropy A_Z ~ 3.3."
    },
    "ti3alc2": {
        "match": "Ti3AlC2",
        "formula": "Ti3AlC2 (MAX Phase)",
        "crystal_system": "Hexagonal",
        "space_group": "P6_3/mmc (194)",
        "c_ij": {
            "c11": 361.0, "c33": 299.0, "c12": 75.0, "c13": 70.0, "c44": 124.0
        },
        "density": 4.25,
        "density_basis": "unverified",
        "reference_status": "experimental-polycrystal-neutron-diffraction",
        "reference": ("Gray, Kisi, Kirstein, Stampfl, J. Am. Ceram. Soc. 100, 705 (2017), as tabulated in "
                      "Ahams et al., Sci. Rep. 2021, Table 2 (read online)"),
        "reference_note": ("not a single-crystal measurement: constants derived from neutron diffraction of a "
                           "polycrystal; first-principles (Materials Project) values agree"),
        "notes": "Layered ternary carbide; metallic electrical conductivity with ceramic temperature resistance."
    },
    "zno": {
        "match": "ZnO",
        "formula": "ZnO (Wurtzite)",
        "crystal_system": "Hexagonal",
        "space_group": "P6_3mc (186)",
        "c_ij": {
            "c11": 209.7, "c33": 210.9, "c12": 121.1, "c13": 105.1, "c44": 42.47
        },
        "density": 5.68,
        "density_basis": ("calculated from a=3.2496, c=5.2042 A (Morkoc & Ozgur, Zinc Oxide, Wiley-VCH 2009, "
                          "Table 1.2) and M=81.38 g/mol, 2 formula units per cell"),
        "reference_status": "experimental-single-crystal",
        "reference": ("Bateman, J. Appl. Phys. 33, 3309 (1962), as tabulated in Morkoc & Ozgur, Zinc Oxide "
                      "(Wiley-VCH 2009), Table 1.6"),
        "reference_note": "room temperature; other measurements scatter by several percent",
        "notes": "Piezoelectric semiconductor; polar hexagonal wurtzite structure."
    },
    "niti": {
        "match": "NiTi",
        "formula": "NiTi (B2 Austenite)",
        "crystal_system": "Cubic",
        "space_group": "Pm-3m (221)",
        "c_ij": {
            "c11": 162.0, "c12": 129.0, "c44": 35.0
        },
        "density": 6.45,
        "density_basis": "unverified (a 2025 resonant-ultrasound study uses 6.5)",
        "reference_status": "experimental-single-crystal",
        "reference": ("Mercier, Melton, Gremaud, Hagi, J. Appl. Phys. 51, 1833 (1980), 298 K, as quoted in "
                      "Ren & Sehitoglu, Comput. Mater. Sci. 123, 19 (2016), Table 4"),
        "reference_note": ("B2 austenite; the constants depend strongly on composition and on the temperature "
                           "relative to the martensite start (C' = (C11-C12)/2 softens on cooling)"),
        "notes": "Nitinol shape memory alloy; low C' = (C11 - C12)/2 = 16.5 GPa precedes thermoelastic martensitic transformation."
    },
    "wc": {
        "match": "WC",
        "formula": "WC (Tungsten Carbide)",
        "crystal_system": "Hexagonal",
        "space_group": "P-6m2 (187)",
        "c_ij": {
            "c11": 720.0, "c33": 972.0, "c12": 254.0, "c13": 267.0, "c44": 328.0
        },
        "density": 15.63,
        "density_basis": "unverified (the X-ray cell volume 20.75 A^3 of Brugman et al. gives 15.67)",
        "reference_status": "experimental-single-crystal",
        "reference": ("Lee & Gilmore, J. Mater. Sci. 17, 2657 (1982), ultrasonic pulse-echo, as tabulated in "
                      "Kim, Massa, Rohrer, Int. J. Refract. Met. Hard Mater. 24, 89 (2006), Table 2"),
        "reference_note": ("secondary-source conflict on C13: Zhang et al. (arXiv:2201.02411) imply C13 near 150 "
                           "GPa and a DFT study reports C13 about 100 GPa below this experiment; the original "
                           "1982 paper was not read (abstract only), so C13 = 267 GPa rests on the Kim et al. table"),
        "notes": "Ultra-hard transition metal carbide; high shear modulus and severe brittleness."
    },
    "fe": {
        "match": "Fe",
        "formula": "α-Fe (Ferrite BCC)",
        "crystal_system": "Cubic",
        "space_group": "Im-3m (229)",
        "c_ij": {
            "c11": 233.1, "c12": 135.4, "c44": 117.8
        },
        "density": 7.87,
        "density_basis": "Ledbetter & Reed, J. Phys. Chem. Ref. Data 2, 531 (1973), Table 4 (293 K)",
        "reference_status": "experimental-single-crystal",
        "reference": ("Rayne & Chandrasekhar, Phys. Rev. 122, 1714 (1961), 10 MHz pulse-echo, 99.99 Fe, no field, "
                      "as tabulated in Ledbetter & Reed, J. Phys. Chem. Ref. Data 2, 531 (1973), Table 5"),
        "reference_note": "room temperature; at 0 K the same authors give 243.1/138.1/121.9",
        "notes": "Ferromagnetic BCC iron; Zener anisotropy A_Z = 2.41."
    },
    "ni": {
        "match": "Ni",
        "formula": "Ni (Nickel FCC)",
        "crystal_system": "Cubic",
        "space_group": "Fm-3m (225)",
        "c_ij": {
            "c11": 250.8, "c12": 150.0, "c44": 123.5
        },
        "density": 8.91,
        "density_basis": "Ledbetter & Reed, J. Phys. Chem. Ref. Data 2, 531 (1973), Table 4 (293 K)",
        "reference_status": "experimental-single-crystal",
        "reference": ("Alers, Neighbours, Sato, J. Phys. Chem. Solids 13, 40 (1960), 99.95 Ni, 10 MHz pulse-echo, "
                      "as tabulated in Ledbetter & Reed, J. Phys. Chem. Ref. Data 2, 531 (1973), Table 6"),
        "reference_note": ("measured in a 10 kOe saturating magnetic field; zero-field (unsaturated) values "
                           "are lower in C44 (Ledbetter & Reed best values: 249/155/114 no field, 254/155/123 "
                           "saturated)"),
        "notes": "FCC matrix base for nickel superalloys; high ductility."
    },
    "ti": {
        "match": "Ti",
        "formula": "α-Ti (Titanium HCP)",
        "crystal_system": "Hexagonal",
        "space_group": "P6_3/mmc (194)",
        "c_ij": {
            "c11": 162.4, "c33": 180.7, "c12": 92.0, "c13": 69.0, "c44": 46.7
        },
        "density": 4.51,
        "density_basis": "unverified",
        "reference_status": "experimental-single-crystal",
        "reference": ("Fisher & Renken, Phys. Rev. 135, A482 (1964), as tabulated in Chakraborty & Rogal, "
                      "arXiv:2008.00165, Suppl. Table S1 (experimental hcp Ti row)"),
        "reference_note": "room temperature",
        "notes": "Hexagonal close-packed room-temperature titanium; moderate elastic anisotropy."
    },
    "al": {
        "match": "Al",
        "formula": "Al (Aluminium FCC)",
        "crystal_system": "Cubic",
        "space_group": "Fm-3m (225)",
        "c_ij": {
            "c11": 107.3, "c12": 60.08, "c44": 28.3
        },
        "density": 2.70,
        "density_basis": "unverified",
        "reference_status": "experimental-single-crystal",
        "reference": ("Vallin, Mongy, Salama, Beckman, J. Appl. Phys. 35, 1825 (1964), as listed in "
                      "Rassoulinejad-Mousavi et al., J. Appl. Phys. 119, 244304 (2016) (arXiv:1605.09237), Table 2"),
        "reference_note": ("C12 = 60.08 is as printed in that table; other compilations give 60.7-60.9 GPa "
                           "(Kamm & Alers 1964), a 0.1-1.4 % spread that moves A_Z between 1.20 and 1.21"),
        "notes": "Nearly isotropic FCC metal (A_Z = 1.20); low density."
    },
    "w": {
        "match": "W",
        "formula": "W (Tungsten BCC)",
        "crystal_system": "Cubic",
        "space_group": "Im-3m (229)",
        "c_ij": {
            "c11": 523.27, "c12": 204.53, "c44": 160.72
        },
        "density": 19.26,
        "density_basis": "Archimedes measurement 19.260 g/cm^3, Qi et al. (OSTI 1529600)",
        "reference_status": "experimental-single-crystal",
        "reference": ("Featherston & Neighbours, Phys. Rev. 130, 1324 (1963), ultrasonic, 300 K, as listed in "
                      "Qi et al. (OSTI 1529600), Table III"),
        "reference_note": None,
        "notes": "Unique among elemental metals for being almost perfectly elastically isotropic (A_Z = 1.01)."
    },
    "cu": {
        "match": "Cu",
        "formula": "Cu (Copper FCC)",
        "crystal_system": "Cubic",
        "space_group": "Fm-3m (225)",
        "c_ij": {
            "c11": 168.4, "c12": 121.4, "c44": 75.4
        },
        "density": 8.96,
        "density_basis": "unverified",
        "reference_status": "experimental-single-crystal",
        "reference": ("Overton & Gaffney, Phys. Rev. 98, 969 (1955), room temperature (1.6839/1.2142/0.7539 "
                      "x 10^12 dyn/cm^2), as listed in Ledbetter & Naimon, J. Phys. Chem. Ref. Data 3, 897 "
                      "(1974), Table 2; also J. Appl. Phys. 119, 244304 (2016), Table 1"),
        "reference_note": None,
        "notes": "Highly anisotropic FCC metal (A_Z = 3.21); high thermal and electrical conductivity."
    }
}
# LiFePO4 (triphylite) is deliberately NOT in the library: its constants in the previous library were
# unsourced and the values recalled by a reviewer (Maxisch & Ceder, Phys. Rev. B 73, 174112, DFT) could not be
# checked against the paper. A formula without an entry gets the isotropic tensor from supplied K_VRH/G_VRH,
# or "unavailable".

# Constants each symmetry class needs (Voigt notation). Nothing missing is filled in.
REQUIRED_CONSTANTS = {
    "cubic": ("c11", "c12", "c44"),
    "hexagonal": ("c11", "c12", "c13", "c33", "c44"),
    "trigonal": ("c11", "c12", "c13", "c14", "c33", "c44"),
    "tetragonal": ("c11", "c12", "c13", "c33", "c44", "c66"),
    "orthorhombic": ("c11", "c22", "c33", "c12", "c13", "c23", "c44", "c55", "c66"),
    "isotropic": ("c11", "c12"),
}


class ElasticityUnavailable(Exception):
    """The requested result cannot be produced from the supplied input without inventing a value."""

    def __init__(self, code: str, reason: str):
        self.code = code
        self.reason = reason
        super().__init__(reason)


def crystal_family(crystal_system):
    """Symmetry family of a crystal-system string, or None when it is not supported."""
    if not isinstance(crystal_system, str):
        return None
    text = crystal_system.lower().strip()
    if "cubic" in text or "fcc" in text or "bcc" in text:
        return "cubic"
    if "hexagonal" in text or "hcp" in text:
        return "hexagonal"
    if "trigonal" in text or "rhombohedral" in text:
        return "trigonal"
    if "tetragonal" in text:
        return "tetragonal"
    if "orthorhombic" in text:
        return "orthorhombic"
    if "isotropic" in text:
        return "isotropic"
    return None


_DESCRIPTIVE_SUFFIX = re.compile(r"\s+\([^()]*\)\s*$")


def lookup_library_entry(formula):
    """Exact library lookup: the formula (a trailing descriptive " (...)" removed) must equal an
    entry's formula token, case-sensitive ("Ni3Al", "Fe3C (Cementite)"). Substring or "nearest"
    matches are never made: "Al2O3" is not aluminium, "TiC" is not titanium. Returns the entry or None."""
    if not isinstance(formula, str):
        return None
    base = _DESCRIPTIVE_SUFFIX.sub("", formula.strip())
    for entry in ELASTIC_CONSTANTS_LIBRARY.values():
        if base == entry["match"]:
            return entry
    return None


_FORMULA_FULL = re.compile(r"(?:[A-Z][a-z]?(?:\d+(?:\.\d+)?)?)+")
_FORMULA_TOKEN = re.compile(r"([A-Z][a-z]?)(\d+(?:\.\d+)?)?")


def parse_formula(formula):
    """{element: count} of a plain formula such as "Fe3C", "LiFePO4" or "Ni3Al (gamma prime)", or None
    when it is not a parsable formula of known elements (groups, charges, free text)."""
    if not isinstance(formula, str):
        return None
    base = _DESCRIPTIVE_SUFFIX.sub("", formula.strip())
    if not base or _FORMULA_FULL.fullmatch(base) is None:
        return None
    counts = {}
    for symbol, number in _FORMULA_TOKEN.findall(base):
        if not physical_constants.is_known_element(symbol):
            return None
        count = float(number) if number else 1.0
        if count <= 0.0:
            return None
        counts[symbol] = counts.get(symbol, 0.0) + count
    return counts or None


def composition_basis(formula):
    """(atoms per formula unit n, formula-unit molar mass M in g/mol) from the composition, or None."""
    counts = parse_formula(formula)
    if counts is None:
        return None
    n_atoms = sum(counts.values())
    mass = sum(count * physical_constants.atomic_weight(el) for el, count in counts.items())
    return n_atoms, mass


_PIVOT_FLOOR = 1e-12
# Relative eigenvalue floor for "all eigenvalues > 0" (Born positive definiteness).
EIGENVALUE_POSITIVE_RTOL = 1e-10


def _min_partial_pivot_exceeds_floor(c: np.ndarray) -> bool:
    """True when every partial-pivoting LU pivot of ``c`` is >= 1e-12 in magnitude.

    Cheap certificate first: the pivots multiply to |det C| and partial pivoting
    bounds the k-th pivot by 2^k * max|C_ij|, so
    min pivot >= |det C| / (2^15 * max|C_ij|^5). Only when that bound does not
    clear the floor (near-singular input) are the actual pivots computed with
    LAPACK getrf (scipy.linalg.lu_factor, imported lazily to keep the common
    path free of the scipy import cost).
    """
    if not np.all(np.isfinite(c)):
        return True  # as before: non-finite input propagates through the inverse
    scale = float(np.max(np.abs(c)))
    if scale == 0.0:
        return False
    sign, logdet = np.linalg.slogdet(c)
    if sign != 0 and logdet - 15.0 * math.log(2.0) - 5.0 * math.log(scale) > math.log(_PIVOT_FLOOR) + 1e-6:
        return True
    from scipy.linalg import LinAlgWarning, lu_factor
    with warnings.catch_warnings():
        # An exactly singular C_ij takes the fallback; do not warn on stderr.
        warnings.simplefilter("ignore", LinAlgWarning)
        lu, _ = lu_factor(c, check_finite=False)
    return bool(np.min(np.abs(np.diag(lu))) >= _PIVOT_FLOOR)


def invert_6x6_matrix(matrix: list[list[float]]) -> list[list[float]]:
    """Invert the 6x6 stiffness matrix C_ij (numpy.linalg.inv, LAPACK LU with
    partial pivoting).

    Near-singular fallback (unchanged): when a partial-pivoting pivot falls below
    1e-12 the diagonal reciprocal 1/max(1e-4, C_ii) is returned instead. These are
    the pivots the former Gauss-Jordan elimination tested.
    """
    c = np.asarray(matrix, dtype=np.float64)
    if not _min_partial_pivot_exceeds_floor(c):
        # Fallback for ill-conditioned or near-singular matrices
        return np.diag(1.0 / np.maximum(1e-4, np.diag(c))).tolist()
    return np.linalg.inv(c).tolist()


def jacobi_eigenvalues_symmetric(matrix: list[list[float]], max_iter: int = 100) -> list[float]:
    """Eigenvalues of the real symmetric 6x6 matrix in ascending order (LAPACK
    symmetric eigensolver, numpy.linalg.eigvalsh). The name is kept for callers;
    ``max_iter`` belonged to the former Jacobi rotation loop and is ignored."""
    return np.linalg.eigvalsh(np.asarray(matrix, dtype=np.float64)).tolist()


def _numeric_or_none(value):
    """float(value) for numbers and numeric strings; None for None, bool, or non-numbers."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalise_space_group(value) -> str:
    return re.sub(r"[\s_]", "", str(value).split("(")[0]).lower()


def _custom_values(user_c_ij, family: str) -> dict:
    """Constants of the supplied C_ij dict; every constant the symmetry class needs must be present."""
    if family == "trigonal" and _numeric_or_none(user_c_ij.get("c15")) not in (None, 0.0):
        raise ElasticityUnavailable(
            "UNSUPPORTED_SYMMETRY_CLASS",
            "a trigonal C_ij with C15 (point groups 3 and -3) is not supported; only -3m, 32 and 3m "
            "(C11 C12 C13 C14 C33 C44) are")
    values = {}
    missing = []
    for key in REQUIRED_CONSTANTS[family]:
        number = _numeric_or_none(user_c_ij.get(key))
        if number is None:
            missing.append(key)
        else:
            values[key] = number
    if missing:
        raise ElasticityUnavailable(
            "MISSING_ELASTIC_CONSTANTS",
            f"custom_c_ij lacks {', '.join(missing)}, which the {family} symmetry class needs; "
            "no constant is filled in from a default")
    return values


def build_stiffness_matrix(crystal_system: str, k_vrh: float, g_vrh: float, formula: str = "", user_c_ij: dict = None) -> tuple[list[list[float]], str]:
    """
    Construct 6x6 stiffness tensor C_ij respecting crystal point group symmetry.
    Priority:
    1. If user explicitly provided custom C_ij entries, use them (all constants of the class are required).
    2. If the formula is an EXACT match of a library entry, use that entry's constants (and its crystal
       system: a different requested system or space group raises ElasticityUnavailable).
    3. Otherwise an isotropic tensor from the supplied K_VRH and G_VRH (both required and positive).
    Raises ElasticityUnavailable instead of inventing a constant.
    """
    c = [[0.0] * 6 for _ in range(6)]
    family = crystal_family(crystal_system)
    entry = lookup_library_entry(formula)

    if user_c_ij and any((_numeric_or_none(v) or 0.0) > 0 for v in user_c_ij.values()):
        if family is None:
            raise ElasticityUnavailable(
                "UNSUPPORTED_CRYSTAL_SYSTEM",
                f"crystal system {crystal_system!r} is not supported (cubic, hexagonal, trigonal, tetragonal, "
                "orthorhombic, isotropic); no isotropic stand-in is substituted")
        source_notes = "Custom User Elastic Constants"
        values = _custom_values(user_c_ij, family)
    elif entry is not None:
        entry_family = crystal_family(entry["crystal_system"])
        if family is not None and family != entry_family:
            raise ElasticityUnavailable(
                "PHASE_MISMATCH",
                f"the library entry for {entry['match']} is the {entry['crystal_system']} phase "
                f"({entry['space_group']}); the requested crystal system {crystal_system!r} is another phase")
        family = entry_family
        source_notes = (f"Built-in elastic-constants library entry (a lookup table, not a DFT calculation): "
                        f"{entry['formula']} ({entry['notes']}); reference status: {entry['reference_status']}; "
                        f"reference: {entry['reference']}")
        if entry["reference_note"]:
            source_notes += f"; caveat: {entry['reference_note']}"
        values = _custom_values(entry["c_ij"], family)
    else:
        if family is None:
            raise ElasticityUnavailable(
                "UNSUPPORTED_CRYSTAL_SYSTEM",
                f"crystal system {crystal_system!r} is not supported (cubic, hexagonal, trigonal, tetragonal, "
                "orthorhombic, isotropic); no isotropic stand-in is substituted")
        k_val, g_val = _numeric_or_none(k_vrh), _numeric_or_none(g_vrh)
        if k_val is None or g_val is None:
            raise ElasticityUnavailable(
                "NO_ELASTIC_CONSTANTS",
                "no exact library entry for this formula, no custom_c_ij, and no K_VRH/G_VRH: there are no "
                "elastic constants to work from (nothing is guessed from a similar formula or a default)")
        if (math.isfinite(k_val) and k_val <= 0.0) or (math.isfinite(g_val) and g_val <= 0.0):
            raise ElasticityUnavailable("NON_POSITIVE_MODULI", "K_VRH and G_VRH must be positive")
        # K = C11 - 4/3*G, C12 = K - 2/3*G, C44 = G: exact isotropic tensor, no perturbation.
        c11 = k_val + (4.0 / 3.0) * g_val
        c12 = k_val - (2.0 / 3.0) * g_val
        values = {"c11": c11, "c12": c12, "c13": c12, "c14": 0.0, "c22": c11, "c23": c12, "c33": c11,
                  "c44": g_val, "c55": g_val, "c66": g_val}
        source_notes = (f"Isotropic tensor from supplied K_VRH={k_val:.1f} GPa, G_VRH={g_val:.1f} GPa "
                        "(no single-crystal C_ij: anisotropy is zero by construction)")

    v = values
    # Crystal Symmetry Enforcement
    if family == "cubic":
        # 3 independent constants: C11, C12, C44
        c11, c12, c44 = v["c11"], v["c12"], v["c44"]
        c[0][0] = c11; c[0][1] = c12; c[0][2] = c12
        c[1][0] = c12; c[1][1] = c11; c[1][2] = c12
        c[2][0] = c12; c[2][1] = c12; c[2][2] = c11
        c[3][3] = c44; c[4][4] = c44; c[5][5] = c44
    elif family in ("hexagonal", "trigonal"):
        # Hexagonal: 5 independent constants C11, C33, C12, C13, C44 and C66 = (C11 - C12)/2.
        # Trigonal (-3m, 32, 3m; Nye / Brugger Voigt form, x1 along a two-fold axis or normal to a mirror):
        # additionally C14 with C24 = -C14, C56 = C14.
        c11, c12, c13, c33, c44 = v["c11"], v["c12"], v["c13"], v["c33"], v["c44"]
        c66_calc = (c11 - c12) / 2.0
        c[0][0] = c11; c[0][1] = c12; c[0][2] = c13
        c[1][0] = c12; c[1][1] = c11; c[1][2] = c13
        c[2][0] = c13; c[2][1] = c13; c[2][2] = c33
        c[3][3] = c44; c[4][4] = c44; c[5][5] = c66_calc
        if family == "trigonal":
            c14 = v["c14"]
            c[0][3] = c14; c[3][0] = c14
            c[1][3] = -c14; c[3][1] = -c14
            c[4][5] = c14; c[5][4] = c14
    elif family == "tetragonal":
        # 6 independent constants: C11, C33, C12, C13, C44, C66
        c11, c12, c13, c33, c44, c66 = v["c11"], v["c12"], v["c13"], v["c33"], v["c44"], v["c66"]
        c[0][0] = c11; c[0][1] = c12; c[0][2] = c13
        c[1][0] = c12; c[1][1] = c11; c[1][2] = c13
        c[2][0] = c13; c[2][1] = c13; c[2][2] = c33
        c[3][3] = c44; c[4][4] = c44; c[5][5] = c66
    elif family == "orthorhombic":
        # 9 independent constants: C11, C22, C33, C12, C13, C23, C44, C55, C66
        c11, c22, c33 = v["c11"], v["c22"], v["c33"]
        c12, c13, c23 = v["c12"], v["c13"], v["c23"]
        c44, c55, c66 = v["c44"], v["c55"], v["c66"]
        c[0][0] = c11; c[0][1] = c12; c[0][2] = c13
        c[1][0] = c12; c[1][1] = c22; c[1][2] = c23
        c[2][0] = c13; c[2][1] = c23; c[2][2] = c33
        c[3][3] = c44; c[4][4] = c55; c[5][5] = c66
    else:
        # Isotropic: C11, C12, and C44 = (C11 - C12)/2
        c11, c12 = v["c11"], v["c12"]
        c66_iso = (c11 - c12) / 2.0
        c[0][0] = c11; c[0][1] = c12; c[0][2] = c12
        c[1][0] = c12; c[1][1] = c11; c[1][2] = c12
        c[2][0] = c12; c[2][1] = c12; c[2][2] = c11
        c[3][3] = c66_iso; c[4][4] = c66_iso; c[5][5] = c66_iso

    return c, source_notes


def evaluate_born_stability_criteria(c: list[list[float]], crystal_system: str) -> dict:
    """
    Evaluate necessary and sufficient Born mechanical stability conditions.
    Reference: Mouhat & Coudert, Physical Review B 90, 045104 (2014).
    """
    family = crystal_family(crystal_system)
    checks = []

    # 1. Eigenvalue condition (universal necessary and sufficient: all eigenvalues > 0)
    eigenvalues = jacobi_eigenvalues_symmetric(c)
    min_eig = min(eigenvalues)
    # Positive definite only above a relative floor: an exactly singular C_ij (e.g.
    # c11 == c12) has a zero eigenvalue that LAPACK returns as +-1e-14-ish rounding
    # noise, which must not count as positive (the former Jacobi loop returned 0.0).
    all_eig_positive = min_eig > EIGENVALUE_POSITIVE_RTOL * max(abs(e) for e in eigenvalues)

    # Criteria evaluation by crystal symmetry
    if family == "cubic":
        # 1. C11 - C12 > 0 (Shear stability)
        val1 = c[0][0] - c[0][1]
        checks.append({
            "name": "Tetragonal Shear Modulus C'",
            "formula": "C11 - C12 > 0",
            "value": round(val1, 2),
            "passed": val1 > 0,
            "physicalMeaning": "Resistance to volume-conserving tetragonal shear deformation"
        })

        # 2. C11 + 2*C12 > 0 (Bulk compressibility / positive bulk modulus)
        val2 = c[0][0] + 2.0 * c[0][1]
        checks.append({
            "name": "Bulk Hydrostatic Compression",
            "formula": "C11 + 2*C12 > 0",
            "value": round(val2, 2),
            "passed": val2 > 0,
            "physicalMeaning": "Lattice must resist uniform hydrostatic volume collapse"
        })

        # 3. C44 > 0 (Trigonal shear stability)
        val3 = c[3][3]
        checks.append({
            "name": "Trigonal Shear Modulus C44",
            "formula": "C44 > 0",
            "value": round(val3, 2),
            "passed": val3 > 0,
            "physicalMeaning": "Resistance to monoclinic / trigonal angular distortion"
        })

    elif family == "hexagonal":
        # Hexagonal Born criteria (Mouhat & Coudert Eq. 2)
        val1 = c[0][0] - abs(c[0][1])
        checks.append({
            "name": "In-Plane Basal Shear",
            "formula": "C11 - |C12| > 0",
            "value": round(val1, 2),
            "passed": val1 > 0,
            "physicalMeaning": "Basal plane shear stiffness stability"
        })

        # 2*C13^2 < C33*(C11 + C12)
        val2 = c[2][2] * (c[0][0] + c[0][1]) - 2.0 * (c[0][2] ** 2)
        checks.append({
            "name": "Coupled Axial Dilatation",
            "formula": "C33*(C11 + C12) - 2*C13² > 0",
            "value": round(val2, 2),
            "passed": val2 > 0,
            "physicalMeaning": "Prevents spontaneous axial c-axis collapse under transverse stress"
        })

        val3 = c[3][3]
        checks.append({
            "name": "Prismatic Shear Modulus C44",
            "formula": "C44 > 0",
            "value": round(val3, 2),
            "passed": val3 > 0,
            "physicalMeaning": "Prismatic out-of-plane shear resistance"
        })

        val4 = c[5][5]
        checks.append({
            "name": "Basal Shear Modulus C66",
            "formula": "C66 = (C11 - C12)/2 > 0",
            "value": round(val4, 2),
            "passed": val4 > 0,
            "physicalMeaning": "In-plane basal angular stiffness"
        })

    elif family == "trigonal":
        # Rhombohedral I (-3m, 32, 3m) Born criteria, Mouhat & Coudert Eq. 5:
        # C11 > |C12|, C44 > 0, C13^2 < C33 (C11 + C12) / 2, C14^2 < C44 (C11 - C12) / 2
        val1 = c[0][0] - abs(c[0][1])
        checks.append({
            "name": "In-Plane Basal Shear",
            "formula": "C11 - |C12| > 0",
            "value": round(val1, 2),
            "passed": val1 > 0,
            "physicalMeaning": "Basal plane shear stiffness stability"
        })
        val2 = c[2][2] * (c[0][0] + c[0][1]) - 2.0 * (c[0][2] ** 2)
        checks.append({
            "name": "Coupled Axial Dilatation",
            "formula": "C33*(C11 + C12) - 2*C13² > 0",
            "value": round(val2, 2),
            "passed": val2 > 0,
            "physicalMeaning": "Prevents spontaneous axial c-axis collapse under transverse stress"
        })
        val3 = c[3][3]
        checks.append({
            "name": "Shear Modulus C44",
            "formula": "C44 > 0",
            "value": round(val3, 2),
            "passed": val3 > 0,
            "physicalMeaning": "Out-of-basal-plane shear resistance"
        })
        val4 = c[3][3] * (c[0][0] - c[0][1]) - 2.0 * (c[0][3] ** 2)
        checks.append({
            "name": "Trigonal Shear Coupling C14",
            "formula": "C44*(C11 - C12) - 2*C14² > 0",
            "value": round(val4, 2),
            "passed": val4 > 0,
            "physicalMeaning": "Coupling between basal and out-of-plane shear must not soften the lattice"
        })

    elif family == "orthorhombic":
        # Orthorhombic Born criteria (Mouhat & Coudert Eq. 1)
        # Principal diagonal > 0
        diag_pass = all(c[i][i] > 0 for i in range(6))
        checks.append({
            "name": "Positive Principal Diagonal Constants",
            "formula": "C11, C22, C33, C44, C55, C66 > 0",
            "value": round(min(c[i][i] for i in range(6)), 2),
            "passed": diag_pass,
            "physicalMeaning": "All uncoupled normal and shear deformations require positive work"
        })

        # Leading 2x2 principal minors
        m12 = c[0][0] * c[1][1] - (c[0][1] ** 2)
        checks.append({
            "name": "Planar Sub-Minor (C11*C22 - C12²)",
            "formula": "C11*C22 - C12² > 0",
            "value": round(m12, 2),
            "passed": m12 > 0,
            "physicalMeaning": "Biaxial planar strain stability in xy plane"
        })

        # 3x3 determinant of normal components
        det_normal = (
            c[0][0] * c[1][1] * c[2][2]
            + 2.0 * c[0][1] * c[0][2] * c[1][2]
            - c[0][0] * (c[1][2] ** 2)
            - c[1][1] * (c[0][2] ** 2)
            - c[2][2] * (c[0][1] ** 2)
        )
        checks.append({
            "name": "Triaxial Determinant det(C_normal)",
            "formula": "det(C_normal) > 0",
            "value": round(det_normal, 2),
            "passed": det_normal > 0,
            "physicalMeaning": "3D volumetric elastic energy positive-definiteness"
        })

    else:
        # Isotropic / tetragonal / General (eigenvalue condition above decides the rest)
        checks.append({
            "name": "Positive Shear Modulus",
            "formula": "G = C44 > 0",
            "value": round(c[3][3], 2),
            "passed": c[3][3] > 0,
            "physicalMeaning": "Material resists shear distortion"
        })
        checks.append({
            "name": "Positive Bulk Modulus",
            "formula": "K = (C11 + 2*C12)/3 > 0",
            "value": round((c[0][0] + 2 * c[0][1]) / 3.0, 2),
            "passed": (c[0][0] + 2 * c[0][1]) > 0,
            "physicalMeaning": "Material resists hydrostatic compression"
        })

    is_stable = all_eig_positive and all(chk["passed"] for chk in checks)

    return {
        "isMechanicallyStable": is_stable,
        "minimumEigenvalueGPa": round(min_eig, 3),
        "allEigenvaluesGPa": [round(e, 2) for e in eigenvalues],
        "verdict": (
            "Mechanically Stable (Passes Born Criteria & Positive Definite Energy)"
            if is_stable
            else "Mechanically Unstable (Violates Born Lattice Stability: Risk of Soft-Mode Phase Transition / Shear Collapse)"
        ),
        "criteriaChecks": checks
    }


def calculate_directional_youngs_modulus_general(s: list[list[float]], direction: list[float]):
    """
    Young's modulus E along the unit direction n (Cartesian components direction = (n1, n2, n3), any
    length) from the FULL Voigt compliance matrix: 1/E = a^T S a with
    a = (n1^2, n2^2, n3^2, n2 n3, n1 n3, n1 n2) (S in engineering-shear Voigt notation), which equals
    n_i n_j n_k n_l S_ijkl. Valid for every crystal system, including the S14 terms of trigonal crystals.
    Returns None when 1/E is not positive (a non-physical compliance).
    """
    h, k, l = direction
    norm = math.sqrt(h * h + k * k + l * l)
    if norm == 0:
        return None
    l1, l2, l3 = h / norm, k / norm, l / norm
    a = (l1 * l1, l2 * l2, l3 * l3, l2 * l3, l1 * l3, l1 * l2)
    inv_e = sum(a[i] * s[i][j] * a[j] for i in range(6) for j in range(6))
    if not inv_e > 0.0:
        return None
    return 1.0 / inv_e


def _require_finite_stiffness(c_matrix, source_notes: str, k_vrh: float, g_vrh: float) -> None:
    """LAPACK eigen/inverse routines need finite C_ij (the former Jacobi/Gauss-Jordan
    loops silently returned NaN/inf-laden results). A non-finite custom_c_ij entry,
    or an infinite k_vrh/g_vrh on the isotropic branch, raises
    input_validation.ValidationError (NON_FINITE)."""
    if all(math.isfinite(v) for row in c_matrix for v in row):
        return
    import input_validation
    if source_notes == "Custom User Elastic Constants":
        field = "custom_c_ij"
    else:
        field = "k_vrh" if not math.isfinite(k_vrh) else "g_vrh"
    raise input_validation.ValidationError(
        input_validation.NON_FINITE, field, "elastic stiffness constants must be finite",
        {"source": source_notes})


# Directions reported for E(n). The labels are lattice [hkl] only where that is exact: cubic (equal
# orthogonal axes) and the cell axes [100], [001] of the orthogonal-axis systems. Every other entry is
# a Cartesian direction (x1 along a, x3 along c): the lattice parameters, which a lattice [hkl] needs,
# are not inputs of this module.
_DIRECTIONS = (
    ([1, 0, 0], "[100]", True),
    ([1, 1, 0], "[110]", False),
    ([1, 1, 1], "[111]", False),
    ([0, 0, 1], "[001]", True),
    ([2, 1, 0], "[210]", False),
    ([3, 1, 1], "[311]", False),
)


def _unavailable_result(reason_code: str, reason: str, start_time: float, formula, crystal_system) -> dict:
    return {
        "success": False,  # envelope shape only; "status" is authoritative (HTTP 200, not an error)
        "status": "unavailable",
        "unavailableCode": reason_code,
        "reason": reason,
        "engine": ENGINE_NAME,
        "scientificModel": "Crystal-Symmetry-Governed Voigt-Reuss-Hill Homogenization & Born Mechanical Stability",
        "label": MODEL_LABEL,
        "isDft": False,
        "computeTimeMs": round((time.time() - start_time) * 1000.0, 2),
        "materialInfo": {"formula": formula, "crystal_system": crystal_system},
    }


def calculate_dft_properties(payload: dict) -> dict:
    """Execute complete continuum elasticity, Born stability, and acoustic property calculations.

    (The function name is historical: nothing here is DFT.) Returns an "unavailable" result (status,
    reason; no numbers) when the input does not determine a tensor without a default or a guess."""
    start_time = time.time()

    formula = payload.get("formula")
    try:
        return _calculate_elasticity(payload, start_time, formula)
    except ElasticityUnavailable as exc:
        return _unavailable_result(exc.code, exc.reason, start_time, formula, payload.get("crystal_system"))


def _optional_float(value):
    return None if value is None else float(value)


def _calculate_elasticity(payload: dict, start_time: float, formula) -> dict:
    material_id = payload.get("material_id", "mp-custom")
    user_c_ij = payload.get("custom_c_ij", None)
    entry = lookup_library_entry(formula)

    crystal_system = payload.get("crystal_system")
    space_group = payload.get("space_group")
    if entry is not None and space_group is not None and \
            _normalise_space_group(space_group) != _normalise_space_group(entry["space_group"]):
        raise ElasticityUnavailable(
            "PHASE_MISMATCH",
            f"the library entry for {entry['match']} is {entry['space_group']}; the requested space group "
            f"{space_group!r} is another phase")
    custom_present = bool(user_c_ij) and any((_numeric_or_none(v) or 0.0) > 0 for v in user_c_ij.values())
    if crystal_system is None:
        if custom_present:
            raise ElasticityUnavailable(
                "MISSING_CRYSTAL_SYSTEM", "custom_c_ij needs the crystal system that fixes its symmetry class")
        crystal_system = entry["crystal_system"] if entry is not None else "Isotropic"
    if space_group is None and entry is not None:
        space_group = entry["space_group"]

    k_vrh = _optional_float(payload.get("k_vrh"))
    g_vrh = _optional_float(payload.get("g_vrh"))
    density = _optional_float(payload.get("density"))
    if density is None and entry is not None:
        density = entry["density"]  # library density (reference status as the entry's)
    formation_e = _optional_float(payload.get("formation_energy_per_atom"))
    e_above_hull = _optional_float(payload.get("energy_above_hull"))
    band_gap = _optional_float(payload.get("band_gap"))

    # 1. Build 6x6 Elastic Stiffness Tensor C_ij (GPa) respecting crystal symmetry
    c_matrix, source_notes = build_stiffness_matrix(crystal_system, k_vrh, g_vrh, formula or "", user_c_ij)
    _require_finite_stiffness(c_matrix, source_notes, k_vrh, g_vrh)
    family = crystal_family(crystal_system)  # a library entry of another family raised PHASE_MISMATCH above
    if source_notes == "Custom User Elastic Constants":
        constants_origin, reference_status = "custom-user-supplied", "supplied-by-caller"
    elif entry is not None:
        constants_origin, reference_status = "builtin-library-exact-match", entry["reference_status"]
    else:
        constants_origin, reference_status = "isotropic-from-supplied-K-G", "supplied-by-caller"

    # 2. Invert to 6x6 Compliance Tensor S_ij (1/GPa)
    s_matrix = invert_6x6_matrix(c_matrix)

    # 3. Evaluate Born Mechanical Stability Criteria & Eigenvalues
    stability_results = evaluate_born_stability_criteria(c_matrix, crystal_system)

    # 4. Voigt Homogenization Bounds
    # K_V = ((C11 + C22 + C33) + 2*(C12 + C23 + C13)) / 9
    k_voigt = (
        (c_matrix[0][0] + c_matrix[1][1] + c_matrix[2][2])
        + 2.0 * (c_matrix[0][1] + c_matrix[1][2] + c_matrix[0][2])
    ) / 9.0

    # G_V = ((C11 + C22 + C33) - (C12 + C23 + C13) + 3*(C44 + C55 + C66)) / 15
    g_voigt = (
        (c_matrix[0][0] + c_matrix[1][1] + c_matrix[2][2])
        - (c_matrix[0][1] + c_matrix[1][2] + c_matrix[0][2])
        + 3.0 * (c_matrix[3][3] + c_matrix[4][4] + c_matrix[5][5])
    ) / 15.0

    # 5. Reuss Homogenization Bounds
    # 1/K_R = (S11 + S22 + S33) + 2*(S12 + S23 + S13)
    s_k_sum = (s_matrix[0][0] + s_matrix[1][1] + s_matrix[2][2]) + 2.0 * (s_matrix[0][1] + s_matrix[1][2] + s_matrix[0][2])
    k_reuss = 1.0 / max(1e-7, s_k_sum)

    # 15/G_R = 4*(S11 + S22 + S33) - 4*(S12 + S23 + S13) + 3*(S44 + S55 + S66)
    s_g_sum = (
        4.0 * ((s_matrix[0][0] + s_matrix[1][1] + s_matrix[2][2]) - (s_matrix[0][1] + s_matrix[1][2] + s_matrix[0][2]))
        + 3.0 * (s_matrix[3][3] + s_matrix[4][4] + s_matrix[5][5])
    )
    g_reuss = 15.0 / max(1e-7, s_g_sum)

    # 6. Hill Averages
    k_calc_vrh = max(1.0, (k_voigt + k_reuss) / 2.0)
    g_calc_vrh = max(1.0, (g_voigt + g_reuss) / 2.0)

    # 7. Young's Modulus & Poisson's Ratio
    youngs_e = (9.0 * k_calc_vrh * g_calc_vrh) / max(1e-6, (3.0 * k_calc_vrh + g_calc_vrh))
    poisson_nu = (3.0 * k_calc_vrh - 2.0 * g_calc_vrh) / max(1e-6, (2.0 * (3.0 * k_calc_vrh + g_calc_vrh)))
    p_wave_modulus = k_calc_vrh + (4.0 / 3.0) * g_calc_vrh

    # 8. Pugh Ductility Ratio (B/G) and Cauchy Pressure
    pugh_ratio = k_calc_vrh / max(0.1, g_calc_vrh)
    cauchy_pressure = c_matrix[0][1] - c_matrix[3][3]  # C12 - C44 (GPa)

    # Ductility assessment based on Pugh (B/G > 1.75), Cauchy pressure, and Poisson's ratio (Frantsevich > 0.26)
    is_ductile = pugh_ratio > 1.75 and poisson_nu > 0.26
    ductility_verdict = (
        "Ductile (Metallic dislocation slip favored; high shear compliance)"
        if is_ductile
        else "Brittle (Directional covalent/ionic bonding; cleavage failure prone)"
    )

    # 9. Anisotropy Indices
    # Universal Anisotropy Index A^U = 5*(G_V / G_R) + (K_V / K_R) - 6
    universal_anisotropy = max(0.0, 5.0 * (g_voigt / max(1e-4, g_reuss)) + (k_voigt / max(1e-4, k_reuss)) - 6.0)

    # Zener Anisotropy Ratio 2*C44 / (C11 - C12): defined for cubic crystals (and trivially 1 for isotropic)
    if family in ("cubic", "isotropic"):
        denom_zener = c_matrix[0][0] - c_matrix[0][1]
        zener_anisotropy = round((2.0 * c_matrix[3][3]) / max(1e-4, abs(denom_zener)), 3)
    else:
        zener_anisotropy = None

    # 10. Acoustic Sound Velocities & Debye Temperature. Only for a mechanically stable tensor (an
    # unstable one has imaginary acoustic modes) and only with a supplied or library density; nothing is
    # clamped or defaulted.
    acoustic, directional_moduli, directional_status, directional_reason = _acoustic_and_directional(
        stability_results["isMechanicallyStable"], density, formula, payload, k_calc_vrh, g_calc_vrh,
        youngs_e, poisson_nu, s_matrix, family)

    elapsed_ms = round((time.time() - start_time) * 1000.0, 2)

    return {
        "success": True,
        "status": "available",
        "engine": ENGINE_NAME,
        "scientificModel": "Crystal-Symmetry-Governed Voigt-Reuss-Hill Homogenization & Born Mechanical Stability",
        "label": MODEL_LABEL,
        "isDft": False,
        "constantsOrigin": constants_origin,
        "referenceStatus": reference_status,
        "sourceNotes": source_notes,
        "computeTimeMs": elapsed_ms,
        "materialInfo": {
            "formula": formula,
            "material_id": material_id,
            "crystal_system": crystal_system,
            "space_group": space_group,
            "density": density,
            "formation_energy_per_atom": formation_e,
            "energy_above_hull": e_above_hull,
            "band_gap": band_gap,
            "is_stable": None if e_above_hull is None else e_above_hull <= 0.005,
            "is_metal": None if band_gap is None else band_gap < 0.05
        },
        "elasticStiffnessMatrix_Cij_GPa": [[round(val, 2) for val in row] for row in c_matrix],
        "elasticComplianceMatrix_Sij_1_over_GPa": [[round(val, 6) for val in row] for row in s_matrix],
        "bornStability": stability_results,
        "voigtReussHillModuli": {
            "bulkModulus_K_Voigt_GPa": round(k_voigt, 2),
            "bulkModulus_K_Reuss_GPa": round(k_reuss, 2),
            "bulkModulus_K_VRH_GPa": round(k_calc_vrh, 2),
            "shearModulus_G_Voigt_GPa": round(g_voigt, 2),
            "shearModulus_G_Reuss_GPa": round(g_reuss, 2),
            "shearModulus_G_VRH_GPa": round(g_calc_vrh, 2),
            "youngsModulus_E_VRH_GPa": round(youngs_e, 2),
            "poissonsRatio_nu": round(poisson_nu, 3),
            "pWaveModulus_GPa": round(p_wave_modulus, 2)
        },
        "mechanicalIntegrityIndices": {
            "pughRatio_B_over_G": round(pugh_ratio, 3),
            "cauchyPressure_C12_minus_C44_GPa": round(cauchy_pressure, 2),
            "ductilityVerdict": ductility_verdict,
            "universalAnisotropyIndex_AU": round(universal_anisotropy, 4),
            "zenerAnisotropyFactor_AZ": zener_anisotropy,
            "isIsotropic": universal_anisotropy < 0.05
        },
        "acousticAndThermalProperties": acoustic,
        "directionalYoungsModuli": directional_moduli,
        "directionalYoungsModuliStatus": directional_status,
        "directionalYoungsModuliReason": directional_reason
    }


def _acoustic_and_directional(stable: bool, density, formula, payload: dict, k_vrh: float, g_vrh: float,
                              youngs_e: float, poisson_nu: float, s_matrix, family):
    """Acoustic/thermal block and the E(n) list; every value is a number or None with a reason."""
    acoustic = {
        "status": "unavailable", "reason": None,
        "longitudinalSoundVelocity_m_s": None, "transverseSoundVelocity_m_s": None,
        "meanSoundVelocity_m_s": None, "debyeTemperature_K": None,
        "gruneisenParameter_gamma": None, "minimumThermalConductivity_W_mK": None,
        "debyeBasis": None,
    }
    if not stable:
        reason = ("the stiffness tensor is not mechanically stable (Born criteria / positive definiteness): "
                  "acoustic velocities and the Debye temperature are not defined")
        acoustic["reason"] = reason
        return acoustic, None, "unavailable", reason
    directional = []
    for hkl, label, is_axis in _DIRECTIONS:
        e_dir = calculate_directional_youngs_modulus_general(s_matrix, hkl)
        lattice = family == "cubic" or is_axis
        directional.append({
            "direction": label,
            "hkl": hkl,
            "frame": "lattice" if lattice else "cartesian",
            "label": label if lattice else f"({hkl[0]},{hkl[1]},{hkl[2]}) Cartesian",
            "youngsModulusGPa": None if e_dir is None else round(e_dir, 2),
            "ratioToAverage": None if e_dir is None else round(e_dir / max(0.1, youngs_e), 3)
        })
    if density is None or not math.isfinite(density) or density <= 0.0:
        acoustic["reason"] = ("no positive density supplied (density, g/cm^3) and no library entry for this "
                              "formula: sound velocities and the Debye temperature need the density")
        return acoustic, directional, "available", None
    rho_si = density * 1000.0  # kg/m^3
    v_longitudinal = math.sqrt(max(0.0, (k_vrh + 4.0 / 3.0 * g_vrh) * 1e9) / rho_si)
    v_transverse = math.sqrt(max(0.0, g_vrh * 1e9) / rho_si)

    inv_vm3 = (1.0 / max(1.0, v_longitudinal ** 3) + 2.0 / max(1.0, v_transverse ** 3)) / 3.0
    v_mean = math.pow(1.0 / max(1e-15, inv_vm3), 1.0 / 3.0)
    acoustic.update(status="available", reason=None,
                    longitudinalSoundVelocity_m_s=round(v_longitudinal, 1),
                    transverseSoundVelocity_m_s=round(v_transverse, 1),
                    meanSoundVelocity_m_s=round(v_mean, 1))
    if poisson_nu < 2.0 / 3.0:
        # Belomestnykh-Teslenko high-temperature Gruneisen parameter from Poisson's ratio
        acoustic["gruneisenParameter_gamma"] = round(1.5 * ((1.0 + poisson_nu) / (2.0 - 3.0 * poisson_nu)), 2)

    # Debye temperature and minimum thermal conductivity need the atomic number density, i.e. the number
    # of ATOMS per formula unit and the formula-unit molar mass, both from the composition (the cell site
    # count nsites is not that quantity).
    basis = composition_basis(formula)
    basis_source = "composition (formula parsed; CIAAW 2021 atomic weights, physical_constants)"
    ignored = {}
    supplied_mass = _numeric_or_none(payload.get("molar_mass"))
    supplied_atoms = _numeric_or_none(payload.get("atoms_per_formula_unit"))
    if basis is None and supplied_mass is not None and supplied_atoms is not None \
            and supplied_mass > 0.0 and supplied_atoms > 0.0:
        basis = (supplied_atoms, supplied_mass)
        basis_source = "supplied atoms_per_formula_unit and molar_mass (formula could not be parsed)"
    elif basis is not None and supplied_mass is not None:
        ignored["molar_mass"] = "composition-derived formula-unit mass is used"
    if payload.get("nsites") is not None:
        ignored["nsites"] = "cell site count is not the atoms per formula unit; not used"
    if basis is None:
        acoustic["reason"] = ("Debye temperature and minimum thermal conductivity unavailable: the formula is "
                              "not a parsable composition and no atoms_per_formula_unit with molar_mass "
                              "(g/mol, per formula unit) was supplied; there is no default molar mass")
        return acoustic, directional, "available", None
    n_atoms, formula_mass = basis
    atom_density = n_atoms * AVOGADRO_CONSTANT_NA * rho_si / (formula_mass / 1000.0)  # atoms per m^3
    debye_temp_k = (PLANCK_CONSTANT_H / BOLTZMANN_CONSTANT_KB) * math.pow((3.0 * atom_density) / (4.0 * math.pi), 1.0 / 3.0) * v_mean
    kappa_min = 0.87 * BOLTZMANN_CONSTANT_KB * math.pow(atom_density, 2.0 / 3.0) * math.sqrt(youngs_e * 1e9 / rho_si)
    acoustic.update(
        debyeTemperature_K=round(debye_temp_k, 1),
        minimumThermalConductivity_W_mK=round(kappa_min, 3),
        debyeBasis={
            "atomsPerFormulaUnit": n_atoms,
            "formulaUnitMolarMass_g_mol": round(formula_mass, 4),
            "meanAtomicMass_g_mol": round(formula_mass / n_atoms, 4),
            "atomNumberDensity_per_m3": atom_density,
            "source": basis_source,
            "reference": DEBYE_REFERENCE,
            "ignoredInputs": ignored,
        })
    return acoustic, directional, "available", None


def main():
    """CLI & JSON stdin entrypoint."""
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "--status":
            print(json.dumps({
                "status": "ready",
                "engine": "MetalliX Continuum Elasticity & Crystal Symmetry Homogenizer",
                "isDft": False,
                "pythonVersion": sys.version.split()[0],
                "capabilities": [
                    "Crystal-Symmetry 6x6 Stiffness Construction",
                    "Born Mechanical Stability & Jacobi Eigenvalues",
                    "Exact Matrix Inversion for Compliance Tensor S_ij",
                    "Voigt-Reuss-Hill Homogenization Bounds",
                    "Universal Elastic Anisotropy A^U & Zener Ratio",
                    "Directional Young's Modulus E(n)",
                    "Acoustic Wave Velocities & Debye Temperature"
                ]
            }))
            return

        if len(sys.argv) > 1 and sys.argv[1] != "-":
            raw_input = sys.argv[1]
        else:
            raw_input = sys.stdin.read()

        if not raw_input.strip():
            payload = {
                "formula": "Fe3C (Cementite)",
                "crystal_system": "Orthorhombic",
                "space_group": "Pnma"
            }
        else:
            payload = json.loads(raw_input)

        result = calculate_dft_properties(payload)
        print(json.dumps(result))
    except Exception as e:
        validation = sys.modules.get("input_validation")
        if validation is not None and isinstance(e, validation.ValidationError):
            # Phase 6a envelope: invalid input, not a solver failure (HTTP 422 in the bridge).
            print(json.dumps(validation.validation_envelope(e)))
            sys.exit(2)
        sys.stderr.write(f"Elasticity Calculator Error: {str(e)}\n")
        print(json.dumps({
            "success": False,
            "error": str(e),
            "engine": ENGINE_NAME
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()
