"""CALPHAD honesty (fx-calphad lane, AUDIT-engines-nonlpbf-opus.md defect D2).

Pins what calphad_solver may and may not answer:
  (a) no silent non-thermodynamic fallback: without pycalphad the answer is the explicit
      "unavailable" envelope; the old fallback model (isEmpirical false, fails Gibbs-Duhem)
      is gone;
  (b) pycalphad test fixtures (file header or catalogue flag) are refused and never auto-selected;
  (c) a requested element absent from the database is refused, never dropped/renormalised
      (Ti-6Al-4V lost its Al);
  (d) solidus-at-the-grid-minimum and gamma-prime-by-phase-name are flagged unavailable.

Everything except the TestRealPath class runs on the locked interpreter, which has no
pycalphad (the fallback branch is tested directly, with PYCALPHAD_AVAILABLE forced off, so
it also runs where pycalphad exists). TestRealPath needs pycalphad and is skipped with a
reason otherwise; it was run with .runtime/scientific-win-py312-cu128 (pycalphad 0.11.2).
"""

import contextlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import calphad_solver as cs  # noqa: E402

FIXTURE_IDS = {"alcocrni", "mc_fecocrnbti", "cr_fe_ni"}
ASSESSMENT_IDS = {"cost507", "alni_dupin_2001", "crtiv_ghosh"}
TI64 = {"Ti": 90.0, "Al": 6.0, "V": 4.0}
IN718 = {"Ni": 53.0, "Cr": 19.0, "Fe": 18.0, "Nb": 5.0, "Mo": 3.0, "Ti": 1.0, "Al": 1.0}
REAL_ELEMENTS = {  # ELEMENT commands of the files as pycalphad 0.11.2 reads them
    "alcocrni.tdb": {"AL", "CO", "CR", "NI"},
    "COST507.tdb": {"AL", "AR", "B", "C", "CE", "CR", "CU", "FE", "HF", "LI", "MG", "MN", "MO", "N", "NB", "ND",
                    "NI", "O", "SI", "SN", "TA", "TI", "V", "W", "Y", "ZN", "ZR"},
    "alni_dupin_2001.tdb": {"AL", "NI"},
    "mc_fecocrnbti.tdb": {"AL", "B", "C", "CO", "CR", "CU", "FE", "H", "HF", "LA", "MN", "MO", "N", "NB", "NI",
                          "O", "P", "PD", "S", "SI", "TI", "V", "W", "Y"},
    "Cr-Fe-Ni_shallow_bcc.tdb": {"CR", "FE", "NI"},
    "crtiv_ghosh.tdb": {"CR", "TI", "V"},
}


@contextlib.contextmanager
def pycalphad_forced(available: bool):
    old = cs.PYCALPHAD_AVAILABLE
    cs.PYCALPHAD_AVAILABLE = available
    try:
        yield
    finally:
        cs.PYCALPHAD_AVAILABLE = old


def compute(elements, **kw):
    return cs.compute_multi_component_equilibrium("t", dict(elements), **kw)


def resolve(elements, preferred=None):
    """resolve_database the way compute_multi_component_equilibrium calls it (base element included)."""
    _, at = cs.normalize_composition(dict(elements))
    return cs.resolve_database(list(at), preferred, None, cs.base_element(at))


def assert_no_numbers(test, out):
    for absent in ("equilibriumProfile", "criticalTemperatures", "isEmpirical", "multiElementScheil",
                   "solutePartitioning", "phacompAnalysis", "thermodynamicStabilityIndex"):
        test.assertNotIn(absent, out)


class TestNoSilentFallback(unittest.TestCase):
    def test_without_pycalphad_the_answer_is_unavailable_with_the_exact_reason(self):
        with pycalphad_forced(False):
            out = compute(TI64)  # a light alloy with a suitable database: pycalphad is the only gap
        self.assertIs(out["success"], False)
        self.assertEqual(out["status"], "unavailable")
        self.assertEqual(out["reason"], "pycalphad not installed")
        self.assertEqual(out["unavailableKind"], "pycalphad-not-installed")
        self.assertIs(out["pycalphadAvailable"], False)
        assert_no_numbers(self, out)
        self.assertNotEqual(out["engine"], "subregular-adaptive-minimizer")

    def test_the_old_fallback_model_is_gone(self):
        for name in ("fallback_subregular_minimization", "evaluate_subregular_thermodynamic_state",
                     "calculate_alloy_critical_boundaries", "run_adaptive_temperature_sweep"):
            self.assertFalse(hasattr(cs, name), name)
        source = (HERE / "calphad_solver.py").read_text(encoding="utf-8")
        self.assertNotIn("subregular-adaptive-minimizer", source)
        self.assertNotIn("fallback_subregular", source)

    def test_every_request_is_unavailable_without_pycalphad_never_a_profile(self):
        with pycalphad_forced(False):
            for elements in (IN718, TI64, {"Ni": 90.0, "Al": 10.0}, {"Al": 88.5, "Si": 10.0, "Mg": 0.5, "Fe": 1.0},
                             {"Fe": 65.5, "Cr": 17.0, "Ni": 12.0, "Mo": 2.5, "Mn": 2.0, "Si": 0.75, "C": 0.03}):
                with self.subTest(elements=elements):
                    out = compute(elements)
                    self.assertIs(out["success"], False)
                    self.assertEqual(out["status"], "unavailable")
                    assert_no_numbers(self, out)
                    self.assertIn("pycalphad not installed", out["reasons"])

    def test_a_failing_pycalphad_equilibrium_is_unavailable_not_a_fallback(self):
        original = cs.solve_pycalphad_equilibrium

        def boom(**kwargs):
            raise RuntimeError("boom")

        cs.solve_pycalphad_equilibrium = boom
        try:
            with pycalphad_forced(True):
                out = compute({"Ni": 90.0, "Al": 10.0})
        finally:
            cs.solve_pycalphad_equilibrium = original
        self.assertIs(out["success"], False)
        self.assertEqual(out["unavailableKind"], "pycalphad-equilibrium-failed")
        self.assertIn("boom", out["reason"])
        assert_no_numbers(self, out)

    def test_unavailable_is_exit_0_json_with_provenance_through_main(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        proc = subprocess.run([sys.executable, "-B", "calphad_solver.py"], cwd=str(HERE), env=env, timeout=120,
                              input=json.dumps({"elements": TI64, "databaseId": "crtiv_ghosh"}).encode(),
                              capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        out = json.loads(proc.stdout.decode("utf-8"))
        self.assertEqual(out["status"], "unavailable")
        self.assertNotIn("errorKind", out)  # not a 422 validation envelope
        self.assertIn("provenance", out)

    def test_database_list_reports_pycalphad_state_and_database_status(self):
        listing = cs.list_available_databases()
        if not cs.PYCALPHAD_AVAILABLE:
            self.assertEqual(listing["pycalphadVersion"], "Not installed")
            self.assertEqual(listing["unavailableReason"], "pycalphad not installed")
        by_id = {e["id"]: e for e in listing["databases"]}
        self.assertEqual({i for i, e in by_id.items() if e["status"] == "test-fixture"}, FIXTURE_IDS)
        self.assertEqual({i for i, e in by_id.items() if e["status"] == "assessment"}, ASSESSMENT_IDS)
        self.assertEqual(listing["usableDatabasesCount"], len(ASSESSMENT_IDS))


class TestFixtureDatabasesRefused(unittest.TestCase):
    def test_catalogue_marks_exactly_the_fixtures_and_does_not_present_them_as_assessments(self):
        for entry in cs.OPEN_TDB_CATALOG:
            with self.subTest(db=entry["id"]):
                if entry["id"] in FIXTURE_IDS:
                    self.assertEqual(entry["status"], "test-fixture")
                    self.assertIs(entry["usable"], False)
                    self.assertTrue(entry["statusReason"])
                    text = (entry["name"] + entry["description"] + entry["source"] + entry["suitability"]).lower()
                    self.assertIn("test", text)
                    for claim in ("sgte steel assessment", "saunders", "open calphad al-co-cr-ni assessment",
                                  "superalloys (inconel 718"):
                        self.assertNotIn(claim, text)
                else:
                    self.assertEqual(entry["status"], "assessment")
                    self.assertIs(entry["usable"], True)

    def test_headers_alone_identify_the_two_files_that_carry_a_testing_header(self):
        # Independent of the catalogue flag: the file header text.
        for file_name in ("alcocrni.tdb", "mc_fecocrnbti.tdb"):
            reason = cs.database_fixture_reason(None, os.path.join(cs.DATABASES_DIR, file_name))
            self.assertIsNotNone(reason, file_name)
            self.assertTrue(reason.startswith("file header:"), reason)
        for file_name in ("COST507.tdb", "alni_dupin_2001.tdb", "crtiv_ghosh.tdb"):
            self.assertIsNone(cs.database_fixture_reason(None, os.path.join(cs.DATABASES_DIR, file_name)), file_name)

    def test_header_detection_refuses_a_file_even_if_its_catalogue_entry_says_assessment(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "fx.tdb").write_text(
                "$ FOR TESTING PURPOSES ONLY -- NOT FOR RESEARCH\n ELEMENT AL FCC_A1 26.98 0 0 !\n"
                " ELEMENT NI FCC_A1 58.69 0 0 !\n", encoding="utf-8")
            Path(tmp, "ok.tdb").write_text(" ELEMENT AL FCC_A1 26.98 0 0 !\n ELEMENT NI FCC_A1 58.69 0 0 !\n",
                                           encoding="utf-8")
            fx = {"id": "fx", "fileName": "fx.tdb", "name": "Fx", "elements": ["AL", "NI"],
                  "status": "assessment", "usable": True, "suitability": "", "statusReason": None,
                  "assessedBaseElements": ["NI", "AL"]}
            ok = dict(fx, id="ok", fileName="ok.tdb", name="Ok")
            old_dir, old_cat = cs.DATABASES_DIR, cs.OPEN_TDB_CATALOG
            cs.DATABASES_DIR = tmp
            try:
                cs.OPEN_TDB_CATALOG = [fx]
                res = cs.resolve_database(["Ni", "Al"], "fx", None, "Ni")  # asked for by id: refused
                self.assertFalse(res["ok"])
                self.assertEqual(res["kind"], "database-test-fixture")
                # auto mode skips the file (recorded), it does not abort the selection ...
                res = cs.resolve_database(["Ni", "Al"], None, None, "Ni")
                self.assertFalse(res["ok"])
                self.assertEqual(res["extra"]["databasesConsidered"][0]["status"], "test-fixture-skipped")
                # ... so a later, genuine database is still found
                cs.OPEN_TDB_CATALOG = [fx, ok]
                res = cs.resolve_database(["Ni", "Al"], None, None, "Ni")
                self.assertTrue(res["ok"])
                self.assertEqual(res["id"], "ok")
            finally:
                cs.DATABASES_DIR, cs.OPEN_TDB_CATALOG = old_dir, old_cat

    def test_asking_for_a_fixture_by_id_is_refused_with_the_reason(self):
        for db_id in FIXTURE_IDS:
            with self.subTest(db=db_id):
                with pycalphad_forced(True):  # even where pycalphad exists
                    out = compute({"Ni": 60.0, "Cr": 20.0, "Fe": 20.0}, database_id=db_id)
                self.assertIs(out["success"], False)
                self.assertEqual(out["status"], "unavailable")
                self.assertEqual(out["unavailableKind"], "database-test-fixture")
                self.assertIn("test fixture", out["reason"])
                self.assertEqual(out["databaseId"], db_id)
                self.assertEqual(out["databaseStatus"], "test-fixture")
                assert_no_numbers(self, out)

    def test_automatic_choice_never_lands_on_a_fixture(self):
        # Before: IN718 -> alcocrni/mc_fecocrnbti, 316L -> mc_fecocrnbti, Fe-Cr-Ni -> the 1-phase file.
        for elements in (IN718, {"Fe": 65.5, "Cr": 17.0, "Ni": 12.0, "Mo": 2.5, "Mn": 2.0}, {"Fe": 70.0, "Cr": 18.0, "Ni": 12.0},
                         {"Ni": 70.0, "Al": 10.0, "Cr": 10.0, "Co": 10.0}, {"Co": 60.0, "Cr": 28.0, "Mo": 6.0, "W": 6.0}):
            with self.subTest(elements=elements):
                res = resolve(elements)
                if res["ok"]:
                    self.assertIn(res["id"], ASSESSMENT_IDS)
                else:
                    self.assertNotIn(res["extra"].get("databaseId"), FIXTURE_IDS)

    def test_binary_ni_al_uses_the_dupin_assessment(self):
        res = cs.resolve_database(["Ni", "Al"])
        self.assertTrue(res["ok"])
        self.assertEqual(res["id"], "alni_dupin_2001")
        self.assertEqual(res["status"], "assessment")


class TestMissingElementsRefused(unittest.TestCase):
    def test_ti_6al_4v_on_the_cr_ti_v_database_is_refused_listing_al(self):
        # Before: Al was dropped, the rest renormalised, beta transus 800 degC at grid resolution.
        out = compute(TI64, database_id="crtiv_ghosh")
        self.assertIs(out["success"], False)
        self.assertEqual(out["unavailableKind"], "elements-missing-from-database")
        self.assertEqual(out["missingElements"], ["Al"])
        self.assertIn("Al", out["reason"])
        self.assertEqual(out["requestedElements"], ["Ti", "Al", "V"])
        assert_no_numbers(self, out)

    def test_automatic_choice_keeps_every_element(self):
        with pycalphad_forced(False):
            out = compute(TI64)
        self.assertEqual(out["databaseId"], "cost507")  # the narrowest assessment containing Ti, Al and V
        self.assertEqual(out["requestedElements"], ["Ti", "Al", "V"])
        self.assertEqual(out["unavailableKind"], "pycalphad-not-installed")

    def test_no_database_covers_lists_the_missing_elements(self):
        # Ti base: COST 507 is in scope but has no Co; Al base: nothing has P and S.
        for elements, missing in (({"Ti": 80.0, "Al": 10.0, "Co": 10.0}, ["Co"]), ({"Al": 90.0, "P": 5.0, "S": 5.0}, ["P", "S"])):
            with self.subTest(elements=elements):
                out = compute(elements)
                self.assertEqual(out["unavailableKind"], "no-database-covers-elements")
                self.assertEqual(out["missingElements"], missing)
                self.assertIn("lacks", out["reason"])
                self.assertNotIn(out["databaseId"], FIXTURE_IDS)
                assert_no_numbers(self, out)

    def test_both_reasons_are_reported_when_pycalphad_is_also_missing(self):
        with pycalphad_forced(False):
            out = compute(TI64, database_id="crtiv_ghosh")
        self.assertEqual(out["unavailableKind"], "elements-missing-from-database")
        self.assertIn("pycalphad not installed", out["reasons"])

    def test_custom_tdb_text_missing_an_element_is_refused(self):
        text = "$ comment ELEMENT XX\n ELEMENT TI HCP_A3 47.88 0 0 !\n ELEMENT V BCC_A2 50.94 0 0 !\n"
        out = compute(TI64, custom_tdb_text=text)
        self.assertEqual(out["unavailableKind"], "elements-missing-from-database")
        self.assertEqual(out["missingElements"], ["Al"])
        self.assertEqual(out["databaseStatus"], "user-supplied")

    def test_unknown_database_id_is_refused_not_ignored(self):
        out = compute({"Ni": 90.0, "Al": 10.0}, database_id="no_such_db")
        self.assertEqual(out["unavailableKind"], "unknown-database-id")

    def test_tdb_element_parser(self):
        self.assertEqual(cs.tdb_elements_from_text(
            "ELEMENT /- ELECTRON_GAS 0 0 0 !\nELEMENT VA VACUUM 0 0 0 !\n element al fcc_a1 1 2 3 ! ELEMENT NI FCC_A1 1 2 3 !\n"
            "$ ELEMENT ZZ\nFUNCTION F 1 2; 3 N !\n"), {"AL", "NI"})

    def test_catalogue_element_lists_are_the_files_elements(self):
        for entry in cs.OPEN_TDB_CATALOG:
            with self.subTest(db=entry["id"]):
                path = os.path.join(cs.DATABASES_DIR, entry["fileName"])
                self.assertEqual(cs.tdb_file_elements(path), REAL_ELEMENTS[entry["fileName"]])
                self.assertEqual(set(entry["elements"]), REAL_ELEMENTS[entry["fileName"]])


def _pt(t, *phases):
    return {"temperatureC": float(t), "phases": [{"phaseId": p, "fraction": f} for p, f in phases]}


class TestCriticalTemperatureFlags(unittest.TestCase):
    """derive_critical_temperatures is a pure function of the profile (no pycalphad needed)."""

    def derive(self, profile, l12=None, beta=None, sigma=None, phacomp_sigma=None, **kw):
        return cs.derive_critical_temperatures(profile, l12, beta, sigma, phacomp_sigma, **kw)

    def test_solid_at_the_grid_minimum_is_never_reported_as_the_solidus(self):
        # Audit: solidus 600 (the lowest grid T) in all three runs. Solid at 600, liquid at the
        # top: the solidus is the bracket 1400-1450, not the grid minimum.
        profile = [_pt(600, ("FCC_A1", 1.0)), _pt(1000, ("FCC_A1", 1.0)), _pt(1400, ("FCC_A1", 1.0)),
                   _pt(1450, ("LIQUID", 1.0))]
        values, status = self.derive(profile)
        self.assertEqual(values["solidusC"], 1425.0)
        self.assertEqual(status["solidusC"]["status"], "bracketed-by-grid")
        self.assertEqual(status["solidusC"]["bracketC"], [1400.0, 1450.0])
        self.assertEqual(values["liquidusC"], 1425.0)

    def test_liquid_present_at_the_grid_minimum_gives_no_solidus(self):
        profile = [_pt(600, ("FCC_A1", 0.995), ("LIQUID", 0.005)), _pt(900, ("LIQUID", 1.0))]
        values, status = self.derive(profile)
        self.assertIsNone(values["solidusC"])
        self.assertEqual(status["solidusC"]["status"], "unavailable")
        self.assertIn("lowest grid temperature", status["solidusC"]["reason"])

    def test_no_liquid_anywhere_gives_no_solidus_and_no_liquidus(self):
        values, status = self.derive([_pt(t, ("FCC_A1", 1.0)) for t in (600, 900, 1200, 1450)])
        self.assertIsNone(values["solidusC"])
        self.assertIsNone(values["liquidusC"])
        self.assertIn("above the grid", status["solidusC"]["reason"])

    def test_the_bracket_is_refined_by_multi_section_to_the_tolerance(self):
        # Synthetic liquid fraction: 0 below 1300.3, linear to 1 at 1337.7 (solidus 1300.3, liquidus 1337.7).
        def true_liquid(t):
            return min(1.0, max(0.0, (t - 1300.3) / (1337.7 - 1300.3)))

        def refine(temps):
            return [true_liquid(t) for t in temps]

        grid = [_pt(t, *([("LIQUID", round(true_liquid(t), 4))] if true_liquid(t) > 0.001 else []),
                    *([("FCC_A1", round(1 - true_liquid(t), 4))] if true_liquid(t) < 0.999 else []))
                for t in (1250, 1275, 1300, 1325, 1350, 1375)]
        values, status = self.derive(grid, refine=refine, tolerance_c=0.5)
        self.assertEqual(status["solidusC"]["status"], "bisected")
        self.assertAlmostEqual(values["solidusC"], 1300.3, delta=0.5)
        self.assertAlmostEqual(values["liquidusC"], 1337.7, delta=0.5)
        lo, hi = status["solidusC"]["bracketC"]
        self.assertLessEqual(lo, 1300.3 + 0.5)
        self.assertGreaterEqual(hi, 1300.3 - 0.5)
        self.assertLessEqual(hi - lo, 0.5)
        self.assertEqual(status["solidusC"]["gridBracketC"], [1300.0, 1325.0])
        self.assertLessEqual(status["solidusC"]["refinementRounds"], 3)
        self.assertAlmostEqual(values["freezingRangeC"], 37.4, delta=1.0)

    def test_a_refinement_point_that_does_not_converge_leaves_the_grid_bracket(self):
        profile = [_pt(1250, ("FCC_A1", 1.0)), _pt(1350, ("LIQUID", 1.0))]
        values, status = self.derive(profile, refine=lambda temps: [None] * len(temps))
        self.assertEqual(status["solidusC"]["status"], "bracketed-by-grid")
        self.assertEqual(status["solidusC"]["bracketC"], [1250.0, 1350.0])
        self.assertEqual(values["solidusC"], 1300.0)

    def test_not_converged_grid_points_are_ignored_and_flagged(self):
        profile = [_pt(1250, ("FCC_A1", 1.0)),
                   {"temperatureC": 1275.0, "status": "not-converged", "phases": []},  # would read as "no liquid"
                   _pt(1300, ("LIQUID", 1.0))]
        values, status = self.derive(profile)
        self.assertEqual(status["solidusC"]["gridBracketC"], [1250.0, 1300.0])
        self.assertIn("did not converge", status["solidusC"]["warning"])
        values, status = self.derive([{"temperatureC": 1250.0, "status": "not-converged", "phases": []}])
        self.assertIsNone(values["liquidusC"])
        self.assertEqual(status["liquidusC"]["reason"], "no grid point converged")

    def test_liquidus_is_never_a_fabricated_default(self):
        # Audit: "liquidus 1500" was t_max - 50 when no liquid appeared. Now: unavailable.
        profile = [_pt(t, ("FCC_A1", 1.0)) for t in (600, 900, 1200, 1450)]
        values, status = self.derive(profile)
        self.assertIsNone(values["liquidusC"])
        self.assertNotIn(1400.0, values.values())  # t_max - 50
        self.assertIn("above the grid", status["liquidusC"]["reason"])

    def test_fully_liquid_at_the_grid_minimum_gives_no_liquidus(self):
        profile = [_pt(1500, ("LIQUID", 1.0)), _pt(1600, ("LIQUID", 1.0))]
        values, status = self.derive(profile)
        self.assertIsNone(values["liquidusC"])
        self.assertIn("lowest grid temperature", status["liquidusC"]["reason"])

    def test_gamma_prime_by_phase_name_is_never_a_solvus(self):
        # Audit: Ni-10at%Al reported single-phase "L12_FCC" 600-1450 degC and a gamma-prime solvus of
        # 1425 degC; that L12 is the disordered gamma.
        profile = [_pt(t, ("FCC_L12", 1.0)) for t in range(600, 1426, 25)] + [_pt(1450, ("LIQUID", 1.0))]
        values, status = self.derive(profile, l12=1425.0)
        self.assertIsNone(values["gammaPrimeSolvusC"])
        flag = status["gammaPrimeSolvusC"]
        self.assertEqual(flag["status"], "unavailable")
        self.assertIn("phase name only", flag["reason"])
        self.assertEqual(flag["observedByNameOnly"]["highestGridTemperatureC"], 1425.0)

    def test_gamma_prime_without_any_l12_phase_is_unavailable_too(self):
        values, status = self.derive([_pt(600, ("FCC_A1", 1.0))])
        self.assertIsNone(values["gammaPrimeSolvusC"])
        self.assertEqual(status["gammaPrimeSolvusC"]["status"], "unavailable")

    def test_every_critical_temperature_key_has_a_status(self):
        values, status = self.derive([_pt(600, ("FCC_A1", 1.0))], phacomp_sigma=850.0)
        self.assertEqual(set(values), set(status))
        self.assertEqual(status["tcpSigmaRiskTemperatureC"]["status"], "screening-constant")
        self.assertEqual(values["tcpSigmaRiskTemperatureC"], 850.0)


class TestDatabaseScope(unittest.TestCase):
    """Science review B1: IN718 was routed to the light-alloy database COST 507 and answered
    success true with FCC + 30-96 % BCC_B2 and no liquid below 1425 C."""

    def test_catalogue_declares_machine_readable_scope(self):
        scope = {e["id"]: e["assessedBaseElements"] for e in cs.OPEN_TDB_CATALOG}
        self.assertEqual(scope["cost507"], ["AL", "MG", "TI"])
        self.assertEqual(scope["alni_dupin_2001"], ["AL", "NI"])
        for fixture in FIXTURE_IDS:
            self.assertEqual(scope[fixture], [])
        for entry in cs.OPEN_TDB_CATALOG:
            if entry["status"] == "assessment":
                self.assertTrue(entry["assessedBaseElements"], entry["id"])

    def test_in718_is_never_routed_to_cost_507(self):
        for pyc in (False, True):
            with self.subTest(pycalphad=pyc), pycalphad_forced(pyc):
                out = compute(IN718)
                self.assertIs(out["success"], False)
                self.assertEqual(out["baseElement"], "Ni")
                self.assertNotEqual(out["databaseId"], "cost507")
                self.assertEqual(out["unavailableKind"], "no-database-covers-elements")
                assert_no_numbers(self, out)
                considered = {c["databaseId"]: c for c in out["databasesConsidered"]}
                self.assertEqual(considered["cost507"]["notAssessedForBase"], "Ni")

    def test_explicit_cost_507_for_a_ni_base_alloy_is_refused_with_the_reason(self):
        out = compute(IN718, database_id="cost507")
        self.assertEqual(out["unavailableKind"], "database-not-assessed-for-base")
        self.assertIn("database 'cost507' is not assessed for Ni-base alloys", out["reason"])
        self.assertEqual(out["assessedBaseElements"], ["AL", "MG", "TI"])
        self.assertIn("Ni-, Fe- and Co-base alloys", out["databaseSuitability"])
        assert_no_numbers(self, out)

    def test_fe_and_co_base_alloys_have_no_database(self):
        for elements in ({"Fe": 65.5, "Cr": 17.0, "Ni": 12.0, "Mo": 2.5, "Mn": 2.0},
                         {"Co": 60.0, "Cr": 28.0, "Mo": 6.0, "W": 6.0}):
            with self.subTest(elements=elements):
                out = compute(elements)
                self.assertEqual(out["unavailableKind"], "database-not-assessed-for-base")
                self.assertIn("databases are never substituted", out["reason"])
                self.assertNotIn("databaseId", out)

    def test_light_alloys_still_resolve_to_cost_507(self):
        for elements in (TI64, {"Al": 88.5, "Si": 10.0, "Mg": 0.5, "Fe": 1.0}, {"Mg": 92.0, "Al": 3.0, "Zn": 1.0}):
            with self.subTest(elements=elements):
                res = resolve(elements)
                self.assertTrue(res["ok"], res)
                self.assertEqual(res["id"], "cost507")
        with pycalphad_forced(False):
            out = compute(TI64)
        self.assertIn("Al, Mg or Ti base", out["databaseSuitability"])  # shown by the UI

    def test_the_solver_result_carries_the_suitability_text(self):
        res = resolve({"Ni": 90.0, "Al": 10.0})
        self.assertEqual(res["id"], "alni_dupin_2001")
        self.assertEqual(res["suitability"], "Binary Al-Ni only")


def _fake_equilibrium(nan_rows, n_comp=3):
    """Stand-in for pycalphad's equilibrium(): finite everywhere except the given rows."""
    class Arr:
        def __init__(self, values):
            self.values = np.asarray(values)
            self.shape = self.values.shape

    def fake(dbf, comps, phases, conditions):
        temps = list(conditions["T"])
        n = len(temps)
        gm = np.full(n, -50000.0)
        mu = np.full((n, n_comp), -60000.0)
        nps = np.full((n, 3), np.nan)
        nps[:, 0] = 1.0
        names = np.array([["HCP_A3", "", ""]] * n, dtype=object)
        for r in nan_rows:
            gm[r] = np.nan
            mu[r] = np.nan
            nps[r] = np.nan
            names[r] = ""
        return SimpleNamespace(T=Arr(temps), component=Arr(["TI", "AL", "V"]), GM=Arr(gm), MU=Arr(mu),
                               NP=Arr(nps), Phase=Arr(names))
    return fake


class TestNonConvergedEquilibrium(unittest.TestCase):
    """Code review B1, on the lock: pycalphad returns NaN for a point that did not converge; the
    solver must never put NaN in the JSON or report such a point as a state."""

    def run_with(self, nan_rows):
        fake_dbf = SimpleNamespace(elements=["TI", "AL", "V", "VA"], phases={"HCP_A3": 1})
        fake_v = SimpleNamespace(P="P", T="T", X=lambda c: "X_" + str(c))
        patches = (mock.patch.object(cs, "PYCALPHAD_AVAILABLE", True),
                   mock.patch.object(cs, "np", np, create=True),
                   mock.patch.object(cs, "v", fake_v, create=True),
                   mock.patch.object(cs, "equilibrium", _fake_equilibrium(nan_rows), create=True),
                   mock.patch.object(cs, "load_database_with_info",
                                     lambda *a, **k: (fake_dbf, {"status": "miss", "sha256": "fake"})),
                   mock.patch.dict(sys.modules, {"pycalphad": None}))  # no Workspace: plain equilibrium path
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            return compute(TI64, t_min_c=500.0, t_max_c=1450.0, t_step_c=25.0)

    def test_all_points_non_finite_is_unavailable(self):
        out = self.run_with(range(39))
        self.assertIs(out["success"], False)
        self.assertEqual(out["status"], "unavailable")
        self.assertEqual(out["unavailableKind"], "pycalphad-equilibrium-failed")
        self.assertEqual(out["reason"], "pycalphad equilibrium failed (non-finite results)")
        self.assertEqual((out["nonConvergedPoints"], out["gridPoints"]), (39, 39))
        assert_no_numbers(self, out)
        json.dumps(out, allow_nan=False)

    def test_more_than_half_non_finite_is_unavailable(self):
        out = self.run_with(range(20))
        self.assertEqual(out["unavailableKind"], "pycalphad-equilibrium-failed")
        self.assertEqual(out["nonConvergedPoints"], 20)

    def test_a_few_non_finite_points_are_null_with_a_status_and_the_rest_survives(self):
        out = self.run_with([5, 6, 30])
        self.assertIs(out["success"], True)
        profile = out["equilibriumProfile"]
        self.assertEqual(len(profile), 39)
        failed = [p for p in profile if p["status"] == "not-converged"]
        self.assertEqual(len(failed), 3)
        for p in failed:
            self.assertEqual(p["phases"], [])
            for key in ("totalGibbsEnergy_kJ_mol", "chemicalPotentials_J_mol", "thermodynamicActivities"):
                self.assertIsNone(p[key])
        self.assertEqual(out["nonConvergedPoints"], [p["temperatureC"] for p in failed])
        good = [p for p in profile if p["status"] == "converged"]
        self.assertEqual(len(good), 36)
        self.assertTrue(all(p["totalGibbsEnergy_kJ_mol"] == -50.0 for p in good))
        json.dumps(out, allow_nan=False)  # no NaN anywhere
        # a failed point is not read as "no liquid": the liquidus/solidus reasons are about the converged grid
        self.assertEqual(out["criticalTemperatureStatus"]["solidusC"]["status"], "unavailable")

    def test_serialisation_backstop_never_emits_nan(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            text = cs.serialize_result({"success": True, "alloyName": "x", "value": bad, "provenance": {"a": 1}})
            doc = json.loads(text, parse_constant=lambda c: self.fail(f"non-JSON constant {c}"))
            self.assertIs(doc["success"], False)
            self.assertEqual(doc["unavailableKind"], "non-finite-result")
            self.assertEqual(doc["reason"], "pycalphad equilibrium failed (non-finite results)")
        self.assertEqual(json.loads(cs.serialize_result({"success": True, "v": 1.5}))["v"], 1.5)


class TestPhacompScope(unittest.TestCase):
    """Science review S3: AlSi10Mg and Ti-6Al-4V reported "High" TCP risk and an 850 C sigma temperature."""

    def phacomp(self, elements, unit="wt_pct"):
        return cs.calculate_phacomp(cs.normalize_composition(dict(elements), unit)[1])

    def test_only_ni_base_alloys_get_a_phacomp_screening(self):
        for elements in ({"Al": 88.5, "Si": 10.0, "Mg": 0.5, "Fe": 1.0}, TI64,
                         {"Fe": 65.5, "Cr": 17.0, "Ni": 12.0, "Mo": 2.5}):
            with self.subTest(elements=elements):
                p = self.phacomp(elements)
                self.assertEqual(p["status"], "unavailable")
                self.assertIn("Ni-base superalloys only", p["reason"])
                for key in ("n_v_bar", "m_d_bar", "tcpEmbrittlementRisk", "tcpSigmaRiskTemperatureC",
                            "thermodynamicStabilityIndex"):
                    self.assertIsNone(p[key], key)

    def test_ni_base_uses_the_tabulated_values_and_nothing_invented(self):
        p = self.phacomp({"Ni": 80.0, "Cr": 20.0})
        self.assertEqual(p["status"], "screening-tabulated-values")
        self.assertIn(p["tcpEmbrittlementRisk"], ("Low", "Moderate", "High"))
        p = self.phacomp({"Ni": 90.0, "Cu": 10.0})  # Cu has no tabulated Nv/Md: no default of 1.0
        self.assertEqual(p["status"], "unavailable")
        self.assertIn("Cu", p["reason"])


@unittest.skipUnless(cs.PYCALPHAD_AVAILABLE,
                     "pycalphad is not installed in this interpreter (the locked CI environment): the real "
                     "equilibrium path is exercised with .runtime/scientific-win-py312-cu128 only")
class TestRealPath(unittest.TestCase):
    def test_ni_al_dupin_runs_the_real_path_and_flags_the_audit_defects(self):
        out = compute({"Ni": 90.0, "Al": 10.0}, unit="at_pct", t_min_c=600.0, t_max_c=1700.0, t_step_c=20.0)
        self.assertIs(out["success"], True)
        self.assertIs(out["isEmpirical"], False)
        self.assertEqual(out["databaseId"], "alni_dupin_2001")
        self.assertEqual(out["databaseStatus"], "assessment")
        crit = out["criticalTemperatures"]
        # independent pycalphad bisection (review oracle): solidus 1444.7, liquidus 1446.8
        self.assertAlmostEqual(crit["solidusC"], 1444.7, delta=0.5)
        self.assertAlmostEqual(crit["liquidusC"], 1446.8, delta=0.5)
        self.assertEqual(out["criticalTemperatureStatus"]["solidusC"]["status"], "bisected")
        self.assertIsNone(crit["gammaPrimeSolvusC"])
        self.assertEqual(out["criticalTemperatureStatus"]["gammaPrimeSolvusC"]["status"], "unavailable")
        # the former ad hoc screening curve and the default k table are gone: a stepwise Scheil-Gulliver
        # path from pycalphad equilibria, and k only from its primary-phase tie-line
        self.assertEqual(out["multiElementScheilStatus"], "pycalphad-scheil-gulliver")
        for row in out["solutePartitioning"]:
            self.assertEqual(row["partitionCoefficientSource"], "scheil-primary-phase-tie-line")
            self.assertNotIn("assumedPrecipitateFraction", row)
        # pycalphad's own consistency: fractions sum to 1, and sum(x_i mu_i) = G_m
        for point in out["equilibriumProfile"]:
            self.assertAlmostEqual(sum(ph["fraction"] for ph in point["phases"]), 1.0, delta=2e-3)
            gm = point["totalGibbsEnergy_kJ_mol"] * 1000.0
            x_mu = sum(out["atomicFractions"][el.capitalize()] * mu
                       for el, mu in point["chemicalPotentials_J_mol"].items() if el != "VA")
            self.assertAlmostEqual(x_mu, gm, delta=max(5.0, 1e-4 * abs(gm)))

    def test_solving_directly_on_a_database_without_al_is_refused(self):
        wt, at = cs.normalize_composition(TI64)
        path = os.path.join(cs.DATABASES_DIR, "crtiv_ghosh.tdb")
        with self.assertRaises(cs.CalphadUnavailable) as ctx:
            cs.solve_pycalphad_equilibrium("t", wt, at, 600.0, 1700.0, 100.0, path, "Cr-Ti-V")
        self.assertEqual(ctx.exception.kind, "elements-missing-from-database")
        self.assertEqual(ctx.exception.extra["missingElements"], ["Al"])

    def test_the_element_parser_agrees_with_pycalphad_for_every_catalogue_file(self):
        from pycalphad import Database
        for entry in cs.OPEN_TDB_CATALOG:
            path = os.path.join(cs.DATABASES_DIR, entry["fileName"])
            real = {str(e).upper() for e in Database(path).elements} - {"VA", "/-"}
            self.assertEqual(cs.tdb_file_elements(path), real, entry["id"])


    def test_alsi10mg_bracket_is_refined_and_confirmed_by_independent_equilibria(self):
        from pycalphad import Database, equilibrium, variables as v
        elements = {"Al": 88.5, "Si": 10.0, "Mg": 0.5, "Fe": 1.0}
        out = compute(elements, t_min_c=400.0, t_max_c=750.0, t_step_c=10.0)
        self.assertIs(out["success"], True)
        status = out["criticalTemperatureStatus"]
        self.assertEqual(status["solidusC"]["status"], "bisected")
        self.assertEqual(status["liquidusC"]["status"], "bisected")
        self.assertLess(out["criticalTemperatures"]["solidusC"], out["criticalTemperatures"]["liquidusC"])
        db = Database(os.path.join(cs.DATABASES_DIR, "COST507.tdb"))
        _, at = cs.normalize_composition(elements)
        comps = [k.upper() for k in at] + ["VA"]

        def liquid_at(t_c):
            cond = {v.P: 101325, v.T: t_c + 273.15}
            for k in at:
                if k != "Al":
                    cond[v.X(k.upper())] = at[k]
            eq = equilibrium(db, comps, list(db.phases.keys()), cond)
            return sum(float(n) for p, n in zip(eq.Phase.values.ravel(), eq.NP.values.ravel())
                       if p == "LIQUID" and float(n) > 0.001)

        lo, hi = status["solidusC"]["bracketC"]
        self.assertEqual(liquid_at(lo), 0.0)
        self.assertGreater(liquid_at(hi), 0.001)
        lo, hi = status["liquidusC"]["bracketC"]
        self.assertLess(liquid_at(lo), 0.999)
        self.assertGreaterEqual(liquid_at(hi), 0.999)
        # the grid bracket alone was 10 degC wide
        self.assertLessEqual(status["solidusC"]["toleranceC"], 0.5)

    def test_ti_6al_4v_preset_with_oxygen_is_unavailable_never_nan(self):
        # Code-review B1: the Studio's Ti-6Al-4V preset (Ti, Al, V, Fe, O) on COST 507 returned 39/39 NaN
        # grid points with success true and invalid JSON.
        preset = {"Ti": 89.6, "Al": 6.2, "V": 4.0, "Fe": 0.15, "O": 0.05}
        out = compute(preset, t_min_c=500.0, t_max_c=1450.0, t_step_c=25.0)
        self.assertIs(out["success"], False)
        self.assertEqual(out["status"], "unavailable")
        self.assertEqual(out["unavailableKind"], "pycalphad-equilibrium-failed")
        self.assertEqual(out["reason"], "pycalphad equilibrium failed (non-finite results)")
        self.assertEqual(out["nonConvergedPoints"], out["gridPoints"])
        json.dumps(out, allow_nan=False)  # raises on NaN / Infinity



if __name__ == "__main__":
    unittest.main()
