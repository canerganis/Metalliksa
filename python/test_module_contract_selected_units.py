"""Conditional units are explicit, closed and attached to real selectors."""
import copy
import dataclasses
import unittest
import module_contract as mc
from test_module_contract import _contract, _evidence


def field(**changes):
    params = dict(key="temperature", label="Input temperature", quantity_kind="temperature",
                  unit=None, min=None, max=None, default=20, unit_selector="scale",
                  unit_options=(("C", "degC"), ("K", "K")))
    return mc.InputField(**{**params, **changes})


def operation(selector_type="enum", selector_values=("C", "K")):
    selector = mc.InputField(key="scale", label="Input scale", quantity_kind="selection",
                            unit=None, min=None, max=None, default="C", value_type=selector_type,
                            enum=selector_values)
    return mc.Operation(id="convert", route=None, input=(field(), selector),
                        authority=mc.Authority(kind="browser-local", exception_reason="Local conversion."),
                        output=mc.OutputSchema(fields=("result",), status_key=None))


class SelectedUnitTests(unittest.TestCase):
    def test_closed_unit_map_roundtrip_and_finite_numeric_validation(self):
        op = operation()
        contract = _contract(operations=(op,), evidence=_evidence(emits=(), note="Conversion is not validation."))
        self.assertEqual(mc.contract_from_dict(contract.to_dict()), contract)
        self.assertEqual(op.input[0].to_dict()["unitOptions"], {"C": "degC", "K": "K"})
        self.assertEqual(op.input_problems({"temperature": 300, "scale": "K"}), [])
        self.assertTrue(op.input_problems({"temperature": float("nan"), "scale": "C"}))
        self.assertTrue(op.input_problems({"temperature": 300, "scale": "F"}))

    def test_no_missing_or_ambiguous_units_or_cross_scale_bounds(self):
        for changes in ({"unit_selector": None}, {"unit_options": ()}, {"unit": "degC"},
                        {"unit_options": (("C", ""), ("K", "K"))}, {"min": 0}, {"step": 1},
                        {"unit_options": (("C", "degC"), ("C", "K"))}):
            with self.subTest(changes=changes), self.assertRaises(mc.ContractError):
                field(**changes)
        with self.assertRaises(mc.ContractError):
            field(value_type="enum", enum=("C", "K"), default="C")

    def test_selector_is_declared_enum_with_exact_unit_coverage(self):
        op = operation()
        for inputs in ((field(),), (field(unit_selector="absent"), op.input[1]),
                       (field(unit_options=(("C", "degC"),)), op.input[1])):
            with self.subTest(inputs=inputs), self.assertRaises(mc.ContractError):
                dataclasses.replace(op, input=inputs)
        flag = mc.InputField(key="scale", label="Flag", quantity_kind="flag", unit=None,
                             min=None, max=None, default=True, value_type="boolean")
        with self.assertRaises(mc.ContractError):
            dataclasses.replace(op, input=(field(), flag))

    def test_old_fixed_unit_contracts_read_and_bad_json_map_rejected(self):
        contract = _contract()
        old = contract.to_dict()
        for input_field in old["operations"][0]["input"]:
            input_field.pop("unitSelector")
            input_field.pop("unitOptions")
        self.assertEqual(mc.contract_from_dict(old), contract)
        new = _contract(operations=(operation(),), evidence=_evidence(emits=(), note="No physical oracle.")).to_dict()
        for bad_map in ("C", [], None):
            payload = copy.deepcopy(new)
            payload["operations"][0]["input"][0]["unitOptions"] = bad_map
            with self.subTest(bad_map=bad_map), self.assertRaises(mc.ContractError):
                mc.contract_from_dict(payload)


if __name__ == "__main__":
    unittest.main()
