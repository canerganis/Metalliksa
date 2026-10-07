# MatCalc open thermodynamic databases (mc_ni, mc_fe): licence, source and changes

The files `mc_ni_v2036_repaired.tdb` and `mc_fe_v2062_repaired.tdb` in this directory are **derivative
databases** of the MatCalc open thermodynamic databases. They are released under the same licence as
the originals:

- the database: **Open Database License (ODbL) v1.0**, http://opendatacommons.org/licenses/odbl/1.0/
- the individual contents: **Database Contents License (DbCL) v1.0**, http://opendatacommons.org/licenses/dbcl/1.0/

This licence covers only these two TDB files and their repair reports. It does not cover the rest of the
repository.

## Attribution

MatCalc open databases, (c) Erwin Povoden-Karadeniz, TU Wien (copyright holder and editor named in the file
headers; mc_fe update by E. Povoden-Karadeniz and A. Jacob). Source: MatCalc, "Open databases",
https://www.matcalc.at/index.php/databases/open-databases . Each file keeps the original header, licence
notice and reference list (commented out only where pycalphad cannot parse the bibliography text).

## Originals

| File | Release (download page / file header) | URL | Size (bytes) | sha256 |
|---|---|---|---:|---|
| `mc_ni_v2036.tdb` | 2.036, 2024-08-24 on the page; header "mc_ni_v2.036.tdb, updated 20.08.2024" | https://www.matcalc.at/images/stories/Download/Database/mc_ni_v2036.tdb | 416,720 | `84ba813156e1f7d8bde495d74420319afec03572b981f6b56103807f305313ab` |
| `mc_fe_v2062.tdb` | 2.062, 2024-11-08 | https://www.matcalc.at/images/stories/Download/Database/mc_fe_v2062.tdb | 489,296 | `aa02077eac3f602dd7479cbeafb09b450e282716752b3ae2b1fc3a57d9c64865` |

Retrieved 2026-10-07 (direct download, no registration, no payment, no terms beyond ODbL/DbCL); the hashes
equal those recorded on 2026-10-05 in `external-data-manifest.json`. The download page lists these as the
latest open releases (mc_ni 2.036, mc_fe 2.062) and states the ODbL/DbCL licensing. The mc_ni 2.036 header
licence sentence names the file "mc_ni_v2.035.tdb" (a stale name in the original header; the version line
reads 2.036). The originals are not committed; they are fetched by `python/tools/fetch_external_data.py`.

## Derivative files and changes (ODbL 4.6: the altered database is offered here; the method is below)

| File | Size (bytes) | sha256 |
|---|---:|---|
| `mc_ni_v2036_repaired.tdb` | 424,658 | `c914f534cc99f5fc2f7aab0373cfe5bc720bd2b85b545027d35ac4e0bcc6f94d` |
| `mc_fe_v2062_repaired.tdb` | 499,133 | `cb0a7f9f747b9b16bc8bb5085250f9449091e0031480e3d7527eb0ad1e1f3fd4` |

Produced (byte for byte reproducible) by the repository tool `python/tools/tdb_repair.py`:

    python python/tools/tdb_repair.py mc_ni_v2036.tdb mc_ni_v2036_repaired.tdb --report mc_ni_v2036_repair_report.json
    python python/tools/tdb_repair.py mc_fe_v2062.tdb mc_fe_v2062_repaired.tdb --report mc_fe_v2062_repair_report.json --allow-ambiguous

The change is syntactic, so that pycalphad 0.11.2 can read the files; every change is listed in the JSON
reports next to the files. In summary:

- MatCalc-only directives commented out (prefix `$ [tdb_repair]`): `REFERENCE_ELEMENT`, `ATTACH_CONTRIBUTION`,
  `ADD_COMPOSITION_SET` (mc_ni 11, mc_fe 14).
- MatCalc-only `HMVA` parameters (vacancy formation enthalpy; not part of the Gibbs energy) commented out
  (mc_ni 13, mc_fe 21).
- Typos fixed: temperature limit `6000.00.00` -> `6000.00` (2 + 2), `G(PH;...)` -> `G(PH,...)` (mc_fe 1),
  a missing `!` (mc_fe 1), stray `: > >> 1` after a constituent list (mc_fe 1), blanks in four citation tags
  (mc_fe), bibliography free text commented out (1 + 1).
- mc_fe only, ambiguous (`--allow-ambiguous`): two `PDMN_B2` parameters written `273.00 273 +46000-23*T ...;
  6000.00 N ; 6000.00 N`; the stray `273` and the duplicated range tail were dropped. If the `273` was meant as
  part of the expression, the effect is +273 J/mol on two parameters of a Pd-Mn phase.
- No G, L, TC or BMAGN value was changed otherwise (the tool compares every retained parameter statement with
  the original and aborts on any difference). Retained parameters: 3586 (mc_ni), 4093 (mc_fe).

## What the derivative does not reproduce

- `ATTACH_CONTRIBUTION BCC_B2 BCC_A2 ORDER_DISORDER` is lost, so `BCC_B2` holds only the ordered part of the
  MatCalc split model. `python/calphad_solver.py` therefore excludes `BCC_B2` (catalogue `excludedPhases`).
- Composition-set hints are lost; pycalphad finds miscibility gaps itself.
- `HMVA` and other kinetic extras are not used in an equilibrium calculation.
- pycalphad warns that the type character `%` has no `TYPE_DEFINITION` line; it is the MatCalc/Thermo-Calc
  default type and carries no model.

Use in this application: CALPHAD calculation with the named database (pycalphad), not validated against
experiment. Phase selection differs from MatCalc practice (MatCalc selects phases explicitly; the solver selects
all phases except the excluded ones); see the catalogue entries `mc_ni` and `mc_fe`.
