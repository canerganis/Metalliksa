"""WARM_MODULE_NAMES parity with the module registry (Phase 7 slice 1).

python/persistent_ipc_service.py keeps WARM_MODULE_NAMES warm by hand; the
registry records ``authority.warm`` per python-ipc operation. Design 7 makes the
registry the source; until then this test pins the difference so neither list
drifts silently. persistent_ipc_service.py is read with ``ast`` (not imported).

Run from the python directory:  python -B -m unittest test_module_warm_parity
"""
import ast
import json
import unittest
from pathlib import Path

import module_registry as mr

PYTHON_DIR = Path(__file__).resolve().parent

# Warm scripts with no registry operation behind them at 464806f. Each one is a
# reported mismatch, not an endorsement: a registered view calls none of these
# through a python-ipc route. Ratchet: entries may only be removed; the keys must
# stay a subset of the immutable python/module_warm_parity.ceiling.json.
WARM_WITHOUT_REGISTRY_OPERATION = {
    "xrd_peak_deconvolution": "/api/python/xrd-deconvolve has no caller in src/",
    "lpbf_build_job_solver": "build jobs go through the LPBF worker (/api/lpbf/jobs), not a python-ipc route",
}


def warm_module_names() -> list:
    tree = ast.parse((PYTHON_DIR / "persistent_ipc_service.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "WARM_MODULE_NAMES" for t in node.targets):
            return list(ast.literal_eval(node.value))
    raise AssertionError("WARM_MODULE_NAMES not found in persistent_ipc_service.py")


def registry_warm_scripts(contracts) -> set:
    return {
        Path(op.authority.script).stem
        for contract in contracts for op in contract.operations
        if op.authority.kind == "python-ipc" and op.authority.warm
    }


def warm_ceiling() -> set:
    data = json.loads((PYTHON_DIR / "module_warm_parity.ceiling.json").read_text(encoding="utf-8"))
    return set(data["names"])


def warm_parity_problems(warm, registry_warm, allowed, ceiling) -> list:
    """Every mismatch between WARM_MODULE_NAMES and the registry; empty means parity holds."""
    problems = []
    if len(warm) != len(set(warm)):
        problems.append("duplicate WARM_MODULE_NAMES entry")
    warm = set(warm)
    problems += [f"registry warm, not in WARM_MODULE_NAMES: {name}" for name in sorted(registry_warm - warm)]
    problems += [f"warm without registry operation, not allowlisted: {name}" for name in sorted(warm - registry_warm - set(allowed))]
    problems += [f"stale allowlist entry: {name}" for name in sorted(set(allowed) - (warm - registry_warm))]
    problems += [f"allowlist entry beyond the immutable ceiling: {name}" for name in sorted(set(allowed) - ceiling)]
    return problems


class WarmParityTests(unittest.TestCase):
    def test_warm_list_equals_registry_warm_plus_reported_mismatches(self):
        problems = warm_parity_problems(warm_module_names(), registry_warm_scripts(mr.build_registry()),
                                        WARM_WITHOUT_REGISTRY_OPERATION, warm_ceiling())
        self.assertEqual(problems, [])

    def test_registry_cold_python_scripts_are_not_warm(self):
        warm = set(warm_module_names())
        for contract in mr.build_registry():
            for op in contract.operations:
                if op.authority.kind == "python-ipc" and not op.authority.warm:
                    with self.subTest(module=contract.id, operation=op.id):
                        self.assertNotIn(Path(op.authority.script).stem, warm)

    def test_parity_logic_detects_each_kind_of_drift(self):
        # Synthetic inputs, independent of the live lists, so each branch is exercised.
        ceiling = {"old_cold"}
        self.assertEqual(warm_parity_problems(["a", "old_cold"], {"a"}, {"old_cold"}, ceiling), [])
        self.assertEqual(warm_parity_problems(["old_cold"], {"a"}, {"old_cold"}, ceiling),
                         ["registry warm, not in WARM_MODULE_NAMES: a"])
        self.assertEqual(warm_parity_problems(["a", "new"], {"a"}, set(), ceiling),
                         ["warm without registry operation, not allowlisted: new"])
        self.assertEqual(warm_parity_problems(["a"], {"a"}, {"old_cold"}, ceiling),
                         ["stale allowlist entry: old_cold"])
        self.assertEqual(warm_parity_problems(["a", "a"], {"a"}, set(), ceiling), ["duplicate WARM_MODULE_NAMES entry"])

    def test_mutation_new_warm_script_plus_allowlist_entry_still_fails(self):
        warm = warm_module_names() + ["new_unregistered_solver"]
        allowed = {**WARM_WITHOUT_REGISTRY_OPERATION, "new_unregistered_solver": "sneaked in"}
        problems = warm_parity_problems(warm, registry_warm_scripts(mr.build_registry()), allowed, warm_ceiling())
        self.assertEqual(problems, ["allowlist entry beyond the immutable ceiling: new_unregistered_solver"])
        # Removing entries stays allowed by the ceiling (the stale check asks for cleanup only).
        self.assertNotIn("ceiling", " ".join(warm_parity_problems([], set(), {}, warm_ceiling())))


if __name__ == "__main__":
    unittest.main()
