"""Unit tests for the graded mesh (< 5 um) and the boiling cap / k_eff multiplier (lpbf_evaporation_marangoni).

Verifies:
1. Graded mesh generates sub-5 um resolution (< 5 um) in laser zone with conservative metrics.
2. Liquid-phase k_eff multiplier 1 + (lambda - 1) f_liq (isotropic surrogate; estimated).
3. The boiling cap: T is clipped at T_boil above the boiling enthalpy, the excess enthalpy stays
   in the cell and the returned vapor fraction is a diagnostic proxy, not a mass loss.
   This is NOT an evaporation model (no Langmuir flux is used anywhere in the solver).
"""

import math
import unittest
import numpy as np

from lpbf_graded_mesh import generate_graded_axis, generate_graded_mesh_3d
from lpbf_evaporation_marangoni import (
    calculate_keff_marangoni,
    invert_enthalpy_with_boiling_cap,
)
from lpbf_material_registry import material, enthalpy_table


class TestGradedMeshAndEvaporationPhysics(unittest.TestCase):
    def test_graded_axis_achieves_sub_5um_resolution(self):
        span = 600e-6       # 600 um domain
        fine_span = 80e-6   # 80 um laser corridor
        dx_fine = 2.5e-6    # 2.5 um (< 5 um target)
        dx_coarse = 25.0e-6 # 25 um outer

        centers, widths, faces = generate_graded_axis(span, fine_span, dx_fine, dx_coarse)
        
        # 1. Check sub-5 um fine cells in center
        min_width_um = float(widths.min()) * 1e6
        self.assertLess(min_width_um, 5.0)
        self.assertAlmostEqual(min_width_um, 2.5, delta=0.1)

        # 2. Check total span coverage and face continuity
        self.assertAlmostEqual(float(faces[0]), -span / 2.0)
        self.assertAlmostEqual(float(faces[-1]), span / 2.0)
        self.assertEqual(len(faces), len(centers) + 1)
        self.assertTrue((widths > 0).all())
        self.assertTrue((np.diff(faces) > 0).all())

        # 3. Symmetry check around x=0
        self.assertAlmostEqual(float(centers[len(centers) // 2 - 1] + centers[len(centers) // 2]), 0.0, delta=1e-12)

    def test_graded_mesh_3d_cell_efficiency(self):
        # Compare 3D graded mesh vs uniform fine mesh
        span_x = 800e-6
        span_y = 400e-6
        depth_z = 300e-6
        spot_radius = 35e-6
        dx_fine = 2.5e-6     # 2.5 um fine
        dx_coarse = 25.0e-6  # 25 um coarse

        mesh = generate_graded_mesh_3d(span_x, span_y, depth_z, spot_radius, dx_fine, dx_coarse)
        
        # Verify sub-5 um in center
        self.assertLess(mesh["dx_fine_m"] * 1e6, 5.0)
        self.assertLess(mesh["dy_fine_m"] * 1e6, 5.0)
        self.assertLess(mesh["dz_fine_m"] * 1e6, 5.0)

        # Uniform cells would be: (800/2.5) * (400/2.5) * (300/2.5) = 320 * 160 * 120 = 6,144,000 cells!
        uniform_cells = (span_x / dx_fine) * (span_y / dx_fine) * (depth_z / dx_fine)
        self.assertGreater(uniform_cells, 6_000_000)

        # Graded mesh should be substantially more compact (< 500,000 cells)
        self.assertLess(mesh["total_cells"], 500_000)
        cell_reduction_ratio = uniform_cells / mesh["total_cells"]
        self.assertGreater(cell_reduction_ratio, 10.0)  # >10x reduction!

    def test_marangoni_keff_enhancement(self):
        k_solid = 11.4  # IN718 solid conductivity
        k_liquid = 29.0 # IN718 liquid conductivity

        # Solid phase (liquid_fraction = 0)
        k_eff_sol = calculate_keff_marangoni(k_solid, liquid_fraction=0.0, lambda_marangoni=2.2)
        self.assertAlmostEqual(k_eff_sol, k_solid)

        # Full liquid phase (liquid_fraction = 1.0)
        k_eff_liq = calculate_keff_marangoni(k_liquid, liquid_fraction=1.0, lambda_marangoni=2.2)
        self.assertAlmostEqual(k_eff_liq, 2.2 * k_liquid)

        # Mushy transition (liquid_fraction = 0.5)
        k_mushy = 0.5 * (k_solid + k_liquid)
        k_eff_mushy = calculate_keff_marangoni(k_mushy, liquid_fraction=0.5, lambda_marangoni=2.2)
        self.assertTrue(k_solid < k_eff_mushy < k_eff_liq)

    def test_280w_boiling_lock_resolution(self):
        # Retrieve IN718 material properties and enthalpy table
        mat = material("Inconel 718")
        t_table, h_table = enthalpy_table(mat)
        t_boil = mat["boiling_K"]
        h_boil = float(np.interp(t_boil, t_table, h_table))
        l_vap = 6.4e6  # IN718 latent heat of vaporization [J/kg]

        # In standard model, an enthalpy exceeding h_boil (as occurs with 280 W laser input)
        # crashes with ValueError: Thermal model validity exceeded...
        # Here we test invert_enthalpy_with_boiling_cap (a temperature cap, not evaporation):
        
        # Scenario 1: Below boiling (normal transient heating)
        h_normal = np.array([h_table[0], h_boil * 0.5, h_boil * 0.9])
        t_norm, vap_norm = invert_enthalpy_with_boiling_cap(h_normal, h_table, t_table, t_boil, l_vap)
        self.assertTrue((vap_norm == 0.0).all())
        self.assertTrue((t_norm < t_boil).all())

        # Scenario 2: 280 W laser spot energy injection exceeding h_boil by 50 kJ/kg
        h_exceed = np.array([h_boil + 50_000.0, h_boil + 200_000.0])
        t_exceed, vap_exceed = invert_enthalpy_with_boiling_cap(h_exceed, h_table, t_table, t_boil, l_vap)
        
        # Temperature is safely bounded at T_boil (vaporization buffering)
        for t in t_exceed:
            self.assertAlmostEqual(t, t_boil, delta=1e-3)
            
        # Vapor fraction buffers excess enthalpy: f_vap = excess_h / L_vap
        expected_vap1 = 50_000.0 / l_vap
        expected_vap2 = 200_000.0 / l_vap
        self.assertAlmostEqual(vap_exceed[0], expected_vap1, places=6)
        self.assertAlmostEqual(vap_exceed[1], expected_vap2, places=6)
        self.assertTrue(0.0 < vap_exceed[0] < vap_exceed[1] < 0.1)


if __name__ == "__main__":
    unittest.main()
