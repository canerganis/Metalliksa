# Digital Twin Phase 0 — current-code audit

Started 2026-09-21 at `fb1a614b8b9ce97b2cbe4d818ea622b63664d008`, branch `main`.
The application tree and index were initially clean. The parent repository already
contained changes, including STATUS.md and cache deletions; these are not ours.
Gemini ownership is unknown. See ACTIVE_WORK.md for this task's scope.

**Phase 0 is open. No later phase or experimental qualification is accepted.**

## Current bounded core baseline — owner01a0c36f

See `LPBF_CORE_BASELINE_2026-09-21.md` for current16entry UI/API/worker map,
shared thermal seams, source-backed specialist gaps and fresh melting CPU profile.
40W/40um and20um produce actual saved molten fields, wall2.317/4.893s and~245MB
peak process working set. W/D changes40/40→80/20um; convergence remains OPEN.
Prior nonmelting profile input was10W (historical40W wording corrected).
Fresh five CPU groups44PASS/5explicit Linux/OpenFOAMskip. First sandbox failures
were temp-directory permissions; scoped reruns pass. Source calibration still null.
Detailed first shared-core contract plan is written; no later phase accepted.

## 2026-09-21 — LPBF source and current WSL checkpoint

UI661153a and HDF5 inspection b0bd0bd are committed locally. Source archive UI
passed real compiled-browser preview/import/verify, keyboard,503 and delayed reply
checks. The source metadata inspector and hash-bound catalog guards passed their
regressions; full167unit, strict TypeScript and production build passed. UI lint
passed in661153a. No solver or experimental acceptance follows from these results.

WSL was checked outside sandbox: Ubuntu22.04/WSL2 starts, kernel
6.18.33.2-microsoft-standard-WSL2, /usr/bin/python3 is3.10.12. Current environment
doctor reports NumPy1.21.5/SciPy1.8.0;15 listed scientific dependencies including
Torch are missing, Node/Docker are outside this Linux PATH and Docker engine unavailable.
The NVIDIA bridge reports RTX4060 Laptop/driver616.92; Torch CUDA cannot be tested
in this interpreter. These system package versions are not the Windows lock.
The actual current `python/test_lpbf_engineering.py` completed26/26 tests,
including compiled OpenFOAM versus independent reference, in69.935s. No skipped
tests. This is a bounded numerical/software suite, not all-engine or GPU evidence.
Logs: `.runtime/phase0-audit/wsl-doctor-01a0c35a.json` and
`.runtime/phase0-audit/wsl-engineering-01a0c35a.log`. No installation or WSL config
change. No owned test server remains running.

Remaining LPBF baseline work:

- Update bounded LPBF UI/API/worker/solver/material/test mapping against current
  source; preserve model-specific assumptions and evidence limits. Existing module
  inventory is a starting map, not a fresh exhaustive claim.
- Profile a representative melting run with wall time, peak RAM, artifact volume
  and explicit backend; prior40W/1175.58K non-melting run is not this evidence.
- Finish shared-component review (material, SI units, source/beam convention,
  enthalpy, boundary conditions, numerical controls and result provenance), then
  write the detailed next implementation plan. No dependent phase accepted early.
- Thermal comparison needs a clarified primary calibration equation/emissivity
  and a frozen measurement operator. HDF5 source units/conditions are now reviewed;
  temperature conversion remains null. This does not block independent numerics.

Already established within their scopes: workspace ownership/clean checkpoints,
Windows CPU baseline, actual WSL/OpenFOAM baseline, source hashes/use terms,
SQLite driver/transaction/backup ADR, versioned source repository+artifact bundle,
bounded API and UI. Source storage is not a complete simulation/experiment store.
Secondary-module work remains deferred.

## 2026-09-21 — EIS request identity and fitted topology

- Studio/Builder fit and DRT share an input-bound attempt; topology, observation,
  parameter, weighting or iteration changes discard old data/errors/pending state.
  Retry/unmount invalidate replies even when transport ignores abort. FileReader
  completion is guarded too. HTTP abort is not Python compute cancellation.
- Results no longer silently rewrite initial guesses or globally apply to Builder.
  Explicit Apply uses a fitted topology copy. A newly found normalizer error was
  reproduced independently: returned R2 report previously retained initial R3 in
  topology; regression failed, then passed without modifying the initial object.
- Plotly clears previous curves/metrics during debounce, rejects late replies and
  incomplete/nonfinite simulation reports, exposes errors, removes click listeners
  and purges its plot on unmount. Preview now uses actual fitted topology.
- Fresh `npm run test:unit`:126/126 PASS; `npm run lint`:PASS;
  `npm run build`:PASS23.28s (existing chunk-size warnings). Logs:
  `.runtime/phase0-audit/identity-{unit,lint,build}-final.txt`.
- Browser `tests/contracts-browser.html`, real Node3193→PythonIPC5193 with explicit
  CPU Python3.12: before fix, held local fit overwrote edited Rs9 with0.02874 and
  falsely displayed current convergence. After fix Rs9 survives; no Apply/report.
  Held DRT after edits stays empty. Changed workspace prop resets the session.
  Studio Enter Apply emits actual Rs0.028743577/C0.238972388; initial guesses stay
  unchanged. Builder Enter Apply updates circuit, invalidating outstanding DRT.
  Held global fit after dataset change produces no summary/Apply. Partial global
  response shows error. Held Plotly reply cannot overwrite a new HTTP503 error;
  old metrics remain absent. Screenshot checked. Shared hook browser self-test:
  10 PASS (input/retry/late error/finally/A-B-A/unmount/zero). These are software
  checks using synthetic inputs, not experimental qualification.
- Remaining: explicit client-JS fitting, SyntheticNoise wrappers/provenance,
  incomplete static ASTM/K-K labels, legacy LinKK numerics and broader Phase0.

## 2026-09-21 continuation: CNLS numerical and result contracts

- Source HEAD4f76eca inherited clean. Sign repair committed b5c83c3 after failing
  analytic resistor/Randles fixtures. New report repair follows in the next commit.
- Local LM now solves against -J^T r for the experimental-minus-calculated
  residual Jacobian. R20 and Rs5/Rct120/C20uF are recovered against independent
  analytic fixtures. NumPy and scalar resistor paths pass. These are numerical
  verification only, not experimental model validation.
- Fixed parameters and max_iter0 evaluate actual residuals, never perfect defaults.
  Report includes termination reason/converged, actual chiSquare/DOF/RMSE, and
  unclipped magnitude-based R² (null for constant observed magnitude). Finite
  inputs/options/bounds checked; frontend lowerBound/upperBound aliases honored.
- Local uncertainty uses a final-iterate column-scaled SVD and residual variance.
  Rank loss, active bounds, no convergence or missing NumPy => null uncertainty.
  Fixed-parameter zero error is conditional on an imposed value, not estimated
  confidence. Covariance remains a local linear approximation, not calibration.
- DE has a local RNG and reported randomSeed (default42, CLI configurable).
  Determinism test checks identical parameters/objective and no global RNG mutation.
  Finite global runs do not prove a global optimum. No-polish uses actual iter0
  evaluation. Global input/budget validation and correlated stratified seeding
  remain separate review candidates; not claimed fully audited.
- Fitted-circuit residuals no longer certify independent K-K or ASTM compliance.
  Short LinKK input returns unavailable/null. Existing fixed-basis regularized
  clipped-Voigt model is now explicitly descriptive screening, not a stationarity
  diagnosis or standards certificate; its normal equations and basis selection
  still require review. Frequency sorting stabilizes the low/high subset meaning.
- Shared report normalizer preserves explicit null and rejects missing/duplicate
  parameter rows, out-of-bounds fits and residual/input identity mismatch. Studio
  and asyncAutoFit now use it; HTTP/partial responses do not fall back to JS.
  Studio retry clears fit/DRT. Builder and studio render unavailable uncertainty/R².
  Existing explicit client-JS solver, late input/reply paths, Plotly, synthetic-noise
  wrappers and remaining synthetic instrument/experiment metadata are NOT repaired.
- Fresh validation: Python CNLS12/12, no-fabricated-outputs10/10; unit125/125,
  lintPASS, buildPASS23.32s. Logs `.runtime/phase0-audit/cnls-*`.
- Browser real components / actual Node→Python at3192/5192: studio and builder
  local fit65iterations/reduced objective1.029e-2/R²0.99124; nullable independent
  K-K assessment displayed. Studio HTTP503 clears old results, partial global
  report errors. Enter runs local fit; Tab reaches apply button with visible focus;
  builder result panel visually checked. No experimental evidence claimed.
- First test server used default IPC5055 and returned legacy metrics despite a
  fresh Node frontend. Those results were discarded. Only owned PID23964 and
  verified descendants were stopped; replacementPID17488 uses isolatedIPC5192.
  Record this runtime identity risk for supervisor follow-up. Port24678 untouched.

## 2026-09-21 continuation: UI contract repairs

- Clean baseline 6600806, same LOCAL main checkout. AgentMemory recall empty;
  CBM generation2026-09-18 stale on all inspected paths, new tests/helper untracked.
  Source fallback used; Graft refreshed16files. No independent agents or installs.
- TypeScript errors repaired through real fields/contracts: legacy embedded alloy
  inputs, Recharts payload selection, refs/timer types, numeric tooltip label,
  chart row schema, nested melt-pool width and actual candidate strength/cost/misfit.
- Candidate pipeline now accepts CandidateAlloySolution fields and rejects missing
  or nonfinite supplied properties instead of generating1050MPa/default chemistry.
  Existing derived kinetic/XRD/hardness heuristics remain; this is no scientific
  qualification of those profiles. Inverse component itself required no edit.
- EDS broken modal replaced with reference-spot chemistry transfer to Alloy Builder.
  No hardcoded ASTM grain8.5 is transferred. Raw uploaded spectrum disables this
  action because preset chemistry is not its quantified composition. Other EDS
  spectrum/AI/report/compliance claims remain an explicit unreviewed audit scope.
- Heat-treatment scenario requires explicit precipitate fraction0–0.35, accepts0,
  and hides results on blank/invalid input. Scheil solid fraction is not reused.
  Candidate YS/UTS corrected. Existing empirical coefficients,0.95% porosity and
  4um spacing are disclosed assumptions. Model validity and hardcoded property
  multipliers are NOT validated by this UI repair.
- Browser exposed actual CNLS response crash after initial type fix: Python emits
  reducedChiSquare, not chiSquare/chiSquared. New normalizer validates available
  report fields, maps parameter identities/bounds, derives RMSE from residuals and
  weighted chiSquare from reducedChiSquare*DOF. Missing fields reject; zero stays0.
  EquivalentCircuitBuilder no longer invents0.001/0.99/default success, nor switches
  solver on HTTP failure. Retry clears old fit. Missing convergence is not confirmed.
- Fresh evidence: lint PASS, unit122/122 PASS, build PASS25.61s (chunk warnings).
  Candidate transfer2 and missing-heat-input1 regressions observed red then green.
  CNLS helper2 PASS; its initial red was module-not-yet-present, while the real
  component crash was reproduced in browser before normalization.
- Actual browser: heat blank/0/0.2/0.5, zero gain and invalid-result removal; EDS
  keyboard Enter transferred exact spot values Ni53.4/Cr19.3/etc; Recharts point
  opened TI64-GONG-LOF-01 detail, keyboard closed it; inverse transfer modal displayed
  actual candidate; all four classic circuit charts rendered, screenshot checked.
  Real API→CPU Python fit showed reducedChiSquare1.14e3, R²0,80iterations with
  convergence NOT confirmed. Test-only HTTP503 and incomplete report cleared fit
  and showed explicit errors. Software/fixture evidence only. Full EDS upload and
  standalone legacy embedded simulator were not browser-tested.
- The dev Vite watcher was disabled; browser reload initially retained cached old
  code. Restarting ONLY owned server descendants loaded current code. Port24678
  is owned elsewhere and was not touched. Final server cleanup recorded in STATUS.

New bounded findings for next package (not fixed here): Python run_cnls_fit appears
to use residual exp-calc and its Jacobian but adds +solve(JTJ,JTr); inspect step sign
with analytic regression before changing it. Browser result stayed at initial
parameters with high cost. It omits convergence/rmse, returns fake perfect scores
when no adjustable parameters, and clips covariance/R². len<5 Lin-KK still reports
95/true/zero. CNLSFittingStudio and cnlsOptimizer.runAsyncAutoFit still have invented
default metrics; EquivalentCircuitBuilder/Plotly stale-input cancellation remains
to audit. Built-in EIS metadata still calls synthetic circuits measured experiments.
Repair these next, then material authority/queued transient and remaining Phase0
profiling/raw hashes/source terms/SQLite ADR. Phase0 remains OPEN.

The user's subsequent instruction expands the audit to fabricated Python outputs.
Random sampling is evaluated by method/seed/convergence; it is not itself fabrication.

## Discovery and evidence boundary

Agent Memory targeted recall returned no records. Codebase Memory project
`C-Users-can02-Projects-metalliksaa-Metalliksa-1`, generation
`2026-09-18T15:50:24Z`, is stale for the inspected paths. Keyhole and the new
orchestrators are not tracked; worker/bridge/router metadata changed. Coverage
therefore triggered direct-source inspection. Graft workspace freshness also
reported drift; repository-local `graft map/ask/skeleton` supplied current paths.
No negative claim here relies on a top-N graph search. This is a bounded audit,
not a full scientific review of every model in the repository.

## Fresh baseline and regression checks

| Check | Actual result | Boundary |
| --- | --- | --- |
| `npm run build` | PASS, Vite 3640 modules, server bundle generated | Chunk-size warnings; does not type-check |
| `npm run lint` | FAIL, existing TypeScript errors in multiple component files | Includes Keyhole `NodeJS` type, Recharts record types, inconsistent alloy properties |
| `npm run test:unit` | FAIL, module-inventory coverage/runtime coverage assertions | First sandbox run was EPERM; rerun outside sandbox reached real assertions |
| scientific venv `pip check` + `python/check_requirement_ranges.py` | PASS; all 18 declared requirement ranges satisfied | Warp is not declared or in this environment |
| scientific venv `environment_doctor.py --gpu-smoke --timeout 30` | CUDA training smoke PASS, RTX 4060 Laptop, Torch 2.11.0+cu128 | Docker engine unavailable; ParaView/pvpython absent from PATH; report `.runtime/phase0-audit/doctor.json` |
| scientific venv `test_lpbf_build_job.py` | PASS fast mode | Slow UQ/NIST not run; optional Warp fallbacks printed |
| scientific venv Eagar–Tsai, Goldak/Fabbro, meltpool accuracy scripts | PASS | Existing fixture envelopes, not a newly frozen independent experiment protocol |
| scientific venv `test_phase26.py` | FAIL: no worker reply | Direct worker launch exposed missing `warp` during eager import |
| system Python direct small keyhole call | FAIL: WarpCodegenError mutating constant `bounces` | Warp 1.17.0, CUDA 12.9/driver 13.4; NumPy 2.5.3/SciPy 1.18.1 exceed repo bounds |
| CPU venv `test_lpbf_worker_optional.py` before/after fix | FAIL missing Warp → PASS | Real JSON-lines worker; absent Warp/Torch simulated, CPU estimator real |
| CPU venv `test_lpbf_engineering.py` after import isolation | 25 PASS, 1 OpenFOAM SKIP, 21.194 s | Conservation, manufactured solution, mesh, artifacts, cache, cancellation; host CPU only |

Exact local interpreters: `.runtime/lpbf-win-py312/Scripts/python.exe` (CPU),
`.runtime/scientific-win-py312-cu128/Scripts/python.exe` (scientific), and
`C:/Users/can02/AppData/Local/Programs/Python/Python312/python.exe` (system Warp).
`py -3` selects Python 3.14.5, whereas `python` selects 3.12.10. Package scripts
using `py -3` do not establish that the intended scientific environment is used.
No packages were installed or lock files changed by this audit.

## Findings and repairs

1. **CPU worker availability repaired.** Three eager imports (`lpbf_keyhole_raytracing`,
   `lpbf_modulus_fno`, `lpbf_transient_3d_gpu`) made optional GPU dependencies
   mandatory for every RPC and queued CPU subprocess. Import each only in its RPC
   branch. Missing-backend errors remain visible and later requests still work.
2. **Keyhole is unqualified and initially non-executable.** In addition to the Warp
   compile failure, inputs are unchecked/coerced, NumPy's global RNG is unseeded,
   grid spacing differs from advertised dx/dy, the reflection clamps backface dot
   products, and escaped versus bounce-limited power are combined. No sampling
   convergence or uncertainty report exists. The angular absorption rule is an
   empirical approximation, not a complex-index Fresnel solution. Gaussian cavity
   geometry is prescribed, not a thermally solved surface.
3. **Keyhole UI route is disconnected.** `KeyholeRaytracingLab.tsx` fetches
   `http://localhost:5000/rpc`; `routes/lpbfSimulation.ts` has no keyhole or
   transient-3d-gpu route. Worker supports those method strings over stdin.
   UI lacks visible failure/stale-response rejection and geometry disposal.
4. **There are distinct things named orchestrator.** `python/orchestrator.py` is
   a standalone demo: replaces input power with 250, sleeps, publishes 1500 as
   maximum temperature, no solver, no cancellation, uncaught task exceptions,
   no returned final state. `routes/orchestrator.ts` and `AIOrchestratorPanel.tsx`
   instead perform external AI dataset planning, not simulation. Sol/Astra are
   optional, but the UI marks every card Completed when any result exists. No
   end-to-end cancellation; local approval state is not an ingestion operation.
   `server/processOrchestrator.ts` supervises the actual Python IPC service.
5. **Existing queue should remain the owner.** UI engineering workspace →
   `/api/lpbf/jobs` → `server/lpbfWorkerBridge.ts` → `python/lpbf_worker.py` Queue →
   isolated `lpbf_simulation.run` subprocess. SQLite tracks terminal states;
   cancellation kills the child, startup marks interrupted jobs failed, integrity
   gates reject corrupt artifacts/results. Direct lab RPCs bypass this queue and
   block the input loop; their timeout is not cancellation.
6. **Fabricated output candidates confirmed in source.** FNO instantiates random
   untrained weights on each request, adds an artificial spatial temperature
   profile and invents cooling rates. Battery/corrosion ingestion fabricates
   missing measurement curves; uploaded-EIS analysis invents K–K residuals from
   frequency and reports PASSED. Micrograph `--export-only` exports an untrained
   network. These require removal or explicit unavailable behavior, not relabeling
   as experimental evidence. Legitimate equation-based simulation and test
   fixtures are distinct and must not be deleted merely for a keyword match.
7. **Material authority is duplicated.** Worker thermal-accumulation branch has
   four hardcoded presets and silently substitutes Ti64 for unknown materials;
   several direct lab branches have independent default constants. These need
   migration to the material authority with explicit missing-data rejection.

## Outstanding Phase 0 acceptance work

- Complete fresh visible-module route/data/test mapping and reconcile inventory.
- Run isolated live API and browser checks, including failures/stale inputs.
- Verify WSL outside the initial sandbox access denial; do not call it absent.
- Measure a small thermal run's wall time, peak memory and artifact volume.
- Check benchmark raw hashes and source/use conditions against manifests.
- Run isolated Node SQLite transaction/backup/restore spike and write ADR.
- Finish fabrication triage, keep unimplemented capabilities unavailable, and
  record any still-open scientific/model limitations individually.
- Write the first dependent implementation plan only after this baseline gate.

## 2026-09-21 successor verification and repairs

These observations supersede the initial defects above only in the stated scope.
Phase 0 remains open. No experimental qualification or all-engine audit is claimed.

- Keyhole repaired in Python: bounded finite inputs before allocation, executable
  dynamic Warp counter, grid spacing and two-sided reflections, local PCG64 seed,
  separate absorbed/escaped/bounce-limited energy, sampling standard error and
  explicit empirical/prescribed-geometry limits. Six numerical/software tests pass
  on system Python 3.12/Warp 1.17 (CPU and CUDA); system NumPy/SciPy exceed the repo
  ranges, so this is not clean locked-environment reproduction.
- Same-origin keyhole Node route is now connected. `test_phase26.py` uses an
  isolated temporary job directory and cleans up a timed-out subprocess. Worker
  RPC PASS. HTTP regression PASS. The UI uses the shared LPBF power/diameter,
  invalidates results immediately, aborts HTTP and rejects stale replies, disposes
  mesh geometry, and exposes backend/seed/sampling/error/energy/model limits.
- Actual browser on isolated port 3188: 280 W, diameter 80 um, depth 120 um,
  absorption .35, 4096 rays, seed 0, CPU → 208.007 W absorbed, 71.990 W escaped,
  .003 W unresolved (rounded display), 74.29% absorption, .160 percentage-point
  sampling standard error. Changing rays to 1 immediately removed results, then
  showed `num_rays must be in [32, 100000]`; restoring 4096 recomputed the result.
  Tab advanced from Rays to Random seed; focus, controls, limits and 3D geometry
  were visually inspected. Initial browser timeouts resolved after page loading.
  HTTP abort is NOT worker computation cancellation; direct lab queue work remains.
- Live API exposed WSL-first selection ignoring explicit METALLIX_PYTHON for the
  LPBF worker. Added failing regression, then made the explicit executable take
  precedence. Without it WSL-first remains. Runtime/API tests: 16 PASS. Actual API
  with 1024 rays, seed 17, default model, CPU: 142.8692584000528 W absorbed,
  107.13074159994721 W escaped, zero unresolved/closure error.
- Curved geometry sensitivity: `python/benchmark_keyhole_convergence.py`, fixed
  200 um aperture, 250 W, radius 50 um, depth 120 um, absorption .35, 16384 rays,
  seed 17, CPU. Absorption at 32/64/128 nodes per axis: .71489646/.71137585/
  .70515435, standard errors .00080579/.00075287/.00076420. All energy closure
  errors zero. At 128 nodes, 4/8/16 bounces agree with zero unresolved power.
  Mesh differences do not decrease regularly: asymptotic convergence is NOT
  established. No tolerance was relaxed or experimental conclusion drawn.
- FNO now rejects inference until a trained validated checkpoint, provenance,
  normalization and applicability contract exist. Scientific venv rejection test
  PASS; retained network architecture is not a registered trained model.
- Standalone orchestrator runs the actual reference solver with unchanged inputs,
  balance checks, error propagation and cooperative progress cancellation. Battery,
  Tafel, EIS and OCP ingestion require observed aligned finite data. Tafel units are
  explicit and opposing branch regression intersection replaces invented icorr.
  Uploaded EIS uses actual Voigt residual screening, never a fabricated PASS.
  `test_no_fabricated_outputs.py`: 10 PASS on CPU venv, including valid battery,
  analytic Tafel, A/mA/uA/log(A) equivalence, invalid branches and in-flight cancel.
  Tests are analytic/software fixtures, not measured experimental validation.
- Tafel automatic branch selection and severity heuristics still need a scientific
  applicability review. EIS underlying clipped normal-equation fit remains screening.
  UI EISUploadInsightsStudio and PhysicalValidationStudio fabricated fallback paths
  and default compliance metrics are still OPEN, as is untrained micrograph export.
- Inventory now maps all 35 registered modules including environment groups;
  FNO is explicitly unavailable and transient GPU's missing HTTP route stays a gap.
  Targeted inventory tests 3 PASS. Initial full unit run: 109 PASS / 2 inventory
  FAIL; rerun after correction recorded below. Build PASS (24.36 s Vite), existing
  large chunk warnings. TypeScript lint still FAILS in preexisting components;
  no Keyhole diagnostics. Logs: `.runtime/phase0-audit/*-successor.txt`.
- Local Graft refreshed changed files. CBM remains generation 2026-09-18T15:50:24Z;
  targeted coverage was stale/untracked and direct sources superseded it. Parent
  STATUS.md is the active continuation point, updated at each meaningful checkpoint.

Final full unit rerun after inventory corrections: **111 PASS / 0 FAIL**, 2.564 s.
This does not clear the separate TypeScript lint or Phase 0 scientific gates.

## EIS frontend repair — continuation 01a0c11f

- Removed fabricated upload-analysis and physical-validation fallback reports,
  default compliance scores and the unconditional ASTM/ISO certificate. Missing
  metrics stay unavailable, actual zero stays zero. Export requires a current
  result; absent partial-report sections cannot retain previous metrics.
- Shared request hook binds results to serialized inputs, clears on retry/change,
  aborts HTTP and rejects late replies even when transport ignores abort. It does
  not claim cancellation of Python computation. Upload record result cache removed.
- Found `eisFileParser.ts` examples are generated circuit spectra, despite names
  and instrument metadata. These two studios and reports now label them synthetic;
  fabricated fixed charging/corrosion guidance removed. Other consumers and the
  underlying example metadata still need a source/provenance audit.
- Fresh unit **117 PASS / 0 FAIL**; build PASS (25.35 s, chunk warning). Lint still
  FAILS with previous component diagnostics; none in the two studios/shared hook.
  Logs `.runtime/phase0-audit/{unit,build,lint}-eis-final.txt`.
- Browser: actual components mounted in `tests/eis-browser.html` using real Node
  API → Python at isolated ports 3190/5190. Physical CPE 8.2761 uF, Lin-KK score 0
  displayed as returned; uploaded EIS displayed SCREENING, not invented DRIFT/PASS.
  Test-only transport controls verified HTTP503 removes prior results, missing
  report sections stay unavailable, exports disable on failure/pending, and an
  old delayed success cannot replace a newer error after temperature/area change.
  Keyboard Tab moves temperature → nominal capacity; screenshot inspected.
  This is UI/software evidence on synthetic input, not experimental validation.
- Underlying CNLS clipped normal-equation fit, small-input fabricated score in
  its direct API, broad backend stationarity/compliance strings, heuristic SOH/
  DRT interpretations and examples elsewhere remain scientific/audit gaps.
  The physical studio rejects reports with no residuals rather than showing the
  backend's insufficient-points score. No Phase 0 gate is accepted by this repair.

## Micrograph training/export guard repair — continuation 01a0c11f

- Import no longer runs pip when segmentation-models-pytorch is missing; training
  reports the missing dependency. No packages installed and no pretrained weights
  downloaded. ImageNet download removed from the research training path.
- `--export-only` and direct `export_to_onnx` explicitly refuse export until a
  supported trained checkpoint, provenance, preprocessing/class contract and
  independent evaluation exist. Tensor shape verification is not validation.
  Existing outputs are neither overwritten nor removed. No ONNX was generated.
- Nonpositive/noninteger epochs, invalid batch size or learning rate, missing
  data pipeline and empty training/validation splits fail before model allocation.
  Non-finite losses abort. The expected local module
  `python/lpbf_real_dataset_pipeline.py` is absent (coverage missing + filesystem
  checked), so research training is currently unavailable too. No training run or
  segmentation accuracy is claimed; retained training code is not qualified.
- Scientific Python3.12 venv `test_micrograph_export_guards.py`: seven PASS.
  Initial controlled red reproduced installer attempt, random model creation,
  zero-epoch initialization and unguarded export. Backend nonfabrication regression
  suite remains ten PASS on CPU venv. Logs in `.runtime/phase0-audit/`.
- EIS test server PID41348 and captured children stopped; no listeners remain
  on 3190/5190. Unknown-owner HMR24678 was left untouched. Phase0 stays open.
# 2026-09-21 — Python synthetic recovery contract

Owner01a0c326. Four focused regressions first failed, including actual CLI
constant-magnitude benchmark failing on null R-squared. After repair 4/4 pass;
existing CNLS12/12 and no_fabricated_outputs10/10 pass with lpbf-win-py312.
Recovery preserves missing values, undefined zero-denominator percentages and
unavailable uncertainty; aggregate percentages require every row. No arbitrary
robustness grade, inferred reliability, default convergence/time or score.
One synthetic realization is not experimental qualification. Frontend migration
and its tests remain pending; Phase0 is open.
