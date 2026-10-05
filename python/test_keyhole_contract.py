"""Numerical/software checks on prescribed geometry, never experimental validation."""
import copy
import math
import unittest
import numpy as np
try:
    import warp as _warp_probe  # noqa: F401
except ImportError as _warp_exc:
    _WARP_MISSING = str(_warp_exc)
else:
    _WARP_MISSING = None

if _WARP_MISSING is not None:
    @unittest.skip("warp is not installed in this interpreter: " + str(_WARP_MISSING))
    class WarpUnavailable(unittest.TestCase):
        def test_warp_unavailable(self):
            pass
else:
    import warp as wp
    from lpbf_keyhole_raytracing import compute_keyhole_raytracing


    BASE = dict(nx=16, ny=16, dx=20e-6, dy=20e-6, num_rays=1024,
                seed=17, ui_ray_limit=8, device="cpu", max_bounces=4,
                power_W=250.0, beam_radius_um=50.0, keyhole_depth_um=0.0,
                base_absorption=0.3)


    class KeyholeContract(unittest.TestCase):
        def run_case(self, **updates):
            return compute_keyhole_raytracing({**BASE, **updates})

        def test_rejects_invalid_inputs_before_allocating(self):
            for key, value in [("nx", 1), ("ny", 1.5), ("num_rays", True),
                               ("num_rays", 1000001), ("max_bounces", 0),
                               ("max_bounces", 1000), ("dx", 0), ("dy", -1),
                               ("power_W", -1), ("power_W", float("inf")),
                               ("beam_radius_um", 0), ("base_absorption", 1.1),
                               ("base_absorption", float("nan")), ("seed", -1),
                               ("keyhole_depth_um", -1), ("device", "auto")]:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.run_case(**{key: value})
            for bad in (None, [], "bad"):
                with self.assertRaises(ValueError):
                    compute_keyhole_raytracing(bad)

        def test_flat_surface_absorbs_normal_incidence_fraction(self):
            result = self.run_case()
            self.assertAlmostEqual(result["total_absorbed_W"], 75.0, delta=1e-4)
            self.assertAlmostEqual(result["total_escaped_W"], 175.0, delta=1e-4)
            self.assertEqual(result["total_truncated_W"], 0.0)
            self.assertLess(result["energy_balance_relative_error"], 1e-6)
            self.assertEqual(result["device"], "cpu")
            vertices = np.array(result["mesh"]["vertices"]).reshape(16, 16, 3)
            np.testing.assert_allclose(np.diff(vertices[:, 0, 0]), 20e-6, rtol=1e-6)

        def test_reflection_and_bounce_budget_are_not_escaped_energy(self):
            result = self.run_case(max_bounces=1)
            self.assertEqual(result["total_escaped_W"], 0.0)
            self.assertAlmostEqual(result["total_truncated_W"], 175.0, delta=1e-4)
            self.assertAlmostEqual(sum(result[k] for k in
                ("total_absorbed_W", "total_escaped_W", "total_truncated_W")), 250, delta=1e-4)
            reflected = self.run_case(base_absorption=0)
            self.assertEqual(reflected["total_absorbed_W"], 0)
            self.assertAlmostEqual(reflected["total_escaped_W"], 250, delta=1e-4)
            self.assertEqual(self.run_case(base_absorption=1)["total_truncated_W"], 0)
            zero = self.run_case(power_W=0)
            self.assertEqual(zero["absorption_efficiency"], 0)
            self.assertEqual(zero["energy_balance_relative_error"], 0)

        def test_seed_reproduces_paths_without_mutating_global_rng(self):
            np.random.seed(101)
            before = copy.deepcopy(np.random.get_state())
            first = self.run_case(keyhole_depth_um=120)
            second = self.run_case(keyhole_depth_um=120)
            after = np.random.get_state()
            np.testing.assert_array_equal(before[1], after[1])
            self.assertEqual(before[2:], after[2:])
            self.assertEqual(first["ray_paths"], second["ray_paths"])
            self.assertEqual(first["total_absorbed_W"], second["total_absorbed_W"])
            self.assertNotEqual(first["ray_paths"], self.run_case(seed=18)["ray_paths"])
            self.assertEqual(first["total_absorbed_W"], self.run_case(keyhole_depth_um=120, ui_ray_limit=0)["total_absorbed_W"])
            self.assertEqual(first["sampling"]["seed"], 17)

        def test_gaussian_aperture_matches_independent_integral_at_three_sample_counts(self):
            # Square aperture [-30,30] um, Gaussian 1/e^2 radius 50 um.
            expected = 0.3 * math.erf(math.sqrt(2) * 30 / 50) ** 2
            for n in (1024, 4096, 16384):
                with self.subTest(n=n):
                    result = self.run_case(nx=7, ny=7, dx=10e-6, dy=10e-6, num_rays=n)
                    se = result["sampling"]["absorption_efficiency_standard_error"]
                    self.assertLess(abs(result["absorption_efficiency"] - expected), 5 * se + 1e-6)
                    self.assertGreater(se, 0)
                    self.assertLess(result["energy_balance_relative_error"], 1e-6)

        @unittest.skipUnless(wp.is_cuda_available(), "CUDA unavailable")
        def test_cpu_gpu_same_sample_comparison(self):
            cpu = self.run_case(keyhole_depth_um=120)
            gpu = self.run_case(keyhole_depth_um=120, device="cuda:0")
            for key in ("total_absorbed_W", "total_escaped_W", "total_truncated_W"):
                self.assertAlmostEqual(cpu[key], gpu[key], delta=0.025)


    if __name__ == "__main__":
        unittest.main()
