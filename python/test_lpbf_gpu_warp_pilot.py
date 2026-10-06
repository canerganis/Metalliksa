"""Warp v2 archive identity regressions using synthetic schema fixtures only."""

import copy
import hashlib
import json
import shutil
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from lpbf_gpu_thermal import _python_json
from lpbf_gpu_warp_pilot import (
    CONTRACT_STATUS, MODEL_ID, WARP_SOLVER_ID, enforce_gpu_warp_pilot_result,
    validate_warp_pilot_request, _warp_device_evidence,
)
from lpbf_gpu_thermal import PILOT_JOB_TYPE
from lpbf_worker import Queue, _archive_run_kind
from lpbf_evidence import write_artifacts
from test_lpbf_gpu_archive_producer import CASE, GpuArchiveProducer, _test_dir


def _as_warp_v2(result):
    result = copy.deepcopy(result)
    result["runKind"] = "gpu-thermal-pilot"
    result["settings"]["executionEngine"] = "warp"
    result["label"] = "Unvalidated Warp v2 thermal parity pilot"
    result["confidence"] = "low"
    result["solver"]["id"] = WARP_SOLVER_ID
    result["solver"]["modelId"] = MODEL_ID
    result["gpuRunContract"]["schemaVersion"] = 2
    result["gpuRunContract"]["capture"].update(
        contractStatus=CONTRACT_STATUS, engineId="warp")
    result["provenance"]["deviceEvidence"].update(
        engineId="warp", warp="synthetic-schema-fixture",
        warpCudaToolkitVersion="12.8", cudaDriverVersion="13.0")
    result["provenance"]["deviceEvidence"].pop("torch", None)
    result["provenance"]["deviceEvidence"].pop("cudaRuntime", None)
    result["gpuPilot"]["scope"] = "same-model CPU/Warp numerical parity only"

    contract = result["gpuRunContract"]
    serialized = contract["serializedInputs"]
    hashes = contract["hashes"]
    serialized["requestJson"] = _python_json(result["settings"])
    hashes["requestHash"] = hashlib.sha256(serialized["requestJson"].encode()).hexdigest()
    result["provenance"]["inputHash"] = hashes["requestHash"]
    hashes["implementationHash"] = result["provenance"]["implementationHash"]
    return result


class WarpPilotArchiveIdentity(unittest.TestCase):
    def setUp(self):
        self.source = GpuArchiveProducer()
        self.result, self.folder = self.source._archived_fixture()
        self.result = _as_warp_v2(self.result)

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def test_structural_v2_snapshot_passes_metadata_and_full_byte_numeric_guard(self):
        # The reused CUDA fixture proves schema routing only, never Warp execution.
        self.assertIs(enforce_gpu_warp_pilot_result(self.result), self.result)
        self.assertIs(enforce_gpu_warp_pilot_result(self.result, self.folder), self.result)

    def test_rejects_detached_warp_engine_model_provenance_and_nested_cpu_core(self):
        mutations = (
            lambda result: result["gpuRunContract"]["capture"].update(engineId="torch"),
            lambda result: result["provenance"]["deviceEvidence"].update(engineId="torch"),
            lambda result: result["solver"].update(id="enthalpy-fv-6-cuda-pilot-1"),
            lambda result: result["provenance"].update(createdAt="2026-09-27T10:00:00"),
            lambda result: result["gpuPilot"]["cpu"]["coreContract"].update(inputSha256="0" * 64),
            lambda result: result["provenance"]["deviceEvidence"].update(cudaRuntime="12.8"),
            lambda result: result["provenance"]["deviceEvidence"].update(warpCudaToolkitVersion="unknown"),
            lambda result: result["provenance"]["deviceEvidence"].update(cudaDriverVersion=None),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                changed = copy.deepcopy(self.result)
                mutate(changed)
                with self.assertRaises(ValueError):
                    enforce_gpu_warp_pilot_result(changed)

    def test_request_validator_keeps_engine_selector_out_of_cpu_validator(self):
        raw = {"jobType": "gpu-thermal-pilot", "executionEngine": "warp", "backend": "cuda:0"}
        with patch("lpbf_gpu_thermal_warp._require_warp_cuda"), \
                patch("lpbf_gpu_thermal_warp._validate_candidate",
                      return_value=({"backend": "reference"}, {}, {})) as validate, \
                patch.dict("sys.modules", {"torch": None}):
            settings, _material = validate_warp_pilot_request(raw)
        self.assertEqual(settings["executionEngine"], "warp")
        self.assertEqual(settings["backend"], "cuda:0")
        self.assertNotIn("executionEngine", validate.call_args.args[0])
        with self.assertRaises(ValueError):
            validate_warp_pilot_request({"jobType": "gpu-thermal-pilot"})

    def test_worker_cache_restore_and_capture_keep_warp_v2_identity(self):
        raw = {**CASE, "executionEngine": "warp"}
        root = _test_dir("warp-queue")
        with patch("lpbf_gpu_thermal_warp._require_warp_cuda"), \
                patch("lpbf_worker.capabilities", return_value={"openfoamVersion": None}):
            queue = Queue(root, start=False)
            try:
                submitted = queue.submit(raw)
                destination = queue.root / submitted["id"]
                submitted_settings = json.loads((destination / "input.json").read_text())
                for source in self.folder.rglob("*"):
                    if source.is_file() and source.name not in ("result.json", "result.tmp"):
                        target = destination / source.relative_to(self.folder)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(source, target)
                (destination / "input.json").write_text(json.dumps(submitted_settings, allow_nan=False), encoding="utf-8")
                self.result["settings"] = submitted_settings
                self.result["gpuRunContract"]["serializedInputs"]["requestJson"] = _python_json(self.result["settings"])
                request_json = self.result["gpuRunContract"]["serializedInputs"]["requestJson"]
                self.result["gpuRunContract"]["hashes"]["requestHash"] = hashlib.sha256(request_json.encode()).hexdigest()
                self.result["provenance"]["inputHash"] = self.result["gpuRunContract"]["hashes"]["requestHash"]
                write_artifacts(self.result, destination)
                (destination / "result.json").write_text(json.dumps(self.result, allow_nan=False), encoding="utf-8")
                queue.update(submitted["id"], status="completed")
                restored = queue.get(submitted["id"])
                self.assertEqual(restored["status"], "completed", restored.get("error"))
                self.assertEqual(restored["requestSummary"]["executionEngine"], "warp")
                self.assertEqual(_archive_run_kind(PILOT_JOB_TYPE, restored["result"]), PILOT_JOB_TYPE)
                captured = queue.capture(submitted["id"])
                self.assertEqual(captured["contractStatus"], CONTRACT_STATUS)
                self.assertEqual(captured["runKind"], PILOT_JOB_TYPE)
                self.assertEqual(captured["inputJson"], self.result["gpuRunContract"]["serializedInputs"]["requestJson"])
                cache_hit = queue.submit(raw)
                self.assertEqual(cache_hit["id"], submitted["id"])
                self.assertTrue(cache_hit["cacheHit"])
                field_ref = self.result["gpuFieldArtifacts"]["states"]["gpu"]["fields"]["enthalpy_J_m3"]
                field_path = destination / field_ref["path"]
                tampered = field_path.read_bytes()
                field_path.write_bytes(bytes([tampered[0] ^ 1]) + tampered[1:])
                fresh = queue.submit(raw)
                self.assertNotEqual(fresh["id"], submitted["id"])
                self.assertFalse(fresh["cacheHit"])
                self.assertEqual(queue.get(submitted["id"])["status"], "failed")
            finally:
                queue.close()
                shutil.rmtree(root, ignore_errors=True)


class WarpDeviceEvidence(unittest.TestCase):
    def test_uses_own_toolkit_driver_and_synchronizes_without_torch(self):
        import lpbf_gpu_thermal_warp as candidate
        selected = SimpleNamespace(is_cuda=True, ordinal=0, name="test GPU", arch=89)
        api = SimpleNamespace(__version__="1.17.0", init=Mock(),
                              get_device=Mock(return_value=selected), synchronize_device=Mock(),
                              get_cuda_toolkit_version=Mock(return_value=(12, 8)),
                              get_cuda_driver_version=Mock(return_value=(13, 0)))
        with patch.object(candidate, "wp", api), patch.dict("sys.modules", {"torch": None}):
            evidence = _warp_device_evidence("cuda:0")
            self.assertEqual(evidence["computeCapability"], [8, 9])
            self.assertEqual(evidence["warpCudaToolkitVersion"], "12.8")
            self.assertEqual(evidence["cudaDriverVersion"], "13.0")
            self.assertNotIn("torch", evidence)
            self.assertNotIn("cudaRuntime", evidence)
            api.synchronize_device.assert_called_once_with(selected)
            for invalid in (None, (12,), (True, 8), (0, 8), (12, -1), "12.8"):
                api.get_cuda_toolkit_version.return_value = invalid
                with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, "toolkit"):
                    _warp_device_evidence("cuda:0")


if __name__ == "__main__":
    unittest.main()
