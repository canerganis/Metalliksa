"""Documented output changes of the physics-audit lane tafel-uq (EUQ-3/4/5/6/11/13).

Golden expectations (python/golden/phase6a/<solver>/step_b/*.json) may record these changes only
because each one is checked exactly here, never by a tolerance:

- tafel_corrosion_rate_solver (EUQ-6, EUQ-3): the 'standards' list loses "NACE SP0169" and "ISO 8044",
  the severity block gains the pinned scaleSource / textBasis texts, the fit result gains currentInput.
  EUQ-5 (supplied 0 kept) and EUQ-13 (0.15 V intersection limit) do not change any golden case.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------------------------------------
# Tafel (EUQ-3, EUQ-6)
# ---------------------------------------------------------------------------------------------------------
TAFEL_STANDARDS = ["ASTM G102-89(2015)", "ASTM G59-97(2020)"]
TAFEL_REMOVED_STANDARDS = {"standards[2]": "NACE SP0169", "standards[3]": "ISO 8044"}
TAFEL_SEVERITY_SCALE_SOURCE = (
    "Fontana, Corrosion Engineering, 3rd ed., relative corrosion resistance scale (mm/y equivalents): "
    "Outstanding < 0.02, Excellent 0.02-0.1, Good 0.1-0.5, Fair 0.5-1, Poor 1-5, Unacceptable > 5 mm/y"
)
TAFEL_SEVERITY_TEXT_BASIS = (
    "In-house engineering guidance: the description and recommendation texts are not taken from Fontana or "
    "from any standard"
)
TAFEL_DENSITY_INPUT = {"keys": ["currentDensity_uA_cm2"], "currentUnit": None, "currentIsDensity": None,
                       "densityUnit": "uA/cm2"}
_TAFEL_ROW = re.compile(r"standards\[\d+\]|severity\.(scaleSource|textBasis)|currentInput(\..+)?")


def is_tafel_audit_row(key: str) -> bool:
    return bool(_TAFEL_ROW.fullmatch(key))


def tafel_row_problem(row: Dict[str, Any], new_stdout: Optional[Dict[str, Any]]) -> Optional[str]:
    """None when ``row`` is exactly one of the documented tafel changes."""
    key, kind = row["key"], row["kind"]
    if new_stdout is None:
        return f"{key}: documented tafel change needs the re-blessed document"
    if key in TAFEL_REMOVED_STANDARDS:
        if kind != "removed" or row["old"] != TAFEL_REMOVED_STANDARDS[key] or new_stdout.get("standards") != TAFEL_STANDARDS:
            return f"{key}: expected the removal of {TAFEL_REMOVED_STANDARDS[key]!r} leaving {TAFEL_STANDARDS!r}"
        return None
    if key == "severity.scaleSource" or key == "severity.textBasis":
        expected = TAFEL_SEVERITY_SCALE_SOURCE if key.endswith("scaleSource") else TAFEL_SEVERITY_TEXT_BASIS
        if kind != "added" or row["new"] != expected or (new_stdout.get("severity") or {}).get(key.split(".")[1]) != expected:
            return f"{key}: expected the pinned text as an added row"
        return None
    if key.startswith("currentInput"):
        if kind != "added" or new_stdout.get("currentInput") != TAFEL_DENSITY_INPUT:
            return f"{key}: expected currentInput {TAFEL_DENSITY_INPUT!r} (density-keyed points) as added rows"
        return None
    return f"{key}: no documented tafel change for this row"
