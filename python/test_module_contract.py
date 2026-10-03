"""Schema, closed-vocabulary and evidence-ceiling checks for module contracts.

Run from the python directory:  python -B -m unittest test_module_contract
"""
import dataclasses
import re
import unittest
from pathlib import Path

import module_contract as mc
import module_registry as mr

REPO_ROOT = Path(__file__).resolve().parent.parent


def _view():
    return mc.View(component="src/components/UQLab.tsx", export="UQLab")


def _field(**overrides):
    values = dict(key="power_W", label="Laser power", unit="W", quantity_kind="power",
                  min=50.0, max=400.0, default=200.0, display_units=("W", "kW"))
    values.update(overrides)
    return mc.InputField(**values)


def _operation(**authority_overrides):
    authority = dict(kind="python-ipc", script="uq_lab.py", timeout_ms=30000)
    authority.update(authority_overrides)
    return mc.Operation(id="run", route="/api/uq/run", authority=mc.Authority(**authority),
                        input=(_field(),), output=mc.OutputSchema(fields=("samples",)))


def _evidence(**overrides):
    values = dict(emits=("screening-only", "unvalidated"), ceiling="screening-only",
                  forbidden_claims=mc.FORBIDDEN_CLAIM_KEYS)
    values.update(overrides)
    return mc.Evidence(**values)


def _contract(**overrides):
    values = dict(id="uq-lab", version="1.0.0", owner="evidence-team", workspace="evidence",
                  label="Uncertainty", description="Sampling.", next="qualification",
                  maturity="Research", navigation="listed", view=_view(), evidence=_evidence(),
                  tests=mc.TestRefs(schema="python/test_contract_uq_lab.py"),
                  migration_state="contracted", operations=(_operation(),),
                  lifecycle=mc.Lifecycle(background_work="none"))
    values.update(overrides)
    return mc.ModuleContract(**values)


class ClosedVocabularyTests(unittest.TestCase):
    def test_evidence_types_mirror_research_ts(self):
        source = (REPO_ROOT / "src" / "types" / "research.ts").read_text(encoding="utf-8")
        match = re.search(r"export const EVIDENCE_TYPES = \[([^\]]*)\] as const", source)
        self.assertIsNotNone(match)
        self.assertEqual(tuple(re.findall(r"'([^']+)'", match.group(1))), mc.EVIDENCE_TYPES)

    def test_single_status_vocabulary_is_disjoint_union(self):
        self.assertEqual(mc.EVIDENCE_STATUSES, mc.EVIDENCE_TYPES + mc.RUN_STATES)
        self.assertFalse(set(mc.EVIDENCE_TYPES) & set(mc.RUN_STATES))
        self.assertEqual(mc.RUN_STATES, ("unvalidated", "inconclusive", "unavailable", "outside-validity-domain"))

    def test_valid_contract_builds_and_is_frozen(self):
        contract = _contract()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            contract.maturity = "Preview"  # type: ignore[misc]
        self.assertEqual(contract.to_dict()["migrationState"], "contracted")

    def test_production_maturity_is_barred(self):
        for maturity in ("Production", "Unresolved", "research"):
            with self.subTest(maturity=maturity), self.assertRaises(mc.ContractError):
                _contract(maturity=maturity)

    def test_closed_enums_reject_unknown_values(self):
        cases = [
            lambda: _contract(navigation="visible"),
            lambda: _contract(workspace="unknown"),
            lambda: _contract(migration_state="partial"),
            lambda: _operation(kind="shell"),
            lambda: _operation(gpu="maybe"),
            lambda: mc.Lifecycle(background_work="forever"),
            lambda: mc.Lifecycle(background_work="none", resources=("websocket",)),
            lambda: mc.Oracle(status="done"),
            lambda: _evidence(emits=("qualified",)),
            lambda: _evidence(ceiling="unvalidated"),
        ]
        for index, build in enumerate(cases):
            with self.subTest(case=index), self.assertRaises(mc.ContractError):
                build()

    def test_hidden_navigation_requires_reason(self):
        with self.assertRaises(mc.ContractError):
            _contract(navigation="hidden")
        with self.assertRaises(mc.ContractError):
            _contract(navigation="listed", hidden_reason="not hidden")
        self.assertEqual(_contract(navigation="hidden", hidden_reason="authority missing").hidden_reason,
                         "authority missing")

    def test_identity_formats(self):
        with self.assertRaises(mc.ContractError):
            _contract(version="1.0")
        with self.assertRaises(mc.ContractError):
            _contract(id="UQ Lab")
        with self.assertRaises(mc.ContractError):
            _contract(view=mc.View(component="src/App.tsx", export="App"))


class FieldAndAuthorityTests(unittest.TestCase):
    def test_hard_range_and_default(self):
        with self.assertRaises(mc.ContractError):
            _field(min=500.0)
        with self.assertRaises(mc.ContractError):
            _field(default=1000.0)
        with self.assertRaises(mc.ContractError):
            _field(max=float("inf"))
        with self.assertRaises(mc.ContractError):
            _field(step=0.0)

    def test_enum_default_must_be_member(self):
        self.assertEqual(_field(enum=("a", "b"), default="a").default, "a")
        with self.assertRaises(mc.ContractError):
            _field(enum=("a", "b"), default="c")

    def test_authority_requirements(self):
        with self.assertRaises(mc.ContractError):
            _operation(script=None)
        with self.assertRaises(mc.ContractError):
            _operation(kind="lpbf-worker", script=None)
        with self.assertRaises(mc.ContractError):
            _operation(kind="browser-local", script=None)
        self.assertEqual(_operation(kind="browser-local", script=None,
                                    exception_reason="recorded debt").authority.kind, "browser-local")
        with self.assertRaises(mc.ContractError):
            _operation(timeout_ms=0)

    def test_route_must_be_api(self):
        with self.assertRaises(mc.ContractError):
            mc.Operation(id="run", route="uq/run", authority=mc.Authority(kind="node-provider", timeout_ms=1),
                         input=(), output=mc.OutputSchema(fields=("x",)))

    def test_validity_domain_requires_sources(self):
        rng = mc.FieldRange(key="power_W", min=100.0, max=300.0, unit="W")
        with self.assertRaises(mc.ContractError):
            mc.ValidityDomain(ranges=(rng,), source_refs=())
        self.assertEqual(len(mc.ValidityDomain(ranges=(rng,), source_refs=("ref",)).ranges), 1)


class EvidenceCeilingTests(unittest.TestCase):
    def test_emits_must_not_exceed_ceiling(self):
        with self.assertRaises(mc.ContractError):
            _evidence(emits=("calibrated-simulation",), ceiling="screening-only")
        self.assertTrue(mc.within_ceiling("unresolved", "screening-only"))
        self.assertFalse(mc.within_ceiling("measured", "screening-only"))

    def test_run_states_are_always_within_ceiling(self):
        for state in mc.RUN_STATES:
            for ceiling in mc.EVIDENCE_TYPES:
                self.assertTrue(mc.within_ceiling(state, ceiling))

    def test_pending_oracle_caps_ceiling(self):
        strong = _evidence(emits=("calibrated-simulation",), ceiling="calibrated-simulation")
        with self.assertRaises(mc.ContractError):
            _contract(evidence=strong)
        present = mc.TestRefs(schema="python/test_contract_uq_lab.py",
                              oracle=mc.Oracle(status="present", ref="python/test_uq_oracle.py"))
        self.assertEqual(_contract(evidence=strong, tests=present).evidence.ceiling, "calibrated-simulation")

    def test_present_oracle_requires_reference(self):
        with self.assertRaises(mc.ContractError):
            mc.Oracle(status="present")


class ForbiddenClaimTests(unittest.TestCase):
    def test_always_forbidden_claims_required(self):
        for claim in mc.ALWAYS_FORBIDDEN_CLAIMS:
            remaining = tuple(c for c in mc.FORBIDDEN_CLAIM_KEYS if c != claim)
            with self.subTest(claim=claim), self.assertRaises(mc.ContractError):
                _evidence(forbidden_claims=remaining)

    def test_unknown_claim_key_rejected(self):
        with self.assertRaises(mc.ContractError):
            _evidence(forbidden_claims=mc.FORBIDDEN_CLAIM_KEYS + ("approved",))

    def test_measured_and_validated_forbidden_below_their_ceiling(self):
        base = ("qualified", "certified", "productionReady", "airworthy")
        with self.assertRaises(mc.ContractError):
            _evidence(forbidden_claims=base + ("validated",))
        with self.assertRaises(mc.ContractError):
            _evidence(forbidden_claims=base + ("measured",))
        self.assertEqual(_evidence(emits=("measured",), ceiling="measured", forbidden_claims=base).ceiling,
                         "measured")

    def test_output_fields_cannot_be_claim_keys(self):
        for claim in mc.FORBIDDEN_CLAIM_KEYS:
            with self.subTest(claim=claim), self.assertRaises(mc.ContractError):
                mc.OutputSchema(fields=("value", claim))

    def test_contracted_requires_reviewed_owner_and_operations(self):
        with self.assertRaises(mc.ContractError):
            _contract(owner=f"{mc.TODO_MARKER}: unassigned")
        with self.assertRaises(mc.ContractError):
            _contract(operations=())
        with self.assertRaises(mc.ContractError):
            _contract(evidence=_evidence(emits=()))


class LegacyRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = mr.build_registry()
        cls.workspaces = (REPO_ROOT / "src" / "data" / "workspaces.ts").read_text(encoding="utf-8")
        cls.app = (REPO_ROOT / "src" / "App.tsx").read_text(encoding="utf-8")

    def test_one_legacy_contract_per_listed_module(self):
        modules = mr.parse_workspaces_modules(self.workspaces)
        self.assertEqual(len(modules), self.workspaces.count("{ id: '") - 4)  # minus WORKSPACES rows
        self.assertEqual([c.id for c in self.registry], [m["id"] for m in modules])
        self.assertTrue(all(c.migration_state == "legacy" for c in self.registry))

    def test_seed_matches_typescript_sources(self):
        self.assertEqual(mr.load_seed(), mr.build_seed(self.workspaces, self.app),
                         "seed drifted; run python scripts/emit-module-registry.py --refresh-seed")

    def test_generated_files_are_current(self):
        self.assertEqual(mr.stale_outputs(), [], "run python scripts/emit-module-registry.py")

    def test_legacy_contracts_make_no_reviewed_claims(self):
        for contract in self.registry:
            with self.subTest(module=contract.id):
                self.assertEqual(contract.evidence.emits, ())
                self.assertEqual(contract.evidence.ceiling, mc.PENDING_ORACLE_CEILING)
                self.assertEqual(contract.evidence.forbidden_claims, mc.FORBIDDEN_CLAIM_KEYS)
                self.assertIn(mc.TODO_MARKER, contract.owner)
                self.assertIn(mc.TODO_MARKER, contract.evidence.note)
                self.assertEqual(contract.tests.oracle.status, "pending")
                self.assertEqual(contract.navigation, "listed")
                self.assertIsNone(contract.validity_domain)

    def test_views_exist(self):
        for contract in self.registry:
            with self.subTest(module=contract.id):
                self.assertTrue((REPO_ROOT / contract.view.component).is_file())


if __name__ == "__main__":
    unittest.main()
