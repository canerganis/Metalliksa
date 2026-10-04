"""Full-field CPU/CUDA parity for the bounded Phase 22 production path."""

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

    from lpbf_transient_3d_gpu import TransientEnthalpy3DGPU
    from phase22_legacy_test_material import LEGACY_SOLVER_TEST_MATERIAL


    CASE = {
        "shape": (5, 5, 5),
        "spacing_m": 1.0e-5,
        "initial_temperature_K": 1700.0,
        "toolpath": {
            "t": [0.0, 6.0e-6],
            "x": [2.0e-5, 2.0e-5],
            "y": [2.0e-5, 2.0e-5],
            "p": [25.0, 25.0],
        },
    }

    # Tolerances are fixed from expected single-precision backend differences,
    # independently of the CPU/CUDA values observed by this test.
    TOLERANCES = {
        "temperature_max_abs_K": 0.05,
        "enthalpy_relative_l2": 2.0e-5,
        "velocity_max_abs_m_s": 1.0e-5,
        "pressure_relative_l2": 2.0e-5,
        "surface_max_abs_m": 5.0e-8,
    }


    def _run(device):
        nx, ny, nz = CASE["shape"]
        solver = TransientEnthalpy3DGPU(
            nx=nx, ny=ny, nz=nz,
            dx=CASE["spacing_m"], dy=CASE["spacing_m"], dz=CASE["spacing_m"],
        )
        solver.device = device
        return solver.solve_toolpath(
            CASE["toolpath"], T_preheat_K=CASE["initial_temperature_K"],
            include_diagnostic_fields=True, **LEGACY_SOLVER_TEST_MATERIAL,
        )


    def _relative_l2(left, right):
        scale = max(float(np.linalg.norm(left.ravel())), 1.0e-30)
        return float(np.linalg.norm((left - right).ravel()) / scale)


    @unittest.skipUnless(wp.get_cuda_device_count() > 0, "Warp CUDA device unavailable")
    class Phase22FullFieldCudaParity(unittest.TestCase):
        def test_full_thermal_hydrodynamic_fields_cpu_cuda(self):
            wp.config.use_precompiled_headers = False
            cpu = _run("cpu")
            cuda = _run("cuda:0")
            self.assertGreater(cpu["steps"], 0)
            self.assertEqual(cpu["steps"], cuda["steps"])

            cpu_fields = cpu["diagnostic_fields"]
            cuda_fields = cuda["diagnostic_fields"]
            self.assertEqual(set(cpu_fields), set(cuda_fields))
            for name in cpu_fields:
                self.assertEqual(cpu_fields[name].shape, cuda_fields[name].shape, name)
                self.assertTrue(np.isfinite(cpu_fields[name]).all(), name)
                self.assertTrue(np.isfinite(cuda_fields[name]).all(), name)

            self.assertLessEqual(
                float(np.max(np.abs(cpu_fields["temperature_K"] - cuda_fields["temperature_K"]))),
                TOLERANCES["temperature_max_abs_K"],
            )
            self.assertLessEqual(
                _relative_l2(cpu_fields["enthalpy_J_m3"], cuda_fields["enthalpy_J_m3"]),
                TOLERANCES["enthalpy_relative_l2"],
            )
            cpu_velocity = np.stack([cpu_fields[f"velocity_{axis}_m_s"] for axis in "xyz"])
            cuda_velocity = np.stack([cuda_fields[f"velocity_{axis}_m_s"] for axis in "xyz"])
            self.assertLessEqual(
                float(np.max(np.abs(cpu_velocity - cuda_velocity))),
                TOLERANCES["velocity_max_abs_m_s"],
            )
            self.assertLessEqual(
                _relative_l2(cpu_fields["pressure_Pa"], cuda_fields["pressure_Pa"]),
                TOLERANCES["pressure_relative_l2"],
            )
            self.assertLessEqual(
                float(np.max(np.abs(cpu_fields["surface_z_m"] - cuda_fields["surface_z_m"]))),
                TOLERANCES["surface_max_abs_m"],
            )

        def test_diagnostic_fields_are_opt_in(self):
            solver = TransientEnthalpy3DGPU(nx=3, ny=3, nz=3, dx=1.0e-5, dy=1.0e-5, dz=1.0e-5)
            solver.device = "cpu"
            result = solver.solve_toolpath(
                {"t": [0.0], "x": [0.0], "y": [0.0], "p": [0.0]},
                T_preheat_K=300.0, **LEGACY_SOLVER_TEST_MATERIAL,
            )
            self.assertNotIn("diagnostic_fields", result)

        def test_full_field_diagnostics_reject_oversized_mesh(self):
            solver = TransientEnthalpy3DGPU(nx=47, ny=47, nz=46, dx=1.0e-5, dy=1.0e-5, dz=1.0e-5)
            with self.assertRaisesRegex(ValueError, "limited to 100000 cells"):
                solver.solve_toolpath(
                    {"t": [0.0], "x": [0.0], "y": [0.0], "p": [0.0]},
                    include_diagnostic_fields=True, **LEGACY_SOLVER_TEST_MATERIAL,
                )


    if __name__ == "__main__":
        unittest.main()
