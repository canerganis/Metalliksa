"""Independent discrete manufactured-solution check for CUDA pressure PCG."""

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

    from lpbf_transient_3d_gpu import launch_pressure_pcg


    SHAPE = (9, 9, 9)
    SPACING = (20.0e-6, 20.0e-6, 20.0e-6)
    DT_S = 2.0e-7
    RHO = 4420.0
    T_SOLIDUS_K = 1000.0
    RELATIVE_TOLERANCE = 1.0e-3


    def _apply_manufactured_pressure_operator(pressure, spacing):
        """Independent host assembly with closed sides and a zero-pressure free surface."""
        nx, ny, nz = pressure.shape
        dx, dy, dz = spacing
        result = np.zeros_like(pressure, dtype=np.float64)
        active = range(1, nx - 1), range(1, ny - 1), range(1, nz - 1)
        for i in active[0]:
            for j in active[1]:
                for k in active[2]:
                    diagonal = 0.0
                    neighbor_sum = 0.0
                    for di, dj, dk, h in (
                        (-1, 0, 0, dx), (1, 0, 0, dx),
                        (0, -1, 0, dy), (0, 1, 0, dy),
                        (0, 0, -1, dz), (0, 0, 1, dz),
                    ):
                        ni, nj, nk = i + di, j + dj, k + dk
                        if ni <= 0 or ni >= nx - 1 or nj <= 0 or nj >= ny - 1 or nk <= 0:
                            cell_class = 0
                        elif nk > nz - 2:
                            cell_class = 2  # free-surface air: pressure Dirichlet zero
                        elif nk >= nz - 1:
                            cell_class = 0
                        else:
                            cell_class = 1
                        if cell_class in (1, 2):
                            coefficient = 1.0 / (h * h)
                            diagonal += coefficient
                            if cell_class == 1:
                                neighbor_sum -= pressure[ni, nj, nk] * coefficient
                    result[i, j, k] = diagonal * pressure[i, j, k] + neighbor_sum
        return result


    def _wp_array(values, dtype=float):
        return wp.array(np.asarray(values), dtype=dtype, device="cuda:0")


    @unittest.skipUnless(wp.get_cuda_device_count() > 0, "Warp CUDA device unavailable")
    class Phase22CudaManufacturedPressure(unittest.TestCase):
        def test_cuda_pcg_recovers_discrete_manufactured_pressure(self):
            wp.config.use_precompiled_headers = False
            nx, ny, nz = SHAPE
            dx, dy, dz = SPACING
            i, j, k = np.indices(SHAPE, dtype=np.float64)
            exact = i * i + 2.0 * j * j + 3.0 * k * k
            active = np.zeros(SHAPE, dtype=bool)
            active[1:-1, 1:-1, 1:-1] = True
            exact[active] -= float(exact[active].mean())
            rhs = _apply_manufactured_pressure_operator(exact, SPACING)
            divergence = -(DT_S / RHO) * rhs
            temperature = np.full(SHAPE, T_SOLIDUS_K + 100.0)
            surface = np.full((nx, ny), (nz - 2) * dz)

            P = _wp_array(np.zeros(SHAPE))
            Div = _wp_array(divergence)
            Z_surf = _wp_array(surface)
            T = _wp_array(temperature)
            fields = [wp.zeros(SHAPE, dtype=float, device="cuda:0") for _ in range(4)]
            residual, preconditioned, direction, A_direction = fields
            scalars = [wp.zeros(1, dtype=float, device="cuda:0") for _ in range(9)]
            (rho_current, rho_next, rhs_norm2, residual_norm2, residual_next_norm2,
             scale_norm2, direction_dot_A, alpha, beta) = scalars
            status = wp.zeros(1, dtype=wp.int32, device="cuda:0")
            iterations = wp.zeros(1, dtype=wp.int32, device="cuda:0")

            launch_pressure_pcg(
                P, Div, Z_surf, T, SHAPE, SPACING, DT_S, RHO, T_SOLIDUS_K,
                residual, preconditioned, direction, A_direction,
                rho_current, rho_next, rhs_norm2, residual_norm2,
                residual_next_norm2, scale_norm2, direction_dot_A, alpha, beta,
                status, iterations, relative_tolerance=RELATIVE_TOLERANCE,
            )
            wp.synchronize_device("cuda:0")
            actual = P.numpy().astype(np.float64)
            status_code = int(status.numpy()[0])
            iteration_count = int(iterations.numpy()[0])
            linear_residual = float(np.sqrt(residual_norm2.numpy()[0] / scale_norm2.numpy()[0]))

            self.assertEqual(status_code, 1)
            self.assertGreater(iteration_count, 0)
            self.assertLessEqual(linear_residual, RELATIVE_TOLERANCE)
            gauge_error = actual[active] - exact[active]
            gauge_error -= gauge_error.mean()
            pressure_relative_l2 = float(np.linalg.norm(gauge_error) / np.linalg.norm(exact[active]))
            self.assertLessEqual(pressure_relative_l2, RELATIVE_TOLERANCE)
            independent_residual = _apply_manufactured_pressure_operator(actual, SPACING) - rhs
            relative_residual = float(
                np.linalg.norm(independent_residual[active]) / np.linalg.norm(rhs[active])
            )
            self.assertLessEqual(relative_residual, RELATIVE_TOLERANCE)


    if __name__ == "__main__":
        unittest.main()
