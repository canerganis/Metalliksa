"""Public-run progress integration tests; all cases remain software/numerical evidence."""
import contextlib
import unittest
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import lpbf_simulation
from lpbf_run_progress import CpuRunProgress, current_progress, track_cpu_progress


class AutoRunProgressTests(unittest.TestCase):
    def setUp(self):
        self.raw = {
            "mode": "standard", "backend": "reference", "material": "Inconel 718",
            "power_W": 10, "speed_mm_s": 10000, "mesh_um": 40,
            "layer_um": 40, "trackLength_um": 100, "cooling_s": 20e-6,
            "dwell_s": 0, "maxDt_s": 1e-6, "convection_W_m2K": 0,
            "powderGridPolicy": "layer-conforming",
        }

    def test_completion_callback_waits_until_public_postprocessing_has_succeeded(self):
        snapshots = []
        tracker = CpuRunProgress(observer=snapshots.append)
        original = lpbf_simulation.build_core_contract

        def inspect_before_contract(*args, **kwargs):
            self.assertEqual(tracker.snapshot()["stage"], "running")
            return original(*args, **kwargs)

        with patch.object(
                lpbf_simulation, "build_core_contract", side_effect=inspect_before_contract):
            result = lpbf_simulation.run(self.raw, run_progress=tracker)

        self.assertEqual(result["validationStatus"], "unvalidated")
        self.assertEqual(tracker.snapshot()["stage"], "completed")
        self.assertEqual(snapshots[-1]["stage"], "completed")
        self.assertEqual(sum(snapshot["stage"] == "completed" for snapshot in snapshots), 1)
        self.assertGreater(tracker.snapshot()["acceptedSteps"], 0)

    def test_downstream_postprocessing_failures_keep_exception_and_started_progress(self):
        for stage in ("build_core_contract", "enforce_thermal_balances", "write_artifacts", "json"):
            with self.subTest(stage=stage):
                tracker = CpuRunProgress()
                error = RuntimeError(f"injected {stage} failure")
                patchers = []
                if stage == "json":
                    original_dumps = lpbf_simulation.json.dumps

                    def fail_final_serialization(value, *args, **kwargs):
                        if isinstance(value, dict) and "metrics" in value and "provenance" in value:
                            raise error
                        return original_dumps(value, *args, **kwargs)

                    patchers.extend((patch.object(lpbf_simulation.json, "dumps",
                                                  side_effect=fail_final_serialization),
                                     patch.object(lpbf_simulation, "write_artifacts")))
                else:
                    patchers.append(patch.object(lpbf_simulation, stage, side_effect=error))
                    if stage != "write_artifacts":
                        patchers.append(patch.object(lpbf_simulation, "write_artifacts"))
                with patchers[0]:
                    with patchers[1] if len(patchers) > 1 else contextlib.nullcontext():
                        with self.assertRaises(RuntimeError) as caught:
                            lpbf_simulation.run(self.raw, run_progress=tracker)

                self.assertIs(caught.exception, error)
                progress = error.progress
                self.assertEqual(progress["stage"], "failed")
                self.assertEqual(progress["failureStage"], "postprocessing")
                self.assertGreater(progress["acceptedSteps"], 0)
                self.assertGreater(progress["lastAcceptedTime_s"], 0)
                self.assertNotEqual(tracker.snapshot()["stage"], "completed")
                self.assertIsNone(current_progress())

    def test_source_budget_failure_is_attached_before_first_accepted_step(self):
        tracker = CpuRunProgress(maximum_source_evaluations=0)
        with self.assertRaisesRegex(RuntimeError, "source-evaluation budget") as caught:
            lpbf_simulation.run(self.raw, run_progress=tracker)
        self.assertEqual(caught.exception.progress["stage"], "failed")
        self.assertEqual(caught.exception.progress["acceptedSteps"], 0)
        self.assertEqual(caught.exception.progress["attemptedSourceEvaluations"], 0)

    def test_auto_reference_and_explicit_reference_have_identical_small_cpu_fields_and_metrics(self):
        explicit_states, auto_states = [], []
        explicit = lpbf_simulation.run(
            self.raw, final_state_observer=explicit_states.append,
            run_progress=CpuRunProgress(), capabilities={},
        )
        automatic_input = {**self.raw, "backend": "auto"}
        automatic_input.pop("powderGridPolicy")
        automatic = lpbf_simulation.run(
            automatic_input, final_state_observer=auto_states.append,
            run_progress=CpuRunProgress(), capabilities={"openfoamThermal": True},
        )
        self.assertEqual(len(explicit_states), 1)
        self.assertEqual(len(auto_states), 1)
        for name in ("coordinates_m", "temperature_K", "enthalpy_J_m3", "density_kg_m3", "accepted_dt_s"):
            np.testing.assert_array_equal(explicit_states[0][name], auto_states[0][name])
        self.assertEqual(explicit["metrics"], automatic["metrics"])
        self.assertEqual(explicit["discretization"], automatic["discretization"])
        self.assertEqual(explicit["numericalDiagnostics"]["acceptedTimestepDistribution"],
                         automatic["numericalDiagnostics"]["acceptedTimestepDistribution"])
        self.assertEqual(automatic["requestedBackend"], "auto")
        self.assertEqual(automatic["settings"]["backend"], "reference")

    def test_explicit_openfoam_backend_rejects_tracker_without_changing_dispatch(self):
        raw = {**self.raw, "backend": "openfoam-thermal"}
        tracker = CpuRunProgress()
        dispatch_error = RuntimeError("OpenFOAM dispatch sentinel")
        foam = SimpleNamespace(thermal=Mock(side_effect=dispatch_error))
        with patch.dict(sys.modules, {"lpbf_openfoam": foam}):
            with self.assertRaises(ValueError):
                lpbf_simulation.run(raw, run_progress=tracker)
            self.assertEqual(tracker.snapshot()["stage"], "running")
            self.assertEqual(tracker.snapshot()["acceptedSteps"], 0)
            with self.assertRaises(RuntimeError) as caught:
                lpbf_simulation.run(raw)
            self.assertIs(caught.exception, dispatch_error)
            foam.thermal.assert_called_once()
        result = lpbf_simulation.run(self.raw, run_progress=tracker)
        self.assertEqual(result["validationStatus"], "unvalidated")
        self.assertEqual(tracker.snapshot()["stage"], "completed")

    def test_tracker_is_single_use_at_public_run_boundary(self):
        tracker = CpuRunProgress()
        first = lpbf_simulation.run(self.raw, run_progress=tracker)
        frozen = tracker.snapshot()
        with self.assertRaisesRegex(ValueError, "single-use"):
            lpbf_simulation.run(self.raw, run_progress=tracker)
        self.assertEqual(tracker.snapshot(), frozen)
        self.assertEqual(first["validationStatus"], "unvalidated")
        self.assertIsNone(current_progress())

    def test_completion_observer_failure_preserves_counts_without_second_notification(self):
        snapshots = []
        error = LookupError("completion observer failure")

        def observer(snapshot):
            snapshots.append(snapshot)
            if snapshot["stage"] == "completed":
                raise error

        tracker = CpuRunProgress(observer=observer)
        with self.assertRaises(LookupError) as caught:
            lpbf_simulation.run(self.raw, run_progress=tracker)
        self.assertIs(caught.exception, error)
        self.assertEqual(error.progress["stage"], "failed")
        self.assertEqual(error.progress["failureStage"], "postprocessing")
        self.assertGreater(error.progress["acceptedSteps"], 0)
        self.assertEqual(sum(row["stage"] == "completed" for row in snapshots), 1)
        self.assertIsNone(current_progress())

    def test_thermal_failure_notifies_failed_observer_once_across_both_decorators(self):
        snapshots = []
        tracker = CpuRunProgress(observer=snapshots.append, maximum_source_evaluations=0)
        with self.assertRaisesRegex(RuntimeError, "source-evaluation budget") as caught:
            lpbf_simulation.run(self.raw, run_progress=tracker)
        self.assertEqual(caught.exception.progress["stage"], "failed")
        self.assertEqual(caught.exception.progress["acceptedSteps"], 0)
        self.assertEqual(sum(row["stage"] == "failed" for row in snapshots), 1)
        self.assertIsNone(current_progress())

    def test_nested_public_tracker_is_rejected_and_following_run_recovers(self):
        nested = CpuRunProgress()
        def enter_nested(_snapshot):
            lpbf_simulation.run(self.raw, run_progress=nested)

        outer = CpuRunProgress(observer=enter_nested)
        with self.assertRaisesRegex(ValueError, "nested") as caught:
            lpbf_simulation.run(self.raw, run_progress=outer)
        self.assertEqual(caught.exception.progress["acceptedSteps"], 0)
        self.assertEqual(nested.snapshot()["acceptedSteps"], 0)
        self.assertIsNone(current_progress())

        recovery = CpuRunProgress()
        result = lpbf_simulation.run(self.raw, run_progress=recovery)
        self.assertEqual(result["validationStatus"], "unvalidated")
        self.assertEqual(recovery.snapshot()["stage"], "completed")
        self.assertIsNone(current_progress())

    def test_nested_tracker_from_completion_observer_fails_outer_without_starting_inner(self):
        inner = CpuRunProgress()

        def observer(snapshot):
            if snapshot["stage"] == "completed":
                lpbf_simulation.run(self.raw, run_progress=inner)

        outer = CpuRunProgress(observer=observer)
        with self.assertRaisesRegex(ValueError, "nested") as caught:
            lpbf_simulation.run(self.raw, run_progress=outer)
        self.assertEqual(caught.exception.progress["stage"], "failed")
        self.assertEqual(caught.exception.progress["failureStage"], "postprocessing")
        self.assertGreater(caught.exception.progress["acceptedSteps"], 0)
        self.assertEqual(inner.snapshot()["stage"], "running")
        self.assertEqual(inner.snapshot()["acceptedSteps"], 0)
        self.assertIsNone(current_progress())

    def test_untracked_public_run_from_begin_observer_is_rejected_before_body(self):
        attempted = [False]
        validate_calls = [0]
        original_validate = lpbf_simulation.validate

        def observer(_snapshot):
            if not attempted[0]:
                attempted[0] = True
                lpbf_simulation.run(self.raw)

        def count_validate(*args, **kwargs):
            validate_calls[0] += 1
            if validate_calls[0] > 1:
                raise AssertionError("nested public run body was entered")
            return original_validate(*args, **kwargs)

        tracker = CpuRunProgress(observer=observer)
        with patch.object(lpbf_simulation, "validate", side_effect=count_validate):
            with self.assertRaisesRegex(ValueError, "nested") as caught:
                lpbf_simulation.run(self.raw, run_progress=tracker)

        self.assertEqual(validate_calls[0], 1)
        self.assertEqual(caught.exception.progress["stage"], "failed")
        self.assertEqual(caught.exception.progress["acceptedSteps"], 0)
        self.assertEqual(caught.exception.progress["attemptedSourceEvaluations"], 0)
        self.assertEqual(caught.exception.progress["attemptedSourceCellSteps"], 0)
        self.assertIsNone(current_progress())

    def test_untracked_public_run_from_completion_observer_is_rejected_without_counter_change(self):
        nested_calls = [0]
        validate_calls = [0]
        completed_counts = []
        original_validate = lpbf_simulation.validate

        def observer(snapshot):
            if snapshot["stage"] == "completed":
                nested_calls[0] += 1
                completed_counts.append(snapshot["acceptedSteps"])
                lpbf_simulation.run(self.raw)

        def count_validate(*args, **kwargs):
            validate_calls[0] += 1
            if validate_calls[0] > 1:
                raise AssertionError("nested public run body was entered")
            return original_validate(*args, **kwargs)

        tracker = CpuRunProgress(observer=observer)
        with patch.object(lpbf_simulation, "validate", side_effect=count_validate):
            with self.assertRaisesRegex(ValueError, "nested") as caught:
                lpbf_simulation.run(self.raw, run_progress=tracker)

        self.assertEqual(nested_calls[0], 1)
        self.assertEqual(validate_calls[0], 1)
        self.assertEqual(caught.exception.progress["stage"], "failed")
        self.assertEqual(caught.exception.progress["failureStage"], "postprocessing")
        self.assertGreater(caught.exception.progress["acceptedSteps"], 0)
        self.assertEqual(caught.exception.progress["acceptedSteps"], completed_counts[0])
        self.assertIsNone(current_progress())

    def test_untracked_public_run_from_first_accept_observer_cannot_contaminate_outer_counts(self):
        validate_calls = [0]
        original_validate = lpbf_simulation.validate

        def observer(snapshot):
            if snapshot["acceptedSteps"] == 1:
                lpbf_simulation.run(self.raw)

        def count_validate(*args, **kwargs):
            validate_calls[0] += 1
            if validate_calls[0] > 1:
                raise AssertionError("nested public run body was entered")
            return original_validate(*args, **kwargs)

        tracker = CpuRunProgress(observer=observer)
        with patch.object(lpbf_simulation, "validate", side_effect=count_validate):
            with self.assertRaisesRegex(ValueError, "nested") as caught:
                lpbf_simulation.run(self.raw, run_progress=tracker)
        self.assertEqual(validate_calls[0], 1)
        self.assertEqual(caught.exception.progress["acceptedSteps"], 1)
        self.assertEqual(caught.exception.progress["attemptedSourceEvaluations"], 1)
        self.assertIsNone(current_progress())

    def test_untracked_transient_inside_tracked_callback_never_enters_body(self):
        entered = []

        @track_cpu_progress
        def tiny_transient(p, run_progress=None):
            entered.append(True)
            return "entered"

        def observer(_snapshot):
            tiny_transient(p)

        tracker = CpuRunProgress(observer=observer)
        p, _ = lpbf_simulation.validate(self.raw)
        with self.assertRaisesRegex(ValueError, "nested") as caught:
            tiny_transient(p, run_progress=tracker)
        self.assertEqual(entered, [])
        self.assertEqual(caught.exception.progress["stage"], "failed")
        self.assertEqual(caught.exception.progress["acceptedSteps"], 0)
        self.assertIsNone(current_progress())


if __name__ == "__main__":
    unittest.main()
