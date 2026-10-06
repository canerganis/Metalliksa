"""Run a fresh, resource-bounded LPBF P4 accepted-dt protocol (v2)."""

import datetime
import hashlib
import json
import math
from contextlib import contextmanager
from pathlib import Path
import subprocess

import numpy as np

from lpbf_core_physics import calculate_mesh_domain, scan_segments
import lpbf_simulation
from lpbf_simulation import IMPLEMENTATION_SOURCE_FILES, implementation_fingerprint, validate


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "docs" / "LPBF_P4_CPU_OPERATOR_CONVERGENCE_PROTOCOL_2026-09-28_v2.json"
FROZEN_REQUESTED_MAX_DT_S = [5e-8, 2.5e-8, 1.25e-8]
FROZEN_RESOURCE_LIMITS = {
    "maximumCells": 600000,
    "estimatedBytesPerCell": 1024,
    "maximumEstimatedBytes": 805306368,
    "maximumStepsPerCase": 40000,
    "maximumTotalCellSteps": 30000000000,
}
FROZEN_ACCEPTANCE_REFERENCE = {
    "discreteAssessment": "python/lpbf_convergence_study.py#ACCEPTANCE",
    "continuousContourAssessment": "python/lpbf_contour_convergence_study.py#ACCEPTANCE",
    "thresholdsChanged": False,
}


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _repo_path(root, relative, label):
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError(f"Invalid {label} path")
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError(f"Invalid {label} path")
    root = root.resolve()
    lexical = root
    for part in relative_path.parts:
        lexical = lexical / part
        if lexical.is_symlink() or getattr(lexical, "is_junction", lambda: False)():
            raise ValueError(f"{label} path contains a link")
    path = lexical.resolve()
    if root not in path.parents:
        raise ValueError(f"{label} path is outside the repository")
    return path


def _load_protocol(protocol_path=PROTOCOL_PATH):
    path = Path(protocol_path).resolve(strict=True)
    if path != PROTOCOL_PATH.resolve():
        raise ValueError("Only the registered P4 v2 protocol is accepted")
    raw = path.read_bytes()
    protocol = json.loads(raw)
    required = {
        "schemaVersion", "protocolId", "status", "scope", "experimentalValidation",
        "scenarioFile", "scenarioDocumentProtocolId", "scenarioSha256",
        "requestedMaxDt_s", "expectedImplementationFingerprint", "runnerFile", "runnerSha256",
        "assessmentModuleFile", "assessmentModuleSha256", "contourAssessmentModuleFile",
        "contourAssessmentModuleSha256", "expectedModelId", "expectedSolverId",
        "expectedActualBackend", "expectedMaterialId", "expectedMaterialRevisionSha256",
        "expectedResolvedInputSha256", "output", "partial", "fieldDirectory",
        "resourceLimits", "acceptanceReference",
    }
    if (not isinstance(protocol, dict) or set(protocol) != required
            or type(protocol["schemaVersion"]) is not int or protocol["schemaVersion"] != 2
            or protocol["protocolId"] != "lpbf-p4-cpu-operator-accepted-dt-v2"
            or protocol["status"] != "frozen-before-execution"
            or protocol["experimentalValidation"] is not False
            or protocol["requestedMaxDt_s"] != FROZEN_REQUESTED_MAX_DT_S
            or protocol["resourceLimits"] != FROZEN_RESOURCE_LIMITS
            or protocol["acceptanceReference"] != FROZEN_ACCEPTANCE_REFERENCE):
        raise ValueError("Unsupported or unfrozen P4 v2 protocol")
    runner_rel = Path(__file__).resolve().relative_to(ROOT).as_posix()
    if protocol["runnerFile"] != runner_rel or _sha256(Path(__file__).read_bytes()) != protocol["runnerSha256"]:
        raise ValueError("P4 v2 runner identity differs from protocol")
    scenario_path = _repo_path(ROOT, protocol["scenarioFile"], "Scenario")
    scenario_bytes = scenario_path.read_bytes()
    document = json.loads(scenario_bytes)
    if (not isinstance(document, dict) or document.get("protocolId") != protocol["scenarioDocumentProtocolId"]
            or _sha256(scenario_bytes) != protocol["scenarioSha256"]
            or not isinstance(document.get("scenario"), dict)):
        raise ValueError("P4 v2 scenario identity differs from protocol")
    for module_key, hash_key in (("assessmentModuleFile", "assessmentModuleSha256"),
                                 ("contourAssessmentModuleFile", "contourAssessmentModuleSha256")):
        module = _repo_path(ROOT, protocol[module_key], module_key)
        if not module.is_file() or _sha256(module.read_bytes()) != protocol[hash_key]:
            raise ValueError(f"P4 v2 {module_key} identity differs from protocol")
    if _sha256(Path(__file__).read_bytes()) != protocol["runnerSha256"]:
        raise ValueError("P4 v2 runner changed while loading protocol")
    if implementation_fingerprint() != protocol["expectedImplementationFingerprint"]:
        raise ValueError("Current numerical source fingerprint differs from fresh protocol")
    return protocol, document["scenario"], raw, scenario_bytes


def _resource_preflight(scenario, protocol):
    """Resolve only small inputs/geometry, then bound the run before solver allocation."""
    p, material = validate(scenario)
    if (p.get("mode") != "standard" or p.get("backend") != "reference"
            or p.get("study", "none") != "none" or p.get("surfaceMode") != "powder-layer"
            or "measurements" in p or p.get("powderGridPolicy") != "layer-conforming"):
        raise ValueError("Fresh P4 v2 gate supports only the fixed standard CPU layer-conforming scenario")
    expected_input = _sha256(json.dumps(p, sort_keys=True, allow_nan=False).encode("utf-8"))
    model_id = "stationary-enthalpy-conduction-layer-conforming-v1"
    if (expected_input != protocol["expectedResolvedInputSha256"]
            or model_id != protocol["expectedModelId"]
            or "numpy-reference" != protocol["expectedActualBackend"]
            or "enthalpy-fv-6" != protocol["expectedSolverId"]
            or material.get("materialId") != protocol["expectedMaterialId"]
            or material.get("materialRevisionSha256") != protocol["expectedMaterialRevisionSha256"]):
        raise ValueError("Resolved solver, input or material identity differs from fresh protocol")
    domain = calculate_mesh_domain(p)
    cells = int(domain["nx"] * domain["ny"] * domain["nz"])
    _segments, end_s = scan_segments(p)
    if not math.isfinite(end_s) or end_s <= 0:
        raise ValueError("Invalid resolved simulation duration")
    limits = protocol["resourceLimits"]
    if (not isinstance(limits, dict) or set(limits) != {
            "maximumCells", "estimatedBytesPerCell", "maximumEstimatedBytes",
            "maximumStepsPerCase", "maximumTotalCellSteps"}):
        raise ValueError("Invalid P4 v2 resource limits")
    cells_max = limits["maximumCells"]
    bytes_per_cell = limits["estimatedBytesPerCell"]
    max_bytes = limits["maximumEstimatedBytes"]
    max_steps = limits["maximumStepsPerCase"]
    max_cell_steps = limits["maximumTotalCellSteps"]
    if any(type(value) is not int or value <= 0 for value in (cells_max, bytes_per_cell, max_bytes, max_steps, max_cell_steps)):
        raise ValueError("P4 v2 resource limits must be positive integers")
    estimates = []
    total_cell_steps = 0
    for requested in protocol["requestedMaxDt_s"]:
        if type(requested) not in (int, float) or not math.isfinite(requested) or requested <= 0:
            raise ValueError("P4 v2 requested timestep levels are invalid")
        steps = math.ceil(end_s / requested)
        total_cell_steps += cells * steps
        estimates.append({"requestedMaxDt_s": requested, "lowerBoundSteps": steps,
                          "lowerBoundCellSteps": cells * steps})
    estimated_bytes = cells * bytes_per_cell
    if (cells > cells_max or estimated_bytes > max_bytes
            or any(item["lowerBoundSteps"] > max_steps for item in estimates)
            or total_cell_steps > max_cell_steps):
        raise ValueError("P4 v2 resource preflight exceeded before solver allocation")
    return {"cells": cells, "estimatedBytes": estimated_bytes,
            "lowerBoundTotalCellSteps": total_cell_steps, "cases": estimates,
            "material": material, "resolvedSettings": p, "modelId": model_id}


def _guarded_source_limiter(original, *, cells, max_steps_case, max_total_cell_steps, counters):
    """Count accepted source-limiter calls and reject before a cap-breaking update."""
    def guarded(*args, **kwargs):
        if counters["caseSteps"] >= max_steps_case:
            raise RuntimeError("P4 v2 runtime per-case timestep limit reached before the next update")
        if (counters["totalSteps"] + 1) * cells > max_total_cell_steps:
            raise RuntimeError("P4 v2 runtime total cell-step limit reached before the next update")
        result = original(*args, **kwargs)
        counters["caseSteps"] += 1
        counters["totalSteps"] += 1
        return result
    return guarded


@contextmanager
def _install_runtime_step_guard(*, cells, max_steps_case, max_total_cell_steps, counters):
    original = lpbf_simulation.source_limited_step
    lpbf_simulation.source_limited_step = _guarded_source_limiter(
        original, cells=cells, max_steps_case=max_steps_case,
        max_total_cell_steps=max_total_cell_steps, counters=counters)
    try:
        yield original
    finally:
        lpbf_simulation.source_limited_step = original


def _preflight_destinations(protocol):
    paths = {key: _repo_path(ROOT, protocol[key], key)
             for key in ("output", "partial", "fieldDirectory")}
    if paths["partial"] != paths["output"].with_name(paths["output"].stem + ".partial.json"):
        raise ValueError("P4 v2 partial path is not paired with its output path")
    reserved = [*paths.values(), paths["partial"].with_name(paths["partial"].name + ".tmp")]
    if len(set(reserved)) != len(reserved):
        raise ValueError("P4 v2 evidence destinations must be distinct")
    for path in reserved:
        if path.exists():
            raise FileExistsError(f"P4 v2 evidence destination already exists: {path.relative_to(ROOT)}")
        if path.parent.exists() and path.parent.is_symlink():
            raise ValueError("P4 v2 evidence destination parent must not be a link")
    return paths


def _write_new(path, payload):
    data = (json.dumps(payload, indent=2, allow_nan=False) + "\n").encode("utf-8")
    with path.open("xb") as stream:
        stream.write(data)


def _replace_partial(path, payload):
    temporary = path.with_name(path.name + ".tmp")
    data = (json.dumps(payload, indent=2, allow_nan=False) + "\n").encode("utf-8")
    with temporary.open("xb") as stream:
        stream.write(data)
    temporary.replace(path)


def _mark_failed_partial(path, report, error):
    failed = dict(report)
    failed.update(stage="failed", status="failed", integrityStatus="not-completed",
                  failedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  error=f"{type(error).__name__}: {error}"[:1000])
    try:
        _replace_partial(path, failed)
    except Exception:
        # Preserve the original solver/field/assessment exception.
        pass


def _write_field(path, state):
    with path.open("xb") as stream:
        np.savez(stream, **state)
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return {"path": path.relative_to(ROOT).as_posix(), "size_bytes": size,
            "sha256": digest.hexdigest(), "encoding": "NumPy NPZ, uncompressed"}


def run_protocol(protocol_path=PROTOCOL_PATH):
    protocol, scenario, protocol_bytes, scenario_bytes = _load_protocol(protocol_path)
    resources = _resource_preflight(scenario, protocol)
    destinations = _preflight_destinations(protocol)
    from lpbf_convergence_study import _axis
    from lpbf_contour_convergence_study import _contour_axis
    import lpbf_convergence_study as convergence_study

    assessment_path = _repo_path(ROOT, protocol["assessmentModuleFile"], "Assessment module")
    contour_path = _repo_path(ROOT, protocol["contourAssessmentModuleFile"], "Contour assessment module")
    protocol_sha = _sha256(protocol_bytes)
    source_fingerprint = protocol["expectedImplementationFingerprint"]
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()
    report = {
        "schemaVersion": 2, "protocolId": protocol["protocolId"],
        "protocolSha256": protocol_sha, "runnerSha256": protocol["runnerSha256"],
        "scenarioFile": protocol["scenarioFile"], "scenarioSha256": _sha256(scenario_bytes),
        "executionHeadCommit": head, "scope": protocol["scope"],
        "experimentalValidation": False, "implementationFingerprintAtStart": source_fingerprint,
        "implementationSourceManifest": list(IMPLEMENTATION_SOURCE_FILES),
        "resolvedIdentity": {"inputSha256": protocol["expectedResolvedInputSha256"],
            "modelId": resources["modelId"], "solverId": protocol["expectedSolverId"],
            "actualBackend": protocol["expectedActualBackend"],
            "materialId": protocol["expectedMaterialId"],
            "materialRevisionSha256": protocol["expectedMaterialRevisionSha256"]},
        "resourcePreflight": {key: value for key, value in resources.items()
                              if key not in ("material", "resolvedSettings")},
        "runtimeWork": {"acceptedSteps": 0, "acceptedCellSteps": 0},
        "requestedMaxDt_s": list(protocol["requestedMaxDt_s"]),
        "output": protocol["output"], "partial": protocol["partial"],
        "fieldDirectory": protocol["fieldDirectory"], "rows": [], "stage": "running",
        "startedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    _write_new(destinations["partial"], report)
    original_run = convergence_study.run
    original_step_limiter = lpbf_simulation.source_limited_step
    runtime_steps = {"caseSteps": 0, "totalSteps": 0}
    current_requested = None
    try:
        destinations["fieldDirectory"].mkdir()
        for requested in protocol["requestedMaxDt_s"]:
            current_requested = requested
            if implementation_fingerprint() != source_fingerprint:
                raise ValueError("Numerical source fingerprint changed before P4 v2 row")
            captured = []

            def capture_run(payload):
                return original_run(payload, final_state_observer=captured.append)

            runtime_steps["caseSteps"] = 0
            try:
                with _install_runtime_step_guard(cells=resources["cells"],
                        max_steps_case=protocol["resourceLimits"]["maximumStepsPerCase"],
                        max_total_cell_steps=protocol["resourceLimits"]["maximumTotalCellSteps"],
                        counters=runtime_steps):
                    convergence_study.run = capture_run
                    row = convergence_study._case_result(scenario, "maxDt_s", requested)
            finally:
                convergence_study.run = original_run
            if row.get("status") != "completed" or len(captured) != 1:
                report["failedCase"] = {"requestedMaxDt_s": requested, "row": row,
                    "runtimeCaseSteps": runtime_steps["caseSteps"],
                    "runtimeTotalSteps": runtime_steps["totalSteps"]}
                report["stage"] = "failed-before-output"
                _replace_partial(destinations["partial"], report)
                raise ValueError(f"P4 v2 row failed or did not capture one final state: {requested}")
            row["runtimeWork"] = {"acceptedSteps": runtime_steps["caseSteps"],
                                  "acceptedCellSteps": runtime_steps["caseSteps"] * resources["cells"]}
            field_name = f"maxdt-{requested:.4e}.npz"
            field_path = destinations["fieldDirectory"] / field_name
            row["fieldArtifact"] = _write_field(field_path, captured[0])
            row["implementationIntegrity"] = {
                "before": source_fingerprint,
                "recorded": row.get("provenance", {}).get("implementationHash"),
                "after": implementation_fingerprint(),
                "stable": row.get("provenance", {}).get("implementationHash") == source_fingerprint
                    == implementation_fingerprint(),
            }
            identity = row.get("model", {})
            material = row.get("material", {})
            if (identity.get("modelId") != protocol["expectedModelId"]
                    or identity.get("solverId") != protocol["expectedSolverId"]
                    or identity.get("actualBackend") != protocol["expectedActualBackend"]
                    or material.get("materialId") != protocol["expectedMaterialId"]
                    or material.get("materialRevisionSha256") != protocol["expectedMaterialRevisionSha256"]
                    or not row["implementationIntegrity"]["stable"]):
                raise ValueError("P4 v2 solver, material or source identity changed during a row")
            report["rows"].append(row)
            report["runtimeWork"] = {"acceptedSteps": runtime_steps["totalSteps"],
                                     "acceptedCellSteps": runtime_steps["totalSteps"] * resources["cells"]}
            _replace_partial(destinations["partial"], report)
            current_requested = None
    except BaseException as error:
        report["runtimeWork"] = {"acceptedSteps": runtime_steps["totalSteps"],
                                 "acceptedCellSteps": runtime_steps["totalSteps"] * resources["cells"]}
        if current_requested is not None:
            report["failedCaseRequestedMaxDt_s"] = current_requested
        _mark_failed_partial(destinations["partial"], report, error)
        raise
    finally:
        convergence_study.run = original_run
        lpbf_simulation.source_limited_step = original_step_limiter
    try:
        assessment = _axis(report["rows"], "actualMeanDt_s")
        contour_assessment = _contour_axis({"levels": report["rows"]}, "actualMeanDt_s")
        statuses = (assessment["status"], contour_assessment["status"])
        overall_status = "failed" if "failed" in statuses else (
            "inconclusive" if "inconclusive" in statuses else "pass")
        report.update(assessment=assessment,
                      continuousContourAssessment=contour_assessment,
                      contourEvidenceScope="Numerical thermal proxy only; no optical or experimental validation",
                      assessmentModuleSha256AtEnd=_sha256(assessment_path.read_bytes()),
                      contourAssessmentModuleSha256AtEnd=_sha256(contour_path.read_bytes()),
                      implementationFingerprintAtEnd=implementation_fingerprint(),
                      integrityStatus="pass", stage="completed", status=overall_status,
                      completedAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
        if (report["implementationFingerprintAtEnd"] != source_fingerprint
                or report["assessmentModuleSha256AtEnd"] != protocol["assessmentModuleSha256"]
                or report["contourAssessmentModuleSha256AtEnd"] != protocol["contourAssessmentModuleSha256"]):
            report["integrityStatus"] = "failed"
            report["status"] = "failed"
        _replace_partial(destinations["partial"], report)
        _write_new(destinations["output"], report)
    except BaseException as error:
        _mark_failed_partial(destinations["partial"], report, error)
        raise
    return report


if __name__ == "__main__":
    result = run_protocol()
    print(json.dumps({"status": result["status"], "integrityStatus": result["integrityStatus"],
                      "output": result["output"], "fieldDirectory": result["fieldDirectory"]}, indent=2))
