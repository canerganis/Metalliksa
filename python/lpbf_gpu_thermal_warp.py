"""Opt-in Warp candidate for the bounded enthalpy-fv-6 CUDA thermal pilot.

This module deliberately is not wired into the queue or default solver. It
keeps the existing CPU GL2 source integrator and timestep limiter, while Warp
fuses constitutive lookup, finite-volume conduction, enthalpy advancement and
enthalpy inversion into a small number of explicit CUDA kernels per step.
"""

from __future__ import annotations

import math
import re
import time

import numpy as np

try:
    import warp as wp
except ImportError:  # Fail closed at call time; never route to the Torch solver.
    wp = None

from lpbf_core_physics import calculate_mesh_domain, scan_segments, thermal_si_inputs
from lpbf_heat_source import (MINIMUM_SOURCE_CAPTURE_FRACTION,
                              require_source_capture, source_limited_step)
from lpbf_material_registry import enthalpy_table, property_at
from lpbf_peak import PeakMeltTracker
from lpbf_simulation import validate


WARP_SOLVER_ID = "enthalpy-fv-6-warp-candidate-1"
MAX_CELLS = 100_000
MAX_STEPS = 20_000


def _require_warp_cuda(device: str):
    if not isinstance(device, str) or re.fullmatch(r"cuda:[0-9]+", device) is None:
        raise ValueError("Explicit cuda:N device required; no CPU fallback")
    if wp is None:
        raise RuntimeError("Warp is unavailable; explicit Warp CUDA candidate cannot run")
    try:
        wp.init()
        warp_device = wp.get_device(device)
        if not warp_device.is_cuda or warp_device.ordinal != int(device[5:]):
            raise RuntimeError(f"Warp device {device} is not CUDA")
    except Exception as exc:
        raise RuntimeError(f"Warp CUDA device {device} unavailable; no CPU fallback") from exc
    return warp_device


if wp is not None:
    @wp.func
    def _linear_interp(value: wp.float64, xp: wp.array(dtype=wp.float64),
                       fp: wp.array(dtype=wp.float64), count: int) -> wp.float64:
        if value <= xp[0]:
            return fp[0]
        if value >= xp[count - 1]:
            return fp[count - 1]
        lo = wp.int32(0)
        hi = wp.int32(count - 1)
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if value < xp[mid]:
                hi = mid
            else:
                lo = mid
        return fp[lo] + (value - xp[lo]) * (fp[hi] - fp[lo]) / (xp[hi] - xp[lo])


    @wp.kernel
    def _constitutive_kernel(
        temperature: wp.array(dtype=wp.float64),
        ever: wp.array(dtype=wp.uint8),
        powder: wp.array(dtype=wp.uint8),
        rho: wp.array(dtype=wp.float64),
        table_t: wp.array(dtype=wp.float64),
        table_k: wp.array(dtype=wp.float64),
        table_cp: wp.array(dtype=wp.float64),
        table_count: int,
        powder_ratio: wp.float64,
        k_out: wp.array(dtype=wp.float64),
        cp_out: wp.array(dtype=wp.float64),
    ):
        i = wp.tid()
        t = temperature[i]
        k = _linear_interp(t, table_t, table_k, table_count)
        cp = _linear_interp(t, table_t, table_cp, table_count)
        if powder[i] != 0 and ever[i] == 0:
            k = k * powder_ratio
        k_out[i] = k
        cp_out[i] = cp


    @wp.kernel
    def _finite_volume_kernel(
        temperature: wp.array(dtype=wp.float64),
        k: wp.array(dtype=wp.float64),
        active: wp.array(dtype=wp.uint8),
        rho: wp.array(dtype=wp.float64),
        cp: wp.array(dtype=wp.float64),
        nx: int,
        ny: int,
        nz: int,
        top_index: int,
        dx: wp.float64,
        t0: wp.float64,
        convection: wp.float64,
        emissivity: wp.float64,
        cp_floor: wp.float64,
        rate_out: wp.array(dtype=wp.float64),
        diagonal_out: wp.array(dtype=wp.float64),
        diffusivity_out: wp.array(dtype=wp.float64),
        boundary_rate_out: wp.array(dtype=wp.float64),
    ):
        i = wp.tid()
        plane = ny * nz
        ix = i // plane
        iy = (i // nz) % ny
        iz = i % nz
        rate = wp.float64(0.0)
        boundary_rate = wp.float64(0.0)
        diagonal = wp.float64(0.0)
        if active[i] != 0:
            if ix > 0:
                j = i - plane
                if active[j] != 0:
                    face = (wp.float64(2.0) * k[i] * k[j] / (k[i] + k[j])) / (dx * dx)
                    rate += face * (temperature[j] - temperature[i])
                    diagonal += face
            if ix + 1 < nx:
                j = i + plane
                if active[j] != 0:
                    face = (wp.float64(2.0) * k[i] * k[j] / (k[i] + k[j])) / (dx * dx)
                    rate += face * (temperature[j] - temperature[i])
                    diagonal += face
            if iy > 0:
                j = i - nz
                if active[j] != 0:
                    face = (wp.float64(2.0) * k[i] * k[j] / (k[i] + k[j])) / (dx * dx)
                    rate += face * (temperature[j] - temperature[i])
                    diagonal += face
            if iy + 1 < ny:
                j = i + nz
                if active[j] != 0:
                    face = (wp.float64(2.0) * k[i] * k[j] / (k[i] + k[j])) / (dx * dx)
                    rate += face * (temperature[j] - temperature[i])
                    diagonal += face
            if iz > 0:
                j = i - 1
                if active[j] != 0:
                    face = (wp.float64(2.0) * k[i] * k[j] / (k[i] + k[j])) / (dx * dx)
                    rate += face * (temperature[j] - temperature[i])
                    diagonal += face
            if iz + 1 < nz:
                j = i + 1
                if active[j] != 0:
                    face = (wp.float64(2.0) * k[i] * k[j] / (k[i] + k[j])) / (dx * dx)
                    rate += face * (temperature[j] - temperature[i])
                    diagonal += face
            if iz == 0:
                bottom = wp.float64(2.0) * k[i] * (temperature[i] - t0) / (dx * dx)
                rate -= bottom
                boundary_rate -= bottom
                diagonal += wp.float64(2.0) * k[i] / (dx * dx)
            if iz == top_index:
                t = temperature[i]
                surface_loss = (convection * (t - t0)
                    + emissivity * wp.float64(5.670374419e-8) * (t*t*t*t - t0*t0*t0*t0)) / dx
                rate -= surface_loss
                boundary_rate -= surface_loss
                diagonal += (convection + emissivity * wp.float64(5.670374419e-8)
                    * (t+t0) * (t*t+t0*t0)) / dx
        rate_out[i] = rate
        boundary_rate_out[i] = boundary_rate
        diagonal_out[i] = diagonal
        diffusivity_out[i] = k[i] / (rho[i] * cp[i])


    @wp.kernel
    def _enthalpy_update_kernel(
        temperature: wp.array(dtype=wp.float64),
        enthalpy: wp.array(dtype=wp.float64),
        rate: wp.array(dtype=wp.float64),
        source: wp.array(dtype=wp.float64),
        rho: wp.array(dtype=wp.float64),
        active: wp.array(dtype=wp.uint8),
        ever: wp.array(dtype=wp.uint8),
        table_h: wp.array(dtype=wp.float64),
        table_t: wp.array(dtype=wp.float64),
        table_count: int,
        h0: wp.float64,
        liquidus: wp.float64,
        dt: wp.float64,
        invalid: wp.array(dtype=wp.int32),
    ):
        i = wp.tid()
        h_vol = enthalpy[i] + dt * (rate[i] + source[i])
        h_specific = h_vol / rho[i] + h0
        if not wp.isfinite(h_specific):
            wp.atomic_max(invalid, 0, 1)
            return
        value = _linear_interp(h_specific, table_h, table_t, table_count)
        temperature[i] = value
        enthalpy[i] = h_vol
        if value >= liquidus and active[i] != 0:
            ever[i] = wp.uint8(1)


    @wp.kernel
    def _cell_integer_kernel(values: wp.array(dtype=wp.int32), value: int):
        i = wp.tid()
        values[i] = value


def _launch_candidate_kernel(kernel, *, dim, inputs, device):
    """Avoid Warp's Windows NVRTC PCH temp-directory path for this opt-in run.

    The local execution sandbox denies access to the PCH directories Warp
    creates, while ordinary NVRTC compilation works. Restore the process-wide
    option immediately after compilation/launch so this candidate does not
    change compilation behavior for other Warp users.
    """
    use_pch = wp.config.use_precompiled_headers
    wp.config.use_precompiled_headers = False
    try:
        wp.launch(kernel, dim=dim, inputs=inputs, device=device)
    finally:
        wp.config.use_precompiled_headers = use_pch


def _boundary_loss_for_step(total_rate, boundary_rate, cell_volume, dt):
    """Return explicit bottom/surface losses after checking internal FV conservation."""
    total_rate = np.asarray(total_rate, dtype=np.float64)
    boundary_rate = np.asarray(boundary_rate, dtype=np.float64)
    if (total_rate.ndim != 1 or boundary_rate.shape != total_rate.shape
            or not np.isfinite(total_rate).all() or not np.isfinite(boundary_rate).all()
            or not math.isfinite(cell_volume) or cell_volume <= 0
            or not math.isfinite(dt) or dt <= 0):
        raise ValueError("Warp candidate energy ledger received invalid step rates")

    conductive_rate = total_rate - boundary_rate
    conductive_net = float(np.sum(conductive_rate, dtype=np.float64))
    conductive_scale = float(np.sum(np.abs(conductive_rate), dtype=np.float64))
    rate_scale = max(float(np.sum(np.abs(total_rate), dtype=np.float64)),
                     float(np.sum(np.abs(boundary_rate), dtype=np.float64)))
    conservation_tolerance = 64.0 * np.finfo(np.float64).eps * max(conductive_scale, rate_scale, 1e-300)
    if abs(conductive_net) > conservation_tolerance:
        raise ValueError("Warp candidate internal conductive rates do not cancel")

    volume_dt = cell_volume * dt
    explicit_loss = -float(np.sum(boundary_rate, dtype=np.float64)) * volume_dt
    total_rate_loss = -float(np.sum(total_rate, dtype=np.float64)) * volume_dt
    conductive_net_energy = conductive_net * volume_dt
    summation_scale = volume_dt * max(
        float(np.sum(np.abs(total_rate), dtype=np.float64)),
        float(np.sum(np.abs(boundary_rate), dtype=np.float64)))
    ledger_tolerance = 128.0 * np.finfo(np.float64).eps * max(
        abs(explicit_loss), abs(total_rate_loss), abs(conductive_net_energy), summation_scale, 1e-300)
    if abs(total_rate_loss - (explicit_loss - conductive_net_energy)) > ledger_tolerance:
        raise ValueError("Warp candidate boundary energy ledger does not match total finite-volume rate")
    return explicit_loss


def _energy_closure(energy_in, energy_out, stored):
    closure = abs(energy_in - energy_out - stored) / max(energy_in, 1e-12)
    if not math.isfinite(closure) or closure > .01:
        raise ValueError(f"Warp candidate energy balance failed: {closure:.3%}")
    return closure


def _validate_candidate(raw):
    if not isinstance(raw, dict):
        raise ValueError("Warp thermal candidate requires a settings object")
    resolved = dict(raw)
    resolved.pop("jobType", None)
    resolved["backend"] = "reference"
    p, material = validate(resolved)
    if (p["mode"] != "standard" or p["study"] != "none" or p["tracks"] != 1
            or p["layers"] != 1 or p["surfaceMode"] != "powder-layer"
            or p.get("measurements")):
        raise ValueError("Warp candidate supports one powder-layer track/layer, standard/reference, no study or measurements")
    if p.get("powderGridPolicy") != "layer-conforming":
        raise ValueError("Warp candidate requires the layer-conforming thermal grid")
    domain = calculate_mesh_domain(p)
    cells = domain["nx"] * domain["ny"] * domain["nz"]
    if cells > MAX_CELLS:
        raise ValueError("Warp candidate cell budget exceeded")
    return p, material, domain


def _pilot_capture_projection(coordinates_m, temperature_K, enthalpy_J_m3,
                             density_kg_m3, accepted_dt_s, *, time_s,
                             initial_temperature_K, cell_volume_m3):
    """Select the shared codec's five arrays and three scalars without reconstruction."""
    return {
        "coordinates_m": coordinates_m,
        "temperature_K": temperature_K,
        # Warp's state is volumetric excess enthalpy (J/m^3), not specific H.
        "enthalpy_J_m3": enthalpy_J_m3,
        "density_kg_m3": density_kg_m3,
        "accepted_dt_s": accepted_dt_s,
        "time_s": time_s,
        "initial_temperature_K": initial_temperature_K,
        "cell_volume_m3": cell_volume_m3,
    }


def run_warp(raw, device="cuda:0", capture_final=True, capture_pilot_state=False):
    """Run the explicit Warp candidate; unavailable Warp/CUDA always raises."""
    if type(capture_pilot_state) is not bool:
        raise ValueError("capture_pilot_state must be a boolean")
    if capture_pilot_state and not capture_final:
        raise ValueError("Pilot-state capture requires capture_final=True")
    warp_device = _require_warp_cuda(device)
    p, material, domain = _validate_candidate(raw)
    nx, ny, nz = (int(domain[key]) for key in ("nx", "ny", "nz"))
    dx = float(domain["dx"])
    span = float(domain["span"])
    substrate = float(domain["substrate_depth"])
    cells = nx * ny * nz
    radius = float(domain["radius"])
    axis = (np.arange(nx, dtype=np.float64) + .5) * dx - span / 2
    axis_y = (np.arange(ny, dtype=np.float64) + .5) * dx - ny * dx / 2
    z = (np.arange(nz, dtype=np.float64) + .5) * dx - substrate
    layer_m = p["layer_um"] * 1e-6
    zz = np.broadcast_to(z[None, None, :], (nx, ny, nz))
    active_np = (zz < layer_m).astype(np.uint8).ravel()
    powder_np = (zz > 0).ravel()
    if not np.any(z < 0) or not np.any((z >= 0) & (z < layer_m)):
        raise ValueError("Mesh cannot resolve substrate and powder layer")
    xyz = np.stack(np.meshgrid(axis, axis_y, z, indexing="ij"), axis=-1).reshape(-1, 3)
    tracker = PeakMeltTracker(xyz, dx, material)

    thermal = thermal_si_inputs(p, material)
    t0 = float(thermal["preheat_K"])
    rho0 = float(property_at(material, t0, 1))
    rho_np = rho0 * np.where(powder_np, p["packingFraction"], 1.0)
    table = np.asarray(material["table"], dtype=np.float64)
    table_t_np, table_h_np = enthalpy_table(material)
    h0 = float(np.interp(t0, table_t_np, table_h_np))
    h_boil = float(np.interp(material["boiling_K"], table_t_np, table_h_np))
    cp_floor = float(np.min(table[:, 3]))
    segments, end = scan_segments(p)
    top_index = int(np.flatnonzero(z < layer_m)[-1])

    # Warp owns the evolving state. CPU source integration remains the exact
    # shared GL2 implementation and gets the passive field/capacity each step.
    temperature = wp.array(np.full(cells, t0), dtype=wp.float64, device=warp_device)
    enthalpy = wp.zeros(cells, dtype=wp.float64, device=warp_device)
    ever = wp.zeros(cells, dtype=wp.uint8, device=warp_device)
    active = wp.array(active_np, dtype=wp.uint8, device=warp_device)
    rho = wp.array(rho_np, dtype=wp.float64, device=warp_device)
    powder = wp.array(powder_np.astype(np.uint8), dtype=wp.uint8, device=warp_device)
    table_t = wp.array(table[:, 0].copy(), dtype=wp.float64, device=warp_device)
    table_k = wp.array(table[:, 2].copy(), dtype=wp.float64, device=warp_device)
    table_cp = wp.array(table[:, 3].copy(), dtype=wp.float64, device=warp_device)
    table_h = wp.array(table_h_np, dtype=wp.float64, device=warp_device)
    inverse_t = wp.array(table_t_np, dtype=wp.float64, device=warp_device)
    k = wp.zeros(cells, dtype=wp.float64, device=warp_device)
    cp = wp.zeros(cells, dtype=wp.float64, device=warp_device)
    rate = wp.zeros(cells, dtype=wp.float64, device=warp_device)
    boundary_rate = wp.zeros(cells, dtype=wp.float64, device=warp_device)
    diagonal = wp.zeros(cells, dtype=wp.float64, device=warp_device)
    diffusivity = wp.zeros(cells, dtype=wp.float64, device=warp_device)
    source = wp.zeros(cells, dtype=wp.float64, device=warp_device)
    invalid = wp.zeros(1, dtype=wp.int32, device=warp_device)
    cp_host = np.empty(cells, dtype=np.float64)
    rate_host = np.empty(cells, dtype=np.float64)
    boundary_rate_host = np.empty(cells, dtype=np.float64)
    diagonal_host = np.empty(cells, dtype=np.float64)
    diffusivity_host = np.empty(cells, dtype=np.float64)
    min_dt = float(p["maxDt_s"])
    max_dt = 0.0
    energy_in = energy_out = peak = 0.0
    peak = t0
    time_s = 0.0
    step = 0
    source_retries = 0
    accepted_dt_s = [] if capture_pilot_state else None
    sigma = 5.670374419e-8
    liquidus = float(material["liquidus_K"])
    capture_min = 1.0

    while time_s < end:
        if step >= MAX_STEPS:
            raise ValueError("Warp candidate timestep budget exceeded")
        segment = next((item for item in segments
                        if item["start_s"] <= time_s + 1e-14
                        and time_s < item["end_s"] - 1e-14), None)
        _launch_candidate_kernel(
            _constitutive_kernel, dim=cells,
            inputs=[temperature, ever, powder, rho, table_t, table_k,
                    table_cp, table.shape[0], float(p["powderConductivityRatio"]), k, cp],
            device=warp_device)
        _launch_candidate_kernel(
            _finite_volume_kernel, dim=cells,
            inputs=[temperature, k, active, rho, cp, nx, ny, nz, top_index,
                    dx, t0, float(p["convection_W_m2K"]),
                    float(material["emissivity"]), cp_floor, rate, diagonal,
                     diffusivity, boundary_rate], device=warp_device)
        # These five bulk transfers replace the Torch path's many elementwise
        # launches and reductions. Source remains CPU-authoritative by design.
        cp_host[:] = cp.numpy()
        rate_host[:] = rate.numpy()
        boundary_rate_host[:] = boundary_rate.numpy()
        diagonal_host[:] = diagonal.numpy()
        diffusivity_host[:] = diffusivity.numpy()
        wp.synchronize_device(warp_device)
        dt = min(float(p["maxDt_s"]), .12 * dx * dx / float(np.max(diffusivity_host)),
                 radius / (4.0 * thermal["speed_m_s"]), end - time_s)
        events = [item[key] - time_s for item in segments for key in ("start_s", "end_s")
                  if item[key] > time_s + 1e-14]
        if events:
            dt = min(dt, min(events))
        stable = .9 * rho_np * cp_floor / np.maximum(diagonal_host, 1e-30)
        dt = min(dt, float(np.min(stable)))
        capacity_host = rho_np * cp_host
        dt, source_np, _, capture, retries = source_limited_step(
            axis, z, dx, segment, time_s, dt, layer_m, radius, layer_m,
            thermal["absorbed_power_W"], rate_host.reshape(nx, ny, nz),
            capacity_host.reshape(nx, ny, nz), axis_y=axis_y)
        require_source_capture(capture, MINIMUM_SOURCE_CAPTURE_FRACTION)
        capture_min = min(capture_min, capture)
        source_retries += retries
        # Host source is copied to this fixed device buffer and the state update
        # plus table inversion are fused in one kernel launch.
        wp.copy(source, wp.array(np.ascontiguousarray(source_np).ravel(),
                                 dtype=wp.float64, device="cpu"))
        _launch_candidate_kernel(_cell_integer_kernel, dim=1,
                                 inputs=[invalid, 0], device=warp_device)
        _launch_candidate_kernel(
            _enthalpy_update_kernel, dim=cells,
            inputs=[temperature, enthalpy, rate, source, rho, active, ever,
                    table_h, inverse_t, len(table_h_np), h0, liquidus, dt, invalid],
            device=warp_device)
        invalid_host = invalid.numpy()
        if int(invalid_host[0]) != 0:
            raise ValueError("Warp thermal candidate produced a nonfinite enthalpy")

        time_s += dt
        if accepted_dt_s is not None:
            accepted_dt_s.append(dt)
        roundoff = min(1e-14, 2 * math.ulp(end) * (step + 1))
        if end - time_s <= roundoff:
            time_s = end
        step += 1
        min_dt = min(min_dt, dt)
        max_dt = max(max_dt, dt)
        energy_in += float(source_np.sum()) * dx**3 * dt
        # Count the modeled bottom and exposed-surface fluxes directly, while
        # independently checking that internal face fluxes cancel each step.
        energy_out += _boundary_loss_for_step(rate_host, boundary_rate_host, dx**3, dt)

        # Pull the field only for melt/tracker updates. A few comparisons are
        # deliberately on CPU to retain the existing PeakMeltTracker contract.
        temperature_host = temperature.numpy()
        if (not np.isfinite(temperature_host).all()
                or np.min(enthalpy_host := enthalpy.numpy() / rho_np + h0) < table_h_np[0] - 1e-8
                or np.max(enthalpy_host) >= h_boil):
            raise ValueError("Warp thermal model validity exceeded (boiling or nonphysical enthalpy)")
        melt = (temperature_host >= liquidus) & (active_np != 0)
        melt_count = int(np.count_nonzero(melt))
        if melt_count > tracker.count:
            tracker.observe(temperature_host, layer_m, p["scanAngle_deg"], time_s, step, sampled=True)
        peak = max(peak, float(np.max(temperature_host)))

    if capture_pilot_state:
        # Synchronize once before the final full-state readback. Captured fields
        # come from the actual evolving Warp arrays; no H(T) reconstruction or
        # per-step full-field capture is performed.
        wp.synchronize_device(warp_device)
        enthalpy_host = enthalpy.numpy()
        temperature_host = temperature.numpy()
        density_host = rho.numpy()
    else:
        enthalpy_host = enthalpy.numpy()
        temperature_host = temperature.numpy()
    stored = float(np.sum(enthalpy_host)) * dx**3
    closure = _energy_closure(energy_in, energy_out, stored)
    metrics, extraction = tracker.finish(None, step)
    metrics["peakTemperature_K"] = peak
    result = {
        "solver": {"id": WARP_SOLVER_ID,
                   "modelId": "stationary-enthalpy-conduction-layer-conforming-v1",
                   "actualBackend": device, "thermalEvolutionDevice": device,
                   "sourceIntegrationDevice": "cpu", "sourceTimestepLimiterDevice": "cpu",
                   "dtype": "float64"},
        "material": {key: material[key] for key in
                     ("name", "materialId", "materialRevisionSha256", "version")},
        "settings": p, "metrics": metrics, "peakExtraction": extraction,
        "energyBalance": {"input_J": energy_in, "losses_J": energy_out,
                          "stored_J": stored, "relativeError": closure},
        "discretization": {"cells": cells, "mesh_m": dx,
                           "minimumDt_s": min_dt, "maximumDt_s": max_dt,
                           "meanDt_s": end / step, "steps": step},
        "validationStatus": "unvalidated", "productionReady": False,
        "warpCandidate": {"status": "not-yet-compared", "sourceCaptureMinimum": capture_min,
                          "sourceRetries": source_retries},
    }
    if capture_final:
        field = {"temperature_K": temperature_host,
                 "coordinates_m": xyz, "time_s": time_s,
                 "surface_m": layer_m, "steps": step}
        if capture_pilot_state:
            capture = _pilot_capture_projection(
                coordinates_m=xyz,
                temperature_K=temperature_host,
                enthalpy_J_m3=enthalpy_host,
                density_kg_m3=density_host,
                accepted_dt_s=np.asarray(accepted_dt_s, dtype=np.float64),
                time_s=time_s,
                initial_temperature_K=t0,
                cell_volume_m3=dx**3,
            )
            return result, field, capture
        return result, field
    return result


def compare_with_cpu(raw, device="cuda:0"):
    """Run both solvers and apply the frozen pilot field/parity gate."""
    from lpbf_gpu_thermal import _field_parity, _run_cpu_with_final, PARITY_TARGETS

    gpu, field = run_warp(raw, device, capture_final=True)
    cpu, frame, cpu_field, cpu_coordinates = _run_cpu_with_final(raw)
    if (cpu["coreContract"]["modelId"] != gpu["solver"]["modelId"]
            or cpu["material"]["materialRevisionSha256"]
            != gpu["material"]["materialRevisionSha256"]):
        raise ValueError("CPU/Warp model or material revision mismatch")
    alignment, field_result = _field_parity(cpu, gpu, frame, cpu_field,
                                            cpu_coordinates, field)
    gpu["warpCandidate"].update(status=field_result["status"],
                                finalSampling=alignment,
                                finalTemperatureField=field_result,
                                targets=dict(PARITY_TARGETS))
    return {"status": field_result["status"], "gpu": gpu,
            "cpu": {"discretization": cpu["discretization"],
                    "coreContract": cpu["coreContract"],
                    "material": cpu["material"]},
            "comparisons": {"finalSampling": alignment,
                            "finalTemperatureField": field_result},
            "experimentalValidation": False}


def benchmark_alternating(raw, device="cuda:0", repeats=3):
    """Warm compilation, then alternate Torch/Warp wall timings for one case."""
    if type(repeats) is not int or repeats != 3:
        raise ValueError("Benchmark protocol is frozen to three alternating trials")
    import torch
    from lpbf_gpu_thermal import run_gpu

    _require_warp_cuda(device)
    # Compile and warm both paths outside the measured alternating sequence.
    run_gpu(raw, device, capture_final=False, use_cuda_source=False)
    run_warp(raw, device, capture_final=False)
    trials = {"torch": [], "warp": []}
    order = ("torch", "warp", "warp", "torch", "torch", "warp")
    for label in order:
        torch.cuda.synchronize(device)
        started = time.perf_counter()
        if label == "torch":
            result = run_gpu(raw, device, capture_final=False, use_cuda_source=False)
        else:
            result = run_warp(raw, device, capture_final=False)
        torch.cuda.synchronize(device)
        elapsed = time.perf_counter() - started
        trials[label].append({"runtime_s": elapsed,
                              "steps": result["discretization"]["steps"],
                              "cells": result["discretization"]["cells"]})
    summary = {}
    for label, entries in trials.items():
        values = np.asarray([item["runtime_s"] for item in entries], dtype=np.float64)
        summary[label] = {"trials": entries, "median_s": float(np.median(values)),
                          "spread_s": float(np.max(values) - np.min(values))}
    summary["speedRatioTorchOverWarp"] = summary["torch"]["median_s"] / summary["warp"]["median_s"]
    return summary
