"""Run one frozen 12.5 ns P4 CPU diagnostic and reuse the bound 50/25 ns rows."""

import argparse
import copy
import datetime
import hashlib
import json
import math
import subprocess
from pathlib import Path

from lpbf_simulation import IMPLEMENTATION_SOURCE_FILES, implementation_fingerprint


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/LPBF_P4_REFINED_DT_PROTOCOL_2026-09-25.json"


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _path(relative):
    if not isinstance(relative, str) or "\\" in relative:
        raise ValueError("Expected a repository-relative POSIX path")
    path = (ROOT / relative).resolve()
    if ROOT not in path.parents or not path.is_file():
        raise ValueError(f"Missing or external frozen input: {relative}")
    return path


def _write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _identity(row):
    model, material = row["model"], row["material"]
    return (model["modelId"], model["actualBackend"], model["solverId"],
            material["materialId"], material["materialRevisionSha256"])


def _check_row(row, requested, fingerprint, identity, energy_limit, require_energy_pass=True):
    if row.get("status") != "completed" or not math.isclose(row.get("requested", 0), requested, rel_tol=0, abs_tol=1e-20):
        raise ValueError("Missing completed frozen timestep row")
    if _identity(row) != identity or row["provenance"]["implementationHash"] != fingerprint:
        raise ValueError("Model, material or implementation changed between rows")
    integrity = row.get("implementationIntegrity", {})
    if any(integrity.get(key) != fingerprint for key in ("before", "recorded", "after")) or integrity.get("stable") is not True:
        raise ValueError("Row implementation integrity is not stable")
    energy = row["energyBalance"]
    recomputed = abs(energy["input_J"] - energy["losses_J"] - energy["stored_J"]) / max(energy["input_J"], 1e-30)
    if (not math.isfinite(recomputed) or energy["input_J"] <= 0
            or not math.isclose(recomputed, energy["relativeError"], rel_tol=1e-5, abs_tol=1e-15)
            or (require_energy_pass and recomputed > energy_limit)):
        raise ValueError("Row energy closure evidence is invalid or exceeds the frozen gate")
    distribution = row["acceptedTimestepDistribution"]
    if (not isinstance(row.get("actualMeanDt_s"), (int, float)) or row["actualMeanDt_s"] <= 0
            or distribution["count"] != row["steps"]
            or not math.isclose(distribution["mean_s"], row["actualMeanDt_s"], rel_tol=1e-12)):
        raise ValueError("Accepted timestep evidence is inconsistent")


def preflight():
    protocol_path = _path("docs/LPBF_P4_REFINED_DT_PROTOCOL_2026-09-25.json")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("status") != "frozen-before-execution" or protocol.get("experimentalValidation") is not False:
        raise ValueError("Protocol is not frozen with bounded evidence scope")
    if protocol["runnerFile"] != "python/run_lpbf_p4_refined_dt_diagnostic.py" or _sha(Path(__file__)) != protocol["runnerSha256"]:
        raise ValueError("Runner hash differs from protocol")
    for relative, expected in protocol["frozenFileSha256"].items():
        if _sha(_path(relative)) != expected:
            raise ValueError(f"Frozen file hash mismatch: {relative}")
    baseline = json.loads(_path(protocol["baselineReportFile"]).read_text(encoding="utf-8"))
    scenario_doc = json.loads(_path(protocol["scenarioFile"]).read_text(encoding="utf-8"))
    scenario = scenario_doc["scenario"]
    if (scenario_doc["protocolId"] != protocol["scenarioDocumentProtocolId"]
            or baseline.get("stage") != "completed" or baseline.get("integrityStatus") != "pass"
            or baseline.get("status") != "inconclusive" or baseline.get("experimentalValidation") is not False
            or baseline.get("protocolSha256") != protocol["baselineProtocolSha256"]
            or baseline.get("scenarioSha256") != protocol["frozenFileSha256"][protocol["scenarioFile"]]
            or baseline.get("assessmentModuleSha256AtEnd") != protocol["frozenFileSha256"]["python/lpbf_convergence_study.py"]
            or baseline.get("implementationFingerprintAtStart") != protocol["implementationFingerprint"]
            or baseline.get("implementationFingerprintAtEnd") != protocol["implementationFingerprint"]
            or baseline.get("implementationSourceManifest") != list(IMPLEMENTATION_SOURCE_FILES)
            or len(baseline.get("rows", [])) != 3):
        raise ValueError("Baseline report identity or integrity does not match protocol")
    if (scenario.get("mode") != "standard" or scenario.get("backend") != "reference"
            or scenario.get("material") != "Inconel 718" or scenario.get("mesh_um") != 5
            or scenario.get("study") != "none" or scenario.get("powderGridPolicy") != "layer-conforming"
            or "measurements" in scenario or baseline.get("fixedMesh_um") != 5):
        raise ValueError("Scenario differs from frozen 5 um IN718 CPU scope")
    fingerprint = implementation_fingerprint()
    if fingerprint != protocol["implementationFingerprint"]:
        raise ValueError("Current implementation fingerprint differs from reused rows")
    rows = baseline["rows"]
    identity = tuple(protocol["expectedModelMaterialIdentity"])
    for row, requested in zip(rows, (1e-7, 5e-8, 2.5e-8)):
        _check_row(row, requested, fingerprint, identity, protocol["energyRelativeErrorMax"])
    if baseline["assessment"]["energyStatus"] != "pass":
        raise ValueError("Baseline energy gate is not pass")
    output = ROOT / protocol["outputFile"]
    partial = ROOT / protocol["partialFile"]
    if output.exists() or partial.exists():
        raise FileExistsError("Refined diagnostic output already exists")
    return protocol, scenario, copy.deepcopy(rows[1:]), identity, output, partial, _sha(protocol_path)


def execute():
    protocol, scenario, rows, identity, output, partial, protocol_sha = preflight()
    from lpbf_convergence_study import _axis, _case_result
    from lpbf_contour_convergence_study import _contour_axis

    fingerprint = protocol["implementationFingerprint"]
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()
    report = {"schemaVersion": 1, "protocolId": protocol["protocolId"],
              "protocolSha256": protocol_sha, "baselineReportFile": protocol["baselineReportFile"],
              "baselineReportSha256": protocol["frozenFileSha256"][protocol["baselineReportFile"]],
              "scenarioSha256": protocol["frozenFileSha256"][protocol["scenarioFile"]],
              "runnerSha256": protocol["runnerSha256"], "assessmentFileSha256": {
                  path: protocol["frozenFileSha256"][path] for path in protocol["assessmentFiles"]},
              "implementationFingerprintAtStart": fingerprint,
              "executionHeadCommit": head, "fixedMesh_um": 5,
              "requestedMaxDt_s": protocol["requestedMaxDt_s"],
              "reusedRows": [copy.deepcopy(row) for row in rows],
              "newRow": None, "stage": "running", "experimentalValidation": False,
              "priorFrozenP4Status": "failed", "priorFingerprintDiagnosticStatus": "inconclusive",
              "startedAt": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    _write(partial, report)
    before = implementation_fingerprint()
    if before != fingerprint:
        raise ValueError("Implementation changed before new run")
    row = _case_result(scenario, "maxDt_s", protocol["requestedMaxDt_s"][-1])
    after = implementation_fingerprint()
    row["implementationIntegrity"] = {"before": before,
        "recorded": row.get("provenance", {}).get("implementationHash"), "after": after,
        "stable": before == row.get("provenance", {}).get("implementationHash") == after == fingerprint}
    report["newRow"] = row
    _write(partial, report)
    _check_row(row, protocol["requestedMaxDt_s"][-1], fingerprint, identity,
               protocol["energyRelativeErrorMax"], require_energy_pass=False)
    all_rows = rows + [row]
    actual = [item["actualMeanDt_s"] for item in all_rows]
    ratios = [actual[0] / actual[1], actual[1] / actual[2]]
    ratio_status = "pass" if all(abs(ratio - 2) <= protocol["factorTwoRelativeTolerance"] * 2 for ratio in ratios) else "inconclusive"
    cell = _axis(all_rows, "actualMeanDt_s")
    contour = _contour_axis({"levels": all_rows}, "actualMeanDt_s")
    if ratio_status != "pass":
        for assessment in (cell, contour):
            if assessment["status"] == "pass":
                assessment["status"] = "inconclusive"
                assessment["reason"] = "Actual accepted mean dt ratios are not both factor two"
    report.update(actualMeanDt_s=actual, actualRefinementRatios=ratios,
                  factorTwoStatus=ratio_status, cellExtentAssessment=cell,
                  continuousContourAssessment=contour,
                  contourEvidenceScope="Numerical thermal proxy only; no optical or experimental validation",
                  implementationFingerprintAtEnd=after,
                  assessmentFileSha256AtEnd={path: _sha(_path(path)) for path in protocol["assessmentFiles"]},
                  status="failed" if "failed" in (cell["status"], contour["status"])
                  else "inconclusive" if "inconclusive" in (ratio_status, cell["status"], contour["status"])
                  else "pass", stage="completed",
                  completedAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
    if report["assessmentFileSha256AtEnd"] != report["assessmentFileSha256"] or implementation_fingerprint() != fingerprint:
        raise ValueError("Assessment or implementation changed during the run")
    _write(output, report)
    _write(partial, report)
    print(json.dumps({"status": report["status"], "cell": cell["status"],
                      "contour": contour["status"], "output": str(output)}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Run the single expensive 12.5 ns case")
    args = parser.parse_args()
    if args.execute:
        execute()
    else:
        protocol, _, _, _, _, _, digest = preflight()
        print(json.dumps({"preflight": "pass", "protocolSha256": digest,
                          "requestedMaxDt_s": protocol["requestedMaxDt_s"]}, indent=2))
