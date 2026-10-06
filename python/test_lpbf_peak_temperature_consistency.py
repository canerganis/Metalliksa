"""Peak output must use the same beam-center field as the selected heat source."""
import unittest
from unittest.mock import patch

import lpbf_thermal_solver as solver


class PeakTemperatureConsistency(unittest.TestCase):
    def _assert_peak_matches_center_field(self, heat_source, field_owner, method_name):
        center_values = []
        original = getattr(field_owner, method_name)

        def recording_temperature(field, x_m, y_m, z_m):
            value = original(field, x_m, y_m, z_m)
            if x_m == 0.0 and y_m == 0.0 and z_m == 0.0:
                center_values.append(float(value))
            return value

        with patch.object(field_owner, method_name, recording_temperature):
            result = solver.calculate_meltpool_physics(
                "Inconel 718", 285.0, 960.0, 80.0,
                preheat_temp_C=80.0,
                heat_source=heat_source,
            )

        self.assertTrue(center_values, "the selected field was not sampled at the beam center")
        self.assertEqual(
            result["hydrodynamicsAndRecoil"]["peakTemperature_C"],
            round(center_values[0], 1),
        )

    def test_rosenthal_peak_is_evaluated_from_the_selected_field(self):
        original = solver.rosenthal_temperature_C
        center_values = []

        def recording_rosenthal(x_m, y_m, z_m, *args):
            value = original(x_m, y_m, z_m, *args)
            if x_m == 0.0 and y_m == 0.0 and z_m == 0.0:
                center_values.append(float(value))
            return value

        with patch.object(solver, "rosenthal_temperature_C", recording_rosenthal):
            result = solver.calculate_meltpool_physics(
                "Inconel 718", 285.0, 960.0, 80.0,
                preheat_temp_C=80.0,
                heat_source="rosenthal",
            )

        self.assertTrue(center_values, "Rosenthal field was not sampled at the beam center")
        self.assertEqual(
            result["hydrodynamicsAndRecoil"]["peakTemperature_C"],
            round(center_values[0], 1),
        )

    def test_eagar_tsai_peak_remains_the_selected_field_center(self):
        self._assert_peak_matches_center_field("eagar-tsai", solver.EagarTsaiField, "temperature_C")

    def test_goldak_peak_remains_the_selected_field_center(self):
        self._assert_peak_matches_center_field("goldak", solver.GoldakField, "temperature_C")


if __name__ == "__main__":
    unittest.main()
