#!/usr/bin/env python3
"""
Murakami sqrt(area) geometry constants, shared by the two Murakami engines.

Leaf module: standard library + input_validation only. It must NOT be imported by
any file listed in lpbf_simulation.IMPLEMENTATION_SOURCE_FILES (see
test_phase6a_leaf_modules.py). Used by murakami_fatigue_screening.py (build-job /
industrial screening) and lpbf_fatigue_fracture.py (Phase 13 lab); before this
module each file carried its own copy and they disagreed.

Source
------
Y. Murakami, "Metal Fatigue: Effects of Small Defects and Nonmetallic Inclusions",
Elsevier (2002; 2nd ed. 2019): the fatigue limit for a defect of projected area
``area`` (um^2), Vickers hardness HV (kgf/mm^2) is

    sigma_w = C * (HV + 120) / (sqrt(area))^(1/6)        [MPa]

with C = 1.43 for a defect on the surface, 1.41 for a defect in contact with the
surface (sub-surface, "touching" the surface) and 1.56 for a defect in the interior.
Checked on the web against secondary literature quoting the book (2026-10-04); the
primary book was not available.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping

import input_validation

SURFACE = "surface"
SUBSURFACE = "subsurface"
INTERNAL = "internal"

# Murakami geometry constant C by defect location (dimensionless).
MURAKAMI_C: Mapping[str, float] = MappingProxyType({
    SURFACE: 1.43,
    SUBSURFACE: 1.41,
    INTERNAL: 1.56,
})
C_SURFACE = MURAKAMI_C[SURFACE]
C_SUBSURFACE = MURAKAMI_C[SUBSURFACE]
C_INTERNAL = MURAKAMI_C[INTERNAL]
HV_OFFSET = 120.0

# Accepted spellings (case-insensitive, stripped) -> canonical location.
_LOCATION_ALIASES = {
    "surface": SURFACE,
    "sub-surface": SUBSURFACE,
    "subsurface": SUBSURFACE,
    "sub_surface": SUBSURFACE,
    "sub surface": SUBSURFACE,
    "internal": INTERNAL,
    "interior": INTERNAL,
}


def classify_location(location: Any) -> str:
    """Canonical location (surface / subsurface / internal) for a user string.

    An unrecognised or non-string value raises ValidationError (OUT_OF_RANGE): the
    constants differ by up to 9 % and the old silent fallback (anything unknown ->
    internal 1.56 in one engine, 1.41 in the other) hid typos.
    """
    if isinstance(location, str):
        canonical = _LOCATION_ALIASES.get(location.strip().lower())
        if canonical is not None:
            return canonical
    raise input_validation.ValidationError(
        input_validation.OUT_OF_RANGE, "location",
        f"must be one of {sorted(_LOCATION_ALIASES)}",
        {"value": repr(location), "allowed": sorted(_LOCATION_ALIASES)})


def murakami_geometric_constant(location: Any) -> float:
    """Murakami C for a defect ``location`` (see classify_location)."""
    return MURAKAMI_C[classify_location(location)]


def murakami_sqrt_area_limit_MPa(sqrt_area_um: float, hardness_HV: float, location: Any = INTERNAL) -> float:
    """sigma_w = C (HV + 120) / sqrt(area)^(1/6) in MPa; sqrt_area in um, HV in kgf/mm^2.

    Both inputs must be finite and > 0 (ValidationError otherwise): a non-positive
    sqrt(area) has no meaning and was previously clamped to a tiny positive value,
    silently producing a large, invented limit.
    """
    area = input_validation.require_positive("sqrtArea_um", sqrt_area_um)
    hv = input_validation.require_positive("hardness_HV", hardness_HV)
    return murakami_geometric_constant(location) * (hv + HV_OFFSET) / (area ** (1.0 / 6.0))
