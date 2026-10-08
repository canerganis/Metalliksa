# la6-gusarov bump: drift reasons (cda80143... -> ec7e1f7a...)

Companion to `LPBF_IMPLEMENTATION_BUMP_2026-10-08_la6-gusarov.json`, the tool output of

`python -B tools/lpbf_bump_record.py --from-revision 4f5faa3a --with-parity-check --slow --expect-drift <the 97 entries of ....expect-drift.txt>`

run at the second re-pin commit `26db2ace` (fingerprint `ec7e1f7a6606...`; the first pin `5f9d651e` was superseded because the exported provenance title still credited Gusarov & Smurov 2010). The pre-bump parity goldens (`cda80143`, from `4f5faa3a`) were checked out into the working tree for the run, so the record says `worktreeDirty: true`; the python sources were at `26db2ace` in the locked warp-less reference interpreter `.runtime/lpbf-win-py312` (CPython 3.12.10, NumPy 2.2.6, no `warp`). Result: **17 DRIFT, 8 PASS, 0 FAIL, 0 SKIP** (G11 and G18 ran); `pinMatchesToHash: true`, `versionUnchanged: true` (`enthalpy-fv-6`). Base: branch `feat/lpbf-la6-gusarov-bump` from main `4f5faa3a` (taban 4f5faa3a; spec base `5e8ffed0`, tree-identical for all 36 manifest files). Manifest files changed (3 of 36): `lpbf_defect_diagnostics.py`, `lpbf_peak.py`, `lpbf_simulation.py`.

The allowlist was derived key by key from a full check of this tree (all 97 diff keys, not the printed list). Reference cases G1/G2/G4 have no numeric drift; G1 only changes text and digests.

## Causes

| id | cause | source | files |
|---|---|---|---|
| LG-1 | LA-6: `crossSectionArea_um2` was the largest global-x plane. It is now the largest scan-normal slab (cells binned by along-scan coordinate into slabs one projected cell wide; slab cell volume over slab thickness). Bit-equal at 0/90/180 degrees. G3 stripe multilayer peaks on layer 2 at 102 degrees: 6400 -> 2698.01 um2 (pi/4*W*D of the reported W/D is 2720). Synthetic ellipsoid W 100 / D 50 / L 400 um: ratio to pi/4*W*D within 1.02-1.06 at dx = 10 um for 0, 35, 45, 67, 90, 102 degrees (old rule 1.02-3.97); 0.81-1.44 at dx = 40 um (voxelisation, present at 0 degrees too). | spec `SPEC_bump_LA6_gusarov.md` section 1.1 | `lpbf_peak.py` |
| LG-2 | The `assumptions` cross-section sentence no longer says the section is not scan-normal. | LG-1 | `lpbf_simulation.py` |
| LG-3 | Balling `sources` / `basis` / Moderate `reason` attribution: pi*sqrt(3/2) is Yadroitsev et al. 2010 Eq. (13) (cylinder diameter D, wavelength L); the mechanism (Plateau-Rayleigh break-up when length exceeds circumference, substrate contact stabilises) is Gusarov, Yadroitsev, Bertrand & Smurov 2007 sec. 3-4. Gusarov & Smurov 2010 (Phys. Procedia 5:381) was never read and is dropped from exported text, including the `defect_diagnostics()` provenance title (now "Yadroitsev et al. (2010) Eq. 13; Gusarov et al. (2007); Hofmann et al. 316L tracks (Zenodo 16979848)"). Constants 3.847 / 5.5 and `eagar-tsai-aspect-balling-screen-v1` unchanged. | Gusarov et al. 2007 (10.1016/j.apsusc.2007.08.074, local `papers/`, not in the repo); Yadroitsev et al. 2010 (10.1016/j.jmatprotec.2010.05.010) | `lpbf_defect_diagnostics.py` |
| LG-4 | `geometricDefectScreen.modelId` `elliptic-overlap-screening-v1` -> `-v2` (balling block semantics changed at d92d1a3a while the id stayed v1). | d92d1a3a | `lpbf_defect_diagnostics.py` |

## Drift by case (raw before -> after)

| case / observation | before | after |
|---|---|---|
| g3 stripe multilayer `result.key.metrics` | `crossSectionArea_um2` 6399.999999999998 (all other metrics bit-equal) | 2698.0101440071016 |
| g1, g3 x3 (stripe, island, meander), g5, g6 x4, g7 x2, g8, g14 x2, g16 x3, g17 x3, g19: `*.key.assumptions` (22 slots) | cross-section sentence "...not scan-normal for rotated scans." | LG-2 sentence |
| the same 22 slots: `*.key.geometricDefectScreen` | `modelId` v1, balling sources/basis/reason (2010 attribution) | `modelId` v2, LG-3 text |
| the same 22 slots: `canonicalSha256` + `orderedTypedSha256` | G1 stripped `f9b41280...` | G1 stripped `e37e76ab...` (V1 re-binding mandatory) |
| g3 stripe multilayer `canonicalSha256` / `orderedTypedSha256` | follows `metrics` | follows `metrics` |
| g11 `meltpool.0/1/2` canonical + typed digests (6) | hash of thermal dicts with v1 text | hash with v2 text; geometry, peak temperature, regime unchanged |
| g18 `meltpool.in625` | digest of v1 text | digest of v2 text |

No thermal history, energy balance, field artefact, NPZ, midTrack, peakInterpolatedMeltPool, numericalDiagnostics, G12 or G13 observation drifts.

## Goldens

Not re-recorded in this commit; see the separate golden commit.

## Labels

Evidence labels unchanged: `experimentalValidation=false`, `validationStatus=unvalidated`, `productionReady=false`.
