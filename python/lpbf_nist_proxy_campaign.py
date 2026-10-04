"""Versioned input contract for an unvalidated AMB2022-03 proxy campaign.

This validator binds six numerical thermal-proxy sections to three separately
archived computational track runs and one trusted source revision. It does not
match the etched optical measurement operator or establish validation.
"""

import math
import re


SCHEMA_VERSION = 1
CAMPAIGN_SCHEMA_VERSION = 2
CAMPAIGN_KIND = "lpbf-nist-amb2022-03-proxy-campaign"
BENCHMARK = "AMB2022-03-TMPG"
SOURCE_DATASET_ID = "nist-amb2022-03-optical-table4-local-v1"
SECTION_OPERATOR = "bare-plate-corridor-accepted-peak-x-linear-section-v1"
CONTOUR_OPERATOR = "linear-liquidus-crossings-between-cell-centers-v1"
INTERPOLATION_OPERATORS = {
    "exact-cell-center",
    "linear-interpolation-between-accepted-peak-temperature-planes-v1",
}
SECTION_POSITIONS_MM = (4.9, 6.0)
SECTION_IDS = ("x-4p9mm", "x-6p0mm")
TRACK_IDS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
RUN_ID = re.compile(r"^[a-f0-9]{32}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")


def _is_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _is_sha(value):
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def _is_record(value):
    return isinstance(value, dict)


def _is_json_safe(value):
    if value is None or type(value) in (bool, int, str):
        return True
    if type(value) is float:
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_is_json_safe(item) for item in value)
    if _is_record(value):
        return all(isinstance(key, str) and _is_json_safe(item) for key, item in value.items())
    return False


def _safe_relative_path(value):
    if not isinstance(value, str) or not value or "\x00" in value:
        return False
    normalized = value.replace("\\", "/")
    return (not normalized.startswith("/")
            and re.match(r"^[A-Za-z]:", normalized) is None
            and all(part not in ("", ".", "..") for part in normalized.split("/")))


def _check_keys(value, required, optional, label, reasons):
    if not _is_record(value):
        reasons.append(f"{label} must be an object.")
        return False
    missing = sorted(set(required) - value.keys())
    extra = sorted(value.keys() - set(required) - set(optional))
    if missing:
        reasons.append(f"{label} is missing required fields: {', '.join(missing)}.")
    if extra:
        reasons.append(f"{label} has unsupported fields: {', '.join(extra)}.")
    return not missing and not extra


_SOURCE_FIELDS = {
    "datasetId", "revision", "documentSha256", "artifactPath",
    "artifactSha256", "artifactSizeBytes", "caseNumber",
}


def _validate_source_binding(binding, expected, label, reasons):
    if not _check_keys(binding, _SOURCE_FIELDS, set(), label, reasons):
        return
    if binding.get("datasetId") != SOURCE_DATASET_ID:
        reasons.append(f"{label}.datasetId is not the registered AMB2022-03 Table 4 transcription.")
    if type(binding.get("revision")) is not int or binding["revision"] < 1:
        reasons.append(f"{label}.revision must be a positive integer.")
    if not _is_sha(binding.get("documentSha256")):
        reasons.append(f"{label}.documentSha256 must be a lowercase SHA-256.")
    if not _is_sha(binding.get("artifactSha256")):
        reasons.append(f"{label}.artifactSha256 must be a lowercase SHA-256.")
    if not _safe_relative_path(binding.get("artifactPath")):
        reasons.append(f"{label}.artifactPath must be a safe relative path.")
    if type(binding.get("artifactSizeBytes")) is not int or binding["artifactSizeBytes"] < 1:
        reasons.append(f"{label}.artifactSizeBytes must be a positive integer.")
    if not isinstance(binding.get("caseNumber"), str) or not binding["caseNumber"].strip():
        reasons.append(f"{label}.caseNumber must identify one published Table 4 case.")

    if expected is None:
        reasons.append("A trusted expected source revision is required.")
    elif not _is_record(expected):
        reasons.append("Trusted expected source revision must be an object.")
    elif _check_keys(expected, _SOURCE_FIELDS, set(),
                     "Trusted expected source revision", reasons):
        for key in _SOURCE_FIELDS:
            if binding.get(key) != expected.get(key):
                reasons.append(f"{label}.{key} does not match the trusted source revision.")


_RUN_FIELDS = {
    "runId", "runDocumentSha256", "resultArtifact", "inputSha256",
    "materialSha256", "materialId", "materialRevisionSha256", "coreContract",
}
_RUN_FIELDS_V2 = _RUN_FIELDS | {"executedSettings"}


def _validate_run_identity(run, label, reasons, schema_version=SCHEMA_VERSION, expected_beam_diameter_um=None):
    fields = _RUN_FIELDS_V2 if schema_version == CAMPAIGN_SCHEMA_VERSION else _RUN_FIELDS
    if not _check_keys(run, fields, set(), label, reasons):
        return
    if not isinstance(run.get("runId"), str) or RUN_ID.fullmatch(run["runId"]) is None:
        reasons.append(f"{label}.runId must be a 32-character archived run ID.")
    for key in ("runDocumentSha256", "inputSha256", "materialSha256", "materialRevisionSha256"):
        if not _is_sha(run.get(key)):
            reasons.append(f"{label}.{key} must be a lowercase SHA-256.")
    if run.get("materialId") != "in718":
        reasons.append(f"{label}.materialId must resolve to IN718.")
    if schema_version == CAMPAIGN_SCHEMA_VERSION:
        settings = run.get("executedSettings")
        if not _is_record(settings) or not _is_json_safe(settings):
            reasons.append(f"{label}.executedSettings must be a JSON-safe captured settings object.")
        elif (not _is_number(settings.get("beamDiameter_um"))
              or settings["beamDiameter_um"] != expected_beam_diameter_um):
            reasons.append(f"{label}.executedSettings.beamDiameter_um must match the trusted Table 4 case.")

    artifact = run.get("resultArtifact")
    if _check_keys(artifact, {"path", "sha256", "size_bytes"}, set(), f"{label}.resultArtifact", reasons):
        path = artifact.get("path")
        if not _safe_relative_path(path):
            reasons.append(f"{label}.resultArtifact.path must be a safe relative path.")
        if not _is_sha(artifact.get("sha256")):
            reasons.append(f"{label}.resultArtifact.sha256 must be a lowercase SHA-256.")
        if type(artifact.get("size_bytes")) is not int or artifact["size_bytes"] < 0:
            reasons.append(f"{label}.resultArtifact.size_bytes must be a nonnegative integer.")

    core = run.get("coreContract")
    if _check_keys(core, {"schemaVersion", "modelId", "solverId", "actualBackend"}, set(),
                   f"{label}.coreContract", reasons):
        if type(core.get("schemaVersion")) is not int or core["schemaVersion"] < 1:
            reasons.append(f"{label}.coreContract.schemaVersion must be a positive integer.")
        for key in ("modelId", "solverId", "actualBackend"):
            if not isinstance(core.get(key), str) or not core[key].strip():
                reasons.append(f"{label}.coreContract.{key} must be a nonempty string.")


def _validate_observation(observation, track, section_index, campaign_source, expected_source, label, reasons,
                          schema_version=SCHEMA_VERSION, expected_beam_diameter_um=None):
    fields = {
        "sectionId", "coordinateFrame", "scanDirection", "distanceFromScanStart_mm",
        "surfaceZ_m", "status", "geometry", "operator", "provenance",
    }
    if not _check_keys(observation, fields, set(), label, reasons):
        return

    expected_id = SECTION_IDS[section_index]
    expected_distance = SECTION_POSITIONS_MM[section_index]
    if observation.get("sectionId") != expected_id:
        reasons.append(f"{label}.sectionId must be {expected_id}.")
    if observation.get("coordinateFrame") != "scan-start-relative":
        reasons.append(f"{label}.coordinateFrame must be scan-start-relative.")
    if observation.get("scanDirection") != "+X":
        reasons.append(f"{label}.scanDirection must be +X.")
    distance = observation.get("distanceFromScanStart_mm")
    if type(distance) not in (int, float) or distance != expected_distance:
        reasons.append(f"{label}.distanceFromScanStart_mm must be exactly {expected_distance}.")
    if not _is_number(observation.get("surfaceZ_m")) or observation["surfaceZ_m"] != 0:
        reasons.append(f"{label}.surfaceZ_m must be finite and exactly zero.")
    if observation.get("status") != "thermal-proxy":
        reasons.append(f"{label}.status must remain thermal-proxy; optical/etched claims are prohibited.")

    geometry = observation.get("geometry")
    if _check_keys(geometry, {"width_um", "depth_um"}, set(), f"{label}.geometry", reasons):
        for key in ("width_um", "depth_um"):
            if not _is_number(geometry.get(key)) or geometry[key] <= 0:
                reasons.append(f"{label}.geometry.{key} must be positive and finite.")

    operator = observation.get("operator")
    op_fields = {"sectionOperatorId", "interpolationOperatorId", "contourOperatorId", "evidenceClass"}
    if _check_keys(operator, op_fields, set(), f"{label}.operator", reasons):
        if operator.get("sectionOperatorId") != SECTION_OPERATOR:
            reasons.append(f"{label}.operator.sectionOperatorId is not the registered corridor thermal-proxy operator.")
        if operator.get("interpolationOperatorId") not in INTERPOLATION_OPERATORS:
            reasons.append(f"{label}.operator.interpolationOperatorId is unsupported.")
        if operator.get("contourOperatorId") != CONTOUR_OPERATOR:
            reasons.append(f"{label}.operator.contourOperatorId is not the registered liquidus proxy operator.")
        if operator.get("evidenceClass") != "thermal-proxy-only":
            reasons.append(f"{label}.operator.evidenceClass must be thermal-proxy-only.")

    provenance = observation.get("provenance")
    if _check_keys(provenance, {"sourceBinding", "runIdentity"}, set(), f"{label}.provenance", reasons):
        _validate_source_binding(provenance.get("sourceBinding"), expected_source,
                                 f"{label}.provenance.sourceBinding", reasons)
        if provenance.get("sourceBinding") != campaign_source:
            reasons.append(f"{label}.provenance.sourceBinding differs from the campaign source binding.")
        _validate_run_identity(provenance.get("runIdentity"), f"{label}.provenance.runIdentity", reasons,
                               schema_version, expected_beam_diameter_um)
        if provenance.get("runIdentity") != track.get("runIdentity"):
            reasons.append(f"{label}.provenance.runIdentity differs from its simulated track run.")


def _validate_beam_input_declaration(declaration, expected_source_binding, expected_beam_diameter_um, reasons):
    label = "campaign.beamInputDeclaration"
    fields = {"status", "definition", "value_um", "mappingStatus", "measuredProfileMatched", "sourceBinding"}
    if not _check_keys(declaration, fields, set(), label, reasons):
        return
    if declaration.get("status") != "published-source-declared":
        reasons.append(f"{label}.status must be published-source-declared.")
    if declaration.get("definition") != "D4sigma":
        reasons.append(f"{label}.definition must be D4sigma.")
    value = declaration.get("value_um")
    if not _is_number(value) or value <= 0:
        reasons.append(f"{label}.value_um must be positive and finite.")
    if declaration.get("mappingStatus") != "conditional-ideal-Gaussian":
        reasons.append(f"{label}.mappingStatus must be conditional-ideal-Gaussian.")
    if declaration.get("measuredProfileMatched") is not False:
        reasons.append(f"{label}.measuredProfileMatched must be false.")
    if declaration.get("sourceBinding") != expected_source_binding:
        reasons.append(f"{label}.sourceBinding does not match the trusted source revision.")
    if expected_beam_diameter_um is None or not _is_number(expected_beam_diameter_um):
        reasons.append("A trusted source-derived Table 4 D4sigma value is required for schema v2.")
    elif value != expected_beam_diameter_um:
        reasons.append(f"{label}.value_um does not match the trusted Table 4 D4sigma value.")


def validate_proxy_campaign(campaign, expected_source_binding=None, expected_beam_diameter_um=None):
    """Validate a six-section thermal-proxy campaign without optical claims.

    ``expected_source_binding`` must come from a trusted, byte-verified source
    archive lookup. Structural validity alone is not enough to accept a source.
    """
    reasons = []
    schema_version = campaign.get("schemaVersion") if _is_record(campaign) else None
    fields = {
        "schemaVersion", "kind", "campaignId", "benchmark", "caseNumber",
        "sourceBinding", "claimBoundary", "samplingPlan", "tracks",
    }
    if schema_version == CAMPAIGN_SCHEMA_VERSION and type(schema_version) is int:
        fields.add("beamInputDeclaration")
    structurally_closed = _check_keys(campaign, fields, set(), "campaign", reasons)
    if _is_record(campaign):
        if type(schema_version) is not int or schema_version not in (SCHEMA_VERSION, CAMPAIGN_SCHEMA_VERSION):
            reasons.append("campaign.schemaVersion must be 1 or 2.")
        if schema_version == CAMPAIGN_SCHEMA_VERSION and type(schema_version) is int:
            _validate_beam_input_declaration(campaign.get("beamInputDeclaration"),
                                             expected_source_binding, expected_beam_diameter_um, reasons)
        if campaign.get("kind") != CAMPAIGN_KIND:
            reasons.append(f"campaign.kind must be {CAMPAIGN_KIND}.")
        if not isinstance(campaign.get("campaignId"), str) or RUN_ID.fullmatch(campaign["campaignId"]) is None:
            reasons.append("campaign.campaignId must be a 32-character lowercase hexadecimal ID.")
        if campaign.get("benchmark") != BENCHMARK:
            reasons.append(f"campaign.benchmark must be {BENCHMARK}.")
        case_number = campaign.get("caseNumber")
        if not isinstance(case_number, str) or not case_number.strip():
            reasons.append("campaign.caseNumber must identify one published Table 4 case.")

        source = campaign.get("sourceBinding")
        _validate_source_binding(source, expected_source_binding, "campaign.sourceBinding", reasons)
        if _is_record(source) and case_number != source.get("caseNumber"):
            reasons.append("campaign.caseNumber differs from campaign.sourceBinding.caseNumber.")

        claim = campaign.get("claimBoundary")
        claim_fields = {"resultKind", "validationStatus", "experimentalValidation", "opticalOperatorMatched"}
        if _check_keys(claim, claim_fields, set(), "campaign.claimBoundary", reasons):
            if claim.get("resultKind") != "thermal-proxy-screening":
                reasons.append("campaign.claimBoundary.resultKind must be thermal-proxy-screening.")
            if claim.get("validationStatus") != "unvalidated":
                reasons.append("campaign.claimBoundary.validationStatus must remain unvalidated.")
            if claim.get("experimentalValidation") is not False:
                reasons.append("campaign.claimBoundary.experimentalValidation must be false.")
            if claim.get("opticalOperatorMatched") is not False:
                reasons.append("campaign.claimBoundary.opticalOperatorMatched must be false.")

        plan = campaign.get("samplingPlan")
        plan_fields = {"coordinateFrame", "scanDirection", "sectionPositions_mm", "expectedTrackCount",
                       "expectedObservationCount", "replicateSemantics"}
        if _check_keys(plan, plan_fields, set(), "campaign.samplingPlan", reasons):
            if plan.get("coordinateFrame") != "scan-start-relative":
                reasons.append("campaign.samplingPlan.coordinateFrame must be scan-start-relative.")
            if plan.get("scanDirection") != "+X":
                reasons.append("campaign.samplingPlan.scanDirection must be +X.")
            positions = plan.get("sectionPositions_mm")
            if (not isinstance(positions, list) or len(positions) != 2
                    or any(type(value) not in (int, float) for value in positions)
                    or positions != list(SECTION_POSITIONS_MM)):
                reasons.append("campaign.samplingPlan.sectionPositions_mm must be exactly [4.9, 6.0].")
            if type(plan.get("expectedTrackCount")) is not int or plan["expectedTrackCount"] != 3:
                reasons.append("campaign.samplingPlan.expectedTrackCount must be 3.")
            if type(plan.get("expectedObservationCount")) is not int or plan["expectedObservationCount"] != 6:
                reasons.append("campaign.samplingPlan.expectedObservationCount must be 6.")
            expected_replicate_semantics = ("reproducibility-evidence-not-independent-replicates"
                                            if schema_version == CAMPAIGN_SCHEMA_VERSION
                                            else "independent-computational-runs-only")
            if plan.get("replicateSemantics") != expected_replicate_semantics:
                reasons.append(f"campaign.samplingPlan.replicateSemantics must be {expected_replicate_semantics}.")

        tracks = campaign.get("tracks")
        if not isinstance(tracks, list) or len(tracks) != 3:
            reasons.append("campaign.tracks must contain exactly three simulated tracks.")
        else:
            track_ids, run_ids = set(), set()
            for track_index, track in enumerate(tracks):
                label = f"campaign.tracks[{track_index}]"
                if not _check_keys(track, {"simulatedTrackId", "experimentalTrackId", "replicateKind",
                                           "runIdentity", "observations"}, set(), label, reasons):
                    continue
                track_id = track.get("simulatedTrackId")
                if not isinstance(track_id, str) or TRACK_IDS.fullmatch(track_id) is None:
                    reasons.append(f"{label}.simulatedTrackId must be a valid nonempty identifier.")
                elif track_id in track_ids:
                    reasons.append(f"{label}.simulatedTrackId is duplicated.")
                else:
                    track_ids.add(track_id)

                experimental_id = track.get("experimentalTrackId")
                trusted_ids = (expected_source_binding.get("experimentalTrackIds", [])
                               if _is_record(expected_source_binding) else [])
                if not isinstance(trusted_ids, list):
                    trusted_ids = []
                if experimental_id is not None and experimental_id not in trusted_ids:
                    reasons.append(f"{label}.experimentalTrackId is not supplied by the trusted source revision.")
                expected_replicate_kind = ("reproducibility-execution"
                                           if schema_version == CAMPAIGN_SCHEMA_VERSION
                                           else "independent-computational-run")
                if track.get("replicateKind") != expected_replicate_kind:
                    reasons.append(f"{label}.replicateKind must be {expected_replicate_kind}.")

                _validate_run_identity(track.get("runIdentity"), f"{label}.runIdentity", reasons,
                                       schema_version, expected_beam_diameter_um)
                run = track.get("runIdentity")
                if _is_record(run) and isinstance(run.get("runId"), str):
                    if run["runId"] in run_ids:
                        reasons.append(f"{label}.runIdentity.runId is duplicated across simulated tracks.")
                    run_ids.add(run["runId"])

                observations = track.get("observations")
                if not isinstance(observations, list) or len(observations) != 2:
                    reasons.append(f"{label}.observations must contain exactly the 4.9 mm and 6.0 mm sections.")
                    continue
                seen_sections = set()
                for observation in observations:
                    section_id = observation.get("sectionId") if _is_record(observation) else None
                    if section_id in seen_sections:
                        reasons.append(f"{label}.observations contains duplicate section {section_id!r}.")
                    seen_sections.add(section_id)
                    if section_id in SECTION_IDS:
                        section_index = SECTION_IDS.index(section_id)
                    else:
                        section_index = len(seen_sections) - 1
                    if section_index > 1:
                        reasons.append(f"{label}.observations contains an unsupported section.")
                        continue
                    _validate_observation(observation, track, section_index, source,
                                          expected_source_binding, f"{label}.observations[{section_index}]", reasons,
                                          schema_version, expected_beam_diameter_um)
                if seen_sections != set(SECTION_IDS):
                    reasons.append(f"{label}.observations must contain each required section exactly once.")

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": f"{CAMPAIGN_KIND}-validation",
        "campaignId": campaign.get("campaignId") if _is_record(campaign) else None,
        "status": "unavailable" if reasons or not structurally_closed else "proxy-screening-only",
        "validationStatus": "unvalidated",
        "experimentalValidation": False,
        "numericalConvergenceStatus": "not-evaluated",
        "comparisonResiduals": None,
        "observationCount": 6 if not reasons and structurally_closed else None,
        "reasons": reasons,
    }
