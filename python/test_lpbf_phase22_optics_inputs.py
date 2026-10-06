"""Wave B LT-4: the Phase 22 solver takes beam radius, A, h and emissivity as required inputs.

They used to be hard-coded launch constants (30 um, 0.4, 10 W/m^2K, 0.35). The checks run on the
Warp CPU device, so they need Warp but no CUDA.
"""

import unittest

try:
    import warp as _warp_probe  # noqa: F401
except ImportError as _warp_exc:
    _WARP_MISSING = str(_warp_exc)
else:
    _WARP_MISSING = None

OPTICS = ("beam_radius_m", "absorptivity", "h_conv_W_m2K", "emissivity")
TOOLPATH = {"t": [0.0, 2e-7], "x": [30e-6, 30e-6], "y": [30e-6, 30e-6], "p": [80.0, 80.0]}

if _WARP_MISSING is not None:
    @unittest.skip("warp is not installed in this interpreter: " + str(_WARP_MISSING))
    class WarpUnavailable(unittest.TestCase):
        def test_warp_unavailable(self):
            pass
else:
    from lpbf_transient_3d_gpu import TransientEnthalpy3DGPU
    from phase22_legacy_test_material import LEGACY_SOLVER_TEST_MATERIAL

    def _solver():
        solver = TransientEnthalpy3DGPU(nx=7, ny=7, nz=7, dx=10e-6, dy=10e-6, dz=10e-6)
        solver.device = "cpu"
        return solver

    class Phase22OpticsInputs(unittest.TestCase):
        def test_fixture_carries_the_former_launch_constants(self):
            self.assertEqual({k: LEGACY_SOLVER_TEST_MATERIAL[k] for k in OPTICS},
                             {"beam_radius_m": 30e-6, "absorptivity": 0.4,
                              "h_conv_W_m2K": 10.0, "emissivity": 0.35})

        def test_missing_optics_arguments_raise_type_error(self):
            material = {k: v for k, v in LEGACY_SOLVER_TEST_MATERIAL.items() if k not in OPTICS}
            for missing in OPTICS:
                with self.subTest(missing=missing):
                    kwargs = {**material, **{k: LEGACY_SOLVER_TEST_MATERIAL[k] for k in OPTICS if k != missing}}
                    with self.assertRaises(TypeError):
                        _solver().solve_toolpath(TOOLPATH, **kwargs)

        def test_out_of_range_optics_raise_before_launch(self):
            for name, bad in (("absorptivity", 1.2), ("absorptivity", 0.0), ("emissivity", -0.1),
                              ("beam_radius_m", 0.0), ("beam_radius_m", 2e-3), ("h_conv_W_m2K", -1.0),
                              ("absorptivity", float("nan")), ("emissivity", True)):
                with self.subTest(name=name, value=bad):
                    with self.assertRaises(ValueError):
                        _solver().solve_toolpath(TOOLPATH, **{**LEGACY_SOLVER_TEST_MATERIAL, name: bad})

        def test_absorptivity_scales_nominal_and_absorbed_energy(self):
            ledgers = {}
            for a in (0.2, 0.4):
                result = _solver().solve_toolpath(
                    TOOLPATH, include_energy_ledger=True,
                    **{**LEGACY_SOLVER_TEST_MATERIAL, "absorptivity": a})
                ledgers[a] = result["energy_ledger"]
            nominal = {a: _find(ledger, "nominal_absorbed_J") for a, ledger in ledgers.items()}
            self.assertIsNotNone(nominal[0.4])
            absorbed = {a: ledger["terms_J"]["laser_absorbed_in_J"] for a, ledger in ledgers.items()}
            self.assertAlmostEqual(nominal[0.2] / nominal[0.4], 0.5, delta=1e-6)
            self.assertAlmostEqual(absorbed[0.2] / absorbed[0.4], 0.5, delta=1e-6)

    def _find(tree, key):
        if isinstance(tree, dict):
            if key in tree:
                return tree[key]
            for value in tree.values():
                found = _find(value, key)
                if found is not None:
                    return found
        return None


if __name__ == "__main__":
    unittest.main()
