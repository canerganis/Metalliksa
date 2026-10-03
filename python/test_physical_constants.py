import ast
import unittest
from decimal import Decimal
from pathlib import Path

import physical_constants as pc

HERE = Path(__file__).parent

# Union of the elements the calphad, icme and tafel tables use today (DESIGN-6a section 1).
DESIGN_ELEMENTS = ("Fe", "Cr", "Ni", "Mo", "Mn", "Si", "C", "Ti", "Al", "V", "Zn", "Mg", "Cu",
                   "Nb", "Co", "W", "O", "N", "B", "Zr", "Ta", "Hf", "Re")


def _literal_dict(path: Path, name: str) -> dict:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {path.name}")


class ExactConstantsTest(unittest.TestCase):
    def test_defining_constants_are_exact_si_2019_values(self):
        self.assertEqual(pc.AVOGADRO.value, 6.02214076e23)
        self.assertEqual(pc.BOLTZMANN.value, 1.380649e-23)
        self.assertEqual(pc.ELEMENTARY_CHARGE.value, 1.602176634e-19)
        self.assertEqual(pc.ZERO_CELSIUS_K.value, 273.15)
        for c in (pc.AVOGADRO, pc.BOLTZMANN, pc.ELEMENTARY_CHARGE, pc.GAS_CONSTANT_R,
                  pc.FARADAY, pc.ZERO_CELSIUS_K):
            self.assertTrue(c.exact)
            self.assertTrue(c.unit)
            self.assertTrue(c.source)

    def test_gas_constant_is_exact_product_na_k(self):
        exact = Decimal("6.02214076e23") * Decimal("1.380649e-23")
        self.assertEqual(pc.GAS_CONSTANT_R.value, float(exact))
        product = pc.AVOGADRO.value * pc.BOLTZMANN.value
        self.assertLessEqual(abs(pc.GAS_CONSTANT_R.value - product) / product, 1e-15)
        self.assertEqual(pc.GAS_CONSTANT_R.unit, "J/(mol*K)")

    def test_faraday_is_exact_product_na_e(self):
        exact = Decimal("6.02214076e23") * Decimal("1.602176634e-19")
        self.assertEqual(pc.FARADAY.value, float(exact))
        product = pc.AVOGADRO.value * pc.ELEMENTARY_CHARGE.value
        self.assertLessEqual(abs(pc.FARADAY.value - product) / product, 1e-15)
        self.assertEqual(pc.FARADAY.unit, "C/mol")

    def test_constants_are_immutable(self):
        with self.assertRaises(Exception):
            pc.GAS_CONSTANT_R.value = 8.314  # type: ignore[misc]


class AtomicWeightTest(unittest.TestCase):
    def test_design_elements_are_present(self):
        for el in DESIGN_ELEMENTS:
            self.assertIn(el, pc.STANDARD_ATOMIC_WEIGHTS)

    def test_abridged_values_lie_within_ciaaw_interval(self):
        for symbol, rec in pc.STANDARD_ATOMIC_WEIGHTS.items():
            lo, hi = rec.interval
            self.assertLess(lo, hi, symbol)
            # The abridged value is rounded to its last printed digit; allow half a unit.
            exponent = Decimal(repr(rec.value)).as_tuple().exponent
            half_unit = float(Decimal(5) * Decimal(10) ** (exponent - 1))
            self.assertGreaterEqual(rec.value + half_unit, lo, symbol)
            self.assertLessEqual(rec.value - half_unit, hi, symbol)
            self.assertEqual(rec.unit, "g/mol")
            self.assertIn("CIAAW", rec.source)

    def test_unknown_element_raises_without_fallback(self):
        for bad in ("Xx", "Zz", "Qq", "Unobtainium", "", "  ", None, 50, 55.0, "Fe2", "fe", "co"):
            with self.subTest(bad=bad):
                with self.assertRaises(pc.UnknownElementError):
                    pc.atomic_weight(bad)
                self.assertFalse(pc.is_known_element(bad))

    def test_tdb_uppercase_and_canonical_case_are_accepted(self):
        self.assertEqual(pc.atomic_weight("Fe"), 55.845)
        self.assertEqual(pc.atomic_weight("FE"), 55.845)
        self.assertEqual(pc.atomic_weight(" Ni "), 58.693)
        self.assertEqual(pc.atomic_weight("CO"), pc.atomic_weight("Co"))

    def test_unknown_element_error_is_key_error_with_readable_message(self):
        with self.assertRaises(KeyError) as ctx:
            pc.atomic_weight("Xx")
        self.assertIn("no fallback", str(ctx.exception))

    def test_calphad_table_values_match_registry(self):
        # Step 3 of the migration must be bit-identical for the atomic weights.
        table = _literal_dict(HERE / "calphad_solver.py", "ATOMIC_WEIGHTS")
        for el, value in table.items():
            self.assertEqual(pc.atomic_weight(el), value, el)

    def test_tafel_table_values_match_registry(self):
        import tafel_corrosion_rate_solver as tafel
        for alloy_id, preset in tafel.ALLOY_LIBRARY.items():
            for el, value in preset["atomic_weights"].items():
                self.assertEqual(pc.atomic_weight(el), value, f"{alloy_id}:{el}")


if __name__ == "__main__":
    unittest.main()
