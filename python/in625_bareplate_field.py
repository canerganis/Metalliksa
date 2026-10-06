"""Bounded IN625 bare-substrate conduction screening (no powder or melt pool).

The only constitutive authority is ``in625_thermal_material``'s mass-basis
Cp/k/H(T) law, bounded to 273.15..1623.15 K. The density 8440 kg/m^3 is a
constant supplier-bulletin assumption, not a lot-matched measurement. The
moving surface source accepts absorbed power directly in W; no absorptivity,
laser coupling, vapor, fluid flow, or free-surface physics is inferred.

All six boundaries are adiabatic. The scan is a normalized Gaussian surface
power distribution, so its discrete integral equals the explicit absorbed-W
input at every step. This is a numerical/model screening path only and carries
the source model's ``unvalidated-literature-model-screening`` status.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

try:
    import warp as _wp
except ImportError:  # The explicit CUDA solver retains its Torch reference fallback.
    _wp = None

from in625_thermal_material import (
    LIQUIDUS_K,
    REFERENCE_TEMPERATURE_K,
    in625_lpbf_thermal_at_kelvin,
    in625_lpbf_thermal_snapshot,
)
from lpbf_heat_source import MINIMUM_SOURCE_CAPTURE_FRACTION, require_source_capture


DENSITY_KG_M3 = 8440.0
DENSITY_BASIS = "constant supplier bulletin assumption; not lot-matched"
DENSITY_SOURCE_URL = (
    "https://www.specialmetals.com/documents/technical-bulletins/inconel/"
    "inconel-alloy-625.pdf"
)
MODEL_STATUS = "unvalidated-literature-model-screening"
_SNAPSHOT = in625_lpbf_thermal_snapshot()
MATERIAL_REVISION_SHA256 = _SNAPSHOT["materialRevisionSha256"]


@dataclass(frozen=True)
class BareplateConfig:
    """Uniform cell-centered plate and explicit absorbed-power scan inputs."""

    shape_xyz: tuple[int, int, int] = (16, 8, 6)
    cell_size_m: tuple[float, float, float] = (0.00025, 0.00025, 0.00025)
    initial_temperature_K: float = 298.15
    dt_s: float = 1.0e-5
    steps: int = 10
    absorbed_power_W: float = 20.0
    spot_sigma_m: float = 0.0004
    scan_start_x_m: float = 0.001
    scan_y_m: float = 0.001
    scan_velocity_x_m_s: float = 0.0


@dataclass(frozen=True)
class BareplateResult:
    temperature_K: object
    specific_enthalpy_J_kg: object
    time_s: object
    total_enthalpy_J: object
    peak_temperature_K: object
    energy_residual_J: object
    metadata: dict


def _validate(config: BareplateConfig) -> tuple[int, int, int]:
    if not isinstance(config, BareplateConfig):
        raise ValueError("config must be a BareplateConfig")
    if (not isinstance(config.shape_xyz, tuple) or len(config.shape_xyz) != 3
            or any(type(n) is not int or n < 2 for n in config.shape_xyz)):
        raise ValueError("shape_xyz must contain three integer dimensions >= 2")
    if (not isinstance(config.cell_size_m, tuple) or len(config.cell_size_m) != 3
            or any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0
                   for v in config.cell_size_m)):
        raise ValueError("cell_size_m must contain three positive finite lengths")
    if type(config.steps) is not int or config.steps < 1:
        raise ValueError("steps must be a positive integer")
    scalar_values = (config.initial_temperature_K, config.dt_s,
                     config.absorbed_power_W, config.spot_sigma_m,
                     config.scan_start_x_m, config.scan_y_m,
                     config.scan_velocity_x_m_s)
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in scalar_values):
        raise ValueError("all scalar model inputs must be finite numbers")
    if not REFERENCE_TEMPERATURE_K <= config.initial_temperature_K < LIQUIDUS_K:
        raise ValueError("initial temperature must be inside the bounded IN625 law")
    if config.dt_s <= 0 or config.absorbed_power_W < 0 or config.spot_sigma_m <= 0:
        raise ValueError("dt/sigma must be positive and absorbed power nonnegative")
    nx, ny, nz = config.shape_xyz
    dx, dy, dz = map(float, config.cell_size_m)
    lx, ly = nx * dx, ny * dy
    x_end = config.scan_start_x_m + config.scan_velocity_x_m_s * config.dt_s * (config.steps - 1)
    if not (0.0 <= config.scan_start_x_m <= lx and 0.0 <= x_end <= lx):
        raise ValueError("scan center must remain inside the bareplate x extent")
    if not 0.0 <= config.scan_y_m <= ly:
        raise ValueError("scan center must remain inside the bareplate y extent")

    # Conservative explicit FTCS limit for the smallest mass-basis Cp and
    # largest k in the admitted model interval, with 0.45 safety factor.
    sample_temperatures = np.linspace(REFERENCE_TEMPERATURE_K, LIQUIDUS_K, 129)
    cp_min = min(in625_lpbf_thermal_at_kelvin(float(t))["effectiveHeatCapacity_J_kgK"]
                 for t in sample_temperatures)
    k_max = max(in625_lpbf_thermal_at_kelvin(float(t))["thermalConductivity_W_mK"]
                for t in sample_temperatures)
    inv_sum = 1.0 / dx**2 + 1.0 / dy**2 + 1.0 / dz**2
    dt_limit = 0.45 * DENSITY_KG_M3 * cp_min / (2.0 * k_max * inv_sum)
    if config.dt_s > dt_limit:
        raise ValueError(f"dt_s exceeds explicit conduction stability bound ({dt_limit:.9g} s)")
    return nx, ny, nz


def _law_numpy(temperature):
    """Array form of the exact bounded constitutive equations in the authority."""
    t = np.asarray(temperature, dtype=np.float64)
    if not np.isfinite(t).all() or (t < REFERENCE_TEMPERATURE_K).any() or (t > LIQUIDUS_K).any():
        raise ValueError("temperature outside bounded IN625 enthalpy law")
    a, b, c, d = _SNAPSHOT["solidCpPolynomial_J_kgK"]
    ak, bk = _SNAPSHOT["solidConductivityLinear_W_mK"]
    cp_s_fun = lambda temp: a + b * temp + c * temp**2 + d * temp**3
    k_s_fun = lambda temp: ak + bk * temp
    primitive = lambda temp: (a * temp + b * temp**2 / 2.0 + c * temp**3 / 3.0
                              + d * temp**4 / 4.0)
    ts, tl = _SNAPSHOT["solidus_K"], LIQUIDUS_K
    cp_s_at_solidus = cp_s_fun(ts)
    width = tl - ts
    delta = np.maximum(t - ts, 0.0)
    fraction = np.clip(delta / width, 0.0, 1.0)
    cp_s = cp_s_fun(t)
    cp_mushy = cp_s_at_solidus + (_SNAPSHOT["liquidCp_J_kgK"] - cp_s_at_solidus) * fraction
    cp = np.where(t <= ts, cp_s, cp_mushy)
    k = np.where(t <= ts, k_s_fun(t),
                 k_s_fun(ts) + (_SNAPSHOT["liquidConductivity_W_mK"] - k_s_fun(ts)) * fraction)
    h_solidus = primitive(ts) - primitive(REFERENCE_TEMPERATURE_K)
    h_solid = primitive(t) - primitive(REFERENCE_TEMPERATURE_K)
    h_mushy = (h_solidus + cp_s_at_solidus * delta
               + (_SNAPSHOT["liquidCp_J_kgK"] - cp_s_at_solidus) * delta**2 / (2.0 * width)
               + _SNAPSHOT["latentHeat_J_kg"] * fraction)
    h = np.where(t <= ts, h_solid, h_mushy)
    cp_eff = np.where(t <= ts, cp, cp + _SNAPSHOT["latentHeat_J_kg"] / width)
    return cp, cp_eff, k, h


def _temperature_from_enthalpy_numpy(enthalpy):
    h = np.asarray(enthalpy, dtype=np.float64)
    h0 = _law_numpy(np.asarray(REFERENCE_TEMPERATURE_K))[3]
    h1 = _law_numpy(np.asarray(LIQUIDUS_K))[3]
    if not np.isfinite(h).all() or (h < h0).any() or (h > h1).any():
        raise ValueError("enthalpy crosses bounded IN625 temperature interval; rejecting step")
    lo = np.full(h.shape, REFERENCE_TEMPERATURE_K, dtype=np.float64)
    hi = np.full(h.shape, LIQUIDUS_K, dtype=np.float64)
    for _ in range(60):
        mid = (lo + hi) / 2.0
        hm = _law_numpy(mid)[3]
        below = hm < h
        lo = np.where(below, mid, lo)
        hi = np.where(below, hi, mid)
    return (lo + hi) / 2.0


def _temperature_from_enthalpy_torch(enthalpy, law, h0, h1, torch):
    """Invert bounded CUDA enthalpy without revalidating each bisection midpoint."""
    if (not bool(torch.isfinite(enthalpy).all())
            or bool((enthalpy < h0).any()) or bool((enthalpy > h1).any())):
        raise ValueError("enthalpy crosses bounded IN625 temperature interval; rejecting step")
    lo = torch.full_like(enthalpy, REFERENCE_TEMPERATURE_K)
    hi = torch.full_like(enthalpy, LIQUIDUS_K)
    for _ in range(60):
        mid = (lo + hi) / 2.0
        below = law(mid, validate=False)[3] < enthalpy
        lo, hi = torch.where(below, mid, lo), torch.where(below, hi, mid)
    return (lo + hi) / 2.0


if _wp is not None:
    @_wp.func
    def _in625_specific_enthalpy_warp(t: _wp.float64, reference: _wp.float64,
                                      solidus: _wp.float64, liquidus: _wp.float64,
                                      a: _wp.float64, b: _wp.float64, c: _wp.float64,
                                      d: _wp.float64, liquid_cp: _wp.float64,
                                      latent: _wp.float64) -> _wp.float64:
        hs = (a*solidus + b*solidus*solidus/_wp.float64(2.0)
              + c*solidus*solidus*solidus/_wp.float64(3.0)
              + d*solidus*solidus*solidus*solidus/_wp.float64(4.0)
              - (a*reference + b*reference*reference/_wp.float64(2.0)
                 + c*reference*reference*reference/_wp.float64(3.0)
                 + d*reference*reference*reference*reference/_wp.float64(4.0)))
        if t <= solidus:
            return (a*t + b*t*t/_wp.float64(2.0) + c*t*t*t/_wp.float64(3.0)
                    + d*t*t*t*t/_wp.float64(4.0)
                    - (a*reference + b*reference*reference/_wp.float64(2.0)
                       + c*reference*reference*reference/_wp.float64(3.0)
                       + d*reference*reference*reference*reference/_wp.float64(4.0)))
        cs = a + b*solidus + c*solidus*solidus + d*solidus*solidus*solidus
        delta = t-solidus
        width = liquidus-solidus
        fraction = delta/width
        return (hs + cs*delta + (liquid_cp-cs)*delta*delta/(_wp.float64(2.0)*width)
                + latent*fraction)


    @_wp.kernel
    def _in625_inverse_bisection_kernel(enthalpy: _wp.array(dtype=_wp.float64),
                                        temperature: _wp.array(dtype=_wp.float64),
                                        count: _wp.int32, reference: _wp.float64,
                                        solidus: _wp.float64, liquidus: _wp.float64,
                                        a: _wp.float64, b: _wp.float64, c: _wp.float64,
                                        d: _wp.float64, liquid_cp: _wp.float64,
                                        latent: _wp.float64):
        i = _wp.tid()
        if i < count:
            target = enthalpy[i]
            lo = reference
            hi = liquidus
            for _ in range(60):
                mid = (lo+hi)/_wp.float64(2.0)
                below = _in625_specific_enthalpy_warp(
                    mid, reference, solidus, liquidus, a, b, c, d, liquid_cp, latent
                ) < target
                if below:
                    lo = mid
                else:
                    hi = mid
            temperature[i] = (lo+hi)/_wp.float64(2.0)


def _temperature_from_enthalpy_warp(enthalpy, h0, h1, torch):
    """Invert IN625 enthalpy in one CUDA kernel while retaining 60 bisections."""
    if _wp is None:
        raise RuntimeError("Warp is unavailable for the fused IN625 CUDA inverse")
    if (not bool(torch.isfinite(enthalpy).all())
            or bool((enthalpy < h0).any()) or bool((enthalpy > h1).any())):
        raise ValueError("enthalpy crosses bounded IN625 temperature interval; rejecting step")
    _wp.init()
    contiguous = enthalpy.contiguous()
    result = torch.empty_like(contiguous)
    input_wp = _wp.from_torch(contiguous.reshape(-1), dtype=_wp.float64)
    output_wp = _wp.from_torch(result.reshape(-1), dtype=_wp.float64)
    stream = _wp.stream_from_torch(torch.cuda.current_stream(device=enthalpy.device))
    coefficients = _SNAPSHOT["solidCpPolynomial_J_kgK"]
    with _wp.ScopedStream(stream, sync_enter=False, sync_exit=False):
        _wp.launch(
            kernel=_in625_inverse_bisection_kernel,
            dim=contiguous.numel(),
            inputs=[input_wp, output_wp, contiguous.numel(), REFERENCE_TEMPERATURE_K,
                    _SNAPSHOT["solidus_K"], LIQUIDUS_K, *coefficients,
                    _SNAPSHOT["liquidCp_J_kgK"], _SNAPSHOT["latentHeat_J_kg"]],
            device=str(enthalpy.device),
        )
    return result


def _conductive_power_numpy(temperature, conductivity, cfg):
    nx, ny, nz = cfg.shape_xyz
    dx, dy, dz = map(float, cfg.cell_size_m)
    net = np.zeros_like(temperature)
    # Grid order is (z, y, x); harmonic face conductivity conserves pair flux.
    for axis, spacing, area in ((2, dx, dy*dz), (1, dy, dx*dz), (0, dz, dx*dy)):
        left = [slice(None)] * 3
        right = [slice(None)] * 3
        left[axis], right[axis] = slice(None, -1), slice(1, None)
        left, right = tuple(left), tuple(right)
        harmonic = 2.0 * conductivity[left] * conductivity[right] / (conductivity[left] + conductivity[right])
        power = harmonic * area / spacing * (temperature[right] - temperature[left])
        net[left] += power
        net[right] -= power
    return net


def _source_capture_fraction(cfg, step):
    """Continuous Gaussian power fraction represented by the lateral domain."""
    nx, ny, _ = cfg.shape_xyz
    dx, dy, _ = map(float, cfg.cell_size_m)
    center_x = cfg.scan_start_x_m + cfg.scan_velocity_x_m_s * cfg.dt_s * step
    root_two_sigma = math.sqrt(2.0) * cfg.spot_sigma_m
    x_fraction = 0.5 * (
        math.erf((nx * dx - center_x) / root_two_sigma)
        - math.erf((0.0 - center_x) / root_two_sigma)
    )
    y_fraction = 0.5 * (
        math.erf((ny * dy - cfg.scan_y_m) / root_two_sigma)
        - math.erf((0.0 - cfg.scan_y_m) / root_two_sigma)
    )
    return x_fraction * y_fraction


def _source_numpy(cfg, step):
    nx, ny, _ = cfg.shape_xyz
    dx, dy, _ = map(float, cfg.cell_size_m)
    x = (np.arange(nx) + 0.5) * dx
    y = (np.arange(ny) + 0.5) * dy
    center_x = cfg.scan_start_x_m + cfg.scan_velocity_x_m_s * cfg.dt_s * step
    capture = require_source_capture(
        _source_capture_fraction(cfg, step), MINIMUM_SOURCE_CAPTURE_FRACTION
    )
    with np.errstate(over="ignore"):
        weights = np.exp(-0.5 * (((x[None, :] - center_x) / cfg.spot_sigma_m)**2
                                 + ((y[:, None] - cfg.scan_y_m) / cfg.spot_sigma_m)**2))
    weight_sum = float(weights.sum())
    if not math.isfinite(weight_sum) or weight_sum <= 0.0:
        raise ValueError("surface source is unresolved on this grid; increase spot_sigma_m")
    weights /= weight_sum
    source = np.zeros((cfg.shape_xyz[2], ny, nx), dtype=np.float64)
    source[-1] = cfg.absorbed_power_W * weights
    return source, capture


def run_cpu(config: BareplateConfig = BareplateConfig()) -> BareplateResult:
    """Run the NumPy reference path; all boundaries are zero-flux/adiabatic."""
    _validate(config)
    nx, ny, nz = config.shape_xyz
    shape = (nz, ny, nx)
    temperature = np.full(shape, config.initial_temperature_K, dtype=np.float64)
    _, _, _, enthalpy = _law_numpy(temperature)
    dx, dy, dz = map(float, config.cell_size_m)
    mass = DENSITY_KG_M3 * dx * dy * dz
    times, total_enthalpy, peaks, residuals, captures = [], [], [], [], []
    initial_energy = float(enthalpy.sum() * mass)
    expected_energy = initial_energy
    for step in range(config.steps):
        _, _, conductivity, _ = _law_numpy(temperature)
        source, capture = _source_numpy(config, step)
        captures.append(capture)
        candidate_h = enthalpy + config.dt_s * (_conductive_power_numpy(temperature, conductivity, config) + source) / mass
        candidate_t = _temperature_from_enthalpy_numpy(candidate_h)
        if (candidate_t > LIQUIDUS_K).any():
            raise ValueError("step exceeds IN625 liquidus bound; no clipping or superheat is allowed")
        enthalpy, temperature = candidate_h, candidate_t
        expected_energy += config.absorbed_power_W * config.dt_s
        energy = float(enthalpy.sum() * mass)
        times.append((step + 1) * config.dt_s)
        total_enthalpy.append(energy)
        peaks.append(float(temperature.max()))
        residuals.append(energy - expected_energy)
    return BareplateResult(temperature, enthalpy, np.asarray(times), np.asarray(total_enthalpy),
                           np.asarray(peaks), np.asarray(residuals),
                           _metadata(config, "numpy", min(captures)))


def _metadata(config, backend, source_capture_fraction):
    return {
        "alloyId": "in625",
        "materialRevisionSha256": MATERIAL_REVISION_SHA256,
        "validationStatus": MODEL_STATUS,
        "solverModel": "3D cell-centered conduction, enthalpy inversion, adiabatic boundaries",
        "boundaryConditions": "zero-flux on all six faces",
        "sourceModel": "moving normalized Gaussian top-surface flux; absorbed W is explicit input",
        "sourceCaptureFractionMinimum": source_capture_fraction,
        "sourceCaptureThreshold": MINIMUM_SOURCE_CAPTURE_FRACTION,
        "absorbedPower_W": config.absorbed_power_W,
        "density_kg_m3": DENSITY_KG_M3,
        "densityBasis": DENSITY_BASIS,
        "densitySource": DENSITY_SOURCE_URL,
        "temperatureBounds_K": [REFERENCE_TEMPERATURE_K, LIQUIDUS_K],
        "backend": backend,
        "device": "cpu" if backend == "numpy" else backend,
        "powderOrMeltPoolClaim": False,
    }


def run_cuda(config: BareplateConfig = BareplateConfig(), device: str = "cuda:0") -> BareplateResult:
    """Run explicit CUDA device path. It fails closed and never falls back to CPU."""
    _validate(config)
    if not isinstance(device, str) or not device.startswith("cuda:"):
        raise ValueError("device must be an explicit CUDA device such as 'cuda:0'")
    try:
        import torch
    except ImportError as error:
        raise RuntimeError("PyTorch is required for the explicit CUDA path") from error
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; explicit CUDA path cannot run")
    try:
        dev = torch.device(device)
        if dev.index is None or dev.index < 0 or dev.index >= torch.cuda.device_count():
            raise ValueError("requested CUDA device index is unavailable")
    except (RuntimeError, ValueError) as error:
        raise ValueError(f"invalid or unavailable CUDA device {device!r}") from error
    nx, ny, nz = config.shape_xyz
    shape = (nz, ny, nx)
    dtype = torch.float64
    temperature = torch.full(shape, config.initial_temperature_K, dtype=dtype, device=dev)
    cp_poly = torch.tensor(_SNAPSHOT["solidCpPolynomial_J_kgK"], dtype=dtype, device=dev)
    k_linear = torch.tensor(_SNAPSHOT["solidConductivityLinear_W_mK"], dtype=dtype, device=dev)

    def law(t, *, validate=True):
        if validate and (not bool(torch.isfinite(t).all())
                         or bool((t < REFERENCE_TEMPERATURE_K).any())
                         or bool((t > LIQUIDUS_K).any())):
            raise ValueError("temperature outside bounded IN625 enthalpy law")
        a, b, c, d = cp_poly.unbind()
        ak, bk = k_linear.unbind()
        prim = lambda q: a*q + b*q**2/2.0 + c*q**3/3.0 + d*q**4/4.0
        cp_s_fun = lambda q: a + b*q + c*q**2 + d*q**3
        ks = lambda q: ak + bk*q
        ts, tl = _SNAPSHOT["solidus_K"], LIQUIDUS_K
        cs = cp_s_fun(ts)
        width = tl - ts
        delta = torch.clamp(t - ts, min=0.0)
        fraction = torch.clamp(delta / width, min=0.0, max=1.0)
        cps = cp_s_fun(t)
        cp_m = cs + (_SNAPSHOT["liquidCp_J_kgK"] - cs) * fraction
        cp = torch.where(t <= ts, cps, cp_m)
        k = torch.where(t <= ts, ks(t), ks(ts) + (_SNAPSHOT["liquidConductivity_W_mK"] - ks(ts))*fraction)
        hs = prim(ts) - prim(REFERENCE_TEMPERATURE_K)
        hm = (hs + cs*delta + (_SNAPSHOT["liquidCp_J_kgK"] - cs)*delta**2/(2.0*width)
              + _SNAPSHOT["latentHeat_J_kg"]*fraction)
        h = torch.where(t <= ts, prim(t)-prim(REFERENCE_TEMPERATURE_K), hm)
        cp_eff = torch.where(t <= ts, cp, cp + _SNAPSHOT["latentHeat_J_kg"] / width)
        return cp, cp_eff, k, h

    # These endpoint values use the same Torch arithmetic as the field law, but
    # are scalar constants computed once instead of full-field tensors each step.
    h0 = law(torch.full((), REFERENCE_TEMPERATURE_K, dtype=dtype, device=dev))[3]
    h1 = law(torch.full((), LIQUIDUS_K, dtype=dtype, device=dev))[3]

    def inverse(h):
        if _wp is not None:
            return _temperature_from_enthalpy_warp(h, h0, h1, torch)
        return _temperature_from_enthalpy_torch(h, law, h0, h1, torch)

    def conductive_power(t, conductivity):
        net = torch.zeros_like(t)
        dx, dy, dz = map(float, config.cell_size_m)
        for axis, spacing, area in ((2, dx, dy*dz), (1, dy, dx*dz), (0, dz, dx*dy)):
            l, r = [slice(None)]*3, [slice(None)]*3
            l[axis], r[axis] = slice(None, -1), slice(1, None)
            l, r = tuple(l), tuple(r)
            harmonic = 2*conductivity[l]*conductivity[r]/(conductivity[l]+conductivity[r])
            q = harmonic*area/spacing*(t[r]-t[l])
            net[l] = net[l]+q
            net[r] = net[r]-q
        return net

    def source(step):
        dx, dy, _ = map(float, config.cell_size_m)
        x = (torch.arange(nx, dtype=dtype, device=dev)+0.5)*dx
        y = (torch.arange(ny, dtype=dtype, device=dev)+0.5)*dy
        cx = config.scan_start_x_m + config.scan_velocity_x_m_s*config.dt_s*step
        capture = require_source_capture(
            _source_capture_fraction(config, step), MINIMUM_SOURCE_CAPTURE_FRACTION
        )
        weights = torch.exp(-0.5*(((x[None,:]-cx)/config.spot_sigma_m)**2
                                  + ((y[:,None]-config.scan_y_m)/config.spot_sigma_m)**2))
        if not bool(torch.isfinite(weights).all()) or float(weights.sum().item()) <= 0.0:
            raise ValueError("surface source is unresolved on this grid; increase spot_sigma_m")
        weights = weights/weights.sum()
        result = torch.zeros(shape, dtype=dtype, device=dev)
        result[-1] = config.absorbed_power_W*weights
        return result, capture

    _, _, _, enthalpy = law(temperature)
    dx, dy, dz = map(float, config.cell_size_m)
    mass = DENSITY_KG_M3*dx*dy*dz
    initial_energy = float((enthalpy.sum()*mass).item())
    expected_energy = initial_energy
    times, energies, peaks, residuals, captures = [], [], [], [], []
    for step in range(config.steps):
        _, _, conductivity, _ = law(temperature)
        source_field, capture = source(step)
        captures.append(capture)
        candidate_h = enthalpy + config.dt_s*(conductive_power(temperature, conductivity)+source_field)/mass
        candidate_t = inverse(candidate_h)
        if bool((candidate_t > LIQUIDUS_K).any()):
            raise ValueError("step exceeds IN625 liquidus bound; no clipping or superheat is allowed")
        enthalpy, temperature = candidate_h, candidate_t
        expected_energy += config.absorbed_power_W*config.dt_s
        energy = float((enthalpy.sum()*mass).item())
        times.append((step+1)*config.dt_s)
        energies.append(energy)
        peaks.append(float(temperature.max().item()))
        residuals.append(energy-expected_energy)
    return BareplateResult(temperature.detach(), enthalpy.detach(),
                           torch.tensor(times, dtype=dtype, device=dev),
                           torch.tensor(energies, dtype=dtype, device=dev),
                           torch.tensor(peaks, dtype=dtype, device=dev),
                           torch.tensor(residuals, dtype=dtype, device=dev),
                           _metadata(config, device, min(captures)))
