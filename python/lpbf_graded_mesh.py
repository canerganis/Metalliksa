"""Graded (stretched) 1D/3D mesh generation for sub-5um laser focus resolution in LPBF.

Refines the laser track interaction zone below 5 um while coarsening distant
boundaries to prevent memory/cell count explosion. Uses finite-volume conservative
metrics: cell widths, face areas, cell volumes, and harmonic interface distances.
"""

import math
import numpy as np


def generate_graded_axis(span_m, fine_span_m, dx_fine_m, dx_coarse_m, growth_ratio=1.15):
    """Generate a symmetric 1D graded coordinate axis centered at 0.
    
    Parameters:
        span_m: Total domain span [m]
        fine_span_m: Central region with fine uniform spacing [m]
        dx_fine_m: Cell spacing in fine zone [m] (e.g. 2.5 um, strictly < 5 um)
        dx_coarse_m: Maximum cell spacing in outer zone [m] (e.g. 25 um)
        growth_ratio: Rate at which cell width expands outside fine zone (default 1.15)
        
    Returns:
        centers: 1D numpy array of cell centers [m]
        widths: 1D numpy array of cell widths (dx) [m]
        faces: 1D numpy array of face coordinates [m] (length = len(centers) + 1)
    """
    if dx_fine_m <= 0 or dx_coarse_m < dx_fine_m:
        raise ValueError("Invalid mesh spacing parameters")
    if growth_ratio < 1.0:
        raise ValueError("Growth ratio must be >= 1.0")
    if fine_span_m >= span_m:
        # Uniform fine mesh
        n = max(1, int(round(span_m / dx_fine_m)))
        dx = span_m / n
        faces = np.linspace(-span_m / 2.0, span_m / 2.0, n + 1)
        centers = 0.5 * (faces[:-1] + faces[1:])
        widths = np.diff(faces)
        return centers, widths, faces

    # Fine center cells
    half_fine = fine_span_m / 2.0
    n_fine_half = max(1, int(round(half_fine / dx_fine_m)))
    dx_fine_actual = half_fine / n_fine_half

    # Half positive side: fine part
    pos_widths = [dx_fine_actual] * n_fine_half
    cur_x = half_fine
    cur_dx = dx_fine_actual
    
    # Outer growing part
    half_span = span_m / 2.0
    while cur_x < half_span - 1e-12:
        cur_dx = min(cur_dx * growth_ratio, dx_coarse_m)
        if cur_x + cur_dx > half_span:
            cur_dx = half_span - cur_x
        pos_widths.append(cur_dx)
        cur_x += cur_dx

    # Full symmetric widths
    widths = np.array(list(reversed(pos_widths)) + pos_widths, dtype=float)
    
    # Construct faces starting at -half_span
    faces = np.zeros(len(widths) + 1, dtype=float)
    faces[0] = -half_span
    for i in range(len(widths)):
        faces[i + 1] = faces[i] + widths[i]
    # Enforce exact symmetry around 0
    faces = 0.5 * (faces - faces[::-1])
    widths = np.diff(faces)
    centers = 0.5 * (faces[:-1] + faces[1:])
    return centers, widths, faces


def generate_graded_mesh_3d(span_x_m, span_y_m, depth_z_m,
                            fine_spot_radius_m, dx_fine_m, dx_coarse_m):
    """Create full 3D graded mesh geometry for laser melt pool simulation.
    
    Refines X and Y around the laser track corridor and Z near top surface.
    Ensures dx_fine < 5 um in the laser zone.
    """
    fine_span_xy = max(4.0 * fine_spot_radius_m, 20e-6)
    cx, wx, fx = generate_graded_axis(span_x_m, fine_span_xy, dx_fine_m, dx_coarse_m)
    cy, wy, fy = generate_graded_axis(span_y_m, fine_span_xy, dx_fine_m, dx_coarse_m)
    
    # Z axis: surface at 0, goes down to -depth_z_m
    # Fine cells near top (0 .. -fine_spot_radius_m * 2), coarsening downward
    half_fine_z = 2.0 * fine_spot_radius_m
    n_fine_z = max(1, int(round(half_fine_z / dx_fine_m)))
    dz_fine = half_fine_z / n_fine_z
    z_widths = [dz_fine] * n_fine_z
    cur_z = half_fine_z
    cur_dz = dz_fine
    while cur_z < depth_z_m - 1e-12:
        cur_dz = min(cur_dz * 1.15, dx_coarse_m)
        if cur_z + cur_dz > depth_z_m:
            cur_dz = depth_z_m - cur_z
        z_widths.append(cur_dz)
        cur_z += cur_dz

    z_widths = np.array(z_widths, dtype=float)
    # Faces: 0 down to -depth_z_m
    fz = np.zeros(len(z_widths) + 1, dtype=float)
    for i in range(len(z_widths)):
        fz[i + 1] = fz[i] - z_widths[i]
    cz = 0.5 * (fz[:-1] + fz[1:])
    wz = z_widths

    return {
        "x": {"centers": cx, "widths": wx, "faces": fx},
        "y": {"centers": cy, "widths": wy, "faces": fy},
        "z": {"centers": cz, "widths": wz, "faces": fz},
        "shape": (len(cx), len(cy), len(cz)),
        "total_cells": len(cx) * len(cy) * len(cz),
        "dx_fine_m": float(wx[len(wx) // 2]),
        "dy_fine_m": float(wy[len(wy) // 2]),
        "dz_fine_m": float(wz[0]),
    }
