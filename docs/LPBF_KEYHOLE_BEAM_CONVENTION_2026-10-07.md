# LPBF keyhole beam convention and depth datum: zero-served-value-drift record (2026-10-07)

**Comparison and provenance only. No served value changes; no frozen file is touched.** Design: D-3a (Fabbro beam
convention) and D-1 (powder layer and depth datum), both "text plus diagnostic" outcomes.

## What changed

| item | where | served value |
|---|---|---|
| Depth datum and spot definition written into provenance | `data/benchmark/{hofmann-316l-2026,totis-ti64-2021}/LICENSE-ATTRIBUTION.md`, `HOFMANN_PROVENANCE` / `TOTIS_PROVENANCE` in `python/lpbf_public_datasets.py` (text fields only; data-file SHA-256 pins unchanged) | none |
| Declared sensitivity column `depthDatumCorrection_um` = phi * t | `python/tools/lpbf_dataset_comparison.py` (`depth_datum_correction_um`, `rows[].sensitivity`) | none (reported next to the served prediction) |
| Gan 2021 Supplementary Data 1 flagged as the Cunningham 2019 experiments | `python/lpbf_keyhole_literature.py` (`independentOfCunningham2019 = False`), Gan `LICENSE-ATTRIBUTION.md` | none |
| Fabbro half-maximum-diameter diagnostic and scope flag | `python/tools/lpbf_keyhole_benchmark.py` (`fabbro_fwhm_diagnostic`, `--beam-convention`), record `docs/LPBF_KEYHOLE_BEAM_CONVENTION_2026-10-07.json` | none ("diagnostic, not served") |

## Settled datum and spot facts

- **Hofmann 316L (2026):** depth is measured from the original substrate surface (powder/substrate interface) to the
  pool bottom, width at that level (Fig. 2, Sec. 2.2). Spot: single-mode Gaussian, 50 um focus, defocused to 80/110/140 um;
  the diameter definition is not stated (1/e^2 assumed). PSD D50 30.4 um; packing not stated.
- **Totis Ti-6Al-4V (Vaglio 2020 / Data in Brief):** depth is measured from the top of the printed base under the 25 um
  layer, height above it (Fig. 1, Fig. 2(b), Sec. 1.3). Spot 50 um, 1/e^2 stated (Sec. 2). The base was printed in the
  same job, not wrought.
- KU Leuven datum and spot remain unconfirmed (sensitivity only). Lane, NIST, Trapp, Ghosh are bare: datum is the surface.

## Datum sensitivity column

`depthDatumCorrection_um = phi * t` with phi = 0.60 (Trapp 2017), for powder-layer rows (t > 0) of sources whose datum is
the substrate: Hofmann 30 / 60 um -> 18 / 36 um, Totis 25 um -> 15 um. Wording: "geometric assumption (h_surface = phi*t);
powder denudation not modelled". It is a declared assumption-based conversion, never a confirmed correction and never
the served depth. The existing comparison records `LPBF_DATASET_COMPARISON_*` were not regenerated (the full run is
thousands of solver calls); they are unchanged, and the next regeneration adds the `sensitivity` key to the 547 Hofmann/Totis
rows with t > 0 (additive) and the updated Totis limit sentence.

## Fabbro diagnostic

Fabbro 2020 Sec. 3.4 defines his d as the uniform / half-maximum diameter (56 um for Cunningham's 95 um 1/e^2 beam,
FWHM = sqrt(ln2/2) x 1/e^2 = 0.5887 d); the app passes the 1/e^2 diameter. `fabbroDepthFwhm_um` repeats the solver's own
`fabbro_keyhole_depth_m` call (arguments recorded from the unchanged solver) with d = FWHM, same absorptivity, properties and
ramp. `aspectRatioInScope = (e / d_FWHM >= 1) and (2 <= Pe <= 10)`, both on the FWHM basis.

Ti-6Al-4V, served -> FWHM diagnostic (median predicted / measured; MAPE %): Cunningham 95 um (n 46) 0.62 -> 1.00 and
45 -> 26, in scope 28/46; Cunningham 140 um (n 23) 0.12 -> 0.20, 1/23 in scope (R < 1, outside Fabbro's cylindrical
keyhole); Zhao bare (n 8) 0.35 -> 0.54; Zhao powder (n 11) 0.83 -> 1.32. NIST IN718 285 W / 960 mm/s / 67 um: served 123.9 um
(unchanged), FWHM diagnostic 195.4 um (melt depth 139.7 um).

**Not adopted:** the FWHM convention breaks the vapour <= measured-melt-depth bound on IN718 and 316L (NIST 0/7 -> 7/7,
Hofmann bare 55/210 -> 93/210, KU 316L 11/44 -> 26/44; D-3a record), so it stays a labelled diagnostic. The physics that
could unblock it is a sourced per-alloy keyhole absorptivity (D-3b), not the beam convention alone.

## Limits

Cunningham and Gan Supplementary Data 1 are the same experiments (not independent); Cunningham/Zhao depths are
digitized; 20 C preheat is assumed for those rows; the Zhao rows are boundary points; phi = 0.60 is Trapp's estimate for
his cups; powder denudation and bead height change the real surface height.

Tests: `python/test_lpbf_zero_drift_depth.py` (self-contained; SHA pins, no network).
