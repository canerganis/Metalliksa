"""Bounded diagnostic contracts; never launch the expensive solver."""
import copy
import contextlib
import importlib.util
import json
import math
import shutil
import unittest
import uuid
from pathlib import Path
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "python/run_lpbf_fixed_event_5um_time_probe.py"


@contextlib.contextmanager
def workspace_temporary_directory():
    # Plain mkdir inherits workspace ACLs; tempfile's restrictive Windows ACLs
    # cannot be traversed by this sandbox. Delete only this verified test root.
    path = ROOT / "python" / (".tmp-5um-time-probe-" + uuid.uuid4().hex)
    path.mkdir()
    try:
        yield path
    finally:
        if not path.resolve().is_relative_to((ROOT / "python").resolve()):
            raise ValueError("Test cleanup path escaped the workspace")
        shutil.rmtree(path)


class FiveUmTimeProbeTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(RUNNER.is_file(), "5um fixed-event runner has not been implemented")
        spec = importlib.util.spec_from_file_location("five_um_probe_test_subject", RUNNER)
        self.probe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.probe)
        # Baseline/field unit tests remain usable after a genuine execution.
        # The production CLI still checks fresh destinations before any solve.
        self.fresh_patch = mock.patch.object(self.probe, "fresh_destinations")
        self.fresh_patch.start()
        self.addCleanup(self.fresh_patch.stop)

    def test_preflight_binds_baseline_and_two_new_levels_without_solver(self):
        with mock.patch.object(self.probe.lpbf_simulation, "run", side_effect=AssertionError("must not solve")):
            plan = self.probe.preflight()
        self.assertEqual([c["maxDt_s"] for c in plan["cases"]], [5e-8, 2.5e-8])
        self.assertEqual([c["predictedSteps"] for c in plan["cases"]], [5000, 10000])
        self.assertEqual(plan["baseline"]["step"], 2920)
        self.assertEqual(plan["baselineRow"]["sourceTimestepRetries"], 1673)
        self.assertEqual(plan["protocol"]["predictedTotalCellSteps"], 7_898_880_000)
        self.assertFalse(plan["protocol"]["experimentalValidation"])

    def test_protocol_rejects_budget_or_scientific_scope_mutations(self):
        p = json.loads(self.probe.PROTOCOL_PATH.read_text())
        for key, value in [("maximumTotalCellSteps", 7_898_879_999),
                           ("levels", [5e-8, 1.25e-8]),
                           ("experimentalValidation", True),
                           ("mesh_um", 10), ("maximumStepsByMaxDt", {"5e-08": 50000, "2.5e-08": 11000})]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.probe.validate_protocol({**p, key: value})

    def test_baseline_rejects_changed_report_or_material_before_reuse(self):
        plan = self.probe.preflight()
        for key in ("reportSha256", "fieldSha256", "materialRevisionSha256", "inputSha256"):
            p = copy.deepcopy(plan["protocol"])
            p["baseline"][key] = "0" * 64
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.probe.load_baseline(p, plan["baselineCase"])

    def test_baseline_rejects_changed_implementation(self):
        p = json.loads(self.probe.PROTOCOL_PATH.read_text())
        with mock.patch.object(self.probe.lpbf_simulation, "implementation_fingerprint", return_value="0" * 64):
            with self.assertRaisesRegex(ValueError, "implementation"):
                self.probe.preflight()

    def test_clock_replay_rejects_negative_steps_and_wrong_event(self):
        good = self.probe.replay_steps(np.array([.1, .1]), .2, .1, 1e-14)
        self.assertEqual(good["count"], 2)
        self.assertEqual(good["replayedTime_s"], .2)
        for steps, target in [([.1, -.1], .2), ([.1, .1], .3), ([float("nan")], .1), ([.11, .09], .2)]:
            with self.subTest(steps=steps), self.assertRaises(ValueError):
                self.probe.replay_steps(steps, target, .1, 1e-14)

    def test_field_metrics_have_weighted_l2_rms_and_maximum(self):
        m = self.probe.field_difference([1., 2., 2.], [2., 2., 4.], .5)
        self.assertAlmostEqual(m["volumeL2Difference"], math.sqrt(2.5))
        self.assertAlmostEqual(m["rmsDifference"], math.sqrt(5/3))
        self.assertEqual(m["maximumAbsoluteDifference"], 2.)

    def test_phase_audit_distinguishes_powder_melt_from_substrate_penetration(self):
        # An analytic liquidus bottom at z=+0.5; top powder cells are molten.
        axis = np.array([-1.5, -.5, .5, 1.5])
        xyz = np.stack(np.meshgrid(axis, axis, axis, indexing="ij"), -1).reshape(-1, 3)
        t = 1000 + 100 * (xyz[:, 2] - .5) - 200 * xyz[:, 1] ** 2
        snap = {"coordinates_m": xyz, "temperature_K": t, "cell_volume_m3": 1.}
        audit = self.probe.phase_plane_audit(snap, 1., {"liquidus_K": 1000., "solidus_K": 900.},
                                              x_position_m=0., surface_m=2., z_plane_m=1.)
        self.assertEqual(audit["substrate"]["liquidusCells"], 0)
        self.assertGreater(audit["powder"]["liquidusCells"], 0)
        self.assertTrue(audit["fixedEventCrossSection"]["topBoundaryMolten"])
        self.assertEqual(audit["substratePenetration_um"], 0.)
        self.assertGreater(audit["surfaceReferencedMeltDepth_um"], 0.)
        self.assertEqual(audit["commonZWidth"]["status"], "thermal-proxy")
        self.assertEqual(audit["commonZWidth"]["width_um"], 1_000_000.)

    def test_phase_audit_records_resolved_volumes_and_molten_z(self):
        plan = self.probe.preflight()
        snapshot = plan["baseline"]
        audit = self.probe.phase_plane_audit(snapshot, 5e-6, plan["baselineCase"]["material"])
        self.assertIn("liquidusVolume_m3", audit["substrate"])
        self.assertEqual(audit["substrate"]["liquidusVolume_m3"], 0.)
        self.assertAlmostEqual(audit["lowestMoltenCellZ_m"], 7.5e-6)
        self.assertAlmostEqual(audit["powder"]["liquidusVolume_m3"],
                               audit["powder"]["liquidusCells"] * (5e-6)**3)

    def test_field_validator_rejects_inconsistent_density_and_cell_volume(self):
        plan = self.probe.preflight()
        for key, replacement in [("cell_volume_m3", 1.),
                                 ("density_kg_m3", np.ones(plan["baselineCase"]["cells"]))]:
            corrupted = {**plan["baseline"], key: replacement}
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "density|cell volume"):
                self.probe.validate_state(corrupted, plan["baselineRow"], plan["baselineCase"], plan["protocol"])

    def test_plane_audit_rejects_out_of_support_extrapolation(self):
        plan = self.probe.preflight()
        with self.assertRaisesRegex(ValueError, "support"):
            self.probe.phase_plane_audit(plan["baseline"], 5e-6, plan["baselineCase"]["material"],
                                         z_plane_m=40e-6)

    def test_runtime_guard_stops_before_next_source_update(self):
        state = {"acceptedSteps": 0, "caseSteps": 0, "acceptedCellSteps": 0}
        p = json.loads(self.probe.PROTOCOL_PATH.read_text())
        case = {"cells": 526592, "maxDt_s": 5e-8}
        with mock.patch.object(self.probe.lpbf_simulation, "source_limited_step", return_value="accepted") as source:
            with self.probe.step_budget(state, case, p):
                self.assertEqual(self.probe.lpbf_simulation.source_limited_step(), "accepted")
                state["caseSteps"] = 5500
                with self.assertRaisesRegex(RuntimeError, "step ceiling"):
                    self.probe.lpbf_simulation.source_limited_step()
            self.assertEqual(source.call_count, 1)
        self.assertEqual(state["acceptedCellSteps"], 526592)

    def test_runtime_guard_enforces_cell_work_and_wall_before_source(self):
        p = json.loads(self.probe.PROTOCOL_PATH.read_text())
        case = {"cells": 526592, "maxDt_s": 5e-8}
        for state, clock in [({"acceptedSteps": 0, "caseSteps": 0, "acceptedCellSteps": p["maximumTotalCellSteps"]}, [0., 0.]),
                             ({"acceptedSteps": 0, "caseSteps": 0, "acceptedCellSteps": 0}, [0., 1201.])]:
            with mock.patch.object(self.probe.lpbf_simulation, "source_limited_step") as source:
                with self.probe.step_budget(state, case, p, clock=iter(clock).__next__):
                    with self.assertRaises(RuntimeError):
                        self.probe.lpbf_simulation.source_limited_step()
                source.assert_not_called()

    def test_runtime_guard_checks_rss_before_source_and_restores_on_failure(self):
        p = json.loads(self.probe.PROTOCOL_PATH.read_text())
        state = {"acceptedSteps": 0, "caseSteps": 0, "acceptedCellSteps": 0}
        case = {"cells": 526592, "maxDt_s": 5e-8}
        with mock.patch.object(self.probe.lpbf_simulation, "source_limited_step") as source:
            with self.probe.step_budget(state, case, p, rss_reader=lambda: 805306369):
                with self.assertRaisesRegex(RuntimeError, "RSS"):
                    self.probe.lpbf_simulation.source_limited_step()
            self.assertIs(self.probe.lpbf_simulation.source_limited_step, source)
            source.assert_not_called()

    def test_executor_retains_first_row_and_failed_partial_without_solver(self):
        # The controlled execution fixture advances guard calls only; no heat solve.
        probe = self.probe
        plan = probe.preflight()
        actual_safe_path = probe.safe_path
        with workspace_temporary_directory() as temporary:
            destination = Path(temporary)

            def paths(relative):
                if relative in [plan["protocol"][key] for key in ("output", "partial", "fieldDirectory")]:
                    return destination / Path(relative).name
                return actual_safe_path(relative)

            def controlled_run(payload, selected_time_observer, selected_time_s, final_state_observer):
                if payload["maxDt_s"] == 2.5e-8:
                    raise RuntimeError("controlled second-row failure")
                dt = np.full(5000, 5e-8)
                replay = probe.replay_steps(dt, selected_time_s, 5e-8, 1e-14)
                snapshot = {**plan["baseline"], "accepted_dt_s": dt, "step": 5000,
                            "time_s": replay["replayedTime_s"], "target_time_s": selected_time_s,
                            "scheduler_time_s": selected_time_s,
                            "time_difference_s": selected_time_s-replay["replayedTime_s"],
                            "roundoff_tolerance_s": min(1e-14, 2*math.ulp(selected_time_s)*5001)}
                for _ in dt:
                    probe.lpbf_simulation.source_limited_step()
                selected_time_observer(snapshot)
                final_state_observer({"time_s": selected_time_s, "accepted_dt_s": dt})
                row = plan["baselineRow"]
                return {"effectiveMode": "standard", "solver": row["solver"], "coreContract": row["model"],
                        "material": row["material"], "energyBalance": row["energyBalance"],
                        "discretization": {"cells": 526592, "steps": 5000, "mesh_m": 5e-6,
                                           "meanDt_s": float(dt.mean()), "minimumDt_s": 5e-8},
                        "numericalDiagnostics": {"acceptedTimestepDistribution":
                            probe.lpbf_simulation.summarize_accepted_timesteps(dt, 5e-8, 0, 0)}}

            with mock.patch.object(probe, "preflight", return_value=plan), \
                    mock.patch.object(probe, "safe_path", side_effect=paths), \
                    mock.patch.object(probe.lpbf_simulation, "source_limited_step", return_value=None), \
                    mock.patch.object(probe.lpbf_simulation, "run", side_effect=controlled_run):
                with self.assertRaisesRegex(RuntimeError, "controlled second-row failure"):
                    probe.execute()
            partial = json.loads((destination / Path(plan["protocol"]["partial"]).name).read_text())
            self.assertEqual(partial["stage"], "failed")
            self.assertEqual(len(partial["rows"]), 2)
            self.assertTrue(partial["rows"][0]["reused"])
            self.assertEqual(partial["runtimeWork"]["acceptedCellSteps"], 2_632_960_000)
            self.assertEqual(partial["rows"][1]["acceptedClockReplay"]["count"], 5000)
            self.assertTrue((destination / Path(plan["protocol"]["fieldDirectory"]).name /
                             partial["rows"][1]["fieldArtifact"]["path"]).is_file())
            self.assertFalse((destination / Path(plan["protocol"]["output"]).name).exists())


if __name__ == "__main__":
    unittest.main()
