#!/usr/bin/env python3
"""lpbf_solidification_segregation: Scheil identities, D97 reproduction, provenance and status rules.

Self-contained (stdlib only, no network, no TDB). Run: python -B -m unittest test_lpbf_solidification_segregation
"""
import copy
import json
import math
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lpbf_solidification_segregation as seg  # noqa: E402

NI = seg.CONSTANTS["ni-base"]


def _micro(status, **extra):
    block = {"status": status, "G_K_m": 2.0e7, "R_m_s": 0.4, "coolingRate_K_s": 8.0e6,
             "morphology": "Cellular (Hunt G/R screening)", "PDAS_um": 0.55, "SDAS_um": None}
    block.update(extra)
    return block


class ScheilIdentities(unittest.TestCase):
    def test_liquid_composition_at_fs0_equals_c0(self):
        for c0 in (0.5, 4.75, 5.125, 12.0):
            self.assertAlmostEqual(seg.scheil_liquid_composition(c0, 0.46, 0.0), c0, places=12)

    def test_liquid_composition_rises_with_fs(self):
        prev = 0.0
        for fs in (0.0, 0.3, 0.6, 0.9, 0.95, 0.99):
            cl = seg.scheil_liquid_composition(5.0, 0.46, fs)
            self.assertGreater(cl, prev)
            prev = cl

    def test_eutectic_fraction_matches_closed_form_and_inverts(self):
        f = seg.scheil_eutectic_fraction(5.0, 23.1, 0.46)
        self.assertAlmostEqual(f, (23.1 / 5.0) ** (1.0 / (0.46 - 1.0)), places=14)
        # the Scheil liquid at fs = 1 - f_e is exactly the eutectic composition
        self.assertAlmostEqual(seg.scheil_liquid_composition(5.0, 0.46, 1.0 - f), 23.1, places=9)

    def test_eutectic_fraction_monotone_in_c0(self):
        values = [seg.scheil_eutectic_fraction(c0, 23.1, 0.46) for c0 in (1.0, 2.0, 4.75, 5.125, 5.5, 10.0, 20.0)]
        self.assertEqual(values, sorted(values))
        self.assertTrue(all(b > a for a, b in zip(values, values[1:])))

    def test_eutectic_fraction_is_one_at_or_above_ce(self):
        self.assertEqual(seg.scheil_eutectic_fraction(23.1, 23.1, 0.46), 1.0)
        self.assertEqual(seg.scheil_eutectic_fraction(30.0, 23.1, 0.46), 1.0)

    def test_k_to_one_and_invalid_k_are_guarded(self):
        for k in (1.0, 1.0 + 1e-12, 1.2, 0.0, -0.1, float("nan"), float("inf")):
            with self.assertRaises(seg.SegregationModelError, msg=k):
                seg.scheil_eutectic_fraction(5.0, 23.1, k)
            with self.assertRaises(seg.SegregationModelError, msg=k):
                seg.scheil_liquid_composition(5.0, k, 0.5)
        # approaching 1 from below stays finite and the eutectic fraction goes to 0 (no segregation)
        self.assertLess(seg.scheil_eutectic_fraction(5.0, 23.1, 0.999), 1e-100)

    def test_non_positive_inputs_refused(self):
        for bad in (0.0, -1.0, float("nan")):
            with self.assertRaises(seg.SegregationModelError):
                seg.scheil_eutectic_fraction(bad, 23.1, 0.46)
        with self.assertRaises(seg.SegregationModelError):
            seg.scheil_liquid_composition(5.0, 0.46, 1.0)


class PseudoTernaryD97(unittest.TestCase):
    def test_reproduces_d97_alloy_7_5_example(self):
        # D97 'Eutectic-Type Solidification': Alloy 7.5 (Table 1: 4.92 Nb, 0.081 C, Ni base): primary
        # solidification until about 0.10 liquid with 0.24 wt% C, then 0.08 gamma/NbC + 0.02 gamma/Laves.
        r = seg.pseudo_ternary_path(4.92, 0.081, NI)
        self.assertEqual(r["status"], "computed")
        self.assertAlmostEqual(r["liquidAtPrimaryEnd"]["C_wt"], 0.24, delta=0.01)
        self.assertAlmostEqual(r["fLaves"], 0.02, delta=0.005)
        # This implementation gives 0.087 liquid at the end of primary solidification (Eq. 1 at the Eq. 6
        # intersection), against "0.10" in the D97 text; stated, not tuned.
        self.assertAlmostEqual(r["fEutecticTotal"], 0.087, delta=0.002)
        self.assertAlmostEqual(r["fNbC"], 0.065, delta=0.003)
        self.assertEqual(r["terminatedBy"], "laves-point")

    def test_d97_high_c_low_nb_alloys_form_no_laves(self):
        # D97: Ni base alloys 2, 3.5 and 4 (high C / low Nb) showed no Laves phase.
        for nb, c in ((1.95, 0.132), (1.94, 0.075), (1.91, 0.155)):
            r = seg.pseudo_ternary_path(nb, c, NI)
            self.assertEqual(r["fLaves"], 0.0, (nb, c, r))
            self.assertGreater(r["fNbC"], 0.0)
            self.assertEqual(r["terminatedBy"], "liquid-exhausted-on-NbC-line")

    def test_mass_bookkeeping(self):
        r = seg.pseudo_ternary_path(5.125, 0.08, NI)
        self.assertAlmostEqual(r["fNbC"] + r["fLaves"], r["fEutecticTotal"], places=12)
        self.assertLessEqual(r["fEutecticTotal"], 1.0)

    def test_step_convergence(self):
        coarse = seg.pseudo_ternary_path(5.125, 0.08, NI)
        fine = seg.pseudo_ternary_path(5.125, 0.08, NI, step_wt_nb=seg.EUTECTIC_STEP_WT_NB / 10.0)
        self.assertLess(abs(coarse["fLaves"] - fine["fLaves"]), 1e-3)

    def test_binary_is_upper_bound_on_laves_over_carbon(self):
        f_bin = seg.scheil_eutectic_fraction(5.125, NI["C_Nb_laves"]["value"], NI["k_gamma_Nb"]["value"])
        prev = f_bin
        for c in (0.001, 0.005, 0.01, 0.02, 0.04, 0.06, 0.08, 0.12, 0.17):
            r = seg.pseudo_ternary_path(5.125, c, NI)
            self.assertLessEqual(r["fLaves"], prev + 1e-12, c)
            prev = r["fLaves"]

    def test_low_carbon_reaches_laves_point_before_nbc_line(self):
        r = seg.pseudo_ternary_path(1.82, 0.010, NI)  # D97 alloy 3
        self.assertEqual(r["fNbC"], 0.0)
        self.assertAlmostEqual(r["fLaves"], seg.scheil_eutectic_fraction(1.82, 23.1, 0.46), places=12)

    def test_primary_nbc_field_is_outside_model(self):
        self.assertEqual(seg.pseudo_ternary_path(5.0, 1.0, NI)["status"], "outside-model")


class Provenance(unittest.TestCase):
    def test_every_constant_has_source_and_locator(self):
        for set_id, cset in seg.CONSTANTS.items():
            for key, entry in cset.items():
                with self.subTest(set_id=set_id, key=key):
                    self.assertIn(entry["source"], seg.SOURCES)
                    self.assertTrue(entry["locator"].strip())
                    self.assertIn("unit", entry)
                    if entry["verified"]:
                        self.assertTrue(seg.SOURCES[entry["source"]]["read"])
                        self.assertIsInstance(entry["value"], (int, float))
                    else:
                        self.assertIsNone(entry["value"])

    def test_composition_limits_have_a_read_source(self):
        for alloy_id, spec in seg.COMPOSITION_LIMITS.items():
            self.assertTrue(seg.SOURCES[spec["source"]]["read"], alloy_id)
            self.assertTrue(spec["locator"])

    def test_label_never_promotes_evidence(self):
        blocks = [seg.segregation_estimate(a, _micro("available")) for a in ("in718", "in625", "ss316l")]
        texts = [seg.EVIDENCE_LABEL] + [b.get("evidenceLabel") or "" for b in blocks]
        for text in texts:
            for word in ("validated", "calibrated", "measured"):
                self.assertNotIn(word, text.lower(), text)
        self.assertTrue(seg.EVIDENCE_LABEL.startswith("Literature estimate (screening)"))


class AlloyStatus(unittest.TestCase):
    def test_in718_available_with_band_and_validity(self):
        b = seg.segregation_estimate("in718", _micro("available"))
        self.assertEqual(b["status"], "available")
        self.assertEqual(b["schema"], seg.SCHEMA)
        self.assertEqual([p["label"] for p in b["band"]], ["min", "nominal", "max"])
        self.assertEqual([p["Nb_wt"] for p in b["band"]], [4.75, 5.125, 5.5])
        lav = [p["binaryUpperBound"]["fLaves"] for p in b["band"]]
        self.assertEqual(lav, sorted(lav))
        for p in b["band"]:
            self.assertLessEqual(p["pseudoTernaryAtCmax"]["fLaves"], p["binaryUpperBound"]["fLaves"])
        self.assertEqual(b["k_Nb"]["value"], 0.46)
        self.assertIn("Table", b["k_Nb"]["locator"])
        self.assertEqual(b["riskClass"], "eutectic Laves expected (Scheil)")
        v = b["validity"]
        self.assertIs(v["outsideSourceRegime"], True)
        self.assertIs(v["outsideSourceComposition"], True)
        self.assertTrue(any(r.startswith("Mo") for r in v["outsideSourceCompositionReasons"]))
        self.assertIn("upper bound", b["upperBoundNote"].lower())
        self.assertIn("back-diffusion", b["upperBoundNote"])
        seg_ratio = b["segregation"]
        self.assertEqual(seg_ratio["coreRatioToNominal"], 0.46)
        self.assertTrue(all(r["ratioToNominal"] > 1.0 for r in seg_ratio["interdendritic"]))
        json.dumps(b, allow_nan=False)

    def test_in625_unavailable_unverified(self):
        b = seg.segregation_estimate("in625", _micro("available"))
        self.assertEqual(b["status"], "unavailable")
        self.assertIn(seg.UNVERIFIED_REASON, b["reason"])
        self.assertNotIn("band", b)

    def test_unverified_constant_gives_unavailable(self):
        patched = copy.deepcopy(seg.CONSTANTS)
        patched["ni-base"]["k_gamma_Nb"] = {**patched["ni-base"]["k_gamma_Nb"], "verified": False}
        with mock.patch.object(seg, "CONSTANTS", patched):
            b = seg.segregation_estimate("in718", _micro("available"))
        self.assertEqual(b["status"], "unavailable")
        self.assertIn(seg.UNVERIFIED_REASON, b["reason"])
        self.assertNotIn("band", b)

    def test_non_nb_alloys_not_applicable(self):
        for alloy in ("ss316l", "ti6al4v", "alsi10mg", "unknown", "", None):
            b = seg.segregation_estimate(alloy, _micro("available"))
            self.assertEqual(b["status"], "not-applicable", alloy)
            self.assertEqual(b["reason"], seg.NOT_APPLICABLE_REASON)
            self.assertNotIn("band", b)


class ProcessCoupling(unittest.TestCase):
    def test_available_copies_g_r_without_recomputing(self):
        m = _micro("available")
        before = copy.deepcopy(m)
        pc = seg.segregation_estimate("in718", m)["processCoupling"]
        self.assertEqual(m, before)  # input not mutated
        self.assertEqual(pc["status"], "available")
        for key in ("G_K_m", "R_m_s", "morphology", "PDAS_um", "coolingRate_K_s"):
            self.assertEqual(pc[key], m[key])
        self.assertIs(pc["usedInCalculation"], False)

    def test_composition_result_independent_of_microstructure(self):
        a = seg.segregation_estimate("in718", _micro("available"))
        b = seg.segregation_estimate("in718", _micro("available", G_K_m=1.0e5, R_m_s=1.0))
        a.pop("processCoupling"), b.pop("processCoupling")
        self.assertEqual(a, b)

    def test_degenerate_floor_and_unavailable_give_unavailable_coupling(self):
        for status in ("degenerate-floor", "unavailable", "weird", None):
            m = _micro(status, reason="R and the cooling rate sit on the solver clamp floors")
            b = seg.segregation_estimate("in718", m)
            self.assertEqual(b["status"], "available")  # composition-only result still given
            pc = b["processCoupling"]
            self.assertEqual(pc["status"], "unavailable", status)
            self.assertTrue(pc["reason"])
            for key in ("G_K_m", "R_m_s", "morphology", "PDAS_um"):
                self.assertIsNone(pc[key])
        self.assertEqual(seg.segregation_estimate("in718", None)["processCoupling"]["status"], "unavailable")

    def test_screening_fallback_passes_through_with_reason(self):
        pc = seg.segregation_estimate("in718", _micro("screening-fallback", reason="tail-length heuristic"))[
            "processCoupling"]
        self.assertEqual(pc["status"], "screening-fallback")
        self.assertEqual(pc["reason"], "tail-length heuristic")

    def test_no_invented_kinetic_constant(self):
        text = json.dumps(seg.segregation_estimate("in718", _micro("available"))).lower()
        for banned in ("v_d", "aziz", "diffusive speed"):
            self.assertNotIn(banned, text)


if __name__ == "__main__":
    unittest.main()
