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
    FORBIDDEN_CLAIM_KEYS, GPU_MODES, HTTP_METHODS, LIFECYCLE_RESOURCES, MATURITY, MIGRATION_STATES, NAVIGATION,
    ORACLE_STATES, OWNER_UNASSIGNED, PENDING_ORACLE_CEILING, RUN_STATES, SEED_TEXT_FIELDS, TODO_MARKER, VALUE_TYPES,
    WORKSPACES,
    Authority, Evidence, InputField, Lifecycle, ModuleContract, Operation, Oracle, OutputSchema, TestRefs, View,
)
from module_contracts_dataset_view import build_dataset_view_contract
from module_contracts_calibration_scorecard import build_calibration_scorecard_contract
from module_contracts_eds import build_eds_contract
from module_contracts_composition import build_composition_contract
from module_contracts_elasticity import build_elasticity_contract
from module_contracts_database import build_database_contract
from module_contracts_calphad import build_calphad_contract
from module_contracts_evidence import build_experimental_data_contract, build_traceability_contract

PYTHON_DIR = Path(__file__).resolve().parent
REPO_ROOT = PYTHON_DIR.parent
SEED_PATH = PYTHON_DIR / "module_registry_seed.json"
APP_TSX = REPO_ROOT / "src" / "App.tsx"
GENERATED_JSON = REPO_ROOT / "src" / "generated" / "moduleRegistry.json"
GENERATED_TS = REPO_ROOT / "src" / "generated" / "moduleRegistry.ts"
# Small eager slice (navigation + badge data). The full GENERATED_TS is imported lazily by the
# app (src/modules/registry.ts loadModuleContractDetails) to keep the entry chunk small.
GENERATED_CORE_TS = REPO_ROOT / "src" / "generated" / "moduleRegistryCore.ts"
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


def _op(op_id: str, method, route, authority: Authority) -> Operation:
    return Operation(id=op_id, method=method, route=route, authority=authority)


def _local(op_id: str, reason: str) -> Operation:
    return Operation(id=op_id, route=None, authority=_browser(reason))


def _worker_op(method: str) -> Operation:
    return _op(method, "POST", f"/api/python/lpbf-{method}", _worker(method))


_THERMAL_SOLVER = _op("lpbf-thermal-solver", "POST", "/api/python/lpbf-thermal-solver",
                      _py("lpbf_thermal_solver", _PHYSICS_TIMEOUT_MS, warm=True))
_AI_CONSULT = _op("ai-consult", "POST", "/api/consult", _NODE)
_EVIDENCE_READS_ONLY = ("EvidenceWorkspace only reads useLpbfBuildJobStore (lastKey, job) and "
                        "useLpbfEngineeringStore; it dispatches no server request (build jobs are "
                        "submitted from 3d-distortion-lab), so no operation is bound.")

LEGACY_OPERATIONS: Dict[str, Tuple[Operation, ...]] = {
    "3d-distortion-lab": (
        _op("lpbf-capabilities", "GET", "/api/lpbf/capabilities", _worker("capabilities")),
        _op("lpbf-estimate", "POST", "/api/lpbf/estimate", _worker("estimate")),
        _op("lpbf-job-submit", "POST", "/api/lpbf/jobs", _worker("submit")),
        _op("lpbf-job-repeat", "POST", "/api/lpbf/jobs/repeat", _worker("submit-repeat")),
        _op("lpbf-job-status", "GET", "/api/lpbf/jobs/:id", _worker("get")),
        _op("lpbf-job-cancel", "DELETE", "/api/lpbf/jobs/:id", _worker("cancel")),
        _op("lpbf-job-artifact", "GET", "/api/lpbf/jobs/:id/artifacts/:name", _worker("artifact")),
        _THERMAL_SOLVER,
        _op("lpbf-calibrated-meltpool", "POST", "/api/python/lpbf-calibrated-meltpool",
            _py("lpbf_calibrated_meltpool", _PHYSICS_TIMEOUT_MS, warm=False)),
        _op("stl-slicer-build-time", "POST", "/api/python/stl-slicer-build-time",
            _py("stl_slicer_build_time_solver", _PHYSICS_TIMEOUT_MS, warm=True)),
        _op("lpbf-source-catalog", "GET", "/api/lpbf/sources", _NODE),
        _op("lpbf-run-archive", "GET", "/api/lpbf/runs", _NODE),
    ),
    "lpbf-optimizer": (
        _op("bayesian-optimize", "POST", "/api/python/lpbf-bayesian-optimize",
            _py("lpbf_bayesian_optimizer", 120000, warm=False)),
        _op("process-window", "POST", "/api/python/lpbf-process-window",
            _py("lpbf_process_window", 60000, warm=False)),
    ),
    "solidification-microstructure": (_worker_op("solidification-microstructure"),),
    "experimental-validation": (
        _op("lpbf-source-measurements", "GET", "/api/lpbf/sources/:datasetId/measurements", _NODE),
    ),
    # The thermal-solver call came from the InverseAlloyStudio subtree (LaserMeltPoolThermalMap), deleted 2026-10-04.
    "electrochem-suite": (
        _op("pourbaix-diagram", "POST", "/api/python/pourbaix-diagram", _py("pourbaix_solver", _PHYSICS_TIMEOUT_MS, warm=True)),
        _op("tafel-corrosion-rate", "POST", "/api/python/tafel-corrosion-rate",
            _py("tafel_corrosion_rate_solver", _CHARACTERIZATION_TIMEOUT_MS, warm=True)),
        _op("battery-corrosion-eis", "POST", "/api/python/battery-corrosion-eis",
            _py("battery_corrosion_eis_solver", _CHARACTERIZATION_TIMEOUT_MS, warm=True)),
    ),
    "calculators": (
        _local("engineering-correlations", "unit-aware engineering correlations are evaluated in the browser."),
    ),
    "research-hub": (
        _op("research-registry", "GET", "/api/research/registry", _NODE),
        _op("research-registry-save", "PUT", "/api/research/registry", _NODE),
        _op("research-search", "GET", "/api/research/search", _NODE),
    ),
    "digital-twin": (_AI_CONSULT,),
}

LEGACY_NOTES: Dict[str, Tuple[str, ...]] = {
    "materials-project": (
        "Elastic Constants retains the materials-project identity. The user explicitly submits custom "
        "C_ij or isotropic K/G; optional density and composition are not taken from the shared specimen "
        "or the legacy library. No catalog, consultation or Materials Project request is dispatched. "
        "Missing derived properties remain unavailable; input edits invalidate pending responses.",
    ),
    "experimental-data": (_EVIDENCE_READS_ONLY,),
    "traceability": (_EVIDENCE_READS_ONLY,),
}


# --- Contracted modules (Phase 7 wave 1 pilot) --------------------------------
#
# Every field, bound, default, output key and note below is read from the cited
# source lines (``source_refs``). A bound the authority does not enforce is left
# None; nothing is completed from another module or a guess. All request keys
# are optional at the authority (it applies the listed default when a key is
# absent), so ``required`` is False throughout.

CONTRACT_VERSION = "0.1.0"
_MICRO = "µm"


def _num(key: str, label: str, unit: str, kind: str, default, lo=None, hi=None,
         integer: bool = False, note: str = None) -> InputField:
    return InputField(key=key, label=label, unit=unit, quantity_kind=kind, min=lo, max=hi, default=default,
                      required=False, step=1 if integer else None,
                      value_type="integer" if integer else "number", note=note)


def _choice(key: str, label: str, kind: str, values: Tuple[str, ...], default: str, note: str = None) -> InputField:
    return InputField(key=key, label=label, unit=None, quantity_kind=kind, min=None, max=None, default=default,
                      required=False, enum=values, value_type="enum", note=note)


# keyhole-raytracing: bounds are the _number(key, default, lower, upper, integer)
# calls in python/lpbf_keyhole_raytracing.py:76-90 (the authority rejects outside them).
_KEYHOLE_FIELDS = (
    _num("nx", "Mesh nodes (x)", "1", "count", 64, 2, 256, integer=True,
         note="Not sent by the view; the authority default applies."),
    _num("ny", "Mesh nodes (y)", "1", "count", 64, 2, 256, integer=True,
         note="Not sent by the view; the authority default applies."),
    _num("dx", "Mesh spacing (x)", "m", "length", 2e-6, 1e-9, 1e-3,
         note="Not sent by the view; the authority default applies."),
    _num("dy", "Mesh spacing (y)", "m", "length", 2e-6, 1e-9, 1e-3,
         note="Not sent by the view; the authority default applies."),
    _num("power_W", "Laser power", "W", "power", 250, 0, 1e6,
         note="The view sends the shared LPBF process laserPower_W."),
    _num("beam_radius_um", "Beam radius (1/e² intensity)", _MICRO, "length", 50, 0.01, 10000,
         note="The view sends the shared beamDiameter_um / 2."),
    _num("base_absorption", "Base absorption", "1", "absorptivity", 0.3, 0, 1,
         note="Empirical angular law input, not complex-index Fresnel optics."),
    _num("keyhole_depth_um", "Prescribed cavity depth", _MICRO, "length", 100, 0, 10000),
    _num("max_bounces", "Maximum bounces", "1", "count", 5, 1, 32, integer=True,
         note="Power still in flight at the limit is reported as bounce-limited (truncated), not escaped."),
    _num("num_rays", "Rays", "1", "count", 10000, 32, 100000, integer=True),
    _num("seed", "Random seed", "1", "rng-seed", 0, 0, 2 ** 32 - 1, integer=True),
    _num("ui_ray_limit", "Returned ray paths", "1", "count", 1000, 0, 1000, integer=True,
         note="Display subset only; drawn from a separate generator and never changes the physics samples. "
              "The view sends 150."),
    _choice("device", "Backend", "compute-device", ("cpu", "cuda:0"), "cpu",
            note="No silent backend substitution: any other value is rejected."),
)

_KEYHOLE_OUTPUT = OutputSchema(
    fields=("status", "model_id", "device", "warp_version", "solve_time_ms", "total_input_W",
            "total_absorbed_W", "total_escaped_W", "total_truncated_W", "total_missed_W",
            "mesh_aperture_half_extent_um", "energy_balance_relative_error",
            "absorption_efficiency", "absorption_efficiency_of_intercepted", "missed_fraction",
            "sampling", "inputs", "limitations", "mesh", "ray_paths"),
    status_key=None,
    # The solver returns the literal "success"; failures raise and reach the route as errors.
    transport_values=(("status", ("success",)),),
)

# test_keyhole_contract.py imports warp, which the CI CPU lock (python/requirements-lpbf.in)
# does not install; test_module_contract checks this note against the oracle's imports.
_KEYHOLE_ORACLE_CI_NOTE = "Oracle not run in CI (requires Warp/GPU stack)."

# Checked against the solver's top-level imports by test_contract_keyhole_raytracing.
_KEYHOLE_WARP_NOTE = ("python/lpbf_keyhole_raytracing.py imports warp (NVIDIA Warp) at module level: without "
                      "Warp on the worker interpreter the operation fails; there is no non-Warp path.")

_KEYHOLE_EVIDENCE_NOTE = (
    "Emits no evidence status: the output has no status key ('status' is the transport value "
    "'success'). Ceiling screening-only: a prescribed Gaussian cavity (not a solved free surface) with "
    "an empirical angular absorption law, no material optical data and no experimental comparison "
    "(python/lpbf_keyhole_raytracing.py docstring and 'limitations'). The oracle is analytic: it compares "
    "the Monte Carlo result with the Gaussian square-aperture integral and the flat-surface "
    "normal-incidence fraction in python/test_keyhole_contract.py. It checks sampling and energy "
    "bookkeeping on a flat surface only, not the physics, and does not raise the ceiling. "
    + _KEYHOLE_ORACLE_CI_NOTE
)

_UQ_FIELDS = (
    _choice("baseMetal", "Base metal", "element", ("Ni", "Fe", "Ti", "Al"), "Ni",
            note="The authority maps any value other than Ni/Fe/Ti to the Al constants without an error; "
                 "the contract accepts only the four tabulated keys."),
    _num("coolingRate_nominal", "Nominal cooling rate", "K/s", "cooling-rate", 150000.0,
         note="No bound is enforced; a value <= 0 fails in math.log (not expressible as an inclusive bound)."),
    _num("coolingRate_cov", "Cooling-rate coefficient of variation", "1", "coefficient-of-variation", 0.25,
         note="Fraction (0.25 = 25 %); no bound is enforced."),
    _num("agingTemp_nominal", "Nominal aging temperature", "degC", "temperature", 720.0,
         note="No bound is enforced; each draw is floored at 200 degC."),
    _num("agingTemp_stdDev", "Aging temperature standard deviation", "K", "temperature-difference", 7.5,
         note="Temperature difference (no offset); no bound is enforced."),
    _num("agingTime_nominal", "Nominal aging time", "h", "time", 8.0,
         note="No bound is enforced; each draw is floored at 0.2 h."),
    _num("agingTime_stdDev", "Aging time standard deviation", "h", "time", 0.25),
    _num("serviceStress_nominal", "Nominal service stress", "MPa", "stress", 720.0,
         note="No bound is enforced; each draw is floored at 50 MPa."),
    _num("serviceStress_cov", "Service-stress coefficient of variation", "1", "coefficient-of-variation", 0.08),
    _num("specMinYield_MPa", "Specification minimum yield strength", "MPa", "stress", 1100.0),
    _num("specMinUTS_MPa", "Specification minimum UTS", "MPa", "stress", 1350.0,
         note="Echoed in alloyMetadata only; no UTS is computed (the UTS output is unavailable)."),
    _num("specMinElongation_pct", "Specification minimum elongation", "%", "strain", 12.0),
    _num("mcSamples", "Sample count", "1", "count", 2500, 500, 10000, integer=True,
         note="The authority clamps values outside [500, 10000] instead of rejecting them; the contract "
              "declares [500, 10000] as its hard range."),
    _choice("samplingMethod", "Sampling method", "sampling-method", ("sobol_qmc",), "sobol_qmc",
            note="The authority rejects 'pseudo_mc' with a ValueError; the view still offers it."),
    InputField(key="scramble", label="Random digital shift", unit=None, quantity_kind="flag", min=None, max=None,
               default=True, required=False, value_type="boolean",
               note="The authority coerces with bool(); the contract accepts only booleans."),
    _num("seed", "Random seed", "1", "rng-seed", 42, integer=True,
         note="No bound is enforced (int() conversion)."),
)

_UQ_OUTPUT = OutputSchema(
    fields=("success", "engine", "computeTimeMs", "sampleSizeN", "samplingMetadata", "alloyMetadata",
            "inputUncertainties", "stochasticProperties", "sobolSensitivityAnalysis", "sensitivityMetadata",
            "aerospaceReliability", "provenance"),
    status_key=None,
)

_UQ_EVIDENCE_NOTE = (
    "Emits no evidence status: the output has no status key. stochasticProperties UTS, K_Ic and critical "
    "flaw size (and aerospaceReliability.criticalFlawMedian_mm / criticalFlaw_P10_mm) are null with an "
    "'unavailable: ...' *_status string because their former laws were invented; they are not evidence. "
    "aerospaceReliability.qualificationStatus is "
    "the fixed text 'Screening only; qualification not assessed' and sensitivityMetadata.status is "
    "'estimated' or 'unavailable_zero_variance'; neither is an evidence status. Ceiling: the pending-oracle "
    "cap (screening-only). Simulated populations from a heuristic strengthening model are not coupon "
    "evidence or allowables."
)

_UQ_WARM_NOTE = ("warm: true is the best case: python/persistent_ipc_service.py pre-imports the solver "
                 "(WARM_MODULE_NAMES). When the IPC daemon is unreachable, server/processOrchestrator.ts "
                 "falls back to a cold ad-hoc spawn; each attempt (socket, HTTP, spawn) gets the 25000 ms "
                 "timeout separately, so the total wait can exceed it.")

_PILOT_FORBIDDEN = FORBIDDEN_CLAIM_KEYS  # every claim key stays forbidden


def _keyhole_contract(row: Dict[str, str]) -> ModuleContract:
    operation = Operation(
        id="keyhole-raytracing", method="POST", route="/api/python/lpbf-keyhole-raytracing",
        authority=Authority(kind="lpbf-worker", worker_method="keyhole-raytracing",
                            timeout_ms=_WORKER_TIMEOUT_MS, gpu="optional"),
        input=_KEYHOLE_FIELDS, output=_KEYHOLE_OUTPUT,
    )
    return _pilot(row, operation=operation,
                  # Rewritten from the contract: the seed said "GPU-accelerated ... via NVIDIA Warp BVH",
                  # but the authority defaults to CPU and CUDA is optional.
                  reviewed={"description": "Seeded Monte Carlo ray optics in a prescribed Gaussian cavity "
                                           "(NVIDIA Warp; CPU by default, CUDA optional); prescribed cavity, not a "
                                           "solved free surface; empirical absorption law is not calibrated."},
                  evidence=Evidence(emits=(), ceiling="screening-only", forbidden_claims=_PILOT_FORBIDDEN,
                                    note=_KEYHOLE_EVIDENCE_NOTE),
                  oracle=Oracle(status="present", ci_note=_KEYHOLE_ORACLE_CI_NOTE,
                                scope="It checks sampling and energy bookkeeping on a flat surface only.",
                                ref="python/test_keyhole_contract.py::KeyholeContract."
                                                      "test_gaussian_aperture_matches_independent_integral_at_three_sample_counts"),
                  lifecycle=Lifecycle(background_work="none", resources=("raf", "three", "fetch")),
                  notes=(
                      "The view's number inputs use narrower UI bounds (laser power 0-1000 W, beam diameter "
                      "40-300 µm, cavity depth 0-300 µm, rays step 256) than the authority's hard ranges; "
                      "the contract records the authority's ranges.",
                      "Aborting the HTTP request discards a stale response but does not cancel the worker "
                      "computation (comment in the effect cleanup of src/components/KeyholeRaytracingLab.tsx).",
                      "No validity domain is declared: the module states no source-backed applicability range "
                      "(prescribed cavity, empirical absorption).",
                      _KEYHOLE_WARP_NOTE,
                  ),
                  # Content-anchored: symbols, or line ranges that must still contain the quoted text.
                  sources=(
                      "python/lpbf_keyhole_raytracing.py:1-5#Seeded optics on a prescribed cavity",
                      "python/lpbf_keyhole_raytracing.py::_number",
                      "python/lpbf_keyhole_raytracing.py::compute_keyhole_raytracing",
                      "python/lpbf_worker_rpc.py::_rpc_keyhole_raytracing",
                      "routes/lpbfSimulation.ts:33#/api/python/lpbf-keyhole-raytracing",
                      "server/lpbfWorkerBridge.ts:58#requestTimeoutMs ?? 20000",
                      "src/components/KeyholeRaytracingLab.tsx::KeyholeRaytracingLab",
                      "docs/MODULE_EVIDENCE_INVENTORY.md:40#`keyhole-raytracing` /",
                  ))


def _uq_contract(row: Dict[str, str]) -> ModuleContract:
    operation = Operation(
        id="stochastic-uq-mmpds", method="POST", route="/api/python/stochastic-uq-mmpds",
        authority=_py("stochastic_uq_mmpds_solver", _PHYSICS_TIMEOUT_MS, warm=True),
        input=_UQ_FIELDS, output=_UQ_OUTPUT,
        undeclared_input=("alloyName", "standardSpec", "composition_wt", "composition_tolerances"),
    )
    return _pilot(row, operation=operation, reviewed={},
                  evidence=Evidence(emits=(), ceiling=PENDING_ORACLE_CEILING, forbidden_claims=_PILOT_FORBIDDEN,
                                    note=_UQ_EVIDENCE_NOTE),
                  oracle=Oracle(status="pending"),
                  lifecycle=Lifecycle(background_work="none", resources=("fetch",)),
                  notes=(
                      "alloyName and standardSpec are free-text labels echoed in alloyMetadata; composition_wt and "
                      "composition_tolerances are element -> wt% maps (a missing tolerance defaults to 10 % of the "
                      "nominal). The Field schema cannot describe them, so they are recorded as undeclaredInput.",
                      "More than 13 composition elements exceed the 32-dimension Sobol table in the sensitivity "
                      "pass (2 x (elements + 3) dimensions) and the authority raises a ValueError.",
                      "The view fixes the engine to Sobol QMC (the authority rejects 'pseudo_mc'). The solver run is "
                      "on-demand and illustrative: the strength model is an uncalibrated toy superposition, so only "
                      "relative Sobol indices are shown in the view.",
                      "Coupon statistics over uploaded coupon CSV rows only (computeMMPDSEmpiricalStats in "
                      "src/components/uqLabData.ts; no coupons are bundled and none are generated) run in the "
                      "browser: recorded single-authority debt, not bound as an operation because the code "
                      "declares no route or deadline for it.",
                      "Known removal: UTS, K_Ic and critical flaw size were removed from the response (null + "
                      "unavailable status); the initialFlawSize_um_* inputs no longer exist.",
                      "No validity domain is declared: no source-backed applicability range exists for the "
                      "strengthening model or the input distributions.",
                      _UQ_WARM_NOTE,
                  ),
                  # Content-anchored: symbols, or line ranges that must still contain the quoted text.
                  # pythonComputationService.ts is anchored by symbol because other lanes delete lines there.
                  sources=(
                      "python/stochastic_uq_mmpds_solver.py::solve_stochastic_uq",
                      "python/stochastic_uq_mmpds_solver.py::SobolSequenceGenerator",
                      "python/stochastic_uq_mmpds_solver.py::provenance",
                      "python/alloy_data_kinetics_uq_fatigue.py::UQ_BASE_METAL_LATTICE",
                      "python/alloy_data_kinetics_uq_fatigue.py::uq_lattice_constants",
                      "python/alloy_data_kinetics_uq_fatigue.py::UQ_DEFAULT_BASE_METAL",
                      "routes/physics.ts::handlePythonDispatch",
                      "python/persistent_ipc_service.py::WARM_MODULE_NAMES",
                      "server/processOrchestrator.ts::PersistentPythonIPCSupervisor.execute",
                      "routes/physics.ts:99-100#python/stochastic_uq_mmpds_solver.py",
                      "src/components/UQLab.tsx::UQLab",
                      "src/components/UQLab.tsx::runQMCSolver",
                      "src/components/uqLabData.ts::computeMMPDSEmpiricalStats",
                      "src/services/pythonComputationService.ts::calculateStochasticUQMMPDS",
                      "docs/MODULE_EVIDENCE_INVENTORY.md:77#`uq-lab` /",
                  ))


# --- Contracted modules (Phase 7 wave 2) --------------------------------------
#
# Same rules as the pilots: every key, default and output field is read from the cited
# authority code (each scaffold checks them against the code by AST and against a real
# run); a bound the authority does not enforce stays None. No oracle exists for any of
# these modules, so each keeps the pending-oracle cap and emits no status. Identity text
# (label, description, next, maturity) stays seed-derived: wording is not reviewed here.

_WORKER_NO_VALIDATION = ("The worker RPC handler reads each key with a default and applies no range check "
                         "(float()/int() conversion only where noted); the contract's types and enums are "
                         "stricter than the authority.")
_PENDING_CAP = ("Ceiling: the pending-oracle cap (screening-only); no oracle exists, so results are "
                "unvalidated.")


def _wave2(row, operation: Operation, evidence_note: str, notes, sources, resources=("fetch",),
           extra_operations=(), version=None) -> ModuleContract:
    return _pilot(row, operation=operation, reviewed={}, extra_operations=extra_operations, version=version,
                  evidence=Evidence(emits=(), ceiling=PENDING_ORACLE_CEILING, forbidden_claims=_PILOT_FORBIDDEN,
                                    note=evidence_note),
                  oracle=Oracle(status="pending"),
                  lifecycle=Lifecycle(background_work="none", resources=resources),
                  notes=tuple(notes), sources=tuple(sources))


def _flag(key: str, label: str, default: bool, note: str = None) -> InputField:
    return InputField(key=key, label=label, unit=None, quantity_kind="flag", min=None, max=None, default=default,
                      required=False, value_type="boolean", note=note)


def _worker_contract_op(op_id: str, fields, output: OutputSchema, undeclared=()) -> Operation:
    return Operation(id=op_id, method="POST", route=f"/api/python/lpbf-{op_id}",
                     authority=_worker(op_id), input=tuple(fields), output=output,
                     undeclared_input=tuple(undeclared))


_WORKER_SOURCES = (
    "server/lpbfWorkerBridge.ts:58#requestTimeoutMs ?? 20000",
    "python/lpbf_worker_rpc.py::dispatch",
)

# ttt-cct-kinetics: keys and defaults of the data.get(...) calls in the script entry point.
_KINETICS_ALLOYS = ("AISI 4140", "AISI 4340", "AISI D2", "Inconel 718", "Ti-6Al-4V", "Al 7075")
_KINETICS_FIELDS = (
    _choice("alloy", "Alloy", "alloy", _KINETICS_ALLOYS, "AISI 4140",
            note="The authority resolves the name through alloy_registry (kinetics domain) and rejects an unknown "
                 "or ambiguous name with input_validation UNKNOWN_ALLOY (exit 2, HTTP 422); the contract lists the "
                 "six kinetics table names the view offers."),
    _num("coolingRate_C_s", "Selected cooling rate", "K/s", "cooling-rate", 10.0,
         note="Passed unconverted by the entry point. Sets only calphadVsKineticsGap.kineticRealityAtSelectedCooling; "
              "the CCT map uses a fixed list of rates. For AISI 4140 and AISI 4340 (Li model available) a value "
              "<= 0 is rejected with input_validation NON_POSITIVE (exit 2); for the other alloys a non-number is "
              "rejected with NON_FINITE (exit 2) and no bound is enforced."),
    _num("grainSize_um", "Prior austenite grain size", _MICRO, "length", 25.0,
         note="Passed unconverted by the entry point. Only the Li (1998) model uses it (AISI 4140, AISI 4340), as "
              "the mean planar grain diameter converted to the ASTM E112 grain size number; there a value <= 0 is "
              "rejected with input_validation NON_POSITIVE (exit 2) and a value outside 1-1000 µm (an input sanity "
              "bound of the implementation, not a source range) with OUT_OF_RANGE (exit 2). For AISI D2 (outside "
              "the model range), "
              "Inconel 718, Ti-6Al-4V and Al 7075 it is ignored and only echoed in inputParameters, so a negative "
              "value returns exit 0."),
    _num("austTemp_C", "Austenitisation temperature", "degC", "temperature", 860.0,
         note="Passed unconverted by the entry point. For AISI 4140 and AISI 4340 a value outside 0-1600 degC "
              "(input sanity bound) is rejected with OUT_OF_RANGE (exit 2); otherwise no bound is enforced. At or "
              "below the Grange Ae3 the Li model's CCT starts and critical cooling rate are unavailable (fully "
              "austenitic start assumed)."),
    _num("agingTemp_C", "Aging temperature", "degC", "temperature", 720.0,
         note="Passed unconverted by the entry point; no bound is enforced."),
    _num("agingTime_h", "Aging time", "h", "time", 8.0,
         note="Passed unconverted by the entry point. Echoed in inputParameters only; the LSW coarsening profile uses a fixed 0.1-100 h time grid."),
)
_KINETICS_OUTPUT = OutputSchema(
    fields=("success", "engine", "computeTimeMs", "alloy", "alloyMetadata", "inputParameters",
            "criticalTransformationTemperatures", "tttIsothermalCurves", "cctContinuousCoolingMap",
            "lswPrecipitateCoarsening", "calphadVsKineticsGap", "kineticsModel", "tttIncubationFloor",
            "provenance"),
    status_key=None,
)


def _kinetics_contract(row: Dict[str, str]) -> ModuleContract:
    operation = Operation(
        id="kinetics-ttt-cct", method="POST", route="/api/python/kinetics-ttt-cct",
        authority=_py("kinetics_ttt_cct_solver", _PHYSICS_TIMEOUT_MS, warm=True),
        input=_KINETICS_FIELDS, output=_KINETICS_OUTPUT,
    )
    return _wave2(
        row, operation,
        evidence_note=(
            "Emits no evidence status: kineticsModel.status (available for AISI 4140 and AISI 4340, unavailable "
            "for AISI D2 outside the Li model composition range and with the reason 'kinetics model is "
            "steel-only' for Inconel 718, Ti-6Al-4V and Al 7075), kineticsModel.validationStatus 'unvalidated' / "
            "evidenceLevel 'screening' and the per-row *_status keys record applicability and availability, not "
            "evidence. Transformation start times come from the Li et al. (1998) equations (python "
            "test_kinetics_li1998 reproduces the model author's AISI 4140 example and the Li-model CCT panels of "
            "Collins et al. 2023 within stated tolerances); no matched experimental TTT/CCT fixture is registered "
            "as the contract oracle. " + _PENDING_CAP),
        notes=(
            "calphadVsKineticsGap.equilibriumPrediction is fixed steel text in the solver ('Ferrite + Cementite / "
            "Equilibrium intermetallics') for AISI 4140 and AISI 4340, status static-text-not-a-calphad-calculation; "
            "for AISI D2 it is null with status unavailable-composition-outside-li-model-range and for Inconel 718, "
            "Ti-6Al-4V and Al 7075 null with status unavailable-kinetics-model-steel-only; no CALPHAD calculation "
            "runs in this operation.",
            "TTT/CCT model: Li, Niebuhr, Meekisho & Atteridge (1998) ferrite/pearlite/bainite start curves from "
            "composition and ASTM grain size (kineticsModel.sourceLabel, modelVersion li1998-additivity-v1), Grange "
            "Ae3/Ae1, Li Bs, Kung-Rayment Ms, CCT starts by the additivity rule per phase (no phase interaction). "
            "Reported only for a steel inside the composition range stated by M. Li (1996 thesis p. 86): AISI 4140 "
            "and AISI 4340; AISI D2 is outside it and Inconel 718, Ti-6Al-4V and Al 7075 are not steels, so their "
            "TTT curves, CCT starts, critical cooling rate and verdict are null with the reason (for the "
            "non-steels: 'kinetics model is steel-only'). Registry "
            "placeholders (alloy_registry.KINETICS_PLACEHOLDERS: Inconel 718 and Al 7075 Ms/Mf) are null.",
            "cctContinuousCoolingMap[].phaseFractions, predictedHardness_HRC and predictedHardness_HV are null for "
            "every alloy (status unavailable-fractions-not-computed for the modelled steels): the Li model needs "
            "the equilibrium ferrite/pearlite amounts of a thermodynamic Fe-C-M model that is not implemented. "
            "calphadVsKineticsGap.kineticRealityAtSelectedCooling.predictedMartensite_pct is given only when no "
            "diffusional start is reached above Ms (Koistinen-Marburger at 25 C).",
            "The LSW coarsening profile (K = 8 gamma D C_e Vm^2 / (9 R T), C_e in mol/m^3) uses the same nucleus "
            "radius, coarsening constants and Orowan/cutting strengthening law (280 MPa peak at a 9 nm critical "
            "radius) for every alloy; only the diffusion activation energy differs. It is null at or above the "
            "registry Ae3 (steels: Ae1).",
            "Validity domain (kineticsModel.validityDomain): 0.1<C<0.5, Si<1.0, Mn<2, Ni<4, Cr<3, Mo<1, V<0.2, "
            "Cu<0.5, Mn+Ni+Cr+Mo<5 (printed as Mo+Ni+Cr+Mo; both sums are checked), 0.01<Al<0.05 wt% (M. Li 1996 "
            "thesis p. 86, stated as untested by the author); a negative content is outside. Al is not in the "
            "registry compositions, so the Al bound is unchecked and the status is 'inside-partially-checked' "
            "(AISI 4140, AISI 4340). This solver-side check is not declared as the contract validity domain "
            "(pilot contracts carry none).",
            "tttIsothermalCurves: for ferrite only tStart_s (1 %) is reported; t50_s and tFinish_s are null because "
            "the ferrite fraction is a volume fraction of the austenite that ends at the equilibrium ferrite amount "
            "(not modelled). Pearlite uses the phantom fraction (goes to completion) and bainite the volume "
            "fraction (kineticsModel.li1998.reactionFractionBasis).",
            "warm: true is the best case: python/persistent_ipc_service.py pre-imports the solver; without the "
            "IPC daemon server/processOrchestrator.ts falls back to a cold spawn with the 25000 ms timeout per "
            "attempt.",
        ),
        sources=(
            "python/kinetics_ttt_cct_solver.py::solve_phase_transformation_kinetics",
            "python/kinetics_ttt_cct_solver.py::LiModel",
            "python/kinetics_ttt_cct_solver.py::li_composition_check",
            "python/kinetics_ttt_cct_solver.py::resolve_kinetics_alloy",
            "python/kinetics_ttt_cct_solver.py::provenance",
            "python/alloy_data_kinetics_uq_fatigue.py::KINETICS_LEGACY_NAMES",
            "python/input_validation.py::require_known_alloy",
            "routes/physics.ts::handlePythonDispatch",
            "routes/physics.ts:89#python/kinetics_ttt_cct_solver.py",
            "python/persistent_ipc_service.py::WARM_MODULE_NAMES",
            "src/components/PhaseKineticsTTTCCTStudio.tsx::PhaseKineticsTTTCCTStudio",
            "src/services/pythonComputationService.ts::calculatePhaseKineticsTTTCCT",
            "docs/MODULE_EVIDENCE_INVENTORY.md:62#`ttt-cct-kinetics` /",
        ))


# icme-motor: keys and defaults of the params.get(...) calls in solve_multiscale_pipeline.
_ICME_COMPONENTS = ("turbine_blade_root", "pressure_bulkhead", "lpbf_bracket")
_ICME_FIELDS = (
    _choice("baseMetal", "Base metal", "element", ("Ni", "Fe", "Ti", "Al"), "Ni",
            note="Any other value is rejected with input_validation UNKNOWN_ELEMENT (exit 2, HTTP 422)."),
    _num("coolingRate_C_s", "Cooling rate", "K/s", "cooling-rate", 150000.0,
         note="Converted with float(); no bound is enforced; values below 1 K/s are floored at 1 in the SDAS power law."),
    _num("agingTemp_C", "Aging temperature", "degC", "temperature", 720.0,
         note="Converted with float(); no bound is enforced."),
    _num("agingTime_h", "Aging time", "h", "time", 8.0, note="Converted with float(); no bound is enforced."),
    _num("strainRate_s_inv", "Reference strain rate", "1/s", "strain-rate", 0.001,
         note="Converted with float(); written into the exported material cards only. No bound is enforced."),
    _num("serviceTemp_C", "Service temperature", "degC", "temperature", 25.0,
         note="Converted with float() by the authority but not used in any computed value (the structuralVerdict "
              "text is the same at 1000 degC)."),
    _choice("componentType", "Component", "component-catalog", _ICME_COMPONENTS, "turbine_blade_root",
            note="The authority silently uses turbine_blade_root for any other value; the contract accepts only "
                 "the three catalog keys."),
)
_ICME_OUTPUT = OutputSchema(
    fields=("success", "modelStatus", "modelStatusNote", "modelParts", "engine", "computeTimeMs",
            "inputParameters", "scale0_dftAtomistic",
            "scale1_calphadSoluteMisfit", "scale2_microstructureKinetics", "scale3_continuumPlasticity",
            "scale4_macroComponentFEA", "caeExportCards", "provenance"),
    status_key=None,
    transport_values=(("modelStatus", ("illustrative",)),),
)


def _icme_contract(row: Dict[str, str]) -> ModuleContract:
    operation = Operation(
        id="icme-multiscale-pipeline", method="POST", route="/api/python/icme-multiscale-pipeline",
        authority=_py("icme_multiscale_pipeline_solver", _PHYSICS_TIMEOUT_MS, warm=True),
        input=_ICME_FIELDS, output=_ICME_OUTPUT,
        undeclared_input=("alloyName", "crystalSystem", "composition_wt", "grainSize_um"),
    )
    return _wave2(
        row, operation,
        evidence_note=(
            "Emits no evidence status: modelStatus is a model label (always 'illustrative'), not an evidence "
            "status, and the output has no evidence status key. scale4_macroComponentFEA.structuralVerdict is "
            "fixed text chosen by comparing the estimated yield strength with a catalog safety factor (a "
            "yield-only check: no creep, fatigue or fracture check); it is not an "
            "evidence status and not a structural assessment. The scale names (DFT, CALPHAD, FEA) label tabulated "
            "constants and closed-form estimates in the solver; no DFT, CALPHAD or FEA computation runs. "
            "ultimateTensileStrength_UTS_MPa, fractureToughness_K1c_MPa_sqrt_m, criticalFlawSize_ac_mm and "
            "plasticZoneRadius_rp_mm are null (unavailable, with a status text) because the model has no valid way "
            "to compute them. "
            + _PENDING_CAP),
        notes=(
            "alloyName is a free-text label written into the output and the material cards; crystalSystem is "
            "echoed only and its default depends on baseMetal; composition_wt is an element -> wt% map (an element "
            "without ICME atomic-weight data is rejected with UNKNOWN_ELEMENT); grainSize_um is an optional override "
            "with no default (absent, null or <= 0 uses the SDAS estimate). The Field schema cannot describe these, "
            "so they are recorded as undeclaredInput.",
            "Wording gap fixed in fx-icme: the verdict used to read 'STRUCTURALLY SAFE (Passed Yield & Creep "
            "Criteria)' although no creep check exists. It is now a yield-only text ('YIELD CHECK PASSED ... no "
            "creep, fatigue or fracture check'); serviceTemp_C is still not used and the verdict is the same at "
            "1000 degC (no creep check exists).",
            "Wording gap fixed in fx-icme: the exported CAE material cards were headed 'MetalliX Multi-Scale ICME "
            "Calibrated Card'; they are now headed 'ILLUSTRATIVE Card (uncalibrated, not validated)' because no "
            "calibration against data is performed.",
            "Unavailable by design (fx-icme): the former UTS (equal to the yield strength by the Hollomon K choice) "
            "and the former K_Ic (a formula with the unit MPa, not MPa*sqrt(m)) are null with status texts; the "
            "critical flaw size and plastic zone radius that need K_Ic are null too.",
            "No validity domain is declared: no source-backed applicability range is established for the "
            "coupled estimates.",
            "warm: true is the best case: python/persistent_ipc_service.py pre-imports the solver; without the "
            "IPC daemon server/processOrchestrator.ts falls back to a cold spawn with the 25000 ms timeout per "
            "attempt.",
        ),
        sources=(
            "python/icme_multiscale_pipeline_solver.py::solve_multiscale_pipeline",
            "python/icme_multiscale_pipeline_solver.py::main",
            "python/icme_multiscale_pipeline_solver.py::_unknown_element",
            "python/alloy_data_calphad_battery_icme.py::icme_base_metal",
            "routes/physics.ts::handlePythonDispatch",
            "routes/physics.ts:94#python/icme_multiscale_pipeline_solver.py",
            "python/persistent_ipc_service.py::WARM_MODULE_NAMES",
            "src/components/ICMEMultiScalePipelineStudio.tsx::ICMEMultiScalePipelineStudio",
            "src/services/pythonComputationService.ts::calculateICMEMultiScalePipeline",
            "docs/MODULE_EVIDENCE_INVENTORY.md:66#`icme-motor` /",
        ))


# murakami-fatigue: keys and defaults of _rpc_fatigue_fracture in python/lpbf_worker_rpc.py.
_FATIGUE_FIELDS = (
    _choice("alloyName", "Alloy", "alloy", ("Ti-6Al-4V", "316L SS", "Inconel 718", "AlSi10Mg"), "Ti-6Al-4V",
            note="The authority resolves the name through alloy_registry (fatigue_fracture domain) and rejects an "
                 "unknown name with input_validation UNKNOWN_ALLOY (HTTP 422); the contract lists the four table "
                 "names the view offers."),
    _num("sqrtArea_um", "Defect size (sqrt area)", _MICRO, "length", 45.0,
         note="Converted with float(); the authority requires a finite value > 0 and rejects anything else with "
              "input_validation NON_POSITIVE (HTTP 422)."),
    _choice("location", "Defect location", "defect-location", ("surface", "sub-surface", "internal"), "internal",
            note="The authority (murakami_constants.classify_location) accepts surface, sub-surface/subsurface and "
                 "internal/interior, case-insensitive, and rejects any other text with OUT_OF_RANGE (HTTP 422); the "
                 "contract accepts the view's three values."),
    _num("stressRatio_R", "Stress ratio R", "1", "stress-ratio", -1.0,
         note="Converted with float(); the authority requires a finite R < 1 and rejects R >= 1 with OUT_OF_RANGE "
              "(HTTP 422). The fatigue-limit correction still caps 0.99 < R < 1 at 0.99."),
    _num("stressAmplitude_MPa", "Cyclic stress amplitude", "MPa", "stress", 220.0,
         note="Converted with float(); the authority requires a finite value > 0 (NON_POSITIVE, HTTP 422)."),
)


def _fatigue_contract(row: Dict[str, str]) -> ModuleContract:
    operation = _worker_contract_op(
        "fatigue-fracture", _FATIGUE_FIELDS,
        OutputSchema(fields=("fatigue_limit", "kitagawa_takahashi_curve", "paris_crack_growth"), status_key=None),
        undeclared=("type",))
    return _wave2(
        row, operation,
        evidence_note=(
            "Emits no evidence status: the output has no status key (paris_crack_growth.status is the integration "
            "outcome 'non_propagating', 'fractured' or 'runout', not an evidence status). Murakami, El-Haddad and "
            "Paris expressions with per-alloy constants from alloy_registry (fatigue_fracture domain); no oracle "
            "compares the result with an independent reference. " + _PENDING_CAP),
        notes=(
            "The handler reads 'type' (default 'full') and never uses it; it is recorded as undeclaredInput.",
            "No validity domain is declared: no source-backed applicability range is established for the "
            "defect sizes or stress ratios.",
            "UNKNOWN_ALLOY and the input rejections noted on the fields reach the route as HTTP 422 through "
            "LpbfWorkerValidationError (routes/lpbfSimulation.ts workerError).",
        ),
        sources=_WORKER_SOURCES + (
            "python/lpbf_worker_rpc.py::_rpc_fatigue_fracture",
            "python/lpbf_fatigue_fracture.py::fatigue_constants",
            "python/lpbf_fatigue_fracture.py::MurakamiFatigueEngine.calculate_fatigue_limit",
            "python/lpbf_fatigue_fracture.py::MurakamiFatigueEngine.simulate_paris_crack_growth",
            "python/alloy_data_kinetics_uq_fatigue.py::FATIGUE_LEGACY_NAMES",
            "routes/lpbfSimulation.ts:31#/api/python/lpbf-fatigue-fracture",
            "routes/lpbfSimulation.ts::workerError",
            "src/components/MurakamiFatigueLab.tsx::MurakamiFatigueLab",
            "src/services/pythonComputationService.ts::computeMurakamiFatigue",
            "docs/MODULE_EVIDENCE_INVENTORY.md:32#`murakami-fatigue` /",
        ))


# The two toolpath-studio operations (kinematics and adaptive feed-forward) share the G-code/CLI parser (lpbf_toolpath_kinematics).
_TOOLPATH_FORMAT = _choice("format", "Toolpath format", "toolpath-format", ("gcode", "cli"), "gcode",
                           note="The authority lower-cases the value and parses anything other than 'cli' as G-code.")
_CONTENT_NOTE = ("content is the raw G-code or CLI text (default empty: zero segments). The Field schema cannot "
                 "describe free text, so it is recorded as undeclaredInput.")

_TOOLPATH_FIELDS = (
    _TOOLPATH_FORMAT,
    _num("defaultPower_W", "Default laser power", "W", "power", 250.0,
         note="Used for vectors without an explicit power word. Passed unconverted; no bound is enforced."),
    _num("defaultSpeed_mms", "Default scan speed", "mm/s", "speed", 1000.0,
         note="Used for vectors without an explicit feed word. Passed unconverted; no bound is enforced."),
    _flag("skywritingEnabled", "Skywriting", False, note="Passed unconverted to the scanner profile."),
    _num("accelMax_mms2", "Maximum mirror acceleration", "mm/s^2", "acceleration", 40000.0,
         note="Passed unconverted; no bound is enforced."),
    _num("jumpSpeed_mms", "Jump speed", "mm/s", "speed", 3000.0, note="Passed unconverted; no bound is enforced."),
    _num("laserOnDelay_us", "Laser-on delay", "µs", "time", 100.0, note="Passed unconverted; no bound is enforced."),
    _num("laserOffDelay_us", "Laser-off delay", "µs", "time", 120.0,
         note="Passed unconverted; stored in the scanner profile but not used by the kinematics engine."),
    _num("markDelay_us", "Mark delay", "µs", "time", 200.0, note="Passed unconverted; no bound is enforced."),
    _num("jumpDelay_us", "Jump delay", "µs", "time", 350.0, note="Passed unconverted; no bound is enforced."),
)


_ADAPTIVE_FIELDS = (
    _TOOLPATH_FORMAT,
    _num("defaultPower_W", "Default laser power", "W", "power", 280.0,
         note="Converted with float(); no bound is enforced."),
    _num("defaultSpeed_mms", "Default scan speed", "mm/s", "speed", 1000.0,
         note="Converted with float(); no bound is enforced."),
    _flag("apply67DegRotation", "Apply 67° interlayer rotation", False,
          note="The authority coerces with bool(); the contract accepts only booleans."),
    _num("layerIndex", "Layer index", "1", "count", 1, integer=True,
         note="Converted with int(); no bound is enforced. When apply67DegRotation is true the rotation angle is "
              "67° x layerIndex; otherwise it is 0."),
    _num("accelMax_mms2", "Maximum mirror acceleration", "mm/s^2", "acceleration", 40000.0,
         note="Converted with float(); no bound is enforced."),
    _num("jumpSpeed_mms", "Jump speed", "mm/s", "speed", 3000.0, note="Converted with float(); no bound is enforced."),
)


def _toolpath_contract(row: Dict[str, str]) -> ModuleContract:
    operation = _worker_contract_op(
        "toolpath-kinematics", _TOOLPATH_FIELDS,
        OutputSchema(fields=("total_segments", "total_build_time_s", "total_laser_on_time_s", "duty_cycle_pct",
                             "total_energy_input_J", "total_mark_distance_mm", "total_jump_distance_mm",
                             "hotspot_count", "hotspots", "skywriting_mitigation_active", "no_cruise_segment_count",
                             "marking_segment_count", "laser_never_fires", "warnings"), status_key=None),
        undeclared=("content",))
    # Merged in from the former adaptive-mitigation module (Feed-forward power tab of the same view).
    feedforward = _worker_contract_op(
        "adaptive-feedforward", _ADAPTIVE_FIELDS,
        OutputSchema(fields=("total_segments", "mitigated_hotspots_count", "overall_energy_reduction_pct",
                             "rotation_angle_deg", "total_mitigated_energy_J", "mitigated_gcode", "sample_segments"),
                     status_key=None),
        undeclared=("content",))
    return _wave2(
        row, operation,
        extra_operations=(feedforward,),
        version="0.2.0",
        evidence_note=(
            "Emits no evidence status: the output has no status key. Trapezoidal or triangular galvanometer "
            "velocity profiles plus the configured scanner delays; a hotspot is a segment whose average linear energy density exceeds 1.25 times the "
            "nominal P/v. No thermal field is solved and no in-situ measurement is compared. "
            "Operation adaptive-feedforward (Feed-forward power tab) emits no evidence status either: the output has "
            "no status key. Feed-forward power scaling P_nom * min(1, "
            "v_peak / v_nom) from the kinematic peak speed of each vector, plus an optional rotation by 67° x "
            "layerIndex about the origin; no sensor signal is read, so nothing is closed-loop, and no defect "
            "reduction is measured. " + _PENDING_CAP),
        notes=(
            _CONTENT_NOTE,
            "No validity domain is declared: no source-backed applicability range is established for the scanner "
            "parameters.",
            "Contract 0.2.0: the adaptive-feedforward operation was merged in from the former adaptive-mitigation "
            "module (now the Feed-forward power tab of this view); the worker route and RPC are unchanged.",
            "mitigated_hotspots_count counts laser vectors whose kinematic peak speed is below 0.99 x the nominal "
            "speed; it is not the toolpath-studio hotspot definition (average linear energy density above 1.25 x "
            "nominal P/v). overall_energy_reduction_pct uses the nominal-speed time of each vector.",
            "The cited inventory row named the route /api/python/lpbf-adaptive-mitigation, which does not exist; the "
            "Phase 7 wave 2 fix round corrected it to the served /api/python/lpbf-adaptive-feedforward.",
            "No validity domain is declared: no source-backed applicability range is established.",
        ),
        sources=_WORKER_SOURCES + (
            "python/lpbf_worker_rpc.py::_rpc_toolpath_kinematics",
            "python/lpbf_toolpath_kinematics.py::ScannerProfile",
            "python/lpbf_toolpath_kinematics.py::GalvanometerKinematicsEngine.simulate_vector",
            "python/lpbf_toolpath_kinematics.py::GalvanometerKinematicsEngine.simulate_toolpath",
            "routes/lpbfSimulation.ts:30#/api/python/lpbf-toolpath-kinematics",
            "src/components/LpbfToolpathStudioLab.tsx::LpbfToolpathStudioLab",
            "src/services/pythonComputationService.ts::simulateToolpathKinematics",
            "docs/MODULE_EVIDENCE_INVENTORY.md:30#`toolpath-studio` /",
            "python/lpbf_worker_rpc.py::_rpc_adaptive_feedforward",
            "python/lpbf_adaptive_feedforward.py::AdaptiveFeedforwardMitigator.compensate_vector",
            "python/lpbf_adaptive_feedforward.py::AdaptiveFeedforwardMitigator.process_toolpath",
            "routes/lpbfSimulation.ts:32#/api/python/lpbf-adaptive-feedforward",
            "src/components/LpbfToolpathStudioLab.tsx::ToolpathFeedforwardPanel",
            "src/services/pythonComputationService.ts::processAdaptiveFeedforward",
            "docs/MODULE_EVIDENCE_INVENTORY.md:34#Merged 2026-10-07 | `adaptive-mitigation`",
        ))


# micrograph (micrograph rework): keys, defaults and bounds are those of python/micrograph_measure.py
# read_request (literal defaults) and the _int/_finite checks in measure(); the authority rejects
# values outside the declared ranges with MeasureInputError (HTTP 400 through the worker route).
_GREY_OFF_NOTE = "is not a threshold: no grey level satisfies it, so the class is not measured"
_MICROGRAPH_FIELDS = (
    _num("cropTopPx", "Rows excluded at the top", "px", "pixel-count", 0, 0, 4095, integer=True),
    _num("cropBottomPx", "Rows excluded at the bottom (data bar)", "px", "pixel-count", 0, 0, 4095, integer=True,
         note="The SEM data bar is excluded by the user here; nothing is excluded by default."),
    _num("cropLeftPx", "Columns excluded at the left", "px", "pixel-count", 0, 0, 4095, integer=True),
    _num("cropRightPx", "Columns excluded at the right", "px", "pixel-count", 0, 0, 4095, integer=True),
    _num("umPerPx", "Stated pixel size", "µm/px", "image-scale", 0.0, 0, None,
         note="0 (default) means not supplied. A positive value needs calibrationNote (its source) and cannot be "
              "combined with a scale bar."),
    _num("barLengthUm", "Scale-bar length", _MICRO, "length", 0.0, 0, None,
         note="0 (default) means not supplied; with barLengthPx (>= 2) the authority computes umPerPx."),
    _num("barLengthPx", "Scale-bar length on the image", "px", "pixel-length", 0.0, 0, None,
         note="Caliper length drawn by the user over the image scale bar; 0 (default) means not supplied."),
    _num("darkMaxGrey", "Dark class: grey <= threshold", "1", "grey-level", -1, -1, 254, integer=True,
         note=f"-1 (default) {_GREY_OFF_NOTE}. Must be below brightMinGrey when both classes are measured."),
    _num("brightMinGrey", "Bright class: grey >= threshold", "1", "grey-level", 256, 1, 256, integer=True,
         note=f"256 (default) {_GREY_OFF_NOTE}."),
    _num("boundaryMaxGrey", "Grain boundaries: grey <= threshold", "1", "grey-level", -1, -1, 254, integer=True,
         note=f"-1 (default) {_GREY_OFF_NOTE}; automatic E112 counting assumes boundaries darker than grains."),
    _num("tiles", "Tiles per side for the field-to-field CI", "1", "count", 4, 2, 10, integer=True,
         note="Convention of this module (k x k tiles of one image), not a standard value."),
    _num("sensitivityDeltaGrey", "Threshold sensitivity step", "1", "grey-level", 10, 1, 64, integer=True,
         note="The class fraction is also reported at threshold -/+ this many grey levels."),
    _num("minAreaPx", "Smallest counted particle", "px", "pixel-count", 4, 1, 100000, integer=True,
         note="Detection limit of the particle count (reported as an ECD when calibrated); a convention."),
    _num("linesPerDirection", "E112 test lines per direction", "1", "count", 8, 1, 50, integer=True,
         note="Horizontal rows and vertical columns at i/(m+1) of the region of interest."),
    _flag("returnMasks", "Return class masks for the overlay", True),
)
_MICROGRAPH_UNDECLARED = ("imageWidth", "imageHeight", "imageData", "calibrationNote", "darkLabel", "brightLabel",
                          "manualCounts", "manualClicks")
_MICROGRAPH_OUTPUT = OutputSchema(
    fields=("schema", "methodVersion", "record", "calibrationRequired", "testLines", "classes", "grainSize",
            "grainSizeManual", "limitations"),
    status_key=None,
)
_MICROGRAPH_ORACLE_SCOPE = "Synthetic known-answer images only (O1-O9); no real micrograph is compared."
_MICROGRAPH_EVIDENCE_NOTE = (
    "Emits no evidence status: neither output carries a status key. micrograph-measure is measurement software "
    "(threshold area fraction with field-to-field CI and threshold sensitivity, connected-component particles, "
    "ASTM E112 intersection counting) checked against synthetic oracle images in "
    "python/test_micrograph_measure.py; it has no comparison with real micrographs or with manual counts by a "
    "metallographer, so the ceiling stays screening-only. Lengths, areas, densities and G are null without a "
    "user calibration. diagnose-micrograph returns language-model text: advisory, never a measurement.")


def _micrograph_contract(row: Dict[str, str]) -> ModuleContract:
    measure = Operation(
        id="micrograph-measure", method="POST", route="/api/python/micrograph-measure",
        authority=_py("micrograph_measure", 60000, warm=False), input=_MICROGRAPH_FIELDS, output=_MICROGRAPH_OUTPUT,
        undeclared_input=_MICROGRAPH_UNDECLARED)
    describe = Operation(
        id="diagnose-micrograph", method="POST", route="/api/metallurgy/diagnose-micrograph",
        authority=Authority(kind="node-provider", timeout_ms=60000),
        input=(_choice("mimeType", "Image media type", "media-type",
                       ("image/jpeg", "image/png", "image/webp", "image/gif"), "image/jpeg",
                       note="Used only when imageBase64 is not a data: URL (the data-URL type wins); other types "
                            "are rejected with HTTP 415."),),
        output=OutputSchema(fields=("diagnosis",), status_key=None),
        undeclared_input=("imageBase64", "prompt"))
    seed = {"label": row["label"], "description": row["description"], "next": row["next"], "maturity": row["scope"]}
    return ModuleContract(
        id=row["id"], version=CONTRACT_VERSION, owner=OWNER_UNASSIGNED, workspace=row["workspace"],
        label=seed["label"], description=seed["description"], next=seed["next"], maturity=seed["maturity"],
        navigation="listed", seed_derived=SEED_TEXT_FIELDS,
        view=View(component=row["viewComponent"], export=row["viewExport"]),
        evidence=Evidence(emits=(), ceiling="screening-only", forbidden_claims=_PILOT_FORBIDDEN,
                          note=_MICROGRAPH_EVIDENCE_NOTE),
        tests=TestRefs(oracle=Oracle(status="present", scope=_MICROGRAPH_ORACLE_SCOPE,
                                     ref="python/test_micrograph_measure.py::O1SquareGrid.test_exact_intercept_and_g"),
                       schema="python/test_contract_micrograph.py", docs=module_doc_path(row["id"])),
        migration_state="contracted", operations=(measure, describe),
        lifecycle=Lifecycle(background_work="none", resources=("fetch",)),
        legacy_notes=(
            "imageData is the 8-bit greyscale image (row-major bytes, base64) with imageWidth and imageHeight "
            "(each 1-4096); labels, calibrationNote, manualCounts (one count per test line, multiples of 0.5) and "
            "manualClicks are free text or lists. The Field schema cannot describe them, so they are recorded as "
            "undeclaredInput; the authority validates them.",
            "The view decodes PNG/JPEG/BMP/GIF/WebP in the browser; TIFF is not decoded (the view says so) and no "
            "instrument metadata (pixel size) is read from files.",
            "diagnose-micrograph needs OPENAI_API_KEY and is refused when AIRGAPPED=1; its timeout is the provider "
            "default (server/openaiService.ts), the route passes none.",
            "No validity domain is declared: no real-image comparison establishes an applicability range.",
            "micrograph-measure runs as a python-ipc script (IPC process pool, or an ad-hoc process when the daemon "
            "is unreachable) under a 60000 ms deadline, not in the serial LPBF worker: the worker refuses RPC lines "
            "over 1,000,000 characters (an image above about 865 x 865 px) and would hold up LPBF job calls. The "
            "route answers 413 above 24,000,000 bytes of JSON (a 4096 x 4096 image is 22.4 MB).",
        ),
        source_refs=(
            "routes/physics.ts",
            "server/processOrchestrator.ts::runPythonScript",
            "python/micrograph_measure.py::main",
            "python/micrograph_measure.py::read_request",
            "python/micrograph_measure.py::measure",
            "python/micrograph_measure.py::intercept_statistics",
            "routes/copilot.ts",
            "server/openaiService.ts:42#request.timeoutMs ?? 60_000",
            "src/components/MicrographLab.tsx::MicrographLab",
            "src/components/MicrographAdvisoryDescription.tsx::MicrographAdvisoryDescription",
            "src/components/MicrographMeasureStudio.tsx::MicrographMeasureStudio",
            "src/services/micrographMeasureService.ts::measureMicrograph",
            "src/utils/micrographInput.ts::buildMeasureRequest",
            "docs/MODULE_EVIDENCE_INVENTORY.md:64#`micrograph` /",
        ),
    )


def _pilot(row, *, reviewed, operation, evidence, oracle, lifecycle, notes, sources,
           extra_operations=(), version=None) -> ModuleContract:
    """Contract around one operation (plus ``extra_operations`` when a view serves more than one).
    ``reviewed`` replaces seed identity text (SEED_TEXT_FIELDS); every field not replaced is recorded
    as seed-derived (unreviewed). ``version`` overrides CONTRACT_VERSION for a bumped contract."""
    slug = row["id"].replace("-", "_")
    seed = {"label": row["label"], "description": row["description"], "next": row["next"], "maturity": row["scope"]}
    unknown = set(reviewed) - set(SEED_TEXT_FIELDS)
    if unknown:
        raise ValueError(f"{row['id']}: reviewed names non-seed fields {sorted(unknown)}")
    text = {**seed, **reviewed}
    return ModuleContract(
        id=row["id"], version=version or CONTRACT_VERSION, owner=OWNER_UNASSIGNED, workspace=row["workspace"],
        label=text["label"], description=text["description"], next=text["next"], maturity=text["maturity"],
        navigation="listed", seed_derived=tuple(f for f in SEED_TEXT_FIELDS if f not in reviewed),
        view=View(component=row["viewComponent"], export=row["viewExport"]),
        evidence=evidence,
        tests=TestRefs(oracle=oracle, schema=f"python/test_contract_{slug}.py", docs=module_doc_path(row["id"])),
        migration_state="contracted", operations=(operation, *extra_operations), lifecycle=lifecycle,
        legacy_notes=notes, source_refs=sources,
    )


def module_doc_path(module_id: str) -> str:
    return f"docs/modules/{module_id}.md"


CONTRACTED_BUILDERS = {
    "database": build_database_contract,
    "phase-diagram": build_calphad_contract,
    "experimental-data": build_experimental_data_contract,
    "traceability": build_traceability_contract,
    "alloy-builder": build_composition_contract,
    "materials-project": build_elasticity_contract,
    "eds-lab": build_eds_contract,
    "lpbf-dataset-comparison": build_dataset_view_contract,
    "lpbf-calibration-scorecard": build_calibration_scorecard_contract,
    "keyhole-raytracing": _keyhole_contract,
    "uq-lab": _uq_contract,
    # Phase 7 wave 2
    "ttt-cct-kinetics": _kinetics_contract,
    "icme-motor": _icme_contract,
    "murakami-fatigue": _fatigue_contract,
    "toolpath-studio": _toolpath_contract,
    # Micrograph rework (python/micrograph_measure.py authority)
    "micrograph": _micrograph_contract,
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


# path | path:start[-end]#expected text | path::Symbol | path::Class.method
_LINE_REF = re.compile(r"^(?P<path>[^:#]+?)(?::(?P<start>\d+)(?:-(?P<end>\d+))?(?:#(?P<expect>.+))?)?$")
_SYMBOL_REF = re.compile(r"^(?P<path>[^:#]+)::(?P<symbol>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)$")


def _python_symbol_problem(text: str, symbol: str) -> str:
    """'' when ``symbol`` (top-level name or Class.method) is defined in the Python source."""
    import ast
    body = ast.parse(text).body

    def defined(nodes, name):
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
                return node
            if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
                return node
            if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == name:
                return node
        return None

    owner, _, member = symbol.partition(".")
    node = defined(body, owner)
    if node is None:
        return f"{owner} is not defined at module level"
    if member:
        if not isinstance(node, ast.ClassDef):
            return f"{owner} is not a class"
        if not isinstance(defined(node.body, member), (ast.FunctionDef, ast.AsyncFunctionDef)):
            return f"class {owner} has no method {member}"
    return ""


def _ts_symbol_problem(text: str, symbol: str) -> str:
    """'' when ``symbol`` is declared in TS/TSX source: a function, class, const/let, or a
    class/object method at the start of a line (call sites such as ``obj.name(`` never match)."""
    owner, _, member = symbol.partition(".")
    name = member or owner
    declaration = re.compile(
        rf"^\s*(?:export\s+)?(?:default\s+)?(?:(?:public|private|protected|static|readonly)\s+)*(?:async\s+)?"
        rf"(?:function\s*\*?\s*|class\s+|const\s+|let\s+|var\s+)?"
        rf"{re.escape(name)}\s*[(<=:]", re.MULTILINE)
    if not declaration.search(text):
        return f"{name} is not declared"
    if member and not re.search(rf"^\s*(?:export\s+)?(?:class|const|let|var)\s+{re.escape(owner)}\b", text, re.MULTILINE):
        return f"{owner} is not declared"
    return ""


def contract_refs(contract: ModuleContract) -> List[str]:
    """Every repository reference a contract makes (view, scripts, tests, docs, sources)."""
    refs = [contract.view.component]
    refs += [op.authority.script for op in contract.operations if op.authority.script]
    refs += [r for r in (contract.tests.schema, contract.tests.docs, contract.tests.oracle.ref) if r]
    refs += list(contract.source_refs)
    if contract.validity_domain:
        refs += list(contract.validity_domain.source_refs)
    return refs


def ref_problem(ref: str, root: Path = REPO_ROOT, generated: frozenset = frozenset()) -> str:
    """Why ``ref`` does not resolve in the repository, or '' when it does.

    Forms:
    - ``path``: the file exists.
    - ``path::Symbol`` / ``path::Class.method``: content anchor. Python is checked with the
      AST (the class must contain the method); TS/TSX by a declaration at line start.
    - ``path:start-end#expected text``: the lines exist and still contain the expected
      text, so a ref whose lines shift fails. A line ref without ``#expected`` is rejected.
    Paths in ``generated`` are emitter outputs; ``stale_outputs`` checks their presence.
    """
    symbol = _SYMBOL_REF.match(ref)
    match = symbol or _LINE_REF.match(ref)
    if not match:
        return f"{ref}: unrecognised reference form"
    rel = match.group("path")
    if rel in generated:
        return ""
    path = (root / rel)
    if rel.startswith(("/", "\\")) or ".." in Path(rel).parts or not path.is_file():
        return f"{ref}: {rel} does not exist"
    text = path.read_text(encoding="utf-8")
    if symbol:
        name = symbol.group("symbol")
        if rel.endswith(".py"):
            problem = _python_symbol_problem(text, name)
        elif rel.endswith((".ts", ".tsx")):
            problem = _ts_symbol_problem(text, name)
        else:
            problem = "symbol anchors apply only to .py/.ts/.tsx files"
        return f"{ref}: {problem} in {rel}" if problem else ""
    if match.group("start"):
        expect = match.group("expect")
        if not expect:
            return f"{ref}: a line reference needs '#<expected text>' so shifted lines are detected"
        start = int(match.group("start"))
        end = int(match.group("end") or start)
        lines = text.splitlines()
        if not 1 <= start <= end <= len(lines):
            return f"{ref}: lines {start}-{end} outside {rel} ({len(lines)} lines)"
        if expect not in "\n".join(lines[start - 1:end]):
            return f"{ref}: {rel}:{start}-{end} no longer contains {expect!r}"
    return ""


CI_LOCK = PYTHON_DIR / "requirements-lpbf.in"  # the CI python job installs only this
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def oracle_ci_module(ref: str) -> str:
    """unittest module name of an oracle reference (path::Class.method)."""
    return Path(ref.split("::")[0]).stem


def oracle_listed_in_ci(ref: str) -> bool:
    """True when the oracle's test module is a word of the CI workflow (the python unittest lists)."""
    text = CI_WORKFLOW.read_text(encoding="utf-8") if CI_WORKFLOW.is_file() else ""
    return re.search(rf"(?<![\w.]){re.escape(oracle_ci_module(ref))}(?![\w.])", text) is not None


def _top_level_imports(path: Path) -> set:
    """Module-level imports, including those guarded by a module-level try/if (an oracle that probes
    `import warp` and skips itself still needs warp to run for real, so the CI gap must still be recorded)."""
    import ast
    names = set()

    def visit(statements):
        for node in statements:
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
            elif isinstance(node, ast.Try):
                visit(node.body)
                for handler in node.handlers:
                    visit(handler.body)
                visit(node.orelse)
                visit(node.finalbody)
            elif isinstance(node, ast.If):
                visit(node.body)
                visit(node.orelse)

    visit(ast.parse(path.read_text(encoding="utf-8")).body)
    return names


def oracle_ci_missing_packages(ref: str) -> List[str]:
    """Third-party packages the oracle test (and the repo modules it imports directly) need
    that the CI CPU lock does not install. Non-empty means the oracle cannot run in CI."""
    oracle = REPO_ROOT / ref.split("::")[0]
    names = _top_level_imports(oracle)
    for name in list(names):
        local = PYTHON_DIR / f"{name}.py"
        if local.is_file():
            names |= _top_level_imports(local)
    lock = {re.split(r"[=<>\[ ]", line.strip())[0].lower()
            for line in CI_LOCK.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")}
    third_party = {n for n in names if n not in sys.stdlib_module_names and not (PYTHON_DIR / f"{n}.py").is_file()}
    return sorted(n for n in third_party if n.lower() not in lock)


def contract_ref_problems(contract: ModuleContract, root: Path = REPO_ROOT,
                          generated: frozenset = frozenset()) -> List[str]:
    return [p for p in (ref_problem(ref, root, generated) for ref in contract_refs(contract)) if p]


def build_registry(seed: List[Dict[str, str]] = None, builders: Dict = None) -> Tuple[ModuleContract, ...]:
    rows = load_seed() if seed is None else seed
    builders = CONTRACTED_BUILDERS if builders is None else builders
    contracts = tuple(builders[row["id"]](row) if row["id"] in builders else legacy_contract(row) for row in rows)
    ids = [c.id for c in contracts]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate module ids in registry")
    known = set(ids)
    for table, name in ((LEGACY_OPERATIONS, "LEGACY_OPERATIONS"), (LEGACY_NOTES, "LEGACY_NOTES"),
                        (builders, "CONTRACTED_BUILDERS")):
        unknown = set(table) - known
        if unknown:
            raise ValueError(f"{name} names unregistered modules: {sorted(unknown)}")
    both = set(LEGACY_OPERATIONS) & set(builders)
    if both:
        raise ValueError(f"contracted modules still listed in LEGACY_OPERATIONS: {sorted(both)}")
    generated = frozenset(module_doc_path(c.id) for c in contracts if c.migration_state == "contracted")
    for contract in contracts:
        if contract.next not in known:
            raise ValueError(f"{contract.id}: next {contract.next!r} is not a registered module")
        if contract.migration_state == "contracted":
            # A contracted module's references must all resolve (design 8: refs must exist).
            problems = contract_ref_problems(contract, generated=generated)
            if problems:
                raise ValueError(f"{contract.id}: unresolved references: {problems}")
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
        "// Full contracts. The app imports this module lazily; the eager slice is moduleRegistryCore.ts.",
        "",
        "import type {",
        "  ContractMaturity, ContractNavigation, ContractWorkspace, EvidenceStatus, EvidenceType, MigrationState, OracleState,",
        "} from './moduleRegistryCore';",
        "",
        f"export type ForbiddenClaimKey = {_union(FORBIDDEN_CLAIM_KEYS)};",
        f"export type AuthorityKind = {_union(AUTHORITY_KINDS)};",
        f"export type GpuMode = {_union(GPU_MODES)};",
        f"export type BackgroundWork = {_union(BACKGROUND_WORK)};",
        f"export type LifecycleResource = {_union(LIFECYCLE_RESOURCES)};",
        "",
        f"export type FieldValueType = {_union(VALUE_TYPES)};",
        "export interface ContractField {",
        "  readonly key: string; readonly label: string; readonly valueType: FieldValueType; readonly unit: string | null;",
        "  readonly displayUnits: readonly string[]; readonly quantityKind: string;",
        "  readonly unitSelector: string | null; readonly unitOptions: Readonly<Record<string, string>>;",
        "  readonly min: number | null; readonly max: number | null; readonly step: number | null;",
        "  readonly default: number | string | boolean; readonly required: boolean; readonly enum: readonly string[];",
        "  readonly note: string | null;",
        "}",
        "export interface ContractAuthority {",
        "  readonly kind: AuthorityKind; readonly script: string | null; readonly workerMethod: string | null;",
        "  readonly timeoutMs: number | null; readonly gpu: GpuMode; readonly warm: boolean; readonly exceptionReason: string | null;",
        "}",
        "export interface ContractOperation {",
        f"  readonly id: string; readonly method: {_union(HTTP_METHODS)} | null; readonly route: string | null;",
        "  readonly authority: ContractAuthority;",
        "  readonly input: readonly ContractField[];",
        "  readonly undeclaredInput: readonly string[];",
        "  readonly output: {",
        "    readonly fields: readonly string[]; readonly statusKey: string | null;",
        "    readonly transportValues: Readonly<Record<string, readonly string[]>>;",
        "    readonly transportObjects: Readonly<Record<string, Readonly<Record<string, readonly string[]>>>>;",
        "  } | null;",
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
        "    readonly schema: string | null;",
        "    readonly oracle: {",
        "      readonly status: OracleState; readonly ref: string | null; readonly ciNote: string | null; readonly scope: string | null;",
        "    };",
        "    readonly docs: string | null;",
        "  };",
        "  readonly migrationState: MigrationState;",
        "  readonly legacyNotes: readonly string[];",
        "  readonly sourceRefs: readonly string[];",
        "  readonly seedDerived: readonly string[];",
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


def _cell(value) -> str:
    if value is None or value == [] or value == ():
        return "—"
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text.replace("|", "\\|")


def render_module_doc(contract: ModuleContract) -> str:
    """Generated reference page for a contracted module (docs/modules/<id>.md)."""
    c = contract
    lines = [
        f"# {c.label} (`{c.id}`)",
        "",
        "> Generated by `python/module_registry.py` from the module contract. Do not edit by hand: edit the",
        "> contract and run `python -m module_contract emit` from `python/`. This page restates the contract;",
        "> it is not a validation report.",
        "",
        f"- Migration state: {c.migration_state}; contract version {c.version}",
        f"- Maturity: {c.maturity} (product maturity, not the evidence status of a result)",
        f"- Workspace: {c.workspace}; owner: {c.owner}",
        "- Seed-derived (copied unreviewed from the module seed): " + (", ".join(c.seed_derived) or "none"),
        f"- View: `{c.view.component}` (`{c.view.export}`)",
        "",
        "## Operations",
    ]
    for op in c.operations:
        a = op.authority
        target = a.script or a.worker_method or a.kind
        lines += [
            "",
            f"### `{op.id}`: `{op.method} {op.route}`",
            "",
            f"Authority: {a.kind} `{target}`; timeout {a.timeout_ms} ms; GPU {a.gpu}; warm {str(a.warm).lower()}.",
            "",
            "| Key | Label | Type | Unit | Min | Max | Step | Default | Note |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for f in op.input:
            kind = f"enum {list(f.enum)}" if f.enum else f.value_type
            lines.append("| " + " | ".join(_cell(v) for v in (
                f"`{f.key}`", f.label, kind, f.unit, f.min, f.max, f.step, f.default, f.note)) + " |")
        lines += [
            "",
            "— = not established from the authority code or a source; the contract states no bound.",
            "All keys are optional at the authority, which applies the listed default when a key is absent."
            if not any(f.required for f in op.input) else "Required keys are marked in the contract JSON.",
        ]
        if op.undeclared_input:
            lines += ["", "Undeclared input keys (read by the authority, not describable by the Field schema): "
                      + ", ".join(f"`{k}`" for k in op.undeclared_input) + "."]
        for field in op.input:
            if field.unit_selector:
                lines += ["", f"`{field.key}` is interpreted in the unit selected by `{field.unit_selector}`: "
                          + ", ".join(f"`{choice}` → `{unit}`" for choice, unit in field.unit_options)
                          + ". No fixed canonical-unit conversion is performed by this contract."]
        if op.output:
            status = (f"evidence status key `{op.output.status_key}`" if op.output.status_key
                      else "no status key, so the output carries no evidence status")
            lines += ["", f"Output fields ({status}): " + ", ".join(f"`{k}`" for k in op.output.fields) + "."]
            for key, values in op.output.transport_values:
                lines += ["", f"`{key}` is a transport field, not an evidence status; values: "
                          + ", ".join(f"`{v}`" for v in values) + "."]
            for key, members in op.output.transport_objects:
                lines += ["", f"`{key}` is an object-valued transport inventory, not evidence or a full metadata schema:"]
                for path, values in members:
                    lines += [f"- `{path}`: " + ", ".join(f"`{v}`" for v in values) + "."]
    e = c.evidence
    oracle = (f"present, `{c.tests.oracle.ref}`" if c.tests.oracle.status == "present"
              else f"pending (ceiling capped at {PENDING_ORACLE_CEILING})")
    lines += [
        "",
        "## Evidence",
        "",
        f"- Ceiling: {e.ceiling} (the strongest class this module may claim; not a result status)",
        f"- Emits: {', '.join(e.emits) if e.emits else 'none'}",
        f"- Forbidden claims: {', '.join(e.forbidden_claims)}",
        f"- Oracle: {oracle}",
        f"- Oracle scope: {c.tests.oracle.scope}" if c.tests.oracle.scope else "- Oracle scope: none",
        f"- Oracle in CI: {c.tests.oracle.ci_note}" if c.tests.oracle.ci_note
        else ("- Oracle in CI: none (oracle pending)" if c.tests.oracle.status == "pending"
              else (f"- Oracle in CI: yes (`{oracle_ci_module(c.tests.oracle.ref)}` is in the "
                    f"{CI_WORKFLOW.relative_to(REPO_ROOT).as_posix()} Python unittest list)"
                    if oracle_listed_in_ci(c.tests.oracle.ref)
                    else f"- Oracle in CI: NOT LISTED (`{oracle_ci_module(c.tests.oracle.ref)}` is missing from "
                         f"{CI_WORKFLOW.relative_to(REPO_ROOT).as_posix()})")),
        f"- Note: {e.note}" if e.note else "- Note: none",
        "",
        "## Validity domain",
        "",
    ]
    if c.validity_domain:
        vd = c.validity_domain
        lines += [f"- `{r.key}`: {r.min} to {r.max} {r.unit}" for r in vd.ranges]
        lines += [f"- Source: {ref}" for ref in vd.source_refs]
    else:
        lines.append("None declared in this contract (any solver-side applicability check is described in the "
                     "recorded notes).")
    lc = c.lifecycle
    lines += [
        "",
        "## Lifecycle",
        "",
        f"Background work: {lc.background_work}; resources: {', '.join(lc.resources) or 'none'}." if lc
        else "Not declared.",
        "",
        "## Recorded notes",
        "",
    ]
    lines += [f"- {note}" for note in c.legacy_notes] or ["None."]
    lines += ["", "## Source references", ""]
    lines += [f"- `{ref}`" for ref in c.source_refs]
    lines += ["", "## Tests", "", f"- Contract scaffold: `{c.tests.schema}`", ""]
    return "\n".join(lines)


# Keys of the eager slice. Everything else (operations, fields, notes, refs, lifecycle,
# validity domain, forbidden claims) stays in the lazily imported full registry.
CORE_CONTRACT_KEYS = ("id", "version", "workspace", "label", "description", "next", "maturity",
                      "navigation", "hiddenReason", "view", "migrationState")


def core_document(document: dict) -> dict:
    """Eager projection of the registry document: navigation identity plus badge data."""
    def core(contract: dict) -> dict:
        slim = {key: contract[key] for key in CORE_CONTRACT_KEYS}
        slim["evidence"] = {"ceiling": contract["evidence"]["ceiling"]}
        oracle = contract["tests"]["oracle"]
        slim["tests"] = {"oracle": {"status": oracle["status"], "ciNote": oracle["ciNote"], "scope": oracle["scope"]}}
        return slim
    vocabulary = document["vocabulary"]
    return {
        "schemaVersion": document["schemaVersion"],
        "generatedBy": document["generatedBy"],
        "vocabulary": {key: vocabulary[key] for key in ("evidenceTypes", "pendingOracleCeiling", "maturity",
                                                         "navigation", "migrationStates")},
        "contracts": [core(contract) for contract in document["contracts"]],
    }


def render_core_ts(document: dict) -> str:
    body = json.dumps(core_document(document), indent=2, ensure_ascii=False)
    lines = [
        "// GENERATED by python/module_registry.py. Do not edit by hand.",
        "// Regenerate: python -m module_contract emit (from python/) or python scripts/emit-module-registry.py",
        "// Eager slice of the module registry (navigation + evidence badge). Full contracts: moduleRegistry.ts.",
        "",
        f"export type EvidenceType = {_union(EVIDENCE_TYPES)};",
        f"export type RunState = {_union(RUN_STATES)};",
        "export type EvidenceStatus = EvidenceType | RunState;",
        f"export type ContractMaturity = {_union(MATURITY)};",
        f"export type ContractNavigation = {_union(NAVIGATION)};",
        f"export type ContractWorkspace = {_union(WORKSPACES)};",
        f"export type OracleState = {_union(ORACLE_STATES)};",
        f"export type MigrationState = {_union(MIGRATION_STATES)};",
        "",
        "export interface ModuleContractCore {",
        "  readonly id: string; readonly version: string; readonly workspace: ContractWorkspace;",
        "  readonly label: string; readonly description: string; readonly next: string;",
        "  readonly maturity: ContractMaturity; readonly navigation: ContractNavigation; readonly hiddenReason: string | null;",
        "  readonly view: { readonly component: string; readonly export: string };",
        "  readonly migrationState: MigrationState;",
        "  readonly evidence: { readonly ceiling: EvidenceType };",
        "  readonly tests: {",
        "    readonly oracle: { readonly status: OracleState; readonly ciNote: string | null; readonly scope: string | null };",
        "  };",
        "}",
        "export interface ModuleRegistryCoreDocument {",
        "  readonly schemaVersion: number; readonly generatedBy: string;",
        "  readonly vocabulary: Readonly<Record<string, string | readonly string[]>>;",
        "  readonly contracts: readonly ModuleContractCore[];",
        "}",
        "",
        f"export const MODULE_REGISTRY_CORE = {body} as const satisfies ModuleRegistryCoreDocument;",
        "",
    ]
    return "\n".join(lines)


def rendered_outputs() -> Dict[Path, str]:
    contracts = build_registry()
    document = registry_document(contracts)
    outputs = {GENERATED_JSON: render_json(document), GENERATED_TS: render_ts(document),
               GENERATED_CORE_TS: render_core_ts(document)}
    for contract in contracts:
        if contract.migration_state == "contracted":
            outputs[REPO_ROOT / module_doc_path(contract.id)] = render_module_doc(contract)
    return outputs


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
