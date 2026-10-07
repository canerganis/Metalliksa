# LPBF melt-pool calibration scorecard (2026-10-07)

**Screening only: nuisance parameters fitted to published tracks; not validation.** Evidence kind `screening-only`; label promotion proposed: **none**; `experimentalValidation` = false; `opticalOperatorMatched` = false.

Schema `lpbf-calibration-scorecard-1`; implementation fingerprint `d92d1a3ae85cd4c1adab6dc734eaae589ef4c275c33f09015aff639998f10ddd`; config sha256 `6926386ddf9ad2a0d9fc787b4dbca7324b20b466e7a806be38b949fbafa1271b`; code revision `ac8e000eb6d8ed892ac46a3da82d5efb07c54aac` (feat/lpbf-scorecard-calibration-infra; dirty tracked paths: 0); tool sha256 `3aae27682d375690e9da99ebe0b0745747d3c33ad7329bfc96229e3b2735e8d8`; quick mode: False.

Honesty: calibration of nuisance parameters against published single tracks; not experimental validation; the frozen screening kernels are read-only; absorptivity is a fitted effective parameter that absorbs model error, not a measured one; estimated material laws; no per-row measurement uncertainty exists in any source; experimentalValidation=false, opticalOperatorMatched=false.

## Gate outcome

Calibrated mode may serve a cell only when its status is `enabled`: held-out skill CI95 lower bound >= -0.02 on every held-out source (and > 0 on at least one), 90 % interval coverage Wilson upper bound >= 0.90, no physics-compensation flag, fold-wise eta agreement, same decision under both KU beam readings, no rung that resolves fewer rows than default. Status counts: no-data 12, rejected 17, within-source-only 1.

| kernel | alloy | quantity | status | served rung | reasons |
|---|---|---|---|---|---|
| eagar-tsai | 316L Stainless Steel | width | **rejected** | default | sourceDependentEta; noRungImprovesAcrossSources: no ladder rung beats default on the inner training score; held-out source hofmann-316l-2026: skill CI95 lower bound -0.438 < -0.02; held-out source ku-leuven-316l-2021: skill CI95 lower bound -0.147 < -0.02; no held-out source with skill CI95 lower bound > 0 |
| eagar-tsai | 316L Stainless Steel | depth | **rejected** | default | unresolvedInput: decision differs between beam readings 37.5=within-source-only, 75=rejected |
| eagar-tsai | Ti-6Al-4V | width | **rejected** | default | noRungImprovesAcrossSources: no ladder rung beats default on the inner training score; held-out source totis-ti64-2021: skill CI95 lower bound -0.219 < -0.02; no held-out source with skill CI95 lower bound > 0; within-source skill CI95 lower bound not > 0 on any source |
| eagar-tsai | Ti-6Al-4V | depth | **rejected** | default | noRungImprovesAcrossSources: no ladder rung beats default on the inner training score; held-out source totis-ti64-2021: skill CI95 lower bound -0.256 < -0.02; no held-out source with skill CI95 lower bound > 0; within-source skill CI95 lower bound not > 0 on any source |
| eagar-tsai | Inconel 625 | width | **rejected** | eta2 | boundHit; etaSplit; single source: no leave-one-source-out available |
| eagar-tsai | Inconel 625 | depth | **rejected** | default | noRungImprovesAcrossSources: no ladder rung beats default on the inner training score; single source: no leave-one-source-out available; no within-source evaluation possible: no source has enough parameter sets for grouped k-fold |
| eagar-tsai | Inconel 718 | width | **no-data** | - | no trainable measured source for this alloy |
| eagar-tsai | Inconel 718 | depth | **no-data** | - | no trainable measured source for this alloy |
| eagar-tsai | AlSi10Mg | width | **no-data** | - | no trainable measured source for this alloy |
| eagar-tsai | AlSi10Mg | depth | **no-data** | - | no trainable measured source for this alloy |
| goldak | 316L Stainless Steel | width | **rejected** | default | sourceDependentEta; unresolvedRows; noRungImprovesAcrossSources: no ladder rung beats default on the inner training score; held-out source hofmann-316l-2026: skill CI95 lower bound -0.422 < -0.02; held-out source hofmann-316l-2026: rung leaves more rows unresolved than default; held-out source ku-leuven-316l-2021: skill CI95 lower bound -0.860 < -0.02; no held-out source with skill CI95 lower bound > 0 |
| goldak | 316L Stainless Steel | depth | **within-source-only** | default | noRungImprovesAcrossSources: no ladder rung beats default on the inner training score; held-out source hofmann-316l-2026: 90 % PI coverage Wilson upper bound 0.743 < 0.9; no held-out source with skill CI95 lower bound > 0 |
| goldak | Ti-6Al-4V | width | **rejected** | eta | etaInconsistentWithMeasuredAbsorptance; held-out source totis-ti64-2021: skill CI95 lower bound -0.237 < -0.02; no held-out source with skill CI95 lower bound > 0 |
| goldak | Ti-6Al-4V | depth | **rejected** | default | noRungImprovesAcrossSources: no ladder rung beats default on the inner training score; held-out source totis-ti64-2021: skill CI95 lower bound -0.238 < -0.02; no held-out source with skill CI95 lower bound > 0; within-source skill CI95 lower bound not > 0 on any source |
| goldak | Inconel 625 | width | **rejected** | eta2 | single source: no leave-one-source-out available; no within-source evaluation possible: no source has enough parameter sets for grouped k-fold |
| goldak | Inconel 625 | depth | **rejected** | default | noRungImprovesAcrossSources: no ladder rung beats default on the inner training score; single source: no leave-one-source-out available; no within-source evaluation possible: no source has enough parameter sets for grouped k-fold |
| goldak | Inconel 718 | width | **no-data** | - | no trainable measured source for this alloy |
| goldak | Inconel 718 | depth | **no-data** | - | no trainable measured source for this alloy |
| goldak | AlSi10Mg | width | **no-data** | - | no trainable measured source for this alloy |
| goldak | AlSi10Mg | depth | **no-data** | - | no trainable measured source for this alloy |
| rosenthal | 316L Stainless Steel | width | **rejected** | default | unresolvedRows; noRungImprovesAcrossSources: no ladder rung beats default on the inner training score; held-out source hofmann-316l-2026: skill CI95 lower bound -0.336 < -0.02; held-out source hofmann-316l-2026: rung leaves more rows unresolved than default; no held-out source with skill CI95 lower bound > 0 |
| rosenthal | 316L Stainless Steel | depth | **rejected** | default | unresolvedInput: decision differs between beam readings 37.5=rejected, 75=within-source-only |
| rosenthal | Ti-6Al-4V | width | **rejected** | default | unresolvedRows; noRungImprovesAcrossSources: no ladder rung beats default on the inner training score; held-out source totis-ti64-2021: skill CI95 lower bound -0.041 < -0.02; held-out source totis-ti64-2021: rung leaves more rows unresolved than default; no held-out source with skill CI95 lower bound > 0 |
| rosenthal | Ti-6Al-4V | depth | **rejected** | default | unresolvedRows; noRungImprovesAcrossSources: no ladder rung beats default on the inner training score; held-out source totis-ti64-2021: skill CI95 lower bound -0.082 < -0.02; held-out source totis-ti64-2021: rung leaves more rows unresolved than default; no held-out source with skill CI95 lower bound > 0 |
| rosenthal | Inconel 625 | width | **rejected** | eta | single source: no leave-one-source-out available; no within-source evaluation possible: no source has enough parameter sets for grouped k-fold |
| rosenthal | Inconel 625 | depth | **rejected** | default | noRungImprovesAcrossSources: no ladder rung beats default on the inner training score; single source: no leave-one-source-out available; no within-source evaluation possible: no source has enough parameter sets for grouped k-fold |
| rosenthal | Inconel 718 | width | **no-data** | - | no trainable measured source for this alloy |
| rosenthal | Inconel 718 | depth | **no-data** | - | no trainable measured source for this alloy |
| rosenthal | AlSi10Mg | width | **no-data** | - | no trainable measured source for this alloy |
| rosenthal | AlSi10Mg | depth | **no-data** | - | no trainable measured source for this alloy |

## Held-out errors (leave-one-source-out, rung selected inside training only)

MAPE on the rows resolved by default and the rung; both directions of every two-source alloy. Equal source weight is the headline; unresolved rows are counted (and score as failures in the gate).

| kernel | alloy | q | held out | trained on | rung | n rows / sets | unresolved default / rung | MAPE default -> served % | skill CI95 | vs powerlaw | PI90 coverage (Wilson) | PI90 width x |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| eagar-tsai | 316L Stainless Steel | width | hofmann-316l-2026 | ku-leuven-316l-2021 | eta2 | 677 / 378 | 0 / 0 | 10.7 -> 14.8 | -0.38 [-0.44, -0.32] (does-not-beat) | beats | 0.98 [0.97, 0.99] n=677 | 2.43 |
| eagar-tsai | 316L Stainless Steel | width | ku-leuven-316l-2021 | hofmann-316l-2026 | eta | 44 / 44 | 0 / 0 | 16.7 -> 18.6 | -0.11 [-0.15, -0.08] (does-not-beat) | does-not-beat | 0.93 [0.82, 0.98] n=44 | 2.16 |
| eagar-tsai | 316L Stainless Steel | depth | hofmann-316l-2026 | ku-leuven-316l-2021 | default | 677 / 378 | 0 / 0 | 36.9 -> 36.9 | 0.00 [0.00, 0.00] (no-change) | - | 0.81 [0.78, 0.84] n=677 | 4.23 (not informative) |
| eagar-tsai | 316L Stainless Steel | depth | ku-leuven-316l-2021 | hofmann-316l-2026 | eta2+dOffset | 44 / 44 | 0 / 0 | 29.0 -> 31.3 | -0.08 [-0.14, -0.03] (does-not-beat) | does-not-beat | 1.00 [0.92, 1.00] n=44 | 12.56 (not informative) |
| eagar-tsai | Ti-6Al-4V | width | ku-leuven-ti64-2021 | totis-ti64-2021 | default | 14 / 14 | 0 / 0 | 8.4 -> 8.4 | 0.00 [0.00, 0.00] (no-change) | - | 1.00 [0.78, 1.00] n=14 | 3.23 (not informative) |
| eagar-tsai | Ti-6Al-4V | width | totis-ti64-2021 | ku-leuven-ti64-2021 | eta2 | 80 / 80 | 0 / 0 | 18.7 -> 21.1 | -0.13 [-0.22, -0.04] (does-not-beat) | does-not-beat | 0.99 [0.93, 1.00] n=80 | 3.13 (not informative) |
| eagar-tsai | Ti-6Al-4V | depth | ku-leuven-ti64-2021 | totis-ti64-2021 | default | 14 / 14 | 0 / 0 | 28.6 -> 28.6 | 0.00 [0.00, 0.00] (no-change) | - | 0.86 [0.60, 0.96] n=14 | 4.13 (not informative) |
| eagar-tsai | Ti-6Al-4V | depth | totis-ti64-2021 | ku-leuven-ti64-2021 | eta2 | 80 / 80 | 0 / 0 | 36.5 -> 41.2 | -0.13 [-0.26, -0.03] (does-not-beat) | beats | 0.97 [0.91, 0.99] n=80 | 12.21 (not informative) |
| goldak | 316L Stainless Steel | width | hofmann-316l-2026 | ku-leuven-316l-2021 | eta2 | 677 / 378 | 4 / 12 | 15.2 -> 21.0 | -0.38 [-0.42, -0.34] (does-not-beat) | does-not-beat | 0.93 [0.91, 0.95] n=665 | 2.78 (not informative) |
| goldak | 316L Stainless Steel | width | ku-leuven-316l-2021 | hofmann-316l-2026 | eta2 | 44 / 44 | 0 / 0 | 16.1 -> 26.7 | -0.66 [-0.86, -0.49] (does-not-beat) | does-not-beat | 0.82 [0.68, 0.90] n=44 | 2.14 |
| goldak | 316L Stainless Steel | depth | hofmann-316l-2026 | ku-leuven-316l-2021 | default | 677 / 378 | 4 / 4 | 42.5 -> 42.5 | 0.00 [0.00, 0.00] (no-change) | - | 0.71 [0.67, 0.74] n=673 | 3.69 (not informative) |
| goldak | 316L Stainless Steel | depth | ku-leuven-316l-2021 | hofmann-316l-2026 | default | 44 / 44 | 0 / 0 | 29.0 -> 29.0 | 0.00 [0.00, 0.00] (no-change) | - | 1.00 [0.92, 1.00] n=44 | 5.73 (not informative) |
| goldak | Ti-6Al-4V | width | ku-leuven-ti64-2021 | totis-ti64-2021 | default | 14 / 14 | 0 / 0 | 11.0 -> 11.0 | 0.00 [0.00, 0.00] (no-change) | - | 1.00 [0.78, 1.00] n=14 | 3.98 (not informative) |
| goldak | Ti-6Al-4V | width | totis-ti64-2021 | ku-leuven-ti64-2021 | eta2 | 80 / 80 | 0 / 0 | 20.6 -> 23.0 | -0.11 [-0.24, -0.01] (does-not-beat) | does-not-beat | 1.00 [0.95, 1.00] n=80 | 4.49 (not informative) |
| goldak | Ti-6Al-4V | depth | ku-leuven-ti64-2021 | totis-ti64-2021 | default | 14 / 14 | 0 / 0 | 28.6 -> 28.6 | 0.00 [0.00, 0.00] (no-change) | - | 0.93 [0.69, 0.99] n=14 | 4.34 (not informative) |
| goldak | Ti-6Al-4V | depth | totis-ti64-2021 | ku-leuven-ti64-2021 | eta2 | 80 / 80 | 0 / 0 | 39.1 -> 43.3 | -0.11 [-0.24, -0.01] (does-not-beat) | inconclusive | 0.97 [0.91, 0.99] n=80 | 12.45 (not informative) |
| rosenthal | 316L Stainless Steel | width | hofmann-316l-2026 | ku-leuven-316l-2021 | eta2 | 677 / 378 | 7 / 40 | 26.2 -> 32.3 | -0.23 [-0.34, -0.12] (does-not-beat) | does-not-beat | 0.96 [0.95, 0.98] n=637 | 10.09 (not informative) |
| rosenthal | 316L Stainless Steel | width | ku-leuven-316l-2021 | hofmann-316l-2026 | default | 44 / 44 | 0 / 0 | 57.7 -> 57.7 | 0.00 [0.00, 0.00] (no-change) | - | 1.00 [0.92, 1.00] n=44 | 7.58 (not informative) |
| rosenthal | 316L Stainless Steel | depth | hofmann-316l-2026 | ku-leuven-316l-2021 | eta | 677 / 378 | 7 / 35 | 59.2 -> 32.7 | 0.45 [0.40, 0.49] (beats) | beats | 0.97 [0.96, 0.98] n=642 | 14.17 (not informative) |
| rosenthal | 316L Stainless Steel | depth | ku-leuven-316l-2021 | hofmann-316l-2026 | default | 44 / 44 | 0 / 0 | 44.0 -> 44.0 | 0.00 [0.00, 0.00] (no-change) | - | 1.00 [0.92, 1.00] n=44 | 9.37 (not informative) |
| rosenthal | Ti-6Al-4V | width | ku-leuven-ti64-2021 | totis-ti64-2021 | default | 14 / 14 | 0 / 0 | 37.0 -> 37.0 | 0.00 [0.00, 0.00] (no-change) | - | 1.00 [0.78, 1.00] n=14 | 11.00 (not informative) |
| rosenthal | Ti-6Al-4V | width | totis-ti64-2021 | ku-leuven-ti64-2021 | eta | 80 / 80 | 0 / 2 | 52.3 -> 51.0 | 0.02 [-0.04, 0.08] (inconclusive) | does-not-beat | 1.00 [0.95, 1.00] n=78 | 13.53 (not informative) |
| rosenthal | Ti-6Al-4V | depth | ku-leuven-ti64-2021 | totis-ti64-2021 | default | 14 / 14 | 0 / 0 | 69.0 -> 69.0 | 0.00 [0.00, 0.00] (no-change) | - | 1.00 [0.78, 1.00] n=14 | 12.36 (not informative) |
| rosenthal | Ti-6Al-4V | depth | totis-ti64-2021 | ku-leuven-ti64-2021 | eta2+dOffset | 80 / 80 | 0 / 2 | 41.4 -> 35.1 | 0.15 [-0.08, 0.31] (inconclusive) | beats | 0.99 [0.93, 1.00] n=78 | 24.22 (not informative) |

### Equal-source-weight headline

| kernel | alloy | q | status | MAPE default -> served % (equal source weight) | row-weighted |
|---|---|---|---|---|---|
| eagar-tsai | 316L Stainless Steel | width | rejected | 13.7 -> 16.7 | 11.1 -> 15.0 |
| eagar-tsai | 316L Stainless Steel | depth | rejected | 32.9 -> 34.1 | 36.4 -> 36.5 |
| eagar-tsai | Ti-6Al-4V | width | rejected | 13.6 -> 14.7 | 17.2 -> 19.2 |
| eagar-tsai | Ti-6Al-4V | depth | rejected | 32.6 -> 34.9 | 35.4 -> 39.3 |
| goldak | 316L Stainless Steel | width | rejected | 15.7 -> 23.9 | 15.3 -> 21.4 |
| goldak | 316L Stainless Steel | depth | within-source-only | 35.7 -> 35.7 | 41.7 -> 41.7 |
| goldak | Ti-6Al-4V | width | rejected | 15.8 -> 17.0 | 19.2 -> 21.2 |
| goldak | Ti-6Al-4V | depth | rejected | 33.9 -> 36.0 | 37.5 -> 41.1 |
| rosenthal | 316L Stainless Steel | width | rejected | 41.9 -> 45.0 | 28.1 -> 33.8 |
| rosenthal | 316L Stainless Steel | depth | rejected | 51.6 -> 38.4 | 58.3 -> 33.4 |
| rosenthal | Ti-6Al-4V | width | rejected | 44.6 -> 44.0 | 50.0 -> 48.9 |
| rosenthal | Ti-6Al-4V | depth | rejected | 55.2 -> 52.0 | 45.5 -> 40.1 |

## Within-source grouped 5-fold (nested rung selection, seeds 0/1/2)

| kernel | alloy | q | source | rows / sets | MAPE default -> served % | skill (seed 0) CI95 | skill seeds 0/1/2 |
|---|---|---|---|---|---|---|---|
| eagar-tsai | 316L Stainless Steel | width | hofmann-316l-2026 | 677 / 378 | 10.7 -> 10.4 | 0.03 [0.01, 0.05] | 0.03, 0.02, 0.04 |
| eagar-tsai | 316L Stainless Steel | width | ku-leuven-316l-2021 | 44 / 44 | 16.7 -> 11.9 | 0.29 [0.14, 0.41] | 0.29, 0.21, 0.28 |
| eagar-tsai | 316L Stainless Steel | depth | hofmann-316l-2026 | 677 / 378 | 36.9 -> 34.2 | 0.07 [0.03, 0.11] | 0.07, 0.07, 0.07 |
| eagar-tsai | 316L Stainless Steel | depth | ku-leuven-316l-2021 | 44 / 44 | 29.0 -> 31.8 | -0.10 [-0.28, 0.03] | -0.10, 0.00, -0.24 |
| eagar-tsai | Ti-6Al-4V | width | totis-ti64-2021 | 80 / 80 | 18.7 -> 18.8 | -0.01 [-0.02, 0.01] | -0.01, -0.02, 0.01 |
| eagar-tsai | Ti-6Al-4V | depth | totis-ti64-2021 | 80 / 80 | 36.5 -> 37.0 | -0.01 [-0.07, 0.06] | -0.01, 0.01, -0.02 |
| goldak | 316L Stainless Steel | width | hofmann-316l-2026 | 677 / 378 | 15.5 -> 12.7 | 0.18 [0.13, 0.23] | 0.18, 0.18, 0.19 |
| goldak | 316L Stainless Steel | width | ku-leuven-316l-2021 | 44 / 44 | 16.1 -> 12.6 | 0.22 [0.07, 0.34] | 0.22, 0.15, 0.22 |
| goldak | 316L Stainless Steel | depth | hofmann-316l-2026 | 677 / 378 | 42.5 -> 39.0 | 0.08 [0.05, 0.12] | 0.08, 0.00, 0.06 |
| goldak | 316L Stainless Steel | depth | ku-leuven-316l-2021 | 44 / 44 | 29.0 -> 31.8 | -0.10 [-0.28, 0.03] | -0.10, 0.00, -0.24 |
| goldak | Ti-6Al-4V | width | totis-ti64-2021 | 80 / 80 | 20.6 -> 20.6 | 0.00 [0.00, 0.00] | 0.00, 0.00, 0.00 |
| goldak | Ti-6Al-4V | depth | totis-ti64-2021 | 80 / 80 | 39.1 -> 39.9 | -0.02 [-0.08, 0.05] | -0.02, 0.00, -0.02 |
| rosenthal | 316L Stainless Steel | width | hofmann-316l-2026 | 677 / 378 | 26.8 -> 26.8 | 0.00 [0.00, 0.00] | 0.00, 0.00, 0.00 |
| rosenthal | 316L Stainless Steel | width | ku-leuven-316l-2021 | 44 / 44 | 57.7 -> 47.9 | 0.17 [0.12, 0.24] | 0.17, 0.16, 0.18 |
| rosenthal | 316L Stainless Steel | depth | hofmann-316l-2026 | 677 / 378 | 59.1 -> 59.1 | 0.00 [0.00, 0.00] | 0.00, 0.00, 0.00 |
| rosenthal | 316L Stainless Steel | depth | ku-leuven-316l-2021 | 44 / 44 | 44.0 -> 40.3 | 0.08 [-0.03, 0.20] | 0.08, 0.09, 0.10 |
| rosenthal | Ti-6Al-4V | width | totis-ti64-2021 | 80 / 80 | 52.2 -> 53.0 | -0.02 [-0.05, 0.01] | -0.02, -0.01, -0.02 |
| rosenthal | Ti-6Al-4V | depth | totis-ti64-2021 | 80 / 80 | 44.8 -> 43.2 | 0.03 [0.01, 0.06] | 0.03, 0.06, 0.08 |

Sources without a within-source evaluation (not silently dropped):

- ku-leuven-ti64-2021: 14 parameter sets; fewer than 20 parameter sets: no within-source grouped 5-fold
- lane-in625-2020: 6 parameter sets; fewer than 20 parameter sets: no within-source grouped 5-fold

## Fitted parameters (final fit on all trainable sources of the alloy; bootstrap CI90)

| kernel | alloy | q | rung | eta_W | eta_D | eta joint | c_D by class | flags |
|---|---|---|---|---|---|---|---|---|
| eagar-tsai | 316L Stainless Steel | width | default | 0.395 [0.385, 0.420] | 0.460 [0.430, 0.485] | 0.435 [0.415, 0.460] | conduction -0.30, keyhole -0.04, transition -0.06 | - |
| eagar-tsai | 316L Stainless Steel | depth | default | 0.395 [0.385, 0.420] | 0.460 [0.430, 0.485] | 0.435 [0.415, 0.460] | conduction -0.30, keyhole -0.04, transition -0.06 | - |
| eagar-tsai | Ti-6Al-4V | width | default | 0.405 [0.390, 0.415] | 0.370 [0.305, 0.400] | 0.385 [0.360, 0.400] | conduction -0.63, keyhole +0.10, transition +0.25 | - |
| eagar-tsai | Ti-6Al-4V | depth | default | 0.405 [0.390, 0.415] | 0.370 [0.305, 0.400] | 0.385 [0.360, 0.400] | conduction -0.63, keyhole +0.10, transition +0.25 | - |
| eagar-tsai | Inconel 625 | width | eta2 | 0.250 [0.250, 0.445] | 0.600 [0.320, 0.600] | 0.375 [0.320, 0.600] | conduction +0.00, keyhole +0.00, transition +0.00 | boundHit, etaSplit |
| eagar-tsai | Inconel 625 | depth | default | 0.250 [0.250, 0.445] | 0.600 [0.320, 0.600] | 0.375 [0.320, 0.600] | conduction +0.00, keyhole +0.00, transition +0.00 | - |
| goldak | 316L Stainless Steel | width | default | 0.440 [0.415, 0.470] | 0.460 [0.415, 0.485] | 0.455 [0.415, 0.470] | conduction -0.46, keyhole -0.04, transition -0.10 | - |
| goldak | 316L Stainless Steel | depth | default | 0.440 [0.415, 0.470] | 0.460 [0.415, 0.485] | 0.455 [0.415, 0.470] | conduction -0.46, keyhole -0.04, transition -0.10 | - |
| goldak | Ti-6Al-4V | width | eta | 0.425 [0.405, 0.450] | 0.365 [0.305, 0.391] | 0.385 [0.365, 0.410] | conduction -0.69, keyhole +0.11, transition +0.19 | etaInconsistentWithMeasuredAbsorptance |
| goldak | Ti-6Al-4V | depth | default | 0.425 [0.405, 0.450] | 0.365 [0.305, 0.391] | 0.385 [0.365, 0.410] | conduction -0.69, keyhole +0.11, transition +0.19 | - |
| goldak | Inconel 625 | width | eta2 | 0.525 [0.505, 0.570] | 0.600 [0.500, 0.600] | 0.585 [0.500, 0.600] | conduction +0.00, keyhole +0.00, transition +0.00 | - |
| goldak | Inconel 625 | depth | default | 0.525 [0.505, 0.570] | 0.600 [0.500, 0.600] | 0.585 [0.500, 0.600] | conduction +0.00, keyhole +0.00, transition +0.00 | - |
| rosenthal | 316L Stainless Steel | width | default | 0.415 [0.345, 0.570] | 0.335 [0.315, 0.350] | 0.340 [0.315, 0.360] | conduction -0.13, keyhole +0.01, transition +0.04 | - |
| rosenthal | 316L Stainless Steel | depth | default | 0.415 [0.345, 0.570] | 0.335 [0.315, 0.350] | 0.340 [0.315, 0.360] | conduction -0.13, keyhole +0.01, transition +0.04 | - |
| rosenthal | Ti-6Al-4V | width | default | 0.260 [0.250, 0.281] | 0.250 [0.250, 0.260] | 0.250 [0.250, 0.260] | conduction +0.10, keyhole +0.04, transition +0.42 | - |
| rosenthal | Ti-6Al-4V | depth | default | 0.260 [0.250, 0.281] | 0.250 [0.250, 0.260] | 0.250 [0.250, 0.260] | conduction +0.10, keyhole +0.04, transition +0.42 | - |
| rosenthal | Inconel 625 | width | eta | 0.610 [0.550, 0.650] | 0.550 [0.550, 0.550] | 0.550 [0.550, 0.550] | conduction +0.00, keyhole +0.00, transition +0.00 | - |
| rosenthal | Inconel 625 | depth | default | 0.610 [0.550, 0.650] | 0.550 [0.550, 0.550] | 0.550 [0.550, 0.550] | conduction +0.00, keyhole +0.00, transition +0.00 | - |

Parameters are listed for every cell for diagnosis; the `rung` column says what would be served, and nothing is served unless the status is `enabled`. A `default` rung means no ladder rung beat the unchanged screening result on the training-only inner score.

### Physics-compensation notes

- eagar-tsai / Inconel 625 / width: boundHit: eta (W) 0.250 within 1 grid step of a bound or in > 20 % of bootstrap replicates
- eagar-tsai / Inconel 625 / width: etaSplit: |ln(eta_D/eta_W)| = 0.88 > ln 1.3 (eta_W 0.250, eta_D 0.600): one physical absorptivity cannot be both
- goldak / Ti-6Al-4V / width: etaInconsistentWithMeasuredAbsorptance: fitted effective eta disagrees with measured absorptance (keyhole band 0.40-0.94, eta 0.385) -> eta is absorbing model error (diagnostic, not a validation claim)

## Regime confusion vs KU Leuven published labels

**316L Stainless Steel, KU beam reading 37.5 um (screening class at default eta, input-only)** n=44, accuracy 0.84; keyhole precision 0.93, recall 1.00

| published \ screening | conduction | transition | keyhole |
|---|---|---|---|
| conduction | 0 | 4 | 0 |
| transition | 0 | 0 | 3 |
| keyhole | 0 | 0 | 37 |

**316L Stainless Steel, KU beam reading 75 um (screening class at default eta, input-only)** n=44, accuracy 0.66; keyhole precision 1.00, recall 0.68

| published \ screening | conduction | transition | keyhole |
|---|---|---|---|
| conduction | 4 | 0 | 0 |
| transition | 3 | 0 | 0 |
| keyhole | 1 | 11 | 25 |

**Ti-6Al-4V, KU beam reading 37.5 um (screening class at default eta, input-only)** n=14, accuracy 0.29; keyhole precision 0.36, recall 1.00

| published \ screening | conduction | transition | keyhole |
|---|---|---|---|
| conduction | 0 | 3 | 2 |
| transition | 0 | 0 | 5 |
| keyhole | 0 | 0 | 4 |

**Ti-6Al-4V, KU beam reading 75 um (screening class at default eta, input-only)** n=14, accuracy 0.57; keyhole precision -, recall 0.00

| published \ screening | conduction | transition | keyhole |
|---|---|---|---|
| conduction | 5 | 0 | 0 |
| transition | 2 | 3 | 0 |
| keyhole | 0 | 4 | 0 |

**Geometry-based keyhole call (predicted D/W > 1 vs measured D/W > 1), KU rows held out; each rung's OWN width and depth, never measured D with calibrated W**

| alloy | kernel | rung | n | tp / fp / fn / tn | precision | recall |
|---|---|---|---|---|---|---|
| 316L Stainless Steel | eagar-tsai | default | 44 | 34 / 5 / 0 / 5 | 0.87 | 1.00 |
| 316L Stainless Steel | eagar-tsai | eta | 44 | 34 / 6 / 0 / 4 | 0.85 | 1.00 |
| 316L Stainless Steel | eagar-tsai | eta2 | 44 | 34 / 4 / 0 / 6 | 0.89 | 1.00 |
| 316L Stainless Steel | eagar-tsai | eta2+dOffset | 44 | 34 / 3 / 0 / 7 | 0.92 | 1.00 |
| 316L Stainless Steel | goldak | default | 44 | 34 / 6 / 0 / 4 | 0.85 | 1.00 |
| 316L Stainless Steel | goldak | eta | 44 | 34 / 7 / 0 / 3 | 0.83 | 1.00 |
| 316L Stainless Steel | goldak | eta2 | 44 | 33 / 3 / 1 / 7 | 0.92 | 0.97 |
| 316L Stainless Steel | goldak | eta2+dOffset | 44 | 33 / 3 / 1 / 7 | 0.92 | 0.97 |
| 316L Stainless Steel | rosenthal | default | 44 | 33 / 3 / 1 / 7 | 0.92 | 0.97 |
| 316L Stainless Steel | rosenthal | eta | 44 | 33 / 2 / 1 / 8 | 0.94 | 0.97 |
| 316L Stainless Steel | rosenthal | eta2 | 44 | 32 / 0 / 2 / 10 | 1.00 | 0.94 |
| 316L Stainless Steel | rosenthal | eta2+dOffset | 44 | 25 / 0 / 9 / 10 | 1.00 | 0.74 |
| Ti-6Al-4V | eagar-tsai | default | 14 | 6 / 3 / 0 / 5 | 0.67 | 1.00 |
| Ti-6Al-4V | eagar-tsai | eta | 14 | 6 / 4 / 0 / 4 | 0.60 | 1.00 |
| Ti-6Al-4V | eagar-tsai | eta2 | 14 | 6 / 7 / 0 / 1 | 0.46 | 1.00 |
| Ti-6Al-4V | eagar-tsai | eta2+dOffset | 14 | 6 / 8 / 0 / 0 | 0.43 | 1.00 |
| Ti-6Al-4V | goldak | default | 14 | 6 / 4 / 0 / 4 | 0.60 | 1.00 |
| Ti-6Al-4V | goldak | eta | 14 | 6 / 5 / 0 / 3 | 0.55 | 1.00 |
| Ti-6Al-4V | goldak | eta2 | 14 | 6 / 6 / 0 / 2 | 0.50 | 1.00 |
| Ti-6Al-4V | goldak | eta2+dOffset | 14 | 6 / 8 / 0 / 0 | 0.43 | 1.00 |
| Ti-6Al-4V | rosenthal | default | 14 | 6 / 1 / 0 / 7 | 0.86 | 1.00 |
| Ti-6Al-4V | rosenthal | eta | 14 | 6 / 1 / 0 / 7 | 0.86 | 1.00 |
| Ti-6Al-4V | rosenthal | eta2 | 14 | 2 / 0 / 4 / 8 | 1.00 | 0.33 |
| Ti-6Al-4V | rosenthal | eta2+dOffset | 14 | 2 / 0 / 4 / 8 | 1.00 | 0.33 |

## Guo N01 (red card) and catalog sentinels

Guo N01/N04-N06 and NIST AMB2022-03 Table 4 were used while the frozen physics was developed (PROOF 023, the Goldak fix, test_goldak_fabbro bands): they are development data, not blind held-out data. N01 (260 W, 520 mm/s, keyhole, D_meas 180 um) is a documented keyhole-depth failure: it is NOT fitted, it is in no training split, and calibration does not fix it.

| kernel | rung | W pred / meas um | D pred / meas um | D factor | inside x0.5-2 |
|---|---|---|---|---|---|
| eagar-tsai | default | 171.2 / 114 | 75.8 / 180 | 0.42 | NO |
| eagar-tsai | eta | 174.1 / 114 | 77.3 / 180 | 0.43 | NO |
| eagar-tsai | eta2 | 166.2 / 114 | 85.1 / 180 | 0.47 | NO |
| eagar-tsai | eta2+dOffset | 166.2 / 114 | 80.3 / 180 | 0.45 | NO |
| goldak | default | 162.8 / 114 | 81.0 / 180 | 0.45 | NO |
| goldak | eta | 169.9 / 114 | 86.1 / 180 | 0.48 | NO |
| goldak | eta2 | 166.9 / 114 | 88.4 / 180 | 0.49 | NO |
| goldak | eta2+dOffset | 166.9 / 114 | 80.3 / 180 | 0.45 | NO |
| rosenthal | default | 202.7 / 114 | 137.7 / 180 | 0.77 | yes |
| rosenthal | eta | 160.8 / 114 | 97.3 / 180 | 0.54 | yes |
| rosenthal | eta2 | 200.6 / 114 | 94.5 / 180 | 0.53 | yes |
| rosenthal | eta2+dOffset | 200.6 / 114 | 98.3 / 180 | 0.55 | yes |

## Unresolved-row accounting (no silent drops)

unresolved test rows count as failures (mapeUnresolvedAsFail, a rung that resolves fewer rows than default fails the gate); MAPE columns are on the common resolved subset and always listed with the unresolved count

| kernel | source | role | rows | resolved at default | unresolved at default | statuses |
|---|---|---|---|---|---|---|
| eagar-tsai | hofmann-316l-2026 | trainable | 677 | 677 | 0 | {'computed': 677} |
| eagar-tsai | ku-leuven-316l-2021 | trainable | 44 | 44 | 0 | {'computed': 44} |
| eagar-tsai | ku-leuven-ti64-2021 | trainable | 14 | 14 | 0 | {'computed': 14} |
| eagar-tsai | lane-in625-2020 | trainable | 23 | 23 | 0 | {'computed': 23} |
| eagar-tsai | totis-ti64-2021 | trainable | 80 | 80 | 0 | {'computed': 80} |
| eagar-tsai | guo-316l-2024 | catalog-sentinel | 4 | 4 | 0 | {'computed': 4} |
| eagar-tsai | nist-amb2022-03-in718 | catalog-sentinel | 7 | 7 | 0 | {'computed': 7} |
| goldak | hofmann-316l-2026 | trainable | 677 | 673 | 4 | {'computed': 673, 'width-floor-applied': 4} |
| goldak | ku-leuven-316l-2021 | trainable | 44 | 44 | 0 | {'computed': 44} |
| goldak | ku-leuven-ti64-2021 | trainable | 14 | 14 | 0 | {'computed': 14} |
| goldak | lane-in625-2020 | trainable | 23 | 18 | 5 | {'computed': 18, 'width-floor-applied': 5} |
| goldak | totis-ti64-2021 | trainable | 80 | 80 | 0 | {'computed': 80} |
| goldak | guo-316l-2024 | catalog-sentinel | 4 | 4 | 0 | {'computed': 4} |
| goldak | nist-amb2022-03-in718 | catalog-sentinel | 7 | 7 | 0 | {'computed': 7} |
| rosenthal | hofmann-316l-2026 | trainable | 677 | 670 | 7 | {'computed': 670, 'width-floor-applied': 7} |
| rosenthal | ku-leuven-316l-2021 | trainable | 44 | 44 | 0 | {'computed': 44} |
| rosenthal | ku-leuven-ti64-2021 | trainable | 14 | 14 | 0 | {'computed': 14} |
| rosenthal | lane-in625-2020 | trainable | 23 | 18 | 5 | {'computed': 18, 'width-floor-applied': 5} |
| rosenthal | totis-ti64-2021 | trainable | 80 | 80 | 0 | {'computed': 80} |
| rosenthal | guo-316l-2024 | catalog-sentinel | 4 | 4 | 0 | {'computed': 4} |
| rosenthal | nist-amb2022-03-in718 | catalog-sentinel | 7 | 7 | 0 | {'computed': 7} |

Rows excluded by the loaders:

- ku-leuven-316l-2021: ku-leuven-316l-2021-41 (w exp / d exp blank in the processed source file); ku-leuven-316l-2021-42 (w exp / d exp blank in the processed source file); ku-leuven-316l-2021-47 (w exp / d exp blank in the processed source file); ku-leuven-316l-2021-48 (w exp / d exp blank in the processed source file)
- not a geometry source: cmu-ti64-2026: no power / no beam diameter in the source rows: not a geometry row set
- not a geometry source: ku-leuven-in718-2021: width/depth units and width operator unresolved: excluded everywhere
- not a geometry source: simonds-316l-2018, nist-mds2-2525: stationary-spot absorptance: used as R5 bands and bounds only
- not a geometry source: nist thermal targets: thermal-history targets, not melt-pool geometry: out of scope

## Sources

| source | role | alloy | rows used | parameter sets | DOI | table sha256 |
|---|---|---|---|---|---|---|
| hofmann-316l-2026 | trainable | 316L Stainless Steel | 677 | 378 | 10.5281/zenodo.16979848 | `d4bbc7a60b536118586f44b64beb0fa20f94133f6d1a8d0fdcf726003720c3d8` |
| ku-leuven-316l-2021 | trainable | 316L Stainless Steel | 44 | 44 | 10.6084/m9.figshare.15035733.v1 + 10.6084/m9.figshare.15035703.v1 | `e031aead71bf64c70a35ae05d64c0c576d33c2ae757a1e5bda68b5da532ac831` |
| totis-ti64-2021 | trainable | Ti-6Al-4V | 80 | 80 | 10.17632/s9438vb5xd.1 | `3b5794f3a25a5f67fa0d8d1ab006834205ef820b046c24deb15836025825d623` |
| ku-leuven-ti64-2021 | trainable | Ti-6Al-4V | 14 | 14 | 10.6084/m9.figshare.15035709.v1 + 10.6084/m9.figshare.15035712.v2 | `e031aead71bf64c70a35ae05d64c0c576d33c2ae757a1e5bda68b5da532ac831` |
| lane-in625-2020 | trainable | Inconel 625 | 23 | 6 | 10.1007/s40192-020-00169-1 | `32fe10fb8606a49cdc59e1e3753b40e6be9ea9751dae9ec8ac95c217e6d16179` |
| guo-316l-2024 | catalog-sentinel (test-only) | 316L Stainless Steel | 4 | 4 | 10.3390/mi15020170 | n/a (literature catalog table, not file-hashed) |
| nist-amb2022-03-in718 | catalog-sentinel (test-only) | Inconel 718 | 7 | 7 | 10.1007/s40192-024-00355-5 | n/a (literature catalog table, not file-hashed) |

## What this does not show

- It is not experimental validation. Effective absorptivity is a fitted nuisance parameter that absorbs every other model error (material laws, the Fabbro keyhole term, the flat-plate path, spot definition, assumed 20 C preheat); it must not be read as a measured absorptivity of any alloy.
- No source reports per-row measurement uncertainty, sectioning position or replicate scatter; intervals cover parameter-set resampling and the between-source offset only, not measurement error.
- Between-source offsets (machine, powder, atmosphere, operator) are larger than anything a per-alloy absorptivity removes; a calibration that helps inside one source usually does not transfer to the next.
- Only two 316L sources and two Ti-6Al-4V sources are available for leave-one-source-out; Inconel 625 has one source (within-source only); Inconel 718 and AlSi10Mg have no trainable source (no-data).
- KU Leuven's beam diameter (37.5 vs 75 um) is unresolved; the gate decision is required to be identical under both readings, otherwise the cell is rejected as 'unresolved input'.
- The catalog sentinels (Guo, NIST IN718) were used while the frozen physics was developed; they are reported separately and are not blind held-out data.
- The served default screening output, the Build Job verdict and the balling screen are unchanged by this work; calibration never re-scores a Build Job.
