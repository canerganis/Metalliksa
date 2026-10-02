"""Synthetic section oracles; these fields are not measured LPBF evidence."""
import unittest

import numpy as np

import lpbf_peak


class FixedEventCrossSection(unittest.TestCase):
    def analytic_field(self):
        # At x=1 um the exact liquidus is |y| + |z+2| = 3 um.
        # Piecewise linear temperatures make its edge crossings exact.
        x, y, z = np.meshgrid(np.array([0., 2., 4.]),
                              np.arange(-4., 5., 2.),
                              np.arange(-6., 3., 2.), indexing="ij")
        xyz = np.column_stack((x.ravel(), y.ravel(), z.ravel())) * 1e-6
        temperature = 1000. + 100.*(3. + .5*(x-1.) - abs(y) - abs(z+2.))
        return xyz, temperature.ravel()

    def observe(self, xyz, temperature, x=1e-6, **kwargs):
        function = getattr(lpbf_peak, "fixed_event_liquidus_cross_section", None)
        self.assertTrue(callable(function), "Fixed-event section operator is missing")
        return function(xyz, temperature, x, 2e-6, 1000., **kwargs)

    def test_analytic_diamond_at_interpolated_physical_plane(self):
        xyz, temperature = self.analytic_field()
        before_xyz, before_temperature = xyz.copy(), temperature.copy()
        result = self.observe(xyz, temperature)
        self.assertEqual(result["status"], "thermal-proxy")
        self.assertAlmostEqual(result["width_um"], 6.)
        self.assertAlmostEqual(result["depth_um"], 5.)
        self.assertAlmostEqual(result["xPosition_m"], 1e-6)
        self.assertEqual(result["sourcePlaneIndices"], [0, 1])
        self.assertAlmostEqual(result["xInterpolationFraction"], .5)
        self.assertFalse(result["topBoundaryMolten"])
        self.assertFalse(result["experimentalValidation"])
        self.assertIn("single accepted event", result["temporalSelection"])
        self.assertEqual(result["surfaceTreatment"], "no-extrapolation")
        np.testing.assert_array_equal(xyz, before_xyz)
        np.testing.assert_array_equal(temperature, before_temperature)

    def test_exact_plane_and_shifted_substrate_interface(self):
        xyz, temperature = self.analytic_field()
        result = self.observe(xyz, temperature, x=2e-6,
                              substrate_interface_z_m=-1e-6)
        self.assertEqual(result["status"], "thermal-proxy")
        self.assertAlmostEqual(result["width_um"], 7.)
        self.assertAlmostEqual(result["depth_um"], 4.5)
        self.assertEqual(result["sourcePlaneIndices"], [1, 1])

    def test_other_planes_do_not_contribute_to_selected_contour(self):
        xyz, temperature = self.analytic_field()
        temperature[xyz[:, 0] == 4e-6] = 3000.
        result = self.observe(xyz, temperature)
        self.assertEqual(result["status"], "thermal-proxy")
        self.assertAlmostEqual(result["width_um"], 6.)
        self.assertAlmostEqual(result["depth_um"], 5.)

    def test_top_molten_is_reported_without_surface_extrapolation(self):
        xyz, _ = self.analytic_field()
        # Open at the top: the deepest crossing is exactly z=-3 um.
        temperature = 1000. + 100.*np.minimum(
            3.-abs(xyz[:, 1]*1e6), xyz[:, 2]*1e6+3.)
        result = self.observe(xyz, temperature)
        self.assertEqual(result["status"], "thermal-proxy")
        self.assertTrue(result["topBoundaryMolten"])
        self.assertAlmostEqual(result["width_um"], 6.)
        self.assertAlmostEqual(result["depth_um"], 3.)
        self.assertEqual(result["surfaceTreatment"], "no-extrapolation")

    def test_no_substrate_penetration_has_zero_depth(self):
        xyz, temperature = self.analytic_field()
        result = self.observe(xyz, temperature, substrate_interface_z_m=-6e-6)
        self.assertEqual(result["status"], "thermal-proxy")
        self.assertEqual(result["depth_um"], 0.)

    def test_no_melt_and_unresolved_threshold_cell(self):
        xyz, temperature = self.analytic_field()
        self.assertEqual(self.observe(xyz, np.full_like(temperature, 900.))["status"],
                         "no-melt")
        temperature[:] = 900.
        temperature[(xyz[:, 1] == 0.) & (xyz[:, 2] == -2e-6)] = 1000.
        result = self.observe(xyz, temperature)
        self.assertEqual(result["status"], "inconclusive")
        self.assertIsNone(result["width_um"])

    def test_lateral_and_bottom_contact_are_inconclusive(self):
        xyz, temperature = self.analytic_field()
        for mask in (xyz[:, 1] == -4e-6, xyz[:, 1] == 4e-6,
                     xyz[:, 2] == -6e-6):
            with self.subTest(boundary=xyz[mask][0].tolist()):
                field = temperature.copy()
                field[mask] = 2000.
                result = self.observe(xyz, field)
                self.assertEqual(result["status"], "inconclusive")
                self.assertIsNone(result["width_um"])
                self.assertIsNone(result["depth_um"])

    def test_outside_center_support_does_not_extrapolate(self):
        xyz, temperature = self.analytic_field()
        for x in (-1e-12, 4e-6+1e-12):
            with self.subTest(x=x):
                result = self.observe(xyz, temperature, x=x)
                self.assertEqual(result["status"], "inconclusive")
                self.assertIsNone(result["width_um"])

    def test_invalid_or_degenerate_cartesian_fields_are_inconclusive(self):
        xyz, temperature = self.analytic_field()
        duplicate = xyz.copy()
        duplicate[0] = duplicate[1]
        shifted = xyz.copy()
        shifted[0, 0] += 1e-7
        nonfinite = temperature.copy()
        nonfinite[0] = np.nan
        only_one_x = xyz[:, 0] == 0.
        for coords, field in ((duplicate, temperature), (shifted, temperature),
                              (xyz[:-1], temperature[:-1]),
                              (xyz[::-1], temperature[::-1]),
                              (xyz, nonfinite), (xyz, temperature[:-1]),
                              (xyz[only_one_x], temperature[only_one_x])):
            with self.subTest(shape=coords.shape):
                result = self.observe(coords, field)
                self.assertEqual(result["status"], "inconclusive")
                self.assertIsNone(result["width_um"])

    def test_invalid_mesh_and_physical_scalars_are_inconclusive(self):
        xyz, temperature = self.analytic_field()
        function = getattr(lpbf_peak, "fixed_event_liquidus_cross_section", None)
        self.assertTrue(callable(function), "Fixed-event section operator is missing")
        for x, dx, liquidus, interface in ((1e-6, 0., 1000., 0.),
                                           (1e-6, 1e-6, 1000., 0.),
                                           (np.nan, 2e-6, 1000., 0.),
                                           (1e-6, 2e-6, 0., 0.),
                                           (1e-6, 2e-6, 1000., np.inf)):
            with self.subTest(dx=dx, x=x):
                result = function(xyz, temperature, x, dx, liquidus, interface)
                self.assertEqual(result["status"], "inconclusive")


if __name__ == "__main__":
    unittest.main()
