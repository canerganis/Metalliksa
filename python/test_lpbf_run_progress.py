"""CPU work/progress accounting oracles; no experimental validation."""
import contextlib
import unittest
from unittest.mock import patch

import numpy as np
import lpbf_heat_source
import lpbf_simulation
from lpbf_run_progress import CpuRunProgress, current_progress


class CpuProgressTests(unittest.TestCase):
    def setUp(self):
        self.p, self.m = lpbf_simulation.validate({
            "mode": "standard", "backend": "reference", "material": "Inconel 718",
            "power_W": 60, "speed_mm_s": 1000, "mesh_um": 40,
            "layer_um": 80, "trackLength_um": 100, "cooling_s": 0,
            "dwell_s": 0, "maxDt_s": 1e-6, "convection_W_m2K": 0,
        })
        self.domain = dict(radius=50e-6, span=80e-6, nx=2, ny=1, nz=4,
                           nxy=2, dx=40e-6, substrate_depth=80e-6)

    @contextlib.contextmanager
    def forcing(self, *, capture_failure=None, source_failure=None, heating_K=0.):
        context = {"calls": 0}
        original = lpbf_heat_source.source_limited_step

        def limited(*args, **kwargs):
            context["passive"], context["capacity"] = args[10], args[11]
            return original(*args, **kwargs)

        def source(*args, **kwargs):
            context["calls"] += 1
            if context["calls"] == source_failure:
                raise ValueError("injected source evaluation failure")
            dt = args[5]
            increment = heating_K(context["calls"]) if callable(heating_K) else heating_K
            rate = context["capacity"]*increment/dt
            capture = .5 if context["calls"] == capture_failure else 1.
            return rate-context["passive"], capture

        with patch.object(lpbf_simulation, "calculate_mesh_domain", return_value=self.domain), \
             patch.object(lpbf_simulation, "source_limited_step", side_effect=limited), \
             patch.object(lpbf_heat_source, "integrated_source", side_effect=source):
            yield context

    def transient(self, tracker=None, **kwargs):
        return lpbf_simulation.transient(self.p, self.m, run_progress=tracker, **kwargs)

    def test_success_fields_and_clock_are_bitwise_equal_with_opt_in_progress(self):
        fields, tracked_fields = [], []
        with self.forcing():
            first = self.transient(final_state_observer=fields.append)
        snapshots = []
        tracker = CpuRunProgress(observer=snapshots.append)
        with self.forcing() as context:
            second = self.transient(tracker, final_state_observer=tracked_fields.append)
        for name in ("coordinates_m", "temperature_K", "enthalpy_J_m3", "density_kg_m3", "accepted_dt_s"):
            np.testing.assert_array_equal(fields[0][name], tracked_fields[0][name])
        self.assertEqual(first["discretization"], second["discretization"])
        progress = tracker.snapshot()
        self.assertEqual(progress["stage"], "completed")
        self.assertEqual(progress["acceptedSteps"], len(fields[0]["accepted_dt_s"]))
        self.assertEqual(progress["attemptedSourceEvaluations"], context["calls"])
        self.assertEqual(progress["attemptedSourceCellSteps"], context["calls"]*8)
        self.assertEqual(progress["lastAcceptedTime_s"], float(np.cumsum(fields[0]["accepted_dt_s"])[-1]))
        snapshots[0]["acceptedSteps"] = -123
        self.assertGreaterEqual(tracker.snapshot()["acceptedSteps"], 0)
        self.assertIsNone(current_progress())

    def test_first_and_nth_capture_failure_never_accept_invalid_candidate(self):
        for nth in (1, 3):
            with self.subTest(nth=nth):
                tracker = CpuRunProgress()
                with self.forcing(capture_failure=nth):
                    with self.assertRaisesRegex(ValueError, "capture") as caught:
                        self.transient(tracker)
                progress = caught.exception.progress
                self.assertEqual(progress["acceptedSteps"], nth-1)
                self.assertEqual(progress["attemptedSourceEvaluations"], nth)
                self.assertAlmostEqual(progress["lastAcceptedTime_s"], (nth-1)*1e-6)
                self.assertEqual(progress["stage"], "failed")

    def test_first_and_nth_boiling_stop_preserves_last_valid_clock(self):
        for nth in (1, 3):
            with self.subTest(nth=nth):
                material = dict(self.m)
                # Deliberately low injected validity boundary isolates STOP accounting.
                material["boiling_K"] = self.p["preheat_C"]+273.15+(nth-.5)*20.
                tracker = CpuRunProgress()
                with self.forcing(heating_K=20.):
                    with self.assertRaisesRegex(ValueError, "boiling limit") as caught:
                        lpbf_simulation.transient(self.p, material, run_progress=tracker)
                self.assertEqual(caught.exception.progress["acceptedSteps"], nth-1)
                self.assertAlmostEqual(caught.exception.progress["lastAcceptedTime_s"], (nth-1)*1e-6)

    def test_source_exception_counts_attempted_evaluation_without_acceptance(self):
        tracker = CpuRunProgress()
        with self.forcing(source_failure=2):
            with self.assertRaisesRegex(ValueError, "injected source") as caught:
                self.transient(tracker)
        self.assertEqual(caught.exception.progress["acceptedSteps"], 1)
        self.assertEqual(caught.exception.progress["attemptedSourceEvaluations"], 2)
        self.assertEqual(caught.exception.progress["sourceEvaluationFailures"], 1)

    def test_local_observer_failure_is_after_valid_acceptance(self):
        tracker = CpuRunProgress()
        def fail(_record):
            raise LookupError("injected local callback")
        with self.forcing():
            with self.assertRaisesRegex(LookupError, "local callback") as caught:
                self.transient(tracker, local_history_observer=fail,
                               local_history_indices_ijk=((0, 0, 2),))
        self.assertEqual(caught.exception.progress["acceptedSteps"], 1)
        self.assertEqual(caught.exception.progress["lastAcceptedDt_s"], 1e-6)

    def test_progress_observer_failure_does_not_lose_committed_step(self):
        def observer(record):
            if record["acceptedSteps"]:
                raise LookupError("injected progress callback")
        tracker = CpuRunProgress(observer=observer)
        with self.forcing():
            with self.assertRaisesRegex(LookupError, "progress callback") as caught:
                self.transient(tracker)
        self.assertEqual(caught.exception.progress["acceptedSteps"], 1)
        self.assertIsNone(current_progress())

    def test_source_retry_budget_stops_before_next_integrated_evaluation(self):
        tracker = CpuRunProgress(maximum_source_evaluations=1)
        with self.forcing(heating_K=100.) as context:
            with self.assertRaisesRegex(RuntimeError, "source-evaluation budget") as caught:
                self.transient(tracker)
        self.assertEqual(context["calls"], 1)
        self.assertEqual(caught.exception.progress["attemptedSourceEvaluations"], 1)
        self.assertEqual(caught.exception.progress["sourceEvaluationRetries"], 0)
        self.assertEqual(caught.exception.progress["acceptedSteps"], 0)

    def test_source_cell_work_budget_stops_before_first_evaluation(self):
        tracker = CpuRunProgress(maximum_source_cell_steps=7)
        with self.forcing() as context:
            with self.assertRaisesRegex(RuntimeError, "source cell-step budget") as caught:
                self.transient(tracker)
        self.assertEqual(context["calls"], 0)
        self.assertEqual(caught.exception.progress["attemptedSourceEvaluations"], 0)

    def test_real_internal_retry_success_counts_additional_source_work(self):
        tracker = CpuRunProgress()
        with self.forcing(heating_K=lambda n: 100. if n == 1 else 0.) as context:
            self.transient(tracker)
        progress = tracker.snapshot()
        self.assertEqual(progress["sourceEvaluationRetries"], 1)
        self.assertEqual(progress["attemptedSourceEvaluations"], progress["acceptedSteps"]+1)
        self.assertEqual(progress["attemptedSourceCellSteps"], context["calls"]*8)

    def test_exception_on_internal_retry_preserves_attempt_and_retry_counts(self):
        tracker = CpuRunProgress()
        with self.forcing(heating_K=100., source_failure=2):
            with self.assertRaisesRegex(ValueError, "injected source") as caught:
                self.transient(tracker)
        progress = caught.exception.progress
        self.assertEqual(progress["acceptedSteps"], 0)
        self.assertEqual(progress["attemptedSourceEvaluations"], 2)
        self.assertEqual(progress["sourceEvaluationRetries"], 1)
        self.assertEqual(progress["sourceEvaluationFailures"], 1)

    def test_selected_event_callback_failure_keeps_raw_and_scheduler_clocks(self):
        event = lpbf_simulation.scan_segments(self.p)[1]
        tracker = CpuRunProgress()
        def fail(_state):
            raise LookupError("injected selected-time callback")
        with self.forcing():
            with self.assertRaisesRegex(LookupError, "selected-time callback") as caught:
                self.transient(tracker, selected_time_observer=fail, selected_time_s=event)
        progress = caught.exception.progress
        self.assertEqual(progress["acceptedSteps"], 100)
        self.assertEqual(progress["lastAcceptedSchedulerTime_s"], event)
        self.assertAlmostEqual(progress["lastAcceptedTime_s"], event, delta=1e-14)

    def test_reusing_tracker_does_not_corrupt_completed_snapshot(self):
        tracker = CpuRunProgress()
        with self.forcing():
            self.transient(tracker)
        previous = tracker.snapshot()
        with self.forcing() as context:
            with self.assertRaisesRegex(ValueError, "single-use"):
                self.transient(tracker)
        self.assertEqual(context["calls"], 0)
        self.assertEqual(tracker.snapshot(), previous)

    def test_public_run_rejects_progress_for_unsupported_backend_before_dispatch(self):
        for backend in ("torch-cuda", "warp-cuda", "openfoam-thermal"):
            with self.subTest(backend=backend):
                with self.assertRaises(ValueError):
                    lpbf_simulation.run({**self.p, "backend": backend}, run_progress=CpuRunProgress())


if __name__ == "__main__":
    unittest.main()
