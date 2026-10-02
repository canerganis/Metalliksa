"""The worker explains a failed CPU solve without publishing a result."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import lpbf_worker as worker


def failed_progress():
    return dict(schemaVersion=1, scope="cpu-reference", stage="failed",
                acceptedSteps=2, lastAcceptedTime_s=2e-8,
                lastAcceptedSchedulerTime_s=2e-8, lastAcceptedDt_s=1e-8,
                attemptedSourceEvaluations=4, sourceEvaluationRetries=1,
                attemptedSourceCellSteps=400, sourceEvaluationFailures=0,
                cells=100, failureType="ValueError", reason="Boiling limit")


class WorkerRunProgressTests(unittest.TestCase):
    def test_only_supported_cpu_single_solves_get_tracker(self):
        raw = dict(mode="standard", backend="reference", study="none")
        self.assertIsNotNone(worker._cpu_run_progress_for(raw))
        self.assertIsNotNone(worker._cpu_run_progress_for({**raw, "backend": "auto"}))
        for key, value in (("mode", "screening"), ("mode", "high-fidelity"),
                           ("backend", "openfoam-thermal"),
                           ("study", "mesh"), ("study", "timestep"),
                           ("thermalModelId", "layered-plate-enthalpy-v1")):
            with self.subTest(key=key, value=value):
                self.assertIsNone(worker._cpu_run_progress_for({**raw, key: value}))

    def test_failure_message_uses_last_valid_accepted_state(self):
        error = ValueError("Boiling limit")
        error.progress = failed_progress()
        text = worker._cpu_failure_progress_message(error)
        self.assertIn("2 accepted steps", text)
        self.assertIn("2e-08 s", text)
        self.assertIn("4 source evaluations", text)
        self.assertIn("1 retries", text)
        self.assertIn("400 source cell-evaluations", text)
        self.assertIn("No completed result", text)

    def test_legacy_or_unsupported_errors_do_not_gain_progress_claim(self):
        error = ValueError("Legacy failure")
        self.assertIsNone(worker._cpu_failure_progress_message(error))
        for changes in (dict(scope="cuda"), dict(stage="completed"), dict(schemaVersion=True),
                        dict(acceptedSteps=True), dict(lastAcceptedTime_s=float("nan")),
                        dict(attemptedSourceCellSteps=-1), dict(acceptedSteps=9),
                        dict(lastAcceptedDt_s=None)):
            with self.subTest(changes=changes):
                error.progress = {**failed_progress(), **changes}
                self.assertIsNone(worker._cpu_failure_progress_message(error))

    def test_zero_step_failure_is_reported_without_last_dt(self):
        error = ValueError("Failed at first source")
        error.progress = {**failed_progress(), "acceptedSteps": 0,
                          "lastAcceptedTime_s": 0., "lastAcceptedSchedulerTime_s": 0.,
                          "lastAcceptedDt_s": None}
        self.assertIn("0 accepted steps", worker._cpu_failure_progress_message(error))

    def test_worker_failure_consumes_tracker_and_never_writes_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "input.json").write_text(json.dumps(
                dict(mode="standard", backend="reference", study="none")))
            (folder / "capabilities.json").write_text("{}")
            error = ValueError("Boiling limit")
            error.progress = failed_progress()
            output = io.StringIO()
            with patch.object(worker.sys, "argv", ["worker", "--execute", str(folder)]), \
                    patch.object(worker, "run", side_effect=error) as solve, \
                    contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as stop:
                worker.main()
            self.assertEqual(stop.exception.code, 1)
            self.assertIsNotNone(solve.call_args.kwargs["run_progress"])
            self.assertIn("Boiling limit", output.getvalue())
            self.assertIn("2 accepted steps", output.getvalue())
            self.assertFalse((folder / "result.json").exists())
            self.assertFalse((folder / "result.tmp").exists())

    def test_unsupported_worker_path_keeps_legacy_signature_and_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "input.json").write_text(json.dumps(dict(mode="screening", backend="auto")))
            (folder / "capabilities.json").write_text("{}")
            output = io.StringIO()
            with patch.object(worker.sys, "argv", ["worker", "--execute", str(folder)]), \
                    patch.object(worker, "run", side_effect=ValueError("Legacy failure")) as solve, \
                    contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
                worker.main()
            self.assertEqual(solve.call_args.kwargs, {})
            self.assertEqual(output.getvalue(), "Legacy failure\n")

    def test_postprocessing_failure_retains_completed_thermal_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "input.json").write_text(json.dumps(
                dict(mode="standard", backend="reference", study="none")))
            (folder / "capabilities.json").write_text("{}")
            error = ValueError("Result audit failed")
            def solve(*args, run_progress, **kwargs):
                run_progress.begin()
                run_progress.set_cells(100)
                run_progress.before_source_evaluation(0)
                run_progress.accept(1e-8, 1e-8, 1e-8)
                run_progress.complete()
                raise error
            output = io.StringIO()
            with patch.object(worker.sys, "argv", ["worker", "--execute", str(folder)]), \
                    patch.object(worker, "run", side_effect=solve), \
                    contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
                worker.main()
            self.assertIn("Result audit failed", output.getvalue())
            self.assertIn("1 accepted steps", output.getvalue())
            self.assertEqual(error.progress["stage"], "failed")
            self.assertEqual(error.progress["failureStage"], "postprocessing")
            self.assertFalse((folder / "result.json").exists())
            self.assertFalse((folder / "result.tmp").exists())


if __name__ == "__main__":
    unittest.main()
