"""
Approximate Rockwell C -> Vickers conversion for NON-AUSTENITIC STEELS (ASTM E140 Table 1).

The result is a table estimate, never a measurement. It is linear interpolation between the
published Table 1 rows HRC 20..68 (integer HRC steps). Outside HRC 20..68 the value is
unavailable (None): no extrapolation and no clamping.

The 49 (HRC, HV) rows are the same values as E140_TABLE1 in src/utils/hardnessConversion.ts
(the shared TypeScript util). There they were cross-checked between three public
reproductions of the table, and every row is checked again against an independently
transcribed fixture, tests/fixtures/hardness-tables-sources.ts:
  [A] Laboratory Testing Inc.  https://labtesting.com/wp-content/uploads/2012/08/chart-hardness-c.pdf
  [B] Anderson Laboratories    https://andersonlabs.com/wp-content/uploads/2021/12/ASTM-Hardness-Conversion-Table-Rockwell-C-Range.pdf
  [C] Struers poster (UPC)     https://epsevg.upc.edu/ca/stl/posters/cem/hardness-conversion-poster.pdf
python/test_hardness_conversion_e140.py asserts that this table equals both TypeScript tables
row for row, so the Python and TypeScript copies cannot drift apart.

Scope: the tables apply to non-austenitic steels only. Austenitic stainless steels,
titanium, nickel and aluminium alloys get no conversion (status
STATUS_UNAVAILABLE_ALLOY_CLASS).
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

TABLE_ID = "ASTM E140 Table 1 (Rockwell C range, non-austenitic steels)"
METHOD = "linear interpolation between tabulated HRC rows; HV rounded half up to an integer"
HRC_MIN = 20.0
HRC_MAX = 68.0

# (HRC, HV): ASTM E140 Table 1 via [A][B][C]; identical to src/utils/hardnessConversion.ts E140_TABLE1.
E140_TABLE1_HRC_HV: Tuple[Tuple[int, int], ...] = (
    (20, 238), (21, 243), (22, 248), (23, 254), (24, 260), (25, 266), (26, 272), (27, 279),
    (28, 286), (29, 294), (30, 302), (31, 310), (32, 318), (33, 327), (34, 336), (35, 345),
    (36, 354), (37, 363), (38, 372), (39, 382), (40, 392), (41, 402), (42, 412), (43, 423),
    (44, 434), (45, 446), (46, 458), (47, 471), (48, 484), (49, 498), (50, 513), (51, 528),
    (52, 544), (53, 560), (54, 577), (55, 595), (56, 613), (57, 633), (58, 653), (59, 674),
    (60, 697), (61, 720), (62, 746), (63, 772), (64, 800), (65, 832), (66, 865), (67, 900),
    (68, 940),
)

STATUS_CONVERTED = "converted-astm-e140-table1"
STATUS_UNAVAILABLE_RANGE = "unavailable-outside-e140-table1-hrc-20-68"
STATUS_UNAVAILABLE_ALLOY_CLASS = "unavailable-no-verified-table-for-alloy-class"
STATUSES = (STATUS_CONVERTED, STATUS_UNAVAILABLE_RANGE, STATUS_UNAVAILABLE_ALLOY_CLASS)


def interpolate_hv_from_hrc(hrc: float) -> Optional[float]:
    """Unrounded HV for ``hrc`` by linear interpolation in Table 1; None outside HRC 20..68."""
    if not isinstance(hrc, (int, float)) or isinstance(hrc, bool) or not math.isfinite(hrc):
        return None
    if hrc < HRC_MIN or hrc > HRC_MAX:
        return None
    rows = E140_TABLE1_HRC_HV
    for (h0, v0), (h1, v1) in zip(rows, rows[1:]):
        if hrc <= h1:
            return v0 + (v1 - v0) * (hrc - h0) / (h1 - h0)
    return float(rows[-1][1])


def hrc_to_hv_non_austenitic_steel(hrc: float) -> Tuple[Optional[float], str]:
    """(HV, status) for a non-austenitic steel. HV is a float integer (e.g. 653.0) or None.

    Rounding is half up, like Math.round in the TypeScript util for these positive values.
    """
    hv = interpolate_hv_from_hrc(hrc)
    if hv is None:
        return None, STATUS_UNAVAILABLE_RANGE
    return float(math.floor(hv + 0.5)), STATUS_CONVERTED


def provenance() -> dict:
    return {
        "table": TABLE_ID,
        "method": METHOD,
        "validRange_HRC": [HRC_MIN, HRC_MAX],
        "scope": "non-austenitic steels only; other alloy classes are unavailable",
        "note": "Approximate table conversion, not a measurement and not a substitute for direct testing.",
    }
