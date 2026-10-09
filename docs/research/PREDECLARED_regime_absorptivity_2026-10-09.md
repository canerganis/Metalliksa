# Regime-dependent absorptivity law: pre-registration (2026-10-09)

File: `docs/research/PREDECLARED_regime_absorptivity_2026-10-09.md`

**PREDECLARED. Screening evaluation, not validation. No candidate number has been computed.** This file fixes the
law, its parameters, the data roles, the metrics, the baseline and the decision rule BEFORE the first prediction of
the candidate law exists. Repo state: `Metalliksa-1` origin/main `02503eed` (same tree as local `90f08ef6`), frozen
implementation fingerprint `ec7e1f7a6606e937e448fefe97549b49a7ddfe7b95376b93867ae007b0c12555`. Nothing in the frozen
solver changes in this evaluation. Labels stay as they are: `experimentalValidation=false`,
`validationStatus=unvalidated`, `productionReady=false`.

## 1. Hypothesis

A single flat-plate absorptivity per alloy cannot represent the rise of coupled power once a vapor depression forms
(Simonds 2018 Table III, NIST mds2-2525, Trapp 2017, Ye 2019, Gan 2021). The keyhole benchmark of 2026-10-07 lists
"flat keyhole absorptivity" as one candidate cause of the depth under-prediction in keyhole conditions
(`KEYHOLE_DEPTH_BENCHMARK_NOTE` in `python/lpbf_thermal_solver.py`). H1: replacing the flat absorptivity of the
conduction-field kernels by a law A(dH/hs) that equals the flat value in conduction and rises toward a published
keyhole plateau improves held-out melt-pool depth without degrading width, regime classification or interval
coverage. H0: it does not.

## 2. What the app does today (02503eed)

Correction to the task framing: only part of the app uses a flat absorptivity.

| quantity | today | file |
|---|---|---|
| normalized enthalpy H = dH/hs | A_flat P / (rho cp_s max(50, T_liq - T0) sqrt(pi alpha_s v r^3)), r = 1/e^2 radius, solid k and cp, A_flat = material `absorptivity_IR` | `lpbf_thermal_solver.calculate_meltpool_physics` |
| regime label | H < 15 conduction, 15 to 20 transition, >= 20 keyhole mode (`ENTHALPY_TRANSITION`, `ENTHALPY_KEYHOLE`; basis in `docs/LPBF_KEYHOLE_THRESHOLD_EVIDENCE_2026-10-07.md`) | same |
| Eagar-Tsai and Goldak absorbed power | A_flat P (flat) | same |
| Rosenthal (Build Job) absorbed power | eta_eff P with an UNCITED multi-reflection ramp: eta_eff = 1 - (1 - A_flat)^(1 + 1.8 min(4, (H - 15)/8)) for H > 15, else A_flat | same |
| Fabbro keyhole depth | Fabbro 2020 eq. 2 with A_flat, 15 to 30 onset ramp | `fabbro_keyhole.py` |
| Rosenthal keyhole depth increment | uncited heuristic keyed to flat H (15/30 band edges) | `lpbf_thermal_solver.py` |
| A_flat values | 316L 0.42, Ti-6Al-4V 0.35, Inconel 625 0.38 (legacy-estimated secondary), Inconel 718 0.38 | material authority |

## 3. Candidate law (primary arm A0, the only arm that can produce PASS)

```
H     = A_flat P / (rho cp_s max(50, T_liq - T0) sqrt(pi alpha_s v r^3))      (unchanged, flat A)
A(H)  = A_flat                                                  for H <= H_on
A(H)  = A_kh - (A_kh - A_flat) exp(-(H - H_on) / H_s)          for H >  H_on
```

Functional form: a saturating exponential from the same family as Gan et al. 2021 Eq. 6 (eta = 0.7 (1 - exp(-0.6 Ke_m Ld*)),
after Ye et al. 2019). It is shifted so that it starts at the app's own flat value at the vapor-depression onset
instead of at zero. No parameter is fitted.

| parameter | value | source | status |
|---|---|---|---|
| A_flat | material authority `absorptivity_IR` at 02503eed (table in section 2) | `four_alloy_materials.py`, `SECONDARY_THERMOPHYSICAL_DB` | unchanged baseline value; makes conduction rows identical by construction |
| H_on | 15.0 | frozen `ENTHALPY_TRANSITION`: Cunningham et al. 2019 Fig. 3A blue line (vapor-depression transition), app index 13.0 to 16.9 along speed | taken from frozen code, not from new data |
| A_kh | 0.70 | Gan et al. 2021 Eq. 6 eta_max = 0.7 (printed constant, row `gan2021-absorptivity` of `data/benchmark/keyhole-reference-relations-2026/published_relations.csv`) | published constant |
| H_s | 5.0 | ENTHALPY_KEYHOLE - ENTHALPY_TRANSITION = 20 - 15: 63 % of the rise is reached at the keyhole-mode onset (melt-pool D/W about 0.5, where the depression becomes deep enough for multiple reflections) | declared structural choice, not derived from data |

Cross-checks already in the repo were NOT used to set any value. They bracket 0.70, but none of them chose it:

| source | values |
|---|---|
| NIST mds2-2525, Ti-6Al-4V stationary pulse (`docs/LPBF_NIST_2525_ABSORPTANCE_COMPARISON_2026-10-08_la6-gusarov.md`) | keyhole-phase window mean 62.0 % (within-trace SD 7.1 pp); pre-keyhole 32.5 % |
| Simonds 2018 Table III, 316L stationary spot | coupling 0.31 without keyhole; up to 0.86 at 0.889 MW/cm2 |
| Trapp 2017, 316L scanning disc (digitized) | plateau about 0.76 to 0.79 at 100 and 500 mm/s |
| Ye 2019, minimal absorptivity Am | 0.26 (Ti-6Al-4V), 0.28 (IN625, 316L) |

Properties:

1. Continuous at H_on, monotone non-decreasing and bounded in [A_flat, A_kh].
2. Inside the v1 calibration bounds [0.25, 0.80] for every app alloy.
3. If A_flat >= A_kh, the law returns A_flat.
4. H is still computed with A_flat. The law is therefore explicit (no fixed-point iteration), and the 15/20
   thresholds keep the convention they were derived in.

Where A(H) enters (A0):

1. Eagar-Tsai and Goldak: absorbed power = A(H) P instead of A_flat P.
2. Rosenthal: eta_eff = A(H) REPLACES the uncited multi-reflection ramp (not stacked on it). The latent-heat factor
   1/(1 + 0.55 St) is unchanged.

Unchanged in A0: H itself, the regime label, `keyholePorosityRisk`, the Fabbro absorptivity (flat), the Rosenthal
keyhole increment heuristic (keyed to flat H), the process map, the `powder-raytrace` path (out of scope) and the
calibration layer (not used: this is a default-kernel comparison).

## 4. Secondary and sensitivity arms (reported only, cannot produce PASS)

| arm | change from A0 | purpose |
|---|---|---|
| S1 | A_kh = 0.62 (NIST mds2-2525 Ti-6Al-4V keyhole-phase mean, measured) | endpoint sensitivity, low |
| S2 | A_kh = 0.79 (Trapp 2017 Fig. 4, 316L disc 500 mm/s, highest plotted value 0.792, digitized) | endpoint sensitivity, high; digitized, context only |
| S3 | H_s = 2.5 | steeper rise |
| S4 | H_s = 10.0 | gentler rise |
| G | Gan 2021 Eq. 6 as published: A = max(A_flat, 0.7 (1 - exp(-0.6 X))), X = Am P / ((T_liq - T0) pi rho cp_s v r^2), Am from Ye 2019 Table 1, r = d/2, T_liq - T0 floored at 50 K as in H. It has no onset, so it can differ from baseline below H = 15. Unavailable for Inconel 718 (no Am) | published form without the app-anchored onset |
| K | A0 plus Fabbro absorptivity = A(H) on Eagar-Tsai and Goldak | keyhole A in the depth model as well |
| F | A0 form with A_kh = 0.70 fixed and H_s FITTED per kernel on the grid 1.0 to 20.0 step 0.5. Objective: equal-source-weighted depth MAPE on affected rows of the training sources. Leave-one-source-out over the five trainable sources: a trainable held-out source is scored with H_s fitted on the other four, a test-only source with H_s fitted on all five. Ties go to the larger H_s | shows what fitting would buy. If F passes the rule and A0 fails, that is recorded as a hypothesis for a NEW pre-registration, not as a PASS |

## 5. Data roles

| source | alloy | role | depth/width criteria (C1, C3) | significance (C2) | regime label set |
|---|---|---|---|---|---|
| hofmann-316l-2026 | 316L | held-out; trainable class (PI pool, arm F) | yes | yes | (i) measured D/W |
| ku-leuven-316l-2021 | 316L | held-out; trainable class; beam nuisance 37.5 / 75 um | yes | yes | (i), (ii) KU published |
| totis-ti64-2021 | Ti-6Al-4V | held-out; trainable class | yes | yes | (i) |
| ku-leuven-ti64-2021 | Ti-6Al-4V | held-out; trainable class; beam nuisance 37.5 / 75 um | yes | yes | (i), (ii) |
| lane-in625-2020 | Inconel 625 | held-out; trainable class | yes | yes | (i) |
| ghosh-in625-2018 | Inconel 625 | test-only (assumed spot; nuisance 140 / 100 um) | yes | no | (i) |
| trapp-316l-2017 | 316L | test-only (digitized; 0.5 mm discs; 117 W row has no depth, excluded) | yes | no | (i) |
| cunningham-ti64-2019, Fig. 3B, 95 um, 46 cases | Ti-6Al-4V | test-only (digitized; depth is VAPOR-DEPRESSION depth, not melt-pool depth) | no | no | (iii) Fig. 3A line labels; containment diagnostic D1 |
| guo-316l-2024, nist-amb2022-03-in718 | 316L, IN718 | catalog sentinels (used during physics development) | reported separately, never in the verdict | no | none |

Rules:

1. In A0 nothing is fitted, so every melt-pool source is held out. "Trainable class" only means the source may enter
   the PI90 residual pool (section 7, M5) and arm F. Leave-one-source-out applies to both: a source never contributes
   to its own interval or its own fitted H_s.
2. No digitized source and no source with an assumed spot size ever trains: not in the PI pool, not in arm F.
3. Endpoint and cross-check sources are never evaluation targets of the melt-pool criteria, because that would be
   circular: nist-mds2-2525, simonds-316l-2018, the Trapp absorptivity series, ye-2019-absorptivity and the Gan 2021
   relations.
4. Not used, with the same exclusions as the 2026-10-07 dataset comparison: zhao-ti64-2020 (porosity boundary, not
   melt-pool geometry), cmu-ti64-* (no power or beam diameter) and ku-leuven-in718-2021 (dimension units unresolved).
5. AlSi10Mg and Inconel 718 have no eligible held-out source. This evaluation says nothing about them.

## 6. Row rules

1. Rows and kernel inputs exactly as `python/tools/lpbf_calibration_fit_v2.py` builds them at 02503eed:
   1. same loaders and table sha256 pins;
   2. preheat 20 C;
   3. bare-plate rows with the nominal 30 um layer;
   4. Lane Table 3 powers (nominal power reported as sensitivity only);
   5. Trapp 117 W row excluded, Ghosh case 7 kept.
2. Hofmann balling-flagged rows are excluded from width metrics and kept for depth (v1 rule).
3. No row is removed on its measured response. Replicates stay separate rows; the bootstrap cluster is the
   parameter set (power, speed, spot, layer) within a source.
4. A row is "affected" when its flat H > H_on under the nuisance reading being scored. Affected flags depend only on
   inputs. They are written in the stage-1 record (section 9) before any kernel output exists.

## 7. Baseline and metrics

Baseline: the frozen `calculate_meltpool_physics` at 02503eed with `absorption_model="flat-plate"`, the same three
kernels (`eagar-tsai`, `goldak`, `rosenthal`), the same rows and inputs. For Eagar-Tsai and Goldak the baseline is
flat; for Rosenthal it is the uncited multi-reflection ramp. No calibration layer in either arm.

Each metric is computed per kernel, per arm and per source. The criteria use affected rows; all-row values are also
reported.

| id | metric | definition |
|---|---|---|
| M1 | depth MAPE | mean of abs(pred - meas) / meas over common resolved rows |
| M2 | width MAPE | same, width-eligible rows |
| M3 | skill | 1 - MAPE_candidate / MAPE_baseline, paired cluster bootstrap (`lpbf_calibration_stats.paired_skill`), B = 1000, seed 0, percentile CI95. Pooled skill = 1 - mean_s MAPE_cand,s / mean_s MAPE_base,s (equal source weight), stratified cluster bootstrap |
| M4 | regime classification accuracy | Prediction = kernel melt-pool D/W >= 0.5 (King 2014 / Cunningham 2019 melt-pool criterion, which is what the app's keyhole-mode label means). Label sets: (i) measured D/W >= 0.5 on every held-out melt-pool row with both dimensions, equal source weight; (ii) KU Leuven published `melting regime`, binary keyhole vs not (transition counts as not keyhole); (iii) Cunningham Fig. 3A labels on the 46 Fig. 3B 95 um cases, keyhole = above the red line. The index-based label (15/20 on flat H) is unchanged by construction and reported as a control |
| M5 | PI90 coverage | For held-out source s and quantity q, take the arm's residuals ln(meas/pred) on the trainable-class sources other than s. mu = mean of per-source means. sigma = sqrt(mean within-source variance + (between-source SD of the means, ddof 1)^2); the between term is 0 and flagged when fewer than 3 pool sources remain. PI90 = pred exp(mu +/- 1.6449 sigma). Coverage = share of s rows inside, with a Wilson 95 % interval; mean PI log-width reported |
| M6 | bias | signed mean relative error, reported |
| M7 | resolved rows | rows with status `computed` in each arm |

Diagnostics (reported, not in the verdict):

1. D1 containment: share of Cunningham 95 um cases where predicted melt-pool depth >= measured vapor-depression depth.
2. D2 absorptance shape: MAE of A(H) against the Trapp 2017 scanning 316L disc series (non-penetrated points;
   60 um 1/e^2, app 316L properties) versus the flat 0.42. Digitized, context only.
3. D3 envelope: every A(H) value inside [0.25, 0.80].
4. D4 conduction identity: candidate width and depth on non-affected rows equal the baseline exactly.

## 8. Decision rule (arm A0)

Eligible set E(k) for kernel k: the held-out sources among the five trainable-class sources, ghosh-in625-2018 and
trapp-316l-2017 that have at least 5 affected rows resolved in both arms and at least 3 clusters.

| criterion | rule |
|---|---|
| C1 depth direction | depth skill > 0 on EVERY source in E(k) |
| C2 depth significance | depth skill CI95 lower bound > 0 on AT LEAST ONE source in E(k) that is trainable-class (not digitized, spot not assumed) |
| C3 width non-regression | width skill >= -0.05 on every source in E(k), and pooled width skill CI95 lower bound >= -0.05 |
| C4 regime non-regression | accuracy_candidate >= accuracy_baseline (point estimate) on each label set (i), (ii), (iii) |
| C5 coverage non-regression | on every source in E(k) with n >= 10 rows per quantity: coverage_candidate >= coverage_baseline - 0.05 (absolute Wilson check, upper >= 0.90, reported) |
| C6 resolution | candidate resolves no fewer rows than baseline in every source |

Kernel verdict: PASS if C1 to C6 all hold. INCONCLUSIVE if E(k) has fewer than 2 sources or no trainable-class
source. Otherwise FAIL.

Nuisance: the verdict is computed on the 2 x 2 grid (KU beam 37.5 / 75 um) x (Ghosh spot 140 / 100 um). The primary
reading is 37.5 um and 140 um. If any kernel verdict differs across the four readings, the overall result is
INCONCLUSIVE (rejected: unresolved input).

Overall:

| result | condition |
|---|---|
| PASS | all three kernels PASS under all four nuisance readings |
| FAIL | at least one kernel FAILs and the verdicts are identical across the nuisance grid. Recorded as FAIL (mixed), with per-kernel detail, when some kernels pass |
| INCONCLUSIVE | eligibility not met, or nuisance disagreement |
| INVALID | parity check (section 9, stage 2) or D4 fails. No verdict until the harness is fixed; the law is never touched |

The rule is conjunctive over sources, kernels and readings, so no multiplicity correction is applied.

Robustness label, only on PASS: re-check C1, C3 and C4 under S1 to S4. The result is "PASS (robust)" if all three
hold in all four arms, otherwise "PASS (endpoint-sensitive)" with the failing arms named. The label does not change
the verdict and must be carried into the bump proposal.

## 9. Freeze and run procedure

1. Stage 0: commit this file and a machine-readable copy of every value above,
   `python/lpbf_regime_absorptivity_config.py`, whose sha256 is pinned in
   `python/test_lpbf_regime_absorptivity_config.py`. Neither file is in `lpbf_simulation.IMPLEMENTATION_SOURCE_FILES`
   and no frozen file imports them.
2. Stage 1 (input-only): `python/tools/lpbf_regime_absorptivity_eval.py --stage inputs` writes
   `docs/research/RESULT_regime_absorptivity_stage1_<date>.json`. It holds, per row, flat H under each nuisance
   reading, the affected flag, and eligibility per source and kernel. No kernel output. Committed before stage 2.
3. Stage 2 (parity): the evaluation harness rebuilds the kernel composition read-only from the frozen building blocks
   (`EagarTsaiField`, `GoldakField`, `rosenthal_temperature_C`, `_liquidus_extent`, `fabbro_keyhole_depth_m`).
   1. In baseline mode it must reproduce `calculate_meltpool_physics` width, depth and extent status on every row,
      kernel and nuisance reading (relative tolerance 1e-9, identical status).
   2. A test asserts the implementation fingerprint is still
      `ec7e1f7a6606e937e448fefe97549b49a7ddfe7b95376b93867ae007b0c12555`. A different fingerprint stops the run.
4. Stage 3: run all arms, compute all metrics and apply the verdict rule. Output
   `docs/research/RESULT_regime_absorptivity_<date>.md` and `.json` with the config sha256, repo commit, fingerprint,
   dataset table sha256s, bootstrap seed and the stage-1 record hash.

After the first stage-3 number exists, none of the following may change for this evaluation: the law, A_kh, H_on,
H_s, the arms, data roles, row rules, eligibility thresholds, metrics, margins (0.05), bootstrap size and seed,
label sets, nuisance grid, kernels. Any change is recorded as a deviation, the run is relabelled exploratory, and it
cannot produce PASS.

## 10. Consequences

PASS produces a planned physics bump PROPOSAL, not an implementation:
`docs/LPBF_IMPLEMENTATION_BUMP_<date>_regime-absorptivity.*` in the `tools/lpbf_bump_record.py` format, status
proposed. The proposal covers:

1. the frozen file to change (`lpbf_thermal_solver.py`), the fingerprint bump and a golden re-pin with intent;
2. the records to regenerate: dataset comparison, keyhole benchmark, NIST 2525 comparison and process map, plus
   calibration under a new calibration version, since kernel outputs change;
3. UI copy that says the absorptivity is flat;
4. the robustness label;
5. the per-alloy scope: Inconel 718 and AlSi10Mg have no eligible evidence and stay flat unless a separate transfer
   argument is approved.

Maintainer review and sign-off are required. No label is promoted.

FAIL: recorded as a negative result in the stage-3 RESULT file with the per-criterion table. An addendum line in
`docs/LPBF_KEYHOLE_THRESHOLD_EVIDENCE_2026-10-07.md` points to it (the frozen `KEYHOLE_DEPTH_BENCHMARK_NOTE` is not
edited). This law, its parameters and these arms are not retried. A different law needs a new dated
pre-registration that cites this one.

INCONCLUSIVE or INVALID: recorded with the reason; no bump proposal.

## 11. Exposure statement

Before writing this file the author read:

1. the 2026-10-07 dataset comparison header (dataset caveats, regime row counts);
2. `LPBF_KEYHOLE_THRESHOLD_EVIDENCE_2026-10-07.md`, which states that the Fabbro depth under-predicts the Cunningham
   vapor depth (median ratio 0.62 at 95 um), exceeds the measured 316L melt depth in 176/677 Hofmann tracks, and that
   Rosenthal is about equal to the vapor depth;
3. the NIST 2525 comparison;
4. the Trapp and Simonds absorptance tables;
5. the v2 pre-registration.

The calibration scorecards' per-source error tables were not opened for this purpose. The baseline errors are
therefore partly known; candidate errors are not. A_kh comes from a printed constant, and H_on and H_s come from
frozen thresholds, so no parameter was chosen from melt-pool residuals. The hypothesis itself was motivated by the
known keyhole depth under-prediction.

## 12. Known weaknesses (declared now)

1. H_s = 5 is a structural choice tied to the threshold spacing, not a measurement.
2. Inconel 625: the app note says measured keyhole rows sit at H 13.9 to 18.6, so rows below 15 are unchanged by A0.
   By design the law cannot help them.
3. Eagar-Tsai and Goldak depth is max(field depth, Fabbro depth). Where Fabbro dominates, A0 changes only width.
   Arm K reports the alternative.
4. Hofmann already shows the Fabbro depth above the measured melt depth in part of the tracks. More absorbed power
   can increase depth error there, which is a legitimate way for H1 to fail.
5. Several inputs are uncertain, and each is handled by role or nuisance rather than resolved:
   1. Totis: depth reference line unstated.
   2. KU Leuven: beam size and width operator unconfirmed.
   3. Ghosh: spot size assumed.
   4. Trapp: digitized, on thin discs.
   5. Cunningham: depth is not a melt-pool depth.
6. The PI90 is a simple pooled log-residual interval across alloys, not the calibration layer's interval.
7. A0 is evaluated on default kernels only. Interaction with the calibration layer is out of scope; a fitted eta can
   absorb part of the effect.

## 13. References

1. Gan et al. 2021, Nat. Commun. 12, 2379, doi:10.1038/s41467-021-22704-0, Eqs. 6-7.
2. Ye et al. 2019, Adv. Eng. Mater. 21, 1900185, doi:10.1002/adem.201900185, Table 1.
3. Simonds et al. 2018, Phys. Rev. Applied 10, 044061, doi:10.1103/PhysRevApplied.10.044061, Table III.
4. Simonds et al. 2022, NIST mds2-2525 v1.3.2, doi:10.18434/mds2-2525.
5. Trapp et al. 2017, Appl. Mater. Today 9, 341, doi:10.1016/j.apmt.2017.08.006, Figs. 3(a), 4, 6, 7.
6. Cunningham et al. 2019, Science 363, 849, doi:10.1126/science.aav4687, Fig. 3.
7. King et al. 2014, J. Mater. Process. Technol. 214, 2915, doi:10.1016/j.jmatprotec.2014.06.005.
8. Fabbro 2020, Appl. Sci. (keyhole depth eq. 2), as cited in `fabbro_keyhole.py`.
9. Repo: `python/lpbf_public_datasets.py`, `python/lpbf_literature_datasets.py`, `python/lpbf_keyhole_literature.py`,
   `python/lpbf_calibration_config_v2.py`, `docs/LPBF_CALIBRATION_V2_PREREGISTRATION_2026-10-07.md`,
   `docs/LPBF_KEYHOLE_THRESHOLD_EVIDENCE_2026-10-07.md`, `docs/LPBF_NIST_2525_ABSORPTANCE_COMPARISON_2026-10-08_la6-gusarov.md`.
