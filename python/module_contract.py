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
HTTP_METHODS = ("GET", "POST", "PUT", "DELETE", "PATCH")
# Field value types. number/integer carry a canonical unit; boolean/enum carry none.
VALUE_TYPES = ("number", "integer", "boolean", "enum")

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

def _is_integer(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and float(value).is_integer())


@dataclass(frozen=True)
class InputField:
    """One request key of an operation, in the canonical unit the authority expects.

    ``min``/``max`` are hard bounds (outside -> reject). A bound is None when no
    limit is established from the authority code or a source; it is never guessed.
    """
    key: str
    label: str
    unit: Optional[str]  # canonical unit sent to the authority (number/integer only)
    quantity_kind: str
    min: Optional[float]
    max: Optional[float]
    default: Scalar
    required: bool = True
    step: Optional[float] = None
    display_units: Tuple[str, ...] = ()
    enum: Tuple[str, ...] = ()
    value_type: str = "number"
    # Recorded fact about how the authority treats this key (e.g. clamps instead of rejecting).
    note: Optional[str] = None

    def __post_init__(self) -> None:
        _require(isinstance(self.key, str) and bool(_KEY.match(self.key)), f"invalid field key {self.key!r}")
        _text(self.label, f"{self.key}.label")
        _text(self.quantity_kind, f"{self.key}.quantityKind")
        _one_of(self.value_type, VALUE_TYPES, f"{self.key}.valueType")
        _require(isinstance(self.required, bool), f"{self.key}.required must be a boolean")
        _unique(self.display_units, f"{self.key}.displayUnits")
        if self.note is not None:
            _text(self.note, f"{self.key}.note")
        numeric = self.value_type in ("number", "integer")
        if numeric:
            _text(self.unit, f"{self.key}.unit")
            for bound in ("min", "max"):
                if getattr(self, bound) is not None:
                    _finite(getattr(self, bound), f"{self.key}.{bound}")
            if self.min is not None and self.max is not None:
                _require(self.min <= self.max, f"{self.key}: min must not exceed max")
            if self.step is not None:
                _finite(self.step, f"{self.key}.step")
                _require(self.step > 0, f"{self.key}.step must be positive")
            _require(not self.enum, f"{self.key}: enum applies only to valueType 'enum'")
        else:
            _require(self.unit is None and self.min is None and self.max is None and self.step is None
                     and not self.display_units,
                     f"{self.key}: {self.value_type} fields carry no unit, bounds or step")
        if self.value_type == "enum":
            _require(len(self.enum) > 0, f"{self.key}: enum fields need values")
            _unique(self.enum, f"{self.key}.enum")
            for value in self.enum:
                _text(value, f"{self.key}.enum")
        else:
            _require(not self.enum, f"{self.key}: enum applies only to valueType 'enum'")
        problem = self.value_problem(self.default)
        _require(problem is None, f"{self.key}: default {problem}")
        if self.value_type == "integer" and self.step is not None:
            _require(_is_integer(self.step), f"{self.key}.step must be an integer")

    def value_problem(self, value: Any) -> Optional[str]:
        """Why ``value`` is not acceptable for this field, or None. Hard bounds reject."""
        if self.value_type == "boolean":
            return None if isinstance(value, bool) else "must be a boolean"
        if self.value_type == "enum":
            return None if isinstance(value, str) and value in self.enum else f"must be one of {list(self.enum)}"
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return "must be a finite number"
        if self.value_type == "integer" and not _is_integer(value):
            return "must be an integer"
        if self.min is not None and value < self.min:
            return f"must be >= {self.min}"
        if self.max is not None and value > self.max:
            return f"must be <= {self.max}"
        return None

    def to_dict(self) -> dict:
        return {
            "key": self.key, "label": self.label, "valueType": self.value_type, "unit": self.unit,
            "displayUnits": list(self.display_units), "quantityKind": self.quantity_kind,
            "min": self.min, "max": self.max, "step": self.step, "default": self.default,
            "required": self.required, "enum": list(self.enum), "note": self.note,
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


def looks_like_status_key(key: str) -> bool:
    """Output keys a reader could take for a result/evidence status (case and '_' ignored)."""
    norm = key.replace("_", "").lower()
    return norm.endswith("status") or norm.startswith("evidence")


@dataclass(frozen=True)
class OutputSchema:
    fields: Tuple[str, ...]
    # Top-level key carrying the run's evidence status. None records that the
    # authority's output carries no evidence status at all (then emits is empty).
    status_key: Optional[str] = "evidenceStatus"
    # Status-like fields that are transport values, with every value the authority
    # can put there (e.g. ("status", ("success",))). None of them may be an evidence
    # status or a claim; any other status-like field is rejected.
    transport_values: Tuple[Tuple[str, Tuple[str, ...]], ...] = ()

    def __post_init__(self) -> None:
        _require(len(self.fields) > 0, "output.fields must not be empty")
        _unique(self.fields, "output.fields")
        for key in self.fields:
            _require(key not in FORBIDDEN_CLAIM_KEYS, f"output field {key!r} is a forbidden claim key")
        transport = dict(self.transport_values)
        _require(len(transport) == len(self.transport_values), "output.transportValues keys must be unique")
        for key, values in transport.items():
            _require(key in self.fields, f"output.transportValues key {key!r} is not an output field")
            _require(key != self.status_key, f"output.transportValues cannot describe the status key {key!r}")
            _require(len(values) > 0, f"output.transportValues[{key!r}] needs values")
            _unique(values, f"output.transportValues[{key!r}]")
            for value in values:
                _text(value, f"output.transportValues[{key!r}]")
                _require(value not in EVIDENCE_STATUSES and value not in FORBIDDEN_CLAIM_KEYS,
                         f"output.transportValues[{key!r}] value {value!r} is an evidence status or claim")
        for key in self.fields:
            if key != self.status_key and looks_like_status_key(key):
                # Without this, a contract with statusKey None could hide a real status field.
                _require(key in transport, f"output field {key!r} looks like a status key; declare it as the "
                                           "statusKey or list its transport values")
        if self.status_key is None:
            return
        _text(self.status_key, "output.statusKey")
        # The status key is reserved by the same claim names as the fields.
        _require(self.status_key not in FORBIDDEN_CLAIM_KEYS,
                 f"output.statusKey {self.status_key!r} is a forbidden claim key")
        _require(self.status_key not in self.fields,
                 f"output.statusKey {self.status_key!r} collides with an output field")

    def to_dict(self) -> dict:
        return {"fields": list(self.fields), "statusKey": self.status_key,
                "transportValues": {key: list(values) for key, values in self.transport_values}}


@dataclass(frozen=True)
class Operation:
    id: str
    # None only for browser-local operations, which have no server route.
    route: Optional[str]
    authority: Authority
    input: Tuple[InputField, ...] = ()
    # None = output schema not yet declared (legacy contracts only; see ModuleContract).
    output: Optional[OutputSchema] = None
    # HTTP method of the route; required with a route, absent without one.
    method: Optional[str] = None
    # Request keys the authority reads that the Field schema cannot describe
    # (free-text labels, element maps). Recorded so they are not silently missing.
    undeclared_input: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require(isinstance(self.id, str) and bool(_MODULE_ID.match(self.id)), f"invalid operation id {self.id!r}")
        if self.route is None:
            _require(self.authority.kind == "browser-local", f"{self.id}: only browser-local operations may omit a route")
            _require(self.method is None, f"{self.id}: an operation without a route has no HTTP method")
        else:
            _require(isinstance(self.route, str) and self.route.startswith("/api/"), "operation.route must start with /api/")
            _one_of(self.method, HTTP_METHODS, f"{self.id}.method")
        _unique(tuple(f.key for f in self.input), f"{self.id}.input keys")
        _unique(self.undeclared_input, f"{self.id}.undeclaredInput")
        for key in self.undeclared_input:
            _require(isinstance(key, str) and bool(_KEY.match(key)), f"{self.id}: invalid undeclared key {key!r}")
        _require(not set(self.undeclared_input) & {f.key for f in self.input},
                 f"{self.id}: a key cannot be both declared and undeclared")

    def to_dict(self) -> dict:
        return {
            "id": self.id, "method": self.method, "route": self.route, "authority": self.authority.to_dict(),
            "input": [f.to_dict() for f in self.input],
            "undeclaredInput": list(self.undeclared_input),
            "output": self.output.to_dict() if self.output else None,
        }

    def input_problems(self, payload: Any) -> list:
        """Contract-side request check: required keys, types, hard ranges, unknown keys.

        Pure; never coerces or clamps. Undeclared-but-recorded keys are passed through
        unchecked because the schema cannot describe them.
        """
        if not isinstance(payload, dict):
            return ["payload must be an object"]
        problems = []
        fields = {f.key: f for f in self.input}
        for key, spec in fields.items():
            if key not in payload:
                if spec.required:
                    problems.append(f"{key}: required")
                continue
            problem = spec.value_problem(payload[key])
            if problem:
                problems.append(f"{key}: {problem}")
        for key in payload:
            if key not in fields and key not in self.undeclared_input:
                problems.append(f"{key}: not declared by the contract")
        return problems


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
    # Repository files (optionally ``path:line`` or ``path:start-end``) the contract's
    # fields, limits and outputs were read from. Required once contracted; each must exist.
    source_refs: Tuple[str, ...] = ()

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
            # Legacy node-provider/browser-local authorities may leave the timeout undeclared;
            # a contracted operation must state the deadline it runs under.
            _require(all(op.authority.timeout_ms is not None for op in self.operations),
                     f"{self.id}: contracted operations must declare authority.timeoutMs")
            # emits lists only statuses the code really emits: an output without a
            # status key emits none, and an output with one must declare what it emits.
            carries_status = any(op.output.status_key is not None for op in self.operations)
            if carries_status:
                _require(len(self.evidence.emits) > 0, f"{self.id}: contracted modules must declare emits")
            else:
                _require(len(self.evidence.emits) == 0,
                         f"{self.id}: emits must be empty when no operation output carries a status key")
                _text(self.evidence.note, f"{self.id}.evidence.note")
            _require(self.lifecycle is not None, f"{self.id}: contracted modules need a lifecycle")
            _text(self.tests.schema, f"{self.id}.tests.schema")
            _text(self.tests.docs, f"{self.id}.tests.docs")
            _require(len(self.source_refs) > 0, f"{self.id}: contracted modules need sourceRefs")
            _require(TODO_MARKER not in self.owner, f"{self.id}: contracted modules need a reviewed owner")
        _unique(self.source_refs, f"{self.id}.sourceRefs")
        for ref in self.source_refs:
            _text(ref, f"{self.id}.sourceRefs")

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
            "legacyNotes": list(self.legacy_notes), "sourceRefs": list(self.source_refs),
        }


# --- Round trip (generated JSON -> contract) ----------------------------------

def _field_from_dict(d: dict) -> InputField:
    return InputField(key=d["key"], label=d["label"], unit=d["unit"], quantity_kind=d["quantityKind"],
                      min=d["min"], max=d["max"], default=d["default"], required=d["required"],
                      step=d["step"], display_units=tuple(d["displayUnits"]), enum=tuple(d["enum"]),
                      value_type=d["valueType"], note=d["note"])


def _operation_from_dict(d: dict) -> Operation:
    a = d["authority"]
    authority = Authority(kind=a["kind"], timeout_ms=a["timeoutMs"], gpu=a["gpu"], warm=a["warm"],
                          script=a["script"], worker_method=a["workerMethod"], exception_reason=a["exceptionReason"])
    out = d["output"]
    return Operation(id=d["id"], route=d["route"], method=d["method"], authority=authority,
                     input=tuple(_field_from_dict(f) for f in d["input"]),
                     undeclared_input=tuple(d["undeclaredInput"]),
                     output=OutputSchema(fields=tuple(out["fields"]), status_key=out["statusKey"],
                                         transport_values=tuple((k, tuple(v)) for k, v in out["transportValues"].items()))
                     if out else None)


def contract_from_dict(d: dict) -> ModuleContract:
    """Rebuild (and so re-validate) a contract from its emitted dictionary."""
    vd = d["validityDomain"]
    lc = d["lifecycle"]
    t = d["tests"]
    ev = d["evidence"]
    return ModuleContract(
        id=d["id"], version=d["version"], owner=d["owner"], workspace=d["workspace"], label=d["label"],
        description=d["description"], next=d["next"], maturity=d["maturity"], navigation=d["navigation"],
        hidden_reason=d["hiddenReason"], view=View(component=d["view"]["component"], export=d["view"]["export"]),
        operations=tuple(_operation_from_dict(op) for op in d["operations"]),
        validity_domain=ValidityDomain(
            ranges=tuple(FieldRange(**r) for r in vd["ranges"]), source_refs=tuple(vd["sourceRefs"]),
            materials=tuple(vd["materials"]), regime_notes=tuple(vd["regimeNotes"])) if vd else None,
        evidence=Evidence(emits=tuple(ev["emits"]), ceiling=ev["ceiling"],
                          forbidden_claims=tuple(ev["forbiddenClaims"]), note=ev["note"]),
        lifecycle=Lifecycle(background_work=lc["backgroundWork"], resources=tuple(lc["resources"])) if lc else None,
        tests=TestRefs(oracle=Oracle(status=t["oracle"]["status"], ref=t["oracle"]["ref"]),
                       schema=t["schema"], docs=t["docs"]),
        migration_state=d["migrationState"], legacy_notes=tuple(d["legacyNotes"]),
        source_refs=tuple(d["sourceRefs"]),
    )


if __name__ == "__main__":
    # `python -m module_contract emit [--check]` (run from python/)
    # delegates to the registry emitter; scripts/emit-module-registry.py is equivalent.
    import sys

    from module_registry import main as _registry_main

    _args = sys.argv[1:]
    if not _args or _args[0] != "emit":
        print("usage: python -m module_contract emit [--check]", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(_registry_main(_args[1:]))
