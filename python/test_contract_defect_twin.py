"""Contract scaffold for defect-twin (Phase 7 wave 2).

Run from the python directory:  python -B -m unittest test_contract_defect_twin
The oracle is pending, so the oracle test is skipped and the ceiling stays capped.
"""
import re
import unittest

from contract_test_support import (PYTHON_DIR, AuthorityReadsMixin, ContractScaffold, function_node, get_conversions,
                                   get_reads, worker_dispatch)

HANDLER = function_node(PYTHON_DIR / "lpbf_worker_rpc.py", "_rpc_stl_voxelize")
STL = ("solid probe\n"
       "facet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 10 0 0\nvertex 0 10 5\nendloop\nendfacet\n"
       "facet normal 0 0 1\nouter loop\nvertex 10 0 0\nvertex 10 10 5\nvertex 0 10 5\nendloop\nendfacet\n"
       "endsolid probe\n")


VIEW = PYTHON_DIR.parent / "src" / "components" / "LpbfDefectTwinLab.tsx"


def view_defaults():
    """(sample STL, defects) as LpbfDefectTwinLab.tsx sends them with its default controls."""
    text = VIEW.read_text(encoding="utf-8")
    stl = re.search(r"SAMPLE_STL_CUBE\s*=\s*`([^`]*)`", text).group(1)
    keyhole = int(re.search(r"\[keyholePoresCount, setKeyholePoresCount\] = useState\((\d+)\)", text).group(1))
    lof = int(re.search(r"\[lofPoresCount, setLofPoresCount\] = useState\((\d+)\)", text).group(1))
    # Mirrors the two loops in handleVoxelize.
    defects = [{"x": 4.0 + i * 2.5, "y": 6.0 + i * 1.8, "z": 5.0 + i * 2.2, "type": "keyhole",
                "diameter_um": 40.0 + i * 8.0} for i in range(keyhole)]
    defects += [{"x": 12.0 - j * 2.0, "y": 14.0 - j * 1.5, "z": 8.0 + j * 3.0, "type": "lof",
                 "diameter_um": 70.0 + j * 15.0} for j in range(lof)]
    return stl, defects


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
        with self.assertRaises(ZeroDivisionError):  # recorded gap (pinned): no bound, 0 divides by zero
            worker_dispatch("stl-voxelize", {"stlContent": STL, "resolution": 0})

    def test_recorded_gap_empty_geometry_reports_a_density(self):
        # Known gap pinned as current behaviour: fixing it means updating the contract note and this test.
        empty = worker_dispatch("stl-voxelize", {})
        self.assertEqual((empty["num_triangles"], empty["part_volume_mm3"], empty["relative_density_pct"]),
                         (0, 0.031, 100.0))
        _, defects = view_defaults()
        self.assertEqual(len(defects), 8)
        with_view_defects = worker_dispatch("stl-voxelize", {"stlContent": "", "defects": defects})
        self.assertAlmostEqual(with_view_defects["relative_density_pct"], 94.95, delta=0.01)
        self.assertTrue(any("about 94.95 against that fictitious volume" in note
                            for note in self.contract.legacy_notes))

    def test_recorded_gap_view_sample_cube_volume_is_a_triangle_count_proxy(self):
        # Known gap pinned as current behaviour: fixing it means updating the contract note and this test.
        stl, defects = view_defaults()
        result = worker_dispatch("stl-voxelize", {"stlContent": stl, "resolution": 32, "defects": defects})
        self.assertEqual(result["bounds"]["dimensions_mm"], [20.0, 20.0, 20.0])
        self.assertEqual((result["num_triangles"], result["part_volume_mm3"], result["relative_density_pct"]),
                         (4, 0.977, 99.842))
        self.assertTrue(any("part_volume_mm3 0.977 against an enclosed 8000 mm3" in note
                            for note in self.contract.legacy_notes))


if __name__ == "__main__":
    unittest.main()
