"""Thermal liquidus geometry diagnostics using sub-cell linear interpolation.

These utilities do not implement an etched-optical observer, establish independent
track-field provenance, or enable a NIST comparison residual.
"""

import math
import numpy as np


def extract_subcell_liquidus_geometry(y_coords_m, z_coords_m, t_2d_plane, t_liquidus_k):
    """Estimate thermal liquidus geometry on a transverse Y-Z plane.

    This is a thermal contour diagnostic, not a measured or etched optical boundary.
    
    Parameters:
        y_coords_m: 1D array of transverse cell centers [m] (centered at 0)
        z_coords_m: 1D array of vertical cell centers [m] (0 is surface, negative downward)
        t_2d_plane: 2D array of peak temperatures T[y_idx, z_idx] [K]
        t_liquidus_k: Material liquidus temperature [K] (1609.15 K for IN718)
        
    Returns:
        dict: {
            "width_um": float | None,
            "depth_um": float | None,
            "subcell_interpolated": bool,
            "valid": bool
        }
    """
    y_coords_m = np.asarray(y_coords_m, dtype=float)
    z_coords_m = np.asarray(z_coords_m, dtype=float)
    t_2d_plane = np.asarray(t_2d_plane, dtype=float)
    if (y_coords_m.ndim != 1 or z_coords_m.ndim != 1 or t_2d_plane.ndim != 2
            or len(y_coords_m) < 2 or len(z_coords_m) < 2
            or t_2d_plane.shape != (len(y_coords_m), len(z_coords_m))):
        raise ValueError("Coordinate and temperature array dimensions must match")
    if (not np.isfinite(y_coords_m).all() or not np.isfinite(z_coords_m).all()
            or not np.isfinite(t_2d_plane).all()
            or isinstance(t_liquidus_k, bool) or not isinstance(t_liquidus_k, (int, float, np.number))
            or not math.isfinite(t_liquidus_k)):
        raise ValueError("Coordinates, temperatures and liquidus temperature must be finite")
    if np.any(np.diff(y_coords_m) <= 0.0):
        raise ValueError("Y coordinates must be strictly increasing")
    if np.any(np.diff(z_coords_m) >= 0.0):
        raise ValueError("Z coordinates must be strictly decreasing")
    ny, nz = t_2d_plane.shape
        
    # Find molten mask
    molten = (t_2d_plane >= t_liquidus_k)
    if not molten.any():
        return {"width_um": None, "depth_um": None, "subcell_interpolated": False, "valid": False}
        
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

    closed_contour = (
        max_width_m > 0.0
        and max_depth_m > 0.0
        and not molten[0, :].any()
        and not molten[-1, :].any()
        and not molten[:, -1].any()
    )
    return {
        "width_um": float(max_width_m * 1e6) if closed_contour else None,
        "depth_um": float(max_depth_m * 1e6) if closed_contour else None,
        "subcell_interpolated": bool(closed_contour),
        "valid": bool(closed_contour),
    }


def build_six_section_diagnostic_aggregate(section_results):
    """Aggregate six unverified geometry diagnostics across three tracks.
    
    Parameters:
        section_results: list of dicts, each with keys:
            track: int (1, 2, 3)
            position_mm: float (4.9 or 6.0)
            width_um: float
            depth_um: float
            
    Returns:
        dict: Explicitly unverified aggregate; no optical or provenance claim.
    """
    if not isinstance(section_results, (list, tuple)) or len(section_results) != 6:
        raise ValueError("Exactly 6 section diagnostics are required")

    expected_pairs = {(track, position) for track in (1, 2, 3) for position in (4.9, 6.0)}
    actual_pairs = set()
    normalized = []
    for index, result in enumerate(section_results):
        if not isinstance(result, dict):
            raise ValueError(f"Section diagnostic {index} must be a mapping")
        track = result.get("track")
        position = result.get("position_mm")
        if isinstance(track, bool) or not isinstance(track, int) or track not in (1, 2, 3):
            raise ValueError(f"Section diagnostic {index} has an invalid track")
        if (isinstance(position, bool) or not isinstance(position, (int, float))
                or not math.isfinite(position) or position not in (4.9, 6.0)):
            raise ValueError(f"Section diagnostic {index} has an invalid position")
        pair = (track, float(position))
        if pair in actual_pairs:
            raise ValueError(f"Duplicate track-position pair: {pair}")
        actual_pairs.add(pair)

        for quantity in ("width_um", "depth_um"):
            value = result.get(quantity)
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value <= 0.0):
                raise ValueError(f"Section diagnostic {index} has invalid {quantity}")
        normalized.append(dict(result))

    if actual_pairs != expected_pairs:
        raise ValueError("Section diagnostics must cover each track at both required positions")

    widths = [r["width_um"] for r in normalized]
    depths = [r["depth_um"] for r in normalized]
    
    mean_w = float(np.mean(widths))
    std_w = float(np.std(widths, ddof=1))
    mean_d = float(np.mean(depths))
    std_d = float(np.std(depths, ddof=1))
    
    return {
        "status": "unverified-aggregate",
        "resultKind": "thermal-geometry-diagnostic",
        "claimBoundary": {
            "opticalOperatorMatched": False,
            "experimentalValidation": False,
            "independentTrackFieldBinding": False,
        },
        "observationCount": 6,
        "locations_mm": [4.9, 6.0],
        "tracks": [1, 2, 3],
        "sections": normalized,
        "widthMean_um": mean_w,
        "widthStdDev_um": std_w,
        "depthMean_um": mean_d,
        "depthStdDev_um": std_d,
        "width_um": mean_w,
        "depth_um": mean_d,
    }
