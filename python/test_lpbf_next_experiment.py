"""Offline tests for the next-experiment proposal (stub solver, stub training rows; no frozen-physics run).
Screening: experiment proposal; not a print recommendation."""

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lpbf_calibration_layer as layer  # noqa: E402
import lpbf_next_experiment as ne  # noqa: E402

MATERIAL = "316L Stainless Steel"
SCALES = {"eagar-tsai": 0.0, "goldak": 0.4, "rosenthal": 0.8}


def stub_solver(unresolved_above_speed=None):
    """Kernel disagreement grows with power: kernel k scales W and D by exp(a_k * (P / 400)^2)."""
    def solver(args, kernel, eta):
        _, P, v, d = args[0], args[1], args[2], args[3]
        if unresolved_above_speed is not None and v > unresolved_above_speed and kernel != "rosenthal":
            return None, None, "heuristic-width-fallback"
        base_w = 80.0 * math.sqrt(P / v) * 10.0
        f = math.exp(SCALES[kernel] * (P / 400.0) ** 2)
        return base_w * f, 0.5 * base_w * f ** 1.3, "computed"
    return solver


def regime_stub(material, P, v, spot, preheat):
    return "conduction"


def no_training(material):
    return []


def spec(**over):
    s = {"material": MATERIAL, "power_W": [100.0, 400.0], "speed_mm_s": [400.0, 1600.0], "spots_um": [100.0],
         "layer_um": 40.0, "preheat_C": 80.0, "n": 6, "seed": 3, "plate": {"x_mm": 150.0, "y_mm": 100.0},
         "grid": 5}
    s.update(over)
    return s


def plan(**over):
    kw = {"calibration": None, "solver_call": stub_solver(), "training_loader": no_training, "regime_fn": regime_stub}
    kw.update({k: over.pop(k) for k in list(kw) if k in over})
    return ne.plan_experiment(spec(**over), **kw)


def enabled_calib():
    return {"calibrationId": "stub", "contentSha256": "a" * 64, "configSha256": "b" * 64, "implementationHash": "c" * 64,
            "cells": [{"kernel": "goldak", "material": MATERIAL, "quantity": "width", "status": "enabled",
                       "interval": {"m": 0.0, "sWithin": 0.1, "sSource": 0.1, "levels": [0.8, 0.9]}}]}


def seg_distance(a, b):
    """Distance between two horizontal segments (x0, x1, y)."""
    dx = max(0.0, max(a[0], b[0]) - min(a[1], b[1]))
    return math.hypot(dx, abs(a[2] - b[2]))


class NextExperimentTests(unittest.TestCase):
    def test_deterministic_for_a_seed_and_seed_only_moves_the_layout(self):
        a, b = plan(), plan()
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        c = plan(seed=4)
        key = lambda p: [(q["trackId"], q["power_W"], q["speed_mm_s"], q["beamDiameter_um"]) for q in p["points"]]
        self.assertEqual(key(a), key(c))
        self.assertNotEqual([q["layout"] for q in a["points"]], [q["layout"] for q in c["points"]])

    def test_n_distinct_points_within_limits(self):
        p = plan(n=20, spots_um=[60.0, 100.0], grid=6)
        self.assertEqual(len(p["points"]), 20)
        keys = {(q["power_W"], q["speed_mm_s"], q["beamDiameter_um"]) for q in p["points"]}
        self.assertEqual(len(keys), 20)
        from lpbf_simulation import BOUNDS
        for q in p["points"]:
            self.assertTrue(BOUNDS["power_W"][0] <= q["power_W"] <= BOUNDS["power_W"][1])
            self.assertTrue(100.0 <= q["power_W"] <= 400.0 and 400.0 <= q["speed_mm_s"] <= 1600.0)
            self.assertIn(q["beamDiameter_um"], (60.0, 100.0))
        self.assertLessEqual(p["candidates"]["total"], 15 * 15 * 2)
        self.assertEqual(p["label"], "Screening: experiment proposal; not a print recommendation")
        self.assertEqual(p["evidenceKind"], "screening-only")
        self.assertEqual(p["schema"], "lpbf-next-experiment-plan-1")

    def test_plate_spacing_rule_and_random_order(self):
        for spots in ([100.0], [100.0, 400.0]):
            p = plan(n=12, spots_um=spots, plate={"x_mm": 200.0, "y_mm": 200.0})
            need = max(3.0, 10.0 * max(spots) / 1000.0)
            self.assertAlmostEqual(p["plate"]["pitch_mm"], need)
            segs = [(q["layout"]["x_start_mm"], q["layout"]["x_end_mm"], q["layout"]["y_mm"]) for q in p["points"]]
            for i in range(len(segs)):
                for j in range(i + 1, len(segs)):
                    self.assertGreaterEqual(seg_distance(segs[i], segs[j]) + 1e-9, need)
            for s in segs:  # inside the plate with the edge margin
                self.assertTrue(0 <= s[0] and s[1] <= 200.0 and 0 <= s[2] <= 200.0)
            self.assertEqual(sorted(q["layout"]["printOrder"] for q in p["points"]), list(range(1, 13)))
        orders = {tuple(q["layout"]["printOrder"] for q in plan(n=12, seed=s)["points"]) for s in range(5)}
        self.assertGreater(len(orders), 1, "the seed must change the random plate order")

    def test_first_pick_lands_in_the_high_disagreement_region(self):
        p = plan(n=4)
        self.assertGreaterEqual(p["points"][0]["power_W"], 300.0)
        d = [q["score"]["disagreement"]["raw"] for q in p["points"]]
        self.assertGreater(d[0], 0)
        self.assertGreaterEqual(max(d), d[0] * 0.999)

    def test_gaussian_down_weight_spreads_the_batch(self):
        p = plan(n=5, grid=7)
        pts = [(math.log(q["power_W"]), math.log(q["speed_mm_s"])) for q in p["points"]]
        self.assertGreater(len({pt for pt in pts}), 4)

    def test_no_interval_cell_gives_null_and_says_so(self):
        p = plan(calibration={"calibrationId": "x", "contentSha256": "0" * 64, "configSha256": "0" * 64,
                              "implementationHash": "0" * 64, "cells": []})
        self.assertIsNone(p["intervalWidth"]["lnHiOverLo"])
        self.assertIn("null", p["intervalWidth"]["note"])
        for q in p["points"]:
            self.assertIsNone(q["score"]["intervalWidth"]["lnHiOverLo"])
            self.assertIn("no enabled calibration cell", q["score"]["intervalWidth"]["note"])
        q = plan(calibration=enabled_calib())
        want = math.log(math.exp(1.6449 * math.sqrt(0.02)) / math.exp(-1.6449 * math.sqrt(0.02)))
        self.assertAlmostEqual(q["intervalWidth"]["lnHiOverLo"], want, places=5)
        self.assertEqual(q["calibration"]["contentSha256"], "a" * 64)

    def test_plan_records_config_and_calibration_shas(self):
        p = plan(calibration=enabled_calib())
        self.assertEqual(p["configSha256"], ne.next_experiment_config_sha256())
        self.assertEqual(len(p["configSha256"]), 64)
        self.assertEqual(p["calibration"]["configSha256"], "b" * 64)
        none = plan()
        self.assertFalse(none["calibration"]["available"])

    def test_real_artefact_is_read_and_hashed(self):
        try:
            art = layer.load_calibration()
        except layer.CalibrationError:
            self.skipTest("committed artefact not loadable on this checkout")
        p = plan(calibration="default")
        self.assertEqual(p["calibration"]["contentSha256"], art["contentSha256"])

    def test_candidates_with_fewer_than_two_resolved_kernels_are_excluded_and_counted(self):
        p = plan(solver_call=stub_solver(unresolved_above_speed=1000.0), n=4)
        self.assertGreater(p["candidates"]["excluded"]["fewerThanTwoKernelsResolved"], 0)
        for q in p["points"]:
            self.assertLessEqual(q["speed_mm_s"], 1000.0)
            self.assertGreaterEqual(q["score"]["disagreement"]["nResolvedKernels"], 2)

    def test_coverage_prefers_points_far_from_training_and_existing_points(self):
        train = [{"power_W": 400.0, "speed_mm_s": 400.0, "beamDiameter_um": 100.0, "regimeClass": "conduction",
                  "source": "s", "material": MATERIAL}]
        base = plan(n=1, training_loader=lambda m: train)
        self.assertEqual(base["candidates"]["trainingPoints"], 1)
        c = base["points"][0]["score"]["coverage"]
        self.assertTrue(c["classUnderCovered"])
        self.assertIsNotNone(c["nearestDistanceStd"])
        ex = plan(n=1, existing=[{"power_W": base["points"][0]["power_W"], "speed_mm_s": base["points"][0]["speed_mm_s"],
                                  "beamDiameter_um": 100.0}], training_loader=lambda m: train)
        self.assertEqual(ex["candidates"]["existingPoints"], 1)
        self.assertNotEqual((ex["points"][0]["power_W"], ex["points"][0]["speed_mm_s"]),
                            (base["points"][0]["power_W"], base["points"][0]["speed_mm_s"]))

    def test_refuses_missing_plate_size_and_n_out_of_range(self):
        for plate in (None, {}, {"x_mm": 100.0}, {"x_mm": 100.0, "y_mm": 0.0}):
            with self.assertRaises(ne.PlanError):
                plan(plate=plate)
        for n in (0, 49, -1, 2.5, True):
            with self.assertRaises(ne.PlanError):
                plan(n=n)
        with self.assertRaises(ne.PlanError):
            plan(n=48, grid=3)  # 9 candidates cannot give 48 distinct points

    def test_refuses_out_of_bounds_inputs_and_a_too_small_plate(self):
        with self.assertRaises(ne.PlanError):
            plan(power_W=[5.0, 400.0])
        with self.assertRaises(ne.PlanError):
            plan(spots_um=[10.0])
        with self.assertRaises(ne.PlanError):
            plan(speed_mm_s=[1600.0, 400.0])
        with self.assertRaises(ne.PlanError) as cm:
            plan(n=30, grid=7, spots_um=[60.0, 100.0], plate={"x_mm": 30.0, "y_mm": 30.0})
        self.assertIn("too small", str(cm.exception))

    def test_outputs_are_written_and_the_template_has_blank_measurement_cells(self):
        p = plan(n=5)
        d = Path(tempfile.mkdtemp())
        paths = ne.write_outputs(p, d)
        self.assertEqual(sorted(paths), ["measurement_template.csv", "plan.json", "plate_layout.csv",
                                         "plate_layout.svg", "print_plan.csv"])
        tpl = (d / "measurement_template.csv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(tpl[0], "track_id,power_W,speed_mm_s,spot_um,width_um,depth_um,notes")
        self.assertEqual(len(tpl), 6)
        self.assertTrue(all(r.endswith(",,,") for r in tpl[1:]))
        self.assertIn("<svg", (d / "plate_layout.svg").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((d / "plan.json").read_text(encoding="utf-8"))["schema"], ne.PLAN_SCHEMA)

    def test_the_module_never_edits_the_frozen_physics_or_the_calibration_stack(self):
        text = Path(ne.__file__).read_text(encoding="utf-8")
        self.assertNotIn("IMPLEMENTATION_SOURCE_FILES", text)
        from lpbf_simulation import IMPLEMENTATION_SOURCE_FILES
        self.assertNotIn("lpbf_next_experiment.py", IMPLEMENTATION_SOURCE_FILES)
        self.assertNotIn("lpbf_user_measurements.py", IMPLEMENTATION_SOURCE_FILES)


if __name__ == "__main__":
    unittest.main()
