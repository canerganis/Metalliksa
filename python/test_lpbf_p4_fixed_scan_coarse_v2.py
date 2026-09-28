"""Cheap contract tests for the single-case P4 coarse v2 preflight."""

import unittest
import time
from unittest.mock import patch

import run_lpbf_p4_fixed_scan_coarse_v2 as coarse


class FixedScanCoarseV2PreflightTests(unittest.TestCase):
    def test_frozen_case_resolves_exact_first_scan_end_and_final_time(self):
        with patch.object(coarse.lpbf_simulation, "run", side_effect=AssertionError("preflight must not solve")):
            (protocol, _protocol_bytes, _scenario_bytes, resolved, material, segments,
             final_time, selected_time, _domain, resources, destinations) = coarse.preflight()

        self.assertEqual(protocol["status"], "frozen-before-execution")
        self.assertFalse(protocol["experimentalValidation"])
        self.assertEqual(resolved["power_W"], 40)
        self.assertEqual(resolved["material"], "Inconel 718")
        self.assertEqual(resolved["mesh_um"], 20)
        self.assertEqual(resolved["maxDt_s"], 2.5e-8)
        self.assertEqual(selected_time, segments[0]["end_s"])
        self.assertEqual(selected_time, protocol["nominalScanEndTime_s"])
        self.assertEqual(final_time, protocol["finalTime_s"])
        self.assertAlmostEqual(selected_time, 250e-6, places=16)
        self.assertAlmostEqual(final_time, 350e-6, places=16)
        self.assertEqual(material["materialId"], "in718")
        self.assertEqual(material["materialRevisionSha256"], protocol["expectedMaterialRevisionSha256"])
        self.assertEqual(resources["cells"], 8228)
        self.assertEqual(resources["lowerBoundSteps"], 14000)
        self.assertEqual(resources["lowerBoundCellSteps"], 115_192_000)
        self.assertEqual(resolved["mesh_um"], 20, "the frozen 5 um source scenario is explicitly overridden")
        for path in destinations.values():
            self.assertFalse(path.exists(), f"preflight must not create {path}")

    def test_one_level_is_always_inconclusive_and_thresholds_are_preserved(self):
        protocol, *_ = coarse.preflight()
        acceptance = protocol["acceptance"]
        self.assertEqual(acceptance["status"], "inconclusive")
        self.assertIn("insufficient levels", acceptance["reason"])
        self.assertEqual(acceptance["minimumLevelsPerAxis"], 3)
        self.assertEqual(acceptance["maximumLevelsPerAxis"], 6)
        self.assertEqual(acceptance["energyRelativeErrorMax"], 0.01)
        self.assertEqual(acceptance["finestPairWidthDepthRelativeChangeMax"], 0.05)
        self.assertFalse(acceptance["existingThresholdsChanged"])

    def test_protocol_pins_solver_material_source_and_exclusive_new_destinations(self):
        protocol, *_rest, destinations = coarse.preflight()
        self.assertEqual(protocol["expectedModelId"], coarse.MODEL_ID)
        self.assertEqual(protocol["expectedSolverId"], coarse.SOLVER_ID)
        self.assertEqual(protocol["expectedActualBackend"], coarse.BACKEND_ID)
        self.assertEqual(protocol["expectedImplementationFingerprint"], coarse.implementation_fingerprint())
        self.assertEqual(protocol["temporalSelection"], "first-scan-end-accepted-state-v1")
        self.assertEqual(protocol["observationOperator"], "fixed-scan-end-liquidus-cell-edge-contour-v1")
        self.assertEqual(destinations["output"].name, "LPBF_P4_FIXED_SCAN_COARSE_V2_2026-09-28.json")
        self.assertEqual(destinations["partial"].name, "LPBF_P4_FIXED_SCAN_COARSE_V2_2026-09-28.partial.json")
        self.assertEqual(destinations["fieldDirectory"].name, "LPBF_P4_FIXED_SCAN_COARSE_V2_FIELDS_2026-09-28")
        self.assertTrue(all(coarse.ROOT in path.parents for path in destinations.values()))

    def test_observation_module_hash_mismatch_is_rejected_without_solving(self):
        protocol, *_ = coarse.preflight()
        altered = dict(protocol, observationModuleSha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "observation module hash"):
            coarse._verify_observation_module(altered)

    def test_runtime_guard_counts_steps_enforces_both_caps_and_restores(self):
        original = coarse.lpbf_simulation.source_limited_step
        calls = []

        def fake_limiter(*args, **kwargs):
            calls.append((args, kwargs))
            return "accepted"

        coarse.lpbf_simulation.source_limited_step = fake_limiter
        try:
            counters = {"acceptedSteps": 0}
            limits = {"maximumSteps": 5, "maximumCellSteps": 10, "maximumWallSeconds": 10,
                      "maximumPeakRssBytes": 10**9}
            with coarse._install_runtime_guard(counters, cells=10, limits=limits,
                                               start=time.perf_counter(), rss_state=None):
                guarded = coarse.lpbf_simulation.source_limited_step
                self.assertIsNot(guarded, fake_limiter)
                self.assertEqual(guarded("step"), "accepted")
                self.assertEqual(counters["acceptedSteps"], 1)
                with self.assertRaisesRegex(RuntimeError, "cell-step limit"):
                    guarded("step over cell cap")
            self.assertIs(coarse.lpbf_simulation.source_limited_step, fake_limiter)
            self.assertEqual(len(calls), 1)

            step_limits = dict(limits, maximumSteps=1, maximumCellSteps=100)
            with coarse._install_runtime_guard({"acceptedSteps": 0}, cells=10, limits=step_limits,
                                               start=time.perf_counter(), rss_state=None):
                guarded = coarse.lpbf_simulation.source_limited_step
                guarded("one")
                with self.assertRaisesRegex(RuntimeError, "accepted-step limit"):
                    guarded("over step cap")
            self.assertIs(coarse.lpbf_simulation.source_limited_step, fake_limiter)

            with self.assertRaisesRegex(ValueError, "exercise failure restoration"):
                with coarse._install_runtime_guard({"acceptedSteps": 0}, cells=10, limits=limits,
                                                   start=time.perf_counter(), rss_state=None):
                    self.assertIsNot(coarse.lpbf_simulation.source_limited_step, fake_limiter)
                    raise ValueError("exercise failure restoration")
            self.assertIs(coarse.lpbf_simulation.source_limited_step, fake_limiter)
        finally:
            coarse.lpbf_simulation.source_limited_step = original


if __name__ == "__main__":
    unittest.main()
