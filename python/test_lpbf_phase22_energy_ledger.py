import unittest

import numpy as np
import warp as wp

from lpbf_transient_3d_gpu import TransientEnthalpy3DGPU
from phase22_legacy_test_material import LEGACY_SOLVER_TEST_MATERIAL


class Phase22EnergyLedger(unittest.TestCase):
    def test_energy_ledger_closes_against_independent_enthalpy_sum(self):
        solver = TransientEnthalpy3DGPU(
            nx=7, ny=7, nz=7, dx=10e-6, dy=10e-6, dz=10e-6,
        )
        solver.device = "cpu"
        initial_temperature = 300.0
        result = solver.solve_toolpath(
            {
                "t": [0.0, 2e-7],
                "x": [30e-6, 30e-6],
                "y": [30e-6, 30e-6],
                "p": [80.0, 80.0],
            },
            T_preheat_K=initial_temperature,
            include_diagnostic_fields=True,
            include_energy_ledger=True,
            **LEGACY_SOLVER_TEST_MATERIAL,
        )

        ledger = result["energy_ledger"]
        final_enthalpy = result["diagnostic_fields"]["enthalpy_J_m3"]
        cp = 670.0
        rho = 4420.0
        initial_enthalpy = rho * cp * initial_temperature
        cell_volume = solver.dx * solver.dy * solver.dz
        independent_change = float(
            np.sum(final_enthalpy.astype(np.float64) - initial_enthalpy, dtype=np.float64)
            * cell_volume
        )
        self.assertAlmostEqual(
            ledger["enthalpy_J"]["change_total"], independent_change,
            delta=max(abs(independent_change) * 1e-10, 1e-16),
        )
        self.assertGreater(ledger["terms_J"]["laser_absorbed_in_J"], 0.0)
        self.assertLess(ledger["closure"]["relative_error"], 1e-3)
        self.assertAlmostEqual(
            ledger["closure"]["residual_J"],
            ledger["enthalpy_J"]["change_total"] - ledger["closure"]["modeled_change_J"],
            delta=1e-16,
        )


if __name__ == "__main__":
    unittest.main()
