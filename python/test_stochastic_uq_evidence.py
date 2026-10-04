"""Regression checks for reported UQ evidence, not validation of material physics."""
import json
import math
import random
import unittest
from unittest.mock import patch

import stochastic_uq_mmpds_solver as solver


class SamplingEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qmc = solver.solve_stochastic_uq({'mcSamples': 500})
        # The pseudo-MC comparison arm was removed: the solver rejects samplingMethod='pseudo_mc'
        # (disabled upstream in f9ae3e4). No replacement baseline is invented; QMC assertions only.

    def test_single_run_does_not_invent_performance_or_effective_samples(self):
        for result in (self.qmc,):
            metadata = result['samplingMetadata']
            for key in ('qmcAccelerationFactor', 'effectiveSampleSize', 'varianceReductionRatio'):
                self.assertIsNone(metadata[key])
            self.assertEqual(metadata['discrepancySampleSize'], 150)
            self.assertEqual(result['sampleSizeN'], 500)
            self.assertNotIn('Certified', result['aerospaceReliability']['qualificationStatus'])

    def test_qmc_uncertainty_is_unavailable_without_replicates(self):
        for stats in self.qmc['stochasticProperties'].values():
            for key in ('aBasisConfidenceInterval95', 'bBasisConfidenceInterval95',
                        'allowableStandardError_A', 'allowableStandardError_B'):
                self.assertIsNone(stats[key])
            self.assertIn('replicates', stats['allowableUncertaintyMethod'])

    def test_material_distribution_baseline_preserved(self):
        # Seed 42 / 500 draws (QMC arm only; the pseudo-MC arm was removed together with the
        # removed solver option). Recorded after the norm_ppf sign fix: the earlier baseline
        # (3467.7, 32.54, 3387.2, 3422.6) was computed with normal draws of sigma 0.776 instead
        # of 1, so only the mean (centred on the nominal) survived; stdDev and A/B-basis moved.
        for result, expected in ((self.qmc, (3467.8, 41.37, 3365.4, 3410.5)),):
            stats = result['stochasticProperties']['yieldStrength_Rp02']
            self.assertEqual(tuple(stats[key] for key in ('mean', 'stdDev', 'aBasisAllowable', 'bBasisAllowable')), expected)

    def test_sensitivity_matches_actual_supplied_chemistry(self):
        original = solver.solve_single_realization
        seen = []
        def observe(*args, **kwargs):
            seen.append(set(kwargs['comp'] if kwargs else args[1]))
            return original(*args, **kwargs)
        with patch.object(solver, 'solve_single_realization', side_effect=observe):
            result = solver.solve_stochastic_uq({'mcSamples': 500, 'baseMetal': 'Al',
                'composition_wt': {'Si': 10.0, 'Mg': 0.3}, 'composition_tolerances': {'Si': 0.5, 'Mg': 0.1}})
        self.assertTrue(all(keys == {'Si', 'Mg'} for keys in seen))
        self.assertEqual(len(result['sobolSensitivityAnalysis']), 5)
        self.assertEqual(result['sensitivityMetadata']['evaluationCount'], 150 * 7)

    def test_raw_indices_are_not_clamped_or_normalized(self):
        rows = self.qmc['sobolSensitivityAnalysis']
        self.assertFalse(self.qmc['sensitivityMetadata']['indicesNormalized'])
        self.assertTrue(any(row['interactionIndex'] < 0 for row in rows))
        for row in rows:
            self.assertAlmostEqual(row['varianceContributionPct'], 100 * row['sobolFirstOrderIndex'], delta=0.1)
        self.assertNotAlmostEqual(sum(row['varianceContributionPct'] for row in rows), 100.0, delta=0.1)

    def test_constant_population_has_no_invented_sensitivity_or_cpk(self):
        result = solver.solve_stochastic_uq({'mcSamples': 500, 'composition_wt': {},
            'coolingRate_cov': 0, 'agingTemp_stdDev': 0, 'agingTime_stdDev': 0,
            'serviceStress_cov': 0, 'initialFlawSize_um_std': 0})
        self.assertEqual(result['sensitivityMetadata']['status'], 'unavailable_zero_variance')
        for row in result['sobolSensitivityAnalysis']:
            self.assertIsNone(row['sobolFirstOrderIndex'])
            self.assertIsNone(row['varianceContributionPct'])
        self.assertIsNone(result['stochasticProperties']['yieldStrength_Rp02']['cpk'])
        json.dumps(result, allow_nan=False)

    def test_sobol_dimensions_never_silently_repeat(self):
        with self.assertRaisesRegex(ValueError, '32 dimensions'):
            solver.SobolSequenceGenerator(33)

    def test_discrepancy_is_a_point_set_diagnostic(self):
        # One centered 1D point has centered L2 squared discrepancy 1/12.
        self.assertAlmostEqual(solver.compute_centered_l2_discrepancy([[0.5]]), math.sqrt(1 / 12), places=6)


class NormalQuantileTests(unittest.TestCase):
    """norm_ppf feeds every normal input (composition, process, stress, flaw, Saltelli)."""

    @staticmethod
    def _grid():
        # Uniform plus dense log-spaced tails over (1e-6, 1 - 1e-6).
        n = 20000
        uniform = [1e-6 + (1.0 - 2e-6) * i / n for i in range(n + 1)]
        tail = [10.0 ** (-6.0 + 5.0 * i / 2000) for i in range(2001)]
        return uniform + tail + [1.0 - p for p in tail]

    def test_matches_scipy_ndtri_over_the_grid(self):
        from scipy.special import ndtri  # independent oracle (scipy is in the CI lock)
        worst = max(abs(solver.norm_ppf(p) - float(ndtri(p))) for p in self._grid())
        self.assertLess(worst, 1e-9)

    def test_known_quantiles_and_symmetry(self):
        # The audit's counter-examples: p=0.10 gave -0.068 and p=0.30 gave -0.266.
        self.assertAlmostEqual(solver.norm_ppf(0.10), -1.2815515655446004, places=9)
        self.assertAlmostEqual(solver.norm_ppf(0.30), -0.5244005127080409, places=9)
        self.assertAlmostEqual(solver.norm_ppf(0.975), 1.959963984540054, places=9)
        self.assertEqual(solver.norm_ppf(0.5), 0.0)
        for p in (1e-6, 0.01, 0.1, 0.3, 0.45):
            self.assertAlmostEqual(solver.norm_ppf(p), -solver.norm_ppf(1.0 - p), places=9)
        self.assertEqual((solver.norm_ppf(0.0), solver.norm_ppf(1.0)), (-8.0, 8.0))

    def test_is_strictly_increasing(self):
        values = [solver.norm_ppf(p) for p in sorted(set(self._grid()))]
        self.assertTrue(all(b > a for a, b in zip(values, values[1:])))

    def test_inverse_of_norm_cdf(self):
        for p in (1e-6, 0.001, 0.1, 0.3, 0.5, 0.7, 0.9, 0.999, 1.0 - 1e-6):
            self.assertAlmostEqual(solver.norm_cdf(solver.norm_ppf(p)), p, places=9)

    def test_transformed_sobol_and_seeded_draws_are_standard_normal(self):
        # The sign error gave sigma = 0.776 for transformed Sobol draws.
        points = solver.SobolSequenceGenerator(dimension=4, scramble=True, seed=42).generate(4096)
        for dim in range(4):
            z = [solver.norm_ppf(point[dim]) for point in points]
            mean = sum(z) / len(z)
            std = math.sqrt(sum((v - mean) ** 2 for v in z) / (len(z) - 1))
            self.assertAlmostEqual(mean, 0.0, delta=5e-3, msg=f'dim {dim}')
            self.assertAlmostEqual(std, 1.0, delta=5e-3, msg=f'dim {dim}')
        rng = random.Random(42)
        z = [solver.norm_ppf(rng.random()) for _ in range(20000)]
        mean = sum(z) / len(z)
        std = math.sqrt(sum((v - mean) ** 2 for v in z) / (len(z) - 1))
        self.assertAlmostEqual(mean, 0.0, delta=0.03)
        self.assertAlmostEqual(std, 1.0, delta=0.03)


class SobolConvergenceTests(unittest.TestCase):
    """Sobol G-function (d=8, exact integral 1): the local Sobol QMC must converge and beat plain MC."""

    A = (0.0, 1.0, 4.5, 9.0, 99.0, 99.0, 99.0, 99.0)

    def _g(self, x):
        value = 1.0
        for xi, ai in zip(x, self.A):
            value *= (abs(4.0 * xi - 2.0) + ai) / (1.0 + ai)
        return value

    def _qmc_error(self, n):
        points = solver.SobolSequenceGenerator(dimension=8, scramble=True, seed=42).generate(n)
        return abs(sum(self._g(p) for p in points) / n - 1.0)

    def test_qmc_error_shrinks_and_beats_pseudo_random_mc(self):
        errors = {n: self._qmc_error(n) for n in (256, 4096, 16384)}
        self.assertLess(errors[16384], 1e-4)
        self.assertLess(errors[16384], errors[256] / 10.0)
        rng = random.Random(1)
        mc = abs(sum(self._g([rng.random() for _ in range(8)]) for _ in range(16384)) / 16384 - 1.0)
        self.assertLess(errors[16384], mc / 10.0)


if __name__ == '__main__':
    unittest.main()
