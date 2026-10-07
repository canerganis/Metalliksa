"""Offline tests for lpbf_calibration_stats.py and lpbf_calibration_cells.py (synthetic kernel; no dataset, no solver,
no GPU). HELD-OUT CALIBRATION OF NUISANCE PARAMETERS, NOT EXPERIMENTAL VALIDATION."""

import copy
import math
import random
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import calibration_synth_support as sy  # noqa: E402
import lpbf_calibration_cells as cl  # noqa: E402
import lpbf_calibration_stats as st  # noqa: E402
from lpbf_calibration_config import CALIBRATION_CONFIG as CFG, CATALOG_SOURCES  # noqa: E402

CFG_SMALL = sy.small_cfg(CFG)
ALLOY = "SynthAlloy"
CFG_SMALL["materialDefaults"][ALLOY] = 0.42


def rows_for(source, n, eta_w, eta_d, offset_w=0.0, offset_d=0.0, noise=0.0, seed=0, **kw):
    return sy.synth_rows(source, ALLOY, n, eta_w, eta_d, 0.42, offset_w, offset_d, noise=noise, seed=seed, **kw)


def fk_for(rows, kernel="eagar-tsai"):
    return sy.build_fk(rows, kernel)


class SplitTests(unittest.TestCase):
    def test_replicates_never_straddle_folds(self):  # T-SPL-1
        rows = rows_for("A", 40, 0.5, 0.5, seed=1)
        assert any(sum(1 for r in rows if st.set_key(r) == st.set_key(x)) > 1 for x in rows), "fixture needs replicates"
        for seed in (0, 1, 2):
            seen = {}
            for f, (train, test) in enumerate(st.grouped_kfold(rows, 5, seed)):
                st.assert_no_leak(train, test)
                for r in test:
                    seen.setdefault(st.set_key(r), set()).add(f)
            self.assertTrue(all(len(v) == 1 for v in seen.values()))
        self.assertEqual(st.grouped_kfold(rows, 5, 0)[0][1], st.grouped_kfold(rows, 5, 0)[0][1])

    def test_kfold_idx_uses_the_same_fold_rule(self):
        rows = rows_for("A", 30, 0.5, 0.5, seed=2)
        fk = fk_for(rows)
        by_rows = st.grouped_kfold(rows, 5, 1)
        by_idx = st.kfold_idx(fk, np.arange(len(rows)), 5, 1)
        for (_, test_rows), (_, test_idx) in zip(by_rows, by_idx):
            self.assertEqual(sorted(r["rowId"] for r in test_rows), sorted(rows[i]["rowId"] for i in test_idx))

    def test_loso_never_shares_a_source_and_assert_no_leak_raises(self):  # T-SPL-2
        rows = rows_for("A", 20, 0.5, 0.5, seed=3) + rows_for("B", 20, 0.5, 0.5, seed=4)
        for held, train, test in st.leave_one_source_out(rows):
            self.assertTrue(all(st.row_source(r) != held for r in train))
            self.assertTrue(all(st.row_source(r) == held for r in test))
            st.assert_no_leak(train, test, by_source=True)
        with self.assertRaises(AssertionError):
            st.assert_no_leak(rows[:5], rows[3:8])
        with self.assertRaises(AssertionError):
            st.assert_no_leak(rows_for("A", 5, 0.5, 0.5, seed=5), rows_for("A", 5, 0.5, 0.5, seed=6), by_source=True)


class FitTests(unittest.TestCase):
    def test_recovers_true_eta_within_one_grid_step_without_noise(self):  # T-FIT-1
        rows = rows_for("A", 40, 0.55, 0.55, seed=1)
        fk = fk_for(rows)
        fit = st.fit_ladder(fk, np.arange(len(rows)), CFG_SMALL, 0.42)
        step = CFG_SMALL["fitGrid"]["step"]
        self.assertLessEqual(abs(fit["etaW"] - 0.55), step + 1e-9)
        self.assertLessEqual(abs(fit["etaD"] - 0.55), step + 1e-9)

    def test_bound_hit_is_flagged(self):  # T-FIT-2
        rows = rows_for("A", 30, 0.95, 0.95, seed=2)
        fit = st.fit_ladder(fk_for(rows), np.arange(len(rows)), CFG_SMALL, 0.42)
        self.assertAlmostEqual(fit["etaW"], CFG_SMALL["bounds"][1], places=6)
        self.assertTrue(fit["boundHit"]["W"] and fit["boundHit"]["D"])

    def test_prior_pulls_toward_the_prior_when_data_are_flat(self):  # T-FIT-3
        rows = rows_for("A", 30, 0.5, 0.5, seed=3)
        fk = fk_for(rows)
        K = fk.lnW.shape[1]
        flat = np.zeros((len(rows), len(fk.eta)))
        fk.lnW = fk.lnW[:, :1] + flat  # same value at every eta
        fk.lnD = fk.lnD[:, :1] + flat
        fit = st.fit_ladder(fk, np.arange(len(rows)), CFG_SMALL, 0.42)
        self.assertAlmostEqual(fit["etaW"], 0.42, delta=CFG_SMALL["fitGrid"]["step"] + 1e-9)
        self.assertAlmostEqual(fit["etaD"], 0.42, delta=CFG_SMALL["fitGrid"]["step"] + 1e-9)

    def test_depth_offset_class_fallback_chain(self):  # T-FIT-4
        rows = rows_for("A", 30, 0.5, 0.5, offset_d=0.2, seed=4)
        for i, r in enumerate(rows):
            r["regimeClass"] = "keyhole" if i % 3 else ("conduction" if i % 15 == 0 else "keyhole")
        fk = fk_for(rows)
        fit = st.fit_ladder(fk, np.arange(len(rows)), CFG_SMALL, 0.42)
        self.assertEqual(fit["cdSource"]["keyhole"], "class")
        self.assertEqual(fit["cdSource"]["conduction"], "alloy")
        self.assertEqual(fit["cdSource"]["transition"], "alloy")
        few = rows[:8]
        few_fit = st.fit_ladder(fk_for(few), np.arange(len(few)), CFG_SMALL, 0.42)
        self.assertTrue(all(v == "zero" for v in few_fit["cdSource"].values()), few_fit["cdSource"])
        self.assertTrue(all(v == 0.0 for v in few_fit["cd"].values()))
        self.assertTrue(all(abs(v) <= CFG_SMALL["cdClipLn"] + 1e-9 for v in fit["cd"].values()))

    def test_source_weight_is_capped_for_small_sources(self):  # T-WEIGHT-1
        w = st.source_weights({"big": 40, "tiny": 4}, 20)
        self.assertAlmostEqual(sum(w.values()), 1.0)
        self.assertAlmostEqual(w["tiny"], (4 / 20) / (1 + 4 / 20))
        self.assertLess(w["tiny"], 0.2)  # equal weighting would give 0.5

    def test_guards_refuse_catalog_rows(self):  # T-LEAK-3 (guard)
        rows = rows_for("A", 6, 0.5, 0.5, seed=5)
        rows[0]["catalog"] = True
        with self.assertRaises(AssertionError):
            st.assert_trainable(rows, CATALOG_SOURCES)
        with self.assertRaises(AssertionError):
            st.assert_trainable(rows_for("guo-316l-2024", 3, 0.5, 0.5, seed=6), CATALOG_SOURCES)
        fk = fk_for(rows_for("guo-316l-2024", 12, 0.5, 0.5, seed=7))
        with self.assertRaises(AssertionError):
            cl.serve(fk, np.arange(len(fk.rows)), CFG_SMALL, 0.42)


class BootstrapTests(unittest.TestCase):
    def test_deterministic_for_a_seed_and_ci_contains_truth(self):  # T-BOOT-1
        rows = rows_for("A", 40, 0.55, 0.55, seed=1) + rows_for("B", 30, 0.55, 0.55, seed=2)
        fk = fk_for(rows)
        idx = np.arange(len(rows))
        a = st.fit_ladder(fk, idx, CFG_SMALL, 0.42, bootstrap=True, seed=0)
        b = st.fit_ladder(fk, idx, CFG_SMALL, 0.42, bootstrap=True, seed=0)
        self.assertEqual(a["boot"], b["boot"])
        c = st.fit_ladder(fk, idx, CFG_SMALL, 0.42, bootstrap=True, seed=1)
        self.assertEqual(c["etaW"], a["etaW"])
        for key in ("W", "D"):
            lo, hi = a["boot"][key]["ci90"]
            self.assertLessEqual(lo, 0.55 + 1e-9)
            self.assertGreaterEqual(hi, 0.55 - 1e-9)

    def test_paired_skill_bootstrap_is_deterministic(self):
        rng = np.random.default_rng(0)
        meas = rng.uniform(50, 200, 60)
        good = meas * (1 + rng.normal(0, 0.05, 60))
        bad = meas * (1 + rng.normal(0.2, 0.1, 60))
        cl_ids = np.repeat(np.arange(20), 3)
        a = st.paired_skill(good, bad, meas, np.ones(60, bool), cl_ids, 300, 0)
        b = st.paired_skill(good, bad, meas, np.ones(60, bool), cl_ids, 300, 0)
        self.assertEqual(a, b)
        self.assertGreater(a["ci95"][0], 0.0)
        self.assertEqual(st.verdict_from_ci(a["ci95"]), "beats")


class IntervalTests(unittest.TestCase):
    def test_conformal_interval_reaches_nominal_coverage(self):  # T-PI-1
        rng = np.random.default_rng(1)
        s_within, tau = 0.10, 0.12
        k = 0
        n = 0
        for _ in range(500):  # many held-out sources drawn from the SAME offset distribution
            off = rng.normal(0.0, tau)
            ln_res = off + rng.normal(0.0, s_within, 40)  # ln(meas / pred)
            lo, hi = st.conformal_interval(0.0, s_within, tau, 0.9)
            cov = st.coverage(np.exp(ln_res), np.ones(40), lo, hi, np.ones(40, bool))
            k += cov["k"]
            n += cov["n"]
        self.assertAlmostEqual(k / n, 0.9, delta=0.05)

    def test_undercoverage_is_reported_not_hidden(self):  # T-PI-2
        s_within, tau = 0.10, 0.12
        lo, hi = st.conformal_interval(0.0, s_within, tau, 0.9)
        offset = 5 * tau  # a held-out source far outside the offset distribution
        rng = np.random.default_rng(2)
        meas = np.exp(offset + rng.normal(0, s_within, 40))
        cov = st.coverage(meas, np.ones(40), lo, hi, np.ones(40, bool))
        self.assertLess(cov["coverage"], 0.5)
        self.assertLess(cov["wilson95"][1], 0.9)
        gate = CFG["gate"]
        ev = {"hasSecondSource": True, "servedRung": "eta", "flags": {}, "etaConsistent": True, "unresolvedWorse": False,
              "p2": [{"source": "S", "skillLb95": 0.2, "coverage90N": 40, "coverage90WilsonUpper": cov["wilson95"][1],
                      "unresolvedRung": 0, "unresolvedDefault": 0}], "p1": []}
        self.assertNotEqual(st.gate_cell(ev, gate)["status"], "enabled")

    def test_source_sd_inflation_and_minimum_sources(self):
        self.assertIsNone(st.source_sd_inflated([0.1, 0.2]))
        out = st.source_sd_inflated([0.0, 0.1, -0.1, 0.05])
        self.assertGreater(out["sdUpper"], out["sd"])
        self.assertAlmostEqual(st.chi2_ppf(0.95, 3), 7.8147, delta=1e-3)
        self.assertAlmostEqual(st.chi2_ppf(0.10, 3), 0.5844, delta=1e-3)

    def test_wilson_interval(self):
        lo, hi = st.wilson(9, 10)
        self.assertTrue(0.55 < lo < 0.65 and 0.97 < hi <= 1.0)
        self.assertIsNone(st.wilson(0, 0))


def gate_ev(**kw):
    ev = {"noData": False, "hasSecondSource": True, "servedRung": "eta2", "flags": {}, "etaConsistent": True,
          "unresolvedWorse": False,
          "p2": [{"source": "A", "skillLb95": 0.10, "coverage90N": 40, "coverage90WilsonUpper": 0.97,
                  "unresolvedRung": 0, "unresolvedDefault": 0},
                 {"source": "B", "skillLb95": -0.01, "coverage90N": 30, "coverage90WilsonUpper": 0.95,
                  "unresolvedRung": 0, "unresolvedDefault": 0}],
          "p1": [{"source": "A", "lb": 0.05}]}
    ev.update(kw)
    return ev


class GateTests(unittest.TestCase):
    G = CFG["gate"]

    def test_enabled(self):  # T-GATE-1
        self.assertEqual(st.gate_cell(gate_ev(), self.G)["status"], "enabled")

    def test_within_source_only(self):  # T-GATE-2
        bad = gate_ev()
        bad["p2"][1]["skillLb95"] = -0.2  # fails the cross-source floor, but the within-source skill is positive
        self.assertEqual(st.gate_cell(bad, self.G)["status"], "within-source-only")
        single = gate_ev(hasSecondSource=False, p2=[])
        self.assertEqual(st.gate_cell(single, self.G)["status"], "within-source-only")

    def test_rejected(self):  # T-GATE-3
        none_pos = gate_ev(p1=[{"source": "A", "lb": -0.05}])
        none_pos["p2"][1]["skillLb95"] = -0.2
        self.assertEqual(st.gate_cell(none_pos, self.G)["status"], "rejected")
        only_flat = gate_ev()
        only_flat["p2"][0]["skillLb95"] = 0.0  # no source with lower bound strictly > 0
        self.assertNotEqual(st.gate_cell(only_flat, self.G)["status"], "enabled")
        cov = gate_ev()
        cov["p2"][0]["coverage90WilsonUpper"] = 0.85
        self.assertNotEqual(st.gate_cell(cov, self.G)["status"], "enabled")
        small_n = gate_ev()
        small_n["p2"][0].update(coverage90N=6, coverage90WilsonUpper=0.2)  # n < 10: the coverage rule is not applied
        self.assertEqual(st.gate_cell(small_n, self.G)["status"], "enabled")

    def test_default_rung_blocks_enabled_but_keeps_a_within_source_gain_visible(self):
        ev = gate_ev(servedRung="default")
        out = st.gate_cell(ev, self.G)
        self.assertEqual(out["status"], "within-source-only")
        self.assertTrue(any(r.startswith("noRungImprovesAcrossSources") for r in out["reasons"]))
        no_p1 = st.gate_cell(gate_ev(servedRung="default", p1=[]), self.G)
        self.assertEqual(no_p1["status"], "rejected")
        none_possible = st.gate_cell(gate_ev(hasSecondSource=False, p2=[], p1=[]), self.G)
        self.assertEqual(none_possible["status"], "rejected")
        self.assertTrue(any("no within-source evaluation possible" in r for r in none_possible["reasons"]))

    def test_no_data(self):  # T-GATE-4
        out = st.gate_cell({"noData": True}, self.G)
        self.assertEqual(out["status"], "no-data")

    def test_each_physics_flag_forces_rejected_with_its_name(self):  # T-PHYS-1..4 (gate side)
        for name in ("boundHit", "etaSplit", "offsetDominant", "etaInconsistentWithMeasuredAbsorptance"):
            out = st.gate_cell(gate_ev(flags={name: True}), self.G)
            self.assertEqual(out["status"], "rejected", name)
            self.assertIn(name, out["reasons"])

    def test_source_dependent_eta_rejects(self):  # T-CONS-1 (gate side)
        out = st.gate_cell(gate_ev(etaConsistent=False), self.G)
        self.assertEqual(out["status"], "rejected")
        self.assertIn("sourceDependentEta", out["reasons"])

    def test_unresolved_rows_count_against_the_rung(self):  # T-UNRES-1 (gate side)
        worse = gate_ev()
        worse["p2"][0]["unresolvedRung"] = 3
        worse["p2"][0]["unresolvedDefault"] = 1
        self.assertNotEqual(st.gate_cell(worse, self.G)["status"], "enabled")
        self.assertEqual(st.gate_cell(gate_ev(unresolvedWorse=True), self.G)["status"], "rejected")

    def test_beam_reading_disagreement_rejects(self):  # T-BEAM-1
        same = st.combine_beam_variants({"37.5": {"status": "rejected", "reasons": ["x"]},
                                         "75.0": {"status": "rejected", "reasons": ["y"]}})
        self.assertEqual(same["status"], "rejected")
        diff = st.combine_beam_variants({"37.5": {"status": "enabled", "reasons": []},
                                         "75.0": {"status": "within-source-only", "reasons": []}})
        self.assertEqual(diff["status"], "rejected")
        self.assertTrue(diff["reasons"][0].startswith("unresolvedInput"))

    def test_eta_consistency_rule(self):
        self.assertTrue(st.eta_consistent(0.42, [0.40, 0.44], 0.45, [0.43, 0.47], 0.15))
        self.assertFalse(st.eta_consistent(0.33, [0.31, 0.35], 0.42, [0.41, 0.43], 0.15))
        self.assertTrue(st.eta_consistent(0.33, [0.2, 0.5], 0.42, [0.3, 0.5], 0.15))


class PhysicsFlagTests(unittest.TestCase):
    base_fit = {"jW": 10, "jD": 10, "jJ": 10, "etaW": 0.5, "etaD": 0.5, "etaJ": 0.5, "boundHit": {"W": False, "D": False, "J": False},
                "cd": {"conduction": 0.0, "transition": 0.0, "keyhole": 0.0}, "boot": {}}

    def flags(self, fit, rung, q, material="SynthAlloy", class_sets=None):
        return cl.physics_flags(fit, rung, q, CFG_SMALL, class_sets or {"conduction": 10, "transition": 10, "keyhole": 10}, material)

    def test_bound_hit(self):  # T-PHYS-1
        fit = copy.deepcopy(self.base_fit)
        fit["boundHit"]["W"] = True
        self.assertTrue(self.flags(fit, "eta2", "width")["flags"]["boundHit"])
        fit2 = copy.deepcopy(self.base_fit)
        fit2["boot"] = {"W": {"boundHitFraction": 0.3}}
        self.assertTrue(self.flags(fit2, "eta2", "width")["flags"]["boundHit"])
        self.assertFalse(self.flags(self.base_fit, "eta2", "width")["flags"]["boundHit"])

    def test_eta_split(self):  # T-PHYS-2
        fit = copy.deepcopy(self.base_fit)
        fit.update(etaW=0.30, etaD=0.60)
        self.assertTrue(self.flags(fit, "eta2", "width")["flags"]["etaSplit"])
        self.assertFalse(self.flags(fit, "eta", "width")["flags"]["etaSplit"], "tied joint eta is not a split")

    def test_offset_dominant(self):  # T-PHYS-3
        fit = copy.deepcopy(self.base_fit)
        fit["cd"]["keyhole"] = -0.5
        self.assertTrue(self.flags(fit, "eta2+dOffset", "depth")["flags"]["offsetDominant"])
        self.assertFalse(self.flags(fit, "eta2", "depth")["flags"]["offsetDominant"])

    def test_absorptance_disagreement(self):  # T-PHYS-4
        fit = copy.deepcopy(self.base_fit)
        fit.update(etaW=0.70, etaD=0.70)
        out = self.flags(fit, "eta2", "width", material="316L Stainless Steel", class_sets={"conduction": 12, "transition": 0, "keyhole": 0})
        self.assertTrue(out["flags"]["etaInconsistentWithMeasuredAbsorptance"])
        self.assertIn("absorbing model error", " ".join(out["notes"]))
        fine = self.flags(dict(fit, etaW=0.34), "eta2", "width", material="316L Stainless Steel", class_sets={"conduction": 12, "transition": 0, "keyhole": 0})
        self.assertFalse(fine["flags"]["etaInconsistentWithMeasuredAbsorptance"])


class PhysicsDiagnosticsForDefaultRungTests(unittest.TestCase):
    """The diagnostics exist for every fitted cell, also when the served rung is `default`; they never veto then."""
    base_fit = PhysicsFlagTests.base_fit
    flags = PhysicsFlagTests.flags

    def test_default_rung_still_computes_diagnostics_but_is_not_gate_relevant(self):
        fit = copy.deepcopy(self.base_fit)
        fit.update(etaW=0.30, etaD=0.60)
        fit["boundHit"]["D"] = True
        fit["cd"]["keyhole"] = -0.5
        out = self.flags(fit, "default", "depth")
        self.assertFalse(out["gateRelevant"])
        self.assertTrue(out["diagnosticFlags"]["boundHit"] and out["diagnosticFlags"]["etaSplit"]
                        and out["diagnosticFlags"]["offsetDominant"])
        self.assertFalse(any(out["flags"].values()), "nothing is served, so nothing can veto")
        self.assertAlmostEqual(out["diagnostics"]["maxAbsCd"], 0.5)
        self.assertIn("diagnostic only", " ".join(out["notes"]))
        self.assertIn("absorptanceMismatch", self.flags(fit, "default", "width", material="316L Stainless Steel",
                                                         class_sets={"conduction": 12, "transition": 0, "keyhole": 0})["diagnostics"])

    def test_served_rung_keeps_gate_semantics(self):
        fit = copy.deepcopy(self.base_fit)
        fit["boundHit"]["W"] = True
        out = self.flags(fit, "eta2", "width")
        self.assertTrue(out["gateRelevant"] and out["flags"]["boundHit"] and out["diagnosticFlags"]["boundHit"])

    def test_no_fit_gives_empty_flags(self):
        out = self.flags(None, "default", "width")
        self.assertFalse(any(out["flags"].values()) or any(out["diagnosticFlags"].values()))


class BoundHitGridStepTests(unittest.TestCase):
    def test_within_one_fine_step_of_the_bound_counts(self):  # R5: "within one grid step", not only exactly on the bound
        src = (Path(__file__).resolve().parent / "lpbf_calibration_stats.py").read_text(encoding="utf-8")
        self.assertIn("j <= step or j >= J - 1 - step", src)
        self.assertIn("(j[okj] <= step) | (j[okj] >= J - 1 - step)", src)
        self.assertEqual(CFG["gate"]["boundHitSteps"], 1)


class ConfusionTests(unittest.TestCase):
    def test_counts_and_keyhole_precision_recall(self):  # T-CONF-1
        pub = ["keyhole", "keyhole", "keyhole", "conduction", "conduction", "transition"]
        pred = ["keyhole", "keyhole", "transition", "keyhole", "conduction", "transition"]
        c = st.confusion(pub, pred)
        self.assertEqual(c["matrix"]["keyhole"]["keyhole"], 2)
        self.assertEqual(c["matrix"]["keyhole"]["transition"], 1)
        self.assertEqual(c["matrix"]["conduction"]["keyhole"], 1)
        self.assertEqual(c["n"], 6)
        self.assertAlmostEqual(c["accuracy"], 4 / 6)
        k = c["keyholeOnly"]
        self.assertEqual((k["tp"], k["fp"], k["fn"], k["tn"]), (2, 1, 1, 2))
        self.assertAlmostEqual(k["precision"], 2 / 3)
        self.assertAlmostEqual(k["recall"], 2 / 3)


class SelectionTests(unittest.TestCase):
    def test_rung_choice_ignores_held_out_measurements(self):  # T-SEL-1
        train = rows_for("A", 40, 0.55, 0.50, noise=0.03, seed=1) + rows_for("B", 40, 0.55, 0.50, noise=0.03, seed=2)
        held_a = rows_for("H", 30, 0.55, 0.50, seed=3)
        held_b = rows_for("H", 30, 0.20, 0.90, offset_w=0.7, offset_d=-0.7, seed=4)  # wildly different measurements
        # same keys (the generator is deterministic in the inputs), different measured values
        fk_a = fk_for(train + held_a)
        fk_b = fk_for(train + held_b)
        idx = np.flatnonzero(fk_a.source_idx != fk_a.sources.index("H"))
        for q in ("width", "depth"):
            self.assertEqual(cl.select_rung(fk_a, idx, q, CFG_SMALL, 0.42), cl.select_rung(fk_b, idx, q, CFG_SMALL, 0.42))

    def test_joint_eta_that_improves_width_by_accident_is_not_served(self):  # T-SEL-2
        # Width rows flagged as balling are excluded from the width fit (so eta_W stays at the default and does not
        # improve width) while depth, which uses every row, drags the joint eta upward; the balling rows' width happens
        # to like the higher joint eta, so the joint rung would "improve" width by accident.
        rng = random.Random(7)
        rows = rows_for("A", 60, 0.42, 0.90, seed=1)
        for r in rows:
            if rng.random() < 0.85:
                r["balling"] = 1
                r["width_um"] = sy.synth_geometry(0.90, r["power_W"], r["speed_mm_s"], r["beamDiameter_um"])[0]
        fk = fk_for(rows)
        idx = np.arange(len(rows))
        sel = cl.select_rung(fk, idx, "width", CFG_SMALL, 0.42)
        gain = sel["innerRelativeGain"]
        self.assertGreater(gain["eta"], CFG_SMALL["rungMarginRel"], "the accidental joint improvement must exist for this test to bite")
        self.assertLessEqual(gain["eta2"], CFG_SMALL["rungMarginRel"])
        self.assertNotEqual(sel["rung"], "eta")
        self.assertEqual(sel["rung"], "default")
        self.assertFalse(sel["eligible"]["eta"])


class LeakTests(unittest.TestCase):
    def test_s_source_never_uses_the_held_out_source_or_a_theta_fitted_with_it(self):  # T-LEAK-4
        rows = (rows_for("A", 30, 0.5, 0.5, seed=1) + rows_for("B", 30, 0.55, 0.55, seed=2) +
                sy.synth_rows("C", "Other", 30, 0.45, 0.45, 0.40, seed=3) + sy.synth_rows("D", "Other", 30, 0.5, 0.5, 0.40, seed=4))
        cfg = copy.deepcopy(CFG_SMALL)
        cfg["materialDefaults"]["Other"] = 0.40
        cfg["dataRoles"]["trainable"] = ["A", "B", "C", "D"]
        fk = fk_for(rows)
        seen_pools = []
        original = st.fit_ladder

        def spy(fk_, idx, *a, **k):
            seen_pools.append(set(fk_.sources[s] for s in np.unique(fk_.source_idx[np.asarray(idx)])))
            return original(fk_, idx, *a, **k)

        st.fit_ladder = spy
        try:
            train = np.flatnonzero(np.isin(fk.source_idx, [fk.sources.index("B"), fk.sources.index("C"), fk.sources.index("D")]))
            ip = cl.interval_params(fk, train, "eta2", "width", cfg, 0.42, exclude_sources=["A"])
        finally:
            st.fit_ladder = original
        self.assertNotIn("A", ip["sourceMeanResiduals"])
        self.assertTrue(all("A" not in pool for pool in seen_pools), seen_pools)
        # the residual of the other source of the held-out source's alloy (B) must come from a theta fitted without A and B
        # (nothing is left: default eta), so it equals the default-rung residual
        pd_, ok = st.predict_rung(fk, fk.subset_idx(source="B"), "default", None, "width")
        expect = float(np.mean(fk.lnWm[fk.subset_idx(source="B")][ok] - np.log(pd_[ok])))
        self.assertAlmostEqual(ip["sourceMeanResiduals"]["B"], expect, places=9)


class UnresolvedTests(unittest.TestCase):
    def test_unresolved_rows_are_counted_and_score_as_failures(self):  # T-UNRES-1
        rows = rows_for("A", 40, 0.55, 0.55, seed=1)
        fk = fk_for(rows)
        eta_hi = fk.eta >= 0.5
        fk.ok[:1, :] = np.where(eta_hi[None, :], False, fk.ok[:1, :])  # 1 of 40 rows (2.5 %, under the 5 % floor) is unresolved at the fitted eta
        fit = st.fit_ladder(fk, np.arange(len(rows)), CFG_SMALL, 0.42)
        ev = cl.evaluate_rungs(fk, np.arange(len(rows)), np.arange(len(rows)), fit, "eta2", "width", CFG_SMALL, with_powerlaw=False)
        r = ev["rungs"]["eta2"]
        self.assertGreaterEqual(r["unresolved"], 1)
        self.assertEqual(ev["rungs"]["default"]["unresolved"], 0)
        self.assertGreater(r["mapeUnresolvedAsFail"], r["metrics"]["mapePct"])
        pred = np.array([100.0, 100.0, 100.0])
        meas = np.array([100.0, 100.0, 100.0])
        self.assertAlmostEqual(st.mape_unresolved_as_fail(pred, meas, np.array([True, True, False])), 100.0 / 3)


class ConsistencyTests(unittest.TestCase):
    def test_two_sources_with_opposite_offsets_are_rejected_for_source_dependent_eta(self):  # T-CONS-1
        rows = rows_for("A", 40, 0.30, 0.30, noise=0.02, seed=1) + rows_for("B", 40, 0.70, 0.70, noise=0.02, seed=2)
        fk = fk_for(rows)
        res = cl.analyze_kernel_alloy(fk, ALLOY, CFG_SMALL)
        for q in ("width", "depth"):
            cell = res["cells"][q]
            self.assertIs(cell["etaConsistent"], False)
            self.assertEqual(cell["gate"]["status"], "rejected")
            self.assertIn("sourceDependentEta", cell["gate"]["reasons"])


if __name__ == "__main__":
    unittest.main()
