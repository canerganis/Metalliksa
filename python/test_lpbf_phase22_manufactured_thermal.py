"""Independent Fourier-mode oracle for the production Phase 22 heat operator."""

import math
from pathlib import Path
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

    wp.config.use_precompiled_headers = False
    wp.config.kernel_cache_dir = str(Path(__file__).resolve().parent / ".tmp-phase22-manufactured-warp")

    from lpbf_transient_3d_gpu import enthalpy_3d_nonlinear_step_kernel


    RHO = 4420.0
    CP = 670.0
    K = 15.0
    ALPHA = K / (RHO * CP)
    BASE_K = 300.0
    AMPLITUDE_K = 10.0
    DOMAIN_M = 1.6e-3
    FINAL_TIME_S = 4.0e-3
    FOURIER_NUMBER = 0.1
    TEMPERATURE_RELATIVE_L2_MAX = 0.01
    ENERGY_RELATIVE_MAX = 0.01


    def _run_manufactured_mode(device, nx):
        """Run only the production enthalpy/conduction step on a solid sine mode."""
        ny = nz = nx
        dx = DOMAIN_M / (nx - 1)
        dy = dz = dx
        sine = np.sin(np.pi * np.arange(nx, dtype=np.float64) / (nx - 1))
        initial_mode = (AMPLITUDE_K * sine[:, None, None]
                        * sine[None, :, None] * sine[None, None, :])
        initial_temperature = BASE_K + initial_mode
        initial_enthalpy = RHO * CP * initial_temperature

        T = wp.array(initial_temperature, dtype=float, device=device)
        H = wp.array(initial_enthalpy, dtype=float, device=device)
        T_new = wp.zeros((nx, ny, nz), dtype=float, device=device)
        H_new = wp.zeros((nx, ny, nz), dtype=float, device=device)
        U, V, W = (wp.zeros((nx, ny, nz), dtype=float, device=device) for _ in range(3))
        # k_surf is the last z index, outside the interior update region. The
        # manufactured mode has homogeneous fixed-temperature values at all outer
        # nodes; no free-surface exchange is applied.
        Z_surf = wp.full((nx, ny), nz * dz, dtype=float, device=device)
        tp_t = wp.array([0.0, FINAL_TIME_S], dtype=float, device=device)
        tp_x = wp.zeros(2, dtype=float, device=device)
        tp_y = wp.zeros(2, dtype=float, device=device)
        tp_p = wp.zeros(2, dtype=float, device=device)

        stable_dt = FOURIER_NUMBER * dx * dx / ALPHA
        steps = math.ceil(FINAL_TIME_S / stable_dt)
        dt = FINAL_TIME_S / steps
        for step in range(steps):
            wp.launch(
                kernel=enthalpy_3d_nonlinear_step_kernel,
                dim=(nx, ny, nz),
                inputs=[
                    T, H, U, V, W, T_new, H_new, Z_surf,
                    nx, ny, nz, dx, dy, dz, dt, step * dt,
                    RHO, 2.9e5, 1000.0, 1100.0,
                    tp_t, tp_x, tp_y, tp_p, 2,
                    40e-6, 0.0, 0.0, 0.0, BASE_K,
                    0.0, 9.7e6, 173.93, 3533.0,
                    CP, CP, K, K,
                ],
                device=device,
            )
            T, T_new = T_new, T
            H, H_new = H_new, H
        wp.synchronize_device(device)

        time = steps * dt
        exact_sine = np.sin(np.pi * np.arange(nx, dtype=np.float64) / (nx - 1))
        # Exact 3-D Dirichlet eigenmode: u=A*sin(pi*x/L)*sin(pi*y/L)*sin(pi*z/L)
        # times exp(-alpha*(3*pi^2/L^2)*t), with alpha=k/(rho*cp).
        exact_mode = (AMPLITUDE_K * exact_sine[:, None, None]
                      * exact_sine[None, :, None] * exact_sine[None, None, :]
                      * np.exp(-3.0 * ALPHA * (np.pi / DOMAIN_M) ** 2 * time))
        exact_temperature = BASE_K + exact_mode
        actual_temperature = T.numpy().astype(np.float64)
        actual_enthalpy = H.numpy().astype(np.float64)
        volume = dx * dy * dz

        error = actual_temperature - exact_temperature
        exact_perturbation = exact_temperature - BASE_K
        relative_l2 = float(np.linalg.norm(error) / np.linalg.norm(exact_perturbation))
        actual_energy_change = float(np.sum(actual_enthalpy - initial_enthalpy) * volume)
        exact_energy_change = float(
            RHO * CP * np.sum(exact_temperature - initial_temperature) * volume
        )
        energy_relative_error = abs(actual_energy_change - exact_energy_change) / abs(exact_energy_change)
        return {
            "steps": steps,
            "dt_s": dt,
            "relative_l2": relative_l2,
            "energy_relative_error": energy_relative_error,
        }


    class Phase22ManufacturedThermal(unittest.TestCase):
        def test_cpu_fourier_mode_converges_to_independent_field_and_energy(self):
            results = [_run_manufactured_mode("cpu", nx) for nx in (9, 17, 33)]
            errors = [result["relative_l2"] for result in results]
            energy_errors = [result["energy_relative_error"] for result in results]
            for result in results:
                self.assertLessEqual(result["relative_l2"], TEMPERATURE_RELATIVE_L2_MAX)
                self.assertLessEqual(result["energy_relative_error"], ENERGY_RELATIVE_MAX)
                self.assertGreater(result["steps"], 0)
                self.assertGreater(result["dt_s"], 0.0)
            self.assertGreater(errors[0], errors[1])
            self.assertGreater(errors[1], errors[2])
            self.assertLess(errors[2] / errors[0], 0.35)
            self.assertGreater(energy_errors[0], energy_errors[1])
            self.assertGreater(energy_errors[1], energy_errors[2])
            self.assertLess(energy_errors[2] / energy_errors[0], 0.2)

        @unittest.skipUnless(wp.get_cuda_device_count() > 0, "Warp CUDA device unavailable")
        def test_explicit_cuda_fourier_mode_matches_independent_field_and_energy(self):
            result = _run_manufactured_mode("cuda:0", 33)
            self.assertLessEqual(result["relative_l2"], TEMPERATURE_RELATIVE_L2_MAX)
            self.assertLessEqual(result["energy_relative_error"], ENERGY_RELATIVE_MAX)


    if __name__ == "__main__":
        unittest.main()
