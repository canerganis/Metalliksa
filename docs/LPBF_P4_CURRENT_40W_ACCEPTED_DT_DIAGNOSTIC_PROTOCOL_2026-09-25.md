# P4 40 W accepted time-step distribution diagnostic

Protocol ID: `lpbf-p4-current-40w-accepted-dt-diagnostic-v1`
Scenario: `docs/LPBF_P4_CURRENT_MODEL_40W_SCENARIO_2026-09-25.json`
Prior frozen protocol: `docs/LPBF_P4_CURRENT_MODEL_40W_PROTOCOL_2026-09-25.md`
Output: `docs/LPBF_P4_CURRENT_40W_ACCEPTED_DT_DIAGNOSTIC_2026-09-25.json`

## Scope

Repeat only the frozen temporal refinement axis to record the accepted-step
distribution added to the current CPU reference solver diagnostics. This is a
supplementary numerical diagnostic. It does not replace or mutate the original
six-run P4 report, its mesh results, its thresholds, or its acceptance status.
It is not an experimental comparison or validation.

## Frozen inputs

Use the scenario JSON bytes unchanged (SHA-256
`2abec47f9d35c02158ea2e06876e3ca06c3ba5ba9243f1ddccaa94ef64752ea6`), fixed
requested mesh 5 µm, and the already frozen maximum time steps 100, 50, and
25 ns, coarse to fine. Run the explicit `standard/reference` CPU scenario and
record solver/model/material identities and provenance from every result.

## Recorded diagnostics

Preserve the accepted-timestep summary returned by each solver run, including
count, total, mean, percentiles, minimum/maximum, `sum(dt^2)/T`, fraction of
steps at the requested cap, source-limited step count, and source retries.
Report these observed values without defining a new pass threshold. Apply the
existing frozen temporal acceptance only as already specified by the original
protocol; if actual levels do not meet it, retain `failed` or `inconclusive`.

## Execution integrity

Write a distinct partial record before execution and after each completed
level. Preserve completed rows if a later level fails. The final report must
record the protocol/scenario hashes, execution HEAD, all three row identities,
and `experimentalValidation=false`. Do not overwrite the original P4 report
or the pre-existing historical partial record.
