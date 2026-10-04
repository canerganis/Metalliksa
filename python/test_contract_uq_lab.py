"""Contract scaffold for uq-lab (Phase 7 wave 1 pilot).

Run from the python directory:  python -B -m unittest test_contract_uq_lab
The oracle is pending, so the oracle test is skipped and the ceiling stays capped.
"""
import ast
import unittest
from pathlib import Path

import alloy_data_kinetics_uq_fatigue as uq_data
import stochastic_uq_mmpds_solver as solver
from contract_test_support import ContractScaffold

SOLVER = Path(__file__).resolve().parent / "stochastic_uq_mmpds_solver.py"


def authority_reads():
    """key -> default node for every params.get("key", default) in solve_stochastic_uq."""
    tree = ast.parse(SOLVER.read_text(encoding="utf-8"))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "solve_stochastic_uq")
    reads = {}
    for node in ast.walk(function):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get"
                and getattr(node.func.value, "id", None) == "params"):
            reads[node.args[0].value] = node.args[1]
    return reads


def sample_clamp():
    """(lower, upper) of the int(min(upper, max(lower, params.get("mcSamples", ...)))) clamp."""
    tree = ast.parse(SOLVER.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "min" and len(node.args) == 2:
            inner = node.args[1]
            if isinstance(inner, ast.Call) and getattr(inner.func, "id", None) == "max":
                getter = inner.args[1]
                if isinstance(getter, ast.Call) and getter.args and getattr(getter.args[0], "value", None) == "mcSamples":
                    return inner.args[0].value, node.args[0].value
    raise AssertionError("mcSamples clamp not found")


class UqLabContractScaffold(ContractScaffold, unittest.TestCase):
    MODULE_ID = "uq-lab"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (cls.operation,) = cls.contract.operations
        # 100 is outside the contract range; the authority clamps it (recorded gap).
        cls.clamped = solver.solve_stochastic_uq({"mcSamples": 100})

    def test_every_key_the_authority_reads_is_declared(self):
        reads = authority_reads()
        fields = {f.key: f for f in self.operation.input}
        self.assertEqual(set(reads), set(fields) | set(self.operation.undeclared_input))
        for key, node in reads.items():
            if key not in fields:
                continue
            with self.subTest(key=key):
                if isinstance(node, ast.Constant):
                    self.assertEqual(fields[key].default, node.value)
                else:  # module-level default, e.g. uq_data.UQ_DEFAULT_BASE_METAL
                    self.assertEqual(fields[key].default, getattr(uq_data, node.attr))

    def test_declared_bounds_and_choices_come_from_the_authority(self):
        fields = {f.key: f for f in self.operation.input}
        self.assertEqual((fields["mcSamples"].min, fields["mcSamples"].max), sample_clamp())
        self.assertEqual(set(fields["baseMetal"].enum), set(uq_data.UQ_BASE_METAL_LATTICE))
        self.assertEqual(fields["samplingMethod"].enum, ("sobol_qmc",))
        bounded = sorted(f.key for f in self.operation.input if f.min is not None or f.max is not None)
        self.assertEqual(bounded, ["mcSamples"], "no other bound is enforced by the authority")

    def test_authority_clamps_sample_count_the_contract_rejects(self):
        self.assertTrue(self.operation.input_problems({"mcSamples": 100}))
        self.assertEqual(self.clamped["sampleSizeN"], 500)

    def test_authority_rejects_pseudo_mc_like_the_contract(self):
        self.assertTrue(self.operation.input_problems({"samplingMethod": "pseudo_mc"}))
        with self.assertRaisesRegex(ValueError, "Pseudo-Random Monte Carlo is disabled"):
            solver.solve_stochastic_uq({"mcSamples": 500, "samplingMethod": "pseudo_mc"})

    def test_output_fields_match_authority_result(self):
        # The script entry point (also used by the warm IPC service) adds "provenance".
        self.assertEqual(tuple(self.clamped) + ("provenance",), self.operation.output.fields)
        self.assertNotIn(self.clamped["aerospaceReliability"]["qualificationStatus"], ("qualified", "certified"))


if __name__ == "__main__":
    unittest.main()
