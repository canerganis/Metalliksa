"""Queue timeout defaults must cover supported job types without a timeout field."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from lpbf_worker import Queue, _archive_run_kind


class _CompletedChild:
    returncode = 0

    def __init__(self):
        self.poll_count = 0

    def poll(self):
        self.poll_count += 1
        return None if self.poll_count == 1 else 0

    def wait(self, timeout=None):
        return 0


class WorkerTimeout(unittest.TestCase):
    def test_worker_run_kind_is_explicit_and_keeps_gpu_archive_closed(self):
        self.assertEqual(_archive_run_kind("build-job"), "build-screening")
        self.assertEqual(_archive_run_kind(None), "transient-thermal")
        analytical = {"settings": {"mode": "screening"},
                      "coreContract": {"resolvedPhysics": {"transient": False}}}
        self.assertEqual(_archive_run_kind(None, analytical), "analytical-screening")
        direct_physics = {"settings": {"mode": "screening"}, "resolvedPhysics": {"transient": False}}
        self.assertEqual(_archive_run_kind(None, direct_physics), "analytical-screening")
        self.assertIsNone(_archive_run_kind("gpu-thermal-pilot"))

    def test_build_job_without_timeout_uses_bounded_worker_default(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as root:
            queue = Queue(root=root, start=False)
            job = "a" * 32
            folder = Path(root) / job
            folder.mkdir()
            (folder / "input.json").write_text(json.dumps({"jobType": "build-job"}))
            (folder / "result.json").write_text(json.dumps({"success": True}))
            with queue.connect() as connection:
                connection.execute(
                    "INSERT INTO jobs VALUES (?,?,?,?,?,?,?)",
                    (job, "test-key", "running", 0.0, "", None, time.time()),
                )

            try:
                with patch("lpbf_worker._spawn_execution_child", return_value=_CompletedChild()), \
                     patch("lpbf_worker.enforce_thermal_balances"):
                    queue.execute(job)

                self.assertEqual(queue.get(job)["status"], "completed")
            finally:
                queue.close()


if __name__ == "__main__":
    unittest.main()
