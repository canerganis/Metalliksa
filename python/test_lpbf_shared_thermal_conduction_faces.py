import unittest

import numpy as np


class SharedThermalConductionFaceTests(unittest.TestCase):
    def test_heterogeneous_internal_faces_match_independent_assembly_and_conserve_power(self):
        from lpbf_simulation import conduction_rate

        # All three dimensions contain an internal face. The disabled high-
        # temperature corner checks that every face touching an inactive cell
        # is insulated, including faces on each coordinate axis.
        temperature_K = np.array(
            [
                [[500.0, 420.0], [380.0, 330.0]],
                [[310.0, 350.0], [340.0, 2000.0]],
            ],
            dtype=np.float64,
        )
        conductivity_W_mK = np.array(
            [
                [[8.0, 19.0], [31.0, 13.0]],
                [[42.0, 11.0], [23.0, 7.0]],
            ],
            dtype=np.float64,
        )
        active = np.ones(temperature_K.shape, dtype=bool)
        active[1, 1, 1] = False
        dx_m = 2.5e-4

        # Assemble each internal face once, independently of the production
        # vectorized face loop. Rates are volumetric (W/m^3), so each face's
        # conductance includes 1/dx^2 and contributes equal/opposite rates.
        expected_W_m3 = np.zeros_like(temperature_K)
        for cell in np.ndindex(temperature_K.shape):
            if not active[cell]:
                continue
            for axis in range(3):
                neighbor = list(cell)
                neighbor[axis] += 1
                if neighbor[axis] == temperature_K.shape[axis]:
                    continue
                neighbor = tuple(neighbor)
                if not active[neighbor]:
                    continue
                k_cell = conductivity_W_mK[cell]
                k_neighbor = conductivity_W_mK[neighbor]
                harmonic_k = 2.0 * k_cell * k_neighbor / (k_cell + k_neighbor)
                face_rate_W_m3 = (
                    harmonic_k
                    * (temperature_K[neighbor] - temperature_K[cell])
                    / dx_m**2
                )
                expected_W_m3[cell] += face_rate_W_m3
                expected_W_m3[neighbor] -= face_rate_W_m3

        actual_W_m3 = conduction_rate(temperature_K, conductivity_W_mK, active, dx_m)

        # Float64 operator parity tolerance is fixed before comparison.
        np.testing.assert_allclose(actual_W_m3, expected_W_m3, rtol=2e-14, atol=1e-10)
        self.assertLess(actual_W_m3[0, 0, 0], 0.0)
        self.assertGreater(actual_W_m3[1, 0, 0], 0.0)
        np.testing.assert_array_equal(actual_W_m3[~active], 0.0)

        # The integrated internal power must cancel after multiplying the
        # volumetric rate by the uniform cell volume.
        cell_volume_m3 = dx_m**3
        cell_power_W = actual_W_m3 * cell_volume_m3
        conservation_tolerance_W = (
            64.0
            * np.finfo(np.float64).eps
            * max(float(np.sum(np.abs(cell_power_W))), 1.0)
        )
        self.assertLessEqual(abs(float(np.sum(cell_power_W))), conservation_tolerance_W)

        # A doubled spacing changes each volumetric face rate by exactly 1/4.
        coarser_W_m3 = conduction_rate(
            temperature_K, conductivity_W_mK, active, 2.0 * dx_m
        )
        np.testing.assert_allclose(coarser_W_m3, actual_W_m3 / 4.0, rtol=2e-14, atol=1e-10)


if __name__ == "__main__":
    unittest.main()
