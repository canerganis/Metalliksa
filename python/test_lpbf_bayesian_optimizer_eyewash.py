import unittest
from unittest import mock

import lpbf_bayesian_optimizer as bo


class TestBayesianOptimizerHonesty(unittest.TestCase):
    def test_unknown_alloy_refused_not_in718(self):
        res = bo.run_bayesian_optimization("specimen-inconel-718", n_iter=2, n_warmup=1)
        self.assertFalse(res["success"])
        self.assertEqual(res["errorKind"], "validation")
        self.assertNotIn("iterations", res)

    def test_missing_alloy_refused(self):
        self.assertFalse(bo.run_bayesian_optimization(None, n_iter=2, n_warmup=1)["success"])

    def test_ti64_resolves_to_ti64(self):
        res = bo.run_bayesian_optimization("Ti64", n_iter=2, n_warmup=1)
        self.assertTrue(res["success"])
        self.assertEqual(res["alloyId"], "ti6al4v")
        self.assertEqual(res["beamDiameter_um"], 80.0)
        self.assertEqual(res["preheatTemp_C"], 80.0)

    def test_beam_and_preheat_reach_solver(self):
        import lpbf_thermal_solver as ts
        real = ts.calculate_meltpool_physics
        seen = []

        def spy(**kw):
            seen.append((kw["beam_diameter_um"], kw["preheat_temp_C"]))
            return real(**kw)

        with mock.patch.object(ts, "calculate_meltpool_physics", spy):
            res = bo.run_bayesian_optimization("in718", n_iter=1, n_warmup=1,
                                               beam_diameter_um=100, preheat_temp_C=200)
        self.assertTrue(res["success"])
        self.assertEqual(seen, [(100.0, 200.0)])

    def test_solver_error_propagates_not_scored_zero(self):
        import lpbf_thermal_solver as ts
        with mock.patch.object(ts, "calculate_meltpool_physics", side_effect=RuntimeError("boom")):
            res = bo.run_bayesian_optimization("in718", n_iter=2, n_warmup=1)
        self.assertFalse(res["success"])
        self.assertEqual(res["errorKind"], "solver")
        self.assertIn("boom", res["error"])
        self.assertNotIn("iterations", res)

    def test_iteration_cap_enforced_not_clamped(self):
        res = bo.run_bayesian_optimization("in718", n_iter=bo.MAX_ITERATIONS + 1, n_warmup=1)
        self.assertFalse(res["success"])
        self.assertIn(str(bo.MAX_ITERATIONS), res["error"])

    def test_iterations_report_verdicts(self):
        res = bo.run_bayesian_optimization("ss316l", n_iter=2, n_warmup=1)
        self.assertTrue(all(isinstance(i["verdict"], str) for i in res["iterations"]))


if __name__ == "__main__":
    unittest.main()
