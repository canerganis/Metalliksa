"""Same-input CPU, PyTorch CUDA and Warp CUDA thermal-state parity gate."""

from pathlib import Path
import unittest

import numpy as np

import lpbf_gpu_thermal as torch_candidate
import lpbf_gpu_thermal_warp as warp_candidate


CASE = {
    "mode": "standard", "backend": "reference", "material": "Inconel 718",
    "power_W": 60, "speed_mm_s": 1200, "mesh_um": 40, "maxDt_s": 2e-7,
    "layer_um": 80, "trackLength_um": 200, "cooling_s": 2e-5, "dwell_s": 0,
    "powderGridPolicy": "layer-conforming",
}


def _relative_field_errors(reference, candidate, *, baseline=None):
    reference = np.asarray(reference, dtype=np.float64)
    candidate = np.asarray(candidate, dtype=np.float64)
    if reference.shape != candidate.shape:
        raise AssertionError(f"field shape mismatch: {reference.shape} != {candidate.shape}")
    if not np.isfinite(reference).all() or not np.isfinite(candidate).all():
        raise AssertionError("nonfinite value in captured field")
    difference = candidate - reference
    scale = reference if baseline is None else np.asarray(baseline, dtype=np.float64)
    return (float(np.linalg.norm(difference) / max(float(np.linalg.norm(scale)), 1.0)),
            float(np.max(np.abs(difference)) / max(float(np.max(np.abs(scale))), 1.0)))


class ThreeBackendThermalParity(unittest.TestCase):
    def test_canonical_40um_cpu_torch_warp_same_invocation(self):
        try:
            import torch
        except ImportError:
            self.skipTest("unverified: PyTorch CUDA dependency is unavailable")
        wp = warp_candidate.wp
        if not torch.cuda.is_available():
            self.skipTest("unverified: PyTorch CUDA device is unavailable")
        if wp is None or not wp.is_cuda_available():
            self.skipTest("unverified: Warp CUDA device is unavailable")

        cuda_device = "cuda:0"
        try:
            warp_candidate._require_warp_cuda(cuda_device)
        except (RuntimeError, ValueError) as error:
            self.skipTest(f"unverified: Warp cannot use {cuda_device}: {error}")

        previous_pch = wp.config.use_precompiled_headers
        previous_cache = wp.config.kernel_cache_dir
        wp.config.use_precompiled_headers = False
        wp.config.kernel_cache_dir = str(Path(__file__).resolve().parent / ".tmp-three-backend-parity-warp")
        self.addCleanup(setattr, wp.config, "kernel_cache_dir", previous_cache)
        self.addCleanup(setattr, wp.config, "use_precompiled_headers", previous_pch)

        # These calls share one immutable request. CPU source integration is
        # authoritative on both CUDA paths, so timestep and source inputs bind.
        cpu, _, _, _, cpu_state = torch_candidate._run_cpu_with_final(CASE, include_final_state=True)
        torch_result, torch_state = torch_candidate.run_gpu(
            CASE, cuda_device, capture_final=True, use_cuda_source=False)
        warp_result, _, warp_state = warp_candidate.run_warp(
            CASE, cuda_device, capture_final=True, capture_pilot_state=True)
        results = {"CPU": cpu, "PyTorch CUDA": torch_result, "Warp CUDA": warp_result}
        states = {"CPU": cpu_state, "PyTorch CUDA": torch_state, "Warp CUDA": warp_state}

        material = cpu["material"]
        model_id = cpu["coreContract"]["modelId"]
        for name, result in results.items():
            backend_model_id = (result["coreContract"]["modelId"] if name == "CPU"
                                else result["solver"]["modelId"])
            with self.subTest(backend=name, identity="input-model-material"):
                self.assertEqual(result["settings"], cpu["settings"])
                self.assertEqual(result["material"]["materialId"], material["materialId"])
                self.assertEqual(result["material"]["materialRevisionSha256"],
                                 material["materialRevisionSha256"])
                self.assertEqual(backend_model_id, model_id)
                self.assertEqual(result["discretization"]["mesh_m"], cpu["discretization"]["mesh_m"])
                self.assertEqual(result["discretization"]["cells"], cpu["discretization"]["cells"])
                self.assertEqual(result["discretization"]["steps"], cpu["discretization"]["steps"])
                self.assertLessEqual(result["energyBalance"]["relativeError"], .01)

        reference_dt = cpu_state["accepted_dt_s"]
        reference_coordinates = cpu_state["coordinates_m"]
        reference_density = cpu_state["density_kg_m3"]
        reference_temperature = cpu_state["temperature_K"]
        reference_enthalpy = cpu_state["enthalpy_J_m3"]
        initial_temperature = cpu_state["initial_temperature_K"]
        temperature_rise = reference_temperature - initial_temperature
        for name, state in states.items():
            with self.subTest(backend=name, identity="full-grid-and-time-step-sequence"):
                np.testing.assert_array_equal(state["accepted_dt_s"], reference_dt)
                np.testing.assert_array_equal(state["coordinates_m"], reference_coordinates)
                np.testing.assert_array_equal(state["density_kg_m3"], reference_density)
                self.assertEqual(state["time_s"], cpu_state["time_s"])
                self.assertEqual(state["initial_temperature_K"], initial_temperature)
                self.assertEqual(state["cell_volume_m3"], cpu_state["cell_volume_m3"])

            if name == "CPU":
                continue
            with self.subTest(backend=name, field="temperature-rise"):
                l2, linf = _relative_field_errors(
                    reference_temperature, state["temperature_K"], baseline=temperature_rise)
                self.assertLessEqual(l2, .01)
                self.assertLessEqual(linf, .01)
            with self.subTest(backend=name, field="volumetric-enthalpy"):
                l2, linf = _relative_field_errors(reference_enthalpy, state["enthalpy_J_m3"])
                self.assertLessEqual(l2, .01)
                self.assertLessEqual(linf, .01)

            result = results[name]
            for quantity in ("input_J", "losses_J", "stored_J"):
                expected = cpu["energyBalance"][quantity]
                actual = result["energyBalance"][quantity]
                with self.subTest(backend=name, energy=quantity):
                    self.assertLessEqual(abs(actual - expected) / max(abs(expected), 1e-30), .01)
            with self.subTest(backend=name, metric="peak-temperature"):
                expected = cpu["metrics"]["peakTemperature_K"]
                actual = result["metrics"]["peakTemperature_K"]
                self.assertLessEqual(abs(actual - expected) / max(abs(expected), 1e-30), .01)
            for quantity in ("width_um", "depth_um", "length_um"):
                with self.subTest(backend=name, metric=quantity):
                    self.assertLessEqual(abs(result["metrics"][quantity] - cpu["metrics"][quantity]), 40.0)
            with self.subTest(backend=name, metric="melt-volume"):
                expected = cpu["metrics"]["volume_um3"]
                actual = result["metrics"]["volume_um3"]
                self.assertGreater(expected, 0.0, "canonical parity case must contain a melt volume")
                self.assertLessEqual(abs(actual - expected) / expected, .01)


if __name__ == "__main__":
    unittest.main()
