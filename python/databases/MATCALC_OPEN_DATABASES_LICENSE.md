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

## mc_ti (Ti alloys and Ti aluminides, release 2.03)

`mc_ti_v203_repaired.tdb` is a **derivative database** of the MatCalc titanium database `mc_ti_v2.03.tdb`
(release of January 2025 by MatCalc Engineering GmbH). It is a special database on the MatCalc site, not one of
the three on the "open databases" page; its file header states the same terms:

- the database: **Open Database License (ODbL) v1.0**, http://opendatacommons.org/licenses/odbl/1.0/
- the individual contents: **Database Contents License (DbCL) v1.0**, http://opendatacommons.org/licenses/dbcl/1.0/

Copyright: Erwin Povoden-Karadeniz, TU Wien / MatCalc Engineering GmbH (copyright holder and editor named in the
file header). The MatCalc page states the special databases are free for private, scientific and commercial use.
The licence covers only this TDB file and its repair report, not the rest of the repository.

| Item | Value |
|---|---|
| Source page | https://www.matcalc.at/index.php/databases/special-databases |
| Original URL | https://www.matcalc.at/images/stories/Download/Database/mc_ti_v203.tdb |
| Original file | `mc_ti_v203.tdb`, 78,191 bytes, retrieved 2026-10-09 |
| sha256 original | `7bec5404071fa3cbdaf340bdb431af98f5a00a6d5526b84ff31834b5ff5841cb` |
| Repaired file | `mc_ti_v203_repaired.tdb`, 81,833 bytes |
| sha256 repaired | `f8758e12d8a96109b4dee0e0d95365ebe6ec19b0d1b8e3b249465c46a12e94ff` |
| Repair report | `mc_ti_v203_repair_report.json` |

Produced (byte for byte reproducible) by the repository tool `python/tools/tdb_repair.py`:

    python python/tools/tdb_repair.py mc_ti_v203.tdb mc_ti_v203_repaired.tdb --report mc_ti_v203_repair_report.json \
        --origin "MatCalc special databases, https://www.matcalc.at/index.php/databases/special-databases"

The original is not committed. Changes are syntactic only, so that pycalphad 0.11.2 can read the file:

- MatCalc-only directives commented out (prefix `$ [tdb_repair]`): `REFERENCE_ELEMENT TI` and
  `ATTACH_CONTRIBUTION BCC_B2 BCC_A2 ORDER_DISORDER` (2).
- MatCalc-only `HMVA` parameters (vacancy formation enthalpy; not part of the Gibbs energy) commented out (7).
- 22 `FUNCTION` statements whose citation tag stood alone on the next line (`... 6000.00 N` newline
  `REF: 170 !`) had the tag joined to the statement and `REF: 170` written as `REF:170`. pycalphad rejected the
  split form; the function expressions are untouched.
- Bibliography free text commented out (1).
- No G, L, TC or BMAGN value was changed (the tool compares every retained parameter statement with the original
  and aborts on any difference). Retained parameters: 508.

Share-alike: the repaired file is an altered database, so ODbL share-alike applies to it. Anyone who publicly uses
it must keep this notice, the attribution above and the same licence for the altered database.

What the derivative does not reproduce: `ATTACH_CONTRIBUTION BCC_B2 BCC_A2 ORDER_DISORDER` is lost, so `BCC_B2`
holds only the ordered part of the MatCalc split model (it does not appear in the Ti-6Al-4V runs). `HMVA` extras
are not used in an equilibrium calculation.

Scope in this application (Opus review 2026-10-09, `.orchestra/REPORT-wave-b-opus-review.md`): valid for the beta
transus, liquidus/solidus and single-phase beta of Ti-6Al-4V. Not valid for alpha/beta fractions or phase
compositions below about 900 degC (beta fraction 1 % at 800 degC against roughly 15 to 20 % expected; below about
850 degC the BCC phase switches to a V-rich branch). The database holds no Fe and no O. The solidus is about 25 K
below handbook values. Not validated against experiment in this application.
