import base64
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from in625_bareplate_field import run_cpu
from lpbf_worker import (
    IN625_BAREPLATE_ARTIFACT,
    Queue,
    _bareplate_result_to_json,
    _enforce_bareplate_result,
    _validate_in625_bareplate_request,
    _write_deterministic_bareplate_field,
)


JOB = {
    "jobType": "in625-bareplate-field",
    "backend": "cpu",
    "config": {
        "shapeXYZ": [14, 14, 4],
        "cellSizeM": [0.00025, 0.00025, 0.00025],
        "steps": 2,
        "absorbedPowerW": 20.0,
        "scanStartXM": 0.00175,
        "scanYM": 0.00175,
    },
}


class In625BareplateWorkerTests(unittest.TestCase):
    def temporary_directory(self):
        return tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])

    def test_request_is_canonical_strict_and_bounded(self):
        normalized, config = _validate_in625_bareplate_request(JOB)
        self.assertEqual(normalized["jobType"], "in625-bareplate-field")
        self.assertEqual(normalized["backend"], "cpu")
        self.assertEqual(config.shape_xyz, (14, 14, 4))
        self.assertEqual(normalized["config"]["cellSizeM"], JOB["config"]["cellSizeM"])

        for bad in (
            {**JOB, "backend": "cuda"},
            {**JOB, "backend": "auto"},
            {**JOB, "timeout_s": 20},
            {**JOB, "unexpected": True},
            {**JOB, "config": {**JOB["config"], "shapeXYZ": [True, 8, 4]}},
            {**JOB, "config": {**JOB["config"], "steps": 0}},
            {**JOB, "config": {**JOB["config"], "cellSizeM": [1e-4, 0, 1e-4]}},
            {**JOB, "config": {**JOB["config"], "shape_xyz": [8, 8, 4]}},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                _validate_in625_bareplate_request(bad)

        too_many_cells = {**JOB, "config": {**JOB["config"], "shapeXYZ": [1001, 1001, 2]}}
        with self.assertRaisesRegex(ValueError, "cell count"):
            _validate_in625_bareplate_request(too_many_cells)

    def test_field_artifact_bytes_and_digest_are_deterministic(self):
        normalized, config = _validate_in625_bareplate_request(JOB)
        output = run_cpu(config)
        with self.temporary_directory() as tmp:
            first, second = Path(tmp) / "first.bin", Path(tmp) / "second.bin"
            _write_deterministic_bareplate_field(first, output)
            _write_deterministic_bareplate_field(second, output)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(first.stat().st_size, 14 * 14 * 4 * 8)
            result = _bareplate_result_to_json(normalized, config, output, tmp)
            self.assertEqual(result["field"]["artifact"], IN625_BAREPLATE_ARTIFACT)
            self.assertEqual(result["field"]["byteOrder"], "little-endian")
            self.assertEqual(result["field"]["shapeXYZ"], [14, 14, 4])
            self.assertEqual(result["field"]["encoding"], "little-endian")
            self.assertEqual(result["field"]["scope"], "final cell-centered temperature field only; no interface interpolation")
            self.assertEqual(result["field"]["sha256"], hashlib.sha256((Path(tmp) / IN625_BAREPLATE_ARTIFACT).read_bytes()).hexdigest())

    def test_queue_cpu_execution_result_and_artifact_integrity(self):
        with self.temporary_directory() as tmp:
            queue = Queue(tmp, start=False)
            try:
                submitted = queue.submit(JOB)
                self.assertEqual(submitted["requestSummary"]["jobType"], "in625-bareplate-field")
                self.assertEqual(submitted["requestSummary"]["backend"], "cpu")
                queue.update(submitted["id"], status="running")
                queue.execute(submitted["id"])
                state = queue.get(submitted["id"])
                self.assertEqual(state["status"], "completed", state.get("error"))
                result = state["result"]
                captured = queue.capture(submitted["id"])
                self.assertEqual(result["runKind"], "bounded-material-screening")
                self.assertEqual(captured["runKind"], "bounded-material-screening")
                self.assertEqual(json.loads(captured["resultJson"])["runKind"], "bounded-material-screening")
                self.assertEqual(json.loads(captured["inputJson"]), result["settings"])
                self.assertEqual(json.loads(captured["materialJson"]), result["material"])
                self.assertEqual(result["settings"], state["requestSummary"] | {"jobType": "in625-bareplate-field"})
                self.assertEqual(result["solver"]["actualBackend"], "cpu")
                self.assertEqual(result["validationStatus"], "unvalidated-literature-model-screening")
                self.assertIs(result["productionReady"], False)
                self.assertEqual(result["energyBalance"]["losses_J"], 0.0)
                self.assertLessEqual(result["energyBalance"]["relativeError"], 0.01)
                self.assertEqual(result["field"]["encoding"], "little-endian")
                self.assertEqual(result["field"]["arrayOrder"], "z,y,x")
                self.assertEqual(result["field"]["scope"], "final cell-centered temperature field only; no interface interpolation")
                self.assertTrue({"input.json", "capabilities.json", IN625_BAREPLATE_ARTIFACT}.issubset(
                    {artifact["path"] for artifact in result["artifacts"]}))
                self.assertEqual({artifact["path"] for artifact in result["artifacts"]},
                                 {artifact["path"] for artifact in json.loads(captured["resultJson"])["artifacts"]})
                entry = next(a for a in result["artifacts"] if a["path"] == IN625_BAREPLATE_ARTIFACT)
                fetched = queue.artifact({"id": submitted["id"], "name": IN625_BAREPLATE_ARTIFACT})
                self.assertEqual(hashlib.sha256(base64.b64decode(fetched["content"])).hexdigest(), entry["sha256"])
            finally:
                queue.close()

    def test_cache_identity_includes_backend_device_and_config(self):
        with self.temporary_directory() as tmp:
            queue = Queue(tmp, start=False)
            try:
                first = queue.submit(JOB)
                duplicate = queue.submit(JOB)
                self.assertEqual(first["id"], duplicate["id"])
                self.assertTrue(duplicate["deduplicated"])
                changed_config = {**JOB, "config": {**JOB["config"], "steps": 3}}
                second = queue.submit(changed_config)
                self.assertNotEqual(first["id"], second["id"])
                with patch("lpbf_worker._check_in625_bareplate_cuda_device"):
                    cuda0 = queue.submit({**JOB, "backend": "cuda:0"})
                    cuda1 = queue.submit({**JOB, "backend": "cuda:1"})
                self.assertNotEqual(cuda0["id"], first["id"])
                self.assertNotEqual(cuda0["id"], cuda1["id"])
            finally:
                queue.close()

    def test_explicit_cuda_failure_propagates_without_cpu_fallback(self):
        with self.temporary_directory() as tmp:
            normalized, config = _validate_in625_bareplate_request({**JOB, "backend": "cuda:7"})
            with patch("in625_bareplate_field.run_cuda", side_effect=RuntimeError("explicit CUDA unavailable")) as cuda:
                from lpbf_worker import _run_in625_bareplate_job
                with self.assertRaisesRegex(RuntimeError, "explicit CUDA unavailable"):
                    _run_in625_bareplate_job(normalized, tmp)
                cuda.assert_called_once_with(config, "cuda:7")

    def test_real_cuda_queue_path_when_device_exists(self):
        try:
            import torch
            available = torch.cuda.is_available() and torch.cuda.device_count() > 0
        except ImportError:
            available = False
        if not available:
            self.skipTest("CUDA unavailable; explicit IN625 worker device path unverified")
        with self.temporary_directory() as tmp:
            queue = Queue(tmp, start=False)
            try:
                submitted = queue.submit({**JOB, "backend": "cuda:0"})
                queue.update(submitted["id"], status="running")
                queue.execute(submitted["id"])
                state = queue.get(submitted["id"])
                self.assertEqual(state["status"], "completed", state.get("error"))
                self.assertEqual(state["result"]["solver"]["actualBackend"], "cuda:0")
                self.assertEqual(state["result"]["provenance"]["deviceEvidence"]["selected"], "cuda:0")
                self.assertTrue(state["result"]["provenance"]["deviceEvidence"]["noCpuFallback"])
            finally:
                queue.close()

    def test_malformed_persisted_result_is_rejected_as_value_error(self):
        normalized, config = _validate_in625_bareplate_request(JOB)
        output = run_cpu(config)
        with self.temporary_directory() as tmp:
            result = _bareplate_result_to_json(normalized, config, output, tmp)
            for path, value in (("solver", None), ("provenance", None), ("field", None), ("energyBalance", [])):
                corrupted = dict(result)
                corrupted[path] = value
                with self.subTest(path=path), self.assertRaises(ValueError):
                    _enforce_bareplate_result(corrupted, normalized)


if __name__ == "__main__":
    unittest.main()
