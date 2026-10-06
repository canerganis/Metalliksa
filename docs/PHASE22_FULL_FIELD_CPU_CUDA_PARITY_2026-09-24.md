# Phase 22 full-field CPU/CUDA parity — 2026-09-24

## Frozen case and method

The focused test `python/test_lpbf_phase22_full_field_cuda_parity.py` uses the
same five-step, 5×5×5, 10 µm, 25 W stationary path as the prior scalar smoke.
It runs the production `TransientEnthalpy3DGPU.solve_toolpath` on CPU and
explicit RTX 4060 Laptop `cuda:0`. Before this observation, tolerances were
fixed at: temperature max absolute difference ≤0.05 K, enthalpy relative L2
≤2e-5, combined velocity-component max absolute difference ≤1e-5 m/s,
pressure relative L2 ≤2e-5, and surface max absolute difference ≤5e-8 m.
Relative L2 is `||CPU-GPU||₂ / max(||CPU||₂, 1e-30)` for each stored field.

The solver's new `include_diagnostic_fields` option is opt-in, leaves the
default result schema unchanged, and rejects grids above 100,000 cells. It
returns final T, H, U/V/W, pressure, and surface-height arrays for local
diagnostic callers; the worker does not enable it.

## Results

| Field | Maximum absolute difference | Relative L2 | Limit |
| --- | ---: | ---: | ---: |
| Temperature (K) | 2.44140625e-4 | 2.17847518e-8 | max abs ≤0.05 K |
| Enthalpy (J/m³) | 1024 | 1.96030996e-8 | rel L2 ≤2e-5 |
| Velocity X (m/s) | 4.29153442e-6 | 1.11043744e-6 | combined max abs ≤1e-5 m/s |
| Velocity Y (m/s) | 1.66893005e-6 | 5.83230246e-7 | combined max abs ≤1e-5 m/s |
| Velocity Z (m/s) | 1.78813934e-6 | 6.31768387e-7 | combined max abs ≤1e-5 m/s |
| Pressure (Pa) | 0.25 | 6.92049923e-7 | rel L2 ≤2e-5 |
| Surface height (m) | 0 | 0 | max abs ≤5e-8 m |

The focused test ran **3/3 PASS**, including default-schema and oversized-grid
guard checks. This establishes close final-field software parity for one small
case. It does not establish energy closure: the solver does not accumulate an
auditable source/convection/radiation/evaporation ledger, so the case's total
energy residual is unavailable. It also does not establish independent
analytical correctness, mesh/time convergence, broad backend equivalence,
performance, or experimental validation. Phase 22 surface stress/recoil laws
remain heuristic.
