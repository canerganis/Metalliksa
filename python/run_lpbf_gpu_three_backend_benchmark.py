"""Conservative fresh-process benchmark for the canonical 40 um IN718 case.

Only solver-call wall time is measured; capture is included. This is not a
kernel, queue, archive, API, UI, or speedup measurement.
"""
from __future__ import annotations

import argparse
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

ROOT = Path(__file__).resolve().parents[1]
CASE = {"mode":"standard", "backend":"reference", "material":"Inconel 718",
        "power_W":60, "speed_mm_s":1200, "mesh_um":40, "maxDt_s":2e-7,
        "layer_um":80, "trackLength_um":200, "cooling_s":2e-5, "dwell_s":0,
        "powderGridPolicy":"layer-conforming"}
BACKENDS = ("cpu", "torch", "warp")
ORDERS = (BACKENDS, ("torch", "warp", "cpu"), ("warp", "cpu", "torch"))
ROUNDS = 5
MAX_TIMEOUT = 7200
TIMING_STAGE = "freshProcessStartupAndImport+firstCudaCall+parityPreflight+warmup+measurements"

def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _canonical(x) -> bytes:
    return json.dumps(x, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

def _positive(v):
    if not math.isfinite(v) or v <= 0: raise ValueError("timing must be finite and positive")
    return float(v)

def _within_relative(actual, expected, tolerance):
    return (math.isfinite(actual) and math.isfinite(expected) and
            abs(actual-expected)/max(abs(expected),1e-30) <= tolerance)

def _within_absolute(actual, expected, tolerance):
    return (math.isfinite(actual) and math.isfinite(expected) and
            abs(actual-expected) <= tolerance)

def _warmup_call(call, synchronize):
    """Time post-preflight warm-up through completed CUDA/Warp work."""
    started = time.perf_counter()
    call()
    synchronize()
    return _positive(time.perf_counter() - started)

def _worker(session: int) -> dict:
    t_start = time.perf_counter()
    import numpy as np
    import torch
    import lpbf_gpu_thermal as tc
    import lpbf_gpu_thermal_warp as wc
    from lpbf_simulation import implementation_fingerprint
    from test_lpbf_gpu_three_backend_parity import CASE as CANONICAL, _relative_field_errors
    t_imports = time.perf_counter() - t_start

    t_cuda_probe_start = time.perf_counter()
    if CANONICAL != CASE: raise RuntimeError("canonical input identity changed")
    if not torch.cuda.is_available() or not wc.wp or not wc.wp.is_cuda_available():
        raise RuntimeError("CUDA unavailable; refusing benchmark")
    device="cuda:0"; prop=torch.cuda.get_device_properties(device)
    t_first_cuda = time.perf_counter() - t_cuda_probe_start

    order=ORDERS[session]
    def solve(label, capture):
        if label == "cpu": return tc._run_cpu_with_final(CASE, include_final_state=capture)
        if label == "torch": return tc.run_gpu(CASE, device, capture_final=capture, use_cuda_source=False)
        return wc.run_warp(CASE, device, capture_final=capture, capture_pilot_state=capture)

    # A full canonical parity pass in this fresh process; discard states locally.
    t_preflight_start = time.perf_counter()
    cpu=solve("cpu", True); cpu_result, cpu_state=cpu[0], cpu[-1]
    torch_result, torch_state=solve("torch", True)
    warp_pack=solve("warp", True); warp_result, warp_state=warp_pack[0], warp_pack[-1]
    results=(cpu_result,torch_result,warp_result); states=(cpu_state,torch_state,warp_state)
    def result_model(r, label):
        return (r["coreContract"]["modelId"] if label == "cpu"
                else r["solver"]["modelId"])
    if not all(r["settings"] == cpu_result["settings"] and
       r["material"]["materialId"] == "in718" and
       r["material"]["materialRevisionSha256"] == cpu_result["material"]["materialRevisionSha256"] and
       result_model(r, label) == cpu_result["coreContract"]["modelId"] and
       r["discretization"]["mesh_m"] == cpu_result["discretization"]["mesh_m"] and
       r["discretization"]["cells"] == cpu_result["discretization"]["cells"] and
       r["discretization"]["steps"] == cpu_result["discretization"]["steps"] and
       math.isfinite(r["energyBalance"]["relativeError"]) and
       r["energyBalance"]["relativeError"] <= .01
       for label, r in zip(BACKENDS, results)):
        raise RuntimeError("model/material/grid/accepted-work or energy parity gate failed")
    for state in states[1:]:
        np.testing.assert_array_equal(state["accepted_dt_s"], cpu_state["accepted_dt_s"])
        np.testing.assert_array_equal(state["coordinates_m"], cpu_state["coordinates_m"])
        np.testing.assert_array_equal(state["density_kg_m3"], cpu_state["density_kg_m3"])
        if (state["time_s"] != cpu_state["time_s"] or
            state["initial_temperature_K"] != cpu_state["initial_temperature_K"] or
            state["cell_volume_m3"] != cpu_state["cell_volume_m3"]):
            raise RuntimeError("final state time/initial-temperature/cell-volume identity mismatch")
        temperature_rise=cpu_state["temperature_K"]-cpu_state["initial_temperature_K"]
        for key, baseline in (("temperature_K", cpu_state["temperature_K"]),
                              ("enthalpy_J_m3", cpu_state["enthalpy_J_m3"])):
            kwargs={"baseline":temperature_rise} if key == "temperature_K" else {}
            l2, linf=_relative_field_errors(baseline, state[key], **kwargs)
            if max(l2,linf) > .01: raise RuntimeError(f"{key} parity gate failed")
    for label, result in zip(BACKENDS[1:], results[1:]):
        for quantity in ("input_J", "losses_J", "stored_J"):
            expected=cpu_result["energyBalance"][quantity]
            actual=result["energyBalance"][quantity]
            if not _within_relative(actual, expected, .01):
                raise RuntimeError(f"{label} {quantity} parity gate failed")
        expected=cpu_result["metrics"]["peakTemperature_K"]
        actual=result["metrics"]["peakTemperature_K"]
        if not _within_relative(actual, expected, .01):
            raise RuntimeError(f"{label} peak-temperature parity gate failed")
        for metric in ("width_um", "depth_um", "length_um"):
            actual=result["metrics"][metric]; expected=cpu_result["metrics"][metric]
            if not _within_absolute(actual, expected, 40.0):
                raise RuntimeError(f"{label} {metric} geometry-quantization gate failed (40 um)")
        expected=cpu_result["metrics"]["volume_um3"]
        actual=result["metrics"]["volume_um3"]
        if (not math.isfinite(expected) or expected <= 0 or
            not _within_relative(actual, expected, .01)):
            raise RuntimeError(f"{label} melt-volume parity gate failed")
    t_preflight = time.perf_counter() - t_preflight_start
    del cpu, torch_state, warp_pack, warp_state, states
    samples={k:[] for k in BACKENDS}; warm={}; timings=[]; cuda_events={k:[] for k in ("torch", "warp")}
    for label in order:
        sync=(lambda: torch.cuda.synchronize(device)) if label != "cpu" else (lambda: None)
        warm[label]=_warmup_call(lambda: solve(label, True), sync)
    for round_no in range(ROUNDS):
        for label in order:
            evt_start, evt_end = None, None
            if label != "cpu":
                torch.cuda.synchronize(device)
                evt_start = torch.cuda.Event(enable_timing=True)
                evt_end = torch.cuda.Event(enable_timing=True)
                evt_start.record()
            t=time.perf_counter(); result=solve(label, True)
            cuda_ms = None
            if label != "cpu":
                evt_end.record()
                torch.cuda.synchronize(device)
                cuda_ms = _positive(evt_start.elapsed_time(evt_end))
                cuda_events[label].append(cuda_ms)
            elapsed=_positive(time.perf_counter()-t)
            samples[label].append(elapsed)
            meas = {"round":round_no+1,"backend":label,"order":list(order),"solveAndFinalCaptureWall_s":elapsed}
            if cuda_ms is not None:
                meas["cudaEventWall_ms"] = cuda_ms
            timings.append(meas)
    files=[Path(tc.__file__),Path(wc.__file__),Path(__import__("lpbf_simulation").__file__),
           Path(__file__).resolve(),Path(__import__("test_lpbf_gpu_three_backend_parity").__file__).resolve()]
    stages = {
        "processStartupAndImport_s": _positive(t_imports),
        "firstCudaCall_s": _positive(t_first_cuda),
        "parityPreflight_s": _positive(t_preflight),
        "warmupWall_s": warm,
        "cudaEventStages_ms": {
            k: {"median_ms": statistics.median(v), "min_ms": min(v), "max_ms": max(v)}
            for k, v in cuda_events.items() if v
        },
        "unmeasured": {
            "queueWait": "not-measured",
            "apiHandling": "not-measured",
            "archivePersistence": "not-measured",
            "uiWall": "not-measured"
        }
    }
    return {"session":session+1,"pid":os.getpid(),"order":list(order),
      "stages":stages,"warmupWall_s":warm,"samples":samples,"measurements":timings,
      "identity":{"inputSha256":_hash(_canonical(CASE)),"sourceSha256":{p.name:_hash(p.read_bytes()) for p in files},
      "implementationFingerprint":implementation_fingerprint(),"materialId":cpu_result["material"]["materialId"],
      "materialRevisionSha256":cpu_result["material"]["materialRevisionSha256"],
      "modelId":cpu_result["coreContract"]["modelId"],"cells":cpu_result["discretization"]["cells"],
      "acceptedSteps":cpu_result["discretization"]["steps"],"device":prop.name,
      "computeCapability":f"{prop.major}.{prop.minor}","python":platform.python_version(),
      "torch":str(torch.__version__),"cudaRuntime":str(torch.version.cuda),"warp":str(wc.wp.__version__)}}

def _aggregate(sessions):
    if (len(sessions)!=3 or
        any(s.get("session") != i+1 or s.get("order") != list(ORDERS[i])
            for i,s in enumerate(sessions))):
        raise ValueError("requires exactly three sessions with frozen rotated order")
    identities=[s["identity"] for s in sessions]
    if any(i != identities[0] for i in identities[1:]): raise ValueError("session code/input/device identity mismatch")
    summary={}
    for backend in BACKENDS:
        values=[]
        for i, s in enumerate(sessions):
            per_session=s["samples"].get(backend, [])
            if len(per_session)!=ROUNDS or any(not math.isfinite(v) or v <= 0 for v in per_session):
                raise ValueError(f"requires exactly {ROUNDS} finite positive samples per backend/session")
            values.extend(per_session)
        for i,s in enumerate(sessions):
            measurements=s.get("measurements", [])
            expected=[(rnd, label) for rnd in range(1,ROUNDS+1) for label in ORDERS[i]]
            actual=[(m.get("round"),m.get("backend")) for m in measurements]
            if len(measurements)!=ROUNDS*len(BACKENDS) or actual!=expected:
                raise ValueError("measurement records must match the rotated round/order protocol")
            by_backend={k:[] for k in BACKENDS}
            for m in measurements:
                value=m.get("solveAndFinalCaptureWall_s")
                if not isinstance(value,(int,float)) or not math.isfinite(value) or value <= 0:
                    raise ValueError("measurement duration must be finite and positive")
                by_backend[m["backend"]].append(float(value))
            if any(by_backend[k] != list(map(float,s["samples"][k])) for k in BACKENDS):
                raise ValueError("measurement values must match per-backend sample arrays")
        cuda_vals = []
        if backend != "cpu":
            for s in sessions:
                for m in s.get("measurements", []):
                    if m.get("backend") == backend and "cudaEventWall_ms" in m:
                        cuda_vals.append(float(m["cudaEventWall_ms"]))
        backend_summary = {"median_s":statistics.median(values),"min_s":min(values),"max_s":max(values),"range_s":max(values)-min(values),"sampleCount":len(values)}
        if cuda_vals:
            backend_summary["cudaEvent_ms"] = {"median_ms": statistics.median(cuda_vals), "min_ms": min(cuda_vals), "max_ms": max(cuda_vals), "sampleCount": len(cuda_vals)}
        summary[backend] = backend_summary
    return {"schemaVersion":1,"benchmarkId":"lpbf-cpu-torch-warp-fresh-process-wall-v1",
      "timingStage":TIMING_STAGE,
      "sessionWallDefinition":"complete child subprocess wall duration; startup/import/parity preflight/warmup/measurements combined and not separated",
      "scope":{"measured":"solver call plus final-state capture wall time",
       "parity":"final-state fields; input/loss/stored energy and peak temperature within 1%; width/depth/length within 40 um geometry cell quantization; volume within 1%",
       "geometryCellQuantization_um":40,"finalStateFieldGate":True,
       "cudaEventInstrumentation":{"status":"enabled","measuredBackends":["torch","warp"],"unit":"milliseconds"},
       "unmeasuredStages":{
           "queueWait":"not-measured",
           "apiHandling":"not-measured",
           "archivePersistence":"not-measured",
           "uiWall":"not-measured"
       },
       "excludedTiming":["queue","API","archive/persistence","UI"]},
      "roundsPerBackendPerSession":ROUNDS,"totalSamplesPerBackend":ROUNDS*len(sessions),"sessions":sessions,"summary":summary}

def run(output: Path, timeout: int=MAX_TIMEOUT):
    if not 1 <= timeout <= MAX_TIMEOUT: raise ValueError("timeout must be in [1, 7200]")
    sessions=[]
    for i in range(3):
        start=time.perf_counter()
        proc=subprocess.run([sys.executable,str(Path(__file__).resolve()),"--worker",str(i)],cwd=ROOT,
            capture_output=True,text=True,timeout=timeout)
        wall=time.perf_counter()-start
        if proc.returncode: raise RuntimeError(f"session {i+1} refused/failed: {proc.stderr[-2000:]}")
        row=json.loads(proc.stdout.strip().splitlines()[-1]); row["sessionWall_s"]=_positive(wall)
        sessions.append(row)
    output.write_text(json.dumps(_aggregate(sessions),indent=2,allow_nan=False)+"\n",encoding="utf-8")

def main(argv=None):
    ap=argparse.ArgumentParser(); ap.add_argument("--output",type=Path,default=ROOT/"lpbf_three_backend_benchmark.json")
    ap.add_argument("--timeout-seconds",type=int,default=MAX_TIMEOUT); ap.add_argument("--worker",type=int,choices=range(3))
    a=ap.parse_args(argv)
    if a.worker is not None: print(json.dumps(_worker(a.worker),allow_nan=False,separators=(",",":")))
    else: run(a.output,a.timeout_seconds)

if __name__=="__main__": main()
