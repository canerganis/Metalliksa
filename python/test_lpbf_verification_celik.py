"""Wave B LT-2 (Celik et al. 2008 three-grid check) and LT-3 (single-mesh G/R/Tdot label).

Celik, Ghia, Roache & Freitas, J. Fluids Eng. 130(7) (2008) 078001: Step 2 asks for a refinement
factor r = h_coarse/h_fine > 1.3; Eq. 3a-c give the apparent order p for unequal ratios by
fixed-point iteration; Eq. 7 gives GCI_fine = 1.25 e_a21 / (r21^p - 1). Table 1 supplies the
reference vectors used below. Self-contained: the study tests run the 10 W, 40 um reference case.
"""

import math
import unittest
from unittest.mock import patch

import lpbf_simulation
from lpbf_simulation import _layer_aligned_mesh_levels, run, BOUNDS
from lpbf_verification import CELIK_MIN_REFINEMENT_RATIO, convergence

CASE = dict(mode="standard", backend="reference", power_W=40, mesh_um=40, trackLength_um=200,
            cooling_s=.0001, dwell_s=0)


def _h(cells):
    """Representative 2-D spacing h = N^-1/2 (Celik Eq. 1 with unit area)."""
    return cells ** -0.5


class CelikTable1(unittest.TestCase):
    def test_column_1_reattachment_length(self):
        # N 18000/8000/4500 -> r21 1.5, r32 1.333; Celik: p 1.53, GCI_fine 2.2 %.
        out = convergence([5.863, 5.972, 6.063], [_h(4500), _h(8000), _h(18000)])
        self.assertEqual(out["status"], "numerically-converging")
        self.assertAlmostEqual(out["observedOrder"], 1.53, delta=0.01)
        self.assertAlmostEqual(out["fineGCI_pct"], 2.2, delta=0.1)
        self.assertAlmostEqual(out["refinementRatios"][1], 1.5, places=6)

    def test_column_2_velocity_p_below_one(self):
        # N 18000/4500/980 -> r21 2.0, r32 2.143; Celik: p 0.75, GCI_fine 1.1 %.
        out = convergence([10.6050, 10.7250, 10.7880], [_h(980), _h(4500), _h(18000)])
        self.assertEqual(out["status"], "numerically-converging")
        self.assertAlmostEqual(out["observedOrder"], 0.75, delta=0.01)
        self.assertAlmostEqual(out["fineGCI_pct"], 1.1, delta=0.1)

    def test_column_3_oscillatory_is_inconclusive(self):
        out = convergence([6.0909, 5.9624, 6.0042], [_h(980), _h(4500), _h(18000)])
        self.assertEqual(out["status"], "inconclusive")
        self.assertTrue(out["oscillatory"])
        self.assertIn("oscillatory", out["reason"])


class CelikIdentities(unittest.TestCase):
    def test_constant_ratio_reduces_to_closed_form(self):
        values, spacings = [120.0, 105.0, 101.25], [4.0, 2.0, 1.0]
        out = convergence(values, spacings)
        a, b = values[0] - values[1], values[1] - values[2]
        self.assertAlmostEqual(out["observedOrder"], math.log(abs(a / b)) / math.log(2.0), places=9)
        self.assertAlmostEqual(convergence([1.16, 1.04, 1.01], [.4, .2, .1])["observedOrder"], 2.0, places=9)

    def test_synthetic_order_on_unequal_spacings(self):
        spacings = [40.0, 20.0, 40.0 / 3.0]
        values = [1.0 + h ** 1.7 for h in spacings]
        out = convergence(values, spacings)
        self.assertEqual(out["status"], "numerically-converging")
        self.assertAlmostEqual(out["observedOrder"], 1.7, delta=1e-6)

    def test_ratio_below_1p3_is_inconclusive(self):
        out = convergence([1.0 + 0.8 ** 2, 1.0 + 0.7 ** 2, 1.0 + 0.2 ** 2], [0.8, 0.7, 0.2])
        self.assertEqual(out["status"], "inconclusive")
        self.assertIn(f"Refinement ratio below {CELIK_MIN_REFINEMENT_RATIO}", out["reason"])

    def test_none_and_non_numeric_values_are_inconclusive(self):
        for values in ([None, 1.0, 1.0], [1.0, float("nan"), 1.0], [True, 1.0, 2.0], [1.0, "2", 3.0]):
            with self.subTest(values=values):
                self.assertEqual(convergence(values, [4.0, 2.0, 1.0])["status"], "inconclusive")

    def test_diverging_trend_is_inconclusive(self):
        out = convergence([1.0 + 0.1 * h ** -0.5 for h in (4.0, 2.0, 1.0)], [4.0, 2.0, 1.0])
        self.assertEqual(out["status"], "inconclusive")


class LayerAlignedMeshPlan(unittest.TestCase):
    def test_plan_contains_request_and_meets_the_ratio(self):
        for layer in range(15, 151, 5):
            for mesh in range(5, 81, 5):
                p = {"layer_um": float(layer), "mesh_um": float(mesh)}
                plan = _layer_aligned_mesh_levels(p)
                n = max(1, int(math.ceil(layer / mesh - 1e-12)))
                max_cells = int(math.floor(layer / BOUNDS["mesh_um"][0] + 1e-12))
                with self.subTest(layer=layer, mesh=mesh):
                    if plan is None:
                        self.assertLess(max_cells, 3)
                        continue
                    cells = [c for c, _ in plan]
                    self.assertIn(n, cells)
                    self.assertEqual(cells, sorted(cells))
                    self.assertLessEqual(cells[-1], max_cells)
                    for coarse, fine in zip(cells, cells[1:]):
                        self.assertGreaterEqual(fine / coarse, CELIK_MIN_REFINEMENT_RATIO - 1e-12)

    def test_40_over_20_gives_one_two_three(self):
        plan = _layer_aligned_mesh_levels({"layer_um": 40.0, "mesh_um": 20.0})
        self.assertEqual([c for c, _ in plan], [1, 2, 3])


class TimestepStudyRefinesBelowRealisedStep(unittest.TestCase):
    def test_medium_and_fine_cap_dt_below_the_realised_mean(self):
        real = lpbf_simulation.transient
        requested = []

        def recording(p, m, *args, **kwargs):
            requested.append(p["maxDt_s"])
            return real(p, m, *args, **kwargs)

        with patch.object(lpbf_simulation, "transient", recording):
            r = run({**CASE, "power_W": 10, "study": "timestep"})
        self.assertEqual(len(requested), 3)
        mean_dt = r["convergenceStudy"]["results"][0]["discretization"]["meanDt_s"] \
            if isinstance(r["convergenceStudy"]["results"][0], dict) and "discretization" in r["convergenceStudy"]["results"][0] \
            else None
        base = r["discretization"]["meanDt_s"] if mean_dt is None else mean_dt
        self.assertAlmostEqual(requested[1], max(BOUNDS["maxDt_s"][0], base / math.sqrt(2.0)), delta=1e-18)
        self.assertAlmostEqual(requested[2], max(BOUNDS["maxDt_s"][0], base / 2.0), delta=1e-18)
        checks = r["convergenceStudy"]["checks"]
        for key in ("thermalGradient_K_m", "solidificationRate_m_s", "coolingRate_K_s"):
            self.assertIn(key, checks)
            self.assertIn(checks[key]["status"], ("inconclusive", "numerically-converging", "failed"))


class SolidificationResolutionLT3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cold = run({**CASE, "power_W": 10})
        cls.hot = run({**CASE, "power_W": 60})

    def test_label_present_and_never_mesh_verified(self):
        for r in (self.cold, self.hot):
            res = r["numericalDiagnostics"]["solidificationResolution"]
            self.assertEqual(res["methodId"], "melt-pool-cell-count-v1")
            self.assertFalse(res["meshVerified"])
            self.assertEqual(res["gradientStencilCells"], 2)
            self.assertIn(res["status"], ("not-available", "stencil-spans-melt-pool", "single-mesh-unverified"))

    def test_status_follows_cell_count(self):
        for r in (self.cold, self.hot):
            res = r["numericalDiagnostics"]["solidificationResolution"]
            if r["metrics"].get("thermalGradient_K_m") is None:
                self.assertEqual(res["status"], "not-available")
            elif min(res["cellsAcrossWidth"], res["cellsAcrossDepth"]) < 2:
                self.assertEqual(res["status"], "stencil-spans-melt-pool")
            else:
                self.assertEqual(res["status"], "single-mesh-unverified")
            self.assertAlmostEqual(res["mesh_um"], 40.0, places=6)


if __name__ == "__main__":
    unittest.main()
