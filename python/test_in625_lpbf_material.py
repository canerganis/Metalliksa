"""Source-bounded IN625 fusion-enthalpy screening contract."""

import hashlib
import json
import math
import unittest

import numpy as np

from four_alloy_materials import FOUR_ALLOY_IDS
from in625_thermal_material import (
    LIQUIDUS_K, SOLIDUS_K, LATENT_HEAT_J_KG,
    in625_lpbf_thermal_at_kelvin,
)
from lpbf_material_registry import (
    catalog, material, thermal_screening_at, thermal_screening_material,
)


# Independent oracle contract for the bounded Sabau/JMatPro model. These
# literals are transcribed from the model source, not imported from the
# production implementation. The oracle integrates Cp by Gauss-Legendre
# quadrature rather than using the production polynomial primitive.
_ORACLE_REFERENCE_K = 273.15
_ORACLE_SOLIDUS_K = 1563.15
_ORACLE_LIQUIDUS_K = 1623.15
_ORACLE_LATENT_J_KG = 290_000.0
_ORACLE_LIQUID_CP_J_KGK = 700.0
_ORACLE_CP_COEFFICIENTS = (362.0, 0.125, 0.0001741, -7.527126e-8)
_ORACLE_GL_NODES, _ORACLE_GL_WEIGHTS = np.polynomial.legendre.leggauss(12)
_ORACLE_ABS_TOL_J_KG = 1e-6


def _oracle_solid_cp(temperature_k):
    a, b, c, d = _ORACLE_CP_COEFFICIENTS
    return a + b*temperature_k + c*temperature_k**2 + d*temperature_k**3


def _oracle_gauss_integral(function, low, high):
    """Integrate a smooth specific-heat law independently of production code."""
    midpoint = (low + high) / 2
    half_width = (high - low) / 2
    weighted_values = (
        float(weight) * function(midpoint + half_width*float(node))
        for node, weight in zip(_ORACLE_GL_NODES, _ORACLE_GL_WEIGHTS)
    )
    return half_width * math.fsum(weighted_values)


def _oracle_mushy_cp(temperature_k):
    width = _ORACLE_LIQUIDUS_K - _ORACLE_SOLIDUS_K
    cp_solidus = _oracle_solid_cp(_ORACLE_SOLIDUS_K)
    fraction = (temperature_k - _ORACLE_SOLIDUS_K) / width
    return cp_solidus + (_ORACLE_LIQUID_CP_J_KGK - cp_solidus)*fraction


def _oracle_specific_enthalpy(temperature_k):
    if temperature_k <= _ORACLE_SOLIDUS_K:
        return _oracle_gauss_integral(
            _oracle_solid_cp, _ORACLE_REFERENCE_K, temperature_k
        )
    width = _ORACLE_LIQUIDUS_K - _ORACLE_SOLIDUS_K
    mushy_sensible = _oracle_gauss_integral(
        _oracle_mushy_cp, _ORACLE_SOLIDUS_K, temperature_k
    )
    latent = _ORACLE_LATENT_J_KG * (temperature_k - _ORACLE_SOLIDUS_K) / width
    return (
        _oracle_gauss_integral(
            _oracle_solid_cp, _ORACLE_REFERENCE_K, _ORACLE_SOLIDUS_K
        )
        + mushy_sensible
        + latent
    )


class In625LpbfThermalScreening(unittest.TestCase):
    def test_alias_revision_and_source_scope(self):
        snapshots = [thermal_screening_material(name) for name in
                     ("IN625", "Inconel 625", "inconel-625", " in625 ")]
        self.assertTrue(all(snapshot == snapshots[0] for snapshot in snapshots))
        snapshot = snapshots[0]
        self.assertEqual(snapshot["materialId"], "in625")
        self.assertEqual(snapshot["validationStatus"], "unvalidated-literature-model-screening")
        self.assertEqual(snapshot["temperatureCoverage_K"], [273.15, LIQUIDUS_K])
        self.assertIn("10.1007/s11663-020-01808-w", snapshot["source"])
        self.assertIn("Appendix B", snapshot["sourceLocators"]["solidCpAndConductivity"])
        digest = snapshot.pop("materialRevisionSha256")
        encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode("utf-8")
        self.assertEqual(digest, hashlib.sha256(encoded).hexdigest())
        self.assertEqual(len(digest), 64)

    def test_source_equations_and_energy_across_melting(self):
        room = in625_lpbf_thermal_at_kelvin(273.15)
        self.assertEqual(room["materialRevisionSha256"], thermal_screening_material("IN625")["materialRevisionSha256"])
        self.assertAlmostEqual(room["thermalConductivity_W_mK"], 4.93 + .01575*273.15)
        self.assertAlmostEqual(room["specificHeat_J_kgK"],
                               362 + .125*273.15 + .0001741*273.15**2 - 7.527126e-8*273.15**3)
        self.assertEqual(room["specificEnthalpy_J_kg"], 0)
        solid = in625_lpbf_thermal_at_kelvin(SOLIDUS_K)
        liquid = in625_lpbf_thermal_at_kelvin(LIQUIDUS_K)
        self.assertEqual(solid["liquidFraction"], 0)
        self.assertEqual(liquid["liquidFraction"], 1)
        self.assertEqual(liquid["specificHeat_J_kgK"], 700)
        self.assertEqual(liquid["thermalConductivity_W_mK"], 30)
        expected_mushy = (solid["specificHeat_J_kgK"] + 700)/2*(LIQUIDUS_K-SOLIDUS_K) + LATENT_HEAT_J_KG
        self.assertAlmostEqual(liquid["specificEnthalpy_J_kg"]-solid["specificEnthalpy_J_kg"], expected_mushy)
        temperatures = [273.15, 500, 1000, SOLIDUS_K, (SOLIDUS_K+LIQUIDUS_K)/2, LIQUIDUS_K]
        enthalpies = [thermal_screening_at("in625", t)["specificEnthalpy_J_kg"] for t in temperatures]
        self.assertTrue(all(b > a for a, b in zip(enthalpies, enthalpies[1:])))
        midpoint = thermal_screening_at("in625", (SOLIDUS_K+LIQUIDUS_K)/2)
        self.assertEqual(midpoint["liquidFraction"], .5)
        self.assertAlmostEqual(midpoint["effectiveHeatCapacity_J_kgK"] - midpoint["specificHeat_J_kgK"],
                               LATENT_HEAT_J_KG/(LIQUIDUS_K-SOLIDUS_K))

    def test_independent_quadrature_oracle_for_bounded_enthalpy(self):
        """Check the model's piecewise enthalpy against independently integrated Cp.

        This verifies implementation mathematics for the stated literature model
        only; it does not qualify the source inputs or establish physical validity.
        The 1e-6 J/kg absolute tolerance is much smaller than the 290 kJ/kg latent
        term and accommodates floating-point quadrature/integration roundoff.
        """
        self.assertEqual(_ORACLE_REFERENCE_K, 273.15)
        snapshot = thermal_screening_material("IN625")
        self.assertEqual(snapshot["temperatureCoverage_K"],
                         [_ORACLE_REFERENCE_K, _ORACLE_LIQUIDUS_K])
        self.assertEqual(snapshot["solidus_K"], _ORACLE_SOLIDUS_K)
        self.assertEqual(snapshot["liquidus_K"], _ORACLE_LIQUIDUS_K)
        self.assertEqual(snapshot["latentHeat_J_kg"], _ORACLE_LATENT_J_KG)
        self.assertEqual(snapshot["validationStatus"],
                         "unvalidated-literature-model-screening")

        width = _ORACLE_LIQUIDUS_K - _ORACLE_SOLIDUS_K
        temperatures = [
            _ORACLE_REFERENCE_K, 500.0, 1000.0,
            _ORACLE_SOLIDUS_K - 1.0, _ORACLE_SOLIDUS_K,
            *(_ORACLE_SOLIDUS_K + width*f for f in (0.05, 0.2, 0.5, 0.8, 0.95)),
            _ORACLE_LIQUIDUS_K,
        ]
        results = [thermal_screening_at("IN625", temperature) for temperature in temperatures]
        for temperature, result in zip(temperatures, results):
            with self.subTest(temperature_K=temperature):
                self.assertAlmostEqual(
                    result["specificEnthalpy_J_kg"],
                    _oracle_specific_enthalpy(temperature),
                    delta=_ORACLE_ABS_TOL_J_KG,
                )

        # H is continuous across the solidus and liquidus. Reconstruct the
        # same endpoint from each one-sided interval using independently
        # integrated sensible Cp and the declared latent fraction.
        epsilon_k = 1e-3
        solidus_below = thermal_screening_at("IN625", _ORACLE_SOLIDUS_K-epsilon_k)
        solidus_at = thermal_screening_at("IN625", _ORACLE_SOLIDUS_K)
        solidus_above = thermal_screening_at("IN625", _ORACLE_SOLIDUS_K+epsilon_k)
        solidus_left_limit = (
            solidus_below["specificEnthalpy_J_kg"]
            + _oracle_gauss_integral(
                _oracle_solid_cp, _ORACLE_SOLIDUS_K-epsilon_k, _ORACLE_SOLIDUS_K
            )
        )
        solidus_right_limit = (
            solidus_above["specificEnthalpy_J_kg"]
            - _oracle_gauss_integral(
                _oracle_mushy_cp, _ORACLE_SOLIDUS_K, _ORACLE_SOLIDUS_K+epsilon_k
            )
            - _ORACLE_LATENT_J_KG*epsilon_k/width
        )
        self.assertAlmostEqual(solidus_left_limit, solidus_at["specificEnthalpy_J_kg"],
                               delta=_ORACLE_ABS_TOL_J_KG)
        self.assertAlmostEqual(solidus_right_limit, solidus_at["specificEnthalpy_J_kg"],
                               delta=_ORACLE_ABS_TOL_J_KG)

        liquidus_below = thermal_screening_at("IN625", _ORACLE_LIQUIDUS_K-epsilon_k)
        liquidus_at = thermal_screening_at("IN625", _ORACLE_LIQUIDUS_K)
        liquidus_left_limit = (
            liquidus_below["specificEnthalpy_J_kg"]
            + _oracle_gauss_integral(
                _oracle_mushy_cp, _ORACLE_LIQUIDUS_K-epsilon_k, _ORACLE_LIQUIDUS_K
            )
            + _ORACLE_LATENT_J_KG*epsilon_k/width
        )
        self.assertAlmostEqual(liquidus_left_limit, liquidus_at["specificEnthalpy_J_kg"],
                               delta=_ORACLE_ABS_TOL_J_KG)

        # The melt interval contains both sensible enthalpy and the full
        # 290 kJ/kg latent contribution, partitioned linearly by liquid fraction.
        solidus_h = solidus_at["specificEnthalpy_J_kg"]
        for fraction in (0.05, 0.2, 0.5, 0.8, 1.0):
            temperature = _ORACLE_SOLIDUS_K + fraction*width
            result = thermal_screening_at("IN625", temperature)
            sensible = _oracle_gauss_integral(_oracle_mushy_cp, _ORACLE_SOLIDUS_K, temperature)
            expected_latent = _ORACLE_LATENT_J_KG*fraction
            actual_latent = result["specificEnthalpy_J_kg"] - solidus_h - sensible
            with self.subTest(latent_fraction=fraction):
                self.assertAlmostEqual(actual_latent, expected_latent,
                                       delta=_ORACLE_ABS_TOL_J_KG)

        # Strict monotonicity is checked densely across both branches.
        ordered_temperatures = np.linspace(_ORACLE_REFERENCE_K, _ORACLE_LIQUIDUS_K, 257)
        enthalpies = [
            thermal_screening_at("IN625", float(temperature))["specificEnthalpy_J_kg"]
            for temperature in ordered_temperatures
        ]
        self.assertTrue(all(right > left for left, right in zip(enthalpies, enthalpies[1:])))

        # Verify dH/dT against independently evaluated Cp, away from the
        # piecewise join where a centered difference would cross branches.
        delta_k = 1e-3
        for temperature in (900.0, _ORACLE_SOLIDUS_K+0.4*width,
                            _ORACLE_SOLIDUS_K+0.7*width):
            below = thermal_screening_at("IN625", temperature-delta_k)["specificEnthalpy_J_kg"]
            above = thermal_screening_at("IN625", temperature+delta_k)["specificEnthalpy_J_kg"]
            finite_difference_cp = (above-below)/(2*delta_k)
            expected_cp = (
                _oracle_solid_cp(temperature) if temperature < _ORACLE_SOLIDUS_K
                else _oracle_mushy_cp(temperature) + _ORACLE_LATENT_J_KG/width
            )
            with self.subTest(derivative_temperature_K=temperature):
                self.assertAlmostEqual(finite_difference_cp, expected_cp, delta=1e-3)

    def test_data_gate_and_locked_four_alloy_boundary(self):
        for name in ("IN718", "unknown", "IN625;in718", "", None):
            with self.subTest(name=name), self.assertRaises(ValueError):
                thermal_screening_material(name)
            with self.subTest(name=name), self.assertRaises(ValueError):
                thermal_screening_at(name, 300)
        for value in (273.14, LIQUIDUS_K+.01, float("nan"), math.inf, True, "300"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                thermal_screening_at("IN625", value)
        for name in ("Inconel 625", "IN625"):
            with self.assertRaisesRegex(ValueError, "thermophysical data missing"):
                material(name)
        item = next(item for item in catalog() if item["name"] == "Inconel 625")
        self.assertFalse(item["available"])
        self.assertTrue(item["thermalOnlyAvailable"])
        names = [item["name"] for item in catalog()]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(names[:4], ["Ti-6Al-4V", "316L Stainless Steel", "AlSi10Mg", "Inconel 718"])
        self.assertEqual(FOUR_ALLOY_IDS, ("ti6al4v", "ss316l", "alsi10mg", "in718"))


if __name__ == "__main__":
    unittest.main()
