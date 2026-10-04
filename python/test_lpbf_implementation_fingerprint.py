import ast
import contextlib
import re
import shutil
import tempfile
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

# Local modules that no manifest file may import even if they were manifested:
# design 5c B1 moves the test-only CFD case writers to lpbf_cfd_cases (non-manifest);
# B1' removes the unreachable openfoam-cfd branch from run() and drops lpbf_cfd.py from
# the manifest, so the experimental CFD layer must not be wired back in silently.
FORBIDDEN_MANIFEST_IMPORTS = frozenset({"lpbf_cfd_cases", "lpbf_cfd"})


def _imported_names(tree):
    """Dotted names imported statically, via importlib.import_module/__import__ literals,
    or relatively (returned with their leading dots)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                yield "." * node.level + (node.module or "")
            elif node.module:
                yield node.module
        elif (isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant)
              and isinstance(node.args[0].value, str)):
            func = node.func
            name = (func.attr if isinstance(func, ast.Attribute)
                    else func.id if isinstance(func, ast.Name) else None)
            if name in ("import_module", "__import__"):
                yield node.args[0].value


def unmanifested_local_imports(python_root, manifest):
    """Return (manifest file, module, kind) for each local import outside the manifest.

    Resolution mirrors importlib's path finder for one directory: a regular package
    (<name>/__init__.py) wins over <name>.py, which wins over a namespace directory.
    A package or directory is covered only if every .py file below it is manifested.
    """
    python_root = Path(python_root)
    manifested = {Path(item).as_posix() for item in manifest}
    problems = []
    for relative in manifest:
        if not relative.endswith(".py"):
            continue
        path = python_root / relative
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for name in sorted(set(_imported_names(tree))):
            if name.startswith("."):
                problems.append((relative, ".", "relative import"))
                continue
            top = name.split(".")[0]
            if top in FORBIDDEN_MANIFEST_IMPORTS:
                problems.append((relative, top, "forbidden in manifest"))
            package = python_root / top
            if (package / "__init__.py").is_file() or (
                    package.is_dir() and not (python_root / f"{top}.py").is_file()):
                sources = sorted(p.relative_to(python_root).as_posix() for p in package.rglob("*.py"))
                if not sources or any(source not in manifested for source in sources):
                    kind = "package" if (package / "__init__.py").is_file() else "namespace directory"
                    problems.append((relative, top, kind))
            elif (python_root / f"{top}.py").is_file() and f"{top}.py" not in manifested:
                problems.append((relative, top, "module"))
    return sorted(set(problems))


@contextlib.contextmanager
def _closure_fixture_root():
    base = Path(__file__).resolve().parents[1] / ".tmp-lpbf-closure-fixtures"
    base.mkdir(exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(dir=base) as directory:
            yield Path(directory)
    finally:
        shutil.rmtree(base, ignore_errors=True)


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
        # Covers local modules, regular packages (<name>/__init__.py), namespace
        # directories, importlib/__import__ string literals and relative imports.
        self.assertEqual(
            unmanifested_local_imports(Path(__file__).parent, IMPLEMENTATION_SOURCE_FILES), [])

    def test_closure_checker_detects_packages_directories_and_dynamic_imports(self):
        with _closure_fixture_root() as root:
            files = {
                "solver.py": ("import numpy\nimport leaf\nimport pkgmod.core\n"
                              "from nsdir import helper\nimport importlib\n"
                              "importlib.import_module('dyn')\n__import__('dyn2')\n"
                              "from . import sibling\nimport lpbf_cfd_cases\n"),
                "leaf.py": "VALUE = 1\n",
                "pkgmod/__init__.py": "",
                "pkgmod/core.py": "VALUE = 2\n",
                "nsdir/helper.py": "VALUE = 3\n",
                "dyn.py": "VALUE = 4\n",
                "dyn2.py": "VALUE = 5\n",
                "lpbf_cfd_cases.py": "VALUE = 6\n",
            }
            for relative, text in files.items():
                (root / relative).parent.mkdir(parents=True, exist_ok=True)
                (root / relative).write_text(text, encoding="utf-8")
            problems = unmanifested_local_imports(root, ("solver.py", "leaf.py"))
            flagged = {(module, kind) for _, module, kind in problems}
            self.assertEqual(flagged, {
                ("pkgmod", "package"), ("nsdir", "namespace directory"),
                ("dyn", "module"), ("dyn2", "module"), (".", "relative import"),
                ("lpbf_cfd_cases", "forbidden in manifest"), ("lpbf_cfd_cases", "module"),
            })
            # The pre-5c checker looked only for <name>.py and missed both directories.
            self.assertNotIn("pkgmod.py", files)
            covered = unmanifested_local_imports(root, (
                "solver.py", "leaf.py", "pkgmod/__init__.py", "pkgmod/core.py",
                "nsdir/helper.py", "dyn.py", "dyn2.py"))
            self.assertEqual({(m, k) for _, m, k in covered},
                             {(".", "relative import"), ("lpbf_cfd_cases", "forbidden in manifest"),
                              ("lpbf_cfd_cases", "module")})

    def test_regular_package_shadows_same_named_module_like_importlib(self):
        with _closure_fixture_root() as root:
            (root / "solver.py").write_text("import twin\n", encoding="utf-8")
            (root / "twin.py").write_text("VALUE = 1\n", encoding="utf-8")
            (root / "twin").mkdir()
            (root / "twin" / "__init__.py").write_text("VALUE = 2\n", encoding="utf-8")
            problems = unmanifested_local_imports(root, ("solver.py", "twin.py"))
            self.assertEqual([(m, k) for _, m, k in problems], [("twin", "package")])

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
