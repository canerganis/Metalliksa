import numpy as np
import warp as wp
import os

os.environ.setdefault("HOME", os.environ.get("USERPROFILE", ""))

_wp_initialized = False

def ensure_wp_initialized():
    global _wp_initialized
    if not _wp_initialized:
        wp.init()
        _wp_initialized = True

@wp.kernel
def rosenthal_slice_kernel(
    na: int,
    nb: int,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    z_val: float,
    plane: int, # 0 for XY, 1 for XZ, 2 for YZ
    T0: float,
    P_eff: float,
    k_th: float,
    v_scan: float,
    alpha_th: float,
    r_reg: float,
    T_out: wp.array(dtype=float)
):
    tid = wp.tid()
    if tid >= na * nb:
        return

    # Row-major [ia][ib] (axis a outermost), the layout of the CPU sample_thermal_slice and of the
    # frontend reader T_C[ia * nb + ib] (meltPool3DGeometry.ts).
    i = tid // nb
    j = tid % nb

    dx = (x_max - x_min) / float(wp.max(1, na - 1))
    dy = (y_max - y_min) / float(wp.max(1, nb - 1))

    a = x_min + float(i) * dx
    b = y_min + float(j) * dy

    x_m = float(0.0)
    y_m = float(0.0)
    z_m = float(0.0)

    if plane == 0:
        x_m = a
        y_m = b
        z_m = z_val
    elif plane == 1:
        x_m = a
        y_m = z_val
        z_m = b
    else:
        x_m = z_val
        y_m = a
        z_m = b

    R = wp.sqrt(x_m * x_m + y_m * y_m + z_m * z_m + r_reg * r_reg)
    arg = -v_scan * (R + x_m) / (2.0 * alpha_th)
    if arg < -45.0:
        arg = -45.0
    if arg > 20.0:
        arg = 20.0

    T_out[tid] = T0 + (P_eff / (2.0 * 3.1415926535 * k_th * R)) * wp.exp(arg)

def compute_rosenthal_slice_warp(axis_a_span, axis_b_span, na, nb, plane, z_val, T0, P_eff, k_th, v_scan, alpha_th, r_reg):
    ensure_wp_initialized()
    total_points = na * nb
    T_out = wp.zeros(shape=total_points, dtype=float, device="cuda:0")
    
    wp.launch(
        kernel=rosenthal_slice_kernel,
        dim=total_points,
        inputs=[
            na, nb, 
            axis_a_span[0], axis_a_span[1], 
            axis_b_span[0], axis_b_span[1], 
            z_val, plane, 
            T0, P_eff, k_th, v_scan, alpha_th, r_reg, 
            T_out
        ],
        device="cuda:0"
    )
    wp.synchronize()
    # Round to 1 decimal place to match CPU implementation
    return np.round(T_out.numpy(), 1).tolist()
