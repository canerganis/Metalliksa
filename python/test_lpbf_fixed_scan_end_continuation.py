"""Pure admission and planning tests for the separately versioned continuation."""

import copy
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import run_lpbf_fixed_scan_end_convergence as original
import run_lpbf_fixed_scan_end_continuation as continuation


class FixedScanEndContinuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (cls.protocol, cls.scenario, cls.specs, cls.fingerprint, *_rest) = original.preflight()
        cls.coarse = json.loads(continuation.COARSE_REPORT_PATH.read_bytes())

    def test_exact_five_case_plan_reuses_two_and_orders_only_three_missing_cases(self):
        all_cases, reused, new = continuation._expected_cases(self.protocol)
        self.assertEqual(len(all_cases), 5)
        self.assertEqual([(row["mesh_um"], row["maxDt_s"]) for row in reused],
                         [(20, 2.5e-8), (10, 2.5e-8)])
        self.assertEqual([(row["mesh_um"], row["maxDt_s"]) for row in new],
                         [(5, 2.5e-8), (5, 5e-8), (5, 1.25e-8)])
        self.assertEqual(len({(row["mesh_um"], row["maxDt_s"]) for row in all_cases}), 5)

    def test_audits_actual_coarse_bytes_contours_inputs_and_final_energy(self):
        reused = continuation._audit_coarse_rows(
            self.protocol, self.scenario, self.specs, self.coarse,
            continuation.COARSE_FIELD_DIRECTORY)
        self.assertEqual([row["mesh_um"] for row in reused], [20, 10])
        self.assertEqual([row["executionOrigin"]["kind"] for row in reused],
                         ["reused-coarse-observation-check"] * 2)
        self.assertEqual([row["executionOrigin"]["reconstructedInputs"]["provenance"]
                          for row in reused], [
            "Reconstructed by validate() from the frozen scenario and current fingerprint-pinned source; not captured at the coarse run."
        ] * 2)
        self.assertEqual([row["fieldArtifact"]["steps"] for row in reused], [10_000, 10_000])
        self.assertEqual([row["steps"] for row in reused], [14_000, 14_000])
        self.assertTrue(all(row["energyBalance"]["relativeError"] <= .01 for row in reused))

    def test_changed_resolved_input_identity_rejects_coarse_reuse(self):
        changed = copy.deepcopy(self.coarse)
        changed["rows"][0]["provenance"]["inputHash"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "resolved input|input identity"):
            continuation._audit_coarse_rows(
                self.protocol, self.scenario, self.specs, changed,
                continuation.COARSE_FIELD_DIRECTORY)

    def test_contour_is_recomputed_from_the_selected_state_artifact(self):
        changed = copy.deepcopy(self.coarse)
        changed["rows"][1]["fixedScanEndObservation"]["depth_um"] += 1.0
        with self.assertRaisesRegex(ValueError, "Recomputed coarse contour differs"):
            continuation._audit_coarse_rows(
                self.protocol, self.scenario, self.specs, changed,
                continuation.COARSE_FIELD_DIRECTORY)

    def test_missing_or_failed_coarse_case_cannot_be_replaced(self):
        changed = copy.deepcopy(self.coarse)
        changed["rows"].pop()
        with self.assertRaisesRegex(ValueError, "exactly the two frozen rows"):
            continuation._audit_coarse_rows(
                self.protocol, self.scenario, self.specs, changed,
                continuation.COARSE_FIELD_DIRECTORY)
        changed = copy.deepcopy(self.coarse)
        changed["rows"][0]["status"] = "failed"
        with self.assertRaisesRegex(ValueError, "absent or failed"):
            continuation._audit_coarse_rows(
                self.protocol, self.scenario, self.specs, changed,
                continuation.COARSE_FIELD_DIRECTORY)

    def test_oversized_uncompressed_declaration_is_rejected_before_numpy_decoder(self):
        row = copy.deepcopy(self.coarse["rows"][0])
        row["fieldArtifact"]["uncompressedBytes"] = self.protocol["maxUncompressedFieldBytes"] + 1
        path = continuation.COARSE_FIELD_DIRECTORY / row["fieldArtifact"]["path"]
        cells = row["cells"]
        shapes = {"coordinates_m": (cells, 3), "temperature_K": (cells,),
                  "enthalpy_J_m3": (cells,), "density_kg_m3": (cells,),
                  "accepted_dt_s": (row["fieldArtifact"]["steps"],)}
        with mock.patch.object(continuation.np, "load",
                               side_effect=AssertionError("decoder reached before byte-bound rejection")):
            with self.assertRaisesRegex(ValueError, "uncompressed byte count"):
                continuation._load_npz(
                    path, shapes, self.protocol["maxUncompressedFieldBytes"],
                    row["fieldArtifact"]["uncompressedBytes"],
                    row["fieldArtifact"]["sha256"], row["fieldArtifact"]["byteSize"])

    def test_existing_continuation_partial_blocks_preflight_retry(self):
        class FakePath:
            def __init__(self, exists):
                self.present = exists

            def exists(self):
                return self.present

        with self.assertRaisesRegex(FileExistsError, "never replace a failed attempt"):
            continuation._reject_existing_attempt(
                FakePath(False), FakePath(True), FakePath(False))

    def test_preflight_checks_continuation_paths_not_original_protocol_paths(self):
        context = list(original.preflight())
        context[6:9] = [Path("continuation-output.json"),
                         Path("continuation-output.partial.json"), Path("continuation-fields")]
        with (mock.patch.object(continuation.original, "preflight", return_value=tuple(context)),
              mock.patch.object(continuation, "_reject_existing_attempt",
                                side_effect=FileExistsError("sentinel")) as check_paths):
            with self.assertRaisesRegex(FileExistsError, "sentinel"):
                continuation.preflight()
        check_paths.assert_called_once_with(
            continuation.OUTPUT_PATH,
            continuation.OUTPUT_PATH.with_name(continuation.OUTPUT_PATH.stem + ".partial.json"),
            continuation.FIELD_DIRECTORY)

    def test_pre_solver_gate_failure_retains_failed_and_not_started_rows(self):
        context = list(continuation.preflight())
        context[6] = Path("continuation-test-output.json")
        context[7] = Path("continuation-test-output.partial.json")
        context[8] = Path("continuation-test-fields")
        writes = []
        with (mock.patch.object(continuation, "preflight", return_value=tuple(context)),
              mock.patch.object(continuation.subprocess, "run",
                                return_value=SimpleNamespace(stdout="HEAD")),
              mock.patch.object(continuation, "_write_json",
                                side_effect=lambda path, value: writes.append((path, copy.deepcopy(value)))),
              mock.patch.object(Path, "mkdir"),
              mock.patch.object(Path, "exists", return_value=False),
              mock.patch.object(continuation, "_assert_frozen_sources",
                                side_effect=ValueError("source changed")),
              mock.patch.object(continuation.original, "run",
                                side_effect=AssertionError("solver must not run"))):
            result = continuation.execute()
        self.assertEqual(result["status"], "failed")
        rows = result["reusedRows"] + result["newRows"]
        self.assertEqual([row["executionOrigin"]["caseOrdinal"] for row in rows], [1, 2, 3, 4, 5])
        self.assertEqual([row["status"] for row in result["newRows"]],
                         ["failed", "not-run", "not-run"])
        self.assertFalse(result["newRows"][0]["executionOrigin"]["solverInvoked"])
        self.assertEqual(result["newRows"][0]["executionOrigin"]["attemptCount"], 1)
        self.assertEqual(len(writes), 6)

    def test_reuse_addendum_records_wrapper_and_reconstructed_snapshots(self):
        reused = continuation._audit_coarse_rows(
            self.protocol, self.scenario, self.specs, self.coarse,
            continuation.COARSE_FIELD_DIRECTORY)
        evidence = continuation._addendum_evidence(
            self.protocol, self.scenario, reused, "a" * 64)
        self.assertEqual(evidence["continuationWrapper"]["sha256"], "a" * 64)
        self.assertEqual(evidence["continuationWrapper"]["reportPath"],
                         "docs/LPBF_P4_FIXED_SCAN_END_CONTINUATION_2026-09-27.json")
        self.assertEqual(evidence["continuationWrapper"]["fieldDirectory"],
                         "docs/LPBF_P4_FIXED_SCAN_END_CONTINUATION_FIELDS_2026-09-27")
        self.assertTrue(evidence["change"]["beforeFineExecution"])
        self.assertFalse(evidence["change"]["thresholdsChanged"])
        self.assertFalse(evidence["change"]["failedRowsReplaced"])
        self.assertEqual([row["caseOrdinal"] for row in evidence["coarseEvidence"]["rows"]], [1, 2])
        self.assertEqual([row["caseOrdinal"] for row in evidence["newCases"]], [3, 4, 5])
        self.assertTrue(all(len(row["resolvedInputHash"]) == 64
                            and "settings" in row["resolvedInputs"]
                            and "material" in row["resolvedInputs"]
                            for row in evidence["newCases"]))
        self.assertTrue(all("settings" in row["reconstructedInputs"]
                            and "material" in row["reconstructedInputs"]
                            for row in evidence["coarseEvidence"]["rows"]))

    def test_failed_attempt_records_no_retry_and_solver_invocation_state(self):
        spec = {"axes": ["mesh", "time"], "mesh_um": 5, "maxDt_s": 2.5e-8}
        before_launch = continuation._failed_row(spec, ValueError("gate failed"), 3, False)
        after_launch = continuation._failed_row(spec, RuntimeError("solver failed"), 3, True)
        self.assertEqual(before_launch["executionOrigin"]["attemptCount"], 1)
        self.assertFalse(before_launch["executionOrigin"]["solverInvoked"])
        self.assertTrue(after_launch["executionOrigin"]["solverInvoked"])


if __name__ == "__main__":
    unittest.main()
