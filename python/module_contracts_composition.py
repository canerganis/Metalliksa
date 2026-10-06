"""Bounded Module SDK contract for AlloyBuilder's browser-local editor."""

from typing import Mapping, Tuple

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

_BROWSER_LOCAL_REASON = (
    "AlloyBuilder calls browser Zustand actions directly; this operation has no server route "
    "or execution deadline."
)


def _browser_operation(
    operation_id: str,
    *,
    fields: Tuple[InputField, ...] = (),
    undeclared: Tuple[str, ...] = (),
    output_field: str = "activeMaterialSpecimen",
) -> Operation:
    return Operation(
        id=operation_id,
        route=None,
        method=None,
        authority=Authority(
            kind="browser-local",
            timeout_ms=None,
            exception_reason=_BROWSER_LOCAL_REASON,
        ),
        input=fields,
        undeclared_input=undeclared,
        output=OutputSchema(fields=(output_field,), status_key=None),
    )


COMPOSITION_OPERATIONS: Tuple[Operation, ...] = (
        _browser_operation("update-specimen-name", undeclared=("name",)),
        _browser_operation("update-category", undeclared=("category",)),
        _browser_operation("update-standard-designation", undeclared=("standardDesignation",)),
        _browser_operation("update-manufacturing-route", undeclared=("manufacturingRoute",)),
        _browser_operation("add-element", undeclared=("element",)),
        _browser_operation(
            "set-element-content",
            fields=(
                InputField(
                    key="percentage",
                    label="Element content",
                    unit="%",
                    quantity_kind="element-composition-percentage",
                    min=0.0,
                    max=100.0,
                    step=0.1,
                    default=0.0,
                    required=True,
                    note=(
                        "The active input displays the current stored value; schema default 0.0 records "
                        "the clear-input action, not an initial field value. Clearing the HTML number "
                        "field maps to 0; setElement removes exactly zero. Finite values in 0..100 "
                        "are store-enforced input bounds, not a physical applicability domain; percentages "
                        "retain the active specimen's wt.% or at.% unit. The 0.1 step is a UI hint."
                    ),
                ),
            ),
            undeclared=("element",),
        ),
        _browser_operation("remove-element", undeclared=("element",)),
        _browser_operation("normalize-composition"),
        _browser_operation("load-preset", undeclared=("presetId",)),
        _browser_operation("reset-to-default"),
)


def build_composition_contract(seed: Mapping[str, str]) -> ModuleContract:
    """Build an action-scoped contract from the unchanged alloy-builder seed row.

    Each Operation names one user-driven browser store action. The SDK field vocabulary
    cannot type free-text values or the dynamic element-to-number composition map, so
    those exact action arguments are recorded in ``undeclared_input`` rather than
    represented by a fabricated object or enum schema.
    """

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
                "No oracle is present. The editor computes only a rule-of-mixtures density from the shown "
                "composition; liquidus/solidus and strength are displayed as unavailable. Software contract "
                "checks do not establish physical validation."
            ),
        ),
        tests=TestRefs(
            oracle=Oracle(status="pending"),
            schema="python/test_module_contract_composition.py",
            docs="docs/modules/alloy-builder.md",
        ),
        migration_state="contracted",
        operations=COMPOSITION_OPERATIONS,
        lifecycle=Lifecycle(background_work="none", resources=()),
        legacy_notes=(
            "Composition remains browser-local state: MaterialSpecimen.composition is an element-symbol-to-number "
            "map, not a request object. Each operation scopes one visible store action; the map is not encoded "
            "as a fabricated flat or nested InputField schema. UI controls preserve dynamic state between actions.",
            "String-valued arguments are recorded by their actual key in undeclaredInput because the SDK value "
            "types do not include strings. Category and route choices can include the active value at runtime, "
            "so no closed enum is inferred.",
            "Add Element calls setElement with the selected symbol and a fixed 1.0; the editable number and slider "
            "call setElement with the current symbol and value. The numeric control has min=0/max=100/step=0.1; "
            "the slider max is 100 for the active base metal and 35 otherwise. The store rejects non-finite, "
            "negative and over-100 content before modifying state or deriving estimates.",
            "normalizeComposition is a separate click action; invalid entries or a non-finite/non-positive "
            "total are rejected before scaling by 100/total. JSON import validates composition before "
            "derivation and rejects exponent overflow; invalid maps leave both active specimen aliases unchanged.",
            "Preset buttons call loadPreset(key), which sets the preset's catalogue designation; editing the "
            "composition away from that preset clears it. Reset calls resetToDefault. The editor has no "
            "snapshot button: savedSpecimens had no view, so the Save action was removed from the UI.",
            "The component destructures updateComposition but does not call it directly; edits currently "
            "use setElement/removeElement and the separate metadata setters. Weight-percent updates also "
            "publish an active pipeline payload; atomic-percent updates return before that pipeline sync.",
            "Name/category/designation/route, composition edits, preset, reset and normalize are separate "
            "browser-local actions; the component does not submit one combined specimen-editor request.",
            "The KPI panel shows the inverse rule-of-mixtures density (unavailable for at.% or an element "
            "without a tabulated density), states liquidus/solidus/yield/UTS as unavailable (no validated "
            "composition-to-property model), and shows the user's shared LPBF process settings. No physical "
            "oracle is present.",
        ),
        source_refs=(
            "src/components/AlloyBuilder.tsx:31-61#activeMaterialSpecimen",
            "src/components/AlloyBuilder.tsx:110-115#resetToDefault",
            "src/components/AlloyBuilder.tsx:136-185#Specimen Name",
            "src/components/AlloyBuilder.tsx:46-47#categoryOptions",
            "src/components/AlloyBuilder.tsx:195-210#loadPreset(key)",
            "src/components/AlloyBuilder.tsx:215-245#Auto-Normalize to 100%",
            "src/components/AlloyBuilder.tsx:55-62#ruleOfMixturesDensity",
            "src/components/AlloyBuilder.tsx:340-346#COMPOSITION_PROPERTY_UNAVAILABLE_NOTE",
            "src/utils/compositionPropertyAvailability.ts::ruleOfMixturesDensity",
            "src/store/useMaterialStore.ts:27-89#composition: Record<string, number>",
            "src/store/useMaterialStore.ts:94-119#Core Actions",
            "src/store/useMaterialStore.ts::isValidCompositionInput",
            "src/store/useMaterialStore.ts",
            "tests/material-composition-validation.test.ts",
            "src/utils/materialDataPipeline.ts:718-729#setActivePipelineMaterial",
        ),
        seed_derived=("label", "description", "next", "maturity"),
    )
