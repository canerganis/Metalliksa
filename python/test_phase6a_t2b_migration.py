"""Phase 6a tranche 2b structural migration: kinetics, stochastic UQ, fatigue, phase9.

- outputs equal the pre-migration code, compared in-process against the base blob
  (git show 7f3f803:...) with key ORDER included (json.dumps without sort_keys),
  for every alloy / base metal, not only the five golden cases per solver;
- an unknown kinetics/fatigue alloy is a ValidationError exactly where the old code
  silently substituted AISI 4140 / Ti-6Al-4V; the stochastic fallbacks are kept;
- kinetics stdout envelope + exit 2, also through persistent_ipc_service;
- source guard against re-introduced constant literals / silent table fallbacks.
"""

import ast
import json
import os
import subprocess
import sys
import types
import unittest
from pathlib import Path

import alloy_registry as reg
import input_validation as iv
import kinetics_ttt_cct_solver as kin
import lpbf_fatigue_fracture as ff
import physical_constants as pc
import stochastic_uq_mmpds_solver as uq
from phase6a_test_support import require_git_revision

HERE = Path(__file__).parent
BASE = "7f3f803"
MIGRATED = ("kinetics_ttt_cct_solver.py", "stochastic_uq_mmpds_solver.py", "lpbf_fatigue_fracture.py")


def _base_module(name):
    """Execute the pre-migration blob of python/<name>.py as a throwaway module."""
    try:
        src = subprocess.run(["git", "-C", str(HERE), "show", f"{BASE}:python/{name}.py"],
                             capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    module = types.ModuleType(f"_t2b_base_{name}")
    sys.modules[module.__name__] = module
    try:
        exec(compile(src, f"{name}.py@{BASE}", "exec"), module.__dict__)
    finally:
        sys.modules.pop(module.__name__, None)
    return module


def _strip(doc):
    if isinstance(doc, dict):
        return {k: _strip(v) for k, v in doc.items() if k != "computeTimeMs"}
    if isinstance(doc, list):
        return [_strip(v) for v in doc]
    return doc


def _run(script, payload):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run([sys.executable, "-B", script], input=json.dumps(payload).encode(),
                          capture_output=True, cwd=str(HERE), env=env, timeout=300)
    return proc.returncode, json.loads(proc.stdout.decode("utf-8"))


OLD_KIN = _base_module("kinetics_ttt_cct_solver")
OLD_UQ = _base_module("stochastic_uq_mmpds_solver")
OLD_FF = _base_module("lpbf_fatigue_fracture")


@require_git_revision(OLD_KIN is not None, f"git revision {BASE} unavailable")
class KineticsTest(unittest.TestCase):
    LEGACY = ("AISI 4140", "AISI 4340", "AISI D2", "Inconel 718", "Ti-6Al-4V", "Al 7075")

    def test_every_alloy_equals_the_base_blob_including_key_order(self):
        for name in self.LEGACY:
            for args in ((name,), (name, 0.3, 40.0, 900.0, 4.0, 650.0), (name, 2000.0)):
                with self.subTest(args=args):
                    new = _strip(kin.solve_phase_transformation_kinetics(*args))
                    old = _strip(OLD_KIN.solve_phase_transformation_kinetics(*args))
                    self.assertEqual(json.dumps(new), json.dumps(old))

    def test_unknown_alloy_raises_instead_of_aisi4140(self):
        for name in ("Unobtainium XYZ", "", None, 4140, "4140", "Inconel"):
            with self.subTest(name=name):
                with self.assertRaises(iv.ValidationError) as ctx:
                    kin.solve_phase_transformation_kinetics(name)
                self.assertEqual(ctx.exception.code, iv.UNKNOWN_ALLOY)
                self.assertEqual(ctx.exception.field, "alloy")
        # Old behaviour for the record: a silent AISI 4140 solve.
        old = OLD_KIN.solve_phase_transformation_kinetics("Unobtainium XYZ")
        self.assertEqual(old["alloyMetadata"]["Ae3_C"], 780.0)

    def test_registry_alloy_without_kinetics_data_is_refused(self):
        with self.assertRaises(iv.ValidationError) as ctx:
            kin.solve_phase_transformation_kinetics("316L SS")
        self.assertEqual(ctx.exception.detail["reason"], "no-domain-data")

    def test_aliases_resolve_to_their_own_alloy(self):
        # Behaviour change: before, "IN718" silently got AISI 4140 data.
        res = kin.solve_phase_transformation_kinetics("IN718")
        self.assertEqual(res["alloy"], "IN718")
        self.assertEqual(res["alloyMetadata"]["Ae3_C"], 1020.0)
        ref = kin.solve_phase_transformation_kinetics("Inconel 718")
        self.assertEqual(json.dumps(_strip({**res, "alloy": None})), json.dumps(_strip({**ref, "alloy": None})))

    def test_build_job_names_still_resolve(self):
        # lpbf_build_job_solver.py:641 maps alloy ids to these names in-process.
        for name in ("Inconel 718", "Ti-6Al-4V", "AISI 4140"):
            self.assertTrue(kin.solve_phase_transformation_kinetics(name, 1e5)["success"])

    def test_envelope_internal_error_and_provenance(self):
        code, out = _run("kinetics_ttt_cct_solver.py", {"alloy": "Unobtainium"})
        self.assertEqual(code, 2)
        self.assertEqual(set(out), {"success", "error", "errorKind"})
        self.assertEqual(out["errorKind"], "validation")
        self.assertEqual(out["error"]["code"], "UNKNOWN_ALLOY")
        code, out = _run("kinetics_ttt_cct_solver.py", {"alloy": "AISI 4140", "coolingRate_C_s": "fast"})
        self.assertEqual(code, 1)
        self.assertEqual(out["errorKind"], "internal")
        code, out = _run("kinetics_ttt_cct_solver.py", {"alloy": "AISI 4340"})
        self.assertEqual(code, 0)
        prov = out["provenance"]
        self.assertEqual(prov["registryAlloyId"], "aisi4340")
        self.assertEqual(prov["registryVersion"], reg.REGISTRY_VERSION)
        self.assertEqual(prov["constantsVersion"], pc.CONSTANTS_VERSION)
        self.assertEqual(prov["gasConstantR_J_molK"], 8.314)


@require_git_revision(OLD_FF is not None, f"git revision {BASE} unavailable")
class FatigueTest(unittest.TestCase):
    def test_database_view_equals_the_old_table(self):
        self.assertEqual(list(ff.ALLOY_FATIGUE_DATABASE), list(OLD_FF.ALLOY_FATIGUE_DATABASE))
        for name, old in OLD_FF.ALLOY_FATIGUE_DATABASE.items():
            self.assertEqual(repr(vars(ff.ALLOY_FATIGUE_DATABASE[name])), repr(vars(old)), name)

    def test_engine_outputs_equal_the_base_blob(self):
        for name in OLD_FF.ALLOY_FATIGUE_DATABASE:
            new, old = ff.MurakamiFatigueEngine(name), OLD_FF.MurakamiFatigueEngine(name)
            for call in (lambda e: e.calculate_fatigue_limit(33.0, "surface", 0.1),
                         lambda e: e.generate_kitagawa_takahashi_curve("internal", -1.0, 25),
                         lambda e: e.simulate_paris_crack_growth(60.0, 250.0, 0.1)):
                self.assertEqual(json.dumps(call(new)), json.dumps(call(old)), name)

    def test_unknown_alloy_raises_instead_of_ti64(self):
        for name in ("X", "Unobtanium-X", "AISI 4140", None):
            with self.subTest(name=name):
                with self.assertRaises(iv.ValidationError) as ctx:
                    ff.MurakamiFatigueEngine(name)
                self.assertEqual(ctx.exception.code, iv.UNKNOWN_ALLOY)
                self.assertEqual(ctx.exception.field, "alloyName")
        self.assertEqual(OLD_FF.MurakamiFatigueEngine("X").alloy.name, "Ti-6Al-4V")

    def test_custom_alloy_needs_no_known_name(self):
        custom = ff.AlloyFatigueConstants("custom", 300.0, 400.0, 3.0, 50.0, 1e-11, 3.0)
        self.assertIs(ff.MurakamiFatigueEngine("anything", custom_alloy=custom).alloy, custom)

    def test_alias_resolves_to_own_constants(self):
        # Behaviour change: before, "IN718" silently got the Ti-6Al-4V constants.
        self.assertEqual(ff.MurakamiFatigueEngine("IN718").alloy.name, "Inconel 718")


@require_git_revision(OLD_UQ is not None, f"git revision {BASE} unavailable")
class StochasticTest(unittest.TestCase):
    def test_single_realization_equals_the_base_blob_for_every_branch(self):
        comp = {"Nb": 5.0, "Ti": 0.9, "Al": 0.5, "Zr": 0.3, "Mg": 0.1}
        for base in ("Ni", "Fe", "Ti", "Al", "Zz", None, ["Ni"]):
            args = (base, comp, 1.5e5, 720.0, 8.0, 700.0, 40.0)
            self.assertEqual(repr(uq.solve_single_realization(*args)),
                             repr(OLD_UQ.solve_single_realization(*args)), repr(base))

    def test_request_defaults_unchanged(self):
        new = _strip(uq.solve_stochastic_uq({"mcSamples": 500}))
        old = _strip(OLD_UQ.solve_stochastic_uq({"mcSamples": 500}))
        self.assertEqual(json.dumps(new), json.dumps(old))

    def test_main_adds_provenance_only(self):
        code, out = _run("stochastic_uq_mmpds_solver.py", {"mcSamples": 500})
        self.assertEqual(code, 0)
        prov = out.pop("provenance")
        self.assertEqual(prov["gasConstantR_J_molK"], 8.314)
        self.assertEqual(prov["registryVersion"], reg.REGISTRY_VERSION)
        self.assertNotIn("registryAlloyId", prov)  # alloyName is a label, never resolved
        old = _strip(OLD_UQ.solve_stochastic_uq({"mcSamples": 500}))
        self.assertEqual(json.dumps(_strip(out), sort_keys=True), json.dumps(old, sort_keys=True))


class PersistentIpcRelayTest(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        ipc = sys.modules.get("persistent_ipc_service")
        if ipc is not None:
            ipc.registry.shutdown()

    def test_kinetics_envelope_relayed(self):
        import persistent_ipc_service as ipc
        res = ipc._worker_run_script(str(HERE / "kinetics_ttt_cct_solver.py"),
                                     json.dumps({"alloy": "Unobtainium"}), [])
        self.assertEqual(res["exitCode"], 2, res.get("stderr"))
        out = json.loads(res["stdout"])
        self.assertEqual(out["errorKind"], "validation")
        self.assertEqual(out["error"]["code"], "UNKNOWN_ALLOY")
        # The ProcessPoolExecutor path submits this same _worker_run_script; it is
        # exercised by test_phase6a_migration (the module-global pool is shut down by
        # that test's tearDownClass, so it is not re-used here).


class SourceGuardTest(unittest.TestCase):
    FORBIDDEN_FLOATS = (8.314, 8.3145, 8.31446, 8.314462618, 96485.33212, 96485.33, 96485.0, 273.15,
                        265000.0)

    def test_no_constant_literals(self):
        for name in MIGRATED:
            tree = ast.parse((HERE / name).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, float):
                    self.assertNotIn(node.value, self.FORBIDDEN_FLOATS, f"{name}:{node.lineno}")

    def test_no_silent_table_fallback(self):
        for name in MIGRATED:
            src = (HERE / name).read_text(encoding="utf-8")
            self.assertNotIn("ALLOY_KINETICS_DB.get(", src)
            self.assertNotIn("ALLOY_FATIGUE_DATABASE.get(", src)
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "get" and len(node.args) == 2
                        and isinstance(node.args[1], ast.Subscript)):
                    self.fail(f"{name}:{node.lineno} uses .get(key, TABLE[...])")

    def test_lattice_and_potency_tables_moved(self):
        src = (HERE / "stochastic_uq_mmpds_solver.py").read_text(encoding="utf-8")
        for literal in ("3.585", "0.2535", "247.0", '"Nb": 14.5', '"Inconel 718 (Aero LPBF)"'):
            self.assertNotIn(literal, src)

    def test_phase9_mapping_moved(self):
        src = (HERE / "phase9_surrogate.py").read_text(encoding="utf-8")
        self.assertIn("query_mat = process_map_material_name(alloy_name)", src)
        self.assertNotIn('"Inconel 718" if alloy_name.upper()', src)


if __name__ == "__main__":
    unittest.main()
