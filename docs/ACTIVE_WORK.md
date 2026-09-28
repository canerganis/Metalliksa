# Active delegated LPBF work — 2026-09-27


## Active implementation handoff — 2026-09-27

User-selected shared checkout remains in force; no worktree move, staging, or
commit. Luna owns the Warp v2 code package: `python/lpbf_worker.py`,
`python/lpbf_gpu_thermal.py`, `python/lpbf_gpu_thermal_warp.py`, associated
Python tests; and strict TS identity/archive/client/UI boundaries in
`server/lpbfGpuRunIdentity.ts`, `server/lpbfGpuRunArchive.ts`,
`server/lpbfRunRepository.ts`, `src/types/lpbfRun.ts`,
`src/services/lpbfSimulationService.ts`, `src/services/lpbfRunArchiveClient.ts`,
`server/lpbfRunImport.ts`, `server/lpbfRunArchiveService.ts`,
`server/lpbfRunBundle.ts`, `src/components/3d-distortion-lab/LpbfEngineeringSimulation.tsx`,
`src/components/LpbfRunArchivePanel.tsx`, with the nearest tests. Keep Torch v1
unchanged; Warp is a strict v2 engine union. Root owns evidence/docs, parity/
performance assessment and integration review; Sol/Astra are read-only auditors.

GPU results on the captured same input: Warp-vs-Torch backend pilot ratio
1.294x; moving Torch source integration CPU→CUDA only 1.019x; profiler exposes
host dispatch/sync but no device-kernel times. Do not change the source default
from this weak delta. CPU/Warp and CPU/Torch parity both pass. IN718 experiment
remains unvalidated; IN625 remains screening-only; fine CPU convergence remains
inconclusive.

## Current checkpoint — 2026-09-27T18:18Z

User chose the old shared checkout workflow and deferred worktree workflow. Do
not move changes or create new worktrees. No commits have been made for the
current packages; user requested committing them together later.

- Fine scan-end CPU series and Node GPU archive UI/API package are complete at
  their bounded scopes. Sol independently audited persisted run/source and
  export/import/restore identity; no new solve or HTTP was run for that audit.
- Warp opt-in state capture was implemented and reviewed. Actual CUDA test
  passed, and a same-input CPU/Warp numerical report is saved (SHA `4fb7a039574524d8522253603f96bd7f31c21896ad754df87fc06cc2c90dbaf5`).
  CPU/Warp model state is not yet integrated into the public archive contract.
- An alternating RTX 4060 GPU pilot measured Torch median 10.483 s and Warp 8.102 s (three trials each); same-case CPU/Warp and CPU/Torch numerical gates both pass. No profiler attribution or application-wide speed claim.
- IN625 remains screening-only; source audit did not establish uncertainty or
  lot-matched experimental properties, so no full-transient admission.
- Remaining: add or explicitly withhold Warp archive integration; repeated,
  profiler-backed attribution and representative repeated performance checks; applicable independent
  IN718 experiment; finish general source/run/result API/UI restore/export
  checks; keep unresolved convergence and missing validation as unvalidated.
- Next action: integrate a backend-neutral CPU/Torch/Warp evidence descriptor
  only if exact solver/material/input identity remains preserved; otherwise
  keep Warp diagnostic-only, then profile the measured hotspot before any
  result-preserving optimization.

Integration owner: current goal task `01a0df9c-3718-7451-8f47-39d2bd9c7168`,
shared checkout `Metalliksa-1`, branch `codex/lpbf-buildjob-material-identity`.

User reverted the worktree workflow: continue in the original shared checkout.
Three070aa37-based worktrees were created but no files copied or agents assigned;
leave them idle. Separate scopes and root-only index remain. Commit after
package acceptance. Fine91816 finished17:34:27Z/exit0; final admission PASS,
mesh/time/overall INCONCLUSIVE, energyPASS, sourcefbef fixed. Numerical source
freeze readback complete; Warp remains next separate implementation package.
GPU UI path fix parent5/5+Sol10/10PASS; browser import/bundle acceptance pending.

Node integration candidate: parent24+48+4 tests, lint/build PASS; Sol21 pure
checks PASS. Initial prototype mismatch and metadata gate omissions are closed.
Actual same GPU job/source rev1 preview200/12refs135737B PASS. Production
browser source selection reload PASS, but GPU panel omits its own archiver.
Luna now owns the narrow completed-bound GPU archiver UI/test fix (same16
paths; only engineering UI/test expected to change); Sol independent review.
Root owns real API/browser on new runtime session32477, HTTP4176/IPC5056,
IABtab3 and evidence/docs/index. No new GPU solve. Fine PID6556 remains live;
all numerical/protocol/wrapper sources stay frozen. Do not restart it.

Numerical partial package: exact two-new-row snapshot25030a53... retained;
Astra independent admission and root two-NPZ/ten-array/selected-clock readback
PASS. Frozen20/10/5 mesh axis INCONCLUSIVE(width trend unresolved); depth and
energy PASS. No time/overall verdict. NPZ250us is not final350us energy/time
replay. Root commits this scoped evidence without waiting for Node integration;
final12.5ns remains live and all numerical/protocol/wrapper sources frozen.

Latest committed foundationdf030da; five source/two report Git bindings PASS.
Luna Node integration is mutable, including current archive GET verification,
RunArchivePanel and SourceArchivePanel selection persistence. Root actual
IABtab2 on4176 comparison stage passes keyboard officialXLSX selection/verify,
revision1/SHA73293ca6...; consoleerrors[]. Reload resets source choice to first
dataset; explicit reselection preserves stored revision/hash and correctly
reports bytes not checked in this view. Luna fixes the selection bug, root
retests after production rebuild. Keep previous engineeringGPU/scientificContext
UI files frozen; numerical source freeze remains until fine row12.5ns ends.

User requests sustained parallel independent work. Current capacity is root
plus three agents: Astra science/architecture, Luna implementation, Sol
independent read-only review. Split owned paths; do not create duplicate work
or edit numerical manifest sources during the live fine continuation.

Foundation final gate: parent27/27+lint PASS, Sol31/31 final and prior8/8 reader
PASS, Astra509 serializer/oracle examples PASS. All three reported defects
closed; frozen five helper/test source hashes are in the foundation report.
Root integrates only that package and evidence. Luna next owns run types,
repository/import/bundle/client/archive panel and necessary NIST/proxy exclusions
plus nearest tests. Foundation five files stay frozen; no Python changes.
Actual source API official optical revision1 import/verify PASS. Same completed
GPUjob preview fails503/classification; baseline report retained. Next actual
acceptance uses this same job/revision, avoiding a replacement GPU solve.
Fine state2reused+2newcomplete; final12.5ns row running. Hold source freeze.

Current integration HEAD8e59c3e; saved-input browser package committed. Five
top-level evidence reports pass exact Git-byte hashes. TS GPU foundation is
frozen: new bounded JSON/identity/numerics modules, shared artifact reader,
and one test. Parent27/27 focused tests PASS, zero skips; Sol read-only
adversarial closure is active. Repository/import/bundle integration remains
the next separate Luna package. Root owns evidence/docs/index/commits.

Sol found a concrete P1 in frozen identity f4e02fcf...: alternate Unicode
string escaping could mint a semantically unchanged material revision accepted
by TS but rejected by Python core identity. Initial27 tests did not cover it.
Luna owns the TS-only admission fix/regression; Sol closure required before
foundation commit or archive integration. Numerical Python source freeze holds.

Fine continuation now has2 reused+1 completed new row:5um25ns,
526592cells14000steps, before=recorded=afterfbef0..., NPZ retained. Remaining
two rows run serially; source freeze remains, no convergence verdict yet.
Astra's single small cProfile diagnostic preserved five CPU arrays byte-exact;
root verified committed archive lineage without solving. Candidate Goldak and
Gaussian optimizations are unimplemented. Contended profile time is not a
benchmark; evidence is LPBF_CPU_PROFILE_DIAGNOSTIC_2026-09-27.json.

Latest UI acceptance: parent11/11 focused tests, lint and production build PASS;
Sol15/15 independent pure cases PASS. Actual browser saved/current fields,
partial match, device difference/return, keyboard comparison and final reload
PASS, no console errors. Original browser failure retained; new scoped report
ef16b4d7... does not accept the overall workflow or experiments. No new GPU solve.
Luna now owns only new server/lpbfGpuRunIdentity.ts, bounded JSON token helper,
server/lpbfGpuPilotNumerics.ts, shared-resolver server/lpbfGpuPilotArtifacts.ts,
and nearest tests. No UI/types/repository/import/bundle or Python edits in this
package. Root docs/index/integration; Sol independent review. Actual committed
job2bcb fields are cross-language fixtures; no mock data presented as measurement.

LIVE fine CPU continuation: session91816 / PID6556, started
2026-09-27T15:55:37.665575Z, execution commit0459d6c. Persistent partial stage
running with2 reused rows/0 new rows at launch; expected fingerprint fbef0...
matches. Only three missing5um rows run. Hold original protocol/runner/addendum/
wrapper/coarse bytes and all numerical manifest sources, including Warp, until
the series ends. Do not restart or replace failed rows. Luna's UI then pure TS
archive work may proceed; avoid heavy GPU/CPU benchmarks during this solve.
Root owns process/proofs/docs/index; ordinary slow progress is not failure.

Previous ready gate: parent18/18 continuation/observer tests PASS9.532s; Sol9/9
independent pure closure PASS. Wrapper e25774cf... and addendum19a5f5c4...
are frozen. All three continuation defects are closed; no missing5um solver
has launched. Root preserves exact protocol/coarse/scenario/wrapper dependency
bytes in Git before launching only the three missing cases. Numerical source
fingerprint fbef0... stays fixed throughout. Luna now owns only GPU-panel
executed-input/mismatch presentation and the LPBF scientific-context label
plus nearest tests; no numerical or archive schema changes yet. The prior
browser failure is committed da90525 and its12 files pass Git numeric readback.

Previous review gate: no missing5um solver had launched. Sol found original
output paths / prior-failure guard mismatch, undefined case ordinal index, and
missing40MB NPZ pre-decode admission. Luna owns wrapper/test/addendum fixes;
Sol independent closure and parent focused tests precede any fine launch.
The original protocol, runner and coarse evidence stay immutable. Root owns
PROOF/STATUS/ACTIVE_WORK/index; preserve all unrelated changes. The actual
browser partial failure and completed job fields are retained for review.

Previous verified checkpoint: worker/capture/client package committed7fb7e66, parent37Python/18TS
tests, lint and production build PASS; Sol independent review clean. Both actual
native outputs also pass the production client parser. Parent reconstructed all
24 committed manifest files from Git objects; byte/numeric readback PASS.
Actual native-worker retry
capture/cache/reopen PASS,12 fields/input/capability files,15.898s. First attempt
cache miss is retained: editing test_lpbf_gpu_queue.py during execution changed
the broad all-Python cache fingerprint despite identical input/capability bytes.
No solver is live. Luna now owns only new fixed-scan-end continuation wrapper,
reuse addendum and focused tests; original protocol/runner/coarse report stay
immutable. Astra actual coarse admission PASS. Root integrates scoped commit.
Permanent GPU Node archive remains disabled: next Luna package is exact-string
identity verifier, shared local/content-store bounded reader, and pure TS
numerical assessor; then run types/repository/import/bundle validation. Store
save is metadata-only and must not claim field verification. Nested CPU core
never grants GPU CPU/NIST/proxy-campaign eligibility. Freeze all numerical
manifest sources including Warp throughout the three missing fine CPU rows.

Actual production browser acceptance is partial: keyboard IN718 CUDA submit
job2bcb01e5799041ec9458a947506d491f completed/bound12files/parityPASS; comparison
disclosure and same-job/hash reload PASS. Concrete input-presentation defect:
reload resets advanced controls20um/1us while saved job40um/200ns remains pass,
without executed-input summary/current-input mismatch. Luna will fix the GPU
panel and nearest UI tests after continuation handoff. Preserve failed UI
observation in docs/LPBF_GPU_BOUND_BROWSER_ACCEPTANCE_2026-09-27.partial.json,
SHA4873e3bb5eaf746c9f79c3faac698effea69d8941652de1b8dba982b6fa2c3e9.
Owned production runtime session83814, HTTP4176 loopback/IPC5056; IABtab1.
The initial default-IPC runtime was stopped after verifying its IPC child PID
belonged to our node; no unrelated process was stopped. GPU browser job is
complete; no convergence solver is live. An extra Luna spawn was rejected by
the agent thread limit; use the existing Luna sequentially rather than retrying.
Astra new Naderi131um broad-spot candidate is unvalidated: the archived XLSX
contains72 IN718 rows with48.25168–80um spots only, no110/131um candidate.
Do not substitute narrow-spot measurements or redownload the same workbook.

Current continuation ownership (2026-09-27):

After the model-switch interruption, the previous agent handles were absent.
Replacement agents now own the same bounded tasks: `gpu_producer_luna` owns
only `python/lpbf_gpu_thermal.py` and `python/test_lpbf_gpu_archive_producer.py`;
`gpu_review_sol` is read-only; `gpu_numeric_astra` defined numerical archive
guards and historical raw/resolved-input binding. `fixed_observer_luna` owns
only `python/lpbf_simulation.py` plus new fixed-scan-end protocol/test files.
Both numerical-source owners finished/froze before parent real CUDA acceptance.
No new convergence series is live.
Sol reproduced accepted invalid nested CPU hashes, traversal/oversize/duplicate
manifest entries and float32 declarations. Luna is closing those defects.
Producer foundation is now held stable after seven focused tests. Parent's
permitted default queue compatibility suite passed 5/5 including one real CUDA
job; this is not the new bound-field archive acceptance or a frozen benchmark.
`gpu_review_sol` closed 29 previous defects and found one remaining malformed
field-metadata error path. Luna added typed guards and five malformed fixtures;
the seven focused producer tests pass without CUDA. Sol now rechecks that
closure and numeric overflow handling. `gpu_numerics_luna` handed off the new
pure numeric validator/test files (11 tests). The producer integrates it after
bounded byte/hash readback. Sol final producer closure is 40/40; parent combined
producer/numeric/codec/legacy-queue regression is 33/33 PASS with real CUDA.
Parent real bound acceptance is PASS: 1,210 cells, 934 equal accepted dt steps,
12 manifest files/131,480 bytes, stable source hash fbef0bde60ea3fa1b16a009e97ea2db718fff835af1abfec59590cfded01761c.
Evidence is in docs/LPBF_GPU_BOUND_ARCHIVE_ACCEPTANCE_2026-09-27.json and its
artifact directory. This does not enable worker/capture/TS/UI GPU archives.
Fixed-time observer parent tests are 7/7 PASS, including a bounded real-solver
callback mutation comparison with cooling after the selected event.
The physical observation is the first scan end (250 microseconds), not the
cooling endpoint (350 microseconds). The prior UI session 17083 handle is missing and HTTP4176
refuses connection; create/restart an owned acceptance runtime when needed.

Next concrete integration: wire the bound producer through lpbf_worker.py and
lpbf_run_capture.py, then separate GPU TS parser/repository/bundle byte resolver
and UI without granting CPU/NIST eligibility. Preserve the already recorded
acceptance fields and legacy GPU behavior. Warp still lacks actual H/rho/dt
capture; five alternating CPU/Torch and CPU/Warp end-to-end pairs remain open.
The five-case fixed-time protocol has not run. Refresh its implementation
binding only before execution if covered numerical sources change again;
hold all covered sources throughout the five-row series once it starts.

Current package is committed as `4c15513`. Parent re-exported all 12 artifact
files from committed Git objects into a new isolated directory: exact manifest
hashes and full numerical readback PASS. Raw acceptance JSON and f64 files have
Git attributes preserving bytes across line-ending conversion. Graft refresh
was attempted and stopped at the known inaccessible lpbf-run-shape directory;
use exact source fallback for uncovered/new nodes.

Next active ownership: `gpu_producer_luna` owns only Python worker/capture plus
focused tests. `gpu_review_sol` maps the current client parser rejection before
enabling new queue output. GPU bound results must be accepted by the client
parser in the same integration package; its old empty-artifact requirement
would otherwise reject newly bound jobs. Astra completed the five-pair IO
protocol: add single-backend write/read APIs plus an assembling descriptor to
the codec, retaining the existing pair writer's validation-before-write.
Each backend row times its own normalize/solve/capture/write/readback; pair
assessment and overall pair wall are separate, never allocated arbitrarily
between backends. No second CPU solve or dummy other-backend state is allowed.
Warm-up is separate; five alternating pairs retain failures and elapsed error
durations without replacement runs or speedup claims from failed parity.
`gpu_producer_luna` additionally owns src/services/lpbfSimulationService.ts and
tests/lpbf-gpu-pilot-client.test.ts, after Sol reproduced the actual bound
result rejection. Client bound/legacy branches must reject partial/null GPU
metadata and any top-level CPU core; preserve existing numerical identity
guards. Only enable worker bound output coherently with this parser change.
Warp actual-field capture task is not started (agent thread slot limit);
finish/release current bounded work before assigning it to a Luna.

Parent coarse P4 observation check completed (session4160 exit0). 20 micrometres
at25ns:8,228 cells/14,000 final steps,25.922s;10 micrometres:65,824 cells,
14,000 final steps,149.319s. Both selected-state clocks differ from the250us
target by5.708e-17s within1.084e-15s; final energy error1.631e-13. Selected
NPZ fields contain10,000 steps at250us; final row metrics are at350us. Their
enthalpy integrals must not be compared to final stored energy. Parent field
byte/array hashes, finite values and sequential accepted-clock replay PASS.
This two-row observation check does not establish numerical convergence.
The report/NPZ directory are docs/LPBF_P4_FIXED_SCAN_END_OBSERVATION_CHECK_2026-09-27.json
and docs/LPBF_P4_FIXED_SCAN_END_OBSERVATION_CHECK_FIELDS_2026-09-27. Report SHA
e35bc891d167db66e39c3ee7a24daf4f2cdbbd0a103dadf3da8bbc9efb0948a7.
Astra approved a separate hash-bound reuse addendum and continuation wrapper,
preserving the original five-case protocol/runner and coarse report unchanged.
The addendum must explicitly record this execution change after coarse results
and before fine results. Admission must recompute contours and resolved input
identity, validate model/material/source identities and final energy closure,
pin report/NPZ/array/protocol/harness/wrapper hashes, and retain all five unique
cases. Only the three missing5um cases then run; no cherry-picking or replacement
failures. All manifest sources including Warp stay frozen throughout those rows.
Current numerical fingerprint fbef0bde60ea3fa1b16a009e97ea2db718fff835af1abfec59590cfded01761c.
No solver is live. Astra is auditing actual coarse admission; Luna finishes the
worker/capture/client package before implementing the separate wrapper/addendum.
Sol independently reviews that package. Root owns combined tests and commits.

- User model assignment: Astra owns difficult scientific/architecture decisions;
  Sol owns bounded reviews; Luna implements code changes. Parent owns integration,
  live browser acceptance, scoped commits, PROOF and STATUS.
- `gpu_archive_astra`: primary-paper screen finished and committed `f3b4898`.
  Now read-only scientific design of archive numerical consistency guards:
  recomputed temperature norms, enthalpy energy, accepted timesteps and valid
  failed-parity records. No code edits or heavy runs.
- `artifact_review_sol`: completed archive seam review. Manifest must include
  input/capabilities as well as ten binary refs; new descriptor refs are a
  matching subset, not the whole manifest. Legacy GPU remains view-only.
  Now maps TS parser/repository/bundle/resolver integration and checks the
  observed broad capability availability labels against the four-alloy guard.
- `artifact_fix_luna`: precision fix `501c43f`, endpoint fix `1249ba1` integrated.
  Capture implementation `e98a424` is handed off and parent verified:
  CPU/CUDA capture/artifacts 13/13 PASS, actual Warp parity 1/1 PASS. No
  worker/archive wiring in this package. No live solver remains from these tests.
  New ownership: only `python/lpbf_gpu_thermal.py` and new
  `python/test_lpbf_gpu_archive_producer.py`, opt-in artifact_dir producer and
  strict versioned GPU contract guard. No worker/capture/TS wiring yet. Default
  producer must preserve legacy behavior. Parent integration/commit follows.
- `readiness_finish_luna`: owns `server/lpbfWorkerBridge.ts`,
  `routes/lpbfSimulation.ts`, `tests/lpbf-worker-readiness.test.ts`; completed
  readiness/recovery fixes. Parent 13/13 tests and lint passed; Sol replayed
  four concrete race/transport repros and closed all. No live restart.
  Parent subsequently completed isolated real-Python HTTP delayed-startup
  recovery: 503 then 200, one native launch, committed `c5b0b93`. This fixture
  is stopped; user/runtime ports were not changed. No new agent was started
  for fixed-time convergence because the agent thread limit was reached;
  its observer/protocol work remains pending the current Luna handoff.
- `in625_gate`: finished the two property-source catalog entries, source scope,
  UI and tests. Parent owns acceptance/commit. Original sources were committed
  as `cdc4c58`; full model admission remains closed.
- `hmr_binding`: handed off its readiness patch (8 tests passed) to Luna.
  Current parent-owned live server: session 17083, port 4176, IPC port 5056,
  DISABLE_HMR=true for stable acceptance during parallel edits. Preserve other
  applications using 5055. Prior agent-owned session 62530 has ended.

Completed previous package:

- Parent: integration complete for the packages below; owns the pending endpoint fix after the CPU diagnostic finishes.
- `gpu_result_contract`: completed queue input/material integrity repairs (`66aed0b`, `ed9cc9e`); left the real CUDA endpoint regression in `python/test_lpbf_gpu_thermal.py` failing and uncommitted pending the frozen run. No numerical manifest edits.
- `hmr_binding`: completed HTTP/HMR isolation (`89703e5`) and application-only dependency discovery (`aedc614`); existing uncommitted HOST edit preserved. Combined runtime tests 4/4 passed.
- `in625_gate`: completed source-candidate follow-up in the existing IN625 evidence matrix (`66aed0b`); full admission remains closed.

Previous packages were reviewed, tested and committed; current work above is
still in progress. Unrelated edits remain untouched.
CPU diagnostic session 1840 completed, exit 0, all frozen hashes verified.
`06132ae` preserves the inconclusive discrete/continuous time refinement.
The numerical source freeze is lifted. GPU archival needs a distinct contract
and complete field artifacts; CPU core-v1 must not be relabeled.

Astra's next implementation contract: `runKind=gpu-thermal-pilot`,
`contractStatus=gpu-pilot-v1-bound`, separate `gpuRunContract` and
`gpuFieldArtifacts`. Preserve Python-serialized input/material/CPU-input JSON
hashes and the historical implementation fingerprint; do not rehash JSON by
Node serialization or compare restored runs to current source code. Add opt-in
CPU final-state observer and GPU final H/rho/dt capture from actual arrays;
never reconstruct H from T or run a second solve for archive capture. Descriptor
references ten binary arrays, while `write_artifacts` must manifest the whole
job folder including input/capabilities. Extend worker, capture, repository,
import/bundle byte/numeric verifier, client and RunImport UI in that order.
Permit sound failed-parity records; legacy GPU records remain view-only.
Recompute saved temperature norms and energy/step metadata consistency from
artifacts at archive boundaries. Experimental validity remains false.

Sol TS integration map (read-only review, not implemented):
- `lpbfSimulationService.parseGpuPilotJob`: separate legacy/new branches;
  partial/null new fields and top-level CPU coreContract are errors. Keep
  `parseSimulationJob/checkCoreContract` CPU-only.
- `src/types/lpbfRun.ts` and repository unions: add distinct GPU run/status;
  repository dispatch uses GPU requestSummary from stored settings. Validate
  SHA256 of exact Python serialized strings in Node, structural snapshots and
  nested CPU input binding; never hash a Node reserialization. Historical
  implementation binds to saved provenance, not current source.
- `server/lpbfGpuPilotArtifacts.ts`: internal ref resolver with default local
  read and archive `store.verify({sha256,byteSize})`; both use the same bounded
  reader/numeric checks. Do not derive object-store paths from logical paths.
- Import dry-run uses local artifacts; post-putFile/save and bundle
  backup/verify/restore use the object-store resolver. Preserve original
  source revisions even if current source archive has newer revisions.
- GPU must remain ineligible for CPU NIST/proxy campaigns, including direct
  repository saves and bundle references. A nested CPU parity core contract
  does not grant experimental eligibility. Test local/store equivalence,
  rehashed invalid fields, failed-parity archives, missing queue folder after
  restore, legacy/partial contracts and unchanged CPU archive regressions.
- Current numerical guard checks detailed summary math only for overall
  `pass`. Before enabling GPU archive capture, verify self-consistency for
  `failed/inconclusive` too; failed backend agreement is valid evidence,
  fabricated/inconsistent stored report values are not.

Astra numerical guard design (not yet implemented): validate every backend's
own cells/steps/time/preheat/mesh and accepted-dt min/max/mean; compare actual
H integral `V*sum(H)` to stored energy without multiplying density again.
Use FP64 roundoff bounds based on `u=2^-53`, `gamma(k)=ku/(1-ku)` and `sumabs(H)`,
not an energy-relative or arbitrary absolute floor. Suggested energy envelope
`2*gamma(n+2)*V*sumabs(H)/(1-gamma(n-1))`, n<=100000, with explicit overflow/
underflow treatment. Recompute T rise L2/max only for matching ordered grids
and sampling; mismatched but internally sound grids remain failed evidence
without fabricated norms. Norm integrity envelope may use gamma(4*n+32);
the original parity decision thresholds remain unchanged. Validate scalar
difference math and status precedence for pass/failed/inconclusive alike.
Final fields cannot reconstruct peak/history geometry, input/loss integrals
or alone prove constitutive H–T correctness. These limits must remain explicit.

Historical input binding decision: `validate_pilot_request` already returns
resolved p, including defaults/optics. The reference passed to CPU is derived
from that resolved request; the second CPU validate pass is a fixed point in
this allowlisted scope. Persist actual CPU result settings separately in
`cpuResolvedSettingsJson`; require it to equal `cpuInputJson` and the reference
derived from `requestJson`. Build the nested CPU core contract using archived
settings/material, not current registry replay. JSON string hashes remain
independent of the core's compact serialization. Future material/defaults
changes must not silently invalidate sound historical records.

Astra benchmark design (not yet implemented): current Warp module's
`benchmark_alternating` has only three Torch/Warp repeats and no CPU oracle/
full artifacts. Freeze the existing 60 W, 1200 mm/s, 10 micrometre,
layer-conforming IN718 case (expected 73568 cells/934 steps). After real Warp
H/rho/dt capture is added, run five alternating-order pairs for CPU–Torch and
CPU–Warp, one warm-up/backend, result cache disabled, no concurrent solve.
Measure host normalization/solve/synchronization/capture/write/readback wall
time; assess captured runs without a second solve. Keep every failed/slow
row. Save raw times, order, fields/hashes, versions/hardware/thread settings,
start/end fingerprints and parity. Separate profiling from timing; measure
source integration, transfers, host synchronization and observation costs
before optimizing. This driver alone is not application end-to-end evidence:
also measure submit/queue/result/persistent archive/readable-result, retaining
the GPU pilot CPU oracle cost. No speedup claim exists from this design.

Astra convergence decision (read-only assessment): the existing contours are
sampled at different peak-count times (250.150/250.100/250.0875 microseconds).
Do not reinterpret the small W/D changes as convergence. Next freeze a distinct
`fixed-scan-end-liquidus-cell-edge-contour-v1` observation at physical scan end
250 microseconds, laser x=100 micrometres, surface z=40 micrometres. Reuse the
same spatial contour calculation without peak-time selection or extrapolation.
Five unique cases cover mesh 20/10/5 micrometres at 25 ns and time 50/25/12.5 ns
at 5 micrometres. Run 20/10 micrometre observation checks before expensive fine
runs; do not launch before protocol/observer review and frozen hashes. Preserve
current energy/trend/finest-pair thresholds and historical P4 statuses. Record
T/H fields and crossing locations for diagnosis; no automatic further refinement
if the new observation is also nonmonotonic. Peak-selection is a plausible
contributor, not a proven explanation of the mesh trend.

# Previous LPBF goal owner — 01a0cfbf-d2ad-7f70-b94f-b89183eb819c, 2026-09-25

## NIST case 0 raw six-observation source regression (2026-09-25)

Pinned the exact AMB2022-03 Table 4 case 0 source records in the existing
workbook-reader regression. Official workbook SHA remains
`2cfaac96aaca3dabb77b7029f842cdcc7e75c5a2cf3577d0734823246364a931`. Source
rows 2–7 preserve line 1/2/3 at both 4.9 and 6.0 mm, P3/P4 part identifiers,
285 W, 960 mm/s, 67 µm, and each raw width/depth value. The full
`python/test_lpbf_nist_official_measurements.py` suite passed **4/4**. This
strengthens input provenance only; it does not implement an etched-optical
model observation operator or authorize residual/validation claims. Keep proxy
campaign v1 unchanged and create a distinct v2 contract only after its model
observable is explicitly defined.

## CUDA parity coverage — all four legacy registry alloys (2026-09-25)

The explicit CUDA reference-model parity tests now cover IN718 and 316L plus
AlSi10Mg and Ti-6Al-4V. Added the latter two to
`python/test_lpbf_gpu_thermal.py`. The focused four-alloy invocation passed
**3/3 test methods** (the new method contains separate Al and Ti subtests), and
Python compilation/diff check passed. All snapshots are registry
`estimated`/`estimated-legacy`. The tests verify explicit `cuda:0` thermal
evolution, CPU source integration, matching model/material revisions, and
same-input CPU/GPU numerical parity; validation remains false and no speedup
is claimed. IN625 remains limited to its separate bare-plate thermal-screening
path, not the generic powder transient. Next add alloys only after their
property evidence and uncertainty pass the material-data admission gate.

## Frozen diagnostic protocol — 40 W tied-peak endpoint spread (2026-09-25)

Before execution, froze `docs/LPBF_P4_CURRENT_40W_TIED_ENDPOINT_DIAGNOSTIC_PROTOCOL_2026-09-25.md`
for the exact frozen P4 40 W scenario at 20/10/5 µm, fixed 25 ns maximum
timestep. It records equal maximum molten-cell endpoints and compares the
existing production contour spread against an independent offline edge oracle.
This is diagnostic only (`acceptanceStatus=not-assessed`), leaves the frozen
P4 report untouched, and cannot establish experimental validity. Next execute
the registered runner once and add its report/protocol SHA evidence below.

Execution completed. Report:
`docs/LPBF_P4_CURRENT_40W_TIED_ENDPOINT_DIAGNOSTIC_2026-09-25.json` (SHA-256
`7a45ce57645b7b0bb88fe7a844dfdaffbae770d7872f62bcee3a5ac68e493235`);
frozen protocol SHA-256
`c5628e46eed810e6de7638742e2c15f1b94e60f1386df07cf1241c960d5b88ee`.
The 20/10/5 µm levels had 2,349/190/7 tied accepted maximum-count states; all
contours were valid. Production and independent offline oracle min/median/max
matched exactly for width and depth at every level. Width/depth ranges in µm:
20 µm: 70.689–72.477 / 28.623–29.656; 10 µm: 74.328–74.518 /
32.811–33.332; 5 µm: 77.7036–77.7063 / 34.6929–34.6963. The ranges do not
overlap between mesh levels, so tied-time selection does not account for the
mesh trend. First-endpoint cell-extent values and the original frozen P4
acceptance are unchanged. Runtime was 3,379.94 s; this is diagnostic overhead.

The diagnostic runner did not emit a new energy ledger. Energy values are
explicitly cross-referenced from the matching-input frozen P4 mesh levels and
are not presented as new measurements from this run. Actual execution HEAD at
start was `476a55e`; only status/continuation docs changed from code commit
`15b4663`, and implementation SHA-256 stayed
`72520e2a25c5a6b781e2c7a0bb8c501deadfe2d6c15ce73e017bbd22e56459d3`. The
diagnostic's `acceptanceStatus` remains `not-assessed`; frozen P4 remains
failed/inconclusive and experimental validation remains false.

Next: preserve NIST v1 `thermal-proxy-screening`; define a separately
versioned v2 contract using the six raw official observations before any new
comparison implementation. The etch/fusion-zone observation and measured beam
profile gates must stay explicit; proxy residuals cannot be called validation.

## Continuation checkpoint — frozen 40 W P4 and provenance repair (2026-09-25)

The frozen six-run IN718 CPU study is complete and recorded in
`docs/LPBF_P4_CURRENT_MODEL_40W_2026-09-25.json`. Energy closure passed with a
maximum relative error of `1.63e-13`. The discrete mesh gate failed: requested
20/10/5 µm levels produced cell-extent widths 80/80/80 µm and depths 20/30/35
µm; the finest depth pair changed 14.29%. The supplementary contour mesh trend
is inconclusive. The time study is inconclusive because the first actual mean
step was 89.217 ns, followed by 50 and 25 ns, so the required constant
refinement ratio is absent. This remains numerical evidence, not experimental
validation.

The result field named `implementationHash` had included process/material
inputs, even though `inputHash` already records the request. A separate
`implementation_fingerprint()` now hashes the solver source tree and model
version only. CPU, CUDA-pilot and engineering-benchmark provenance use it;
`fingerprint(p, m)` remains the full cache/queue key, preserving input
separation. Python compilation, diff check, an input-separation assertion and
the two-input provenance regression pass. The combined cache/queue test passed
its hash assertions but could not create/open its SQLite database because
Windows denied access to the temporary directory (`WinError 5`). Commit only
the owned solver/test files, P4 report and continuation docs. Then investigate
the failed discrete resolution gate without changing its frozen thresholds;
keep the NIST observation operator and measured-profile gates closed. Current
physics audits have not demonstrated a production thermal equation defect, so
do not rewrite governing equations absent a reproducible physical/numerical
failure.

## Continuation checkpoint — layer-aligned mesh-study repair (2026-09-25)

The failed UI study was the 28 µm middle level (the requested 20 µm mesh was
the base; 40 µm was the coarse level). Its z-cell centers were 14 and 42 µm.
The whole-cell active mask correctly excluded the 42 µm center, but that cell
spanned 28–56 µm and the physical 40 µm layer surface cut through it. The
cell-integrated source therefore omitted the 28–40 µm part of the Gaussian
source and captured 54.8506%. The 99% guard and source normalization remain
unchanged; no partial-cell thermal capacity or conduction was invented.

The built-in standard powder-layer mesh study now runs the CPU-reference model
with a layer-conforming grid and three distinct integer cells-per-layer levels.
For the reproduced IN718 vector these are 1/2/3 cells per layer and 40/20/13.333
µm. The original backend request and executed backend are recorded separately;
an automatic backend request is explicitly executed as the CPU reference for
this numerical study. The exact 30 W, 1200 mm/s, 80 µm study completed all three
levels; energy relative error was 3.04e-16. Width, depth and volume trends were
inconclusive, so this is not convergence acceptance or experimental validation.

The convergence panel now discloses the layer-aligned CPU-reference protocol,
requested versus executed backend, and cells-per-layer sequence. The API type
also preserves the execution-input hash. Python regressions and TypeScript
typecheck passed. The focused TSX test still cannot start because esbuild
returns `spawn EPERM`; no browser verification was done. P4 review confirms the
latest conforming study is not a substitute for the frozen P4 gate. Next:
investigate tied peak-time selection as a diagnostic-only sensitivity, then
freeze any new numerical protocol before running it. Keep the 80 W frozen P4
status failed and the 75 W contour study inconclusive. P5 source/operator and
IN625 full-transient data gates also remain open.

## 2026-09-25 continuation — NIST observation-count gate

The official NIST workbook and catalog define six cross-sections per process
condition: three tracks, each sampled at 4.9 and 6.0 mm from its start. The
comparator's previous synthetic positive fixture supplied one x=5 mm midpoint
section while declaring `observationCount=6`; that schema could emit numerical
residuals without matching the source sampling plan. The Python comparator now
always withholds residuals until a versioned six-section operator backed by
three separate simulated tracks is implemented. Reports expose the required
positions and track count. Targeted regression: all 6 tests pass. This does not
validate the engine or change the unavailable P5 result. Do not launch another
NIST solve until the observation contract, source profile, and 10 mm model
validity/cost gates are resolved.

## 2026-09-25 continuation — live run bundle round-trip

Verified the current localhost UI against its existing source/run archive. The
server-local export contains 3 runs, 132 run artifacts, and 3 source links;
the UI verified the manifest and restored an isolated copy with restore ID
`2e251b3d73a7470ead671287649ace35` from bundle
`be741eebfa12413a8fd78978ecefdfc3`. The live archive still displayed its
original 3 records. Selecting the archived IN718 run then produced `unavailable`
because its Table 4 source revision 1 did not match reviewed local revision 2;
the old run was not rebound. This proves the current software archive path, not
scientific validity or experimental agreement. Next prioritize the CPU/P4 gate
and the versioned three-track/two-section proxy-campaign contract; preserve the
source-profile and 10 mm validity/cost gates.

The UI also selected official NIST optical-workbook revision 1 and rechecked
its archived bytes: publisher XLSX (25,811 bytes, SHA-256
`2cfaac96aaca3dabb77b7029f842cdcc7e75c5a2cf3577d0734823246364a931`) and
publisher checksum sidecar (64 bytes, SHA-256
`770c0826e53e42c242110e69c032f2cbc74f6183048c43a530c5b62e746ae09b`) matched.
The archive-document SHA is `73293ca6c2a1929a2e244f806d6eb5900d4c739716f7f291e74c9bc12dc291b6`.
The same view still marks the optical operator unimplemented, so these exact
source bytes are provenance evidence only.

## Continuation checkpoint — P8 archive acceptance and physics continuation (2026-09-25)

The goal remains active. User explicitly authorizes scientific fixes or a Python
engine rebuild when evidence shows the current result is inadequate. Do not
weaken acceptance gates or describe numerical/device parity as experimental
validation.

P7: `docs/IN625_P7_PROPERTY_EVIDENCE_MATRIX_2026-09-25.md` now maps chemistry,
lot/state, evidence type, range, uncertainty, gate status and missing evidence
for each required IN625 property. IN625 remains thermal-screening-only;
`fullTransient` and `buildJob` remain closed. Sources for powder and substrate
are distinct benchmark scopes; no cross-lot property splicing is admitted.

Physics audit: Phase 21's `TransientEnthalpyFDMSolver` is deliberately a
stationary 2D screening model: `speed_m_s` is ignored, beam radius/absorptivity
are fixed, and the 2D source has no out-of-plane power normalization. The
worker still exposes the named RPC, but the service method has no indexed UI
caller. Preserve its screening label and do not present it as a scan-resolved
melt pool. A future traveling-source solver would need its own model contract,
power normalization, conservation checks and validation scope. P4 tied-peak
endpoint selection is a plausible discrete-observable sensitivity (439/300/25
equal endpoints by mesh), not a proven cause of the frozen failed result.
P5 stays unavailable because the current model lacks matching melt flow,
evaporation mass transfer and mass/latent-energy closure.

Mesh-study failure diagnosis: a fresh UI "Three meshes" attempt stopped when
the middle 28 µm level captured only 54.851% of the Gaussian source, below the
unchanged 99% minimum. The guard is functioning as intended; this does not
justify renormalizing a truncated source or relaxing the threshold. The study
runner previously let one invalid level discard the requested fine solve and
the other levels. It now records that level as unavailable, preserves the
requested result and any other completed levels, and marks all partial-study
convergence checks failed. No convergence claim is made from an incomplete
sequence. Commit `4684213` contains the Python handling, UI rendering and
regression coverage. Focused study regressions, 15 heat-source tests (one
OpenFOAM skip), and `npm run lint` passed. The focused TSX UI test could not
start (`spawn EPERM`). Broader Windows Python verification encountered 7
access-denied temp-directory errors (2 OpenFOAM checks skipped), so the full
package is not yet verified.

Engine choice: the standard 3D CPU transient in `python/lpbf_simulation.py`
already follows piecewise-linear moving scan segments with a cell-integrated
Gaussian source, two-node time quadrature, adaptive explicit stepping and a
global energy ledger on a fixed material grid. It is the better canonical
thermal reference; do not rebuild it before its resolution/validation gaps are
measured. The separate `TransientEnthalpyFDMSolver` remains stationary 2D
screening and must not be represented as scan-resolved. A proposed factor-two
source-power defect was disproved: each GL2 time node contributes 0.5P, and
both together integrate to P per step; the existing axial power regression
passed. Spatial source renormalization remains explicitly bounded by the 99%
capture guard and is not experimental validation.

P8: the current source built with `npm run build`; Vite reported a large
Three.js chunk warning. The freshly built server and Python worker started
locally and `/api/health` returned `status: ok`. A fresh UI pass computed the
bounded IN625 bare-plate screening job on CPU and CUDA with matching revision
and material snapshot identity. Peak temperature matched at 300.226 K, final
enthalpy differed by `2.22e-16 J`, and the temperature-field maximum absolute
difference was `1.14e-13 K`. This is same-input numerical/device parity, not
experimental validation. The IN625 run was archived with exact local-derived
source revision SHA-256
`be3286b30b3ec3a6970b577cd9050b19de716cbf8754c7ac2355cf20d5cea655`; its run
contract remains legacy/unbound. A fresh IN718 transient job was also archived;
its 40/20/60 µm melt geometry remains under-resolved and unvalidated. The
IN625-vs-IN718 NIST Table 4 comparison correctly returned unavailable due to
the unmatched material/process contract. UI keyboard selection of the archived
run passed (ArrowUp/ArrowDown changed and restored the selection). Server-local
bundle `5c86ac62fed64f9b93c9a53b8d6817a9` was created with 3 runs, 132 run
artifacts, and 3 source links; verification passed and isolated restore
`58d94b80d0904a53bb11f5bab73eac51` completed while the live archive remained
unchanged. This is software workflow/integrity evidence only.

The NIST local Table 4 transcription was refreshed from source version 1.0.0
(archived revision 1; 3,374 bytes; document SHA-256
`b312cc286ccf7cd41c2ff8bc2bea3c0cf183af432125f402dfbebdf71b235ee0`) to
catalog version 1.1.0 (archived revision 2; 4,321 bytes; SHA-256
`6c9d9f80f8c4eb2b7a6c18bbaab9ed7a993e43f155190dfff49808a4f854aaf0`). The
import verified bytes and added source-located heat-treatment context. Earlier
IN718 run `aad3bc4b6ceb4abbbc56942554f202cb` remains immutably linked to rev 1;
the comparator correctly rejected its outdated fixed artifact. NIST case 0
also differs from that run's process vector, and the strict model gate needs a
verified measured AMB2022-03 beam profile that the source hunt has not found.
No run was silently rebound; new source provenance alone does not qualify the
model.

Next: resolve why the coarse UI mesh represents too little source while keeping
the 99% guard fixed; rerun the three-level study and inspect its per-level
status. Then quantify mesh/time error for the existing moving-source solver,
continue P4 tied-peak diagnosis without changing its frozen protocol, increase
resolution where melt dimensions span only 1–2 cells, and locate the exact
measured AMB2022-03 beam-profile artifact before a source-matched comparison.
Retain P7 full-transient/build-job and P5 gates as closed until evidence passes
admission. Preserve user-owned changes and stage only owned files.

## Continuation checkpoint — layer-conforming P4 v2 result (2026-09-24)

The third, separately frozen one-layer 80 W IN718 companion used the opt-in
`layer-conforming` grid and its distinct model ID. Protocol/scenario were
committed before execution in `e439a56`; the scenario SHA-256 is
`80c3d4e1c58e28559914ff3a02fc6edc762b8ffe21336466f60b2826fe388ecc`. All six
CPU runs completed and passed the existing source guard and energy closure
(maximum relative error `1.286e-13`). Actual mesh spacing was 26.6667, 13.3333,
and 6.6667 µm (factor two); actual mean timestep levels were 99.982, 49.991,
and 24.996 ns (factor two). Mesh assessment is `inconclusive`: discrete
width/depth are identical on the finest pair and the three-level oracle
reports unresolved/identical discrete geometry. Timestep assessment is also
`inconclusive`: all levels report identical discrete width/depth. The report
is `docs/LPBF_P4_LAYER_CONFORMING_V2_80W_2026-09-24.json` (SHA-256
`873ea698d00d7deb5db06ad241028b42161ea24e9d6385d3f6953164e270c4ec`). It is
CPU numerical evidence only, not experimental validation, and does not change
the original frozen P4 or either prior companion outcome.

Next: preserve all three companion outcomes, then continue the remaining P0–P10
work. Investigate the discrete-melt geometry plateau as a model/observable
limitation without changing frozen acceptance or retuning this campaign. P5
remains unavailable; GPU qualification/performance and alloy admission remain
open. Do not claim scientific validation from energy closure or contour proxies.

## Continuation checkpoint — factor-two P4 companion (2026-09-24)

The second separately frozen layer-conforming campaign is committed as
`9594ea4` and its six-run report as `docs/LPBF_P4_LAYER_CONFORMING_FACTOR_TWO_80W_2026-09-24.json`
(SHA-256 `563a449fb3ad7069706941104efccb8a624089ab1fa1fcf35a59acd8e807097d`).
All runs completed with the unchanged 99% source-capture guard. Energy closure
passed (maximum relative error `1.281e-13`). Mesh trend failed: the first two
cell-extent W/D pairs are identical and the finest pair changes 33.33% in width
and 20.0% in depth. Timestep trend is inconclusive because all three accepted
time levels report identical cell-extent W/D. The frozen original P4 remains
`failed`; both companion reports remain distinct numerical outcomes. The safe
next P10 action is to determine whether a physically consistent cut-cell/source
fix can preserve the z=0 interface; do not shift the grid origin or weaken any
source/convergence criterion. Continue the other P0–P10 lanes independently.

## Continuation checkpoint — layer-conforming P4 v1 (2026-09-24)

The unsafe substrate-depth shift proposed during diagnosis was rejected: it
would move the z=0 material interface and misclassify whole cells. A separate
one-layer, layer-conforming companion protocol was frozen before running in
`067eea6` (`docs/LPBF_P4_LAYER_CONFORMING_PROTOCOL_2026-09-24.md` and its
scenario JSON). All six runs completed under the unchanged 99% source-capture
guard and 1% energy criterion. Energy closure passed (maximum relative error
`3.07e-14`), but v1 is `failed` for mesh convergence and `inconclusive` for
timestep convergence: the actual mesh ratios are 2 and 1.5, and actual mean-dt
ratios are not constant. The solver's existing trend oracle therefore returns
inconclusive; no acceptance criterion changed. Results are preserved in
`docs/LPBF_P4_LAYER_CONFORMING_80W_2026-09-24.json` (SHA-256
`2c74226dace13c93290e8086f3e1e57dc526f2967dcf4454f9416011c5598b51`). The
original frozen P4 remains `failed`. Next, if another companion is justified,
predeclare exact factor-two, surface-conforming actual meshes and timesteps;
do not reuse these v1 results to claim a pass.

## Continuation checkpoint — P4 forensic boundary + NIST beam correction (2026-09-24)

NIST's 2025 beam report includes a normalized measured signal-intensity
profile and central x/y sections in Fig. 7, plus measured caustic points and a
`Dg(z)` fit in Fig. 8; Fig. 5 is simulated. The public sources reviewed so far
do not expose the raw numeric 2D camera array or a scan-specific source-byte
binding. A digitized plot would be derived data with its own uncertainty, not
the original measured field. `Dg`/`D4σ` equality remains an explicit ideal-
Gaussian assumption. The active plan has been corrected; P5 remains
`unavailable`.

P4 remains frozen `failed`: width trend inconclusive, depth finest-pair change
17.1875%, timestep geometry inconclusive. Its report stores aggregate rows, not
the original runs' full thermal history or field series. A replay at diagnostic
commit `5dae4c9` matched all six stored input hashes and exactly reproduced
each row's actual spacing, steps, W/D, peak temperature and energy error. Its
`implementationHash` did not match, so this remains a matched-input forensic
diagnostic, not an exact-code replay. Equal-maximum endpoints ranged from 439
and 300 on the two coarser meshes to 25 on the fine mesh; this is a plausible
selection sensitivity, not a proven cause of non-monotonic depth. Details:
`docs/LPBF_P4_PEAK_DIAGNOSTIC_REPLAY_2026-09-24.md`. Separately, today's solver
rejects the 86.763%-capture coarse mesh under its newer 99% minimum; do not
weaken that guard or the P4 criteria. A Git-blob scan of 69 commits from the
P4 harness through the new capture gate found no matching original
`implementationHash`; the historical tree was likely dirty or outside the
recorded Git ancestry and cannot be recovered from the report hash alone. The
comparison confirms that the numerical operator files stayed unchanged from
the frozen-report commit to the diagnostic commit; only additive tie counters,
their serialization and one explanatory label differed. This supports using
the plateau counts as same-operator diagnostics, not as byte-identical
historical execution. The completed 75 W vectors are exhausted and cannot be
reused as prospective levels.

P8's strongest recorded live UI evidence is the IN625 flow in `PROOF.md` §
“Core physics + IN625 UI/archive integration”: source revision 2
preview/import/byte verification; explicit CPU/CUDA calculation and UI
comparison; exact-source run archive; bundle verification; and isolated restore
with the live archive unchanged. This supports software flow only. That run is
`legacy-unbound`, IN625 remains unvalidated screening, and NIST comparison is
unavailable. Older references below to the IN718 `e8e…` run and bundle are
historical, not the latest flow.

The broad P0–P10 goal stays active. Preserve user-owned `docs/README.md`,
`sonkayıtlar/LOG.md`, `docs/SCIENTIFIC_RESEARCH_VISION.md`, and
`.tmp-phase22-review-cache/`; stage only explicitly owned checkpoint files.

## Latest checkpoint — IN625 mushy-range CUDA witness (2026-09-24)

User explicitly widened this goal to include evidenced physics defects in the
core engines. The previously committed Phase 22 work metric-projects Marangoni
surface gradients and points recoil inward along the height-graph normal.
Follow-up: a second audit found that Marangoni shear used vertical
`dz` instead of the normal spacing `dz/sqrt(1+h_x²+h_y²)`; the code and
regression test are updated, and the full Phase 22 Python suite passed **29/29**
with CPU and actual RTX 4060 `cuda:0` test coverage. The alloy capability
matrix is recorded at
`docs/LPBF_ALLOY_CAPABILITY_MATRIX_2026-09-24.md`.

New P6 witness: `python/test_in625_bareplate_field.py` exercises the bounded
IN625 enthalpy solver from a synthetic 1500 K initial state through the mushy
interval at two resolutions. The 128- and 1,024-cell CPU/CUDA pairs match to
max 9.10e-13 K and 3.50e-10 J/kg; each energy residual is 5.33e-15 J. CUDA
times are 9.196 s and 23.254 s versus CPU 0.289 s and 1.316 s, with incremental
memory 24,576 and 176,128 B. This is model-law numerical evidence, not process
validation or a GPU speedup.

Focused evidence: Phase 22 Python 29/29 plus CPU/CUDA field/multistep/pressure
groups 5/5; IN625 binary/client tests 6/6; source/API groups 10/10 and 16/16;
run preview round-trip 2/2; TypeScript, lint, and diff checks passed. Live UI
used 1,152 cells × 11 steps on CPU and explicit RTX 4060 `cuda:0`: maximum
field difference 0 K, RMS 0 K, and zero scalar/energy-ledger differences.
IN625 remains unvalidated literature-model screening; its run has a legacy
unbound core contract, and no experimental comparison is admitted.

Next: use the completed P4/P5/P6/P7 audits to scope physics/data work; keep
frozen P4 `failed` and P5 `unavailable`. P6's two tests show the current
PyTorch CUDA path is slower at both tested sizes, so profile/refactor only if a
larger same-physics workload can justify it. Archive and evaluate the nearest
Hastelloy X sources before any runtime alloy admission. P6/P7 remain partial.
No goal-completion claim yet. The Marangoni package is committed as `fbe47df`.
Preserve user-owned `docs/README.md`,
`sonkayıtlar/LOG.md`, and `docs/SCIENTIFIC_RESEARCH_VISION.md` edits; do not
stage them.

## Acceptance audit results (2026-09-24)

- P4: frozen 80 W thresholds remain ≥3 levels per axis, ≤1% energy error,
  ≤5% finest-pair W and D change, and converging trend from actual spacings.
  The frozen report is `failed`; its 5 µm extension is not a replacement.
  The separate preregistered 75 W contour run is `inconclusive` (mesh depth and
  both time metrics). Do not start another P4 run until a new protocol is
  committed with distinct model/process scope and actual-resolution rules.
- P5: `enthalpy-fv-6` stopped at its fixed-material boiling limit after 133
  steps (0.1024% of Case 0); it lacks melt flow, evaporation mass transfer,
  free-surface topology and matching mass/latent-energy closure. Preserve
  `unavailable`; do not remove the guard or repeat the same case. A new model
  revision requires closed mass/energy/force checks and measured IN718/beam
  inputs before a separate 3×3 plus optical-operator campaign.
- P6: the new 1500 K synthetic IN625 witness now exercises the mushy enthalpy
  range with CPU/CUDA field, independent enthalpy and global energy parity.
  The tiny CUDA case is ~32× slower than CPU; scale/performance qualification
  remains open and this does not qualify the alloy source.
- P7: no alternate alloy source package currently clears the gate. Hastelloy X
  is the nearest research candidate: an LPBF paper provides as-deposited Cp /
  enthalpy and solid-state diffusivity data, but liquid conductivity in its
  released model is a 15× approximation, so it is not admitted. CoCrMo sources
  do not demonstrate a matched chemistry/state or complete phase-change set.
  Keep IN625 bounded screening only until matched, uncertainty-bounded inputs
  are archived.

Immediate next work: decide a separately bounded P4 numeric campaign only
after a new frozen protocol; for P5 define a physically closed free-surface
model before implementing it; for P6 test a larger same-physics IN625 case and
report crossover honestly; for P7 archive and evaluate the Hastelloy X source
curves before any runtime alloy admission.

## Latest P6/P7 integration checkpoint — 2026-09-24

Implemented a model-specific IN625 bare-substrate conduction field path with
matching NumPy and explicit CUDA evaluators. Root owns final integration and
proof. Scope is limited to the literature-model enthalpy interval, explicit
absorbed-W source, fixed supplier density assumption, and adiabatic domain;
powder-bed/full transient and experimental qualification remain unavailable.
The focused CUDA parity and energy results are in
`docs/IN625_BAREPLATE_GPU_SCREENING_2026-09-24.md`. The shared source-capture
threshold now lives in `lpbf_heat_source.py` and is imported by the existing
reference solver. No agent is currently writing. Next: inspect/commit the
isolated solver and run the aggregate project gates without staging user docs.

Latest active slice (2026-09-24): P1 now emits a composite build-job identity
over canonical alloy, model, solver revision, and property snapshot schema/
revision/content hash; the separate property-only hash remains stable in meaning.
The full identity participates in cache keys and successful TypeScript results
are rejected when identity fields are missing or inconsistent. An independent
IN625 enthalpy quadrature oracle passes, but the model remains unvalidated and
build-job/full-transient admission stays closed.

P10 found a high-confidence OpenFOAM closure defect: evaporation energy and
recoil/plume sources had no corresponding VOF/continuity mass transfer. The
generated multiphysics case and implicit C++ default now disable those sources;
the explicit recoil-formula fixture remains enabled and is labeled as formula-
only evidence. Diagnostics report absent mass-transfer closure. This does not
implement a fully coupled evaporating VOF model. Focused validation: build-job
identity script PASS, IN625/OpenFOAM gate 7/7, TypeScript session 12/12,
`npm run lint` PASS, Python syntax check PASS; OpenFOAM compile not run. A GPU
feasibility audit is active because P6/P7 now require a qualifying GPU thermal
path for at least one newly admitted alloy. P4/P5/P6 remain open.

Root owns report integration and the next GPU feasibility/integration gates;
preserve frozen acceptance criteria and current user edits in `docs/README.md`,
`sonkayıtlar/LOG.md`, and `docs/SCIENTIFIC_RESEARCH_VISION.md`.
P5 Case 0's 480 µm run stopped at the fixed-material boiling guard after 133
steps (0.1024% of scan). CPU enthalpy-FV lacks evaporation/free-surface/momentum;
Phase 22 height-graph terms are heuristic and OpenFOAM defaults are not IN718-
qualified. Do not remove the guard or rerun the same model. Require a new model
revision with manufactured mass/energy/force checks before a new 3×3 P5 protocol.

Root owns integration and `STATUS.md`/`PROOF.md` on
`codex/lpbf-buildjob-material-identity`; no push. The official NIST workbook
audit is `ef303e7`. Phase 21 stationary 2D screening physics repairs are
`69fae9a` and `bf34aef` (6 focused Python tests PASS); P10 was added to the
active plan in `04e0ea4`. Commit `13d1f05` fixes the OpenFOAM two-phase
thermal-advection flux: metal apparent heat capacity and gas heat capacity now
follow their own `alphaPhi` phase-volume fluxes instead of applying a
volume-weighted `cp` to mixture `rhoPhi`. The focused static-source/numerical
oracle passes 2 tests; it is not OpenFOAM runtime evidence. WSL
`E_ACCESSDENIED` prevented local solver compile/integration. Commits `e8f8313`
and `c902700` fix the build-job field-peak/cache identity and Phase 22 face
transport/projection contracts.
New P6 smoke artifact: `python/test_lpbf_phase22_multistep_cuda_parity.py` and
`docs/PHASE22_CPU_CUDA_MULTISTEP_SMOKE_2026-09-24.md`. The five-step production
`solve_toolpath` case passed on CPU and explicit RTX 4060 `cuda:0`; root rerun
passed 1/1 using a workspace-local Warp cache. It records converged pressure
projections and close scalar parity, but no full-field parity, energy closure,
performance, mesh/time convergence, or experiment qualification. Max absolute
post-projection divergence differs (0.078125 vs 0.15625 s^-1) and remains
reported. Warp's system PCH temp cleanup emitted WinError 5 after exit code 0.
The follow-on full-field diagnostic is in `python/test_lpbf_phase22_full_field_cuda_parity.py` and
`docs/PHASE22_FULL_FIELD_CPU_CUDA_PARITY_2026-09-24.md`: all final T/H/U/V/W/P/surface arrays
passed the frozen CPU/explicit-`cuda:0` tolerances for the same small case (3/3
focused PASS); opt-in output is capped at 100,000 cells and defaults remain
unchanged. No auditable energy ledger is exposed, so energy closure remains
unavailable and P6 remains partial.
The CUDA PCG also passed one independent manufactured-pressure oracle on a
9³ liquid grid (linear residual `7.4851e-4`, gauge-adjusted pressure error
`2.9145e-4`, independent operator residual `7.4854e-4`, each within `1e-3`);
see `docs/PHASE22_CUDA_PRESSURE_MANUFACTURED_2026-09-24.md`. This does not close
the energy-ledger requirement or validate surface-force laws.
The Phase 22 CPU Warp + peak consistency + material capability suite passes 19
tests; standalone build-job checks and TypeScript typecheck also pass. The
TypeScript session behavior runner passed 11 focused tests in the elevated
runner after the sandbox attempt failed with `spawn EPERM`. PyTorch CUDA is
available on this host, though the explicit Phase 22 Warp tests still ran on
CPU and do not establish CUDA execution for that solver. The pressure stencil
pairs
the face divergence, gradient, and Jacobi operator, but its fixed ten sweeps
do not meet the 1e-3 relative divergence target on smooth manufactured fields
(residual ratios 0.420619 at 9^3 and 0.793338 at 17^3); 300 sweeps still leave
0.0378842 at 17^3. The fixed Jacobi solve was replaced by matrix-free,
device-reduction preconditioned conjugate gradient on the unchanged face-based
operator. CPU Warp manufactured-field tests meet the 1e-3 measured linear and
post-projection divergence gates at 9^3 (15 iterations) and 17^3 (35
iterations), and exercise zero/nonzero Neumann compatibility, disconnected
components, exhaustion, and numerical failure. CUDA execution/performance for
Phase 22 remains unverified on this host.
Commit `11334ff` records this pressure-solver repair. Commit `96eeca2` fixes
integer array conduction silently truncating fractional face fluxes; its
focused suite passes 6 tests. CUDA pilot parity tests now pass for IN718 and
316L on `cuda:0`; 316L uses the existing `estimated-legacy` snapshot and this
is numerical parity only, not source-backed alloy qualification. IN625 still
lacks a complete source-backed transient property/optical/flow input set.
IN625 P7 remains partial: the 273.15–1623.15 K route is explicitly
unvalidated literature-model screening; source validity span and material /
process state are not established.
The NIST 2019 IN625 powder conductivity source is inverse-derived for powder
only (100–500 °C), has no matched AMB2018-02 lot, and cannot be routed into the
current no-powder-state GPU material path. NIST's AMB2018-02 plate certificate
is the next identity source to inspect; it does not itself provide property
curves. Do not elevate P7 without matched properties and validity/uncertainty.
CPU transient whole-cell surface geometry remains a documented cut-cell
limitation, not a repaired defect. The separate
preregistered 75 W 3+3 contour report is `4110e73`, SHA-256
`b9cff92e01378a58ac4ed17333c21ad591a956dfc6e32ddd2dda8a219026b866`.
All six solves completed with energy PASS, contour mesh width PASS, contour
mesh depth and both time metrics inconclusive; total 75 W contour/discrete
status is inconclusive. The frozen 80 W P4 result remains failed. P5 remains
unavailable. The preregistered peak-selection diagnostic repeat is complete in
`docs/LPBF_P4_PEAK_SELECTION_DIAGNOSTIC_75W_2026-09-24.json`, SHA-256
`bb7241cd328842517b8a0ad232c1cf160f0238ec459bbf66967ccc464b0ae4e`; it remains
inconclusive with unchanged criteria. Peak ties shrink from 416 endpoints at
20 µm to 11 at 10 µm and 1 at 5 µm; the 10 µm timestep refinement shifts the
selected endpoint by about 0.1 µs while W/D changes remain below 0.004% and
non-monotonic. Peak selection is a plausible contributor to mesh-depth
non-monotonicity, not a proven cause. The global cell-center contour remains a
numerical proxy without surface extrapolation or NIST section equivalence.
The versioned section operator is now committed as `7e5437e`; it emits separate
4.9/6.0 mm thermal-proxy records for one simulated line, with no extrapolation.
Next: measure corridor-width sensitivity, then plan an affordable independent
3+3 with three separately identified simulated/experimental lines. NIST's 2025
beam report provides a measured nominal 67 µm Gaussian `Dg` diameter with 5.2%
combined standard uncertainty and a plotted measured normalized profile with
central x/y sections (Fig. 7); Fig. 5 is simulated. The reviewed public sources
do not expose a raw numeric 2D irradiance array or scan-specific source-byte
binding. Keep P5 unavailable until measurement/proxy provenance, explicit
`Dg`/D4σ-to-model mapping and uncertainty, line identities, and the optical
section operator are present.
The original 3 mm track bound rejected the NIST 10 mm baseline; the square
domain estimates were 4.18M/32.32M/258.27M cells at 20/10/5 µm. The rectangular
corridor reduces this to 205,200/1,556,975/12,123,933 estimated cells, still
exceeding the 600,000-cell guard at 10/5 µm. No 10 mm solve ran. Preserve the
67 µm measured-diameter, ideal-Gaussian approximation as a separate exploratory
condition from the full-profile gate. Phase 22 recoil/interface kinematics are now coupled by
post-projection height-graph motion (`3ff4c9e`; Warp CPU 24/24), but CUDA
execution, interface breakup/reformation, and plume dynamics remain unverified
or out of scope. Preserve the P7 source-data gate.
Root alone changes checkpoint documents.

User widened the active goal to repair evidenced physics defects in the core
engines as well as the planned alloy/GPU/data work. Completed packages on this
continuation: `39a6f8f` fixes sloped-interface Marangoni temperature sampling;
`52b51cb` matches evaporative energy and height loss to the same interface
area; `ee730ec` rejects severe Gaussian source truncation in the CPU reference;
`46b9be6` applies the same capture gate to CPU and explicit CUDA pilot;
`9325765` separates optional claimed source-validity bounds from generated
material-table coverage. The enthalpy/phase audit found no evidenced defect.
Root owns integration and checkpoint docs; external user changes remain
unowned.

Latest bounded CPU benchmark: the 1 mm, 20 µm bare-plate corridor completed
4,267 steps across 25,200 cells in 24.47 s with relative energy error
`6.53e-14`. The full Phase 22 `solve_toolpath` path then ran a deterministic
one-step case on both CPU and actual RTX 4060 `cuda:0`; both pressure solves
converged in seven PCG iterations. Maximum-temperature difference was
0.000244 K and maximum-velocity difference was 1.69e-8 m/s, with identical melt
volume and keyhole depth. This verifies a tiny coupled-device smoke, not full
workload parity or performance. The 10 mm bare-plate CPU attempt stopped at the
documented boiling-validity boundary before completing a scan; see
`docs/p5_case0_10mm_480um_validity_stop.json`.

`corridor_sensitivity_feasibility` completed a preregistered three-width
feasibility audit (`a065b77`); all estimated CPU runs exceeded the reference
worker's 300 s timeout, so no solve was initially launched. Root then tried the
480 µm case directly on the local CPU reference solver. It stopped after 133
source-step evaluations at the documented boiling-validity boundary because
the fixed-material solver has no evaporation/free-surface model. See
`docs/p5_case0_10mm_480um_validity_stop.json`. No section or comparison result
was emitted. The ideal-Gaussian input and absent experimental line identities
still prevent P5 qualification.

A separate primary-source audit of IN625 is recorded in
`docs/IN625_P7_SOURCE_GATE_2026-09-24.md`. It found no matched full-range table
that can pass P7 without unsupported material-state transfer or extrapolation;
the current screening capability and full-transient/GPU gate are unchanged.

P4 frozen 80 W IN718 3-mesh/3-timestep report is
`docs/LPBF_CPU_CONVERGENCE_80W_2026-09-24.json`: all six completed, energy
PASS, mesh width inconclusive, mesh depth FAILED at 17.1875% finest-pair change,
timestep geometry inconclusive, overall `failed`. No experimental validation.
Roundoff-only width trend was repaired in `92a0e59`. P5 exact-source NIST Table 4
comparison is correctly `unavailable`, errors null, with seven genuine missing
conditions after the JSON-number fix `3f152d1`.
The surface-aligned 80 W 3+3 diagnostic still failed P4: W/D mesh
40/40 → 40/40 → 60/50 µm, finest width/depth changes 33.33%/20%, energy PASS,
time geometry inconclusive. Source capture exceeded 0.999999999.
An exploratory 5 µm, 588,544-cell solve (`2a5493a`) completed in 375 s: discrete W/D
60/55 µm, 10→5 µm depth change 9.09%, still over the frozen 5% limit.
Supplementary liquidus-contour W/D 20→10→5 µm is monotonic with 1.27%/3.70%
finest changes, but lacks a predeclared independent 3+3 gate; P4 stays failed.
The official NIST workbook/sidecar SHA is verified; all 42 BP1 source rows
reproduce the seven local Table 4 aggregate rows at 0.1 µm. The new workbook
source is a distinct dataset; the existing transcription and run link persist.

Earlier P8 browser flow: local Table 4 revision 1 imported/verified; IN718 30 W
powder-layer short pilot archived as run `e8e26ffea4784e6288f7ddab5839de01`;
bundle `46c140da2e984c0ba00468eec09bdaf6` exported/verified and restored as
isolated copy `1ac0729abd5a47928c80f2ed8bfe71ec`. The run is intentionally
not NIST condition-matched. Newer IN625 archive/bundle flow is recorded in
`PROOF.md` and summarized above. P9 checks: Python 91 PASS/3 Windows OpenFOAM skips;
Ubuntu/OpenFOAM engineering 29 PASS; latest TypeScript unit 232 PASS, lint and
build PASS; new Python source audit 3 PASS. Browser tab 2 and local dev server
session 29665 are live. Official workbook source preview/import/revision-1
verify passed in the browser. The separate continuous-geometry protocol and
independent process/time study are now reported at the top of this file; scope
a matched NIST optical operator for P5 only after its physical inputs are known.

External `docs/README.md`, `sonkayıtlar/LOG.md`, and
`docs/SCIENTIFIC_RESEARCH_VISION.md` remain unowned. Preserve them.

# Previous LPBF handoff — 2026-09-23

Latest 2026-09-23 handoff: root committed the explicit GPU queue pilot
(`98c33aa`) and NIST optical Table 4 local-transcription archive (`34bd387`).
`cpu_convergence` now owns only the separate GPU pilot client types, UI, and
focused tests; standard simulation parsing remains separate. `property_snapshot`
has completed the Python NIST comparison gate (`dffa0e5`) and now owns its
server run/source API service, route, and focused tests. `run_contract_ui` now
owns only new Python model-capability audit files and narrow matrix corrections.
Root owns integration,
`STATUS.md`, this file, and commits. All three agents share the checkout and must
preserve external changes. The optical source package is complete; its former
owner has handed off. P4 real 60 W IN718 [45,30,20] µm / [4e-7,2e-7,1e-7] s
pilot remains inconclusive: energy passes, coarse mesh has no melt, and time-axis
W/D is identical at the cell-level operator. No experimental-validation claim.

Latest ownership update: root integrated CPU convergence (`94ddf92`), IN625
bounded solid data (`76d5506`), NIST bare-plate UI gate (`246904c`) and Table 4
uncertainty (`3376300`), CUDA single-track pilot (`37a56cd`), exact-source run
service (`b3292ee`), build-job effective snapshot (`887e398`), and source
selection UI (`0daa456`). Root owns `STATUS.md`, this coordination file, the
execution plan and integration. Bundle API (`258032f`) and bare-plate CPU pilot
(`f4e5ba0`) are committed. `property_snapshot` now owns
`python/lpbf_material_registry.py`, `python/in625_thermal_material.py`,
`docs/LPBF_ALLOY_CAPABILITY_MATRIX_2026-09-23.md`, and a new focused Python
test for bounded IN625 thermal data. `cpu_convergence` owns
`python/lpbf_gpu_thermal.py`, `python/lpbf_simulation.py`,
`python/lpbf_worker.py`, optionally `server/lpbfWorkerBridge.ts` and
`routes/lpbfSimulation.ts`, and focused tests for a separate GPU queue pilot.
Bundle UI (`2c5b78f`) is committed. `run_contract_ui` now owns
`server/lpbfSourceCatalog.ts`, a new
`data/benchmark/nist-amb2022-03-optical/` transcription, and focused source
catalog tests; it may update `src/data/meltPoolLiteratureCases.ts` and its
focused test only to share the data source. Root stages/commits each package
only after handoff and verification.
External dirty documents remain unowned.

User authorized continuous LPBF core/database work including GPU thermal parity
and data-gated alloy expansion. Starting branch `codex/lpbf-buildjob-material-identity`
at `a35499d`. The existing changes in `docs/README.md`,
`sonkayıtlar/LOG.md`, and new `docs/SCIENTIFIC_RESEARCH_VISION.md` are external
and remain unowned. All agents preserve them and root alone stages/commits.

# Current owner — 01a0c399-42df-72b0-9872-1010354f2d9a, 2026-09-21

Continues LOCAL b8b1f7f after source01a0c383 stopped writing. Owns
server/lpbfRunBundle.ts, tests/lpbf-run-bundle.test.ts, its narrow plan and
checkpoint docs/parent STATUS.md. First acceptance: full immutable run + source
snapshot/bytes, exact historical links, exclusive destination, completion last,
isolated verified restore. Existing source-only bundle preserved. No agents,
live migration, push or installs. All eleven external dirty paths remain unowned.
Phase0 OPEN; continue API/UI and shared physics after this package.
Bundle complete d7dc7e4. Now also owns server/lpbfArchivePaths.ts,
server/lpbfRunArchiveService.ts, routes/lpbfRuns.ts, narrow bridge/worker/server
integration, focused API/path/capture tests and .gitignore. No external paths
adopted. The 2026-09-21 API plan is retained at `docs/archive/2026-09-21/2026-09-21-lpbf-run-api.md`; current acceptance is governed by this file and `STATUS.md`.

# Previous owner — 01a0c36f-7006-7eb3-992d-73265a0a354d, 2026-09-21

Continues clean application HEAD2ce1abc in the same LOCAL checkout. Predecessor
stopped writes after dispatch. Owns bounded current LPBF engine/core evidence map,
representative melting CPU resource profile, shared-core contracts/implementation
subplan, and checkpoint documents/parent STATUS.md. Preserve model identities and
frozen numerical acceptance thresholds. Phase0 remains OPEN. No installation,
push, live migration or secondary-module work. Graph generation18Sep is stale;
task-directed coverage and direct source fallback are required.

Completed baseline/planning commit b9567c6. Now owns and completes
python/lpbf_core_contract.py, test_lpbf_core_contract.py, lpbf_simulation.py,
lpbf_evidence.py, src/services/lpbfSimulationService.ts and lpbf-contract.test.ts.
New results carry v1 input/material/model/backend identity; legacy absence remains
legacy. Python8PASS, current WSL core+engineering/source/peak/overlap54PASS no
skips, real result client parse and all64prechange artifact hashes identical.
Initial full167unitPASS. Subsequently OTHER writer changed
docs/SECONDARY_MODULE_BACKLOG.md, src/components/uqLabData.ts,
src/services/pythonComputationService.ts, src/utils/monteCarloEngine.ts.
These four paths are NOT ours; preserved/unstaged. Latest full suite147PASS/3FAIL:
uq-coupon-csv, uq-empirical, uq-presentation crash on the new UQ import-time throw.
Final lint/strict targeted TS/build PASS; focused parser6PASS. Do not describe
the shared tree as clean/full-green. No owned server/process remains.
Next bounded package: durable simulation-run records bound to exact source
revisions; inspect existing repository/worker snapshots and design its own plan.
Source stops writing after successor dispatch; successor claims its real task ID.

# Previous owner — 01a0c35a-2c97-7352-8d90-87ae9e0403b3, 2026-09-21

Packages complete:661153a source UI; b0bd0bd HDF5 metadata review. Fresh WSL
engineering26PASS including OpenFOAM; doctor records missing dependencies, no
Torch GPU proof. Newest audit/CURRENT CONTINUATION define remaining Phase0 scope.
Source stops writing after successor dispatch; successor claims its own real ID.

Continues clean 77fb27f in the same LOCAL checkout; predecessor stopped writes.
Owns source archive UI/service/tests, LpbfEngineeringWorkspace integration and
checkpoint documents. Acceptance: source conditions/unknowns, hash-bound preview
and import, revision-bound fresh integrity, visible failures, stale-response
protection and actual browser/keyboard checks. Preserve activeSpecimen inputs.
Phase0 OPEN; shared LPBF core/database remains the overall objective.
CBM generation18Sep stale/untracked in scope; exact source fallback used.
UI package661153a complete;166unit/lint/strictTS/build and actual browser checks
passed. Test server42236 stopped. Next owns python/nist_hdf5_review.py, its tests,
IN718 source-context metadata, catalog provenance guard and review/checkpoint docs.
System Python3.12.10 has h5py3.16.0/NumPy2.5.3; use only metadata inspection here,
not solver verification. No dependency installation needed. Raw Model string has
unbalanced parentheses; no inferred correction or temperature conversion allowed.

# Previous owner — 01a0c349-747d-7e52-bbf7-8e87df3211f7, 2026-09-21

Continues shared LOCAL checkout from clean cda8c12; source01a0c339 stopped writes.
Owns server/lpbfArtifactStore.ts, server/lpbfSourceImport.ts, related focused tests,
repository integration and checkpoint documents/parent STATUS.md. First acceptance:
streaming hash/size verification, contained regular files, exclusive immutable
publication, owned staging cleanup, all bytes verified before metadata publication,
and bytes+metadata backup/restore. Preserve unreviewed scientific evidence. Phase0
OPEN; no live migration or secondary modules. CBM18Sep lacks these files; direct
source fallback. Plan: artifact store → import → bundle → actual IN718 pilot.

Storage package complete:14 new regressions/full156unitPASS, strict TS PASS.
Actual IN718 three files550398609bytes imported/backed up/restored; portable report
`.runtime/lpbf-source-archive-portable-01a0c349/report.json`. SHA identity unchanged,
null measurement conversion preserved. Bundle snapshots no longer create WAL/SHM;
sidecar-bearing bundles rejected. Docs LPBF_SOURCE_ARCHIVE/PROOF record limits.
Next package: a bounded source archive API and UI integration, then HDF5 review and
shared-core gates. Source archive is not a complete simulation/experiment backup.
Storage commit ca3fb07 clean. API package owns server/lpbfSourceCatalog.ts,
server/lpbfSourceArchiveService.ts, routes/lpbfSources.ts, server.ts, .gitignore
and tests/lpbf-source-api.test.ts. Approved local catalog only; no client paths,
URLs or source metadata accepted. Preview binds document hash and expected revision;
import revalidates all bytes. Fresh integrity checks remain separate from science.
API package complete:5new tests/full161unitPASS, lint/strict API TS/build PASS.
Actual production server3195+IPC5195 smoke imported3IN718 files, verified current
bytes, retained null conversion and rejected stale revision409. Owned server40016
and descendants41112/30868/console hosts stopped; both ports have no listeners.
Evidence `.runtime/phase0-audit/source-api-smoke-01a0c349.json`. No UI changes yet.
Next owner should add source archive panel to LpbfEngineeringWorkspace comparison
stage with current-input-bound async state; do not turn raw signal into measurements.
Source01a0c349 stops writing after successor dispatch; no overlapping work assumed.

# Previous owner — 01a0c339-7e60-7573-b548-4fd5e6cbef44, 2026-09-21

Continuation started from clean application HEAD affdaec. Source01a0c326 stops
writing after dispatch. First package owns python/lpbf_worker.py,
python/test_lpbf_thermal_materials.py and checkpoint documents/parent STATUS.md.
Acceptance: thermal-accumulation uses four_alloy_materials, resolves aliases,
rejects unknown/missing identity instead of silently calculating Ti64, and keeps
the screening equations unchanged. Verify real JSON-lines worker requests and
CPU engineering/Phase17 tests. No secondary-module work, push or installation.
Graph generation18Sep is stale; exact source fallback applies. Phase0 OPEN.
Also owns the thermal service's required material type. Package verified:
RPC3, engineering25+1skip, Phase17 5, optional1, unit133 and lint PASS.
Next owns tests/lpbf-sqlite-compatibility.test.ts and SQLite ADR/provenance notes.
Material repair committed2a118ee. SQLite trial3 and full unit136PASS; source-context
metadata and low-power profile recorded. Also owns PROOF.md. Next scope is isolated
versioned metadata repository and its tests; no live legacy data migration yet.
Exact next paths: server/lpbfSourceRepository.ts, tests/lpbf-source-repository.test.ts.
Contract: immutable source archive metadata revisions, explicit unreviewed evidence,
bounded validated JSON, hash-checked reads, CAS conflicts, metadata-only backup.
Repository complete:6new tests/full142unit/targetedTS/strictmodulePASS. Real IN718
metadata-only pilot saved and restored under ignored .runtime. No live migration.
Next work is content-addressed artifact storage + dry-run import + full bundle.
On clean continuation dispatch, source01a0c339 stops writing; successor must claim
this same LOCAL checkout after reading STATUS/CURRENT CONTINUATION and Git.

# Latest architecture decision — shared LPBF core authorized

User explicitly reversed the earlier restriction: "Yok yok ortak çekirdek yapalım".
Build the shared LPBF core and database integration; defer secondary modules.
Final in-flight repair64e7cca (Python0159cdf), app tree clean. Existing model-specific
assumptions and validation evidence must remain explicit.

# Current owner — 01a0c326-5fad-7fb1-8c28-47770538592d, 2026-09-21

USER PRIORITY UPDATE: LPBF engines and database first. Secondary module work is
deferred in SECONDARY_MODULE_BACKLOG, no longer a phase gate. In-flight EIS repair
verified unit133/lint/build, Python4+12+10 and actual browser; recording final
checkpoint only. Next scope is LPBF tests, material authority and data persistence.

User explicitly authorized continuation and confirmed no other agent is editing
the three dirty EIS files; inherit their existing changes without reverting.
Source01a0c323 has stopped writing. Starting HEAD5c9e7cb. First package owns
python/cnls_fitting_solver.py, focused synthetic contract tests, then the
SyntheticNoiseStressStudio/cnlsOptimizer/syntheticEISNoiseGenerator consumers,
their types and regression/browser harnesses. Preserve observed external edits.
Acceptance: fit displayed points, no invented recovery/uncertainty/grades,
input-bound asynchronous work, meaningful unit/numerical/browser checks.
Phase0 OPEN. STATUS and handoff maintained by this owner.

# Historical owner retained — successor NOT created

Two create_thread calls were auto-review rejected. Original user messages were
retrieved before retry, but review still requires direct approval in this task.
Approval question pending; do not bypass/retry without it. Source01a0c15d retains
ownership. d4db76d code verified; clean app tree before docs-only checkpoint.
Phase0 remains OPEN; exact next work is CURRENT CONTINUATION. No running server.

# Successor dispatch checkpoint after d4db76d

Identity/fitted-topology package complete;126unit/lint/build/10browser hook checks
PASS, actual held-response paths verified. Servers37764,17228,25496 and verified
children stopped;3193/5193 no listeners. Source01a0c15d stops writing on fresh LOCAL
successor dispatch. Successor inherits after STATUS/CURRENT CONTINUATION/Git.
Next scope: explicit client-JS and SyntheticNoise contracts; inspected findings
recorded in handoff, not yet implemented. Phase0 OPEN. No push/install.

# Current owner — 01a0c15d, 2026-09-21

Inherited clean LOCAL main HEAD792e6b7; source01a0c148 stopped on dispatch.
Owns CNLSFittingStudio, EquivalentCircuitBuilder, PlotlyEISViewer, a focused
request lifecycle helper if needed, tests/contracts-browser.tsx and checkpoint
documents/parent STATUS. Acceptance: changed inputs/retries/unmount reject late
fit and DRT results; accepted fits do not silently rewrite newer inputs; Python
simulation never displays old points as current. Held real-response browser
regression plus lint/unit/build. No push/install/worktree or Gemini assignment.
Phase0 remains OPEN. Historical ownership below is superseded.

Package verified: unit126/lint/buildPASS,10 hook browser assertions, real held
fit/DRT/simulation regressions PASS. Additional owned paths pythonCnlsReport and
its test: fitted report topology corrected (R3→R2 red/green). Details in Phase0
audit. Next scope: explicit client-JS solver and SyntheticNoise consumers.

# Successor dispatch checkpoint

Code e1ab00f complete; browser serverPID17488 and descendants stopped;
3192/5192 have no listeners. Source01a0c148 stops writing upon fresh LOCAL
successor dispatch. Inherit after reading STATUS/CURRENT CONTINUATION and Git.
First scope: Studio/Builder/Plotly input identity and late responses. All other
open scopes/limits are in current handoff. Phase0 remains OPEN.

# CNLS package checkpoint — current owner01a0c148

Sign fix b5c83c3; result-contract package verified with Python12+10, unit125,
lint and buildPASS; browser actualAPI3192→IPC5192 passed local fit/error/partial
flows. Owned paths include CNLSFittingStudio, cnlsOptimizer, pythonCnlsReport,
eisData types, builder null rendering, focused tests and checkpoint documents.
Next immediate scope: late-input/report identity across Studio/Builder/Plotly;
explicit client-JS and SyntheticNoise stress wrappers still need audit. Then
synthetic EIS provenance and prior Phase0 gates. Phase0 OPEN. No push/install.

# Current owner — 2026-09-21

Continuation task 01a0c148-fa30-79c0-8e4f-94a5c74bb4d4 inherits the shared LOCAL
main checkout at clean HEAD4f76eca. Source01a0c133 stopped writing on dispatch.
Owns python/cnls_fitting_solver.py, new focused numerical tests, fitting report
contracts/consumers as inspected, and STATUS/PROOF/audit/handoff/this record.
First acceptance: analytic R and R-C recovery; truthful fixed/zero-iteration,
uncertainty and convergence reports. No phase acceptance, push, install or
Gemini scope assumed. Historical ownership below is superseded.
# Active Work

Checkpoint ad5adf5: current package complete (lint PASS, unit122, build PASS,
browser software checks). Final server PID31408 absent and3191/5191 have no
listeners. Fresh successor will inherit on dispatch; source01a0c133 will stop
writing then. First pending scope: Python CNLS numerical/short-input contracts,
shared fitting consumers and synthetic EIS provenance, after inspecting/claiming.
See CURRENT CONTINUATION; historical ownership below is superseded on transfer.

Continuation task 01a0c133-a81d-7f93-9174-d85ad5b1e979 owns the shared LOCAL
checkout from clean HEAD 6600806 on 2026-09-21; source 01a0c11f stopped writing.
Current package: the twelve component paths in lint-continuation-baseline.txt,
src/utils/materialDataPipeline.ts and focused regression/browser tests. Ownership
also includes this record, Phase0 audit, handoff and parent STATUS.md. No worktree,
push, package install or Gemini assignment. Acceptance: tsc passes through actual
contracts; candidate identity/properties survive transfer; missing precipitation
input cannot become a default prediction; EDS transfers chemistry only; browser
interaction, unit suite and build verified. Phase0 remains OPEN.

Browser exposed a real Python CNLS report mismatch (missing chiSquare crashes
the circuit builder). Same owner additionally claims src/utils/pythonCnlsReport.ts
and tests/python-cnls-report.test.ts. Normalize observed fields without success
defaults; do not infer convergence when Python omits its termination reason.


Continuation task 01a0c11f-9971-7130-b007-bfc77b3a474a takes ownership on
2026-09-21 from source 01a0c10a after verifying clean HEAD a1348ff and empty index.
Same LOCAL checkout; no worktree, push or Gemini assignment. Current package owns
the two EIS studios, shared latest-request hook/service and regression tests.
Acceptance: backend errors/missing reports remain unavailable, old responses and
cached results cannot masquerade as current input, and no compliance defaults.
Micrograph export remains the next claimed package. Phase 0 remains open.

EIS package complete: unit117/117, build PASS, live component/API browser checks
PASS (real results, controlled failures/partial/late responses, keyboard). General
lint remains FAIL, no changed-EIS diagnostics. See Phase0 audit for exact limits.
Next work: train_micrograph_segmentation.py import side effects and untrained
export guards; new Python regression tests belong to this same owner.

Micrograph export package complete: seven guard regressions PASS; existing
nonfabrication backend ten PASS. Training/export availability is explicit, no
artifact generated. Next planned scope is the existing TypeScript lint failures;
claim exact files after inspecting real type contracts. Test servers3190/5190 stopped.

Successor Codex task 01a0c10a-46a8-76f0-8ab9-a58e32966009 took ownership on
2026-09-21 after checking HEAD 95b6222, the empty index, and every inherited dirty
path against the handoff. Source task has stopped editing. Same checkout and
acceptance gates continue; no Gemini work assumed. Additional owned UI paths:
src/components/EISUploadInsightsStudio.tsx and PhysicalValidationStudio.tsx.
Acceptance: analysis failures clear results and expose errors; unavailable
consistency metrics never become fabricated pass/fail evidence.

Live API follow-up: Codex owns server/pythonRuntime.ts and
tests/python-runtime.test.ts. Explicit METALLIX_PYTHON must select that executable
for LPBF as well as other services; absent an override, preserve WSL-first behavior.

Verification record ownership includes PROOF.md and
python/benchmark_keyhole_convergence.py. This is prescribed-cavity numerical
evidence only; curved mesh asymptotic convergence remains unresolved.

Fresh-task handoff requested by the user: see the archived `docs/archive/2026-09-21/DIGITAL_TWIN_HANDOFF_2026-09-21.md`.
After successor dispatch the source task stops editing; successor Codex inherits
the scopes below after rechecking Git/ownership. Continue until acceptance gates
are satisfied; proactively checkpoint and transfer before context fills.

Coordination record; not an atomic lock or proof that another agent received a task.

| Agent | Task | Checkout | Owned paths | State / acceptance |
| --- | --- | --- | --- | --- |
| Codex | Digital Twin Phase 0 current-code audit | Metalliksa-1, main, baseline fb1a614 | docs/ACTIVE_WORK.md, docs/DIGITAL_TWIN_PHASE0_AUDIT_2026-09-21.md, audit regression tests; parent STATUS.md | In progress: fresh runtime/build/tests, keyhole energy/seed/input checks, orchestrator and UI/API/worker tracing; no phase gate accepted yet |
| Gemini | Not assigned here | Unknown | None recorded | User will assign scope; confirm paths before overlapping writes |

Codex additionally owns python/lpbf_worker.py and python/test_lpbf_worker_optional.py to isolate optional Warp/PyTorch imports from the CPU queue. Acceptance: real CPU capabilities and estimate requests work without optional backends; unsupported requests return an error without killing the worker; existing queue tests retain cancellation/restart/error behavior.

Next repair scope (same owner, 2026-09-21): python/lpbf_keyhole_raytracing.py, python/test_phase26.py and new keyhole regression tests; python/orchestrator.py, python/lpbf_modulus_fno.py, python/test_phase11.py, python/battery_corrosion_python_ingest.py, python/battery_corrosion_eis_solver.py, python/train_micrograph_segmentation.py and fabrication regression tests. No fabricated measurements, untrained inference or fixed thermal result may be published as a successful calculation. Missing implementations fail explicitly. Keyhole acceptance: valid bounded finite inputs, executable Warp kernel, reproducible local RNG, distinct absorbed/escaped/truncated energy and flat-surface analytic checks. No experimental validation claimed.

Integration scope also owned by Codex: routes/lpbfSimulation.ts, src/components/KeyholeRaytracingLab.tsx, docs/MODULE_EVIDENCE_INVENTORY.md, and tests for the new route. Acceptance: same-origin UI → Node → worker requests; visible backend failure; superseded results discarded; no implicit remote scene assets; current inventory includes all registry modules with honest evidence limits.

Codex maintains shared STATUS.md and serial Git index operations until an explicit handoff. Further product fixes will be claimed here after inspection and before editing. Gemini scope remains unknown; this record is not delivery confirmation. Recheck working tree and this record before each write/commit.

Checkpoint8157c18 complete. Source task01a0c10a stops writes when successor is
created. Next owner must read STATUS and the CURRENT CONTINUATION section of
`docs/archive/2026-09-21/DIGITAL_TWIN_HANDOFF_2026-09-21.md`, verify Git, then continue the claimed open scopes.
No Gemini work assumed; no phase gate accepted. Temporary test servers are stopped.
# Current owner — 01a0c383-a755-7b53-84c6-3ec040b67aa0, 2026-09-21

Handoff checkpoint:5ee6fae run archive; adfdcca evidence repair. User explicitly
requested a fresh task now (context grew). Source stops all writes after LOCAL
successor dispatch; successor claims its real ID. Test3197 server and verified
descendants stopped. Next fullrun+source bundle/restore then bounded API/UI.
Remaining dirty files are external, preserved; user stopped that other task.

Run package committed5ee6fae. Next owns only LPBF experimental comparison:
python/lpbf_experimental_validation.py, python/test_phase10.py,
src/components/ExperimentalValidationLab.tsx, its focused presentation test and
checkpoint docs. Remove fabricated fixed simulation inputs and unconditional
validated/pass/high claims. Missing linked data remains unavailable; arithmetic
comparison must not imply independent experimental validation.

Continues LOCAL HEAD64bc5aa. Owns new lpbf run capture/repository/import modules,
their focused tests, narrow python/lpbf_worker.py integration and checkpoint docs.
Acceptance: immutable snapshots, Python-verified bindings, complete output manifest,
exact historical source revisions, byte checks before publication, isolated restore.
No live migration, second queue, installation, push or secondary module work.
Preserve external edits in SECONDARY_MODULE_BACKLOG, uqLabData,
pythonComputationService, monteCarloEngine, eisFileParser and tafelParser.
CBM generation2026-09-18 stale/untracked; direct source fallback for named paths.

## Newest core-physics slice — Phase 22 evaporation (2026-09-24)

Phase 22 now uses the same `T >= T_solidus` gate for liquid-surface
evaporation energy loss, free-surface mass recession, and energy-ledger
accounting. A regression first reproduced energy loss at 1850 K with fixed
surface height, then passed with zero below-solidus evaporation and preserved
the above-solidus mass/energy relation. Full
`test_lpbf_transient_3d_gpu.py`: **30/30 CPU Warp PASS**; no GPU execution was
run for this slice. Windows pytest-cache and Warp PCH-temp cleanup ACL warnings
occurred after passing kernel checks. Experimental/model qualification does
not change. Next physics review: bound the explicit momentum predictor's time
step by advection and viscosity stability as well as thermal diffusion.

## Latest numerical physics fix — explicit momentum time step (2026-09-24)

`solve_toolpath` now limits its nominal step by both thermal diffusion and the
combined explicit advection/viscosity rate, conservatively assuming the
existing 5 m/s per-component velocity clamp. The bound is
`dt * sum(5/h_a + 2*(mu/rho)/h_a^2) <= 0.5`. The synthetic low-alpha case
confirms the momentum limit controls, and exact-end-time scheduling remains
intact. The full Phase 22 Python suite passes **31/31 on CPU Warp**. This is
numerical stability coverage, not experimental validation. Next: continue the
separate alloy data gate and P4/P5 model/data blockers without changing their
recorded outcomes.

## Latest P7 source decision — Hastelloy X (2026-09-24)

The source review does not clear a complete melting-range data gate. Scheel
et al. gives useful as-deposited LPBF Cp/enthalpy coverage, but liquid
conductivity is a 15× model assumption, density is a fixed room-temperature
measurement, and uncertainty is incomplete. NASA AM context and NIMS
liquid-density evidence do not combine into a chemistry/state-matched property
revision. Keep P7 and runtime admission closed; a bounded pilot may be considered
only with measured properties separated from explicit assumptions. Detailed
source limits and citations: docs/HASTELLOY_X_P7_SOURCE_HUNT_2026-09-24.md.

P4 remains failed, P5 unavailable, and P6 partial. Continue physics closure and
same-physics GPU scale/crossover analysis; numerical parity alone is not
qualification.

## Latest core-physics closure — projected CFL and graph-floor stop (2026-09-24)

Phase 22 now checks the actual projected velocity field against the explicit
momentum/enthalpy transport bound before enthalpy or the energy ledger changes.
If the conservative 0.5 rate bound is exceeded, the solver fails closed with a
validity error. The same preflight stops if a molten surface with evaporation
would be clipped at the z=2*dz graph floor. Synthetic regressions cover both
conditions; the full Phase 22 suite passes 33/33 on CPU Warp. GPU execution was
not part of this test run; Windows Warp temp cleanup emitted an ACL warning
after passing tests.

NIMS experiment 264 remains a separate liquid-density source lead only:
public metadata exposes no chemistry ID, numerical values/uncertainty, or
specimen-specific surface-tension/viscosity fits. See
docs/HASTELLOY_X_P7_SOURCE_HUNT_2026-09-24.md. P4 failed, P5 unavailable, P6
partial, and P7 closed remain unchanged.

## IN625 repeated timing checkpoint — 2026-09-24

A post-change timing campaign used a warm-up and five alternating CPU/CUDA
repeats at each frozen mushy-range resolution. Median CUDA/CPU ratios were
24.6× slower at 128 cells and 14.1× slower at 1,024 cells; temperature-field
differences remained below 9.1e-13 K. The focused suite passed 12/12 after the
synchronization reduction. This direct solver timing excludes UI/API transport
and is not a paired before/after campaign, so it establishes neither speedup nor
crossover. Details: docs/IN625_CUDA_BENCHMARK_2026-09-24.md.

Next: keep this path as explicit numerical CPU/CUDA parity evidence and profile
larger same-physics workloads before attempting fused kernels. P6/P7 remain
partial; IN625 remains unvalidated.

## Larger same-domain IN625 timing screen — 2026-09-24

A 2,048-cell z-refined case preserved the 2×2×0.5 mm domain, 3.3 ms
duration, 30 W / 0.099 J source and 1500 K initial condition. Three
alternating warmed timings had CPU/CUDA medians 4.013/43.617 s, with CUDA
10.87× slower. Both outputs reached 1593.516258 K and 44 mushy cells; the
independent enthalpy and energy oracles passed, with max temperature/enthalpy
differences 9.10e-13 K / 4.66e-10 J/kg. This remains numerical screening, not
process validation or GPU crossover. See
docs/IN625_CUDA_BENCHMARK_2026-09-24.md.

Next: only pursue fused GPU work if a backend profile confirms launch or
arithmetic bottlenecks; keep P6/P7 partial.

## Latest Phase 22 surface/enthalpy consistency fix — 2026-09-24

The moving whole-cell surface graph could advance after the enthalpy update,
leaving newly exposed cells hot in the published final state. A reconciliation
kernel now resets those cells to ambient enthalpy/temperature and records the
change once in `surface_mask_reset_J`; reported liquid volume is masked by the
current surface graph. The integrated moving-surface regression confirms a
nonzero reset term and relative energy closure error `2.79e-4`. Full
`test_lpbf_transient_3d_gpu.py`: **34/34 PASS**, including execution on CPU Warp
and RTX 4060 `cuda:0`. This is software/numerical consistency evidence, not
experimental validation. The per-step kernel's performance cost is not yet
measured.

Next: continue the active P0–P10 LPBF goal. First resolve how to represent the
NIST P5 source's 800°C/2 h treatment in the existing immutable dataset,
manifest, API catalog, and archived revision chain; do not silently rewrite a
source-bound artifact. Preserve P4 failed, P5 unavailable, and P6/P7 partial.

## NIST AMB2022-03 metadata correction — 2026-09-24

The official methods description establishes that the AMB2022-03 bare plates
were vacuum residual-stress annealed at 800°C for 2 h before scanning (Section
2.1, PDF p. 2); Section 2.5 identifies BP1 as one of those bare plates. The
local aggregate values were unchanged. A new immutable transcription
`table4-aggregate-v2.json` / version 1.1.0 records that preparation, its source
location, and the superseded v1 artifact hash. The manifest, source catalog,
NIST comparison service, Python gate, and run client now bind the v2 SHA-256.
The frozen P5 v1 preregistration remains on its original path and hash.

Windows subprocess stdin is explicitly decoded as UTF-8 in the Python NIST
comparison entry point; default console encoding had corrupted the new degree
symbol and caused correct source bytes to fail both canonical-content and
metadata checks.

Verification: NIST source/run API/UI/literature tests **30/30 PASS**; Python
comparison plus official workbook aggregate tests **9/9 PASS**; TypeScript
`npm run lint` PASS. This corrects specimen metadata only. P5 remains unavailable
because the modeled slab/support/bottom thermal boundary, 5° incidence,
measured-profile byte binding, and section operator do not match the NIST
experiment.

Next: scope a source-matched 3.17 mm IN718 plate with full-contact SS304 backing
and bottom boundary, then close the 5° source geometry and profile evidence
before any new P5 run. Keep P4/P5/P6/P7 outcomes as recorded; do not relax source
capture, mesh, or acceptance thresholds.

## Phase 22 guard GPU follow-up — 2026-09-24

The lower graph-floor and projected-CFL regressions now cover CPU and explicit
cuda:0 when available. Focused execution passed 2 tests and 4 device subtests
on NVIDIA GeForce RTX 4060 Laptop GPU. This verifies the new guard kernels and
fail-closed path execute on CUDA; it does not qualify the process model.

## NIST P5 geometry feasibility audit — 2026-09-24

The current `stationary-enthalpy-conduction-v1` resolves one homogeneous material, with a minimum 300 µm IN718 substrate, an initial-temperature fixed bottom, and no SS304 layer/contact model. The NIST comparison cannot be made source-matched by merely increasing domain depth: that would extend IN718 rather than add the support stack. Any backing/contact treatment needs a separate opt-in solver/model identity so existing v1 runs and hashes remain valid.

The current source is a normal-incidence symmetric Gaussian. `scanAngle_deg=0` is the scan-path direction and does not encode incidence. NIST Table 1's optical/thermography setup is 5 ± 0.5°; the 8° condition belongs to separate dynamic-coupling measurements. The AMB2022-03 optical package reviewed for this audit exposes no measured irradiance-map artifact, so a measured-profile gate must remain closed until one is located and byte-bound.

Next: design the versioned source/geometry contract for an opt-in layered 3.17 mm IN718 plate plus full-contact SS304 backing, with explicit interface and bottom-boundary assumptions and incidence angle/azimuth. First validate the numerical implementation independently; retain P5 as unavailable until exact source evidence, section operator, convergence, and comparison checks all pass. Preserve v1 behavior and all P4/P5/P6/P7 outcomes.

## P5 public source boundaries — 2026-09-24

NIST identifies the AMB2022-03 coupon dimensions (25.4 × 25.4 × 3.17 mm), 800 °C / 2 h residual-stress anneal, full bottom contact to an SS304 baseplate clamped by two screws, center underside Type-K thermocouple, and backside rise below 0.1 °C after a single track. The reviewed public sources do not identify the SS304 baseplate thickness or outside dimensions, screw preload/coordinates, interface conductance, or a dimensioned holder drawing. The local 2716/2718 packages expose process/thermography or optical geometry artifacts but no holder thermal-stack data. These unknowns cannot be replaced by guessed thickness, ideal contact, or AMB2022-01 geometry.

The profile source hunt found no AMB2022-03 measured irradiance array/map in the official source packages or the NIST beam-metrology report. Reported beam diameter/caustic and a rotationally symmetric Gaussian description are not the measured spatial profile bytes required by the current evidence gate. A beam CSV from AMB2022-01 belongs to different apparatus/conditions and is not transferable.

Next: complete the v2 contract design with explicit known coupon/process facts, and treat SS304 thickness/contact conductance/boundary as provenance-bound unknowns or sensitivity-only parameters. Keep the measured-profile gate closed; no source-matched P5 result can be reported until both the missing hardware metadata and exact profile artifact are resolved. Do not weaken the existing acceptance gate.

## Layered plate v2 numerical pilot — 2026-09-24

Added an opt-in `layered-plate-enthalpy-v1` CPU reference path for one bare IN718 plate over a generic SS304 support. Plate/support thickness, area-specific interface resistance, support-bottom boundary, oblique assumed-Gaussian source geometry and source penetration are explicit inputs and are bound in `coreContract` schema v2. The finite-volume interface operator conserves face transfers; the support has a separately hashed, bounded generic literature snapshot. Existing v1 model identity remains unchanged.

Focused verification: layered plate + heat source + layered conduction **24 PASS / 1 platform skip**; two v2 core-contract tests **2/2 PASS**; Python compile, TypeScript typecheck and `git diff --check` PASS. The TypeScript runtime test is blocked by Windows Node/esbuild `spawn EPERM`. One broader saved-binding test is blocked by Windows SQLite temp-directory ACL errors. These are stated validation limits, not solver passes.

This path is an unvalidated sensitivity model, not a source-matched AMB2022-03 reproduction. Generic SS304 properties and assumed contact/bottom boundary values are not specimen measurements; no measured AMB2022-03 irradiance map was found. Keep NIST P5 unavailable. The layered-model package is committed as `9a95cce`. The independent IN625 CUDA inverse is committed as `0c15487`; it passed 13 focused field tests and three same-workload paired timing runs. Warp was faster in each, with identical peak/mushy-cell fields and negligible enthalpy difference. Raw times and the variability boundary are in `docs/IN625_CUDA_BENCHMARK_2026-09-24.md`. This is limited to the tested screening workload and does not validate the alloy or process. Next: close or explicitly retain the P7 material data gate, then verify the full select→compute→compare→export→restore workflow; P6 is still partial.

## Layered-plate v2 scaffold

A standalone `lpbf_ss304_support_material.py` now provides a hashed, generic AISI 304 literature-property snapshot and bounded Cp/k/density/enthalpy evaluator for sensitivity-model development. It is deliberately not runtime alloy admission and is not the specimen's exact support revision; temperature evaluation outside 273.15–1473.15 K fails closed. Focused tests pass 4/4. Next, integrate only through a separate opt-in layered solver identity and retain the NIST source-match gate as unavailable until backing thickness, contact/bottom boundary evidence and measured AMB2022-03 beam-profile bytes are available.
# 2026-09-25 — proxy campaign contract and physics-engine audit

Current package adds a standalone `lpbf_nist_proxy_campaign.py` v1 contract:
three unique computational runs × two 4.9/6.0 mm thermal-proxy sections,
source/run/input/material provenance, and hard rejection of optical/etched or
experimental-validation claims. It additionally fails closed on boolean
schema versions, malformed trusted source metadata, and unsafe absolute or
traversing artifact paths. A valid report says `proxy-screening-only`, with
`numericalConvergenceStatus=not-evaluated` and no comparison residuals.

Focused test: `python -m unittest test_lpbf_nist_proxy_campaign -v`, **12/12
PASS**; targeted diff check PASS. The contract is not yet integrated into the
archive/API and does not verify files, solve physics, implement the observation
operator, calculate residuals, or establish mesh/time convergence.

User explicitly authorizes scientifically justified repair or replacement of
poorly functioning physics engines, including Python implementations. Next:
trace current callers/identities and audit CPU `enthalpy-fv-6` and Phase 22 GPU
operators against independent conservation/manufactured-solution checks; make a
new solver revision only for a reproduced defect, preserve old model/hash
identity, then compare CPU/GPU on identical frozen inputs. Do not present
screening or numerical parity as experimental validation. P4/P5/P6/P7 gates
remain as recorded.

# 2026-09-25 — Phase 22 parity repair and transient verification gap

Both the Phase 22 full-field and multistep CUDA parity tests hardcoded five
steps, while the adaptive stability rule produces 19 for the frozen 6 µs case.
The stale assertions prevented parity checks from running. They now require
positive step count and equal CPU/CUDA count, then execute the existing fixed
field/pressure/surface tolerances.

Verification: six focused Phase 22 suites passed **42/42** on the NVIDIA RTX
4060, including manufactured thermal and pressure fields, energy closure, and
full-field thermal/hydrodynamic parity. Legacy Phase 21 focused tests passed
**6/6**. The larger CPU engineering/heat-source/core-contract command reached
62 tests but had **8 errors and 2 skips**; errors came from SQLite temp DB
creation/cleanup permission failures, so report it as incomplete.

Independent source review found no reproduced bug in production CPU
`enthalpy-fv-6` or the reviewed Phase 22 operators. This does not qualify their
screening/prototype assumptions or experimental validity. Known boundary: the
CPU temporal refinement study uses a test-local update loop rather than the
production transient stepping path. Next: create an independent manufactured
transient check that exercises production stepping, while preserving solver
identity for any correction and only opening a new model revision for a
reproduced physics defect. The current user authorizes scientifically justified
Python solver repair/replacement. P4/P5/P6/P7 gates remain unchanged.

## 2026-09-25 — production CPU final-step correction and convergence result

The production `transient()` loop accumulated enough floating-point time error
to add a tiny final step at 50/25 ns. A frozen 350 µs case produced 7,001 /
14,001 steps and minimum dt `5.18e-17` / `4.34e-19` s. The loop now snaps the
reported integration time to `end` inside a step-count-scaled ULP tolerance
capped at `1e-14` s. The integration increment, source, and energy accounting
are unchanged; the new regression fails before this fix and passes after it.

Post-fix actual CPU 3×3 run: standard IN718, 40 W, 200 µm track, 40 µm layer,
layer-conforming, meshes 40/20/10 µm; timestep caps 100/50/25 ns yielded actual
100/50/25 ns and 3,500/7,000/14,000 steps. Max energy residual `1.63e-13`.
Mesh gate **failed**: depths 40/20/30 µm; finest pair differs 33.3%. Time gate
**inconclusive**: width/depth are identical across time levels although peak T
changes 2795.36→2793.79→2793.74 K; that metric is outside the pre-frozen gate.
Focused production physics and convergence-contract tests **15/15 PASS**.

Next: retain P4 as failed/inconclusive; diagnose grid/thresholded-geometry
resolution and design any new observable/protocol before running it. This is
numerical screen evidence, not experimental validation. Preserve original P4
thresholds and continue the complete P0–P10 objective.

## 2026-09-25 — Production transient manufactured check and CUDA request guard

Added `python/test_lpbf_production_transient_manufactured.py`. Uniform and
nonuniform manufactured enthalpy ramps now run through the actual CPU
`transient()` loop while retaining production source-limiter retries and
capture checks. For the nonuniform solution, the passive conduction and
boundary-loss rate at every step matches a separately coded face-flux oracle;
three distinct timestep caps recover the analytic final peak and center. Both
cases close energy below `1e-10`. This closes the prior gap where temporal
refinement used a separate local update loop and now checks the production
spatial operator on a manufactured field. It remains numerical verification,
not experimental validation.

The CUDA thermal pilot now rejects `powderGridPolicy=layer-conforming` before
device discovery and mesh work. The pilot still implements the standard-grid
model identity, so accepting a layer-aligned request would have performed
expensive work under the wrong contract. Standard/reference acceptance remains
covered. No physical equations or legacy model identity changed.

Verification: `test_lpbf_gpu_thermal` plus the two manufactured transient tests
**9/9 PASS**, including frozen IN718 and estimated-legacy 316L CUDA parity on
RTX 4060. The manufactured + heat-source + convergence suites ran **27 tests:
26 PASS, 1 Linux-only OpenFOAM skip**. These checks do not establish
experimental validity or a GPU speedup.

Implementation commits: `e8fd1ca` and `7bacffa`.

Next: measure the scale/crossover of a parity-matched CUDA/Warp implementation
of the same `enthalpy-fv-6` physics before using it to attempt the preregistered
2.5 µm P4 refinement. Preserve P4 thresholds/outcomes; P6 remains partial and
IN625 full-transient admission remains closed.

## 2026-09-25 — P7 alternative-alloy source gate

A primary-source scan found no alternate LPBF alloy ready for full-transient
admission. The strongest data set is NIST SRM 1155a steel (Cr18-Ni12-Mo2; the
thermophysical papers identify it as 316/316L): its certificate is a dense
steel disk intended for chemical-analysis reference, while the papers provide
enthalpy/density/Cp and thermal conductivity over the melting range. Part of
conductivity is inferred from Wiedemann–Franz and
Smith–Palmer relations; the high-temperature solid Smith–Palmer coefficients
come from a composition-similar 316L, and the liquid relation is an explicit
Wiedemann–Franz assumption. It can support only a separately named dense-SRM
reference model, not LPBF powder/as-built admission. [NIST certificate](https://tsapps.nist.gov/srmext/certificates/1155a.pdf),
[Pichler et al. 2019](https://doi.org/10.1007/s10853-019-04261-6),
[Pichler et al. 2022](https://doi.org/10.1007/s10765-022-02991-5).

The screened AM-state alternatives do not cover melting: PBF Ti-6Al-4V
thermophysical data stop near 1000 °C, and the reviewed as-built SLM AlSi10Mg
data stop at 500 °C. [Ti-6Al-4V PBF study](https://doi.org/10.1016/j.addma.2022.103045),
[AlSi10Mg study](https://doi.org/10.1557/jmr.2018.405). Decision: keep the P7
LPBF alloy gate closed; do not relabel dense NIST steel properties as AM
properties. Existing estimated-legacy 316L and IN625 screening remain
separately classified.

## 2026-09-25 continuation — scientific Python authority and P6 source path

Can explicitly authorized scientifically justified repairs or a Python replacement for a core physics engine when its current results are inadequate. Preserve governing-equation provenance, model identity, frozen acceptance thresholds and evidence scope. Separate analytical/manufactured checks, CPU/GPU parity, performance measurements and experimental validation.

The opt-in CUDA implementation now evaluates the same two-node GL2 moving Gaussian cell integral and the existing 25 K source-step limiter used by the CPU reference for the bounded standard powder-layer single-track subset. Direct cell source/rate agreement is within `rtol=1e-10`; capture differs by at most `1e-12`, timestep by `1e-15`, and retry count is exact. The frozen full CPU/CUDA temperature-field parity passes without relaxing targets. Optimizing GL2 batching and joining capture/timestep readback reduced the CUDA-source median from 10.171 s to 9.062 s, but the synchronized alternating 934-step CPU-source median was 6.722 s: the CUDA source path remains about 35% slower. It stays opt-in; queued/default metadata still identifies CPU source integration and limiting. No speedup is claimed. Commit: `a3d8aaa`.

Focused verification on the current checkout: `python/test_lpbf_gpu_thermal.py` 9/9 passed on the RTX 4060; full `tsc --noEmit` and the owned-file `git diff --check` passed. The tied-peak diagnostic regression passed 2/2; no historical P4 result or frozen threshold changed. Earlier production transient manufactured-forcing and face-flux checks remain recorded above.

The NIST proxy-campaign persistence/API slice is committed as `d967f87`: three archived runs must bind the same exact source revision, physical input/material revision and core identity; the server derives the campaign from archive records. Client-supplied measurements/residual/validation claims are rejected. Bundle schema v2 retains v1 reading and checks run/source references. Runtime Node/tsx tests could not start in this Windows environment (`spawn EPERM`); do not call the campaign flow integrated until the UI slice and end-to-end checks are completed. A route allowlist regression was added but shares this runtime limitation. Do not present this six-section thermal-proxy screening record as an optical comparison or NIST validation.

Next: finish the campaign UI/client typing and panel wiring; rerun typecheck and focused tests where the environment permits. Then run an identical-workload P6 scale/crossover benchmark while preserving the strict parity contract. Only consider using CUDA for P4 mesh refinement if measurements show a useful crossover; keep frozen P4 failed/inconclusive outcomes unchanged. Keep P5 unavailable and P7 LPBF/as-built material admission closed.

## 2026-09-25 continuation — proxy campaign UI wired

The archive panel/client now select three distinct archived transient-thermal run IDs and a published Table 4 case, request a server-derived preview, show the six simulated thermal-proxy sections with explicit unvalidated/no-residual wording, then save the immutable campaign record using the preview hash. Client payloads never include measurements or validation claims. Server API/persistence/bundle commit: `d967f87`; UI/client plus focused client and server-rendered UI tests: `7004742`.

Full `tsc --noEmit` passed after integration; focused Python GPU tests passed 9/9 on the RTX 4060; `git diff --check` was clean. Node API/client/UI test processes could not start: Windows returned `spawn EPERM` from the test runner/esbuild worker. Direct Node type stripping also cannot resolve this repository's extensionless TypeScript imports. Treat these runtime tests as unavailable, not passing. A successful preview/create and live v2 bundle export/verify/restore have not been exercised with eligible archived runs. The UI also has no campaign list/reopen endpoint yet, so a saved campaign is only displayed from its create response until the user reloads; bundle persistence remains the recovery path.

Next: implement a campaign list/reopen read path if it fits the persistence flow, then verify preview → immutable create → bundle export/verify/isolated restore with the real archive and keep the optical comparator unavailable. Continue P6 scale/crossover only with exact CPU parity; current CUDA source integration remains about 35% slower and opt-in.

## 2026-09-25 continuation — reopenable campaigns and bundle v2 client fix

A follow-up review found the run-bundle client still accepted only manifest schema v1, while the campaign persistence commit exports schema v2 with `campaignCount`. The client now accepts the exact v1 or v2 field set, validates the v2 count, and retains v1 compatibility; focused regression added to `tests/lpbf-run-client.test.ts`.

Saved campaign records now have a read-only `GET /api/lpbf/runs/proxy-campaigns` path. It verifies each campaign record hash through the repository decoder and checks every archived run document hash and exact source-revision link before returning records. The panel loads saved campaigns after refresh and can reopen their six proxy observations. Focused API/client tests cover the list response. Commit: `7cfba1a`.

`tsc --noEmit` passed after the list and bundle-client changes; Node tests remain unavailable due the repeated Windows `spawn EPERM`. `git diff --check` is clean. Do not mark live campaign API/UI and bundle round-trip complete without a successful runtime exercise. Next: verify the whole flow with eligible archived run/source identities when the process-runner blocker permits, then perform a strict-parity scale/crossover benchmark for P6. Keep the CPU source default; current CUDA source integration remains about 35% slower.

## 2026-09-25 continuation — campaign list and integration test result

The campaign read/list path and bundle-v2 client acceptance are committed in `7cfba1a`. Follow-up testing from the restricted environment initially hit `spawn EPERM`; the same focused Node suite was then run outside that process restriction. API, campaign client/UI, run repository, bundle client, and bundle API/bundle restore tests passed **48/48**. The campaign repository test also confirmed a persisted record reopens from SQLite and a changed archived run SHA is rejected.

The server-rendered panel test exposed the existing `useInputBoundTask` useLayoutEffect warning. `src/hooks/useInputBoundTask.ts` now keeps layout-effect timing in browsers and uses passive effect during server rendering. The rerun has no SSR warning and remains 48/48. Full `tsc --noEmit` and `git diff --check` pass. This proves the mock/in-process API contracts and synthetic archive/bundle round-trip; no real, eligible three-run NIST source-bound campaign has been created in the live app yet. P5 remains unavailable and no physical validation claim is introduced.

## 2026-09-25 continuation — scientifically authorized core repairs and P6 scale check

Can explicitly authorized scientifically justified repair or Python replacement of inadequate core physics engines. Preserve equation provenance/model identity unless a supported model change is deliberately justified; do not relax frozen capture/parity/convergence gates. Report software/numerical evidence separately from physical validation.

On RTX 4060, the matched IN718 10 µm, 73,568-cell, 934-step case passed CPU/GPU parity with both source paths: field-rise L2/max relative differences were `2.60e-9` / `7.28e-9`, and energy/other parity targets passed. Speed was not repeatable: one un-warmed alternating series gave CPU reference 11.4155 s and CUDA evolution + CPU source 9.4337 s; a warmed series gave CPU 9.6377 s and CUDA 9.5839 s (GPU samples 8.2945–9.7906 s). The latter pair is effectively tied. CUDA source integration median 9.4236 s did not materially improve on CPU source integration. The earlier `compare_with_cpu` wall times included both GPU and CPU oracle work and are not standalone path timings. A 5 µm full run did not start because it exceeds the pilot's current `MAX_CELLS=100000` guard; earlier 5 µm component timing is not a full-solver result. Keep the CPU source path as default and CUDA source integration opt-in. These are numerical/software checks, not experimental validation.

At 20 µm and 9,196 cells, alternating medians were 6.8944/7.0524 s for CUDA evolution + CPU source and 3.3405/3.2946 s for CPU reference (GPU about 2.1x slower). The full CPU/GPU field comparison passed. No repeatable useful crossover is established; the previous scalar synchronization-batching experiment was reverted after it showed no stable improvement.

Next: proceed with the open live source-bound proxy-campaign archive round-trip when eligible archived runs are present; in P6, profile the dominant transient operator and select the next optimization only if strict full-field parity can be retained. Frozen P4 outcomes and P7 alloy admission stay unchanged.

## 2026-09-25 continuation — layer-conforming powder default and shared GPU identity

The core review found that legacy cell-center activation and physical-surface source clipping could refer to different z faces. Standard NumPy-reference powder transients now automatically use the existing `layer-conforming` grid and model identity `stationary-enthalpy-conduction-layer-conforming-v1`; `backend=auto` resolves to that reference path for standard powder runs. Archived legacy v1 records and their identity remain intact. The explicit OpenFOAM selection is outside this change and has not been validated for the aligned model.

The concrete IN718 80 µm/25 µm-request/three-layer legacy reproduction stopped at 86.763% source capture under the unchanged 99% minimum. The aligned run completed at an actual 20 µm spacing with zero surface-face offset, 13,068 cells, 2,602 steps, and energy-relative error `2.57e-14`. The CUDA pilot now accepts and binds the same layer-conforming model; its full CPU/GPU parity tests, queue integrity test, and result/client contract passed.

Verification: Python engineering **36 passed, 1 OpenFOAM worker skip**; core contract **15/15**; CUDA thermal **9/9**; heat-source **14 passed, 1 OpenFOAM skip**; CUDA queue **3/3**; full TypeScript typecheck and focused Node GPU/contract tests **5/5**. The broader API suite had 5 passing tests and one OpenFOAM capability check unavailable on this Windows worker. No experimental validation was added. Next: profile GPU evolution without trusting `compare_with_cpu` wall time, and live-test the NIST proxy archive flow when eligible runs are present.

## 2026-09-25 continuation — manufactured liquidus-contour geometry check

The recorded 6.6667 µm IN718 run has no full resolved input, material/model identity, input hash, or standalone report, so it is not a controlled refinement pair with the older 10 µm run. Keep the descriptive 80/33.333 µm and 2590.16 K output separate from the older 80/30 µm and 2793.74 K record; do not use those deltas as convergence evidence.

Added an analytic 3D contour check using a translated sphere and a translated ellipsoid rotated with the scan direction. For 20/10/5/2.5 µm samples, the existing peak liquidus-edge operator's absolute width/depth errors decreased at every refinement; at 2.5 µm the largest errors were 0.044/0.0193 µm. `python/test_lpbf_interpolated_section.py` passed **5/5** on the Windows Python 3.12 runtime. This is measurement-operator verification, not a thermal PDE or physical validation. The tied-peak audit also found no broad time-tie spread sufficient to explain the P4 depth failure. Current evidence does not justify replacing the heat equation.

Next: keep P4 failed/inconclusive and run any new convergence study only from a fully resolved, hashed scenario with the current material/model identity; preserve both cell-extent and contour outputs and their distinct gates. Do not reuse the unhashed 6.6667 µm diagnostic as a refinement level.

## 2026-09-25 continuation — build-job material revision response contract

The real Python build-job result omitted top-level `materialPropertyRevision`, although the TypeScript store requires it to match the revision inside `buildJobIdentity`. Add the versioned field from `MATERIAL_PROPERTY_REVISION`, assert the Python result contract, and add a client regression that rejects a backend-shaped successful response with the top-level field missing. A direct Windows Python 3.12 solver call returned success and matching `build-job-effective-properties-v1` revisions. The focused Node regression then passed **13/13** on an allowed runner after the restricted sandbox returned `spawn EPERM`; `git diff --check` passed. This response-contract repair is separate from physical model validation.

## 2026-09-25 continuation — material snapshot hash binding and GPU profile

The build-job client now recomputes the Python-compatible canonical SHA-256 for the material-property snapshot and its build-job identity before accepting a result. The archive repository independently verifies both bindings when present while retaining read compatibility for historical v1 records without the new fields. Focused client/repository tests passed 26/26, including Python float byte spelling, tampering rejection, archive hash persistence and v1 compatibility. `npx tsc --noEmit` passed.

A warmed RTX 4060 profile of the same 10 µm, 73,568-cell, 934-step IN718 pilot case exposed substantial per-step CPU/GPU transfer and launch overhead (149,447 CUDA kernel launches, 12,245 synchronizations, 18,785 tensor copies; profiler attributed 4.393 s of CPU time to launch APIs). A `torch.compile` trial was unavailable because this Windows environment lacks a working Triton installation. A separate fused Warp candidate is in progress under strict full-field CPU parity. These facts do not establish a physical-model defect or a stable speedup; the existing Torch path remains opt-in.

Next: finish the Warp candidate measurements, then diagnose the frozen P4 convergence evidence for a concrete numerical/operator defect before changing equations. Any repair must preserve frozen thresholds and be verified against an independent analytic/manufactured or CPU oracle; report numerical and physical evidence separately.

## 2026-09-25 continuation — opt-in Warp CUDA candidate and P4 audit

A separate explicit-device Warp CUDA candidate now fuses constitutive lookup, finite-volume conduction, enthalpy advancement and inverse-table lookup while retaining the shared CPU GL2 source integration and 25 K timestep limiter. It is bounded to 100,000 cells / 20,000 steps and is not wired into the queue or default solver. On the RTX 4060 exact 10 µm IN718 pilot (73,568 cells, 934 steps), full-field CPU parity passed: same timeline, relative rise L2 `6.81e-17`, max-rise `1.58e-16`, and energy closure `1.83e-14`. The focused regression passed 2/2 and `py_compile` passed.

An alternating warmed 3+3 CUDA comparison measured Torch at median `12.0627 s` (range `0.6353 s`) and Warp at `8.0938 s` (range `0.2647 s`), ratio `1.490x` for this one thermal evolution case. Both completed the same 934 steps. This is a promising pilot result, not a full workflow or alloy-wide performance claim. The Warp NVRTC PCH temp directory hit Windows ACL denial; the candidate temporarily disables the PCH option only while launching/compiling its kernels and restores the prior global setting immediately. One inaccessible Warp temp subfolder remains outside the repository. Keep the candidate opt-in pending environment cleanup and broader workload validation.

A separate read-only audit of frozen P4 found no evidenced error in the thermal equation or flux operator. Energy closure passed at `1.63e-13`; the mesh gate still fails on its discrete geometry output (width 80/80/80 µm, depth 20/30/35 µm, finest-pair depth change 14.2857%). Preserve that result and all limits. P4 actual mean accepted steps were 89.217/50/25 ns, ratios 1.784/2.000, so time convergence remains correctly inconclusive. Next, improve diagnostic evidence by recording the accepted-dt distribution and active bounds; requested `maxDt` ratios alone cannot certify realized temporal refinement.

## 2026-09-25 continuation — realized timestep-distribution diagnostics

The CPU reference now records the accepted timestep sequence as a compact distribution: count and total, min/mean/median/p90/p99/max, `sum(dt²)/T` as a descriptive first-order Euler error scale, fraction at requested `maxDt`, and source-limited step/retry counts. The solver schedule, equations, model ID, energy gate and frozen P4 acceptance thresholds are unchanged. Convergence-study rows carry this evidence. The API validates the version, ordering and formula; the physics panel shows it in an expandable section with explicit wording that it is not a convergence pass criterion.

Verification: Python heat-source suite **15 passed, 1 OpenFOAM skip**; focused TypeScript UI/API diagnostics suite **5/5 passed**; `npx tsc --noEmit` passed. The full frozen P4 three-level case has not been rerun with this instrumentation, and its old failed/inconclusive results remain unchanged.

Next: run at least three predeclared maxDt levels on the same CPU/reference workload and inspect realized `sum(dt²)/T` ratios and requested-cap binding fractions. Leave the outcome inconclusive if the actual distributions do not satisfy the existing ratio requirement; preserve the mesh, physics and acceptance thresholds.

## 2026-09-25 continuation — four-alloy Warp parity

The opt-in Warp candidate passed same-model full-field CPU parity for IN718, 316L, AlSi10Mg and Ti-6Al-4V on the common 10 µm, single-track/single-layer process case. All four material-specific revisions and CPU/Warp step counts matched, energy closure passed, and every result remained `experimentalValidation=false`. The Python test module completed 3/3 tests, with the four materials as subchecks in one test. These are four estimated materials and numerical/software parity only; they are not alloy qualification or experimental validation. The 1.490x Warp/Torch timing remains specific to the IN718 pilot and must not be generalized to the other alloys.

The test process used a per-command `WARP_CACHE_PATH` inside `python/.warp-cache` to avoid the denied user-profile kernel cache. Warp still emitted a cleanup traceback for a PCH temp directory below `%TEMP%`, but the Python process returned exit code 0 and every assertion passed. No persistent Warp cache setting, default backend, or queue route was changed. Keep the candidate opt-in.

## 2026-09-25 continuation — scoped IN625 source admission and NIST run-cost audit

Added `validate_in625_screening_admission`: the bounded IN625 route now checks the exact alloy identity, canonical content digest, source/locators, and pinned constitutive inputs before the capability report marks it available. It admits only `bounded-fusion-enthalpy-screening`; full transient admission and experimental validation remain false. A stale digest and a correctly rehashed but wrong-alloy snapshot both reject. This is source-scoped data admission, not an experimentally validated material model.

Focused verification: `test_lpbf_material_capabilities` 5/5, the generic unverified-user-table compatibility test 1/1, Python compilation and targeted `git diff --check` passed. The broader `test_lpbf_engineering` ran 38 cases but had 6 `WinError 5` temporary-folder/SQLite access errors and one OpenFOAM skip; it is not a passing suite.

The NIST path audit found an existing 10 mm bare-plate rectangular-corridor CPU route with 4.9/6.0 mm thermal-proxy samples. Estimated meshes are about 171,696 cells at 20 µm, 386,127 at 15 µm, and 1.30M at 10 µm (above the CPU 600k cell cap); current GPU pilots do not accept this bare-plate contract. The sampling operator still does not measure NIST's etched optical boundary. Next: cost and corridor-boundary sensitivity preflight for a source-bound CPU protocol; do not start a three-run campaign until runtime and domain independence are supported.

The first 20 µm NIST-input cost run stopped at the model's boiling/nonphysical-enthalpy validity guard. It used estimated legacy IN718 IR absorptivity 0.38 and a 5 µm source-penetration assumption because NIST does not provide that volumetric input; neither assumption is source-matched. No complete runtime was measured, no run was archived, and the failure does not establish an error in the enthalpy equation. Do not tune absorptivity to force a successful or closer-looking comparison; obtain source evidence or preserve the NIST path as unavailable.

The official optical source catalog lists the six case-0 P3/P4 cross-section TIFFs and per-file SHA-256 sidecars; the 2024 paper reports six measurements per case (three tracks × two sections). The TIFF bytes and sidecar values are not yet locally verified, so the optical operator still cannot be implemented against inspected pixels. The separate NIST dynamic-coupling dataset is not an exact 67 µm beam input: its baseline is 285 W / 960 mm/s / 110 µm with 76 and 131 µm spot variants. NIST defines coupling as non-reflected power and explicitly says it can include plume absorption; it provides no uncertainty budget for that measurement. Do not substitute it for the old 0.38 absorptivity in the 67 µm case.

## 2026-09-25 continuation — production-path manufactured diffusion check

Added a third focused test while retaining both existing production transient regressions. The new test applies a fixed-property analytic diffusion eigenmode through `lpbf_simulation.run()` with the production mixed boundaries: Dirichlet at the substrate base, insulated side/top conduction, and the top radiative boundary balanced explicitly in the manufactured forcing. Only `integrated_source` is patched; the original timestep selection, source limiter/retries, enthalpy update, conduction and energy ledger remain active. It is a numerical operator check, not an LPBF laser/material validation.

Verification: `python -m unittest test_lpbf_production_transient_manufactured -v` **3/3 passed** (11.1 s); targeted `git diff --check` passed. Predeclared 8/16/32 z-cell meshes with `maxDt=1e4*dx²` gave full-field RMS errors `5.656e-4 / 1.421e-4 / 3.556e-5 K`, observed spatial orders `1.993 / 1.998`, and relative energy closure `2.79e-16 / 2.79e-16 / 5.59e-16`.

The analytic production-path result and read-only equation audit did not establish a core thermal physics defect, so no solver equation was changed. Frozen P4 still fails its mesh acceptance gate. The new workflow roundtrip test is reported PASS 1/1 by its worker agent, with TypeScript and diff checks passing there; this shell could not reproduce the run because Python process probing/child spawning is blocked (`METALLIX_PYTHON --version` / `spawn EPERM`). The test correctly preserves NIST comparison as unavailable/unvalidated when exact optical/process matching is missing.

Next: finish the source/data acceptance and end-to-end evidence matrix. Keep the NIST experimental comparison unavailable until raw TIFF bytes/checksums are retrieved and inspected. Only alter a physics equation when an independent oracle demonstrates a reproducible error.

Follow-up same-turn check: the material capability suite passed **5/5**, including the four existing alloy snapshot contracts, strict unsupported-identity rejection, IN625's bounded source/content/constitutive-input gate, and snapshot-mutation isolation.

## 2026-09-25 continuation — analytical melt-pool input/irradiance fixes

A read-only targeted audit found a silent Rosenthal fallback for unknown heat-source IDs, 10-unit floors on laser power/speed/beam that made the solved and reported process vectors diverge, and no finite-positive validation for process dimensions. It also found that `peakIntensity_MW_cm2` was the uniform-disk average while the code called it Gaussian beam-center intensity. For a Gaussian beam with 1/e² diameter `d=2w`, the normalized profile integrates to `P` with `I0=2P/(πw²)=8P/(πd²)`. The Python solver now rejects unknown source IDs and invalid process values, preserves positive sub-10 inputs without clipping, computes VED/LED from the same input vector, and reports Gaussian peak irradiance with the corrected formula. The shared TypeScript intensity helper uses the same formula.

Verification: solver input/irradiance/wavelength regression **5/5 PASS**; melt-pool accuracy fixture **PASS**; Goldak/Fabbro fixture **PASS**; TypeScript typecheck **PASS**; direct execution of the TypeScript helper **PASS** (285 W, 67 µm → 16.167 MW/cm²); scoped `git diff --check` **PASS**. The Node/tsx test worker could not spawn in this sandbox (`EPERM`); it was not counted as passed. This output-metric correction and input validation do not establish experimental validation or alter the frozen P4 gates.

Next: audit remaining bounded physics engines; preserve failed/inconclusive convergence and NIST evidence gates.

Wavelength follow-up: no `absorptivity_Blue` material property was found in the indexed Python material records, while the UI exposes `Blue_450nm`; the previous selector treated every non-Green wavelength as IR. The engine now accepts only IR_1064nm and Green_515nm where corresponding material properties exist, and the Blue options in both thermal-map screens are disabled with an explicit reason. The same focused suite asserts Blue rejection and the Inconel 718 Green absorptivity path.

## 2026-09-25 continuation — multi-track impulse-energy kernel

The isolated `green_function_point_temperature()` returned the point-source Green's function per joule as though it were a temperature rise; varying absorbed power left its result unchanged (0/100/200 W all returned 3408.0125 for the reproduced input). It now multiplies by the instantaneous heat impulse `Q = P_abs * dt`. The production hatch-sequence integration already applied `P_abs * dt_sub` to its kernel and was not changed. `python -m unittest test_phase17 -v` passes **6/6**, including zero power → zero rise and exact linearity with impulse energy; `py_compile` and scoped diff check pass. This remains an analytical screening model, not experimental validation.

Code/test commit: `bb8087e`. Continue targeted engine review and keep NIST experimental comparison blocked by source/condition traceability until resolved.

## 2026-09-25 continuation — multi-track near-wake quadrature

The thermal accumulation audit identified a converged-integral defect in the
fixed 8-pulse midpoint rule. Reproduced with Ti-6Al-4V at 280 W, 1000 mm/s,
8 mm track length and 0.1 mm hatch: for the next-track near-wake sample at
12.5 ms and (4.0, 0.1) mm, 8 pulses returned 73.307667 K while independent
refinement reached 115.422057 K by 32/64 pulses. This is a 36.5% underprediction
within the current model's own Green-kernel formulation.

`evaluate_track_temperature_rise` now doubles midpoint resolution from 8,
accepting only when consecutive accumulated values differ by at most 0.1%,
with a 512-pulse bound and an explicit error if convergence is not reached.
The near-wake regression passes against the converged value within 0.2 K.
`python -m unittest test_phase17 -v` passed **7/7**; `py_compile` and scoped
`git diff --check` passed.

This corrects quadrature, not the physical model: residual accumulation still
represents each scan as centerline point pulses without the Gaussian beam
footprint, and the Rosenthal spot-rise relation remains a screening estimate.
No experimental validation is implied. Next continue the bounded engine audit
and source-matched workflow while leaving the NIST optical comparison
unavailable until the source and observation gates are satisfied.

## 2026-09-25 continuation — reject unbracketed solidification fronts

A manufactured field exposed a false-front defect in `_binary_z_liquidus`: if
temperature remained above liquidus at the configured search-depth ceiling,
the helper returned that ceiling as if it were a root. For `Tliq=1700 K`,
`T=1700+100+1e6*x-1e5*z`, and an 8 µm search depth, the old mapper reported 9
front points with median `G≈1.005e6 K/m` and `R≈0.995 m/s`; the crossing was
actually at 960 µm, outside the domain.

An unbracketed upper boundary now returns the no-front sentinel, while an exact
liquidus crossing on the boundary remains accepted. Regressions cover both
cases. `python -m unittest test_lpbf_solidification -v` passed **6 tests**
with **1 OpenFOAM-only skip**; Python compilation and scoped `git diff --check`
passed. This is a manufactured search-bound correction only, not experimental
validation.

Next continue bounded engine review and complete source-matched workflow
evidence; screening G/R remains distinct from measured solidification data.

## 2026-09-25 continuation — normalize Goldak to physical total power

The source equation audit found that the standard Goldak double-ellipsoid with
`f_f+f_r=2` integrates over both lobes to `2Q` (Fachinotti et al., 2009,
[DOI 10.1002/cnm.1324](https://doi.org/10.1002/cnm.1324), Eq. 2). The Python
analytical field had received physical absorbed/geometric power directly as
`Q`, doubling its represented power. `GoldakField` now interprets its input as
physical total power and evaluates the conventional coefficient at half that
value. The model identity is now `goldak-total-power-v2`; both downloadable
CAE cards emit the half-power Goldak coefficient alongside efficiency.

The measured-track factor-of-two scoring band did not change. After the
normalization, Guo 316L N01 predicted depth is 131.3 µm vs 180 µm (27.1% MAPE),
inside that broad screening band. This is not exact process matching or
experimental validation; the NIST source-matched optical comparison remains
unavailable and frozen P4 acceptance remains unchanged.

Verification: new Goldak total-power normalization tests **2/2 passed**;
`test_goldak_fabbro.py`, melt-pool accuracy, solidification-front script,
literature catalog, and TypeScript typecheck passed. An old catalog assertion
that N01 must stay outside the unchanged broad band was updated to match the
new calculation; no acceptance threshold was changed. Scoped diff check passed.

Next continue the bounded solver audits and source-matched workflow evidence.

## 2026-09-25 continuation — accepted timestep distribution run in progress

An opt-in repeat execution scope is now implemented and committed. Ordinary
queue submissions still reuse the matching computational job. An explicit
repeat skips only that reuse lookup, retaining the same validated physical
input/cache identity while producing a distinct run ID. The UI exposes this
only after the exact input signature completes and labels it as a computational
record, not a physical repeat. Commits: `363c1ef` and `c354032`.

The frozen 5 µm CPU temporal diagnostic for P4 is running against protocol
`docs/LPBF_P4_CURRENT_40W_ACCEPTED_DT_DIAGNOSTIC_PROTOCOL_2026-09-25.md`
(SHA-256 `2f9fbea438a1b9c22aa7124a72550a354bf4b7b6df2a82a908449302d591d1a4`).
The 100 ns level completed with 3,923 accepted steps, mean 89.217 ns, minimum
3.094 ns, and 1,682 source-limited/retried steps. The 50 ns level completed
with 7,000 steps, mean 50 ns, 99.986% cap hits, and no source-limited steps or
retries. The 25 ns level is currently running. Partial results are in
`docs/LPBF_P4_CURRENT_40W_ACCEPTED_DT_DIAGNOSTIC_2026-09-25.partial.json`.
Continue the existing process; do not restart it. Once all three levels finish,
verify the final report against the frozen protocol and retain failed or
inconclusive status when required. This diagnostic does not change the frozen
P4 failure or establish experimental validation.

The existing temporal estimator requires a constant actual-spacing ratio
within 2%. The completed levels have mean-dt ratios 1.784 and 2.0 (the
first-order `sum(dt²)/T` scales have ratios 1.830 and 2.0). The coarsest run
contains 1,682 source-limited/retried steps while the 50 ns run has none, so an
unequal-spacing Richardson fit to one scalar effective dt is not justified for
this frozen case. The continuous contour changed only about 0.003% in width and
less than 0.001% in depth from 100 to 50 ns; the finest row is still pending.
Keep the frozen gate unchanged and report temporal convergence as inconclusive
unless all existing acceptance conditions are actually met.

## 2026-09-25 continuation — NIST Table 4 section identity

Read-only source audit mapped the publisher workbook's six rows per condition
to three physical tracks (`_1`, `_2`, `_3`) and two sections per track: P3 at
4.9 mm and P4 at 6.0 mm. The later NIST result report says Table 4 `n=6`, and
the publisher TIFF catalog uses matching P3/P4 plus track-number filenames.
The older challenge-method document instead says three tracks × P1–P4. Keep
that source discrepancy explicit; do not synthesize P1/P2 Table 4 rows. The
publisher workbook is locally hash-pinned, but individual TIFF bytes/sidecars
are not yet locally verified and no etched-optical observation operator exists.

The existing campaign remains bound to the local Table 4 aggregate transcription
and `thermal-proxy-screening`; its geometry is not an etched optical observation
and it emits no comparison residuals. Next source task is to archive/hash-bind
the six raw observations and matching TIFFs in a separate experimental evidence
contract before implementing any optical comparison operator.

## 2026-09-25 continuation — archive workflow portability gap

Read-only UI/API audit confirmed the live path for material and input
selection, worker execution, exact source-bound run archiving, unvalidated
proxy-campaign preview/save, and server-local bundle export/verify/isolated
restore. The current bundle UI returns an ID only: it cannot download a portable
bundle to the user's device, upload one on another server, or open the restored
copy in the application. Existing bundle tests verify same-server integrity and
restore isolation, not cross-server portability or restored-run navigation.
The thermal proxy remains explicitly unvalidated. Any portable-bundle follow-up
needs bounded streaming, strict manifest/artifact verification, archive quotas,
and isolated restore; do not weaken source identity checks.

An additional source hunt found no IN625 or alternative alloy with a complete,
LPBF-relevant five-property table over the full transient range, including an
independently supported upper temperature and viscosity. Keep the current
IN625 CUDA path at bounded bare-plate screening; CPU/CUDA parity for the four
legacy registry alloys is numerical implementation parity only. Do not admit a
new generic transient alloy or broaden scientific CUDA qualification until the
data gate passes.

## 2026-09-25 continuation — NIST measured-profile source correction

The primary-source follow-up refined the earlier “no measured profile found”
wording: NIST AMS 100-67 Fig. 7 includes normalized measured signal-intensity
traces and central x/y sections. This is a published plotted 1D profile, not a
raw 2D camera array or an identified data artifact tied to the exact AMB2022-03
Case 0 67 µm / 5° scan; no profile-byte checksum is locally pinned. The report's
3.3 µm (5.2%, k=1) uncertainty applies to spot diameter, not profile intensity.
Keep the current gate closed until case-specific profile bytes and their
D4σ/model mapping are established. Source: [NIST AMS 100-67](https://doi.org/10.6028/NIST.AMS.100-67).

## 2026-09-25 continuation — accepted-dt diagnostic completed

The frozen supplementary 5 µm CPU run completed at requested max-dt values of
100/50/25 ns. Energy relative error stayed below `1.7e-13`; discrete width and
depth remained 80/35 µm. The existing gate correctly reports `inconclusive`:
accepted mean dt was 89.22/50/25 ns, which does not provide the constant actual
refinement ratio required by the existing convergence helper. No nonuniform
Richardson fit or new criterion is admissible. Original P4 remains `failed` and
unchanged; no experimental validation is implied.

The three row implementation hashes differ because the current fingerprint
hashes every `python/*.py`, including repeat-worker/test files written while the
long run was active. No numerical solver edit was found among post-start Python
changes, but this is not a single implementation-hash-locked convergence series.
For any future acceptance claim, freeze the source snapshot for the entire
series and record solver-scoped provenance. Report SHA-256 is
`777ed20aa55b4c518ce27a0d6672c50b987bb786eb67e24a1db1ebb0ee3d9284`.

## 2026-09-25 continuation — thermal implementation fingerprint v2

The broad `python/*.py` fingerprint was replaced with a versioned production
source manifest covering the static Python import closure and checked-in local
OpenFOAM sources/build files. It excludes tests, worker orchestration, scratch
files, and the diagnostic runner; it fails closed for missing, duplicate, or
out-of-root entries. The UI now calls it an implementation fingerprint rather
than a source revision. Focused provenance checks passed 6/6; the existing
input-independence case passed; repeat-scope tests passed 2/2 in the permitted
runner after the default sandbox could not open its temporary SQLite files.
TypeScript typecheck, Python compilation, and scoped diff check passed.

A new frozen protocol pins the scenario, runner bytes, levels, output path, and
per-row hash-integrity requirement. The repeat computation has not started yet;
the previous report remains preserved and inconclusive. Next: commit this
protocol/runner with the source change, execute the frozen levels, then report
only the existing numerical gate outcome.

## 2026-09-25 continuation — solver-fingerprint-locked P4 run started

The frozen 5 µm CPU diagnostic is now running in terminal session `29680`
against `docs/LPBF_P4_CURRENT_40W_FINGERPRINT_PROTOCOL_2026-09-25.json`.
Protocol SHA-256 is
`DB0A85E22A75709FCABB3F3BEE9E7C0D44213A081881F6A076EE5DE6820274DF`; the
scenario SHA-256 is
`2ABEC47F9D35C02158EA2E06876E3CA06C3BA5BA9243F1DDCCAA94EF64752EA6`.
The requested max-dt levels are 100/50/25 ns. The run records its versioned
solver manifest and its start-time dirty paths. It started at
`2026-09-25T20:00:11+03:00` with implementation fingerprint
`8302df5a8237b0a84b9b6e467b37421a7627f831611f9c992d037f3ac118948b`.
Latest live-session poll: stage `running`; the 100 ns row completed in 3,923
steps, with mean accepted dt 89.217 ns and relative energy error `1.335e-14`.
The 50 ns row completed in 7,000 steps with mean accepted dt 50 ns. Both rows
have matching before/recorded/after implementation hashes. The 25 ns level
remains in progress. Two rows do not establish convergence or acceptance.
Continue polling this same handle, verify all three row hashes, and apply the
existing convergence gate. Preserve the previous `failed`/`inconclusive`
reports.

## 2026-09-25 continuation — IN625 enthalpy scope and data-gate audit

Read-only source review confirmed that IN625 already has a separate typed
`in625-bareplate-field` job and `barePlateThermalField` capability, bound to
the exact source snapshot and recorded as `bounded-material-screening`. The
scope is 273.15–1623.15 K, assumes fixed supplier density 8440 kg/m³, and uses
explicit absorbed watts. Above-liquidus, powder/full-transient, and
experimental-validation claims are rejected or excluded. A second thermal-
only gate would duplicate the existing capability.

The enthalpy PDE uses density, conductivity, heat capacity, phase bounds, and
latent heat; viscosity does not enter this field equation, though it remains
needed for the full transient report's derived Marangoni metric. Keep the
full-transient gate unchanged. This was a source audit only: no tests or
runtime execution were performed, so existing dirty source/test files remain
untouched and runtime verification is still required before claiming a check.

## 2026-09-25 continuation — portable run bundle flow

Added streaming USTAR download/upload, isolated import verification and restore,
and UI navigation to restored records. The restore ID is stored locally in the
browser and can be entered again after a page reload. Existing run/source hash,
identity, and live-store isolation checks remain in force. The path rejects
traversal, links, duplicate entries, and oversized archives.

Focused HTTP/tar tests pass **6/6**; `npx tsc --noEmit`, production build, and
scoped `git diff --check` pass. In a separate local browser tab, the LPBF
workflow loaded and the restore-ID control enabled only for a valid 32-digit
hex ID. The actual file-transfer/restore UI action was not exercised; the API
round-trip test covers download, upload, verify, restore, list, and open while
checking that live database bytes remain unchanged.

Current transport is uncompressed USTAR with a 16 GiB limit. Imported bundles
have no retention/cleanup policy yet. Bundle integrity is evidence integrity,
not model or experimental validation.

## 2026-09-25 continuation — P4 final diagnostic and browser archive round-trip

The fingerprint-locked 5 µm CPU run completed all requested 100/50/25 ns levels.
Final report: `docs/LPBF_P4_CURRENT_40W_FINGERPRINT_DIAGNOSTIC_2026-09-25.json`,
SHA-256 `726cad9aa1d4f2b7dc3009b8b10ed1a7db08b49ba1f9bc9e4b872f662054b558`.
Protocol and scenario hashes matched the frozen files; runner and assessment
module hashes matched their pinned values. All row before/recorded/after
implementation hashes and the final hash matched
`8302df5a8237b0a84b9b6e467b37421a7627f831611f9c992d037f3ac1189489`.
The three rows took 3,923/7,000/14,000 accepted steps, with mean dt
89.217/50/25 ns. Maximum relative energy error was `1.629e-13` (pass).
The actual mean timestep ratio is not constant, so the existing time-axis
convergence gate is **inconclusive**. Reported zero finest-pair relative change
uses cell-extent width/depth (80/35 µm at all levels); the independent
continuous-contour values vary and were not the acceptance metric. The frozen
P4 failure and experimental-validation=false remain unchanged.

In the separate local test browser tab, a 3-run/132-artifact/3-source-link
bundle was created, verified, downloaded (10,107,904 bytes), uploaded from the
downloaded `.tar`, verified, restored into a second isolated archive, and a
restored run was opened. Restore ID persistence through reload also worked.
The UI lost its download button for a verified, existing bundle ID after reload;
`LpbfRunArchivePanel` now offers download for that verified ID. `npx tsc --noEmit`
and scoped diff check passed; the changed button appeared after verification
in the browser. The production build passed in the permitted runner (the
default sandbox returned `spawn EPERM` before the build could start). This archive
integrity flow does not validate the model or the NIST optical comparison.

Next: address the separately versioned NIST optical observation operator and qualified alloy-data
admission without weakening existing evidence gates.

## Active parallel LPBF packages (2026-09-25)

- `/root/restored_run_comparison` owns `routes/lpbfRuns.ts`,
  `src/components/LpbfRunArchivePanel.tsx`, `src/services/lpbfRunArchiveClient.ts`,
  and focused route/client tests until handoff. Contract: restored runs expose
  the existing scientific comparison result without promoting unavailable
  optical evidence to validation. Root owns browser QA and integration commit.
- `/root/nist_case0_tiff_map` is read-only: map six official Case 0 workbook
  observations to exact NIST TIFF/sidecar assets and report provenance gaps.
- `/root/p4_refined_dt_protocol` owns only new refined-timestep protocol,
  runner, and focused test files. It must not launch the heavy 12.5 ns run;
  root will review/freeze the protocol and launch at most one run. The prior
  frozen P4 and completed fingerprint diagnostic remain immutable.

Handoffs: restored-run comparison and NIST TIFF mapping agents completed;
root owns integration. The refined-dt agent completed the new protocol/runner;
root reviewed and committed them as `f3866c8`, then started exactly one 12.5 ns
solve in live terminal session `68021` at `2026-09-25T18:17:47Z`. Partial report
`docs/LPBF_P4_REFINED_DT_DIAGNOSTIC_2026-09-25.partial.json` is `running`.
Protocol SHA-256 is
`a49e64803db8ac14a01d361a7958515ff3927ddf258880a6aeb9d73966342595`;
the implementation fingerprint matches the prior 50/25 ns rows. Do not edit
manifest sources or restart for observation delay. `/root/lpbf_cpu_hotspot_audit`
now owns a read-only CPU performance audit while this run executes.

The official NIST workbook Case 0 rows 2–7 map in order to L0-1/P3,
L0-1/P4, L0-2/P3, L0-2/P4, L0-3/P3, L0-3/P4. The NIST catalog lists each
`AMB2022-718-SH1-BP1-{P3|P4}-L0-{1|2|3}.tif` and a separate `_m.tif`
variant, each with its own `.sha256` sidecar. The source image bytes, sidecar
contents, and `_m` annotation meaning were not verified: official data fetch
failed at the local proxy. This mapping advances source identification only.

Restored-run comparison integration: a dedicated restore endpoint reads the
verified isolated bundle; UI shows the same NIST comparison panel for restored
runs. Root reran focused route/client/tar tests **27/27 PASS** and `npx tsc
--noEmit PASS`. Browser on restarted local server showed restored and live
records return the same `unavailable`/`unvalidated` source-revision reason;
keyboard Return triggered the restored action. Production build and scoped
integration commit are next. The browser sample's archived Table 4 revision 1
does not match the currently reviewed revision 2, so no residual was shown.

Root completed the production build (PASS) and reviewed the scoped diff. The
read-only CPU audit found duplicate harmonic face-conductivity work in
`conduction_rate` and `conduction_diagonal`; existing timings do not establish
a P4 speedup. Keep the live solver fingerprint fixed until session `68021`
finishes, then profile and compare numerical parity before a performance edit.

## LPBF CUDA lifecycle and validation checkpoint (closed for this work package, 2026-09-28)

- Root owns integration, scientific acceptance gates, STATUS/PROOF and commits. Preserve all unrelated dirty files and existing user work.
- `/root/sol_workflow_audit` (completed, read-only) audited Queue cancellation, timeout, child kill, startup recovery, race behavior and existing GPU-specific tests; concrete gaps were reported to root.
- `/root/astra_science` (completed, read-only) audited convergence and independent IN718 measurement evidence gates; no solver run or evidence relabeling was proposed.
- `/root/sol_nvidia` (completed, read-only) checked actual GPU/benchmark evidence and Nsight availability; no code or tests were changed.
- `/root/luna_source_ui` completed the scoped worker/test edits in `python/lpbf_worker.py` and `python/test_lpbf_worker_lifecycle.py`; root reviewed and tightened terminal-state ordering. The focused lifecycle, timeout and CUDA queue group passed **15/15** under the permitted runner, including actual RTX 4060 CUDA queue execution. Changes are ready for an explicit-path commit.
- Shared acceptance: terminal status must survive refresh; a cancelled/timed-out/restarted job cannot publish partial results, count as completed/cache-hit, or silently fall back; retry identity and artifacts stay explicit. Numerical/experimental evidence remains separately labelled.
- Remaining boundary: Windows abrupt worker-process death is not covered by a Job Object or equivalent tree-lifetime mechanism; orphan-child recovery remains open. Full queue E2E performance and moving-source convergence/IN718 experimental gates also remain open; see `STATUS.md` for current evidence and next actions.

## LPBF continuation checkpoint — 2026-09-28
Worker cleanup ordering and source-revision restore/selection issues are implemented and narrowly verified. Focused worker tests 13/13, source API/client/selection tests 20/20, lint, Python compilation and production build pass. Two explicit-path commits are being prepared for these scoped packages; no push/merge. Preserve all remaining user and unrelated changes.
Next exact actions: finish scoped commits; profile the frozen thermal workload in repeated CPU/GPU sessions without changing solver fingerprint; rerun mesh/time convergence on current code; keep the IN718 experimental gate closed until a setup-matched independent measurement package with uncertainty and observable mapping is pinned. Re-check the four-alloy single authority and any new-alloy provenance/uncertainty gate before model admission. Keep software correctness, numerical verification and experimental validity separate; use `unvalidated` where evidence is missing.

Commit record: worker lifecycle package **4c6fb21**; source revision archive/API/UI package **3f3e048**; evidence/checkpoint updates **67495aa**. All are local commits on `codex/lpbf-buildjob-material-identity`; nothing was pushed or merged.

## LPBF performance and convergence audit — 2026-09-28
Prior alternating measurements are solver-only (one session, 3 samples/backend) and do not include final-field capture/full job. Warp median 8.101761 s vs Torch 10.482651 s on 73,568 cells/934 steps; CPU-source/Torch source-integration 10.517767 s vs 10.322751 s. Profiler counts expose transfer/dispatch/synchronization as candidates but no kernel durations; Nsight Systems/Compute unavailable on PATH. Do not optimize a named kernel or claim E2E speedup from this evidence.
P4 fixed-scan continuation is not safe to rerun as-is: old source/solver fingerprints and occupied output paths. The 20/10/5 µm mesh and 50/25/12.5 ns timestep matrix's three fine runs cost an estimated 25.8B cell-steps. Next implementation unit: version a fresh P4 protocol and runner with explicit empty output/field roots and current solver/material/source hashes, memory/cell/time preflight, preserving ≤1% energy and finest-pair ≤5% W/D plus trend gate. Run coarse case first, then decide if full matrix is feasible.
Worker residuals: Queue.close's production call is process shutdown; direct ResumeThread WinAPI fault injection and process-descendant behavior stay unverified. Do not present fake-child regression as those proofs.

## P4 v2 frozen gate — 2026-09-28
Commit `64cae84` adds `docs/LPBF_P4_CPU_OPERATOR_CONVERGENCE_PROTOCOL_2026-09-28_v2.json` and its dedicated bounded runner/regressions. Root repeated tests 9/9, Python compilation and exact hash/material/source/destination preflight smoke: PASS. Solver not run. Before execution, check system memory and make a single coarse-level feasibility measurement or otherwise justify starting the full matrix. The v2 protocol only tests accepted-timestep convergence at 5 µm mesh; the historic spatial mesh study remains inconclusive. Preserve the three P4 acceptance thresholds and all old report files.

## 2026-09-28 continuation — fresh P4 v2 CPU run completed
The frozen temporal protocol was executed successfully from HEAD `c20f69cfaaaf3365374cc2ba7343ea36a1b2befa`; report `docs/LPBF_P4_CPU_OPERATOR_CONVERGENCE_V2_2026-09-28.json`. All 3 rows completed at fixed 5 µm / 526,592 cells: 7,000 / 14,000 / 28,000 accepted steps for 50 / 25 / 12.5 ns, totaling 25.803008B cell-steps. Maximum energy relative error `3.5676e-13` (energy PASS); integrity and all three final-field NPZ hashes/sizes PASS. Implementation fingerprint stayed fixed at `05ac6db2446c7ee940355d172432eab6e299c31bc543bb6cc72722522f8347dd`.

Both discrete and continuous-contour temporal assessments remain **inconclusive** under the unchanged frozen gate: discrete 80/35 µm geometry is identical at all three levels; contour finest-pair changes are 0.00305% / 0.00119%, but its trend check reports non-monotonic/unresolved geometry. This fixed-mesh time study says nothing about spatial convergence. `experimentalValidation=false`; independent IN718 experimental validation remains **unvalidated**. Supersedes the earlier “solver not run” preflight note above.

Next: freeze and preflight a separately versioned spatial mesh protocol using the current implementation/material/input hashes and exclusive outputs; profile full-job CPU/Torch/Warp timing and transfers only with repeatable measurements and final-field parity. Keep the new-alloy evidence gate and independent IN718 experiment gate closed pending admissible sources, uncertainty and observable/setup mapping.

## 2026-09-28 continuation — repeated RTX 4060 Torch/Warp benchmark
The frozen 10 µm IN718 request (73,568 cells / 934 steps) was measured in two separate sessions with the existing warmed, alternating three-trial/backend procedure. Report: `docs/LPBF_GPU_ALTERNATING_BENCHMARK_2026-09-28.json`. Torch/Warp medians were 12.084/12.047 s (1.003×) and 12.361/12.044 s (1.026×). Within-session spreads exceeded the median differences; the previous single-session 1.294× Warp result was not reproduced. The measured scope omits final-field capture, queue and persistence, so end-to-end performance remains unmeasured. Do not optimize based on this result alone. Next profile the full request lifecycle and device timeline, then select one attribution-backed target; require unchanged numerical parity after any optimization.

Nsight availability was rechecked beyond PATH: no `nsys.exe` or `ncu.exe` exists under the standard NVIDIA Program Files roots. Prior instrumentation counted 149,447 launches, 12,245 async copies and 12,245 synchronizations without device-kernel durations. GPU kernel attribution remains unavailable; do not treat dispatch counts as kernel time.

Focused shared-core contract, transient enthalpy, mesh-convergence and contour-convergence regressions passed **35/35** on the permitted Windows runner. The sandbox attempt's sole failure was Windows TEMP/SQLite access and passed on rerun. Software/conservation regression evidence is distinct from scientific-source review and independent experiment validation; both remain open.

## 2026-09-28 continuation — alloy evidence gate review
IN625 remains screening-only. Correction: the Georgia Tech XLSX and source pages are already archived; local file hashes and all 20 values/U95 columns were checked against the property-inspection record. Data cover solid material only from 260–1000 °C; conductivity derives from measured diffusivity/Cp and assumed fixed density. The specimen's lot/chemistry/heat treatment and transfer to the LPBF target are unknown. NIST's 0.65–1.02 W/(m·K) interval is LPBF powder-only and its inverse-model assumed-parameter uncertainty sensitivity was not analyzed. The combined sources do not close phase-transition/latent/liquid/optical/full-model uncertainty, so no full-model admission. No alloy authority changes. Next: obtain target-lot/composition and model-scope coverage or leave IN625 `unvalidated`. For IN718, residuals stay withheld until exact NIST source binding, setup/profile and optical observer match; process/observer identity failures must remain `unavailable`.

Verification update: four-alloy/material capability + IN625 property-table Python tests **7/7 PASS**; local Georgia Tech artifact hashes and workbook-vs-inspection cells/U95 exact. TypeScript catalog Vitest could not run because the package is not present in the offline npm cache (`ENOTCACHED`); this remains unverified.

IN718 case 0 residual remains withheld. The checksum-bound NIST Table 4 transcription is 285 W/960 mm/s/67 µm D4σ, six measurements per condition; current GPU timing request is 60 W/1200 mm/s/80 µm, and the P4 CPU temporal study is another 40 W/800 mm/s/80 µm case. No per-case measured 2D beam-profile artifact or six-section observer is bound to a comparable run. Focused NIST comparison/parser tests **10/10 PASS**, demonstrating correct `unavailable` behavior rather than a physical comparison. Next: only make a NIST comparison after a matched CPU run captures the exact spatial/replicate observer and the measured beam profile/input uncertainty; then compare mean + uncertainty with the model result. Current CPU experiment status stays **not verified**.

## 2026-09-28 continuation — Windows Job Object cleanup paths
Worker lifecycle cleanup now checks Win32 `CloseHandle` and does not publish a process return code until all owned handles close; a failed close retains the handle for cleanup retry. Direct WinAPI mock regressions cover ResumeThread failure/reap, TerminateJobObject error, wait error, and CloseHandle error/retry. Actual parent-kill test confirms the child is gone, stale job failed, and artifact absent. Focused lifecycle/timeout suite **17/17 PASS**; `py_compile` and diff check PASS. These mocks are not real OS fault injection, and descendant process-tree behavior remains **unverified**. Commit this package after final diff/status review.
# LPBF archive follow-up — 2026-09-28

Completed this package: source-link status now checks the archived dataset ID,
revision, and SHA-256 before saying `exact-revision-bound`; unresolved links
remain explicitly unverified. Focused API/client/UI tests **28/28 PASS** and
TypeScript lint **PASS**; code/evidence commit `b184c46`. A fresh local server completed API export/verify/
isolated restore/readback and real UI bundle verify/restore/export; a restored
run preserved its ID, document hash, and `unvalidated-model` status. The tar
route returned 200 with 134,133,760 bytes. All 21 source and 134 run artifact
references matched local byte counts and SHA-256 values.

Open evidence: IN718 Table 4 comparison still reports `unavailable` because the
fixed artifact does not match the reviewed local comparison revision. No
residual was calculated. An older 4177 server's bundle create returned 503,
while 4178 passed; investigate runtime/root configuration before calling the
existing local instance healthy. Keep the user's 4176 browser tab untouched.

Next: inspect 4177/4176 bundle roots and refresh persistence without changing
run/source records; locate the historical Table 4 artifact if available,
otherwise preserve `unavailable`. Continue shared-physics literature,
spatial-convergence, NVIDIA profiling, and four-alloy authority checks.
