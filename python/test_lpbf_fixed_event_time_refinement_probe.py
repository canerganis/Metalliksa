"""Focused contract tests for the bounded 12.5 ns refinement runner."""

import copy
import json
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

import run_lpbf_fixed_event_time_refinement_probe as probe


def history(times, ever=None, values=None):
    n = len(times)
    if ever is None:
        ever = np.zeros((n, 19, 2), dtype=bool)
    if values is None:
        values = np.zeros((n, 19, 6), dtype=np.float64)
    return {
        "time_s": np.asarray(times, dtype=np.float64),
        "accepted_dt_s": np.diff(np.r_[0., times]).astype(np.float64),
        "values": np.asarray(values, dtype=np.float64),
        "ever": np.asarray(ever, dtype=bool),
        "cell_indices_ijk": np.zeros((19, 3), dtype=np.int32),
        "coordinates_m": np.zeros((19, 3), dtype=np.float64),
    }


class RefinementProtocolTests(unittest.TestCase):
    def test_live_source_change_is_rejected_before_solver(self):
        with mock.patch.object(probe, "fresh_destinations"), \
                mock.patch.object(probe.lpbf_simulation, "implementation_fingerprint", return_value="1" * 64), \
                mock.patch.object(probe.lpbf_simulation, "run", side_effect=AssertionError("solver called")):
            with self.assertRaisesRegex(ValueError, "Frozen numerical implementation changed"):
                probe.preflight()

    def test_protocol_is_frozen_and_has_only_one_new_case_and_fresh_outputs(self):
        protocol = json.loads(probe.PROTOCOL_PATH.read_text(encoding="utf-8"))
        probe._validate_protocol(protocol)
        self.assertEqual(protocol["levels"], [5e-8, 2.5e-8, 1.25e-8])
        self.assertEqual(protocol["expectedCells"], 526592)
        self.assertEqual(protocol["expectedStepsByMaxDt"]["1.25e-08"], 20000)
        self.assertEqual(protocol["maximumStepsByMaxDt"]["1.25e-08"], 22788)
        self.assertEqual(protocol["maximumTotalCellSteps"], 12_000_000_000)
        self.assertEqual(protocol["expectedImplementationFingerprint"],
                         "d7e5c4e3d5f0a59c4b955e0e1ca29f624fe6249c4e7cd1522e84ed1a87249315")
        self.assertFalse(protocol["experimentalValidation"])
        self.assertEqual(protocol["convergenceConclusion"], "inconclusive")
        self.assertTrue(protocol["output"].endswith("LPBF_FIXED_EVENT_TIME_REFINEMENT_2026-10-02.json"))
        self.assertIn("LPBF_FIXED_EVENT_TIME_REFINEMENT_2026-10-02", protocol["partial"])
        self.assertIn("LPBF_FIXED_EVENT_TIME_REFINEMENT_2026-10-02", protocol["historyDirectory"])

    def test_protocol_rejects_timestep_step_budget_and_cell_step_budget_changes(self):
        protocol = json.loads(probe.PROTOCOL_PATH.read_text(encoding="utf-8"))
        altered = copy.deepcopy(protocol)
        altered["levels"][-1] = 1e-8
        with self.assertRaisesRegex(ValueError, "fixed timestep"):
            probe._validate_protocol(altered)
        altered = copy.deepcopy(protocol)
        altered["maximumStepsByMaxDt"]["1.25e-08"] = 19999
        with self.assertRaises(ValueError):
            probe._validate_protocol(altered)
        altered = copy.deepcopy(protocol)
        altered["maximumTotalCellSteps"] -= 1
        with self.assertRaisesRegex(ValueError, "cell-step"):
            probe._validate_protocol(altered)

    @mock.patch.object(probe.lpbf_simulation, "implementation_fingerprint", return_value=probe.IMPLEMENTATION)
    def test_report_archive_and_ordered_cell_identity_fail_before_solver(self, _frozen_fingerprint):
        # Isolate archive guards from the separately tested live-source guard.
        original_protocol = probe.PROTOCOL_PATH.read_bytes()
        protocol = json.loads(original_protocol)
        actual_exists = Path.exists
        output_names = {Path(protocol[name]).name for name in ("output", "partial", "historyDirectory")}
        def destinations_are_fresh(path):
            return False if path.name in output_names else actual_exists(path)
        cases = ("history-report", "archive", "ordered-cells")
        for case in cases:
            with self.subTest(case=case):
                with mock.patch.object(Path, "exists", destinations_are_fresh):
                  with mock.patch.object(probe.lpbf_simulation, "run", side_effect=AssertionError("solver called")):
                    if case == "history-report":
                        target = probe.ROOT / protocol["historyReport"]
                        actual_hash = probe.old.sha256_file
                        def changed_hash(path):
                            return "0"*64 if Path(path) == target else actual_hash(path)
                        with mock.patch.object(probe.old, "sha256_file", side_effect=changed_hash):
                            with self.assertRaisesRegex(ValueError, "historyReport"):
                                probe.preflight()
                    elif case == "archive":
                        actual_hash = probe.old.sha256_file
                        def changed_archive(path):
                            return "0"*64 if str(path).endswith(".npz") else actual_hash(path)
                        with mock.patch.object(probe.old, "sha256_file", side_effect=changed_archive):
                            with self.assertRaisesRegex(ValueError, "archive"):
                                probe.preflight()
                    else:
                        mutated = copy.deepcopy(protocol)
                        mutated["orderedSelectedCells"][0]["coordinate_m"][0] += 1e-9
                        changed_bytes = json.dumps(mutated).encode("utf-8")
                        original_read = Path.read_bytes
                        def read_protocol(path):
                            return changed_bytes if path == probe.PROTOCOL_PATH else original_read(path)
                        with mock.patch.object(Path, "read_bytes", read_protocol):
                            with self.assertRaisesRegex(ValueError, "history report identity"):
                                probe.preflight(probe.PROTOCOL_PATH)

    def test_preflight_rejects_missing_psutil_before_solver(self):
        with mock.patch.object(probe, "_load_psutil", side_effect=ImportError("psutil unavailable")):
            with mock.patch.object(probe.lpbf_simulation, "run", side_effect=AssertionError("solver called")):
                with self.assertRaisesRegex((ImportError, RuntimeError), "psutil"):
                    probe.preflight()

    def test_existing_destination_fails_before_solver(self):
        protocol = json.loads(probe.PROTOCOL_PATH.read_text(encoding="utf-8"))
        occupied = mock.Mock()
        occupied.exists.return_value = True
        with mock.patch.object(probe, "safe_path", return_value=occupied):
            with mock.patch.object(probe.lpbf_simulation, "run", side_effect=AssertionError("solver called")):
                with self.assertRaisesRegex(FileExistsError, "destinations already exist"):
                    probe.preflight()

    def test_execute_calls_solver_once_and_persists_partial_on_step_budget_failure(self):
        protocol = json.loads(probe.PROTOCOL_PATH.read_text(encoding="utf-8"))
        key = "1.25e-08"
        protocol["maximumStepsByMaxDt"][key] = 0
        case = {"dt": 1.25e-8, "key": key, "payload": {}, "material": {},
                "domain": {}, "cells": 526592, "indices": [], "positions": [],
                "inputSha256": "0" * 64}
        plan = {"protocol": protocol, "protocolSha256": "1" * 64, "case": case,
                "histories": [history([1e-5])]*2, "baseline": {},
                "historyMaximumUncompressedBytes": 1}
        fake_paths = {name: mock.Mock() for name in ("partial", "output", "historyDirectory")}
        writes = []

        class FakeHistoryBuffer:
            count = 0
            def __init__(self, *_args):
                pass
            def observe(self, _record):
                self.count += 1

        def fake_safe_path(name):
            text = str(name)
            return fake_paths["partial" if ".partial." in text else "output" if text.endswith(".json") else "historyDirectory"]

        def bounded_run(*_args, local_history_observer, **_kwargs):
            probe.lpbf_simulation.source_limited_step()
            self.fail("a zero accepted-step budget must stop before an observation")

        psutil = mock.Mock()
        psutil.Process.return_value.memory_info.return_value.rss = 1024
        with mock.patch.object(probe, "preflight", return_value=plan):
            with mock.patch.object(probe, "safe_path", side_effect=fake_safe_path):
                with mock.patch.object(probe, "_write_json", side_effect=lambda path, _report, **_kwargs: writes.append(path)):
                    with mock.patch.object(probe, "_load_psutil", return_value=psutil):
                        with mock.patch.object(probe.old, "HistoryBuffer", FakeHistoryBuffer):
                            with mock.patch.object(probe.lpbf_simulation, "source_limited_step", return_value=(1e-8, None, None, None, 0)):
                                with mock.patch.object(probe.lpbf_simulation, "run", side_effect=bounded_run) as run:
                                    with self.assertRaisesRegex(RuntimeError, "accepted-step ceiling"):
                                        probe.execute()
        run.assert_called_once()
        self.assertGreaterEqual(len(writes), 1)
        self.assertIs(writes[0], fake_paths["partial"])

    def test_partial_after_one_accepted_observation_preserves_counters(self):
        protocol = json.loads(probe.PROTOCOL_PATH.read_text(encoding="utf-8"))
        key = "1.25e-08"
        protocol["maximumStepsByMaxDt"][key] = 1
        case = {"dt": 1.25e-8, "key": key, "payload": {}, "material": {},
                "domain": {}, "cells": 526592, "indices": [], "positions": [],
                "inputSha256": "0" * 64}
        plan = {"protocol": protocol, "protocolSha256": "1" * 64, "case": case,
                "histories": [history([1e-5])]*2, "baseline": {},
                "historyMaximumUncompressedBytes": 1}
        fake_paths = {name: mock.Mock() for name in ("partial", "output", "historyDirectory")}
        writes = []

        class FakeHistoryBuffer:
            def __init__(self, *_args):
                self.count = 0
            def observe(self, _record):
                self.count += 1

        def fake_safe_path(name):
            text = str(name)
            return fake_paths["partial" if ".partial." in text else "output" if text.endswith(".json") else "historyDirectory"]

        def after_one_step(*_args, local_history_observer, **_kwargs):
            probe.lpbf_simulation.source_limited_step()
            local_history_observer({"step": 1, "time_s": 1e-8, "acceptedDt_s": 1e-8})
            probe.lpbf_simulation.source_limited_step()

        psutil = mock.Mock()
        psutil.Process.return_value.memory_info.return_value.rss = 1024
        with mock.patch.object(probe, "preflight", return_value=plan):
            with mock.patch.object(probe, "safe_path", side_effect=fake_safe_path):
                with mock.patch.object(probe, "_write_json", side_effect=lambda path, report, **kw: writes.append((path, report.copy()))):
                    with mock.patch.object(probe, "_load_psutil", return_value=psutil):
                        with mock.patch.object(probe.old, "HistoryBuffer", FakeHistoryBuffer):
                            with mock.patch.object(probe.lpbf_simulation, "source_limited_step", return_value=(1e-8, None, None, None, 0)):
                                with mock.patch.object(probe.lpbf_simulation, "run", side_effect=after_one_step) as run:
                                    with self.assertRaisesRegex(RuntimeError, "accepted-step ceiling"):
                                        probe.execute()
        run.assert_called_once()
        partials = [report for path, report in writes if path is fake_paths["partial"]]
        self.assertTrue(partials)
        partial = partials[-1]
        self.assertEqual(partial["stage"], "partial")
        self.assertEqual(partial["runtimeWork"]["acceptedSteps"], 1)
        self.assertEqual(partial["runtimeWork"]["acceptedCellSteps"], 526592)
        self.assertEqual(partial["runtimeWork"]["lastTime_s"], 1e-8)
        self.assertFalse(any(report.get("stage") == "completed" for _, report in writes))

    def test_execute_enforces_cell_step_wall_and_sampled_rss_budgets(self):
        base = json.loads(probe.PROTOCOL_PATH.read_text(encoding="utf-8"))
        key = "1.25e-08"
        case = {"dt": 1.25e-8, "key": key, "payload": {}, "material": {},
                "domain": {}, "cells": 526592, "indices": [], "positions": [],
                "inputSha256": "0" * 64}

        class FakeHistoryBuffer:
            def __init__(self, *_args):
                self.count = 0
            def observe(self, _record):
                self.count += 1

        for budget, value, message in (("maximumTotalCellSteps", 0, "cell-step ceiling"),
                                       ("maximumWallTimeByMaxDt_s", -1, "wall-time ceiling"),
                                       ("maximumSampledRssBytes", 0, "sampled RSS ceiling")):
            with self.subTest(budget=budget):
                protocol = copy.deepcopy(base)
                if budget == "maximumWallTimeByMaxDt_s":
                    protocol[budget][key] = value
                else:
                    protocol[budget] = value
                fake_plan = {"protocol": protocol, "protocolSha256": "1"*64, "case": case,
                             "histories": [history([1e-5])]*2, "baseline": {},
                             "historyMaximumUncompressedBytes": 1}
                paths = {name: mock.Mock() for name in ("partial", "output", "historyDirectory")}
                psutil = mock.Mock()
                psutil.Process.return_value.memory_info.return_value.rss = 1024 if budget == "maximumSampledRssBytes" else 0
                def fake_run(*_args, **_kwargs):
                    probe.lpbf_simulation.source_limited_step()
                    raise AssertionError("cell-step guard should stop before advancing")
                run_effect = fake_run if budget == "maximumTotalCellSteps" else AssertionError("must stop at guard")
                def fake_safe_path(name):
                    value = str(name)
                    return paths["partial" if ".partial." in value else "output" if value.endswith(".json") else "historyDirectory"]
                with mock.patch.object(probe, "preflight", return_value=fake_plan):
                    with mock.patch.object(probe, "safe_path", side_effect=fake_safe_path):
                        with mock.patch.object(probe, "_write_json") as write:
                            with mock.patch.object(probe, "_load_psutil", return_value=psutil):
                                with mock.patch.object(probe.old, "HistoryBuffer", FakeHistoryBuffer):
                                    with mock.patch.object(probe.lpbf_simulation, "source_limited_step", return_value=(1e-8, None, None, None, 0)):
                                        with mock.patch.object(probe.lpbf_simulation, "run", side_effect=run_effect):
                                            with self.assertRaisesRegex(RuntimeError, message):
                                                probe.execute()
                self.assertGreaterEqual(write.call_count, 1)
                self.assertEqual(write.call_args.args[1]["stage"], "partial")
                self.assertIn(message, write.call_args.args[1]["reason"])

    @mock.patch.object(probe.lpbf_simulation, "implementation_fingerprint", return_value=probe.IMPLEMENTATION)
    def test_execute_one_mocked_case_checks_observer_fields_and_completes_artifacts(self, _frozen_fingerprint):
        protocol = json.loads(probe.PROTOCOL_PATH.read_text(encoding="utf-8"))
        event_time = 2e-8
        protocol["expectedEventTime_s"] = event_time
        key = "1.25e-08"
        indices = [(i, 0, 0) for i in range(19)]
        positions = [[float(i), 0., 0.] for i in range(19)]
        case = {"dt": 1.25e-8, "key": key, "payload": {},
                "material": {"liquidus_K": 1000.},
                "domain": {"nx": 19, "ny": 1, "nz": 1}, "cells": 19,
                "indices": indices, "positions": positions,
                "inputSha256": "a" * 64}
        baseline = history([1e-8, event_time])
        baseline["cell_indices_ijk"] = np.asarray(indices, dtype="<i4")
        baseline["coordinates_m"] = np.asarray(positions, dtype="<f8")
        baseline["values"][:, :, 0] = 300.
        baseline["values"][:, :, 2] = 1.
        plan = {"protocol": protocol, "protocolSha256": "b"*64, "case": case,
                "histories": [baseline, baseline], "baseline": {},
                "historyMaximumUncompressedBytes": 10_000}

        class MemoryPath:
            def __init__(self, name):
                self.name = str(name)
                self.removed = False
            def mkdir(self):
                return None
            def __truediv__(self, child):
                return MemoryPath(self.name + "/" + str(child))
            def stat(self):
                return mock.Mock(st_size=256)
            def relative_to(self, _root):
                return self
            def as_posix(self):
                return self.name.replace("\\", "/")
            def unlink(self):
                self.removed = True
            def exists(self):
                return not self.removed

        paths = {"partial": MemoryPath("docs/partial.json"),
                 "output": MemoryPath("docs/output.json"),
                 "historyDirectory": MemoryPath("docs/fields")}
        writes = []
        archives = []
        psutil = mock.Mock()
        psutil.Process.return_value.memory_info.return_value.rss = 1024

        def fake_safe_path(name):
            value = str(name)
            return paths["partial" if ".partial." in value else "output" if value.endswith(".json") else "historyDirectory"]

        def fake_run(*_args, final_state_observer, local_history_observer,
                     local_history_indices_ijk, **_kwargs):
            self.assertEqual(local_history_indices_ijk, indices)
            for step, time_s in ((1, 1e-8), (2, event_time)):
                probe.lpbf_simulation.source_limited_step()
                cells = [{"coordinate_m": position, "temperature_K": 300.,
                          "enthalpy_J_m3": 0., "effectiveConductivity_W_mK": 1.,
                          "sourceRate_W_m3": 0., "conductionRate_W_m3": 0.,
                          "passiveRate_W_m3": 0., "everLiquidusBefore": False,
                          "everLiquidusAfter": False} for position in positions]
                local_history_observer({"step": step, "time_s": time_s,
                                        "acceptedDt_s": 1e-8,
                                        "cell_indices_ijk": [list(v) for v in indices],
                                        "cells": cells})
            final_state_observer({"time_s": event_time,
                                  "coordinates_m": np.asarray(positions, dtype="<f8"),
                                  "temperature_K": np.full(19, 300., dtype="<f8"),
                                  "enthalpy_J_m3": np.zeros(19, dtype="<f8"),
                                  "density_kg_m3": np.ones(19, dtype="<f8"),
                                  "accepted_dt_s": np.full(2, 1e-8, dtype="<f8")})
            return {"provenance": {"executionInputHash": case["inputSha256"],
                                   "implementationHash": probe.IMPLEMENTATION}}

        with mock.patch.object(probe, "preflight", return_value=plan):
            with mock.patch.object(probe, "safe_path", side_effect=fake_safe_path):
                with mock.patch.object(probe, "_write_json", side_effect=lambda path, report, **kw: writes.append((path, report.copy()))):
                    with mock.patch.object(probe, "_load_psutil", return_value=psutil):
                        with mock.patch.object(probe.np, "savez_compressed", side_effect=lambda path, **fields: archives.append((path, fields))):
                            with mock.patch.object(probe.old, "sha256_file", return_value="c"*64):
                                with mock.patch.object(probe.lpbf_simulation, "source_limited_step", return_value=(1e-8, None, None, None, 0)):
                                    with mock.patch.object(probe.lpbf_simulation, "run", side_effect=fake_run) as run:
                                        report = probe.execute()
        run.assert_called_once()
        self.assertEqual(report["stage"], "completed")
        self.assertTrue(report["localFinalTemperatureEnthalpyCoordinatesExactMatch"])
        self.assertEqual(report["runtimeWork"]["acceptedSteps"], 2)
        self.assertEqual(len(archives), 2)
        self.assertEqual(len(writes), 3)
        self.assertEqual(writes[-1][1]["stage"], "completed")


class CanonicalHistoryComparisonTests(unittest.TestCase):
    def test_equal_and_different_histories_are_compared_at_exact_canonical_times(self):
        times = np.arange(1, 6, dtype=float) * 1e-5
        a = history(times)
        b = history(times)
        equal = probe.compare_canonical_histories(a, b, b, times[-1])
        self.assertEqual(equal["comparisonStatus"], "comparable")
        self.assertEqual(equal["refinementEverMismatchCheckpointCells"], 0)
        changed = np.zeros((5, 19, 2), dtype=bool)
        changed[-1, 0, 1] = True
        different = probe.compare_canonical_histories(a, b, history(times, ever=changed), times[-1])
        self.assertEqual(different["refinementEverMismatchCheckpointCells"], 1)
        self.assertEqual(different["possibleCheckpointCellPairs"], 5 * 19)

    def test_missing_canonical_timestamp_is_inconclusive_without_interpolation(self):
        times = np.arange(1, 6, dtype=float) * 1e-5
        result = probe.compare_canonical_histories(
            history(times), history(times), history(times[[0, 1, 3, 4]]), times[-1])
        self.assertEqual(result["comparisonStatus"], "inconclusive")
        self.assertEqual(result["refinementEverMismatchCheckpointCells"], None)
        self.assertTrue(result.get("missingCanonicalTimestamp"))

    def test_transition_summary_marks_absence_censored_and_keeps_sides_separate(self):
        arrays = history([1e-5, 2e-5, 3e-5])
        summary = probe.transition_summary(arrays, 3e-5)
        self.assertEqual(len(summary), 19)
        self.assertTrue(all(row["crossingTime_s"] is None and row["censoredAtEvent"]
                            for row in summary))
        triggered = np.zeros((3, 19, 2), dtype=bool)
        triggered[1:, 0, 1] = True
        summary = probe.transition_summary(history([1e-5, 2e-5, 3e-5], ever=triggered), 3e-5)
        self.assertEqual(summary[0]["crossingTime_s"], 2e-5)
        self.assertFalse(summary[0]["censoredAtEvent"])


if __name__ == "__main__":
    unittest.main()
