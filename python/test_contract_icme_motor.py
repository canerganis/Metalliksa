"""Contract scaffold for icme-motor (Phase 7 wave 2).

Run from the python directory:  python -B -m unittest test_contract_icme_motor
The oracle is pending, so the oracle test is skipped and the ceiling stays capped.
"""
import unittest

from contract_test_support import (PYTHON_DIR, AuthorityReadsMixin, ContractScaffold, function_node, get_conversions,
                                   get_reads, run_script)

SCRIPT = "icme_multiscale_pipeline_solver.py"


class IcmeContractScaffold(ContractScaffold, AuthorityReadsMixin, unittest.TestCase):
    MODULE_ID = "icme-motor"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (cls.operation,) = cls.contract.operations
        cls.exit_code, cls.result = run_script(SCRIPT, {})

    def test_every_key_the_authority_reads_is_declared(self):
        solver = function_node(PYTHON_DIR / SCRIPT, "solve_multiscale_pipeline")
        self.assert_reads_match(self.operation, get_reads(solver, "params"))
        self.assert_conversion_notes(self.operation, get_conversions(solver, "params"))

    def test_output_fields_match_the_default_run(self):
        self.assertEqual(self.exit_code, 0, self.result)
        self.assertEqual(tuple(self.result), self.operation.output.fields)
        self.assertEqual(self.result["inputParameters"]["componentType"], "turbine_blade_root")

    def test_unknown_base_metal_is_rejected_by_the_contract_and_by_input_validation(self):
        payload = {"baseMetal": "Cu"}
        self.assertEqual(len(self.operation.input_problems(payload)), 1)
        exit_code, envelope = run_script(SCRIPT, payload)
        self.assertEqual(exit_code, 2)
        self.assertEqual(envelope["errorKind"], "validation")
        self.assertEqual((envelope["error"]["code"], envelope["error"]["field"]), ("UNKNOWN_ELEMENT", "baseMetal"))

    def test_unknown_composition_element_is_rejected_by_input_validation(self):
        # composition_wt is undeclared (an element map); the authority validates its elements.
        exit_code, envelope = run_script(SCRIPT, {"composition_wt": {"Xx": 1.0}})
        self.assertEqual(exit_code, 2)
        self.assertEqual(envelope["error"]["code"], "UNKNOWN_ELEMENT")

    def test_recorded_gap_unknown_component_falls_back_silently(self):
        self.assertEqual(len(self.operation.input_problems({"componentType": "landing_gear"})), 1)
        exit_code, result = run_script(SCRIPT, {"componentType": "landing_gear"})
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["scale4_macroComponentFEA"]["componentName"],
                         self.result["scale4_macroComponentFEA"]["componentName"])
        note = next(f.note for f in self.operation.input if f.key == "componentType")
        self.assertIn("silently uses turbine_blade_root", note)

    def test_structural_verdict_is_not_an_evidence_status(self):
        self.assertNotIn("structuralVerdict", self.operation.output.fields, "nested, not a top-level status")
        self.assertIn("structuralVerdict is fixed text", self.contract.evidence.note)
        # The verdict is one of the two fixed texts in the solver (vocabulary tripwire).
        self.assertIn(self.result["scale4_macroComponentFEA"]["structuralVerdict"],
                      ("STRUCTURALLY SAFE (Passed Yield & Creep Criteria)",
                       "WARNING: INSUFFICIENT SAFETY MARGIN (Risk of Plastic Yielding)"))

    def test_recorded_gap_creep_wording_without_a_creep_check(self):
        # Known gap pinned as current behaviour: fixing the wording (or adding a creep check) means
        # updating the contract note and this test.
        verdict = "STRUCTURALLY SAFE (Passed Yield & Creep Criteria)"
        self.assertEqual(self.result["scale4_macroComponentFEA"]["structuralVerdict"], verdict)
        exit_code, hot = run_script(SCRIPT, {"serviceTemp_C": 1000.0})
        self.assertEqual(exit_code, 0, hot)
        self.assertEqual(hot["scale4_macroComponentFEA"], self.result["scale4_macroComponentFEA"])
        self.assertTrue(any("no creep check exists" in note for note in self.contract.legacy_notes))

    def test_recorded_gap_calibrated_card_header(self):
        # Known gap pinned as current behaviour: fixing the wording means updating the contract note and this test.
        self.assertIn("MetalliX Multi-Scale ICME Calibrated Card", self.result["caeExportCards"]["abaqus"])
        self.assertTrue(any("'MetalliX Multi-Scale ICME Calibrated Card'" in note
                            for note in self.contract.legacy_notes))


if __name__ == "__main__":
    unittest.main()
