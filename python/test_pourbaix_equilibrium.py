"""Pourbaix engine: minimum-Gibbs-energy equilibrium (25 C), SPEC-pourbaix-opus.md section 3.

Run from python/:  python -B -m unittest test_pourbaix_equilibrium

Tolerances (spec): line intercepts +/-1 mV, slopes +/-0.0005 V/pH, vertical lines and
triple-point pH +/-0.01, triple-point E +/-2 mV. Every grid point used for a classification
check is at least 1 mV from a boundary (an exact tie would be broken by table order).
"""

import json
import math
import os
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "tools"))

import pourbaix_oracle as oracle  # noqa: E402
import pourbaix_solver as solver  # noqa: E402
import pourbaix_species_25c as table  # noqa: E402

K = 0.0591597  # ln10 RT/F at 298.15 K (V)
INTERCEPT, SLOPE, VERTICAL, TRIPLE_E = 0.001, 0.0005, 0.01, 0.002
ELEMENTS = ("Fe", "Ni", "Cu", "Zn", "Mg", "Al")  # the v4 elements; Cr, Mo, Ti: test_pourbaix_ticrmo
ALL_ELEMENTS = ELEMENTS + ("Cr", "Mo", "Ti")
KJ_PER_LOG_K = 0.0591597 * 96.48533212  # ln10 RT at 298.15 K in kJ/mol (5.708)


def _run_cli(payload):
    proc = subprocess.run([sys.executable, "-B", str(HERE / "pourbaix_solver.py")],
                          input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8")
    return proc.returncode, json.loads(proc.stdout)


def _sloped(testcase, element, a, b, e0, slope, log_a=-6.0):
    line = solver.boundary_line(element, a, b, log_a)
    testcase.assertEqual(line["type"], "sloped", (element, a, b))
    testcase.assertAlmostEqual(line["E_V_SHE_at_pH0"], e0, delta=INTERCEPT, msg=f"{element} {a}/{b} intercept")
    testcase.assertAlmostEqual(line["slope_V_per_pH"], slope, delta=SLOPE, msg=f"{element} {a}/{b} slope")


def _vertical(testcase, element, a, b, ph, log_a=-6.0):
    line = solver.boundary_line(element, a, b, log_a)
    testcase.assertEqual(line["type"], "vertical", (element, a, b))
    testcase.assertAlmostEqual(line["pH"], ph, delta=VERTICAL, msg=f"{element} {a}/{b} pH")


def _grid(ph_lo=-2.0, ph_hi=16.0, ph_step=0.25, e_lo=-3.0, e_hi=2.5, e_step=0.0173):
    ph = ph_lo
    while ph <= ph_hi + 1e-9:
        e = e_lo
        while e <= e_hi + 1e-9:
            yield ph, e
            e += e_step
        ph += ph_step


class FeSpecNumbersTest(unittest.TestCase):
    def test_fe_lines_at_1e_minus_6(self):
        _sloped(self, "Fe", "Fe", "Fe2+", -0.6176, 0.0)
        _sloped(self, "Fe", "Fe2+", "Fe3+", 0.7706, 0.0)
        _vertical(self, "Fe", "Fe3+", "Fe2O3", 1.759)
        _sloped(self, "Fe", "Fe2+", "Fe2O3", 1.0828, -0.1775)
        _sloped(self, "Fe", "Fe2+", "Fe3O4", 1.5138, -0.2366)
        _sloped(self, "Fe", "Fe3O4", "Fe2O3", 0.2209, -0.0592)
        _sloped(self, "Fe", "Fe", "Fe3O4", -0.0848, -0.0592)
        _sloped(self, "Fe", "Fe3O4", "HFeO2-", -1.2867, 0.0296)
        _sloped(self, "Fe", "Fe", "HFeO2-", 0.3159, -0.0887)
        _sloped(self, "Fe", "Fe2O3", "FeO4^2-", 2.0959, -0.0986)

    def test_fe_activity_dependence_is_per_couple_type(self):
        # a = 1: solid/aqueous couple moves by (k/n) log a, aqueous/aqueous does not.
        _sloped(self, "Fe", "Fe", "Fe2+", -0.4401, 0.0, log_a=0.0)
        _sloped(self, "Fe", "Fe2+", "Fe2O3", 0.7279, -0.1775, log_a=0.0)
        # Fe2+/Fe3+ is 0.7706 V at every activity (the activity terms cancel)
        for log_a in (-8.0, -6.0, -3.0, 0.0):
            _sloped(self, "Fe", "Fe2+", "Fe3+", 0.7706, 0.0, log_a=log_a)
        # solid/aqueous shift is (k/Delta n) log a per metal atom
        d = (solver.boundary_line("Fe", "Fe", "Fe2+", -6.0)["E_V_SHE_at_pH0"]
             - solver.boundary_line("Fe", "Fe", "Fe2+", 0.0)["E_V_SHE_at_pH0"])
        self.assertAlmostEqual(d, K / 2 * -6.0, delta=1e-4)

    def test_fe_triple_points_and_ranges(self):
        result = solver.solve_pourbaix_diagram("Fe", 25.0, -6.0, 0.0, [])
        ends = {}
        for b in result["analyticalBoundaries"]:
            ends[b["id"]] = [(p["pH"], p["E_V_SHE"]) for p in b["points"]]

        def has_point(boundary_id, ph, e):
            return any(abs(p - ph) <= VERTICAL and abs(v - e) <= TRIPLE_E for p, v in ends[boundary_id])
        for ident in ("Fe__Fe2+", "Fe2+__Fe3+", "Fe3+__Fe2O3", "Fe2+__Fe2O3", "Fe2+__Fe3O4", "Fe3O4__Fe2O3",
                      "Fe__Fe3O4", "Fe3O4__HFeO2-", "Fe__HFeO2-", "Fe2O3__FeO4^2-"):
            self.assertIn(ident, ends)
        for ident, ph, e in (("Fe2+__Fe3+", 1.759, 0.7706), ("Fe3+__Fe2O3", 1.759, 0.7706),
                             ("Fe2+__Fe2O3", 1.759, 0.7706), ("Fe2+__Fe2O3", 7.29, -0.210),
                             ("Fe2+__Fe3O4", 7.29, -0.210), ("Fe3O4__Fe2O3", 7.29, -0.210),
                             ("Fe__Fe2+", 9.01, -0.618), ("Fe2+__Fe3O4", 9.01, -0.618),
                             ("Fe__Fe3O4", 9.01, -0.618), ("Fe__Fe3O4", 13.54, -0.886),
                             ("Fe3O4__HFeO2-", 13.54, -0.886), ("Fe__HFeO2-", 13.54, -0.886)):
            self.assertTrue(has_point(ident, ph, e), (ident, ph, e, ends[ident]))
        # range of Fe/Fe2+ is pH <= 9.01 (the left end is the box edge), Fe2+/Fe3+ pH <= 1.76
        self.assertAlmostEqual(max(p for p, _ in ends["Fe__Fe2+"]), 9.01, delta=VERTICAL)
        self.assertAlmostEqual(max(p for p, _ in ends["Fe2+__Fe3+"]), 1.76, delta=VERTICAL)

    def test_audit_spot_points(self):
        # pH 6 / -0.40 V and pH 8 / -0.55 V are Fe2+ (the old tree said Passivation);
        # pH 3 / +0.60 V is Fe2O3 (the old tree said Active).
        for ph, e, expected in ((6.0, -0.40, "Fe2+"), (8.0, -0.55, "Fe2+"), (3.0, 0.60, "Fe2O3")):
            res = solver.evaluate_point_mechanism("Fe", ph, e)
            self.assertEqual(res["dominantSpeciesId"], expected, (ph, e))
            self.assertEqual(oracle.dominant("Fe", ph, e), expected)
        self.assertEqual(solver.evaluate_point_mechanism("Fe", 6.0, -0.40)["category"], "Corrosion (acid)")
        self.assertEqual(solver.evaluate_point_mechanism("Fe", 3.0, 0.60)["category"],
                         "Passivation (thermodynamic, film-forming)")


class OtherElementPinsTest(unittest.TestCase):
    def test_ni(self):
        # NEA-TDB set E (Gamsjager 2005; S1 of REVIEW-pbx-sci): the atlas pins of the spec (-0.4275, pH 9.088,
        # 12.204, 0.1101) are superseded; the oracle (tools/pourbaix_oracle.py DATA["Ni"]) carries the new numbers.
        _sloped(self, "Ni", "Ni", "Ni2+", -0.4147, 0.0)
        _vertical(self, "Ni", "Ni2+", "Ni(OH)2", 8.514)
        _vertical(self, "Ni", "Ni(OH)2", "HNiO2-", 12.171)
        _sloped(self, "Ni", "Ni", "Ni(OH)2", 0.0890, -0.0592)
        _sloped(self, "Ni", "Ni", "Ni2+", -0.2372, 0.0, log_a=0.0)
        _vertical(self, "Ni", "Ni2+", "Ni(OH)2", 5.514, log_a=0.0)

    def test_cu(self):
        _sloped(self, "Cu", "Cu", "Cu2+", 0.1619, 0.0)
        _vertical(self, "Cu", "Cu2+", "CuO", 6.674)
        _sloped(self, "Cu", "Cu", "Cu2O", 0.4722, -0.0592)
        _sloped(self, "Cu", "Cu2O", "CuO", 0.6412, -0.0592)
        _vertical(self, "Cu", "CuO", "HCuO2-", 12.978)
        _vertical(self, "Cu", "HCuO2-", "CuO2^2-", 13.122)

    def test_zn(self):
        _sloped(self, "Zn", "Zn", "Zn2+", -0.9396, 0.0)
        _vertical(self, "Zn", "Zn2+", "ZnO", 8.772)
        _vertical(self, "Zn", "ZnO", "HZnO2-", 11.228)
        _vertical(self, "Zn", "HZnO2-", "ZnO2^2-", 12.770)

    def test_mg(self):
        _sloped(self, "Mg", "Mg", "Mg2+", -2.5343, 0.0)
        _vertical(self, "Mg", "Mg2+", "Mg(OH)2", 11.370)
        # Mg immunity lies below the old -2.5 V box: the box now reaches -3.0 V
        self.assertEqual(table.BOX["E_min_V_SHE"], -3.0)
        self.assertEqual(solver.evaluate_point_mechanism("Mg", 7.0, -2.8)["dominantSpeciesId"], "Mg")

    def test_withheld_al_rows_reproduce_the_spec_pins(self):
        # The rejected atlas Al rows (AlO2-, hydrargillite; V3) still reproduce the spec's Al pins, so the
        # drift to the adopted set O (AluminiumSetOTest) is measured against the spec's own numbers.
        a = oracle.WITHHELD["Al"]["sp"]
        coeffs = {}
        for name, (x, o, h, z, g, phase, role) in a.items():
            m, n = (2 * o - h) / x, (z + 2 * o - h) / x
            ln_a = 0.0 if phase == "s" else -6.0 * oracle.LN10
            coeffs[name] = ((g * 1000 - o * oracle.WITHHELD["Al"]["H2O"] * 1000 + oracle.R * oracle.T * ln_a) / x,
                            -m * oracle.LN10 * oracle.R * oracle.T, -n * oracle.F)

        def line(p, q):
            d0, dp, de = (coeffs[p][i] - coeffs[q][i] for i in range(3))
            return (-d0 / dp,) if abs(de) < 1e-9 else (-d0 / de, -dp / de)
        self.assertAlmostEqual(line("Al", "Al3+")[0], -1.7806, delta=INTERCEPT)
        self.assertAlmostEqual(line("Al3+", "Al2O3.3H2O")[0], 3.898, delta=VERTICAL)
        self.assertAlmostEqual(line("Al2O3.3H2O", "AlO2-")[0], 8.587, delta=VERTICAL)
        self.assertAlmostEqual(line("Al", "Al2O3.3H2O")[0], -1.5500, delta=INTERCEPT)
        self.assertAlmostEqual(line("Al", "AlO2-")[0], -1.3806, delta=INTERCEPT)
        # the table keeps the same rejected values (V3) under withheldSpecies, never in the engine
        withheld = {r[0]: r for r in table.WITHHELD_SPECIES["Al"]}
        self.assertAlmostEqual(withheld["AlO2-(atlas)"][7], a["AlO2-"][4], delta=1e-9)
        self.assertAlmostEqual(withheld["Al2O3.3H2O(atlas)"][7], a["Al2O3.3H2O"][4], delta=1e-9)
        self.assertEqual((withheld["AlO2-(atlas)"][10], withheld["Al2O3.3H2O(atlas)"][10]), ("V3", "V3"))


class AluminiumSetOTest(unittest.TestCase):
    """Al from ONE set (O: CHNOSZ OBIGT, Tagirov & Schott 2001 + gibbsite Robie et al. 1978, SUPCRT92 water).

    Pins come from the independent oracle (tools/pourbaix_oracle.py DATA["Al"]); the cross-checks use
    published numbers that do not come from that set (PHREEQC llnl.dat / phreeqc.dat, OpenStax/NBS,
    CODATA 1989 key values, the CRC E0 on the Wikipedia data page).
    """

    def test_lines_at_1e_minus_6(self):
        _sloped(self, "Al", "Al", "Al3+", -1.8024, 0.0)
        _vertical(self, "Al", "Al3+", "Al(OH)3", 4.577)
        _vertical(self, "Al", "Al(OH)3", "Al(OH)4-", 9.118)
        _sloped(self, "Al", "Al", "Al(OH)3", -1.5317, -0.0592)
        _sloped(self, "Al", "Al", "Al(OH)4-", -1.3519, -0.0789)

    def test_lines_at_unit_activity(self):
        _sloped(self, "Al", "Al", "Al3+", -1.6841, 0.0, log_a=0.0)
        _vertical(self, "Al", "Al3+", "Al(OH)3", 2.577, log_a=0.0)
        _vertical(self, "Al", "Al(OH)3", "Al(OH)4-", 15.118, log_a=0.0)
        _sloped(self, "Al", "Al", "Al(OH)4-", -1.2335, -0.0789, log_a=0.0)

    def test_triple_points_and_domains(self):
        result = solver.solve_pourbaix_diagram("Al", 25.0, -6.0, 0.0, [])
        ends = {b["id"]: [(p["pH"], p["E_V_SHE"]) for p in b["points"]] for b in result["analyticalBoundaries"]}
        self.assertEqual(set(ends), {"Al__Al3+", "Al__Al(OH)3", "Al__Al(OH)4-", "Al3+__Al(OH)3", "Al(OH)3__Al(OH)4-"})
        for ident, ph, e in (("Al__Al3+", 4.577, -1.8024), ("Al3+__Al(OH)3", 4.577, -1.8024),
                             ("Al__Al(OH)3", 4.577, -1.8024), ("Al__Al(OH)3", 9.118, -2.0711),
                             ("Al(OH)3__Al(OH)4-", 9.118, -2.0711), ("Al__Al(OH)4-", 9.118, -2.0711)):
            self.assertTrue(any(abs(p - ph) <= VERTICAL and abs(v - e) <= TRIPLE_E for p, v in ends[ident]),
                            (ident, ends[ident]))
        # inside the water window at pH 7 the stable phase is gibbsite (passivation), pH 2 Al3+, pH 11 Al(OH)4-
        for ph, e, sid, cat in ((7.0, -0.2, "Al(OH)3", "Passivation (thermodynamic, film-forming)"),
                                (2.0, 0.0, "Al3+", "Corrosion (acid)"), (11.0, -0.3, "Al(OH)4-", "Corrosion (alkaline)"),
                                (7.0, -2.2, "Al", "Immunity")):
            r = solver.evaluate_point_mechanism("Al", ph, e)
            self.assertEqual((r["dominantSpeciesId"], r["category"]), (sid, cat), (ph, e))
            self.assertEqual(oracle.dominant("Al", ph, e), sid)

    def test_unit_activity_e0_against_published_values(self):
        e0 = solver.boundary_line("Al", "Al", "Al3+", 0.0)["E_V_SHE_at_pH0"]
        # NBS (Wagman 1982) Al3+ -485.0 kJ/mol as printed in OpenStax Chemistry 2e App. G: -1.6756 V
        self.assertAlmostEqual(e0, -485.0e3 / (3 * 96485.33212), delta=0.010)
        # CODATA 1989 key values (dfH -538.4 +/- 1.5 kJ/mol, S -325 +/- 10 J/mol/K; Al 28.30, H2 130.680):
        # dfG -491.5 +/- 3.3 kJ/mol, E0 -1.6980 +/- 0.0115 V; the set lies within 1.5 sigma
        dfg_codata = -538.4 + 298.15 * (325 - 1.5 * 130.680 + 28.30) / 1000.0
        self.assertAlmostEqual(dfg_codata, -491.51, delta=0.01)
        self.assertAlmostEqual(e0, dfg_codata * 1e3 / (3 * 96485.33212), delta=1.5 * 0.0115)
        # CRC/Wikipedia -1.662 V is the Latimer/atlas value (-115000 cal): documented 22 mV exception
        self.assertAlmostEqual(e0, -1.662, delta=0.025)
        self.assertGreater(abs(e0 - (-1.662)), 0.010)
        # alkaline Al(OH)4-/Al ("H2AlO3- + H2O + 3e- = Al + 4OH-", CRC on the Wikipedia data page): -2.33 V
        line = solver.boundary_line("Al", "Al", "Al(OH)4-", 0.0)
        self.assertAlmostEqual(line["E_V_SHE_at_pH0"] + 14.0 * line["slope_V_per_pH"], -2.33, delta=0.010)

    def test_reaction_constants_against_open_databases(self):
        # 2.5 kJ/mol = V2 tolerance (0.44 log units). Values read from the PHREEQC databases (USGS).
        rows = {r["id"]: r["dfG_kJ_mol"] for r in table.species_rows("Al")}
        w = table.water_dfg_kj_mol("Al")
        log_ks0 = -(rows["Al3+"] + 3 * w - rows["Al(OH)3"]) / KJ_PER_LOG_K      # gibbsite + 3H+ = Al3+ + 3H2O
        log_b4 = -(rows["Al(OH)4-"] - rows["Al3+"] - 4 * w) / KJ_PER_LOG_K     # Al3+ + 4H2O = Al(OH)4- + 4H+
        self.assertAlmostEqual(log_ks0, 7.730, delta=0.002)
        self.assertAlmostEqual(log_b4, -22.849, delta=0.002)
        tol = 2.5 / KJ_PER_LOG_K
        for published in (7.756, 8.11):          # llnl.dat (thermo.com.V8.R6), phreeqc.dat/wateq4f.dat
            self.assertAlmostEqual(log_ks0, published, delta=tol)
        for published in (-22.8833, -22.7):      # llnl.dat (as AlO2-), phreeqc.dat/wateq4f.dat
            self.assertAlmostEqual(log_b4, published, delta=tol)
        # the boundaries follow from them: pH = (log Ks0 - log a)/3 and pH = -(log Ks0 + log b4) - log a
        # (1e-4: KJ_PER_LOG_K uses the rounded 0.0591597 V)
        self.assertAlmostEqual(solver.boundary_line("Al", "Al3+", "Al(OH)3", -6.0)["pH"], (log_ks0 + 6) / 3, delta=1e-4)
        self.assertAlmostEqual(solver.boundary_line("Al", "Al(OH)3", "Al(OH)4-", -6.0)["pH"],
                               -(log_ks0 + log_b4) - 6, delta=1e-4)
        self.assertAlmostEqual(w, -56687 * 4.184 / 1000, delta=1e-9)

    def _with_extra(self, extra):
        sp = dict(oracle.DATA["Al"]["sp"])
        sp.update(extra)
        return sp

    def _boundaries(self, sp, log_a=-6.0):
        c = oracle.coeffs_of(sp, oracle.DATA["Al"]["H2O"], log_a)

        def line(p, q):
            d0, dp, de = (c[p][i] - c[q][i] for i in range(3))
            return -d0 / dp if abs(de) < 1e-9 else (-d0 / de, -dp / de)
        return line

    def test_excluded_solids_boehmite_and_corundum(self):
        # corundum never wins (8.0 kJ/mol per Al above gibbsite + water); boehmite would replace gibbsite
        # (0.69 kJ/mol lower in this set) and shift the solid boundaries to pH 4.54 / 9.24: same categories.
        corundum = self._with_extra({"Al2O3": oracle.AL_EXCLUDED["Al2O3"]})
        boehmite = self._with_extra({"AlO(OH)": oracle.AL_EXCLUDED["AlO(OH)"]})
        line = self._boundaries(boehmite)
        self.assertAlmostEqual(line("Al3+", "AlO(OH)"), 4.537, delta=VERTICAL)
        self.assertAlmostEqual(line("AlO(OH)", "Al(OH)4-"), 9.239, delta=VERTICAL)
        for ph, e in _grid(ph_step=0.5, e_step=0.05):
            gc = oracle.coeffs_of(corundum, oracle.DATA["Al"]["H2O"])
            g = {k: v[0] + v[1] * ph + v[2] * e for k, v in gc.items()}
            self.assertGreater(g["Al2O3"], g["Al(OH)3"] + 7.9e3)
        table_rows = {r[0]: r for r in table.WITHHELD_SPECIES["Al"]}
        self.assertAlmostEqual(table_rows["AlO(OH)"][7], oracle.AL_EXCLUDED["AlO(OH)"][4], delta=1e-9)
        self.assertAlmostEqual(table_rows["Al2O3"][7], oracle.AL_EXCLUDED["Al2O3"][4], delta=1e-6)
        self.assertAlmostEqual(table_rows["Al2O3"][7], -1582.26, delta=0.01)
        self.assertNotIn("AlO(OH)", {r["id"] for r in table.species_rows("Al")})
        self.assertNotIn("Al2O3", {r["id"] for r in table.species_rows("Al")})

    def test_omitted_hydrolysis_species_have_no_domain_at_default_activities(self):
        # AlOH2+ / Al(OH)2+ (TS01, same set) have no domain for log a >= -7.16; at log a = -8 AlOH2+
        # takes pH 4.96-5.38 (recorded in sourceSetNote).
        sp = self._with_extra(oracle.AL_HYDROLYSIS_OMITTED)
        for log_a in (-7.0, -6.0, -3.0, 0.0):
            c = oracle.coeffs_of(sp, oracle.DATA["Al"]["H2O"], log_a)
            for ph, e in _grid(ph_step=0.05, e_step=0.05):
                g = {k: v[0] + v[1] * ph + v[2] * e for k, v in c.items()}
                self.assertNotIn(min(g, key=g.get), oracle.AL_HYDROLYSIS_OMITTED, (log_a, ph, e))
        line = self._boundaries(sp, -8.0)
        self.assertAlmostEqual(line("Al3+", "AlOH2+"), 4.964, delta=VERTICAL)
        self.assertAlmostEqual(line("AlOH2+", "Al(OH)3"), 5.383, delta=VERTICAL)
        self.assertIn("-7.16", table.ELEMENT_SET["Al"][2])


class NickelSetETest(unittest.TestCase):
    """Ni from ONE set (E: NEA-TDB, Gamsjager et al. 2005) with CODATA water; open-database cross checks."""

    def rows(self):
        return {r["id"]: r["dfG_kJ_mol"] for r in table.species_rows("Ni")}

    def test_set_values_and_water(self):
        g = self.rows()
        self.assertAlmostEqual(table.water_dfg_kj_mol("Ni"), -237.140, delta=1e-9)
        self.assertAlmostEqual(g["Ni2+"], -45.773, delta=1e-9)
        self.assertAlmostEqual(g["Ni(OH)2"], -457.100, delta=1e-9)
        self.assertAlmostEqual(g["HNiO2-"], -590.519 + 237.140, delta=1e-9)  # Ni(OH)3- - H2O
        self.assertEqual({table.ELEMENT_SET["Ni"][0]} | {r["source"] for r in table.species_rows("Ni")[1:]}, {"E"})

    def test_reaction_constants_reproduce_the_nea_selection(self):
        g, w = self.rows(), table.water_dfg_kj_mol("Ni")
        log_ks0 = -(g["Ni2+"] + 2 * w - g["Ni(OH)2"]) / KJ_PER_LOG_K          # Ni(OH)2 + 2H+ = Ni2+ + 2H2O
        log_b3 = -((g["HNiO2-"] + w) - g["Ni2+"] - 3 * w) / KJ_PER_LOG_K     # Ni2+ + 3H2O = Ni(OH)3- + 3H+
        self.assertAlmostEqual(log_ks0, 11.02, delta=0.01)   # NEA / PSI-Nagra TDB 12/07 selection (+/- 0.20)
        self.assertAlmostEqual(log_b3, -29.2, delta=0.01)    # NEA selection (+/- 1.7)

    def test_open_database_cross_checks(self):
        g, w = self.rows(), table.water_dfg_kj_mol("Ni")
        log_ks0 = -(g["Ni2+"] + 2 * w - g["Ni(OH)2"]) / KJ_PER_LOG_K
        combined = -((g["HNiO2-"] + w) - g["Ni(OH)2"] - w) / KJ_PER_LOG_K     # Ni(OH)2 + H2O = Ni(OH)3- + H+
        # CHNOSZ OBIGT (SH88) Ni+2 -10900 cal: V1 (0.5 kJ/mol)
        self.assertAlmostEqual(g["Ni2+"], -10900 * 4.184 / 1000.0, delta=0.5)
        # wateq4f.dat (Nordstrom 1990) Ni(OH)2 solubility 10.8: independent value within 2.5 kJ/mol
        self.assertLess(abs(log_ks0 - 10.8) * KJ_PER_LOG_K, 2.5)
        # llnl.dat: 12.7485 - 30.9852 = -18.2367 for Ni(OH)2 + H2O = Ni(OH)3- + H+ (0.3 kJ/mol)
        self.assertAlmostEqual(combined, 12.7485 - 30.9852, delta=0.5 / KJ_PER_LOG_K)
        # the data spread is real and stated: llnl.dat Ni(OH)2 alone is 9.9 kJ/mol away
        self.assertGreater(abs(log_ks0 - 12.7485) * KJ_PER_LOG_K, 9.0)
        rows = {r["id"]: r for r in table.species_rows("Ni")}
        self.assertIn("12.75", rows["Ni(OH)2"]["evidence"])
        # the old atlas constant (12.17) is 6.6 kJ/mol from the NEA value: the module's own 2.5 kJ limit
        self.assertGreater(abs(12.17 - log_ks0) * KJ_PER_LOG_K, 6.0)

    def test_boundary_moves_from_atlas_to_nea(self):
        # Ni2+/Ni(OH)2 at a = 1e-6: atlas 9.09 -> NEA 8.51 (review pbx-sci S1)
        self.assertAlmostEqual(solver.boundary_line("Ni", "Ni2+", "Ni(OH)2", -6.0)["pH"], (11.02 + 6.0) / 2, delta=0.01)

    def test_nio2_is_withheld_and_the_sentence_about_it_is_pinned(self):
        # review pbx-rr SF-2: served as V2 although anchored to the very 1.593 V it was checked against, and the
        # text said "about 5 mV" above the O2 line (the atlas-set figure) while it is 38 mV after the re-anchoring.
        self.assertNotIn("NiO2", {r["id"] for r in table.species_rows("Ni")})
        row = next(r for r in table.WITHHELD_SPECIES["Ni"] if r[0] == "NiO2")
        self.assertEqual(row[10], "V3")
        self.assertIn("at least 38 mV above it (minimum at pH 8.5)", row[11])
        self.assertIn("WITHHELD estimate", row[11])
        self.assertAlmostEqual(row[7], oracle.WITHHELD["Ni"]["NiO2"][4], delta=1e-6)
        # the pinned figure: with NiO2 added back (alone: the other withheld rows stay out), the lowest edge of
        # its domain above the O2 line
        sp = dict(oracle.DATA["Ni"]["sp"])
        sp["NiO2"] = oracle.WITHHELD["Ni"]["NiO2"]
        c = oracle.coeffs_of(sp, oracle.DATA["Ni"]["H2O"], -6.0)

        def dominant(ph, e):
            g = {k: v[0] + v[1] * ph + v[2] * e for k, v in c.items()}
            return min(g, key=g.get)

        best = None
        for i in range(-200, 1601, 5):
            ph = i / 100.0
            e_oer = 1.2288 - K * ph
            e = e_oer
            while dominant(ph, e) != "NiO2" and e < e_oer + 0.2:
                e += 0.0005
            if e < e_oer + 0.2 and (best is None or e - e_oer < best):
                best = e - e_oer
        self.assertAlmostEqual(best, 0.038, delta=0.002)
        # withholding it changes no cell inside the water window
        for ph, e in _grid(ph_lo=-2.0, ph_hi=16.0, ph_step=0.1, e_lo=-3.0, e_hi=2.5, e_step=0.01):
            if -K * ph <= e <= 1.2288 - K * ph:
                self.assertNotEqual(dominant(ph, e), "NiO2")


class StandardPotentialCrossCheckTest(unittest.TestCase):
    """Unit-activity E0 from the table vs independent published values (10 mV; Mg2+/Mg 20 mV)."""

    ACID = (("Fe", "Fe", "Fe2+", -0.447, 0.010), ("Fe", "Fe2+", "Fe3+", 0.771, 0.010),
            ("Fe", "Fe", "Fe3O4", -0.085, 0.010), ("Fe", "Fe3O4", "Fe2O3", 0.22, 0.010),
            ("Fe", "Fe2+", "Fe2O3", 0.728, 0.010), ("Fe", "Fe2+", "Fe3O4", 0.98, 0.010),
            ("Fe", "Fe3+", "FeO4^2-", 2.20, 0.010),
            ("Cu", "Cu", "Cu2+", 0.3419, 0.010), ("Cu", "Cu", "Cu+", 0.521, 0.010),
            ("Cu", "Cu+", "Cu2+", 0.153, 0.010), ("Zn", "Zn", "Zn2+", -0.7618, 0.010),
            ("Mg", "Mg", "Mg2+", -2.372, 0.020))
    ALKALINE = (("Cu", "Cu", "Cu2O", -0.36),
                ("Zn", "Zn", "ZnO2^2-", -1.199), ("Mg", "Mg", "Mg(OH)2", -2.69))

    def test_acid_couples(self):
        for el, a, b, ref, tol in self.ACID:
            with self.subTest(couple=f"{el} {a}/{b}"):
                e0 = solver.boundary_line(el, a, b, 0.0)["E_V_SHE_at_pH0"]
                self.assertAlmostEqual(e0, ref, delta=tol)

    def test_alkaline_couples(self):
        for el, a, b, ref in self.ALKALINE:
            with self.subTest(couple=f"{el} {a}/{b}"):
                line = solver.boundary_line(el, a, b, 0.0)
                self.assertAlmostEqual(line["E_V_SHE_at_pH0"] + 14.0 * line["slope_V_per_pH"], ref, delta=0.010)

    def test_nickel_exceptions_are_documented_and_bounded(self):
        # NEA-TDB (calorimetric / solubility based) vs the older electrochemical CRC values:
        # Ni2+/Ni -0.2372 vs -0.257 V, Ni(OH)2/Ni (1 M OH-) -0.739 vs -0.72 V. Both are 19-20 mV off,
        # outside the 10 mV V2 test, inside 25 mV; the rows' evidence records them.
        e0 = solver.boundary_line("Ni", "Ni", "Ni2+", 0.0)["E_V_SHE_at_pH0"]
        line = solver.boundary_line("Ni", "Ni", "Ni(OH)2", 0.0)
        alk = line["E_V_SHE_at_pH0"] + 14.0 * line["slope_V_per_pH"]
        self.assertAlmostEqual(e0, -0.2372, delta=1e-3)
        self.assertAlmostEqual(alk, -0.7393, delta=1e-3)
        self.assertGreater(abs(e0 - -0.257), 0.010)
        self.assertGreater(abs(alk - -0.72), 0.010)
        self.assertLess(abs(e0 - -0.257), 0.025)
        self.assertLess(abs(alk - -0.72), 0.025)
        rows = {r["id"]: r for r in table.species_rows("Ni")}
        self.assertIn("-0.257", rows["Ni2+"]["evidence"])
        self.assertIn("-0.72", rows["Ni(OH)2"]["evidence"])
        self.assertIn("documented exception", rows["Ni2+"]["evidence"])
        self.assertIn("documented exception", rows["Ni(OH)2"]["evidence"])

    def test_table_values_for_documented_deltas(self):
        self.assertAlmostEqual(solver.boundary_line("Fe", "Fe", "Fe2+", 0.0)["E_V_SHE_at_pH0"], -0.4401, delta=1e-3)
        self.assertAlmostEqual(solver.boundary_line("Mg", "Mg", "Mg2+", 0.0)["E_V_SHE_at_pH0"], -2.3568, delta=1e-3)


class WaterLinesTest(unittest.TestCase):
    def test_water_lines_at_25c(self):
        lines = solver.generate_water_stability_lines(25.0)
        for row_a, row_b in zip(lines["line_a_hydrogen_HER"], lines["line_b_oxygen_OER"]):
            self.assertAlmostEqual(row_a["E_V_SHE"], 0.0 - K * row_a["pH"], delta=0.001)
            self.assertAlmostEqual(row_b["E_V_SHE"], 1.2288 - K * row_b["pH"], delta=0.001)
        self.assertEqual(lines["e0_OER"], 1.2288)
        self.assertAlmostEqual(lines["nernstSlope"], K, delta=1e-5)

    def test_water_lines_match_oracle(self):
        for ph in (0.0, 4.5, 14.0):
            her, oer = oracle.water_lines(ph)
            got = solver._water_lines_at(ph)
            self.assertAlmostEqual(got[0], her, delta=1e-6)
            self.assertAlmostEqual(got[1], oer, delta=1e-6)


class ArgminPolygonConsistencyTest(unittest.TestCase):
    def test_solver_argmin_equals_independent_brute_force(self):
        for el in ELEMENTS:
            for log_a in (-6.0, -3.0, 0.0):
                checked = 0
                for ph, e in _grid():
                    if oracle.margin_V(el, ph, e, log_a) < 0.001:
                        continue
                    sp = solver._argmin(solver._coefficients(el, log_a), ph, e)
                    self.assertEqual(sp.id, oracle.dominant(el, ph, e, log_a), (el, log_a, ph, e))
                    checked += 1
                self.assertGreater(checked, 5000, (el, log_a))

    def test_exact_tie_goes_to_the_earlier_table_row(self):
        class Row:
            def __init__(self, ident, c0):
                self.id, self.c0, self.cpH, self.cE = ident, c0, 0.0, 0.0
        self.assertEqual(solver._argmin([Row("first", 5.0), Row("second", 5.0), Row("third", 9.0)], 0.0, 0.0).id, "first")
        self.assertEqual(solver._argmin([Row("a", 5.0), Row("b", 4.0)], 0.0, 0.0).id, "b")

    def test_no_species_has_a_lower_g_than_the_winner(self):
        for el in ELEMENTS:
            for ph, e in _grid(ph_step=0.5, e_step=0.051):
                winner = solver._argmin(solver._coefficients(el, -6.0), ph, e)
                g = oracle.g_values(el, ph, e)
                self.assertLessEqual(g[winner.id], min(g.values()) + 1e-6, (el, ph, e))

    def test_argmin_agrees_with_polygon_membership(self):
        for el in ELEMENTS:
            for log_a in (-6.0, -2.0):
                domains = solver.compute_domains(el, log_a)
                for ph, e in _grid(ph_step=0.37, e_step=0.0411):
                    if oracle.margin_V(el, ph, e, log_a) < 0.001:
                        continue
                    winner = solver._argmin(solver._coefficients(el, log_a), ph, e).id
                    inside = [sid for sid, poly in domains.items() if oracle.point_in_polygon(poly, ph, e)]
                    self.assertEqual(inside, [winner], (el, log_a, ph, e))

    def test_solver_polygons_match_oracle_polygons(self):
        for el in ELEMENTS:
            ours = solver.compute_domains(el, -6.0)
            theirs = oracle.polygons(el, -6.0)
            self.assertEqual(set(ours), set(theirs), el)
            for sid, poly in ours.items():
                area = 0.5 * abs(sum(poly[k][0] * poly[(k + 1) % len(poly)][1] - poly[(k + 1) % len(poly)][0] * poly[k][1]
                                     for k in range(len(poly))))
                self.assertAlmostEqual(area, theirs[sid][1], delta=1e-6, msg=(el, sid))

    def test_boundary_segments_lie_on_the_minimum(self):
        # every emitted segment: both species equal and no other species lower along it
        for el in ELEMENTS:
            result = solver.solve_pourbaix_diagram(el, 25.0, -6.0, 0.0, [])
            self.assertTrue(result["analyticalBoundaries"], el)
            for b in result["analyticalBoundaries"]:
                p0, p1 = b["points"]
                for t in (0.05, 0.5, 0.95):
                    ph = p0["pH"] + t * (p1["pH"] - p0["pH"])
                    e = p0["E_V_SHE"] + t * (p1["E_V_SHE"] - p0["E_V_SHE"])
                    g = oracle.g_values(el, ph, e)
                    low = min(g.values())
                    self.assertAlmostEqual(g[b["speciesAId"]], low, delta=1e-3, msg=(el, b["id"]))
                    self.assertAlmostEqual(g[b["speciesBId"]], low, delta=1e-3, msg=(el, b["id"]))

    def test_grid_cells_use_the_argmin_and_the_category_of_the_role(self):
        for el in ELEMENTS:
            result = solver.solve_pourbaix_diagram(el, 25.0, -6.0, 0.0, [])
            self.assertEqual(len(result["stabilityFieldGrid"]), 315)
            for cell in result["stabilityFieldGrid"]:
                if oracle.margin_V(el, cell["pH"], cell["E_V_SHE"]) < 0.001:
                    continue
                self.assertEqual(cell["dominantSpeciesId"], oracle.dominant(el, cell["pH"], cell["E_V_SHE"]))
                self.assertEqual(cell["category"], oracle.category(el, cell["pH"], cell["E_V_SHE"]))

    def test_withholding_ni3o4_ni2o3_changes_categories_and_is_documented(self):
        # Spec section 2 says the category does not depend on Ni3O4/Ni2O3; with the atlas values it does
        # (they would replace Ni2+ / HNiO2- by "Passivation" in part of the map). They are unverified (V3)
        # and withheld, so the engine must not use them.
        diff = 0
        for ph, e in _grid(ph_lo=0.0, ph_hi=14.0, ph_step=0.1, e_lo=-1.5, e_hi=2.0, e_step=0.01):
            if oracle.category("Ni", ph, e) != oracle.category("Ni", ph, e, include_withheld=True):
                diff += 1
        self.assertGreater(diff, 0)
        self.assertNotIn("Ni3O4", {r["id"] for r in table.species_rows("Ni")})
        self.assertNotIn("Ni2O3", {r["id"] for r in table.species_rows("Ni")})


class BoundaryCompletenessTest(unittest.TestCase):
    """analyticalBoundaries is exactly the set of shared polygon edges of the oracle, for every element."""

    def test_boundary_pairs_and_ends_equal_the_oracle_edges(self):
        import pourbaix_golden_check as check
        for el in ELEMENTS:
            for log_a in (-6.0, -4.0, -3.0, 0.0):
                with self.subTest(element=el, log_a=log_a):
                    result = solver.solve_pourbaix_diagram(el, 25.0, log_a, 0.0, [])
                    ids = {s["id"]: s["id"] for s in result["speciesTable"]["species"]}
                    got = {(b["speciesAId"], b["speciesBId"]): [(q["pH"], q["E_V_SHE"]) for q in b["points"]]
                           for b in result["analyticalBoundaries"]}
                    want = check._oracle_boundaries(el, log_a)
                    self.assertEqual(sorted(got), sorted(want))
                    self.assertTrue(set(sum(map(list, got), [])) <= set(ids))
                    for pair, pts in got.items():
                        ends = want[pair]
                        straight = all(abs(pts[0][i] - ends[0][i]) <= 1e-4 and abs(pts[1][i] - ends[1][i]) <= 1e-4 for i in (0, 1))
                        swapped = all(abs(pts[0][i] - ends[1][i]) <= 1e-4 and abs(pts[1][i] - ends[0][i]) <= 1e-4 for i in (0, 1))
                        self.assertTrue(straight or swapped, (pair, pts, ends))
                    # no boundary is shorter than 1e-6 and every domain edge appears (P8 mutant: short ones dropped)
                    for pair, ends in want.items():
                        self.assertGreater(math.hypot(ends[0][0] - ends[1][0], ends[0][1] - ends[1][1]), 1e-9)


class CategoryTest(unittest.TestCase):
    def test_role_to_category(self):
        for el in ELEMENTS:
            for row in table.species_rows(el):
                self.assertEqual(row["category"], table.CATEGORY_BY_ROLE[row["role"]])
        res = {sid: solver.evaluate_point_mechanism("Fe", ph, e) for sid, ph, e in (
            ("Fe", 7.0, -0.9), ("Fe2+", 2.0, 0.0), ("HFeO2-", 15.0, -1.0), ("Fe2O3", 7.0, 0.5), ("FeO4^2-", 7.0, 1.9))}
        self.assertEqual({k: v["dominantSpeciesId"] for k, v in res.items()},
                         {k: k for k in res})
        self.assertEqual({k: v["category"] for k, v in res.items()}, {
            "Fe": "Immunity", "Fe2+": "Corrosion (acid)", "HFeO2-": "Corrosion (alkaline)",
            "Fe2O3": "Passivation (thermodynamic, film-forming)", "FeO4^2-": "Transpassive"})

    def test_outside_water_window_is_labelled(self):
        inside = solver.evaluate_point_mechanism("Fe", 7.0, 0.0)
        self.assertTrue(inside["isInsideWaterStability"])
        below = solver.evaluate_point_mechanism("Fe", 7.0, -0.9)
        self.assertFalse(below["isInsideWaterStability"])
        self.assertIn("outside water stability (metastable)", below["regime"])
        self.assertEqual(below["category"], "Immunity")
        above = solver.evaluate_point_mechanism("Fe", 7.0, 1.2)
        self.assertFalse(above["isInsideWaterStability"])

    def test_texts_are_fixed_per_category_and_make_no_unsupported_claims(self):
        texts = {}
        for ph, e in ((7.0, -0.9), (2.0, 0.0), (15.0, -1.0), (7.0, 0.5), (7.0, 1.9)):
            r = solver.evaluate_point_mechanism("Fe", ph, e)
            texts.setdefault(r["category"], set()).add((r["mechanismId"], r["mechanismTitle"], r["mechanismDetails"]))
        self.assertEqual(len(texts), 5)
        for category, variants in texts.items():
            self.assertEqual(len(variants), 1, category)
        blob = json.dumps(solver.CATEGORY_TEXTS) + json.dumps(solver.CATEGORY_MITIGATION)
        source = (HERE / "pourbaix_solver.py").read_text(encoding="utf-8")
        for claim in ("negligible passivation current", "practically immune", "100% corrosion protection",
                      "Immense", "Ultra-Protective", "stifled"):
            self.assertNotIn(claim, blob)
            self.assertNotIn(claim, source)

    def test_cathodic_protection_uses_the_computed_metal_boundary(self):
        r = solver.evaluate_point_mechanism("Fe", 2.0, 0.0)
        self.assertEqual(r["deltaE_Immunity_V"], round(0.0 - (-0.6176), 3))
        self.assertTrue(any("-0.62 V" in m for m in r["engineeringMitigations"]), r["engineeringMitigations"])
        cu = solver.evaluate_point_mechanism("Cu", 3.0, 0.5)
        boundary = solver._metal_boundary_E(solver._coefficients("Cu", -6.0), 3.0)
        self.assertAlmostEqual(boundary, 0.1619, delta=0.001)
        self.assertEqual(cu["deltaE_Immunity_V"], round(0.5 - boundary, 3))


class ValidationTest(unittest.TestCase):
    def _raises(self, code, field, *args, **kwargs):
        with self.assertRaises(solver.ValidationError) as ctx:
            solver.solve_pourbaix_diagram(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)
        self.assertEqual(ctx.exception.field, field)
        return ctx.exception

    def test_temperature_other_than_25c_is_unsupported(self):
        for t in (24.4, 25.6, 0.0, 60.0, 80.0, 300.0):
            err = self._raises("TEMPERATURE_UNSUPPORTED", "temperature_C", "Fe", t, -6.0, 0.0, [])
            self.assertEqual(err.detail["supported"], [25.0])
        for t in (24.5, 25.0, 25.5):
            self.assertEqual(solver.solve_pourbaix_diagram("Fe", t, -6.0, 0.0, [])["parameters"]["temperature_C"], 25.0)
        self._raises("TEMPERATURE_UNSUPPORTED", "temperature_C", "Al", 60, -4, 200, [])  # Al data is 25 C only too
        self._raises("TEMPERATURE_UNSUPPORTED", "temperature_C", "Ti", 60, -6, 0, [])  # before the data check
        self._raises("TEMPERATURE_UNSUPPORTED", "temperature_C", "Ni", 80, -5, 600, [])

    def test_unavailable_elements_raise_data_unavailable(self):
        # v5: every engine element has a table (Cr, Mo and Ti with withheld candidate sets); the refusal path
        # stays for an element whose table is removed
        self.assertEqual(table.available_elements(), list(ALL_ELEMENTS))
        self.assertEqual(table.UNAVAILABLE_ELEMENTS, {})
        self.assertEqual(solver.UNAVAILABLE_ONLY_ELEMENTS, ())
        from unittest import mock
        with mock.patch.object(table, "available_elements", return_value=list(ELEMENTS)), \
                mock.patch.dict(table.UNAVAILABLE_ELEMENTS, {"Cr": "test reason"}):
            err = self._raises("POURBAIX_DATA_UNAVAILABLE", "element", "Cr", 25.0, -6.0, 0.0, [])
        self.assertEqual(err.detail, {"element": "Cr", "reason": "test reason", "available": list(ELEMENTS)})

    def test_unknown_element_still_unknown_element(self):
        self._raises("UNKNOWN_ELEMENT", "element", "Unobtainium", 25.0, -6.0, 0.0, [])

    def test_unknown_reference_electrode_raises(self):
        pts = [{"ph": 7, "potential_V": 0.1, "refElectrode": "NotARef"}]
        self._raises("UNKNOWN_REFERENCE_ELECTRODE", "refElectrode", "Fe", 25.0, -6.0, 0.0, pts)
        ok = solver.solve_pourbaix_diagram("Fe", 25.0, -6.0, 0.0, [{"ph": 7, "potential_V": 0.1}])
        self.assertEqual(ok["experimentalOverlay"]["points"][0]["potential_V_SHE"], 0.1)  # default SHE

    def test_activity_range(self):
        # S2 (review pbx-sci): the hydrolysis species are omitted for every element, so the activity is
        # limited to 1e-6 .. 1 (MgOH+ takes about 5 % of the window at 1e-8)
        for bad in (-8.5, -8.0, -7.0, -6.01, 0.5, 3):
            self._raises("OUT_OF_RANGE", "ionActivity_log10", "Fe", 25.0, bad, 0.0, [])
        for good in (-6.0, -3.0, 0.0):
            self.assertTrue(solver.solve_pourbaix_diagram("Fe", 25.0, good, 0.0, [])["success"])
        self.assertEqual(table.ACTIVITY_LOG10_RANGE, (-6.0, 0.0))

    def test_hydrolysis_omission_is_stated_in_the_model_block_for_every_element(self):
        for el in ELEMENTS:
            model = solver.solve_pourbaix_diagram(el, 25.0, -6.0, 0.0, [])["model"]
            text = " ".join(model["excludedSpecies"])
            self.assertIn("mononuclear hydrolysis species", text, el)
            self.assertIn("omitted", text, el)
            self.assertEqual(model["dissolvedActivityRange_log10"], [-6.0, 0.0], el)

    def test_zn_is_named_as_constant_dependent_in_the_statement_and_the_zno_row(self):
        # review pbx-rr SF-1: Zn(OH)2(aq): log K(ZnO + H2O = Zn(OH)2(aq)) = -6.28 (IUPAC 2013, ZnO survives at
        # 1e-6 M) or -5.36 (wateq4f / Baes & Mesmer, ZnO domain gone) with the table's NBS ZnO
        rows = {r["id"]: r for r in table.species_rows("Zn")}
        log_ks0 = -(rows["Zn2+"]["dfG_kJ_mol"] + table.water_dfg_kj_mol("Zn") - rows["ZnO"]["dfG_kJ_mol"]) / KJ_PER_LOG_K
        self.assertAlmostEqual(log_ks0, 11.54, delta=0.02)               # ZnO + 2H+ = Zn2+ + H2O
        self.assertAlmostEqual(log_ks0 - 16.9, -5.36, delta=0.02)        # wateq4f / Baes & Mesmer log *beta2
        self.assertAlmostEqual(log_ks0 - 17.82, -6.28, delta=0.02)       # IUPAC 2013
        zn = solver.solve_pourbaix_diagram("Zn", 25.0, -6.0, 0.0, [])["model"]["excludedSpecies"][2]
        self.assertIn("Zn is constant-dependent", zn)
        self.assertIn("IUPAC 2013", zn)
        self.assertIn("Baes & Mesmer", zn)
        self.assertIn("Fe, Ni, Cu, Mg and Al", zn)
        for text in (rows["ZnO"]["evidence"],):
            self.assertIn("constant-dependent", text)
            self.assertIn("-6.28", text)
            self.assertIn("-5.36", text)
        ui = (HERE.parent / "src" / "components" / "DynamicPourbaixStudio.tsx").read_text(encoding="utf-8")
        self.assertIn("Zn is constant-dependent", ui)

    def test_bad_point_inputs_are_validation_errors_not_classifications(self):
        # S3 (review pbx-sci): NaN pH was classified Immunity, inf E Immunity, pH 30 accepted, missing pH/E
        # defaulted to 7 / 0 V.
        nan, inf = float("nan"), float("inf")
        cases = [
            ({"ph": nan, "potential_V": 0.0}, "NON_FINITE", "experimentalPoints[0].pH"),
            ({"ph": 7.0, "potential_V": inf}, "NON_FINITE", "experimentalPoints[0].potential_V"),
            ({"ph": 7.0, "potential_V": -inf}, "NON_FINITE", "experimentalPoints[0].potential_V"),
            ({"ph": "nan", "potential_V": 0.0}, "NON_FINITE", "experimentalPoints[0].pH"),
            ({"ph": "7", "potential_V": 0.0}, "NON_FINITE", "experimentalPoints[0].pH"),
            ({"ph": True, "potential_V": 0.0}, "NON_FINITE", "experimentalPoints[0].pH"),
            ({"ph": 30.0, "potential_V": 0.0}, "OUT_OF_RANGE", "experimentalPoints[0].pH"),
            ({"ph": -2.5, "potential_V": 0.0}, "OUT_OF_RANGE", "experimentalPoints[0].pH"),
            ({"ph": 7.0, "potential_V": 3.0}, "OUT_OF_RANGE", "experimentalPoints[0].potential_V_SHE"),
            ({"ph": 7.0, "potential_V": -3.4, "refElectrode": "CSE"}, "OUT_OF_RANGE",
             "experimentalPoints[0].potential_V_SHE"),   # -3.4 + 0.316 V SHE is below the box
            ({"potential_V": 0.0}, "MISSING_PROPERTY", "experimentalPoints[0].pH"),
            ({"ph": 7.0}, "MISSING_PROPERTY", "experimentalPoints[0].potential_V"),
            ({}, "MISSING_PROPERTY", "experimentalPoints[0].pH"),
            ("not an object", "MISSING_PROPERTY", "experimentalPoints[0]"),
        ]
        for point, code, field in cases:
            with self.subTest(point=repr(point)):
                err = self._raises(code, field, "Fe", 25.0, -6.0, 0.0, [point])
                self.assertEqual(err.field, field)
        # the second point is the bad one: the index is reported
        self._raises("OUT_OF_RANGE", "experimentalPoints[1].pH", "Fe", 25.0, -6.0, 0.0,
                     [{"ph": 7.0, "potential_V": 0.0}, {"ph": 17.0, "potential_V": 0.0}])
        # box edges are accepted
        for ph, e in ((-2.0, -3.0), (16.0, 2.5)):
            res = solver.solve_pourbaix_diagram("Fe", 25.0, -6.0, 0.0, [{"ph": ph, "potential_V": e}])
            self.assertEqual(len(res["experimentalOverlay"]["points"]), 1)
        # the direct entry point refuses too
        for ph, e in ((float("nan"), 0.0), (7.0, float("inf")), (30.0, 0.0)):
            with self.assertRaises(solver.ValidationError):
                solver.evaluate_point_mechanism("Fe", ph, e)

    def test_cli_rejects_nan_tokens_in_points_and_reads_stdin_as_utf8(self):
        raw = '{"element": "Fe", "experimentalPoints": [{"ph": NaN, "potential_V": 0.1}]}'
        proc = subprocess.run([sys.executable, "-B", str(HERE / "pourbaix_solver.py")], input=raw.encode("utf-8"),
                              capture_output=True)
        out = json.loads(proc.stdout.decode("ascii"))
        self.assertEqual((proc.returncode, out["error"]["code"]), (2, "NON_FINITE"))
        # C7 (review pbx-code): stdin is decoded as UTF-8 whatever the locale code page is, so echoed
        # notes survive; run with UTF-8 mode off to reproduce a cp1254 / cp1252 locale
        notes = "Fe²⁺ → Fe₂O₃ · çğıöşü"
        payload = {"element": "Fe", "experimentalPoints": [{"ph": 7.0, "potential_V": 0.1, "notes": notes}]}
        env = dict(os.environ, PYTHONUTF8="0", PYTHONIOENCODING="cp1254")
        proc = subprocess.run([sys.executable, "-B", str(HERE / "pourbaix_solver.py")],
                              input=json.dumps(payload, ensure_ascii=False).encode("utf-8"), capture_output=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertEqual(json.loads(proc.stdout.decode("ascii"))["experimentalOverlay"]["points"][0]["notes"], notes)

    def test_cli_exit_codes_and_envelopes(self):
        code, out = _run_cli({"element": "Al", "temperature_C": 60})
        self.assertEqual((code, out["errorKind"], out["error"]["code"]), (2, "validation", "TEMPERATURE_UNSUPPORTED"))
        code, out = _run_cli({"element": "Mo", "ionActivity_log10": -3})
        self.assertEqual((code, out["error"]["code"], out["error"]["field"]), (2, "OUT_OF_RANGE", "ionActivity_log10"))
        code, out = _run_cli({"element": "Ti"})
        self.assertEqual((code, out["engine"]), (0, "pourbaix-gibbs-25c-v5"))
        code, out = _run_cli({"element": "Fe", "experimentalPoints": [{"ph": 7, "potential_V": 0, "refElectrode": "X"}]})
        self.assertEqual((code, out["error"]["code"]), (2, "UNKNOWN_REFERENCE_ELECTRODE"))
        self.assertEqual(set(out["error"]), {"code", "field", "message", "detail"})
        code, out = _run_cli({"element": "Fe"})
        self.assertEqual(code, 0)
        self.assertEqual(out["engine"], "pourbaix-gibbs-25c-v5")


class OutputContractTest(unittest.TestCase):
    OLD_TOP_KEYS = {"success", "engine", "computeTimeMs", "element", "systemName", "parameters",
                    "waterStabilityLines", "chloridePittingBoundary", "analyticalBoundaries", "speciesInventory",
                    "stabilityFieldGrid", "experimentalOverlay", "provenance"}
    OLD_POINT_KEYS = {"id", "name", "pH", "potential_Input_V", "refElectrode", "potential_V_SHE",
                      "currentDensity_uA_cm2", "timeHours", "stageName", "notes", "regime", "dominantSpecies",
                      "mechanismId", "mechanismTitle", "mechanismDetails", "riskLevel", "color", "depolarizer",
                      "deltaE_Immunity_V", "deltaE_Pitting_V", "isInsideWaterStability", "engineeringMitigations"}

    def setUp(self):
        self.points = [{"id": "p1", "name": "Acid", "ph": 2, "potential_V": -0.2, "refElectrode": "SCE"},
                       {"ph": 12, "potential_V": 0.3}]
        self.result = solver.solve_pourbaix_diagram("Fe", 25, -6, 1000, self.points)

    def test_every_old_key_is_kept_and_new_keys_are_added(self):
        self.assertTrue(self.OLD_TOP_KEYS <= set(self.result))
        self.assertTrue({"model", "speciesTable", "temperatureStatus", "domains", "dataValidity"} <= set(self.result))
        self.assertEqual(self.result["engine"], "pourbaix-gibbs-25c-v5")
        self.assertTrue({"temperature_C", "nernstSlope_V_pH", "ionActivity_log10", "chlorideConcentration_ppm",
                         "chloride_Molar", "pittingPotential_V_SHE", "pittingRisk"} <= set(self.result["parameters"]))
        for pt in self.result["experimentalOverlay"]["points"]:
            self.assertTrue(self.OLD_POINT_KEYS <= set(pt))
            self.assertTrue({"category", "dominantSpeciesId", "insideWithheldDataRegion",
                             "withheldDataSpeciesIds"} <= set(pt))
        for cell in self.result["stabilityFieldGrid"]:
            self.assertTrue({"pH", "E_V_SHE", "regime", "dominantSpecies", "mechanismTitle", "color",
                             "category", "dominantSpeciesId"} <= set(cell))
        for b in self.result["analyticalBoundaries"]:
            self.assertTrue({"id", "name", "equation", "boundaryType", "speciesA", "speciesB", "points"} <= set(b))
        self.assertTrue({"immunity", "corrosion_acid", "passivation", "corrosion_alkaline"} <= set(self.result["speciesInventory"]))

    def test_model_and_provenance(self):
        model = self.result["model"]
        self.assertEqual(model["temperature_C"], 25.0)
        self.assertIn("γ=1", model["activityCoefficients"])
        self.assertTrue(any("Cr₂O₇" in s for s in model["excludedSpecies"]))
        self.assertEqual(self.result["temperatureStatus"]["status"], "supported-25C-only")
        rows = self.result["speciesTable"]["species"]
        self.assertEqual([r["id"] for r in rows], [r["id"] for r in table.species_rows("Fe")])
        for r in rows:
            self.assertIn(r["verification"], ("V1", "V2"))
            self.assertTrue(r["source"] and r["evidence"] and r["role"])
        self.assertEqual(self.result["speciesTable"]["waterDfG_kJ_mol"], table.water_dfg_kj_mol("Fe"))

    def test_epit_model_is_gone_and_chloride_is_only_echoed(self):
        b = self.result["chloridePittingBoundary"]
        self.assertEqual(b["status"], "unavailable-no-sourced-epit")
        self.assertIs(b["pittingActive"], False)
        self.assertEqual(b["chloride_ppm"], 1000.0)
        self.assertIsNone(self.result["parameters"]["pittingPotential_V_SHE"])
        for pt in self.result["experimentalOverlay"]["points"]:
            self.assertIsNone(pt["deltaE_Pitting_V"])
            self.assertNotIn("Pitting", pt["regime"])
        with_cl = solver.solve_pourbaix_diagram("Fe", 25, -6, 0, self.points)
        self.assertEqual(with_cl["stabilityFieldGrid"], self.result["stabilityFieldGrid"])
        source = (HERE / "pourbaix_solver.py").read_text(encoding="utf-8")
        for token in ("base_epit", "Chloride Pitting Breakdown", "k_sensitivity", "calculate_chloride_pitting_boundary"):
            self.assertNotIn(token, source)

    def test_reference_electrode_offsets_applied(self):
        pts = {p["id"]: p for p in self.result["experimentalOverlay"]["points"]}
        self.assertAlmostEqual(pts["p1"]["potential_V_SHE"], -0.2 + 0.241, places=6)

    def test_default_cases_old_to_new(self):
        # fe_chloride_points: p4 (pH 7, -0.9 V vs CSE = -0.584 V SHE) was Passivation, is Fe2+ corrosion;
        # p1-p3 keep their category; cu_nochloride keeps its category.
        fe = solver.solve_pourbaix_diagram("Fe", 25, -6, 1000, [
            {"id": "p1", "name": "Acid", "ph": 2, "potential_V": -0.2, "refElectrode": "SCE"},
            {"id": "p2", "name": "Neutral", "ph": 7, "potential_V": 0.1, "refElectrode": "Ag/AgCl (3M KCl)"},
            {"id": "p3", "name": "Alkaline", "ph": 12, "potential_V": 0.3, "refElectrode": "SHE"},
            {"id": "p4", "name": "Cathodic", "ph": 7, "potential_V": -0.9, "refElectrode": "CSE"}])
        got = {p["id"]: (p["category"], p["dominantSpeciesId"]) for p in fe["experimentalOverlay"]["points"]}
        self.assertEqual(got["p4"], ("Corrosion (acid)", "Fe2+"))
        self.assertEqual(got["p1"][0], "Corrosion (acid)")
        self.assertEqual(got["p2"][0], "Passivation (thermodynamic, film-forming)")
        self.assertEqual(got["p3"][0], "Passivation (thermodynamic, film-forming)")
        cu = solver.solve_pourbaix_diagram("Cu", 25, -6, 0, [{"ph": 5, "potential_V": 0.4, "refElectrode": "SHE"}])
        self.assertEqual(cu["experimentalOverlay"]["points"][0]["category"], "Corrosion (acid)")


class GeneratedSpeciesFileTest(unittest.TestCase):
    def test_committed_json_is_byte_identical_to_a_fresh_emit(self):
        committed = table.GENERATED_JSON.read_bytes()
        self.assertEqual(committed, table.render_json().encode("utf-8"),
                         "run: python pourbaix_species_25c.py --emit")
        self.assertNotIn(b"\r", committed)
        self.assertTrue(committed.endswith(b"}\n"))
        self.assertFalse(table.is_stale())

    def test_emit_is_deterministic_and_check_cli_passes(self):
        self.assertEqual(table.render_json(), table.render_json())
        proc = subprocess.run([sys.executable, "-B", str(HERE / "pourbaix_species_25c.py"), "--check"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_emit_to_a_scratch_path_is_lf_and_identical(self):
        import tempfile
        with tempfile.TemporaryDirectory(prefix="pourbaix-e-emit-") as tmp:
            path = Path(tmp) / "out" / "pourbaixSpecies25C.json"
            table.emit(path)
            self.assertEqual(path.read_bytes(), table.GENERATED_JSON.read_bytes())

    def test_gitattributes_pins_lf(self):
        text = (HERE.parent / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("/src/generated/pourbaixSpecies25C.json text eol=lf", text.splitlines())

    def test_document_content(self):
        doc = json.loads(table.GENERATED_JSON.read_text(encoding="utf-8"))
        self.assertEqual(doc["schema"], "pourbaix-species-25c-v2")
        self.assertEqual({k for k, v in doc["elements"].items() if v["available"]}, set(ALL_ELEMENTS))
        self.assertEqual(set(doc["elements"]), set(ALL_ELEMENTS))
        for el in ALL_ELEMENTS:
            self.assertEqual(doc["elements"][el]["activityLog10Range"], list(table.activity_range(el)))
            for row in doc["elements"][el]["species"]:
                self.assertTrue({"id", "formula", "x", "o", "h", "z", "phase", "dfG_kJ_mol", "role", "source",
                                 "verification", "evidence", "category"} <= set(row))
                self.assertIn(row["verification"], ("V1", "V2"), (el, row["id"]))
        self.assertEqual(doc["box"]["E_min_V_SHE"], -3.0)

    def test_table_agrees_with_the_independent_oracle_data(self):
        # the oracle encodes the numbers separately (atlas as cal/mol): a transcription slip shows here
        for el in ALL_ELEMENTS:
            ours = {r["id"]: r for r in table.species_rows(el)}
            theirs = oracle.DATA[el]["sp"]
            self.assertEqual(list(ours), list(theirs), el)
            self.assertAlmostEqual(table.water_dfg_kj_mol(el), oracle.DATA[el]["H2O"], delta=1e-9)
            for sid, (x, o, h, z, g, phase, role) in theirs.items():
                r = ours[sid]
                self.assertEqual((r["x"], r["o"], r["h"], r["z"], r["phase"], r["role"]), (x, o, h, z, phase, role), (el, sid))
                self.assertAlmostEqual(r["dfG_kJ_mol"], g, delta=1e-6, msg=(el, sid))

    def test_spec_values_in_kj(self):
        # SPEC section 2 prints these to 2 decimals; the table keeps the exact cal x 4.184 products
        expected = {("Fe", "Fe2+"): -84.94, ("Fe", "Fe3+"): -10.59, ("Fe", "HFeO2-"): -379.18,
                    ("Fe", "Fe3O4"): -1014.20, ("Fe", "Fe2O3"): -740.99}
        for (el, sid), kj in expected.items():
            row = next(r for r in table.species_rows(el) if r["id"] == sid)
            self.assertAlmostEqual(row["dfG_kJ_mol"], kj, delta=0.006, msg=(el, sid))
        self.assertAlmostEqual(table.water_dfg_kj_mol("Fe"), -237.19, delta=0.006)

    def test_fe_o4_is_derived_from_latimer_and_flagged(self):
        row = next(r for r in table.species_rows("Fe") if r["id"] == "FeO4^2-")
        self.assertEqual(row["source"], "L")
        self.assertIn("estimate", row["evidence"])

    def test_withheld_and_unverified_rows_are_not_in_the_engine(self):
        for el in ALL_ELEMENTS:
            for row in table.species_rows(el):
                self.assertNotEqual(row["verification"], "V3", (el, row["id"]))
        for rows in table.WITHHELD_SPECIES.values():
            self.assertTrue(any(r[10] == "V3" for r in rows))


if __name__ == "__main__":
    unittest.main()
