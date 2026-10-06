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
- `lane-in625-amb2018-02/`: Lane et al. 2020 (AMB2018-02) Tables 3 and 4, IN625 bare-plate single tracks. AMMT cooling rates are flagged do-not-use (Table 3 footnote c); the AMMT 137.9/179.2 W vs 150/195 W power question is unresolved.
- `nist-amb2022-03-thermal-targets/`: AMB2022-03 results document Tables 1-3 (TTAM, TSCR, TLCR, TTCR) for the seven IN718 cases. Reference targets only; no like-for-like model comparison exists in the app.
- `simonds-316l-2018/`: Simonds et al. 2018 Table III, 316L SRM 1155a stationary-spot absorptance. Reference target only; the app has no stationary-spot model.
