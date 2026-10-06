"""Worker restore/cache/capture tests using committed CUDA archive bytes; no solver run."""

import copy
import hashlib
import json
from pathlib import Path
import shutil
import unittest
from uuid import uuid4
from unittest.mock import patch

import numpy as np

from lpbf_worker import BINARY, Queue, _archive_run_kind
from lpbf_simulation import fingerprint


ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE = ROOT / "docs" / "LPBF_GPU_BOUND_ARCHIVE_ACCEPTANCE_2026-09-27"
JOB_ID = "f" * 32


def _write_json(path, value):
    path.write_text(json.dumps(value, allow_nan=False), encoding="utf-8")


def _bound_job(folder):
    shutil.copytree(ACCEPTANCE, folder)
    result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
    settings = result["settings"]
    _write_json(folder / "input.json", settings)
    input_path = folder / "input.json"
    input_hash = hashlib.sha256(input_path.read_bytes()).hexdigest()
    for ref in result["artifacts"]:
        if ref["path"] == "input.json":
            ref.update(size_bytes=input_path.stat().st_size, sha256=input_hash)
    result["runKind"] = "gpu-thermal-pilot"
    result["provenance"]["runtime_s"] = 0.01
    result["provenance"]["executionRuntime"] = {
        "executable": "test-python", "python": "3.12", "platform": "test", "numpy": "test"}
    _write_json(folder / "result.json", result)
    return result


def _rehash_field(folder, result, backend, quantity, mutate):
    ref = result["gpuFieldArtifacts"]["states"][backend]["fields"][quantity]
    path = folder / ref["path"]
    values = np.fromfile(path, dtype="<f8")
    mutate(values)
    values.astype("<f8", copy=False).tofile(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    ref["sha256"] = digest
    for manifest_ref in result["artifacts"]:
        if manifest_ref["path"] == ref["path"]:
            manifest_ref.update(size_bytes=path.stat().st_size, sha256=digest)
            break
    _write_json(folder / "result.json", result)


class GpuBoundWorkerCapture(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).parent / ".tmp-gpu-archive-tests" / f"bound-worker-{uuid4().hex}"
        self.root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root)
        self.folder = self.root / JOB_ID
        self.result = _bound_job(self.folder)
        self.queue = Queue(self.root, start=False)
        self.addCleanup(self.queue.close)
        with self.queue.connect() as db:
            db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?)",
                       (JOB_ID, None, "completed", 1., "", None, 1.))

    def test_bound_result_restore_and_capture_preserve_distinct_contract(self):
        state = self.queue.get(JOB_ID)
        self.assertEqual(state["status"], "completed", state.get("error"))
        self.assertIn("gpuRunContract", state["result"])
        self.assertNotIn("coreContract", state["result"])
        captured = self.queue.capture(JOB_ID)
        self.assertEqual(captured["contractStatus"], "gpu-pilot-v1-bound")
        self.assertEqual(captured["runKind"], "gpu-thermal-pilot")
        inputs = self.result["gpuRunContract"]["serializedInputs"]
        self.assertEqual(captured["inputJson"], inputs["requestJson"])
        self.assertEqual(captured["materialJson"], inputs["materialJson"])
        self.assertEqual(json.loads(captured["resultJson"])["runKind"], "gpu-thermal-pilot")
        self.assertEqual(_archive_run_kind("gpu-thermal-pilot", self.result), "gpu-thermal-pilot")

    def test_rehashed_temperature_or_enthalpy_tampering_fails_restore_and_cache(self):
        for backend, quantity in (("gpu", "temperature_K"), ("cpu", "enthalpy_J_m3")):
            with self.subTest(backend=backend, quantity=quantity):
                # Start from the committed same-run bytes for each tampering case.
                shutil.rmtree(self.folder)
                self.result = _bound_job(self.folder)
                self.queue.update(JOB_ID, status="completed", error=None)
                _rehash_field(self.folder, self.result, backend, quantity,
                              lambda values: values.__setitem__(0, values[0] + 1.0))
                restored = self.queue.get(JOB_ID)
                self.assertEqual(restored["status"], "failed")
                self.assertNotIn("result", restored)
                self.assertIn("integrity failed", restored["error"])

    def test_cache_hit_revalidates_fields_before_reuse(self):
        settings = self.result["settings"]
        material = self.result["material"]
        self.queue.caps["binaryHash"] = hashlib.sha256(BINARY.read_bytes()).hexdigest() if BINARY.is_file() else None
        self.queue.caps["openfoamThermal"] = bool(self.queue.caps["openfoamVersion"] and self.queue.caps["binaryHash"])
        key_payload = fingerprint(settings, material) + json.dumps(self.queue.caps, sort_keys=True)
        cache_key = hashlib.sha256(key_payload.encode()).hexdigest()
        with self.queue.connect() as db:
            db.execute("UPDATE jobs SET cache_key=? WHERE id=?", (cache_key, JOB_ID))
        with patch("lpbf_gpu_thermal.validate_pilot_request", return_value=(settings, material)):
            cached = self.queue.submit(settings)
        self.assertTrue(cached["cacheHit"])
        self.assertEqual(cached["id"], JOB_ID)

    def test_cache_rejects_rehashed_temperature_artifact(self):
        settings = self.result["settings"]
        material = self.result["material"]
        ref = self.result["gpuFieldArtifacts"]["states"]["gpu"]["fields"]["temperature_K"]
        self.queue.caps["binaryHash"] = hashlib.sha256(BINARY.read_bytes()).hexdigest() if BINARY.is_file() else None
        self.queue.caps["openfoamThermal"] = bool(self.queue.caps["openfoamVersion"] and self.queue.caps["binaryHash"])
        cache_key = hashlib.sha256((fingerprint(settings, material)
                                    + json.dumps(self.queue.caps, sort_keys=True)).encode()).hexdigest()
        with self.queue.connect() as db:
            db.execute("UPDATE jobs SET cache_key=? WHERE id=?", (cache_key, JOB_ID))
        _rehash_field(self.folder, self.result, "gpu", "temperature_K",
                      lambda values: values.__setitem__(0, values[0] + 1.0))
        with patch("lpbf_gpu_thermal.validate_pilot_request", return_value=(settings, material)):
            fresh = self.queue.submit(settings)
        self.assertFalse(fresh["cacheHit"])
        self.assertEqual(self.queue.get(JOB_ID)["status"], "failed")
        self.assertIn("corrupt", self.queue.get(JOB_ID)["error"])

    def test_legacy_unbound_gpu_result_remains_view_only(self):
        result = copy.deepcopy(self.result)
        result.pop("gpuRunContract")
        result.pop("gpuFieldArtifacts")
        result.pop("runKind")
        result["artifacts"] = []
        _write_json(self.folder / "result.json", result)
        self.assertIsNone(_archive_run_kind("gpu-thermal-pilot", result))
        state = self.queue.get(JOB_ID)
        self.assertEqual(state["status"], "completed")
        with self.assertRaisesRegex(ValueError, "distinct bound archive contract"):
            self.queue.capture(JOB_ID)


if __name__ == "__main__":
    unittest.main()
