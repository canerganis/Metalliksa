"""Phase 6a tranche 2a: structural migration of calphad, battery EIS and icme solvers.

Covers: bit-exact golden regression for the three solvers, parity with the
pre-migration blob on extra payloads, the calphad legacy 50.0 g/mol element
fallback kept in step (a) (fix round B1), the icme validation errors that replace the
silent element/base-metal defaults (and only those), the stdout envelope + exit
code 2 (also through the persistent IPC runner), provenance, the pinned
pre-existing battery success:true masking, and a source guard.
"""

import ast
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "tools"))

import capture_phase6a_golden as golden  # noqa: E402
import drift_report  # noqa: E402
import phase6a_cases_t2a as cases  # noqa: E402

import alloy_data_calphad_battery_icme as data  # noqa: E402
import calphad_solver  # noqa: E402
import icme_multiscale_pipeline_solver as icme  # noqa: E402
import input_validation as iv  # noqa: E402
import physical_constants as pc  # noqa: E402
from phase6a_test_support import require_git_revision  # noqa: E402

SOLVERS = ("calphad_solver", "battery_corrosion_eis_solver", "icme_multiscale_pipeline_solver")
TRANCHE2_BASE = "7f3f803"


def _run(script, payload):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run([sys.executable, "-B", script], input=json.dumps(payload).encode(),
                          capture_output=True, cwd=str(HERE), env=env, timeout=180)
    return proc.returncode, json.loads(proc.stdout.decode("utf-8"))


def _git_available() -> bool:
    try:
        golden.solver_bytes("calphad_solver", TRANCHE2_BASE)
        golden.solver_bytes("calphad_solver", golden.BASE_REVISION)
        return True
    except Exception:
        return False


class GoldenRegressionTest(unittest.TestCase):
    maxDiff = None

    def _check(self, solver, case):
        doc = golden.load_golden(solver, case)
        self.assertEqual(golden.canonical(doc["input"]), golden.canonical(cases.CASES[solver][case]))
        # Stored input text must equal the payload text (order-sensitive solvers).
        self.assertEqual(json.dumps(doc["input"]), json.dumps(cases.CASES[solver][case]))
        fresh = golden.run_solver(solver, doc["input"])
        expected_code = cases.EXPECTED_BEHAVIOUR_CHANGES.get((solver, case))
        if expected_code is not None:
            self.assertEqual(fresh["exitCode"], 2, fresh["stderr"])
            out = fresh["stdout"]
            self.assertEqual(set(out), {"success", "error", "errorKind"})
            self.assertIs(out["success"], False)
            self.assertEqual(out["errorKind"], "validation")
            self.assertEqual(out["error"]["code"], expected_code)
            self.assertIsNone(fresh["provenance"])
            # The old golden is the record of the silent default.
            self.assertEqual(doc["exitCode"], 0)
            self.assertIs(doc["stdout"].get("success"), True)
            return
        self.assertEqual(fresh["exitCode"], doc["exitCode"], fresh["stderr"])
        rows = drift_report.diff(doc["stdout"], fresh["stdout"])
        self.assertEqual(rows, [], drift_report.render(f"{solver}/{case}", rows, 20))
        self.assertEqual(golden.canonical(fresh["stdout"]), golden.canonical(doc["stdout"]))

    def test_case_counts(self):
        for solver in SOLVERS:
            self.assertGreaterEqual(len(cases.CASES[solver]), 3)
            self.assertLessEqual(len(cases.CASES[solver]), 5)
            self.assertIn(solver, golden.CASES)

    def test_calphad_solver(self):
        for case in cases.CASES["calphad_solver"]:
            with self.subTest(case=case):
                self._check("calphad_solver", case)

    def test_battery_corrosion_eis_solver(self):
        for case in cases.CASES["battery_corrosion_eis_solver"]:
            with self.subTest(case=case):
                self._check("battery_corrosion_eis_solver", case)

    def test_icme_multiscale_pipeline_solver(self):
        for case in cases.CASES["icme_multiscale_pipeline_solver"]:
            with self.subTest(case=case):
                self._check("icme_multiscale_pipeline_solver", case)

    def test_volatile_duration_key_is_stripped(self):
        doc = golden.load_golden("battery_corrosion_eis_solver", "p2d_continuum_nmc811")
        self.assertNotIn("pythonDurationMs", json.dumps(doc["stdout"]))
        self.assertIn("pythonDurationMs", golden.VOLATILE_KEYS)


@require_git_revision(_git_available(), "git or base revisions d33b6f5/7f3f803 unavailable")
class BaseBlobTest(unittest.TestCase):
    """The pre-migration blob vs the migrated solver on payloads outside the golden set."""

    PARITY = {
        "battery_corrosion_eis_solver": [
            {"action": "bernardi_thermal", "cellFormat": "4680-tabless", "nominalCapAh": 22.0,
             "cRate": 2.0, "coolingType": "bottom_cold_plate", "tempAmbientC": 30.0},
            {"action": "corrosion_kinetics", "metalId": "al-7075", "i0Corr_uA": 1.85, "ePit": -0.68, "e0": -1.66},
            {"action": "lli_lam_deconvolution", "chemistryId": "nmc811", "initialCapAh": 5.0, "degradedCapAh": 4.2},
            {"action": "drt", "frequencies": cases._EIS_F, "zReal": cases._EIS_ZR, "zImag": cases._EIS_ZI},
            {"action": "p2d_continuum", "chemistryId": "lfp", "cRate": 0.5, "tempC": 45.0, "soc": 0.2},
        ],
        "calphad_solver": [
            {"action": "list_databases"},
            {"elements": {"Co": 60.0, "Cr": 28.0, "Mo": 6.0, "W": 6.0}, "tMin": 900.0, "tMax": 1500.0, "tStep": 40.0},
            {"elements": {"Al": 50.0, "Ni": 50.0}, "unit": "at_pct", "tMin": 900.0, "tMax": 1700.0, "tStep": 50.0},
            {"elements": {"Cu": 70.0, "Zn": 30.0}, "tMin": 700.0, "tMax": 1100.0, "tStep": 25.0},
            # Legacy 50.0 g/mol fallback kept in step (a) (fix round B1): unknown elements
            # with positive amounts must give the pre-migration output, in both units.
            {"elements": {"Fe": 90.0, "P": 5.0, "Sn": 5.0}},
            {"elements": {"Cu": 83.0, "Sn": 7.0, "Pb": 7.0, "Zn": 3.0}, "unit": "at_pct",
             "tMin": 700.0, "tMax": 1200.0, "tStep": 50.0},
            {"elements": {"Ni": 70.0, "Xx": 30.0}, "customTdbText": "ELEMENT XX BLANK 0 0 0 !"},
        ],
        "icme_multiscale_pipeline_solver": [
            {"baseMetal": "Fe", "composition_wt": {"C": 0.2, "Cr": 12.0, "Mo": 1.0, "V": 0.3, "W": 0.5},
             "grainSize_um": 12.0, "coolingRate_C_s": 50.0, "componentType": "pressure_bulkhead"},
            {"baseMetal": "Al", "composition_wt": {"Zn": 5.6, "Mg": 2.5, "Cu": 1.6, "Co": 0.0}},
            {"baseMetal": "Ni", "composition_wt": {"Cr": 16.0, "Co": 8.5, "W": 2.6, "Al": 3.4, "Ti": 3.4},
             "agingTemp_C": 850, "agingTime_h": 24, "serviceTemp_C": 650},
        ],
    }

    def _base(self, solver, payload):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / f"{solver}.py"
            script.write_bytes(golden.solver_bytes(solver, TRANCHE2_BASE))
            return golden.run_solver(solver, payload, script=script)

    def test_solvers_are_identical_at_d33b6f5_and_7f3f803(self):
        for solver in SOLVERS:
            self.assertEqual(golden.normalised_sha256(golden.solver_bytes(solver, TRANCHE2_BASE)),
                             golden.normalised_sha256(golden.solver_bytes(solver, golden.BASE_REVISION)))
            self.assertEqual(golden.load_golden(solver, next(iter(cases.CASES[solver])))["gitHead"][:7],
                             TRANCHE2_BASE)

    def test_extra_payloads_match_the_base_blob(self):
        for solver, payloads in self.PARITY.items():
            for payload in payloads:
                with self.subTest(solver=solver, payload=payload):
                    old = self._base(solver, payload)
                    new = golden.run_solver(solver, payload)
                    self.assertEqual(new["exitCode"], old["exitCode"], new["stderr"])
                    rows = drift_report.diff(old["stdout"], new["stdout"])
                    self.assertEqual(rows, [], drift_report.render(solver, rows, 10))

    def test_changed_inputs_succeeded_with_a_default_before(self):
        changed = [
            ("icme_multiscale_pipeline_solver", {"baseMetal": "Co", "composition_wt": {"Cr": 20.0}}),
            ("icme_multiscale_pipeline_solver", {"baseMetal": "Ni", "composition_wt": {"cr": 19.0}}),
        ]
        for solver, payload in changed:
            with self.subTest(solver=solver, payload=payload):
                old = self._base(solver, payload)
                self.assertEqual(old["exitCode"], 0)
                self.assertIs(old["stdout"]["success"], True)
                new = golden.run_solver(solver, payload)
                self.assertEqual(new["exitCode"], 2)
                self.assertEqual(new["stdout"]["error"]["code"], "UNKNOWN_ELEMENT")

    def test_source_tables_are_bound_to_the_base_blob(self):
        for solver in cases.SOURCE_TABLES:
            doc = json.loads((golden.GOLDEN_DIR / solver / golden.SOURCE_TABLES_FILE).read_text(encoding="utf-8"))
            self.assertEqual(doc["solverSha256"],
                             golden.normalised_sha256(golden.solver_bytes(solver, golden.BASE_REVISION)))
            values = {name: cases._literal_assignment(golden.solver_bytes(solver, TRANCHE2_BASE), fn, name)
                      for fn, name in cases.SOURCE_TABLES[solver]}
            self.assertEqual(golden.canonical(values), golden.canonical(doc["values"]))


# src/data/materialsDatabase.ts:10 and :111 (AISI 1018-type and AISI 4140-type
# specimens): P and S at positive amounts, sent as-is by CALPHADMultiComponentStudio.
P_S_SPECIMENS = (
    {"C": 0.18, "Mn": 0.75, "P": 0.04, "S": 0.05, "Fe": 98.98},
    {"C": 0.40, "Cr": 1.00, "Mo": 0.20, "Mn": 0.85, "Si": 0.25, "P": 0.035, "S": 0.04, "Fe": 97.225},
)


class CalphadElementTest(unittest.TestCase):
    def test_unknown_elements_use_the_legacy_fallback(self):
        # Fix round B1: refusing these made UI specimens lose the Python engine.
        self.assertEqual(data.CALPHAD_LEGACY_UNKNOWN_ELEMENT_WEIGHT_G_MOL, 50.0)
        for elements in ({"Ni": 70, "Xx": 30}, {"Fe": 95, "P": 5}, {"Ti": 90, "Sn": 10},
                         {"Ni": 90, "": 10}, {"Cu": 60, "Pb": 40}):
            for unit in ("wt_pct", "at_pct"):
                with self.subTest(elements=elements, unit=unit):
                    wt, at = calphad_solver.normalize_composition(elements, unit)
                    self.assertEqual(len(wt), 2)
                    self.assertAlmostEqual(sum(at.values()), 1.0, places=12)
        self.assertEqual(calphad_solver._atomic_weight("P"), 50.0)
        self.assertEqual(calphad_solver._atomic_weight("Fe"), 55.845)
        self.assertEqual(calphad_solver.legacy_fallback_elements(["Fe", "P", "S", "C"]), ["P", "S"])

    def test_p_and_s_specimens_get_a_normal_python_result(self):
        for elements in P_S_SPECIMENS:
            with self.subTest(elements=elements):
                code, out = _run("calphad_solver.py", {"name": "steel", "elements": elements,
                                                       "tMin": 500.0, "tMax": 1600.0, "tStep": 50.0})
                self.assertEqual(code, 0)
                self.assertIs(out["success"], True)
                self.assertTrue(out["equilibriumProfile"])  # what the UI requires
                self.assertNotIn("errorKind", out)
                self.assertEqual(out["engine"], "subregular-adaptive-minimizer")
                fallback = out["provenance"]["legacyAtomicWeightFallback"]
                self.assertEqual(fallback["elements"], ["P", "S"])
                self.assertEqual(fallback["weight_g_mol"], 50.0)
                self.assertIn("step (b)", fallback["note"])

    def test_custom_tdb_text_is_not_refused(self):
        code, out = _run("calphad_solver.py", {"elements": {"Ni": 70.0, "Xx": 30.0},
                                               "customTdbText": "ELEMENT XX BLANK 0 0 0 !"})
        self.assertEqual(code, 0)
        self.assertIs(out["success"], True)
        self.assertEqual(out["provenance"]["legacyAtomicWeightFallback"]["elements"], ["Xx"])

    def test_known_elements_report_no_fallback(self):
        fresh = golden.run_solver("calphad_solver", cases.CASES["calphad_solver"]["in718_wt_pct"])
        self.assertEqual(fresh["provenance"]["provenance"]["legacyAtomicWeightFallback"]["elements"], [])

    def test_case_variants_and_zero_amounts_are_unchanged(self):
        wt, at = calphad_solver.normalize_composition({"ni": 50.0, "CR": 50.0, "Xx": 0, "Yy": None})
        self.assertEqual(set(wt), {"Ni", "Cr"})
        # Empty input keeps its documented default.
        wt, _ = calphad_solver.normalize_composition({})
        self.assertEqual(wt, {"Ni": 80.0, "Al": 10.0, "Cr": 10.0})

    def test_atomic_weights_and_r(self):
        self.assertEqual(calphad_solver.GAS_CONSTANT_R, pc.TRUNCATED_GAS_CONSTANT_R)
        self.assertEqual(list(calphad_solver.ATOMIC_WEIGHTS), list(data.CALPHAD_ELEMENTS))


class IcmeElementTest(unittest.TestCase):
    def test_unknown_solute_raises_only_when_it_is_weighted(self):
        for comp in ({"Cr": 19.0, "Zr": 0.5}, {"cr": 19.0}, {"Hf": 0.0005}):
            with self.subTest(comp=comp):
                with self.assertRaises(iv.ValidationError) as ctx:
                    icme.solve_multiscale_pipeline({"baseMetal": "Ni", "composition_wt": comp})
                self.assertEqual(ctx.exception.code, iv.UNKNOWN_ELEMENT)
                self.assertTrue(ctx.exception.field.startswith("composition_wt."))
                self.assertEqual(ctx.exception.detail["reason"], "no-icme-atomic-weight")
        # A zero amount never consulted the 55.0 fallback, so it is still accepted.
        out = icme.solve_multiscale_pipeline({"baseMetal": "Ni", "composition_wt": {"Cr": 19.0, "Zr": 0.0}})
        self.assertTrue(out["success"])

    def test_unknown_base_metal_raises(self):
        for base in ("Co", "Cu", "Mg", "ni", "Xx", None):
            with self.subTest(base=base):
                with self.assertRaises(iv.ValidationError) as ctx:
                    icme.solve_multiscale_pipeline({"baseMetal": base, "composition_wt": {"Cr": 10.0}})
                self.assertEqual(ctx.exception.field, "baseMetal")
                self.assertEqual(ctx.exception.detail["reason"], "no-icme-base-data")
                self.assertEqual(ctx.exception.detail["supported"], ["Ni", "Fe", "Ti", "Al"])

    def test_supported_bases_and_t_melt(self):
        for base, t_melt in (("Ni", 1350.0), ("Fe", 1450.0), ("Ti", 1650.0), ("Al", 660.0)):
            out = icme.solve_multiscale_pipeline({"baseMetal": base, "composition_wt": {"Cr": 1.0}})
            self.assertEqual(out["scale3_continuumPlasticity"]["johnsonCookParameters"]["T_melt_C"], t_melt)

    def test_default_composition_comes_from_the_registry(self):
        comp = icme._default_composition_wt()
        self.assertEqual(list(comp), ["Cr", "Fe", "Nb", "Mo", "Ti", "Al", "C", "Si", "Mn"])
        comp["Cr"] = 0.0  # a fresh copy each call; the registry value is untouched
        self.assertEqual(icme._default_composition_wt()["Cr"], 19.0)


class EnvelopeAndProvenanceTest(unittest.TestCase):
    def test_calphad_internal_error(self):
        # calphad has no validation refusal in step (a) (legacy element fallback kept).
        code, out = _run("calphad_solver.py", {"elements": {"Ni": 80}, "tMin": "cold"})
        self.assertEqual(code, 1)
        self.assertEqual(out["errorKind"], "internal")
        self.assertIs(out["success"], False)

    def test_icme_envelope_and_internal_error(self):
        code, out = _run("icme_multiscale_pipeline_solver.py", {"baseMetal": "Co"})
        self.assertEqual(code, 2)
        self.assertEqual(out["error"]["field"], "baseMetal")
        code, out = _run("icme_multiscale_pipeline_solver.py", {"coolingRate_C_s": "fast"})
        self.assertEqual(code, 1)
        self.assertEqual(out["errorKind"], "internal")

    def test_battery_internal_error_and_pinned_success_masking(self):
        code, out = _run("battery_corrosion_eis_solver.py", {"action": "p2d_continuum", "tempC": "warm"})
        self.assertEqual(code, 1)
        self.assertEqual(out["errorKind"], "internal")
        # Pre-existing masking, deliberately unchanged in step (a).
        code, out = _run("battery_corrosion_eis_solver.py", {"action": "no_such_action"})
        self.assertEqual(code, 0)
        self.assertIs(out["success"], True)
        self.assertIn("Unknown action", out["error"])
        self.assertNotIn("provenance", out)

    def test_provenance(self):
        fresh = golden.run_solver("calphad_solver", cases.CASES["calphad_solver"]["in718_wt_pct"])
        prov = fresh["provenance"]["provenance"]
        self.assertEqual(prov["gasConstantR_J_molK"], pc.TRUNCATED_GAS_CONSTANT_R)
        self.assertEqual(prov["constantsVersion"], pc.CONSTANTS_VERSION)
        self.assertEqual(prov["domainDataVersion"], data.DATA_VERSION)
        fresh = golden.run_solver("icme_multiscale_pipeline_solver", {})
        prov = fresh["provenance"]["provenance"]
        self.assertEqual(prov["gasConstantR_J_molK"], 8.314)
        self.assertEqual(prov["domainDataVersion"], data.DATA_VERSION)
        fresh = golden.run_solver("battery_corrosion_eis_solver", cases.CASES["battery_corrosion_eis_solver"]["nernst_planck_poisson"])
        self.assertEqual(fresh["provenance"]["provenance"]["constantsVersion"], pc.CONSTANTS_VERSION)


class PersistentIpcRelayTest(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        ipc = sys.modules.get("persistent_ipc_service")
        if ipc is not None:
            ipc.registry.shutdown()

    def _assert_envelope(self, res):
        self.assertEqual(res["exitCode"], 2, res.get("stderr"))
        out = json.loads(res["stdout"])
        self.assertEqual(out["errorKind"], "validation")
        self.assertEqual(out["error"]["code"], "UNKNOWN_ELEMENT")

    def test_pool_worker_and_process_pool_paths(self):
        import persistent_ipc_service as ipc
        self._assert_envelope(ipc._worker_run_script(
            str(HERE / "icme_multiscale_pipeline_solver.py"), json.dumps({"baseMetal": "Co"}), []))
        # Own registry: another test module may already have shut the global pool down.
        own = ipc.ConcurrentModuleRegistry(ipc.SCRIPT_DIR, num_workers=1)
        try:
            res = own.execute_script("python/icme_multiscale_pipeline_solver.py",
                                     {"composition_wt": {"Zr": 1.0}}, [], 60000)
        finally:
            own.shutdown()
        self.assertEqual(res["concurrency"], "process_pool")
        self._assert_envelope(res)

    def test_in_process_fallback_path(self):
        import persistent_ipc_service as ipc
        registry = object.__new__(ipc.ConcurrentModuleRegistry)
        registry.script_dir = str(HERE)
        registry.compiled_code = {}
        registry.stats_lock = threading.Lock()
        registry.fallback_lock = threading.Lock()
        registry.request_count = 0
        registry.active_jobs = 0
        registry.total_duration_ms = 0.0
        registry.pool = None
        res = registry.execute_script("python/icme_multiscale_pipeline_solver.py", {"baseMetal": "Co"})
        self.assertEqual(res["concurrency"], "in_process_fallback")
        self._assert_envelope(res)


class SourceGuardTest(unittest.TestCase):
    FORBIDDEN_FLOATS = (8.314, 8.3145, 8.31446, 8.314462618, 96485.33212, 96485.33, 96485.332,
                        96485.0, 273.15)
    FILES = tuple(f"{s}.py" for s in SOLVERS)

    def _tree(self, name):
        return ast.parse((HERE / name).read_text(encoding="utf-8"))

    def test_no_constant_literals(self):
        for name in self.FILES:
            for node in ast.walk(self._tree(name)):
                if isinstance(node, ast.Constant) and isinstance(node.value, float):
                    self.assertNotIn(node.value, self.FORBIDDEN_FLOATS, f"{name}:{node.lineno}")

    def test_no_numeric_atomic_weight_fallbacks(self):
        src = (HERE / "icme_multiscale_pipeline_solver.py").read_text(encoding="utf-8")
        for pattern in ("atomic_weights.get(", "atomic_weights = {"):
            self.assertNotIn(pattern, src)
        # calphad keeps exactly one, named, legacy fallback (fix round B1).
        src = (HERE / "calphad_solver.py").read_text(encoding="utf-8")
        self.assertEqual(src.count("ATOMIC_WEIGHTS.get("), 1)
        self.assertIn("ATOMIC_WEIGHTS.get(el, CALPHAD_LEGACY_UNKNOWN_ELEMENT_WEIGHT_G_MOL)", src)
        self.assertNotIn("50.0)", src.split("def _atomic_weight", 1)[1].split("def legacy_fallback_elements", 1)[0])

    def test_no_table_fallback_pattern_in_calphad_and_icme(self):
        # battery_corrosion_eis_solver keeps ELECTROLYTE_FORMULATIONS.get(id, TABLE[...]) and
        # specs.get(fmt, specs[...]); icme keeps component_catalog.get(componentType, ...).
        # Neither is an alloy/element name; both are listed for step (b).
        allowed = {("icme_multiscale_pipeline_solver.py", "component_catalog")}
        for name in ("calphad_solver.py", "icme_multiscale_pipeline_solver.py"):
            for node in ast.walk(self._tree(name)):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "get" and len(node.args) == 2
                        and isinstance(node.args[1], ast.Subscript)):
                    table = getattr(node.func.value, "id", None)
                    if (name, table) not in allowed:
                        self.fail(f"{name}:{node.lineno} uses .get(key, TABLE[...])")


if __name__ == "__main__":
    unittest.main()
