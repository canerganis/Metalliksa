# LPBF dataset comparison (2026-10-05)

**Comparison of screening kernels against published single-track measurements; not experimental validation; estimated material laws; absorptivity assumed.**

Schema `lpbf-dataset-comparison-1`; implementation fingerprint `11b04b8fa3de1a6b2cf46afb67e6c439f05ca9d0ab2affec92f1e5b239eb3359`; quick mode: False. Honesty: comparison, not validation; screening kernels; estimated material laws; absorptivity assumed (not measured); published single-track measurements, no replicate or uncertainty model; a failing comparison is reported, not fitted away. `experimentalValidation` = false.

Slim view record `LPBF_DATASET_COMPARISON_2026-10-05.view.json` (this record minus `breakdowns` and `referenceTransient.rows`; sha256 of its LF bytes `300bdc94ff875cf5044f76b1ebb7073cdf4a9c04a1109f69ff4655ac28c0a880`).

## Datasets

- **hofmann-316l-2026** (316L Stainless Steel): DOI 10.5281/zenodo.16979848, CC BY 4.0, 677 rows recorded, table sha256 `d4bbc7a60b536118586f44b64beb0fa20f94133f6d1a8d0fdcf726003720c3d8`. Hofmann et al., melt-pool geometry data for 316L single tracks (Aconity Midi), Zenodo 10.5281/zenodo.16979848 (v1, 2025-08-28); associated paper Materials & Design 262 (2026) 115459, doi:10.1016/j.matdes.2026.115459.
  - caveat: Measured cross-sections from micrographs; the uncertainty budget is not stated in the files read.
  - caveat: The d_laser column is the laser spot DIAMETER in mm; the diameter definition (1/e^2 or other) is not stated on the Zenodo record and was not confirmed from the paper: treated as 1/e^2 by assumption.
  - caveat: Absorptivity is not measured; the comparison uses the repo's estimated 316L absorptivity.
  - caveat: Build-plate temperature is not given: 20 C is an assumption.
  - caveat: t_powder = 0 rows are bare plate; t_powder 30/60 um are powder layers (the packing is not stated).
  - caveat: The CSV header calls the area column 'um' although the values are um^2 (width x depth scale confirms).
  - caveat: 677 rows contain repeated parameter sets (623 distinct) -- replicates are kept as separate rows.
  - caveat: Where the width/depth are taken along the track and whether the section is at steady state is not stated in the files read.
  - caveat: 316L thermophysical properties used by the models are estimated, not measured.
- **totis-ti64-2021** (Ti-6Al-4V): DOI 10.17632/s9438vb5xd.1, CC BY 4.0, 80 rows recorded, table sha256 `3b5794f3a25a5f67fa0d8d1ab006834205ef820b046c24deb15836025825d623`. Totis, Vaglio et al., single-track Ti6Al4V SEM images and geometrical data (Concept Laser M2, 50 um laser spot), Mendeley Data, 10.17632/s9438vb5xd.1 (v1, 2021-04-26); related article Data in Brief, doi:10.1016/j.dib.2020.106443.
  - caveat: Tracks were made on a 25 um powder layer over a printed Ti-6Al-4V base (not a bare plate, not a semi-infinite wrought substrate); the 50 um spot is taken as 1/e^2 from the research note.
  - caveat: The workbook does not state the depth reference line (original substrate surface vs powder surface): depth is used 'as found'; the Mendeley page and the workbook do not say.
  - caveat: One track per (power, speed) cell: no replicates, no scatter estimate.
  - caveat: Absorptivity is not measured; the comparison uses the repo's estimated Ti-6Al-4V absorptivity.
  - caveat: Build-plate temperature is not given: 20 C is an assumption.
  - caveat: No balling flag in the workbook: the regime classifier uses inputs only for this dataset.
  - caveat: Width, depth and height are SEM-derived values read from the workbook sheets 'Track width (W)', 'Track depth (D)', 'Track height (H)', 'Contact angle' (microhardness sheet not used).
  - caveat: Ti-6Al-4V thermophysical properties used by the models are estimated, not measured.
- **cmu-ti64-st-2026** (Ti-6Al-4V): DOI 10.1184/R1/25696293.v1, CC BY 4.0, 216 rows recorded, table sha256 `7f415afb20cd8e1698efcbc4948654ed4b95bb4fc1854b5c1e7f45e9874a1f90`. CMU KiltHub, Ti-6Al-4V melt-pool variability, 10.1184/R1/25696293.v1.
  - caveat: ST source table has no power column; beam diameter is also unreported. No solver prediction is made.
- **cmu-ti64-mt-2026** (Ti-6Al-4V): DOI 10.1184/R1/25696293.v1, CC BY 4.0, 410 rows recorded, table sha256 `d8d318fd673c69ad250a9d44cc7b37b71d3706cde7ad93539049454aedf09c57`. CMU KiltHub, Ti-6Al-4V melt-pool variability, 10.1184/R1/25696293.v1.
  - caveat: Beam diameter, layer, preheat and absorptivity are unreported; no solver prediction is made.
- **ku-leuven-in718-2021** (Inconel 718): DOI 10.6084/m9.figshare.15035706.v1, CC0, 48 rows recorded, table sha256 `d8731ecc5cd027e697e4fbd7f9dabb634c197f0325f4282eb3c86ce9ff9d512b`. KU Leuven IN718 melt-pool measurements, Figshare, 10.6084/m9.figshare.15035706.v1.
  - caveat: Source CSV does not state units for w exp/d exp; article describes half-width, so dimensions are retained as source values and excluded from numeric comparison until resolved.
  - caveat: 48 numbered conditions; 38 contain both dimensions and 10 have missing dimensions.
  - caveat: Condition means, not individual cross-sections; source sample counts vary.
  - caveat: Paper reports 37.5 um spot and 60 um powder layer; preheat and measured absorptivity are not reported.

## Regime screening rule

Screening classifier, not the papers' regime definition. Inputs: normalised enthalpy dH/h_s = eta*P / (rho*cp_s*max(50, T_liq-T0)*sqrt(pi*alpha_s*v*r^3)) (same form as lpbf_thermal_solver.py, flat-plate absorptivity_IR of the material authority, solid k/cp, r = d/2) and the dataset's own balling flag. balling == 1 -> 'balling-flagged' (Hofmann only); otherwise dH/h_s < 15 -> 'conduction', 15 <= dH/h_s < 30 -> 'transition', >= 30 -> 'keyhole'. Measured D/W is recorded next to the label but not used for it. Added datasets without a reported beam diameter (CMU) or with unresolved measured dimension units/operator (KU Leuven) are labeled unclassified and excluded from kernel predictions; no regime label is inferred for them.

Row counts per regime: all 1431, balling-flagged 216, conduction 141, keyhole 194, transition 206, unclassified-missing-process-input 626, unclassified-source-dimensions-unresolved 48

## Assumptions

- **absorptivity**: the repo's estimated absorptivity_IR (316L 0.42, Ti-6Al-4V 0.35), flat-plate
- **addedDatasetTreatment**: CMU ST has no power field; all CMU rows lack beam diameter. KU Leuven source dimensions retain unresolved units and width operator. These rows have no numeric regime classification or kernel predictions and are excluded from MAPE/statistics; source observations remain in rows with explicit extentStatus reasons.
- **hatch_um**: 100 (neither dataset has a hatch: single tracks; the hatch only enters the lack-of-fusion screen, not the width/depth/length extents)
- **inclusionRule**: a row counts for statistics only when extentStatus == 'computed'
- **layer_um**: t_powder 0 (bare plate) rows are passed with a nominal 30 um layer because the function requires a positive layer; width/depth/length do not depend on it (checked at 10/30/60 um)
- **powderBedRayTracer**: calculate_meltpool_physics tries the optional GPU powder ray tracer and falls back to the flat-plate absorptivity on any exception. This harness pins the flat-plate path (sys.modules['powder_bed_raytracer'] = None before the solver import; --allow-raytracer unpins), so the ray tracer was not used; see `absorption`
- **preheat_C**: 20 C assumed (not given by either dataset)

## Absorption path

Path: **flat-plate** (pinned: True). sys.modules['powder_bed_raytracer'] = None is set in the main process and in every worker before lpbf_thermal_solver is imported, so the solver's `from powder_bed_raytracer import ...` raises ImportError and its except branch (flat-plate absorptivity) is taken; the solver is not edited.

Ray-tracer module present: True; importable in a separate probe process: False. Absorptivity by material: 316L 0.42, Ti-6Al-4V 0.35. Fallback warnings captured: 3963 of 3963 solver calls (by kernel, main run: eagar-tsai 757, goldak 757, rosenthal 757).

flat-plate absorptivity_IR; the GPU powder ray tracer was not used; with it the predictions change (reviewer stub: Eagar-Tsai hofmann-0001 171.0/119.6 -> 209.2/143.6 um at effective 0.65). fallbackWarnings counts the solver's 'GPU Powder Bed Ray Tracing failed' messages (captured, not suppressed): with the pin it fires once per solver call (solverCalls), which confirms the flat-plate branch was the realized path.

## Limits

- Kernels are compared on different included subsets (rows with extentStatus == 'computed'): pooled n = rosenthal 519 of 1431, eagar-tsai 757 of 1431, goldak 743 of 1431. Only summary.<kernel>.common (n = 519, the rows where all kernels are computed) is a like-for-like comparison; pooled and per-regime figures of different kernels are not.
- Rosenthal conduction statistics rest on 27 of 141 conduction rows: they are selected by the kernel's own output (only rows where Rosenthal resolves an extent without heuristic fallback, search-box limitation or the 0.55 x beam-diameter width floor are 'computed'), so they describe the rows it can resolve, not the regime.
- Eagar-Tsai and Goldak keyhole-regime depth statistics are identical (bias +0.4 %, MAPE 24.7 %) because both add the same Fabbro keyhole depth term; they are not independent evidence.
- The measurements carry no uncertainty model (neither dataset provides per-row measurement uncertainty); the bootstrap intervals cover resampling of parameter sets only, not measurement error, the estimated material laws or the assumed absorptivity.
- Replicate rows are not independent: the Hofmann table has 677 rows but only 623 distinct parameter sets; the bootstrap intervals resample whole parameter sets (clusters), the point statistics weight every row.
- Balling-flagged rows (216) are inside the pooled 'all' headline statistics; a continuous-track screening kernel is not meant to describe them.
- The Totis depth reference line (original substrate surface vs powder surface) is not stated by the source; the 80 Totis depths carry an unknown offset.
- The kernels ignore powder-layer thickness (identical predictions at 0/30/60 um; see assumptions.layer_um), so any trend with powder-layer thickness is in the measurements only.
- Absorption path: flat-plate absorptivity_IR (316L 0.42, Ti-6Al-4V 0.35); the GPU powder ray tracer was not used; with the ray tracer the predictions change.
- The reference-transient block depends on wall-clock budgets (total and per case): on a slower host rows can become 'not-run (budget)'. --reuse-reference copies the block of an earlier record instead.

## Summary: kernel x regime (all datasets pooled)

Bias = mean((pred-meas)/meas); rows with extentStatus other than `computed` are excluded and counted. Fractions: share of rows within +-30 % of the measurement / within the x0.5-2 band.

### Pooled (the `common` regime = rows where all kernels are computed)

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 519 | 912 | +21.5 | 30.3 | 61.1 | 61% / 98% | +42.6 | 51.8 | 73.7 | 50% / 86% |
| rosenthal | balling-flagged | 121 | 95 | +26.7 | 30.5 | 47.7 | 59% / 97% | +97.8 | 100.9 | 81.6 | 31% / 67% |
| rosenthal | common | 519 | 912 | +21.5 | 30.3 | 61.1 | 61% / 98% | +42.6 | 51.8 | 73.7 | 50% / 86% |
| rosenthal | conduction | 27 | 114 | -35.0 | 35.0 | 59.8 | 22% / 96% | -1.1 | 29.9 | 20.1 | 52% / 93% |
| rosenthal | keyhole | 192 | 2 | +44.9 | 44.9 | 85.5 | 34% / 98% | +23.4 | 36.4 | 94.2 | 55% / 93% |
| rosenthal | transition | 179 | 27 | +1.4 | 13.8 | 30.2 | 96% / 100% | +32.5 | 38.4 | 40.9 | 59% / 90% |
| rosenthal | unclassified-missing-process-input | 0 | 626 | - | - | - | - | - | - | - | - |
| rosenthal | unclassified-source-dimensions-unresolved | 0 | 48 | - | - | - | - | - | - | - | - |
| eagar-tsai | all | 757 | 674 | -10.2 | 13.9 | 29.0 | 94% / 100% | +10.9 | 34.1 | 54.1 | 63% / 91% |
| eagar-tsai | balling-flagged | 216 | 0 | -10.1 | 14.6 | 31.9 | 92% / 100% | +37.9 | 50.8 | 46.7 | 56% / 84% |
| eagar-tsai | common | 519 | 912 | -8.4 | 13.2 | 28.3 | 95% / 100% | +9.8 | 36.7 | 64.5 | 59% / 91% |
| eagar-tsai | conduction | 141 | 0 | -12.5 | 14.8 | 27.0 | 94% / 100% | +17.2 | 28.5 | 13.3 | 74% / 93% |
| eagar-tsai | keyhole | 194 | 0 | -4.0 | 11.2 | 25.0 | 98% / 100% | +0.4 | 24.7 | 82.8 | 67% / 98% |
| eagar-tsai | transition | 206 | 0 | -14.6 | 15.2 | 30.7 | 92% / 100% | -11.9 | 29.2 | 43.6 | 59% / 92% |
| eagar-tsai | unclassified-missing-process-input | 0 | 626 | - | - | - | - | - | - | - | - |
| eagar-tsai | unclassified-source-dimensions-unresolved | 0 | 48 | - | - | - | - | - | - | - | - |
| goldak | all | 743 | 688 | -17.4 | 20.0 | 39.5 | 81% / 99% | +17.7 | 37.7 | 54.6 | 61% / 91% |
| goldak | balling-flagged | 215 | 1 | -17.1 | 20.2 | 41.3 | 79% / 100% | +44.8 | 54.4 | 47.0 | 53% / 83% |
| goldak | common | 519 | 912 | -12.6 | 16.2 | 33.9 | 91% / 100% | +11.9 | 37.0 | 64.3 | 60% / 91% |
| goldak | conduction | 128 | 13 | -29.9 | 30.1 | 50.0 | 52% / 98% | +38.9 | 43.9 | 17.0 | 56% / 88% |
| goldak | keyhole | 194 | 0 | -6.6 | 12.4 | 27.9 | 98% / 100% | +0.4 | 24.7 | 82.8 | 67% / 98% |
| goldak | transition | 206 | 0 | -20.3 | 20.4 | 39.6 | 85% / 100% | -7.6 | 28.6 | 42.5 | 65% / 93% |
| goldak | unclassified-missing-process-input | 0 | 626 | - | - | - | - | - | - | - | - |
| goldak | unclassified-source-dimensions-unresolved | 0 | 48 | - | - | - | - | - | - | - | - |

### Cluster-bootstrap 95 % intervals (pooled summary cells)

Distinct parameter sets (dataset, power, speed, beam diameter, layer) resampled with replacement, 1000 replicates, `random.Random(0)`, percentile 2.5/97.5; replicates of one set stay together. The intervals cover this resampling only (no measurement uncertainty, no material-law uncertainty); they are in JSON `summary.<kernel>.<regime>.<width|depth>.{bias_pct_ci95, mape_pct_ci95, n_parameterSets}`.

| kernel | regime | n | parameter sets | W bias % CI95 | W MAPE % CI95 | D bias % CI95 | D MAPE % CI95 |
|---|---|---|---|---|---|---|---|
| rosenthal | all | 519 | 477 | [18.6, 24.3] | [28.2, 32.3] | [36.4, 49.4] | [46.1, 58.1] |
| rosenthal | balling-flagged | 121 | 120 | [21.6, 32.2] | [26.1, 35.5] | [78.1, 118.9] | [81.7, 121.7] |
| rosenthal | common | 519 | 477 | [18.6, 24.3] | [28.2, 32.3] | [36.4, 49.4] | [46.1, 58.1] |
| rosenthal | conduction | 27 | 24 | [-38.6, -31.3] | [31.3, 38.6] | [-12.0, 10.7] | [20.7, 38.8] |
| rosenthal | keyhole | 192 | 183 | [41.3, 48.1] | [41.4, 48.1] | [17.2, 29.6] | [31.6, 41.4] |
| rosenthal | transition | 179 | 159 | [-1.2, 3.8] | [12.5, 15.1] | [25.8, 39.3] | [32.5, 44.2] |
| eagar-tsai | all | 757 | 703 | [-11.1, -9.3] | [13.3, 14.6] | [6.8, 15.2] | [30.8, 37.8] |
| eagar-tsai | balling-flagged | 216 | 215 | [-12.1, -8.3] | [13.3, 15.8] | [27.7, 49.1] | [41.5, 61.4] |
| eagar-tsai | common | 519 | 477 | [-9.6, -7.2] | [12.5, 13.9] | [4.8, 15.5] | [32.4, 41.6] |
| eagar-tsai | conduction | 141 | 128 | [-14.4, -10.7] | [13.4, 16.1] | [9.5, 25.0] | [22.1, 35.2] |
| eagar-tsai | keyhole | 194 | 185 | [-5.7, -2.1] | [10.2, 12.2] | [-4.1, 4.8] | [22.0, 27.3] |
| eagar-tsai | transition | 206 | 185 | [-16.1, -13.3] | [14.0, 16.4] | [-16.9, -7.3] | [25.9, 32.5] |
| goldak | all | 743 | 690 | [-18.5, -16.4] | [19.1, 20.8] | [13.1, 22.2] | [33.9, 41.6] |
| goldak | balling-flagged | 215 | 214 | [-19.1, -15.0] | [18.7, 21.7] | [34.4, 56.0] | [45.5, 65.1] |
| goldak | common | 519 | 477 | [-13.8, -11.4] | [15.4, 17.0] | [6.8, 17.6] | [32.7, 41.9] |
| goldak | conduction | 128 | 116 | [-32.0, -27.9] | [28.2, 32.1] | [29.0, 49.0] | [35.1, 53.3] |
| goldak | keyhole | 194 | 185 | [-8.4, -4.7] | [11.3, 13.5] | [-4.1, 4.8] | [22.0, 27.3] |
| goldak | transition | 206 | 185 | [-21.6, -19.0] | [19.2, 21.7] | [-12.7, -2.9] | [25.0, 32.0] |

### Dataset cmu-ti64-mt-2026

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 0 | 410 | - | - | - | - | - | - | - | - |
| rosenthal | unclassified-missing-process-input | 0 | 410 | - | - | - | - | - | - | - | - |
| eagar-tsai | all | 0 | 410 | - | - | - | - | - | - | - | - |
| eagar-tsai | unclassified-missing-process-input | 0 | 410 | - | - | - | - | - | - | - | - |
| goldak | all | 0 | 410 | - | - | - | - | - | - | - | - |
| goldak | unclassified-missing-process-input | 0 | 410 | - | - | - | - | - | - | - | - |

### Dataset cmu-ti64-st-2026

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 0 | 216 | - | - | - | - | - | - | - | - |
| rosenthal | unclassified-missing-process-input | 0 | 216 | - | - | - | - | - | - | - | - |
| eagar-tsai | all | 0 | 216 | - | - | - | - | - | - | - | - |
| eagar-tsai | unclassified-missing-process-input | 0 | 216 | - | - | - | - | - | - | - | - |
| goldak | all | 0 | 216 | - | - | - | - | - | - | - | - |
| goldak | unclassified-missing-process-input | 0 | 216 | - | - | - | - | - | - | - | - |

### Dataset hofmann-316l-2026

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 454 | 223 | +17.4 | 26.8 | 55.5 | 65% / 99% | +47.3 | 54.2 | 63.7 | 50% / 85% |
| rosenthal | balling-flagged | 121 | 95 | +26.7 | 30.5 | 47.7 | 59% / 97% | +97.8 | 100.9 | 81.6 | 31% / 67% |
| rosenthal | conduction | 26 | 107 | -34.3 | 34.3 | 60.1 | 23% / 100% | +1.4 | 28.5 | 18.7 | 54% / 96% |
| rosenthal | keyhole | 137 | 0 | +38.2 | 38.2 | 79.7 | 42% / 99% | +28.1 | 35.8 | 73.1 | 56% / 94% |
| rosenthal | transition | 170 | 21 | +2.1 | 13.9 | 30.8 | 96% / 100% | +34.0 | 39.8 | 41.8 | 56% / 89% |
| eagar-tsai | all | 677 | 0 | -10.5 | 13.4 | 29.4 | 96% / 100% | +13.4 | 34.0 | 46.8 | 65% / 92% |
| eagar-tsai | balling-flagged | 216 | 0 | -10.1 | 14.6 | 31.9 | 92% / 100% | +37.9 | 50.8 | 46.7 | 56% / 84% |
| eagar-tsai | conduction | 133 | 0 | -12.2 | 14.1 | 27.3 | 96% / 100% | +14.9 | 24.8 | 12.0 | 78% / 95% |
| eagar-tsai | keyhole | 137 | 0 | -5.6 | 10.4 | 25.8 | 99% / 100% | +5.5 | 24.0 | 66.6 | 71% / 99% |
| eagar-tsai | transition | 191 | 0 | -13.2 | 13.9 | 30.1 | 97% / 100% | -9.8 | 28.5 | 44.8 | 62% / 93% |
| goldak | all | 663 | 14 | -18.0 | 19.8 | 40.6 | 82% / 100% | +20.5 | 37.7 | 47.2 | 62% / 91% |
| goldak | balling-flagged | 215 | 1 | -17.1 | 20.2 | 41.3 | 79% / 100% | +44.8 | 54.4 | 47.0 | 53% / 83% |
| goldak | conduction | 120 | 13 | -29.3 | 29.5 | 51.0 | 55% / 98% | +35.6 | 38.7 | 16.1 | 59% / 92% |
| goldak | keyhole | 137 | 0 | -8.2 | 12.0 | 29.4 | 99% / 100% | +5.5 | 24.0 | 66.6 | 71% / 99% |
| goldak | transition | 191 | 0 | -18.8 | 19.0 | 39.3 | 91% / 100% | -5.5 | 28.1 | 43.7 | 66% / 93% |

### Dataset ku-leuven-in718-2021

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 0 | 48 | - | - | - | - | - | - | - | - |
| rosenthal | unclassified-source-dimensions-unresolved | 0 | 48 | - | - | - | - | - | - | - | - |
| eagar-tsai | all | 0 | 48 | - | - | - | - | - | - | - | - |
| eagar-tsai | unclassified-source-dimensions-unresolved | 0 | 48 | - | - | - | - | - | - | - | - |
| goldak | all | 0 | 48 | - | - | - | - | - | - | - | - |
| goldak | unclassified-source-dimensions-unresolved | 0 | 48 | - | - | - | - | - | - | - | - |

### Dataset totis-ti64-2021

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 65 | 15 | +49.7 | 54.4 | 91.2 | 28% / 94% | +9.6 | 34.8 | 122.5 | 57% / 91% |
| rosenthal | conduction | 1 | 7 | -53.7 | 53.7 | 52.6 | 0% / 0% | -66.1 | 66.1 | 42.1 | 0% / 0% |
| rosenthal | keyhole | 55 | 2 | +61.4 | 61.5 | 98.7 | 16% / 95% | +11.7 | 37.9 | 133.0 | 51% / 91% |
| rosenthal | transition | 9 | 6 | -10.4 | 11.2 | 15.3 | 100% / 100% | +4.6 | 12.3 | 10.8 | 100% / 100% |
| eagar-tsai | all | 80 | 0 | -8.1 | 18.1 | 26.1 | 80% / 100% | -10.1 | 34.9 | 96.0 | 48% / 90% |
| eagar-tsai | conduction | 8 | 0 | -18.9 | 25.4 | 19.9 | 62% / 100% | +55.7 | 90.5 | 27.2 | 12% / 50% |
| eagar-tsai | keyhole | 57 | 0 | -0.0 | 13.1 | 23.2 | 96% / 100% | -11.9 | 26.2 | 112.6 | 58% / 98% |
| eagar-tsai | transition | 15 | 0 | -33.0 | 33.0 | 37.2 | 27% / 100% | -38.2 | 38.2 | 23.9 | 27% / 80% |
| goldak | all | 80 | 0 | -13.2 | 21.0 | 29.2 | 71% / 98% | -6.2 | 37.2 | 95.9 | 51% / 89% |
| goldak | conduction | 8 | 0 | -39.9 | 39.9 | 30.7 | 12% / 88% | +88.2 | 121.1 | 26.5 | 12% / 25% |
| goldak | keyhole | 57 | 0 | -2.7 | 13.6 | 23.9 | 95% / 100% | -11.9 | 26.2 | 112.6 | 58% / 98% |
| goldak | transition | 15 | 0 | -39.1 | 39.1 | 43.4 | 13% / 93% | -34.6 | 34.6 | 22.4 | 47% / 87% |

### Hofmann, spot 110 um

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 87 | 74 | +9.1 | 20.0 | 53.8 | 82% / 99% | +44.0 | 49.6 | 67.2 | 48% / 86% |
| rosenthal | balling-flagged | 9 | 36 | +5.4 | 20.0 | 46.4 | 89% / 89% | +106.0 | 106.0 | 89.3 | 22% / 56% |
| rosenthal | conduction | 7 | 30 | -32.4 | 32.4 | 54.5 | 29% / 100% | +2.9 | 29.4 | 23.8 | 57% / 100% |
| rosenthal | keyhole | 24 | 0 | +29.7 | 29.7 | 81.5 | 62% / 100% | +29.2 | 34.6 | 86.0 | 58% / 100% |
| rosenthal | transition | 47 | 8 | +5.6 | 13.3 | 33.4 | 98% / 100% | +45.7 | 49.4 | 54.4 | 47% / 83% |
| eagar-tsai | all | 161 | 0 | -12.6 | 14.2 | 31.9 | 98% / 100% | +9.3 | 29.2 | 40.2 | 66% / 94% |
| eagar-tsai | balling-flagged | 45 | 0 | -13.2 | 15.1 | 33.4 | 93% / 100% | +28.2 | 42.3 | 26.2 | 53% / 87% |
| eagar-tsai | conduction | 37 | 0 | -11.7 | 14.2 | 24.6 | 100% / 100% | +10.0 | 18.8 | 11.8 | 78% / 97% |
| eagar-tsai | keyhole | 24 | 0 | -9.5 | 10.8 | 34.4 | 100% / 100% | +3.5 | 20.2 | 72.9 | 71% / 100% |
| eagar-tsai | transition | 55 | 0 | -13.9 | 14.9 | 33.8 | 98% / 100% | -4.0 | 29.3 | 42.1 | 65% / 95% |
| goldak | all | 158 | 3 | -21.7 | 22.0 | 44.7 | 77% / 100% | +18.4 | 33.7 | 40.7 | 65% / 92% |
| goldak | balling-flagged | 44 | 1 | -23.6 | 23.6 | 46.5 | 73% / 100% | +40.2 | 47.1 | 27.2 | 57% / 84% |
| goldak | conduction | 35 | 2 | -29.2 | 29.6 | 46.6 | 51% / 100% | +29.3 | 31.7 | 14.6 | 69% / 94% |
| goldak | keyhole | 24 | 0 | -12.5 | 13.3 | 40.5 | 100% / 100% | +3.5 | 20.2 | 72.9 | 71% / 100% |
| goldak | transition | 55 | 0 | -19.3 | 19.8 | 43.6 | 87% / 100% | +0.5 | 30.1 | 41.3 | 67% / 95% |

### Hofmann, spot 140 um

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 62 | 92 | -3.1 | 19.7 | 57.1 | 74% / 100% | +20.0 | 30.5 | 56.4 | 65% / 94% |
| rosenthal | balling-flagged | 4 | 34 | -12.9 | 16.5 | 37.6 | 75% / 100% | +102.8 | 102.8 | 77.2 | 25% / 50% |
| rosenthal | conduction | 11 | 50 | -37.9 | 37.9 | 77.4 | 0% / 100% | +3.3 | 25.0 | 18.5 | 55% / 100% |
| rosenthal | keyhole | 7 | 0 | +28.1 | 28.1 | 94.4 | 57% / 100% | +25.5 | 32.0 | 110.9 | 57% / 100% |
| rosenthal | transition | 40 | 8 | +1.9 | 13.5 | 41.3 | 98% / 100% | +15.3 | 24.4 | 45.7 | 72% / 95% |
| eagar-tsai | all | 154 | 0 | -12.7 | 13.4 | 35.7 | 98% / 100% | +4.1 | 27.8 | 44.3 | 69% / 94% |
| eagar-tsai | balling-flagged | 38 | 0 | -12.4 | 13.0 | 35.4 | 100% / 100% | +11.8 | 26.2 | 20.8 | 74% / 97% |
| eagar-tsai | conduction | 61 | 0 | -13.1 | 14.4 | 32.8 | 95% / 100% | +19.9 | 28.6 | 13.6 | 80% / 93% |
| eagar-tsai | keyhole | 7 | 0 | -10.7 | 10.8 | 49.5 | 100% / 100% | +1.2 | 27.1 | 94.2 | 71% / 100% |
| eagar-tsai | transition | 48 | 0 | -12.8 | 12.9 | 37.1 | 100% / 100% | -21.8 | 28.0 | 66.5 | 52% / 92% |
| goldak | all | 144 | 10 | -24.7 | 24.7 | 57.0 | 72% / 99% | +18.1 | 37.0 | 45.8 | 51% / 93% |
| goldak | balling-flagged | 38 | 0 | -25.8 | 25.8 | 56.7 | 66% / 100% | +29.8 | 37.2 | 23.0 | 50% / 95% |
| goldak | conduction | 51 | 10 | -31.2 | 31.2 | 63.0 | 51% / 98% | +44.9 | 47.7 | 19.9 | 45% / 90% |
| goldak | keyhole | 7 | 0 | -13.7 | 13.7 | 57.6 | 100% / 100% | +1.2 | 27.1 | 94.2 | 71% / 100% |
| goldak | transition | 48 | 0 | -18.7 | 18.7 | 50.1 | 96% / 100% | -17.2 | 27.0 | 64.5 | 56% / 94% |

### Hofmann, spot 50 um

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 172 | 3 | +27.7 | 33.0 | 50.0 | 52% / 98% | +52.3 | 59.3 | 58.3 | 51% / 85% |
| rosenthal | balling-flagged | 74 | 0 | +38.0 | 38.6 | 53.7 | 43% / 96% | +84.5 | 89.6 | 76.0 | 45% / 76% |
| rosenthal | conduction | 6 | 3 | -29.6 | 29.6 | 24.4 | 50% / 100% | -4.6 | 28.3 | 12.0 | 67% / 83% |
| rosenthal | keyhole | 51 | 0 | +41.3 | 41.3 | 63.0 | 33% / 100% | +25.3 | 34.7 | 51.8 | 53% / 96% |
| rosenthal | transition | 41 | 0 | +0.5 | 13.1 | 16.3 | 93% / 100% | +36.0 | 39.5 | 21.5 | 56% / 90% |
| eagar-tsai | all | 175 | 0 | -6.8 | 13.4 | 21.6 | 94% / 100% | +22.2 | 42.2 | 51.4 | 65% / 89% |
| eagar-tsai | balling-flagged | 74 | 0 | -4.6 | 14.9 | 26.3 | 89% / 100% | +53.6 | 67.2 | 64.4 | 58% / 76% |
| eagar-tsai | conduction | 9 | 0 | -4.8 | 12.4 | 10.2 | 100% / 100% | +2.0 | 20.6 | 9.2 | 78% / 100% |
| eagar-tsai | keyhole | 51 | 0 | -4.5 | 10.1 | 15.9 | 100% / 100% | +5.0 | 23.6 | 52.3 | 69% / 100% |
| eagar-tsai | transition | 41 | 0 | -14.1 | 14.9 | 20.1 | 95% / 100% | -8.5 | 24.9 | 19.0 | 71% / 95% |
| goldak | all | 175 | 0 | -10.5 | 15.5 | 23.6 | 91% / 100% | +23.6 | 42.2 | 51.3 | 67% / 88% |
| goldak | balling-flagged | 74 | 0 | -7.3 | 15.9 | 27.6 | 86% / 100% | +53.7 | 67.2 | 64.4 | 58% / 76% |
| goldak | conduction | 9 | 0 | -17.4 | 18.8 | 15.5 | 89% / 100% | +12.9 | 22.1 | 8.9 | 78% / 89% |
| goldak | keyhole | 51 | 0 | -6.8 | 11.2 | 17.5 | 100% / 100% | +5.0 | 23.6 | 52.3 | 69% / 100% |
| goldak | transition | 41 | 0 | -19.2 | 19.4 | 23.9 | 90% / 100% | -5.1 | 24.7 | 18.5 | 78% / 95% |

### Hofmann, spot 80 um

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 133 | 54 | +19.2 | 26.6 | 62.2 | 68% / 99% | +56.0 | 61.8 | 71.1 | 42% / 80% |
| rosenthal | balling-flagged | 34 | 25 | +12.3 | 17.1 | 32.8 | 82% / 100% | +123.9 | 124.0 | 91.4 | 6% / 53% |
| rosenthal | conduction | 2 | 24 | -35.0 | 35.0 | 42.1 | 50% / 100% | +3.5 | 45.3 | 16.3 | 0% / 100% |
| rosenthal | keyhole | 55 | 0 | +40.3 | 40.3 | 90.0 | 38% / 98% | +30.5 | 37.8 | 77.5 | 58% / 89% |
| rosenthal | transition | 42 | 5 | -0.3 | 15.8 | 26.4 | 95% / 100% | +36.8 | 43.8 | 36.6 | 52% / 90% |
| eagar-tsai | all | 187 | 0 | -10.2 | 12.9 | 27.5 | 94% / 100% | +16.2 | 35.6 | 49.4 | 61% / 90% |
| eagar-tsai | balling-flagged | 59 | 0 | -13.2 | 14.9 | 34.6 | 88% / 100% | +42.4 | 52.5 | 44.4 | 46% / 83% |
| eagar-tsai | conduction | 26 | 0 | -13.1 | 13.8 | 19.9 | 92% / 100% | +14.4 | 25.9 | 8.3 | 73% / 96% |
| eagar-tsai | keyhole | 55 | 0 | -4.3 | 10.4 | 24.4 | 98% / 100% | +7.3 | 25.7 | 71.1 | 73% / 96% |
| eagar-tsai | transition | 47 | 0 | -12.0 | 12.8 | 24.4 | 96% / 100% | -5.6 | 31.1 | 35.6 | 60% / 89% |
| goldak | all | 186 | 1 | -16.6 | 18.2 | 33.7 | 85% / 99% | +21.4 | 37.4 | 49.4 | 62% / 90% |
| goldak | balling-flagged | 59 | 0 | -18.8 | 19.4 | 39.9 | 81% / 100% | +46.9 | 54.9 | 44.4 | 47% / 83% |
| goldak | conduction | 25 | 1 | -29.8 | 29.8 | 35.4 | 56% / 96% | +33.4 | 36.3 | 10.6 | 68% / 96% |
| goldak | keyhole | 55 | 0 | -6.9 | 11.9 | 27.0 | 98% / 100% | +7.3 | 25.7 | 71.1 | 73% / 96% |
| goldak | transition | 47 | 0 | -17.9 | 17.9 | 31.3 | 89% / 100% | -0.7 | 29.8 | 34.8 | 66% / 89% |

**Powder-layer breakdowns below:** the kernels ignore powder-layer thickness (identical predictions at 0/30/60 um, see `assumptions.layer_um`), so any trend with powder-layer thickness in these tables is in the measurements only, not a kernel result.

### Hofmann, powder layer 0 um

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 111 | 99 | +15.3 | 24.0 | 46.5 | 70% / 100% | +53.9 | 56.1 | 65.1 | 38% / 81% |
| rosenthal | balling-flagged | 22 | 16 | +20.5 | 22.5 | 32.3 | 64% / 100% | +92.9 | 92.9 | 85.2 | 0% / 68% |
| rosenthal | conduction | 6 | 67 | -33.8 | 33.8 | 58.3 | 50% / 100% | -12.2 | 13.5 | 8.4 | 100% / 100% |
| rosenthal | keyhole | 41 | 0 | +33.8 | 33.8 | 64.2 | 51% / 100% | +44.0 | 45.8 | 73.0 | 46% / 85% |
| rosenthal | transition | 42 | 16 | +1.4 | 13.7 | 25.7 | 95% / 100% | +52.7 | 53.0 | 46.9 | 40% / 81% |
| eagar-tsai | all | 210 | 0 | -13.5 | 14.6 | 31.2 | 94% / 100% | +8.4 | 21.9 | 32.3 | 83% / 95% |
| eagar-tsai | balling-flagged | 38 | 0 | -16.3 | 16.8 | 35.6 | 87% / 100% | +26.7 | 39.9 | 46.5 | 61% / 87% |
| eagar-tsai | conduction | 73 | 0 | -14.0 | 15.4 | 29.0 | 96% / 100% | -0.4 | 9.5 | 5.2 | 99% / 99% |
| eagar-tsai | keyhole | 41 | 0 | -8.8 | 10.7 | 27.1 | 100% / 100% | +19.8 | 27.7 | 49.8 | 73% / 98% |
| eagar-tsai | transition | 58 | 0 | -14.2 | 15.0 | 33.4 | 93% / 100% | -0.8 | 21.5 | 23.9 | 86% / 95% |
| goldak | all | 199 | 11 | -22.7 | 23.1 | 45.3 | 67% / 100% | +17.5 | 25.2 | 33.3 | 79% / 95% |
| goldak | balling-flagged | 38 | 0 | -21.7 | 21.7 | 44.1 | 68% / 100% | +30.5 | 37.4 | 46.1 | 63% / 87% |
| goldak | conduction | 62 | 11 | -33.0 | 33.0 | 55.4 | 35% / 98% | +19.4 | 19.5 | 9.5 | 85% / 98% |
| goldak | keyhole | 41 | 0 | -11.2 | 12.7 | 31.2 | 100% / 100% | +19.8 | 27.7 | 49.8 | 73% / 98% |
| goldak | transition | 58 | 0 | -20.4 | 20.9 | 42.4 | 78% / 100% | +5.4 | 21.4 | 23.6 | 88% / 95% |

### Hofmann, powder layer 30 um

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 142 | 90 | +16.6 | 27.6 | 53.3 | 65% / 98% | +37.5 | 48.4 | 57.8 | 54% / 87% |
| rosenthal | balling-flagged | 40 | 51 | +33.2 | 36.5 | 55.2 | 60% / 92% | +85.4 | 90.4 | 80.2 | 40% / 62% |
| rosenthal | conduction | 9 | 35 | -35.8 | 35.8 | 57.0 | 11% / 100% | +8.7 | 35.0 | 14.9 | 33% / 89% |
| rosenthal | keyhole | 36 | 0 | +38.6 | 38.6 | 75.9 | 33% / 100% | +16.6 | 30.0 | 64.4 | 67% / 100% |
| rosenthal | transition | 57 | 4 | -0.6 | 13.1 | 28.2 | 96% / 100% | +21.7 | 32.7 | 34.1 | 60% / 96% |
| eagar-tsai | all | 232 | 0 | -10.0 | 14.1 | 30.3 | 94% / 100% | +15.3 | 38.7 | 48.4 | 54% / 88% |
| eagar-tsai | balling-flagged | 91 | 0 | -9.4 | 16.5 | 35.7 | 88% / 100% | +32.9 | 45.9 | 41.4 | 58% / 84% |
| eagar-tsai | conduction | 44 | 0 | -10.8 | 13.4 | 26.5 | 95% / 100% | +41.9 | 48.2 | 15.2 | 45% / 89% |
| eagar-tsai | keyhole | 36 | 0 | -5.0 | 8.9 | 19.0 | 100% / 100% | -5.6 | 24.3 | 75.4 | 58% / 100% |
| eagar-tsai | transition | 61 | 0 | -13.2 | 14.0 | 29.4 | 100% / 100% | -17.7 | 29.6 | 53.3 | 52% / 87% |
| goldak | all | 229 | 3 | -18.4 | 21.1 | 42.1 | 81% / 100% | +23.9 | 44.8 | 48.7 | 48% / 87% |
| goldak | balling-flagged | 90 | 1 | -18.1 | 23.7 | 47.0 | 71% / 100% | +42.2 | 52.5 | 42.0 | 50% / 82% |
| goldak | conduction | 42 | 2 | -27.5 | 27.9 | 48.2 | 67% / 98% | +64.4 | 68.9 | 20.9 | 19% / 83% |
| goldak | keyhole | 36 | 0 | -7.8 | 10.3 | 22.7 | 100% / 100% | -5.6 | 24.3 | 75.4 | 58% / 100% |
| goldak | transition | 61 | 0 | -18.7 | 18.9 | 38.5 | 95% / 100% | -13.7 | 28.9 | 51.5 | 61% / 89% |

### Hofmann, powder layer 60 um

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 201 | 34 | +19.2 | 27.9 | 61.3 | 63% / 99% | +50.6 | 57.3 | 66.9 | 53% / 86% |
| rosenthal | balling-flagged | 59 | 28 | +24.5 | 29.4 | 47.0 | 56% / 98% | +107.9 | 111.0 | 81.3 | 37% / 69% |
| rosenthal | conduction | 11 | 5 | -33.3 | 33.3 | 63.3 | 18% / 100% | +2.9 | 31.5 | 24.7 | 45% / 100% |
| rosenthal | keyhole | 60 | 0 | +40.9 | 40.9 | 90.7 | 40% / 98% | +24.1 | 32.4 | 77.8 | 57% / 97% |
| rosenthal | transition | 71 | 1 | +4.6 | 14.7 | 35.2 | 96% / 100% | +32.9 | 37.6 | 44.3 | 63% / 89% |
| eagar-tsai | all | 235 | 0 | -8.2 | 11.8 | 26.6 | 98% / 100% | +15.9 | 40.1 | 55.3 | 60% / 92% |
| eagar-tsai | balling-flagged | 87 | 0 | -8.1 | 11.6 | 25.4 | 98% / 100% | +48.1 | 60.7 | 51.7 | 53% / 83% |
| eagar-tsai | conduction | 16 | 0 | -7.2 | 10.4 | 20.6 | 100% / 100% | +10.0 | 30.1 | 20.7 | 75% / 100% |
| eagar-tsai | keyhole | 60 | 0 | -3.7 | 11.0 | 28.3 | 98% / 100% | +2.4 | 21.3 | 70.9 | 77% / 98% |
| eagar-tsai | transition | 72 | 0 | -12.4 | 12.8 | 27.9 | 99% / 100% | -10.4 | 33.1 | 49.6 | 50% / 96% |
| goldak | all | 235 | 0 | -13.5 | 15.8 | 34.4 | 95% / 100% | +19.8 | 41.4 | 55.1 | 60% / 91% |
| goldak | balling-flagged | 87 | 0 | -14.0 | 15.9 | 33.0 | 91% / 100% | +53.9 | 63.8 | 52.1 | 53% / 82% |
| goldak | conduction | 16 | 0 | -19.5 | 20.2 | 39.0 | 100% / 100% | +22.3 | 33.9 | 21.2 | 62% / 94% |
| goldak | keyhole | 60 | 0 | -6.4 | 12.5 | 31.5 | 98% / 100% | +2.4 | 21.3 | 70.9 | 77% / 98% |
| goldak | transition | 72 | 0 | -17.5 | 17.5 | 37.3 | 97% / 100% | -7.3 | 32.7 | 48.6 | 54% / 96% |

## Absorptivity sensitivity (SENSITIVITY, not a calibration)

SENSITIVITY, not a calibrated value: conduction-regime rows (regime assigned at the repo's default absorptivity), absorptivity_IR overridden uniformly via prop_overrides; the absorptivity actually acting in a physical track is unknown.

Conduction rows: 141.

| kernel | a=0.30 W MAPE % | a=0.40 W MAPE % | a=0.50 W MAPE % | a=0.60 W MAPE % | a=0.30 D MAPE % | a=0.40 D MAPE % | a=0.50 D MAPE % | a=0.60 D MAPE % | a=0.30 n | a=0.40 n | a=0.50 n | a=0.60 n |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | 49.9 | 37.2 | 22.0 | 12.8 | 34.6 | 30.0 | 45.9 | 90.0 | 15 | 26 | 37 | 48 |
| eagar-tsai | 23.1 | 15.6 | 11.5 | 9.9 | 30.5 | 28.7 | 39.5 | 56.2 | 140 | 141 | 141 | 141 |
| goldak | 41.2 | 31.4 | 23.6 | 17.4 | 29.7 | 42.0 | 60.3 | 76.6 | 103 | 126 | 136 | 139 |

Included row counts vary with assumed absorptivity: each column uses only rows where the kernel resolves an extent. These are different evaluation subsets; lower width error can accompany higher depth error. Sensitivity, not calibration.

## Reference transient (bare plate, low power)

This block depends on wall-clock budgets (total and per case): on a slower or busier host cases can turn into 'not-run (budget)', so it is not guaranteed to reproduce; `--reuse-reference` copies the block of an earlier record instead of re-running it. This record's block was reused from a record with sha256 `ce162c9100f4416c3028e3d779a73677eeba20e30fd9976d9ce540d127cbcae4` (LF-normalised).

Hofmann rows with t_powder = 0 (bare plate) and P <= 100 W (26 rows); all other rows are not run with the reference transient.
Completed 17, boiling stop 9, not run (budget) 0 of 26. sourcePenetration_um = 40 is an arbitrary, unvalidated choice for the bare-plate volumetric absorption depth; mesh 20 um is coarse relative to the 50-140 um spots and the result is not mesh-converged: every completed case has depth <= 2 cells, so its width/depth are cell-quantised (meshLimited = true) and carry almost no information about the measured track; a completed width of 0 means no resolved liquid extent. completed/boiling-stop is the reference transient's own validity stop; the widths/depths are a model comparison, not validation. Rows beyond the budget were skipped, not estimated.

| row | P W | v mm/s | d um | status | W pred | W meas | D pred | D meas |
|---|---|---|---|---|---|---|---|---|
| hofmann-0047 | 75 | 1050 | 50 | completed (mesh-limited) | 39.5 | 72.8 | 19.7 | 25.7 |
| hofmann-0083 | 100 | 600 | 110 | completed (mesh-limited) | 98.9 | 121.2 | 39.6 | 35.2 |
| hofmann-0102 | 100 | 300 | 80 | boiling-stop | - | 140.1 | - | 54.8 |
| hofmann-0156 | 75 | 750 | 80 | completed (mesh-limited) | 40.0 | 99.8 | 20.0 | 25.6 |
| hofmann-0164 | 50 | 600 | 80 | completed (mesh-limited) | 40.0 | 86.0 | 20.0 | 18.0 |
| hofmann-0241 | 50 | 900 | 50 | completed (mesh-limited) | 39.5 | 66.8 | 19.7 | 22.0 |
| hofmann-0245 | 100 | 900 | 50 | boiling-stop | - | 77.9 | - | 36.6 |
| hofmann-0269 | 100 | 300 | 80 | boiling-stop | - | 124.4 | - | 50.0 |
| hofmann-0301 | 100 | 1200 | 80 | completed (mesh-limited) | 40.0 | 104.9 | 20.0 | 21.6 |
| hofmann-0326 | 50 | 300 | 50 | boiling-stop | - | 80.8 | - | 33.4 |
| hofmann-0341 | 100 | 1200 | 50 | boiling-stop | - | 67.2 | - | 29.2 |
| hofmann-0346 | 100 | 1500 | 50 | completed (mesh-limited) | 39.5 | 69.9 | 19.7 | 26.1 |
| hofmann-0409 | 100 | 900 | 80 | completed (mesh-limited) | 80.0 | 87.6 | 40.0 | 30.3 |
| hofmann-0412 | 50 | 300 | 140 | completed (mesh-limited) | 60.0 | 112.9 | 20.0 | 14.9 |
| hofmann-0432 | 100 | 900 | 110 | completed (mesh-limited) | 59.4 | 107.1 | 19.8 | 24.1 |
| hofmann-0446 | 75 | 750 | 50 | boiling-stop | - | 69.0 | - | 29.8 |
| hofmann-0467 | 50 | 600 | 80 | completed (mesh-limited) | 40.0 | 88.2 | 20.0 | 18.0 |
| hofmann-0508 | 100 | 600 | 50 | boiling-stop | - | 92.7 | - | 53.3 |
| hofmann-0529 | 100 | 1050 | 80 | completed (mesh-limited) | 40.0 | 101.7 | 20.0 | 27.9 |
| hofmann-0541 | 50 | 300 | 110 | completed (mesh-limited) | 59.4 | 115.9 | 39.6 | 22.2 |
| hofmann-0544 | 50 | 450 | 50 | completed (mesh-limited) | 39.5 | 74.8 | 39.5 | 26.8 |
| hofmann-0563 | 100 | 600 | 140 | completed (mesh-limited) | 100.0 | 130.1 | 40.0 | 26.4 |
| hofmann-0606 | 100 | 450 | 50 | boiling-stop | - | 123.3 | - | 84.7 |
| hofmann-0608 | 50 | 1050 | 80 | completed (mesh-limited) | 0.0 | 71.1 | 0.0 | 14.6 |
| hofmann-0613 | 50 | 900 | 50 | completed (mesh-limited) | 39.5 | 52.4 | 19.7 | 20.9 |
| hofmann-0618 | 100 | 600 | 80 | boiling-stop | - | 96.1 | - | 38.1 |
