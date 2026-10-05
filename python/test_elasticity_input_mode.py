"""Regression tests for explicit user/library/isotropic elasticity input selection."""

import unittest
from unittest.mock import patch

import dft_property_calculator as dft


def run(payload):
    return dft.calculate_dft_properties(payload)


class ElasticityInputModeTests(unittest.TestCase):
    def test_custom_mode_uses_complete_user_tensor_for_library_formula_without_density_fill(self):
        payload = {
            "formula": "Ni",
            "input_mode": "custom",
            "crystal_system": "Cubic",
            "custom_c_ij": {"c11": 205.0, "c12": 105.0, "c44": 50.0},
        }
        with patch.object(dft, "lookup_library_entry", wraps=dft.lookup_library_entry) as lookup:
            out = run(payload)

        self.assertEqual((out["status"], out["constantsOrigin"]), ("available", "custom-user-supplied"))
        self.assertEqual(out["elasticStiffnessMatrix_Cij_GPa"][0][:3], [205.0, 105.0, 105.0])
        self.assertIsNone(out["materialInfo"]["density"])
        self.assertNotIn("Ni", [call.args[0] for call in lookup.call_args_list])

    def test_custom_mode_needs_the_complete_symmetry_tensor_even_for_library_formula(self):
        out = run({
            "formula": "Ni",
            "input_mode": "custom",
            "crystal_system": "Cubic",
            "custom_c_ij": {"c12": 105.0, "c44": 50.0},
            "k_vrh": 100.0,
            "g_vrh": 40.0,
        })

        self.assertEqual((out["status"], out["unavailableCode"]), ("unavailable", "MISSING_ELASTIC_CONSTANTS"))
        self.assertIn("c11", out["reason"])
        self.assertNotIn("elasticStiffnessMatrix_Cij_GPa", out)

    def test_custom_mode_requires_custom_constants_instead_of_moduli_or_library_fallback(self):
        out = run({
            "formula": "Ni",
            "input_mode": "custom",
            "crystal_system": "Cubic",
            "k_vrh": 100.0,
            "g_vrh": 40.0,
        })

        self.assertEqual(out["status"], "unavailable")
        self.assertNotIn("elasticStiffnessMatrix_Cij_GPa", out)

    def test_custom_mode_requires_caller_symmetry_instead_of_inheriting_library_symmetry(self):
        out = run({
            "formula": "Ni",
            "input_mode": "custom",
            "custom_c_ij": {"c11": 205.0, "c12": 105.0, "c44": 50.0},
        })

        self.assertEqual((out["status"], out["unavailableCode"]), ("unavailable", "MISSING_CRYSTAL_SYSTEM"))

    def test_custom_trigonal_mode_preserves_c14_couplings(self):
        out = run({
            "formula": "Ni",
            "input_mode": "custom",
            "crystal_system": "Trigonal",
            "custom_c_ij": {
                "c11": 200.0, "c12": 80.0, "c13": 75.0, "c14": 10.0, "c33": 220.0, "c44": 65.0,
            },
        })

        self.assertEqual(out["status"], "available")
        matrix = out["elasticStiffnessMatrix_Cij_GPa"]
        self.assertEqual((matrix[0][3], matrix[1][3], matrix[4][5]), (10.0, -10.0, 10.0))

    def test_isotropic_mode_forces_supplied_moduli_and_does_not_fill_library_density(self):
        with patch.object(dft, "lookup_library_entry", wraps=dft.lookup_library_entry) as lookup:
            out = run({
                "formula": "Ni",
                "input_mode": "isotropic",
                "crystal_system": "Cubic",
                "k_vrh": 100.0,
                "g_vrh": 40.0,
                "custom_c_ij": {"c11": 205.0, "c12": 105.0, "c44": 50.0},
            })

        self.assertEqual((out["status"], out["constantsOrigin"]), ("available", "isotropic-from-supplied-K-G"))
        self.assertEqual(out["materialInfo"]["crystal_system"], "Isotropic")
        self.assertEqual(out["elasticStiffnessMatrix_Cij_GPa"][0][:3], [153.33, 73.33, 73.33])
        self.assertEqual(out["elasticStiffnessMatrix_Cij_GPa"][3][3], 40.0)
        self.assertIsNone(out["materialInfo"]["density"])
        self.assertNotIn("Ni", [call.args[0] for call in lookup.call_args_list])

    def test_isotropic_mode_requires_both_positive_finite_moduli(self):
        for payload in (
            {"formula": "Ni", "input_mode": "isotropic", "k_vrh": 100.0},
            {"formula": "Ni", "input_mode": "isotropic", "k_vrh": 0.0, "g_vrh": 40.0},
            {"formula": "Ni", "input_mode": "isotropic", "k_vrh": 100.0, "g_vrh": float("inf")},
        ):
            with self.subTest(payload=payload):
                out = run(payload)
                self.assertEqual(out["status"], "unavailable")
                self.assertNotIn("elasticStiffnessMatrix_Cij_GPa", out)

    def test_library_mode_uses_only_exact_entry_and_ignores_other_constant_inputs(self):
        out = run({
            "formula": "Ni",
            "input_mode": "library",
            "k_vrh": 100.0,
            "g_vrh": 40.0,
            "custom_c_ij": {"c11": 205.0, "c12": 105.0, "c44": 50.0},
        })

        self.assertEqual((out["status"], out.get("constantsOrigin")), ("available", "builtin-library-exact-match"))
        self.assertEqual(out["elasticStiffnessMatrix_Cij_GPa"][0][:3], [250.8, 150.0, 150.0])
        self.assertEqual(out["elasticStiffnessMatrix_Cij_GPa"][3][3], 123.5)
        self.assertEqual(out["materialInfo"]["density"], 8.91)

    def test_library_mode_without_exact_formula_does_not_fall_back_to_isotropic(self):
        out = run({"formula": "Zr3Al2", "input_mode": "library", "k_vrh": 100.0, "g_vrh": 40.0})

        self.assertEqual((out["status"], out.get("unavailableCode")), ("unavailable", "NO_ELASTIC_CONSTANTS"))
        self.assertNotIn("elasticStiffnessMatrix_Cij_GPa", out)

    def test_unknown_mode_uses_unavailable_envelope(self):
        out = run({"formula": "Ni", "input_mode": "automatic"})

        self.assertEqual(out["status"], "unavailable")
        self.assertIn("unavailableCode", out)
        self.assertNotIn("elasticStiffnessMatrix_Cij_GPa", out)

    def test_absent_mode_preserves_exact_library_and_custom_precedence(self):
        library = run({"formula": "Ni"})
        self.assertEqual(library["constantsOrigin"], "builtin-library-exact-match")

        custom = run({
            "formula": "Ni",
            "crystal_system": "Cubic",
            "custom_c_ij": {"c11": 205.0, "c12": 105.0, "c44": 50.0},
        })
        self.assertEqual(custom["constantsOrigin"], "custom-user-supplied")
        self.assertEqual(custom["elasticStiffnessMatrix_Cij_GPa"][0][:3], [205.0, 105.0, 105.0])
        self.assertEqual(custom["materialInfo"]["density"], 8.91)


if __name__ == "__main__":
    unittest.main()
