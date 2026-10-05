"""Source-bounded Module SDK contracts for the LPBF optimizer and solidification views."""

from typing import Mapping

from module_contract import (
    FORBIDDEN_CLAIM_KEYS,
    OWNER_UNASSIGNED,
    PENDING_ORACLE_CEILING,
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


CONTRACT_VERSION = "0.1.0"


def _contract(seed: Mapping[str, str], operation: Operation, notes, sources) -> ModuleContract:
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
                "Oracle pending. This contract inventories software requests and screening outputs only; "
                "it asserts no validated process recommendation or physical applicability."
            ),
        ),
        tests=TestRefs(
            oracle=Oracle(status="pending"),
            schema="python/test_module_contract_lpbf_secondary.py",
            docs=f"docs/modules/{seed['id']}.md",
        ),
        migration_state="contracted",
        operations=(operation,),
        lifecycle=Lifecycle(background_work="none", resources=("fetch",)),
        legacy_notes=tuple(notes),
        source_refs=tuple(sources),
        seed_derived=("label", "description", "next", "maturity"),
    )


def build_lpbf_optimizer_contract(seed: Mapping[str, str]) -> ModuleContract:
    """Describe the visible optimizer request without flattening its nested bounds map."""
    if seed["id"] != "lpbf-optimizer":
        raise ValueError("LPBF optimizer contract must preserve the lpbf-optimizer seed identity")
    operation = Operation(
        id="bayesian-optimize",
        method="POST",
        route="/api/python/lpbf-bayesian-optimize",
        authority=Authority(
            kind="python-ipc",
            script="python/lpbf_bayesian_optimizer.py",
            timeout_ms=120000,
            warm=False,
        ),
        # paramBounds is a map of four two-number intervals, not four flat request keys.
        # String alloyId is also outside InputField's scalar vocabulary.
        undeclared_input=("alloyId", "paramBounds", "nIterations", "nWarmup", "seed"),
        output=OutputSchema(
            fields=("success", "alloyId", "bestParams", "bestScore", "iterations", "converged", "elapsedMs", "nIterations"),
            status_key=None,
        ),
    )
    return _contract(
        seed,
        operation,
        notes=(
            "The view submits only on Run Optimization. Its body is alloyId from the active specimen, nested "
            "paramBounds for laserPower_W (W), scanSpeed_mms (mm/s), hatch_um (µm), layer_um (µm), "
            "nIterations, nWarmup and seed=42. Initial UI intervals are [100,500], [200,2000], [60,200] "
            "and [20,80]; number controls have no HTML min/max/step and the authority does not validate interval "
            "ordering or positive widths. These inputs remain undeclared rather than inventing a nested schema.",
            "The entry point defaults missing alloyId to in718, bounds to the script constants, iterations to 20, "
            "warmup to 5 and seed to 42; nIterations is capped above at 30 but not given a lower bound. "
            "An unresolved alloy id silently resolves to in718. The objective combines a screening build-verdict "
            "score with normalized scan-rate productivity; fixed beam diameter 80 µm, preheat 80 °C and "
            "1064 nm are used internally. bestScore and the UI's 'best' candidate are heuristic software outputs, "
            "not a qualified process recommendation, experimental result or validated optimum.",
            "The script imports numpy and scipy at module load and has no dependency-unavailable envelope or "
            "fallback. Dispatch/IPC errors surface through the route/service failure path. The request has a "
            "120000 ms Python-IPC timeout and is not warm. The browser holds request/result/loading/error state; "
            "no interval, background loop or persisted worker resource is started by this view.",
        ),
        sources=(
            "src/components/LpbfBayesianOptimizerLab.tsx::LpbfBayesianOptimizerLab",
            "src/services/pythonComputationService.ts:647-655#lpbf-bayesian-optimize",
            "routes/physics.ts:83-84#120000",
            "python/lpbf_bayesian_optimizer.py::run_bayesian_optimization",
            "python/lpbf_bayesian_optimizer.py:151-174#nIterations",
        ),
    )


def build_solidification_microstructure_contract(seed: Mapping[str, str]) -> ModuleContract:
    """Describe the view's worker request and its explicit unavailable/screening outcomes."""
    if seed["id"] != "solidification-microstructure":
        raise ValueError("Solidification contract must preserve the solidification-microstructure seed identity")
    operation = Operation(
        id="solidification-microstructure",
        method="POST",
        route="/api/python/lpbf-solidification-microstructure",
        authority=Authority(
            kind="lpbf-worker",
            worker_method="solidification-microstructure",
            timeout_ms=20000,
        ),
        # The view sends one nested params object; no SDK map type exists to describe it truthfully.
        undeclared_input=("params",),
        output=OutputSchema(
            fields=("status", "source", "reason", "modelId", "gradientSource", "usedFieldMap",
                    "heatSourceModel", "materialName", "inputs", "absorptivity", "materialEvidence",
                    "morphologyBands_G_over_R", "scope", "disclaimer", "G_K_m", "R_m_s",
                    "coolingRate_K_s", "PDAS_um", "SDAS_um", "morphology"),
            status_key=None,
            transport_values=(("status", ("available", "unavailable", "screening-fallback", "degenerate-floor")),),
        ),
    )
    return _contract(
        seed,
        operation,
        notes=(
            "Compute is user-triggered; each setting change clears the displayed result. The view sends a nested "
            "params object with Python-authority materialName and power_W (W), speed_mm_s (mm/s), hatch_um (µm), "
            "layerThickness_um (µm), beamDiameter_um (µm), preheat_C (°C), heatSource. Visible presets are "
            "Inconel 718, Ti-6Al-4V, AlSi10Mg and 316L SS; defaults are 285 W, 960 mm/s, 110 µm hatch, "
            "40 µm layer, 80 µm beam, 80 °C and Rosenthal. Visible input min/max/step are UI controls; backend "
            "requires finite values, positive power/speed/beam/layer/hatch, and preheat above absolute zero and "
            "below known liquidus. Missing material or inputs and unsupported/unusable physics return unavailable; "
            "there is no substitute alloy or numeric fallback.",
            "The current view does not send cfdResult or material properties. Worker RPC therefore invokes "
            "compute_screening_field_microstructure, which calls lpbf_thermal_solver and projects its "
            "solidificationKinetics. available, screening-fallback and degenerate-floor are source/model result "
            "labels; unavailable has null numeric fields. Provenance includes source/modelId/gradientSource, "
            "material evidence and disclaimer where returned. They are screening estimates, not in-situ tracking "
            "or experimental validation. The separate legacy CFD RPC branch is not reachable from this view.",
            "The browser performs one fetch per explicit compute and maintains result/error/loading state; it starts "
            "no interval or background work. The LPBF worker is a server-managed child reused across requests; "
            "request timeout is 20000 ms (startup timeout is separately 60000 ms). Worker unavailability maps "
            "to HTTP 503 with retry hint, validation refusal to 422, and other route errors to 400. This module "
            "contract records availability as transport values only and emits no evidence status.",
        ),
        sources=(
            "src/components/SolidificationMicrostructureLab.tsx::SolidificationMicrostructureLab",
            "src/components/SolidificationMicrostructureLab.tsx::solidificationRequest",
            "src/services/pythonComputationService.ts:659-676#lpbf-solidification-microstructure",
            "routes/lpbfSimulation.ts:22-38#solidification-microstructure",
            "server/lpbfWorkerBridge.ts:58#requestTimeoutMs ?? 20000",
            "python/lpbf_worker_rpc.py::_rpc_solidification_microstructure",
            "python/lpbf_solidification_microstructure.py::compute_screening_field_microstructure",
            "python/lpbf_solidification_microstructure.py:267-284#status",
        ),
    )
