"""Shared scaffold for python/test_contract_<id>.py (Phase 7 module SDK).

Each contracted module gets a small test file that subclasses ``ContractScaffold``:
schema round trip through the committed generated JSON, contract-side range
rejection, resolvable references, and an oracle test that is skipped with a
reason while the oracle is pending (which keeps the evidence ceiling capped).
Authority-specific checks live in the per-module file.
"""
import ast
import importlib.util
import json
import math
import os
import subprocess
import sys
import unittest
from pathlib import Path

import module_contract as mc
import module_registry as mr

PYTHON_DIR = Path(__file__).resolve().parent
REPO_ROOT = PYTHON_DIR.parent
GENERATED_JSON = REPO_ROOT / "src" / "generated" / "moduleRegistry.json"


# --- Authority helpers (Phase 7 wave 2) ----------------------------------------

def _tree(path: Path) -> ast.Module:
    return ast.parse(Path(path).read_text(encoding="utf-8"))


def function_node(path: Path, name: str) -> ast.AST:
    """The (first) function definition called ``name`` in a Python file."""
    for node in ast.walk(_tree(path)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {path}")


def main_block(path: Path) -> ast.AST:
    """The module-level ``if __name__ == "__main__":`` block of a Python file."""
    for node in _tree(path).body:
        if (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
                and getattr(node.test.left, "id", None) == "__name__"):
            return node
    raise AssertionError(f"no __main__ block in {path}")


def _is_get(node: ast.AST, receiver: str) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get"
            and getattr(node.func.value, "id", None) == receiver and bool(node.args)
            and isinstance(node.args[0], ast.Constant))


def _is_subscript(node: ast.AST, receiver: str) -> bool:
    return (isinstance(node, ast.Subscript) and getattr(node.value, "id", None) == receiver
            and isinstance(node.slice, ast.Constant))


def key_accesses(node: ast.AST, receiver: str) -> list:
    """Every way ``node`` reads the request dict ``receiver``: (key, kind, default node).

    kind is 'get' (``r.get("k", d)``), 'subscript' (``r["k"]``) or 'in' (``"k" in r``). Any other
    use of the receiver (a computed key, iteration, ``.items()``, passing it on whole) is returned
    with key None and kind 'escape', because the key set can then no longer be read from the code.
    """
    parents = {child: parent for parent in ast.walk(node) for child in ast.iter_child_nodes(parent)}
    accesses = []
    for name in ast.walk(node):
        if not (isinstance(name, ast.Name) and name.id == receiver and isinstance(name.ctx, ast.Load)):
            continue
        parent = parents.get(name)
        grand = parents.get(parent)
        if isinstance(parent, ast.Attribute) and parent.attr == "get" and _is_get(grand, receiver):
            accesses.append((grand.args[0].value, "get", grand.args[1] if len(grand.args) > 1 else None))
        elif _is_subscript(parent, receiver):
            accesses.append((parent.slice.value, "subscript", None))
        elif (isinstance(parent, ast.Compare) and len(parent.ops) == 1 and isinstance(parent.ops[0], (ast.In, ast.NotIn))
              and parent.comparators[0] is name and isinstance(parent.left, ast.Constant)):
            accesses.append((parent.left.value, "in", None))
        else:
            accesses.append((None, "escape", getattr(name, "lineno", None)))
    return accesses


def get_reads(node: ast.AST, receiver: str) -> dict:
    """key -> default node (None without one) for every read of the request dict ``receiver``.

    Fails on a read the AST cannot attribute to a literal key (see key_accesses) and on a key read
    more than once, so a second read with another default cannot hide behind the first.
    """
    accesses = key_accesses(node, receiver)
    escapes = [line for key, kind, line in accesses if kind == "escape"]
    if escapes:
        raise AssertionError(f"{receiver} is used in a way the key check cannot follow (lines {escapes})")
    keys = [key for key, _, _ in accesses]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        raise AssertionError(f"{receiver} reads these keys more than once: {duplicates}")
    return {key: default for key, _, default in accesses}


def get_conversions(node: ast.AST, receiver: str) -> dict:
    """key -> 'float' | 'int' | 'bool' when the read is wrapped in that conversion, else None."""
    conversions = {key: None for key in get_reads(node, receiver)}
    for call in ast.walk(node):
        if (isinstance(call, ast.Call) and getattr(call.func, "id", None) in ("float", "int", "bool") and call.args):
            inner = call.args[0]
            if _is_get(inner, receiver):
                conversions[inner.args[0].value] = call.func.id
            elif _is_subscript(inner, receiver):
                conversions[inner.slice.value] = call.func.id
    return conversions


def run_script(script: str, payload: dict) -> tuple:
    """Run a python/ solver script the way the dispatch route does (JSON on stdin).

    Returns (exit code, parsed stdout). The warm IPC service executes the same entry point.
    """
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run([sys.executable, "-B", str(PYTHON_DIR / script)], input=json.dumps(payload),
                          capture_output=True, text=True, cwd=str(PYTHON_DIR), env=env, timeout=300)
    try:
        return proc.returncode, json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{script} printed no JSON (exit {proc.returncode}); stderr: {proc.stderr}") from exc


def worker_dispatch(method: str, payload: dict):
    """Call the LPBF worker RPC handler exactly as python/lpbf_worker.py does for ``method``."""
    import lpbf_worker_rpc
    return lpbf_worker_rpc.dispatch({"method": method, "payload": payload}, None, lambda queue: {})


class AuthorityReadsMixin:
    """Checks a single-operation contract against the authority's key reads (AST)."""

    def assert_reads_match(self, operation: mc.Operation, reads: dict) -> None:
        fields = {f.key: f for f in operation.input}
        self.assertEqual(set(reads), set(fields) | set(operation.undeclared_input),
                         "every key the authority reads is declared or recorded as undeclared")
        for key, node in reads.items():
            if key not in fields:
                continue
            with self.subTest(key=key):
                self.assertIsNotNone(node, "a declared optional key has a literal default in the authority")
                default = ast.literal_eval(node)  # declared defaults are literals in the authority (e.g. -1.0)
                self.assertEqual(fields[key].default, default)
                # Same type as well as value: 64 (int) and 64.0 (float) are different defaults.
                self.assertIs(type(fields[key].default), type(default))
                self.assertFalse(fields[key].required)
                self.assertIsNone(fields[key].min, "the authority enforces no bound")
                self.assertIsNone(fields[key].max, "the authority enforces no bound")

    CONVERSION_PHRASES = {"float": "Converted with float()", "int": "Converted with int()",
                          "bool": "coerces with bool()", None: "Passed unconverted"}

    def assert_conversion_notes(self, operation: mc.Operation, conversions: dict) -> None:
        """Both directions: every number/integer/boolean field note states exactly the conversion the
        authority applies (float()/int()/bool() or none), and int() <-> valueType integer."""
        for field in operation.input:
            with self.subTest(key=field.key):
                note = field.note or ""
                stated = [conv for conv, phrase in self.CONVERSION_PHRASES.items() if phrase in note]
                actual = conversions[field.key]
                if field.value_type in ("number", "integer", "boolean"):
                    self.assertEqual(stated, [actual], "the note must state the authority's conversion")
                else:
                    self.assertIn(stated, ([], [actual]))
                self.assertEqual(field.value_type == "integer", actual == "int",
                                 "int()-converted keys are integer fields and integer fields are int()-converted")


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
