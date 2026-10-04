"""fx-icme (backlog lane 9, audit D5): the ICME pipeline is an illustrative estimator.

Oracles are analytic (Hollomon/Considere algebra, units) or structural (what the output
claims); none of them reads a golden file. Before the fix the default run returned
UTS == Rp0.2 == 1191.8 MPa, K_Ic == 740.6 MPa*sqrt(m), a_c == 247.47 mm and the verdict
'STRUCTURALLY SAFE (Passed Yield & Creep Criteria)' although no creep check exists.
"""

import json
import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import icme_multiscale_pipeline_solver as icme  # noqa: E402

SOURCE = (HERE / "icme_multiscale_pipeline_solver.py").read_text(encoding="utf-8")


def _run(payload=None):
    out = icme.solve_multiscale_pipeline(dict(payload or {}))
    out.pop("computeTimeMs", None)
    return out


def _mech(out):
    return out["scale3_continuumPlasticity"]["mechanicalProperties"]


class HollomonConsidereIdentityTest(unittest.TestCase):
    """Why UTS is unavailable: the model's own K and n make the Considere UTS equal Rp0.2."""

    def test_considere_uts_of_the_models_own_k_and_n_is_the_yield_strength(self):
        # Hollomon sigma = K*eps^n; necking at true strain n; engineering UTS = K*(n/e)^n.
        for payload in ({}, {"baseMetal": "Fe", "composition_wt": {"C": 0.4, "Cr": 1.0}},
                        {"baseMetal": "Ti", "composition_wt": {"Al": 6.0, "V": 4.0}},
                        {"baseMetal": "Al", "composition_wt": {"Mg": 2.5, "Zn": 5.6}}):
            with self.subTest(payload=payload):
                m = _mech(_run(payload))
                n, k, ys = m["hollomon_n"], m["hollomon_K_MPa"], m["yieldStrength_Rp02_MPa"]
                considere_uts = k * (n / math.e) ** n
                # n and K are printed rounded to 3 and 1 decimals: 5e-3 relative covers both.
                self.assertAlmostEqual(considere_uts / ys, 1.0, delta=5e-3)

    def test_uts_is_not_reported_as_the_yield_strength(self):
        for payload in ({}, {"baseMetal": "Ti", "composition_wt": {"Al": 6.0, "V": 4.0}}):
            with self.subTest(payload=payload):
                m = _mech(_run(payload))
                self.assertIsNone(m["ultimateTensileStrength_UTS_MPa"])
                self.assertTrue(m["ultimateTensileStrength_UTS_status"].startswith("unavailable:"))
                self.assertIn("Considere", m["ultimateTensileStrength_UTS_status"])
                self.assertNotEqual(m["ultimateTensileStrength_UTS_MPa"], m["yieldStrength_Rp02_MPa"])


class UnavailableFractureToughnessTest(unittest.TestCase):
    def test_k1c_and_everything_derived_from_it_is_unavailable(self):
        out = _run()
        m = _mech(out)
        self.assertIsNone(m["fractureToughness_K1c_MPa_sqrt_m"])
        self.assertTrue(m["fractureToughness_K1c_status"].startswith("unavailable:"))
        lefm = out["scale4_macroComponentFEA"]["lefmDamageTolerance"]
        self.assertIsNone(lefm["criticalFlawSize_ac_mm"])
        self.assertIsNone(lefm["plasticZoneRadius_rp_mm"])
        self.assertTrue(lefm["inspectionNDICapability"].startswith("Unavailable"))
        self.assertTrue(lefm["status"].startswith("unavailable:"))

    def test_old_k1c_formula_is_gone(self):
        # sqrt(2/3 * E[MPa] * sigma_y[MPa] * eps_f * n^2) is sqrt(MPa^2) = MPa, not MPa*sqrt(m):
        # it cannot be a fracture toughness, so it must not be in the solver any more.
        self.assertNotIn("(2.0 / 3.0) * (youngs_modulus_E_GPa * 1000.0) * yield_strength_MPa", SOURCE)

    def test_no_invented_k1c_floor_remains(self):
        self.assertNotIn("max(15.0, (2.0 / 3.0)", SOURCE)


class HonestVerdictTest(unittest.TestCase):
    def test_verdict_does_not_claim_a_creep_check(self):
        for payload in ({}, {"serviceTemp_C": 1000.0}, {"baseMetal": "Al", "composition_wt": {"Mg": 1.0}}):
            with self.subTest(payload=payload):
                out = _run(payload)
                verdict = out["scale4_macroComponentFEA"]["structuralVerdict"]
                self.assertNotIn("Creep Criteria", verdict)
                self.assertNotIn("STRUCTURALLY SAFE", verdict)
                self.assertIn("yield", verdict.lower())
                self.assertTrue("no creep" in verdict or "yield-only check" in verdict)
                basis = out["scale4_macroComponentFEA"]["structuralVerdictBasis"]
                self.assertIn("No creep", basis)

    def test_pass_and_fail_wording_follow_the_unchanged_decision(self):
        passed = _run()["scale4_macroComponentFEA"]
        self.assertGreaterEqual(passed["actualSafetyFactor"], passed["requiredSafetyFactor"])
        self.assertTrue(passed["structuralVerdict"].startswith("YIELD CHECK PASSED"))
        failed = _run({"baseMetal": "Al", "composition_wt": {"Mg": 1.0}})["scale4_macroComponentFEA"]
        self.assertLess(failed["actualSafetyFactor"], failed["requiredSafetyFactor"])
        self.assertTrue(failed["structuralVerdict"].startswith("WARNING: INSUFFICIENT YIELD SAFETY MARGIN"))

    def test_service_temperature_changes_nothing(self):
        # The note says serviceTemp_C has no effect; this pins that statement.
        self.assertEqual(json.dumps(_run({"serviceTemp_C": 25.0})), json.dumps(_run({"serviceTemp_C": 1000.0})))


class ModelStatusTest(unittest.TestCase):
    def test_model_status_and_plain_language_note(self):
        out = _run()
        self.assertEqual(out["modelStatus"], "illustrative")
        note = out["modelStatusNote"]
        for needle in ("closed-form", "tabulated constants", "no DFT is run", "no thermodynamic calculation",
                       "not a finite-element analysis", "room-temperature only", "unavailable"):
            self.assertIn(needle, note)
        self.assertEqual(len(out["modelParts"]), 6)
        self.assertNotIn("HPC Pipeline", out["engine"])
        self.assertIn("illustrative", out["engine"])

    def test_cards_are_not_called_calibrated(self):
        self.assertNotIn("Calibrated Card", SOURCE)
        cards = _run()["caeExportCards"]
        for name, card in cards.items():
            with self.subTest(card=name):
                self.assertNotIn("alibrated Card", card)
                self.assertIn("ILLUSTRATIVE", card)
                self.assertIn("uncalibrated", card)

    def test_output_is_strict_json(self):
        json.dumps(_run(), allow_nan=False)


if __name__ == "__main__":
    unittest.main()
