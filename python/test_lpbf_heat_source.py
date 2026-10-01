"""Independent numerical oracles; synthetic verification, not measured validation."""
import math
import io
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest
import numpy as np
from lpbf_core_physics import calculate_mesh_domain
from lpbf_heat_source import (require_source_capture, gaussian_interval, cell_weights, integrated_source,
                              source_limited_step, conduction_diagonal)
from lpbf_simulation import MINIMUM_SOURCE_CAPTURE_FRACTION, validate


def _moving_source_case(travel_radii):
    radius = 100e-6
    dx = 0.4 * radius
    axis = (np.arange(27, dtype=np.float64) - 13) * dx
    z = -(np.arange(14, dtype=np.float64) + 0.5) * dx
    surface = 0.0
    segment = {
        "start": np.array([-0.5 * travel_radii * radius, 0.0]),
        "end": np.array([0.5 * travel_radii * radius, 0.0]),
        "start_s": 0.0,
        "end_s": 1.0,
    }
    return axis, z, dx, segment, surface, radius, 1.5 * radius, 75.0


def _high_order_moving_source_reference(case, *, reverse=False, order=96):
    """Independent temporal GL reference; spatial cell integrals stay shared."""
    axis, z, dx, segment, surface, radius, penetration, power = case
    if reverse:
        segment = {**segment, "start": segment["end"], "end": segment["start"]}
    nodes, weights = np.polynomial.legendre.leggauss(order)
    source = np.zeros((len(axis), len(axis), len(z)), dtype=np.float64)
    capture = 1.0
    for node, weight in zip((nodes + 1.0) * 0.5, weights * 0.5):
        position = segment["start"] + node * (segment["end"] - segment["start"])
        cell_mass = cell_weights(axis, z, dx, position, surface, radius, penetration, axis)
        total = float(cell_mass.sum())
        capture = min(capture, 2.0 * total)
        source += cell_mass * (power / (total * dx**3)) * weight
    return source, capture


class HeatSourceVerification(unittest.TestCase):
    def test_layer_conforming_powder_grid_aligns_surfaces_and_captures_source(self):
        for requested_mesh in (36.7, 13.34, 6.667):
            with self.subTest(requested_mesh=requested_mesh):
                raw = dict(mode="standard", backend="reference", material="Inconel 718",
                           power_W=80, speed_mm_s=1200, beamDiameter_um=80,
                           layer_um=80, mesh_um=requested_mesh, trackLength_um=200,
                           tracks=1, layers=3, powderGridPolicy="layer-conforming")
                p, _ = validate(raw)
                domain = calculate_mesh_domain(p)
                dx = domain["dx"]
                layer_m = p["layer_um"]*1e-6
                substrate_cells = domain["substrate_depth"]/dx
                self.assertLessEqual(dx*1e6, requested_mesh*(1+1e-12))
                requested_span = p["trackLength_um"]*1e-6+6*domain["radius"]
                self.assertGreaterEqual(domain["span"], requested_span)
                self.assertLess(domain["span"]-requested_span, dx*(1+1e-12))
                self.assertAlmostEqual(substrate_cells, round(substrate_cells), places=10)
                self.assertAlmostEqual(domain["span"]/dx, round(domain["span"]/dx), places=10)
                for layer_index in range(1, p["layers"]+1):
                    face_index = (domain["substrate_depth"]+layer_index*layer_m)/dx
                    self.assertAlmostEqual(face_index, round(face_index), places=10)

                axis = (np.arange(domain["nx"])+.5)*dx-domain["span"]/2
                z = (np.arange(domain["nz"])+.5)*dx-domain["substrate_depth"]
                captures = [2*float(cell_weights(axis, z, dx, [x, 0.], layer_m,
                                                    domain["radius"], layer_m).sum())
                            for x in np.linspace(-100e-6, 100e-6, 11)]
                self.assertGreaterEqual(min(captures), MINIMUM_SOURCE_CAPTURE_FRACTION)

    def test_standard_powder_grid_defaults_to_layer_conforming_and_legacy_geometry_remains_reproducible(self):
        p, _ = validate(dict(mode="standard", backend="reference", mesh_um=36.7,
                             trackLength_um=200, beamDiameter_um=80, layer_um=80))
        domain = calculate_mesh_domain(p)
        self.assertEqual(p["powderGridPolicy"], "layer-conforming")
        self.assertAlmostEqual(domain["dx"]*1e6, 80/3, places=8)
        for layer in range(1, p["layers"]+1):
            self.assertAlmostEqual((domain["substrate_depth"]+layer*p["layer_um"]*1e-6)/domain["dx"],
                                   round((domain["substrate_depth"]+layer*p["layer_um"]*1e-6)/domain["dx"]),
                                   places=10)
        legacy = dict(p)
        legacy.pop("powderGridPolicy")
        legacy_domain = calculate_mesh_domain(legacy)
        self.assertEqual(legacy_domain["nxy"], 12)
        self.assertAlmostEqual(legacy_domain["dx"]*1e6, 36.6666666667, places=8)
        self.assertAlmostEqual(legacy_domain["substrate_depth"]*1e6, 330., places=8)

    def test_layer_conforming_policy_rejects_unimplemented_modes(self):
        base = dict(mode="standard", backend="reference", surfaceMode="bare-plate",
                    sourcePenetration_um=40, powderGridPolicy="layer-conforming")
        with self.assertRaisesRegex(ValueError, "requires standard reference or OpenFOAM powder-layer mode"):
            validate(base)

    def test_capture_gate_uses_shared_one_percent_limit(self):
        self.assertEqual(require_source_capture(MINIMUM_SOURCE_CAPTURE_FRACTION,
                                               MINIMUM_SOURCE_CAPTURE_FRACTION),
                         MINIMUM_SOURCE_CAPTURE_FRACTION)
        with self.assertRaisesRegex(ValueError, "Gaussian source capture .* below the 99% minimum"):
            require_source_capture(MINIMUM_SOURCE_CAPTURE_FRACTION - 1e-6,
                                   MINIMUM_SOURCE_CAPTURE_FRACTION)

    @unittest.skipIf(os.name == "nt", "OpenFOAM dispatch is Linux-only")
    def test_reused_case_cannot_inherit_new_binary_diagnostics(self):
        from lpbf_openfoam import thermal
        with tempfile.TemporaryDirectory() as tmp:
            case = Path(tmp)/"openfoam-case"
            case.mkdir()
            stale = case/"numerical-diagnostics.json"
            stale.write_text('{"sourceIntegration":"cell-integrated-gaussian-gl2-v1"}')
            child = SimpleNamespace(stdout=io.StringIO(""), wait=lambda: 0)
            with patch("lpbf_openfoam.BINARY", Path(__file__)), patch("lpbf_openfoam.generate_case", return_value=(1., [])), patch("lpbf_openfoam.subprocess.Popen", return_value=child):
                with self.assertRaisesRegex(ValueError, "binary is outdated"):
                    thermal({}, {}, artifact_dir=tmp)
            self.assertFalse(stale.exists())

    def test_cell_integral_matches_independent_quadrature_including_tail(self):
        for a, b in [(-.2, .3), (2.8, 3.1), (-3.1, -2.8), (-10, 10)]:
            nodes, weights = np.polynomial.legendre.leggauss(128)
            x = (a+b)/2+(b-a)/2*nodes
            expected = float(np.sum(weights*np.sqrt(2/np.pi)*np.exp(-2*x*x))*(b-a)/2)
            self.assertAlmostEqual(float(gaussian_interval(a, b, 0, 1))/expected, 1, delta=1e-10)

    def test_refinement_additivity_and_translation_continuity(self):
        fine_edges = np.linspace(-.5, .5, 9)
        fine = gaussian_interval(fine_edges[:-1], fine_edges[1:], .23, .17)
        self.assertAlmostEqual(float(fine.sum()), float(gaussian_interval(-.5, .5, .23, .17)), delta=1e-14)
        self.assertLess(abs(float(gaussian_interval(-.5, .5, .5-1e-9, .2))-float(gaussian_interval(-.5, .5, .5+1e-9, .2))), 1e-7)

    def test_symmetry_power_and_future_powder(self):
        axis = (np.arange(12)+.5)*.25-1.5
        z = (np.arange(10)+.5)*.25-1.5
        segment = dict(start_s=0., end_s=1., start=[0., 0.], end=[0., 0.])
        source, capture = integrated_source(axis, z, .25, segment, 0, .2, .1, .4, .3, 70.)
        self.assertAlmostEqual(float(source.sum())*.25**3, 70., delta=1e-11)
        np.testing.assert_allclose(source, source[::-1], atol=1e-10)
        self.assertTrue((source >= 0).all())
        self.assertTrue((source[:, :, z >= .1] == 0).all())
        self.assertGreater(capture, 0)
        self.assertLessEqual(capture, 1)

    def test_oblique_source_zero_angle_is_exact_legacy_parity(self):
        axis = (np.arange(18)+.5)*.1-.9
        z = (np.arange(14)+.5)*.1-1.3
        segment = dict(start_s=0., end_s=1., start=[-.2, .1], end=[.2, -.1])
        legacy, legacy_capture = integrated_source(axis, z, .1, segment, .1, .7, 0., .35, .3, 40.)
        explicit, explicit_capture = integrated_source(
            axis, z, .1, segment, .1, .7, 0., .35, .3, 40.,
            incidence_angle_deg=0., incidence_azimuth_deg=37.)
        np.testing.assert_array_equal(explicit, legacy)
        self.assertEqual(explicit_capture, legacy_capture)

    def test_oblique_source_normalizes_on_large_domain_and_rotates_with_azimuth(self):
        dx = .1
        axis = (np.arange(40)+.5)*dx-2.
        z = (np.arange(20)+.5)*dx-2.
        segment = dict(start_s=0., end_s=1., start=[0., 0.], end=[0., 0.])
        along_x, capture_x = integrated_source(
            axis, z, dx, segment, 0., .2, 0., .45, .4, 70.,
            incidence_angle_deg=30., incidence_azimuth_deg=0.)
        along_y, capture_y = integrated_source(
            axis, z, dx, segment, 0., .2, 0., .45, .4, 70.,
            incidence_angle_deg=30., incidence_azimuth_deg=90.)
        self.assertAlmostEqual(float(along_x.sum())*dx**3, 70., delta=1e-11)
        self.assertAlmostEqual(float(along_y.sum())*dx**3, 70., delta=1e-11)
        self.assertAlmostEqual(capture_x, 1., delta=2e-3)
        self.assertAlmostEqual(capture_y, 1., delta=2e-3)
        np.testing.assert_allclose(along_y, along_x.transpose(1, 0, 2), rtol=2e-12, atol=1e-12)
        xx = axis[:, None, None]
        shallow = z > -.5
        deep = z < -1.2
        centroid_shallow = float((along_x[:, :, shallow]*xx).sum()/along_x[:, :, shallow].sum())
        centroid_deep = float((along_x[:, :, deep]*xx).sum()/along_x[:, :, deep].sum())
        self.assertGreater(centroid_deep, centroid_shallow)

    def test_oblique_source_rejects_invalid_angles(self):
        axis = np.array([-.5, .5])
        z = np.array([-.5])
        segment = dict(start_s=0., end_s=1., start=[0., 0.], end=[0., 0.])
        for angle in (-1., 90., math.inf, math.nan, True):
            with self.subTest(angle=angle), self.assertRaisesRegex(ValueError, "Incidence angle"):
                integrated_source(axis, z, 1., segment, 0., .1, 0., .5, .5, 1.,
                                  incidence_angle_deg=angle)
        for azimuth in (-1., 360., math.inf, math.nan, True):
            with self.subTest(azimuth=azimuth), self.assertRaisesRegex(ValueError, "Incidence azimuth"):
                integrated_source(axis, z, 1., segment, 0., .1, 0., .5, .5, 1.,
                                  incidence_azimuth_deg=azimuth)

    def test_moving_quadrature_beats_left_endpoint_and_reverses(self):
        axis = (np.arange(16)+.5)*.2-1.6
        z = (np.arange(8)+.5)*.2-1.6
        seg = dict(start_s=0., end_s=1., start=[-.1, 0.], end=[.1, 0.])
        actual, _ = integrated_source(axis, z, .2, seg, 0, 1, 0, .5, .3, 1)
        reference = np.zeros_like(actual)
        for t in (np.arange(1000)+.5)/1000:
            w = cell_weights(axis, z, .2, [-.1+.2*t, 0], 0, .5, .3)
            reference += w/(w.sum()*.2**3*1000)
        w = cell_weights(axis, z, .2, seg["start"], 0, .5, .3)
        left = w/(w.sum()*.2**3)
        self.assertLess(np.linalg.norm(actual-reference), np.linalg.norm(left-reference)*.01)
        reverse, _ = integrated_source(axis, z, .2, {**seg, "start":seg["end"], "end":seg["start"]}, 0, 1, 0, .5, .3, 1)
        np.testing.assert_allclose(actual, reverse, rtol=1e-13, atol=1e-13)

    def test_adaptive_moving_source_matches_high_order_oracle_through_four_radii(self):
        for travel_radii in (.5, 1., 2., 4., 8.):
            with self.subTest(travel_radii=travel_radii):
                case = _moving_source_case(travel_radii)
                axis, z, dx, segment, surface, radius, penetration, power = case
                actual, capture = integrated_source(
                    axis, z, dx, segment, 0., 1., surface, radius, penetration,
                    power, axis_y=axis)
                expected, expected_capture = _high_order_moving_source_reference(case)
                relative_l2 = np.linalg.norm(actual - expected) / np.linalg.norm(expected)
                self.assertTrue(np.isfinite(actual).all())
                self.assertLessEqual(relative_l2, 1e-6, (travel_radii, relative_l2))
                self.assertAlmostEqual(float(actual.sum()) * dx**3, power, delta=1e-12)
                self.assertAlmostEqual(capture, expected_capture, delta=1e-12)
                self.assertGreaterEqual(capture, MINIMUM_SOURCE_CAPTURE_FRACTION)

                reverse, reverse_capture = integrated_source(
                    axis, z, dx,
                    {**segment, "start": segment["end"], "end": segment["start"]},
                    0., 1., surface, radius, penetration, power, axis_y=axis)
                np.testing.assert_allclose(actual, reverse, rtol=1e-12, atol=1e-10)
                self.assertAlmostEqual(capture, reverse_capture, delta=1e-12)

    def test_source_recomputed_after_cap_and_dwell_is_dark(self):
        axis = np.arange(-1.5, 2, 1.)
        z = np.array([-1.5, -.5, .5])
        seg = dict(start_s=0., end_s=1., start=[-1., 0.], end=[1., 0.])
        passive = np.zeros((4, 4, 3))
        capacity = np.ones_like(passive)
        dt, source, rate, _, retries = source_limited_step(axis, z, 1, seg, 0, 1, 0, .5, .5, 1000, passive, capacity)
        self.assertGreater(retries, 0)
        self.assertLessEqual(float((dt*np.abs(rate)/capacity).max()), 25*(1+1e-12))
        expected, _ = integrated_source(axis, z, 1, seg, 0, dt, 0, .5, .5, 1000)
        np.testing.assert_allclose(source, expected)
        dark, _ = integrated_source(axis, z, 1, None, 1, .1, 0, .5, .5, 1000)
        self.assertTrue((dark == 0).all())
        with self.assertRaises(ValueError):
            integrated_source(axis, z, 1, seg, .9, .2, 0, .5, .5, 1000)

    def test_heterogeneous_row_sum_preserves_temperature_bounds(self):
        from lpbf_simulation import conduction_rate
        k = np.array([1., 1000., 1.]).reshape(3, 1, 1)
        active = np.ones_like(k, dtype=bool)
        temperature = np.array([300., 900., 300.]).reshape(k.shape)
        diagonal = conduction_diagonal(k, active, 1)
        dt = .9/float(diagonal.max())
        advanced = temperature+dt*conduction_rate(temperature, k, active, 1)
        self.assertGreaterEqual(float(advanced.min()), 300.)
        self.assertLessEqual(float(advanced.max()), 900.)
        self.assertAlmostEqual(float(advanced.sum()), float(temperature.sum()))

    def test_scan_schedule_energy_and_resolution_diagnostics(self):
        from lpbf_simulation import run, scan_segments
        r = run(dict(mode="standard", backend="reference", material="316L Stainless Steel", power_W=20,
                     mesh_um=40, trackLength_um=100, tracks=2, layers=2, dwell_s=.00003, cooling_s=.00002))
        p = r["settings"]
        segments, end = scan_segments(p)
        expected = p["power_W"]*p["absorptivity"]*sum(s["end_s"]-s["start_s"] for s in segments)
        self.assertAlmostEqual(r["energyBalance"]["input_J"], expected, delta=expected*1e-10)
        self.assertAlmostEqual(r["thermalHistory"][-1]["time_s"], end, delta=1e-13)
        d = r["numericalDiagnostics"]
        self.assertLessEqual(d["maximumEnthalpyIncrement_K"], 25*(1+1e-10))
        self.assertLessEqual(d["maximumSurfaceOffset_um"], r["discretization"]["mesh_m"]*5e5+1e-9)
        dt_summary = d["acceptedTimestepDistribution"]
        self.assertEqual(dt_summary["methodId"], "accepted-timestep-distribution-v1")
        self.assertEqual(dt_summary["count"], r["discretization"]["steps"])
        self.assertAlmostEqual(dt_summary["total_s"], end, delta=1e-13)
        self.assertAlmostEqual(dt_summary["mean_s"], r["discretization"]["meanDt_s"], delta=1e-15)
        self.assertAlmostEqual(dt_summary["sourceTimestepRetries"], d["sourceTimestepRetries"])
        self.assertLessEqual(dt_summary["minimum_s"], dt_summary["p50_s"])
        self.assertLessEqual(dt_summary["p50_s"], dt_summary["p90_s"])
        self.assertLessEqual(dt_summary["p90_s"], dt_summary["p99_s"])
        self.assertLessEqual(dt_summary["p99_s"], dt_summary["maximum_s"])
        self.assertGreaterEqual(dt_summary["eulerFirstOrderWeightedDt_s"], dt_summary["minimum_s"])
        self.assertLessEqual(dt_summary["eulerFirstOrderWeightedDt_s"], dt_summary["maximum_s"])
        self.assertEqual(r["geometricDefectScreen"]["status"], "unresolved")

    def test_accepted_timestep_distribution_uses_realized_steps(self):
        from lpbf_simulation import summarize_accepted_timesteps
        summary = summarize_accepted_timesteps([1.0, 1.0, 0.5], 1.0, 1, 2)
        self.assertEqual(summary["count"], 3)
        self.assertAlmostEqual(summary["total_s"], 2.5)
        self.assertAlmostEqual(summary["mean_s"], 2.5/3)
        self.assertAlmostEqual(summary["eulerFirstOrderWeightedDt_s"], 2.25/2.5)
        self.assertAlmostEqual(summary["requestedMaxDtHitFraction"], 2/3)
        self.assertEqual(summary["sourceLimitedStepCount"], 1)
        self.assertEqual(summary["sourceTimestepRetries"], 2)
        # Geometric requested caps do not imply geometric realized refinement.
        coarse = summarize_accepted_timesteps([1.0, .1], 1.0, 0, 0)
        fine = summarize_accepted_timesteps([.5, .5], .5, 0, 0)
        self.assertAlmostEqual(coarse["eulerFirstOrderWeightedDt_s"], .9181818181818182)
        self.assertAlmostEqual(fine["eulerFirstOrderWeightedDt_s"], .5)
        with self.assertRaises(ValueError):
            summarize_accepted_timesteps([1.0, 0.0], 1.0, 0, 0)


if __name__ == "__main__":
    unittest.main()
