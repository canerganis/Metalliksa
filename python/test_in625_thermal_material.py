"""Checks for the source-bounded, unregistered IN625 solid thermal table."""

import unittest

from in625_thermal_material import in625_solid_thermal_at_celsius


class In625SolidThermalTable(unittest.TestCase):
    def test_tabulated_values_and_linear_interpolation(self):
        self.assertEqual(in625_solid_thermal_at_celsius(21), {
            "thermal_conductivity_W_mK": 9.8,
            "specific_heat_J_kgK": 410.0,
        })
        at_38 = in625_solid_thermal_at_celsius(38)
        self.assertEqual(at_38["thermal_conductivity_W_mK"], 10.1)
        self.assertAlmostEqual(at_38["specific_heat_J_kgK"], 410 + (427 - 410) * 17 / 72)
        self.assertEqual(in625_solid_thermal_at_celsius(982), {
            "thermal_conductivity_W_mK": 25.2,
            "specific_heat_J_kgK": 645.0,
        })

    def test_unavailable_outside_common_solid_range(self):
        for temperature in (-18.01, 982.01, 1290, float("nan"), float("inf"), True):
            with self.subTest(temperature=temperature), self.assertRaises(ValueError):
                in625_solid_thermal_at_celsius(temperature)


if __name__ == "__main__":
    unittest.main()
