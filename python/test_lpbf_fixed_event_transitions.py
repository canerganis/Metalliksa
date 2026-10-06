"""Tests for bounded, accepted-step liquidus transition analysis."""

import hashlib
import json
import unittest
from pathlib import Path
from unittest import mock
from uuid import uuid4

import numpy as np

import analyze_lpbf_fixed_event_transitions as transitions


SCRATCH = Path(__file__).resolve().parents[1] / ".tmp-lpbf-transition-analysis-20261002"
LEVELS = (5e-8, 2.5e-8, 1.25e-8)
EVENT = 2.5e-8


def make_history(times, first_true_steps, cells=2, identity=None):
    times = np.asarray(times, dtype="<f8")
    dt = np.diff(np.r_[0., times]).astype("<f8")
    indices = np.asarray(identity if identity is not None else [[i, 0, 0] for i in range(cells)], dtype="<i4")
    coordinates = indices.astype("<f8") * 1e-6
    ever = np.zeros((len(times), cells, 2), dtype=np.bool_)
    for cell, first_true in enumerate(first_true_steps):
        seen = False
        for step in range(len(times)):
            ever[step, cell, 0] = seen
            if first_true is not None and step >= first_true:
                seen = True
            ever[step, cell, 1] = seen
    values = np.zeros((len(times), cells, 6), dtype="<f8")
    values[:, :, 0] = 300.
    values[:, :, 2] = 1.
    return {"time_s": times, "accepted_dt_s": dt, "values": values,
            "ever": ever, "cell_indices_ijk": indices,
            "coordinates_m": coordinates}


def trio(crossings, *, cells=2):
    result = {}
    for level, spec in zip(LEVELS, crossings):
        times, per_cell = spec
        result[level] = make_history(times, per_cell, cells=cells)
    return result


class TransitionSummaryTests(unittest.TestCase):
    def test_reports_each_crossing_as_accepted_step_right_endpoint_and_interval(self):
        data = trio([
            ([1e-8, EVENT], [0, None]),
            ([1.25e-8, EVENT], [1, None]),
            ([1e-8, 1.5e-8, 2e-8, EVENT], [2, None]),
        ])
        result = transitions.analyze_transition_histories(data, EVENT)
        first = result["cells"][0]
        coarse = first["byLevel"]["5e-08"]
        self.assertEqual(coarse["crossingTime_s"], 1e-8)
        self.assertEqual(coarse["acceptedInterval_s"], [0., 1e-8])
        self.assertEqual(coarse["intervalConvention"], "(previousAcceptedTime_s, crossingTime_s]")
        self.assertFalse(coarse["rightCensored"])

    def test_absence_is_null_right_censored_at_the_fixed_event(self):
        times = np.linspace(EVENT/10, EVENT, 10)
        data = {level: make_history(times, [None, None]) for level in LEVELS}
        result = transitions.analyze_transition_histories(data, EVENT)
        for row in result["cells"]:
            for level in row["byLevel"].values():
                self.assertIsNone(level["crossingTime_s"])
                self.assertIsNone(level["acceptedInterval_s"])
                self.assertEqual(level["rightCensoredAt_s"], EVENT)

    def test_first_step_crossing_is_bounded_from_zero(self):
        data = {level: make_history([EVENT/2, EVENT], [0, None]) for level in LEVELS}
        row = transitions.analyze_transition_histories(data, EVENT)["cells"][0]["byLevel"]["1.25e-08"]
        self.assertEqual(row["firstEverStep"], 1)
        self.assertEqual(row["acceptedInterval_s"], [0., EVENT/2])

    def test_terminal_step_crossing_is_marked_boundary_sensitive(self):
        data = {level: make_history([EVENT/2, EVENT], [1, None]) for level in LEVELS}
        row = transitions.analyze_transition_histories(data, EVENT)["cells"][0]["byLevel"]["5e-08"]
        self.assertTrue(row["terminalCrossing"])
        self.assertEqual(row["crossingTime_s"], EVENT)

    def test_pair_deltas_preserve_raw_roundoff_sized_values(self):
        data = {
            LEVELS[0]: make_history([1e-8, 2e-8, EVENT], [1, None]),
            LEVELS[1]: make_history([1e-8, 1.5e-8, 2e-8, EVENT], [2, None]),
            LEVELS[2]: make_history([1e-8, 1.5e-8, 2e-8, EVENT], [2, None]),
        }
        # Shift only accepted timestamps, retaining a valid positive dt chain.
        fine = data[LEVELS[2]]
        fine["time_s"] = fine["time_s"] + np.array([0., 0., 5e-15, 5e-15])
        fine["accepted_dt_s"] = np.diff(np.r_[0., fine["time_s"]]).astype("<f8")
        result = transitions.analyze_transition_histories(data, EVENT)
        comparison = result["cells"][0]["comparisons"]["25nsTo12_5ns"]
        self.assertAlmostEqual(comparison["rawDelta_s"], 5e-15, places=22)
        self.assertTrue(comparison["roundoffEquivalent"])

    def test_one_sided_crossing_keeps_delta_null(self):
        data = {level: make_history([EVENT/2, EVENT], [0 if level == LEVELS[0] else None, None])
                for level in LEVELS}
        comparisons = transitions.analyze_transition_histories(data, EVENT)["cells"][0]["comparisons"]
        self.assertEqual(comparisons["50nsTo25ns"]["status"], "one_sided_crossing")
        self.assertIsNone(comparisons["50nsTo25ns"]["rawDelta_s"])

    def test_rejects_malformed_clock_chain_and_ever_state(self):
        data = {level: make_history([EVENT/2, EVENT], [1, None]) for level in LEVELS}
        damaged = {key: value.copy() for key, value in data[LEVELS[1]].items()}
        damaged["accepted_dt_s"][0] += 1e-8
        data[LEVELS[1]] = damaged
        with self.assertRaisesRegex(ValueError, "clock"):
            transitions.analyze_transition_histories(data, EVENT)
        data[LEVELS[1]] = make_history([EVENT/2, EVENT], [1, None])
        data[LEVELS[1]]["ever"][1, 0, 0] = True
        with self.assertRaisesRegex(ValueError, "ever"):
            transitions.analyze_transition_histories(data, EVENT)

    def test_rejects_negative_clock_hidden_by_absolute_roundoff_tolerance(self):
        tiny_event = 3e-15
        arrays = make_history([-1e-15, tiny_event], [1, None])
        arrays["accepted_dt_s"] = np.asarray([1e-15, 2e-15], dtype="<f8")
        data = {level: {name: value.copy() for name, value in arrays.items()} for level in LEVELS}
        with self.assertRaisesRegex(ValueError, "positive"):
            transitions.analyze_transition_histories(data, tiny_event)

    def test_rejects_inconsistent_cell_order_or_coordinates(self):
        data = {level: make_history([EVENT/2, EVENT], [0, None]) for level in LEVELS}
        data[LEVELS[2]]["coordinates_m"][0, 0] += 1e-6
        with self.assertRaisesRegex(ValueError, "grid|cell"):
            transitions.analyze_transition_histories(data, EVENT)


class ArchiveAndOutputTests(unittest.TestCase):
    def test_refinement_report_pin_rejects_archive_hash_self_consistency_tampering(self):
        report_path = transitions.ROOT / "docs/LPBF_FIXED_EVENT_TIME_REFINEMENT_2026-10-02.json"
        original = report_path.read_bytes()
        report = json.loads(original)
        report["rows"][0]["historyArtifact"]["sha256"] = "f" * 64
        tampered = json.dumps(report, sort_keys=True).encode("utf-8")
        with self.assertRaisesRegex(ValueError, "Frozen refinement report hash mismatch"):
            transitions._parse_pinned_json(
                tampered, transitions.EXPECTED_REFINEMENT_REPORT_SHA256, "Frozen refinement report")

    def test_archive_reader_checks_archive_and_each_array_hash(self):
        arrays = make_history([EVENT/2, EVENT], [1, None])
        archive_path = SCRATCH / f"test-history-{uuid4().hex}.npz"
        try:
            np.savez_compressed(archive_path, **arrays)
            digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
            array_hashes = {name: transitions.array_sha256(value) for name, value in arrays.items()}
            loaded = transitions.load_history_archive(archive_path, digest, array_hashes,
                                                       5e-8, EVENT)
            self.assertTrue(np.array_equal(loaded["ever"], arrays["ever"]))
            with self.assertRaisesRegex(ValueError, "archive hash"):
                transitions.load_history_archive(archive_path, "0"*64, array_hashes,
                                                 5e-8, EVENT)
            wrong = dict(array_hashes)
            wrong["time_s"] = "0"*64
            with self.assertRaisesRegex(ValueError, "array.*hash"):
                transitions.load_history_archive(archive_path, digest, wrong,
                                                 5e-8, EVENT)
        finally:
            archive_path.unlink(missing_ok=True)

    def test_output_pair_uses_no_overwrite_policy(self):
        identifier = uuid4().hex
        json_path, md_path = SCRATCH / f"out-{identifier}.json", SCRATCH / f"out-{identifier}.md"
        try:
            transitions.write_outputs(json_path, md_path, {"status": "ok"}, "# report\n")
            self.assertEqual(json_path.read_text(encoding="utf-8"), '{\n  "status": "ok"\n}\n')
            self.assertEqual(md_path.read_text(encoding="utf-8"), "# report\n")
            with self.assertRaisesRegex(FileExistsError, "exists"):
                transitions.write_outputs(json_path, md_path, {"status": "other"}, "overwritten\n")
            self.assertEqual(md_path.read_text(encoding="utf-8"), "# report\n")
        finally:
            json_path.unlink(missing_ok=True)
            md_path.unlink(missing_ok=True)

    def test_one_existing_output_prevents_creation_of_its_pair(self):
        identifier = uuid4().hex
        json_path, md_path = SCRATCH / f"out-{identifier}.json", SCRATCH / f"out-{identifier}.md"
        md_path.write_text("existing\n", encoding="utf-8")
        try:
            with self.assertRaisesRegex(FileExistsError, "exists"):
                transitions.write_outputs(json_path, md_path, {"status": "new"}, "new\n")
            self.assertFalse(json_path.exists())
            self.assertEqual(md_path.read_text(encoding="utf-8"), "existing\n")
        finally:
            json_path.unlink(missing_ok=True)
            md_path.unlink(missing_ok=True)

    def test_failed_second_link_does_not_remove_replaced_first_destination(self):
        identifier = uuid4().hex
        json_path, md_path = SCRATCH / f"race-{identifier}.json", SCRATCH / f"race-{identifier}.md"
        original_link = transitions.os.link
        calls = 0

        def link_with_replacement(source, destination):
            nonlocal calls
            calls += 1
            if calls == 1:
                original_link(source, destination)
                Path(destination).unlink()
                Path(destination).write_text("replacement owned by another writer\n", encoding="utf-8")
                return None
            raise OSError("simulated second-link failure")

        try:
            with mock.patch.object(transitions.os, "link", side_effect=link_with_replacement):
                with self.assertRaisesRegex(OSError, "second-link failure"):
                    transitions.write_outputs(json_path, md_path, {"status": "new"}, "new\n")
            self.assertEqual(json_path.read_text(encoding="utf-8"), "replacement owned by another writer\n")
            self.assertFalse(md_path.exists())
        finally:
            json_path.unlink(missing_ok=True)
            md_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
