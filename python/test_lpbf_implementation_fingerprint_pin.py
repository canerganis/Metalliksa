"""Pin of the real LPBF implementation fingerprint (design 5c, stage P1).

python/lpbf_implementation_fingerprint.expected holds the one accepted value of
lpbf_simulation.implementation_fingerprint(). Any edit to a file listed in
IMPLEMENTATION_SOURCE_FILES, to the manifest itself or to VERSION changes the
fingerprint and fails this test, so an unplanned bump can no longer slip through
on the manual lane check alone.

Procedure for a planned bump (design 3.2/3.3, stage B; section 8 for planned drift), and
for nothing else.
All parity commands must run in the recorded environment (the reference machine and the
locked .runtime/lpbf-win-py312 interpreter; tools/lpbf_parity_check.py skips, it does not
pass, when the environment differs).
1. Before any manifest edit, on the pre-bump commit:
       python -B tools/lpbf_parity_check.py --check --slow                   (all PASS)
       python -B tools/lpbf_bump_record.py --out <scratch>/before.json
2. Make the cleanup commits B1-B5 on ONE bump branch. From the first B commit until
   B6 THIS PIN TEST IS RED on that branch (the fingerprint has moved, the pin has not),
   so Phase B lands on main only as ONE atomic merge after B6; no B commit is merged
   alone. Gate every B commit with
       python -B tools/lpbf_parity_check.py --check --expect-unpinned        (fast cases)
   which treats only the pin mismatch as a warning; observation diffs and a result
   implementationHash != implementation_fingerprint() still fail. Add --slow (G2,
   real bare-plate fixture) at B1, B3, B4, B5 and B6. A corrected-physics bump that is
   MEANT to change results adds --expect-drift with the narrowest allowlist
   (CASE:KEY_GLOB entries; whole cases only outside g1/g2/g4): every other diff, every
   identity digest and all g1/g2/g4 numerics still fail, and an entry without drift
   fails as stale.
3. In the bookkeeping commit (B6) write the new value into
   lpbf_implementation_fingerprint.expected (one lowercase hex line), then run
       python -B -m unittest test_lpbf_implementation_fingerprint_pin       (green again)
       python -B tools/lpbf_parity_check.py --check --slow [--expect-drift ...]
   (all PASS, or DRIFT only where allowed; the tool reports "implementationHash
   differs from the recording: bump")
       python -B tools/lpbf_bump_record.py --from-revision <pre-bump sha>
           --with-parity-check --slow [--expect-drift ...]
           --out ../docs/LPBF_IMPLEMENTATION_BUMP_<date>.json
   (one command line, the same allowlist; every case PASS or DRIFT, none SKIP; the
   record carries each drifted observation's before -> after and raw values: that is
   the numeric drift report)
4. Never re-record the parity goldens in the bump: they are the pre-bump side of
   the proof. After the atomic merge, re-record the goldens at the new fingerprint in
   a separate commit of their own (record twice; only the drifted observations and
   the recording metadata may change), as B5 step 2 did for edddf0dc. Never edit this
   file to make an unexplained fingerprint pass.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lpbf_fingerprint_pin import EXPECTED_FINGERPRINT_FILE, read_pinned_fingerprint
from lpbf_simulation import IMPLEMENTATION_SOURCE_FILES, VERSION, implementation_fingerprint

HERE = Path(__file__).resolve().parent


def pinned_fingerprint():
    # The one strict parser, shared with tools/lpbf_parity_check.py and tools/lpbf_bump_record.py.
    return read_pinned_fingerprint(EXPECTED_FINGERPRINT_FILE)


class ImplementationFingerprintPinTests(unittest.TestCase):
    def test_expected_file_is_one_lowercase_sha256_line(self):
        self.assertRegex(pinned_fingerprint(), r"^[0-9a-f]{64}$")

    def test_strict_parser_rejects_anything_but_one_hex_line(self):
        good = "a" * 64
        cases = ((good + "\n", True), (good + "\r\n", True), (good, False),
                 (good.upper() + "\n", False), (" " + good + "\n", False),
                 (good + "\n\n", False), ("a" * 63 + "\n", False),
                 (good + "\n" + good + "\n", False), ("\ufeff" + good + "\n", False))
        base = HERE.parent / ".tmp-lpbf-pin-parser"
        base.mkdir(exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(dir=base) as directory:
                path = Path(directory) / "pin.expected"
                for content, ok in cases:
                    with self.subTest(content=content):
                        path.write_bytes(content.encode("utf-8"))
                        if ok:
                            self.assertEqual(read_pinned_fingerprint(path), good)
                        else:
                            with self.assertRaises(ValueError):
                                read_pinned_fingerprint(path)
        finally:
            shutil.rmtree(base, ignore_errors=True)

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
