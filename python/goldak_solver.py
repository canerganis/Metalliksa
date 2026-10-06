#!/usr/bin/env python3
"""
Goldak double-ellipsoid temperature field (Goldak et al., Metall. Trans. B 1984)
with the Fachinotti–Cardona (Mecánica Computacional 2008) erf correction to Nguyen 1999.

Quasi-steady, laser-attached frame: +x travel, z ≥ 0 depth (adiabatic free surface
via the y ≥ 0 interpretation in Fachinotti Remark II).

Axes (af, ar, b, c) are an input — typically beam-seeded, not a circular fit to W/D.
Not Goldak FEA and not a qualification solver.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.special import erf as _erf  # vectorised; the frompyfunc(math.erf) wrapper cost 2.6-3.9x in screening()

MODEL_ID = "goldak-half-space-v3"
# Time quadrature in u = sqrt(tau): a first panel [0, u0], geometric panels (x2) while their width
# stays below the wake-pulse scale du = KAPPA * sqrt(alpha/2) / v, then uniform panels of width du
# up to u_max = sqrt(tau_end). The wake pulse of a point x < 0 sits at tau = |x|/v with standard
# deviation sqrt(sf/6)/v in tau, i.e. about sqrt(alpha/2)/v in u at every speed, so uniform-in-u
# panels resolve it at any Peclet number. A single Gauss-Legendre rule on [0, tau_max] (the v2
# kernel) truncated or under-resolved the wake by up to 100 % for v <= 0.2 or >= 1.5 m/s.
_GL_GEOMETRIC_N = 12
_GL_UNIFORM_N = 8
_PULSE_PANEL_SIGMAS = 3.0
# Wake window (laser frame, x < 0) the quadrature is sized for; temperature_C widens it on demand.
WAKE_LENGTH_M = 3.0e-3
# exp(-E_CUT) truncation level of the advective Gaussian tail beyond the wake window.
_E_CUT = 40.0


def _u_panels(u0: float, du: float, u_max: float):
    xi_g, w_g = leggauss(_GL_GEOMETRIC_N)
    xi_u, w_u = leggauss(_GL_UNIFORM_N)
    edges = [0.0, u0]
    while edges[-1] < du and edges[-1] * 2.0 < u_max:
        edges.append(edges[-1] * 2.0)
    us, ws = [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        us.append(0.5 * (hi - lo) * (xi_g + 1.0) + lo)
        ws.append(w_g * (0.5 * (hi - lo)))
    lo = edges[-1]
    while lo < u_max:
        hi = lo + du if lo + du < u_max else u_max
        us.append(0.5 * (hi - lo) * (xi_u + 1.0) + lo)
        ws.append(w_u * (0.5 * (hi - lo)))
        lo = hi
    return np.concatenate(us), np.concatenate(ws)


def goldak_fractions(af_m: float, ar_m: float) -> tuple[float, float]:
    """Continuity of q across x=0: ff/af = fr/ar, ff+fr=2 (Fachinotti eq. 18)."""
    af = max(1e-7, float(af_m))
    ar = max(1e-7, float(ar_m))
    ff = 2.0 * af / (af + ar)
    fr = 2.0 - ff
    return ff, fr


def goldak_q_parameter_W(total_power_W: float) -> float:
    """Return Goldak's Q coefficient for the power absorbed by the body.

    Q is the power deposited in the half-space body z >= 0 (Goldak 1984): with the
    6√3 prefactor and ff + fr = 2, each half-ellipsoid integrates to f_i·Q/2 over
    z >= 0, so the two together give exactly Q. Integrating the same q over all z
    gives 2Q, but that doubling is the image source that makes z = 0 adiabatic
    (Fachinotti Remark II): the analytic full-space field IS the half-space solution
    for a body receiving Q. Q must therefore NOT be halved; the far field tends to
    Rosenthal(P_absorbed). (goldak-total-power-v2 halved it: a factor-2 power error.)
    """
    return float(total_power_W)


def seed_goldak_axes(r0_m: float) -> dict:
    """Beam-based first guess (Goldak default ar ≈ 2 af, not a measured pool)."""
    r0 = max(8e-6, float(r0_m))
    return {
        "af_m": r0,
        "ar_m": 2.0 * r0,
        "b_m": r0,
        "c_m": r0,
    }


class GoldakField:
    def __init__(
        self,
        T0_C: float,
        Q_W: float,
        rho: float,
        cp: float,
        alpha_th: float,
        af_m: float,
        ar_m: float,
        b_m: float,
        c_m: float,
    ):
        self.T0_C = float(T0_C)
        # Public input is the absorbed power deposited in the half-space body;
        # see goldak_q_parameter_W (no halving; the full-space 2Q is the image source).
        self.Q_W = goldak_q_parameter_W(Q_W)
        self.rho_cp = max(1.0, float(rho) * float(cp))
        self.alpha = max(1e-12, float(alpha_th))
        self.af = max(4e-6, float(af_m))
        self.ar = max(4e-6, float(ar_m))
        self.b = max(4e-6, float(b_m))
        self.c = max(4e-6, float(c_m))
        self.ff, self.fr = goldak_fractions(self.af, self.ar)
        # Fachinotti eq. 15 prefactor, with ρc so the result is kelvin.
        self.pref = (3.0 * math.sqrt(3.0) * self.Q_W) / (math.pi * math.sqrt(math.pi) * self.rho_cp)
        self.v = 0.0
        self._tau = None
        self._w = None

    def bind_speed(self, v_scan_m_s: float) -> "GoldakField":
        self.v = max(1e-6, float(v_scan_m_s))
        self._build(WAKE_LENGTH_M)
        return self

    def _build(self, wake_m: float) -> None:
        """Quadrature nodes for points down to x = -wake_m behind the source (see module header)."""
        v, alpha = self.v, self.alpha
        a_min = min(self.af, self.ar, self.b, self.c)
        a_max = max(self.af, self.ar, self.b, self.c)
        # Near-source scales: diffusion over the source (a^2/12 alpha) and advection over it (a/v).
        u0 = 0.1 * math.sqrt(min(a_min * a_min / (12.0 * alpha), a_min / v))
        # tau_end: the advective Gaussian exp(-3 (x + v tau)^2 / sf) of the farthest wake point has
        # decayed by exp(-E_CUT), and the near-field diffusive tail exp(-v^2 tau / 4 alpha) likewise.
        tau_wake = wake_m / v
        tau_end = max((wake_m + math.sqrt(4.0 * _E_CUT * alpha * tau_wake + _E_CUT * a_max * a_max / 3.0)) / v,
                      4.0 * _E_CUT * alpha / (v * v))
        du = _PULSE_PANEL_SIGMAS * math.sqrt(alpha / 2.0) / v
        u, w = _u_panels(u0, du, math.sqrt(tau_end))
        # tau = u^2, dtau = 2 u du; u > 0 at every node (no tau = 0 singularity in the erf argument).
        self._tau = np.maximum(u * u, 1e-10)
        self._w = w * 2.0 * u
        self._wake_m = wake_m

    def temperature_C(self, x_m, y_m, z_m):
        if self._tau is None:
            raise RuntimeError("GoldakField.bind_speed() must be called first.")
        x = np.asarray(x_m, dtype=np.float64)
        y = np.asarray(y_m, dtype=np.float64)
        z = np.asarray(np.abs(z_m), dtype=np.float64)
        scalar = x.ndim == 0 and y.ndim == 0 and z.ndim == 0
        x, y, z = np.broadcast_arrays(np.atleast_1d(x), np.atleast_1d(y), np.atleast_1d(z))
        shape = x.shape
        x = x.reshape(-1)
        y = y.reshape(-1)
        z = z.reshape(-1)
        x_min = float(x.min())
        if -x_min > self._wake_m:
            # Adaptive wake window: a point farther behind the source than the quadrature was sized
            # for gets a wider quadrature (never a silently truncated one); the window only grows.
            self._build(1.25 * -x_min)

        tau = self._tau[:, None]
        w = self._w[:, None]
        s12 = 12.0 * self.alpha * tau
        sa = s12 + self.b ** 2
        sb = s12 + self.c ** 2
        sf = s12 + self.af ** 2
        sr = s12 + self.ar ** 2
        # Moving-frame: torch at 0 now; past location → x + v τ (wake at x < 0).
        xh = x[None, :] + self.v * tau
        expo = -3.0 * (y[None, :] ** 2) / sa - 3.0 * (z[None, :] ** 2) / sb
        expo = np.clip(expo, -60.0, 20.0)
        base = np.exp(expo) / (np.sqrt(sa) * np.sqrt(sb))

        Af = np.exp(np.clip(-3.0 * (xh ** 2) / sf, -60.0, 20.0)) / np.sqrt(sf)
        Ar = np.exp(np.clip(-3.0 * (xh ** 2) / sr, -60.0, 20.0)) / np.sqrt(sr)
        sqrt_kt = np.sqrt(self.alpha * tau)
        Bf = _erf((self.af / 2.0) * xh / (sqrt_kt * np.sqrt(sf)))
        Br = _erf((self.ar / 2.0) * xh / (sqrt_kt * np.sqrt(sr)))
        split = self.fr * Ar * (1.0 - Br) + self.ff * Af * (1.0 + Bf)
        integ = np.sum(w * base * split, axis=0)
        T = self.T0_C + self.pref * integ
        T = T.reshape(shape)
        if scalar:
            return float(T.reshape(-1)[0])
        return T
