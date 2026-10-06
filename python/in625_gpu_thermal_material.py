"""Bounded CPU/CUDA constitutive adapter for the IN625 screening model.

This module evaluates only the existing mass-basis Cp, k, liquid fraction,
and specific enthalpy law. It is not a thermal field solver and does not
qualify IN625 for full transient or GPU LPBF use. Inputs are restricted to
the source model's 273.15..1623.15 K range; no extrapolation is performed.
The underlying JMatPro-derived solid fit and liquid/mushy assumptions remain
unvalidated screening inputs (see ``in625_thermal_material``).
"""

from __future__ import annotations

from in625_thermal_material import (
    LATENT_HEAT_J_KG,
    LIQUID_CP_J_KGK,
    LIQUID_K_W_MK,
    LIQUIDUS_K,
    REFERENCE_TEMPERATURE_K,
    SOLIDUS_K,
    _CP_COEFFICIENTS,
    _K_COEFFICIENTS,
    in625_lpbf_thermal_snapshot,
)


_REVISION = in625_lpbf_thermal_snapshot()["materialRevisionSha256"]
_VALIDATION_STATUS = "unvalidated-literature-model-screening"


def _validate_cpu_input(temperature_k):
    import numpy as np

    if isinstance(temperature_k, (bool, np.bool_)):
        raise ValueError("IN625 screening temperature must be a finite Kelvin number")
    values = np.asarray(temperature_k)
    if values.dtype.kind not in "iuf":
        raise ValueError("IN625 screening temperature must be a finite Kelvin number")
    values = values.astype(np.float64, copy=False)
    if not np.isfinite(values).all() or (values < REFERENCE_TEMPERATURE_K).any() or (values > LIQUIDUS_K).any():
        raise ValueError("IN625 fusion-enthalpy screening outside 273.15..1623.15 K")
    return values, values.ndim == 0


def in625_cpu_thermal_at_kelvin(temperature_k):
    """Evaluate bounded IN625 Cp, k and H(T) on CPU using NumPy float64.

    Scalar input produces Python floats; array-like input produces arrays.
    Returned ``validationStatus`` is intentionally unqualified. This is a
    constitutive-law adapter only, not GPU field-physics parity.
    """
    import numpy as np

    t, scalar = _validate_cpu_input(temperature_k)
    a, b, c, d = _CP_COEFFICIENTS
    ka, kb = _K_COEFFICIENTS
    width = LIQUIDUS_K - SOLIDUS_K

    def primitive(x):
        return a*x + b*x**2/2.0 + c*x**3/3.0 + d*x**4/4.0

    cp_solid = a + b*t + c*t**2 + d*t**3
    k_solid = ka + kb*t
    cp_at_solidus = a + b*SOLIDUS_K + c*SOLIDUS_K**2 + d*SOLIDUS_K**3
    delta = t - SOLIDUS_K
    fraction_mushy = delta / width
    cp_mushy = cp_at_solidus + (LIQUID_CP_J_KGK - cp_at_solidus)*fraction_mushy
    k_at_solidus = ka + kb*SOLIDUS_K
    k_mushy = k_at_solidus + (LIQUID_K_W_MK - k_at_solidus)*fraction_mushy
    h_mushy = (
        primitive(SOLIDUS_K) - primitive(REFERENCE_TEMPERATURE_K)
        + cp_at_solidus*delta
        + (LIQUID_CP_J_KGK - cp_at_solidus)*delta**2/(2.0*width)
        + LATENT_HEAT_J_KG*fraction_mushy
    )

    is_solid = t <= SOLIDUS_K
    cp = np.where(is_solid, cp_solid, cp_mushy)
    conductivity = np.where(is_solid, k_solid, k_mushy)
    enthalpy = np.where(
        is_solid,
        primitive(t) - primitive(REFERENCE_TEMPERATURE_K),
        h_mushy,
    )
    effective_cp = np.where(is_solid, cp_solid, cp_mushy + LATENT_HEAT_J_KG/width)
    fraction = np.where(is_solid, 0.0, fraction_mushy)

    def scalarize(value):
        return float(value) if scalar else value

    return {
        "materialId": "in625",
        "materialRevisionSha256": _REVISION,
        "validationStatus": _VALIDATION_STATUS,
        "temperature_K": scalarize(t),
        "specificHeat_J_kgK": scalarize(cp),
        "effectiveHeatCapacity_J_kgK": scalarize(effective_cp),
        "thermalConductivity_W_mK": scalarize(conductivity),
        "liquidFraction": scalarize(fraction),
        "specificEnthalpy_J_kg": scalarize(enthalpy),
    }


def in625_cuda_thermal_at_kelvin(temperature_k, *, device):
    """Evaluate the same bounded law with PyTorch on an explicitly named CUDA device.

    ``device`` must be an explicit ordinal such as ``"cuda:0"``. The returned
    numerical fields are float64 tensors on that device. This adapter provides
    constitutive evaluation only; it does not establish same-physics GPU field
    solver parity or experimental/scientific validity.
    """
    import torch

    if not isinstance(device, str) or not device.startswith("cuda:"):
        raise ValueError("IN625 CUDA adapter requires an explicit device such as cuda:0")
    suffix = device.removeprefix("cuda:")
    if not suffix.isdecimal():
        raise ValueError("IN625 CUDA adapter requires an explicit device such as cuda:0")
    cuda_device = torch.device(device)
    if not torch.cuda.is_available() or int(suffix) >= torch.cuda.device_count():
        raise RuntimeError(f"Requested IN625 CUDA device is unavailable: {device}")

    if isinstance(temperature_k, bool):
        raise ValueError("IN625 screening temperature must be finite numeric Kelvin")
    if isinstance(temperature_k, torch.Tensor) and (
        temperature_k.dtype == torch.bool or temperature_k.is_complex()
    ):
        raise ValueError("IN625 screening temperature must be finite numeric Kelvin")
    try:
        t = torch.as_tensor(temperature_k, dtype=torch.float64, device=cuda_device)
    except (TypeError, ValueError) as exc:
        raise ValueError("IN625 screening temperature must be finite numeric Kelvin") from exc
    if not torch.isfinite(t).all().item():
        raise ValueError("IN625 screening temperature must be finite numeric Kelvin")
    if ((t < REFERENCE_TEMPERATURE_K) | (t > LIQUIDUS_K)).any().item():
        raise ValueError("IN625 fusion-enthalpy screening outside 273.15..1623.15 K")

    a, b, c, d = _CP_COEFFICIENTS
    ka, kb = _K_COEFFICIENTS
    width = LIQUIDUS_K - SOLIDUS_K

    def primitive(x):
        return a*x + b*x**2/2.0 + c*x**3/3.0 + d*x**4/4.0

    cp_solid = a + b*t + c*t**2 + d*t**3
    k_solid = ka + kb*t
    cp_at_solidus = a + b*SOLIDUS_K + c*SOLIDUS_K**2 + d*SOLIDUS_K**3
    delta = t - SOLIDUS_K
    fraction_mushy = delta / width
    cp_mushy = cp_at_solidus + (LIQUID_CP_J_KGK - cp_at_solidus)*fraction_mushy
    k_at_solidus = ka + kb*SOLIDUS_K
    k_mushy = k_at_solidus + (LIQUID_K_W_MK - k_at_solidus)*fraction_mushy
    h_mushy = (
        primitive(SOLIDUS_K) - primitive(REFERENCE_TEMPERATURE_K)
        + cp_at_solidus*delta
        + (LIQUID_CP_J_KGK - cp_at_solidus)*delta**2/(2.0*width)
        + LATENT_HEAT_J_KG*fraction_mushy
    )
    is_solid = t <= SOLIDUS_K
    cp = torch.where(is_solid, cp_solid, cp_mushy)
    conductivity = torch.where(is_solid, k_solid, k_mushy)
    enthalpy = torch.where(
        is_solid,
        primitive(t) - primitive(REFERENCE_TEMPERATURE_K),
        h_mushy,
    )
    effective_cp = torch.where(is_solid, cp_solid, cp_mushy + LATENT_HEAT_J_KG/width)
    fraction = torch.where(is_solid, torch.zeros_like(t), fraction_mushy)
    return {
        "materialId": "in625",
        "materialRevisionSha256": _REVISION,
        "validationStatus": _VALIDATION_STATUS,
        "temperature_K": t,
        "specificHeat_J_kgK": cp,
        "effectiveHeatCapacity_J_kgK": effective_cp,
        "thermalConductivity_W_mK": conductivity,
        "liquidFraction": fraction,
        "specificEnthalpy_J_kg": enthalpy,
    }
