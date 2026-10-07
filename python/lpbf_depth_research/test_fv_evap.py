"""Unit tests of the evaporation term and the research fork (self-contained, CPU, < 1 min).

run: python -B python/lpbf_depth_research/test_fv_evap.py
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np

_PY = Path(__file__).resolve().parent.parent
if str(_PY) not in sys.path:
    sys.path.insert(0, str(_PY))

from lpbf_depth_research import evap_properties as E  # noqa: E402
from lpbf_depth_research import fv_evap as F  # noqa: E402

SMALL = dict(mode="standard", backend="reference", material="316L Stainless Steel", power_W=60.0, speed_mm_s=1000.0,
             beamDiameter_um=80.0, preheat_C=20.0, mesh_um=40.0, trackLength_um=100.0, evaporationModel=False,
             surfaceMode="bare-plate", barePlateGeometry="square", sourcePenetration_um=40.0)
HOT = dict(SMALL, power_W=300.0)


class EvaporationTerm(unittest.TestCase):
    def test_saturation_pressure_is_one_atmosphere_at_the_boiling_point(self):
        for name in ("316L Stainless Steel", "Ti-6Al-4V", "Inconel 718", "Inconel 625"):
            c = E.alloy_evaporation_constants(name)
            self.assertAlmostEqual(float(E.saturation_pressure(c["T_b_K"], c)), E.P_ATM, delta=1e-6)

    def test_mass_flux_against_hand_evaluation_of_the_cited_formula(self):
        # Gan 2021 SI Eq. 12 (high-intensity branch) with Eq. 13, SS316 constants of SI Table 1, beta_R 0.18:
        # m_dot(3500 K) = 0.82 sqrt(0.056/(2 pi 8.314 3500)) 1e5 exp(0.056 6.336e6/(8.314 3122) (1 - 3122/3500))
        c = E.alloy_evaporation_constants("316L Stainless Steel")
        T = 3500.0
        expo = 0.056 * 6.336e6 / (8.314 * 3122.0) * (1.0 - 3122.0 / T)
        hand = 0.82 * math.sqrt(0.056 / (2 * math.pi * 8.314 * T)) * 1e5 * math.exp(expo)
        self.assertAlmostEqual(float(E.mass_flux(T, c)) / hand, 1.0, places=12)
        self.assertAlmostEqual(float(E.heat_flux(T, c)) / (hand * 6.336e6), 1.0, places=12)
        self.assertGreater(hand, 10.0)  # kg/(m2 s): of order 1e1-1e2 at 1.12 T_b

    def test_heat_flux_derivative_matches_finite_difference(self):
        c = E.alloy_evaporation_constants("Ti-6Al-4V")
        for T in (3000.0, 3560.0, 4200.0):
            h = 1e-4 * T
            fd = (float(E.heat_flux(T + h, c)) - float(E.heat_flux(T - h, c))) / (2 * h)
            self.assertAlmostEqual(float(E.heat_flux_derivative(T, c)) / fd, 1.0, places=4)

    def test_additivity_method_reproduces_published_boiling_points(self):
        chk = E.method_checks()
        self.assertLess(abs(chk["IN718_raoult_K"] - 3120.0) / 3120.0, 0.02)   # Knapp 2019 Table 1
        self.assertLess(abs(chk["316L_raoult_K"] - 3090.0) / 3090.0, 0.01)    # Kim 1975 Eq. 14
        c625 = E.alloy_evaporation_constants("Inconel 625")
        self.assertTrue(3000.0 < c625["T_b_K"] < 3200.0)
        self.assertTrue(0.055 < c625["M_kg_mol"] < 0.065)

    def test_unknown_alloy_is_refused_not_substituted(self):
        with self.assertRaises(ValueError):
            E.alloy_evaporation_constants("AlSi10Mg")


class ForkSolver(unittest.TestCase):
    def test_surface_flux_source_deposits_the_absorbed_power_in_the_top_cell_only(self):
        dx = 20e-6
        axis = (np.arange(31) + .5) * dx - 31 * dx / 2
        axis_y = axis.copy()
        z = (np.arange(10) + .5) * dx - 10 * dx
        seg = dict(start_s=0.0, end_s=1e-4, start=[-50e-6, 0.0], end=[50e-6, 0.0])
        src, capture = F.surface_flux_source(axis, axis_y, z, dx, seg, 2e-5, 1e-6, 9, 40e-6, 84.0)
        self.assertAlmostEqual(float(src.sum()) * dx ** 3, 84.0, places=9)
        self.assertEqual(float(np.abs(src[:, :, :9]).max()), 0.0)
        self.assertGreater(capture, 0.999)

    def test_energy_balance_closes_with_the_evaporation_sink(self):
        r = F.run_case(HOT, evaporation=True, source_mode="surface-flux")
        e = r["energy"]
        self.assertLess(e["relativeResidual"], 1e-9)
        self.assertGreater(e["evaporated_J"], 0.0)
        self.assertAlmostEqual(e["absorbed_J"], e["bottomConduction_J"] + e["convectionRadiation_J"] + e["evaporated_J"] + e["stored_J"],
                               delta=1e-9 * e["absorbed_J"])
        self.assertGreater(r["evaporatedMass_kg"], 0.0)

    def test_evaporation_lowers_the_surface_temperature_and_removes_energy(self):
        # without the sink the 300 W surface flux overshoots 2 T_b on this coarse grid; widen the table for the control
        hot = F.run_case(HOT, evaporation=False, source_mode="surface-flux", boiling_stop=False, t_max_factor=6.0)
        cool = F.run_case(HOT, evaporation=True, source_mode="surface-flux", boiling_stop=False)
        self.assertGreater(hot["maxSurfaceTemperature_K"], hot["boiling_K"])
        self.assertLess(cool["maxSurfaceTemperature_K"], hot["maxSurfaceTemperature_K"])
        self.assertEqual(hot["energy"]["evaporated_J"], 0.0)
        self.assertGreater(cool["energy"]["evaporatedFraction"], 0.0)

    def test_frozen_physics_arm_stops_at_boiling_like_the_frozen_solver(self):
        with self.assertRaises(ValueError) as cm:
            F.run_case(HOT, evaporation=False, source_mode="volumetric", boiling_stop=True)
        self.assertIn("boiling", str(cm.exception).lower())

    def test_frozen_physics_arm_matches_the_frozen_solver_on_a_sub_boiling_case(self):
        import contextlib
        import io
        import lpbf_simulation as S
        with contextlib.redirect_stdout(io.StringIO()):
            frozen = S.run(dict(SMALL))
        fork = F.run_case(SMALL, evaporation=False, source_mode="volumetric", boiling_stop=True)
        fm, pk = frozen["metrics"], fork["operators"]["peak"]
        self.assertAlmostEqual(fork["peakTemperature_K"], fm["peakTemperature_K"], delta=1e-3 * fm["peakTemperature_K"])
        for a, b in ((pk["width_um"], fm["width_um"]), (pk["depthSurface_um"], fm["depth_um"]), (pk["length_um"], fm["length_um"])):
            self.assertAlmostEqual(a, b, places=6)
        self.assertEqual(fork["discretization"]["cells"], frozen["discretization"]["cells"])
        mid = frozen["midTrackCrossSection"]
        self.assertAlmostEqual(fork["operators"]["envMid"]["width_um"], mid["width_um"], places=6)
        self.assertAlmostEqual(fork["operators"]["envMid"]["depthPlate_um"], mid["depth_um"], places=6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
