# LPBF next-experiment kit

Screening: experiment proposal; not a print recommendation.

The kit proposes which single tracks to print and measure next so that a measurement teaches the melt-pool
calibration the most, lays them out on a plate, and reads the user's own measurements back as one extra trainable
source for a private scorecard run. Nothing here changes the frozen physics (`lpbf_simulation.IMPLEMENTATION_SOURCE_FILES`
is untouched), nothing derives an evidence label, and the scorecard evidence stays `screening-only`, label promotion `none`.

## 1. Plan

```
python -B python/tools/lpbf_next_experiment.py plan --material "316L Stainless Steel" \
  --power 100 400 --speed 400 1600 --spots 70,100 --layer-um 40 --preheat-c 80 \
  --n 12 --seed 1 --plate-x-mm 120 --plate-y-mm 120 --out-dir .runtime/next-experiment/run1
```

Required: material, power and speed ranges, spot diameters (at most 8), layer, preheat, `n` (1..48), seed and the
plate size. There is no default plate size; a request without one is refused. All inputs must lie inside
`lpbf_simulation.BOUNDS` (read-only); nothing is clipped. `--existing points.csv` (columns `power_W,speed_mm_s,spot_um`)
lists tracks already measured. `--out-dir` refuses `docs/`, `data/calibration/` and the repository root.

Outputs: `plan.json` (schema `lpbf-next-experiment-plan-1`), `print_plan.csv`, `plate_layout.csv`,
`plate_layout.svg`, `measurement_template.csv`.

### Candidates

A log-spaced grid in power and speed (`--grid`, default 9, at most 15 per axis) times the listed spots: at most
15 x 15 x spots candidates. Each candidate runs the three frozen kernels exactly like
`lpbf_calibration_fit._solver_call` (flat-plate, default absorptivity). A candidate where fewer than two kernels
resolve with status `computed` is excluded and counted in `plan.json` (`candidates.excluded`), never scored.

### Information score

Three terms, each scaled to [0, 1] and weighted by `NEXT_EXPERIMENT_CONFIG.weights` (1.0, 0.5, 1.0):

1. Kernel disagreement: sample SD (ddof 1) of ln W and of ln D across the resolved kernels, averaged, divided by
   the largest value among the candidates.
2. Calibration interval width: ln(hi/lo) of the 90 % conformal interval of the matching **enabled** scorecard
   cells (`data/calibration/lpbf-meltpool-calibration-v1.json`, via `load_calibration` / `cell_for`), averaged over
   the kernel x quantity cells of the material and divided by ln(2.5). It is `null` when no enabled cell with an
   interval exists, and the plan states so. In the committed artefact no cell is currently enabled, so this term is
   `null` for every material today. It depends only on the material, so it is the same for every candidate of a
   plan and never changes the ranking inside one plan.
3. Coverage: 0.5 if the candidate's input-only regime class (normalised enthalpy at the default absorptivity) has
   fewer than `minSetsPerClass` (8) training parameter sets (existing points count), plus 0.5 x min(1, d / 3) where
   d is the distance to the nearest training or existing point in standardised ln P, ln v, ln spot. With no training
   points the term is at its maximum and `nearestDistanceStd` is null.

### Greedy batch selection

After each pick every remaining candidate is multiplied by prod_j (1 - exp(-d_ij^2 / (2 L^2))) over the chosen and
existing points; `L` = 0.25 in unit-range ln coordinates of the candidate grid (the one documented constant,
`neighbourLengthScale`). Ties go to the lowest candidate index (sorted by P, v, spot). The selection is a pure
function of the inputs, the calibration artefact and the training tables; the seed only shuffles the plate order.
`plan.json` records the config constants, `configSha256`, and the calibration artefact's `contentSha256`,
`configSha256` and implementation hash, plus the per-track score breakdown.

### Plate

Pitch = max(3 mm, 10 x the largest spot); tracks are 10 mm long, one pitch of edge margin, slots filled row by row
and assigned to the track ranks by a seeded shuffle. A plate too small for `n` tracks is refused with the size needed.

## 2. Measure and import

Print the tracks, measure width and depth, and fill `width_um` and `depth_um` in `measurement_template.csv`. A blank
cell excludes the track with a reason; nothing is imputed.

```
python -B python/tools/lpbf_next_experiment.py import --plan <dir>/plan.json \
  --measurements <dir>/measurement_template.csv --source-id user-my-run
```

The import joins on `track_id` with identical power, speed and spot (a mismatch, an unknown or repeated track id, or
a non-finite or non-positive width or depth refuses the whole import). The source id must match
`^user-[a-z0-9-]{3,40}$` and must not collide with an existing source or an earlier import. It writes
`.runtime/user-calibration/<id>/rows.json`; every row carries the label `Measured (user-supplied)`. That label
describes the user's own data only; it says nothing about the screening model and is never promoted.

## 3. Private scorecard run

```
python -B python/tools/lpbf_calibration_fit.py --user-source .runtime/user-calibration/user-my-run/rows.json \
  --out-dir .runtime/user-scorecard/run1 --table-cache .runtime/cache/lpbf_calib_table.json
```

`--user-source` is repeatable and requires `--out-dir`, which refuses `docs/`, `data/calibration/` and the repository
root. The user rows join as one extra trainable source in a copy of the configuration
(`dataRoles.userSources`; the copy's sha256 is the recorded `configSha256`). Leave-one-source-out, the gate, the rungs
and the intervals are unchanged, so the user source is held out once and also trains the others; it is never a catalog
sentinel. The user's material needs at least one other trainable source of that alloy. The artefact written by a
private run carries the new config sha256, so the runtime loader refuses it: it can never become the committed
calibration by accident. Without the flag the tool's output is byte-identical (`--check` passes). The kernel table
cache is extended by the user's inputs (about 90 frozen-solver calls per track).

## UI

Process Parameter Search lab, third tab "Plan experiments": load a `plan.json` from disk (validated by
`src/data/lpbfExperimentPlan.ts`), see the table, the plate, CSV downloads and the commands above. It makes no
network or worker call and runs no solver. Computing a plan inside the app is a follow-up.

## Limits

A proposal ranked by model disagreement, interval width and data coverage; it does not check printability, does not
choose parameters to print, and validates nothing. User measurements carry no per-row uncertainty and are not
independently verified. CI modules to add (not edited here): `test_lpbf_next_experiment`, `test_lpbf_user_measurements`.
