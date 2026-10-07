#!/usr/bin/env python3
"""Fabbro 2020 generalized piston model (GPM) for the inclined keyhole front -- research module, not served.

R. Fabbro, "Depth Dependence and Keyhole Stability at Threshold, for Different Laser Welding Regimes",
Appl. Sci. 2020, 10, 1487, doi 10.3390/app10041487. Appendix A, Eqs. A1-A12, with Eqs. 8 (R = e/d = 1/tan alpha)
and 9 (Vd = Vw cos alpha). Half-cone keyhole front, first impact of the vertical beam only, uniform spot of
diameter d (Sec. 3.4: for a Gaussian beam use the half-maximum diameter, 0.5887 x the 1/e2 diameter).

Energy balance A_F(alpha) P = Pm + Pvap + Pcond + Pkin with Fresnel absorptivity A_F from steel optical constants
n = 3.6, k = 5.0 at 1.06 um (Fabbro, after Dausinger & Shen 1993); mass balance (A2) with the modified Langmuir
vapour flux (A12); recoil pressure 0.5 (1 + beta) Pcc with beta = 0.2 (A10); Clausius-Clapeyron (A11);
conduction loss from the half-cone with m0 = n0 = 2.3 (A7-A8).

Everything is explicit for a given surface temperature Ts: Eq. A2 with A1 and Eq. 9 gives cos(alpha) in closed form,
    cos(alpha) = [rho_m Vm kappa_m Y / Vw + rho_m Vv (1.5 pi / 4) d - rho_s kappa_m Y] / (0.5 rho_s Vw d),
and the incident power follows as P = Pabs / A_F. The aspect ratio for a given incident power is found by root
finding on R (P(R) is monotonic) with an inner root find on Ts (cos(alpha)(Ts) is monotonic).

Scope stated by Fabbro: 0.5 <~ R <~ 3. Pre-declared evaluation: docs/research/PREDECLARED_fabbro_piston.md.
"""

from __future__ import annotations

import cmath
import json
import math
import statistics as st
import sys
from dataclasses import dataclass, asdict, replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from scipy.optimize import brentq

HERE = Path(__file__).resolve().parent
PY = HERE.parent
if str(PY) not in sys.path:
    sys.path.insert(0, str(PY))

MODEL_ID = "fabbro-gpm-2020-research"
DOI = "10.3390/app10041487"
R_GAS = 8.314
FWHM_OVER_1E2 = math.sqrt(math.log(2.0) / 2.0)  # 0.5887: half-maximum diameter / 1/e2 diameter of a Gaussian
STEEL_N, STEEL_K = 3.6, 5.0                      # Fabbro Appendix A (A4): steel at 1.06 um
SCOPE_R_MIN, SCOPE_R_MAX = 0.5, 3.0


@dataclass(frozen=True)
class PistonProps:
    """Mean thermophysical set of the GPM (SI, temperatures in K)."""
    rho_s: float
    rho_m: float
    cp_s: float
    cp_m: float
    kappa_s: float
    kappa_m: float
    Tm: float
    Tv0: float
    Lm: float
    Lv: float
    Mw: float
    c: float
    T0: float = 300.0
    n: float = STEEL_N
    k: float = STEEL_K
    beta: float = 0.2
    m0: float = 2.3
    n0: float = 2.3
    P0: float = 1e5
    Pamb: float = 1e5
    label: str = ""

    @property
    def K_s(self) -> float:
        return self.rho_s * self.cp_s * self.kappa_s


# Fabbro Appendix A, last paragraph. Cp is not printed: 840 J/kgK is inferred from his fitted a1, b1 with
# (m1, n1) = (2.1, 2.2), T0 = 300 K (both give K = 30 W/mK); Mw from c = Lv Mw / (R Tv0).
FABBRO_TI64 = PistonProps(rho_s=4200.0, rho_m=4200.0, cp_s=840.0, cp_m=840.0, kappa_s=8.5e-6, kappa_m=8.5e-6,
                          Tm=1950.0, Tv0=3500.0, Lm=2.85e5, Lv=9.8e6, Mw=15.8 * R_GAS * 3500.0 / 9.8e6, c=15.8,
                          T0=300.0, label="fabbro-2020-ti64 (Cp 840 inferred)")

PROPERTY_VARIANTS = ("P-EFF", "P-SL", "P-FAB")


def props_from_app(material: str, variant: str = "P-EFF", preheat_C: float = 20.0) -> PistonProps:
    """Per-alloy set from the app's material authority (four_alloy_materials via screening_props).

    P-EFF: solid conduction values replaced by the app's effective screening convention (k_s + k_l)/2, (Cp_s + Cp_l)/2.
    P-SL: solid room-temperature values as stored. P-FAB: Fabbro's own Ti-6Al-4V set (Ti-6Al-4V only)."""
    if variant == "P-FAB":
        if "ti" not in material.lower():
            raise ValueError("P-FAB is Fabbro's Ti-6Al-4V set; not defined for " + material)
        return replace(FABBRO_TI64, T0=preheat_C + 273.15)
    from lpbf_public_datasets import screening_props
    p = screening_props(material)
    k_s, k_l = p["thermal_conductivity_W_mK"], p["thermal_conductivity_liquid_W_mK"]
    cp_s, cp_l = p["specific_heat_J_kgK"], p["specific_heat_liquid_J_kgK"]
    rho_s, rho_l = p["density_kg_m3"], p["density_liquid_kg_m3"]
    if variant == "P-EFF":
        k_s, cp_s = 0.5 * (k_s + k_l), 0.5 * (cp_s + cp_l)
    elif variant != "P-SL":
        raise ValueError(variant)
    Tv0 = p["boiling_C"] + 273.15
    Lv, Mw = p["latent_heat_vap_J_kg"], p["M_molar_kg_mol"]
    return PistonProps(rho_s=rho_s, rho_m=rho_l, cp_s=cp_s, cp_m=cp_l, kappa_s=k_s / (rho_s * cp_s),
                       kappa_m=k_l / (rho_l * cp_l), Tm=p["liquidus_C"] + 273.15, Tv0=Tv0, Lm=p["latent_heat_fusion_J_kg"],
                       Lv=Lv, Mw=Mw, c=Lv * Mw / (R_GAS * Tv0), T0=preheat_C + 273.15,
                       label=f"app:{material}:{variant}")


# ---------------------------------------------------------------- elementary relations (Appendix A)
def fresnel_absorptivity(incidence_rad: float, n: float = STEEL_N, k: float = STEEL_K) -> float:
    """Unpolarised Fresnel absorptivity 1 - (|rs|^2 + |rp|^2)/2 for complex index n + ik, incidence from air."""
    m = complex(n, k)
    ci = math.cos(incidence_rad)
    ct = cmath.sqrt(1.0 - (math.sin(incidence_rad) / m) ** 2)
    rs = (ci - m * ct) / (ci + m * ct)
    rp = (m * ci - ct) / (m * ci + ct)
    return 1.0 - 0.5 * (abs(rs) ** 2 + abs(rp) ** 2)


def clausius_clapeyron_Pa(Ts: float, p: PistonProps) -> float:
    """A11: Pcc = P0 exp(c (1 - Tv0/Ts))."""
    return p.P0 * math.exp(p.c * (1.0 - p.Tv0 / Ts))


def recoil_pressure_Pa(Ts: float, p: PistonProps) -> float:
    """A10: Pr = 0.5 (1 + beta) Pcc."""
    return 0.5 * (1.0 + p.beta) * clausius_clapeyron_Pa(Ts, p)


def threshold_temperature_K(p: PistonProps) -> float:
    """Tth: Pr(Tth) = Pamb (Appendix A remark)."""
    return p.Tv0 / (1.0 - math.log(p.Pamb / (0.5 * (1.0 + p.beta) * p.P0)) / p.c)


def ejection_speed(Ts: float, p: PistonProps) -> float:
    """A10: Vm = sqrt(2 (Pr - Pamb) / rho_m); zero below threshold."""
    return math.sqrt(max(0.0, 2.0 * (recoil_pressure_Pa(Ts, p) - p.Pamb) / p.rho_m))


def vapour_mass_flux(Ts: float, p: PistonProps) -> float:
    """A12: rho_m Vv = (1 - beta) sqrt(Mw / (2 pi R Ts)) Pcc  [kg/m2/s]."""
    return (1.0 - p.beta) * math.sqrt(p.Mw / (2.0 * math.pi * R_GAS * Ts)) * clausius_clapeyron_Pa(Ts, p)


def film_function_Y(Ts: float, p: PistonProps) -> float:
    """A1: Y(Ts) = ln(1 + rho_m Cp_m (Ts - Tm) / (rho_s Cp_s (Tm - T0) + rho_s Lm))."""
    return math.log(1.0 + p.rho_m * p.cp_m * (Ts - p.Tm) / (p.rho_s * p.cp_s * (p.Tm - p.T0) + p.rho_s * p.Lm))


def cos_alpha(Ts: float, Vw: float, d: float, p: PistonProps) -> float:
    """Closed form of A2 with A1 and Eq. 9 (may be < 0 below the depression threshold or > 1 when no stationary
    front exists at this Ts)."""
    Vm = ejection_speed(Ts, p)
    Vv = vapour_mass_flux(Ts, p) / p.rho_m
    Y = film_function_Y(Ts, p)
    return ((p.rho_m * Vm * p.kappa_m * Y / Vw + p.rho_m * Vv * (1.5 * math.pi / 4.0) * d - p.rho_s * p.kappa_m * Y)
            / (0.5 * p.rho_s * Vw * d))


def state_at(Ts: float, alpha: float, Vw: float, d: float, p: PistonProps) -> Dict[str, float]:
    """All GPM quantities for a given (Ts, alpha); residuals of A2 and A3 are recomputed from the pieces."""
    Vm = ejection_speed(Ts, p)
    Vv = vapour_mass_flux(Ts, p) / p.rho_m
    Y = film_function_Y(Ts, p)
    ca, sa = math.cos(alpha), math.sin(alpha)
    Vd = Vw * ca
    delta0 = p.kappa_m * Y / Vd
    R = 1.0 / math.tan(alpha)
    e = R * d
    Sv = (1.5 * math.pi / 4.0) * d * d / sa
    T_star = 0.5 * (p.Tm + Ts)
    dHm = p.cp_s * (p.Tm - p.T0) + p.Lm + p.cp_m * (Ts - T_star)
    dHv = p.cp_s * (p.Tm - p.T0) + p.Lm + p.cp_m * (Ts - p.Tm) + p.Lv
    Pm = p.rho_m * Vm * delta0 * e * dHm
    Pvap = p.rho_m * Vv * Sv * dHv
    Pe_d = Vw * d / (2.0 * p.kappa_s)
    Pcond = p.K_s * (p.Tm - p.T0) * (0.5 * p.m0 * Pe_d * (1.0 + 2.0 * delta0 / d) + p.n0) * e
    Pkin = p.rho_m * Vm * delta0 * e * Vm * Vm / 2.0
    Pabs = Pm + Pvap + Pcond + Pkin
    A = fresnel_absorptivity(math.pi / 2.0 - alpha, p.n, p.k)
    mass_lhs = 0.5 * p.rho_s * Vw * (d + 2.0 * delta0) * e
    mass_rhs = p.rho_m * Vm * delta0 * e + p.rho_m * Vv * Sv
    return {"Ts_K": Ts, "alpha_rad": alpha, "R": R, "depth_m": e, "delta0_m": delta0, "Vd_m_s": Vd, "Vm_m_s": Vm,
            "Vv_m_s": Vv, "Sv_m2": Sv, "recoil_Pa": recoil_pressure_Pa(Ts, p), "A_F": A, "Pm_W": Pm, "Pvap_W": Pvap,
            "Pcond_W": Pcond, "Pkin_W": Pkin, "Pabs_W": Pabs, "P_W": Pabs / A, "Pe": Pe_d,
            "fracCond": Pcond / Pabs, "fracVap": Pvap / Pabs, "fracFus": Pm / Pabs, "fracKin": Pkin / Pabs,
            "massResidual": abs(mass_lhs - mass_rhs) / mass_lhs, "dVm_over_Vw": Vm / Vw - 1.0}


# ---------------------------------------------------------------- solvers
def _ts_window(Vw: float, d: float, p: PistonProps) -> Tuple[float, float]:
    """Ts interval on which 0 < cos(alpha) < 1 (cos(alpha)(Ts) increases with Ts)."""
    Tth = threshold_temperature_K(p)
    lo = Tth * (1.0 + 1e-9)
    f_lo = cos_alpha(lo, Vw, d, p)
    hi, step = lo, 0.5
    while cos_alpha(hi, Vw, d, p) < 1.0:
        step *= 2.0
        hi = lo + step
        if step > 1e5:
            raise RuntimeError("no stationary front found")
    if f_lo > 0.0:
        t_zero = lo
    else:
        t_zero = brentq(lambda T: cos_alpha(T, Vw, d, p), lo, hi, xtol=1e-9, rtol=1e-13, maxiter=200)
    t_one = brentq(lambda T: cos_alpha(T, Vw, d, p) - 1.0, lo, hi, xtol=1e-9, rtol=1e-13, maxiter=200)
    return t_zero, t_one


def state_for_aspect_ratio(R: float, Vw: float, d: float, p: PistonProps) -> Dict[str, float]:
    """Solve Ts from A2 for the front inclination alpha = atan(1/R), then the full state (P as output)."""
    alpha = math.atan2(1.0, R)
    target = math.cos(alpha)
    t_zero, t_one = _ts_window(Vw, d, p)
    Ts = brentq(lambda T: cos_alpha(T, Vw, d, p) - target, t_zero, t_one, xtol=1e-9, rtol=1e-14, maxiter=200)
    return state_at(Ts, alpha, Vw, d, p)


def threshold_powers(Vw: float, d: float, p: PistonProps) -> Dict[str, float]:
    """P* (R -> 0, Eq. 14 depression threshold) and Pt (R = 1, Eq. 11)."""
    return {"Pstar_W": state_for_aspect_ratio(1e-4, Vw, d, p)["P_W"], "Pt_W": state_for_aspect_ratio(1.0, Vw, d, p)["P_W"]}


def solve_power(P: float, Vw: float, d: float, p: PistonProps, R_max: float = 200.0) -> Dict[str, Any]:
    """Aspect ratio and depth for an incident power P (uniform spot d). Below P* the depth is 0."""
    s_lo = state_for_aspect_ratio(1e-4, Vw, d, p)
    if P <= s_lo["P_W"]:
        return {"status": "below-threshold", "R": 0.0, "depth_m": 0.0, "P_W": P, "Pstar_W": s_lo["P_W"],
                "energyResidual": 0.0, "massResidual": 0.0}
    s_hi = state_for_aspect_ratio(R_max, Vw, d, p)
    if P >= s_hi["P_W"]:
        return {"status": "above-range", "R": math.inf, "depth_m": math.inf, "P_W": P, "Pstar_W": s_lo["P_W"]}
    lnR = brentq(lambda x: state_for_aspect_ratio(math.exp(x), Vw, d, p)["P_W"] - P, math.log(1e-4), math.log(R_max),
                 xtol=1e-10, rtol=1e-13, maxiter=200)
    s = state_for_aspect_ratio(math.exp(lnR), Vw, d, p)
    s.update({"status": "solved", "Pstar_W": s_lo["P_W"], "energyResidual": abs(s["A_F"] * P - s["Pabs_W"]) / (s["A_F"] * P),
              "P_W": P})
    return s


def keyhole_depth(power_W: float, speed_mm_s: float, beam_diameter_1e2_um: float, props: PistonProps,
                  beam_convention: str = "fwhm") -> Dict[str, Any]:
    """Depth for a Gaussian 1/e2 diameter: d_eff = 0.5887 d (Fabbro Sec. 3.4) or d itself."""
    scale = FWHM_OVER_1E2 if beam_convention == "fwhm" else 1.0
    d = beam_diameter_1e2_um * 1e-6 * scale
    s = solve_power(float(power_W), speed_mm_s * 1e-3, d, props)
    s["d_eff_um"] = d * 1e6
    s["beamConvention"] = beam_convention
    s["modelId"] = MODEL_ID
    s["inScopePred"] = bool(SCOPE_R_MIN <= s["R"] <= SCOPE_R_MAX)
    return s


# ---------------------------------------------------------------- Step 1: reproduction of Fabbro 2020
GRID_D = (60e-6, 120e-6, 180e-6)
GRID_V = (0.25, 0.5, 1.0)
FIG4_PT_READ = {0.25: 240.0, 0.5: 340.0, 1.0: 600.0}
FIG7_READ = {(0.25, 60e-6): (1.4, 2.3), (0.25, 120e-6): (2.1, 3.2), (0.25, 180e-6): (2.6, 4.5),
             (0.5, 60e-6): (2.0, 3.3), (0.5, 120e-6): (3.2, 5.8), (0.5, 180e-6): (4.5, 7.4),
             (1.0, 60e-6): (3.3, 5.7), (1.0, 120e-6): (5.8, 9.4), (1.0, 180e-6): (7.4, 12.7)}


def _linfit(xs: List[float], ys: List[float]) -> Tuple[float, float, float]:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx
    a = my - b * mx
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - my) ** 2 for y in ys)
    return a, b, 1.0 - ss_res / ss_tot


def reproduce_fabbro(p: PistonProps = FABBRO_TI64) -> Dict[str, Any]:
    """Recompute every published number listed in PREDECLARED_fabbro_piston.md (R1-R8)."""
    out: Dict[str, Any] = {"props": asdict(p)}
    A1 = fresnel_absorptivity(math.pi / 4.0, p.n, p.k)
    out["R1"] = {"A_F_pi4": A1, "published": 0.32}
    out["R2"] = {"Tth_over_Tv0": threshold_temperature_K(p) / p.Tv0, "published": 1.041}
    # R3: threshold grid and Eq. 11 fit
    xs, ys, grid = [], [], []
    for Vw in GRID_V:
        for d in GRID_D:
            th = threshold_powers(Vw, d, p)
            xs.append(Vw * d)
            ys.append(A1 * th["Pt_W"] / d)
            grid.append({"Vw": Vw, "d_um": d * 1e6, "Pt_W": th["Pt_W"], "Pstar_W": th["Pstar_W"]})
    a1, b1, r2 = _linfit(xs, ys)
    K = p.K_s
    out["R3"] = {"a1": a1, "b1": b1, "r2": r2, "published_a1": 2.1e5, "published_b1": 1.2e10,
                 "m1": b1 * 2.0 * p.kappa_s / (K * (p.Tv0 - p.T0)), "n1": a1 / (K * (p.Tv0 - p.T0)),
                 "published_m1": 2.1, "published_n1": 2.2, "grid": grid}
    # R4: Fig. 4, d = 120 um, R(P) at the four powers and Pt
    fig4 = {}
    for Vw in GRID_V:
        pts = [state_for_aspect_ratio(R, Vw, 120e-6, p) for R in (0.5, 1.0, 1.5, 2.0, 2.5)]
        Ps = [s["P_W"] for s in pts]
        Rs = [s["R"] for s in pts]
        a, b, rr = _linfit(Ps, Rs)
        Pt = [s for s in pts if abs(s["R"] - 1.0) < 1e-9][0]["P_W"]
        fig4[Vw] = {"P_W": Ps, "R": Rs, "r0": b, "Pprime_W": -a / b, "r2": rr, "Pt_W": Pt, "Pt_read_W": FIG4_PT_READ[Vw]}
    out["R4"] = fig4
    # R5, R6, R8 over the grid for R in 0.5..2.5
    shares = {"fracCond": [], "fracVap": [], "fracFus": [], "fracKin": []}
    AF = []
    fig7 = {}
    for Vw in GRID_V:
        for d in GRID_D:
            for R in (0.5, 1.0, 1.5, 2.0, 2.5):
                s = state_for_aspect_ratio(R, Vw, d, p)
                for key in shares:
                    shares[key].append(s[key])
                AF.append(s["A_F"])
            s05 = state_for_aspect_ratio(0.5, Vw, d, p)
            s25 = state_for_aspect_ratio(2.5, Vw, d, p)
            fig7[f"{Vw}|{d*1e6:.0f}"] = {"dVm_R05": s05["dVm_over_Vw"], "dVm_R25": s25["dVm_over_Vw"],
                                         "read": FIG7_READ[(Vw, d)]}
    out["R5"] = {k: (min(v), max(v)) for k, v in shares.items()}
    out["R6"] = {"A_F_min": min(AF), "A_F_max": max(AF)}
    out["R8"] = fig7
    # R7: appendix remark, d = 300 um
    rem = {}
    for Vw in (0.05, 0.5):
        s = state_for_aspect_ratio(2.5, Vw, 300e-6, p)
        rem[f"1bar|{Vw}"] = {"P_W": s["P_W"], "Ts_K": s["Ts_K"], "recoil_bar": s["recoil_Pa"] / 1e5, "Vm_m_s": s["Vm_m_s"]}
        p_low = replace(p, Pamb=1e3)                       # ambient 0.01 bar, vapour curve unchanged
        s = state_for_aspect_ratio(2.5, Vw, 300e-6, p_low)
        rem[f"0.01bar-curve-unchanged|{Vw}"] = {"P_W": s["P_W"], "Ts_K": s["Ts_K"], "recoil_bar": s["recoil_Pa"] / 1e5}
        p_low2 = replace(p, Pamb=1e3, P0=1e3, Tv0=2780.0)  # ambient 0.01 bar, curve re-anchored at Tv0 = 2780 K
        s = state_for_aspect_ratio(2.5, Vw, 300e-6, p_low2)
        rem[f"0.01bar-reanchored-2780K|{Vw}"] = {"P_W": s["P_W"], "Ts_K": s["Ts_K"], "recoil_bar": s["recoil_Pa"] / 1e5}
    rem["published"] = {"1bar|0.05": 1200.0, "0.01bar|0.05": 571.0, "1bar|0.5": 3700.0, "0.01bar|0.5": 3700.0,
                        "Ts_K": 3600.0, "recoil_bar": 2.0, "Vm_m_s": 6.0}
    out["R7"] = rem
    # Cp sensitivity of the Eq. 11 constants
    sens = {}
    for cp in (700.0, 840.0, 1000.0):
        q = replace(p, cp_s=cp, cp_m=cp)
        xs2, ys2 = [], []
        for Vw in GRID_V:
            for d in GRID_D:
                xs2.append(Vw * d)
                ys2.append(A1 * threshold_powers(Vw, d, q)["Pt_W"] / d)
        a, b, _ = _linfit(xs2, ys2)
        sens[cp] = {"a1": a, "b1": b, "K_W_mK": q.K_s}
    out["cpSensitivity"] = sens
    return out


def reproduction_verdict(rep: Dict[str, Any]) -> Dict[str, Any]:
    """Pass/fail per pre-declared target (tolerances from PREDECLARED_fabbro_piston.md)."""
    v: Dict[str, Any] = {}
    v["R1"] = abs(rep["R1"]["A_F_pi4"] - 0.32) <= 0.01
    v["R2"] = abs(rep["R2"]["Tth_over_Tv0"] / 1.041 - 1.0) <= 0.01
    v["R3"] = (abs(rep["R3"]["b1"] / 1.2e10 - 1.0) <= 0.20) and (abs(rep["R3"]["a1"] / 2.1e5 - 1.0) <= 0.40)
    v["R4"] = all(abs(f["Pt_W"] / f["Pt_read_W"] - 1.0) <= 0.15 and f["r2"] > 0.98 for f in rep["R4"].values())
    sh = rep["R5"]
    v["R5"] = (0.20 <= sh["fracCond"][0] and sh["fracCond"][1] <= 0.55 and 0.10 <= sh["fracVap"][0]
               and sh["fracVap"][1] <= 0.45 and 0.20 <= sh["fracFus"][0] and sh["fracFus"][1] <= 0.50
               and sh["fracKin"][1] < 0.005)
    v["R6"] = 0.30 <= rep["R6"]["A_F_min"] and rep["R6"]["A_F_max"] <= 0.37
    r7 = rep["R7"]
    v["R7_P_1bar"] = (abs(r7["1bar|0.05"]["P_W"] / 1200.0 - 1.0) <= 0.20
                      and abs(r7["1bar|0.5"]["P_W"] / 3700.0 - 1.0) <= 0.20)
    v["R7_P_0.01bar_curve_unchanged"] = abs(r7["0.01bar-curve-unchanged|0.05"]["P_W"] / 571.0 - 1.0) <= 0.20
    v["R7_P_0.01bar_reanchored"] = abs(r7["0.01bar-reanchored-2780K|0.05"]["P_W"] / 571.0 - 1.0) <= 0.20
    v["R7_Ts"] = abs(r7["1bar|0.5"]["Ts_K"] / 3600.0 - 1.0) <= 0.05
    v["R7_recoil"] = abs(r7["1bar|0.5"]["recoil_bar"] / 2.0 - 1.0) <= 0.30
    v["R7_Vm"] = abs(r7["1bar|0.5"]["Vm_m_s"] / 6.0 - 1.0) <= 0.30
    v["R8"] = all(abs(f["dVm_R05"] / f["read"][0] - 1.0) <= 0.25 and abs(f["dVm_R25"] / f["read"][1] - 1.0) <= 0.25
                  for f in rep["R8"].values())
    v["requiredPass"] = all(v[k] for k in ("R1", "R3", "R4", "R5", "R7_P_1bar")) and (
        v["R7_P_0.01bar_curve_unchanged"] or v["R7_P_0.01bar_reanchored"])
    return v


# ---------------------------------------------------------------- Step 3: pre-declared evaluation
def _stats(pairs: List[Tuple[float, float]]) -> Dict[str, float]:
    pairs = [(x, m) for x, m in pairs if m]
    if not pairs:
        return {"n": 0}
    rel = [(x - m) / m for x, m in pairs]
    return {"n": len(pairs), "ratio": st.median(x / m for x, m in pairs), "mape": 100.0 * st.mean(abs(r) for r in rel),
            "bias": 100.0 * st.mean(rel)}


def _baseline_depths(row: Dict[str, Any], dH: float) -> Dict[str, float]:
    """App Fabbro (K0: d = 1/e2) and its FWHM variant (K1-r30), app room-temperature props, as in the D-3a report."""
    from fabbro_keyhole import fabbro_keyhole_depth_m
    from lpbf_public_datasets import screening_props
    p = screening_props(row["material"])
    k = p["thermal_conductivity_W_mK"]
    alpha = k / (p["density_kg_m3"] * p["specific_heat_J_kgK"])
    out = {}
    for name, scale in (("app-1e2", 1.0), ("app-fwhm", FWHM_OVER_1E2)):
        r = fabbro_keyhole_depth_m(row["power_W"], row["speed_mm_s"] * 1e-3, row["beamDiameter_um"] * 1e-6 * scale, k,
                                   alpha, p["boiling_C"], row["preheat_C"], p["absorptivity_IR"], dH)
        out[name] = r["depth_m"] * 1e6
    return out


def load_evaluation_rows() -> Dict[str, List[Dict[str, Any]]]:
    import lpbf_keyhole_literature as kl
    import lpbf_public_datasets as pd
    sets: Dict[str, List[Dict[str, Any]]] = {}

    def mk(r, meas, kind, extra=None):
        d = {"rowId": r["rowId"], "material": r["material"], "power_W": r["power_W"], "speed_mm_s": r["speed_mm_s"],
             "beamDiameter_um": r["beamDiameter_um"], "preheat_C": r.get("preheat_C", 20.0), "meas_um": meas,
             "kind": kind}
        d["dH"] = pd.normalized_enthalpy(d["material"], d["power_W"], d["speed_mm_s"], d["beamDiameter_um"], d["preheat_C"])
        d.update(extra or {})
        return d

    cun = kl.load_cunningham_depths()["rows"]
    sets["cunningham95"] = [mk(r, r["vaporDepressionDepth_um"], "vapour") for r in cun if r["beamDiameter_um"] == 95.0]
    sets["cunningham140"] = [mk(r, r["vaporDepressionDepth_um"], "vapour") for r in cun if r["beamDiameter_um"] == 140.0]
    gan = kl.load_gan_data1_ti64()["rows"]
    sets["gan-data1-95 (same experiments, not counted)"] = [mk(r, r["keyholeDepth_um"], "vapour") for r in gan if r["beamDiameter_um"] == 95.0]
    sets["gan-data1-140 (same experiments, not counted)"] = [mk(r, r["keyholeDepth_um"], "vapour") for r in gan if r["beamDiameter_um"] == 140.0]
    zhao = kl.load_zhao_boundary()["rows"]
    sets["zhao-bare"] = [mk(r, r["keyholeDepth_um"], "vapour") for r in zhao if r["setting"] == "bare" and r["keyholeDepth_um"]]
    sets["zhao-powder (powder bed, reported only)"] = [mk(r, r["keyholeDepth_um"], "vapour") for r in zhao if r["setting"] != "bare" and r["keyholeDepth_um"]]
    nist = json.loads((PY.parent / "data/benchmark/nist-amb2022-03-optical/table4-aggregate-v2.json").read_text("utf-8"))
    T0 = float(nist["experiment"]["substrateAndChamberTemperature_C"])
    sets["nist-in718 (melt bound)"] = [mk({"rowId": f"nist-{c['caseNumber']}", "material": "Inconel 718",
                                           "power_W": float(c["laserPower_W"]), "speed_mm_s": float(c["scanSpeed_mm_s"]),
                                           "beamDiameter_um": float(c["beamDiameterD4sigma_um"]), "preheat_C": T0},
                                          float(c["depthMean_um"]), "melt") for c in nist["cases"]]
    hof = pd.load_hofmann_316l()["rows"]
    for layer, shift in ((0.0, 0.0), (30.0, 18.0), (60.0, 36.0)):
        name = "hofmann-bare keyhole band (melt bound)" if layer == 0.0 else f"hofmann-{layer:.0f}um keyhole band (melt bound, datum -{shift:.0f} um)"
        rows = []
        for r in hof:
            if r["layer_um"] != layer or r["balling"] == 1:
                continue
            m = mk(r, r["depth_um"], "melt", {"datumShift_um": shift})
            if m["dH"] >= 20.0:
                rows.append(m)
        sets[name] = rows
    ku = pd.load_ku_leuven_316l_ti64()["rows"]
    sets["ku-316l keyhole (melt bound)"] = [mk(r, r["depth_um"], "melt") for r in ku if r["material"].startswith("316L") and r.get("publishedRegime") == "keyhole"]
    sets["ku-ti64 keyhole (melt bound, reported only)"] = [mk(r, r["depth_um"], "melt") for r in ku if r["material"].startswith("Ti") and r.get("publishedRegime") == "keyhole"]
    return sets


def evaluate(variant: str = "P-EFF", beam_convention: str = "fwhm", sets: Optional[Dict[str, List[Dict[str, Any]]]] = None) -> Dict[str, Any]:
    sets = sets or load_evaluation_rows()
    report: Dict[str, Any] = {"variant": variant, "beamConvention": beam_convention, "sets": {}}
    max_e_res, max_m_res = 0.0, 0.0
    for name, rows in sets.items():
        preds = []
        for r in rows:
            if variant == "P-FAB" and not r["material"].startswith("Ti"):
                continue
            p = props_from_app(r["material"], variant, r["preheat_C"])
            s = keyhole_depth(r["power_W"], r["speed_mm_s"], r["beamDiameter_um"], p, beam_convention)
            base = _baseline_depths(r, r["dH"])
            e_um = s["depth_m"] * 1e6 - r.get("datumShift_um", 0.0)
            if s["status"] == "solved":
                max_e_res = max(max_e_res, s["energyResidual"])
                max_m_res = max(max_m_res, s["massResidual"])
            meas_R = r["meas_um"] / s["d_eff_um"]
            in_scope = (SCOPE_R_MIN <= meas_R <= SCOPE_R_MAX) if r["kind"] == "vapour" else s["inScopePred"]
            preds.append({"rowId": r["rowId"], "P": r["power_W"], "v": r["speed_mm_s"], "d": r["beamDiameter_um"],
                          "meas_um": r["meas_um"], "pred_um": e_um, "R_pred": s["R"], "R_meas": meas_R,
                          "status": s["status"], "inScope": in_scope, "A_F": s.get("A_F"), "Ts_K": s.get("Ts_K"),
                          "fracVap": s.get("fracVap"), "fracCond": s.get("fracCond"), "fracFus": s.get("fracFus"),
                          "dH": r["dH"], **base})
        if not preds:
            continue
        kind = rows[0]["kind"]
        ins = [q for q in preds if q["inScope"]]
        entry: Dict[str, Any] = {"kind": kind, "n": len(preds), "nInScope": len(ins),
                                 "nBelowThreshold": sum(1 for q in preds if q["status"] == "below-threshold"),
                                 "gpm_inScope": _stats([(q["pred_um"], q["meas_um"]) for q in ins]),
                                 "gpm_all": _stats([(q["pred_um"], q["meas_um"]) for q in preds]),
                                 "app1e2_inScope": _stats([(q["app-1e2"], q["meas_um"]) for q in ins]),
                                 "app1e2_all": _stats([(q["app-1e2"], q["meas_um"]) for q in preds]),
                                 "appFwhm_inScope": _stats([(q["app-fwhm"], q["meas_um"]) for q in ins]),
                                 "appFwhm_all": _stats([(q["app-fwhm"], q["meas_um"]) for q in preds]),
                                 "R_pred_median": st.median(q["R_pred"] for q in preds if math.isfinite(q["R_pred"])),
                                 "R_meas_median": st.median(q["R_meas"] for q in preds),
                                 "fracVap_median": st.median(q["fracVap"] for q in preds if q["fracVap"] is not None) if any(q["fracVap"] is not None for q in preds) else None,
                                 "rows": preds}
        if kind == "melt":
            entry["violations_all"] = sum(1 for q in preds if q["pred_um"] > q["meas_um"])
            entry["violations_inScope"] = sum(1 for q in ins if q["pred_um"] > q["meas_um"])
            entry["violations_app1e2"] = sum(1 for q in preds if q["app-1e2"] > q["meas_um"])
            entry["violations_appFwhm"] = sum(1 for q in preds if q["app-fwhm"] > q["meas_um"])
        report["sets"][name] = entry
    report["maxEnergyResidual"] = max_e_res
    report["maxMassResidual"] = max_m_res
    return report


def optics_sensitivity(Vw: float = 0.8, d_1e2_um: float = 95.0, P: float = 250.0) -> List[Dict[str, float]]:
    """Depth change with the Fresnel optical constants (steel 3.6 + 5i is Fabbro's; no alloy value is claimed)."""
    out = []
    for n in (2.5, 3.6, 5.0):
        for k in (3.0, 5.0, 7.0):
            p = replace(FABBRO_TI64, n=n, k=k)
            s = keyhole_depth(P, Vw * 1e3, d_1e2_um, p)
            out.append({"n": n, "k": k, "A_F_pi4": fresnel_absorptivity(math.pi / 4, n, k), "depth_um": s["depth_m"] * 1e6, "R": s["R"]})
    return out


def _fmt(s: Dict[str, float]) -> str:
    return "-" if s.get("n", 0) == 0 else f"n{s['n']} {s['ratio']:.2f} / {s['mape']:.0f} / {s['bias']:+.0f}"


def main(argv: List[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--reproduce", action="store_true")
    ap.add_argument("--evaluate", action="store_true")
    ap.add_argument("--json", type=Path, default=None)
    a = ap.parse_args(argv)
    out: Dict[str, Any] = {}
    if a.reproduce or not a.evaluate:
        rep = reproduce_fabbro()
        ver = reproduction_verdict(rep)
        out["reproduction"] = rep
        out["verdict"] = ver
        print(f"R1 A_F(pi/4) = {rep['R1']['A_F_pi4']:.3f} (0.32)  R2 Tth/Tv0 = {rep['R2']['Tth_over_Tv0']:.4f} (1.041)")
        print(f"R3 a1 = {rep['R3']['a1']:.3e} (2.1e5)  b1 = {rep['R3']['b1']:.3e} (1.2e10)  r2 = {rep['R3']['r2']:.4f}  m1 = {rep['R3']['m1']:.2f} (2.1)  n1 = {rep['R3']['n1']:.2f} (2.2)")
        for g in rep["R3"]["grid"]:
            print(f"   Vw {g['Vw']} d {g['d_um']:.0f}: Pt {g['Pt_W']:.0f} W, P* {g['Pstar_W']:.0f} W")
        for Vw, f in rep["R4"].items():
            print(f"R4 Fig.4 d=120 Vw={Vw}: Pt {f['Pt_W']:.0f} W (read {f['Pt_read_W']:.0f}), r0 {f['r0']*1e3:.2f}/kW, P' {f['Pprime_W']:.0f} W, r2 {f['r2']:.4f}; P(R=0.5..2.5) = " + ", ".join(f"{x:.0f}" for x in f["P_W"]))
        print("R5 shares (min,max): " + ", ".join(f"{k} {v[0]*100:.0f}-{v[1]*100:.1f}%" for k, v in rep["R5"].items()))
        print(f"R6 A_F range {rep['R6']['A_F_min']:.3f}-{rep['R6']['A_F_max']:.3f}")
        for k, v in rep["R7"].items():
            print(f"R7 {k}: {v}")
        for k, v in rep["R8"].items():
            print(f"R8 Vw|d {k}: dVm/Vw R0.5 {v['dVm_R05']:.1f} (read {v['read'][0]}), R2.5 {v['dVm_R25']:.1f} (read {v['read'][1]})")
        print("Cp sensitivity: " + "; ".join(f"Cp {cp:.0f}: a1 {v['a1']:.2e} b1 {v['b1']:.2e} K {v['K_W_mK']:.1f}" for cp, v in rep["cpSensitivity"].items()))
        print("verdict: " + ", ".join(f"{k}={'PASS' if v else 'FAIL'}" for k, v in ver.items()))
    if a.evaluate:
        sets = load_evaluation_rows()
        out["evaluation"] = {}
        for variant in PROPERTY_VARIANTS:
            for conv in ("fwhm", "1e2"):
                rep = evaluate(variant, conv, sets)
                out["evaluation"][f"{variant}|{conv}"] = rep
                print(f"\n### {variant} d_eff={conv}: max energy residual {rep['maxEnergyResidual']:.2e}, max mass residual {rep['maxMassResidual']:.2e}")
                print("| set | n | in scope | below P* | GPM in-scope n ratio/MAPE/bias | GPM all | app 1/e2 in-scope | app FWHM in-scope | R_meas med | R_pred med | Pvap share med | bound viol all / in-scope (app1e2 / appFWHM) |")
                print("|---|---|---|---|---|---|---|---|---|---|---|---|")
                for name, e in rep["sets"].items():
                    viol = (f"{e['violations_all']}/{e['n']} / {e['violations_inScope']}/{e['nInScope']} ({e['violations_app1e2']} / {e['violations_appFwhm']})"
                            if e["kind"] == "melt" else "")
                    fv = f"{e['fracVap_median']*100:.0f}%" if e["fracVap_median"] is not None else "-"
                    print(f"| {name} | {e['n']} | {e['nInScope']} | {e['nBelowThreshold']} | {_fmt(e['gpm_inScope'])} | {_fmt(e['gpm_all'])} | {_fmt(e['app1e2_inScope'])} | {_fmt(e['appFwhm_inScope'])} | {e['R_meas_median']:.2f} | {e['R_pred_median']:.2f} | {fv} | {viol} |")
        out["opticsSensitivity"] = optics_sensitivity()
        print("\nOptics sensitivity (Fabbro Ti64 set, 95 um 1/e2, 250 W, 0.8 m/s): " + "; ".join(f"n{o['n']} k{o['k']}: A_F {o['A_F_pi4']:.3f} e {o['depth_um']:.0f} um" for o in out["opticsSensitivity"]))
    if a.json:
        a.json.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
