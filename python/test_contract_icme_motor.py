"""Contract scaffold for icme-motor (Phase 7 wave 2).

Run from the python directory:  python -B -m unittest test_contract_icme_motor
The oracle is pending, so the oracle test is skipped and the ceiling stays capped.
"""
import unittest

from contract_test_support import (PYTHON_DIR, AuthorityReadsMixin, ContractScaffold, function_node, get_reads,
                                   run_script)

SCRIPT = "icme_multiscale_pipeline_solver.py"


class IcmeContractScaffold(ContractScaffold, AuthorityReadsMixin, unittest.TestCase):
    MODULE_ID = "icme-motor"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (cls.operation,) = cls.contract.operations
        cls.exit_code, cls.result = run_script(SCRIPT, {})

    def test_every_key_the_authority_reads_is_declared(self):
        reads = get_reads(function_node(PYTHON_DIR / SCRIPT, "solve_multiscale_pipeline"), "params")
        self.assert_reads_match(self.operation, reads)

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
        verdict = self.result["scale4_macroComponentFEA"]["structuralVerdict"]
        self.assertNotIn("structuralVerdict", self.operation.output.fields, "nested, not a top-level status")
        self.assertIn("structuralVerdict is fixed text", self.contract.evidence.note)
        self.assertIsInstance(verdict, str)


if __name__ == "__main__":
    unittest.main()
