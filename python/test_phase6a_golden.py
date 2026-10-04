"""Phase 6a golden regression: migrated solvers must stay bit-exact.

Every case in python/golden/phase6a/<solver>/<case>.json was captured at the
pre-migration revision (tools/capture_phase6a_golden.py). The current solver is
run exactly like the app's ad-hoc spawn path and its stdout, with only the
volatile keys stripped, must serialise to the identical canonical JSON text.

Deliberate behaviour changes (silent default -> validation error) are listed in
EXPECTED_BEHAVIOUR_CHANGES; for those cases the old golden stays on disk as the
record of the old behaviour and the test asserts the new validation envelope.
"""

import json
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
# Both were silent defaults before the Phase 6a structural migration:
# - tafel alloyId "unobtainium-x" was solved with the AISI 316L preset;
# - pourbaix element "Unobtainium" was drawn with the Fe system (Ni point branch).
EXPECTED_BEHAVIOUR_CHANGES = {
    ("tafel_corrosion_rate_solver", "edge_unknown_alloy_zero_icorr"): "UNKNOWN_ALLOY",
    ("pourbaix_solver", "edge_unknown_element_badvals"): "UNKNOWN_ELEMENT",
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
                self.assertEqual(golden.step_b_violations(solver, doc["driftVsBase"], doc["stdout"],
                                                          golden.CASES[solver][case]), [])
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
