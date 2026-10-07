# Keyhole-regime bump — drift reasons (d92d1a3a… → cb5f6ecc…)

Companion to `LPBF_IMPLEMENTATION_BUMP_2026-10-07_keyhole-regime.json`, the tool output of

`python -B tools/lpbf_bump_record.py --from-revision 6f6f58f5 --with-parity-check --slow --expect-drift <the 8 entries of ….expect-drift.txt>`

run at the re-pin commit `577f92f4` (python tree clean, `worktreeDirty: false`) in the locked warp-less reference interpreter `.runtime/lpbf-win-py312` (G11/G18 ran, not skipped). Result: **2 DRIFT, 23 PASS, 0 FAIL**; `pinMatchesToHash: true`, `versionUnchanged: true` (`enthalpy-fv-6`). Base: main `6f6f58f5` (pin `d92d1a3a…`). Manifest files changed (1 of 36): `lpbf_thermal_solver.py`.

The allowlist was derived from all diff keys of a full check of this tree (not the printed list): 8 exact keys, all in G11 (7) and G18 (1) — the two cases that call `calculate_meltpool_physics`. The transient reference path never reads the regime, so G1–G10, G12–G17, G19 and the NPZ case are bit-equal.

## Causes

| id | cause | source | files |
|---|---|---|---|
| KR-1 | Regime keyhole-mode threshold 30 → 20 (repo convention): overlap of King 2014 30±4 converted by 1.351 (19.3–25.2) and the Cunningham 2019 Fig. 3A red line (17.3–20.0). Keyhole string "Keyhole Mode (melt-pool D/W > 0.5 screening onset)", process-map label "Keyhole Mode"; 20 ≤ dH/hs < 30 moves Transition → Keyhole; `regimeBasis` added. | King et al. 2014; Cunningham et al. 2019 (+ SM); `docs/LPBF_KEYHOLE_BENCHMARK_2026-10-07_keyhole-regime.*` | `lpbf_thermal_solver.py` |
| KR-2 | `keyholePorosityRisk` decoupled from the regime index: same numeric gate (15/30), honest labels (Negligible / Possible / High), `keyholePorosityBasis`, `keyholePorosityResolved: false`. | Zhao et al. 2020 | `lpbf_thermal_solver.py` |
| KR-3 | Text only: `KEYHOLE_INCREMENT_BASIS` (15/30 are the heuristic's own legacy constants), `FABBRO_BASIS` + `keyholeModel.depthBenchmarkNote` (benchmark under/over-prediction). The cause of the Fabbro Ti-6Al-4V under-prediction is not resolved; leading hypotheses are the flat keyhole absorptivity (no A(R) multiple-reflection term) and no vaporisation heat sink; tracked as a later bump. No number changes. | keyhole benchmark | `lpbf_thermal_solver.py` |

All widths, depths, lengths, vapor-cavity depths, η_eff, temperatures, recoil, Marangoni, solidification, balling, Tang/LoF, contours and thermal slices are bit-equal to `6f6f58f5` on a 462-case snapshot (7 alloys × 11 P–v × 2 spots × 3 kernels); only label/basis text keys differ (the legacy 15/30 band edges are kept as `KEYHOLE_INCREMENT_FULL_AT` for the Rosenthal increment, the grid depth proxy and the transverse contour shape).

## Drift by case (raw before → after)

| case / observation | before | after |
|---|---|---|
| g11 `meltpool.0` IN718 200/800/80 Rosenthal (dH/hs 23.67) | regime "Transition Mode"; porosity "Low-Moderate (Occasional Fluctuations)"; grid cells 20–30 "Transition"/"Keyhole Defect Zone" | regime "Keyhole Mode (melt-pool D/W > 0.5 screening onset)"; porosity "Possible (15 <= dH/hs < 30; …)"; grid "Keyhole Mode"; basis fields; geometry equal |
| g11 `meltpool.1` Ti64 280/1200/70 Eagar–Tsai (39.05) | "Keyhole Mode (Deep Vapor Cavity)"; "High (Vapor Bubble Entrapment / Pore Defect Risk)" | new keyhole string; "High (screening proxy dH/hs >= 30; not a porosity boundary: …)" |
| g11 `meltpool.2` 316L 370/600/60 Goldak (64.67) | as above | as above |
| g11 `thermalSolver.classify_enthalpy_regime` | classifier thresholds 15/30, deep-vapor-cavity string | 15/20, new string |
| g11 `…canonicalSha256` / `…typedSha256` ×3 | tool hashes of the full thermal dicts | hashes of the same dicts with the text/label keys above (`meltpool.N.geometry` entries unchanged) |
| g18 `meltpool.in625` IN625 200/800/80 Rosenthal (25.62) | "Transition Mode"; "Low-Moderate (…)" | keyhole mode; "Possible (…)" |

## Goldens

Not re-recorded in this commit (separate guarded commit).

## Labels

Evidence labels unchanged: `experimentalValidation=false`, `validationStatus=unvalidated`, `productionReady=false`. Keyhole mode is not keyhole porosity; the threshold is derived for Ti-6Al-4V and 316L and transferred for IN718 / IN625 / AlSi10Mg.
