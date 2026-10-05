"""Bounded Module SDK contract for the local Materials Database view."""

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

_CATEGORIES = (
    "All",
    "Carbon Steel",
    "Alloy Steel",
    "Tool Steel",
    "Stainless Steel",
    "Aluminum Alloy",
    "Copper Alloy",
    "Titanium Alloy",
    "Nickel Superalloy",
    "Magnesium Alloy",
    "Refractory & Specialty",
    "Ceramic & Carbide",
)
_SORT_FIELDS = ("yield", "tensile", "specific_strength", "modulus", "density", "name")
_SORT_ORDERS = ("desc", "asc")
_TRANSFER_TARGETS = ("alloy-builder", "icme-motor", "3d-distortion-lab", "phase-diagram")

_BROWSER_REASON = (
    "MaterialsDatabaseView reads the bundled MATERIALS_DATABASE and mutates browser-local React/UI state; "
    "it has no server route or operation deadline."
)


def _local_operation(
    operation_id: str,
    *,
    fields: Tuple[InputField, ...] = (),
    undeclared: Tuple[str, ...] = (),
    outputs: Tuple[str, ...],
) -> Operation:
    return Operation(
        id=operation_id,
        route=None,
        method=None,
        authority=Authority(kind="browser-local", timeout_ms=None, exception_reason=_BROWSER_REASON),
        input=fields,
        undeclared_input=undeclared,
        output=OutputSchema(fields=outputs, status_key=None),
    )


DATABASE_OPERATIONS: Tuple[Operation, ...] = (
    _local_operation(
        "search-catalog",
        undeclared=("searchQuery",),
        outputs=("filteredMaterials", "visibleCount"),
    ),
    _local_operation(
        "filter-by-category",
        fields=(
            InputField(
                key="selectedCategory",
                label="Catalog category filter",
                unit=None,
                quantity_kind="local-catalog-filter",
                min=None,
                max=None,
                default="All",
                required=False,
                enum=_CATEGORIES,
                value_type="enum",
                note="These are the exact category pills in MaterialsDatabaseView; the field filters local rows only.",
            ),
        ),
        outputs=("filteredMaterials", "visibleCount"),
    ),
    _local_operation(
        "filter-by-min-yield-strength",
        fields=(
            InputField(
                key="minYield", label="Minimum yield-strength filter", unit="MPa",
                quantity_kind="local-catalog-filter", min=None, max=None, default=0,
                required=False, step=50,
                note="UI state default and slider step; slider attributes do not establish material validity bounds.",
            ),
        ),
        outputs=("filteredMaterials", "visibleCount"),
    ),
    _local_operation(
        "filter-by-min-modulus",
        fields=(
            InputField(
                key="minModulus", label="Minimum Young's-modulus filter", unit="GPa",
                quantity_kind="local-catalog-filter", min=None, max=None, default=40,
                required=False, step=10,
                note="UI state default and slider step; slider attributes do not establish material validity bounds.",
            ),
        ),
        outputs=("filteredMaterials", "visibleCount"),
    ),
    _local_operation(
        "filter-by-max-density",
        fields=(
            InputField(
                key="maxDensity", label="Maximum density filter", unit="g/cm^3",
                quantity_kind="local-catalog-filter", min=None, max=None, default=17.0,
                required=False, step=0.2,
                note="UI state default and slider step; slider attributes do not establish material validity bounds.",
            ),
        ),
        outputs=("filteredMaterials", "visibleCount"),
    ),
    _local_operation(
        "reset-property-range-filters",
        outputs=("minYield", "maxYield", "minModulus", "maxModulus", "minDensity", "maxDensity"),
    ),
    _local_operation(
        "switch-view-mode",
        fields=(
            InputField(
                key="activeTab", label="Database view mode", unit=None, quantity_kind="local-view-mode",
                min=None, max=None, default="split", enum=("split", "heatmap", "catalog"), value_type="enum",
            ),
        ),
        outputs=("activeView",),
    ),
    _local_operation(
        "sort-catalog",
        fields=(
            InputField(
                key="sortBy", label="Catalog sort key", unit=None, quantity_kind="local-sort-control",
                min=None, max=None, default="yield", enum=_SORT_FIELDS, value_type="enum",
            ),
            InputField(
                key="sortOrder", label="Catalog sort direction", unit=None, quantity_kind="local-sort-control",
                min=None, max=None, default="desc", enum=_SORT_ORDERS, value_type="enum",
            ),
        ),
        outputs=("sortedMaterials",),
    ),
    _local_operation(
        "select-material-record",
        undeclared=("material",),
        outputs=("selectedMaterial",),
    ),
    _local_operation(
        "toggle-comparison-record",
        undeclared=("material",),
        outputs=("compareList",),
    ),
    _local_operation(
        "copy-selected-record",
        outputs=("clipboardWrite", "copyFeedback"),
    ),
    _local_operation(
        "export-catalog-json",
        outputs=("downloadedJsonFile",),
    ),
    _local_operation(
        "open-transfer-picker",
        outputs=("transferPickerOpen",),
    ),
    _local_operation(
        "dispatch-material-to-module",
        fields=(
            InputField(
                key="targetId", label="Transfer destination", unit=None, quantity_kind="module-navigation-target",
                min=None, max=None, default="alloy-builder", enum=_TRANSFER_TARGETS, value_type="enum",
                note="Exact destination IDs rendered by SendToModuleModal for this transfer flow.",
            ),
        ),
        outputs=("pipelineMaterialEvent", "navigationTarget"),
    ),
)


def build_database_contract(seed: Mapping[str, str]) -> ModuleContract:
    """Build the source-bounded contract from the unchanged database seed row."""
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
                "No numerical or provenance oracle is declared for this catalog view. Displayed handbook-style "
                "properties and downstream composition-based profiles remain screening material; browsing or "
                "transferring a record does not establish source applicability, calibration, or physical validation."
            ),
        ),
        tests=TestRefs(
            oracle=Oracle(status="pending"),
            schema="python/test_module_contract_database.py",
            docs="docs/modules/database.md",
        ),
        migration_state="contracted",
        operations=DATABASE_OPERATIONS,
        lifecycle=Lifecycle(background_work="none", resources=()),
        legacy_notes=(
            "This module reads the statically imported MATERIALS_DATABASE array and performs filtering, sorting, "
            "selection, comparison, clipboard copy, JSON download, and transfer-payload preparation in the browser. "
            "Outputs name local view effects and transfer state; this is not an API request/response surface.",
            "MaterialSpec stores nominal scalar or min/max composition entries and property values, but has no "
            "per-property source citation, condition/temper, applicability, uncertainty, or confidence fields. The "
            "catalog header says 'Calibrated'; that UI label is not a record-level evidence link or validation proof.",
            "Selection and comparison callbacks receive MaterialSpec records from local catalog rows. Since the SDK "
            "scalar schema cannot describe that nested record/map, these actions record the actual 'material' input "
            "as undeclared rather than inventing a record-ID endpoint or object schema.",
            "createPipelinePayloadFromMaterialSpec preserves originalComposition and marks composition as nominal "
            "or range-midpoint, while normalizing composition and deriving kinetic, hardness, and XRD profiles. "
            "The downstream bridge states that source property values/confidence are not promoted and derived "
            "properties remain estimates. Missing Poisson ratio also receives a code fallback in the pipeline; "
            "that fallback is software behavior, not a database measurement.",
            "The transfer picker presents Alloy Builder, ICME, LPBF wizard, and Phase Diagram as destinations. "
            "Dispatch stores the payload through the browser pipeline utility, then navigates after a 350 ms "
            "setTimeout. This is a local cross-module handoff, not provider/server execution or LPBF acceptance.",
            "The comparison list initially contains catalog entries at indexes 0 and 5; clicking toggles membership "
            "and additions stop at four entries. The category and view-mode enums below describe the actual visible "
            "controls, not material-property validity classes.",
            "Copy feedback clears after a 2000 ms setTimeout. Catalog JSON export creates an object URL, clicks a "
            "download link, and revokes the URL in the same handler. Lifecycle has no timeout/object-URL resource "
            "kind; these are noted as short UI effects rather than invented lifecycle resources.",
            "No fetch, worker, solver, scheduled job, or source download is initiated by this view. The nested "
            "comparison and transfer dialogs are UI children, not background work.",
        ),
        source_refs=(
            "src/components/MaterialsDatabaseView.tsx:36-111#filteredMaterials",
            "src/components/MaterialsDatabaseView.tsx:122-143#handleCopySpec",
            "src/components/MaterialsDatabaseView.tsx:60-72#categories",
            "src/components/MaterialsDatabaseView.tsx:236-338#Property Sliders",
            "src/components/MaterialsDatabaseView.tsx:250-264#Sort:",
            "src/components/MaterialsDatabaseView.tsx:150-150#Calibrated chemical compositions",
            "src/components/MaterialsDatabaseView.tsx:56-56#compareList",
            "src/components/MaterialsDatabaseView.tsx:113-118#compareList.length < 4",
            "src/components/MaterialsDatabaseView.tsx:373-377#MaterialsPropertyHeatmapD3",
            "src/components/MaterialsDatabaseView.tsx:402-402#setSelectedMaterial(mat)",
            "src/components/MaterialsDatabaseView.tsx:483-483#createPipelinePayloadFromMaterialSpec",
            "src/types.ts:32-63#MaterialSpec",
            "src/data/materialsDatabase.ts:1-28#MATERIALS_DATABASE",
            "src/utils/materialDataPipeline.ts:666-715#createPipelinePayloadFromMaterialSpec",
            "src/utils/materialDataPipeline.ts:718-729#setActivePipelineMaterial",
            "src/components/SendToModuleButton.tsx:6-12#SendToModuleButtonProps",
            "src/components/SendToModuleModal.tsx:47-62#handleDispatch",
            "src/components/SendToModuleModal.tsx:63-132#targets",
            "src/utils/materialDataPipeline.ts:6-11#ModuleTargetId",
            "src/services/materialContextBridge.ts:47-70#applyIdentity",
            "src/services/materialContextBridge.ts:91-91#subscribeToPipelineMaterial",
        ),
        seed_derived=("label", "description", "next", "maturity"),
    )
