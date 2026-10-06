"""Wave B LT-1: the Warp Rosenthal slice uses the CPU sampler's row-major [ia][ib] layout.

sample_thermal_slice (lpbf_thermal_solver.py) loops axis a outermost, so element ia*nb+ib is
(a_ia, b_ib); the frontend reads T_C[ia*nz + iz] (meltPool3DGeometry.ts). The Warp kernel used
(tid % na, tid // na), which transposes the slice whenever na != nb. The index-contract test runs
everywhere; the element-wise CPU comparison needs Warp with a CUDA device.
"""

import math
import unittest

from lpbf_thermal_solver import rosenthal_temperature_C, sample_thermal_slice

try:
    import warp as _wp  # noqa: F401
    _wp.init()
    _CUDA = _wp.get_cuda_device_count() > 0
except Exception:  # noqa: BLE001 - any import/init failure means "no GPU path here"
    _CUDA = False


def _kernel_indices(tid, na, nb):
    """The index math of warp_thermal_solver.rosenthal_slice_kernel after LT-1."""
    return tid // nb, tid % nb


class IndexContract(unittest.TestCase):
    def test_index_contract_without_gpu(self):
        na, nb = 7, 4
        axis_a, axis_b = (0.0, 6.0), (0.0, 3.0)
        cpu = sample_thermal_slice(lambda a, b: 10.0 * a + b, axis_a, axis_b, na, nb)
        self.assertEqual(len(cpu), na * nb)
        for tid in range(na * nb):
            ia, ib = _kernel_indices(tid, na, nb)
            a = axis_a[0] + (axis_a[1] - axis_a[0]) * ia / (na - 1)
            b = axis_b[0] + (axis_b[1] - axis_b[0]) * ib / (nb - 1)
            self.assertEqual(cpu[tid], round(10.0 * a + b, 1))

    def test_kernel_source_uses_row_major_indices(self):
        import pathlib
        source = (pathlib.Path(__file__).with_name("warp_thermal_solver.py")).read_text(encoding="utf-8")
        self.assertIn("i = tid // nb", source)
        self.assertIn("j = tid % nb", source)
        self.assertNotIn("tid % nx", source)


@unittest.skipUnless(_CUDA, "Warp with a CUDA device is required for the element-wise slice comparison")
class WarpMatchesCpuSampler(unittest.TestCase):
    def test_layout_matches_cpu_sampler(self):
        from warp_thermal_solver import compute_rosenthal_slice_warp
        T0, P, k, v, alpha, r_reg = 80.0, 180.0, 25.0, 0.94, 5.5e-6, 28e-6
        na, nb = 36, 24
        a_span, b_span = (-300e-6, 120e-6), (0.0, 160e-6)
        for plane in (1, 2):
            with self.subTest(plane=plane):
                plane_val = 0.0
                warp_vals = compute_rosenthal_slice_warp(a_span, b_span, na, nb, plane, plane_val,
                                                         T0, P, k, v, alpha, r_reg)
                if plane == 1:
                    def f(a, b):
                        return rosenthal_temperature_C(a, plane_val, b, T0, P, k, v, alpha, r_reg)
                else:
                    def f(a, b):
                        return rosenthal_temperature_C(plane_val, a, b, T0, P, k, v, alpha, r_reg)
                cpu_vals = sample_thermal_slice(f, a_span, b_span, na, nb)
                self.assertEqual(len(warp_vals), len(cpu_vals))
                # float32 kernel against float64 CPU (both rounded to 0.1 C): rounding only. A transposed
                # layout differs by thousands of degrees.
                worst = max(abs(w - c) - 1e-4 * abs(c) for w, c in zip(warp_vals, cpu_vals))
                self.assertLessEqual(worst, 0.5)
                # First column of the slice (fixed a, increasing depth) must fall with depth as on the CPU.
                column = warp_vals[0:4]
                self.assertTrue(all(math.isfinite(t) for t in column))
                self.assertEqual(sorted(column, reverse=True), column)


if __name__ == "__main__":
    unittest.main()
