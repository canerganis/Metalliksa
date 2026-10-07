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
