"""Offline tests for the machine-calibrated melt-pool CLI and the Build Job ``machineCalibration`` extra (synthetic
artefacts built with the fake solver of test_lpbf_machine_calibration; the Build Job checks use the real frozen
Rosenthal path once per request). SCREENING ONLY, NOT VALIDATION."""

import ast
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lpbf_machine_calibration as mc  # noqa: E402
import lpbf_machine_calibrated_meltpool as cli  # noqa: E402
import lpbf_build_job_solver as bj  # noqa: E402
import test_lpbf_machine_calibration as T  # noqa: E402

PYTHON_DIR = Path(__file__).resolve().parent
SCRIPT = PYTHON_DIR / "lpbf_machine_calibrated_meltpool.py"


def make_art(method=T.FULL_METHOD, impl=T.IMPL, factor=T.UNIFORM):
    return mc.build_artefact(T.user_doc(factor, noise=T.NOISE, method=method), solver_call=T.fake_solver,
                             implementation_hash=impl, generated_at="2026-10-09T00:00:00+00:00")


def write_root(root, *arts):
    for i, art in enumerate(arts):
        mc.write_artefact(art, Path(root) / f"user-{i}" / cli.ARTEFACT_NAME)


class Discovery(unittest.TestCase):
    def test_status_lists_ready_stale_and_invalid_without_paths(self):
        good = make_art()
        stale = make_art(impl="c" * 64, factor=lambda P, v, d, h: 0.5)
        with tempfile.TemporaryDirectory() as d:
            write_root(d, good, stale)
            bad = Path(d) / "user-9"
            bad.mkdir()
            (bad / cli.ARTEFACT_NAME).write_text("{nope", encoding="utf-8")
            out = cli.status(d, expected_impl_hash=T.IMPL)
        self.assertTrue(out["success"])
        self.assertEqual(sorted(a["state"] for a in out["artefacts"]), ["invalid", "ready", "stale"])
        self.assertEqual(out["status"], "ready")
        self.assertNotIn(d.replace("\\", "\\\\"), json.dumps(out))
        self.assertFalse(out["experimentalValidation"])
        self.assertEqual(out["eligibleCells"], mc.MACHINE_CALIBRATION_CONFIG["eligibleCells"])
        self.assertNotIn("validated", json.dumps(out).lower())

    def test_empty_and_missing_root_are_none(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(cli.status(d)["status"], "none")
            self.assertEqual(cli.status(Path(d) / "absent")["status"], "none")


class Run(unittest.TestCase):
    def setUp(self):
        self.art = make_art()
        self.cell = next(c for c in self.art["cells"] if c["kernel"] == "rosenthal" and c["quantity"] == "depth")

    def req(self, **kw):
        return {**T.INPUTS, "machineCalibration": self.art["machineCalibrationId"], **kw}

    def run_(self, data, arts=None, impl=T.IMPL):
        with tempfile.TemporaryDirectory() as d:
            write_root(d, *(arts if arts is not None else [self.art]))
            return cli.run(data, root=d, solver=T.apply_solver(), expected_impl_hash=impl)

    def test_served_with_full_method_fields_is_calibrated_simulation(self):
        out = self.run_(self.req())
        blk = out["machineCalibrated"]
        self.assertTrue(out["success"])
        self.assertTrue(blk["available"])
        self.assertEqual(blk["evidenceKind"], "calibrated-simulation")
        self.assertEqual(blk["evidenceScope"], "this machine, user data")
        self.assertAlmostEqual(blk["depth_um"], T.synth_depth(200.0, 900.0, 80.0) * self.cell["factor"], places=9)
        self.assertFalse(out["experimentalValidation"])
        self.assertFalse(blk["usedForBuildJobVerdict"])
        self.assertIn("stay on this computer", out["privacy"])
        self.assertIn("empirical machine offset", blk["note"])

    def test_green_wavelength_refused_and_ir_served_via_cli(self):
        green = self.run_(self.req(laserWavelength="Green_515nm"))["machineCalibrated"]
        self.assertFalse(green["available"])
        self.assertIsNone(green["depth_um"])
        self.assertEqual(green["evidenceKind"], "screening-only")
        self.assertIn("not applied to Green_515nm", green["reasonText"][0])
        ir = self.run_(self.req(laserWavelength="IR_1064nm"))["machineCalibrated"]
        self.assertTrue(ir["available"])
        self.assertEqual(ir["evidenceKind"], "calibrated-simulation")

    def test_build_job_block_wavelength_basis(self):
        with tempfile.TemporaryDirectory() as d:
            write_root(d, self.art)
            kw = dict(root=Path(d), solver=T.apply_solver(), expected_impl_hash=T.IMPL, screening_depth_um=1.0)
            mid = self.art["machineCalibrationId"]
            green = cli.build_job_block(mid, T.MAT, {**T.INPUTS, "laserWavelength": "Green_515nm"}, **kw)
            ir = cli.build_job_block(mid, T.MAT, {**T.INPUTS, "laserWavelength": "IR_1064nm"}, **kw)
        self.assertFalse(green["available"])
        self.assertIn("not applied to Green_515nm", green["reasonText"][0])
        self.assertTrue(ir["available"])
        self.assertFalse(green["usedForBuildJobVerdict"])

    def test_missing_method_fields_downgrade_to_screening_only_and_list_them(self):
        art = make_art(method=None)
        out = self.run_(self.req(machineCalibration=art["machineCalibrationId"]), arts=[art])
        blk = out["machineCalibrated"]
        self.assertTrue(blk["available"])
        self.assertEqual(blk["evidenceKind"], "screening-only")
        self.assertTrue(blk["missingMethodFields"])

    def test_not_eligible_kernel_returns_screening_with_reason(self):
        out = self.run_(self.req(heatSource="eagar-tsai"))
        blk = out["machineCalibrated"]
        self.assertFalse(blk["available"])
        self.assertEqual(blk["status"], "not-eligible")
        self.assertEqual(blk["evidenceKind"], "screening-only")
        self.assertIsNone(blk["depth_um"])

    def test_unknown_stale_and_tampered_artefacts_never_fail_the_request(self):
        out = self.run_(self.req(machineCalibration="mc-000000000000"))
        self.assertTrue(out["success"])
        self.assertFalse(out["machineCalibrated"]["available"])
        self.assertIn("not found", out["machineCalibrated"]["reasonText"][0])
        self.assertIn("meltPoolGeometry", out["screening"])
        out = self.run_(self.req(), impl="d" * 64)
        self.assertFalse(out["machineCalibrated"]["available"])
        self.assertTrue(out["machineCalibrated"]["stale"])
        self.assertIn("re-fit", out["machineCalibrated"]["reasonText"][0])
        tampered = copy.deepcopy(self.art)
        tampered["cells"][-1]["factor"] = 2.0
        out = self.run_(self.req(), arts=[tampered])
        self.assertFalse(out["machineCalibrated"]["available"])
        self.assertIsNone(out["machineCalibrated"]["depth_um"])

    def test_validation_refusals(self):
        bad_inputs = [None, [], {"material": T.MAT}, self.req(machineCalibration="../../etc/passwd"),
                      self.req(machineCalibration="mc-ZZZZZZZZZZZZ"), self.req(material=""), self.req(material=None),
                      self.req(heatSource="fdm"), self.req(laserPower_W=-5), self.req(scanSpeed_mm_s=float("nan")),
                      self.req(beamDiameter_um=True), self.req(preheatTemp_C=-300.0)]
        for bad in bad_inputs:
            out = cli.run(bad, root=tempfile.gettempdir(), solver=T.apply_solver())
            self.assertFalse(out["success"], bad)
            self.assertEqual(out["errorKind"], "validation", bad)

    def test_request_cannot_point_at_a_path(self):
        with tempfile.TemporaryDirectory() as d:
            out = cli.run(self.req(machineCalibration="mc-0123456789ab", path=str(Path(d) / "x.json")), root=d,
                          solver=T.apply_solver())
        self.assertFalse(out["machineCalibrated"]["available"])


class CliProcess(unittest.TestCase):
    def call(self, stdin, env_dir, *args):
        env = {**os.environ, cli.ROOT_ENV: env_dir, "PYTHONDONTWRITEBYTECODE": "1"}
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *args], input=stdin, capture_output=True, text=True,
                              cwd=str(PYTHON_DIR), env=env, timeout=180)

    def test_status_action_and_flag_print_one_json_document(self):
        with tempfile.TemporaryDirectory() as d:
            for p in (self.call(json.dumps({"action": "status"}), d), self.call("", d, "--status")):
                self.assertEqual(p.returncode, 0, p.stderr)
                doc = json.loads(p.stdout)
                self.assertEqual(doc["status"], "none")
                self.assertTrue(doc["success"])

    def test_validation_refusal_exits_2_with_the_envelope(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.call(json.dumps({"material": T.MAT}), d)
            self.assertEqual(p.returncode, 2)
            self.assertEqual(json.loads(p.stdout)["errorKind"], "validation")
            p = self.call("{not json", d)
            self.assertEqual(p.returncode, 2)
            self.assertEqual(json.loads(p.stdout)["errorKind"], "validation")

    def test_unknown_id_runs_the_real_screening_solver(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.call(json.dumps({**T.INPUTS, "machineCalibration": "mc-0123456789ab"}), d)
            self.assertEqual(p.returncode, 0, p.stderr)
            doc = json.loads(p.stdout)
            self.assertFalse(doc["machineCalibrated"]["available"])
            self.assertIn("meltPoolGeometry", doc["screening"])


class BuildJobExtra(unittest.TestCase):
    """The optional ``machineCalibration`` input adds a top-level ``machineCalibrated`` block and changes nothing else."""
    REQ = {"alloyId": "ss316l", "laserPower_W": 200.0, "scanSpeed_mm_s": 900.0, "beamDiameter_um": 80.0,
           "preheatTemp_C": 20.0, "layerThickness_um": 30.0, "hatchSpacing_um": 100.0, "bypassCache": True}

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.art = make_art(impl=None)  # live implementation fingerprint, so the real loader accepts it
        write_root(cls.tmp.name, cls.art)
        cls._old = os.environ.get(cli.ROOT_ENV)
        os.environ[cli.ROOT_ENV] = cls.tmp.name
        cls.base = bj.solve_lpbf_build_job(dict(cls.REQ))
        cls.cal = bj.solve_lpbf_build_job({**cls.REQ, "machineCalibration": cls.art["machineCalibrationId"]})

    @classmethod
    def tearDownClass(cls):
        if cls._old is None:
            os.environ.pop(cli.ROOT_ENV, None)
        else:
            os.environ[cli.ROOT_ENV] = cls._old
        cls.tmp.cleanup()

    def test_default_request_has_no_machine_block(self):
        self.assertTrue(self.base["success"])
        self.assertNotIn("machineCalibrated", self.base)

    def test_extra_key_only_and_verdict_unchanged(self):
        self.assertTrue(self.cal["success"])
        self.assertIn("machineCalibrated", self.cal)
        self.assertEqual(set(self.cal) - {"machineCalibrated"}, set(self.base))
        for key in ("alloyId", "buildJobIdentity", "materialPropertySha256", "microstructure", "segregation", "kinetics",
                    "porosity", "qualification", "verdict"):
            self.assertEqual(json.dumps(self.cal[key], sort_keys=True), json.dumps(self.base[key], sort_keys=True), key)
        self.assertEqual(self.cal["verdict"], self.base["verdict"])
        self.assertEqual(self.cal["thermal"]["meltPoolGeometry"], self.base["thermal"]["meltPoolGeometry"])

    def test_block_is_next_to_the_screening_value_and_not_used_for_the_verdict(self):
        blk = self.cal["machineCalibrated"]
        self.assertTrue(blk["available"], blk.get("reasonText"))
        self.assertFalse(blk["usedForBuildJobVerdict"])
        self.assertFalse(blk["experimentalValidation"])
        self.assertEqual(blk["screeningDepth_um"], self.base["thermal"]["meltPoolGeometry"]["depth_um"])
        self.assertEqual(blk["evidenceKind"], "calibrated-simulation")
        self.assertNotEqual(blk["depth_um"], blk["screeningDepth_um"])
        self.assertNotIn("validated", json.dumps(blk).lower())

    def test_cache_and_input_are_not_polluted(self):
        data = {**self.REQ, "bypassCache": False, "machineCalibration": self.art["machineCalibrationId"]}
        before = copy.deepcopy(data)
        first = bj.solve_lpbf_build_job(data)
        self.assertEqual(data, before)
        again = bj.solve_lpbf_build_job({k: v for k, v in data.items() if k != "machineCalibration"})
        self.assertIn("machineCalibrated", first)
        self.assertNotIn("machineCalibrated", again)

    def test_bad_id_or_missing_artefact_never_fails_the_job(self):
        for mcid in ("nope", "mc-000000000000", 7):
            out = bj.solve_lpbf_build_job({**self.REQ, "machineCalibration": mcid})
            self.assertTrue(out["success"], mcid)
            self.assertFalse(out["machineCalibrated"]["available"], mcid)
            self.assertEqual(out["verdict"], self.base["verdict"])

    def test_null_id_means_not_requested(self):
        out = bj.solve_lpbf_build_job({**self.REQ, "machineCalibration": None})
        self.assertTrue(out["success"])
        self.assertNotIn("machineCalibrated", out)

    def test_failed_job_stays_failed_without_a_block(self):
        out = bj.solve_lpbf_build_job({"alloyId": "unobtainium", "machineCalibration": "mc-000000000000"})
        self.assertFalse(out["success"])
        self.assertNotIn("machineCalibrated", out)


class FrozenGuard(unittest.TestCase):
    def test_no_frozen_file_imports_the_new_module(self):
        import lpbf_simulation
        for name in lpbf_simulation.IMPLEMENTATION_SOURCE_FILES:
            p = PYTHON_DIR / name
            if not p.exists() or p.suffix != ".py":
                continue
            for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
                mods = []
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    mods = [node.module]
                for m in mods:
                    self.assertFalse(m.startswith("lpbf_machine_calibrat"), f"{name} imports {m}")


if __name__ == "__main__":
    unittest.main()
