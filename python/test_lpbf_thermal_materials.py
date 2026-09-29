"""Real worker boundary checks: material identity must survive thermal requests."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class ThermalMaterialContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        names = ["IN718", " Inconel 718 ", "316L", "AlSi10Mg", "Ti64",
                 "unobtainium", "", None]
        payloads = [{"material": {"name": name}, "config": {"numTracks": 2}}
                    for name in names]
        payloads.append({"config": {"numTracks": 2}})
        messages = [{"id": i, "method": "thermal-accumulation", "payload": p}
                    for i, p in enumerate(payloads)]
        messages.append({"id": 9, "method": "capabilities", "payload": None})
        with tempfile.TemporaryDirectory() as root:
            result = subprocess.run(
                [sys.executable, "-B", str(Path(__file__).with_name("lpbf_worker.py"))],
                input="".join(json.dumps(m) + "\n" for m in messages),
                capture_output=True, text=True, timeout=30,
                env={**os.environ, "METALLIKSA_JOB_ROOT": root},
            )
        if result.returncode:
            raise AssertionError(result.stderr)
        cls.replies = [
            json.loads(line)
            for line in result.stdout.splitlines()
            if line.strip().startswith("{")
        ]

    def test_alias_uses_same_material_and_result(self):
        self.assertEqual(self.replies[0]["data"], self.replies[1]["data"])
        self.assertEqual(self.replies[0]["data"]["alloy"], "Inconel 718")

    def test_shared_authority_temperature_units(self):
        # Hand-converted shared liquidus/boiling Celsius constants, not legacy presets.
        for index, name, melt, boil in ((0, "Inconel 718", 1609.15, 3123.15),
                                        (2, "316L Stainless Steel", 1673.15, 3087.15),
                                        (3, "AlSi10Mg", 868.15, 2743.15),
                                        (4, "Ti-6Al-4V", 1933.15, 3560.15)):
            with self.subTest(name=name):
                data = self.replies[index]["data"]
                self.assertEqual(data["alloy"], name)
                self.assertAlmostEqual(data["melting_point_K"], melt)
                self.assertAlmostEqual(data["boiling_point_K"], boil)

    def test_unknown_or_missing_identity_is_error_and_worker_survives(self):
        for reply in self.replies[5:9]:
            with self.subTest(reply=reply):
                self.assertNotIn("data", reply)
                self.assertIn("alloy", reply["error"].lower())
        self.assertTrue(self.replies[9]["data"]["thermalSolver"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
