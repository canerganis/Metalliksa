"""Contract tests for the independent continuous-geometry numerical gate."""

import copy
import unittest
from unittest.mock import patch

from lpbf_contour_convergence_study import CONTOUR_OPERATOR, PROTOCOL_ID, contour_study
from lpbf_peak import PEAK_EXTRACTION
from test_lpbf_convergence_study import CASE, fake_solver


def contour_solver(payload):
    result = fake_solver(payload)
    width = result["metrics"]["width_um"]
    depth = result["metrics"]["depth_um"]
    result["metrics"].update(width_um=100., depth_um=50.)
    result["peakInterpolatedMeltPool"] = {
        "status": "thermal-proxy", "operator": CONTOUR_OPERATOR,
        "temporalSelection": PEAK_EXTRACTION,
        "surfaceTreatment": "No temperature extrapolation to the model surface",
        "width_um": width, "depth_um": depth,
    }
    return result


class ContourConvergenceStudy(unittest.TestCase):
    def test_contour_pass_keeps_original_discrete_gate_inconclusive(self):
        original = copy.deepcopy(CASE)
        with patch("lpbf_convergence_study.run", side_effect=contour_solver):
            report = contour_study(CASE, [80, 40, 20], [4e-7, 2e-7, 1e-7])
        self.assertEqual(CASE, original)
        self.assertEqual(report["protocolId"], PROTOCOL_ID)
        self.assertEqual(report["status"], "inconclusive")
        self.assertEqual(report["discreteStatus"], "inconclusive")
        self.assertEqual(report["contourStatus"], "pass")
        self.assertFalse(report["experimentalValidation"])
        for axis in ("meshStudy", "timestepStudy"):
            self.assertEqual(report[axis]["contourAssessment"]["status"], "pass")

    def test_changed_operator_cannot_pass(self):
        def wrong(payload):
            result = contour_solver(payload)
            result["peakInterpolatedMeltPool"]["operator"] = "unknown"
            return result
        with patch("lpbf_convergence_study.run", side_effect=wrong):
            report = contour_study(CASE, [80, 40, 20], [4e-7, 2e-7, 1e-7])
        self.assertEqual(report["contourStatus"], "failed")
        self.assertIn("unavailable", report["meshStudy"]["contourAssessment"]["invalidLevels"][0]["reason"])

    def test_finest_change_over_frozen_five_percent_fails(self):
        def drift(payload):
            result = contour_solver(payload)
            if payload["mesh_um"] == 20 and payload["maxDt_s"] == 1e-7:
                result["peakInterpolatedMeltPool"]["depth_um"] = 40.
            return result
        with patch("lpbf_convergence_study.run", side_effect=drift):
            report = contour_study(CASE, [80, 40, 20], [4e-7, 2e-7, 1e-7])
        self.assertEqual(report["contourStatus"], "failed")
        self.assertGreater(report["meshStudy"]["contourAssessment"]["metrics"]["depth_um"]["finestPairRelativeChange"], .05)

    def test_incomplete_contour_and_energy_failure_remain_visible(self):
        def broken(payload):
            result = contour_solver(payload)
            if payload["mesh_um"] == 40:
                result["peakInterpolatedMeltPool"]["status"] = "inconclusive"
            return result
        with patch("lpbf_convergence_study.run", side_effect=broken):
            report = contour_study(CASE, [80, 40, 20], [4e-7, 2e-7, 1e-7])
        self.assertEqual(report["meshStudy"]["contourAssessment"]["status"], "failed")
        self.assertEqual(report["meshStudy"]["contourAssessment"]["invalidLevels"][0]["requested"], 40)

        def energy_drift(payload):
            result = contour_solver(payload)
            if payload["mesh_um"] == 80:
                result["energyBalance"]["stored_J"] = .7
            return result
        with patch("lpbf_convergence_study.run", side_effect=energy_drift):
            report = contour_study(CASE, [80, 40, 20], [4e-7, 2e-7, 1e-7])
        self.assertEqual(report["meshStudy"]["contourAssessment"]["energyStatus"], "failed")


if __name__ == "__main__":
    unittest.main()
