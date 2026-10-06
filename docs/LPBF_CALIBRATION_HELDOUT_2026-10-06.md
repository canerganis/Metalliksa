# LPBF held-out absorptivity calibration (2026-10-06)

**Held-out calibration of the Eagar-Tsai screening kernel's absorptivity against published single-track measurements; not experimental validation; absorptivity fitted, not measured; estimated material laws.**

Schema `lpbf-calibration-heldout-1`; implementation fingerprint `11b04b8fa3de1a6b2cf46afb67e6c439f05ca9d0ab2affec92f1e5b239eb3359`; code revision `b382889d9028ef3c649b346f5b586b9888cc98d0` (orch/calib; dirty tracked paths: 0); Python 3.12.10; quick mode: False. Evidence label: **Calibrated simulation (held-out calibration of one nuisance parameter against published single-track data; tested regime only)**; `experimentalValidation` = false; `opticalOperatorMatched` = false.

Honesty: held-out calibration, not experimental validation; the Eagar-Tsai screening kernel is read-only; absorptivity is a fitted nuisance parameter, not a measured one; estimated material laws; published single-track measurements without an uncertainty model; a calibration that does not beat the physics-free baseline is reported as such.

## What was done

- Kernel: lpbf_thermal_solver.calculate_meltpool_physics(heat_source='eagar-tsai'), flat-plate (sys.modules['powder_bed_raytracer'] = None, as in the comparison harness); varied: prop_overrides={'absorptivity_IR': a}; nothing else is changed; second scalar: none fitted (the regime variant is a class-wise absorptivity, not a second physical parameter). Solver calls 28009, flat-plate fallback warnings 28009 (table source: cache et_grid_table.json).
- Grid: 37 absorptivity values from 0.20 to 0.90 (step 0.02, plus the material defaults).
- Loss: per row 0.5 * (|ln(W_pred/W_meas)| + |ln(D_pred/D_meas)|); rows of one parameter set are averaged first, then the mean over the training parameter sets is minimised on the absorptivity grid (argmin, ties to the smaller value). A grid value is a candidate only when the kernel resolves an extent (extentStatus == 'computed') for at least 98% of the training rows.
- Split: parameter set = (material, power_W, speed_mm_s, beamDiameter_um); powder-layer thickness is deliberately NOT part of the key, so replicates and layer variants of one laser setting are always on the same side of a split. Folds: the sorted set keys are shuffled with random.Random(seed) and dealt round-robin into k folds. k = 5, seeds [0, 1, 2]; bootstrap 1000 replicates, seed 0.
- Models: **default** = uncalibrated harness absorptivity (316L Stainless Steel 0.42, Ti-6Al-4V 0.35); no fitting; **const** = one absorptivity per training fold (grid argmin of the loss); **regime** = one absorptivity per input-only enthalpy class; a class with fewer than 8 training sets inherits the const value; **powerlaw** = ln W (and ln D) = c + a ln P + b ln v + e ln d fitted on the training fold; no physics.
- Skill: 1 - metric(model)/metric(baseline) on the same held-out rows; paired cluster-bootstrap CI; verdict 'beats' only when the whole 95 % interval is above 0.

## Datasets

- **hofmann-316l-2026** (316L Stainless Steel): DOI 10.5281/zenodo.16979848, CC BY 4.0, 677 rows, table sha256 `d4bbc7a60b536118586f44b64beb0fa20f94133f6d1a8d0fdcf726003720c3d8`. Hofmann et al., melt-pool geometry data for 316L single tracks (Aconity Midi), Zenodo 10.5281/zenodo.16979848 (v1, 2025-08-28); associated paper Materials & Design 262 (2026) 115459, doi:10.1016/j.matdes.2026.115459.
- **totis-ti64-2021** (Ti-6Al-4V): DOI 10.17632/s9438vb5xd.1, CC BY 4.0, 80 rows, table sha256 `3b5794f3a25a5f67fa0d8d1ab006834205ef820b046c24deb15836025825d623`. Totis, Vaglio et al., single-track Ti6Al4V SEM images and geometrical data (Concept Laser M2, 50 um laser spot), Mendeley Data, 10.17632/s9438vb5xd.1 (v1, 2021-04-26); related article Data in Brief, doi:10.1016/j.dib.2020.106443.

Counts: Hofmann 677 rows = 378 distinct (P, v, d) sets (623 with the powder layer in the key); Totis 80 rows = 80 sets. Rows by input-only class: {'conduction': 172, 'transition': 303, 'keyhole': 282}; by harness label: {'balling-flagged': 216, 'conduction': 141, 'keyhole': 194, 'transition': 206}.

## Headline verdicts (held-out, paired bootstrap)

**Grouped 5-fold CV, hofmann-316l-2026 (seed 0)**
- const vs default (width): skill (MAPE) 0.15 [0.13, 0.17] -> **beats**
- const vs default (depth): skill (MAPE) -0.19 [-0.24, -0.15] -> **does not beat**
- const vs powerlaw (width): skill (MAPE) -0.20 [-0.27, -0.13] -> **does not beat**
- const vs powerlaw (depth): skill (MAPE) -0.26 [-0.37, -0.15] -> **does not beat**
- regime vs default (width): skill (MAPE) 0.16 [0.13, 0.18] -> **beats**
- regime vs default (depth): skill (MAPE) -0.17 [-0.23, -0.12] -> **does not beat**
- regime vs powerlaw (width): skill (MAPE) -0.19 [-0.26, -0.12] -> **does not beat**
- regime vs powerlaw (depth): skill (MAPE) -0.23 [-0.34, -0.13] -> **does not beat**

**Grouped 5-fold CV, totis-ti64-2021 (seed 0)**
- const vs default (width): skill (MAPE) -0.09 [-0.22, 0.01] -> **inconclusive**
- const vs default (depth): skill (MAPE) 0.01 [-0.12, 0.16] -> **inconclusive**
- const vs powerlaw (width): skill (MAPE) -0.84 [-1.25, -0.51] -> **does not beat**
- const vs powerlaw (depth): skill (MAPE) -0.24 [-0.39, -0.12] -> **does not beat**
- regime vs default (width): skill (MAPE) 0.03 [-0.07, 0.12] -> **inconclusive**
- regime vs default (depth): skill (MAPE) 0.01 [-0.10, 0.13] -> **inconclusive**
- regime vs powerlaw (width): skill (MAPE) -0.64 [-1.01, -0.34] -> **does not beat**
- regime vs powerlaw (depth): skill (MAPE) -0.24 [-0.40, -0.11] -> **does not beat**

**Leave-one-dataset-out, train=hofmann-316l-2026;test=totis-ti64-2021 (cross-material transfer)**
- const vs default (width): skill (MAPE) -0.15 [-0.32, -0.01] -> **does not beat**
- const vs default (depth): skill (MAPE) -0.04 [-0.21, 0.15] -> **inconclusive**
- const vs powerlaw (width): skill (MAPE) -0.22 [-0.40, -0.06] -> **does not beat**
- const vs powerlaw (depth): skill (MAPE) 0.20 [-0.07, 0.44] -> **inconclusive**
- regime vs default (width): skill (MAPE) -0.08 [-0.22, 0.05] -> **inconclusive**
- regime vs default (depth): skill (MAPE) -0.01 [-0.16, 0.16] -> **inconclusive**
- regime vs powerlaw (width): skill (MAPE) -0.14 [-0.30, -0.00] -> **does not beat**
- regime vs powerlaw (depth): skill (MAPE) 0.23 [-0.03, 0.45] -> **inconclusive**

**Leave-one-dataset-out, train=totis-ti64-2021;test=hofmann-316l-2026 (cross-material transfer)**
- const vs default (width): skill (MAPE) 0.00 [0.00, 0.00] -> **inconclusive**
- const vs default (depth): skill (MAPE) 0.00 [0.00, 0.00] -> **inconclusive**
- const vs powerlaw (width): skill (MAPE) 0.25 [0.20, 0.30] -> **beats**
- const vs powerlaw (depth): skill (MAPE) 0.89 [0.88, 0.90] -> **beats**
- regime vs default (width): skill (MAPE) 0.02 [-0.01, 0.05] -> **inconclusive**
- regime vs default (depth): skill (MAPE) -0.04 [-0.11, 0.01] -> **inconclusive**
- regime vs powerlaw (width): skill (MAPE) 0.27 [0.21, 0.32] -> **beats**
- regime vs powerlaw (depth): skill (MAPE) 0.89 [0.87, 0.90] -> **beats**

## Grouped k-fold cross-validation (per dataset, no cross-material mixing)

### hofmann-316l-2026, seed 0 (primary: bootstrap intervals, breakdown)

n = 677 held-out rows (378 parameter sets), 0 excluded (not resolved by every compared model). Bias = mean((pred-meas)/meas); MAE in um; 95 % intervals = cluster bootstrap by parameter set.

| model | W bias % | W MAE um | W MAPE % | D bias % | D MAE um | D MAPE % | W skill vs default / powerlaw | D skill vs default / powerlaw |
|---|---|---|---|---|---|---|---|---|
| default | -10.5 [-11.3, -9.6] | 23.3 [22.0, 24.7] | 13.4 [12.8, 14.1] | +13.4 [8.8, 18.3] | 30.5 [27.3, 33.7] | 34.0 [30.4, 38.1] | - / -0.41 [-0.50, -0.32] | - / -0.05 [-0.14, 0.03] |
| const | -6.1 [-7.1, -5.1] | 19.4 [18.2, 20.7] | 11.4 [10.8, 12.1] | +29.7 [24.6, 35.2] | 32.0 [29.0, 35.3] | 40.5 [35.9, 45.6] | +0.15 [0.13, 0.17] / -0.20 [-0.27, -0.13] | -0.19 [-0.24, -0.15] / -0.26 [-0.37, -0.15] |
| regime | -6.8 [-7.7, -5.9] | 19.3 [18.2, 20.6] | 11.4 [10.8, 12.0] | +29.0 [23.8, 34.4] | 31.6 [28.5, 34.9] | 39.8 [35.6, 44.5] | +0.16 [0.13, 0.18] / -0.19 [-0.26, -0.12] | -0.17 [-0.23, -0.12] / -0.23 [-0.34, -0.13] |
| powerlaw | +0.9 [0.1, 1.9] | 15.1 [14.1, 16.2] | 9.5 [8.9, 10.3] | +14.1 [9.6, 18.9] | 26.8 [24.1, 29.7] | 32.2 [28.5, 36.0] | +0.29 [0.24, 0.33] / - | +0.05 [-0.03, 0.12] / - |

Fits per fold (train side only; `*` = class fell back to the const value for lack of training sets):

- fold 0 (train 302 sets / test 76 sets): const a = 0.46 (train loss 0.198, 302 sets); regime a = conduction 0.44, transition 0.48, keyhole 0.44; power law W: p^+0.39, s^-0.29, b^+0.30; D: p^+1.14, s^-1.11, b^-1.13
- fold 1 (train 302 sets / test 76 sets): const a = 0.48 (train loss 0.202, 302 sets); regime a = conduction 0.46, transition 0.50, keyhole 0.44; power law W: p^+0.39, s^-0.29, b^+0.30; D: p^+1.12, s^-1.11, b^-1.11
- fold 2 (train 302 sets / test 76 sets): const a = 0.48 (train loss 0.202, 302 sets); regime a = conduction 0.46, transition 0.48, keyhole 0.44; power law W: p^+0.39, s^-0.29, b^+0.30; D: p^+1.14, s^-1.09, b^-1.12
- fold 3 (train 303 sets / test 75 sets): const a = 0.46 (train loss 0.192, 303 sets); regime a = conduction 0.44, transition 0.48, keyhole 0.44; power law W: p^+0.39, s^-0.29, b^+0.31; D: p^+1.18, s^-1.09, b^-1.17
- fold 4 (train 303 sets / test 75 sets): const a = 0.46 (train loss 0.202, 303 sets); regime a = conduction 0.44, transition 0.48, keyhole 0.44; power law W: p^+0.39, s^-0.29, b^+0.30; D: p^+1.22, s^-1.14, b^-1.24

Held-out breakdown by harness regime label (point values, no intervals; the balling flag enters the label only):

| regime label (harness) | n | model | W bias % | W MAPE % | D bias % | D MAPE % |
|---|---|---|---|---|---|---|
| balling-flagged | 216 | default | -10.1 | 14.6 | +37.9 | 50.8 |
| balling-flagged | 216 | const | -6.0 | 13.3 | +56.9 | 63.7 |
| balling-flagged | 216 | regime | -6.7 | 13.1 | +56.0 | 62.7 |
| balling-flagged | 216 | powerlaw | +3.9 | 12.4 | +28.0 | 41.4 |
| conduction | 133 | default | -12.2 | 14.1 | +14.9 | 24.8 |
| conduction | 133 | const | -8.8 | 12.1 | +24.6 | 29.4 |
| conduction | 133 | regime | -10.2 | 12.9 | +20.6 | 27.2 |
| conduction | 133 | powerlaw | +1.2 | 9.4 | +10.8 | 32.4 |
| keyhole | 137 | default | -5.6 | 10.4 | +5.5 | 24.0 |
| keyhole | 137 | const | -0.0 | 9.2 | +18.4 | 28.7 |
| keyhole | 137 | regime | -3.4 | 9.7 | +10.5 | 25.2 |
| keyhole | 137 | powerlaw | -1.7 | 7.2 | -5.1 | 20.2 |
| transition | 191 | default | -13.2 | 13.9 | -9.8 | 28.5 |
| transition | 191 | const | -8.7 | 10.4 | +10.6 | 30.6 |
| transition | 191 | regime | -7.2 | 9.6 | +17.6 | 33.1 |
| transition | 191 | powerlaw | -0.7 | 8.1 | +14.4 | 30.3 |

### hofmann-316l-2026, seed 1 (stability repeat, point values)

n = 677 held-out rows (378 parameter sets), 0 excluded (not resolved by every compared model). Bias = mean((pred-meas)/meas); MAE in um; 95 % intervals = cluster bootstrap by parameter set.

| model | W bias % | W MAE um | W MAPE % | D bias % | D MAE um | D MAPE % | W skill vs default / powerlaw | D skill vs default / powerlaw |
|---|---|---|---|---|---|---|---|---|
| default | -10.5 | 23.3 | 13.4 | +13.4 | 30.5 | 34.0 | - / -0.40 | - / -0.06 |
| const | -6.9 | 19.8 | 11.6 | +26.9 | 31.0 | 38.9 | +0.14 / -0.21 | -0.15 / -0.21 |
| regime | -6.9 | 19.3 | 11.4 | +28.8 | 31.6 | 39.6 | +0.15 / -0.19 | -0.17 / -0.23 |
| powerlaw | +1.0 | 15.2 | 9.6 | +13.9 | 26.7 | 32.1 | +0.29 / - | +0.06 / - |

Fits per fold (train side only; `*` = class fell back to the const value for lack of training sets):

- fold 0 (train 302 sets / test 76 sets): const a = 0.46 (train loss 0.191, 302 sets); regime a = conduction 0.46, transition 0.48, keyhole 0.44; power law W: p^+0.38, s^-0.28, b^+0.32; D: p^+1.18, s^-1.10, b^-1.19
- fold 1 (train 302 sets / test 76 sets): const a = 0.46 (train loss 0.202, 302 sets); regime a = conduction 0.44, transition 0.48, keyhole 0.44; power law W: p^+0.39, s^-0.29, b^+0.31; D: p^+1.17, s^-1.10, b^-1.14
- fold 2 (train 302 sets / test 76 sets): const a = 0.46 (train loss 0.203, 302 sets); regime a = conduction 0.44, transition 0.50, keyhole 0.44; power law W: p^+0.39, s^-0.30, b^+0.28; D: p^+1.11, s^-1.13, b^-1.13
- fold 3 (train 303 sets / test 75 sets): const a = 0.46 (train loss 0.201, 303 sets); regime a = conduction 0.44, transition 0.48, keyhole 0.44; power law W: p^+0.40, s^-0.30, b^+0.29; D: p^+1.17, s^-1.12, b^-1.18
- fold 4 (train 303 sets / test 75 sets): const a = 0.46 (train loss 0.200, 303 sets); regime a = conduction 0.46, transition 0.48, keyhole 0.44; power law W: p^+0.39, s^-0.28, b^+0.30; D: p^+1.17, s^-1.09, b^-1.13

### hofmann-316l-2026, seed 2 (stability repeat, point values)

n = 677 held-out rows (378 parameter sets), 0 excluded (not resolved by every compared model). Bias = mean((pred-meas)/meas); MAE in um; 95 % intervals = cluster bootstrap by parameter set.

| model | W bias % | W MAE um | W MAPE % | D bias % | D MAE um | D MAPE % | W skill vs default / powerlaw | D skill vs default / powerlaw |
|---|---|---|---|---|---|---|---|---|
| default | -10.5 | 23.3 | 13.4 | +13.4 | 30.5 | 34.0 | - / -0.41 | - / -0.06 |
| const | -6.5 | 19.6 | 11.5 | +28.2 | 31.7 | 39.7 | +0.15 / -0.20 | -0.17 / -0.24 |
| regime | -7.0 | 19.5 | 11.4 | +27.9 | 31.2 | 39.0 | +0.15 / -0.20 | -0.15 / -0.22 |
| powerlaw | +0.9 | 15.2 | 9.5 | +13.7 | 26.6 | 32.0 | +0.29 / - | +0.06 / - |

Fits per fold (train side only; `*` = class fell back to the const value for lack of training sets):

- fold 0 (train 302 sets / test 76 sets): const a = 0.46 (train loss 0.198, 302 sets); regime a = conduction 0.44, transition 0.48, keyhole 0.44; power law W: p^+0.40, s^-0.29, b^+0.30; D: p^+1.16, s^-1.11, b^-1.16
- fold 1 (train 302 sets / test 76 sets): const a = 0.46 (train loss 0.200, 302 sets); regime a = conduction 0.46, transition 0.48, keyhole 0.44; power law W: p^+0.39, s^-0.29, b^+0.30; D: p^+1.13, s^-1.14, b^-1.13
- fold 2 (train 302 sets / test 76 sets): const a = 0.46 (train loss 0.202, 302 sets); regime a = conduction 0.44, transition 0.48, keyhole 0.44; power law W: p^+0.39, s^-0.28, b^+0.30; D: p^+1.17, s^-1.09, b^-1.12
- fold 3 (train 303 sets / test 75 sets): const a = 0.46 (train loss 0.196, 303 sets); regime a = conduction 0.44, transition 0.48, keyhole 0.44; power law W: p^+0.40, s^-0.29, b^+0.31; D: p^+1.19, s^-1.13, b^-1.20
- fold 4 (train 303 sets / test 75 sets): const a = 0.48 (train loss 0.200, 303 sets); regime a = conduction 0.46, transition 0.48, keyhole 0.44; power law W: p^+0.38, s^-0.29, b^+0.30; D: p^+1.14, s^-1.08, b^-1.16

### totis-ti64-2021, seed 0 (primary: bootstrap intervals, breakdown)

n = 80 held-out rows (80 parameter sets), 0 excluded (not resolved by every compared model). Bias = mean((pred-meas)/meas); MAE in um; 95 % intervals = cluster bootstrap by parameter set.

| model | W bias % | W MAE um | W MAPE % | D bias % | D MAE um | D MAPE % | W skill vs default / powerlaw | D skill vs default / powerlaw |
|---|---|---|---|---|---|---|---|---|
| default | -8.1 [-12.5, -3.8] | 21.2 [18.0, 24.5] | 18.1 [15.7, 20.4] | -10.1 [-19.8, 0.4] | 62.5 [48.4, 79.4] | 34.9 [28.9, 42.8] | - / -0.68 [-1.04, -0.37] | - / -0.26 [-0.46, -0.11] |
| const | +1.0 [-3.9, 5.8] | 23.9 [20.5, 27.7] | 19.7 [17.4, 22.0] | +11.9 [0.7, 24.3] | 42.1 [34.1, 51.1] | 34.4 [26.1, 44.8] | -0.09 [-0.22, 0.01] / -0.84 [-1.25, -0.51] | +0.01 [-0.12, 0.16] / -0.24 [-0.39, -0.12] |
| regime | -0.3 [-4.7, 4.1] | 21.3 [18.1, 24.7] | 17.6 [15.4, 19.8] | +11.9 [0.8, 24.3] | 46.8 [36.9, 57.8] | 34.5 [26.2, 44.8] | +0.03 [-0.07, 0.12] / -0.64 [-1.01, -0.34] | +0.01 [-0.10, 0.13] / -0.24 [-0.40, -0.11] |
| powerlaw | +1.3 [-1.7, 4.8] | 11.2 [9.4, 13.0] | 10.7 [8.6, 13.3] | +7.3 [-2.0, 17.1] | 40.5 [29.2, 54.1] | 27.7 [20.8, 36.0] | +0.40 [0.27, 0.51] / - | +0.20 [0.10, 0.32] / - |

Fits per fold (train side only; `*` = class fell back to the const value for lack of training sets):

- fold 0 (train 64 sets / test 16 sets): const a = 0.42 (train loss 0.250, 64 sets); regime a = conduction 0.42*, transition 0.48, keyhole 0.40; power law W: p^+0.18, s^-0.38; D: p^+1.29, s^-1.00
- fold 1 (train 64 sets / test 16 sets): const a = 0.42 (train loss 0.233, 64 sets); regime a = conduction 0.42*, transition 0.48, keyhole 0.40; power law W: p^+0.20, s^-0.39; D: p^+1.26, s^-0.97
- fold 2 (train 64 sets / test 16 sets): const a = 0.46 (train loss 0.244, 64 sets); regime a = conduction 0.46*, transition 0.48, keyhole 0.42; power law W: p^+0.20, s^-0.38; D: p^+1.42, s^-0.98
- fold 3 (train 64 sets / test 16 sets): const a = 0.42 (train loss 0.257, 64 sets); regime a = conduction 0.35, transition 0.48, keyhole 0.40; power law W: p^+0.21, s^-0.41; D: p^+1.30, s^-0.99
- fold 4 (train 64 sets / test 16 sets): const a = 0.42 (train loss 0.250, 64 sets); regime a = conduction 0.42*, transition 0.50, keyhole 0.40; power law W: p^+0.18, s^-0.40; D: p^+1.31, s^-0.98

Held-out breakdown by harness regime label (point values, no intervals; the balling flag enters the label only):

| regime label (harness) | n | model | W bias % | W MAPE % | D bias % | D MAPE % |
|---|---|---|---|---|---|---|
| conduction | 8 | default | -18.9 | 25.4 | +55.7 | 90.5 |
| conduction | 8 | const | -13.0 | 21.5 | +81.7 | 113.8 |
| conduction | 8 | regime | -13.0 | 21.5 | +81.7 | 113.8 |
| conduction | 8 | powerlaw | +20.0 | 20.6 | +50.4 | 85.6 |
| keyhole | 57 | default | -0.0 | 13.1 | -11.9 | 26.2 |
| keyhole | 57 | const | +10.4 | 17.5 | +8.1 | 26.2 |
| keyhole | 57 | regime | +7.3 | 15.7 | +1.8 | 24.7 |
| keyhole | 57 | powerlaw | +1.4 | 7.5 | +7.6 | 21.5 |
| transition | 15 | default | -33.0 | 33.0 | -38.2 | 38.2 |
| transition | 15 | const | -27.3 | 27.3 | -10.5 | 23.4 |
| transition | 15 | regime | -22.5 | 22.5 | +13.2 | 29.4 |
| transition | 15 | powerlaw | -8.8 | 17.9 | -16.8 | 20.4 |

### totis-ti64-2021, seed 1 (stability repeat, point values)

n = 80 held-out rows (80 parameter sets), 0 excluded (not resolved by every compared model). Bias = mean((pred-meas)/meas); MAE in um; 95 % intervals = cluster bootstrap by parameter set.

| model | W bias % | W MAE um | W MAPE % | D bias % | D MAE um | D MAPE % | W skill vs default / powerlaw | D skill vs default / powerlaw |
|---|---|---|---|---|---|---|---|---|
| default | -8.1 | 21.2 | 18.1 | -10.1 | 62.5 | 34.9 | - / -0.68 | - / -0.26 |
| const | +1.4 | 24.1 | 19.9 | +13.4 | 41.2 | 36.1 | -0.10 / -0.86 | -0.04 / -0.30 |
| regime | -0.4 | 21.4 | 17.7 | +11.4 | 46.7 | 34.4 | +0.02 / -0.66 | +0.01 / -0.24 |
| powerlaw | +1.2 | 11.2 | 10.7 | +7.6 | 37.7 | 27.8 | +0.41 / - | +0.20 / - |

Fits per fold (train side only; `*` = class fell back to the const value for lack of training sets):

- fold 0 (train 64 sets / test 16 sets): const a = 0.40 (train loss 0.261, 64 sets); regime a = conduction 0.40*, transition 0.46, keyhole 0.40; power law W: p^+0.19, s^-0.40; D: p^+1.31, s^-1.01
- fold 1 (train 64 sets / test 16 sets): const a = 0.42 (train loss 0.239, 64 sets); regime a = conduction 0.42*, transition 0.48, keyhole 0.40; power law W: p^+0.20, s^-0.39; D: p^+1.40, s^-0.96
- fold 2 (train 64 sets / test 16 sets): const a = 0.46 (train loss 0.239, 64 sets); regime a = conduction 0.46*, transition 0.48, keyhole 0.40; power law W: p^+0.20, s^-0.38; D: p^+1.24, s^-0.95
- fold 3 (train 64 sets / test 16 sets): const a = 0.46 (train loss 0.250, 64 sets); regime a = conduction 0.46*, transition 0.48, keyhole 0.42; power law W: p^+0.21, s^-0.38; D: p^+1.33, s^-0.99
- fold 4 (train 64 sets / test 16 sets): const a = 0.42 (train loss 0.244, 64 sets); regime a = conduction 0.42*, transition 0.48, keyhole 0.40; power law W: p^+0.18, s^-0.40; D: p^+1.30, s^-1.00

### totis-ti64-2021, seed 2 (stability repeat, point values)

n = 80 held-out rows (80 parameter sets), 0 excluded (not resolved by every compared model). Bias = mean((pred-meas)/meas); MAE in um; 95 % intervals = cluster bootstrap by parameter set.

| model | W bias % | W MAE um | W MAPE % | D bias % | D MAE um | D MAPE % | W skill vs default / powerlaw | D skill vs default / powerlaw |
|---|---|---|---|---|---|---|---|---|
| default | -8.1 | 21.2 | 18.1 | -10.1 | 62.5 | 34.9 | - / -0.66 | - / -0.24 |
| const | +1.9 | 24.1 | 20.1 | +14.5 | 40.5 | 35.2 | -0.11 / -0.84 | -0.01 / -0.25 |
| regime | -0.9 | 21.2 | 17.5 | +10.2 | 47.1 | 33.7 | +0.03 / -0.61 | +0.03 / -0.20 |
| powerlaw | +1.2 | 11.2 | 10.9 | +7.5 | 42.9 | 28.2 | +0.40 / - | +0.19 / - |

Fits per fold (train side only; `*` = class fell back to the const value for lack of training sets):

- fold 0 (train 64 sets / test 16 sets): const a = 0.46 (train loss 0.258, 64 sets); regime a = conduction 0.46*, transition 0.48, keyhole 0.40; power law W: p^+0.20, s^-0.38; D: p^+1.29, s^-0.97
- fold 1 (train 64 sets / test 16 sets): const a = 0.42 (train loss 0.242, 64 sets); regime a = conduction 0.42*, transition 0.48, keyhole 0.40; power law W: p^+0.20, s^-0.40; D: p^+1.42, s^-0.99
- fold 2 (train 64 sets / test 16 sets): const a = 0.46 (train loss 0.248, 64 sets); regime a = conduction 0.35, transition 0.48, keyhole 0.40; power law W: p^+0.22, s^-0.40; D: p^+1.34, s^-1.04
- fold 3 (train 64 sets / test 16 sets): const a = 0.42 (train loss 0.240, 64 sets); regime a = conduction 0.42*, transition 0.48, keyhole 0.40; power law W: p^+0.20, s^-0.39; D: p^+1.25, s^-0.97
- fold 4 (train 64 sets / test 16 sets): const a = 0.42 (train loss 0.247, 64 sets); regime a = conduction 0.42*, transition 0.46, keyhole 0.40; power law W: p^+0.16, s^-0.39; D: p^+1.29, s^-0.95

## Leave-one-dataset-out (cross-material transfer)

### train=hofmann-316l-2026;test=totis-ti64-2021

absorptivity fitted on 316L Stainless Steel (hofmann-316l-2026) and applied to Ti-6Al-4V (totis-ti64-2021): a cross-material transfer of a nuisance parameter; the power-law baseline is likewise fitted on one material and applied to the other.

Fits: const a = 0.46 (train loss 0.199, 378 sets); regime a = conduction 0.44, transition 0.48, keyhole 0.44; power law W: p^+0.39, s^-0.29, b^+0.30; D: p^+1.16, s^-1.11, b^-1.15

n = 80 held-out rows (80 parameter sets), 0 excluded (not resolved by every compared model). Bias = mean((pred-meas)/meas); MAE in um; 95 % intervals = cluster bootstrap by parameter set.

| model | W bias % | W MAE um | W MAPE % | D bias % | D MAE um | D MAPE % | W skill vs default / powerlaw | D skill vs default / powerlaw |
|---|---|---|---|---|---|---|---|---|
| default | -8.1 [-12.5, -3.8] | 21.2 [18.0, 24.5] | 18.1 [15.7, 20.4] | -10.1 [-19.8, 0.4] | 62.5 [48.4, 79.4] | 34.9 [28.9, 42.8] | - / -0.06 [-0.17, 0.04] | - / +0.23 [0.05, 0.38] |
| const | +4.5 [-0.6, 9.5] | 25.4 [21.7, 29.5] | 20.7 [18.4, 23.2] | +21.0 [9.1, 33.9] | 35.6 [29.6, 42.6] | 36.2 [26.4, 47.9] | -0.15 [-0.32, -0.01] / -0.22 [-0.40, -0.06] | -0.04 [-0.21, 0.15] / +0.20 [-0.07, 0.44] |
| regime | +2.9 [-2.0, 7.6] | 23.7 [20.2, 27.5] | 19.4 [17.1, 21.8] | +18.2 [6.5, 30.5] | 38.9 [31.5, 47.2] | 35.1 [25.8, 46.2] | -0.08 [-0.22, 0.05] / -0.14 [-0.30, -0.00] | -0.01 [-0.16, 0.16] / +0.23 [-0.03, 0.45] |
| powerlaw | -6.9 [-11.0, -2.9] | 20.3 [17.2, 24.1] | 17.0 [14.7, 19.4] | -40.4 [-46.1, -34.3] | 92.2 [74.7, 111.0] | 45.4 [41.7, 48.8] | +0.06 [-0.04, 0.14] / - | -0.30 [-0.61, -0.05] / - |

Breakdown by harness regime label:

| regime label (harness) | n | model | W bias % | W MAPE % | D bias % | D MAPE % |
|---|---|---|---|---|---|---|
| conduction | 8 | default | -18.9 | 25.4 | +55.7 | 90.5 |
| conduction | 8 | const | -10.9 | 20.4 | +93.1 | 124.6 |
| conduction | 8 | regime | -12.2 | 21.3 | +87.0 | 119.0 |
| conduction | 8 | powerlaw | -13.4 | 21.9 | -7.5 | 38.8 |
| keyhole | 57 | default | -0.0 | 13.1 | -11.9 | 26.2 |
| keyhole | 57 | const | +14.3 | 19.8 | +15.8 | 26.9 |
| keyhole | 57 | regime | +11.8 | 18.2 | +10.7 | 25.6 |
| keyhole | 57 | powerlaw | -1.0 | 13.9 | -42.6 | 45.3 |
| transition | 15 | default | -33.0 | 33.0 | -38.2 | 38.2 |
| transition | 15 | const | -24.6 | 24.6 | +2.6 | 24.2 |
| transition | 15 | regime | -23.2 | 23.2 | +9.8 | 26.2 |
| transition | 15 | powerlaw | -25.8 | 25.8 | -49.5 | 49.5 |

### train=totis-ti64-2021;test=hofmann-316l-2026

absorptivity fitted on Ti-6Al-4V (totis-ti64-2021) and applied to 316L Stainless Steel (hofmann-316l-2026): a cross-material transfer of a nuisance parameter; the power-law baseline is likewise fitted on one material and applied to the other.

Fits: const a = 0.42 (train loss 0.247, 80 sets); regime a = conduction 0.35, transition 0.48, keyhole 0.40; power law W: p^+0.19, s^-0.39; D: p^+1.32, s^-0.98

n = 677 held-out rows (378 parameter sets), 0 excluded (not resolved by every compared model). Bias = mean((pred-meas)/meas); MAE in um; 95 % intervals = cluster bootstrap by parameter set.

| model | W bias % | W MAE um | W MAPE % | D bias % | D MAE um | D MAPE % | W skill vs default / powerlaw | D skill vs default / powerlaw |
|---|---|---|---|---|---|---|---|---|
| default | -10.5 [-11.3, -9.6] | 23.3 [22.0, 24.7] | 13.4 [12.8, 14.1] | +13.4 [8.8, 18.3] | 30.5 [27.3, 33.7] | 34.0 [30.4, 38.1] | - / +0.25 [0.20, 0.30] | - / +0.89 [0.88, 0.90] |
| const | -10.5 [-11.3, -9.6] | 23.3 [22.0, 24.7] | 13.4 [12.8, 14.1] | +13.4 [8.8, 18.3] | 30.5 [27.3, 33.7] | 34.0 [30.4, 38.1] | +0.00 [0.00, 0.00] / +0.25 [0.20, 0.30] | +0.00 [0.00, 0.00] / +0.89 [0.88, 0.90] |
| regime | -10.3 [-11.2, -9.4] | 22.5 [21.1, 23.8] | 13.2 [12.5, 13.9] | +18.2 [13.4, 23.1] | 31.0 [27.7, 34.3] | 35.5 [31.6, 39.7] | +0.02 [-0.01, 0.05] / +0.27 [0.21, 0.32] | -0.04 [-0.11, 0.01] / +0.89 [0.87, 0.90] |
| powerlaw | -5.2 [-7.3, -3.0] | 30.6 [28.4, 32.8] | 18.0 [16.9, 19.2] | +317.0 [293.7, 340.4] | 275.5 [248.4, 304.0] | 317.0 [293.7, 340.4] | -0.34 [-0.44, -0.25] / - | -8.33 [-9.52, -7.28] / - |

Breakdown by harness regime label:

| regime label (harness) | n | model | W bias % | W MAPE % | D bias % | D MAPE % |
|---|---|---|---|---|---|---|
| balling-flagged | 216 | default | -10.1 | 14.6 | +37.9 | 50.8 |
| balling-flagged | 216 | const | -10.1 | 14.6 | +37.9 | 50.8 |
| balling-flagged | 216 | regime | -9.5 | 14.1 | +44.2 | 53.9 |
| balling-flagged | 216 | powerlaw | -8.5 | 18.8 | +364.4 | 364.4 |
| conduction | 133 | default | -12.2 | 14.1 | +14.9 | 24.8 |
| conduction | 133 | const | -12.2 | 14.1 | +14.9 | 24.8 |
| conduction | 133 | regime | -17.7 | 18.5 | -0.7 | 24.0 |
| conduction | 133 | powerlaw | -2.7 | 19.9 | +375.9 | 375.9 |
| keyhole | 137 | default | -5.6 | 10.4 | +5.5 | 24.0 |
| keyhole | 137 | const | -5.6 | 10.4 | +5.5 | 24.0 |
| keyhole | 137 | regime | -7.8 | 11.4 | -0.0 | 23.3 |
| keyhole | 137 | powerlaw | -4.2 | 13.8 | +182.7 | 182.8 |
| transition | 191 | default | -13.2 | 13.9 | -9.8 | 28.5 |
| transition | 191 | const | -13.2 | 13.9 | -9.8 | 28.5 |
| transition | 191 | regime | -7.6 | 9.8 | +15.1 | 31.2 |
| transition | 191 | powerlaw | -4.0 | 18.7 | +318.8 | 318.8 |

## In-sample reference (optimistic, not held-out)

Fit and score on the same rows; shown only so the held-out gap is visible.

| dataset | const a | regime a | W MAPE % default / const / regime / powerlaw | D MAPE % default / const / regime / powerlaw |
|---|---|---|---|---|
| hofmann-316l-2026 | 0.46 | conduction 0.44, transition 0.48, keyhole 0.44 | 13.4 / 11.6 / 11.5 / 9.5 | 34.0 / 38.9 / 38.8 / 31.5 |
| totis-ti64-2021 | 0.42 | conduction 0.35, transition 0.48, keyhole 0.40 | 18.1 / 19.3 / 17.8 / 10.5 | 34.9 / 33.3 / 31.1 / 25.7 |

## What this does not show

- It is not experimental validation and it does not establish the kernel as a general model of melt-pool geometry: one nuisance parameter was fitted to published cross-section measurements and the error on rows the fit did not see is reported. The evidence label is at most 'Calibrated simulation' for the tested regime; experimentalValidation stays false.
- There is no uncertainty model for the measurements: neither dataset gives per-row measurement uncertainty, sectioning position or replicate scatter (Totis has one track per cell). The bootstrap intervals cover resampling of parameter sets only, not measurement error, the estimated material laws or the regime rule.
- Absorptivity is a fitted nuisance parameter, not a measured one. The fitted value absorbs every other model error (material laws, the Fabbro keyhole term, the flat-plate path, the assumed 1/e^2 spot definition, the 20 C preheat assumption) and must not be read as the physical absorptivity of 316L or Ti-6Al-4V.
- Conduction and keyhole regimes are mixed: the 'regime' calibration assigns classes from an input-only normalised-enthalpy screen at the default absorptivity, not from the papers' regime definitions; the 216 balling-flagged Hofmann rows stay inside the headline numbers (the flag is a measured outcome and is not used for fitting); the Totis depth reference line is not stated by the source.
- The datasets are small: 677 Hofmann rows (378 distinct (P, v, d) sets) and 80 Totis rows; a 5-fold split leaves one fifth of each for testing, and the leave-one-dataset-out transfer rests on a single pair of datasets.
- Laser, powder, atmosphere and machine differ between the datasets (Aconity Midi, bare plate and 30/60 um 316L powder layers vs Concept Laser M2, 25 um Ti-6Al-4V layer over a printed base); the kernel ignores the powder layer entirely, and a cross-material transfer of a fitted absorptivity has no physical justification. It is reported because it is the only out-of-distribution test available here.
- The grid search is bounded (absorptivity 0.20 to 0.90); a fit at the grid edge is flagged, not extrapolated.
- The kernel's own inclusion rule (extentStatus == 'computed') selects the scored rows; rows any compared model does not resolve are excluded and counted, not estimated.

## Assumptions

- **hatch_um**: 100.0
- **layerForBarePlate_um**: 30.0
- **preheat_C**: 20 C assumed (not given by either dataset)
- **regimeClassForFitting**: input-only normalised enthalpy at the material default absorptivity, thresholds 15/30; the balling flag is NOT used
- **defaultAbsorptivity**: {'316L Stainless Steel': 0.42, 'Ti-6Al-4V': 0.35}

Regime rule (harness): Screening classifier, not the papers' regime definition. Inputs: normalised enthalpy dH/h_s = eta*P / (rho*cp_s*max(50, T_liq-T0)*sqrt(pi*alpha_s*v*r^3)) (same form as lpbf_thermal_solver.py, flat-plate absorptivity_IR of the material authority, solid k/cp, r = d/2) and the dataset's own balling flag. balling == 1 -> 'balling-flagged' (Hofmann only); otherwise dH/h_s < 15 -> 'conduction', 15 <= dH/h_s < 30 -> 'transition', >= 30 -> 'keyhole'. Measured D/W is recorded next to the label but not used for it.
