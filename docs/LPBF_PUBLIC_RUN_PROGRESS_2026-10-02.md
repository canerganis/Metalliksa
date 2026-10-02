# CPU public-run progress and Automatic dispatch

## Supported scope

`CpuRunProgress` remains optional for Standard / Reference / single CPU solves.
Valid Standard Automatic powder-layer requests now receive worker progress
tracking after the existing dispatcher resolves them to Reference. The numerical
solver, default inputs, accepted clock and backend selection are unchanged.
Bare-plate Automatic inputs and Automatic inputs with an explicit powder grid
policy remain invalid under the existing input rules. Reference bare-plate inputs
retain their existing support. Studies, calibration, layered-plate, OpenFOAM,
Torch and Warp are outside this CPU progress contract.

The worker's shared `cpu_reference_progress_supported()` helper predicts eligible
CPU candidates. Public `run()` still validates the actual selected solver and
resolved Reference settings before starting the tracker. The helper does not
validate all input fields or change dispatch. Unsupported input/backend failures
before tracking begins do not acquire a CPU work claim.

## Lifecycle and failure boundary

1. Public `run()` validates the tracker type and single-use rule. It resolves
   inputs and the existing backend, then checks actual CPU eligibility.
2. `transient()` begins source-work and accepted-step accounting. Counts retain
   their original definitions and optional source-work budget behavior.
3. Successful thermal stepping leaves public progress `running` while
   core-contract construction, thermal audits, artifact writes and final JSON
   checks execute.
4. Public `run()` emits `completed` only after all its processing succeeds.
   A direct `transient()` call still completes at that method's return boundary.
5. An exception after tracking starts is re-raised as the same object and type,
   with `exception.progress`. Errors after thermal processing finished add
   `failureStage: "postprocessing"`. The same error crossing both decorators
   triggers one failure notification. Callback errors preserve accepted counts
   and their original exception.

The worker adds runtime evidence and publishes `result.json` after `run()` returns.
Publication failure retains completed CPU work and returns a failed job without
a newly published completed result. A failed execution can leave diagnostic
field files or an incomplete temporary write; those are not completed results.
Hard kills, timeout recovery, memory limits and other solver work remain outside
the source-work counter contract.

## Callback scope isolation

Calling `run()` or `transient()` inside an active tracked callback is rejected
before inner solver work, whether the inner call supplies a tracker or omits it.
Without the no-tracker guard, an inner transient inherited the outer ContextVar
and could corrupt its source-work or accepted-step counters. Both public and
thermal entry points now guard this case. Metadata observers should return their
analysis and perform another solve after the active call ends.

Public-boundary and source-accounting contexts are reset after success or error.
A tracker whose solve actually started remains single-use. A rejected preflight
that never started tracking leaves that tracker available for a valid later call.

## Recorded controls

The machine-readable companion `LPBF_PUBLIC_RUN_PROGRESS_2026-10-02.json` records
the exact source identity, code commit, current checks and two real worker errors.
The large fixed-event refinement experiment was not rerun.

- A small real 230-step solve compares saved pre-package `run/transient` source,
  with tracking disabled, against the final tracked Reference and Automatic
  paths. Numerical dependencies are the current unchanged production functions;
  it is not a reconstruction of the historical runtime environment. Final
  coordinates, temperature, enthalpy, density, accepted dt, clocks, metrics,
  physical audits, thermal history and settings match exactly.
- Automatic still requests `auto` while the existing execution settings resolve
  to `reference`, including when OpenFOAM capability is advertised.
- Separate Reference and Automatic worker children fail at the same boiling
  validity stop: 132 accepted steps / 3.19345553 microseconds last accepted time,
  266 source evaluations / 133 retries / 42,560 source cell-evaluations. Their
  output matches exactly, exit code is 1 and neither publishes a result.
- Four injected public downstream failures retain the same exception and CPU
  counters. Other fixtures cover publication failure, budgets, callback errors,
  single-use, preflight reuse, tracked and untracked nested calls, context reset,
  and unsupported OpenFOAM dispatch with its existing call signature.

These checks establish software behavior and numerical preservation for the
bounded case. They do not establish moving-source convergence, physical LPBF
accuracy, experimental validation, backend qualification or release acceptance.

## Final revision

- Local code commit: `3498da5a21168b4f74dda2c5c462ff78a0f6663e`; no push.
- Canonical source identity: `4cf24334a711ecf6fd41597cb087726580c0ed85b52ece72e0f15b89f6802e35`.
- Record SHA-256: `ed4759668a777ed117d9b52a9463d2f163851d6be1a21fc75ca87d67863cc5c1`.
- Final combined controls: **186 PASS / 2 SKIP / 0 FAIL**, 188 tests in 113.621 s.
  Skips are the Linux-only OpenFOAM oracle and Windows symlink privilege check.
  The 14 new public-run tests and 5 new worker tests all passed. Python
  compilation passed; no frontend code changed in this package.
- Committed and working production manifests yield the same canonical identity.
  Six frozen refinement/source-record artifacts remain byte-identical to the
  package's starting commit. Main graph refresh is still blocked by an existing
  denied temporary directory; the six owned source files have an isolated,
  byte-exact refresh with 146 nodes, 390 edges and 6 cards.
