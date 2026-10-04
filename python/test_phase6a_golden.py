"""Phase 6a golden regression: migrated solvers must stay bit-exact.

Every case in python/golden/phase6a/<solver>/<case>.json was captured at the
pre-migration revision (tools/capture_phase6a_golden.py). The current solver is
run exactly like the app's ad-hoc spawn path and its stdout, with only the
volatile keys stripped, must serialise to the identical canonical JSON text.

Deliberate behaviour changes (silent default -> validation error) are listed in
EXPECTED_BEHAVIOUR_CHANGES; for those cases the old golden stays on disk as the
record of the old behaviour and the test asserts the new validation envelope.
"""

import copy
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "tools"))

import capture_phase6a_golden as golden  # noqa: E402
import drift_report  # noqa: E402
from phase6a_test_support import require_git_revision  # noqa: E402

# (solver, case) -> expected validation error code (exit 2, errorKind "validation").
# The first two were silent defaults before the Phase 6a structural migration:
# - tafel alloyId "unobtainium-x" was solved with the AISI 316L preset;
# - pourbaix element "Unobtainium" was drawn with the Fe system (Ni point branch).
# The last two are the WP-E 25 C Gibbs engine: a 60 C (Al) or 80 C (Ni) request used to get a map
# from hand-written temperature extrapolations; it now gets the TEMPERATURE_UNSUPPORTED envelope.
EXPECTED_BEHAVIOUR_CHANGES = {
    ("tafel_corrosion_rate_solver", "edge_unknown_alloy_zero_icorr"): "UNKNOWN_ALLOY",
    ("pourbaix_solver", "edge_unknown_element_badvals"): "UNKNOWN_ELEMENT",
    ("pourbaix_solver", "al_hot_chloride"): "TEMPERATURE_UNSUPPORTED",
    ("pourbaix_solver", "ni_acid_points"): "TEMPERATURE_UNSUPPORTED",
}
# ---- BEGIN phase6a-t2b block: kinetics / fatigue unknown alloy (was AISI 4140 / Ti-6Al-4V) ----
EXPECTED_BEHAVIOUR_CHANGES.update(golden._t2b_cases.EXPECTED_BEHAVIOUR_CHANGES)
# ---- END phase6a-t2b block ----


class GoldenFilesTest(unittest.TestCase):
    def test_every_case_has_a_golden_file(self):
        for solver, case in golden.iter_golden_cases():
            path = golden.golden_path(solver, case)
            self.assertTrue(path.is_file(), str(path))
            doc = golden.load_golden(solver, case)
            self.assertEqual(doc["schema"], golden.GOLDEN_SCHEMA)
            self.assertEqual(doc["solver"], solver)
            self.assertEqual(doc["case"], case)
            self.assertEqual(doc["baseRevision"], golden.BASE_REVISION)
            self.assertEqual(golden.canonical(doc["input"]), golden.canonical(golden.CASES[solver][case]))
            # N2: the stored input is exactly the key-sorted payload (same text, same
            # order), so the regression re-run sends what the sorted payload says.
            self.assertEqual(json.dumps(doc["input"], ensure_ascii=False),
                             json.dumps(golden.CASES[solver][case], sort_keys=True, ensure_ascii=False),
                             f"{solver}/{case}")

    def test_case_counts(self):
        for solver, cases in golden.CASES.items():
            self.assertGreaterEqual(len(cases), 3, solver)
            self.assertLessEqual(len(cases), 5, solver)

    def test_golden_files_hold_no_volatile_keys(self):
        for solver, case in golden.iter_golden_cases():
            text = golden.golden_path(solver, case).read_text(encoding="utf-8")
            stdout = json.dumps(golden.load_golden(solver, case)["stdout"])
            for key in golden.VOLATILE_KEYS:
                self.assertNotIn(f'"{key}"', stdout, f"{solver}/{case}: {key}")
            self.assertTrue(text.endswith("\n"))


class GoldenRegressionTest(unittest.TestCase):
    maxDiff = None

    def _check(self, solver: str, case: str):
        doc = golden.load_golden(solver, case)
        # Design step (b): a re-blessed expectation (step_b/<case>.json) replaces the
        # d33b6f5 golden for the comparison; StepBGoldenTest checks its recorded drift.
        expected = golden.load_expected(solver, case)
        # Run the CASES payload, not doc["input"]: golden files store the input with
        # sorted keys, and key order is significant for some solvers (stochastic UQ maps
        # composition elements to Sobol dimensions in insertion order).
        # GoldenFilesTest asserts both are canonically equal.
        fresh = golden.run_solver(solver, golden.CASES[solver][case])
        expected_code = EXPECTED_BEHAVIOUR_CHANGES.get((solver, case))
        if expected_code is not None:
            self.assertEqual(fresh["exitCode"], 2, fresh["stderr"])
            out = fresh["stdout"]
            self.assertIs(out.get("success"), False)
            self.assertEqual(out.get("errorKind"), "validation")
            self.assertEqual(out["error"]["code"], expected_code)
            self.assertTrue(out["error"]["field"])
            self.assertTrue(out["error"]["message"])
            self.assertIsInstance(out["error"]["detail"], dict)
            self.assertEqual(set(out), {"success", "error", "errorKind"})
            # The old golden is still the pre-migration record of the silent default.
            self.assertEqual(doc["exitCode"], 0)
            # (the fatigue driver output has no "success" key; it must not be an error)
            self.assertIsNot(doc["stdout"].get("success"), False)
            self.assertNotIn("error", doc["stdout"])
            return
        self.assertEqual(fresh["exitCode"], expected["exitCode"], fresh["stderr"])
        rows = drift_report.diff(expected["stdout"], fresh["stdout"])
        self.assertEqual(rows, [], drift_report.render(f"{solver}/{case}", rows, 20))
        self.assertEqual(golden.canonical(fresh["stdout"]), golden.canonical(expected["stdout"]))

    def test_tafel_corrosion_rate_solver(self):
        for case in golden.CASES["tafel_corrosion_rate_solver"]:
            with self.subTest(case=case):
                self._check("tafel_corrosion_rate_solver", case)

    def test_pourbaix_solver(self):
        for case in golden.CASES["pourbaix_solver"]:
            with self.subTest(case=case):
                self._check("pourbaix_solver", case)

    def test_pourbaix_temperature_envelope_detail(self):
        # WP-E: the 60 C Al and 80 C Ni requests are refused (25 C engine, no extrapolation).
        for case in ("al_hot_chloride", "ni_acid_points"):
            with self.subTest(case=case):
                requested = golden.CASES["pourbaix_solver"][case]["temperature_C"]
                self.assertNotEqual(requested, 25)
                fresh = golden.run_solver("pourbaix_solver", golden.CASES["pourbaix_solver"][case])
                err = fresh["stdout"]["error"]
                self.assertEqual((fresh["exitCode"], err["code"], err["field"]), (2, "TEMPERATURE_UNSUPPORTED", "temperature_C"))
                self.assertEqual(err["detail"], {"requested": float(requested), "supported": [25.0], "toleranceC": 0.5})


def _git_available() -> bool:
    try:
        golden.solver_bytes("pourbaix_solver", golden.BASE_REVISION)
        return True
    except Exception:
        return False


@require_git_revision(_git_available(), f"git or revision {golden.BASE_REVISION} unavailable")
class GoldenBindingTest(unittest.TestCase):
    """Golden files are bound to the immutable solver blobs they were captured from."""

    def _blob_sha(self, solver):
        return golden.normalised_sha256(golden.solver_bytes(solver, golden.BASE_REVISION))

    def test_every_golden_records_the_base_blob_sha256(self):
        for solver, case in golden.iter_golden_cases():
            doc = golden.load_golden(solver, case)
            self.assertEqual(doc["solverSha256"], self._blob_sha(solver), f"{solver}/{case}")
            self.assertEqual(doc["solverFile"], f"python/{solver}.py")
            self.assertIn(doc["solverSource"], {f"git:{golden.BASE_REVISION}", "worktree"})
        for solver in golden._TABLE_TARGETS:
            path = golden.GOLDEN_DIR / solver / golden.SOURCE_TABLES_FILE
            doc = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(doc["solverSha256"], self._blob_sha(solver), solver)

    def test_normalised_sha256_ignores_only_crlf(self):
        self.assertEqual(golden.normalised_sha256(b"a\r\nb\n"), golden.normalised_sha256(b"a\nb\n"))
        self.assertNotEqual(golden.normalised_sha256(b"a\nb\n"), golden.normalised_sha256(b"a\nc\n"))

    def _in_temp_golden_dir(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        original = golden.GOLDEN_DIR
        golden.GOLDEN_DIR = Path(tmp.name)
        self.addCleanup(setattr, golden, "GOLDEN_DIR", original)
        return Path(tmp.name)

    def test_force_capture_of_changed_solver_is_refused(self):
        # The migrated working-tree solvers differ from the d33b6f5 blobs.
        tmp = self._in_temp_golden_dir()
        for solver in golden.CASES:
            self.assertNotEqual(golden.normalised_sha256(golden.solver_bytes(solver)), self._blob_sha(solver))
            case = next(iter(golden.CASES[solver]))
            with self.assertRaises(golden.CaptureRefused):
                golden.capture(solver, case, force=True)
        with self.assertRaises(golden.CaptureRefused):
            golden.capture_source_tables(force=True)
        self.assertEqual(list(tmp.rglob("*.json")), [])

    def test_capture_from_base_blob_reproduces_committed_golden(self):
        committed = {(s, c): golden.load_golden(s, c) for s, c in golden.iter_golden_cases()}
        tmp = self._in_temp_golden_dir()
        for solver, case in golden.iter_golden_cases():
            golden.capture(solver, case, force=True, from_revision=golden.BASE_REVISION)
            fresh = json.loads((tmp / solver / f"{case}.json").read_text(encoding="utf-8"))
            old = committed[(solver, case)]
            self.assertEqual(fresh["exitCode"], old["exitCode"], f"{solver}/{case}")
            self.assertEqual(golden.canonical(fresh["stdout"]), golden.canonical(old["stdout"]), f"{solver}/{case}")
            self.assertEqual(fresh["solverSha256"], old["solverSha256"])
        golden.capture_source_tables(force=True, from_revision=golden.BASE_REVISION)
        for solver in golden._TABLE_TARGETS:
            fresh = json.loads((tmp / solver / golden.SOURCE_TABLES_FILE).read_text(encoding="utf-8"))
            old = json.loads((HERE / "golden" / "phase6a" / solver / golden.SOURCE_TABLES_FILE).read_text(encoding="utf-8"))
            self.assertEqual(golden.canonical(fresh["values"]), golden.canonical(old["values"]), solver)

    def test_from_revision_other_than_base_is_refused(self):
        self._in_temp_golden_dir()
        with self.assertRaises(golden.CaptureRefused):
            golden.capture("pourbaix_solver", "cu_nochloride", force=True, from_revision="HEAD")


class StepBGoldenTest(unittest.TestCase):
    """Re-blessed expectations of design step (b) carry their full drift against d33b6f5."""

    def _step_b_files(self):
        return sorted(golden.GOLDEN_DIR.glob(f"*/{golden.STEP_B_DIR}/*.json"))

    def test_every_step_b_file_belongs_to_a_known_case(self):
        for path in self._step_b_files():
            solver, case = path.parent.parent.name, path.stem
            with self.subTest(file=f"{solver}/{case}"):
                self.assertIn(solver, golden.CASES)
                self.assertIn(case, golden.CASES[solver])
                # A behaviour change (validation envelope or success-flag flip) is never a re-bless.
                self.assertNotIn((solver, case), EXPECTED_BEHAVIOUR_CHANGES)
                self.assertNotIn((solver, case), golden._t2a_cases.EXPECTED_BEHAVIOUR_CHANGES)
                self.assertNotIn((solver, case), golden._t2a_cases.EXPECTED_SUCCESS_FLAG_CHANGES)
                self.assertNotIn((solver, case), golden._t2a_cases.EXPECTED_UNAVAILABLE_CHANGES)
                self.assertNotIn((solver, case), golden.step_b_excluded_cases())

    def test_excluded_cases_cover_every_behaviour_change(self):
        excluded = golden.step_b_excluded_cases()
        for key in (set(EXPECTED_BEHAVIOUR_CHANGES) | set(golden._t2a_cases.EXPECTED_BEHAVIOUR_CHANGES)
                    | set(golden._t2a_cases.EXPECTED_SUCCESS_FLAG_CHANGES)
                    | set(golden._t2a_cases.EXPECTED_UNAVAILABLE_CHANGES)):
            self.assertIn(key, excluded)

    def test_recorded_drift_is_a_bounded_value_change(self):
        # Fix round item 7: numeric rows only (changed strings only under pythonCode),
        # |rel| <= 1e-2, tafel <= 3 * |EW rel| + 1e-2 (see step_b_max_rel).
        for path in self._step_b_files():
            solver, case = path.parent.parent.name, path.stem
            with self.subTest(file=f"{solver}/{case}"):
                doc = json.loads(path.read_text(encoding="utf-8"))
                base = golden.load_golden(solver, case)["stdout"]
                self.assertEqual(golden.step_b_violations(solver, doc["driftVsBase"], doc["stdout"],
                                                          golden.CASES[solver][case], base), [])
                self.assertEqual(golden.step_b_document_violations(solver, doc["stdout"]), [])

    def test_guard_rejects_structural_and_large_drift(self):
        num = lambda key, rel: {"key": key, "kind": "numeric", "old": 1.0, "new": 1.0 + rel, "abs": rel, "rel": rel}
        self.assertEqual(golden.step_b_violations("kinetics_ttt_cct_solver", [num("x", 0.009)]), [])
        self.assertTrue(golden.step_b_violations("kinetics_ttt_cct_solver", [num("x", 0.02)]))
        self.assertTrue(golden.step_b_violations("icme_multiscale_pipeline_solver",
                                                 [{"key": "a", "kind": "added", "old": None, "new": 1}]))
        self.assertTrue(golden.step_b_violations("tafel_corrosion_rate_solver",
                                                 [{"key": "alloyName", "kind": "changed", "old": "a", "new": "b"}]))
        self.assertEqual(golden.step_b_violations("tafel_corrosion_rate_solver",
                                                  [{"key": "pythonCode", "kind": "changed", "old": "a", "new": "b"}]), [])
        rows = [num("equivalentWeight", 0.03), num("remainingPittingMm", -0.09)]
        self.assertEqual(golden.step_b_violations("tafel_corrosion_rate_solver", rows), [])
        self.assertTrue(golden.step_b_violations("tafel_corrosion_rate_solver", rows + [num("x", 0.2)]))

    def test_documented_hardness_change_is_checked_exactly(self):
        # EXPECTED_DOCUMENTED_VALUE_CHANGES: kinetics predictedHardness_HV -> ASTM E140 Table 1.
        solver = "kinetics_ttt_cct_solver"
        key = "cctContinuousCoolingMap[0].predictedHardness_HV"
        skey = key + "_status"

        def doc(alloy_type, hrc, status):
            return {"alloyMetadata": {"type": alloy_type},
                    "cctContinuousCoolingMap": [{"predictedHardness_HRC": hrc, "predictedHardness_HV_status": status}]}

        def hv_row(old, new):
            kind = "numeric" if new is not None else "changed"
            row = {"key": key, "kind": kind, "old": old, "new": new}
            if kind == "numeric":
                row.update(abs=new - old, rel=(new - old) / old)
            return row

        conv, rng, cls = ("converted-astm-e140-table1", "unavailable-outside-e140-table1-hrc-20-68",
                          "unavailable-no-verified-table-for-alloy-class")
        steel = lambda hrc, status: doc("Low-Alloy Steel", hrc, status)
        add = lambda status: {"key": skey, "kind": "added", "old": None, "new": status}
        # accepted: steel 42 HRC 481 -> 412 (|rel| 0.14), steel 18 HRC 229 -> null, Ti 64 HRC 712 -> null
        self.assertEqual(golden.step_b_violations(solver, [hv_row(481.0, 412.0), add(conv)], steel(42.0, conv)), [])
        self.assertEqual(golden.step_b_violations(solver, [hv_row(229.0, None), add(rng)], steel(18.0, rng)), [])
        self.assertEqual(golden.step_b_violations(
            solver, [hv_row(712.0, None), add(cls)], doc("Alpha-Beta Titanium Alloy", 64.0, cls)), [])
        # rejected: no document, wrong new value, int instead of float, wrong old value,
        # non-steel given a number, wrong status, status changed instead of added
        self.assertTrue(golden.step_b_violations(solver, [hv_row(481.0, 412.0)]))
        self.assertTrue(golden.step_b_violations(solver, [hv_row(481.0, 413.0)], steel(42.0, conv)))
        self.assertTrue(golden.step_b_violations(solver, [hv_row(481.0, 412)], steel(42.0, conv)))
        self.assertTrue(golden.step_b_violations(solver, [hv_row(480.0, 412.0)], steel(42.0, conv)))
        self.assertTrue(golden.step_b_violations(
            solver, [hv_row(712.0, 800.0)], doc("Precipitation-Hardenable Ni-Fe Superalloy", 64.0, conv)))
        self.assertTrue(golden.step_b_violations(solver, [add(rng)], steel(42.0, conv)))
        self.assertTrue(golden.step_b_violations(
            solver, [{"key": skey, "kind": "changed", "old": "x", "new": conv}], steel(42.0, conv)))
        # the exception is per solver and per key: same key elsewhere, or a null HRC, stays structural
        self.assertTrue(golden.step_b_violations("stochastic_uq_mmpds_solver", [hv_row(229.0, None)], steel(18.0, rng)))
        self.assertTrue(golden.step_b_violations(solver, [{"key": "cctContinuousCoolingMap[0].predictedHardness_HRC",
                                                           "kind": "changed", "old": 18.0, "new": None}],
                                                 steel(18.0, rng)))
        big = {"key": "x", "kind": "numeric", "old": 1.0, "new": 1.02, "abs": 0.02, "rel": 0.02}
        self.assertTrue(golden.step_b_violations(solver, [big], steel(42.0, conv)))

    # ---- pourbaix: WP-E equilibrium engine, documented value change (WP-G) ----------------------
    POURBAIX = "pourbaix_solver"
    POURBAIX_CASES = ("fe_chloride_points", "cu_nochloride")

    def _pb(self, case):
        old = golden.load_golden(self.POURBAIX, case)["stdout"]
        new = copy.deepcopy(golden.load_expected(self.POURBAIX, case)["stdout"])
        return old, new

    def _pb_violations(self, old, new):
        return golden.step_b_violations(self.POURBAIX, drift_report.diff(old, new), new, old_stdout=old)

    def test_pourbaix_step_b_files_exist_for_the_value_cases_only(self):
        for case in self.POURBAIX_CASES:
            self.assertTrue(golden.step_b_path(self.POURBAIX, case).is_file(), case)
            self.assertEqual(golden.load_expected(self.POURBAIX, case)["label"], golden.STEP_B_LABEL)
        for case in ("al_hot_chloride", "ni_acid_points", "edge_unknown_element_badvals"):
            self.assertFalse(golden.step_b_path(self.POURBAIX, case).exists(), case)
            self.assertIn((self.POURBAIX, case), EXPECTED_BEHAVIOUR_CHANGES)
            self.assertIn((self.POURBAIX, case), golden.step_b_excluded_cases())

    def test_pourbaix_documented_patterns_are_listed_exactly(self):
        import pourbaix_golden_check as check
        table = golden.EXPECTED_DOCUMENTED_VALUE_CHANGES
        self.assertEqual(set(table), {"kinetics_ttt_cct_solver", "pourbaix_solver", "stochastic_uq_mmpds_solver",
                                        "icme_multiscale_pipeline_solver"})
        self.assertEqual(set(table["pourbaix_solver"]), set(check.DOCUMENTED_VALUE_CHANGES))
        self.assertEqual(len(table["pourbaix_solver"]), len(check.DOCUMENTED_KEYS))
        # no catch-all: every pattern is one leaf-key path, anchored by fullmatch
        for key in check.DOCUMENTED_KEYS:
            self.assertNotIn(".*", key)
            self.assertTrue(golden._is_documented_change_row(self.POURBAIX, key.replace("[]", "[7]")), key)
        for key in ("model.hiddenSwitch", "stabilityFieldGrid[3].note", "systemName", "success", "provenance.x",
                    "speciesTable.species[2].extra", "analyticalBoundaries[0].line.extra",
                    "experimentalOverlay.points[0].verdict", "parameters.nernstSlope_V_pH"):
            self.assertFalse(golden._is_documented_change_row(self.POURBAIX, key), key)

    def test_pourbaix_documented_change_is_checked_exactly(self):
        # The real re-blessed documents are exactly the oracle's equilibrium (every row verified).
        for case in self.POURBAIX_CASES:
            with self.subTest(case=case):
                old, new = self._pb(case)
                self.assertEqual(self._pb_violations(old, new), [])

    def test_pourbaix_guard_rejects_wrong_species_line_text_and_undocumented_keys(self):
        def other_id(doc, current):
            return next(s["id"] for s in doc["speciesTable"]["species"] if s["id"] != current)

        def grid_species(doc):
            doc["stabilityFieldGrid"][100]["dominantSpeciesId"] = other_id(
                doc, doc["stabilityFieldGrid"][100]["dominantSpeciesId"])

        def grid_category(doc):
            doc["stabilityFieldGrid"][5]["category"] = "Immunity (wrong)"

        def grid_regime(doc):
            doc["stabilityFieldGrid"][7]["regime"] += " "

        def line_intercept(doc):
            b = next(b for b in doc["analyticalBoundaries"] if b["line"]["type"] == "sloped")
            b["line"]["E_V_SHE_at_pH0"] += 2e-4

        def line_slope(doc):
            b = next(b for b in doc["analyticalBoundaries"] if b["line"]["type"] == "sloped"
                     and abs(b["line"]["slope_V_per_pH"]) > 1e-3)
            b["line"]["slope_V_per_pH"] *= 1.01

        def boundary_species(doc):
            b = doc["analyticalBoundaries"][1]
            b["speciesAId"], b["speciesBId"] = b["speciesBId"], b["speciesAId"]

        def boundary_end(doc):
            doc["analyticalBoundaries"][2]["points"][1]["pH"] += 2e-4

        def boundary_dropped(doc):
            del doc["analyticalBoundaries"][-1]

        def boundary_equation(doc):
            doc["analyticalBoundaries"][1]["equation"] = doc["analyticalBoundaries"][1]["equation"].replace("e⁻", "")

        def table_dfg(doc):
            doc["speciesTable"]["species"][1]["dfG_kJ_mol"] += 1e-3

        def table_stoichiometry(doc):
            doc["speciesTable"]["species"][2]["z"] += 1

        def inventory(doc):
            doc["speciesInventory"]["immunity"].append("Xx(s)")

        def domain_vertex(doc):
            doc["domains"][1]["polygon"][0]["E_V_SHE"] += 2e-4

        def point_species(doc):
            pt = doc["experimentalOverlay"]["points"][0]
            pt["dominantSpeciesId"] = other_id(doc, pt["dominantSpeciesId"])

        def point_text(doc):
            doc["experimentalOverlay"]["points"][0]["mechanismDetails"] += " It is always protective."

        def point_delta(doc):
            doc["experimentalOverlay"]["points"][0]["deltaE_Immunity_V"] += 0.001

        def water_line(doc):
            doc["waterStabilityLines"]["line_b_oxygen_OER"][3]["E_V_SHE"] += 0.001

        def pitting_status(doc):
            doc["chloridePittingBoundary"]["status"] = "available"

        def temperature_note(doc):
            doc["temperatureStatus"]["note"] += "!"

        def model_text(doc):
            doc["model"]["method"] = "rule tree"

        def key_in_section(doc):
            doc["model"]["hiddenSwitch"] = True

        def key_in_cell(doc):
            doc["stabilityFieldGrid"][3]["note"] = "x"

        def key_top_level(doc):
            doc["confidence"] = 1.0

        def undocumented_change(doc):
            doc["systemName"] += " (edited)"

        def undocumented_numeric(doc):
            doc["parameters"]["nernstSlope_V_pH"] *= 1.2

        # REVIEW-pbx-code SHOULD-FIX 2/3: forged provenance and drift under the old 1 % bound
        def self_intersecting_polygon(doc):
            d = next(d for d in doc["domains"] if len(d["polygon"]) >= 4)
            d["polygon"][1], d["polygon"][2] = d["polygon"][2], d["polygon"][1]

        def consistent_species_rename(doc):
            formula = doc["speciesTable"]["species"][4]["formula"]
            renamed = json.loads(json.dumps(doc, ensure_ascii=False).replace(formula, formula + "·film"))
            doc.clear()
            doc.update(renamed)

        def level_upgrade(doc):
            row = next(r for r in doc["speciesTable"]["species"] if r["verification"] == "V2")
            row["verification"] = "V1"

        def forged_evidence(doc):
            doc["speciesTable"]["species"][1]["evidence"] = "exact NIST value, fully protective"

        def forged_source(doc):
            doc["speciesTable"]["species"][1]["source"] = "Z"

        def scaled_equation(doc):
            b = doc["analyticalBoundaries"][1]
            left, right = b["equation"].split(" ⇌ ")
            def double(side):
                out = []
                for t in side.split(" + "):
                    m = re.fullmatch(r"(\d*)(.+)", t)
                    out.append(str(2 * int(m.group(1) or 1)) + m.group(2))
                return " + ".join(out)
            b["equation"] = double(left) + " ⇌ " + double(right)

        def water_padded_equation(doc):
            b = doc["analyticalBoundaries"][1]
            left, right = b["equation"].split(" ⇌ ")
            b["equation"] = left + " + 7H₂O ⇌ " + right + " + 7H₂O"

        def nernst_slope_half_percent(doc):
            doc["parameters"]["nernstSlope_V_pH"] *= 1.005

        def her_line_drift(doc):
            doc["waterStabilityLines"]["line_a_hydrogen_HER"][5]["E_V_SHE"] *= 1.009

        def her_equation_text(doc):
            doc["waterStabilityLines"]["equation_HER"] += " "

        def measured_potential_drift(doc):
            doc["experimentalOverlay"]["points"][0]["potential_Input_V"] *= 1.008

        def withheld_text(doc):
            doc["speciesTable"]["withheldSpecies"].append({"id": "Xx", "verification": "V3", "reason": "x"})

        mutants = [
            ("wrong species in a grid cell", grid_species, "stabilityFieldGrid"),
            ("wrong category in a grid cell", grid_category, "stabilityFieldGrid"),
            ("wrong regime text", grid_regime, "stabilityFieldGrid"),
            ("wrong line intercept (+2e-4 V)", line_intercept, "analyticalBoundaries"),
            ("wrong line slope (+1 %)", line_slope, "analyticalBoundaries"),
            ("boundary species swapped", boundary_species, "analyticalBoundaries"),
            ("boundary end moved (2e-4)", boundary_end, "analyticalBoundaries"),
            ("boundary dropped", boundary_dropped, "analyticalBoundaries"),
            ("unbalanced equation", boundary_equation, "analyticalBoundaries"),
            ("species dfG +1e-3 kJ/mol", table_dfg, "speciesTable"),
            ("species charge changed", table_stoichiometry, "speciesTable"),
            ("species inventory changed", inventory, "speciesInventory"),
            ("domain vertex moved (2e-4)", domain_vertex, "domains"),
            ("wrong species at a measured point", point_species, "experimentalOverlay"),
            ("wrong text at a measured point", point_text, "experimentalOverlay"),
            ("wrong deltaE_Immunity_V (+1 mV)", point_delta, "experimentalOverlay"),
            ("water line b +1 mV", water_line, "waterStabilityLines"),
            ("pitting status text", pitting_status, "chloridePittingBoundary"),
            ("temperature note text", temperature_note, "temperatureStatus"),
            ("model method text", model_text, "model"),
            ("undocumented key inside a documented section", key_in_section, "not a value drift"),
            ("undocumented key inside a grid cell", key_in_cell, "not a value drift"),
            ("undocumented top-level key", key_top_level, "not a value drift"),
            ("undocumented changed key", undocumented_change, "not a value drift"),
            ("undocumented numeric change (20 %)", undocumented_numeric, "|rel|"),
            ("self-intersecting polygon (two vertices swapped)", self_intersecting_polygon, "domains"),
            ("consistent species-formula rename", consistent_species_rename, "speciesTable"),
            ("verification level V2 -> V1", level_upgrade, "speciesTable"),
            ("forged evidence text", forged_evidence, "speciesTable"),
            ("forged source id", forged_source, "speciesTable"),
            ("equation scaled by 2", scaled_equation, "analyticalBoundaries"),
            ("equation padded with water on both sides", water_padded_equation, "analyticalBoundaries"),
            ("Nernst slope +0.5 % (under the old 1 % bound)", nernst_slope_half_percent, "|rel|"),
            ("HER line +0.9 % (under the old 1 % bound)", her_line_drift, "|rel|"),
            ("HER equation text", her_equation_text, "waterStabilityLines"),
            ("measured input potential +0.8 % (under the old 1 % bound)", measured_potential_drift, "|rel|"),
            ("withheld species appended", withheld_text, "speciesTable"),
        ]
        for name, mutate, expect in mutants:
            for case in self.POURBAIX_CASES:
                with self.subTest(mutant=name, case=case):
                    old, new = self._pb(case)
                    mutate(new)
                    violations = self._pb_violations(old, new)
                    self.assertTrue(violations, "mutant accepted")
                    self.assertTrue(any(expect in v for v in violations), (expect, violations[:3]))

    def test_pourbaix_oracle_check_itself_rejects_her_and_input_drift(self):
        # independent of the step-(b) bound: the section checks of document_problems
        import pourbaix_golden_check as check
        for case in self.POURBAIX_CASES:
            old, new = self._pb(case)
            self.assertEqual({k: v for k, v in check.document_problems(old, new).items() if v}, {})
            her = copy.deepcopy(new)
            her["waterStabilityLines"]["line_a_hydrogen_HER"][5]["E_V_SHE"] *= 1.009
            self.assertTrue(check.document_problems(old, her)["waterStabilityLines"], case)
            eq = copy.deepcopy(new)
            eq["waterStabilityLines"]["equation_HER"] += " "
            self.assertTrue(check.document_problems(old, eq)["waterStabilityLines"], case)
            pot = copy.deepcopy(new)
            pot["experimentalOverlay"]["points"][0]["potential_Input_V"] *= 1.008
            self.assertTrue(check.document_problems(old, pot)["experimentalOverlay"], case)
            slope = copy.deepcopy(new)
            slope["parameters"]["nernstSlope_V_pH"] *= 1.005
            self.assertTrue(check.document_problems(old, slope)["parameters"], case)
            slope_w = copy.deepcopy(new)
            slope_w["waterStabilityLines"]["nernstSlope"] *= 1.005
            self.assertTrue(check.document_problems(old, slope_w)["waterStabilityLines"], case)

    def test_pourbaix_has_no_generic_percentage_bound(self):
        # every numeric Pourbaix drift row is a documented change or a violation: bound 0
        self.assertEqual(golden.step_b_max_rel(self.POURBAIX, [{"key": "x", "rel": 0.001}]), 0.0)
        self.assertEqual(golden.step_b_max_rel("kinetics_ttt_cct_solver", []), golden.STEP_B_DEFAULT_MAX_REL)
        row = {"key": "parameters.nernstSlope_V_pH", "kind": "numeric", "old": 0.05916, "new": 0.05917,
               "abs": 1e-5, "rel": 1.7e-4}
        self.assertTrue(golden.step_b_violations(self.POURBAIX, [row]))

    def test_pourbaix_polygon_order_check(self):
        import pourbaix_golden_check as check
        square = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        self.assertTrue(check._convex_simple(square))
        self.assertTrue(check._convex_simple(list(reversed(square))))
        self.assertFalse(check._convex_simple([square[0], square[2], square[1], square[3]]))  # bow tie
        self.assertFalse(check._convex_simple(square[:2]))
        self.assertFalse(check._convex_simple([(0.0, 0.0), (2.0, 0.0), (1.0, 0.5), (2.0, 2.0), (0.0, 2.0)]))  # concave

    def test_pourbaix_guard_tolerance_is_only_the_boundary_coordinate_bound(self):
        # 1e-4 V is the spec's bound for boundary coordinates; a shift inside it is accepted,
        # outside it (see the mutants above) is not. Nothing else is accepted by tolerance.
        old, new = self._pb("fe_chloride_points")
        b = next(b for b in new["analyticalBoundaries"] if b["line"]["type"] == "sloped")
        b["line"]["E_V_SHE_at_pH0"] += 5e-5
        b["points"][0]["E_V_SHE"] += 5e-5
        self.assertEqual(self._pb_violations(old, new), [])
        old, new = self._pb("fe_chloride_points")
        new["stabilityFieldGrid"][0]["E_V_SHE"] = round(new["stabilityFieldGrid"][0]["E_V_SHE"] + 5e-5, 6)
        self.assertTrue(self._pb_violations(old, new))

    def test_pourbaix_guard_checks_the_old_value_and_the_documents(self):
        import pourbaix_golden_check as check
        old, new = self._pb("cu_nochloride")
        rows = drift_report.diff(old, new)
        self.assertEqual(golden.step_b_violations(self.POURBAIX, rows, new, old_stdout=old), [])
        # without the d33b6f5 golden or the re-blessed document nothing is accepted
        self.assertTrue(golden.step_b_violations(self.POURBAIX, rows, new))
        self.assertTrue(golden.step_b_violations(self.POURBAIX, rows, None, old_stdout=old))
        # the old value of a row must be the golden's leaf; the new value the document's leaf
        forged = copy.deepcopy(rows)
        next(r for r in forged if r["key"] == "stabilityFieldGrid[3].regime")["old"] = "Immunity (forged)"
        self.assertTrue(any("d33b6f5 golden" in v for v in golden.step_b_violations(self.POURBAIX, forged, new, old_stdout=old)))
        forged = copy.deepcopy(rows)
        next(r for r in forged if r["key"] == "stabilityFieldGrid[3].regime")["new"] = "Immunity (forged)"
        self.assertTrue(golden.step_b_violations(self.POURBAIX, forged, new, old_stdout=old))
        # a "removed" row whose key still exists in the re-blessed document is not accepted
        removed = next(r for r in rows if r["kind"] == "removed")
        self.assertNotIn(removed["key"], check.flatten(new))
        self.assertEqual(golden.step_b_violations(self.POURBAIX, [removed], new, old_stdout=old), [])
        still_there = copy.deepcopy(new)
        still_there["analyticalBoundaries"][0]["points"] += [{"pH": 0.0, "E_V_SHE": 0.0}] * 20
        self.assertTrue(golden.step_b_violations(self.POURBAIX, [removed], still_there, old_stdout=old))
        # the exception is per solver: the same keys elsewhere stay structural drift
        self.assertTrue(golden.step_b_violations("tafel_corrosion_rate_solver", rows, new, old_stdout=old))
        # a document of another element than the golden's is not accepted
        other_old, _ = self._pb("fe_chloride_points")
        self.assertTrue(golden.step_b_violations(self.POURBAIX, rows, new, old_stdout=other_old))

    def test_pourbaix_oracle_check_holds_for_other_inputs(self):
        # The check is not tuned to the two blessed cases: it recomputes the equilibrium of any
        # served element/activity from the oracle and must agree with the engine.
        import pourbaix_golden_check as check
        import pourbaix_solver
        points = [{"id": "a", "ph": 1.0, "potential_V": -0.3, "refElectrode": "SCE"},
                  {"ph": 6.5, "potential_V": 0.5, "refElectrode": "SHE"},
                  {"ph": 13.0, "potential_V": -1.2, "refElectrode": "MMS"},
                  {"ph": 9.0, "potential_V": 1.9, "refElectrode": "Ag/AgCl (3M KCl)"}]
        # Al joined the served set with WP-Al (OBIGT TS01 + gibbsite): the guard must hold for it too.
        for element, log_a in (("Ni", -6.0), ("Zn", -4.0), ("Mg", -6.0), ("Fe", -3.0), ("Cu", -4.0),
                               ("Al", -6.0), ("Al", -3.0), ("Al", 0.0)):
            with self.subTest(element=element, log_a=log_a):
                doc = json.loads(json.dumps(
                    pourbaix_solver.solve_pourbaix_diagram(element, 25.0, log_a, 350.0, points)))
                problems = check.document_problems(doc, doc)
                self.assertEqual({k: v[:2] for k, v in problems.items() if v}, {})

    def test_pourbaix_guard_rejects_wrong_aluminium_data(self):
        # Mutants on an Al document (served by the engine since WP-Al): each must be a violation.
        import copy
        import pourbaix_golden_check as check
        import pourbaix_solver
        base = json.loads(json.dumps(pourbaix_solver.solve_pourbaix_diagram(
            "Al", 25.0, -6.0, 350.0, [{"ph": 6.5, "potential_V": -0.2, "refElectrode": "SHE"}])))

        def species(doc, sid):
            return next(r for r in doc["speciesTable"]["species"] if r["id"] == sid)

        def mutate_dfg(doc):
            species(doc, "Al(OH)3")["dfG_kJ_mol"] += 1e-3

        def mutate_charge(doc):
            species(doc, "Al(OH)4-")["z"] = -2

        def mutate_withheld_level(doc):
            doc["speciesTable"]["withheldSpecies"][2]["verification"] = "V3"  # boehmite is V2 (excluded)

        def mutate_withheld_dropped(doc):
            doc["speciesTable"]["withheldSpecies"].pop()

        def mutate_domain(doc):
            doc["domains"][1]["polygon"][0]["E_V_SHE"] += 2e-4

        def mutate_point(doc):
            doc["experimentalOverlay"]["points"][0]["dominantSpeciesId"] = "Al3+"

        def mutate_level(doc):
            species(doc, "Al(OH)4-")["verification"] = "V1"

        def mutate_evidence(doc):
            species(doc, "Al(OH)3")["evidence"] += " (exact)"

        def mutate_withheld_reason(doc):
            doc["speciesTable"]["withheldSpecies"][0]["reason"] = "unverified"

        self.assertEqual({k: v for k, v in check.document_problems(base, base).items() if v}, {})
        for mutate in (mutate_dfg, mutate_charge, mutate_withheld_level, mutate_withheld_dropped,
                       mutate_domain, mutate_point, mutate_level, mutate_evidence, mutate_withheld_reason):
            with self.subTest(mutant=mutate.__name__):
                doc = copy.deepcopy(base)
                mutate(doc)
                problems = check.document_problems(base, doc)
                self.assertTrue(any(problems.values()), mutate.__name__)
    def _kinetics_step_b(self, case):
        path = golden.step_b_path("kinetics_ttt_cct_solver", case)
        doc = json.loads(path.read_text(encoding="utf-8"))
        return doc["driftVsBase"], doc["stdout"]

    def test_fx_kinetics_documented_changes_are_checked_exactly(self):
        # Engine-fix lane fx-kinetics (tools/kinetics_documented_changes.py): every documented row is
        # verified against the re-blessed document; a wrong value, a wrong status, the wrong alloy class
        # or an unflagged placeholder is a violation, and numeric R drift stays under the bounded guard.
        import copy
        solver = "kinetics_ttt_cct_solver"
        for case in ("aisi4140_ui_defaults", "aisi4340_slow_cool", "in718_lpbf_quench", "ti64_beta_quench"):
            rows, new = self._kinetics_step_b(case)
            self.assertEqual(golden.step_b_violations(solver, rows, new), [], case)
            self.assertEqual(golden.step_b_document_violations(solver, new), [], case)

        def violations(case, mutate_rows=None, mutate_doc=None):
            rows, new = self._kinetics_step_b(case)
            rows, new = copy.deepcopy(rows), copy.deepcopy(new)
            if mutate_rows:
                mutate_rows(rows)
            if mutate_doc:
                mutate_doc(new)
            return golden.step_b_violations(solver, rows, new) + golden.step_b_document_violations(solver, new)

        def row(rows, key):
            return next(r for r in rows if r["key"] == key)

        def doc_set(path, value):
            def mutate(doc):
                node = doc
                for part in path[:-1]:
                    node = node[part]
                node[path[-1]] = value
            return mutate

        # non-steel: the steel-only claim must hold in the document, and every nulled value must be null
        self.assertTrue(violations("in718_lpbf_quench", mutate_doc=doc_set(["kineticsModel", "status"], "available")))
        self.assertTrue(violations("in718_lpbf_quench", mutate_doc=doc_set(["alloyMetadata", "type"], "Low-Alloy Steel")))
        self.assertTrue(violations("in718_lpbf_quench", mutate_rows=lambda rows: row(
            rows, "cctContinuousCoolingMap[0].phaseFractions.Martensite_pct").update(new=63.0)))
        self.assertTrue(violations("in718_lpbf_quench", mutate_rows=lambda rows: row(
            rows, "cctContinuousCoolingMap[0].transformedStart_status").update(new="available")))
        # placeholders: only keys flagged in alloy_registry.KINETICS_PLACEHOLDERS may be null
        self.assertTrue(violations("ti64_beta_quench", mutate_rows=lambda rows: rows.append(
            {"key": "alloyMetadata.Ms_C", "kind": "changed", "old": 800.0, "new": None})))
        self.assertTrue(violations("in718_lpbf_quench", mutate_rows=lambda rows: row(
            rows, "criticalTransformationTemperatures.Ms_C_status").update(new="registry-screening-value")))
        # LSW: the recorded old/new radius, strengthening and regime must equal the independent oracle
        key = "lswPrecipitateCoarsening[9].meanRadius_nm"
        self.assertTrue(violations("aisi4140_ui_defaults", mutate_rows=lambda rows: row(rows, key).update(new=22.9)))
        self.assertTrue(violations("aisi4140_ui_defaults", mutate_rows=lambda rows: row(rows, key).update(old=1.6)))
        self.assertTrue(violations("aisi4140_ui_defaults", mutate_rows=lambda rows: row(
            rows, "lswPrecipitateCoarsening[9].strengtheningMechanism").update(new="Weak-Pair / Strong-Pair Cutting")))
        self.assertTrue(violations("aisi4140_ui_defaults", mutate_doc=doc_set(
            ["lswPrecipitateCoarsening", 0, "meanRadius_nm"], 1.5)))
        # steel TTT floor flags and the floor-driven CCT start
        self.assertTrue(violations("aisi4140_ui_defaults", mutate_doc=doc_set(
            ["tttIsothermalCurves", 0, "floorHit"], not self._kinetics_step_b("aisi4140_ui_defaults")[1][
                "tttIsothermalCurves"][0]["floorHit"])))
        self.assertTrue(violations("aisi4140_ui_defaults", mutate_doc=doc_set(["tttIncubationFloor", "floorHitCount"], 31)))
        self.assertTrue(violations("aisi4140_ui_defaults", mutate_doc=doc_set(
            ["cctContinuousCoolingMap", 0, "primaryMicrostructure"], "Pearlite")))
        # a steel row may not lose its phase fractions (only non-steel rows do)
        self.assertTrue(golden.step_b_violations(solver, [
            {"key": "cctContinuousCoolingMap[0].phaseFractions.Martensite_pct", "kind": "changed", "old": 98.0, "new": None}],
            self._kinetics_step_b("aisi4140_ui_defaults")[1]))
        # numeric R drift of a steel TTT time stays under the default bound (not a documented row)
        num = lambda rel: [{"key": "tttIsothermalCurves[0].t50_s", "kind": "numeric", "old": 1.0,
                            "new": 1.0 + rel, "abs": rel, "rel": rel}]
        steel_doc = self._kinetics_step_b("aisi4140_ui_defaults")[1]
        self.assertEqual(golden.step_b_violations(solver, num(0.005), steel_doc), [])
        self.assertTrue(golden.step_b_violations(solver, num(0.05), steel_doc))
        # without the re-blessed document nothing of this is accepted
        self.assertTrue(golden.step_b_violations(solver, self._kinetics_step_b("in718_lpbf_quench")[0]))
    def test_fx_kinetics_document_checks_reject_the_review_mutants(self):
        # fx-kinetics code review S1: the row handlers see only drifted values, so every mutant below
        # (a value that equals the base, or an inconsistent status/flag) must be caught by the whole-document
        # checks (tools/kinetics_documented_changes.document_violations).
        import copy
        solver = "kinetics_ttt_cct_solver"
        docs = {c: self._kinetics_step_b(c)[1] for c in ("aisi4140_ui_defaults", "in718_lpbf_quench", "ti64_beta_quench")}

        def rejected(case, mutate):
            doc = copy.deepcopy(docs[case])
            mutate(doc)
            self.assertTrue(golden.step_b_document_violations(solver, doc), case)

        for case, doc in docs.items():
            self.assertEqual(golden.step_b_document_violations(solver, doc), [], case)

        def floor_never(doc):
            for p in doc["tttIsothermalCurves"]:
                p["floorHit"] = False
            doc["tttIncubationFloor"].update(floorHitCount=0, status="no-floor-hit-points")

        def floor_from_rounded(doc):  # one flagged point lost
            next(p for p in doc["tttIsothermalCurves"] if p["floorHit"])["floorHit"] = False
            doc["tttIncubationFloor"]["floorHitCount"] -= 1

        def reported_start(doc):  # the old "775 C Pearlite" claim comes back with a "computed" status
            row = doc["cctContinuousCoolingMap"][4]
            row.update(transformedStartTemp_C=774.5, transformedStartTime_s=8.55, primaryMicrostructure="Pearlite",
                       transformedStart_status="diffusional-start-scheil-additivity", unavailableReason=None)

        def start_null_with_wrong_status(doc):
            doc["cctContinuousCoolingMap"][4]["transformedStart_status"] = "athermal-martensite-no-diffusional-start-above-ms"

        def start_blanking_narrowed(doc):  # a start reported while the status still says "not computed"
            doc["cctContinuousCoolingMap"][9].update(transformedStartTemp_C=765.0, primaryMicrostructure="Pearlite")

        rejected("aisi4140_ui_defaults", floor_never)
        rejected("aisi4140_ui_defaults", floor_from_rounded)
        rejected("aisi4140_ui_defaults", reported_start)
        rejected("aisi4140_ui_defaults", start_null_with_wrong_status)
        rejected("aisi4140_ui_defaults", start_blanking_narrowed)
        # placeholder echoed in alloyMetadata although it is flagged and null elsewhere
        rejected("in718_lpbf_quench", lambda d: d["alloyMetadata"].update(Ms_C=-50.0))
        rejected("in718_lpbf_quench", lambda d: d["criticalTransformationTemperatures"].update(Ms_C=-50.0))
        rejected("in718_lpbf_quench", lambda d: d["criticalTransformationTemperatures"].update(Ms_C_status="registry-screening-value"))
        # non-steel critical cooling rate shown while its status says unavailable (both blocks), eutectoid Ae1 shown
        rejected("in718_lpbf_quench", lambda d: d["criticalTransformationTemperatures"].update(CriticalCoolingRate_CCR_C_s=150.0))
        rejected("in718_lpbf_quench", lambda d: d["alloyMetadata"].update(critical_cooling_rate_C_s=150.0))
        rejected("ti64_beta_quench", lambda d: d["criticalTransformationTemperatures"].update(Ae1_C=700.0))
        rejected("ti64_beta_quench", lambda d: d["alloyMetadata"].update(Ae1_C=700.0))
        rejected("ti64_beta_quench", lambda d: d["alloyMetadata"].update(Ms_C=None))  # unflagged: must stay a number
        # kineticsModel block
        rejected("in718_lpbf_quench", lambda d: d["kineticsModel"].update(illustrativeOnly=False))
        rejected("in718_lpbf_quench", lambda d: d["kineticsModel"].update(scope="all-alloys"))
        rejected("in718_lpbf_quench", lambda d: d["kineticsModel"].update(placeholderParameters=[]))
        rejected("in718_lpbf_quench", lambda d: d["kineticsModel"].update(note="Steel template"))
        rejected("aisi4140_ui_defaults", lambda d: d["kineticsModel"].update(status="unavailable"))
        rejected("aisi4140_ui_defaults", lambda d: d["tttIncubationFloor"].update(note="x"))
        # gap fields of a non-steel and the steel texts
        rejected("ti64_beta_quench", lambda d: d["calphadVsKineticsGap"]["kineticRealityAtSelectedCooling"].update(
            criticalCoolingRate_C_s=410.0))
        rejected("ti64_beta_quench", lambda d: d["calphadVsKineticsGap"]["equilibriumPrediction"].update(
            stablePhasesAtRT="Ferrite + Cementite / Equilibrium intermetallics"))
        rejected("aisi4140_ui_defaults", lambda d: d["calphadVsKineticsGap"]["equilibriumPrediction"].update(reason="x"))
        rejected("aisi4140_ui_defaults", lambda d: d["calphadVsKineticsGap"]["kineticRealityAtSelectedCooling"].update(
            verdict="Full Martensitic / Metastable Quench"))
        # LSW: a number above the solvus is rejected, a null below it is rejected
        rejected("in718_lpbf_quench", lambda d: d["lswPrecipitateCoarsening"][0].update(meanRadius_nm=None))
        rejected("in718_lpbf_quench", lambda d: d["inputParameters"].update(agingTemp_C=1100.0))

        # untested guard branches (code review N1)
        steel_doc, in718_doc = docs["aisi4140_ui_defaults"], docs["in718_lpbf_quench"]
        # a handler that cannot verify (bad index) is a violation, never "accepted"
        bad_index = {"key": "tttIsothermalCurves[99].floorHit", "kind": "added", "old": None, "new": True}
        self.assertTrue(golden.step_b_violations(solver, [bad_index], steel_doc))
        # registryAlloyId is the registry id the request alloy resolves to
        rid = {"key": "kineticsModel.registryAlloyId", "kind": "added", "old": None, "new": "in718"}
        self.assertEqual(golden.step_b_violations(solver, [rid], in718_doc), [])
        self.assertTrue(golden.step_b_violations(solver, [dict(rid, new="ti6al4v")], in718_doc))
        # HV of a non-steel row whose HRC is now null: the old value must be the old formula of an old HRC band
        hv = lambda old: {"key": "cctContinuousCoolingMap[0].predictedHardness_HV", "kind": "changed", "old": old, "new": None}
        self.assertEqual(golden.step_b_violations(solver, [hv(229.0)], in718_doc), [])
        self.assertTrue(golden.step_b_violations(solver, [hv(500.0)], in718_doc))
        # the not-computed CCT start reason must be the exact text
        reason = {"key": "cctContinuousCoolingMap[0].unavailableReason", "kind": "added", "old": None,
                  "new": "incubation law has no Ae3 asymptote; start not computed"}
        self.assertEqual(golden.step_b_violations(solver, [reason], steel_doc), [])
        self.assertTrue(golden.step_b_violations(solver, [dict(reason, new="the Scheil-additivity start is not a model result")], steel_doc))
        # D2 only: the equilibrium text names carbides; another steel may not change it
        d2 = {"alloyMetadata": {"type": "Cold-Work Tool Steel"}, "kineticsModel": {"registryAlloyId": "aisid2"}}
        phases = {"key": "calphadVsKineticsGap.equilibriumPrediction.stablePhasesAtRT", "kind": "changed",
                  "old": "Ferrite + Cementite / Equilibrium intermetallics", "new": "Ferrite + alloy carbides (M7C3 / M23C6)"}
        self.assertEqual(golden.step_b_violations(solver, [phases], d2), [])
        self.assertTrue(golden.step_b_violations(solver, [phases], steel_doc))
        self.assertTrue(golden.step_b_violations(solver, [dict(phases, new="Ferrite + carbides")], d2))
        # LSW above the solvus: old value must still be the old formula, new must be null
        al = {"alloyMetadata": {"type": "Aerospace Aluminum", "Q_diff_kJ_mol": 130.0, "Ae3_C": 480.0, "Ae1_C": None},
              "inputParameters": {"agingTemp_C": 720.0}, "lswPrecipitateCoarsening": [{"agingTime_h": 0.1}]}
        import kinetics_documented_changes as kdc
        old_r = round(kdc.lsw_radius_nm(130.0, 720.0, 0.1, 8.314, corrected=False), 2)
        lsw = {"key": "lswPrecipitateCoarsening[0].meanRadius_nm", "kind": "changed", "old": old_r, "new": None}
        self.assertEqual(golden.step_b_violations(solver, [lsw], al), [])
        self.assertTrue(golden.step_b_violations(solver, [dict(lsw, old=old_r + 1.0)], al))
        self.assertTrue(golden.step_b_violations(solver, [dict(lsw, new=1884.97, kind="numeric", abs=1.0, rel=1.0)], al))

    def test_documented_uq_sampler_change_is_checked_against_the_scipy_oracle(self):
        # EXPECTED_DOCUMENTED_VALUE_CHANGES: stochastic UQ norm_ppf sign fix. The drift rows are
        # not bounded; the whole new document must equal the solver run with scipy's ndtri.
        import copy
        solver, case = "stochastic_uq_mmpds_solver", "seed42_n500_defaults_ni"
        payload = golden.CASES[solver][case]
        oracle = golden._uq_scipy_oracle_stdout(payload)
        base = golden.load_golden(solver, case)["stdout"]
        rows = drift_report.diff(base, oracle)
        self.assertTrue(rows)
        self.assertEqual(golden.step_b_violations(solver, rows, oracle, payload), [])
        # not the oracle: a perturbed document, the pre-fix (sigma 0.776) document itself
        perturbed = copy.deepcopy(oracle)
        perturbed["stochasticProperties"]["yieldStrength_Rp02"]["stdDev"] += 0.01
        self.assertTrue(golden.step_b_violations(solver, rows, perturbed, payload))
        self.assertTrue(golden.step_b_violations(solver, rows, base, payload))
        # no document or no payload cannot be verified
        self.assertTrue(golden.step_b_violations(solver, rows, oracle))
        self.assertTrue(golden.step_b_violations(solver, rows, None, payload))
        # rows outside the listed patterns keep the numeric bound, and structural rows are refused
        other = {"key": "samplingMetadata.centeredL2Discrepancy", "kind": "numeric", "old": 1.0, "new": 1.5,
                 "abs": 0.5, "rel": 0.5}
        self.assertTrue(golden.step_b_violations(solver, [other], oracle, payload))
        added = {"key": "stochasticProperties.yieldStrength_Rp02.newKey", "kind": "added", "old": None, "new": 1.0}
        self.assertTrue(golden.step_b_violations(solver, [added], oracle, payload))
        # the exception does not leak to another solver
        self.assertTrue(golden.step_b_violations("kinetics_ttt_cct_solver", rows[:1], oracle, payload))

    def test_uq_oracle_is_the_pinned_prefix_blob_not_the_working_tree_solver(self):
        # Review fxa B1: the oracle must not be able to match a later solver edit.
        import stochastic_uq_mmpds_solver as current
        pinned = golden._uq_pinned_solver_module()
        self.assertIsNot(pinned, current)
        self.assertAlmostEqual(pinned.norm_ppf(0.10), -0.0675829, places=6)   # the sign error is still in the oracle blob
        self.assertAlmostEqual(current.norm_ppf(0.10), -1.2815515655, places=9)
        self.assertEqual(golden.normalised_sha256(golden.solver_bytes(
            "stochastic_uq_mmpds_solver", golden.UQ_ORACLE_REVISION)), golden.UQ_ORACLE_SHA256)
        # the oracle run must not leave the substitute behind
        golden._uq_scipy_oracle_stdout(golden.CASES["stochastic_uq_mmpds_solver"]["seed42_n500_defaults_ni"])
        self.assertAlmostEqual(pinned.norm_ppf(0.10), -0.0675829, places=6)

    def test_uq_guard_rejects_other_solver_changes_hidden_in_the_listed_rows(self):
        # Review fxa B1 mutants: documents that differ from the pinned-solver oracle by anything
        # other than the inverse normal must be refused, in-pattern rows included.
        import copy
        solver, case = "stochastic_uq_mmpds_solver", "preset_steel4340_ams6414"   # baseMetal Fe
        payload = golden.CASES[solver][case]
        oracle = golden._uq_scipy_oracle_stdout(payload)
        base = golden.load_golden(solver, case)["stdout"]
        self.assertEqual(golden.step_b_violations(solver, drift_report.diff(base, oracle), oracle, payload), [])

        def scale_yield(doc):  # a 5 % yield change only for baseMetal Fe
            stats = doc["stochasticProperties"]["yieldStrength_Rp02"]
            for key, value in stats.items():
                if isinstance(value, float):
                    stats[key] = value * 1.05

        def cpk(doc):  # Cpk 3.0 -> 3.3 sigma
            stats = doc["stochasticProperties"]["yieldStrength_Rp02"]
            stats["cpk"] = round(stats["cpk"] / 1.1, 2)

        def sobol_label(doc):
            doc["sobolSensitivityAnalysis"][0]["parameter"] = "renamed (Chemistry)"

        def extra_key(doc):
            doc["stochasticProperties"]["yieldStrength_Rp02"]["extraKey"] = 1.0

        def out_of_pattern(doc):  # 2 % on a row outside the three patterns
            doc["samplingMetadata"]["centeredL2Discrepancy"] *= 1.02

        for name, mutate in (("fe-only yield x1.05", scale_yield), ("cpk", cpk), ("sobol label", sobol_label),
                             ("extra key", extra_key), ("out-of-pattern x1.02", out_of_pattern)):
            mutant = copy.deepcopy(oracle)
            mutate(mutant)
            rows = drift_report.diff(base, mutant)
            self.assertTrue(golden.step_b_violations(solver, rows, mutant, payload), name)

    def test_documented_icme_change_is_checked_exactly(self):
        # EXPECTED_DOCUMENTED_VALUE_CHANGES (fx-icme, lane 9): UTS/K_Ic/a_c/r_p -> null, the
        # verdict without a creep claim, 'Calibrated Card' relabelled, new honesty keys. Rows are
        # derived from the real d33b6f5 golden vs a fresh run, then mutated one at a time.
        solver, case = "icme_multiscale_pipeline_solver", "default_payload_in718"
        base = golden.load_golden(solver, case)["stdout"]
        fresh = golden.run_solver(solver, golden.CASES[solver][case])["stdout"]
        rows = drift_report.diff(base, fresh)
        self.assertEqual(golden.step_b_violations(solver, rows, fresh), [])
        self.assertTrue(golden.step_b_violations(solver, rows))  # no re-blessed document: not verifiable

        def mutated(key, **changes):
            out = []
            for r in rows:
                out.append(dict(r, **changes) if r["key"] == key else r)
            self.assertIn(key, [r["key"] for r in rows], key)
            return out

        uts = "scale3_continuumPlasticity.mechanicalProperties.ultimateTensileStrength_UTS_MPa"
        k1c = "scale3_continuumPlasticity.mechanicalProperties.fractureToughness_K1c_MPa_sqrt_m"
        verdict = "scale4_macroComponentFEA.structuralVerdict"
        ac = "scale4_macroComponentFEA.lefmDamageTolerance.criticalFlawSize_ac_mm"
        ndi = "scale4_macroComponentFEA.lefmDamageTolerance.inspectionNDICapability"
        bad = [
            mutated(uts, old=1000.0),                          # old UTS was not the old yield strength
            # free-text claims: only the exact pinned texts are accepted (review S2)
            mutated("modelStatusNote", new=fresh["modelStatusNote"] + " Validated against FEA and CALPHAD."),
            mutated("modelParts[3]", new="validated FEA component limit"),
            mutated("scale4_macroComponentFEA.structuralVerdictBasis",
                    new=fresh["scale4_macroComponentFEA"]["structuralVerdictBasis"] + " Certified to ASME."),
            mutated("engine", new="MetalliX ICME Multi-Scale Closed-Form Estimator (illustrative; DFT-validated"),
            mutated("scale3_continuumPlasticity.mechanicalProperties.ultimateTensileStrength_UTS_status", new="unavailable: DFT-validated"),
            mutated("scale3_continuumPlasticity.mechanicalProperties.fractureToughness_K1c_status", new="unavailable: certified"),
            mutated("scale4_macroComponentFEA.lefmDamageTolerance.status", new="unavailable: FEA-validated"),
            mutated(uts, new=1191.8),                          # UTS must be null, not a number
            mutated(k1c, new=100.0),
            mutated(ac, new=1.0),
            mutated(verdict, new="STRUCTURALLY SAFE (Passed Yield & Creep Criteria)"),
            mutated(verdict, new="YIELD CHECK PASSED (no creep, but with a Creep claim)"),
            mutated(ndi, new="Detectable with Standard X-Ray / UT (Flaw > 1.0mm)"),
            mutated("modelStatus", new="validated"),
            mutated("engine", new="MetalliX ICME Multi-Scale HPC Pipeline (DFT -> CALPHAD -> Kinetics -> Microstructure -> Macro FEA)"),
            mutated("caeExportCards.abaqus", new=fresh["caeExportCards"]["abaqus"] + "\n*EXTRA"),
            mutated("caeExportCards.ansys", new=fresh["caeExportCards"]["ansys"].replace("ILLUSTRATIVE", "CALIBRATED")),
        ]
        for i, variant in enumerate(bad):
            with self.subTest(mutation=i):
                self.assertTrue(golden.step_b_violations(solver, variant, fresh))
        # review S1: every documented rule must occur and the unavailable values must be null.
        # Mutant: UTS and K_Ic put back to the old value (== yield) -> no UTS/K_Ic drift rows.
        import copy
        reverted = copy.deepcopy(fresh)
        mech = reverted["scale3_continuumPlasticity"]["mechanicalProperties"]
        mech["ultimateTensileStrength_UTS_MPa"] = base["scale3_continuumPlasticity"]["mechanicalProperties"][
            "ultimateTensileStrength_UTS_MPa"]
        mech.pop("ultimateTensileStrength_UTS_status")
        rows_reverted = drift_report.diff(base, reverted)
        self.assertNotIn(uts, [r["key"] for r in rows_reverted])
        self.assertTrue(golden.step_b_violations(solver, rows_reverted, reverted))
        # a documented row dropped from an otherwise valid table, with the value still null in the document
        for dropped in (uts, verdict, "modelStatus", "caeExportCards.lsDyna", "modelParts[2]"):
            with self.subTest(dropped=dropped):
                partial = [r for r in rows if r["key"] != dropped]
                self.assertTrue(golden.step_b_violations(solver, partial, fresh))
        # a unavailable value that is not null in the re-blessed document
        not_null = copy.deepcopy(fresh)
        not_null["scale3_continuumPlasticity"]["mechanicalProperties"]["fractureToughness_K1c_MPa_sqrt_m"] = 100.0
        self.assertTrue(golden.step_b_violations(solver, rows, not_null))
        # the exception is per solver: the same row under another solver is structural
        self.assertTrue(golden.step_b_violations("tafel_corrosion_rate_solver", [rows[0]], fresh))
        # an undocumented non-numeric row of the same solver still fails
        extra = {"key": "scale3_continuumPlasticity.mechanicalProperties.hollomon_n", "kind": "changed",
                 "old": "a", "new": "b"}
        self.assertTrue(golden.step_b_violations(solver, rows + [extra], fresh))

    def test_recorded_solver_sha256_is_the_current_solver(self):
        # A solver edit after a re-bless must come with a new re-bless (and drift table).
        for path in self._step_b_files():
            solver = path.parent.parent.name
            with self.subTest(file=str(path.relative_to(golden.GOLDEN_DIR))):
                doc = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(doc["solverSha256"], golden.normalised_sha256(golden.solver_bytes(solver)))

    def test_step_b_metadata_and_recorded_drift(self):
        for path in self._step_b_files():
            solver, case = path.parent.parent.name, path.stem
            with self.subTest(file=f"{solver}/{case}"):
                doc = json.loads(path.read_text(encoding="utf-8"))
                base = golden.load_golden(solver, case)
                self.assertEqual(doc["schema"], golden.STEP_B_SCHEMA)
                self.assertEqual(doc["label"], golden.STEP_B_LABEL)
                self.assertEqual((doc["solver"], doc["case"]), (solver, case))
                self.assertEqual(doc["solverFile"], f"python/{solver}.py")
                self.assertEqual(len(doc["solverSha256"]), 64)
                self.assertEqual(golden.canonical(doc["input"]), golden.canonical(golden.CASES[solver][case]))
                self.assertEqual(doc["exitCode"], base["exitCode"])
                rows = drift_report.diff(base["stdout"], doc["stdout"])
                # A re-bless exists only for a real drift, and the recorded table is complete.
                self.assertTrue(rows)
                self.assertEqual(golden.canonical(doc["driftVsBase"]), golden.canonical(rows))
                self.assertTrue(text_ends_with_newline(path))

    def test_load_expected_prefers_step_b(self):
        for path in self._step_b_files():
            solver, case = path.parent.parent.name, path.stem
            self.assertEqual(golden.load_expected(solver, case)["label"], golden.STEP_B_LABEL)
        solver, case = "pourbaix_solver", "cu_nochloride"
        if not golden.step_b_path(solver, case).exists():
            self.assertEqual(golden.load_expected(solver, case), golden.load_golden(solver, case))

    def test_bless_dry_run_reports_no_drift_for_the_committed_state(self):
        import bless_step_b
        before = sorted(p.as_posix() for p in golden.GOLDEN_DIR.rglob("*.json"))
        drift, log = bless_step_b.bless("pourbaix_solver", dry_run=True)
        self.assertEqual([rows for _, rows in drift if rows], [])
        self.assertTrue(any("behaviour change" in line for line in log))
        self.assertEqual(sorted(p.as_posix() for p in golden.GOLDEN_DIR.rglob("*.json")), before)


def text_ends_with_newline(path: Path) -> bool:
    return path.read_text(encoding="utf-8").endswith("\n")


class ProvenanceTest(unittest.TestCase):
    """Provenance is stripped from the bit-exact comparison, so pin it here."""

    def _fresh(self, solver, case):
        return golden.run_solver(solver, golden.CASES[solver][case])

    def test_tafel_provenance(self):
        import alloy_registry
        import physical_constants as pc
        expected_ids = {
            "solve_316l_default_fields": "ss316l",
            "solve_1018_custom_composition": "steel1018",
            "fit_curve_synthetic_bv": "al6061",
            # every preset-derived field was supplied: the alloy is never resolved
            "solve_unknown_alloy_full_overrides": None,
        }
        for case, registry_id in expected_ids.items():
            with self.subTest(case=case):
                prov = self._fresh("tafel_corrosion_rate_solver", case)["provenance"]["provenance"]
                self.assertEqual(prov["registryVersion"], alloy_registry.REGISTRY_VERSION)
                self.assertEqual(prov["constantsVersion"], pc.CONSTANTS_VERSION)
                self.assertEqual(prov["registryAlloyId"], registry_id)
                # Design step (b): exact SI 2019 products.
                self.assertEqual(prov["gasConstantR_J_molK"], pc.GAS_CONSTANT_R.value)
                self.assertEqual(prov["faraday_C_mol"], pc.FARADAY.value)

    def test_pourbaix_provenance(self):
        import physical_constants as pc
        prov = self._fresh("pourbaix_solver", "fe_chloride_points")["provenance"]["provenance"]
        self.assertEqual(prov["constantsVersion"], pc.CONSTANTS_VERSION)
        # Design step (b): exact SI 2019 products.
        self.assertEqual(prov["gasConstantR_J_molK"], pc.GAS_CONSTANT_R.value)
        self.assertEqual(prov["faraday_C_mol"], pc.FARADAY.value)

    def test_validation_envelope_has_no_provenance(self):
        for solver, case in EXPECTED_BEHAVIOUR_CHANGES:
            self.assertIsNone(self._fresh(solver, case)["provenance"])


class DriftReportTest(unittest.TestCase):
    def test_identical_documents_have_no_rows(self):
        doc = {"a": 1.5, "b": [1, {"c": "x"}], "d": None}
        self.assertEqual(drift_report.diff(doc, json.loads(json.dumps(doc))), [])

    def test_numeric_row_has_abs_and_rel(self):
        rows = drift_report.diff({"x": {"y": 2.0}}, {"x": {"y": 2.5}})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["key"], "x.y")
        self.assertEqual(rows[0]["kind"], "numeric")
        self.assertEqual(rows[0]["abs"], 0.5)
        self.assertEqual(rows[0]["rel"], 0.25)

    def test_type_change_is_detected_even_when_equal(self):
        rows = drift_report.diff({"x": 1}, {"x": 1.0})
        self.assertEqual(len(rows), 1)

    def test_added_removed_changed(self):
        rows = {r["key"]: r["kind"] for r in drift_report.diff(
            {"a": 1, "b": "s", "l": [1, 2]}, {"b": "t", "c": 3, "l": [1]})}
        self.assertEqual(rows, {"a": "removed", "b": "changed", "c": "added", "l[1]": "removed"})

    def test_empty_containers_are_kept(self):
        rows = {r["key"]: r["kind"] for r in drift_report.diff({"a": {}, "b": []}, {"c": {}})}
        self.assertEqual(rows, {"a": "removed", "b": "removed", "c": "added"})
        self.assertEqual(drift_report.diff({"a": {}}, {"a": {}}), [])
        rows = drift_report.diff({"a": {}}, {"a": {"x": 1}})
        self.assertEqual({r["key"] for r in rows}, {"a", "a.x"})

    def test_zero_old_value_has_no_relative_delta(self):
        rows = drift_report.diff({"x": 0.0}, {"x": 1e-9})
        self.assertIsNone(rows[0]["rel"])

    def test_strip_volatile_is_recursive(self):
        doc = {"durationMs": 1, "a": {"timestamp": "t", "b": [{"computeTimeMs": 2, "c": 3}]},
               "pythonVersion": "3.12"}
        self.assertEqual(golden.strip_volatile(doc), {"a": {"b": [{"c": 3}]}})


if __name__ == "__main__":
    unittest.main()
