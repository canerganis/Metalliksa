import copy
import unittest

from lpbf_nist_proxy_campaign import (
    CAMPAIGN_KIND,
    BENCHMARK,
    CONTOUR_OPERATOR,
    SECTION_IDS,
    SECTION_OPERATOR,
    SOURCE_DATASET_ID,
    validate_proxy_campaign,
)


DOC_SHA = "a" * 64
ARTIFACT_SHA = "b" * 64
INPUT_SHA = "c" * 64
MATERIAL_SHA = "d" * 64
MATERIAL_REVISION_SHA = "e" * 64
RUN_DOCUMENT_SHA = "f" * 64
RUN_ARTIFACT_SHA = "1" * 64


def _source_binding():
    return {
        "datasetId": SOURCE_DATASET_ID,
        "revision": 2,
        "documentSha256": DOC_SHA,
        "artifactPath": "table4-aggregate-v2.json",
        "artifactSha256": ARTIFACT_SHA,
        "artifactSizeBytes": 4321,
        "caseNumber": "2.1",
    }


def _run_identity(index):
    return {
        "runId": f"{index:032x}",
        "runDocumentSha256": RUN_DOCUMENT_SHA,
        "resultArtifact": {
            "path": "result-sections.json",
            "sha256": RUN_ARTIFACT_SHA,
            "size_bytes": 512,
        },
        "inputSha256": INPUT_SHA,
        "materialSha256": MATERIAL_SHA,
        "materialId": "in718",
        "materialRevisionSha256": MATERIAL_REVISION_SHA,
        "coreContract": {
            "schemaVersion": 1,
            "modelId": "stationary-enthalpy-conduction-v1",
            "solverId": "enthalpy-fv-6",
            "actualBackend": "numpy-reference",
        },
    }


def _campaign():
    source = _source_binding()
    tracks = []
    for track_index in range(3):
        run = _run_identity(track_index + 1)
        observations = []
        for section_index, (section_id, distance) in enumerate(zip(SECTION_IDS, (4.9, 6.0))):
            observations.append({
                "sectionId": section_id,
                "coordinateFrame": "scan-start-relative",
                "scanDirection": "+X",
                "distanceFromScanStart_mm": distance,
                "surfaceZ_m": 0.0,
                "status": "thermal-proxy",
                "geometry": {"width_um": 140.0 + section_index, "depth_um": 110.0 + section_index},
                "operator": {
                    "sectionOperatorId": SECTION_OPERATOR,
                    "interpolationOperatorId": "linear-interpolation-between-accepted-peak-temperature-planes-v1",
                    "contourOperatorId": CONTOUR_OPERATOR,
                    "evidenceClass": "thermal-proxy-only",
                },
                "provenance": {
                    "sourceBinding": copy.deepcopy(source),
                    "runIdentity": copy.deepcopy(run),
                },
            })
        tracks.append({
            "simulatedTrackId": f"sim-line-{track_index + 1}",
            "experimentalTrackId": None,
            "replicateKind": "independent-computational-run",
            "runIdentity": run,
            "observations": observations,
        })
    return {
        "schemaVersion": 1,
        "kind": CAMPAIGN_KIND,
        "campaignId": "9" * 32,
        "benchmark": BENCHMARK,
        "caseNumber": "2.1",
        "sourceBinding": source,
        "claimBoundary": {
            "resultKind": "thermal-proxy-screening",
            "validationStatus": "unvalidated",
            "experimentalValidation": False,
            "opticalOperatorMatched": False,
        },
        "samplingPlan": {
            "coordinateFrame": "scan-start-relative",
            "scanDirection": "+X",
            "sectionPositions_mm": [4.9, 6.0],
            "expectedTrackCount": 3,
            "expectedObservationCount": 6,
            "replicateSemantics": "independent-computational-runs-only",
        },
        "tracks": tracks,
    }


def _campaign_v2():
    campaign = _campaign()
    campaign["schemaVersion"] = 2
    campaign["beamInputDeclaration"] = {
        "status": "published-source-declared",
        "definition": "D4sigma",
        "value_um": 67.0,
        "mappingStatus": "conditional-ideal-Gaussian",
        "measuredProfileMatched": False,
        "sourceBinding": copy.deepcopy(campaign["sourceBinding"]),
    }
    campaign["samplingPlan"]["replicateSemantics"] = "reproducibility-evidence-not-independent-replicates"
    for track in campaign["tracks"]:
        track["replicateKind"] = "reproducibility-execution"
    return campaign


class TestNistProxyCampaign(unittest.TestCase):
    def test_complete_campaign_is_proxy_screening_only(self):
        report = validate_proxy_campaign(_campaign(), _source_binding())
        self.assertEqual(report["status"], "proxy-screening-only")
        self.assertEqual(report["validationStatus"], "unvalidated")
        self.assertIs(report["experimentalValidation"], False)
        self.assertEqual(report["numericalConvergenceStatus"], "not-evaluated")
        self.assertIsNone(report["comparisonResiduals"])
        self.assertEqual(report["observationCount"], 6)
        self.assertEqual(report["reasons"], [])

    def test_schema_version_rejects_boolean(self):
        campaign = _campaign()
        campaign["schemaVersion"] = True
        report = validate_proxy_campaign(campaign, _source_binding())
        self.assertEqual(report["status"], "unavailable")
        self.assertTrue(any("schemaVersion must be 1 or 2" in reason for reason in report["reasons"]))

    def test_v2_declared_source_input_is_accepted_without_measurement_claim(self):
        report = validate_proxy_campaign(_campaign_v2(), _source_binding(), 67.0)
        self.assertEqual(report["status"], "proxy-screening-only")
        self.assertEqual(report["reasons"], [])
        self.assertIsNone(report["comparisonResiduals"])
        self.assertIs(report["experimentalValidation"], False)

    def test_v2_rejects_wrong_beam_definition(self):
        campaign = _campaign_v2()
        campaign["beamInputDeclaration"]["definition"] = "FWHM"
        report = validate_proxy_campaign(campaign, _source_binding(), 67.0)
        self.assertEqual(report["status"], "unavailable")
        self.assertTrue(any("definition must be D4sigma" in reason for reason in report["reasons"]))

    def test_v2_rejects_wrong_beam_mapping_status(self):
        campaign = _campaign_v2()
        campaign["beamInputDeclaration"]["mappingStatus"] = "measured-profile"
        report = validate_proxy_campaign(campaign, _source_binding(), 67.0)
        self.assertEqual(report["status"], "unavailable")
        self.assertTrue(any("mappingStatus must be conditional-ideal-Gaussian" in reason
                            for reason in report["reasons"]))

    def test_v1_rejects_wrong_replicate_semantics(self):
        campaign = _campaign()
        campaign["samplingPlan"]["replicateSemantics"] = "reproducibility-evidence-not-independent-replicates"
        report = validate_proxy_campaign(campaign, _source_binding())
        self.assertEqual(report["status"], "unavailable")
        self.assertTrue(any("replicateSemantics must be independent-computational-runs-only" in reason
                            for reason in report["reasons"]))

    def test_v2_rejects_v1_replicate_semantics(self):
        campaign = _campaign_v2()
        campaign["samplingPlan"]["replicateSemantics"] = "independent-computational-runs-only"
        report = validate_proxy_campaign(campaign, _source_binding(), 67.0)
        self.assertEqual(report["status"], "unavailable")
        self.assertTrue(any("replicateSemantics must be reproducibility-evidence-not-independent-replicates"
                            in reason for reason in report["reasons"]))

    def test_v1_rejects_v2_replicate_kind(self):
        campaign = _campaign()
        campaign["tracks"][0]["replicateKind"] = "reproducibility-execution"
        report = validate_proxy_campaign(campaign, _source_binding())
        self.assertEqual(report["status"], "unavailable")
        self.assertTrue(any("replicateKind must be independent-computational-run" in reason
                            for reason in report["reasons"]))

    def test_v2_rejects_v1_replicate_kind(self):
        campaign = _campaign_v2()
        campaign["tracks"][0]["replicateKind"] = "independent-computational-run"
        report = validate_proxy_campaign(campaign, _source_binding(), 67.0)
        self.assertEqual(report["status"], "unavailable")
        self.assertTrue(any("replicateKind must be reproducibility-execution" in reason
                            for reason in report["reasons"]))

    def test_campaign_root_rejects_unknown_fields(self):
        campaign = _campaign_v2()
        campaign["unreviewedEvidence"] = {"experimentalValidation": True}
        report = validate_proxy_campaign(campaign, _source_binding(), 67.0)
        self.assertEqual(report["status"], "unavailable")
        self.assertTrue(any("campaign has unsupported fields: unreviewedEvidence" in reason
                            for reason in report["reasons"]))

    def test_v2_rejects_untrusted_or_forged_declaration(self):
        mutations = (
            ("value_um", 68.0, "trusted Table 4 D4sigma"),
            ("status", "measured", "status must be published-source-declared"),
            ("measuredProfileMatched", True, "measuredProfileMatched must be false"),
        )
        for key, value, expected_reason in mutations:
            with self.subTest(key=key):
                campaign = _campaign_v2()
                campaign["beamInputDeclaration"][key] = value
                report = validate_proxy_campaign(campaign, _source_binding(), 67.0)
                self.assertEqual(report["status"], "unavailable")
                self.assertTrue(any(expected_reason in reason for reason in report["reasons"]))

        campaign = _campaign_v2()
        campaign["beamInputDeclaration"]["sourceBinding"]["artifactSha256"] = "0" * 64
        report = validate_proxy_campaign(campaign, _source_binding(), 67.0)
        self.assertEqual(report["status"], "unavailable")
        self.assertTrue(any("sourceBinding does not match the trusted source revision" in reason
                            for reason in report["reasons"]))

        campaign = _campaign_v2()
        campaign["beamInputDeclaration"]["measuredEvidence"] = {"present": True}
        report = validate_proxy_campaign(campaign, _source_binding(), 67.0)
        self.assertEqual(report["status"], "unavailable")
        self.assertTrue(any("unsupported fields" in reason for reason in report["reasons"]))

    def test_v2_requires_trusted_source_value(self):
        report = validate_proxy_campaign(_campaign_v2(), _source_binding())
        self.assertEqual(report["status"], "unavailable")
        self.assertTrue(any("trusted source-derived Table 4 D4sigma" in reason for reason in report["reasons"]))

    def test_unsafe_artifact_paths_are_rejected(self):
        for unsafe_path in ("../outside.json", "C:/outside.json", "/outside.json"):
            with self.subTest(path=unsafe_path):
                campaign = _campaign()
                campaign["tracks"][0]["runIdentity"]["resultArtifact"]["path"] = unsafe_path
                for observation in campaign["tracks"][0]["observations"]:
                    observation["provenance"]["runIdentity"] = copy.deepcopy(campaign["tracks"][0]["runIdentity"])
                report = validate_proxy_campaign(campaign, _source_binding())
                self.assertEqual(report["status"], "unavailable")
                self.assertTrue(any("safe relative path" in reason for reason in report["reasons"]))

        campaign = _campaign()
        campaign["sourceBinding"]["artifactPath"] = "../outside.json"
        report = validate_proxy_campaign(campaign, _source_binding())
        self.assertEqual(report["status"], "unavailable")
        self.assertTrue(any("artifactPath must be a safe relative path" in reason for reason in report["reasons"]))

    def test_malformed_trusted_source_is_rejected_without_exception(self):
        expected = _source_binding()
        expected["experimentalTrackIds"] = "track-1"
        report = validate_proxy_campaign(_campaign(), expected)
        self.assertEqual(report["status"], "unavailable")
        self.assertTrue(any("Trusted expected source revision" in reason for reason in report["reasons"]))

    def test_missing_or_duplicate_section_is_unavailable(self):
        campaign = _campaign()
        campaign["tracks"][0]["observations"].pop()
        report = validate_proxy_campaign(campaign, _source_binding())
        self.assertEqual(report["status"], "unavailable")
        self.assertTrue(any("observations must contain exactly" in reason for reason in report["reasons"]))

        campaign = _campaign()
        campaign["tracks"][0]["observations"][1]["sectionId"] = "x-4p9mm"
        report = validate_proxy_campaign(campaign, _source_binding())
        self.assertEqual(report["status"], "unavailable")
        self.assertTrue(any("duplicate section" in reason for reason in report["reasons"]))

    def test_exact_sampling_positions_are_required(self):
        campaign = _campaign()
        campaign["tracks"][1]["observations"][0]["distanceFromScanStart_mm"] = 5.0
        report = validate_proxy_campaign(campaign, _source_binding())
        self.assertEqual(report["status"], "unavailable")
        self.assertTrue(any("must be exactly 4.9" in reason for reason in report["reasons"]))

    def test_nonfinite_or_nonpositive_geometry_is_rejected(self):
        for invalid_value in (float("nan"), float("inf"), 0.0, -1.0):
            with self.subTest(value=invalid_value):
                campaign = _campaign()
                campaign["tracks"][2]["observations"][1]["geometry"]["depth_um"] = invalid_value
                report = validate_proxy_campaign(campaign, _source_binding())
                self.assertEqual(report["status"], "unavailable")
                self.assertTrue(any("depth_um must be positive and finite" in reason for reason in report["reasons"]))

    def test_optical_etched_and_experimental_validation_claims_are_rejected(self):
        campaign = _campaign()
        campaign["tracks"][0]["observations"][0]["status"] = "optical-operator-matched"
        report = validate_proxy_campaign(campaign, _source_binding())
        self.assertEqual(report["status"], "unavailable")
        self.assertTrue(any("optical/etched claims are prohibited" in reason for reason in report["reasons"]))

        campaign = _campaign()
        campaign["claimBoundary"]["experimentalValidation"] = True
        report = validate_proxy_campaign(campaign, _source_binding())
        self.assertEqual(report["status"], "unavailable")
        self.assertTrue(any("experimentalValidation must be false" in reason for reason in report["reasons"]))

        campaign = _campaign()
        campaign["claimBoundary"]["resultKind"] = "etched-optical-validation"
        report = validate_proxy_campaign(campaign, _source_binding())
        self.assertEqual(report["status"], "unavailable")

    def test_source_and_each_section_provenance_must_match_trusted_revision(self):
        campaign = _campaign()
        campaign["sourceBinding"]["revision"] = 1
        report = validate_proxy_campaign(campaign, _source_binding())
        self.assertEqual(report["status"], "unavailable")
        self.assertTrue(any("does not match the trusted source revision" in reason for reason in report["reasons"]))

        campaign = _campaign()
        campaign["tracks"][1]["observations"][1]["provenance"]["runIdentity"]["inputSha256"] = "0" * 64
        report = validate_proxy_campaign(campaign, _source_binding())
        self.assertEqual(report["status"], "unavailable")
        self.assertTrue(any("runIdentity differs from its simulated track run" in reason for reason in report["reasons"]))

    def test_simulated_track_and_archived_run_ids_must_be_unique(self):
        campaign = _campaign()
        campaign["tracks"][1]["simulatedTrackId"] = campaign["tracks"][0]["simulatedTrackId"]
        report = validate_proxy_campaign(campaign, _source_binding())
        self.assertEqual(report["status"], "unavailable")
        self.assertTrue(any("simulatedTrackId is duplicated" in reason for reason in report["reasons"]))

        campaign = _campaign()
        campaign["tracks"][1]["runIdentity"]["runId"] = campaign["tracks"][0]["runIdentity"]["runId"]
        for observation in campaign["tracks"][1]["observations"]:
            observation["provenance"]["runIdentity"] = copy.deepcopy(campaign["tracks"][1]["runIdentity"])
        report = validate_proxy_campaign(campaign, _source_binding())
        self.assertEqual(report["status"], "unavailable")
        self.assertTrue(any("runId is duplicated across simulated tracks" in reason for reason in report["reasons"]))

    def test_experimental_track_id_requires_trusted_source_identity(self):
        campaign = _campaign()
        campaign["tracks"][0]["experimentalTrackId"] = "track-1"
        report = validate_proxy_campaign(campaign, _source_binding())
        self.assertEqual(report["status"], "unavailable")
        self.assertTrue(any("not supplied by the trusted source revision" in reason for reason in report["reasons"]))

        source = _source_binding()
        source["experimentalTrackIds"] = ["track-1"]
        campaign = _campaign()
        campaign["sourceBinding"]["experimentalTrackIds"] = ["track-1"]
        for track in campaign["tracks"]:
            for observation in track["observations"]:
                observation["provenance"]["sourceBinding"]["experimentalTrackIds"] = ["track-1"]
        campaign["tracks"][0]["experimentalTrackId"] = "track-1"
        report = validate_proxy_campaign(campaign, source)
        self.assertEqual(report["status"], "proxy-screening-only")

    def test_a_trusted_source_binding_is_required(self):
        report = validate_proxy_campaign(_campaign())
        self.assertEqual(report["status"], "unavailable")
        self.assertTrue(any("trusted expected source revision is required" in reason for reason in report["reasons"]))


if __name__ == "__main__":
    unittest.main()
