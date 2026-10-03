"""Bare-plate reference physics and location-specific thermal section checks."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np

import lpbf_peak
from lpbf_peak import (midtrack_bare_plate_section,
                       interpolated_midtrack_bare_plate_section,
                       rectangular_corridor_section_samples,
                       rectangular_corridor_section_observations)
from lpbf_core_physics import calculate_mesh_domain, scan_segments
from lpbf_evidence import resource_estimate
from lpbf_simulation import run, validate


CASE = {"mode": "standard", "backend": "reference", "surfaceMode": "bare-plate",
        "sourcePenetration_um": 40, "material": "Inconel 718", "power_W": 80,
        "speed_mm_s": 1200, "mesh_um": 40, "maxDt_s": 2e-7,
        "trackLength_um": 200, "cooling_s": 2e-5, "dwell_s": 0}


class BarePlate(unittest.TestCase):
    def test_midpoint_optical_operator_uses_widest_and_deepest_extent(self):
        axis = np.array([-1.5, -.5, .5, 1.5])
        z = np.array([-2.5, -1.5, -.5])
        molten = np.zeros((4, 4, 3), dtype=bool)
        molten[1, 0, 1] = True
        molten[1, 3, 1] = True
        molten[1, 2, 0] = True
        molten[2, 0, 0] = True  # Another plane must not widen/deepen this cut.
        section = midtrack_bare_plate_section(axis, z, molten, 1.)
        self.assertEqual(section["status"], "thermal-proxy")
        self.assertEqual(section["width_um"], 4e6)
        self.assertEqual(section["depth_um"], 3e6)
        self.assertEqual(section["sampleCells"], 3)
        self.assertEqual(section["planeOffset_um"], -5e5)
        self.assertFalse(section["midpointResolvedWithinQuarterCell"])

    def test_bare_plate_requires_explicit_model_inputs(self):
        for patch in ({"sourcePenetration_um": None}, {"backend": "auto"},
                      {"tracks": 2}, {"layers": 2}, {"scanAngle_deg": 45},
                      {"measurements": [{"width_um": 1, "depth_um": 1, "source": "synthetic"}]}):
            with self.assertRaises(ValueError):
                validate({**CASE, **patch})
        with self.assertRaises(ValueError):
            validate({**CASE, "spotD4sigma_um": 67})

    def test_reference_bare_plate_energy_mass_and_unavailable_experiment(self):
        result = run(CASE)
        section = result["midTrackCrossSection"]
        self.assertEqual(section["status"], "thermal-proxy")
        self.assertGreater(section["width_um"], 0)
        self.assertGreater(section["depth_um"], 0)
        self.assertLess(result["energyBalance"]["relativeError"], .01)
        self.assertEqual(result["massBalance"]["deposited_kg"], 0)
        self.assertEqual(result["experimentalComparison"]["status"], "unavailable")
        self.assertEqual(result["coreContract"]["actualBackend"], "numpy-reference")

    def test_powder_mode_default_retains_numerical_path(self):
        powder = {"mode": "standard", "backend": "reference", "power_W": 40,
                  "mesh_um": 40, "trackLength_um": 200, "cooling_s": .0001, "dwell_s": 0}
        original = run(powder)
        explicit = run({**powder, "surfaceMode": "powder-layer"})
        self.assertEqual(original["metrics"], explicit["metrics"])
        self.assertEqual(original["energyBalance"], explicit["energyBalance"])
        self.assertIsNone(original["midTrackCrossSection"])

    def test_rectangular_corridor_geometry_preserves_full_scan_and_energy(self):
        rectangular = {**CASE, "barePlateGeometry": "rectangular-corridor",
                       "trackLength_um": 600, "maxDt_s": 1e-6}
        result = run(rectangular)
        self.assertAlmostEqual(result["scanPath"][0]["start"][0], -300e-6)
        self.assertAlmostEqual(result["scanPath"][0]["end"][0], 300e-6)
        self.assertEqual(result["scanPath"][0]["start"][1], 0.0)
        self.assertEqual(result["scanPath"][0]["end"][1], 0.0)
        observations = result["barePlateSectionObservations"]
        self.assertEqual(len(observations), 2)
        self.assertTrue(all(record["status"] == "unsupported" for record in observations))
        self.assertEqual(len({record["recordId"] for record in observations}), 2)
        domain = calculate_mesh_domain(validate(rectangular)[0])
        self.assertGreater(domain["nx"], domain["ny"])
        self.assertEqual(result["discretization"]["cells"], domain["nx"]*domain["ny"]*domain["nz"])
        self.assertEqual(result["discretization"]["requestedCorridorWidth_um"], 480)
        self.assertAlmostEqual(result["discretization"]["effectiveCorridorWidth_um"],
                               domain["effective_span_y"]*1e6)
        self.assertLess(result["energyBalance"]["relativeError"], .01)
        self.assertEqual(result["midTrackCrossSection"]["status"], "thermal-proxy")
        with patch("lpbf_simulation.rectangular_corridor_section_observations", return_value=[]):
            no_observations = run(rectangular)
        for key in ("energyBalance", "discretization", "thermalHistory"):
            self.assertEqual(result[key], no_observations[key])

    def test_rectangular_corridor_sections_keep_exact_positions_and_interpolate_off_grid(self):
        axis_x = np.arange(-.005, .0091, .002)
        axis_y = np.arange(-.01, .0101, .002)
        z = np.arange(-.01, .0021, .002)
        requests = rectangular_corridor_section_samples(axis_x, -.005, .01)
        self.assertEqual([row["distanceFromScanStart_mm"] for row in requests], [4.9, 6.0])
        self.assertAlmostEqual(requests[0]["xCoordinate_m"], -.0001)
        self.assertAlmostEqual(requests[1]["xCoordinate_m"], .001)
        self.assertEqual(requests[0]["interpolationOperator"],
                         "linear-interpolation-between-accepted-peak-temperature-planes-v1")
        self.assertAlmostEqual(requests[0]["interpolationFraction"], .45)
        self.assertEqual(requests[1]["interpolationOperator"], "exact-cell-center")
        self.assertEqual(len({row["recordId"] for row in requests}), 2)
        self.assertTrue(all("one simulated" in row["scanLineScope"] for row in requests))

        left = np.full((len(axis_y), len(z)), 300.)
        right = np.full_like(left, 300.)
        for iy, y_value in enumerate(axis_y):
            if abs(y_value) <= .006:
                left[iy, z >= -.008] = 1800.
            if abs(y_value) <= .002:
                right[iy, z >= -.004] = 1800.
        fields = {2: left, 3: right}
        observations = rectangular_corridor_section_observations(axis_y, z, fields, requests, .002, 1000.)
        off_grid, exact = observations
        expected_field = .55*left+.45*right
        expected = interpolated_midtrack_bare_plate_section(axis_y, z, expected_field, .002, 1000., 0.)
        self.assertEqual(off_grid["status"], "thermal-proxy")
        self.assertEqual(exact["status"], "thermal-proxy")
        self.assertAlmostEqual(off_grid["width_um"], expected["width_um"])
        self.assertAlmostEqual(off_grid["depth_um"], expected["depth_um"])
        self.assertNotEqual(off_grid["width_um"], exact["width_um"])
        self.assertNotEqual(off_grid["depth_um"], exact["depth_um"])
        self.assertEqual(off_grid["temporalAggregation"],
                         "accepted-step maximum per source X plane, then spatially interpolated")

    def test_rectangular_corridor_field_artifact_preserves_source_plane_provenance(self):
        self.assertTrue(hasattr(lpbf_peak, "write_rectangular_corridor_section_field_artifact"))
        axis_x = np.arange(-.005, .0091, .002)
        axis_y = np.arange(-.01, .0101, .002)
        z = np.arange(-.01, .0021, .002)
        requests = rectangular_corridor_section_samples(axis_x, -.005, .01)
        left = np.full((len(axis_y), len(z)), 300., dtype=np.float64)
        right = np.full_like(left, 300.)
        for iy, y_value in enumerate(axis_y):
            if abs(y_value) <= .006:
                left[iy, z >= -.008] = 1800.
            if abs(y_value) <= .002:
                right[iy, z >= -.004] = 1800.
        fields = {2: left, 3: right}
        observations = rectangular_corridor_section_observations(
            axis_y, z, fields, requests, .002, 1000.)
        self.assertEqual([row["status"] for row in observations],
                         ["thermal-proxy", "thermal-proxy"])

        with TemporaryDirectory() as directory:
            output = Path(directory) / "corridor-sections.npz"
            lpbf_peak.write_rectangular_corridor_section_field_artifact(
                output, axis_x, axis_y, z, observations, fields, .002, 1000., 17)
            self.assertEqual(sorted(path.name for path in Path(directory).iterdir()),
                             ["corridor-sections.npz"])
            with np.load(output, allow_pickle=False) as artifact:
                self.assertEqual(set(artifact.files), {
                    "schema_version", "scan_start_x_m", "section_x_m", "section_distance_mm",
                    "temperature_planes_K", "plane_indices", "plane_x_m", "axis_y_m", "z_m",
                    "mesh_m", "liquidus_K", "accepted_step_count",
                    "section_source_plane_indices", "section_interpolation_fraction",
                    "section_interpolation_operator", "section_record_id",
                })
                self.assertEqual(artifact["temperature_planes_K"].dtype, np.dtype(np.float64))
                self.assertEqual(int(artifact["schema_version"]), 1)
                self.assertEqual(float(artifact["scan_start_x_m"]), -.005)
                np.testing.assert_allclose(artifact["section_x_m"], [-.0001, .001])
                np.testing.assert_allclose(artifact["section_distance_mm"], [4.9, 6.0])
                np.testing.assert_array_equal(artifact["temperature_planes_K"],
                                              np.stack([left, right]))
                np.testing.assert_array_equal(artifact["plane_indices"], [2, 3])
                np.testing.assert_array_equal(artifact["plane_x_m"], axis_x[[2, 3]])
                np.testing.assert_array_equal(artifact["axis_y_m"], axis_y)
                np.testing.assert_array_equal(artifact["z_m"], z)
                self.assertEqual(float(artifact["mesh_m"]), .002)
                self.assertEqual(float(artifact["liquidus_K"]), 1000.)
                self.assertEqual(int(artifact["accepted_step_count"]), 17)
                np.testing.assert_array_equal(artifact["section_source_plane_indices"],
                                              [[2, 3], [3, -1]])
                np.testing.assert_allclose(artifact["section_interpolation_fraction"], [.45, 0.])
                np.testing.assert_array_equal(artifact["section_interpolation_operator"],
                                              ["linear-interpolation-between-accepted-peak-temperature-planes-v1",
                                               "exact-cell-center"])
                np.testing.assert_array_equal(artifact["section_record_id"],
                                              ["single-line-x-4p9mm", "single-line-x-6p0mm"])

    def test_rectangular_corridor_field_artifact_rejects_unbound_or_invalid_fields(self):
        self.assertTrue(hasattr(lpbf_peak, "write_rectangular_corridor_section_field_artifact"))
        axis_x = np.arange(-.005, .0091, .002)
        axis_y = np.arange(-.01, .0101, .002)
        z = np.arange(-.01, .0021, .002)
        requests = rectangular_corridor_section_samples(axis_x, -.005, .01)
        left = np.full((len(axis_y), len(z)), 300., dtype=np.float64)
        right = np.full_like(left, 300.)
        for iy, y_value in enumerate(axis_y):
            if abs(y_value) <= .006:
                left[iy, z >= -.008] = 1800.
            if abs(y_value) <= .002:
                right[iy, z >= -.004] = 1800.
        fields = {2: left, 3: right}
        observations = rectangular_corridor_section_observations(
            axis_y, z, fields, requests, .002, 1000.)

        invalid_fields = [
            {3: right},
            {2: np.zeros((len(axis_y)-1, len(z))), 3: right},
            {2: np.full((len(axis_y), len(z)), np.nan), 3: right},
        ]
        unsupported = [dict(row) for row in observations]
        unsupported[0]["status"] = "unsupported"
        with TemporaryDirectory() as directory:
            for index, candidate in enumerate(invalid_fields + [fields]):
                output = Path(directory) / f"invalid-{index}.npz"
                summaries = unsupported if index == len(invalid_fields) else observations
                with self.subTest(candidate=index):
                    with self.assertRaises(ValueError):
                        lpbf_peak.write_rectangular_corridor_section_field_artifact(
                            output, axis_x, axis_y, z, summaries, candidate,
                            .002, 1000., 17)
                    self.assertFalse(output.exists())
            for index, count in enumerate((0, -1, True, 1.5)):
                output = Path(directory) / f"invalid-count-{index}.npz"
                with self.subTest(accepted_step_count=count):
                    with self.assertRaises(ValueError):
                        lpbf_peak.write_rectangular_corridor_section_field_artifact(
                            output, axis_x, axis_y, z, observations, fields,
                            .002, 1000., count)
                    self.assertFalse(output.exists())

    def test_rectangular_corridor_sections_report_unsupported_without_extrapolation(self):
        axis_x = np.array([-.003, -.002, -.001])
        too_short = rectangular_corridor_section_samples(axis_x, -.005, .005)
        self.assertTrue(all(row["status"] == "unsupported" for row in too_short))
        self.assertIn("outside the represented cell-center X domain", too_short[0]["reason"])
        self.assertIn("beyond the simulated scan length", too_short[1]["reason"])

    def test_rectangular_corridor_10mm_estimates_and_refuses_oversized_fine_meshes(self):
        p, m = validate({**CASE, "barePlateGeometry": "rectangular-corridor",
                         "trackLength_um": 10000, "mesh_um": 20})
        estimate = resource_estimate(p, m)
        self.assertLess(estimate["cells"], 600000)
        for mesh_um in (10, 5):
            p, m = validate({**CASE, "barePlateGeometry": "rectangular-corridor",
                             "trackLength_um": 10000, "mesh_um": mesh_um})
            estimate = resource_estimate(p, m)
            domain = calculate_mesh_domain(p)
            self.assertEqual(estimate["shape"], [domain["nx"], domain["ny"], domain["nz"]])
            self.assertEqual(estimate["cells"], domain["nx"]*domain["ny"]*domain["nz"])
            self.assertGreater(estimate["cells"], 600000)
            segments, _ = scan_segments(p)
            self.assertAlmostEqual(abs(segments[0]["end"][0]-segments[0]["start"][0]), .01)
            with self.assertRaisesRegex(ValueError, r"requires [\d,]+ cells, above the 600000-cell"):
                run({**CASE, "barePlateGeometry": "rectangular-corridor",
                     "trackLength_um": 10000, "mesh_um": mesh_um})

    def test_rectangular_corridor_width_is_explicit_and_defaults_to_twelve_radii(self):
        base = {**CASE, "barePlateGeometry": "rectangular-corridor", "mesh_um": 20,
                "trackLength_um": 10000}
        p, _ = validate(base)
        self.assertEqual(p["corridorWidth_um"], 480)
        default_domain = calculate_mesh_domain(p)
        self.assertEqual(default_domain["ny"], 25)
        self.assertAlmostEqual(default_domain["effective_span_y"], default_domain["ny"]*default_domain["dx"])

        for width_um, expected_ny in ((320, 17), (480, 25), (640, 33)):
            p, m = validate({**base, "corridorWidth_um": width_um})
            domain = calculate_mesh_domain(p)
            estimate = resource_estimate(p, m)
            self.assertEqual(domain["ny"], expected_ny)
            self.assertEqual(estimate["cells"], domain["nx"]*expected_ny*domain["nz"])
            self.assertAlmostEqual(domain["span_y"], width_um*1e-6)
            self.assertAlmostEqual(domain["effective_span_y"], expected_ny*domain["dx"])

        larger_beam, _ = validate({**CASE, "barePlateGeometry": "rectangular-corridor",
                                   "beamDiameter_um": 120})
        self.assertEqual(larger_beam["corridorWidth_um"], 720)

    def test_truncated_gaussian_is_rejected_and_wide_corridors_report_capture(self):
        narrow = {**CASE, "barePlateGeometry": "rectangular-corridor", "mesh_um": 20,
                  "corridorWidth_um": 20, "sourcePenetration_um": 20}
        with self.assertRaisesRegex(ValueError, "Gaussian source capture .* below the 99% minimum"):
            run(narrow)

        for width_um in (320, 480):
            with self.subTest(width_um=width_um):
                result = run({**narrow, "power_W": 40, "sourcePenetration_um": 40,
                              "corridorWidth_um": width_um,
                              "trackLength_um": 200, "maxDt_s": 2e-7})
                diagnostics = result["numericalDiagnostics"]
                self.assertGreaterEqual(diagnostics["minimumCapturedSourceFraction"], 1. / 1.01)
                self.assertLessEqual(diagnostics["maximumSourceRenormalization"], 1.01)

    def test_corridor_width_rejects_other_geometries_invalid_values_and_over_budget_meshes(self):
        with self.assertRaisesRegex(ValueError, "only supported for rectangular-corridor"):
            validate({**CASE, "corridorWidth_um": 480})
        for width in (0, -1, True, float("nan"), float("inf"), "480"):
            with self.assertRaises(ValueError):
                validate({**CASE, "barePlateGeometry": "rectangular-corridor",
                          "corridorWidth_um": width})

        wide = {**CASE, "barePlateGeometry": "rectangular-corridor", "trackLength_um": 10000,
                "mesh_um": 20, "corridorWidth_um": 2000}
        p, m = validate(wide)
        estimate = resource_estimate(p, m)
        self.assertGreater(estimate["cells"], 600000)
        with self.assertRaisesRegex(ValueError, r"requires [\d,]+ cells, above the 600000-cell"):
            run(wide)

    def test_bare_plate_square_default_is_unchanged_by_explicit_square(self):
        implicit = run(CASE)
        explicit = run({**CASE, "barePlateGeometry": "square"})
        self.assertNotIn("barePlateSectionObservations", implicit)
        self.assertEqual(implicit["metrics"], explicit["metrics"])
        self.assertEqual(implicit["energyBalance"], explicit["energyBalance"])
        self.assertEqual(implicit["discretization"], explicit["discretization"])

    def test_10mm_track_requires_rectangular_bare_plate_opt_in(self):
        with self.assertRaisesRegex(ValueError, "only by the opt-in bare-plate rectangular-corridor"):
            validate({"trackLength_um": 10000})

    def test_separate_three_level_studies_keep_frozen_targets(self):
        mesh = run({**CASE, "mesh_um": 30, "maxDt_s": 1e-7, "study": "mesh"})
        time = run({**CASE, "mesh_um": 40, "maxDt_s": 1e-7, "study": "timestep"})
        for result, kind in ((mesh, "mesh"), (time, "timestep")):
            study = result["convergenceStudy"]
            self.assertEqual(study["kind"], kind)
            self.assertEqual(study["metricSource"], "midTrackCrossSection")
            self.assertEqual(len(study["results"]), 3)
            self.assertEqual(study["acceptance"]["targets"]["energyRelativeErrorMax"], .01)
            self.assertEqual(study["acceptance"]["targets"]["finestPairWidthDepthRelativeChangeMax"], .05)
            self.assertEqual(study["acceptance"]["status"], "inconclusive")
            self.assertEqual(study["acceptance"]["energyStatus"], "pass")
            self.assertEqual(result["experimentalComparison"]["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
