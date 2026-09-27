import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TEST_DIRECTORY = ROOT / "python" / ".fixed-scan-end-test-output"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lpbf_simulation
from lpbf_fixed_scan_end_observation import write_selected_state_artifact
import run_lpbf_fixed_scan_end_convergence as fixed_protocol
from run_lpbf_fixed_scan_end_convergence import _case_specs


class FixedScanEndProtocolTests(unittest.TestCase):
    def setUp(self):
        TEST_DIRECTORY.mkdir(exist_ok=True)

    def tearDown(self):
        for path in TEST_DIRECTORY.iterdir():
            path.unlink()
        TEST_DIRECTORY.rmdir()

    def test_case_matrix_has_five_unique_rows_and_reuses_shared_finest_case(self):
        specs = _case_specs({
            "meshLevels_um": [20, 10, 5], "fixedMeshMaxDt_s": 2.5e-8,
            "timeLevels_s": [5e-8, 2.5e-8, 1.25e-8], "fixedTimeStudyMesh_um": 5,
        })
        self.assertEqual(len(specs), 5)
        shared = next(row for row in specs if row["mesh_um"] == 5 and row["maxDt_s"] == 2.5e-8)
        self.assertEqual(shared["axes"], ["mesh", "time"])

    def test_time_axis_reuses_the_finest_mesh_case_in_coarse_to_fine_order(self):
        specs = _case_specs({
            "meshLevels_um": [20, 10, 5], "fixedMeshMaxDt_s": 2.5e-8,
            "timeLevels_s": [5e-8, 2.5e-8, 1.25e-8], "fixedTimeStudyMesh_um": 5,
        })
        rows = []
        for spec in specs:
            rows.append({
                "mesh_um": spec["mesh_um"], "requestedMaxDt_s": spec["maxDt_s"],
                "fixedScanEndObservation": {
                    "status": "thermal-proxy", "operator": "peak-liquidus-cell-edge-linear-contour-v1",
                    "temporalSelection": fixed_protocol.TEMPORAL_SELECTION,
                    "width_um": 30., "depth_um": 15.,
                },
            })
        with patch.object(fixed_protocol, "_axis", side_effect=lambda selected, key: {
                "requests": [row["requested"] for row in selected], "key": key}):
            assessment = fixed_protocol._assessment_rows(rows, specs, "time")
        self.assertEqual(assessment["requests"], [5e-8, 2.5e-8, 1.25e-8])
        self.assertEqual(assessment["key"], "actualMeanDt_s")

    def test_run_accepts_existing_first_scan_end_without_starting_solver(self):
        scenario_path = ROOT / "docs" / "LPBF_P4_CURRENT_MODEL_40W_SCENARIO_2026-09-25.json"
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))["scenario"]
        target = lpbf_simulation.scan_segments(scenario)[0][0]["end_s"]

        class SolverReached(Exception):
            pass

        def stop_at_solver(*args, **kwargs):
            raise SolverReached(kwargs)

        with patch.object(lpbf_simulation, "transient", side_effect=stop_at_solver):
            with self.assertRaises(SolverReached) as reached:
                lpbf_simulation.run(scenario, selected_time_observer=lambda state: None,
                                    selected_time_s=target)
        self.assertEqual(reached.exception.args[0]["selected_time_s"], target)

    def test_run_rejects_a_time_that_is_not_an_existing_scan_end(self):
        scenario_path = ROOT / "docs" / "LPBF_P4_CURRENT_MODEL_40W_SCENARIO_2026-09-25.json"
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))["scenario"]
        target = lpbf_simulation.scan_segments(scenario)[0][0]["end_s"]
        with patch.object(lpbf_simulation, "transient") as solver:
            with self.assertRaisesRegex(ValueError, "existing scan-segment end event"):
                lpbf_simulation.run(scenario, selected_time_observer=lambda state: None,
                                    selected_time_s=target + 1e-12)
        solver.assert_not_called()

    def test_mutating_selected_state_copies_does_not_change_the_solve(self):
        scenario_path = ROOT / "docs" / "LPBF_P4_CURRENT_MODEL_40W_SCENARIO_2026-09-25.json"
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))["scenario"]
        scenario.update(power_W=10, trackLength_um=100, mesh_um=20,
                        maxDt_s=2.5e-7, cooling_s=2e-5)
        target = lpbf_simulation.scan_segments(scenario)[0][0]["end_s"]
        baseline = lpbf_simulation.run(scenario)
        observed = []

        def mutate_copied_state(state):
            observed.append({
                "target_time_s": state["target_time_s"],
                "time_s": state["time_s"],
                "coordinates_m": state["coordinates_m"].copy(),
                "temperature_K": state["temperature_K"].copy(),
                "enthalpy_J_m3": state["enthalpy_J_m3"].copy(),
                "density_kg_m3": state["density_kg_m3"].copy(),
                "accepted_dt_s": state["accepted_dt_s"].copy(),
            })
            for key in ("coordinates_m", "temperature_K", "enthalpy_J_m3", "density_kg_m3", "accepted_dt_s"):
                state[key][...] = -123.
            for key in ("target_time_s", "time_s", "scheduler_time_s", "time_difference_s",
                        "roundoff_tolerance_s", "step", "initial_temperature_K", "cell_volume_m3"):
                state[key] = -123

        captured = lpbf_simulation.run(
            scenario, selected_time_observer=mutate_copied_state, selected_time_s=target)
        self.assertEqual(len(observed), 1)
        self.assertAlmostEqual(observed[0]["target_time_s"], target, places=15)
        self.assertLessEqual(abs(observed[0]["time_s"] - target), 1e-14)
        self.assertTrue(np.isfinite(observed[0]["temperature_K"]).all())
        self.assertTrue(np.isfinite(observed[0]["enthalpy_J_m3"]).all())
        self.assertTrue(np.all(observed[0]["density_kg_m3"] > 0))
        self.assertGreater(observed[0]["accepted_dt_s"].size, 0)
        for key in ("metrics", "energyBalance", "discretization", "numericalDiagnostics",
                    "thermalHistory", "massBalance", "phaseAudit", "fieldOverlapDiagnostics",
                    "peakInterpolatedMeltPool"):
            self.assertEqual(captured.get(key), baseline.get(key), key)

    def test_snapshot_artifact_preserves_actual_arrays_and_hashes(self):
        snapshot = {
            "coordinates_m": np.array([[0., 0., 0.], [1e-6, 0., 0.]]),
            "temperature_K": np.array([300., 1700.]),
            "enthalpy_J_m3": np.array([0., 1.2e9]),
            "density_kg_m3": np.array([4000., 8000.]),
            "accepted_dt_s": np.array([1e-4, 1.5e-4]),
            "target_time_s": 2.5e-4, "time_s": 2.5e-4,
            "scheduler_time_s": 2.5e-4, "time_difference_s": 0.,
            "roundoff_tolerance_s": 1e-14, "step": 2,
            "initial_temperature_K": 353.15, "cell_volume_m3": 1e-18,
        }
        path = TEST_DIRECTORY / "state.npz"
        descriptor = write_selected_state_artifact(snapshot, path)
        self.assertEqual(descriptor["cells"], 2)
        self.assertEqual(set(descriptor["fieldSha256"]), {
            "coordinates_m", "temperature_K", "enthalpy_J_m3", "density_kg_m3", "accepted_dt_s"})
        with np.load(path) as saved:
            np.testing.assert_array_equal(saved["temperature_K"], snapshot["temperature_K"])
            np.testing.assert_array_equal(saved["enthalpy_J_m3"], snapshot["enthalpy_J_m3"])

    def test_snapshot_artifact_rejects_clock_mismatch_and_byte_overrun(self):
        snapshot = {
            "coordinates_m": np.array([[0., 0., 0.]]), "temperature_K": np.array([300.]),
            "enthalpy_J_m3": np.array([0.]), "density_kg_m3": np.array([4000.]),
            "accepted_dt_s": np.array([2.5e-4]), "target_time_s": 2.5e-4,
            "time_s": 2.5e-4, "scheduler_time_s": 2.5e-4, "time_difference_s": 0.,
            "roundoff_tolerance_s": 1e-14, "step": 1,
            "initial_temperature_K": 353.15, "cell_volume_m3": 1e-18,
        }
        path = TEST_DIRECTORY / "state.npz"
        invalid = dict(snapshot, time_s=2.5e-4 + 1e-12)
        with self.assertRaisesRegex(ValueError, "inconsistent|replay"):
            write_selected_state_artifact(invalid, path)
        with self.assertRaisesRegex(ValueError, "byte bound"):
            write_selected_state_artifact(snapshot, path, max_uncompressed_bytes=8)
        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
