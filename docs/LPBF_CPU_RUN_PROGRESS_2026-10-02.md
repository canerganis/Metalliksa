# CPU run progress and source-work accounting

## Supported scope

An additive, opt-in `CpuRunProgress` tracks Standard / Reference / single CPU
solves, including the existing bare-plate case. Layered-plate, studies,
OpenFOAM, Torch and Warp executions are outside this contract. The worker
enables it only for explicit Reference inputs; Automatic dispatch is unchanged.

```python
from lpbf_run_progress import CpuRunProgress
from lpbf_simulation import run

progress = CpuRunProgress(maximum_source_evaluations=1000,
                          maximum_source_cell_steps=100_000_000)
try:
    result = run(inputs, run_progress=progress)
except Exception as error:
    diagnostics = getattr(error, "progress", None)
```

Instances are single-use. Snapshots are copied metadata, not recoverable fields
or completed results. The worker reports the last valid thermal state on failure.
It also retains work counts if result processing fails after thermal stepping.
Direct `run()` callers can inspect their tracker when downstream processing fails;
the exception attachment is guaranteed by the CPU transient scope, not every
dispatcher or output operation.

## Count semantics

- An accepted step passes source capture and candidate enthalpy/temperature
  validity before its time and counters are committed. Callback failure after
  this point retains that accepted step.
- `lastAcceptedTime_s` is the raw cumulative accepted clock;
  `lastAcceptedSchedulerTime_s` includes existing event roundoff handling.
- Source evaluations include every internal retry and an evaluation that raises.
  The source cell count is evaluations multiplied by the resolved cell count.
- Optional source-work limits reject the next evaluation before it starts.
  They exclude conduction, allocations and other solver work; they are not
  wall-clock, memory or operating-system kill limits. Worker defaults add no cap.
- The boiling/model-validity stop is retained. Rejected candidates do not become
  accepted steps, completed results or experimental observations.

## Verification at this revision

- Combined focused suite: **106 PASS / 1 Linux-only OpenFOAM SKIP / 0 FAIL**.
- A 230-step real CPU case matched the pre-change source exactly for final
  fields, accepted steps, thermal history, physical audits and metrics.
- A live worker child stopped at boiling after 132 accepted steps and reported
  266 source evaluations, 133 retries and 42,560 source cell-evaluations. No
  completed result was written.
- The implementation manifest now includes three previously omitted production
  helpers and the progress module; local static import closure is complete.

The final current-filesystem implementation fingerprint is
`a8c81340d03e221a8cb9cacbd2bc02ae48321c9498e3c6412e0ff47bc39eb3ef`.
Owned modified numerical sources use preserved LF bytes. Other legacy manifest
files retain their existing byte policy; whole-manifest cross-platform identity
has not been established. Historical reports retain their original identifiers.
