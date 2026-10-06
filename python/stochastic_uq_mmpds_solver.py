#!/usr/bin/env python3
"""
MetalliX Stochastic Uncertainty Quantification (UQ) & Aerospace MMPDS Allowables Solver
Author: MetalliX Computational Materials Science HPC Engine

Performs high-dimensional forward Monte Carlo uncertainty propagation,
variance-based sensitivity estimates, and approximate A/B-style statistical
screening bounds. Simulated populations are not qualification evidence.
"""

import sys
import json
import math
import time
import random
from statistics import NormalDist

import numpy as np

import alloy_data_kinetics_uq_fatigue as _uq_data
import alloy_registry
import physical_constants

# Phase 6a structural migration (design step (a)): constants come from
# physical_constants / alloy_data_kinetics_uq_fatigue with unchanged values.
# Phase 6a value step (b): exact SI 2019 R = N_A*k (was the 4-significant-figure 8.314).
R_GAS = physical_constants.GAS_CONSTANT_R.value  # J/(mol*K), exact
ZERO_C_K = physical_constants.ZERO_CELSIUS_K.value

_STD_NORMAL = NormalDist()

# Outputs that depended on invented laws are reported as unavailable (same shape as the ICME solver's
# ultimateTensileStrength_UTS_status / fractureToughness_K1c_status).
UTS_UNAVAILABLE_STATUS = "unavailable: no sourced UTS / work-hardening law (the former UTS = YS*(1+2.15n) was invented); see the ICME solver"
K1C_UNAVAILABLE_STATUS = "unavailable: no sourced fracture-toughness law (the former K_Ic clamp of 18-160 MPa*sqrt(m) was invented); see the ICME solver"
CRITICAL_FLAW_UNAVAILABLE_STATUS = "unavailable: critical flaw size needs a sourced K_Ic; the former estimate was dimensionally unsupported"

def norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def norm_ppf(p: float) -> float:
    """Standard normal quantile function (inverse CDF; stdlib statistics.NormalDist, ~1e-15).

    Replaces the earlier Beasley-Springer-Moro style rational approximation, whose central
    denominator had a sign error (p = 0.10 gave -0.068 instead of -1.2816, non-monotone, and
    transformed Sobol draws had sigma 0.776) and whose tail polynomial was truncated (0.09
    error at p = 1e-6). Out-of-range p is clamped to +/-8 as before.

    Accuracy: max abs error < 1e-14 against scipy.special.ndtri over p in (1e-6, 1 - 1e-6)
    (test_stochastic_uq_evidence.NormalQuantileTests).

    The +/-8 clamp is not monotone with inv_cdf below p = 6.2e-16 (and above 1 - 1.1e-16),
    where |z| > 8 (inv_cdf(1e-20) = -9.26 < inv_cdf(0) -> -8). The solver cannot reach that
    range: Sobol points lie in [1.16e-10, 1 - 1.16e-10] (|z| <= 6.34) and the reliability index
    argument is pre-clamped to [1e-6, 1 - 1e-6].
    """
    if p <= 0.0:
        return -8.0
    if p >= 1.0:
        return 8.0
    return _STD_NORMAL.inv_cdf(p)

# Wichura AS241 (PPND16) coefficients: the same rational approximation as CPython's
# statistics.NormalDist.inv_cdf, evaluated here with the identical Horner order so that the
# vectorised quantile agrees with norm_ppf to the last bit or two (checked in
# test_stochastic_uq_vectorized_parity).
_AS241_CENTRAL_NUM = (2.50908_09287_30122_6727e+3, 3.34305_75583_58812_8105e+4, 6.72657_70927_00870_0853e+4,
                      4.59219_53931_54987_1457e+4, 1.37316_93765_50946_1125e+4, 1.97159_09503_06551_4427e+3,
                      1.33141_66789_17843_7745e+2, 3.38713_28727_96366_6080e+0)
_AS241_CENTRAL_DEN = (5.22649_52788_52854_5610e+3, 2.87290_85735_72194_2674e+4, 3.93078_95800_09271_0610e+4,
                      2.12137_94301_58659_5867e+4, 5.39419_60214_24751_1077e+3, 6.87187_00749_20579_0830e+2,
                      4.23133_30701_60091_1252e+1, 1.0)
_AS241_NEAR_NUM = (7.74545_01427_83414_07640e-4, 2.27238_44989_26918_45833e-2, 2.41780_72517_74506_11770e-1,
                   1.27045_82524_52368_38258e+0, 3.64784_83247_63204_60504e+0, 5.76949_72214_60691_40550e+0,
                   4.63033_78461_56545_29590e+0, 1.42343_71107_49683_57734e+0)
_AS241_NEAR_DEN = (1.05075_00716_44416_84324e-9, 5.47593_80849_95344_94600e-4, 1.51986_66563_61645_71966e-2,
                   1.48103_97642_74800_74590e-1, 6.89767_33498_51000_04550e-1, 1.67638_48301_83803_84940e+0,
                   2.05319_16266_37758_82187e+0, 1.0)
_AS241_FAR_NUM = (2.01033_43992_92288_13265e-7, 2.71155_55687_43487_57815e-5, 1.24266_09473_88078_43860e-3,
                  2.65321_89526_57612_30930e-2, 2.96560_57182_85048_91230e-1, 1.78482_65399_17291_33580e+0,
                  5.46378_49111_64114_36990e+0, 6.65790_46435_01103_77720e+0)
_AS241_FAR_DEN = (2.04426_31033_89939_78564e-15, 1.42151_17583_16445_88870e-7, 1.84631_83175_10054_68180e-5,
                  7.86869_13114_56132_59100e-4, 1.48753_61290_85061_48525e-2, 1.36929_88092_27358_05310e-1,
                  5.99832_20655_58879_37690e-1, 1.0)

def _horner(coeffs, r):
    acc = coeffs[0] * r + coeffs[1]
    for c in coeffs[2:]:
        acc = acc * r + c
    return acc

def norm_ppf_array(p):
    """Vectorised norm_ppf: same AS241 evaluation and the same +/-8 clamp, elementwise."""
    p = np.asarray(p, dtype=np.float64)
    out = np.empty(p.shape, dtype=np.float64)
    low = p <= 0.0
    high = p >= 1.0
    interior = ~(low | high)
    out[low] = -8.0
    out[high] = 8.0
    pi = p[interior]
    q = pi - 0.5
    x = np.empty(pi.shape, dtype=np.float64)
    central = np.abs(q) <= 0.425
    if central.any():
        qc = q[central]
        r = 0.180625 - qc * qc
        num = _horner(_AS241_CENTRAL_NUM[:-1], r) * r + _AS241_CENTRAL_NUM[-1]
        num = num * qc
        den = _horner(_AS241_CENTRAL_DEN[:-1], r) * r + _AS241_CENTRAL_DEN[-1]
        x[central] = num / den
    tail = ~central
    if tail.any():
        qt = q[tail]
        pt = pi[tail]
        r = np.sqrt(-np.log(np.where(qt <= 0.0, pt, 1.0 - pt)))
        xt = np.empty(r.shape, dtype=np.float64)
        near = r <= 5.0
        if near.any():
            rn = r[near] - 1.6
            xt[near] = _horner(_AS241_NEAR_NUM[:-1], rn) * rn + _AS241_NEAR_NUM[-1]
            xt[near] = xt[near] / (_horner(_AS241_NEAR_DEN[:-1], rn) * rn + _AS241_NEAR_DEN[-1])
        far = ~near
        if far.any():
            rf = r[far] - 5.0
            xt[far] = (_horner(_AS241_FAR_NUM[:-1], rf) * rf + _AS241_FAR_NUM[-1]) / (
                _horner(_AS241_FAR_DEN[:-1], rf) * rf + _AS241_FAR_DEN[-1])
        xt = np.where(qt < 0.0, -xt, xt)
        x[tail] = xt
    out[interior] = x
    return out

def _require_finite(*arrays):
    """Reject non-finite populations the way the scalar code did (math.exp/pow raised OverflowError).

    NumPy silently produces inf/nan where math.exp(1e308)-style calls raised; a population with
    non-finite draws or outputs would otherwise be reported as a successful run with
    Infinity/NaN statistics.
    """
    for arr in arrays:
        if not np.all(np.isfinite(arr)):
            raise OverflowError("math range error")

def _pmax(a, b):
    """Elementwise Python max(a, b): b only if b > a (keeps the NaN/tie behaviour of the scalar code)."""
    return np.where(b > a, b, a)

def _pmin(a, b):
    """Elementwise Python min(a, b): b only if b < a."""
    return np.where(b < a, b, a)

def compute_mmpds_k_factors(n: int):
    """
    Approximate one-sided normal tolerance factors targeting population fractions
    0.99 and 0.90 at nominal confidence 0.95. This is not MMPDS qualification.
    """
    if n < 3:
        return 10.0, 8.0
    
    # Approximate one-sided normal tolerance factors
    # k = (z_p + sqrt(z_p^2 - a*b)) / a where a = 1 - z_gamma^2/(2*(n-1)), b = z_p^2 - z_gamma^2/n
    z_gamma = 1.6448536  # 95% confidence
    
    # A-Basis: p = 0.99 -> z_p = 2.3263479
    z_a = 2.3263479
    denom_a = 1.0 - (z_gamma**2) / (2.0 * (n - 1.0))
    if denom_a > 0:
        disc_a = max(0.0, z_a**2 - denom_a * (z_a**2 - (z_gamma**2) / n))
        k_a = (z_a + math.sqrt(disc_a)) / denom_a
    else:
        k_a = z_a + z_gamma * math.sqrt(1.0 / n + (z_a**2) / (2.0 * (n - 1.0)))

    # B-Basis: p = 0.90 -> z_p = 1.2815516
    z_b = 1.2815516
    denom_b = 1.0 - (z_gamma**2) / (2.0 * (n - 1.0))
    if denom_b > 0:
        disc_b = max(0.0, z_b**2 - denom_b * (z_b**2 - (z_gamma**2) / n))
        k_b = (z_b + math.sqrt(disc_b)) / denom_b
    else:
        k_b = z_b + z_gamma * math.sqrt(1.0 / n + (z_b**2) / (2.0 * (n - 1.0)))

    return round(k_a, 3), round(k_b, 3)

# Limit state of the reliability block: g = Rp0.2 - YIELD_DESIGN_FACTOR * max(50 MPa, service stress).
# Pf = P(g < 0) is therefore the probability that the model yield strength falls below 1.5x the service
# stress (an exceedance probability at a design factor), not the probability of yielding at the service stress.
YIELD_DESIGN_FACTOR = 1.5
# Generalized reliability index (Ditlevsen 1979): beta_G = Phi^-1(1 - Pf), from the sampled failure count.
# It is NOT the Hasofer-Lind index (Hasofer & Lind 1974: minimum distance from the origin to the limit-state
# surface in standard-normal space, a FORM design-point search), which this solver does not compute; the two
# agree only for a limit state linear in standard-normal variables, and this one is not (EUQ-11).
RELIABILITY_INDEX_METHOD = (
    "Generalized reliability index beta_G = Phi^-1(1 - Pf) (Ditlevsen 1979) from the sampled failure count; "
    "not the Hasofer-Lind / FORM index (no design-point search is run)"
)
LIMIT_STATE_TEXT = "g = Rp0.2 - 1.5 * max(50 MPa, service stress); Pf = P(g < 0) at design factor 1.5"
CENSORED_BOUND_METHOD = (
    "No sampled point (or every point) failed, so Pf and beta_G are censored: the bound uses the rule of three "
    "(95 %, Pf < 3/N or Pf > 1 - 3/N), which assumes independent samples; the QMC points are not independent, so "
    "the bound is approximate"
)


def generalized_reliability_index(failures: int, n: int) -> dict:
    """beta_G and Pf from ``failures`` of ``n`` samples; censored (null + one-sided bound) at 0 or n failures.

    The former output clamped Pf to [1e-6, 1 - 1e-6] and reported +/-4.75 as if it were an estimate.
    """
    pf = failures / n
    if 0 < failures < n:
        return {"pf": pf, "beta": norm_ppf(1.0 - pf), "status": "estimated", "bound": None}
    p3 = min(1.0, 3.0 / n)
    if failures == 0:
        bound = {"type": "lower", "beta": norm_ppf(1.0 - p3) if p3 < 1.0 else None, "pfUpper": p3}
        return {"pf": 0.0, "beta": None, "status": "censored_no_failures", "bound": bound}
    bound = {"type": "upper", "beta": norm_ppf(p3) if p3 < 1.0 else None, "pfLower": 1.0 - p3}
    return {"pf": 1.0, "beta": None, "status": "censored_all_failures", "bound": bound}


class SobolSequenceGenerator:
    """
    Antonov-Saleev Gray code Quasi-Monte Carlo Sobol Sequence Generator (up to 32 dimensions).
    Direction numbers: Joe & Kuo, SIAM J. Sci. Comput. 30 (2008) 2635, file new-joe-kuo-6.21201
    (dimension 1 is the van der Corput sequence, dimensions 2-32 are its rows d = 2..32), with an
    optional random digital shift. This implementation skips the origin; balanced-net guarantees are
    not claimed for arbitrary sample counts.

    EUQ-4: the former local table was not a Joe-Kuo set: its dimension 20 used (s=6, a=28),
    x^6+x^5+x^4+x^3+1, which is not primitive over GF(2) (the order of x is 15, not 63), dimensions
    21-32 were shifted one row, and the initial m values from dimension 13 on were not Joe-Kuo's.
    That gave degenerate 2-D projections (1024 unscrambled points of dimensions 22/28 covered 65 of
    1024 grid cells, corr(dim 21, dim 23) = 0.75) and correlated Saltelli A/B columns.
    Rows are (s, a, [m_1..m_s]); bit k of a (from the top, k = 1..s-1) is the polynomial coefficient a_k.
    """
    POLY = [
        (1, 0, [1]),                            # dim 1 (van der Corput; m_i = 1 for all i)
        (1, 0, [1]),                            # dim 2
        (2, 1, [1, 3]),                         # dim 3
        (3, 1, [1, 3, 1]),                      # dim 4
        (3, 2, [1, 1, 1]),                      # dim 5
        (4, 1, [1, 1, 3, 3]),                   # dim 6
        (4, 4, [1, 3, 5, 13]),                  # dim 7
        (5, 2, [1, 1, 5, 5, 17]),               # dim 8
        (5, 4, [1, 1, 5, 5, 5]),                # dim 9
        (5, 7, [1, 1, 7, 11, 19]),              # dim 10
        (5, 11, [1, 1, 5, 1, 1]),               # dim 11
        (5, 13, [1, 1, 1, 3, 11]),              # dim 12
        (5, 14, [1, 3, 5, 5, 31]),              # dim 13
        (6, 1, [1, 3, 3, 9, 7, 49]),            # dim 14
        (6, 13, [1, 1, 1, 15, 21, 21]),         # dim 15
        (6, 16, [1, 3, 1, 13, 27, 49]),         # dim 16
        (6, 19, [1, 1, 1, 15, 7, 5]),           # dim 17
        (6, 22, [1, 3, 1, 15, 13, 25]),         # dim 18
        (6, 25, [1, 1, 5, 5, 19, 61]),          # dim 19
        (7, 1, [1, 3, 7, 11, 23, 15, 103]),     # dim 20
        (7, 4, [1, 3, 7, 13, 13, 15, 69]),      # dim 21
        (7, 7, [1, 1, 3, 13, 7, 35, 63]),       # dim 22
        (7, 8, [1, 3, 5, 9, 1, 25, 53]),        # dim 23
        (7, 14, [1, 3, 1, 13, 9, 35, 107]),     # dim 24
        (7, 19, [1, 3, 1, 5, 27, 61, 31]),      # dim 25
        (7, 21, [1, 1, 5, 11, 19, 41, 61]),     # dim 26
        (7, 28, [1, 3, 5, 3, 3, 13, 69]),       # dim 27
        (7, 31, [1, 1, 7, 13, 1, 19, 1]),       # dim 28
        (7, 32, [1, 3, 7, 5, 13, 19, 59]),      # dim 29
        (7, 37, [1, 1, 3, 9, 25, 29, 41]),      # dim 30
        (7, 41, [1, 3, 5, 13, 23, 1, 55]),      # dim 31
        (7, 42, [1, 3, 7, 3, 13, 59, 17]),      # dim 32
    ]

    def __init__(self, dimension: int, scramble: bool = True, seed: int = 42):
        if not 1 <= dimension <= len(self.POLY):
            raise ValueError("Sobol sampling supports 1 to 32 dimensions; use pseudo_mc for more inputs")
        self.d = dimension
        self.scramble = scramble
        self.seed = seed
        self.L = 32
        self.two_pow_L = float(1 << self.L)
        self._init_direction_numbers()
        self.reset()

    def _init_direction_numbers(self):
        self.V = []
        for d in range(self.d):
            s, a, init_m = self.POLY[d]
            m = [0] * (self.L + 1)
            for i in range(1, s + 1):
                m[i] = init_m[i - 1] if (i - 1) < len(init_m) else 1
            if d == 0:
                for i in range(1, self.L + 1):
                    m[i] = 1
            else:
                for i in range(s + 1, self.L + 1):
                    new_m = m[i - s] ^ (m[i - s] << s)
                    for k in range(1, s):
                        if (a >> (s - 1 - k)) & 1:
                            new_m ^= (m[i - k] << k)
                    m[i] = new_m
            v_dim = [(m[i] << (self.L - i)) & 0xFFFFFFFF for i in range(1, self.L + 1)]
            self.V.append(v_dim)

        if self.scramble:
            rng = random.Random(self.seed)
            self.shift = [rng.getrandbits(self.L) for _ in range(self.d)]
        else:
            self.shift = [0] * self.d

    def reset(self):
        self.X = [0] * self.d
        self.count = 0

    def generate_array(self, n: int):
        """Next n points as an (n, d) float64 array (vectorised Antonov-Saleev Gray-code update).

        Point i XORs direction number V[d][c_i] into the running state, c_i = trailing ones of i, so
        the states are an XOR prefix-scan; every value is an exact integer below 2**32, hence the
        points are bit-identical to the sequential loop this replaced.
        """
        if n <= 0:
            return np.empty((0, self.d), dtype=np.float64)
        idx = np.arange(self.count, self.count + n, dtype=np.int64) + 1
        lowest = idx & -idx  # lowest set bit of i + 1 == 2**(trailing ones of i)
        c = np.minimum(np.frexp(lowest.astype(np.float64))[1] - 1, self.L - 1)
        v_all = np.asarray(self.V, dtype=np.uint64)  # (d, L)
        state = np.bitwise_xor.accumulate(v_all[:, c], axis=1)  # (d, n)
        state ^= np.asarray(self.X, dtype=np.uint64)[:, None]
        self.X = [int(v) for v in state[:, -1]]
        val = state ^ np.asarray(self.shift, dtype=np.uint64)[:, None]
        # Map strictly to open interval (0, 1) to avoid infinite probit boundaries
        pts = (val.astype(np.float64) + 0.5) / self.two_pow_L
        self.count += n
        return np.ascontiguousarray(pts.T)

    def generate(self, n: int):
        return self.generate_array(n).tolist()

def compute_centered_l2_discrepancy(points, max_eval: int = 150) -> float:
    """
    Computes Hickernell (1998) centered L2 star discrepancy CD_2(P)
    to rigorously benchmark point cloud uniformity on the unit hypercube.

    Vectorised with NumPy: the per-dimension products and the left-to-right accumulation order
    of the original double loop are kept, so the value is unchanged.
    """
    N = len(points)
    if N == 0:
        return 0.0
    sub = np.asarray(points[:max_eval], dtype=np.float64)
    M = sub.shape[0]
    d = sub.shape[1]

    term1 = (13.0 / 12.0) ** d

    z = np.abs(sub - 0.5)
    prod2 = np.ones(M)
    for k in range(d):
        prod2 *= (1.0 + 0.5 * z[:, k] - 0.5 * (z[:, k] ** 2))
    sum_term2 = float(np.cumsum(prod2)[-1])  # sequential adds, as the original `+=`
    term2 = (2.0 / M) * sum_term2

    prod3 = np.ones((M, M))
    for k in range(d):
        col = sub[:, k]
        zi = z[:, k][:, None]
        zj = z[:, k][None, :]
        zdiff = np.abs(col[:, None] - col[None, :])
        prod3 *= (1.0 + 0.5 * zi + 0.5 * zj - 0.5 * zdiff)
    sum_term3 = float(np.cumsum(prod3.ravel())[-1])  # row-major == original i-outer, j-inner order
    term3 = (1.0 / (M * M)) * sum_term3

    cd2_sq = max(0.0, term1 - term2 + term3)
    return round(math.sqrt(cd2_sq), 6)

def solve_single_realization(
    base_metal: str,
    comp: dict,
    cooling_rate: float,
    aging_temp_C: float,
    aging_time_h: float,
    service_stress_MPa: float
) -> dict:
    """Evaluates the illustrative strength model for one stochastic state draw.

    Only yield strength and elongation are returned. UTS, fracture toughness and critical flaw size
    were removed: their laws (UTS = YS*(1 + 2.15 n), K_Ic clamped to 18-160, a_c from that K_Ic) were
    invented, not sourced (the ICME solver reports the same quantities as unavailable).
    """
    # 1. Base Metal Lattice & Elasticity (alloy_data_kinetics_uq_fatigue; same values,
    # same legacy fallback: a base metal other than Ni/Fe/Ti uses the Al constants)
    lattice = _uq_data.uq_lattice_constants(base_metal)
    a0 = lattice["a0"]
    b_nm = lattice["b_nm"]
    C11, C12, C44 = lattice["C11"], lattice["C12"], lattice["C44"]
    taylor_M = lattice["taylor_M"]
    sigma_0 = lattice["sigma_0"]
    k_hp = lattice["k_hp"]  # MPa*sqrt(um)

    # VRH shear modulus
    G_Voigt = (C11 - C12 + 3.0 * C44) / 5.0
    G_Reuss = 5.0 * (C11 - C12) * C44 / max(1.0, (4.0 * C44 + 3.0 * (C11 - C12)))
    G_GPa = (G_Voigt + G_Reuss) / 2.0

    # 2. Solid Solution Strengthening (Labusch)
    delta_sigma_ss = 0.0
    # solute potency coefficients
    misfit_weights = _uq_data.UQ_SOLUTE_POTENCY
    for el, wt in comp.items():
        wt_val = max(0.0, wt)
        potency = misfit_weights.get(el, _uq_data.UQ_DEFAULT_SOLUTE_POTENCY)
        delta_sigma_ss += potency * (wt_val ** 0.67)

    # 3. Solidification & Grain Size (Kurz-Fisher / Hunt)
    # SDAS / grain size d (um) ~ K * (cooling_rate)^(-0.33)
    cooling_rate_eff = max(0.1, cooling_rate)
    d_grain_um = max(0.5, 45.0 * (cooling_rate_eff ** -0.32))
    delta_sigma_hp = k_hp / math.sqrt(d_grain_um)

    # 4. Dislocation Forest Hardening
    # Dislocation density rho increases with cooling thermal stress / strain
    rho_m2 = max(1e12, 1e13 * (cooling_rate_eff ** 0.22))
    alpha_disloc = 0.35
    delta_sigma_disloc = taylor_M * alpha_disloc * (G_GPa * 1000.0) * (b_nm * 1e-3) * math.sqrt(rho_m2) * 1e-6

    # 5. Precipitation Kinetics (LSW Ostwald Ripening + Orowan Looping)
    # Mean radius r_nm ~ (K_0 * exp(-Q/RT) * t)^(1/3)
    T_K = aging_temp_C + ZERO_C_K
    Q_diff = _uq_data.UQ_PRECIPITATION_Q_J_MOL  # J/mol
    R_gas = R_GAS
    arrhenius = math.exp(-min(45.0, Q_diff / (R_gas * max(300.0, T_K))))
    r_nm = max(0.8, 18.0 * ((arrhenius * 1e8 * max(0.1, aging_time_h)) ** 0.333))
    
    # Superalloy / Al volume fraction estimated from key precipitating solutes (Nb, Ti, Al)
    f_pct = min(28.0, (comp.get("Nb", 0.0) * 2.2 + comp.get("Ti", 0.0) * 3.5 + comp.get("Al", 0.0) * 4.0 + comp.get("Mg", 0.0) * 3.0))
    f_vol = max(0.005, f_pct / 100.0)
    lambda_spacing_nm = max(2.0, (math.sqrt(math.pi / max(0.001, f_vol)) - 2.0) * r_nm)

    # Shearing vs Orowan crossover
    sigma_shear = (taylor_M * (G_GPa * 1000.0) * (b_nm / 1.0)) * math.sqrt(max(0.001, f_vol * r_nm / 1.5)) * 0.12
    sigma_orowan = (taylor_M * 0.8 * (G_GPa * 1000.0) * b_nm) / max(5.0, lambda_spacing_nm) * math.log(max(2.0, 2.0 * r_nm / b_nm)) * 0.18
    delta_sigma_ppt = min(sigma_shear, sigma_orowan)

    # 6. Generalized Power-Law Superposition (q = 1.4)
    q_pow = 1.4
    coupled_term = (delta_sigma_disloc ** q_pow + delta_sigma_ppt ** q_pow) ** (1.0 / q_pow)
    sigma_yield_MPa = sigma_0 + delta_sigma_ss + delta_sigma_hp + coupled_term

    # 7. Strain-hardening exponent and elongation (illustrative; feeds elongation only)
    n_work_hardening = max(0.05, min(0.35, 0.42 - 0.00022 * sigma_yield_MPa))
    elongation_pct = max(3.0, min(50.0, 3200.0 / (sigma_yield_MPa ** 0.82) * (1.0 + 1.5 * n_work_hardening)))

    # Limit state margin (yield only)
    applied_stress = max(50.0, service_stress_MPa)
    margin_yield_MPa = sigma_yield_MPa - applied_stress * YIELD_DESIGN_FACTOR

    return {
        "yield_MPa": sigma_yield_MPa,
        "elongation_pct": elongation_pct,
        "margin_yield_MPa": margin_yield_MPa,
        "delta_sigma_ss": delta_sigma_ss,
        "delta_sigma_hp": delta_sigma_hp,
        "delta_sigma_ppt": delta_sigma_ppt,
        "grain_size_um": d_grain_um,
        "applied_stress": applied_stress
    }

def solve_realizations_vec(
    base_metal: str,
    comp: dict,
    cooling_rate,
    aging_temp_C,
    aging_time_h,
    service_stress_MPa
) -> dict:
    """Vectorised solve_single_realization: same physics, same operation order, arrays in/out.

    comp maps element -> float64 array (or float); the other arguments are float64 arrays of the
    same length. Python max/min are emulated with _pmax/_pmin so ties and NaN behave as before.
    solve_single_realization (scalar) stays the readable reference; test_stochastic_uq_vectorized_parity
    compares the two.
    """
    lattice = _uq_data.uq_lattice_constants(base_metal)
    b_nm = lattice["b_nm"]
    C11, C12, C44 = lattice["C11"], lattice["C12"], lattice["C44"]
    taylor_M = lattice["taylor_M"]
    sigma_0 = lattice["sigma_0"]
    k_hp = lattice["k_hp"]  # MPa*sqrt(um)

    # VRH shear modulus (scalar)
    G_Voigt = (C11 - C12 + 3.0 * C44) / 5.0
    G_Reuss = 5.0 * (C11 - C12) * C44 / max(1.0, (4.0 * C44 + 3.0 * (C11 - C12)))
    G_GPa = (G_Voigt + G_Reuss) / 2.0

    # Solid solution strengthening (Labusch), element order as in comp
    delta_sigma_ss = 0.0
    misfit_weights = _uq_data.UQ_SOLUTE_POTENCY
    for el, wt in comp.items():
        wt_val = _pmax(0.0, wt)
        potency = misfit_weights.get(el, _uq_data.UQ_DEFAULT_SOLUTE_POTENCY)
        delta_sigma_ss = delta_sigma_ss + potency * (wt_val ** 0.67)

    # Grain size and Hall-Petch
    cooling_rate_eff = _pmax(0.1, cooling_rate)
    d_grain_um = _pmax(0.5, 45.0 * (cooling_rate_eff ** -0.32))
    delta_sigma_hp = k_hp / np.sqrt(d_grain_um)

    # Dislocation forest hardening
    rho_m2 = _pmax(1e12, 1e13 * (cooling_rate_eff ** 0.22))
    alpha_disloc = 0.35
    delta_sigma_disloc = taylor_M * alpha_disloc * (G_GPa * 1000.0) * (b_nm * 1e-3) * np.sqrt(rho_m2) * 1e-6

    # Precipitation (LSW ripening + shearing/Orowan)
    T_K = aging_temp_C + ZERO_C_K
    Q_diff = _uq_data.UQ_PRECIPITATION_Q_J_MOL  # J/mol
    R_gas = R_GAS
    arrhenius = np.exp(-_pmin(45.0, Q_diff / (R_gas * _pmax(300.0, T_K))))
    r_nm = _pmax(0.8, 18.0 * ((arrhenius * 1e8 * _pmax(0.1, aging_time_h)) ** 0.333))

    f_pct = _pmin(28.0, (comp.get("Nb", 0.0) * 2.2 + comp.get("Ti", 0.0) * 3.5 + comp.get("Al", 0.0) * 4.0 + comp.get("Mg", 0.0) * 3.0))
    f_vol = _pmax(0.005, f_pct / 100.0)
    lambda_spacing_nm = _pmax(2.0, (np.sqrt(math.pi / _pmax(0.001, f_vol)) - 2.0) * r_nm)

    sigma_shear = (taylor_M * (G_GPa * 1000.0) * (b_nm / 1.0)) * np.sqrt(_pmax(0.001, f_vol * r_nm / 1.5)) * 0.12
    sigma_orowan = (taylor_M * 0.8 * (G_GPa * 1000.0) * b_nm) / _pmax(5.0, lambda_spacing_nm) * np.log(_pmax(2.0, 2.0 * r_nm / b_nm)) * 0.18
    delta_sigma_ppt = _pmin(sigma_shear, sigma_orowan)

    # Generalized power-law superposition (q = 1.4)
    q_pow = 1.4
    coupled_term = (delta_sigma_disloc ** q_pow + delta_sigma_ppt ** q_pow) ** (1.0 / q_pow)
    sigma_yield_MPa = sigma_0 + delta_sigma_ss + delta_sigma_hp + coupled_term

    # Strain-hardening exponent and elongation (illustrative; feeds elongation only)
    n_work_hardening = _pmax(0.05, _pmin(0.35, 0.42 - 0.00022 * sigma_yield_MPa))
    elongation_pct = _pmax(3.0, _pmin(50.0, 3200.0 / (sigma_yield_MPa ** 0.82) * (1.0 + 1.5 * n_work_hardening)))

    applied_stress = _pmax(50.0, service_stress_MPa)
    margin_yield_MPa = sigma_yield_MPa - applied_stress * YIELD_DESIGN_FACTOR

    _require_finite(sigma_yield_MPa, elongation_pct, margin_yield_MPa, delta_sigma_ss, delta_sigma_hp,
                    delta_sigma_ppt, d_grain_um, applied_stress)
    return {
        "yield_MPa": sigma_yield_MPa,
        "elongation_pct": elongation_pct,
        "margin_yield_MPa": margin_yield_MPa,
        "delta_sigma_ss": delta_sigma_ss,
        "delta_sigma_hp": delta_sigma_hp,
        "delta_sigma_ppt": delta_sigma_ppt,
        "grain_size_um": d_grain_um,
        "applied_stress": applied_stress
    }

def solve_stochastic_uq(params: dict) -> dict:
    t0 = time.time()

    alloy_name = params.get("alloyName", _uq_data.UQ_DEFAULT_ALLOY_NAME)
    base_metal = params.get("baseMetal", _uq_data.UQ_DEFAULT_BASE_METAL)
    standard_spec = params.get("standardSpec", _uq_data.UQ_DEFAULT_STANDARD_SPEC)
    
    # Sampling configuration: Sobol QMC vs Pseudo-Random MC
    sampling_method = params.get("samplingMethod", "sobol_qmc")
    scramble = bool(params.get("scramble", True))
    seed = int(params.get("seed", 42))

    # Nominal chemistry & tolerances (± delta wt%)
    nominal_comp = params.get("composition_wt", _uq_data.uq_default_composition_wt())
    comp_tolerances = params.get("composition_tolerances", _uq_data.uq_default_composition_tolerances())

    # Process variables
    cooling_rate_nominal = float(params.get("coolingRate_nominal", 150000.0))
    cooling_rate_cov = float(params.get("coolingRate_cov", 0.25))  # 25% scatter
    
    aging_temp_nominal = float(params.get("agingTemp_nominal", 720.0))
    aging_temp_std = float(params.get("agingTemp_stdDev", 7.5))  # +/- 7.5 C furnace gradient
    
    aging_time_nominal = float(params.get("agingTime_nominal", 8.0))
    aging_time_std = float(params.get("agingTime_stdDev", 0.25))  # +/- 15 min
    
    service_stress_nominal = float(params.get("serviceStress_nominal", 720.0))
    service_stress_cov = float(params.get("serviceStress_cov", 0.08))  # 8% flight load fluctuation

    spec_min_yield = float(params.get("specMinYield_MPa", 1100.0))
    spec_min_uts = float(params.get("specMinUTS_MPa", 1350.0))  # echoed in alloyMetadata only; no UTS is computed
    spec_min_elongation = float(params.get("specMinElongation_pct", 12.0))

    N_samples = int(min(10000, max(500, params.get("mcSamples", 2500))))

    # Deterministic Seed for reproducible scientific comparison across parameter tuning
    random.seed(seed)

    elements = list(nominal_comp.keys())
    E_dim = len(elements)
    # Total Sobol dimensions: Elements + CoolingRate + AgingTemp + AgingTime + ServiceStress + one reserved
    # column (the former flaw-size dimension). It is kept so the sampled points, and with them every
    # yield statistic, stay bit-identical after the flaw-size outputs were removed.
    total_dims = E_dim + 5

    # Log-normal parameters for cooling rate
    sigma_log_cr = math.sqrt(math.log(1.0 + cooling_rate_cov**2))
    mu_log_cr = math.log(cooling_rate_nominal) - 0.5 * (sigma_log_cr**2)

    # -------------------------------------------------------------
    # Low-Discrepancy Sobol Sequence Generation or Pseudo-Random Draw
    # -------------------------------------------------------------
    if sampling_method == "sobol_qmc":
        sobol_gen = SobolSequenceGenerator(dimension=total_dims, scramble=scramble, seed=seed)
        qmc_points = sobol_gen.generate_array(N_samples)
        sobol_cd2 = compute_centered_l2_discrepancy(qmc_points, max_eval=min(150, N_samples))
        
        # Disabled pseudo benchmark comparison to strictly enforce Sobol QMC
        pseudo_cd2 = 0
        discrepancy_reduction_pct = 0.0
    else:
        raise ValueError("Standard Pseudo-Random Monte Carlo is disabled. Enforcing QMC/Sobol determinism. Pass samplingMethod='sobol_qmc'.")

    qmc_points = np.asarray(qmc_points, dtype=np.float64)

    def draw_factors(U):
        """Quantile-transform an (n, >=E_dim+3) matrix of uniforms into physical draws."""
        comp_draw = {}
        for idx_e, el in enumerate(elements):
            nom = nominal_comp[el]
            tol = comp_tolerances.get(el, nom * 0.1)
            std_el = tol / 3.0
            # Sample normal composition and floor at zero (not a truncated-normal CDF)
            comp_draw[el] = _pmax(0.0, nom + norm_ppf_array(U[:, idx_e]) * std_el)
        # Cooling rate (log-normal), aging temperature / time (normal) via exact quantile transforms
        cr = np.exp(mu_log_cr + sigma_log_cr * norm_ppf_array(U[:, E_dim]))
        t_age = _pmax(200.0, aging_temp_nominal + norm_ppf_array(U[:, E_dim + 1]) * aging_temp_std)
        time_age = _pmax(0.2, aging_time_nominal + norm_ppf_array(U[:, E_dim + 2]) * aging_time_std)
        _require_finite(cr, t_age, time_age, *comp_draw.values())
        return comp_draw, cr, t_age, time_age

    comp_s, cr_s, t_age_s, time_age_s = draw_factors(qmc_points)
    # Service stress (normal) is sampled only in the main population.
    service_stress_s = _pmax(50.0, service_stress_nominal + norm_ppf_array(qmc_points[:, E_dim + 3]) * (service_stress_nominal * service_stress_cov))
    _require_finite(service_stress_s)

    res = solve_realizations_vec(
        base_metal=base_metal,
        comp=comp_s,
        cooling_rate=cr_s,
        aging_temp_C=t_age_s,
        aging_time_h=time_age_s,
        service_stress_MPa=service_stress_s
    )
    yield_list = res["yield_MPa"]
    elong_list = res["elongation_pct"]
    margin_yield_list = res["margin_yield_MPa"]

    # Descriptive model statistics; uncertainty of a single QMC run is not estimated.
    def calc_stats(arr, spec_min: float = None):
        sorted_np = np.sort(np.asarray(arr, dtype=np.float64))
        sorted_arr = sorted_np.tolist()
        n = len(sorted_arr)
        # builtin sum over the (sorted) float list: same compensated summation as the scalar loop
        mean_val = sum(sorted_arr) / n
        dev = sorted_np - mean_val
        # the scalar code raised OverflowError from float ** on overflow; do not report inf/nan statistics
        _require_finite(dev, dev ** 2, dev ** 3, dev ** 4)
        var_val = sum((dev ** 2).tolist()) / (n - 1) if sorted_arr[0] != sorted_arr[-1] else 0.0
        std_val = math.sqrt(var_val)
        cov_pct = (std_val / mean_val * 100.0) if mean_val != 0 else 0.0

        # Skewness
        skew = (sum((dev ** 3).tolist()) / n) / max(1e-6, (std_val**3))
        # Kurtosis
        kurt = (sum((dev ** 4).tolist()) / n) / max(1e-6, (std_val**4)) - 3.0

        # Percentiles
        def get_pct(p: float):
            idx = int(p * (n - 1))
            return sorted_arr[max(0, min(n - 1, idx))]

        p01 = get_pct(0.01)
        p025 = get_pct(0.025)
        p10 = get_pct(0.10)
        p25 = get_pct(0.25)
        p50 = get_pct(0.50)
        p75 = get_pct(0.75)
        p90 = get_pct(0.90)
        p975 = get_pct(0.975)
        p99 = get_pct(0.99)

        # Approximate normal A/B-style screening bounds; no experimental qualification
        k_a, k_b = compute_mmpds_k_factors(n)
        a_basis = max(0.0, mean_val - k_a * std_val)
        b_basis = max(0.0, mean_val - k_b * std_val)

        # The iid normal approximation is not a QMC error estimator.
        se_a = se_b = None
        a_ci = b_ci = None
        if sampling_method == "pseudo_mc":
            se_a = std_val * math.sqrt(1.0 / n + (k_a ** 2) / (2.0 * (n - 1.0)))
            se_b = std_val * math.sqrt(1.0 / n + (k_b ** 2) / (2.0 * (n - 1.0)))
            a_ci = [round(max(0.0, a_basis - 1.96 * se_a), 1), round(a_basis + 1.96 * se_a, 1)]
            b_ci = [round(max(0.0, b_basis - 1.96 * se_b), 1), round(b_basis + 1.96 * se_b, 1)]

        # Process capability Cpk against specification minimum
        cpk = None
        conformance_pct = 100.0
        if spec_min is not None:
            cpk = round((mean_val - spec_min) / (3.0 * std_val), 2) if std_val > 0 else None
            conformance_count = n - int(np.searchsorted(sorted_np, spec_min, side='left'))
            conformance_pct = round((conformance_count / n) * 100.0, 2)

        # Histogram Bins generation (25 bins)
        min_v = sorted_arr[0]
        max_v = sorted_arr[-1]
        bin_width = (max_v - min_v) / 25.0 if max_v > min_v else 1.0
        histogram = []
        starts = [min_v + b * bin_width for b in range(25)]
        ends = [b_start + bin_width for b_start in starts]
        lower_idx = np.searchsorted(sorted_np, starts, side='left').tolist()
        upper_idx = np.searchsorted(sorted_np, ends, side='left').tolist()
        cum_idx = np.searchsorted(sorted_np, ends, side='right').tolist()
        for b in range(25):
            b_start = starts[b]
            b_end = ends[b]
            b_center = (b_start + b_end) / 2.0
            if b == 24:
                count = int(np.count_nonzero(((sorted_np >= b_start) & (sorted_np < b_end)) | (sorted_np == max_v)))
            else:
                count = upper_idx[b] - lower_idx[b]
            freq = count / (n * bin_width) if bin_width > 0 else 0.0
            # Fitted normal probability density
            fitted_pdf = (1.0 / (std_val * math.sqrt(2 * math.pi))) * math.exp(-0.5 * ((b_center - mean_val) / std_val)**2) if std_val > 0 else 0.0
            histogram.append({
                "binCenter": round(b_center, 1),
                "binStart": round(b_start, 1),
                "binEnd": round(b_end, 1),
                "count": count,
                "empiricalPdf": round(freq, 6),
                "fittedNormalPdf": round(fitted_pdf, 6),
                "cumulativePct": round((cum_idx[b] / n) * 100.0, 1)
            })

        return {
            "mean": round(mean_val, 1),
            "stdDev": round(std_val, 2),
            "covPct": round(cov_pct, 2),
            "skewness": round(skew, 3),
            "kurtosis": round(kurt, 3),
            "min": round(min_v, 1),
            "max": round(max_v, 1),
            "median_P50": round(p50, 1),
            "P10": round(p10, 1),
            "P90": round(p90, 1),
            "ci95Lower_P2_5": round(p025, 1),
            "ci95Upper_P97_5": round(p975, 1),
            "P01": round(p01, 1),
            "P99": round(p99, 1),
            "mmpds_kA": k_a,
            "mmpds_kB": k_b,
            "aBasisAllowable": round(a_basis, 1),
            "bBasisAllowable": round(b_basis, 1),
            "aBasisConfidenceInterval95": a_ci,
            "bBasisConfidenceInterval95": b_ci,
            "allowableStandardError_A": round(se_a, 2) if se_a is not None else None,
            "allowableStandardError_B": round(se_b, 2) if se_b is not None else None,
            "allowableUncertaintyMethod": "iid-normal delta approximation; simulated population only" if sampling_method == "pseudo_mc" else "unavailable: independent randomized QMC replicates required",
            "cpk": cpk,
            "conformancePct": conformance_pct,
            "histogram": histogram
        }

    yield_stats = calc_stats(yield_list, spec_min_yield)
    elong_stats = calc_stats(elong_list, spec_min_elongation)

    # 4. Reliability & Failure Probability
    failures_yield = int(np.count_nonzero(margin_yield_list < 0))
    reliability = generalized_reliability_index(failures_yield, N_samples)
    pf_yield = reliability["pf"]

    # Sensitivity uses the same supplied chemistry and process distributions.
    # Service stress and flaw size do not enter the model yield-strength output.
    sensitivity_factors = [
        {"param": el + " (Composition)", "key": el, "desc": "Supplied composition tolerance"}
        for el in elements
    ] + [
        {"param": "dT/dt (Cooling Rate)", "key": "CoolingRate", "desc": "Assumed cooling-rate distribution"},
        {"param": "T_age (Aging Temp)", "key": "AgingTemp", "desc": "Assumed furnace temperature scatter"},
        {"param": "t_age (Aging Time)", "key": "AgingTime", "desc": "Assumed hold duration scatter"}
    ]
    M_saltelli = min(350, max(150, N_samples // 6))
    k_factors = len(sensitivity_factors)
    saltelli_sobol = SobolSequenceGenerator(dimension=2 * k_factors, scramble=scramble, seed=seed + 101)
    saltelli_pts = saltelli_sobol.generate_array(M_saltelli)

    def eval_factor_matrix(V):
        """Yield strength for every row of V (rows are factor-uniform vectors)."""
        c_draw, cr_draw, t_age_draw, time_age_draw = draw_factors(V)
        return solve_realizations_vec(
            base_metal, c_draw, cr_draw, t_age_draw, time_age_draw,
            service_stress_nominal
        )["yield_MPa"]

    A_pts = saltelli_pts[:, :k_factors]
    B_pts = saltelli_pts[:, k_factors:]
    y_A = eval_factor_matrix(A_pts)
    y_B = eval_factor_matrix(B_pts)
    combined_y = np.concatenate([y_A, y_B])
    combined_list = combined_y.tolist()
    mean_comb = sum(combined_list) / len(combined_list)
    _require_finite(combined_y, (combined_y - mean_comb) ** 2)
    total_var = sum(((combined_y - mean_comb) ** 2).tolist()) / len(combined_list)
    variance_available = max(combined_list) - min(combined_list) > 1e-12 * max(1.0, abs(mean_comb))
    sensitivity_indices = []
    for idx, item in enumerate(sensitivity_factors):
        vec_AB = A_pts.copy()
        vec_AB[:, idx] = B_pts[:, idx]
        y_AB = eval_factor_matrix(vec_AB)
        _require_finite((y_A - y_AB) ** 2, (y_B - mean_comb) * (y_AB - y_A))
        # Centered Saltelli first-order and Jansen total-order estimators.
        # Raw finite-sample estimates may be negative or exceed one.
        s_first = sum(((y_B - mean_comb) * (y_AB - y_A)).tolist()) / (M_saltelli * total_var) if variance_available else None
        s_total = sum(((y_A - y_AB) ** 2).tolist()) / (2.0 * M_saltelli * total_var) if variance_available else None
        sensitivity_indices.append({
            "parameter": item["param"],
            "description": item["desc"],
            "sobolFirstOrderIndex": round(s_first, 3) if s_first is not None else None,
            "sobolTotalOrderIndex": round(s_total, 3) if s_total is not None else None,
            "interactionIndex": round(s_total - s_first, 3) if s_first is not None else None,
            "varianceContributionPct": round(s_first * 100.0, 1) if s_first is not None else None
        })
    sensitivity_indices.sort(key=lambda row: row["varianceContributionPct"] if row["varianceContributionPct"] is not None else -math.inf, reverse=True)

    # Conformance & Risk Decision
    a_basis_pass = yield_stats["aBasisAllowable"] >= spec_min_yield
    b_basis_pass = yield_stats["bBasisAllowable"] >= spec_min_yield
    cpk_pass = yield_stats["cpk"] is not None and yield_stats["cpk"] >= 1.33

    qualification_status = "Screening only; qualification not assessed"

    compute_time_ms = round((time.time() - t0) * 1000.0, 1)

    return {
        "success": True,
        "engine": "MetalliX Stochastic UQ & Quasi-Monte Carlo Sobol MMPDS-01 Solver",
        "computeTimeMs": compute_time_ms,
        "sampleSizeN": N_samples,
        "samplingMetadata": {
            "samplingMethod": sampling_method,
            "scrambled": scramble if sampling_method == "sobol_qmc" else False,
            "sobolDimensions": total_dims,
            "qmcAccelerationFactor": None,
            "effectiveSampleSize": None,
            "centeredL2Discrepancy": round(sobol_cd2, 6),
            "pseudoDiscrepancyBenchmark": round(pseudo_cd2, 6),
            "discrepancyReductionPct": discrepancy_reduction_pct,
            "varianceReductionRatio": None,
            "theoreticalConvergenceRate": "Not estimated for this run",
            "samplingDescription": "Local Sobol sequence (Joe & Kuo 2008 new-joe-kuo-6.21201 direction numbers) with optional random digital shift." if sampling_method == "sobol_qmc" else "Seeded pseudo-random Monte Carlo sampling.",
            "discrepancySampleSize": min(150, N_samples),
            "diagnosticsLimitations": "Centered L2 discrepancy compares the first 150 points with one seeded pseudo-random set; it is not an estimator error, variance reduction, effective sample size or measured speedup. The local Sobol implementation skips the origin and allows arbitrary sample counts; balanced-net guarantees are not claimed."

        },
        "alloyMetadata": {
            "alloyName": alloy_name,
            "baseMetal": base_metal,
            "standardSpec": standard_spec,
            "specMinYield_MPa": spec_min_yield,
            "specMinUTS_MPa": spec_min_uts,
            "specMinElongation_pct": spec_min_elongation
        },
        "inputUncertainties": {
            "compositionTolerances": comp_tolerances,
            "coolingRate_nominal": cooling_rate_nominal,
            "coolingRate_cov": cooling_rate_cov,
            "agingTemp_nominal": aging_temp_nominal,
            "agingTemp_stdDev": aging_temp_std,
            "agingTime_nominal": aging_time_nominal,
            "agingTime_stdDev": aging_time_std,
            "serviceStress_nominal": service_stress_nominal,
            "serviceStress_cov": service_stress_cov
        },
        "stochasticProperties": {
            "yieldStrength_Rp02": yield_stats,
            "ultimateTensileStrength_UTS": None,
            "ultimateTensileStrength_UTS_status": UTS_UNAVAILABLE_STATUS,
            "elongationPct": elong_stats,
            "fractureToughness_K1c": None,
            "fractureToughness_K1c_status": K1C_UNAVAILABLE_STATUS,
            "criticalFlawSize_ac": None,
            "criticalFlawSize_ac_status": CRITICAL_FLAW_UNAVAILABLE_STATUS
        },
        "sobolSensitivityAnalysis": sensitivity_indices,
        "sensitivityMetadata": {
            "method": "Centered Saltelli first-order / Jansen total-order pick-freeze on a digitally shifted "
                      "Joe-Kuo Sobol design (A and B from one 2k-dimensional sequence)",
            "output": "yieldStrength_Rp02",
            "baseSampleSize": M_saltelli,
            "evaluationCount": M_saltelli * (k_factors + 2),
            "independentInputs": True,
            "indicesNormalized": False,
            "status": "estimated" if variance_available else "unavailable_zero_variance",
            "limitations": "Finite-sample model estimates without confidence intervals. Values are not clipped or normalized and may fall outside [0, 1]. All supplied composition factors and cooling/aging distributions are included; service stress and flaw size do not enter yield strength."
        },
        "aerospaceReliability": {
            "qualificationStatus": qualification_status,
            "limitState": LIMIT_STATE_TEXT,
            "designFactor": YIELD_DESIGN_FACTOR,
            "failureCount": failures_yield,
            "probabilityYieldBelowDesignStress_Pf": pf_yield,
            "generalizedReliabilityIndex": None if reliability["beta"] is None else round(reliability["beta"], 2),
            "generalizedReliabilityIndexStatus": reliability["status"],
            "generalizedReliabilityIndexBound": None if reliability["bound"] is None else {
                k: (round(v, 2) if k == "beta" and v is not None else v) for k, v in reliability["bound"].items()},
            "generalizedReliabilityIndexBoundMethod": None if reliability["bound"] is None else CENSORED_BOUND_METHOD,
            "reliabilityIndexMethod": RELIABILITY_INDEX_METHOD,
            "aBasisConforming": a_basis_pass,
            "bBasisConforming": b_basis_pass,
            "cpkConforming": cpk_pass,
            "criticalFlawMedian_mm": None,
            "criticalFlaw_P10_mm": None,
            "criticalFlaw_status": CRITICAL_FLAW_UNAVAILABLE_STATUS
        }
    }

def provenance() -> dict:
    """Constants/data versions (alloyName is a label only; it is not resolved)."""
    out = {
        "registryVersion": alloy_registry.REGISTRY_VERSION,
        "constantsVersion": physical_constants.CONSTANTS_VERSION,
        "gasConstantR_J_molK": R_GAS,
        "constantsNote": "Exact SI 2019 R = N_A*k (Phase 6a value step); it replaced the "
                         "4-significant-figure R = 8.314.",
        "modelStatus": "Illustrative, not calibrated: the strength model in solve_single_realization is "
                       "a toy superposition that is not fitted or validated against measured properties "
                       "(the default Inconel 718 case predicts a yield strength of about 3.5 GPa). "
                       "In the default case the precipitate radius is held at its 0.8 nm floor, so the aging "
                       "inputs have no effect on the output. Treat all strength statistics, A/B-style bounds, Cpk, "
                       "Pf and Sobol indices as screening of this model only, not as material allowables.",
    }
    out.update(_uq_data.provenance())
    return out

if __name__ == "__main__":
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            params = {
                "alloyName": _uq_data.UQ_DEFAULT_ALLOY_NAME,
                "baseMetal": _uq_data.UQ_DEFAULT_BASE_METAL,
                "standardSpec": _uq_data.UQ_DEFAULT_STANDARD_SPEC,
                "mcSamples": 2000
            }
        else:
            params = json.loads(input_data)
        
        result = solve_stochastic_uq(params)
        result["provenance"] = provenance()
        print(json.dumps(result, indent=2))
    except Exception as e:
        err_res = {
            "success": False,
            "error": str(e)
        }
        print(json.dumps(err_res), file=sys.stderr)
        sys.exit(1)
