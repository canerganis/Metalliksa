"""Source-bounded contract for the measurement comparison view.

This helper is intentionally not registered in module_registry.py. The SDK
contract currently requires a timeout for every routed contracted operation,
but the source-measurements fetch has no deadline. Calling this module
``contracted`` would therefore require inventing lifecycle behavior.
"""
from __future__ import annotations

from typing import Mapping

from module_contract import (
    FORBIDDEN_CLAIM_KEYS,
    OWNER_UNASSIGNED,
    Authority,
    Evidence,
    Lifecycle,
    ModuleContract,
    Operation,
    Oracle,
    OutputSchema,
    TestRefs,
    View,
)


MEASUREMENT_ROUTE = "/api/lpbf/sources/cmu-ti64-meltpool-v1/measurements"


def build_experimental_validation_contract(seed: Mapping[str, str]) -> ModuleContract:
    """Describe the current fixed-dataset view without asserting validation."""
    if seed["id"] != "experimental-validation":
        raise ValueError("Experimental Validation preserves its canonical module identity")
    return ModuleContract(
        id=seed["id"], version="0.1.0", owner=OWNER_UNASSIGNED,
        workspace=seed["workspace"], label=seed["label"],
        description=seed["description"], next=seed["next"], maturity=seed["scope"],
        navigation="listed", view=View(component=seed["viewComponent"], export=seed["viewExport"]),
        operations=(
            Operation(
                id="load-cmu-ti64-measurements", route=MEASUREMENT_ROUTE, method="GET",
                authority=Authority(kind="node-provider"),
                output=OutputSchema(fields=("datasetId", "data", "error"), status_key=None),
            ),
            Operation(
                id="render-measurement-comparison", route=None, method=None,
                authority=Authority(
                    kind="browser-local",
                    exception_reason=(
                        "ExperimentalValidationLab filters loaded rows and renders Recharts series plus "
                        "conditional dots from the existing Engineering job in Zustand."
                    ),
                ),
                undeclared_input=("measurementData", "job"),
                output=OutputSchema(
                    fields=("widthSeries", "depthSeries", "simulationReferenceDots", "loadingMessage", "errorMessage"),
                    status_key=None,
                ),
            ),
        ),
        evidence=Evidence(
            emits=(), ceiling="screening-only", forbidden_claims=FORBIDDEN_CLAIM_KEYS,
            note=(
                "The view juxtaposes source measurements and a stored simulation result; it computes no residual, "
                "matching score, uncertainty-aware comparison, or independent validation. No independent oracle "
                "is declared. Rendering measured rows does not validate a solver or establish an applicability domain."
            ),
        ),
        tests=TestRefs(
            oracle=Oracle(status="pending"),
            schema="python/test_module_contract_experimental_validation.py",
            docs="docs/MODULE_EVIDENCE_INVENTORY.md",
        ),
        # The SDK model requires timeoutMs on routed contracted operations. The
        # actual GET only passes an AbortSignal for unmount cancellation; it has
        # no deadline. Keep this module legacy until the contract can state that
        # lifecycle truthfully (or the product adds a real deadline).
        migration_state="legacy",
        lifecycle=Lifecycle(background_work="none", resources=("fetch",)),
        legacy_notes=(
            "The view has no user input selectors. It always requests the fixed dataset id "
            "cmu-ti64-meltpool-v1 and locally keeps only rows whose power_W is exactly 370; the dataset id is "
            "embedded in the route, not a user-selectable enum. The Engineering job is read from the existing "
            "Zustand store, not submitted by this view.",
            "GET returns datasetId and data on success; data rows contain slice, orientation, power_W, "
            "velocity_mms, width_um, depth_um, and cap_um. The component plots width_um and depth_um against "
            "velocity_mms; cap_um, slice, and orientation are not displayed. The endpoint response has no "
            "provenance, revision, citation, source hash, or evidenceStatus field. The separate source archive "
            "catalog/current/verify APIs are not called by this view, so do not claim that the plotted response "
            "shows current source verification or citation provenance.",
            "The source route requires an imported current archive revision for this dataset and returns 404 "
            "when it is absent; service/integrity failures can return 503. Other successfully resolved dataset "
            "ids return an empty data array, though this view uses only the fixed CMU id. The client converts "
            "non-OK responses to a generic load error and renders that error without a retry control.",
            "A successful response with no 370 W rows leaves data empty. The component uses data.length === 0 "
            "as its loading branch and has no separate empty/unavailable state, so an empty-but-successful "
            "response displays the loading message indefinitely.",
            "The request starts on mount with cache=no-store and an AbortController; cleanup aborts on unmount. "
            "No request deadline or retry is implemented. The SDK's routed contracted-operation schema requires "
            "a timeoutMs, so this helper remains migrationState=legacy instead of inventing one.",
            "The overlay reads job.result.metrics and job.result.settings from shared state. It draws width/depth "
            "ReferenceDots only when both objects exist and abs(settings.power_W - 370) < 5. It does not check "
            "material identity, exact process-condition correspondence, result freshness/signature, or compare "
            "the simulation velocity against individual measurement records. The dots are a visual juxtaposition, "
            "not calculated agreement or validation.",
            "The component's title and copy describe a comparison; the existence of measured data is not an "
            "independent validation oracle for this simulation. Oracle state remains pending and the evidence "
            "ceiling remains screening-only.",
        ),
        source_refs=(
            "python/module_registry_seed.json",
            "src/App.tsx",
            "src/components/ExperimentalValidationLab.tsx",
            "src/services/lpbfSourceService.ts",
            "routes/lpbfSources.ts",
            "server/lpbfSourceArchiveService.ts",
            "src/store/useLpbfEngineeringStore.ts",
            "src/services/lpbfSimulationService.ts",
            "tests/lpbf-source-api.test.ts",
            "tests/lpbf-experimental-evidence.test.tsx",
            "tests/lpbf-phase4-e2e.test.ts",
            "docs/MODULE_EVIDENCE_INVENTORY.md",
        ),
        seed_derived=("label", "description", "next", "maturity"),
    )
