"""Phase 6a tranche 2b golden regression: kinetics and fatigue.

The cases live in tools/phase6a_t2b_golden_cases.py and were captured at the
pre-migration code (the solver blobs equal d33b6f5 and 7f3f803). The comparison
logic is the shared test_phase6a_golden.GoldenRegressionTest._check: bit-exact
canonical JSON, or the validation envelope for the cases listed in
test_phase6a_golden.EXPECTED_BEHAVIOUR_CHANGES.
"""

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "tools"))

import capture_phase6a_golden as golden  # noqa: E402
import test_phase6a_golden as shared  # noqa: E402

SOLVERS = ("kinetics_ttt_cct_solver", "lpbf_fatigue_fracture")


class T2bGoldenRegressionTest(unittest.TestCase):
    maxDiff = None
    _check = shared.GoldenRegressionTest._check

    def _solver(self, solver):
        for case in golden.CASES[solver]:
            with self.subTest(case=case):
                self._check(solver, case)

    def test_kinetics_ttt_cct_solver(self):
        self._solver("kinetics_ttt_cct_solver")

    def test_lpbf_fatigue_fracture(self):
        self._solver("lpbf_fatigue_fracture")

    def test_cases_are_registered(self):
        for solver in SOLVERS:
            self.assertIn(solver, golden.CASES)
            self.assertEqual(len(golden.CASES[solver]), 5, solver)
        self.assertEqual(golden.MODULE_DRIVERS["lpbf_fatigue_fracture"],
                         "tools/phase6a_fatigue_golden_driver.py")


class FatigueKs2Ks3OracleTest(unittest.TestCase):
    """Physics audit KS-2 / KS-3: the documented-change oracle accepts the re-blessed fatigue documents and
    rejects the d33b6f5 ones (Y = 1 El-Haddad, Paris from sqrt(area)/2), so it is not vacuous."""

    def test_oracle_separates_old_and_new_documents(self):
        import fatigue_documented_changes as fdc
        for case, payload in golden.CASES["lpbf_fatigue_fracture"].items():
            if (("lpbf_fatigue_fracture", case) in golden.step_b_excluded_cases()):
                continue
            with self.subTest(case=case):
                self.assertEqual(fdc.document_problems(golden.load_expected("lpbf_fatigue_fracture", case)["stdout"],
                                                       payload), [])
                self.assertTrue(fdc.document_problems(golden.load_golden("lpbf_fatigue_fracture", case)["stdout"],
                                                      payload))

    def test_ui_default_case_values(self):
        out = golden.load_expected("lpbf_fatigue_fracture", "ti64_ui_defaults")["stdout"]
        # Ti-6Al-4V internal 45 um, R = -1: a0 = (1/pi)(3.2/(0.5*510))^2 = 50.13 um (was 12.53, Y = 1).
        self.assertEqual(out["fatigue_limit"]["el_haddad_a0_um"], 50.13)
        self.assertEqual(out["fatigue_limit"]["fatigue_limit_R_minus_1_MPa"], 370.2)  # was 238.0
        # dK0 = 0.5 * 240 * sqrt(pi * 45e-6) = 1.427 < 3.2 (E647 Kmax at R = -1).
        self.assertEqual(out["paris_crack_growth"]["status"], "non_propagating")
        self.assertEqual(out["paris_crack_growth"]["delta_K_initial_MPa_m"], 1.427)


if __name__ == "__main__":
    unittest.main()
