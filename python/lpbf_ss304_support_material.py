"""Bounded literature model for SS304 support sensitivity calculations.

This is not a specimen-matched AMB2022-03 baseplate property record. In
particular, its density is a room-temperature literature value and its thermal
fits are generic AISI 304 data. Values outside the stated 0--1200 °C range are
rejected rather than extrapolated.
"""
import hashlib
import json
import math

import numpy as np


REFERENCE_TEMPERATURE_K = 273.15
MAXIMUM_TEMPERATURE_K = 1473.15
DENSITY_KG_M3 = 7920.0
CP_A_J_KGK = 6.683
CP_B_J_KGK2 = 0.04906
CP_C_J_KGK = 80.74
K_A_W_MK = 9.705
K_B_W_MK2 = 0.0176
K_C_W_MK3 = -1.60e-6

_SOURCE = "https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=860705"


def ss304_support_thermal_snapshot():
    """Return immutable, literature-derived AISI 304 support-model metadata."""
    snapshot = {
        "schemaVersion": 1,
        "materialId": "ss304",
        "name": "AISI 304 stainless steel (generic support sensitivity model)",
        "capability": "bounded-solid-thermal-properties",
        "validationStatus": "unvalidated-literature-model-screening",
        "provenanceClass": "literature-constitutive-model",
        "source": _SOURCE,
        "sourceLocators": {
            "density": "Section 3.1.1, PDF p. 14; commonly reported at 23 °C",
            "heatCapacity": "Section 3.1.1, Figure 1, PDF p. 14; fit reported in the text",
            "thermalConductivity": "Section 3.1.1, PDF p. 14; recommended Bogaard curve",
        },
        "temperatureCoverage_K": [REFERENCE_TEMPERATURE_K, MAXIMUM_TEMPERATURE_K],
        "density_kg_m3": DENSITY_KG_M3,
        "heatCapacityFit_J_kgK": {
            "form": "A + B*T + C*ln(T)",
            "coefficients": [CP_A_J_KGK, CP_B_J_KGK2, CP_C_J_KGK],
            "temperatureUnit": "K",
        },
        "thermalConductivityFit_W_mK": {
            "form": "A + B*T + C*T^2",
            "coefficients": [K_A_W_MK, K_B_W_MK2, K_C_W_MK3],
            "temperatureUnit": "K",
        },
        "uncertaintyNote": (
            "Generic AISI 304 fits and a commonly reported room-temperature density; "
            "the AMB2022-03 SS304 holder's material certificate, property revision, "
            "and temperature-dependent density are not identified by this source. "
            "No quantified fit uncertainty or independent validation is provided here."
        ),
    }
    payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("utf-8")
    snapshot["materialRevisionSha256"] = hashlib.sha256(payload).hexdigest()
    return snapshot


def ss304_support_thermal_at_kelvin(temperature_k):
    """Evaluate bounded solid cp, k, density and enthalpy from 273.15 K."""
    if isinstance(temperature_k, bool) or not isinstance(temperature_k, (int, float)):
        raise ValueError("SS304 screening temperature must be a finite Kelvin number")
    temperature_k = float(temperature_k)
    if (not math.isfinite(temperature_k)
            or not REFERENCE_TEMPERATURE_K <= temperature_k <= MAXIMUM_TEMPERATURE_K):
        raise ValueError("SS304 screening properties outside 273.15..1473.15 K")

    density, cp, conductivity, enthalpy = ss304_support_thermal_fields(np.asarray(temperature_k))
    return {
        "materialId": "ss304",
        "materialRevisionSha256": ss304_support_thermal_snapshot()["materialRevisionSha256"],
        "validationStatus": "unvalidated-literature-model-screening",
        "temperature_K": temperature_k,
        "density_kg_m3": float(density),
        "specificHeat_J_kgK": float(cp),
        "thermalConductivity_W_mK": float(conductivity),
        "specificEnthalpy_J_kg": float(enthalpy),
    }


def ss304_support_thermal_fields(temperature_k):
    """Vectorized bounded ``(rho, cp, k, h)`` arrays for solver fields."""
    raw = np.asarray(temperature_k)
    if raw.dtype.kind not in "iuf" or raw.dtype.kind == "b":
        raise ValueError("SS304 screening temperatures must be numeric Kelvin values")
    temperature = np.asarray(raw, dtype=np.float64)
    if (not np.isfinite(temperature).all()
            or np.any(temperature < REFERENCE_TEMPERATURE_K)
            or np.any(temperature > MAXIMUM_TEMPERATURE_K)):
        raise ValueError("SS304 screening properties outside 273.15..1473.15 K")

    cp = CP_A_J_KGK + CP_B_J_KGK2 * temperature + CP_C_J_KGK * np.log(temperature)
    conductivity = K_A_W_MK + K_B_W_MK2 * temperature + K_C_W_MK3 * temperature**2
    t0 = REFERENCE_TEMPERATURE_K
    enthalpy = (
        CP_A_J_KGK * (temperature - t0)
        + 0.5 * CP_B_J_KGK2 * (temperature**2 - t0**2)
        + CP_C_J_KGK * ((temperature * np.log(temperature) - temperature)
                        - (t0 * math.log(t0) - t0))
    )
    if (not np.isfinite(cp).all() or np.any(cp <= 0)
            or not np.isfinite(conductivity).all() or np.any(conductivity <= 0)):
        raise ValueError("SS304 literature fit produced nonphysical thermal properties")
    density = np.full_like(temperature, DENSITY_KG_M3)
    return density, cp, conductivity, enthalpy
