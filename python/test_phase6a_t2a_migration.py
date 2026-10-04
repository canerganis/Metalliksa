"""Phase 6a tranche 2a: structural migration of calphad, battery EIS and icme solvers.

Covers: bit-exact golden regression for the three solvers, parity with the
pre-migration blob on extra payloads, the calphad legacy 50.0 g/mol element
fallback kept in step (a) (fix round B1), the icme validation errors that replace the
silent element/base-metal defaults (and only those), the stdout envelope + exit
code 2 (also through the persistent IPC runner), provenance, the pinned
battery error returns now reporting success:false (formerly masked as true), and a source guard.
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
        expected_unavailable = cases.EXPECTED_UNAVAILABLE_CHANGES.get((solver, case))
        if expected_unavailable is not None:
            # fx-calphad: the removed non-thermodynamic fallback. The old golden stays as the
            # record (exit 0, success true, engine "subregular-adaptive-minimizer", isEmpirical false).
            self.assertEqual(doc["exitCode"], 0)
            self.assertIs(doc["stdout"]["success"], True)
            self.assertEqual(doc["stdout"]["engine"], "subregular-adaptive-minimizer")
            self.assertIs(doc["stdout"]["isEmpirical"], False)
            if calphad_solver.PYCALPHAD_AVAILABLE:
                self.skipTest("pycalphad is importable: this interpreter takes the real path; the golden "
                              "freezes the no-pycalphad 'unavailable' envelope of the locked interpreter")
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
            {"action": "lli_lam_deconvolution", "chemistryId": "nmc811", "initialCapAh": 5.0, "degradedCapAh": 4.2},
            {"action": "drt", "frequencies": cases._EIS_F, "zReal": cases._EIS_ZR, "zImag": cases._EIS_ZI},
            {"action": "p2d_continuum", "chemistryId": "lfp", "cRate": 0.5, "tempC": 45.0, "soc": 0.2},
        ],
    }
    # calphad_solver left PARITY with the fallback removal (fx-calphad): its success output no
    # longer exists on the locked interpreter. What is still comparable (the wt%/at%
    # composition, the element refusal) is checked against the same base blob in
    # test_calphad_composition_still_matches_the_base_blob_apart_from_the_weights.
    # Design step (b) value change: these payloads drift on purpose against the base blob
    # (icme: exact R and CIAAW weights). The check keeps the output structure and exit
    # code identical and bounds the numeric drift; the full rows are in the commit body.
    VALUE_STEP_DRIFT = {
        # Fix round item 6 drifted the corrosion_kinetics K1 (0.00327 -> 0.0032707148, +2.19e-4).
        # That payload is no longer a bounded drift: the engine-fix lane (defect 6b) replaced the
        # substring EW/density with the registry values on purpose; it is checked exactly in
        # CorrosionKineticsEquivalentWeightChangeTest below instead of widening this bound.
        "battery_corrosion_eis_solver": [],
        "icme_multiscale_pipeline_solver": [
            {"baseMetal": "Fe", "composition_wt": {"C": 0.2, "Cr": 12.0, "Mo": 1.0, "V": 0.3, "W": 0.5},
             "grainSize_um": 12.0, "coolingRate_C_s": 50.0, "componentType": "pressure_bulkhead"},
            {"baseMetal": "Al", "composition_wt": {"Zn": 5.6, "Mg": 2.5, "Cu": 1.6, "Co": 0.0}},
            {"baseMetal": "Ni", "composition_wt": {"Cr": 16.0, "Co": 8.5, "W": 2.6, "Al": 3.4, "Ti": 3.4},
             "agingTemp_C": 850, "agingTime_h": 24, "serviceTemp_C": 650},
        ],
    }
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
                    # fx-icme: the documented ICME rows (EXPECTED_DOCUMENTED_VALUE_CHANGES) are
                    # verified exactly; every other row must still be a bounded numeric drift.
                    self.assertEqual(golden.step_b_violations(solver, rows, new["stdout"]), [],
                                     drift_report.render(solver, rows, 10))
                    rows = [r for r in rows if not golden._is_documented_change_row(solver, r["key"])]
                    self.assertEqual({r["kind"] for r in rows}, {"numeric"},
                                     drift_report.render(solver, rows, 10))
                    worst = max(abs(r["rel"]) for r in rows if r["rel"] is not None)
                    self.assertLessEqual(worst, self.VALUE_STEP_MAX_REL)

    def test_corrosion_kinetics_documented_equivalent_weight_change(self):
        """Engine-fix lane (defects 6b + review S3/NIT): the one documented, exactly checked change.

        Base blob: EW 9.0 g/eq and 2.81 g/cm3 for any id containing "al" (substring match), mpy factor
        39.37, Stern-Geary 2.303 instead of ln(10). Now: the registry record "al7075" (computed ASTM G102
        EW 9.5583, 2.81 g/cm3), 1000/25.4 mils per mm, ln(10); rates rounded to 6 significant digits. The
        payload carries betaA/betaC explicitly (the old defaults 0.12 / 0.11 no longer exist). Every changed
        value is pinned; nothing else may differ and the added keys are the four alloy keys.
        """
        import math
        import re
        ba, bc, i0 = 0.12, 0.11, 1.85
        payload = {"action": "corrosion_kinetics", "metalId": "al-7075", "betaA": ba, "betaC": bc, "i0Corr_uA": i0,
                   "ePit": -0.68, "e0": -1.66}
        old = self._base("battery_corrosion_eis_solver", payload)
        new = golden.run_solver("battery_corrosion_eis_solver", payload)
        self.assertEqual((old["exitCode"], new["exitCode"]), (0, 0), new["stderr"])
        rows = drift_report.diff(old["stdout"], new["stdout"])
        by_key = {r["key"]: r for r in rows}
        nyquist = re.compile(r"coatingNyquist\[\d+\]\.spectrum\[\d+\]\.(zReal|minusZImag)")
        fixed = {"corrosionRate_mm_yr", "corrosionRate_mpy", "polarizationResistance_Rp_Ohm_cm2", "alloyId",
                 "equivalentWeight_g_eq", "density_g_cm3", "equivalentWeightNote"}
        self.assertEqual({k for k in by_key if not nyquist.fullmatch(k)}, fixed,
                         drift_report.render("battery_corrosion_eis_solver", rows, 20))
        for key in ("alloyId", "equivalentWeight_g_eq", "density_g_cm3", "equivalentWeightNote"):
            self.assertEqual(by_key[key]["kind"], "added", key)
        k1 = (1e-6 * 31557600.0 * 10.0) / pc.FARADAY.value

        def sig6(x):
            return round(x, 5 - int(math.floor(math.log10(abs(x)))))

        # base blob: K1 0.00327 (printed), 9.0 / 2.81, 39.37, B with 2.303 (+1e-12), Rp rounded to 1 decimal
        cr_old = 0.00327 * i0 * 9.0 / 2.81
        self.assertEqual(old["stdout"]["corrosionRate_mm_yr"], round(cr_old, 5))
        self.assertEqual(old["stdout"]["corrosionRate_mpy"], round(cr_old * 39.37, 4))
        b_old = ba * bc / (2.303 * (ba + bc) + 1e-12)
        self.assertEqual(old["stdout"]["polarizationResistance_Rp_Ohm_cm2"], round(b_old / (i0 * 1e-6), 1))
        # new: registry EW, exact mils per mm and ln(10); 6 significant digits
        cr_new = k1 * i0 * 9.5583 / 2.81
        self.assertEqual(new["stdout"]["corrosionRate_mm_yr"], sig6(cr_new))
        self.assertEqual(new["stdout"]["corrosionRate_mpy"], sig6(cr_new * 1000.0 / 25.4))
        b_new = ba * bc / (math.log(10.0) * (ba + bc))
        self.assertEqual(new["stdout"]["sternGeary_B_V"], round(b_new, 4))
        self.assertEqual(new["stdout"]["polarizationResistance_Rp_Ohm_cm2"], round(b_new / (i0 * 1e-6), 1))
        self.assertEqual(new["stdout"]["alloyId"], "al7075")
        self.assertEqual(new["stdout"]["equivalentWeight_g_eq"], 9.5583)
        self.assertEqual(new["stdout"]["density_g_cm3"], 2.81)
        self.assertEqual(
            new["stdout"]["equivalentWeightNote"],
            "ASTM G102 EW computed in alloy_registry (corrosion domain) from the alloy composition: "
            "elements >= 1 wt % counted, mass fractions renormalised, in-house valences (no per-value citation).")
        # the Nyquist rows only follow the 1.8e-4 change of B (Rp)
        worst = max(abs(r["rel"]) for k, r in by_key.items() if nyquist.fullmatch(k) and r["rel"] is not None)
        self.assertLess(worst, 5e-4)

    def test_changed_inputs_succeeded_with_a_default_before(self):
        changed = [
            ("icme_multiscale_pipeline_solver", {"baseMetal": "Co", "composition_wt": {"Cr": 20.0}}),
            ("icme_multiscale_pipeline_solver", {"baseMetal": "Ni", "composition_wt": {"cr": 19.0}}),
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

    def test_ui_specimen_compositions_normalise_except_the_re_label(self):
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
        # Fix round: the wc-co specimen is written as W/C/Co (WC decomposed) and normalises;
        # the WE43 "RE" (rare earths) label is refused instead of being read as rhenium.
        self.assertEqual(refused, [({"Mg": 92.5, "Y": 4.0, "RE": 3.3, "Zr": 0.45}, "elements.RE")] * 2)
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
        # Empty input keeps its documented default.
        wt, _ = calphad_solver.normalize_composition({})
        self.assertEqual(wt, {"Ni": 80.0, "Al": 10.0, "Cr": 10.0})

    def test_atomic_weights_and_r(self):
        self.assertEqual(calphad_solver.GAS_CONSTANT_R, pc.GAS_CONSTANT_R.value)
        self.assertFalse(hasattr(calphad_solver, "ATOMIC_WEIGHTS"))
        self.assertFalse(hasattr(calphad_solver, "legacy_fallback_elements"))


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

    def test_battery_internal_error_and_error_returns_report_success_false(self):
        code, out = _run("battery_corrosion_eis_solver.py", {"action": "p2d_continuum", "tempC": "warm"})
        self.assertEqual(code, 1)
        self.assertEqual(out["errorKind"], "internal")
        # V1 follow-up: the former success:true masking (pinned here until now) is gone.
        # Error returns keep exit code 0 and the same message, but report success:false.
        few = {"frequencies": [1000.0, 100.0, 10.0], "zReal": [1.0, 1.1, 1.2], "zImag": [-0.1, -0.2, -0.3]}
        expected = [
            ({"action": "no_such_action"}, "Unknown action 'no_such_action'"),
            ({"action": "drt", **few}, "Insufficient frequency points for DRT"),
            ({"action": "analyze_uploaded_eis", **few}, "At least 4 frequency points are required for EIS analysis."),
            ({"action": "identify_bisquert_tlm", **few},
             "At least 4 frequency points are required for Bisquert TLM component identification."),
            ({"action": "analyze_uploaded_eis", "frequencies": [1.0, 2.0, 3.0, 4.0], "zReal": [float("nan")] * 4,
              "zImag": [0.0] * 4}, "No valid numeric impedance data found."),
        ]
        for payload, message in expected:
            with self.subTest(action=payload["action"], message=message):
                code, out = _run("battery_corrosion_eis_solver.py", payload)
                self.assertEqual(code, 0)
                self.assertIs(out["success"], False)
                self.assertEqual(out["error"], message)
                self.assertNotIn("provenance", out)
        # Successful outputs still say success:true and carry provenance.
        code, out = _run("battery_corrosion_eis_solver.py", cases.CASES["battery_corrosion_eis_solver"]["nernst_planck_poisson"])
        self.assertEqual(code, 0)
        self.assertIs(out["success"], True)
        self.assertNotIn("error", out)
        self.assertIn("provenance", out)

    def test_provenance(self):
        fresh = golden.run_solver("calphad_solver", cases.CASES["calphad_solver"]["in718_wt_pct"])
        prov = fresh["provenance"]["provenance"]
        self.assertEqual(prov["gasConstantR_J_molK"], pc.GAS_CONSTANT_R.value)
        self.assertEqual(prov["constantsVersion"], pc.CONSTANTS_VERSION)
        self.assertEqual(prov["domainDataVersion"], data.DATA_VERSION)
        fresh = golden.run_solver("icme_multiscale_pipeline_solver", {})
        prov = fresh["provenance"]["provenance"]
        # Design step (b): exact R and CIAAW weights.
        self.assertEqual(prov["gasConstantR_J_molK"], pc.GAS_CONSTANT_R.value)
        self.assertEqual(prov["atomicWeightsSource"], pc.CIAAW_SOURCE)
        self.assertEqual(icme.R_GAS, pc.GAS_CONSTANT_R.value)
        self.assertEqual(prov["domainDataVersion"], data.DATA_VERSION)
        fresh = golden.run_solver("battery_corrosion_eis_solver", cases.CASES["battery_corrosion_eis_solver"]["nernst_planck_poisson"])
        prov = fresh["provenance"]["provenance"]
        self.assertEqual(prov["constantsVersion"], pc.CONSTANTS_VERSION)
        # Design step (b): one exact R/F for all four battery sites.
        self.assertEqual(prov["gasConstantR_J_molK"], pc.GAS_CONSTANT_R.value)
        self.assertEqual(prov["faraday_C_mol"], pc.FARADAY.value)

    def test_battery_sites_use_the_exact_constants(self):
        import battery_corrosion_eis_solver as battery
        self.assertEqual(battery.R_GAS, pc.GAS_CONSTANT_R.value)
        self.assertEqual(battery.F_FARADAY, pc.FARADAY.value)
        src = (HERE / "battery_corrosion_eis_solver.py").read_text(encoding="utf-8")
        for name in ("LEGACY_R_", "LEGACY_F_", "TRUNCATED_"):
            self.assertNotIn(name, src)


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
        # Design step (b): calphad has no atomic-weight fallback at all.
        src = (HERE / "calphad_solver.py").read_text(encoding="utf-8")
        self.assertNotIn("ATOMIC_WEIGHTS", src)
        self.assertNotIn("CALPHAD_LEGACY", src)
        self.assertIn("physical_constants.atomic_weight(el)", src)

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
