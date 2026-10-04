#!/usr/bin/env python3
"""
Domain data for the Phase 6a tranche-2a solvers: calphad_solver,
battery_corrosion_eis_solver and icme_multiscale_pipeline_solver.

Structural step (a) only. Every number here is a copy of the value the solver used
at BASE_REVISION, including rounded/truncated constants and legacy rounded atomic
weights, so the solver output stays bit-identical. The value step (b) swaps them
for the exact physical_constants records; see the drift preview in the tranche-2a
handoff.

Provenance honesty (RULES.md section 2): no value below carries a per-value
citation in its solver, so the solver-local values are tagged ``estimated``. The
truncated R/F printings are tagged ``literature`` like physical_constants does for
CODATA values, with ``exact=False`` and a note naming the truncation.

Leaf module: standard library + physical_constants only, no numpy/scipy at import.
alloy_registry imports it (one delimited block); no manifest file may import it
until the planned implementation-fingerprint bump.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Dict, Mapping, Tuple

from physical_constants import LEGACY_GAS_CONSTANT_R_4SF, Constant, atomic_weight

DATA_VERSION = "alloy-data-calphad-battery-icme-1"
BASE_REVISION = "7f3f803"

# --------------------------------------------------------------------------- legacy constants
# Rounded/truncated printings of R and F found in the solvers at BASE_REVISION. The
# 8.314462618 / 96485.33212 truncations already exist as
# physical_constants.TRUNCATED_GAS_CONSTANT_R / TRUNCATED_FARADAY and are not repeated.
_CODATA = "NIST CODATA 2018"
_TRUNC_NOTE = ("Rounded printing of the CODATA value kept for bit-identical output in Phase 6a "
               "step (a); not exact. Replaced by the exact SI product in step (b).")

# The value itself lives in physical_constants (single authority, shared with the
# kinetics and stochastic UQ solvers); this record only adds unit/source metadata.
LEGACY_R_8_314 = Constant(LEGACY_GAS_CONSTANT_R_4SF, "J/(mol*K)", f"{_CODATA} R, rounded to 3 decimals",
                          False, note=_TRUNC_NOTE)
LEGACY_R_8_31446 = Constant(8.31446, "J/(mol*K)", f"{_CODATA} R, rounded to 5 decimals", False,
                            note=_TRUNC_NOTE)
LEGACY_F_96485_332 = Constant(96485.332, "C/mol", f"{_CODATA} F, rounded to 3 decimals", False,
                              note=_TRUNC_NOTE)
LEGACY_F_96485_33 = Constant(96485.33, "C/mol", f"{_CODATA} F, rounded to 2 decimals", False,
                             note=_TRUNC_NOTE)

# Where each truncated constant is used (solver file, function) -> (R, F) names.
# "TRUNCATED_*" refers to physical_constants; None means the site uses no F.
# Design step (b) removed the calphad, battery_corrosion_eis_solver and
# icme_multiscale_pipeline_solver sites (exact SI R/F); no site is left.
LEGACY_CONSTANT_SITES: Mapping[Tuple[str, str], Tuple[str, object]] = MappingProxyType({})

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
