"""Focused archive contract and opt-in producer tests; no CUDA execution."""

import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from lpbf_gpu_thermal import (GPU_SOLVER_ID, PARITY_TARGETS, PILOT_JOB_TYPE,
                              enforce_gpu_pilot_result, run_queued_pilot)
from lpbf_core_contract import build_core_contract
from lpbf_core_physics import scan_segments
from lpbf_gpu_pilot_artifacts import write_pilot_artifacts


DEVICE = "cuda:0"
MODEL = "stationary-enthalpy-conduction-layer-conforming-v1"
CASE = {"jobType": PILOT_JOB_TYPE, "mode": "standard", "backend": DEVICE,
        "material": "Inconel 718", "power_W": 60, "speed_mm_s": 1200,
        "mesh_um": 40, "maxDt_s": 2e-7, "layer_um": 80,
        "trackLength_um": 200, "cooling_s": 2e-5, "dwell_s": 0}


def _validated_inputs():
    from lpbf_gpu_thermal import validate_pilot_request
    with patch("lpbf_gpu_thermal.require_cuda", return_value=(None, None)):
        return validate_pilot_request(CASE)


def _state(settings=None):
    if settings is None:
        settings, _ = _validated_inputs()
    mesh_m = settings["mesh_um"] * 1e-6
    cpu_input = {key: value for key, value in settings.items() if key != "jobType"}
    _, final_time = scan_segments(cpu_input)
    return {
        "coordinates_m": np.array([[0., 0., 0.], [mesh_m, 0., 0.]], dtype=np.float64),
        "temperature_K": np.array([settings["preheat_C"] + 273.15, 400.]),
        "enthalpy_J_m3": np.array([1e9, 2e9]),
        "density_kg_m3": np.array([8000., 8000.]),
        "accepted_dt_s": np.array([final_time / 2, final_time / 2]),
        "time_s": final_time, "initial_temperature_K": settings["preheat_C"] + 273.15,
        "cell_volume_m3": mesh_m ** 3,
    }


def _parity(settings=None, material=None):
    if settings is None or material is None:
        settings, material = _validated_inputs()
    cpu_input = {key: value for key, value in settings.items() if key != "jobType"}
    cpu_input["backend"] = "reference"
    core = build_core_contract(cpu_input, material, "enthalpy-fv-6", "standard")
    state = _state(settings)
    mesh_m = settings["mesh_um"] * 1e-6
    steps = len(state["accepted_dt_s"])
    stored = math.fsum(map(float, state["enthalpy_J_m3"])) * state["cell_volume_m3"]
    cpu_disc = {"cells": 2, "mesh_m": mesh_m, "steps": steps,
                "minimumDt_s": float(np.min(state["accepted_dt_s"])),
                "maximumDt_s": float(np.max(state["accepted_dt_s"])),
                "meanDt_s": state["time_s"] / steps}
    gpu = {
        "solver": {"id": GPU_SOLVER_ID, "modelId": MODEL, "actualBackend": DEVICE,
                   "thermalEvolutionDevice": DEVICE, "sourceIntegrationDevice": "cpu",
                   "sourceTimestepLimiterDevice": "cpu", "dtype": "float64"},
        "metrics": {"peakTemperature_K": 1000., "width_um": 1., "depth_um": 1.,
                    "length_um": 1., "volume_um3": 1.},
        "energyBalance": {"input_J": stored, "losses_J": 0., "stored_J": stored, "relativeError": 0.},
        "discretization": dict(cpu_disc), "peakExtraction": {},
    }
    expected = ("finalSampling", "finalTemperatureField", "peakTemperature_K", "input_J",
                "losses_J", "stored_J", "width_um", "depth_um", "length_um", "volume_um3")
    comparisons = {name: {"status": "pass", "cpu": 1., "gpu": 1.,
                          "relativeDifference": 0.} for name in expected}
    comparisons["peakTemperature_K"] = {"status": "pass", "cpu": 1000., "gpu": 1000.,
                                        "relativeDifference": 0.}
    comparisons["input_J"] = {"status": "pass", "cpu": stored, "gpu": stored, "relativeDifference": 0.}
    comparisons["losses_J"] = {"status": "pass", "cpu": 0., "gpu": 0., "relativeDifference": 0.}
    comparisons["stored_J"] = {"status": "pass", "cpu": stored, "gpu": stored, "relativeDifference": 0.}
    for name in ("width_um", "depth_um", "length_um"):
        comparisons[name] = {"status": "pass", "cpu": 1., "gpu": 1.,
                             "absoluteDifference_um": 0.}
    comparisons["finalSampling"] = {"status": "pass", "cpuSteps": steps, "gpuSteps": steps,
        "cellCount": 2, "cpuFinalTime_s": state["time_s"], "cpuFrameTime_s": state["time_s"],
        "gpuFinalTime_s": state["time_s"], "expectedEnd_s": state["time_s"]}
    comparisons["finalTemperatureField"] = {"status": "pass", "relativeRiseL2": 0.,
        "relativeRiseMax": 0., "cpuEncoding": "float64 final state observer",
        "gpuEncoding": "float64 final state"}
    return {"status": "pass", "scope": "same-model CPU/GPU numerical parity only",
        "experimentalValidation": False, "targets": dict(PARITY_TARGETS), "gpu": gpu,
        "cpu": {"solver": {"id": "enthalpy-fv-6"}, "coreContract": core,
                "material": {key: material[key] for key in ("name", "materialId", "materialRevisionSha256", "version")},
                "discretization": cpu_disc, "resolvedSettings": cpu_input}, "comparisons": comparisons}


def _write_capture(folder):
    settings, _ = _validated_inputs()
    state = _state(settings)
    return write_pilot_artifacts(folder, state, state)


def _test_dir(name):
    root = Path(__file__).parent / ".tmp-gpu-archive-tests"
    root.mkdir(exist_ok=True)
    target = root / name
    if target.exists():
        shutil.rmtree(target)
    target.mkdir()
    return target


class GpuArchiveProducer(unittest.TestCase):
    def _fake_cuda(self):
        return SimpleNamespace(
            cuda=SimpleNamespace(synchronize=lambda _device: None,
                get_device_properties=lambda _device: SimpleNamespace(name="fixture GPU"),
                get_device_capability=lambda _device: (9, 0)),
            version=SimpleNamespace(cuda="fixture"), __version__="fixture-torch"), DEVICE

    def _producer_patches(self, parity, capture=False):
        settings, material = _validated_inputs()
        def compare(_reference, _device, **kwargs):
            if capture:
                self.assertTrue(callable(kwargs.get("evidence_sink")))
                kwargs["evidence_sink"](_state(), _state())
            else:
                self.assertNotIn("evidence_sink", kwargs)
            return copy.deepcopy(parity)
        return (
            patch("lpbf_gpu_thermal.validate_pilot_request", return_value=(dict(settings), dict(material))),
            patch("lpbf_gpu_thermal.compare_with_cpu", side_effect=compare),
            patch("lpbf_gpu_thermal.require_cuda", return_value=self._fake_cuda()),
            patch("lpbf_gpu_thermal.implementation_fingerprint", return_value="b" * 64),
        )

    def test_opt_in_producer_writes_same_run_capture_and_whole_folder_manifest(self):
        settings, material = _validated_inputs()
        parity = _parity(settings, material)
        folder = _test_dir("producer")
        try:
            (folder / "input.json").write_text("{}", encoding="utf-8")
            (folder / "capabilities.json").write_text("{}", encoding="utf-8")
            patches = self._producer_patches(parity, capture=True)
            with patches[0], patches[1], patches[2], patches[3]:
                result = run_queued_pilot(dict(CASE), artifact_dir=folder)
            self.assertIn("gpuRunContract", result)
            self.assertIn("gpuFieldArtifacts", result)
            self.assertNotIn("coreContract", result)
            self.assertEqual(len(result["gpuFieldArtifacts"]["states"]), 2)
            self.assertEqual(len([ref for state in result["gpuFieldArtifacts"]["states"].values()
                                  for ref in state["fields"].values()]), 10)
            manifest_paths = {item["path"] for item in result["artifacts"]}
            self.assertTrue({"input.json", "capabilities.json"}.issubset(manifest_paths))
            self.assertTrue(any(path.startswith("gpu-pilot/") for path in manifest_paths))
            enforce_gpu_pilot_result(result, artifact_dir=folder)
        finally:
            shutil.rmtree(folder)

    def test_default_path_keeps_legacy_empty_artifact_view(self):
        settings, material = _validated_inputs()
        patches = self._producer_patches(_parity(settings, material))
        with patches[0], patches[1], patches[2], patches[3]:
            result = run_queued_pilot(dict(CASE))
        self.assertEqual(result["artifacts"], [])
        self.assertNotIn("gpuRunContract", result)
        self.assertNotIn("gpuFieldArtifacts", result)
        enforce_gpu_pilot_result(result)

    def _archived_fixture(self):
        folder = _test_dir("guard-fixture")
        try:
            settings, material = _validated_inputs()
            reference = {key: value for key, value in settings.items() if key != "jobType"}
            reference["backend"] = "reference"
            resolved_settings = dict(reference)
            core = build_core_contract(resolved_settings, material, "enthalpy-fv-6", "standard")
            parity = _parity(settings, material)
            inputs = {"requestJson": json.dumps(settings, sort_keys=True, allow_nan=False),
                      "materialJson": json.dumps(material, sort_keys=True, allow_nan=False),
                      "cpuInputJson": json.dumps(reference, sort_keys=True, allow_nan=False),
                      "cpuResolvedSettingsJson": json.dumps(resolved_settings, sort_keys=True, allow_nan=False)}
            hashes = {name.replace("Json", "Hash"): hashlib.sha256(value.encode("utf-8")).hexdigest()
                      for name, value in inputs.items()}
            # Names are spelled explicitly in the public contract.
            hashes["implementationHash"] = "b" * 64
            result = {
                "schemaVersion": 1, "jobType": PILOT_JOB_TYPE,
                "requestedMode": "standard", "label": "Unvalidated CUDA thermal parity pilot",
                "confidence": "low", "settings": settings, "material": dict(material),
                "effectiveMode": "gpu-pilot", "validationStatus": "unvalidated", "productionReady": False,
                "artifacts": [], "solver": dict(parity["gpu"]["solver"]),
                "energyBalance": dict(parity["gpu"]["energyBalance"]),
                "metrics": parity["gpu"]["metrics"],
                "discretization": dict(parity["gpu"]["discretization"]),
                "gpuPilot": {"experimentalValidation": False, "status": parity["status"],
                    "targets": dict(PARITY_TARGETS),
                    "cpu": {**parity["cpu"], "coreContract": core},
                    "comparisons": parity["comparisons"]},
                "provenance": {"inputHash": hashes["requestHash"], "implementationHash": "b" * 64,
                    "materialVersion": material["version"], "createdAt": "2026-09-27T10:00:00+00:00",
                    "deviceEvidence": {"selected": DEVICE, "name": "fixture GPU",
                        "computeCapability": [9, 0], "torch": "fixture", "cudaRuntime": "fixture",
                        "thermalEvolution": DEVICE,
                        "sourceIntegration": "cpu", "sourceTimestepLimiter": "cpu", "synchronizedAfterSolve": True}},
            }
            result["gpuRunContract"] = {"schemaVersion": 1, "runKind": PILOT_JOB_TYPE,
                "capture": {"contractStatus": "gpu-pilot-v1-bound", "modelId": MODEL,
                    "backend": DEVICE, "device": DEVICE, "dtype": "float64"},
                "serializedInputs": inputs, "hashes": hashes}
            result["gpuRunContract"]["hashes"]["cpuResolvedSettingsHash"] = hashes["cpuResolvedSettingsHash"]
            result["gpuFieldArtifacts"] = _write_capture(folder)
            from lpbf_evidence import write_artifacts
            write_artifacts(result, folder)
            # Duplicate mutable state outside the temporary folder for pure guard tests.
            copy_result = copy.deepcopy(result)
            copy_folder = _test_dir("guard-fixture-copy")
            for path in folder.rglob("*"):
                if path.is_file():
                    target = copy_folder / path.relative_to(folder)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(path.read_bytes())
            return copy_result, copy_folder
        finally:
            shutil.rmtree(folder)

    def test_guard_rejects_null_partial_duplicate_and_tampered_json_bindings(self):
        result, folder = self._archived_fixture()
        try:
            enforce_gpu_pilot_result(result, artifact_dir=folder)
            for mutation in ("null", "partial", "duplicate", "tampered-hash", "tampered-input"):
                changed = copy.deepcopy(result)
                if mutation == "null":
                    changed["gpuRunContract"] = None
                elif mutation == "partial":
                    del changed["gpuFieldArtifacts"]
                elif mutation == "duplicate":
                    inputs = changed["gpuRunContract"]["serializedInputs"]
                    inputs["requestJson"] = '{"backend":"cuda:0","backend":"cuda:1"}'
                elif mutation == "tampered-hash":
                    changed["gpuRunContract"]["hashes"]["materialHash"] = "c" * 64
                else:
                    changed["gpuRunContract"]["serializedInputs"]["requestJson"] = "{}"
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    enforce_gpu_pilot_result(changed)
        finally:
            shutil.rmtree(folder)

    def test_guard_requires_descriptor_refs_in_manifest_and_valid_folder_bytes(self):
        result, folder = self._archived_fixture()
        try:
            missing = copy.deepcopy(result)
            missing["artifacts"] = [item for item in missing["artifacts"]
                                    if not item["path"].startswith("gpu-pilot/")]
            with self.assertRaisesRegex(ValueError, "not bound"):
                enforce_gpu_pilot_result(missing)
            target = folder / result["gpuFieldArtifacts"]["states"]["cpu"]["fields"]["temperature_K"]["path"]
            target.write_bytes(target.read_bytes() + b"x")
            with self.assertRaisesRegex(ValueError, "folder manifest"):
                enforce_gpu_pilot_result(result, artifact_dir=folder)
        finally:
            shutil.rmtree(folder)

    def test_archive_guard_is_snapshot_only_and_requires_complete_folder_manifest(self):
        result, folder = self._archived_fixture()
        try:
            with patch("lpbf_gpu_thermal.validate", side_effect=AssertionError("live validation used")):
                enforce_gpu_pilot_result(result, artifact_dir=folder)
            (folder / "unlisted.bin").write_bytes(b"extra")
            with self.assertRaisesRegex(ValueError, "manifest is incomplete"):
                enforce_gpu_pilot_result(result, artifact_dir=folder)
        finally:
            shutil.rmtree(folder)

    def test_archive_guard_rejects_malformed_identity_numeric_and_dtype_bindings(self):
        result, folder = self._archived_fixture()
        try:
            mutations = (
                lambda item: item.update(schemaVersion=True),
                lambda item: item.update(requestedMode="screening"),
                lambda item: item.update(label=False),
                lambda item: item["gpuPilot"].update(targets={**item["gpuPilot"]["targets"],
                                                            "integralRelativeMax": True}),
                lambda item: item["energyBalance"].update(relativeError=False),
                lambda item: item["metrics"].update(peakTemperature_K=0.),
                lambda item: item["solver"].update(dtype="float32"),
                lambda item: item["provenance"]["deviceEvidence"].update(computeCapability=[float("nan"), 0]),
            )
            for index, mutate in enumerate(mutations):
                changed = copy.deepcopy(result)
                mutate(changed)
                with self.subTest(index=index), self.assertRaises(ValueError):
                    enforce_gpu_pilot_result(changed, artifact_dir=folder)
        finally:
            shutil.rmtree(folder)

    def test_archive_field_metadata_malformed_types_fail_as_value_errors(self):
        result, folder = self._archived_fixture()
        try:
            mutations = (
                lambda item: item["discretization"].pop("steps"),
                lambda item: item["gpuPilot"]["cpu"].update(discretization=None),
                lambda item: item["gpuPilot"]["comparisons"]["finalSampling"].pop("cpuFinalTime_s"),
                lambda item: item["gpuPilot"]["comparisons"]["finalSampling"].update(cpuFinalTime_s="2"),
                lambda item: item["gpuPilot"]["cpu"]["discretization"].update(mesh_m="1"),
                lambda item: item["gpuPilot"]["cpu"]["discretization"].update(mesh_m=1e308),
                lambda item: item["discretization"].update(mesh_m=1e-200),
            )
            for index, mutate in enumerate(mutations):
                changed = copy.deepcopy(result)
                mutate(changed)
                with self.subTest(index=index), self.assertRaises(ValueError):
                    enforce_gpu_pilot_result(changed, artifact_dir=folder)
        finally:
            shutil.rmtree(folder)


if __name__ == "__main__":
    unittest.main()
