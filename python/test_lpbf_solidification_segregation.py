#!/usr/bin/env python3
"""lpbf_solidification_segregation: Scheil identities, D97 reproduction, provenance and status rules.

Self-contained (stdlib only, no network, no TDB). Run: python -B -m unittest test_lpbf_solidification_segregation
"""
import copy
import hashlib
import json
import math
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lpbf_solidification_segregation as seg  # noqa: E402

NI = seg.CONSTANTS["ni-base-d97"]  # the 1997 conference constants: the D97 reproduction tests use them explicitly
NI_D98 = seg.CONSTANTS["ni-base"]  # the shipped IN718 set (D98 Table 2)


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


class D98Constants(unittest.TestCase):
    """The shipped IN718 constant sets are DuPont, Robino & Marder, Acta Mater 46 (1998) 4781, Table 2."""

    def test_table_2_values_and_provenance(self):
        ni, fe = seg.CONSTANTS["ni-base"], seg.CONSTANTS["fe-base"]
        expected_ni = {"k_gamma_Nb": 0.45, "k_gamma_C": 0.21, "a_wtC": 1.13, "b_wtC_per_wtNb": -0.047,
                       "C_Nb_laves": 23.1, "C_C_laves": 0.04, "C_NbC_Nb": 90.5, "C_NbC_C": 9.5}
        expected_fe = {"k_gamma_Nb": 0.25, "k_gamma_C": 0.21, "a_wtC": 1.37, "b_wtC_per_wtNb": -0.065,
                       "C_Nb_laves": 20.4, "C_C_laves": 0.04, "C_NbC_Nb": 90.5, "C_NbC_C": 9.5}
        for cset, expected in ((ni, expected_ni), (fe, expected_fe)):
            self.assertEqual({k: v["value"] for k, v in cset.items()}, expected)
            for entry in cset.values():
                self.assertEqual(entry["source"], "D98")
                self.assertIn("D98 Table 2", entry["locator"])
        self.assertIn("10.1016/S1359-6454(98)00123-2", seg.SOURCES["D98"]["citation"])
        # the D97 sets stay available, cited to D97, with the 1997 values
        self.assertEqual(seg.CONSTANTS["ni-base-d97"]["k_gamma_Nb"]["value"], 0.46)
        self.assertEqual(seg.CONSTANTS["fe-base-d97"]["a_wtC"]["value"], 1.24)
        self.assertTrue(all(e["source"] == "D97" for e in seg.CONSTANTS["ni-base-d97"].values()))

    def test_shipped_in718_numbers_are_the_d98_values(self):
        b = seg.segregation_estimate("in718", _micro("available"))
        self.assertEqual(b["source"], seg.SOURCES["D98"])
        self.assertEqual(b["k_Nb"]["value"], 0.45)
        binary = [p["binaryUpperBound"]["fGammaLavesConstituent"] for p in b["band"]]
        for got, want in zip(binary, (0.0564, 0.0647, 0.0736)):
            self.assertAlmostEqual(got, want, delta=5e-4)
        tern = [p["pseudoTernaryAtCmax"]["fGammaLavesConstituent"] for p in b["band"]]
        self.assertEqual(b["band"][0]["pseudoTernaryAtCmax"]["C_wt"], 0.08)
        for got, want in zip(tern, (0.0198, 0.0282, 0.0372)):
            self.assertAlmostEqual(got, want, delta=5e-4)

    def test_d98_class_ii_point_lies_near_the_regressed_line(self):
        # a + b * 23.1 = 0.0443 wt% C against the tabulated 0.04 (D97 constants: 0.056 against 0.03)
        c = seg.CONSTANTS["ni-base"]
        line = c["a_wtC"]["value"] + c["b_wtC_per_wtNb"]["value"] * c["C_Nb_laves"]["value"]
        self.assertAlmostEqual(line, 0.0443, delta=1e-4)
        self.assertLess(abs(line - c["C_C_laves"]["value"]), 0.005)


class PseudoTernaryD97(unittest.TestCase):
    def test_reproduces_d97_alloy_7_5_example(self):
        # D97 'Eutectic-Type Solidification': Alloy 7.5 (Table 1: 4.92 Nb, 0.081 C, Ni base): primary
        # solidification until about 0.10 liquid with 0.24 wt% C, then 0.08 gamma/NbC + 0.02 gamma/Laves.
        r = seg.pseudo_ternary_path(4.92, 0.081, NI)
        self.assertEqual(r["status"], "computed")
        self.assertAlmostEqual(r["liquidAtPrimaryEnd"]["C_wt"], 0.24, delta=0.01)
        self.assertAlmostEqual(r["fGammaLavesConstituent"], 0.02, delta=0.005)
        # This implementation gives 0.087 liquid at the end of primary solidification (Eq. 1 at the Eq. 6
        # intersection), against "0.10" in the D97 text; stated, not tuned.
        self.assertAlmostEqual(r["fEutecticTotal"], 0.087, delta=0.002)
        self.assertAlmostEqual(r["fGammaNbCConstituent"], 0.065, delta=0.003)
        self.assertEqual(r["terminatedBy"], "laves-point")

    def test_d97_high_c_low_nb_alloys_form_no_laves(self):
        # D97: Ni base alloys 2, 3.5 and 4 (high C / low Nb) showed no Laves phase.
        for nb, c in ((1.95, 0.132), (1.94, 0.075), (1.91, 0.155)):
            r = seg.pseudo_ternary_path(nb, c, NI)
            self.assertEqual(r["fGammaLavesConstituent"], 0.0, (nb, c, r))
            self.assertGreater(r["fGammaNbCConstituent"], 0.0)
            self.assertEqual(r["terminatedBy"], "liquid-exhausted-on-NbC-line")

    def test_mass_bookkeeping(self):
        r = seg.pseudo_ternary_path(5.125, 0.08, NI)
        self.assertAlmostEqual(r["fGammaNbCConstituent"] + r["fGammaLavesConstituent"], r["fEutecticTotal"], places=12)
        self.assertLessEqual(r["fEutecticTotal"], 1.0)

    def test_step_convergence(self):
        coarse = seg.pseudo_ternary_path(5.125, 0.08, NI)
        fine = seg.pseudo_ternary_path(5.125, 0.08, NI, step_wt_nb=seg.EUTECTIC_STEP_WT_NB / 10.0)
        self.assertLess(abs(coarse["fGammaLavesConstituent"] - fine["fGammaLavesConstituent"]), 1e-3)

    def test_binary_is_upper_bound_on_laves_over_carbon(self):
        f_bin = seg.scheil_eutectic_fraction(5.125, NI["C_Nb_laves"]["value"], NI["k_gamma_Nb"]["value"])
        prev = f_bin
        for c in (0.001, 0.005, 0.01, 0.02, 0.04, 0.06, 0.08, 0.12, 0.17):
            r = seg.pseudo_ternary_path(5.125, c, NI)
            self.assertLessEqual(r["fGammaLavesConstituent"], prev + 1e-12, c)
            prev = r["fGammaLavesConstituent"]

    def test_low_carbon_reaches_laves_point_before_nbc_line(self):
        r = seg.pseudo_ternary_path(1.82, 0.010, NI)  # D97 alloy 3
        self.assertEqual(r["fGammaNbCConstituent"], 0.0)
        self.assertAlmostEqual(r["fGammaLavesConstituent"], seg.scheil_eutectic_fraction(1.82, 23.1, 0.46), places=12)

    def test_primary_nbc_field_is_outside_model(self):
        self.assertEqual(seg.pseudo_ternary_path(5.0, 1.0, NI)["status"], "outside-model")

    def test_documented_discrepancy_with_d97_measurements(self):
        # Documented discrepancy, NOT a calibration target (nothing is tuned to these numbers).
        # D97 Fig. 3 (QIA of GTA welds, read from the bar chart, about +-0.5 vol%):
        #   alloy 5 (Table 1: 5.17 Nb, 0.013 C): gamma/Laves about 2 vol%  -> model about 3x high
        #   alloy 8 (Table 1: 4.72 Nb, 0.170 C): gamma/Laves about 1.5 vol% on about 14 vol% gamma/NbC
        #                                        -> model predicts no gamma/Laves at all
        a5 = seg.pseudo_ternary_path(5.17, 0.013, NI)
        self.assertAlmostEqual(a5["fGammaLavesConstituent"], 0.0625, delta=0.001)
        self.assertGreater(a5["fGammaLavesConstituent"], 2.0 * 0.02)  # over-prediction vs Fig. 3
        a8 = seg.pseudo_ternary_path(4.72, 0.170, NI)
        self.assertEqual(a8["fGammaLavesConstituent"], 0.0)  # under-prediction vs Fig. 3 (measured > 0)
        self.assertAlmostEqual(a8["fGammaNbCConstituent"], 0.148, delta=0.002)
        self.assertEqual(a8["terminatedBy"], "liquid-exhausted-on-NbC-line")


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
        lav = [p["binaryUpperBound"]["fGammaLavesConstituent"] for p in b["band"]]
        self.assertEqual(lav, sorted(lav))
        for p in b["band"]:
            self.assertLessEqual(p["pseudoTernaryAtCmax"]["fGammaLavesConstituent"], p["binaryUpperBound"]["fGammaLavesConstituent"])
        self.assertEqual(b["k_Nb"]["value"], 0.45)
        self.assertIn("Table", b["k_Nb"]["locator"])
        self.assertEqual(b["riskClass"], "eutectic Laves expected (Scheil)")
        v = b["validity"]
        self.assertIs(v["outsideSourceRegime"], True)
        self.assertIs(v["outsideSourceComposition"], True)
        self.assertTrue(any(r.startswith("Mo") for r in v["outsideSourceCompositionReasons"]))
        self.assertIn("upper bound", b["upperBoundNote"].lower())
        self.assertIn("back-diffusion", b["upperBoundNote"])
        seg_ratio = b["segregation"]
        self.assertEqual(seg_ratio["coreRatioToNominal"], 0.45)
        self.assertTrue(all(r["ratioToNominal"] > 1.0 for r in seg_ratio["interdendritic"]))
        json.dumps(b, allow_nan=False)

    def test_source_agreement_and_quantity_notes(self):
        b = seg.segregation_estimate("in718", _micro("available"))
        note = b["sourceAgreementNote"]
        self.assertEqual(note, seg.SOURCE_AGREEMENT_NOTE)
        self.assertIn("Fig. 9b", note)
        self.assertIn("predicts no gamma/Laves", note)
        self.assertIn("not an upper bound on measured", b["upperBoundNote"])
        self.assertIn("not phase fractions", b["quantity"])
        self.assertIn("not a bound on measurement", b["binaryBoundNote"])

    def test_risk_class_is_stated_positive_by_construction(self):
        b = seg.segregation_estimate("in718", _micro("available"))
        self.assertIs(b["riskClassPositiveByConstruction"], True)
        self.assertIn("positive by construction", b["riskClassRule"])
        for nb in (0.5, 1.0, 5.0):  # binary Scheil: f_e > 0 for every Nb > 0
            self.assertGreater(seg.scheil_eutectic_fraction(nb, 23.1, 0.46), 0.0)

    def test_app_nominal_composition_is_explained(self):
        b = seg.segregation_estimate("in718", _micro("available"))
        self.assertIn("alloy_registry", b["composition"]["appNominalNote"])
        self.assertIn("no cited source", b["composition"]["appNominalNote"])

    def test_fe_balance_uses_containment(self):
        # A specification whose Fe range overlaps the source range at one end is still outside.
        info = {"balanceByDifference_wt": {"min": 11.0, "max": 25.0}}
        v = seg._validity("in718", info, "ni-base")
        self.assertTrue(any(r.startswith("Fe") for r in v["outsideSourceCompositionReasons"]))
        inside = seg._validity("in718", {"balanceByDifference_wt": {"min": 10.5, "max": 11.0}}, "ni-base")
        self.assertFalse(any(r.startswith("Fe") for r in inside["outsideSourceCompositionReasons"]))

    def test_in718_output_unchanged_by_the_in625_branch(self):
        # sha256 of the in718 block with the D98 Table 2 constants (re-pinned deliberately when the source switched
        # from the D97 conference values; the previous pin 489d0b83... was the D97-constant output).
        b = seg.segregation_estimate("in718", _micro("available"))
        digest = hashlib.sha256(json.dumps(b, sort_keys=True, allow_nan=False).encode()).hexdigest()
        self.assertEqual(digest, "e0b46e9f72c55a4166c620acd77c9b06a58c14039114a373d54e4cd539510f8c")

    def test_in625_output_unchanged_by_the_d98_switch(self):
        # sha256 of the in625 block as produced on main 9f5c4e72 (D97 constants for IN718); in625 uses its own
        # constant sets (C88 / D96), so the D98 switch must not move it.
        for micro, pin in ((_micro("available"), "11209258f4d5909c87912420b147f288db44ed146aae48dd3604db82af70a798"),
                           (None, "5a1cf4c183db7a4f7c5fb98ebd6e60cb60078693cf01176eb7370698ad34f4dc")):
            b = seg.segregation_estimate("in625", micro)
            digest = hashlib.sha256(json.dumps(b, sort_keys=True, allow_nan=False).encode()).hexdigest()
            self.assertEqual(digest, pin)

    def test_in625_unverified_constant_gives_unavailable(self):
        patched = copy.deepcopy(seg.CONSTANTS)
        patched["in625-c88"]["C_Nb_laves"] = {**patched["in625-c88"]["C_Nb_laves"], "value": None, "verified": False}
        with mock.patch.object(seg, "CONSTANTS", patched):
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


class In625(unittest.TestCase):
    """Alloy 625: k_Nb from Cieslak et al. 1988 (C88), C_e from DuPont 1996 (D96); binary gamma-Nb Scheil only."""

    def test_reproduces_d96_own_check(self):
        # D96 Section IV-C: Eq. 5 with C_e 18.9, C_0 2.07, k_Nb 0.46 gives f_e = 1.7 vol% (measured 1.3-2.2 vol%
        # gamma + Laves in the DTA sample). Tolerance: the paper rounds to 0.1 vol%, so |f - 0.017| <= 0.0005.
        f = seg.scheil_eutectic_fraction(2.07, 18.9, 0.46)
        self.assertAlmostEqual(f, 0.017, delta=0.0005)
        self.assertTrue(0.013 <= f <= 0.022)
        b = seg.segregation_estimate("in625", None)
        self.assertEqual(b["sourceReproduction"]["fComputed"], round(f, 4))
        self.assertEqual(b["sourceReproduction"]["measuredRange"], [0.013, 0.022])

    def test_c88_k_values_are_core_over_nominal(self):
        # C88 Table VIII: k = C_core / C_nom by EPMA, reported to two decimals (core 1.91/1.82/1.84/1.79 wt%).
        for core, (alloy, row) in zip((1.91, 1.82, 1.84, 1.79), sorted(seg.C88_MEASURED.items())):
            self.assertAlmostEqual(core / row["Nb_wt"], row["k"], delta=0.006, msg=alloy)
        self.assertEqual(seg.CONSTANTS["in625-c88"]["k_gamma_Nb"]["value"],
                         min(r["k"] for r in seg.C88_MEASURED.values()))
        # C88 Table VII: k = m_L / m_S = 11.1 / 20.6 for Nb
        self.assertAlmostEqual(11.1 / 20.6, seg.CONSTANTS["in625-c88"]["k_gamma_Nb_slopes"]["value"], delta=0.005)

    def test_constants_and_locators(self):
        c = seg.CONSTANTS["in625-c88"]
        self.assertEqual(c["k_gamma_Nb"]["source"], "C88")
        self.assertIn("Table VIII", c["k_gamma_Nb"]["locator"])
        self.assertIn("Table VII", c["k_gamma_Nb_slopes"]["locator"])
        self.assertEqual(c["C_Nb_laves"]["value"], 18.9)
        self.assertEqual(c["C_Nb_laves"]["source"], "D96")
        self.assertIn("Eq. 5", c["C_Nb_laves"]["locator"])
        d = seg.CONSTANTS["in625-d96"]
        self.assertEqual(d["k_gamma_Nb"]["value"], 0.46)
        self.assertIn("Table IV", d["k_gamma_Nb"]["locator"])
        self.assertTrue(seg.SOURCES["C88"]["read"] and seg.SOURCES["D96"]["read"] and seg.SOURCES["SM625"]["read"])
        # C_e = 18.9 is the 75/25 vol% Laves/gamma mix of 22.1 and 9.3 wt% Nb (D96 Tables III and V)
        self.assertAlmostEqual(0.75 * 22.1 + 0.25 * 9.3, 18.9, places=9)
        # D96 Table IV: k_Nb = C_s,i / C_0 = 0.97 / 2.07 is 0.469; the paper reports 0.46 and that value is used
        self.assertAlmostEqual(0.97 / 2.07, 0.46, delta=0.01)

    def test_source_composition_ranges(self):
        c88 = seg.SOURCE_COMPOSITION_RANGE["in625-c88"]
        self.assertIn("Table I", c88["locator"])
        self.assertEqual(c88["range"]["Nb"], (3.53, 3.61))
        self.assertEqual(c88["range"]["Fe"], (2.26, 2.31))
        d96 = seg.SOURCE_COMPOSITION_RANGE["in625-d96"]
        self.assertIn("Table II", d96["locator"])
        expected = {"Fe": 28.14, "Ni": 44.91, "Cr": 16.67, "Mo": 6.78, "Nb": 2.07, "Si": 0.24, "Ti": 0.17, "C": 0.050}
        self.assertEqual({el: lo for el, (lo, hi) in d96["range"].items()}, expected)
        self.assertTrue(all(lo == hi for lo, hi in d96["range"].values()))

    def test_in625_available_binary_band_over_spec(self):
        b = seg.segregation_estimate("in625", _micro("available"))
        self.assertEqual(b["status"], "available")
        self.assertEqual(b["schema"], seg.SCHEMA)
        self.assertEqual(b["modelId"], seg.IN625_MODEL_ID)
        self.assertTrue(b["evidenceLabel"].startswith("Literature estimate (screening)"))
        self.assertEqual(b["constantSet"], "in625-c88")
        self.assertIn("Cieslak", b["source"]["citation"])
        self.assertIn("DuPont", b["secondarySource"]["citation"])
        self.assertIn("Special Metals", b["composition"]["source"])
        self.assertEqual([p["Nb_wt"] for p in b["band"]], [3.15, 3.65, 4.15])
        lav = [p["binaryUpperBound"]["fGammaLavesConstituent"] for p in b["band"]]
        for p, f in zip(b["band"], lav):
            self.assertEqual(f, round(seg.scheil_eutectic_fraction(p["Nb_wt"], 18.9, 0.51), 4))
            self.assertEqual(p["pseudoTernaryAtCmax"]["status"], "not-modelled")
            self.assertNotIn("fGammaLavesConstituent", p["pseudoTernaryAtCmax"])
        self.assertEqual(lav, [0.0258, 0.0349, 0.0453])
        ks = b["kSensitivity"]
        self.assertEqual([p["fGammaLavesConstituent"] for p in ks["c88TableVII"]["band"]], [0.0203, 0.028, 0.037])
        self.assertEqual([p["fGammaLavesConstituent"] for p in ks["d96Overlay"]["band"]], [0.0362, 0.0476, 0.0604])
        self.assertNotIn("feBaseSensitivity", b)
        self.assertIsNone(b["riskClass"])
        self.assertIn("not established", b["riskClassRule"])
        self.assertEqual(b["k_Nb"]["value"], 0.51)
        json.dumps(b, allow_nan=False)

    def test_c88_comparison_model_is_high_in_every_alloy(self):
        # Documented comparison, NOT a calibration target: C88 Section III-B measured 0.3-1.3 vol% total minor
        # constituent in alloys 5-8; the model (own k, C_e 18.9) gives about 3 % in each, 2.4-9.8x higher.
        rows = seg.segregation_estimate("in625", None)["sourceComparison"]["c88"]
        self.assertEqual([r["alloy"] for r in rows], ["5", "6", "7", "8"])
        self.assertEqual([r["fMeasured"] for r in rows], [0.003, 0.007, 0.013, 0.009])
        for r in rows:
            self.assertGreater(r["fComputed"], r["fMeasured"] + 2 * r["fMeasuredSd"], r)
        self.assertEqual([r["ratioComputedToMeasured"] for r in rows], [9.8, 4.8, 2.4, 3.6])
        self.assertIn("NbC only", rows[1]["phasesObserved"])

    def test_in625_validity_states_the_limits(self):
        v = seg.segregation_estimate("in625", _micro("available"))["validity"]
        self.assertIs(v["outsideSourceRegime"], True)
        self.assertIs(v["outsideSourceComposition"], True)
        self.assertIn("LPBF", v["outsideSourceRegimeReason"])
        for el in ("Nb", "C", "Fe", "Si"):
            self.assertTrue(any(r.startswith(el + ":") for r in v["outsideSourceCompositionReasons"]), el)
        self.assertEqual(v["d96SourceComposition_wt"]["Fe"], 28.14)
        self.assertIn("28.14 wt% Fe", v["d96SourceNote"])
        for word in ("NbC", "Laves", "not established", "alloy 6"):
            self.assertIn(word, v["phaseIdentityNote"])
        self.assertIn("Alloy 718", v["ceTransferNote"])
        self.assertIn("16.8-19.2", v["ceTransferNote"])

    def test_in625_ratio_and_coupling(self):
        b = seg.segregation_estimate("in625", _micro("available"))
        self.assertEqual(b["segregation"]["coreRatioToNominal"], 0.51)
        self.assertIn("C88", b["segregation"]["basis"])
        self.assertEqual(b["processCoupling"]["status"], "available")
        self.assertIs(b["processCoupling"]["usedInCalculation"], False)
        self.assertEqual(seg.segregation_estimate("in625", None)["processCoupling"]["status"], "unavailable")
        text = json.dumps(b).lower()
        for banned in ("v_d", "aziz", "diffusive speed"):
            self.assertNotIn(banned, text)


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
