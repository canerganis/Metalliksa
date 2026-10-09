"""Carbon activity against the SGTE unary graphite reference (GHSERCC) when HEX_A9 is not modelled.

mc_ni_v2036_repaired.tdb names HEX_A9 as the SER phase of C in its ELEMENT record but does not model that
phase, so a_C used to be null while mu_C was reported. The same file defines FUNCTION GHSERCC, the SGTE unary
expression for graphite (Dinsdale 1991, CALPHAD 15:317, DOI 10.1016/0364-5916(91)90030-N). The fallback uses
that function from the same database and never a reference from another database or from DFT.
All fixtures are in this file or in the repository's own TDB.
"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import calphad_solver as cs  # noqa: E402
import calphad_test_lane  # noqa: E402

TDB = HERE / "databases" / "mc_ni_v2036_repaired.tdb"
T_K = 1223.15  # 950 C
ALLOY = {"Ni": 53.0, "Cr": 19.0, "Fe": 18.0, "Nb": 5.0, "Mo": 3.0, "Ti": 1.0, "Al": 0.5, "C": 0.04}


def _load():
    from pycalphad import Database
    return Database(str(TDB))


@unittest.skipUnless(cs.PYCALPHAD_AVAILABLE, "pycalphad is not installed in this interpreter")
class TestGhserFunctionReference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dbf = _load()

    def test_c_element_phase_is_not_modelled(self):
        self.assertEqual(self.dbf.refstates["C"]["phase"], "HEX_A9")
        self.assertNotIn("HEX_A9", self.dbf.phases)

    def test_ghsercc_at_298_15_is_zero_by_ser_definition(self):
        # SER: G(298.15 K) = H298 and S298 from the ELEMENT record, so G = H298 - T*S298 with H298 taken as the
        # zero of the scale: GHSERCC(298.15) = -298.15 * S298 within 1 J/mol (S298 = 5.7423 J/mol/K from the TDB).
        s298 = float(self.dbf.refstates["C"]["S298"])
        ref = cs._ghser_function_gm(self.dbf, "C", [298.15])
        self.assertEqual(ref["function"], "GHSERCC")
        self.assertAlmostEqual(ref["gm"][0], -298.15 * s298, delta=1.0)

    def test_refuses_outside_the_stated_range(self):
        for t in (272.0, 6000.0, 7000.0):
            self.assertIsNone(cs._ghser_function_gm(self.dbf, "C", [t])["gm"], t)

    def test_reference_basis_string_and_value(self):
        ref = cs._pure_element_reference_gm(self.dbf, "C", [T_K])
        self.assertIsNotNone(ref["gm"])
        self.assertEqual(ref["basis"], "SER unary function GHSERCC (graphite, HEX_A9; "
                                       "reference phase not modelled in this database)")

    def test_elements_with_modelled_phase_do_not_use_the_fallback(self):
        ref = cs._pure_element_reference_gm(self.dbf, "NI", [T_K])
        self.assertNotIn("basis", ref)
        self.assertEqual(ref["phase"], "FCC_A1")

    def test_no_ghser_function_stays_unavailable(self):
        from types import SimpleNamespace
        fake = SimpleNamespace(refstates={"XX": {"phase": "BLANK"}}, phases={}, symbols={})
        ref = cs._pure_element_reference_gm(fake, "XX", [T_K])
        self.assertIsNone(ref["gm"])
        self.assertIn("BLANK", ref["reason"])


@unittest.skipUnless(calphad_test_lane.RUN_REAL_SOLVES, calphad_test_lane.SKIP_REASON)
class TestCarbonActivityRealSolve(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run = lambda: cs.compute_multi_component_equilibrium(
            "IN718+C", ALLOY, unit="wt_pct", t_min_c=950.0, t_max_c=950.0, t_step_c=25.0,
            database_id="mc_ni", adaptive_grid=False, boundary_refinement=False, scheil=False)
        cls.on = run()
        orig = cs._ghser_function_gm
        cs._ghser_function_gm = lambda dbf, el, temps: {"gm": None, "function": f"GHSER{el}"}
        try:
            cls.off = run()
        finally:
            cs._ghser_function_gm = orig

    @staticmethod
    def point(out):
        return next(p for p in out["equilibriumProfile"] if abs(p["temperatureK"] - T_K) < 1e-6)

    def test_carbon_activity_is_finite_and_in_unit_interval(self):
        a_c = self.point(self.on)["thermodynamicActivities"]["C"]
        self.assertIsNotNone(a_c)
        self.assertTrue(0.0 < a_c <= 1.0, a_c)
        ref = self.on["activityReferenceStates"]["C"]
        self.assertEqual(ref["status"], "available")
        self.assertIn("graphite", ref["basis"])
        self.assertIn("reference phase not modelled", ref["basis"])
        self.assertIn("Dinsdale", ref["referenceSource"])

    def test_without_fallback_carbon_activity_is_null(self):
        self.assertIsNone(self.point(self.off)["thermodynamicActivities"]["C"])

    def test_existing_activities_are_unchanged(self):
        a_on = self.point(self.on)["thermodynamicActivities"]
        a_off = self.point(self.off)["thermodynamicActivities"]
        self.assertAlmostEqual(a_on["NI"], 0.2727, delta=1e-3)
        for el, val in a_off.items():
            if el != "C":
                self.assertAlmostEqual(a_on[el], val, delta=1e-9, msg=el)


if __name__ == "__main__":
    unittest.main()
