import math
import unittest

from lpbf_thermal_solver import calculate_meltpool_physics


class TestLpbfThermalSolverInputContract(unittest.TestCase):
    def test_rejects_unrecognized_heat_source_instead_of_substituting_rosenthal(self):
        with self.assertRaisesRegex(ValueError, "Unsupported LPBF heat source"):
            calculate_meltpool_physics(
                "Inconel 718", 285.0, 960.0, 80.0, heat_source="rosenthal-ish"
            )

    def test_rejects_wavelength_without_a_resolved_material_absorptivity(self):
        with self.assertRaisesRegex(ValueError, "Unsupported LPBF laser wavelength"):
            calculate_meltpool_physics(
                "Inconel 718", 285.0, 960.0, 80.0, laser_wavelength="Blue_450nm"
            )

    def test_uses_material_green_absorptivity_for_green_laser(self):
        result = calculate_meltpool_physics(
            "Inconel 718", 285.0, 960.0, 80.0, laser_wavelength="Green_515nm"
        )
        self.assertEqual(
            result["processParameters"]["fabbroAbsorptivity"],
            0.58,
        )

    def test_preserves_sub_ten_positive_inputs_and_uses_gaussian_peak_irradiance(self):
        result = calculate_meltpool_physics(
            "Inconel 718",
            laser_power_W=5.0,
            scan_speed_mm_s=5.0,
            beam_diameter_um=5.0,
            layer_thickness_um=40.0,
            hatch_spacing_um=100.0,
            heat_source="rosenthal",
        )
        process = result["processParameters"]
        self.assertEqual(process["laserPower_W"], 5.0)
        self.assertEqual(process["scanSpeed_mm_s"], 5.0)
        self.assertEqual(process["beamDiameter_um"], 5.0)
        self.assertEqual(process["volumetricEnergyDensity_J_mm3"], 250.0)
        self.assertEqual(process["linearEnergyDensity_J_m"], 1000.0)
        expected_peak = 8.0 * 5.0 / (math.pi * (5e-6 ** 2)) * 1e-10
        self.assertEqual(process["peakIntensity_MW_cm2"], round(expected_peak, 3))

    def test_rejects_nonphysical_or_nonfinite_process_dimensions(self):
        base = dict(
            material_name="Inconel 718",
            laser_power_W=285.0,
            scan_speed_mm_s=960.0,
            beam_diameter_um=80.0,
        )
        for field, value in (
            ("laser_power_W", 0.0),
            ("scan_speed_mm_s", math.nan),
            ("beam_diameter_um", -1.0),
            ("layer_thickness_um", -40.0),
            ("hatch_spacing_um", math.inf),
        ):
            with self.subTest(field=field, value=value):
                with self.assertRaisesRegex(ValueError, "finite and positive"):
                    calculate_meltpool_physics(**dict(base, **{field: value}))


if __name__ == "__main__":
    unittest.main()
