import json
from pathlib import Path
import unittest

from module_contract import contract_from_dict
from module_contracts_calibration_scorecard import build_calibration_scorecard_contract
from module_registry import contract_ref_problems


class CalibrationScorecardContractTests(unittest.TestCase):
    def setUp(self):
        seed = json.loads(Path(__file__).with_name("module_registry_seed.json").read_text(encoding="utf-8"))
        self.contract = build_calibration_scorecard_contract(next(r for r in seed if r["id"] == "lpbf-calibration-scorecard"))

    def test_local_read_only_authority_has_no_solver_or_deadline(self):
        operation, = self.contract.operations
        self.assertEqual(operation.authority.kind, "browser-local")
        self.assertIsNone(operation.authority.timeout_ms)
        self.assertIsNone(operation.authority.script)
        self.assertIsNone(operation.route)
        self.assertEqual(self.contract.lifecycle.background_work, "none")

    def test_display_does_not_promote_any_evidence_label(self):
        self.assertEqual(self.contract.evidence.ceiling, "screening-only")
        self.assertEqual(self.contract.evidence.emits, ())
        self.assertEqual(self.contract.tests.oracle.status, "pending")
        self.assertIn("validated", self.contract.evidence.forbidden_claims)
        self.assertEqual(contract_from_dict(self.contract.to_dict()), self.contract)

    def test_sources_resolve_and_absent_malformed_limits_are_declared(self):
        self.assertEqual(contract_ref_problems(self.contract, generated=frozenset((self.contract.tests.docs,))), [])
        notes = " ".join(self.contract.legacy_notes)
        self.assertIn("absent record", notes)
        self.assertIn("malformed", notes)
        self.assertIn("screening only", notes)


if __name__ == "__main__":
    unittest.main()
