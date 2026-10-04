"""WARM_MODULE_NAMES parity with the module registry (Phase 7 slice 1).

python/persistent_ipc_service.py keeps WARM_MODULE_NAMES warm by hand; the
registry records ``authority.warm`` per python-ipc operation. Design 7 makes the
registry the source; until then this test pins the difference so neither list
drifts silently. persistent_ipc_service.py is read with ``ast`` (not imported).

Run from the python directory:  python -B -m unittest test_module_warm_parity
"""
import ast
import unittest
from pathlib import Path

import module_registry as mr

PYTHON_DIR = Path(__file__).resolve().parent

# Warm scripts with no registry operation behind them at 464806f. Each one is a
# reported mismatch, not an endorsement: a registered view calls none of these
# through a python-ipc route. Ratchet: entries may only be removed.
WARM_WITHOUT_REGISTRY_OPERATION = {
    "cnls_fitting_solver": "only the unreachable EIS cluster / utils/cnlsOptimizer call /api/python/cnls-*",
    "xrd_peak_deconvolution": "/api/python/xrd-deconvolve has no caller in src/",
    "inverse_alloy_optimizer": "/api/python/inverse-alloy-optimize has no caller in src/",
    "marangoni_pore_instability_solver": "only the unreachable MarangoniPoreInstabilityLab calls it",
    "part_scale_inherent_strain_solver": "/api/python/part-scale-inherent-strain has no caller in src/",
    "lpbf_build_job_solver": "build jobs go through the LPBF worker (/api/lpbf/jobs), not a python-ipc route",
    "engine_dispatcher": "generic dispatcher, not a module script",
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


class WarmParityTests(unittest.TestCase):
    def test_warm_list_equals_registry_warm_plus_reported_mismatches(self):
        warm = warm_module_names()
        self.assertEqual(len(warm), len(set(warm)), "duplicate WARM_MODULE_NAMES entry")
        registry_warm = registry_warm_scripts(mr.build_registry())
        self.assertEqual(registry_warm - set(warm), set(),
                         "registry marks scripts warm that persistent_ipc_service.py does not warm")
        self.assertEqual(set(warm) - registry_warm, set(WARM_WITHOUT_REGISTRY_OPERATION),
                         "WARM_MODULE_NAMES and the registry diverged beyond the recorded mismatch list")

    def test_registry_cold_python_scripts_are_not_warm(self):
        warm = set(warm_module_names())
        for contract in mr.build_registry():
            for op in contract.operations:
                if op.authority.kind == "python-ipc" and not op.authority.warm:
                    with self.subTest(module=contract.id, operation=op.id):
                        self.assertNotIn(Path(op.authority.script).stem, warm)

    def test_parity_logic_detects_drift(self):
        contracts = mr.build_registry()
        registry_warm = registry_warm_scripts(contracts)
        some = sorted(registry_warm)[0]
        self.assertIn(some, registry_warm)
        # Dropping a warm script from WARM_MODULE_NAMES must surface as a mismatch.
        self.assertNotEqual(registry_warm - (set(warm_module_names()) - {some}), set())


if __name__ == "__main__":
    unittest.main()
