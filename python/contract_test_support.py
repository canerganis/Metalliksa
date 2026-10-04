"""Shared scaffold for python/test_contract_<id>.py (Phase 7 module SDK).

Each contracted module gets a small test file that subclasses ``ContractScaffold``:
schema round trip through the committed generated JSON, contract-side range
rejection, resolvable references, and an oracle test that is skipped with a
reason while the oracle is pending (which keeps the evidence ceiling capped).
Authority-specific checks live in the per-module file.
"""
import importlib.util
import json
import math
import unittest
from pathlib import Path

import module_contract as mc
import module_registry as mr

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATED_JSON = REPO_ROOT / "src" / "generated" / "moduleRegistry.json"


def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def out_of_range_values(field: mc.InputField):
    """Values just outside each declared hard bound (none for an absent bound)."""
    values = []
    if field.min is not None:
        values.append(field.min - max(1.0, abs(field.min)))
    if field.max is not None:
        values.append(field.max + max(1.0, abs(field.max)))
    return values


class ContractScaffold:
    """Mixin; subclasses set MODULE_ID and inherit from unittest.TestCase."""
    MODULE_ID = ""

    @classmethod
    def setUpClass(cls):
        cls.contract = next(c for c in mr.build_registry() if c.id == cls.MODULE_ID)
        document = json.loads(GENERATED_JSON.read_text(encoding="utf-8"))
        cls.generated = next(c for c in document["contracts"] if c["id"] == cls.MODULE_ID)

    def test_contract_is_contracted(self):
        self.assertEqual(self.contract.migration_state, "contracted")

    def test_schema_round_trip(self):
        # Python -> JSON text -> Python rebuilds an equal, re-validated contract ...
        rebuilt = mc.contract_from_dict(json.loads(json.dumps(self.contract.to_dict())))
        self.assertEqual(rebuilt, self.contract)
        # ... and the committed generated JSON is that same contract.
        self.assertEqual(self.generated, self.contract.to_dict())
        self.assertEqual(mc.contract_from_dict(self.generated), self.contract)

    def test_defaults_pass_and_hard_ranges_reject(self):
        for operation in self.contract.operations:
            defaults = {f.key: f.default for f in operation.input}
            self.assertEqual(operation.input_problems(defaults), [], operation.id)
            self.assertEqual(operation.input_problems({}), [], "every key is optional at the authority")
            for field in operation.input:
                bad = list(out_of_range_values(field))
                if field.value_type in ("number", "integer"):
                    bad += [math.nan, math.inf, True, "1"]
                if field.value_type == "integer":
                    bad.append(field.default + 0.5)
                if field.value_type == "enum":
                    bad += ["not-a-member", 1]
                if field.value_type == "boolean":
                    bad += [1, "true"]
                for value in bad:
                    with self.subTest(operation=operation.id, key=field.key, value=value):
                        problems = operation.input_problems({**defaults, field.key: value})
                        self.assertEqual(len(problems), 1, problems)
                        self.assertTrue(problems[0].startswith(f"{field.key}:"), problems)
            self.assertTrue(operation.input_problems({**defaults, "zzUnknown": 1}))

    def test_references_resolve(self):
        self.assertEqual(mr.contract_ref_problems(self.contract), [])

    def test_oracle(self):
        oracle = self.contract.tests.oracle
        if oracle.status == "pending":
            self.skipTest(f"oracle pending for {self.MODULE_ID}: ceiling capped at {mc.PENDING_ORACLE_CEILING}")
        self.run_oracle(oracle.ref)

    def run_oracle(self, ref: str):  # pragma: no cover - overridden where an oracle exists
        self.fail(f"{self.MODULE_ID}: oracle {ref} is present but no runner is defined")


def run_unittest_ref(case: unittest.TestCase, ref: str) -> None:
    """Run ``path::Class.method`` from a python/ test module and fail on any failure."""
    path, symbol = ref.split("::")
    module = Path(path).stem
    suite = unittest.defaultTestLoader.loadTestsFromName(f"{module}.{symbol}")
    result = unittest.TestResult()
    suite.run(result)
    case.assertEqual(result.testsRun, 1, ref)
    case.assertEqual((result.failures, result.errors, result.skipped), ([], [], []), ref)
