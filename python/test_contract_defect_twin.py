"""Contract scaffold for defect-twin (Phase 7 wave 2).

Run from the python directory:  python -B -m unittest test_contract_defect_twin
The oracle is pending, so the oracle test is skipped and the ceiling stays capped.
"""
import unittest

from contract_test_support import (PYTHON_DIR, AuthorityReadsMixin, ContractScaffold, function_node, get_conversions,
                                   get_reads, worker_dispatch)

HANDLER = function_node(PYTHON_DIR / "lpbf_worker_rpc.py", "_rpc_stl_voxelize")
STL = ("solid probe\n"
       "facet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 10 0 0\nvertex 0 10 5\nendloop\nendfacet\n"
       "facet normal 0 0 1\nouter loop\nvertex 10 0 0\nvertex 10 10 5\nvertex 0 10 5\nendloop\nendfacet\n"
       "endsolid probe\n")


class DefectTwinContractScaffold(ContractScaffold, AuthorityReadsMixin, unittest.TestCase):
    MODULE_ID = "defect-twin"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (cls.operation,) = cls.contract.operations
        cls.result = worker_dispatch(cls.operation.authority.worker_method,
                                     {"stlContent": STL, "defects": [{"type": "keyhole", "diameter_um": 45.0}]})

    def test_every_key_the_worker_reads_is_declared(self):
        self.assert_reads_match(self.operation, get_reads(HANDLER, "payload"))
        self.assert_conversion_notes(self.operation, get_conversions(HANDLER, "payload"))

    def test_output_fields_match_a_run(self):
        self.assertEqual(tuple(self.result), self.operation.output.fields)
        self.assertEqual((self.result["num_triangles"], self.result["total_defects_count"]), (2, 1))

    def test_part_volume_is_triangle_count_times_voxel_volume(self):
        # Recorded in the evidence note: no inside/outside fill is computed.
        sx, sy, sz = self.result["voxel_size_mm"]
        self.assertAlmostEqual(self.result["part_volume_mm3"], 2 * sx * sy * sz, delta=0.01)
        self.assertIn("max(triangle count, 1) times the voxel volume", self.contract.evidence.note)

    def test_non_integer_resolution_is_rejected_by_the_contract(self):
        self.assertEqual(len(self.operation.input_problems({"resolution": 2.5})), 1)
        self.assertEqual(len(self.operation.input_problems({"resolution": "32"})), 1)
        with self.assertRaises(ZeroDivisionError):  # recorded: no bound, 0 divides by zero
            worker_dispatch("stl-voxelize", {"stlContent": STL, "resolution": 0})

    def test_recorded_gap_empty_geometry_reports_full_density(self):
        empty = worker_dispatch("stl-voxelize", {})
        self.assertEqual((empty["num_triangles"], empty["relative_density_pct"]), (0, 100.0))
        self.assertTrue(any("reports relative_density_pct 100" in note for note in self.contract.legacy_notes))


if __name__ == "__main__":
    unittest.main()
