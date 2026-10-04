"""Pin of the real LPBF implementation fingerprint (design 5c, stage P1).

python/lpbf_implementation_fingerprint.expected holds the one accepted value of
lpbf_simulation.implementation_fingerprint(). Any edit to a file listed in
IMPLEMENTATION_SOURCE_FILES, to the manifest itself or to VERSION changes the
fingerprint and fails this test, so an unplanned bump can no longer slip through
on the manual lane check alone.

Procedure for the single planned bump (design 3.2, stage B6), and for nothing else:
1. Before any manifest edit, on the pre-bump commit:
       python -B tools/lpbf_parity_check.py --check --slow      (all PASS)
       python -B tools/lpbf_bump_record.py --out <scratch>/before.json
2. Make the cleanup commits on the bump branch. After each one:
       python -B tools/lpbf_parity_check.py --check             (fast cases PASS;
   only the pin below fails, with the new value printed in its message)
3. In the bookkeeping commit (B6) write the new value into
   lpbf_implementation_fingerprint.expected (one lowercase hex line), then run
       python -B -m unittest test_lpbf_implementation_fingerprint_pin
       python -B tools/lpbf_parity_check.py --check --slow      (all PASS; the
   tool reports "implementationHash differs from the recording: bump")
       python -B tools/lpbf_bump_record.py --from-revision <pre-bump sha> \
           --out ../docs/LPBF_IMPLEMENTATION_BUMP_<date>.json
4. Never re-record the parity goldens in the bump: they are the pre-bump side of
   the proof. Never edit this file to make an unexplained fingerprint pass.
"""

import re
import unittest
from pathlib import Path
from unittest.mock import patch

from lpbf_simulation import IMPLEMENTATION_SOURCE_FILES, VERSION, implementation_fingerprint

HERE = Path(__file__).resolve().parent
EXPECTED_FILE = HERE / "lpbf_implementation_fingerprint.expected"


def pinned_fingerprint():
    text = EXPECTED_FILE.read_bytes().decode("ascii")
    match = re.fullmatch(r"([0-9a-f]{64})\r?\n", text)
    if match is None:
        raise ValueError(f"{EXPECTED_FILE.name} must contain exactly one lowercase sha256 hex line")
    return match.group(1)


class ImplementationFingerprintPinTests(unittest.TestCase):
    def test_expected_file_is_one_lowercase_sha256_line(self):
        self.assertRegex(pinned_fingerprint(), r"^[0-9a-f]{64}$")

    def test_current_implementation_matches_the_pin(self):
        current = implementation_fingerprint()
        self.assertEqual(
            current, pinned_fingerprint(),
            f"LPBF implementation fingerprint changed to {current} (VERSION {VERSION}, "
            f"{len(IMPLEMENTATION_SOURCE_FILES)} manifest entries). Only the planned bump may "
            "update lpbf_implementation_fingerprint.expected; follow the procedure in this "
            "module's docstring.")

    def test_pin_detects_a_one_byte_source_mutation(self):
        # Mutation oracle without touching any manifest file on disk.
        target = (HERE / "lpbf_core_physics.py").resolve()
        self.assertIn("lpbf_core_physics.py", IMPLEMENTATION_SOURCE_FILES)
        self.assertIn(b"SOURCE_QUADRATURE_MAX_ORDER = 256", target.read_bytes())
        read_bytes = Path.read_bytes

        def mutated(path):
            content = read_bytes(path)
            if path.resolve() == target:
                content = content.replace(b"SOURCE_QUADRATURE_MAX_ORDER = 256",
                                          b"SOURCE_QUADRATURE_MAX_ORDER = 257", 1)
            return content

        with patch.object(Path, "read_bytes", mutated):
            self.assertNotEqual(implementation_fingerprint(), pinned_fingerprint())

    def test_pin_detects_a_version_change(self):
        import lpbf_simulation
        with patch.object(lpbf_simulation, "VERSION", VERSION + "-mutated"):
            self.assertNotEqual(lpbf_simulation.implementation_fingerprint(), pinned_fingerprint())


if __name__ == "__main__":
    unittest.main()
