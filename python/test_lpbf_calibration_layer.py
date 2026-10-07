"""Offline tests for lpbf_calibration_layer.py and lpbf_calibrated_meltpool.py (hand-built artefact, injected fake
solver: no dataset, no frozen-physics run). SCREENING ONLY, NOT VALIDATION."""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lpbf_calibration_layer as layer  # noqa: E402
import lpbf_calibrated_meltpool as cli  # noqa: E402
from lpbf_calibration_config import CALIBRATION_CONFIG, CALIBRATION_SCHEMA, config_sha256  # noqa: E402

IMPL = "a" * 64
MAT = "316L Stainless Steel"
INPUTS = {"material": MAT, "laserPower_W": 200.0, "scanSpeed_mm_s": 900.0, "beamDiameter_um": 80.0, "preheatTemp_C": 20.0,
          "layerThickness_um": 30.0, "hatchSpacing_um": 100.0, "heatSource": "eagar-tsai"}


def cell(kernel, quantity, status, rung="eta2", params=None):
    base = {"etaW": 0.50, "etaD": 0.46, "etaJoint": 0.48, "cD": {"conduction": 0.0, "transition": 0.0, "keyhole": 0.10},
            "etaPrior": 0.42}
    return {"kernel": kernel, "material": MAT, "quantity": quantity, "status": status, "rung": rung, "reasons": [],
            "params": params or base,
            "interval": {"m": 0.0, "sWithin": 0.10, "sSource": 0.12, "levels": [0.8, 0.9]},
            "heldOutScore": [{"heldOut": "ku-leuven-316l-2021", "trainedOn": ["hofmann-316l-2026"], "rung": rung, "nRows": 44,
                              "nSets": 44, "mapeDefault": 16.6, "mapeServed": 12.0, "skill": 0.28, "skillCi95": [0.05, 0.40],
                              "coverage90": {"coverage": 0.93, "k": 41, "n": 44, "wilson95": [0.82, 0.98]}}],
            "withinSourceScore": [], "flags": {}, "beamStatuses": None}


def make_artefact(cells, impl=IMPL):
    art = {
        "schema": CALIBRATION_SCHEMA, "calibrationId": "", "generatedAt": "2026-10-07", "implementationHash": impl,
        "codeRevision": {"gitHead": "x"}, "tool": {"path": "python/tools/lpbf_calibration_fit.py", "sha256": "0" * 64},
        "configSha256": config_sha256(CALIBRATION_CONFIG), "config": CALIBRATION_CONFIG,
        "trainingData": [{"source": "hofmann-316l-2026", "doi": "10.5281/zenodo.16979848", "tableSha256": "d" * 64,
                          "rowsUsed": 677, "parameterSets": 378, "material": MAT}],
        "catalogSentinelSources": ["guo-316l-2024"], "heldOutSources": "leave-one-source-out", "priors": {},
        "envelope": {MAT: {"laserPower_W": [100.0, 350.0], "scanSpeed_mm_s": [400.0, 1200.0], "beamDiameter_um": [50.0, 110.0],
                           "normalizedEnthalpyDefault": [2.0, 60.0], "sources": ["hofmann-316l-2026"], "rows": 677}},
        "cells": cells, "scorecardRecord": "docs/LPBF_CALIBRATION_SCORECARD_2026-10-07.json", "scorecardSha256": "e" * 64,
        "evidenceKind": "screening-only", "proposedEvidenceKind": None, "evidenceLabel": layer.LABEL,
        "labelPromotionProposed": "none", "honesty": "synthetic fixture", "contentSha256": "",
    }
    sha = layer.artefact_content_sha256(art)
    art["contentSha256"] = sha
    art["calibrationId"] = f"lpbf-meltpool-calib-2026-10-07-{sha[:12]}"
    return art


def fake_solver(calls=None, default_eta=0.42):
    def solver(material, power, speed, beam, preheat, layer_um, hatch, wavelength="IR_1064nm", heat_source="rosenthal",
               sulfur_ppm=15.0, absorption_model=None, thermal_slice_backend=None, prop_overrides=None):
        if calls is not None:
            calls.append({"heat_source": heat_source, "absorption_model": absorption_model, "prop_overrides": prop_overrides})
        eta = (prop_overrides or {}).get("absorptivity_IR", default_eta)
        return {"success": True, "material": material, "heatSource": heat_source,
                "processParameters": {"normalizedEnthalpy": 40.0 * eta / default_eta, "absorptionModel": absorption_model},
                "meltPoolGeometry": {"width_um": 300.0 * eta, "depth_um": 200.0 * eta, "extentStatus": "computed"}}
    return solver


class ArtefactTests(unittest.TestCase):
    def write(self, art):
        d = Path(tempfile.mkdtemp())
        p = d / "calib.json"
        p.write_text(json.dumps(art), encoding="utf-8")
        return p

    def test_round_trip_and_tamper_detection(self):  # T-ART-1
        art = make_artefact([cell("eagar-tsai", "width", "enabled")])
        loaded = layer.load_calibration(self.write(art), expected_impl_hash=IMPL)
        self.assertEqual(loaded["contentSha256"], art["contentSha256"])
        tampered = copy.deepcopy(art)
        tampered["cells"][0]["params"]["etaW"] = 0.51
        with self.assertRaises(layer.CalibrationError):
            layer.load_calibration(self.write(tampered), expected_impl_hash=IMPL)
        extra = copy.deepcopy(art)
        extra["surprise"] = 1
        with self.assertRaises(layer.CalibrationError):
            layer.load_calibration(self.write(extra), expected_impl_hash=IMPL)
        with self.assertRaises(layer.CalibrationError):
            layer.load_calibration(Path(tempfile.mkdtemp()) / "missing.json", expected_impl_hash=IMPL)

    def test_stale_implementation_hash_is_refused(self):  # T-ART-2
        art = make_artefact([cell("eagar-tsai", "width", "enabled")])
        with self.assertRaises(layer.CalibrationStale) as cm:
            layer.load_calibration(self.write(art), expected_impl_hash="b" * 64)
        self.assertIn("stale for this physics version", str(cm.exception))

    def test_config_hash_mismatch_is_refused(self):  # T-CFG-1
        art = make_artefact([cell("eagar-tsai", "width", "enabled")])
        art["config"] = copy.deepcopy(art["config"])
        art["config"]["prior"] = {**art["config"]["prior"], "lambda": 0.5}
        art["contentSha256"] = layer.artefact_content_sha256(art)
        with self.assertRaises(layer.CalibrationError):
            layer.load_calibration(self.write(art), expected_impl_hash=IMPL)
        art2 = make_artefact([cell("eagar-tsai", "width", "enabled")])
        art2["configSha256"] = "0" * 64
        art2["contentSha256"] = layer.artefact_content_sha256(art2)
        with self.assertRaises(layer.CalibrationError):
            layer.load_calibration(self.write(art2), expected_impl_hash=IMPL)

    def test_promotion_proposals_are_refused(self):
        art = make_artefact([cell("eagar-tsai", "width", "enabled")])
        art["proposedEvidenceKind"] = "calibrated-simulation"
        art["contentSha256"] = layer.artefact_content_sha256(art)
        with self.assertRaises(layer.CalibrationError):
            layer.load_calibration(self.write(art), expected_impl_hash=IMPL)


class RuntimeTests(unittest.TestCase):
    def calib(self, cells):
        return make_artefact(cells)

    def test_screening_block_is_the_plain_solver_call_byte_for_byte(self):  # T-RUN-1
        calls = []
        calib = self.calib([cell("eagar-tsai", "width", "enabled"), cell("eagar-tsai", "depth", "enabled")])
        out = layer.apply_calibration(INPUTS, "eagar-tsai", calib, solver=fake_solver(calls))
        plain = fake_solver()(MAT, 200.0, 900.0, 80.0, 20.0, 30.0, 100.0, "IR_1064nm", heat_source="eagar-tsai",
                              sulfur_ppm=15.0, absorption_model=None, thermal_slice_backend=None)
        self.assertEqual(json.dumps(out["screening"], sort_keys=True), json.dumps(plain, sort_keys=True))
        self.assertIsNone(calls[0]["prop_overrides"], "the screening call carries no override")
        self.assertIsNone(calls[0]["absorption_model"])
        self.assertTrue(all(c["absorption_model"] == "flat-plate" for c in calls[1:]))

    def test_only_enabled_cells_are_served(self):  # T-RUN-2
        calib = self.calib([cell("eagar-tsai", "width", "enabled"), cell("eagar-tsai", "depth", "within-source-only")])
        out = layer.apply_calibration(INPUTS, "eagar-tsai", calib, solver=fake_solver())
        c = out["calibrated"]
        self.assertTrue(c["available"])
        self.assertAlmostEqual(c["width_um"], 300.0 * 0.50)
        self.assertIsNone(c["depth_um"])
        self.assertIn("within-source-only", c["depthReason"])
        self.assertIsNone(c["depthOverWidth"])
        self.assertIn("no depth/width", c["depthOverWidthReason"])
        self.assertEqual(c["cells"]["depth"]["status"], "within-source-only")
        rejected = self.calib([cell("eagar-tsai", "width", "rejected"), cell("eagar-tsai", "depth", "rejected")])
        none = layer.apply_calibration(INPUTS, "eagar-tsai", rejected, solver=fake_solver())
        self.assertFalse(none["calibrated"]["available"])
        self.assertIsNone(none["calibrated"]["width_um"])
        other_kernel = layer.apply_calibration(dict(INPUTS, heatSource="goldak"), "goldak", calib, solver=fake_solver())
        self.assertFalse(other_kernel["calibrated"]["available"])

    def test_label_and_no_promotion_strings(self):  # T-RUN-3
        calib = self.calib([cell("eagar-tsai", "width", "enabled"), cell("eagar-tsai", "depth", "enabled")])
        out = layer.apply_calibration(INPUTS, "eagar-tsai", calib, solver=fake_solver())
        self.assertEqual(out["evidenceKind"], "screening-only")
        self.assertEqual(out["calibration"]["evidenceKind"], "screening-only")
        self.assertIn("not validation", out["calibration"]["label"])
        text = json.dumps(out)
        self.assertNotIn("Calibrated simulation", text)
        self.assertNotIn("calibrated-simulation", text)
        self.assertIn("rung selected in training only", json.dumps(out["calibration"]["heldOutScore"]))
        self.assertIn("hofmann-316l-2026 (677 rows)", out["calibration"]["fittedOn"])

    def test_outside_training_envelope_is_flagged(self):  # T-RUN-4
        calib = self.calib([cell("eagar-tsai", "width", "enabled")])
        inside = layer.apply_calibration(INPUTS, "eagar-tsai", calib, solver=fake_solver())
        self.assertFalse(inside["outsideTrainingEnvelope"])
        outside = layer.apply_calibration(dict(INPUTS, laserPower_W=900.0), "eagar-tsai", calib, solver=fake_solver())
        self.assertTrue(outside["outsideTrainingEnvelope"])
        self.assertTrue(any("power" in n for n in outside["envelopeNotes"]))

    def test_both_served_gives_ratio_and_intervals_and_offsets(self):
        calib = self.calib([cell("eagar-tsai", "width", "enabled"), cell("eagar-tsai", "depth", "enabled", rung="eta2+dOffset")])
        out = layer.apply_calibration(INPUTS, "eagar-tsai", calib, solver=fake_solver())
        c = out["calibrated"]
        self.assertIsNotNone(c["depthOverWidth"])
        self.assertAlmostEqual(c["depthOverWidth"], c["depth_um"] / c["width_um"])
        lo, hi = c["width_pi90_um"]
        self.assertLess(lo, c["width_um"])
        self.assertGreater(hi, c["width_um"])
        self.assertLess(c["width_pi80_um"][1] - c["width_pi80_um"][0], hi - lo)
        # the screening regime label is unchanged and no calibrated label replaces it
        self.assertEqual(c["regimeLabel"], "keyhole")
        self.assertNotIn("regimeLabelCalibrated", c)

    def test_cli_returns_screening_only_when_not_requested_stale_or_missing(self):
        saved_solver, saved_load = layer._default_solver, layer.load_calibration
        layer._default_solver = lambda: fake_solver()
        try:
            plain = fake_solver()(MAT, 200.0, 900.0, 80.0, 20.0, 30.0, 100.0, "IR_1064nm", heat_source="eagar-tsai",
                                  sulfur_ppm=15.0, absorption_model=None, thermal_slice_backend=None)
            off = cli.run(dict(INPUTS))
            self.assertEqual(off["screening"], plain)
            self.assertFalse(off["calibrated"]["available"])
            self.assertIn("not requested", off["calibrated"]["reason"])

            def stale():
                raise layer.CalibrationStale("calibration stale for this physics version")

            def missing():
                raise layer.CalibrationError("calibration artefact missing")

            for loader, text in ((stale, "stale"), (missing, "unavailable")):
                layer.load_calibration = loader
                out = cli.run(dict(INPUTS, calibrationMode=True))
                self.assertEqual(out["screening"], plain)
                self.assertFalse(out["calibrated"]["available"])
                self.assertIn(text, out["calibrated"]["reason"])
                self.assertEqual(out["evidenceKind"], "screening-only")
            layer.load_calibration = lambda: make_artefact([cell("eagar-tsai", "width", "enabled")])
            served = cli.run(dict(INPUTS, calibrationMode=True))
            self.assertTrue(served["calibrated"]["available"])
        finally:
            layer._default_solver, layer.load_calibration = saved_solver, saved_load
        self.assertIn("enabledCells", cli.status())


if __name__ == "__main__":
    unittest.main()
