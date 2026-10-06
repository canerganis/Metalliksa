# P4 peak-selection diagnostic protocol

Protocol ID: `p4-peak-selection-diagnostic-v1`
Registered before the diagnostic rerun. This is a repeat of the existing 75 W
numerical case to expose peak-selection metadata that the first report omitted;
it is not an independent acceptance study and cannot replace or upgrade that
report.

## Fixed inputs and runs

Use the exact scenario in `docs/LPBF_P4_CONTOUR_SCENARIO_75W_2026-09-24.json`
and the same solver, material revision, and six requested resolutions from
`docs/LPBF_P4_CONTOUR_PROTOCOL_2026-09-24.md`:

- Mesh: 20, 10, and 5 µm at maximum timestep 5e-8 s.
- Timestep: 1e-7, 5e-8, and 2.5e-8 s at mesh 10 µm.

## Diagnostic fields

Retain the existing `accepted-step-molten-volume-v1` operator and earliest-step
tie behavior. For each run, record the selected peak step/time, molten-cell
count and volume, number of endpoints tied at the maximum count, and first/last
times at that count. The selected field and its contour remain the same output
used by the prior protocol. These fields diagnose whether mesh or timestep
refinement changes the selected accepted endpoint or leaves a long equal-volume
plateau; they do not define a new acceptance metric.

The cell-center contour continues to linearly interpolate liquidus crossings
between neighboring active cells without surface extrapolation. The existing
global projected width/depth is a numerical thermal proxy, not a cross-section
measurement operator. No optical-surface crossing, alternative temporal
aggregation, or NIST comparison is inferred by this diagnostic.

## Acceptance and interpretation

The original energy, finest-pair W/D, and three-level monotonic convergence
criteria are unchanged. The repeated report must retain both its discrete and
contour statuses; ties or stable geometry do not turn an inconclusive gate into
PASS. No thresholds may be adjusted after observing results. The diagnostic
only answers whether selected peak endpoints/tie windows vary across the
declared resolutions. Experimental validity remains false.
