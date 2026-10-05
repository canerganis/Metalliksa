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
LEGACY_CEILING = 17  # 16 + the read-only lpbf-dataset-comparison view (legacy contract, no operations; LPBF batch 1)
# Registry (seed) order. Wave 1 pilots: keyhole-raytracing, uq-lab; the rest are Phase 7 wave 2.
CONTRACTED = ("toolpath-studio", "murakami-fatigue", "adaptive-mitigation",
              "keyhole-raytracing", "ttt-cct-kinetics", "micrograph", "icme-motor", "uq-lab")


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
    return mc.Operation(id="run", method="POST", route="/api/uq/run", authority=mc.Authority(**authority),
                        input=(_field(),), output=mc.OutputSchema(fields=("samples",)))


def _evidence(**overrides):
    values = dict(emits=("screening-only", "unvalidated"), ceiling="screening-only",
                  forbidden_claims=mc.FORBIDDEN_CLAIM_KEYS)
    values.update(overrides)
    return mc.Evidence(**values)


def _contract(**overrides):
    values = dict(id="uq-lab", version="1.0.0", owner=mc.OWNER_UNASSIGNED, workspace="evidence",
                  label="Uncertainty", description="Sampling.", next="qualification",
                  maturity="Research", navigation="listed", view=_view(), evidence=_evidence(),
                  tests=mc.TestRefs(schema="python/test_contract_uq_lab.py", docs="docs/modules/uq-lab.md"),
                  migration_state="contracted", operations=(_operation(),),
                  lifecycle=mc.Lifecycle(background_work="none"),
                  source_refs=("python/stochastic_uq_mmpds_solver.py",))
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
        enum = dict(value_type="enum", unit=None, min=None, max=None, display_units=())
        self.assertEqual(_field(enum=("a", "b"), default="a", **enum).default, "a")
        with self.assertRaises(mc.ContractError):
            _field(enum=("a", "b"), default="c", **enum)
        with self.assertRaises(mc.ContractError):
            _field(enum=("a", "b"), default="a")  # a number field cannot carry an enum
        with self.assertRaises(mc.ContractError):
            _field(enum=(), default="a", **enum)

    def test_value_types_and_absent_bounds(self):
        # An unestablished bound stays None; it is never guessed.
        open_field = _field(min=None, max=None, default=-5.0)
        self.assertIsNone(open_field.value_problem(1e9))
        self.assertEqual(open_field.to_dict()["min"], None)
        with self.assertRaises(mc.ContractError):
            _field(unit=None)
        with self.assertRaises(mc.ContractError):
            _field(value_type="string")
        with self.assertRaises(mc.ContractError):
            _field(value_type="integer", default=2.5, min=0, max=10)
        with self.assertRaises(mc.ContractError):
            _field(value_type="integer", default=2, min=0, max=10, step=0.5)
        flag = dict(value_type="boolean", unit=None, min=None, max=None, display_units=())
        self.assertTrue(_field(default=True, **flag).default)
        with self.assertRaises(mc.ContractError):
            _field(default=1, **flag)
        with self.assertRaises(mc.ContractError):
            _field(default=True, step=1, **flag)  # boolean fields carry no step
        with self.assertRaises(mc.ContractError):
            _field(note=" ")

    def test_input_problems_rejects_without_coercing(self):
        count = _field(key="n", value_type="integer", unit="1", quantity_kind="count", min=1, max=10,
                       default=5, required=False, display_units=())
        operation = mc.Operation(id="run", method="POST", route="/api/x", input=(_field(), count),
                                 authority=mc.Authority(kind="node-provider", timeout_ms=1),
                                 undeclared_input=("label",))
        self.assertEqual(operation.input_problems({"power_W": 200.0, "label": "free text"}), [])
        self.assertEqual(operation.input_problems({}), ["power_W: required"])
        cases = {"power_W": [49.0, 401.0, float("nan"), True, "200"], "n": [0, 11, 2.5]}
        for key, values in cases.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    problems = operation.input_problems({"power_W": 200.0, key: value})
                    self.assertEqual(len(problems), 1)
                    self.assertTrue(problems[0].startswith(key))
        self.assertEqual(operation.input_problems({"power_W": 200.0, "extra": 1}), ["extra: not declared by the contract"])
        self.assertEqual(operation.input_problems([]), ["payload must be an object"])
        with self.assertRaises(mc.ContractError):
            mc.Operation(id="run", method="POST", route="/api/x", input=(_field(),),
                         authority=mc.Authority(kind="node-provider", timeout_ms=1), undeclared_input=("power_W",))

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

    def test_routed_operations_need_an_http_method(self):
        node = mc.Authority(kind="node-provider")
        with self.assertRaises(mc.ContractError):
            mc.Operation(id="remote", route="/api/x", authority=node)
        with self.assertRaises(mc.ContractError):
            mc.Operation(id="remote", method="FETCH", route="/api/x", authority=node)
        with self.assertRaises(mc.ContractError):
            mc.Operation(id="local", method="GET", route=None,
                         authority=mc.Authority(kind="browser-local", exception_reason="recorded debt"))
        self.assertEqual(mc.Operation(id="remote", method="GET", route="/api/x", authority=node).to_dict()["method"], "GET")

    def test_contracted_operations_must_declare_output(self):
        undeclared = mc.Operation(id="run", method="POST", route="/api/uq/run",
                                  authority=mc.Authority(kind="python-ipc", script="uq_lab.py", timeout_ms=1))
        with self.assertRaises(mc.ContractError):
            _contract(operations=(undeclared,))
        self.assertIsNone(undeclared.to_dict()["output"])

    def test_contracted_operations_must_declare_a_timeout(self):
        for authority in (mc.Authority(kind="node-provider"),
                          mc.Authority(kind="browser-local", exception_reason="recorded debt")):
            operation = mc.Operation(id="run", method="POST", route="/api/uq/run", authority=authority,
                                     output=mc.OutputSchema(fields=("samples",)))
            with self.subTest(kind=authority.kind), self.assertRaises(mc.ContractError):
                _contract(operations=(operation,))
        timed = mc.Operation(id="run", method="POST", route="/api/uq/run",
                             authority=mc.Authority(kind="node-provider", timeout_ms=12000),
                             output=mc.OutputSchema(fields=("samples",)))
        self.assertEqual(_contract(operations=(timed,)).operations[0].authority.timeout_ms, 12000)

    def test_legacy_notes_are_unique_text(self):
        with self.assertRaises(mc.ContractError):
            _contract(legacy_notes=("same", "same"))
        with self.assertRaises(mc.ContractError):
            _contract(legacy_notes=(" ",))

    def test_route_must_be_api(self):
        with self.assertRaises(mc.ContractError):
            mc.Operation(id="run", method="POST", route="uq/run", authority=mc.Authority(kind="node-provider", timeout_ms=1),
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
        present = mc.TestRefs(schema="python/test_contract_uq_lab.py", docs="docs/modules/uq-lab.md",
                              oracle=mc.Oracle(status="present", ref="python/test_uq_oracle.py", scope="Checks x."))
        self.assertEqual(_contract(evidence=strong, tests=present).evidence.ceiling, "calibrated-simulation")

    def test_present_oracle_requires_reference(self):
        with self.assertRaises(mc.ContractError):
            mc.Oracle(status="present")
        with self.assertRaises(mc.ContractError):  # and a user-facing scope sentence
            mc.Oracle(status="present", ref="python/x.py")
        with self.assertRaises(mc.ContractError):
            mc.Oracle(status="pending", scope="Checks x.")


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
        for person in ("Jane Doe", "jane@example.com", "evidence workspace"):
            with self.subTest(owner=person), self.assertRaises(mc.ContractError):
                _contract(owner=person)
        self.assertEqual(_contract(owner="team:evidence").owner, "team:evidence")
        with self.assertRaises(mc.ContractError):
            _contract(seed_derived=("label", "label"))
        with self.assertRaises(mc.ContractError):
            _contract(seed_derived=("owner",))
        with self.assertRaises(mc.ContractError):
            _contract(operations=())
        with self.assertRaises(mc.ContractError):
            _contract(evidence=_evidence(emits=()))
        with self.assertRaises(mc.ContractError):
            _contract(source_refs=())
        with self.assertRaises(mc.ContractError):
            _contract(tests=mc.TestRefs(schema="python/test_contract_uq_lab.py"))

    def test_status_like_fields_need_a_status_key_or_transport_values(self):
        # With statusKey None, a field that reads like a status must be declared transport-only.
        for key in ("status", "evidenceStatus", "evidence_status", "runStatus", "qualificationStatus", "evidenceLevel"):
            with self.subTest(key=key), self.assertRaises(mc.ContractError):
                mc.OutputSchema(fields=("value", key), status_key=None)
        ok = mc.OutputSchema(fields=("value", "status"), status_key=None, transport_values=(("status", ("success",)),))
        self.assertEqual(ok.to_dict()["transportValues"], {"status": ["success"]})
        for values in (("screening-only",), ("unvalidated",), ("qualified",), ()):
            with self.subTest(values=values), self.assertRaises(mc.ContractError):
                mc.OutputSchema(fields=("value", "status"), status_key=None, transport_values=(("status", values),))
        with self.assertRaises(mc.ContractError):  # transport key must be an output field
            mc.OutputSchema(fields=("value",), status_key=None, transport_values=(("status", ("success",)),))
        with self.assertRaises(mc.ContractError):  # the status key itself is not a transport field
            mc.OutputSchema(fields=("value",), status_key="status", transport_values=(("status", ("success",)),))
        with self.assertRaises(mc.ContractError):  # a second status-like field next to the status key
            mc.OutputSchema(fields=("value", "runStatus"))
        self.assertEqual(mc.OutputSchema(fields=("value", "success")).status_key, "evidenceStatus")

    def test_emits_follow_the_output_status_key(self):
        # An output without a status key emits nothing; declaring emits then is a false claim.
        silent = mc.Operation(id="run", method="POST", route="/api/uq/run",
                              authority=mc.Authority(kind="python-ipc", script="uq_lab.py", timeout_ms=1),
                              output=mc.OutputSchema(fields=("samples",), status_key=None))
        with self.assertRaises(mc.ContractError):
            _contract(operations=(silent,))
        with self.assertRaises(mc.ContractError):
            _contract(operations=(silent,), evidence=_evidence(emits=()))  # needs an explanatory note
        quiet = _contract(operations=(silent,), evidence=_evidence(emits=(), note="no status key"))
        self.assertEqual(quiet.evidence.emits, ())
        self.assertIsNone(silent.to_dict()["output"]["statusKey"])


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
        for contract in (c for c in self.registry if c.migration_state == "legacy"):
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
        for contract in (c for c in self.registry if c.migration_state == "legacy"):
            self.assertEqual(contract.source_refs, ())
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

    def test_every_contract_round_trips_through_the_generated_json(self):
        document = json.loads((REPO_ROOT / "src" / "generated" / "moduleRegistry.json").read_text(encoding="utf-8"))
        rebuilt = tuple(mc.contract_from_dict(entry) for entry in document["contracts"])
        self.assertEqual(rebuilt, self.registry)


class ContractedRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = mr.build_registry()
        cls.contracted = {c.id: c for c in cls.registry if c.migration_state == "contracted"}

    def test_pilots_are_the_only_contracted_modules(self):
        self.assertEqual(tuple(self.contracted), CONTRACTED)
        self.assertEqual(set(mr.CONTRACTED_BUILDERS), set(CONTRACTED))
        self.assertFalse(set(mr.LEGACY_OPERATIONS) & set(CONTRACTED))

    def test_every_reference_of_every_contracted_module_exists(self):
        generated = {mr.REPO_ROOT / mr.module_doc_path(module_id) for module_id in CONTRACTED}
        self.assertTrue(all(path.is_file() for path in generated), "run the emitter")
        for contract in self.contracted.values():
            refs = mr.contract_refs(contract)
            for ref in refs:
                with self.subTest(module=contract.id, ref=ref):
                    self.assertEqual(mr.ref_problem(ref), "")
            self.assertIn(contract.tests.schema, refs)
            self.assertIn(contract.tests.docs, refs)

    def test_contracted_module_with_a_missing_ref_fails(self):
        for missing in ("python/does_not_exist.py", "python/stochastic_uq_mmpds_solver.py:999999",
                        "python/test_keyhole_contract.py::KeyholeContract.test_not_there", "../outside.py"):
            def broken(row, missing=missing):
                contract = mr.CONTRACTED_BUILDERS[row["id"]](row)
                return dataclasses.replace(contract, source_refs=contract.source_refs + (missing,))
            builders = dict(mr.CONTRACTED_BUILDERS, **{"uq-lab": broken})
            with self.subTest(ref=missing), self.assertRaisesRegex(ValueError, "uq-lab: unresolved references"):
                mr.build_registry(builders=builders)
        # The oracle reference is checked too.
        def bad_oracle(row):
            contract = mr.CONTRACTED_BUILDERS[row["id"]](row)
            oracle = dataclasses.replace(contract.tests.oracle, ref="python/nope.py::T.t")
            tests = dataclasses.replace(contract.tests, oracle=oracle)
            return dataclasses.replace(contract, tests=tests)
        with self.assertRaisesRegex(ValueError, "keyhole-raytracing: unresolved references"):
            mr.build_registry(builders=dict(mr.CONTRACTED_BUILDERS, **{"keyhole-raytracing": bad_oracle}))

    def test_pilot_evidence_is_bounded(self):
        for contract in self.contracted.values():
            with self.subTest(module=contract.id):
                evidence = contract.evidence
                # Neither authority output carries an evidence status, so nothing is emitted.
                self.assertTrue(all(op.output.status_key is None for op in contract.operations))
                self.assertEqual(evidence.emits, ())
                self.assertEqual(evidence.ceiling, "screening-only")
                self.assertEqual(evidence.forbidden_claims, mc.FORBIDDEN_CLAIM_KEYS)
                self.assertIsNone(contract.validity_domain)
                self.assertNotIn(mc.TODO_MARKER, evidence.note)
        keyhole = self.contracted["keyhole-raytracing"].tests.oracle
        self.assertEqual(keyhole.status, "present")
        self.assertTrue(keyhole.ref.startswith("python/test_keyhole_contract.py::"))
        self.assertEqual(self.contracted["uq-lab"].tests.oracle.status, "pending")

    def test_oracle_ci_gap_is_recorded_exactly_when_the_oracle_cannot_run_in_ci(self):
        for contract in self.contracted.values():
            oracle = contract.tests.oracle
            if oracle.status != "present":
                self.assertIsNone(oracle.ci_note, contract.id)
                continue
            missing = mr.oracle_ci_missing_packages(oracle.ref)
            with self.subTest(module=contract.id, missing=missing):
                if missing:
                    self.assertTrue(oracle.ci_note, "a present oracle outside the CI lock must record the gap")
                    self.assertIn("not run in CI", oracle.ci_note)
                    for package in missing:
                        self.assertIn(package.lower(), oracle.ci_note.lower())
                    self.assertIn(oracle.ci_note, contract.evidence.note)
                else:
                    self.assertIsNone(oracle.ci_note, "no gap to record")
        self.assertEqual(mr.oracle_ci_missing_packages(self.contracted["keyhole-raytracing"].tests.oracle.ref), ["warp"])

    def test_a_present_oracle_without_a_ci_gap_note_is_listed_in_the_ci_workflow(self):
        # Micrograph review S2: "no CI gap" must mean the oracle module really runs in CI, not only that its
        # packages are in the CI lock. The generated module page derives its "Oracle in CI" line from the same check.
        for contract in self.contracted.values():
            oracle = contract.tests.oracle
            if oracle.status == "present" and not oracle.ci_note:
                with self.subTest(module=contract.id):
                    self.assertTrue(mr.oracle_listed_in_ci(oracle.ref), mr.oracle_ci_module(oracle.ref))
                    self.assertTrue(mr.oracle_listed_in_ci(contract.tests.schema), contract.tests.schema)
        self.assertFalse(mr.oracle_listed_in_ci("python/test_not_a_module.py::T.t"))

    def test_ci_note_must_be_echoed_in_the_evidence_note(self):
        base = mr.CONTRACTED_BUILDERS["keyhole-raytracing"]
        row = next(r for r in mr.load_seed() if r["id"] == "keyhole-raytracing")
        contract = base(row)
        with self.assertRaisesRegex(mc.ContractError, "oracle CI gap"):
            dataclasses.replace(contract, evidence=dataclasses.replace(contract.evidence, note="silent"))
        with self.assertRaises(mc.ContractError):
            mc.Oracle(status="pending", ci_note="not run")

    def test_contracted_modules_claim_no_owner_and_mark_seed_text(self):
        seed = {row["id"]: row for row in mr.load_seed()}
        for contract in self.contracted.values():
            with self.subTest(module=contract.id):
                self.assertEqual(contract.owner, mc.OWNER_UNASSIGNED, "no person/team owner is claimed")
                row = seed[contract.id]
                original = {"label": row["label"], "description": row["description"], "next": row["next"],
                            "maturity": row["scope"]}
                for name in mc.SEED_TEXT_FIELDS:
                    if name in contract.seed_derived:
                        self.assertEqual(getattr(contract, name), original[name], f"{name} marked seed-derived")
                    else:
                        self.assertNotEqual(getattr(contract, name), original[name], f"{name} claimed rewritten")
        keyhole = self.contracted["keyhole-raytracing"]
        self.assertNotIn("description", keyhole.seed_derived)
        self.assertNotIn("GPU-accelerated", keyhole.description)
        self.assertIn("CPU by default, CUDA optional", keyhole.description)
        self.assertEqual(self.contracted["uq-lab"].seed_derived, mc.SEED_TEXT_FIELDS)
        for contract in self.registry:
            if contract.migration_state == "legacy":
                self.assertEqual(contract.seed_derived, mc.SEED_TEXT_FIELDS, contract.id)

    def test_pilot_units_and_wording_are_consistent(self):
        # One symbol per unit: µm (not um/micron), degC (not °C) for temperatures with an offset.
        units = {f.unit for c in self.contracted.values() for op in c.operations for f in op.input if f.unit}
        self.assertLessEqual(units, {"1", "m", "W", "µm", "K/s", "degC", "K", "h", "MPa", "%",
                                     # Phase 7 wave 2
                                     "1/s", "mm/s", "mm/s^2", "µs", "W/(m*K)", "m^2/s",
                                     # micrograph rework (image pixels and image scale)
                                     "px", "µm/px"})
        texts = [f.note or "" for c in self.contracted.values() for op in c.operations for f in op.input]
        texts += [n for c in self.contracted.values() for n in c.legacy_notes]
        texts += [c.evidence.note for c in self.contracted.values()]
        for text in texts:
            with self.subTest(text=text[:40]):
                self.assertNotRegex(text, r"\d\s?um\b|°C|micron")
                self.assertNotIn("The oracle is numerical", text)
        mc_samples = next(f for f in self.contracted["uq-lab"].operations[0].input if f.key == "mcSamples")
        self.assertIn("declares [500, 10000]", mc_samples.note)
        self.assertTrue(any(n.startswith("warm: true is the best case") for n in self.contracted["uq-lab"].legacy_notes))

    def test_pilot_authorities_match_the_legacy_binding(self):
        keyhole = self.contracted["keyhole-raytracing"].operations[0]
        self.assertEqual((keyhole.method, keyhole.route, keyhole.authority.worker_method, keyhole.authority.timeout_ms),
                         ("POST", "/api/python/lpbf-keyhole-raytracing", "keyhole-raytracing", 20000))
        uq = self.contracted["uq-lab"].operations[0]
        self.assertEqual((uq.method, uq.route, uq.authority.script, uq.authority.timeout_ms, uq.authority.warm),
                         ("POST", "/api/python/stochastic-uq-mmpds", "python/stochastic_uq_mmpds_solver.py", 25000, True))

    def test_wave2_authorities_match_the_legacy_binding(self):
        # Same operation id, route, authority and deadline the legacy contracts recorded (slice 1).
        worker = ("lpbf-worker", 20000, False)
        expected = {
            "toolpath-studio": ("toolpath-kinematics", "/api/python/lpbf-toolpath-kinematics", "toolpath-kinematics") + worker,
            "murakami-fatigue": ("fatigue-fracture", "/api/python/lpbf-fatigue-fracture", "fatigue-fracture") + worker,
            "adaptive-mitigation": ("adaptive-feedforward", "/api/python/lpbf-adaptive-feedforward",
                                    "adaptive-feedforward") + worker,
            "ttt-cct-kinetics": ("kinetics-ttt-cct", "/api/python/kinetics-ttt-cct",
                                 "python/kinetics_ttt_cct_solver.py", "python-ipc", 25000, True),
            "icme-motor": ("icme-multiscale-pipeline", "/api/python/icme-multiscale-pipeline",
                           "python/icme_multiscale_pipeline_solver.py", "python-ipc", 25000, True),
        }
        for module_id, values in expected.items():
            (operation,) = self.contracted[module_id].operations
            a = operation.authority
            with self.subTest(module=module_id):
                self.assertEqual((operation.id, operation.route, a.script or a.worker_method, a.kind, a.timeout_ms,
                                  a.warm), values)
                self.assertEqual((operation.method, a.gpu), ("POST", "none"))
                self.assertEqual(self.contracted[module_id].tests.oracle.status, "pending")
                self.assertEqual(self.contracted[module_id].seed_derived, mc.SEED_TEXT_FIELDS,
                                 "wave 2 does not rewrite identity text")
                # The cited inventory row names the route that is actually served.
                (row_ref,) = [r for r in self.contracted[module_id].source_refs
                              if r.startswith("docs/MODULE_EVIDENCE_INVENTORY.md:")]
                line = int(row_ref.split(":")[1].split("#")[0])
                inventory = (REPO_ROOT / "docs" / "MODULE_EVIDENCE_INVENTORY.md").read_text(encoding="utf-8")
                self.assertIn(f"`{operation.route}`", inventory.splitlines()[line - 1])

    def test_eager_core_slice_carries_only_navigation_and_badge_data(self):
        core = mr.core_document(mr.registry_document(self.registry))
        allowed = set(mr.CORE_CONTRACT_KEYS) | {"evidence", "tests"}
        for entry in core["contracts"]:
            self.assertEqual(set(entry), allowed)
            self.assertEqual(set(entry["evidence"]), {"ceiling"})
            self.assertEqual(set(entry["tests"]), {"oracle"})
            self.assertEqual(set(entry["tests"]["oracle"]), {"status", "ciNote", "scope"})
        self.assertIn(mr.GENERATED_CORE_TS, mr.rendered_outputs())

    def test_ref_forms(self):
        self.assertEqual(mr.ref_problem("python/module_registry.py"), "")
        self.assertIn("does not exist", mr.ref_problem("/etc/passwd"))
        generated = frozenset({"docs/modules/not-yet.md"})
        self.assertEqual(mr.ref_problem("docs/modules/not-yet.md", generated=generated), "")
        # Line references must carry the text they expect, so shifted lines fail.
        self.assertIn("needs '#", mr.ref_problem("python/module_registry.py:1-2"))
        self.assertEqual(mr.ref_problem('python/module_registry.py:1-2#"""Module registry'), "")
        self.assertIn("no longer contains", mr.ref_problem("python/module_registry.py:3-4#Module registry"))
        self.assertIn("outside", mr.ref_problem("python/module_registry.py:2-1#x"))
        # Python symbols via the AST; Class.method needs the method inside that class.
        self.assertEqual(mr.ref_problem("python/module_registry.py::build_registry"), "")
        self.assertEqual(mr.ref_problem("python/module_registry.py::CORE_CONTRACT_KEYS"), "")
        self.assertIn("not defined", mr.ref_problem("python/module_registry.py::nowhere"))
        oracle = "python/test_keyhole_contract.py::KeyholeContract.test_flat_surface_absorbs_normal_incidence_fraction"
        self.assertEqual(mr.ref_problem(oracle), "")
        self.assertIn("has no method", mr.ref_problem("python/test_keyhole_contract.py::KeyholeContract.run_casex"))
        self.assertIn("not a class", mr.ref_problem("python/module_contract.py::within_ceiling.x"))
        # A method of another class does not satisfy Class.method.
        self.assertIn("has no method", mr.ref_problem("python/module_contract.py::Oracle.input_problems"))
        # TS/TSX declarations; a call site is not a declaration.
        self.assertEqual(mr.ref_problem("src/services/pythonComputationService.ts::calculateStochasticUQMMPDS"), "")
        self.assertIn("not declared", mr.ref_problem("src/components/UQLab.tsx::calculateStochasticUQMMPDS"))

    def test_symbol_refs_survive_line_deletions_elsewhere(self):
        # orch/dead-surface deletes these line ranges of pythonComputationService.ts; the uq-lab
        # reference is anchored on the symbol, so it must still resolve afterwards.
        import tempfile
        rel = "src/services/pythonComputationService.ts"
        lines = (REPO_ROOT / rel).read_text(encoding="utf-8").splitlines(keepends=True)
        removed = set()
        for start, end in ((207, 236), (1276, 1356), (1819, 1876)):
            removed.update(range(start, end + 1))
        kept = "".join(line for number, line in enumerate(lines, 1) if number not in removed)
        ref = next(r for r in mr.build_registry() if r.id == "uq-lab").source_refs
        ref = next(r for r in ref if r.startswith(rel))
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / rel
            target.parent.mkdir(parents=True)
            target.write_text(kept, encoding="utf-8")
            self.assertEqual(mr.ref_problem(ref, root=Path(root)), "")
            self.assertIn("::", ref)

    def test_top_level_imports_walk_every_try_branch_including_finalbody(self):
        import tempfile
        lines = ["try:", "    import alpha", "except ImportError:", "    import beta", "else:", "    import gamma",
                 "finally:", "    import delta", "if True:", "    import epsilon", ""]
        with tempfile.TemporaryDirectory() as root:
            fixture = Path(root) / "scratch_imports.py"
            fixture.write_text(chr(10).join(lines), encoding="utf-8")
            self.assertEqual(mr._top_level_imports(fixture), {"alpha", "beta", "gamma", "delta", "epsilon"})


if __name__ == "__main__":
    unittest.main()
