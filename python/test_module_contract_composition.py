import json
import unittest
from pathlib import Path

from module_contract import ContractError, ModuleContract
from module_contracts_composition import COMPOSITION_OPERATIONS, build_composition_contract


class CompositionContractTests(unittest.TestCase):
    def setUp(self):
        rows = json.loads(Path(__file__).with_name("module_registry_seed.json").read_text(encoding="utf-8"))
        self.seed = next(row for row in rows if row["id"] == "alloy-builder")

    def test_builder_constructs_contract_and_preserves_seed_identity(self):
        contract = build_composition_contract(self.seed)

        self.assertIsInstance(contract, ModuleContract)
        self.assertEqual(
            (contract.id, contract.workspace, contract.label, contract.description,
             contract.next, contract.maturity),
            ("alloy-builder", "materials", "Composition Editor",
             "Edit and normalise the active specimen's composition (wt%) with simple composition-based estimates; no inverse design.",
             "phase-diagram", "Research"),
        )
        self.assertEqual(contract.seed_derived, ("label", "description", "next", "maturity"))
        self.assertEqual(contract.view.component, "src/components/AlloyBuilder.tsx")
        self.assertEqual(contract.view.export, "AlloyBuilder")
        self.assertEqual(contract.migration_state, "contracted")
        self.assertEqual(contract.evidence.ceiling, "screening-only")
        self.assertEqual(contract.evidence.emits, ())
        self.assertEqual(contract.tests.oracle.status, "pending")
        self.assertEqual(contract.lifecycle.background_work, "none")

    def test_visible_store_actions_have_separate_browser_local_scopes(self):
        operations = {operation.id: operation for operation in COMPOSITION_OPERATIONS}

        self.assertEqual(
            tuple(operations),
            ("update-specimen-name", "update-category", "update-standard-designation",
             "update-manufacturing-route", "add-element", "set-element-content", "remove-element",
             "normalize-composition", "load-preset", "reset-to-default", "save-current-specimen"),
        )
        self.assertTrue(all(operation.route is None and operation.method is None for operation in operations.values()))
        self.assertTrue(all(operation.authority.kind == "browser-local" for operation in operations.values()))
        self.assertTrue(all(operation.authority.timeout_ms is None for operation in operations.values()))
        self.assertEqual(operations["update-category"].undeclared_input, ("category",))
        self.assertEqual(operations["save-current-specimen"].output.fields, ("savedSpecimens",))

    def test_percentage_type_and_store_input_bounds_are_declared(self):
        operation = next(op for op in COMPOSITION_OPERATIONS if op.id == "set-element-content")

        self.assertEqual(operation.input[0].min, 0)
        self.assertEqual(operation.input[0].max, 100)
        self.assertTrue(operation.input[0].required)
        self.assertEqual(operation.undeclared_input, ("element",))
        self.assertEqual(operation.input_problems({"percentage": "18.5", "element": "Ni"}),
                         ["percentage: must be a finite number"])
        self.assertTrue(operation.input_problems({"percentage": 101, "element": "Ni"}))
        self.assertTrue(any("composition" in problem for problem in operation.input_problems(
            {"percentage": 18.5, "element": "Ni", "composition": {"Ni": 18.5}}
        )))

    def test_bad_seed_identity_fails_contract_construction(self):
        bad_seed = {**self.seed, "id": "Alloy Builder"}

        with self.assertRaises(ContractError):
            build_composition_contract(bad_seed)


if __name__ == "__main__":
    unittest.main()
