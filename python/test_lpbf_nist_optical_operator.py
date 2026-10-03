"""Unit tests for the NIST AMB2022-03 optical boundary operator and residual generation."""

import unittest
import numpy as np

from lpbf_nist_optical_operator import (
    extract_subcell_liquidus_geometry,
    build_six_section_diagnostic_aggregate,
)
from lpbf_nist_in718_comparison import (
    compare_nist_in718_optical_geometry,
    ARCHIVE_DATASET_ID,
    SOURCE_DATASET_ID,
    TRANSCRIPTION_ARTIFACT_SHA256,
)


class TestNistOpticalOperator(unittest.TestCase):
    def test_subcell_boundary_continuous_accuracy(self):
        # Create analytical melt pool shape:
        # T(y, z) = T_liquidus + T_peak * (1 - (y/W_semi)^2 - (z/D)^2)
        # Exact width = 2 * W_semi = 100.0 um
        # Exact depth = D = 50.0 um
        t_liquidus = 1609.15
        t_peak = 1000.0
        w_semi = 50e-6
        d_exact = 50e-6

        # Coarse grid: dy = 10 um, dz = 10 um
        y_coords = np.linspace(-80e-6, 80e-6, 17)
        z_coords = np.linspace(0.0, -80e-6, 9)

        ny = len(y_coords)
        nz = len(z_coords)
        plane = np.zeros((ny, nz), dtype=float)

        for iy, y in enumerate(y_coords):
            for iz, z in enumerate(z_coords):
                r_sq = (y / w_semi)**2 + (z / d_exact)**2
                if r_sq <= 1.0:
                    plane[iy, iz] = t_liquidus + t_peak * (1.0 - r_sq)
                else:
                    plane[iy, iz] = t_liquidus - 200.0 * (r_sq - 1.0)

        res = extract_subcell_liquidus_geometry(y_coords, z_coords, plane, t_liquidus)
        self.assertTrue(res["valid"])
        self.assertTrue(res["subcell_interpolated"])

        # Check sub-cell accuracy is within 2 um despite 10 um cell spacing
        self.assertAlmostEqual(res["width_um"], 100.0, delta=2.5)
        self.assertAlmostEqual(res["depth_um"], 50.0, delta=2.5)

    def test_melt_geometry_without_closed_width_and_depth_contours_is_invalid(self):
        t_liquidus = 1609.15
        y_coords = np.array([-10e-6, 0.0, 10e-6])
        z_coords = np.array([0.0, -10e-6, -20e-6])
        plane = np.full((3, 3), t_liquidus - 100.0)
        plane[1, 2] = t_liquidus + 100.0

        result = extract_subcell_liquidus_geometry(y_coords, z_coords, plane, t_liquidus)

        self.assertIsNone(result["width_um"])
        self.assertIsNone(result["depth_um"])
        self.assertFalse(result["valid"])

    def test_liquidus_geometry_rejects_nonfinite_or_misordered_inputs(self):
        t_liquidus = 1609.15
        y_coords = np.array([-10e-6, 0.0, 10e-6])
        z_coords = np.array([0.0, -10e-6, -20e-6])
        plane = np.full((3, 3), t_liquidus - 100.0)
        plane[1, 0] = t_liquidus + 100.0
        plane[1, 1] = t_liquidus + 100.0

        nonfinite_plane = plane.copy()
        nonfinite_plane[0, 0] = float("nan")
        invalid_inputs = [
            (y_coords, z_coords, nonfinite_plane, t_liquidus),
            (y_coords[::-1], z_coords, plane, t_liquidus),
            (y_coords, z_coords[::-1], plane, t_liquidus),
            (y_coords, z_coords, plane, float("nan")),
        ]
        for inputs in invalid_inputs:
            with self.subTest(inputs=inputs):
                with self.assertRaises(ValueError):
                    extract_subcell_liquidus_geometry(*inputs)

    def test_six_section_observation_construction(self):
        sections = [
            {"track": 1, "position_mm": 4.9, "width_um": 110.0, "depth_um": 55.0},
            {"track": 1, "position_mm": 6.0, "width_um": 112.0, "depth_um": 56.0},
            {"track": 2, "position_mm": 4.9, "width_um": 108.0, "depth_um": 54.0},
            {"track": 2, "position_mm": 6.0, "width_um": 111.0, "depth_um": 55.5},
            {"track": 3, "position_mm": 4.9, "width_um": 109.0, "depth_um": 54.5},
            {"track": 3, "position_mm": 6.0, "width_um": 113.0, "depth_um": 57.0},
        ]

        obs = build_six_section_diagnostic_aggregate(sections)
        self.assertEqual(obs["status"], "unverified-aggregate")
        self.assertEqual(obs["resultKind"], "thermal-geometry-diagnostic")
        self.assertFalse(obs["claimBoundary"]["opticalOperatorMatched"])
        self.assertFalse(obs["claimBoundary"]["experimentalValidation"])
        self.assertFalse(obs["claimBoundary"]["independentTrackFieldBinding"])
        self.assertNotIn("operator", obs)
        self.assertNotIn("subcellInterpolation", obs)
        self.assertEqual(obs["observationCount"], 6)
        self.assertEqual(obs["locations_mm"], [4.9, 6.0])
        self.assertEqual(len(obs["sections"]), 6)
        self.assertAlmostEqual(obs["widthMean_um"], 110.5, places=2)
        self.assertAlmostEqual(obs["depthMean_um"], 55.333, places=2)

        # Invalid count check
        with self.assertRaises(ValueError):
            build_six_section_diagnostic_aggregate(sections[:4])

    def test_six_section_aggregate_rejects_incomplete_or_invalid_pairs(self):
        sections = [
            {"track": 1, "position_mm": 4.9, "width_um": 110.0, "depth_um": 55.0},
            {"track": 1, "position_mm": 6.0, "width_um": 112.0, "depth_um": 56.0},
            {"track": 2, "position_mm": 4.9, "width_um": 108.0, "depth_um": 54.0},
            {"track": 2, "position_mm": 6.0, "width_um": 111.0, "depth_um": 55.5},
            {"track": 3, "position_mm": 4.9, "width_um": 109.0, "depth_um": 54.5},
            {"track": 3, "position_mm": 6.0, "width_um": 113.0, "depth_um": 57.0},
        ]
        invalid_cases = []

        duplicate = [dict(section) for section in sections]
        duplicate[-1]["track"] = 2
        duplicate[-1]["position_mm"] = 4.9
        invalid_cases.append(duplicate)

        invalid_track = [dict(section) for section in sections]
        invalid_track[-1]["track"] = 4
        invalid_cases.append(invalid_track)

        invalid_position = [dict(section) for section in sections]
        invalid_position[-1]["position_mm"] = 5.5
        invalid_cases.append(invalid_position)

        non_finite = [dict(section) for section in sections]
        non_finite[-1]["width_um"] = float("nan")
        invalid_cases.append(non_finite)

        non_positive = [dict(section) for section in sections]
        non_positive[-1]["depth_um"] = 0.0
        invalid_cases.append(non_positive)

        for invalid_sections in invalid_cases:
            with self.subTest(sections=invalid_sections):
                with self.assertRaises(ValueError):
                    build_six_section_diagnostic_aggregate(invalid_sections)

    def test_unverified_six_section_shape_cannot_enable_residual(self):
        # A valid-looking six-row aggregate lacks evidence of independent track fields.
        from test_lpbf_nist_in718_comparison import (
            synthetic_result,
            source_binding,
            TABLE_PATH,
        )
        import json

        result = synthetic_result()
        binding = source_binding()
        table4 = json.loads(TABLE_PATH.read_text(encoding="utf-8"))

        # Add valid sixSectionObservation
        sections = [
            {"track": 1, "position_mm": 4.9, "width_um": 140.0, "depth_um": 150.0},
            {"track": 1, "position_mm": 6.0, "width_um": 142.0, "depth_um": 151.0},
            {"track": 2, "position_mm": 4.9, "width_um": 139.0, "depth_um": 149.5},
            {"track": 2, "position_mm": 6.0, "width_um": 141.0, "depth_um": 150.5},
            {"track": 3, "position_mm": 4.9, "width_um": 138.0, "depth_um": 149.0},
            {"track": 3, "position_mm": 6.0, "width_um": 140.0, "depth_um": 150.0},
        ]
        result["sixSectionObservation"] = build_six_section_diagnostic_aggregate(sections)
        # Match finest reported optical section exactly to mean
        result["sixSectionObservation"]["width_um"] = 140.0
        result["sixSectionObservation"]["depth_um"] = 150.0

        report = compare_nist_in718_optical_geometry(
            result, table4, binding, binding, "0"
        )

        self.assertEqual(report["status"], "unavailable")
        self.assertEqual(report["validationStatus"], "unvalidated")
        self.assertIsNone(report["errors"])
        self.assertIn("independent simulated track field", " ".join(report["reasons"]))

    def test_single_transient_does_not_emit_repeated_field_as_six_sections(self):
        from lpbf_simulation import run

        result = run({
            "mode": "standard", "material": "Inconel 718", "power_W": 220.0,
            "speed_mm_s": 900.0, "beamDiameter_um": 80.0, "preheat_C": 23.5,
            "layer_um": 40.0, "hatch_um": 100.0, "mesh_um": 80.0,
            "maxDt_s": 1e-5, "trackLength_um": 100.0, "tracks": 1, "layers": 1,
            "dwell_s": 0.0, "cooling_s": 0.0, "backend": "reference",
            "surfaceMode": "bare-plate", "barePlateGeometry": "square",
            "sourcePenetration_um": 50.0, "opticalObserver": "nist-six-section",
        })

        self.assertIn("metrics", result)
        self.assertNotIn("sixSectionObservation", result)


if __name__ == "__main__":
    unittest.main()
