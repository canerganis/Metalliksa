import json
import unittest
from pathlib import Path

from module_contract import ModuleContract, contract_from_dict
from module_contracts_lpbf_secondary import (
    build_lpbf_optimizer_contract,
    build_solidification_microstructure_contract,
)
from module_registry import ref_problem


class LpbfSecondaryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads(Path(__file__).with_name("module_registry_seed.json").read_text(encoding="utf-8"))

    def seed(self, module_id):
        return next(row for row in self.rows if row["id"] == module_id)

    def test_optimizer_preserves_seed_and_actual_ipc_request_boundary(self):
        seed = self.seed("lpbf-optimizer")
        contract = build_lpbf_optimizer_contract(seed)
        operation = contract.operations[0]

        self.assertIsInstance(contract, ModuleContract)
        self.assertEqual((contract.id, contract.workspace, contract.label, contract.maturity),
                         ("lpbf-optimizer", "lpbf", seed["label"], seed["scope"]))
        self.assertEqual(contract.seed_derived, ("label", "description", "next", "maturity"))
        self.assertEqual(contract.view.component, "src/components/LpbfBayesianOptimizerLab.tsx")
        self.assertEqual((operation.method, operation.route),
                         ("POST", "/api/python/lpbf-bayesian-optimize"))
        self.assertEqual((operation.authority.kind, operation.authority.script,
                          operation.authority.timeout_ms, operation.authority.warm),
                         ("python-ipc", "python/lpbf_bayesian_optimizer.py", 120000, False))
        self.assertEqual(operation.undeclared_input,
                         ("alloyId", "paramBounds", "nIterations", "nWarmup", "seed",
                          "beamDiameter_um", "preheatTemp_C"))
        payload = {"alloyId": "in718", "paramBounds": {"laserPower_W": [100, 500]},
                   "nIterations": 20, "nWarmup": 5, "seed": 42,
                   "beamDiameter_um": 80, "preheatTemp_C": 80}
        self.assertEqual(operation.input_problems(payload), [])
        self.assertEqual(contract.evidence.emits, ())
        self.assertEqual(contract.evidence.ceiling, "screening-only")
        self.assertEqual(contract.tests.oracle.status, "pending")
        self.assertEqual(contract.lifecycle.resources, ("fetch",))
        self.assertFalse(any("silently resolves to in718" in note for note in contract.legacy_notes))
        self.assertTrue(any("missing or unknown alloy is refused" in note for note in contract.legacy_notes))
        self.assertIn("errorKind", operation.output.fields)
        self.assertTrue(any("not a qualified process recommendation" in note
                            for note in contract.legacy_notes))

    def test_optimizer_contract_declares_the_process_window_operation(self):
        contract = build_lpbf_optimizer_contract(self.seed("lpbf-optimizer"))
        self.assertEqual([op.id for op in contract.operations], ["bayesian-optimize", "process-window"])
        operation = contract.operations[1]
        self.assertEqual((operation.method, operation.route),
                         ("POST", "/api/python/lpbf-process-window"))
        self.assertEqual((operation.authority.kind, operation.authority.script,
                          operation.authority.timeout_ms, operation.authority.warm),
                         ("python-ipc", "python/lpbf_process_window.py", 60000, False))
        self.assertEqual(operation.undeclared_input,
                         ("alloyId", "beamDiameter_um", "layer_um", "hatch_um", "preheatTemp_C",
                          "powers", "speeds", "overlayBeamTolerance_pct"))
        payload = {"alloyId": "in718", "beamDiameter_um": 80, "layer_um": 40, "hatch_um": 110,
                   "preheatTemp_C": 80, "powers": [100, 200], "speeds": [500, 600],
                   "overlayBeamTolerance_pct": 10}
        self.assertEqual(operation.input_problems(payload), [])
        self.assertEqual(operation.output.status_key, None)
        for field in ("success", "errorKind", "grid", "cells", "counts", "gridAdvisories", "overlay",
                      "provenance", "cache", "computeMs"):
            self.assertIn(field, operation.output.fields)
        self.assertEqual(contract.evidence.ceiling, "screening-only")
        self.assertEqual(contract.evidence.emits, ())
        notes = " ".join(contract.legacy_notes)
        self.assertIn("process-window", notes)
        self.assertIn("16-entry LRU", notes)
        self.assertIn("no overlay point carries a verdict colour", notes)
        self.assertIn("never coloured as a verdict", notes)
        # the optimizer operation is unchanged
        self.assertEqual(contract.operations[0].route, "/api/python/lpbf-bayesian-optimize")
        # the script exists, the route is served, and the IPC allow-lists name it
        root = Path(__file__).resolve().parent.parent
        self.assertTrue((root / "python" / "lpbf_process_window.py").is_file())
        self.assertIn('"/api/python/lpbf-process-window"', (root / "routes" / "physics.ts").read_text(encoding="utf-8"))
        self.assertIn('"lpbf_process_window"', (root / "server" / "processOrchestrator.ts").read_text(encoding="utf-8"))
        self.assertIn('"lpbf_process_window"', (root / "python" / "persistent_ipc_service.py").read_text(encoding="utf-8"))

    def test_solidification_inventory_matches_worker_and_unavailable_union(self):
        seed = self.seed("solidification-microstructure")
        contract = build_solidification_microstructure_contract(seed)
        operation = contract.operations[0]

        self.assertEqual(contract.id, seed["id"])
        self.assertEqual(contract.view.export, "SolidificationMicrostructureLab")
        self.assertEqual((operation.method, operation.route, operation.authority.kind,
                          operation.authority.worker_method, operation.authority.timeout_ms),
                         ("POST", "/api/python/lpbf-solidification-microstructure", "lpbf-worker",
                          "solidification-microstructure", 20000))
        self.assertEqual(operation.undeclared_input, ("params",))
        self.assertEqual(operation.input_problems({"params": {"materialName": "Inconel 718",
                                                                "power_W": 285}}), [])
        self.assertEqual(operation.output.status_key, None)
        self.assertEqual(dict(operation.output.transport_values)["status"],
                         ("available", "unavailable", "screening-fallback", "degenerate-floor"))
        self.assertTrue({"regime", "normalizedEnthalpy", "regimeNote", "g_over_r_ratio", "doi"}
                        .issubset(operation.output.fields))
        self.assertEqual(contract.evidence.emits, ())
        self.assertEqual(contract.evidence.ceiling, "screening-only")
        self.assertEqual(contract.tests.oracle.status, "pending")
        notes = " ".join(contract.legacy_notes)
        self.assertIn("does not send cfdResult", notes)
        self.assertIn("no substitute alloy or numeric fallback", notes)
        self.assertIn("-273.15 degC", notes)
        self.assertIn("liquidus_C is known", notes)
        self.assertIn("that value in degC", notes)
        self.assertIn("HTTP 200", notes)
        self.assertIn("422", notes)

    def test_wrong_seed_identity_is_rejected_by_each_builder(self):
        optimizer = self.seed("lpbf-optimizer")
        solidification = self.seed("solidification-microstructure")

        with self.assertRaises(ValueError):
            build_lpbf_optimizer_contract(solidification)
        with self.assertRaises(ValueError):
            build_solidification_microstructure_contract(optimizer)

    def test_every_source_reference_resolves(self):
        for builder, module_id in (
            (build_lpbf_optimizer_contract, "lpbf-optimizer"),
            (build_solidification_microstructure_contract, "solidification-microstructure"),
        ):
            contract = builder(self.seed(module_id))
            unresolved = [problem for ref in contract.source_refs
                          if (problem := ref_problem(ref))]
            self.assertEqual(unresolved, [], msg=f"{module_id}: {unresolved}")

    def test_both_contracts_round_trip_through_canonical_json_shape(self):
        for builder, module_id in (
            (build_lpbf_optimizer_contract, "lpbf-optimizer"),
            (build_solidification_microstructure_contract, "solidification-microstructure"),
        ):
            with self.subTest(module_id=module_id):
                contract = builder(self.seed(module_id))
                self.assertEqual(contract_from_dict(contract.to_dict()), contract)

    def test_identity_is_not_reassigned(self):
        contract = build_lpbf_optimizer_contract(self.seed("lpbf-optimizer"))
        broken_seed = {**self.seed("lpbf-optimizer"), "id": "solidification-microstructure"}
        with self.assertRaises(ValueError):
            build_lpbf_optimizer_contract(broken_seed)
        self.assertEqual(contract.id, "lpbf-optimizer")


if __name__ == "__main__":
    unittest.main()
