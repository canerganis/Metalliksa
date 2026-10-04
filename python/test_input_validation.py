import json
import math
import unittest

import input_validation as iv


class ScalarChecksTest(unittest.TestCase):
    def assertCode(self, code, fn, *args, **kwargs):
        with self.assertRaises(iv.ValidationError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)
        return ctx.exception

    def test_non_finite(self):
        for bad in (math.nan, math.inf, -math.inf, float("nan"), "1.0", None, True, [1.0]):
            with self.subTest(bad=bad):
                err = self.assertCode(iv.NON_FINITE, iv.require_finite, "power_W", bad)
                self.assertEqual(err.field, "power_W")

    def test_finite_passes_and_returns_float(self):
        self.assertEqual(iv.require_finite("x", 3), 3.0)
        self.assertIsInstance(iv.require_finite("x", 3), float)

    def test_non_positive(self):
        self.assertCode(iv.NON_POSITIVE, iv.require_positive, "area_cm2", -3)
        self.assertCode(iv.NON_POSITIVE, iv.require_positive, "area_cm2", 0)
        self.assertCode(iv.NON_POSITIVE, iv.require_positive, "x", -1e-300, allow_zero=True)
        self.assertEqual(iv.require_positive("x", 0, allow_zero=True), 0.0)
        self.assertCode(iv.NON_FINITE, iv.require_positive, "x", math.nan)

    def test_out_of_range(self):
        err = self.assertCode(iv.OUT_OF_RANGE, iv.require_range, "pH", 20, 0, 14, "1")
        self.assertEqual(err.detail["hi"], 14)
        self.assertEqual(iv.require_range("pH", 14, 0, 14, "1"), 14.0)
        self.assertEqual(iv.require_range("T", -500, None, 0, "degC"), -500.0)

    def test_bad_unit(self):
        self.assertCode(iv.BAD_UNIT, iv.require_unit, "unit", "bogus_unit", ("wt_pct", "at_pct"))
        self.assertCode(iv.BAD_UNIT, iv.require_unit, "unit", None, ("wt_pct",))
        self.assertEqual(iv.require_unit("unit", "wt_pct", ("wt_pct", "at_pct")), "wt_pct")


class CompositionTest(unittest.TestCase):
    def code_of(self, comp):
        with self.assertRaises(iv.ValidationError) as ctx:
            iv.require_composition(comp)
        return ctx.exception.code

    def test_valid_composition_is_returned_unchanged(self):
        comp = {"Ni": 52.5, "Cr": 19.0, "Fe": 18.5, "Nb": 5.1, "Mo": 3.05, "Ti": 0.9, "Al": 0.55}
        self.assertEqual(iv.require_composition(comp), comp)
        self.assertEqual(iv.require_composition({"NI": 80, "AL": 0}), {"Ni": 80.0, "Al": 0.0})

    def test_bad_compositions(self):
        self.assertEqual(self.code_of({"Xx": 10, "Ni": 90}), iv.UNKNOWN_ELEMENT)
        self.assertEqual(self.code_of({"Ni": -5, "Al": 10}), iv.NON_POSITIVE)
        self.assertEqual(self.code_of({"Ni": math.nan}), iv.NON_FINITE)
        self.assertEqual(self.code_of({"Ni": 90, "Cr": 11}), iv.OUT_OF_RANGE)
        self.assertEqual(self.code_of({}), iv.OUT_OF_RANGE)
        self.assertEqual(self.code_of([("Ni", 100)]), iv.OUT_OF_RANGE)
        self.assertEqual(self.code_of({"Ni": 0, "Al": 0}), iv.NON_POSITIVE)
        self.assertEqual(self.code_of({"Fe": 50, "FE": 10}), iv.OUT_OF_RANGE)

    def test_rounding_tolerance(self):
        self.assertEqual(sum(iv.require_composition({"Ni": 60.3, "Cr": 40.2}).values()), 100.5)


class AlloyChecksTest(unittest.TestCase):
    def test_unknown_alloy(self):
        with self.assertRaises(iv.ValidationError) as ctx:
            iv.require_known_alloy("Unobtainium XYZ", "kinetics")
        err = ctx.exception
        self.assertEqual(err.code, iv.UNKNOWN_ALLOY)
        self.assertEqual(err.field, "alloy")
        self.assertEqual(err.detail["domain"], "kinetics")

    def test_alloy_without_domain_data(self):
        with self.assertRaises(iv.ValidationError) as ctx:
            iv.require_known_alloy("AlSi10Mg", "kinetics", field="alloy")
        self.assertEqual(ctx.exception.detail["reason"], "no-domain-data")

    def test_ambiguous_alloy_reports_unknown_alloy_code(self):
        import alloy_registry as reg
        from unittest import mock
        compact = dict(reg._COMPACT_INDEX)
        compact["fooalloy"] = frozenset({"aisi4140", "aisi4340"})
        with mock.patch.object(reg, "_COMPACT_INDEX", compact):
            with self.assertRaises(iv.ValidationError) as ctx:
                iv.require_known_alloy("foo alloy")
        self.assertEqual(ctx.exception.code, iv.UNKNOWN_ALLOY)
        self.assertEqual(ctx.exception.detail["reason"], "ambiguous")

    def test_known_alloy_and_missing_property(self):
        rec = iv.require_known_alloy("AISI 4140", "kinetics")
        self.assertEqual(rec.id, "aisi4140")
        self.assertEqual(iv.require_property(rec, "Ae3_C", "kinetics").value, 780.0)
        with self.assertRaises(iv.ValidationError) as ctx:
            iv.require_property(rec, "gamma_solvus_C", "kinetics")
        self.assertEqual(ctx.exception.code, iv.MISSING_PROPERTY)

    def test_bare_grade_is_reported_as_unknown_alloy(self):
        for domain in (None, "kinetics"):
            with self.assertRaises(iv.ValidationError) as ctx:
                iv.require_known_alloy("304", domain)
            self.assertEqual(ctx.exception.code, iv.UNKNOWN_ALLOY)
            self.assertEqual(ctx.exception.detail["reason"], "bare-grade")

    def test_documented_type_error_codes(self):
        with self.assertRaises(iv.ValidationError) as ctx:
            iv.require_finite("power_W", "200")
        self.assertEqual(ctx.exception.code, iv.NON_FINITE)
        self.assertEqual(ctx.exception.detail["type"], "str")
        with self.assertRaises(iv.ValidationError) as ctx:
            iv.require_composition(["Ni"])
        self.assertEqual(ctx.exception.code, iv.OUT_OF_RANGE)
        self.assertEqual(ctx.exception.detail["type"], "list")

    def test_new_spec_elements_are_accepted(self):
        self.assertEqual(iv.require_composition({"Fe": 99.9, "S": 0.03, "P": 0.04}),
                         {"Fe": 99.9, "S": 0.03, "P": 0.04})
        self.assertEqual(iv.require_element("element", "Sn"), "Sn")

    def test_unknown_element(self):
        with self.assertRaises(iv.ValidationError) as ctx:
            iv.require_element("element", "Xx")
        self.assertEqual(ctx.exception.code, iv.UNKNOWN_ELEMENT)
        self.assertEqual(iv.require_element("element", "Nb"), "Nb")


class EnvelopeTest(unittest.TestCase):
    def test_envelope_shape_is_json_serialisable(self):
        err = iv.ValidationError(iv.OUT_OF_RANGE, "pH", "must be within [0, 14] 1",
                                 {"value": 20.0, "lo": 0, "hi": 14})
        env = iv.validation_envelope(err)
        self.assertEqual(env["success"], False)
        self.assertEqual(env["errorKind"], "validation")
        self.assertEqual(set(env["error"]), {"code", "field", "message", "detail"})
        json.dumps(env, allow_nan=False)

    def test_unknown_code_is_rejected(self):
        with self.assertRaises(ValueError):
            iv.ValidationError("SOMETHING_ELSE", "x", "y")

    def test_codes_match_design(self):
        self.assertEqual(iv.ERROR_CODES, frozenset({
            "NON_FINITE", "NON_POSITIVE", "OUT_OF_RANGE", "UNKNOWN_ALLOY",
            "UNKNOWN_ELEMENT", "MISSING_PROPERTY", "BAD_UNIT"}))


if __name__ == "__main__":
    unittest.main()
