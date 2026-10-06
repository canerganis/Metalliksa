"""Run a frozen accepted-timestep diagnostic without mutating the P4 gate."""
import argparse
import copy
import datetime
import hashlib
import json
import subprocess
from pathlib import Path

from lpbf_simulation import IMPLEMENTATION_SOURCE_FILES, implementation_fingerprint


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def run_protocol(protocol_path, scenario_path, output_path):
    protocol_path = Path(protocol_path).resolve()
    scenario_path = Path(scenario_path).resolve()
    output_path = Path(output_path).resolve()
    root = Path(__file__).resolve().parents[1]
    protocol_bytes = protocol_path.read_bytes()
    scenario_bytes = scenario_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    scenario_document = json.loads(scenario_bytes)
    scenario = scenario_document.get("scenario")
    if (not isinstance(scenario, dict)
            or scenario_document.get("protocolId") != protocol["scenarioDocumentProtocolId"]):
        raise ValueError("Scenario document identity does not match the frozen protocol")
    if _sha256(scenario_bytes) != protocol["scenarioSha256"]:
        raise ValueError("Scenario bytes do not match the frozen protocol")
    if str(scenario_path.relative_to(root)).replace("\\", "/") != protocol["scenarioFile"]:
        raise ValueError("Scenario path differs from the frozen protocol")
    if str(output_path.relative_to(root)).replace("\\", "/") != protocol["output"]:
        raise ValueError("Output path differs from the frozen protocol")
    assessment_path = (root / protocol["assessmentModuleFile"]).resolve()
    if root not in assessment_path.parents or not assessment_path.is_file():
        raise FileNotFoundError("Assessment module is missing or outside the repository")
    assessment_hash = _sha256(assessment_path.read_bytes())
    if assessment_hash != protocol["assessmentModuleSha256"]:
        raise ValueError("Assessment module bytes do not match the frozen protocol")
    if scenario.get("mode") != "standard" or scenario.get("backend") != "reference":
        raise ValueError("Only the frozen standard/reference CPU scenario is accepted")
    if scenario.get("mesh_um") != protocol["fixedMesh_um"]:
        raise ValueError("Scenario mesh does not match the frozen protocol")

    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True,
                          capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--",
         *[f"python/{path}" for path in IMPLEMENTATION_SOURCE_FILES]],
        cwd=root, check=True, capture_output=True, text=True).stdout.splitlines()
    baseline_hash = implementation_fingerprint()
    runner_hash = _sha256(Path(__file__).read_bytes())
    if runner_hash != protocol["runnerSha256"]:
        raise ValueError("Runner bytes do not match the frozen protocol")
    from lpbf_convergence_study import _axis, _case_result

    rows = []
    base = {
        "schemaVersion": 1,
        "protocolId": protocol["protocolId"],
        "protocolSha256": _sha256(protocol_bytes),
        "runnerSha256": runner_hash,
        "assessmentModuleFile": protocol["assessmentModuleFile"],
        "assessmentModuleSha256": assessment_hash,
        "scenarioFile": str(scenario_path.relative_to(root)).replace("\\", "/"),
        "scenarioDocumentProtocolId": scenario_document["protocolId"],
        "scenarioSha256": _sha256(scenario_bytes),
        "executionHeadCommit": head,
        "scope": protocol["scope"],
        "experimentalValidation": False,
        "priorFrozenP4Status": protocol["priorFrozenP4Status"],
        "startedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "fixedMesh_um": protocol["fixedMesh_um"],
        "requestedMaxDt_s": protocol["requestedMaxDt_s"],
        "dirtyManifestPathsAtStart": dirty,
        "implementationFingerprintAtStart": baseline_hash,
        "implementationSourceManifest": list(IMPLEMENTATION_SOURCE_FILES),
    }
    partial_path = output_path.with_name(output_path.stem + ".partial.json")
    _write(partial_path, {**base, "stage": "running", "rows": rows})

    for requested in protocol["requestedMaxDt_s"]:
        before_hash = implementation_fingerprint()
        row = _case_result(scenario, "maxDt_s", requested)
        after_hash = implementation_fingerprint()
        recorded_hash = row.get("provenance", {}).get("implementationHash")
        row["implementationIntegrity"] = {
            "before": before_hash,
            "recorded": recorded_hash,
            "after": after_hash,
            "stable": before_hash == recorded_hash == after_hash,
        }
        rows.append(row)
        _write(partial_path, {**base, "stage": "running", "rows": rows,
                              "lastCompletedAt": datetime.datetime.now(
                                  datetime.timezone.utc).isoformat()})

    assessment = _axis(rows, "actualMeanDt_s")
    integrity = "pass" if all(row["implementationIntegrity"]["stable"]
                              for row in rows) else "failed"
    status = ("failed" if integrity == "failed" or assessment["status"] == "failed"
              else assessment["status"])
    final = {**base, "rows": rows, "assessment": assessment,
             "integrityStatus": integrity,
             "assessmentModuleSha256AtEnd": _sha256(assessment_path.read_bytes()),
             "implementationFingerprintAtEnd": implementation_fingerprint(),
             "stage": "completed", "status": status,
             "completedAt": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    if (final["implementationFingerprintAtEnd"] != baseline_hash
            or final["assessmentModuleSha256AtEnd"] != assessment_hash):
        final["integrityStatus"] = "failed"
        final["status"] = "failed"
    _write(output_path, final)
    _write(partial_path, final)
    print(json.dumps({"status": final["status"], "integrityStatus": final["integrityStatus"],
                      "assessment": assessment["status"], "output": str(output_path)}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("scenario", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    run_protocol(args.protocol, args.scenario, args.output)


if __name__ == "__main__":
    main()
