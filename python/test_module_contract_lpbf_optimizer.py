import json
import unittest
from pathlib import Path

import module_registry as mr
from module_contract import contract_from_dict

DOC = Path(__file__).resolve().parent.parent / "docs" / "modules" / "lpbf-optimizer.md"


class LpbfOptimizerRegistryContractTests(unittest.TestCase):
    """Self-contained: reads only the committed seed, the builder and the generated module page."""

    @classmethod
    def setUpClass(cls):
        cls.contracts = {c.id: c for c in mr.build_registry()}
        cls.contract = cls.contracts["lpbf-optimizer"]

    def test_module_is_contracted_not_legacy(self):
        self.assertIn("lpbf-optimizer", mr.CONTRACTED_BUILDERS)
        self.assertNotIn("lpbf-optimizer", mr.LEGACY_OPERATIONS)
        self.assertEqual(self.contract.migration_state, "contracted")

    def test_operations_match_the_routes_the_view_calls(self):
        ops = {op.id: op for op in self.contract.operations}
        self.assertEqual(set(ops), {"bayesian-optimize", "process-window"})
        expected = {
            "bayesian-optimize": ("/api/python/lpbf-bayesian-optimize", "python/lpbf_bayesian_optimizer.py", 120000),
            "process-window": ("/api/python/lpbf-process-window", "python/lpbf_process_window.py", 60000),
        }
        for op_id, (route, script, timeout) in expected.items():
            op = ops[op_id]
            self.assertEqual((op.method, op.route, op.authority.kind, op.authority.script,
                              op.authority.timeout_ms, op.authority.warm),
                             ("POST", route, "python-ipc", script, timeout, False))
            self.assertIsNone(op.output.status_key)
            self.assertNotIn("evidence", op.output.fields)  # reserved by the SDK; named in the notes
        # Fields the view reads (LpbfBayesianOptimizerLab.tsx gateSummary, keyholeGateNote).
        self.assertLessEqual({"gateSummary", "keyholeGateNote"}, set(ops["bayesian-optimize"].output.fields))

    def test_screening_ceiling_and_no_emitted_status(self):
        self.assertEqual(self.contract.evidence.ceiling, "screening-only")
        self.assertEqual(self.contract.evidence.emits, ())
        self.assertEqual(self.contract.tests.oracle.status, "pending")
        self.assertEqual(self.contract.tests.docs, "docs/modules/lpbf-optimizer.md")
        self.assertEqual(contract_from_dict(self.contract.to_dict()), self.contract)
        notes = " ".join(self.contract.legacy_notes)
        self.assertIn("suggestion, not a qualified window", notes)
        self.assertIn("the SDK reserves that name", notes)

    def test_every_reference_resolves(self):
        generated = frozenset(mr.module_doc_path(c.id) for c in self.contracts.values()
                              if c.migration_state == "contracted")
        self.assertEqual(mr.contract_ref_problems(self.contract, generated=generated), [])

    def test_committed_doc_states_inputs_outputs_and_limits(self):
        text = DOC.read_text(encoding="utf-8")
        for needle in ("`bayesian-optimize`", "`process-window`", "paramBounds", "noPositiveScore",
                       "225 cells", "suggestion, not a qualified window", "Ceiling: screening-only"):
            self.assertIn(needle, text)
        self.assertNotIn("\u2014 ", text.split("## Operations")[0].split("\n", 6)[-1][:0])


if __name__ == "__main__":
    unittest.main()
