# LPBF melt-pool calibration artefact

`lpbf-meltpool-calibration-v1.json` is the versioned, hashed calibration artefact of the opt-in calibrated mode of the
Melt Pool lab. **Screening only, not validation.** It is written only by `python/tools/lpbf_calibration_fit.py`
(`npm run lpbf:calibration`); never edit it by hand.

- Every cell (kernel x alloy x quantity) carries a gate status: `enabled`, `within-source-only`, `rejected` or `no-data`.
  Only `enabled` cells may ever be served by `python/lpbf_calibration_layer.py`; the UI shows no calibrated-mode control
  while no cell is enabled for the chosen kernel and alloy.
- `contentSha256` is the sha256 of the canonical JSON (sorted keys, no spaces) with `contentSha256` and `calibrationId`
  blanked. The loader refuses a tampered file, unknown keys, a `configSha256` that differs from the compiled-in
  `CALIBRATION_CONFIG` (a config change needs a NEW calibration version), a proposed evidence promotion, and an
  `implementationHash` that differs from the live frozen-physics fingerprint (`CalibrationStale`).
- `scorecardRecord` / `scorecardSha256` point to the full scorecard record in `docs/LPBF_CALIBRATION_SCORECARD_<date>.json`.
- `evidenceKind` is `screening-only` and `proposedEvidenceKind` is `null`. Any label promotion is only ever proposed in a
  PROOF entry for maintainer approval; no code path derives a label from scores.
- Catalog sentinels (Guo, NIST IN718) were used while the frozen physics was developed. They never train, never enter the
  final fit, the between-source term or the gate; they are reported in a separate block of the scorecard.

Check without recomputing: `npm run lpbf:calibration:check`.

## Calibration v2 (2026-10-07)

`lpbf-meltpool-calibration-v2.json` (+ `.summary.json`) is a NEW pre-registered version
(`python/lpbf_calibration_config_v2.py`, `docs/LPBF_CALIBRATION_V2_PREREGISTRATION_2026-10-07.md`), written only by
`python/tools/lpbf_calibration_fit_v2.py` (`npm run lpbf:calibration:v2`, check: `npm run lpbf:calibration:v2:check`).
It adds Ghosh 2018 IN625 and Trapp 2017 316L as test-only held-out sources (never trained; they can only block a
cell) and a diagnostic absorptivity envelope (Trapp 2017, Ye 2019). v1 is unchanged and still verifies. The runtime
layer accepts only the v1 config hash, so calibrated mode never reads the v2 artefact (`servedByRuntime: false`).

## Error bands v1 (2026-10-07)

`lpbf-meltpool-error-bands-v1.json` (+ `.summary.json`, `.rows.json`) is the measured published-track error of the frozen
screening kernels, written only by `python/tools/lpbf_error_bands.py` (`npm run lpbf:bands`, check without a solver run:
`npm run lpbf:bands:check`; `--from-rows` re-derives the artefact from the committed row table after a statistics or
wording change). **Reporting only, Screening only, not validation.** It is not calibration: nothing is fitted and no
served value changes.

- Every published single track (Hofmann 316L, KU Leuven 316L/Ti64, Totis Ti64, Lane IN625, Trapp 316L, Ghosh IN625, NIST
  AMB2022-03 IN718) is run through the three frozen kernels at the default absorptivity (flat-plate). The relative error
  `pred / meas - 1` is summarised per kernel x alloy family (316L, Ti64, Ni = IN625 + IN718) x screening regime class
  (conduction / transition / keyhole / all; thresholds 15 / 20 on the normalised enthalpy, the solver's ENTHALPY_TRANSITION / ENTHALPY_KEYHOLE) x quantity (depth, width) with
  equal source weight: median, 10-90 % range, n rows, n parameter sets, sources, per-source medians.
- Eligibility (pre-declared in `PREDECLARED_depth_bands_machinecal.md`): at least 2 sources, 10 rows and 3 rows per source,
  otherwise `insufficient-data` (n and the sources are still listed). Eligible cells carry the leave-one-source-out
  coverage of the 10-90 % band built from the other sources; coverage >= 0.70 (nominal 0.80) is `band`, otherwise
  `band-under-covers`.
- Result today: no depth cell reaches the 0.70 floor (best: Eagar-Tsai 316L all regimes 0.68); four width family cells pass
  (Eagar-Tsai 316L all 0.75 and keyhole 0.75, Goldak 316L keyhole 0.74, Goldak Ni conduction 0.73). The per-source
  medians are the finding: the between-source offset is as large as the band half-width, so a band from published
  tracks does not predict the error on another lab's machine.
- The display (Build Job card, Melt Pool lab, process-window cell detail, run report) always prints n, the sources, the
  per-source medians and the measured held-out coverage, never a bare "+/- x %", and ends with the approved label line
  "Screening only · typical published-data error shown; transfer to another lab not established". The wording lives in
  `band_sentence` (`python/lpbf_error_bands.py`) and `src/data/lpbfErrorBands.ts`, pinned to one golden fixture
  (`tests/fixtures/lpbf-error-band-sentences.json`). The evidence label stays "Screening only"; no label, verdict or gate
  reads a band; `experimentalValidation` is false.
- `contentSha256` is the sha256 of the canonical JSON with `contentSha256` and `bandsId` blanked. The loader refuses a
  tampered file, unknown keys, a config hash that differs from the compiled-in `BANDS_CONFIG`, a proposed promotion and an
  `implementationHash` that differs from the live frozen-physics fingerprint (`BandsStale`). After any physics bump
  rerun `npm run lpbf:bands` (the unit test of the summary fails until then).
- Current artefact: `lpbf-meltpool-error-bands-2026-10-07-8cc89f494031`, contentSha256 `8cc89f494031d08806af0da8ad06c3a7de5add6572f9136b653dd6ad522fc1df`.
