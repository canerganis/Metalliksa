"""Final-state capture tests; synthetic comparisons are not experimental validation."""

import shutil
import unittest
from pathlib import Path
from uuid import uuid4

import numpy as np

from lpbf_gpu_pilot_artifacts import read_pilot_artifacts, write_pilot_artifacts
from lpbf_gpu_thermal import compare_with_cpu
from lpbf_simulation import run as cpu_run


CASE = {
    "mode": "standard", "backend": "reference", "material": "Inconel 718",
    "power_W": 60, "speed_mm_s": 1200, "mesh_um": 40, "maxDt_s": 2e-7,
    "preheat_C": 80, "layer_um": 80, "trackLength_um": 200,
    "cooling_s": 2e-5, "dwell_s": 0,
}
STATE_KEYS = {
    "coordinates_m", "temperature_K", "enthalpy_J_m3", "density_kg_m3",
    "accepted_dt_s", "time_s", "initial_temperature_K", "cell_volume_m3",
}


def _capture_artifact_directory():
    root = Path(__file__).resolve().parent
    folder = root / f".tmp-final-state-capture-{uuid4().hex}"
    folder.mkdir()
    return root, folder


class FinalStateCapture(unittest.TestCase):
    def test_cpu_observer_receives_one_actual_final_state_after_success(self):
        captured = []
        captured_stored_energy = []

        def observer(state):
            captured.append(state)
            captured_stored_energy.append(
                float(np.sum(state["enthalpy_J_m3"])) * state["cell_volume_m3"])
            state["temperature_K"].fill(0.)
            state["enthalpy_J_m3"].fill(0.)

        result = cpu_run(CASE, final_state_observer=observer)

        self.assertEqual(len(captured), 1)
        state = captured[0]
        self.assertEqual(set(state), STATE_KEYS)
        cells = result["discretization"]["cells"]
        steps = result["discretization"]["steps"]
        self.assertEqual(state["coordinates_m"].shape, (cells, 3))
        for quantity in ("temperature_K", "enthalpy_J_m3", "density_kg_m3"):
            self.assertEqual(state[quantity].shape, (cells,))
        self.assertEqual(state["accepted_dt_s"].shape, (steps,))
        self.assertEqual(state["time_s"], result["thermalHistory"][-1]["time_s"])
        self.assertEqual(state["initial_temperature_K"], CASE["preheat_C"] + 273.15)
        self.assertEqual(state["cell_volume_m3"], result["discretization"]["mesh_m"] ** 3)
        self.assertAlmostEqual(
            captured_stored_energy[0],
            result["energyBalance"]["stored_J"], delta=1e-12,
        )
        self.assertTrue(np.all(state["temperature_K"] == 0.))
        self.assertTrue(np.all(state["enthalpy_J_m3"] == 0.))
        self.assertNotIn("finalState", result)

    def test_cpu_observer_rejects_unsupported_study_before_solving(self):
        captured = []
        with self.assertRaisesRegex(ValueError, "standard reference powder-layer"):
            cpu_run({**CASE, "study": "mesh"}, final_state_observer=captured.append)
        self.assertEqual(captured, [])

    def test_cuda_capture_roundtrips_through_final_field_artifact_writer(self):
        try:
            import torch
            available = torch.cuda.is_available()
        except ImportError:
            available = False
        if not available:
            self.skipTest("CUDA runtime unavailable; final-state artifact capture unverified")

        root, folder = _capture_artifact_directory()
        try:
            observed = []
            descriptor = None

            def evidence_sink(cpu_state, gpu_state):
                nonlocal descriptor
                observed.append((cpu_state, gpu_state))
                expected = tuple({
                    key: value.copy() if isinstance(value, np.ndarray) else value
                    for key, value in state.items()
                } for state in (cpu_state, gpu_state))
                descriptor = write_pilot_artifacts(folder, cpu_state, gpu_state)
                cpu_state["temperature_K"].fill(0.)
                return expected

            expected_states = []

            def mutating_sink(cpu_state, gpu_state):
                expected_states.extend(evidence_sink(cpu_state, gpu_state))

            result = compare_with_cpu(CASE, "cuda:0", evidence_sink=mutating_sink)
            self.assertEqual(result["comparisons"]["finalSampling"]["status"], "pass")
            self.assertEqual(result["comparisons"]["finalTemperatureField"]["status"], "pass")
            self.assertEqual(len(observed), 1)
            self.assertEqual(set(expected_states[0]), STATE_KEYS)
            self.assertEqual(set(expected_states[1]), STATE_KEYS)
            self.assertFalse(set(STATE_KEYS) & set(result["gpu"]))
            restored = read_pilot_artifacts(folder, descriptor)
            for backend, expected in zip(("cpu", "gpu"), expected_states):
                for quantity in ("coordinates_m", "temperature_K", "enthalpy_J_m3",
                                 "density_kg_m3", "accepted_dt_s"):
                    np.testing.assert_array_equal(restored[backend][quantity], expected[quantity])
                for quantity in ("time_s", "initial_temperature_K", "cell_volume_m3"):
                    self.assertEqual(restored[backend][quantity], expected[quantity])
        finally:
            if folder.resolve().parent == root and folder.name.startswith(".tmp-final-state-capture-"):
                shutil.rmtree(folder)


if __name__ == "__main__":
    unittest.main()
