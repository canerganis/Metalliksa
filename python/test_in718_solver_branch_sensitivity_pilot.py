import unittest

from run_in718_solver_branch_sensitivity_pilot import (
    ABSORPTIVITY_SCALES,
    HEAT_SOURCES,
    PROCESS_CASES,
    build_design,
    summarize_result,
)


class In718SolverBranchSensitivityPilotTests(unittest.TestCase):
    def test_design_is_complete_unique_and_bounded(self):
        design = build_design(0.38)
        self.assertEqual(len(design), len(PROCESS_CASES) * len(ABSORPTIVITY_SCALES) * len(HEAT_SOURCES))
        self.assertEqual(len({row["run_id"] for row in design}), len(design))
        self.assertEqual({row["heat_source"] for row in design}, set(HEAT_SOURCES))
        self.assertEqual({row["absorptivity_scale"] for row in design}, set(ABSORPTIVITY_SCALES))
        self.assertTrue(all(0.0 < row["absorptivity_IR_override"] < 1.0 for row in design))

    def test_evaluation_id_separates_repeats_from_design_condition(self):
        baseline = next(row for row in build_design(0.38) if row["run_id"].endswith("__eta1.0__rosenthal") and "285w" in row["run_id"])
        evaluations = [
            {**baseline, "evaluation_id": f"{baseline['run_id']}__rep{index:02d}"}
            for index in (1, 2)
        ]
        self.assertEqual(evaluations[0]["run_id"], evaluations[1]["run_id"])
        self.assertNotEqual(evaluations[0]["evaluation_id"], evaluations[1]["evaluation_id"])

    def test_design_rejects_invalid_base_absorptivity(self):
        for value in (0.0, 1.0, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_design(value)

    def test_result_summary_preserves_solver_outputs_and_marks_missing_thermal_field(self):
        result = {
            "success": True,
            "engine": "solver-v1",
            "modelId": "model-a",
            "heatSourceModel": "rosenthal",
            "processParameters": {
                "normalizedEnthalpy": 2.0,
                "effectiveAbsorptivity": 0.6,
                "conductionAbsorptivity": 0.5,
                "fabbroAbsorptivity": 0.38,
            },
            "meltPoolGeometry": {
                "width_um": 90.0,
                "depth_um": 35.0,
                "length_um": 500.0,
                "regime": "conduction",
                "depthToWidthRatio_D_over_W": 0.39,
            },
            "hydrodynamicsAndRecoil": {"peakTemperature_C": 1700.0},
            "thermal": None,
        }
        summary = summarize_result(result, warnings="", runtime_s=1.0)
        self.assertTrue(summary["solver_success"])
        self.assertFalse(summary["metrics"]["thermal_output_present"])
        self.assertEqual(summary["metrics"]["melt_pool_width_um"], 90.0)
        self.assertTrue(all(summary["finite_numeric_metrics"].values()))

    def test_powder_bed_fallback_warning_is_explicit(self):
        summary = summarize_result({"success": False}, warnings="GPU Powder Bed Ray Tracing failed", runtime_s=0)
        self.assertTrue(summary["raytrace_fallback_warning_seen"])


if __name__ == "__main__":
    unittest.main()
