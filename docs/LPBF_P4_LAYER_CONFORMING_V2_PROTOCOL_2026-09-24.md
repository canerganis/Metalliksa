# P4 layer-conforming v2 companion protocol — 2026-09-24

## Scope and relation to prior evidence

This is a separately frozen numerical companion for the one-layer 80 W IN718
powder-bed case. It exercises the opt-in whole-cell `layer-conforming` grid
policy introduced in code commit `a752cf8` and the distinct model identity
`stationary-enthalpy-conduction-layer-conforming-v1`. It does not modify or
supersede the original frozen P4 campaign, the first layer-conforming
companion, or the factor-two layer-conforming companion. Their outcomes and
acceptance criteria remain unchanged.

The fixed process vector is in
[`LPBF_P4_LAYER_CONFORMING_V2_SCENARIO_2026-09-24.json`](LPBF_P4_LAYER_CONFORMING_V2_SCENARIO_2026-09-24.json).
Its SHA-256 is
`80c3d4e1c58e28559914ff3a02fc6edc762b8ffe21336466f60b2826fe388ecc`.
The scenario explicitly requests standard/reference CPU, one 80 µm layer,
`surfaceMode=powder-layer`, and `powderGridPolicy=layer-conforming`.

## Preregistered levels and domain preflight

The mesh axis requests maximum cell sizes 36.7, 13.34, and 6.667 µm, with
fixed `maxDt_s=2.5e-8`. The layer-conforming policy is expected to produce
actual cell widths 26.6666667, 13.3333333, and 6.6666667 µm, respectively,
forming a factor-two sequence within floating-point tolerance. Expected cell
shapes are 17×17×15, 33×33×29, and 66×66×57. The corresponding centered
in-plane spans are 453.333333, 440, and 440 µm; substrate depths are
320, 306.666667, and 300 µm. The z=0 substrate/powder interface and the
80 µm powder-layer top are cell faces at every level. Actual solver-reported
spacing and shape are authoritative.

The timestep axis requests 1e-7, 5e-8, and 2.5e-8 s at fixed requested mesh
size 6.667 µm. Stability-limited actual mean timesteps are authoritative and
must satisfy the existing actual-spacing trend check; no timestep result may
be retuned after observing metrics.

The geometry-only preflight for the frozen mesh vector verified the layer
surface alignment, no coarser-than-requested actual spacing, in-plane padding
of less than one cell, and sampled Gaussian source capture of at least 99%
over 11 source positions. This is a geometric guard preflight only; it is not
a substitute for each solver interval's existing 99% source-capture guard.

## Frozen acceptance

Use `lpbf_convergence_study.ACCEPTANCE` unchanged: three completed,
strictly descending levels per axis; constant refinement ratio in actual
spacings as evaluated by the existing trend oracle; energy relative error at
most 1%; and width and depth each changing by at most 5% over the finest pair
while satisfying `lpbf_verification.convergence` on the actual levels. All
runs must retain identical model ID, solver, backend, material identity, and
material revision. The layer-conforming model identity must be present on all
runs. Preserve failed and inconclusive outcomes; do not drop runs, relax a
guard, or adjust a criterion.

The scenario SHA-256, requested vectors, policy, and acceptance criteria are
frozen before solver outputs are generated. If any expected geometry or
actual-ratio condition is not met, report the observed result under this
protocol; do not replace levels after seeing metrics.

## Interpretation boundary

This campaign tests numerical behavior for this one-layer process vector with
whole-cell layer-surface alignment. It does not establish arbitrary
multi-layer/cut-cell correctness, GPU parity or performance, or experimental
validity. It is independent numerical evidence only and cannot convert any
earlier failed or inconclusive P4 result into a pass.
