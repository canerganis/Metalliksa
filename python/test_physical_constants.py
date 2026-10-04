import ast
import json
import unittest
from decimal import Decimal
from pathlib import Path

import physical_constants as pc

HERE = Path(__file__).parent

# Union of the elements the calphad, icme and tafel tables use today (DESIGN-6a section 1).
DESIGN_ELEMENTS = ("Fe", "Cr", "Ni", "Mo", "Mn", "Si", "C", "Ti", "Al", "V", "Zn", "Mg", "Cu",
                   "Nb", "Co", "W", "O", "N", "B", "Zr", "Ta", "Hf", "Re")

# Elements that steel, IN718, Ti and Al specifications list (including impurity
# limits such as S and P, and Sn in Ti alloys). Every one needs a CIAAW 2021 weight.
SPEC_ELEMENTS = ("Ni", "Cr", "Fe", "Mo", "Nb", "Ti", "Al", "V", "Co", "W", "Ta", "Cu", "Mn",
                 "Si", "C", "N", "O", "S", "P", "B", "Zr", "Mg", "Zn", "Sn")


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

    def test_exact_minus_truncated_drift_is_pinned(self):
        # tafel_corrosion_rate_solver, pourbaix_solver and calphad_solver use the CODATA
        # printed truncations 8.314462618 and 96485.33212, not the exact products. A
        # structural migration step that swaps in these records therefore CANNOT be
        # bit-exact against the golden outputs; it is a (tiny) value change.
        self.assertEqual(pc.TRUNCATED_GAS_CONSTANT_R, 8.314462618)
        self.assertEqual(pc.TRUNCATED_FARADAY, 96485.33212)
        d_r = pc.GAS_CONSTANT_R.value - pc.TRUNCATED_GAS_CONSTANT_R
        d_f = pc.FARADAY.value - pc.TRUNCATED_FARADAY
        self.assertNotEqual(d_r, 0.0)
        self.assertNotEqual(d_f, 0.0)
        self.assertAlmostEqual(d_r, 1.5324e-10, delta=1e-13)
        self.assertAlmostEqual(d_f, 3.3100e-6, delta=1e-9)
        self.assertAlmostEqual(d_r / pc.GAS_CONSTANT_R.value, 1.84e-11, delta=0.01e-11)
        self.assertAlmostEqual(d_f / pc.FARADAY.value, 3.43e-11, delta=0.01e-11)

    def test_solvers_still_use_the_truncated_values(self):
        import pourbaix_solver
        import tafel_corrosion_rate_solver as tafel
        # Design step (b): tafel uses the exact SI products.
        self.assertEqual(tafel.R_GAS, pc.GAS_CONSTANT_R.value)
        self.assertEqual(tafel.FARADAY_C_PER_MOL, pc.FARADAY.value)
        # calphad_solver (Phase 6a tranche 2a structural migration) takes R from this
        # module, still as the truncated value.
        import calphad_solver
        self.assertEqual(calphad_solver.GAS_CONSTANT_R, pc.TRUNCATED_GAS_CONSTANT_R)
        # pourbaix_solver: design step (b) switched R/F to the exact SI products.
        self.assertEqual(pourbaix_solver.R_GAS, pc.GAS_CONSTANT_R.value)
        self.assertEqual(pourbaix_solver.F_FARADAY, pc.FARADAY.value)
        self.assertEqual(pourbaix_solver.calculate_nernst_slope(25.0),
                         (2.302585093 * pc.GAS_CONSTANT_R.value * 298.15) / pc.FARADAY.value)

    def test_constant_metadata_fields(self):
        for c in (pc.AVOGADRO, pc.BOLTZMANN, pc.ELEMENTARY_CHARGE, pc.GAS_CONSTANT_R,
                  pc.FARADAY, pc.ZERO_CELSIUS_K):
            self.assertEqual(c.source_type, "literature")
            self.assertIn(c.source_type, pc.SOURCE_TYPES)
            self.assertIsNone(c.validity)
            self.assertIn("literature", c.note)

    def test_source_type_vocabulary_matches_alloy_registry(self):
        import alloy_registry
        self.assertEqual(pc.SOURCE_TYPES, alloy_registry.SOURCE_TYPES)

    def test_invalid_metadata_is_rejected(self):
        with self.assertRaises(ValueError):
            pc.Constant(1.0, "1", "x", False, source_type="defined-constant")
        with self.assertRaises(ValueError):
            pc.Constant(1.0, "1", "x", False, validity=(0.0, 1.0))  # type: ignore[arg-type]
        ok = pc.Constant(1.0, "1", "x", False, source_type="computed", validity=(0.0, 1.0, "K"))
        self.assertEqual(ok.validity, (0.0, 1.0, "K"))
        with self.assertRaises(ValueError):
            pc.AtomicWeight("Xx", 1.0, (0.9, 1.1), source_type="guess")

    def test_constants_are_immutable(self):
        with self.assertRaises(Exception):
            pc.GAS_CONSTANT_R.value = 8.314  # type: ignore[misc]


class AtomicWeightTest(unittest.TestCase):
    def test_design_elements_are_present(self):
        for el in DESIGN_ELEMENTS:
            self.assertIn(el, pc.STANDARD_ATOMIC_WEIGHTS)

    def test_specification_elements_are_present(self):
        for el in SPEC_ELEMENTS:
            self.assertIn(el, pc.STANDARD_ATOMIC_WEIGHTS, el)

    def test_added_impurity_and_tin_weights(self):
        # CIAAW 2021: S interval [32.059, 32.076] abridged 32.06; P 30.973761998(5)
        # abridged 30.974; Sn 118.710(7) abridged 118.71.
        self.assertEqual(pc.atomic_weight("S"), 32.06)
        self.assertEqual(pc.atomic_weight_record("S").interval, (32.059, 32.076))
        self.assertEqual(pc.atomic_weight("P"), 30.974)
        self.assertEqual(pc.atomic_weight_record("P").interval, (30.973761993, 30.973762003))
        self.assertEqual(pc.atomic_weight("Sn"), 118.71)
        self.assertEqual(pc.atomic_weight_record("Sn").interval, (118.703, 118.717))

    def test_step_b_added_elements(self):
        # Design step (b): CIAAW 2021 abridged value and standard interval for the
        # elements UI specimens send (Be, Sc, Pd, Pb) and common alloying additions.
        expected = {
            "Li": (6.94, (6.938, 6.997)), "Be": (9.0122, (9.0121826, 9.0121836)),
            "Ca": (40.078, (40.074, 40.082)), "Sc": (44.956, (44.955903, 44.955911)),
            "Pd": (106.42, (106.41, 106.43)), "Ag": (107.87, (107.8680, 107.8684)),
            "Sb": (121.76, (121.759, 121.761)), "La": (138.91, (138.90540, 138.90554)),
            "Ce": (140.12, (140.115, 140.117)), "Nd": (144.24, (144.239, 144.245)),
            "Pb": (207.2, (206.14, 207.94)), "Bi": (208.98, (208.98039, 208.98041)),
        }
        for el, (value, interval) in expected.items():
            with self.subTest(el=el):
                self.assertEqual(pc.atomic_weight(el), value)
                self.assertEqual(pc.atomic_weight_record(el).interval, interval)
                self.assertEqual(pc.atomic_weight(el.upper()), value)

    def test_atomic_weight_metadata_fields(self):
        for symbol, rec in pc.STANDARD_ATOMIC_WEIGHTS.items():
            self.assertEqual(rec.source_type, "literature", symbol)
            # The CIAAW interval is variability, not applicability validity.
            self.assertIsNone(rec.validity, symbol)
            self.assertIn("not an applicability validity", rec.note)

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
        # Snapshot of calphad ATOMIC_WEIGHTS at the pre-migration base revision.
        import calphad_solver
        snapshot = HERE / "golden" / "phase6a" / "calphad_solver" / "_source_tables.json"
        table = json.loads(snapshot.read_text(encoding="utf-8"))["values"]["ATOMIC_WEIGHTS"]
        self.assertEqual(len(table), 28)
        for el, value in table.items():
            self.assertEqual(pc.atomic_weight(el), value, el)
        self.assertEqual(calphad_solver.ATOMIC_WEIGHTS, table)

    def test_tafel_table_values_match_registry(self):
        # Snapshot of tafel ALLOY_LIBRARY at the pre-migration base revision.
        snapshot = HERE / "golden" / "phase6a" / "tafel_corrosion_rate_solver" / "_source_tables.json"
        library = json.loads(snapshot.read_text(encoding="utf-8"))["values"]
        self.assertEqual(len(library), 9)
        for alloy_id, preset in library.items():
            for el, value in preset["atomic_weights"].items():
                self.assertEqual(pc.atomic_weight(el), value, f"{alloy_id}:{el}")

    def test_pourbaix_atomic_masses_match_registry(self):
        import pourbaix_solver
        snapshot = HERE / "golden" / "phase6a" / "pourbaix_solver" / "_source_tables.json"
        old = json.loads(snapshot.read_text(encoding="utf-8"))["values"]
        self.assertEqual(set(old), set(pourbaix_solver.POURBAIX_ELEMENT_SYSTEMS))
        for el, entry in old.items():
            self.assertEqual(pc.atomic_weight(el), entry["atomicMass"], el)
            self.assertEqual(pourbaix_solver.POURBAIX_ELEMENT_SYSTEMS[el]["atomicMass"], entry["atomicMass"], el)


if __name__ == "__main__":
    unittest.main()
