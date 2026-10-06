import copy
import json
import unittest
from pathlib import Path

import run_lpbf_fixed_event_mesh_probe as probe


ROOT = Path(__file__).resolve().parents[1]


class FixedEventMeshProbeTests(unittest.TestCase):
    def test_volume_weighted_field_difference_metrics(self):
        reference = [1.0, 2.0, 2.0]
        candidate = [2.0, 2.0, 4.0]

        metrics = probe._field_difference(reference, candidate, cell_volume_m3=0.5)

        self.assertAlmostEqual(metrics["volumeL2Difference"], (2.5) ** 0.5)
        self.assertAlmostEqual(metrics["relativeL2Difference"], (5.0 / 9.0) ** 0.5)
        self.assertEqual(metrics["maximumAbsoluteDifference"], 2.0)

    def test_protocol_has_three_fixed_mesh_levels_and_diagnostic_only_status(self):
        protocol = json.loads(probe.PROTOCOL_PATH.read_text(encoding="utf-8"))

        probe._validate_protocol(protocol)

        self.assertEqual(protocol["levels"], [1e-7, 5e-8, 2.5e-8])
        self.assertEqual(protocol["mesh_um"], 10)
        self.assertEqual(protocol["cooling_s"], 0)
        self.assertEqual(protocol["maximumTotalCellSteps"], 1_300_000_000)
        self.assertFalse(protocol["experimentalValidation"])
        self.assertEqual(protocol["convergenceConclusion"], "inconclusive")
        self.assertEqual(protocol["status"], "diagnostic-only")

    def test_protocol_rejects_cost_ceiling_or_level_mutations(self):
        protocol = json.loads(probe.PROTOCOL_PATH.read_text(encoding="utf-8"))
        over_budget = copy.deepcopy(protocol)
        over_budget["maximumTotalCellSteps"] = 1_151_920_000 - 1
        with self.assertRaisesRegex(ValueError, "cell-step ceiling"):
            probe._validate_protocol(over_budget)

        wrong_levels = copy.deepcopy(protocol)
        wrong_levels["levels"] = [1e-7, 5e-8, 2e-8]
        with self.assertRaisesRegex(ValueError, "fixed timestep levels"):
            probe._validate_protocol(wrong_levels)

    def test_preflight_resolves_exact_domain_event_and_inputs_without_solving(self):
        protocol, protocol_bytes, _scenario_bytes, event, cases = probe.preflight()

        self.assertEqual(len(protocol_bytes), len(probe.PROTOCOL_PATH.read_bytes()))
        self.assertEqual(event["end_s"], protocol["expectedEventTime_s"])
        self.assertEqual([case["cells"] for case in cases], [65_824] * 3)
        self.assertEqual([case["predictedSteps"] for case in cases], [2500, 5000, 10000])

    def test_completed_case_validation_records_realized_dt_energy_and_final_event(self):
        case = {"maxDt_s": 1e-7, "cells": 65_824, "domain": {"dx": 1e-5}}
        accepted = [1e-7] * 2500
        selected = {"step": 2500, "time_s": 0.00025, "roundoff_tolerance_s": 1e-12,
                    "accepted_dt_s": accepted}
        final = {"time_s": 0.00025, "accepted_dt_s": accepted}
        result = {
            "discretization": {"mesh_m": 1e-5, "cells": 65_824, "steps": 2500,
                               "meanDt_s": 1e-7, "minimumDt_s": 1e-7},
            "numericalDiagnostics": {"acceptedTimestepDistribution": {
                "methodId": "accepted-timestep-distribution-v1", "count": 2500,
                "requestedMaxDt_s": 1e-7, "total_s": 0.00025, "mean_s": 1e-7, "minimum_s": 1e-7,
                "maximum_s": 1e-7, "sourceLimitedStepCount": 0, "sourceTimestepRetries": 0}},
            "energyBalance": {"input_J": 2.0, "losses_J": 0.5, "stored_J": 1.5,
                              "relativeError": 0.0, "denominator": "input_J"},
        }

        realized = probe._validate_completed_case(result, selected, final, case, 0.00025)

        self.assertEqual(realized["discretization"]["steps"], 2500)
        self.assertEqual(realized["acceptedTimestepDistribution"]["requestedMaxDt_s"], 1e-7)
        self.assertEqual(realized["sourceTimestepRetries"], 0)
        self.assertEqual(realized["energyBalance"]["relativeError"], 0.0)

    def test_completed_case_validation_rejects_selected_event_before_final_state(self):
        case = {"maxDt_s": 1e-7, "cells": 65_824, "domain": {"dx": 1e-5}}
        accepted = [1e-7] * 2500
        selected = {"step": 2499, "time_s": 0.0002499, "roundoff_tolerance_s": 1e-12,
                    "accepted_dt_s": accepted[:-1]}
        final = {"time_s": 0.00025, "accepted_dt_s": accepted}
        result = {
            "discretization": {"mesh_m": 1e-5, "cells": 65_824, "steps": 2500,
                               "meanDt_s": 1e-7, "minimumDt_s": 1e-7},
            "numericalDiagnostics": {"acceptedTimestepDistribution": {
                "count": 2500, "requestedMaxDt_s": 1e-7, "total_s": 0.00025, "mean_s": 1e-7,
                "minimum_s": 1e-7, "maximum_s": 1e-7,
                "sourceLimitedStepCount": 0, "sourceTimestepRetries": 0}},
            "energyBalance": {"input_J": 2.0, "losses_J": 0.5, "stored_J": 1.5,
                              "relativeError": 0.0},
        }

        with self.assertRaisesRegex(ValueError, "selected event must be the final run state"):
            probe._validate_completed_case(result, selected, final, case, 0.00025)


if __name__ == "__main__":
    unittest.main()
