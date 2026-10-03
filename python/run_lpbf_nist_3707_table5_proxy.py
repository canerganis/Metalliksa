"""One frozen, resource-bounded thermal proxy; default is preflight.

Published etched/solidified geometry and simulated liquidus geometry have
different operators. Numerical differences here are diagnostic, never a
matched experimental residual, calibration fit, or independent validation.
"""
import argparse
import contextlib
import datetime
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path
from unittest.mock import patch

import numpy as np

import lpbf_simulation as solver
from lpbf_core_physics import calculate_mesh_domain, integrated_source, scan_segments

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/LPBF_NIST_3707_TABLE5_PROXY_2026-10-02_PROTOCOL.json"
OUTPUT = ROOT / "docs/LPBF_NIST_3707_TABLE5_PROXY_2026-10-02.json"
TABLE = ROOT / "data/benchmark/nist-access-review-2026-10-02/mds2-3707-single-track-table5.json"
ID = "nist-3707-table5-finite-length-locality-20um-v1"
INPUTS = dict(mode="standard", backend="reference", study="none", material="Inconel 718",
              surfaceMode="bare-plate", barePlateGeometry="rectangular-corridor",
              power_W=285.0, speed_mm_s=960.0, beamDiameter_um=72.0,
              trackLength_um=8000.0, corridorWidth_um=432.0, mesh_um=20.0,
              maxDt_s=1e-6, sourcePenetration_um=80.0, absorptivity=.35,
              preheat_C=80.0, cooling_s=0.0, dwell_s=0.0, tracks=1, layers=1,
              scanAngle_deg=0.0, timeout_s=600.0)
LIMITS = dict(maximumCells=200000, maximumSteps=75000,
              maximumCellSteps=1359600000, maximumRssBytes=536870912,
              maximumWallTime_s=600.0, maximumReportBytes=2000000)
CASE_OVERRIDES = [{"trackLength_um": length, "mesh_um": math.nextafter(20.0, math.inf)}
                  for length in (1004.0, 1604.0)]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_bytes())


def validate_protocol(protocol):
    fixed = {"schemaVersion": 1, "protocolId": ID, "inputs": INPUTS,
             "limits": LIMITS, "caseOverrides": CASE_OVERRIDES,
             "validationStatus": "unvalidated",
             "experimentalValidation": False, "operatorMismatch": True,
             "fittingOrTuning": False,
             "tableFile": TABLE.relative_to(ROOT).as_posix(),
             "output": OUTPUT.relative_to(ROOT).as_posix()}
    if not isinstance(protocol, dict) or set(protocol) != set(fixed) | {
            "tableSha256", "implementationSha256", "priorFullLengthReportSha256",
            "assumptions", "scope"}:
        raise ValueError("Unexpected proxy protocol schema")
    for key, expected in fixed.items():
        if protocol[key] != expected or (type(expected) is bool and type(protocol[key]) is not bool):
            raise ValueError(f"Frozen proxy protocol differs: {key}")
    for key in ("tableSha256", "implementationSha256", "priorFullLengthReportSha256"):
        value = protocol[key]
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError(f"Invalid hash: {key}")
    for path in (TABLE, OUTPUT, PROTOCOL):
        if not path.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError("Proxy path escapes repository")
        for component in (path, *path.parents):
            if component == ROOT:
                break
            if component.is_symlink() or (hasattr(component, "is_junction") and component.is_junction()):
                raise ValueError("Proxy path has symlink or junction")


def check_resources(cells, steps, rss, wall, limits=LIMITS, *, cellsteps=None):
    values = ((cells, "maximumCells"), (steps, "maximumSteps"),
              (cells*steps if cellsteps is None else cellsteps, "maximumCellSteps"), (rss, "maximumRssBytes"),
              (wall, "maximumWallTime_s"))
    if any(not math.isfinite(value) or value < 0 for value, _ in values):
        raise ValueError("Invalid resource measurement")
    for value, key in values:
        if value > limits[key]:
            raise RuntimeError(f"Proxy resource budget exceeded: {key} ({value})")


def preflight(require_fresh=False):
    protocol_bytes = PROTOCOL.read_bytes()
    protocol = json.loads(protocol_bytes)
    validate_protocol(protocol)
    prior = None
    if OUTPUT.exists():
        prior_bytes = OUTPUT.read_bytes()
        prior = json.loads(prior_bytes)
        if require_fresh and (digest(prior_bytes) != protocol["priorFullLengthReportSha256"]
                or prior.get("stage") != "preflight-denied"
                or prior.get("runtimeWork", {}).get("attemptedSteps") != 0):
            raise FileExistsError("Locality report already exists or prior full-length report differs; no overwrite")
    if digest(TABLE.read_bytes()) != protocol["tableSha256"]:
        raise ValueError("Table transcription hash differs")
    if solver.implementation_fingerprint() != protocol["implementationSha256"]:
        raise ValueError("Thermal implementation hash differs")
    table = read_json(TABLE)
    process = table["specimen_and_process"]
    for key, value in {"laser_power_W": 285, "scan_speed_mm_s": 960,
                       "gaussian_spot_diameter_um": 72,
                       "track_length_approx_mm": 8}.items():
        if process[key] != value:
            raise ValueError(f"Published fixed condition differs: {key}")
    if table["dataset_id"] != "mds2-3707" or table["source_document"]["table"] != 5:
        raise ValueError("Unexpected published reference")
    cases = [_case_preflight({**protocol["inputs"], **override}) for override in CASE_OVERRIDES]
    for case in cases:
        domain = case["domain"]
        if domain["nx"] % 2 != 1 or abs(case["midpointPlane_m"]) > 1e-15:
            raise ValueError("Locality case midpoint is not a cell centre")
        if abs(domain["dx"]-20e-6) > 1e-16:
            raise ValueError("Locality cases must retain effective 20 um resolution")
    if any(cases[0]["domain"][k] != cases[1]["domain"][k] for k in ("ny", "nz")):
        raise ValueError("Locality cases must share transverse/depth cell counts")
    estimated_steps = sum(case["heuristicEstimatedSteps"] for case in cases)
    estimated_work = sum(case["heuristicEstimatedCellSteps"] for case in cases)
    max_cells = max(case["cells"] for case in cases)
    reasons = []
    for value, key in ((max_cells, "maximumCells"), (estimated_steps, "maximumSteps"),
                       (estimated_work, "maximumCellSteps")):
        if value > LIMITS[key]:
            reasons.append(f"Initial-source heuristic exceeds {key}: {value} > {LIMITS[key]}")
    allocation_estimate = max_cells*8*100
    if allocation_estimate > LIMITS["maximumRssBytes"]:
        reasons.append("100-double-arrays memory estimate exceeds RSS cap")
    if estimated_work/3e6 > LIMITS["maximumWallTime_s"]:
        reasons.append("Slow end of heuristic 3 to 8 million cellsteps/s range exceeds wall-time cap")
    return dict(protocol=protocol, protocolSha256=digest(protocol_bytes), cases=cases,
                totalHeuristicEstimatedSteps=estimated_steps,
                totalHeuristicEstimatedCellSteps=estimated_work,
                estimatedFullArrayBytes=allocation_estimate,
                heuristicWallTimeRange_s=[estimated_work/8e6, estimated_work/3e6],
                runtimeEstimateAssumption="3 to 8 million cellsteps/s; not a measured runtime for these cases",
                executionEligible=not reasons, executionDenialReasons=reasons,
                resourceEstimateIsGuaranteed=False, assumptions=protocol["assumptions"],
                publishedSummary=table["published_summary"],
                priorFullLengthPreflight=prior if prior and prior.get("stage") == "preflight-denied" else None)


def _case_preflight(raw):
    settings, material = solver.validate(raw)
    domain = calculate_mesh_domain(settings)
    cells = domain["nx"]*domain["ny"]*domain["nz"]
    segments, end = scan_segments(settings)
    minimum_steps = math.ceil(end/settings["maxDt_s"])
    dx = domain["dx"]
    axis = (np.arange(domain["nx"])+.5)*dx-domain["span"]/2
    y = (np.arange(domain["ny"])+.5)*dx-domain["ny"]*dx/2
    z = (np.arange(domain["nz"])+.5)*dx-domain["substrate_depth"]
    thermal = solver.thermal_si_inputs(settings, material)
    source, capture = integrated_source(axis, z, dx, segments[0], 0.0, settings["maxDt_s"],
        0.0, domain["radius"], settings["sourcePenetration_um"]*1e-6,
        thermal["absorbed_power_W"], axis_y=y)
    solver.require_source_capture(capture, solver.MINIMUM_SOURCE_CAPTURE_FRACTION)
    t0 = thermal["preheat_K"]
    capacity = float(solver.property_at(material, t0, 1)*solver.property_at(material, t0, 3))
    estimate_dt = min(settings["maxDt_s"], .95*25*capacity/float(source.max()))
    estimated_steps = math.ceil(end/estimate_dt)
    temperatures = np.linspace(t0, material["boiling_K"], 10000)
    alpha = float(np.max(solver.property_at(material, temperatures, 2)/(
        solver.property_at(material, temperatures, 1)*solver.property_at(material, temperatures, 3))))
    return dict(rawInputs=raw, settings=settings, domain=domain,
                cells=cells, end_s=end, minimumStepsByMaxDt=minimum_steps,
                initialSourceCapEstimatedDt_s=estimate_dt,
                heuristicEstimatedSteps=estimated_steps,
                heuristicEstimatedCellSteps=cells*estimated_steps,
                initialSourceCaptureFraction=capture,
                beamDiameterCells=settings["beamDiameter_um"]*1e-6/dx,
                midpointPlane_m=float(axis[int(np.argmin(np.abs(axis)))]),
                centreSourceCrossingTime_s=settings["trackLength_um"]*1e-6/(2*thermal["speed_m_s"]),
                modelMaximumTableDiffusivity_m2_s=alpha,
                fullRunDiffusionLength_m=math.sqrt(4*alpha*end),
                startDistanceToCentre_m=settings["trackLength_um"]*.5e-6,
                startDistanceOverFullRunDiffusionLength=(settings["trackLength_um"]*.5e-6)/math.sqrt(4*alpha*end),
                diffusionEstimateScope="sqrt(4*max(table k/rho/cp)*full-run-time); a locality rationale, not an error bound")


@contextlib.contextmanager
def runtime_guard(cells, counters, start):
    try:
        import psutil
    except ImportError as error:
        raise RuntimeError("psutil is required for monitored proxy execution") from error
    original = solver._conduction_rate_and_diagonal
    process = psutil.Process()

    def checked(*args, **kwargs):
        if args[0].size != cells:
            raise RuntimeError("Proxy runtime cell count differs")
        steps = counters["attemptedSteps"]+1
        work = counters["attemptedCellSteps"]+cells
        rss = process.memory_info().rss
        wall = time.perf_counter()-start
        check_resources(cells, steps, rss, wall, cellsteps=work)
        counters.update(attemptedSteps=steps, attemptedCellSteps=work,
                        maximumSampledRssBytes=max(counters["maximumSampledRssBytes"], rss),
                        wallTime_s=wall)
        return original(*args, **kwargs)

    with patch.object(solver, "_conduction_rate_and_diagonal", side_effect=checked):
        yield
    check_resources(cells, counters["attemptedSteps"], process.memory_info().rss,
                    time.perf_counter()-start, cellsteps=counters["attemptedCellSteps"])


def execute():
    plan = preflight(require_fresh=True)
    protocol = plan["protocol"]
    counters = dict(attemptedSteps=0, attemptedCellSteps=0,
                    maximumSampledRssBytes=0, wallTime_s=0.0)
    report = dict(schemaVersion=1, protocolId=ID, stage="running",
                  status="diagnostic-only", validationStatus="unvalidated",
                  experimentalValidation=False, operatorMismatch=True,
                  fittingOrTuning=False, matchedExperimentalResidualAvailable=False,
                  convergenceConclusion="not-assessed",
                  protocolSha256=plan["protocolSha256"],
                  tableSha256=protocol["tableSha256"],
                  implementationSha256=protocol["implementationSha256"],
                  executionHeadCommit=subprocess.check_output(["git", "rev-parse", "HEAD"],
                      cwd=ROOT, text=True).strip(),
                  startedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  finiteLengthApproximation=True, equivalenceToEightMmTrackEstablished=False,
                  preflight={k: v for k, v in plan.items() if k != "protocol"},
                  assumptions=protocol["assumptions"], cases=[],
                  workCountSemantics="Attempted steps count conduction assemblies; a failing final assembly may not be accepted. Accepted counts are exact only for completed cases. Source-internal retries are reported by completed solver results.",
                  limits=LIMITS, runtimeWork=counters)
    started = time.perf_counter()
    case = None
    try:
        if not plan["executionEligible"]:
            raise RuntimeError("Preflight execution denied: "+"; ".join(plan["executionDenialReasons"]))
        for case in plan["cases"]:
            before_steps = counters["attemptedSteps"]
            before_work = counters["attemptedCellSteps"]
            if solver.implementation_fingerprint() != protocol["implementationSha256"]:
                raise RuntimeError("Thermal implementation changed before locality case")
            with runtime_guard(case["cells"], counters, started):
                result = solver.run(case["rawInputs"])
            if result["provenance"]["implementationHash"] != protocol["implementationSha256"]:
                raise RuntimeError("Executed thermal implementation differs")
            case_steps = counters["attemptedSteps"]-before_steps
            if result["discretization"]["steps"] != case_steps:
                raise RuntimeError("Runtime step count differs from accepted solver steps")
            section = result.get("midTrackInterpolatedCrossSection") or {}
            report["cases"].append(dict(trackLength_um=case["rawInputs"]["trackLength_um"],
                acceptedSteps=case_steps,
                acceptedCellSteps=counters["attemptedCellSteps"]-before_work,
                result=result, thermalProxyOperator=section))
        sensitivity = compare_locality(report["cases"])
        report.update(stage="complete", localLengthSensitivity=sensitivity,
                      diagnosticGeometryDifferences=None)
    except Exception as error:
        report.update(stage="preflight-denied" if not plan["executionEligible"] else "aborted",
                      error=dict(type=type(error).__name__, message=str(error)),
                      diagnosticGeometryDifferences=None)
        if case is not None:
            report["failedCase"] = dict(trackLength_um=case["rawInputs"]["trackLength_um"],
                attemptedSteps=counters["attemptedSteps"]-before_steps,
                attemptedCellSteps=counters["attemptedCellSteps"]-before_work,
                acceptedSteps=None, reason="Failure occurred before a complete solver result was available")
        attempted_lengths = {row["trackLength_um"] for row in report["cases"]}
        if case is not None:
            attempted_lengths.add(case["rawInputs"]["trackLength_um"])
        report["unexecutedTrackLengths_um"] = [row["rawInputs"]["trackLength_um"]
            for row in plan["cases"] if row["rawInputs"]["trackLength_um"] not in attempted_lengths]
    report["wallTime_s"] = time.perf_counter()-started
    report["endedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    data = (json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)+"\n").encode()
    if len(data) > LIMITS["maximumReportBytes"]:
        raise RuntimeError("Proxy report size budget exceeded")
    # Only the frozen, zero-step full-length preflight may be replaced, and its
    # complete original record is retained inside this report. Completed runs
    # are never overwritten by a repeated CLI invocation.
    if OUTPUT.exists() and digest(OUTPUT.read_bytes()) != protocol["priorFullLengthReportSha256"]:
        raise FileExistsError("Proxy destination changed during execution")
    with OUTPUT.open("wb" if OUTPUT.exists() else "xb") as stream:
        stream.write(data)
    return dict(stage=report["stage"], report=OUTPUT.relative_to(ROOT).as_posix(),
                sha256=digest(data), wallTime_s=report["wallTime_s"], runtimeWork=counters,
                diagnosticGeometryDifferences=report["diagnosticGeometryDifferences"],
                localLengthSensitivity=report.get("localLengthSensitivity"),
                error=report.get("error"))


def compare_locality(cases):
    result = dict(status="inconclusive", thresholdRule="both absolute W/D differences <= one effective mesh h",
                  experimentalValidation=False, equivalenceToEightMmTrackEstablished=False,
                  differences_um=None)
    if len(cases) != 2:
        return result
    sections = [case["thermalProxyOperator"] for case in cases]
    if any(section.get("status") != "thermal-proxy" for section in sections):
        result["reason"] = "One or both midpoint liquidus contours are unresolved"
        return result
    if any(section.get(f"{quantity}_um") is None for section in sections for quantity in ("width", "depth")):
        return result
    mesh = min(section["mesh_um"] for section in sections)
    differences = {quantity: sections[1][f"{quantity}_um"]-sections[0][f"{quantity}_um"]
                   for quantity in ("width", "depth")}
    result.update(status="pass-local-length-sensitivity" if all(abs(v) <= mesh for v in differences.values())
                         else "inconclusive", differences_um=differences, threshold_um=mesh,
                  scope="Conditional two-short-length thermal-proxy sensitivity; no 8 mm equivalence, numerical convergence or etched-boundary validation")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    print(json.dumps(execute() if args.execute else preflight(), indent=2, allow_nan=False))
