"""The LPBF worker RPC relays Phase 6a validation errors as an envelope (fix round S1).

lpbf_fatigue_fracture raises input_validation.ValidationError (UNKNOWN_ALLOY) for an
unknown alloy; the worker reply must carry errorKind "validation" plus the envelope
so the Node bridge can answer HTTP 422, like the migrated dispatch-route solvers.
"""

import json
import unittest

import input_validation as iv
import lpbf_worker
import lpbf_worker_rpc


class RpcValidationErrorTest(unittest.TestCase):
    def test_fatigue_unknown_alloy_reply_carries_the_envelope(self):
        request = {"id": 7, "method": "fatigue-fracture", "payload": {"alloyName": "Unobtainium"}}
        with self.assertRaises(iv.ValidationError) as ctx:
            lpbf_worker_rpc.dispatch(request, None, lambda q: {})
        reply = lpbf_worker.rpc_error_response(request, ctx.exception)
        self.assertEqual(reply["id"], 7)
        self.assertEqual(reply["errorKind"], "validation")
        self.assertEqual(reply["error"], str(ctx.exception))
        env = reply["validation"]
        self.assertEqual(env, iv.validation_envelope(ctx.exception))
        self.assertEqual(env["error"]["code"], "UNKNOWN_ALLOY")
        self.assertIs(env["success"], False)
        json.dumps(reply, allow_nan=False)  # what the worker prints

    def test_other_errors_keep_the_plain_reply(self):
        reply = lpbf_worker.rpc_error_response({"id": 3}, ValueError("Unknown method"))
        self.assertEqual(reply, {"id": 3, "error": "Unknown method"})
        reply = lpbf_worker.rpc_error_response({}, ValueError("x"))
        self.assertEqual(reply, {"id": None, "error": "x"})
        reply = lpbf_worker.rpc_error_response("not a dict", ValueError("y"))
        self.assertEqual(reply, {"id": None, "error": "y"})

    def test_known_alloy_still_succeeds(self):
        request = {"id": 1, "method": "fatigue-fracture", "payload": {"alloyName": "Ti-6Al-4V"}}
        data = lpbf_worker_rpc.dispatch(request, None, lambda q: {})
        self.assertIn("fatigue_limit", data)


if __name__ == "__main__":
    unittest.main()
