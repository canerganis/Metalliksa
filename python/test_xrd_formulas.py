"""Analytic oracles for xrd_peak_deconvolution (Pearson-VII area, Williamson-Smallman
dislocation density, honest unavailable states, unclipped r_wp).

Synthetic inputs and closed-form / scipy.integrate references: numerical verification
only, not experimental validation.
"""
import math
import unittest
from unittest.mock import patch

import numpy as np
from scipy import integrate

import xrd_peak_deconvolution as xrd


def quad_area(profile, lo=-math.inf, hi=math.inf):
    value, _err = integrate.quad(profile, lo, hi, limit=400, epsabs=0.0, epsrel=1e-10)
    return value


class PearsonVIIAreaTests(unittest.TestCase):
    def test_area_matches_numerical_integral_of_the_profile(self):
        # Heavy-tailed shapes (m near 1) are integrated on the infinite line by scipy.
        for m in (0.8, 1.0, 1.5, 2.0, 5.0, 10.0):
            with self.subTest(m=m):
                intensity, fwhm = 3200.0, 0.27
                numeric = quad_area(lambda x: xrd.pearson_vii_profile(43.5 + x, 43.5, intensity, fwhm, m))
                analytic = xrd.pearson_vii_integrated_area(intensity, fwhm, m)
                self.assertAlmostEqual(analytic / numeric, 1.0, delta=2e-6)

    def test_closed_form_limits(self):
        intensity, fwhm = 1000.0, 0.3
        # m = 1: Lorentzian, area = pi * I * (fwhm / 2)
        self.assertAlmostEqual(xrd.pearson_vii_integrated_area(intensity, fwhm, 1.0),
                               math.pi * intensity * fwhm / 2.0, places=9)
        # m = 20 (the profile clamp): close to the Gaussian limit, I * fwhm * sqrt(pi / (4 ln 2)),
        # approached from the Pearson side as 1/m.
        gauss = intensity * fwhm * math.sqrt(math.pi / (4.0 * math.log(2.0)))
        self.assertLess(abs(xrd.pearson_vii_integrated_area(intensity, fwhm, 20.0) / gauss - 1.0), 0.03)

    def test_old_formula_was_off_by_the_audit_numbers(self):
        # audit: area off by +13 % (m=1), -27 % (m=2), -84 % (m=10) with I*w*sqrt(pi)/m
        for m, relative_error in ((1.0, 0.128), (2.0, -0.27), (10.0, -0.84)):
            with self.subTest(m=m):
                old = 1.0 * 1.0 * math.sqrt(math.pi) / m
                new = xrd.pearson_vii_integrated_area(1.0, 1.0, m)
                self.assertAlmostEqual(old / new - 1.0, relative_error, delta=0.01)

    def test_divergent_shape_is_unavailable_not_a_number(self):
        for m in (0.5, 0.3):
            self.assertIsNone(xrd.pearson_vii_integrated_area(1000.0, 0.25, m))

    def test_fitted_pearson_vii_roi_reports_the_analytic_area(self):
        true_c, true_i, true_w, true_m = 43.30, 4000.0, 0.20, 1.6
        tt = np.linspace(42.0, 45.0, 301)
        points = [{"twoTheta": float(x),
                   "sampleIntensity": float(200.0 + true_i * (1.0 + 4.0 * (2.0 ** (1.0 / true_m) - 1.0)
                                                              * ((x - true_c) / true_w) ** 2) ** -true_m)}
                  for x in tt]
        out = xrd.deconvolve_peak_roi(points, 43.25, 3500.0, 0.25, "pearson-vii", pearson_m=2.0, enable_ka2=False)
        ka1 = out["ka1Peak"]
        reference = quad_area(lambda x: xrd.pearson_vii_profile(x, 0.0, ka1["intensity"], ka1["fwhm_deg"],
                                                                ka1["shapeParameter"]))
        self.assertAlmostEqual(ka1["integratedArea"] / reference, 1.0, delta=2e-3)
        # and the noise-free truth itself (fit recovers the generating profile)
        truth = quad_area(lambda x: xrd.pearson_vii_profile(x, 0.0, true_i, true_w, true_m))
        self.assertAlmostEqual(ka1["integratedArea"] / truth, 1.0, delta=0.01)


class WilliamsonHallTests(unittest.TestCase):
    WAVELENGTH, K = 1.540598, 0.94

    def peaks(self, size_nm, strain, two_thetas=(38.0, 44.0, 64.0, 77.0, 82.0)):
        out = []
        for two_theta in two_thetas:
            theta = math.radians(two_theta / 2.0)
            beta = self.K * self.WAVELENGTH / (size_nm * 10.0) / math.cos(theta) + 4.0 * strain * math.tan(theta)
            out.append({"twoTheta": two_theta, "fwhm": math.degrees(beta), "instrumentalBroadening": 0.0})
        return out

    def test_dislocation_density_uses_the_rms_strain_under_the_gaussian_assumption(self):
        # rho = 2*sqrt(3) * <eps^2>^(1/2) / (D * b), SI units. The Williamson-Hall slope is the
        # apparent (Stokes-Wilson) strain e; rms = e / sqrt(2 ln 2) = 0.8493 e (Gaussian strain,
        # FWHM breadth). Hand value for D = 40 nm, e = 1.5e-3, b = 0.25 nm:
        # 2*1.7320508*(1.5e-3*0.8493218) / (40e-9 * 0.25e-9) = 4.4132e14 m^-2
        rms = 1.5e-3 / math.sqrt(2.0 * math.log(2.0))
        self.assertAlmostEqual(rms / (1.5e-3 * 0.8493218), 1.0, places=6)
        expected = 2.0 * math.sqrt(3.0) * rms / (40e-9 * 0.25e-9)
        self.assertAlmostEqual(expected / 4.4132e14, 1.0, delta=2e-5)
        result = xrd.solve_williamson_hall(self.peaks(40.0, 1.5e-3))
        self.assertAlmostEqual(result["crystalliteSize_nm"], 40.0, delta=0.01)
        self.assertAlmostEqual(result["microstrain_epsilon"], 1.5e-3, delta=1e-6)  # apparent strain kept
        self.assertAlmostEqual(result["microstrainRms_epsilon"], rms, delta=1e-6)
        self.assertAlmostEqual(result["dislocationDensity_m2"] / expected, 1.0, delta=1e-3)
        self.assertAlmostEqual(result["dislocationDensity_x10_14_m2"], 4.413, delta=0.005)
        self.assertEqual(result["microstrainStatus"], "resolved")
        self.assertEqual(result["crystalliteSizeStatus"], "resolved")
        self.assertEqual(result["dislocationDensityStatus"],
                         "computed-williamson-smallman-2sqrt3-rms-strain-gaussian-assumption")
        self.assertIn("apparent (Stokes-Wilson)", result["strainDefinition"])
        self.assertIn("Gaussian", result["strainDefinition"])
        self.assertEqual(result["williamsonHallStatus"], "ok")
        # rejected: the sqrt(3) factor (half), the 2*sqrt(3) on the apparent strain (+17.7 %)
        apparent_based = 2.0 * math.sqrt(3.0) * 1.5e-3 / (40e-9 * 0.25e-9)
        for wrong in (expected / 2.0, apparent_based):
            self.assertGreater(abs(result["dislocationDensity_m2"] / wrong - 1.0), 0.1)
        self.assertAlmostEqual(apparent_based / expected, 1.1774100, places=6)

    def test_instrumental_width_not_below_observed_is_excluded_not_invented(self):
        good = self.peaks(40.0, 1.5e-3)
        reference = xrd.solve_williamson_hall(good)
        # a peak whose observed width equals / is below the instrumental one (old code: 0.0316 deg)
        bad = [{"twoTheta": 51.0, "fwhm": 0.05, "instrumentalBroadening": 0.06},
               {"twoTheta": 90.0, "fwhm": 0.06, "instrumentalBroadening": 0.06}]
        mixed = xrd.solve_williamson_hall(good + bad)
        self.assertEqual(mixed["excludedPeakCount"], 2)
        rows = {row["twoTheta"]: row for row in mixed["whRegressionPoints"]}
        for two_theta in (51.0, 90.0):
            self.assertIsNone(rows[two_theta]["fwhm_phys_deg"])
            self.assertIsNone(rows[two_theta]["y_betaCosTheta"])
            self.assertEqual(rows[two_theta]["status"], "excluded-instrumental-width-not-below-observed")
        # the regression is exactly the one without the excluded peaks
        for key in ("slope", "intercept", "crystalliteSize_nm", "microstrain_epsilon", "dislocationDensity_m2"):
            self.assertEqual(mixed[key], reference[key], key)

    def test_fewer_than_two_resolvable_peaks_gives_unavailable_everything(self):
        peaks = self.peaks(40.0, 1.5e-3)[:1] + [{"twoTheta": 51.0, "fwhm": 0.05, "instrumentalBroadening": 0.06}]
        result = xrd.solve_williamson_hall(peaks)
        self.assertTrue(result["success"])
        self.assertEqual(result["williamsonHallStatus"], "unavailable-fewer-than-2-peaks-wider-than-instrumental")
        for key in ("crystalliteSize_nm", "microstrain_epsilon", "microstrainRms_epsilon",
                    "dislocationDensity_m2", "slope", "intercept", "rSquared"):
            self.assertIsNone(result[key], key)

    def test_nonpositive_slope_is_unavailable_not_clamped(self):
        # FWHM shrinking with 2theta: negative slope (no strain broadening resolved)
        peaks = [{"twoTheta": t, "fwhm": f, "instrumentalBroadening": 0.0}
                 for t, f in ((38.0, 0.30), (44.0, 0.29), (64.0, 0.27), (77.0, 0.26))]
        result = xrd.solve_williamson_hall(peaks)
        self.assertLess(result["slope"], 0.0)
        self.assertIsNone(result["microstrain_epsilon"])
        self.assertIsNone(result["microstrain_percent"])
        self.assertIsNone(result["dislocationDensity_m2"])
        self.assertIsNone(result["dislocationDensity_x10_14_m2"])
        self.assertEqual(result["microstrainStatus"], "unavailable-nonpositive-slope")
        self.assertEqual(result["dislocationDensityStatus"], "unavailable-needs-positive-slope-and-intercept")
        self.assertIsNotNone(result["crystalliteSize_nm"])  # the size is still resolved here

    def test_nonpositive_intercept_gives_no_size_and_no_dislocation_density(self):
        # pure strain broadening: beta cos(theta) = 4 eps sin(theta) exactly, intercept ~ 0;
        # a negative intercept (beta cos below the strain line at small angle) must not
        # be clamped to a huge size.
        peaks = []
        for two_theta in (38.0, 44.0, 64.0, 77.0):
            theta = math.radians(two_theta / 2.0)
            beta = (4.0 * 2e-3 * math.sin(theta) - 1e-3) / math.cos(theta)
            peaks.append({"twoTheta": two_theta, "fwhm": math.degrees(beta), "instrumentalBroadening": 0.0})
        result = xrd.solve_williamson_hall(peaks)
        self.assertLess(result["intercept"], 0.0)
        self.assertIsNone(result["crystalliteSize_nm"])
        self.assertIsNone(result["crystalliteSize_A"])
        self.assertEqual(result["crystalliteSizeStatus"], "unavailable-nonpositive-intercept")
        self.assertIsNone(result["dislocationDensity_m2"])
        self.assertGreater(result["microstrain_epsilon"], 0.0)


class RwpReportingTests(unittest.TestCase):
    def noisy_points(self, noise_sd):
        rng = np.random.RandomState(20261004)
        tt = np.linspace(42.0, 45.0, 121)
        peak = 150.0 / (1.0 + ((tt - 43.5) / 0.1) ** 2)
        y = 100.0 + peak + rng.normal(0.0, noise_sd, tt.size)
        return [{"twoTheta": float(a), "sampleIntensity": float(b)} for a, b in zip(tt, y)]

    def test_poor_fit_is_reported_above_the_old_15_percent_cap(self):
        out = xrd.deconvolve_peak_roi(self.noisy_points(90.0), 43.5, 150.0, 0.2, enable_ka2=False)
        reported = out["goodnessOfFit"]["r_wp_pct"]
        # independent recomputation from the returned profile (rounded to 0.01 per point)
        resid = np.array([p["residual"] for p in out["deconvolutionProfile"]])
        raw = np.array([p["rawIntensity"] for p in out["deconvolutionProfile"]])
        independent = 100.0 * math.sqrt(float(resid @ resid) / float(raw @ raw))
        self.assertGreater(independent, 30.0)  # far above the former cap
        self.assertAlmostEqual(reported, independent, delta=0.05)
        self.assertTrue(out["fitDiagnostics"]["poorFit"])
        self.assertEqual(out["fitDiagnostics"]["rWpPoorFitThresholdPct"], 15.0)

    def test_non_converged_fit_is_flagged_even_with_a_small_residual(self):
        original = xrd._fit_profile_least_squares

        def not_converged(*args, **kwargs):
            solution, info = original(*args, **kwargs)
            return solution, dict(info, status=0)  # scipy status 0 = evaluation budget exhausted

        with patch.object(xrd, "_fit_profile_least_squares", not_converged):
            out = xrd.deconvolve_peak_roi(self.noisy_points(1.0), 43.5, 150.0, 0.2, enable_ka2=False)
        self.assertLess(out["goodnessOfFit"]["r_wp_pct"], 2.0)
        self.assertEqual(out["fitDiagnostics"]["status"], 0)
        self.assertTrue(out["fitDiagnostics"]["poorFit"])

    def test_r_wp_has_no_denominator_clamp(self):
        # intensities far below 1 count: sum(y^2) << 1, where the old max(1.0, .) understated r_wp
        rng = np.random.RandomState(7)
        tt = np.linspace(42.0, 45.0, 121)
        y = 0.01 + 0.03 / (1.0 + ((tt - 43.5) / 0.1) ** 2) + rng.normal(0.0, 0.002, tt.size)
        points = [{"twoTheta": float(a), "sampleIntensity": float(b)} for a, b in zip(tt, y)]
        original = xrd._fit_profile_least_squares
        captured = {}

        def spy(*args, **kwargs):
            captured["x"], info = original(*args, **kwargs)
            return captured["x"], info

        with patch.object(xrd, "_fit_profile_least_squares", spy):
            out = xrd.deconvolve_peak_roi(points, 43.5, 0.03, 0.2, enable_ka2=False)
        self.assertTrue(out["fitDiagnostics"]["accepted"])
        c1, i1, w1, shape, b0, b1 = captured["x"]
        model = b0 + b1 * tt + xrd._profile_array(tt, c1, i1, w1, shape, "pseudo-voigt")
        sse = float(np.sum((y - model) ** 2))
        self.assertLess(float(y @ y), 0.5)
        independent = 100.0 * math.sqrt(sse / float(y @ y))
        self.assertAlmostEqual(out["goodnessOfFit"]["r_wp_pct"], independent, delta=0.01)
        clamped = 100.0 * math.sqrt(sse / 1.0)
        self.assertGreater(independent / clamped, 2.0)  # the old clamp understated it more than 2x

    def test_all_zero_intensities_give_unavailable_r_wp(self):
        tt = np.linspace(42.0, 45.0, 21)
        points = [{"twoTheta": float(a), "sampleIntensity": 0.0} for a in tt]
        out = xrd.deconvolve_peak_roi(points, 43.5, 10.0, 0.2, enable_ka2=False)
        self.assertIsNone(out["goodnessOfFit"]["r_wp_pct"])
        self.assertTrue(out["fitDiagnostics"]["poorFit"])

    def test_good_fit_is_not_flagged(self):
        out = xrd.deconvolve_peak_roi(self.noisy_points(1.0), 43.5, 150.0, 0.2, enable_ka2=False)
        self.assertLess(out["goodnessOfFit"]["r_wp_pct"], 2.0)
        self.assertFalse(out["fitDiagnostics"]["poorFit"])


if __name__ == "__main__":
    unittest.main()
