# IN718 source metadata review — 2026-09-21

Scope: local, hash-checked NIST mds2-2716 source archive. This is source inspection,
not temperature reconstruction, solver validation or phase acceptance.

`python/nist_hdf5_review.py` checks the manifest before and after inspection,
opens HDF5 read-only, and records attributes, shapes, dtype, chunks and compression.
It never reads dataset values or evaluates calibration expressions. External/soft
links, repeated hard-link objects, excessive traversal/attributes and nonfinite
metadata are rejected. This bounded inspection is not a hostile-file OS sandbox.
The optional h5py import is outside the application worker. Output uses exclusive
creation. The checked-in `data/benchmark/nist-amb2022-03/hdf5-metadata-review.json`
contains the complete inspected metadata; `source-context.json` carries the relevant
conditions and both HDF5 fingerprints into immutable source revisions.

Runtime: existing system Python3.12.10, h5py3.16.0, NumPy2.5.3. No package installed.
This runtime is for metadata inspection only, not a locked solver-environment claim.
Reproduce with that interpreter and:

```
python -B python/nist_hdf5_review.py data/benchmark/nist-amb2022-03/manifest.json --output NEW-report.json
python -B python/test_nist_hdf5_review.py
```

## Findings from local HDF5 attributes

- 14 scan-strategy objects;59 thermography objects, including27 signal datasets:
21 line repeats and6 pads (two `_SS` pads excluded from challenge conditions).
Baseline groups are `Line_0_1` through `Line_0_3`, not `Line_0_Y_Z`. Other line
groups identify six additional cases and three repeats each. Keep repeats grouped.
- All Signal arrays are uint16, stored in gzip chunks25×25×25. Single-track shapes
are700×640×304; X pads40001×640×304; Y pads10001×640×304. One decoded X-pad cube
would occupy15,565,189,120 bytes. Inspection reads no such cube.
- Signal attributes report digital levels,12-bit depth, threshold100 and
`threshold_zeros="true"`. These zeros are censored detector data, not0°C/K.
- ThermalData reports30000 frames/s and20000ns shutter exposure. These do not establish
trigger alignment, spatial registration or a measurement comparison operator.
- Group conditions preserve each source power, speed and spot size with source
units. `spot_size_measure` is literally `D4s`. Scan paths are `/XYPT/Xpad` and
`/XYPT/Ypad`; T is an instrument trigger. Calibration flags are stored as the
string `false`; do not treat a nonempty string as a true calibration flag.

## Temperature conversion remains unavailable

The exact stored model text is:

```
T(x) = 14388/a/log((c*e/x+1)-b/a;
```

The parentheses are unbalanced. Coefficients are a0.9655, b197.2, c43920000;
input is `Signal [DL]`, output claims emissivity-corrected°C. The archive's note
mentions a September2024 model-equation correction, but this inspected string
still needs clarification. No emissivity value was found among the73 inspected
objects' attributes. These observations do not authorize guessing the grouping,
emissivity, Celsius/Kelvin convention or valid conversion range. R²0.9988 and
RMSE4.923 describe the stored regression; they do not validate our solver.

The [NIST challenge description](https://www.nist.gov/system/files/documents/2022/05/26/AMB2022-03%20Measurement%20and%20Challenge%20Descriptions_1.01.pdf)
Table2 labels the spot diameter D4σ. Sections3.1–3.2 describe apparent-temperature
comparison, three repeats, aligned centerline histories and an inflection-based
measurement definition. This external document was consulted but is not a locally
hashed artifact in the three-file archive. PDF text was available; the web tool's
page-image retrieval failed with a cache miss.

Next gate: obtain an unambiguous primary calibration equation/emissivity and freeze
the measurement operator/validity limits before reconstructing temperatures. Then
choose independent case groups and comparison tolerances before solver evaluation.
Thermal validation, powder-bed validation and training readiness remain false.
Common-core work and independent numerical tests can proceed meanwhile.

## Verification

Four HDF5 regressions first failed, then passed: metadata fidelity with forbidden
dataset reads, link/cycle rejection, oversized attributes, and nonfinite values.
Catalog regression first failed, then passed for a mismatched HDF5 review hash.
Actual source hashes matched before/after metadata inspection. Existing archived
revisions are untouched; updated review metadata needs a new explicit preview/import.
