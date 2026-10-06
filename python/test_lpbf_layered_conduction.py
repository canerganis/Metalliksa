import unittest

import numpy as np

from lpbf_layered_conduction import conduction_heat_rate


class LayeredConductionTests(unittest.TestCase):
    def setUp(self):
        self.dx = 0.25
        self.resistance = 0.0

    def test_uniform_conductivity_matches_insulated_discrete_laplacian(self):
        temperature = np.arange(27, dtype=float).reshape(3, 3, 3) ** 1.2
        k = np.full_like(temperature, 12.0)
        actual = conduction_heat_rate(
            temperature, k, self.dx, contact_resistance_m2K_W=self.resistance
        )

        laplacian = np.zeros_like(temperature)
        for axis in range(3):
            for cell in np.ndindex(temperature.shape):
                for direction in (-1, 1):
                    neighbor = list(cell)
                    neighbor[axis] += direction
                    if 0 <= neighbor[axis] < temperature.shape[axis]:
                        laplacian[cell] += temperature[tuple(neighbor)] - temperature[cell]
        expected = k * self.dx * laplacian
        np.testing.assert_allclose(actual, expected, rtol=1e-13, atol=1e-12)

    def test_zero_resistance_marked_interface_matches_unmarked_face(self):
        temperature = np.array([[[400.0]], [[300.0]]])
        k = np.array([[[10.0]], [[30.0]]])
        mask = np.ones((1, 1, 1), dtype=bool)
        ordinary = conduction_heat_rate(
            temperature, k, self.dx, contact_resistance_m2K_W=0.0
        )
        marked = conduction_heat_rate(
            temperature, k, self.dx, contact_resistance_m2K_W=0.0,
            interface_z=mask,
        )
        np.testing.assert_array_equal(marked, ordinary)

    def test_positive_contact_resistance_reduces_interface_transfer(self):
        temperature = np.array([[[400.0]], [[300.0]]])
        k = np.full_like(temperature, 20.0)
        mask = np.ones((1, 1, 1), dtype=bool)
        ordinary = conduction_heat_rate(
            temperature, k, self.dx, contact_resistance_m2K_W=0.0,
            interface_z=mask,
        )
        resisted = conduction_heat_rate(
            temperature, k, self.dx, contact_resistance_m2K_W=0.01,
            interface_z=mask,
        )
        self.assertGreater(abs(ordinary[0, 0, 0]), abs(resisted[0, 0, 0]))
        self.assertLess(resisted[0, 0, 0], 0.0)
        self.assertAlmostEqual(resisted[0, 0, 0], -resisted[1, 0, 0])

    def test_internal_transfers_conserve_total_heat_rate(self):
        rng = np.random.default_rng(2026)
        temperature = rng.uniform(250.0, 1800.0, (5, 4, 3))
        k = rng.uniform(1.0, 100.0, temperature.shape)
        interfaces = rng.random((4, 4, 3)) > 0.6
        rate = conduction_heat_rate(
            temperature,
            k,
            self.dx,
            contact_resistance_m2K_W=0.002,
            interface_z=interfaces,
        )
        self.assertAlmostEqual(float(np.sum(rate)), 0.0, delta=1e-10)

    def test_face_touching_inactive_cell_is_insulated(self):
        temperature = np.array([[[400.0]], [[300.0]]])
        k = np.full_like(temperature, 20.0)
        active = np.array([[[True]], [[False]]])
        rate = conduction_heat_rate(
            temperature,
            k,
            self.dx,
            contact_resistance_m2K_W=0.005,
            interface_z=np.ones((1, 1, 1), dtype=bool),
            active_cells=active,
        )
        np.testing.assert_array_equal(rate, np.zeros_like(rate))

    def test_invalid_inputs_fail(self):
        temperature = np.ones((2, 2, 2))
        k = np.ones_like(temperature)
        kwargs = {"contact_resistance_m2K_W": 0.0}
        with self.assertRaises(ValueError):
            conduction_heat_rate(temperature, k, 0.0, **kwargs)
        with self.assertRaises(ValueError):
            conduction_heat_rate(temperature, np.zeros_like(k), self.dx, **kwargs)
        with self.assertRaises(ValueError):
            conduction_heat_rate(temperature, k, self.dx, contact_resistance_m2K_W=-1.0)
        with self.assertRaises(ValueError):
            conduction_heat_rate(temperature, k, True, **kwargs)
        with self.assertRaises(ValueError):
            conduction_heat_rate(temperature, k, self.dx, contact_resistance_m2K_W=True)
        with self.assertRaises(ValueError):
            conduction_heat_rate(
                temperature, k, self.dx, **kwargs, interface_z=np.zeros((2, 2, 2), dtype=bool)
            )
        with self.assertRaises(ValueError):
            conduction_heat_rate(
                temperature, k, self.dx, **kwargs, active_cells=np.ones((2, 2, 2))
            )
        with self.assertRaises(ValueError):
            conduction_heat_rate(temperature, k[:, :, :1], self.dx, **kwargs)


if __name__ == "__main__":
    unittest.main()
