"""Peak output must come from the selected heat-source field.

Since the 2026-10-06 tier-2 bump the reported peak is the axial (y = z = 0) maximum of the selected
field, max(T(0,0,0), T(x_peak,0,0)), because the regularised moving-source fields peak behind the
beam centre at high speed. Every sample is recorded from the selected field only, so a peak taken
from another kernel would not match.
"""
import unittest
from unittest.mock import patch

import lpbf_thermal_solver as solver


class PeakTemperatureConsistency(unittest.TestCase):
    def _assert_peak(self, result, center_values, axial_values):
        self.assertTrue(center_values, "the selected field was not sampled at the beam center")
        peak = result["hydrodynamicsAndRecoil"]["peakTemperature_C"]
        self.assertGreaterEqual(peak, round(center_values[0], 1))
        # The reported peak is the axial maximum of the same field (ternary refinement: within rounding).
        self.assertAlmostEqual(peak, round(max(axial_values), 1), delta=0.11)
        offset_um = result["meltPoolGeometry"]["peakOffset_um"]
        self.assertLessEqual(offset_um, 0.0)

    def _record(self, heat_source, field_owner, method_name):
        center_values, axial_values = [], []
        original = getattr(field_owner, method_name)

        def recording_temperature(field, x_m, y_m, z_m):
            value = original(field, x_m, y_m, z_m)
            if y_m == 0.0 and z_m == 0.0:
                axial_values.append(float(value))
                if x_m == 0.0:
                    center_values.append(float(value))
            return value

        with patch.object(field_owner, method_name, recording_temperature):
            result = solver.calculate_meltpool_physics(
                "Inconel 718", 285.0, 960.0, 80.0,
                preheat_temp_C=80.0,
                heat_source=heat_source,
            )
        self._assert_peak(result, center_values, axial_values)

    def test_rosenthal_peak_is_evaluated_from_the_selected_field(self):
        original = solver.rosenthal_temperature_C
        center_values, axial_values = [], []

        def recording_rosenthal(x_m, y_m, z_m, *args):
            value = original(x_m, y_m, z_m, *args)
            if y_m == 0.0 and z_m == 0.0:
                axial_values.append(float(value))
                if x_m == 0.0:
                    center_values.append(float(value))
            return value

        with patch.object(solver, "rosenthal_temperature_C", recording_rosenthal):
            result = solver.calculate_meltpool_physics(
                "Inconel 718", 285.0, 960.0, 80.0,
                preheat_temp_C=80.0,
                heat_source="rosenthal",
            )
        self._assert_peak(result, center_values, axial_values)
        self.assertLess(result["meltPoolGeometry"]["peakOffset_um"], 0.0)

    def test_eagar_tsai_peak_is_evaluated_from_the_selected_field(self):
        self._record("eagar-tsai", solver.EagarTsaiField, "temperature_C")

    def test_goldak_peak_is_evaluated_from_the_selected_field(self):
        self._record("goldak", solver.GoldakField, "temperature_C")


if __name__ == "__main__":
    unittest.main()
