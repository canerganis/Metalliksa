"""Bounded contracts for the two browser-local EvidenceWorkspace modes."""
from __future__ import annotations

from typing import Mapping

from module_contract import (
    ContractError,
    FORBIDDEN_CLAIM_KEYS,
    OWNER_UNASSIGNED,
    PENDING_ORACLE_CEILING,
    Authority,
    Evidence,
    InputField,
    Lifecycle,
    ModuleContract,
    Operation,
    Oracle,
    OutputSchema,
    TestRefs,
    View,
)


_LOCAL = Authority(
    kind="browser-local",
    exception_reason=(
        "EvidenceWorkspace reads browser Zustand stores and performs browser download/navigation actions; "
        "it declares no server route or execution deadline."
    ),
)

_PACKAGE_OUTPUTS = (
    "schemaVersion",
    "exportedAt",
    "scope",
    "activeSpecimen",
    "research",
    "engineering",
    "buildScreening",
    "missingEvidence",
    "blob",
    "url",
    "anchor",
    "download",
    "notice",
)


def _local_operation(
    operation_id: str,
    *,
    outputs: tuple[str, ...],
    inputs: tuple[InputField, ...] = (),
) -> Operation:
    return Operation(
        id=operation_id,
        route=None,
        method=None,
        authority=_LOCAL,
        input=inputs,
        output=OutputSchema(fields=outputs, status_key=None),
    )


def _mode_operations(*, experimental: bool) -> tuple[Operation, ...]:
    scope_field = InputField(
        key="allMaterials",
        label="Show all materials",
        unit=None,
        quantity_kind="display-filter",
        min=None,
        max=None,
        default=False,
        required=True,
        value_type="boolean",
        note=(
            "This checkbox changes only the visible finding filter; it does not change the records "
            "included in the exported research snapshot."
        ),
    )
    operations = [
        _local_operation(
            "set-material-scope",
            inputs=(scope_field,),
            outputs=("allMaterials", "findings"),
        ),
    ]
    if experimental:
        operations.append(
            _local_operation(
                "navigate-to-measurement-entry",
                outputs=("activeTab", "eventName", "tabId"),
            )
        )
    operations.extend((
        _local_operation(
            "navigate-to-research-registry",
            outputs=("activeTab", "eventName", "tabId"),
        ),
        _local_operation(
            "export-evidence-package",
            outputs=_PACKAGE_OUTPUTS,
        ),
    ))
    return tuple(operations)


_COMMON_NOTES = (
    "Both entries render src/components/EvidenceWorkspace.tsx with a fixed mode prop. Findings visible in the list are filtered by allMaterials || finding.materialId === activeSpecimen.id; experimental mode additionally requires finding.evidenceType === 'measured'. The checkbox and mode filters affect display only.",
    "The 'measured' evidenceType is a user-declared record classification. A measured label, reviewed source, review status, or integration link does not establish independent validation or externally certified data.",
    "Export reads the current activeSpecimen, research.exportSnapshot(), engineering.job, engineering.submittedInput, build.job, and peekLpbfBuildJobKey() comparison. It does not use the visible findings list, so the research snapshot includes all briefs, sources, findings, integrations, and feedback regardless of mode or checkbox filter.",
    "The downloaded JSON has schemaVersion, exportedAt, scope, activeSpecimen, research, engineering, buildScreening, and missingEvidence keys. engineering.job and submittedInput are null when absent; build.job is null before a build run. The active specimen is copied from its store; no specimen, job, measurement, or result is synthesized.",
    "The export click handler returns void. Output fields distinguish keys in the downloaded package from the Blob, object URL, anchor download property, and notice used by the browser flow; they are not a returned API object. It revokes the object URL after a 1000 ms setTimeout; lifecycle vocabulary has no timeout resource, so no interval/background resource is declared.",
    "EvidenceWorkspace has no effect, fetch, worker submission, or other background operation. Research data persist in browser-local storage through the research store; changing the active Research Hub tab is persisted there. This view does not save research data to a server.",
    "An export exception is surfaced in the notice as an operational failure. It does not create an evidence status. Qualification and independent experimental validation remain unresolved.",
)


def _build_contract(seed: Mapping[str, str], *, module_id: str, experimental: bool) -> ModuleContract:
    if seed.get("id") != module_id:
        raise ContractError(f"{module_id}: expected its own registry seed row")
    mode_notes = (
        "Experimental mode renders ResearchIntegrationPanel for validation-dataset links and its button opens Research Hub registry. Its measurement-entry button sets activeTab to 'extract' and dispatches metallix-navigate-tab with tabId 'research-hub'."
        if experimental else
        "Traceability mode shows provenance for all evidence types (subject to material scope). Its review button sets activeTab to 'registry' and dispatches metallix-navigate-tab with tabId 'research-hub'."
    )
    return ModuleContract(
        id=module_id,
        version="1.0.0",
        owner=OWNER_UNASSIGNED,
        workspace=seed["workspace"],
        label=seed["label"],
        description=seed["description"],
        next=seed["next"],
        maturity=seed["scope"],
        navigation="listed",
        view=View(component=seed["viewComponent"], export=seed["viewExport"]),
        evidence=Evidence(
            emits=(),
            ceiling=PENDING_ORACLE_CEILING,
            forbidden_claims=FORBIDDEN_CLAIM_KEYS,
            note=(
                "No independent physical or validation oracle is attached to this workspace. User-entered measured labels and reviewed source links are not independent validation; package export is a transport action, not scientific evidence. No oracle promotes the ceiling beyond screening-only."
            ),
        ),
        tests=TestRefs(
            oracle=Oracle(status="pending"),
            schema="python/test_module_contract_evidence.py",
            docs=f"docs/modules/{module_id}.md",
        ),
        migration_state="contracted",
        operations=_mode_operations(experimental=experimental),
        lifecycle=Lifecycle(background_work="none", resources=()),
        legacy_notes=(_COMMON_NOTES + (mode_notes,)),
        source_refs=(
            "python/module_registry_seed.json",
            "src/App.tsx::App",
            "src/components/EvidenceWorkspace.tsx::EvidenceWorkspace",
            "src/components/ResearchIntegrationPanel.tsx::ResearchIntegrationPanel",
            "src/types/research.ts",
            "src/store/useResearchStore.ts",
            "src/store/useMaterialSpecimenStore.ts::useMaterialSpecimenStore",
            "src/store/useLpbfEngineeringStore.ts::useLpbfEngineeringStore",
            "src/store/useLpbfBuildJobStore.ts::useLpbfBuildJobStore",
            "src/store/useLpbfBuildJobStore.ts::peekLpbfBuildJobKey",
        ),
        seed_derived=("label", "description", "next", "maturity"),
    )


def build_experimental_data_contract(seed: Mapping[str, str]) -> ModuleContract:
    """Build the contract for EvidenceWorkspace's experimental mode."""
    return _build_contract(seed, module_id="experimental-data", experimental=True)


def build_traceability_contract(seed: Mapping[str, str]) -> ModuleContract:
    """Build the contract for EvidenceWorkspace's traceability mode."""
    return _build_contract(seed, module_id="traceability", experimental=False)
