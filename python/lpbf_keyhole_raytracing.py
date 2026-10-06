"""Seeded optics on a prescribed cavity, not a thermal/free-surface solver.

The angular absorption law is empirical, not complex-index Fresnel optics.
Power still in flight at the bounce limit is unresolved, never escaped/absorbed.
Rays that never hit the finite mesh (start outside its aperture) are reported as
missed power, separately from power that escapes after at least one reflection.
"""
import math
import time
import numpy as np
import warp as wp


@wp.kernel
def trace_rays_kernel(
    mesh: wp.uint64,
    ray_starts: wp.array(dtype=wp.vec3),
    ray_dirs: wp.array(dtype=wp.vec3),
    ray_powers: wp.array(dtype=float),
    max_bounces: int,
    base_absorption: float,
    offset: float,
    path_points: wp.array(dtype=wp.vec3, ndim=2),
    path_powers: wp.array(dtype=float, ndim=2),
    path_counts: wp.array(dtype=int),
    escaped: wp.array(dtype=int),
):
    tid = wp.tid()
    pos = ray_starts[tid]
    direction = ray_dirs[tid]
    power = ray_powers[tid]
    path_points[tid, 0] = pos
    path_powers[tid, 0] = power
    count = int(0)
    for i in range(max_bounces):
        pos = pos + direction * offset
        query = wp.mesh_query_ray(mesh, pos, direction, 1.0)
        count = count + 1
        if query.result:
            normal = wp.normalize(query.normal)
            dot_dn = wp.dot(direction, normal)
            if dot_dn > 0.0:
                normal = -normal
                dot_dn = -dot_dn
            cos_theta = wp.clamp(-dot_dn, 0.0, 1.0)
            absorption = wp.min(1.0, base_absorption * (1.0 + 0.5 * (1.0 - cos_theta)))
            power = power * (1.0 - absorption)
            pos = pos + direction * query.t
            direction = wp.normalize(direction - 2.0 * dot_dn * normal)
            path_points[tid, count] = pos
            path_powers[tid, count] = power
            if power == 0.0:
                break
        else:
            escaped[tid] = 1
            path_points[tid, count] = pos + direction * 0.001
            path_powers[tid, count] = power
            break
    path_counts[tid] = count


def _number(params, key, default, lower, upper, integer=False):
    value = params.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a finite number")
    if not math.isfinite(value) or not lower <= value <= upper:
        raise ValueError(f"{key} must be in [{lower}, {upper}]")
    if integer and int(value) != value:
        raise ValueError(f"{key} must be an integer")
    return int(value) if integer else float(value)


def compute_keyhole_raytracing(params):
    started = time.perf_counter()
    if not isinstance(params, dict):
        raise ValueError("Ray-tracing parameters must be an object")
    # Operational bounds limit allocations and avoid sub-float geometry.
    nx = _number(params, "nx", 64, 2, 256, True)
    ny = _number(params, "ny", 64, 2, 256, True)
    dx = _number(params, "dx", 2e-6, 1e-9, 1e-3)
    dy = _number(params, "dy", 2e-6, 1e-9, 1e-3)
    power = _number(params, "power_W", 250, 0, 1e6)
    radius = _number(params, "beam_radius_um", 50, 0.01, 10000) * 1e-6
    absorption = _number(params, "base_absorption", 0.3, 0, 1)
    depth = _number(params, "keyhole_depth_um", 100, 0, 10000) * 1e-6
    bounces = _number(params, "max_bounces", 5, 1, 32, True)
    count = _number(params, "num_rays", 10000, 32, 100000, True)
    seed = _number(params, "seed", 0, 0, 2**32 - 1, True)
    ui_count = _number(params, "ui_ray_limit", 1000, 0, 1000, True)
    device_name = params.get("device", "cpu")
    if device_name not in ("cpu", "cuda:0"):
        raise ValueError("device must be cpu or cuda:0; no silent backend substitution")
    device = wp.get_device(device_name)
    rng = np.random.default_rng(seed)
    x = (np.arange(nx) - (nx - 1) / 2) * dx
    y = (np.arange(ny) - (ny - 1) / 2) * dy
    X, Y = np.meshgrid(x, y, indexing="ij")
    Z = -depth * np.exp(-(X**2 + Y**2) / (2 * (radius / 1.5)**2))
    vertices = np.stack([X, Y, Z], axis=-1).reshape(-1, 3).astype(np.float32)
    faces = []
    for i in range(nx - 1):
        for j in range(ny - 1):
            idx = i * ny + j
            faces.extend(([idx, idx + ny, idx + 1], [idx + 1, idx + ny, idx + ny + 1]))
    faces = np.asarray(faces, dtype=np.int32)
    mesh = wp.Mesh(points=wp.array(vertices, dtype=wp.vec3, device=device),
                   indices=wp.array(faces.ravel(), dtype=int, device=device))
    # Equal-power rays sampled from normalized Gaussian I(r) ~ exp(-2r²/w²).
    r = radius * np.sqrt(-0.5 * np.log1p(-rng.random(count)))
    theta = 2 * np.pi * rng.random(count)
    starts = np.column_stack((r * np.cos(theta), r * np.sin(theta), np.full(count, 1e-5))).astype(np.float32)
    dirs = np.zeros_like(starts)
    dirs[:, 2] = -1
    initial = np.full(count, power / count, dtype=np.float32)
    points_wp = wp.zeros((count, bounces + 1), dtype=wp.vec3, device=device)
    powers_wp = wp.zeros((count, bounces + 1), dtype=float, device=device)
    counts_wp = wp.zeros(count, dtype=int, device=device)
    escaped_wp = wp.zeros(count, dtype=int, device=device)
    wp.launch(trace_rays_kernel, dim=count, device=device,
              inputs=[mesh.id, wp.array(starts, dtype=wp.vec3, device=device),
                      wp.array(dirs, dtype=wp.vec3, device=device),
                      wp.array(initial, dtype=float, device=device), bounces, absorption,
                      min(dx, dy, radius) * 1e-4],
              outputs=[points_wp, powers_wp, counts_wp, escaped_wp])
    wp.synchronize_device(device)
    points, powers, counts = points_wp.numpy(), powers_wp.numpy(), counts_wp.numpy()
    escaped = escaped_wp.numpy().astype(bool)
    # A ray that escapes on its first query never touched the mesh: it fell outside the
    # finite aperture. That is a geometry artefact, not reflected (escaped) power.
    missed = escaped & (counts == 1)
    reflected_out = escaped & ~missed
    remaining = powers[np.arange(count), counts].astype(np.float64)
    absorbed = initial.astype(np.float64) - remaining
    absorbed_w = float(absorbed.sum())
    missed_w = float(remaining[missed].sum())
    escaped_w = float(remaining[reflected_out].sum())
    truncated_w = float(remaining[~escaped].sum())
    half_extent_um = float(min((nx - 1) * dx, (ny - 1) * dy) / 2 * 1e6)
    limitations = ["Prescribed Gaussian cavity, not a solved free surface",
                   "Empirical angular absorption, not Fresnel optics",
                   "Finite mesh aperture; no material or experimental qualification",
                   "Bounce-limited power remains unresolved"]
    if missed_w > 0:
        limitations.append(
            f"{missed_w / power * 100:.2f}% of the input power falls outside the {2 * half_extent_um:.0f} um mesh "
            "aperture and never reaches the cavity; absorption of total input is reduced by this geometry "
            "artefact (a mesh aperture of at least 3x the beam radius avoids it)")
    efficiency = absorbed_w / power if power else 0.0
    intercepted_w = power - missed_w
    # Absorption of the power that actually reaches the mesh; None when nothing reaches it.
    intercepted_efficiency = absorbed_w / intercepted_w if intercepted_w > 0 else None
    fractions = absorbed / (power / count) if power else np.zeros(count)
    se = float(np.std(fractions, ddof=1) / np.sqrt(count))
    # UI stream never changes physics samples.
    ui_rng = np.random.default_rng(seed ^ 0x9E3779B9)
    selected = ui_rng.choice(count, min(count, ui_count), replace=False)
    return {
        "status": "success", "model_id": "prescribed-cavity-ray-optics-v2",
        "device": str(device), "warp_version": wp.__version__,
        "solve_time_ms": (time.perf_counter() - started) * 1000,
        "total_input_W": power, "total_absorbed_W": absorbed_w,
        "total_escaped_W": escaped_w, "total_truncated_W": truncated_w, "total_missed_W": missed_w,
        "mesh_aperture_half_extent_um": half_extent_um,
        "energy_balance_relative_error": (abs(power - absorbed_w - escaped_w - truncated_w - missed_w) / power
                                          if power else 0.0),
        "absorption_efficiency": efficiency,
        "absorption_efficiency_of_intercepted": intercepted_efficiency,
        "missed_fraction": (missed_w / power) if power else 0.0,
        "sampling": {"method": "equal-power Gaussian Monte Carlo", "generator": "PCG64",
                     "seed": seed, "num_rays": count, "beam_radius_definition": "1/e^2 intensity",
                     "absorption_efficiency_standard_error": se,
                     "uncertainty_scope": "Sampling only; excludes geometry, bounce truncation and model error"},
        "inputs": dict(nx=nx, ny=ny, dx=dx, dy=dy, power_W=power,
                       beam_radius_um=radius * 1e6, keyhole_depth_um=depth * 1e6,
                       base_absorption=absorption, max_bounces=bounces, seed=seed,
                       num_rays=count, device=str(device), ui_ray_limit=ui_count),
        "limitations": limitations,
        "mesh": {"vertices": vertices.ravel().tolist(), "indices": faces.ravel().tolist()},
        "ray_paths": [{"points": points[i, :counts[i] + 1].tolist(),
                       "powers": powers[i, :counts[i] + 1].tolist()} for i in selected],
    }
