# LPBF Scheil / Laves cross-check (2026-10-07)

Local analysis run of `python/tools/xcheck_scheil_laves.py`. Both columns are calculations; neither is a measurement and neither is validated for LPBF. The TDB is not part of the repository.

## Step 0: database decision (recorded before modelling)

- `calphad_solver.OPEN_TDB_CATALOG` holds no usable Ni-Cr-Fe-Nb-Mo assessment and `system_coverage()` reports
  IN718 and IN625 as not covered. `mc_fecocrnbti.tdb` is a refused test fixture.
- The only open candidate is MatCalc `mc_ni` v2.036 (ODbL 1.0 / DbCL 1.0, has LAVES), held outside git under
  `.orchestra/external-data/` with a syntactic repair. `docs/EXTERNAL_DATA_NOTES.md` section 4: never commit the TDBs,
  review with legal counsel before shipping (the repaired copy is a derivative under ODbL share-alike).
- `docs/XCHECK_SUPERALLOY_TABLE.md`: its Scheil path completes for IN718 but is incomplete for IN625 (equilibrium not
  converged, 4.2 % liquid left at 1170 degC).
- Decision: the shipped path is the published closed-form model (`python/lpbf_solidification_segregation.py`,
  DuPont, Robino & Marder 1997, SAND97-1669C, Literature estimate (screening)). pycalphad Scheil on `mc_ni` is this
  optional local cross-check only: never a default path, never in CI, never in the app. `mc_ni` was not added to the
  catalogue and `calphad_solver.py` was not edited.

## Run

- TDB: `mc_ni_repaired.tdb` (sha256 `c914f534cc99...`), pycalphad 0.11.2
- Literature side: `lpbf_solidification_segregation` (DuPont, Robino & Marder 1997, Literature estimate (screening)); fractions of the liquid, mass basis; C = 0 is the binary upper bound, C = 0.08 the pseudo-ternary model at the specification maximum.
- pycalphad side: `calphad_solver.scheil_gulliver`; phase amounts in moles of atoms. Indicative comparison only.
- IN718 composition: midpoints of SMC-045 Table 1 for Ni, Cr, Nb, Mo, Ti, Al, Fe balance; minor max-only elements left out: Co, Mn, Si, P, S, B, Cu.

| Case | Literature f_Laves | pycalphad Scheil status | LAVES (mol atoms) | Other solids (mol atoms) | Terminal T (degC) | Remaining liquid |
|---|---|---|---|---|---|---|
| IN718 midpoint, C=0.0 | 0.0615 | complete | 0.01935 | DELTA 0.010412, ETA 0.023378, FCC_A1 0.94686 | 1127.85 | 0.0 |
| IN718 midpoint, C=0.08 | 0.0264 | complete | none formed | DELTA 0.038886, ETA 0.0212, FCC_A1 0.93701, SIGMA 0.002903 | 1103.83 | 0.0 |

IN625 was not run: the repository holds no cited IN625 composition limits and its literature constants are not verified (the segregation block reports IN625 as unavailable).

Incomplete or non-converged paths are reported as they stopped; nothing is extrapolated.
