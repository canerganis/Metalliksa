"""AMB2022-03 optical comparison gates; positive fixtures are synthetic schemas."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from lpbf_core_contract import build_core_contract
from lpbf_material_registry import material
from lpbf_nist_in718_comparison import (
    ARCHIVE_DATASET_ID, OPTICAL_OPERATOR, SOURCE_DATASET_ID, TRANSCRIPTION_ARTIFACT_SHA256,
    compare_nist_in718_optical_geometry,
)
from lpbf_simulation import run


TABLE_PATH = (Path(__file__).resolve().parents[1] / "data" / "benchmark" /
              "nist-amb2022-03-optical" / "table4-aggregate-v2.json")


def source_binding():
    return {"datasetId": ARCHIVE_DATASET_ID, "sourceDatasetId": SOURCE_DATASET_ID,
            "artifactSha256": TRANSCRIPTION_ARTIFACT_SHA256,
            "revision": 2, "documentSha256": "a"*64}


def synthetic_result():
    """Schema fixture only: no executed model or measured-profile artifact."""
    settings = {"backend": "reference", "material": "Inconel 718", "surfaceMode": "bare-plate",
                "tracks": 1, "layers": 1, "scanAngle_deg": 0, "trackLength_um": 10_000,
                "power_W": 285, "speed_mm_s": 960, "beamDiameter_um": 67,
                "preheat_C": 23.5, "mesh_um": 5}
    resolved = material("Inconel 718")
    core = build_core_contract(settings, resolved, "enthalpy-fv-6", "standard")
    process_vector = {"power_W": 285, "speed_mm_s": 960, "beamDiameterD4sigma_um": 67,
                      "beamProfileSha256": "b"*64, "trackLength_um": 10_000,
                      "surfaceMode": "bare-plate", "materialId": "in718"}
    section = {"status": "optical-operator-matched", "operator": OPTICAL_OPERATOR,
               "observationCount": 6, "location": "near-10mm-track-midpoint",
               "longitudinalPosition_mm": 5, "surface_m": 0, "mesh_um": 5,
               "planeOffset_um": 0, "midpointResolvedWithinQuarterCell": True,
               "width_um": 140, "depth_um": 150}
    def axis(spacings):
        return {"levels": [{"actualResolution": spacing, "modelId": core["modelId"],
                            "materialSha256": core["materialSha256"], "operator": OPTICAL_OPERATOR,
                            "processVector": process_vector,
                            "energyRelativeError": .005, "width_um": width, "depth_um": depth}
                           for spacing, width, depth in zip(spacings, (130, 137, 140), (140, 147, 150))]}
    return {"settings": settings, "material": resolved, "coreContract": core,
            "solver": {"id": "enthalpy-fv-6"}, "effectiveMode": "standard",
            "scanPath": [{"start_s": 0, "end_s": 10/960, "start": [-.005, 0], "end": [.005, 0]}],
            "midTrackCrossSection": section,
            "beamConvention": {"mappingStatus": "measured-profile-verified"},
            "measuredBeamProfileEvidence": {"status": "measured-profile-matched",
                                            "profileArtifactVerified": True,
                                            "profileSha256": "b"*64,
                                            "D4sigma_um": 67, "modelInputDiameter_um": 67},
            "comparisonConvergence": {"mesh": axis((20, 10, 5)),
                                      "timestep": axis((4e-7, 2e-7, 1e-7))}}


class In718NistOpticalComparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = json.loads(TABLE_PATH.read_text(encoding="utf-8"))

    def compare(self, result=None, table=None, binding=None, expected=None, case="0"):
        binding = source_binding() if binding is None else binding
        expected = source_binding() if expected is None else expected
        return compare_nist_in718_optical_geometry(
            synthetic_result() if result is None else result,
            copy.deepcopy(self.table) if table is None else table,
            binding, expected, case)

    def test_source_and_table_identity_gates_withhold_numeric_error(self):
        stale = source_binding(); stale["revision"] = 1
        wrong_sha = source_binding(); wrong_sha["documentSha256"] = "c"*64
        wrong_dataset = source_binding(); wrong_dataset["sourceDatasetId"] = "other"
        wrong_artifact = source_binding(); wrong_artifact["artifactSha256"] = "d"*64
        invalid_tables = []
        bad_count = copy.deepcopy(self.table); bad_count["measurement"]["countPerCondition"] = 3
        invalid_tables.append(bad_count)
        wrong_case = copy.deepcopy(self.table); wrong_case["cases"][0]["beamDiameterD4sigma_um"] = 110
        invalid_tables.append(wrong_case)
        wrong_direction = copy.deepcopy(self.table); wrong_direction["experiment"]["scanDirection"] = "+Y"
        invalid_tables.append(wrong_direction)
        altered_mean = copy.deepcopy(self.table); altered_mean["cases"][0]["widthMean_um"] = 136.4
        invalid_tables.append(altered_mean)
        missing = copy.deepcopy(self.table); missing["cases"].pop()
        invalid_tables.append(missing)
        for binding in (stale, wrong_sha, wrong_dataset, wrong_artifact):
            with self.subTest(binding=binding):
                report = self.compare(binding=binding)
                self.assertEqual(report["status"], "unavailable")
                self.assertIsNone(report["errors"])
                self.assertTrue(report["reasons"])
        malformed_expected = source_binding(); malformed_expected["revision"] = True
        self.assertEqual(self.compare(expected=malformed_expected)["status"], "unavailable")
        for table in invalid_tables:
            with self.subTest(table=table.get("experiment")):
                report = self.compare(table=table)
                self.assertEqual(report["status"], "unavailable")
                self.assertIsNone(report["errors"])
        self.assertEqual(self.compare(case="absent")["status"], "unavailable")

    def test_current_pilot_mismatches_return_specific_reasons(self):
        result = synthetic_result()
        result["settings"]["trackLength_um"] = 200
        result["settings"]["surfaceMode"] = "powder-layer"
        result["settings"]["beamDiameter_um"] = 80
        result["settings"]["power_W"] = 200
        result["settings"]["preheat_C"] = 80
        result["midTrackCrossSection"]["operator"] = "midtrack-ever-liquidus-cell-section-v1"
        result["midTrackCrossSection"]["status"] = "thermal-proxy"
        result["beamConvention"]["mappingStatus"] = "conditional ideal-Gaussian identity"
        del result["measuredBeamProfileEvidence"]
        del result["comparisonConvergence"]["timestep"]
        report = self.compare(result=result)
        self.assertEqual(report["status"], "unavailable")
        self.assertIsNone(report["errors"])
        reasons = " ".join(report["reasons"])
        for text in ("core contract", "bare-plate", "power or scan speed", "beam profile", "optical", "timestep"):
            self.assertIn(text, reasons)

    def test_executed_short_bare_plate_pilot_remains_unavailable(self):
        pilot = run({"mode": "standard", "backend": "reference", "surfaceMode": "bare-plate",
                     "sourcePenetration_um": 40, "material": "Inconel 718", "power_W": 80,
                     "speed_mm_s": 1200, "mesh_um": 40, "maxDt_s": 2e-7,
                     "trackLength_um": 200, "cooling_s": 2e-5, "dwell_s": 0})
        report = self.compare(result=pilot)
        self.assertEqual(report["status"], "unavailable")
        self.assertIsNone(report["errors"])
        reasons = " ".join(report["reasons"])
        for text in ("10 mm +X", "power or scan speed", "beam profile", "optical", "mesh", "timestep"):
            self.assertIn(text, reasons)

    def test_material_mesh_operator_and_three_plus_three_gates(self):
        variants = []
        mismatch = synthetic_result(); mismatch["material"] = material("Ti64")
        variants.append(mismatch)
        unresolved = synthetic_result(); unresolved["midTrackCrossSection"]["planeOffset_um"] = 3
        variants.append(unresolved)
        sparse = synthetic_result(); sparse["comparisonConvergence"]["mesh"]["levels"].pop()
        variants.append(sparse)
        unstable = synthetic_result(); unstable["comparisonConvergence"]["timestep"]["levels"][-1]["width_um"] = 180
        variants.append(unstable)
        wrong_path = synthetic_result(); wrong_path["scanPath"][0]["end"] = [.0002, 0]
        variants.append(wrong_path)
        drifting_vector = synthetic_result()
        drifting_vector["comparisonConvergence"]["mesh"]["levels"][0]["processVector"] = {
            **drifting_vector["comparisonConvergence"]["mesh"]["levels"][0]["processVector"], "power_W": 325}
        variants.append(drifting_vector)
        thermal_proxy = synthetic_result()
        thermal_proxy["midTrackCrossSection"].update(status="thermal-proxy", operator="midtrack-ever-liquidus-cell-section-v1")
        variants.append(thermal_proxy)
        unverified_profile = synthetic_result()
        unverified_profile["measuredBeamProfileEvidence"]["profileArtifactVerified"] = False
        variants.append(unverified_profile)
        for result in variants:
            with self.subTest(result=result["midTrackCrossSection"]):
                report = self.compare(result=result)
                self.assertEqual(report["status"], "unavailable")
                self.assertIsNone(report["errors"])

    def test_single_midpoint_cannot_stand_in_for_nist_six_section_operator(self):
        report = self.compare()
        self.assertEqual(report["status"], "unavailable")
        self.assertEqual(report["validationStatus"], "unvalidated")
        self.assertIsNone(report["errors"])
        self.assertIn("4.9/6.0 mm", " ".join(report["reasons"]))
        self.assertEqual(report["reference"]["sectionPositions_mm"], [4.9, 6.0])
        self.assertEqual(report["reference"]["trackCount"], 3)

    def test_cli_preserves_python_json_number_lexemes(self):
        request = {"resultJson": json.dumps(synthetic_result(), allow_nan=False),
                   "table4Json": TABLE_PATH.read_text(encoding="utf-8"),
                   "sourceBinding": source_binding(),
                   "expectedSourceBinding": source_binding(), "caseNumber": "0"}
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("lpbf_nist_in718_comparison.py"))],
            input=json.dumps(request), text=True, capture_output=True, check=True)
        report = json.loads(completed.stdout)
        self.assertEqual(report["status"], "unavailable")
        self.assertIsNone(report["errors"])
        self.assertIn("independent simulated track field", " ".join(report["reasons"]))


if __name__ == "__main__":
    unittest.main()
