"""Phase 6a structural migration of tafel_corrosion_rate_solver and pourbaix_solver.

Covers: registry-backed presets are value-identical to the pre-migration tables,
an unknown alloy/element is a ValidationError exactly where the old code silently
substituted a default, the stdout envelope + exit code 2 (also through the
persistent IPC runner), and a source guard against re-introduced literals.
"""

import ast
import json
import os
import subprocess
import sys
import threading
import unittest
from pathlib import Path

import input_validation as iv
import pourbaix_solver
import tafel_corrosion_rate_solver as tafel

HERE = Path(__file__).parent
SNAPSHOT_DIR = HERE / "golden" / "phase6a"
MIGRATED = ("tafel_corrosion_rate_solver.py", "pourbaix_solver.py")


def _snapshot(solver):
    path = SNAPSHOT_DIR / solver / "_source_tables.json"
    return json.loads(path.read_text(encoding="utf-8"))["values"]


def _run(script, payload):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run([sys.executable, "-B", script], input=json.dumps(payload).encode(),
                          capture_output=True, cwd=str(HERE), env=env, timeout=120)
    return proc.returncode, json.loads(proc.stdout.decode("utf-8"))


SOLVE_BASE = {"iCorr_uA_cm2": 2.0, "eCorr_V": -0.3, "betaA": 0.1, "betaC": 0.12,
              "specimenAreaCm2": 1.0, "initialThicknessMm": 5.0, "allowableLossMm": 1.5,
              "temperatureC": 30.0}
FULL_OVERRIDES = {"alloyName": "Caller alloy", "density_g_cm3": 7.5, "equivalentWeight": 25.0,
                  "activationEnergyJ_mol": 30000.0}


class TafelPresetTest(unittest.TestCase):
    def test_presets_equal_the_pre_migration_library(self):
        library = _snapshot("tafel_corrosion_rate_solver")
        self.assertEqual(len(library), 9)
        for tafel_id, old in library.items():
            with self.subTest(alloy=tafel_id):
                new = tafel.corrosion_preset(tafel_id)
                new.pop("registry_id")
                # Design step (b): "ew" is computed from the preset's own composition
                # (see test_preset_ew_equals_the_custom_composition_path); the rest is unchanged.
                self.assertEqual(new.pop("ew"), tafel.calculate_equivalent_weight(
                    old["composition"], old["valencies"], old["atomic_weights"]))
                old = {k: v for k, v in old.items() if k != "ew"}
                self.assertEqual(json.dumps(new, sort_keys=True), json.dumps(old, sort_keys=True))

    def test_preset_ew_equals_the_custom_composition_path(self):
        # Design step (b): one source. A preset alloyId, and the same alloyId with its own
        # composition sent as customComposition, give the same EW and the same output.
        library = _snapshot("tafel_corrosion_rate_solver")
        for tafel_id in library:
            with self.subTest(alloy=tafel_id):
                preset = tafel.corrosion_preset(tafel_id)
                by_id = tafel.solve_tafel_corrosion_rate(dict(SOLVE_BASE, alloyId=tafel_id))
                by_comp = tafel.solve_tafel_corrosion_rate(
                    dict(SOLVE_BASE, alloyId=tafel_id, customComposition=preset["composition"]))
                self.assertEqual(by_id["equivalentWeight"], preset["ew"])
                self.assertEqual(by_comp["equivalentWeight"], preset["ew"])
                for doc in (by_id, by_comp):
                    for key in ("durationMs", "timestamp"):
                        doc.pop(key)
                self.assertEqual(json.dumps(by_id, sort_keys=True), json.dumps(by_comp, sort_keys=True))

    def test_ts_common_alloys_mirror_the_registry(self):
        # Design step (b): src/utils/tafelParser.ts COMMON_ALLOYS density and EW are the
        # registry values (one source); duplex2205 has no registry data and must stay so.
        import re
        text = (HERE.parent / "src" / "utils" / "tafelParser.ts").read_text(encoding="utf-8")
        block = text.split("export const COMMON_ALLOYS", 1)[1].split("];", 1)[0]
        rows = re.findall(r'id: "([^"]+)".*?density: ([0-9.]+), equivalentWeight: ([0-9.]+)', block)
        self.assertEqual(len(rows), 10)
        for ui_id, density, ew in rows:
            with self.subTest(ui_id=ui_id):
                if ui_id == "duplex2205":
                    with self.assertRaises(iv.ValidationError) as ctx:
                        tafel.corrosion_preset(ui_id)
                    self.assertEqual(ctx.exception.code, iv.UNKNOWN_ALLOY)
                    continue
                preset = tafel.corrosion_preset(ui_id)
                self.assertEqual(float(density), preset["density_g_cm3"])
                self.assertEqual(float(ew), preset["ew"])
        # The client fallbacks default to the 316L preset values, not their own copies.
        self.assertIn("dataset.metadata.equivalentWeight || COMMON_ALLOYS[0].equivalentWeight", text)
        self.assertIn("dataset.metadata.density_g_cm3 || COMMON_ALLOYS[0].density", text)
        service = (HERE.parent / "src" / "services" / "pythonComputationService.ts").read_text(encoding="utf-8")
        self.assertIn(f"payload.equivalentWeight || {tafel.corrosion_preset('steel-316l')['ew']})", service)

    def test_ui_ids_now_resolve_to_their_own_preset(self):
        # TafelPolarizationLab sends src/utils/tafelParser.ts COMMON_ALLOYS ids; before
        # the migration none of them matched and all silently became AISI 316L.
        pairs = {"ss316l": "steel-316l", "ss304": "steel-304", "steel1018": "steel-1018",
                 "ti64": "ti-6al-4v", "al7075": "al-7075", "al6061": "al-6061",
                 "cu_c110": "cu-c110", "inconel718": "inconel-718", "az31b": "az31b"}
        for ui_id, tafel_id in pairs.items():
            self.assertEqual(tafel.corrosion_preset(ui_id), tafel.corrosion_preset(tafel_id), ui_id)

    def test_unknown_alloy_raises_where_the_preset_would_be_used(self):
        cases = [
            dict(SOLVE_BASE, alloyId="unobtainium-x"),
            dict(SOLVE_BASE, alloyId="duplex2205", **{k: v for k, v in FULL_OVERRIDES.items()
                                                       if k != "density_g_cm3"}),
            dict(SOLVE_BASE, alloyId="duplex2205", **{k: v for k, v in FULL_OVERRIDES.items()
                                                       if k != "activationEnergyJ_mol"}),
            dict(SOLVE_BASE, alloyId="duplex2205", **FULL_OVERRIDES,
                 customComposition={"Fe": 0.7, "Cr": 0.22, "Ni": 0.05}),
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(iv.ValidationError) as ctx:
                    tafel.solve_tafel_corrosion_rate(payload)
                self.assertEqual(ctx.exception.code, iv.UNKNOWN_ALLOY)
                self.assertEqual(ctx.exception.field, "alloyId")

    def test_unknown_alloy_is_accepted_when_nothing_is_taken_from_a_preset(self):
        out = tafel.solve_tafel_corrosion_rate(dict(SOLVE_BASE, alloyId="duplex2205", **FULL_OVERRIDES))
        self.assertTrue(out["success"])
        self.assertEqual(out["alloyName"], "Caller alloy")
        self.assertIsNone(out["provenance"]["registryAlloyId"])
        out = tafel.solve_tafel_corrosion_rate(dict(
            SOLVE_BASE, alloyId="duplex2205", **FULL_OVERRIDES,
            customComposition={"Fe": 0.7, "Cr": 0.3}, customValencies={"Fe": 2, "Cr": 3},
            customAtomicWeights={"Fe": 55.845, "Cr": 51.996}))
        self.assertTrue(out["success"])

    def test_missing_alloy_id_still_defaults_to_316l(self):
        # A documented default for an absent field is not a silent substitution.
        out = tafel.solve_tafel_corrosion_rate(dict(SOLVE_BASE))
        self.assertEqual(out["alloyId"], "steel-316l")
        self.assertEqual(out["alloyName"], "AISI 316L Stainless Steel")
        self.assertEqual(out["provenance"]["registryAlloyId"], "ss316l")

    def test_bare_grade_and_alloy_without_corrosion_data_are_refused(self):
        for name, reason in (("304", "bare-grade"), ("alsi10mg", "no-domain-data"),
                             ("AISI 4140", "no-domain-data")):
            with self.subTest(name=name):
                with self.assertRaises(iv.ValidationError) as ctx:
                    tafel.corrosion_preset(name)
                self.assertEqual(ctx.exception.code, iv.UNKNOWN_ALLOY)
                self.assertEqual(ctx.exception.detail["reason"], reason)

    def test_titanium_variants_do_not_consume_the_grade5_preset(self):
        library = _snapshot("tafel_corrosion_rate_solver")
        for name in ("ti-6al-4v", "Ti64", "Titanium Ti-6Al-4V (Grade 5)", "Ti-6Al-4V Grade 5 Titanium",
                     "ti64_ams4928", "TI6AL4V"):
            with self.subTest(accepted=name):
                preset = tafel.corrosion_preset(name.lower())
                self.assertEqual(preset["composition"], library["ti-6al-4v"]["composition"])
                self.assertEqual(preset["density_g_cm3"], library["ti-6al-4v"]["density_g_cm3"])
                self.assertEqual(preset["ew"], 11.8715)  # computed (design step (b)); stored was 11.97
        for name in ("Ti-6Al-4V ELI", "ti-6al-4v eli", "Ti-6Al-4V ELI Grade 23", "Ti6Al4V ELI"):
            with self.subTest(rejected=name):
                with self.assertRaises(iv.ValidationError) as ctx:
                    tafel.corrosion_preset(name.lower())
                self.assertEqual(ctx.exception.code, iv.UNKNOWN_ALLOY)
                self.assertEqual(ctx.exception.detail["reason"], "variant-without-preset")
                self.assertIn("Grade 5", ctx.exception.message)
                with self.assertRaises(iv.ValidationError):
                    tafel.solve_tafel_corrosion_rate(dict(SOLVE_BASE, alloyId=name))
                # The full caller-supplied property set never consults the preset.
                out = tafel.solve_tafel_corrosion_rate(dict(SOLVE_BASE, alloyId=name, **FULL_OVERRIDES))
                self.assertTrue(out["success"])
                self.assertIsNone(out["provenance"]["registryAlloyId"])
        code, out = _run("tafel_corrosion_rate_solver.py", {"alloyId": "Ti-6Al-4V ELI"})
        self.assertEqual(code, 2)
        self.assertEqual(out["error"]["detail"]["reason"], "variant-without-preset")

    def test_fit_curve_unknown_alloy_raises(self):
        points = [{"potential": -0.5 + 0.05 * i, "currentDensity_uA_cm2": 1.0 + abs(i - 5)} for i in range(11)]
        with self.assertRaises(iv.ValidationError):
            tafel.fit_tafel_curve({"points": points, "alloyId": "unobtainium-x"})
        out = tafel.fit_tafel_curve({"points": points, "alloyId": "unobtainium-x",
                                     "alloyName": "x", "density_g_cm3": 7.0, "equivalentWeight": 20.0})
        self.assertTrue(out["success"])


class PourbaixElementTest(unittest.TestCase):
    def test_supported_elements_still_solve(self):
        for el in pourbaix_solver.POURBAIX_ELEMENT_SYSTEMS:
            with self.subTest(element=el):
                out = pourbaix_solver.solve_pourbaix_diagram(el, 25.0, -6.0, 0.0, [])
                self.assertEqual(out["element"], el)

    def test_unknown_or_non_string_element_raises(self):
        for el in ("Unobtainium", "fe", "Mo", "", None, ["Fe"]):
            with self.subTest(element=el):
                with self.assertRaises(iv.ValidationError) as ctx:
                    pourbaix_solver.solve_pourbaix_diagram(el, 25.0, -6.0, 0.0, [])
                self.assertEqual(ctx.exception.code, iv.UNKNOWN_ELEMENT)
                self.assertEqual(ctx.exception.field, "element")


class EnvelopeTest(unittest.TestCase):
    def test_tafel_validation_envelope_exit_2(self):
        code, out = _run("tafel_corrosion_rate_solver.py", {"alloyId": "unobtainium-x"})
        self.assertEqual(code, 2)
        self.assertEqual(out["errorKind"], "validation")
        self.assertIs(out["success"], False)
        self.assertEqual(out["error"]["code"], "UNKNOWN_ALLOY")
        self.assertEqual(set(out["error"]), {"code", "field", "message", "detail"})

    def test_tafel_internal_error_exit_1(self):
        code, out = _run("tafel_corrosion_rate_solver.py", {"action": "fit_curve", "points": [{"potential": 0}]})
        self.assertEqual(code, 1)
        self.assertEqual(out["errorKind"], "internal")
        self.assertIn("minimum of 5", out["error"])

    def test_pourbaix_validation_envelope_exit_2(self):
        code, out = _run("pourbaix_solver.py", {"element": "Xx"})
        self.assertEqual(code, 2)
        self.assertEqual(out["errorKind"], "validation")
        self.assertEqual(out["error"]["code"], "UNKNOWN_ELEMENT")

    def test_pourbaix_internal_error_exit_1(self):
        code, out = _run("pourbaix_solver.py", {"element": "Fe", "temperature_C": "hot"})
        self.assertEqual(code, 1)
        self.assertEqual(out["errorKind"], "internal")


class PersistentIpcRelayTest(unittest.TestCase):
    """The envelope and exit code 2 pass through persistent_ipc_service unchanged.

    Importing persistent_ipc_service builds its global ConcurrentModuleRegistry
    (warm imports + a ProcessPoolExecutor); it is shut down after these tests.
    """

    @classmethod
    def tearDownClass(cls):
        ipc = sys.modules.get("persistent_ipc_service")
        if ipc is not None:
            ipc.registry.shutdown()

    def test_real_process_pool_path(self):
        import persistent_ipc_service as ipc
        # Own registry: another test module may already have shut the global pool down.
        own = ipc.ConcurrentModuleRegistry(ipc.SCRIPT_DIR, num_workers=1)
        try:
            res = own.execute_script("python/tafel_corrosion_rate_solver.py",
                                     {"alloyId": "unobtainium-x"}, [], 60000)
            self.assertEqual(res["concurrency"], "process_pool")
            self._assert_envelope(res, "UNKNOWN_ALLOY")
            res = own.execute_script("python/pourbaix_solver.py", {"element": "Xx"}, [], 60000)
            self.assertEqual(res["concurrency"], "process_pool")
            self._assert_envelope(res, "UNKNOWN_ELEMENT")
        finally:
            own.shutdown()

    def _assert_envelope(self, res, code):
        self.assertEqual(res["exitCode"], 2, res.get("stderr"))
        out = json.loads(res["stdout"])
        self.assertEqual(out["errorKind"], "validation")
        self.assertEqual(out["error"]["code"], code)

    def test_pool_worker_path(self):
        import persistent_ipc_service as ipc
        res = ipc._worker_run_script(str(HERE / "tafel_corrosion_rate_solver.py"),
                                     json.dumps({"alloyId": "unobtainium-x"}), [])
        self._assert_envelope(res, "UNKNOWN_ALLOY")
        res = ipc._worker_run_script(str(HERE / "pourbaix_solver.py"), json.dumps({"element": "Xx"}), [])
        self._assert_envelope(res, "UNKNOWN_ELEMENT")
        ok = ipc._worker_run_script(str(HERE / "pourbaix_solver.py"), json.dumps({"element": "Fe"}), [])
        self.assertEqual(ok["exitCode"], 0)
        self.assertTrue(json.loads(ok["stdout"])["success"])

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
        registry.pool = None  # forces the in-process fallback branch
        res = registry.execute_script("python/tafel_corrosion_rate_solver.py", {"alloyId": "unobtainium-x"})
        self.assertEqual(res["concurrency"], "in_process_fallback")
        self._assert_envelope(res, "UNKNOWN_ALLOY")
        res = registry.execute_script("python/pourbaix_solver.py", {"element": "Xx"})
        self._assert_envelope(res, "UNKNOWN_ELEMENT")


class SourceGuardTest(unittest.TestCase):
    """Migrated files must not re-introduce constant literals or silent fallbacks."""

    FORBIDDEN_FLOATS = (8.314, 8.3145, 8.31446, 8.314462618, 96485.33212, 96485.33, 96485.0, 273.15)

    def test_no_constant_literals(self):
        for name in MIGRATED:
            tree = ast.parse((HERE / name).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, float):
                    self.assertNotIn(node.value, self.FORBIDDEN_FLOATS, f"{name}:{node.lineno}")

    def test_no_silent_table_fallback(self):
        tafel_src = (HERE / "tafel_corrosion_rate_solver.py").read_text(encoding="utf-8")
        self.assertNotIn("ALLOY_LIBRARY", tafel_src)
        pourbaix_src = (HERE / "pourbaix_solver.py").read_text(encoding="utf-8")
        self.assertNotIn('POURBAIX_ELEMENT_SYSTEMS.get(', pourbaix_src)
        for name in MIGRATED:
            tree = ast.parse((HERE / name).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                # .get(<key>, TABLE[...]) is the silent-default pattern of the design.
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "get" and len(node.args) == 2
                        and isinstance(node.args[1], ast.Subscript)):
                    self.fail(f"{name}:{node.lineno} uses .get(key, TABLE[...])")

    def test_atomic_masses_come_from_physical_constants(self):
        src = (HERE / "pourbaix_solver.py").read_text(encoding="utf-8")
        self.assertEqual(src.count('"atomicMass": physical_constants.atomic_weight('), 8)


if __name__ == "__main__":
    unittest.main()
