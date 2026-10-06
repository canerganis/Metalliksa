"""Goldak power normalization and time quadrature: half-space physics contract (not validation).

Goldak's double ellipsoid q = 6√3 f_i Q /(a_i b c π√π) exp(-3x²/a_i² - 3y²/b² - 3z²/c²)
with f_f + f_r = 2 integrates to Q over the half-space body z >= 0 (each lobe to
f_i Q / 2) and to 2Q over all z. The analytic Nguyen/Fachinotti field integrates the
even-in-z source over all z: that doubling is the image source that makes z = 0
adiabatic, so Q is the absorbed power and the far field tends to the Rosenthal point
source driven by the same power. goldak-total-power-v2 halved Q; v3 does not.

The quadrature references below come from an independent adaptive integration (SciPy
quad with wake-pulse breakpoints) of the same closed-form (x, y, z) integrand over tau;
IN718 solid properties, P = 100 W, beam-seeded axes (af = r0, ar = 2 r0, b = c = r0).
The v2 single Gauss-Legendre rule was off by -5.6 %..-100 % and +12..+20 % at these points.
"""
import math
import unittest

import numpy as np

from goldak_solver import GoldakField, MODEL_ID, goldak_fractions, goldak_q_parameter_W, seed_goldak_axes
from lpbf_thermal_solver import rosenthal_temperature_C

K_TH, RHO, CP = 11.4, 8190.0, 435.0  # IN718 solid, as used by the screening paths
ALPHA = K_TH / (RHO * CP)

# (v m/s, r0 m, x m, y m, z m) -> oracle ΔT (K) for P = 100 W.
QUADRATURE_REFERENCES = {
    (0.05, 40e-6, -300e-6, 0.0, 0.0): 4852.8749,
    (0.05, 40e-6, -1000e-6, 0.0, 0.0): 1412.0836,
    (0.05, 40e-6, -2000e-6, 0.0, 0.0): 701.9547,
    (0.2, 20e-6, -300e-6, 0.0, 0.0): 4728.5375,
    (0.2, 20e-6, -1000e-6, 0.0, 0.0): 1402.4401,
    (0.2, 20e-6, -500e-6, 20e-6, 10e-6): 2771.3080,
    (0.8, 80e-6, -1000e-6, 0.0, 0.0): 1262.3947,
    (0.8, 80e-6, -2000e-6, 0.0, 0.0): 662.7326,
    (1.5, 80e-6, -300e-6, 0.0, 0.0): 2680.1568,
    (1.5, 80e-6, -1000e-6, 0.0, 0.0): 1141.7971,
    (3.0, 40e-6, -100e-6, 0.0, 0.0): 6631.0798,
    (3.0, 40e-6, -300e-6, 0.0, 0.0): 3396.4864,
    (3.0, 40e-6, -2000e-6, 0.0, 0.0): 661.0923,
    (3.0, 80e-6, 0.0, 0.0, 0.0): 906.4847,
    (3.0, 80e-6, -300e-6, 0.0, 0.0): 1808.4907,
    (3.0, 80e-6, -1000e-6, 0.0, 0.0): 947.8265,
    # Beyond the 3 mm wake window the quadrature is widened on demand (never truncated to zero).
    (2.5, 80e-6, -4500e-6, 0.0, 0.0): 285.4812,
}


def _half_space_power(Q, af, ar, b, c, n=241):
    """Trapezoid integral of q over z >= 0 (half weight on the z = 0 plane); full-space value too."""
    ff, fr = goldak_fractions(af, ar)
    xs = np.linspace(-4 * ar, 4 * af, n)
    ys = np.linspace(-4 * b, 4 * b, n)
    zs = np.linspace(0.0, 4 * c, n)
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")
    A = np.where(X >= 0, af, ar)
    F = np.where(X >= 0, ff, fr)
    q = 6 * math.sqrt(3) * F * Q / (A * b * c * math.pi ** 1.5) * np.exp(-3 * X ** 2 / A ** 2 - 3 * Y ** 2 / b ** 2 - 3 * Z ** 2 / c ** 2)
    wz = np.ones(n)
    wz[0] = wz[-1] = 0.5
    dv = (xs[1] - xs[0]) * (ys[1] - ys[0]) * (zs[1] - zs[0])
    half = float((q * wz[None, None, :]).sum() * dv)
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
        Q = 100.0
        self.assertAlmostEqual(ff * Q / 2 + fr * Q / 2, Q)  # closed form: each lobe deposits f_i Q / 2 in z >= 0
        half, full = _half_space_power(Q, 40e-6, 80e-6, 40e-6, 40e-6)
        self.assertAlmostEqual(half / Q, 1.0, delta=0.001, msg=f"half-space integral {half}")
        self.assertAlmostEqual(full / (2 * Q), 1.0, delta=0.001, msg=f"full-space integral {full}")

    def test_far_field_matches_rosenthal_point_source_with_the_same_power(self):
        P, v = 76.0, 0.8
        small = GoldakField(80.0, P, RHO, CP, ALPHA, 4e-6, 4e-6, 4e-6, 4e-6).bind_speed(v)
        for x in (-100e-6, -200e-6, -400e-6):
            ros = rosenthal_temperature_C(x, 0.0, 0.0, 80.0, P, K_TH, v, ALPHA, 0.0) - 80.0
            gk = small.temperature_C(x, 0.0, 0.0) - 80.0
            self.assertAlmostEqual(gk / ros, 1.0, delta=0.005, msg=f"x={x*1e6:g} um ratio {gk/ros}")
        seeded = GoldakField(80.0, P, RHO, CP, ALPHA, **seed_goldak_axes(40e-6)).bind_speed(v)
        ratios = []
        for x in (-300e-6, -600e-6, -1000e-6, -2000e-6):
            ros = rosenthal_temperature_C(x, 0.0, 0.0, 80.0, P, K_TH, v, ALPHA, 0.0) - 80.0
            ratios.append((seeded.temperature_C(x, 0.0, 0.0) - 80.0) / ros)
        self.assertEqual(ratios, sorted(ratios), f"ratio not monotone: {ratios}")
        self.assertAlmostEqual(ratios[-1], 1.0, delta=0.015, msg=f"2 mm ratio {ratios[-1]}")
        self.assertGreater(ratios[0], 0.9, f"0.3 mm ratio {ratios[0]} (v2 gave 0.47)")

    def test_time_quadrature_matches_the_independent_oracle_across_speeds(self):
        fields = {}
        for (v, r0, x, y, z), ref in QUADRATURE_REFERENCES.items():
            field = fields.get((v, r0))
            if field is None:
                field = fields[(v, r0)] = GoldakField(0.0, 100.0, RHO, CP, ALPHA, **seed_goldak_axes(r0)).bind_speed(v)
            got = field.temperature_C(x, y, z)
            self.assertAlmostEqual(got / ref, 1.0, delta=1e-5,
                                   msg=f"v={v} r0={r0*1e6:g} um at ({x*1e6:g},{y*1e6:g},{z*1e6:g}) um: {got:.4f} vs {ref:.4f}")

    def test_wake_window_widens_instead_of_truncating(self):
        field = GoldakField(0.0, 100.0, RHO, CP, ALPHA, **seed_goldak_axes(80e-6)).bind_speed(2.5)
        self.assertEqual(field._wake_m, 3.0e-3)
        near = field.temperature_C(-1000e-6, 0.0, 0.0)
        far = field.temperature_C(-4500e-6, 0.0, 0.0)
        self.assertGreater(field._wake_m, 4.5e-3)
        self.assertAlmostEqual(far / 285.4812, 1.0, delta=1e-5)
        # Widening the window must not change the near-field value beyond quadrature noise.
        self.assertAlmostEqual(field.temperature_C(-1000e-6, 0.0, 0.0) / near, 1.0, delta=1e-6)

    def test_node_count_stays_bounded(self):
        for v, r0 in ((0.05, 40e-6), (0.8, 40e-6), (3.0, 10e-6), (3.0, 80e-6)):
            field = GoldakField(0.0, 100.0, RHO, CP, ALPHA, **seed_goldak_axes(r0)).bind_speed(v)
            self.assertLess(len(field._tau), 400, f"v={v} r0={r0*1e6:g} um: {len(field._tau)} nodes")


if __name__ == "__main__":
    unittest.main()
