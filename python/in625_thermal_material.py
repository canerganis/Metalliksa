"""Source-bounded IN625 solid table and fusion-enthalpy screening model.

Special Metals, INCONEL alloy 625 (2013), Tables 2 and 3, page 2:
https://www.specialmetals.com/documents/technical-bulletins/inconel/inconel-alloy-625.pdf

Table 2 specific heat values are labelled calculated; Table 3 conductivity
values were measured on material annealed at 2100 F for one hour. Their common
tabulated solid interval is -18..982 C. No liquid or powder surrogate is made.
"""

from bisect import bisect_left
import hashlib
import json
import math


SOURCE_URL = (
    "https://www.specialmetals.com/documents/technical-bulletins/inconel/"
    "inconel-alloy-625.pdf"
)
SOLID_TEMPERATURE_RANGE_C = (-18.0, 982.0)

# Celsius, J/(kg K): Special Metals Table 2.
_SPECIFIC_HEAT = (
    (-18.0, 402.0), (21.0, 410.0), (93.0, 427.0),
    (204.0, 456.0), (316.0, 481.0), (427.0, 511.0),
    (538.0, 536.0), (649.0, 565.0), (760.0, 590.0),
    (871.0, 620.0), (982.0, 645.0),
)

# Celsius, W/(m K): Special Metals Table 3.
_CONDUCTIVITY = (
    (-18.0, 9.2), (21.0, 9.8), (38.0, 10.1),
    (93.0, 10.8), (204.0, 12.5), (316.0, 14.1),
    (427.0, 15.7), (538.0, 17.5), (649.0, 19.0),
    (760.0, 20.8), (871.0, 22.8), (982.0, 25.2),
)


def _interpolate(table, temperature_c):
    temperatures = [row[0] for row in table]
    index = bisect_left(temperatures, temperature_c)
    if index < len(table) and temperatures[index] == temperature_c:
        return table[index][1]
    low_t, low_value = table[index - 1]
    high_t, high_value = table[index]
    return low_value + (temperature_c - low_t) * (high_value - low_value) / (high_t - low_t)


def in625_solid_thermal_at_celsius(temperature_c):
    """Interpolate tabulated solid k and Cp; refuse extrapolation and phase use."""
    if isinstance(temperature_c, bool) or not isinstance(temperature_c, (int, float)):
        raise ValueError("IN625 temperature must be a finite Celsius number")
    temperature_c = float(temperature_c)
    if not math.isfinite(temperature_c):
        raise ValueError("IN625 temperature must be finite")
    low, high = SOLID_TEMPERATURE_RANGE_C
    if not low <= temperature_c <= high:
        raise ValueError(f"IN625 solid thermal table unavailable outside {low:g}..{high:g} C")
    return {
        "thermal_conductivity_W_mK": _interpolate(_CONDUCTIVITY, temperature_c),
        "specific_heat_J_kgK": _interpolate(_SPECIFIC_HEAT, temperature_c),
    }


# Sabau et al., Metallurgical and Materials Transactions B 51 (2020),
# Appendix B and "Setup of STLF Simulation Model and Material Properties".
# JMatPro-calculated solid fits are a constitutive model, not measured IN625
# curves. Only the source's solid/mushy interval is used; no high-T extension.
SABAU_URL = "https://doi.org/10.1007/s11663-020-01808-w"
REFERENCE_TEMPERATURE_K = 273.15
SOLIDUS_K = 1290.0 + 273.15
LIQUIDUS_K = 1350.0 + 273.15
LATENT_HEAT_J_KG = 290_000.0
LIQUID_CP_J_KGK = 700.0
LIQUID_K_W_MK = 30.0
_CP_COEFFICIENTS = (362.0, 0.125, 0.0001741, -7.527126e-8)
_K_COEFFICIENTS = (4.93, 0.01575)


def _solid_cp(temperature_k):
    a, b, c, d = _CP_COEFFICIENTS
    return a + b*temperature_k + c*temperature_k**2 + d*temperature_k**3


def _solid_k(temperature_k):
    a, b = _K_COEFFICIENTS
    return a + b*temperature_k


def _solid_cp_primitive(temperature_k):
    a, b, c, d = _CP_COEFFICIENTS
    return (a*temperature_k + b*temperature_k**2/2
            + c*temperature_k**3/3 + d*temperature_k**4/4)


def in625_lpbf_thermal_snapshot():
    """Versioned, mass-basis IN625 fusion-enthalpy screening evidence."""
    snapshot = {
        "schemaVersion": 1,
        "materialId": "in625",
        "name": "Inconel 625",
        "capability": "bounded-fusion-enthalpy-screening",
        "validationStatus": "unvalidated-literature-model-screening",
        "provenanceClass": "literature-constitutive-model",
        "source": SABAU_URL,
        "sourceLocators": {
            "solidCpAndConductivity": "Appendix B, JMatPro-calculated equations",
            "liquidCpAndConductivity": "Appendix B, liquid-phase constants",
            "phaseAndLatent": "Setup of STLF Simulation Model and Material Properties",
        },
        "temperatureCoverage_K": [REFERENCE_TEMPERATURE_K, LIQUIDUS_K],
        "solidus_K": SOLIDUS_K,
        "liquidus_K": LIQUIDUS_K,
        "latentHeat_J_kg": LATENT_HEAT_J_KG,
        "solidCpPolynomial_J_kgK": list(_CP_COEFFICIENTS),
        "solidConductivityLinear_W_mK": list(_K_COEFFICIENTS),
        "liquidCp_J_kgK": LIQUID_CP_J_KGK,
        "liquidConductivity_W_mK": LIQUID_K_W_MK,
        "phaseInterpolation": "linear solid-to-liquid fraction over 1290..1350 C",
        "uncertaintyNote": (
            "JMatPro/model-based inputs; no quantified property uncertainty or "
            "independent validation. Mushy heat capacity and conductivity are "
            "explicit linear screening interpolations. No powder, vapor, "
            "optical, volumetric-density or above-liquidus prediction."
        ),
    }
    payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("utf-8")
    snapshot["materialRevisionSha256"] = hashlib.sha256(payload).hexdigest()
    return snapshot


def validate_in625_screening_admission(snapshot=None):
    """Admit only the pinned IN625 evidence for bounded enthalpy screening.

    This checks identity, cited source locators, model inputs, scope, and the
    content digest. It does not validate the constitutive model experimentally
    or admit a full transient property table.
    """
    candidate = in625_lpbf_thermal_snapshot() if snapshot is None else snapshot
    if not isinstance(candidate, dict):
        raise ValueError("IN625 screening evidence must be an object")

    expected = in625_lpbf_thermal_snapshot()
    supplied = dict(candidate)
    revision = supplied.pop("materialRevisionSha256", None)
    payload = json.dumps(supplied, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("utf-8")
    computed_revision = hashlib.sha256(payload).hexdigest()
    if revision != computed_revision:
        raise ValueError("IN625 screening evidence content digest mismatch")
    if candidate != expected:
        raise ValueError("IN625 screening evidence does not match the pinned source scope")

    return {
        "accepted": True,
        "scope": "bounded-fusion-enthalpy-screening",
        "materialId": "in625",
        "materialRevisionSha256": revision,
        "source": SABAU_URL,
        "sourceLocators": dict(expected["sourceLocators"]),
        "modelTemperatureCoverage_K": list(expected["temperatureCoverage_K"]),
        "sourceValidityRange_K": None,
        "validationStatus": expected["validationStatus"],
        "fullTransientAdmitted": False,
        "experimentalValidation": False,
    }


def in625_lpbf_thermal_at_kelvin(temperature_k):
    """Return bounded Cp, k, liquid fraction and specific enthalpy from 273.15 K."""
    if isinstance(temperature_k, bool) or not isinstance(temperature_k, (int, float)):
        raise ValueError("IN625 screening temperature must be a finite Kelvin number")
    temperature_k = float(temperature_k)
    if not math.isfinite(temperature_k) or not REFERENCE_TEMPERATURE_K <= temperature_k <= LIQUIDUS_K:
        raise ValueError("IN625 fusion-enthalpy screening outside 273.15..1623.15 K")
    if temperature_k <= SOLIDUS_K:
        cp = _solid_cp(temperature_k)
        conductivity = _solid_k(temperature_k)
        enthalpy = _solid_cp_primitive(temperature_k) - _solid_cp_primitive(REFERENCE_TEMPERATURE_K)
        fraction = 0.0
        effective_cp = cp
    else:
        width = LIQUIDUS_K - SOLIDUS_K
        delta = temperature_k - SOLIDUS_K
        fraction = delta / width
        cp_s = _solid_cp(SOLIDUS_K)
        cp = cp_s + (LIQUID_CP_J_KGK - cp_s)*fraction
        conductivity = _solid_k(SOLIDUS_K) + (LIQUID_K_W_MK - _solid_k(SOLIDUS_K))*fraction
        enthalpy = (_solid_cp_primitive(SOLIDUS_K) - _solid_cp_primitive(REFERENCE_TEMPERATURE_K)
                    + cp_s*delta + (LIQUID_CP_J_KGK - cp_s)*delta**2/(2*width)
                    + LATENT_HEAT_J_KG*fraction)
        effective_cp = cp + LATENT_HEAT_J_KG/width
    return {
        "materialId": "in625",
        "materialRevisionSha256": in625_lpbf_thermal_snapshot()["materialRevisionSha256"],
        "validationStatus": "unvalidated-literature-model-screening",
        "temperature_K": temperature_k,
        "specificHeat_J_kgK": cp,
        "effectiveHeatCapacity_J_kgK": effective_cp,
        "thermalConductivity_W_mK": conductivity,
        "liquidFraction": fraction,
        "specificEnthalpy_J_kg": enthalpy,
    }
