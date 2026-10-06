#!/usr/bin/env python3
"""
MetalliX ASTM G102 / G59 High-Precision Tafel Annual Corrosion Rate Solver
CPython 3.10+ Scientific Engine for Electrochemical Degradation & Faraday Penetration

Formulas & Standards:
- ASTM G102: Standard Practice for Calculation of Corrosion Rates and Related Information from Electrochemical Measurements
- ASTM G59: Standard Test Method for Conducting Potentiodynamic Polarization Resistance Measurements
- Severity bands: Fontana, Corrosion Engineering (3rd ed.), relative corrosion resistance scale in its
  mm/y equivalents. NACE SP0169 (cathodic protection of buried piping) and ISO 8044 (vocabulary) define
  no rate bands and are not cited. The description / recommendation texts are in-house guidance.
"""

import sys
import json
import math
import time

import alloy_registry
import physical_constants
from input_validation import (BAD_UNIT, NON_FINITE, NON_POSITIVE, OUT_OF_RANGE, UNKNOWN_ALLOY, UNKNOWN_ELEMENT, require_unit,
                              ValidationError, require_known_alloy, validation_envelope)

# Physical & Electrochemical Constants
# Phase 6a value step (b): R and F are the exact SI 2019 products N_A*k and N_A*e
# from physical_constants (they replaced the CODATA printed truncations
# 8.314462618 / 96485.33212; relative change 1.8e-11 / 3.4e-11).
FARADAY_C_PER_MOL = physical_constants.FARADAY.value  # C / mol, exact
SECONDS_PER_YEAR = 31557600.0     # 365.25 days * 86400 s/day
R_GAS = physical_constants.GAS_CONSTANT_R.value  # J / (mol * K), exact
ZERO_CELSIUS_K = physical_constants.ZERO_CELSIUS_K.value  # 273.15 K

# Alloy data (density, EW, composition, valencies, Ea, E0) lives in
# alloy_registry (domain "corrosion"); atomic weights come from
# physical_constants.STANDARD_ATOMIC_WEIGHTS. Only the display labels this solver
# has always reported stay here, keyed by registry id.
# Stern-Geary B = beta_a * beta_c / (ln(10) * (beta_a + beta_c)): the exact natural log of 10, not the
# printed 2.302585 / 2.303.
LN10 = math.log(10.0)
# 1 mil = 0.001 in = 0.0254 mm exactly, so mpy = mm/yr * 1000 / 25.4 (was 39.37 / 39.3701 / 39.37007874).
MILS_PER_MM = 1000.0 / 25.4
# Rounding of the reported values is by decimals, kept from the Phase 6a goldens: corrosionRateMmYr 5,
# corrosionRateMpy 3, corrosionRateUmYr 2, corrosionRateNmHr 3 (fit result and temperature table: mm/yr 4,
# mpy 2). Rates below ~1e-3 mm/yr therefore carry few significant digits (9e-5 mm/yr prints one);
# the unrounded value is not exposed. This is a display precision, not an accuracy claim.
_CORROSION_DISPLAY_NAME = {
    "ss316l": "AISI 316L Stainless Steel",
    "ss304": "AISI 304 Stainless Steel",
    "steel1018": "Carbon Steel (AISI 1018)",
    "ti6al4v": "Titanium Ti-6Al-4V (Grade 5)",
    "al7075": "Aerospace Aluminum 7075-T6",
    "al6061": "Structural Aluminum 6061-T6",
    "cu_c110": "Pure Copper (ETP C11000)",
    "in718": "Nickel Superalloy Inconel 718",
    "az31b": "Magnesium Alloy AZ31B",
}


# The registry record "ti6al4v" also carries the LPBF ELI / Grade 23 names, but the
# only titanium corrosion preset here is Ti-6Al-4V Grade 5. Only these names (as
# normalised by alloy_registry.normalise_name) may consume that preset; every other
# name that resolves to "ti6al4v" (e.g. "Ti-6Al-4V ELI", "... Grade 23") is refused.
_TI_GRADE5_PRESET_NAMES = frozenset({
    "ti-6al-4v", "ti6al4v", "ti64", "titanium ti-6al-4v (grade 5)", "ti-6al-4v grade 5",
    "ti-6al-4v grade 5 titanium", "ti-6al-4v grade 5 (ams 4928)", "ti-6al-4v grade 5 (aero am)",
    "ti-6al-4v (grade 5 alpha-beta)", "ti64-ams4928",
})


def corrosion_preset(alloy_id: str) -> dict:
    """Registry-backed alloy preset. Raises ValidationError(UNKNOWN_ALLOY) instead of
    silently substituting AISI 316L for an unknown id."""
    record = require_known_alloy(alloy_id, alloy_registry.DOMAIN_CORROSION, field="alloyId")
    if record.id == "ti6al4v" and alloy_registry.normalise_name(alloy_id) not in _TI_GRADE5_PRESET_NAMES:
        raise ValidationError(
            UNKNOWN_ALLOY, "alloyId",
            f"Alloy {alloy_id!r} is a titanium variant without a corrosion preset; the only "
            "titanium preset is Ti-6Al-4V Grade 5 ('ti-6al-4v'). Send that id, or supply "
            "alloyName, density_g_cm3, equivalentWeight and activationEnergyJ_mol.",
            {"name": repr(alloy_id), "domain": alloy_registry.DOMAIN_CORROSION,
             "reason": "variant-without-preset", "presetAlloy": "ti-6al-4v"},
        )
    table = record.domains[alloy_registry.DOMAIN_CORROSION]
    composition = dict(table["composition"].value)
    return {
        "registry_id": record.id,
        "name": _CORROSION_DISPLAY_NAME[record.id],
        "density_g_cm3": table["density_g_cm3"].value,
        "ew": table["ew"].value,
        "composition": composition,
        "valencies": dict(table["valencies"].value),
        "atomic_weights": {el: physical_constants.atomic_weight(el) for el in composition},
        "activation_energy_j_mol": table["activation_energy_j_mol"].value,
        "standard_e0_v": table["standard_e0_v"].value,
    }


class _LazyPreset:
    """Resolves the alloy only when a preset value is actually consumed.

    The solver reads preset values only for fields the caller did not supply, so an
    unknown alloyId is an error exactly where the old code would have silently used
    the AISI 316L preset, and nowhere else.
    """

    def __init__(self, alloy_id: str):
        self.alloy_id = alloy_id
        self._preset = None

    def _resolve(self) -> dict:
        if self._preset is None:
            self._preset = corrosion_preset(self.alloy_id)
        return self._preset

    def __getitem__(self, key):
        return self._resolve()[key]

    def get(self, key, default=None):
        return self._resolve().get(key, default)

    @property
    def registry_id(self):
        return None if self._preset is None else self._preset["registry_id"]


def _provenance(preset) -> dict:
    return {
        "registryVersion": alloy_registry.REGISTRY_VERSION,
        "constantsVersion": physical_constants.CONSTANTS_VERSION,
        "registryAlloyId": None if preset is None else preset.registry_id,
        "gasConstantR_J_molK": R_GAS,
        "faraday_C_mol": FARADAY_C_PER_MOL,
        "constantsNote": "Exact SI 2019 R = N_A*k and F = N_A*e (Phase 6a value step); "
                         "they replaced the CODATA printed truncations 8.314462618 / 96485.33212.",
    }

def calculate_equivalent_weight(composition: dict, valencies: dict, atomic_weights: dict) -> float:
    """
    Computes ASTM G102 Equivalent Weight (EW):
    EW = ( sum_i [ (f_i * n_i) / W_i ] )^(-1)
    where:
    f_i = mass fraction of element i, counting only elements present at >= 1 % by
          mass, renormalised over those elements (ASTM G102 practice)
    n_i = valence (oxidation state)
    W_i = atomic weight in g/mol

    Phase 6a design step (b): the formula lives in alloy_registry.astm_g102_equivalent_weight,
    which also computes every preset "ew", so a preset alloyId and the same composition sent
    as customComposition give the same EW. A counted element (>= 1 % by mass) without a
    valence or an atomic weight, or a composition with no counted element, raises
    ValidationError(UNKNOWN_ELEMENT); the former silent 27.0 g/equivalent fallback is gone.
    """
    counted = alloy_registry.astm_g102_counted_elements(composition)
    missing = [el for el in counted if el not in valencies or el not in atomic_weights]
    if missing or not counted:
        field = f"customComposition.{missing[0]}" if missing else "customComposition"
        raise ValidationError(
            UNKNOWN_ELEMENT, field,
            ("customComposition element(s) " + ", ".join(repr(el) for el in missing) +
             " (>= 1 % by mass) have no valence or atomic weight; send customValencies and "
             "customAtomicWeights for them." if missing else
             "customComposition has no element with a positive amount; the equivalent weight "
             "cannot be computed."),
            {"missing": missing, "counted": counted, "reason": "no-equivalent-weight-data"},
        )
    ew = alloy_registry.astm_g102_equivalent_weight(composition, valencies, atomic_weights)
    if ew is None:  # unreachable after the checks above; kept explicit, never a default
        raise ValidationError(UNKNOWN_ELEMENT, "customComposition", "equivalent weight not computable",
                              {"reason": "no-equivalent-weight-data"})
    return ew

# Standards that define what this solver computes (EUQ-6: NACE SP0169 and ISO 8044 removed; they
# define no corrosion-rate bands).
STANDARDS = ["ASTM G102-89(2015)", "ASTM G59-97(2020)"]

SEVERITY_SCALE_SOURCE = (
    "Fontana, Corrosion Engineering, 3rd ed., relative corrosion resistance scale (mm/y equivalents): "
    "Outstanding < 0.02, Excellent 0.02-0.1, Good 0.1-0.5, Fair 0.5-1, Poor 1-5, Unacceptable > 5 mm/y"
)
SEVERITY_TEXT_BASIS = (
    "In-house engineering guidance: the description and recommendation texts are not taken from Fontana or "
    "from any standard"
)


def classify_corrosion_severity(cr_mm_yr: float) -> dict:
    """
    Categorizes a uniform corrosion rate on Fontana's relative corrosion resistance scale
    (Corrosion Engineering, 3rd ed.; mm/y equivalents of < 1, 1-5, 5-20, 20-50, 50-200, > 200 mpy).

    EUQ-6: the former docstring cited NACE SP0169 (cathodic protection of buried piping) and ISO 8044
    (vocabulary); neither defines rate bands. Fontana's Poor band (1-5 mm/y) was merged into
    'Unacceptable / Critical' (>= 1 mm/y); it is restored, and Unacceptable starts at 5 mm/y.
    The description / recommendation texts are in-house guidance (SEVERITY_TEXT_BASIS).
    """
    band = _severity_band(cr_mm_yr)
    band["scaleSource"] = SEVERITY_SCALE_SOURCE
    band["textBasis"] = SEVERITY_TEXT_BASIS
    return band


def _severity_band(cr_mm_yr: float) -> dict:
    if cr_mm_yr < 0.02:
        return {
            "level": "Outstanding",
            "code": "OUTSTANDING",
            "color": "emerald",
            "description": "Negligible corrosion degradation. Suitable for long-life aerospace, biomedical, and precision critical parts without corrosion allowance.",
            "recommendation": "Standard surface passivating inspection; corrosion allowance can be 0.00 mm."
        }
    elif cr_mm_yr < 0.10:
        return {
            "level": "Excellent",
            "code": "EXCELLENT",
            "color": "sky",
            "description": "Very low corrosion rate. Highly reliable for marine subsea hulls, offshore piping, and structural load-bearing airframes.",
            "recommendation": "Periodic 5-year ultrasonic wall gauge inspection; minimal sacrificial allowance."
        }
    elif cr_mm_yr < 0.50:
        return {
            "level": "Good",
            "code": "GOOD",
            "color": "amber",
            "description": "Moderate corrosion rate. Standard structural steel in non-aggressive industrial atmospheres or mild water.",
            "recommendation": "Apply protective epoxy/polyurethane coating or zinc galvanizing. Corrosion allowance 1.5 - 3.0 mm recommended."
        }
    elif cr_mm_yr < 1.00:
        return {
            "level": "Fair",
            "code": "FAIR",
            "color": "orange",
            "description": "Noticeable corrosion penetration. Significant wall thinning occurs within 2 to 5 years if unprotected.",
            "recommendation": "Active cathodic protection (ICCP/sacrificial zinc) and chemical corrosion inhibitor injection mandated."
        }
    elif cr_mm_yr < 5.00:
        return {
            "level": "Poor",
            "code": "POOR",
            "color": "red",
            "description": "High corrosion rate. Usable only for short-life or readily replaced parts with a large corrosion allowance.",
            "recommendation": "Change the material or the environment, or apply corrosion protection, before service; confirm the rate by immersion or field testing."
        }
    else:
        return {
            "level": "Unacceptable",
            "code": "UNACCEPTABLE",
            "color": "rose",
            "description": "Severe catastrophic dissolution. Wall breach and structural failure imminent without immediate mitigation.",
            "recommendation": "Material change required (upgrade to Inconel/316L/Titanium) or continuous heavy-duty barrier protection."
        }

def _present(data: dict, *keys):
    """First value among ``keys`` that is not None (a supplied 0 is kept, not defaulted)."""
    for key in keys:
        value = data.get(key)
        if value is not None:
            return value
    return None


def _scenario_number(data: dict, keys: tuple, default: float, label: str, rule: str) -> float:
    """A scenario input (area, thickness, allowance, temperature): the first supplied key, else ``default``.

    Replaces the former falsy-``or`` chains, which turned a supplied 0 (e.g. temperatureC = 0 C, the
    Arrhenius reference) into the default. A supplied value must be a finite number and satisfy ``rule``:
    "positive" (> 0), "nonzero" (!= 0; the area keeps its documented abs() handling) or
    "above_absolute_zero" (> -273.15 C). Anything else is a ValidationError, never a silent default.
    """
    raw = _present(data, *keys)
    if raw is None:
        return default
    field = next(key for key in keys if data.get(key) is not None)
    try:
        if isinstance(raw, bool):
            raise TypeError
        value = float(raw)
    except (TypeError, ValueError):
        raise ValidationError(NON_FINITE, field, f"{label} must be a number", {"value": repr(raw)})
    if not math.isfinite(value):
        raise ValidationError(NON_FINITE, field, f"{label} must be finite", {"value": repr(raw)})
    if rule == "positive" and value <= 0.0:
        raise ValidationError(NON_POSITIVE, field, f"{label} must be > 0", {"value": value, "allowZero": False})
    if rule == "nonzero" and value == 0.0:
        raise ValidationError(NON_POSITIVE, field, f"{label} must not be 0", {"value": value, "allowZero": False})
    if rule == "above_absolute_zero" and value <= -ZERO_CELSIUS_K:
        raise ValidationError(OUT_OF_RANGE, field, f"{label} must be above absolute zero (-273.15 C)",
                              {"value": value, "lo": -ZERO_CELSIUS_K, "hi": None, "unit": "C"})
    return value


def _supplied_positive(raw, label: str):
    """(value, None) for a supplied finite number > 0, else (None, reason).

    Replaces the former falsy-``or`` defaults (i_corr 1.25 uA/cm2, betaA 0.120, betaC 0.100):
    a measurement that was not supplied is unavailable, never invented.
    """
    if raw is None:
        return None, f"{label} was not supplied"
    if isinstance(raw, bool):
        return None, f"{label} must be a number, not a boolean"
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None, f"{label} must be a number (received {raw!r})"
    if not math.isfinite(value) or value <= 0.0:
        return None, f"{label} must be a finite number > 0 (received {raw!r})"
    return value, None


def _substrate_value(raw, label: str, preset, preset_key: str):
    """(value, None) or (None, reason) for a substrate property (density, EW, activation energy).

    A supplied value must be a finite number > 0 (no falsy-``or`` fallback to the preset); an absent
    one comes from the registry preset of the alloyId the caller sent; with neither it is unavailable.
    There is no default alloy: a request without alloyId and without the value is not guessed as 316L.
    """
    if raw is not None:
        return _supplied_positive(raw, label)
    if preset is None:
        return None, f"{label} was not supplied and no alloyId was sent"
    return preset[preset_key], None


def _resolve_substrate(data: dict, alloy_id, need_activation_energy: bool = False):
    """Resolve the substrate of a request: (preset or None, substrate dict, reasons dict).

    Never substitutes an alloy: ``alloy_id`` is None when the caller sent none. The equivalent weight
    comes from customComposition (valences from customValencies, or from the sent alloyId's preset;
    atomic weights from customAtomicWeights, the preset, or the CIAAW table), else equivalentWeight,
    else the preset. A request that gives neither alloy nor the values gets reasons, not numbers.
    """
    preset = _LazyPreset(alloy_id) if alloy_id else None
    reasons = {}
    alloy_name = data.get("alloyName") or (preset["name"] if preset is not None else None)
    density, density_reason = _substrate_value(data.get("density_g_cm3"), "density_g_cm3", preset, "density_g_cm3")
    ew, ew_reason = None, None
    custom_comp = data.get("customComposition")
    if custom_comp and isinstance(custom_comp, dict):
        valencies = data.get("customValencies") or (preset.get("valencies", {}) if preset is not None else {})
        if data.get("customAtomicWeights"):
            atomic_weights = data["customAtomicWeights"]
        elif preset is not None:
            atomic_weights = preset.get("atomic_weights", {})
        else:
            atomic_weights = {el: physical_constants.atomic_weight(el) for el in custom_comp
                              if physical_constants.is_known_element(el)}
        derived_ew = calculate_equivalent_weight(custom_comp, valencies, atomic_weights)
        if derived_ew > 0:
            ew = derived_ew
        else:
            ew_reason = "equivalentWeight derived from customComposition is not > 0"
    else:
        ew, ew_reason = _substrate_value(data.get("equivalentWeight"), "equivalentWeight", preset, "ew")
    ea, ea_reason = (None, None)
    if need_activation_energy:
        ea, ea_reason = _substrate_value(data.get("activationEnergyJ_mol"), "activationEnergyJ_mol", preset,
                                         "activation_energy_j_mol")
    problems = [r for r in (density_reason, ew_reason) if r]
    if problems:
        reasons["substrate"] = "; ".join(problems)
    if ea_reason:
        reasons["activationEnergyJ_mol"] = ea_reason
    return preset, {"alloy_name": alloy_name, "density": density, "ew": ew, "ea": ea}, reasons


UNAVAILABLE_STATUS = "unavailable"
PARTIAL_STATUS = "partial"
UNAVAILABLE_NOTE = (
    "Values reported as null are unavailable: they were not supplied or could not be fitted from "
    "the data, and no default or fallback value was substituted."
)


def solve_tafel_corrosion_rate(data: dict) -> dict:
    """
    Core solver calculating annual corrosion rate from Tafel Icorr and substrate parameters.

    The corrosion current density iCorr_uA_cm2 is a required measurement: when it is missing or
    not a finite number > 0 the result has status "unavailable" with the reason (the former
    silent 1.25 uA/cm2 default is gone). Missing or invalid betaA/betaC make only the
    Stern-Geary B and Rp unavailable (status "partial"); the Faraday rate does not need them.
    The scenario inputs (area, thickness, allowable loss, temperature) keep their documented
    defaults; they are projection settings, not measurements.
    """
    start_time = time.perf_counter()

    # 1. Parse Input Parameters
    i_corr_ua_cm2, i_corr_reason = _supplied_positive(
        _present(data, "iCorr_uA_cm2", "icorr", "i_corr"), "iCorr_uA_cm2")
    e_corr_raw = _present(data, "eCorr_V", "ecorr", "e_corr")
    e_corr_v = None if e_corr_raw is None else float(e_corr_raw)
    beta_a, beta_a_reason = _supplied_positive(_present(data, "betaA", "beta_a"), "betaA")  # V/decade
    beta_c, beta_c_reason = _supplied_positive(_present(data, "betaC", "beta_c"), "betaC")  # V/decade
    # Scenario inputs: a supplied value is used as given (a supplied 0 is not replaced by the default,
    # EUQ-5); only an absent key takes the documented default.
    specimen_area_cm2 = _scenario_number(data, ("specimenAreaCm2", "area"), 1.0, "specimenAreaCm2", "nonzero")
    initial_thickness_mm = _scenario_number(data, ("initialThicknessMm", "thicknessMm"), 5.0,
                                            "initialThicknessMm", "positive")
    allowable_loss_mm = _scenario_number(data, ("allowableLossMm", "corrosionAllowanceMm"), 1.5,
                                         "allowableLossMm", "positive")
    # The measurement temperature is the Arrhenius reference T_ref of temperatureSensitivity.
    temp_c = _scenario_number(data, ("temperatureC", "tempC"), 25.0, "temperatureC", "above_absolute_zero")

    # 2. Material Substrate: the alloyId the caller sent (never a default alloy), or the supplied
    # density / equivalentWeight / customComposition; otherwise unavailable with the reason.
    alloy_id_raw = data.get("alloyId") or data.get("materialId")
    alloy_id = str(alloy_id_raw).lower() if alloy_id_raw else None
    preset, substrate, substrate_reasons = _resolve_substrate(data, alloy_id, need_activation_energy=True)
    alloy_name = substrate["alloy_name"]
    density = substrate["density"]
    ew = substrate["ew"]
    ea_j_mol = substrate["ea"]
    activation_reason = substrate_reasons.pop("activationEnergyJ_mol", None)

    # Ensure physical positive bounds
    if density is not None:
        density = max(0.1, abs(density))
    if ew is not None:
        ew = max(1.0, abs(ew))
    specimen_area_cm2 = max(1e-4, abs(specimen_area_cm2))

    unavailable = {}
    if i_corr_reason:
        unavailable["iCorr_uA_cm2"] = i_corr_reason
    if beta_a_reason:
        unavailable["betaA"] = beta_a_reason
    if beta_c_reason:
        unavailable["betaC"] = beta_c_reason

    # Stern-Geary (ASTM G59) needs both Tafel slopes and i_corr; it does not need the substrate
    stern_ok = beta_a is not None and beta_c is not None
    stern_geary_b = rp_ohm_cm2 = rp_apparent_ohm = None
    if i_corr_ua_cm2 is not None:
        i_corr_ua_cm2 = max(1e-9, i_corr_ua_cm2)
        if stern_ok:
            beta_a = max(0.005, beta_a)
            beta_c = max(0.005, beta_c)
            # B = (beta_a * beta_c) / [ln(10) * (beta_a + beta_c)]; R_p = B / i_corr, i_corr in A/cm2
            stern_geary_b = (beta_a * beta_c) / (LN10 * (beta_a + beta_c))
            rp_ohm_cm2 = stern_geary_b / (i_corr_ua_cm2 * 1e-6)
            rp_apparent_ohm = rp_ohm_cm2 / specimen_area_cm2

    if i_corr_ua_cm2 is None or substrate_reasons:
        # No corrosion current density or no substrate: the Faraday rate cannot be computed.
        # Report it, never invent it.
        unavailable.update(substrate_reasons)
        reason_text = "; ".join(unavailable[k] for k in ("iCorr_uA_cm2", "substrate") if k in unavailable)
        duration_ms = round((time.perf_counter() - start_time) * 1000.0, 3)
        return {
            "success": True,
            "isPythonEngine": True,
            "pythonVersion": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "standards": list(STANDARDS),
            "durationMs": duration_ms,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),

            "status": UNAVAILABLE_STATUS,
            "unavailableReason": (f"Corrosion rate unavailable: {reason_text}. Supply a measured or fitted "
                                  "corrosion current density and the substrate (alloyId, or density_g_cm3 with "
                                  "equivalentWeight / customComposition); no default value is used."),
            "unavailable": unavailable,
            "unavailableNote": UNAVAILABLE_NOTE,

            "corrosionRateMmYr": None,
            "corrosionRateMpy": None,
            "corrosionRateUmYr": None,
            "corrosionRateNmHr": None,
            "massLoss_g_m2_day": None,
            "massLoss_mdd": None,
            "massLoss_kg_m2_yr": None,

            "sternGearyB_V": None if stern_geary_b is None else round(stern_geary_b, 5),
            "rp_ohm_cm2": None if rp_ohm_cm2 is None else round(rp_ohm_cm2, 1),
            "rp_apparent_ohm": None if rp_apparent_ohm is None else round(rp_apparent_ohm, 2),

            "alloyId": alloy_id,
            "alloyName": alloy_name,
            "density_g_cm3": density,
            "equivalentWeight": ew,
            "iCorr_uA_cm2": i_corr_ua_cm2,
            "eCorr_V": e_corr_v,
            "betaA": beta_a,
            "betaC": beta_c,
            "specimenAreaCm2": specimen_area_cm2,
            "temperatureC": temp_c,
            "initialThicknessMm": initial_thickness_mm,
            "allowableLossMm": allowable_loss_mm,

            "rulUniformYears": None,
            "severity": None,
            "timelineProjections": [],
            "temperatureSensitivity": [],
            "provenance": _provenance(preset),
        }

    # 3. Stern-Geary Kinetics: computed above (needs both Tafel slopes and i_corr)

    # 4. Faraday's Law Corrosion Rates (ASTM G102)
    # CR (mm/year) = [K1 * i_corr (uA/cm2) * EW] / density (g/cm3)
    # K1 = (1e-6 * 31557600 * 10) / F = 0.0032707148 mm*g/(uA*cm*year) with the exact F
    exact_k1 = (1e-6 * SECONDS_PER_YEAR * 10.0) / FARADAY_C_PER_MOL
    cr_mm_yr = (exact_k1 * i_corr_ua_cm2 * ew) / density
    cr_mpy = cr_mm_yr * MILS_PER_MM  # mils per year
    cr_um_yr = cr_mm_yr * 1000.0     # micrometers per year
    cr_nm_hr = (cr_mm_yr * 1e6) / (365.25 * 24.0)

    # Mass Loss Rate (MR in g / (m^2 * day))
    # ASTM G102 equation: MR = 8.954e-3 * i_corr * EW
    exact_k2 = (1e-6 * 86400.0 * 1e4) / FARADAY_C_PER_MOL  # = 8.95473e-3
    mass_loss_g_m2_day = exact_k2 * i_corr_ua_cm2 * ew
    mass_loss_mdd = mass_loss_g_m2_day * 10.0 # mg / (dm^2 * day)
    mass_loss_kg_m2_yr = mass_loss_g_m2_day * 0.36525

    # Total Corrosion Current (Microamps)
    total_icorr_ua = i_corr_ua_cm2 * specimen_area_cm2

    # 5. Service Life & Wall Thinning Projections (1 to 25 Years)
    years_timeline = [1, 2, 3, 5, 7, 10, 15, 20, 25]
    projections = []

    for yr in years_timeline:
        loss_uniform_mm = cr_mm_yr * yr
        remaining_wall_mm = max(0.0, initial_thickness_mm - loss_uniform_mm)
        wall_loss_pct = min(100.0, (loss_uniform_mm / initial_thickness_mm) * 100.0)
        
        is_breached = loss_uniform_mm >= allowable_loss_mm
        
        projections.append({
            "year": yr,
            "lossUniformMm": round(loss_uniform_mm, 4),
            "remainingWallMm": round(remaining_wall_mm, 3),
            "wallLossPct": round(wall_loss_pct, 2),
            "exceedsAllowance": is_breached
        })

    # Remaining Useful Life (RUL) in Years before exceeding corrosion allowance
    # A zero corrosion rate has no finite life: unavailable (None), not a 999-year placeholder.
    rul_uniform_years = (allowable_loss_mm / cr_mm_yr) if cr_mm_yr > 0 else None

    # 6. Temperature Sensitivity (Arrhenius Model from 5°C to 85°C)
    t_ref_k = temp_c + ZERO_CELSIUS_K
    temp_sensitivity = []
    for t_test_c in (range(5, 90, 10) if ea_j_mol is not None else ()):
        t_test_k = t_test_c + ZERO_CELSIUS_K
        # Arrhenius: i_corr(T) = i_corr_ref * exp( (-Ea / R) * (1/T - 1/T_ref) )
        exponent = (-ea_j_mol / R_GAS) * (1.0 / t_test_k - 1.0 / t_ref_k)
        # clamp exponent to avoid numerical overflow
        exponent = max(-10.0, min(10.0, exponent))
        factor = math.exp(exponent)
        i_test_ua = i_corr_ua_cm2 * factor
        cr_test_mm_yr = (exact_k1 * i_test_ua * ew) / density
        temp_sensitivity.append({
            "tempC": t_test_c,
            "tempK": t_test_k,
            "arrheniusFactor": round(factor, 3),
            "iCorr_uA_cm2": round(i_test_ua, 4),
            "corrosionRateMmYr": round(cr_test_mm_yr, 4),
            "corrosionRateMpy": round(cr_test_mm_yr * MILS_PER_MM, 2)
        })

    # 7. Severity Rating & Recommendations
    severity = classify_corrosion_severity(cr_mm_yr)

    duration_ms = round((time.perf_counter() - start_time) * 1000.0, 3)

    result = {
        "success": True,
        "isPythonEngine": True,
        "pythonVersion": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "standards": list(STANDARDS),
        "durationMs": duration_ms,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        
        # Core Output Parameters
        "corrosionRateMmYr": round(cr_mm_yr, 5),
        "corrosionRateMpy": round(cr_mpy, 3),
        "corrosionRateUmYr": round(cr_um_yr, 2),
        "corrosionRateNmHr": round(cr_nm_hr, 3),
        "massLoss_g_m2_day": round(mass_loss_g_m2_day, 4),
        "massLoss_mdd": round(mass_loss_mdd, 3),
        "massLoss_kg_m2_yr": round(mass_loss_kg_m2_yr, 4),
        
        # Stern-Geary Metrics
        "sternGearyB_V": None if stern_geary_b is None else round(stern_geary_b, 5),
        "rp_ohm_cm2": None if rp_ohm_cm2 is None else round(rp_ohm_cm2, 1),
        "rp_apparent_ohm": None if rp_apparent_ohm is None else round(rp_apparent_ohm, 2),
        
        # Substrate Metadata
        "alloyId": alloy_id,
        "alloyName": alloy_name,
        "density_g_cm3": density,
        "equivalentWeight": ew,
        "iCorr_uA_cm2": i_corr_ua_cm2,
        "eCorr_V": e_corr_v,
        "betaA": beta_a,
        "betaC": beta_c,
        "specimenAreaCm2": specimen_area_cm2,
        "temperatureC": temp_c,
        "initialThicknessMm": initial_thickness_mm,
        "allowableLossMm": allowable_loss_mm,
        
        # Remaining Useful Life (RUL)
        "rulUniformYears": None if rul_uniform_years is None else round(rul_uniform_years, 2),
        
        # Categorization & Engineering Decisions
        "severity": severity,
        
        # Time and Temperature Projections
        "timelineProjections": projections,
        "temperatureSensitivity": temp_sensitivity,
        
        # Phase 6a provenance (registry / constants versions)
        "provenance": _provenance(preset),
    }
    if activation_reason:
        unavailable["activationEnergyJ_mol"] = activation_reason
    if not stern_ok or activation_reason:
        parts = []
        if not stern_ok:
            parts.append("Stern-Geary B and polarization resistance unavailable: "
                         + "; ".join(unavailable[k] for k in ("betaA", "betaC") if k in unavailable) + ".")
        if activation_reason:
            parts.append("Temperature sensitivity unavailable: " + activation_reason + ".")
        result["status"] = PARTIAL_STATUS
        result["unavailableReason"] = " ".join(parts)
        result["unavailable"] = unavailable
        result["unavailableNote"] = UNAVAILABLE_NOTE
    return result

def linear_regression_py(x_arr, y_arr):
    n = len(x_arr)
    if n < 2:
        return {"m": 0.0, "b": y_arr[0] if y_arr else 0.0, "r2": 0.0}
    sum_x = sum(x_arr)
    sum_y = sum(y_arr)
    sum_xy = sum(x * y for x, y in zip(x_arr, y_arr))
    sum_xx = sum(x * x for x in x_arr)
    denom = n * sum_xx - sum_x * sum_x
    if abs(denom) < 1e-15:
        return {"m": 0.0, "b": sum_y / n, "r2": 0.0}
    m = (n * sum_xy - sum_x * sum_y) / denom
    b = (sum_y - m * sum_x) / n
    mean_y = sum_y / n
    ss_tot = sum((y - mean_y) ** 2 for y in y_arr)
    ss_res = sum((y - (m * x + b)) ** 2 for x, y in zip(x_arr, y_arr))
    r2 = max(0.0, 1.0 - ss_res / ss_tot) if ss_tot > 1e-15 else 1.0
    return {"m": m, "b": b, "r2": round(r2, 4)}

MIN_BRANCH_POINTS = 3

# Largest accepted distance (V) between the Evans intersection of the fitted branches and the measured
# current valley; farther away, the valley is used as E_corr (reported, never silent). EUQ-13: one value
# for both engines; src/utils/tafelParser.ts TAFEL_INTERSECTION_MAX_OFFSET_V must equal it (checked by
# tests/tafel-intersection-parity.test.ts and python/test_tafel_physics_audit.py). Python used 0.25 V and
# TypeScript 0.15 V, so data with the intersection 0.15-0.25 V from the valley got E_corr and i_corr
# differing by 10^(dE/beta_a) between the engines. 0.15 V is a heuristic, not a value from ASTM G102/G59:
# the default fit windows reach 0.22 V from the valley, and an intersection farther away than 0.15 V
# usually signals a poor branch fit.
INTERSECTION_MAX_OFFSET_V = 0.15

# Factor from the stated currentUnit to microamperes (EUQ-3).
CURRENT_UNIT_TO_UA = {"A": 1e6, "mA": 1e3, "uA": 1.0, "nA": 1e-3}


def _branch_unavailable_reason(branch: str, window, pts: list, fit: dict, expect_positive_slope: bool):
    """Reason string when a Tafel branch cannot be fitted from the data, else None.

    A branch is unavailable when its window holds fewer than MIN_BRANCH_POINTS points or its
    log i - E slope has the wrong sign (the anodic slope must be > 0, the cathodic slope < 0).
    No substitute slope, intercept or R2 is ever produced for such a branch.
    """
    lo, hi = min(window), max(window)
    if len(pts) < MIN_BRANCH_POINTS:
        return (f"{branch} branch unavailable: {len(pts)} data point(s) in the fit window "
                f"[{lo:.3f}, {hi:.3f}] V (at least {MIN_BRANCH_POINTS} are required)")
    slope = fit["m"]
    if expect_positive_slope and slope <= 0:
        return (f"{branch} branch unavailable: the fitted log i vs E slope is {slope:.3f} (not > 0), "
                "so the data in the window do not show anodic Tafel behaviour")
    if not expect_positive_slope and slope >= 0:
        return (f"{branch} branch unavailable: the fitted log i vs E slope is {slope:.3f} (not < 0), "
                "so the data in the window do not show cathodic Tafel behaviour")
    return None


def fit_tafel_curve(data: dict) -> dict:
    """
    CPython 3.10 High-Precision Tafel Extrapolation Engine (ASTM G102 & ASTM G59).
    Processes user-uploaded polarization data points, performs linear least-squares regression
    on anodic and cathodic branches, solves for intersection (Ecorr, Icorr), and computes
    polarization resistance Rp and annual penetration rates (mm/year).

    When a branch cannot be fitted (too few points in its window or a slope of the wrong sign)
    nothing is invented for it: that branch's slope, beta and R2 are null, and so are the
    Evans-intersection Ecorr/Icorr and everything derived from them, unless the caller
    supplied manualEcorrOverride / manualIcorrOverride. The result then carries
    fitStatus "unavailable" and the reasons in unavailable / unavailableReason.
    """
    start_time = time.perf_counter()
    raw_points = data.get("points") or data.get("rawPoints") or []
    file_content = data.get("fileContent") or data.get("fileText") or ""
    area = _scenario_number(data, ("electrodeAreaCm2", "specimenAreaCm2"), 1.0, "electrodeAreaCm2", "positive")

    # Parse file content if provided as string
    if not raw_points and file_content:
        import re
        lines = file_content.splitlines()
        parsed_pts = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith(";") or line.startswith("*"):
                continue
            parts = re.split(r'[\t,;\s]+', line)
            if len(parts) >= 2:
                try:
                    p0 = float(parts[0].replace(",", "."))
                    p1 = float(parts[1].replace(",", "."))
                    parsed_pts.append({"potential": p0, "current": abs(p1)})
                except ValueError:
                    continue
        if parsed_pts:
            raw_points = parsed_pts

    if not raw_points or len(raw_points) < 5:
        raise ValueError("Insufficient data points for Tafel extrapolation. A minimum of 5 experimental points is required.")

    # Unit of the bare "current" key (EUQ-3). It used to be guessed point by point (|c| < 0.1 and dataset
    # max < 0.5 -> amperes, else microamperes), so a low-current uA scan was inflated 1e6-fold and a dataset
    # with max between 0.1 and 0.5 mixed two scales in one curve. No value range identifies the unit, so the
    # caller must state it once for the whole dataset: currentUnit (A / mA / uA / nA) and, when the values
    # are already per cm2, currentIsDensity = true. The unit used is echoed in currentInput.
    uses_bare_current = any(_present(pt, "currentDensity_uA_cm2", "current_uA") is None
                            and pt.get("current") is not None for pt in raw_points)
    current_unit = None
    current_scale_to_uA = None
    current_is_density = False
    if uses_bare_current:
        unit_raw = data.get("currentUnit")
        if unit_raw is None:
            raise ValidationError(
                BAD_UNIT, "currentUnit",
                "points use the unit-less 'current' key; send currentUnit (one of "
                f"{sorted(CURRENT_UNIT_TO_UA)}) for the whole dataset, or send currentDensity_uA_cm2. "
                "The unit is not guessed from the magnitude of the values.",
                {"unit": None, "allowed": sorted(CURRENT_UNIT_TO_UA)})
        current_unit = require_unit("currentUnit", unit_raw, sorted(CURRENT_UNIT_TO_UA))
        current_scale_to_uA = CURRENT_UNIT_TO_UA[current_unit]
        density_raw = data.get("currentIsDensity", False)
        if not isinstance(density_raw, bool):
            raise ValidationError(BAD_UNIT, "currentIsDensity", "currentIsDensity must be true or false",
                                  {"unit": repr(density_raw), "allowed": [True, False]})
        current_is_density = density_raw
    current_keys = set()

    norm_points = []
    for idx, pt in enumerate(raw_points):
        pot_raw = _present(pt, "potential", "e", "voltage")
        if pot_raw is None:
            raise ValidationError(NON_FINITE, f"points[{idx}].potential",
                                  "point has no potential value (potential / e / voltage); no value is invented",
                                  {"type": "NoneType", "index": idx})
        pot = float(pot_raw)
        density_key = next((k for k in ("currentDensity_uA_cm2", "current_uA") if pt.get(k) is not None), None)
        curr_uA = None if density_key is None else pt[density_key]
        if curr_uA is None and pt.get("current") is not None:
            c = float(pt.get("current"))
            # One unit decision for the whole dataset (currentUnit / currentIsDensity above).
            curr_uA = abs(c) * current_scale_to_uA / (1.0 if current_is_density else area)
            current_keys.add("current")
        elif curr_uA is not None:
            current_keys.add(density_key)
            curr_uA = float(curr_uA)
        else:
            raise ValidationError(NON_FINITE, f"points[{idx}].current",
                                  "point has no current value (currentDensity_uA_cm2 / current_uA / current); "
                                  "no value is invented", {"type": "NoneType", "index": idx})

        curr_uA = max(1e-9, curr_uA)
        log_i = float(pt.get("logCurrentDensity") or math.log10(curr_uA))
        norm_points.append({
            "potential": round(pot, 4),
            "currentDensity_uA_cm2": round(curr_uA, 5),
            "logCurrentDensity": round(log_i, 4)
        })

    # Find raw minimum valley
    min_idx = 0
    min_curr = norm_points[0]["currentDensity_uA_cm2"]
    for i, p in enumerate(norm_points):
        if p["currentDensity_uA_cm2"] < min_curr:
            min_curr = p["currentDensity_uA_cm2"]
            min_idx = i

    raw_ecorr = norm_points[min_idx]["potential"]
    raw_icorr = min_curr

    potentials = [p["potential"] for p in norm_points]
    min_scan_e = min(potentials)
    max_scan_e = max(potentials)

    # Windows
    custom_cath = data.get("customCathodicRange")
    custom_anod = data.get("customAnodicRange")

    if custom_cath and len(custom_cath) == 2:
        cath_min_e, cath_max_e = custom_cath[0], custom_cath[1]
    else:
        cath_min_e = max(min_scan_e, raw_ecorr - 0.22)
        cath_max_e = min(raw_ecorr - 0.04, cath_min_e + 0.15)

    if custom_anod and len(custom_anod) == 2:
        anod_min_e, anod_max_e = custom_anod[0], custom_anod[1]
    else:
        anod_min_e = max(raw_ecorr + 0.04, raw_ecorr + 0.05)
        anod_max_e = min(max_scan_e, raw_ecorr + 0.22)

    cath_pts = [p for p in norm_points if min(cath_min_e, cath_max_e) <= p["potential"] <= max(cath_min_e, cath_max_e)]
    anod_pts = [p for p in norm_points if min(anod_min_e, anod_max_e) <= p["potential"] <= max(anod_min_e, anod_max_e)]

    cath_fit = linear_regression_py([p["potential"] for p in cath_pts], [p["logCurrentDensity"] for p in cath_pts])
    anod_fit = linear_regression_py([p["potential"] for p in anod_pts], [p["logCurrentDensity"] for p in anod_pts])

    # Branch validity: an unusable branch is unavailable, never replaced by an assumed slope or R2.
    cath_reason = _branch_unavailable_reason("Cathodic", (cath_min_e, cath_max_e), cath_pts, cath_fit, False)
    anod_reason = _branch_unavailable_reason("Anodic", (anod_min_e, anod_max_e), anod_pts, anod_fit, True)
    if cath_reason:
        cath_fit = None
    if anod_reason:
        anod_fit = None
    both_branches = cath_fit is not None and anod_fit is not None

    # Intersect (Evans construction): needs both branches. When the intersection is unusable (parallel
    # branches, or more than INTERSECTION_MAX_OFFSET_V from the measured valley) the measured valley is used as E_corr; this
    # substitution is REPORTED (intersectionStatus / intersectionNote), never silent.
    extrapolated_ecorr = None
    extrapolated_log_icorr = None
    intersection_note = None
    if both_branches:
        denom = anod_fit["m"] - cath_fit["m"]
        extrapolated_ecorr = raw_ecorr
        if abs(denom) > 1e-6:
            e_inter = (cath_fit["b"] - anod_fit["b"]) / denom
            if abs(e_inter - raw_ecorr) <= INTERSECTION_MAX_OFFSET_V:
                extrapolated_ecorr = e_inter
            else:
                intersection_note = (
                    f"the Evans intersection of the fitted branches is at {e_inter:.3f} V, "
                    f"{abs(e_inter - raw_ecorr):.3f} V from the measured current valley (limit {INTERSECTION_MAX_OFFSET_V:.2f} V); the measured "
                    f"valley {raw_ecorr:.4f} V is used as E_corr and i_corr is read from the anodic line there")
        else:
            intersection_note = (
                "the fitted branches are parallel, so they do not intersect; the measured current valley "
                f"{raw_ecorr:.4f} V is used as E_corr and i_corr is read from the anodic line there")

        extrapolated_log_icorr = anod_fit["m"] * extrapolated_ecorr + anod_fit["b"]

    # Manual Overrides
    if data.get("manualEcorrOverride") is not None:
        extrapolated_ecorr = float(data["manualEcorrOverride"])
    if data.get("manualIcorrOverride") is not None:
        extrapolated_log_icorr = math.log10(max(1e-9, float(data["manualIcorrOverride"])))

    extrapolated_icorr_uA = None if extrapolated_log_icorr is None else 10 ** extrapolated_log_icorr

    beta_a_v_dec = None if anod_fit is None else abs(1.0 / anod_fit["m"])
    beta_c_v_dec = None if cath_fit is None else abs(1.0 / cath_fit["m"])
    beta_a_mv_dec = None if beta_a_v_dec is None else beta_a_v_dec * 1000.0
    beta_c_mv_dec = None if beta_c_v_dec is None else beta_c_v_dec * 1000.0

    # Substrate & Annual Corrosion Rate: the alloyId the caller sent (never a default alloy), or the supplied
    # density / equivalentWeight / customComposition; otherwise the rate is unavailable with the reason.
    alloy_id_raw = data.get("alloyId") or data.get("materialId")
    alloy_id = str(alloy_id_raw).lower() if alloy_id_raw else None
    preset, substrate, substrate_reasons = _resolve_substrate(data, alloy_id)
    alloy_name = substrate["alloy_name"]
    density = substrate["density"]
    ew = substrate["ew"]
    substrate_known = not substrate_reasons
    if substrate_known:
        density = max(0.1, abs(density))
        ew = max(1.0, abs(ew))

    # Stern-Geary needs both slopes and i_corr; Faraday needs only i_corr
    stern_b = rp_ohm_cm2 = None
    if both_branches and extrapolated_icorr_uA is not None:
        stern_b = (beta_a_v_dec * beta_c_v_dec) / (LN10 * (beta_a_v_dec + beta_c_v_dec))
        i_corr_a_cm2 = extrapolated_icorr_uA * 1e-6
        rp_ohm_cm2 = stern_b / i_corr_a_cm2

    cr_mm_yr = cr_mpy = cr_um_yr = mass_loss_g_m2_day = severity = None
    if extrapolated_icorr_uA is not None and substrate_known:
        exact_k1 = (1e-6 * SECONDS_PER_YEAR * 10.0) / FARADAY_C_PER_MOL
        cr_mm_yr = (exact_k1 * extrapolated_icorr_uA * ew) / density
        cr_mpy = cr_mm_yr * MILS_PER_MM
        cr_um_yr = cr_mm_yr * 1000.0

        exact_k2 = (1e-6 * 86400.0 * 1e4) / FARADAY_C_PER_MOL
        mass_loss_g_m2_day = exact_k2 * extrapolated_icorr_uA * ew
        severity = classify_corrosion_severity(cr_mm_yr)

    # Tangent lines (only for the branches that were fitted)
    ref_e = extrapolated_ecorr if extrapolated_ecorr is not None else raw_ecorr
    e_min_plot = min(min_scan_e, ref_e - 0.35)
    e_max_plot = max(max_scan_e, ref_e + 0.35)
    n_steps = 60
    tangent_lines = []
    for i in range(n_steps + 1):
        e = e_min_plot + (e_max_plot - e_min_plot) * (i / n_steps)
        show_a = anod_fit is not None and (e >= ref_e - 0.04) and (e <= anod_max_e + 0.15)
        show_c = cath_fit is not None and (e <= ref_e + 0.04) and (e >= cath_min_e - 0.15)
        log_ia = anod_fit["m"] * e + anod_fit["b"] if show_a else None
        log_ic = cath_fit["m"] * e + cath_fit["b"] if show_c else None
        tangent_lines.append({
            "potential": round(e, 4),
            "logI_anodic": round(log_ia, 4) if show_a else None,
            "logI_cathodic": round(log_ic, 4) if show_c else None,
        })

    # Fitted Butler-Volmer Profile (needs both slopes and i_corr)
    fitted_bv = []
    if both_branches and extrapolated_icorr_uA is not None:
        for i in range(70):
            e = e_min_plot + (e_max_plot - e_min_plot) * (i / 69)
            overpot = e - extrapolated_ecorr
            ia = 10 ** (overpot / beta_a_v_dec)
            ic = 10 ** (-overpot / beta_c_v_dec)
            net_i = abs(ia - ic)
            total_curr = extrapolated_icorr_uA * net_i
            log_val = math.log10(max(1e-6, total_curr))
            fitted_bv.append({
                "potential": round(e, 4),
                "logI_model": round(log_val, 4)
            })

    duration_ms = round((time.perf_counter() - start_time) * 1000.0, 3)

    def _r(value, digits):
        return None if value is None else round(value, digits)

    result = {
        "success": True,
        "isPythonEngine": True,
        "pythonVersion": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "solverMethod": "Linear least-squares Tafel-branch fit with Evans-diagram intersection (ASTM G102 formulation)",
        "durationMs": duration_ms,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "eCorr": _r(extrapolated_ecorr, 4),
        "iCorr_uA_cm2": _r(extrapolated_icorr_uA, 4),
        "logIcorr": _r(extrapolated_log_icorr, 4),
        "rawEcorrValley": round(raw_ecorr, 4),
        "rawIcorrValley": round(raw_icorr, 4),
        "betaA_mV_dec": _r(beta_a_mv_dec, 2),
        "betaC_mV_dec": _r(beta_c_mv_dec, 2),
        "betaA_V_dec": _r(beta_a_v_dec, 4),
        "betaC_V_dec": _r(beta_c_v_dec, 4),
        "anodicSlope_dLogI_dE": None if anod_fit is None else round(anod_fit["m"], 4),
        "cathodicSlope_dLogI_dE": None if cath_fit is None else round(cath_fit["m"], 4),
        "anodicR2": None if anod_fit is None else anod_fit["r2"],
        "cathodicR2": None if cath_fit is None else cath_fit["r2"],
        "cathodicRange": [round(cath_min_e, 3), round(cath_max_e, 3)],
        "anodicRange": [round(anod_min_e, 3), round(anod_max_e, 3)],
        "sternGearyB_V": _r(stern_b, 5),
        "rp_ohm_cm2": _r(rp_ohm_cm2, 1),
        "corrosionRateMmYr": _r(cr_mm_yr, 5),
        "corrosionRateMpy": _r(cr_mpy, 3),
        "corrosionRateUmYr": _r(cr_um_yr, 2),
        "massLoss_g_m2_day": _r(mass_loss_g_m2_day, 4),
        "tangentLines": tangent_lines,
        "fittedButlerVolmer": fitted_bv,
        "severity": severity,
        "alloyId": alloy_id,
        "alloyName": alloy_name,
        "density_g_cm3": density,
        "equivalentWeight": ew,
        "specimenAreaCm2": area,
        # EUQ-3: the current unit used for every point (stated, never guessed per point).
        "currentInput": {
            "keys": sorted(current_keys),
            "currentUnit": current_unit,
            "currentIsDensity": None if current_unit is None else current_is_density,
            "densityUnit": "uA/cm2",
        },
        "pointsCount": len(norm_points),
        "minScanE": round(min_scan_e, 4),
        "maxScanE": round(max_scan_e, 4),
        "provenance": _provenance(preset),
    }
    if intersection_note and not (data.get("manualEcorrOverride") is not None
                                  and data.get("manualIcorrOverride") is not None):
        result["intersectionStatus"] = "substituted-measured-valley"
        result["intersectionNote"] = intersection_note
    if not both_branches or (extrapolated_icorr_uA is not None and not substrate_known):
        reasons = {}
        if anod_reason:
            reasons["anodicBranch"] = anod_reason
        if cath_reason:
            reasons["cathodicBranch"] = cath_reason
        if extrapolated_icorr_uA is None:
            reasons["iCorr_uA_cm2"] = ("the Evans intersection needs both Tafel branches; no corrosion "
                                       "current density is invented (supply manualIcorrOverride to use a known value)")
        if extrapolated_icorr_uA is not None and not substrate_known:
            reasons["substrate"] = substrate_reasons["substrate"]
        result["fitStatus"] = UNAVAILABLE_STATUS
        result["unavailableReason"] = "; ".join(reasons.values())
        result["unavailable"] = reasons
        result["unavailableNote"] = UNAVAILABLE_NOTE
    return result

def main():
    try:
        input_data = {}
        if len(sys.argv) > 1 and sys.argv[1].startswith("{"):
            input_data = json.loads(sys.argv[1])
        else:
            raw = sys.stdin.read().strip()
            if raw:
                input_data = json.loads(raw)
        
        if input_data.get("action") == "fit_curve" or "points" in input_data or "rawPoints" in input_data or "fileContent" in input_data:
            result = fit_tafel_curve(input_data)
        else:
            result = solve_tafel_corrosion_rate(input_data)
        print(json.dumps(result))
    except ValidationError as e:
        # Phase 6a envelope: invalid input, not a solver failure (HTTP 422 in the bridge).
        print(json.dumps(validation_envelope(e)))
        sys.exit(2)
    except Exception as e:
        err_res = {
            "success": False,
            "error": str(e),
            "isPythonEngine": True,
            "durationMs": 0.0,
            "errorKind": "internal",
        }
        print(json.dumps(err_res))
        sys.exit(1)

if __name__ == "__main__":
    main()

