"""Conservative cell-integrated Gaussian heating on the stationary cubic grid.

The Gaussian integral follows NIST DLMF 7.2; time integration uses two-point
Gauss-Legendre quadrature. This improves source discretization, not model fidelity
to fluid flow. The heat equation still advances with explicit Euler.
"""
import numpy as np
from lpbf_run_progress import current_progress
from lpbf_core_physics import (SOURCE_INTEGRATION, GAUSS_NODES, _evaluate,
                               gaussian_interval, cell_weights, integrated_source)

MINIMUM_SOURCE_CAPTURE_FRACTION = 1. / 1.01


def require_source_capture(capture, minimum_fraction):
    """Validate the shared source-capture limit before applying its renormalized field."""
    if (isinstance(capture, (bool, np.bool_)) or not isinstance(capture, (int, float, np.number))
            or not np.isfinite(capture) or capture < minimum_fraction):
        raise ValueError(
            f"Gaussian source capture {capture:.3%} is below "
            f"the {minimum_fraction:.0%} minimum; expand the represented domain"
        )
    return capture


def source_limited_step(axis, z, dx, segment, time, dt, surface, radius, penetration, power, passive_rate, capacity, axis_y=None,
                        incidence_angle_deg=0.0, incidence_azimuth_deg=0.0):
    """Reintegrate the moving source whenever its sensible-increment cap cuts dt."""
    progress = current_progress()
    for retries in range(12):
        if progress is not None:
            progress.before_source_evaluation(retries)
        try:
            source, capture = integrated_source(axis, z, dx, segment, time, dt, surface, radius, penetration, power,
                                               axis_y=axis_y, incidence_angle_deg=incidence_angle_deg,
                                               incidence_azimuth_deg=incidence_azimuth_deg)
        except Exception:
            if progress is not None:
                progress.source_evaluation_failed()
            raise
        rate = passive_rate+source
        allowed = float(np.min(25.*capacity/np.maximum(np.abs(rate), 1e-30)))
        if allowed >= dt*(1-1e-12):
            return dt, source, rate, capture, retries
        dt = .95*allowed
    raise ValueError("Moving-source timestep limit failed to converge")


def conduction_diagonal(k, active, dx):
    """Positive local sum of interior conductances per cell volume [W/m³/K]."""
    diagonal = np.zeros_like(k)
    for axis in range(3):
        lo, hi = [slice(None)]*3, [slice(None)]*3
        lo[axis], hi[axis] = slice(None, -1), slice(1, None)
        lo, hi = tuple(lo), tuple(hi)
        face = 2*k[lo]*k[hi]/(k[lo]+k[hi])/dx**2*(active[lo]&active[hi])
        diagonal[lo] += face
        diagonal[hi] += face
    return diagonal
