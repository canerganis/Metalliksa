#!/usr/bin/env python3
"""
Domain data for the Phase 6a tranche-2a solvers: calphad_solver,
battery_corrosion_eis_solver and icme_multiscale_pipeline_solver.

Phase 6a design step (b) (value commits) replaced every rounded/truncated R/F
printing and every legacy atomic weight that step (a) had copied here with the
exact physical_constants records (SI 2019 R = N_A*k, F = N_A*e; CIAAW 2021
abridged atomic weights); those legacy records were removed. What remains is
solver-local domain data.

Provenance honesty (RULES.md section 2): no value below carries a per-value
citation in its solver, so the solver-local values are tagged ``estimated``.

Leaf module: standard library + physical_constants only, no numpy/scipy at import.
alloy_registry imports it (one delimited block); no manifest file may import it
until the planned implementation-fingerprint bump.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Dict, Mapping, Tuple

from physical_constants import atomic_weight

# -2: design step (b) (exact R/F, CIAAW weights; legacy constant records removed).
DATA_VERSION = "alloy-data-calphad-battery-icme-2"
BASE_REVISION = "7f3f803"

# --------------------------------------------------------------------------- calphad
# Design step (b): calphad_solver takes every atomic weight from
# physical_constants.STANDARD_ATOMIC_WEIGHTS (CIAAW 2021 abridged) and refuses symbols
# without one. Its former 28-symbol table (identical CIAAW values) and the 50.0 g/mol
# stand-in for every other symbol were removed; the pre-migration table stays
# snapshotted in golden/phase6a/calphad_solver/_source_tables.json.

# --------------------------------------------------------------------------- icme
DOMAIN_ICME = "icme"
_ICME_REF = f"icme_multiscale_pipeline_solver.py @{BASE_REVISION}"
# The 16 elements the solver has Scale-0 data for (the keys of its pre-migration
# atomic_weights table, icme_multiscale_pipeline_solver.py:118-122 @BASE_REVISION, in
# that order). Design step (b): their weights are the CIAAW 2021 abridged values from
# physical_constants; the legacy rounded copies (58.69, 55.85, 52.00, ... up to
# 0.005 g/mol off) were removed. They stay snapshotted in
# golden/phase6a/icme_multiscale_pipeline_solver/_source_tables.json.
ICME_ELEMENTS: Tuple[str, ...] = (
    "Ni", "Fe", "Cr", "Mo", "Nb", "Ti", "Al", "C", "Si", "Mn", "V", "W", "Co", "Cu", "Mg", "Zn",
)

# Base metals with a Scale-0 data branch in the solver (Ni, Fe, Ti; everything else
# fell into the Al branch before the migration).
ICME_BASE_METALS: Tuple[str, ...] = ("Ni", "Fe", "Ti", "Al")

ICME_T_MELT_NOTE = (
    "Johnson-Cook T_melt screening value per base metal, copied from the solver; no citation. "
    "Ni 1350 and Fe 1450 degC are below the pure-metal melting points (1455 / 1538 degC) and "
    "look like alloy values; Ti 1650 vs 1668 degC; Al 660 degC is pure Al."
)
# icme_multiscale_pipeline_solver.py:292 t_melt_C chain, per base metal (degC).
ICME_JOHNSON_COOK_T_MELT_C: Mapping[str, float] = MappingProxyType({
    "Ni": 1350.0, "Fe": 1450.0, "Ti": 1650.0, "Al": 660.0,
})

# Alloy-keyed icme data, wired into alloy_registry as domain "icme".
# icme_multiscale_pipeline_solver.py:28-30: default solute composition when the
# payload has no composition_wt (Inconel 718 solutes; Ni is the balance).
ICME_UNITS: Mapping[str, str] = MappingProxyType({"default_solute_composition_wt": "wt%"})
ICME_ALLOY_TABLES: Mapping[str, Mapping[str, object]] = MappingProxyType({
    "in718": MappingProxyType({
        "default_solute_composition_wt": MappingProxyType({
            "Cr": 19.0, "Fe": 18.0, "Nb": 5.1, "Mo": 3.0, "Ti": 0.9, "Al": 0.5, "C": 0.05,
            "Si": 0.2, "Mn": 0.2,
        }),
    }),
})
ICME_DEFAULT_ALLOY_ID = "in718"

# --------------------------------------------------------------------------- registry wiring
REGISTRY_NOTE = "Solver-local screening value copied unchanged; no per-value citation in source."
# domain -> (alloy-keyed table, units, source_ref); consumed by alloy_registry's
# tranche-2a block.
REGISTRY_DOMAIN_TABLES: Mapping[str, Tuple[Mapping[str, Mapping[str, object]], Mapping[str, str], str]] = (
    MappingProxyType({
        DOMAIN_ICME: (ICME_ALLOY_TABLES, ICME_UNITS, f"{_ICME_REF} :28-30 default composition_wt"),
    })
)


class UnsupportedElementError(KeyError):
    """An element (or base metal) the solver has no data for. No fallback is used."""

    def __init__(self, element: object, domain: str, supported: Tuple[str, ...]):
        self.element = element
        self.domain = domain
        self.supported = tuple(supported)
        super().__init__(
            f"No {domain} data for element {element!r}; supported: {', '.join(self.supported)} "
            f"(no fallback value is used)."
        )

    def __str__(self) -> str:
        return str(self.args[0])


def icme_atomic_weight(element: object) -> float:
    """CIAAW 2021 abridged weight of one of the 16 ICME elements; others are refused."""
    if not isinstance(element, str) or element not in ICME_ELEMENTS:
        raise UnsupportedElementError(element, "icme atomic-weight", ICME_ELEMENTS)
    return atomic_weight(element)


def icme_base_metal(base: object) -> str:
    if not isinstance(base, str) or base not in ICME_BASE_METALS:
        raise UnsupportedElementError(base, "icme base-metal", ICME_BASE_METALS)
    return base


def provenance() -> Dict[str, str]:
    return {"domainDataVersion": DATA_VERSION, "domainDataBaseRevision": BASE_REVISION}
