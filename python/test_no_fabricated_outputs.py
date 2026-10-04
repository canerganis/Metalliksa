"""Reject missing observations and untrained inference; use real input-dependent computation."""
import copy
import math
import threading
import unittest
from unittest.mock import patch
from lpbf_simulation import run as actual_run
from battery_corrosion_python_ingest import (
    analyze_battery_data, analyze_corrosion_tafel, analyze_eis_data, analyze_ocp_data,
)
from battery_corrosion_eis_solver import analyze_uploaded_eis_dataset
from orchestrator import run_orchestrator


class EvidenceIntegrity(unittest.TestCase):
    def test_battery_preserves_observed_curves_and_derivative(self):
        result = analyze_battery_data(dict(nominalCapacityAh=1, cycles=[1, 2],
            retention_pct=[100, 95], ce_pct=[99, 98],
            voltage_V=[3, 3.2, 3.4, 3.6], capacity_mAh=[0, 100, 200, 300]))
        self.assertEqual(result['gcdCurve'][-1], {'voltage': 3.6, 'capacity_mAh': 300})
        self.assertEqual([p['dqdv'] for p in result['dqdvSpectrogram']], [500, 500])
        self.assertEqual(result['summary']['finalRetentionPct'], 95)
        self.assertEqual(result['summary']['avgCoulombicEfficiencyPct'], 98.5)

    def test_tafel_analytic_intersection_and_unit_equivalence(self):
        # Two exact asymptotic branches: Ecorr=-0.2 V, icorr=10 uA/cm2,
        # beta_a=0.1 V/dec and beta_c=0.2 V/dec; area=2 cm2.
        potentials = [-.6, -.4, -.2, 0, .2]
        magnitudes_uA = [2000, 200, 20, 2000, 200000]
        summaries = []
        for field, values in (
            ('current_A', [v * 1e-6 for v in magnitudes_uA]),
            ('current_mA', [v * 1e-3 for v in magnitudes_uA]),
            ('current_uA', magnitudes_uA),
            ('log_i', [math.log10(v * 1e-6) for v in magnitudes_uA]),
        ):
            data = dict(potential_V=potentials, electrodeArea_cm2=2,
                        density_g_cm3=8, equivalentWeight=28)
            data[field] = values
            summary = analyze_corrosion_tafel(data)['summary']
            self.assertAlmostEqual(summary['eCorr_V'], -.2, places=4)
            self.assertAlmostEqual(summary['iCorr_uA_cm2'], 10, places=4)
            self.assertEqual(summary['betaA_V_dec'], .1)
            self.assertEqual(summary['betaC_V_dec'], .2)
            self.assertAlmostEqual(summary['cr_mm_year'], .11445, places=5)
            self.assertAlmostEqual(summary['rp_ohm_cm2'], 2894.8, delta=.1)
            summaries.append(summary)
        self.assertTrue(all(summary == summaries[0] for summary in summaries))

    def test_tafel_rejects_ambiguous_units_and_unresolved_branches(self):
        base = dict(potential_V=[-.6, -.4, -.2, 0, .2],
                    electrodeArea_cm2=2, density_g_cm3=8, equivalentWeight=28)
        for columns in (
            dict(current_A=[1]*5, current_mA=[1]*5),
            dict(current_uA=[0]*5), dict(current_uA=[1, 2, 3, 4, 5]),
            dict(current_uA=[1]*5),
        ):
            with self.subTest(columns=columns), self.assertRaises(ValueError):
                analyze_corrosion_tafel({**base, **columns})

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

    def test_ingestion_never_manufactures_missing_observations(self):
        for analyze in (analyze_battery_data, analyze_corrosion_tafel, analyze_eis_data, analyze_ocp_data):
            with self.subTest(analyze=analyze.__name__), self.assertRaises(ValueError):
                analyze({})

    def test_ingestion_rejects_misaligned_and_nonfinite_arrays(self):
        for payload in (
            {"frequencies": [1, 2], "zReal": [2], "zImag": [-1, -1]},
            {"frequencies": [1, float("nan")], "zReal": [2, 3], "zImag": [-1, -1]},
        ):
            with self.assertRaises(ValueError):
                analyze_eis_data(payload)

    def test_ingestion_has_no_user_script_execution(self):
        # The exec-script HTTP route was removed; the module must not execute caller code.
        import json
        import subprocess
        import sys
        from pathlib import Path
        import battery_corrosion_python_ingest as ingest
        self.assertFalse(hasattr(ingest, "execute_user_python_script"))
        script = Path(ingest.__file__).resolve()
        payload = json.dumps({"action": "execute_python_script", "scriptCode": "print('ran')"})
        done = subprocess.run([sys.executable, "-B", str(script)], input=payload, capture_output=True,
                              text=True, cwd=script.parent, timeout=60)
        out = json.loads(done.stdout)  # JSON only: the script's print() never ran
        self.assertFalse(out["success"])
        self.assertIn("Unknown action", out["error"])

    def test_ocp_preserves_actual_samples(self):
        result = analyze_ocp_data({"time_s": [0, 60, 120, 180, 240, 300],
                                   "potential_V": [-.2, -.19, -.18, -.17, -.16, -.15]})
        self.assertEqual(len(result["ocpPlot"]), 6)
        self.assertEqual(result["ocpPlot"][-1]["potential_V"], -.15)

    def test_eis_consistency_residuals_depend_on_observations_not_just_frequency(self):
        frequencies = [10 ** (4 - i / 4) for i in range(25)]
        spectrum = [2 + 8 / (1 + 1j * 2 * math.pi * f * .002) for f in frequencies]
        real, imag = [z.real for z in spectrum], [z.imag for z in spectrum]
        first = analyze_uploaded_eis_dataset(frequencies, real, imag)["kramersKronigValidation"]
        corrupted = real[:]
        corrupted[12] += 100
        second = analyze_uploaded_eis_dataset(frequencies, corrupted, imag)["kramersKronigValidation"]
        self.assertNotEqual(first["residuals"], second["residuals"])
        self.assertGreater(second["pseudoChiSq"], first["pseudoChiSq"])
        self.assertNotEqual(first["grade"], "PASSED")

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
