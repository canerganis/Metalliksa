# P4 current 40 W tied-peak diagnostic protocol

Protocol ID: `lpbf-p4-current-40w-tied-endpoint-diagnostic-v1`.
Prepared before the diagnostic execution. This is a post-study sensitivity
diagnostic only; it cannot change, replace, or upgrade the frozen P4 result.

## Frozen identity and scope

- Scenario: `docs/LPBF_P4_CURRENT_MODEL_40W_SCENARIO_2026-09-25.json`.
- Scenario SHA-256:
  `2abec47f9d35c02158ea2e06876e3ca06c3ba5ba9243f1ddccaa94ef64752ea6`.
- Execution commit: `15b4663373ba9700e2c9a8cb9b2169c1a83835b9`.
- Solver implementation SHA-256:
  `72520e2a25c5a6b781e2c7a0bb8c501deadfe2d6c15ce73e017bbd22e56459d3`.
- Model: CPU NumPy reference, `enthalpy-fv-6`, Inconel 718, layer-conforming
  powder grid. Change only requested mesh to 20, 10, and 5 µm; keep every other
  scenario input, including the 25 ns maximum step, fixed.
- Runner: `docs/diagnose_p4_tied_peak_endpoints.py`.

The existing accepted-step molten-cell-count operator and first-maximum
selection remain unchanged. For each mesh, capture every accepted time step
with the maximum molten-cell count and report its first/last time, endpoint
count, valid-contour count, and the width/depth min, median, and max from both
the production contour tracker and independent offline edge-crossing oracle.
Also retain the originally selected first-endpoint geometry, energy ledger,
mesh/cell/step counts, model/material identity, and run time.

## Interpretation

`acceptanceStatus` is fixed to `not-assessed`. No convergence thresholds,
temporal-selection rules, or frozen P4 results are changed. Agreement between
two implementations checks the contour calculation on the captured fields;
it does not validate the thermal equations against an experiment. A tie means
equal discretized molten-cell count only and is not evidence of a physically
steady melt pool. Contours remain numerical liquidus proxies without surface
extrapolation, melt flow, evaporation, recoil, or keyhole physics. Experimental
validation remains false.

## Output

Write `docs/LPBF_P4_CURRENT_40W_TIED_ENDPOINT_DIAGNOSTIC_2026-09-25.json` and
record the protocol SHA-256 and report SHA-256 in `STATUS.md` and
`docs/ACTIVE_WORK.md` after the run. A failed or unsupported oracle comparison
must remain visible; do not filter invalid endpoints to manufacture agreement.
