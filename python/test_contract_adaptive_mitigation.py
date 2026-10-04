"""Contract scaffold for adaptive-mitigation (Phase 7 wave 2).

Run from the python directory:  python -B -m unittest test_contract_adaptive_mitigation
The oracle is pending, so the oracle test is skipped and the ceiling stays capped.
"""
import unittest

from contract_test_support import (PYTHON_DIR, AuthorityReadsMixin, ContractScaffold, function_node, get_conversions,
                                   get_reads, worker_dispatch)

HANDLER = function_node(PYTHON_DIR / "lpbf_worker_rpc.py", "_rpc_adaptive_feedforward")
GCODE = "G0 X0 Y0\nG1 X10 Y0 S280 F60000\nG1 X10 Y0.1 S280 F60000\nG1 X0 Y0.1 S280 F60000\n"


class AdaptiveMitigationContractScaffold(ContractScaffold, AuthorityReadsMixin, unittest.TestCase):
    MODULE_ID = "adaptive-mitigation"

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
        empty = worker_dispatch("adaptive-feedforward", {})
        self.assertEqual(tuple(empty), self.operation.output.fields)

    def test_rotation_is_67_degrees_times_the_layer_index(self):
        rotated = worker_dispatch("adaptive-feedforward",
                                  {"content": GCODE, "apply67DegRotation": True, "layerIndex": 2})
        self.assertEqual(rotated["rotation_angle_deg"], 134.0)
        self.assertEqual(self.result["rotation_angle_deg"], 0.0)

    def test_hotspot_count_is_the_peak_speed_definition(self):
        # mitigated_hotspots_count counts vectors with v_peak < 0.99 v_nom (recorded note), not LED spikes.
        from lpbf_adaptive_feedforward import AdaptiveFeedforwardMitigator
        from lpbf_toolpath_kinematics import LPBFToolpathParser
        vectors = LPBFToolpathParser.parse_gcode(GCODE, default_power_W=280.0, default_speed_mms=1000.0)
        mitigator = AdaptiveFeedforwardMitigator()
        expected = sum(1 for v in vectors if mitigator.compensate_vector(v).is_mitigated)
        self.assertEqual(self.result["mitigated_hotspots_count"], expected)
        self.assertTrue(any("0.99 x the nominal speed" in note for note in self.contract.legacy_notes))

    def test_recorded_gap_string_flag_is_rejected_by_the_contract_but_coerced_by_the_authority(self):
        # Known gap pinned as current behaviour: fixing it means updating the contract note and this test.
        self.assertEqual(len(self.operation.input_problems({"apply67DegRotation": "false"})), 1)
        coerced = worker_dispatch("adaptive-feedforward", {"content": GCODE, "apply67DegRotation": "false"})
        self.assertEqual(coerced["rotation_angle_deg"], 67.0, "bool('false') is True at the authority")

    def test_non_numeric_input_is_rejected_by_the_contract_and_fails_in_the_authority(self):
        self.assertEqual(len(self.operation.input_problems({"defaultPower_W": "high"})), 1)
        with self.assertRaises(ValueError):
            worker_dispatch("adaptive-feedforward", {"content": GCODE, "defaultPower_W": "high"})


if __name__ == "__main__":
    unittest.main()
