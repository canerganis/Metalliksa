"""Protocol integrity and bounded-resource gates; no thermal solver runs."""
import copy
import json
import math
from pathlib import Path
import unittest
from unittest.mock import mock_open, patch

import run_lpbf_nist_3707_table5_proxy as proxy


class NistTable5ProxyGuards(unittest.TestCase):
    def test_protocol_rejects_parameter_tuning_coarsening_and_claim_changes(self):
        protocol = proxy.read_json(proxy.PROTOCOL)
        proxy.validate_protocol(protocol)
        for key, value in (("power_W", 280), ("mesh_um", 40),
                           ("absorptivity", .4), ("trackLength_um", 4000)):
            altered = copy.deepcopy(protocol)
            altered["inputs"][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "inputs"):
                proxy.validate_protocol(altered)
        for key, value in (("experimentalValidation", True), ("operatorMismatch", False),
                           ("fittingOrTuning", True)):
            altered = copy.deepcopy(protocol)
            altered[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, key):
                proxy.validate_protocol(altered)

    def test_every_resource_limit_and_nonfinite_value_fails_closed(self):
        limits = dict(maximumCells=10, maximumSteps=10, maximumCellSteps=50,
                      maximumRssBytes=100, maximumWallTime_s=1)
        proxy.check_resources(10, 5, 100, 1, limits)
        for args in ((11, 0, 0, 0), (1, 11, 0, 0), (10, 6, 0, 0),
                     (1, 1, 101, 0), (1, 1, 0, 1.01)):
            with self.subTest(args=args), self.assertRaises(RuntimeError):
                proxy.check_resources(*args, limits)
        for value in (math.inf, math.nan, -1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                proxy.check_resources(1, 1, 0, value, limits)

    def test_short_length_preflight_retains_twenty_um_centre_and_total_caps(self):
        with patch.object(proxy.solver, "run", side_effect=AssertionError("must not solve")):
            plan = proxy.preflight()
        self.assertEqual([c["cells"] for c in plan["cases"]], [21045, 31395])
        self.assertEqual([c["domain"]["nx"] for c in plan["cases"]], [61, 91])
        self.assertTrue(plan["executionEligible"])
        self.assertLess(plan["totalHeuristicEstimatedCellSteps"], proxy.LIMITS["maximumCellSteps"])
        for case in plan["cases"]:
            self.assertLess(abs(case["midpointPlane_m"]), 1e-15)
            self.assertAlmostEqual(case["domain"]["dx"]*1e6, 20.0, places=12)
        self.assertFalse(plan["resourceEstimateIsGuaranteed"])
        self.assertEqual(plan["protocol"]["inputs"]["mesh_um"], 20)

    def test_changed_reference_hash_is_rejected_before_solver(self):
        with patch.object(proxy, "digest", return_value="0"*64):
            with self.assertRaisesRegex(ValueError, "transcription hash"):
                proxy.preflight()

    def test_execute_denial_writes_diagnostic_report_without_solver(self):
        plan = proxy.preflight()
        plan["executionEligible"] = False
        plan["executionDenialReasons"] = ["synthetic resource denial"]
        stream = mock_open()
        with patch.object(Path, "open", stream), patch.object(Path, "exists", return_value=False), \
                patch.object(proxy, "preflight", return_value=plan), \
                patch.object(proxy.subprocess, "check_output", return_value="synthetic-head\n"), \
                patch.object(proxy.solver, "run", side_effect=AssertionError("must not solve")):
            summary = proxy.execute()
        report = json.loads(stream.return_value.write.call_args.args[0])
        stream.assert_called_once_with("xb")
        self.assertEqual(summary["stage"], "preflight-denied")
        self.assertEqual(report["runtimeWork"]["attemptedSteps"], 0)
        self.assertFalse(report["experimentalValidation"])
        self.assertTrue(report["operatorMismatch"])
        self.assertIsNone(report["diagnosticGeometryDifferences"])
        self.assertNotIn("result", report)

    def test_total_work_guard_uses_sum_of_different_case_cell_counts(self):
        limits = {**proxy.LIMITS, "maximumCellSteps": 50}
        proxy.check_resources(10, 3, 0, 0, limits, cellsteps=50)
        with self.assertRaisesRegex(RuntimeError, "maximumCellSteps"):
            proxy.check_resources(10, 3, 0, 0, limits, cellsteps=51)

    def test_locality_pass_is_limited_to_resolved_two_case_sensitivity(self):
        def case(width, depth, status="thermal-proxy"):
            return {"thermalProxyOperator": dict(status=status, width_um=width, depth_um=depth, mesh_um=20)}
        report = proxy.compare_locality([case(100, 90), case(119, 109)])
        self.assertEqual(report["status"], "pass-local-length-sensitivity")
        self.assertFalse(report["equivalenceToEightMmTrackEstablished"])
        self.assertFalse(report["experimentalValidation"])
        self.assertEqual(proxy.compare_locality([case(100, 90), case(121, 90)])["status"], "inconclusive")
        self.assertEqual(proxy.compare_locality([case(100, 90), case(None, None, "inconclusive")])["status"], "inconclusive")


if __name__ == "__main__":
    unittest.main()
