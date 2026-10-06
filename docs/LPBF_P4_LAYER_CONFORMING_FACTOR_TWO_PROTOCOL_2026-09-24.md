# P4 factor-two layer-conforming campaign protocol — 2026-09-24

## Scope and relation to prior evidence

This is a second, separately frozen companion campaign for the one-layer 80 W
IN718 powder-bed case. It uses the same process and solver as the frozen P4
report, but a distinct grid-conforming resolution vector: every mesh actual
spacing divides both the 80 µm layer and substrate depth, and every requested
refinement ratio is two. The first layer-conforming companion remains a
separate failed/inconclusive result because its actual ratios did not satisfy
the solver's fixed-ratio trend oracle. Neither companion changes the original
frozen P4 result or its criteria.

The fixed process vector is in
[`LPBF_P4_LAYER_CONFORMING_FACTOR_TWO_SCENARIO_2026-09-24.json`](LPBF_P4_LAYER_CONFORMING_FACTOR_TWO_SCENARIO_2026-09-24.json).
The scenario file SHA-256 is
`73a12be7edc393986b9772f1bcef1ba50f9394e19c60dc32d409287f1dd5219a`.

## Preregistered levels and geometry

The 440 µm in-plane span gives exact actual mesh spacings from requested
maximum sizes 40, 20 and 10 µm. These form a constant ratio of two and align
the substrate interface and 80 µm layer top to cell faces:

| Axis | Requested levels | Expected actual levels | Expected cells |
|---|---:|---:|---:|
| Mesh | 40, 20, 10 µm | 40, 20, 10 µm | 11×11×10, 22×22×19, 44×44×38 |
| Timestep | 1e-7, 5e-8, 2.5e-8 s | Use the accepted actual mean `dt` | Fixed at 10 µm actual mesh |

Before running the solver, the domain-only check found minimum half-space
Gaussian capture `0.999999999013` across 11 equally spaced source locations
from −100 to +100 µm at all three mesh levels. It also confirmed exact surface
alignment. These are geometric preflight results only. Every solver source
interval must pass the existing 99% capture guard; no validity limit is
changed.

## Frozen acceptance

Use `lpbf_convergence_study.ACCEPTANCE` unchanged. Each axis must have three
completed, strictly descending levels and a constant refinement ratio in its
actual spacings; each run must have energy error ≤1%; width and depth must each
change by ≤5% over the finest pair and satisfy the existing numerical trend
oracle over the three actual levels. All runs must share the exact model,
solver, backend, material identity and material revision. Failed and
inconclusive outcomes stay visible; no case is dropped or criterion adjusted.

The timestep requests are set below the preceding pilot's observed
stability-limited first level so all three can be resolved by the solver. The
accepted actual mean timesteps remain authoritative. If their ratios are not
constant within the existing oracle, the axis remains inconclusive; do not
retune this campaign after seeing its metrics.

## Interpretation boundary

This companion tests numerical behavior for this one-layer case on a
surface-conforming geometric sequence. It does not repair general multi-layer
cut-cell geometry, does not supersede any prior report, and is not experimental
validation.
