"""Goldak power normalization: half-space physics contract (not validation).

Goldak's double ellipsoid q = 6√3 f_i Q /(a_i b c π√π) exp(-3x²/a_i² - 3y²/b² - 3z²/c²)
with f_f + f_r = 2 integrates to Q over the half-space body z >= 0 (each lobe to
f_i Q / 2) and to 2Q over all z. The analytic Nguyen/Fachinotti field integrates the
even-in-z source over all z: that doubling is the image source that makes z = 0
adiabatic, so Q is the absorbed power and the far field tends to the Rosenthal point
source driven by the same power. goldak-total-power-v2 halved Q; v3 does not.
"""
import math
import unittest

import numpy as np

from goldak_solver import GoldakField, MODEL_ID, goldak_fractions, goldak_q_parameter_W, seed_goldak_axes
from lpbf_thermal_solver import rosenthal_temperature_C

K_TH, RHO, CP = 11.4, 8190.0, 435.0  # IN718 solid, as used by the screening paths
ALPHA = K_TH / (RHO * CP)


def _half_space_power(Q, af, ar, b, c, n=241):
    """Midpoint integral of q over z >= 0 (returns the full-space value too)."""
    ff, fr = goldak_fractions(af, ar)
    xs = np.linspace(-4 * ar, 4 * af, n)
    ys = np.linspace(-4 * b, 4 * b, n)
    zs = np.linspace(0.0, 4 * c, n)
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")
    A = np.where(X >= 0, af, ar)
    F = np.where(X >= 0, ff, fr)
    q = 6 * math.sqrt(3) * F * Q / (A * b * c * math.pi ** 1.5) * np.exp(-3 * X ** 2 / A ** 2 - 3 * Y ** 2 / b ** 2 - 3 * Z ** 2 / c ** 2)
    dv = (xs[1] - xs[0]) * (ys[1] - ys[0]) * (zs[1] - zs[0])
    half = float(q.sum() * dv)
    return half, 2.0 * half  # q is even in z


class GoldakPowerNormalization(unittest.TestCase):
    def test_model_id_is_the_half_space_kernel(self):
        self.assertEqual(MODEL_ID, "goldak-half-space-v3")

    def test_q_is_the_absorbed_power_not_half(self):
        self.assertEqual(goldak_q_parameter_W(100.0), 100.0)
        field = GoldakField(T0_C=25.0, Q_W=100.0, rho=8000.0, cp=500.0, alpha_th=1.0e-5,
                            af_m=40e-6, ar_m=80e-6, b_m=40e-6, c_m=40e-6)
        self.assertEqual(field.Q_W, 100.0)

    def test_lobes_integrate_to_q_over_the_half_space_and_2q_over_all_space(self):
        ff, fr = goldak_fractions(40e-6, 80e-6)
        self.assertAlmostEqual(ff, 2.0 / 3.0)
        self.assertAlmostEqual(fr, 4.0 / 3.0)
        # closed form: each lobe deposits f_i Q / 2 in z >= 0
        Q = 100.0
        self.assertAlmostEqual(ff * Q / 2 + fr * Q / 2, Q)
        half, full = _half_space_power(Q, 40e-6, 80e-6, 40e-6, 40e-6)
        self.assertAlmostEqual(half / Q, 1.0, delta=0.02, msg=f"half-space integral {half}")
        self.assertAlmostEqual(full / (2 * Q), 1.0, delta=0.02, msg=f"full-space integral {full}")

    def test_far_field_matches_rosenthal_point_source_with_the_same_power(self):
        P, v = 76.0, 0.8
        # Small axes: the source is nearly a point; agreement must hold already at 100 um.
        small = GoldakField(80.0, P, RHO, CP, ALPHA, 4e-6, 4e-6, 4e-6, 4e-6).bind_speed(v)
        for x in (-100e-6, -200e-6, -400e-6):
            ros = rosenthal_temperature_C(x, 0.0, 0.0, 80.0, P, K_TH, v, ALPHA, 0.0) - 80.0
            gk = small.temperature_C(x, 0.0, 0.0) - 80.0
            self.assertAlmostEqual(gk / ros, 1.0, delta=0.005, msg=f"x={x*1e6:g} um ratio {gk/ros}")
        # Seed axes (40/80/40/40 um): the ratio must rise monotonically towards 1.
        axes = seed_goldak_axes(40e-6)
        seeded = GoldakField(80.0, P, RHO, CP, ALPHA, **axes).bind_speed(v)
        ratios = []
        for x in (-300e-6, -600e-6, -1000e-6, -2000e-6):
            ros = rosenthal_temperature_C(x, 0.0, 0.0, 80.0, P, K_TH, v, ALPHA, 0.0) - 80.0
            ratios.append((seeded.temperature_C(x, 0.0, 0.0) - 80.0) / ros)
        self.assertEqual(ratios, sorted(ratios), f"ratio not monotone: {ratios}")
        self.assertAlmostEqual(ratios[-1], 1.0, delta=0.015, msg=f"2 mm ratio {ratios[-1]}")
        self.assertGreater(ratios[0], 0.9, f"0.3 mm ratio {ratios[0]} (v2 gave 0.47)")


if __name__ == "__main__":
    unittest.main()
