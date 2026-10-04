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
_CANNED_QUALIFY = ("POST /api/metallurgy/qualify-aerospace returns constant values (qualified: true) "
                   "without calling any authority; not bound as an operation.")

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
        _op("stl-slicer-build-time", "POST", "/api/python/stl-slicer-build-time",
            _py("stl_slicer_build_time_solver", _PHYSICS_TIMEOUT_MS, warm=True)),
        _op("lpbf-source-catalog", "GET", "/api/lpbf/sources", _NODE),
        _op("lpbf-run-archive", "GET", "/api/lpbf/runs", _NODE),
    ),
    "lpbf-optimizer": (
        _op("bayesian-optimize", "POST", "/api/python/lpbf-bayesian-optimize",
            _py("lpbf_bayesian_optimizer", 120000, warm=False)),
    ),
    "solidification-microstructure": (_worker_op("solidification-microstructure"),),
    "thermomechanical-distortion": (_worker_op("thermomechanical-distortion"),),
    "experimental-validation": (
        _op("lpbf-source-measurements", "GET", "/api/lpbf/sources/:datasetId/measurements", _NODE),
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
    "database": (
        _local("catalog-lookup", "material records are read from the bundled src/data/materialsDatabase.ts in the browser."),
    ),
    "alloy-builder": (_THERMAL_SOLVER,),
    "phase-diagram": (
        _op("calphad-databases", "GET", "/api/python/calphad-databases", _py("calphad_solver", 15000, warm=True)),
        _op("calphad-minimize", "POST", "/api/python/calphad-minimize", _py("calphad_solver", 40000, warm=True)),
        _AI_CONSULT,
    ),
    "ttt-cct-kinetics": (
        _op("kinetics-ttt-cct", "POST", "/api/python/kinetics-ttt-cct",
            _py("kinetics_ttt_cct_solver", _PHYSICS_TIMEOUT_MS, warm=True)),
    ),
    "micrograph": (
        _op("diagnose-micrograph", "POST", "/api/metallurgy/diagnose-micrograph", _NODE),
        _AI_CONSULT,
    ),
    "eds-lab": (_AI_CONSULT,),
    "electrochem-suite": (
        _op("pourbaix-diagram", "POST", "/api/python/pourbaix-diagram", _py("pourbaix_solver", _PHYSICS_TIMEOUT_MS, warm=True)),
        _op("tafel-corrosion-rate", "POST", "/api/python/tafel-corrosion-rate",
            _py("tafel_corrosion_rate_solver", _CHARACTERIZATION_TIMEOUT_MS, warm=True)),
        _op("battery-corrosion-eis", "POST", "/api/python/battery-corrosion-eis",
            _py("battery_corrosion_eis_solver", _CHARACTERIZATION_TIMEOUT_MS, warm=True)),
    ),
    "icme-motor": (
        _op("icme-multiscale-pipeline", "POST", "/api/python/icme-multiscale-pipeline",
            _py("icme_multiscale_pipeline_solver", _PHYSICS_TIMEOUT_MS, warm=True)),
    ),
    "materials-project": (
        _op("dft-properties", "POST", "/api/python/dft-properties",
            _py("dft_property_calculator", _PHYSICS_TIMEOUT_MS, warm=True)),
        _op("metallurgy-consult", "POST", "/api/metallurgy/consult", _NODE),
    ),
    "calculators": (
        _local("engineering-correlations", "unit-aware engineering correlations are evaluated in the browser."),
    ),
    "research-hub": (
        _op("research-registry", "GET", "/api/research/registry", _NODE),
        _op("research-registry-save", "PUT", "/api/research/registry", _NODE),
        _op("research-search", "GET", "/api/research/search", _NODE),
    ),
    "experimental-data": (),
    "digital-twin": (_AI_CONSULT,),
    "qualification": (
        _local("coupon-statistics", "protocol screening and coupon statistics are computed in the browser."),
    ),
    "aerospace-pdf-audit": (
        _local("report-template", "demonstration report templates are assembled in the browser."),
    ),
    "traceability": (),
    "copilot": (_op("metallurgy-consult", "POST", "/api/metallurgy/consult", _NODE),),
    "ai-orchestrator": (_op("dataset-plan", "POST", "/api/orchestrator/dataset-plan", _NODE),),
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
    "materials-project": (
        "GET /api/materials-project/search returns a hard-coded record list (routes/copilot.ts "
        "MATERIALS_PROJECT_VERIFIED_DATA) labelled 'Verified Materials Project Physical DFT Reference "
        "Catalog' without calling any authority; not bound as an operation (canned; deletion/follow-up "
        "candidate).",
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
            "total_absorbed_W", "total_escaped_W", "total_truncated_W", "energy_balance_relative_error",
            "absorption_efficiency", "sampling", "inputs", "limitations", "mesh", "ray_paths"),
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
    _num("initialFlawSize_um_mean", "Initial flaw size mean", _MICRO, "length", 45.0,
         note="No bound is enforced; each draw is floored at 5 µm."),
    _num("initialFlawSize_um_std", "Initial flaw size standard deviation", _MICRO, "length", 15.0),
    _num("specMinYield_MPa", "Specification minimum yield strength", "MPa", "stress", 1100.0),
    _num("specMinUTS_MPa", "Specification minimum UTS", "MPa", "stress", 1350.0),
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
    "Emits no evidence status: the output has no status key. aerospaceReliability.qualificationStatus is "
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
                                           "(NVIDIA Warp; CPU by default, CUDA optional); empirical absorption, "
                                           "not a solved keyhole."},
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
                      "routes/lpbfSimulation.ts:44#/api/python/lpbf-keyhole-raytracing",
                      "server/lpbfWorkerBridge.ts:58#requestTimeoutMs ?? 20000",
                      "src/components/KeyholeRaytracingLab.tsx::KeyholeRaytracingLab",
                      "docs/MODULE_EVIDENCE_INVENTORY.md:40#`keyhole-raytracing` / Keyhole Ray Tracing",
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
                      "The view offers 'Pseudo-MC', which the authority rejects; python/test_stochastic_uq_evidence.py "
                      "still expects pseudo_mc to succeed and errors in setUpClass (observed in Phase 7 wave 1).",
                      "Coupon statistics over uploaded or synthetic coupons (computeMMPDSEmpiricalStats in "
                      "src/components/uqLabData.ts) run in the browser: recorded single-authority debt, not bound as "
                      "an operation because the code declares no route or deadline for it.",
                      "No validity domain is declared: no source-backed applicability range exists for the "
                      "strengthening model or the input distributions.",
                      _UQ_WARM_NOTE,
                  ),
                  # Content-anchored: symbols, or line ranges that must still contain the quoted text.
                  # pythonComputationService.ts is anchored by symbol because other lanes delete lines there.
                  sources=(
                      "python/stochastic_uq_mmpds_solver.py::solve_stochastic_uq",
                      "python/stochastic_uq_mmpds_solver.py:398#Pseudo-Random Monte Carlo is disabled",
                      "python/stochastic_uq_mmpds_solver.py::provenance",
                      "python/alloy_data_kinetics_uq_fatigue.py::UQ_BASE_METAL_LATTICE",
                      "python/alloy_data_kinetics_uq_fatigue.py::uq_lattice_constants",
                      "python/alloy_data_kinetics_uq_fatigue.py::UQ_DEFAULT_BASE_METAL",
                      "routes/physics.ts::handlePythonDispatch",
                      "python/persistent_ipc_service.py::WARM_MODULE_NAMES",
                      "server/processOrchestrator.ts::PersistentPythonIPCSupervisor.execute",
                      "routes/physics.ts:120-121#python/stochastic_uq_mmpds_solver.py",
                      "src/components/UQLab.tsx::UQLab",
                      "src/components/UQLab.tsx::runQMCSolver",
                      "src/components/uqLabData.ts::computeMMPDSEmpiricalStats",
                      "src/services/pythonComputationService.ts::calculateStochasticUQMMPDS",
                      "docs/MODULE_EVIDENCE_INVENTORY.md:77#`uq-lab` / Uncertainty & Coupons",
                  ))


def _pilot(row, *, reviewed, operation, evidence, oracle, lifecycle, notes, sources) -> ModuleContract:
    """Contract around one operation. ``reviewed`` replaces seed identity text (SEED_TEXT_FIELDS);
    every field not replaced is recorded as seed-derived (unreviewed)."""
    slug = row["id"].replace("-", "_")
    seed = {"label": row["label"], "description": row["description"], "next": row["next"], "maturity": row["scope"]}
    unknown = set(reviewed) - set(SEED_TEXT_FIELDS)
    if unknown:
        raise ValueError(f"{row['id']}: reviewed names non-seed fields {sorted(unknown)}")
    text = {**seed, **reviewed}
    return ModuleContract(
        id=row["id"], version=CONTRACT_VERSION, owner=OWNER_UNASSIGNED, workspace=row["workspace"],
        label=text["label"], description=text["description"], next=text["next"], maturity=text["maturity"],
        navigation="listed", seed_derived=tuple(f for f in SEED_TEXT_FIELDS if f not in reviewed),
        view=View(component=row["viewComponent"], export=row["viewExport"]),
        evidence=evidence,
        tests=TestRefs(oracle=oracle, schema=f"python/test_contract_{slug}.py", docs=module_doc_path(row["id"])),
        migration_state="contracted", operations=(operation,), lifecycle=lifecycle,
        legacy_notes=notes, source_refs=sources,
    )


def module_doc_path(module_id: str) -> str:
    return f"docs/modules/{module_id}.md"


CONTRACTED_BUILDERS = {
    "keyhole-raytracing": _keyhole_contract,
    "uq-lab": _uq_contract,
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


def _top_level_imports(path: Path) -> set:
    import ast
    names = set()
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
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
        if op.output:
            status = (f"evidence status key `{op.output.status_key}`" if op.output.status_key
                      else "no status key, so the output carries no evidence status")
            lines += ["", f"Output fields ({status}): " + ", ".join(f"`{k}`" for k in op.output.fields) + "."]
            for key, values in op.output.transport_values:
                lines += ["", f"`{key}` is a transport field, not an evidence status; values: "
                          + ", ".join(f"`{v}`" for v in values) + "."]
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
        f"- Oracle in CI: {c.tests.oracle.ci_note}" if c.tests.oracle.ci_note else "- Oracle in CI: no recorded gap",
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
        lines.append("None declared: no source-backed applicability range is established.")
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
