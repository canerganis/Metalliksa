# Current-model IN718 CPU refinement protocol — 40 W

Protocol ID: `lpbf-p4-current-layer-conforming-40w-2026-09-25-v1`
Scenario: `docs/LPBF_P4_CURRENT_MODEL_40W_SCENARIO_2026-09-25.json`
Report: `docs/LPBF_P4_CURRENT_MODEL_40W_2026-09-25.json`

## Purpose and separation

This is a new, supplementary numerical study for the current production CPU
model. It does not replace, combine with, or relabel any previous frozen P4
result. The unarchived 6.6667 µm diagnostic is excluded because its complete
resolved input, model identity, and material revision were not saved. Any old
40/20/10 µm values remain historical context only until their exact run
identities are established.

The study assesses numerical refinement for the explicitly configured
`standard/reference` IN718 powder-layer case only. It cannot establish
experimental validity, alloy-law accuracy, or production readiness.

## Frozen scenario

The complete raw scenario and both refinement axes are frozen in the companion
JSON before execution. It specifies 40 W, 800 mm/s, 80 µm 1/e² beam diameter,
80 °C preheat, one 200 µm track, one 40 µm powder layer, 0.1 ms cooling, no
dwell, explicit CPU reference backend, and the `layer-conforming` grid policy.
Other solver settings are explicitly written in that JSON. Validation and
each run's result must record the resolved CPU solver, current model ID,
material ID and revision, input hash, execution-input hash, and implementation
hash.

## Refinement matrix

- Mesh axis: requested 20, 10, and 5 µm; fixed maximum time step 25 ns.
- Time axis: maximum steps 100, 50, and 25 ns; fixed requested mesh 5 µm.
- The existing `lpbf_contour_convergence_study` executor reports both the
  frozen discrete cell-extent observables and the separate predeclared linear
  liquidus-contour observables. Neither operator may be swapped into the
  other's acceptance gate after seeing results.
- A preflight with `calculate_mesh_domain` resolved 20/10/5 µm to exactly
  20/10/5 µm and 8,228/65,824/526,592 cells. The finest level is below the
  production CPU solver's 600,000-cell guard. The host reported 9.56 GiB
  available physical memory at preflight; stop before a run if current memory
  pressure materially reduces this headroom.

## Acceptance

Use the existing frozen numerical limits: relative energy closure at most
0.01, at least three strictly refining actual levels, a finest-pair relative
change no greater than 5% in both width and depth, and the existing
`lpbf_verification.convergence` trend check on actual spacings. Model ID,
solver ID, backend, alloy ID, and material-revision hash must match across each
axis. Source-capture gates remain unchanged. A failed or inconclusive outcome
is reported as such; no thresholds or metrics will be changed after execution.

The primary report status comes from the discrete cell-extent gate. The
contour-specific status is reported separately and remains a numerical thermal
proxy only. Experimental comparison and validation are outside this protocol.

## Provenance at freeze

- Current code commit: `e906568` (`Verify analytic LPBF melt contours`).
- Companion JSON SHA-256 at freeze: `2abec47f9d35c02158ea2e06876e3ca06c3ba5ba9243f1ddccaa94ef64752ea6`.
- At execution preflight the material resolved to `in718` / `lpbf-materials-1`
  and available physical memory was 9.71 GiB.
- Freeze time: 2026-09-25, before the six solver runs.
