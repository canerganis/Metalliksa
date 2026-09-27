"""Versioned Warp v2 producer and historical archive guard for GPU pilots."""

import datetime
import hashlib
import json
import math
import os
import re
from pathlib import Path

from lpbf_gpu_thermal import (
    MAX_ARCHIVE_FILES, MAX_ARCHIVE_INPUT_JSON_BYTES, MAX_ARCHIVE_TOTAL_BYTES,
    PARITY_TARGETS, PILOT_JOB_TYPE, _field_parity, _parse_bound_json,
    _run_cpu_with_final, _strict_json_equal, _python_json, _parse_created_at,
    _enforce_gpu_archive_field_metadata,
)
from lpbf_core_contract import _encoded, build_core_contract

WARP_SOLVER_ID = "enthalpy-fv-6-warp-candidate-1"
MODEL_ID = "stationary-enthalpy-conduction-layer-conforming-v1"
CONTRACT_STATUS = "gpu-pilot-v2-warp-bound"
CONTRACT_KEYS = {"schemaVersion", "runKind", "capture", "serializedInputs", "hashes"}
CAPTURE_KEYS = {"contractStatus", "modelId", "backend", "device", "dtype", "engineId"}
INPUT_KEYS = {"requestJson", "materialJson", "cpuInputJson", "cpuResolvedSettingsJson"}
HASH_KEYS = {"requestHash", "materialHash", "cpuInputHash", "cpuResolvedSettingsHash", "implementationHash"}
COMPARISON_KEYS = ("finalSampling", "finalTemperatureField", "peakTemperature_K", "input_J",
                   "losses_J", "stored_J", "width_um", "depth_um", "length_um", "volume_um3")
SHA_RE = re.compile(r"[a-f0-9]{64}\Z")
EXCLUDED_ROOT_FILES = {"result.json", "result.tmp", "progress.log"}


def validate_warp_pilot_request(raw):
    """Resolve Warp selection using the CPU validator without passing its selector through."""
    if (not isinstance(raw, dict) or raw.get("executionEngine") != "warp"
            or raw.get("jobType") != PILOT_JOB_TYPE):
        raise ValueError("Explicit Warp executionEngine required")
    from lpbf_gpu_thermal_warp import _require_warp_cuda, _validate_candidate
    device = raw.get("backend")
    _require_warp_cuda(device)
    validated, material, _domain = _validate_candidate(
        {key: value for key, value in raw.items() if key != "executionEngine"})
    return {**validated, "backend": device, "jobType": PILOT_JOB_TYPE,
            "executionEngine": "warp"}, material


def _warp_device_evidence(device):
    """Capture Warp's own device and build-toolkit/driver identities after synchronization."""
    from lpbf_gpu_thermal_warp import _require_warp_cuda, wp
    selected = _require_warp_cuda(device)
    wp.synchronize_device(selected)

    def version_text(value, label):
        if (not isinstance(value, tuple) or len(value) != 2
                or any(type(part) is not int or part < 0 for part in value) or value[0] == 0):
            raise ValueError(f"Warp {label} version is unavailable for capture identity")
        return f"{value[0]}.{value[1]}"

    version = getattr(wp, "__version__", None)
    if (not isinstance(version, str) or not version.strip()
            or not isinstance(selected.name, str) or not selected.name.strip()
            or type(selected.arch) is not int or selected.arch <= 0):
        raise ValueError("Warp runtime/device identity is unavailable for capture")
    return {
        "engineId": "warp", "selected": device, "name": selected.name,
        "computeCapability": [selected.arch // 10, selected.arch % 10], "warp": version,
        # Toolkit means the version used to build Warp, not Torch's CUDA build.
        "warpCudaToolkitVersion": version_text(wp.get_cuda_toolkit_version(), "CUDA toolkit"),
        "cudaDriverVersion": version_text(wp.get_cuda_driver_version(), "CUDA driver"),
        "thermalEvolution": device, "sourceIntegration": "cpu",
        "sourceTimestepLimiter": "cpu", "synchronizedAfterSolve": True,
    }


def _digest_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _dict(value, name):
    if not isinstance(value, dict):
        raise ValueError(f"Invalid Warp GPU archive {name}")
    return value


def _positive_finite(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"Invalid Warp GPU archive {name}")
    return value


def _nonnegative_finite(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"Invalid Warp GPU archive {name}")
    return value


def _comparison_report(cpu, gpu, frame, cpu_temperature, cpu_coordinates, gpu_field):
    from lpbf_gpu_thermal import _field_parity

    alignment, field = _field_parity(cpu, gpu, frame, cpu_temperature, cpu_coordinates, gpu_field)
    comparisons = {"finalSampling": alignment, "finalTemperatureField": field}
    scalar_pairs = {
        "peakTemperature_K": (cpu["metrics"]["peakTemperature_K"], gpu["metrics"]["peakTemperature_K"]),
        "input_J": (cpu["energyBalance"]["input_J"], gpu["energyBalance"]["input_J"]),
        "losses_J": (cpu["energyBalance"]["losses_J"], gpu["energyBalance"]["losses_J"]),
        "stored_J": (cpu["energyBalance"]["stored_J"], gpu["energyBalance"]["stored_J"]),
    }
    for name, (cpu_value, gpu_value) in scalar_pairs.items():
        difference = abs(cpu_value - gpu_value) / max(abs(cpu_value), 1e-30)
        comparisons[name] = {"cpu": cpu_value, "gpu": gpu_value, "relativeDifference": difference,
                             "status": "pass" if difference <= PARITY_TARGETS["integralRelativeMax"] else "failed"}
    cell_um = gpu["discretization"]["mesh_m"] * 1e6
    for name in ("width_um", "depth_um", "length_um"):
        cpu_value, gpu_value = cpu["metrics"][name], gpu["metrics"][name]
        difference = abs(cpu_value - gpu_value)
        comparisons[name] = {"cpu": cpu_value, "gpu": gpu_value, "absoluteDifference_um": difference,
                             "status": "inconclusive" if cpu_value == gpu_value == 0 else (
                                 "pass" if difference <= PARITY_TARGETS["widthDepthAbsoluteCellsMax"] * cell_um
                                 else "failed")}
    cpu_value, gpu_value = cpu["metrics"]["volume_um3"], gpu["metrics"]["volume_um3"]
    difference = abs(cpu_value - gpu_value) / max(cpu_value, 1e-30)
    comparisons["volume_um3"] = {"cpu": cpu_value, "gpu": gpu_value, "relativeDifference": difference,
                                 "status": "inconclusive" if cpu_value == gpu_value == 0 else (
                                     "pass" if difference <= PARITY_TARGETS["peakMeltVolumeRelativeMax"]
                                     else "failed")}
    statuses = [comparisons[key]["status"] for key in COMPARISON_KEYS]
    overall = "failed" if "failed" in statuses else "inconclusive" if "inconclusive" in statuses else "pass"
    return overall, comparisons


def _manifest_entry_map(result):
    artifacts = result.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) > MAX_ARCHIVE_FILES:
        raise ValueError("Warp GPU archive manifest is missing or over budget")
    entries, folded, total = {}, set(), 0
    for entry in artifacts:
        if (not isinstance(entry, dict) or set(entry) != {"path", "size_bytes", "sha256"}
                or not isinstance(entry["path"], str) or not entry["path"]
                or len(entry["path"]) > 512 or re.search(r"[\\:\x00-\x1f]", entry["path"])
                or any(not part or part in (".", "..") or part.endswith((".", " "))
                       or re.fullmatch(r"(?:con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\..*)?", part, re.I)
                       for part in entry["path"].split("/"))
                or type(entry["size_bytes"]) is not int or not 0 <= entry["size_bytes"] <= 2**53 - 1
                or not isinstance(entry["sha256"], str) or SHA_RE.fullmatch(entry["sha256"]) is None):
            raise ValueError("Invalid Warp GPU archive manifest entry")
        key = entry["path"].casefold()
        total += entry["size_bytes"]
        if key in folded or total > MAX_ARCHIVE_TOTAL_BYTES:
            raise ValueError("Duplicate or over-budget Warp GPU archive manifest")
        folded.add(key)
        entries[entry["path"]] = (entry["size_bytes"], entry["sha256"])
    return entries


def _verify_folder_manifest(result, folder):
    from lpbf_gpu_pilot_artifacts import read_pilot_artifacts

    root_path = Path(folder).absolute()
    for candidate in [*reversed(root_path.parents), root_path]:
        if candidate.is_symlink() or getattr(candidate, "is_junction", lambda: False)():
            raise ValueError("Warp GPU archive folder must not contain links")
    root = root_path.resolve(strict=True)
    expected = _manifest_entry_map(result)
    actual, folded, total = {}, set(), 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in list(dirs):
            candidate = base / name
            if candidate.is_symlink() or getattr(candidate, "is_junction", lambda: False)():
                raise ValueError("Warp GPU archive folder contains a link")
        for name in files:
            candidate = base / name
            relative = candidate.relative_to(root).as_posix()
            if relative in EXCLUDED_ROOT_FILES:
                continue
            if (candidate.is_symlink() or getattr(candidate, "is_junction", lambda: False)()
                    or not candidate.is_file()):
                raise ValueError("Warp GPU archive folder contains a non-regular file")
            key = relative.casefold()
            if key in folded:
                raise ValueError("Warp GPU archive folder has case-folded duplicate paths")
            folded.add(key)
            stat = candidate.stat()
            total += stat.st_size
            if total > MAX_ARCHIVE_TOTAL_BYTES:
                raise ValueError("Warp GPU archive folder exceeds byte budget")
            digest = hashlib.sha256()
            with candidate.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            actual[relative] = (stat.st_size, digest.hexdigest())
    if actual != expected:
        raise ValueError("Warp GPU archive manifest does not cover the complete job folder")
    descriptor = result.get("gpuFieldArtifacts")
    refs = {}
    states = _dict(descriptor, "field descriptor").get("states")
    for backend in ("cpu", "gpu"):
        state = _dict(_dict(states, "field states").get(backend), f"{backend} field state")
        fields = _dict(state.get("fields"), f"{backend} field map")
        for ref in fields.values():
            ref = _dict(ref, "field reference")
            refs[ref.get("path")] = (ref.get("size_bytes"), ref.get("sha256"))
    if any(expected.get(path) != ref for path, ref in refs.items()):
        raise ValueError("Warp GPU field references do not match the full manifest")
    return read_pilot_artifacts(root, descriptor)


def enforce_gpu_warp_pilot_result(result, artifact_dir=None):
    """Validate Warp v2 identity; optionally verify every byte and recompute parity evidence."""
    result = _dict(result, "result")
    contract = _dict(result.get("gpuRunContract"), "run contract")
    capture = _dict(contract.get("capture"), "capture binding")
    serialized = _dict(contract.get("serializedInputs"), "serialized inputs")
    hashes = _dict(contract.get("hashes"), "hashes")
    descriptor = _dict(result.get("gpuFieldArtifacts"), "field descriptor")
    settings = _dict(result.get("settings"), "settings")
    solver = _dict(result.get("solver"), "solver")
    provenance = _dict(result.get("provenance"), "provenance")
    evidence = _dict(provenance.get("deviceEvidence"), "device evidence")
    material = _dict(result.get("material"), "material")
    if (set(contract) != CONTRACT_KEYS or type(contract.get("schemaVersion")) is not int
            or contract["schemaVersion"] != 2 or contract.get("runKind") != PILOT_JOB_TYPE
            or set(capture) != CAPTURE_KEYS or capture.get("contractStatus") != CONTRACT_STATUS
            or capture.get("engineId") != "warp" or capture.get("modelId") != MODEL_ID
            or set(serialized) != INPUT_KEYS or set(hashes) != HASH_KEYS
            or type(result.get("schemaVersion")) is not int or result.get("schemaVersion") != 1
            or result.get("jobType") != PILOT_JOB_TYPE or result.get("runKind") != PILOT_JOB_TYPE
            or "coreContract" in result or settings.get("executionEngine") != "warp"
            or settings.get("jobType") != PILOT_JOB_TYPE
            or result.get("requestedMode") != "standard" or result.get("effectiveMode") != "gpu-pilot"
            or result.get("validationStatus") != "unvalidated" or result.get("productionReady") is not False
            or result.get("label") != "Unvalidated Warp v2 thermal parity pilot"
            or result.get("confidence") != "low"
            or solver.get("id") != WARP_SOLVER_ID or solver.get("modelId") != MODEL_ID
            or solver.get("dtype") != "float64" or solver.get("sourceIntegrationDevice") != "cpu"
            or solver.get("sourceTimestepLimiterDevice") != "cpu"):
        raise ValueError("Warp v2 pilot identity or contract shape is invalid")
    device = settings.get("backend")
    if (not isinstance(device, str) or re.fullmatch(r"cuda:[0-9]+", device) is None
            or any(capture.get(key) != value for key, value in (("backend", device), ("device", device), ("dtype", "float64")))
            or solver.get("actualBackend") != device or solver.get("thermalEvolutionDevice") != device
            or evidence.get("selected") != device or evidence.get("thermalEvolution") != device
            or evidence.get("sourceIntegration") != "cpu" or evidence.get("sourceTimestepLimiter") != "cpu"
            or evidence.get("engineId") != "warp" or not isinstance(evidence.get("warp"), str)
            or not evidence["warp"].strip() or "torch" in evidence or "cudaRuntime" in evidence
            or not isinstance(evidence.get("name"), str) or not evidence["name"].strip()
            or any(not isinstance(evidence.get(key), str)
                   or re.fullmatch(r"[1-9][0-9]*\.[0-9]+", evidence[key]) is None
                   for key in ("warpCudaToolkitVersion", "cudaDriverVersion"))
            or evidence.get("synchronizedAfterSolve") is not True
            or type(evidence.get("synchronizedAfterSolve")) is not bool
            or evidence.get("synchronizedAfterSolve") is not True
            or not isinstance(evidence.get("computeCapability"), list)
            or len(evidence["computeCapability"]) != 2
            or any(type(value) is not int or value < 0 for value in evidence["computeCapability"])):
        raise ValueError("Warp v2 runtime/device evidence is detached from the result")

    for key in HASH_KEYS:
        if not isinstance(hashes[key], str) or SHA_RE.fullmatch(hashes[key]) is None:
            raise ValueError("Invalid Warp v2 input hash")
    input_values = {}
    expected_values = {
        "requestJson": settings,
        "materialJson": material,
    }
    cpu_input = {key: value for key, value in settings.items()
                 if key not in ("jobType", "executionEngine")}
    cpu_input["backend"] = "reference"
    expected_values["cpuInputJson"] = cpu_input
    expected_values["cpuResolvedSettingsJson"] = cpu_input
    hash_for_input = {"requestJson": "requestHash", "materialJson": "materialHash",
                      "cpuInputJson": "cpuInputHash", "cpuResolvedSettingsJson": "cpuResolvedSettingsHash"}
    for name, expected in expected_values.items():
        value = serialized.get(name)
        input_values[name] = _parse_bound_json(value, expected, hashes.get(hash_for_input[name]), name)
    if (hashes["implementationHash"] != provenance.get("implementationHash")
            or provenance.get("inputHash") != hashes["requestHash"]
            or provenance.get("materialVersion") != material.get("version")
            or not isinstance(provenance.get("createdAt"), str)
            or not math.isfinite(_parse_created_at(provenance["createdAt"]))):
        raise ValueError("Warp v2 provenance is detached from the captured inputs")
    resolved = input_values["cpuResolvedSettingsJson"]
    resolved_material = input_values["materialJson"]
    revision = resolved_material.get("materialRevisionSha256") if isinstance(resolved_material, dict) else None
    if (not isinstance(revision, str) or SHA_RE.fullmatch(revision) is None
            or hashlib.sha256(_encoded({key: value for key, value in resolved_material.items()
                                        if key != "materialRevisionSha256"})).hexdigest() != revision):
        raise ValueError("Warp v2 material revision hash mismatch")
    pilot = _dict(result.get("gpuPilot"), "parity summary")
    if (pilot.get("experimentalValidation") is not False
            or pilot.get("scope") != "same-model CPU/Warp numerical parity only"):
        raise ValueError("Warp v2 parity scope is invalid")
    cpu = _dict(pilot.get("cpu"), "CPU summary")
    core = _dict(cpu.get("coreContract"), "nested CPU core contract")
    cpu_solver = _dict(cpu.get("solver"), "CPU solver")
    cpu_material = _dict(cpu.get("material"), "CPU material summary")
    for key in ("name", "materialId", "materialRevisionSha256", "version"):
        if cpu_material.get(key) != material.get(key):
            raise ValueError("Warp v2 nested CPU material mismatch")
    if (cpu_solver.get("id") != core.get("solverId")
            or not _strict_json_equal(cpu.get("resolvedSettings"), resolved)):
        raise ValueError("Warp v2 CPU reference core is not bound to the captured reference input")
    try:
        expected_core = build_core_contract(resolved, resolved_material, cpu_solver.get("id"), "standard")
    except (TypeError, ValueError, KeyError, OverflowError) as error:
        raise ValueError("Warp v2 CPU reference core cannot be reconstructed from its snapshot") from error
    if not _strict_json_equal(core, expected_core):
        raise ValueError("Warp v2 CPU reference core is not bound to the captured reference input")

    if (not isinstance(result.get("metrics"), dict)
            or _positive_finite(result["metrics"].get("peakTemperature_K"), "peak temperature") is None
            or any(_nonnegative_finite(result["metrics"].get(key), key) is None
                   for key in ("width_um", "depth_um", "length_um", "volume_um3"))):
        raise ValueError("Invalid Warp v2 result metrics")
    _enforce_gpu_archive_field_metadata(result, descriptor)

    if artifact_dir is not None:
        decoded = _verify_folder_manifest(result, artifact_dir)
        from lpbf_gpu_pilot_numerics import validate_pilot_numerics
        validate_pilot_numerics(result, decoded, PARITY_TARGETS)
    return result


def run_queued_warp_pilot(raw, artifact_dir):
    """Run one CPU reference and one Warp candidate, then archive their actual full states."""
    if artifact_dir is None:
        raise ValueError("Warp v2 pilot requires a job folder for its bound field evidence")
    request, material = validate_warp_pilot_request(raw)
    device = request["backend"]
    reference = {key: value for key, value in request.items()
                 if key not in ("jobType", "executionEngine")}
    reference["backend"] = "reference"

    from lpbf_gpu_thermal import implementation_fingerprint
    from lpbf_gpu_thermal_warp import run_warp
    from lpbf_gpu_pilot_artifacts import write_pilot_artifacts
    cpu, frame, cpu_temperature, cpu_coordinates, cpu_state = _run_cpu_with_final(
        reference, include_final_state=True)
    gpu, gpu_field, gpu_state = run_warp(reference, device, capture_final=True, capture_pilot_state=True)
    if (cpu["coreContract"]["modelId"] != gpu["solver"]["modelId"]
            or cpu["material"]["materialRevisionSha256"] != gpu["material"]["materialRevisionSha256"]):
        raise ValueError("CPU/Warp model or material revision mismatch")
    status, comparisons = _comparison_report(cpu, gpu, frame, cpu_temperature, cpu_coordinates, gpu_field)
    warp_candidate = dict(gpu["warpCandidate"])
    warp_candidate["status"] = status
    cpu_summary = {"solver": cpu["solver"], "coreContract": cpu["coreContract"],
                   "material": {key: cpu["material"][key] for key in
                               ("name", "materialId", "materialRevisionSha256", "version")},
                   "discretization": cpu["discretization"], "resolvedSettings": cpu["settings"]}
    parity = {"status": status, "scope": "same-model CPU/Warp numerical parity only",
              "experimentalValidation": False, "targets": dict(PARITY_TARGETS),
              "cpu": cpu_summary, "comparisons": comparisons}

    device_evidence = _warp_device_evidence(device)
    result = {
        "schemaVersion": 1, "jobType": PILOT_JOB_TYPE, "runKind": PILOT_JOB_TYPE,
        "requestedMode": "standard", "effectiveMode": "gpu-pilot",
        "solver": gpu["solver"], "settings": request, "material": material,
        "metrics": gpu["metrics"], "energyBalance": gpu["energyBalance"],
        "discretization": gpu["discretization"], "peakExtraction": gpu["peakExtraction"],
        "warpCandidate": warp_candidate, "gpuPilot": parity,
        "validationStatus": "unvalidated", "productionReady": False,
        "label": "Unvalidated Warp v2 thermal parity pilot", "confidence": "low", "artifacts": [],
        "provenance": {
            "inputHash": _digest_text(_python_json(request)),
            "implementationHash": implementation_fingerprint(),
            "materialVersion": material["version"],
            "createdAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "deviceEvidence": device_evidence,
        },
    }
    descriptor = write_pilot_artifacts(artifact_dir, cpu_state, gpu_state)
    request_json = _python_json(request)
    material_json = _python_json(material)
    cpu_input_json = _python_json(reference)
    cpu_resolved_settings_json = _python_json(cpu["settings"])
    result["gpuFieldArtifacts"] = descriptor
    result["gpuRunContract"] = {
        "schemaVersion": 2, "runKind": PILOT_JOB_TYPE,
        "capture": {"contractStatus": CONTRACT_STATUS, "modelId": gpu["solver"]["modelId"],
                    "backend": device, "device": device, "dtype": gpu["solver"]["dtype"],
                    "engineId": "warp"},
        "serializedInputs": {"requestJson": request_json, "materialJson": material_json,
                             "cpuInputJson": cpu_input_json,
                             "cpuResolvedSettingsJson": cpu_resolved_settings_json},
        "hashes": {"requestHash": _digest_text(request_json), "materialHash": _digest_text(material_json),
                   "cpuInputHash": _digest_text(cpu_input_json),
                   "cpuResolvedSettingsHash": _digest_text(cpu_resolved_settings_json),
                   "implementationHash": result["provenance"]["implementationHash"]},
    }
    from lpbf_evidence import write_artifacts
    write_artifacts(result, artifact_dir)
    enforce_gpu_warp_pilot_result(result, artifact_dir=artifact_dir)
    json.dumps(result, allow_nan=False)
    return result
