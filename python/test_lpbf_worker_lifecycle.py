"""Deterministic queue lifecycle tests; child processes and CUDA execution are controlled."""
import ctypes
import json
import io
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, call, patch

from lpbf_gpu_thermal import PILOT_JOB_TYPE
from lpbf_worker import Queue, _WindowsJobChild, _spawn_windows_job_child


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
        self.kill_error = None
        self.exit_on_kill_error = False
        self.wait_timeouts = []
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
        if self.kill_error:
            if self.exit_on_kill_error:
                self.returncode = 0
            raise self.kill_error
        if self.on_kill:
            self.on_kill()
        self.killed = True
        self.returncode = -9

    def wait(self, timeout=None):
        self.waited = True
        self.wait_timeouts.append(timeout)
        return self.returncode


class ResumeFailureChild(_WindowsJobChild):
    def __init__(self, failed_kills):
        self.pid = 1234
        self.returncode = None
        self.failed_kills = failed_kills
        self.kill_attempts = 0
        self.wait_timeouts = []
        self.final_kill_started = threading.Event()
        self.allow_final_kill = threading.Event()

    def resume(self):
        raise OSError("ResumeThread failed")

    def poll(self):
        return self.returncode

    def kill(self):
        self.kill_attempts += 1
        if self.kill_attempts <= self.failed_kills:
            raise PermissionError(5, "Access is denied")
        self.final_kill_started.set()
        if not self.allow_final_kill.wait(timeout=3):
            raise TimeoutError("test did not release final termination")
        self.returncode = -9

    def wait(self, timeout=None):
        self.wait_timeouts.append(timeout)
        return self.returncode


class QueueLifecycle(unittest.TestCase):
    def test_resume_failure_keeps_job_running_until_child_cleanup_is_confirmed(self):
        with tempfile.TemporaryDirectory() as root, isolated_queue(root) as queue:
            submitted = submit_gpu(queue)
            job = submitted["id"]
            child = ResumeFailureChild(failed_kills=2)
            with patch("lpbf_worker._spawn_execution_child", return_value=child):
                queue.thread = threading.Thread(target=queue.work, daemon=True)
                queue.thread.start()
                self.assertTrue(child.final_kill_started.wait(timeout=3),
                                "worker did not retry child termination")
                self.assertEqual(queue.get(job)["status"], "running",
                                 "failed ResumeThread cleanup must not become terminal")
                self.assertIs(queue.children.get(job), child)
                self.assertEqual(child.kill_attempts, 3)
                self.assertEqual(child.wait_timeouts, [])
                child.allow_final_kill.set()

                deadline = time.monotonic() + 3
                while queue.get(job)["status"] == "running" and time.monotonic() < deadline:
                    time.sleep(0.01)
                queue.close()

            self.assertEqual(queue.get(job)["status"], "failed")
            self.assertNotIn(job, queue.children)
            self.assertEqual(child.wait_timeouts, [5])

    @unittest.skipUnless(os.name == "nt", "Windows Job Object API contract")
    def test_resume_thread_failure_reaps_process_before_closing_owned_handles(self):
        api = Mock()
        api.ResumeThread.return_value = 0xFFFFFFFF
        api.TerminateJobObject.return_value = 1
        api.WaitForSingleObject.side_effect = [0, 0, 0]
        api.CloseHandle.return_value = 1

        def set_exit_code(_process_handle, code_pointer):
            ctypes.cast(code_pointer, ctypes.POINTER(ctypes.c_ulong)).contents.value = 23
            return 1

        api.GetExitCodeProcess.side_effect = set_exit_code
        child = _WindowsJobChild(11, 22, 33, 44)
        with patch("lpbf_worker.ctypes.WinDLL", return_value=api), \
             patch("lpbf_worker.ctypes.get_last_error", return_value=5), \
             patch("lpbf_worker.ctypes.WinError", side_effect=lambda code: OSError(code, "injected WinAPI failure")):
            with self.assertRaisesRegex(OSError, "injected WinAPI failure"):
                child.resume()

        self.assertEqual(child.returncode, 23)
        self.assertEqual(api.ResumeThread.call_args, call(33))
        api.TerminateJobObject.assert_called_once_with(22, 1)
        self.assertEqual([entry.args for entry in api.CloseHandle.call_args_list], [(22,), (33,), (11,)])
        self.assertIsNone(child._job_handle)
        self.assertIsNone(child._thread_handle)
        self.assertIsNone(child._process_handle)

    @unittest.skipUnless(os.name == "nt", "Windows Job Object API contract")
    def test_close_handle_failure_preserves_handle_and_exit_state_for_retry(self):
        api = Mock()
        api.WaitForSingleObject.return_value = 0
        api.CloseHandle.side_effect = [1, 0, 1, 1]

        def set_exit_code(_process_handle, code_pointer):
            ctypes.cast(code_pointer, ctypes.POINTER(ctypes.c_ulong)).contents.value = 37
            return 1

        api.GetExitCodeProcess.side_effect = set_exit_code
        child = _WindowsJobChild(11, 22, 33, 44)
        with patch("lpbf_worker.ctypes.WinDLL", return_value=api), \
             patch("lpbf_worker.ctypes.get_last_error", return_value=6), \
             patch("lpbf_worker.ctypes.WinError", side_effect=lambda code: OSError(code, "injected close failure")):
            with self.assertRaisesRegex(OSError, "injected close failure"):
                child.poll()
            self.assertIsNone(child.returncode)
            self.assertIsNone(child._job_handle)
            self.assertEqual(child._thread_handle, 33)
            self.assertEqual(child._process_handle, 11)

            self.assertEqual(child.poll(), 37)

        self.assertEqual([entry.args for entry in api.CloseHandle.call_args_list],
                         [(22,), (33,), (33,), (11,)])
        self.assertIsNone(child._job_handle)
        self.assertIsNone(child._thread_handle)
        self.assertIsNone(child._process_handle)

    @unittest.skipUnless(os.name == "nt", "Windows Job Object API contract")
    def test_terminate_job_failure_does_not_claim_live_child_is_killed(self):
        api = Mock()
        api.WaitForSingleObject.side_effect = [0x102, 0x102]
        api.TerminateJobObject.return_value = 0
        child = _WindowsJobChild(11, 22, 33, 44)
        with patch("lpbf_worker.ctypes.WinDLL", return_value=api), \
             patch("lpbf_worker.ctypes.get_last_error", return_value=5), \
             patch("lpbf_worker.ctypes.WinError", side_effect=lambda code: OSError(code, "injected terminate failure")):
            with self.assertRaisesRegex(OSError, "injected terminate failure"):
                child.kill()

        api.TerminateJobObject.assert_called_once_with(22, 1)
        self.assertIsNone(child.returncode)
        self.assertEqual((child._process_handle, child._job_handle, child._thread_handle), (11, 22, 33))
        self.assertEqual([entry.args for entry in api.WaitForSingleObject.call_args_list],
                         [(11, 0), (11, 0)])

    @unittest.skipUnless(os.name == "nt", "Windows Job Object API contract")
    def test_wait_api_failure_does_not_mark_child_reaped(self):
        api = Mock()
        api.WaitForSingleObject.return_value = 0xFFFFFFFF
        child = _WindowsJobChild(11, 22, 33, 44)
        with patch("lpbf_worker.ctypes.WinDLL", return_value=api), \
             patch("lpbf_worker.ctypes.get_last_error", return_value=6), \
             patch("lpbf_worker.ctypes.WinError", side_effect=lambda code: OSError(code, "injected wait failure")):
            with self.assertRaisesRegex(OSError, "injected wait failure"):
                child.wait(timeout=0.1)

        self.assertIsNone(child.returncode)
        self.assertEqual((child._process_handle, child._job_handle, child._thread_handle), (11, 22, 33))

    def test_queued_cancel_is_terminal_and_never_launches_child(self):
        with tempfile.TemporaryDirectory() as root, isolated_queue(root) as queue:
            submitted = submit_gpu(queue)
            with patch("lpbf_worker._spawn_execution_child") as spawn_child:
                state = queue.cancel(submitted["id"])
            self.assertEqual(state["status"], "cancelled")
            self.assertEqual(state["error"], "Cancelled by user")
            spawn_child.assert_not_called()

    def test_running_cancel_kills_child_and_preserves_cancelled_status(self):
        with tempfile.TemporaryDirectory() as root, isolated_queue(root) as queue:
            submitted = submit_gpu(queue)
            job = submitted["id"]
            queue.update(job, status="running")
            children = []
            child_started = threading.Event()
            execution_errors = []
            status_seen_at_kill = []

            def spawn(_command, log):
                child = FakeChild(log, on_kill=lambda: status_seen_at_kill.append(queue.get(job)["status"]))
                children.append(child)
                child_started.set()
                return child

            with patch("lpbf_worker._spawn_execution_child", side_effect=spawn):
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

    def test_queue_close_reaps_real_child_before_terminal_state_or_artifacts(self):
        test_root = Path(os.environ.get(
            "METALLIX_LPBF_TEST_ROOT", Path(__file__).resolve().parent / "codex-lpbf-test-tmp"))
        self.assertTrue(test_root.is_dir(), f"test root must exist before the run: {test_root}")
        with tempfile.TemporaryDirectory(prefix="queue-close-", dir=test_root) as root, \
             isolated_queue(root) as queue:
            submitted = submit_gpu(queue)
            job = submitted["id"]
            folder = Path(root) / job
            started = folder / "child-started"
            result = folder / "result.json"
            artifact = folder / "late-artifact.svg"
            payload = (
                "import sys,time; from pathlib import Path; "
                "started,result,artifact=map(Path,sys.argv[1:]); "
                "started.write_text('ready'); time.sleep(30); "
                "result.write_text('{}'); artifact.write_text('late')"
            )
            children = []
            status_at_kill = []
            status_at_reap = []

            def spawn(_command, log):
                command = [sys.executable, "-c", payload, str(started), str(result), str(artifact)]
                if os.name == "nt":
                    child = _spawn_windows_job_child(command, log)
                else:
                    child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                              start_new_session=True)
                original_kill = child.kill
                original_wait = child.wait

                def observed_kill():
                    status_at_kill.append(queue.get(job)["status"])
                    return original_kill()

                def observed_wait(timeout=None):
                    code = original_wait(timeout=timeout)
                    status_at_reap.append((queue.get(job)["status"], child.poll(), code))
                    return code

                child.kill = observed_kill
                child.wait = observed_wait
                children.append(child)
                return child

            with patch("lpbf_worker._spawn_execution_child", side_effect=spawn):
                queue.thread = threading.Thread(target=queue.work, daemon=True)
                queue.thread.start()
                deadline = time.monotonic() + 10
                while not started.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(started.exists(), "real execution child did not start")
                try:
                    queue.close()
                    self.assertFalse(queue.thread.is_alive(), "queue close returned before its worker exited")
                    self.assertEqual(len(children), 1)
                    self.assertEqual(status_at_kill, ["running"],
                                     "shutdown must not publish terminal state before termination")
                    self.assertTrue(status_at_reap, "shutdown did not wait for the real child")
                    self.assertEqual(status_at_reap[-1][0], "running",
                                     "terminal state was published before the child was reaped")
                    self.assertIsNotNone(status_at_reap[-1][1], "child was still live when wait returned")
                    self.assertEqual(status_at_reap[-1][1], status_at_reap[-1][2])
                    self.assertEqual(queue.get(job)["status"], "failed")
                    self.assertFalse(result.exists(), "shutdown allowed result publication")
                    self.assertFalse(artifact.exists(), "shutdown allowed late artifact publication")
                finally:
                    # Keep test cleanup bounded even when an assertion exposes a shutdown regression.
                    for child in children:
                        if child.poll() is None:
                            child.kill()
                            child.wait(timeout=5)
                    if queue.thread.is_alive():
                        queue.thread.join(timeout=5)
                    self.assertFalse(queue.thread.is_alive(), "test child cleanup did not finish")

    @unittest.skipUnless(os.name == "nt", "Windows Job Object access-denied handling")
    def test_access_denied_keeps_live_child_running_but_signaled_child_can_be_reaped(self):
        job = "c" * 32
        queue = Queue.__new__(Queue)
        queue.lock = threading.RLock()
        state = {"status": "running"}
        child = FakeChild(io.StringIO())
        child.kill_error = PermissionError(5, "Access is denied")
        queue.children = {job: child}
        queue.get = lambda _job: dict(state)
        queue.update = lambda _job, **values: state.update(values)

        with self.assertRaises(PermissionError):
            queue.cancel(job)
        self.assertEqual(state["status"], "running", "a live child must not be persisted as cancelled")
        self.assertIs(queue.children.get(job), child, "a live child must remain registered for recovery")
        self.assertFalse(child.waited)

        child.exit_on_kill_error = True
        result = queue.cancel(job)
        self.assertEqual(result["status"], "cancelled")
        self.assertTrue(child.waited, "signaled child must still be waited/reaped")
        self.assertEqual(child.wait_timeouts, [5])
        self.assertNotIn(job, queue.children)
        child.output.close()

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

            def spawn(_command, log):
                child = FakeChild(log)
                children.append(child)
                return child

            with patch("lpbf_worker._spawn_execution_child", side_effect=spawn):
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

            def spawn(_command, log):
                child = FakeChild(log, returncode=17)
                (Path(root) / job / partial_name).write_text("partial artifact")
                return child

            with patch("lpbf_worker._spawn_execution_child", side_effect=spawn):
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

    @unittest.skipUnless(os.name == "nt", "Windows Job Object hard-crash integration")
    def test_abrupt_parent_death_kills_execute_child_and_prevents_publication(self):
        test_root = Path(os.environ.get(
            "METALLIX_LPBF_TEST_ROOT", Path(__file__).resolve().parent / "codex-lpbf-test-tmp"))
        self.assertTrue(test_root.is_dir(), f"test root must exist before the run: {test_root}")
        with tempfile.TemporaryDirectory(prefix="job-owner-crash-", dir=test_root) as root:
            job = "b" * 32
            folder = Path(root) / job
            folder.mkdir()
            (folder / "input.json").write_text(json.dumps({"mode": "standard", "backend": "cpu"}))
            db = sqlite3.connect(Path(root) / "queue.sqlite")
            try:
                db.execute("CREATE TABLE jobs(id TEXT PRIMARY KEY, cache_key TEXT, status TEXT, progress REAL, log TEXT, error TEXT, created REAL)")
                db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?)", (job, "crash-test", "running", 0., "", None, 1.))
                db.commit()
            finally:
                db.close()
            helper = r'''
import sys, time
from pathlib import Path
from lpbf_worker import _spawn_windows_job_child
folder = Path(sys.argv[1])
payload = "import sys,time; from pathlib import Path; time.sleep(1.2); p=Path(sys.argv[1]); (p/'result.json').write_text('{}'); (p/'orphan-artifact.svg').write_text('orphan')"
with (folder / "progress.log").open("w") as log:
    child = _spawn_windows_job_child([sys.executable, "-c", payload, str(folder)], log)
    child.resume()
    print(child.pid, flush=True)
    time.sleep(60)
'''
            parent = subprocess.Popen([sys.executable, "-c", helper, str(folder)],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      text=True, cwd=str(Path(__file__).resolve().parent))
            pid = None
            child_handle = None
            try:
                ready = threading.Event()
                output = []
                reader = threading.Thread(target=lambda: (output.append(parent.stdout.readline()), ready.set()), daemon=True)
                reader.start()
                self.assertTrue(ready.wait(15), "helper parent did not report its child PID")
                if not output[0].strip():
                    parent.kill()
                    parent.wait(timeout=5)
                    self.fail(f"helper failed to start child: {parent.stderr.read()}")
                pid = int(output[0].strip())
                import ctypes
                kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
                kernel.OpenProcess.restype = ctypes.c_void_p
                kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
                kernel.WaitForSingleObject.restype = ctypes.c_ulong
                kernel.CloseHandle.argtypes = [ctypes.c_void_p]
                child_handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
                self.assertTrue(child_handle, "child PID could not be opened to verify liveness")
                self.assertEqual(kernel.WaitForSingleObject(child_handle, 0), 0x102,
                                 "reported child was not live before parent termination")
                parent.kill()
                parent.wait(timeout=5)
                self.assertEqual(kernel.WaitForSingleObject(child_handle, 5000), 0,
                                 "child survived abrupt Job Object owner death")

                with isolated_queue(root) as queue:
                    state = queue.get(job)
                    self.assertEqual(state["status"], "failed")
                    self.assertEqual(state["error"], "Worker restarted during execution")
                self.assertFalse((folder / "result.json").exists())
                self.assertFalse((folder / "orphan-artifact.svg").exists())
            finally:
                if parent.poll() is None:
                    parent.kill()
                    parent.wait(timeout=5)
                if child_handle:
                    kernel.CloseHandle(child_handle)
                if pid is not None:
                    import ctypes
                    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
                    kernel.OpenProcess.restype = ctypes.c_void_p
                    kernel.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
                    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
                    child_handle = kernel.OpenProcess(0x0001, False, pid)
                    if child_handle:
                        try:
                            kernel.TerminateProcess(child_handle, 1)
                        finally:
                            kernel.CloseHandle(child_handle)
                if parent.stdout:
                    parent.stdout.close()
                if parent.stderr:
                    parent.stderr.close()

    @staticmethod
    def _execute_capture(queue, job, errors):
        try:
            queue.execute(job)
        except Exception as error:
            errors.append(error)


if __name__ == "__main__":
    unittest.main()
