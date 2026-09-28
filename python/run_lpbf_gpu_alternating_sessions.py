"""Run the frozen Torch/Warp alternating timing protocol in fresh processes.

This wrapper records solver wall time only. It does not measure field capture,
queueing, persistence, UI latency, or experimental validity.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
from contextlib import redirect_stdout
from io import StringIO


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = ROOT / "docs" / "LPBF_GPU_ALTERNATING_BENCHMARK_2026-09-28.json"
SOURCE_REPORT = ROOT / "docs" / "LPBF_GPU_BACKEND_ALTERNATING_BENCHMARK_2026-09-27.json"
DEFAULT_OUTPUT = ROOT / "docs" / "LPBF_GPU_ALTERNATING_BENCHMARK_2026-09-28_FRESH.json"
EXPECTED_CELLS = 73568
EXPECTED_STEPS = 934
ALTERNATING_ORDER = ["torch", "warp", "warp", "torch", "torch", "warp"]
EXCLUDED_SCOPE = ["final-field capture", "queue", "archive/persistence", "UI"]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _read_baseline(path: Path) -> dict:
    baseline = json.loads(path.read_text(encoding="utf-8"))
    if baseline.get("schemaVersion") != 1 or baseline.get("benchmarkId") != "lpbf-torch-warp-alternating-solver-wall-v1":
        raise ValueError("Unsupported or malformed frozen benchmark baseline")
    source = baseline.get("input", {})
    settings = source.get("settings", {})
    if source.get("materialId") != "in718" or source.get("estimatedProperties") is not True:
        raise ValueError("Baseline material identity is not the expected estimated IN718 snapshot")
    if source.get("resolvedWorkPerTrial") != {"cells": EXPECTED_CELLS, "acceptedSteps": EXPECTED_STEPS}:
        raise ValueError("Baseline work count differs from the frozen case")
    required_settings = {
        "mode", "backend", "power_W", "speed_mm_s", "mesh_um", "maxDt_s",
        "trackLength_um", "layer_um", "cooling_s", "dwell_s", "powderGridPolicy",
    }
    if set(settings) != required_settings or settings.get("backend") != "reference":
        raise ValueError("Baseline settings are incomplete or no longer the fixed reference case")
    for name in ("requestSha256", "implementationFingerprint", "warpModuleSha256"):
        value = source.get(name)
        if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError(f"Invalid baseline {name}")
    # The historical field named requestSha256 is the CPU-reference case hash,
    # not a digest of the later fully validated GPU request/settings object.
    source_report = json.loads(SOURCE_REPORT.read_text(encoding="utf-8"))
    legacy_case = {**settings, "material": "Inconel 718"}
    legacy_case_hash = _sha256(_json_bytes(legacy_case))
    if (source_report.get("case") != legacy_case
            or source_report.get("caseSha256") != legacy_case_hash
            or source.get("requestSha256") != legacy_case_hash):
        raise ValueError("Frozen baseline does not match its historical source report case identity")
    return baseline


def _version_tuple(value, label):
    if not isinstance(value, tuple) or len(value) != 2 or any(type(x) is not int for x in value):
        raise RuntimeError(f"Unavailable {label} version")
    return f"{value[0]}.{value[1]}"


def _worker(baseline_path: Path, session: int, preflight_only: bool = False) -> dict:
    baseline = _read_baseline(baseline_path)
    expected = baseline["input"]
    expected_settings = expected["settings"]

    # Keep all imported runtime chatter away from the one-line worker protocol.
    with redirect_stdout(StringIO()):
        from lpbf_gpu_thermal import _python_json
        from lpbf_gpu_warp_pilot import validate_warp_pilot_request
        from lpbf_gpu_thermal_warp import benchmark_alternating, wp
        from lpbf_simulation import implementation_fingerprint
        import torch

        device = "cuda:0"
        raw = {
            "jobType": "gpu-thermal-pilot",
            "executionEngine": "warp",
            **expected_settings,
            "backend": device,
            "material": "Inconel 718",
            "preheat_C": 80,
        }
        request, material = validate_warp_pilot_request(raw)
        reference_request = {key: value for key, value in request.items()
                             if key not in ("jobType", "executionEngine")}
        reference_request["backend"] = "reference"
        validated_settings = {key: reference_request.get(key) for key in expected_settings}
        baseline_settings_sha = _sha256(_json_bytes(expected_settings))
        validated_settings_sha = _sha256(_json_bytes(validated_settings))
        if validated_settings != expected_settings:
            raise RuntimeError(f"session {session}: validated settings differ from frozen baseline")
        if material.get("materialId") != "in718":
            raise RuntimeError(f"session {session}: resolved material is not canonical IN718")
        material_revision = material.get("materialRevisionSha256")
        if not isinstance(material_revision, str) or len(material_revision) != 64:
            raise RuntimeError(f"session {session}: material revision identity unavailable")

        fingerprint = implementation_fingerprint()
        runner_hash = _sha256(Path(__file__).resolve().read_bytes())
        if fingerprint != expected["implementationFingerprint"]:
            raise RuntimeError(f"session {session}: implementation fingerprint differs from frozen baseline")
        warp_path = Path(__import__("lpbf_gpu_thermal_warp").__file__).resolve()
        warp_hash = _sha256(warp_path.read_bytes())
        if warp_hash != expected["warpModuleSha256"]:
            raise RuntimeError(f"session {session}: Warp module hash differs from frozen baseline")

        if not torch.cuda.is_available() or torch.cuda.device_count() < 1:
            raise RuntimeError(f"session {session}: CUDA device unavailable")
        props = torch.cuda.get_device_properties(device)
        warp_device = wp.get_device(device)
        cc = f"{props.major}.{props.minor}"
        if (warp_device.name != props.name or f"{warp_device.arch // 10}.{warp_device.arch % 10}" != cc):
            raise RuntimeError(f"session {session}: Torch/Warp device identity mismatch")
        toolkit = _version_tuple(wp.get_cuda_toolkit_version(), "Warp CUDA toolkit")
        driver = _version_tuple(wp.get_cuda_driver_version(), "CUDA driver")
        runtime = {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "torch": str(torch.__version__),
            "torchCudaRuntime": str(torch.version.cuda),
            "warp": str(wp.__version__),
            "warpCudaToolkit": toolkit,
            "cudaDriver": driver,
        }
        device_identity = {
            "name": str(props.name),
            "memoryGiB": round(props.total_memory / (1024 ** 3), 3),
            "computeCapability": cc,
            "selected": device,
        }
        expected_device = baseline.get("device", {})
        if (device_identity["name"] != expected_device.get("gpu")
                or device_identity["computeCapability"] != expected_device.get("computeCapability")
                or round(device_identity["memoryGiB"]) != expected_device.get("memoryGiB")
                or ("torch" in expected_device and runtime["torch"] != expected_device["torch"])
                or ("cudaRuntime" in expected_device
                    and runtime["torchCudaRuntime"] != expected_device["cudaRuntime"])
                or runtime["warp"] != expected_device.get("warp")
                or runtime["warpCudaToolkit"] != expected_device.get("cudaToolkit")
                or runtime["cudaDriver"] != expected_device.get("driver")):
            raise RuntimeError(f"session {session}: runtime/device identity differs from frozen baseline")

    if preflight_only:
        return {
            "status": "preflight-pass-no-solve",
            "legacyCaseIdentity": {
                "meaning": "CPU-reference case hash recorded as requestSha256 by the source report",
                "sha256": expected["requestSha256"],
            },
            "validatedSettingsIdentity": {
                "meaning": "digest of the exact fixed settings after current GPU request validation, normalized to backend=reference",
                "baselineSha256": baseline_settings_sha,
                "validatedSha256": validated_settings_sha,
            },
            "validatedRequestSha256": _sha256(_python_json(reference_request).encode("utf-8")),
            "benchmarkRunnerSha256": runner_hash,
            "materialId": material["materialId"],
            "materialRevisionSha256": material_revision,
            "implementationFingerprint": fingerprint,
            "warpModuleSha256": warp_hash,
            "device": device_identity,
            "runtime": runtime,
            "expectedCells": EXPECTED_CELLS,
            "expectedAcceptedSteps": EXPECTED_STEPS,
            "solverInvoked": False,
        }

    # benchmark_alternating itself performs exactly one warm-up per backend
    # and enforces exactly three measured trials per backend.
    # The alternating helper compares reference-validated Torch and Warp GPU
    # executors. `raw` above is only the explicit CUDA queue request used for
    # identity/device preflight; solver inputs must retain backend=reference.
    with redirect_stdout(StringIO()):
        timings = benchmark_alternating(reference_request, device=device, repeats=3)

    checked = {}
    for engine in ("torch", "warp"):
        entries = timings.get(engine, {}).get("trials")
        if not isinstance(entries, list) or len(entries) != 3:
            raise RuntimeError(f"session {session}: {engine} did not return exactly three trials")
        raw_trials = []
        for entry in entries:
            runtime_s = entry.get("runtime_s")
            cells, steps = entry.get("cells"), entry.get("steps")
            if (type(runtime_s) not in (int, float) or not math.isfinite(runtime_s) or runtime_s <= 0
                    or cells != EXPECTED_CELLS or steps != EXPECTED_STEPS):
                raise RuntimeError(f"session {session}: {engine} work identity/count mismatch")
            raw_trials.append({"runtime_s": float(runtime_s), "cells": cells, "acceptedSteps": steps})
        values = [row["runtime_s"] for row in raw_trials]
        median = statistics.median(values)
        checked[engine] = {
            "trials": raw_trials,
            "median_s": median,
            "mad_s": statistics.median(abs(value - median) for value in values),
            "spread_s": max(values) - min(values),
        }

    identity = {
        "legacyCaseSha256": expected["requestSha256"],
        "validatedSettingsSha256": validated_settings_sha,
        "validatedRequestSha256": _sha256(_python_json(reference_request).encode("utf-8")),
        "benchmarkRunnerSha256": runner_hash,
        "materialId": "in718",
        "materialRevisionSha256": material_revision,
        "implementationFingerprint": fingerprint,
        "warpModuleSha256": warp_hash,
        "device": device_identity,
        "runtime": runtime,
        "cellsPerTrial": EXPECTED_CELLS,
        "acceptedStepsPerTrial": EXPECTED_STEPS,
    }
    return {
        "session": session,
        "processId": os.getpid(),
        "identity": identity,
        "protocol": {"warmupsPerBackend": 1, "alternatingOrder": ALTERNATING_ORDER,
                     "measuredTrialsPerBackend": 3, "captureFinal": False,
                     "useCudaSource": False},
        "torch": checked["torch"],
        "warp": checked["warp"],
        "torchOverWarp": checked["torch"]["median_s"] / checked["warp"]["median_s"],
    }


def _worker_entry(args) -> int:
    try:
        result = _worker(Path(args.baseline), args.worker_session)
        print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "aborted", "session": args.worker_session,
                          "errorType": type(exc).__name__, "error": str(exc)},
                         sort_keys=True, separators=(",", ":")), file=sys.stderr)
        return 2


def _aggregate(sessions: list[dict]) -> dict:
    common_identity = sessions[0]["identity"]
    for row in sessions[1:]:
        if row["identity"] != common_identity:
            raise RuntimeError("session identities differ; refusing cross-session aggregation")
    aggregate = {}
    for engine in ("torch", "warp"):
        values = [trial["runtime_s"] for row in sessions for trial in row[engine]["trials"]]
        median = statistics.median(values)
        aggregate[engine] = {
            "trialCount": len(values), "median_s": median,
            "mad_s": statistics.median(abs(value - median) for value in values),
            "spread_s": max(values) - min(values),
            "sessionMedians_s": [row[engine]["median_s"] for row in sessions],
        }
    return aggregate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sessions", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--preflight", action="store_true",
                        help="validate frozen input, implementation and runtime identities without invoking either solver")
    parser.add_argument("--worker-session", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.worker_session is not None:
        return _worker_entry(args)
    if args.preflight:
        result = _worker(args.baseline.resolve(), 0, preflight_only=True)
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        return 0
    if args.sessions < 3:
        parser.error("--sessions must be at least 3 for independent-process evidence")
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")
    baseline_path = args.baseline.resolve()
    output_path = args.output.resolve()
    baseline = _read_baseline(baseline_path)
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing report: {output_path}")

    started = dt.datetime.now(dt.timezone.utc)
    wall_started = time.perf_counter()
    sessions = []
    for session in range(1, args.sessions + 1):
        command = [sys.executable, str(Path(__file__).resolve()), "--baseline", str(baseline_path),
                   "--worker-session", str(session)]
        try:
            completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True,
                                       timeout=args.timeout_seconds, check=False)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"session {session} timed out; no aggregate report was written") from None
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or f"exit {completed.returncode}"
            raise RuntimeError(f"session {session} aborted; no aggregate report was written: {detail}")
        try:
            row = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"session {session} returned invalid output; no aggregate report was written") from exc
        if row.get("session") != session:
            raise RuntimeError(f"session {session} response identity mismatch; no report was written")
        sessions.append(row)

    aggregate = _aggregate(sessions)
    report = {
        "schemaVersion": 1,
        "benchmarkId": "lpbf-torch-warp-alternating-independent-process-sessions-v1",
        "status": "completed",
        "scope": "Warm, alternating Torch/Warp solver wall time only",
        "excludes": EXCLUDED_SCOPE,
        "experimentalValidation": False,
        "baseline": baseline_path.relative_to(ROOT).as_posix() if baseline_path.is_relative_to(ROOT) else str(baseline_path),
        "baselineIdentity": baseline["input"],
        "startedAtUtc": started.isoformat(),
        "completedAtUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "wallSecondsIncludingFreshProcessStartup": time.perf_counter() - wall_started,
        "sessionCount": args.sessions,
        "identityAggregationPolicy": "all request, material revision, implementation, device and runtime identities must match exactly",
        "sessions": sessions,
        "aggregate": aggregate,
        "interpretation": {
            "speedRatioMedianOfSessionMeasurementsTorchOverWarp": statistics.median(
                row["torchOverWarp"] for row in sessions),
            "endToEndSpeedup": "unmeasured",
            "kernelAttribution": "unavailable; this timing protocol does not profile device kernels",
            "numericalParity": "not measured by this timing protocol",
            "experimentalValidation": False,
        },
    }
    payload = (json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation occurs only after all sessions and identity gates pass.
    created_output = False
    try:
        stream = output_path.open("xb")
        created_output = True
        with stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        # Remove only the file created by this invocation if persistence failed.
        if created_output:
            try:
                output_path.unlink()
            except FileNotFoundError:
                pass
        raise
    print(json.dumps({"status": "completed", "sessions": args.sessions,
                      "report": str(output_path), "sha256": _sha256(payload)},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ABORTED: {exc}", file=sys.stderr)
        raise SystemExit(2)
