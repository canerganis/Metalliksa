"""Parity of the NumPy-vectorised stochastic UQ solver against its pre-vectorisation scalar code.

The solver's hot loops (Sobol generation, centred L2 discrepancy, per-draw physics, descriptive
statistics, Saltelli pick-freeze) were vectorised without changing the sampling order: the same
seed must still give the same outputs. _LEGACY_SOURCE is a verbatim copy of
python/stochastic_uq_mmpds_solver.py at the last scalar revision; it is the reference these tests
compare against and is never imported by production code. Guards:

- Sobol points are bit-identical (state is an exact integer XOR scan below 2**32);
- the AS241 array quantile agrees with the scalar norm_ppf within a few ulp;
- the centred L2 discrepancy is equal (same accumulation order);
- the vector physics kernel agrees with solve_single_realization to 1e-12 relative;
- the full result document equals the reference (floats to one rounding unit of their printed
  precision, everything else exactly) and the recorded seed-42/N500 and other seed baselines hold.
"""
import json
import math
import types
import unittest

import numpy as np

import stochastic_uq_mmpds_solver as solver

_LEGACY_SOURCE = r'''#!/usr/bin/env python3
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

import alloy_data_kinetics_uq_fatigue as _uq_data
import alloy_registry
import physical_constants

# Phase 6a structural migration (design step (a)): constants come from
# physical_constants / alloy_data_kinetics_uq_fatigue with unchanged values.
# Phase 6a value step (b): exact SI 2019 R = N_A*k (was the 4-significant-figure 8.314).
R_GAS = physical_constants.GAS_CONSTANT_R.value  # J/(mol*K), exact
ZERO_C_K = physical_constants.ZERO_CELSIUS_K.value

_STD_NORMAL = NormalDist()

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

class SobolSequenceGenerator:
    """
    Antonov-Saleev Gray code Quasi-Monte Carlo Sobol Sequence Generator (up to 32 dimensions).
    Uses a local direction-number table and optional random digital shift.
    This implementation skips the origin; balanced-net guarantees are not claimed.
    """
    POLY = [
        (1, 0, [1]),                       # dim 1
        (1, 0, [1]),                       # dim 2
        (2, 1, [1, 3]),                    # dim 3
        (3, 1, [1, 3, 1]),                 # dim 4
        (3, 2, [1, 1, 1]),                 # dim 5
        (4, 1, [1, 1, 3, 3]),              # dim 6
        (4, 4, [1, 3, 5, 13]),             # dim 7
        (5, 2, [1, 1, 5, 5, 17]),          # dim 8
        (5, 4, [1, 1, 5, 5, 5]),           # dim 9
        (5, 7, [1, 1, 7, 11, 19]),         # dim 10
        (5, 11, [1, 1, 5, 1, 1]),          # dim 11
        (5, 13, [1, 1, 1, 3, 11]),         # dim 12
        (5, 14, [1, 3, 5, 5, 9]),          # dim 13
        (6, 1, [1, 1, 1, 1, 1, 1]),        # dim 14
        (6, 13, [1, 1, 3, 3, 5, 5]),       # dim 15
        (6, 16, [1, 3, 1, 5, 1, 3]),       # dim 16
        (6, 19, [1, 1, 5, 3, 7, 11]),      # dim 17
        (6, 22, [1, 1, 3, 1, 3, 7]),       # dim 18
        (6, 25, [1, 3, 3, 9, 7, 3]),       # dim 19
        (6, 28, [1, 1, 7, 3, 9, 13]),      # dim 20
        (7, 1, [1, 1, 1, 1, 1, 1, 1]),     # dim 21
        (7, 4, [1, 3, 5, 11, 7, 13, 29]),  # dim 22
        (7, 7, [1, 1, 3, 7, 15, 31, 63]),  # dim 23
        (7, 8, [1, 3, 1, 7, 5, 13, 27]),   # dim 24
        (7, 14, [1, 1, 5, 11, 13, 17, 33]),# dim 25
        (7, 19, [1, 3, 3, 9, 11, 23, 47]), # dim 26
        (7, 21, [1, 1, 7, 5, 15, 29, 59]), # dim 27
        (7, 28, [1, 3, 5, 1, 7, 15, 31]),  # dim 28
        (7, 31, [1, 1, 1, 3, 9, 27, 53]),  # dim 29
        (7, 32, [1, 3, 7, 15, 31, 63, 127]),# dim 30
        (7, 37, [1, 1, 5, 3, 11, 25, 49]), # dim 31
        (7, 41, [1, 3, 3, 7, 13, 21, 43])  # dim 32
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

    def generate(self, n: int):
        points = []
        for i in range(self.count, self.count + n):
            c = 0
            temp = i
            while temp & 1:
                temp >>= 1
                c += 1
            if c >= self.L:
                c = self.L - 1
            pt = [0.0] * self.d
            for d in range(self.d):
                self.X[d] ^= self.V[d][c]
                val = self.X[d] ^ self.shift[d]
                # Map strictly to open interval (0, 1) to avoid infinite probit boundaries
                pt[d] = (val + 0.5) / self.two_pow_L
            points.append(pt)
        self.count += n
        return points

def compute_centered_l2_discrepancy(points, max_eval: int = 150) -> float:
    """
    Computes Hickernell (1998) centered L2 star discrepancy CD_2(P)
    to rigorously benchmark point cloud uniformity on the unit hypercube.
    """
    N = len(points)
    if N == 0:
        return 0.0
    sub = points[:max_eval]
    M = len(sub)
    d = len(sub[0])

    term1 = (13.0 / 12.0) ** d

    sum_term2 = 0.0
    for i in range(M):
        prod = 1.0
        for k in range(d):
            z = abs(sub[i][k] - 0.5)
            prod *= (1.0 + 0.5 * z - 0.5 * (z ** 2))
        sum_term2 += prod
    term2 = (2.0 / M) * sum_term2

    sum_term3 = 0.0
    for i in range(M):
        for j in range(M):
            prod = 1.0
            for k in range(d):
                zi = abs(sub[i][k] - 0.5)
                zj = abs(sub[j][k] - 0.5)
                zdiff = abs(sub[i][k] - sub[j][k])
                prod *= (1.0 + 0.5 * zi + 0.5 * zj - 0.5 * zdiff)
            sum_term3 += prod
    term3 = (1.0 / (M * M)) * sum_term3

    cd2_sq = max(0.0, term1 - term2 + term3)
    return round(math.sqrt(cd2_sq), 6)

def solve_single_realization(
    base_metal: str,
    comp: dict,
    cooling_rate: float,
    aging_temp_C: float,
    aging_time_h: float,
    service_stress_MPa: float,
    flaw_size_um: float
) -> dict:
    """Evaluates multi-scale physics for one stochastic state draw."""
    # 1. Base Metal Lattice & Elasticity (alloy_data_kinetics_uq_fatigue; same values,
    # same legacy fallback: a base metal other than Ni/Fe/Ti uses the Al constants)
    lattice = _uq_data.uq_lattice_constants(base_metal)
    a0 = lattice["a0"]
    b_nm = lattice["b_nm"]
    C11, C12, C44 = lattice["C11"], lattice["C12"], lattice["C44"]
    taylor_M = lattice["taylor_M"]
    sigma_0 = lattice["sigma_0"]
    k_hp = lattice["k_hp"]  # MPa*sqrt(um)
    nu = lattice["nu"]
    G_c_kJ_m2 = lattice["G_c_kJ_m2"]  # fracture energy

    # VRH Elastic Moduli
    bulk_B = (C11 + 2.0 * C12) / 3.0
    G_Voigt = (C11 - C12 + 3.0 * C44) / 5.0
    G_Reuss = 5.0 * (C11 - C12) * C44 / max(1.0, (4.0 * C44 + 3.0 * (C11 - C12)))
    G_GPa = (G_Voigt + G_Reuss) / 2.0
    E_GPa = (9.0 * bulk_B * G_GPa) / max(1.0, (3.0 * bulk_B + G_GPa))

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

    # 7. Tensile UTS, Hollomon Strain Hardening, Ductility
    n_work_hardening = max(0.05, min(0.35, 0.42 - 0.00022 * sigma_yield_MPa))
    # UTS = Yield * (1 + 2.1 * n)
    sigma_uts_MPa = sigma_yield_MPa * (1.0 + 2.15 * n_work_hardening)
    
    # Elongation A%
    elongation_pct = max(3.0, min(50.0, 3200.0 / (sigma_yield_MPa ** 0.82) * (1.0 + 1.5 * n_work_hardening)))

    # 8. Fracture Toughness K_1c & Critical Flaw Size a_c
    # K_1c ~ sqrt(E * G_c / (1 - nu^2)) modified by ductility/yield
    k1c_base = math.sqrt((E_GPa * G_c_kJ_m2) / max(0.1, (1.0 - nu**2)))
    k1c_MPa_sqrt_m = max(18.0, min(160.0, k1c_base * (1.0 + 0.025 * elongation_pct) * (900.0 / max(300.0, sigma_yield_MPa)) ** 0.35))

    # Critical Flaw Size (LEFM ASTM E1820)
    # a_c = (1/pi) * (K_1c / (1.12 * sigma_service))^2 (meters -> mm)
    applied_stress = max(50.0, service_stress_MPa)
    flaw_ac_mm = (1.0 / math.pi) * ((k1c_MPa_sqrt_m / (1.12 * applied_stress)) ** 2) * 1000.0
    flaw_ac_mm = max(0.05, min(250.0, flaw_ac_mm))

    # Limit State Margins
    # M_yield = Yield - Applied_Stress * 1.5
    margin_yield_MPa = sigma_yield_MPa - applied_stress * 1.5
    margin_flaw_mm = flaw_ac_mm - (flaw_size_um / 1000.0)

    return {
        "yield_MPa": sigma_yield_MPa,
        "uts_MPa": sigma_uts_MPa,
        "elongation_pct": elongation_pct,
        "k1c_MPa_m": k1c_MPa_sqrt_m,
        "critical_flaw_ac_mm": flaw_ac_mm,
        "margin_yield_MPa": margin_yield_MPa,
        "margin_flaw_mm": margin_flaw_mm,
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

    flaw_size_mean_um = float(params.get("initialFlawSize_um_mean", 45.0))
    flaw_size_std_um = float(params.get("initialFlawSize_um_std", 15.0))

    spec_min_yield = float(params.get("specMinYield_MPa", 1100.0))
    spec_min_uts = float(params.get("specMinUTS_MPa", 1350.0))
    spec_min_elongation = float(params.get("specMinElongation_pct", 12.0))

    N_samples = int(min(10000, max(500, params.get("mcSamples", 2500))))

    # Deterministic Seed for reproducible scientific comparison across parameter tuning
    random.seed(seed)

    elements = list(nominal_comp.keys())
    E_dim = len(elements)
    # Total uncertain dimensions: Elements + CoolingRate + AgingTemp + AgingTime + ServiceStress + FlawSize
    total_dims = E_dim + 5

    # Log-normal parameters for cooling rate
    sigma_log_cr = math.sqrt(math.log(1.0 + cooling_rate_cov**2))
    mu_log_cr = math.log(cooling_rate_nominal) - 0.5 * (sigma_log_cr**2)

    # -------------------------------------------------------------
    # Low-Discrepancy Sobol Sequence Generation or Pseudo-Random Draw
    # -------------------------------------------------------------
    if sampling_method == "sobol_qmc":
        sobol_gen = SobolSequenceGenerator(dimension=total_dims, scramble=scramble, seed=seed)
        qmc_points = sobol_gen.generate(N_samples)
        sobol_cd2 = compute_centered_l2_discrepancy(qmc_points, max_eval=min(150, N_samples))
        
        # Disabled pseudo benchmark comparison to strictly enforce Sobol QMC
        pseudo_cd2 = 0
        discrepancy_reduction_pct = 0.0
    else:
        raise ValueError("Standard Pseudo-Random Monte Carlo is disabled. Enforcing QMC/Sobol determinism. Pass samplingMethod='sobol_qmc'.")

    yield_list = []
    uts_list = []
    elong_list = []
    k1c_list = []
    flaw_ac_list = []
    margin_yield_list = []

    for i in range(N_samples):
        pt = qmc_points[i]

        # 1. Sample normal composition and floor at zero (not a truncated-normal CDF)
        comp_sample = {}
        for idx_e, el in enumerate(elements):
            nom = nominal_comp[el]
            tol = comp_tolerances.get(el, nom * 0.1)
            std_el = tol / 3.0
            u_val = pt[idx_e]
            z_el = norm_ppf(u_val)
            val = nom + z_el * std_el
            comp_sample[el] = max(0.0, val)

        # 2. Sample Process Parameters via exact quantile transformations
        # Cooling rate (Log-normal distribution)
        z_cr = norm_ppf(pt[E_dim])
        cooling_rate_i = math.exp(mu_log_cr + sigma_log_cr * z_cr)

        # Aging temperature (Normal)
        z_temp = norm_ppf(pt[E_dim + 1])
        aging_temp_i = max(200.0, aging_temp_nominal + z_temp * aging_temp_std)

        # Aging time (Normal)
        z_time = norm_ppf(pt[E_dim + 2])
        aging_time_i = max(0.2, aging_time_nominal + z_time * aging_time_std)

        # Service stress (Normal)
        z_stress = norm_ppf(pt[E_dim + 3])
        service_stress_i = max(50.0, service_stress_nominal + z_stress * (service_stress_nominal * service_stress_cov))

        # Flaw size (Normal)
        z_flaw = norm_ppf(pt[E_dim + 4])
        flaw_size_i = max(5.0, flaw_size_mean_um + z_flaw * flaw_size_std_um)

        # Solve Physics
        res = solve_single_realization(
            base_metal=base_metal,
            comp=comp_sample,
            cooling_rate=cooling_rate_i,
            aging_temp_C=aging_temp_i,
            aging_time_h=aging_time_i,
            service_stress_MPa=service_stress_i,
            flaw_size_um=flaw_size_i
        )

        yield_list.append(res["yield_MPa"])
        uts_list.append(res["uts_MPa"])
        elong_list.append(res["elongation_pct"])
        k1c_list.append(res["k1c_MPa_m"])
        flaw_ac_list.append(res["critical_flaw_ac_mm"])
        margin_yield_list.append(res["margin_yield_MPa"])

    # Descriptive model statistics; uncertainty of a single QMC run is not estimated.
    def calc_stats(arr: list, spec_min: float = None):
        sorted_arr = sorted(arr)
        n = len(sorted_arr)
        mean_val = sum(sorted_arr) / n
        var_val = sum((x - mean_val)**2 for x in sorted_arr) / (n - 1) if sorted_arr[0] != sorted_arr[-1] else 0.0
        std_val = math.sqrt(var_val)
        cov_pct = (std_val / mean_val * 100.0) if mean_val != 0 else 0.0

        # Skewness
        skew = (sum((x - mean_val)**3 for x in sorted_arr) / n) / max(1e-6, (std_val**3))
        # Kurtosis
        kurt = (sum((x - mean_val)**4 for x in sorted_arr) / n) / max(1e-6, (std_val**4)) - 3.0

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
            conformance_count = sum(1 for x in sorted_arr if x >= spec_min)
            conformance_pct = round((conformance_count / n) * 100.0, 2)

        # Histogram Bins generation (25 bins)
        min_v = sorted_arr[0]
        max_v = sorted_arr[-1]
        bin_width = (max_v - min_v) / 25.0 if max_v > min_v else 1.0
        histogram = []
        for b in range(25):
            b_start = min_v + b * bin_width
            b_end = b_start + bin_width
            b_center = (b_start + b_end) / 2.0
            count = sum(1 for x in sorted_arr if b_start <= x < b_end or (b == 24 and x == max_v))
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
                "cumulativePct": round((sum(1 for x in sorted_arr if x <= b_end) / n) * 100.0, 1)
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
    uts_stats = calc_stats(uts_list, spec_min_uts)
    elong_stats = calc_stats(elong_list, spec_min_elongation)
    k1c_stats = calc_stats(k1c_list, 60.0)
    flaw_ac_stats = calc_stats(flaw_ac_list, 1.0)

    # 4. Reliability & Failure Probability
    failures_yield = sum(1 for m in margin_yield_list if m < 0)
    pf_yield = failures_yield / N_samples
    beta_reliability_yield = norm_ppf(1.0 - max(1e-6, min(1.0 - 1e-6, pf_yield)))

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
    saltelli_pts = saltelli_sobol.generate(M_saltelli)

    def eval_factor_vector(vec):
        c_draw = {
            el: max(0.0, nominal_comp[el] + norm_ppf(vec[idx]) * (comp_tolerances.get(el, nominal_comp[el] * 0.1) / 3.0))
            for idx, el in enumerate(elements)
        }
        cr_draw = math.exp(mu_log_cr + sigma_log_cr * norm_ppf(vec[E_dim]))
        t_age_draw = max(200.0, aging_temp_nominal + norm_ppf(vec[E_dim + 1]) * aging_temp_std)
        time_age_draw = max(0.2, aging_time_nominal + norm_ppf(vec[E_dim + 2]) * aging_time_std)
        return solve_single_realization(
            base_metal, c_draw, cr_draw, t_age_draw, time_age_draw,
            service_stress_nominal, flaw_size_mean_um
        )["yield_MPa"]

    y_A = [eval_factor_vector(row[:k_factors]) for row in saltelli_pts]
    y_B = [eval_factor_vector(row[k_factors:]) for row in saltelli_pts]
    combined_y = y_A + y_B
    mean_comb = sum(combined_y) / len(combined_y)
    total_var = sum((v - mean_comb)**2 for v in combined_y) / len(combined_y)
    variance_available = max(combined_y) - min(combined_y) > 1e-12 * max(1.0, abs(mean_comb))
    sensitivity_indices = []
    for idx, item in enumerate(sensitivity_factors):
        y_AB = []
        for row in saltelli_pts:
            vec_AB = list(row[:k_factors])
            vec_AB[idx] = row[k_factors + idx]
            y_AB.append(eval_factor_vector(vec_AB))
        # Centered Saltelli first-order and Jansen total-order estimators.
        # Raw finite-sample estimates may be negative or exceed one.
        s_first = sum((y_B[j] - mean_comb) * (y_AB[j] - y_A[j]) for j in range(M_saltelli)) / (M_saltelli * total_var) if variance_available else None
        s_total = sum((y_A[j] - y_AB[j])**2 for j in range(M_saltelli)) / (2.0 * M_saltelli * total_var) if variance_available else None
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
            "samplingDescription": "Local Sobol sequence with optional random digital shift." if sampling_method == "sobol_qmc" else "Seeded pseudo-random Monte Carlo sampling.",
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
            "ultimateTensileStrength_UTS": uts_stats,
            "elongationPct": elong_stats,
            "fractureToughness_K1c": k1c_stats,
            "criticalFlawSize_ac": flaw_ac_stats
        },
        "sobolSensitivityAnalysis": sensitivity_indices,
        "sensitivityMetadata": {
            "method": "Centered Saltelli first-order / Jansen total-order; seeded pseudo-MC pick-freeze",
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
            "yieldFailureProbability_Pf": pf_yield,
            "hasoferLindBetaIndex": round(beta_reliability_yield, 2),
            "aBasisConforming": a_basis_pass,
            "bBasisConforming": b_basis_pass,
            "cpkConforming": cpk_pass,
            "criticalFlawMedian_mm": flaw_ac_stats["median_P50"],
            "criticalFlaw_P10_mm": flaw_ac_stats["P10"]
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
'''


def _load_legacy():
    module = types.ModuleType("stochastic_uq_scalar_reference")
    exec(compile(_LEGACY_SOURCE, "<stochastic_uq scalar reference>", "exec"), module.__dict__)
    return module


LEGACY = _load_legacy()

CASES = {
    "s42_n500_default": {"mcSamples": 500},
    "s1_n500": {"mcSamples": 500, "seed": 1},
    "s7_n2500_noscramble": {"mcSamples": 2500, "seed": 7, "scramble": False},
    "s12345_n10000": {"mcSamples": 10000, "seed": 12345},
    "s99_n777_Fe": {"mcSamples": 777, "seed": 99, "baseMetal": "Fe",
                    "composition_wt": {"C": 0.4, "Cr": 0.8, "Mo": 0.25, "Ni": 1.8, "Mn": 0.7},
                    "composition_tolerances": {"C": 0.03, "Cr": 0.1, "Mo": 0.05}},
    "s5_n1234_Ti": {"mcSamples": 1234, "seed": 5, "baseMetal": "Ti",
                    "composition_wt": {"Al": 6.0, "V": 4.0, "Fe": 0.2},
                    "composition_tolerances": {"Al": 0.4, "V": 0.3, "Fe": 0.05},
                    "coolingRate_nominal": 80000.0, "coolingRate_cov": 0.6, "agingTemp_nominal": 540.0},
    "s3_n600_Al": {"mcSamples": 600, "seed": 3, "baseMetal": "Al",
                   "composition_wt": {"Si": 10.0, "Mg": 0.3}, "composition_tolerances": {"Si": 0.5, "Mg": 0.1}},
    "s8_n900_extreme": {"mcSamples": 900, "seed": 8, "coolingRate_nominal": 5.0, "coolingRate_cov": 1.5,
                        "agingTemp_nominal": 250.0, "agingTemp_stdDev": 60.0, "agingTime_nominal": 0.5,
                        "agingTime_stdDev": 0.6, "serviceStress_nominal": 40.0, "serviceStress_cov": 0.5,
                        "initialFlawSize_um_mean": 3.0, "initialFlawSize_um_std": 40.0},
    "s11_n300_unknown_base": {"mcSamples": 300, "seed": 11, "baseMetal": "Zz"},
    "empty_composition": {"mcSamples": 500, "seed": 4, "composition_wt": {}, "composition_tolerances": {}},
    "zero_variance": {"mcSamples": 500, "seed": 2, "composition_wt": {"Nb": 5.0},
                      "composition_tolerances": {"Nb": 0.0}, "coolingRate_cov": 0.0,
                      "agingTemp_stdDev": 0.0, "agingTime_stdDev": 0.0},
}

# yield mean, stdDev, A-basis, B-basis, Pf, top sensitivity parameter and index, discrepancy:
# recorded from the scalar code before vectorisation (independent of the embedded reference).
GOLDEN = {
    "s42_n500_default": (3467.8, 41.37, 3365.4, 3410.5, 0.0, "dT/dt (Cooling Rate)", 0.581, 0.212048),
    "s1_n500": (3468.2, 41.17, 3366.3, 3411.1, 0.0, "dT/dt (Cooling Rate)", 0.566, 0.214096),
    "s7_n2500_noscramble": (3467.9, 40.93, 3370.0, 3413.6, 0.0, "dT/dt (Cooling Rate)", 0.598, 0.212335),
    "s12345_n10000": (3467.9, 41.24, 3370.6, 3414.1, 0.0, "dT/dt (Cooling Rate)", 0.645, 0.21308),
    "s99_n777_Fe": (1327.8, 28.36, 1258.5, 1289.1, 0.003861003861003861, "dT/dt (Cooling Rate)", 1.042, 0.116108),
    "s5_n1234_Ti": (2855.7, 44.98, 2746.9, 2795.1, 0.0, "dT/dt (Cooling Rate)", 0.671, 0.072795),
    "s3_n600_Al": (554.6, 13.65, 521.0, 535.8, 1.0, "Mg (Composition)", 0.558, 0.054621),
    "s8_n900_extreme": (2785.2, 36.33, 2696.7, 2735.9, 0.0, "dT/dt (Cooling Rate)", 0.478, 0.216249),
    "s11_n300_unknown_base": (1229.9, 12.57, 1198.8, 1212.5, 0.046, "Nb (Composition)", 0.37, 0.216645),
    "empty_composition": (1399.4, 35.15, 1312.4, 1350.7, 0.0, "dT/dt (Cooling Rate)", 1.005, 0.029812),
}


def _strip(doc):
    return {k: v for k, v in doc.items() if k != "computeTimeMs"}


def _without_unsupported(doc):
    """The scalar reference document with the three invented-law outputs (UTS, K_Ic, critical flaw size)
    replaced by null + the solver's unavailable status: the only intended difference to the reference."""
    out = json.loads(json.dumps(doc))
    props = out["stochasticProperties"]
    props["ultimateTensileStrength_UTS"] = None
    props["ultimateTensileStrength_UTS_status"] = solver.UTS_UNAVAILABLE_STATUS
    props["fractureToughness_K1c"] = None
    props["fractureToughness_K1c_status"] = solver.K1C_UNAVAILABLE_STATUS
    props["criticalFlawSize_ac"] = None
    props["criticalFlawSize_ac_status"] = solver.CRITICAL_FLAW_UNAVAILABLE_STATUS
    rel = out["aerospaceReliability"]
    rel["criticalFlawMedian_mm"] = None
    rel["criticalFlaw_P10_mm"] = None
    rel["criticalFlaw_status"] = solver.CRITICAL_FLAW_UNAVAILABLE_STATUS
    return out


def _legacy_kernel_subset(legacy_result, new_result):
    """The reference realisation restricted to the keys the current kernel still returns."""
    return {k: v for k, v in legacy_result.items() if k in new_result}


# Production rounding (decimals) per result field; floats of these fields may differ by one unit
# in the last rounded digit (a different ulp in numpy exp/log/pow can flip a rounding). Every
# other float must agree to 1e-12 relative.
_ROUNDING = {
    "mean": 1, "stdDev": 2, "covPct": 2, "skewness": 3, "kurtosis": 3, "min": 1, "max": 1,
    "median_P50": 1, "P10": 1, "P90": 1, "ci95Lower_P2_5": 1, "ci95Upper_P97_5": 1, "P01": 1, "P99": 1,
    "aBasisAllowable": 1, "bBasisAllowable": 1, "cpk": 2, "conformancePct": 2,
    "binCenter": 1, "binStart": 1, "binEnd": 1, "empiricalPdf": 6, "fittedNormalPdf": 6, "cumulativePct": 1,
    "sobolFirstOrderIndex": 3, "sobolTotalOrderIndex": 3, "interactionIndex": 3, "varianceContributionPct": 1,
    "hasoferLindBetaIndex": 2, "centeredL2Discrepancy": 6, "criticalFlawMedian_mm": 1, "criticalFlaw_P10_mm": 1,
}


def _diffs(new, old, path="$"):
    """Differences between two result documents (see _ROUNDING for the float tolerance)."""
    if isinstance(old, dict):
        if not isinstance(new, dict) or set(new) != set(old):
            return [(path, "keys", sorted(set(new) ^ set(old)) if isinstance(new, dict) else new)]
        out = []
        for key in old:
            out += _diffs(new[key], old[key], f"{path}.{key}")
        return out
    if isinstance(old, list):
        if not isinstance(new, list) or len(new) != len(old):
            return [(path, "length", None)]
        out = []
        for i, (a, b) in enumerate(zip(new, old)):
            out += _diffs(a, b, f"{path}[{i}]")
        return out
    if isinstance(old, float) and isinstance(new, float):
        if new == old:
            return []
        places = _ROUNDING.get(path.rsplit(".", 1)[-1].split("[")[0])
        tol = (1.01 * 10.0 ** -places if places is not None else 0.0) + 1e-12 * abs(old)
        return [] if abs(new - old) <= tol else [(path, new, old)]
    return [] if (new == old and type(new) is type(old)) else [(path, new, old)]


class SobolParityTests(unittest.TestCase):
    def test_points_are_bit_identical_including_chunked_generation(self):
        for dim in (1, 2, 4, 13, 32):
            for scramble in (True, False):
                for seed in (0, 42, 987654321):
                    new = solver.SobolSequenceGenerator(dim, scramble=scramble, seed=seed)
                    old = LEGACY.SobolSequenceGenerator(dim, scramble=scramble, seed=seed)
                    for chunk in (1, 2, 3, 500, 1021):  # continues the Gray-code state across calls
                        self.assertEqual(new.generate(chunk), old.generate(chunk), (dim, scramble, seed, chunk))
                    self.assertEqual(new.X, old.X)
                    self.assertEqual(new.count, old.count)

    def test_array_and_list_forms_agree_and_empty_request_is_empty(self):
        gen = solver.SobolSequenceGenerator(5, scramble=True, seed=7)
        arr = gen.generate_array(64)
        self.assertEqual(arr.shape, (64, 5))
        self.assertEqual(arr.tolist(), solver.SobolSequenceGenerator(5, scramble=True, seed=7).generate(64))
        self.assertEqual(gen.generate(0), [])
        self.assertEqual(LEGACY.SobolSequenceGenerator(5, scramble=True, seed=7).generate(0), [])

    def test_dimension_limit_unchanged(self):
        with self.assertRaises(ValueError):
            solver.SobolSequenceGenerator(33)
        with self.assertRaises(ValueError):
            solver.SobolSequenceGenerator(0)

    def test_centered_l2_discrepancy_equal(self):
        for dim, n in ((1, 1), (3, 7), (8, 150), (13, 500), (32, 200)):
            pts = LEGACY.SobolSequenceGenerator(dim, scramble=True, seed=3).generate(n)
            self.assertEqual(solver.compute_centered_l2_discrepancy(pts, 150),
                             LEGACY.compute_centered_l2_discrepancy(pts, 150), (dim, n))
        self.assertEqual(solver.compute_centered_l2_discrepancy([]), 0.0)
        self.assertEqual(solver.compute_centered_l2_discrepancy([[0.5]]),
                         LEGACY.compute_centered_l2_discrepancy([[0.5]]))


class ComparatorTests(unittest.TestCase):
    def test_rounded_field_mutations_beyond_one_unit_are_detected(self):
        doc = _strip(solver.solve_stochastic_uq({"mcSamples": 500}))
        self.assertEqual(_diffs(doc, json.loads(json.dumps(doc))), [])
        row = doc["sobolSensitivityAnalysis"][0]
        for key, step in (("sobolTotalOrderIndex", 0.1), ("sobolFirstOrderIndex", 0.01), ("interactionIndex", 0.01)):
            mutant = json.loads(json.dumps(doc))
            mutant["sobolSensitivityAnalysis"][0][key] = round(row[key] + step, 3)
            self.assertNotEqual(_diffs(mutant, doc), [], key)
        mutant = json.loads(json.dumps(doc))
        mutant["sobolSensitivityAnalysis"][0]["sobolTotalOrderIndex"] = 0.0
        mutant["sobolSensitivityAnalysis"][0]["sobolTotalOrderIndex"] = round(row["sobolTotalOrderIndex"] + 0.001, 3)
        self.assertEqual(_diffs(mutant, doc), [])  # one unit of the 3-decimal rounding is tolerated
        mutant = json.loads(json.dumps(doc))
        mutant["stochasticProperties"]["yieldStrength_Rp02"]["stdDev"] += 0.05
        self.assertNotEqual(_diffs(mutant, doc), [])
        zero = json.loads(json.dumps(doc))
        zero_old = json.loads(json.dumps(doc))
        zero_old["sobolSensitivityAnalysis"][0]["sobolTotalOrderIndex"] = 0.0
        zero["sobolSensitivityAnalysis"][0]["sobolTotalOrderIndex"] = 0.1
        self.assertNotEqual(_diffs(zero, zero_old), [])  # 0.0 vs 0.1 (reviewer's mutation)


class NonFinitePopulationTests(unittest.TestCase):
    def test_overflow_is_rejected_like_the_scalar_reference(self):
        for payload in ({"mcSamples": 500, "coolingRate_nominal": 1e308},
                        {"mcSamples": 500, "composition_tolerances": {"Nb": 1e308}}):
            with self.subTest(payload=payload):
                with self.assertRaises((OverflowError, ValueError)) as old_err:
                    LEGACY.solve_stochastic_uq(dict(payload))
                with self.assertRaises(type(old_err.exception)):
                    solver.solve_stochastic_uq(dict(payload))

    def test_non_finite_populations_are_rejected_instead_of_reported(self):
        # The scalar code returned Infinity statistics for the first payload and let NaN draws
        # reach the histogram (NaN endpoints flipped cumulativePct); both are now a controlled error.
        for payload in ({"mcSamples": 500, "composition_wt": {"Nb": 1e308}, "composition_tolerances": {"Nb": 1e308}},
                        {"mcSamples": 500, "coolingRate_nominal": float("nan")},
                        {"mcSamples": 500, "agingTemp_nominal": float("inf")}):
            with self.subTest(payload=payload):
                with self.assertRaises(OverflowError):
                    solver.solve_stochastic_uq(dict(payload))

    def test_nan_inputs_floored_by_max_semantics_still_match_the_reference(self):
        # max(0.0, nan) == 0.0 and max(50.0, nan) == 50.0 in the scalar code: kept by _pmax.
        for payload in ({"mcSamples": 500, "composition_wt": {"Nb": float("nan")}},
                        {"mcSamples": 500, "serviceStress_nominal": float("nan")}):
            with self.subTest(payload=payload):
                new = _strip(solver.solve_stochastic_uq(dict(payload)))
                old = _without_unsupported(_strip(LEGACY.solve_stochastic_uq(dict(payload))))
                self.assertEqual(json.dumps(new, sort_keys=True), json.dumps(old, sort_keys=True))


class QuantileParityTests(unittest.TestCase):
    def test_array_quantile_matches_scalar_to_a_few_ulp(self):
        grid = np.concatenate([
            np.linspace(1e-12, 1 - 1e-12, 20001),
            np.logspace(-300, -1, 600), 1.0 - np.logspace(-16, -1, 600),
            [0.5, 0.075, 0.925, 0.425 + 0.5, 0.5 - 0.425, 1.16e-10, 1 - 1.16e-10],
        ])
        got = solver.norm_ppf_array(grid)
        want = np.array([solver.norm_ppf(float(p)) for p in grid])
        ulp = np.spacing(np.maximum(np.abs(want), 1e-300))
        self.assertLessEqual(float(np.max(np.abs(got - want) / ulp)), 4.0)

    def test_clamps_and_shapes_like_scalar(self):
        p = np.array([[-1.0, 0.0, 1.0, 2.0], [0.5, 0.25, 0.75, 1e-6]])
        got = solver.norm_ppf_array(p)
        self.assertEqual(got.shape, p.shape)
        self.assertEqual(got[0].tolist(), [-8.0, -8.0, 8.0, 8.0])
        self.assertEqual(got[1].tolist(), [solver.norm_ppf(v) for v in p[1].tolist()])
        self.assertEqual(solver.norm_ppf_array([]).shape, (0,))


class PhysicsKernelParityTests(unittest.TestCase):
    def test_vector_kernel_matches_scalar_realisation(self):
        rng = np.random.default_rng(20261005)
        n = 400
        comp = {"Nb": rng.uniform(0.0, 6.0, n), "Ti": rng.uniform(0.0, 1.5, n), "Al": rng.uniform(0.0, 1.0, n),
                "Mg": rng.uniform(0.0, 0.4, n), "Cr": rng.uniform(0.0, 20.0, n), "Zr": rng.uniform(0.0, 0.5, n),
                "Cu": np.zeros(n)}
        cr = np.exp(rng.uniform(math.log(0.05), math.log(1e7), n))  # spans the 0.1 floor, grain floor, rho floor
        temp = rng.uniform(150.0, 1000.0, n)  # below 200 C and into the Arrhenius clamp
        time_h = rng.uniform(0.05, 40.0, n)
        stress = rng.uniform(10.0, 1500.0, n)
        flaw = rng.uniform(1.0, 200.0, n)  # only the reference kernel still takes a flaw size
        for base in ("Ni", "Fe", "Ti", "Al", "Zz", None):
            vec = solver.solve_realizations_vec(base, comp, cr, temp, time_h, stress)
            for key, column in vec.items():
                column = np.broadcast_to(np.asarray(column, dtype=float), (n,))
                for i in range(n):
                    scalar = LEGACY.solve_single_realization(
                        base, {el: float(v[i]) for el, v in comp.items()},
                        float(cr[i]), float(temp[i]), float(time_h[i]), float(stress[i]), float(flaw[i]))[key]
                    self.assertTrue(math.isclose(float(column[i]), scalar, rel_tol=1e-12, abs_tol=1e-12),
                                    (base, key, i, float(column[i]), scalar))

    def test_scalar_reference_still_matches_legacy_exactly(self):
        args = ("Ni", {"Nb": 5.0, "Ti": 0.9, "Al": 0.5, "Zr": 0.3, "Mg": 0.1}, 1.5e5, 720.0, 8.0, 700.0, 40.0)
        new = solver.solve_single_realization(*args[:-1])
        self.assertEqual(repr(new), repr(_legacy_kernel_subset(LEGACY.solve_single_realization(*args), new)))


class ResultParityTests(unittest.TestCase):
    def test_full_documents_equal_the_scalar_reference(self):
        for name, payload in CASES.items():
            with self.subTest(case=name):
                new = _strip(solver.solve_stochastic_uq(dict(payload)))
                old = _without_unsupported(_strip(LEGACY.solve_stochastic_uq(dict(payload))))
                self.assertEqual(_diffs(new, old), [])

    def test_recorded_scalar_baselines_hold(self):
        for name, expected in GOLDEN.items():
            with self.subTest(case=name):
                result = solver.solve_stochastic_uq(dict(CASES[name]))
                stats = result["stochasticProperties"]["yieldStrength_Rp02"]
                top = result["sobolSensitivityAnalysis"][0]
                got = (stats["mean"], stats["stdDev"], stats["aBasisAllowable"], stats["bBasisAllowable"],
                       result["aerospaceReliability"]["yieldFailureProbability_Pf"], top["parameter"],
                       top["sobolFirstOrderIndex"], result["samplingMetadata"]["centeredL2Discrepancy"])
                self.assertEqual(got, expected)

    def test_in718_seed42_n500_baseline(self):
        stats = solver.solve_stochastic_uq({"mcSamples": 500})["stochasticProperties"]["yieldStrength_Rp02"]
        self.assertEqual((stats["mean"], stats["stdDev"], stats["aBasisAllowable"], stats["bBasisAllowable"]),
                         (3467.8, 41.37, 3365.4, 3410.5))

    def test_zero_variance_status_and_seed_reproducibility(self):
        result = solver.solve_stochastic_uq(dict(CASES["zero_variance"]))
        self.assertEqual(result["sensitivityMetadata"]["status"], "unavailable_zero_variance")
        first = _strip(solver.solve_stochastic_uq({"mcSamples": 500, "seed": 31}))
        again = _strip(solver.solve_stochastic_uq({"mcSamples": 500, "seed": 31}))
        other = _strip(solver.solve_stochastic_uq({"mcSamples": 500, "seed": 32}))
        self.assertEqual(json.dumps(first), json.dumps(again))
        self.assertNotEqual(json.dumps(first), json.dumps(other))

    def test_error_paths_unchanged(self):
        for bad in ({"samplingMethod": "pseudo_mc"}, {"samplingMethod": "latin"}):
            with self.assertRaises(ValueError) as new_err:
                solver.solve_stochastic_uq(dict(bad))
            with self.assertRaises(ValueError) as old_err:
                LEGACY.solve_stochastic_uq(dict(bad))
            self.assertEqual(str(new_err.exception), str(old_err.exception))
        many = {f"E{i}": 1.0 for i in range(30)}  # 30 + 5 dimensions exceed the 32-dimension Sobol limit
        with self.assertRaises(ValueError) as new_err:
            solver.solve_stochastic_uq({"composition_wt": many})
        with self.assertRaises(ValueError) as old_err:
            LEGACY.solve_stochastic_uq({"composition_wt": many})
        self.assertEqual(str(new_err.exception), str(old_err.exception))


if __name__ == "__main__":
    unittest.main()
