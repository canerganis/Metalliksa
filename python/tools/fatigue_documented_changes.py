"""
Documented value changes of lpbf_fatigue_fracture against the d33b6f5 base goldens (physics audit KS-2, KS-3).

Used by capture_phase6a_golden.documented_change_violation (via
phase6a_t2b_golden_cases.EXPECTED_DOCUMENTED_VALUE_CHANGES) and by test_phase6a_t2b_migration.

Changes (base golden -> now):

KS-2  El-Haddad intrinsic length with Murakami's geometry factor:
      a0 = (1/pi) (Delta_K_th / (Y sigma_e0))^2, Y = 0.65 surface / sub-surface, 0.5 internal
      (was Y = 1), and sigma_w = sigma_e0 sqrt(a0 / (sqrt(area) + a0)) without the ad hoc factor
      C_loc / 1.56. New key fatigue_limit.el_haddad_geometry_factor_Y.
KS-3  Paris growth of the defect itself: x = sqrt(area) from x0 = sqrt(area) (was sqrt(area)/2),
      Delta_K = Y_loc Delta_sigma_eff sqrt(pi x) with Y_loc by location (was 0.65 for all),
      Delta_sigma_eff = sigma_max for R <= 0 (ASTM E647; was 2 sigma_a for every R), the closed-form
      Paris life (was forward Euler with 5 % steps), critical size from K_IC = Y_loc sigma_max sqrt(pi x).
      New keys in paris_crack_growth (geometry factor, effective range, initial Delta_K, convention, critical
      size, integration method) and a 50-point curve that starts at the initial defect.

The check is an independent recomputation, not a tolerance on the drift:

* the constants are the d33b6f5 table snapshot (golden/phase6a/lpbf_fatigue_fracture/_source_tables.json),
  never the working-tree registry or solver;
* the Paris life is integrated numerically here (composite Simpson in ln x, 4000 intervals), separate code
  from the solver's closed form;
* every re-blessed leaf in the documented sections must agree with this oracle within its display rounding;
* the OLD value of el_haddad_a0_um must be the old Y = 1 formula of the same constants.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PYTHON_DIR = Path(__file__).resolve().parent.parent
TABLES = PYTHON_DIR / "golden" / "phase6a" / "lpbf_fatigue_fracture" / "_source_tables.json"

DESCRIPTIONS: Dict[str, str] = {
    r"fatigue_limit\.(el_haddad_a0_um|fatigue_limit_R_minus_1_MPa|fatigue_limit_corrected_MPa)":
        "KS-2: El-Haddad a0 = (1/pi)(dKth/(Y sigma_e0))^2 with Murakami Y (0.65 surface/sub-surface, 0.5 "
        "internal), no C_loc/1.56 factor; the reconciled limit min(sigma_e0, El-Haddad, Murakami) follows",
    r"fatigue_limit\.el_haddad_geometry_factor_Y": "KS-2: new key, the Y used in a0",
    r"kitagawa_takahashi_curve\[\d+\]\.fatigue_limit_MPa": "KS-2: Kitagawa-Takahashi points with the corrected a0",
    r"paris_crack_growth\..+":
        "KS-3: Paris growth in x = sqrt(area) from x0 = sqrt(area), Y by location, dK = Kmax for R <= 0 "
        "(ASTM E647), closed-form life, new descriptive keys and a 50-point curve",
}

Y_BY_LOCATION = {"surface": 0.65, "sub-surface": 0.65, "subsurface": 0.65, "sub_surface": 0.65,
                 "sub surface": 0.65, "internal": 0.5, "interior": 0.5}
C_BY_LOCATION = {"surface": 1.43, "sub-surface": 1.41, "subsurface": 1.41, "sub_surface": 1.41,
                 "sub surface": 1.41, "internal": 1.56, "interior": 1.56}
CYCLES_MAX = 10_000_000
CURVE_POINTS = 50
DK_CONVENTION = "ASTM E647: Delta_K = K_max for R <= 0, K_max - K_min for R > 0"
INTEGRATION = "closed-form Paris integral in x = sqrt(area) (constant Murakami Y)"

_PATH_RE = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


def _table() -> Dict[str, Dict[str, Any]]:
    return json.loads(TABLES.read_text(encoding="utf-8"))["values"]


def _leaf(doc: Any, key: str) -> Tuple[bool, Any]:
    cur = doc
    for name, idx in _PATH_RE.findall(key):
        try:
            cur = cur[int(idx)] if idx else cur[name]
        except (KeyError, IndexError, TypeError):
            return False, None
    return True, cur


def _payload(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], float, str, float, float]:
    alloy = _table()[payload.get("alloyName", "Ti-6Al-4V")]
    return (alloy, float(payload.get("sqrtArea_um", 45.0)), payload.get("location", "internal"),
            float(payload.get("stressRatio_R", -1.0)), float(payload.get("stressAmplitude_MPa", 220.0)))


def old_a0_um(alloy: Dict[str, Any]) -> float:
    """The d33b6f5 a0 (Y = 1), rounded like the output."""
    return round((alloy["threshold_stress_intensity_MPa_m"] / alloy["smooth_fatigue_limit_MPa"]) ** 2
                 / math.pi * 1e6, 2)


def limit_R_minus_1(alloy: Dict[str, Any], d_um: float, loc: str) -> Tuple[float, float]:
    """(a0 [um], fatigue limit at R = -1 [MPa]) from the Y-consistent El-Haddad and Murakami branches."""
    key = loc.strip().lower()
    y = Y_BY_LOCATION[key]
    s0 = alloy["smooth_fatigue_limit_MPa"]
    a0 = 1e6 / math.pi * (alloy["threshold_stress_intensity_MPa_m"] / (y * s0)) ** 2
    eh = s0 / math.sqrt(1.0 + d_um / a0)
    mur = C_BY_LOCATION[key] * (alloy["hardness_HV"] + 120.0) * d_um ** (-1.0 / 6.0)
    return a0, min(s0, eh, mur)


def r_factor(alloy: Dict[str, Any], r: float) -> float:
    if r == -1.0:
        return 1.0
    return ((1.0 - min(r, 0.99)) / 2.0) ** (0.226 + 0.0001 * alloy["hardness_HV"])


def paris_cycles(alloy: Dict[str, Any], y: float, dse: float, x0: float, x: float, n: int = 4000) -> float:
    """N = integral_x0^x dx / (C (y dse sqrt(pi x))^m), composite Simpson in u = ln x."""
    if x <= x0:
        return 0.0
    c, m = alloy["paris_C"], alloy["paris_m"]
    u0, u1 = math.log(x0), math.log(x)
    h = (u1 - u0) / n

    def f(u: float) -> float:
        xx = math.exp(u)
        return xx / (c * (y * dse * math.sqrt(math.pi * xx)) ** m)

    total = f(u0) + f(u1) + sum((4 if i % 2 else 2) * f(u0 + i * h) for i in range(1, n))
    return total * h / 3.0


def _close(a: Any, b: float, tol: float) -> bool:
    return isinstance(a, (int, float)) and not isinstance(a, bool) and abs(a - b) <= tol


def document_problems(stdout: Dict[str, Any], payload: Dict[str, Any]) -> List[str]:
    """Every disagreement of a re-blessed driver stdout with the independent expectation."""
    out: List[str] = []
    try:
        alloy, d_um, loc, r, amp = _payload(payload)
        fl, kt, pc = stdout["fatigue_limit"], stdout["kitagawa_takahashi_curve"], stdout["paris_crack_growth"]
    except (KeyError, TypeError) as exc:
        return [f"fatigue: re-blessed document or payload incomplete ({exc!r})"]
    key = loc.strip().lower()
    y = Y_BY_LOCATION[key]

    # --- KS-2: fatigue limit and Kitagawa-Takahashi curve
    a0, lim = limit_R_minus_1(alloy, d_um, loc)
    if fl.get("el_haddad_geometry_factor_Y") != y:
        out.append(f"fatigue_limit.el_haddad_geometry_factor_Y {fl.get('el_haddad_geometry_factor_Y')!r} != {y}")
    if not _close(fl.get("el_haddad_a0_um"), a0, 0.0051):
        out.append(f"fatigue_limit.el_haddad_a0_um {fl.get('el_haddad_a0_um')!r} != {a0:.4f}")
    if not _close(fl.get("fatigue_limit_R_minus_1_MPa"), lim, 0.051):
        out.append(f"fatigue_limit.fatigue_limit_R_minus_1_MPa {fl.get('fatigue_limit_R_minus_1_MPa')!r} != {lim:.3f}")
    if not _close(fl.get("fatigue_limit_corrected_MPa"), lim * r_factor(alloy, r), 0.051):
        out.append(f"fatigue_limit.fatigue_limit_corrected_MPa {fl.get('fatigue_limit_corrected_MPa')!r} "
                   f"!= {lim * r_factor(alloy, r):.3f}")
    if len(kt) != 30:
        out.append(f"kitagawa_takahashi_curve has {len(kt)} points, expected 30")
    else:
        for i, point in enumerate(kt):
            d = 10.0 ** (-1.0 + 4.0 * i / 29)
            expect = limit_R_minus_1(alloy, d, loc)[1] * r_factor(alloy, r)
            if not _close(point.get("fatigue_limit_MPa"), expect, 0.051):
                out.append(f"kitagawa_takahashi_curve[{i}].fatigue_limit_MPa {point.get('fatigue_limit_MPa')!r} "
                           f"!= {expect:.3f}")

    # --- KS-3: Paris growth
    x0 = d_um * 1e-6
    sigma_max = 2.0 * amp / (1.0 - r)
    dse = sigma_max if r <= 0.0 else 2.0 * amp
    x_f = (alloy["fracture_toughness_K_IC"] / (y * sigma_max)) ** 2 / math.pi
    dk0 = y * dse * math.sqrt(math.pi * x0)
    exact = {"location": loc, "geometry_factor_Y": y, "delta_K_convention": DK_CONVENTION,
             "integration": INTEGRATION, "initial_crack_size_um": d_um}
    for k, v in exact.items():
        if pc.get(k) != v:
            out.append(f"paris_crack_growth.{k} {pc.get(k)!r} != {v!r}")
    for k, v, tol in (("delta_sigma_eff_MPa", dse, 0.0051), ("delta_K_initial_MPa_m", dk0, 0.00051),
                      ("critical_sqrt_area_um", x_f * 1e6, 0.0051)):
        if not _close(pc.get(k), v, tol):
            out.append(f"paris_crack_growth.{k} {pc.get(k)!r} != {v!r}")
    curve = pc.get("crack_growth_curve") or []
    if dk0 < alloy["threshold_stress_intensity_MPa_m"]:
        want = ("non_propagating", CYCLES_MAX, round(d_um, 2))
    elif x0 >= x_f:
        want = ("fractured", 0, round(d_um, 2))
    else:
        n_f = paris_cycles(alloy, y, dse, x0, x_f)
        if n_f > CYCLES_MAX:
            lo, hi = x0, x_f  # bisection for the size reached at CYCLES_MAX
            for _ in range(200):
                mid = math.sqrt(lo * hi)
                lo, hi = (mid, hi) if paris_cycles(alloy, y, dse, x0, mid) < CYCLES_MAX else (lo, mid)
            want = ("runout", CYCLES_MAX, round(lo * 1e6, 2))
        else:
            want = ("fractured", n_f, round(x_f * 1e6, 2))
    got = (pc.get("status"), pc.get("cycles_to_failure"), pc.get("final_crack_size_um"))
    if got[0] != want[0] or not _close(got[1], want[1], max(1.0, 1e-6 * want[1])) \
            or not _close(got[2], want[2], 0.0101):
        out.append(f"paris_crack_growth status/cycles/final size {got!r} != {want!r}")
    if not curve or curve[0] != {"cycles": 0, "crack_length_um": d_um, "delta_K_MPa_m": round(dk0, 2)}:
        out.append(f"paris_crack_growth.crack_growth_curve[0] {curve[:1]!r} is not the initial defect")
    if pc.get("status") in ("non_propagating",) or want[1] == 0:
        if len(curve) != 1:
            out.append("paris_crack_growth.crack_growth_curve: no growth, expected only the initial point")
        return out
    if len(curve) != CURVE_POINTS:
        out.append(f"paris_crack_growth.crack_growth_curve has {len(curve)} points, expected {CURVE_POINTS}")
    prev = -1
    for i, p in enumerate(curve):
        x = p.get("crack_length_um", 0.0) * 1e-6
        if p.get("cycles", -1) < prev:
            out.append(f"paris_crack_growth.crack_growth_curve[{i}]: cycles decrease")
        prev = p.get("cycles", -1)
        if not _close(p.get("delta_K_MPa_m"), y * dse * math.sqrt(math.pi * x), 0.0051 + 1e-3):
            out.append(f"paris_crack_growth.crack_growth_curve[{i}].delta_K_MPa_m {p.get('delta_K_MPa_m')!r}")
        if 0 < i < len(curve) - 1:
            rate = alloy["paris_C"] * (y * dse * math.sqrt(math.pi * x)) ** alloy["paris_m"]
            tol = 1.0 + 0.0051e-6 / rate + 1e-6 * p["cycles"]
            if not _close(p.get("cycles"), paris_cycles(alloy, y, dse, x0, x), tol):
                out.append(f"paris_crack_growth.crack_growth_curve[{i}].cycles {p.get('cycles')!r}")
    if curve[-1].get("cycles") != pc.get("cycles_to_failure") or \
            curve[-1].get("crack_length_um") != pc.get("final_crack_size_um"):
        out.append("paris_crack_growth.crack_growth_curve[-1] is not the end state")
    return out


def is_documented_row(key: str) -> bool:
    return any(re.fullmatch(p, key) for p in DESCRIPTIONS)


def row_violation(row: Dict[str, Any], new_stdout: Optional[Dict[str, Any]],
                  payload: Optional[Dict[str, Any]], old_stdout: Optional[Dict[str, Any]] = None,
                  _cache: Dict[Tuple[int, int], List[str]] = {}) -> Optional[str]:  # noqa: B006
    """None when ``row`` is a documented KS-2/KS-3 change and the whole document passes the oracle."""
    key = row["key"]
    if not is_documented_row(key):
        return f"{key}: not a documented fatigue change"
    if new_stdout is None or payload is None:
        return f"{key}: documented change needs the re-blessed document and the case payload"
    present, value = _leaf(new_stdout, key)
    if row["kind"] == "removed":
        if present:
            return f"{key}: removed row but the key is present in the re-blessed document"
    elif not present or value != row["new"] or type(value) is not type(row["new"]):
        return f"{key}: row new value {row['new']!r} is not the re-blessed document's {value!r}"
    if key == "fatigue_limit.el_haddad_a0_um":
        alloy = _payload(payload)[0]
        if row["old"] != old_a0_um(alloy):
            return f"{key}: old {row['old']!r} is not the Y = 1 formula {old_a0_um(alloy)!r}"
    cache_key = (id(new_stdout), id(payload))
    if cache_key not in _cache:
        _cache.clear()
        _cache[cache_key] = document_problems(new_stdout, payload)
    problems = _cache[cache_key]
    return f"{key}: re-blessed document fails the KS-2/KS-3 oracle: {problems[:3]}" if problems else None
