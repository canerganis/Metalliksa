"""Analytic fixtures: numerical verification, not experimental validation."""
import math
import unittest
from unittest.mock import patch

import cnls_fitting_solver as solver


def parameter(name, value, lower=1e-9, upper=1e5, fixed=False):
    return dict(paramName=name, elementId=name, field="value", value=value,
                min=lower, max=upper, isFixed=fixed, paramType="Resistor", unit="Ohm")


RESISTOR = {"branches": [{"connection": "series", "elements": [
    {"id": "R", "name": "R", "type": "R", "value": 2.0}]}]}


def resistor_points():
    return [dict(frequency=10.0 ** (i / 4), zReal=20.0, minusZImag=0.0) for i in range(20)]


class CNLSNumericsTests(unittest.TestCase):
    def test_frontend_bounds_are_respected(self):
        p = parameter("R", 2)
        del p["min"], p["max"]
        p.update(lowerBound=1, upperBound=3)
        report = solver.run_cnls_fit(RESISTOR, resistor_points(), [p])
        self.assertLessEqual(report["parameters"][0]["fittedValue"], 3)
        self.assertIsNone(report["parameters"][0]["stdError"])

    def test_global_fit_has_local_reproducible_rng(self):
        import random
        state = random.getstate()
        kwargs = dict(max_generations=3, pop_size=10, polish_lm=False, seed=27)
        first = solver.run_global_auto_fit(RESISTOR, resistor_points(), [parameter("R", 2)], **kwargs)
        second = solver.run_global_auto_fit(RESISTOR, resistor_points(), [parameter("R", 2)], **kwargs)
        self.assertEqual(first["globalDeChiSquare"], second["globalDeChiSquare"])
        self.assertEqual(first["parameters"], second["parameters"])
        self.assertEqual(first["randomSeed"], 27)
        self.assertEqual(random.getstate(), state)
        self.assertFalse(first["converged"])

    def test_fixed_model_is_evaluated_instead_of_declared_perfect(self):
        report = solver.run_cnls_fit(RESISTOR, resistor_points(), [parameter("R", 2, fixed=True)])
        self.assertGreater(report["reducedChiSquare"], 0.1)
        self.assertEqual(len(report["residuals"]), 20)
        self.assertEqual(report["parameters"][0]["fittedValue"], 2)
        self.assertFalse(report["converged"])
        self.assertEqual(report["terminationReason"], "no_adjustable_parameters")

    def test_zero_iterations_evaluates_without_claiming_convergence(self):
        report = solver.run_cnls_fit(RESISTOR, resistor_points(), [parameter("R", 2)], max_iter=0)
        self.assertEqual(report["iterations"], 0)
        self.assertFalse(report["converged"])
        self.assertGreater(report["reducedChiSquare"], 0.1)
        self.assertIsNone(report["parameters"][0]["stdError"])
        self.assertIsNone(report["rSquared"])

    def test_negative_r_squared_is_not_clipped(self):
        points = [dict(frequency=i+1, zReal=i+1, minusZImag=0) for i in range(10)]
        report = solver.run_cnls_fit(RESISTOR, points, [parameter("R", 100, fixed=True)], "unit")
        self.assertLess(report["rSquared"], 0)

    def test_rank_deficient_parameters_have_no_invented_certainty(self):
        topology = {"branches": [{"connection": "series", "elements": [
            {"id": name, "name": name, "type": "R", "value": 2} for name in ("R1", "R2")]}]}
        report = solver.run_cnls_fit(topology, resistor_points(), [parameter("R1", 2), parameter("R2", 2)])
        self.assertIsNone(report["parameters"][0]["stdError"])
        self.assertIsNone(report["parameters"][1]["percentError"])

    def test_invalid_data_and_options_are_rejected(self):
        for points, options in [([], {}), ([dict(frequency=0, zReal=1, minusZImag=0)], {}),
                                ([dict(frequency=1, zReal=float("nan"), minusZImag=0)], {}),
                                (resistor_points(), {"max_iter": -1}),
                                (resistor_points(), {"weighting": "typo"})]:
            with self.subTest(points=points, options=options), self.assertRaises(ValueError):
                solver.run_cnls_fit(RESISTOR, points, [parameter("R", 2)], **options)

    def test_short_lin_kk_is_unavailable(self):
        report = solver.perform_lin_kk_stationarity_test(resistor_points()[:4])
        self.assertEqual(report["status"], "unavailable")
        self.assertIsNone(report["isStationary"])
        self.assertIsNone(report["driftScore"])
        self.assertIsNone(report["kkChiSquare"])

    def test_voigt_screen_does_not_identify_time_domain_stationarity(self):
        report = solver.perform_lin_kk_stationarity_test(resistor_points())
        self.assertIsNone(report["isStationary"])
        self.assertIsNone(report["driftScore"])
        self.assertNotIn("Compliant", report["stationarityStatus"])

    def test_fitting_does_not_certify_kk_or_astm(self):
        report = solver.run_cnls_fit(RESISTOR, resistor_points(), [parameter("R", 20)])
        self.assertTrue(report["converged"])
        self.assertIsNone(report["kramersKronig"]["isValid"])
        self.assertIsNone(report["astmG106"]["isAstmG106Compliant"])

    def test_resistor_moves_toward_known_value(self):
        # Phase 6b removed the scalar residual path: the fit is NumPy-only, and the
        # HAS_NUMPY flag (kept for the disabled DE auto-fit) does not select a backend.
        report = solver.run_cnls_fit(RESISTOR, resistor_points(), [parameter("R", 2)], "unit")
        self.assertAlmostEqual(report["parameters"][0]["fittedValue"], 20, delta=1e-6)
        self.assertLess(report["reducedChiSquare"], 1e-12)

    def test_fit_without_numpy_is_a_clear_runtime_error(self):
        with patch.object(solver, "np", None), self.assertRaisesRegex(RuntimeError, "requires NumPy"):
            solver.run_cnls_fit(RESISTOR, resistor_points(), [parameter("R", 2)], "unit")
        with patch.object(solver, "np", None), self.assertRaisesRegex(RuntimeError, "requires NumPy"):
            solver.perform_lin_kk_stationarity_test(resistor_points())

    def test_randles_recovers_three_known_parameters(self):
        # Independent closed form: Rs + Rct / (1 + j*w*Rct*Cdl).
        points = []
        for i in range(60):
            f = 10 ** (-1 + 6 * i / 59)
            z = 5 + 120 / (1 + 1j * 2 * math.pi * f * 120 * 2e-5)
            points.append(dict(frequency=f, zReal=z.real, minusZImag=-z.imag))
        params = [parameter("Rs", 12), parameter("Rct", 60), parameter("Cdl", 7e-5, 1e-9, 0.1)]
        report = solver.run_cnls_fit("standard_randles", points, params, "modulus", max_iter=150)
        for p, expected in zip(report["parameters"], (5, 120, 2e-5)):
            self.assertAlmostEqual(p["fittedValue"] / expected, 1, delta=1e-5)
        self.assertLess(report["reducedChiSquare"], 1e-12)


if __name__ == "__main__":
    unittest.main(verbosity=2)
