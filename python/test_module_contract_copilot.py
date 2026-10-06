import json
import unittest
from pathlib import Path
from module_contract import ContractError, contract_from_dict
from module_contracts_copilot import build_copilot_contract
from module_registry import contract_ref_problems


class CopilotContractTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent
        seed = json.loads((self.root / "python/module_registry_seed.json").read_text(encoding="utf-8"))
        self.contract = build_copilot_contract(next(row for row in seed if row["id"] == "copilot"))

    def test_roundtrip_refs_and_nonpromotion(self):
        c = self.contract
        self.assertEqual(contract_from_dict(c.to_dict()), c)
        self.assertEqual(contract_ref_problems(c, generated=frozenset({"docs/modules/copilot.md"})), [])
        self.assertEqual((c.tests.oracle.status, c.evidence.ceiling, c.evidence.emits),
                         ("pending", "screening-only", ()))
        with self.assertRaises(ContractError):
            build_copilot_contract({"id": "wrong"})

    def test_real_provider_request_and_local_actions(self):
        operations = {op.id: op for op in self.contract.operations}
        consult = operations["consult"]
        self.assertEqual((consult.route, consult.method, consult.authority.timeout_ms),
                         ("/api/metallurgy/consult", "POST", 60000))
        view = (self.root / "src/components/MetallurgyCopilot.tsx").read_text(encoding="utf-8")
        route = (self.root / "routes/copilot.ts").read_text(encoding="utf-8")
        self.assertIn('fetch("/api/metallurgy/consult"', view)
        self.assertIn('history: apiHistory.slice(0, -1)', view)
        self.assertIn('return res.json({ response: text, text, answer: text })', route)
        self.assertEqual(consult.output.fields, ("response", "text", "answer", "error"))
        for name in ("edit-prompt", "copy-message", "clear-history"):
            self.assertIsNone(operations[name].route)
            self.assertIsNone(operations[name].authority.timeout_ms)
        notes = " ".join(self.contract.legacy_notes)
        self.assertIn("does not consume the history array", notes)
        self.assertIn("aborts the fetch", notes)
        self.assertIn('signal: request.signal', view)
        self.assertIn('requestLifecycle.current.isCurrent(request)', view)
        self.assertIn('requestLifecycle.current.invalidate()', view)
        self.assertEqual(set(consult.undeclared_input), {"prompt", "history", "message", "context", "systemInstruction"})
        self.assertIn("cannot enforce string length", notes)
        self.assertIn("not a scientific result", notes)


if __name__ == "__main__":
    unittest.main()
