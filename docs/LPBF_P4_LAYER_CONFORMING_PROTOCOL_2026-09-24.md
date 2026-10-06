# P4 layer-conforming mesh campaign protocol — 2026-09-24

## Scope

This is a separate numerical campaign for the one-layer, 80 W IN718 powder-bed
case. It asks whether the existing whole-cell stationary-grid solver shows a
credible mesh trend when every mesh face coincides with both the substrate
interface (`z = 0`) and the active layer top (`z = 80 µm`). It does not amend or
replace the frozen P4 report, whose status remains `failed`, and it is not
experimental validation. The solver, process conditions, material revision,
and acceptance thresholds are unchanged; only the preregistered resolution
vector is new.

## Frozen process and model

The complete explicit process vector is in
[`LPBF_P4_LAYER_CONFORMING_SCENARIO_2026-09-24.json`](LPBF_P4_LAYER_CONFORMING_SCENARIO_2026-09-24.json).
It fixes standard/reference CPU execution, IN718, 80 W, 1200 mm/s, 80 µm
beam diameter and layer, one 200 µm track, and the same cooling/dwell and
material defaults recorded in that file. Model scope is
`stationary-enthalpy-conduction-v1`, solver `enthalpy-fv-6`, and the registered
IN718 material revision emitted in each run. The frozen scenario file SHA-256
is `1031ad8708e010d84c40ccfd171f09a72ce7bf715b501559aa500adf2c49b326`.

## Preregistered resolution vectors

The convergence harness takes requested maximum mesh sizes. The fixed geometry
span is 440 µm. The following values produce the listed actual cubic cell sizes
and cell counts under `calculate_mesh_domain`; the actual values, not the
requests, govern all comparisons:

| Axis | Requested levels | Expected actual `dx` | Expected `nx × ny × nz` |
|---|---:|---:|---:|
| Mesh | 40.0, 20.0, 13.334 µm | 40.0, 20.0, 13.333333… µm | 11³, 22²×19, 33²×29 |
| Timestep | 4e-7, 2e-7, 1e-7 s | Actual accepted mean `dt` is recorded | Fixed at requested 13.334 µm (actual 13.333333… µm) |

Each mesh satisfies `80 µm / dx ∈ integers` and `substrate_depth / dx ∈
integers`, so the powder/baseplate interface and layer top lie on cell faces.
Before the campaign, a domain-only calculation gave minimum Gaussian
half-space capture `0.999999999013` across 11 evenly spaced beam positions from
−100 to +100 µm for each level. This is a preflight calculation, not a solver
result. Every actual source interval must still pass the existing shared 99%
capture guard; no validity threshold is changed.

## Frozen acceptance

The campaign uses the existing `lpbf_convergence_study.ACCEPTANCE` unchanged:

- At least three strictly descending, completed levels for each independent
  axis, evaluated using actual `dx` or actual mean `dt`.
- Every run has relative energy-balance error ≤1% and the same model, solver,
  backend, material identity, and material revision.
- Width and depth each have ≤5% relative change across the finest pair and a
  `numerically-converging` trend from `lpbf_verification.convergence` over the
  three finest actual spacings.
- Any failed source-capture guard or solver run remains a visible failure; no
  failed case is dropped and no threshold is adjusted after results.

## Interpretation boundary

The campaign is a companion result about grid-conforming resolutions for the
existing one-layer model. It cannot retroactively turn the original frozen P4
result into a pass. It does not resolve general multi-layer cut-cell geometry;
intermediate layer faces can still fall between cell faces when `layer_um/dx`
is nonintegral. It does not validate the heat-transfer model against an
experiment.
