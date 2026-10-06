import math
import unittest

from lpbf_ss304_support_material import (
    DENSITY_KG_M3,
    MAXIMUM_TEMPERATURE_K,
    REFERENCE_TEMPERATURE_K,
    ss304_support_thermal_at_kelvin,
    ss304_support_thermal_fields,
    ss304_support_thermal_snapshot,
)


class Ss304SupportMaterialTests(unittest.TestCase):
    def test_snapshot_is_versioned_and_warns_against_specimen_identity(self):
        first = ss304_support_thermal_snapshot()
        second = ss304_support_thermal_snapshot()
        self.assertEqual(first, second)
        self.assertEqual(first["materialId"], "ss304")
        self.assertEqual(first["validationStatus"], "unvalidated-literature-model-screening")
        self.assertIn("holder's material certificate", first["uncertaintyNote"])
        self.assertEqual(len(first["materialRevisionSha256"]), 64)

    def test_reference_temperature_has_zero_enthalpy_and_positive_properties(self):
        result = ss304_support_thermal_at_kelvin(REFERENCE_TEMPERATURE_K)
        self.assertEqual(result["density_kg_m3"], DENSITY_KG_M3)
        self.assertEqual(result["specificEnthalpy_J_kg"], 0.0)
        self.assertGreater(result["specificHeat_J_kgK"], 0)
        self.assertGreater(result["thermalConductivity_W_mK"], 0)

    def test_enthalpy_derivative_matches_heat_capacity(self):
        temperature = 1000.0
        delta = 1e-3
        lower = ss304_support_thermal_at_kelvin(temperature - delta)["specificEnthalpy_J_kg"]
        upper = ss304_support_thermal_at_kelvin(temperature + delta)["specificEnthalpy_J_kg"]
        midpoint_cp = ss304_support_thermal_at_kelvin(temperature)["specificHeat_J_kgK"]
        self.assertTrue(math.isclose((upper - lower) / (2 * delta), midpoint_cp, rel_tol=1e-8))

    def test_vectorized_fields_match_scalar_evaluation(self):
        temperatures = [REFERENCE_TEMPERATURE_K, 700.0, 1200.0]
        density, cp, conductivity, enthalpy = ss304_support_thermal_fields(temperatures)
        for index, temperature in enumerate(temperatures):
            scalar = ss304_support_thermal_at_kelvin(temperature)
            self.assertEqual(density[index], scalar["density_kg_m3"])
            self.assertEqual(cp[index], scalar["specificHeat_J_kgK"])
            self.assertEqual(conductivity[index], scalar["thermalConductivity_W_mK"])
            self.assertAlmostEqual(enthalpy[index], scalar["specificEnthalpy_J_kg"], places=9)

    def test_temperature_bounds_are_fail_closed(self):
        self.assertGreater(
            ss304_support_thermal_at_kelvin(MAXIMUM_TEMPERATURE_K)["specificEnthalpy_J_kg"], 0
        )
        for invalid in (REFERENCE_TEMPERATURE_K - 1, MAXIMUM_TEMPERATURE_K + 1, math.inf, math.nan, True):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                ss304_support_thermal_at_kelvin(invalid)
        for invalid in ([REFERENCE_TEMPERATURE_K, MAXIMUM_TEMPERATURE_K + 1], [True, False]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                ss304_support_thermal_fields(invalid)


if __name__ == "__main__":
    unittest.main()
