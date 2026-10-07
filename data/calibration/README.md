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
