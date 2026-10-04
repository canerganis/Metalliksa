"""
Independent oracle for the Li (1998) steel kinetics in kinetics_ttt_cct_solver (lane kin-li).

Written separately from the solver and with different numerics, so a re-blessed golden can be checked against
it: S(X) and the additivity integrals by scipy.integrate.quad (adaptive, with the end-point singularities left
to quad), CCT crossings by scipy.optimize.brentq on the integral, the critical cooling rate as the integral down
to Ms. The equations are transcribed from the sources, not from the solver:

  M. Li, PhD thesis, Oregon Graduate Institute (1996), doi:10.6083/M4S180SN, Eqs. 3.67 and 3.69-3.77 (pp. 83-86):
    S(X) = int_0^X dX / (X^(0.4(1-X)) (1-X)^(0.4X))
    tau_F = FC S(X) / (2^(0.41G) (Ae3-T)^3 exp(-27500/RT)),  FC = exp(1.00+6.31C+1.78Mn+0.31Si+1.12Ni+2.70Cr+4.06Mo)
    tau_P = PC S(X) / (2^(0.32G) (Ae1-T)^3 exp(-27500/RT)),  PC = exp(-4.25+4.12C+4.36Mn+0.44Si+1.71Ni+3.33Cr+5.19 Mo^0.5)
    tau_B = BC S(X) / (2^(0.29G) (Bs-T)^2 exp(-27500/RT)),   BC = exp(-10.23+10.18C+0.85Mn+0.55Ni+0.90Cr+0.36Mo)
    Bs = 637 - 58C - 35Mn - 15Ni - 34Cr - 41Mo
    Ms = 539 - 423C - 30.4Mn - 12.1Cr - 17.7Ni - 7.5Mo + 10Co - 7.5Si
    validity (p. 86): 0.1<C<0.5, Si<1.0, Mn<2, Ni<4, Cr<3, Mo<1, V<0.2, Cu<0.5, Mo+Ni+Cr+Mo<5, 0.01<Al<0.05
  J. Collins et al., Metals 13 (2023) 1168 (CC BY 4.0): Q = 115,060 J/mol (Eqs. 6, 9, 12); Grange (degF -> degC)
    Ae3 = (1570 - 323C - 25Mn + 80Si - 32Ni - 3Cr - 32)(5/9)  (Eq. 8),  Ae1 = (1333 - 25Mn + 40Si - 26Ni + 42Cr - 32)(5/9)
    (Eq. 11); G = -3.2877 - 6.6439 log10(l), l = sqrt(pi/4) d (Eqs. 3-4, l in mm).
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from scipy.integrate import quad
from scipy.optimize import brentq

Q_J_MOL = 27500.0 * 4.184
PHASES = ("Ferrite", "Pearlite", "Bainite")
N1 = {"Ferrite": 0.41, "Pearlite": 0.32, "Bainite": 0.29}
N2 = {"Ferrite": 3.0, "Pearlite": 3.0, "Bainite": 2.0}
ZERO_C = 273.15
COVERED = {"Fe", "C", "Si", "Mn", "Ni", "Cr", "Mo", "V", "Cu", "Al"}


def wt(comp: Dict[str, float], el: str) -> float:
    return float(comp[el]) if comp.get(el) else 0.0


def s_integral(x: float) -> float:
    return quad(lambda u: u ** (-0.4 * (1.0 - u)) * (1.0 - u) ** (-0.4 * u), 0.0, x, limit=400,
                epsabs=1e-13, epsrel=1e-12)[0]


def range_violations(comp: Dict[str, float]) -> Tuple[List[str], List[str]]:
    """Violation and unchecked texts in the solver's wording (the wording is part of the output contract)."""
    bad: List[str] = []
    for el in sorted(comp):
        if el not in COVERED and float(comp[el] or 0.0) > 0.0:
            bad.append(f"{el} {comp[el]:g} wt% is not covered by the stated range")
    c = wt(comp, "C")
    if not (0.1 < c < 0.5):
        bad.append(f"C {c:g} wt% (range 0.1 < C < 0.5)")
    for el, hi in (("Si", 1.0), ("Mn", 2.0), ("Ni", 4.0), ("Cr", 3.0), ("Mo", 1.0), ("V", 0.2), ("Cu", 0.5)):
        if not wt(comp, el) < hi:
            bad.append(f"{el} {wt(comp, el):g} wt% (range {el} < {hi:g})")
    s1 = wt(comp, "Mn") + wt(comp, "Ni") + wt(comp, "Cr") + wt(comp, "Mo")
    if not s1 < 5.0:
        bad.append(f"Mn+Ni+Cr+Mo {s1:g} wt% (range < 5)")
    s2 = wt(comp, "Mo") + wt(comp, "Ni") + wt(comp, "Cr") + wt(comp, "Mo")
    if not s2 < 5.0:
        bad.append(f"Mo+Ni+Cr+Mo (as printed) {s2:g} wt% (range < 5)")
    unchecked: List[str] = []
    if "Al" in comp:
        if not (0.01 < wt(comp, "Al") < 0.05):
            bad.append(f"Al {wt(comp, 'Al'):g} wt% (range 0.01 < Al < 0.05)")
    else:
        unchecked.append("Al not specified in the registry composition: the 0.01 < Al < 0.05 wt% bound is not checked")
    return bad, unchecked


class Oracle:
    def __init__(self, comp: Dict[str, float], grain_um: float, r_gas: float):
        self.r = r_gas
        c, mn, si, ni, cr, mo, co = (wt(comp, e) for e in ("C", "Mn", "Si", "Ni", "Cr", "Mo", "Co"))
        self.ae3 = (1570 - 323 * c - 25 * mn + 80 * si - 32 * ni - 3 * cr - 32) * 5 / 9
        self.ae1 = (1333 - 25 * mn + 40 * si - 26 * ni + 42 * cr - 32) * 5 / 9
        self.bs = 637 - 58 * c - 35 * mn - 15 * ni - 34 * cr - 41 * mo
        self.ms = 539 - 423 * c - 30.4 * mn - 12.1 * cr - 17.7 * ni - 7.5 * mo + 10 * co - 7.5 * si
        self.F = {
            "Ferrite": math.exp(1.00 + 6.31 * c + 1.78 * mn + 0.31 * si + 1.12 * ni + 2.70 * cr + 4.06 * mo),
            "Pearlite": math.exp(-4.25 + 4.12 * c + 4.36 * mn + 0.44 * si + 1.71 * ni + 3.33 * cr + 5.19 * mo ** 0.5),
            "Bainite": math.exp(-10.23 + 10.18 * c + 0.85 * mn + 0.55 * ni + 0.90 * cr + 0.36 * mo),
        }
        self.top = {"Ferrite": self.ae3, "Pearlite": self.ae1, "Bainite": self.bs}
        self.g = -3.2877 - 6.6439 * math.log10(math.sqrt(math.pi / 4) * grain_um / 1000.0)
        self.s01 = s_integral(0.01)

    def tau(self, phase: str, x: float, t_c: float) -> float:
        dt = self.top[phase] - t_c
        return (self.F[phase] * s_integral(x)
                / (2 ** (N1[phase] * self.g) * dt ** N2[phase] * math.exp(-Q_J_MOL / (self.r * (t_c + ZERO_C)))))

    def inv_tau_start(self, phase: str, t_c: float) -> float:
        dt = self.top[phase] - t_c
        if dt <= 0:
            return 0.0
        return (2 ** (N1[phase] * self.g) * dt ** N2[phase] * math.exp(-Q_J_MOL / (self.r * (t_c + ZERO_C)))
                / (self.F[phase] * self.s01))

    def ttt(self, points_per_phase: int = 40, max_s: float = 1e6) -> List[Dict[str, float]]:
        out = []
        for ph in PHASES:
            hi = self.top[ph] - 1.0
            if hi <= self.ms:
                continue
            for i in range(points_per_phase):
                t_c = self.ms + (hi - self.ms) * i / (points_per_phase - 1)
                ts = self.tau(ph, 0.01, t_c)
                if ts >= max_s:
                    continue
                out.append({"temperature_C": t_c, "phase": ph, "tStart_s": ts, "t50_s": self.tau(ph, 0.5, t_c),
                            "tFinish_s": self.tau(ph, 0.99, t_c), "drivingForce_DeltaT_C": self.top[ph] - t_c})
        return out

    def integral(self, phase: str, t_from: float, t_to: float) -> float:
        """int_{t_to}^{t_from} dT / tau_start(T)."""
        if t_from <= t_to:
            return 0.0
        return quad(lambda t: self.inv_tau_start(phase, t), t_to, t_from, limit=400, epsabs=1e-14, epsrel=1e-11)[0]

    def phase_start(self, phase: str, aust_c: float, rate: float) -> Optional[float]:
        t0 = min(aust_c, self.top[phase])
        if t0 <= self.ms or self.integral(phase, t0, self.ms) < rate:
            return None
        return brentq(lambda t: self.integral(phase, t0, t) - rate, self.ms, t0, xtol=1e-7)

    def critical_rate(self, aust_c: float) -> float:
        return max(self.integral(ph, min(aust_c, self.top[ph]), self.ms) for ph in PHASES)
