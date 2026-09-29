"""NIST AMB2022-03 optical boundary observation operator with sub-cell linear interpolation.

Implements the six-section optical etched-boundary observer for NIST Case 0 IN718 tracks:
- Evaluates at P3 = 4.9 mm and P4 = 6.0 mm from track start for 3 simulated tracks.
- Performs sub-cell linear contour interpolation across cell faces to determine exact
  liquidus boundary coordinates without grid-step quantization error.
- Computes mean width and depth across the 6 physical sections.
"""

import math
import numpy as np


def extract_subcell_optical_boundary(y_coords_m, z_coords_m, t_2d_plane, t_liquidus_k):
    """Compute melt pool width and depth on a transverse Y-Z plane using sub-cell interpolation.
    
    Parameters:
        y_coords_m: 1D array of transverse cell centers [m] (centered at 0)
        z_coords_m: 1D array of vertical cell centers [m] (0 is surface, negative downward)
        t_2d_plane: 2D array of peak temperatures T[y_idx, z_idx] [K]
        t_liquidus_k: Material liquidus temperature [K] (1609.15 K for IN718)
        
    Returns:
        dict: {
            "width_um": float,
            "depth_um": float,
            "subcell_interpolated": bool,
            "valid": bool
        }
    """
    ny, nz = t_2d_plane.shape
    if ny != len(y_coords_m) or nz != len(z_coords_m):
        raise ValueError("Coordinate and temperature array dimensions must match")
        
    # Find molten mask
    molten = (t_2d_plane >= t_liquidus_k)
    if not molten.any():
        return {"width_um": 0.0, "depth_um": 0.0, "subcell_interpolated": True, "valid": False}
        
    # 1. Depth: find deepest point along Z (typically near y=0)
    # Search each vertical column for the liquidus crossing below molten cells
    max_depth_m = 0.0
    for iy in range(ny):
        col_t = t_2d_plane[iy, :]
        for iz in range(nz - 1):
            t_curr = col_t[iz]
            t_next = col_t[iz + 1]
            if t_curr >= t_liquidus_k and t_next < t_liquidus_k:
                # Linear crossing between z[iz] and z[iz+1]
                z_curr = z_coords_m[iz]
                z_next = z_coords_m[iz + 1]
                fraction = (t_liquidus_k - t_curr) / (t_next - t_curr)
                z_cross = z_curr + fraction * (z_next - z_curr)
                depth = -z_cross  # surface is at 0, negative downward
                if depth > max_depth_m:
                    max_depth_m = depth
            elif t_curr >= t_liquidus_k and iz == nz - 1:
                depth = -z_coords_m[iz]
                if depth > max_depth_m:
                    max_depth_m = depth

    # 2. Width: find maximum lateral span across all Z levels
    max_width_m = 0.0
    for iz in range(nz):
        row_t = t_2d_plane[:, iz]
        # Find left crossing (y < 0) and right crossing (y > 0)
        y_left = None
        y_right = None
        for iy in range(ny - 1):
            t_left = row_t[iy]
            t_right = row_t[iy + 1]
            # Left boundary: crossing into molten
            if t_left < t_liquidus_k and t_right >= t_liquidus_k:
                frac = (t_liquidus_k - t_left) / (t_right - t_left)
                y_cross = y_coords_m[iy] + frac * (y_coords_m[iy + 1] - y_coords_m[iy])
                if y_left is None or y_cross < y_left:
                    y_left = y_cross
            # Right boundary: crossing out of molten
            elif t_left >= t_liquidus_k and t_right < t_liquidus_k:
                frac = (t_liquidus_k - t_left) / (t_right - t_left)
                y_cross = y_coords_m[iy] + frac * (y_coords_m[iy + 1] - y_coords_m[iy])
                if y_right is None or y_cross > y_right:
                    y_right = y_cross
        if y_left is not None and y_right is not None:
            width = y_right - y_left
            if width > max_width_m:
                max_width_m = width

    return {
        "width_um": float(max_width_m * 1e6),
        "depth_um": float(max_depth_m * 1e6),
        "subcell_interpolated": True,
        "valid": True,
    }


def build_nist_six_section_observation(section_results):
    """Aggregate 6 section observations (3 tracks x 2 positions [P3, P4]).
    
    Parameters:
        section_results: list of dicts, each with keys:
            track: int (1, 2, 3)
            position_mm: float (4.9 or 6.0)
            width_um: float
            depth_um: float
            
    Returns:
        dict: Standardized NIST optical observation block
    """
    if len(section_results) != 6:
        raise ValueError("Exactly 6 section observations required (3 tracks x 2 positions)")
        
    widths = [r["width_um"] for r in section_results]
    depths = [r["depth_um"] for r in section_results]
    
    mean_w = float(np.mean(widths))
    std_w = float(np.std(widths, ddof=1))
    mean_d = float(np.mean(depths))
    std_d = float(np.std(depths, ddof=1))
    
    return {
        "status": "optical-operator-matched",
        "operator": "amb2022-03-etched-optical-six-section-mean-v1",
        "observationCount": 6,
        "locations_mm": [4.9, 6.0],
        "tracks": [1, 2, 3],
        "sections": section_results,
        "widthMean_um": mean_w,
        "widthStdDev_um": std_w,
        "depthMean_um": mean_d,
        "depthStdDev_um": std_d,
        "width_um": mean_w,
        "depth_um": mean_d,
        "subcellInterpolation": True,
    }
