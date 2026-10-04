"""
lpbf_fatigue_fracture.py — Phase 13: Rigorous Murakami Fatigue & Fracture Mechanics Engine
========================================================================================
Physics-grounded fatigue limit, Kitagawa-Takahashi diagram, and Paris crack growth engine.

Theoretical Foundations:
  1. Murakami, Y. (2002). "Metal Fatigue: Effects of Small Defects and Nonmetallic Inclusions." Elsevier.
  2. Kitagawa, H., & Takahashi, S. (1976). "Applicability of fracture mechanics to very small cracks."
  3. El Haddad, M. H., et al. (1979). "Fatigue life predictions for notch and crack." J. Eng. Mater. Technol.
  4. Paris, P., & Erdogan, F. (1963). "A critical analysis of crack propagation laws." J. Basic Eng.

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


class MurakamiFatigueEngine:
    """Calculates defect-tolerant fatigue endurance limits and crack propagation lifetimes."""

    def __init__(self, alloy_name: str = "Ti-6Al-4V", custom_alloy: Optional[AlloyFatigueConstants] = None):
        # A dataclass instance is always truthy, so this equals the old `custom_alloy or ...`.
        self.alloy = custom_alloy if custom_alloy is not None else fatigue_constants(alloy_name)

    def el_haddad_intrinsic_crack_length_um(self) -> float:
        """Calculates El-Haddad intrinsic crack size a0 (in micrometers)."""
        # a0 = (1/pi) * (Delta_K_th / sigma_e0)^2  [in meters]
        a0_m = (1.0 / math.pi) * ((self.alloy.threshold_stress_intensity_MPa_m / self.alloy.smooth_fatigue_limit_MPa) ** 2)
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
        c_geom = self.murakami_geometric_constant(location)
        sqrt_area_um = input_validation.require_positive("sqrtArea_um", sqrt_area_um)
        stress_ratio_R = self._require_stress_ratio(stress_ratio_R)
        hv = self.alloy.hardness_HV
        sigma_e0 = self.alloy.smooth_fatigue_limit_MPa
        a0_um = self.el_haddad_intrinsic_crack_length_um()

        # Pure Murakami formula (valid for medium-to-large defects)
        # sigma_w = c * (HV + 120) / (sqrt_area)^(1/6)
        area_safe = sqrt_area_um  # validated finite and > 0 above
        murakami_raw = murakami_constants.murakami_sqrt_area_limit_MPa(area_safe, hv, location)

        # Kitagawa-Takahashi / El-Haddad bounded limit:
        # Scale by geometric location factor ratio (surface vs internal)
        geom_ratio = c_geom / murakami_constants.C_INTERNAL
        el_haddad_limit = sigma_e0 * math.sqrt(a0_um / (area_safe + a0_um)) * geom_ratio

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
        cycles_max: int = 10_000_000
    ) -> Dict[str, Any]:
        """
        Integrates Paris-Erdogan law da/dN = C * (Delta_K)^m
        Delta_K = Y * Delta_sigma * sqrt(pi * a)
        """
        initial_defect_sqrt_area_um = input_validation.require_positive(
            "sqrtArea_um", initial_defect_sqrt_area_um)
        cyclic_stress_amplitude_MPa = input_validation.require_positive(
            "stressAmplitude_MPa", cyclic_stress_amplitude_MPa)
        stress_ratio_R = self._require_stress_ratio(stress_ratio_R)
        # Initial crack half-length in meters: a0 = initial_defect / 2
        a = (initial_defect_sqrt_area_um / 2.0) * 1e-6
        delta_sigma = cyclic_stress_amplitude_MPa * 2.0  # Peak-to-peak stress range
        y_geom = 0.65  # Typical shape factor for semi-elliptical/internal defect

        c_paris = self.alloy.paris_C
        m_paris = self.alloy.paris_m
        k_ic = self.alloy.fracture_toughness_K_IC
        delta_k_th = self.alloy.threshold_stress_intensity_MPa_m

        # Critical final crack size at fracture: a_f = (K_IC / (Y * sigma_max))^2 / pi
        sigma_max = delta_sigma / (1.0 - stress_ratio_R)
        a_final = ((k_ic / (y_geom * sigma_max)) ** 2) / math.pi

        current_cycles = 0
        curve = []
        step_da = a * 0.05  # Adaptive step size: 5% of current crack length

        while a < a_final and current_cycles < cycles_max:
            delta_k = y_geom * delta_sigma * math.sqrt(math.pi * a)

            # If Delta_K is below threshold, crack does not propagate (infinite life)
            if delta_k < delta_k_th and current_cycles == 0:
                return {
                    "status": "non_propagating",
                    "cycles_to_failure": cycles_max,
                    "final_crack_size_um": round(a * 1e6, 2),
                    "initial_crack_size_um": initial_defect_sqrt_area_um,
                    "crack_growth_curve": [{"cycles": 0, "crack_length_um": initial_defect_sqrt_area_um}]
                }

            da_dn = c_paris * (delta_k ** m_paris)
            if da_dn <= 1e-15:
                break

            dn = step_da / da_dn
            current_cycles += int(dn)
            a += step_da
            step_da = a * 0.05

            if len(curve) < 100:
                curve.append({
                    "cycles": current_cycles,
                    "crack_length_um": round(a * 1e6, 2),
                    "delta_K_MPa_m": round(delta_k, 2)
                })

        return {
            "status": "fractured" if a >= a_final else "runout",
            "cycles_to_failure": current_cycles,
            "final_crack_size_um": round(min(a, a_final) * 1e6, 2),
            "initial_crack_size_um": initial_defect_sqrt_area_um,
            "crack_growth_curve": curve
        }
