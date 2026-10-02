import ast
import re
import unittest
from unittest.mock import patch
from pathlib import Path

from lpbf_simulation import (
    IMPLEMENTATION_SOURCE_FILES,
    _fingerprint_implementation_sources,
    _fingerprint_manifest_entries,
    implementation_fingerprint,
    fingerprint,
    validate,
)


class ImplementationFingerprintTests(unittest.TestCase):
    def test_manifest_excludes_worker_test_and_diagnostic_runner(self):
        self.assertNotIn("lpbf_worker.py", IMPLEMENTATION_SOURCE_FILES)
        self.assertNotIn("test_lpbf_execution_scope.py", IMPLEMENTATION_SOURCE_FILES)
        self.assertNotIn("run_lpbf_accepted_dt_diagnostic.py", IMPLEMENTATION_SOURCE_FILES)
        self.assertFalse(any(Path(item).name.startswith("test_")
                             for item in IMPLEMENTATION_SOURCE_FILES))

    def test_manifested_production_source_changes_hash(self):
        before = _fingerprint_manifest_entries([("solver.py", b"value = 1\n")], "solver-v1")
        after = _fingerprint_manifest_entries([("solver.py", b"value = 2\n")], "solver-v1")
        self.assertNotEqual(before, after)

    def test_missing_or_duplicate_manifest_paths_fail_closed(self):
        root = Path(__file__).parent
        with self.assertRaises(FileNotFoundError):
            _fingerprint_implementation_sources(root, ("missing.py",), "solver-v1")
        with self.assertRaises(ValueError):
            _fingerprint_implementation_sources(
                root, ("solver.py", "solver.py"), "solver-v1")

    def test_manifest_covers_static_local_python_import_closure(self):
        python_root = Path(__file__).parent
        manifested = {Path(item).stem for item in IMPLEMENTATION_SOURCE_FILES
                      if item.endswith(".py")}
        for relative in IMPLEMENTATION_SOURCE_FILES:
            if not relative.endswith(".py"):
                continue
            path = python_root / relative
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                imported = []
                if isinstance(node, ast.Import):
                    imported.extend(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    imported.append(node.module.split(".")[0])
                for module in imported:
                    if (python_root / f"{module}.py").is_file():
                        self.assertIn(module, manifested,
                                      f"{relative} imports unmanifested local module {module}")

    def test_manifest_covers_checked_in_openfoam_includes(self):
        source_root = Path(__file__).parent
        manifested = {Path(item).as_posix() for item in IMPLEMENTATION_SOURCE_FILES}
        for relative in IMPLEMENTATION_SOURCE_FILES:
            if not relative.endswith(".C"):
                continue
            source = source_root / relative
            for include in re.findall(r'^\s*#include\s+"([^"]+)"',
                                      source.read_text(encoding="utf-8"), re.MULTILINE):
                local_header = (source.parent / include).resolve()
                if local_header.is_file():
                    self.assertIn(local_header.relative_to(source_root.resolve()).as_posix(),
                                  manifested,
                                  f"{relative} includes unmanifested local source {include}")

    def test_production_helper_changes_bind_implementation_and_cache_identity(self):
        root = Path(__file__).parent
        helpers = ("lpbf_evaporation_marangoni.py", "lpbf_gpu_pilot_artifacts.py",
                   "lpbf_gpu_pilot_numerics.py", "lpbf_run_progress.py")
        p, material = validate({"mode": "standard", "backend": "reference"})
        implementation_before = implementation_fingerprint()
        cache_before = fingerprint(p, material)
        read_bytes = Path.read_bytes
        for relative in helpers:
            with self.subTest(helper=relative):
                self.assertIn(relative, IMPLEMENTATION_SOURCE_FILES)
                target = (root / relative).resolve()
                def changed_content(path):
                    content = read_bytes(path)
                    return content+b"\n# identity mutation oracle\n" if path.resolve() == target else content
                with patch.object(Path, "read_bytes", changed_content):
                    self.assertNotEqual(implementation_fingerprint(), implementation_before)
                    self.assertNotEqual(fingerprint(p, material), cache_before)

    def test_public_fingerprint_is_stable_and_sha256_shaped(self):
        self.assertRegex(implementation_fingerprint(), r"^[0-9a-f]{64}$")
        self.assertEqual(implementation_fingerprint(), implementation_fingerprint())


if __name__ == "__main__":
    unittest.main()
