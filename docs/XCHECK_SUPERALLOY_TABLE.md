# Cross-check: liquidus / solidus against the Zenodo 22901717 superalloy table (2026-10-06)

Evidence label: **Screening only**. This is a comparison of one computed result against another computed result. It cannot upgrade any label to Validated simulation or Calibrated simulation, and it changes no solver, golden file, fingerprint or ceiling.

## What is compared

| | Reference (the table) | Ours |
|---|---|---|
| Source | Zenodo record 22901717, `Superalloys.xlsx` (CC BY 4.0, M. Younes Araghi and S. Xu, University of Oklahoma), sha256 `03ca2aa9...c2d90a` | pycalphad 0.11.2 on the repaired MatCalc `mc_ni` database (`.orchestra/external-data/repaired/mc_ni_repaired.tdb`) |
| Kind | Thermo-Calc / TCNI12 calculation (per the record, not re-verified here). Not a measurement | CALPHAD calculation with a different assessment (MatCalc open database, ODbL) plus a syntactic repair |
| Solver | Thermo-Calc | pycalphad `equilibrium`, project `calphad_solver.scheil_gulliver` for the Scheil path |

Both sides are calculations. Agreement would show that two assessments agree, not that either matches a real alloy. Disagreement points at an assessment, composition or definition difference, not at a measured error.

## Verified facts about the table (read with pandas/openpyxl, 555 rows x 50 columns, one sheet)

- Columns used: `Alloy`, `Family`, `Solidus Temp (∘C)`, `Liquidus Temp (∘C)`, `Freezing Range`, and 20 element columns (Al B C Co Cr Fe Hf Mo Nb Ni Re Ru Si Ta Ti V W Zr Cu Mn).
- Composition basis: the element columns are **mass fractions** (not percent). For every row they sum to 1.0 (min and max of the row sums are both 1.0). Row 0 string `Cr18.6 Co17.6 ... Ni52.377` matches Cr 0.186, Co 0.176, Ni 0.52377, so the string is in wt%. Our script multiplies by 100 and passes `wt_pct` to `normalize_composition`.
- Compositions are nominal and often balanced to 100 by Ni. Row `IN718` has Fe 0 and Ni 71.48 (no Fe, B 0.02), a different material from row `Inconel 718` (Fe 18.5, Ni 52.96, C 0.04). 37 alloy names repeat in the table.
- **Unit finding (important, inferred, not confirmed by the authors).** The headers say degrees Celsius, but the temperatures are not consistent with that for most named alloys. 165 of the 211 Ni-based rows have a liquidus above 1455 (the melting point of pure Ni in deg C), which is impossible for a Ni-based alloy in deg C. Read as kelvin the named alloys land in the expected range (Inconel 625: 1613 K = 1340 deg C; Inconel 600: 1693 K = 1420 deg C). The first roughly 190 rows look like kelvin; the later rows (numbered alloys, FBB series, Co-based) look like deg C (for example liquidus 1394 / 1219 for `Alloy4`, 1482 / 1450 for `FBB-1`). Since the file documents no per-row unit, the split is a plausibility argument only. The comparison below subtracts 273.15 from the table values of the 18 named alloys. If the numbers are instead read as printed (deg C) the mean bias is about -281 K on the liquidus and -269 K on the solidus, which is physically implausible, so that reading is rejected, but it remains an assumption. The table `Processing Window` (= solidus minus gamma-prime solvus, 1574 - 875 = 699 for row 0) mixes the two readings, which supports the unit mix. Someone should ask the record authors.
- The table does not say how its solidus is defined (equilibrium, or Scheil terminal, or a liquid-fraction threshold). The freezing range equals liquidus minus solidus.

## Method (`python/tools/xcheck_superalloy_table.py`, analysis only)

1. Read the row, take the 20 mass-fraction columns, call `calphad_solver.normalize_composition(..., "wt_pct")` (project atomic weights), build mole fractions. No other solver code is changed.
2. Phases: LIQUID, FCC_A1, BCC_A2, HCP_A3, GAMMA_PRIME, DELTA, SIGMA, MU_PHASE, LAVES, P_PHASE, R_PHASE, M23C6, M6C, M7C3, M3C2, ETA, borides (CRB, CR2B, CR5B3, M2B, MOB, MOB2, NBB, NB3B2, NB5B6, TIB, TIB2, TI3B4), NI5HF, NI7HF2, NITI2, NI2CR, G_PHASE, CHI_A12, DIAMOND_A4, GRAPHITE. **BCC_B2 and NIAL are excluded** because the repair drops the BCC_B2 order-disorder attachment (`docs/EXTERNAL_DATA_NOTES.md`); no ordered-phase result is used. An alloy that would form B2 near the solidus (high Al) would be misdescribed; the 18 alloys here are low in Al (at most 4 wt%), but whether B2 would have entered was not tested by a run that includes it.
3. Equilibrium liquidus = lowest temperature with liquid >= 99.9 %; solidus = lowest temperature with liquid > 0.1 % (same definitions as `derive_critical_temperatures`). Coarse 25 K grid (liquidus 1200 to 2000 deg C, solidus 1000 deg C up to the liquidus), then multi-section refinement to 0.5 K. Reported value is the middle of the final bracket.
4. Scheil: `scheil_gulliver` with a 5 K step, liquid below 0.1 % as the stop. Only runs that ended by "liquid below 0.1 %" or "liquid exhausted within step" are called complete. Terminal temperature is reported; incomplete runs are listed as incomplete, not as a solidus.
5. Interpreter: `C:/Users/can02/AppData/Local/Programs/Python/Python312/python.exe` with pycalphad 0.11.2 and pandas. It needs pycalphad, so it was not run on a pycalphad-free CPU interpreter; `--summarize` mode only needs the standard library.

## Which alloys could and could not be computed

- Of 555 rows, 287 contain only elements present in the repaired `mc_ni` (Al B C Co Cr Cu Fe Hf Mn Mo Nb Ni Si Ti V W Zr). **268 rows cannot be computed** because they contain Ta, Re or Ru, which `mc_ni` does not define (CM247LC, Mar-M246, Rene N5/N6, IN-738, IN792 and others). `mc_fe` has Ta but no Re/Ru and is an Fe database; `mc_al` is an Al database; neither is suitable for these Ni alloys and none was used.
- 18 named alloys were chosen from the computable set (well-known commercial Ni/Fe-Ni alloys). 17 were computed. **Rene 80 was not computed**: pycalphad returned non-converged points next to both boundaries, so no liquidus or solidus is reported. The Co-based rows were not attempted (MatCalc `mc_ni` is a Ni-base assessment; Co-base alloys would also need a Co-base check).
- The Inconel 625 row was computed in a separate solo run before a small script fix (the fix, adding the upper search end to the coarse grid, only matters for freezing ranges narrower than 25 K, and it changed Inconel 600). The same code was not re-run for 625; its range is wide enough that the fix cannot matter.

## Results (deg C; difference = ours minus table; table read as kelvin converted to deg C)

| Alloy | table liq | table sol | our liq (eq) | our sol (eq) | our Scheil end | d_liq (K) | d_sol (K) | d_Scheil vs table sol (K) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Inconel 718 | 1313 | 1210 | 1348 | 1252 | 1110 | +35 | +42 | -100 |
| IN718 (table row has no Fe) | 1344 | 1282 | 1359 | 1283 | 1161 | +15 | +1 | -121 |
| Inconel 625 | 1340 | 1262 | 1368 | 1308 | incomplete (equilibrium not converged, 4.2 % liquid left at 1170) | +28 | +46 | n/a |
| Inconel 600 | 1420 | 1418 | 1417 | 1413 | 1409 | -2 | -4 | -8 |
| Inconel 601 | 1402 | 1388 | 1396 | 1344 | 1328 | -6 | -44 | -60 |
| Inconel 617 | 1402 | 1394 | 1396 | 1344 | 1263 | -6 | -50 | -131 |
| Inconel 690 | 1400 | 1393 | 1395 | 1362 | 1307 | -5 | -30 | -86 |
| Inconel X750 | 1409 | 1392 | 1401 | 1383 | 1303 | -7 | -8 | -88 |
| Inconel 706 | 1355 | 1249 | 1383 | 1287 | 1130 | +28 | +38 | -119 |
| Waspaloy | 1388 | 1217 | 1367 | 1305 | 1314 | -21 | +89 | +97 |
| Hastelloy X | 1383 | 1308 | 1400 | 1359 | 1267 | +18 | +52 | -40 |
| Incoloy 800 | 1416 | 1395 | 1427 | 1378 | 1319 | +11 | -17 | -76 |
| Nimonic 80A | 1396 | 1376 | 1385 | 1362 | 1252 | -11 | -13 | -124 |
| Nimonic 90 | 1394 | 1373 | 1382 | 1358 | 1234 | -12 | -14 | -139 |
| Astroloy | 1385 | 1336 | 1347 | 1300 | 1059 | -38 | -36 | -277 |
| Rene 41 | 1350 | 1283 | 1333 | 1258 | incomplete (equilibrium not converged, 21 % liquid left at 1260) | -17 | -25 | n/a |
| Udimet 720 | 1365 | 1130 | 1214 | 1177 | 1176 | -151 | +47 | +46 |
| Rene 80 | 1274 | 1154 | not computed (non-converged points at both boundaries) | | | | | |

Raw numbers, brackets, statuses and compositions: `docs/XCHECK_SUPERALLOY_TABLE_RESULTS.json`.

### Statistics (n = 17 computed alloys, table read as kelvin)

| Quantity | n | mean bias (ours - table) | MAE | max abs error |
|---|---:|---:|---:|---:|
| Equilibrium liquidus | 17 | -8.3 K | 24.2 K | 150.8 K (Udimet 720) |
| Equilibrium solidus | 17 | +4.3 K | 32.7 K | 88.6 K (Waspaloy) |
| Scheil end vs table solidus (informational) | 15 | -81.8 K | 100.8 K | 276.8 K (Astroloy) |

Without the Udimet 720 outlier, n = 16: liquidus mean bias +0.6 K, MAE 16.3 K; solidus mean bias +1.6 K, MAE 31.8 K. These are descriptive numbers for 17 hand-picked alloys, not an uncertainty estimate.

## Reading the result

- Equilibrium liquidus agrees with the table within about 40 K for 16 of 17 alloys; the solidus within about 50 K for 15 of 17, with a few larger gaps (Waspaloy +89 K, Inconel 625 +46 K, Hastelloy X +52 K). The sign of the differences is mixed, so there is no systematic offset, but the scatter is tens of K, larger than a "same thermodynamics" agreement would give. It is consistent with two different assessments, composition differences (the table compositions are nominal and Ni-balanced), and different definitions of the solidus.
- Udimet 720: our liquidus 1214 deg C is 151 K below the table and below any plausible value for a Ni-base alloy with 55 % Ni, so this is most likely a limitation of the repaired `mc_ni` (Ti 5 wt%, B, Zr) or of the phase list, not a property of the alloy. It was not diagnosed. Rene 80 (Ti 5 wt%, B) failed to converge, which points the same way: treat Ti and B rich alloys with this database as unreliable.
- Inconel 718 and 625: ours are higher than the table by 28 to 46 K on both boundaries. The two table rows for IN718 differ in composition by 35 K in liquidus, a reminder that the reference depends on the entered composition.
- The Scheil column is not a like-for-like comparison: the table does not say whether its solidus is an equilibrium or a Scheil quantity. Our Scheil end is far below the equilibrium solidus for Nb/Ti/Al-bearing alloys (up to 277 K), which is expected qualitatively for Scheil with segregation, and the Scheil path is capped by the 5 K step and by `equilibrium-not-converged` stops (two alloys). For Waspaloy and Udimet 720 the Scheil end sits above the equilibrium solidus by a few to 9 K (step size and the 0.1 % definition; not analysed further).
- The table is not a measurement. A close match to TCNI12 does not show closeness to a real alloy; a mismatch does not show our database is wrong.

## What this changes in the project

Nothing. No label, status, golden, fingerprint, ceiling, STATUS.md or PROOF.md was touched. The existing wording for CALPHAD output (calculated with a named database, not validated against experiment) stays. If this is cited, cite it as "cross-check against a Thermo-Calc/TCNI12 table, Screening only".

## Not verified

- The record's own statements (TCNI12, Thermo-Calc 2024a) are taken from the record text and the existing data notes, not independently checked.
- The kelvin-versus-Celsius split of the table is inferred from plausibility, not confirmed.
- No experimental data was used.
- `mc_ni` phases were not inspected for each alloy (which phase forms at the solidus); only the temperatures are reported.
- Co-based rows (306), alloys with Ta/Re/Ru (268 rows) and the other ~270 computable rows were not run.

## Reproduce

From `python/`:

```
set PYTHONDONTWRITEBYTECODE=1
C:/Users/can02/AppData/Local/Programs/Python/Python312/python.exe -B tools/xcheck_superalloy_table.py \
  --xlsx <path>/zenodo-22901717/Superalloys.xlsx --tdb <path>/repaired/mc_ni_repaired.tdb \
  --out result.json --alloys "Inconel 718,Inconel 600" --scheil-step 5
C:/Users/can02/AppData/Local/Programs/Python/Python312/python.exe -B tools/xcheck_superalloy_table.py \
  --summarize ../docs/XCHECK_SUPERALLOY_TABLE_RESULTS.json
```

Run one alloy per process for long lists: pycalphad Workspaces were not released between alloys and a batch of 9 alloys grew to several GB. A single alloy takes from about 1.5 minutes to over 30 minutes on a loaded machine.
