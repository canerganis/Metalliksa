# SPEC: machine-specific (single-source) melt-pool calibration from the user's own tracks

File: `docs/research/SPEC_machine_calibration_2026-10-09.md`. Design only; nothing in the product implements it yet.
Pre-registration: `docs/research/PREDECLARED_machine_calibration_2026-10-07.md` (section B is this method; text and
date kept verbatim, it was written before the simulation ran). Labels unchanged: `experimentalValidation=false`,
evidence kind `screening-only`.

## Re-verification on ec7e1f7a (2026-10-09)

The design below was simulated on 2026-10-07 on the kernel grid of fingerprint `d92d1a3a…`. Two planned physics
bumps landed since (`d92d1a3a` → `cda80143` keyhole regime threshold; `cda80143` → `ec7e1f7a` LA-6 scan-normal
section, Gusarov 2007 balling sources, `geometricDefectScreen.modelId` v2). Result: **the kernel outputs did not
move, and every number in sections 0 to 11 stands on `ec7e1f7a6606e937e448fefe97549b49a7ddfe7b95376b93867ae007b0c12555`
(main `343da59e`).**

Evidence:

1. Full rebuild, not a sample. `docs/research/machcal/build_grid.py` on a clean worktree of main `343da59e` with the
   locked interpreter `.runtime/lpbf-win-py312` (`implementation_fingerprint()` printed `ec7e1f7a…` at start), same
   849 rows (`calib-proto/rows.json`), same call (flat-plate, layer 30 µm, hatch 100 µm), 3 kernels × 15
   absorptivity nodes (0.20 to 0.90 step 0.05) = 38 205 cells. The output file is byte-identical to the 2026-10-07
   grid: sha256 `25e993083a20259c0552b65744c4c340703b455f96087ed8b5e080bfeac87cc8` on both. Cell by cell
   (`compare_grids.py`): 38 205 of 38 205 exactly equal; max |ln ratio| = 0 for width, depth and normalised enthalpy
   in Eagar-Tsai, Goldak and Rosenthal; 0 status changes; 0 cells over 1e-3.
2. The five simulation scripts, rerun unchanged on the rebuilt grid, reproduce `machcal_results.json`,
   `machcal_oracle.json`, `machcal_gate2.json`, `machcal_gate2_big.json`, `machcal_gate3.json` and
   `machcal_report.md` byte for byte.
3. Why (explanation; the check above is the proof): the keyhole bump changed the regime threshold (keyhole at
   normalised enthalpy 20 instead of 30) and decoupled the porosity screen, and PROOF.md records melt-pool W/D/L
   unchanged. The LA-6 bump changed the scan-normal peak cross section (`lpbf_peak.py`), the defect screen
   (`lpbf_defect_diagnostics.py`) and Build Job wording. It does not edit `lpbf_thermal_solver.py`.

What did change is the regime class label. `machcal_oracle.py` and `machcal_gate3.py` classify with the
`d92d1a3a` split 15 / 30 on normalised enthalpy at the default absorptivity; the solver on `ec7e1f7a` uses 15 / 20.
No G1 to G7 number and no held-out MAPE uses regime classes, so the headline does not depend on it. The "regime
bias at default" column in section 1 and the G8 strata stay on the declared 15 / 30 split (method unchanged).
Sensitivity at 15 / 20 (oracle script with the threshold edited; not pre-registered, reported for the reader):
Hofmann Eagar-Tsai conduction +38 % (163 sets), transition +7 % (120), keyhole +17 % (393); Hofmann Rosenthal
+39 / +48 / +62 %; Totis Eagar-Tsai +80 / −38 / −15 %. KU Leuven 316L becomes one class (all 44 sets keyhole;
Eagar-Tsai −13 %, Rosenthal −9 %), so its "transition +90 %" in sections 0 and 1 rests on 4 sets at the old split
and is not a regime-split explanation on the current classifier. Its G6 false-pass rate is a draw statistic and
does not depend on the split, so it remains the counter-example.

A further caveat found on re-reading: the KU Leuven rows use beam diameter 37.5 µm. The 2026-10-09
regime-absorptivity pre-registration (`docs/research/PREDECLARED_regime_absorptivity_2026-10-09.md`, finding R4)
treats this as unverified (diameter or radius; nuisance readings 37.5 and 75 µm). The KU Leuven cells here use the
37.5 µm reading only.

### Scripts and data

`docs/research/machcal/` holds the scripts and their outputs: `build_grid.py` (kernel grid, about 16 min on 15
processes; writes `calib-proto/grid.json`, 2.7 MB, not committed), `compare_grids.py`, `machcal_sim.py` (section B
of the pre-registration), `machcal_oracle.py`, `machcal_gate2.py`, `machcal_gate2_big.py`, `machcal_gate3.py`, the
input rows `calib-proto/rows.json` and the committed outputs listed above. The interpolation check in
`machcal_sim.py` reads `depth_tdep_results.json` (2 MB, exact served default per row on `d92d1a3a`), which is kept
in the research archive and not committed. Without it the script skips that check and only the
`interpolationCheck` key and the first report line differ. That skip is the only edit to the archived scripts.
The gate families in `machcal_gate2.py` and `machcal_gate3.py` and the oracle ceiling were declared in their
docstrings after the first result and are reported as such.

Data: frozen kernels at absorptivity 0.20 to 0.90 step 0.05, flat-plate; ln-interpolation error at the served
default median |ln| 0.0003 for Eagar-Tsai and Goldak, 0.002 for Rosenthal. Stand-in "users" are Hofmann, KU Leuven
316L, Totis, KU Leuven Ti64 and Lane, each alone. No product code calls this, and nothing frozen is touched by the
design.

## 0. TL;DR (honest headline)

- **A single effective absorptivity fitted on 3–8 of the user's tracks does not make Eagar-Tsai or Goldak depth
  better on that user's other tracks.** Simulated on the literature sources as stand-in machines, the held-out
  depth MAPE got WORSE in 62–72 % of draws on Hofmann (35 → 37 %), 96–100 % on KU Leuven 316L (29 → 33 %), 44–62 %
  on Totis (37 → 37 %). The reason is structural, not statistical: the depth error of the lab kernels depends on
  the regime class (Hofmann ET: conduction +38 %, transition +2 %, keyhole +31 %; Totis ET: +80 / −35 / −12 %),
  and absorptivity moves all regimes together. Even the whole-source oracle (one eta fitted in-sample on all
  44–676 tracks) gains only 0–4 points (Hofmann ET 36.6 → 32.6 at eta 0.36; KU 316L 28.7 → 28.7).
- **A within-user leave-one-track-out gate cannot detect this.** LOO skill > 0 passes 24–62 % of the time and,
  conditional on passing, the held-out depth is worse 65–100 % of the time for ET/Goldak (false-pass rate). More
  tracks (12–24) and a two-regime consistency check (G8) do not fix it (false pass 0.75–0.98 on Hofmann ET/Goldak,
  0.59–0.83 on Totis ET): the gate is testing the wrong hypothesis.
- **It does work where the default bias is a uniform machine-level offset — Rosenthal depth (the Build Job
  kernel):** Hofmann 51 → 34 % held-out MAPE in every draw (worse in 0–7 %), gate G6 (uniform sign on ≥ 80 % of
  the user's tracks, |mean ln residual| ≥ 0.15, LOO skill > 0, eta not at a bound) passes 28–47 % of draws with a
  **0.00 false-pass rate** at 4–8 tracks and 0.50–0.61 at 12–24, the 80 % user band covers 0.80–0.84 of the
  held-out tracks (half-width ±65–85 %). Totis Rosenthal: 42 → 35 % (G6 pass 0.03–0.07, false 0.08–0.33). KU
  Leuven 316L Rosenthal is the counter-example: its error is regime-split (transition +90 %, keyhole −19 %), the
  fit helps on average (44 → 36 %) but G6 passes 4–20 % of draws and 82–100 % of those are false passes. KU Ti64
  Rosenthal (70 → 26 %) hits the 0.25 bound and is correctly refused. Lane IN625 (6 usable sets) is too small.
- Fitted eta on the Rosenthal cells is 0.29–0.35 (316L envelope 0.248–0.797: inside; Ti64 ≥ 0.255: at the bound).
  It is absorbed model error, not a measured absorptivity, and the spec says so in the label.
- Product consequence: the flow is worth building, but **gated by a pre-registered eligible-cell list derived from
  the stand-in simulation (today: Rosenthal depth for 316L and Ti-6Al-4V only; no ET/Goldak depth cell; width
  cells only via the joint rung where width did not worsen)**, plus the user-data gate G6, plus a user band from
  the LOO residuals. The user sees "calibrated for this machine (user data)" only for served cells; every other
  cell says why not, with the user's own residual summary. Evidence kind stays `screening-only`; nothing touches
  `experimentalValidation`, the global artefact, or the committed scorecard. The alternative "machine depth factor"
  (a multiplicative offset instead of eta) performs the same on Rosenthal (oracle 33.0 vs 32.6) and is more honest
  about being an empirical correction; it is listed for the maintainer's choice in section 9.

## 1. Simulation summary (numbers the design rests on)

Stand-in user = one literature source; m tracks drawn at random (one cross-section per parameter set), fit on
them, test on the source's remaining sets; 200 draws per cell; depth-only absorptivity rung `etaD` unless noted.
`worse%` = fraction of draws where the held-out depth MAPE rose; gates per section 3.

| stand-in | kernel | sets | HO depth MAPE default → cal, m = 6 (all draws) | worse % | G3 pass / false pass (m = 6) | G6 pass / false pass / cov80 (m = 6) | oracle eta-only (whole source) | regime bias at default |
|---|---|---|---|---|---|---|---|---|
| Hofmann 316L | eagar-tsai | 377 | 35.4 → 37.2 | 64 | 0.29 / 0.76 | 0.08 / 0.94 / 0.64 | 36.6 → 32.6 @ 0.36 | cond +38, tran +2, keyh +31 |
| Hofmann 316L | goldak | 350 | 38.6 → 39.4 | 55 | 0.29 / 0.75 | 0.07 / 0.60 / 0.69 | 40.7 → 35.0 @ 0.335 | +57 / +8 / +31 |
| Hofmann 316L | rosenthal | 349 | 51.0 → 34.9 | 3 | 0.64 / 0.00 | 0.45 / 0.00 / 0.82 | 58.5 → 32.6 @ 0.285 | +39 / +56 / +63 |
| KU Leuven 316L | eagar-tsai | 44 | 28.8 → 32.5 | 100 | 0.54 / 1.00 | 0.42 / 1.00 / 0.79 | 28.7 → 28.7 @ 0.415 | tran +31, keyh −18 |
| KU Leuven 316L | goldak | 44 | 28.8 → 32.2 | 100 | 0.54 / 1.00 | 0.42 / 1.00 / 0.79 | 28.7 → 28.7 | same |
| KU Leuven 316L | rosenthal | 44 | 43.9 → 36.3 | 32 | 0.39 / 0.26 | 0.10 / 1.00 / 0.74 | 43.8 → 34.3 @ 0.29 | tran +90, keyh −19 |
| Totis Ti64 | eagar-tsai | 80 | 36.9 → 36.7 | 46 | 0.70 / 0.56 | 0.41 / 0.70 / 0.78 | 36.5 → 34.0 @ 0.385 | cond +80, tran −35, keyh −12 |
| Totis Ti64 | goldak | 78 | 33.4 → 32.5 | 41 | 0.71 / 0.48 | 0.52 / 0.58 / 0.79 | 33.2 → 30.2 @ 0.40 | +63 / −31 / −12 |
| Totis Ti64 | rosenthal | 78 | 41.7 → 37.5 | 20 | 0.20 / 0.08 | 0.07 / 0.23 / 0.75 | 41.4 → 33.4 @ 0.25 (bound) | +45 / +8 / +18 |
| KU Leuven Ti64 | eagar-tsai | 14 | 28.0 → 20.3 | 21 | 0.42 / 0.26 | 0.12 / 0.40 / 0.87 | 28.6 → 17.6 @ 0.295 | tran +51, keyh +13 |
| KU Leuven Ti64 | goldak | 14 | 28.0 → 20.3 | 25 | 0.53 / 0.27 | 0.15 / 0.43 / 0.86 | 28.6 → 17.3 @ 0.295 | same |
| KU Leuven Ti64 | rosenthal | 14 | 68.9 → 25.7 | 0 | 0.01 (bound hit) | 0.00 (bound hit) | 69.0 → 26.6 @ 0.25 (bound) | tran +128, keyh +50 |
| Lane IN625 | eagar-tsai | 6 | m = 3: 28.3 → 37.7 | 96 | — | — | 25.1 → 25.0 | cond −1, tran −52 |

Joint rung `etaJoint` (one eta for width and depth): same depth picture; width changes −1.8 pt (Hofmann Goldak
15.3 → 13.5) to +4 pt (Totis ET 18.7 → 21.4); KU 316L Rosenthal width 57.7 → 49.4. Width-only calibration is a
separate quantity cell and is not the subject of this spec; the joint rung is allowed only where the eligibility
run shows width did not worsen (section 3.1).

More tracks (m = 12, 16, 24, `machcal_gate2_big.json`): Hofmann Rosenthal G6 pass 0.50–0.61, false 0.00, 51 → 34,
cov 0.83–0.84; Hofmann ET/Goldak G6 pass falls to 0.00–0.03 (correct refusal); KU 316L ET/Goldak false pass stays
1.00; Totis ET false 0.66–0.71. Regime-stratified draws with a two-class consistency gate G8 (`machcal_gate3.json`):
Hofmann Rosenthal pass 0.28–0.42 / false 0.00 / cov 0.81–0.84; Hofmann ET false 0.85–0.98; Totis ET 0.59–0.83.

## 2. Flow (user-facing)

1. Plan (exists): `python/tools/lpbf_next_experiment.py plan` → `plan.json`, plate layout, `measurement_template.csv`
   (`docs/LPBF_NEXT_EXPERIMENT.md`). New: `--for-machine-calibration` sets `n` ≥ 6, asks for ≥ 2 regime classes
   with ≥ 3 tracks each (the planner's coverage term already prefers under-represented classes; add a hard
   constraint) and records `plan.purpose = "machine-calibration"`.
2. Print and measure (exists): the user fills width/depth; import (exists): `lpbf_next_experiment.py import` →
   `.runtime/user-calibration/<user-id>/rows.json`, rows labelled `Measured (user-supplied)` (unchanged).
3. **Fit (new)**: `python/tools/lpbf_machine_calibration.py fit --user-source <rows.json> --out-dir
   .runtime/machine-calibration/<user-id>/` runs the frozen kernels through the public API (same call as
   `lpbf_calibration_fit._solver_call`, flat-plate) on the user's inputs for the absorptivity node grid (≈ 31 nodes
   × 3 kernels × m tracks ≈ 150–750 calls, 20 ms each), fits per kernel × quantity on the production fine grid with
   the production loss (`lpbf_calibration_stats.fit_ladder` with one source: set-averaged mean |ln| + λ = 0.05
   prior at the material default), runs the gate (section 3), computes the user band (section 4) and writes the
   **machine artefact** `machine-calibration.json` (section 5) plus `report.md`. Never writes to `docs/`,
   `data/calibration/` or the repo root (reuse `refuse_record_dir`).
4. Serve (new, opt-in): the Melt Pool lab and the Build Job get a "Machine calibration" selector listing the
   artefacts found under `.runtime/machine-calibration/` (status endpoint). When one is selected and the cell for
   (kernel, material, quantity) is `served`, the result shows the calibrated value with the user band and the
   label of section 6, next to the unchanged screening value. Everything else is unchanged.
5. Re-check: every served value also prints the user's own LOO residual summary (m, median, spread, per-regime
   medians) so the user sees what the gate saw.

The existing `--user-source` private scorecard run (user rows as an extra LOSO source) stays as it is; this spec
adds the single-source fit next to it, it does not replace it.

## 3. Gate (pre-registered; evaluated in the simulation; nothing tuned after)

### 3.1 Eligibility (per kernel × alloy × quantity; a committed list, not computed from the user's data)

A cell may be machine-calibrated only if the stand-in simulation on the published sources shows, for that kernel
× alloy × quantity, (a) at least one source where the whole-source oracle gain ≥ 10 MAPE points with a uniform
sign of the default residual across its regime classes, and (b) a G6 false-pass rate ≤ 0.05 on that source at
m = 6. Today's list (from this pass; to be regenerated by the tool's `eligibility` sub-command from the committed
kernel grid once it exists, and committed as `MACHINE_CALIBRATION_CONFIG.eligibleCells`):

| kernel | alloy | quantity | eligible | evidence |
|---|---|---|---|---|
| rosenthal | 316L Stainless Steel | depth | yes (1 of 2 stand-ins; KU Leuven 316L is a documented false-pass case) | Hofmann 51 → 34, G6 false 0.00 |
| rosenthal | Ti-6Al-4V | depth | yes, with bound watch (Totis 42 → 35, G6 false 0.08–0.33; KU Ti64 refused at the bound) | borderline: maintainer decides (section 9) |
| rosenthal | Inconel 625 | depth | no — Lane has 6 usable sets; not simulated | insufficient stand-in |
| eagar-tsai / goldak | any | depth | **no** — regime-dependent error, oracle gain < 5 pt, false pass 0.6–1.0 | sections 0–1 |
| any | any | width | not in this spec; a width cell may be added by the same procedure later | — |

### 3.2 Per-user gate G6 (all must hold; each is reported with its number)

1. m ≥ 4 resolved tracks (default and every absorptivity node `computed`), ≥ 2 regime classes present
   (reported; not a hard condition, because the stand-ins show it has no power), all inside
   `lpbf_simulation.BOUNDS`.
2. Uniform default offset: ≥ 80 % of the user's ln residuals at the default share one sign AND |mean| ≥ 0.15.
   (This is the condition that distinguishes a machine offset from the kernels' regime-shape error.)
3. LOO skill > 0: leave-one-track-out refits, 1 − MAE_ln(cal) / MAE_ln(default) > 0.
4. Fitted eta not within one fine-grid step of the bounds [0.25, 0.80] (KU Ti64 Rosenthal is refused by this).
5. Fitted eta inside the alloy's measured-absorptance envelope of calibration v2 (`absorptivityReferences`): 316L
   0.248–0.797; Ti-6Al-4V ≥ 0.255; IN625 ≥ 0.275 (diagnostic in v2, hard here because a single-source fit has no
   other guard against compensation).
6. The cell is in the eligibility list.
Outcome per cell: `served`, `refused:<reason>` (every failed condition listed), or `not-eligible`.

Expected behaviour (from the simulation): on a machine that behaves like Hofmann the Rosenthal depth cell is served
in about 30–45 % of 6-track campaigns and 50–60 % of 12–16-track campaigns, with a 0–1 % chance that serving makes
the depth worse; on a machine like KU Leuven 316L it is served in 4–20 % of campaigns and is wrong most of those
times — this residual risk is printed in the label (section 6) and is why the result stays screening-only.

## 4. User band

Per served cell: LOO residuals e_i = ln(meas_i / pred_i(eta fitted without track i)), i = 1..m; centre μ = mean e,
spread s = SD(e, ddof 1); 80 % band = value × exp(μ ± t_{0.90, m−1} · s · √(1 + 1/m)). Measured coverage of this
band on the stand-ins' held-out tracks: 0.80–0.84 (Hofmann Rosenthal, m 4–24), 0.71–0.76 (Totis Rosenthal),
0.74–0.79 (KU 316L, where the centre is wrong). Half-width in the simulation: ±60–85 % at m = 6–8, ±65 % at 16.
The band is shown only with its m and the sentence "80 % of your own held-out tracks fell inside a band like this
in the simulation on published sources; it is not a tolerance". Non-informative rule as in calibrated mode:
hi/lo > 2.5 → "not informative" flag (expected for m ≤ 5).

## 5. Machine artefact (`.runtime/machine-calibration/<user-id>/machine-calibration.json`, schema `lpbf-machine-calibration-1`)

```
{ schema, machineCalibrationId, userSourceId, generatedAt, implementationHash, codeRevision, toolSha256,
  configSha256 (MACHINE_CALIBRATION_CONFIG), userRowsSha256, planSha256,
  material, nTracks, nResolved, regimeClasses: {conduction: n, transition: n, keyhole: n},
  cells: [ { kernel, quantity, status: served|refused|not-eligible, reasons: [..], rung: etaD|etaJoint,
             eta, etaPrior, etaCi90 (bootstrap over tracks, 200 replicates), lossDefault, lossCal,
             gate: { uniformSignFraction, meanLnResidualDefault, looSkill, boundHit, envelopeOk, eligible },
             looResiduals: [..], band: { mu, s, t, level: 0.8, factors: [lo, hi], informative },
             perRegimeMedianLoo: {..}, envelope: {power, speed, beam ranges of the user's tracks} } ],
  evidenceKind: "screening-only", label: "Calibrated for this machine (user data): screening only, not validation",
  experimentalValidation: false, labelPromotionProposed: "none",
  honesty: "single-source fit of an effective absorptivity to the user's own unverified single-track measurements;
            it absorbs model error; no per-row uncertainty; the global calibration and scorecard are unchanged",
  contentSha256 }
```
Loader refusals mirror `lpbf_calibration_layer.load_calibration`: unknown keys, content hash, config hash, stale
implementation hash (`MachineCalibrationStale` → the UI says "re-fit after the physics bump"), evidence fields.

## 6. Labels and UI text (English; wording changes need the maintainer, section 9)

- Served value: `Depth 96 µm · calibrated for this machine (user data: 6 tracks, user-abc) · 80 % band 55–165 µm
  (not a tolerance) · Screening only — not validation`. Badge text `Screening only` unchanged; a second small
  badge `machine-calibrated (user data)` with the user source id. Tooltip: eta 0.33 (material default 0.42),
  gate numbers, "the absorptivity is an effective fitted value that absorbs model error".
- Refused cell: `Depth 120 µm (screening) · machine calibration not served: your 6 tracks do not show a uniform
  offset (4 over, 2 under; mean −4 %) — a single absorptivity cannot represent this`; or `… fitted absorptivity at
  the bound (0.25)`; or `… this kernel's depth error is regime-dependent on every published source; machine
  calibration is not offered for Eagar-Tsai / Goldak depth (see scorecard v2)`.
- Always: "Your measurements stay on this computer (`.runtime/machine-calibration/`), are not sent anywhere, do
  not change the published-track calibration or the scorecard, and do not become validation evidence."
- Never: "validated", "accurate", "qualified"; never a verdict change in the Build Job from the calibrated depth
  (the verdict keeps using the screening geometry; the calibrated depth is reported next to it with its band — a
  verdict on calibrated geometry is a separate maintainer decision).

## 7. Files (non-frozen; fingerprint unchanged)

- `python/lpbf_machine_calibration_config.py` (new): `MACHINE_CALIBRATION_CONFIG` with the gate constants
  (0.80, 0.15, bounds, envelope table copied by value from v2 with its sha, `eligibleCells`), `config_sha256()`.
  Not in `IMPLEMENTATION_SOURCE_FILES`; no frozen file imports it (extend the `test_lpbf_calibration_frozen` scan).
- `python/lpbf_machine_calibration.py` (new): `fit_machine(user_doc, kernel_table, cfg)` (pure; takes a kernel
  table dict like `lpbf_calibration_fit.build_table` so tests inject a fake), `gate_cell`, `user_band`,
  `build_artefact`, `load_machine_calibration`, `apply_machine_calibration(inputs, kernel, art, solver=...)`
  (screening unchanged + `machineCalibrated` block; same shape as `lpbf_calibration_layer.apply_calibration`).
- `python/tools/lpbf_machine_calibration.py` (new CLI): `fit`, `check`, `eligibility` (reads the committed
  calibration kernel-table cache `.runtime/cache/lpbf_calib_table.json` when present; otherwise refuses — the
  eligibility list is a maintainer action, not a user action).
- `python/lpbf_next_experiment.py`: `--for-machine-calibration` constraint and `plan.purpose`.
- `python/lpbf_machine_calibrated_meltpool.py` (new CLI) behind `POST /api/python/lpbf-machine-calibrated-meltpool`
  and `GET …/status` in `routes/physics.ts` (fits the authority rules; `AUTHORITY_ALLOWLIST.json` not grown).
- `python/lpbf_build_job_solver.py`: optional `machineCalibration: <id>` input → `machineCalibrated` block in the
  result (`extras` level, outside golden-compared keys); verdict unchanged.
- Frontend: `src/data/lpbfMachineCalibration.ts` (status + artefact summary types), selector + served/refused
  rendering in `CalibratedMeltpoolPanel.tsx` (a second section "Machine calibration (user data)"),
  `IndustrialLPBFDecisionLab.tsx` W×D tile second line, `LpbfExperimentPlanPanel.tsx` (the `fit` command added
  to `plan.commands` when `purpose = machine-calibration`), `LpbfRunReportExport.tsx` block "Machine calibration
  (user data)" with artefact id/sha, m, gate numbers, band.
- Docs: `docs/LPBF_NEXT_EXPERIMENT.md` section 4 "Machine calibration", `data/calibration/README.md` pointer,
  `docs/LPBF_ENGINEERING.md`, PROOF entry (label promotion: none).

## 8. Tests (self-contained; synthetic kernel table; no dataset, no solver, no GPU)

Python `python/test_lpbf_machine_calibration.py`:
1. fit recovers a planted eta: synthetic table D(eta) = D0·(eta/0.42)^1.3 with measurements at eta* = 0.33 plus
   noise → fitted eta within one fine step; LOO skill > 0; band covers the planted truth.
2. gate refusals, one per condition: 3 tracks (m < 4); mixed signs (3 over / 3 under) → `uniformSign`; |mean| 0.05
   → `offsetTooSmall`; planted eta 0.24 → `boundHit`; eta outside the envelope; cell not eligible
   (`eagar-tsai|depth`) → `not-eligible` even with a perfect fit.
3. regime-dependent planted error (+30 % conduction, −30 % keyhole, zero mean) → refused by `uniformSign` and the
   per-regime medians are reported.
4. artefact round trip: `build_artefact` → `load_machine_calibration` → unknown key / edited byte / config drift /
   stale hash refused; a stale artefact gives `available: false` without raising at the call site.
5. `apply_machine_calibration`: screening block byte-identical to the plain solver call (injected fake solver);
   calibrated value equals solver at the fitted eta; band factors applied; no D/W derived from mixed values.
6. CLI refuses `--out-dir docs/`, `data/calibration/`, repo root; `check` reproduces the artefact.
7. frozen guard: no `IMPLEMENTATION_SOURCE_FILES` entry imports the new modules; `python/lpbf_fingerprint_pin.py`
   unchanged.
8. eligibility sub-command on a synthetic kernel grid with one uniform-offset source and one regime-split source
   → the first cell eligible, the second not (thresholds 10 pt / 0.05).
TypeScript `tests/lpbf-machine-calibration.test.tsx`: selector hidden when no artefact; served cell renders the
exact label sentence and both badges; refused cell renders the reason text; Build Job tile shows the calibrated
depth next to, never instead of, the screening value; report block present; `plan.commands` gains the `fit`
command only for `purpose = machine-calibration`.
CI: add `test_lpbf_machine_calibration` to `.github/workflows/ci.yml` python list; `scripts/ci-unit-tests.txt` LF.

## 9. Needs the maintainer's decision before implementation

1. Evidence-label wording: the badge `machine-calibrated (user data)` and the sentence "calibrated for this
   machine (user data) · Screening only — not validation" are new label text. RULES.md evidence kinds include
   `Calibrated simulation`; this spec does **not** use that kind (the fit is single-source, unverified user data,
   model-error absorbing). If the maintainer wants the served value to carry `calibrated-simulation`, that is a
   label promotion and needs a PROOF entry and approval; the default here is `screening-only` everywhere.
2. Eligibility of Rosenthal Ti-6Al-4V depth (Totis G6 false pass 0.08–0.33 and the eta sits near the envelope
   bound): include with the bound watch, or 316L only until a second Ti64 stand-in with ≥ 20 sets exists.
3. Nuisance choice: effective absorptivity (this spec; consistent with the calibration layer) versus a plain
   "machine depth factor" exp(c) with the same gate (oracle: Hofmann Rosenthal 33.0 vs 32.6; simpler, no physics
   claim, no envelope check possible). The spec can be re-targeted to the factor with the same tests.
4. Whether the Build Job verdict may ever use the machine-calibrated depth (this spec: no; reporting only).
5. Minimum tracks: the spec sets 4 for the gate and 6 for the planner default; the simulation shows no benefit
   above ~8 for Rosenthal (pass 0.42–0.74 at 8, 0.50–0.61 at 16, false 0.00 throughout) and no rescue of
   ET/Goldak at any m — so "3–8 tracks" is enough for what can be calibrated, and nothing fixes what cannot.

## 10. Sonnet-ready work package (branch `feat/lpbf-machine-calibration`, after the maintainer answers section 9)

WP-M1 config + core: `lpbf_machine_calibration_config.py`, `lpbf_machine_calibration.py` (fit, gate, band,
artefact, loader, apply), `test_lpbf_machine_calibration.py` cases 1–5, 7. Acceptance: on the synthetic table the
planted eta is recovered; every gate refusal has its own test; `test_lpbf_calibration_frozen` passes.
WP-M2 CLI + eligibility + planner flag: `python/tools/lpbf_machine_calibration.py`, `lpbf_next_experiment.py`
(`--for-machine-calibration`, `plan.purpose`), tests 6, 8, `test_lpbf_next_experiment` extended. Acceptance:
`eligibility` on the committed kernel-table cache reproduces section 3.1 (Rosenthal 316L depth eligible; ET/Goldak
depth not) — run by the maintainer, not in CI.
WP-M3 serving: `lpbf_machine_calibrated_meltpool.py`, route + status, `lpbf_build_job_solver.py` extras block;
`test_lpbf_build_job` goldens unchanged; `tests/server-route-validation.test.ts` extended for the new route.
WP-M4 frontend + docs: selector, panel section, tile line, plan commands, report block; `tests/lpbf-machine-
calibration.test.tsx`; `npm run lint`, `npm run test:unit`, `npm run check:bundle`; real-browser check incl.
keyboard; docs + PROOF + STATUS. No `Ceiling-Review` trailer; commit messages end with the Claude co-author line.

## 11. What this does not show

The stand-ins are published sources, not machines: their replicates, cross-section method and measurement
uncertainty are unknown, and a user's tracks will differ from the plan's assumptions (powder layer 30 µm in the
grid, hatch 100 µm, preheat as stated). The simulation used one random cross-section per parameter set; real
users may measure replicates (the fit should then take the set mean, as `set_key` already groups replicates).
IN625 and IN718 were not simulated (Lane 6 usable sets; NIST is a sentinel). The user band is calibrated on the
same source the fit came from; it says nothing about a different powder lot, plate or machine state.
