"""Phase 6a tranche 2b golden regression: kinetics, stochastic UQ and fatigue.

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

SOLVERS = ("kinetics_ttt_cct_solver", "stochastic_uq_mmpds_solver", "lpbf_fatigue_fracture")


class T2bGoldenRegressionTest(unittest.TestCase):
    maxDiff = None
    _check = shared.GoldenRegressionTest._check

    def _solver(self, solver):
        for case in golden.CASES[solver]:
            with self.subTest(case=case):
                self._check(solver, case)

    def test_kinetics_ttt_cct_solver(self):
        self._solver("kinetics_ttt_cct_solver")

    def test_stochastic_uq_mmpds_solver(self):
        self._solver("stochastic_uq_mmpds_solver")

    def test_lpbf_fatigue_fracture(self):
        self._solver("lpbf_fatigue_fracture")

    def test_cases_are_registered(self):
        for solver in SOLVERS:
            self.assertIn(solver, golden.CASES)
            self.assertEqual(len(golden.CASES[solver]), 5, solver)
        self.assertEqual(golden.MODULE_DRIVERS["lpbf_fatigue_fracture"],
                         "tools/phase6a_fatigue_golden_driver.py")


class ProofBaselineTest(unittest.TestCase):
    """PROOF.md:1044 Seed42/N500 QMC baseline as recorded at d33b6f5 (with the norm_ppf sign
    error: normal draws had sigma 0.776), and the current expectation after the fix (same
    numbers as test_stochastic_uq_evidence)."""

    def test_seed42_n500_yield_baseline(self):
        doc = golden.load_golden("stochastic_uq_mmpds_solver", "seed42_n500_defaults_ni")
        stats = doc["stdout"]["stochasticProperties"]["yieldStrength_Rp02"]
        self.assertEqual(tuple(stats[k] for k in ("mean", "stdDev", "aBasisAllowable", "bBasisAllowable")),
                         (3467.7, 32.54, 3387.2, 3422.6))
        self.assertEqual(doc["stdout"]["sampleSizeN"], 500)

    def test_seed42_n500_yield_expectation_after_the_norm_ppf_fix(self):
        doc = golden.load_expected("stochastic_uq_mmpds_solver", "seed42_n500_defaults_ni")
        stats = doc["stdout"]["stochasticProperties"]["yieldStrength_Rp02"]
        self.assertEqual(tuple(stats[k] for k in ("mean", "stdDev", "aBasisAllowable", "bBasisAllowable")),
                         (3467.8, 41.37, 3365.4, 3410.5))


if __name__ == "__main__":
    unittest.main()
