"""
lpbf_fatigue_fracture.py — Phase 13: Rigorous Murakami Fatigue & Fracture Mechanics Engine
========================================================================================
Physics-grounded fatigue limit, Kitagawa-Takahashi diagram, and Paris crack growth engine.

Theoretical Foundations:
  1. Murakami, Y. (2002). "Metal Fatigue: Effects of Small Defects and Nonmetallic Inclusions." Elsevier.
  2. Kitagawa, H., & Takahashi, S. (1976). "Applicability of fracture mechanics to very small cracks."
  3. El Haddad, M. H., et al. (1979). "Fatigue life predictions for notch and crack." J. Eng. Mater. Technol.
  4. Paris, P., & Erdogan, F. (1963). "A critical analysis of crack propagation laws." J. Basic Eng.
  5. ASTM E647: for R <= 0 the stress-intensity range is Delta_K = K_max (compressive part excluded).

Stress-intensity convention (fixes KS-2 / KS-3 of the 2026-10 physics audit):
  Murakami's sqrt(area) stress-intensity factor, K_I,max = Y * sigma * sqrt(pi * sqrt(area)) with
  Y = 0.65 for a surface (and sub-surface, on the virtual area) defect and Y = 0.5 for an internal
  defect (Murakami 2002, ch. 2; Murakami & Endo 1994), is used in BOTH the El-Haddad intrinsic length
  and the Paris integration:
    * El-Haddad: a0 = (1/pi) * (Delta_K_th / (Y * sigma_e0))^2 on the sqrt(area) scale, and
      sigma_w = sigma_e0 * sqrt(a0 / (sqrt(area) + a0)). Before, Y was omitted (Y = 1) and an
      ad hoc factor C_loc / 1.56 was applied, which put the long-crack asymptote 1.7x-2x too low.
    * Paris: the crack is the defect itself, x = sqrt(area), starting at x0 = sqrt(area) (not
      sqrt(area)/2), Delta_K = Y_loc * Delta_sigma_eff * sqrt(pi * x), Delta_sigma_eff = sigma_max for
      R <= 0 (ASTM E647) and sigma_max - sigma_min for R > 0; the life is the closed-form Paris
      integral (constant Y), not a forward-Euler sum.
  sigma_e0 is a stress AMPLITUDE at R = -1, where sigma_a = sigma_max, so pairing it with Delta_K_th in
  the K_max (R <= 0) convention is consistent. The stored Delta_K_th values are internal table values
  without a citation and without a recorded stress ratio; they are used as the threshold in that
  convention for every R (no R dependence of Delta_K_th is modelled).

Standard Alloy Fatigue Properties Database (calibrated from literature):
  - Ti-6Al-4V (LPBF As-Built / Stress-Relieved):
      HV: 340, sigma_e0: 510 MPa, Delta_K_th: 3.2 MPa*sqrt(m), K_IC: 55 MPa*sqrt(m), Paris C: 1.8e-11, m: 3.3
  - 316L SS (LPBF As-Built):
      HV: 215, sigma_e0: 240 MPa, Delta_K_th: 4.8 MPa*sqrt(m), K_IC: 85 MPa*sqrt(m), Paris C: 3.5e-12, m: 3.1
  - Inconel 718 (LPBF Direct Aged):
      HV: 440, sigma_e0: 620 MPa, Delta_K_th: 4.2 MPa*sqrt(m), K_IC: 70 MPa*sqrt(m), Paris C: 1.2e-11, m: 3.4
  - AlSi10Mg (LPBF As-Built):
      HV: 115, sigma_e0: 150 MPa, Delta_K_th: 1.8 MPa*sqrt(m), K_IC: 32 MPa*sqrt(m), Paris C: 2.1e-10, m: 3.8
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import List, Dict, Any, Mapping, Optional, Tuple

import alloy_data_kinetics_uq_fatigue as _fatigue_data
import alloy_registry
import input_validation
import murakami_constants


@dataclass
class AlloyFatigueConstants:
    name: str
    hardness_HV: float
    smooth_fatigue_limit_MPa: float     # sigma_e0 (smooth specimen endurance limit at R=-1)
    threshold_stress_intensity_MPa_m: float # Delta_K_th [MPa*m^0.5]
    fracture_toughness_K_IC: float      # K_IC [MPa*m^0.5]
    paris_C: float                      # Paris constant C [m/cycle / (MPa*sqrt(m))^m]
    paris_m: float                      # Paris exponent m


def fatigue_constants(alloy_name: str) -> AlloyFatigueConstants:
    """Registry-backed constants (domain "fatigue_fracture") for ``alloy_name``.

    Phase 6a structural migration (design step (a)): the values are the former
    local table, now held by alloy_registry; ``name`` is the legacy table key.
    Raises input_validation.ValidationError (UNKNOWN_ALLOY) for a name without
    fatigue data; before the migration such names silently used Ti-6Al-4V.
    """
    record = input_validation.require_known_alloy(
        alloy_name, alloy_registry.DOMAIN_FATIGUE_FRACTURE, field="alloyName")
    values = {key: record.value(key, alloy_registry.DOMAIN_FATIGUE_FRACTURE)
              for key in _fatigue_data.FATIGUE_KEYS}
    return AlloyFatigueConstants(name=_fatigue_data.FATIGUE_LEGACY_NAMES[record.id], **values)


# Read-only view keyed by the legacy names (same keys, order and values as before).
ALLOY_FATIGUE_DATABASE: Mapping[str, AlloyFatigueConstants] = MappingProxyType({
    legacy: fatigue_constants(legacy) for legacy in _fatigue_data.FATIGUE_LEGACY_NAMES.values()
})


# Murakami sqrt(area) stress-intensity geometry factor Y by canonical defect location:
# K_I,max = Y * sigma * sqrt(pi * sqrt(area)). Murakami (2002) ch. 2 / Murakami & Endo (1994):
# 0.65 for a surface defect, 0.5 for an internal defect. A sub-surface defect is treated as a
# surface defect on its virtual area (murakami_constants docstring), so it takes 0.65 as well.
MURAKAMI_SIF_Y: Mapping[str, float] = MappingProxyType({
    murakami_constants.SURFACE: 0.65,
    murakami_constants.SUBSURFACE: 0.65,
    murakami_constants.INTERNAL: 0.5,
})
DELTA_K_CONVENTION = "ASTM E647: Delta_K = K_max for R <= 0, K_max - K_min for R > 0"
PARIS_INTEGRATION = "closed-form Paris integral in x = sqrt(area) (constant Murakami Y)"
PARIS_CURVE_POINTS = 50


def murakami_sif_geometry_factor(location: str) -> float:
    """Y of K_I,max = Y * sigma * sqrt(pi * sqrt(area)) for ``location`` (ValidationError if unknown)."""
    return MURAKAMI_SIF_Y[murakami_constants.classify_location(location)]


class MurakamiFatigueEngine:
    """Calculates defect-tolerant fatigue endurance limits and crack propagation lifetimes."""

    def __init__(self, alloy_name: str = "Ti-6Al-4V", custom_alloy: Optional[AlloyFatigueConstants] = None):
        # A dataclass instance is always truthy, so this equals the old `custom_alloy or ...`.
        self.alloy = custom_alloy if custom_alloy is not None else fatigue_constants(alloy_name)

    def el_haddad_intrinsic_crack_length_um(self, location: str = "internal") -> float:
        """El-Haddad intrinsic length a0 on the sqrt(area) scale (micrometres) for ``location``.

        a0 = (1/pi) * (Delta_K_th / (Y * sigma_e0))^2 with Murakami's Y (0.65 surface / sub-surface,
        0.5 internal), so that the long-crack asymptote is Delta_K_th = Y * sigma * sqrt(pi * sqrt(area)),
        the same stress-intensity factor as the Murakami branch (El Haddad, Topper & Smith 1979 with
        the geometry factor; Murakami 2002). Fix KS-2: Y was omitted (Y = 1).
        """
        y = murakami_sif_geometry_factor(location)
        a0_m = (1.0 / math.pi) * (
            (self.alloy.threshold_stress_intensity_MPa_m / (y * self.alloy.smooth_fatigue_limit_MPa)) ** 2)
        return a0_m * 1e6  # Convert meters to µm

    def murakami_geometric_constant(self, location: str) -> float:
        """Murakami C factor for surface (1.43), sub-surface (1.41) or internal (1.56) defect.

        Shared with murakami_fatigue_screening via murakami_constants; an unknown
        location raises input_validation.ValidationError instead of defaulting.
        """
        return murakami_constants.murakami_geometric_constant(location)

    @staticmethod
    def _require_stress_ratio(stress_ratio_R: float) -> float:
        """Finite R < 1. R = 1 (static load) has no stress range and divides by zero in
        sigma_max = delta_sigma / (1 - R); it is rejected, not clamped."""
        r = input_validation.require_finite("stressRatio_R", stress_ratio_R)
        if r >= 1.0:
            raise input_validation.ValidationError(
                input_validation.OUT_OF_RANGE, "stressRatio_R",
                "must be < 1 (R = sigma_min / sigma_max; R = 1 is a static load)",
                {"value": r, "hi": 1.0, "hiInclusive": False})
        return r

    def calculate_fatigue_limit(
        self,
        sqrt_area_um: float,
        location: str = "internal",
        stress_ratio_R: float = -1.0
    ) -> Dict[str, float]:
        """
        Computes the fatigue limit considering:
          1. Classic Murakami formula
          2. El-Haddad / Kitagawa-Takahashi bounded transition
          3. Stress ratio R correction (Murakami-Nisitani power law)
        """
        self.murakami_geometric_constant(location)  # validates the location first, as before
        sqrt_area_um = input_validation.require_positive("sqrtArea_um", sqrt_area_um)
        stress_ratio_R = self._require_stress_ratio(stress_ratio_R)
        hv = self.alloy.hardness_HV
        sigma_e0 = self.alloy.smooth_fatigue_limit_MPa
        y_sif = murakami_sif_geometry_factor(location)
        a0_um = self.el_haddad_intrinsic_crack_length_um(location)

        # Pure Murakami formula (valid for medium-to-large defects)
        # sigma_w = c * (HV + 120) / (sqrt_area)^(1/6)
        area_safe = sqrt_area_um  # validated finite and > 0 above
        murakami_raw = murakami_constants.murakami_sqrt_area_limit_MPa(area_safe, hv, location)

        # Kitagawa-Takahashi / El-Haddad bounded limit with the location's Murakami Y inside a0
        # (KS-2); the location enters only through Y, no extra C_loc / C_internal factor.
        el_haddad_limit = sigma_e0 * math.sqrt(a0_um / (area_safe + a0_um))

        # Reconciled limit: Cannot exceed smooth fatigue limit sigma_e0
        fatigue_limit_R_minus_1 = min(sigma_e0, el_haddad_limit, murakami_raw)

        # Stress ratio R correction (Murakami-Nisitani formula for R != -1)
        # sigma_w(R) = sigma_w(-1) * ((1 - R) / 2)^alpha
        alpha = 0.226 + 0.0001 * hv
        if stress_ratio_R > 0.99:
            stress_ratio_R = 0.99
        r_factor = ((1.0 - stress_ratio_R) / 2.0) ** alpha if stress_ratio_R != -1.0 else 1.0

        corrected_fatigue_limit = fatigue_limit_R_minus_1 * r_factor

        return {
            "sqrt_area_um": sqrt_area_um,
            "hardness_HV": hv,
            "el_haddad_a0_um": round(a0_um, 2),
            "el_haddad_geometry_factor_Y": y_sif,
            "murakami_raw_MPa": round(murakami_raw, 1),
            "fatigue_limit_R_minus_1_MPa": round(fatigue_limit_R_minus_1, 1),
            "stress_ratio_R": stress_ratio_R,
            "fatigue_limit_corrected_MPa": round(corrected_fatigue_limit, 1),
            "location": location
        }

    def generate_kitagawa_takahashi_curve(
        self,
        location: str = "internal",
        stress_ratio_R: float = -1.0,
        n_points: int = 50
    ) -> List[Dict[str, float]]:
        """Generates the Kitagawa-Takahashi curve points from 0.1 µm to 1000 µm."""
        # Logarithmic spacing from 0.1 µm to 1000 µm
        log_min, log_max = math.log10(0.1), math.log10(1000.0)
        points = []

        for i in range(n_points):
            val_um = 10.0 ** (log_min + (log_max - log_min) * (i / (n_points - 1)))
            res = self.calculate_fatigue_limit(val_um, location=location, stress_ratio_R=stress_ratio_R)
            points.append({
                "defect_sqrt_area_um": round(val_um, 2),
                "fatigue_limit_MPa": res["fatigue_limit_corrected_MPa"]
            })
        return points

    def simulate_paris_crack_growth(
        self,
        initial_defect_sqrt_area_um: float,
        cyclic_stress_amplitude_MPa: float,
        stress_ratio_R: float = 0.1,
        cycles_max: int = 10_000_000,
        location: str = "internal",
    ) -> Dict[str, Any]:
        """
        Paris-Erdogan growth da/dN = C * (Delta_K)^m of the defect itself (fix KS-3).

        The crack size is x = sqrt(area), starting at x0 = sqrt(area) of the defect, with Murakami's
        Delta_K = Y_loc * Delta_sigma_eff * sqrt(pi * x): Y_loc = 0.65 (surface / sub-surface) or 0.5
        (internal), Delta_sigma_eff = sigma_max for R <= 0 (ASTM E647) and sigma_max - sigma_min for R > 0,
        sigma_max = 2 * sigma_a / (1 - R). Fracture when K_max = Y_loc * sigma_max * sqrt(pi * x) = K_IC.
        With constant Y the life is the closed-form integral
            N(x) = (x^(1 - m/2) - x0^(1 - m/2)) / ((1 - m/2) * C * (Y * Delta_sigma_eff * sqrt(pi))^m)
        (ln(x / x0) / (C * (Y * Delta_sigma_eff * sqrt(pi))^2) for m = 2). Using the sqrt(area) SIF up to
        the critical size is a screening assumption (no crack-shape evolution is modelled).
        """
        initial_defect_sqrt_area_um = input_validation.require_positive(
            "sqrtArea_um", initial_defect_sqrt_area_um)
        cyclic_stress_amplitude_MPa = input_validation.require_positive(
            "stressAmplitude_MPa", cyclic_stress_amplitude_MPa)
        stress_ratio_R = self._require_stress_ratio(stress_ratio_R)
        y_geom = murakami_sif_geometry_factor(location)

        c_paris = self.alloy.paris_C
        m_paris = self.alloy.paris_m
        k_ic = self.alloy.fracture_toughness_K_IC
        delta_k_th = self.alloy.threshold_stress_intensity_MPa_m

        x0 = initial_defect_sqrt_area_um * 1e-6           # sqrt(area) [m]
        delta_sigma = 2.0 * cyclic_stress_amplitude_MPa    # sigma_max - sigma_min
        sigma_max = delta_sigma / (1.0 - stress_ratio_R)
        delta_sigma_eff = sigma_max if stress_ratio_R <= 0.0 else delta_sigma
        # Critical sqrt(area): K_IC = Y * sigma_max * sqrt(pi * x_f)
        x_final = ((k_ic / (y_geom * sigma_max)) ** 2) / math.pi

        def delta_k(x: float) -> float:
            return y_geom * delta_sigma_eff * math.sqrt(math.pi * x)

        b = c_paris * (y_geom * delta_sigma_eff * math.sqrt(math.pi)) ** m_paris  # da/dN = b * x^(m/2)
        q = 1.0 - m_paris / 2.0

        def cycles_to(x: float) -> float:
            if abs(q) < 1e-12:
                return math.log(x / x0) / b
            return (x ** q - x0 ** q) / (q * b)

        def size_after(n: float) -> float:
            if abs(q) < 1e-12:
                return x0 * math.exp(b * n)
            return (x0 ** q + q * b * n) ** (1.0 / q)

        dk0 = delta_k(x0)
        result: Dict[str, Any] = {
            "location": location,
            "geometry_factor_Y": y_geom,
            "delta_sigma_eff_MPa": round(delta_sigma_eff, 2),
            "delta_K_initial_MPa_m": round(dk0, 3),
            "delta_K_convention": DELTA_K_CONVENTION,
            "critical_sqrt_area_um": round(x_final * 1e6, 2),
            "integration": PARIS_INTEGRATION,
            "initial_crack_size_um": initial_defect_sqrt_area_um,
        }
        start_point = [{"cycles": 0, "crack_length_um": initial_defect_sqrt_area_um,
                        "delta_K_MPa_m": round(dk0, 2)}]

        # Below threshold at the initial defect: no growth (infinite life within the model)
        if dk0 < delta_k_th:
            result.update({"status": "non_propagating", "cycles_to_failure": cycles_max,
                           "final_crack_size_um": round(x0 * 1e6, 2), "crack_growth_curve": start_point})
            return result

        if x0 >= x_final:
            # K_max >= K_IC already at the initial defect: fracture on the first load cycle.
            result.update({"status": "fractured", "cycles_to_failure": 0,
                           "final_crack_size_um": round(x0 * 1e6, 2), "crack_growth_curve": start_point})
            return result

        n_failure = cycles_to(x_final)
        if n_failure > cycles_max:
            status, n_end, x_end = "runout", float(cycles_max), size_after(float(cycles_max))
        else:
            status, n_end, x_end = "fractured", n_failure, x_final

        curve = []
        last = PARIS_CURVE_POINTS - 1
        for i in range(PARIS_CURVE_POINTS):
            # geometric spacing in x from x0 to x_end (both ends included)
            x = x0 * (x_end / x0) ** (i / last)
            n = 0.0 if i == 0 else (n_end if i == last else cycles_to(x))
            curve.append({
                "cycles": int(n),
                "crack_length_um": round(x * 1e6, 2),
                "delta_K_MPa_m": round(delta_k(x), 2),
            })

        result.update({
            "status": status,
            "cycles_to_failure": int(n_end),
            "final_crack_size_um": round(x_end * 1e6, 2),
            "crack_growth_curve": curve,
        })
        return result
