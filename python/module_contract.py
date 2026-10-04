"""Module contract schema (Phase 7 step 0 skeleton).

Stdlib-only frozen dataclasses that describe one product module: identity,
maturity, navigation, operations and their authority, canonical input fields,
validity domain, evidence ceiling, lifecycle, test references and migration
state. See .orchestra/DESIGN-7-module-sdk.md (section 1).

Every vocabulary below is closed. Validation happens in ``__post_init__`` so an
invalid contract cannot be constructed. The contract never computes or upgrades
an evidence status; it only bounds what a module may report.

Items marked TODO(maintainer-review) are skeleton defaults, not reviewed facts.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Optional, Tuple, Union

# --- Closed vocabularies ---------------------------------------------------

# Mirrors EVIDENCE_TYPES in src/types/research.ts (order preserved).
# TODO(maintainer-review): reusing the research.ts source-classification enum
# as the run-output status vocabulary is unreviewed
# (.orchestra/REVIEW-prep-opus-python.md, maintainer item 2).
# TODO(maintainer-review): "unresolved" is both an evidence type here and,
# semantically, close to a run state (no claim); the double meaning is
# unreviewed (.orchestra/REVIEW-prep-opus-python.md, maintainer item 8).
EVIDENCE_TYPES: Tuple[str, ...] = (
    "measured",
    "validated-simulation",
    "calibrated-simulation",
    "literature-estimate",
    "screening-only",
    "unresolved",
)
# Run states describe why a result carries no evidence claim. They never
# exceed any ceiling and are always allowed in ``emits``.
RUN_STATES: Tuple[str, ...] = (
    "unvalidated",
    "inconclusive",
    "unavailable",
    "outside-validity-domain",
)
EVIDENCE_STATUSES: Tuple[str, ...] = EVIDENCE_TYPES + RUN_STATES

# TODO(maintainer-review): strength order used only for ceiling comparison.
# Lower index = stronger claim. The relative position of literature-estimate
# and screening-only is a skeleton assumption pending review
# (.orchestra/REVIEW-prep-opus-python.md, maintainer item 1).
EVIDENCE_RANK = {status: index for index, status in enumerate(EVIDENCE_TYPES)}

# Ceiling cap applied while a module's oracle test is pending (design 1).
# TODO(maintainer-review): this cap also blocks literature-estimate (e.g. DB
# lookups) until an oracle exists (.orchestra/REVIEW-prep-opus-python.md,
# maintainer item 3).
PENDING_ORACLE_CEILING = "screening-only"

# Claim keys a module output must never set truthy unless allowed (design 1).
# TODO(maintainer-review): exact, case-sensitive, top-level closed list;
# synonyms (isQualified, certifiable, flightReady, approved, compliant) are not
# covered and a field named "measured" is barred even at a measured ceiling
# (.orchestra/REVIEW-prep-opus-python.md, maintainer item 5).
FORBIDDEN_CLAIM_KEYS: Tuple[str, ...] = (
    "qualified",
    "certified",
    "validated",
    "measured",
    "productionReady",
    "airworthy",
)
# TODO(maintainer-review): claims forbidden for every module while maturity
# is barred from Production (roadmap G03). Hard-coded until G03
# (.orchestra/REVIEW-prep-opus-python.md, maintainer item 6).
ALWAYS_FORBIDDEN_CLAIMS: Tuple[str, ...] = ("qualified", "certified", "productionReady", "airworthy")

MATURITY = ("Research", "Preview")  # Production barred until roadmap G03.
NAVIGATION = ("listed", "hidden")
WORKSPACES = ("lpbf", "materials", "evidence", "orchestration")
AUTHORITY_KINDS = ("python-ipc", "lpbf-worker", "browser-local", "node-provider")
GPU_MODES = ("none", "optional", "required")
BACKGROUND_WORK = ("none", "pausable", "server-job")
LIFECYCLE_RESOURCES = ("raf", "interval", "three", "fetch")
ORACLE_STATES = ("present", "pending")
MIGRATION_STATES = ("legacy", "contracted")

TODO_MARKER = "TODO(maintainer-review)"

_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_MODULE_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

Scalar = Union[float, int, str, bool]


class ContractError(ValueError):
    """Raised when a contract violates the schema."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _one_of(value: str, allowed: Tuple[str, ...], name: str) -> None:
    _require(value in allowed, f"{name} must be one of {allowed}, got {value!r}")


def _text(value: Any, name: str) -> None:
    _require(isinstance(value, str) and value.strip() != "", f"{name} must be a non-empty string")


def _finite(value: Any, name: str) -> None:
    _require(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value),
             f"{name} must be a finite number")


def _unique(values: Tuple[Any, ...], name: str) -> None:
    _require(len(set(values)) == len(values), f"{name} must not contain duplicates")


def evidence_rank(status: str) -> Optional[int]:
    """Rank of an evidence type, or None for run states (no claim)."""
    return EVIDENCE_RANK.get(status)


def within_ceiling(status: str, ceiling: str) -> bool:
    """True when ``status`` does not claim more than ``ceiling``."""
    _one_of(status, EVIDENCE_STATUSES, "status")
    _one_of(ceiling, EVIDENCE_TYPES, "ceiling")
    rank = evidence_rank(status)
    return rank is None or rank >= EVIDENCE_RANK[ceiling]


# --- Building blocks -------------------------------------------------------

@dataclass(frozen=True)
class InputField:
    key: str
    label: str
    unit: str  # canonical unit sent to the authority
    quantity_kind: str
    min: float
    max: float
    default: Scalar
    required: bool = True
    step: Optional[float] = None
    display_units: Tuple[str, ...] = ()
    enum: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require(isinstance(self.key, str) and bool(_KEY.match(self.key)), f"invalid field key {self.key!r}")
        _text(self.label, f"{self.key}.label")
        _text(self.unit, f"{self.key}.unit")
        _text(self.quantity_kind, f"{self.key}.quantityKind")
        _finite(self.min, f"{self.key}.min")
        _finite(self.max, f"{self.key}.max")
        _require(self.min <= self.max, f"{self.key}: min must not exceed max")
        if self.step is not None:
            _finite(self.step, f"{self.key}.step")
            _require(self.step > 0, f"{self.key}.step must be positive")
        _unique(self.display_units, f"{self.key}.displayUnits")
        if self.enum:
            _unique(self.enum, f"{self.key}.enum")
            _require(self.default in self.enum, f"{self.key}: default must be one of enum")
        else:
            _finite(self.default, f"{self.key}.default")
            _require(self.min <= self.default <= self.max, f"{self.key}: default outside hard range")

    def to_dict(self) -> dict:
        return {
            "key": self.key, "label": self.label, "unit": self.unit,
            "displayUnits": list(self.display_units), "quantityKind": self.quantity_kind,
            "min": self.min, "max": self.max, "step": self.step, "default": self.default,
            "required": self.required, "enum": list(self.enum),
        }


@dataclass(frozen=True)
class Authority:
    kind: str
    # None means the code declares no timeout for this authority (browser-local,
    # node-provider). python-ipc and lpbf-worker always run under a deadline.
    timeout_ms: Optional[int] = None
    gpu: str = "none"
    warm: bool = False
    script: Optional[str] = None
    worker_method: Optional[str] = None
    exception_reason: Optional[str] = None

    def __post_init__(self) -> None:
        _one_of(self.kind, AUTHORITY_KINDS, "authority.kind")
        _one_of(self.gpu, GPU_MODES, "authority.gpu")
        if self.timeout_ms is not None or self.kind in ("python-ipc", "lpbf-worker"):
            _require(isinstance(self.timeout_ms, int) and not isinstance(self.timeout_ms, bool)
                     and self.timeout_ms > 0, "authority.timeoutMs must be a positive integer")
        _require(isinstance(self.warm, bool), "authority.warm must be a boolean")
        if self.warm:
            # Only the persistent Python IPC service keeps modules warm.
            _require(self.kind == "python-ipc", "authority.warm applies only to python-ipc")
        if self.kind == "python-ipc":
            _text(self.script, "authority.script")
        if self.kind == "lpbf-worker":
            _text(self.worker_method, "authority.workerMethod")
        if self.kind == "browser-local":
            # Recorded debt against the single-authority rule (design 1).
            _text(self.exception_reason, "authority.exceptionReason")

    def to_dict(self) -> dict:
        return {
            "kind": self.kind, "script": self.script, "workerMethod": self.worker_method,
            "timeoutMs": self.timeout_ms, "gpu": self.gpu, "warm": self.warm,
            "exceptionReason": self.exception_reason,
        }


@dataclass(frozen=True)
class OutputSchema:
    fields: Tuple[str, ...]
    status_key: str = "evidenceStatus"

    def __post_init__(self) -> None:
        _require(len(self.fields) > 0, "output.fields must not be empty")
        _unique(self.fields, "output.fields")
        for key in self.fields:
            _require(key not in FORBIDDEN_CLAIM_KEYS, f"output field {key!r} is a forbidden claim key")
        _text(self.status_key, "output.statusKey")
        # The status key is reserved by the same claim names as the fields.
        _require(self.status_key not in FORBIDDEN_CLAIM_KEYS,
                 f"output.statusKey {self.status_key!r} is a forbidden claim key")
        _require(self.status_key not in self.fields,
                 f"output.statusKey {self.status_key!r} collides with an output field")

    def to_dict(self) -> dict:
        return {"fields": list(self.fields), "statusKey": self.status_key}


@dataclass(frozen=True)
class Operation:
    id: str
    # None only for browser-local operations, which have no server route.
    route: Optional[str]
    authority: Authority
    input: Tuple[InputField, ...] = ()
    # None = output schema not yet declared (legacy contracts only; see ModuleContract).
    output: Optional[OutputSchema] = None

    def __post_init__(self) -> None:
        _require(isinstance(self.id, str) and bool(_MODULE_ID.match(self.id)), f"invalid operation id {self.id!r}")
        if self.route is None:
            _require(self.authority.kind == "browser-local", f"{self.id}: only browser-local operations may omit a route")
        else:
            _require(isinstance(self.route, str) and self.route.startswith("/api/"), "operation.route must start with /api/")
        _unique(tuple(f.key for f in self.input), f"{self.id}.input keys")

    def to_dict(self) -> dict:
        return {
            "id": self.id, "route": self.route, "authority": self.authority.to_dict(),
            "input": [f.to_dict() for f in self.input],
            "output": self.output.to_dict() if self.output else None,
        }


@dataclass(frozen=True)
class FieldRange:
    key: str
    min: float
    max: float
    unit: str

    def __post_init__(self) -> None:
        _require(isinstance(self.key, str) and bool(_KEY.match(self.key)), f"invalid range key {self.key!r}")
        _finite(self.min, f"validity.{self.key}.min")
        _finite(self.max, f"validity.{self.key}.max")
        _require(self.min <= self.max, f"validity.{self.key}: min must not exceed max")
        _text(self.unit, f"validity.{self.key}.unit")

    def to_dict(self) -> dict:
        return {"key": self.key, "min": self.min, "max": self.max, "unit": self.unit}


@dataclass(frozen=True)
class ValidityDomain:
    """Outside the domain a result is downgraded, never rejected (design 1)."""
    ranges: Tuple[FieldRange, ...]
    source_refs: Tuple[str, ...]
    materials: Tuple[str, ...] = ()
    regime_notes: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _unique(tuple(r.key for r in self.ranges), "validity.ranges keys")
        # A validity domain must come from sources and never be invented.
        _require(len(self.source_refs) > 0, "validity.sourceRefs must not be empty")

    def to_dict(self) -> dict:
        return {
            "ranges": [r.to_dict() for r in self.ranges], "materials": list(self.materials),
            "regimeNotes": list(self.regime_notes), "sourceRefs": list(self.source_refs),
        }


@dataclass(frozen=True)
class Oracle:
    status: str = "pending"
    ref: Optional[str] = None

    def __post_init__(self) -> None:
        _one_of(self.status, ORACLE_STATES, "oracle.status")
        if self.status == "present":
            _text(self.ref, "oracle.ref")

    def to_dict(self) -> dict:
        return {"status": self.status, "ref": self.ref}


@dataclass(frozen=True)
class TestRefs:
    oracle: Oracle = field(default_factory=Oracle)
    schema: Optional[str] = None
    docs: Optional[str] = None

    def to_dict(self) -> dict:
        return {"schema": self.schema, "oracle": self.oracle.to_dict(), "docs": self.docs}


@dataclass(frozen=True)
class Evidence:
    emits: Tuple[str, ...]
    ceiling: str
    forbidden_claims: Tuple[str, ...]
    note: Optional[str] = None

    def __post_init__(self) -> None:
        _one_of(self.ceiling, EVIDENCE_TYPES, "evidence.ceiling")
        _unique(self.emits, "evidence.emits")
        for status in self.emits:
            _one_of(status, EVIDENCE_STATUSES, "evidence.emits")
            _require(within_ceiling(status, self.ceiling),
                     f"evidence.emits {status!r} exceeds ceiling {self.ceiling!r}")
        _unique(self.forbidden_claims, "evidence.forbiddenClaims")
        for claim in self.forbidden_claims:
            _one_of(claim, FORBIDDEN_CLAIM_KEYS, "evidence.forbiddenClaims")
        for claim in ALWAYS_FORBIDDEN_CLAIMS:
            _require(claim in self.forbidden_claims, f"evidence.forbiddenClaims must include {claim!r}")
        if self.ceiling != "measured":
            _require("measured" in self.forbidden_claims,
                     "'measured' must be forbidden unless the ceiling is measured")
        # TODO(maintainer-review): allowing "validated" at a validated-simulation
        # ceiling mixes numerical verification with experimental validation
        # (.orchestra/REVIEW-prep-opus-python.md, maintainer item 4).
        if self.ceiling not in ("measured", "validated-simulation"):
            _require("validated" in self.forbidden_claims,
                     "'validated' must be forbidden below a validated ceiling")

    def to_dict(self) -> dict:
        return {"emits": list(self.emits), "ceiling": self.ceiling,
                "forbiddenClaims": list(self.forbidden_claims), "note": self.note}


@dataclass(frozen=True)
class Lifecycle:
    background_work: str
    resources: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _one_of(self.background_work, BACKGROUND_WORK, "lifecycle.backgroundWork")
        _unique(self.resources, "lifecycle.resources")
        for resource in self.resources:
            _one_of(resource, LIFECYCLE_RESOURCES, "lifecycle.resources")

    def to_dict(self) -> dict:
        return {"backgroundWork": self.background_work, "resources": list(self.resources)}


@dataclass(frozen=True)
class View:
    component: str  # path under src/components/
    export: str

    def __post_init__(self) -> None:
        _require(isinstance(self.component, str) and self.component.startswith("src/components/")
                 and self.component.endswith(".tsx"), f"view.component must be src/components/*.tsx, got {self.component!r}")
        _require(isinstance(self.export, str) and bool(_KEY.match(self.export)), "view.export must be an identifier")

    def to_dict(self) -> dict:
        return {"component": self.component, "export": self.export}


# --- Module contract ---------------------------------------------------------

@dataclass(frozen=True)
class ModuleContract:
    id: str
    version: str
    owner: str
    workspace: str
    label: str
    description: str
    next: str
    maturity: str
    navigation: str
    view: View
    evidence: Evidence
    tests: TestRefs
    migration_state: str
    operations: Tuple[Operation, ...] = ()
    hidden_reason: Optional[str] = None
    validity_domain: Optional[ValidityDomain] = None
    lifecycle: Optional[Lifecycle] = None
    # Recorded facts about missing or non-authoritative behaviour (e.g. a route the
    # view calls that no server handles). Notes never raise a claim.
    legacy_notes: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require(isinstance(self.id, str) and bool(_MODULE_ID.match(self.id)), f"invalid module id {self.id!r}")
        _require(isinstance(self.version, str) and bool(_SEMVER.match(self.version)), f"{self.id}: version must be semver")
        _text(self.owner, f"{self.id}.owner")
        _one_of(self.workspace, WORKSPACES, f"{self.id}.workspace")
        _text(self.label, f"{self.id}.label")
        _text(self.description, f"{self.id}.description")
        _require(isinstance(self.next, str) and bool(_MODULE_ID.match(self.next)), f"{self.id}: invalid next")
        _one_of(self.maturity, MATURITY, f"{self.id}.maturity")
        _one_of(self.navigation, NAVIGATION, f"{self.id}.navigation")
        if self.navigation == "hidden":
            _text(self.hidden_reason, f"{self.id}.hiddenReason")
        else:
            _require(self.hidden_reason is None, f"{self.id}: hiddenReason only applies to hidden modules")
        _one_of(self.migration_state, MIGRATION_STATES, f"{self.id}.migrationState")
        _unique(tuple(op.id for op in self.operations), f"{self.id}.operations ids")
        _unique(self.legacy_notes, f"{self.id}.legacyNotes")
        for note in self.legacy_notes:
            _text(note, f"{self.id}.legacyNotes")
        if self.tests.oracle.status == "pending":
            _require(EVIDENCE_RANK[self.evidence.ceiling] >= EVIDENCE_RANK[PENDING_ORACLE_CEILING],
                     f"{self.id}: a pending oracle caps the ceiling at {PENDING_ORACLE_CEILING!r}")
        if self.migration_state == "contracted":
            _require(len(self.operations) > 0, f"{self.id}: contracted modules need operations")
            _require(all(op.output is not None for op in self.operations),
                     f"{self.id}: contracted operations must declare an output schema")
            _require(len(self.evidence.emits) > 0, f"{self.id}: contracted modules must declare emits")
            _require(self.lifecycle is not None, f"{self.id}: contracted modules need a lifecycle")
            _text(self.tests.schema, f"{self.id}.tests.schema")
            _require(TODO_MARKER not in self.owner, f"{self.id}: contracted modules need a reviewed owner")

    def to_dict(self) -> dict:
        return {
            "id": self.id, "version": self.version, "owner": self.owner,
            "workspace": self.workspace, "label": self.label, "description": self.description,
            "next": self.next, "maturity": self.maturity, "navigation": self.navigation,
            "hiddenReason": self.hidden_reason, "view": self.view.to_dict(),
            "operations": [op.to_dict() for op in self.operations],
            "validityDomain": self.validity_domain.to_dict() if self.validity_domain else None,
            "evidence": self.evidence.to_dict(),
            "lifecycle": self.lifecycle.to_dict() if self.lifecycle else None,
            "tests": self.tests.to_dict(), "migrationState": self.migration_state,
            "legacyNotes": list(self.legacy_notes),
        }


if __name__ == "__main__":
    # `python -m module_contract emit [--check] [--refresh-seed]` (run from python/)
    # delegates to the registry emitter; scripts/emit-module-registry.py is equivalent.
    import sys

    from module_registry import main as _registry_main

    _args = sys.argv[1:]
    if not _args or _args[0] != "emit":
        print("usage: python -m module_contract emit [--check] [--refresh-seed]", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(_registry_main(_args[1:]))
