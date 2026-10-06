from __future__ import annotations

import json
import unittest
from pathlib import Path

import module_contract as mc
import module_registry as mr
from module_contracts_evidence import (
    build_experimental_data_contract,
    build_traceability_contract,
)


ROOT = Path(__file__).resolve().parent.parent


class EvidenceWorkspaceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows = json.loads((ROOT / "python" / "module_registry_seed.json").read_text(encoding="utf-8"))
        cls.seeds = {row["id"]: row for row in rows if row["id"] in {"experimental-data", "traceability"}}
        cls.contracts = {
            "experimental-data": build_experimental_data_contract(cls.seeds["experimental-data"]),
            "traceability": build_traceability_contract(cls.seeds["traceability"]),
        }

    def test_both_modes_preserve_seed_identity_and_are_pending_screening_only(self):
        for module_id, contract in self.contracts.items():
            with self.subTest(module_id=module_id):
                seed = self.seeds[module_id]
                self.assertIsInstance(contract, mc.ModuleContract)
                self.assertEqual(contract.id, module_id)
                self.assertEqual((contract.workspace, contract.label, contract.description,
                                  contract.next, contract.maturity),
                                 (seed["workspace"], seed["label"], seed["description"],
                                  seed["next"], seed["scope"]))
                self.assertEqual(contract.seed_derived, ("label", "description", "next", "maturity"))
                self.assertEqual((contract.view.component, contract.view.export),
                                 ("src/components/EvidenceWorkspace.tsx", "EvidenceWorkspace"))
                self.assertEqual(contract.migration_state, "contracted")
                self.assertEqual(contract.evidence.ceiling, "screening-only")
                self.assertEqual(contract.evidence.emits, ())
                self.assertEqual(contract.tests.oracle.status, "pending")
                self.assertEqual(contract.lifecycle.background_work, "none")
                self.assertEqual(contract.lifecycle.resources, ())
                self.assertIn("measured", contract.evidence.forbidden_claims)
                self.assertIn("not independent validation", contract.evidence.note)

    def test_mode_specific_findings_and_navigation_actions_are_distinct(self):
        experimental = self.contracts["experimental-data"]
        traceability = self.contracts["traceability"]
        exp_ops = {operation.id: operation for operation in experimental.operations}
        trace_ops = {operation.id: operation for operation in traceability.operations}

        self.assertEqual(tuple(exp_ops), ("set-material-scope", "navigate-to-measurement-entry",
                                           "navigate-to-research-registry", "export-evidence-package"))
        self.assertEqual(tuple(trace_ops), ("set-material-scope", "navigate-to-research-registry",
                                             "export-evidence-package"))
        scope = exp_ops["set-material-scope"]
        self.assertEqual(len(scope.input), 1)
        self.assertEqual((scope.input[0].key, scope.input[0].value_type, scope.input[0].default,
                          scope.input[0].required), ("allMaterials", "boolean", False, True))
        self.assertEqual(scope.output.fields, ("allMaterials", "findings"))
        self.assertEqual(exp_ops["navigate-to-measurement-entry"].input, ())
        self.assertEqual(exp_ops["navigate-to-measurement-entry"].output.fields,
                         ("activeTab", "eventName", "tabId"))
        self.assertEqual(exp_ops["navigate-to-research-registry"].output.fields,
                         ("activeTab", "eventName", "tabId"))
        self.assertEqual(trace_ops["navigate-to-research-registry"].input, ())

        all_notes = " ".join(experimental.legacy_notes + traceability.legacy_notes)
        self.assertIn("evidenceType === 'measured'", all_notes)
        self.assertIn("allMaterials ||", all_notes)
        self.assertIn("does not establish independent validation", all_notes)

    def test_export_is_stateful_and_contains_the_full_snapshot_not_visible_findings(self):
        expected_package_keys = (
            "schemaVersion", "exportedAt", "scope", "activeSpecimen", "research",
            "engineering", "buildScreening", "missingEvidence",
        )
        for contract in self.contracts.values():
            export = next(op for op in contract.operations if op.id == "export-evidence-package")
            with self.subTest(module_id=contract.id):
                self.assertEqual(export.input, ())
                self.assertEqual(export.output.status_key, None)
                self.assertEqual(export.output.fields,
                                 expected_package_keys + ("blob", "url", "anchor", "download", "notice"))
                notes = " ".join(contract.legacy_notes)
                self.assertIn("research.exportSnapshot()", notes)
                self.assertIn("briefs, sources, findings, integrations, and feedback", notes)
                self.assertIn("engineering.job and submittedInput are null", notes)
                self.assertIn("build.job is null", notes)
                self.assertIn("void", notes)
                self.assertIn("setTimeout", notes)

    def test_source_references_resolve_and_generated_docs_are_placeholders(self):
        generated_docs = frozenset(mr.module_doc_path(module_id) for module_id in self.contracts)
        for module_id, contract in self.contracts.items():
            with self.subTest(module_id=module_id):
                self.assertEqual(contract.tests.docs, mr.module_doc_path(module_id))
                self.assertEqual(mr.contract_ref_problems(contract, root=ROOT, generated=generated_docs), [])
                self.assertIn("src/types/research.ts", contract.source_refs)
                self.assertIn("src/components/ResearchIntegrationPanel.tsx::ResearchIntegrationPanel",
                              contract.source_refs)
                self.assertEqual(mc.contract_from_dict(contract.to_dict()), contract)

    def test_builder_rejects_a_seed_from_the_other_workspace_mode(self):
        wrong_seed = {**self.seeds["experimental-data"], "id": "traceability"}
        with self.assertRaises(mc.ContractError):
            build_experimental_data_contract(wrong_seed)


if __name__ == "__main__":
    unittest.main()
