import json
import unittest
from pathlib import Path

from module_contract import ContractError, ModuleContract
from module_contracts_composition import build_composition_contract


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

    def test_operation_models_only_the_numeric_control_and_rejects_fake_map_payload(self):
        operation = build_composition_contract(self.seed).operations[0]

        self.assertEqual(operation.id, "specimen-editor")
        self.assertIsNone(operation.route)
        self.assertEqual(operation.authority.kind, "browser-local")
        self.assertEqual([field.key for field in operation.input], ["percentage"])
        self.assertEqual(operation.undeclared_input, ("element",))
        self.assertEqual(operation.input_problems({"percentage": 18.5, "element": "Ni"}), [])
        self.assertTrue(any("composition" in problem for problem in operation.input_problems(
            {"percentage": 18.5, "element": "Ni", "composition": {"Ni": 18.5}}
        )))

    def test_percentage_type_is_checked_without_invented_physical_bounds(self):
        operation = build_composition_contract(self.seed).operations[0]

        self.assertIsNone(operation.input[0].min)
        self.assertIsNone(operation.input[0].max)
        self.assertEqual(operation.input_problems({"percentage": "18.5", "element": "Ni"}),
                         ["percentage: must be a finite number"])
        self.assertEqual(operation.input_problems({"percentage": 101, "element": "Ni"}), [])

    def test_bad_seed_identity_fails_contract_construction(self):
        bad_seed = {**self.seed, "id": "Alloy Builder"}

        with self.assertRaises(ContractError):
            build_composition_contract(bad_seed)


if __name__ == "__main__":
    unittest.main()
