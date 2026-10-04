"""Contract scaffold for keyhole-raytracing (Phase 7 wave 1 pilot).

Run from the python directory:  python -B -m unittest test_contract_keyhole_raytracing
Authority runs need NVIDIA Warp on the interpreter and are skipped without it.
"""
import ast
import unittest
from pathlib import Path

from contract_test_support import ContractScaffold, has_module, out_of_range_values, run_unittest_ref

SOLVER = Path(__file__).resolve().parent / "lpbf_keyhole_raytracing.py"
WARP = has_module("warp")


def _constant(node):
    # Bounds are literals or constant arithmetic such as 2**32 - 1.
    return eval(compile(ast.Expression(node), str(SOLVER), "eval"), {"__builtins__": {}})


def authority_bounds():
    """key -> (default, lower, upper, integer) from the _number(...) calls in the solver."""
    tree = ast.parse(SOLVER.read_text(encoding="utf-8"))
    bounds = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "_number" and len(node.args) >= 5:
            key = node.args[1].value
            integer = len(node.args) > 5 and node.args[5].value is True
            bounds[key] = tuple(_constant(arg) for arg in node.args[2:5]) + (integer,)
    return bounds


def authority_devices():
    tree = ast.parse(SOLVER.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Compare) and isinstance(node.ops[0], ast.NotIn)
                and getattr(node.left, "id", None) == "device_name"):
            return tuple(_constant(node.comparators[0]))
    raise AssertionError("device check not found")


class KeyholeContractScaffold(ContractScaffold, unittest.TestCase):
    MODULE_ID = "keyhole-raytracing"

    def operation(self):
        (operation,) = self.contract.operations
        return operation

    def test_fields_match_authority_validation(self):
        fields = {f.key: f for f in self.operation().input}
        bounds = authority_bounds()
        self.assertEqual(set(fields), set(bounds) | {"device"})
        for key, (default, lower, upper, integer) in bounds.items():
            field = fields[key]
            with self.subTest(key=key):
                self.assertEqual((field.default, field.min, field.max), (default, lower, upper))
                self.assertEqual(field.value_type, "integer" if integer else "number")
                self.assertFalse(field.required)
        self.assertEqual(fields["device"].enum, authority_devices())
        self.assertEqual(fields["device"].default, "cpu")

    @unittest.skipUnless(WARP, "NVIDIA Warp is not installed on this interpreter")
    def test_authority_rejects_what_the_contract_rejects(self):
        from lpbf_keyhole_raytracing import compute_keyhole_raytracing
        operation = self.operation()
        for field in operation.input:
            values = out_of_range_values(field) + (["cuda:7"] if field.key == "device" else [])
            for value in values:
                with self.subTest(key=field.key, value=value):
                    self.assertTrue(operation.input_problems({field.key: value}))
                    with self.assertRaises(ValueError):
                        compute_keyhole_raytracing({field.key: value})

    @unittest.skipUnless(WARP, "NVIDIA Warp is not installed on this interpreter")
    def test_output_fields_match_authority_result(self):
        from lpbf_keyhole_raytracing import compute_keyhole_raytracing
        result = compute_keyhole_raytracing(dict(nx=8, ny=8, dx=20e-6, dy=20e-6, num_rays=64, ui_ray_limit=4))
        self.assertEqual(tuple(result), self.operation().output.fields)

    def run_oracle(self, ref):
        if not WARP:
            self.skipTest("oracle present but NVIDIA Warp is not installed on this interpreter")
        run_unittest_ref(self, ref)


if __name__ == "__main__":
    unittest.main()
