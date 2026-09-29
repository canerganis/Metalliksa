"""AMB2022-03 Table 4 optical geometry comparison gate.

The caller must supply Table 4 rows loaded from a verified source archive and
the archive's trusted expected revision/document SHA. This module neither
fetches observations nor upgrades a thermal section to an optical observation.
"""

import hashlib
import json
import math
import re

from four_alloy_materials import resolve_alloy_id
from lpbf_core_contract import enforce_core_contract


RESULTS_URL = "https://www.nist.gov/document/am-bench-amb2022-03-measurement-and-result-descriptions-v10"
METHODS_URL = "https://www.nist.gov/document/amb2022-03-measurement-and-challenge-descriptions-version-101"
ARCHIVE_DATASET_ID = "nist-amb2022-03-optical-table4-local-v1"
SOURCE_DATASET_ID = "nist-mds2-2718"
TRANSCRIPTION_ARTIFACT_SHA256 = "d1b36dfa2e01a3537093c481e249ce52df6b8879c1c67480ddb9aa10799133da"
# SHA-256 of the parsed v1.1.0 transcription as sorted compact ASCII JSON.
# This binds parameter-supplied rows independently of source-document metadata.
TRANSCRIPTION_CONTENT_SHA256 = "250e7cdb8c9665fa242cf567464ade681ba627c28c6a0b9226ef1a45642f6267"
BENCHMARK = "AMB2022-03-TMPG"
OPTICAL_OPERATOR = "amb2022-03-etched-optical-six-section-mean-v1"
CASE_PROCESS = {
    "0": (285, 960, 67), "1.1": (285, 960, 49), "1.2": (285, 960, 82),
    "2.1": (285, 1200, 67), "2.2": (285, 800, 67),
    "3.1": (325, 960, 67), "3.2": (245, 960, 67),
}
_SHA = re.compile(r"^[0-9a-f]{64}$")


def _object(value):
    return value if isinstance(value, dict) else {}


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _close(value, target, tolerance=1e-9):
    return _number(value) and abs(value - target) <= tolerance


def _source_reasons(binding, expected):
    reasons = []
    binding, expected = _object(binding), _object(expected)
    if binding.get("datasetId") != ARCHIVE_DATASET_ID or binding.get("sourceDatasetId") != SOURCE_DATASET_ID:
        reasons.append("Source archive dataset and publisher identity are not AMB2022-03 Table 4 / nist-mds2-2718.")
    if expected.get("datasetId") != ARCHIVE_DATASET_ID or expected.get("sourceDatasetId") != SOURCE_DATASET_ID:
        reasons.append("Trusted expected source identity is missing or different.")
    if (binding.get("artifactSha256") != TRANSCRIPTION_ARTIFACT_SHA256
            or expected.get("artifactSha256") != TRANSCRIPTION_ARTIFACT_SHA256):
        reasons.append("Local Table 4 transcription artifact SHA-256 does not match the archived fixed bytes.")
    for key in ("revision", "documentSha256"):
        if binding.get(key) != expected.get(key):
            reasons.append(f"Source {key} does not match the selected exact archive revision.")
    if type(binding.get("revision")) is not int or binding["revision"] < 1:
        reasons.append("Source revision must be a positive integer.")
    if type(expected.get("revision")) is not int or expected["revision"] < 1:
        reasons.append("Trusted expected revision must be a positive integer.")
    if not isinstance(binding.get("documentSha256"), str) or not _SHA.fullmatch(binding["documentSha256"]):
        reasons.append("Source document SHA-256 is missing or malformed.")
    if not isinstance(expected.get("documentSha256"), str) or not _SHA.fullmatch(expected["documentSha256"]):
        reasons.append("Trusted expected document SHA-256 is missing or malformed.")
    return reasons


def _table_reasons(table):
    table = _object(table)
    reasons = []
    try:
        encoded = json.dumps(table, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode("utf-8")
        if hashlib.sha256(encoded).hexdigest() != TRANSCRIPTION_CONTENT_SHA256:
            reasons.append("Table 4 parameter rows differ from the frozen local transcription content.")
    except (TypeError, ValueError, OverflowError, UnicodeError):
        reasons.append("Table 4 parameter rows are not finite JSON.")
    if (table.get("schemaVersion") != 1 or table.get("kind") != "local-transcription-of-published-aggregate-measurements"
            or table.get("benchmark") != "AMB2022-03" or table.get("material") != "IN718"
            or table.get("doi") != "10.18434/mds2-2718"
            or table.get("publishedResults") != RESULTS_URL or table.get("publishedMethods") != METHODS_URL):
        reasons.append("Table 4 local transcription identity or primary-source links do not match.")
    measure, experiment = _object(table.get("measurement")), _object(table.get("experiment"))
    if (measure.get("countPerCondition") != 6 or measure.get("unit") != "um"
            or measure.get("method") != "Ex-situ dark-field optical cross-section geometry"):
        reasons.append("Table 4 must contain six optical cross-section measurements per condition in micrometres.")
    if (experiment.get("processScope") != "bare-plate" or experiment.get("sample") != "AMB2022-718-SH1-BP1"
            or experiment.get("scanDirection") != "+X" or experiment.get("beamDiameterDefinition") != "D4sigma"
            or experiment.get("trackLength_mm") != 10
            or experiment.get("powderLayerThickness_um") is not None
            or experiment.get("hatchSpacing_um") is not None):
        reasons.append("Table 4 experiment must be the 10 mm +X IN718 bare-plate optical track with D4sigma beam.")
    treatment = experiment.get("heatTreatment")
    evidence = _object(experiment.get("heatTreatmentEvidence"))
    if (treatment != "Residual-stress annealed in vacuum at 800 °C for 2 h before laser processing."
            or evidence.get("sourceUrl") != METHODS_URL
            or evidence.get("location") != "Version 1.01, Section 2.1 (Plate preparation), PDF page 2"
            or experiment.get("heatTreatmentMissingReason") is not None):
        reasons.append("Table 4 BP1 heat-treatment metadata must bind to the NIST methods description.")
    rows = table.get("cases")
    if not isinstance(rows, list) or len(rows) != len(CASE_PROCESS):
        return reasons + ["All seven published Table 4 process cases are required."], {}
    by_case = {}
    for row in rows:
        row = _object(row)
        case = row.get("caseNumber")
        if case not in CASE_PROCESS or case in by_case:
            reasons.append("Table 4 case IDs are unknown or duplicated.")
            continue
        by_case[case] = row
        power, speed, diameter = CASE_PROCESS[case]
        if (row.get("sampleId") != f"AMB2022-718-SH1-BP1-L{case}"
                or not _close(row.get("laserPower_W"), power)
                or not _close(row.get("scanSpeed_mm_s"), speed)
                or not _close(row.get("beamDiameterD4sigma_um"), diameter)):
            reasons.append(f"Table 4 case {case} P/v/D4sigma or sample ID is mismatched.")
        if any(not _number(row.get(key)) or row[key] <= 0 for key in
               ("depthMean_um", "depthStdDev_um", "widthMean_um", "widthStdDev_um")):
            reasons.append(f"Table 4 case {case} optical mean or standard deviation is missing or nonpositive.")
    if set(by_case) != set(CASE_PROCESS):
        reasons.append("Table 4 process cases are incomplete.")
    return reasons, by_case


def _axis_reasons(axis, label, core, section, process_vector):
    axis = _object(axis)
    levels = axis.get("levels")
    if not isinstance(levels, list) or len(levels) < 3 or len(levels) > 6:
        return [f"{label} convergence needs 3–6 independently executed levels."]
    reasons = []
    spacings = []
    for row in levels:
        row = _object(row)
        spacing = row.get("actualResolution")
        if (not _number(spacing) or spacing <= 0 or row.get("modelId") != core.get("modelId")
                or row.get("materialSha256") != core.get("materialSha256")
                or row.get("processVector") != process_vector
                or row.get("operator") != OPTICAL_OPERATOR
                or not _number(row.get("energyRelativeError")) or not 0 <= row["energyRelativeError"] <= .01
                or any(not _number(row.get(key)) or row[key] <= 0 for key in ("width_um", "depth_um"))):
            return [f"{label} convergence levels lack bound model/material/operator, positive geometry, or ≤1% energy closure."]
        spacings.append(spacing)
    if any(a <= b for a, b in zip(spacings, spacings[1:])):
        reasons.append(f"{label} actual resolution does not strictly refine.")
    for key in ("width_um", "depth_um"):
        values = [row[key] for row in levels[-3:]]
        coarse_change, fine_change = abs(values[1]-values[0]), abs(values[2]-values[1])
        if fine_change > .05*values[2] or fine_change > coarse_change + 1e-12:
            reasons.append(f"{label} {key} does not meet frozen ≤5% finest-pair and improving-trend gates.")
        if not _close(values[2], section.get(key), 1e-6):
            reasons.append(f"{label} finest {key} differs from the reported optical section.")
    return reasons


def _model_reasons(result, row):
    result = _object(result)
    settings, material = _object(result.get("settings")), _object(result.get("material"))
    core, section = _object(result.get("coreContract")), _object(result.get("midTrackCrossSection"))
    reasons = []
    try:
        enforce_core_contract(result)
        if not core:
            raise ValueError("Core contract absent")
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        reasons.append(f"Executed core contract is missing or inconsistent: {error}.")
    if (core.get("modelId") != "stationary-enthalpy-conduction-v1" or core.get("actualBackend") != "numpy-reference"
            or core.get("evidenceClass") != "unvalidated-model" or result.get("effectiveMode") != "standard"):
        reasons.append("An explicit standard CPU transient core and unvalidated-model evidence class are required.")
    if material.get("materialId") != "in718" or resolve_alloy_id(settings.get("material")) != "in718":
        reasons.append("Model material is not the resolved IN718 alloy.")
    if (settings.get("surfaceMode") != "bare-plate" or type(settings.get("tracks")) is not int
            or settings["tracks"] != 1 or type(settings.get("layers")) is not int or settings["layers"] != 1
            or not _close(settings.get("scanAngle_deg"), 0)
            or not _close(settings.get("trackLength_um"), 10_000)):
        reasons.append("Model requires one 10 mm +X bare-plate track with no powder layer.")
    path = result.get("scanPath")
    if not isinstance(path, list) or len(path) != 1:
        reasons.append("Executed scan path must contain one uninterrupted 10 mm +X laser track.")
    else:
        segment = _object(path[0])
        start, end = segment.get("start"), segment.get("end")
        if (not isinstance(start, list) or not isinstance(end, list) or len(start) != 2 or len(end) != 2
                or not all(_number(v) for v in start + end)
                or not _close(start[0], -.005) or not _close(end[0], .005)
                or not _close(start[1], 0) or not _close(end[1], 0)
                or not _close(segment.get("start_s"), 0)
                or not _number(segment.get("end_s"))
                or not _close(segment["end_s"], 10/settings["speed_mm_s"] if _number(settings.get("speed_mm_s")) and settings["speed_mm_s"] > 0 else -1)):
            reasons.append("Executed scan path does not match the continuous 10 mm +X NIST track.")
    if (not _close(settings.get("power_W"), row.get("laserPower_W"))
            or not _close(settings.get("speed_mm_s"), row.get("scanSpeed_mm_s"))):
        reasons.append("Model laser power or scan speed differs from the selected Table 4 case.")
    if not _number(settings.get("preheat_C")) or not 22.5 <= settings["preheat_C"] <= 24.5:
        reasons.append("Model substrate temperature is outside the NIST 23.5 ± 1 °C condition.")
    beam = _object(result.get("measuredBeamProfileEvidence"))
    convention = _object(result.get("beamConvention"))
    if (beam.get("status") != "measured-profile-matched" or beam.get("profileArtifactVerified") is not True
            or not isinstance(beam.get("profileSha256"), str)
            or not _SHA.fullmatch(beam["profileSha256"])
            or convention.get("mappingStatus") != "measured-profile-verified"
            or not _close(beam.get("D4sigma_um"), row.get("beamDiameterD4sigma_um"))
            or not _close(beam.get("modelInputDiameter_um"), settings.get("beamDiameter_um"))
            or not _close(settings.get("beamDiameter_um"), row.get("beamDiameterD4sigma_um"))):
        reasons.append("Measured beam profile and D4sigma-to-model input identity are not established.")
    six_sections = result.get("sixSectionObservation")
    has_valid_six_sections = False
    if isinstance(six_sections, dict):
        if (six_sections.get("status") == "optical-operator-matched"
                and six_sections.get("operator") == OPTICAL_OPERATOR
                and six_sections.get("observationCount") == 6
                and six_sections.get("locations_mm") == [4.9, 6.0]
                and isinstance(six_sections.get("sections"), list)
                and len(six_sections["sections"]) == 6
                and all(_number(s.get("width_um")) and s["width_um"] > 0
                        and _number(s.get("depth_um")) and s["depth_um"] > 0
                        for s in six_sections["sections"])):
            has_valid_six_sections = True
            section = six_sections

    if not has_valid_six_sections:
        if (section.get("status") != "optical-operator-matched" or section.get("operator") != OPTICAL_OPERATOR
                or section.get("observationCount") != 6 or section.get("location") != "near-10mm-track-midpoint"
                or not _close(section.get("longitudinalPosition_mm"), 5)
                or not _close(section.get("surface_m"), 0)
                or section.get("midpointResolvedWithinQuarterCell") is not True
                or not _number(section.get("mesh_um")) or section["mesh_um"] <= 0
                or not _close(section.get("mesh_um"), settings.get("mesh_um"))
                or not _number(section.get("planeOffset_um"))
                or abs(section["planeOffset_um"]) > section["mesh_um"]/4
                or any(not _number(section.get(key)) or section[key] <= 0 for key in ("width_um", "depth_um"))):
            reasons.append("Mid-track section does not match the six-sample etched optical widest/deepest operator and resolved position.")
        # The NIST aggregate comprises two physical sections on each of three
        # separately scanned tracks (4.9 and 6.0 mm from each track start). A
        # single midpoint result cannot stand in for those six observations, even
        # if a caller labels it with the optical operator or sets count=6.
        reasons.append(
            "NIST six-section operator is not implemented: require separate 4.9/6.0 mm section records for each of three simulated tracks."
        )
    convergence = _object(result.get("comparisonConvergence"))
    process_vector = {"power_W": settings.get("power_W"), "speed_mm_s": settings.get("speed_mm_s"),
                      "beamDiameterD4sigma_um": row.get("beamDiameterD4sigma_um"),
                      "beamProfileSha256": beam.get("profileSha256"), "trackLength_um": 10_000,
                      "surfaceMode": "bare-plate", "materialId": "in718"}
    for label in ("mesh", "timestep"):
        reasons.extend(_axis_reasons(convergence.get(label), label, core, section, process_vector))
    return reasons


def compare_nist_in718_optical_geometry(result, table4, source_binding, expected_source_binding, case_number):
    """Return unavailable reasons unless source, process, operator and numerics match.

    A comparable result is still an unvalidated model residual against a local
    transcription. This function never declares experimental qualification.
    """
    source_reasons = _source_reasons(source_binding, expected_source_binding)
    reasons = list(source_reasons)
    table_reasons, rows = _table_reasons(table4)
    reasons.extend(table_reasons)
    row = rows.get(case_number) if isinstance(case_number, str) else None
    if row is None:
        reasons.append("Selected Table 4 case number is absent or invalid.")
    else:
        reasons.extend(_model_reasons(result, row))
    report = {"schemaVersion": 1, "benchmark": BENCHMARK, "caseNumber": case_number,
              "status": "unavailable", "validationStatus": "unvalidated",
              "reference": {"doi": "10.18434/mds2-2718", "results": RESULTS_URL,
                            "resultsLocator": "Table 4, CHAL-AMB2022-03-TMPG",
                            "methods": METHODS_URL,
                            "measurement": "six optical cross-section depth/width measurements per condition",
                            "sectionPositions_mm": [4.9, 6.0], "trackCount": 3,
                            "archiveKind": "local transcription of published aggregate means and standard deviations"},
              "sourceBinding": source_binding if not source_reasons else None,
              "reasons": reasons, "errors": None}
    if reasons:
        return report
    section = result.get("sixSectionObservation") or result.get("midTrackCrossSection", {})
    report["status"] = "comparable-screening"
    report["errors"] = {quantity: {
        "signed_um": section[f"{quantity}_um"] - row[f"{quantity}Mean_um"],
        "absolute_um": abs(section[f"{quantity}_um"] - row[f"{quantity}Mean_um"]),
        "measuredMean_um": row[f"{quantity}Mean_um"],
        "publishedStdDev_um": row[f"{quantity}StdDev_um"],
        "model_um": section[f"{quantity}_um"],
    } for quantity in ("width", "depth")}
    return report


if __name__ == "__main__":
    import sys

    request = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    print(json.dumps(compare_nist_in718_optical_geometry(
        json.loads(request["resultJson"]), json.loads(request["table4Json"]), request["sourceBinding"],
        request["expectedSourceBinding"], request["caseNumber"]),
        allow_nan=False, separators=(",", ":")))
