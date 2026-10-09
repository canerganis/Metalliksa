# Regime-dependent absorptivity law: pre-registration (2026-10-09)

File: `docs/research/PREDECLARED_regime_absorptivity_2026-10-09.md`

**PREDECLARED. Screening evaluation, not validation. No candidate number has been computed.** This file fixes the
law, its parameters, the data roles, the metrics, the baseline and the decision rule BEFORE the first prediction of
the candidate law exists. Repo state: `Metalliksa-1` origin/main `02503eed` (same tree as local `90f08ef6`), frozen
implementation fingerprint `ec7e1f7a6606e937e448fefe97549b49a7ddfe7b95376b93867ae007b0c12555`. Nothing in the frozen
solver changes in this evaluation. Labels stay as they are: `experimentalValidation=false`,
`validationStatus=unvalidated`, `productionReady=false`.

**Amended once, before any result.** Amendment 1 below governs wherever it differs from the original text
(commit `91174d2c`). The body sections 1 to 13 already carry the amended wording.

## Amendment 1 (2026-10-09, before any result)

State at amendment: the original pre-registration is commit `91174d2c` on branch `research/regime-absorptivity`. It
received an independent review (Codex Sol, verdict NEEDS-AMENDMENT: 5 blockers, 3 should-fix) before any result
existed. No stage-1, stage-2 or stage-3 output exists. The worktree holds two uncommitted harness drafts
(`python/lpbf_regime_absorptivity_config.py`, `python/lpbf_regime_absorptivity_kernel.py`) that were never run on a
dataset row, in either arm. Reading done for this amendment is listed in section 11, item 6.

| id | review finding | severity | decision | sections changed |
|---|---|---|---|---|
| R1 | C6 counts rows, so the candidate can resolve different rows than the baseline | blocker | accept | 6, 7.1, 8 |
| R2 | stage 1 claims "no kernel output" but needs eligibility that depends on resolved rows | blocker | accept | 6, 8, 9 |
| R3 | Trapp and Cunningham are both exposed cross-checks and verdict targets | blocker | accept | 4, 5, 7, 8, 11 |
| R4 | KU Leuven beam size and width operator unresolved; no source manifest | blocker | accept-modified | 5, 5a (new), 6, 8, 12 |
| R5 | C2 takes significance from any one source; C1 point estimates are not simultaneous evidence | should-fix | accept-modified | 7, 8 |
| R6 | coverage gate rewards wider intervals; Wilson interval ignores clustering | should-fix | accept-modified | 7, 8 |
| R7 | C4 scoring population, Cunningham ties and numeric edge cases unspecified | blocker | accept | 6, 7, 7.1, 8 |
| R8 | arm G is not "as published"; A0 framing and the 0.70 ceiling overstated | should-fix | accept | 1, 3, 4, 13 |
| A1 | author correction: the Totis depth datum IS stated in the repo provenance | n/a | correction | 5a, 12 |
| A2 | author addition: the Lane power reading is unresolved and could reach affected rows | n/a | change | 5a, 8 |

### R1. Rowwise preservation instead of row counts (accept)

Reason: equal counts allow the candidate to drop hard rows and pick up easy ones. Eligibility and the scoring
population now come from the baseline alone (R2), and the candidate must resolve every row of that population.

Changed sentences:

1. C6, was: "candidate resolves no fewer rows than baseline in every source". Now: "Rowwise preservation: every row of
   the frozen scoring population P_all(k, g, s, q) (section 6, rule 6) is resolved by the candidate (status
   `computed`, finite and positive width and depth). One unresolved row fails C6 for that kernel and reading."
2. Added (section 7.1): an unresolved candidate row is scored with absolute percentage error 1.0 in both quantities,
   counts as a miss for coverage and is left out of the interval-score mean (its count is reported). Rows that only
   the candidate resolves are never scored; their count is reported.

### R2. Stage 1 input-only, stage 2 baseline freeze (accept)

Reason: "resolved in both arms" needs kernel output, so it cannot sit in an input-only stage, and it must not wait for
the candidate.

Changed sentences:

1. Stage 1, was: "It holds, per row, flat H under each nuisance reading, the affected flag, and eligibility per
   source and kernel." Now: "It holds, per row, flat H under each input reading, the affected flag, input validity,
   gate status per quantity from the source manifest, the cluster key and the frozen labels; per source, the input
   eligibility counts. It holds no kernel output."
2. New stage 2 freeze: the baseline is run on every row; parity is checked; the scoring populations, E(k, g),
   E_W(k, g), the C4 populations, the PI pools and the evaluability flags are written and committed before the
   candidate law is executed on any dataset row.
3. E(k), was: "at least 5 affected rows resolved in both arms and at least 3 clusters". Now: "at least 5 rows and 3
   clusters in the frozen baseline scoring population P(k, g, s, depth), and baseline depth MAPE > 0 on it".

### R3. Exposed cross-check sources become diagnostic-only (accept)

Reason: Trapp Fig. 3(a) track geometry and the Trapp Fig. 4 absorptance at 500 mm/s are the same specimens and
campaign (the loader cross-checks one against the other); the author read that absorptance series and S2 takes its
endpoint from it. Cunningham Fig. 3A sets H_on (blue line) and, with King 2014, the 20 threshold that sets H_s; Gan
2021, the source of A_kh, analysed the Cunningham Ti-6Al-4V cases (Gan ref. 2); and the 2026-10-07 threshold note,
read before writing, gives the Rosenthal baseline score on the Cunningham labels (43/46). Different quantities from
one experiment are not independent evidence.

Changed sentences:

1. `trapp-316l-2017`, was: "test-only (digitized; 0.5 mm discs; 117 W row has no depth, excluded)", in E(k). Now:
   "diagnostic-only (D6), exposed: same experiment as the Trapp absorptance series. Never in E(k), C1 to C6, the PI
   pool or arm F."
2. Label set (iii), was part of C4. Now diagnostic D5 (Cunningham regime agreement), reported only. D1 stays
   diagnostic.
3. Section 5 rule 3, was: "Endpoint and cross-check sources are never evaluation targets of the melt-pool criteria,
   because that would be circular: ...". Now also names Trapp Fig. 3(a) geometry and the Cunningham Fig. 3A/3B data
   as diagnostic-only, and labels hofmann-316l-2026 and totis-ti64-2021 "held-out, partly exposed" (their baseline
   errors are partly known and they were the held-out checks of the 15/20 threshold bump). The KU Leuven published
   labels were not used to set the thresholds (stated in the threshold note) and stay in C4.

### R4. Frozen source manifest (accept-modified)

Reason: unresolved operators and conventions can move C3, C4 and the affected set. Accepted: a frozen manifest
(section 5a) with DOI, files and pins, columns, units, operators, specimen conditions and every conversion; ambiguous
response quantities leave the verdict. Modified: an input with a documented alternative reading stays in the verdict
as a nuisance axis instead of being excluded, because a PASS then has to hold under every reading, so the verdict
cannot depend on which reading is true; the cost is a higher chance of INCONCLUSIVE.

Changed sentences:

1. New section 5a. Rule: a measured response (width, depth) is gated only when its operator has a document locator.
   An unconfirmed response operator is reported, never gated. An input definition with a documented alternative
   becomes a nuisance axis; an input definition without one is a declared assumption (section 12).
2. KU Leuven width: operator inferred, article unread (HTTP 403), so KU width leaves C3, C5 and label set (i); it is
   reported as a diagnostic. KU beam stays on the nuisance grid (37.5 / 75 um). KU depth is gated under the new depth
   datum axis.
3. New nuisance axis "depth datum" (section 8): measured depth as published, or measured depth + 0.60 t (powder
   layer above the measurement datum), for every source.
4. Totis width is gated only if a stage-0 locator confirms its operator (section 5a, rule 3).

### R5. One pooled significance endpoint (accept-modified)

Reason: "at least one of up to five sources" is a selection over sources. Accepted: C2 becomes one pooled endpoint per
kernel and reading. Modified: per-source positive confidence bounds are not required, because several sources have
too few rows for that to be informative; instead the claim is restricted: C1 is a direction check, and no result
statement may say the law improves depth on every source.

Changed sentences:

1. C2, was: "depth skill CI95 lower bound > 0 on AT LEAST ONE source in E(k) that is trainable-class". Now: "pooled
   depth skill over the trainable-class sources in E(k, g) (equal source weight, stratified cluster bootstrap) has
   CI95 lower bound > 0".
2. Was: "The rule is conjunctive over sources, kernels and readings, so no multiplicity correction is applied." Now:
   section 8, "Multiplicity", which states the intersection-union argument for kernels and readings, the single
   pooled endpoint, and that C1 is not a significance claim.

### R6. Coverage gated with an interval score (accept-modified)

Reason: wider intervals can keep coverage without better prediction. Accepted: C5 also needs interval-score
non-regression, and Wilson intervals are descriptive. Modified: the arm-specific recentering (mu) is kept because it
is the declared out-of-source interval construction for both arms and the interval score penalises both width and
misses; the uncentred variant (mu = 0) is reported.

Changed sentences:

1. C5, was: "coverage_candidate >= coverage_baseline - 0.05 (absolute Wilson check, upper >= 0.90, reported)". Now:
   "(a) coverage_candidate >= coverage_baseline - 0.05 and (b) mean log interval score of the candidate <= 1.05 x that
   of the baseline".
2. Wilson intervals and a cluster-bootstrap interval for the coverage difference are reported, never gated.

### R7. Frozen C4 population and edge cases (accept)

Changed sentences:

1. M4, was: "(i) measured D/W >= 0.5 on every held-out melt-pool row with both dimensions". Now: "(i) affected rows of
   the frozen scoring population whose source has gated width and depth operators, balling-flagged rows excluded".
   "The criteria use affected rows" now holds for every criterion, including C4.
2. Ties: predicted and measured D/W >= 0.5 is keyhole (inclusive), computed from the 0.1 um-rounded kernel output and
   the published measured values. Cunningham labels and their `nearBoundary` flags are frozen in stage 1
   (diagnostic D5 reports all 46 and the non-boundary subset).
3. New section 7.1: zero baseline MAPE, undefined bootstrap replicates, nonpositive or nonfinite predictions,
   insufficient width rows, insufficient PI pools, variance conventions and the verdict when a criterion is not
   evaluable.

### R8. Honest labels (accept)

Changed sentences:

1. Arm G, was: "Gan 2021 Eq. 6 as published". Now: "G (Gan 2021 Eq. 6, adapted)", with its adaptations listed.
2. Section 1, was: "rises toward a published keyhole plateau". Now: "rises toward a ceiling taken from a published
   fitted relation".
3. A_kh, was: "published constant". Now: "asymptote of Gan's fitted effective energy-coupling relation; not a
   measured, universal optical plateau". A0 is called a literature-inspired screening surrogate.

### A1. Totis depth datum (author correction)

Was (section 12): "Totis: depth reference line unstated." The repo provenance (`TOTIS_PROVENANCE`) records it from
Vaglio et al. 2020 (Fig. 1, Fig. 2(b), Sec. 1.3): depth is measured from the top of the printed base, under the 25 um
powder layer. Section 12 is corrected; the datum axis covers the layer offset.

### A2. Lane power reading (author addition)

`LANE_POWER_QUESTION` marks applied versus commanded power as unresolved. Was: "Lane Table 3 powers (nominal power
reported as sensitivity only)". Now: Table 3 powers are primary; stage 1 records the affected flags under both
readings; if any Lane row is affected under either reading, the nominal reading joins the verdict grid, otherwise it
stays a reported sensitivity.

### What the harness drafts must change

1. Config: version `lpbf-regime-absorptivity-config-2`; `preregistration.commit` and `sha256Lf` point to the
   Amendment 1 commit and this file; add `sourceManifest` (section 5a), the depth-datum axis and the conditional Lane
   axis; Trapp moves from `testOnly` to `diagnosticOnly`; label set (iii) moves to diagnostics; C2, C4, C5, C6 and the
   verdict precedence as in section 8; `multiplicity` text replaced; arm G renamed and its adaptations listed;
   interval score settings (alpha 0.10, margin 1.05); stage-2 record path.
2. Kernel module: the law and the recomposition are unchanged. The G policy keeps its floor and clamp but must be
   labelled "adapted". No candidate call on dataset rows before the stage-2 commit.

## 1. Hypothesis

A single flat-plate absorptivity per alloy cannot represent the rise of coupled power once a vapor depression forms
(Simonds 2018 Table III, NIST mds2-2525, Trapp 2017, Ye 2019, Gan 2021). The keyhole benchmark of 2026-10-07 lists
"flat keyhole absorptivity" as one candidate cause of the depth under-prediction in keyhole conditions
(`KEYHOLE_DEPTH_BENCHMARK_NOTE` in `python/lpbf_thermal_solver.py`). H1: replacing the flat absorptivity of the
conduction-field kernels by a law A(dH/hs) that equals the flat value in conduction and rises toward a ceiling taken
from a published fitted relation (Gan 2021, eta_max = 0.70) improves held-out melt-pool depth without degrading
width, regime classification or interval quality. H0: it does not.

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

A0 is a literature-inspired screening surrogate, not a published law.

```
H     = A_flat P / (rho cp_s max(50, T_liq - T0) sqrt(pi alpha_s v r^3))      (unchanged, flat A)
A(H)  = A_flat                                                  for H <= H_on
A(H)  = A_kh - (A_kh - A_flat) exp(-(H - H_on) / H_s)          for H >  H_on
```

Functional form: a saturating exponential from the same family as Gan et al. 2021 Eq. 6 (eta = 0.7 (1 - exp(-0.6 Ke_m Ld*)),
after Ye et al. 2019). A0 is not Gan's relation: its independent variable is the app's flat H instead of Gan's
Ke_m Ld*, it has an onset, and it starts at the app's own flat value at the vapor-depression onset instead of at
zero. No parameter is fitted.

| parameter | value | source | status |
|---|---|---|---|
| A_flat | material authority `absorptivity_IR` at 02503eed (table in section 2) | `four_alloy_materials.py`, `SECONDARY_THERMOPHYSICAL_DB` | unchanged baseline value; makes conduction rows identical by construction |
| H_on | 15.0 | frozen `ENTHALPY_TRANSITION`: Cunningham et al. 2019 Fig. 3A blue line (vapor-depression transition), app index 13.0 to 16.9 along speed | taken from frozen code, not from new data |
| A_kh | 0.70 | Gan et al. 2021 Eq. 6 eta_max = 0.7 (printed constant, row `gan2021-absorptivity` of `data/benchmark/keyhole-reference-relations-2026/published_relations.csv`) | asymptote of Gan's fitted effective energy-coupling relation; not a measured, universal optical plateau. Gan's eta is an effective coupling coefficient, not a pure optical absorptance |
| H_s | 5.0 | ENTHALPY_KEYHOLE - ENTHALPY_TRANSITION = 20 - 15: 63 % of the rise is reached at the keyhole-mode onset (melt-pool D/W about 0.5, where the depression becomes deep enough for multiple reflections) | declared structural choice, not derived from data |

Cross-checks already in the repo were NOT used to set any value. They bracket 0.70, but none of them chose it. They
are context only and never evaluation targets (section 5, rule 3):

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
| S2 | A_kh = 0.79 (Trapp 2017 Fig. 4, 316L disc 500 mm/s, highest plotted value 0.792, digitized) | endpoint sensitivity, high; digitized, context only. Its source experiment is the diagnostic-only Trapp geometry (D6) |
| S3 | H_s = 2.5 | steeper rise |
| S4 | H_s = 10.0 | gentler rise |
| G | "G (Gan 2021 Eq. 6, adapted)": A = max(A_flat, 0.7 (1 - exp(-0.6 X))), X = Am P / ((T_liq - T0) pi rho cp_s v r^2). Adaptations to the published relation: (1) the floor max(A_flat, .) is added; (2) T_liq - T0 is floored at 50 K as in H; (3) app properties (solid rho and cp_s, liquidus) replace Gan's property set; (4) r = d/2 from the app's 1/e^2 diameter input; (5) Am from Ye 2019 Table 1. It has no onset, so it can differ from baseline below H = 15. Unavailable for Inconel 718 (no Am) | the published functional form, adapted to app inputs, without the app-anchored onset |
| K | A0 plus Fabbro absorptivity = A(H) on Eagar-Tsai and Goldak | keyhole A in the depth model as well |
| F | A0 form with A_kh = 0.70 fixed and H_s FITTED per kernel and reading on the grid 1.0 to 20.0 step 0.5. Objective: equal-source-weighted depth MAPE on the frozen scoring populations P(k, g, s, depth) of the training sources. Leave-one-source-out over the five trainable sources: a trainable held-out source is scored with H_s fitted on the other four, ghosh-in625-2018 with H_s fitted on all five. Ties go to the larger H_s | shows what fitting would buy. If F passes the rule and A0 fails, that is recorded as a hypothesis for a NEW pre-registration, not as a PASS |

## 5. Data roles

| source | alloy | role | gated quantities (C1, C2, C3, C5) | in pooled C2 | regime label set |
|---|---|---|---|---|---|
| hofmann-316l-2026 | 316L | held-out, partly exposed; trainable class (PI pool, arm F) | depth; width (balling-flagged rows excluded) | yes | (i) |
| ku-leuven-316l-2021 | 316L | held-out; trainable class; beam nuisance 37.5 / 75 um | depth only (width operator unconfirmed: reported, not gated) | yes | (ii) KU published |
| totis-ti64-2021 | Ti-6Al-4V | held-out, partly exposed; trainable class | depth; width only if confirmed at stage 0 (section 5a) | yes | (i) only if width confirmed |
| ku-leuven-ti64-2021 | Ti-6Al-4V | held-out; trainable class; beam nuisance 37.5 / 75 um | depth only (as KU 316L) | yes | (ii) |
| lane-in625-2020 | Inconel 625 | held-out; trainable class; conditional power axis (section 8) | depth, width | yes | (i) |
| ghosh-in625-2018 | Inconel 625 | test-only (assumed spot; nuisance 140 / 100 um) | depth, width | no | (i) |
| trapp-316l-2017 | 316L | diagnostic-only (D6), exposed: same experiment as the Trapp absorptance series and the S2 endpoint | none | no | none |
| cunningham-ti64-2019, Fig. 3B, 95 um, 46 cases | Ti-6Al-4V | diagnostic-only (D1, D5): depth is VAPOR-DEPRESSION depth; Fig. 3A lines set H_on and inform H_s; Gan 2021 analysed these cases | none | no | none in the verdict; Fig. 3A labels in D5 |
| guo-316l-2024, nist-amb2022-03-in718 | 316L, IN718 | catalog sentinels (used during physics development) | reported separately, never in the verdict | no | none |

Rules:

1. In A0 nothing is fitted, so every melt-pool source is held out. "Trainable class" only means the source may enter
   the PI90 residual pool (section 7, M5) and arm F. Leave-one-source-out applies to both: a source never contributes
   to its own interval or its own fitted H_s.
2. No digitized source and no source with an assumed spot size ever trains: not in the PI pool, not in arm F.
3. Never evaluation targets of the verdict, because that would be circular or exposed: the endpoint and cross-check
   sources nist-mds2-2525, simonds-316l-2018, the Trapp absorptivity series, ye-2019-absorptivity and the Gan 2021
   relations; the Trapp Fig. 3(a) track geometry (same experiment as the Trapp absorptivity series); the Cunningham
   2019 Fig. 3A lines and Fig. 3B/3C depths (they set H_on, inform H_s, and were analysed by Gan 2021). Trapp and
   Cunningham are reported as diagnostics only. "Partly exposed" marks held-out sources whose baseline errors were
   partly known to the author and that served as held-out checks of the 15/20 threshold bump (section 11); they stay
   in the verdict with that label.
4. Not used, with the same exclusions as the 2026-10-07 dataset comparison: zhao-ti64-2020 (porosity boundary, not
   melt-pool geometry), cmu-ti64-* (no power or beam diameter) and ku-leuven-in718-2021 (dimension units unresolved).
5. AlSi10Mg and Inconel 718 have no eligible held-out source. This evaluation says nothing about them.

## 5a. Source manifest (frozen; machine-readable copy in the config as `sourceManifest`)

| source | files and pins | width operator | depth operator and datum | units, conversions | beam input | specimen, layer t, preheat | gate status |
|---|---|---|---|---|---|---|---|
| hofmann-316l-2026 | Zenodo 10.5281/zenodo.16979848 `MeltpoolGeometryData.csv` (raw sha256 `5dd0629b...`); table `meltpool_geometry.csv` sha256 `d4bbc7a6...`; paper doi:10.1016/j.matdes.2026.115459 | weld_width_um at the original substrate surface (paper Fig. 2, Sec. 2.2) | penetration_depth_um, substrate surface to melt-pool bottom (paper Fig. 2, Sec. 2.2) | um; area column (mislabelled um) not used; d_laser mm x 1000 = um | d_laser diameter; definition not stated, 1/e^2 assumed (equal to D4sigma for the stated single-mode Gaussian); no alternative reading carried | plate with t_powder 0 / 30 / 60 um; t = t_powder; kernel layer input 30 um when t = 0; 20 C assumed | depth gated; width gated, balling-flagged rows excluded |
| totis-ti64-2021 | Mendeley 10.17632/s9438vb5xd.1 `Allegati.zip :: Data.xlsx` (sha256 `3211cbaa...`); table `tracks.csv` sha256 `3b5794f3...`; Data in Brief doi:10.1016/j.dib.2020.106443 | sheet "Track width (W)"; reference height not in the repo record | sheet "Track depth (D)", from the top of the printed Ti-6Al-4V base under the powder layer (Vaglio 2020 Fig. 1, Fig. 2(b), Sec. 1.3) | um; no conversion | 50 um, 1/e^2 stated | 25 um powder on a printed base (same job), t = 25 um; one track per cell; 20 C assumed | depth gated; width conditional (rule 3) |
| ku-leuven-316l-2021, ku-leuven-ti64-2021 | Figshare 10.6084/m9.figshare.15035733.v1, 15035703.v1 (316L), 15035709.v1, 15035712.v2 (Ti-6Al-4V), sha256 pinned in `KU_WAVE2_FILES`; table `conditions.csv` sha256 `e031aead...`; article doi:10.1016/j.jmatprotec.2022.117547 NOT read (HTTP 403) | "w exp" (processed file), full width INFERRED, not confirmed | "d exp" (processed file); datum and powder layer not stated | um (unit tag in the raw files; processed files untagged; 316L values equal raw section means); decimal comma read as point; model and error columns excluded by name | 37.5 um, diameter versus radius unverified: nuisance readings 37.5 / 75 um | layer not stated; t = 60 um in the datum reading (cited from the unread article by the 2026-10-05 KU IN718 record; unverified); 20 C assumed | depth gated (datum axis); width NOT gated; published labels used verbatim in (ii) |
| lane-in625-2020 | doi:10.1007/s40192-020-00169-1, PMC8194244 JATS XML (sha256 `19757c67...`, not committed); `table3_tracks.csv` sha256 `32fe10fb...` | Table 3 first "Cross Section (um)" column, track mean of N = 3 (column order confirmed: CBM means reproduce Table 4 Class Width) | Table 3 second "Cross Section" column; bare plate, depth below the plate surface | um; D4sigma used as the 1/e^2 diameter (equal for a Gaussian) | D4sigma 100 um (CBM), 170 um (AMMT), Table 1 | bare IN625 plate, t = 0; 20 C assumed; power: Table 3 (primary) versus nominal case power (conditional axis) | depth and width gated |
| ghosh-in625-2018 | doi:10.1007/s11837-018-2771-x; `fig1_tracks.csv` pinned in `lpbf_literature_datasets.py`; PDF sha256 `b89cd530...` (not committed) | printed "w" label in Fig. 1, CLSM section at track centre | printed "h" label in Fig. 1, below the bare plate surface | um; printed numbers, not digitized | not stated: nuisance readings 140 / 100 um | bare plate, t = 0; 20 C assumed | depth and width gated (test-only) |
| trapp-316l-2017 | doi:10.1016/j.apmt.2017.08.006; `fig3a_tracks_digitized.csv` | digitized Fig. 3(a) open circles | digitized Fig. 3(a) filled circles; 0.5 mm discs | um, read uncertainty 3 um | 60 um 1/e^2 stated | bare discs, t = 0 | diagnostic-only |
| cunningham-ti64-2019 | doi:10.1126/science.aav4687; pinned CSVs in `lpbf_keyhole_literature.py` | n/a | vapor-depression depth, digitized | um | 95 um | bare plate | diagnostic-only |

Manifest rules:

1. A measured response is gated only when its operator has a document locator in this table. An unconfirmed response
   operator is reported as a diagnostic, never gated, never in a label set.
2. An input definition with a documented alternative reading is a nuisance axis of the verdict grid (section 8). An
   input definition without one is a declared assumption (section 12).
3. Totis width: before stage 1, the worker reads Vaglio et al. 2020 (Data in Brief, open access) Fig. 1 and Fig.
   2(b). If the W definition is printed there, its locator and wording go into `sourceManifest` and Totis width is
   gated and enters label set (i); otherwise Totis width is reported only. This is recorded in the config before its
   sha256 is pinned (stage 0). No other source may be re-classified after stage 0.
4. The only conversions are the ones in the "units, conversions" column and the datum reading (section 8: measured
   depth + 0.60 t, phi = 0.60 as in the repo provenance). No other conversion, offset or rescaling is applied.

## 6. Row rules

1. Rows and kernel inputs exactly as `python/tools/lpbf_calibration_fit_v2.py` builds them at 02503eed:
   1. same loaders and table sha256 pins;
   2. preheat 20 C;
   3. bare-plate rows with the nominal 30 um layer;
   4. Lane Table 3 powers in the primary reading (nominal powers per section 8);
   5. Trapp 117 W row excluded, Ghosh case 7 kept.
2. Hofmann balling-flagged rows are excluded from width metrics and kept for depth (v1 rule).
3. No row is removed on its measured response. Replicates stay separate rows; the bootstrap cluster is the
   parameter set (power, speed, beam input, layer input) within a source. A row whose measured width or depth is
   missing, nonpositive or nonfinite is input-invalid for that quantity; it is listed in stage 1 with its reason.
4. A row is "affected" when its flat H > H_on under the input reading being scored. Affected flags depend only on
   inputs. They are written in the stage-1 record (section 9) before any kernel output exists. The depth datum axis
   does not change H.
5. Stage-1 input eligibility of row r for quantity q: input-valid for q, gated for q by the manifest, and not
   balling-flagged when q = width.
6. Frozen scoring populations, set at stage 2 from the baseline only. For kernel k, reading g, source s, quantity q:
   P_all(k, g, s, q) = stage-1 eligible rows of s for q whose baseline status is `computed` with finite, positive
   width and depth. P(k, g, s, q) = the affected rows of P_all(k, g, s, q). P is the scoring population of every
   criterion; P_all feeds the PI pool and the all-row reports. Neither changes after the stage-2 commit.
7. Rowwise preservation: a row of P_all that the candidate does not resolve (status other than `computed`, or a
   nonfinite or nonpositive width or depth) is a candidate failure (C6). Rows resolved by the candidate but not in
   P_all are never scored.

## 7. Baseline and metrics

Baseline: the frozen `calculate_meltpool_physics` at 02503eed with `absorption_model="flat-plate"`, the same three
kernels (`eagar-tsai`, `goldak`, `rosenthal`), the same rows and inputs. For Eagar-Tsai and Goldak the baseline is
flat; for Rosenthal it is the uncited multi-reflection ramp. No calibration layer in either arm.

Each metric is computed per kernel, per reading, per arm and per source. The criteria use the affected scoring
population P; values on P_all are also reported.

| id | metric | definition |
|---|---|---|
| M1 | depth MAPE | mean over rows of P(k, g, s, depth) of abs(pred - meas) / meas, row-weighted within the source |
| M2 | width MAPE | same, on P(k, g, s, width) |
| M3 | skill | per source: 1 - MAPE_candidate / MAPE_baseline, paired cluster bootstrap (`lpbf_calibration_stats.paired_skill`), B = 1000, `numpy.random.default_rng(0)` per call, clusters sorted by key string, percentile CI95. Pooled over a named source set S: 1 - mean_{s in S} MAPE_cand,s / mean_{s in S} MAPE_base,s (equal source weight); stratified cluster bootstrap: one `default_rng(0)` stream per pooled call, sources in sorted id order, for each source draw a (B, n_clusters_s) index array, replicate MAPEs row-weighted within source |
| M4 | regime classification accuracy | Prediction: kernel melt-pool D/W >= 0.5 (King 2014 / Cunningham 2019 melt-pool criterion, which is what the app's keyhole-mode label means). Label sets: (i) measured D/W >= 0.5 on the rows of P(k, g, s, depth) that also have a gated width and are not balling-flagged, sources whose width and depth operators are both confirmed (hofmann, lane, ghosh, totis if confirmed), measured depth under the datum reading g; accuracy = mean over sources with at least one such row of the per-source accuracy; (ii) KU Leuven published `melting regime` on the rows of P(k, g, s, depth) of the two KU sources, binary keyhole versus not (transition counts as not keyhole), equal weight of the two sources. The index-based label (15/20 on flat H) is unchanged by construction and reported as a control |
| M5 | PI90 coverage | For source s, quantity q, arm a: pool = the rows of P_all(k, g, j, q) for trainable-class sources j other than s (ghosh: all five), residuals ln(meas/pred_a), measured depth under the datum reading g. Per pool source: mean m_j and, when n_j >= 2, variance v_j (ddof 1). mu = mean of the m_j. sigma = sqrt(mean of the v_j + s_b^2), s_b = SD of the m_j (ddof 1) when 3 or more pool sources, else 0 and flagged. PI90 = pred_a exp(mu +/- 1.6449 sigma). Coverage = share of the rows of P(k, g, s, q) inside. Uncentred variant (mu = 0) reported |
| M6 | bias | signed mean relative error, reported |
| M7 | resolved rows | rows with status `computed` in each arm; sizes of P and P_all; candidate failures; rows resolved only by the candidate |
| M8 | log interval score | per row of P(k, g, s, q), with l, u the log PI90 bounds and y = ln(meas), alpha = 0.10: IS = (u - l) + (2/alpha)(l - y) [y < l] + (2/alpha)(y - u) [y > u] (Gneiting and Raftery 2007). Mean over the rows |

Coverage uncertainty: Wilson 95 % intervals of each coverage and a paired cluster-bootstrap CI95 of the coverage
difference (same scheme as M3) are reported. They are descriptive: replicated rows are clustered, and neither
interval is gated.

Diagnostics (reported, not in the verdict):

1. D1 containment: share of Cunningham 95 um cases where predicted melt-pool depth >= measured vapor-depression depth.
2. D2 absorptance shape: MAE of A(H) against the Trapp 2017 scanning 316L disc series (non-penetrated points;
   60 um 1/e^2, app 316L properties) versus the flat 0.42. Digitized, context only.
3. D3 envelope: every A(H) value inside [0.25, 0.80].
4. D4 conduction identity: candidate width and depth on non-affected rows equal the baseline exactly. A failure makes
   the run INVALID (section 8).
5. D5 Cunningham regime agreement (former label set (iii)): Fig. 3A labels on the 46 Fig. 3B 95 um cases, keyhole =
   above the red line, transition and conduction = not keyhole; reported on all 46 and on the cases with
   `nearBoundary` false. Labels and flags are frozen in stage 1.
6. D6 Trapp geometry: M1 to M3 and M4 (measured D/W) on the Trapp Fig. 3(a) rows with a plotted depth.
7. D7 ungated widths: M2, M3 and measured D/W accuracy for KU Leuven, and for Totis if its width stays unconfirmed.

### 7.1 Edge cases (fixed now)

1. Zero baseline MAPE: a source whose baseline MAPE on P(k, g, s, q) is 0 is removed from E(k, g) (depth) or
   E_W(k, g) (width) at stage 2, with the reason recorded.
2. Bootstrap replicates whose baseline MAPE is 0 are undefined. If more than 10 of the 1000 are undefined, that CI is
   not evaluable; otherwise the percentiles use the defined replicates and the undefined count is reported.
3. Baseline prediction nonpositive or nonfinite: the row is not in P_all (rule 6). Candidate prediction nonpositive or
   nonfinite: candidate failure (rule 7), scored with absolute percentage error 1.0 in both quantities, counted
   outside the PI90, left out of the M8 mean with its count reported.
4. Ties: D/W is computed from the 0.1 um-rounded kernel outputs and the published measured values; D/W >= 0.5 is
   keyhole for both prediction and measurement.
5. PI undefined: when the pool has fewer than 2 sources with rows, or no pool source with n_j >= 2, or sigma = 0. Then
   C5 is not evaluable for that (s, q).
6. Not evaluable criteria: see section 8, kernel verdict.

## 8. Decision rule (arm A0)

Verdict grid. Readings g are the combinations of these axes; the primary reading is listed first:

1. KU Leuven beam diameter: 37.5 um, 75 um.
2. Ghosh spot: 140 um, 100 um.
3. Depth datum: as published (t ignored), or measured depth + 0.60 t (t per section 5a: Hofmann t_powder, Totis 25 um,
   KU 60 um, Lane and Ghosh 0). This axis changes measured depths and measured D/W, never kernel inputs or H.
4. Lane power: Table 3, nominal case power. This axis is active only if stage 1 finds at least one Lane row affected
   under either power; otherwise the nominal reading is a reported sensitivity and the axis is absent.

The grid has 8 readings, or 16 with the Lane axis active.

Eligible sets, from the stage-2 record:

1. E(k, g): the five trainable-class sources and ghosh-in625-2018 with at least 5 rows and at least 3 clusters in
   P(k, g, s, depth) and baseline depth MAPE > 0.
2. E_W(k, g): the sources of E(k, g) with gated width, at least 5 rows and 3 clusters in P(k, g, s, width) and
   baseline width MAPE > 0.
3. T(k, g): the trainable-class sources in E(k, g).

| criterion | rule |
|---|---|
| C1 depth direction | depth skill point estimate > 0 on EVERY source in E(k, g). A direction check, not a significance claim |
| C2 depth significance | pooled depth skill over T(k, g) (M3, equal source weight, stratified cluster bootstrap) has CI95 lower bound > 0 |
| C3 width non-regression | width skill >= -0.05 on every source in E_W(k, g), and pooled width skill over E_W(k, g) has CI95 lower bound >= -0.05 |
| C4 regime non-regression | accuracy_candidate >= accuracy_baseline (point estimate) on each evaluable label set (i), (ii) (M4) |
| C5 interval non-regression | for every s in E(k, g) and q in {depth; width if s in E_W(k, g)} with at least 10 rows in P(k, g, s, q) and a defined PI in both arms: (a) coverage_candidate >= coverage_baseline - 0.05 and (b) mean M8 of the candidate <= 1.05 x mean M8 of the baseline |
| C6 rowwise preservation | every row of P_all(k, g, s, q), for every source and quantity, is resolved by the candidate |

Not evaluable: C2 when its CI is not evaluable (section 7.1); C3 when E_W(k, g) is empty or its pooled CI is not
evaluable; C4 when neither label set has a row (a label set without rows is skipped); C5 when no (s, depth) pair
qualifies.

Kernel verdict for kernel k and reading g, applied in this order:

1. INCONCLUSIVE if E(k, g) has fewer than 2 sources or T(k, g) is empty.
2. FAIL if any evaluable criterion C1 to C6 fails.
3. INCONCLUSIVE if C2, C3, C4 or C5 is not evaluable.
4. PASS otherwise.

The primary reading is KU 37.5 um, Ghosh 140 um, datum as published, Lane Table 3. If any kernel verdict differs
across the readings of the grid, the overall result is INCONCLUSIVE (rejected: unresolved input).

Overall:

| result | condition |
|---|---|
| PASS | all three kernels PASS under every reading of the grid |
| FAIL | at least one kernel FAILs and every kernel verdict is identical across the grid. Recorded as FAIL (mixed), with per-kernel detail, when some kernels pass |
| INCONCLUSIVE | eligibility or evaluability not met, or nuisance disagreement |
| INVALID | parity check (section 9, stage 2) or D4 fails. No verdict until the harness is fixed; the law is never touched |

Multiplicity. Each kernel and reading has one significance endpoint (C2, pooled). PASS requires every kernel and
reading to pass, an intersection-union rule, so the conjunction needs no adjustment of the per-test level (Berger
1982). C1, C3, C4 and C5 are non-regression or direction conditions that can only make PASS harder. C1 is a point
estimate per source and is not evidence of improvement on each source: no result text may claim that the law
improves depth on every source.

Robustness label, only on PASS: re-check C1, C3 and C4 under S1 to S4 at every reading. The result is "PASS
(robust)" if all three hold in all four arms, otherwise "PASS (endpoint-sensitive)" with the failing arms named. The
label does not change the verdict and must be carried into the bump proposal.

## 9. Freeze and run procedure

1. Stage 0: commit this file (Amendment 1), then a machine-readable copy of every value above,
   `python/lpbf_regime_absorptivity_config.py` (version `lpbf-regime-absorptivity-config-2`, pointing to the
   Amendment 1 commit and the LF sha256 of this file, including `sourceManifest` with the Totis width outcome of
   section 5a rule 3), whose sha256 is pinned in `python/test_lpbf_regime_absorptivity_config.py`, and the kernel
   module `python/lpbf_regime_absorptivity_kernel.py`. None of these files is in
   `lpbf_simulation.IMPLEMENTATION_SOURCE_FILES` and no frozen file imports them.
2. Stage 1 (input-only): `python/tools/lpbf_regime_absorptivity_eval.py --stage inputs` writes
   `docs/research/RESULT_regime_absorptivity_stage1_<date>.json`. It holds, per row: inputs under each input reading,
   flat H, the affected flag, input validity and reasons, gate status per quantity from the manifest, the cluster
   key, the KU published label, measured D/W under each datum reading, and the Cunningham Fig. 3A label with its
   `nearBoundary` flag. Per source: input-eligible and affected row and cluster counts per reading. Globally: whether
   the Lane power axis is active. It holds no kernel output. Committed before stage 2.
3. Stage 2 (parity and baseline freeze): `--stage baseline` writes
   `docs/research/RESULT_regime_absorptivity_stage2_<date>.json`.
   1. The harness rebuilds the kernel composition read-only from the frozen building blocks (`EagarTsaiField`,
      `GoldakField`, `rosenthal_temperature_C`, `_liquidus_extent`, `fabbro_keyhole_depth_m`). In baseline mode it
      must reproduce `calculate_meltpool_physics` width, depth and extent status on every row, kernel and input
      reading (relative tolerance 1e-9, identical status).
   2. A test asserts the implementation fingerprint is still
      `ec7e1f7a6606e937e448fefe97549b49a7ddfe7b95376b93867ae007b0c12555`. A different fingerprint stops the run.
   3. The record holds the baseline width, depth and status per row, kernel and input reading; P_all and P;
      E(k, g), E_W(k, g), T(k, g); the C4 populations; the PI pool memberships; the evaluability flags; and the
      sources removed under section 7.1. It holds no skill, coverage, accuracy or interval score.
   4. Committed before the candidate law (any arm) is executed on any dataset row. Unit tests of the law on synthetic
      H values are allowed before that.
4. Stage 3: `--stage run` refuses to start unless the stage-1 and stage-2 records are committed and their hashes
   match. It runs all arms, computes all metrics and applies the verdict rule. Output
   `docs/research/RESULT_regime_absorptivity_<date>.md` and `.json` with the config sha256, repo commit, fingerprint,
   dataset table sha256s, bootstrap seed and the stage-1 and stage-2 record hashes.

After the first stage-3 number exists, none of the following may change for this evaluation: the law, A_kh, H_on,
H_s, the arms, data roles, the source manifest, row rules, the frozen populations, eligibility thresholds, metrics,
margins (0.05 and 1.05), the interval-score alpha, bootstrap size and seed, label sets, verdict grid axes and
readings, kernels. Any change is recorded as a deviation, the run is relabelled exploratory, and it cannot produce
PASS.

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
   argument is approved;
6. the A0 label: a literature-inspired screening surrogate with a ceiling from a fitted relation, not a measured law.

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
   vapor depth (median ratio 0.62 at 95 um), exceeds the measured 316L melt depth in 176/677 Hofmann tracks, that
   Rosenthal is about equal to the vapor depth, and that the King D/W indicator on the Rosenthal melt pool scores
   43/46 on the Cunningham Fig. 3A labels; it also names Hofmann and Totis as the held-out checks of the 15/20 bump;
3. the NIST 2525 comparison;
4. the Trapp and Simonds absorptance tables (the Trapp series is the same experiment as the Trapp Fig. 3(a) geometry);
5. the v2 pre-registration.

The calibration scorecards' per-source error tables were not opened for this purpose. The baseline errors are
therefore partly known; candidate errors are not. A_kh comes from a printed constant, and H_on and H_s come from
frozen thresholds, so no parameter was chosen from melt-pool residuals. The hypothesis itself was motivated by the
known keyhole depth under-prediction. Because of items 2 and 4, Trapp geometry and the Cunningham data are
diagnostic-only and Hofmann and Totis carry the label "partly exposed".

6. For Amendment 1 (after the review, before any result) the author read the review, the loader provenance records
   in `python/lpbf_public_datasets.py`, `python/lpbf_literature_datasets.py` and `python/lpbf_keyhole_literature.py`,
   the KU Leuven `conditions.csv`, the Lane Table 3 and Trapp Fig. 3(a) track tables, the threshold basis in
   `lpbf_thermal_solver.py`, the `paired_skill` and `wilson` helpers, and the two harness drafts. These hold measured
   inputs and responses and code, no model output of this evaluation. No kernel was run.

## 12. Known weaknesses (declared now)

1. H_s = 5 is a structural choice tied to the threshold spacing, not a measurement.
2. Inconel 625: the app note says measured keyhole rows sit at H 13.9 to 18.6, so rows below 15 are unchanged by A0.
   By design the law cannot help them.
3. Eagar-Tsai and Goldak depth is max(field depth, Fabbro depth). Where Fabbro dominates, A0 changes only width.
   Arm K reports the alternative.
4. Hofmann already shows the Fabbro depth above the measured melt depth in part of the tracks. More absorbed power
   can increase depth error there, which is a legitimate way for H1 to fail.
5. Several inputs are uncertain, and each is handled by role, manifest gate or nuisance axis rather than resolved:
   1. Totis: tracks on a 25 um powder layer over a printed base; the depth datum is stated (base top) and the layer
      offset is bracketed by the datum axis; the width operator is gated only if confirmed at stage 0.
   2. KU Leuven: beam size unverified (nuisance axis), width operator unconfirmed (width not gated), depth datum and
      powder layer not stated (datum axis with an unverified t = 60 um).
   3. Ghosh: spot size assumed (nuisance axis).
   4. Trapp: digitized, on thin discs, and exposed: diagnostic only.
   5. Cunningham: depth is not a melt-pool depth, and the data set H_on: diagnostic only.
   6. Hofmann: beam diameter definition not stated; 1/e^2 is assumed and no alternative reading is carried.
   7. Lane: applied versus commanded power unresolved (conditional axis).
6. The PI90 is a simple pooled log-residual interval across alloys, not the calibration layer's interval. Its centre
   is arm-specific (recentred on the pool), which is why C5 also gates the interval score.
7. A0 is evaluated on default kernels only. Interaction with the calibration layer is out of scope; a fitted eta can
   absorb part of the effect.
8. A grid of 8 or 16 readings with "any disagreement gives INCONCLUSIVE" makes INCONCLUSIVE more likely. This is the
   accepted price of not resolving the inputs by choice.
9. Without Trapp, and with KU and possibly Totis widths reported only, C3 and label set (i) rest on fewer sources than
   the original text implied.

## 13. References

1. Gan et al. 2021, Nat. Commun. 12, 2379, doi:10.1038/s41467-021-22704-0, Eqs. 6-7.
2. Ye et al. 2019, Adv. Eng. Mater. 21, 1900185, doi:10.1002/adem.201900185, Table 1.
3. Simonds et al. 2018, Phys. Rev. Applied 10, 044061, doi:10.1103/PhysRevApplied.10.044061, Table III.
4. Simonds et al. 2022, NIST mds2-2525 v1.3.2, doi:10.18434/mds2-2525.
5. Trapp et al. 2017, Appl. Mater. Today 9, 341, doi:10.1016/j.apmt.2017.08.006, Figs. 3(a), 4, 6, 7.
6. Cunningham et al. 2019, Science 363, 849, doi:10.1126/science.aav4687, Fig. 3.
7. King et al. 2014, J. Mater. Process. Technol. 214, 2915, doi:10.1016/j.jmatprotec.2014.06.005.
8. Fabbro 2020, Appl. Sci. (keyhole depth eq. 2), as cited in `fabbro_keyhole.py`.
9. Hofmann et al. 2026, Materials & Design 262, 115459, doi:10.1016/j.matdes.2026.115459; data Zenodo
   doi:10.5281/zenodo.16979848.
10. Vaglio, Totis et al. 2020, Data in Brief, doi:10.1016/j.dib.2020.106443; data Mendeley doi:10.17632/s9438vb5xd.1.
11. Coen, Goossens, Van Hooreweder 2022, J. Mater. Process. Technol. 304, 117547, doi:10.1016/j.jmatprotec.2022.117547
    (not read); data Figshare as listed in section 5a.
12. Lane et al. 2020, Integr. Mater. Manuf. Innov. 9, doi:10.1007/s40192-020-00169-1, Tables 1, 3, 4.
13. Ghosh et al. 2018, JOM 70, 1011, doi:10.1007/s11837-018-2771-x, Fig. 1.
14. Gneiting and Raftery 2007, J. Am. Stat. Assoc. 102, 359, doi:10.1198/016214506000001437 (interval score).
15. Berger 1982, Technometrics 24, 295 (intersection-union tests).
16. Repo: `python/lpbf_public_datasets.py`, `python/lpbf_literature_datasets.py`, `python/lpbf_keyhole_literature.py`,
    `python/lpbf_calibration_config_v2.py`, `docs/LPBF_CALIBRATION_V2_PREREGISTRATION_2026-10-07.md`,
    `docs/LPBF_KEYHOLE_THRESHOLD_EVIDENCE_2026-10-07.md`, `docs/LPBF_NIST_2525_ABSORPTANCE_COMPARISON_2026-10-08_la6-gusarov.md`.
