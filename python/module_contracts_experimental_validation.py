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
                output=OutputSchema(fields=("datasetId", "scope", "data", "error"), status_key=None),
            ),
            Operation(
                id="render-measurement-comparison", route=None, method=None,
                authority=Authority(
                    kind="browser-local",
                    exception_reason=(
                        "ExperimentalValidationLab aggregates loaded rows per scan velocity (mean, sample SD, n), "
                        "gates the overlay on material, power and beam diameter, and renders Recharts series, "
                        "conditional dots and a width residual from the existing Engineering job in Zustand."
                    ),
                ),
                undeclared_input=("measurementData", "job"),
                output=OutputSchema(
                    fields=(
                        "widthSeries", "remeltDepthSeries", "perVelocityAggregates", "overlayGate",
                        "simulationReferenceDots", "widthResidual", "remeltDepthContext",
                        "unresolvedScope", "loadingMessage", "emptyMessage", "errorMessage",
                    ),
                    status_key=None,
                ),
            ),
        ),
        evidence=Evidence(
            emits=(), ceiling="screening-only", forbidden_claims=FORBIDDEN_CLAIM_KEYS,
            note=(
                "The view juxtaposes source measurements and a stored simulation result. It computes per-velocity "
                "mean and sample SD of the measured rows and one width residual (simulated minus the measured mean "
                "at an exactly matching velocity, no interpolation). The measured depth is remelt depth with the "
                "cap excluded, not the simulated melt-pool depth, so no depth residual is computed. It computes no "
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
            "cmu-ti64-meltpool-v1; the dataset id is embedded in the route, not a user-selectable enum. The "
            "client applies no power filter: the heading text states the distinct powers present in the loaded "
            "rows (all 370 W in the pinned table). The Engineering job is read from the existing Zustand store, "
            "not submitted by this view.",
            "GET returns datasetId, scope and data on success. scope is the server constant CMU_MT_SCOPE "
            "(server/cmuMeasurements.ts): file raw/MTMeasurements.csv, trackScope multi-track-powder-entrained, "
            "the reason that file is used (STMeasurements.csv has no power column), and an unresolved list "
            "(beam profile/diameter for this CSV, layer thickness, powder lot, thermal boundary conditions), "
            "which the view renders. Data rows contain slice, orientation, power_W, velocity_mms, width_um, "
            "depth_um, and cap_um; the CSV Depth column is remelt depth with the cap excluded. The endpoint "
            "response has no revision, citation, source hash, or evidenceStatus field. The separate source "
            "archive catalog/current/verify APIs are not called by this view, so do not claim that the plotted "
            "response shows current source verification or citation provenance.",
            "The source route requires an imported current archive revision for this dataset and returns 404 "
            "when it is absent; service/integrity failures can return 503. Other successfully resolved dataset "
            "ids return an empty data array, though this view uses only the fixed CMU id. The client converts "
            "non-OK responses to a generic load error and renders that error without a retry control.",
            "A successful response with zero rows shows an explicit empty message (the view tracks a loaded flag "
            "separately from data.length) rather than the loading message.",
            "The request starts on mount with cache=no-store and an AbortController; cleanup aborts on unmount. "
            "No request deadline or retry is implemented. The SDK's routed contracted-operation schema requires "
            "a timeoutMs, so this helper remains migrationState=legacy instead of inventing one.",
            "The overlay reads job.result.metrics and job.result.settings from shared state and draws width/depth "
            "ReferenceDots only when src/utils/experimentalValidation.ts overlayGate passes: material is "
            "Ti-6Al-4V, power within 5 W of 370 W, and beam diameter within 5 um of 100 um (the manufacturer-"
            "reported spot of the cited fatigue-coupon build, not stated in the CSV). A failed gate lists its "
            "reasons and draws nothing. The residual is simulated minus the measured mean at an exactly "
            "matching scan velocity (no interpolation); it is unavailable, with a reason, when no measurement "
            "exists at that velocity. Only width carries a residual: the depth row shows both values for context "
            "and states that the quantity definitions differ. It does not check result freshness/signature. The "
            "dots and residual are a juxtaposition, not calculated agreement or validation.",
            "The component's title and copy describe a comparison; the existence of measured data is not an "
            "independent validation oracle for this simulation. Oracle state remains pending and the evidence "
            "ceiling remains screening-only.",
        ),
        source_refs=(
            "python/module_registry_seed.json",
            "src/App.tsx",
            "src/components/ExperimentalValidationLab.tsx",
            "src/utils/experimentalValidation.ts",
            "server/cmuMeasurements.ts",
            "src/services/lpbfSourceService.ts",
            "routes/lpbfSources.ts",
            "server/lpbfSourceArchiveService.ts",
            "src/store/useLpbfEngineeringStore.ts",
            "src/services/lpbfSimulationService.ts",
            "tests/lpbf-source-api.test.ts",
            "tests/lpbf-experimental-evidence.test.tsx",
            "tests/lpbf-experimental-validation-logic.test.ts",
            "tests/lpbf-phase4-e2e.test.ts",
            "docs/MODULE_EVIDENCE_INVENTORY.md",
        ),
        seed_derived=("label", "description", "next", "maturity"),
    )
