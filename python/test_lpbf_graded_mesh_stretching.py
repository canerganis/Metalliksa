"""Regression test for physics audit finding LT-5 (graded mesh boundary slivers).

The old outward growth loop cut the last cell to whatever span was left
(cur_dx = half_span - cur_x). For generate_graded_axis(100e-6, 20e-6, 2.5e-6, 25e-6)
that produced a 0.535 um boundary cell (below dx_fine = 2.5 um) and a 14.3x
neighbour jump against the stated growth ratio of 1.15; the 3D z axis ended
17.69 um -> 3.55 um. Standard stretched-grid practice (Ferziger & Peric,
Computational Methods for Fluid Dynamics, non-uniform grids) keeps adjacent
cell ratios near 1.1-1.3 and never below the fine spacing.

Self-contained: the old truncating loop is reproduced below as a fixture so the
original wrong numbers stay pinned next to the corrected behaviour.
"""

import unittest

import numpy as np

from lpbf_graded_mesh import generate_graded_axis, generate_graded_mesh_3d

TOL = 1e-9


def _old_truncating_half_widths(fine_len, total_len, dx_fine, dx_coarse, g):
    """Pre-fix algorithm (python/lpbf_graded_mesh.py at b0d77480), kept as a fixture."""
    n = max(1, int(round(fine_len / dx_fine)))
    dx = fine_len / n
    widths = [dx] * n
    cur_x, cur_dx = fine_len, dx
    while cur_x < total_len - 1e-12:
        cur_dx = min(cur_dx * g, dx_coarse)
        if cur_x + cur_dx > total_len:
            cur_dx = total_len - cur_x
        widths.append(cur_dx)
        cur_x += cur_dx
    return np.array(widths)


def _max_adjacent_ratio(w):
    w = np.asarray(w, dtype=float)
    return float(np.max(np.maximum(w[1:] / w[:-1], w[:-1] / w[1:])))


class TestGradedMeshStretchingLT5(unittest.TestCase):
    def test_old_loop_reproduces_audit_numbers(self):
        old = _old_truncating_half_widths(10e-6, 50e-6, 2.5e-6, 25e-6, 1.15)
        self.assertAlmostEqual(old.min() * 1e6, 0.5354, places=3)
        self.assertAlmostEqual(_max_adjacent_ratio(old), 14.28, places=2)
        old_z = _old_truncating_half_widths(30e-6, 150e-6, 2.5e-6, 25e-6, 1.15)
        self.assertAlmostEqual(old_z[-2] * 1e6, 17.69, places=2)
        self.assertAlmostEqual(old_z[-1] * 1e6, 3.55, places=2)

    def _assert_well_graded(self, widths, span, dx_fine, growth):
        widths = np.asarray(widths, dtype=float)
        self.assertAlmostEqual(float(widths.sum()), span, delta=span * 1e-12)
        self.assertGreaterEqual(float(widths.min()), dx_fine * (1.0 - TOL))
        self.assertLessEqual(_max_adjacent_ratio(widths), growth * (1.0 + TOL))

    def test_axis_100um_has_no_sliver(self):
        _, w, f = generate_graded_axis(100e-6, 20e-6, 2.5e-6, 25e-6)
        self._assert_well_graded(w, 100e-6, 2.5e-6, 1.15)
        # Was 0.535 um / 14.3x before the fix.
        self.assertGreater(float(w.min()) * 1e6, 2.49)
        self.assertLess(_max_adjacent_ratio(w), 1.15 + 1e-9)
        self.assertAlmostEqual(float(f[0]), -50e-6, delta=1e-18)
        self.assertAlmostEqual(float(f[-1]), 50e-6, delta=1e-18)

    def test_axis_spans_and_ratios(self):
        for span in (26e-6, 30e-6, 60e-6, 100e-6, 400e-6, 600e-6, 1000e-6):
            for growth in (1.05, 1.15, 1.3):
                with self.subTest(span=span, growth=growth):
                    _, w, _ = generate_graded_axis(span, 20e-6, 2.5e-6, 25e-6, growth)
                    self._assert_well_graded(w, span, 2.5e-6, growth)
                    self.assertLessEqual(float(w.max()), 25e-6 * (1.0 + TOL))

    def test_axis_400um_end_cell_no_longer_jumps(self):
        _, w, _ = generate_graded_axis(400e-6, 20e-6, 2.5e-6, 25e-6)
        # Old mesh ended [..., 25, 4.81] um, a 5.2x jump.
        self.assertLessEqual(_max_adjacent_ratio(w), 1.15 * (1.0 + TOL))

    def test_3d_z_axis_has_no_end_jump(self):
        mesh = generate_graded_mesh_3d(400e-6, 400e-6, 150e-6, 15e-6, 2.5e-6, 25e-6)
        wz = mesh["z"]["widths"]
        self._assert_well_graded(wz, 150e-6, 2.5e-6, 1.15)
        self.assertAlmostEqual(float(mesh["z"]["faces"][-1]), -150e-6, delta=1e-18)
        for axis in ("x", "y"):
            self._assert_well_graded(mesh[axis]["widths"], 400e-6, 2.5e-6, 1.15)


if __name__ == "__main__":
    unittest.main()
