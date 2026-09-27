"""Opt-in Warp evidence projection and full-state capture coverage."""

import math
import os
import unittest
from unittest.mock import patch

import numpy as np

import lpbf_gpu_thermal_warp as candidate


CASE = {
    "mode": "standard", "backend": "reference", "material": "Inconel 718",
    "power_W": 60, "speed_mm_s": 1200, "mesh_um": 10, "maxDt_s": 2e-7,
    "layer_um": 80, "trackLength_um": 200, "cooling_s": 2e-5, "dwell_s": 0,
    "powderGridPolicy": "layer-conforming",
}


class WarpThermalCapture(unittest.TestCase):
    def test_capture_option_is_explicit_and_requires_final_state(self):
        with self.assertRaisesRegex(ValueError, "capture_pilot_state must be a boolean"):
            candidate.run_warp(CASE, capture_pilot_state=1)
        with self.assertRaisesRegex(ValueError, "requires capture_final=True"):
            candidate.run_warp(CASE, capture_final=False, capture_pilot_state=True)

    def test_projection_is_exactly_the_shared_codec_state_and_keeps_volumetric_h(self):
        from lpbf_gpu_pilot_artifacts import _state_arrays

        coordinates = np.asarray([[0., 0., 0.], [1., 0., 0.]], dtype=np.float64)
        temperature = np.asarray([300., 301.], dtype=np.float64)
        # These values are volumetric excess enthalpy, exactly as stored by Warp.
        enthalpy = np.asarray([2.0e6, 3.0e6], dtype=np.float64)
        density = np.asarray([8000., 4400.], dtype=np.float64)
        accepted_dt = np.asarray([.25, .25], dtype=np.float64)
        state = candidate._pilot_capture_projection(
            coordinates, temperature, enthalpy, density, accepted_dt,
            time_s=.5, initial_temperature_K=300., cell_volume_m3=2e-9)

        self.assertEqual(set(state), {
            "coordinates_m", "temperature_K", "enthalpy_J_m3", "density_kg_m3",
            "accepted_dt_s", "time_s", "initial_temperature_K", "cell_volume_m3",
        })
        self.assertIs(state["enthalpy_J_m3"], enthalpy)
        arrays, cells, steps = _state_arrays(state)
        self.assertEqual((cells, steps), (2, 2))
        np.testing.assert_array_equal(arrays["accepted_dt_s"], accepted_dt)
        np.testing.assert_array_equal(arrays["enthalpy_J_m3"], enthalpy)
        stored_j = state["cell_volume_m3"] * float(np.sum(arrays["enthalpy_J_m3"]))
        self.assertEqual(stored_j, 1.0e-2)

    @unittest.skipUnless(os.environ.get("METALLIX_RUN_WARP_CAPTURE_TEST") == "1",
                         "Set METALLIX_RUN_WARP_CAPTURE_TEST=1 for one explicit Warp/CUDA capture run")
    def test_opt_in_warp_capture_returns_actual_common_codec_state(self):
        from lpbf_gpu_pilot_artifacts import _state_arrays

        available = candidate.wp is not None and candidate.wp.is_cuda_available()
        if not available:
            self.skipTest("Warp/CUDA unavailable; actual-state capture unverified")

        from lpbf_gpu_warp_pilot import _warp_device_evidence, validate_warp_pilot_request
        with patch.dict("sys.modules", {"torch": None}):
            resolved, _ = validate_warp_pilot_request(
                {**CASE, "backend": "cuda:0", "jobType": "gpu-thermal-pilot", "executionEngine": "warp"})
            self.assertEqual(resolved["executionEngine"], "warp")
            result, field, state = candidate.run_warp(
                CASE, "cuda:0", capture_final=True, capture_pilot_state=True)
            evidence = _warp_device_evidence("cuda:0")
        self.assertEqual(evidence["warp"], candidate.wp.__version__)
        self.assertEqual(evidence["warpCudaToolkitVersion"],
                         ".".join(map(str, candidate.wp.get_cuda_toolkit_version())))
        self.assertEqual(evidence["cudaDriverVersion"],
                         ".".join(map(str, candidate.wp.get_cuda_driver_version())))
        self.assertEqual(evidence["name"], candidate.wp.get_device("cuda:0").name)
        self.assertNotIn("cudaRuntime", evidence)
        self.assertNotIn("torch", evidence)
        arrays, cells, steps = _state_arrays(state)
        self.assertEqual(set(state), {
            "coordinates_m", "temperature_K", "enthalpy_J_m3", "density_kg_m3",
            "accepted_dt_s", "time_s", "initial_temperature_K", "cell_volume_m3",
        })
        self.assertEqual((cells, steps), (result["discretization"]["cells"],
                                          result["discretization"]["steps"]))
        for name in ("coordinates_m", "temperature_K", "enthalpy_J_m3",
                     "density_kg_m3", "accepted_dt_s"):
            self.assertEqual(state[name].dtype, np.dtype(np.float64), name)
            self.assertTrue(state[name].flags.c_contiguous, name)
        self.assertTrue(math.isclose(state["time_s"],
                                     result["discretization"]["meanDt_s"] * steps,
                                     rel_tol=1e-15, abs_tol=0.0))
        self.assertEqual(state["time_s"], field["time_s"])
        np.testing.assert_array_equal(state["temperature_K"], field["temperature_K"])
        np.testing.assert_array_equal(state["coordinates_m"], field["coordinates_m"])
        normalized, material, domain = candidate._validate_candidate(CASE)
        t0 = float(candidate.thermal_si_inputs(normalized, material)["preheat_K"])
        self.assertEqual(t0, normalized["preheat_C"] + 273.15)
        self.assertEqual(state["initial_temperature_K"], t0)
        dx = float(domain["dx"])
        self.assertEqual(state["cell_volume_m3"], dx ** 3)
        nx, ny, nz = (int(domain[key]) for key in ("nx", "ny", "nz"))
        z = (np.arange(nz, dtype=np.float64) + .5) * dx - float(domain["substrate_depth"])
        expected_rho0 = float(candidate.property_at(material, t0, 1))
        expected_rho = expected_rho0 * np.where(
            np.broadcast_to(z[None, None, :], (nx, ny, nz)).ravel() > 0,
            normalized["packingFraction"], 1.0)
        np.testing.assert_array_equal(state["density_kg_m3"], expected_rho)
        self.assertTrue(np.isfinite(state["density_kg_m3"]).all())
        self.assertTrue((state["density_kg_m3"] > 0).all())
        self.assertEqual(state["cell_volume_m3"] * float(np.sum(arrays["enthalpy_J_m3"])),
                         result["energyBalance"]["stored_J"])
        self.assertEqual(arrays["accepted_dt_s"].size, steps)


if __name__ == "__main__":
    unittest.main()
