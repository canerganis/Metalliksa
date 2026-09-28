"""Independent manufactured-solution check for the shared conduction stencil.

This verifies spatial consistency of the insulated, constant-property operator;
it is not an LPBF validation or an energy-ledger test.
"""

import unittest

import numpy as np

from lpbf_simulation import conduction_rate


class ManufacturedConductionVerification(unittest.TestCase):
    def test_neumann_compatible_cosine_field_is_second_order(self):
        conductivity_W_mK = 2.0
        errors = []

        # Cell-centred cosine modes have zero normal gradient at every domain
        # boundary, matching the operator's insulated exterior faces.
        for n in (8, 16, 32, 64):
            dx_m = 1.0 / n
            coordinates = (np.arange(n, dtype=np.float64) + 0.5) * dx_m
            x, y, z = np.meshgrid(coordinates, coordinates, coordinates, indexing="ij")
            perturbation_K = (
                np.cos(np.pi * x) * np.cos(np.pi * y) * np.cos(np.pi * z)
            )
            temperature_K = 300.0 + perturbation_K
            conductivity = np.full(temperature_K.shape, conductivity_W_mK)
            active = np.ones(temperature_K.shape, dtype=bool)

            rate_W_m3 = conduction_rate(temperature_K, conductivity, active, dx_m)
            exact_rate_W_m3 = -3.0 * np.pi**2 * conductivity_W_mK * perturbation_K
            errors.append(float(np.sqrt(np.mean((rate_W_m3 - exact_rate_W_m3) ** 2))))

        refinement_ratios = [errors[i] / errors[i + 1] for i in range(len(errors) - 1)]
        # A factor of four is second order under 2x refinement; allow margin
        # for the coarsest grid while rejecting first-order behavior.
        for ratio in refinement_ratios:
            self.assertGreater(ratio, 3.8)


if __name__ == "__main__":
    unittest.main()
