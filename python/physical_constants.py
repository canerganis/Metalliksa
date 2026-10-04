#!/usr/bin/env python3
"""
Physical constants and standard atomic weights for the free (non-LPBF-core) solvers.

Leaf module: standard library only, no numpy/scipy at import. It must NOT be
imported by any file listed in lpbf_simulation.IMPLEMENTATION_SOURCE_FILES until
the planned implementation-fingerprint bump (see test_phase6a_leaf_modules.py).

Sources
-------
- SI defining constants (exact since the 2019 SI redefinition), as listed in
  CODATA 2018: N_A, k, e. R and F are exact products of defining constants:
  R = N_A * k, F = N_A * e. NIST CODATA 2018, https://physics.nist.gov/cuu/Constants/
- 273.15 K is the exact offset of the Celsius scale (SI Brochure, 9th ed., 2019, 2.3.1).
- Standard atomic weights: IUPAC CIAAW, "Standard atomic weights of the elements
  2021", Pure Appl. Chem. 94 (2022) 573-600, https://www.ciaaw.org . The value
  used in calculations is the CIAAW abridged five-significant-figure value; the
  standard interval or uncertainty range is kept for validation.

Record metadata
---------------
Both record types carry ``source_type`` (same vocabulary as
alloy_registry.SOURCE_TYPES) and ``validity``. CODATA/SI defined constants and
CIAAW standard atomic weights are tagged ``literature`` (a cited standard table),
with a note saying what kind of value it is. ``validity`` is an applicability
range (lo, hi, unit) or None when the source states none. The CIAAW standard
interval is the isotopic-abundance spread of normal terrestrial material; it is
an uncertainty/variability range, NOT an applicability validity range, so it is
kept separately in ``AtomicWeight.interval`` and ``validity`` stays None.

Exact versus truncated R and F
------------------------------
GAS_CONSTANT_R and FARADAY below are the full exact products N_A*k and N_A*e.
The free solvers (tafel_corrosion_rate_solver, pourbaix_solver, calphad_solver)
use the CODATA printed truncations 8.314462618 and 96485.33212. Those differ from
the exact values by about 1.84e-11 (R) and 3.4e-11 (F) relative, so a structural
migration step that swaps in these records cannot be bit-exact against golden
outputs; test_physical_constants pins the deltas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

CONSTANTS_VERSION = "physical-constants-1"
SI_EXACT_SOURCE = "CODATA 2018 / SI 2019 exact"
CIAAW_SOURCE = "IUPAC CIAAW standard atomic weights 2021 (abridged five-figure values)"
# Same vocabulary as alloy_registry.SOURCE_TYPES (kept local: this module is a leaf).
SOURCE_TYPES = frozenset({"measured", "literature", "estimated", "computed", "synthetic"})
DEFINED_CONSTANT_NOTE = (
    "Cited standard value (CODATA 2018 / SI 2019); exact by definition, tagged literature."
)
ATOMIC_WEIGHT_NOTE = (
    "CIAAW 2021 standard atomic weight for normal terrestrial material; tagged literature. "
    "The interval is isotopic variability, not an applicability validity range."
)
# CODATA printed truncations used by tafel/pourbaix/calphad today (not exact).
TRUNCATED_GAS_CONSTANT_R = 8.314462618
TRUNCATED_FARADAY = 96485.33212


def _check_metadata(source_type: str, validity: object) -> None:
    if source_type not in SOURCE_TYPES:
        raise ValueError(f"Invalid source_type {source_type!r}")
    if validity is not None:
        if (not isinstance(validity, tuple) or len(validity) != 3
                or not isinstance(validity[2], str) or not validity[2]):
            raise ValueError("validity must be None or a (lo, hi, unit) tuple")


@dataclass(frozen=True)
class Constant:
    """One physical constant with unit, provenance, exactness flag and metadata.

    ``validity`` is an applicability range (lo, hi, unit) or None when the source
    states none; None does not mean "valid everywhere".
    """

    value: float
    unit: str
    source: str
    exact: bool
    source_type: str = "literature"
    validity: Optional[Tuple[Optional[float], Optional[float], str]] = None
    note: str = DEFINED_CONSTANT_NOTE

    def __post_init__(self) -> None:
        _check_metadata(self.source_type, self.validity)


# SI 2019 defining constant, exact (CODATA 2018).
AVOGADRO = Constant(6.02214076e23, "1/mol", SI_EXACT_SOURCE, True)
# SI 2019 defining constant, exact (CODATA 2018).
BOLTZMANN = Constant(1.380649e-23, "J/K", SI_EXACT_SOURCE, True)
# SI 2019 defining constant, exact (CODATA 2018).
ELEMENTARY_CHARGE = Constant(1.602176634e-19, "C", SI_EXACT_SOURCE, True)
# Exact: N_A * k = 8.31446261815324 J/(mol K) (CODATA 2018 lists 8.314 462 618... exact).
GAS_CONSTANT_R = Constant(8.31446261815324, "J/(mol*K)", SI_EXACT_SOURCE + " (N_A*k)", True)
# Exact: N_A * e = 96485.3321233100184 C/mol (CODATA 2018 lists 96 485.332 12... exact).
FARADAY = Constant(96485.3321233100184, "C/mol", SI_EXACT_SOURCE + " (N_A*e)", True)
# Exact Celsius offset (SI Brochure 9th ed., 2019).
ZERO_CELSIUS_K = Constant(273.15, "K", "SI Brochure 9th ed. (2019), exact definition", True)


class UnknownElementError(KeyError):
    """Raised when an element symbol has no CIAAW standard atomic weight here."""

    def __init__(self, element: object):
        self.element = element
        super().__init__(
            f"Unknown element {element!r}: no standard atomic weight is registered "
            f"(no fallback value is used)."
        )

    def __str__(self) -> str:  # KeyError would otherwise repr() the message
        return str(self.args[0])


@dataclass(frozen=True)
class AtomicWeight:
    """CIAAW 2021 standard atomic weight.

    ``value`` is the abridged five-significant-figure value used in calculations.
    ``interval`` is the CIAAW standard range: for single-valued elements it is
    value +/- the stated uncertainty; for interval elements it is the published
    [lower, upper] interval. ``interval`` is variability/uncertainty, not
    applicability validity: ``validity`` is a separate (lo, hi, unit) range or
    None when the source states none.
    """

    symbol: str
    value: float
    interval: Tuple[float, float]
    source: str = CIAAW_SOURCE
    unit: str = "g/mol"
    source_type: str = "literature"
    validity: Optional[Tuple[Optional[float], Optional[float], str]] = None
    note: str = ATOMIC_WEIGHT_NOTE

    def __post_init__(self) -> None:
        _check_metadata(self.source_type, self.validity)


def _aw(symbol: str, abridged: float, lo: float, hi: float) -> AtomicWeight:
    return AtomicWeight(symbol, abridged, (lo, hi))


# Every entry below is from the CIAAW 2021 table (Pure Appl. Chem. 94 (2022) 573).
# Columns: abridged value, then the standard interval [lo, hi]. For single-valued
# elements [lo, hi] = standard value -/+ its stated uncertainty, quoted in comments.
STANDARD_ATOMIC_WEIGHTS: Dict[str, AtomicWeight] = {
    a.symbol: a
    for a in (
        _aw("H", 1.008, 1.00784, 1.00811),        # interval [1.00784, 1.00811]
        _aw("B", 10.81, 10.806, 10.821),          # interval [10.806, 10.821]
        _aw("C", 12.011, 12.0096, 12.0116),       # interval [12.0096, 12.0116]
        _aw("N", 14.007, 14.00643, 14.00728),     # interval [14.00643, 14.00728]
        _aw("O", 15.999, 15.99903, 15.99977),     # interval [15.99903, 15.99977]
        _aw("Mg", 24.305, 24.304, 24.307),        # interval [24.304, 24.307]
        _aw("Al", 26.982, 26.9815381, 26.9815387),  # 26.9815384(3)
        _aw("Si", 28.085, 28.084, 28.086),        # interval [28.084, 28.086]
        _aw("P", 30.974, 30.973761993, 30.973762003),  # 30.973761998(5)
        _aw("S", 32.06, 32.059, 32.076),          # interval [32.059, 32.076]
        _aw("Ti", 47.867, 47.866, 47.868),        # 47.867(1)
        _aw("V", 50.942, 50.9414, 50.9416),       # 50.9415(1)
        _aw("Cr", 51.996, 51.9955, 51.9967),      # 51.9961(6)
        _aw("Mn", 54.938, 54.938041, 54.938045),  # 54.938043(2)
        _aw("Fe", 55.845, 55.843, 55.847),        # 55.845(2)
        _aw("Co", 58.933, 58.933191, 58.933197),  # 58.933194(3)
        _aw("Ni", 58.693, 58.6930, 58.6938),      # 58.6934(4)
        _aw("Cu", 63.546, 63.543, 63.549),        # 63.546(3)
        _aw("Zn", 65.38, 65.36, 65.40),           # 65.38(2)
        _aw("Y", 88.906, 88.905836, 88.905840),   # 88.905838(2)
        _aw("Zr", 91.224, 91.222, 91.226),        # 91.224(2)
        _aw("Nb", 92.906, 92.90636, 92.90638),    # 92.90637(1)
        _aw("Mo", 95.95, 95.94, 95.96),           # 95.95(1)
        _aw("Ru", 101.07, 101.05, 101.09),        # 101.07(2)
        _aw("Sn", 118.71, 118.703, 118.717),      # 118.710(7)
        _aw("Hf", 178.49, 178.480, 178.492),      # 178.486(6)
        _aw("Ta", 180.95, 180.94786, 180.94790),  # 180.94788(2)
        _aw("W", 183.84, 183.83, 183.85),         # 183.84(1)
        _aw("Re", 186.21, 186.206, 186.208),      # 186.207(1)
        _aw("Pt", 195.08, 195.075, 195.093),      # 195.084(9)
        _aw("Au", 196.97, 196.966566, 196.966574),  # 196.966570(4)
    )
}


def _normalise_symbol(element: object) -> Optional[str]:
    """Accept canonical case ("Fe") or the all-uppercase TDB convention ("FE").

    Lowercase or mixed forms ("fe", "cO") are rejected rather than guessed, so
    that e.g. "co" is never silently read as cobalt.
    """
    if not isinstance(element, str):
        return None
    text = element.strip()
    if not text or not text.isalpha() or not text.isascii() or len(text) > 2:
        return None
    if text.isupper():
        return text[0] + text[1:].lower()
    if text[0].isupper() and text[1:].islower():
        return text
    return None


def atomic_weight_record(element: object) -> AtomicWeight:
    """Return the CIAAW record for ``element``; raise UnknownElementError otherwise."""
    symbol = _normalise_symbol(element)
    if symbol is None or symbol not in STANDARD_ATOMIC_WEIGHTS:
        raise UnknownElementError(element)
    return STANDARD_ATOMIC_WEIGHTS[symbol]


def atomic_weight(element: object) -> float:
    """Abridged CIAAW 2021 standard atomic weight in g/mol. No silent fallback."""
    return atomic_weight_record(element).value


def is_known_element(element: object) -> bool:
    symbol = _normalise_symbol(element)
    return symbol is not None and symbol in STANDARD_ATOMIC_WEIGHTS


def provenance() -> Dict[str, str]:
    """Compact provenance block for solver outputs."""
    return {
        "constantsVersion": CONSTANTS_VERSION,
        "constantsSource": SI_EXACT_SOURCE,
        "atomicWeightsSource": CIAAW_SOURCE,
    }
