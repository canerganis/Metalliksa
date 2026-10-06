"""Physics-audit regressions for python/stochastic_uq_mmpds_solver.py (EUQ-11; EUQ-4 is covered with the
scalar reference in test_stochastic_uq_vectorized_parity.py).

EUQ-11: the output 'hasoferLindBetaIndex' was Phi^-1(1 - Pf) from the sampled failure count, i.e. the
generalized reliability index (Ditlevsen 1979), not the Hasofer-Lind index (Hasofer & Lind 1974: minimum
distance to the limit-state surface in standard-normal space); Pf was computed at 1.5x the service stress
without saying so; and 0 or N failures were clamped to Pf = 1e-6 and reported as beta = +/-4.75.
"""

import unittest
from statistics import NormalDist

import stochastic_uq_mmpds_solver as solver


class GeneralizedReliabilityIndexTests(unittest.TestCase):
    def test_zero_failures_are_censored_not_4_75(self):
        old_beta = solver.norm_ppf(1.0 - max(1e-6, min(1.0 - 1e-6, 0.0)))
        self.assertEqual(round(old_beta, 2), 4.75)  # the former point value
        r = solver.generalized_reliability_index(0, 500)
        self.assertIsNone(r["beta"])
        self.assertEqual(r["status"], "censored_no_failures")
        self.assertEqual(r["bound"]["type"], "lower")
        self.assertAlmostEqual(r["bound"]["beta"], NormalDist().inv_cdf(1.0 - 3.0 / 500), places=12)
        self.assertAlmostEqual(round(r["bound"]["beta"], 2), 2.51)
        self.assertEqual(r["bound"]["pfUpper"], 0.006)

    def test_all_failures_are_censored(self):
        r = solver.generalized_reliability_index(600, 600)
        self.assertIsNone(r["beta"])
        self.assertEqual((r["status"], r["bound"]["type"], r["pf"]), ("censored_all_failures", "upper", 1.0))
        self.assertAlmostEqual(r["bound"]["beta"], NormalDist().inv_cdf(3.0 / 600), places=12)

    def test_estimate_between(self):
        r = solver.generalized_reliability_index(3, 777)
        self.assertEqual(r["status"], "estimated")
        self.assertAlmostEqual(r["beta"], NormalDist().inv_cdf(1.0 - 3 / 777), places=12)
        self.assertIsNone(r["bound"])

    def test_output_names_the_index_and_the_design_factor(self):
        out = solver.solve_stochastic_uq({"mcSamples": 500})
        rel = out["aerospaceReliability"]
        self.assertNotIn("hasoferLindBetaIndex", rel)
        self.assertNotIn("yieldFailureProbability_Pf", rel)
        self.assertEqual(rel["designFactor"], 1.5)
        self.assertIn("1.5", rel["limitState"])
        self.assertIn("not the Hasofer-Lind", rel["reliabilityIndexMethod"])
        # default IN718 run: no sampled point fails, so beta_G is a lower bound, not 4.75
        self.assertEqual((rel["failureCount"], rel["probabilityYieldBelowDesignStress_Pf"]), (0, 0.0))
        self.assertIsNone(rel["generalizedReliabilityIndex"])
        self.assertEqual(rel["generalizedReliabilityIndexBound"], {"type": "lower", "beta": 2.51, "pfUpper": 0.006})
        self.assertNotIn("pseudo-MC", out["sensitivityMetadata"]["method"])

    def test_estimated_case(self):
        rel = solver.solve_stochastic_uq({"mcSamples": 777, "seed": 99, "baseMetal": "Fe",
                                          "composition_wt": {"C": 0.4, "Cr": 0.8, "Mo": 0.25, "Ni": 1.8, "Mn": 0.7},
                                          "composition_tolerances": {"C": 0.03, "Cr": 0.1, "Mo": 0.05}}
                                         )["aerospaceReliability"]
        self.assertEqual(rel["failureCount"], 3)
        self.assertEqual(rel["generalizedReliabilityIndexStatus"], "estimated")
        self.assertEqual(rel["generalizedReliabilityIndex"], round(NormalDist().inv_cdf(1.0 - 3 / 777), 2))


if __name__ == "__main__":
    unittest.main()
