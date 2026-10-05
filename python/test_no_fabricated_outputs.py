"""Reject missing observations and untrained inference; use real input-dependent computation.

The battery/corrosion ingestion and uploaded-EIS cases were deleted on 2026-10-04 with
battery_corrosion_python_ingest.py and the uploaded-EIS solver action (no UI consumer)."""
import copy
import threading
import unittest
from unittest.mock import patch
from lpbf_simulation import run as actual_run
from orchestrator import run_orchestrator


class EvidenceIntegrity(unittest.TestCase):
    def test_orchestrator_cancels_during_actual_solver_progress(self):
        event = threading.Event()
        checkpoints = []
        def run_with_cancellation(payload, report):
            def intercept(progress, message):
                checkpoints.append(message)
                event.set()
                report(progress, message)
            return actual_run(payload, report=intercept)
        # Wrap only progress delivery, retaining the actual thermal solver.
        with patch('orchestrator.run', side_effect=run_with_cancellation):
            result = run_orchestrator(dict(mode='standard', backend='reference',
                power_W=40, mesh_um=40, trackLength_um=200, cooling_s=.0001, dwell_s=0),
                cancel_event=event)
        self.assertTrue(checkpoints)
        self.assertEqual(result['status'], 'cancelled')
        self.assertNotIn('result', result)

    def test_orchestrator_preserves_input_and_returns_actual_solver_result(self):
        case = dict(mode="standard", backend="reference", power_W=40,
                    mesh_um=40, trackLength_um=200, cooling_s=.0001, dwell_s=0)
        original = copy.deepcopy(case)
        first = run_orchestrator(case)
        second = run_orchestrator({**case, "power_W": 30})
        self.assertEqual(case, original)
        self.assertEqual(first["status"], "completed")
        self.assertEqual(first["result"]["settings"]["power_W"], 40)
        self.assertNotEqual(first["result"]["provenance"]["inputHash"], second["result"]["provenance"]["inputHash"])
        self.assertNotEqual(first["result"]["energyBalance"]["input_J"], second["result"]["energyBalance"]["input_J"])
        self.assertFalse(first["result"]["productionReady"])

    def test_orchestrator_reports_failure_and_cancellation_without_result(self):
        failed = run_orchestrator({"power_W": -1})
        self.assertEqual(failed["status"], "failed")
        self.assertNotIn("result", failed)
        event = threading.Event()
        event.set()
        cancelled = run_orchestrator({"power_W": 40}, cancel_event=event)
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertNotIn("result", cancelled)


if __name__ == "__main__":
    unittest.main()
