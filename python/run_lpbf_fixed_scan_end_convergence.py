"""Run the frozen fixed first-scan-end CPU liquidus-contour diagnostic."""

import argparse
import copy
import datetime
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lpbf_convergence_study import ACCEPTANCE, _axis
from lpbf_fixed_scan_end_observation import (
    ARTIFACT_SCOPE,
    MAX_UNCOMPRESSED_FIELD_BYTES,
    OBSERVATION_OPERATOR,
    TEMPORAL_SELECTION,
    write_selected_state_artifact,
)
from lpbf_peak import interpolated_peak_melt_pool
from lpbf_simulation import IMPLEMENTATION_SOURCE_FILES, implementation_fingerprint, run, scan_segments


PROTOCOL_PATH = ROOT / "docs" / "LPBF_P4_FIXED_SCAN_END_CONVERGENCE_PROTOCOL_2026-09-27.json"
OUTPUT_PATH = ROOT / "docs" / "LPBF_P4_FIXED_SCAN_END_CONVERGENCE_2026-09-27.json"
FIELD_DIRECTORY = ROOT / "docs" / "LPBF_P4_FIXED_SCAN_END_FIELDS_2026-09-27"
SCENARIO_PATH = ROOT / "docs" / "LPBF_P4_CURRENT_MODEL_40W_SCENARIO_2026-09-25.json"
ASSESSMENT_PATH = ROOT / "python" / "lpbf_convergence_study.py"
CONTOUR_PATH = ROOT / "python" / "lpbf_peak.py"
PROTOCOL_ID = "lpbf-p4-fixed-scan-end-liquidus-contour-2026-09-27-v1"


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _case_specs(protocol):
    unique = {}
    for mesh in protocol["meshLevels_um"]:
        key = (mesh, protocol["fixedMeshMaxDt_s"])
        unique.setdefault(key, {"mesh_um": mesh, "maxDt_s": protocol["fixedMeshMaxDt_s"], "axes": []})
        unique[key]["axes"].append("mesh")
    for dt in protocol["timeLevels_s"]:
        key = (protocol["fixedTimeStudyMesh_um"], dt)
        unique.setdefault(key, {"mesh_um": protocol["fixedTimeStudyMesh_um"], "maxDt_s": dt, "axes": []})
        unique[key]["axes"].append("time")
    rows = list(unique.values())
    expected = {(20, 2.5e-8), (10, 2.5e-8), (5, 2.5e-8),
                (5, 5e-8), (5, 1.25e-8)}
    if {(row["mesh_um"], row["maxDt_s"]) for row in rows} != expected or len(rows) != 5:
        raise ValueError("Protocol must define the five unique frozen CPU cases")
    return rows


def preflight(protocol_path=PROTOCOL_PATH, output_path=OUTPUT_PATH, field_directory=FIELD_DIRECTORY):
    protocol_path = Path(protocol_path).resolve()
    if protocol_path != PROTOCOL_PATH.resolve():
        raise ValueError("Only the registered fixed scan-end protocol is accepted")
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    if (protocol.get("schemaVersion") != 1 or protocol.get("protocolId") != PROTOCOL_ID
            or protocol.get("status") != "frozen-before-execution"
            or protocol.get("experimentalValidation") is not False):
        raise ValueError("Fixed scan-end protocol is not frozen with bounded evidence scope")
    if protocol.get("runnerFile") != "python/run_lpbf_fixed_scan_end_convergence.py" \
            or protocol.get("runnerSha256") != _sha256_file(Path(__file__)):
        raise ValueError("Fixed scan-end runner hash differs from the protocol")
    observation_path = ROOT / "python" / "lpbf_fixed_scan_end_observation.py"
    if protocol.get("observationModuleSha256") != _sha256_file(observation_path):
        raise ValueError("Fixed scan-end observation module hash differs from the protocol")
    if protocol.get("scenarioFile") != "docs/LPBF_P4_CURRENT_MODEL_40W_SCENARIO_2026-09-25.json" \
            or protocol.get("scenarioSha256") != _sha256_file(SCENARIO_PATH):
        raise ValueError("Fixed scan-end scenario differs from the frozen source bytes")
    if protocol.get("assessmentModuleSha256") != _sha256_file(ASSESSMENT_PATH):
        raise ValueError("Numerical assessment module hash differs from the protocol")
    if protocol.get("contourModuleSha256") != _sha256_file(CONTOUR_PATH):
        raise ValueError("Spatial contour module hash differs from the protocol")
    scenario_document = json.loads(SCENARIO_PATH.read_bytes())
    if scenario_document.get("protocolId") != protocol.get("scenarioDocumentProtocolId"):
        raise ValueError("Scenario document protocol identity differs")
    scenario = scenario_document.get("scenario")
    if (not isinstance(scenario, dict) or scenario.get("mode") != "standard"
            or scenario.get("backend") != "reference" or scenario.get("study") != "none"
            or scenario.get("surfaceMode") != "powder-layer" or "measurements" in scenario
            or scenario.get("material") != "Inconel 718" or scenario.get("power_W") != 40
            or scenario.get("mesh_um") != 5 or scenario.get("maxDt_s") != 2.5e-8):
        raise ValueError("Scenario is outside the frozen standard/reference 40 W CPU scope")
    segments, _ = scan_segments(scenario)
    expected_target = segments[0]["end_s"]
    expected_x = float(segments[0]["end"][0])
    expected_surface = scenario["layer_um"] * 1e-6
    if (protocol.get("targetTime_s") != expected_target
            or protocol.get("beamCenterX_m") != expected_x
            or protocol.get("surfaceZ_m") != expected_surface):
        raise ValueError("Observation target differs from the first scan-end physical location")
    if (protocol.get("contourOperator") != OBSERVATION_OPERATOR
            or protocol.get("spatialOperator") != "peak-liquidus-cell-edge-linear-contour-v1"
            or protocol.get("temporalSelection") != TEMPORAL_SELECTION
            or protocol.get("acceptance") != ACCEPTANCE
            or protocol.get("fieldFormat") != "numpy-npz-compressed-little-endian-float64-v1"
            or protocol.get("fieldScope") != ARTIFACT_SCOPE
            or protocol.get("maxUncompressedFieldBytes") != MAX_UNCOMPRESSED_FIELD_BYTES):
        raise ValueError("Contour operator, temporal selection, or inherited acceptance differs")
    if protocol.get("implementationSourceManifest") != list(IMPLEMENTATION_SOURCE_FILES):
        raise ValueError("Implementation source manifest differs from the solver manifest")
    fingerprint = implementation_fingerprint()
    if protocol.get("expectedImplementationFingerprint") != fingerprint:
        raise ValueError("Current solver implementation differs from the frozen fingerprint")
    output_path = Path(output_path).resolve()
    field_directory = Path(field_directory).resolve()
    if ROOT not in output_path.parents or ROOT not in field_directory.parents:
        raise ValueError("Diagnostic output paths must remain within the repository")
    if (output_path.relative_to(ROOT).as_posix() != protocol.get("outputFile")
            or field_directory.relative_to(ROOT).as_posix() != protocol.get("fieldDirectory")):
        raise ValueError("Diagnostic output paths differ from the frozen protocol")
    partial = output_path.with_name(output_path.stem + ".partial.json")
    if output_path.exists() or partial.exists() or field_directory.exists():
        raise FileExistsError("Fixed scan-end diagnostic output already exists")
    return (protocol, scenario, _case_specs(protocol), fingerprint, output_path, partial,
            field_directory, _sha256_bytes(protocol_bytes), scenario_document)


def _row_from_result(spec, result, contour, field_artifact, before, after, fingerprint):
    core = result["coreContract"]
    settings = result["settings"]
    expected_model = "stationary-enthalpy-conduction-layer-conforming-v1"
    if (result.get("effectiveMode") != "standard" or result.get("solver", {}).get("id") != "enthalpy-fv-6"
            or core.get("actualBackend") != "numpy-reference" or core.get("modelId") != expected_model
            or core.get("solverId") != result["solver"]["id"] or settings.get("mesh_um") != spec["mesh_um"]
            or settings.get("maxDt_s") != spec["maxDt_s"]):
        raise ValueError("Frozen CPU solver identity or resolved case settings changed")
    if not result["material"].get("materialId") or not result["material"].get("materialRevisionSha256"):
        raise ValueError("Resolved material identity or revision is missing")
    actual_hash = result["provenance"].get("implementationHash")
    integrity = {"before": before, "recorded": actual_hash, "after": after,
                 "stable": before == actual_hash == after == fingerprint}
    if not integrity["stable"]:
        raise ValueError("Frozen implementation fingerprint changed during a diagnostic row")
    discretization = result["discretization"]
    energy = result["energyBalance"]
    input_j, losses_j, stored_j = (energy[key] for key in ("input_J", "losses_J", "stored_J"))
    relative_error = abs(input_j - losses_j - stored_j) / max(input_j, 1e-30)
    return {
        "axes": list(spec["axes"]),
        "requested": {"mesh_um": spec["mesh_um"], "maxDt_s": spec["maxDt_s"]},
        "mesh_um": spec["mesh_um"], "requestedMaxDt_s": spec["maxDt_s"], "status": "completed",
        "actualMesh_m": discretization["mesh_m"], "cells": discretization["cells"],
        "actualMeanDt_s": discretization["meanDt_s"], "actualMinimumDt_s": discretization["minimumDt_s"],
        "steps": discretization["steps"], "metrics": copy.deepcopy(result["metrics"]),
        "historicalPeakSelection": {key: result.get("numericalDiagnostics", {}).get(key) for key in (
            "meltPoolExtraction", "peakMeltTime_s", "peakMeltStep", "peakMeltCellCount",
            "equalMaximumEndpointCount", "firstEqualMaximumTime_s", "lastEqualMaximumTime_s")},
        "historicalPeakContour": copy.deepcopy(result.get("peakInterpolatedMeltPool")),
        "fixedScanEndObservation": contour,
        "fieldArtifact": field_artifact,
        "energyBalance": {"input_J": input_j, "losses_J": losses_j, "stored_J": stored_j,
                          "relativeError": relative_error, "denominator": "input_J",
                          "reference": "initial enthalpy at preheat"},
        "model": {"modelId": core["modelId"], "actualBackend": core["actualBackend"],
                  "solverId": core["solverId"]},
        "material": {"name": result["material"]["name"],
                     "materialId": result["material"].get("materialId"),
                     "materialRevisionSha256": result["material"].get("materialRevisionSha256"),
                     "version": result["material"]["version"]},
        "provenance": {"inputHash": result["provenance"]["inputHash"],
                       "implementationHash": actual_hash},
        "implementationIntegrity": integrity,
    }


def _assessment_rows(rows, specs, axis):
    selected = []
    axis_specs = sorted((spec for spec in specs if axis in spec["axes"]),
                        key=lambda item: item["mesh_um"] if axis == "mesh" else item["maxDt_s"],
                        reverse=True)
    for spec in axis_specs:
        row = next(item for item in rows if item["mesh_um"] == spec["mesh_um"]
                   and item["requestedMaxDt_s"] == spec["maxDt_s"])
        contour = row["fixedScanEndObservation"]
        projected = copy.deepcopy(row)
        projected["requested"] = spec["mesh_um"] if axis == "mesh" else spec["maxDt_s"]
        if (contour.get("status") != "thermal-proxy"
                or contour.get("operator") != "peak-liquidus-cell-edge-linear-contour-v1"
                or contour.get("temporalSelection") != TEMPORAL_SELECTION
                or any(type(contour.get(key)) not in (int, float)
                       or not math.isfinite(contour[key]) or contour[key] <= 0
                       for key in ("width_um", "depth_um"))):
            projected.update(status="failed", reason="Fixed scan-end liquidus contour is unavailable or invalid")
        projected["width_um"] = contour.get("width_um")
        projected["depth_um"] = contour.get("depth_um")
        selected.append(projected)
    actual_key = "actualMesh_m" if axis == "mesh" else "actualMeanDt_s"
    return _axis(selected, actual_key)


def execute(protocol_path=PROTOCOL_PATH, output_path=OUTPUT_PATH, field_directory=FIELD_DIRECTORY):
    (protocol, scenario, specs, fingerprint, output, partial, fields, protocol_sha,
     scenario_document) = preflight(protocol_path, output_path, field_directory)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()
    report = {
        "schemaVersion": 1, "protocolId": protocol["protocolId"],
        "protocolSha256": protocol_sha,
        "scenarioFile": protocol["scenarioFile"],
        "scenarioDocumentProtocolId": scenario_document["protocolId"],
        "scenarioSha256": protocol["scenarioSha256"],
        "runnerSha256": protocol["runnerSha256"],
        "observationModuleSha256": protocol["observationModuleSha256"],
        "assessmentModuleSha256": protocol["assessmentModuleSha256"],
        "contourModuleSha256": protocol["contourModuleSha256"],
        "implementationFingerprintAtStart": fingerprint,
        "implementationFingerprintAtEnd": None,
        "implementationSourceManifest": list(IMPLEMENTATION_SOURCE_FILES),
        "executionHeadCommit": head, "scope": protocol["scope"],
        "experimentalValidation": False,
        "priorFrozenP4Status": protocol["priorFrozenP4Status"],
        "fixedObservation": {"operator": protocol["contourOperator"],
                             "spatialOperator": protocol["spatialOperator"],
                             "temporalSelection": protocol["temporalSelection"],
                             "targetTime_s": protocol["targetTime_s"],
                             "beamCenterX_m": protocol["beamCenterX_m"],
                             "surfaceZ_m": protocol["surfaceZ_m"]},
        "acceptance": copy.deepcopy(ACCEPTANCE), "cases": copy.deepcopy(specs),
        "rows": [], "stage": "running",
        "startedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    _write_json(partial, report)
    liquidus = None
    identity = None
    for spec in specs:
        payload = copy.deepcopy(scenario)
        payload.update(mesh_um=spec["mesh_um"], maxDt_s=spec["maxDt_s"])
        observed = []
        before = implementation_fingerprint()
        if before != fingerprint:
            raise ValueError("Implementation changed before a diagnostic row")
        result = run(payload, selected_time_observer=observed.append,
                     selected_time_s=protocol["targetTime_s"])
        after = implementation_fingerprint()
        if len(observed) != 1:
            raise ValueError("Each run must produce exactly one accepted scan-end state")
        snapshot = observed[0]
        liquidus = result["material"].get("liquidus_K") if liquidus is None else liquidus
        if not isinstance(liquidus, (int, float)) or not math.isfinite(liquidus) or liquidus <= 0:
            raise ValueError("Resolved material liquidus is missing")
        contour = interpolated_peak_melt_pool(
            snapshot["coordinates_m"], snapshot["temperature_K"], protocol["surfaceZ_m"],
            payload["scanAngle_deg"], payload["mesh_um"] * 1e-6, liquidus)
        contour.update(temporalSelection=protocol["temporalSelection"],
                       observationOperator=protocol["contourOperator"],
                       targetTime_s=snapshot["target_time_s"],
                       actualTime_s=snapshot["time_s"],
                       targetMinusActualTime_s=snapshot["time_difference_s"],
                       roundoffTolerance_s=snapshot["roundoff_tolerance_s"],
                       beamCenterX_m=protocol["beamCenterX_m"],
                       surfaceZ_m=protocol["surfaceZ_m"],
                       evidenceScope="CPU numerical thermal proxy only; no experimental validation")
        artifact_path = fields / (f"mesh-{spec['mesh_um']:g}um-dt-{spec['maxDt_s']:.4g}s.npz")
        field_artifact = write_selected_state_artifact(snapshot, artifact_path)
        field_artifact["path"] = artifact_path.relative_to(ROOT).as_posix()
        row = _row_from_result(spec, result, contour, field_artifact, before, after, fingerprint)
        row_identity = (row["model"]["modelId"], row["model"]["actualBackend"],
                        row["model"]["solverId"], row["material"]["materialId"],
                        row["material"]["materialRevisionSha256"])
        if identity is None:
            identity = row_identity
        elif row_identity != identity:
            raise ValueError("Model or material revision changed between diagnostic rows")
        report["rows"].append(row)
        _write_json(partial, report)
    mesh_assessment = _assessment_rows(report["rows"], specs, "mesh")
    time_assessment = _assessment_rows(report["rows"], specs, "time")
    after_all = implementation_fingerprint()
    if after_all != fingerprint:
        raise ValueError("Frozen implementation changed during the convergence diagnostic")
    report.update(meshAssessment=mesh_assessment, timeAssessment=time_assessment,
                  implementationFingerprintAtEnd=after_all,
                  status="failed" if "failed" in (mesh_assessment["status"], time_assessment["status"])
                  else "inconclusive" if "inconclusive" in (mesh_assessment["status"], time_assessment["status"])
                  else "pass",
                  stage="completed", completedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  contourEvidenceScope="Numerical thermal proxy only; not an etched-optical section or experimental validation")
    _write_json(output, report)
    _write_json(partial, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL_PATH)
    args = parser.parse_args()
    report = execute(args.protocol)
    print(json.dumps({"status": report["status"], "mesh": report["meshAssessment"]["status"],
                      "time": report["timeAssessment"]["status"], "output": str(OUTPUT_PATH)}, indent=2))


if __name__ == "__main__":
    main()
