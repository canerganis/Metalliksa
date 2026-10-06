#!/usr/bin/env python3
"""
Solidification-front G, R, G·R from a conduction temperature field.

Quasi-steady laser frame (+x travel, z ≥ 0 depth). On the liquidus isotherm,
G = |∇T| and local growth R_n = v n_x with n = ∇T/|∇T| into the melt
(Kou / Hunt geometry). Build-surface incline multiplies R by cos θ so
vertical walls do not claim R = v. Not Gäumann–Trivedi–Kurz CET (no N0).

PDAS is Hunt–Lu λ1 ∝ G^{-1/2} R^{-1/4} with an LPBF-scale SI prefactor
(µm cells), not unused welding pdas_A1. SDAS is Kirkwood λ2 ∝ Ṫ^{-1/3}.

Does not re-score Build Job printability.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional

MODEL_ID = "solidification-front-v1"
HUNT_DOI = "10.1016/0025-5416(84)90201-X"
AHMED_RACK_DOI = "10.1016/S0921-5093(97)00802-2"

# Hunt 1984 morphology vs G/R (K s / m²). Screening bands, not alloy K_col.
G_OVER_R_PLANAR = 1.0e10
G_OVER_R_CELLULAR = 5.0e8
G_OVER_R_COLUMNAR = 1.0e7

# Hunt–Lu SI: λ1 = A G^{-1/2} R^{-1/4}. G=1e6 K/m, R=0.5 m/s → ~1 µm.
HUNT_LU_A_SI = 1.19e-3

TI64_MARTENSITE_K_S = 410.0


def _t_scalar(T_fn: Callable, x: float, y: float, z: float) -> float:
    val = T_fn(x, y, z)
    try:
        return float(val)
    except (TypeError, ValueError):
        return float(val.reshape(-1)[0])


def _grad_T(T_fn: Callable, x: float, y: float, z: float, h: float) -> tuple[float, float, float]:
    h = max(8e-8, float(h))
    dTdx = (_t_scalar(T_fn, x + h, y, z) - _t_scalar(T_fn, x - h, y, z)) / (2.0 * h)
    dTdy = (_t_scalar(T_fn, x, y + h, z) - _t_scalar(T_fn, x, y - h, z)) / (2.0 * h)
    dTdz = (_t_scalar(T_fn, x, y, z + h) - _t_scalar(T_fn, x, y, max(0.0, z - h))) / (2.0 * h)
    return dTdx, dTdy, dTdz


def _binary_z_liquidus(T_fn: Callable, x: float, T_liq: float, z_hi: float) -> float:
    if _t_scalar(T_fn, x, 0.0, 0.0) < T_liq:
        return -1.0
    lo, hi = 0.0, max(4e-6, float(z_hi))
    # Bisection needs a sign-changing bracket. If the top of the search
    # domain is still superheated, the liquidus crossing lies beyond the
    # requested domain; do not report its boundary as a physical front.
    if _t_scalar(T_fn, x, 0.0, hi) > T_liq:
        return -1.0
    for _ in range(16):
        mid = 0.5 * (lo + hi)
        if _t_scalar(T_fn, x, 0.0, mid) >= T_liq:
            lo = mid
        else:
            hi = mid
    return lo


def hunt_morphology(g_over_r: float) -> str:
    if g_over_r >= G_OVER_R_PLANAR:
        return "Planar (Hunt G/R screening)"
    if g_over_r >= G_OVER_R_CELLULAR:
        return "Cellular (Hunt G/R screening)"
    if g_over_r >= G_OVER_R_COLUMNAR:
        return "Columnar dendritic (Hunt G/R screening)"
    return "Mixed / equiaxed tendency (Hunt G/R screening)"


def hunt_lu_pdas_um(G_K_m: float, R_m_s: float) -> float:
    G = max(1.0e4, float(G_K_m))
    R = max(1.0e-5, float(R_m_s))
    return HUNT_LU_A_SI * (G ** -0.5) * (R ** -0.25) * 1.0e6


def kirkwood_sdas_um(cooling_K_s: float, B: float) -> float:
    tdot = max(10.0, float(cooling_K_s))
    return abs(float(B)) * (tdot ** -0.33)


def phase_transformation_note(material_name: str, cooling_rate_K_s: float) -> Dict[str, Any]:
    name = (material_name or "").lower()
    Tdot = float(cooling_rate_K_s)
    if "ti-6al-4v" in name or "ti6al4v" in name or name.startswith("ti64"):
        martensite = Tdot >= TI64_MARTENSITE_K_S
        return {
            "alloyClass": "Ti-6Al-4V",
            "expected": "beta_to_alpha_prime_martensite" if martensite else "diffusion_alpha_possible",
            "criterion": (
                f"Ahmed & Rack 1998: β → α' when cooling > {TI64_MARTENSITE_K_S:.0f} K/s "
                f"(here {Tdot:.0f} K/s)"
            ),
            "source": "Ahmed & Rack, Mater. Sci. Eng. A 243 (1998) 206–211",
            "doi": AHMED_RACK_DOI,
        }
    if "316" in name:
        return {
            "alloyClass": "316L",
            "expected": "austenite_cellular_dendritic",
            "criterion": "LPBF cooling typically yields sub-micron cells; spacing from PDAS/SDAS only",
            "source": "screening — no invented cell-size table",
            "doi": HUNT_DOI,
        }
    if "alsi10mg" in name or "al-si" in name:
        return {
            "alloyClass": "AlSi10Mg",
            "expected": "alpha_Al_plus_eutectic_Si",
            "criterion": "rapid solidification eutectic Si network (not quantified here)",
            "source": "screening — no invented Si spacing table",
            "doi": HUNT_DOI,
        }
    if "718" in name or "inconel" in name:
        return {
            "alloyClass": "IN718",
            "expected": "gamma_cellular_possible_laves",
            "criterion": "interdendritic Laves possible; not quantified without Scheil/CALPHAD",
            "source": "screening — no invented Laves fraction",
            "doi": HUNT_DOI,
        }
    return {
        "alloyClass": "unspecified",
        "expected": "not_classified",
        "criterion": "no alloy-specific solid-state rule",
        "source": None,
        "doi": None,
    }


def map_solidification_front(
    T_fn: Callable,
    T_liq: float,
    v_scan: float,
    x_rear: float,
    search_depth: float,
    h_m: float,
    cos_theta: float = 1.0,
    n_samples: int = 9,
) -> Optional[Dict[str, Any]]:
    """Sample the rear liquidus in the x–z plane (y=0) and return G, R, Tdot stats."""
    x_rear = max(4e-6, float(x_rear))
    z_hi = max(8e-6, float(search_depth))
    n_samples = max(5, min(16, int(n_samples)))
    incline = max(0.05, float(cos_theta))
    xs = [-x_rear * (0.92 - 0.70 * i / max(1, n_samples - 1)) for i in range(n_samples)]
    samples: List[Dict[str, float]] = []
    for x in xs:
        z = _binary_z_liquidus(T_fn, x, T_liq, z_hi)
        if z < 0.0:
            continue
        gx, gy, gz = _grad_T(T_fn, x, 0.0, z, h_m)
        g_mag = math.sqrt(gx * gx + gy * gy + gz * gz)
        if g_mag < 1.0:
            continue
        nx = gx / g_mag
        R_loc = max(0.0, float(v_scan) * nx) * incline
        samples.append({
            "x_um": round(x * 1e6, 1),
            "z_um": round(z * 1e6, 1),
            "G_K_m": g_mag,
            "R_m_s": R_loc,
            "coolingRate_K_s": g_mag * R_loc,
            "g_over_r": g_mag / max(1e-6, R_loc),
            "n_x": nx,
        })
    if len(samples) < 3:
        return None

    def _med(key: str) -> float:
        vals = sorted(s[key] for s in samples)
        return vals[len(vals) // 2]

    tail = min(samples, key=lambda s: s["x_um"])
    bottom = max(samples, key=lambda s: s["z_um"])
    return {
        "nPoints": len(samples),
        "G_median_K_m": _med("G_K_m"),
        "G_tail_K_m": tail["G_K_m"],
        "R_median_m_s": _med("R_m_s"),
        "R_tail_m_s": tail["R_m_s"],
        "coolingRate_median_K_s": _med("coolingRate_K_s"),
        "tail": tail,
        "bottom": bottom,
        "samples": samples,
    }


def evaluate_solidification(
    T_fn: Callable,
    *,
    T_liq: float,
    T_sol: float,
    t_surface: float,
    v_scan: float,
    x_rear: float,
    x_front: float,
    search_depth: float,
    r_beam: float,
    cos_theta: float,
    pdas_A1: float,
    sdas_B1: float,
    material_name: str,
) -> Dict[str, Any]:
    del x_front, pdas_A1  # rear-wake map; Hunt–Lu SI replaces welding pdas_A1
    mapped = map_solidification_front(
        T_fn,
        T_liq,
        v_scan,
        x_rear,
        search_depth,
        h_m=max(1.2e-7, 0.025 * max(8e-6, r_beam)),
        cos_theta=cos_theta,
    )
    used_field = mapped is not None
    if mapped is None:
        # Screening G ~ ΔT / tail length, not T_liq / length (absolute T is not a gradient).
        delta_T = max(10.0, float(t_surface) - float(T_sol))
        G = max(100.0, delta_T / max(1e-6, float(x_rear)))
        R = max(1e-4, v_scan * max(0.05, cos_theta))
        Tdot = G * R
        source = "tail-length-fallback"
    else:
        G = mapped["G_median_K_m"]
        R = max(1e-4, mapped["R_median_m_s"])
        Tdot = max(1.0, mapped["coolingRate_median_K_s"])
        source = MODEL_ID

    g_over_r = max(1.0, G / max(1e-6, R))
    out: Dict[str, Any] = {
        "modelId": MODEL_ID,
        "gradientSource": source,
        "usedFieldMap": used_field,
        "thermalGradient_G_K_m": G,
        "solidificationRate_R_m_s": R,
        "coolingRate_K_s": Tdot,
        "g_over_r_ratio": g_over_r,
        "microstructureMorphology": hunt_morphology(g_over_r),
        "primaryDendriteArmSpacing_PDAS_um": hunt_lu_pdas_um(G, R),
        "secondaryDendriteArmSpacing_SDAS_um": kirkwood_sdas_um(Tdot, sdas_B1),
        "phaseTransformation": phase_transformation_note(material_name, Tdot),
        "doi": HUNT_DOI,
        "disclaimer": (
            "G,R from the conduction-field liquidus. Hunt G/R bands are not calibrated N0 CET. "
            "Does not re-score Build Job."
        ),
    }
    if mapped is not None:
        out["G_tail_K_m"] = mapped["G_tail_K_m"]
        out["R_tail_m_s"] = mapped["R_tail_m_s"]
        out["frontPointCount"] = mapped["nPoints"]
        out["tail"] = {
            "x_um": mapped["tail"]["x_um"],
            "z_um": mapped["tail"]["z_um"],
            "G_K_m": round(mapped["tail"]["G_K_m"], 0),
            "R_m_s": round(mapped["tail"]["R_m_s"], 4),
        }
        out["bottom"] = {
            "x_um": mapped["bottom"]["x_um"],
            "z_um": mapped["bottom"]["z_um"],
            "G_K_m": round(mapped["bottom"]["G_K_m"], 0),
            "R_m_s": round(mapped["bottom"]["R_m_s"], 4),
        }
    return out
