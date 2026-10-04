"""Contract scaffold for ttt-cct-kinetics (Phase 7 wave 2).

Run from the python directory:  python -B -m unittest test_contract_ttt_cct_kinetics
The oracle is pending, so the oracle test is skipped and the ceiling stays capped.
"""
import unittest

import alloy_data_kinetics_uq_fatigue as kinetics_data
from contract_test_support import (PYTHON_DIR, AuthorityReadsMixin, ContractScaffold, get_conversions, get_reads,
                                   main_block, run_script)

SCRIPT = "kinetics_ttt_cct_solver.py"


class KineticsContractScaffold(ContractScaffold, AuthorityReadsMixin, unittest.TestCase):
    MODULE_ID = "ttt-cct-kinetics"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (cls.operation,) = cls.contract.operations
        # One default input through the real entry point (the one the route and the warm IPC run).
        cls.exit_code, cls.result = run_script(SCRIPT, {})

    def test_every_key_the_entry_point_reads_is_declared(self):
        entry = main_block(PYTHON_DIR / SCRIPT)
        self.assert_reads_match(self.operation, get_reads(entry, "data"))
        # The entry point passes every value on unconverted; the notes say so ("Passed unconverted").
        self.assert_conversion_notes(self.operation, get_conversions(entry, "data"))

    def test_alloy_choices_are_the_kinetics_table(self):
        alloy = next(f for f in self.operation.input if f.key == "alloy")
        self.assertEqual(set(alloy.enum), set(kinetics_data.KINETICS_LEGACY_NAMES.values()))

    def test_output_fields_match_the_default_run(self):
        self.assertEqual(self.exit_code, 0, self.result)
        self.assertEqual(tuple(self.result), self.operation.output.fields)
        self.assertEqual(self.result["inputParameters"]["agingTime_h"],
                         next(f.default for f in self.operation.input if f.key == "agingTime_h"))

    def test_unknown_alloy_is_rejected_by_the_contract_and_by_input_validation(self):
        payload = {"alloy": "Unobtanium 9000"}
        self.assertEqual(len(self.operation.input_problems(payload)), 1)
        exit_code, envelope = run_script(SCRIPT, payload)
        self.assertEqual(exit_code, 2)
        self.assertEqual(envelope["errorKind"], "validation")
        self.assertEqual((envelope["error"]["code"], envelope["error"]["field"]), ("UNKNOWN_ALLOY", "alloy"))

    def test_recorded_gap_negative_grain_size_fails_only_for_the_steels(self):
        # Known gap pinned as current behaviour: fixing it means updating the contract note and this test.
        # No bound is enforced (none is declared). Only the steel JMAK branch uses the grain size.
        self.assertEqual(self.operation.input_problems({"grainSize_um": -5.0}), [])
        exit_code, result = run_script(SCRIPT, {"grainSize_um": -5.0})  # default alloy AISI 4140 (steel)
        self.assertEqual((exit_code, result.get("errorKind")), (1, "internal"))
        exit_code, result = run_script(SCRIPT, {"alloy": "Inconel 718", "grainSize_um": -5.0})
        self.assertEqual(exit_code, 0, result)
        self.assertEqual(result["inputParameters"]["priorGrainSize_um"], -5.0)
        note = next(f.note for f in self.operation.input if f.key == "grainSize_um")
        self.assertIn("negative value fails", note)
        self.assertIn("for Inconel 718, Ti-6Al-4V and Al 7075 it is ignored", note)

    def test_recorded_gap_equilibrium_text_is_steel_text_for_every_alloy(self):
        # Known gap pinned as current behaviour: fixing it means updating the contract note and this test.
        exit_code, result = run_script(SCRIPT, {"alloy": "Ti-6Al-4V"})
        self.assertEqual(exit_code, 0, result)
        steel = self.result["calphadVsKineticsGap"]["equilibriumPrediction"]
        self.assertEqual(result["calphadVsKineticsGap"]["equilibriumPrediction"], steel)
        self.assertIn("Ferrite + Cementite", steel["stablePhasesAtRT"])
        self.assertTrue(any("fixed steel text" in note for note in self.contract.legacy_notes))


if __name__ == "__main__":
    unittest.main()
