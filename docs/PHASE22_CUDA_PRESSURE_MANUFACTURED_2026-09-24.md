# Phase 22 CUDA manufactured pressure solution — 2026-09-24

The focused test `python/test_lpbf_phase22_cuda_manufactured_pressure.py`
checks the actual device-side PCG solve on RTX 4060 `cuda:0` against an
independently assembled host finite-volume operator.

## Manufactured case

- Grid: 9×9×9; spacing 20 µm on each axis; liquid density 4420 kg/m³;
  `dt=2e-7 s`.
- All interior cells are liquid. Side and bottom boundaries are closed
  zero-normal-gradient faces; the top neighbor above the height graph is air
  with zero gauge pressure.
- The exact discrete pressure is `p[i,j,k]=i²+2j²+3k²`, mean-centered over
  active cells. The manufactured right-hand side is formed independently as
  `Div=-(dt/rho) A p`, with `A=-D(G)` assembled from the stated face rules.
- CPU/CUDA-independent acceptance: converged status, linear residual,
  gauge-adjusted pressure relative L2 error, and independently recomputed
  operator residual each ≤`1e-3`.

## Result

The explicit CUDA PCG solve converged and passed **1/1**. Measured relative
linear residual was `7.4851e-4`; gauge-adjusted pressure relative L2 error was
`2.9145e-4`; independent operator residual was `7.4854e-4`.

This verifies the discrete pressure solver on one manufactured domain. It
does not validate the Phase 22 constitutive surface-force laws, thermal energy
closure, full workload performance, mesh convergence, or experiment agreement.
