"""CALPHAD speed and solidification post-processing (calphad-use lane).

Pins:
  (a) calphad_model_cache: bounded LRU caches, hit/miss accounting, invalidation when a database
      file's content changes (hash, not modification time), the disabled mode;
  (b) a warm (cached) pycalphad result is exactly the cold result, for the same and for another
      composition of the same system, and the result says which one it was (modelCache.status);
  (c) scheil_gulliver against the analytic Scheil equation of an ideal binary (constant k, linear
      liquidus) and its stop rules (eutectic, non-convergence, limits), with mass balance;
  (d) the real Scheil path for Al-7Si (COST 507) against the Al-Si eutectic of Murray and
      McAlister (1984), the classical Scheil equation and the equilibrium solidus;
  (e) system coverage: alloys without an assessed database are reported unavailable with a reason;
  (f) the IPC service runs calphad requests in one dedicated worker (affinity pool).

(a), (c), (e) and the IPC routing run on the locked interpreter (no pycalphad); (b), (d) and the
worker identity need pycalphad and are skipped with a reason without it.
"""

import json
import math
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import calphad_model_cache as cmc  # noqa: E402
import calphad_solver as cs  # noqa: E402

NEEDS_PYCALPHAD = unittest.skipUnless(
    cs.PYCALPHAD_AVAILABLE,
    "pycalphad is not installed in this interpreter (the locked CI environment); the real path runs with "
    "the server interpreter (METALLIX_PYTHON) or .runtime/scientific-win-py312-cu128")

VOLATILE_KEYS = {"computeTimeMs", "timingsMs", "modelCache", "provenance"}


def _stable(result):
    """A result without the keys that legitimately differ between a cold and a warm run."""
    out = {k: v for k, v in result.items() if k not in VOLATILE_KEYS}
    block = dict(out.get("scheilSolidification") or {})
    block.pop("elapsedMs", None)
    out["scheilSolidification"] = block
    return out


class TestCacheMechanics(unittest.TestCase):
    def test_database_cache_hits_by_content_and_is_bounded(self):
        cache = cmc.CalphadModelCache(max_workspaces=2, max_databases=2)
        parsed = []

        def parse(text):
            parsed.append(text)
            return ("db", text)

        a, info = cache.database("A", parse)
        self.assertEqual((info["status"], a), ("miss", ("db", "A")))
        a2, info = cache.database("A", parse)
        self.assertEqual(info["status"], "hit")
        self.assertIs(a2, a)
        cache.database("B", parse)
        cache.database("C", parse)  # evicts A (least recently used)
        self.assertEqual(cache.stats()["databaseEntries"], 2)
        _, info = cache.database("A", parse)
        self.assertEqual(info["status"], "miss")
        self.assertEqual(parsed, ["A", "B", "C", "A"])
        self.assertGreaterEqual(cache.stats()["evictions"], 2)

    def test_workspace_cache_lru_bound_and_counters(self):
        cache = cmc.CalphadModelCache(max_workspaces=2, max_databases=2)
        builds = []

        def build(tag):
            return lambda: builds.append(tag) or {"ws": tag}

        k1, k2, k3 = ("v", "sha1", ("A", "B")), ("v", "sha1", ("A", "C")), ("v", "sha2", ("A", "B"))
        w1, lock1, info = cache.workspace(k1, build(1))
        self.assertEqual(info["status"], "miss")
        w1b, lock1b, info = cache.workspace(k1, build(99))
        self.assertEqual(info["status"], "hit")
        self.assertIs(w1b, w1)
        self.assertIs(lock1b, lock1)
        cache.workspace(k2, build(2))
        cache.workspace(k1, build(98))       # k1 becomes most recent
        cache.workspace(k3, build(3))        # evicts k2
        _, _, info = cache.workspace(k2, build(4))
        self.assertEqual(info["status"], "miss")
        self.assertEqual(builds, [1, 2, 3, 4])
        st = cache.stats()
        self.assertEqual(st["workspaceEntries"], 2)
        self.assertEqual((st["workspaceHits"], st["workspaceMisses"]), (2, 4))
        self.assertEqual(st["scope"], "process")

    def test_changed_file_content_invalidates_everything_built_from_it(self):
        cache = cmc.CalphadModelCache(max_workspaces=4, max_databases=4)
        tmp = tempfile.mkdtemp(prefix="calphad-use-cache-")
        self.addCleanup(shutil.rmtree, tmp, True)
        path = os.path.join(tmp, "x.tdb")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("ELEMENT AL FCC_A1 26.98 0 0 !\n")
        stamp = os.stat(path).st_mtime
        text = cmc.read_tdb_text(path)
        _, info = cache.database(text, lambda t: t, path=path)
        sha_old = info["sha256"]
        cache.workspace(("v", sha_old, ("AL", "NI")), lambda: "old-ws")
        # same modification time, different content: must not be served from the old parse
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("ELEMENT NI FCC_A1 58.69 0 0 !\n")
        os.utime(path, (stamp, stamp))
        text = cmc.read_tdb_text(path)
        db, info = cache.database(text, lambda t: t, path=path)
        self.assertEqual(info["status"], "miss")
        self.assertNotEqual(info["sha256"], sha_old)
        self.assertIn("NI", db)
        self.assertEqual(cache.stats()["invalidations"], 1)
        _, _, winfo = cache.workspace(("v", sha_old, ("AL", "NI")), lambda: "rebuilt")
        self.assertEqual(winfo["status"], "miss")  # the workspace of the old content is gone

    def test_disabled_cache_builds_every_time_and_says_so(self):
        cache = cmc.CalphadModelCache(max_workspaces=0, max_databases=0)
        n = []
        for _ in range(2):
            _, _, info = cache.workspace(("v", "s", ()), lambda: n.append(1) or "w")
            self.assertEqual(info["status"], "disabled")
        self.assertEqual(len(n), 2)
        self.assertEqual(cache.stats()["workspaceEntries"], 0)

    def test_bounds_from_the_environment_are_clamped(self):
        with mock.patch.dict(os.environ, {cmc.ENV_MAX_WORKSPACES: "1000", cmc.ENV_MAX_DATABASES: "x"}):
            cache = cmc.CalphadModelCache()
        self.assertEqual(cache.max_workspaces, 64)
        self.assertEqual(cache.max_databases, cmc.DEFAULT_MAX_DATABASES)


def _ideal_binary(k=0.2, t_melt=660.0, slope=-600.0, c_eutectic=None, t_eutectic=None, fail_below=None):
    """Equilibrium of a binary with a straight liquidus T = Tm + m*C_L and constant k = C_S/C_L
    (mole fraction of B). Below t_eutectic everything is solid. Returns run_point for scheil_gulliver."""
    def run_point(t_c, x):
        if fail_below is not None and t_c < fail_below:
            return None
        xb = x["B"]
        if t_eutectic is not None and t_c < t_eutectic:
            return {"liquid": 0.0, "liquidX": {}, "phases": {"ALPHA": 1.0 - xb, "BETA": xb}}
        c_l = (t_c - t_melt) / slope  # liquid composition on the liquidus at t_c (slope < 0)
        if xb >= c_l:  # above this composition's liquidus: all liquid
            return {"liquid": 1.0, "liquidX": {"A": 1.0 - xb, "B": xb}, "phases": {}}
        c_s = k * c_l
        if xb <= c_s:  # below its solidus: all solid
            return {"liquid": 0.0, "liquidX": {}, "phases": {"ALPHA": 1.0}}
        f_l = (xb - c_s) / (c_l - c_s)
        return {"liquid": f_l, "liquidX": {"A": 1.0 - c_l, "B": c_l}, "phases": {"ALPHA": 1.0 - f_l},
                "phasesX": {"ALPHA": {"A": 1.0 - c_s, "B": c_s}}}
    return run_point


class TestScheilAlgorithm(unittest.TestCase):
    """Oracle: for constant k and a straight liquidus the Scheil equation is exact,
    C_L = C0 (1 - fs)^(k - 1), and T = Tm + m C_L."""

    def test_matches_the_analytic_scheil_equation(self):
        k, tm, m, c0 = 0.2, 660.0, -600.0, 0.05
        t_liq = tm + m * c0
        out = cs.scheil_gulliver(_ideal_binary(k, tm, m), t_liq, {"A": 1 - c0, "B": c0},
                                 step_c=0.25, max_steps=200, min_temperature_c=t_liq - 40.0)
        self.assertGreater(len(out["points"]), 50)
        worst = 0.0
        for p in out["points"][1:]:
            c_l = (p["temperatureC"] - tm) / m
            fs_exact = 1.0 - (c_l / c0) ** (1.0 / (k - 1.0))
            worst = max(worst, abs(p["fractionSolid"] - fs_exact))
        # first-order discretisation error of the stepwise algorithm at a 0.25 K step
        self.assertLess(worst, 5e-3)
        self.assertLess(out["massBalanceMaxAbsError"], 1e-12)
        self.assertEqual(out["status"], "incomplete")  # no eutectic and the floor was reached
        self.assertEqual(out["terminationReason"], "temperature-floor")
        fa = out["firstAppearance"]["ALPHA"]
        self.assertAlmostEqual(fa["phaseX"]["B"] / fa["liquidX"]["B"], k, places=9)

    def test_error_shrinks_with_the_step(self):
        k, tm, m, c0 = 0.2, 660.0, -600.0, 0.05
        t_liq = tm + m * c0

        def err(step):
            out = cs.scheil_gulliver(_ideal_binary(k, tm, m), t_liq, {"A": 1 - c0, "B": c0},
                                     step_c=step, max_steps=2000, min_temperature_c=t_liq - 20.0)
            p = out["points"][-1]
            c_l = (p["temperatureC"] - tm) / m
            return abs(p["fractionSolid"] - (1.0 - (c_l / c0) ** (1.0 / (k - 1.0))))

        self.assertLess(err(0.25), err(2.0))

    def test_eutectic_ends_the_path_inside_one_step_and_balances_mass(self):
        k, tm, m, c0, te = 0.2, 660.0, -600.0, 0.05, 620.0
        t_liq = tm + m * c0
        out = cs.scheil_gulliver(_ideal_binary(k, tm, m, t_eutectic=te), t_liq, {"A": 1 - c0, "B": c0},
                                 step_c=1.0, max_steps=500)
        self.assertEqual(out["status"], "complete")
        self.assertEqual(out["terminationReason"], "liquid-exhausted-within-step")
        lo, hi = out["terminalBracketC"]
        self.assertTrue(lo <= te <= hi and hi - lo == 1.0)
        self.assertEqual(out["points"][-1]["fractionSolid"], 1.0)
        self.assertEqual(out["remainingLiquidFraction"], 0.0)
        self.assertLess(out["massBalanceMaxAbsError"], 1e-12)
        # the liquid that reached the eutectic is the Scheil fraction at T just above it
        before = out["points"][-2]
        c_l = (before["temperatureC"] - tm) / m
        self.assertAlmostEqual(1.0 - before["fractionSolid"], (c_l / c0) ** (1.0 / (k - 1.0)), delta=0.01)

    def test_a_point_that_does_not_converge_stops_the_path_without_extrapolation(self):
        k, tm, m, c0 = 0.2, 660.0, -600.0, 0.05
        t_liq = tm + m * c0
        out = cs.scheil_gulliver(_ideal_binary(k, tm, m, fail_below=620.0), t_liq, {"A": 1 - c0, "B": c0},
                                 step_c=1.0)
        self.assertEqual(out["status"], "incomplete")
        self.assertEqual(out["terminationReason"], "equilibrium-not-converged")
        self.assertGreaterEqual(out["points"][-1]["temperatureC"], 620.0)
        self.assertGreater(out["remainingLiquidFraction"], 0.0)

    def test_step_and_time_limits_are_reported(self):
        k, tm, m, c0 = 0.2, 660.0, -600.0, 0.05
        out = cs.scheil_gulliver(_ideal_binary(k, tm, m), tm + m * c0, {"A": 1 - c0, "B": c0},
                                 step_c=0.5, max_steps=3)
        self.assertEqual((out["status"], out["terminationReason"], out["steps"]), ("incomplete", "step-limit", 3))
        out = cs.scheil_gulliver(_ideal_binary(k, tm, m), tm + m * c0, {"A": 1 - c0, "B": c0},
                                 step_c=0.5, time_budget_s=-1.0)
        self.assertEqual(out["terminationReason"], "time-budget")

    def test_outputs_without_a_path_are_unavailable_not_invented(self):
        points, block, rows = cs._scheil_outputs(None, "the liquidus is not available", {"Al": 93, "Si": 7},
                                                 "db", ["AL", "SI"])
        self.assertEqual(points, [])
        self.assertEqual(block["status"], "unavailable")
        self.assertEqual(block["evidence"], "unvalidated")
        self.assertIn("liquidus", block["reason"])
        for row in rows:
            self.assertIsNone(row["partitionCoefficient_k"])
            self.assertEqual(row["partitionCoefficientSource"], "unavailable")


class TestSystemCoverage(unittest.TestCase):
    def test_reference_alloys_without_a_database_say_so(self):
        cov = {row["id"]: row for row in cs.system_coverage()}
        for sys_id in ("in718", "in625", "ss316l"):
            self.assertEqual(cov[sys_id]["status"], "unavailable", sys_id)
            self.assertTrue(cov[sys_id]["reason"].startswith("no thermodynamic database for this system"))
        self.assertEqual(cov["in718"]["unavailableKind"], "no-database-covers-elements")
        self.assertEqual(cov["ss316l"]["unavailableKind"], "database-not-assessed-for-base")
        self.assertEqual(cov["ti6al4v"]["databaseId"], "cost507")
        self.assertIn("995", cov["ti6al4v"]["knownDeviation"])
        self.assertEqual(cov["alsi10mg"]["databaseId"], "cost507")
        self.assertEqual(cov["ni_al"]["databaseId"], "alni_dupin_2001")
        for row in cov.values():
            if row["status"] == "covered":
                self.assertIn("not established", row["note"])

    def test_database_listing_carries_coverage_and_cache_state(self):
        listing = cs.list_available_databases()
        self.assertEqual(len(listing["systemCoverage"]), len(cs.COVERAGE_REFERENCE_SYSTEMS))
        self.assertEqual(listing["modelCache"]["scope"], "process")
        json.dumps(listing, allow_nan=False)


@NEEDS_PYCALPHAD
class TestWarmEqualsCold(unittest.TestCase):
    def setUp(self):
        cmc.reset_process_cache()
        self.addCleanup(cmc.reset_process_cache)

    def run_ni_al(self, al_at_pct=10.0):
        return cs.compute_multi_component_equilibrium(
            "Ni-Al", {"Ni": 100.0 - al_at_pct, "Al": al_at_pct}, unit="at_pct",
            t_min_c=1300.0, t_max_c=1500.0, t_step_c=20.0)

    def test_warm_result_is_identical_to_cold_and_labelled(self):
        cold = self.run_ni_al()
        warm = self.run_ni_al()
        self.assertIs(cold["success"], True)
        self.assertEqual(cold["modelCache"]["status"], "cold")
        self.assertEqual(warm["modelCache"]["status"], "warm")
        self.assertEqual(warm["modelCache"]["workspaceBuildMs"], 0.0)
        self.assertEqual(_stable(cold), _stable(warm))  # exact equality, floats included
        self.assertEqual(warm["modelCache"]["processId"], os.getpid())
        for key in ("databaseLoad", "workspaceBuild", "gridEquilibrium", "boundaryRefinement", "scheil", "total"):
            self.assertIn(key, warm["timingsMs"])

    def test_another_composition_of_the_same_system_is_warm_and_equals_its_cold_run(self):
        self.run_ni_al(10.0)
        warm_other = self.run_ni_al(12.0)
        self.assertEqual(warm_other["modelCache"]["status"], "warm")
        cmc.reset_process_cache()
        cold_other = self.run_ni_al(12.0)
        self.assertEqual(cold_other["modelCache"]["status"], "cold")
        self.assertEqual(_stable(cold_other), _stable(warm_other))

    def test_disabled_cache_gives_the_same_numbers(self):
        cached = self.run_ni_al()
        cmc.reset_process_cache(max_workspaces=0, max_databases=0)
        uncached = self.run_ni_al()
        self.assertEqual(uncached["modelCache"]["status"], "cold")
        self.assertEqual(uncached["modelCache"]["workspace"], "disabled")
        self.assertEqual(_stable(cached), _stable(uncached))

    def test_edited_custom_database_text_is_never_served_from_the_old_parse(self):
        with open(os.path.join(cs.DATABASES_DIR, "alni_dupin_2001.tdb"), encoding="utf-8") as fh:
            text = fh.read()
        args = dict(name="t", elements={"Ni": 90.0, "Al": 10.0}, unit="at_pct", t_min_c=1300.0, t_max_c=1500.0,
                    t_step_c=20.0, scheil=False)
        first = cs.compute_multi_component_equilibrium(custom_tdb_text=text, **args)
        self.assertEqual(first["modelCache"]["database"], "miss")
        again = cs.compute_multi_component_equilibrium(custom_tdb_text=text, **args)
        self.assertEqual((again["modelCache"]["database"], again["modelCache"]["status"]), ("hit", "warm"))
        edited = text + "\n$ edited copy\n"
        changed = cs.compute_multi_component_equilibrium(custom_tdb_text=edited, **args)
        self.assertEqual((changed["modelCache"]["database"], changed["modelCache"]["status"]), ("miss", "cold"))
        self.assertNotEqual(changed["modelCache"]["databaseSha256"], first["modelCache"]["databaseSha256"])


@NEEDS_PYCALPHAD
class TestAlSiScheilOracle(unittest.TestCase):
    """Al-7 wt% Si on COST 507. Murray and McAlister, Bull. Alloy Phase Diagrams 5 (1984) 74:
    Al-Si eutectic at 577 degC and 12.6 wt% Si. A Scheil path of a hypoeutectic Al-Si alloy ends at
    the eutectic, and its eutectic fraction follows the classical Scheil equation."""

    @classmethod
    def setUpClass(cls):
        cls.out = cs.compute_multi_component_equilibrium(
            "Al-7Si", {"Al": 93.0, "Si": 7.0}, t_min_c=500.0, t_max_c=700.0, t_step_c=5.0, scheil_step_c=0.5)

    def test_path_ends_at_the_eutectic(self):
        out = self.out
        self.assertIs(out["success"], True)
        self.assertEqual(out["databaseId"], "cost507")
        block = out["scheilSolidification"]
        self.assertEqual(block["status"], "pycalphad-scheil-gulliver")
        self.assertEqual(block["terminationReason"], "liquid-exhausted-within-step")
        self.assertEqual(block["evidence"], "unvalidated")
        lo, hi = block["terminalBracketC"]
        self.assertLessEqual(hi - lo, 0.5 + 1e-9)
        # the equilibrium solidus of a hypoeutectic binary beyond the solubility limit is the eutectic
        solidus = out["criticalTemperatures"]["solidusC"]
        self.assertTrue(lo - 0.5 <= solidus <= hi + 0.5, (lo, hi, solidus))
        self.assertAlmostEqual((lo + hi) / 2.0, 577.0, delta=1.5)
        self.assertLess(block["massBalanceMaxAbsError"], 1e-9)
        self.assertEqual(set(block["phaseAmounts"]), {"FCC_A1", "DIAMOND_A4"})

    def test_last_liquid_is_eutectic_and_fraction_follows_the_scheil_equation(self):
        out = self.out
        pts = [p for p in out["multiElementScheil"] if p["liquidCompositions"]]
        last = pts[-1]
        self.assertAlmostEqual(last["liquidCompositions"]["Si"], 12.6, delta=0.5)
        k = {r["element"]: r["partitionCoefficient_k"] for r in out["solutePartitioning"]}["SI"]
        x0 = out["atomicFractions"]["Si"]
        # liquid mole fraction of Si at the last step, from its wt% (CIAAW weights)
        w = last["liquidCompositions"]
        n_si = w["Si"] / cs._atomic_weight("Si")
        x_e = n_si / (n_si + w["Al"] / cs._atomic_weight("Al"))
        f_l_equation = (x_e / x0) ** (1.0 / (k - 1.0))
        self.assertAlmostEqual(1.0 - last["fractionSolid"], f_l_equation, delta=0.03)
        self.assertAlmostEqual(k, 0.11, delta=0.03)  # k(Si in Al) about 0.1 to 0.13 in the literature

    def test_liquidus_and_scheil_start(self):
        out = self.out
        self.assertAlmostEqual(out["criticalTemperatures"]["liquidusC"], 614.0, delta=4.0)
        self.assertGreaterEqual(out["scheilSolidification"]["startTemperatureC"],
                                out["criticalTemperatures"]["liquidusC"])
        json.dumps(out, allow_nan=False)


class TestIpcAffinityRouting(unittest.TestCase):
    """calphad_solver runs in a dedicated single-worker pool so its model cache is reused."""

    def test_calphad_requests_go_to_the_affinity_pool_and_other_scripts_do_not(self):
        import persistent_ipc_service as ipc
        self.assertIn("calphad_solver", ipc.AFFINITY_SCRIPT_NAMES)
        reg = ipc.ConcurrentModuleRegistry.__new__(ipc.ConcurrentModuleRegistry)
        reg.script_dir = ipc.SCRIPT_DIR
        self.assertEqual(reg._affinity_name(os.path.join(ipc.SCRIPT_DIR, "calphad_solver.py")), "calphad_solver")
        self.assertIsNone(reg._affinity_name(os.path.join(ipc.SCRIPT_DIR, "pourbaix_solver.py")))

    def test_two_calphad_requests_share_one_worker(self):
        import persistent_ipc_service as ipc
        reg = ipc.ConcurrentModuleRegistry(ipc.SCRIPT_DIR, num_workers=1)
        self.addCleanup(reg.shutdown)
        payload = {"name": "Ni-Al", "elements": {"Ni": 90.0, "Al": 10.0}, "unit": "at_pct",
                   "tMin": 1300.0, "tMax": 1500.0, "tStep": 20.0}
        runs = [reg.execute_script("python/calphad_solver.py", payload, [], 120000) for _ in range(2)]
        for r in runs:
            self.assertEqual(r["exitCode"], 0, r["stderr"][-800:])
            self.assertEqual(r["concurrency"], "affinity_pool:calphad_solver")
        self.assertEqual(reg.get_status()["affinityPools"], ["calphad_solver"])
        outs = [json.loads(r["stdout"]) for r in runs]
        if cs.PYCALPHAD_AVAILABLE:
            self.assertEqual([o["modelCache"]["status"] for o in outs], ["cold", "warm"])
            self.assertEqual(outs[0]["modelCache"]["processId"], outs[1]["modelCache"]["processId"])
            self.assertNotEqual(outs[0]["modelCache"]["processId"], os.getpid())
        else:
            self.assertEqual(outs[0]["unavailableKind"], "pycalphad-not-installed")

    def test_timeout_recycles_only_the_affinity_worker_when_it_is_alone(self):
        import persistent_ipc_service as ipc
        reg = ipc.ConcurrentModuleRegistry.__new__(ipc.ConcurrentModuleRegistry)
        import threading
        reg.stats_lock = threading.Lock()
        reg.affinity_active = {"calphad_solver": 1}
        reg._affinity_pool = mock.Mock()
        reg._terminate_workers = mock.Mock()
        running = mock.Mock()
        running.cancel.return_value = False
        self.assertEqual(reg._abandon_affinity("calphad_solver", running),
                         "worker terminated and affinity pool recycled")
        reg._affinity_pool.assert_called_once_with("calphad_solver", recycle=True)
        reg._terminate_workers.assert_not_called()  # the shared pool is untouched
        reg.affinity_active = {"calphad_solver": 2}
        reg._affinity_pool.reset_mock()
        self.assertIn("other job(s) share", reg._abandon_affinity("calphad_solver", running))
        reg._affinity_pool.assert_not_called()


if __name__ == "__main__":
    unittest.main()
