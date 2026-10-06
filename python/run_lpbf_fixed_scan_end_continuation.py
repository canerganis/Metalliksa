"""Continue the frozen five-case fixed scan-end study from audited coarse rows."""

import argparse
import copy
import datetime
import hashlib
import io
import json
import math
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_lpbf_fixed_scan_end_convergence as original
from lpbf_fixed_scan_end_observation import FIELD_NAMES, TEMPORAL_SELECTION
from lpbf_peak import interpolated_peak_melt_pool
from lpbf_simulation import implementation_fingerprint, validate

ADDENDUM_PATH = ROOT / "docs" / "LPBF_P4_FIXED_SCAN_END_REUSE_ADDENDUM_2026-09-27.json"
COARSE_REPORT_PATH = ROOT / "docs" / "LPBF_P4_FIXED_SCAN_END_OBSERVATION_CHECK_2026-09-27.json"
COARSE_FIELD_DIRECTORY = ROOT / "docs" / "LPBF_P4_FIXED_SCAN_END_OBSERVATION_CHECK_FIELDS_2026-09-27"
OUTPUT_PATH = ROOT / "docs" / "LPBF_P4_FIXED_SCAN_END_CONTINUATION_2026-09-27.json"
FIELD_DIRECTORY = ROOT / "docs" / "LPBF_P4_FIXED_SCAN_END_CONTINUATION_FIELDS_2026-09-27"
EXPECTED_COARSE_REPORT_SHA256 = "e35bc891d167db66e39c3ee7a24daf4f2cdbbd0a103dadf3da8bbc9efb0948a7"
EXPECTED_PROTOCOL_SHA256 = "a384c0e0a72aa8fe1bf3a5543d70c0558971a5a9a8dcea45550c034c58cd93e1"
EXPECTED_COARSE_RUNNER_SHA256 = "1e70784260b2987bb13378223e2832a32e3bbb804d27c9d764a59d6235c68021"
EXPECTED_EXECUTION_HEAD = "4c155132ffa0141ff31f6eb0b865d718e2f9a72d"
EXPECTED_INPUT_HASHES = {
    20: "98ba7cb77c7f3c71c0a402c66897070232831bfed6b640cb4737f2123fec767a",
    10: "ae5b179d5260e8356c993f066d92e329ac3913a70f46153dbe3ec9df17eb81a1",
}
EXPECTED_MATERIAL_REVISION_SHA256 = "c90d2094ca2b5162b26399347a6fb0f9d703b1a05e8aa0883d9d9672012e8c06"
ORIGINAL_PROTOCOL_ID = "lpbf-p4-fixed-scan-end-liquidus-contour-2026-09-27-v1"
ADDENDUM_ID = "lpbf-p4-fixed-scan-end-coarse-reuse-addendum-2026-09-27-v1"


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _assert_frozen_sources(protocol, addendum_sha, wrapper_sha, addendum):
    paths = {
        "protocol": (original.PROTOCOL_PATH, EXPECTED_PROTOCOL_SHA256),
        "scenario": (original.SCENARIO_PATH, protocol["scenarioSha256"]),
        "runner": (Path(__file__).with_name(Path(protocol["runnerFile"]).name), protocol["runnerSha256"]),
        "observation": (Path(__file__).with_name("lpbf_fixed_scan_end_observation.py"),
                        protocol["observationModuleSha256"]),
        "assessment": (original.ASSESSMENT_PATH, protocol["assessmentModuleSha256"]),
        "contour": (original.CONTOUR_PATH, protocol["contourModuleSha256"]),
        "coarseReport": (COARSE_REPORT_PATH, EXPECTED_COARSE_REPORT_SHA256),
        "addendum": (ADDENDUM_PATH, addendum_sha),
        "wrapper": (Path(__file__), wrapper_sha),
    }
    for name, (path, expected) in paths.items():
        if _sha256_file(path) != expected:
            raise ValueError(f"Frozen {name} bytes changed during continuation")
    for row in addendum["coarseEvidence"]["rows"]:
        path = COARSE_FIELD_DIRECTORY / row["fieldArtifact"]
        if _sha256_file(path) != row["fieldArtifactSha256"]:
            raise ValueError("A reused coarse field artifact changed during continuation")
    if implementation_fingerprint() != protocol["expectedImplementationFingerprint"]:
        raise ValueError("Numerical implementation fingerprint changed during continuation")


def _reject_existing_attempt(output, partial, fields):
    if output.exists() or partial.exists() or fields.exists():
        raise FileExistsError("Continuation output already exists; never replace a failed attempt")


def _expected_cases(protocol):
    all_cases = original._case_specs(protocol)
    retained = {(20, protocol["fixedMeshMaxDt_s"]), (10, protocol["fixedMeshMaxDt_s"])}
    reuse = [case for case in all_cases if (case["mesh_um"], case["maxDt_s"]) in retained]
    execute = [case for case in all_cases if (case["mesh_um"], case["maxDt_s"]) not in retained]
    if ([(case["mesh_um"], case["maxDt_s"]) for case in reuse]
            != [(20, protocol["fixedMeshMaxDt_s"]), (10, protocol["fixedMeshMaxDt_s"])]
            or [(case["mesh_um"], case["maxDt_s"]) for case in execute]
            != [(5, protocol["fixedMeshMaxDt_s"]), (5, protocol["timeLevels_s"][0]),
                (5, protocol["timeLevels_s"][2])]
            or len(all_cases) != 5):
        raise ValueError("Continuation must preserve exactly two coarse and three missing cases")
    return all_cases, reuse, execute


def _load_npz(path, expected_shapes, max_uncompressed_bytes, expected_uncompressed_bytes,
              expected_file_sha256, expected_file_size):
    path = Path(path)
    if (path.is_symlink() or not path.is_file()
            or path.stat().st_size != expected_file_size
            or path.stat().st_size > max_uncompressed_bytes):
        raise ValueError("Reused field artifact is missing or linked")
    data = path.read_bytes()
    if (len(data) != expected_file_size or len(data) > max_uncompressed_bytes
            or _sha256_bytes(data) != expected_file_sha256):
        raise ValueError("Reused field artifact bytes differ from the bounded descriptor")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        expected_members = {f"{name}.npy" for name in FIELD_NAMES}
        if (len(infos) != len(expected_members)
                or len({info.filename for info in infos}) != len(infos)
                or {info.filename for info in infos} != expected_members):
            raise ValueError("Reused field artifact has an unexpected array set")
        if (any(info.file_size < 0 or info.compress_size < 0
                or info.file_size > max_uncompressed_bytes for info in infos)
                or sum(info.file_size for info in infos) > max_uncompressed_bytes):
            raise ValueError("Reused field artifact exceeds its ZIP member byte bound")
        payload_total = 0
        for name in FIELD_NAMES:
            info = next(item for item in infos if item.filename == f"{name}.npy")
            with archive.open(info) as member:
                version = np.lib.format.read_magic(member)
                if version == (1, 0):
                    shape, _fortran_order, dtype = np.lib.format.read_array_header_1_0(member)
                elif version in ((2, 0), (3, 0)):
                    shape, _fortran_order, dtype = np.lib.format.read_array_header_2_0(member)
                else:
                    raise ValueError("Reused field artifact has an unsupported NPY version")
                dtype = np.dtype(dtype)
                if (shape != expected_shapes[name] or dtype.kind != "f" or dtype.itemsize != 8
                        or dtype.byteorder == ">"):
                    raise ValueError(f"Reused field array header is invalid for {name}")
                payload_bytes = math.prod(shape) * dtype.itemsize
                if (payload_bytes > max_uncompressed_bytes
                        or member.tell() + payload_bytes != info.file_size):
                    raise ValueError(f"Reused field array payload is invalid for {name}")
                payload_total += payload_bytes
        if payload_total != expected_uncompressed_bytes:
            raise ValueError("Reused field artifact declared uncompressed byte count differs")
    with np.load(io.BytesIO(data), allow_pickle=False) as archive:
        arrays = {name: np.ascontiguousarray(archive[name]) for name in FIELD_NAMES}
    for name, array in arrays.items():
        if (array.dtype.kind != "f" or array.dtype.itemsize != 8 or array.dtype.byteorder == ">"
                or not np.isfinite(array).all()):
            raise ValueError(f"Reused field array {name} is not finite float64")
    return arrays


def _resolved_case_identity(scenario, spec, row):
    request = copy.deepcopy(scenario)
    request.update(mesh_um=spec["mesh_um"], maxDt_s=spec["maxDt_s"])
    resolved, material = validate(request)
    expected_input_hash = _sha256_bytes(json.dumps(
        resolved, sort_keys=True, allow_nan=False).encode("utf-8"))
    if row.get("provenance", {}).get("inputHash") != expected_input_hash:
        raise ValueError("Reused coarse row resolved input identity differs")
    reported_material = row.get("material")
    material_identity = (material.get("name"), material.get("materialId"),
                         material.get("materialRevisionSha256"), material.get("version"))
    reported_identity = (reported_material.get("name"), reported_material.get("materialId"),
                         reported_material.get("materialRevisionSha256"), reported_material.get("version")) \
        if isinstance(reported_material, dict) else None
    if reported_identity != material_identity:
        raise ValueError("Reused coarse row material identity differs from the frozen scenario")
    if (row.get("model") != {
            "modelId": "stationary-enthalpy-conduction-layer-conforming-v1",
            "actualBackend": "numpy-reference", "solverId": "enthalpy-fv-6"}):
        raise ValueError("Reused coarse row model identity differs")
    return resolved, material


def _verify_row_energy(row, tolerance):
    energy = row.get("energyBalance")
    if not isinstance(energy, dict):
        raise ValueError("Reused coarse row has no final energy balance")
    values = [energy.get(key) for key in ("input_J", "losses_J", "stored_J", "relativeError")]
    if any(isinstance(value, bool) or not isinstance(value, (int, float)
               ) or not math.isfinite(value) for value in values):
        raise ValueError("Reused coarse row energy values are invalid")
    input_j, losses_j, stored_j, recorded = values
    measured = abs(input_j - losses_j - stored_j) / max(abs(input_j), 1e-30)
    if (energy.get("denominator") != "input_J"
            or energy.get("reference") != "initial enthalpy at preheat"
            or input_j <= 0 or losses_j < 0 or stored_j < 0 or recorded < 0
            or abs(recorded - measured) > 1e-12 or measured > tolerance):
        raise ValueError("Reused coarse row final energy closure does not pass")


def _verify_selected_field(row, spec, protocol, resolved, material, field_directory):
    artifact = row.get("fieldArtifact")
    expected_name = f"mesh-{spec['mesh_um']:g}um.npz"
    if (not isinstance(artifact, dict) or artifact.get("path") != expected_name
            or artifact.get("scope") != "CPU numerical diagnostic fields only; not a run archive or experimental evidence"
            or artifact.get("format") != "numpy-npz-compressed-little-endian-float64-v1"):
        raise ValueError("Reused coarse row field descriptor identity differs")
    path = Path(field_directory) / expected_name
    cells = row.get("cells")
    if type(cells) is not int or cells <= 0:
        raise ValueError("Reused coarse row cell count is invalid")
    declared_steps = artifact.get("steps")
    if type(declared_steps) is not int or declared_steps <= 0:
        raise ValueError("Reused selected-state step count is invalid")
    expected_shapes = {"coordinates_m": (cells, 3), "temperature_K": (cells,),
                       "enthalpy_J_m3": (cells,), "density_kg_m3": (cells,),
                       "accepted_dt_s": (declared_steps,)}
    arrays = _load_npz(path, expected_shapes, protocol["maxUncompressedFieldBytes"],
                       artifact.get("uncompressedBytes"), artifact.get("sha256"),
                       artifact.get("byteSize"))
    for name, shape in expected_shapes.items():
        if arrays[name].shape != shape:
            raise ValueError(f"Reused coarse field shape differs for {name}")
    accepted_dt = arrays["accepted_dt_s"]
    if (declared_steps != 10_000 or row.get("steps") != 14_000
            or accepted_dt.ndim != 1 or accepted_dt.size != artifact.get("steps")
            or accepted_dt.size <= 0 or np.any(accepted_dt <= 0)):
        raise ValueError("Reused selected-state accepted timestep array is invalid")
    replayed_time = 0.0
    for step in accepted_dt:
        next_time = replayed_time + float(step)
        if not math.isfinite(next_time) or next_time <= replayed_time:
            raise ValueError("Reused selected-state accepted timesteps do not advance")
        replayed_time = next_time
    selected_time = artifact.get("actualTime_s")
    target_time = protocol["targetTime_s"]
    if (replayed_time != selected_time or artifact.get("schedulerTime_s") != selected_time
            or artifact.get("targetTime_s") != target_time
            or artifact.get("targetMinusActualTime_s") != target_time - selected_time
            or abs(target_time - selected_time) > artifact.get("roundoffTolerance_s", 0)):
        raise ValueError("Reused selected state is not the original first scan-end event")
    if sum(array.nbytes for array in arrays.values()) != artifact.get("uncompressedBytes"):
        raise ValueError("Reused selected-state uncompressed byte count differs")
    if not isinstance(artifact.get("fieldSha256"), dict) or set(artifact["fieldSha256"]) != set(FIELD_NAMES):
        raise ValueError("Reused coarse array hash manifest is incomplete")
    for name in FIELD_NAMES:
        digest = hashlib.sha256(memoryview(arrays[name]).cast("B")).hexdigest()
        if artifact.get("fieldSha256", {}).get(name) != digest:
            raise ValueError(f"Reused coarse array hash differs for {name}")

    energy = row["energyBalance"]
    _verify_row_energy(row, original.ACCEPTANCE["energyRelativeErrorMax"])
    # Selected arrays stop at 250 us; final report energy is at the later cooling endpoint.
    contour = interpolated_peak_melt_pool(
        arrays["coordinates_m"], arrays["temperature_K"], protocol["surfaceZ_m"],
        resolved["scanAngle_deg"], row["actualMesh_m"], material["liquidus_K"])
    contour.update(temporalSelection=protocol["temporalSelection"],
                   observationOperator=protocol["contourOperator"],
                   targetTime_s=artifact["targetTime_s"],
                   actualTime_s=artifact["actualTime_s"],
                   targetMinusActualTime_s=artifact["targetMinusActualTime_s"],
                   roundoffTolerance_s=artifact["roundoffTolerance_s"],
                   evidenceScope="Numerical thermal proxy; no experimental validation")
    stored = row.get("fixedScanEndObservation")
    for key in contour:
        if contour.get(key) != stored.get(key):
            raise ValueError(f"Recomputed coarse contour differs for {key}")
    if (stored.get("temporalSelection") != TEMPORAL_SELECTION
            or stored.get("observationOperator") != protocol["contourOperator"]
            or stored.get("targetTime_s") != target_time
            or stored.get("actualTime_s") != selected_time
            or stored.get("evidenceScope") != "Numerical thermal proxy; no experimental validation"):
        raise ValueError("Reused coarse contour temporal or evidence identity differs")
    return arrays


def _audit_coarse_rows(protocol, scenario, specs, report, field_directory):
    if (not isinstance(report, dict) or report.get("schemaVersion") != 1
            or report.get("scope") != "Two coarse fixed scan-end observation checks; insufficient levels for convergence"
            or report.get("stage") != "completed" or report.get("experimentalValidation") is not False
            or report.get("convergenceStatus") != "unvalidated"
            or report.get("protocolSha256") != _sha256_file(original.PROTOCOL_PATH)
            or report.get("implementationHash") != implementation_fingerprint()
            or report.get("runnerSha256") != EXPECTED_COARSE_RUNNER_SHA256
            or report.get("executionHead") != EXPECTED_EXECUTION_HEAD
            or _sha256_bytes(report.get("runnerText", "").encode("utf-8")) != report.get("runnerSha256")):
        raise ValueError("Coarse observation report provenance is not admissible")
    expected_cases, reuse_specs, _ = _expected_cases(protocol)
    coarse_specs = [spec for spec in expected_cases
                    if (spec["mesh_um"], spec["maxDt_s"]) in
                    {(item["mesh_um"], item["maxDt_s"]) for item in reuse_specs}]
    rows = report.get("rows")
    if not isinstance(rows, list) or len(rows) != len(coarse_specs):
        raise ValueError("Coarse observation report must contain exactly the two frozen rows")
    by_key = {}
    for row in rows:
        key = (row.get("mesh_um"), row.get("requestedMaxDt_s")) if isinstance(row, dict) else None
        if key in by_key:
            raise ValueError("Coarse observation report contains duplicate rows")
        by_key[key] = row
    admitted = []
    for spec in coarse_specs:
        key = (spec["mesh_um"], spec["maxDt_s"])
        row = by_key.get(key)
        if not isinstance(row, dict) or row.get("status") != "completed":
            raise ValueError("A required coarse scan-end row is absent or failed")
        if row.get("requested") != {"mesh_um": spec["mesh_um"], "maxDt_s": spec["maxDt_s"]}:
            raise ValueError("Coarse row requested mesh/timestep identity differs")
        if row.get("axes") != spec["axes"]:
            raise ValueError("Coarse row study-axis identity differs")
        resolved, material = _resolved_case_identity(scenario, spec, row)
        if (row["provenance"]["inputHash"] != EXPECTED_INPUT_HASHES[spec["mesh_um"]]
                or material.get("materialRevisionSha256") != EXPECTED_MATERIAL_REVISION_SHA256):
            raise ValueError("Coarse resolved input or material revision differs from the audited record")
        _verify_selected_field(row, spec, protocol, resolved, material, field_directory)
        copy_row = copy.deepcopy(row)
        copy_row["executionOrigin"] = {
            "kind": "reused-coarse-observation-check",
            "caseOrdinal": len(admitted) + 1,
            "report": "docs/LPBF_P4_FIXED_SCAN_END_OBSERVATION_CHECK_2026-09-27.json",
            "reportSha256": _sha256_file(COARSE_REPORT_PATH),
            "fieldArtifact": row["fieldArtifact"]["path"],
            "fieldArtifactSha256": row["fieldArtifact"]["sha256"],
            "reconstructedInputs": {
                "provenance": "Reconstructed by validate() from the frozen scenario and current fingerprint-pinned source; not captured at the coarse run.",
                "inputHash": row["provenance"]["inputHash"],
                "settings": resolved,
                "material": material,
            },
        }
        admitted.append(copy_row)
    return admitted


def _addendum_evidence(protocol, scenario, coarse_rows, wrapper_hash):
    _, _, new_specs = _expected_cases(protocol)
    new_cases = []
    for index, spec in enumerate(new_specs, start=3):
        request = copy.deepcopy(scenario)
        request.update(mesh_um=spec["mesh_um"], maxDt_s=spec["maxDt_s"])
        resolved, material = validate(request)
        new_cases.append({
            "caseOrdinal": index,
            "mesh_um": spec["mesh_um"],
            "maxDt_s": spec["maxDt_s"],
            "resolvedInputHash": _sha256_bytes(json.dumps(
                resolved, sort_keys=True, allow_nan=False).encode("utf-8")),
            "resolvedInputs": {
                "provenance": "Predeclared by validate() from the frozen scenario and fingerprint-pinned source; execution must match.",
                "settings": resolved,
                "material": material,
            },
        })
    return {
        "schemaVersion": 1,
        "addendumId": ADDENDUM_ID,
        "createdAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "change": {
            "reason": "The coarse fixed-scan-end observation check completed before this reuse amendment.",
            "beforeFineExecution": True,
            "executionPlan": "Reuse only the completed 20 um and 10 um rows; execute each of the three missing 5 um cases exactly once.",
            "thresholdsChanged": False,
            "originalProtocolOrRunnerChanged": False,
            "failedRowsReplaced": False,
        },
        "originalProtocol": {
            "protocolId": protocol["protocolId"],
            "path": "docs/LPBF_P4_FIXED_SCAN_END_CONVERGENCE_PROTOCOL_2026-09-27.json",
            "sha256": _sha256_file(original.PROTOCOL_PATH),
            "runnerPath": protocol["runnerFile"],
            "runnerSha256": protocol["runnerSha256"],
            "scenarioSha256": protocol["scenarioSha256"],
            "observationModuleSha256": protocol["observationModuleSha256"],
            "assessmentModuleSha256": protocol["assessmentModuleSha256"],
            "contourModuleSha256": protocol["contourModuleSha256"],
            "implementationFingerprint": protocol["expectedImplementationFingerprint"],
        },
        "continuationWrapper": {
            "path": "python/run_lpbf_fixed_scan_end_continuation.py",
            "sha256": wrapper_hash,
            "reportPath": OUTPUT_PATH.relative_to(ROOT).as_posix(),
            "partialPath": OUTPUT_PATH.with_name(OUTPUT_PATH.stem + ".partial.json").relative_to(ROOT).as_posix(),
            "fieldDirectory": FIELD_DIRECTORY.relative_to(ROOT).as_posix(),
        },
        "coarseEvidence": {
            "path": "docs/LPBF_P4_FIXED_SCAN_END_OBSERVATION_CHECK_2026-09-27.json",
            "sha256": _sha256_file(COARSE_REPORT_PATH),
            "executionHead": EXPECTED_EXECUTION_HEAD,
            "runnerSha256": EXPECTED_COARSE_RUNNER_SHA256,
            "fieldDirectory": "docs/LPBF_P4_FIXED_SCAN_END_OBSERVATION_CHECK_FIELDS_2026-09-27",
            "rows": [{
                "caseOrdinal": index + 1,
                "mesh_um": row["mesh_um"],
                "requestedMaxDt_s": row["requestedMaxDt_s"],
                "inputHash": row["provenance"]["inputHash"],
                "materialRevisionSha256": row["material"]["materialRevisionSha256"],
                "rowSha256": _sha256_bytes(_canonical({key: value for key, value in row.items()
                                                        if key != "executionOrigin"}).encode("utf-8")),
                "fieldArtifact": row["fieldArtifact"]["path"],
                "fieldArtifactSha256": row["fieldArtifact"]["sha256"],
                "fieldArraySha256": row["fieldArtifact"]["fieldSha256"],
                "reconstructedInputs": copy.deepcopy(row["executionOrigin"]["reconstructedInputs"]),
            } for index, row in enumerate(coarse_rows)],
        },
        "scope": "CPU numerical thermal proxy at the first scan end; no experimental validation",
        "energyTimingBoundary": "Coarse final energy is reported at 350 us; selected field artifacts stop at 250 us. Do not compare selected-state H integrals to final-time stored energy.",
        "allFiveUniqueCasesRetained": True,
        "newCases": new_cases,
    }


def prepare_addendum():
    """Write the approved reuse amendment once, without launching any solver."""
    if ADDENDUM_PATH.exists():
        raise FileExistsError("Reuse addendum already exists; preserve its original bytes")
    protocol, scenario, specs, fingerprint, *_ = original.preflight()
    if (protocol["protocolId"] != ORIGINAL_PROTOCOL_ID
            or fingerprint != protocol["expectedImplementationFingerprint"]
            or _sha256_file(original.PROTOCOL_PATH) != EXPECTED_PROTOCOL_SHA256
            or _sha256_file(COARSE_REPORT_PATH) != EXPECTED_COARSE_REPORT_SHA256):
        raise ValueError("Frozen protocol, implementation, or coarse report identity changed")
    coarse_report = json.loads(COARSE_REPORT_PATH.read_bytes())
    coarse_rows = _audit_coarse_rows(protocol, scenario, specs, coarse_report, COARSE_FIELD_DIRECTORY)
    _write_json(ADDENDUM_PATH, _addendum_evidence(
        protocol, scenario, coarse_rows, _sha256_file(Path(__file__))))
    return ADDENDUM_PATH


def preflight():
    protocol, scenario, specs, fingerprint, _output, _partial, _fields, protocol_sha, scenario_document = original.preflight()
    output = OUTPUT_PATH
    partial = output.with_name(output.stem + ".partial.json")
    fields = FIELD_DIRECTORY
    _reject_existing_attempt(output, partial, fields)
    if (protocol["protocolId"] != ORIGINAL_PROTOCOL_ID
            or fingerprint != protocol["expectedImplementationFingerprint"]
            or _sha256_file(original.PROTOCOL_PATH) != EXPECTED_PROTOCOL_SHA256
            or _sha256_file(COARSE_REPORT_PATH) != EXPECTED_COARSE_REPORT_SHA256
            or not ADDENDUM_PATH.is_file()):
        raise ValueError("Frozen protocol, implementation, coarse report, or reuse addendum changed")
    addendum = json.loads(ADDENDUM_PATH.read_bytes())
    coarse_report = json.loads(COARSE_REPORT_PATH.read_bytes())
    wrapper_hash = _sha256_file(Path(__file__))
    if (addendum.get("schemaVersion") != 1 or addendum.get("addendumId") != ADDENDUM_ID
            or addendum.get("continuationWrapper") != {
                "path": "python/run_lpbf_fixed_scan_end_continuation.py", "sha256": wrapper_hash,
                "reportPath": OUTPUT_PATH.relative_to(ROOT).as_posix(),
                "partialPath": OUTPUT_PATH.with_name(OUTPUT_PATH.stem + ".partial.json").relative_to(ROOT).as_posix(),
                "fieldDirectory": FIELD_DIRECTORY.relative_to(ROOT).as_posix()}
            or addendum.get("originalProtocol", {}).get("sha256") != protocol_sha
            or addendum.get("originalProtocol", {}).get("implementationFingerprint") != fingerprint
            or addendum.get("coarseEvidence", {}).get("sha256") != EXPECTED_COARSE_REPORT_SHA256
            or addendum.get("coarseEvidence", {}).get("runnerSha256") != EXPECTED_COARSE_RUNNER_SHA256
            or addendum.get("coarseEvidence", {}).get("executionHead") != EXPECTED_EXECUTION_HEAD
            or addendum.get("coarseEvidence", {}).get("path") != COARSE_REPORT_PATH.relative_to(ROOT).as_posix()
            or addendum.get("coarseEvidence", {}).get("fieldDirectory") != COARSE_FIELD_DIRECTORY.relative_to(ROOT).as_posix()
            or addendum.get("change", {}).get("beforeFineExecution") is not True
            or addendum.get("change", {}).get("failedRowsReplaced") is not False
            or addendum.get("change", {}).get("thresholdsChanged") is not False
            or addendum.get("change", {}).get("originalProtocolOrRunnerChanged") is not False
            or addendum.get("allFiveUniqueCasesRetained") is not True):
        raise ValueError("Reuse addendum does not bind this continuation to the frozen sources")
    reused = _audit_coarse_rows(protocol, scenario, specs, coarse_report, COARSE_FIELD_DIRECTORY)
    expected_evidence = _addendum_evidence(protocol, scenario, reused, wrapper_hash)
    expected_rows = expected_evidence["coarseEvidence"]["rows"]
    if addendum.get("coarseEvidence", {}).get("rows") != expected_rows:
        raise ValueError("Reuse addendum coarse row or array identity differs from the preserved evidence")
    all_cases, _, new_cases = _expected_cases(protocol)
    if addendum.get("newCases") != expected_evidence["newCases"]:
        raise ValueError("Reuse addendum does not retain the three predeclared missing cases")
    _assert_frozen_sources(protocol, _sha256_file(ADDENDUM_PATH), wrapper_hash, addendum)
    return (protocol, scenario, all_cases, new_cases, reused, fingerprint,
            output, partial, fields, protocol_sha, scenario_document, addendum,
            _sha256_file(ADDENDUM_PATH), wrapper_hash)


def _failed_row(spec, error, ordinal, solver_invoked):
    return {
        "axes": list(spec["axes"]),
        "requested": {"mesh_um": spec["mesh_um"], "maxDt_s": spec["maxDt_s"]},
        "mesh_um": spec["mesh_um"], "requestedMaxDt_s": spec["maxDt_s"],
        "status": "failed", "executionOrigin": {
            "kind": "new-continuation-execution", "caseOrdinal": ordinal,
            "solverInvoked": solver_invoked, "attemptCount": 1,
        },
        "failure": {"type": type(error).__name__, "message": str(error)},
    }


def _not_started_row(spec, ordinal, reason):
    return {
        "axes": list(spec["axes"]),
        "requested": {"mesh_um": spec["mesh_um"], "maxDt_s": spec["maxDt_s"]},
        "mesh_um": spec["mesh_um"], "requestedMaxDt_s": spec["maxDt_s"],
        "status": "not-run", "executionOrigin": {
            "kind": "new-continuation-not-started", "caseOrdinal": ordinal,
            "solverInvoked": False, "attemptCount": 0,
        },
        "failure": {"type": "ContinuationStopped", "message": reason},
    }


def execute():
    try:
        (protocol, scenario, all_cases, new_cases, reused, fingerprint, output, partial,
         fields, protocol_sha, scenario_document, addendum, addendum_sha, wrapper_hash) = preflight()
    except Exception as error:
        if (not OUTPUT_PATH.exists() and not OUTPUT_PATH.with_name(OUTPUT_PATH.stem + ".partial.json").exists()
                and not FIELD_DIRECTORY.exists()):
            _write_json(OUTPUT_PATH.with_name(OUTPUT_PATH.stem + ".partial.json"), {
                "schemaVersion": 1, "continuationId": "lpbf-p4-fixed-scan-end-continuation-2026-09-27-v1",
                "stage": "preflight-failed", "status": "failed", "solverLaunched": False,
                "failure": {"type": type(error).__name__, "message": str(error)},
                "experimentalValidation": False,
                "recordedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            })
        raise
    _reject_existing_attempt(output, partial, fields)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()
    report = {
        "schemaVersion": 1, "continuationId": "lpbf-p4-fixed-scan-end-continuation-2026-09-27-v1",
        "originalProtocolId": protocol["protocolId"], "originalProtocolSha256": protocol_sha,
        "reuseAddendumPath": ADDENDUM_PATH.relative_to(ROOT).as_posix(),
        "reuseAddendumSha256": addendum_sha, "continuationWrapperSha256": wrapper_hash,
        "coarseReportPath": addendum["coarseEvidence"]["path"],
        "coarseReportSha256": EXPECTED_COARSE_REPORT_SHA256,
        "scenarioSha256": protocol["scenarioSha256"],
        "runnerSha256": protocol["runnerSha256"],
        "observationModuleSha256": protocol["observationModuleSha256"],
        "assessmentModuleSha256": protocol["assessmentModuleSha256"],
        "contourModuleSha256": protocol["contourModuleSha256"],
        "implementationFingerprintAtStart": fingerprint,
        "implementationFingerprintAtEnd": None,
        "implementationSourceManifest": list(original.IMPLEMENTATION_SOURCE_FILES),
        "executionHeadCommit": head, "scope": protocol["scope"],
        "experimentalValidation": False,
        "priorFrozenP4Status": protocol["priorFrozenP4Status"],
        "fixedObservation": {"operator": protocol["contourOperator"],
                             "spatialOperator": protocol["spatialOperator"],
                             "temporalSelection": protocol["temporalSelection"],
                             "targetTime_s": protocol["targetTime_s"],
                             "beamCenterX_m": protocol["beamCenterX_m"],
                             "surfaceZ_m": protocol["surfaceZ_m"]},
        "acceptance": copy.deepcopy(original.ACCEPTANCE),
        "allFiveUniqueCases": [{"caseOrdinal": index + 1, "mesh_um": case["mesh_um"], "maxDt_s": case["maxDt_s"],
                                "axes": list(case["axes"])} for index, case in enumerate(all_cases)],
        "reusedRows": reused, "newRows": [], "stage": "running",
        "startedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    _write_json(partial, report)
    fields.mkdir(parents=True)
    stop_reason = None
    for case_index, spec in enumerate(new_cases, start=3):
        payload = copy.deepcopy(scenario)
        payload.update(mesh_um=spec["mesh_um"], maxDt_s=spec["maxDt_s"])
        solver_invoked = False
        partial_evidence = {}
        try:
            _assert_frozen_sources(protocol, addendum_sha, wrapper_hash, addendum)
        except Exception as error:
            stop_reason = str(error)
            report["newRows"].append(_failed_row(spec, error, case_index, False))
            _write_json(partial, report)
            break
        try:
            before = implementation_fingerprint()
            if before != fingerprint:
                raise ValueError("Frozen implementation changed before a continuation row")
            observed = []
            solver_invoked = True
            result = original.run(payload, selected_time_observer=observed.append,
                                  selected_time_s=protocol["targetTime_s"])
            after = implementation_fingerprint()
            if after != fingerprint:
                raise ValueError("Frozen implementation changed during a continuation row")
            _assert_frozen_sources(protocol, addendum_sha, wrapper_hash, addendum)
            if len(observed) != 1:
                raise ValueError("Each new run must produce exactly one accepted scan-end state")
            snapshot = observed[0]
            liquidus = result["material"].get("liquidus_K")
            if isinstance(liquidus, bool) or not isinstance(liquidus, (int, float)) \
                    or not math.isfinite(liquidus) or liquidus <= 0:
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
            from lpbf_fixed_scan_end_observation import write_selected_state_artifact
            artifact = write_selected_state_artifact(snapshot, artifact_path)
            artifact["path"] = artifact_path.relative_to(ROOT).as_posix()
            partial_evidence = {"fieldArtifact": copy.deepcopy(artifact),
                                "fixedScanEndObservation": copy.deepcopy(contour)}
            row = original._row_from_result(spec, result, contour, artifact, before, after, fingerprint)
            predeclared = addendum["newCases"][case_index - 3]
            if (row["provenance"].get("inputHash") != predeclared["resolvedInputHash"]
                    or result.get("settings") != predeclared["resolvedInputs"]["settings"]
                    or result.get("material") != predeclared["resolvedInputs"]["material"]):
                raise ValueError("Executed resolved settings/material differ from the predeclared addendum case")
            row["executionOrigin"] = {"kind": "new-continuation-execution",
                                       "caseOrdinal": case_index,
                                       "solverInvoked": True, "attemptCount": 1,
                                       "continuationWrapperSha256": wrapper_hash,
                                       "reuseAddendumSha256": addendum_sha,
                                       "resolvedInputs": {
                                           "provenance": "Captured from this continuation run.",
                                           "inputHash": row["provenance"]["inputHash"],
                                           "settings": copy.deepcopy(result["settings"]),
                                           "material": copy.deepcopy(result["material"]),
                                       }}
            identity = (row["model"]["modelId"], row["model"]["actualBackend"],
                        row["model"]["solverId"], row["material"]["materialId"],
                        row["material"]["materialRevisionSha256"])
            expected_identity = (reused[0]["model"]["modelId"], reused[0]["model"]["actualBackend"],
                                 reused[0]["model"]["solverId"], reused[0]["material"]["materialId"],
                                 reused[0]["material"]["materialRevisionSha256"])
            if identity != expected_identity:
                raise ValueError("Model or material identity changed between reused and new rows")
        except Exception as error:
            row = _failed_row(spec, error, case_index, solver_invoked)
            if partial_evidence:
                row["partialEvidence"] = partial_evidence
        report["newRows"].append(row)
        _write_json(partial, report)
        try:
            _assert_frozen_sources(protocol, addendum_sha, wrapper_hash, addendum)
        except Exception as error:
            stop_reason = str(error)
            break
    if stop_reason is not None:
        for case_index, spec in enumerate(new_cases[len(report["newRows"]):],
                                          start=3 + len(report["newRows"])):
            report["newRows"].append(_not_started_row(spec, case_index, stop_reason))
            _write_json(partial, report)
    all_rows = reused + report["newRows"]
    assessment_rows = [row for row in all_rows if row.get("status") == "completed"]
    if len(assessment_rows) != len(all_cases):
        mesh_assessment = {"status": "failed", "reason": "At least one predeclared row failed; all outcomes are retained"}
        time_assessment = copy.deepcopy(mesh_assessment)
    else:
        mesh_assessment = original._assessment_rows(all_rows, all_cases, "mesh")
        time_assessment = original._assessment_rows(all_rows, all_cases, "time")
    after_all = implementation_fingerprint()
    freeze_failure = None
    try:
        _assert_frozen_sources(protocol, addendum_sha, wrapper_hash, addendum)
    except Exception as error:
        freeze_failure = {"type": type(error).__name__, "message": str(error)}
    report.update(
        implementationFingerprintAtEnd=after_all,
        meshAssessment=mesh_assessment, timeAssessment=time_assessment,
        status="failed" if freeze_failure is not None
        or "failed" in (mesh_assessment["status"], time_assessment["status"])
        else "inconclusive" if "inconclusive" in (mesh_assessment["status"], time_assessment["status"])
        else "pass",
        stage="completed", completedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        contourEvidenceScope="Numerical thermal proxy only; not an etched-optical section or experimental validation")
    if freeze_failure is not None:
        report["freezeFailure"] = freeze_failure
    _write_json(output, report)
    _write_json(partial, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-addendum", action="store_true",
                        help="write the one-time reuse amendment after audit; do not launch solver rows")
    args = parser.parse_args()
    path = prepare_addendum() if args.prepare_addendum else execute()
    print(json.dumps({"path": str(path), "mode": "addendum-only" if args.prepare_addendum else "continued"}, indent=2))


if __name__ == "__main__":
    main()
