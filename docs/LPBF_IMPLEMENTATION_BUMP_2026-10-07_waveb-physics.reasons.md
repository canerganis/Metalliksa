# Wave B physics bump — drift reasons (ddd8358a… → f3ba9896…)

Companion to `LPBF_IMPLEMENTATION_BUMP_2026-10-07_waveb-physics.json`, the tool output of

`python -B tools/lpbf_bump_record.py --from-revision f84ccb39 --with-parity-check --slow --expect-drift <the 260 entries of ….expect-drift.txt>`

run at the re-pin commit `012c9900` (python tree clean, `worktreeDirty: false`) in the locked warp-less reference interpreter `.runtime/lpbf-win-py312` (CPython 3.12.10, NumPy 2.2.6, no `warp`). Result: **22 DRIFT, 3 PASS (g10, g13, npz_determinism), 0 FAIL**; `pinMatchesToHash: true`, `versionUnchanged: true`. Base: main `f84ccb39` (Wave A + Tier 2 merged, pin `ddd8358a…`). Plan: `WAVE_B_BUMP_PLAN.md` (maintainer-approved, lead decisions D1, D10, D11) and its five cluster plans. Lengths in µm, temperatures in °C unless stated.

The allowlist was derived from a full `--check --expect-unpinned --slow` of this tree, not copied from the plan: the plan's 189-key list was built from a run whose printed diff list is truncated after 40 lines per case (`... 51 more`), so it missed 51 G17-AlSi10Mg keys; this list has 260 exact keys.

## Deviation from the plan (LT-3 label location)

The plan put the LT-3 label in `numericalDiagnostics.solidificationResolution` and expected G2 `fixture.strippedResultEqual` True → False. The harness refuses both: `numericalDiagnostics` and `fixture.*` of the reference transient cases (G1/G2/G4) are numerics that never drift under `--expect-drift` (measured: `changed result.key.numericalDiagnostics: reference-case numerics never drift`). The label carries no numerics, so it is a **top-level result key `solidificationResolution`** instead, and the G2 fixture comparison drops exactly that one name when the fixture lacks it (guarded harness commit `c969b4ce`, for lead review). Consequences: `numericalDiagnostics` is bit-equal in every reference case, G2 `fixture.strippedResultEqual` stays **true**, and the reference-numerics refusal rules are unchanged.

## Causes

| id | cause | source | files |
|---|---|---|---|
| LT-1 | Warp Rosenthal slice index order `(tid // nb, tid % nb)`; opt-in only | internal consistency with `sample_thermal_slice` | `warp_thermal_solver.py` |
| LT-2 | Three-grid check: Celik unequal-ratio apparent order, r ≥ 1.3 gate, oscillation first, GCI on r21; mesh levels spread to r ≥ 1.3; timestep study refines below the realised mean step; protocol `…-v2-celik-ratio` | Celik, Ghia, Roache & Freitas 2008, J. Fluids Eng. 130:078001, Steps 2-3, Eq. 3/7 | `lpbf_verification.py`, `lpbf_simulation.py` |
| LT-3 | `solidificationResolution` label (cells across the pool, 2-cell stencil, `meshVerified: false`) and G/R/Tdot study checks | no cell-count threshold is cited (stencil rule) | `lpbf_simulation.py` |
| LT-4 | Phase 22 solver optics are required inputs (no golden calls it) | — | `lpbf_transient_3d_gpu.py` |
| LT-7 | GPU validators reject `evaporationModel` (GPU pilots excluded from parity) | — | `lpbf_gpu_thermal*.py` |
| LA-1 | Marangoni surface velocity DebRoy & David 1995 Eq. 8 (was m^1.5/s) | Rev. Mod. Phys. 67, 85 | `marangoni_screening.py` |
| LA-2 | Rosenthal regularisation on the 1/R prefactor only (true R in the exponent) | Rosenthal 1946, Trans. ASME 68, 849 | `lpbf_thermal_solver.py`, `warp_thermal_solver.py` |
| D1 | Reported peak stays T(0,0,0), labelled `peakTemperatureBasis` (`regularised-singular-source-value` / `distributed-source-conduction-centre-value`), `peakExceedsVaporization`, `surfaceTemperatureBasis` | lead decision | `lpbf_thermal_solver.py` |
| LA-3 | Geometric keyhole screen: risk None, King mode indicator (D/W > 0.5) | King et al. 2014 sec. 5.2 | `lpbf_defect_diagnostics.py` |
| LA-4 | Fabbro eq. 2 only (eq. 3 is the same expression; the average was a no-op up to 1 ULP), Pe fit flag, relabels | Fabbro 2020 eq. 2-3 | `fabbro_keyhole.py`, `lpbf_thermal_solver.py` |
| LA-5 | ET/Goldak take the absorbed power as Q (no 1/(1+0.55 St)); Rosenthal factor kept, exported (uncited) | Eagar & Tsai 1983; Goldak 1984 | `lpbf_thermal_solver.py` |
| LA-7 | Per-layer midpoint penetration feeds `lof_screened` (option A), 1e-6 µm tolerance; no golden value drift (g3 already 0.0/True) | Tang et al. 2017 | `lpbf_overlap.py` |
| LA-8 | `heuristic-keyhole-increment-v1` id/basis; continuous Knight recoil helper | Anisimov 1968 / Knight 1979 | `lpbf_thermal_solver.py` |
| KS-1 | Solidifying-front sampling (deepest liquidus point backwards, n_x > 0 only, one sample set) | Kou ch. 6 (R = V cos φ) | `solidification_front.py` |
| KS-4/6/7 | Powder ray tracer bounces/closure, Gaussian sampler, bed-top depth (opt-in only) | — | `powder_bed_raytracer.py` |
| KS-8 | Hunt 1984 / Hunt & Lu 1996 / Kirkwood 1985 DOIs | Crossref | `solidification_front.py`, `lpbf_solidification_microstructure.py` |
| MD-1 | Solidus row for alloys with k_liq < k_RT (AlSi10Mg, Scalmalloy, Cu); Cu k(Tm) 328 W/m K | Ho, Powell & Liley 1972 | `lpbf_material_registry.py` |
| MD-2/MD-5 | One dγ/dT per alloy: IN718 −4.0e-4 (Mills 2006 Eq. 24, upper bound), AlSi10Mg −3.5e-4 (unsourced) | Mills et al. 2006 | `four_alloy_materials.py` |
| MD-3 | Rosenthal 1946 DOI; `in718-eos-like` → measured `in718-nist-amb2022-03-0` row | Lane et al. 2024 | `four_alloy_materials.py` |
| MD-4 | One IN625 extended route (Sabau law continued above liquidus, spec density) | Sabau et al. 2020 | `in625_thermal_material.py` |
| MD-6/MD-7 | U95 budgets and emissivity 0.35 labelled as assumed | — | `four_alloy_materials.py`, `in625_thermal_material.py`, `lpbf_material_registry.py` |

## Observations (260 exact keys) by case

| case | keys | cause | raw before → after |
|---|---|---|---|
| g1_v1_60w_in718 (reference) | `result.{canonicalSha256, orderedTypedSha256, topLevelKeys, key.geometricDefectScreen, key.solidificationResolution}` | LA-3, LT-3 | keyhole.risk "low" → null, kingModeIndicator conduction-mode (D/W 0.25); label 4.0 / 1.0 cells at 20 µm, `stencil-spans-melt-pool`. Stripped digest **6a5e59be… → ff428b93…**. Metrics, thermalHistory, numericalDiagnostics, artifacts, materialSha256 `6a8d7bde…`, materialRevisionSha256 `5c9179e9…`, inputSha256 unchanged |
| g2_bare_plate_100w_corridor (reference, slow) | `result.{canonicalSha256, orderedTypedSha256, topLevelKeys, key.solidificationResolution}` | LT-3 | 1.0 / 1.0 cells at 39.85 µm, stencil-spans. `fixture.strippedResultEqual` stays true, `npzBytesEqual` true, artifacts 0 mismatched |
| g4_layered_plate (reference) | same 4 | LT-3 | not-available (no melt at 20 µm) |
| g15 | same 4 | LT-3 | 1.0 / 1.0 at 40 µm |
| g3 ×3, g5, g8, g14, g17-Ti64/316L, g19 | digests, `key.geometricDefectScreen`, `key.solidificationResolution`, topLevelKeys; g8 also `plain.canonicalSha256` | LA-3, LT-3 | keyhole risk low/moderate → null with mode indicator; no overlap (LA-7) value drift |
| g6_screening_and_fallback | 12: 4 sub-runs × {canonical, ordered, key.geometricDefectScreen} | LA-3 | risk "low" → null, conduction-mode |
| g7_mesh_study / g7_timestep_study | + `key.convergenceStudy` | LT-2, LT-3 | protocol v1 → `v2-celik-ratio`; G/R/Tdot checks added (inconclusive: unmelted 10 W case); timestep levels 2.0e-6/1.41e-6/1.0e-6 → 1.0e-6/7.06e-7/5.0e-7 s (ratios 1.42/1.41 instead of coarsening above the realised step) |
| g16_non_in718_transient | 25: AlSi10Mg 16 (incl. exact `materialRevisionSha256`, `coreContract.materialSha256`, metrics, thermalHistory, numericalDiagnostics, energyBalance, discretization, peakInterpolatedMeltPool), 316L/Ti64 4 each | MD-1, LA-3, LT-3 | AlSi10Mg 40 W: peak 939.43 → 886.97 K, G 9.68e6 → 9.96e6 K/m, R 0.612 → 0.157 m/s, Tdot 5.69e6 → 1.63e6 K/s, Ma 25.5 → 6.7 |
| g17_evaporation_alsi10mg | 91 (40 + 51 hidden by the print limit): field frames, artifacts, npz arrays, evaporation counters, identity digests, metrics | MD-1, LA-3, LT-3 | L 280 → 240, volume 3.39e6 → 2.82e6 µm³, G 2.42e6 → 2.47e6 K/m, R 0.808 → 0.675 m/s, Tdot 8.86e5 → 9.72e5 K/s |
| g9_material_snapshots | 28 | MD-1..7 | AlSi10Mg k between RT and solidus 127.5…85.3 → 130.0 (held), Scalmalloy 113.1… → 115.0, Cu k 383.1…228.9 → 388.1…346.6 W/m K; rho/cp of those tables 1-ULP only (segment split on the same line); dγ/dT IN718 −4.2e-4 → −4.0e-4, AlSi10Mg −1.8e-4 → −3.5e-4; catalog notes; literature cases (DOI, NIST row); IN625 extended route |
| g11_build_job_meltpool | 12: `meltpool.{0,1,2}.{canonicalSha256, typedSha256, geometry_um, peakTemperature_C}` | LA-2, D1, LA-5, LA-1, LA-3, LA-4, LA-8, KS-1, KS-8 | payload 0 IN718 200/800/80 Rosenthal W/D/L/cavity [144.7, 104.2, 755.3, 33.2] → [154.9, 110.4, 804.9, 35.2], peak **2500.2 → 35097.0** (regularised singular-source value, labelled; surface 2500.2 → 2850.0 = T_vap); payload 1 Ti64 280/1200 ET [126.5, 124.5, 641.9, 67.9] → [135.8, 124.5, 742.8, 63.1], peak 28776.6 → 33381.2; payload 2 316L 370/600 Goldak [169.0, 251.6, 681.8, 168.6] → [183.2, 251.6, 792.7, 161.8], peak 19247.4 → 22491.2 |
| g18_in625_latent_heat | `meltpool.in625`, `.geometry_um` | as G11 | [145.7, 110.0, 795.0, 38.6] → [155.9, 116.5, 846.5, 40.8]; latent-heat flags and values unchanged |
| g12_analytical_modules | 5 | LA-2, LA-4, LA-1, KS-1, KS-8 | Rosenthal probe temperatures +0.3 to +0.6 % (e.g. 2487.43 → 2498.40); Fabbro depth 1 ULP (eq. 2 only) + `pecletInFitRange`/`blendBasis`; Marangoni u 0.00286 → 2.08 m/s and 0.00763 → 7.69 m/s (Pe_Ma 0.026 → 18.9, 0.069 → 69.9) + DOI; solidification probe: the synthetic field had no n_x > 0 sample (R on the 1e-4 floor, "Planar") → tail-length fallback (G 1.14e9 K/m, R 0.8 m/s, "Cellular"); Hunt DOI |

## VERSION

`enthalpy-fv-6` unchanged: no Wave B hunk touches the transient operator (`lpbf_simulation.transient` stepping, `lpbf_core_physics`, enthalpy inversion, source deposition). Measured: every metric, thermalHistory, energyBalance, field, artifact, NPZ and numericalDiagnostics observation of G1, G2, G4 and G15 is bit-equal; G13 (source quadrature) and NPZ determinism PASS. The only transient numbers that move are AlSi10Mg (G16/G17), through its material table (MD-1), which is versioned by `materialRevisionSha256` / `materialSha256` (both drift, both named as exact keys).

## Effects outside the goldens

- Reference cases, AMB2022-03 (7 tracks), KS-1 grid and the published-dataset comparison: see PROOF.md (2026-10-07 Wave B entry) and `LPBF_DATASET_COMPARISON_2026-10-07_waveb-physics.*`. Highlights: IN718 280/940 Rosenthal 175.2/159.7/1250.5 → 183.8/166.4/1306.8; AMB MAPE W/D Rosenthal 38.3/24.1 → 43.0/27.5 %, ET W 9.6 → 7.7 %, Goldak W 12.8 → 8.4 %; KS-1 grid available/degenerate/fallback 84/9/7 → 97/0/3.
- G12 solidification probe after KS-1: the tail-length fallback values (G 1.14e9 K/m, R 0.8 m/s, Tdot 9.1e8 K/s, PDAS 0.037 µm, SDAS 0.055 µm) are heuristic screening values from the existing fallback on a synthetic analytic field, labelled `gradientSource=tail-length-fallback`; they are not microstructure predictions and the spacings are physically implausible. A plausibility clamp on the fallback is left for a later wave. In the real 100-case grid the fallback now occurs 3 times (base: 7 fallbacks plus 9 degenerate).
- Golden scope: besides the 260 allowlisted observation keys, 22 goldens also change the `rawValues` entries of exactly those keys (every changed rawValues key mirrors a changed observation key); everything else differs only in `recordedGitHead`/`recordedImplementationHash`/`recordedRuns_s`.
- GPU-only (not covered by the warp-less harness): LT-1 max |warp − cpu| 11 582 → 0.1 °C (RTX 4060); LT-7 validators reject evaporationModel; LT-4 optics required; KS-4/6/7 opt-in ray tracer (NIST case conduction A 0.581 → 0.609, Goldak ray-traced width 145.9 → 163.5 µm).
- Build job: `BUILD_JOB_SOLVER_REVISION` v10 → `lpbf-build-job-waveb-front-field-marangoni-v11`; microstructure fixture re-captured (degenerate block synthetic).
- Labels: `experimentalValidation=false`, `validationStatus=unvalidated`, `productionReady=false` everywhere; no evidence label promoted.
