# Frozen 80 W P4 peak-selection diagnostic replay — 2026-09-24

## Scope and provenance

This is a forensic diagnostic for the existing frozen report
[`LPBF_CPU_CONVERGENCE_80W_2026-09-24.json`](LPBF_CPU_CONVERGENCE_80W_2026-09-24.json).
It does not change that report, its acceptance limits, or its `failed` status.
The replay used an isolated checkout at `5dae4c9436e9f9b09820ec170bfa3acf1ee9b7d5`
and the exact requested process vector and mesh/time levels from the frozen
report. All six canonical input hashes matched the stored hashes. Every
replayed actual mesh, mean timestep, step count, W, D, peak temperature, and
energy error had zero numerical delta from the frozen row.

The replay is **not an exact implementation replay**: all six provenance
`implementationHash` values differed, and fingerprinting the frozen inputs at
the report commit `ec6b0a5` also failed to reproduce the stored hashes. The hash
covers every `python/*.py` file and the validated inputs, so the exact
report-time source tree has not yet been identified. A Git-blob scan over 69
commits from the P4 harness through the new capture gate found no matching
implementation hash; the original run likely used a dirty/uncommitted or
unrecorded Python tree. The diff from `ec6b0a5` to diagnostic commit `5dae4c9`
changes the peak tracker only to add equal-peak
counters, adds their serialization, and updates a descriptive section label;
the thermal update, material registry, source integration, and verification
operator are unchanged. Those counters do not change peak winner selection.
Thus the replay is a matched-input diagnostic on the same numerical solver
path, not retroactive validation of the original implementation. The replay
commit predates the current 99% minimum source-capture guard; the coarse case
captures 86.763% and is rejected by today's guard. No guard was relaxed in the
main checkout.

## Replay results

Mesh study (fixed requested maximum timestep `1e-7 s`; each run used 1,867
steps):

| Requested mesh (µm) | Actual mesh (µm) | W × D (µm) | Peak step | Equal-maximum endpoints | Equal-maximum time window (µs) |
|---:|---:|---:|---:|---:|---:|
| 36.7 | 36.6667 | 73.3333 × 43.3333 | 1,429 | 439 | 142.900–186.667 |
| 24.45 | 24.4444 | 48.8889 × 55.5556 | 1,568 | 300 | 156.800–186.667 |
| 16.3 | 16.2963 | 48.8889 × 47.4074 | 1,706 | 25 | 170.567–172.967 |

Timestep study (fixed requested mesh `16.3 µm`):

| Requested max dt (s) | Actual mean dt (µs) | Steps | W × D (µm) | Peak step | Equal-maximum endpoints | Equal-maximum time window (µs) |
|---:|---:|---:|---:|---:|---:|---:|
| 4e-7 | 0.368179 | 507 | 48.8889 × 47.4074 | 467 | 6 | 170.667–172.667 |
| 2e-7 | 0.199857 | 934 | 48.8889 × 47.4074 | 854 | 12 | 170.667–172.867 |
| 1e-7 | 0.0999821 | 1,867 | 48.8889 × 47.4074 | 1,706 | 25 | 170.567–172.967 |

## Interpretation and boundary

The mesh replay shows broad equal-maximum plateaus on the two coarser meshes;
the fine-mesh plateau is much shorter. For the timestep sequence, the W/D
values remain identical while denser sampling increases the number of tied
endpoints across a similar approximately 2.2 µs interval. Peak-selection
plateaus are therefore a plausible sensitivity of the discrete extraction,
but these diagnostics do not prove they caused the failed mesh-depth trend.

Frozen P4 stays `failed`: the 80 W depth finest-pair change is 17.1875%, the
width trend is inconclusive, and timestep geometry is inconclusive. The separate
75 W contour study remains `inconclusive`. Neither result is experimental
validation. Do not reuse the completed 75 W vectors or alter existing criteria;
any new 80 W campaign must freeze its process, model, operator, resolution
vectors, and acceptance rules prospectively.
