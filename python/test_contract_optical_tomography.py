"""Contract scaffold for optical-tomography (Phase 7 wave 2).

Run from the python directory:  python -B -m unittest test_contract_optical_tomography
The oracle is pending, so the oracle test is skipped and the ceiling stays capped.
"""
import unittest

from contract_test_support import (PYTHON_DIR, AuthorityReadsMixin, ContractScaffold, function_node, get_conversions,
                                   get_reads, worker_dispatch)

HANDLER = function_node(PYTHON_DIR / "lpbf_worker_rpc.py", "_rpc_optical_tomography")
VIEW_KEYS = ("laser_power_W", "scan_speed_mm_s", "sensor_resolution")  # sent by OpticalTomographyLab.tsx


class OpticalTomographyContractScaffold(ContractScaffold, AuthorityReadsMixin, unittest.TestCase):
    MODULE_ID = "optical-tomography"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (cls.operation,) = cls.contract.operations
        cls.result = worker_dispatch(cls.operation.authority.worker_method, {})

    def test_every_key_the_worker_reads_is_declared(self):
        self.assert_reads_match(self.operation, get_reads(HANDLER, "payload"))
        self.assert_conversion_notes(self.operation, get_conversions(HANDLER, "payload"))

    def test_output_fields_match_the_default_run(self):
        self.assertEqual(tuple(self.result), self.operation.output.fields)
        self.assertEqual(self.result["resolution"], [64, 64])
        self.assertEqual(len(self.result["pixels_1d"]), 64 * 64)

    def test_non_numeric_input_is_rejected_by_the_contract_and_fails_in_the_authority(self):
        self.assertEqual(len(self.operation.input_problems({"scanSpeed_mms": "fast"})), 1)
        with self.assertRaises(ValueError):
            worker_dispatch("optical-tomography", {"scanSpeed_mms": "fast"})

    def test_recorded_gap_view_keys_are_not_read_by_the_authority(self):
        view = (PYTHON_DIR.parent / "src" / "components" / "OpticalTomographyLab.tsx").read_text(encoding="utf-8")
        reads = get_reads(HANDLER, "payload")
        for key in VIEW_KEYS:
            with self.subTest(key=key):
                self.assertIn(f"{key}:", view)
                self.assertNotIn(key, reads)
                self.assertTrue(self.operation.input_problems({key: 1}), "the contract rejects the view key")
        # The view's laser power and speed change nothing: the authority defaults apply.
        small = {"res_x": 4, "res_y": 4}
        ignored = worker_dispatch("optical-tomography", {**small, "laser_power_W": 50.0, "scan_speed_mm_s": 3000.0})
        self.assertEqual(ignored, worker_dispatch("optical-tomography", small))
        self.assertTrue(any("does not read" in note for note in self.contract.legacy_notes))


if __name__ == "__main__":
    unittest.main()
