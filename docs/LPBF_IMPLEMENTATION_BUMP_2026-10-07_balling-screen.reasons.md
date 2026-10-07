# Balling-screen bump — drift reasons (f3ba9896… → d92d1a3a…)

Companion to `LPBF_IMPLEMENTATION_BUMP_2026-10-07_balling-screen.json`, the tool output of

`python -B tools/lpbf_bump_record.py --from-revision 8efabc62 --with-parity-check --slow --expect-drift <the 66 entries of ….expect-drift.txt>`

run at the re-pin commit `2a0eb47a` (python tree clean, `worktreeDirty: false`) in the locked warp-less reference interpreter `.runtime/lpbf-win-py312` (CPython 3.12.10, NumPy 2.2.6, no `warp`). Result: **14 DRIFT, 11 PASS, 0 FAIL**; `pinMatchesToHash: true`, `versionUnchanged: true` (`enthalpy-fv-6`). Base: `feat/lpbf-physics-bump-wave-b` at `8efabc62` (pin `f3ba9896…`), itself on main `f84ccb39`. Manifest files changed (3 of 36): `lpbf_defect_diagnostics.py`, `lpbf_simulation.py`, `lpbf_thermal_solver.py`.

The allowlist was derived key by key from a full check of this tree (all diff keys, not the 40-line printed list) and contains only exact keys; no reference-case numerics, honesty or identity observation is in it.

## Cause (one finding)

| id | cause | source | files |
|---|---|---|---|
| BAL-1 | The frozen balling flag (steady-Rosenthal L/W > 3.8 → "High", > π → "Moderate"), the transient path's `length > π·W` mainRisk, the geometric screen's L/W > 1.2π / > π bands and the process-map grid's `(1.6 + 0.55·min(6, Pe)) > 3.8` (= Pe > 4) rule are replaced by ONE screen `lpbf_defect_diagnostics.balling_screen` on the **Eagar–Tsai** liquidus L/W: High > 5.5 (empirical, Hofmann 316L, in-sample, re-calibrated on the Wave B geometry) → risky; Moderate > π√(3/2) = 3.85 → advisory; ET extent not computed → no band. Where no ET L/W exists (transient reference path, quick process-map grid, a bare `defect_diagnostics()` call) no balling band is assigned. | Gusarov & Smurov 2010 (10.1016/j.phpro.2010.08.065); Yadroitsev et al. 2010 (10.1016/j.jmatprotec.2010.05.010); Hofmann et al., Zenodo 10.5281/zenodo.16979848; calibration table `docs/LPBF_BALLING_CALIBRATION_2026-10-07.md` | `lpbf_defect_diagnostics.py`, `lpbf_thermal_solver.py`, `lpbf_simulation.py` |

The thermal solver's liquidus extent search was moved verbatim into `_liquidus_extent` so the Eagar–Tsai companion runs the identical search on a fresh field. Every non-balling output of `calculate_meltpool_physics` is bit-equal to `8efabc62` on 288 cases (4 alloys × 4 P × 3 v × 2 spots × 3 kernels), and the companion equals an `eagar-tsai` run on 72 cases (0 mismatches).

## Drift by case (raw before → after)

| case / observation | before | after |
|---|---|---|
| g1 `result.key.geometricDefectScreen` (V1 60 W IN718, transient) | balling L/W 1.75, risk `low` ("< π … stable") | L/W 1.75, risk `null` ("No balling risk from this geometry: … Eagar-Tsai liquidus L/W … not supplied") |
| g1 `result.canonicalSha256` / `orderedTypedSha256` | stripped `ff428b93…` | `f9b41280…` (only `geometricDefectScreen.balling` differs) |
| g5 evaporation `geometricDefectScreen` | L/W 5.00, risk `high` | risk `null` |
| g6 `screening` / `highFidelityFallback` / `…WithOpenfoam` `geometricDefectScreen` | L/W 5.77, risk `high` | risk `null` |
| g6 `screeningTi64` `geometricDefectScreen` | L/W 7.20, risk `high` | risk `null` |
| g6 ×4 `mainRisk` | `balling (screening)` | `not established` |
| g7 mesh / timestep `geometricDefectScreen` | L/W null, reason "Elongation alone cannot resolve…" | reason text only (risk null both) |
| g14 matched / unmatched `geometricDefectScreen` | L/W 3.00, risk `low` | risk `null` |
| g16 alsi10mg / ss316l / ti6al4v `geometricDefectScreen` | L/W 1.00 / 3.00 / 4.00, risk `low` / `low` / `high` | risk `null` ×3 |
| g17 ti6al4v / 316l / alsi10mg `geometricDefectScreen` | L/W 1.67 / 5.00 / 1.20, risk `low` / `high` / `low` | risk `null` ×3 |
| g19 implicit `geometricDefectScreen` | L/W 3.00, risk `low` | risk `null` |
| g8 observers `result.key.geometricDefectScreen` (+ `plain.canonicalSha256`) | L/W 1.00, risk `low` | risk `null` |
| g11 `meltpool.0` IN718 200/800/80 Rosenthal | `ballingInstabilityRisk` High (Rosenthal L/W 5.20); grid 39 balling cells | Moderate (ET L/W 3.97); `ballingScreen`; geometric screen `moderate`; grid 0 balling cells, `ballingNote` |
| g11 `meltpool.1` Ti64 280/1200/70 ET | High (ET L/W 5.47 via the old > 3.8 rule) ; grid 42 | Moderate (ET L/W 5.47) ; grid 0 |
| g11 `meltpool.2` 316L 370/600/60 Goldak | High (Goldak L/W 4.33); grid 39 | Moderate (ET L/W 4.28); grid 0 |
| g18 `meltpool.in625` IN625 200/800/80 Rosenthal | High (Rosenthal L/W 5.43); grid 40 | Moderate (ET L/W 4.04); grid 0 |

In every transient case the 22 matching `rawValues` entries changed with their keys and nothing else; metrics, `numericalDiagnostics`, thermal history, energy balance, artifacts, NPZ and identity digests are bit-equal (G2/G3/G4/G13/G15/npz PASS). The G11 geometry (`[154.9, 110.4, 804.9, 35.2]`) and peak values are unchanged.

## Goldens

Re-recorded in a separate commit (`--record --force --twice --slow`, locked interpreter, 25 cases twice). Against the f3ba9896 goldens exactly the 66 allowlisted observations and 22 matching `rawValues` changed (checked key by key); every other golden changed only `recordedGitHead` / `recordedImplementationHash` / `recordedRuns_s`.

## Labels

Evidence labels unchanged: `experimentalValidation=false`, `validationStatus=unvalidated`, `productionReady=false`. The High threshold is an in-sample 316L screen; no balling prediction for IN718/Ti-6Al-4V is claimed.
