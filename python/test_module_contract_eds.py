"""Tests for the source-bounded EDS module contract."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import module_contract as mc
from module_contracts_eds import build_eds_contract


ROOT = Path(__file__).resolve().parent.parent


class EDSModuleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seeds = json.loads((ROOT / "python" / "module_registry_seed.json").read_text(encoding="utf-8"))
        cls.seed = next(item for item in seeds if item["id"] == "eds-lab")
        cls.contract = build_eds_contract(cls.seed)

    def test_builds_contracted_browser_local_operations_without_fake_deadlines(self):
        contract = self.contract
        self.assertEqual(contract.id, "eds-lab")
        self.assertEqual(contract.migration_state, "contracted")
        self.assertEqual(len(contract.operations), 7)
        for operation in contract.operations:
            with self.subTest(operation=operation.id):
                self.assertEqual(operation.authority.kind, "browser-local")
                self.assertIsNone(operation.route)
                self.assertIsNone(operation.method)
                self.assertIsNone(operation.authority.timeout_ms)
                self.assertIsNone(operation.output.status_key)

    def test_inputs_capture_scalar_setting_and_nested_undeclared_payloads(self):
        operations = {operation.id: operation for operation in self.contract.operations}
        fwhm = operations["identify-peak-candidates"].input[0]
        self.assertEqual((fwhm.value_type, fwhm.unit, fwhm.min, fwhm.max, fwhm.default),
                         ("number", "eV", 20.0, 1000.0, 130.0))
        self.assertFalse(fwhm.required)
        self.assertIn("spectrumPoints", operations["identify-peak-candidates"].undeclared_input)
        vendor = operations["import-vendor-quantification"]
        self.assertEqual(set(vendor.undeclared_input), {"fileName", "bytes", "instrument", "software", "analysisType"})
        self.assertTrue(any("ArrayBuffer" in note and "energyKeV" in note for note in self.contract.legacy_notes))

    def test_outputs_separate_transport_from_evidence_and_keep_peak_id_nonquantitative(self):
        contract = self.contract
        self.assertEqual(contract.evidence.emits, ())
        self.assertEqual(contract.evidence.ceiling, "screening-only")
        self.assertEqual(contract.tests.oracle.status, "pending")
        outputs = {op.id: set(op.output.fields) for op in contract.operations}
        self.assertIn("peaks", outputs["identify-peak-candidates"])
        self.assertNotIn("composition", outputs["identify-peak-candidates"])
        self.assertIn("composition", outputs["import-vendor-quantification"])
        self.assertIn("transferProvenance", outputs["send-vendor-composition"])
        self.assertIn("does not produce quantitative composition", contract.evidence.note)

    def test_seed_identity_and_round_trip_are_preserved(self):
        contract = self.contract
        self.assertEqual(contract.label, self.seed["label"])
        self.assertEqual(contract.description, self.seed["description"])
        self.assertEqual(contract.next, self.seed["next"])
        self.assertEqual(contract.seed_derived, ("label", "description", "next", "maturity"))
        restored = mc.contract_from_dict(contract.to_dict())
        self.assertEqual(restored, contract)

    def test_every_source_reference_resolves_to_an_existing_line_span(self):
        for ref in self.contract.source_refs:
            path, span = ref.split(":", 1)
            target = ROOT / path
            self.assertTrue(target.is_file(), ref)
            line_count = len(target.read_text(encoding="utf-8").splitlines())
            bounds = [int(value) for value in span.split("-")]
            self.assertLessEqual(bounds[0], bounds[-1], ref)
            self.assertLessEqual(bounds[-1], line_count, ref)


if __name__ == "__main__":
    unittest.main()
