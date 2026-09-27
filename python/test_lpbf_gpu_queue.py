"""Existing LPBF queue dispatches an explicit, isolated CUDA parity pilot."""

import copy
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch

from lpbf_core_contract import build_core_contract
from lpbf_gpu_thermal import (GPU_SOLVER_ID, PARITY_TARGETS, PILOT_JOB_TYPE, enforce_gpu_pilot_result,
                              validate_pilot_request)
from lpbf_worker import Queue


CASE = {"jobType": PILOT_JOB_TYPE, "mode": "standard", "backend": "cuda:0",
        "material": "Inconel 718", "power_W": 60, "speed_mm_s": 1200,
        "mesh_um": 40, "maxDt_s": 2e-7, "layer_um": 80,
        "trackLength_um": 200, "cooling_s": 2e-5, "dwell_s": 0}


def synthetic_pilot_result(settings, material):
    """Queue-integrity fixture only; no CUDA execution or parity evidence."""
    reference = {key: value for key, value in settings.items() if key != "jobType"}
    reference["backend"] = "reference"
    core = build_core_contract(reference, material, "enthalpy-fv-6", "standard")
    return {
        "jobType": PILOT_JOB_TYPE, "settings": settings, "material": material,
        "effectiveMode": "gpu-pilot", "validationStatus": "unvalidated",
        "productionReady": False, "artifacts": [],
        "solver": {"id": GPU_SOLVER_ID, "modelId": core["modelId"],
                   "actualBackend": "cuda:0", "thermalEvolutionDevice": "cuda:0",
                   "sourceIntegrationDevice": "cpu", "sourceTimestepLimiterDevice": "cpu",
                   "dtype": "float64"},
        "energyBalance": {"input_J": 1., "losses_J": 0., "stored_J": 1., "relativeError": 0.},
        "gpuPilot": {
            "experimentalValidation": False, "status": "inconclusive", "targets": dict(PARITY_TARGETS),
            "cpu": {"coreContract": core, "material": material},
            "comparisons": {key: {"status": "inconclusive"} for key in (
                "finalSampling", "finalTemperatureField", "peakTemperature_K", "input_J",
                "losses_J", "stored_J", "width_um", "depth_um", "length_um", "volume_um3")}},
        "provenance": {
            "inputHash": hashlib.sha256(json.dumps(settings, sort_keys=True, allow_nan=False).encode()).hexdigest(),
            "deviceEvidence": {"selected": "cuda:0", "thermalEvolution": "cuda:0",
                               "sourceIntegration": "cpu", "sourceTimestepLimiter": "cpu",
                               "synchronizedAfterSolve": True}},
    }


class GpuQueue(unittest.TestCase):
    def test_restore_and_cache_bind_result_to_submitted_settings(self):
        # Recomputed self-hashes must not let a different request impersonate
        # the submitted job. JSON comparison must also distinguish True from 1.
        for changed in (None, {"power_W": 61.}, {"tracks": True}):
            for operation in ("restore", "cache"):
                with self.subTest(changed=changed, operation=operation), \
                        patch("lpbf_gpu_thermal.require_cuda"), \
                        patch("lpbf_worker.capabilities", return_value={"openfoamVersion": None}), \
                        tempfile.TemporaryDirectory() as tmp:
                    queue = Queue(tmp, start=False)
                    submitted = queue.submit(CASE)
                    settings, material = validate_pilot_request(CASE)
                    result = synthetic_pilot_result(settings, material)
                    if changed:
                        result["settings"].update(changed)
                        result["provenance"]["inputHash"] = hashlib.sha256(
                            json.dumps(result["settings"], sort_keys=True, allow_nan=False).encode()).hexdigest()
                    # Establish the concrete gap: the internal result guard
                    # accepts this fixture, including its recomputed hash.
                    enforce_gpu_pilot_result(result)
                    (queue.root / submitted["id"] / "result.json").write_text(json.dumps(result))
                    queue.update(submitted["id"], status="completed")
                    queue.close()
                    restored = Queue(tmp, start=False)
                    try:
                        if operation == "restore":
                            state = restored.get(submitted["id"])
                            self.assertEqual(state["status"], "failed" if changed else "completed")
                            if changed:
                                self.assertNotIn("result", state)
                                self.assertIn("submitted settings", state["error"])
                        else:
                            state = restored.submit(CASE)
                            self.assertEqual(state["cacheHit"], changed is None)
                            self.assertEqual(state["id"] == submitted["id"], changed is None)
                            if changed:
                                self.assertEqual(restored.get(submitted["id"])["status"], "failed")
                    finally:
                        restored.close()

    def test_requires_explicit_device_and_bounded_reference_case(self):
        for backend in ("reference", "auto", "cuda", "cpu", "cuda:-1"):
            with self.assertRaisesRegex(ValueError, "no CPU fallback"):
                validate_pilot_request({**CASE, "backend": backend})
        with patch("lpbf_gpu_thermal.require_cuda"):
            for invalid in ({"tracks": 2}, {"study": "mesh"},
                            {"surfaceMode": "bare-plate", "sourcePenetration_um": 40},
                            {"mode": "screening"}):
                with self.assertRaises(ValueError):
                    validate_pilot_request({**CASE, **invalid})

    def test_missing_device_is_explicit_submit_error(self):
        with patch("torch.cuda.is_available", return_value=False), tempfile.TemporaryDirectory() as tmp:
            queue = Queue(tmp, start=False)
            try:
                with self.assertRaisesRegex(RuntimeError, "no CPU fallback"):
                    queue.submit(CASE)
            finally:
                queue.close()

    def test_real_cuda_queue_result_and_integrity(self):
        try:
            import torch
            available = torch.cuda.is_available()
        except ImportError:
            available = False
        if not available:
            self.skipTest("CUDA unavailable; queued GPU execution unverified")
        with tempfile.TemporaryDirectory() as tmp:
            queue = Queue(tmp, start=False)
            try:
                submitted = queue.submit(CASE)
                self.assertEqual(submitted["requestSummary"]["backend"], "cuda:0")
                queue.update(submitted["id"], status="running")
                queue.execute(submitted["id"])
                state = queue.get(submitted["id"])
                self.assertEqual(state["status"], "completed", state.get("error"))
                result = state["result"]
                enforce_gpu_pilot_result(result)
                self.assertEqual(result["solver"]["thermalEvolutionDevice"], "cuda:0")
                self.assertEqual(result["solver"]["sourceIntegrationDevice"], "cpu")
                self.assertEqual(result["gpuPilot"]["status"], "pass")
                self.assertEqual(result["gpuPilot"]["comparisons"]["finalTemperatureField"]["status"], "pass")
                self.assertFalse(result["gpuPilot"]["experimentalValidation"])
                self.assertTrue(result["provenance"]["deviceEvidence"]["synchronizedAfterSolve"])
                with self.assertRaisesRegex(ValueError, "archive unavailable"):
                    queue.capture(submitted["id"])
                tampered = copy.deepcopy(result)
                tampered["solver"]["actualBackend"] = "numpy-reference"
                with self.assertRaises(ValueError):
                    enforce_gpu_pilot_result(tampered)
                tampered = copy.deepcopy(result)
                tampered["gpuPilot"]["comparisons"]["finalTemperatureField"]["relativeRiseL2"] = 1.
                with self.assertRaisesRegex(ValueError, "final-field parity"):
                    enforce_gpu_pilot_result(tampered)
            finally:
                queue.close()


if __name__ == "__main__":
    unittest.main()
