#!/usr/bin/env python3
"""
Phase 6a tranche 2b domain data: phase-transformation kinetics, stochastic UQ and
LPBF fatigue/fracture (plus the phase9 process-map name mapping).

Leaf module: standard library only, no numpy/scipy, no local imports. It is read by
alloy_registry (one delimited block: EXTRA_ALIASES) and by the migrated solvers
kinetics_ttt_cct_solver, stochastic_uq_mmpds_solver, lpbf_fatigue_fracture and
phase9_surrogate. It must NOT be imported by any file in
lpbf_simulation.IMPLEMENTATION_SOURCE_FILES until the planned fingerprint bump.

Numeric kinetics and fatigue values are NOT here: they already live in
alloy_registry (_KINETICS, _FATIGUE_FRACTURE domains). This module holds what the
registry does not model:
- kinetics descriptors per alloy (class label that selects the JMAK branch,
  phase list, description) and the legacy solver names;
- stochastic UQ base-metal lattice/elastic constants, solute potencies and the
  precipitation activation energy (keyed by base metal, not by alloy);
- the UQ request defaults (default alloy label, spec, nominal chemistry, tolerances);
- the phase9 process-map material name mapping.

All numbers are copied unchanged from the solvers at BASE_REVISION (structural step
(a) of DESIGN-6a). None carries a per-value citation in the source, so every value
is tagged ``estimated`` (RULES.md section 2): see SOURCES. ``validity`` is None
everywhere: the source states no validity range, which does not mean "valid
everywhere".

Silent defaults that step (a) deliberately KEEPS (listed for step (b)):
- uq_lattice_constants(): an unknown base metal returns the Al constants
  (UQ_LEGACY_FALLBACK_BASE_METAL), exactly like the old if/elif/else chain;
- UQ_DEFAULT_SOLUTE_POTENCY: an unlisted solute gets potency 5.0.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Dict, Mapping, Tuple

DATA_VERSION = "alloy-data-kinetics-uq-fatigue-1"
BASE_REVISION = "7f3f803"

_EST = "estimated"
_NO_CITATION = "Solver-local screening value copied unchanged; no per-value citation in source."

# Provenance per table: source_type, source_ref (file:lines @revision), note.
SOURCES: Mapping[str, Mapping[str, str]] = MappingProxyType({
    "kinetics_descriptors": MappingProxyType({
        "sourceType": _EST, "validity": None,
        "sourceRef": f"kinetics_ttt_cct_solver.py:14-98 ALLOY_KINETICS_DB (type/phases/description) @{BASE_REVISION}",
        "note": "Labels; 'type' selects the JMAK nose/Avrami branch. No citation in source."}),
    "uq_lattice": MappingProxyType({
        "sourceType": _EST, "validity": None,
        "sourceRef": f"stochastic_uq_mmpds_solver.py:224-260 solve_single_realization @{BASE_REVISION}",
        "note": _NO_CITATION}),
    "uq_solute_potency": MappingProxyType({
        "sourceType": _EST, "validity": None,
        "sourceRef": f"stochastic_uq_mmpds_solver.py:272-278 misfit_weights @{BASE_REVISION}",
        "note": _NO_CITATION + " Unlisted solutes use UQ_DEFAULT_SOLUTE_POTENCY (kept silent default)."}),
    "uq_precipitation": MappingProxyType({
        "sourceType": _EST, "validity": None,
        "sourceRef": f"stochastic_uq_mmpds_solver.py:296 Q_diff @{BASE_REVISION}",
        "note": _NO_CITATION}),
    "uq_request_defaults": MappingProxyType({
        "sourceType": _EST, "validity": None,
        "sourceRef": f"stochastic_uq_mmpds_solver.py:358-373 and :735-739 @{BASE_REVISION}",
        "note": "Request defaults (IN718-like nominal chemistry and tolerances), not a specification."}),
    "process_map_names": MappingProxyType({
        "sourceType": _EST, "validity": None,
        "sourceRef": f"phase9_surrogate.py:71 query_mat mapping @{BASE_REVISION}",
        "note": "Name mapping to data/synthetic_process_map.csv 'Material' values."}),
})

# --------------------------------------------------------------------------- registry aliases
# UI strings harvested from src/ that did not resolve before this tranche. Every
# other string the four target components send already resolves (see
# test_alloy_data_kinetics_uq_fatigue.UI_NAMES). Not added: UQLab dataset
# "Hastelloy X Combustor Sheet (AMS 5754)" / "hastelloy-x-ams5754" (no registry
# record; the UQ solver uses alloyName only as a label).
EXTRA_ALIASES: Mapping[str, Tuple[str, ...]] = MappingProxyType({
    # stochastic_uq_mmpds_solver.py:358/:736 default alloyName
    # src/components/uqLabData.ts:302 dataset name (UQLab sends `alloyName: activeDataset.name`)
    "in718": ("Inconel 718 (Aero LPBF)", "Inconel 718 Forged Turbine Disks (AMS 5664)"),
    # uqLabData.ts:340
    "ti6al4v": ("Ti-6Al-4V Grade 5 Airframe Billets (AMS 4928)",),
    # uqLabData.ts:377-378 dataset id and name
    "al7075": ("al7075-t651", "Al 7075-T651 Aerospace Plate (AMS 4045)"),
    # uqLabData.ts:416
    "aisi4340": ("AISI 4340 Ultra-High Strength VAR (AMS 6414)",),
    # uqLabData.ts:453-454 dataset id and name
    "alsi10mg": ("alsi10mg-lpbf-ams4215", "AlSi10Mg Additive LPBF As-Built & SR (AMS 4215)"),
})

# --------------------------------------------------------------------------- kinetics
# Legacy ALLOY_KINETICS_DB keys (the strings PhaseKineticsTTTCCTStudio sends), in the
# original table order. Equal to alloy_registry._KINETICS_SOURCE_NAME (tested).
KINETICS_LEGACY_NAMES: Mapping[str, str] = MappingProxyType({
    "aisi4140": "AISI 4140", "aisi4340": "AISI 4340", "aisid2": "AISI D2",
    "in718": "Inconel 718", "ti6al4v": "Ti-6Al-4V", "al7075": "Al 7075",
})

# Key order of the legacy ALLOY_KINETICS_DB entries (output "alloyMetadata" order).
KINETICS_METADATA_KEYS: Tuple[str, ...] = (
    "type", "composition_wt", "Ae3_C", "Ae1_C", "Ms_C", "Mf_C", "Q_diff_kJ_mol",
    "grain_size_d_um_default", "aust_temp_C_default", "phases",
    "critical_cooling_rate_C_s", "description",
)
KINETICS_DESCRIPTOR_KEYS = frozenset({"type", "phases", "description"})

KINETICS_DESCRIPTORS: Mapping[str, Mapping[str, Any]] = MappingProxyType({
    "aisi4140": MappingProxyType({
        "type": "Low-Alloy Steel",
        "phases": ("Ferrite", "Pearlite", "Bainite", "Martensite"),
        "description": "Medium-carbon Cr-Mo through-hardening alloy steel for shafts and landing gears.",
    }),
    "aisi4340": MappingProxyType({
        "type": "High-Strength Ni-Cr-Mo Steel",
        "phases": ("Ferrite", "Pearlite", "Bainite", "Martensite"),
        "description": "Ultra-high strength structural steel with high hardenability and fracture toughness.",
    }),
    "aisid2": MappingProxyType({
        "type": "Cold-Work High-Carbon High-Cr Tool Steel",
        "phases": ("Proeutectoid Carbides", "Pearlite", "Bainite", "Martensite", "Retained Austenite"),
        "description": "High wear-resistant ledeburitic tool steel with M7C3 carbides.",
    }),
    "in718": MappingProxyType({
        "type": "Precipitation-Hardenable Ni-Fe Superalloy",
        "phases": ("Gamma Prime (Ni3Al,Ti)", "Gamma Double Prime (Ni3Nb)",
                   "Delta (Ni3Nb orthorhombic)", "Laves TCP"),
        "description": "Aerospace superalloy hardened by coherent metastable gamma double prime (bct-DO22).",
    }),
    "ti6al4v": MappingProxyType({
        "type": "Alpha-Beta Titanium Alloy",
        "phases": ("Equiaxed Alpha", "Lamellar Alpha+Beta (Widmanstatten)", "Alpha-Prime Martensite (HCP)"),
        "description": "Workhorse titanium alloy; transformation kinetics govern lamellar vs equiaxed microstructure.",
    }),
    "al7075": MappingProxyType({
        "type": "Precipitation-Hardenable Al-Zn-Mg-Cu Alloy",
        "phases": ("GP Zones", "Eta-Prime (MgZn2)", "Eta Equilibrium (MgZn2)"),
        "description": "Ultra-high strength aerospace aluminum susceptible to quench-sensitivity and stress corrosion.",
    }),
})

# --------------------------------------------------------------------------- fatigue / fracture
# Legacy ALLOY_FATIGUE_DATABASE keys (MurakamiFatigueLab AVAILABLE_ALLOYS), in the
# original order. Equal to alloy_registry._FATIGUE_FRACTURE_SOURCE_NAME (tested).
FATIGUE_LEGACY_NAMES: Mapping[str, str] = MappingProxyType({
    "ti6al4v": "Ti-6Al-4V", "ss316l": "316L SS", "in718": "Inconel 718", "alsi10mg": "AlSi10Mg",
})
FATIGUE_KEYS: Tuple[str, ...] = (
    "hardness_HV", "smooth_fatigue_limit_MPa", "threshold_stress_intensity_MPa_m",
    "fracture_toughness_K_IC", "paris_C", "paris_m",
)

# --------------------------------------------------------------------------- stochastic UQ
UQ_LATTICE_UNITS: Mapping[str, str] = MappingProxyType({
    "a0": "angstrom", "b_nm": "nm", "C11": "GPa", "C12": "GPa", "C44": "GPa",
    "taylor_M": "1", "sigma_0": "MPa", "k_hp": "MPa*um^0.5", "nu": "1", "G_c_kJ_m2": "kJ/m^2",
})

UQ_BASE_METAL_LATTICE: Mapping[str, Mapping[str, float]] = MappingProxyType({
    "Ni": MappingProxyType({"a0": 3.585, "b_nm": 0.2535, "C11": 247.0, "C12": 147.0, "C44": 125.0,
                            "taylor_M": 3.06, "sigma_0": 78.0, "k_hp": 750.0, "nu": 0.31,
                            "G_c_kJ_m2": 45.0}),
    "Fe": MappingProxyType({"a0": 2.866, "b_nm": 0.2482, "C11": 237.0, "C12": 141.0, "C44": 116.0,
                            "taylor_M": 2.75, "sigma_0": 85.0, "k_hp": 600.0, "nu": 0.29,
                            "G_c_kJ_m2": 50.0}),
    "Ti": MappingProxyType({"a0": 2.950, "b_nm": 0.2950, "C11": 160.0, "C12": 90.0, "C44": 46.5,
                            "taylor_M": 4.20, "sigma_0": 180.0, "k_hp": 420.0, "nu": 0.34,
                            "G_c_kJ_m2": 38.0}),
    "Al": MappingProxyType({"a0": 4.049, "b_nm": 0.2863, "C11": 108.0, "C12": 61.0, "C44": 28.5,
                            "taylor_M": 3.06, "sigma_0": 25.0, "k_hp": 180.0, "nu": 0.33,
                            "G_c_kJ_m2": 18.0}),
})
# KEPT silent default (step (a)): the old chain was `if Ni / elif Fe / elif Ti / else Al`.
UQ_LEGACY_FALLBACK_BASE_METAL = "Al"


def uq_lattice_constants(base_metal: object) -> Mapping[str, float]:
    """Lattice/elastic constants for ``base_metal``, with the legacy Al fallback.

    Mirrors the old ``base_metal == "Ni"`` / ``"Fe"`` / ``"Ti"`` / else chain
    exactly (equality, not hashing, so unhashable JSON values fall through too).
    """
    for key in ("Ni", "Fe", "Ti"):
        if base_metal == key:
            return UQ_BASE_METAL_LATTICE[key]
    return UQ_BASE_METAL_LATTICE[UQ_LEGACY_FALLBACK_BASE_METAL]


UQ_SOLUTE_POTENCY: Mapping[str, float] = MappingProxyType({
    "Nb": 14.5, "Mo": 8.5, "Ti": 11.2, "Al": 6.8, "Cr": 4.2,
    "V": 7.5, "Fe": 3.8, "W": 16.2, "Ta": 18.0, "C": 280.0, "Si": 22.0, "Mg": 14.0,
})
UQ_SOLUTE_POTENCY_UNIT = "MPa/(wt%)^0.67"
# KEPT silent default (step (a)): an unlisted solute gets this potency.
UQ_DEFAULT_SOLUTE_POTENCY = 5.0

UQ_PRECIPITATION_Q_J_MOL = 265000.0  # J/mol

UQ_DEFAULT_ALLOY_NAME = "Inconel 718 (Aero LPBF)"
UQ_DEFAULT_BASE_METAL = "Ni"
UQ_DEFAULT_STANDARD_SPEC = "AMS 5662 / AMS 5664"
_UQ_DEFAULT_COMPOSITION_WT = (
    ("Cr", 19.0), ("Fe", 18.0), ("Nb", 5.1), ("Mo", 3.0), ("Ti", 0.9), ("Al", 0.5), ("C", 0.05), ("Si", 0.2),
)
_UQ_DEFAULT_COMPOSITION_TOLERANCES = (
    ("Cr", 1.0), ("Fe", 1.0), ("Nb", 0.35), ("Mo", 0.3), ("Ti", 0.15), ("Al", 0.1), ("C", 0.015), ("Si", 0.08),
)


def uq_default_composition_wt() -> Dict[str, float]:
    """Fresh copy (insertion order = Sobol dimension order) of the default chemistry."""
    return dict(_UQ_DEFAULT_COMPOSITION_WT)


def uq_default_composition_tolerances() -> Dict[str, float]:
    return dict(_UQ_DEFAULT_COMPOSITION_TOLERANCES)


# --------------------------------------------------------------------------- phase9 process map
# phase9_surrogate maps a request name to the data/synthetic_process_map.csv
# "Material" value. Only "IN718" (case-insensitive) is renamed; every other name
# passes through unchanged (an unmatched name selects no CSV rows, as before).
PROCESS_MAP_MATERIAL_NAMES: Mapping[str, str] = MappingProxyType({"IN718": "Inconel 718"})


def process_map_material_name(alloy_name: str) -> str:
    return PROCESS_MAP_MATERIAL_NAMES.get(alloy_name.upper(), alloy_name)


def provenance() -> Dict[str, Any]:
    return {"domainDataVersion": DATA_VERSION, "domainDataBaseRevision": BASE_REVISION}
