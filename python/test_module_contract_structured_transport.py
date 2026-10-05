"""Structured availability remains distinct from scientific evidence."""
import dataclasses
import copy
import unittest

import module_contract as mc
from test_module_contract import _contract, _evidence, _operation


class StructuredTransportTests(unittest.TestCase):
    def output(self, *, key="criticalTemperatureStatus", members=None, **kwargs):
        return mc.OutputSchema(fields=(key,), status_key=None,
            transport_objects=((key, members if members is not None else (
                ("liquidusC.status", ("bisected", "bracketed-by-grid", "unavailable")),
                ("freezingRangeC.status", ("computed", "unavailable")),
            )),), **kwargs)

    def test_closed_status_paths_round_trip_without_evidence(self):
        output = self.output()
        contract = _contract(operations=(dataclasses.replace(_operation(), output=output),),
            evidence=_evidence(emits=(), note="Computed-path availability is not validation."))
        self.assertEqual(mc.contract_from_dict(contract.to_dict()), contract)
        self.assertEqual(output.to_dict()["transportObjects"]["criticalTemperatureStatus"], {
            "liquidusC.status": ["bisected", "bracketed-by-grid", "unavailable"],
            "freezingRangeC.status": ["computed", "unavailable"],
        })
        self.assertEqual(contract.evidence.emits, ())

    def test_scalar_and_structured_declarations_cannot_overlap(self):
        with self.assertRaises(mc.ContractError):
            self.output(transport_values=(("criticalTemperatureStatus", ("computed",)),))

    def test_hidden_evidence_and_claims_remain_forbidden(self):
        for key in ("evidenceStatus", "evidence_status", "validated"):
            with self.subTest(key=key), self.assertRaises(mc.ContractError):
                self.output(key=key)
        for path in ("measured.status", "result.evidenceStatus", "result.evidence_status", "status..leaf", "status/value", "result"):
            with self.subTest(path=path), self.assertRaises(mc.ContractError):
                self.output(members=((path, ("computed",)),))
        for value in ("measured", "qualified", "screening-only", "unvalidated", "validated-simulation"):
            with self.subTest(value=value), self.assertRaises(mc.ContractError):
                self.output(members=(("liquidusC.status", (value,)),))

    def test_empty_duplicate_and_unknown_declarations_are_rejected(self):
        for members in ((), (("x.status", ()),), (("x.status", ("computed", "computed")),),
                        (("x.status", ("computed",)), ("x.status", ("unavailable",)))):
            with self.subTest(members=members), self.assertRaises(mc.ContractError):
                self.output(members=members)
        with self.assertRaises(mc.ContractError):
            mc.OutputSchema(fields=("value",), status_key=None,
                transport_objects=(("criticalTemperatureStatus", (("x.status", ("computed",)),)),))
        with self.assertRaises(mc.ContractError):
            mc.OutputSchema(fields=("criticalTemperatureStatus",), status_key="criticalTemperatureStatus",
                transport_objects=(("criticalTemperatureStatus", (("x.status", ("computed",)),)),))
        with self.assertRaises(mc.ContractError):
            mc.OutputSchema(fields=("criticalTemperatureStatus",), status_key=None,
                transport_objects=(("criticalTemperatureStatus", (("x.status", ("computed",)),)),
                                   ("criticalTemperatureStatus", (("y.status", ("computed",)),))))
        with self.assertRaises(mc.ContractError):
            mc.OutputSchema(fields=("criticalTemperatureStatus",), status_key="evidenceStatus",
                transport_objects=(("criticalTemperatureStatus", (("x.status", ("unavailable",)),)),))

    def test_old_contract_without_structured_extension_still_loads(self):
        contract = _contract()
        payload = contract.to_dict()
        payload["operations"][0]["output"].pop("transportObjects")
        self.assertEqual(mc.contract_from_dict(payload), contract)

    def test_malformed_json_cannot_turn_vocabulary_strings_into_character_enums(self):
        contract = _contract(operations=(dataclasses.replace(_operation(), output=self.output()),),
                             evidence=_evidence(emits=(), note="Transport shapes are not scientific evidence."))
        original = contract.to_dict()
        mutations = (
            lambda out: out.update(transportObjects=[]),
            lambda out: out["transportObjects"].update(criticalTemperatureStatus=[]),
            lambda out: out["transportObjects"]["criticalTemperatureStatus"].update({"freezingRangeC.status": "computed"}),
            lambda out: out["transportObjects"]["criticalTemperatureStatus"].update({"freezingRangeC.status": {"computed": True}}),
            lambda out: out.update(transportValues=[]),
            lambda out: out["transportValues"].update(status="computed"),
            lambda out: out.update(fields="criticalTemperatureStatus"),
        )
        for mutation in mutations:
            payload = copy.deepcopy(original)
            mutation(payload["operations"][0]["output"])
            with self.subTest(mutation=mutation), self.assertRaises(mc.ContractError):
                mc.contract_from_dict(payload)


if __name__ == "__main__":
    unittest.main()
