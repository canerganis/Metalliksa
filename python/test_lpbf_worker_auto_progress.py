"""Automatic dispatch progress and worker publication failure fixtures."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import lpbf_worker as worker


def temp_job():
    root = Path(__file__).resolve().parents[1] / ".tmp-lpbf-worker-auto-progress-fixtures"
    root.mkdir(exist_ok=True)
    return tempfile.TemporaryDirectory(dir=root)


def prepare(folder, settings, caps):
    (folder / "input.json").write_text(json.dumps(settings), encoding="utf-8")
    (folder / "capabilities.json").write_text(json.dumps(caps), encoding="utf-8")


def completed_thermal_work(progress):
    progress.begin()
    progress.set_cells(100)
    progress.before_source_evaluation(0)
    progress.accept(1e-8, 1e-8, 1e-8)
    progress.complete()


class WorkerAutomaticProgressTests(unittest.TestCase):
    def test_tracker_candidate_matches_existing_automatic_dispatch_edges(self):
        standard = dict(mode="standard", backend="auto", study="none")
        for changes, caps, supported in (
            ({}, {}, True),
            ({}, {"openfoamThermal": True}, True),
            ({"powderGridPolicy": "layer-conforming"}, {}, False),
            ({"powderGridPolicy": "layer-conforming"}, {"openfoamThermal": True}, False),
            ({"surfaceMode": "bare-plate"}, {}, False),
            ({"surfaceMode": "bare-plate"}, {"openfoamThermal": True}, False),
            ({"backend": "reference"}, {"openfoamThermal": True}, True),
            ({"backend": "openfoam-thermal"}, {}, False),
            ({"mode": "screening"}, {}, False),
            ({"mode": "calibration"}, {}, False),
            ({"study": "mesh"}, {}, False),
            ({"thermalModelId": "layered-plate-enthalpy-v1"}, {}, False),
        ):
            with self.subTest(changes=changes, caps=caps):
                tracker = worker._cpu_run_progress_for({**standard, **changes}, caps)
                self.assertEqual(tracker is not None, supported)

    def test_automatic_cpu_failure_carries_work_without_publishing_result(self):
        with temp_job() as directory:
            folder = Path(directory)
            prepare(folder, dict(mode="standard", backend="auto", study="none"), {})
            error = ValueError("Automatic CPU failed after accepted work")

            def solve(*args, run_progress, **kwargs):
                self.assertEqual(args[3], {})
                completed_thermal_work(run_progress)
                raise error

            output = io.StringIO()
            with patch.object(worker.sys, "argv", ["worker", "--execute", str(folder)]), \
                    patch.object(worker, "run", side_effect=solve) as call, \
                    contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as stop:
                worker.main()
            self.assertEqual(stop.exception.code, 1)
            self.assertIsNotNone(call.call_args.kwargs["run_progress"])
            self.assertIn("1 accepted steps", output.getvalue())
            self.assertEqual(error.progress["failureStage"], "postprocessing")
            self.assertFalse((folder / "result.json").exists())
            self.assertFalse((folder / "result.tmp").exists())

    def test_explicit_openfoam_path_keeps_legacy_signature_and_error(self):
        with temp_job() as directory:
            folder = Path(directory)
            settings = dict(mode="standard", backend="openfoam-thermal", study="none",
                            surfaceMode="powder-layer")
            caps = {"openfoamThermal": True}
            prepare(folder, settings, caps)
            output = io.StringIO()
            with patch.object(worker.sys, "argv", ["worker", "--execute", str(folder)]), \
                    patch.object(worker, "run", side_effect=ValueError("OpenFOAM failed")) as call, \
                    contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
                worker.main()
            self.assertEqual(call.call_args.kwargs, {})
            self.assertEqual(call.call_args.args[3], caps)
            self.assertEqual(output.getvalue(), "OpenFOAM failed\n")
            self.assertFalse((folder / "result.json").exists())

    def test_publication_failure_after_return_retains_completed_work(self):
        with temp_job() as directory:
            folder = Path(directory)
            prepare(folder, dict(mode="standard", backend="auto", study="none"), {})
            error = OSError("Injected result publication failure")

            def solve(*args, run_progress, **kwargs):
                completed_thermal_work(run_progress)
                return {"provenance": {}}

            original_write = Path.write_text

            def reject_result(path, *args, **kwargs):
                if path == folder / "result.tmp":
                    raise error
                return original_write(path, *args, **kwargs)

            output = io.StringIO()
            with patch.object(worker.sys, "argv", ["worker", "--execute", str(folder)]), \
                    patch.object(worker, "run", side_effect=solve), \
                    patch.object(Path, "write_text", reject_result), \
                    contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
                worker.main()
            self.assertIn("Injected result publication failure", output.getvalue())
            self.assertIn("1 accepted steps", output.getvalue())
            self.assertEqual(error.progress["failureStage"], "postprocessing")
            self.assertFalse((folder / "result.json").exists())

    def test_invalid_capability_file_does_not_claim_started_cpu_work(self):
        with temp_job() as directory:
            folder = Path(directory)
            prepare(folder, dict(mode="standard", backend="auto", study="none"), {})
            (folder / "capabilities.json").write_text("{", encoding="utf-8")
            output = io.StringIO()
            with patch.object(worker.sys, "argv", ["worker", "--execute", str(folder)]), \
                    patch.object(worker, "run") as call, \
                    contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
                worker.main()
            call.assert_not_called()
            self.assertNotIn("accepted steps", output.getvalue())
            self.assertFalse((folder / "result.json").exists())


if __name__ == "__main__":
    unittest.main()
