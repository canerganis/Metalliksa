"""Source-bounded SDK contract for CorrosionEngineeringLab and its reachable children."""
from __future__ import annotations

from typing import Mapping, Tuple

from module_contract import (
    ALWAYS_FORBIDDEN_CLAIMS,
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


CONTRACT_VERSION = "0.1.0"
_PYTHON_TIMEOUT_PHYSICS_MS = 25000
_PYTHON_TIMEOUT_CHARACTERIZATION_MS = 15000


def _enum(key: str, label: str, quantity: str, default: str, values: Tuple[str, ...]) -> InputField:
    return InputField(key=key, label=label, unit=None, quantity_kind=quantity, min=None, max=None,
                      default=default, value_type="enum", enum=values, required=True)


def _number(key: str, label: str, unit: str, quantity: str, default: float, *, note: str) -> InputField:
    return InputField(key=key, label=label, unit=unit, quantity_kind=quantity, min=None, max=None,
                      default=default, required=True, note=note)


def _local(operation_id: str, *, fields: Tuple[InputField, ...] = (),
           undeclared: Tuple[str, ...] = (), outputs: Tuple[str, ...]) -> Operation:
    return Operation(
        id=operation_id, route=None, method=None,
        authority=Authority(kind="browser-local", timeout_ms=None,
                            exception_reason="This operation is performed in React local state; it has no HTTP route or declared deadline."),
        input=fields, undeclared_input=undeclared,
        output=OutputSchema(fields=outputs, status_key=None),
    )


def _python(operation_id: str, script: str, timeout_ms: int, *, fields: Tuple[InputField, ...] = (),
            undeclared: Tuple[str, ...] = (), outputs: Tuple[str, ...],
            transport_values: Tuple[Tuple[str, Tuple[str, ...]], ...] = ()) -> Operation:
    return Operation(
        id=operation_id, route={
            "python/pourbaix_solver.py": "/api/python/pourbaix-diagram",
            "python/tafel_corrosion_rate_solver.py": "/api/python/tafel-corrosion-rate",
            "python/battery_corrosion_eis_solver.py": "/api/python/battery-corrosion-eis",
        }[script], method="POST",
        authority=Authority(kind="python-ipc", script=script, timeout_ms=timeout_ms, warm=True),
        input=fields, undeclared_input=undeclared,
        output=OutputSchema(fields=outputs, status_key=None, transport_values=transport_values),
    )


_VIEW_TABS = ("pren", "polarization", "pourbaix", "corrosion-eis")
_RUN_STATUS = (("status", ("partial", "unavailable")),)
_TAFEL_STATUS = (
    ("fitStatus", ("unavailable",)),
    ("intersectionStatus", ("substituted-measured-valley",)),
)


ELECTROCHEM_OPERATIONS: Tuple[Operation, ...] = (
    _local("select-corrosion-view", fields=(_enum(
        "activeTab", "Selected corrosion view", "ui-view", "corrosion-eis", _VIEW_TABS,
    ),), outputs=("activeTab",)),
    _local("calculate-pren", fields=(
        _number("cr", "Chromium content", "wt.%", "element-content", 22.0,
                note="Default from the local UI; the displayed slider extent is not a validity domain."),
        _number("mo", "Molybdenum content", "wt.%", "element-content", 3.2,
                note="Default from the local UI; the displayed slider extent is not a validity domain."),
        _number("w", "Tungsten content", "wt.%", "element-content", 0.0,
                note="Default from the local UI; the displayed slider extent is not a validity domain."),
        _number("n", "Nitrogen content", "wt.%", "element-content", 0.18,
                note="Default from the local UI; the displayed slider extent is not a validity domain."),
    ), outputs=("prenScore",)),
    _local("apply-pren-alloy-preset", undeclared=("presetLabel",),
           outputs=("cr", "mo", "w", "n", "prenScore")),
    _local("import-tafel-dataset", undeclared=("file", "parsedDataset"),
           outputs=("dataset", "loadError", "parseError", "pythonFitResult",
                    "isPythonFitting", "pythonFitError")),
    _local("estimate-tafel-locally", undeclared=("dataset", "electrodeMetadata", "fitWindows", "manualOverrides"),
           outputs=("fitResult", "unavailableReason", "unavailable")),
    _local("export-tafel-csv", undeclared=("dataset", "localFitResult"), outputs=("csvBlob", "downloadUrl", "downloadAnchor")),
    _local("copy-tafel-summary", undeclared=("dataset", "localFitResult"), outputs=("summaryText", "clipboardWrite", "copyNotification")),
    _local("sync-tafel-to-digital-twin", undeclared=("dataset", "localFitResult", "activeDigitalTwin"),
           outputs=("electrochemistry", "savedToDtNotification")),
    _python("fit-tafel-python", "python/tafel_corrosion_rate_solver.py", _PYTHON_TIMEOUT_CHARACTERIZATION_MS,
            undeclared=("datasetPoints", "datasetMetadata", "fitWindows", "manualOverrides", "selectedAlloyId"),
            outputs=("fitResult", "fitStatus", "intersectionStatus", "pythonFitError"),
            transport_values=_TAFEL_STATUS),
    _python("calculate-annual-corrosion-rate", "python/tafel_corrosion_rate_solver.py",
            _PYTHON_TIMEOUT_CHARACTERIZATION_MS,
            undeclared=("iCorr_uA_cm2", "eCorr_V", "betaA", "betaC", "alloyId", "alloyName",
                        "density_g_cm3", "equivalentWeight", "specimenAreaCm2", "initialThicknessMm",
                        "allowableLossMm", "temperatureC"),
            outputs=("status", "unavailableReason", "corrosionRateMmYr", "corrosionRateMpy",
                     "rp_ohm_cm2", "rulUniformYears"),
            transport_values=_RUN_STATUS),
    _local("manage-pourbaix-test-points", undeclared=("experimentalPoints", "pointAction", "pointFields"),
           outputs=("experimentalPoints", "pointStates", "selectedPointId")),
    _local("select-pourbaix-alloy-element", undeclared=("alloyPresetId", "primaryElement", "refElectrode", "ionActivity"),
           outputs=("selectedAlloyId", "selectedElement", "effectiveIonActivity")),
    _local("set-pourbaix-overlay-display", undeclared=("activeTab", "showExperimentalOverlay", "showTrajectoryPath",
                                                        "showPointLabels", "probePH", "probePotential_SHE", "viewBounds"),
           outputs=("activeTab", "pointStates", "probedState", "viewBounds")),
    _python("solve-pourbaix", "python/pourbaix_solver.py", _PYTHON_TIMEOUT_PHYSICS_MS,
            fields=(_number("temperature_C", "Requested solution temperature", "°C", "temperature", 25.0,
                            note="The reachable UI fixes this to 25 °C; the species data do not support other temperatures."),),
            undeclared=("primaryElement", "effectiveIonActivity", "chlorideActivity", "experimentalPoints"),
            outputs=("pythonPourbaixData", "solverError", "isPythonSolving", "pythonFresh")),
    _python("simulate-corrosion-eis", "python/battery_corrosion_eis_solver.py",
            _PYTHON_TIMEOUT_CHARACTERIZATION_MS,
            undeclared=("action", "metalId", "betaA", "betaC", "i0Corr_uA", "ePit", "e0"),
            outputs=("status", "unavailable", "unavailableReason", "polarizationResistance_Rp_Ohm_cm2",
                     "corrosionRate_mm_yr", "corrosionRate_mpy", "deltaE_pit_V", "pittingAssessment",
                     "pythonDurationMs"),
            transport_values=_RUN_STATUS),
)


def build_electrochem_contract(seed: Mapping[str, str]) -> ModuleContract:
    """Build the electrochem-suite contract from the canonical seed row."""
    if seed.get("id") != "electrochem-suite":
        raise ContractError("electrochem contract seed id must be 'electrochem-suite'")
    return ModuleContract(
        id=seed["id"], version=CONTRACT_VERSION, owner=OWNER_UNASSIGNED,
        workspace=seed["workspace"], label=seed["label"], description=seed["description"],
        next=seed["next"], maturity=seed["scope"], navigation="listed",
        view=View(component=seed["viewComponent"], export=seed["viewExport"]),
        evidence=Evidence(
            emits=(), ceiling=PENDING_ORACLE_CEILING,
            forbidden_claims=tuple(dict.fromkeys(FORBIDDEN_CLAIM_KEYS + ALWAYS_FORBIDDEN_CLAIMS)),
            note=("The local calculators and Python services expose software outputs only. No independent module oracle is "
                  "declared; neither the local fit, solver status, cited standards, nor user-provided polarization data "
                  "establishes independent experimental validation."),
        ),
        tests=TestRefs(oracle=Oracle(status="pending"), schema="python/test_module_contract_electrochem.py",
                       docs="docs/modules/electrochem-suite.md"),
        migration_state="contracted", operations=ELECTROCHEM_OPERATIONS,
        lifecycle=Lifecycle(background_work="none", resources=("fetch",)),
        legacy_notes=(
            "CorrosionEngineeringLab is reachable from electrochem-suite. Its child tabs mount conditionally; switching tabs unmounts the prior child and its local state.",
            "PREN and Tafel's immediate fit are browser-local formulas. Their outputs are calculated estimates and are not validated measurements.",
            "Pourbaix sends only element, fixed 25 °C, effective dissolved-ion activity, chloride activity converted to ppm, and user-supplied point fields to /api/python/pourbaix-diagram. Chloride is echoed; the current equilibrium species model does not include chloride or derive a sourced pitting potential. Unsupported elements suppress dispatch and show unavailable data status. The nested solver run/domain statuses are temperatureStatus=supported-25C-only, dataValidity=withheld-species-regions|withheld-candidates-without-region|no-withheld-candidates, and chloridePittingBoundary=unavailable-no-sourced-epit; these are not evidence statuses. The request signature includes chloride and point fields, but the rendered Python result freshness predicate checks only element and dissolved activity; while another solve is pending, echoed chloride/point diagnostics can remain from an earlier request. The Python request is debounced, visibility-gated, and abortable. The displayed TypeScript map and point classifications remain a separate local path.",
            "Tafel imports user files/pasted text; the benchmark selector was removed because no benchmark dataset is bundled, so the state is upload-only and no synthetic benchmark is invented. The UI has a browser-local tryAutoFitTafel estimate and a Python fit action on the same /api/python/tafel-corrosion-rate route (action=fit_curve); a network failure falls back to the local estimate, while Python validation errors are surfaced and do not reuse the prior Python result. The local manualBetaA/manualBetaC overrides affect the browser fit but are not sent to Python; custom fit windows and Ecorr/Icorr overrides are sent. Dataset values and instrument provenance remain user source labels, not independently validated measurements.",
            "Tafel CSV export creates a Blob URL, clicks a download anchor, then revokes the URL. Summary copy calls navigator.clipboard.writeText without awaiting/rejecting it and raises a success notification optimistically. Digital Twin sync is a conditional callback action; if the callback is absent it does nothing.",
            "The embedded annual-rate child uses the same Tafel route without action=fit_curve and recalculates when fit, dataset metadata, or its own inputs change. Missing iCorr remains unavailable; it is not defaulted. Its status values partial/unavailable are runtime availability states, not evidence statuses.",
            "Corrosion EIS posts action=corrosion_kinetics to /api/python/battery-corrosion-eis. The coating timeline, coating Nyquist and the sub-tab selector were removed (they came from fixed constants); exposureDays is no longer sent. The request is debounced and abortable. Solver partial/unavailable statuses and per-output unavailable reasons describe calculation availability only.",
            "HTTP paths dispatch Python scripts through the registered Python IPC authority; Pourbaix uses a 25 s timeout and Tafel/EIS use 15 s. Pourbaix and EIS requests accept AbortSignal and are aborted when superseded/hidden; Tafel fit and annual-rate requests do not accept AbortSignal and can finish after their child view is unmounted. Child state is not persisted across unmount. Transient notifications and timer details are not represented as lifecycle resources by the current schema vocabulary.",
            "No equivalent-circuit fit/import child is reachable from this module. The contract does not claim circuit fitting, physical validation, measurement provenance beyond the selected source labels, or evidence promotion.",
            "Independent Pourbaix brute-force oracle and its golden comparison tooling exist in python/tools/pourbaix_oracle.py and python/tools/pourbaix_golden_check.py; Tafel/EIS analytic and input-refusal checks exist in python/test_electrochem_fallbacks.py. This contract keeps its module-level oracle pending because those solver-specific checks do not cover every local operation or the complete reachable UI, and none were executed in this task. Their existence does not establish experimental validation.",
        ),
        source_refs=(
            "python/module_registry_seed.json:153-161#electrochem-suite identity",
            "python/module_registry.py:121-128#Python authority timeouts and warm status",
            "python/module_registry.py:192-197#electrochem-suite solver registry operations",
            "routes/physics.ts:86-89#Pourbaix Python dispatch",
            "routes/characterization.ts:27-35#Tafel and corrosion EIS Python dispatch",
            "src/components/CorrosionEngineeringLab.tsx:15-27#suite state and browser-local calculations",
            "src/components/CorrosionEngineeringLab.tsx:296-327#conditional Pourbaix and EIS child mounting",
            "src/components/DynamicPourbaixStudio.tsx:84-152#Pourbaix inputs, unsupported-data availability, and local state",
            "src/components/DynamicPourbaixStudio.tsx:215-258#debounced abortable Python dispatch and freshness handling",
            "src/utils/pourbaixRequest.ts:7-28#actual solver request body and point provenance",
            "src/components/TafelPolarizationLab.tsx:132-175#dataset and analysis state",
            "src/components/TafelPolarizationLab.tsx:202-318#local fit, Python fit trigger, fallback precedence",
            "src/utils/tafelPythonService.ts:29-54#fit_curve endpoint payload",
            "src/utils/tafelPythonService.ts:150-166#validation refusal and local fallback behavior",
            "src/components/PythonAnnualCorrosionRateModule.tsx:35-133#annual corrosion input and request state",
            "src/components/CorrosionEISKineticsStudio.tsx:12-74#EIS action payload and debounced cancellable dispatch",
            "python/battery_corrosion_eis_solver.py:57-92#required supplied inputs and partial/unavailable behavior",
            "python/battery_corrosion_eis_solver.py:186-194#corrosion_kinetics action dispatch",
            "python/tafel_corrosion_rate_solver.py:374-441#annual rate input and availability handling",
            "python/tafel_corrosion_rate_solver.py:1006-1023#fit_curve versus annual-rate dispatch",
            "python/tools/pourbaix_oracle.py:1-23#independent Pourbaix brute-force oracle source",
            "python/tools/pourbaix_golden_check.py:1-25#Pourbaix golden comparison against independent oracle",
            "python/test_electrochem_fallbacks.py:1-30#Tafel and EIS analytic-oracle test scope",
        ),
        seed_derived=("label", "description", "next", "maturity"),
    )
