"""Module registry (Phase 7 step 0 skeleton).

Holds one ``ModuleContract`` per product module and emits the committed
frontend artifacts ``src/generated/moduleRegistry.json`` and
``src/generated/moduleRegistry.ts``.

Migration step 0: every module listed in ``MODULES`` (src/data/workspaces.ts)
is auto-generated as a ``legacy`` contract from the committed snapshot
``python/module_registry_seed.json``. The snapshot is used instead of parsing
TypeScript at runtime so the Python side needs no TS sources and stays
deterministic; ``test_module_contract.py`` re-parses workspaces.ts and App.tsx
and fails when the snapshot drifts. Refresh it with
``python scripts/emit-module-registry.py --refresh-seed``.

Legacy contracts carry only identity and view data from the existing UI. All
other values are TODO(maintainer-review) placeholders that bound claims
conservatively; they are not reviewed facts.

Usage (from the repo root):
    python scripts/emit-module-registry.py            # write generated files
    python scripts/emit-module-registry.py --check    # fail if out of date
    python scripts/emit-module-registry.py --refresh-seed
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from module_contract import (
    ALWAYS_FORBIDDEN_CLAIMS, AUTHORITY_KINDS, BACKGROUND_WORK, EVIDENCE_STATUSES, EVIDENCE_TYPES,
    FORBIDDEN_CLAIM_KEYS, GPU_MODES, LIFECYCLE_RESOURCES, MATURITY, MIGRATION_STATES, NAVIGATION,
    ORACLE_STATES, PENDING_ORACLE_CEILING, RUN_STATES, TODO_MARKER, WORKSPACES,
    Evidence, ModuleContract, Oracle, TestRefs, View,
)

PYTHON_DIR = Path(__file__).resolve().parent
REPO_ROOT = PYTHON_DIR.parent
SEED_PATH = PYTHON_DIR / "module_registry_seed.json"
WORKSPACES_TS = REPO_ROOT / "src" / "data" / "workspaces.ts"
APP_TSX = REPO_ROOT / "src" / "App.tsx"
GENERATED_JSON = REPO_ROOT / "src" / "generated" / "moduleRegistry.json"
GENERATED_TS = REPO_ROOT / "src" / "generated" / "moduleRegistry.ts"
SCHEMA_VERSION = 1

LEGACY_OWNER = f"{TODO_MARKER}: unassigned"
LEGACY_VERSION = "0.0.0"
LEGACY_EVIDENCE_NOTE = (
    f"{TODO_MARKER}: legacy placeholder. Ceiling is the pending-oracle cap and emits is "
    "undeclared; neither is a reviewed per-module evidence statement."
)

# --- Seed parsing (development helpers; pure functions on source text) ------

_MODULE_ROW = re.compile(
    r"\{\s*id:\s*'([^']+)',\s*workspace:\s*'([^']+)',\s*label:\s*'((?:[^'\\]|\\.)*)',\s*"
    r"scope:\s*'([^']+)',\s*description:\s*'((?:[^'\\]|\\.)*)',\s*next:\s*'([^']+)'\s*\}"
)
_LAZY_IMPORT = re.compile(
    r"const\s+(\w+)\s*=\s*lazy\(\(\)\s*=>\s*import\(\s*[\"']\./components/([\w/]+)[\"']\s*\)"
    r"\.then\(\s*m\s*=>\s*\(\{\s*default:\s*m\.(\w+)\s*\}\)\s*\)\s*\)"
)
_CASE = re.compile(r"case\s+'([^']+)':\s*return\s*<(\w+)")


def _unescape(value: str) -> str:
    return re.sub(r"\\(.)", r"\1", value)


def parse_workspaces_modules(text: str) -> List[Dict[str, str]]:
    """Extract MODULES rows from src/data/workspaces.ts source text."""
    start = text.index("export const MODULES = [")
    end = text.index("] as const", start)
    rows = []
    for match in _MODULE_ROW.finditer(text[start:end]):
        module_id, workspace, label, scope, description, next_id = match.groups()
        rows.append({"id": module_id, "workspace": workspace, "label": _unescape(label),
                     "scope": scope, "description": _unescape(description), "next": next_id})
    return rows


def parse_app_views(text: str) -> Dict[str, Dict[str, str]]:
    """Map module id -> view component from the renderModule switch in App.tsx."""
    lazy = {name: (path, export) for name, path, export in _LAZY_IMPORT.findall(text)}
    switch = text[text.index("function renderModule"):]
    views = {}
    for module_id, component in _CASE.findall(switch):
        if component not in lazy:
            raise ValueError(f"view {component!r} for {module_id!r} is not a lazy component import")
        path, export = lazy[component]
        views[module_id] = {"component": f"src/components/{path}.tsx", "export": export}
    return views


def build_seed(workspaces_text: str, app_text: str) -> List[Dict[str, str]]:
    views = parse_app_views(app_text)
    seed = []
    for row in parse_workspaces_modules(workspaces_text):
        view = views.get(row["id"])
        if view is None:
            raise ValueError(f"module {row['id']!r} has no renderModule case")
        seed.append({**row, "viewComponent": view["component"], "viewExport": view["export"]})
    return seed


def render_seed(seed: List[Dict[str, str]]) -> str:
    return json.dumps(seed, indent=2, ensure_ascii=False) + "\n"


def load_seed() -> List[Dict[str, str]]:
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


# --- Registry ---------------------------------------------------------------

def legacy_contract(row: Dict[str, str]) -> ModuleContract:
    """Auto-generate a legacy contract; only identity and view come from the UI."""
    return ModuleContract(
        id=row["id"],
        version=LEGACY_VERSION,
        owner=LEGACY_OWNER,
        workspace=row["workspace"],
        label=row["label"],
        description=row["description"],
        next=row["next"],
        maturity=row["scope"],  # Must already be Research or Preview.
        navigation="listed",  # The UI stays unchanged in step 0.
        view=View(component=row["viewComponent"], export=row["viewExport"]),
        evidence=Evidence(
            emits=(),
            ceiling=PENDING_ORACLE_CEILING,
            forbidden_claims=FORBIDDEN_CLAIM_KEYS,
            note=LEGACY_EVIDENCE_NOTE,
        ),
        tests=TestRefs(oracle=Oracle(status="pending")),
        migration_state="legacy",
    )


def build_registry(seed: List[Dict[str, str]] = None) -> Tuple[ModuleContract, ...]:
    rows = load_seed() if seed is None else seed
    contracts = tuple(legacy_contract(row) for row in rows)
    ids = [c.id for c in contracts]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate module ids in registry")
    known = set(ids)
    for contract in contracts:
        if contract.next not in known:
            raise ValueError(f"{contract.id}: next {contract.next!r} is not a registered module")
    return contracts


# --- Emitters ---------------------------------------------------------------

def registry_document(contracts: Tuple[ModuleContract, ...]) -> dict:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedBy": "python/module_registry.py",
        "vocabulary": {
            "evidenceTypes": list(EVIDENCE_TYPES),
            "runStates": list(RUN_STATES),
            "evidenceStatuses": list(EVIDENCE_STATUSES),
            "pendingOracleCeiling": PENDING_ORACLE_CEILING,
            "forbiddenClaimKeys": list(FORBIDDEN_CLAIM_KEYS),
            "alwaysForbiddenClaims": list(ALWAYS_FORBIDDEN_CLAIMS),
            "maturity": list(MATURITY),
            "navigation": list(NAVIGATION),
            "migrationStates": list(MIGRATION_STATES),
        },
        "contracts": [c.to_dict() for c in contracts],
    }


def render_json(document: dict) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def _union(values) -> str:
    return " | ".join(json.dumps(v) for v in values)


def render_ts(document: dict) -> str:
    body = json.dumps(document, indent=2, ensure_ascii=False)
    lines = [
        "// GENERATED by python/module_registry.py. Do not edit by hand.",
        "// Regenerate: python scripts/emit-module-registry.py",
        "",
        f"export type EvidenceType = {_union(EVIDENCE_TYPES)};",
        f"export type RunState = {_union(RUN_STATES)};",
        "export type EvidenceStatus = EvidenceType | RunState;",
        f"export type ForbiddenClaimKey = {_union(FORBIDDEN_CLAIM_KEYS)};",
        f"export type ContractMaturity = {_union(MATURITY)};",
        f"export type ContractNavigation = {_union(NAVIGATION)};",
        f"export type ContractWorkspace = {_union(WORKSPACES)};",
        f"export type AuthorityKind = {_union(AUTHORITY_KINDS)};",
        f"export type GpuMode = {_union(GPU_MODES)};",
        f"export type BackgroundWork = {_union(BACKGROUND_WORK)};",
        f"export type LifecycleResource = {_union(LIFECYCLE_RESOURCES)};",
        f"export type OracleState = {_union(ORACLE_STATES)};",
        f"export type MigrationState = {_union(MIGRATION_STATES)};",
        "",
        "export interface ContractField {",
        "  readonly key: string; readonly label: string; readonly unit: string;",
        "  readonly displayUnits: readonly string[]; readonly quantityKind: string;",
        "  readonly min: number; readonly max: number; readonly step: number | null;",
        "  readonly default: number | string | boolean; readonly required: boolean; readonly enum: readonly string[];",
        "}",
        "export interface ContractAuthority {",
        "  readonly kind: AuthorityKind; readonly script: string | null; readonly workerMethod: string | null;",
        "  readonly timeoutMs: number; readonly gpu: GpuMode; readonly warm: boolean; readonly exceptionReason: string | null;",
        "}",
        "export interface ContractOperation {",
        "  readonly id: string; readonly route: string; readonly authority: ContractAuthority;",
        "  readonly input: readonly ContractField[];",
        "  readonly output: { readonly fields: readonly string[]; readonly statusKey: string };",
        "}",
        "export interface ContractValidityDomain {",
        "  readonly ranges: readonly { readonly key: string; readonly min: number; readonly max: number; readonly unit: string }[];",
        "  readonly materials: readonly string[]; readonly regimeNotes: readonly string[]; readonly sourceRefs: readonly string[];",
        "}",
        "export interface ModuleContract {",
        "  readonly id: string; readonly version: string; readonly owner: string;",
        "  readonly workspace: ContractWorkspace; readonly label: string; readonly description: string; readonly next: string;",
        "  readonly maturity: ContractMaturity; readonly navigation: ContractNavigation; readonly hiddenReason: string | null;",
        "  readonly view: { readonly component: string; readonly export: string };",
        "  readonly operations: readonly ContractOperation[];",
        "  readonly validityDomain: ContractValidityDomain | null;",
        "  readonly evidence: {",
        "    readonly emits: readonly EvidenceStatus[]; readonly ceiling: EvidenceType;",
        "    readonly forbiddenClaims: readonly ForbiddenClaimKey[]; readonly note: string | null;",
        "  };",
        "  readonly lifecycle: { readonly backgroundWork: BackgroundWork; readonly resources: readonly LifecycleResource[] } | null;",
        "  readonly tests: {",
        "    readonly schema: string | null; readonly oracle: { readonly status: OracleState; readonly ref: string | null };",
        "    readonly docs: string | null;",
        "  };",
        "  readonly migrationState: MigrationState;",
        "}",
        "export interface ModuleRegistryDocument {",
        "  readonly schemaVersion: number; readonly generatedBy: string;",
        "  readonly vocabulary: Readonly<Record<string, string | readonly string[]>>;",
        "  readonly contracts: readonly ModuleContract[];",
        "}",
        "",
        f"export const MODULE_REGISTRY = {body} as const satisfies ModuleRegistryDocument;",
        "",
    ]
    return "\n".join(lines)


def rendered_outputs() -> Dict[Path, str]:
    document = registry_document(build_registry())
    return {GENERATED_JSON: render_json(document), GENERATED_TS: render_ts(document)}


def _normalized(text: str) -> str:
    return text.replace("\r\n", "\n")


def stale_outputs() -> List[Path]:
    """Generated files whose committed text differs from a fresh emit (EOL-insensitive)."""
    stale = []
    for path, text in rendered_outputs().items():
        if not path.exists() or _normalized(path.read_text(encoding="utf-8")) != text:
            stale.append(path)
    return stale


def emit() -> List[Path]:
    written = []
    for path, text in rendered_outputs().items():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="\r\n") as handle:
            handle.write(text)
        written.append(path)
    return written


def refresh_seed() -> Path:
    seed = build_seed(WORKSPACES_TS.read_text(encoding="utf-8"), APP_TSX.read_text(encoding="utf-8"))
    with SEED_PATH.open("w", encoding="utf-8", newline="\r\n") as handle:
        handle.write(render_seed(seed))
    return SEED_PATH


def main(argv: List[str]) -> int:
    if "--refresh-seed" in argv:
        print(f"wrote {refresh_seed()}")
    if "--check" in argv:
        stale = stale_outputs()
        for path in stale:
            print(f"stale: {path}", file=sys.stderr)
        return 1 if stale else 0
    for path in emit():
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
