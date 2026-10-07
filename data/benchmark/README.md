# Engineering benchmark archive

Raw payloads stay in ignored `raw/` directories; small provenance manifests are versioned. On 2026-09-15 three previously downloaded NIST mds2-2716 files were copied from the installation workspace to `nist-amb2022-03/raw/` and fingerprinted. The source copy was retained.

Run from the repository root:

```powershell
python -B python/benchmark_manifest.py data/benchmark/nist-amb2022-03/manifest.json
```

The verifier checks containment, duplicate paths, official source URL shape, bytes, local SHA-256 and the leading HDF5 signature. It does not parse full HDF5 arrays or prove publisher authenticity. A matching checksum establishes unchanged local bytes only. Raw camera signals remain ineligible for temperature validation or training until a reviewed calibration, spatial/time mapping and grouped split exist. This first adapter only supports the archived IN718 bare-plate input kinds.

## Pilot material decision

The founder selected **Ti-6Al-4V** on 2026-09-15. Machine, beam profile, powder lot, heat treatment, measured metrics and acceptance tolerances remain undecided. IN718 data exercise ingestion only and cannot validate Ti-6Al-4V predictions.

Ti-6Al-4V candidates to inspect before assigning holdouts:

- [NIST AMB2025-03](https://doi.org/10.18434/mds2-3734): PBF-LB Ti-6Al-4V high-cycle rotating-bending fatigue. Candidate for E04; fatigue data do not validate a melt-pool thermal field. Listed on the [official AM Bench data page](https://www.nist.gov/ambench/direct-am-bench-data-links-and-referencing-guidance).
- [CMU melt-pool variability dataset](https://doi.org/10.1184/R1/25696293): candidate for geometry comparisons, subject to matching process/measurement scope and source-file review.
- [NIST-hosted Ti-6Al-4V benchmark paper](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=956754): candidate source for melt-pool/keyhole/absorptance experiments and the linked data record. No values have been transcribed or used for calibration here.

No candidate is marked accepted, independently validated, or part of the training set by merely appearing in this list.

## CMU Ti-6Al-4V import available

The [CMU v1 archive guide](cmu-ti64-meltpool-v1/README.md) documents the verified three-file manifest and offline importer. It imports 216 single-track and 410 multi-track measurements with source lines and explicit units. Single-track laser power is absent in the CSV and remains unresolved. No training/holdout split or solver validation is assigned automatically.

## NIST mds2-2525 absorptance archive

`nist-mds2-2525-ti64-absorptance/` holds the absorptance tables of the NIST time-resolved laser absorptance publication ([DOI 10.18434/mds2-2525](https://doi.org/10.18434/mds2-2525), record 1.3.2). The `Spot on Bare Metal` trace is Ti-6Al-4V (SRM 654b, ~300 um polished coupon, no powder); the `Al_*` challenge tables are aluminium (SRM 1241c) and have no application material counterpart. Values are measured for NIST's experiment only and do not validate the application.

The files were acquired from Internet Archive snapshots of the NIST download URLs on 2026-10-06 (data.nist.gov timed out); each SHA-256 and byte count matches the NERDm record. The Ti-6Al-4V scan CSV and the uncertainty-analysis PDF are not acquired and are listed as `absent_files` in `official/manifest.json`; the X-ray images, movies, notebooks and other out-of-scope components of the record are listed under `not_archived_components` with their NIST hashes. `derived/` holds a locally derived summary produced by `python/lpbf_nist_mds2_2525_absorptance.py --write`; its analysis windows are local choices, not NIST phase boundaries.

## Wave 2 open datasets (2026-10-06)

All four were retrieved on 2026-10-06 without the data.nist.gov file server. Each folder's `LICENSE-ATTRIBUTION.md` gives the source URL, licence, byte count and SHA-256; `python/lpbf_public_datasets.py` pins every committed table and refuses changed bytes. They are compared in `docs/LPBF_DATASET_COMPARISON_2026-10-06.*` (`python/tools/lpbf_dataset_comparison.py --include-wave2`); this is a comparison, not validation.

- `ku-leuven-316l-ti64-2021/`: KU Leuven (Coen 2021) Figshare CSVs, CC0, committed unmodified under `source/`. Only the measured `w exp` / `d exp` / `R exp` columns and the authors' regime label are used; the model columns are excluded. The beam diameter is unverified (37.5 um carried from the IN718 record; 75 um re-run as a sensitivity).
- `lane-in625-amb2018-02/`: Lane et al. 2020 (AMB2018-02) Tables 3 and 4, IN625 bare-plate single tracks. AMMT cooling rates are flagged do-not-use in both tables (Table 3 footnote c; Table 4 AMMT classes repeat the AMMT-20 us values). The AMMT 137.9/179.2 W (Table 3) vs 150/195 W (Section 2 case definitions) question is unresolved: the Fig. 2 caption says the indicated powers are the applied laser power, but the Fig. 2 image was not read.
- `nist-amb2022-03-thermal-targets/`: AMB2022-03 results document Tables 1-3 (TTAM, TSCR, TLCR, TTCR) for the seven IN718 cases. Reference targets only; no like-for-like model comparison exists in the app.
- `simonds-316l-2018/`: Simonds et al. 2018 Table III, 316L SRM 1155a stationary-spot absorptance. Reference target only; the app has no stationary-spot model.

## Wave 5 literature transcriptions (2026-10-07)

Numbers transcribed from maintainer-supplied papers; the PDFs and figures are not committed ("values transcribed from the published article; article not redistributed"). Each folder's `LICENSE-ATTRIBUTION.md` gives citation, DOI, licence, the SHA-256 of the PDF copy that was read, and the digitization method. `python/lpbf_literature_datasets.py` pins every CSV (SHA-256) and refuses changed bytes; every row carries a `locator` (table / figure panel) and a `digitized` flag, and digitized values sit in files named `*_digitized.csv`. Tests: `python/test_lpbf_literature_datasets.py`.

- `ghosh-in625-2018/`: Ghosh et al. 2018 (JOM), seven IN625 bare-plate single tracks (49-195 W, 200-800 mm/s). Width/depth are numbers printed in Fig. 1 (`digitized=false`); lengths digitized from the Fig. 2 bars (separate file). The experimental spot size is not stated (140 um model value used, an assumption). Case 7 (195 W, 800 mm/s) matches Lane CBM-B in width and length but not in depth (38 vs 91 um), unresolved.
- `trapp-316l-2017/`: Trapp et al. 2017 (CC BY 4.0), all digitized. 11 316L bare-disc width/depth rows at 500 mm/s, 60 um spot (Fig. 3(a)) and 107 calorimetric absorptivity-vs-power points (316L disc 100/500/1500 mm/s, 316L powder 100/1500 mm/s, W and Al 1100 at 1500 mm/s). Specimens are 0.5 mm discs, not semi-infinite plates.
- `rubenchik-powder-2015/`: Rubenchik et al. 2015, powder-layer absorptivity vs temperature at 970 nm (316 SS, Ti-6Al-4V, Al), digitized at 100 C steps. Cold powder, no melting.
- `ye-2019-absorptivity/`: Ye et al. 2019 Table 1, minimal calorimetric absorptivity Am of bare Ti-6Al-4V (0.26), IN625 (0.28), 316L (0.28) foils.
- `heigel-in625-amb2018-01/`: Heigel, Lane, Levine 2020 Table 2, cooling rates (1290-1000 C) in the AMB2018-01 IN625 3D builds per feature and layer parity. Thermal reference target, not melt-pool geometry.

Read but not ingested: Levine et al. 2020 (AM-Bench 2018 overview; its AMB2018-02 numbers are the Lane 2020 data already in `lane-in625-amb2018-02/`, so ingesting them would double-count); Yadroitsev et al. 2010 (melt-pool sizes only as text ranges for 304L or figures for 904L, and a categorical 316L stability map); Lass et al. 2017 and Keller et al. 2017 (IN625 microsegregation, kept for the segregation-model lane); Simonds et al. 2021 (figure-only time-resolved Ti-6Al-4V absorptance and x-ray geometry, left for a digitization follow-up).

None of these sources is in the calibration scorecard. `TRAINABLE_SOURCES` lives inside the frozen `CALIBRATION_CONFIG`, whose SHA-256 is bound to `data/calibration/lpbf-meltpool-calibration-v1.json`; adding a source is a new calibration version (new config, new artefact, `npm run lpbf:calibration`), a decision for the maintainer.

## NIST mds2-2716 thermography signal metrics

`nist-amb2022-03/derived/thermography-signal-metrics-v1.json` is a locally derived table from the AMB2022-03 IN718 staring-camera file ([DOI 10.18434/mds2-2716](https://doi.org/10.18434/mds2-2716), record 1.3.1) and the pad scan-strategy file. The 550 MB HDF5 file is not committed: `python/lpbf_nist_mds2_2716_thermography.py` reads it from `$METALLIKSA_NIST_2716_DIR`, `$METALLIKSA_EXTERNAL_DATA/nist-mds2-2716/` (see `external-data-manifest.json`) or the ignored `nist-amb2022-03/raw/`, and refuses to run unless size and SHA-256 equal the NIST NERDm record (committed as `nist-amb2022-03/official/nerdm-record-mds2-2716.json`). `derived/manifest.json` pins the inputs, the derived bytes and the runtime. All values are raw camera signal in digital levels (time above thresholds, signal decay from saturation, saturated-region length) plus an inferred pixel pitch and the commanded XYPT track table. No temperature, cooling rate or time above melting is derived: the stored calibration model is malformed and gives no emissivity. Regenerate with `python python/lpbf_nist_mds2_2716_thermography.py --data-dir <dir>`. The citation in the derived table is built from the committed NERDm record (all five authors, exact title, version 1.3.1 issued 2026-01-06, first released 2022-07-15). In the scan-strategy file the StaringCamera trigger (T bit 2) is a single-sample pulse at the first laser-on sample (Xpad 497, Ypad 182), not one sample before it. `external-data/` is git-ignored, and the 550 MB file is flagged `manualPlacementOnly` in `external-data-manifest.json`, so `fetch_external_data.py --fetch` never downloads it.

`python/tools/lpbf_nist_2716_thermography_comparison.py` reads only the hash-pinned derived table and writes `docs/LPBF_NIST_2716_THERMOGRAPHY_COMPARISON_2026-10-06.{json,md}`: case-to-baseline ratios and Spearman ranks of the camera metrics next to the Rosenthal, Eagar-Tsai and Goldak liquidus length and dwell. Every row is `sensitivity-only` or `unavailable`, because the DL thresholds and the model liquidus are different isotherms; absolute values, cooling rates, time above melting, pads and the radiance-temperature bracket are listed as unavailable with reasons. Not done in this lane: pad camera analysis (spec section 4, opt-in) and the gated Phase 2 radiance-temperature bracket.

