"""Persistent JSON-lines RPC worker, SQLite queue and isolated cancellable job processes.

Normally launched inside WSL by the Node bridge. No browser-supplied shell commands.
"""
import hashlib
import base64
import json
import math
import os
from pathlib import Path
import re
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from lpbf_material_registry import catalog
from four_alloy_materials import resolve_alloy_id, thermal_props, THERMAL_NAME
from lpbf_simulation import run, validate, fingerprint
from lpbf_openfoam import BINARY
from lpbf_evidence import resource_estimate, enforce_thermal_balances
from lpbf_run_capture import capture_run
from lpbf_solidification_microstructure import compute_solidification_microstructure  # Phase 8
from lpbf_adaptive_feedforward import AdaptiveFeedforwardMitigator
from lpbf_experimental_validation import validate_experiment
from lpbf_fatigue_fracture import MurakamiFatigueEngine
from lpbf_multilaser_plume import ShieldGasFlow, PlumeParameters, MultiLaserPlumeEngine
from lpbf_optical_tomography import OpticalTomographySimulator
from lpbf_powder_dem_compaction import PowderCompactionEngine
from lpbf_support_optimization import SupportStructureOptimizer
from lpbf_thermal_accumulation import AlloyThermalProperties, HatchProcessConfig, MultiTrackThermalEngine
from lpbf_thermomechanical import analyze_distortion
from lpbf_toolpath_kinematics import LPBFToolpathParser, GalvanometerKinematicsEngine, ScannerProfile
from lpbf_transient_enthalpy_fdm import TransientEnthalpyFDMSolver
from stl_voxelizer import STLVoxelizer

ROOT = Path(os.environ.get("METALLIKSA_JOB_ROOT", str(Path(__file__).resolve().parents[1]/".lpbf-jobs")))
DEFAULT_JOB_TIMEOUT_S = 300.0
IN625_BAREPLATE_JOB_TYPE = "in625-bareplate-field"
IN625_BAREPLATE_MODEL_ID = "in625-bareplate-enthalpy-conduction-v1"
IN625_BAREPLATE_SOLVER_ID = "in625-bareplate-field-v1"
IN625_BAREPLATE_SOLVER_REVISION = "1"
IN625_BAREPLATE_ARTIFACT = "in625-temperature-field-f64le.bin"
IN625_BAREPLATE_MAX_CELLS = 1_000_000
IN625_BAREPLATE_MAX_CELL_STEPS = 2_000_000
IN625_BAREPLATE_MAX_STEPS = 25_000


def _validate_in625_bareplate_request(raw):
    """Strictly normalize the worker API payload for the bounded IN625 solver."""
    from in625_bareplate_field import BareplateConfig, _validate

    if not isinstance(raw, dict) or raw.get("jobType") != IN625_BAREPLATE_JOB_TYPE:
        raise ValueError("Invalid IN625 bareplate job type")
    if set(raw) - {"jobType", "backend", "config"}:
        raise ValueError("Unknown IN625 bareplate request fields")
    backend = raw.get("backend")
    if backend != "cpu" and (not isinstance(backend, str) or not re.fullmatch(r"cuda:[0-9]+", backend)):
        raise ValueError("backend must be 'cpu' or an explicit CUDA device such as 'cuda:0'")
    config_raw = raw.get("config", {})
    if not isinstance(config_raw, dict):
        raise ValueError("config must be an object")
    defaults = BareplateConfig()
    aliases = {
        "shape_xyz": "shapeXYZ", "cell_size_m": "cellSizeM",
        "initial_temperature_K": "initialTemperatureK", "dt_s": "dtS",
        "steps": "steps", "absorbed_power_W": "absorbedPowerW",
        "spot_sigma_m": "spotSigmaM", "scan_start_x_m": "scanStartXM",
        "scan_y_m": "scanYM", "scan_velocity_x_m_s": "scanVelocityXMS",
    }
    # The worker-facing API is camelCase; reject accidental snake_case aliases.
    allowed = set(aliases.values())
    if set(config_raw) - allowed:
        raise ValueError("Unknown IN625 bareplate config fields")
    config_values = {}
    for field_name, api_name in aliases.items():
        value = config_raw.get(api_name, getattr(defaults, field_name))
        if field_name in ("shape_xyz", "cell_size_m"):
            if not isinstance(value, (list, tuple)) or len(value) != 3:
                raise ValueError(f"{api_name} must contain exactly three values")
            if field_name == "shape_xyz":
                if any(type(v) is not int or v < 2 for v in value):
                    raise ValueError("shapeXYZ must contain integers >= 2")
                config_values[field_name] = tuple(value)
            else:
                if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in value):
                    raise ValueError("cellSizeM must contain positive finite numbers")
                config_values[field_name] = tuple(float(v) for v in value)
        else:
            if field_name == "steps":
                if type(value) is not int or value < 1:
                    raise ValueError("steps must be a positive integer")
            elif type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f"{api_name} must be a finite number")
            config_values[field_name] = value
    config = BareplateConfig(**config_values)
    cells = math.prod(config.shape_xyz)
    if cells > IN625_BAREPLATE_MAX_CELLS:
        raise ValueError(f"IN625 bareplate cell count exceeds {IN625_BAREPLATE_MAX_CELLS}")
    if config.steps > IN625_BAREPLATE_MAX_STEPS:
        raise ValueError(f"IN625 bareplate step count exceeds {IN625_BAREPLATE_MAX_STEPS}")
    if cells * config.steps > IN625_BAREPLATE_MAX_CELL_STEPS:
        raise ValueError(f"IN625 bareplate work exceeds {IN625_BAREPLATE_MAX_CELL_STEPS} cell-steps")
    _validate(config)
    normalized_config = {api_name: (list(config_values[field_name]) if field_name in ("shape_xyz", "cell_size_m")
                                     else config_values[field_name])
                         for field_name, api_name in aliases.items()}
    request = {"jobType": IN625_BAREPLATE_JOB_TYPE, "backend": backend, "config": normalized_config}
    return request, config


def _check_in625_bareplate_cuda_device(device):
    """Preflight the exact requested CUDA device; never substitute a backend."""
    try:
        import torch
    except ImportError as error:
        raise RuntimeError("PyTorch is required for the explicit CUDA path") from error
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; explicit CUDA path cannot run")
    index = int(device.split(":", 1)[1])
    if index >= torch.cuda.device_count():
        raise ValueError(f"requested CUDA device index is unavailable: {device}")


def _write_deterministic_bareplate_field(path, result):
    """Write final temperature as deterministic little-endian float64 raw bytes."""
    import numpy as np
    temperature = result.temperature_K
    if hasattr(temperature, "detach"):
        temperature = temperature.detach().to(device="cpu").numpy()
    np.asarray(temperature, dtype="<f8", order="C").tofile(path)


def _bareplate_result_to_json(raw, config, output, folder):
    """Adapt BareplateResult into a bounded, finite JSON result and archive artifact."""
    import numpy as np
    from in625_thermal_material import in625_lpbf_thermal_snapshot

    snapshot = in625_lpbf_thermal_snapshot()
    def array(value):
        if hasattr(value, "detach"):
            value = value.detach().to(device="cpu").numpy()
        result = np.asarray(value, dtype=np.float64)
        if not np.isfinite(result).all():
            raise ValueError("IN625 bareplate solver returned nonfinite values")
        return result

    temperature = array(output.temperature_K)
    enthalpy = array(output.specific_enthalpy_J_kg)
    times = array(output.time_s)
    total = array(output.total_enthalpy_J)
    peaks = array(output.peak_temperature_K)
    residuals = array(output.energy_residual_J)
    if temperature.shape != (config.shape_xyz[2], config.shape_xyz[1], config.shape_xyz[0]):
        raise ValueError("IN625 bareplate final field shape mismatch")
    if enthalpy.shape != temperature.shape or any(v.ndim != 1 or len(v) != config.steps
                                                    for v in (times, total, peaks, residuals)):
        raise ValueError("IN625 bareplate history shape mismatch")
    if not (np.diff(times) > 0).all() or (temperature < 273.15).any() or (temperature > 1623.15).any():
        raise ValueError("IN625 bareplate field or time history is outside its model bounds")

    artifact_path = Path(folder) / IN625_BAREPLATE_ARTIFACT
    _write_deterministic_bareplate_field(artifact_path, output)
    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"), allow_nan=False)
    input_hash = hashlib.sha256(canonical.encode()).hexdigest()
    material = snapshot
    device = raw["backend"]
    device_evidence = {"selected": device, "thermalEvolution": device, "noCpuFallback": True}
    if device.startswith("cuda:"):
        import torch
        cuda_index = int(device.split(":", 1)[1])
        actual = torch.device(device)
        torch.cuda.synchronize(actual)
        properties = torch.cuda.get_device_properties(actual)
        device_evidence.update(name=properties.name, index=cuda_index,
                               computeCapability=list(torch.cuda.get_device_capability(actual)),
                               torch=torch.__version__, cudaRuntime=torch.version.cuda,
                               synchronizedAfterSolve=True)
    else:
        device_evidence.update(name="NumPy CPU", index=None, synchronizedAfterSolve=True)

    initial_total = float(total[0] - config.absorbed_power_W * config.dt_s)
    input_energy = float(config.absorbed_power_W * config.dt_s * config.steps)
    stored_energy = float(total[-1] - initial_total)
    energy_relative_error = abs(stored_energy-input_energy) / max(input_energy, 1e-30)
    if energy_relative_error > 0.01:
        raise ValueError(f"IN625 bareplate energy closure failed ({energy_relative_error:.6g})")
    digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    return {
        "schemaVersion": 1,
        "jobType": IN625_BAREPLATE_JOB_TYPE,
        "runKind": "bounded-material-screening",
        "requestedMode": "screening",
        "effectiveMode": "screening",
        "fallbackReason": None,
        "settings": raw,
        "material": material,
        "solver": {"id": IN625_BAREPLATE_SOLVER_ID, "modelId": IN625_BAREPLATE_MODEL_ID,
                   "revision": IN625_BAREPLATE_SOLVER_REVISION, "actualBackend": device,
                   "device": device, "dtype": "float64"},
        "validationStatus": "unvalidated-literature-model-screening",
        "productionReady": False,
        "confidence": "low",
        "label": "IN625 bare-substrate conduction screening",
        "modelScope": "3D bounded enthalpy conduction on bare substrate; all faces adiabatic; no powder, melt pool, absorptivity, vapor, flow, or free-surface physics",
        "metrics": {"cells": int(temperature.size), "peakTemperature_K": float(temperature.max()),
                    "finalTime_s": float(times[-1]), "finalEnthalpy_J": float(total[-1]),
                    "energyResidual_J": float(residuals[-1]),
                    "minimumSourceCaptureFraction": float(output.metadata["sourceCaptureFractionMinimum"])},
        "energyHistory": [{"time_s": float(t), "totalEnthalpy_J": float(e),
                           "peakTemperature_K": float(p), "energyResidual_J": float(r)}
                          for t, e, p, r in zip(times, total, peaks, residuals)],
        "energyBalance": {"input_J": input_energy, "losses_J": 0.0, "stored_J": stored_energy,
                          "relativeError": energy_relative_error,
                          "scope": "adiabatic bareplate enthalpy accounting; not melt-pool or interface closure"},
        "field": {"artifact": IN625_BAREPLATE_ARTIFACT, "shapeXYZ": list(config.shape_xyz),
                  "dtype": "float64", "encoding": "little-endian",
                  "byteOrder": "little-endian", "arrayOrder": "z,y,x", "sha256": digest,
                  "scope": "final cell-centered temperature field only; no interface interpolation"},
        "numericalDiagnostics": {"sourceCaptureFractionMinimum": float(output.metadata["sourceCaptureFractionMinimum"]),
                                 "temperatureBounds_K": [273.15, 1623.15],
                                 "density_kg_m3": output.metadata["density_kg_m3"],
                                 "densityBasis": output.metadata["densityBasis"]},
        "provenance": {"inputSha256": input_hash,
                       "implementationIdentity": {"modelId": IN625_BAREPLATE_MODEL_ID,
                                                   "solverRevision": IN625_BAREPLATE_SOLVER_REVISION,
                                                   "materialRevisionSha256": snapshot["materialRevisionSha256"],
                                                   "backend": device, "device": device},
                       "deviceEvidence": device_evidence},
        "artifacts": [],
        "assumptions": ["Constant 8440 kg/m^3 supplier-bulletin density assumption; not lot-matched.",
                        "Source input is absorbed power in W; no optical absorptivity is inferred.",
                        "Constitutive law is bounded to 273.15..1623.15 K and remains unvalidated literature-model screening."],
    }


def _enforce_bareplate_result(result, settings, folder=None):
    """Verify queue/cache identity and the custom bareplate result contract."""
    from in625_thermal_material import in625_lpbf_thermal_snapshot

    if (not isinstance(result, dict) or not isinstance(settings, dict)
            or result.get("jobType") != IN625_BAREPLATE_JOB_TYPE
            or result.get("settings") != settings or result.get("validationStatus") != "unvalidated-literature-model-screening"
            or result.get("productionReady") is not False):
        raise ValueError("Invalid IN625 bareplate result identity")
    backend = settings.get("backend")
    material = result.get("material")
    solver = result.get("solver")
    provenance = result.get("provenance")
    field = result.get("field")
    if not isinstance(solver, dict) or not isinstance(provenance, dict) or not isinstance(field, dict):
        raise ValueError("IN625 bareplate result is missing solver/provenance/field identity")
    identity = provenance.get("implementationIdentity")
    expected = in625_lpbf_thermal_snapshot()
    if (material != expected or solver.get("id") != IN625_BAREPLATE_SOLVER_ID
            or solver.get("modelId") != IN625_BAREPLATE_MODEL_ID
            or solver.get("revision") != IN625_BAREPLATE_SOLVER_REVISION
            or solver.get("actualBackend") != backend
            or identity != {"modelId": IN625_BAREPLATE_MODEL_ID,
                            "solverRevision": IN625_BAREPLATE_SOLVER_REVISION,
                            "materialRevisionSha256": expected["materialRevisionSha256"],
                            "backend": backend, "device": backend}
            or field.get("artifact") != IN625_BAREPLATE_ARTIFACT):
        raise ValueError("IN625 bareplate model/material/backend identity mismatch")
    energy = result.get("energyBalance", {})
    if not isinstance(energy, dict):
        raise ValueError("Invalid IN625 bareplate energy accounting")
    values = [energy.get(name) for name in ("input_J", "losses_J", "stored_J", "relativeError")]
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in values):
        raise ValueError("Invalid IN625 bareplate energy accounting")
    if values[1] != 0 or values[3] < 0 or values[3] > 0.01:
        raise ValueError("IN625 bareplate energy closure failed")
    if folder is not None:
        refs = result.get("artifacts")
        if (not isinstance(refs, list) or any(not isinstance(item, dict)
                                              or set(item) != {"path", "size_bytes", "sha256"}
                                              for item in refs)):
            raise ValueError("IN625 bareplate artifact manifest missing")
        entry = next((item for item in refs if item.get("path") == IN625_BAREPLATE_ARTIFACT), None)
        path = Path(folder) / IN625_BAREPLATE_ARTIFACT
        if (not entry or not path.is_file() or path.stat().st_size != entry.get("size_bytes")
                or hashlib.sha256(path.read_bytes()).hexdigest() != entry.get("sha256")
                or entry.get("sha256") != field.get("sha256")):
            raise ValueError("IN625 bareplate field artifact integrity failed")


def _run_in625_bareplate_job(raw, folder):
    from in625_bareplate_field import run_cpu, run_cuda
    request, config = _validate_in625_bareplate_request(raw)
    output = run_cpu(config) if request["backend"] == "cpu" else run_cuda(config, request["backend"])
    result = _bareplate_result_to_json(request, config, output, folder)
    from lpbf_evidence import write_artifacts
    write_artifacts(result, folder)
    _enforce_bareplate_result(result, request, folder)
    return result


def _archive_run_kind(job_type, result=None):
    if job_type == "gpu-thermal-pilot":
        contract = result.get("gpuRunContract") if isinstance(result, dict) else None
        fields = result.get("gpuFieldArtifacts") if isinstance(result, dict) else None
        capture = contract.get("capture") if isinstance(contract, dict) else None
        if (isinstance(contract, dict) and contract.get("runKind") == job_type
                and isinstance(fields, dict)
                and isinstance(capture, dict)
                and capture.get("contractStatus") == "gpu-pilot-v1-bound"):
            return "gpu-thermal-pilot"
        return None  # Legacy pilot output remains view-only.
    if job_type == IN625_BAREPLATE_JOB_TYPE:
        return "bounded-material-screening"
    if job_type == "build-job":
        return "build-screening"
    if isinstance(result, dict):
        settings = result.get("settings")
        core_contract = result.get("coreContract")
        physics = result.get("resolvedPhysics")
        if not isinstance(physics, dict) and isinstance(core_contract, dict):
            physics = core_contract.get("resolvedPhysics")
        if (isinstance(settings, dict) and settings.get("mode") == "screening"
                and isinstance(physics, dict) and physics.get("transient") is False):
            return "analytical-screening"
    return "transient-thermal"


def capabilities():
    foam = Path("/opt/openfoam14/etc/bashrc")
    version = None
    if foam.exists():
        try:
            r = subprocess.run(["bash", "-lc", "source /opt/openfoam14/etc/bashrc; foamVersion"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and "OpenFOAM-14" in r.stdout+r.stderr:
                version = "OpenFOAM-14"
        except (OSError, subprocess.TimeoutExpired):
            pass
    cuda = dict(selection="backend=cuda:N", availability="checked-on-submit", cpuAlternative="backend=cpu",
                evidenceScope="IN625 bareplate bounded enthalpy-conduction screening only")
    try:
        import torch
        cuda.update(runtimeAvailable=bool(torch.cuda.is_available()), deviceCount=int(torch.cuda.device_count()),
                    torchVersion=str(torch.__version__), cudaRuntime=torch.version.cuda)
    except ImportError:
        cuda.update(runtimeAvailable=False, deviceCount=0, torchVersion=None, cudaRuntime=None)
    return dict(openfoamVersion=version, openfoamThermal=bool(version and BINARY.is_file()),
                binaryHash=hashlib.sha256(BINARY.read_bytes()).hexdigest() if BINARY.is_file() else None,
                freeSurfaceSolver=bool(version and (Path(__file__).parent/"openfoam/bin/metalliksaMeltPoolFoam").is_file()), platform=sys.platform,
                thermalSolver=True, materials=catalog(),
                cudaThermalPilot=dict(selection="jobType=gpu-thermal-pilot; backend=cuda:N",
                    availability="checked-on-submit", cpuAlternative="backend=reference",
                    evidenceScope="same-model numerical parity only"),
                in625BareplateField=dict(jobType=IN625_BAREPLATE_JOB_TYPE, cpuAvailable=True,
                    cuda=cuda, alloyId="in625", modelId=IN625_BAREPLATE_MODEL_ID,
                    validationStatus="unvalidated-literature-model-screening", productionReady=False,
                    maximumCells=IN625_BAREPLATE_MAX_CELLS, maximumCellSteps=IN625_BAREPLATE_MAX_CELL_STEPS),
                limitation="No qualified LPBF free-surface CFD solver. High-Fidelity requests return explicitly labelled analytical screening.")


class Queue:
    def __init__(self, root=ROOT, start=True):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root/"queue.sqlite"
        self.caps = capabilities()
        self.lock = threading.RLock()
        self.closed = threading.Event()
        self.thread = None
        with self.connect() as c:
            c.execute("CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, cache_key TEXT, status TEXT, progress REAL, log TEXT, error TEXT, created REAL)")
            c.execute("UPDATE jobs SET status='failed',error='Worker restarted during execution' WHERE status='running'")
        if start:
            self.thread = threading.Thread(target=self.work, daemon=True)
            self.thread.start()

    def close(self):
        self.closed.set()
        if self.thread:
            self.thread.join(timeout=6)

    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.db, timeout=10)
        c.row_factory = sqlite3.Row
        try:
            with c:
                yield c
        finally:
            c.close()

    def update(self, job, **values):
        with self.connect() as c:
            c.execute("UPDATE jobs SET "+",".join(k+"=?" for k in values)+" WHERE id=?", [*values.values(), job])

    def finish_running(self, job, **values):
        # Atomic terminal transition: a cancellation winning the race stays cancelled.
        with self.lock, self.connect() as c:
            c.execute("UPDATE jobs SET "+",".join(k+"=?" for k in values)+" WHERE id=? AND status='running'",
                      [*values.values(), job])

    def get(self, job):
        if not isinstance(job, str) or len(job) != 32 or any(ch not in "0123456789abcdef" for ch in job):
            raise ValueError("Invalid job id")
        with self.connect() as c:
            row = c.execute("SELECT * FROM jobs WHERE id=?", (job,)).fetchone()
        if row is None:
            raise ValueError("Job not found")
        out = dict(row)
        settings = json.loads((self.root/job/"input.json").read_text())
        out["requestSummary"] = {k:settings.get(k) for k in ("jobType","mode","backend","material")}
        if settings.get("jobType") == IN625_BAREPLATE_JOB_TYPE:
            out["requestSummary"] = {k:settings.get(k) for k in ("jobType", "backend", "config")}
        if out["status"] == "completed":
            try:
                out["result"] = json.loads((self.root/job/"result.json").read_text())
                if settings.get("jobType") == "gpu-thermal-pilot":
                    from lpbf_gpu_thermal import enforce_gpu_pilot_result
                    from lpbf_core_contract import _verify_material_revision
                    material = out["result"].get("material") if isinstance(out["result"], dict) else None
                    if not isinstance(material, dict) or "materialRevisionSha256" not in material:
                        raise ValueError("CUDA pilot material revision snapshot is required")
                    _verify_material_revision(material)
                    enforce_gpu_pilot_result(out["result"], artifact_dir=self.root/job)
                    # The pilot guard binds a result to its own settings;
                    # also bind it to the separately persisted submitted job.
                    submitted_hash = hashlib.sha256(
                        json.dumps(settings, sort_keys=True, allow_nan=False).encode()).hexdigest()
                    if out["result"]["provenance"]["inputHash"] != submitted_hash:
                        raise ValueError("CUDA pilot result does not match submitted settings")
                elif settings.get("jobType") == IN625_BAREPLATE_JOB_TYPE:
                    _enforce_bareplate_result(out["result"], settings, self.root/job)
                else:
                    enforce_thermal_balances(out["result"])
            except (OSError, ValueError) as error:
                out.pop("result", None)
                out.update(status="failed", error=f"Saved result integrity failed: {error}")
                self.update(job, status=out["status"], error=out["error"])
        return out

    def capture(self, job):
        with self.lock:
            state = self.get(job)
            if state['status'] != 'completed':
                raise ValueError('Only completed jobs can be captured')
            return capture_run(self.root/job, job)

    def archive_capture(self, job):
        # Internal RPC only: Node maps this root; HTTP never supplies a path.
        return dict(capture=self.capture(job), root=str(self.root.absolute()), platform=sys.platform)

    def artifact(self, payload):
        state = self.get(payload["id"])
        name = payload.get("name")
        import re
        allowed = isinstance(name, str) and (name in ("temperature-slice.svg", "phase-slice.svg", "thermal-history.csv", "field-series.json", "field-coordinates.bin", IN625_BAREPLATE_ARTIFACT) or re.fullmatch(r"field-frame-[0-9]{3}\.bin", name))
        if state["status"] != "completed" or not allowed:
            raise ValueError("Artifact unavailable")
        entry = next((a for a in state["result"].get("artifacts",[]) if a["path"] == name),None)
        if not entry or entry["size_bytes"] > 8_000_000: raise ValueError("Artifact unavailable or too large")
        path = self.root/payload["id"]/name
        if path.stat().st_size != entry["size_bytes"]: raise ValueError("Artifact size mismatch")
        content = path.read_bytes()
        if len(content) != entry["size_bytes"] or hashlib.sha256(content).hexdigest() != entry["sha256"]: raise ValueError("Artifact integrity failed")
        return dict(content=base64.b64encode(content).decode(),type="image/svg+xml" if name.endswith(".svg") else "application/octet-stream" if name.endswith(".bin") else "application/json" if name.endswith(".json") else "text/csv")

    def submit(self, raw, *, execution_scope="deduplicated"):
        if execution_scope not in ("deduplicated", "repeat"):
            raise ValueError("Invalid execution scope")
        job_type = raw.get("jobType")
        if job_type == "build-job":
            p, m = raw, raw
        elif job_type == "gpu-thermal-pilot":
            from lpbf_gpu_thermal import validate_pilot_request
            p, m = validate_pilot_request(raw)
        elif job_type == IN625_BAREPLATE_JOB_TYPE:
            p, _ = _validate_in625_bareplate_request(raw)
            if p["backend"].startswith("cuda:"):
                _check_in625_bareplate_cuda_device(p["backend"])
            from in625_thermal_material import in625_lpbf_thermal_snapshot
            m = in625_lpbf_thermal_snapshot()
        else:
            p, m = validate(raw)
        # A rebuilt binary must invalidate a long-lived worker's cache identity.
        self.caps["binaryHash"] = hashlib.sha256(BINARY.read_bytes()).hexdigest() if BINARY.is_file() else None
        self.caps["openfoamThermal"] = bool(self.caps["openfoamVersion"] and self.caps["binaryHash"])
        if job_type == IN625_BAREPLATE_JOB_TYPE:
            identity = {"request": p, "materialRevisionSha256": m["materialRevisionSha256"],
                        "modelId": IN625_BAREPLATE_MODEL_ID,
                        "solverRevision": IN625_BAREPLATE_SOLVER_REVISION,
                        "backend": p["backend"], "device": p["backend"], "capabilities": self.caps}
            key_payload = json.dumps(identity, sort_keys=True, separators=(",", ":"), allow_nan=False)
        else:
            key_payload = fingerprint(p, m)+json.dumps(self.caps, sort_keys=True)
        key = hashlib.sha256(key_payload.encode()).hexdigest()
        with self.lock, self.connect() as c:
            row = None if execution_scope == "repeat" else c.execute(
                "SELECT id FROM jobs WHERE cache_key=? AND status IN ('queued','running','completed') ORDER BY created DESC LIMIT 1", (key,)).fetchone()
            if row:
                try:
                    cached = self.get(row["id"])
                    if cached["status"] not in ("queued", "running", "completed"):
                        raise ValueError("Cached result no longer usable")
                    if cached["status"] == "completed":
                        for artifact in cached["result"].get("artifacts", []):
                            folder = (self.root/row["id"]).resolve()
                            path = (folder/artifact["path"]).resolve()
                            if folder not in path.parents:
                                raise ValueError("Cached artifact escapes job directory")
                            if not path.is_file() or path.stat().st_size != artifact["size_bytes"]:
                                raise ValueError("Cached artifact missing or size changed")
                            digest = hashlib.sha256()
                            with path.open("rb") as stream:
                                for chunk in iter(lambda: stream.read(1024*1024), b""): digest.update(chunk)
                            if digest.hexdigest() != artifact["sha256"]:
                                raise ValueError("Cached artifact checksum mismatch")
                    return {**cached, "cacheHit": cached["status"] == "completed",
                            "deduplicated": cached["status"] != "completed"}
                except (OSError, ValueError, KeyError):
                    c.execute("UPDATE jobs SET status='failed',error='Cached result/artifacts unavailable or corrupt' WHERE id=?", (row["id"],))
            if c.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0] >= 16:
                raise ValueError("Queue full (16 jobs)")
            job = uuid.uuid4().hex
            folder = self.root/job; folder.mkdir()
            (folder/"input.json").write_text(json.dumps(p, allow_nan=False))
            (folder/"capabilities.json").write_text(json.dumps(self.caps))
            c.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?)", (job, key, "queued", 0., "", None, time.time()))
        return {**self.get(job), "cacheHit": False}

    def cancel(self, job):
        with self.lock:
            state = self.get(job)
            if state["status"] in ("queued", "running"):
                self.update(job, status="cancelled", error="Cancelled by user")
        return self.get(job)

    def work(self):
        while not self.closed.is_set():
            row = None
            try:
                with self.lock, self.connect() as c:
                    row = c.execute("SELECT id FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
                    if row:
                        c.execute("UPDATE jobs SET status='running' WHERE id=?", (row["id"],))
                if not row:
                    time.sleep(.1); continue
                self.execute(row["id"])
            except Exception as e:
                if row:
                    self.finish_running(row["id"], status="failed", error=str(e))
                time.sleep(.1)

    def execute(self, job):
        folder = self.root/job
        params = json.loads((folder/"input.json").read_text())
        timeout_s = params.get("timeout_s", DEFAULT_JOB_TIMEOUT_S)
        with (folder/"progress.log").open("w") as log:
            child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--execute", str(folder)],
                                     stdout=log, stderr=log, start_new_session=(os.name != "nt"))
            started = time.monotonic()
            try:
                while child.poll() is None:
                    state = self.get(job)["status"]
                    timed_out = time.monotonic()-started > timeout_s
                    if state == "cancelled" or timed_out or self.closed.is_set():
                        if os.name == "nt":
                            child.kill()
                        else:
                            os.killpg(child.pid, signal.SIGKILL)
                        child.wait(timeout=5)
                        if state == "cancelled":
                            pass
                        elif timed_out:
                            self.finish_running(job, status="timed_out", error="Simulation timeout")
                        elif self.closed.is_set():
                            self.finish_running(job, status="failed", error="Worker stopped during execution")
                        return
                    text = (folder/"progress.log").read_text(errors="replace")[-16000:]
                    progress = self.get(job)["progress"]
                    for line in text.splitlines():
                        try:
                            event = json.loads(line)
                            progress = max(progress, min(.99, event.get("progress", 0.)))
                        except (ValueError, AttributeError, TypeError):
                            pass
                    self.update(job, progress=progress, log=text)
                    time.sleep(.15)
                with self.lock:
                    if self.get(job)["status"] == "cancelled":
                        return
                    final_log = (folder/"progress.log").read_text(errors="replace")[-16000:]
                    if time.monotonic()-started > timeout_s or self.closed.is_set():
                        self.finish_running(job, status="timed_out" if not self.closed.is_set() else "failed",
                                            error="Simulation timeout" if not self.closed.is_set() else "Worker stopped during execution", log=final_log)
                        return
                    if child.returncode == 0 and (folder/"result.json").exists():
                        result = json.loads((folder/"result.json").read_text())
                        if params.get("jobType") == "gpu-thermal-pilot":
                            from lpbf_gpu_thermal import enforce_gpu_pilot_result
                            enforce_gpu_pilot_result(result, artifact_dir=folder)
                        elif params.get("jobType") == IN625_BAREPLATE_JOB_TYPE:
                            _enforce_bareplate_result(result, params, folder)
                        else:
                            enforce_thermal_balances(result)
                        self.finish_running(job, status="completed", progress=1., log=final_log)
                    else:
                        self.finish_running(job, status="failed", error=final_log[-4000:] or f"Solver exit {child.returncode}", log=final_log)
            finally:
                if child.poll() is None:
                    if os.name == "nt": child.kill()
                    else: os.killpg(child.pid, signal.SIGKILL)
                    child.wait()


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--execute":
        folder = Path(sys.argv[2])
        if os.name != "nt":
            parent_pid = os.getppid()
            def monitor_parent():
                while True:
                    time.sleep(.5)
                    if os.getppid() != parent_pid:
                        os.killpg(os.getpgrp(), signal.SIGKILL)
            threading.Thread(target=monitor_parent, daemon=True).start()
        def report(progress, message):
            print(json.dumps(dict(progress=progress, message=message)), flush=True)
        try:
            execution_start = time.monotonic()
            input_data = json.loads((folder/"input.json").read_text())
            job_type = input_data.get("jobType")

            if job_type == "gpu-thermal-pilot":
                from lpbf_gpu_thermal import run_queued_pilot
                result = run_queued_pilot(input_data, artifact_dir=folder)
            elif job_type == IN625_BAREPLATE_JOB_TYPE:
                result = _run_in625_bareplate_job(input_data, folder)
            elif job_type == "build-job":
                from lpbf_build_job_solver import solve_lpbf_build_job
                result = solve_lpbf_build_job(input_data)
                if "provenance" not in result:
                    result["provenance"] = {}
                result["settings"] = input_data
                result["material"] = {
                    "id": result.get("alloyId"),
                    "propertySha256": result.get("materialPropertySha256"),
                }
                from lpbf_evidence import write_artifacts
                write_artifacts(result, folder)
            else:
                result = run(input_data, report, folder,
                             json.loads((folder/"capabilities.json").read_text()))

            run_kind = _archive_run_kind(job_type, result)
            if run_kind is not None:
                result["runKind"] = run_kind
            result["provenance"]["runtime_s"] = time.monotonic()-execution_start
            import platform
            import numpy
            result["provenance"]["executionRuntime"] = dict(
                executable=sys.executable, python=platform.python_version(),
                platform=platform.platform(), numpy=numpy.__version__)
            (folder/"result.tmp").write_text(json.dumps(result, allow_nan=False))
            (folder/"result.tmp").replace(folder/"result.json")
        except Exception as e:
            print(str(e), flush=True); sys.exit(1)
        return
    ROOT.mkdir(parents=True, exist_ok=True)
    # OS-held lock prevents a second worker from invalidating live running jobs.
    instance_lock = (ROOT/"worker.lock").open("a+b")
    try:
        if os.name == "nt":
            import msvcrt
            instance_lock.seek(0); instance_lock.write(b"0"); instance_lock.flush(); instance_lock.seek(0)
            msvcrt.locking(instance_lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(instance_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("Another LPBF worker owns this job root", file=sys.stderr); sys.exit(2)
    queue = Queue()
    for line in sys.stdin:
        request = {}
        try:
            if len(line) > 1000000: raise ValueError("RPC payload too large")
            request = json.loads(line)
            method = request["method"]
            if method == "capabilities": data = queue.caps
            elif method == "estimate":
                p, m = validate(request["payload"])
                data = resource_estimate(p,m)
            elif method == "submit": data = queue.submit(request["payload"])
            elif method == "submit-repeat": data = queue.submit(request["payload"], execution_scope="repeat")
            elif method == "artifact": data = queue.artifact(request["payload"])
            elif method == "capture": data = queue.capture(request["payload"])
            elif method == "archive-capture": data = queue.archive_capture(request["payload"])
            elif method == "get": data = queue.get(request["payload"])
            elif method == "cancel": data = queue.cancel(request["payload"])
            elif method == "solidification-microstructure":   # Phase 8
                payload = request["payload"]
                p = payload.get("params", {})
                m = payload.get("material", {})
                cfd = payload.get("cfdResult", None)
                data = compute_solidification_microstructure(p, m, cfd)
            elif method == "thermomechanical-distortion":     # Phase 9
                payload = request["payload"]
                p = payload.get("params", {})
                m = payload.get("material", {})
                from lpbf_thermomechanical import analyze_distortion
                data = analyze_distortion(p, m)
            elif method == "industrial-fatigue":              # Phase 10 (New)
                payload = request["payload"]
                from phase10_industrial import run_industrial_fatigue_analysis
                alloy = payload.get("alloy", "IN718")
                power = float(payload.get("power_W", 300))
                speed = float(payload.get("speed_mms", 1000))
                layer = float(payload.get("layer_um", 30.0))
                hatch = float(payload.get("hatch_um", 100.0))
                data = run_industrial_fatigue_analysis(alloy, power, speed, layer, hatch)
            elif method == "experimental-validation":         # Phase 10
                payload = request["payload"]
                p = payload.get("params", {})
                m = payload.get("material", {})
                sim = payload.get("simulationResult", {})
                exp = payload.get("experimentalData", {})
                data = validate_experiment(p, m, sim, exp)
            elif method == "modulus-fno":                     # Phase 11
                from lpbf_modulus_fno import predict_part_scale_thermal_history
                payload = request["payload"]
                power_W = payload.get("laserPower_W", 250.0)
                speed_mms = payload.get("scanSpeed_mms", 1000.0)
                preheat_C = payload.get("preheatTemp_C", 25.0)
                hatch_um = payload.get("hatch_um", 100.0)
                layer_um = payload.get("layer_um", 40.0)
                data = predict_part_scale_thermal_history(
                    power_W=power_W, speed_mms=speed_mms, preheat_C=preheat_C, hatch_um=hatch_um, layer_um=layer_um
                )
            elif method == "toolpath-kinematics":             # Phase 12
                payload = request["payload"]
                raw_text = payload.get("content", "")
                fmt = payload.get("format", "gcode").lower()
                power = payload.get("defaultPower_W", 250.0)
                speed = payload.get("defaultSpeed_mms", 1000.0)
                skywriting = payload.get("skywritingEnabled", False)

                if fmt == "cli":
                    vectors = LPBFToolpathParser.parse_cli(raw_text, default_power_W=power, default_speed_mms=speed)
                else:
                    vectors = LPBFToolpathParser.parse_gcode(raw_text, default_power_W=power, default_speed_mms=speed)

                prof = ScannerProfile(
                    accel_max_mms2=payload.get("accelMax_mms2", 40000.0),
                    jump_speed_mms=payload.get("jumpSpeed_mms", 3000.0),
                    laser_on_delay_us=payload.get("laserOnDelay_us", 100.0),
                    laser_off_delay_us=payload.get("laserOffDelay_us", 120.0),
                    mark_delay_us=payload.get("markDelay_us", 200.0),
                    jump_delay_us=payload.get("jumpDelay_us", 350.0),
                    skywriting_enabled=skywriting
                )
                engine = GalvanometerKinematicsEngine(prof)
                data = engine.simulate_toolpath(vectors)
            elif method == "fatigue-fracture":                # Phase 13
                payload = request["payload"]
                alloy = payload.get("alloyName", "Ti-6Al-4V")
                engine = MurakamiFatigueEngine(alloy)
                sqrt_area = float(payload.get("sqrtArea_um", 45.0))
                location = payload.get("location", "internal")
                r_ratio = float(payload.get("stressRatio_R", -1.0))
                calc_type = payload.get("type", "full")

                fatigue_res = engine.calculate_fatigue_limit(sqrt_area, location, r_ratio)
                kt_curve = engine.generate_kitagawa_takahashi_curve(location, r_ratio, n_points=30)
                paris_res = engine.simulate_paris_crack_growth(
                    initial_defect_sqrt_area_um=sqrt_area,
                    cyclic_stress_amplitude_MPa=float(payload.get("stressAmplitude_MPa", 220.0)),
                    stress_ratio_R=r_ratio
                )
                data = {
                    "fatigue_limit": fatigue_res,
                    "kitagawa_takahashi_curve": kt_curve,
                    "paris_crack_growth": paris_res
                }
            elif method == "toolpath-thermal-map":            # Option 1 Toolpath 3D Viz
                payload = request["payload"]
                from lpbf_toolpath_thermal_api import generate_toolpath_thermal_map
                alloy = payload.get("alloy", "IN718")
                power = float(payload.get("power_W", 250))
                speed = float(payload.get("speed_mms", 1000))
                strategy = payload.get("strategy", "chessboard")
                hatch = float(payload.get("hatch_um", 100))
                angle = float(payload.get("angle_deg", 45))
                island = float(payload.get("island_size_mm", 5.0))
                data = generate_toolpath_thermal_map(alloy, power, speed, strategy, hatch, angle, island)

            elif method == "stl-voxelize":                    # Phase 14
                payload = request["payload"]
                stl_text = payload.get("stlContent", "")
                resolution = int(payload.get("resolution", 32))
                defects = payload.get("defects", [])

                if stl_text.strip().startswith("solid"):
                    triangles = STLVoxelizer.parse_ascii_stl(stl_text)
                else:
                    try:
                        raw_bytes = base64.b64decode(stl_text)
                        triangles = STLVoxelizer.parse_binary_stl(raw_bytes)
                    except Exception:
                        triangles = STLVoxelizer.parse_ascii_stl(stl_text)

                data = STLVoxelizer.voxelize(triangles, resolution=resolution, detected_defects=defects)
            elif method == "adaptive-feedforward":            # Phase 15
                payload = request["payload"]
                raw_text = payload.get("content", "")
                fmt = payload.get("format", "gcode").lower()
                power = float(payload.get("defaultPower_W", 280.0))
                speed = float(payload.get("defaultSpeed_mms", 1000.0))
                apply_rot = bool(payload.get("apply67DegRotation", False))
                layer_idx = int(payload.get("layerIndex", 1))

                if fmt == "cli":
                    vectors = LPBFToolpathParser.parse_cli(raw_text, default_power_W=power, default_speed_mms=speed)
                else:
                    vectors = LPBFToolpathParser.parse_gcode(raw_text, default_power_W=power, default_speed_mms=speed)

                prof = ScannerProfile(
                    accel_max_mms2=float(payload.get("accelMax_mms2", 40000.0)),
                    jump_speed_mms=float(payload.get("jumpSpeed_mms", 3000.0))
                )
                mitigator = AdaptiveFeedforwardMitigator(prof)
                data = mitigator.process_toolpath(vectors, apply_67_deg_rotation=apply_rot, layer_index=layer_idx)
            elif method == "multilaser-plume":               # Phase 16
                payload = request["payload"]
                gas_cfg = payload.get("gasFlow", {})
                flow = ShieldGasFlow(
                    gas_type=gas_cfg.get("gasType", "Argon"),
                    velocity_m_s=float(gas_cfg.get("velocity_m_s", 2.0)),
                    angle_deg=float(gas_cfg.get("angle_deg", 0.0))
                )
                plume_cfg = payload.get("plumeParams", {})
                plume_params = PlumeParameters(
                    sigma_plume_mm=float(plume_cfg.get("sigma_plume_mm", 2.5)),
                    decay_length_mm=float(plume_cfg.get("decay_length_mm", 25.0)),
                    base_extinction_coeff=float(plume_cfg.get("base_extinction_coeff", 0.35)),
                    min_collision_dist_mm=float(plume_cfg.get("min_collision_dist_mm", 1.0)),
                    attenuation_hazard_threshold=float(plume_cfg.get("attenuation_hazard_threshold", 0.10))
                )
                engine = MultiLaserPlumeEngine(flow, plume_params)
                l1_vecs = [tuple(v) for v in payload.get("laser1_vectors", [])]
                l2_vecs = [tuple(v) for v in payload.get("laser2_vectors", [])]
                if not l1_vecs:
                    l1_vecs = [(0.0, 0.0, 40.0, 0.0, 300.0, 1000.0)]
                if not l2_vecs:
                    l2_vecs = [(10.0, 1.0, 50.0, 1.0, 300.0, 1000.0)]

                mode = payload.get("mode", "simulate")
                if mode == "optimize":
                    data = engine.optimize_deconfliction_schedule(l1_vecs, l2_vecs)
                else:
                    data = engine.simulate_multitrack_scenarios(l1_vecs, l2_vecs)
            elif method == "thermal-accumulation":           # Phase 17
                payload = request["payload"]
                mat_cfg = payload.get("material", {})
                alloy_name = mat_cfg.get("name")
                alloy_id = resolve_alloy_id(alloy_name)
                if alloy_id is None:
                    raise ValueError("Unknown or missing alloy for thermal accumulation")
                # Shared screening constants; this model uses IR absorptivity.
                props = thermal_props(alloy_id)
                mat = AlloyThermalProperties(
                    name=THERMAL_NAME[alloy_id],
                    density_kg_m3=props["density_kg_m3"],
                    specific_heat_J_kgK=props["specific_heat_J_kgK"],
                    thermal_conductivity_W_mK=props["thermal_conductivity_W_mK"],
                    absorptivity=props["absorptivity_IR"],
                    melting_temp_K=props["liquidus_C"] + 273.15,
                    boiling_temp_K=props["boiling_C"] + 273.15
                )
                hatch_cfg = payload.get("config", {})
                cfg = HatchProcessConfig(
                    laser_power_W=float(hatch_cfg.get("laserPower_W", 280.0)),
                    scan_velocity_mm_s=float(hatch_cfg.get("scanVelocity_mms", 1000.0)),
                    beam_diameter_um=float(hatch_cfg.get("beamDiameter_um", 80.0)),
                    hatch_spacing_um=float(hatch_cfg.get("hatchSpacing_um", 100.0)),
                    track_length_mm=float(hatch_cfg.get("trackLength_mm", 10.0)),
                    num_tracks=int(hatch_cfg.get("numTracks", 10)),
                    bed_temperature_K=float(hatch_cfg.get("bedTemperature_K", 353.15)),
                    turnaround_delay_ms=float(hatch_cfg.get("turnaroundDelay_ms", 0.5))
                )
                engine = MultiTrackThermalEngine(mat)
                mode = payload.get("mode", "simulate")
                if mode == "optimize":
                    allowable_drift = float(payload.get("maxAllowableDrift_K", 120.0))
                    data = engine.optimize_dwell_delays(cfg, max_allowable_drift_K=allowable_drift)
                else:
                    data = engine.simulate_hatch_sequence(cfg)
            elif method == "powder-dem-compaction":          # Phase 18
                payload = request["payload"]
                engine = PowderCompactionEngine(
                    d10_um=float(payload.get("d10_um", 20.0)),
                    d50_um=float(payload.get("d50_um", 35.0)),
                    d90_um=float(payload.get("d90_um", 55.0)),
                    recoater_gap_um=float(payload.get("recoater_gap_um", 60.0)),
                    box_width_um=float(payload.get("box_width_um", 500.0))
                )
                data = engine.generate_psd_deterministic(int(payload.get("num_particles", 500)))

            elif method == "optical-tomography":             # Phase 19
                payload = request["payload"]
                sim = OpticalTomographySimulator(
                    sensor_resolution=(int(payload.get("res_x", 64)), int(payload.get("res_y", 64))),
                    fov_um=float(payload.get("fov_um", 1000.0)),
                    emissivity=float(payload.get("emissivity", 0.35))
                )
                data = sim.simulate_sensor_frame(
                    laser_power_W=float(payload.get("laserPower_W", 280.0)),
                    scan_speed_mm_s=float(payload.get("scanSpeed_mms", 1000.0)),
                    material_k=float(payload.get("material_k", 15.0)),
                    material_alpha=float(payload.get("material_alpha", 5e-6)),
                    T0_K=float(payload.get("T0_K", 300.0))
                )

            elif method == "support-optimization":           # Phase 20
                payload = request["payload"]
                opt = SupportStructureOptimizer(
                    E_modulus_Pa=float(payload.get("E_modulus_Pa", 110e9)),
                    cte_1_K=float(payload.get("cte_1_K", 9e-6)),
                    yield_strength_Pa=float(payload.get("yield_strength_Pa", 950e6)),
                    thermal_k_W_mK=float(payload.get("thermal_k_W_mK", 15.0)),
                    T_melt_K=float(payload.get("T_melt_K", 1928.0)),
                    T_preheat_K=float(payload.get("T_preheat_K", 353.15))
                )
                # Quick response bundling both thermal and mechanical requirements
                heat_input = float(payload.get("heat_input_W", 280.0))
                L_m = float(payload.get("support_length_m", 0.01))
                area_m2 = float(payload.get("layer_area_m2", 0.0001))
                data = {
                    "thermal_area_m2": opt.calculate_thermal_requirement(heat_input, L_m),
                    "mechanical_area_m2": opt.calculate_mechanical_requirement(area_m2)
                }

            elif method == "bayesian-optimizer":
                payload = request["payload"]
                from lpbf_bayesian_optimizer import run_bayesian_optimization
                data = run_bayesian_optimization(
                    alloy_id=payload.get("alloyId", "in718"),
                    param_bounds=payload.get("paramBounds"),
                    n_iter=payload.get("nIterations", 20),
                    n_warmup=payload.get("nWarmup", 5),
                    seed=payload.get("seed", 42)
                )
            elif method == "transient-enthalpy-fdm":         # Phase 21
                payload = request["payload"]
                solver = TransientEnthalpyFDMSolver(
                    nx=int(payload.get("nx", 100)),
                    nz=int(payload.get("nz", 50)),
                    dx=float(payload.get("dx", 2e-6)),
                    dz=float(payload.get("dz", 2e-6))
                )
                # Using 2D method signature
                data = solver.solve_meltpool_cross_section(
                    power_W=float(payload.get("power_W", 250.0)),
                    speed_m_s=float(payload.get("speed_m_s", 0.8)),
                    T_preheat_K=float(payload.get("T_preheat_K", 300.0)),
                    rho=float(payload.get("rho", 4420.0)),
                    cp=float(payload.get("cp", 670.0)),
                    k_solid=float(payload.get("k_solid", 15.0)),
                    k_liquid=float(payload.get("k_liquid", 25.0)),
                    latent_heat_J_kg=float(payload.get("latent_heat_J_kg", 2.9e5)),
                    T_solidus=float(payload.get("T_solidus", 1878.0)),
                    T_liquidus=float(payload.get("T_liquidus", 1928.0)),
                    sim_time_s=float(payload.get("sim_time_s", 5e-4)),
                    dt=float(payload.get("dt", 1e-6))
                )
                # Convert numpy arrays to lists for JSON serialization
                if isinstance(data, dict):
                    for k, v in data.items():
                        if hasattr(v, 'tolist'):
                            data[k] = v.tolist()

            elif method == "transient-3d-gpu":              # Phase 22
                from lpbf_transient_3d_gpu import TransientEnthalpy3DGPU
                payload = request["payload"]
                
                # Safety clamping to prevent GPU OOM
                nx = max(8, min(256, int(payload.get("nx", 64))))
                ny = max(8, min(256, int(payload.get("ny", 64))))
                nz = max(8, min(128, int(payload.get("nz", 32))))

                solver = TransientEnthalpy3DGPU(
                    nx=nx,
                    ny=ny,
                    nz=nz,
                    dx=float(payload.get("dx", 2e-6)),
                    dy=float(payload.get("dy", 2e-6)),
                    dz=float(payload.get("dz", 2e-6))
                )
                toolpath = payload.get("toolpath", {
                    't': [0.0, 100e-6],
                    'x': [32e-6, 96e-6],
                    'y': [32e-6, 32e-6],
                    'p': [float(payload.get("power_W", 200.0)), float(payload.get("power_W", 200.0))]
                })
                
                # Check for empty toolpath arrays
                if not toolpath.get("t") or not toolpath.get("x") or not toolpath.get("y") or not toolpath.get("p"):
                     raise ValueError("Toolpath arrays cannot be empty")

                data = solver.solve_toolpath(
                    toolpath=toolpath,
                    T_preheat_K=float(payload.get("T_preheat_K", 300.0)),
                    rho=float(payload.get("rho", 4420.0)),
                    L_f=float(payload.get("L_f", 2.9e5)),
                    T_solidus=float(payload.get("T_solidus", 1878.0)),
                    T_liquidus=float(payload.get("T_liquidus", 1928.0)),
                    cp_solid=float(payload.get("cp_solid", 670.0)),
                    cp_liquid=float(payload.get("cp_liquid", 730.0)),
                    k_solid=float(payload.get("k_solid", 15.0)),
                    k_liquid=float(payload.get("k_liquid", 25.0))
                )

            elif method == "keyhole-raytracing":            # Phase 26
                from lpbf_keyhole_raytracing import compute_keyhole_raytracing
                data = compute_keyhole_raytracing(request.get("payload", {}))

            else: raise ValueError("Unknown method")
            response = dict(id=request["id"], data=data)
        except Exception as e:
            response = dict(id=request.get("id"), error=str(e))
        print(json.dumps(response, allow_nan=False), flush=True)
    queue.close()


if __name__ == "__main__":
    main()


