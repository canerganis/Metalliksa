"""CUDA thermal evolution for the CPU reference LPBF enthalpy-conduction model.

The common cell-integrated moving source defaults to the host reference helper;
an opt-in CUDA prototype evaluates the same adaptive Gaussian cell integrals and timestep cap.
Conduction, enthalpy update, constitutive interpolation and melt state run on
CUDA in float64. Queue integration uses a separate, explicit pilot job type.
"""

import math
import re
import hashlib
import json
import datetime

import numpy as np

from lpbf_core_physics import (calculate_mesh_domain, scan_segments, thermal_si_inputs,
                               source_gauss_rule, source_time_quadrature,
                               SOURCE_QUADRATURE_MAX_ORDER, SOURCE_QUADRATURE_RELATIVE_TOLERANCE)
from lpbf_heat_source import require_source_capture, source_limited_step
from lpbf_peak import PeakMeltTracker
from lpbf_simulation import (MINIMUM_SOURCE_CAPTURE_FRACTION, validate, IMPLEMENTATION_FINGERPRINT_SCHEMA,
                             implementation_fingerprint,
                             run as cpu_run)
from lpbf_material_registry import enthalpy_table, property_at


MODEL_ID = "stationary-enthalpy-conduction-v1"
GPU_SOLVER_ID = "enthalpy-fv-6-cuda-pilot-1"
MAX_CELLS = 100000
MAX_STEPS = 20000
# Frozen before any GPU parity result: master plan §11 integral target <=1%;
# W/D phase boundaries are separately limited to one actual grid cell.
PARITY_TARGETS = {"integralRelativeMax": .01, "widthDepthAbsoluteCellsMax": 1.0,
                  "fieldRiseL2RelativeMax": .01, "fieldRiseMaxRelativeMax": .01,
                  "peakMeltVolumeRelativeMax": .01,
                  "source": "docs/DIGITAL_TWIN_MASTER_PLAN_2026-09-21.md#11"}
PILOT_JOB_TYPE = "gpu-thermal-pilot"
MAX_ARCHIVE_INPUT_JSON_BYTES = 1024 * 1024
MAX_ARCHIVE_FILES = 10_000
MAX_ARCHIVE_TOTAL_BYTES = 256 * 1024 * 1024


def _python_json(value):
    return json.dumps(value, sort_keys=True, allow_nan=False)


def _strict_json_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate key in serialized GPU archive input")
        value[key] = item
    return value


def _reject_json_constant(value):
    raise ValueError(f"Invalid JSON constant in GPU archive input: {value}")


def _parse_bound_json(value, expected, digest, name):
    if not isinstance(value, str) or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError(f"Invalid serialized {name} binding")
    encoded = value.encode("utf-8")
    if len(encoded) > MAX_ARCHIVE_INPUT_JSON_BYTES:
        raise ValueError(f"Serialized {name} exceeds GPU archive input limit")
    try:
        parsed = json.loads(value, object_pairs_hook=_strict_json_object, parse_constant=_reject_json_constant)
        canonical = _python_json(parsed)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid serialized {name} JSON") from error
    if ((expected is not None and canonical != _python_json(expected))
            or hashlib.sha256(encoded).hexdigest() != digest):
        raise ValueError(f"Serialized {name} binding changed")
    return parsed


def _enforce_gpu_archive_contract(result, verify_folder=None):
    provenance = result.get("provenance")
    evidence = provenance.get("deviceEvidence") if isinstance(provenance, dict) else None
    if (type(result.get("schemaVersion")) is not int or result["schemaVersion"] != 1
            or result.get("requestedMode") != "standard"
            or result.get("label") != "Unvalidated CUDA thermal parity pilot"
            or result.get("confidence") != "low"
            or not isinstance(provenance, dict) or not isinstance(evidence, dict)
            or not isinstance(result.get("metrics"), dict)
            or not isinstance(result.get("discretization"), dict)):
        raise ValueError("Invalid archived CUDA pilot result envelope")
    metric_values = result["metrics"]
    if (not _finite_nonnegative(metric_values.get("peakTemperature_K"))
            or metric_values["peakTemperature_K"] <= 0
            or any(not _finite_nonnegative(metric_values.get(key))
                   for key in ("width_um", "depth_um", "length_um", "volume_um3"))):
        raise ValueError("Invalid archived CUDA pilot metrics")
    contract = result.get("gpuRunContract")
    descriptor = result.get("gpuFieldArtifacts")
    if (not isinstance(contract, dict) or set(contract) != {
            "schemaVersion", "runKind", "capture", "serializedInputs", "hashes"}
            or type(contract["schemaVersion"]) is not int or contract["schemaVersion"] != 1
            or contract["runKind"] != PILOT_JOB_TYPE):
        raise ValueError("Unsupported GPU archive run contract")
    capture = contract["capture"]
    hashes = contract["hashes"]
    serialized = contract["serializedInputs"]
    if (not isinstance(capture, dict) or set(capture) != {
            "contractStatus", "modelId", "backend", "device", "dtype"}
            or not isinstance(hashes, dict) or set(hashes) != {
                "requestHash", "materialHash", "cpuInputHash", "cpuResolvedSettingsHash", "implementationHash"}
            or not isinstance(serialized, dict) or set(serialized) != {
                "requestJson", "materialJson", "cpuInputJson", "cpuResolvedSettingsJson"}):
        raise ValueError("Invalid GPU archive contract fields")
    if (capture["contractStatus"] != "gpu-pilot-v1-bound"
            or capture["modelId"] != result.get("solver", {}).get("modelId")
            or capture["backend"] != result.get("settings", {}).get("backend")
            or capture["device"] != result.get("provenance", {}).get("deviceEvidence", {}).get("selected")
            or capture["dtype"] != result.get("solver", {}).get("dtype")
            or "coreContract" in result):
        raise ValueError("GPU archive metadata binding changed")
    if (capture["dtype"] != "float64" or result.get("solver", {}).get("dtype") != "float64"
            or not isinstance(provenance.get("inputHash"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", provenance["inputHash"])
            or not isinstance(provenance.get("implementationHash"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", provenance["implementationHash"])
            or provenance.get("materialVersion") != result.get("material", {}).get("version")
            or not isinstance(provenance.get("createdAt"), str)
            or not math.isfinite(_parse_created_at(provenance["createdAt"]))):
        raise ValueError("Invalid archived CUDA pilot provenance")
    capability = evidence.get("computeCapability")
    if (not isinstance(evidence.get("name"), str) or not evidence["name"].strip()
            or not isinstance(evidence.get("torch"), str) or not evidence["torch"].strip()
            or not isinstance(evidence.get("cudaRuntime"), str) or not evidence["cudaRuntime"].strip()
            or not isinstance(capability, list) or len(capability) != 2
            or any(type(value) is not int or value < 0 for value in capability)):
        raise ValueError("Invalid archived CUDA device evidence")
    settings = result.get("settings")
    material = result.get("material")
    if not isinstance(settings, dict) or not isinstance(material, dict):
        raise ValueError("GPU archive inputs are missing")
    cpu_input = {key: value for key, value in settings.items() if key != "jobType"}
    cpu_input["backend"] = "reference"
    _parse_bound_json(serialized["requestJson"], settings, hashes["requestHash"], "request")
    _parse_bound_json(serialized["materialJson"], material, hashes["materialHash"], "material")
    parsed_cpu_input = _parse_bound_json(serialized["cpuInputJson"], cpu_input, hashes["cpuInputHash"], "CPU input")
    resolved_settings = _parse_bound_json(
        serialized["cpuResolvedSettingsJson"], None, hashes["cpuResolvedSettingsHash"],
        "resolved CPU settings")
    if not isinstance(resolved_settings, dict) or resolved_settings.get("backend") != "reference":
        raise ValueError("Invalid serialized resolved CPU settings")
    if _python_json(parsed_cpu_input) != _python_json(resolved_settings):
        raise ValueError("Resolved CPU settings do not match archived CPU input")
    cpu = result.get("gpuPilot", {}).get("cpu", {})
    core = cpu.get("coreContract") if isinstance(cpu, dict) else None
    cpu_solver = cpu.get("solver", {}) if isinstance(cpu, dict) else {}
    if not isinstance(core, dict) or not isinstance(cpu_solver, dict):
        raise ValueError("GPU archive CPU core binding is missing")
    from lpbf_core_contract import build_core_contract
    expected_core = build_core_contract(resolved_settings, material, cpu_solver.get("id"), "standard")
    if _python_json(core) != _python_json(expected_core):
        raise ValueError("GPU archive CPU core contract binding changed")
    implementation_hash = result.get("provenance", {}).get("implementationHash")
    if (not isinstance(implementation_hash, str) or not re.fullmatch(r"[a-f0-9]{64}", implementation_hash)
            or hashes["implementationHash"] != implementation_hash
            or hashes["requestHash"] != result.get("provenance", {}).get("inputHash")):
        raise ValueError("GPU archive provenance binding changed")
    from lpbf_gpu_pilot_artifacts import pilot_artifact_refs, read_pilot_artifacts
    refs = pilot_artifact_refs(descriptor)
    manifest = result.get("artifacts")
    if not isinstance(manifest, list):
        raise ValueError("GPU archive manifest is missing")
    manifest_refs = []
    seen_paths = set()
    folded_paths = set()
    total_bytes = 0
    if len(manifest) > MAX_ARCHIVE_FILES:
        raise ValueError("GPU archive manifest exceeds file count limit")
    for entry in manifest:
        if (not isinstance(entry, dict) or set(entry) != {"path", "size_bytes", "sha256"}
                or not isinstance(entry["path"], str) or not entry["path"] or entry["path"] in seen_paths
                or entry["path"].lower() in folded_paths
                or type(entry["size_bytes"]) is not int or not 0 <= entry["size_bytes"] <= 2**53-1
                or not isinstance(entry["sha256"], str)
                or not re.fullmatch(r"[a-f0-9]{64}", entry["sha256"])):
            raise ValueError("Invalid GPU archive artifact manifest")
        from pathlib import Path
        relative = Path(entry["path"])
        if (relative.is_absolute() or ".." in relative.parts
                or relative.as_posix() != entry["path"] or "\\" in entry["path"]
                or ":" in entry["path"] or any(ord(char) < 32 for char in entry["path"])):
            raise ValueError("Invalid GPU archive artifact path")
        seen_paths.add(entry["path"])
        folded_paths.add(entry["path"].lower())
        total_bytes += entry["size_bytes"]
        if total_bytes > MAX_ARCHIVE_TOTAL_BYTES:
            raise ValueError("GPU archive manifest exceeds total byte limit")
        manifest_refs.append(entry)
    if any(ref not in manifest_refs for ref in refs):
        raise ValueError("GPU field artifacts are not bound by the folder manifest")
    _enforce_gpu_archive_field_metadata(result, descriptor)
    if verify_folder is not None:
        from pathlib import Path
        root_path = Path(verify_folder).absolute()
        if root_path.is_symlink() or getattr(root_path, "is_junction", lambda: False)():
            raise ValueError("GPU archive folder must be an ordinary directory")
        root = root_path.resolve(strict=True)
        actual_paths = set()
        actual_folded = set()
        folder_bytes = 0
        for candidate in root.rglob("*"):
            if candidate.is_symlink() or getattr(candidate, "is_junction", lambda: False)():
                raise ValueError("GPU archive folder contains a linked path")
            if candidate.is_dir():
                continue
            if not candidate.is_file():
                raise ValueError("GPU archive folder contains a non-file entry")
            relative_name = candidate.relative_to(root).as_posix()
            if relative_name in ("result.json", "result.tmp", "progress.log"):
                continue
            actual_paths.add(relative_name)
            actual_folded.add(relative_name.lower())
            folder_bytes += candidate.stat().st_size
            if len(actual_paths) > MAX_ARCHIVE_FILES:
                raise ValueError("GPU archive folder exceeds file count limit")
            if folder_bytes > MAX_ARCHIVE_TOTAL_BYTES:
                raise ValueError("GPU archive folder exceeds total byte limit")
        if actual_paths != seen_paths or len(actual_folded) != len(actual_paths):
            raise ValueError("GPU archive folder manifest is incomplete")
        for entry in manifest:
            relative = Path(entry["path"])
            path = root / relative
            current = root
            for part in relative.parts:
                current = current / part
                if current.is_symlink():
                    raise ValueError("GPU archive folder manifest path or size changed")
            resolved = path.resolve(strict=True)
            if (root not in resolved.parents or not resolved.is_file()
                    or resolved.stat().st_size != entry["size_bytes"]):
                raise ValueError("GPU archive folder manifest path or size changed")
            file_digest = hashlib.sha256()
            with resolved.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    file_digest.update(chunk)
            digest = file_digest.hexdigest()
            if digest != entry["sha256"]:
                raise ValueError("GPU archive folder manifest bytes changed")
        decoded_states = read_pilot_artifacts(root, descriptor)
        from lpbf_gpu_pilot_numerics import validate_pilot_numerics
        validate_pilot_numerics(result, decoded_states, PARITY_TARGETS)


def _enforce_gpu_archive_field_metadata(result, descriptor):
    states = descriptor["states"]
    pilot = result["gpuPilot"]
    cpu = pilot.get("cpu")
    cpu_disc = cpu.get("discretization") if isinstance(cpu, dict) else None
    gpu_disc = result.get("discretization")
    comparisons = pilot.get("comparisons")
    cpu_sampling = comparisons.get("finalSampling") if isinstance(comparisons, dict) else None
    if not isinstance(cpu_disc, dict) or not isinstance(gpu_disc, dict) or not isinstance(cpu_sampling, dict):
        raise ValueError("GPU archive field metadata is incomplete")
    for name, discretization in (("CPU", cpu_disc), ("GPU", gpu_disc)):
        if (type(discretization.get("cells")) is not int or discretization["cells"] <= 0
                or type(discretization.get("steps")) is not int or discretization["steps"] <= 0
                or not _finite_positive(discretization.get("mesh_m"))):
            raise ValueError(f"GPU archive {name} discretization metadata is invalid")
        try:
            cell_volume = discretization["mesh_m"] ** 3
        except OverflowError as error:
            raise ValueError(f"GPU archive {name} cell volume is invalid") from error
        if not _finite_positive(cell_volume):
            raise ValueError(f"GPU archive {name} cell volume is invalid")
    for name in ("cpuFinalTime_s", "cpuFrameTime_s", "gpuFinalTime_s"):
        if not _finite_positive(cpu_sampling.get(name)):
            raise ValueError("GPU archive final sampling metadata is invalid")
    preheat = result.get("settings", {}).get("preheat_C")
    if type(preheat) not in (int, float) or not math.isfinite(preheat):
        raise ValueError("GPU archive initial temperature metadata is invalid")
    expectations = {
        "cpu": (cpu_disc["cells"], cpu_disc["steps"],
                cpu_sampling["cpuFinalTime_s"], cpu_sampling["cpuFrameTime_s"],
                preheat + 273.15,
                cpu_disc["mesh_m"]),
        "gpu": (gpu_disc["cells"], gpu_disc["steps"],
                cpu_sampling["gpuFinalTime_s"], cpu_sampling["gpuFinalTime_s"],
                preheat + 273.15,
                gpu_disc["mesh_m"]),
    }
    for backend, (cells, steps, final_time, frame_time, initial_temperature, mesh_m) in expectations.items():
        state = states[backend]
        if (state["cells"] != cells or state["steps"] != steps
                or not math.isclose(state["time_s"], final_time, rel_tol=1e-12, abs_tol=1e-14)
                or not math.isclose(state["time_s"], frame_time, rel_tol=1e-12, abs_tol=1e-14)
                or not math.isclose(state["initial_temperature_K"], initial_temperature,
                                    rel_tol=1e-12, abs_tol=1e-12)
                or not math.isclose(state["cell_volume_m3"], mesh_m ** 3, rel_tol=1e-12, abs_tol=1e-30)):
            raise ValueError(f"GPU archive {backend} state metadata conflicts with result")


def require_cuda(device):
    if not isinstance(device, str) or not re.fullmatch(r"cuda:[0-9]+", device):
        raise ValueError("Explicit cuda:N device required; no CPU fallback")
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch CUDA runtime unavailable") from exc
    if not torch.cuda.is_available() or int(device[5:]) >= torch.cuda.device_count():
        raise RuntimeError(f"CUDA device {device} unavailable; no CPU fallback")
    return torch, torch.device(device)


def _model_id_for_settings(settings):
    return ("stationary-enthalpy-conduction-layer-conforming-v1"
            if settings.get("powderGridPolicy") == "layer-conforming" else MODEL_ID)


def validate_pilot_request(raw):
    """Resolve an explicit CUDA queue request to the CPU reference physics input."""
    if not isinstance(raw, dict) or raw.get("jobType") != PILOT_JOB_TYPE:
        raise ValueError("Explicit gpu-thermal-pilot jobType required")
    device = raw.get("backend")
    # Check before accepting; execution checks again if the device disappears.
    require_cuda(device)
    reference = {k: v for k, v in raw.items() if k != "jobType"}
    reference["backend"] = "reference"
    p, material = validate(reference)
    if (p["mode"] != "standard" or p["study"] != "none" or p["tracks"] != 1
            or p["layers"] != 1 or p["surfaceMode"] != "powder-layer"
            or p.get("measurements")):
        raise ValueError("CUDA pilot requires one powder-layer track, one layer, standard mode, no study or measurements")
    domain = calculate_mesh_domain(p)
    if domain["nxy"]**2 * domain["nz"] > MAX_CELLS:
        raise ValueError("CUDA pilot cell budget exceeded")
    return {**p, "backend": device, "jobType": PILOT_JOB_TYPE}, material


def _interp(torch, values, xp, fp):
    shape = values.shape
    flat = values.reshape(-1)
    index = torch.searchsorted(xp, flat).clamp(1, len(xp)-1)
    lo, hi = index-1, index
    out = fp[lo] + (flat-xp[lo])*(fp[hi]-fp[lo])/(xp[hi]-xp[lo])
    return torch.where(flat <= xp[0], fp[0], torch.where(flat >= xp[-1], fp[-1], out)).reshape(shape)


def _conduction(torch, temperature, conductivity, active, dx):
    rate = torch.zeros_like(temperature)
    diagonal = torch.zeros_like(temperature)
    for axis in range(3):
        left, right = [slice(None)]*3, [slice(None)]*3
        left[axis], right[axis] = slice(None, -1), slice(1, None)
        left, right = tuple(left), tuple(right)
        k_face = 2*conductivity[left]*conductivity[right]/(conductivity[left]+conductivity[right])
        face = k_face/(dx*dx)*(active[left]&active[right])
        flux = face*(temperature[right]-temperature[left])
        rate[left] += flux
        rate[right] -= flux
        diagonal[left] += face
        diagonal[right] += face
    return rate, diagonal


def _gaussian_interval_torch(torch, lower, upper, center, radius):
    """Integrate the CPU reference's normalized one-dimensional Gaussian cells."""
    scale = math.sqrt(2.0) / radius
    a = (lower - center) * scale
    b = (upper - center) * scale
    positive_tail = 0.5 * (torch.special.erfc(a) - torch.special.erfc(b))
    negative_tail = 0.5 * (torch.special.erfc(-b) - torch.special.erfc(-a))
    central = 0.5 * (torch.special.erf(b) - torch.special.erf(a))
    value = torch.where(a >= 0.0, positive_tail,
                        torch.where(b <= 0.0, negative_tail, central))
    return torch.where(b > a, torch.clamp(value, min=0.0), torch.zeros_like(value))


def _integrated_source_torch(torch, axis, z, dx, segment, time, dt, surface,
                             radius, penetration, power, defer_capture_check=False):
    """CUDA version of the shared adaptive, normal-incidence Gaussian source."""
    source = torch.zeros((axis.numel(), axis.numel(), z.numel()),
                         dtype=axis.dtype, device=axis.device)
    if segment is None:
        capture = torch.ones((), dtype=axis.dtype, device=axis.device) if defer_capture_check else 1.0
        return source, capture
    if (dt <= 0.0 or time < segment["start_s"] - 1e-13
            or time + dt > segment["end_s"] + 1e-13):
        raise ValueError("Source interval must remain inside one laser-on segment")

    x_lower = axis - dx / 2.0
    x_upper = axis + dx / 2.0
    z_lower = z - dx / 2.0
    z_upper = torch.minimum(z + dx / 2.0,
                            torch.as_tensor(surface, dtype=z.dtype, device=z.device))
    depth_lower = _gaussian_interval_torch(
        torch, z_lower, z_upper, surface, penetration)
    depth_lower = torch.where(z < surface, depth_lower, torch.zeros_like(depth_lower))

    start = np.asarray(segment["start"], dtype=np.float64)
    stop = np.asarray(segment["end"], dtype=np.float64)
    duration = segment["end_s"] - segment["start_s"]
    order, refine = source_time_quadrature(segment, dt, radius)
    capture = torch.ones((), dtype=axis.dtype, device=axis.device)
    previous = None
    while True:
        source = torch.zeros_like(source)
        rule_nodes, rule_weights = source_gauss_rule(order)
        # Bound the temporary 4D allocation while sharing the CPU quadrature rule.
        for offset in range(0, order, 8):
            nodes = np.asarray(rule_nodes[offset:offset+8], dtype=np.float64)
            temporal_weights = torch.as_tensor(rule_weights[offset:offset+8],
                                               dtype=axis.dtype, device=axis.device)
            fractions = np.clip((time + nodes * dt - segment["start_s"]) / duration, 0.0, 1.0)
            positions = torch.as_tensor(start[None, :] + fractions[:, None] * (stop - start)[None, :],
                                        dtype=axis.dtype, device=axis.device)
            x_mass = _gaussian_interval_torch(
                torch, x_lower[None, :], x_upper[None, :], positions[:, 0, None], radius)
            y_mass = _gaussian_interval_torch(
                torch, x_lower[None, :], x_upper[None, :], positions[:, 1, None], radius)
            weights = (x_mass[:, :, None, None] * y_mass[:, None, :, None]
                       * depth_lower[None, None, None, :])
            totals = weights.sum(dim=(1, 2, 3))
            captures = torch.clamp(totals * 2.0, max=1.0)
            safe_totals = torch.clamp(totals, min=torch.finfo(totals.dtype).tiny)
            scales = temporal_weights * power / (dx ** 3) / safe_totals
            source = source + (weights * scales[:, None, None, None]).sum(dim=0)
            capture = torch.minimum(capture, torch.min(captures))
        if not refine:
            break
        if previous is not None:
            difference = torch.linalg.vector_norm(source-previous)
            scale = torch.linalg.vector_norm(source)
            if bool((difference <= SOURCE_QUADRATURE_RELATIVE_TOLERANCE*scale).item()):
                break
        if 2*order > SOURCE_QUADRATURE_MAX_ORDER:
            raise ValueError("Moving source quadrature did not converge; shorten the source interval")
        previous = source
        order *= 2
    if defer_capture_check:
        return source, capture
    capture_value = float(capture.item())
    require_source_capture(capture_value, MINIMUM_SOURCE_CAPTURE_FRACTION)
    return source, capture_value


def _source_limited_step_torch(torch, axis, z, dx, segment, time, dt, surface,
                               radius, penetration, power, passive_rate, capacity):
    """CUDA counterpart to source_limited_step with its same 25 K cap/retries."""
    for retries in range(12):
        source, capture = _integrated_source_torch(
            torch, axis, z, dx, segment, time, dt, surface, radius, penetration, power,
            defer_capture_check=True)
        rate = passive_rate + source
        allowed_tensor = torch.min(
            25.0 * capacity / torch.clamp(torch.abs(rate), min=1e-30))
        capture, allowed = torch.stack((capture, allowed_tensor)).tolist()
        require_source_capture(capture, MINIMUM_SOURCE_CAPTURE_FRACTION)
        if allowed >= dt * (1.0 - 1e-12):
            return dt, source, rate, capture, retries
        dt = 0.95 * allowed
    raise ValueError("Moving-source timestep limit failed to converge")


def run_gpu(raw, device="cuda:0", capture_final=False, use_cuda_source=False):
    """Run a bounded single-track/layer reference-physics case on explicit CUDA."""
    torch, cuda = require_cuda(device)
    if type(use_cuda_source) is not bool:
        raise ValueError("use_cuda_source must be a boolean")
    p, material = validate(raw)
    if (p["mode"] != "standard" or p["backend"] != "reference" or p["study"] != "none"
            or p["tracks"] != 1 or p["layers"] != 1):
        raise ValueError("CUDA pilot supports one-track, one-layer standard/reference cases only")
    domain = calculate_mesh_domain(p)
    radius, span, nxy, nz, dx, substrate = (domain[k] for k in
        ("radius", "span", "nxy", "nz", "dx", "substrate_depth"))
    model_id = _model_id_for_settings(p)
    if nxy*nxy*nz > MAX_CELLS:
        raise ValueError("CUDA pilot cell budget exceeded")
    axis = (np.arange(nxy)+.5)*dx-span/2
    z = (np.arange(nz)+.5)*dx-substrate
    axis_cuda = torch.as_tensor(axis, dtype=torch.float64, device=cuda)
    z_cuda = torch.as_tensor(z, dtype=torch.float64, device=cuda)
    layer_m = p["layer_um"]*1e-6
    if not np.any(z < 0) or not np.any((z >= 0)&(z < layer_m)):
        raise ValueError("Mesh cannot resolve substrate and powder layer")
    _, _, zz = np.meshgrid(axis, axis, z, indexing="ij")
    # PeakMeltTracker receives exactly the CPU reference's C-order cell coordinates.
    xyz = np.stack(np.meshgrid(axis, axis, z, indexing="ij"), axis=-1).reshape(-1, 3)
    tracker = PeakMeltTracker(xyz, dx, material)
    ti = thermal_si_inputs(p, material)
    t0 = ti["preheat_K"]
    rho0 = float(property_at(material, t0, 1))
    rho = torch.as_tensor(rho0*np.where(zz > 0, p["packingFraction"], 1.), dtype=torch.float64, device=cuda)
    active = torch.as_tensor(zz < layer_m, device=cuda)
    powder = torch.as_tensor(zz > 0, device=cuda)
    temperature = torch.full((nxy, nxy, nz), t0, dtype=torch.float64, device=cuda)
    enthalpy = torch.zeros_like(temperature)
    ever = torch.zeros_like(active)
    table = torch.as_tensor(material["table"], dtype=torch.float64, device=cuda)
    table_t = table[:, 0].contiguous()
    table_k = table[:, 2].contiguous()
    table_cp = table[:, 3].contiguous()
    tt_np, hh_np = enthalpy_table(material)
    tt = torch.as_tensor(tt_np, dtype=torch.float64, device=cuda)
    hh = torch.as_tensor(hh_np, dtype=torch.float64, device=cuda)
    h0 = float(np.interp(t0, tt_np, hh_np))
    h_boil = float(np.interp(material["boiling_K"], tt_np, hh_np))
    cp_floor = min(row[3] for row in material["table"])
    segments, end = scan_segments(p)
    top_index = int(np.flatnonzero(z < layer_m)[-1])
    energy_in = energy_out = 0.
    peak = t0
    time = 0.
    step = 0
    accepted_dt_s = [] if capture_final else None
    min_dt = p["maxDt_s"]
    max_dt = 0.
    while time < end:
        if step >= MAX_STEPS:
            raise ValueError("CUDA pilot timestep budget exceeded")
        segment = next((s for s in segments if s["start_s"] <= time+1e-14 and time < s["end_s"]-1e-14), None)
        k = _interp(torch, temperature, table_t, table_k) * torch.where(
            powder & ~ever, p["powderConductivityRatio"], 1.)
        cp = _interp(torch, temperature, table_t, table_cp)
        dt = min(p["maxDt_s"], .12*dx*dx/torch.max(k/(rho*cp)).item(),
                 radius/(4*ti["speed_m_s"]), end-time)
        events = [s[v]-time for s in segments for v in ("start_s", "end_s") if s[v] > time+1e-14]
        if events:
            dt = min(dt, min(events))
        rate, diagonal = _conduction(torch, temperature, k, active, dx)
        bottom = 2*k[:, :, 0]*(temperature[:, :, 0]-t0)/dx**2
        rate[:, :, 0] -= bottom
        top = temperature[:, :, top_index]
        surface_loss = (p["convection_W_m2K"]*(top-t0)
            + material["emissivity"]*5.670374419e-8*(top**4-t0**4))/dx
        rate[:, :, top_index] -= surface_loss
        diagonal[:, :, 0] += 2*k[:, :, 0]/dx**2
        diagonal[:, :, top_index] += (p["convection_W_m2K"]
            + material["emissivity"]*5.670374419e-8*(top+t0)*(top**2+t0**2))/dx
        dt = min(dt, torch.min(.9*rho*cp_floor/torch.clamp(diagonal, min=1e-30)).item())
        if use_cuda_source:
            dt, source, rate, capture, _ = _source_limited_step_torch(
                torch, axis_cuda, z_cuda, dx, segment, time, dt, layer_m,
                radius, layer_m, ti["absorbed_power_W"], rate, rho * cp)
        else:
            dt, source_np, _, capture, _ = source_limited_step(
                axis, z, dx, segment, time, dt, layer_m, radius, layer_m,
                ti["absorbed_power_W"], rate.cpu().numpy(), (rho*cp).cpu().numpy())
            require_source_capture(capture, MINIMUM_SOURCE_CAPTURE_FRACTION)
            source = torch.as_tensor(source_np, dtype=torch.float64, device=cuda)
            rate += source
        enthalpy += dt*rate
        specific_h = enthalpy/rho+h0
        if (not torch.isfinite(specific_h).all().item() or torch.min(specific_h).item() < hh_np[0]-1e-8
                or torch.max(specific_h).item() >= h_boil):
            raise ValueError("Thermal model validity exceeded (boiling or nonphysical enthalpy)")
        temperature = _interp(torch, specific_h, hh, tt)
        if accepted_dt_s is not None:
            accepted_dt_s.append(float(dt))
        time += dt
        roundoff = min(1e-14, 2 * math.ulp(end) * (step + 1))
        if end - time <= roundoff:
            time = end
        step += 1
        min_dt = min(min_dt, dt)
        max_dt = max(max_dt, dt)
        energy_in += source.sum().item()*dx**3*dt
        energy_out += (bottom.sum().item()+surface_loss.sum().item())*dx**3*dt
        ever |= (temperature >= material["liquidus_K"]) & active
        peak = max(peak, torch.max(temperature).item())
        melt_count = torch.count_nonzero((temperature >= material["liquidus_K"]) & active).item()
        if melt_count > tracker.count:
            tracker.observe(temperature.cpu().numpy(), layer_m, p["scanAngle_deg"], time, step,
                            sampled=True)
    stored = enthalpy.sum().item()*dx**3
    closure = abs(energy_in-energy_out-stored)/max(energy_in, 1e-12)
    if closure > .01:
        raise ValueError(f"CUDA energy balance failed: {closure:.3%}")
    metrics, extraction = tracker.finish(None, step)
    metrics["peakTemperature_K"] = peak
    result = {"solver": {"id": GPU_SOLVER_ID, "modelId": model_id,
                       "actualBackend": device, "thermalEvolutionDevice": device,
                       "sourceIntegrationDevice": device if use_cuda_source else "cpu",
                       "sourceTimestepLimiterDevice": device if use_cuda_source else "cpu",
                       "dtype": "float64"},
            "material": {k: material[k] for k in ("name", "materialId", "materialRevisionSha256", "version")},
            "settings": p, "metrics": metrics, "peakExtraction": extraction,
            "energyBalance": {"input_J": energy_in, "losses_J": energy_out,
                              "stored_J": stored, "relativeError": closure},
            "discretization": {"cells": nxy*nxy*nz, "mesh_m": dx,
                               "minimumDt_s": min_dt, "maximumDt_s": max_dt,
                               "meanDt_s": end/step, "steps": step},
            "validationStatus": "unvalidated", "productionReady": False}
    if capture_final:
        return result, {"temperature_K": temperature.cpu().numpy().ravel(),
                        "enthalpy_J_m3": enthalpy.cpu().numpy().ravel(),
                        "density_kg_m3": rho.cpu().numpy().ravel(),
                        "coordinates_m": xyz, "time_s": time, "surface_m": layer_m,
                        "accepted_dt_s": np.asarray(accepted_dt_s, dtype=np.float64),
                        "initial_temperature_K": float(t0), "cell_volume_m3": float(dx**3),
                        "steps": step}
    return result


def _run_cpu_with_final(raw, include_final_state=False):
    """Observe the reference solver's final state without filesystem IO."""
    captured = {}
    cpu = cpu_run(raw, final_state_observer=lambda state: captured.setdefault("state", state))
    state = captured.get("state")
    if state is None:
        raise ValueError("CPU final state capture missing")
    settings = cpu["settings"]
    segments, _ = scan_segments(settings)
    active_layer = max((segment["layer"] for segment in segments
                        if segment["start_s"] <= state["time_s"] + 1e-14), default=0)
    surface = 0. if settings["surfaceMode"] == "bare-plate" else (
        active_layer + 1) * thermal_si_inputs(settings, cpu["material"])["layer_m"]
    frame = {"time_s": state["time_s"], "surface_m": surface}
    if include_final_state:
        return cpu, frame, state["temperature_K"], state["coordinates_m"], state
    return cpu, frame, state["temperature_K"], state["coordinates_m"]


def _field_parity(cpu, gpu, frame, cpu_temperature, cpu_coordinates, gpu_field):
    gpu_temperature = gpu_field["temperature_K"]
    gpu_coordinates = gpu_field["coordinates_m"]
    cpu_disc, gpu_disc = cpu["discretization"], gpu["discretization"]
    cpu_time = cpu["thermalHistory"][-1]["time_s"]
    expected_end = scan_segments(cpu["settings"])[1]
    aligned = (cpu_disc["cells"] == gpu_disc["cells"] == len(cpu_temperature) == len(gpu_temperature)
        and cpu_disc["steps"] == gpu_disc["steps"] == gpu_field["steps"]
        and math.isclose(cpu_disc["mesh_m"], gpu_disc["mesh_m"], rel_tol=1e-12)
        and math.isclose(frame["time_s"], cpu_time, rel_tol=1e-12, abs_tol=1e-14)
        and math.isclose(cpu_time, expected_end, rel_tol=1e-12, abs_tol=1e-14)
        and math.isclose(gpu_field["time_s"], cpu_time, rel_tol=1e-12, abs_tol=1e-14)
        and math.isclose(gpu_field["surface_m"], frame["surface_m"], rel_tol=1e-12)
        and cpu_coordinates.shape == gpu_coordinates.shape
        and np.array_equal(cpu_coordinates, gpu_coordinates))
    alignment = {"status": "pass" if aligned else "failed", "cpuFinalTime_s": cpu_time,
                 "cpuFrameTime_s": frame["time_s"], "gpuFinalTime_s": gpu_field["time_s"],
                 "expectedEnd_s": expected_end, "cpuSteps": cpu_disc["steps"],
                 "gpuSteps": gpu_disc["steps"], "cellCount": cpu_disc["cells"]}
    if not aligned:
        return alignment, {"status": "failed", "reason": "Grid, accepted steps, or final sampling time differs"}
    if not np.isfinite(cpu_temperature).all() or not np.isfinite(gpu_temperature).all():
        return alignment, {"status": "failed", "reason": "Nonfinite final temperature field"}
    t0 = cpu["settings"]["preheat_C"]+273.15
    difference = gpu_temperature-cpu_temperature
    rise = cpu_temperature-t0
    l2 = float(np.linalg.norm(difference)/max(np.linalg.norm(rise), 1.0))
    maximum = float(np.max(np.abs(difference))/max(np.max(np.abs(rise)), 1.0))
    status = ("pass" if l2 <= PARITY_TARGETS["fieldRiseL2RelativeMax"]
              and maximum <= PARITY_TARGETS["fieldRiseMaxRelativeMax"] else "failed")
    return alignment, {"status": status, "relativeRiseL2": l2,
                       "relativeRiseMax": maximum, "cpuEncoding": "float64 final state observer",
                       "gpuEncoding": "float64 final state"}


def compare_with_cpu(raw, device="cuda:0", use_cuda_source=False, evidence_sink=None):
    """Run the same fixed case and assess frozen integral and grid-cell targets."""
    if evidence_sink is not None and not callable(evidence_sink):
        raise ValueError("Evidence sink must be callable")
    gpu, gpu_field = run_gpu(raw, device, capture_final=True,
                             use_cuda_source=use_cuda_source)
    if evidence_sink is None:
        cpu, frame, cpu_temperature, cpu_coordinates = _run_cpu_with_final(raw)
        cpu_state = None
    else:
        cpu, frame, cpu_temperature, cpu_coordinates, cpu_state = _run_cpu_with_final(
            raw, include_final_state=True)
    if (cpu["coreContract"]["modelId"] != gpu["solver"]["modelId"]
            or cpu["material"]["materialRevisionSha256"] != gpu["material"]["materialRevisionSha256"]):
        raise ValueError("CPU/GPU model or material revision mismatch")
    comparisons = {}
    alignment, field = _field_parity(cpu, gpu, frame, cpu_temperature, cpu_coordinates, gpu_field)
    comparisons["finalSampling"] = alignment
    comparisons["finalTemperatureField"] = field
    for field, (a, b) in {
        "peakTemperature_K": (cpu["metrics"]["peakTemperature_K"], gpu["metrics"]["peakTemperature_K"]),
        "input_J": (cpu["energyBalance"]["input_J"], gpu["energyBalance"]["input_J"]),
        "losses_J": (cpu["energyBalance"]["losses_J"], gpu["energyBalance"]["losses_J"]),
        "stored_J": (cpu["energyBalance"]["stored_J"], gpu["energyBalance"]["stored_J"]),
    }.items():
        difference = abs(a-b)/max(abs(a), 1e-30)
        comparisons[field] = {"cpu": a, "gpu": b, "relativeDifference": difference,
                              "status": "pass" if difference <= PARITY_TARGETS["integralRelativeMax"] else "failed"}
    cell_um = gpu["discretization"]["mesh_m"]*1e6
    for field in ("width_um", "depth_um", "length_um"):
        a, b = cpu["metrics"][field], gpu["metrics"][field]
        difference = abs(a-b)
        comparisons[field] = {"cpu": a, "gpu": b, "absoluteDifference_um": difference,
            "status": "inconclusive" if a == b == 0 else (
                "pass" if difference <= PARITY_TARGETS["widthDepthAbsoluteCellsMax"]*cell_um else "failed")}
    a, b = cpu["metrics"]["volume_um3"], gpu["metrics"]["volume_um3"]
    difference = abs(a-b)/max(a, 1e-30)
    comparisons["volume_um3"] = {"cpu": a, "gpu": b, "relativeDifference": difference,
        "status": "inconclusive" if a == b == 0 else (
            "pass" if difference <= PARITY_TARGETS["peakMeltVolumeRelativeMax"] else "failed")}
    statuses = [x["status"] for x in comparisons.values()]
    status = "failed" if "failed" in statuses else "inconclusive" if "inconclusive" in statuses else "pass"
    if evidence_sink is not None:
        if cpu_state is None:
            raise ValueError("CPU final state is unavailable for evidence capture")
        evidence_sink(cpu_state, {key: gpu_field[key] for key in (
            "coordinates_m", "temperature_K", "enthalpy_J_m3", "density_kg_m3",
            "accepted_dt_s", "time_s", "initial_temperature_K", "cell_volume_m3")})
    cpu_summary = {"solver": cpu["solver"], "coreContract": cpu["coreContract"],
                   "material": {k: cpu["material"][k] for k in ("name", "materialId", "materialRevisionSha256", "version")},
                   "discretization": cpu["discretization"]}
    if evidence_sink is not None:
        cpu_summary["resolvedSettings"] = cpu["settings"]
    return {"status": status, "scope": "same-model CPU/GPU numerical parity only",
            "experimentalValidation": False, "targets": dict(PARITY_TARGETS),
            "gpu": gpu, "cpu": cpu_summary, "comparisons": comparisons}


def run_queued_pilot(raw, artifact_dir=None):
    """Execute a queue-selected CUDA pilot while retaining separate CPU evidence."""
    request, material = validate_pilot_request(raw)
    device = request["backend"]
    reference = {k: v for k, v in request.items() if k != "jobType"}
    reference["backend"] = "reference"
    captured = {}
    if artifact_dir is None:
        parity = compare_with_cpu(reference, device)
    else:
        from lpbf_gpu_pilot_artifacts import write_pilot_artifacts

        def capture(cpu_state, gpu_state):
            captured["descriptor"] = write_pilot_artifacts(artifact_dir, cpu_state, gpu_state)

        parity = compare_with_cpu(reference, device, evidence_sink=capture)
    gpu = parity["gpu"]
    torch, cuda = require_cuda(device)
    torch.cuda.synchronize(cuda)
    properties = torch.cuda.get_device_properties(cuda)
    result = {
        "schemaVersion": 1, "jobType": PILOT_JOB_TYPE,
        "requestedMode": "standard", "effectiveMode": "gpu-pilot",
        "solver": gpu["solver"], "settings": request, "material": material,
        "metrics": gpu["metrics"], "energyBalance": gpu["energyBalance"],
        "discretization": gpu["discretization"], "peakExtraction": gpu["peakExtraction"],
        "gpuPilot": {k: v for k, v in parity.items() if k != "gpu"},
        "validationStatus": "unvalidated", "productionReady": False,
        "label": "Unvalidated CUDA thermal parity pilot",
        "confidence": "low", "artifacts": [],
        "provenance": {
            "inputHash": hashlib.sha256(json.dumps(request, sort_keys=True, allow_nan=False).encode()).hexdigest(),
            "implementationHash": implementation_fingerprint(),
            "implementationFingerprintSchema": IMPLEMENTATION_FINGERPRINT_SCHEMA,
            "materialVersion": material["version"],
            "createdAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "deviceEvidence": {
                "selected": device, "name": properties.name,
                "computeCapability": list(torch.cuda.get_device_capability(cuda)),
                "torch": torch.__version__, "cudaRuntime": torch.version.cuda,
                "thermalEvolution": device, "sourceIntegration": "cpu",
                "sourceTimestepLimiter": "cpu",
                "synchronizedAfterSolve": True,
            },
        },
    }
    if artifact_dir is not None:
        request_json = _python_json(request)
        material_json = _python_json(material)
        cpu_input_json = _python_json(reference)
        cpu_resolved_settings = parity["cpu"].get("resolvedSettings")
        if not isinstance(cpu_resolved_settings, dict):
            raise ValueError("Resolved CPU settings are unavailable for archive binding")
        cpu_resolved_settings_json = _python_json(cpu_resolved_settings)
        result["gpuRunContract"] = {
            "schemaVersion": 1,
            "runKind": PILOT_JOB_TYPE,
            "capture": {
                "contractStatus": "gpu-pilot-v1-bound",
                "modelId": gpu["solver"]["modelId"],
                "backend": device,
                "device": device,
                "dtype": gpu["solver"]["dtype"],
            },
            "serializedInputs": {
                "requestJson": request_json,
                "materialJson": material_json,
                "cpuInputJson": cpu_input_json,
                "cpuResolvedSettingsJson": cpu_resolved_settings_json,
            },
            "hashes": {
                "requestHash": hashlib.sha256(request_json.encode("utf-8")).hexdigest(),
                "materialHash": hashlib.sha256(material_json.encode("utf-8")).hexdigest(),
                "cpuInputHash": hashlib.sha256(cpu_input_json.encode("utf-8")).hexdigest(),
                "cpuResolvedSettingsHash": hashlib.sha256(cpu_resolved_settings_json.encode("utf-8")).hexdigest(),
                "implementationHash": result["provenance"]["implementationHash"],
            },
        }
        result["gpuFieldArtifacts"] = captured["descriptor"]
        from lpbf_evidence import write_artifacts
        write_artifacts(result, artifact_dir)
    enforce_gpu_pilot_result(result, artifact_dir=artifact_dir)
    json.dumps(result, allow_nan=False)
    return result


def _finite_nonnegative(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _finite_positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def _strict_json_equal(left, right):
    try:
        return _python_json(left) == _python_json(right)
    except (TypeError, ValueError, OverflowError):
        return False


def _parse_created_at(value):
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        timestamp = parsed.timestamp()
    except (OverflowError, TypeError, ValueError) as error:
        raise ValueError("Invalid archived CUDA pilot timestamp") from error
    if parsed.tzinfo is None or not math.isfinite(timestamp):
        raise ValueError("Invalid archived CUDA pilot timestamp")
    return timestamp


def enforce_gpu_pilot_result(result, artifact_dir=None):
    """Fail closed on queue restore without claiming the CPU core contract."""
    if not isinstance(result, dict) or result.get("jobType") != PILOT_JOB_TYPE:
        raise ValueError("Not a CUDA thermal pilot result")
    solver, settings = result.get("solver", {}), result.get("settings", {})
    pilot, provenance = result.get("gpuPilot", {}), result.get("provenance", {})
    if not isinstance(result.get("material"), dict):
        raise ValueError("CUDA pilot material binding invalid")
    if not all(isinstance(value, dict) for value in (solver, settings, pilot, provenance)):
        raise ValueError("CUDA pilot identity fields invalid")
    evidence = provenance.get("deviceEvidence", {})
    if not isinstance(evidence, dict):
        raise ValueError("CUDA pilot device evidence invalid")
    cpu_identity = pilot.get("cpu", {})
    if not isinstance(cpu_identity, dict):
        raise ValueError("CUDA pilot CPU evidence invalid")
    cpu_core = cpu_identity.get("coreContract", {})
    cpu_material = cpu_identity.get("material", {})
    if not isinstance(cpu_core, dict) or not isinstance(cpu_material, dict):
        raise ValueError("CUDA pilot CPU material/core evidence invalid")
    device = settings.get("backend")
    has_contract = "gpuRunContract" in result
    has_fields = "gpuFieldArtifacts" in result
    if has_contract != has_fields or (has_contract and (result["gpuRunContract"] is None
                                                        or result["gpuFieldArtifacts"] is None)):
        raise ValueError("Incomplete GPU archive contract")
    archived = has_contract
    if (not isinstance(device, str) or not re.fullmatch(r"cuda:[0-9]+", device)
            or result.get("effectiveMode") != "gpu-pilot"
            or result.get("validationStatus") != "unvalidated"
            or result.get("productionReady") is not False
            or (not archived and result.get("artifacts") != [])
            or solver.get("id") != GPU_SOLVER_ID or solver.get("modelId") != _model_id_for_settings(settings)
            or solver.get("dtype") != "float64"
            or solver.get("actualBackend") != device
            or solver.get("thermalEvolutionDevice") != device
            or solver.get("sourceIntegrationDevice") not in ("cpu", device)
            or solver.get("sourceTimestepLimiterDevice") not in ("cpu", device)
            or solver.get("sourceIntegrationDevice") != solver.get("sourceTimestepLimiterDevice")
            or evidence.get("selected") != device
            or evidence.get("thermalEvolution") != device
            or evidence.get("sourceIntegration") != solver.get("sourceIntegrationDevice")
            or (solver.get("sourceIntegrationDevice") == "cpu"
                and evidence.get("sourceTimestepLimiter") not in (None, "cpu"))
            or (solver.get("sourceIntegrationDevice") == device
                and evidence.get("sourceTimestepLimiter") != device)
            or evidence.get("synchronizedAfterSolve") is not True
            or pilot.get("experimentalValidation") is not False
            or cpu_core.get("modelId") != _model_id_for_settings(settings)
            or cpu_core.get("actualBackend") != "numpy-reference"
            or cpu_material.get("materialRevisionSha256")
                != result.get("material", {}).get("materialRevisionSha256")):
        raise ValueError("CUDA pilot identity or CPU parity binding failed")
    energy = result.get("energyBalance", {})
    if not isinstance(energy, dict):
        raise ValueError("CUDA pilot energy accounting invalid")
    values = [energy.get(k) for k in ("input_J", "losses_J", "stored_J")]
    if (any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values)
            or values[0] <= 0):
        raise ValueError("CUDA pilot energy accounting invalid")
    if archived:
        metrics = result.get("metrics", {})
        metric_keys = ("peakTemperature_K", "width_um", "depth_um", "length_um", "volume_um3")
        if (not isinstance(metrics, dict)
                or any(not _finite_nonnegative(metrics.get(key)) for key in metric_keys)):
            raise ValueError("CUDA pilot metrics contain invalid numeric values")
    error = abs(values[0]-values[1]-values[2])/values[0]
    if (error > PARITY_TARGETS["integralRelativeMax"]
            or type(energy.get("relativeError")) not in (int, float)
            or not math.isfinite(energy["relativeError"])
            or not math.isclose(error, energy["relativeError"], abs_tol=1e-10)):
        raise ValueError("CUDA pilot energy closure failed")
    comparisons = pilot.get("comparisons", {})
    expected = ("finalSampling", "finalTemperatureField", "peakTemperature_K",
                "input_J", "losses_J", "stored_J", "width_um", "depth_um",
                "length_um", "volume_um3")
    if (not isinstance(comparisons, dict)
            or any(not isinstance(comparisons.get(key), dict)
                   or comparisons[key].get("status") not in ("pass", "failed", "inconclusive")
           for key in expected)):
        raise ValueError("CUDA pilot parity report incomplete")
    statuses = [comparisons[key]["status"] for key in expected]
    status = "failed" if "failed" in statuses else "inconclusive" if "inconclusive" in statuses else "pass"
    if (pilot.get("status") != status
            or (archived and not _strict_json_equal(pilot.get("targets"), PARITY_TARGETS))
            or (not archived and pilot.get("targets") != PARITY_TARGETS)):
        raise ValueError("CUDA pilot parity status or frozen targets changed")
    if archived:
        for key in ("peakTemperature_K", "input_J", "losses_J", "stored_J",
                    "width_um", "depth_um", "length_um", "volume_um3"):
            item = comparisons[key]
            if (not isinstance(item, dict) or not _finite_nonnegative(item.get("cpu"))
                    or not _finite_nonnegative(item.get("gpu"))):
                raise ValueError("CUDA pilot parity report contains invalid numeric values")
            actual_gpu = result["energyBalance"][key] if key.endswith("_J") else result["metrics"][key]
            if item["gpu"] != actual_gpu:
                raise ValueError("CUDA pilot GPU parity result binding changed")
            difference_key = "absoluteDifference_um" if key in ("width_um", "depth_um", "length_um") else "relativeDifference"
            denominator = max(abs(item["cpu"]), 1e-30)
            actual_difference = abs(item["cpu"] - item["gpu"])
            if difference_key == "relativeDifference":
                actual_difference /= denominator
            if (not _finite_nonnegative(item.get(difference_key))
                    or not math.isclose(actual_difference, item[difference_key], rel_tol=1e-12, abs_tol=1e-12)):
                raise ValueError("CUDA pilot parity difference report changed")
    if result.get("provenance", {}).get("inputHash") != hashlib.sha256(
            json.dumps(settings, sort_keys=True, allow_nan=False).encode()).hexdigest():
        raise ValueError("CUDA pilot input binding changed")
    if archived:
        _enforce_gpu_archive_contract(result, verify_folder=artifact_dir)
    if status == "pass":
        sampling = comparisons["finalSampling"]
        cpu_disc, gpu_disc = pilot["cpu"]["discretization"], result["discretization"]
        if (sampling["cpuSteps"] != sampling["gpuSteps"]
                or sampling["cpuSteps"] != cpu_disc["steps"]
                or sampling["gpuSteps"] != gpu_disc["steps"]
                or sampling["cellCount"] != cpu_disc["cells"] or sampling["cellCount"] != gpu_disc["cells"]
                or not math.isclose(sampling["cpuFinalTime_s"], sampling["cpuFrameTime_s"], rel_tol=1e-12, abs_tol=1e-14)
                or not math.isclose(sampling["cpuFinalTime_s"], sampling["gpuFinalTime_s"], rel_tol=1e-12, abs_tol=1e-14)
                or not math.isclose(sampling["cpuFinalTime_s"], sampling["expectedEnd_s"], rel_tol=1e-12, abs_tol=1e-14)):
            raise ValueError("CUDA pilot final sampling report conflicts with discretization")
        field = comparisons["finalTemperatureField"]
        if (not _finite_nonnegative(field.get("relativeRiseL2"))
                or not _finite_nonnegative(field.get("relativeRiseMax"))
                or field["relativeRiseL2"] > PARITY_TARGETS["fieldRiseL2RelativeMax"]
                or field["relativeRiseMax"] > PARITY_TARGETS["fieldRiseMaxRelativeMax"]):
            raise ValueError("CUDA pilot final-field parity exceeds frozen targets")
        for key in ("peakTemperature_K", "input_J", "losses_J", "stored_J"):
            item = comparisons[key]
            actual = abs(item["cpu"]-item["gpu"])/max(abs(item["cpu"]), 1e-30)
            if (not math.isfinite(actual) or actual > PARITY_TARGETS["integralRelativeMax"]
                    or not math.isclose(actual, item["relativeDifference"], abs_tol=1e-10)):
                raise ValueError("CUDA pilot integral parity report changed")
        cell_um = gpu_disc["mesh_m"]*1e6
        for key in ("width_um", "depth_um", "length_um"):
            item = comparisons[key]
            actual = abs(item["cpu"]-item["gpu"])
            if (not math.isfinite(actual) or actual > PARITY_TARGETS["widthDepthAbsoluteCellsMax"]*cell_um
                    or not math.isclose(actual, item["absoluteDifference_um"], abs_tol=1e-10)):
                raise ValueError("CUDA pilot geometry parity report changed")
        volume = comparisons["volume_um3"]
        actual = abs(volume["cpu"]-volume["gpu"])/max(volume["cpu"], 1e-30)
        if (not math.isfinite(actual) or actual > PARITY_TARGETS["peakMeltVolumeRelativeMax"]
                or not math.isclose(actual, volume["relativeDifference"], abs_tol=1e-10)):
            raise ValueError("CUDA pilot melt-volume parity report changed")
