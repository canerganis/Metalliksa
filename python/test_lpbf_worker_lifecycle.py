"""Deterministic queue lifecycle tests; child processes and CUDA execution are controlled."""
import json
import tempfile
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from lpbf_gpu_thermal import PILOT_JOB_TYPE
from lpbf_worker import Queue


GPU_CASE = {
    "jobType": PILOT_JOB_TYPE, "mode": "standard", "backend": "cuda:0",
    "material": "Inconel 718", "power_W": 60, "speed_mm_s": 1200,
    "mesh_um": 40, "maxDt_s": 2e-7, "layer_um": 80,
    "trackLength_um": 200, "cooling_s": 2e-5, "dwell_s": 0,
}


@contextmanager
def isolated_queue(root):
    # Keep the CUDA identity explicit while replacing only the hardware probe and
    # implementation fingerprint; no CPU backend is ever submitted.
    with patch("lpbf_worker.capabilities", return_value={"openfoamVersion": None}), \
         patch("lpbf_worker.fingerprint", return_value="lifecycle-test-fingerprint"), \
         patch("lpbf_gpu_thermal.require_cuda"):
        queue = Queue(root, start=False)
        try:
            yield queue
        finally:
            queue.close()


def submit_gpu(queue):
    return queue.submit(GPU_CASE)


class FakeChild:
    def __init__(self, output, *, returncode=None, on_poll=None, on_kill=None, partial_name=None):
        self.returncode = returncode
        self.on_poll = on_poll
        self.on_kill = on_kill
        self.partial_name = partial_name
        self.output = output
        self.killed = False
        self.waited = False
        self._polled = False
        if partial_name:
            output.write("partial artifact produced before child exit\n")
            output.flush()

    def poll(self):
        if not self._polled and self.on_poll:
            self._polled = True
            self.on_poll()
        return self.returncode

    def kill(self):
        if self.on_kill:
            self.on_kill()
        self.killed = True
        self.returncode = -9

    def wait(self, timeout=None):
        self.waited = True
        return self.returncode


class QueueLifecycle(unittest.TestCase):
    def test_queued_cancel_is_terminal_and_never_launches_child(self):
        with tempfile.TemporaryDirectory() as root, isolated_queue(root) as queue:
            submitted = submit_gpu(queue)
            with patch("lpbf_worker.subprocess.Popen") as popen:
                state = queue.cancel(submitted["id"])
            self.assertEqual(state["status"], "cancelled")
            self.assertEqual(state["error"], "Cancelled by user")
            popen.assert_not_called()

    def test_running_cancel_kills_child_and_preserves_cancelled_status(self):
        with tempfile.TemporaryDirectory() as root, isolated_queue(root) as queue:
            submitted = submit_gpu(queue)
            job = submitted["id"]
            queue.update(job, status="running")
            children = []
            child_started = threading.Event()
            execution_errors = []
            status_seen_at_kill = []

            def spawn(*_args, **kwargs):
                child = FakeChild(kwargs["stdout"], on_kill=lambda: status_seen_at_kill.append(queue.get(job)["status"]))
                children.append(child)
                child_started.set()
                return child

            with patch("lpbf_worker.subprocess.Popen", side_effect=spawn):
                worker = threading.Thread(target=lambda: self._execute_capture(queue, job, execution_errors))
                worker.start()
                self.assertTrue(child_started.wait(timeout=3), "execution child did not start")
                state = queue.cancel(job)
                killed_at_cancel_return = children[0].killed
                reaped_at_cancel_return = children[0].waited
                worker.join(timeout=3)
            self.assertFalse(worker.is_alive(), "execute did not observe cancellation")
            self.assertEqual(execution_errors, [])
            self.assertTrue(killed_at_cancel_return, "cancel returned before the child was terminated")
            self.assertTrue(reaped_at_cancel_return, "cancel returned before the child was reaped")
            self.assertEqual(status_seen_at_kill, ["running"], "cancel became terminal before child termination")
            state = queue.get(job)
            self.assertEqual(state["status"], "cancelled")
            self.assertEqual(len(children), 1)

    def test_forced_timeout_kills_child_and_marks_timed_out(self):
        with tempfile.TemporaryDirectory() as root, isolated_queue(root) as queue:
            submitted = submit_gpu(queue)
            job = submitted["id"]
            queue.update(job, status="running")
            input_path = Path(root) / job / "input.json"
            params = json.loads(input_path.read_text())
            params["timeout_s"] = 0.01
            input_path.write_text(json.dumps(params))
            children = []

            def spawn(*_args, **kwargs):
                child = FakeChild(kwargs["stdout"])
                children.append(child)
                return child

            with patch("lpbf_worker.subprocess.Popen", side_effect=spawn):
                queue.execute(job)
            state = queue.get(job)
            self.assertEqual(state["status"], "timed_out")
            self.assertEqual(state["error"], "Simulation timeout")
            self.assertTrue(children[0].killed)
            self.assertTrue(children[0].waited)

    def test_worker_restart_fails_stale_running_job(self):
        with tempfile.TemporaryDirectory() as root, isolated_queue(root) as queue:
            submitted = submit_gpu(queue)
            queue.update(submitted["id"], status="running")
            queue.close()
            restarted = Queue(root, start=False)
            try:
                state = restarted.get(submitted["id"])
                self.assertEqual(state["status"], "failed")
                self.assertEqual(state["error"], "Worker restarted during execution")
            finally:
                restarted.close()

    def test_same_input_deduplicates_queue_repeat_bypasses_and_cancel_allows_resubmit(self):
        with tempfile.TemporaryDirectory() as root, isolated_queue(root) as queue:
            first = submit_gpu(queue)
            duplicate = submit_gpu(queue)
            repeated = queue.submit(GPU_CASE, execution_scope="repeat")
            self.assertEqual(duplicate["id"], first["id"])
            self.assertTrue(duplicate["deduplicated"])
            self.assertFalse(duplicate["cacheHit"])
            self.assertNotEqual(repeated["id"], first["id"])
            self.assertFalse(repeated["cacheHit"])

            queue.cancel(first["id"])
            replacement = submit_gpu(queue)
            self.assertNotEqual(replacement["id"], first["id"])
            self.assertEqual(replacement["status"], "queued")

    def test_cancel_complete_race_keeps_one_terminal_winner(self):
        with tempfile.TemporaryDirectory() as root, isolated_queue(root) as queue, \
             patch("lpbf_worker.enforce_thermal_balances"):
            # Use a minimal ordinary thermal record here so completed-state
            # get() exercises terminal archive reading without a CUDA solve.
            job = "a" * 32
            folder = Path(root) / job
            folder.mkdir()
            (folder / "input.json").write_text(json.dumps({"mode": "standard", "backend": "cpu"}))
            (folder / "result.json").write_text("{}")
            with queue.connect() as connection:
                connection.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?)",
                    (job, "race-key", "running", 0., "", None, 1.))
            gate = threading.Barrier(3)
            failures = []

            def complete():
                try:
                    gate.wait()
                    queue.finish_running(job, status="completed", progress=1., log="done")
                except Exception as error:  # Report thread assertions in the test thread.
                    failures.append(error)

            def cancel():
                try:
                    gate.wait()
                    queue.cancel(job)
                except Exception as error:
                    failures.append(error)

            threads = [threading.Thread(target=complete), threading.Thread(target=cancel)]
            for thread in threads:
                thread.start()
            gate.wait()
            for thread in threads:
                thread.join(timeout=3)
            self.assertFalse(any(thread.is_alive() for thread in threads))
            self.assertEqual(failures, [])
            with queue.connect() as connection:
                status = connection.execute("SELECT status FROM jobs WHERE id=?", (job,)).fetchone()["status"]
            self.assertIn(status, ("completed", "cancelled"))

    def test_partial_artifact_from_failed_child_is_isolated_from_resubmit(self):
        with tempfile.TemporaryDirectory() as root, isolated_queue(root) as queue:
            submitted = submit_gpu(queue)
            job = submitted["id"]
            queue.update(job, status="running")
            partial_name = "temperature-slice.svg"

            def spawn(*_args, **kwargs):
                child = FakeChild(kwargs["stdout"], returncode=17)
                (Path(root) / job / partial_name).write_text("partial artifact")
                return child

            with patch("lpbf_worker.subprocess.Popen", side_effect=spawn):
                queue.execute(job)
            self.assertEqual(queue.get(job)["status"], "failed")
            self.assertTrue((Path(root) / job / partial_name).exists())
            with self.assertRaisesRegex(ValueError, "Artifact unavailable"):
                queue.artifact({"id": job, "name": partial_name})

            replacement = submit_gpu(queue)
            self.assertNotEqual(replacement["id"], job)
            self.assertFalse((Path(root) / replacement["id"] / partial_name).exists())

    def test_gpu_queue_never_accepts_implicit_or_cpu_fallback_backend(self):
        with tempfile.TemporaryDirectory() as root, \
             patch("lpbf_worker.capabilities", return_value={"openfoamVersion": None}), \
             patch("lpbf_worker.fingerprint", return_value="lifecycle-test-fingerprint"):
            queue = Queue(root, start=False)
            try:
                for backend in ("cpu", "reference", "auto", "cuda", "cuda:-1"):
                    with self.subTest(backend=backend), self.assertRaisesRegex(ValueError, "no CPU fallback"):
                        queue.submit({**GPU_CASE, "backend": backend})
            finally:
                queue.close()

    @staticmethod
    def _execute_capture(queue, job, errors):
        try:
            queue.execute(job)
        except Exception as error:
            errors.append(error)


if __name__ == "__main__":
    unittest.main()
