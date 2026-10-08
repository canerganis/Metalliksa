"""Phase 6a tranche 2a: structural migration of calphad_solver.

Covers: bit-exact golden regression for the three solvers, parity with the
pre-migration blob on extra payloads, the calphad legacy 50.0 g/mol element
fallback kept in step (a) (fix round B1), the stdout envelope + exit
code 2 (also through the persistent IPC runner), provenance, the pinned
and a source guard.
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
import input_validation as iv  # noqa: E402
import physical_constants as pc  # noqa: E402
from phase6a_test_support import require_git_revision  # noqa: E402

SOLVERS = ("calphad_solver",)
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
        expected_code = cases.EXPECTED_BEHAVIOUR_CHANGES.get((solver, case))
        if (cases.EXPECTED_UNAVAILABLE_CHANGES.get((solver, case)) is not None
                and expected_code is None and calphad_solver.PYCALPHAD_AVAILABLE):
            # Decide before solving: with pycalphad this case is a real (minutes-long) equilibrium that
            # this golden never covers; the golden freezes the no-pycalphad 'unavailable' envelope.
            self.skipTest("pycalphad is importable: this interpreter takes the real path; the golden "
                          "freezes the no-pycalphad 'unavailable' envelope of the locked interpreter")
        fresh = golden.run_solver(solver, doc["input"])
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
        expected_unavailable = cases.EXPECTED_UNAVAILABLE_CHANGES.get((solver, case))
        if expected_unavailable is not None:
            # fx-calphad: the removed non-thermodynamic fallback. The old golden stays as the
            # record (exit 0, success true, engine "subregular-adaptive-minimizer", isEmpirical false).
            self.assertEqual(doc["exitCode"], 0)
            self.assertIs(doc["stdout"]["success"], True)
            self.assertEqual(doc["stdout"]["engine"], "subregular-adaptive-minimizer")
            self.assertIs(doc["stdout"]["isEmpirical"], False)
            self.assertEqual(fresh["exitCode"], 0, fresh["stderr"])
            out = fresh["stdout"]
            for key, value in expected_unavailable.items():
                self.assertEqual(out[key], value, key)
            # no number of any kind: nothing to mistake for a CALPHAD result
            for absent in ("equilibriumProfile", "criticalTemperatures", "isEmpirical", "multiElementScheil",
                           "solutePartitioning", "phacompAnalysis"):
                self.assertNotIn(absent, out)
            # the request echo is pinned exactly too (not only its keys)
            payload = cases.CASES[solver][case]
            self.assertEqual(out["alloyName"], payload["name"])
            self.assertEqual(out["temperatureRangeC"], [payload["tMin"], payload["tMax"]])
            self.assertEqual(out["temperatureStepC"], payload["tStep"])
            self.assertEqual(out["nominalComposition"], doc["stdout"]["nominalComposition"])
            self.assertEqual(out["atomicFractions"], doc["stdout"]["atomicFractions"])
            self.assertEqual(out["requestedElements"], list(out["atomicFractions"]))
            self.assertEqual(set(out), set(expected_unavailable) | {
                "alloyName", "nominalComposition", "atomicFractions", "requestedElements",
                "temperatureRangeC", "temperatureStepC"})
            return
        if (solver, case) in cases.EXPECTED_SUCCESS_FLAG_CHANGES:
            # The old golden records success:true next to an error; only that flag flips.
            self.assertIs(doc["stdout"]["success"], True)
            self.assertIn("error", doc["stdout"])
            self.assertEqual(fresh["exitCode"], doc["exitCode"], fresh["stderr"])
            self.assertIs(fresh["stdout"]["success"], False)
            self.assertEqual(golden.canonical(fresh["stdout"]),
                             golden.canonical({**doc["stdout"], "success": False}))
            return
        # Design step (b): compare with the re-blessed expectation when one exists.
        expected = golden.load_expected(solver, case)
        self.assertEqual(fresh["exitCode"], expected["exitCode"], fresh["stderr"])
        rows = drift_report.diff(expected["stdout"], fresh["stdout"])
        self.assertEqual(rows, [], drift_report.render(f"{solver}/{case}", rows, 20))
        self.assertEqual(golden.canonical(fresh["stdout"]), golden.canonical(expected["stdout"]))

    def test_case_counts(self):
        for solver in SOLVERS:
            self.assertGreaterEqual(len(cases.CASES[solver]), 3)
            self.assertLessEqual(len(cases.CASES[solver]), 5)
            self.assertIn(solver, golden.CASES)

    def test_calphad_solver(self):
        for case in cases.CASES["calphad_solver"]:
            with self.subTest(case=case):
                self._check("calphad_solver", case)

@require_git_revision(_git_available(), "git or base revisions d33b6f5/7f3f803 unavailable")
class BaseBlobTest(unittest.TestCase):
    """The pre-migration blob vs the migrated solver on payloads outside the golden set."""

    PARITY: dict = {}
    # calphad_solver left PARITY with the fallback removal (fx-calphad): its success output no
    # longer exists on the locked interpreter. What is still comparable (the wt%/at%
    # composition, the element refusal) is checked against the same base blob in
    # test_calphad_composition_still_matches_the_base_blob_apart_from_the_weights.
    # The check keeps the output structure and exit code identical and bounds the numeric drift.
    VALUE_STEP_DRIFT: dict = {}
    # Largest |relative| drift seen on the payloads above is 2.7e-3 (last printed digit).
    VALUE_STEP_MAX_REL = 1e-2

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

    def test_value_step_payloads_drift_only_numerically_and_boundedly(self):
        for solver, payloads in self.VALUE_STEP_DRIFT.items():
            for payload in payloads:
                with self.subTest(solver=solver, payload=payload):
                    old = self._base(solver, payload)
                    new = golden.run_solver(solver, payload)
                    self.assertEqual(new["exitCode"], old["exitCode"], new["stderr"])
                    rows = drift_report.diff(old["stdout"], new["stdout"])
                    self.assertTrue(rows)  # the value change is visible here
                    self.assertEqual(golden.step_b_violations(solver, rows, new["stdout"], payload), [],
                                     drift_report.render(solver, rows, 10))
                    rows = [r for r in rows if not golden._is_documented_change_row(solver, r["key"])]
                    self.assertLessEqual({r["kind"] for r in rows}, {"numeric"},
                                         drift_report.render(solver, rows, 10))
                    worst = max([abs(r["rel"]) for r in rows if r["rel"] is not None], default=0.0)
                    self.assertLessEqual(worst, self.VALUE_STEP_MAX_REL)

    def test_changed_inputs_succeeded_with_a_default_before(self):
        changed = [
            # Design step (b): calphad refuses symbols without a standard atomic weight
            # (before: 50.0 g/mol stand-in), also with a custom TDB.
            ("calphad_solver", {"elements": {"Ni": 70.0, "Xx": 30.0},
                                "customTdbText": "ELEMENT XX BLANK 0 0 0 !"}),
            ("calphad_solver", {"elements": {"Ni": 70.0, "Cr": 20.0, "Xx": 10.0}, "unit": "at_pct"}),
        ]
        for solver, payload in changed:
            with self.subTest(solver=solver, payload=payload):
                old = self._base(solver, payload)
                self.assertEqual(old["exitCode"], 0)
                self.assertIs(old["stdout"]["success"], True)
                new = golden.run_solver(solver, payload)
                self.assertEqual(new["exitCode"], 2)
                self.assertEqual(new["stdout"]["error"]["code"], "UNKNOWN_ELEMENT")

    def test_real_elements_now_use_ciaaw_weights_instead_of_50(self):
        # Design step (b): P, Sn, Pb are weighted with their CIAAW values; the base
        # blob used 50.0 g/mol. The at%/wt% conversion differs. (fx-calphad: the new run is
        # the unavailable envelope on the locked interpreter, which carries the composition.)
        for payload in ({"elements": {"Fe": 90.0, "P": 5.0, "Sn": 5.0}},
                        {"elements": {"Cu": 83.0, "Sn": 7.0, "Pb": 7.0, "Zn": 3.0}, "unit": "at_pct",
                         "tMin": 700.0, "tMax": 1200.0, "tStep": 50.0}):
            with self.subTest(payload=payload):
                old = self._base("calphad_solver", payload)
                new = golden.run_solver("calphad_solver", payload)
                self.assertEqual((old["exitCode"], new["exitCode"]), (0, 0), new["stderr"])
                self.assertIs(old["stdout"]["success"], True)
                # wt% input keeps nominalComposition, at% input keeps atomicFractions: the other differs
                self.assertNotEqual(golden.canonical([old["stdout"]["nominalComposition"], old["stdout"]["atomicFractions"]]),
                                    golden.canonical([new["stdout"]["nominalComposition"], new["stdout"]["atomicFractions"]]))

    def test_calphad_composition_still_matches_the_base_blob_apart_from_the_weights(self):
        # Payloads whose elements all have a weight in the base blob's 28-symbol table:
        # wt%/at% are bit-identical to the base blob except for the CIAAW value step, which
        # is bounded. The base blob's profile (the removed fallback) is not compared.
        for payload in ({"elements": {"Co": 60.0, "Cr": 28.0, "Mo": 6.0, "W": 6.0}},
                        {"elements": {"Al": 50.0, "Ni": 50.0}, "unit": "at_pct"},
                        {"elements": {"Cu": 70.0, "Zn": 30.0}}):
            with self.subTest(payload=payload):
                old = self._base("calphad_solver", payload)
                new = golden.run_solver("calphad_solver", payload)
                self.assertEqual((old["exitCode"], new["exitCode"]), (0, 0), new["stderr"])
                for key in ("nominalComposition", "atomicFractions"):
                    rows = drift_report.diff(old["stdout"][key], new["stdout"][key])
                    self.assertTrue(all(r["kind"] == "numeric" and abs(r["rel"]) < 1e-2 for r in rows),
                                    drift_report.render(key, rows, 10))

    def test_source_tables_are_bound_to_the_base_blob(self):
        for solver in cases.SOURCE_TABLES:
            doc = json.loads((golden.GOLDEN_DIR / solver / golden.SOURCE_TABLES_FILE).read_text(encoding="utf-8"))
            self.assertEqual(doc["solverSha256"],
                             golden.normalised_sha256(golden.solver_bytes(solver, golden.BASE_REVISION)))
            values = {name: cases._literal_assignment(golden.solver_bytes(solver, TRANCHE2_BASE), fn, name)
                      for fn, name in cases.SOURCE_TABLES[solver]}
            self.assertEqual(golden.canonical(values), golden.canonical(doc["values"]))


MATERIALS_DATABASE_TS = HERE.parent / "src" / "data" / "materialsDatabase.ts"


def _ui_specimen_compositions():
    """Every `composition: { El: value, ... }` literal of src/data/materialsDatabase.ts.

    CALPHADMultiComponentStudio sends these as-is (activeSpecimen.composition)."""
    import re
    text = MATERIALS_DATABASE_TS.read_text(encoding="utf-8")
    out = []
    for body in re.findall(r"composition:\s*\{([^}]*)\}", text):
        pairs = re.findall(r"\b([A-Za-z]+)\s*:\s*([0-9.]+)", body)
        out.append({el: float(v) for el, v in pairs})
    return out


# The UI specimens with P, S, Sn, Pb or Be (14 of the 33 compositions): before design
# step (b) these elements got the 50.0 g/mol stand-in; now their CIAAW weights.
UI_SPECIMENS_P_S_SN_PB_BE = tuple(
    c for c in _ui_specimen_compositions() if set(c) & {"P", "S", "Sn", "Pb", "Be"})


class CalphadElementTest(unittest.TestCase):
    def test_real_elements_get_their_ciaaw_weight(self):
        # Design step (b): no 50.0 g/mol stand-in; P, S, Sn, Pb, Be, Sc have real weights.
        expected = {"P": 30.974, "S": 32.06, "Sn": 118.71, "Pb": 207.2, "Be": 9.0122,
                    "Sc": 44.956, "Pd": 106.42, "Fe": 55.845}
        for el, value in expected.items():
            self.assertEqual(calphad_solver._atomic_weight(el), value, el)
        wt, at = calphad_solver.normalize_composition({"Fe": 95.0, "P": 5.0}, "wt_pct")
        moles = {"Fe": 0.95 / 55.845, "P": 0.05 / 30.974}
        total = sum(moles.values())
        for el in moles:
            self.assertAlmostEqual(at[el], moles[el] / total, places=15)
        wt, at = calphad_solver.normalize_composition({"Cu": 60.0, "Pb": 40.0}, "at_pct")
        mw = 0.6 * 63.546 + 0.4 * 207.2
        self.assertAlmostEqual(wt["Cu"], 0.6 * 63.546 / mw * 100.0, places=12)
        self.assertAlmostEqual(wt["Pb"], 0.4 * 207.2 / mw * 100.0, places=12)

    def test_unknown_symbols_are_refused_in_both_units(self):
        for elements, field in (({"Ni": 70, "Xx": 30}, "elements.Xx"), ({"Ni": 90, "": 10}, "elements."),
                                ({"Ni": 90, "Qq": 10, "Cr": 5}, "elements.Qq")):
            for unit in ("wt_pct", "at_pct"):
                with self.subTest(elements=elements, unit=unit):
                    with self.assertRaises(iv.ValidationError) as ctx:
                        calphad_solver.normalize_composition(elements, unit)
                    self.assertEqual(ctx.exception.code, iv.UNKNOWN_ELEMENT)
                    self.assertEqual(ctx.exception.field, field)
                    self.assertEqual(ctx.exception.detail["reason"], "no-standard-atomic-weight")

    def test_ui_specimen_compositions_all_normalise(self):
        compositions = _ui_specimen_compositions()
        self.assertEqual(len(compositions), 33)
        refused = []
        for comp in compositions:
            for unit in ("wt_pct", "at_pct"):
                with self.subTest(comp=comp, unit=unit):
                    try:
                        wt, at = calphad_solver.normalize_composition(comp, unit)
                    except iv.ValidationError as exc:
                        refused.append((comp, exc.field))
                        continue
                    # Keys are normalised ("RE" in the WE43 entry becomes "Re", rhenium:
                    # a pre-existing reading of the rare-earth label, see the handoff).
                    self.assertEqual(len(wt), len([v for v in comp.values() if v > 0]))
                    self.assertAlmostEqual(sum(at.values()), 1.0, places=12)
        # Fix round: the wc-co specimen is written as W/C/Co (WC decomposed) and normalises.
        # Physics audit MD-8: the WE43 entry no longer carries the "RE" (rare earths) label,
        # which the solver refused; it lists Nd explicitly, so every specimen normalises.
        self.assertEqual(refused, [])
        self.assertIn({"Mg": 93.3, "Y": 4.0, "Nd": 2.25, "Zr": 0.45}, compositions)
        self.assertNotIn({"Mg": 92.5, "Y": 4.0, "RE": 3.3, "Zr": 0.45}, compositions)
        self.assertIn({"W": 88.235, "C": 5.765, "Co": 6.0}, compositions)

    def test_re_label_is_refused_but_rhenium_is_accepted(self):
        with self.assertRaises(iv.ValidationError) as ctx:
            calphad_solver.normalize_composition({"Mg": 92.5, "RE": 3.3})
        self.assertEqual(ctx.exception.code, iv.UNKNOWN_ELEMENT)
        self.assertEqual(ctx.exception.field, "elements.RE")
        self.assertEqual(ctx.exception.detail["reason"], "ambiguous-rare-earth-label")
        self.assertIn("rare earths", str(ctx.exception))
        wt, _ = calphad_solver.normalize_composition({"Ni": 94.0, "Re": 6.0})
        self.assertEqual(set(wt), {"Ni", "Re"})

    def test_wc_co_specimen_is_not_refused_as_invalid_input(self):
        # fx-calphad: without pycalphad the answer is the explicit unavailable envelope (exit 0,
        # no errorKind), never a made-up profile; with pycalphad the real path runs (WC-Co is
        # in no usable database, so it is unavailable for the missing elements there too).
        code, out = _run("calphad_solver.py", {"name": "wc-co", "elements": {"W": 88.235, "C": 5.765, "Co": 6.0},
                                               "tMin": 500.0, "tMax": 1600.0, "tStep": 50.0})
        self.assertEqual(code, 0, out)
        self.assertIs(out["success"], False)
        self.assertEqual(out["status"], "unavailable")
        self.assertNotIn("errorKind", out)
        self.assertNotIn("equilibriumProfile", out)
        # WC-Co is C-base by atom fraction: no usable database is assessed for it (and none has W, C, Co)
        self.assertEqual(out["unavailableKind"], "database-not-assessed-for-base")
        self.assertEqual(out["baseElement"], "C")

    @unittest.skipIf(calphad_solver.PYCALPHAD_AVAILABLE, "pycalphad is importable: the real path runs here; this checks the no-pycalphad envelope")
    def test_p_s_sn_pb_be_specimens_are_normalised_then_answered_explicitly(self):
        # The 14 UI specimens that hit the 50.0 g/mol stand-in before design step (b) still
        # normalise with CIAAW weights (provenance carried). fx-calphad: the answer is a valid
        # envelope with a reason, never a fabricated profile: either the explicit unavailable
        # status (database lacks an element / pycalphad missing) with no numbers.
        self.assertEqual(len(UI_SPECIMENS_P_S_SN_PB_BE), 14)
        for elements in UI_SPECIMENS_P_S_SN_PB_BE:
            with self.subTest(elements=elements):
                code, out = _run("calphad_solver.py", {"name": "specimen", "elements": elements,
                                                       "tMin": 500.0, "tMax": 1600.0, "tStep": 50.0})
                self.assertEqual(code, 0, out)
                self.assertIs(out["success"], False)
                self.assertEqual(out["status"], "unavailable")
                self.assertTrue(out["reason"])
                self.assertNotIn("errorKind", out)
                self.assertNotIn("equilibriumProfile", out)
                self.assertNotIn("legacyAtomicWeightFallback", out["provenance"])
                self.assertEqual(out["provenance"]["gasConstantR_J_molK"], pc.GAS_CONSTANT_R.value)
                self.assertAlmostEqual(sum(out["atomicFractions"].values()), 1.0, places=12)

    def test_custom_tdb_text_with_an_unknown_symbol_is_refused(self):
        code, out = _run("calphad_solver.py", {"elements": {"Ni": 70.0, "Xx": 30.0},
                                               "customTdbText": "ELEMENT XX BLANK 0 0 0 !"})
        self.assertEqual(code, 2)
        self.assertEqual(out["errorKind"], "validation")
        self.assertEqual(out["error"]["code"], "UNKNOWN_ELEMENT")
        self.assertEqual(out["error"]["field"], "elements.Xx")

    def test_case_variants_and_zero_amounts_are_unchanged(self):
        wt, at = calphad_solver.normalize_composition({"ni": 50.0, "CR": 50.0, "Xx": 0, "Yy": None})
        self.assertEqual(set(wt), {"Ni", "Cr"})
        # Empty input is refused (physics audit TK-7): the former default Ni-10Al-10Cr was reported as
        # if the caller had requested it.
        with self.assertRaises(iv.ValidationError) as ctx:
            calphad_solver.normalize_composition({})
        self.assertEqual((ctx.exception.code, ctx.exception.field), ("OUT_OF_RANGE", "elements"))

    def test_atomic_weights_and_r(self):
        self.assertEqual(calphad_solver.GAS_CONSTANT_R, pc.GAS_CONSTANT_R.value)
        self.assertFalse(hasattr(calphad_solver, "ATOMIC_WEIGHTS"))
        self.assertFalse(hasattr(calphad_solver, "legacy_fallback_elements"))


class EnvelopeAndProvenanceTest(unittest.TestCase):
    def test_calphad_internal_error(self):
        code, out = _run("calphad_solver.py", {"elements": {"Ni": 80}, "tMin": "cold"})
        self.assertEqual(code, 1)
        self.assertEqual(out["errorKind"], "internal")
        self.assertIs(out["success"], False)

    def test_provenance(self):
        # A one-point Fe-Cr request: no database assesses an Fe base, so the solver answers 'unavailable'
        # without an equilibrium solve (the in718 case is a minutes-long real solve with pycalphad) and the
        # provenance block is attached either way, with or without pycalphad.
        fresh = golden.run_solver("calphad_solver", {"elements": {"Fe": 50, "Cr": 50}, "tMin": 1000,
                                                     "tMax": 1000, "tStep": 100})
        prov = fresh["provenance"]["provenance"]
        self.assertEqual(prov["gasConstantR_J_molK"], pc.GAS_CONSTANT_R.value)
        self.assertEqual(prov["constantsVersion"], pc.CONSTANTS_VERSION)
        self.assertEqual(prov["domainDataVersion"], data.DATA_VERSION)
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
        # Design step (b): calphad has no atomic-weight fallback at all.
        src = (HERE / "calphad_solver.py").read_text(encoding="utf-8")
        self.assertNotIn("ATOMIC_WEIGHTS", src)
        self.assertNotIn("CALPHAD_LEGACY", src)
        self.assertIn("physical_constants.atomic_weight(el)", src)

    def test_no_table_fallback_pattern_in_calphad(self):
        # (battery_corrosion_eis_solver's ELECTROLYTE_FORMULATIONS and specs
        # tables were deleted with their actions on 2026-10-04.)
        allowed = set()
        for name in ("calphad_solver.py",):
            for node in ast.walk(self._tree(name)):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "get" and len(node.args) == 2
                        and isinstance(node.args[1], ast.Subscript)):
                    table = getattr(node.func.value, "id", None)
                    if (name, table) not in allowed:
                        self.fail(f"{name}:{node.lineno} uses .get(key, TABLE[...])")


if __name__ == "__main__":
    unittest.main()
