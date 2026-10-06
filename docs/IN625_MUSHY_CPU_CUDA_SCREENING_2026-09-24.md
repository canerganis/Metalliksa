# IN625 mushy-range CPU/CUDA screening witness — 2026-09-24

## Scope and selection history

This is a small, synthetic numerical witness for the bounded IN625 bare-plate
model. The initial temperature is intentionally set near the solidus so the
test can exercise the mushy enthalpy law at low cost. It is not a representative
LPBF preheat, process simulation, source qualification, or experimental
validation. The case was selected after CPU-only parameter exploration; the
paired CPU/CUDA run and acceptance tolerances are implementation checks, not a
blind or preregistered scientific study.

The configured material revision is
`f47b07e4c8288b8c7177001f069a254be3410bace43ad5ea2f73168ac4466f07`, with
solidus 1563.15 K, liquidus 1623.15 K, and status
`unvalidated-literature-model-screening`.

## Frozen test vector and numerical checks

- Grid: 8 × 8 × 2 cell-centred cells (128 total), each side 250 µm; domain
  2 mm × 2 mm × 0.5 mm.
- Initial temperature: 1500 K; stationary Gaussian surface source centred at
  (1 mm, 1 mm), sigma 300 µm; explicit absorbed power 30 W.
- Time step: `1e-4 s`, 33 steps, total absorbed energy 0.099 J.
- All six boundaries are adiabatic. The source-capture minimum is
  `0.9982844950`, above the `1/1.01` gate.
- Acceptance: at least one cell enters the open solidus–liquidus interval and
  no cell reaches liquidus; CPU and explicit `cuda:0` agree within 2e-10 K for
  temperature, 2e-7 J/kg for enthalpy, and 2e-10 J for the ledger; a separate
  64-point Gauss–Legendre Cp integral agrees with the full enthalpy field; the
  independently summed total enthalpy closes against initial H plus absorbed
  energy to relative error below 1e-9.

The focused `python/test_in625_bareplate_field.py` suite passes **11/11** on
the RTX 4060 host, including both phase-crossing backend cases. On the 128-cell
grid, CPU and GPU reached 1565.4608746 K and 4 mushy cells; maximum absolute
field differences were 4.55e-13 K and 2.33e-10 J/kg. On the refined grid, both
reached 1577.3396719 K and 32 mushy cells; maximum differences were 9.09e-13 K
and 3.49e-10 J/kg. Both grid levels had CPU and CUDA ledger residual maxima of
5.33e-15 J. The 64-point enthalpy and independent integrated-energy oracles
passed at both resolutions.

## Two-resolution profile and limitations

Both resolutions use the same 2 mm × 2 mm × 0.5 mm domain, 3.3 ms duration,
0.099 J input, source location/profile/power, initial temperature and adiabatic
boundaries. Only mesh and stable timestep were refined. Each row is one
CPU/CUDA wall-clock measurement, not a benchmark campaign:

| Grid | Steps × Δt | CPU | RTX 4060 `cuda:0` | Incremental peak allocation | CUDA/CPU |
| --- | ---: | ---: | ---: | ---: | ---: |
| 128 cells (8×8×2) | 33 × 1e-4 s | 0.289 s | 9.196 s | 24,576 B | 31.8× slower |
| 1,024 cells (16×16×4) | 132 × 2.5e-5 s | 1.316 s | 23.254 s | 176,128 B | 17.7× slower |

Allocated-memory peaks are deltas above the initialized context baseline; they
exclude CUDA context and pre-existing allocations. The measured CUDA path is
slower at both tested sizes, so no GPU speedup or crossover is claimed.

This closes the field-level phase-range coverage gap for the *implemented
screening law*. It does not close the IN625 source/uncertainty gate or qualify
IN625 for the general transient solver, build-job, powder bed, melt flow, or
production use. P6 remains partial and P7 remains partial.
