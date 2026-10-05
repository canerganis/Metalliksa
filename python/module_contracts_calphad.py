"""Source-bound Module SDK contract for the rendered phase-diagram module.

The view contains both a real Python/pycalphad path and explicitly selectable
browser screening paths. The latter are not a recovery path for Python errors.
"""
from module_contract import (
    Authority, Evidence, FORBIDDEN_CLAIM_KEYS, InputField, Lifecycle,
    ModuleContract, Operation, Oracle, OutputSchema, OWNER_UNASSIGNED,
    PENDING_ORACLE_CEILING, TestRefs, View,
)


CONTRACT_VERSION = "0.1.0"


def _selector(key, label, values, default, note):
    return InputField(key=key, label=label, unit=None, quantity_kind="selection",
                      min=None, max=None, default=default, value_type="enum",
                      enum=tuple(values), note=note)


def _number(key, label, unit, quantity_kind, default, note, *, minimum=None, maximum=None):
    return InputField(key=key, label=label, unit=unit, quantity_kind=quantity_kind,
                      min=minimum, max=maximum, default=default, value_type="number", note=note)


def _boolean(key, label, default, note):
    return InputField(key=key, label=label, unit=None, quantity_kind="configuration",
                      min=None, max=None, default=default, value_type="boolean", note=note)


def _python_authority(timeout_ms):
    return Authority(kind="python-ipc", script="python/calphad_solver.py",
                     timeout_ms=timeout_ms, warm=True)


def build_calphad_contract(seed) -> ModuleContract:
    """Describe the actual rendered phase-diagram view without changing its registry seed."""
    if seed["id"] != "phase-diagram":
        raise ValueError("CALPHAD preserves the phase-diagram module identity")

    database_operation = Operation(
        id="calphad-databases", method="GET", route="/api/python/calphad-databases",
        authority=_python_authority(15000),
        output=OutputSchema(fields=("success", "engine", "pycalphadAvailable", "pycalphadVersion",
                                    "unavailableReason", "databasesCount", "usableDatabasesCount",
                                    "databases", "installedFiles", "systemCoverage", "modelCache"),
                            status_key=None),
    )
    minimize = Operation(
        id="calphad-minimize", method="POST", route="/api/python/calphad-minimize",
        authority=_python_authority(40000),
        input=(
            _number("tMin", "Minimum temperature", "degC", "temperature", 500.0,
                    "Direct solver default is 500 degC. The mounted UI always sends a base-element-selected "
                    "window: Al 400–750 degC, Mg 350–700 degC, Ti 600–1750 degC, otherwise 500–1550 degC; "
                    "the UI also sends its step (10 degC for Al/Mg, otherwise 25 degC). No solver hard bound "
                    "is declared for these request values."),
            _number("tMax", "Maximum temperature", "degC", "temperature", 1450.0,
                    "Direct solver default is 1450 degC. UI-selected windows are documented on tMin; "
                    "they depend on the largest alloy element."),
            _number("tStep", "Temperature grid step", "degC", "temperature-step", 20.0,
                    "Direct solver default is 20 degC. UI passes 10 or 25 degC from the selected base-element "
                    "window. The Python solver caps the actual uniform grid at 80 points; these UI values "
                    "are not backend bounds."),
            _selector("unit", "Composition unit", ("wt_pct", "at_pct"), "wt_pct",
                      "UI sends wt_pct for the live specimen; the authority also accepts at_pct."),
            _boolean("adaptiveGrid", "Adaptive grid", False,
                     "The UI sends false; the engine has a uniform grid, not an adaptive grid."),
            _boolean("boundaryRefinement", "Boundary refinement", True,
                     "UI toggle; when enabled, repeated equilibrium calculations refine liquidus/solidus."),
            _number("minRefineStep", "Boundary tolerance", "degC", "temperature-tolerance", 0.5,
                    "The UI selector offers the discrete values 0.2, 0.5, 1.0, and 2.0 degC. Direct Python "
                    "requests are not restricted to those options; the solver uses max(0.05 degC, requested "
                    "value) as its refinement tolerance and declares no upper bound."),
        ),
        undeclared_input=("name", "elements", "databaseId", "customTdbText", "supersedeKey"),
        output=OutputSchema(
            fields=("success", "status", "unavailableKind", "reason", "reasons", "engine",
                    "pycalphadAvailable", "pycalphadVersion", "alloyName", "nominalComposition",
                    "atomicFractions", "requestedElements", "baseElement", "databaseId", "databaseUsed",
                    "databaseSuitability", "databasePath", "missingElements", "databasesConsidered",
                    "temperatureRangeC",
                    "temperatureStepC", "thermodynamicModel", "isEmpirical", "equilibriumCalls",
                    "activeComponents", "dependentComponent", "unsupportedElements", "compositionAdjustments",
                    "gridPoints", "equilibriumProfile", "criticalTemperatures",
                    "phacompAnalysis", "solutePartitioning", "multiElementScheil",
                    "multiElementScheilNote", "scheilSolidification", "thermodynamicStabilityIndex",
                    "tcpEmbrittlementRisk", "nonConvergedPoints", "boundaryRefinement", "phaseNameNotes",
                    "computeTimeMs", "timingsMs", "modelCache", "provenance", "isPythonEngine",
                    "pythonUnavailable",
                    "error", "errorKind", "field", "extra", "rawOutput", "stderr", "script"),
            status_key=None, transport_values=(("status", ("unavailable",)),),
        ),
    )
    client_screening = Operation(
        id="client-screening", route=None,
        authority=Authority(kind="browser-local", timeout_ms=None,
                            exception_reason="Explicit Python-engine-off mode calls the existing TypeScript "
                                            "screening solver; this is recorded single-authority debt."),
        input=(
            _boolean("usePython", "Use Python engine", False,
                     "This operation is selected only when the user explicitly turns the Python engine off; "
                     "Python request failure does not enter this path."),
            _number("tMin", "Minimum temperature", "degC", "temperature", 500.0,
                    "Passed from the same base-element window as the Python request; that selection is not a "
                    "bound on the browser solver input."),
            _number("tMax", "Maximum temperature", "degC", "temperature", 1550.0,
                    "Passed from the same base-element window as the Python request; that selection is not a "
                    "bound on the browser solver input."),
            _number("tStep", "Temperature grid step", "degC", "temperature-step", 25.0,
                    "Passed from the same base-element window as the Python request; that selection is not a "
                    "bound on the browser solver input."),
        ),
        undeclared_input=("alloy", "selectedTdbIndex", "activeTdbContent"),
        output=OutputSchema(fields=("engine", "isPythonEngine", "isEmpirical", "thermodynamicModel",
                                    "databaseUsed", "iterations", "equilibriumProfile", "criticalTemperatures",
                                    "solutePartitioning", "multiElementScheil", "temperatureRangeC",
                                    "temperatureStepC"), status_key=None),
    )
    binary_browser = Operation(
        id="binary-browser-analysis", route=None,
        authority=Authority(kind="browser-local", timeout_ms=None,
                            exception_reason="The rendered CALPHAD lab still evaluates its bundled binary "
                                            "Gibbs models in the browser; this is legacy single-authority debt."),
        input=(
            _number("temperatureC", "Probe temperature", "degC", "temperature", 850.0,
                    "Initial probe is 850 degC for Fe-C; changing system selects other UI presets. No physical "
                    "applicability bound is established by the UI."),
            _number("compositionB", "Component B content", "%", "composition-percentage", 0.45,
                    "Initial Fe-C probe is 0.45 wt%; other systems use at.% or wt.% as declared by the "
                    "selected browser model. System-specific values are selected in the UI."),
        ),
        undeclared_input=("selectedSystemId",),
        output=OutputSchema(fields=("gxChartData", "equilibriumState", "scheilResult", "tdbText"), status_key=None),
    )
    consultation = Operation(
        id="ai-consult", method="POST", route="/api/consult",
        authority=Authority(kind="node-provider", timeout_ms=60000),
        undeclared_input=("prompt",),
        output=OutputSchema(fields=("response", "reply", "text", "answer", "error"), status_key=None),
    )

    return ModuleContract(
        id=seed["id"], version=CONTRACT_VERSION, owner=OWNER_UNASSIGNED,
        workspace=seed["workspace"], label=seed["label"], description=seed["description"],
        next=seed["next"], maturity=seed["scope"], navigation="listed",
        view=View(component=seed["viewComponent"], export=seed["viewExport"]),
        migration_state="contracted",
        operations=(database_operation, minimize, client_screening, binary_browser, consultation),
        lifecycle=Lifecycle(background_work="none", resources=("fetch", "interval")),
        evidence=Evidence(
            emits=(), ceiling=PENDING_ORACLE_CEILING, forbidden_claims=FORBIDDEN_CLAIM_KEYS,
            note="No evidence status is emitted and no numerical oracle is declared. A successful pycalphad "
                 "calculation is solver output, not independent numerical or experimental validation; browser "
                 "screening and bundled binary calculations have no demonstrated applicability domain.",
        ),
        tests=TestRefs(oracle=Oracle(status="pending"), schema="python/test_module_contract_calphad.py",
                       docs="docs/modules/phase-diagram.md"),
        legacy_notes=(
            "The registered phase-diagram view is src/components/PhaseDiagramViewer.tsx; its default view "
            "renders CALPHADThermodynamicsLab, which mounts CALPHADMultiComponentStudio. On mount the studio "
            "requests /api/python/status as an infrastructure health check and /api/python/calphad-databases, "
            "then schedules a minimization after "
            "a short debounce; edits/supersession abort stale client requests. The 250 ms interval only updates "
            "elapsed-time display while solving. No scientific deadline/progress estimate is exposed by that timer.",
            "The Python minimizer has no fallback calculation: missing pycalphad, missing/unassessed database "
            "coverage, missing elements, refused test-fixture TDBs, or equilibrium failure yields an unavailable "
            "envelope without equilibrium/critical-temperature numbers. HTTP 422 validation refusal is displayed "
            "without a client substitute. The visible client solver is reached only after the user explicitly "
            "turns the Python engine off; it is marked empirical/screening and is not the fallback for failure.",
            "The minimization request's elements map, custom TDB text, and alloy name are dynamic values and are "
            "undeclared inputs. UI temperature window/step is derived from the largest element: Al 400–750/10 degC, "
            "Mg 350–700/10 degC, Ti 600–1750/25 degC, otherwise 500–1550/25 degC. Direct Python defaults are "
            "500/1450/20 degC. The UI sends adaptiveGrid=false, boundaryRefinement=true by default and a selectable "
            "0.2/0.5/1/2 degC tolerance; no blanket hard temperature applicability limits are asserted.",
            "The legacy binary lab also computes G-x curves, a browser phase-equilibrium estimate, Scheil-style "
            "solidification and TDB export from bundled TypeScript tables/functions. The 'AI CALPHAD Diagnosis' "
            "button submits binary-system prompt text to /api/consult; service failure or empty/malformed "
            "response leaves the consultation unavailable instead of fabricating a scientific report. Input "
            "changes and unmount abort/invalidate the request. A provider response is not an independently "
            "validated CALPHAD result. Neither browser path is promoted as Python output.",
            "The SDK output fields are conditional inventories. Database coverage entries can say covered or "
            "unavailable, but coverage is an element/base-assessment check, not experimental agreement. Solver "
            "'status=unavailable' is transport state only; no evidence status is emitted. Nested "
            "databaseStatus/criticalTemperatureStatus and multiElementScheilStatus carry richer values the SDK "
            "transport schema cannot type, so those nested keys are intentionally not declared as output fields. "
            "Output numbers depend "
            "on the selected assessed database and conditions; no numerical oracle or physical domain is claimed.",
        ),
        source_refs=(
            "python/module_registry.py::build_registry",
            "src/App.tsx:190-190#case 'phase-diagram': return <PhaseDiagramViewer />;",
            "src/modules/views.ts:23-23#'phase-diagram': lazy(",
            "src/components/PhaseDiagramViewer.tsx::PhaseDiagramViewer",
            "src/components/CALPHADThermodynamicsLab.tsx::CALPHADThermodynamicsLab",
            "src/utils/calphadConsultation.ts::parseConsultationResponse",
            "src/components/CALPHADMultiComponentStudio.tsx::CALPHADMultiComponentStudio",
            "src/services/pythonComputationService.ts::PythonComputationService.getCalphadDatabases",
            "src/services/pythonComputationService.ts::PythonComputationService.solveCalphadEquilibrium",
            "src/utils/calphadResultDisplay.ts::calphadTemperatureWindow",
            "routes/physics.ts:58-63#physicsRouter.post([\"/api/python/calphad-minimize\"",
            "routes/physics.ts:62-63#physicsRouter.get([\"/api/python/calphad-databases\"",
            "routes/copilot.ts:23-52#copilotRouter.post([\"/api/metallurgy/consult\"",
            "server/openaiService.ts::generateGpt6Response",
            "python/calphad_solver.py::list_available_databases",
            "python/calphad_solver.py::normalize_composition",
            "python/calphad_solver.py::unavailable_result",
            "python/calphad_solver.py::resolve_database",
            "python/calphad_solver.py::solve_pycalphad_equilibrium",
            "python/calphad_solver.py::compute_multi_component_equilibrium",
            "python/calphad_solver.py::main",
            "src/physics/calphadMultiComponentSolver.ts::solveMultiComponentEquilibrium",
            "src/physics/calphadGibbsEngine.ts::calculatePhaseEquilibrium",
            "src/physics/calphadGibbsEngine.ts::simulateScheilSolidification",
            "python/test_module_contract_calphad.py",
        ),
        seed_derived=("label", "description", "next", "maturity"),
    )
