# Module evidence inventory

**Historical snapshot:** 2026-09-20, with targeted Phase 0 corrections on 2026-09-21. This is a bounded software evidence inventory, not a current workspace registry or scientific validation report. Fresh execution evidence and unresolved defects for that snapshot are recorded in `docs/DIGITAL_TWIN_PHASE0_AUDIT_2026-09-21.md`; unchanged rows retain their earlier inspection limits. Use `src/data/workspaces.ts`, the live application and current `PROOF.md` entries for present-day status.

## Scope and reading rules

The navigation set has 12 entries (35 when this snapshot was taken) in `src/data/workspaces.ts`; their render mapping is in `src/App.tsx`. None is currently marked Production. These labels describe product maturity, not the evidence status of a calculation. Module IDs below are exact registry IDs; component paths are repository-relative.

This review inspected registry/render wiring, targeted component imports and calculation/request sections, route dispatch, LPBF model contracts, and selected test assertions. It did not execute physical experiments, audit every descendant component, reproduce literature results, verify external source documents, or run all solvers. An endpoint listed below is implementation evidence, not a claim that its dependencies are installed or that its results are accurate. A test location is an available check, not a report that it passed in this task.

**Evidence notation:** **S** = inspected software contract/assertion; **L** = located test or related integration check, not a dedicated scientific benchmark; **G** = dedicated benchmark/test evidence not established in this bounded review. G does not mean no test exists anywhere. Every row additionally inherits the registry/route checks in `tests/workstation.test.ts`. That test checks workspace membership and hash round trips, not rendering or scientific correctness of all modules.

### Graph limitations

Verify (Tier 2) was used with project `metalliksa-active`, rooted at the actual working repository. Parent handoff recorded generation 2026-09-15T13:03:21Z, fast index, 4,231 nodes and 50 partial files. Project identity was rechecked in this task; that inherited generation is not a claim of current filesystem freshness. Narrow searches found the exact App render function and LPBF workspace; the one-hop outbound workspace trace returned all 23 callees without a continuation. The inherited broad Python search (381 matches, only 35 returned) was not used as exhaustive evidence. One component-filter query returned no matches and was treated as insufficient, not absence.

Coverage metadata reported missing freshness for inherited evidence paths; App also reports a parse gap at line 162. Direct source inspection, including App's full file, superseded those graph limitations. The final check covered 115 cited paths: 65 with no recorded issue, 31 partial, and 19 excluded, all with missing freshness. The tests scope returned all 19 recorded exclusions without pagination; Python test files were checked individually (the literal prefix scope `python/test` is not a wildcard). Test-file discovery and selected assertions were therefore read directly. Even clean index coverage is not proof of completeness. The table intentionally names principal paths rather than claiming a complete dependency graph.

## LPBF Engineering

| Module ID / label | Actual component | Principal implementation / API | Evidence and current maturity | Next gap |
| --- | --- | --- | --- | --- | --- |
| `3d-distortion-lab` / LPBF Workflow | `src/components/LpbfEngineeringWorkspace.tsx` | `src/components/3d-distortion-lab/LpbfEngineeringSimulation.tsx`, `src/components/3d-distortion-lab/ResolvedThermalViewer.tsx`; `routes/lpbfSimulation.ts` serves `POST /api/lpbf/jobs`, estimate, capabilities, job read/cancel and artifacts. Separate build screening: `POST /api/python/lpbf-build-job` in `routes/physics.ts` → `python/lpbf_build_job_solver.py`. | **Research. S:** `tests/lpbf-workflow.test.ts` covers shared process, stale/executed input and unresolved qualification; `python/test_lpbf_engineering.py` contains conservation, enthalpy, mesh, field and honest-fallback assertions. **L:** `tests/lpbf-contract.test.ts`, `tests/lpbf-fields.test.ts`, `tests/lpbf-build-session.test.ts`, `python/test_lpbf_api.py`, `python/test_lpbf_build_job.py`. Transient thermal fields are implemented; printability, defect risk and legacy distortion remain screening. | Qualify an explicitly bounded thermal use case against independent matched measurements; keep screening and resolved thermal outputs distinct. See detailed boundaries below. |
| `lpbf-optimizer` / Process Parameter Search | `src/components/LpbfBayesianOptimizerLab.tsx` | `src/services/pythonComputationService.ts` → `/api/python/lpbf-bayesian-optimize`, `routes/physics.ts` → `python/lpbf_bayesian_optimizer.py`. | **Preview. S:** `python/test_phase6.py` and service/route contract. Process parameter optimization using Gaussian Process / Bayesian surrogate. | Multi-objective Pareto frontier calibration with experimental validation data. |
| `solidification-microstructure` / Solidification Map (G/R) | `src/components/SolidificationMicrostructureLab.tsx` | `src/services/pythonComputationService.ts` → `/api/python/lpbf-solidification-microstructure`, `python/lpbf_worker.py` → `python/lpbf_solidification_microstructure.py`. | **Research. S:** `python/test_phase8_microstructure_contract.py`, `python/test_lpbf_solidification_microstructure_rpc.py` and service/component contract. Screening-field G/R from `lpbf_thermal_solver` (equal to the Build Job numbers for Rosenthal with the Build Job's inputs; status available / screening-fallback / degenerate-floor (R or cooling on the solver clamp floors, not a computed value) / unavailable), Hunt-Lu PDAS, Kirkwood SDAS and Hunt G/R morphology bands; not in-situ tracking, not validated. | Calibrate kinetic constants against experimental EBSD/micrograph dendrite spacing measurements. |
| Removed 2026-10-04 | `thermomechanical-distortion` (Thermomechanical Lab) | Deleted with its view, worker route/RPC and Python module (AUDIT-module-deletion-opus D3: fabricated output). | - | - |
| Removed 2026-10-04 | `industrial-certification` (Industrial Certification) | Deleted with its view, worker route/RPC and Python module (AUDIT-module-deletion-opus D3: fabricated output). | - | - |
| `experimental-validation` / Melt Pool vs Measurements | `src/components/ExperimentalValidationLab.tsx` | `src/services/lpbfSourceService.ts` `sourceMeasurements` → `GET /api/lpbf/sources/:datasetId/measurements` (node source catalog); the unused worker route `/api/python/lpbf-experimental-validation` and its Python module were removed on 2026-10-04. | **Research. S:** `tests/lpbf-source-api.test.ts` and the source-catalog contract; reads stored CMU measurements, no model-vs-experiment qualification. | Broaden NIST AM-Bench experimental dataset coverage. |
| Removed 2026-10-04 | `modulus-fno-lab` (Modulus FNO Surrogate) | Deleted with its view, worker route/RPC and Python module (AUDIT-module-deletion-opus D2: hollow view; frozen solvers kept). | - | - |
| Removed 2026-10-08 | `toolpath-studio` (Scan Path Kinematics) | Deleted with its view, worker route/RPC and Python module (slimming pass). | - | - |
| Removed 2026-10-04 | `toolpath-thermal-map` (Toolpath Thermal Map) | Deleted with its view, worker route/RPC and Python module (AUDIT-module-deletion-opus D3: fabricated output). | - | - |
| Removed 2026-10-08 | `murakami-fatigue` (Defect Fatigue & Crack Growth) | Deleted with its view and the /api/python/lpbf-fatigue-fracture route and RPC (slimming pass). The Murakami screening survives only inside the LPBF build job. | - | - |
| Removed 2026-10-04 | `defect-twin` (Spatial Defect Twin) | Deleted with its view, worker route/RPC, Python module and contract (AUDIT-module-deletion-opus D3: fabricated output). | - | - |
| Merged 2026-10-07 | `adaptive-mitigation` (Corner Power Compensation) | Merged into `toolpath-studio` as its Feed-forward power tab, then removed with `toolpath-studio` on 2026-10-08. The old id no longer redirects anywhere. | - | - |
| Removed 2026-10-04 | `multilaser-plume` (Multi-Laser Plume) | Deleted with its view, worker route/RPC and Python module (AUDIT-module-deletion-opus D3: fabricated output). | - | - |
| Removed 2026-10-04 | `thermal-accumulation` (Thermal Accumulation) | Deleted with its view, worker route/RPC and Python module (AUDIT-module-deletion-opus D3: fabricated output). | - | - |
| Removed 2026-10-04 | `powder-compaction` (Powder DEM Compaction) | Deleted with its view, worker route/RPC and Python module (AUDIT-module-deletion-opus D2: hollow view; frozen solvers kept). | - | - |
| Removed 2026-10-04 | `optical-tomography` (Optical Tomography) | Deleted with its view, worker route/RPC, Python module and contract (AUDIT-module-deletion-opus D3: fabricated output). | - | - |
| Removed 2026-10-04 | `transient-3d-gpu` (Transient 3D GPU Solver) | Deleted with its view and worker RPC handler (AUDIT-module-deletion-opus D2: the view posted to a route that never existed); the frozen solver `python/lpbf_transient_3d_gpu.py` stays. | - | - |
| `keyhole-raytracing` / Keyhole Ray Tracing | `src/components/KeyholeRaytracingLab.tsx` | `/api/python/lpbf-keyhole-raytracing` in `routes/lpbfSimulation.ts` → `python/lpbf_worker.py` → `python/lpbf_keyhole_raytracing.py`. | **Research. S:** `python/test_keyhole_contract.py`, `python/test_phase26.py`, `tests/lpbf-keyhole-api.test.ts`; live browser/CPU execution checked on 2026-09-21. Seeded Monte Carlo on prescribed geometry with empirical absorption; sampling error and unresolved bounce power reported. | Curved mesh asymptotic convergence, material optical data, independent experiments and worker computation cancellation remain open. |

### What is actually resolved, screened, or unresolved

- **Resolved thermal research path:** `src/services/lpbfSimulationService.ts` → `routes/lpbfSimulation.ts` → `server/lpbfWorkerBridge.ts` → `python/lpbf_worker.py` → `python/lpbf_simulation.py` (NumPy reference) or `python/lpbf_openfoam.py` (OpenFOAM thermal adapter). Standard/calibration modes solve transient enthalpy conduction on stationary cells with layer activation, temperature-dependent properties and prescribed laser heating/boundary losses. Backend availability must be checked at runtime. These are unvalidated thermal simulations.
- **Resolved does not mean free-surface CFD:** molten-cell dimensions, liquidus sections and enthalpy liquid fraction derive from temperature fields. They do not resolve a metal/gas interface. Flow velocity, momentum, capillary/Marangoni flow, evaporation, recoil, keyhole collapse, pore trapping and residual stress/distortion remain unresolved in this thermal path. Boiling is a validity failure. The high-fidelity request explicitly falls back to screening, with a reason and `validationStatus: unvalidated`, `productionReady: false`.
- **Build decision path:** `python/lpbf_build_job_solver.py` imports `python/lpbf_thermal_solver.py` and `python/stl_slicer_build_time_solver.py`. Regularized Rosenthal geometry (`rosenthal-screening-v1`), hatch/layer comparisons, process-window checks and slicer estimates feed its verdict. The shared `src/store/useLpbfBuildJobStore.ts` owns that result. A `printable` verdict is a screening classification, not an experimentally established print success probability or production release.
- **Specialist analytical labs:** Goldak/Eagar–Tsai and Fabbro depth correction belong to the analytical melt-pool path, not a new build-verdict model. Analytical Marangoni and solidification-front estimates are screening. `python/test_eagar_tsai.py`, `python/test_goldak_fabbro.py`, `python/test_marangoni_screening.py` and `python/test_solidification_front.py` are relevant located checks; their names do not demonstrate resolved flow.
- **Two material scopes:** `python/four_alloy_materials.py` centralizes the four screening alloys (Ti-6Al-4V, 316L, AlSi10Mg, IN718), aliases and process boxes. The engineering thermal path instead imports `python/lpbf_material_registry.py`; its estimated/missing property-law coverage must not be inferred from four-alloy screening support or a database display name.
- **Numerical verification is separate:** inspected `python/test_lpbf_engineering.py` assertions check enthalpy inversion, source energy, stationary mass/phase bookkeeping, validity failure, scan schedules and mesh-study status. A three-mesh nonmelting fixture explicitly remains inconclusive/unvalidated. OpenFOAM/reference agreement checks implementation consistency, not agreement with an experiment.
- **Literature comparison is narrowly scoped:** `python/test_meltpool_literature_catalog.py` checks stored measured-track records in `python/meltpool_literature_catalog.py` against the analytical Goldak+Fabbro path. It expects seven IN718 Lane cases and three 316L Guo cases within a broad ×0.5–2 W/D band; Guo N01 depth is explicitly expected outside that band. It records no measured track for AlSi10Mg or Ti-6Al-4V. These are inspected test expectations, not newly reproduced measurements or independently verified source transcription. The repository's Ti-6Al-4V asymptotic reference is not a measured track. Solver echoes and synthetic fixtures are not experimental ground truth.
- **Calibration/export:** `src/utils/lpbfQualificationReport.ts`, `tests/lpbf-workflow.test.ts` and `src/components/EvidenceWorkspace.tsx` distinguish submitted inputs, current inputs, measured comparisons and missing evidence. User-entered source/holdout labels do not establish independent validation. Worker artifacts and meshes must be retained separately from the evidence JSON.
- **Further located checks (not individually reviewed here):** `tests/lpbf-archive-paths.test.ts`, `tests/lpbf-artifact-store.test.ts`, `tests/lpbf-claims-wording.test.tsx`, `tests/lpbf-error-bands.test.tsx`, `tests/lpbf-experimental-evidence.test.tsx`, `tests/lpbf-experimental-validation-logic.test.ts`, `tests/lpbf-material-authority.test.ts`, `tests/lpbf-measurement-submission.test.ts`, `tests/lpbf-process-window.test.tsx`, `tests/lpbf-result-staleness.test.tsx`, `tests/calphad-display.test.tsx`, `tests/keyhole-loft-and-gate.test.ts`, `python/test_calphad_honesty.py`, `python/test_lpbf_cfd.py`, `python/test_lpbf_bare_plate.py`, `python/test_lpbf_benchmark.py`. They exist as available checks; this inventory does not report that they passed.

Model detail and existing verification records: `docs/LPBF_ENGINEERING.md`. This inventory does not upgrade the claims in that document.

## Materials & Characterization

| Module ID / label | Actual component | Principal implementation / API | Evidence and current maturity | Next gap |
| --- | --- | --- | --- | --- | --- |
| `database` / Materials Database | `src/components/MaterialsDatabaseView.tsx` | `src/data/materialsDatabase.ts`; `src/utils/materialDataPipeline.ts`; shared material transfer. | **Research. S:** `tests/material-context-bridge.test.ts` asserts identity/unit handling and refusal to upgrade confidence. Catalog and transfer evidence do not validate individual property values. | Audit per-property source, units, condition and applicability; distinguish nominal ranges from measurements. |
| Merged 2026-10-09 | `alloy-builder` (Composition Editor) | Folded into `database`; composition and specimen editing now live in the Materials Database view. The standalone view was removed. | - | - |
| `phase-diagram` / Phase Diagrams & CALPHAD | `src/components/PhaseDiagramViewer.tsx` | `src/components/CALPHADMultiComponentStudio.tsx` uses the Python service (the binary phase-diagram lab was removed in the slimming pass); `routes/physics.ts`: `/api/python/calphad-minimize`, `/api/python/calphad-databases` → `python/calphad_solver.py`. | **Research. G:** local model and multicomponent server paths located; database coverage/dependency availability and equilibrium accuracy not established here. | Record database/version and covered phases/elements; benchmark equilibrium and Scheil outputs for supported systems. |
| Removed 2026-10-08 | `ttt-cct-kinetics` (Steel TTT / CCT) | Deleted with its view and the /api/python/kinetics-ttt-cct route (slimming pass). The steel kinetics survive only inside the LPBF build job. | - | - |
| Removed 2026-10-08 | `eds-lab` (EDS Spectrum Viewer) | Deleted with its view and its browser-side parser and peak identification utilities (slimming pass). | - | - |
| Removed 2026-10-08 | `micrograph` (Micrograph Analysis) | Deleted with its view, the /api/python/micrograph-measure route and its Python module (slimming pass). | - | - |
| Removed 2026-10-09 | `electrochem-suite` (Corrosion & Electrochemistry) | Deleted with its view and its corrosion, Tafel, EIS and Pourbaix routes and solvers (slimming pass). | - | - |
| Removed 2026-10-08 | `icme-motor` (Yield Strength Breakdown) | Deleted with its view and the /api/python/icme-multiscale-pipeline route (slimming pass). | - | - |
| Removed 2026-10-08 | `materials-project` (Elastic Constants) | Deleted with its view and the /api/python/dft-properties route (slimming pass). | - | - |
| Removed 2026-10-08 | `calculators` (Metallurgy Calculators) | Deleted with its view and its browser-side conversion utilities (slimming pass). | - | - |

## Evidence & Records

| Module ID / label | Actual component | Principal implementation / API | Evidence and current maturity | Next gap |
| --- | --- | --- | --- | --- | --- |
| `research-hub` / Research Hub | `src/components/AdvancedResearchHub.tsx` | Research panels; `src/store/useResearchStore.ts`, `src/utils/researchRegistry.ts`; `routes/research.ts` (`/api/research/search`), `routes/researchRegistry.ts` (`/api/research/registry`, history/revisions). | **Research. S:** `tests/research-registry.test.ts` asserts review/reference constraints using synthetic fixtures. **L:** `tests/research-api.test.ts`, `tests/research-registry-api.test.ts`, `tests/research-sync.test.ts`, `tests/research-persistence.test.ts`, `tests/research-multitab.test.ts`. Metadata/review software does not verify paper claims. | Traceable primary-source extraction and independent review; authenticated reviewer identity remains outside the documented local registry scope. |
| `experimental-data` / Measured Findings | `src/components/EvidenceWorkspace.tsx`, mode `experimental` | Filters registry findings by measured evidence label/material; `src/utils/researchRegistry.ts`; links validation-dataset references. | **Research. S:** component displays method/source/uncertainty gaps; `tests/research-registry.test.ts` checks synthetic contract records. A user-selected measured label is not independently verified measurement provenance. | Match real specimen/build/process metadata and source files to acceptance criteria; retain contradictions and missing metadata. |
| Removed 2026-10-09 | `digital-twin` (Specimen Records) | Deleted with its view, its context and the optional consultation endpoint (slimming pass). | - | - |
| Removed 2026-10-08 | `uq-lab` (Coupon Statistics & UQ Sampling) | Deleted with its view and the /api/python/stochastic-uq-mmpds route (slimming pass). | - | - |
| Removed 2026-10-04 | `qualification` (ASTM / MMPDS Screening) | Deleted with its view, screening utilities and the canned POST /api/metallurgy/qualify-aerospace route (AUDIT-module-deletion-opus D4: fabricated evidence). | - | - |
| Removed 2026-10-04 | `aerospace-pdf-audit` (Audit Templates) | Deleted with its view, screening utilities and the canned POST /api/metallurgy/qualify-aerospace route (AUDIT-module-deletion-opus D4: fabricated evidence). | - | - |
| `traceability` / Export Review Package | `src/components/EvidenceWorkspace.tsx`, mode `traceability` | Exports active specimen, research snapshot, engineering job/submitted input and screening alignment; shares registry/job stores. | **Research. S:** source declares meshes/full worker artifacts excluded; **L:** `tests/research-persistence.test.ts`, `tests/lpbf-workflow.test.ts` cover related snapshot/report contracts, not the entire downloaded package. | End-to-end export/reimport fixture plus manifest linking separate mesh/worker artifacts and source attachments. |

## AI Orchestration

| Module ID / label | Actual component | Principal implementation / API | Evidence and current maturity | Next gap |
| --- | --- | --- | --- | --- |
| Removed 2026-10-04 | `ai-orchestrator` (AI Orchestrator) | Deleted with its view, the Node orchestrator routes, the approved-source collector and the whole AI Orchestration workspace (AUDIT-module-deletion-opus D4: no computation). | - | - |

## Runtime and environment mapping (A01 review correction)

All modules need the browser application and Node-served assets described by `package.json`, `package-lock.json` and `server.ts`. Browser-side calculations need no Python for the principal local path listed below; optional AI consultation still needs Node/provider access. Browser WebGL/Canvas, file input and storage support must be checked on the target client. This maps requirements, not universal availability.

### Browser calculations and local records

Modules: `database`, `experimental-data`, `traceability`, `lpbf-dataset-comparison`, `lpbf-calibration-scorecard`.

Principal paths run in the browser using the components/parsers/stores above. File import/export needs browser file APIs; persistent records depend on browser storage. Shared server registry synchronization needs `routes/researchRegistry.ts` and a writable `.research-registry/` directory. No AI provider route is served. Registry/parser tests establish selected software contracts only.

### Host Python scientific requests

Modules: `phase-diagram`, `lpbf-optimizer`, `solidification-microstructure`, `experimental-validation`.

The listed Node routes dispatch through `server/processOrchestrator.ts` and `server/pythonRuntime.ts` to the scripts identified in each row. Browser-only subviews can coexist with these requests. Interpreter choice and IPC ports are documented in `docs/ENVIRONMENT_READINESS.md`; broad numerical/CALPHAD/ML requirements are in `python/requirements.txt`. Actual optional library, thermodynamic database and model availability must be checked for the selected operation. A successful import or a warm module is not successful scientific execution. CALPHAD coverage and the full domain dependency environment remain open A02 work.

### LPBF worker and external solver boundary

Modules: `3d-distortion-lab`, `keyhole-raytracing`.

CPU build/thermal paths use the Windows/Python3.12 lock described in `docs/LPBF_CPU_REPRODUCTION.md`. Historical checks there apply only to their stated scope. Explicit `METALLIX_PYTHON` now controls the LPBF worker as well as host services; without it Windows remains WSL-first through `server/lpbfWorkerBridge.ts`. (The industrial-fatigue surrogate, the Shapely/NumPy toolpath thermal map and the legacy transient-GPU lab were deleted on 2026-10-04.) OpenFOAM requires the configured distribution and compiled worker in `python/lpbf_openfoam.py`. Keyhole requires Warp on the selected interpreter and uses explicit CPU or CUDA 0. Native CPU success is not WSL readiness or scientific validation.

### External AI dataset planning (removed)

No module since 2026-10-04: `ai-orchestrator` and its workspace were deleted.

The orchestrator route, provider-backed dataset planning and approved-source collection no longer exist in the application.

### Browser model artifacts and optional image provider (removed)

No module uses a browser model artifact or an image provider since 2026-10-08: `micrograph` and its advisory route were removed, along with the ONNX engine and segmentation training script.

### Network metadata and local research registry

Modules: `research-hub`.

Local briefs/records use browser storage; server revision storage needs writable local registry files. Metadata search additionally needs Node and external Crossref access through `routes/research.ts` and `server/researchSearch.ts`. Network-off mode prevents remote search; it does not erase local evidence. Full-text access/extraction and scientific verification are not supplied by metadata connectivity.

### Node catalog and optional consultation/report provider (removed)

No module dispatches a catalog, consultation or report-provider request since 2026-10-09: `digital-twin`, `copilot` and `materials-project` were removed. `AIRGAPPED=1` still disables external data paths such as Crossref search.

### Availability evidence boundary

The inherited 97-unit-test pass and CPU/GPU/tool checks are recorded in `docs/ENVIRONMENT_READINESS.md` and `docs/LPBF_CPU_REPRODUCTION.md`; they cover only their declared paths. `routes/physics.ts` currently hard-codes `pythonVersion` and subsystem `available: true` in `/api/python/status`. Those fields must not be used as installation proof. Use the actual interpreter doctor, IPC details and operation-specific execution checks. Correcting that status endpoint is separate A02 implementation work, not a prerequisite to accurately inventorying its limitation.

## Next engineering priorities and maintenance

1. Preserve the LPBF distinction between transient thermal output, analytical build screening, numerical checks and independent experimental validation throughout reports.
2. Address evidence-sensitive presentation gaps in the remaining modules, such as source provenance for stored measurements.
3. Add dedicated regression/benchmark fixtures for the G rows, starting with intended near-term use cases. Do not infer a benchmark from a sublab's “validation” name or a standard citation.
4. Maintain this inventory when registry IDs, rendering, request paths or evidence change. Verify all registered IDs remain mapped exactly once; do not silently promote a maturity or result label.

`docs/RESEARCH_WORKSTATION.md` describes product/evidence boundaries. This inventory changes no solver, source dataset, qualification record or proof claim. Commit/push and operational/proof records are owned by the parent task.

## Modules registered after the review pass

Appended at the end so existing line references in `python/module_registry.py` keep resolving.

| Module / label | Principal view | Request path and authority | Evidence tier | Next gap |
| --- | --- | --- | --- | --- |
| `lpbf-dataset-comparison` / Dataset Comparison (LPBF) | `src/components/LpbfDatasetComparisonLab.tsx` (re-export shim; implementation `src/components/3d-distortion-lab/LpbfDatasetComparisonLab.tsx`) | Read-only view of the committed Python-generated record `docs/LPBF_DATASET_COMPARISON_2026-10-05.json` via `src/data/lpbfDatasetComparison.ts`; no server route and no browser computation. | **Research. S:** `tests/lpbf-dataset-comparison.test.ts`, `tests/lpbf-dataset-comparison-lab.test.tsx`. Comparison of screening kernels against published single-track measurements, not validation; the page shows only numbers carried by the JSON. | Experimental validation, calibration and the reference transient on these datasets remain open. |
| `lpbf-calibration-scorecard` / Calibration Scorecard (LPBF) | `src/components/LpbfCalibrationScorecardLab.tsx` | Read-only view of the committed Python-generated record `docs/LPBF_CALIBRATION_SCORECARD_<date>.view.json` via `src/data/lpbfCalibrationScorecard.ts`; no server route and no browser computation. The same record family feeds the hidden opt-in calibrated mode of the Melt Pool lab (`/api/python/lpbf-calibrated-meltpool`, bound to `3d-distortion-lab`), which is offered only for cells that pass the held-out gate. | **Research. S:** `tests/lpbf-calibration-scorecard.test.tsx`, `tests/meltpool-calibrated-toggle.test.tsx`. Held-out errors of nuisance-parameter calibration of the screening kernels, not validation; every result stays Screening only; label promotion proposed: none. | A second independent source per alloy, resolved KU Leuven beam diameter and per-row measurement uncertainty are open; no cell is enabled on today's data. |
