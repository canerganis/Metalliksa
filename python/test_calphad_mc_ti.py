#!/usr/bin/env python3
"""MatCalc mc_ti 2.03 (Ti alloys) in the CALPHAD catalogue, scoped to Ti-6Al-4V critical temperatures.

Self-contained: file hashes, scope and the Ti-6Al-4V reference values are pinned here. No network.

  * file / licence / catalogue / scope tests need no pycalphad;
  * the equilibrium test needs pycalphad (skipped without it; a coarse 50 K scan plus a 1 K local scan);
  * Ti-6Al-4V (wt% Ti 90, Al 6, V 4; x_Al 0.10195, x_V 0.03600): beta transus 996 C, liquidus 1648 C,
    solidus 1578 C, each within 10 K. The numbers are the database's own result (pycalphad 0.11.2); handbook
    values are about 995 C (transus) and 1655 C (liquidus); the solidus is about 25 K below handbook.

    python python/test_calphad_mc_ti.py
"""

import hashlib
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import calphad_solver as cs  # noqa: E402
import calphad_test_lane  # noqa: E402

DB_DIR = os.path.join(HERE, "databases")
FILE = "mc_ti_v203_repaired.tdb"
SIZE = 81833
SHA = "f8758e12d8a96109b4dee0e0d95365ebe6ec19b0d1b8e3b249465c46a12e94ff"
ORIGINAL_SHA = "7bec5404071fa3cbdaf340bdb431af98f5a00a6d5526b84ff31834b5ff5841cb"
SCOPE_FLAG = ("Valid for beta transus, liquidus/solidus and single-phase beta. Not for alpha/beta fractions below "
              "about 900 C. No Fe or O in this database.")
TI64 = {"Ti": 90.0, "Al": 6.0, "V": 4.0}
TOL_K = 10.0


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _entry():
    return next(e for e in cs.OPEN_TDB_CATALOG if e["id"] == "mc_ti")


class TestFileAndLicence(unittest.TestCase):
    def test_file_is_pinned_with_origin_and_licence_header(self):
        path = os.path.join(DB_DIR, FILE)
        self.assertEqual(os.path.getsize(path), SIZE)
        self.assertEqual(_sha(path), SHA)
        with open(path, encoding="utf-8", errors="replace") as fh:
            head = fh.read(4000)
        for needle in ("SYNTACTICALLY REPAIRED COPY", "special-databases", "odbl/1.0", "dbcl/1.0",
                       "ODbL share-alike applies", f"mc_ti_v203.tdb (sha256 {ORIGINAL_SHA})"):
            self.assertIn(needle, head)

    def test_repair_report_names_the_pinned_original(self):
        with open(os.path.join(DB_DIR, "mc_ti_v203_repair_report.json"), encoding="utf-8") as fh:
            rep = json.load(fh)
        self.assertEqual(rep["sourceSha256"], ORIGINAL_SHA)
        self.assertEqual(rep["output"], FILE)
        self.assertEqual(rep["parametersRetained"], 508)
        self.assertEqual(rep["ruleCounts"].get("function-ref-join"), 22)
        self.assertEqual(rep["droppedMatcalcParameterTypes"], ["HMVA"])

    def test_licence_file_has_an_mc_ti_section(self):
        with open(os.path.join(DB_DIR, "MATCALC_OPEN_DATABASES_LICENSE.md"), encoding="utf-8") as fh:
            text = fh.read()
        for needle in ("## mc_ti", "Open Database License (ODbL) v1.0", "Database Contents License (DbCL) v1.0",
                       "Erwin Povoden-Karadeniz", "https://www.matcalc.at/index.php/databases/special-databases",
                       "https://www.matcalc.at/images/stories/Download/Database/mc_ti_v203.tdb",
                       ORIGINAL_SHA, SHA, "share-alike"):
            self.assertIn(needle, text)


class TestCatalogue(unittest.TestCase):
    def test_entry_is_an_assessment_scoped_to_ti_with_the_scope_flag(self):
        e = _entry()
        self.assertEqual(e["fileName"], FILE)
        self.assertEqual(e["status"], "assessment")
        self.assertIs(e["usable"], True)
        self.assertEqual(e["assessedBaseElements"], ["TI"])
        self.assertEqual(e["scopeFlag"], SCOPE_FLAG)
        self.assertIn(ORIGINAL_SHA, e["source"])
        self.assertEqual(set(e["elements"]), cs.tdb_file_elements(os.path.join(DB_DIR, FILE)))
        self.assertNotIn("FE", e["elements"])
        self.assertNotIn("O", e["elements"])

    def test_chosen_by_id_only_and_never_substituted_automatically(self):
        auto = cs.resolve_database(["TI", "AL", "V"], None, None, "TI")
        self.assertTrue(auto["ok"])
        self.assertNotEqual(auto["id"], "mc_ti")
        explicit = cs.resolve_database(["TI", "AL", "V"], "mc_ti", None, "TI")
        self.assertTrue(explicit["ok"])
        self.assertEqual(explicit["id"], "mc_ti")

    def test_fe_and_o_are_refused_not_dropped(self):
        res = cs.resolve_database(["TI", "AL", "V", "FE", "O"], "mc_ti", None, "TI")
        self.assertFalse(res["ok"])
        self.assertEqual(res["kind"], cs.KIND_ELEMENTS_MISSING)
        self.assertEqual(sorted(res["extra"]["missingElements"]), ["FE", "O"])

    def test_not_assessed_for_other_base_metals(self):
        res = cs.resolve_database(["NI", "AL"], "mc_ti", None, "NI")
        self.assertFalse(res["ok"])
        self.assertEqual(res["kind"], cs.KIND_NOT_ASSESSED)


@unittest.skipUnless(calphad_test_lane.RUN_REAL_SOLVES, calphad_test_lane.SKIP_REASON)
class TestTi64CriticalTemperatures(unittest.TestCase):
    """Coarse scan (50 K) for liquidus/solidus and a bracket, then a 1 K local scan for the beta transus."""

    @classmethod
    def setUpClass(cls):
        cls.coarse = cs.compute_multi_component_equilibrium(
            "Ti-6Al-4V", TI64, t_min_c=800.0, t_max_c=1750.0, t_step_c=50.0, database_id="mc_ti", scheil=False)

    def test_coarse_scan_is_a_converged_mc_ti_result_with_the_scope_flag(self):
        r = self.coarse
        self.assertTrue(r.get("success"), r.get("reason"))
        self.assertEqual(r["databaseId"], "mc_ti")
        self.assertEqual(r["databaseScopeFlag"], SCOPE_FLAG)
        self.assertEqual(r.get("nonConvergedPoints"), [])
        self.assertEqual(r["compositionOutsideTestedLimits"], [])

    def test_liquidus_and_solidus_within_10_k(self):
        crit = self.coarse["criticalTemperatures"]
        self.assertAlmostEqual(float(crit["liquidusC"]), 1648.0, delta=TOL_K)
        self.assertAlmostEqual(float(crit["solidusC"]), 1578.0, delta=TOL_K)

    def test_beta_transus_within_10_k(self):
        top_hcp = max(p["temperatureC"] for p in self.coarse["equilibriumProfile"]
                      if any(ph["phaseId"] == "HCP_A3" and ph["fraction"] > 0.0 for ph in p["phases"]))
        local = cs.compute_multi_component_equilibrium(
            "Ti-6Al-4V", TI64, t_min_c=float(top_hcp), t_max_c=float(top_hcp) + 60.0, t_step_c=1.0,
            database_id="mc_ti", scheil=False, boundary_refinement=False)
        self.assertTrue(local.get("success"), local.get("reason"))
        no_hcp = [p["temperatureC"] for p in local["equilibriumProfile"]
                  if not any(ph["phaseId"] == "HCP_A3" and ph["fraction"] > 0.0 for ph in p["phases"])]
        self.assertTrue(no_hcp, "no single-phase BCC point in the local scan")
        self.assertAlmostEqual(float(min(no_hcp)), 996.0, delta=TOL_K)


if __name__ == "__main__":
    unittest.main()
