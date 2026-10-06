"""Low-cost fail-before-solver tests for the fresh P4 v2 protocol gate."""

import hashlib
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

import run_lpbf_p4_accepted_dt_diagnostic_v2 as runner


SCENARIO = {"mode": "standard", "backend": "reference", "study": "none",
            "surfaceMode": "powder-layer", "powderGridPolicy": "layer-conforming"}
MATERIAL = {"materialId": "in718", "materialRevisionSha256": "a" * 64}


def _protocol(p, *, maximum_cells=2000):
    return {
        "requestedMaxDt_s": [0.5, 0.25, 0.125],
        "expectedResolvedInputSha256": hashlib.sha256(
            json.dumps(p, sort_keys=True, allow_nan=False).encode("utf-8")).hexdigest(),
        "expectedModelId": "stationary-enthalpy-conduction-layer-conforming-v1",
        "expectedActualBackend": "numpy-reference", "expectedSolverId": "enthalpy-fv-6",
        "expectedMaterialId": MATERIAL["materialId"],
        "expectedMaterialRevisionSha256": MATERIAL["materialRevisionSha256"],
        "resourceLimits": {"maximumCells": maximum_cells, "estimatedBytesPerCell": 768,
            "maximumEstimatedBytes": 2_000_000, "maximumStepsPerCase": 100,
            "maximumTotalCellSteps": 50_000},
    }


def _geometry(*_args):
    return {"nx": 10, "ny": 10, "nz": 10}


class P4FreshProtocolGate(unittest.TestCase):
    def test_preflight_estimates_cells_memory_and_total_cell_steps_without_solver(self):
        protocol = _protocol(SCENARIO)
        with patch.object(runner, "validate", return_value=(SCENARIO, MATERIAL)), \
             patch.object(runner, "calculate_mesh_domain", side_effect=_geometry), \
             patch.object(runner, "scan_segments", return_value=([], 1.0)):
            estimate = runner._resource_preflight(SCENARIO, protocol)
        self.assertEqual(estimate["cells"], 1000)
        self.assertEqual(estimate["estimatedBytes"], 768_000)
        self.assertEqual(estimate["lowerBoundTotalCellSteps"], 14_000)

    def test_unsafe_cell_limit_stops_orchestration_before_destination_or_solver(self):
        protocol = _protocol(SCENARIO, maximum_cells=999)
        with patch.object(runner, "_load_protocol", return_value=(protocol, SCENARIO, b"p", b"s")), \
             patch.object(runner, "validate", return_value=(SCENARIO, MATERIAL)), \
             patch.object(runner, "calculate_mesh_domain", side_effect=_geometry), \
             patch.object(runner, "scan_segments", return_value=([], 1.0)), \
             patch.object(runner, "_preflight_destinations", side_effect=AssertionError("destination stage reached")), \
             patch("lpbf_convergence_study.run", side_effect=AssertionError("solver must not run")) as solve:
            with self.assertRaisesRegex(ValueError, "resource preflight"):
                runner.run_protocol(Path("unused-protocol.json"))
        solve.assert_not_called()

    def test_identity_mismatch_stops_before_geometry_or_solver(self):
        protocol = _protocol(SCENARIO)
        wrong_material = {**MATERIAL, "materialRevisionSha256": "b" * 64}
        with patch.object(runner, "validate", return_value=(SCENARIO, wrong_material)), \
             patch.object(runner, "calculate_mesh_domain", side_effect=AssertionError("geometry stage reached")):
            with self.assertRaisesRegex(ValueError, "identity differs"):
                runner._resource_preflight(SCENARIO, protocol)

    def test_runtime_timestep_caps_stop_before_calling_next_step_limiter(self):
        calls = []

        def step_limiter(value):
            calls.append(value)
            return value, "state"

        counters = {"caseSteps": 0, "totalSteps": 0}
        guarded = runner._guarded_source_limiter(step_limiter, cells=100,
            max_steps_case=2, max_total_cell_steps=1000, counters=counters)
        self.assertEqual(guarded(1), (1, "state"))
        self.assertEqual(guarded(2), (2, "state"))
        with self.assertRaisesRegex(RuntimeError, "per-case timestep limit"):
            guarded(3)
        self.assertEqual(calls, [1, 2])
        self.assertEqual(counters, {"caseSteps": 2, "totalSteps": 2})

        total_limited = runner._guarded_source_limiter(step_limiter, cells=100,
            max_steps_case=10, max_total_cell_steps=200, counters=counters)
        with self.assertRaisesRegex(RuntimeError, "total cell-step limit"):
            total_limited(4)
        self.assertEqual(calls, [1, 2])

    def test_module_level_limiter_patch_is_installed_and_restored_on_error(self):
        self.assertTrue(callable(runner.lpbf_simulation.source_limited_step))
        original = runner.lpbf_simulation.source_limited_step
        counters = {"caseSteps": 0, "totalSteps": 0}
        with patch.object(runner.lpbf_simulation, "source_limited_step", return_value=("accepted",)) as fake:
            original = runner.lpbf_simulation.source_limited_step
            with self.assertRaisesRegex(RuntimeError, "simulated failure"):
                with runner._install_runtime_step_guard(cells=2, max_steps_case=2,
                        max_total_cell_steps=10, counters=counters):
                    installed = runner.lpbf_simulation.source_limited_step
                    self.assertIsNot(installed, original)
                    self.assertEqual(installed("input"), ("accepted",))
                    self.assertEqual(counters, {"caseSteps": 1, "totalSteps": 1})
                    raise RuntimeError("simulated failure")
            self.assertIs(runner.lpbf_simulation.source_limited_step, original)
            fake.assert_called_once_with("input")

    def test_repo_path_rejects_symlink_ancestor_before_resolution(self):
        root = Path(__file__).parent / ".tmp-p4-v2-symlink-test"
        root.mkdir(exist_ok=True)
        docs = root / "docs"
        docs.mkdir(exist_ok=True)
        original = Path.is_symlink

        def as_link(path):
            return path == docs or original(path)

        try:
            with patch.object(Path, "is_symlink", as_link):
                with self.assertRaisesRegex(ValueError, "contains a link"):
                    runner._repo_path(root, "docs/report.json", "output")
        finally:
            docs.rmdir()
            root.rmdir()

    def test_failed_partial_status_is_updated_without_masking_original_failure(self):
        root = Path(__file__).parent / ".tmp-p4-v2-failed-partial-test"
        root.mkdir(exist_ok=True)
        partial = root / "report.partial.json"
        partial.write_text(json.dumps({"stage": "running"}), encoding="utf-8")
        try:
            runner._mark_failed_partial(partial, {"stage": "running", "rows": []}, RuntimeError("bounded failure"))
            saved = json.loads(partial.read_text(encoding="utf-8"))
            self.assertEqual(saved["stage"], "failed")
            self.assertEqual(saved["status"], "failed")
            self.assertEqual(saved["integrityStatus"], "not-completed")
            self.assertEqual(saved["error"], "RuntimeError: bounded failure")
            self.assertFalse((root / "report.json").exists())
        finally:
            for path in root.iterdir():
                path.unlink()
            root.rmdir()

    def test_failed_partial_write_error_does_not_replace_original_exception(self):
        root = Path(__file__).parent / ".tmp-p4-v2-unwritable-partial-test"
        root.mkdir(exist_ok=True)
        partial = root / "report.partial.json"
        original_error = RuntimeError("solver failure remains primary")
        try:
            with patch.object(runner, "_replace_partial", side_effect=OSError("disk failure")):
                runner._mark_failed_partial(partial, {"stage": "running"}, original_error)
            self.assertEqual(str(original_error), "solver failure remains primary")
        finally:
            root.rmdir()

    def test_preexisting_output_partial_or_field_directory_is_refused(self):
        root = Path(__file__).parent / ".tmp-p4-v2-gate-tests"
        root.mkdir(exist_ok=True)
        cases = (
            ("docs/report.json",),
            ("docs/report.partial.json",),
            ("docs/fields",),
        )
        try:
            for (existing,) in cases:
                target = root / existing
                target.parent.mkdir(parents=True, exist_ok=True)
                if existing.endswith(".json"):
                    target.write_text("reserved", encoding="utf-8")
                else:
                    target.mkdir()
                protocol = {"output": "docs/report.json", "partial": "docs/report.partial.json",
                            "fieldDirectory": "docs/fields"}
                with self.subTest(existing=existing), patch.object(runner, "ROOT", root):
                    with self.assertRaises(FileExistsError):
                        runner._preflight_destinations(protocol)
                if target.is_dir():
                    target.rmdir()
                else:
                    target.unlink()
        finally:
            if root.exists():
                shutil.rmtree(root)


if __name__ == "__main__":
    unittest.main()
