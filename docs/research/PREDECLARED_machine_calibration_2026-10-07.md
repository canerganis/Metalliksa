# Pre-declared methods: empirical depth/width error bands and machine-specific calibration simulation

Written BEFORE running either script (2026-10-07, second Fable, read-only design pass). Repo main; implementation
fingerprint of every input artefact `d92d1a3a…` (scorecard v2, keyhole benchmark, scratchpad tdep rows, calib-proto grid).
No solver call is made: both scripts read existing result files only.

## A. Error bands (`bands_eval.py` -> `bands_results.json`)

Data: `scratchpad/depth_tdep_results.json` rows (863, 8 sources, 4 alloys), prediction `pred["<kernel>|C0"]`
(C0 = the frozen physics exactly as served: material default absorptivity, flat-plate, 20 C preheat unless stated).
Only rows with `status == "computed"` and a finite measured value enter; excluded counts are reported.

Cell = kernel x regime class x alloy family.
- regime class: the app's input-only classifier on the row's normalised enthalpy at the default absorptivity
  (`dH` in the row; thresholds 15 / 30, `lpbf_calibration_stats.regime_class_from_enthalpy`). Balling-flagged rows
  (Hofmann) stay in their enthalpy class (the app's screening label is enthalpy-based; balling is a separate flag);
  their count is reported per cell.
- alloy family: `316L` (316L SS), `Ti64` (Ti-6Al-4V), `Ni` (Inconel 625 + Inconel 718). Per-alloy cells are also
  reported for Ni so the pooling can be judged.
- quantity: depth and width, each its own table.

Statistic: relative error r = pred / meas - 1 (sign: positive = model over-predicts). Reported per cell:
median, 10th and 90th percentiles of r with EQUAL SOURCE WEIGHT (each row weighted 1 / n_rows_of_its_source
inside the cell; weighted quantiles by cumulative weight), n rows, n parameter sets, n sources, source ids,
n balling-flagged rows, and the row-pooled (unweighted) quantiles for comparison.

Eligibility (declared now): a cell shows a band only when n_sources >= 2 AND n_rows >= 10 AND every source in the
cell has >= 3 rows; otherwise "insufficient data" (its n and sources are still listed so nobody can mistake the
blank for "no error").

Coverage check (leave-one-source-out): for each eligible cell and each source s in it, the 10-90 % band is
recomputed from the other sources only (equal source weight) and the fraction of s's rows inside that band is
recorded. Reported per cell: coverage per held-out source, the equal-source-weight mean coverage, the row-pooled
coverage, and the nominal 80 %. A cell is "calibrated-coverage" when the equal-weight mean coverage >= 0.70
(allowing for n_sources as small as 2); otherwise it is labelled "band under-covers held-out sources" and the
spec must display the widened interval (see below) or "insufficient data". The 0.70 floor is declared here, not
tuned afterwards.

Widened band (declared now, used only when the LOSO check fails): the 10-90 % band of the LOSO-held-out residuals
themselves (every row scored with the band it was NOT part of) -- i.e. the empirical interval that would have been
needed; reported next to the naive band.

Catalog sentinels (nist-amb2022-03 IN718) and digitized sources (trapp, ghosh) are included but flagged; a cell
whose band rests on sentinel rows only is labelled as such.

Not comparable, excluded: Cunningham / Zhao vapour-depression depths (keyhole benchmark) are a different quantity
from the melt-pool depth; reported in the spec as a separate caveat, never pooled into the bands.

Prediction before running: depth bands will be wide (10-90 % roughly -40 % … +60 % for ET/Goldak conduction on
316L, dominated by the Hofmann +30 % over-prediction and the KU/Trapp under-prediction), width bands about
-25 % … +15 %; LOSO coverage will fall below 0.80 in the 316L depth cells because the between-source offset
(s_source 0.17-0.29 in ln) is comparable to the band half-width, and Ti64 / Ni cells will mostly be "insufficient
data" (1-2 sources). Rosenthal depth will show the widest bands.

## B. Machine-specific calibration simulation (`machcal_sim.py` -> `machcal_results.json`)

Data: `scratchpad/calib-proto/grid.json` (frozen kernels on absorptivity nodes 0.20..0.90 step 0.05 for 849 rows,
flat-plate, layer 30 um, hatch 100 um) and `calib-proto/rows.json` (measured W, D). Stand-in "users" = the five
trainable sources (hofmann-316l-2026, ku-leuven-316l-2021, totis-ti64-2021, ku-leuven-ti64-2021, lane-in625-2020),
each one alone. Kernels: all three.

Fine grid: ln-linear interpolation between nodes to eta in [0.25, 0.80] step 0.005 (production fit grid). The
served default is the interpolation at the material default (0.42 / 0.35 / 0.38); the interpolation error at the
default is measured against `depth_tdep_results.json` C0 on matching rowIds and reported.

Track = parameter set (source, P, v, spot); a set's measurement is one randomly chosen replicate row (the user
measures one cross-section per track). Only sets whose default and every fine-grid node resolve ("computed") enter.

Experiment: for each source x kernel x m in {3, 4, 5, 6, 8}: 200 random draws (seed = draw index) of m sets as the
"user's tracks"; the remaining sets of the same source are the held-out machine tracks. Draw is skipped when the
source has fewer than m + 3 sets.

Fit (identical loss to production, single source so source weights are moot): eta_D = argmin over the fine grid of
mean |ln(meas_D / pred_D(eta))| + 0.05 ln(eta / eta_prior)^2; eta_W likewise; eta_joint on the mean of both.
Rungs scored: default; etaD (depth-only absorptivity, width untouched); eta_joint (one eta for both).
No regime offset c_D (not enough tracks; pre-registered nuisance list = absorptivity only).

Gate candidates (declared now, evaluated side by side; the spec picks by the numbers):
 G1 leave-one-track-out (LOO) inside the user's m tracks: skill_LOO = 1 - MAE_ln(cal) / MAE_ln(default) > 0;
 G2 G1 and the fitted eta not within one fine step of a bound [0.25, 0.80];
 G3 G2 and m >= 4;
 G4 G3 and LOO MAPE of the calibrated rung <= 25 %.
Reported per (source, kernel, m, rung, gate): pass rate; among passes: held-out MAPE default -> calibrated (median
over draws and 10-90 %), fraction of passes where the held-out MAPE got worse ("false pass"), and the held-out
coverage of the user band.

User band (declared now): depth_cal x exp(mean_LOO ln-residual +/- t_{0.9, m-1} x SD_LOO x sqrt(1 + 1/m)) -- the
LOO residuals of the user's own tracks give both the centre and the spread; coverage is measured on the held-out
tracks of the same source. The nominal level is 80 % (10-90 %).

Prediction before running: depth-only eta fits on 3 tracks will pass G1 about half the time by chance and
false-pass often (> 30 %); with 6-8 tracks the held-out depth MAPE should drop by 5-15 points on Hofmann and KU
316L (within-source works in the scorecard), little or nothing on Totis (within-source skill was ~0), and the
80 % band should cover 65-80 % of held-out tracks. Rosenthal should gain the most on depth because its default
depth bias is the largest. A gate requiring m >= 5 and LOO skill > 0 is expected to bring the false-pass rate
under 20 %.
