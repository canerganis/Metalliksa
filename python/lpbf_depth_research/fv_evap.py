"""Research fork of the enthalpy-FV reference transient (enthalpy-fv-6) with evaporative cooling.

The time loop below is the frozen `lpbf_simulation.transient` algorithm (cubic grid, explicit Euler,
harmonic face conduction, isothermal bottom, convection + radiation top loss, powder slab, exact-event
stepping, source-limited retries, enthalpy inversion) reduced to the bare/powder single-track case,
with three additions that the frozen solver does not have:

1. an evaporative heat sink on the top active cell of every column (`evap_properties.heat_flux`, the
   Hertz-Knudsen-Langmuir / Anisimov mass flux with a Clausius-Clapeyron saturation pressure, times L_v),
   explicit in time and included in the row-sum stability bound;
2. a `surface-flux` heat-source option: the absorbed Gaussian deposited in the top active cell only
   (the frozen half-Gaussian-in-depth `volumetric` source stays available for the control arm);
3. the ever-melted envelope and vapour-cavity-proxy measurement operators next to the frozen
   peak-instant operator.

The enthalpy table is extended above the boiling point with the last tabulated (liquid) cp held constant
(an extrapolation, stated in every result). Not modelled (stated): recoil pressure, surface recession,
free surface, Marangoni flow, keyhole cavity. The frozen modules are imported read-only.
"""
from __future__ import annotations

import math
import sys
import time as _time
from pathlib import Path

import numpy as np

_PY = Path(__file__).resolve().parent.parent
if str(_PY) not in sys.path:
    sys.path.insert(0, str(_PY))

from lpbf_material_registry import property_at  # noqa: E402
from lpbf_core_physics import (calculate_mesh_domain, scan_segments, thermal_si_inputs,  # noqa: E402
                               gaussian_interval, integrated_source, source_gauss_rule,
                               source_time_quadrature, SOURCE_QUADRATURE_MAX_ORDER,
                               SOURCE_QUADRATURE_RELATIVE_TOLERANCE)
from lpbf_simulation import _conduction_rate_and_diagonal, validate  # noqa: E402
from lpbf_heat_source import MINIMUM_SOURCE_CAPTURE_FRACTION  # noqa: E402
from lpbf_depth_research.evap_properties import (alloy_evaporation_constants, heat_flux,  # noqa: E402
                                                 heat_flux_derivative, mass_flux)

FORK_VERSION = "fv-evap-research-1"
STEFAN_BOLTZMANN = 5.670374419e-8


def extended_enthalpy_table(m, t_max_K):
    """Frozen enthalpy law (exact piecewise-linear cp integral + latent-heat ramp) extended to t_max_K.

    Above the last table row `property_at` clamps, so cp above T_b is the tabulated liquid cp (extrapolation)."""
    t = np.unique(np.r_[np.linspace(273.15, t_max_K, 24000), np.asarray(m["table"])[:, 0],
                        m["solidus_K"], m["liquidus_K"], m["boiling_K"]])
    cp = property_at(m, t, 3)
    h = np.r_[0, np.cumsum(np.diff(t) * (cp[1:] + cp[:-1]) / 2)]
    h += m["latentHeat_J_kg"] * np.clip((t - m["solidus_K"]) / (m["liquidus_K"] - m["solidus_K"]), 0, 1)
    return t, h


def surface_flux_source(axis, axis_y, z, dx, segment, time, dt, top_index, radius, power):
    """Time-averaged volumetric rate [W/m^3] of the absorbed Gaussian deposited in the top active cell layer.

    Lateral cell integration and the adaptive Gauss-Legendre time quadrature are the frozen ones
    (`lpbf_core_physics.integrated_source`); the depth profile is a delta at the surface cell."""
    source = np.zeros((len(axis), len(axis_y), len(z)))
    if segment is None:
        return source, 1.0
    if dt <= 0 or time < segment["start_s"] - 1e-13 or time + dt > segment["end_s"] + 1e-13:
        raise ValueError("Source interval must remain inside one laser-on segment")
    start, stop = np.asarray(segment["start"]), np.asarray(segment["end"])
    order, refine = source_time_quadrature(segment, dt, radius)
    minimum_capture = 1.0
    previous = None
    while True:
        source.fill(0.0)
        nodes, temporal_weights = source_gauss_rule(order)
        for node, temporal_weight in zip(nodes, temporal_weights):
            fraction = np.clip((time + node * dt - segment["start_s"]) / (segment["end_s"] - segment["start_s"]), 0.0, 1.0)
            position = start + fraction * (stop - start)
            gx = gaussian_interval(axis - dx / 2, axis + dx / 2, position[0], radius)
            gy = gaussian_interval(axis_y - dx / 2, axis_y + dx / 2, position[1], radius)
            weights = gx[:, None] * gy[None, :]
            total = float(weights.sum())
            if not math.isfinite(total) or total <= 0:
                raise ValueError("Gaussian source is outside the represented active domain")
            minimum_capture = min(minimum_capture, total)
            source[:, :, top_index] += weights * (temporal_weight * power / (total * dx ** 3))
        if not refine:
            return source, minimum_capture
        if previous is not None:
            if np.linalg.norm(source - previous) <= SOURCE_QUADRATURE_RELATIVE_TOLERANCE * np.linalg.norm(source):
                return source, minimum_capture
        if 2 * order > SOURCE_QUADRATURE_MAX_ORDER:
            raise ValueError("Moving source quadrature did not converge; shorten the source interval")
        previous = source.copy()
        order *= 2


def _extents(mask, axis, axis_y, z, dx):
    """Cell-supported extents of a boolean (nx, ny, nz) mask; depth below z = 0 (plate datum) and below z_top."""
    ix, iy, iz = np.nonzero(mask)
    if not len(ix):
        return dict(cells=0, length_um=0.0, width_um=0.0, depthPlate_um=0.0, depthSurface_um=0.0, reachesPlate=False)
    zs = z[iz]
    below = zs < 0
    return dict(cells=int(len(ix)),
                length_um=float((np.ptp(axis[ix]) + dx) * 1e6),
                width_um=float((np.ptp(axis_y[iy]) + dx) * 1e6),
                depthPlate_um=float((-zs[below].min() + dx / 2) * 1e6) if below.any() else 0.0,
                depthSurface_um=float((zs.max() + dx / 2 - zs.min() + dx / 2) * 1e6),
                reachesPlate=bool(below.any()))


def _plane_extents(mask_plane, axis_y, z, dx):
    """Extents on one YZ plane: width = widest extent at any depth, depth below z = 0."""
    iy, iz = np.nonzero(mask_plane)
    if not len(iy):
        return dict(cells=0, width_um=0.0, depthPlate_um=0.0, reachesPlate=False, status="no-melt")
    zs = z[iz]
    below = zs < 0
    return dict(cells=int(len(iy)), width_um=float((np.ptp(axis_y[iy]) + dx) * 1e6),
                depthPlate_um=float((-zs[below].min() + dx / 2) * 1e6) if below.any() else 0.0,
                reachesPlate=bool(below.any()), status="thermal-proxy")


def run_case(raw, *, evaporation=True, source_mode="surface-flux", boiling_stop=False,
             cell_limit=1_200_000, t_max_factor=2.0, max_steps=250_000, progress=None):
    """Run one single-track case. `raw` is a frozen-solver input dict (mode standard, backend reference).

    Returns a plain dict (JSON-serialisable) with status, operators, energy terms and timing. Raises
    ValueError on validity stops with the same wording family as the frozen solver ('boiling' in the
    message for the boiling validity stop)."""
    if source_mode not in ("surface-flux", "volumetric"):
        raise ValueError("source_mode must be 'surface-flux' or 'volumetric'")
    wall0 = _time.perf_counter()
    p, m = validate(raw)
    if p["mode"] != "standard" or p["backend"] != "reference" or p["layers"] != 1 or p["tracks"] != 1 \
            or p["scanAngle_deg"] != 0 or p.get("thermalModelId") or p["barePlateGeometry"] != "square":
        raise ValueError("fork supports standard/reference single +X track, square domain only")
    if p.get("evaporationModel"):
        raise ValueError("the frozen boiling cap is not available in the fork (no temperature cap by design)")
    thermal = thermal_si_inputs(p, m)
    layer_m, speed_m_s, absorbed_power_W, t0 = (thermal[k] for k in ("layer_m", "speed_m_s", "absorbed_power_W", "preheat_K"))
    domain = calculate_mesh_domain(p)
    radius, span, nx, ny, nz, dx, substrate = (domain[k] for k in ("radius", "span", "nx", "ny", "nz", "dx", "substrate_depth"))
    cell_count = nx * ny * nz
    if cell_count > cell_limit:
        raise ValueError(f"mesh requires {cell_count:,} cells, above the fork limit {cell_limit:,}")
    axis = (np.arange(nx) + .5) * dx - span / 2
    axis_y = (np.arange(ny) + .5) * dx - ny * dx / 2
    z = (np.arange(nz) + .5) * dx - substrate
    bare = p["surfaceMode"] == "bare-plate"
    if not bare and int(np.sum(z < layer_m)) <= int(np.sum(z < 0)):
        raise ValueError("Mesh cannot resolve the powder layer")
    x, y, zz = np.meshgrid(axis, axis_y, z, indexing="ij")
    segments, end = scan_segments(p)
    t_max = t_max_factor * m["boiling_K"]
    tt, hh = extended_enthalpy_table(m, t_max)
    h0 = float(np.interp(t0, tt, hh))
    minimum_allowed_h = float(hh[0]) - 1e-8
    boiling_h = float(np.interp(m["boiling_K"], tt, hh))
    h_max = float(hh[-1])
    T = np.full(x.shape, t0)
    rho = float(property_at(m, t0, 1)) * np.where(zz > 0, p["packingFraction"], 1.0)
    H = np.zeros_like(T)
    ever = np.zeros(T.shape, dtype=bool)
    ever_boil = np.zeros(T.shape, dtype=bool)
    midpoint_plane = int(np.argmin(np.abs(axis)))
    cp_floor = min(row[3] for row in m["table"])
    evap_c = alloy_evaporation_constants(p["material"]) if evaporation else None
    liquidus = float(m["liquidus_K"])
    boiling = float(m["boiling_K"])
    energy_in = energy_bottom = energy_surface = energy_evap = mass_evap = 0.0
    peak_count, peak_state = 0, None
    peak_T = max_surface_T = t0
    min_dt, max_dt, minimum_capture, source_retries = p["maxDt_s"], 0.0, 1.0, 0
    time, step = 0.0, 0
    penetration = p["sourcePenetration_um"] * 1e-6 if bare else layer_m
    while time < end:
        seg = next((s for s in segments if s["start_s"] <= time + 1e-14 and time < s["end_s"] - 1e-14), None)
        surface = 0.0 if bare else layer_m
        active = zz < surface
        top_index = int(np.flatnonzero(z < surface)[-1])
        k = property_at(m, T, 2) * np.where((zz > 0) & ~ever, p["powderConductivityRatio"], 1.0)
        cp = property_at(m, T, 3)
        dt = min(p["maxDt_s"], .12 * dx * dx / float(np.max(k / (rho * cp))), radius / (4 * speed_m_s), end - time)
        events = [s[v] - time for s in segments for v in ("start_s", "end_s") if s[v] > time + 1e-14]
        if events:
            dt = min(dt, min(events))
        rate, diagonal = _conduction_rate_and_diagonal(T, k, active, dx)
        bottom = 2 * k[:, :, 0] * (T[:, :, 0] - t0) / dx ** 2
        rate[:, :, 0] -= bottom
        top_T = T[:, :, top_index]
        surface_loss = (p["convection_W_m2K"] * (top_T - t0) + m["emissivity"] * STEFAN_BOLTZMANN * (top_T ** 4 - t0 ** 4)) / dx
        rate[:, :, top_index] -= surface_loss
        diagonal[:, :, 0] += 2 * k[:, :, 0] / dx ** 2
        diagonal[:, :, top_index] += (p["convection_W_m2K"] + m["emissivity"] * STEFAN_BOLTZMANN
                                      * (top_T + t0) * (top_T ** 2 + t0 ** 2)) / dx
        if evaporation:
            q_evap = heat_flux(top_T, evap_c)
            m_dot = mass_flux(top_T, evap_c)
            rate[:, :, top_index] -= q_evap / dx
            diagonal[:, :, top_index] += np.maximum(heat_flux_derivative(top_T, evap_c), 0.0) / dx
        else:
            q_evap = m_dot = None
        dt = min(dt, float(np.min(.9 * rho * cp_floor / np.maximum(diagonal, 1e-30))))
        capacity = rho * cp
        for retries in range(12):
            if source_mode == "surface-flux":
                source, capture = surface_flux_source(axis, axis_y, z, dx, seg, time, dt, top_index, radius, absorbed_power_W)
            else:
                source, capture = integrated_source(axis, z, dx, seg, time, dt, surface, radius, penetration,
                                                    absorbed_power_W, axis_y=axis_y)
            total_rate = rate + source
            allowed = float(np.min(25. * capacity / np.maximum(np.abs(total_rate), 1e-30)))
            if allowed >= dt * (1 - 1e-12):
                break
            dt = .95 * allowed
        else:
            raise ValueError("Moving-source timestep limit failed to converge")
        if capture < MINIMUM_SOURCE_CAPTURE_FRACTION:
            raise ValueError(f"Gaussian source capture {capture:.3%} below the {MINIMUM_SOURCE_CAPTURE_FRACTION:.0%} minimum")
        source_retries += retries
        minimum_capture = min(minimum_capture, capture)
        min_dt, max_dt = min(min_dt, dt), max(max_dt, dt)
        H += dt * total_rate
        h = H / rho + h0
        if not np.isfinite(h).all():
            raise ValueError("Thermal model validity exceeded (non-finite specific enthalpy)")
        minimum_h, maximum_h = float(h.min()), float(h.max())
        if minimum_h < minimum_allowed_h:
            raise ValueError(f"Thermal model validity exceeded below the property-table range ({minimum_h:.6g} J/kg)")
        if boiling_stop and maximum_h >= boiling_h:
            hot = np.unravel_index(int(np.argmax(h)), h.shape)
            raise ValueError("Thermal model validity exceeded at or above the material boiling limit "
                             f"(specific enthalpy {maximum_h:.9g} J/kg; limit {boiling_h:.9g} J/kg at {boiling:.6g} K; "
                             f"cell={tuple(int(i) for i in hot)}, previous T={float(T[hot]):.6g} K); frozen-physics arm")
        if maximum_h >= h_max:
            raise ValueError(f"Fork validity exceeded: enthalpy above the extended table ({t_max:.6g} K = {t_max_factor} T_b)")
        T = np.interp(h, hh, tt)
        time += dt
        if end - time <= min(1e-14, 2 * math.ulp(end) * (step + 1)):
            time = end
        step += 1
        energy_in += float(source.sum()) * dx ** 3 * dt
        energy_bottom += float(bottom.sum()) * dx ** 3 * dt
        energy_surface += float(surface_loss.sum()) * dx ** 3 * dt
        if evaporation:
            energy_evap += float(q_evap.sum()) * dx ** 2 * dt
            mass_evap += float(m_dot.sum()) * dx ** 2 * dt
        melt = (T >= liquidus) & active
        ever |= melt
        ever_boil |= (T >= boiling) & active
        count = int(np.count_nonzero(melt))
        if count > peak_count:
            peak_count = count
            peak_state = (T.copy(), surface, float(time), step)
        peak_T = max(peak_T, float(T.max()))
        max_surface_T = max(max_surface_T, float(T[:, :, top_index].max()))
        if progress is not None and step % 200 == 0:
            progress(time / end, step, peak_T)
        if step > max_steps:
            raise ValueError("Reference solver step budget exceeded")
    stored = float(H.sum()) * dx ** 3
    out_sum = energy_bottom + energy_surface + energy_evap + stored
    residual = abs(energy_in - out_sum) / max(energy_in, 1e-12)
    # Operators
    if peak_state is not None:
        T_pk, surf_pk, t_pk, step_pk = peak_state
        pk = _extents((T_pk >= liquidus) & (zz < surf_pk), axis, axis_y, z, dx)
        pk.update(time_s=t_pk, step=step_pk, depthModelSurface_um=pk["depthSurface_um"])
    else:
        pk = dict(cells=0, length_um=0.0, width_um=0.0, depthPlate_um=0.0, depthSurface_um=0.0, reachesPlate=False)
    env_full = _extents(ever, axis, axis_y, z, dx)
    env_mid = _plane_extents(ever[midpoint_plane], axis_y, z, dx)
    cav_mid = _plane_extents(ever_boil[midpoint_plane], axis_y, z, dx)
    cav_full = _extents(ever_boil, axis, axis_y, z, dx)
    return dict(
        status="completed", forkVersion=FORK_VERSION,
        arm=dict(evaporation=bool(evaporation), sourceMode=source_mode, boilingStop=bool(boiling_stop),
                 marangoniMultiplier=1.0, temperatureCap=False, tMaxFactor=t_max_factor),
        evaporationConstants=({k: evap_c[k] for k in ("alloy", "T_b_K", "L_v_J_kg", "M_kg_mol", "beta_R", "derivation")}
                              if evap_c else None),
        operators=dict(peak=pk, envFull=env_full, envMid=env_mid, cavityMid=cav_mid, cavityFull=cav_full,
                       midplaneOffset_um=float(axis[midpoint_plane] * 1e6)),
        peakTemperature_K=peak_T, maxSurfaceTemperature_K=max_surface_T, boiling_K=boiling,
        energy=dict(absorbed_J=energy_in, bottomConduction_J=energy_bottom, convectionRadiation_J=energy_surface,
                    evaporated_J=energy_evap, stored_J=stored, relativeResidual=residual,
                    evaporatedFraction=energy_evap / max(energy_in, 1e-12)),
        evaporatedMass_kg=mass_evap,
        discretization=dict(cells=int(cell_count), mesh_um=dx * 1e6, nx=nx, ny=ny, nz=nz, steps=step,
                            minimumDt_s=min_dt, maximumDt_s=max_dt, minimumSourceCapture=minimum_capture,
                            sourceRetries=source_retries, trackLength_um=p["trackLength_um"]),
        wall_s=_time.perf_counter() - wall0,
    )


def frozen_input(row, *, mesh_um=20.0, track_um=600.0, penetration_um=40.0):
    """Frozen-solver input dict for one comparison row (same conventions as the earlier fv_depth_eval harness)."""
    raw = {"mode": "standard", "backend": "reference", "material": row["material"], "power_W": row["power_W"],
           "speed_mm_s": row["speed_mm_s"], "beamDiameter_um": row["beamDiameter_um"], "preheat_C": row["preheat_C"],
           "mesh_um": mesh_um, "trackLength_um": track_um, "evaporationModel": False}
    if row.get("t_um", 0) > 0:
        raw.update(surfaceMode="powder-layer", layer_um=row["t_um"])
    else:
        raw.update(surfaceMode="bare-plate", barePlateGeometry="square", sourcePenetration_um=penetration_um)
    if row["material"] == "Inconel 625":
        from in625_thermal_material import in625_transient_material_specification
        raw["properties"] = in625_transient_material_specification()
    return raw
