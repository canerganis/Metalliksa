"""Conservative cell-centred conduction on a uniform cubic 3-D grid.

The returned values are net conductive heat rates into each cell (W). This
module deliberately does not assign density, heat capacity, material identity,
boundary conditions other than insulated outer faces, or contact defaults.
"""

from __future__ import annotations

import numpy as np


def conduction_heat_rate(
    temperature_K: np.ndarray,
    conductivity_W_mK: np.ndarray,
    dx_m: float,
    *,
    contact_resistance_m2K_W: float,
    interface_z: np.ndarray | None = None,
    active_cells: np.ndarray | None = None,
) -> np.ndarray:
    """Return net conductive heat rate into each cell, in watts.

    ``temperature_K`` and ``conductivity_W_mK`` have identical ``(z, y, x)``
    shapes. ``interface_z`` optionally marks z-normal faces and therefore has
    shape ``(z-1, y, x)``; marked faces use the supplied area-specific contact
    resistance in series with the two half-cell conduction resistances.
    ``active_cells`` optionally disables cells; every face touching a disabled
    cell is insulated. All exterior faces are insulated.

    The contact resistance is an explicit required argument (m² K/W), even
    when no interface mask is supplied. The result is a power rate, not a
    temperature derivative; density and heat capacity belong to the caller.
    """
    temperature = np.asarray(temperature_K, dtype=np.float64)
    conductivity = np.asarray(conductivity_W_mK, dtype=np.float64)
    if temperature.ndim != 3 or any(size < 1 for size in temperature.shape):
        raise ValueError("temperature_K must be a non-empty 3-D array")
    if conductivity.shape != temperature.shape:
        raise ValueError("conductivity_W_mK must match temperature_K shape")
    if not np.all(np.isfinite(temperature)):
        raise ValueError("temperature_K must contain only finite values")
    if not np.all(np.isfinite(conductivity)) or np.any(conductivity <= 0.0):
        raise ValueError("conductivity_W_mK must be finite and strictly positive")

    if isinstance(dx_m, (bool, np.bool_)) or isinstance(contact_resistance_m2K_W, (bool, np.bool_)):
        raise ValueError("dx_m and contact_resistance_m2K_W must be numeric scalars, not booleans")
    dx = float(dx_m)
    resistance = float(contact_resistance_m2K_W)
    if not np.isfinite(dx) or dx <= 0.0:
        raise ValueError("dx_m must be finite and strictly positive")
    if not np.isfinite(resistance) or resistance < 0.0:
        raise ValueError("contact_resistance_m2K_W must be finite and nonnegative")

    if interface_z is None:
        z_interfaces = None
    else:
        z_interfaces = np.asarray(interface_z)
        expected = (temperature.shape[0] - 1, *temperature.shape[1:])
        if z_interfaces.shape != expected or z_interfaces.dtype != np.bool_:
            raise ValueError("interface_z must be a boolean (z-1, y, x) array")

    if active_cells is None:
        active = np.ones(temperature.shape, dtype=np.bool_)
    else:
        active = np.asarray(active_cells)
        if active.shape != temperature.shape or active.dtype != np.bool_:
            raise ValueError("active_cells must be a boolean array matching temperature_K")

    net_rate = np.zeros_like(temperature)
    face_area = dx * dx

    # Axis 0 is z, axis 1 is y, and axis 2 is x. Each internal face is
    # evaluated once and its transfer is applied with opposite signs.
    for axis in range(3):
        low_slice = [slice(None)] * 3
        high_slice = [slice(None)] * 3
        low_slice[axis] = slice(0, -1)
        high_slice[axis] = slice(1, None)
        low_slice_tuple = tuple(low_slice)
        high_slice_tuple = tuple(high_slice)

        k_low = conductivity[low_slice_tuple]
        k_high = conductivity[high_slice_tuple]
        face_k = 2.0 * k_low * k_high / (k_low + k_high)
        if axis == 0 and z_interfaces is not None and resistance > 0.0:
            contact_k = dx / (dx / (2.0 * k_low) + resistance + dx / (2.0 * k_high))
            face_k = np.where(z_interfaces, contact_k, face_k)

        connected = active[low_slice_tuple] & active[high_slice_tuple]
        # Positive transfer is from low-index cell to high-index cell.
        transfer_W = face_k * (temperature[low_slice_tuple] - temperature[high_slice_tuple]) * dx
        transfer_W = np.where(connected, transfer_W, 0.0)
        net_rate[low_slice_tuple] -= transfer_W
        net_rate[high_slice_tuple] += transfer_W

    return net_rate
