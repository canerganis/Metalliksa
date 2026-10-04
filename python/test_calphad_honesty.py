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


def assert_no_numbers(test, out):
    for absent in ("equilibriumProfile", "criticalTemperatures", "isEmpirical", "multiElementScheil",
                   "solutePartitioning", "phacompAnalysis", "thermodynamicStabilityIndex"):
        test.assertNotIn(absent, out)


class TestNoSilentFallback(unittest.TestCase):
    def test_without_pycalphad_the_answer_is_unavailable_with_the_exact_reason(self):
        with pycalphad_forced(False):
            out = compute(IN718)
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
            entry = {"id": "fx", "fileName": "fx.tdb", "name": "Fx", "elements": ["AL", "NI"],
                     "status": "assessment", "usable": True, "suitability": "", "statusReason": None}
            old_dir, old_cat = cs.DATABASES_DIR, cs.OPEN_TDB_CATALOG
            cs.DATABASES_DIR, cs.OPEN_TDB_CATALOG = tmp, [entry]
            try:
                for preferred in (None, "fx"):
                    with self.subTest(preferred=preferred):
                        res = cs.resolve_database(["Ni", "Al"], preferred)
                        self.assertFalse(res["ok"])
                        self.assertEqual(res["kind"], "database-test-fixture")
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
                res = cs.resolve_database(list(elements))
                if res["ok"]:
                    self.assertIn(res["id"], ASSESSMENT_IDS)
                else:
                    self.assertNotIn(res["extra"].get("databaseId"), FIXTURE_IDS)
        self.assertEqual(cs.resolve_database(list(IN718))["id"], "cost507")

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
        for elements, missing in (({"W": 88.0, "C": 6.0, "Co": 6.0}, ["Co"]), ({"Fe": 90.0, "P": 5.0, "S": 5.0}, ["P", "S"])):
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

    def derive(self, profile, l12=None, beta=None, sigma=None, phacomp_sigma=None):
        return cs.derive_critical_temperatures(profile, l12, beta, sigma, phacomp_sigma)

    def test_solidus_at_the_grid_minimum_is_unavailable(self):
        # Audit: solidus 600 (the lowest grid T) in all three runs. Solid at 600 and a liquid at the
        # top, but no trace-liquid grid point: nothing brackets the solidus.
        profile = [_pt(600, ("FCC_A1", 1.0)), _pt(1000, ("FCC_A1", 1.0)), _pt(1400, ("FCC_A1", 1.0)),
                   _pt(1450, ("LIQUID", 1.0))]
        values, status = self.derive(profile)
        self.assertIsNone(values["solidusC"])
        self.assertIsNone(values["freezingRangeC"])
        self.assertEqual(status["solidusC"]["status"], "unavailable")
        self.assertIn("grid bound", status["solidusC"]["reason"])
        self.assertEqual(values["liquidusC"], 1450.0)  # an observed grid point, above the grid minimum

    def test_a_trace_liquid_point_inside_the_grid_gives_a_solidus(self):
        profile = [_pt(600, ("FCC_A1", 1.0)), _pt(1300, ("FCC_A1", 0.995), ("LIQUID", 0.005)),
                   _pt(1350, ("FCC_A1", 0.5), ("LIQUID", 0.5)), _pt(1400, ("LIQUID", 1.0))]
        values, status = self.derive(profile)
        self.assertEqual(values["solidusC"], 1300.0)
        self.assertEqual(values["liquidusC"], 1400.0)
        self.assertEqual(values["freezingRangeC"], 100.0)
        self.assertEqual(status["solidusC"]["status"], "computed-grid-resolution")

    def test_trace_liquid_only_at_the_grid_minimum_is_not_a_solidus(self):
        profile = [_pt(600, ("FCC_A1", 0.995), ("LIQUID", 0.005)), _pt(900, ("LIQUID", 1.0))]
        values, status = self.derive(profile)
        self.assertIsNone(values["solidusC"])
        self.assertIn("lowest grid temperature", status["solidusC"]["reason"])

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


@unittest.skipUnless(cs.PYCALPHAD_AVAILABLE,
                     "pycalphad is not installed in this interpreter (the locked CI environment): the real "
                     "equilibrium path is exercised with .runtime/scientific-win-py312-cu128 only")
class TestRealPath(unittest.TestCase):
    def test_ni_al_dupin_runs_the_real_path_and_flags_the_audit_defects(self):
        out = compute({"Ni": 90.0, "Al": 10.0}, unit="at_pct", t_min_c=600.0, t_max_c=1700.0, t_step_c=50.0)
        self.assertIs(out["success"], True)
        self.assertIs(out["isEmpirical"], False)
        self.assertEqual(out["databaseId"], "alni_dupin_2001")
        self.assertEqual(out["databaseStatus"], "assessment")
        crit = out["criticalTemperatures"]
        self.assertIsNone(crit["solidusC"])
        self.assertIsNone(crit["gammaPrimeSolvusC"])
        self.assertEqual(out["criticalTemperatureStatus"]["gammaPrimeSolvusC"]["status"], "unavailable")
        self.assertEqual(out["multiElementScheilStatus"], "screening-curve-not-thermodynamic")
        for row in out["solutePartitioning"]:
            self.assertIn(row["partitionCoefficientSource"], ("tie-line", "default-table-not-thermodynamic"))
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


if __name__ == "__main__":
    unittest.main()
