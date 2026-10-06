"""Contract scaffold for murakami-fatigue (Phase 7 wave 2).

Run from the python directory:  python -B -m unittest test_contract_murakami_fatigue
The oracle is pending, so the oracle test is skipped and the ceiling stays capped.
"""
import unittest

import alloy_data_kinetics_uq_fatigue as fatigue_data
import input_validation
from contract_test_support import (PYTHON_DIR, AuthorityReadsMixin, ContractScaffold, function_node, get_conversions,
                                   get_reads, worker_dispatch)

HANDLER = function_node(PYTHON_DIR / "lpbf_worker_rpc.py", "_rpc_fatigue_fracture")


class FatigueContractScaffold(ContractScaffold, AuthorityReadsMixin, unittest.TestCase):
    MODULE_ID = "murakami-fatigue"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (cls.operation,) = cls.contract.operations
        cls.result = worker_dispatch(cls.operation.authority.worker_method, {})

    def test_every_key_the_worker_reads_is_declared(self):
        self.assert_reads_match(self.operation, get_reads(HANDLER, "payload"))
        self.assert_conversion_notes(self.operation, get_conversions(HANDLER, "payload"))

    def test_alloy_choices_are_the_fatigue_table(self):
        alloy = next(f for f in self.operation.input if f.key == "alloyName")
        self.assertEqual(set(alloy.enum), set(fatigue_data.FATIGUE_LEGACY_NAMES.values()))

    def test_output_fields_match_the_default_run(self):
        self.assertEqual(tuple(self.result), self.operation.output.fields)
        self.assertIn(self.result["paris_crack_growth"]["status"], ("non_propagating", "fractured", "runout"))

    def test_unknown_alloy_is_rejected_by_the_contract_and_by_input_validation(self):
        payload = {"alloyName": "Unobtanium 9000"}
        self.assertEqual(len(self.operation.input_problems(payload)), 1)
        with self.assertRaises(input_validation.ValidationError) as caught:
            worker_dispatch("fatigue-fracture", payload)
        self.assertEqual((caught.exception.code, caught.exception.field), ("UNKNOWN_ALLOY", "alloyName"))

    def test_view_locations_select_the_three_geometry_factors(self):
        from lpbf_fatigue_fracture import MurakamiFatigueEngine
        engine = MurakamiFatigueEngine()
        locations = next(f.enum for f in self.operation.input if f.key == "location")
        factors = {loc: engine.murakami_geometric_constant(loc) for loc in locations}
        self.assertEqual(factors, {"surface": 1.43, "sub-surface": 1.41, "internal": 1.56})

    def test_input_rejections_are_validation_errors(self):
        # fx-murakami: R >= 1, a non-positive amplitude or sqrt(area) are ValidationErrors (HTTP 422),
        # not ZeroDivisionError / math domain error. No exclusive bound is declared in the contract.
        notes = {f.key: f.note for f in self.operation.input}
        for payload, code, phrase in (({"stressRatio_R": 1.0}, input_validation.OUT_OF_RANGE, "R < 1"),
                                      ({"stressAmplitude_MPa": 0.0}, input_validation.NON_POSITIVE, "> 0"),
                                      ({"sqrtArea_um": -5.0}, input_validation.NON_POSITIVE, "> 0")):
            (key,) = payload
            with self.subTest(key=key):
                self.assertEqual(self.operation.input_problems(payload), [], "no bound is declared")
                with self.assertRaises(input_validation.ValidationError) as caught:
                    worker_dispatch("fatigue-fracture", payload)
                self.assertEqual((caught.exception.code, caught.exception.field), (code, key))
                self.assertIn(phrase, notes[key])


if __name__ == "__main__":
    unittest.main()
