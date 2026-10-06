# Phase 22 CPU/CUDA multistep smoke — 2026-09-24

## Frozen case and acceptance limits

The case and limits were fixed in
[`python/test_lpbf_phase22_multistep_cuda_parity.py`](../python/test_lpbf_phase22_multistep_cuda_parity.py)
before the paired CPU/CUDA observation:

- Production `TransientEnthalpy3DGPU.solve_toolpath`, mesh `5×5×5`, spacing
  `10 µm`, duration `6 µs` (5 solver steps), stationary centered path,
  `25 W`, initial temperature `1700 K`.
- Both runs use the same solver defaults and inputs. The CPU run explicitly
  selects `cpu`; the GPU run explicitly selects `cuda:0`.
- Frozen CPU/CUDA limits: peak temperature difference `≤0.05 K`, maximum
  velocity relative difference `≤0.2%`, surface recession difference
  `≤0.05 µm`, relative PCG residual difference `≤2e-5`, and post-projection
  relative-divergence difference `≤2e-5`. Melt volume must match exactly.
- Each run must report five steps, a converged projection, positive PCG
  iterations, nonzero velocity, temperature rise, and nonzero melt volume.

## Observed run

Runtime: Warp `1.17.0`, CUDA Toolkit `12.9`, Driver `13.4`; explicit `cuda:0`
was an NVIDIA GeForce RTX 4060 Laptop GPU (`sm_89`, 8 GiB). CPU was AMD64
Family 25 Model 116 Stepping 1, AuthenticAMD.

| Metric | CPU | CUDA `cuda:0` |
| --- | ---: | ---: |
| Steps | 5 | 5 |
| Projection status | converged | converged |
| PCG max iterations per step | 5 | 5 |
| PCG total iterations | 8 | 8 |
| Relative linear residual | 6.524981369889448e-8 | 4.0668905774454146e-8 |
| Post-projection relative-divergence L2 | 7.344502397672945e-8 | 1.0328636406027447e-7 |
| Maximum post-projection divergence (s⁻¹) | 0.078125 | 0.15625 |
| Peak temperature (K) | 2533.489990234375 | 2533.489990234375 |
| Maximum velocity (m/s) | 3.815609931945801 | 3.815610408782959 |
| Surface recession (µm) | 1.2691725492477417 | 1.2691725492477417 |
| Melt volume (µm³) | 5000.000000000002 | 5000.000000000002 |

All frozen assertions passed in the targeted test. The unequal maximum absolute
divergence values are retained above; the frozen residual comparison uses the
relative-divergence L2 and both runs independently report projection
convergence.

## Evidence limits

This is one small deterministic software-parity smoke, not broad GPU
equivalence, mesh/time convergence, independent analytic verification, or
experimental validation. The production result exposes scalar summaries but
does not expose complete temperature/velocity fields or an energy ledger, so
this run cannot establish full-field parity or energy closure. The configured
laser command is `25 W × 6 µs`; it is not an absorbed-energy measurement. The
solver's legacy free-surface stress/recoil rules are explicitly heuristic, so
the nonzero velocity and melt geometry are not validation of those physical
laws. Runtime measurements are not used for a performance claim.
