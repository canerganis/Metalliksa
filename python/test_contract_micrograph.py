"""Contract checks for the micrograph module (micrograph rework).

The registry contract (python/module_registry.py _micrograph_contract) is checked against the
authority code: the keys and literal defaults read in micrograph_measure.read_request (AST), the
hard ranges the authority rejects (behaviour), the output keys of a real run, and the
diagnose-micrograph route source. The oracle is python/test_micrograph_measure.py (synthetic only).

Run from the python directory:  python -B -m unittest test_contract_micrograph
"""
import ast
import base64
import math
import unittest

import numpy as np

import micrograph_measure as mm
from contract_test_support import (PYTHON_DIR, ContractScaffold, function_node, get_reads, run_unittest_ref,
                                   worker_dispatch)

READ_REQUEST = function_node(PYTHON_DIR / "micrograph_measure.py", "read_request")
REPO = PYTHON_DIR.parent


def base_request():
    grey = np.full((40, 60), 200, np.uint8)
    grey[10:20, 10:30] = 20
    return {"imageWidth": 60, "imageHeight": 40, "imageData": base64.b64encode(grey.tobytes()).decode("ascii"),
            "darkMaxGrey": 100, "darkLabel": "pores"}


class MicrographContract(ContractScaffold, unittest.TestCase):
    MODULE_ID = "micrograph"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.measure, cls.describe = cls.contract.operations

    def run_oracle(self, ref):
        run_unittest_ref(self, ref)

    def test_operations_and_authorities(self):
        self.assertEqual((self.measure.id, self.measure.route, self.measure.authority.kind,
                          self.measure.authority.worker_method, self.measure.authority.timeout_ms),
                         ("micrograph-measure", "/api/python/micrograph-measure", "lpbf-worker", "micrograph-measure", 20000))
        self.assertEqual((self.describe.id, self.describe.route, self.describe.authority.kind,
                          self.describe.authority.timeout_ms),
                         ("diagnose-micrograph", "/api/metallurgy/diagnose-micrograph", "node-provider", 60000))
        route = (REPO / "routes" / "lpbfSimulation.ts").read_text(encoding="utf-8")
        self.assertIn('["post", "/api/python/micrograph-measure", "micrograph-measure"]', route)
        self.assertIn("request.timeoutMs ?? 60_000", (REPO / "server" / "openaiService.ts").read_text(encoding="utf-8"))

    def test_every_key_the_authority_reads_is_declared_with_its_literal_default(self):
        reads = get_reads(READ_REQUEST, "payload")
        fields = {f.key: f for f in self.measure.input}
        self.assertEqual(set(reads), set(fields) | set(self.measure.undeclared_input))
        self.assertEqual(set(reads), set(mm.REQUEST_KEYS), "unknown-key rejection uses the same key set")
        for key, field in fields.items():
            with self.subTest(key=key):
                default = ast.literal_eval(reads[key])
                self.assertEqual(field.default, default)
                self.assertIs(type(field.default), type(default))
                self.assertFalse(field.required)
        for key in self.measure.undeclared_input:
            self.assertIsNone(reads[key], f"{key} has no default in the authority")

    def test_declared_hard_ranges_are_enforced_by_the_authority(self):
        base = base_request()
        self.assertEqual(self.measure.input_problems({k: v for k, v in base.items()
                                                      if k not in self.measure.undeclared_input}), [])
        mm.measure(base)  # the base request is valid
        for field in self.measure.input:
            if field.value_type not in ("number", "integer"):
                continue
            for bound in (field.min, field.max):
                if bound is None:
                    continue
                outside = bound - 1 if bound == field.min else bound + 1
                with self.subTest(key=field.key, value=outside):
                    self.assertTrue(self.measure.input_problems({field.key: outside}))
                    with self.assertRaises(mm.MeasureInputError):
                        mm.measure({**base, field.key: outside})
            if field.value_type == "integer":
                with self.subTest(key=field.key, value="fraction"):
                    with self.assertRaises(mm.MeasureInputError):
                        mm.measure({**base, field.key: field.default + 0.5})
        with self.assertRaises(mm.MeasureInputError):
            mm.measure({**base, "returnMasks": 1})
        with self.assertRaises(mm.MeasureInputError):
            mm.measure({**base, "notAKey": 1})

    def test_output_fields_match_a_real_run_through_the_worker(self):
        result = worker_dispatch("micrograph-measure", base_request())
        self.assertEqual(tuple(result), self.measure.output.fields)
        self.assertIsNone(result["grainSize"])
        self.assertIsNotNone(result["calibrationRequired"])
        self.assertTrue(math.isclose(result["classes"]["dark"]["areaFraction"]["pixelFraction"]["value"], 200 / 2400))

    def test_diagnose_route_reads_and_defaults(self):
        route = (REPO / "routes" / "copilot.ts").read_text(encoding="utf-8")
        handler = route[route.index('"/api/metallurgy/diagnose-micrograph"'):]
        end = handler.find("copilotRouter.", 1)
        handler = handler if end < 0 else handler[:end]
        self.assertIn('req.body?.mimeType || "image/jpeg"', handler)
        (mime,) = self.describe.input
        self.assertEqual(mime.default, "image/jpeg")
        self.assertIn(f'[{", ".join(repr(v).replace(chr(39), chr(34)) for v in mime.enum)}]', handler)
        for key in ("imageBase64", "prompt"):
            self.assertIn(key, self.describe.undeclared_input)
            self.assertIn(key, handler)
        self.assertIn("diagnosis:", handler)

    def test_evidence_stays_bounded_and_honest(self):
        evidence = self.contract.evidence
        self.assertEqual(evidence.emits, ())
        self.assertEqual(evidence.ceiling, "screening-only")
        self.assertIn("no comparison with real micrographs", evidence.note)
        self.assertEqual(self.contract.tests.oracle.status, "present")
        self.assertIsNone(self.contract.tests.oracle.ci_note)


if __name__ == "__main__":
    unittest.main()
