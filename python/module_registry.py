"""Module registry (Phase 7 step 0 skeleton).

Holds one ``ModuleContract`` per product module and emits the committed
frontend artifacts ``src/generated/moduleRegistry.json`` and
``src/generated/moduleRegistry.ts``.

Migration step 0 generated one ``legacy`` contract per navigation module from
``python/module_registry_seed.json``. Since Phase 7 slice 1 the registry is the
single source for navigation: ``MODULES`` in src/data/workspaces.ts is derived
from the emitted listed contracts, so the seed JSON is the canonical identity
data (id, workspace, label, maturity, description, next, view) and is edited by
hand. ``test_module_contract.py`` checks the seed views against the App.tsx
renderModule switch; tests/workspaces-registry-parity.test.ts pins the derived
navigation to the pre-registry golden list.

Legacy contracts carry identity, view and best-effort authority data from the
existing code. All other values are TODO(maintainer-review) placeholders that
bound claims conservatively; they are not reviewed facts.

Usage (from python/):  python -m module_contract emit [--check]
Usage (from the repo root):
    python scripts/emit-module-registry.py            # write generated files
    python scripts/emit-module-registry.py --check    # fail if out of date
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
    Authority, Evidence, ModuleContract, Operation, Oracle, TestRefs, View,
)

PYTHON_DIR = Path(__file__).resolve().parent
REPO_ROOT = PYTHON_DIR.parent
SEED_PATH = PYTHON_DIR / "module_registry_seed.json"
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

# --- App.tsx view parsing (pure function on source text) ---------------------

_LAZY_IMPORT = re.compile(
    r"const\s+(\w+)\s*=\s*lazy\(\(\)\s*=>\s*import\(\s*[\"']\./components/([\w/]+)[\"']\s*\)"
    r"\.then\(\s*m\s*=>\s*\(\{\s*default:\s*m\.(\w+)\s*\}\)\s*\)\s*\)"
)
_CASE = re.compile(r"case\s+'([^']+)':\s*return\s*<(\w+)")


def _function_body(text: str, marker: str) -> str:
    """Text of the brace-balanced body of the function starting at ``marker``."""
    open_index = text.index("{", text.index(marker))
    depth = 0
    for index in range(open_index, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[open_index:index + 1]
    raise ValueError(f"unbalanced braces after {marker!r}")


def parse_app_views(text: str) -> Dict[str, Dict[str, str]]:
    """Map module id -> view component from the renderModule switch in App.tsx."""
    lazy = {name: (path, export) for name, path, export in _LAZY_IMPORT.findall(text)}
    switch = _function_body(text, "function renderModule")
    views = {}
    for module_id, component in _CASE.findall(switch):
        if module_id in views:
            raise ValueError(f"duplicate renderModule case {module_id!r}")
        if component not in lazy:
            raise ValueError(f"view {component!r} for {module_id!r} is not a lazy component import")
        path, export = lazy[component]
        views[module_id] = {"component": f"src/components/{path}.tsx", "export": export}
    return views


def load_seed() -> List[Dict[str, str]]:
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


# --- Legacy authorities (Phase 7 slice 1) ------------------------------------
#
# Best-effort record of which server route and authority each view calls today,
# read from the code (the view's static import closure, src/services/*, routes/*,
# server/*). Timeouts are the values the dispatching code uses: physics.ts
# handlePythonDispatch default 25000 ms (calphad 40000/15000, Bayesian 120000),
# characterization.ts runPythonScript default 15000 ms, LpbfWorkerBridge
# requestTimeoutMs default 20000 ms. node-provider and browser-local authorities
# declare no timeout in code, so none is recorded. ``warm`` is set by hand from
# the script's presence in python/persistent_ipc_service.py WARM_MODULE_NAMES at
# the time of writing; test_module_contract checks the two lists against each
# other instead of deriving one from the other.
#
# Nothing here is an evidence statement: input fields, output schemas, validity
# domains and source refs stay undeclared until a module is contracted.

_PHYSICS_TIMEOUT_MS = 25000      # routes/physics.ts handlePythonDispatch default
_CHARACTERIZATION_TIMEOUT_MS = 15000  # server/processOrchestrator.ts runPythonScript default
_WORKER_TIMEOUT_MS = 20000       # server/lpbfWorkerBridge.ts requestTimeoutMs default


def _py(script: str, timeout_ms: int, warm: bool) -> Authority:
    return Authority(kind="python-ipc", script=f"python/{script}.py", timeout_ms=timeout_ms, warm=warm)


def _worker(method: str) -> Authority:
    return Authority(kind="lpbf-worker", worker_method=method, timeout_ms=_WORKER_TIMEOUT_MS)


_NODE = Authority(kind="node-provider")


def _browser(reason: str) -> Authority:
    return Authority(kind="browser-local", exception_reason=f"Recorded debt (single-authority rule): {reason}")


def _op(op_id: str, route, authority: Authority) -> Operation:
    return Operation(id=op_id, route=route, authority=authority)


def _worker_op(method: str) -> Operation:
    return _op(method, f"/api/python/lpbf-{method}", _worker(method))


_THERMAL_SOLVER = _op("lpbf-thermal-solver", "/api/python/lpbf-thermal-solver",
                      _py("lpbf_thermal_solver", _PHYSICS_TIMEOUT_MS, warm=True))
_AI_CONSULT = _op("ai-consult", "/api/consult", _NODE)
_BUILD_JOB_SUBMIT = _op("lpbf-job-submit", "/api/lpbf/jobs", _worker("submit"))
_BUILD_JOB_STATUS = _op("lpbf-job-status", "/api/lpbf/jobs/:id", _worker("get"))
_CANNED_QUALIFY = ("POST /api/metallurgy/qualify-aerospace returns constant values (qualified: true) "
                   "without calling any authority; not bound as an operation.")

LEGACY_OPERATIONS: Dict[str, Tuple[Operation, ...]] = {
    "3d-distortion-lab": (
        _op("lpbf-capabilities", "/api/lpbf/capabilities", _worker("capabilities")),
        _op("lpbf-estimate", "/api/lpbf/estimate", _worker("estimate")),
        _BUILD_JOB_SUBMIT,
        _op("lpbf-job-repeat", "/api/lpbf/jobs/repeat", _worker("submit-repeat")),
        _BUILD_JOB_STATUS,
        _op("lpbf-job-cancel", "/api/lpbf/jobs/:id", _worker("cancel")),
        _op("lpbf-job-artifact", "/api/lpbf/jobs/:id/artifacts/:name", _worker("artifact")),
        _THERMAL_SOLVER,
        _op("stl-slicer-build-time", "/api/python/stl-slicer-build-time",
            _py("stl_slicer_build_time_solver", _PHYSICS_TIMEOUT_MS, warm=True)),
        _op("lpbf-source-catalog", "/api/lpbf/sources", _NODE),
        _op("lpbf-run-archive", "/api/lpbf/runs", _NODE),
    ),
    "lpbf-optimizer": (
        _op("bayesian-optimize", "/api/python/lpbf-bayesian-optimize",
            _py("lpbf_bayesian_optimizer", 120000, warm=False)),
    ),
    "solidification-microstructure": (_worker_op("solidification-microstructure"),),
    "thermomechanical-distortion": (_worker_op("thermomechanical-distortion"),),
    "experimental-validation": (
        _op("lpbf-source-measurements", "/api/lpbf/sources/:datasetId/measurements", _NODE),
    ),
    "modulus-fno-lab": (_worker_op("modulus-fno"),),
    "toolpath-studio": (_worker_op("toolpath-kinematics"),),
    "toolpath-thermal-map": (_worker_op("toolpath-thermal-map"),),
    "industrial-certification": (_worker_op("industrial-fatigue"),),
    "murakami-fatigue": (_worker_op("fatigue-fracture"),),
    "defect-twin": (_worker_op("stl-voxelize"),),
    "adaptive-mitigation": (_worker_op("adaptive-feedforward"),),
    "multilaser-plume": (_worker_op("multilaser-plume"),),
    "thermal-accumulation": (_worker_op("thermal-accumulation"),),
    "powder-compaction": (_worker_op("powder-dem-compaction"),),
    "optical-tomography": (_worker_op("optical-tomography"),),
    "transient-3d-gpu": (),
    "keyhole-raytracing": (_worker_op("keyhole-raytracing"),),
    "database": (
        _op("catalog-lookup", None, _browser("material records are read from the bundled src/data/materialsDatabase.ts in the browser.")),
    ),
    "alloy-builder": (_THERMAL_SOLVER,),
    "phase-diagram": (
        _op("calphad-databases", "/api/python/calphad-databases", _py("calphad_solver", 15000, warm=True)),
        _op("calphad-minimize", "/api/python/calphad-minimize", _py("calphad_solver", 40000, warm=True)),
        _AI_CONSULT,
    ),
    "ttt-cct-kinetics": (
        _op("kinetics-ttt-cct", "/api/python/kinetics-ttt-cct", _py("kinetics_ttt_cct_solver", _PHYSICS_TIMEOUT_MS, warm=True)),
    ),
    "micrograph": (
        _op("diagnose-micrograph", "/api/metallurgy/diagnose-micrograph", _NODE),
        _AI_CONSULT,
    ),
    "eds-lab": (_AI_CONSULT,),
    "electrochem-suite": (
        _op("pourbaix-diagram", "/api/python/pourbaix-diagram", _py("pourbaix_solver", _PHYSICS_TIMEOUT_MS, warm=True)),
        _op("tafel-corrosion-rate", "/api/python/tafel-corrosion-rate",
            _py("tafel_corrosion_rate_solver", _CHARACTERIZATION_TIMEOUT_MS, warm=True)),
        _op("battery-corrosion-eis", "/api/python/battery-corrosion-eis",
            _py("battery_corrosion_eis_solver", _CHARACTERIZATION_TIMEOUT_MS, warm=True)),
    ),
    "icme-motor": (
        _op("icme-multiscale-pipeline", "/api/python/icme-multiscale-pipeline",
            _py("icme_multiscale_pipeline_solver", _PHYSICS_TIMEOUT_MS, warm=True)),
    ),
    "materials-project": (
        _op("materials-project-search", "/api/materials-project/search", _NODE),
        _op("dft-properties", "/api/python/dft-properties", _py("dft_property_calculator", _PHYSICS_TIMEOUT_MS, warm=True)),
        _op("metallurgy-consult", "/api/metallurgy/consult", _NODE),
    ),
    "calculators": (
        _op("engineering-correlations", None, _browser("unit-aware engineering correlations are evaluated in the browser.")),
    ),
    "research-hub": (
        _op("research-registry", "/api/research/registry", _NODE),
        _op("research-search", "/api/research/search", _NODE),
    ),
    "experimental-data": (_BUILD_JOB_SUBMIT, _BUILD_JOB_STATUS),
    "digital-twin": (_AI_CONSULT,),
    "uq-lab": (
        _op("stochastic-uq-mmpds", "/api/python/stochastic-uq-mmpds",
            _py("stochastic_uq_mmpds_solver", _PHYSICS_TIMEOUT_MS, warm=True)),
    ),
    "qualification": (
        _op("coupon-statistics", None, _browser("protocol screening and coupon statistics are computed in the browser.")),
    ),
    "aerospace-pdf-audit": (
        _op("report-template", None, _browser("demonstration report templates are assembled in the browser.")),
    ),
    "traceability": (_BUILD_JOB_SUBMIT, _BUILD_JOB_STATUS),
    "copilot": (_op("metallurgy-consult", "/api/metallurgy/consult", _NODE),),
    "ai-orchestrator": (_op("dataset-plan", "/api/orchestrator/dataset-plan", _NODE),),
}

LEGACY_NOTES: Dict[str, Tuple[str, ...]] = {
    "transient-3d-gpu": (
        "The view calls POST /api/python/transient-3d-gpu, which no server route handles; "
        "no authority exists for this module.",
    ),
    "micrograph": (
        "POST /api/metallurgy/detect-sem-legend and POST /api/metallurgy/analyze-sem return constant "
        "values without calling any authority; not bound as operations.",
    ),
    "qualification": (_CANNED_QUALIFY,),
    "aerospace-pdf-audit": (_CANNED_QUALIFY,),
}


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
        # TODO(maintainer-review): maturity is copied from the UI scope without
        # review (.orchestra/REVIEW-prep-opus-python.md, maintainer item 7).
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
        operations=LEGACY_OPERATIONS[row["id"]],
        legacy_notes=LEGACY_NOTES.get(row["id"], ()),
    )


def build_registry(seed: List[Dict[str, str]] = None) -> Tuple[ModuleContract, ...]:
    rows = load_seed() if seed is None else seed
    contracts = tuple(legacy_contract(row) for row in rows)
    ids = [c.id for c in contracts]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate module ids in registry")
    known = set(ids)
    for table, name in ((LEGACY_OPERATIONS, "LEGACY_OPERATIONS"), (LEGACY_NOTES, "LEGACY_NOTES")):
        unknown = set(table) - known
        if unknown:
            raise ValueError(f"{name} names unregistered modules: {sorted(unknown)}")
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
        "// Regenerate: python -m module_contract emit (from python/) or python scripts/emit-module-registry.py",
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
        "  readonly timeoutMs: number | null; readonly gpu: GpuMode; readonly warm: boolean; readonly exceptionReason: string | null;",
        "}",
        "export interface ContractOperation {",
        "  readonly id: string; readonly route: string | null; readonly authority: ContractAuthority;",
        "  readonly input: readonly ContractField[];",
        "  readonly output: { readonly fields: readonly string[]; readonly statusKey: string } | null;",
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
        "  readonly legacyNotes: readonly string[];",
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


def seed_view_mismatches(seed: List[Dict[str, str]], app_text: str) -> List[str]:
    """Differences between the seed views and the App.tsx renderModule switch."""
    views = parse_app_views(app_text)
    problems = []
    for row in seed:
        view = views.pop(row["id"], None)
        expected = {"component": row["viewComponent"], "export": row["viewExport"]}
        if view != expected:
            problems.append(f"{row['id']}: seed view {expected} != App.tsx {view}")
    problems.extend(f"{module_id}: App.tsx case without a registry module" for module_id in sorted(views))
    return problems


def main(argv: List[str]) -> int:
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
