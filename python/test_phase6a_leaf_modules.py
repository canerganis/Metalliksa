"""Manifest import-closure guard for the Phase 6a leaf modules.

physical_constants, alloy_registry and input_validation are NOT part of
lpbf_simulation.IMPLEMENTATION_SOURCE_FILES. No manifest file may import them
(directly or via importlib) until the planned implementation-fingerprint bump,
otherwise test_manifest_covers_static_local_python_import_closure fails or the
fingerprint silently stops covering numerical code.
"""

import ast
import subprocess
import sys
import unittest
from pathlib import Path

from lpbf_simulation import IMPLEMENTATION_SOURCE_FILES

HERE = Path(__file__).parent
LEAF_MODULES = ("physical_constants", "alloy_registry", "input_validation",
                "alloy_data_kinetics_uq_fatigue")  # phase6a-t2b domain data
# Local modules each leaf may import (everything else must be standard library).
ALLOWED_LOCAL_IMPORTS = {
    "physical_constants": set(),
    "alloy_registry": {"four_alloy_materials",
                       "alloy_data_kinetics_uq_fatigue",  # phase6a-t2b block
                       "physical_constants"},  # design step (b): computed corrosion EW
    "alloy_data_kinetics_uq_fatigue": set(),  # phase6a-t2b
    "input_validation": {"alloy_registry", "physical_constants"},
}
# Phase 6a tranche 2a domain-data leaf (its own guard: test_alloy_data_calphad_battery_icme).
ALLOWED_LOCAL_IMPORTS["alloy_registry"].add("alloy_data_calphad_battery_icme")


def _imported_modules(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module.split(".")[0]


class LeafModuleGuardTest(unittest.TestCase):
    def test_leaf_modules_are_not_in_manifest(self):
        stems = {Path(item).stem for item in IMPLEMENTATION_SOURCE_FILES}
        for name in LEAF_MODULES:
            self.assertNotIn(name, stems)

    def test_manifest_has_37_entries(self):
        self.assertEqual(len(IMPLEMENTATION_SOURCE_FILES), 37)

    def test_no_manifest_file_imports_a_leaf_module(self):
        for relative in IMPLEMENTATION_SOURCE_FILES:
            if not relative.endswith(".py"):
                continue
            path = HERE / relative
            imported = set(_imported_modules(path))
            text = path.read_text(encoding="utf-8")
            for name in LEAF_MODULES:
                self.assertNotIn(name, imported, f"{relative} imports {name}")
                # Also catch importlib.import_module("name") / __import__("name").
                self.assertNotIn(f'"{name}"', text, f"{relative} references {name}")
                self.assertNotIn(f"'{name}'", text, f"{relative} references {name}")

    def test_leaf_modules_only_import_allowed_local_modules(self):
        for name in LEAF_MODULES:
            local = {m for m in _imported_modules(HERE / f"{name}.py") if (HERE / f"{m}.py").is_file()}
            self.assertLessEqual(local, ALLOWED_LOCAL_IMPORTS[name], name)

    def test_leaf_modules_import_without_numpy_or_scipy(self):
        code = ("import sys, input_validation, alloy_registry, physical_constants; "
                "print(sorted(m for m in ('numpy', 'scipy', 'pycalphad') if m in sys.modules))")
        out = subprocess.run([sys.executable, "-B", "-c", code], cwd=str(HERE),
                             capture_output=True, text=True, check=True)
        self.assertEqual(out.stdout.strip(), "[]")


if __name__ == "__main__":
    unittest.main()
