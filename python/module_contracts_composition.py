"""Bounded Module SDK contract for AlloyBuilder's browser-local editor."""

from typing import Mapping

from module_contract import (
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


CONTRACT_VERSION = "0.1.0"


def build_composition_contract(seed: Mapping[str, str]) -> ModuleContract:
    """Build a conservative contract from the unchanged alloy-builder seed row.

    This is an operation-level inventory, not a unified request schema: the React
    view calls individual Zustand actions. ``percentage`` is the only flat numeric
    edit represented by InputField; the element symbol is recorded as undeclared
    because Module SDK's scalar kinds cannot represent the free-text key. The
    dynamic composition map and other controls are described in legacy_notes.
    """
    operation = Operation(
        id="specimen-editor",
        route=None,
        method=None,
        authority=Authority(
            kind="browser-local",
            # Contracted browser-local entries currently require a positive timeout.
            # This minimum schema sentinel is not enforced by the synchronous UI/store.
            timeout_ms=1,
            exception_reason=(
                "CompositionEditor mutates the browser Zustand store directly; no server route or "
                "runtime deadline exists. timeoutMs=1 is only the positive value required by the "
                "contract schema, not an execution guarantee."
            ),
        ),
        input=(
            InputField(
                key="percentage",
                label="Element content",
                unit="percent in the active specimen unit (wt.% or at.%)",
                quantity_kind="element-composition-percentage",
                min=None,
                max=None,
                step=0.1,
                default=0.0,
                required=False,
                note=(
                    "Optional here because specimen-editor groups distinct UI actions; percentage is "
                    "supplied for each setElement edit. AlloyBuilder renders a 0..100 number input "
                    "with step 0.1, but the store does not enforce those HTML hints. Empty input "
                    "becomes 0, and setElement removes values <= 0."
                ),
            ),
        ),
        undeclared_input=("element",),
        # The browser view observes this shared state after its local mutations; it is not
        # a returned solver result or evidence-bearing output.
        output=OutputSchema(fields=("activeMaterialSpecimen",), status_key=None),
    )

    return ModuleContract(
        id=seed["id"],
        version=CONTRACT_VERSION,
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
                "No oracle is present. This browser-local editor and its composition-based KPI display "
                "are screening-only; the UI labels its estimate unvalidated. A software contract or "
                "passing software checks does not establish physical validation."
            ),
        ),
        tests=TestRefs(
            oracle=Oracle(status="pending"),
            schema="python/test_module_contract_composition.py",
            docs="docs/modules/alloy-builder.md",
        ),
        migration_state="contracted",
        operations=(operation,),
        lifecycle=Lifecycle(background_work="none"),
        legacy_notes=(
            "Operation-level only: AlloyBuilder calls separate browser Zustand actions; it does not "
            "submit a unified operation payload. The active specimen composition is a dynamic "
            "element-symbol-to-number map, which the SDK InputField scalar schema cannot describe; "
            "no element set, nested map schema, or composition-balance check is fabricated.",
            "Other current controls are specimen name and standard designation free text, material "
            "category and manufacturing-route selects, quick presets, normalize-to-100%, remove-element, "
            "reset, and save-snapshot actions. They are directly wired to useMaterialStore and are "
            "not claimed as fields of one request.",
            "The category choices come from MATERIAL_CATEGORIES plus the active category when absent; "
            "route choices come from MANUFACTURING_ROUTES plus the active route when absent. Neither "
            "select is represented as a fixed enum here.",
            "The store persists browser state and synchronizes composition updates to the shared material "
            "pipeline. The editor has no server request lifecycle or background job; its visible KPI "
            "panel says 'Composition-based estimate; unvalidated.'",
            "activeMaterialSpecimen in output.fields denotes the post-action browser store state observed "
            "by the view, not a response payload or oracle result.",
        ),
        source_refs=(
            "src/components/AlloyBuilder.tsx:38-80#activeMaterialSpecimen",
            "src/components/AlloyBuilder.tsx:33-37#MANUFACTURING_ROUTES",
            "src/components/AlloyBuilder.tsx:54-58#categoryOptions",
            "src/components/AlloyBuilder.tsx:183-229#Specimen Name",
            "src/components/AlloyBuilder.tsx:263-360#Auto-Normalize to 100%",
            "src/components/AlloyBuilder.tsx:422#Composition-based estimate; unvalidated",
            "src/store/useMaterialStore.ts:94-116#Core Actions",
            "src/store/useMaterialStore.ts:716-861#updateComposition",
            "src/store/useMaterialStore.ts:863-940#updateName",
            "src/store/useMaterialStore.ts:707#persist(",
        ),
        seed_derived=("label", "description", "next", "maturity"),
    )
