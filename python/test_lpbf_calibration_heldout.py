"""Offline tests for tools/lpbf_calibration_heldout.py.

A tiny synthetic fixture and a synthetic kernel stand in for the datasets and the solver: no dataset file,
no lpbf_thermal_solver import, no Warp. The statistics (grouped split, grid fit, power-law baseline, held-out
metrics, paired bootstrap, verdicts, document and markdown) are exercised end to end.
"""

import json
import math
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))

import lpbf_calibration_heldout as cal  # noqa: E402

TRUE_A = {"SynthA": 0.50, "SynthB": 0.60}
DEFAULT_A = {"SynthA": 0.40, "SynthB": 0.35}
MIN_RESOLVED_A = 0.24  # the synthetic kernel does not resolve an extent below this absorptivity


def synth_kernel_geometry(a, power_W, speed_mm_s, beam_um):
    """A smooth stand-in: W ~ sqrt(a P / v) d^0.3, D ~ W * (a/0.5)^0.5 (um)."""
    w = 400.0 * math.sqrt(a * power_W / speed_mm_s) * (beam_um / 50.0) ** 0.3
    d = 0.6 * w * math.sqrt(a / 0.5)
    return w, d


def synth_kernel(task):
    row, a = task["row"], task["a"]
    w, d = synth_kernel_geometry(a, row["power_W"], row["speed_mm_s"], row["beamDiameter_um"])
    ok = a >= MIN_RESOLVED_A
    return {"width_um": round(w, 3), "depth_um": round(d, 3), "included": ok,
            "extentStatus": "computed" if ok else "heuristic-width-fallback", "fallbackWarnings": 1}


def _class(power_W, speed_mm_s):
    ratio = power_W / speed_mm_s
    return "conduction" if ratio < 0.15 else ("transition" if ratio < 0.3 else "keyhole")


def make_rows(dataset, material, powers, speeds, beams, replicate_every=0, noise=0.05, seed=1, balling_every=0):
    rng = random.Random(seed)
    rows = []
    i = 0
    for p in powers:
        for v in speeds:
            for d in beams:
                reps = 2 if (replicate_every and i % replicate_every == 0) else 1
                for rep in range(reps):
                    w, dd = synth_kernel_geometry(TRUE_A[material], p, v, d)
                    w *= 1.0 + rng.uniform(-noise, noise)
                    dd *= 1.0 + rng.uniform(-noise, noise)
                    i += 1
                    c = _class(p, v)
                    label = "balling-flagged" if (balling_every and i % balling_every == 0) else c
                    rows.append({"dataset": dataset, "rowId": f"{dataset}-{i:03d}", "material": material,
                                 "power_W": float(p), "speed_mm_s": float(v), "beamDiameter_um": float(d),
                                 "layer_um": 30.0 if rep == 0 else 60.0, "preheat_C": 20.0, "hatch_um": None,
                                 "width_um": w, "depth_um": dd, "balling": int(label == "balling-flagged"),
                                 "regimeClass": c, "regimeLabel": label, "defaultAbsorptivity": DEFAULT_A[material]})
    return rows


def fixture():
    rows_a = make_rows("synth-a", "SynthA", (100, 150, 200, 250, 300), (500, 750, 1000, 1250, 1500), (50, 80),
                       replicate_every=4, balling_every=9)
    rows_b = make_rows("synth-b", "SynthB", (100, 200, 300, 400), (500, 1000, 1500, 2000), (50,), seed=2)
    grid = cal.absorptivity_grid(set(DEFAULT_A.values()))
    table = cal.build_table(rows_a + rows_b, grid, jobs=1, kernel=synth_kernel)
    return rows_a, rows_b, table


class SplitTests(unittest.TestCase):
    def test_grouped_kfold_keeps_sets_together_and_is_deterministic(self):
        rows_a, _, _ = fixture()
        folds = cal.grouped_kfold(rows_a, 5, seed=0)
        self.assertEqual(len(folds), 5)
        seen = []
        for train, test in folds:
            cal.assert_no_leak(train, test)
            self.assertEqual(len(train) + len(test), len(rows_a))
            seen += [r["rowId"] for r in test]
        self.assertEqual(sorted(seen), sorted(r["rowId"] for r in rows_a))  # every row tested exactly once
        again = cal.grouped_kfold(rows_a, 5, seed=0)
        self.assertEqual([[r["rowId"] for r in t] for _, t in folds], [[r["rowId"] for r in t] for _, t in again])
        other = cal.grouped_kfold(rows_a, 5, seed=1)
        self.assertNotEqual([[r["rowId"] for r in t] for _, t in folds], [[r["rowId"] for r in t] for _, t in other])

    def test_replicates_share_a_fold(self):
        rows_a, _, _ = fixture()
        keys = {}
        for r in rows_a:
            keys.setdefault(cal.set_key(r), []).append(r["rowId"])
        rep_sets = [ids for ids in keys.values() if len(ids) > 1]
        self.assertGreater(len(rep_sets), 0)
        for _, test in cal.grouped_kfold(rows_a, 3, seed=0):
            test_ids = {r["rowId"] for r in test}
            for ids in rep_sets:
                inside = sum(1 for i in ids if i in test_ids)
                self.assertIn(inside, (0, len(ids)))

    def test_leak_assertion_fires(self):
        rows_a, _, _ = fixture()
        with self.assertRaises(AssertionError):
            cal.assert_no_leak(rows_a[:3], rows_a[:3])


class FitTests(unittest.TestCase):
    def test_constant_fit_recovers_the_generating_absorptivity(self):
        rows_a, rows_b, table = fixture()
        fa = cal.fit_constant(rows_a, table)
        fb = cal.fit_constant(rows_b, table)
        self.assertAlmostEqual(fa["a"], TRUE_A["SynthA"], places=6)
        self.assertAlmostEqual(fb["a"], TRUE_A["SynthB"], places=6)
        self.assertFalse(fa["atGridEdge"])
        self.assertEqual(fa["coverage"], 1.0)
        self.assertLess(fa["trainLoss"], 0.05)

    def test_coverage_floor_rejects_unresolved_grid_values(self):
        rows_a, _, table = fixture()
        curve = cal.fit_constant(rows_a, table)["lossCurve"]
        self.assertIsNone(curve[cal.a_key(0.20)]["loss"])
        self.assertEqual(curve[cal.a_key(0.20)]["coverage"], 0.0)
        self.assertIsNotNone(curve[cal.a_key(0.24)]["loss"])

    def test_regime_fit_falls_back_for_thin_classes(self):
        rows_a, _, table = fixture()
        fit = cal.fit_regime(rows_a, table, min_sets=8)
        n_sets = {c: len({cal.set_key(r) for r in rows_a if r["regimeClass"] == c}) for c in cal.CLASSES}
        for c in cal.CLASSES:
            self.assertEqual(fit["classes"][c]["fellBackToConst"], n_sets[c] < 8, c)
            self.assertAlmostEqual(fit["classes"][c]["a"], TRUE_A["SynthA"], places=6)

    def test_power_law_exact_recovery_and_constant_feature_drop(self):
        rows = []
        for i, (p, v, d) in enumerate([(100, 500, 50), (200, 500, 80), (300, 1000, 50), (150, 1500, 80), (250, 750, 110)]):
            w = math.exp(1.0) * p ** 0.5 * v ** -0.4 * d ** 0.3
            rows.append({"dataset": "x", "rowId": f"x{i}", "material": "M", "power_W": p, "speed_mm_s": v,
                         "beamDiameter_um": d, "width_um": w, "depth_um": 2 * w})
        m = cal.fit_power_law(rows, "width_um")
        self.assertAlmostEqual(m["intercept"], 1.0, places=6)
        self.assertAlmostEqual(m["exponents"]["power_W"], 0.5, places=6)
        self.assertAlmostEqual(m["exponents"]["speed_mm_s"], -0.4, places=6)
        self.assertAlmostEqual(m["exponents"]["beamDiameter_um"], 0.3, places=6)
        self.assertAlmostEqual(cal.predict_power_law(m, rows[2]), rows[2]["width_um"], places=6)
        for r in rows:
            r["beamDiameter_um"] = 50.0
        m2 = cal.fit_power_law(rows, "depth_um")
        self.assertEqual(m2["droppedConstantFeatures"], ["beamDiameter_um"])
        self.assertNotIn("beamDiameter_um", m2["exponents"])


class MetricTests(unittest.TestCase):
    @staticmethod
    def _rows():
        return [{"rowId": "r1", "material": "M", "power_W": 100.0, "speed_mm_s": 500.0, "beamDiameter_um": 50.0,
                 "width_um": 100.0, "depth_um": 50.0, "regimeLabel": "conduction"},
                {"rowId": "r2", "material": "M", "power_W": 200.0, "speed_mm_s": 500.0, "beamDiameter_um": 50.0,
                 "width_um": 200.0, "depth_um": 100.0, "regimeLabel": "keyhole"},
                {"rowId": "r3", "material": "M", "power_W": 300.0, "speed_mm_s": 500.0, "beamDiameter_um": 50.0,
                 "width_um": 100.0, "depth_um": 100.0, "regimeLabel": "keyhole"}]

    def test_hand_computed_metrics_and_skill(self):
        rows = self._rows()
        preds = {"default": [{"rowId": "r1", "width_um": 110.0, "depth_um": 40.0, "included": True},
                             {"rowId": "r2", "width_um": 160.0, "depth_um": 150.0, "included": True},
                             {"rowId": "r3", "width_um": 50.0, "depth_um": 100.0, "included": False}],
                 "const": [{"rowId": "r1", "width_um": 105.0, "depth_um": 45.0, "included": True},
                           {"rowId": "r2", "width_um": 190.0, "depth_um": 110.0, "included": True},
                           {"rowId": "r3", "width_um": 100.0, "depth_um": 100.0, "included": True}]}
        ev = cal.evaluate(rows, preds, replicates=0)
        self.assertEqual((ev["n"], ev["nExcluded"], ev["n_parameterSets"]), (2, 1, 2))  # r3 dropped for every model
        d = ev["models"]["default"]
        self.assertAlmostEqual(d["width"]["bias_pct"], 100 * (0.10 - 0.20) / 2)
        self.assertAlmostEqual(d["width"]["mape_pct"], 15.0)
        self.assertAlmostEqual(d["width"]["mae_um"], 25.0)
        self.assertAlmostEqual(d["depth"]["mape_pct"], 35.0)
        self.assertAlmostEqual(d["depth"]["rmse_um"], math.sqrt((100 + 2500) / 2))
        c = ev["models"]["const"]
        self.assertAlmostEqual(c["width"]["mape_pct"], 5.0)
        self.assertAlmostEqual(c["skillVs_default"]["width"]["mape"], 1 - 5.0 / 15.0)
        self.assertAlmostEqual(c["skillVs_default"]["width"]["mae"], 1 - 7.5 / 25.0)
        self.assertNotIn("skillVs_const", c)

    def test_bootstrap_intervals_contain_the_point_estimate_and_are_paired(self):
        rows = self._rows()
        preds = {"default": [{"rowId": r["rowId"], "width_um": r["width_um"] * 1.2, "depth_um": r["depth_um"] * 0.8, "included": True} for r in rows],
                 "powerlaw": [{"rowId": r["rowId"], "width_um": r["width_um"] * 1.1, "depth_um": r["depth_um"] * 1.3, "included": True} for r in rows],
                 "const": [{"rowId": r["rowId"], "width_um": r["width_um"] * 1.05, "depth_um": r["depth_um"] * 0.9, "included": True} for r in rows]}
        ev = cal.evaluate(rows, preds, replicates=300, seed=3)
        for m in preds:
            for q in ("width", "depth"):
                st = ev["models"][m][q]
                for name in ("bias_pct", "mae_um", "mape_pct"):
                    lo, hi = st[f"{name}_ci95"]
                    self.assertLessEqual(lo, st[name] + 1e-9)
                    self.assertGreaterEqual(hi, st[name] - 1e-9)
        # a uniform 5 % width error vs a uniform 20 % one: the paired skill is exactly 0.75 in every resample
        sk = ev["models"]["const"]["skillVs_default"]["width"]
        self.assertAlmostEqual(sk["mape"], 0.75)
        self.assertAlmostEqual(sk["mape_ci95"][0], 0.75, places=9)
        self.assertAlmostEqual(sk["mape_ci95"][1], 0.75, places=9)
        v = cal.verdicts(ev)
        self.assertEqual(v["const vs default (width)"]["verdict"], "beats")
        self.assertEqual(v["const vs powerlaw (depth)"]["verdict"], "beats")      # 10 % vs 30 %
        self.assertEqual(v["const vs default (depth)"]["verdict"], "beats")       # 10 % vs 20 %
        self.assertEqual(v["default vs powerlaw (width)"]["verdict"], "does not beat")  # 20 % vs 10 %
        self.assertTrue(all(len(x["ci95"]) == 2 for x in v.values()))


class EndToEndOfflineTests(unittest.TestCase):
    def test_document_and_markdown_without_datasets_or_solver(self):
        rows_a, rows_b, table = fixture()
        self.assertNotIn("lpbf_thermal_solver", sys.modules)
        self.assertEqual(table["solverCalls"], len(table["grid"]) * (len(rows_a) + len(rows_b)))
        meta = {"datasets": [{"id": "synth-a", "doi": "-", "license": "-", "url": "-", "tableSha256": "-", "rows": len(rows_a),
                              "material": "SynthA", "citation": "synthetic"},
                             {"id": "synth-b", "doi": "-", "license": "-", "url": "-", "tableSha256": "-", "rows": len(rows_b),
                              "material": "SynthB", "citation": "synthetic"}],
                "regimeRule": "synthetic P/v thresholds"}
        doc = cal.assemble_document(rows_a, rows_b, meta, table, "0" * 64, "2026-01-01", False, replicates=40, seeds=(0, 1))
        self.assertNotIn("lpbf_thermal_solver", sys.modules)
        json.dumps(doc)  # serialisable
        self.assertFalse(doc["evidence"]["experimentalValidation"])
        self.assertFalse(doc["evidence"]["opticalOperatorMatched"])
        self.assertTrue(doc["evidence"]["label"].startswith("Calibrated simulation"))
        self.assertEqual(sorted(doc["crossValidation"]), ["synth-a", "synth-b"])
        cv = doc["crossValidation"]["synth-a"]["bySeed"]["0"]
        self.assertTrue(cv["primary"])
        self.assertEqual(len(cv["folds"]), cal.K_FOLDS)
        self.assertEqual(len(cv["outOfFoldPredictions"]["const"]), len(rows_a))
        for f in cv["folds"]:
            self.assertAlmostEqual(f["fits"]["const"]["a"], TRUE_A["SynthA"], places=6)
        # the synthetic measurements were generated at a = 0.50 with 5 % noise: const must beat the default (0.40)
        self.assertEqual(doc["verdicts"]["cv"]["synth-a"]["const vs default (width)"]["verdict"], "beats")
        lodo = doc["leaveOneDatasetOut"]["train=synth-a;test=synth-b"]
        self.assertTrue(lodo["crossMaterial"])
        self.assertAlmostEqual(lodo["fits"]["const"]["a"], TRUE_A["SynthA"], places=6)  # 0.50 carried into SynthB
        self.assertIn("cross-material transfer", lodo["note"])
        self.assertEqual(doc["inSampleReference"]["synth-b"]["fits"]["const"]["a"], TRUE_A["SynthB"])
        self.assertIn("balling-flagged", cv["byRegimeLabel"])
        self.assertEqual(doc["counts"]["hofmannRows"], len(rows_a))
        self.assertGreater(doc["counts"]["hofmannRows"], doc["counts"]["hofmannSets_P_v_d"])  # replicates exist
        md = cal.render_markdown(doc)
        self.assertIn("not experimental validation", md)
        self.assertIn("## What this does not show", md)
        self.assertIn("`experimentalValidation` = false", md)
        self.assertIn("cross-material transfer", md)
        low = md.lower()
        self.assertNotIn("validated", low)
        self.assertNotIn("predictive", low)
        self.assertNotIn("lpbf_thermal_solver", sys.modules)


if __name__ == "__main__":
    unittest.main()
