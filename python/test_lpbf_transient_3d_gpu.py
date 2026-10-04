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

    from lpbf_transient_3d_gpu import (
        _PRESSURE_PCG_MAX_ITERATIONS,
        _PRESSURE_STATUS_BUDGET_EXHAUSTED,
        _PRESSURE_STATUS_CONVERGED,
        _PRESSURE_STATUS_NUMERICAL_FAILURE,
        _PRESSURE_RELATIVE_DIVERGENCE_TOLERANCE,
        TransientEnthalpy3DGPU,
        _PHASE22_MAX_COMPONENT_SPEED_M_S,
        _PHASE22_MOMENTUM_CFL_LIMIT,
        _phase22_stable_step_size,
        _surface_liquid_mask,
        _step_count,
        _step_size,
        _average_transverse_face_component,
        compute_divergence_kernel,
        enthalpy_3d_nonlinear_step_kernel,
        free_surface_kinematics_kernel,
        phase22_energy_ledger_step_kernel,
        phase22_reconcile_surface_mask_kernel,
        launch_pressure_pcg,
        pressure_jacobi_kernel,
        project_velocity_kernel,
        validate_projected_momentum_cfl_kernel,
        velocity_advection_forces_kernel,
    )
    from phase22_legacy_test_material import LEGACY_SOLVER_TEST_MATERIAL


    @wp.kernel
    def _probe_transverse_interpolants(
        U: wp.array3d(dtype=float), V: wp.array3d(dtype=float), W: wp.array3d(dtype=float),
        T: wp.array3d(dtype=float), Z_surf: wp.array2d(dtype=float),
        result: wp.array(dtype=float), nx: int, ny: int, nz: int, dz: float, T_solidus: float
    ):
        if wp.tid() == 0:
            i, j, k = 2, 2, 2
            result[0] = _average_transverse_face_component(
                V, T, Z_surf, i, j-1, k, i, j, k, i+1, j-1, k, i+1, j, k,
                1, nx, ny, nz, dz, T_solidus)
            result[1] = _average_transverse_face_component(
                W, T, Z_surf, i, j, k-1, i, j, k, i+1, j, k-1, i+1, j, k,
                2, nx, ny, nz, dz, T_solidus)
            result[2] = _average_transverse_face_component(
                U, T, Z_surf, i-1, j, k, i, j, k, i-1, j+1, k, i, j+1, k,
                0, nx, ny, nz, dz, T_solidus)
            result[3] = _average_transverse_face_component(
                W, T, Z_surf, i, j-1, k-1, i, j-1, k, i, j, k-1, i, j, k,
                2, nx, ny, nz, dz, T_solidus)
            result[4] = _average_transverse_face_component(
                U, T, Z_surf, i-1, j, k-1, i, j, k-1, i-1, j, k, i, j, k,
                0, nx, ny, nz, dz, T_solidus)
            result[5] = _average_transverse_face_component(
                V, T, Z_surf, i, j-1, k-1, i, j, k-1, i, j-1, k, i, j, k,
                1, nx, ny, nz, dz, T_solidus)


    class Transient3DPhysicsContracts(unittest.TestCase):
        @staticmethod
        def _wp_array(values):
            return wp.array(np.asarray(values, dtype=np.float32), dtype=float, device="cpu")

        def test_new_surface_graph_resets_exposed_enthalpy_once_and_excludes_melt(self):
            shape = (5, 5, 5)
            dx = dy = dz = 1e-5
            rho, cp_solid, cp_liquid = 4420.0, 670.0, 730.0
            solidus, liquidus, ambient, hot = 1878.0, 1928.0, 300.0, 2000.0
            h_solidus = rho * cp_solid * solidus
            h_liquidus = h_solidus + rho * 2.9e5 + rho * 0.5 * (cp_solid + cp_liquid) * (liquidus - solidus)
            h_hot = h_liquidus + rho * cp_liquid * (hot - liquidus)
            h_ambient = rho * cp_solid * ambient
            temperature = np.full(shape, hot, dtype=np.float32)
            enthalpy = np.full(shape, h_hot, dtype=np.float32)
            surface = np.full(shape[:2], 2.99 * dz, dtype=np.float32)
            devices = ["cpu"] + (["cuda:0"] if wp.get_cuda_device_count() else [])
            previous_pch_setting = wp.config.use_precompiled_headers
            try:
                for device in devices:
                    with self.subTest(device=device):
                        if device != "cpu":
                            wp.config.use_precompiled_headers = False
                        T = wp.array(temperature, dtype=float, device=device)
                        H = wp.array(enthalpy, dtype=float, device=device)
                        Z = wp.array(surface, dtype=float, device=device)
                        reset_J = wp.zeros(shape, dtype=wp.float64, device=device)
                        args = [T, H, Z, reset_J, *shape, dx, dy, dz, rho, 2.9e5,
                                solidus, liquidus, cp_solid, cp_liquid, ambient, 1]

                        wp.launch(phase22_reconcile_surface_mask_kernel, dim=shape,
                                  inputs=args, device=device)
                        wp.synchronize_device(device)
                        first = reset_J.numpy()[2, 2, 3]
                        expected = (h_ambient - float(enthalpy[2, 2, 3])) * dx * dy * dz
                        self.assertAlmostEqual(float(T.numpy()[2, 2, 3]), ambient, delta=1e-5)
                        self.assertAlmostEqual(float(H.numpy()[2, 2, 3]), h_ambient, delta=64.0)
                        self.assertAlmostEqual(float(first), expected, delta=abs(expected) * 1e-5)
                        self.assertFalse(_surface_liquid_mask(T.numpy(), Z.numpy(), dz, liquidus)[2, 2, 3])
                        self.assertTrue(_surface_liquid_mask(T.numpy(), Z.numpy(), dz, liquidus)[2, 2, 2])

                        wp.launch(phase22_reconcile_surface_mask_kernel, dim=shape,
                                  inputs=args, device=device)
                        wp.synchronize_device(device)
                        self.assertEqual(float(reset_J.numpy()[2, 2, 3]), float(first))
            finally:
                wp.config.use_precompiled_headers = previous_pch_setting

        def _run_surface_forces(self, center_temperature):
            shape = (5, 5, 5)
            dx = dy = dz = 1.0e-3
            dt = 1.0e-6
            temperature = np.full(shape, center_temperature, dtype=np.float32)
            # A 100 K difference across 2 mm gives a known tangential gradient.
            temperature[1, 2, 3] = center_temperature - 100.0
            temperature[3, 2, 3] = center_temperature + 100.0
            surface = np.full((shape[0], shape[1]), 3.5 * dz, dtype=np.float32)
            fields = [wp.zeros(shape, dtype=float, device="cpu") for _ in range(6)]
            wp.launch(
                kernel=velocity_advection_forces_kernel, dim=shape,
                inputs=[*fields[:3], *fields[3:], self._wp_array(temperature),
                        self._wp_array(surface), *shape, dx, dy, dz, dt,
                        0.005, 4420.0, -0.0003, 0.0,
                        1928.0, 1878.0, 101325.0, 9.7e6, 173.93, 3533.0],
                device="cpu",
            )
            wp.synchronize()
            return fields[3].numpy()[2, 2, 3], fields[5].numpy()[2, 2, 3]

        def test_free_surface_kinematics_uses_normal_velocity_and_evaporation(self):
            shape = (7, 7, 7)
            dx = dy = dz = 1.0e-3
            dt = 1.0e-3
            surface = np.full((shape[0], shape[1]), 3.5 * dz, dtype=np.float32)
            temperature = np.full(shape, 2000.0, dtype=np.float32)
            U = np.zeros(shape, dtype=np.float32)
            V = np.zeros(shape, dtype=np.float32)
            W = np.full(shape, 0.2, dtype=np.float32)
            updated = self._update_surface(surface, temperature, U, V, W, dt, dx, dy, dz)
            self.assertAlmostEqual(updated[3, 3], float(surface[3, 3]) + 0.2 * dt, delta=2e-7)

            # The evaporative contribution follows the same Hertz-Knudsen flux as
            # the enthalpy sink, converted to liquid recession speed by rho.
            hot = np.full(shape, 3600.0, dtype=np.float32)
            zero = np.zeros(shape, dtype=np.float32)
            updated = self._update_surface(surface, hot, zero, zero, zero, dt, dx, dy, dz)
            p_sat = 101325.0 * np.exp((9.7e6 / 173.93) * (1.0 / 3533.0 - 1.0 / 3600.0))
            m_dot = 0.54 * p_sat / np.sqrt(2.0 * np.pi * 173.93 * 3600.0 + 1e-6)
            expected = float(surface[3, 3]) - dt * m_dot / 4420.0
            self.assertAlmostEqual(updated[3, 3], expected, delta=2e-7)

        def test_evaporation_energy_and_height_mass_use_same_surface_area(self):
            shape = (5, 5, 7)
            dx = dy = dz = 1.0e-4
            dt = 1.0e-5
            rho, lv = 4420.0, 9.7e6
            temperature = np.full(shape, 3600.0, dtype=np.float32)
            surface = np.full(shape[:2], 3.5 * dz, dtype=np.float32)
            for i in range(shape[0]):
                surface[i, :] = (3.5 + 0.5 * (i - 2)) * dz

            old_enthalpy = np.full(shape, 1.0e10, dtype=np.float32)
            new_enthalpy = wp.zeros(shape, dtype=float, device="cpu")
            new_temperature = wp.zeros(shape, dtype=float, device="cpu")
            zero_velocity = wp.zeros(shape, dtype=float, device="cpu")
            empty_toolpath = self._wp_array([0.0])
            wp.launch(
                kernel=enthalpy_3d_nonlinear_step_kernel, dim=shape,
                inputs=[self._wp_array(temperature), self._wp_array(old_enthalpy),
                        zero_velocity, zero_velocity, zero_velocity,
                        new_temperature, new_enthalpy, self._wp_array(surface),
                        *shape, dx, dy, dz, dt, 0.0, rho, 2.9e5,
                        1878.0, 1928.0, empty_toolpath, empty_toolpath,
                        empty_toolpath, empty_toolpath, 0, 30e-6, 0.0,
                        0.0, 0.0, 300.0, 101325.0, lv, 173.93, 3533.0,
                        670.0, 730.0, 15.0, 25.0],
                device="cpu",
            )
            wp.synchronize()
            updated_surface = self._update_surface(
                surface, temperature,
                np.zeros(shape, dtype=np.float32), np.zeros(shape, dtype=np.float32),
                np.zeros(shape, dtype=np.float32), dt, dx, dy, dz,
            )

            i = j = 2
            k = int(float(surface[i, j]) / dz)
            h_x = (float(surface[i + 1, j]) - float(surface[i - 1, j])) / (2.0 * dx)
            area_metric = np.sqrt(1.0 + h_x * h_x)
            p_sat = 101325.0 * np.exp((lv / 173.93) * (1.0 / 3533.0 - 1.0 / 3600.0))
            m_dot = 0.54 * p_sat / np.sqrt(2.0 * np.pi * 173.93 * 3600.0 + 1e-6)
            projected_area = dx * dy
            evaporated_mass_from_height = rho * (float(surface[i, j]) - float(updated_surface[i, j])) * projected_area
            evaporated_mass_from_enthalpy = -(
                float(new_enthalpy.numpy()[i, j, k]) - float(old_enthalpy[i, j, k])
            ) * dx * dy * dz / lv
            expected_mass = m_dot * area_metric * projected_area * dt

            self.assertTrue(np.isclose(evaporated_mass_from_height, expected_mass, rtol=0.01))
            self.assertTrue(np.isclose(evaporated_mass_from_enthalpy, expected_mass, rtol=0.01))
            self.assertTrue(np.isclose(evaporated_mass_from_enthalpy,
                                       evaporated_mass_from_height, rtol=0.01))

        def test_solid_surface_has_no_liquid_evaporation_energy_or_mass_loss(self):
            shape = (5, 5, 7)
            dx = dy = dz = 1.0e-4
            dt = 1.0e-2
            temperature = np.full(shape, 1850.0, dtype=np.float32)
            enthalpy = np.full(shape, 1.0e10, dtype=np.float32)
            surface = np.full(shape[:2], 3.5 * dz, dtype=np.float32)
            zero_velocity = wp.zeros(shape, dtype=float, device="cpu")
            empty_toolpath = self._wp_array([0.0])
            new_enthalpy = wp.zeros(shape, dtype=float, device="cpu")
            new_temperature = wp.zeros(shape, dtype=float, device="cpu")
            wp.launch(
                kernel=enthalpy_3d_nonlinear_step_kernel, dim=shape,
                inputs=[self._wp_array(temperature), self._wp_array(enthalpy),
                        zero_velocity, zero_velocity, zero_velocity,
                        new_temperature, new_enthalpy, self._wp_array(surface),
                        *shape, dx, dy, dz, dt, 0.0, 4420.0, 2.9e5,
                        1878.0, 1928.0, empty_toolpath, empty_toolpath,
                        empty_toolpath, empty_toolpath, 0, 30e-6, 0.0,
                        0.0, 0.0, 300.0, 101325.0, 9.7e6, 173.93, 3533.0,
                        670.0, 730.0, 15.0, 25.0],
                device="cpu",
            )
            wp.synchronize()

            ledger_arrays = [
                wp.zeros(shape, dtype=wp.float64, device="cpu") for _ in range(7)
            ]
            wp.launch(
                kernel=phase22_energy_ledger_step_kernel, dim=shape,
                inputs=[self._wp_array(temperature), self._wp_array(enthalpy),
                        zero_velocity, zero_velocity, zero_velocity,
                        self._wp_array(surface), *ledger_arrays,
                        *shape, dx, dy, dz, dt, 0.0, 4420.0, 2.9e5,
                        1878.0, 1928.0, empty_toolpath, empty_toolpath,
                        empty_toolpath, empty_toolpath, 0, 30e-6, 0.0,
                        0.0, 0.0, 300.0, 101325.0, 9.7e6, 173.93, 3533.0,
                        670.0, 730.0, 15.0, 25.0],
                device="cpu",
            )
            wp.synchronize()

            updated_surface = self._update_surface(
                surface, temperature, np.zeros(shape, dtype=np.float32),
                np.zeros(shape, dtype=np.float32), np.zeros(shape, dtype=np.float32),
                dt, dx, dy, dz,
            )
            i = j = 2
            k = int(float(surface[i, j]) / dz)
            self.assertEqual(float(updated_surface[i, j]), float(surface[i, j]))
            self.assertEqual(float(new_enthalpy.numpy()[i, j, k]), float(enthalpy[i, j, k]))
            self.assertEqual(float(ledger_arrays[5].numpy()[i, j, k]), 0.0)

        def test_convection_and_radiation_losses_use_graph_surface_area_once(self):
            shape = (5, 5, 7)
            dx = dy = dz = 1.0e-4
            dt = 1.0e-5
            temperature = np.full(shape, 2000.0, dtype=np.float32)
            surface = np.full(shape[:2], 3.5 * dz, dtype=np.float32)
            for i in range(shape[0]):
                surface[i, :] = (3.5 + 0.5 * (i - 2)) * dz

            old_enthalpy = np.full(shape, 1.0e9, dtype=np.float32)
            new_enthalpy = wp.zeros(shape, dtype=float, device="cpu")
            new_temperature = wp.zeros(shape, dtype=float, device="cpu")
            zero_velocity = wp.zeros(shape, dtype=float, device="cpu")
            empty_toolpath = self._wp_array([0.0])
            wp.launch(
                kernel=enthalpy_3d_nonlinear_step_kernel, dim=shape,
                inputs=[self._wp_array(temperature), self._wp_array(old_enthalpy),
                        zero_velocity, zero_velocity, zero_velocity,
                        new_temperature, new_enthalpy, self._wp_array(surface),
                        *shape, dx, dy, dz, dt, 0.0, 4420.0, 2.9e5,
                        1878.0, 1928.0, empty_toolpath, empty_toolpath,
                        empty_toolpath, empty_toolpath, 0, 30e-6, 0.0,
                        10.0, 0.35, 300.0, 0.0, 9.7e6, 173.93, 3533.0,
                        670.0, 730.0, 15.0, 25.0],
                device="cpu",
            )
            wp.synchronize()

            i = j = 2
            k = int(float(surface[i, j]) / dz)
            q_loss = 10.0 * (2000.0 - 300.0) + 0.35 * 5.67e-8 * (2000.0**4 - 300.0**4)
            graph_area_metric = np.sqrt(1.0 + 0.5**2)
            expected_delta = -dt * q_loss * graph_area_metric / dz
            actual_delta = float(new_enthalpy.numpy()[i, j, k] - old_enthalpy[i, j, k])
            self.assertAlmostEqual(actual_delta, expected_delta, delta=abs(expected_delta) * 0.01)

        def _update_surface(self, surface, temperature, U, V, W, dt, dx, dy, dz):
            nx, ny = surface.shape
            nz = temperature.shape[2]
            new_surface = wp.zeros((nx, ny), dtype=float, device="cpu")
            surface_floor_hit = wp.zeros(1, dtype=wp.int32, device="cpu")
            wp.launch(
                kernel=free_surface_kinematics_kernel, dim=(nx, ny),
                inputs=[self._wp_array(surface), new_surface, surface_floor_hit,
                        self._wp_array(U), self._wp_array(V), self._wp_array(W),
                        self._wp_array(temperature), nx, ny, nz, dx, dy, dz, dt,
                        4420.0, 1878.0, 101325.0, 9.7e6, 173.93, 3533.0],
                device="cpu",
            )
            wp.synchronize()
            return new_surface.numpy()

        def test_solver_fails_before_evaporation_when_surface_hits_bottom_floor(self):
            toolpath = {
                "t": [0.0, 1e-9], "x": [1e-5, 1e-5],
                "y": [1e-5, 1e-5], "p": [0.0, 0.0],
            }
            devices = ["cpu"] + (["cuda:0"] if wp.get_cuda_device_count() else [])
            previous_pch_setting = wp.config.use_precompiled_headers
            try:
                for device in devices:
                    with self.subTest(device=device):
                        if device != "cpu":
                            wp.config.use_precompiled_headers = False
                        solver = TransientEnthalpy3DGPU(
                            nx=4, ny=4, nz=4, dx=1e-5, dy=1e-5, dz=1e-5
                        )
                        solver.device = device
                        with self.assertRaisesRegex(RuntimeError, "Phase 22 validity error.*z=2\\*dz"):
                            solver.solve_toolpath(toolpath, T_preheat_K=2000.0, **LEGACY_SOLVER_TEST_MATERIAL)
            finally:
                wp.config.use_precompiled_headers = previous_pch_setting
            self.assertEqual(wp.config.use_precompiled_headers, previous_pch_setting)

        def test_free_surface_graph_advects_tangentially(self):
            shape = (7, 7, 7)
            dx = dy = dz = 1.0e-3
            dt = 1.0e-3
            surface = np.full((shape[0], shape[1]), 3.5 * dz, dtype=np.float32)
            for i in range(shape[0]):
                surface[i, :] += np.float32(0.25 * (i - 3) * dx)
            temperature = np.full(shape, 2000.0, dtype=np.float32)
            U = np.full(shape, 0.4, dtype=np.float32)
            zero = np.zeros(shape, dtype=np.float32)
            updated = self._update_surface(surface, temperature, U, zero, zero, dt, dx, dy, dz)
            expected = float(surface[3, 3]) - 0.4 * 0.25 * dt
            self.assertAlmostEqual(updated[3, 3], expected, delta=2e-7)

        def test_projected_recoil_velocity_drives_kinematic_surface(self):
            shape = (7, 7, 7)
            dx = dy = dz = 1.0e-5
            dt = 1.0e-7
            rho = 4420.0
            k_surf = shape[2] - 2
            surface = np.full(shape[:2], k_surf * dz, dtype=np.float32)
            temperature = np.full(shape, 2000.0, dtype=np.float32)
            temperature[3, 3, k_surf] = 3600.0
            zero = np.zeros(shape, dtype=np.float32)
            predictor = [wp.zeros(shape, dtype=float, device="cpu") for _ in range(3)]
            wp.launch(
                kernel=velocity_advection_forces_kernel, dim=shape,
                inputs=[self._wp_array(zero), self._wp_array(zero), self._wp_array(zero),
                        *predictor, self._wp_array(temperature), self._wp_array(surface),
                        *shape, dx, dy, dz, dt, 0.005, rho, -0.0003, 0.0,
                        1928.0, 1878.0, 101325.0, 9.7e6, 173.93, 3533.0],
                device="cpu",
            )
            wp.synchronize()
            velocity = tuple(field.numpy() for field in predictor)
            before, after, _, status, _, _, _, projected_velocity = self._run_pressure_projection(
                velocity, temperature, surface, _PRESSURE_PCG_MAX_ITERATIONS,
                spacing=(dx, dy, dz), dt=dt, rho=rho,
            )
            self.assertEqual(status, _PRESSURE_STATUS_CONVERGED)
            self.assertGreater(np.linalg.norm(before), 0.0)
            self.assertLess(np.linalg.norm(after), np.linalg.norm(before))

            projected_w = projected_velocity[2]
            z_over_dz = float(surface[3, 3]) / dz
            k_w0 = int(z_over_dz - 0.5)
            frac_w = z_over_dz - (k_w0 + 0.5)
            w_surface = ((1.0 - frac_w) * projected_w[3, 3, k_w0]
                         + frac_w * projected_w[3, 3, k_w0 + 1])
            self.assertLess(w_surface, 0.0)

            updated = self._update_surface(
                surface, temperature, *projected_velocity, dt, dx, dy, dz
            )
            p_sat = 101325.0 * np.exp((9.7e6 / 173.93) * (1.0 / 3533.0 - 1.0 / 3600.0))
            m_dot = 0.54 * p_sat / np.sqrt(2.0 * np.pi * 173.93 * 3600.0 + 1e-6)
            expected = float(surface[3, 3]) + dt * (w_surface - m_dot / rho)
            self.assertAlmostEqual(updated[3, 3], expected, delta=2e-7)

        def test_surface_force_temperature_regimes(self):
            # Above solidus but below liquidus: no Marangoni or recoil boundary law.
            u_below_liquidus, w_below_liquidus = self._run_surface_forces(1900.0)
            self.assertAlmostEqual(u_below_liquidus, 0.0, delta=1e-7)
            self.assertAlmostEqual(w_below_liquidus, 0.0, delta=1e-7)

            # Liquidus-to-boiling interval: tangential Marangoni stress, no recoil.
            u_marangoni, w_marangoni = self._run_surface_forces(2500.0)
            self.assertLess(u_marangoni, 0.0)
            self.assertAlmostEqual(w_marangoni, 0.0, delta=1e-7)

            # Above boiling: recoil impulse is active and the sub-boiling Marangoni
            # boundary assignment no longer overwrites the tangential predictor.
            u_recoil, w_recoil = self._run_surface_forces(3600.0)
            self.assertAlmostEqual(u_recoil, 0.0, delta=1e-7)
            self.assertLess(w_recoil, 0.0)

        def test_marangoni_gradient_samples_neighboring_surface_cells(self):
            shape = (5, 5, 7)
            dx = dy = dz = 1.0e-3
            dt = 1.0e-6
            temperature = np.full(shape, 300.0, dtype=np.float32)
            # The graph rises by one cell on each side. Its interface temperature
            # is uniform, while the common z-plane crosses air on one side and
            # sub-surface liquid on the other.
            surface = np.full(shape[:2], 3.5 * dz, dtype=np.float32)
            surface[1, :] = 2.5 * dz
            surface[3, :] = 4.5 * dz
            temperature[1, :, 2] = 2500.0
            temperature[2, :, 3] = 2500.0
            temperature[3, :, 4] = 2500.0
            temperature[3, :, 3] = 2400.0

            fields = [wp.zeros(shape, dtype=float, device="cpu") for _ in range(6)]
            wp.launch(
                kernel=velocity_advection_forces_kernel, dim=shape,
                inputs=[*fields[:3], *fields[3:], self._wp_array(temperature),
                        self._wp_array(surface), *shape, dx, dy, dz, dt,
                        0.005, 4420.0, -0.0003, 0.0,
                        1928.0, 1878.0, 101325.0, 9.7e6, 173.93, 3533.0],
                device="cpu",
            )
            wp.synchronize()
            # Uniform interface temperature has no Marangoni stress despite the
            # different phase temperatures on the same-z neighboring cells.
            self.assertAlmostEqual(fields[3].numpy()[2, 2, 3], 0.0, delta=1e-7)

        def test_marangoni_shear_is_tangent_to_sloped_height_graph(self):
            shape = (7, 7, 7)
            dx = dy = dz = 1.0e-3
            surface = np.empty(shape[:2], dtype=np.float32)
            temperature = np.full(shape, 300.0, dtype=np.float32)
            for i in range(shape[0]):
                for j in range(shape[1]):
                    surface[i, j] = (3.5 + 0.25 * (i - 3) + 0.125 * (j - 3)) * dz
                    k_surface = int(surface[i, j] / dz)
                    temperature[i, j, k_surface] = 2400.0 + 10.0 * (i - 3) + 20.0 * (j - 3)

            hx, hy = 0.25, 0.125
            dT_dx, dT_dy = 10.0 / dx, 20.0 / dy
            denominator = 1.0 + hx * hx + hy * hy
            grad_x = ((1.0 + hy * hy) * dT_dx - hx * hy * dT_dy) / denominator
            grad_y = ((1.0 + hx * hx) * dT_dy - hx * hy * dT_dx) / denominator
            grad_z = hx * grad_x + hy * grad_y
            normal_spacing = dz / np.sqrt(denominator)
            scale = normal_spacing * (-0.0003 / 0.005)
            expected = scale * np.array([grad_x, grad_y, grad_z])
            devices = ["cpu"] + (["cuda:0"] if wp.get_cuda_device_count() else [])
            for device in devices:
                if device != "cpu":
                    wp.config.use_precompiled_headers = False
                fields = [wp.zeros(shape, dtype=float, device=device) for _ in range(6)]
                wp.launch(
                    kernel=velocity_advection_forces_kernel, dim=shape,
                    inputs=[*fields[:3], *fields[3:], wp.array(temperature, dtype=float, device=device),
                            wp.array(surface, dtype=float, device=device), *shape, dx, dy, dz,
                            1.0e-6, 0.005, 4420.0, -0.0003, 0.0,
                            1928.0, 1878.0, 101325.0, 9.7e6, 173.93, 3533.0],
                    device=device,
                )
                wp.synchronize_device(device)
                actual = np.array([field.numpy()[3, 3, 3] for field in fields[3:]])
                np.testing.assert_allclose(actual, expected, rtol=1e-5, atol=1e-7, err_msg=device)
                self.assertAlmostEqual(float(np.dot(actual, [-hx, -hy, 1.0])), 0.0, delta=1e-6)
                actual_surface_gradient = np.array([grad_x, grad_y, grad_z])
                actual_surface_traction = 0.005 * actual / normal_spacing
                np.testing.assert_allclose(
                    actual_surface_traction, -0.0003 * actual_surface_gradient,
                    rtol=1e-5, atol=1e-8, err_msg=device,
                )

        def test_recoil_impulse_follows_local_height_graph_normal(self):
            shape = (7, 7, 7)
            dx = dy = dz = 1.0e-5
            dt = 1.0e-7
            rho = 4420.0
            surface = np.empty(shape[:2], dtype=np.float32)
            for i in range(shape[0]):
                for j in range(shape[1]):
                    surface[i, j] = (3.5 + 0.25 * (i - 3) - 0.125 * (j - 3)) * dz
            temperature = np.full(shape, 2000.0, dtype=np.float32)
            temperature[3, 3, int(surface[3, 3] / dz)] = 3600.0
            p_sat = 101325.0 * np.exp((9.7e6 / 173.93) * (1.0 / 3533.0 - 1.0 / 3600.0))
            recoil_scale = (0.54 * p_sat / rho) * (dt / dz)
            expected = recoil_scale * np.array([0.25, -0.125, -1.0])
            devices = ["cpu"] + (["cuda:0"] if wp.get_cuda_device_count() else [])
            for device in devices:
                if device != "cpu":
                    wp.config.use_precompiled_headers = False
                fields = [wp.zeros(shape, dtype=float, device=device) for _ in range(6)]
                wp.launch(
                    kernel=velocity_advection_forces_kernel, dim=shape,
                    inputs=[*fields[:3], *fields[3:], wp.array(temperature, dtype=float, device=device),
                            wp.array(surface, dtype=float, device=device), *shape, dx, dy, dz, dt,
                            0.005, rho, -0.0003, 0.0, 1928.0, 1878.0,
                            101325.0, 9.7e6, 173.93, 3533.0],
                    device=device,
                )
                wp.synchronize_device(device)
                actual = np.array([field.numpy()[3, 3, 3] for field in fields[3:]])
                np.testing.assert_allclose(actual, expected, rtol=1e-5, atol=1e-7, err_msg=device)
                self.assertAlmostEqual(float(actual[0] + 0.25 * actual[2]), 0.0, delta=1e-7)
                self.assertAlmostEqual(float(actual[1] - 0.125 * actual[2]), 0.0, delta=1e-7)

        @staticmethod
        def _pressure_cell_class_host(temperature, surface, i, j, k, dz, solidus=1000.0):
            nx, ny, nz = temperature.shape
            if i <= 0 or i >= nx - 1 or j <= 0 or j >= ny - 1 or k <= 0:
                return 0
            if k > int(surface[i, j] / dz):
                return 2
            if k >= nz - 1:
                return 0
            return 1 if temperature[i, j, k] >= solidus else 0

        def _pressure_apply_host(self, pressure, temperature, surface, spacing):
            nx, ny, nz = pressure.shape
            dx, dy, dz = spacing
            out = np.zeros_like(pressure, dtype=np.float64)
            for i in range(1, nx - 1):
                for j in range(1, ny - 1):
                    for k in range(1, nz - 1):
                        if self._pressure_cell_class_host(temperature, surface, i, j, k, dz) != 1:
                            continue
                        diagonal = 0.0
                        value = 0.0
                        for di, dj, dk, h in ((-1, 0, 0, dx), (1, 0, 0, dx),
                                              (0, -1, 0, dy), (0, 1, 0, dy),
                                              (0, 0, -1, dz), (0, 0, 1, dz)):
                            cls = self._pressure_cell_class_host(
                                temperature, surface, i + di, j + dj, k + dk, dz
                            )
                            if cls in (1, 2):
                                coefficient = 1.0 / (h * h)
                                diagonal += coefficient
                                if cls == 1:
                                    value -= pressure[i + di, j + dj, k + dk] * coefficient
                        out[i, j, k] = diagonal * pressure[i, j, k] + value
            return out

        def _launch_pressure_operators(self, pressure, temperature, surface, spacing=(1.0, 1.0, 1.0),
                                       velocity=None, div=None, dt=1.0, rho=1.0):
            shape = temperature.shape
            dx, dy, dz = spacing
            P = self._wp_array(pressure)
            T = self._wp_array(temperature)
            Z_surf = self._wp_array(surface)
            U, V, W = (wp.zeros(shape, dtype=float, device="cpu") for _ in range(3))
            if velocity is not None:
                for target, source in zip((U, V, W), velocity):
                    target.assign(self._wp_array(source))
            Div = wp.zeros(shape, dtype=float, device="cpu") if div is None else self._wp_array(div)
            P_new = wp.zeros(shape, dtype=float, device="cpu")
            wp.launch(
                kernel=project_velocity_kernel, dim=shape,
                inputs=[U, V, W, P, Z_surf, T, *shape, dx, dy, dz, dt, rho, 1000.0], device="cpu",
            )
            wp.launch(
                kernel=compute_divergence_kernel, dim=shape,
                inputs=[U, V, W, Div, Z_surf, T, *shape, dx, dy, dz, 1000.0], device="cpu",
            )
            wp.launch(
                kernel=pressure_jacobi_kernel, dim=shape,
                inputs=[P, P_new, Div, Z_surf, T, *shape, dx, dy, dz, dt, rho, 1000.0], device="cpu",
            )
            wp.synchronize()
            return P_new.numpy(), Div.numpy(), tuple(array.numpy() for array in (U, V, W))

        def _run_pressure_projection(self, velocity, temperature, surface, iterations,
                                     spacing=(1.0, 1.0, 1.0), dt=0.1, rho=1.0):
            shape = temperature.shape
            nx, ny, nz = shape
            dx, dy, dz = spacing
            T, Z_surf = self._wp_array(temperature), self._wp_array(surface)
            U, V, W = (self._wp_array(a) for a in velocity)
            P = wp.zeros(shape, dtype=float, device="cpu")
            Div = wp.zeros(shape, dtype=float, device="cpu")

            def divergence():
                wp.launch(kernel=compute_divergence_kernel, dim=shape,
                          inputs=[U, V, W, Div, Z_surf, T, nx, ny, nz, dx, dy, dz, 1000.0],
                          device="cpu")
                wp.synchronize()
                return Div.numpy().copy()

            before = divergence()
            pcg_fields = [wp.zeros(shape, dtype=float, device="cpu") for _ in range(4)]
            residual, preconditioned, direction, A_direction = pcg_fields
            scalars = [wp.zeros(1, dtype=float, device="cpu") for _ in range(9)]
            rho_current, rho_next, rhs_norm2, residual_norm2, residual_next_norm2, scale_norm2, direction_dot_A, alpha, beta = scalars
            status = wp.zeros(1, dtype=wp.int32, device="cpu")
            pcg_iterations = wp.zeros(1, dtype=wp.int32, device="cpu")
            rho_current, rho_next = launch_pressure_pcg(
                P, Div, Z_surf, T, shape, spacing, dt, rho, 1000.0,
                residual, preconditioned, direction, A_direction,
                rho_current, rho_next, rhs_norm2, residual_norm2, residual_next_norm2, scale_norm2,
                direction_dot_A, alpha, beta, status, pcg_iterations,
                max_iterations=iterations,
            )
            wp.launch(kernel=project_velocity_kernel, dim=shape,
                      inputs=[U, V, W, P, Z_surf, T, nx, ny, nz, dx, dy, dz,
                              dt, rho, 1000.0], device="cpu")
            after = divergence()
            projected_velocity = tuple(array.numpy().copy() for array in (U, V, W))
            return (before, after, P.numpy(), int(status.numpy()[0]),
                    int(pcg_iterations.numpy()[0]), float(residual_norm2.numpy()[0]),
                    float(scale_norm2.numpy()[0]), projected_velocity)

        def _solve_pressure(self, div, temperature, surface, initial_pressure=None,
                            spacing=(1.0, 1.0, 1.0), dt=1.0, rho=1.0, max_iterations=100):
            shape = temperature.shape
            T, Z_surf, Div = self._wp_array(temperature), self._wp_array(surface), self._wp_array(div)
            P = self._wp_array(initial_pressure) if initial_pressure is not None else wp.zeros(shape, dtype=float, device="cpu")
            residual, preconditioned, direction, A_direction = [wp.zeros(shape, dtype=float, device="cpu") for _ in range(4)]
            rho_current, rho_next, rhs2, residual2, residual_next2, scale2, pAp, alpha, beta = [wp.zeros(1, dtype=float, device="cpu") for _ in range(9)]
            status = wp.zeros(1, dtype=wp.int32, device="cpu")
            iterations = wp.zeros(1, dtype=wp.int32, device="cpu")
            rho_current, rho_next = launch_pressure_pcg(
                P, Div, Z_surf, T, shape, spacing, dt, rho, 1000.0,
                residual, preconditioned, direction, A_direction,
                rho_current, rho_next, rhs2, residual2, residual_next2, scale2, pAp, alpha, beta,
                status, iterations, max_iterations=max_iterations,
            )
            wp.synchronize()
            scale_value = float(scale2.numpy()[0])
            residual_value = float(residual2.numpy()[0])
            relative = float(np.sqrt(residual_value / scale_value)) if scale_value > 0 else 0.0
            return P.numpy(), int(status.numpy()[0]), int(iterations.numpy()[0]), relative

        def test_step_schedule_ends_exactly_at_requested_duration(self):
            dt = 0.1
            self.assertEqual(_step_count(0.0, dt), 0)
            self.assertEqual(_step_count(0.3, dt), 3)
            self.assertEqual(_step_count(0.25, dt), 3)
            sizes = [_step_size(0.25, dt, step) for step in range(3)]
            self.assertEqual(sizes, [0.1, 0.1, 0.04999999999999999])
            self.assertAlmostEqual(sum(sizes), 0.25)

        def test_phase22_step_size_bounds_explicit_advection_and_viscosity(self):
            dx = dy = dz = 2.0e-6
            rho, mu, k_max, cp_min = 8190.0, 0.01, 10.0, 500.0
            dt = _phase22_stable_step_size(dx, dy, dz, rho, mu, k_max, cp_min)
            spacings = (dx, dy, dz)
            nu = mu / rho
            momentum_rate = sum(
                _PHASE22_MAX_COMPONENT_SPEED_M_S / h + 2.0 * nu / (h * h)
                for h in spacings
            )
            thermal_dt = 0.12 * min(spacings) ** 2 / (k_max / (rho * cp_min))

            self.assertLess(dt, thermal_dt)
            self.assertLessEqual(
                dt * momentum_rate, _PHASE22_MOMENTUM_CFL_LIMIT + 1e-12
            )
            self.assertEqual(_step_count(1e-6, dt), math.ceil(1e-6 / dt))

        def test_projected_velocity_cfl_guard_uses_actual_field(self):
            shape = (5, 5, 5)
            dx = dy = dz = 2.0e-6
            rho, mu = 8190.0, 0.01
            temperature = np.full(shape, 2000.0, dtype=np.float32)
            surface = np.full(shape[:2], 4.5 * dz, dtype=np.float32)
            U = np.zeros(shape, dtype=np.float32)
            V = np.zeros(shape, dtype=np.float32)
            W = np.zeros(shape, dtype=np.float32)
            U[2, 2, 2] = 10.0  # synthetic post-projection component above the 5 m/s predictor cap
            devices = ["cpu"] + (["cuda:0"] if wp.get_cuda_device_count() else [])
            previous_pch_setting = wp.config.use_precompiled_headers
            try:
                for device in devices:
                    with self.subTest(device=device):
                        if device != "cpu":
                            wp.config.use_precompiled_headers = False
                        exceeded = wp.zeros(1, dtype=wp.int32, device=device)
                        wp.launch(
                            kernel=validate_projected_momentum_cfl_kernel, dim=shape,
                            inputs=[wp.array(U, dtype=float, device=device),
                                    wp.array(V, dtype=float, device=device),
                                    wp.array(W, dtype=float, device=device),
                                    wp.array(surface, dtype=float, device=device),
                                    wp.array(temperature, dtype=float, device=device), exceeded,
                                    *shape, dx, dy, dz, 1.0e-7, mu / rho, 1878.0,
                                    _PHASE22_MOMENTUM_CFL_LIMIT],
                            device=device,
                        )
                        wp.synchronize_device(device)
                        self.assertEqual(int(exceeded.numpy()[0]), 1)
            finally:
                wp.config.use_precompiled_headers = previous_pch_setting
            self.assertEqual(wp.config.use_precompiled_headers, previous_pch_setting)

        def test_zero_duration_single_point_toolpath_does_not_heat(self):
            solver = TransientEnthalpy3DGPU(nx=4, ny=4, nz=4, dx=1e-5, dy=1e-5, dz=1e-5)
            result = solver.solve_toolpath({"t": [0.0], "x": [0.0], "y": [0.0], "p": [300.0]}, **LEGACY_SOLVER_TEST_MATERIAL)
            self.assertEqual(result["steps"], 0)
            self.assertEqual(result["max_temperature_K"], 300.0)
            self.assertEqual(result["pressure_projection_status"], "not_run")
            self.assertIsNone(result["pressure_projection_converged"])

        def test_solver_result_reports_measured_projection_status_and_residual(self):
            solver = TransientEnthalpy3DGPU(nx=5, ny=5, nz=5, dx=1e-5, dy=1e-5, dz=1e-5)
            solver.device = "cpu"
            result = solver.solve_toolpath(
                {"t": [0.0, 1e-9], "x": [1e-5, 1e-5], "y": [1e-5, 1e-5], "p": [0.0, 0.0]},
                T_preheat_K=2000.0, **LEGACY_SOLVER_TEST_MATERIAL,
            )
            self.assertEqual(result["pressure_projection_solver"], "preconditioned_conjugate_gradient")
            self.assertIn(result["pressure_projection_status"], ("converged", "not_converged", "numerical_failure"))
            self.assertIsNotNone(result["pressure_projection_converged"])
            self.assertIsNotNone(result["pressure_projection_post_divergence_relative_l2"])
            self.assertIsNotNone(result["pressure_projection_post_divergence_max_s_inv"])
            self.assertEqual(result["pressure_projection_iterations"], result["pressure_projection_max_iterations_per_timestep"])
            self.assertGreaterEqual(result["pressure_projection_total_iterations"], result["pressure_projection_max_iterations_per_timestep"])

        def test_solver_recoil_moves_surface_through_projected_velocity(self):
            solver = TransientEnthalpy3DGPU(nx=5, ny=5, nz=5, dx=1e-5, dy=1e-5, dz=1e-5)
            solver.device = "cpu"
            result = solver.solve_toolpath(
                {"t": [0.0, 1e-7], "x": [1e-5, 1e-5], "y": [1e-5, 1e-5], "p": [0.0, 0.0]},
                T_preheat_K=3600.0,
                include_energy_ledger=True, **LEGACY_SOLVER_TEST_MATERIAL,
            )
            self.assertGreater(result["keyhole_depth_um"], 0.0)
            self.assertIn(result["pressure_projection_status"],
                          ("converged", "not_converged", "numerical_failure"))
            self.assertNotEqual(
                result["energy_ledger"]["terms_J"]["surface_mask_reset_J"], 0.0
            )
            self.assertLess(result["energy_ledger"]["closure"]["relative_error"], 1e-3)

        def _one_step(self, surface, temperature):
            wp.init()
            shape = (5, 5, 5)
            dx = dy = dz = 1e-5
            T = wp.array(temperature.astype(np.float32), dtype=float, device="cpu")
            H = wp.full(shape, 1.0e6, dtype=float, device="cpu")
            zeros = wp.zeros(shape, dtype=float, device="cpu")
            T_new = wp.zeros(shape, dtype=float, device="cpu")
            H_new = wp.zeros(shape, dtype=float, device="cpu")
            Z_surf = wp.array(surface.astype(np.float32), dtype=float, device="cpu")
            empty = wp.array([], dtype=float, device="cpu")
            wp.launch(
                kernel=enthalpy_3d_nonlinear_step_kernel,
                dim=shape,
                inputs=[
                    T, H, zeros, zeros, zeros, T_new, H_new, Z_surf,
                    *shape, dx, dy, dz, 1e-8, 0.0,
                    4420.0, 2.9e5, 1878.0, 1928.0,
                    empty, empty, empty, empty, 0,
                    30e-6, 0.4, 0.0, 0.0, 300.0,
                    0.0, 9.7e6, 173.93, 3533.0,
                    670.0, 730.0, 15.0, 25.0,
                ],
                device="cpu",
            )
            wp.synchronize()
            return H.numpy()[2, 2, 2], H_new.numpy()[2, 2, 2]

        def test_lateral_conduction_does_not_cross_depressed_surface_into_air(self):
            dz = 1e-5
            surface = np.full((5, 5), 2.5 * dz)
            surface[3, 2] = 1.5 * dz  # +x neighbor is air at the tested cell's height
            temperature = np.full((5, 5, 5), 2000.0)
            before, after = self._one_step(surface, temperature)
            self.assertAlmostEqual(after, before, delta=1e-5)

        def test_lateral_conduction_remains_enabled_between_material_cells(self):
            dz = 1e-5
            surface = np.full((5, 5), 2.5 * dz)
            temperature = np.full((5, 5, 5), 2000.0)
            temperature[3, 2, 2] = 300.0
            before, after = self._one_step(surface, temperature)
            self.assertLess(after, before)

        def test_pressure_gradient_and_divergence_are_the_same_discrete_laplacian(self):
            shape = (6, 6, 6)
            dx, dy, dz = 0.7, 1.1, 1.3
            surface = np.full((shape[0], shape[1]), 4.5 * dz, dtype=np.float32)
            surface[3, 2] = 2.5 * dz  # a stepped free surface creates an air face in +x
            temperature = np.full(shape, 2000.0, dtype=np.float32)
            pressure = np.fromfunction(lambda i, j, k: (-1.0) ** (i + j + k), shape, dtype=int).astype(np.float32)
            _, divergence, _ = self._launch_pressure_operators(
                pressure, temperature, surface, (dx, dy, dz)
            )

            def cell_class(i, j, k):
                nx, ny, nz = shape
                if i <= 0 or i >= nx - 1 or j <= 0 or j >= ny - 1 or k <= 0:
                    return 0  # domain face: no penetration
                if k > int(surface[i, j] / dz):
                    return 2  # free-surface air
                if k >= nz - 1:
                    return 0
                if temperature[i, j, k] < 1000.0:
                    return 0  # solid wall
                return 1

            for cell in ((2, 2, 2), (2, 2, 3), (3, 2, 2), (2, 2, 4)):
                i, j, k = cell
                self.assertEqual(cell_class(i, j, k), 1)
                laplacian = 0.0
                for di, dj, dk, h in ((-1, 0, 0, dx), (1, 0, 0, dx),
                                      (0, -1, 0, dy), (0, 1, 0, dy),
                                      (0, 0, -1, dz), (0, 0, 1, dz)):
                    neighbor_class = cell_class(i + di, j + dj, k + dk)
                    if neighbor_class == 1:
                        laplacian += (pressure[i + di, j + dj, k + dk] - pressure[i, j, k]) / (h * h)
                    elif neighbor_class == 2:
                        laplacian -= pressure[i, j, k] / (h * h)
                # Projection starts from zero velocity, so D(-G(p)) must equal -L(p).
                self.assertAlmostEqual(divergence[cell], -laplacian, delta=2e-5)

        def test_pressure_jacobi_uses_matching_active_and_free_surface_coefficients(self):
            shape = (6, 6, 6)
            dx, dy, dz = 0.7, 1.1, 1.3
            surface = np.full((shape[0], shape[1]), 4.5 * dz, dtype=np.float32)
            surface[3, 2] = 2.5 * dz
            temperature = np.full(shape, 2000.0, dtype=np.float32)
            pressure = np.fromfunction(lambda i, j, k: i + 2 * j - 0.5 * k, shape, dtype=int).astype(np.float32)
            pressure_new, divergence, _ = self._launch_pressure_operators(
                pressure, temperature, surface, (dx, dy, dz)
            )

            def cell_class(i, j, k):
                if i <= 0 or i >= shape[0] - 1 or j <= 0 or j >= shape[1] - 1 or k <= 0:
                    return 0
                if k > int(surface[i, j] / dz):
                    return 2
                if k >= shape[2] - 1:
                    return 0
                return 1 if temperature[i, j, k] >= 1000.0 else 0

            i, j, k = 2, 2, 3
            numerator = denominator = 0.0
            for di, dj, dk, h in ((-1, 0, 0, dx), (1, 0, 0, dx),
                                  (0, -1, 0, dy), (0, 1, 0, dy),
                                  (0, 0, -1, dz), (0, 0, 1, dz)):
                cls = cell_class(i + di, j + dj, k + dk)
                if cls in (1, 2):
                    denominator += 1.0 / (h * h)
                    if cls == 1:
                        numerator += pressure[i + di, j + dj, k + dk] / (h * h)
            numerator -= divergence[i, j, k]
            self.assertAlmostEqual(pressure_new[i, j, k], numerator / denominator, delta=2e-5)

        def test_checkerboard_pressure_is_not_a_projection_null_mode(self):
            shape = (6, 6, 6)
            surface = np.full((shape[0], shape[1]), 4.5, dtype=np.float32)
            temperature = np.full(shape, 2000.0, dtype=np.float32)
            pressure = np.fromfunction(lambda i, j, k: (-1.0) ** (i + j + k), shape, dtype=int).astype(np.float32)
            _, divergence, _ = self._launch_pressure_operators(pressure, temperature, surface)
            self.assertGreater(abs(divergence[2, 2, 2]), 1.0)

        def test_single_free_surface_cell_projection_removes_manufactured_divergence(self):
            shape = (5, 5, 5)
            surface = np.full((shape[0], shape[1]), 2.5, dtype=np.float32)
            temperature = np.full(shape, 300.0, dtype=np.float32)
            temperature[2, 2, 2] = 2000.0
            zeros = np.zeros(shape, dtype=np.float32)
            pressure0 = np.zeros(shape, dtype=np.float32)
            w = zeros.copy()
            w[2, 2, 2] = 3.0
            _, before, (u, v, w_after_pressure_solve) = self._launch_pressure_operators(
                pressure0, temperature, surface, velocity=(zeros, zeros, w)
            )
            initial_divergence = before[2, 2, 2]
            self.assertAlmostEqual(initial_divergence, 3.0, delta=1e-6)

            # The single pressure unknown has one free-surface coefficient; one
            # Jacobi update is the exact solve for this manufactured case.
            P = wp.zeros(shape, dtype=float, device="cpu")
            Div = self._wp_array(before)
            P_new = wp.zeros(shape, dtype=float, device="cpu")
            T = self._wp_array(temperature)
            Z_surf = self._wp_array(surface)
            wp.launch(kernel=pressure_jacobi_kernel, dim=shape,
                      inputs=[P, P_new, Div, Z_surf, T, *shape, 1.0, 1.0, 1.0, 1.0, 1.0, 1000.0],
                      device="cpu")
            wp.synchronize()
            solved_pressure = P_new.numpy()
            U, V, W = (self._wp_array(a) for a in (u, v, w_after_pressure_solve))
            wp.launch(kernel=project_velocity_kernel, dim=shape,
                      inputs=[U, V, W, P_new, Z_surf, T, *shape, 1.0, 1.0, 1.0, 1.0, 1.0, 1000.0],
                      device="cpu")
            Div_after = wp.zeros(shape, dtype=float, device="cpu")
            wp.launch(kernel=compute_divergence_kernel, dim=shape,
                      inputs=[U, V, W, Div_after, Z_surf, T, *shape, 1.0, 1.0, 1.0, 1000.0],
                      device="cpu")
            wp.synchronize()
            self.assertLess(abs(Div_after.numpy()[2, 2, 2]), 1e-6)
            self.assertAlmostEqual(solved_pressure[2, 2, 2], -3.0, delta=1e-6)

        def test_pcg_reduces_smooth_divergence_on_small_and_medium_grids(self):
            for n in (9, 17):
                shape = (n, n, n)
                temperature = np.full(shape, 2000.0, dtype=np.float32)
                surface = np.full((n, n), (n - 2.5), dtype=np.float32)
                active = (slice(1, -1), slice(1, -1), slice(1, -1))
                velocity = [np.zeros(shape, dtype=np.float32) for _ in range(3)]
                for i in range(1, n - 2):
                    velocity[0][i, 2:-2, 2:-2] = np.sin(np.pi * i / (n - 2))
                before, after, _, status, iterations, linear_r2, scale2, _ = self._run_pressure_projection(
                    velocity, temperature, surface, _PRESSURE_PCG_MAX_ITERATIONS,
                    dt=1.0, rho=1.0,
                )
                before_norm = np.linalg.norm(before[active].ravel())
                after_norm = np.linalg.norm(after[active].ravel())
                relative_residual = after_norm / before_norm
                linear_relative = np.sqrt(linear_r2 / scale2) if scale2 > 0 else 0.0
                self.assertEqual(status, _PRESSURE_STATUS_CONVERGED)
                self.assertGreater(iterations, 0)
                self.assertLessEqual(relative_residual, _PRESSURE_RELATIVE_DIVERGENCE_TOLERANCE)
                self.assertGreater(linear_relative, 0.0)
                self.assertLessEqual(linear_relative, _PRESSURE_RELATIVE_DIVERGENCE_TOLERANCE)

        def test_pcg_recovers_manufactured_exact_pressure_with_solid_and_air_faces(self):
            shape = (9, 9, 9)
            nx, ny, nz = shape
            spacing = (0.7, 1.1, 1.3)
            dx, dy, dz = spacing
            temperature = np.full(shape, 2000.0, dtype=np.float32)
            temperature[4, 4, 3] = 300.0  # insulating solid inclusion
            surface = np.full((nx, ny), 6.5 * dz, dtype=np.float32)
            surface[4, 3] = surface[4, 4] = 2.5 * dz  # stepped geometric air
            exact = np.zeros(shape, dtype=np.float32)
            exact[:] = np.fromfunction(
                lambda i, j, k: np.sin(0.31 * i) * np.cos(0.27 * j) * np.sin(0.19 * k),
                shape, dtype=float,
            ).astype(np.float32)
            exact[temperature < 1000.0] = 0.0
            A_exact = self._pressure_apply_host(exact, temperature, surface, spacing)
            dt, rho = 0.3, 2.0
            div = (-A_exact * dt / rho).astype(np.float32)
            solved, status, iterations, relative = self._solve_pressure(
                div, temperature, surface, spacing=spacing, dt=dt, rho=rho, max_iterations=200
            )
            active = np.zeros(shape, dtype=bool)
            for i in range(nx):
                for j in range(ny):
                    for k in range(nz):
                        active[i, j, k] = self._pressure_cell_class_host(
                            temperature, surface, i, j, k, dz
                        ) == 1
            error = np.linalg.norm((solved - exact)[active]) / np.linalg.norm(exact[active])
            self.assertEqual(status, _PRESSURE_STATUS_CONVERGED)
            self.assertLessEqual(relative, _PRESSURE_RELATIVE_DIVERGENCE_TOLERANCE)
            self.assertLess(error, 2e-3)
            self.assertGreater(iterations, 0)

        def test_pcg_all_neumann_constant_pressure_and_zero_rhs_nullspace(self):
            shape = (7, 7, 7)
            temperature = np.full(shape, 2000.0, dtype=np.float32)
            surface = np.full((shape[0], shape[1]), (shape[2] - 2.0), dtype=np.float32)
            # A solid cap closes the liquid component from the open top plane.
            temperature[:, :, shape[2] - 2] = 300.0
            div = np.zeros(shape, dtype=np.float32)
            initial_pressure = np.full(shape, 7.0, dtype=np.float32)
            solved, status, iterations, relative = self._solve_pressure(
                div, temperature, surface, initial_pressure=initial_pressure, max_iterations=20
            )
            self.assertEqual(status, _PRESSURE_STATUS_CONVERGED)
            self.assertEqual(iterations, 0)
            self.assertEqual(relative, 0.0)
            active = temperature[1:-1, 1:-1, 1:-1] >= 1000.0
            self.assertTrue(np.allclose(solved[1:-1, 1:-1, 1:-1][active], 7.0))

        def test_pcg_rejects_incompatible_rhs_in_closed_neumann_component(self):
            shape = (9, 9, 9)
            temperature = np.full(shape, 300.0, dtype=np.float32)
            surface = np.full(shape[:2], shape[2] - 2.0, dtype=np.float32)
            temperature[3, 3, 3] = temperature[4, 3, 3] = 2000.0
            div = np.zeros(shape, dtype=np.float32)
            div[3, 3, 3] = div[4, 3, 3] = 1.0
            _, status, _, relative = self._solve_pressure(
                div, temperature, surface, max_iterations=30
            )
            self.assertEqual(status, _PRESSURE_STATUS_NUMERICAL_FAILURE)
            self.assertGreater(relative, _PRESSURE_RELATIVE_DIVERGENCE_TOLERANCE)

        def test_pcg_solves_two_disconnected_compatible_neumann_components(self):
            shape = (10, 10, 10)
            spacing = (0.8, 1.1, 1.3)
            temperature = np.full(shape, 300.0, dtype=np.float32)
            surface = np.full(shape[:2], shape[2] - 2.0, dtype=np.float32)
            components = (((2, 2, 2), (3, 2, 2)), ((6, 6, 6), (7, 6, 6)))
            for first, second in components:
                temperature[first] = temperature[second] = 2000.0
            exact = np.zeros(shape, dtype=np.float32)
            exact[2, 2, 2], exact[3, 2, 2] = -1.0, 2.0
            exact[6, 6, 6], exact[7, 6, 6] = 4.0, 7.0
            rhs = self._pressure_apply_host(exact, temperature, surface, spacing)
            solved, status, iterations, relative = self._solve_pressure(
                -rhs.astype(np.float32), temperature, surface,
                spacing=spacing, max_iterations=30,
            )
            self.assertEqual(status, _PRESSURE_STATUS_CONVERGED)
            self.assertGreater(iterations, 0)
            self.assertLessEqual(relative, _PRESSURE_RELATIVE_DIVERGENCE_TOLERANCE)
            for first, second in components:
                self.assertAlmostEqual(
                    solved[second] - solved[first], exact[second] - exact[first], delta=2e-5
                )

        def test_pcg_rejects_opposite_incompatibilities_across_disconnected_components(self):
            shape = (10, 10, 10)
            temperature = np.full(shape, 300.0, dtype=np.float32)
            surface = np.full(shape[:2], shape[2] - 2.0, dtype=np.float32)
            for first, second in (((2, 2, 2), (3, 2, 2)), ((6, 6, 6), (7, 6, 6))):
                temperature[first] = temperature[second] = 2000.0
            div = np.zeros(shape, dtype=np.float32)
            div[2, 2, 2] = 1.0
            div[6, 6, 6] = -1.0
            _, status, _, relative = self._solve_pressure(
                div, temperature, surface, max_iterations=30
            )
            self.assertEqual(status, _PRESSURE_STATUS_NUMERICAL_FAILURE)
            self.assertGreater(relative, _PRESSURE_RELATIVE_DIVERGENCE_TOLERANCE)

        def test_pcg_reports_budget_exhaustion_and_nonfinite_rhs(self):
            n = 17
            shape = (n, n, n)
            temperature = np.full(shape, 2000.0, dtype=np.float32)
            surface = np.full((n, n), n - 2.5, dtype=np.float32)
            velocity = [np.zeros(shape, dtype=np.float32) for _ in range(3)]
            for i in range(1, n - 2):
                velocity[0][i, 2:-2, 2:-2] = np.sin(np.pi * i / (n - 2))
            before, _, _, status, iterations, residual2, scale2, _ = self._run_pressure_projection(
                velocity, temperature, surface, 1, dt=1.0, rho=1.0
            )
            self.assertEqual(status, _PRESSURE_STATUS_BUDGET_EXHAUSTED)
            self.assertEqual(iterations, 1)
            self.assertGreater(np.sqrt(residual2 / scale2), _PRESSURE_RELATIVE_DIVERGENCE_TOLERANCE)

            bad_div = np.zeros(shape, dtype=np.float32)
            bad_div[3, 3, 3] = np.nan
            _, bad_status, _, _ = self._solve_pressure(bad_div, temperature, surface, max_iterations=5)
            self.assertEqual(bad_status, _PRESSURE_STATUS_NUMERICAL_FAILURE)

        def test_velocity_advection_interpolates_transverse_face_velocity(self):
            shape = (5, 5, 5)
            dx = dy = dz = 1.0
            dt = 0.1
            U = np.zeros(shape, dtype=np.float32)
            V = np.zeros(shape, dtype=np.float32)
            W = np.zeros(shape, dtype=np.float32)
            U[1, 2, 2] = 1.0  # remove the x-gradient so only transverse transport acts
            U[2, 2, 2] = 1.0
            V[2, 1, 2] = V[2, 2, 2] = 2.0
            V[3, 1, 2] = V[3, 2, 2] = 2.0
            temperature = np.full(shape, 2000.0, dtype=np.float32)
            surface = np.full((shape[0], shape[1]), 4.5 * dz, dtype=np.float32)
            arrays = [self._wp_array(values) for values in (U, V, W)]
            outputs = [wp.zeros(shape, dtype=float, device="cpu") for _ in range(3)]
            wp.launch(
                kernel=velocity_advection_forces_kernel, dim=shape,
                inputs=[*arrays, *outputs, self._wp_array(temperature), self._wp_array(surface),
                        *shape, dx, dy, dz, dt, 0.0, 1.0, 0.0, 0.0,
                        1928.0, 1878.0, 0.0, 0.0, 1.0, 3000.0],
                device="cpu",
            )
            wp.synchronize()
            # Four surrounding V faces bilinearly interpolate to 2 at this U face.
            # With dU/dy = 1 and no other gradient, U_new = 1 - 2*dt.
            self.assertAlmostEqual(outputs[0].numpy()[2, 2, 2], 1.0 - 2.0 * dt, delta=1e-6)

        def test_all_six_transverse_mac_interpolants_use_four_surrounding_faces(self):
            shape = (5, 5, 5)
            values = np.fromfunction(lambda i, j, k: 100.0 * i + 10.0 * j + k,
                                     shape, dtype=float).astype(np.float32)
            temperature = np.full(shape, 2000.0, dtype=np.float32)
            surface = np.full((shape[0], shape[1]), 4.5, dtype=np.float32)
            result = wp.zeros(6, dtype=float, device="cpu")
            wp.launch(
                kernel=_probe_transverse_interpolants, dim=1,
                inputs=[self._wp_array(values), self._wp_array(values), self._wp_array(values),
                        self._wp_array(temperature), self._wp_array(surface), result,
                        *shape, 1.0, 1000.0],
                device="cpu",
            )
            wp.synchronize()
            np.testing.assert_allclose(
                result.numpy(), [267.0, 271.5, 177.0, 216.5, 171.5, 216.5], atol=1e-6
            )

        def test_divergence_free_upwind_enthalpy_flux_conserves_global_sum(self):
            shape = (7, 7, 5)
            nx, ny, nz = shape
            dx = dy = dz = 1.0
            dt = 0.01
            temperature = np.full(shape, 2000.0, dtype=np.float32)
            enthalpy = np.fromfunction(
                lambda i, j, k: 1.0e6 + 17.0 * i * i + 11.0 * j + 3.0 * k * k,
                shape, dtype=float,
            ).astype(np.float32)
            surface = np.full((nx, ny), 4.5 * dz, dtype=np.float32)

            # A discrete streamfunction creates nonzero MAC face velocities with
            # zero divergence and zero normal velocity at the active-domain edge.
            psi = np.zeros((nx + 1, ny + 1), dtype=np.float32)
            for i in range(2, nx - 1):
                for j in range(2, ny - 1):
                    psi[i, j] = np.sin(0.7 * i) * np.sin(0.4 * j)
            U = np.zeros(shape, dtype=np.float32)
            V = np.zeros(shape, dtype=np.float32)
            W = np.zeros(shape, dtype=np.float32)
            for i in range(nx - 1):
                for j in range(ny):
                    U[i, j, 2] = psi[i + 1, j + 1] - psi[i + 1, j]
            for i in range(nx):
                for j in range(ny - 1):
                    V[i, j, 2] = -(psi[i + 1, j + 1] - psi[i, j + 1])

            divergence = wp.zeros(shape, dtype=float, device="cpu")
            wp.launch(
                kernel=compute_divergence_kernel, dim=shape,
                inputs=[self._wp_array(U), self._wp_array(V), self._wp_array(W), divergence,
                        self._wp_array(surface), self._wp_array(temperature),
                        *shape, dx, dy, dz, 1878.0],
                device="cpu",
            )
            wp.synchronize()
            self.assertLess(np.max(np.abs(divergence.numpy()[1:-1, 1:-1, 1:-1])), 1e-6)

            T = self._wp_array(temperature)
            H = self._wp_array(enthalpy)
            Uw, Vw, Ww = (self._wp_array(a) for a in (U, V, W))
            T_new = wp.zeros(shape, dtype=float, device="cpu")
            H_new = wp.zeros(shape, dtype=float, device="cpu")
            empty = wp.array([], dtype=float, device="cpu")
            wp.launch(
                kernel=enthalpy_3d_nonlinear_step_kernel, dim=shape,
                inputs=[T, H, Uw, Vw, Ww, T_new, H_new, self._wp_array(surface),
                        *shape, dx, dy, dz, dt, 0.0,
                        4420.0, 2.9e5, 1878.0, 1928.0,
                        empty, empty, empty, empty, 0,
                        30e-6, 0.4, 0.0, 0.0, 300.0,
                        0.0, 9.7e6, 173.93, 3533.0,
                        670.0, 730.0, 15.0, 25.0],
                device="cpu",
            )
            wp.synchronize()

            interior = (slice(1, -1), slice(1, -1), slice(1, -1))
            initial_sum = np.sum(enthalpy[interior], dtype=np.float64)
            final_sum = np.sum(H_new.numpy()[interior], dtype=np.float64)
            self.assertAlmostEqual(final_sum, initial_sum, delta=0.125)


    if __name__ == "__main__":
        unittest.main()
