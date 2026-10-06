"""Independent integral energy accounting for the shared CPU transient.

This is a software-consistency check for the implemented equations. It does not
validate the Gaussian beam, assumed absorptivity, material properties, or model
against experiment.
"""
import inspect
import math
import unittest
from unittest.mock import patch

import numpy as np

import lpbf_simulation
from lpbf_core_physics import calculate_mesh_domain
from lpbf_simulation import scan_segments, transient, validate


class SharedThermalEnergyOracle(unittest.TestCase):
    def test_full_transient_integral_matches_independent_source_and_boundary_accounting(self):
        raw = {
            "mode": "standard",
            "backend": "reference",
            "material": "316L Stainless Steel",
            "power_W": 15,
            "mesh_um": 40,
            "trackLength_um": 100,
            "speed_mm_s": 800,
            "layer_um": 40,
            "layers": 1,
            "tracks": 1,
            "dwell_s": 0,
            "cooling_s": 20e-6,
            "maxDt_s": 5e-6,
        }
        p, material = validate(raw)
        domain = calculate_mesh_domain(p)
        cell_count = domain["nx"] * domain["ny"] * domain["nz"]
        _, end_s = scan_segments(p)
        max_steps = 2_000
        max_cell_steps = 2_000_000
        self.assertLessEqual(cell_count, 10_000, "oracle mesh preflight")
        self.assertLessEqual(math.ceil(end_s / p["maxDt_s"]), max_steps,
                             "requested-dt lower-bound preflight")
        self.assertLessEqual(cell_count * max_steps, max_cell_steps,
                             "hard worst-case cell-step preflight")

        dx = domain["dx"]
        volume = dx ** 3
        expected_absorbed_power_W = p["power_W"] * material["absorptivity"]
        sigma = 5.670374419e-8  # W m^-2 K^-4, same fixed SI constant as the BC.
        independent_input_J = 0.0
        independent_loss_J = 0.0
        accepted_dt = []
        cell_steps = 0
        final_state = []
        solver_source_limiter = lpbf_simulation.source_limited_step

        def intercept_accepted_source_step(*args, **kwargs):
            nonlocal independent_input_J, independent_loss_J, cell_steps
            # Positional contract at the single source-limiter seam in transient:
            # axis, z, dx, segment, time, dt, surface, radius, penetration, power, ...
            segment = args[3]
            nominal_absorbed_power_W = args[9]
            result = solver_source_limiter(*args, **kwargs)
            accepted_dt_s = float(result[0])
            self.assertTrue(math.isfinite(accepted_dt_s) and accepted_dt_s > 0)

            frame = inspect.currentframe().f_back
            local = frame.f_locals
            old_temperature = local["T"].copy()
            conductivity = local["k"].copy()
            top_index = int(local["top_index"])
            preheat_K = float(local["t0"])
            step_dx = float(local["dx"])
            self.assertEqual(step_dx, dx)
            self.assertAlmostEqual(nominal_absorbed_power_W,
                                   expected_absorbed_power_W, delta=1e-12)

            # Independent input integral: laser-off intervals have no beam
            # input; in an accepted laser-on interval the configured absorbed
            # power is W and the actual accepted interval is seconds.
            if segment is not None:
                independent_input_J += expected_absorbed_power_W * accepted_dt_s

            # Reconstruct the explicit boundary fluxes from the pre-update
            # material/temperature state. Each expression below is a rate
            # density [W/m^3]; multiplying by voxel volume [m^3] and dt [s]
            # gives energy [J]. Interior harmonic face fluxes cancel in pairs
            # because all voxels have the same volume.
            bottom_rate_W_m3 = (2.0 * conductivity[:, :, 0]
                                * (old_temperature[:, :, 0] - preheat_K) / step_dx**2)
            top_temperature_K = old_temperature[:, :, top_index]
            top_rate_W_m3 = (
                p["convection_W_m2K"] * (top_temperature_K - preheat_K)
                + material["emissivity"] * sigma
                * (top_temperature_K**4 - preheat_K**4)
            ) / step_dx
            independent_loss_J += (
                float(np.sum(bottom_rate_W_m3, dtype=np.float64))
                + float(np.sum(top_rate_W_m3, dtype=np.float64))
            ) * volume * accepted_dt_s

            accepted_dt.append(accepted_dt_s)
            cell_steps += cell_count
            if len(accepted_dt) > max_steps or cell_steps > max_cell_steps:
                raise AssertionError("runtime timestep/cell-step guard exceeded")
            return result

        with patch.object(lpbf_simulation, "source_limited_step", intercept_accepted_source_step):
            result = transient(p, material, final_state_observer=final_state.append)

        self.assertEqual(len(final_state), 1)
        state = final_state[0]
        observed_stored_J = float(np.sum(state["enthalpy_J_m3"], dtype=np.float64)) * float(state["cell_volume_m3"])
        self.assertEqual(float(state["cell_volume_m3"]), volume)
        self.assertEqual(len(accepted_dt), result["discretization"]["steps"])
        self.assertAlmostEqual(math.fsum(accepted_dt), end_s, delta=1e-12)
        self.assertGreater(independent_input_J, 0.0)
        expected_stored_J = independent_input_J - independent_loss_J
        self.assertGreater(expected_stored_J, 0.0)

        # Bound float64 accumulation/reduction roundoff by accepted update
        # count and the magnitude of independently integrated energy terms.
        # This is intentionally not a model-discretization or experimental gate.
        scale_J = (abs(independent_input_J) + abs(independent_loss_J)
                   + abs(expected_stored_J) + abs(observed_stored_J))
        tolerance_J = (512.0 * np.finfo(np.float64).eps
                       * max(len(accepted_dt), cell_count) * max(scale_J, 1e-30))
        self.assertLessEqual(abs(observed_stored_J - expected_stored_J), tolerance_J,
                             msg=(f"independent integral mismatch: stored={observed_stored_J:.17g} J, "
                                  f"expected={expected_stored_J:.17g} J, "
                                  f"tolerance={tolerance_J:.3g} J"))


if __name__ == "__main__":
    unittest.main()
