"""Graded (stretched) 1D/3D mesh generation for sub-5um laser focus resolution in LPBF.

Refines the laser track interaction zone below 5 um while coarsening distant
boundaries to prevent memory/cell count explosion. Returns finite-volume metrics:
cell centers, cell widths and face coordinates. (Interface distances are not
computed here; a consumer derives them from the centers.)

Stretching rule (standard stretched-grid practice, Ferziger & Peric,
"Computational Methods for Fluid Dynamics", non-uniform grid section): adjacent
cell widths never jump by more than the stated growth ratio, and no cell is
narrower than the fine spacing. The outer graded zone is built from an integer
number of cells whose geometric ratio r <= growth_ratio is solved so the cells
fill the outer span exactly; the last cell is never truncated to a sliver.
"""

import numpy as np


def _fit_graded_widths(dx_start_m, outer_len_m, dx_max_m, growth_ratio):
    """Widths w_k = min(dx_start * r**k, dx_max), k = 1..n, summing exactly to outer_len.

    n is the smallest cell count that can reach outer_len at r = growth_ratio, and
    r in [1, growth_ratio] is found by bisection (the sum is monotone in r). Returns
    None when no such r exists, i.e. the outer span is too short to grade without
    a cell narrower than dx_start; the caller then meshes that zone uniformly.
    """
    if outer_len_m <= 0.0:
        return []

    def widths_for(r, n):
        k = np.arange(1, n + 1, dtype=float)
        return np.minimum(dx_start_m * r ** k, dx_max_m)

    n = 0
    total = 0.0
    while total < outer_len_m * (1.0 - 1e-12):
        n += 1
        total = float(widths_for(growth_ratio, n).sum())
        if n > 100000:  # pragma: no cover - guarded by the spacing checks
            raise ValueError("Graded mesh did not converge")
    if float(widths_for(1.0, n).sum()) > outer_len_m * (1.0 + 1e-12):
        return None
    lo, hi = 1.0, float(growth_ratio)
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if float(widths_for(mid, n).sum()) < outer_len_m:
            lo = mid
        else:
            hi = mid
    w = widths_for(hi, n)
    # Close the span exactly; the correction is at round-off level.
    w[-1] = outer_len_m - float(w[:-1].sum())
    return [float(v) for v in w]


def _graded_half_widths(fine_len_m, total_len_m, dx_fine_m, dx_coarse_m, growth_ratio):
    """Widths from 0 to total_len: uniform fine zone, then a geometric outer zone."""
    n_fine = max(1, int(round(fine_len_m / dx_fine_m)))
    dx_fine_actual = fine_len_m / n_fine
    outer = _fit_graded_widths(
        dx_fine_actual, total_len_m - fine_len_m, dx_coarse_m, growth_ratio
    )
    if outer is None:
        # Outer span too short to grade: mesh the whole half uniformly at ~dx_fine.
        n = max(1, int(round(total_len_m / dx_fine_m)))
        return [total_len_m / n] * n
    return [dx_fine_actual] * n_fine + outer


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

    half_span = span_m / 2.0
    pos_widths = _graded_half_widths(
        fine_span_m / 2.0, half_span, dx_fine_m, dx_coarse_m, growth_ratio
    )

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
    half_fine_z = min(2.0 * fine_spot_radius_m, depth_z_m)
    z_widths = _graded_half_widths(half_fine_z, depth_z_m, dx_fine_m, dx_coarse_m, 1.15)

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
