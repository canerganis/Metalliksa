# Phase 22 manufactured thermal oracle — 2026-09-24

## Purpose and method

This check supplies an independent analytical temperature-field and total-energy
oracle for the production `enthalpy_3d_nonlinear_step_kernel`. It is separate
from CPU/GPU parity and from the Phase 22 energy ledger. The run sets laser power,
velocity, convection, radiation and evaporation to zero; uses fixed properties
(`rho=4420 kg/m³`, `cp=670 J/(kg K)`, `k=15 W/(m K)`); and holds all six domain
faces at `300 K`. No latent-heat transition is reached.

On a cubic domain of side `L=1.6 mm`, the initial field is

`T(x,y,z,0) = 300 K + 10 K sin(pi x/L) sin(pi y/L) sin(pi z/L)`.

The exact solution is the Dirichlet diffusion eigenmode

`T = 300 K + 10 K product_i sin(pi x_i/L) exp(-3 alpha pi² t/L²)`,
where `alpha=k/(rho cp)`. Expected total-energy change is calculated directly
from that exact field as `rho cp integral(T_exact(t)-T_initial) dV`; it does not
read the solver ledger.

The explicit-Euler Fourier number is bounded by 0.1. CPU meshes use 9³, 17³,
and 33³ nodes to check refinement; RTX 4060 `cuda:0` uses 33³. The final time is
4 ms.

## Results

| Device / nodes | Steps | Relative temperature L2 error | Relative exact-energy-change error |
|---|---:|---:|---:|
| CPU / 9³ | 6 | 1.5814e-3 | 6.0033e-3 |
| CPU / 17³ | 21 | 5.5712e-4 | 2.1197e-3 |
| CPU / 33³ | 82 | 1.4679e-4 | 5.5784e-4 |
| RTX 4060 `cuda:0` / 33³ | 82 | 1.4677e-4 | 5.5771e-4 |

Both error sequences decrease monotonically; finest/coarsest ratios are 0.0928
for the field and 0.0930 for energy. The focused test passes **2/2** on the
host, including explicit CUDA execution. The regression is
`python/test_lpbf_phase22_manufactured_thermal.py`.

## Scope

This verifies a fixed-property, no-phase-change, source-free conduction operator
against one closed-form 3D field and its independently integrated energy change.
It does not validate variable material properties, phase-change coupling,
free-surface loss laws, flow, the complete multi-physics solver, IN718
experiments or production-scale GPU performance. P6 remains partial because its
other frozen prerequisites and the overall numerical acceptance gates remain
open.
