import copy
import json
import unittest

import run_lpbf_fixed_event_mesh_refinement_probe as probe


class FixedEventMeshRefinementProbeTests(unittest.TestCase):
    def test_protocol_uses_common_dt_and_three_declared_layer_aligned_domains(self):
        protocol = json.loads(probe.PROTOCOL_PATH.read_text(encoding="utf-8"))

        probe._validate_protocol(protocol)

        self.assertEqual(protocol["meshLevels_um"], [20, 10, 5])
        self.assertEqual(protocol["maxDt_s"], 1e-7)
        self.assertTrue(protocol["protocolId"].endswith("-v2"))
        self.assertEqual({key: value["cells"] for key, value in protocol["expectedDomainByMesh_um"].items()},
                         {"20": 8228, "10": 65824, "5": 526592})
        self.assertEqual(protocol["stepsPerCase"], 3000)
        self.assertEqual(protocol["predictedTotalSteps"], 9000)
        self.assertEqual(protocol["predictedTotalCellSteps"], 1_801_932_000)
        self.assertEqual(protocol["maximumTotalCellSteps"], 1_900_000_000)
        self.assertIn("_V2_", protocol["output"])
        self.assertIn("_V2_", protocol["partial"])
        self.assertIn("_V2_", protocol["fieldDirectory"])
        self.assertFalse(protocol["experimentalValidation"])
        self.assertEqual(protocol["convergenceConclusion"], "inconclusive")

    def test_protocol_rejects_temporal_level_or_resource_bound_changes(self):
        protocol = json.loads(probe.PROTOCOL_PATH.read_text(encoding="utf-8"))
        wrong_dt = copy.deepcopy(protocol)
        wrong_dt["maxDt_s"] = 5e-8
        with self.assertRaisesRegex(ValueError, "common fixed timestep"):
            probe._validate_protocol(wrong_dt)

        under_budget = copy.deepcopy(protocol)
        under_budget["maximumTotalCellSteps"] = 1_801_932_000 - 1
        with self.assertRaisesRegex(ValueError, "cell-step ceiling"):
            probe._validate_protocol(under_budget)

    def test_preflight_resolves_exact_meshes_and_common_event_without_solving(self):
        protocol, raw_protocol, _scenario, event, cases = probe.preflight()

        self.assertEqual(len(raw_protocol), len(probe.PROTOCOL_PATH.read_bytes()))
        self.assertEqual(event["end_s"], protocol["expectedEventTime_s"])
        self.assertEqual([case["cells"] for case in cases], [8228, 65824, 526592])
        self.assertTrue(all(case["payload"]["maxDt_s"] == 1e-7 for case in cases))

    def test_completed_case_validation_requires_final_selected_event_and_preserves_ledger(self):
        accepted = [1e-7] * 2500
        selected = {"step": 2500, "time_s": 0.00025, "roundoff_tolerance_s": 1e-12,
                    "accepted_dt_s": accepted}
        final = {"time_s": 0.00025, "accepted_dt_s": accepted}
        case = {"maxDt_s": 1e-7, "mesh_um": 10, "cells": 65824,
                "domain": {"dx": 1e-5}}
        result = {
            "effectiveMode": "standard",
            "solver": {"id": "enthalpy-fv-6"},
            "coreContract": {"modelId": "stationary-enthalpy-conduction-layer-conforming-v1",
                             "actualBackend": "numpy-reference", "solverId": "enthalpy-fv-6"},
            "material": {"name": "Inconel 718", "materialId": "in718",
                         "materialRevisionSha256": "f" * 64, "version": "lpbf-materials-1"},
            "discretization": {"mesh_m": 1e-5, "cells": 65824, "steps": 2500,
                               "meanDt_s": 1e-7, "minimumDt_s": 1e-7},
            "numericalDiagnostics": {"acceptedTimestepDistribution": {
                "methodId": "accepted-timestep-distribution-v1", "count": 2500,
                "requestedMaxDt_s": 1e-7, "total_s": 0.00025, "mean_s": 1e-7,
                "minimum_s": 1e-7, "maximum_s": 1e-7,
                "sourceLimitedStepCount": 0, "sourceTimestepRetries": 0}},
            "energyBalance": {"input_J": 2.0, "losses_J": 0.5, "stored_J": 1.5,
                              "relativeError": 0.0},
        }

        row = probe._validate_completed_case(result, selected, final, case, 0.00025)

        self.assertEqual(row["sourceTimestepRetries"], 0)
        self.assertEqual(row["energyBalance"]["relativeError"], 0.0)
        self.assertEqual(row["discretization"]["cells"], 65824)
        earlier_event = {**selected, "time_s": 0.000249}
        with self.assertRaisesRegex(ValueError, "selected event must be the final run state"):
            probe._validate_completed_case(result, earlier_event, final, case, 0.00025)


if __name__ == "__main__":
    unittest.main()
