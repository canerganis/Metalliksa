#!/usr/bin/env python3
"""
MetalliX Continuum Elasticity & Crystal Symmetry Homogenization Engine
Author: MetalliX Computational Materials Science Suite

Scientific Scope:
- Crystal-symmetry-governed 6x6 Elastic Stiffness Tensor (C_ij) construction across crystal systems
  (Cubic, Hexagonal, Tetragonal, Orthorhombic, Trigonal, and Isotropic).
- Matrix inversion (LAPACK LU with partial pivoting, numpy.linalg.inv) for the Compliance
  Tensor (S_ij = C_ij^-1), with the near-singular diagonal fallback.
- Born Mechanical Stability Criteria validation (Mouhat & Coudert, Phys. Rev. B 2014) with
  eigenvalues from the LAPACK symmetric eigensolver (numpy.linalg.eigvalsh).
- Voigt, Reuss, and Hill (VRH) bounds for bulk (K) and shear (G) moduli.
- Ranganathan-Ostoja-Starzewski Universal Elastic Anisotropy Index (A^U) and Zener anisotropy (A_Z).
- Crystallographic directional Young's modulus E(hkl) via generalized direction-cosine tensor contraction.
- Ductility, brittleness, and bonding character evaluation via Pugh's ratio (B/G), Cauchy pressure (C_12 - C_44),
  and Frantsevich Poisson's ratio criterion.
- Anderson acoustic velocities (longitudinal, transverse, mean) and Debye temperature (Theta_D).
"""

import sys
import json
import math
import time
import warnings

import numpy as np

# Fundamental Physical Constants (CODATA 2018)
PLANCK_CONSTANT_H = 6.62607015e-34  # J*s
BOLTZMANN_CONSTANT_KB = 1.380649e-23  # J/K
AVOGADRO_CONSTANT_NA = 6.02214076e23  # mol^-1

# Authentic Literature & Materials Project DFT Single-Crystal Elastic Constants Benchmark Library
# All values in GPa
AUTHENTIC_ELASTIC_BENCHMARKS = {
    "fe3c": {
        "formula": "Fe3C (Cementite)",
        "crystal_system": "Orthorhombic",
        "space_group": "Pnma (62)",
        "c_ij": {
            "c11": 385.0, "c22": 340.0, "c33": 320.0,
            "c12": 156.0, "c13": 162.0, "c23": 160.0,
            "c44": 63.0,  "c55": 61.0,  "c66": 85.0
        },
        "density": 7.68,
        "molar_mass": 179.55,
        "nsites": 16,
        "formation_energy_per_atom": 0.076,
        "energy_above_hull": 0.024,
        "band_gap": 0.0,
        "notes": "Metastable orthorhombic carbide; high hardness, directional Fe-C covalent-metallic bonding."
    },
    "lifepo4": {
        "formula": "LiFePO4 (Triphylite)",
        "crystal_system": "Orthorhombic",
        "space_group": "Pnma (62)",
        "c_ij": {
            "c11": 139.0, "c22": 178.0, "c33": 172.0,
            "c12": 65.0,  "c13": 52.0,  "c23": 48.0,
            "c44": 37.0,  "c55": 49.0,  "c66": 44.0
        },
        "density": 3.59,
        "molar_mass": 157.76,
        "nsites": 28,
        "formation_energy_per_atom": -2.312,
        "energy_above_hull": 0.0,
        "band_gap": 3.72,
        "notes": "Olivine cathode; strong [010] 1D Li-ion transport channels, moderate anisotropy."
    },
    "ni3al": {
        "formula": "Ni3Al (γ' Precipitate)",
        "crystal_system": "Cubic",
        "space_group": "Pm-3m (221)",
        "c_ij": {
            "c11": 223.0, "c12": 148.0, "c44": 125.0
        },
        "density": 7.42,
        "molar_mass": 203.07,
        "nsites": 4,
        "formation_energy_per_atom": -0.425,
        "energy_above_hull": 0.0,
        "band_gap": 0.0,
        "notes": "L1_2 ordered superalloy strengthener; high Zener anisotropy A_Z ~ 3.33."
    },
    "ti3alc2": {
        "formula": "Ti3AlC2 (MAX Phase)",
        "crystal_system": "Hexagonal",
        "space_group": "P6_3/mmc (194)",
        "c_ij": {
            "c11": 360.0, "c33": 350.0, "c12": 90.0, "c13": 85.0, "c44": 120.0
        },
        "density": 4.25,
        "molar_mass": 194.63,
        "nsites": 12,
        "formation_energy_per_atom": -0.742,
        "energy_above_hull": 0.0,
        "band_gap": 0.0,
        "notes": "Layered ternary carbide; metallic electrical conductivity with ceramic temperature resistance."
    },
    "zno": {
        "formula": "ZnO (Wurtzite)",
        "crystal_system": "Hexagonal",
        "space_group": "P6_3mc (186)",
        "c_ij": {
            "c11": 209.0, "c33": 216.0, "c12": 120.0, "c13": 104.0, "c44": 44.0
        },
        "density": 5.56,
        "molar_mass": 81.38,
        "nsites": 4,
        "formation_energy_per_atom": -1.785,
        "energy_above_hull": 0.0,
        "band_gap": 0.73,
        "notes": "Piezoelectric semiconductor; polar hexagonal wurtzite structure."
    },
    "niti": {
        "formula": "NiTi (B2 Austenite)",
        "crystal_system": "Cubic",
        "space_group": "Pm-3m (221)",
        "c_ij": {
            "c11": 162.0, "c12": 130.0, "c44": 34.0
        },
        "density": 6.45,
        "molar_mass": 106.38,
        "nsites": 2,
        "formation_energy_per_atom": -0.384,
        "energy_above_hull": 0.0,
        "band_gap": 0.0,
        "notes": "Nitinol shape memory alloy; low C' = (C11 - C12)/2 = 16 GPa precedes thermoelastic martensitic transformation."
    },
    "wc": {
        "formula": "WC (Tungsten Carbide)",
        "crystal_system": "Hexagonal",
        "space_group": "P-6m2 (187)",
        "c_ij": {
            "c11": 720.0, "c33": 970.0, "c12": 250.0, "c13": 150.0, "c44": 290.0
        },
        "density": 15.63,
        "molar_mass": 195.85,
        "nsites": 2,
        "formation_energy_per_atom": -0.218,
        "energy_above_hull": 0.0,
        "band_gap": 0.0,
        "notes": "Ultra-hard transition metal carbide; high shear modulus and severe brittleness."
    },
    "fe": {
        "formula": "α-Fe (Ferrite BCC)",
        "crystal_system": "Cubic",
        "space_group": "Im-3m (229)",
        "c_ij": {
            "c11": 230.0, "c12": 135.0, "c44": 117.0
        },
        "density": 7.87,
        "molar_mass": 55.85,
        "nsites": 2,
        "formation_energy_per_atom": 0.0,
        "energy_above_hull": 0.0,
        "band_gap": 0.0,
        "notes": "Ferromagnetic BCC iron; Zener anisotropy A_Z = 2.46."
    },
    "ni": {
        "formula": "Ni (Nickel FCC)",
        "crystal_system": "Cubic",
        "space_group": "Fm-3m (225)",
        "c_ij": {
            "c11": 247.0, "c12": 147.0, "c44": 125.0
        },
        "density": 8.90,
        "molar_mass": 58.69,
        "nsites": 4,
        "formation_energy_per_atom": 0.0,
        "energy_above_hull": 0.0,
        "band_gap": 0.0,
        "notes": "FCC matrix base for nickel superalloys; high ductility."
    },
    "ti": {
        "formula": "α-Ti (Titanium HCP)",
        "crystal_system": "Hexagonal",
        "space_group": "P6_3/mmc (194)",
        "c_ij": {
            "c11": 162.4, "c33": 180.7, "c12": 92.0, "c13": 69.0, "c44": 46.7
        },
        "density": 4.51,
        "molar_mass": 47.87,
        "nsites": 2,
        "formation_energy_per_atom": 0.0,
        "energy_above_hull": 0.0,
        "band_gap": 0.0,
        "notes": "Hexagonal close-packed room-temperature titanium; moderate elastic anisotropy."
    },
    "al": {
        "formula": "Al (Aluminium FCC)",
        "crystal_system": "Cubic",
        "space_group": "Fm-3m (225)",
        "c_ij": {
            "c11": 108.0, "c12": 62.0, "c44": 28.3
        },
        "density": 2.70,
        "molar_mass": 26.98,
        "nsites": 4,
        "formation_energy_per_atom": 0.0,
        "energy_above_hull": 0.0,
        "band_gap": 0.0,
        "notes": "Nearly isotropic FCC metal (A_Z = 1.23); low density."
    },
    "w": {
        "formula": "W (Tungsten BCC)",
        "crystal_system": "Cubic",
        "space_group": "Im-3m (229)",
        "c_ij": {
            "c11": 523.0, "c12": 203.0, "c44": 160.0
        },
        "density": 19.25,
        "molar_mass": 183.84,
        "nsites": 2,
        "formation_energy_per_atom": 0.0,
        "energy_above_hull": 0.0,
        "band_gap": 0.0,
        "notes": "Unique among elemental metals for being almost perfectly elastically isotropic (A_Z = 1.00)."
    },
    "cu": {
        "formula": "Cu (Copper FCC)",
        "crystal_system": "Cubic",
        "space_group": "Fm-3m (225)",
        "c_ij": {
            "c11": 168.4, "c12": 121.4, "c44": 75.4
        },
        "density": 8.96,
        "molar_mass": 63.55,
        "nsites": 4,
        "formation_energy_per_atom": 0.0,
        "energy_above_hull": 0.0,
        "band_gap": 0.0,
        "notes": "Highly anisotropic FCC metal (A_Z = 3.21); high thermal and electrical conductivity."
    }
}


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


def build_stiffness_matrix(crystal_system: str, k_vrh: float, g_vrh: float, formula: str = "", user_c_ij: dict = None) -> tuple[list[list[float]], str]:
    """
    Construct 6x6 stiffness tensor C_ij respecting crystal point group symmetry.
    Priority:
    1. If user explicitly provided custom C_ij entries, use them and enforce symmetry.
    2. If recognized benchmark material, load authentic DFT/experimental single-crystal constants.
    3. If isotropic or generic input: build mathematically consistent tensor without arbitrary perturbation factors.
    """
    c = [[0.0] * 6 for _ in range(6)]
    sys_lower = crystal_system.lower().strip()
    clean_formula = formula.lower().replace(" ", "").replace("-", "")
    
    # Check if formula matches authentic benchmark
    matched_benchmark = None
    for key, data in AUTHENTIC_ELASTIC_BENCHMARKS.items():
        if key in clean_formula or clean_formula.startswith(key):
            matched_benchmark = data
            break
            
    source_notes = "User / Generic Moduli"
    
    if user_c_ij and any(v > 0 for v in user_c_ij.values()):
        source_notes = "Custom User Elastic Constants"
        # User supplied values
        c11 = float(user_c_ij.get("c11", 200.0))
        c12 = float(user_c_ij.get("c12", 100.0))
        c13 = float(user_c_ij.get("c13", c12))
        c22 = float(user_c_ij.get("c22", c11))
        c23 = float(user_c_ij.get("c23", c13))
        c33 = float(user_c_ij.get("c33", c11))
        c44 = float(user_c_ij.get("c44", 80.0))
        c55 = float(user_c_ij.get("c55", c44))
        c66 = float(user_c_ij.get("c66", c44))
    elif matched_benchmark:
        source_notes = f"Authentic DFT Benchmark: {matched_benchmark['formula']} ({matched_benchmark['notes']})"
        bm_c = matched_benchmark["c_ij"]
        c11 = bm_c.get("c11", 200.0)
        c22 = bm_c.get("c22", c11)
        c33 = bm_c.get("c33", c11)
        c12 = bm_c.get("c12", 100.0)
        c13 = bm_c.get("c13", c12)
        c23 = bm_c.get("c23", c13)
        c44 = bm_c.get("c44", 80.0)
        c55 = bm_c.get("c55", c44)
        c66 = bm_c.get("c66", (c11 - c12) / 2.0 if "hexagonal" in sys_lower else c44)
    else:
        # Generate mathematically exact isotropic baseline without arbitrary distortions
        # K = C11 - 4/3*G, C12 = K - 2/3*G, C44 = G
        k_val = max(10.0, k_vrh)
        g_val = max(5.0, g_vrh)
        c11 = k_val + (4.0 / 3.0) * g_val
        c12 = k_val - (2.0 / 3.0) * g_val
        c44 = g_val
        c22 = c11
        c33 = c11
        c13 = c12
        c23 = c12
        c55 = c44
        c66 = c44
        source_notes = f"Isotropic Baseline ({k_val:.1f} GPa bulk, {g_val:.1f} GPa shear)"

    # Crystal Symmetry Enforcement
    if "cubic" in sys_lower or "fcc" in sys_lower or "bcc" in sys_lower:
        # 3 independent constants: C11, C12, C44
        c[0][0] = c11; c[0][1] = c12; c[0][2] = c12
        c[1][0] = c12; c[1][1] = c11; c[1][2] = c12
        c[2][0] = c12; c[2][1] = c12; c[2][2] = c11
        c[3][3] = c44; c[4][4] = c44; c[5][5] = c44
    elif "hexagonal" in sys_lower or "hcp" in sys_lower or "trigonal" in sys_lower:
        # 5 independent constants: C11, C33, C12, C13, C44. Note C66 = (C11 - C12)/2
        c66_calc = (c11 - c12) / 2.0
        c[0][0] = c11; c[0][1] = c12; c[0][2] = c13
        c[1][0] = c12; c[1][1] = c11; c[1][2] = c13
        c[2][0] = c13; c[2][1] = c13; c[2][2] = c33
        c[3][3] = c44; c[4][4] = c44; c[5][5] = c66_calc
    elif "tetragonal" in sys_lower:
        # 6 independent constants: C11, C33, C12, C13, C44, C66
        c[0][0] = c11; c[0][1] = c12; c[0][2] = c13
        c[1][0] = c12; c[1][1] = c11; c[1][2] = c13
        c[2][0] = c13; c[2][1] = c13; c[2][2] = c33
        c[3][3] = c44; c[4][4] = c44; c[5][5] = c66
    elif "orthorhombic" in sys_lower:
        # 9 independent constants: C11, C22, C33, C12, C13, C23, C44, C55, C66
        c[0][0] = c11; c[0][1] = c12; c[0][2] = c13
        c[1][0] = c12; c[1][1] = c22; c[1][2] = c23
        c[2][0] = c13; c[2][1] = c23; c[2][2] = c33
        c[3][3] = c44; c[4][4] = c55; c[5][5] = c66
    else:
        # Isotropic default
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
    sys_lower = crystal_system.lower().strip()
    checks = []
    
    # 1. Eigenvalue condition (universal necessary and sufficient: all eigenvalues > 0)
    eigenvalues = jacobi_eigenvalues_symmetric(c)
    min_eig = min(eigenvalues)
    # Positive definite only above a relative floor: an exactly singular C_ij (e.g.
    # c11 == c12) has a zero eigenvalue that LAPACK returns as +-1e-14-ish rounding
    # noise, which must not count as positive (the former Jacobi loop returned 0.0).
    all_eig_positive = min_eig > EIGENVALUE_POSITIVE_RTOL * max(abs(e) for e in eigenvalues)
    
    # Criteria evaluation by crystal symmetry
    if "cubic" in sys_lower or "fcc" in sys_lower or "bcc" in sys_lower:
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

    elif "hexagonal" in sys_lower or "hcp" in sys_lower:
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

    elif "orthorhombic" in sys_lower:
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
        # Isotropic / General
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


def calculate_directional_youngs_modulus_general(s: list[list[float]], direction_hkl: list[float]) -> float:
    """
    Compute Young's modulus E in crystallographic direction [h k l] using generalized
    direction cosine tensor contraction for orthorhombic, tetragonal, hexagonal, and cubic crystals.
    1/E(l1,l2,l3) = l1^4*S11 + l2^4*S22 + l3^4*S33 + l2^2*l3^2*(2*S23 + S44) + l1^2*l3^2*(2*S13 + S55) + l1^2*l2^2*(2*S12 + S66)
    """
    h, k, l = direction_hkl
    norm = math.sqrt(h * h + k * k + l * l)
    if norm == 0:
        return 0.0
    l1, l2, l3 = h / norm, k / norm, l / norm
    
    inv_e = (
        (l1 ** 4) * s[0][0]
        + (l2 ** 4) * s[1][1]
        + (l3 ** 4) * s[2][2]
        + (l2 ** 2) * (l3 ** 2) * (2.0 * s[1][2] + s[3][3])
        + (l1 ** 2) * (l3 ** 2) * (2.0 * s[0][2] + s[4][4])
        + (l1 ** 2) * (l2 ** 2) * (2.0 * s[0][1] + s[5][5])
    )
    
    if inv_e <= 1e-7:
        return 1.0 / max(1e-5, s[0][0])
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


def calculate_dft_properties(payload: dict) -> dict:
    """Execute complete continuum elasticity, Born stability, and acoustic property calculations."""
    start_time = time.time()
    
    formula = payload.get("formula", "Fe3C (Cementite)")
    material_id = payload.get("material_id", "mp-custom")
    crystal_system = payload.get("crystal_system", "Orthorhombic")
    space_group = payload.get("space_group", "Pnma")
    
    k_vrh = float(payload.get("k_vrh", 165.0))
    g_vrh = float(payload.get("g_vrh", 78.0))
    density = float(payload.get("density", 7.85))
    formation_e = float(payload.get("formation_energy_per_atom", -0.45))
    e_above_hull = float(payload.get("energy_above_hull", 0.0))
    band_gap = float(payload.get("band_gap", 0.0))
    nsites = int(payload.get("nsites", 4))
    molar_mass = float(payload.get("molar_mass", 55.85))
    user_c_ij = payload.get("custom_c_ij", None)

    # 1. Build 6x6 Elastic Stiffness Tensor C_ij (GPa) respecting crystal symmetry
    c_matrix, source_notes = build_stiffness_matrix(crystal_system, k_vrh, g_vrh, formula, user_c_ij)
    _require_finite_stiffness(c_matrix, source_notes, k_vrh, g_vrh)

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
    
    # Zener Anisotropy Ratio (for cubic crystals: 2*C44 / (C11 - C12))
    denom_zener = c_matrix[0][0] - c_matrix[0][1]
    zener_anisotropy = (2.0 * c_matrix[3][3]) / max(1e-4, abs(denom_zener))

    # 10. Acoustic Sound Velocities & Debye Temperature
    rho_si = max(500.0, density * 1000.0)  # kg/m^3
    v_longitudinal = math.sqrt(max(0.0, (k_calc_vrh + 4.0 / 3.0 * g_calc_vrh) * 1e9) / rho_si)
    v_transverse = math.sqrt(max(0.0, g_calc_vrh * 1e9) / rho_si)
    
    inv_vm3 = (1.0 / max(1.0, v_longitudinal ** 3) + 2.0 / max(1.0, v_transverse ** 3)) / 3.0
    v_mean = math.pow(1.0 / max(1e-15, inv_vm3), 1.0 / 3.0)

    # Debye Temperature Theta_D
    molar_mass_kg = max(0.005, molar_mass / 1000.0)
    n_atoms_per_formula = max(1, nsites)
    atom_density = (n_atoms_per_formula * AVOGADRO_CONSTANT_NA * rho_si) / molar_mass_kg
    debye_temp_k = (PLANCK_CONSTANT_H / BOLTZMANN_CONSTANT_KB) * math.pow((3.0 * atom_density) / (4.0 * math.pi), 1.0 / 3.0) * v_mean

    # Thermal Transport Parameters
    gruneisen_gamma = 1.5 * ((1.0 + poisson_nu) / max(0.1, (2.0 - 3.0 * poisson_nu)))
    kappa_min = 0.87 * BOLTZMANN_CONSTANT_KB * math.pow(atom_density, 2.0 / 3.0) * math.sqrt(youngs_e * 1e9 / rho_si)

    # 11. Crystallographic Directional Young's Modulus E(hkl) Profile
    directions = [
        {"hkl": [1, 0, 0], "label": "[100]"},
        {"hkl": [1, 1, 0], "label": "[110]"},
        {"hkl": [1, 1, 1], "label": "[111]"},
        {"hkl": [0, 0, 1], "label": "[001]"},
        {"hkl": [2, 1, 0], "label": "[210]"},
        {"hkl": [3, 1, 1], "label": "[311]"},
    ]
    directional_moduli = []
    for d in directions:
        e_dir = calculate_directional_youngs_modulus_general(s_matrix, d["hkl"])
        directional_moduli.append({
            "direction": d["label"],
            "hkl": d["hkl"],
            "youngsModulusGPa": round(e_dir, 2),
            "ratioToAverage": round(e_dir / max(0.1, youngs_e), 3)
        })

    elapsed_ms = round((time.time() - start_time) * 1000.0, 2)

    return {
        "success": True,
        "engine": "MetalliX-Continuum-Elasticity-Homogenizer-v4.0",
        "scientificModel": "Crystal-Symmetry-Governed Voigt-Reuss-Hill Homogenization & Born Mechanical Stability",
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
            "is_stable": e_above_hull <= 0.005,
            "is_metal": band_gap < 0.05
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
            "zenerAnisotropyFactor_AZ": round(zener_anisotropy, 3),
            "isIsotropic": universal_anisotropy < 0.05
        },
        "acousticAndThermalProperties": {
            "longitudinalSoundVelocity_m_s": round(v_longitudinal, 1),
            "transverseSoundVelocity_m_s": round(v_transverse, 1),
            "meanSoundVelocity_m_s": round(v_mean, 1),
            "debyeTemperature_K": round(debye_temp_k, 1),
            "gruneisenParameter_gamma": round(gruneisen_gamma, 2),
            "minimumThermalConductivity_W_mK": round(kappa_min, 3)
        },
        "directionalYoungsModuli": directional_moduli
    }


def main():
    """CLI & JSON stdin entrypoint."""
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "--status":
            print(json.dumps({
                "status": "ready",
                "engine": "MetalliX Continuum Elasticity & Crystal Symmetry Homogenizer",
                "pythonVersion": sys.version.split()[0],
                "capabilities": [
                    "Crystal-Symmetry 6x6 Stiffness Construction",
                    "Born Mechanical Stability & Jacobi Eigenvalues",
                    "Exact Matrix Inversion for Compliance Tensor S_ij",
                    "Voigt-Reuss-Hill Homogenization Bounds",
                    "Universal Elastic Anisotropy A^U & Zener Ratio",
                    "Generalized Directional Young's Modulus E(hkl)",
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
                "k_vrh": 228.4,
                "g_vrh": 74.2,
                "density": 7.68,
                "formation_energy_per_atom": 0.076,
                "energy_above_hull": 0.024,
                "nsites": 16,
                "molar_mass": 179.55
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
            "engine": "MetalliX-Continuum-Elasticity-Homogenizer-v4.0"
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()
