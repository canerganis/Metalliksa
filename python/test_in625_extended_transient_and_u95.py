"""Tests for IN625 extended liquid thermophysical data, transient specification, and U95 budgets."""

import math
import unittest

from four_alloy_materials import (
    FOUR_ALLOY_IDS,
    four_alloy_u95_at_temperature,
)
from in625_thermal_material import (
    IN625_BOILING_K,
    IN625_LATENT_HEAT_FUSION_MILLS_J_KG,
    IN625_LIQUID_CP_MILLS_J_KGK,
    IN625_LIQUID_K_MILLS_W_MK,
    IN625_LIQUID_RHO_MILLS_KG_M3,
    IN625_LIQUIDUS_K,
    IN625_SOLID_RHO_KG_M3,
    IN625_SOLIDUS_K,
    KIM_1975_REF,
    MILLS_2002_DOI,
    in625_extended_thermal_at_kelvin,
    in625_transient_material_specification,
    in625_u95_uncertainty_at_kelvin,
)
from lpbf_material_registry import enthalpy_table, material


class TestIn625ExtendedTransientAndU95(unittest.TestCase):
    def test_literature_constants_and_doi(self):
        self.assertEqual(MILLS_2002_DOI, "10.1533/9781845690144")
        self.assertEqual(KIM_1975_REF, "ANL-75-55")
        self.assertEqual(IN625_LIQUID_CP_MILLS_J_KGK, 720.0)
        self.assertEqual(IN625_LIQUID_K_MILLS_W_MK, 30.0)
        self.assertEqual(IN625_LIQUID_RHO_MILLS_KG_M3, 7750.0)
        self.assertEqual(IN625_LATENT_HEAT_FUSION_MILLS_J_KG, 227000.0)
        self.assertEqual(IN625_SOLIDUS_K, 1563.15)
        self.assertEqual(IN625_LIQUIDUS_K, 1623.15)
        self.assertEqual(IN625_BOILING_K, 3173.15)

    def test_in625_transient_material_specification_admitted_by_registry(self):
        spec = in625_transient_material_specification()
        self.assertEqual(spec["name"], "Inconel 625")
        self.assertIn("Mills (2002)", spec["source"])
        self.assertIn(MILLS_2002_DOI, spec["source"])
        self.assertEqual(spec["latentHeat_J_kg"], 227000.0)
        
        # Test admission into lpbf_material_registry
        mat = material("Inconel 625", supplied=spec)
        self.assertEqual(mat["name"], "Inconel 625")
        self.assertEqual(mat["quality"], "user-supplied-unverified")
        self.assertEqual(mat["solidus_K"], 1563.15)
        self.assertEqual(mat["liquidus_K"], 1623.15)
        self.assertEqual(mat["boiling_K"], 3173.15)
        self.assertEqual(mat["latentHeat_J_kg"], 227000.0)
        self.assertEqual(len(mat["table"]), 6)
        
        # Verify that enthalpy_table can integrate it without error
        t, h = enthalpy_table(mat)
        self.assertEqual(len(t), len(h))
        self.assertTrue(all(h[i + 1] > h[i] for i in range(len(h) - 1)))
        self.assertAlmostEqual(t[0], 273.15)
        self.assertAlmostEqual(t[-1], 3173.15)

    def test_in625_extended_thermal_continuity_and_liquid_regime(self):
        # Just at liquidus
        liq = in625_extended_thermal_at_kelvin(IN625_LIQUIDUS_K)
        self.assertEqual(liq["liquidFraction"], 1.0)
        
        # Above liquidus (liquid regime)
        t_above = 2000.0
        res = in625_extended_thermal_at_kelvin(t_above)
        self.assertEqual(res["liquidFraction"], 1.0)
        self.assertEqual(res["specificHeat_J_kgK"], 720.0)
        self.assertEqual(res["thermalConductivity_W_mK"], 30.0)
        self.assertEqual(res["density_kg_m3"], 7750.0)
        
        # Check linear enthalpy rise in liquid phase: dH = Cp * dT
        delta_t = t_above - IN625_LIQUIDUS_K
        expected_dh = 720.0 * delta_t
        self.assertAlmostEqual(res["specificEnthalpy_J_kg"] - liq["specificEnthalpy_J_kg"], expected_dh, delta=1e-5)
        
        # Boiling point boundary check
        boil_res = in625_extended_thermal_at_kelvin(IN625_BOILING_K)
        self.assertTrue(boil_res["specificEnthalpy_J_kg"] > res["specificEnthalpy_J_kg"])
        
        # Out of bounds
        with self.assertRaises(ValueError):
            in625_extended_thermal_at_kelvin(IN625_BOILING_K + 10.0)
        with self.assertRaises(ValueError):
            in625_extended_thermal_at_kelvin(200.0)

    def test_in625_u95_uncertainty_budget(self):
        # Solid phase
        k_solid_u95 = in625_u95_uncertainty_at_kelvin(500.0, "conductivity")
        cp_solid_u95 = in625_u95_uncertainty_at_kelvin(500.0, "specificHeat")
        self.assertEqual(k_solid_u95, 0.06)
        self.assertEqual(cp_solid_u95, 0.05)
        
        # Mushy phase
        t_mushy = (IN625_SOLIDUS_K + IN625_LIQUIDUS_K) / 2.0
        k_mushy_u95 = in625_u95_uncertainty_at_kelvin(t_mushy, "conductivity")
        latent_u95 = in625_u95_uncertainty_at_kelvin(t_mushy, "latentHeat")
        self.assertEqual(k_mushy_u95, 0.12)
        self.assertEqual(latent_u95, 0.10)
        
        # Liquid phase
        k_liquid_u95 = in625_u95_uncertainty_at_kelvin(2000.0, "conductivity")
        visc_liquid_u95 = in625_u95_uncertainty_at_kelvin(2000.0, "viscosity")
        self.assertEqual(k_liquid_u95, 0.10)
        self.assertEqual(visc_liquid_u95, 0.15)
        
        # Out of range
        with self.assertRaises(ValueError):
            in625_u95_uncertainty_at_kelvin(3500.0, "conductivity")

    def test_four_alloy_u95_at_temperature(self):
        for aid in FOUR_ALLOY_IDS:
            with self.subTest(alloy_id=aid):
                # Solid
                k_sol = four_alloy_u95_at_temperature(aid, "k", 300.0)
                cp_sol = four_alloy_u95_at_temperature(aid, "cp", 300.0)
                rho_sol = four_alloy_u95_at_temperature(aid, "rho", 300.0)
                self.assertTrue(0.01 <= k_sol <= 0.10)
                self.assertTrue(0.01 <= cp_sol <= 0.10)
                self.assertTrue(0.005 <= rho_sol <= 0.05)
                
                # Liquid (above 2000 K for all 4 alloys)
                k_liq = four_alloy_u95_at_temperature(aid, "k", 2200.0)
                cp_liq = four_alloy_u95_at_temperature(aid, "cp", 2200.0)
                self.assertTrue(k_liq >= k_sol)
                self.assertTrue(cp_liq >= cp_sol)

        with self.assertRaises(ValueError):
            four_alloy_u95_at_temperature("unknown_alloy", "k", 300.0)


if __name__ == "__main__":
    unittest.main()
