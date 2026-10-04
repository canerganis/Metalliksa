"""Schema, closed-vocabulary and evidence-ceiling checks for module contracts.

Run from the python directory:  python -B -m unittest test_module_contract
"""
import dataclasses
import json
import re
import unittest
from pathlib import Path

import module_contract as mc
import module_registry as mr

REPO_ROOT = Path(__file__).resolve().parent.parent

# Ratchet mirrored in tests/module-registry.test.ts: Phase 7 step 0 generated
# one legacy contract per listed module. Migration may only lower this number.
LEGACY_CEILING = 37


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

    def test_timeout_required_only_where_code_runs_under_a_deadline(self):
        with self.assertRaises(mc.ContractError):
            mc.Authority(kind="python-ipc", script="python/x.py")
        with self.assertRaises(mc.ContractError):
            mc.Authority(kind="lpbf-worker", worker_method="get")
        self.assertIsNone(mc.Authority(kind="node-provider").timeout_ms)
        with self.assertRaises(mc.ContractError):
            mc.Authority(kind="node-provider", timeout_ms=0)

    def test_warm_applies_only_to_python_ipc(self):
        with self.assertRaises(mc.ContractError):
            mc.Authority(kind="lpbf-worker", worker_method="get", timeout_ms=1, warm=True)
        self.assertTrue(mc.Authority(kind="python-ipc", script="python/x.py", timeout_ms=1, warm=True).warm)

    def test_only_browser_local_operations_omit_a_route(self):
        local = mc.Authority(kind="browser-local", exception_reason="recorded debt")
        self.assertIsNone(mc.Operation(id="local", route=None, authority=local).route)
        with self.assertRaises(mc.ContractError):
            mc.Operation(id="remote", route=None, authority=mc.Authority(kind="node-provider"))

    def test_contracted_operations_must_declare_output(self):
        undeclared = mc.Operation(id="run", route="/api/uq/run",
                                  authority=mc.Authority(kind="python-ipc", script="uq_lab.py", timeout_ms=1))
        with self.assertRaises(mc.ContractError):
            _contract(operations=(undeclared,))
        self.assertIsNone(undeclared.to_dict()["output"])

    def test_legacy_notes_are_unique_text(self):
        with self.assertRaises(mc.ContractError):
            _contract(legacy_notes=("same", "same"))
        with self.assertRaises(mc.ContractError):
            _contract(legacy_notes=(" ",))

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

    def test_status_key_cannot_be_claim_key(self):
        for claim in mc.FORBIDDEN_CLAIM_KEYS:
            with self.subTest(claim=claim), self.assertRaises(mc.ContractError):
                mc.OutputSchema(fields=("value",), status_key=claim)
        with self.assertRaises(mc.ContractError):
            mc.OutputSchema(fields=("value",), status_key="value")
        self.assertEqual(mc.OutputSchema(fields=("value",)).status_key, "evidenceStatus")

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
        cls.app = (REPO_ROOT / "src" / "App.tsx").read_text(encoding="utf-8")
        cls.golden = json.loads((REPO_ROOT / "tests" / "fixtures" / "modules-nav-golden.json").read_text(encoding="utf-8"))

    def test_registry_matches_pre_registry_navigation_and_legacy_ratchet(self):
        # The registry is the navigation source since slice 1; the golden is the
        # hand-written MODULES list captured before derivation (same order).
        listed = [c for c in self.registry if c.navigation == "listed"]
        self.assertEqual(
            [{"id": c.id, "workspace": c.workspace, "label": c.label, "scope": c.maturity,
              "description": c.description, "next": c.next} for c in listed],
            self.golden)
        legacy = [c for c in self.registry if c.migration_state == "legacy"]
        # Ratchet: migration may lower the legacy count; it must never grow.
        self.assertLessEqual(len(legacy), LEGACY_CEILING)

    def test_workspaces_ts_no_longer_hand_lists_modules(self):
        workspaces = (REPO_ROOT / "src" / "data" / "workspaces.ts").read_text(encoding="utf-8")
        self.assertIn("LISTED_CONTRACTS", workspaces)
        self.assertNotRegex(workspaces, r"\{\s*id:\s*'[a-z0-9-]+',\s*workspace:")

    def test_render_module_switch_is_bounded_and_rejects_duplicates(self):
        trailing = self.app + "\nfunction later() { switch (x) { case 'zzz-extra': return <UQLab />; } }\n"
        self.assertNotIn("zzz-extra", mr.parse_app_views(trailing))
        first_case = re.search(r"case\s+'[^']+':\s*return\s*<\w+\s*/>;", self.app).group(0)
        duplicated = self.app.replace(first_case, first_case + " " + first_case, 1)
        with self.assertRaisesRegex(ValueError, "duplicate renderModule case"):
            mr.parse_app_views(duplicated)

    def test_seed_views_match_app_render_switch(self):
        self.assertEqual(mr.seed_view_mismatches(mr.load_seed(), self.app), [])
        drifted = [dict(row) for row in mr.load_seed()]
        drifted[0]["viewExport"] = "SomethingElse"
        self.assertEqual(len(mr.seed_view_mismatches(drifted, self.app)), 1)
        self.assertIn("App.tsx case without a registry module", mr.seed_view_mismatches(drifted[1:], self.app)[0])

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

    def test_legacy_operations_declare_authority_only(self):
        # Slice 1 records which authority each view calls; fields, outputs, validity
        # domains and source refs stay undeclared until a module is contracted.
        for contract in self.registry:
            for operation in contract.operations:
                with self.subTest(module=contract.id, operation=operation.id):
                    self.assertEqual(operation.input, ())
                    self.assertIsNone(operation.output)
                    if operation.authority.kind == "browser-local":
                        self.assertIn("Recorded debt", operation.authority.exception_reason)

    def test_legacy_authority_targets_exist_in_code(self):
        worker_routes = (REPO_ROOT / "routes" / "lpbfSimulation.ts").read_text(encoding="utf-8")
        for contract in self.registry:
            for operation in contract.operations:
                authority = operation.authority
                with self.subTest(module=contract.id, operation=operation.id):
                    if authority.kind == "python-ipc":
                        self.assertTrue((REPO_ROOT / authority.script).is_file(), authority.script)
                    if authority.kind == "lpbf-worker":
                        self.assertRegex(worker_routes, rf"[\"']{re.escape(authority.worker_method)}[\"']")

    def test_every_module_has_an_authority_or_a_recorded_gap(self):
        for contract in self.registry:
            with self.subTest(module=contract.id):
                self.assertTrue(contract.operations or contract.legacy_notes,
                                "record the authority or explain why none exists")


if __name__ == "__main__":
    unittest.main()
