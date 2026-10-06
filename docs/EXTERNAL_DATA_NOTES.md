# External data notes (2026-10-06)

Scope: public datasets approved for download by the maintainer. Nothing here is wired into a solver or the UI, and none of it is validation evidence by itself. Raw files are not tracked; `external-data-manifest.json` lists URL, licence, size and sha256, and `python/tools/fetch_external_data.py --verify` checks them.

## 1. NIST mds2-2923 (IN625/IN718 single-track cross-sections) - NOT DOWNLOADED

Status: failed. `data.nist.gov` returned HTTP 503 (a 1128 B maintenance page) for `/rmm/records/mds2-2923`, `/od/id/mds2-2923`, `/od/ds/mds2-2923/` and the two documentation files, on three attempts spaced about 60 s apart (plus earlier 503/504 results from 2026-10-05). The catalog.data.gov CKAN API returned 404 for the dataset id; the HTML mirror page loaded but only lists resources that point back to `data.nist.gov`, so it gives no data. No file of this set was obtained.

What is known only from the mirror page (not from the README): 444 resources, mostly TIFF/JPEG micrographs (IN625 plates 3, 4, 8, 9, 10 and a spot-size series; IN718 sets 20210323_M290 and 20210713_AMB_X), plus `ReadMe` and `Master_TrackList_Measurements.xlsx`, which the dataset asks users to read first and which holds the melt-pool depth and width. The licence is not stated on the mirror page.

Units of every column: UNKNOWN, not read. Do not assume mm or micrometre. When the site is back, read the README and the header and unit rows of `Master_TrackList_Measurements.xlsx`, and record for each column: quantity, unit, depth and width definition (from the surface? total or remelted depth?), power and speed units, and what the "_m" image suffix means. Skip the images if the total is above 300 MB (444 resources) and only list them.

## 2. NIST mds2-2525 (Ti-6Al-4V absorptance and X-ray) - NOT DOWNLOADED

Status: failed (same 503 maintenance page for `/rmm/records/mds2-2525` and `/od/ds/mds2-2525/...`). The earlier files in the local `external-data/nist-mds2-2525` folder are 16-byte error stubs ("error code: 504"), not data; they must not be used. File names known from earlier attempts: `2525_README_v200.txt`, `Absorption_Uncertainty_Analysis.pdf`, `Scan on Bare Metal_Calibrated Absorption Data.csv`, `Spot on Bare Metal_Calibrated Absorption Data.csv`, `Beam Profile_5p5micron pixels_Normalized Integral.csv`. Column units: UNKNOWN, not read.

## 3. Zenodo 22901717 - CALPHAD solidification properties of 555 superalloys - downloaded

- File `Superalloys.xlsx`, 573,341 bytes, sha256 `03ca2aa992c8f66b96f5596c5652c67a99c9f66a90d333d7e0c1ca6950b2d90a` (md5 matches the Zenodo record).
- Licence CC BY 4.0. Creators: M. Younes Araghi, S. Xu (University of Oklahoma). Values were computed with Thermo-Calc 2024a / TCNI12 (a commercial database), so they are calculated, not measured. The record accompanies a paper submitted to MRS Communications.
- One sheet, 555 data rows, 50 columns (the last four are empty). Observed from the header and the first row; the file documents no units except where a header says so:
  - `Solidus Temp (∘C)`, `Liquidus Temp (∘C)`: degrees Celsius (stated in the header). `Freezing Range` equals their difference (79 for 1574 and 1653). `Gamma prime solvus temp` and `Processing Window` have no unit in the header; the magnitudes (875, 699) are consistent with degrees Celsius but this is unconfirmed.
  - `CSC (Easton)`, `CSC (Kou)`, `CSC (C&D)`: crack susceptibility coefficients, no unit given; the three are on different scales (about 149, 673 and 0.54 for the first row).
  - Element columns (Al ... Zr, Cu, Mn): mass fractions that sum to 1 (`Composition_sum`), not percent, although the record text says weight percent. The `chemical_composition` string uses wt% numbers (for example Cr18.6). Check both before use.
  - `Calculated_Density_g_cm3` is g/cm3, `Avg_Density` looks like kg/m3 (8977.8), `Estimated_Cost_USD_kg` is USD per kg, `Avg_Melting_T` is probably K (1673), `H_mix` and `S_mix` carry no unit. `Refeence` (sic) holds a DOI; `Family` is Ni-, Co- or Fe-based.
- Caveats: one thermodynamic database and one solver produced every value; the file has no experimental comparison; the alloy compositions may be nominal. Do not label it Measured.

## 4. MatCalc open databases (mc_fe, mc_ni, mc_al) - downloaded

Originals are in `external-data/matcalc` and recorded in `external-data-manifest.json`: `mc_fe_v2062.tdb` 489,296 B, `mc_ni_v2036.tdb` 416,720 B, `mc_al_v2037.tdb` 308,711 B (sha256 values in the manifest; they match the 2026-10-05 compatibility review). Licence: ODbL 1.0 for the database, DbCL 1.0 for the contents. A repaired copy is an altered derivative database, so ODbL share-alike and attribution apply to it. Keep the original untouched, never commit the TDBs, and review with legal counsel before shipping any of them.

### Syntactic repair (`python/tools/tdb_repair.py`)

pycalphad 0.11.2 cannot read the originals. The tool writes a repaired copy under `external-data/repaired/` (never editing the original) and a JSON report listing every change. Counts from the last run:

| Rule | mc_ni | mc_fe | mc_al | What it does |
|---|---:|---:|---:|---|
| drop-directive | 11 | 14 | 5 | comments out REFERENCE_ELEMENT, ATTACH_CONTRIBUTION, ADD_COMPOSITION_SET |
| drop-matcalc-parameter | 13 | 21 | 8 | comments out MatCalc-only PARAMETER HMVA (and SE in mc_al); these are not G, L, TC or BMAGN |
| fix-temperature-limit | 2 | 2 | 0 | `6000.00.00` becomes `6000.00` |
| semicolon-to-comma | 0 | 1 | 0 | `G(PH;C;0)` becomes `G(PH,C;0)` |
| insert-missing-terminator | 0 | 1 | 0 | adds a missing `!` |
| comment-out-bibliography | 1 | 1 | 1 | reference free text after the last statement |
| ref-tag-space / ref-tag-blank | 0 | 4 | 4 | `REF: x` and `REF:a b` citation tags |
| constituent-trailing-junk | 0 | 1 | 0 | `: > >> 1` after a constituent line |
| ambiguous-stray-number / ambiguous-duplicate-range-tail | 0 | 2 / 2 | 0 | only with `--allow-ambiguous` |

Retained parameters: 3586 (mc_ni), 4093 (mc_fe), 2036 (mc_al). Each retained parameter statement is compared before and after in canonical form (whitespace removed, the declared rewrites undone, citation tag ignored); any difference aborts the run.

The ambiguous case is two mc_fe PDMN_B2 parameters written `273.00 273 +46000-23*T ... ; 6000.00 N ; 6000.00 N`. The file does not settle whether the extra `273` is a duplicated temperature (dropped by the tool) or part of the expression (+273 J/mol). By default the tool refuses; `--allow-ambiguous` was used for mc_fe and both assumptions are listed in the report. The possible effect is 273 J/mol on two parameters of one phase.

### What the repair does not preserve

- `ATTACH_CONTRIBUTION BCC_B2 BCC_A2 ORDER_DISORDER` (and `GP_MAT FCC_A1` in mc_al) is dropped, so those ordered phases are described without the attached disordered-part contribution. Equilibria involving BCC_B2 or GP_MAT are not the MatCalc model and must not be used.
- HMVA and SE (vacancy formation enthalpy and similar kinetic extras) and the composition-set hints are lost. They do not enter an equilibrium calculation in pycalphad, but MatCalc kinetics would need them.
- pycalphad warns that the type-definition character `%` appears in many phases of the repaired mc_ni without a matching TYPE_DEFINITION line; its effect was not analysed.

A successful load or an equilibrium is not validation. The small runs in the handoff only show that the repaired files calculate and return plausible phases.
