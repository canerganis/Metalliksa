"""The CPU worker must survive absent optional backends. No solver is mocked."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class OptionalBackends(unittest.TestCase):
    def test_missing_gpu_backends_do_not_disable_cpu_rpc(self):
        worker = Path(__file__).with_name("lpbf_worker.py")
        # Simulate missing installations, even on a GPU developer machine.
        script = (
            "import sys, runpy; sys.modules['warp'] = None; "
            "sys.modules['torch'] = None; "
            f"sys.path.insert(0, {str(worker.parent)!r}); "
            f"runpy.run_path({str(worker)!r}, run_name='__main__')"
        )
        messages = [
            {"id": 1, "method": "capabilities", "payload": None},
            {"id": 2, "method": "keyhole-raytracing", "payload": {}},
            {"id": 3, "method": "modulus-fno", "payload": {}},
            {"id": 4, "method": "transient-3d-gpu", "payload": {}},
            {"id": 5, "method": "estimate", "payload": {"mode": "standard", "backend": "reference"}},
        ]
        with tempfile.TemporaryDirectory() as root:
            result = subprocess.run(
                [sys.executable, "-B", "-c", script],
                input="".join(json.dumps(message) + "\n" for message in messages),
                capture_output=True, text=True, timeout=30,
                env={**os.environ, "METALLIKSA_JOB_ROOT": root},
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        replies = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual([reply["id"] for reply in replies], [1, 2, 3, 4, 5])
        self.assertTrue(replies[0]["data"]["thermalSolver"])
        inventories = replies[0]["data"]["gpuDevices"]
        self.assertEqual(set(inventories), {"torch", "warp"})
        for inventory in inventories.values():
            self.assertFalse(inventory["runtimeAvailable"])
            self.assertEqual(inventory["devices"], [])
        for reply, dependency in zip(replies[1:4], ("warp", "torch", "warp")):
            self.assertNotIn("data", reply)
            self.assertIn(dependency, reply["error"])
        self.assertNotIn("error", replies[4])
        self.assertIsInstance(replies[4]["data"], dict)
        self.assertTrue(replies[4]["data"])


if __name__ == "__main__":
    unittest.main()
