import time
import math
import warp as wp


_PRESSURE_PCG_MAX_ITERATIONS = 100
_PRESSURE_RELATIVE_DIVERGENCE_TOLERANCE = 1.0e-3
_PRESSURE_STATUS_CONVERGED = 1
_PRESSURE_STATUS_NUMERICAL_FAILURE = 2
_PRESSURE_STATUS_BUDGET_EXHAUSTED = 3
_PHASE22_MAX_COMPONENT_SPEED_M_S = 5.0
_PHASE22_MOMENTUM_CFL_LIMIT = 0.5
import numpy as np

# Phase 25: Thermo-Morphological Keyhole 3D GPU Solver with Hydrodynamics
# Integrated Navier-Stokes, Marangoni Convection, Boussinesq Buoyancy (Liquid Expansion),
# and Recoil Pressure on a dynamic free surface using NVIDIA Warp.

wp.init()


def _step_count(sim_time_s: float, nominal_dt_s: float) -> int:
    """Number of forward-Euler intervals needed to reach the requested end time."""
    if not math.isfinite(sim_time_s) or sim_time_s < 0:
        raise ValueError("Simulation duration must be finite and nonnegative")
    if not math.isfinite(nominal_dt_s) or nominal_dt_s <= 0:
        raise ValueError("Time step must be finite and positive")
    if sim_time_s == 0:
        return 0
    ratio = sim_time_s / nominal_dt_s
    nearest = round(ratio)
    if math.isclose(ratio, nearest, rel_tol=1e-12, abs_tol=1e-12):
        ratio = float(nearest)
    return int(math.ceil(ratio))


def _step_size(sim_time_s: float, nominal_dt_s: float, step: int) -> float:
    """Clip the last update so integration never continues beyond the toolpath."""
    remaining = sim_time_s - step * nominal_dt_s
    return max(0.0, min(nominal_dt_s, remaining))


def _phase22_stable_step_size(
    dx: float, dy: float, dz: float, rho: float, mu: float,
    k_max: float, cp_min: float,
) -> float:
    """Bound explicit heat diffusion, momentum advection, and viscosity steps."""
    spacings = (dx, dy, dz)
    if any(not math.isfinite(h) or h <= 0.0 for h in spacings):
        raise ValueError("Grid spacing must be finite and positive")
    if not math.isfinite(rho) or rho <= 0.0:
        raise ValueError("Density must be finite and positive")
    if not math.isfinite(mu) or mu < 0.0:
        raise ValueError("Dynamic viscosity must be finite and nonnegative")
    if not math.isfinite(k_max) or k_max <= 0.0:
        raise ValueError("Maximum conductivity must be finite and positive")
    if not math.isfinite(cp_min) or cp_min <= 0.0:
        raise ValueError("Minimum heat capacity must be finite and positive")

    alpha_max = k_max / (rho * cp_min)
    thermal_dt = 0.12 * min(spacings) ** 2 / alpha_max
    nu = mu / rho
    momentum_rate = sum(
        _PHASE22_MAX_COMPONENT_SPEED_M_S / h + 2.0 * nu / (h * h)
        for h in spacings
    )
    momentum_dt = _PHASE22_MOMENTUM_CFL_LIMIT / momentum_rate
    return min(thermal_dt, momentum_dt)


def _surface_liquid_mask(temperature, surface_height, dz, liquidus_K):
    """Return liquid cells that remain below the current whole-cell surface graph."""
    surface_index = np.trunc(surface_height / dz).astype(np.int64)
    cell_index = np.arange(temperature.shape[2], dtype=np.int64)[None, None, :]
    below_surface = cell_index <= surface_index[:, :, None]
    return (temperature >= liquidus_K) & below_surface

@wp.struct
class LaserState:
    x: float
    y: float
    power: float

@wp.func
def get_laser_state(
    t: float, 
    tp_t: wp.array(dtype=float), 
    tp_x: wp.array(dtype=float), 
    tp_y: wp.array(dtype=float), 
    tp_p: wp.array(dtype=float), 
    num_pts: int
) -> LaserState:
    if num_pts == 0:
        return LaserState(0.0, 0.0, 0.0)
    if num_pts == 1 or t <= tp_t[0]:
        return LaserState(tp_x[0], tp_y[0], tp_p[0])
    if t >= tp_t[num_pts - 1]:
        return LaserState(tp_x[num_pts-1], tp_y[num_pts-1], tp_p[num_pts-1])
        
    low = int(0)
    high = int(num_pts - 1)
    
    while low <= high:
        mid = (low + high) // 2
        if tp_t[mid] <= t:
            if mid + 1 < num_pts and tp_t[mid + 1] > t:
                dt_seg = tp_t[mid + 1] - tp_t[mid]
                if dt_seg < 1e-12:
                    return LaserState(tp_x[mid], tp_y[mid], tp_p[mid])
                f = (t - tp_t[mid]) / dt_seg
                lx = tp_x[mid] + f * (tp_x[mid + 1] - tp_x[mid])
                ly = tp_y[mid] + f * (tp_y[mid + 1] - tp_y[mid])
                lp = tp_p[mid] + f * (tp_p[mid + 1] - tp_p[mid])
                return LaserState(lx, ly, lp)
            else:
                low = mid + 1
        else:
            high = mid - 1
            
    return LaserState(0.0, 0.0, 0.0)

@wp.func
def get_psat(T: float, P0: float, Lv: float, Rs: float, Tv: float) -> float:
    if T <= 1500.0:
        return 0.0
    return P0 * wp.exp((Lv / Rs) * ((1.0 / Tv) - (1.0 / T)))

@wp.func
def get_evaporation_mass_flux(T: float, P0: float, Lv: float, Rs: float, Tv: float) -> float:
    """Return the existing Hertz-Knudsen-like evaporation mass flux [kg/m^2/s]."""
    if T <= 0.0:
        return 0.0
    P_sat = get_psat(T, P0, Lv, Rs, Tv)
    return (0.54 * P_sat) / wp.sqrt(2.0 * 3.14159265 * Rs * T + 1e-6)

@wp.func
def get_liquid_surface_evaporation_mass_flux(
    T: float, T_solidus: float, P0: float, Lv: float, Rs: float, Tv: float
) -> float:
    """Apply the free-surface evaporation law only to a molten surface cell."""
    if T < T_solidus:
        return 0.0
    return get_evaporation_mass_flux(T, P0, Lv, Rs, Tv)

@wp.func
def get_temperature_from_enthalpy(h_val: float, rho: float, L_f: float, T_s: float, T_l: float, cp_solid: float, cp_liquid: float) -> float:
    H_s = rho * cp_solid * T_s
    cp_mush = 0.5 * (cp_solid + cp_liquid)
    H_l = H_s + rho * L_f + rho * cp_mush * (T_l - T_s)
    if h_val <= H_s:
        return h_val / (rho * cp_solid)
    elif h_val >= H_l:
        return T_l + (h_val - H_l) / (rho * cp_liquid)
    else:
        return T_s + (T_l - T_s) * ((h_val - H_s) / (H_l - H_s))

@wp.func
def get_enthalpy_from_temperature(T: float, rho: float, L_f: float, T_s: float, T_l: float, cp_solid: float, cp_liquid: float) -> float:
    H_s = rho * cp_solid * T_s
    cp_mush = 0.5 * (cp_solid + cp_liquid)
    H_l = H_s + rho * L_f + rho * cp_mush * (T_l - T_s)
    if T <= T_s:
        return rho * cp_solid * T
    elif T >= T_l:
        return H_l + rho * cp_liquid * (T - T_l)
    else:
        return H_s + (H_l - H_s) * ((T - T_s) / (T_l - T_s))

@wp.func
def get_k(T: float, T_s: float, T_l: float, k_solid: float, k_liquid: float) -> float:
    if T <= T_s:
        return k_solid
    elif T >= T_l:
        return k_liquid
    else:
        return k_solid + (k_liquid - k_solid) * ((T - T_s) / (T_l - T_s))

@wp.kernel
def free_surface_kinematics_kernel(
    Z_surf: wp.array2d(dtype=float),
    Z_surf_new: wp.array2d(dtype=float),
    surface_floor_hit: wp.array(dtype=wp.int32),
    U: wp.array3d(dtype=float), V: wp.array3d(dtype=float), W: wp.array3d(dtype=float),
    T: wp.array3d(dtype=float),
    nx: int, ny: int, nz: int,
    dx: float, dy: float, dz: float, dt: float, rho: float,
    T_solidus: float, P0: float, Lv: float, Rs: float, Tv: float
):
    """Advect the height graph with projected liquid velocity and evaporation.

    For z-positive-up coordinates, the graph kinematic condition is
    h_t = w - u*h_x - v*h_y - (m_dot/rho)*sqrt(1+h_x^2+h_y^2).
    """
    i, j = wp.tid()
    z_old = Z_surf[i, j]
    z_new = z_old
    if i > 0 and i < nx - 1 and j > 0 and j < ny - 1:
        k_surf = int(z_old / dz)
        if k_surf < 1:
            k_surf = 1
        if k_surf > nz - 2:
            k_surf = nz - 2
        T_surf = T[i, j, k_surf]
        if T_surf >= T_solidus:
            z_over_dz = z_old / dz
            k_center = int(z_over_dz)
            if k_center > nz - 2:
                k_center = nz - 2
            frac_center = z_over_dz - float(k_center)

            # Interpolate cell-centered tangential velocity to the graph and
            # average the two staggered faces that meet at each cell center.
            u0 = 0.5 * (U[i - 1, j, k_center] + U[i, j, k_center])
            u1 = 0.5 * (U[i - 1, j, k_center + 1] + U[i, j, k_center + 1])
            v0 = 0.5 * (V[i, j - 1, k_center] + V[i, j, k_center])
            v1 = 0.5 * (V[i, j - 1, k_center + 1] + V[i, j, k_center + 1])
            u_surf = (1.0 - frac_center) * u0 + frac_center * u1
            v_surf = (1.0 - frac_center) * v0 + frac_center * v1

            # W is stored on positive-z faces at k+1/2. Interpolate the
            # projected normal velocity to the actual height coordinate.
            k_w0 = int(z_over_dz - 0.5)
            if k_w0 < 0:
                k_w0 = 0
            if k_w0 > nz - 3:
                k_w0 = nz - 3
            frac_w = z_over_dz - (float(k_w0) + 0.5)
            w_surf = (1.0 - frac_w) * W[i, j, k_w0] + frac_w * W[i, j, k_w0 + 1]

            h_x = (Z_surf[i + 1, j] - Z_surf[i - 1, j]) / (2.0 * dx)
            h_y = (Z_surf[i, j + 1] - Z_surf[i, j - 1]) / (2.0 * dy)
            m_dot = get_liquid_surface_evaporation_mass_flux(
                T_surf, T_solidus, P0, Lv, Rs, Tv
            )
            surface_metric = wp.sqrt(1.0 + h_x * h_x + h_y * h_y)
            height_rate = w_surf - u_surf * h_x - v_surf * h_y - (m_dot / rho) * surface_metric
            z_new = z_old + dt * height_rate

            # Keep the graph inside the existing active vertical domain.
            if z_new <= 2.0 * dz:
                if m_dot > 0.0:
                    wp.atomic_max(surface_floor_hit, 0, 1)
                z_new = 2.0 * dz
            max_height = float(nz - 2) * dz
            if z_new > max_height:
                z_new = max_height

    Z_surf_new[i, j] = z_new

@wp.func
def _liquid_velocity_face(
    T: wp.array3d(dtype=float), Z_surf: wp.array2d(dtype=float),
    i: int, j: int, k: int, axis: int,
    nx: int, ny: int, nz: int, dz: float, T_solidus: float
) -> bool:
    """True when a stored positive-axis face is bounded by liquid cells."""
    ri, rj, rk = i, j, k
    if axis == 0:
        ri += 1
    elif axis == 1:
        rj += 1
    else:
        rk += 1

    if i <= 0 or i >= nx - 1 or j <= 0 or j >= ny - 1 or k <= 0 or k >= nz - 1:
        return False
    if ri <= 0 or ri >= nx - 1 or rj <= 0 or rj >= ny - 1 or rk <= 0 or rk >= nz - 1:
        return False
    if k > int(Z_surf[i, j] / dz) or T[i, j, k] < T_solidus:
        return False
    if rk > int(Z_surf[ri, rj] / dz) or T[ri, rj, rk] < T_solidus:
        return False
    return True


@wp.func
def _average_transverse_face_component(
    velocity: wp.array3d(dtype=float), T: wp.array3d(dtype=float),
    Z_surf: wp.array2d(dtype=float),
    i0: int, j0: int, k0: int, i1: int, j1: int, k1: int,
    i2: int, j2: int, k2: int, i3: int, j3: int, k3: int,
    axis: int, nx: int, ny: int, nz: int, dz: float, T_solidus: float
) -> float:
    """Average submerged samples for one bilinearly interpolated component."""
    total = 0.0
    count = 0
    if _liquid_velocity_face(T, Z_surf, i0, j0, k0, axis, nx, ny, nz, dz, T_solidus):
        total += velocity[i0, j0, k0]
        count += 1
    if _liquid_velocity_face(T, Z_surf, i1, j1, k1, axis, nx, ny, nz, dz, T_solidus):
        total += velocity[i1, j1, k1]
        count += 1
    if _liquid_velocity_face(T, Z_surf, i2, j2, k2, axis, nx, ny, nz, dz, T_solidus):
        total += velocity[i2, j2, k2]
        count += 1
    if _liquid_velocity_face(T, Z_surf, i3, j3, k3, axis, nx, ny, nz, dz, T_solidus):
        total += velocity[i3, j3, k3]
        count += 1
    if count > 0:
        return total / float(count)
    return 0.0


@wp.kernel
def velocity_advection_forces_kernel(
    U: wp.array3d(dtype=float), V: wp.array3d(dtype=float), W: wp.array3d(dtype=float),
    U_new: wp.array3d(dtype=float), V_new: wp.array3d(dtype=float), W_new: wp.array3d(dtype=float),
    T: wp.array3d(dtype=float),
    Z_surf: wp.array2d(dtype=float),
    nx: int, ny: int, nz: int,
    dx: float, dy: float, dz: float, dt: float,
    mu: float, rho: float, d_gamma_dT: float, beta: float,
    T_liquidus: float, T_solidus: float,
    P0: float, Lv: float, Rs: float, Tv: float
):
    """Advance the face-velocity predictor with stagger-aware transport.

    The free-surface Marangoni and recoil assignments below remain the legacy
    heuristic boundary treatment; this kernel does not model a moving
    material interface or establish a validated stress/velocity boundary law.
    """
    i, j, k = wp.tid()
    u_c = U[i, j, k]
    v_c = V[i, j, k]
    w_c = W[i, j, k]
    
    if i > 0 and i < nx - 1 and j > 0 and j < ny - 1 and k > 0 and k < nz - 1:
        z_surf = Z_surf[i, j]
        k_surf = int(z_surf / dz)
        T_c = T[i, j, k]
        
        if k > k_surf or T_c < T_solidus:
            U_new[i, j, k] = 0.0
            V_new[i, j, k] = 0.0
            W_new[i, j, k] = 0.0
            return
            
        # MAC coordinates are U=(i+1/2,j,k), V=(i,j+1/2,k),
        # W=(i,j,k+1/2). Each transverse component differs on two axes,
        # requiring a bilinear (four-face) interpolation. Samples crossing a
        # solid, air, or exterior face are omitted; remaining submerged samples
        # form a one-sided average, or zero if none are available.
        v_at_u = _average_transverse_face_component(
            V, T, Z_surf, i, j - 1, k, i, j, k,
            i + 1, j - 1, k, i + 1, j, k,
            1, nx, ny, nz, dz, T_solidus)
        w_at_u = _average_transverse_face_component(
            W, T, Z_surf, i, j, k - 1, i, j, k,
            i + 1, j, k - 1, i + 1, j, k,
            2, nx, ny, nz, dz, T_solidus)
        u_at_v = _average_transverse_face_component(
            U, T, Z_surf, i - 1, j, k, i, j, k,
            i - 1, j + 1, k, i, j + 1, k,
            0, nx, ny, nz, dz, T_solidus)
        w_at_v = _average_transverse_face_component(
            W, T, Z_surf, i, j - 1, k - 1, i, j - 1, k,
            i, j, k - 1, i, j, k,
            2, nx, ny, nz, dz, T_solidus)
        u_at_w = _average_transverse_face_component(
            U, T, Z_surf, i - 1, j, k - 1, i, j, k - 1,
            i - 1, j, k, i, j, k,
            0, nx, ny, nz, dz, T_solidus)
        v_at_w = _average_transverse_face_component(
            V, T, Z_surf, i, j - 1, k - 1, i, j, k - 1,
            i, j - 1, k, i, j, k,
            1, nx, ny, nz, dz, T_solidus)

        du_dx = (u_c - U[i-1, j, k])/dx if u_c > 0.0 else (U[i+1, j, k] - u_c)/dx
        du_dy = (u_c - U[i, j-1, k])/dy if v_at_u > 0.0 else (U[i, j+1, k] - u_c)/dy
        du_dz = (u_c - U[i, j, k-1])/dz if w_at_u > 0.0 else (U[i, j, k+1] - u_c)/dz
        
        dv_dx = (v_c - V[i-1, j, k])/dx if u_at_v > 0.0 else (V[i+1, j, k] - v_c)/dx
        dv_dy = (v_c - V[i, j-1, k])/dy if v_c > 0.0 else (V[i, j+1, k] - v_c)/dy
        dv_dz = (v_c - V[i, j, k-1])/dz if w_at_v > 0.0 else (V[i, j, k+1] - v_c)/dz
        
        dw_dx = (w_c - W[i-1, j, k])/dx if u_at_w > 0.0 else (W[i+1, j, k] - w_c)/dx
        dw_dy = (w_c - W[i, j-1, k])/dy if v_at_w > 0.0 else (W[i, j+1, k] - w_c)/dy
        dw_dz = (w_c - W[i, j, k-1])/dz if w_c > 0.0 else (W[i, j, k+1] - w_c)/dz
        
        adv_u = u_c*du_dx + v_at_u*du_dy + w_at_u*du_dz
        adv_v = u_at_v*dv_dx + v_c*dv_dy + w_at_v*dv_dz
        adv_w = u_at_w*dw_dx + v_at_w*dw_dy + w_c*dw_dz
        
        # Diffusion (viscous forces)
        nu = mu / rho
        lap_u = (U[i+1,j,k] - 2.0*u_c + U[i-1,j,k])/(dx*dx) + (U[i,j+1,k] - 2.0*u_c + U[i,j-1,k])/(dy*dy) + (U[i,j,k+1] - 2.0*u_c + U[i,j,k-1])/(dz*dz)
        lap_v = (V[i+1,j,k] - 2.0*v_c + V[i-1,j,k])/(dx*dx) + (V[i,j+1,k] - 2.0*v_c + V[i,j-1,k])/(dy*dy) + (V[i,j,k+1] - 2.0*v_c + V[i,j,k-1])/(dz*dz)
        lap_w = (W[i+1,j,k] - 2.0*w_c + W[i-1,j,k])/(dx*dx) + (W[i,j+1,k] - 2.0*w_c + W[i,j-1,k])/(dy*dy) + (W[i,j,k+1] - 2.0*w_c + W[i,j,k-1])/(dz*dz)
        
        # Boussinesq Buoyancy (Liquid expansion pushing liquid upwards)
        buoyancy = 0.0
        if T_c > T_liquidus:
            buoyancy = 9.81 * beta * (T_c - T_liquidus)
            
        u_new_val = u_c + dt * (-adv_u + nu * lap_u)
        v_new_val = v_c + dt * (-adv_v + nu * lap_v)
        w_new_val = w_c + dt * (-adv_w + nu * lap_w + buoyancy)
        
        # Free Surface Boundary Conditions (Marangoni & Recoil)
        if k == k_surf:
            # Tangential Marangoni stress is applied over the liquid interval
            # from liquidus through boiling; hotter surfaces use the recoil law.
            if T_c >= T_liquidus and T_c <= Tv:
                # Sample the neighboring interface cells, not the same z-index:
                # on a sloped height graph that plane can cross air/metal and
                # turn a phase jump into a spurious surface-temperature slope.
                k_xp = int(Z_surf[i + 1, j] / dz)
                k_xm = int(Z_surf[i - 1, j] / dz)
                k_yp = int(Z_surf[i, j + 1] / dz)
                k_ym = int(Z_surf[i, j - 1] / dz)
                if k_xp < 1: k_xp = 1
                elif k_xp > nz - 2: k_xp = nz - 2
                if k_xm < 1: k_xm = 1
                elif k_xm > nz - 2: k_xm = nz - 2
                if k_yp < 1: k_yp = 1
                elif k_yp > nz - 2: k_yp = nz - 2
                if k_ym < 1: k_ym = 1
                elif k_ym > nz - 2: k_ym = nz - 2
                dT_dx = (T[i + 1, j, k_xp] - T[i - 1, j, k_xm]) / (2.0 * dx)
                dT_dy = (T[i, j + 1, k_yp] - T[i, j - 1, k_ym]) / (2.0 * dy)

                # Convert graph-coordinate temperature derivatives to the
                # ambient surface gradient. This keeps the applied shear
                # tangent to a sloped height graph instead of injecting a
                # spurious normal component into U/V.
                h_x = (Z_surf[i + 1, j] - Z_surf[i - 1, j]) / (2.0 * dx)
                h_y = (Z_surf[i, j + 1] - Z_surf[i, j - 1]) / (2.0 * dy)
                metric_det = 1.0 + h_x * h_x + h_y * h_y
                grad_x = ((1.0 + h_y * h_y) * dT_dx - h_x * h_y * dT_dy) / metric_det
                grad_y = ((1.0 + h_x * h_x) * dT_dy - h_x * h_y * dT_dx) / metric_det
                grad_z = h_x * grad_x + h_y * grad_y

                # tau = d_gamma/dT * grad_s(T), mu * du_t/dn = tau.
                # The adjacent interior velocity sample is one vertical dz
                # below the graph, so its first-order normal spacing is
                # dz/sqrt(1 + h_x^2 + h_y^2), not dz.
                normal_spacing = dz / wp.sqrt(metric_det)
                shear_scale = normal_spacing * (d_gamma_dT / mu)
                u_marangoni = U[i, j, k-1] + shear_scale * grad_x
                v_marangoni = V[i, j, k-1] + shear_scale * grad_y
                w_marangoni = W[i, j, k-1] + shear_scale * grad_z

                u_new_val = u_marangoni
                v_new_val = v_marangoni
                w_new_val = w_marangoni

            # Recoil acts into the material along the local graph normal only
            # above the boiling temperature. The height metric converts the
            # normal traction to projected-cell volume before division by dz;
            # its flat-surface limit is the previous vertical impulse.
            if T_c > Tv:
                P_sat = get_psat(T_c, P0, Lv, Rs, Tv)
                P_recoil = 0.54 * P_sat
                if P_recoil > 1e6: P_recoil = 1e6 # Clamp recoil pressure
                h_x = (Z_surf[i + 1, j] - Z_surf[i - 1, j]) / (2.0 * dx)
                h_y = (Z_surf[i, j + 1] - Z_surf[i, j - 1]) / (2.0 * dy)
                recoil_scale = (P_recoil / rho) * (dt / dz)
                u_new_val += recoil_scale * h_x
                v_new_val += recoil_scale * h_y
                w_new_val -= recoil_scale
            
        # Hard clamp velocity for CFL stability
        # Keep the per-component cap aligned with the host-side stability bound.
        max_vel = 5.0
        if u_new_val > max_vel: u_new_val = max_vel
        elif u_new_val < -max_vel: u_new_val = -max_vel
        if v_new_val > max_vel: v_new_val = max_vel
        elif v_new_val < -max_vel: v_new_val = -max_vel
        if w_new_val > max_vel: w_new_val = max_vel
        elif w_new_val < -max_vel: w_new_val = -max_vel

        # Darcy damping in mushy zone
        if T_c < T_liquidus and T_c > T_solidus:
            f_L = (T_c - T_solidus) / (T_liquidus - T_solidus)
            K_0 = 1e5
            damping = K_0 * ((1.0 - f_L)**2.0) / (f_L**3.0 + 1e-3)
            u_new_val = u_new_val / (1.0 + dt * damping)
            v_new_val = v_new_val / (1.0 + dt * damping)
            w_new_val = w_new_val / (1.0 + dt * damping)
            
    else:
        u_new_val = u_c
        v_new_val = v_c
        w_new_val = w_c
        
    U_new[i, j, k] = u_new_val
    V_new[i, j, k] = v_new_val
    W_new[i, j, k] = w_new_val

@wp.func
def _pressure_cell_class(
    Z_surf: wp.array2d(dtype=float), T: wp.array3d(dtype=float),
    i: int, j: int, k: int, nx: int, ny: int, nz: int,
    dz: float, T_solidus: float
) -> int:
    """Return 1 for liquid, 2 for free-surface air, and 0 for solid/closed sides."""
    if i <= 0 or i >= nx - 1 or j <= 0 or j >= ny - 1 or k <= 0:
        return 0
    if k > int(Z_surf[i, j] / dz):
        return 2
    if k >= nz - 1:
        return 0
    if T[i, j, k] < T_solidus:
        return 0
    return 1


@wp.func
def _pressure_diagonal(
    Z_surf: wp.array2d(dtype=float), T: wp.array3d(dtype=float),
    i: int, j: int, k: int, nx: int, ny: int, nz: int,
    dx: float, dy: float, dz: float, T_solidus: float
) -> float:
    """Diagonal of A=-DG with the projection's liquid/air/solid face rules."""
    diagonal = 0.0
    inv_dx2 = 1.0 / (dx * dx)
    inv_dy2 = 1.0 / (dy * dy)
    inv_dz2 = 1.0 / (dz * dz)
    cls = _pressure_cell_class(Z_surf, T, i - 1, j, k, nx, ny, nz, dz, T_solidus)
    if cls == 1 or cls == 2:
        diagonal += inv_dx2
    cls = _pressure_cell_class(Z_surf, T, i + 1, j, k, nx, ny, nz, dz, T_solidus)
    if cls == 1 or cls == 2:
        diagonal += inv_dx2
    cls = _pressure_cell_class(Z_surf, T, i, j - 1, k, nx, ny, nz, dz, T_solidus)
    if cls == 1 or cls == 2:
        diagonal += inv_dy2
    cls = _pressure_cell_class(Z_surf, T, i, j + 1, k, nx, ny, nz, dz, T_solidus)
    if cls == 1 or cls == 2:
        diagonal += inv_dy2
    cls = _pressure_cell_class(Z_surf, T, i, j, k - 1, nx, ny, nz, dz, T_solidus)
    if cls == 1 or cls == 2:
        diagonal += inv_dz2
    cls = _pressure_cell_class(Z_surf, T, i, j, k + 1, nx, ny, nz, dz, T_solidus)
    if cls == 1 or cls == 2:
        diagonal += inv_dz2
    return diagonal


@wp.func
def _pressure_apply_A(
    P: wp.array3d(dtype=float), Z_surf: wp.array2d(dtype=float), T: wp.array3d(dtype=float),
    i: int, j: int, k: int, nx: int, ny: int, nz: int,
    dx: float, dy: float, dz: float, T_solidus: float
) -> float:
    """Apply A=-DG using matching face coefficients and pressure boundary classes."""
    center = P[i, j, k]
    value = _pressure_diagonal(Z_surf, T, i, j, k, nx, ny, nz, dx, dy, dz, T_solidus) * center
    inv_dx2 = 1.0 / (dx * dx)
    inv_dy2 = 1.0 / (dy * dy)
    inv_dz2 = 1.0 / (dz * dz)
    if _pressure_cell_class(Z_surf, T, i - 1, j, k, nx, ny, nz, dz, T_solidus) == 1:
        value -= P[i - 1, j, k] * inv_dx2
    if _pressure_cell_class(Z_surf, T, i + 1, j, k, nx, ny, nz, dz, T_solidus) == 1:
        value -= P[i + 1, j, k] * inv_dx2
    if _pressure_cell_class(Z_surf, T, i, j - 1, k, nx, ny, nz, dz, T_solidus) == 1:
        value -= P[i, j - 1, k] * inv_dy2
    if _pressure_cell_class(Z_surf, T, i, j + 1, k, nx, ny, nz, dz, T_solidus) == 1:
        value -= P[i, j + 1, k] * inv_dy2
    if _pressure_cell_class(Z_surf, T, i, j, k - 1, nx, ny, nz, dz, T_solidus) == 1:
        value -= P[i, j, k - 1] * inv_dz2
    if _pressure_cell_class(Z_surf, T, i, j, k + 1, nx, ny, nz, dz, T_solidus) == 1:
        value -= P[i, j, k + 1] * inv_dz2
    return value


@wp.kernel
def compute_divergence_kernel(
    U: wp.array3d(dtype=float), V: wp.array3d(dtype=float), W: wp.array3d(dtype=float),
    Div: wp.array3d(dtype=float),
    Z_surf: wp.array2d(dtype=float),
    T: wp.array3d(dtype=float),
    nx: int, ny: int, nz: int,
    dx: float, dy: float, dz: float,
    T_solidus: float
):
    i, j, k = wp.tid()
    if i > 0 and i < nx - 1 and j > 0 and j < ny - 1 and k > 0 and k < nz - 1:
        if _pressure_cell_class(Z_surf, T, i, j, k, nx, ny, nz, dz, T_solidus) != 1:
            Div[i,j,k] = 0.0
            return

        # U/V/W store positive-axis face velocities.  Backward face differences
        # pair with the forward pressure gradient in project_velocity_kernel.
        div_x = 0.0
        cls = _pressure_cell_class(Z_surf, T, i + 1, j, k, nx, ny, nz, dz, T_solidus)
        if cls == 1 or cls == 2:
            div_x += U[i, j, k] / dx
        cls = _pressure_cell_class(Z_surf, T, i - 1, j, k, nx, ny, nz, dz, T_solidus)
        if cls == 1 or cls == 2:
            div_x -= U[i - 1, j, k] / dx

        div_y = 0.0
        cls = _pressure_cell_class(Z_surf, T, i, j + 1, k, nx, ny, nz, dz, T_solidus)
        if cls == 1 or cls == 2:
            div_y += V[i, j, k] / dy
        cls = _pressure_cell_class(Z_surf, T, i, j - 1, k, nx, ny, nz, dz, T_solidus)
        if cls == 1 or cls == 2:
            div_y -= V[i, j - 1, k] / dy

        div_z = 0.0
        cls = _pressure_cell_class(Z_surf, T, i, j, k + 1, nx, ny, nz, dz, T_solidus)
        if cls == 1 or cls == 2:
            div_z += W[i, j, k] / dz
        cls = _pressure_cell_class(Z_surf, T, i, j, k - 1, nx, ny, nz, dz, T_solidus)
        if cls == 1 or cls == 2:
            div_z -= W[i, j, k - 1] / dz

        Div[i,j,k] = div_x + div_y + div_z

@wp.kernel
def pressure_jacobi_kernel(
    P: wp.array3d(dtype=float), P_new: wp.array3d(dtype=float),
    Div: wp.array3d(dtype=float),
    Z_surf: wp.array2d(dtype=float),
    T: wp.array3d(dtype=float),
    nx: int, ny: int, nz: int,
    dx: float, dy: float, dz: float,
    dt: float, rho: float, T_solidus: float
):
    i, j, k = wp.tid()
    if i > 0 and i < nx - 1 and j > 0 and j < ny - 1 and k > 0 and k < nz - 1:
        z_surf = Z_surf[i, j]
        k_surf = int(z_surf / dz)
        
        if _pressure_cell_class(Z_surf, T, i, j, k, nx, ny, nz, dz, T_solidus) != 1:
            P_new[i,j,k] = 0.0
            return

        # This is the negative-semidefinite Laplacian D(G(p)): active-neighbor
        # faces contribute their pressure, free-surface faces contribute a
        # zero-pressure Dirichlet coefficient, and solid/domain faces are
        # no-penetration Neumann faces with no coefficient.
        numerator = -Div[i,j,k] * rho / dt
        denominator = 0.0
        inv_dx2 = 1.0 / (dx * dx)
        inv_dy2 = 1.0 / (dy * dy)
        inv_dz2 = 1.0 / (dz * dz)

        cls = _pressure_cell_class(Z_surf, T, i - 1, j, k, nx, ny, nz, dz, T_solidus)
        if cls == 1:
            numerator += P[i - 1, j, k] * inv_dx2
            denominator += inv_dx2
        elif cls == 2:
            denominator += inv_dx2
        cls = _pressure_cell_class(Z_surf, T, i + 1, j, k, nx, ny, nz, dz, T_solidus)
        if cls == 1:
            numerator += P[i + 1, j, k] * inv_dx2
            denominator += inv_dx2
        elif cls == 2:
            denominator += inv_dx2

        cls = _pressure_cell_class(Z_surf, T, i, j - 1, k, nx, ny, nz, dz, T_solidus)
        if cls == 1:
            numerator += P[i, j - 1, k] * inv_dy2
            denominator += inv_dy2
        elif cls == 2:
            denominator += inv_dy2
        cls = _pressure_cell_class(Z_surf, T, i, j + 1, k, nx, ny, nz, dz, T_solidus)
        if cls == 1:
            numerator += P[i, j + 1, k] * inv_dy2
            denominator += inv_dy2
        elif cls == 2:
            denominator += inv_dy2

        cls = _pressure_cell_class(Z_surf, T, i, j, k - 1, nx, ny, nz, dz, T_solidus)
        if cls == 1:
            numerator += P[i, j, k - 1] * inv_dz2
            denominator += inv_dz2
        elif cls == 2:
            denominator += inv_dz2
        cls = _pressure_cell_class(Z_surf, T, i, j, k + 1, nx, ny, nz, dz, T_solidus)
        if cls == 1:
            numerator += P[i, j, k + 1] * inv_dz2
            denominator += inv_dz2
        elif cls == 2:
            denominator += inv_dz2

        if denominator > 0.0:
            P_new[i,j,k] = numerator / denominator
        else:
            P_new[i,j,k] = 0.0
    else:
        P_new[i,j,k] = P[i,j,k]


@wp.kernel
def pressure_pcg_clear_reductions_kernel(
    p_ap: wp.array(dtype=float), rho_next: wp.array(dtype=float), residual2: wp.array(dtype=float)
):
    if wp.tid() == 0:
        p_ap[0] = 0.0
        rho_next[0] = 0.0
        residual2[0] = 0.0


@wp.kernel
def pressure_pcg_clear_iteration_reductions_kernel(
    p_ap: wp.array(dtype=float), rho_next: wp.array(dtype=float), residual2_next: wp.array(dtype=float),
    status: wp.array(dtype=wp.int32)
):
    if wp.tid() == 0 and status[0] == 0:
        p_ap[0] = 0.0
        rho_next[0] = 0.0
        residual2_next[0] = 0.0


@wp.kernel
def pressure_pcg_initialize_kernel(
    P: wp.array3d(dtype=float), R: wp.array3d(dtype=float), Z: wp.array3d(dtype=float),
    Direction: wp.array3d(dtype=float),
    Div: wp.array3d(dtype=float), Z_surf: wp.array2d(dtype=float), T: wp.array3d(dtype=float),
    nx: int, ny: int, nz: int, dx: float, dy: float, dz: float,
    dt: float, rho: float, T_solidus: float,
    rz: wp.array(dtype=float), b2: wp.array(dtype=float), r2: wp.array(dtype=float)
):
    i, j, k = wp.tid()
    if _pressure_cell_class(Z_surf, T, i, j, k, nx, ny, nz, dz, T_solidus) == 1:
        ax = _pressure_apply_A(P, Z_surf, T, i, j, k, nx, ny, nz, dx, dy, dz, T_solidus)
        b = -rho * Div[i, j, k] / dt
        residual = b - ax
        diagonal = _pressure_diagonal(Z_surf, T, i, j, k, nx, ny, nz, dx, dy, dz, T_solidus)
        preconditioned = residual / diagonal if diagonal > 0.0 else 0.0
        R[i, j, k] = residual
        Z[i, j, k] = preconditioned
        Direction[i, j, k] = preconditioned
        local_rz = residual * preconditioned
        local_b2 = b * b
        local_r2 = residual * residual
    else:
        R[i, j, k] = 0.0
        Z[i, j, k] = 0.0
        Direction[i, j, k] = 0.0
        local_rz = 0.0
        local_b2 = 0.0
        local_r2 = 0.0
        P[i, j, k] = 0.0

    rz_tile = wp.tile_sum(wp.tile(local_rz))
    b2_tile = wp.tile_sum(wp.tile(local_b2))
    r2_tile = wp.tile_sum(wp.tile(local_r2))
    wp.tile_atomic_add(rz, rz_tile)
    wp.tile_atomic_add(b2, b2_tile)
    wp.tile_atomic_add(r2, r2_tile)


@wp.kernel
def pressure_pcg_initialize_status_kernel(
    rz: wp.array(dtype=float), b2: wp.array(dtype=float), r2: wp.array(dtype=float),
    scale2: wp.array(dtype=float), status: wp.array(dtype=wp.int32), iterations: wp.array(dtype=wp.int32),
    tolerance: float
):
    if wp.tid() == 0:
        rhs2 = b2[0]
        initial_r2 = r2[0]
        if not wp.isfinite(rhs2) or not wp.isfinite(initial_r2) or not wp.isfinite(rz[0]):
            scale2[0] = 1.0
            status[0] = 2
            iterations[0] = 0
        else:
            scale2[0] = rhs2 if rhs2 > 1.0e-30 else initial_r2
            iterations[0] = 0
            if initial_r2 <= tolerance * tolerance * scale2[0]:
                status[0] = 1
            else:
                status[0] = 0


@wp.kernel
def pressure_pcg_apply_kernel(
    Direction: wp.array3d(dtype=float), Ap: wp.array3d(dtype=float),
    Z_surf: wp.array2d(dtype=float), T: wp.array3d(dtype=float),
    nx: int, ny: int, nz: int, dx: float, dy: float, dz: float, T_solidus: float,
    p_ap: wp.array(dtype=float), status: wp.array(dtype=wp.int32)
):
    i, j, k = wp.tid()
    local_dot = 0.0
    if status[0] == 0 and _pressure_cell_class(Z_surf, T, i, j, k, nx, ny, nz, dz, T_solidus) == 1:
        value = _pressure_apply_A(Direction, Z_surf, T, i, j, k, nx, ny, nz, dx, dy, dz, T_solidus)
        Ap[i, j, k] = value
        local_dot = Direction[i, j, k] * value
    else:
        Ap[i, j, k] = 0.0
    dot_tile = wp.tile_sum(wp.tile(local_dot))
    wp.tile_atomic_add(p_ap, dot_tile)


@wp.kernel
def pressure_pcg_check_alpha_kernel(
    rho: wp.array(dtype=float), p_ap: wp.array(dtype=float), alpha: wp.array(dtype=float),
    status: wp.array(dtype=wp.int32)
):
    if wp.tid() == 0 and status[0] == 0:
        denominator = p_ap[0]
        numerator = rho[0]
        if not wp.isfinite(denominator) or not wp.isfinite(numerator) or denominator <= 0.0 or numerator <= 0.0:
            status[0] = 2
            alpha[0] = 0.0
        else:
            alpha[0] = numerator / denominator
            if not wp.isfinite(alpha[0]):
                status[0] = 2


@wp.kernel
def pressure_pcg_update_kernel(
    P: wp.array3d(dtype=float), R: wp.array3d(dtype=float), Z: wp.array3d(dtype=float),
    Direction: wp.array3d(dtype=float), Ap: wp.array3d(dtype=float),
    Z_surf: wp.array2d(dtype=float), T: wp.array3d(dtype=float),
    nx: int, ny: int, nz: int, dx: float, dy: float, dz: float, T_solidus: float,
    alpha: wp.array(dtype=float), rho_next: wp.array(dtype=float), residual2_next: wp.array(dtype=float),
    status: wp.array(dtype=wp.int32)
):
    i, j, k = wp.tid()
    local_rz = 0.0
    local_r2 = 0.0
    if status[0] == 0 and _pressure_cell_class(Z_surf, T, i, j, k, nx, ny, nz, dz, T_solidus) == 1:
        P[i, j, k] += alpha[0] * Direction[i, j, k]
        residual = R[i, j, k] - alpha[0] * Ap[i, j, k]
        diagonal = _pressure_diagonal(Z_surf, T, i, j, k, nx, ny, nz, dx, dy, dz, T_solidus)
        preconditioned = residual / diagonal if diagonal > 0.0 else 0.0
        R[i, j, k] = residual
        Z[i, j, k] = preconditioned
        local_rz = residual * preconditioned
        local_r2 = residual * residual
    rz_tile = wp.tile_sum(wp.tile(local_rz))
    r2_tile = wp.tile_sum(wp.tile(local_r2))
    wp.tile_atomic_add(rho_next, rz_tile)
    wp.tile_atomic_add(residual2_next, r2_tile)


@wp.kernel
def pressure_pcg_check_convergence_kernel(
    rho_next: wp.array(dtype=float), residual2_next: wp.array(dtype=float),
    residual2: wp.array(dtype=float), scale2: wp.array(dtype=float),
    status: wp.array(dtype=wp.int32), iterations: wp.array(dtype=wp.int32), tolerance: float
):
    if wp.tid() == 0 and status[0] == 0:
        next_rho = rho_next[0]
        r2 = residual2_next[0]
        residual2[0] = r2
        if not wp.isfinite(next_rho) or not wp.isfinite(r2):
            status[0] = 2
        else:
            iterations[0] += 1
            if r2 <= tolerance * tolerance * scale2[0]:
                status[0] = 1


@wp.kernel
def pressure_pcg_update_direction_kernel(
    Direction: wp.array3d(dtype=float), Z: wp.array3d(dtype=float),
    nx: int, ny: int, nz: int, beta: wp.array(dtype=float),
    status: wp.array(dtype=wp.int32)
):
    i, j, k = wp.tid()
    if status[0] == 0:
        Direction[i, j, k] = Z[i, j, k] + beta[0] * Direction[i, j, k]
    else:
        Direction[i, j, k] = 0.0


@wp.kernel
def pressure_pcg_check_beta_kernel(
    rho: wp.array(dtype=float), rho_next: wp.array(dtype=float), beta: wp.array(dtype=float),
    status: wp.array(dtype=wp.int32)
):
    if wp.tid() == 0 and status[0] == 0:
        old_rho = rho[0]
        new_rho = rho_next[0]
        if not wp.isfinite(old_rho) or not wp.isfinite(new_rho) or old_rho <= 0.0 or new_rho < 0.0:
            status[0] = 2
            beta[0] = 0.0
        else:
            beta[0] = new_rho / old_rho
            if not wp.isfinite(beta[0]):
                status[0] = 2


@wp.kernel
def pressure_pcg_finalize_kernel(status: wp.array(dtype=wp.int32), iterations: wp.array(dtype=wp.int32)):
    if wp.tid() == 0 and status[0] == 0:
        status[0] = _PRESSURE_STATUS_BUDGET_EXHAUSTED


@wp.kernel
def pressure_pcg_accumulate_status_kernel(
    step_status: wp.array(dtype=wp.int32), step_iterations: wp.array(dtype=wp.int32),
    aggregate_status: wp.array(dtype=wp.int32), max_iterations_observed: wp.array(dtype=wp.int32),
    total_iterations_observed: wp.array(dtype=wp.int32)
):
    if wp.tid() == 0:
        if step_status[0] != _PRESSURE_STATUS_CONVERGED:
            if step_status[0] == _PRESSURE_STATUS_NUMERICAL_FAILURE or aggregate_status[0] == _PRESSURE_STATUS_CONVERGED:
                aggregate_status[0] = step_status[0]
        if step_iterations[0] > max_iterations_observed[0]:
            max_iterations_observed[0] = step_iterations[0]
        total_iterations_observed[0] += step_iterations[0]


def launch_pressure_pcg(
    P, Div, Z_surf, T, shape, spacing, dt, rho, T_solidus,
    residual, preconditioned, direction, operator_direction,
    rho_current, rho_next, rhs_norm2, residual_norm2, residual_next_norm2, scale_norm2,
    direction_dot_operator, alpha, beta, status, iterations,
    max_iterations=_PRESSURE_PCG_MAX_ITERATIONS,
    relative_tolerance=_PRESSURE_RELATIVE_DIVERGENCE_TOLERANCE,
):
    """Run fixed-budget device-side PCG; never reads a device scalar in-loop."""
    nx, ny, nz = shape
    dx, dy, dz = spacing
    wp.launch(kernel=pressure_pcg_clear_reductions_kernel, dim=1,
              inputs=[rho_current, rhs_norm2, residual_norm2], device=P.device)
    wp.launch(kernel=pressure_pcg_initialize_kernel, dim=shape,
              inputs=[P, residual, preconditioned, direction, Div, Z_surf, T,
                      nx, ny, nz, dx, dy, dz, dt, rho, T_solidus,
                      rho_current, rhs_norm2, residual_norm2], device=P.device)
    wp.launch(kernel=pressure_pcg_initialize_status_kernel, dim=1,
              inputs=[rho_current, rhs_norm2, residual_norm2, scale_norm2,
                      status, iterations, relative_tolerance], device=P.device)

    for _ in range(max_iterations):
        wp.launch(kernel=pressure_pcg_clear_iteration_reductions_kernel, dim=1,
                  inputs=[direction_dot_operator, rho_next, residual_next_norm2, status], device=P.device)
        wp.launch(kernel=pressure_pcg_apply_kernel, dim=shape,
                  inputs=[direction, operator_direction, Z_surf, T, nx, ny, nz,
                          dx, dy, dz, T_solidus, direction_dot_operator, status], device=P.device)
        wp.launch(kernel=pressure_pcg_check_alpha_kernel, dim=1,
                  inputs=[rho_current, direction_dot_operator, alpha, status], device=P.device)
        wp.launch(kernel=pressure_pcg_update_kernel, dim=shape,
                  inputs=[P, residual, preconditioned, direction, operator_direction,
                          Z_surf, T, nx, ny, nz, dx, dy, dz, T_solidus,
                          alpha, rho_next, residual_next_norm2, status], device=P.device)
        wp.launch(kernel=pressure_pcg_check_convergence_kernel, dim=1,
                  inputs=[rho_next, residual_next_norm2, residual_norm2, scale_norm2, status, iterations,
                          relative_tolerance], device=P.device)
        wp.launch(kernel=pressure_pcg_check_beta_kernel, dim=1,
                  inputs=[rho_current, rho_next, beta, status], device=P.device)
        wp.launch(kernel=pressure_pcg_update_direction_kernel, dim=shape,
                  inputs=[direction, preconditioned, nx, ny, nz, beta, status], device=P.device)
        rho_current, rho_next = rho_next, rho_current

    wp.launch(kernel=pressure_pcg_finalize_kernel, dim=1,
              inputs=[status, iterations], device=P.device)
    return rho_current, rho_next

@wp.kernel
def project_velocity_kernel(
    U: wp.array3d(dtype=float), V: wp.array3d(dtype=float), W: wp.array3d(dtype=float),
    P: wp.array3d(dtype=float),
    Z_surf: wp.array2d(dtype=float),
    T: wp.array3d(dtype=float),
    nx: int, ny: int, nz: int,
    dx: float, dy: float, dz: float,
    dt: float, rho: float, T_solidus: float
):
    i, j, k = wp.tid()
    # Each thread owns its positive-axis faces.  Air is a free surface with
    # p=0; solid and exterior boundaries impose zero normal velocity.
    left = _pressure_cell_class(Z_surf, T, i, j, k, nx, ny, nz, dz, T_solidus)
    right = _pressure_cell_class(Z_surf, T, i + 1, j, k, nx, ny, nz, dz, T_solidus)
    if i < nx - 1:
        if (left == 1 or left == 2) and (right == 1 or right == 2):
            p_left = P[i, j, k] if left == 1 else 0.0
            p_right = P[i + 1, j, k] if right == 1 else 0.0
            U[i, j, k] -= (dt / rho) * (p_right - p_left) / dx
        elif left == 1 or right == 1:
            U[i, j, k] = 0.0
    else:
        U[i, j, k] = 0.0

    left = _pressure_cell_class(Z_surf, T, i, j, k, nx, ny, nz, dz, T_solidus)
    right = _pressure_cell_class(Z_surf, T, i, j + 1, k, nx, ny, nz, dz, T_solidus)
    if j < ny - 1:
        if (left == 1 or left == 2) and (right == 1 or right == 2):
            p_left = P[i, j, k] if left == 1 else 0.0
            p_right = P[i, j + 1, k] if right == 1 else 0.0
            V[i, j, k] -= (dt / rho) * (p_right - p_left) / dy
        elif left == 1 or right == 1:
            V[i, j, k] = 0.0
    else:
        V[i, j, k] = 0.0

    left = _pressure_cell_class(Z_surf, T, i, j, k, nx, ny, nz, dz, T_solidus)
    right = _pressure_cell_class(Z_surf, T, i, j, k + 1, nx, ny, nz, dz, T_solidus)
    if k < nz - 1:
        if (left == 1 or left == 2) and (right == 1 or right == 2):
            p_left = P[i, j, k] if left == 1 else 0.0
            p_right = P[i, j, k + 1] if right == 1 else 0.0
            W[i, j, k] -= (dt / rho) * (p_right - p_left) / dz
        elif left == 1 or right == 1:
            W[i, j, k] = 0.0
    else:
        W[i, j, k] = 0.0


@wp.kernel
def validate_projected_momentum_cfl_kernel(
    U: wp.array3d(dtype=float), V: wp.array3d(dtype=float), W: wp.array3d(dtype=float),
    Z_surf: wp.array2d(dtype=float), T: wp.array3d(dtype=float),
    exceeded: wp.array(dtype=wp.int32),
    nx: int, ny: int, nz: int, dx: float, dy: float, dz: float,
    dt: float, nu: float, T_solidus: float, cfl_limit: float,
):
    """Flag any liquid cell whose projected explicit transport CFL is unsafe."""
    i, j, k = wp.tid()
    if _pressure_cell_class(Z_surf, T, i, j, k, nx, ny, nz, dz, T_solidus) == 1:
        rate = (
            wp.abs(U[i, j, k]) / dx
            + wp.abs(V[i, j, k]) / dy
            + wp.abs(W[i, j, k]) / dz
            + 2.0 * nu * (1.0 / (dx * dx) + 1.0 / (dy * dy) + 1.0 / (dz * dz))
        )
        if dt * rate > cfl_limit:
            wp.atomic_max(exceeded, 0, 1)


@wp.func
def _liquid_transport_cell(
    T: wp.array3d(dtype=float), Z_surf: wp.array2d(dtype=float),
    i: int, j: int, k: int, nx: int, ny: int, nz: int,
    dz: float, T_solidus: float
) -> bool:
    """Only liquid material cells carry advective enthalpy flux."""
    if i <= 0 or i >= nx - 1 or j <= 0 or j >= ny - 1 or k <= 0 or k >= nz - 1:
        return False
    if k > int(Z_surf[i, j] / dz) or T[i, j, k] < T_solidus:
        return False
    return True


@wp.func
def _enthalpy_face_flux(
    H: wp.array3d(dtype=float), T: wp.array3d(dtype=float),
    Z_surf: wp.array2d(dtype=float), velocity: float,
    li: int, lj: int, lk: int, ri: int, rj: int, rk: int,
    nx: int, ny: int, nz: int, dz: float, T_solidus: float
) -> float:
    """Oriented upwind enthalpy flux; closed at solid, air, and domain faces."""
    if not _liquid_transport_cell(T, Z_surf, li, lj, lk, nx, ny, nz, dz, T_solidus):
        return 0.0
    if not _liquid_transport_cell(T, Z_surf, ri, rj, rk, nx, ny, nz, dz, T_solidus):
        return 0.0
    donor_h = H[li, lj, lk]
    if velocity < 0.0:
        donor_h = H[ri, rj, rk]
    return velocity * donor_h


@wp.kernel
def enthalpy_3d_nonlinear_step_kernel(
    T: wp.array3d(dtype=float), H: wp.array3d(dtype=float),
    U: wp.array3d(dtype=float), V: wp.array3d(dtype=float), W: wp.array3d(dtype=float),
    T_new: wp.array3d(dtype=float), H_new: wp.array3d(dtype=float),
    Z_surf: wp.array2d(dtype=float),
    nx: int, ny: int, nz: int,
    dx: float, dy: float, dz: float,
    dt: float, current_t: float,
    rho: float, L_f: float,
    T_solidus: float, T_liquidus: float,
    tp_t: wp.array(dtype=float), tp_x: wp.array(dtype=float), tp_y: wp.array(dtype=float), tp_p: wp.array(dtype=float), num_pts: int,
    radius: float, eta: float,
    h_c: float, epsilon: float, T_amb: float,
    P0: float, Lv: float, Rs: float, Tv: float,
    cp_solid: float, cp_liquid: float,
    k_solid: float, k_liquid: float
):
    i, j, k = wp.tid()
    
    if i > 0 and i < nx - 1 and j > 0 and j < ny - 1 and k > 0 and k < nz - 1:
        z_surf = Z_surf[i, j]
        k_surf = int(z_surf / dz)
        
        if k > k_surf:
            T_new[i, j, k] = T_amb
            H_new[i, j, k] = get_enthalpy_from_temperature(T_amb, rho, L_f, T_solidus, T_liquidus, cp_solid, cp_liquid)
            return

        T_c = T[i, j, k]
        h_c_val = H[i, j, k]
        k_c = get_k(T_c, T_solidus, T_liquidus, k_solid, k_liquid)
        
        k_xp = 0.0
        if k <= int(Z_surf[i+1, j] / dz):
            k_xp = 0.5 * (k_c + get_k(T[i+1, j, k], T_solidus, T_liquidus, k_solid, k_liquid))
        k_xm = 0.0
        if k <= int(Z_surf[i-1, j] / dz):
            k_xm = 0.5 * (k_c + get_k(T[i-1, j, k], T_solidus, T_liquidus, k_solid, k_liquid))
        k_yp = 0.0
        if k <= int(Z_surf[i, j+1] / dz):
            k_yp = 0.5 * (k_c + get_k(T[i, j+1, k], T_solidus, T_liquidus, k_solid, k_liquid))
        k_ym = 0.0
        if k <= int(Z_surf[i, j-1] / dz):
            k_ym = 0.5 * (k_c + get_k(T[i, j-1, k], T_solidus, T_liquidus, k_solid, k_liquid))
        
        T_zp = T[i, j, k+1]
        if k == k_surf:
            k_zp = 0.0 # Adiabatic to air
        else:
            k_zp = 0.5 * (k_c + get_k(T_zp, T_solidus, T_liquidus, k_solid, k_liquid))
            
        k_zm = 0.5 * (k_c + get_k(T[i, j, k-1], T_solidus, T_liquidus, k_solid, k_liquid))
        
        qx = (k_xp*(T[i+1, j, k] - T_c) - k_xm*(T_c - T[i-1, j, k])) / (dx*dx)
        qy = (k_yp*(T[i, j+1, k] - T_c) - k_ym*(T_c - T[i, j-1, k])) / (dy*dy)
        qz = (k_zp*(T_zp - T_c) - k_zm*(T_c - T[i, j, k-1])) / (dz*dz)
        q_cond = qx + qy + qz
        
        # Conservative upwind transport on the positive-axis face velocities.
        # Each shared face computes the same flux from either adjacent cell,
        # so internal transfers cancel in the global enthalpy sum.
        fx_p = _enthalpy_face_flux(H, T, Z_surf, U[i, j, k],
                                   i, j, k, i + 1, j, k,
                                   nx, ny, nz, dz, T_solidus)
        fx_m = _enthalpy_face_flux(H, T, Z_surf, U[i - 1, j, k],
                                   i - 1, j, k, i, j, k,
                                   nx, ny, nz, dz, T_solidus)
        fy_p = _enthalpy_face_flux(H, T, Z_surf, V[i, j, k],
                                   i, j, k, i, j + 1, k,
                                   nx, ny, nz, dz, T_solidus)
        fy_m = _enthalpy_face_flux(H, T, Z_surf, V[i, j - 1, k],
                                   i, j - 1, k, i, j, k,
                                   nx, ny, nz, dz, T_solidus)
        fz_p = _enthalpy_face_flux(H, T, Z_surf, W[i, j, k],
                                   i, j, k, i, j, k + 1,
                                   nx, ny, nz, dz, T_solidus)
        fz_m = _enthalpy_face_flux(H, T, Z_surf, W[i, j, k - 1],
                                   i, j, k - 1, i, j, k,
                                   nx, ny, nz, dz, T_solidus)
        q_conv = -((fx_p - fx_m) / dx + (fy_p - fy_m) / dy + (fz_p - fz_m) / dz)
        
        h_val_new = h_c_val + dt * (q_cond + q_conv)
        
        if k == k_surf:
            # Multi-track Laser State
            l_state = get_laser_state(current_t, tp_t, tp_x, tp_y, tp_p, num_pts)
            
            x_pos = float(i) * dx
            y_pos = float(j) * dy
            r2 = (x_pos - l_state.x)*(x_pos - l_state.x) + (y_pos - l_state.y)*(y_pos - l_state.y)
            
            q_laser = (2.0 * eta * l_state.power / (3.14159265 * radius * radius)) * wp.exp(-2.0 * r2 / (radius * radius))
            q_loss = (h_c * (T_c - T_amb)
                      + epsilon * 5.67e-8 * (T_c*T_c*T_c*T_c - T_amb*T_amb*T_amb*T_amb))
            
            m_dot_evap = get_liquid_surface_evaporation_mass_flux(
                T_c, T_solidus, P0, Lv, Rs, Tv
            )
            h_x = (Z_surf[i + 1, j] - Z_surf[i - 1, j]) / (2.0 * dx)
            h_y = (Z_surf[i, j + 1] - Z_surf[i, j - 1]) / (2.0 * dy)
            surface_metric = wp.sqrt(1.0 + h_x * h_x + h_y * h_y)
            # H is volumetric and the update below divides surface flux by dz.
            # Keep the flux per actual area here; apply the surface metric
            # once, together with convection and radiation, below.
            q_evap = m_dot_evap * Lv
            
            # Laser input is per projected x-y area; environmental losses act
            # on actual graph area, like the evaporation mass/energy flux.
            h_val_new = h_val_new + dt * (
                q_laser - (q_loss + q_evap) * surface_metric
            ) / dz

        H_new[i, j, k] = h_val_new
        T_new[i, j, k] = get_temperature_from_enthalpy(h_val_new, rho, L_f, T_solidus, T_liquidus, cp_solid, cp_liquid)
    else:
        H_new[i, j, k] = H[i, j, k]
        T_new[i, j, k] = T[i, j, k]


@wp.kernel
def phase22_energy_ledger_step_kernel(
    T: wp.array3d(dtype=float), H: wp.array3d(dtype=float),
    U: wp.array3d(dtype=float), V: wp.array3d(dtype=float), W: wp.array3d(dtype=float),
    Z_surf: wp.array2d(dtype=float),
    laser_J: wp.array3d(dtype=wp.float64),
    conduction_J: wp.array3d(dtype=wp.float64),
    advection_J: wp.array3d(dtype=wp.float64),
    convection_J: wp.array3d(dtype=wp.float64),
    radiation_J: wp.array3d(dtype=wp.float64),
    evaporation_J: wp.array3d(dtype=wp.float64),
    surface_mask_reset_J: wp.array3d(dtype=wp.float64),
    nx: int, ny: int, nz: int,
    dx: float, dy: float, dz: float, dt: float, current_t: float,
    rho: float, L_f: float, T_solidus: float, T_liquidus: float,
    tp_t: wp.array(dtype=float), tp_x: wp.array(dtype=float),
    tp_y: wp.array(dtype=float), tp_p: wp.array(dtype=float), num_pts: int,
    radius: float, eta: float, h_c: float, epsilon: float, T_amb: float,
    P0: float, Lv: float, Rs: float, Tv: float,
    cp_solid: float, cp_liquid: float, k_solid: float, k_liquid: float
):
    """Integrate the implemented enthalpy terms into independent per-cell ledgers."""
    i, j, k = wp.tid()
    if i > 0 and i < nx - 1 and j > 0 and j < ny - 1 and k > 0 and k < nz - 1:
        z_surf = Z_surf[i, j]
        k_surf = int(z_surf / dz)
        volume = wp.float64(dx) * wp.float64(dy) * wp.float64(dz)

        if k > k_surf:
            h_ambient = get_enthalpy_from_temperature(
                T_amb, rho, L_f, T_solidus, T_liquidus, cp_solid, cp_liquid
            )
            surface_mask_reset_J[i, j, k] += (
                wp.float64(h_ambient - H[i, j, k]) * volume
            )
            return

        T_c = T[i, j, k]
        k_c = get_k(T_c, T_solidus, T_liquidus, k_solid, k_liquid)
        k_xp = 0.0
        if k <= int(Z_surf[i + 1, j] / dz):
            k_xp = 0.5 * (k_c + get_k(T[i + 1, j, k], T_solidus, T_liquidus,
                                      k_solid, k_liquid))
        k_xm = 0.0
        if k <= int(Z_surf[i - 1, j] / dz):
            k_xm = 0.5 * (k_c + get_k(T[i - 1, j, k], T_solidus, T_liquidus,
                                      k_solid, k_liquid))
        k_yp = 0.0
        if k <= int(Z_surf[i, j + 1] / dz):
            k_yp = 0.5 * (k_c + get_k(T[i, j + 1, k], T_solidus, T_liquidus,
                                      k_solid, k_liquid))
        k_ym = 0.0
        if k <= int(Z_surf[i, j - 1] / dz):
            k_ym = 0.5 * (k_c + get_k(T[i, j - 1, k], T_solidus, T_liquidus,
                                      k_solid, k_liquid))
        k_zp = 0.0 if k == k_surf else 0.5 * (
            k_c + get_k(T[i, j, k + 1], T_solidus, T_liquidus, k_solid, k_liquid)
        )
        k_zm = 0.5 * (k_c + get_k(T[i, j, k - 1], T_solidus, T_liquidus,
                                  k_solid, k_liquid))
        q_cond = (
            (k_xp * (T[i + 1, j, k] - T_c) - k_xm * (T_c - T[i - 1, j, k])) / (dx * dx)
            + (k_yp * (T[i, j + 1, k] - T_c) - k_ym * (T_c - T[i, j - 1, k])) / (dy * dy)
            + (k_zp * (T[i, j, k + 1] - T_c) - k_zm * (T_c - T[i, j, k - 1])) / (dz * dz)
        )
        fx_p = _enthalpy_face_flux(H, T, Z_surf, U[i, j, k],
                                   i, j, k, i + 1, j, k, nx, ny, nz, dz, T_solidus)
        fx_m = _enthalpy_face_flux(H, T, Z_surf, U[i - 1, j, k],
                                   i - 1, j, k, i, j, k, nx, ny, nz, dz, T_solidus)
        fy_p = _enthalpy_face_flux(H, T, Z_surf, V[i, j, k],
                                   i, j, k, i, j + 1, k, nx, ny, nz, dz, T_solidus)
        fy_m = _enthalpy_face_flux(H, T, Z_surf, V[i, j - 1, k],
                                   i, j - 1, k, i, j, k, nx, ny, nz, dz, T_solidus)
        fz_p = _enthalpy_face_flux(H, T, Z_surf, W[i, j, k],
                                   i, j, k, i, j, k + 1, nx, ny, nz, dz, T_solidus)
        fz_m = _enthalpy_face_flux(H, T, Z_surf, W[i, j, k - 1],
                                   i, j, k - 1, i, j, k, nx, ny, nz, dz, T_solidus)
        q_adv = -((fx_p - fx_m) / dx + (fy_p - fy_m) / dy + (fz_p - fz_m) / dz)
        scale = wp.float64(dt) * volume
        conduction_J[i, j, k] += scale * wp.float64(q_cond)
        advection_J[i, j, k] += scale * wp.float64(q_adv)

        if k == k_surf:
            l_state = get_laser_state(current_t, tp_t, tp_x, tp_y, tp_p, num_pts)
            x_pos = float(i) * dx
            y_pos = float(j) * dy
            r2 = (x_pos - l_state.x) * (x_pos - l_state.x) + (y_pos - l_state.y) * (y_pos - l_state.y)
            q_laser = (2.0 * eta * l_state.power / (3.14159265 * radius * radius)) * wp.exp(-2.0 * r2 / (radius * radius))
            q_convection = h_c * (T_c - T_amb)
            q_radiation = epsilon * 5.67e-8 * (
                T_c * T_c * T_c * T_c - T_amb * T_amb * T_amb * T_amb
            )
            m_dot = get_liquid_surface_evaporation_mass_flux(
                T_c, T_solidus, P0, Lv, Rs, Tv
            )
            h_x = (Z_surf[i + 1, j] - Z_surf[i - 1, j]) / (2.0 * dx)
            h_y = (Z_surf[i, j + 1] - Z_surf[i, j - 1]) / (2.0 * dy)
            area_metric = wp.sqrt(1.0 + h_x * h_x + h_y * h_y)
            projected_area = wp.float64(dx) * wp.float64(dy)
            laser_J[i, j, k] += wp.float64(dt * q_laser) * projected_area
            convection_J[i, j, k] += wp.float64(dt * q_convection * area_metric) * projected_area
            radiation_J[i, j, k] += wp.float64(dt * q_radiation * area_metric) * projected_area
            evaporation_J[i, j, k] += wp.float64(dt * m_dot * Lv * area_metric) * projected_area


@wp.kernel
def phase22_reconcile_surface_mask_kernel(
    T: wp.array3d(dtype=float), H: wp.array3d(dtype=float),
    Z_surf: wp.array2d(dtype=float),
    surface_mask_reset_J: wp.array3d(dtype=wp.float64),
    nx: int, ny: int, nz: int, dx: float, dy: float, dz: float,
    rho: float, L_f: float, T_solidus: float, T_liquidus: float,
    cp_solid: float, cp_liquid: float, T_amb: float, track_reset: int,
):
    """Reconcile final enthalpy/temperature with the advanced whole-cell graph."""
    i, j, k = wp.tid()
    if i > 0 and i < nx - 1 and j > 0 and j < ny - 1 and k > 0 and k < nz - 1:
        if k > int(Z_surf[i, j] / dz):
            h_ambient = get_enthalpy_from_temperature(
                T_amb, rho, L_f, T_solidus, T_liquidus, cp_solid, cp_liquid
            )
            if track_reset != 0:
                volume = wp.float64(dx) * wp.float64(dy) * wp.float64(dz)
                surface_mask_reset_J[i, j, k] += (
                    wp.float64(h_ambient - H[i, j, k]) * volume
                )
            T[i, j, k] = T_amb
            H[i, j, k] = h_ambient

class TransientEnthalpy3DGPU:
    def __init__(self, nx=128, ny=128, nz=64, dx=2e-6, dy=2e-6, dz=2e-6):
        self.nx = nx
        self.ny = ny
        self.nz = nz
        self.dx, self.dy, self.dz = dx, dy, dz
        self.device = "cuda:0" if wp.get_cuda_device_count() > 0 else "cpu"
        
    def solve_toolpath(self, toolpath, T_preheat_K=300.0, *,
              rho, L_f, T_solidus, T_liquidus, Lv, Rs, Tv,
              cp_solid, cp_liquid, k_solid, k_liquid,
              P0=101325.0,
              mu=0.005, d_gamma_dT=-0.0003, beta=1e-4,
              include_diagnostic_fields=False, include_energy_ledger=False):
        """Run the Phase 22 toolpath solve.

        Alloy data (rho, L_f, T_solidus, T_liquidus, Lv, Rs, Tv, cp_solid, cp_liquid,
        k_solid, k_liquid) are keyword-only and REQUIRED: there is no default alloy.
        The caller must take them from four_alloy_materials (the material authority);
        units are kg/m3, J/kg, K, K, J/kg, J/(kg K) (specific gas constant R/M), K,
        J/(kg K), J/(kg K), W/(m K), W/(m K).

        P0 (ambient pressure), mu, d_gamma_dT and beta are model constants of this
        solver, not alloy data, and keep their defaults. They are NOT the authority's
        per-alloy viscosity / d(gamma)/dT / thermal expansion; this solver does not
        read those.
        """

        if type(include_diagnostic_fields) is not bool or type(include_energy_ledger) is not bool:
            raise ValueError("diagnostic options must be booleans")
        diagnostic_cell_count = self.nx * self.ny * self.nz
        if include_diagnostic_fields and diagnostic_cell_count > 100_000:
            raise ValueError("Full-field diagnostics are limited to 100000 cells")
        if include_energy_ledger and diagnostic_cell_count > 1_000_000:
            raise ValueError("Energy-ledger diagnostics are limited to 1000000 cells")
        
        # Unpack Toolpath dict: t, x, y, p
        tp_t = wp.array(toolpath['t'], dtype=float, device=self.device)
        tp_x = wp.array(toolpath['x'], dtype=float, device=self.device)
        tp_y = wp.array(toolpath['y'], dtype=float, device=self.device)
        tp_p = wp.array(toolpath['p'], dtype=float, device=self.device)
        num_pts = len(toolpath['t'])
        
        sim_time_s = toolpath['t'][-1]
        
        k_max = max(k_solid, k_liquid)
        cp_min = min(cp_solid, cp_liquid)
        dt = _phase22_stable_step_size(
            self.dx, self.dy, self.dz, rho, mu, k_max, cp_min
        )
        steps = _step_count(sim_time_s, dt)
        
        print(f"[Phase 25 Multi-Track FDM + Marangoni] Toolpath Pts: {num_pts}. Duration: {sim_time_s*1e6:.1f}us. Steps: {steps}")
        
        shape = (self.nx, self.ny, self.nz)
        T_arr = wp.full(shape=shape, value=float(T_preheat_K), dtype=float, device=self.device)
        
        H_s = rho * cp_solid * T_solidus
        cp_mush = 0.5 * (cp_solid + cp_liquid)
        H_l = H_s + rho * L_f + rho * cp_mush * (T_liquidus - T_solidus)
        if T_preheat_K <= T_solidus:
            h_init = rho * cp_solid * T_preheat_K
        elif T_preheat_K >= T_liquidus:
            h_init = H_l + rho * cp_liquid * (T_preheat_K - T_liquidus)
        else:
            h_init = H_s + (H_l - H_s) * ((T_preheat_K - T_solidus) / (T_liquidus - T_solidus))
            
        H_arr = wp.full(shape=shape, value=float(h_init), dtype=float, device=self.device)
        T_new = wp.zeros_like(T_arr)
        H_new = wp.zeros_like(H_arr)
        energy_arrays = None
        if include_energy_ledger:
            energy_arrays = {
                key: wp.zeros(shape=shape, dtype=wp.float64, device=self.device)
                for key in (
                    "laser_absorbed_in_J", "conduction_net_J", "advection_net_J",
                    "convection_out_J", "radiation_out_J", "evaporation_out_J",
                    "surface_mask_reset_J",
                )
            }
        surface_reset_accumulator = (
            energy_arrays["surface_mask_reset_J"] if energy_arrays is not None else
            wp.zeros(shape=(1, 1, 1), dtype=wp.float64, device=self.device)
        )
        
        # Hydrodynamics fields
        U = wp.zeros(shape=shape, dtype=float, device=self.device)
        V = wp.zeros(shape=shape, dtype=float, device=self.device)
        W = wp.zeros(shape=shape, dtype=float, device=self.device)
        U_new = wp.zeros_like(U)
        V_new = wp.zeros_like(V)
        W_new = wp.zeros_like(W)
        P = wp.zeros(shape=shape, dtype=float, device=self.device)
        P_new = wp.zeros_like(P)
        Div = wp.zeros(shape=shape, dtype=float, device=self.device)
        Div_post = wp.zeros_like(Div)
        pcg_residual = wp.zeros_like(P)
        pcg_preconditioned = wp.zeros_like(P)
        pcg_direction = wp.zeros_like(P)
        pcg_A_direction = wp.zeros_like(P)
        pcg_rho = wp.zeros(1, dtype=float, device=self.device)
        pcg_rho_next = wp.zeros(1, dtype=float, device=self.device)
        pcg_rhs_norm2 = wp.zeros(1, dtype=float, device=self.device)
        pcg_residual_norm2 = wp.zeros(1, dtype=float, device=self.device)
        pcg_residual_next_norm2 = wp.zeros(1, dtype=float, device=self.device)
        pcg_scale_norm2 = wp.zeros(1, dtype=float, device=self.device)
        pcg_direction_dot_A = wp.zeros(1, dtype=float, device=self.device)
        pcg_alpha = wp.zeros(1, dtype=float, device=self.device)
        pcg_beta = wp.zeros(1, dtype=float, device=self.device)
        pcg_status = wp.zeros(1, dtype=wp.int32, device=self.device)
        pcg_iterations = wp.zeros(1, dtype=wp.int32, device=self.device)
        pressure_aggregate_status = wp.full(1, value=_PRESSURE_STATUS_CONVERGED,
                                            dtype=wp.int32, device=self.device)
        max_iterations_observed = wp.zeros(1, dtype=wp.int32, device=self.device)
        total_iterations_observed = wp.zeros(1, dtype=wp.int32, device=self.device)
        
        initial_z_surf = float((self.nz - 2) * self.dz)
        Z_surf = wp.full(shape=(self.nx, self.ny), value=initial_z_surf, dtype=float, device=self.device)
        Z_surf_new = wp.zeros_like(Z_surf)
        surface_floor_hit = wp.zeros(1, dtype=wp.int32, device=self.device)
        momentum_cfl_exceeded = wp.zeros(1, dtype=wp.int32, device=self.device)
        
        start_time = time.perf_counter()
        
        for step in range(steps):
            current_t = step * dt
            step_dt = _step_size(sim_time_s, dt, step)
            
            # 1. Advect & Apply Marangoni/Boussinesq/Recoil Forces on the
            # current interface. The surface is moved from the projected
            # velocity after this step, rather than from a separate pressure
            # to Bernoulli-speed conversion.
            wp.launch(
                kernel=velocity_advection_forces_kernel,
                dim=shape,
                inputs=[
                    U, V, W, U_new, V_new, W_new, T_arr, Z_surf,
                    self.nx, self.ny, self.nz, self.dx, self.dy, self.dz, step_dt,
                    mu, rho, d_gamma_dT, beta, T_liquidus, T_solidus,
                    P0, Lv, Rs, Tv
                ],
                device=self.device
            )
            U, U_new = U_new, U
            V, V_new = V_new, V
            W, W_new = W_new, W
            
            # 2. Compute Divergence
            wp.launch(
                kernel=compute_divergence_kernel,
                dim=shape,
                inputs=[U, V, W, Div, Z_surf, T_arr, self.nx, self.ny, self.nz, self.dx, self.dy, self.dz, T_solidus],
                device=self.device
            )

            # 3. Solve A p = -rho/dt * div(u), A=-D(G(p)). PCG reductions
            # remain on device; the host does not read a scalar in this loop.
            pcg_rho, pcg_rho_next = launch_pressure_pcg(
                P, Div, Z_surf, T_arr, shape, (self.dx, self.dy, self.dz),
                step_dt, rho, T_solidus,
                pcg_residual, pcg_preconditioned, pcg_direction, pcg_A_direction,
                pcg_rho, pcg_rho_next, pcg_rhs_norm2, pcg_residual_norm2,
                pcg_residual_next_norm2,
                pcg_scale_norm2, pcg_direction_dot_A, pcg_alpha, pcg_beta,
                pcg_status, pcg_iterations,
            )
            wp.launch(kernel=pressure_pcg_accumulate_status_kernel, dim=1,
                      inputs=[pcg_status, pcg_iterations, pressure_aggregate_status,
                              max_iterations_observed, total_iterations_observed], device=self.device)
                
            # 4. Project Velocity (Make Divergence-Free)
            wp.launch(
                kernel=project_velocity_kernel,
                dim=shape,
                inputs=[U, V, W, P, Z_surf, T_arr, self.nx, self.ny, self.nz, self.dx, self.dy, self.dz, step_dt, rho, T_solidus],
                device=self.device
            )

            # The predictor clamp cannot bound velocities after pressure
            # projection. Check the actual projected field before any explicit
            # enthalpy transport or energy-ledger update.
            wp.launch(
                kernel=validate_projected_momentum_cfl_kernel,
                dim=shape,
                inputs=[U, V, W, Z_surf, T_arr, momentum_cfl_exceeded,
                        self.nx, self.ny, self.nz, self.dx, self.dy, self.dz,
                        step_dt, mu / rho, T_solidus,
                        _PHASE22_MOMENTUM_CFL_LIMIT],
                device=self.device,
            )

            # Keep the actual post-projection divergence for the final residual
            # report. This is a device launch only; synchronization is deferred
            # to the existing end-of-run barrier.
            wp.launch(
                kernel=compute_divergence_kernel,
                dim=shape,
                inputs=[U, V, W, Div_post, Z_surf, T_arr, self.nx, self.ny,
                        self.nz, self.dx, self.dy, self.dz, T_solidus],
                device=self.device,
            )

            # Predict the graph update from projected velocities before
            # enthalpy applies surface fluxes. If evaporation would be clipped
            # by the bottom-domain floor, stop before recording an energy/mass
            # loss that the geometry cannot represent conservatively.
            wp.launch(
                kernel=free_surface_kinematics_kernel,
                dim=(self.nx, self.ny),
                inputs=[Z_surf, Z_surf_new, surface_floor_hit, U, V, W, T_arr,
                        self.nx, self.ny, self.nz, self.dx, self.dy, self.dz,
                        step_dt, rho, T_solidus, P0, Lv, Rs, Tv],
                device=self.device,
            )
            wp.synchronize_device(self.device)
            if int(surface_floor_hit.numpy()[0]) != 0:
                raise RuntimeError(
                    "Phase 22 validity error: evaporating molten surface reached "
                    "the z=2*dz domain floor; mass and energy cannot be conserved."
                )
            if int(momentum_cfl_exceeded.numpy()[0]) != 0:
                raise RuntimeError(
                    "Phase 22 validity error: projected velocity exceeds the explicit "
                    "momentum and enthalpy transport CFL limit."
                )
            
            # 5. Advect Enthalpy and Compute New Temperatures on the current
            # interface. Its evaporation mass flux is shared with the
            # kinematic height update below.
            wp.launch(
                kernel=enthalpy_3d_nonlinear_step_kernel,
                dim=shape,
                inputs=[
                    T_arr, H_arr, U, V, W, T_new, H_new, Z_surf,
                    self.nx, self.ny, self.nz,
                    self.dx, self.dy, self.dz,
                    step_dt, current_t, rho, L_f, T_solidus, T_liquidus,
                    tp_t, tp_x, tp_y, tp_p, num_pts,
                    30e-6, 0.4, 
                    10.0, 0.35, float(T_preheat_K),
                    P0, Lv, Rs, Tv,
                    float(cp_solid), float(cp_liquid), float(k_solid), float(k_liquid)
                ],
                device=self.device
            )

            if energy_arrays is not None:
                wp.launch(
                    kernel=phase22_energy_ledger_step_kernel,
                    dim=shape,
                    inputs=[
                        T_arr, H_arr, U, V, W, Z_surf,
                        energy_arrays["laser_absorbed_in_J"],
                        energy_arrays["conduction_net_J"], energy_arrays["advection_net_J"],
                        energy_arrays["convection_out_J"], energy_arrays["radiation_out_J"],
                        energy_arrays["evaporation_out_J"], energy_arrays["surface_mask_reset_J"],
                        self.nx, self.ny, self.nz, self.dx, self.dy, self.dz,
                        step_dt, current_t, rho, L_f, T_solidus, T_liquidus,
                        tp_t, tp_x, tp_y, tp_p, num_pts,
                        30e-6, 0.4, 10.0, 0.35, float(T_preheat_K),
                        P0, Lv, Rs, Tv, float(cp_solid), float(cp_liquid),
                        float(k_solid), float(k_liquid),
                    ],
                    device=self.device,
                )

            # The preflighted graph update becomes active with this enthalpy step.
            T_arr, T_new = T_new, T_arr
            H_arr, H_new = H_new, H_arr
            Z_surf, Z_surf_new = Z_surf_new, Z_surf
            # The enthalpy step uses the previous whole-cell geometry. Reconcile
            # cells crossed by the newly advanced graph before publishing or
            # reusing this state; any energy correction is charged exactly here.
            wp.launch(
                kernel=phase22_reconcile_surface_mask_kernel,
                dim=shape,
                inputs=[
                    T_arr, H_arr, Z_surf, surface_reset_accumulator,
                    self.nx, self.ny, self.nz, self.dx, self.dy, self.dz,
                    rho, L_f, T_solidus, T_liquidus, cp_solid, cp_liquid,
                    float(T_preheat_K), 1 if energy_arrays is not None else 0,
                ],
                device=self.device,
            )
            
        wp.synchronize_device(self.device)
        elapsed = time.perf_counter() - start_time
        
        T_host = T_arr.numpy()
        Z_host = Z_surf.numpy()
        U_host = U.numpy()
        V_host = V.numpy()
        W_host = W.numpy()
        
        melted = _surface_liquid_mask(T_host, Z_host, self.dz, T_liquidus)
        melt_vol_um3 = np.sum(melted) * (self.dx * self.dy * self.dz) * 1e18
        max_T = np.max(T_host)
        min_z_m = np.min(Z_host)
        max_depth_um = (initial_z_surf - min_z_m) * 1e6
        
        # Max velocity magnitude for diagnostics
        V_mag = np.sqrt(U_host**2 + V_host**2 + W_host**2)
        max_V = np.max(V_mag)

        if steps:
            pressure_status_code = int(pressure_aggregate_status.numpy()[0])
            pressure_all_steps_ok = pressure_status_code == _PRESSURE_STATUS_CONVERGED
            pressure_iterations_used = int(max_iterations_observed.numpy()[0])
            pressure_total_iterations_used = int(total_iterations_observed.numpy()[0])
            pressure_residual2 = float(pcg_residual_norm2.numpy()[0])
            pressure_scale2 = float(pcg_scale_norm2.numpy()[0])
            pressure_linear_relative_residual = (
                float(np.sqrt(pressure_residual2 / pressure_scale2))
                if pressure_scale2 > 0.0 and np.isfinite(pressure_residual2 / pressure_scale2)
                else (0.0 if pressure_residual2 == 0.0 else float("inf"))
            )
            div_before_host = Div.numpy()
            div_after_host = Div_post.numpy()
            div_before_norm = float(np.linalg.norm(div_before_host.ravel()))
            div_after_norm = float(np.linalg.norm(div_after_host.ravel()))
            pressure_post_divergence_ratio = (
                div_after_norm / div_before_norm if div_before_norm > 0.0
                else (0.0 if div_after_norm == 0.0 else float("inf"))
            )
            pressure_post_divergence_max = float(np.max(np.abs(div_after_host)))
            pressure_projection_converged = (
                pressure_all_steps_ok
                and pressure_linear_relative_residual <= _PRESSURE_RELATIVE_DIVERGENCE_TOLERANCE
                and pressure_post_divergence_ratio <= _PRESSURE_RELATIVE_DIVERGENCE_TOLERANCE
            )
            if pressure_projection_converged:
                pressure_projection_status = "converged"
            elif pressure_status_code == _PRESSURE_STATUS_NUMERICAL_FAILURE:
                pressure_projection_status = "numerical_failure"
            else:
                pressure_projection_status = "not_converged"
        else:
            pressure_status_code = 0
            pressure_iterations_used = 0
            pressure_total_iterations_used = 0
            pressure_linear_relative_residual = None
            pressure_post_divergence_ratio = None
            pressure_post_divergence_max = None
            pressure_projection_converged = None
            pressure_projection_status = "not_run"
        
        result = {
            "melt_volume_um3": float(melt_vol_um3),
            "max_temperature_K": float(max_T),
            "max_velocity_m_s": float(max_V),
            "keyhole_depth_um": float(max_depth_um),
            "sim_time_s": elapsed,
            "device": self.device,
            "steps": steps,
            "pressure_projection_solver": "preconditioned_conjugate_gradient",
            # Keep the old field as a compatibility alias, with the meaning
            # made explicit by the max-per-step and total fields below.
            "pressure_projection_iterations": pressure_iterations_used,
            "pressure_projection_max_iterations_per_timestep": pressure_iterations_used,
            "pressure_projection_total_iterations": pressure_total_iterations_used,
            "pressure_projection_max_iterations": _PRESSURE_PCG_MAX_ITERATIONS,
            "pressure_projection_relative_divergence_tolerance": _PRESSURE_RELATIVE_DIVERGENCE_TOLERANCE,
            "pressure_projection_status": pressure_projection_status,
            "pressure_projection_converged": pressure_projection_converged,
            "pressure_projection_relative_linear_residual": pressure_linear_relative_residual,
            "pressure_projection_post_divergence_relative_l2": pressure_post_divergence_ratio,
            "pressure_projection_post_divergence_max_s_inv": pressure_post_divergence_max,
            "pressure_projection_post_residual_scope": "last timestep; linear gate accumulated over all timesteps" if steps else "not_run"
        }
        if energy_arrays is not None:
            energy_terms = {
                key: float(np.sum(value.numpy(), dtype=np.float64))
                for key, value in energy_arrays.items()
            }
            initial_total = float(h_init * diagnostic_cell_count * self.dx * self.dy * self.dz)
            final_total = float(np.sum(H_arr.numpy(), dtype=np.float64) * self.dx * self.dy * self.dz)
            latent_fraction = np.clip((T_host - T_solidus) / (T_liquidus - T_solidus), 0.0, 1.0)
            final_latent = float(np.sum(rho * L_f * latent_fraction, dtype=np.float64)
                                 * self.dx * self.dy * self.dz)
            initial_fraction = min(1.0, max(0.0, (T_preheat_K - T_solidus)
                                             / (T_liquidus - T_solidus)))
            initial_latent = float(rho * L_f * initial_fraction
                                   * diagnostic_cell_count * self.dx * self.dy * self.dz)
            enthalpy_change = final_total - initial_total
            modeled_change = (
                energy_terms["laser_absorbed_in_J"]
                + energy_terms["conduction_net_J"]
                + energy_terms["advection_net_J"]
                - energy_terms["convection_out_J"]
                - energy_terms["radiation_out_J"]
                - energy_terms["evaporation_out_J"]
                + energy_terms["surface_mask_reset_J"]
            )
            residual = enthalpy_change - modeled_change
            expected_absorbed = float(0.4 * np.trapezoid(toolpath["p"], toolpath["t"]))
            result["energy_ledger"] = {
                "terms_J": energy_terms,
                "enthalpy_J": {
                    "initial_total": initial_total,
                    "final_total": final_total,
                    "change_total": enthalpy_change,
                    "initial_sensible": initial_total - initial_latent,
                    "final_sensible": final_total - final_latent,
                    "initial_latent": initial_latent,
                    "final_latent": final_latent,
                    "change_sensible": (final_total - final_latent) - (initial_total - initial_latent),
                    "change_latent": final_latent - initial_latent,
                },
                "closure": {
                    "modeled_change_J": modeled_change,
                    "residual_J": residual,
                    "relative_error": abs(residual) / max(
                        abs(energy_terms["laser_absorbed_in_J"])
                        + abs(energy_terms["conduction_net_J"])
                        + abs(energy_terms["advection_net_J"])
                        + abs(energy_terms["convection_out_J"])
                        + abs(energy_terms["radiation_out_J"])
                        + abs(energy_terms["evaporation_out_J"])
                        + abs(energy_terms["surface_mask_reset_J"]),
                        1e-30,
                    ),
                },
                "laser_reference": {
                    "nominal_absorbed_J": expected_absorbed,
                    "domain_capture_fraction": (
                        energy_terms["laser_absorbed_in_J"] / expected_absorbed
                        if expected_absorbed > 0.0 else None
                    ),
                    "quadrature": "per-step laser field integrated over interior top cells; nominal input uses trapezoidal toolpath power",
                },
                "scope": "thermal enthalpy only; conduction includes fixed-shell exchange, advection is a shared-face internal flux, and surface-mask resets are explicit; pressure/viscous work is not coupled into enthalpy",
            }
        if include_diagnostic_fields:
            result["diagnostic_fields"] = {
                "temperature_K": T_host.copy(),
                "enthalpy_J_m3": H_arr.numpy(),
                "velocity_x_m_s": U_host.copy(),
                "velocity_y_m_s": V_host.copy(),
                "velocity_z_m_s": W_host.copy(),
                "pressure_Pa": P.numpy(),
                "surface_z_m": Z_host.copy(),
            }
        return result

if __name__ == "__main__":
    print("Initializing Phase 25 Multi-Track GPU FDM Solver (Marangoni + Recoil Hydrodynamics)...")
    solver = TransientEnthalpy3DGPU(nx=128, ny=128, nz=64, dx=2e-6, dy=2e-6, dz=2e-6)
    
    # 5-point Square Toolpath Hatch
    cx, cy = 128e-6, 128e-6
    sq = 25e-6
    toolpath = {
        't': [0.0, 50e-6, 100e-6, 150e-6, 200e-6],
        'x': [cx-sq, cx+sq, cx+sq, cx-sq, cx-sq],
        'y': [cy-sq, cy-sq, cy+sq, cy+sq, cy-sq],
        'p': [200.0, 200.0, 200.0, 200.0, 200.0]
    }
    
    print("Running square hatch toolpath simulation with full fluid mechanics...")
    from four_alloy_materials import thermal_props
    _m = thermal_props("ti6al4v")  # demo alloy; the material authority supplies every value
    res = solver.solve_toolpath(
        toolpath=toolpath,
        rho=_m["density_kg_m3"], L_f=_m["latent_heat_fusion_J_kg"],
        T_solidus=_m["solidus_C"] + 273.15, T_liquidus=_m["liquidus_C"] + 273.15,
        Lv=_m["latent_heat_vap_J_kg"], Rs=8.314462618 / _m["M_molar_kg_mol"],
        Tv=_m["boiling_C"] + 273.15,
        cp_solid=_m["specific_heat_J_kgK"], cp_liquid=_m["specific_heat_liquid_J_kgK"],
        k_solid=_m["thermal_conductivity_W_mK"], k_liquid=_m["thermal_conductivity_liquid_W_mK"],
    )
    print(f"Results: {res}")
    print(f"RUN COMPLETE; pressure-projection status={res['pressure_projection_status']}.")
