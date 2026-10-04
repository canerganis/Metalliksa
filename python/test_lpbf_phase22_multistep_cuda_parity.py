"""Frozen multistep CPU/CUDA smoke for the production Phase 22 solver path.

The case and acceptance limits below are fixed before running it. This is one
small deterministic case, not a claim of broad backend equivalence or physical
validation.
"""

import unittest

import numpy as np
import warp as wp

from lpbf_transient_3d_gpu import TransientEnthalpy3DGPU
from phase22_legacy_test_material import LEGACY_SOLVER_TEST_MATERIAL


# Frozen inputs: small 5^3 mesh, 10 um spacing, 6 us duration, solid initial
# condition and a centered 25 W stationary path. This should exercise thermal
# evolution into the phase-change range as well as the coupled flow update.
CASE = {
    "shape": (5, 5, 5),
    "spacing_m": 1.0e-5,
    "duration_s": 6.0e-6,
    "initial_temperature_K": 1700.0,
    "toolpath": {
        "t": [0.0, 6.0e-6],
        "x": [2.0e-5, 2.0e-5],
        "y": [2.0e-5, 2.0e-5],
        "p": [25.0, 25.0],
    },
}

# Frozen acceptance limits, chosen before the CPU/CUDA observations below.
TOLERANCES = {
    "max_temperature_abs_K": 0.05,
    "max_velocity_rel": 2.0e-3,
    "surface_recession_abs_um": 0.05,
    "pressure_linear_residual_abs": 2.0e-5,
    "post_projection_divergence_rel_abs": 2.0e-5,
    "post_projection_divergence_max_scaled_rel": 2.0e-5,
    "energy_ledger_closure_relative_max": 1.0e-3,
    "energy_terms_absorbed_scale_rel": 1.0e-5,
}


def _run(device):
    nx, ny, nz = CASE["shape"]
    dx = CASE["spacing_m"]
    solver = TransientEnthalpy3DGPU(nx=nx, ny=ny, nz=nz, dx=dx, dy=dx, dz=dx)
    solver.device = device
    result = solver.solve_toolpath(
        CASE["toolpath"], T_preheat_K=CASE["initial_temperature_K"],
        include_energy_ledger=True, **LEGACY_SOLVER_TEST_MATERIAL,
    )
    return result


@unittest.skipUnless(wp.get_cuda_device_count() > 0, "Warp CUDA device unavailable")
class Phase22MultistepCudaParity(unittest.TestCase):
    def test_production_path_cpu_cuda_parity(self):
        # NVRTC's PCH temp directory is ACL-blocked on this Windows host; the
        # regular compilation path is otherwise supported by Warp.
        wp.config.use_precompiled_headers = False
        cuda_device = "cuda:0"
        self.assertIn(cuda_device, [str(device) for device in wp.get_cuda_devices()])

        cpu = _run("cpu")
        cuda = _run(cuda_device)

        for result, expected_device in ((cpu, "cpu"), (cuda, cuda_device)):
            self.assertEqual(result["device"], expected_device)
            self.assertGreater(result["steps"], 0)
            self.assertEqual(result["pressure_projection_solver"],
                             "preconditioned_conjugate_gradient")
            self.assertEqual(result["pressure_projection_status"], "converged")
            self.assertTrue(result["pressure_projection_converged"])
            self.assertGreater(result["pressure_projection_total_iterations"], 0)
            self.assertGreater(result["max_velocity_m_s"], 0.0)
            self.assertGreater(result["max_temperature_K"],
                               CASE["initial_temperature_K"] + 1.0)
            self.assertGreater(result["melt_volume_um3"], 0.0)
            self.assertNotAlmostEqual(
                result["max_temperature_K"], CASE["initial_temperature_K"], delta=1e-8
            )
            for field in (
                "pressure_projection_relative_linear_residual",
                "pressure_projection_post_divergence_relative_l2",
                "pressure_projection_post_divergence_max_s_inv",
            ):
                self.assertTrue(np.isfinite(result[field]), field)

        self.assertEqual(cpu["steps"], cuda["steps"])

        # The max-divergence scalar has units of 1/s. Normalize its backend
        # difference by the characteristic transport rate U/h before applying
        # a dimensionless tolerance, so mesh and case scale remain explicit.
        transport_rate_scale = max(
            cpu["max_velocity_m_s"], cuda["max_velocity_m_s"], 1e-30
        ) / CASE["spacing_m"]
        max_divergence_delta_scaled = abs(
            cpu["pressure_projection_post_divergence_max_s_inv"]
            - cuda["pressure_projection_post_divergence_max_s_inv"]
        ) / transport_rate_scale
        self.assertLessEqual(
            max_divergence_delta_scaled,
            TOLERANCES["post_projection_divergence_max_scaled_rel"],
        )

        self.assertLessEqual(
            abs(cpu["max_temperature_K"] - cuda["max_temperature_K"]),
            TOLERANCES["max_temperature_abs_K"],
        )
        velocity_scale = max(abs(cpu["max_velocity_m_s"]), 1e-30)
        self.assertLessEqual(
            abs(cpu["max_velocity_m_s"] - cuda["max_velocity_m_s"]) / velocity_scale,
            TOLERANCES["max_velocity_rel"],
        )
        self.assertLessEqual(
            abs(cpu["keyhole_depth_um"] - cuda["keyhole_depth_um"]),
            TOLERANCES["surface_recession_abs_um"],
        )
        self.assertEqual(cpu["melt_volume_um3"], cuda["melt_volume_um3"])
        self.assertLessEqual(
            abs(cpu["pressure_projection_relative_linear_residual"]
                - cuda["pressure_projection_relative_linear_residual"]),
            TOLERANCES["pressure_linear_residual_abs"],
        )
        self.assertLessEqual(
            abs(cpu["pressure_projection_post_divergence_relative_l2"]
                - cuda["pressure_projection_post_divergence_relative_l2"]),
            TOLERANCES["post_projection_divergence_rel_abs"],
        )

        cpu_ledger = cpu["energy_ledger"]
        cuda_ledger = cuda["energy_ledger"]
        for ledger in (cpu_ledger, cuda_ledger):
            self.assertLessEqual(
                ledger["closure"]["relative_error"],
                TOLERANCES["energy_ledger_closure_relative_max"],
            )
        nominal_absorbed = cpu_ledger["laser_reference"]["nominal_absorbed_J"]
        energy_difference_limit = (
            TOLERANCES["energy_terms_absorbed_scale_rel"] * nominal_absorbed
        )
        self.assertEqual(set(cpu_ledger["terms_J"]), set(cuda_ledger["terms_J"]))
        for term in cpu_ledger["terms_J"]:
            self.assertLessEqual(
                abs(cpu_ledger["terms_J"][term] - cuda_ledger["terms_J"][term]),
                energy_difference_limit,
                term,
            )
        self.assertLessEqual(
            abs(cpu_ledger["enthalpy_J"]["change_total"]
                - cuda_ledger["enthalpy_J"]["change_total"]),
            energy_difference_limit,
        )
        self.assertLessEqual(
            abs(cpu_ledger["closure"]["relative_error"]
                - cuda_ledger["closure"]["relative_error"]),
            TOLERANCES["post_projection_divergence_rel_abs"],
        )


if __name__ == "__main__":
    unittest.main()
