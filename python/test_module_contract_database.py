import json
import unittest
from pathlib import Path

from module_contract import ContractError, ModuleContract
from module_contracts_database import DATABASE_OPERATIONS, build_database_contract


class DatabaseContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows = json.loads(Path(__file__).with_name("module_registry_seed.json").read_text(encoding="utf-8"))
        cls.seed = next(row for row in rows if row["id"] == "database")

    def test_builder_preserves_seed_identity_and_sets_evidence_ceiling(self):
        contract = build_database_contract(self.seed)

        self.assertIsInstance(contract, ModuleContract)
        self.assertEqual(
            (contract.id, contract.workspace, contract.label, contract.description, contract.next, contract.maturity),
            ("database", "materials", "Materials Database",
             "Handbook values and reviewed research references; source applicability requires review.",
             "alloy-builder", "Research"),
        )
        self.assertEqual(contract.seed_derived, ("label", "description", "next", "maturity"))
        self.assertEqual((contract.view.component, contract.view.export),
                         ("src/components/MaterialsDatabaseView.tsx", "MaterialsDatabaseView"))
        self.assertEqual(contract.evidence.ceiling, "screening-only")
        self.assertEqual(contract.evidence.emits, ())
        self.assertEqual(contract.tests.oracle.status, "pending")
        self.assertEqual(contract.lifecycle.background_work, "none")
        self.assertEqual(contract.lifecycle.resources, ())

    def test_local_view_interactions_are_separate_and_not_routes(self):
        operations = {operation.id: operation for operation in DATABASE_OPERATIONS}
        self.assertEqual(
            tuple(operations),
            ("search-catalog", "filter-by-category", "filter-by-min-yield-strength",
             "filter-by-min-modulus", "filter-by-max-density", "reset-property-range-filters",
             "switch-view-mode", "sort-catalog", "select-material-record", "toggle-comparison-record",
             "copy-selected-record", "export-catalog-json", "open-transfer-picker", "dispatch-material-to-module"),
        )
        self.assertTrue(all(op.route is None and op.method is None for op in operations.values()))
        self.assertTrue(all(op.authority.kind == "browser-local" and op.authority.timeout_ms is None
                            for op in operations.values()))
        self.assertTrue(all(op.output.status_key is None for op in operations.values()))
        self.assertEqual(operations["select-material-record"].undeclared_input, ("material",))
        self.assertEqual(operations["sort-catalog"].output.fields, ("sortedMaterials",))
        self.assertEqual(operations["toggle-comparison-record"].output.fields, ("compareList",))
        self.assertEqual(operations["dispatch-material-to-module"].input[0].enum,
                         ("alloy-builder", "icme-motor", "3d-distortion-lab", "phase-diagram"))

    def test_filters_use_real_controls_without_claiming_hard_material_bounds(self):
        operations = {operation.id: operation for operation in DATABASE_OPERATIONS}
        category = operations["filter-by-category"]
        fields = {field.key: field for field in category.input}

        self.assertEqual(fields["selectedCategory"].enum, (
            "All", "Carbon Steel", "Alloy Steel", "Tool Steel", "Stainless Steel", "Aluminum Alloy",
            "Copper Alloy", "Titanium Alloy", "Nickel Superalloy", "Magnesium Alloy",
            "Refractory & Specialty", "Ceramic & Carbide",
        ))
        self.assertEqual(operations["search-catalog"].undeclared_input, ("searchQuery",))
        self.assertEqual(fields["selectedCategory"].value_problem("Nickel Superalloy"), None)
        self.assertIsNotNone(fields["selectedCategory"].value_problem("Invented category"))
        self.assertEqual(category.input_problems({"selectedCategory": "All"}), [])
        search = operations["search-catalog"]
        self.assertEqual(search.input_problems({"searchQuery": "718"}), [])
        self.assertTrue(any("composition" in problem for problem in search.input_problems(
            {"searchQuery": "718", "composition": {"Ni": 100}}
        )))
        for operation_id, key, default, step in (
            ("filter-by-min-yield-strength", "minYield", 0, 50),
            ("filter-by-min-modulus", "minModulus", 40, 10),
            ("filter-by-max-density", "maxDensity", 17.0, 0.2),
        ):
            field = operations[operation_id].input[0]
            self.assertEqual(field.key, key)
            self.assertEqual((field.default, field.step), (default, step))
            self.assertIsNone(field.min)
            self.assertIsNone(field.max)

    def test_sort_keys_and_target_options_match_visible_controls(self):
        operations = {operation.id: operation for operation in DATABASE_OPERATIONS}
        sort_fields = {field.key: field for field in operations["sort-catalog"].input}
        self.assertEqual(sort_fields["sortBy"].enum,
                         ("yield", "tensile", "specific_strength", "modulus", "density", "name"))
        self.assertEqual(sort_fields["sortOrder"].enum, ("desc", "asc"))
        self.assertEqual(sort_fields["sortBy"].value_problem("specific_strength"), None)
        self.assertIsNotNone(sort_fields["sortBy"].value_problem("hardness"))
        self.assertEqual({field.key: field.enum for field in operations["switch-view-mode"].input}["activeTab"],
                         ("split", "heatmap", "catalog"))
        self.assertIsNotNone(operations["dispatch-material-to-module"].input[0].value_problem("database"))

    def test_provenance_limits_and_derived_transfer_are_explicit(self):
        contract = build_database_contract(self.seed)
        notes = " ".join(contract.legacy_notes)
        self.assertIn("no per-property source citation", notes)
        self.assertIn("range-midpoint", notes)
        self.assertIn("source property values/confidence are not promoted", notes)
        self.assertIn("rather than inventing a record-ID endpoint or object schema", notes)
        self.assertIn("350 ms", notes)
        self.assertIn("2000 ms", notes)
        self.assertIn("not a database measurement", notes)
        self.assertIn("not provider/server execution", notes)
        self.assertIn("indexes 0 and 5", notes)
        self.assertIn("No fetch, worker, solver", notes)
        self.assertIn("physical validation", contract.evidence.note)

    def test_invalid_seed_identity_is_rejected(self):
        with self.assertRaises(ContractError):
            build_database_contract({**self.seed, "id": "Materials Database"})


if __name__ == "__main__":
    unittest.main()
