#!/usr/bin/env python3
"""
MetalliX ASTM G102 / G59 High-Precision Tafel Annual Corrosion Rate Solver
CPython 3.10+ Scientific Engine for Electrochemical Degradation & Faraday Penetration

Formulas & Standards:
- ASTM G102: Standard Practice for Calculation of Corrosion Rates and Related Information from Electrochemical Measurements
- ASTM G59: Standard Test Method for Conducting Potentiodynamic Polarization Resistance Measurements
- NACE SP0169 / ISO 8044: Corrosion Rate Classification & Severity Grading
"""

import sys
import json
import math
import time

import alloy_registry
import physical_constants
from input_validation import UNKNOWN_ALLOY, UNKNOWN_ELEMENT, ValidationError, require_known_alloy, validation_envelope

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
DEFAULT_ALLOY_ID = "steel-316l"
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


def _provenance(preset: "_LazyPreset") -> dict:
    return {
        "registryVersion": alloy_registry.REGISTRY_VERSION,
        "constantsVersion": physical_constants.CONSTANTS_VERSION,
        "registryAlloyId": preset.registry_id,
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

def classify_corrosion_severity(cr_mm_yr: float) -> dict:
    """
    Categorizes corrosion rate based on NACE SP0169 / ISO 8044 / Fontana-Greene standards.
    """
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
    else:
        return {
            "level": "Unacceptable / Critical",
            "code": "UNACCEPTABLE",
            "color": "rose",
            "description": "Severe catastrophic dissolution. Wall breach and structural failure imminent without immediate mitigation.",
            "recommendation": "Material change required (upgrade to Inconel/316L/Titanium) or continuous heavy-duty barrier protection."
        }

def solve_tafel_corrosion_rate(data: dict) -> dict:
    """
    Core solver calculating annual corrosion rate from Tafel Icorr and substrate parameters.
    """
    start_time = time.perf_counter()

    # 1. Parse Input Parameters
    i_corr_ua_cm2 = float(data.get("iCorr_uA_cm2") or data.get("icorr") or data.get("i_corr") or 1.25)
    e_corr_v = float(data.get("eCorr_V") or data.get("ecorr") or data.get("e_corr") or -0.35)
    beta_a = float(data.get("betaA") or data.get("beta_a") or 0.120)  # V/decade
    beta_c = float(data.get("betaC") or data.get("beta_c") or 0.100)  # V/decade
    specimen_area_cm2 = float(data.get("specimenAreaCm2") or data.get("area") or 1.0)
    initial_thickness_mm = float(data.get("initialThicknessMm") or data.get("thicknessMm") or 5.0)
    allowable_loss_mm = float(data.get("allowableLossMm") or data.get("corrosionAllowanceMm") or 1.5)
    temp_c = float(data.get("temperatureC") or data.get("tempC") or 25.0)

    # 2. Material Substrate Lookup or Custom
    alloy_id = str(data.get("alloyId") or data.get("materialId") or DEFAULT_ALLOY_ID).lower()
    preset = _LazyPreset(alloy_id)

    alloy_name = data.get("alloyName") or preset["name"]
    density = float(data.get("density_g_cm3") or preset["density_g_cm3"])
    ew = float(data.get("equivalentWeight") or preset["ew"])
    ea_j_mol = float(data.get("activationEnergyJ_mol") or preset.get("activation_energy_j_mol", 32000.0))

    # If custom alloy composition provided, re-derive exact EW
    custom_comp = data.get("customComposition")
    if custom_comp and isinstance(custom_comp, dict):
        valencies = data.get("customValencies") or preset.get("valencies", {})
        atomic_weights = data.get("customAtomicWeights") or preset.get("atomic_weights", {})
        derived_ew = calculate_equivalent_weight(custom_comp, valencies, atomic_weights)
        if derived_ew > 0:
            ew = derived_ew

    # Ensure physical positive bounds
    i_corr_ua_cm2 = max(1e-9, abs(i_corr_ua_cm2))
    density = max(0.1, abs(density))
    ew = max(1.0, abs(ew))
    beta_a = max(0.005, abs(beta_a))
    beta_c = max(0.005, abs(beta_c))
    specimen_area_cm2 = max(1e-4, abs(specimen_area_cm2))

    # 3. Stern-Geary Kinetics (ASTM G59)
    # B = (beta_a * beta_c) / [2.302585 * (beta_a + beta_c)]
    stern_geary_b = (beta_a * beta_c) / (2.302585 * (beta_a + beta_c))
    
    # Polarization Resistance R_p = B / i_corr
    # i_corr in A/cm2 = i_corr_ua_cm2 * 1e-6
    i_corr_a_cm2 = i_corr_ua_cm2 * 1e-6
    rp_ohm_cm2 = stern_geary_b / i_corr_a_cm2
    rp_apparent_ohm = rp_ohm_cm2 / specimen_area_cm2

    # 4. Faraday's Law Corrosion Rates (ASTM G102)
    # CR (mm/year) = [K1 * i_corr (uA/cm2) * EW] / density (g/cm3)
    # K1 = (1e-6 * 31557600 * 10) / F = 0.0032707148 mm*g/(uA*cm*year) with the exact F
    exact_k1 = (1e-6 * SECONDS_PER_YEAR * 10.0) / FARADAY_C_PER_MOL
    cr_mm_yr = (exact_k1 * i_corr_ua_cm2 * ew) / density
    cr_mpy = cr_mm_yr * 39.37007874  # mils per year
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
    pitting_acceleration_factor = 3.5  # Typical pitting penetration vs uniform ratio

    for yr in years_timeline:
        loss_uniform_mm = cr_mm_yr * yr
        loss_pitting_mm = cr_mm_yr * yr * pitting_acceleration_factor
        remaining_wall_mm = max(0.0, initial_thickness_mm - loss_uniform_mm)
        remaining_pitting_mm = max(0.0, initial_thickness_mm - loss_pitting_mm)
        wall_loss_pct = min(100.0, (loss_uniform_mm / initial_thickness_mm) * 100.0)
        
        is_breached = loss_uniform_mm >= allowable_loss_mm
        
        projections.append({
            "year": yr,
            "lossUniformMm": round(loss_uniform_mm, 4),
            "lossPittingMm": round(loss_pitting_mm, 4),
            "remainingWallMm": round(remaining_wall_mm, 3),
            "remainingPittingMm": round(remaining_pitting_mm, 3),
            "wallLossPct": round(wall_loss_pct, 2),
            "exceedsAllowance": is_breached
        })

    # Remaining Useful Life (RUL) in Years before exceeding corrosion allowance
    rul_uniform_years = (allowable_loss_mm / cr_mm_yr) if cr_mm_yr > 0 else 999.0
    rul_pitting_years = (allowable_loss_mm / (cr_mm_yr * pitting_acceleration_factor)) if cr_mm_yr > 0 else 999.0

    # 6. Temperature Sensitivity (Arrhenius Model from 5°C to 85°C)
    t_ref_k = temp_c + ZERO_CELSIUS_K
    temp_sensitivity = []
    for t_test_c in range(5, 90, 10):
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
            "corrosionRateMpy": round(cr_test_mm_yr * 39.37, 2)
        })

    # 7. Severity Rating & Recommendations
    severity = classify_corrosion_severity(cr_mm_yr)

    # 8. Python Code Generation (reproducible script for user)
    reproducible_python_code = f"""# =========================================================================
# ASTM G102 & G59 Automated Annual Corrosion Rate Calculation
# Grounded in Faraday's Law & Stern-Geary Potentiodynamic Polarization
# =========================================================================
import math

# Inputs determined from Tafel Fit
i_corr_uA_cm2 = {i_corr_ua_cm2}  # Extrapolated corrosion current density
e_corr_V = {e_corr_v}          # Corrosion potential
beta_a = {beta_a}            # Anodic Tafel slope (V/decade)
beta_c = {beta_c}            # Cathodic Tafel slope (V/decade)

# Substrate properties ({alloy_name})
equivalent_weight = {ew}     # EW (g/equivalent)
density_g_cm3 = {density}        # Density rho (g/cm^3)

# 1. Stern-Geary Constant B & Polarization Resistance Rp (ASTM G59)
B = (beta_a * beta_c) / (2.302585 * (beta_a + beta_c))
i_corr_A_cm2 = i_corr_uA_cm2 * 1e-6
Rp = B / i_corr_A_cm2  # Ohm * cm^2

# 2. Faraday Penetration Rate (ASTM G102)
# Formula: CR (mm/yr) = K1 * (i_corr * EW) / density, K1 = 1e-6 * (s per year) * 10 / F
F = {FARADAY_C_PER_MOL!r}  # C/mol, exact SI 2019 value N_A * e
K1 = (1e-6 * 31557600.0 * 10.0) / F  # = 0.0032707148 mm * g / (uA * cm * year)
cr_mm_yr = (K1 * i_corr_uA_cm2 * equivalent_weight) / density_g_cm3
cr_mpy = cr_mm_yr * 39.3701  # mils per year

print(f"Stern-Geary B: {{B:.4f}} V")
print(f"Polarization Resistance Rp: {{Rp:.1f}} Ohm*cm^2")
print(f"Annual Corrosion Rate: {{cr_mm_yr:.5f}} mm/year ({{cr_mpy:.3f}} mpy)")
"""

    duration_ms = round((time.perf_counter() - start_time) * 1000.0, 3)

    return {
        "success": True,
        "isPythonEngine": True,
        "pythonVersion": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "standards": ["ASTM G102-89(2015)", "ASTM G59-97(2020)", "NACE SP0169", "ISO 8044"],
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
        "sternGearyB_V": round(stern_geary_b, 5),
        "rp_ohm_cm2": round(rp_ohm_cm2, 1),
        "rp_apparent_ohm": round(rp_apparent_ohm, 2),
        
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
        "rulUniformYears": round(rul_uniform_years, 2),
        "rulPittingYears": round(rul_pitting_years, 2),
        
        # Categorization & Engineering Decisions
        "severity": severity,
        
        # Time and Temperature Projections
        "timelineProjections": projections,
        "temperatureSensitivity": temp_sensitivity,
        
        # Reproducibility Snippet
        "pythonCode": reproducible_python_code,

        # Phase 6a provenance (registry / constants versions)
        "provenance": _provenance(preset),
    }

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

def fit_tafel_curve(data: dict) -> dict:
    """
    CPython 3.10 High-Precision Tafel Extrapolation Engine (ASTM G102 & ASTM G59).
    Processes user-uploaded polarization data points, performs linear least-squares regression
    on anodic and cathodic branches, solves for intersection (Ecorr, Icorr), and computes
    polarization resistance Rp and annual penetration rates (mm/year).
    """
    start_time = time.perf_counter()
    raw_points = data.get("points") or data.get("rawPoints") or []
    file_content = data.get("fileContent") or data.get("fileText") or ""
    area = float(data.get("electrodeAreaCm2") or data.get("specimenAreaCm2") or 1.0)
    
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

    norm_points = []
    for pt in raw_points:
        pot = float(pt.get("potential") or pt.get("e") or pt.get("voltage") or 0.0)
        curr_uA = pt.get("currentDensity_uA_cm2") or pt.get("current_uA")
        if curr_uA is None and pt.get("current") is not None:
            c = float(pt.get("current"))
            # Auto-detect Amperes vs microamperes
            if abs(c) < 0.1 and max(abs(float(p.get("current", 0.0))) for p in raw_points) < 0.5:
                curr_uA = abs(c) * 1e6 / area
            else:
                curr_uA = abs(c) / area
        elif curr_uA is not None:
            curr_uA = float(curr_uA)
        else:
            curr_uA = 1.0

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

    # Guard slope directions
    if cath_fit["m"] >= 0 or len(cath_pts) < 3:
        m_fall = -8.33
        b_fall = norm_points[min_idx]["logCurrentDensity"] - m_fall * raw_ecorr + 0.5
        cath_fit = {"m": m_fall, "b": b_fall, "r2": 0.85}

    if anod_fit["m"] <= 0 or len(anod_pts) < 3:
        m_fall = 10.0
        b_fall = norm_points[min_idx]["logCurrentDensity"] - m_fall * raw_ecorr + 0.5
        anod_fit = {"m": m_fall, "b": b_fall, "r2": 0.85}

    # Intersect
    denom = anod_fit["m"] - cath_fit["m"]
    extrapolated_ecorr = raw_ecorr
    if abs(denom) > 1e-6:
        e_inter = (cath_fit["b"] - anod_fit["b"]) / denom
        if abs(e_inter - raw_ecorr) <= 0.25:
            extrapolated_ecorr = e_inter

    extrapolated_log_icorr = anod_fit["m"] * extrapolated_ecorr + anod_fit["b"]

    # Manual Overrides
    if data.get("manualEcorrOverride") is not None:
        extrapolated_ecorr = float(data["manualEcorrOverride"])
    if data.get("manualIcorrOverride") is not None:
        extrapolated_log_icorr = math.log10(max(1e-9, float(data["manualIcorrOverride"])))

    extrapolated_icorr_uA = 10 ** extrapolated_log_icorr

    beta_a_v_dec = abs(1.0 / anod_fit["m"])
    beta_c_v_dec = abs(1.0 / cath_fit["m"])
    beta_a_mv_dec = beta_a_v_dec * 1000.0
    beta_c_mv_dec = beta_c_v_dec * 1000.0

    # Substrate & Annual Corrosion Rate
    alloy_id = str(data.get("alloyId") or data.get("materialId") or DEFAULT_ALLOY_ID).lower()
    preset = _LazyPreset(alloy_id)
    alloy_name = data.get("alloyName") or preset["name"]
    density = float(data.get("density_g_cm3") or preset["density_g_cm3"])
    ew = float(data.get("equivalentWeight") or preset["ew"])

    # Stern-Geary & Faraday
    stern_b = (beta_a_v_dec * beta_c_v_dec) / (2.302585 * (beta_a_v_dec + beta_c_v_dec))
    i_corr_a_cm2 = extrapolated_icorr_uA * 1e-6
    rp_ohm_cm2 = stern_b / i_corr_a_cm2

    exact_k1 = (1e-6 * SECONDS_PER_YEAR * 10.0) / FARADAY_C_PER_MOL
    cr_mm_yr = (exact_k1 * extrapolated_icorr_uA * ew) / density
    cr_mpy = cr_mm_yr * 39.3701
    cr_um_yr = cr_mm_yr * 1000.0

    exact_k2 = (1e-6 * 86400.0 * 1e4) / FARADAY_C_PER_MOL
    mass_loss_g_m2_day = exact_k2 * extrapolated_icorr_uA * ew

    # Tangent lines
    e_min_plot = min(min_scan_e, extrapolated_ecorr - 0.35)
    e_max_plot = max(max_scan_e, extrapolated_ecorr + 0.35)
    n_steps = 60
    tangent_lines = []
    for i in range(n_steps + 1):
        e = e_min_plot + (e_max_plot - e_min_plot) * (i / n_steps)
        log_ia = anod_fit["m"] * e + anod_fit["b"]
        log_ic = cath_fit["m"] * e + cath_fit["b"]
        show_a = (e >= extrapolated_ecorr - 0.04) and (e <= anod_max_e + 0.15)
        show_c = (e <= extrapolated_ecorr + 0.04) and (e >= cath_min_e - 0.15)
        tangent_lines.append({
            "potential": round(e, 4),
            "logI_anodic": round(log_ia, 4) if show_a else None,
            "logI_cathodic": round(log_ic, 4) if show_c else None,
        })

    # Fitted Butler-Volmer Profile
    fitted_bv = []
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

    severity = classify_corrosion_severity(cr_mm_yr)
    duration_ms = round((time.perf_counter() - start_time) * 1000.0, 3)

    return {
        "success": True,
        "isPythonEngine": True,
        "pythonVersion": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "solverMethod": "ASTM G102 / G59 CPython 3.10 Linear Least-Squares Evans Optimization",
        "durationMs": duration_ms,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "eCorr": round(extrapolated_ecorr, 4),
        "iCorr_uA_cm2": round(extrapolated_icorr_uA, 4),
        "logIcorr": round(extrapolated_log_icorr, 4),
        "rawEcorrValley": round(raw_ecorr, 4),
        "rawIcorrValley": round(raw_icorr, 4),
        "betaA_mV_dec": round(beta_a_mv_dec, 2),
        "betaC_mV_dec": round(beta_c_mv_dec, 2),
        "betaA_V_dec": round(beta_a_v_dec, 4),
        "betaC_V_dec": round(beta_c_v_dec, 4),
        "anodicSlope_dLogI_dE": round(anod_fit["m"], 4),
        "cathodicSlope_dLogI_dE": round(cath_fit["m"], 4),
        "anodicR2": anod_fit["r2"],
        "cathodicR2": cath_fit["r2"],
        "cathodicRange": [round(cath_min_e, 3), round(cath_max_e, 3)],
        "anodicRange": [round(anod_min_e, 3), round(anod_max_e, 3)],
        "sternGearyB_V": round(stern_b, 5),
        "rp_ohm_cm2": round(rp_ohm_cm2, 1),
        "corrosionRateMmYr": round(cr_mm_yr, 5),
        "corrosionRateMpy": round(cr_mpy, 3),
        "corrosionRateUmYr": round(cr_um_yr, 2),
        "massLoss_g_m2_day": round(mass_loss_g_m2_day, 4),
        "tangentLines": tangent_lines,
        "fittedButlerVolmer": fitted_bv,
        "severity": severity,
        "alloyId": alloy_id,
        "alloyName": alloy_name,
        "density_g_cm3": density,
        "equivalentWeight": ew,
        "specimenAreaCm2": area,
        "pointsCount": len(norm_points),
        "minScanE": round(min_scan_e, 4),
        "maxScanE": round(max_scan_e, 4),
        "provenance": _provenance(preset),
    }

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

