#!/usr/bin/env python3
"""MatCalc open databases (mc_ni 2.036, mc_fe 2.062) in the CALPHAD catalogue.

Self-contained: every expected value is pinned here (file hashes from the 2026-10-07 download and
repair, catalogue scope, the coverage of the three reference alloys). No network.

  * file / licence / catalogue / coverage tests need no pycalphad (run on the locked CI interpreter);
  * one equilibrium smoke test needs pycalphad (skipped without it; about 10 s cold);
  * --slow (or METALLIX_SLOW_TESTS=1) adds the full studio requests with the Scheil path
    (IN625, 316L, IN718; minutes on one CPU).

    python python/test_calphad_matcalc_open.py [--slow]
"""

import hashlib
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import calphad_solver as cs  # noqa: E402

SLOW = "--slow" in sys.argv or os.environ.get("METALLIX_SLOW_TESTS") == "1"
if "--slow" in sys.argv:
    sys.argv.remove("--slow")

DB_DIR = os.path.join(HERE, "databases")
FILES = {
    "mc_ni_v2036_repaired.tdb": (424658, "c914f534cc99f5fc2f7aab0373cfe5bc720bd2b85b545027d35ac4e0bcc6f94d"),
    "mc_fe_v2062_repaired.tdb": (499133, "cb0a7f9f747b9b16bc8bb5085250f9449091e0031480e3d7527eb0ad1e1f3fd4"),
}
ORIGINALS = {  # MatCalc download, 2026-10-07 (same as external-data-manifest.json)
    "mc_ni_v2036.tdb": "84ba813156e1f7d8bde495d74420319afec03572b981f6b56103807f305313ab",
    "mc_fe_v2062.tdb": "aa02077eac3f602dd7479cbeafb09b450e282716752b3ae2b1fc3a57d9c64865",
}
REPORTS = {
    "mc_ni_v2036_repair_report.json": ("mc_ni_v2036.tdb", "mc_ni_v2036_repaired.tdb", 3586),
    "mc_fe_v2062_repair_report.json": ("mc_fe_v2062.tdb", "mc_fe_v2062_repaired.tdb", 4093),
}
LICENSE = os.path.join(DB_DIR, "MATCALC_OPEN_DATABASES_LICENSE.md")

IN718_SPEC = {"Ni": 53.0, "Cr": 19.0, "Fe": 18.0, "Nb": 5.0, "Mo": 3.0, "Ti": 1.0, "Al": 1.0}
IN718_STUDIO = {"Ni": 52.5, "Cr": 19.0, "Fe": 18.5, "Nb": 5.15, "Mo": 3.05, "Ti": 0.95, "Al": 0.55, "C": 0.04,
                "Co": 0.35}  # SPECIMEN_PRESETS["inconel-718"]
IN625 = {"Ni": 61.0, "Cr": 21.5, "Mo": 9.0, "Nb": 3.6, "Fe": 4.9}
SS316L_STUDIO = {"Fe": 65.5, "Cr": 17.5, "Ni": 12.0, "Mo": 2.5, "Mn": 1.8, "Si": 0.6, "C": 0.02}  # "ss-316l"


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def _base(elements):
    return cs.base_element(cs.normalize_composition(elements)[1])


class TestCommittedFiles(unittest.TestCase):
    def test_tdb_files_are_pinned_and_small(self):
        for name, (size, sha) in FILES.items():
            with self.subTest(file=name):
                path = os.path.join(DB_DIR, name)
                self.assertEqual(os.path.getsize(path), size)
                self.assertLess(size, 50 * 1024 * 1024)
                self.assertEqual(_sha(path), sha)

    def test_files_carry_origin_and_licence_header(self):
        for name in FILES:
            with self.subTest(file=name):
                with open(os.path.join(DB_DIR, name), encoding="utf-8", errors="replace") as fh:
                    head = fh.read(4000)
                self.assertIn("SYNTACTICALLY REPAIRED COPY", head)
                self.assertIn("https://www.matcalc.at/index.php/databases/open-databases", head)
                self.assertIn("odbl/1.0", head)
                self.assertIn("dbcl/1.0", head)
                self.assertIn("ODbL share-alike applies", head)
                original = name.replace("_repaired", "")
                self.assertIn(f"{original} (sha256 {ORIGINALS[original]})", head)

    def test_repair_reports_name_the_pinned_originals(self):
        for name, (source, output, retained) in REPORTS.items():
            with self.subTest(report=name):
                with open(os.path.join(DB_DIR, name), encoding="utf-8") as fh:
                    rep = json.load(fh)
                self.assertEqual(rep["source"], source)
                self.assertEqual(rep["sourceSha256"], ORIGINALS[source])
                self.assertEqual(rep["output"], output)
                self.assertEqual(rep["parametersRetained"], retained)
                self.assertIn({"rule": "drop-directive", "detail": "ATTACH_CONTRIBUTION BCC_B2 BCC_A2 ORDER_DISORDER"},
                              rep["repairs"])

    def test_licence_file_states_odbl_attribution_hashes_and_changes(self):
        with open(LICENSE, encoding="utf-8") as fh:
            text = fh.read()
        for needle in ("Open Database License (ODbL) v1.0", "Database Contents License (DbCL) v1.0",
                       "Erwin Povoden-Karadeniz", "TU Wien", "python/tools/tdb_repair.py", "--allow-ambiguous",
                       "https://www.matcalc.at/images/stories/Download/Database/mc_ni_v2036.tdb",
                       "https://www.matcalc.at/images/stories/Download/Database/mc_fe_v2062.tdb"):
            self.assertIn(needle, text)
        for sha in list(ORIGINALS.values()) + [sha for _, sha in FILES.values()]:
            self.assertIn(sha, text)

    def test_originals_in_the_external_data_manifest_have_the_same_hashes(self):
        with open(os.path.join(HERE, "..", "external-data-manifest.json"), encoding="utf-8") as fh:
            manifest = json.load(fh)
        files = {f["name"]: f["sha256"] for ds in manifest["datasets"] if ds["id"] == "matcalc" for f in ds["files"]}
        for name, sha in ORIGINALS.items():
            self.assertEqual(files[name], sha)


class TestCatalogue(unittest.TestCase):
    def entry(self, db_id):
        return next(e for e in cs.OPEN_TDB_CATALOG if e["id"] == db_id)

    def test_entries_are_assessments_with_a_base_scope(self):
        for db_id, file_name, base, pdens in (("mc_ni", "mc_ni_v2036_repaired.tdb", ["NI"], 10),
                                              ("mc_fe", "mc_fe_v2062_repaired.tdb", ["FE"], 30)):
            with self.subTest(db=db_id):
                e = self.entry(db_id)
                self.assertEqual(e["fileName"], file_name)
                self.assertEqual(e["status"], cs.DB_STATUS_ASSESSMENT)
                self.assertIs(e["usable"], True)
                self.assertEqual(e["assessedBaseElements"], base)
                self.assertEqual(set(e["elements"]), cs.tdb_file_elements(os.path.join(DB_DIR, file_name)))
                self.assertIsNone(cs.database_fixture_reason(e, os.path.join(DB_DIR, file_name)))
                self.assertIn("Not validated against experiment", e["suitability"])
                self.assertIn("BCC_B2", e["excludedPhases"])
                self.assertIs(e["startingPointSeeding"], True)
                self.assertEqual(e["calcOptions"], {"pdens": pdens})
                self.assertEqual(e["scheilTimeBudgetS"], 90.0)

    def test_mc_fe_excludes_the_c15_laves_phase_with_the_reason(self):
        reason = self.entry("mc_fe")["excludedPhases"]["C15_LAVES"]
        self.assertIn("-9e6", reason)
        self.assertIn("1550 degC", reason)
        self.assertNotIn("C15_LAVES", self.entry("mc_ni")["excludedPhases"])

    def test_the_three_alloys_resolve_to_the_matcalc_databases(self):
        for elements, expected in ((IN718_SPEC, "mc_ni"), (IN718_STUDIO, "mc_ni"), (IN625, "mc_ni"),
                                   (SS316L_STUDIO, "mc_fe")):
            with self.subTest(elements=elements):
                at = cs.normalize_composition(elements)[1]
                res = cs.resolve_database(list(at), None, None, cs.base_element(at))
                self.assertTrue(res["ok"], res)
                self.assertEqual(res["id"], expected)

    def test_system_coverage(self):
        cov = {row["id"]: row for row in cs.system_coverage()}
        self.assertEqual((cov["in718"]["status"], cov["in718"]["databaseId"]), ("covered", "mc_ni"))
        self.assertEqual((cov["in625"]["status"], cov["in625"]["databaseId"]), ("covered", "mc_ni"))
        self.assertEqual((cov["ss316l"]["status"], cov["ss316l"]["databaseId"]), ("covered", "mc_fe"))
        for sys_id in ("in718", "in625", "ss316l"):
            self.assertIn("knownDeviation", cov[sys_id])
        self.assertEqual(cov["ti6al4v"]["databaseId"], "cost507")  # unchanged

    def test_never_substituted_and_fixtures_still_refused(self):
        at = cs.normalize_composition(IN718_SPEC)[1]
        res = cs.resolve_database(list(at), "mc_fe", None, "Ni")  # steel database for a Ni-base alloy
        self.assertFalse(res["ok"])
        self.assertEqual(res["kind"], cs.KIND_NOT_ASSESSED)
        res = cs.resolve_database(list(at), "mc_fecocrnbti", None, "Ni")
        self.assertFalse(res["ok"])
        self.assertEqual(res["kind"], cs.KIND_TEST_FIXTURE)
        co = cs.normalize_composition({"Co": 60.0, "Cr": 28.0, "Mo": 6.0, "W": 6.0})[1]
        self.assertFalse(cs.resolve_database(list(co), None, None, "Co")["ok"])


class TestHelpers(unittest.TestCase):
    def test_outside_tested_limits_flags_in625_cr_and_mo_for_mc_ni(self):
        limits = next(e for e in cs.OPEN_TDB_CATALOG if e["id"] == "mc_ni")["testedLimitsWtPct"]
        wt, _ = cs.normalize_composition(IN625)
        out = {row["element"]: row for row in cs.outside_tested_limits(wt, limits)}
        self.assertEqual(set(out), {"Cr", "Mo"})
        self.assertEqual(out["Cr"]["testedUpToWtPct"], 20.0)
        self.assertEqual(out["Mo"]["testedUpToWtPct"], 5.0)
        wt718, _ = cs.normalize_composition(IN718_SPEC)
        self.assertEqual(cs.outside_tested_limits(wt718, limits), [])

    def test_seed_site_fractions_follow_the_overall_composition(self):
        y = cs.seed_site_fractions([["CR", "NI"], ["C", "VA"]], {"NI": 0.75, "CR": 0.2, "C": 0.05})
        self.assertAlmostEqual(y[0] + y[1], 1.0, places=12)
        self.assertAlmostEqual(y[2] + y[3], 1.0, places=12)
        self.assertAlmostEqual(y[0] / y[1], 0.2 / 0.75, places=4)
        self.assertGreater(y[3], 0.9)  # interstitial sublattice mostly vacant

    def test_seed_cloud_is_repeatable_and_on_the_simplex(self):
        constituents = [["AL", "CR", "NI"], ["C", "VA"]]
        x = {"NI": 0.7, "CR": 0.2, "AL": 0.09, "C": 0.01}
        a = cs.seed_cloud(constituents, x)
        b = cs.seed_cloud(constituents, x)
        self.assertEqual(a.shape, (cs.SEED_CLOUD_POINTS + 1, 5))
        self.assertTrue((a == b).all())
        self.assertTrue((abs(a[:, :3].sum(axis=1) - 1.0) < 1e-9).all())
        self.assertTrue((abs(a[:, 3:].sum(axis=1) - 1.0) < 1e-9).all())
        self.assertTrue((a >= 0).all())


@unittest.skipUnless(cs.PYCALPHAD_AVAILABLE, "needs pycalphad")
class TestEquilibriumSmoke(unittest.TestCase):
    """One short grid (5 points, no refinement, no Scheil) for IN625 with mc_ni."""

    def test_in625_two_phase_point_near_the_liquidus(self):
        out = cs.compute_multi_component_equilibrium("IN625 smoke", IN625, t_min_c=1250.0, t_max_c=1350.0,
                                                     t_step_c=25.0, boundary_refinement=False, scheil=False)
        self.assertIs(out["success"], True, out.get("reason"))
        self.assertEqual(out["databaseId"], "mc_ni")
        self.assertIn("not validated against experiment", out["evidenceLabel"])
        self.assertEqual([p["phase"] for p in out["excludedPhases"]], ["BCC_B2"])
        self.assertIs(out["startingPointSeeding"]["enabled"], True)
        self.assertEqual({r["element"] for r in out["compositionOutsideTestedLimits"]}, {"Cr", "Mo"})
        point = next(p for p in out["equilibriumProfile"] if abs(p["temperatureC"] - 1350.0) < 0.01)
        phases = {ph["phaseId"]: ph["fraction"] for ph in point["phases"]}
        self.assertEqual(set(phases), {"FCC_A1", "LIQUID"})
        self.assertAlmostEqual(phases["LIQUID"], EXPECTED_IN625_LIQUID_1350C, delta=0.03)
        low = next(p for p in out["equilibriumProfile"] if abs(p["temperatureC"] - 1250.0) < 0.01)
        self.assertEqual({ph["phaseId"] for ph in low["phases"]}, {"FCC_A1"})


EXPECTED_IN625_LIQUID_1350C = 0.528  # mc_ni 2.036 repaired, pycalphad 0.11.2, seeded pdens 30 (2026-10-07)


@unittest.skipUnless(cs.PYCALPHAD_AVAILABLE and SLOW, "slow: full studio requests (--slow, needs pycalphad)")
class TestStudioRequestsSlow(unittest.TestCase):
    """The studio request (500-1550 degC, 25 K grid, refinement, Scheil 2 K) for the three alloys."""

    def setUp(self):
        # The Scheil wall-time budget (90 s) depends on machine load; for these checks of the path itself
        # it is raised so that the result does not depend on how busy the test machine is.
        self._budgets = {e["id"]: e.get("scheilTimeBudgetS") for e in cs.OPEN_TDB_CATALOG}
        for e in cs.OPEN_TDB_CATALOG:
            if e["id"] in ("mc_ni", "mc_fe"):
                e["scheilTimeBudgetS"] = 900.0

    def tearDown(self):
        for e in cs.OPEN_TDB_CATALOG:
            if e["id"] in ("mc_ni", "mc_fe"):
                e["scheilTimeBudgetS"] = self._budgets[e["id"]]

    def run_studio(self, name, elements):
        return cs.compute_multi_component_equilibrium(name, elements, t_min_c=500.0, t_max_c=1550.0,
                                                      t_step_c=25.0, scheil=True)

    def test_in625_equilibrium_and_scheil(self):
        out = self.run_studio("IN625", IN625)
        self.assertIs(out["success"], True)
        ct = out["criticalTemperatures"]
        self.assertAlmostEqual(ct["liquidusC"], EXPECTED["in625"]["liquidusC"], delta=3.0)
        self.assertAlmostEqual(ct["solidusC"], EXPECTED["in625"]["solidusC"], delta=3.0)
        sch = out["scheilSolidification"]
        self.assertEqual(sch["status"], cs.SCHEIL_STATUS_COMPUTED, sch.get("reason"))
        self.assertEqual(sch["primarySolidPhase"], "FCC_A1")

    def test_316l_equilibrium_and_scheil(self):
        out = self.run_studio("316L", SS316L_STUDIO)
        self.assertIs(out["success"], True)
        self.assertEqual(out["databaseId"], "mc_fe")
        ct = out["criticalTemperatures"]
        self.assertAlmostEqual(ct["liquidusC"], EXPECTED["ss316l"]["liquidusC"], delta=3.0)
        self.assertAlmostEqual(ct["solidusC"], EXPECTED["ss316l"]["solidusC"], delta=3.0)
        sch = out["scheilSolidification"]
        self.assertEqual(sch["primarySolidPhase"], "FCC_A1")
        # 2026-10-07: the path stopped at about 1246 degC with 0.11 % liquid (non-converged equilibrium);
        # it must be reported as incomplete with that reason, never extrapolated.
        if sch["status"] != cs.SCHEIL_STATUS_COMPUTED:
            self.assertEqual(sch["terminationReason"], "equilibrium-not-converged")

    def test_in718_studio_preset(self):
        out = self.run_studio("IN718", IN718_STUDIO)
        self.assertIs(out["success"], True)
        ct = out["criticalTemperatures"]
        self.assertAlmostEqual(ct["liquidusC"], EXPECTED["in718"]["liquidusC"], delta=3.0)
        self.assertAlmostEqual(ct["solidusC"], EXPECTED["in718"]["solidusC"], delta=3.0)
        sch = out["scheilSolidification"]
        self.assertEqual(sch["status"], cs.SCHEIL_STATUS_COMPUTED, sch.get("reason"))
        self.assertEqual(sch["primarySolidPhase"], "FCC_A1")
        self.assertEqual(out["knownDeviations"][0]["systemId"], "in718")


# 2026-10-07 studio runs (pycalphad 0.11.2, committed files, catalogue settings); +-3 K tolerance.
EXPECTED = {
    "in625": {"liquidusC": 1366.1, "solidusC": 1309.1},
    "ss316l": {"liquidusC": 1421.9, "solidusC": 1408.1},
    "in718": {"liquidusC": 1350.4, "solidusC": 1249.9},
}


if __name__ == "__main__":
    unittest.main()
