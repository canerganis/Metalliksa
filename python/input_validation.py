#!/usr/bin/env python3
"""
Typed input validation for the free (non-LPBF-core) solvers.

Every check raises ValidationError(code, field, message, detail). Solvers migrated
in Phase 6a catch it in ``__main__`` and print ``validation_envelope(err)`` with
exit code 2 (see .orchestra/DESIGN-6a-materials.md section 2).

Leaf module: standard library + physical_constants + alloy_registry only. It must
NOT be imported by any manifest file until the planned fingerprint bump.
"""

from __future__ import annotations

import math
import numbers
from typing import Any, Dict, Iterable, Mapping, Optional

import alloy_registry
import physical_constants

NON_FINITE = "NON_FINITE"
NON_POSITIVE = "NON_POSITIVE"
OUT_OF_RANGE = "OUT_OF_RANGE"
UNKNOWN_ALLOY = "UNKNOWN_ALLOY"
UNKNOWN_ELEMENT = "UNKNOWN_ELEMENT"
MISSING_PROPERTY = "MISSING_PROPERTY"
BAD_UNIT = "BAD_UNIT"
ERROR_CODES = frozenset({NON_FINITE, NON_POSITIVE, OUT_OF_RANGE, UNKNOWN_ALLOY,
                         UNKNOWN_ELEMENT, MISSING_PROPERTY, BAD_UNIT})

# Composition total tolerance in wt%: the design allows rounding up to 100.5 wt%.
COMPOSITION_MAX_TOTAL_WT = 100.5


class ValidationError(ValueError):
    def __init__(self, code: str, field: str, message: str,
                 detail: Optional[Mapping[str, Any]] = None):
        if code not in ERROR_CODES:
            raise ValueError(f"Unknown validation error code {code!r}")
        self.code = code
        self.field = field
        self.message = message
        self.detail = dict(detail or {})
        super().__init__(f"[{code}] {field}: {message}")

    def to_json(self) -> Dict[str, Any]:
        return {"code": self.code, "field": self.field, "message": self.message,
                "detail": self.detail}


def validation_envelope(err: ValidationError) -> Dict[str, Any]:
    """stdout envelope for a validation failure (process exit code 2)."""
    return {"success": False, "error": err.to_json(), "errorKind": "validation"}


def _number(name: str, x: Any) -> float:
    # bool is an int subclass; a True/False physics input is a caller bug.
    if isinstance(x, bool) or not isinstance(x, numbers.Real):
        raise ValidationError(NON_FINITE, name, "must be a real number",
                              {"value": repr(x), "type": type(x).__name__})
    value = float(x)
    if not math.isfinite(value):
        raise ValidationError(NON_FINITE, name, "must be finite", {"value": repr(x)})
    return value


def require_finite(name: str, x: Any) -> float:
    return _number(name, x)


def require_positive(name: str, x: Any, allow_zero: bool = False) -> float:
    value = _number(name, x)
    if value < 0 or (value == 0 and not allow_zero):
        rule = ">= 0" if allow_zero else "> 0"
        raise ValidationError(NON_POSITIVE, name, f"must be {rule}",
                              {"value": value, "allowZero": allow_zero})
    return value


def require_range(name: str, x: Any, lo: Optional[float], hi: Optional[float], unit: str) -> float:
    value = _number(name, x)
    if (lo is not None and value < lo) or (hi is not None and value > hi):
        raise ValidationError(OUT_OF_RANGE, name, f"must be within [{lo}, {hi}] {unit}",
                              {"value": value, "lo": lo, "hi": hi, "unit": unit})
    return value


def require_unit(name: str, unit: Any, allowed: Iterable[str]) -> str:
    allowed_list = list(allowed)
    if not isinstance(unit, str) or unit not in allowed_list:
        raise ValidationError(BAD_UNIT, name, f"unit must be one of {allowed_list}",
                              {"unit": repr(unit), "allowed": allowed_list})
    return unit


def require_known_alloy(name: Any, domain: Optional[str] = None,
                        field: str = "alloy") -> alloy_registry.AlloyRecord:
    try:
        return alloy_registry.resolve_alloy(name, domain)
    except alloy_registry.AmbiguousAlloyError as exc:
        raise ValidationError(UNKNOWN_ALLOY, field, str(exc),
                              {"name": repr(name), "domain": domain, "reason": "ambiguous",
                               "candidates": list(exc.candidates)}) from exc
    except alloy_registry.UnknownAlloyError as exc:
        raise ValidationError(UNKNOWN_ALLOY, field, str(exc),
                              {"name": repr(name), "domain": domain, "reason": exc.reason,
                               "suggestions": list(exc.suggestions)}) from exc


def require_property(record: alloy_registry.AlloyRecord, key: str, domain: str,
                     field: str = "alloy") -> alloy_registry.ValueRecord:
    try:
        return record.get(key, domain)
    except alloy_registry.MissingPropertyError as exc:
        raise ValidationError(MISSING_PROPERTY, field, str(exc),
                              {"alloy": record.id, "key": key, "domain": domain}) from exc


def require_element(name: str, element: Any) -> str:
    if not physical_constants.is_known_element(element):
        raise ValidationError(UNKNOWN_ELEMENT, name, f"unknown element {element!r}",
                              {"element": repr(element)})
    return physical_constants.atomic_weight_record(element).symbol


def require_composition(comp: Any, field: str = "composition") -> Dict[str, float]:
    """Validate a wt% composition: known elements, finite, >= 0, total <= 100.5 wt%.

    Returns a new dict keyed by canonical element symbols. Nothing is dropped,
    renormalised or filled in.
    """
    if not isinstance(comp, Mapping) or not comp:
        raise ValidationError(OUT_OF_RANGE, field, "must be a non-empty element -> wt% mapping",
                              {"type": type(comp).__name__})
    out: Dict[str, float] = {}
    for element, wt in comp.items():
        symbol = require_element(f"{field}.{element}", element)
        if symbol in out:
            raise ValidationError(OUT_OF_RANGE, f"{field}.{element}", "duplicate element",
                                  {"element": symbol})
        out[symbol] = require_positive(f"{field}.{element}", wt, allow_zero=True)
    total = sum(out.values())
    if total <= 0:
        raise ValidationError(NON_POSITIVE, field, "total must be > 0 wt%",
                              {"total": total, "unit": "wt%"})
    if total >COMPOSITION_MAX_TOTAL_WT:
        raise ValidationError(OUT_OF_RANGE, field,
                              f"total must be <= {COMPOSITION_MAX_TOTAL_WT} wt%",
                              {"total": total, "max": COMPOSITION_MAX_TOTAL_WT, "unit": "wt%"})
    return out
