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
- The two columns are not directly comparable: the literature column is the gamma/Laves eutectic-type constituent (fraction of the liquid, eutectic gamma included), the LAVES column is the amount of the LAVES phase alone, so the constituent is necessarily larger than the phase amount for the same path.
- IN718 composition: midpoints of SMC-045 Table 1 for Ni, Cr, Nb, Mo, Ti, Al, Fe balance; minor max-only elements left out: Co, Mn, Si, P, S, B, Cu.

| Case | Literature gamma/Laves constituent (fraction of liquid) | pycalphad Scheil status | LAVES (mol atoms) | Other solids (mol atoms) | Terminal T (degC) | Remaining liquid |
|---|---|---|---|---|---|---|
| IN718 midpoint, C=0.0 | 0.0615 | complete | 0.01935 | DELTA 0.010412, ETA 0.023378, FCC_A1 0.94686 | 1127.85 | 0.0 |
| IN718 midpoint, C=0.08 | 0.0264 | complete | none formed | DELTA 0.038886, ETA 0.0212, FCC_A1 0.93701, SIGMA 0.002903 | 1103.83 | 0.0 |

No MC carbide formed in the pycalphad path for: IN718 midpoint, C=0.08. The pseudo-ternary model removes Nb into gamma/NbC at that carbon level, so the comparison in that row is doubtful.

IN625 was not run through this pycalphad cross-check (see the IN625 section below for the literature estimate).

Incomplete or non-converged paths are reported as they stopped; nothing is extrapolated.

## IN625: literature estimate (Cieslak 1988 + DuPont 1996), added after W4

The segregation block now reports IN625 as `available` with a separate, smaller model (`modelId`
`cieslak1988-dupont1996-binary-gamma-nb-scheil-v1`, constant set `in625-c88`). The IN718 path and output are
unchanged (sha256 pin in `test_lpbf_solidification_segregation`). Both papers were read in full from
maintainer-supplied PDFs, which are not in the repository.

- Primary source, low-Fe alloy 625: M.J. Cieslak, T.J. Headley, T. Kollie, A.D. Romig Jr., "A melting and
  solidification study of alloy 625", Metall. Trans. A 19A (1988) 2319-2331 (C88). Factorial Nb/C/Si heats, Fe
  about 2.3 wt%, Nb 3.53-3.61 wt% in alloys 5-8 (Table I); GTA welds and DTA.
  - k_Nb = 0.51: the lowest of the EPMA dendrite-core values in Table VIII (0.53, 0.51, 0.52, 0.51 for alloys 5-8).
    Table VII gives 0.54 from the liquidus/solidus slopes (also shown).
  - Measured minor constituent in the rapid-scan DTA specimens, Section III-B: 0.3, 0.7, 1.3 and 0.9 vol% for
    alloys 5-8 (constituents not separated).
  - Phases (Tables IV and IX): 0.038 wt% C without added Si gave gamma/NbC only (alloy 6); low C, low Si gave a small
    amount of mostly Laves (alloy 5); Si promoted Laves and, at low C, M6C.
  - C88 gives no eutectic composition.
- Second source: J.N. DuPont, "Solidification of an Alloy 625 Weld Overlay", Metall. Mater. Trans. A 27A (1996)
  3612-3620 (D96). One GMAW overlay on 2.25Cr-1Mo steel, about 25-28 % dilution, 28.14 wt% Fe (Table II).
  - C_e = 18.9 wt% Nb: Section IV-C, text after Eq. 5. The paper builds it from the Alloy 718 gamma composition in
    the gamma/Laves eutectic (9.3 wt% Nb, Table V, its ref. 19) and the overlay Laves (22.1 wt% Nb, Table III) at
    75 vol% Laves. The low-Fe Laves of C88 holds less Nb (16.8-19.2 wt%, C88 Table V), so C_e for IN625 may be
    lower, which would raise the fraction.
  - k_Nb = 0.46 (Table IV): shown as a cross-check only.
  - Model: Eq. 5, f_e = (C_e / C_0)^(1/(k-1)), binary gamma-Nb Scheil. Neither source gives carbon constants, so no
    pseudo-ternary (gamma/NbC) path is applied for IN625.
  - Paper's own check, reproduced in the unit test: C_0 2.07, k 0.46, C_e 18.9 gives f_e = 0.0166 (paper 1.7 vol%;
    tolerance 0.0005), against 1.3-2.2 vol% gamma + Laves measured.
- Composition authority, read: Special Metals INCONEL alloy 625 technical bulletin (copyright 2013), Table 1:
  Nb (plus Ta) 3.15-4.15, Fe 5.0 max, C 0.10 max, Si 0.50 max, Mo 8.0-10.0, Cr 20.0-23.0, Ni 58.0 min (wt%).

Constituent fraction at C = 0 (fraction of liquid), C_e = 18.9 wt% Nb:

| Nb (wt%) | k 0.51 (C88 Table VIII, used) | k 0.54 (C88 Table VII) | k 0.46 (D96 overlay) |
|---|---|---|---|
| 3.15 (spec min) | 0.0258 | 0.0203 | 0.0362 |
| 3.65 (midpoint) | 0.0349 | 0.0280 | 0.0476 |
| 4.15 (spec max) | 0.0453 | 0.0370 | 0.0604 |

Comparison with C88 (not a calibration target): each alloy's own k and C_e 18.9 give 2.9-3.4 % against 0.3-1.3 vol%
measured, 2.4-9.8 times high in every alloy. D96's overlay check agrees (1.66 % vs 1.3-2.2 vol%), so the model and
C_e fit the Fe-rich overlay but over-predict low-Fe alloy 625.

Limits stated in the block (`validity`, `phaseIdentityNote`):

- The IN625 specification extends outside the C88 range in Nb (3.15-4.15 vs 3.53-3.61), C (0.10 vs 0.008-0.038),
  Fe (5.0 vs about 2.3), Si, Cr, Mo, Ti and Mn; k is assumed constant over the band.
- Phase identity (Laves or NbC) is not established; it depends on C and Si (C88) and on Fe (D96). No Laves risk class
  is given for IN625.
- Upper bound only with respect to back-diffusion, solute trapping, tip undercooling and carbon; not with respect to
  k or C_e, and not a bound on measurement. `outsideSourceRegime` is true (LPBF is not a source process).
- IN625 is not a build-job alloy (`resolve_alloy_id` refuses it), so no build-job output changed and
  `BUILD_JOB_SOLVER_REVISION` stays v14.

## DuPont, Robino & Marder 1998 vs the D97 constants used for IN718 (report only, IN718 not changed)

J.N. DuPont, C.V. Robino, A.R. Marder, Acta Mater. 46 (1998) 4781-4790 (DOI 10.1016/S1359-6454(98)00123-2), read in
full. Its Table 2 differs from the D97 Table 3 values the IN718 path uses:

| Quantity | D97 Ni base (used) | D98 Ni base | D97 Fe base | D98 Fe base |
|---|---|---|---|---|
| k_gamma,Nb | 0.46 | 0.45 | 0.25 | 0.25 |
| k_gamma,C | 0.27 | 0.21 | 0.27 | 0.21 |
| a (wt% C) | 0.98 | 1.13 | 1.24 | 1.37 |
| b (wt% C / wt% Nb) | -0.04 | -0.047 | -0.06 | -0.065 |
| C_Nb, L->(gamma+Laves) (wt% Nb) | 23.1 | 23.1 | 20.4 | 20.4 |
| C_C, L->(gamma+Laves) (wt% C) | 0.03 | 0.04 | 0.03 | 0.04 |
| C_NbC,Nb / C_NbC,C (wt%) | 90.5 / 9.5 | 90.5 / 9.5 | 90.5 / 9.5 | 90.5 / 9.5 |

Effect on the IN718 band if the D98 Ni-base set were used (computed offline, not shipped): binary C = 0 fraction
0.0534 / 0.0615 / 0.0701 becomes 0.0564 / 0.0647 / 0.0736 (Nb 4.75 / 5.125 / 5.50); gamma/Laves at C 0.08 becomes
0.0198 / 0.0282 / 0.0372 instead of 0.0181 / 0.0264 / 0.0352. Whether to move IN718 to the journal values is the
maintainer's decision; nothing was changed.
