# LPBF melt-pool calibration v2: pre-registration (2026-10-07)

**Screening only, not validation.** This file records the v2 protocol decisions BEFORE any v2 number was computed.
The machine-readable form is `CALIBRATION_CONFIG_V2` in `python/lpbf_calibration_config_v2.py`; its sha256 is pinned
in `python/test_lpbf_calibration_v2_config.py`. Results are written to new files
(`docs/LPBF_CALIBRATION_SCORECARD_v2_<date>.*`, `data/calibration/lpbf-meltpool-calibration-v2.json`) by
`python/tools/lpbf_calibration_fit_v2.py`.

## Why a new version

With the v1 sources, nuisance absorptivity fitted on one source does not transfer to the next (no cell `enabled`).
Wave 5 (commit 9c315139) added literature datasets (`python/lpbf_literature_datasets.py`). Adding a source changes
the config, so it needs a new pre-registered version. v1 (`CALIBRATION_CONFIG`, config sha256
`6926386ddf9ad2a0d9fc787b4dbca7324b20b466e7a806be38b949fbafa1271b`, its artefact and the 2026-10-07 scorecard) is not
edited and still verifies (`npm run lpbf:calibration:check`).

## Data roles

| source | alloy | role in v2 | why |
|---|---|---|---|
| hofmann-316l-2026, ku-leuven-316l-2021, totis-ti64-2021, ku-leuven-ti64-2021, lane-in625-2020 | as v1 | trainable (unchanged) | v1 roles carried over |
| guo-316l-2024, nist-amb2022-03-in718 | as v1 | catalog sentinel, test-only (unchanged) | used while the physics was developed |
| ghosh-in625-2018 (7 rows) | Inconel 625 | **test-only** | experimental spot size not stated; 140 um is an assumption |
| trapp-316l-2017 (10 of 11 rows) | 316L | **test-only** | values digitized from a figure; 0.5 mm discs, not semi-infinite |

Rules:

1. No digitized source and no source with an assumed spot size ever trains (fit, rung selection, `s_source`, final fit).
2. A test-only source is scored with exactly what the alloy's cell would serve: the final fit and the served rung,
   trained on all trainable sources of the alloy, and the final cell's interval (80 / 90 %).
3. A test-only source enters the gate as one more held-out source, with the unchanged v1 checks (skill CI95 lower
   bound >= -0.02, PI90 coverage Wilson upper >= 0.90 when n >= 10, no extra unresolved rows, at least one held-out
   source with lower bound > 0). It can only block `enabled`.
4. A test-only source counts as the missing second source of a single-source alloy only if it is not digitized, has
   no assumed spot size and has at least 10 rows (`gate.minRowsForCoverage`; below that the coverage check cannot be
   run). Neither wave-5 source qualifies, so Inconel 625 stays single-source in v2 by rule, whatever the numbers.
5. Test-only folds do not enter the fold-wise eta consistency check or the between-source term `s_source`.
6. Ghosh spot nuisance: the decision must be identical with beam diameter 140 um (primary, the paper's FE input) and
   100 um (Lane 2020 D4sigma of the same laboratory's EOS M270), else `rejected: unresolved input`. Same rule as the
   KU Leuven 37.5 / 75 um reading, which is kept.
7. Trapp: the 117 W row has no plotted depth and is excluded from both quantities (reported). No row is cut on its
   measured response (deep rows approaching the disc thickness are kept and declared).
8. Ghosh case 7 depth (38 um vs Lane 91 um at the same nominal P/v) is kept and recorded, not resolved.

## Absorptivity references

Used as an external sanity envelope on fitted effective absorptivity, never as a training target, prior centre or
gate input. Rule (config `absorptivityReferences`): lower = min(reference - read uncertainty), upper = max(reference +
read uncertainty) when a scanning calorimetric series exists for the alloy, else one-sided.

| alloy | envelope | from |
|---|---|---|
| 316L | 0.248 - 0.797 | Trapp 2017 disc + powder series (points flagged "penetrated" excluded), Ye 2019 Am 0.28 |
| Ti-6Al-4V | >= 0.255 | Ye 2019 Am 0.26 (Rubenchik 2015 powder 0.65-0.72 is static, unmelted: context only) |
| Inconel 625 | >= 0.275 | Ye 2019 Am 0.28 |

Checked on etaW, etaD and etaJoint of every final fit and every leave-one-source-out fold fit; outside ->
diagnostic flag `outsideMeasuredAbsorptivityEnvelope`. Known weakness: the 316L envelope covers almost the whole fit
bound [0.25, 0.80], and the other two alloys have a lower bound only, so this can only catch gross compensation.

Not used: Ghosh Fig. 2 lengths (length is not a calibrated quantity), Heigel 2020 cooling rates (3D-build thermal
target).

## Unchanged

Kernels, absorptivity grids, bounds, prior (centre = material default, lambda 0.05), source weights, rung ladder and
selection, bootstrap sizes and seeds, interval levels, every gate threshold, the v1 measured-absorptance bands
(Simonds 2018, NIST mds2-2525) and the hard physics-compensation flags. Test `test_lpbf_calibration_v2_config.py`
asserts that every one of these blocks equals v1.

## Headline numbers

`headline` = equal source weight over every held-out source (trainable folds and test-only).
`headlineTrainableOnly` = the v1 definition, kept for the before/after comparison.

## Exposure

The runtime layer (`python/lpbf_calibration_layer.py`) only accepts the v1 config hash, so a v2 artefact cannot reach
calibrated mode. If a v2 cell passes the unchanged gate, it is reported and not exposed in the UI: exposure needs
maintainer approval. No evidence label is promoted; `experimentalValidation` stays false.
