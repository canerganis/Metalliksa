"""Contract scaffold for toolpath-studio (Phase 7 wave 2).

Run from the python directory:  python -B -m unittest test_contract_toolpath_studio
The oracle is pending, so the oracle test is skipped and the ceiling stays capped.
"""
import unittest

from contract_test_support import (PYTHON_DIR, AuthorityReadsMixin, ContractScaffold, function_node, get_conversions,
                                   get_reads, worker_dispatch)

HANDLER = function_node(PYTHON_DIR / "lpbf_worker_rpc.py", "_rpc_toolpath_kinematics")
GCODE = "G0 X0 Y0\nG1 X10 Y0 S250 F60000\nG1 X10 Y0.1 S250 F60000\nG1 X0 Y0.1 S250 F60000\n"


class ToolpathContractScaffold(ContractScaffold, AuthorityReadsMixin, unittest.TestCase):
    MODULE_ID = "toolpath-studio"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (cls.operation,) = cls.contract.operations
        cls.result = worker_dispatch(cls.operation.authority.worker_method, {"content": GCODE})

    def test_every_key_the_worker_reads_is_declared(self):
        self.assert_reads_match(self.operation, get_reads(HANDLER, "payload"))
        self.assert_conversion_notes(self.operation, get_conversions(HANDLER, "payload"))

    def test_output_fields_match_a_run(self):
        self.assertEqual(tuple(self.result), self.operation.output.fields)
        self.assertGreater(self.result["total_segments"], 0)
        # The default input (empty content) gives the same keys with zero segments.
        empty = worker_dispatch("toolpath-kinematics", {})
        self.assertEqual((tuple(empty), empty["total_segments"]), (self.operation.output.fields, 0))

    def test_non_numeric_power_is_rejected_by_the_contract_and_fails_in_the_authority(self):
        self.assertEqual(len(self.operation.input_problems({"accelMax_mms2": "fast"})), 1)
        with self.assertRaises(TypeError):
            worker_dispatch("toolpath-kinematics", {"content": GCODE, "accelMax_mms2": "fast"})

    def test_recorded_gap_unknown_format_is_parsed_as_gcode(self):
        self.assertEqual(len(self.operation.input_problems({"format": "step"})), 1)
        as_unknown = worker_dispatch("toolpath-kinematics", {"content": GCODE, "format": "step"})
        self.assertEqual(as_unknown, self.result)

    def test_recorded_laser_off_delay_is_not_used(self):
        delayed = worker_dispatch("toolpath-kinematics", {"content": GCODE, "laserOffDelay_us": 99999.0})
        self.assertEqual(delayed, self.result)
        note = next(f.note for f in self.operation.input if f.key == "laserOffDelay_us")
        self.assertIn("not used", note)


if __name__ == "__main__":
    unittest.main()
