"""Offline tests for lpbf_machine_calibration.py (synthetic solver and synthetic user rows: no dataset, no frozen-physics
run, no GPU). SCREENING ONLY, NOT VALIDATION."""

import ast
import contextlib
import copy
import importlib.util
import io
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lpbf_machine_calibration as mc  # noqa: E402
import lpbf_machine_calibration_config as mcfg  # noqa: E402
import lpbf_simulation  # noqa: E402

PYTHON_DIR = Path(__file__).resolve().parent
REPO_ROOT = PYTHON_DIR.parent
MAT = "316L Stainless Steel"
IMPL = "b" * 64
FULL_METHOD = {"depthDatum": "plate surface", "beamDiameterDefinition": "D4sigma", "measuredPowerW": 198.0,
               "crossSectionLocation": "track mid-length", "replicates": 3}

# (P, v, d): spread over the three regimes of the synthetic enthalpy h = 20 * (P/200) * (900/v)
TRACKS = [(120.0, 1200.0, 80.0), (150.0, 1500.0, 80.0), (180.0, 1000.0, 80.0), (200.0, 900.0, 80.0),
          (240.0, 800.0, 80.0), (280.0, 700.0, 80.0), (320.0, 600.0, 80.0), (360.0, 650.0, 80.0)]


def synth_depth(P, v, d):
    return 100.0 * (P / 200.0) ** 0.9 * (900.0 / v) ** 0.5


def synth_enthalpy(P, v, d):
    return 20.0 * (P / 200.0) * (900.0 / v)


def fake_solver(args, kernel):
    _m, P, v, d, _pre, _layer, _hatch = args
    return 0.9 * synth_depth(P, v, d), synth_depth(P, v, d), "computed", synth_enthalpy(P, v, d)


def user_doc(factor_fn, tracks=TRACKS, method=FULL_METHOD, material=MAT, noise=None):
    """User rows whose measured depth is factor_fn(P, v, d, h) * (1 + noise_i) * the synthetic default depth."""
    rows = []
    for i, (P, v, d) in enumerate(tracks):
        h = synth_enthalpy(P, v, d)
        eps = 0.0 if noise is None else noise[i % len(noise)]
        depth = synth_depth(P, v, d) * factor_fn(P, v, d, h) * math.exp(eps)
        r = {"rowId": f"user-test-t{i}", "trackId": f"t{i}", "source": "user-test", "material": material,
             "power_W": P, "speed_mm_s": v, "beamDiameter_um": d, "preheat_C": 20.0, "layer_um": 30.0, "hatch_um": None,
             "width_um": 0.9 * depth, "depth_um": depth, "balling": None, "publishedLabel": None, "catalog": False,
             "label": mc.ROW_LABEL}
        if method is not None:
            r["method"] = dict(method)
        rows.append(r)
    return {"schema": mc.ROWS_SCHEMA, "sourceId": "user-test", "label": mc.ROW_LABEL, "evidenceKind": "screening-only",
            "material": material, "provenance": {"planSha256": "p" * 64}, "nRows": len(rows), "nExcluded": 0,
            "rows": rows, "excluded": []}


def depth_cell(doc, kernel="rosenthal"):
    fit = mc.fit_machine(doc, solver_call=fake_solver)
    return next(c for c in fit["cells"] if c["kernel"] == kernel and c["quantity"] == "depth")


UNIFORM = lambda P, v, d, h: math.exp(-0.5)  # noqa: E731  planted c* = -0.5 (default over-predicts by 65 %)
NOISE = [0.03, -0.03, 0.02, -0.02]


class RecoveryAndBand(unittest.TestCase):
    def test_planted_factor_recovered(self):  # SPEC case 1
        cell = depth_cell(user_doc(UNIFORM, noise=NOISE))
        self.assertEqual(cell["status"], "served", cell["reasonText"])
        self.assertLess(abs(cell["c"] - (-0.5)), 0.05)
        self.assertLess(abs(cell["factor"] - math.exp(-0.5)), 0.04)
        self.assertGreater(cell["gate"]["looSkill"], 0.0)
        lo, hi = cell["band"]["factors"]
        self.assertLessEqual(lo, math.exp(-0.5) / cell["factor"])
        self.assertGreaterEqual(hi, math.exp(-0.5) / cell["factor"])
        self.assertLessEqual(cell["cCi90"][0], cell["c"])
        self.assertGreaterEqual(cell["cCi90"][1], cell["c"])

    def test_t_quantile_matches_tables(self):
        for df, want in ((3, 1.6377), (5, 1.4759), (9, 1.3830), (10, 1.3722)):
            self.assertAlmostEqual(mc.t_ppf(0.90, df), want, places=3)

    def test_grid_fit_uses_prior_and_ties_to_smaller_c(self):
        c, _ = mc.fit_c([0.0, 0.0, 0.0, 0.0])
        self.assertEqual(c, 0.0)
        c2, _ = mc.fit_c([0.6] * 5)
        self.assertAlmostEqual(c2, 0.6, places=6)

    def test_nuisance_is_a_factor_not_an_absorptivity(self):
        cell = depth_cell(user_doc(UNIFORM, noise=NOISE))
        self.assertAlmostEqual(cell["factor"], math.exp(cell["c"]), places=12)
        self.assertNotIn("eta", json.dumps(cell).lower().replace("beta", ""))


class Eligibility(unittest.TestCase):
    def test_only_rosenthal_316l_depth_is_eligible(self):
        fit = mc.fit_machine(user_doc(UNIFORM, noise=NOISE), solver_call=fake_solver)
        by = {(c["kernel"], c["quantity"]): c for c in fit["cells"]}
        self.assertEqual(by[("rosenthal", "depth")]["status"], "served")
        for key, c in by.items():
            if key != ("rosenthal", "depth"):
                self.assertEqual(c["status"], "not-eligible", key)
                self.assertEqual(c["evidenceKind"], "screening-only")
        self.assertIn("regime-dependent", by[("eagar-tsai", "depth")]["reasonText"][0])
        self.assertIn("regime-dependent", by[("goldak", "depth")]["reasonText"][0])

    def test_ti64_rosenthal_is_not_eligible_even_with_a_perfect_fit(self):  # not-eligible refusal
        doc = user_doc(UNIFORM, material="Ti-6Al-4V")
        cell = depth_cell(doc)
        self.assertEqual(cell["status"], "not-eligible")
        self.assertIn("Ti-6Al-4V", cell["reasonText"][0])
        self.assertIsNone(cell["factor"])

    def test_solver_is_not_called_for_ineligible_cells(self):
        calls = []

        def spy(args, kernel):
            calls.append(kernel)
            return fake_solver(args, kernel)
        mc.fit_machine(user_doc(UNIFORM, noise=NOISE), solver_call=spy)
        self.assertEqual(set(calls), {"rosenthal"})


class GateRefusals(unittest.TestCase):
    def reasons(self, doc):
        return depth_cell(doc)["reasons"]

    def test_too_few_tracks(self):
        self.assertIn("tooFewTracks", self.reasons(user_doc(UNIFORM, tracks=TRACKS[:3])))

    def test_mixed_signs_refused_by_uniform_sign(self):
        doc = user_doc(lambda P, v, d, h: math.exp(0.5 if P < 200 else -0.5) if P != 200 else 1.0, tracks=TRACKS[:6])
        self.assertIn("uniformSign", self.reasons(doc))

    def test_small_offset_refused(self):
        doc = user_doc(lambda P, v, d, h: math.exp(-0.05), noise=NOISE)
        r = self.reasons(doc)
        self.assertIn("offsetTooSmall", r)
        self.assertNotIn("uniformSign", r)

    def test_factor_out_of_range_refused(self):
        doc = user_doc(lambda P, v, d, h: 1.0 / 4.0, noise=NOISE)  # factor 1/4 is outside 1/3..3
        cell = depth_cell(doc)
        self.assertEqual(cell["status"], "refused")
        self.assertIn("factorOutOfRange", cell["reasons"])
        self.assertEqual(cell["evidenceKind"], "screening-only")
        doc_hi = user_doc(lambda P, v, d, h: 4.0, noise=NOISE)
        self.assertIn("factorOutOfRange", self.reasons(doc_hi))

    def test_factor_at_one_third_edge_is_served(self):
        doc = user_doc(lambda P, v, d, h: 0.4, noise=NOISE)
        self.assertEqual(depth_cell(doc)["status"], "served")

    def test_loo_skill_refusal(self):
        g = mc.gate_cell([0.3, 0.3, 0.3, 0.3, 0.3], 0.3, [0.5, 0.5, 0.5, 0.5, 0.5])
        self.assertIn("looSkill", g["reasons"])
        self.assertFalse(g["passed"])

    def test_unresolved_track_refuses(self):
        def solver(args, kernel):
            out = fake_solver(args, kernel)
            return (out[0], out[1], "not-resolved", out[3]) if args[1] == 120.0 else out
        fit = mc.fit_machine(user_doc(UNIFORM, tracks=TRACKS[:4], noise=NOISE), solver_call=solver)
        cell = next(c for c in fit["cells"] if c["kernel"] == "rosenthal" and c["quantity"] == "depth")
        self.assertIn("tooFewTracks", cell["reasons"])

    def test_every_failed_condition_is_listed(self):
        cell = depth_cell(user_doc(lambda P, v, d, h: math.exp(0.02 if P < 250 else -0.02), tracks=TRACKS[:3]))
        self.assertEqual(cell["status"], "refused")
        self.assertGreaterEqual(len(cell["reasons"]), 2)
        self.assertEqual(len(cell["reasons"]), len(cell["reasonText"]))


class RegimeSplit(unittest.TestCase):
    def test_regime_split_planted_error_refused_by_uniform_sign(self):  # SPEC case 3
        # +30 % in conduction, -30 % in keyhole, tracks in between exact: zero mean, no uniform sign
        def split(P, v, d, h):
            if h < 15.0:
                return 1.3
            if h >= 30.0:
                return 0.7
            return 1.0
        cell = depth_cell(user_doc(split, noise=NOISE))
        self.assertEqual(cell["status"], "refused")
        self.assertIn("uniformSign", cell["reasons"])
        pr = cell["perRegimeMedianLoo"]
        self.assertGreater(pr["conduction"], 0.1)
        self.assertLess(pr["keyhole"], -0.1)
        self.assertEqual(cell["evidenceKind"], "screening-only")


class LabelRule(unittest.TestCase):
    def test_complete_method_and_served_is_calibrated_simulation(self):
        cell = depth_cell(user_doc(UNIFORM, noise=NOISE))
        self.assertEqual(cell["evidenceKind"], "calibrated-simulation")
        self.assertEqual(cell["evidenceScope"], "this machine, user data")
        self.assertEqual(cell["missingMethodFields"], [])
        self.assertTrue(cell["methodComplete"])
        self.assertNotIn("validated", json.dumps(cell).lower())

    def test_each_missing_method_field_downgrades_and_is_listed(self):
        for field in mcfg.MACHINE_CALIBRATION_CONFIG["methodFields"]["required"]:
            method = {k: v for k, v in FULL_METHOD.items() if k != field}
            cell = depth_cell(user_doc(UNIFORM, noise=NOISE, method=method))
            self.assertEqual(cell["status"], "served", field)
            self.assertEqual(cell["evidenceKind"], "screening-only", field)
            self.assertIsNone(cell["evidenceScope"])
            self.assertFalse(cell["methodComplete"])
            self.assertTrue(all(m["fields"] == [field] for m in cell["missingMethodFields"]), field)
            self.assertEqual(len(cell["missingMethodFields"]), len(TRACKS))

    def test_one_incomplete_track_is_enough_to_downgrade(self):
        doc = user_doc(UNIFORM, noise=NOISE)
        del doc["rows"][3]["method"]["depthDatum"]
        cell = depth_cell(doc)
        self.assertEqual(cell["evidenceKind"], "screening-only")
        self.assertEqual([m["trackIds"] for m in cell["missingMethodFields"]], [["t3"]])
        self.assertEqual(cell["missingMethodFields"][0]["fields"], ["depthDatum"])

    def test_no_method_block_lists_all_five_fields(self):
        cell = depth_cell(user_doc(UNIFORM, noise=NOISE, method=None))
        self.assertEqual(cell["evidenceKind"], "screening-only")
        self.assertEqual(cell["missingMethodFields"][0]["fields"], mcfg.MACHINE_CALIBRATION_CONFIG["methodFields"]["required"])

    def test_bad_values_count_as_missing(self):
        for bad in ({"measuredPowerW": 0}, {"measuredPowerW": "198"}, {"replicates": 0}, {"replicates": 2.5},
                    {"depthDatum": "  "}, {"crossSectionLocation": None}):
            method = {**FULL_METHOD, **bad}
            cell = depth_cell(user_doc(UNIFORM, noise=NOISE, method=method))
            self.assertEqual(cell["evidenceKind"], "screening-only", bad)

    def test_refused_cell_with_complete_method_is_screening_only(self):
        cell = depth_cell(user_doc(lambda P, v, d, h: math.exp(-0.02), noise=NOISE))
        self.assertEqual(cell["status"], "refused")
        self.assertEqual(cell["evidenceKind"], "screening-only")
        self.assertTrue(cell["methodComplete"])


class ArtefactRoundTrip(unittest.TestCase):
    def build(self, **kw):
        return mc.build_artefact(user_doc(UNIFORM, noise=NOISE), solver_call=fake_solver, implementation_hash=IMPL,
                                 generated_at="2026-10-09T00:00:00+00:00", code_revision="test", **kw)

    def write(self, art, d, name="machine-calibration.json"):
        return mc.write_artefact(art, Path(d) / name)

    def test_round_trip_and_determinism(self):  # SPEC case 4
        a, b = self.build(), self.build()
        self.assertEqual(a, b)
        with tempfile.TemporaryDirectory() as d:
            p = self.write(a, d)
            self.assertEqual(mc.load_machine_calibration(p, expected_impl_hash=IMPL), json.loads(p.read_text("utf-8")))
        self.assertEqual(a["experimentalValidation"], False)
        self.assertEqual(a["labelPromotionProposed"], "none")
        self.assertTrue(a["machineCalibrationId"].startswith("mc-"))

    def refuse(self, mutate, expect=mc.MachineCalibrationError, impl=IMPL, rehash=False):
        art = copy.deepcopy(self.build())
        mutate(art)
        if rehash:
            art["contentSha256"] = mc.artefact_content_sha256(art)
        with tempfile.TemporaryDirectory() as d:
            p = self.write(art, d)
            with self.assertRaises(expect):
                mc.load_machine_calibration(p, expected_impl_hash=impl)

    def test_unknown_key_refused(self):
        self.refuse(lambda a: a.update({"extra": 1}), rehash=True)

    def test_edited_byte_refused(self):
        self.refuse(lambda a: a["cells"][-1].update({"factor": 1.5}))

    def test_config_drift_refused(self):
        self.refuse(lambda a: a.update({"configSha256": "0" * 64}), rehash=True)

    def test_stale_implementation_hash_refused(self):
        self.refuse(lambda a: None, expect=mc.MachineCalibrationStale, impl="c" * 64)

    def test_evidence_promotion_refused(self):
        def promote(a):
            c = next(c for c in a["cells"] if c["status"] == "not-eligible")
            c.update({"evidenceKind": "calibrated-simulation", "evidenceScope": "this machine, user data"})
        self.refuse(promote, rehash=True)
        self.refuse(lambda a: a.update({"experimentalValidation": True}), rehash=True)
        self.refuse(lambda a: a.update({"labelPromotionProposed": "validated"}), rehash=True)

    def test_calibrated_label_without_complete_method_refused(self):
        def strip(a):
            c = next(c for c in a["cells"] if c["status"] == "served")
            c["missingMethodFields"] = [{"trackIds": ["t0"], "fields": ["depthDatum"]}]
        self.refuse(strip, rehash=True)

    def test_served_cell_integrity_refused(self):
        def served(a):
            return next(c for c in a["cells"] if c["status"] == "served")

        def other_material(a):
            a["material"] = "Ti-6Al-4V"

        def eagar_served(a):
            c = next(c for c in a["cells"] if c["kernel"] == "eagar-tsai" and c["quantity"] == "depth")
            c.update({"status": "served", "evidenceKind": "calibrated-simulation",
                      "evidenceScope": "this machine, user data", "methodComplete": True, "missingMethodFields": []})

        def refused_flipped(a):
            c = served(a)
            c["gate"] = dict(c["gate"], passed=False)

        def reasons_left(a):
            served(a)["reasons"] = ["looSkill"]

        def eligible_not_eligible(a):
            c = served(a)
            c.update({"status": "not-eligible", "evidenceKind": "screening-only", "evidenceScope": None,
                      "methodComplete": False})

        for m in (other_material, eagar_served, refused_flipped, reasons_left, eligible_not_eligible):
            with self.subTest(m.__name__):
                self.refuse(m, rehash=True)

    def test_missing_file_and_bad_json(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(mc.MachineCalibrationError):
                mc.load_machine_calibration(Path(d) / "nope.json", expected_impl_hash=IMPL)
            p = Path(d) / "bad.json"
            p.write_text("{not json", encoding="utf-8")
            with self.assertRaises(mc.MachineCalibrationError):
                mc.load_machine_calibration(p, expected_impl_hash=IMPL)

    def test_stale_artefact_is_unavailable_without_raising(self):
        art = self.build()
        with tempfile.TemporaryDirectory() as d:
            p = self.write(art, d)
            got, info = mc.try_load_machine_calibration(p, expected_impl_hash="c" * 64)
            self.assertIsNone(got)
            self.assertFalse(info["available"])
            self.assertTrue(info["stale"])
            self.assertIn("re-fit", info["reason"])
            got, info = mc.try_load_machine_calibration(p, expected_impl_hash=IMPL)
            self.assertTrue(info["available"])
            out = mc.apply_machine_calibration(INPUTS, "rosenthal", None, solver=apply_solver())
            self.assertFalse(out["machineCalibrated"]["available"])


INPUTS = {"material": MAT, "laserPower_W": 200.0, "scanSpeed_mm_s": 900.0, "beamDiameter_um": 80.0,
          "preheatTemp_C": 20.0, "layerThickness_um": 30.0, "hatchSpacing_um": 100.0}


def apply_solver():
    calls = []

    def solver(material, P, v, d, preheat, layer, hatch, wavelength="IR_1064nm", heat_source="rosenthal", **kw):
        calls.append({"heat_source": heat_source, **kw})
        depth = synth_depth(P, v, d)
        res = {"meltPoolGeometry": {"width_um": 0.9 * depth, "depth_um": depth, "extentStatus": "computed"},
               "processParameters": {"normalizedEnthalpy": synth_enthalpy(P, v, d)},
               "absorptionPath": kw.get("absorption_model") or "default-path"}
        return res
    solver.calls = calls
    return solver


class Apply(unittest.TestCase):
    def setUp(self):
        self.art = mc.build_artefact(user_doc(UNIFORM, noise=NOISE), solver_call=fake_solver, implementation_hash=IMPL,
                                     generated_at="2026-10-09T00:00:00+00:00")

    def test_screening_unchanged_and_calibrated_is_factor_times_default(self):  # SPEC case 5
        solver = apply_solver()
        plain = apply_solver()(MAT, 200.0, 900.0, 80.0, 20.0, 30.0, 100.0, "IR_1064nm", heat_source="rosenthal",
                               sulfur_ppm=15.0, absorption_model=None, thermal_slice_backend=None)
        out = mc.apply_machine_calibration(INPUTS, "rosenthal", self.art, solver=solver)
        self.assertEqual(json.dumps(out["screening"], sort_keys=True), json.dumps(plain, sort_keys=True))
        blk = out["machineCalibrated"]
        cell = next(c for c in self.art["cells"] if c["kernel"] == "rosenthal" and c["quantity"] == "depth")
        self.assertTrue(blk["available"])
        self.assertAlmostEqual(blk["depth_um"], synth_depth(200.0, 900.0, 80.0) * cell["factor"], places=9)
        lo, hi = cell["band"]["factors"]
        self.assertAlmostEqual(blk["depthBand_um"][0], blk["depth_um"] * lo, places=9)
        self.assertAlmostEqual(blk["depthBand_um"][1], blk["depth_um"] * hi, places=9)
        self.assertEqual(blk["evidenceKind"], "calibrated-simulation")
        self.assertEqual(blk["evidenceScope"], "this machine, user data")
        self.assertFalse(blk["usedForBuildJobVerdict"])
        self.assertFalse(out["experimentalValidation"])
        self.assertIsNone(blk["width_um"])
        for k in ("depthOverWidth", "aspectRatio", "regime"):
            self.assertNotIn(k, blk)
        # the calibrated call is the flat-plate path with no property override (no absorptivity node)
        extra = solver.calls[1]
        self.assertEqual(extra["absorption_model"], "flat-plate")
        self.assertNotIn("prop_overrides", extra)

    def test_wavelength_other_than_fit_basis_refused(self):
        solver = apply_solver()
        green = mc.apply_machine_calibration(dict(INPUTS, laserWavelength="Green_515nm"), "rosenthal", self.art,
                                             solver=solver)["machineCalibrated"]
        self.assertFalse(green["available"])
        self.assertIsNone(green["depth_um"])
        self.assertEqual(green["evidenceKind"], "screening-only")
        self.assertIn("fitted on the IR_1064nm default; not applied to Green_515nm", green["reasonText"][0])
        self.assertEqual(len(solver.calls), 1)  # only the screening call ran

    def test_ir_served_at_basis_wavelength_and_cpu_backend_default(self):
        seen = []

        def solver(*a, **kw):
            seen.append((a[7], kw.get("thermal_slice_backend")))
            return apply_solver()(*a, **kw)
        blk = mc.apply_machine_calibration(dict(INPUTS, laserWavelength="IR_1064nm", thermalSliceBackend="gpu"),
                                           "rosenthal", self.art, solver=solver)["machineCalibrated"]
        self.assertTrue(blk["available"])
        self.assertEqual(seen[1], ("IR_1064nm", None))

    def test_not_served_kernel_returns_screening_only_with_reasons(self):
        out = mc.apply_machine_calibration(INPUTS, "eagar-tsai", self.art, solver=apply_solver())
        blk = out["machineCalibrated"]
        self.assertFalse(blk["available"])
        self.assertEqual(blk["status"], "not-eligible")
        self.assertEqual(blk["evidenceKind"], "screening-only")
        self.assertIsNone(blk["depth_um"])
        self.assertIn("regime-dependent", blk["reasonText"][0])

    def test_material_mismatch_and_range_note(self):
        other = dict(INPUTS, material="Ti-6Al-4V")
        blk = mc.apply_machine_calibration(other, "rosenthal", self.art, solver=apply_solver())["machineCalibrated"]
        self.assertFalse(blk["available"])
        far = dict(INPUTS, laserPower_W=900.0)
        blk = mc.apply_machine_calibration(far, "rosenthal", self.art, solver=apply_solver())["machineCalibrated"]
        self.assertTrue(blk["outsideUserTrackRange"])

    def test_screening_only_label_when_method_incomplete(self):
        art = mc.build_artefact(user_doc(UNIFORM, noise=NOISE, method=None), solver_call=fake_solver,
                                implementation_hash=IMPL, generated_at="2026-10-09T00:00:00+00:00")
        blk = mc.apply_machine_calibration(INPUTS, "rosenthal", art, solver=apply_solver())["machineCalibrated"]
        self.assertTrue(blk["available"])
        self.assertEqual(blk["evidenceKind"], "screening-only")
        self.assertEqual(blk["missingMethodFields"][0]["fields"], mcfg.MACHINE_CALIBRATION_CONFIG["methodFields"]["required"])


class InputValidation(unittest.TestCase):
    def test_bad_documents_refused(self):
        good = user_doc(UNIFORM)
        for mutate in (lambda d: d.update({"schema": "x"}), lambda d: d.update({"rows": []}),
                       lambda d: d["rows"][0].update({"depth_um": -1.0}),
                       lambda d: d["rows"][0].update({"label": "Validated"}),
                       lambda d: d["rows"][0].update({"material": "other"})):
            doc = copy.deepcopy(good)
            mutate(doc)
            with self.assertRaises(mc.MachineCalibrationError):
                mc.fit_machine(doc, solver_call=fake_solver)

    def test_replicates_are_one_track(self):
        doc = user_doc(UNIFORM, noise=NOISE)
        dup = copy.deepcopy(doc["rows"][0])
        dup["rowId"], dup["trackId"] = "user-test-t0b", "t0b"
        doc["rows"].append(dup)
        tracks = mc.build_tracks(doc)
        self.assertEqual(len(tracks), len(TRACKS))
        self.assertEqual(max(t["nRows"] for t in tracks), 2)

    def test_out_of_bounds_track_is_unresolved(self):
        doc = user_doc(UNIFORM, tracks=TRACKS[:4] + [(5.0, 900.0, 80.0)], noise=NOISE)
        cell = depth_cell(doc)
        self.assertEqual(cell["gate"]["nUnresolved"], 1)
        self.assertIn("tooFewTracks", cell["reasons"])


class CliTests(unittest.TestCase):
    """SPEC case 6: out-dir refusals and check reproduces (synthetic solver; the CLI is loaded under an alias because
    python/tools/lpbf_machine_calibration.py shares its module name with the core module)."""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("lpbf_machine_calibration_cli",
                                                      PYTHON_DIR / "tools" / "lpbf_machine_calibration.py")
        cls.cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.cli)

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.rows = self.tmp / "rows.json"
        self.rows.write_text(json.dumps(user_doc(UNIFORM, noise=NOISE)), encoding="utf-8")
        self.out = self.tmp / "out"

    def run_cli(self, argv, solver=fake_solver):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = self.cli.main(argv, solver_call=solver)
        return code, err.getvalue()

    def fit(self):
        return self.run_cli(["fit", "--user-source", str(self.rows), "--out-dir", str(self.out)])

    def test_fit_writes_artefact_and_report_with_the_scoped_label(self):
        code, err = self.fit()
        self.assertEqual(code, 0, err)
        art = mc.load_machine_calibration(self.out / "machine-calibration.json")
        cell = next(c for c in art["cells"] if c["kernel"] == "rosenthal" and c["quantity"] == "depth")
        self.assertEqual(cell["status"], "served")
        self.assertEqual(cell["evidenceKind"], "calibrated-simulation")
        self.assertEqual(cell["evidenceScope"], "this machine, user data")
        self.assertIs(art["experimentalValidation"], False)
        report = (self.out / "report.md").read_text(encoding="utf-8")
        self.assertIn("empirical machine offset", report)
        self.assertIn("Your measurements stay on this computer", report)
        for ch in ("—", "–"):
            self.assertNotIn(ch, report)

    def test_out_dir_refusals(self):
        for sub in ("docs", "data/calibration", "data/calibration/x", "docs/y", ""):
            target = REPO_ROOT / sub if sub else REPO_ROOT
            with self.assertRaises(SystemExit, msg=sub):
                self.run_cli(["fit", "--user-source", str(self.rows), "--out-dir", str(target)])
        self.assertFalse((REPO_ROOT / "docs" / "machine-calibration.json").exists())
        self.assertFalse((REPO_ROOT / "machine-calibration.json").exists())

    def test_check_reproduces_and_detects_drift(self):
        self.assertEqual(self.fit()[0], 0)
        art_path = self.out / "machine-calibration.json"
        code, err = self.run_cli(["check", "--artefact", str(art_path), "--user-source", str(self.rows)])
        self.assertEqual(code, 0, err)
        self.assertIn("reproduces", err)
        doc = json.loads(self.rows.read_text(encoding="utf-8"))
        doc["rows"][0]["depth_um"] *= 1.5
        other = self.tmp / "rows2.json"
        other.write_text(json.dumps(doc), encoding="utf-8")
        code, err = self.run_cli(["check", "--artefact", str(art_path), "--user-source", str(other)])
        self.assertEqual(code, 1)
        self.assertIn("userRowsSha256", err)
        art = json.loads(art_path.read_text(encoding="utf-8"))
        art["nTracks"] += 1
        art_path.write_text(json.dumps(art), encoding="utf-8")
        code, err = self.run_cli(["check", "--artefact", str(art_path), "--user-source", str(self.rows)])
        self.assertEqual(code, 2)

    def test_check_fails_when_the_solver_changes(self):
        self.assertEqual(self.fit()[0], 0)

        def shifted(args, kernel):
            w, d, status, h = fake_solver(args, kernel)
            return w, d * 1.3, status, h
        code, err = self.run_cli(["check", "--artefact", str(self.out / "machine-calibration.json"),
                                  "--user-source", str(self.rows)], solver=shifted)
        self.assertEqual(code, 1)
        self.assertIn("differs", err)

    def test_eligibility_prints_the_committed_list(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.cli.main(["eligibility"]), 0)
        text = out.getvalue()
        self.assertIn("rosenthal | 316L Stainless Steel | depth", text)
        self.assertIn(mcfg.config_sha256(), text)

    def test_unusable_user_rows_exit_2(self):
        bad = self.tmp / "bad.json"
        bad.write_text("{}", encoding="utf-8")
        code, _ = self.run_cli(["fit", "--user-source", str(bad), "--out-dir", str(self.out)])
        self.assertEqual(code, 2)


class FrozenGuard(unittest.TestCase):
    NEW = ("lpbf_machine_calibration", "lpbf_machine_calibration_config")

    def test_no_frozen_file_imports_the_machine_modules(self):  # SPEC case 7
        offenders = []
        for name in lpbf_simulation.IMPLEMENTATION_SOURCE_FILES:
            path = PYTHON_DIR / name
            if path.suffix != ".py" or not path.is_file():
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                mods = []
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    mods = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
                offenders += [(name, m) for m in mods if m.split(".")[-1].startswith("lpbf_machine_calibration")]
        self.assertEqual(offenders, [])

    def test_new_modules_are_not_in_the_frozen_manifest(self):
        names = {Path(n).stem for n in lpbf_simulation.IMPLEMENTATION_SOURCE_FILES}
        self.assertFalse(names & set(self.NEW))

    def test_fingerprint_equals_the_pin(self):
        expected = (PYTHON_DIR / "lpbf_implementation_fingerprint.expected").read_text(encoding="utf-8").strip()
        self.assertEqual(lpbf_simulation.implementation_fingerprint(), expected)

    def test_fingerprint_pin_file_unchanged_against_head(self):
        r = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "python/lpbf_fingerprint_pin.py",
                            "python/lpbf_implementation_fingerprint.expected"], cwd=str(REPO_ROOT), capture_output=True)
        if r.returncode not in (0, 1):
            self.skipTest("git not available")
        self.assertEqual(r.returncode, 0)

    def test_modules_do_not_write_to_the_repo_or_import_the_server_stack(self):
        src = (PYTHON_DIR / "lpbf_machine_calibration.py").read_text(encoding="utf-8")
        self.assertNotIn("data/calibration", src)
        cfg = mcfg.MACHINE_CALIBRATION_CONFIG
        self.assertIs(cfg["evidence"]["experimentalValidation"], False)
        self.assertEqual(cfg["eligibleCells"], [{"kernel": "rosenthal", "material": MAT, "quantity": "depth"}])


if __name__ == "__main__":
    unittest.main()
