# LPBF dataset comparison (2026-10-07)

**Comparison of screening kernels against published single-track measurements; not experimental validation; estimated material laws; absorptivity assumed.**

Schema `lpbf-dataset-comparison-1`; implementation fingerprint `f3ba98969a723702d9dbe15ae623d28f1327356441919ffdd6edf4e74a6a150d`; quick mode: False. Honesty: comparison, not validation; screening kernels; estimated material laws; absorptivity assumed (not measured); published single-track measurements, no replicate or uncertainty model; a failing comparison is reported, not fitted away. `experimentalValidation` = false.

Slim view record `LPBF_DATASET_COMPARISON_2026-10-07_waveb-physics.view.json` (this record minus `breakdowns` and `referenceTransient.rows`; sha256 of its LF bytes `c959597c2c762bd79e1e356ab64145cc39b9a3b63be372db5d5e3114446fb216`).

## Datasets

- **hofmann-316l-2026** (316L Stainless Steel): DOI 10.5281/zenodo.16979848, CC BY 4.0, 677 rows recorded, table sha256 `d4bbc7a60b536118586f44b64beb0fa20f94133f6d1a8d0fdcf726003720c3d8`. Hofmann et al., melt-pool geometry data for 316L single tracks (Aconity Midi), Zenodo 10.5281/zenodo.16979848 (v1, 2025-08-28); associated paper Materials & Design 262 (2026) 115459, doi:10.1016/j.matdes.2026.115459.
  - caveat: Measured cross-sections from micrographs; the uncertainty budget is not stated in the files read.
  - caveat: The d_laser column is the laser spot DIAMETER in mm; the diameter definition (1/e^2 or other) is not stated on the Zenodo record and was not confirmed from the paper: treated as 1/e^2 by assumption.
  - caveat: Absorptivity is not measured; the comparison uses the repo's estimated 316L absorptivity.
  - caveat: Build-plate temperature is not given: 20 C is an assumption.
  - caveat: t_powder = 0 rows are bare plate; t_powder 30/60 um are powder layers (the packing is not stated).
  - caveat: The CSV header calls the area column 'um' although the values are um^2 (width x depth scale confirms).
  - caveat: 677 rows contain repeated parameter sets (623 distinct) -- replicates are kept as separate rows.
  - caveat: Where the width/depth are taken along the track and whether the section is at steady state is not stated in the files read.
  - caveat: 316L thermophysical properties used by the models are estimated, not measured.
- **totis-ti64-2021** (Ti-6Al-4V): DOI 10.17632/s9438vb5xd.1, CC BY 4.0, 80 rows recorded, table sha256 `3b5794f3a25a5f67fa0d8d1ab006834205ef820b046c24deb15836025825d623`. Totis, Vaglio et al., single-track Ti6Al4V SEM images and geometrical data (Concept Laser M2, 50 um laser spot), Mendeley Data, 10.17632/s9438vb5xd.1 (v1, 2021-04-26); related article Data in Brief, doi:10.1016/j.dib.2020.106443.
  - caveat: Tracks were made on a 25 um powder layer over a printed Ti-6Al-4V base (not a bare plate, not a semi-infinite wrought substrate); the 50 um spot is taken as 1/e^2 from the research note.
  - caveat: The workbook does not state the depth reference line (original substrate surface vs powder surface): depth is used 'as found'; the Mendeley page and the workbook do not say.
  - caveat: One track per (power, speed) cell: no replicates, no scatter estimate.
  - caveat: Absorptivity is not measured; the comparison uses the repo's estimated Ti-6Al-4V absorptivity.
  - caveat: Build-plate temperature is not given: 20 C is an assumption.
  - caveat: No balling flag in the workbook: the regime classifier uses inputs only for this dataset.
  - caveat: Width, depth and height are SEM-derived values read from the workbook sheets 'Track width (W)', 'Track depth (D)', 'Track height (H)', 'Contact angle' (microhardness sheet not used).
  - caveat: Ti-6Al-4V thermophysical properties used by the models are estimated, not measured.
- **cmu-ti64-st-2026** (Ti-6Al-4V): DOI 10.1184/R1/25696293.v1, CC BY 4.0, 216 rows recorded, table sha256 `7f415afb20cd8e1698efcbc4948654ed4b95bb4fc1854b5c1e7f45e9874a1f90`. CMU KiltHub, Ti-6Al-4V melt-pool variability, 10.1184/R1/25696293.v1.
  - caveat: ST source table has no power column; beam diameter is also unreported. No solver prediction is made.
- **cmu-ti64-mt-2026** (Ti-6Al-4V): DOI 10.1184/R1/25696293.v1, CC BY 4.0, 410 rows recorded, table sha256 `d8d318fd673c69ad250a9d44cc7b37b71d3706cde7ad93539049454aedf09c57`. CMU KiltHub, Ti-6Al-4V melt-pool variability, 10.1184/R1/25696293.v1.
  - caveat: Beam diameter, layer, preheat and absorptivity are unreported; no solver prediction is made.
- **ku-leuven-in718-2021** (Inconel 718): DOI 10.6084/m9.figshare.15035706.v1, CC0, 48 rows recorded, table sha256 `d8731ecc5cd027e697e4fbd7f9dabb634c197f0325f4282eb3c86ce9ff9d512b`. KU Leuven IN718 melt-pool measurements, Figshare, 10.6084/m9.figshare.15035706.v1.
  - caveat: Source CSV does not state units for w exp/d exp; article describes half-width, so dimensions are retained as source values and excluded from numeric comparison until resolved.
  - caveat: 48 numbered conditions; 38 contain both dimensions and 10 have missing dimensions.
  - caveat: Condition means, not individual cross-sections; source sample counts vary.
  - caveat: Paper reports 37.5 um spot and 60 um powder layer; preheat and measured absorptivity are not reported.
- **ku-leuven-316l-2021** (316L Stainless Steel): DOI 10.6084/m9.figshare.15035733.v1 + 10.6084/m9.figshare.15035703.v1, CC0, 44 rows recorded, table sha256 `e031aead71bf64c70a35ae05d64c0c576d33c2ae757a1e5bda68b5da532ac831`. V. Coen (KU Leuven), melt-pool measurement CSVs for 316L and Ti-6Al-4V, Figshare (CC0, 2021-07-22): 316L 10.6084/m9.figshare.15035733.v1 (raw) and 15035703.v1 (processed); Ti-6Al-4V 15035709.v1 (raw) and 15035712.v2 (processed). Manuscript: V. Coen, L. Goossens, B. Van Hooreweder, 'Methodology and experimental validation of analytical melt pool models for laser powder bed fusion', J. Mater. Process. Technol. 304 (2022) 117547, doi:10.1016/j.jmatprotec.2022.117547 (article not read: publisher returned HTTP 403).
  - caveat: Only the measured 'w exp', 'd exp', 'R exp' columns and the authors' 'melting regime' label are read from the processed '(2)' files; their 'model' and 'error' columns (analytical-model outputs) are excluded by name.
  - caveat: Units: the raw '(1)' files tag every section row with 'um' (micrometre sign); the processed '(2)' files carry no units. 316L 'w exp'/'d exp' equal the arithmetic means of the raw sections; Ti-6Al-4V values differ from the raw means by a few um (see raw_mean_* columns), so the processing step is not fully reproduced here.
  - caveat: Width operator: 'Width' in the raw files; the authors' R = d/w with keyhole for R > 1 implies full width (inference, the article was not read).
  - caveat: Regime labels are the authors' published labels ('melting regime' column), kept verbatim; they are not a strict function of R exp and are not the repo's screening classifier.
  - caveat: Beam diameter unverified: 37.5 um carried from the 2026-10-05 KU Leuven IN718 record ('Paper reports 37.5 um spot'); the article (doi:10.1016/j.jmatprotec.2022.117547) could not be read (HTTP 403), so diameter vs radius and the beam-size definition are not confirmed.
  - caveat: Powder layer not stated in the files read; the 2026-10-05 KU Leuven IN718 record cites a 60 um powder layer from the Coen article, which could not be read here (HTTP 403), so it is not carried over to these rows (the kernels ignore layer thickness, so there is no numeric effect). Preheat and absorptivity are not stated in the files read; 20 C preheat is an assumption.
  - caveat: Conditions blank in the processed file (316L 600 W at 400/500/1000/1100 mm/s) carry no exp value and are not compared, although the raw file has partial sections for some of them.
  - caveat: Condition means: per-condition section count is taken from the raw file (raw_sections_n); the trailing 'nb. of samples' column of the processed file belongs to its regime-summary block and is not used.
  - caveat: not compared: ku-leuven-316l-2021-41 (w exp / d exp blank in the processed source file)
  - caveat: not compared: ku-leuven-316l-2021-42 (w exp / d exp blank in the processed source file)
  - caveat: not compared: ku-leuven-316l-2021-47 (w exp / d exp blank in the processed source file)
  - caveat: not compared: ku-leuven-316l-2021-48 (w exp / d exp blank in the processed source file)
- **ku-leuven-ti64-2021** (Ti-6Al-4V): DOI 10.6084/m9.figshare.15035709.v1 + 10.6084/m9.figshare.15035712.v2, CC0, 14 rows recorded, table sha256 `e031aead71bf64c70a35ae05d64c0c576d33c2ae757a1e5bda68b5da532ac831`. V. Coen (KU Leuven), melt-pool measurement CSVs for 316L and Ti-6Al-4V, Figshare (CC0, 2021-07-22): 316L 10.6084/m9.figshare.15035733.v1 (raw) and 15035703.v1 (processed); Ti-6Al-4V 15035709.v1 (raw) and 15035712.v2 (processed). Manuscript: V. Coen, L. Goossens, B. Van Hooreweder, 'Methodology and experimental validation of analytical melt pool models for laser powder bed fusion', J. Mater. Process. Technol. 304 (2022) 117547, doi:10.1016/j.jmatprotec.2022.117547 (article not read: publisher returned HTTP 403).
  - caveat: Only the measured 'w exp', 'd exp', 'R exp' columns and the authors' 'melting regime' label are read from the processed '(2)' files; their 'model' and 'error' columns (analytical-model outputs) are excluded by name.
  - caveat: Units: the raw '(1)' files tag every section row with 'um' (micrometre sign); the processed '(2)' files carry no units. 316L 'w exp'/'d exp' equal the arithmetic means of the raw sections; Ti-6Al-4V values differ from the raw means by a few um (see raw_mean_* columns), so the processing step is not fully reproduced here.
  - caveat: Width operator: 'Width' in the raw files; the authors' R = d/w with keyhole for R > 1 implies full width (inference, the article was not read).
  - caveat: Regime labels are the authors' published labels ('melting regime' column), kept verbatim; they are not a strict function of R exp and are not the repo's screening classifier.
  - caveat: Beam diameter unverified: 37.5 um carried from the 2026-10-05 KU Leuven IN718 record ('Paper reports 37.5 um spot'); the article (doi:10.1016/j.jmatprotec.2022.117547) could not be read (HTTP 403), so diameter vs radius and the beam-size definition are not confirmed.
  - caveat: Powder layer not stated in the files read; the 2026-10-05 KU Leuven IN718 record cites a 60 um powder layer from the Coen article, which could not be read here (HTTP 403), so it is not carried over to these rows (the kernels ignore layer thickness, so there is no numeric effect). Preheat and absorptivity are not stated in the files read; 20 C preheat is an assumption.
  - caveat: Conditions blank in the processed file (316L 600 W at 400/500/1000/1100 mm/s) carry no exp value and are not compared, although the raw file has partial sections for some of them.
  - caveat: Condition means: per-condition section count is taken from the raw file (raw_sections_n); the trailing 'nb. of samples' column of the processed file belongs to its regime-summary block and is not used.
- **lane-in625-2020** (Inconel 625): DOI 10.1007/s40192-020-00169-1, not stated as a licence: PMC author manuscript (NIHMS1686029), PMC permissions text 'available for text mining ... fair use'; NIST-authored; numeric table values transcribed with citation, 23 rows recorded, table sha256 `32fe10fb8606a49cdc59e1e3753b40e6be9ea9751dae9ec8ac95c217e6d16179`. B. Lane et al., 'Measurements of melt pool geometry and cooling rates of individual laser traces on IN625 bare plates', Integr. Mater. Manuf. Innov. 9(1) (2020), doi:10.1007/s40192-020-00169-1, PMC8194244, Tables 3 and 4 (AM-Bench AMB2018-02).
  - caveat: Width and depth are Table 3 'Cross Section (um)' track means (N = 3 microscopy measurements per track, sigma = spread, not an uncertainty); the first Cross Section column is width, the second depth (their CBM means reproduce Table 4 Class Width/Depth).
  - caveat: Bare IN625 plate, no powder; preheat not stated (20 C assumed). Spot sizes are D4sigma diameters (CBM 100 um, AMMT 170 um, Table 1); for a Gaussian beam D4sigma equals the 1/e^2 diameter the kernels take.
  - caveat: AMMT power: Fig. 2 caption: 'Laser power values indicated are the applied laser power'; Table 3 lists 137.9/179.2 W for the AMMT cases and the Section 2 case definitions give 150/195 W. Whether these are applied vs commanded powers is not stated explicitly, and the Fig. 2 image was not read. Status: UNRESOLVED. Kernel inputs use the Table 3 values; a nominal-power sensitivity is reported separately.
  - caveat: AMMT cooling rates: Table 3 footnote c says they 'should not be used' (motion blur / calibration range); they are stored flagged do-not-use. AMMT 1290-1000 C cooling rates are blank (footnote b). AMMT-100us case C emittance 0.519 is assumed (footnote a). The conclusions call all cooling rates exemplar, not reference data.
  - caveat: AMMT-100us and AMMT-20us tracks are different physical tracks made under nominally the same conditions (paper Fig. 7); CBM case A is described as near or at keyholing.
  - caveat: IN625 kernel properties come from lpbf_thermal_solver.SECONDARY_THERMOPHYSICAL_DB (provenance class 'legacy-estimated-secondary', absorptivity_IR 0.38 estimated), not from a measured property set.

## Regime screening rule

Screening classifier, not the papers' regime definition. Inputs: normalised enthalpy dH/h_s = eta*P / (rho*cp_s*max(50, T_liq-T0)*sqrt(pi*alpha_s*v*r^3)) (same form as lpbf_thermal_solver.py, flat-plate absorptivity_IR of the material authority, solid k/cp, r = d/2) and the dataset's own balling flag. balling == 1 -> 'balling-flagged' (Hofmann only); otherwise dH/h_s < 15 -> 'conduction', 15 <= dH/h_s < 30 -> 'transition', >= 30 -> 'keyhole'. Measured D/W is recorded next to the label but not used for it. Wave 2 rows (KU Leuven 316L/Ti-6Al-4V, Lane IN625) are classified by the same screening rule; the KU Leuven authors' own labels are kept verbatim in regime.publishedLabel and are not used for the statistics' regime split. Added datasets without a reported beam diameter (CMU) or with unresolved measured dimension units/operator (KU Leuven IN718 (ku-leuven-in718-2021)) are labeled unclassified and excluded from kernel predictions; no regime label is inferred for them.

Row counts per regime: all 1431, balling-flagged 216, conduction 141, keyhole 194, transition 206, unclassified-missing-process-input 626, unclassified-source-dimensions-unresolved 48

## Assumptions

- **hatch_um**: 100 (no dataset in this record has a hatch: single tracks; the hatch only enters the lack-of-fusion screen, not the width/depth/length extents)
- **layer_um**: t_powder 0 (bare plate) rows are passed with a nominal 30 um layer because the function requires a positive layer; width/depth/length do not depend on it (checked at 10/30/60 um)
- **preheat_C**: 20 C assumed for every dataset (no dataset in this record states a build-plate or substrate temperature in the files read)
- **absorptivity**: the repo's estimated absorptivity_IR (316L 0.42, Ti-6Al-4V 0.35; IN625 0.38 from the legacy-estimated secondary table, wave 2 Lane rows only), flat-plate
- **inclusionRule**: a row counts for statistics only when extentStatus == 'computed'
- **powderBedRayTracer**: calculate_meltpool_physics runs the optional GPU powder ray tracer only when absorption_model='powder-raytrace' is requested (tier-2 bump 2026-10-06); the default and this harness use the flat-plate absorptivity, so the ray tracer was not used; see `absorption`
- **wave2**: KU Leuven rows: beam diameter unverified: 37.5 um carried from the 2026-10-05 KU Leuven IN718 record ('Paper reports 37.5 um spot'); the article (doi:10.1016/j.jmatprotec.2022.117547) could not be read (HTTP 403), so diameter vs radius and the beam-size definition are not confirmed; layer left unset (not stated in the files read; the 2026-10-05 KU Leuven IN718 record cites a 60 um powder layer from the Coen article, which could not be read here (HTTP 403), so it is not carried over to these rows; kernels ignore it); 20 C preheat assumed. Lane rows: bare plate (layer 0, passed as the nominal layer), Table 3 power, D4sigma spot as the 1/e^2 diameter, 20 C preheat assumed, IN625 properties from the solver's legacy-estimated secondary table. No kernel parameter was changed for these rows; sensitivities are reported separately.
- **addedDatasetTreatment**: CMU ST has no power field; all CMU rows lack beam diameter. KU Leuven IN718 (ku-leuven-in718-2021) source dimensions retain unresolved units and width operator. These rows have no numeric regime classification or kernel predictions and are excluded from MAPE/statistics; source observations remain in rows with explicit extentStatus reasons. This applies to the IN718 file only: the wave 2 KU Leuven 316L/Ti-6Al-4V units were resolved from their raw '(1)' files (see the wave 2 catalog notes); the same raw-file check was not applied to the IN718 file in this record.

## Absorption path

Path: **flat-plate** (pinned: True). calculate_meltpool_physics(absorption_model='flat-plate'), the solver default on every machine since the 2026-10-06 tier-2 bump; sys.modules['powder_bed_raytracer'] = None is also set in the main process and in every worker so any ray-tracer import fails loudly.

Ray-tracer module present: True; importable in a separate probe process: False. Absorptivity by material: 316L 0.42, Ti-6Al-4V 0.35, Inconel 625 0.38. Flat-plate calls: 4206 of 4206 solver calls (by kernel, main run: rosenthal 838, eagar-tsai 838, goldak 838).

flat-plate absorptivity_IR; the GPU powder ray tracer was not used; with it the predictions change (reviewer stub: Eagar-Tsai hofmann-0001 171.0/119.6 -> 209.2/143.6 um at effective 0.65). flatPlateCalls counts the solver results that report processParameters.absorptionModel == 'flat-plate'; equal to solverCalls when every call took the flat-plate path (failed calls report none).

## Limits

- Kernels are compared on different included subsets (rows with extentStatus == 'computed'): pooled n = rosenthal 750 of 1431, eagar-tsai 757 of 1431, goldak 753 of 1431. Only summary.<kernel>.common (n = 750, the rows where all kernels are computed) is a like-for-like comparison; pooled and per-regime figures of different kernels are not.
- Rosenthal conduction statistics rest on 134 of 141 conduction rows: they are selected by the kernel's own output (only rows where Rosenthal resolves an extent without heuristic fallback, search-box limitation or the 0.55 x beam-diameter width floor are 'computed'), so they describe the rows it can resolve, not the regime.
- Eagar-Tsai and Goldak keyhole-regime depth statistics are identical (bias +0.4 %, MAPE 24.7 %) because both add the same Fabbro keyhole depth term; they are not independent evidence.
- The measurements carry no uncertainty model: the pooled-summary datasets (Hofmann 316L, Totis Ti-6Al-4V) provide no per-row measurement uncertainty; the wave 2 Lane IN625 rows carry Table 3 per-track sigma (measured.widthSigma_um / depthSigma_um, the spread of N = 3 microscopy measurements, not an uncertainty) and the statistics do not use it. The bootstrap intervals cover resampling of parameter sets only, not measurement error, the estimated material laws or the assumed absorptivity.
- Replicate rows are not independent: the Hofmann table has 677 rows but only 623 distinct parameter sets; the bootstrap intervals resample whole parameter sets (clusters), the point statistics weight every row.
- Balling-flagged rows (216) are inside the pooled 'all' headline statistics; a continuous-track screening kernel is not meant to describe them.
- The Totis depth reference line (original substrate surface vs powder surface) is not stated by the source; the 80 Totis depths carry an unknown offset.
- The kernels ignore powder-layer thickness (identical predictions at 0/30/60 um; see assumptions.layer_um), so any trend with powder-layer thickness is in the measurements only.
- Absorption path: flat-plate absorptivity_IR (316L 0.42, Ti-6Al-4V 0.35, Inconel 625 0.38); the GPU powder ray tracer was not used; with the ray tracer the predictions change.
- The reference-transient block depends on wall-clock budgets (total and per case): on a slower host rows can become 'not-run (budget)'. --reuse-reference copies the block of an earlier record instead.
- KU Leuven 316L/Ti-6Al-4V (58 condition means): the beam diameter is unverified: 37.5 um carried from the 2026-10-05 KU Leuven IN718 record ('Paper reports 37.5 um spot'); the article (doi:10.1016/j.jmatprotec.2022.117547) could not be read (HTTP 403), so diameter vs radius and the beam-size definition are not confirmed; the 75 um re-run in wave2.kuBeamDiameterSensitivity shows how much the statistics move with it. Rows are condition means of 7 to 16 sections; the bootstrap resamples conditions, not sections.
- Lane IN625 (23 tracks): AMMT kernel inputs use the Table 3 power (137.9/179.2 W). Fig. 2 caption: 'Laser power values indicated are the applied laser power'; Table 3 lists 137.9/179.2 W for the AMMT cases and the Section 2 case definitions give 150/195 W. Whether these are applied vs commanded powers is not stated explicitly, and the Fig. 2 image was not read. Status: UNRESOLVED. See wave2.laneNominalPowerSensitivity. IN625 properties are legacy estimates (absorptivity_IR 0.38).
- Wave 2 reference targets (NIST AMB2022-03 thermal Tables 2-3, Simonds 2018 Table III) have no like-for-like model comparison in the app; their comparison status is 'unavailable' with the reason recorded.
- The pooled summary, its limits above and the absorptivity sensitivity exclude the 81 wave 2 rows (KU Leuven 316L/Ti-6Al-4V, Lane IN625; see summaryScope), so the pooled headline keeps the 2026-10-05 scope and is comparable to it. Per-dataset wave 2 figures are in wave2.scorecard; they are not pooled across materials.

## Summary: kernel x regime (2026-10-05 dataset scope pooled; wave 2 rows excluded, see the wave 2 scorecard)

summary, limits and absorptivitySensitivity cover the 2026-10-05 dataset scope only, so the pooled headline is comparable to the 2026-10-05 record; wave 2 rows are scored per dataset in wave2.scorecard because their inputs include unverified (KU Leuven beam diameter) or legacy-estimated (IN625 properties) values. Pooled rows: 1431; excluded wave 2 rows: 81.

Bias = mean((pred-meas)/meas); rows with extentStatus other than `computed` are excluded and counted. Fractions: share of rows within +-30 % of the measurement / within the x0.5-2 band.

### Pooled (the `common` regime = rows where all kernels are computed)

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 750 | 681 | +11.9 | 29.5 | 58.3 | 60% / 98% | +52.1 | 57.7 | 66.3 | 43% / 84% |
| rosenthal | balling-flagged | 216 | 0 | +13.0 | 26.6 | 44.9 | 68% / 98% | +92.7 | 94.5 | 70.8 | 21% / 69% |
| rosenthal | conduction | 134 | 7 | -30.7 | 30.8 | 50.7 | 49% / 98% | +38.1 | 43.1 | 16.4 | 56% / 88% |
| rosenthal | keyhole | 194 | 0 | +47.6 | 47.6 | 89.3 | 26% / 98% | +27.5 | 39.6 | 95.7 | 53% / 92% |
| rosenthal | transition | 206 | 0 | +4.7 | 14.8 | 33.1 | 92% / 100% | +41.9 | 45.7 | 44.5 | 48% / 89% |
| rosenthal | unclassified-missing-process-input | 0 | 626 | - | - | - | - | - | - | - | - |
| rosenthal | unclassified-source-dimensions-unresolved | 0 | 48 | - | - | - | - | - | - | - | - |
| rosenthal | common | 750 | 681 | +11.9 | 29.5 | 58.3 | 60% / 98% | +52.1 | 57.7 | 66.3 | 43% / 84% |
| eagar-tsai | all | 757 | 674 | -4.0 | 11.6 | 24.3 | 95% / 100% | +17.5 | 36.8 | 53.9 | 61% / 91% |
| eagar-tsai | balling-flagged | 216 | 0 | -4.1 | 12.8 | 27.3 | 94% / 100% | +44.1 | 53.8 | 46.8 | 54% / 83% |
| eagar-tsai | conduction | 141 | 0 | -7.5 | 11.9 | 22.4 | 95% / 100% | +34.9 | 39.5 | 15.7 | 61% / 88% |
| eagar-tsai | keyhole | 194 | 0 | +3.4 | 11.0 | 24.3 | 95% / 100% | +0.4 | 24.7 | 82.8 | 67% / 98% |
| eagar-tsai | transition | 206 | 0 | -8.5 | 10.7 | 22.3 | 95% / 100% | -6.1 | 28.7 | 42.0 | 63% / 93% |
| eagar-tsai | unclassified-missing-process-input | 0 | 626 | - | - | - | - | - | - | - | - |
| eagar-tsai | unclassified-source-dimensions-unresolved | 0 | 48 | - | - | - | - | - | - | - | - |
| eagar-tsai | common | 750 | 681 | -4.0 | 11.6 | 24.4 | 95% / 100% | +17.5 | 36.9 | 54.2 | 61% / 91% |
| goldak | all | 753 | 678 | -10.9 | 16.1 | 32.7 | 86% / 100% | +24.9 | 42.1 | 54.3 | 56% / 90% |
| goldak | balling-flagged | 216 | 0 | -10.5 | 16.4 | 34.6 | 89% / 100% | +51.6 | 59.0 | 47.4 | 50% / 81% |
| goldak | conduction | 137 | 4 | -24.6 | 25.2 | 43.1 | 58% / 99% | +56.5 | 59.9 | 20.7 | 35% / 84% |
| goldak | keyhole | 194 | 0 | +1.0 | 11.2 | 24.7 | 96% / 100% | +0.4 | 24.7 | 82.8 | 67% / 98% |
| goldak | transition | 206 | 0 | -13.5 | 14.3 | 29.1 | 92% / 100% | -1.2 | 29.1 | 40.7 | 66% / 94% |
| goldak | unclassified-missing-process-input | 0 | 626 | - | - | - | - | - | - | - | - |
| goldak | unclassified-source-dimensions-unresolved | 0 | 48 | - | - | - | - | - | - | - | - |
| goldak | common | 750 | 681 | -10.8 | 16.0 | 32.5 | 86% / 100% | +24.8 | 42.1 | 54.4 | 56% / 89% |

### Cluster-bootstrap 95 % intervals (pooled summary cells)

Distinct parameter sets (dataset, power, speed, beam diameter, layer) resampled with replacement, 1000 replicates, `random.Random(0)`, percentile 2.5/97.5; replicates of one set stay together. The intervals cover this resampling only (no measurement uncertainty, no material-law uncertainty); they are in JSON `summary.<kernel>.<regime>.<width|depth>.{bias_pct_ci95, mape_pct_ci95, n_parameterSets}`.

| kernel | regime | n | parameter sets | W bias % CI95 | W MAPE % CI95 | D bias % CI95 | D MAPE % CI95 |
|---|---|---|---|---|---|---|---|
| rosenthal | all | 750 | 696 | [9.3, 14.5] | [28.0, 31.2] | [47.0, 57.3] | [53.1, 62.5] |
| rosenthal | balling-flagged | 216 | 215 | [8.9, 17.3] | [23.7, 29.5] | [81.0, 106.2] | [82.9, 107.8] |
| rosenthal | conduction | 134 | 121 | [-32.7, -28.7] | [28.9, 32.8] | [29.1, 47.9] | [34.7, 52.3] |
| rosenthal | keyhole | 194 | 185 | [44.3, 51.1] | [44.3, 51.1] | [20.9, 33.6] | [34.8, 44.4] |
| rosenthal | transition | 206 | 185 | [2.1, 7.2] | [13.4, 16.2] | [35.3, 48.7] | [39.5, 52.0] |
| rosenthal | common | 750 | 696 | [9.3, 14.5] | [28.0, 31.2] | [47.0, 57.3] | [53.1, 62.5] |
| eagar-tsai | all | 757 | 703 | [-5.0, -3.0] | [10.9, 12.3] | [13.2, 21.9] | [33.2, 40.8] |
| eagar-tsai | balling-flagged | 216 | 215 | [-6.2, -2.1] | [11.5, 14.2] | [33.8, 55.5] | [44.3, 64.5] |
| eagar-tsai | conduction | 141 | 128 | [-9.5, -5.5] | [10.5, 13.2] | [26.2, 44.1] | [31.4, 47.8] |
| eagar-tsai | keyhole | 194 | 185 | [1.5, 5.4] | [9.8, 12.2] | [-4.1, 4.8] | [22.0, 27.3] |
| eagar-tsai | transition | 206 | 185 | [-10.0, -7.0] | [9.6, 12.0] | [-11.3, -1.3] | [25.2, 32.3] |
| eagar-tsai | common | 750 | 696 | [-5.0, -3.0] | [11.0, 12.3] | [13.2, 21.9] | [33.6, 40.5] |
| goldak | all | 753 | 699 | [-12.2, -9.8] | [15.3, 16.9] | [20.4, 29.5] | [38.4, 46.2] |
| goldak | balling-flagged | 216 | 215 | [-12.8, -8.3] | [15.0, 17.9] | [41.2, 63.5] | [49.1, 70.3] |
| goldak | conduction | 137 | 124 | [-26.9, -22.5] | [23.2, 27.3] | [45.9, 67.4] | [49.8, 70.4] |
| goldak | keyhole | 194 | 185 | [-0.9, 3.1] | [10.1, 12.3] | [-4.1, 4.8] | [22.0, 27.3] |
| goldak | transition | 206 | 185 | [-15.0, -12.0] | [12.9, 15.6] | [-6.5, 4.0] | [25.4, 33.0] |
| goldak | common | 750 | 696 | [-12.0, -9.6] | [15.2, 16.9] | [20.1, 29.5] | [38.5, 45.9] |

### Dataset cmu-ti64-mt-2026

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 0 | 410 | - | - | - | - | - | - | - | - |
| rosenthal | unclassified-missing-process-input | 0 | 410 | - | - | - | - | - | - | - | - |
| eagar-tsai | all | 0 | 410 | - | - | - | - | - | - | - | - |
| eagar-tsai | unclassified-missing-process-input | 0 | 410 | - | - | - | - | - | - | - | - |
| goldak | all | 0 | 410 | - | - | - | - | - | - | - | - |
| goldak | unclassified-missing-process-input | 0 | 410 | - | - | - | - | - | - | - | - |

### Dataset cmu-ti64-st-2026

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 0 | 216 | - | - | - | - | - | - | - | - |
| rosenthal | unclassified-missing-process-input | 0 | 216 | - | - | - | - | - | - | - | - |
| eagar-tsai | all | 0 | 216 | - | - | - | - | - | - | - | - |
| eagar-tsai | unclassified-missing-process-input | 0 | 216 | - | - | - | - | - | - | - | - |
| goldak | all | 0 | 216 | - | - | - | - | - | - | - | - |
| goldak | unclassified-missing-process-input | 0 | 216 | - | - | - | - | - | - | - | - |

### Dataset hofmann-316l-2026

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 670 | 7 | +8.8 | 26.8 | 54.3 | 64% / 99% | +55.6 | 59.1 | 58.9 | 42% / 84% |
| rosenthal | balling-flagged | 216 | 0 | +13.0 | 26.6 | 44.9 | 68% / 98% | +92.7 | 94.5 | 70.8 | 21% / 69% |
| rosenthal | conduction | 126 | 7 | -30.1 | 30.3 | 51.7 | 51% / 98% | +34.7 | 37.9 | 15.5 | 59% / 92% |
| rosenthal | keyhole | 137 | 0 | +41.2 | 41.2 | 84.7 | 31% / 99% | +31.5 | 38.5 | 76.6 | 54% / 93% |
| rosenthal | transition | 191 | 0 | +6.4 | 14.6 | 33.6 | 93% / 100% | +44.6 | 47.7 | 46.0 | 46% / 88% |
| eagar-tsai | all | 677 | 0 | -4.2 | 10.7 | 24.0 | 97% / 100% | +20.4 | 36.9 | 46.5 | 62% / 91% |
| eagar-tsai | balling-flagged | 216 | 0 | -4.1 | 12.8 | 27.3 | 94% / 100% | +44.1 | 53.8 | 46.8 | 54% / 83% |
| eagar-tsai | conduction | 133 | 0 | -7.1 | 11.2 | 22.6 | 96% / 100% | +32.2 | 35.0 | 14.8 | 64% / 92% |
| eagar-tsai | keyhole | 137 | 0 | +2.0 | 9.2 | 23.2 | 98% / 100% | +5.5 | 24.0 | 66.6 | 71% / 99% |
| eagar-tsai | transition | 191 | 0 | -6.9 | 9.3 | 21.2 | 98% / 100% | -3.9 | 28.2 | 43.1 | 64% / 94% |
| goldak | all | 673 | 4 | -11.4 | 15.5 | 33.1 | 88% / 100% | +28.1 | 42.5 | 46.9 | 57% / 89% |
| goldak | balling-flagged | 216 | 0 | -10.5 | 16.4 | 34.6 | 89% / 100% | +51.6 | 59.0 | 47.4 | 50% / 81% |
| goldak | conduction | 129 | 4 | -24.0 | 24.6 | 43.9 | 61% / 98% | +52.9 | 54.5 | 20.4 | 37% / 88% |
| goldak | keyhole | 137 | 0 | -0.4 | 9.6 | 23.9 | 98% / 100% | +5.5 | 24.0 | 66.6 | 71% / 99% |
| goldak | transition | 191 | 0 | -11.8 | 12.7 | 28.2 | 96% / 100% | +1.2 | 29.0 | 41.9 | 68% / 94% |

### Dataset ku-leuven-316l-2021

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 44 | 0 | +57.7 | 57.7 | 93.0 | 11% / 98% | -8.4 | 44.0 | 218.9 | 25% / 82% |
| rosenthal | keyhole | 40 | 0 | +59.6 | 59.6 | 97.2 | 12% / 98% | -18.2 | 39.5 | 229.3 | 28% / 82% |
| rosenthal | transition | 4 | 0 | +38.9 | 38.9 | 27.9 | 0% / 100% | +88.8 | 88.8 | 36.0 | 0% / 75% |
| eagar-tsai | all | 44 | 0 | +12.2 | 16.7 | 30.4 | 80% / 100% | -12.9 | 29.0 | 158.4 | 43% / 100% |
| eagar-tsai | keyhole | 40 | 0 | +12.7 | 17.7 | 31.9 | 78% / 100% | -17.6 | 28.5 | 166.1 | 45% / 100% |
| eagar-tsai | transition | 4 | 0 | +7.0 | 7.0 | 5.9 | 100% / 100% | +33.5 | 33.5 | 16.3 | 25% / 100% |
| goldak | all | 44 | 0 | +11.0 | 16.1 | 29.9 | 82% / 100% | -12.9 | 29.0 | 158.4 | 43% / 100% |
| goldak | keyhole | 40 | 0 | +11.8 | 17.4 | 31.4 | 80% / 100% | -17.6 | 28.5 | 166.1 | 45% / 100% |
| goldak | transition | 4 | 0 | +3.3 | 3.6 | 4.0 | 100% / 100% | +33.5 | 33.5 | 16.3 | 25% / 100% |

### Dataset ku-leuven-in718-2021

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 0 | 48 | - | - | - | - | - | - | - | - |
| rosenthal | unclassified-source-dimensions-unresolved | 0 | 48 | - | - | - | - | - | - | - | - |
| eagar-tsai | all | 0 | 48 | - | - | - | - | - | - | - | - |
| eagar-tsai | unclassified-source-dimensions-unresolved | 0 | 48 | - | - | - | - | - | - | - | - |
| goldak | all | 0 | 48 | - | - | - | - | - | - | - | - |
| goldak | unclassified-source-dimensions-unresolved | 0 | 48 | - | - | - | - | - | - | - | - |

### Dataset ku-leuven-ti64-2021

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 14 | 0 | +37.0 | 37.0 | 39.5 | 29% / 100% | +66.8 | 69.0 | 41.2 | 36% / 50% |
| rosenthal | keyhole | 11 | 0 | +39.4 | 39.4 | 43.5 | 18% / 100% | +50.0 | 52.8 | 41.9 | 45% / 64% |
| rosenthal | transition | 3 | 0 | +28.1 | 28.1 | 19.2 | 67% / 100% | +128.3 | 128.3 | 38.5 | 0% / 0% |
| eagar-tsai | all | 14 | 0 | -7.8 | 8.4 | 9.1 | 100% / 100% | +21.2 | 28.6 | 22.2 | 57% / 100% |
| eagar-tsai | keyhole | 11 | 0 | -8.2 | 8.9 | 10.0 | 100% / 100% | +13.2 | 22.7 | 23.5 | 64% / 100% |
| eagar-tsai | transition | 3 | 0 | -6.5 | 6.5 | 4.4 | 100% / 100% | +50.6 | 50.6 | 16.6 | 33% / 100% |
| goldak | all | 14 | 0 | -10.6 | 11.0 | 11.1 | 100% / 100% | +21.2 | 28.6 | 22.2 | 57% / 100% |
| goldak | keyhole | 11 | 0 | -10.4 | 10.9 | 11.9 | 100% / 100% | +13.2 | 22.7 | 23.5 | 64% / 100% |
| goldak | transition | 3 | 0 | -11.1 | 11.1 | 7.5 | 100% / 100% | +50.6 | 50.6 | 16.6 | 33% / 100% |

### Dataset lane-in625-2020

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 18 | 5 | -18.6 | 18.6 | 26.8 | 100% / 100% | -6.3 | 28.0 | 27.6 | 67% / 100% |
| rosenthal | conduction | 12 | 5 | -22.6 | 22.6 | 30.8 | 100% / 100% | +5.2 | 27.2 | 13.9 | 67% / 100% |
| rosenthal | transition | 6 | 0 | -10.4 | 10.4 | 15.9 | 100% / 100% | -29.4 | 29.4 | 43.6 | 67% / 100% |
| eagar-tsai | all | 23 | 0 | +15.3 | 20.1 | 27.0 | 78% / 100% | -14.2 | 25.2 | 37.2 | 57% / 87% |
| eagar-tsai | conduction | 17 | 0 | +23.9 | 23.9 | 29.6 | 71% / 100% | -1.0 | 15.9 | 11.1 | 76% / 100% |
| eagar-tsai | transition | 6 | 0 | -9.1 | 9.1 | 17.6 | 100% / 100% | -51.7 | 51.7 | 70.4 | 0% / 50% |
| goldak | all | 18 | 5 | -16.1 | 16.1 | 24.3 | 100% / 100% | -2.0 | 39.1 | 39.7 | 22% / 89% |
| goldak | conduction | 12 | 5 | -15.1 | 15.1 | 21.7 | 100% / 100% | +20.2 | 35.5 | 15.8 | 33% / 100% |
| goldak | transition | 6 | 0 | -18.1 | 18.1 | 28.8 | 100% / 100% | -46.3 | 46.3 | 65.0 | 0% / 67% |

### Dataset totis-ti64-2021

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 80 | 0 | +38.0 | 52.2 | 85.1 | 26% / 94% | +23.2 | 46.2 | 110.7 | 51% / 84% |
| rosenthal | conduction | 8 | 0 | -39.2 | 39.2 | 30.5 | 12% / 88% | +91.8 | 124.8 | 26.6 | 12% / 25% |
| rosenthal | keyhole | 57 | 0 | +63.0 | 63.0 | 99.3 | 14% / 95% | +17.7 | 42.1 | 130.5 | 51% / 89% |
| rosenthal | transition | 15 | 0 | -15.7 | 17.8 | 24.8 | 80% / 93% | +7.6 | 19.8 | 14.1 | 73% / 93% |
| eagar-tsai | all | 80 | 0 | -2.2 | 18.7 | 27.3 | 80% / 100% | -7.1 | 36.5 | 95.9 | 51% / 89% |
| eagar-tsai | conduction | 8 | 0 | -14.9 | 22.9 | 17.7 | 75% / 100% | +80.0 | 112.9 | 26.4 | 12% / 25% |
| eagar-tsai | keyhole | 57 | 0 | +6.7 | 15.4 | 26.7 | 89% / 100% | -11.9 | 26.2 | 112.6 | 58% / 98% |
| eagar-tsai | transition | 15 | 0 | -29.2 | 29.2 | 33.3 | 47% / 100% | -35.2 | 35.2 | 22.6 | 47% / 87% |
| goldak | all | 80 | 0 | -6.9 | 20.6 | 29.3 | 74% / 99% | -2.9 | 39.1 | 95.9 | 50% / 90% |
| goldak | conduction | 8 | 0 | -34.2 | 34.2 | 27.2 | 12% / 100% | +114.8 | 145.6 | 25.9 | 0% / 25% |
| goldak | keyhole | 57 | 0 | +4.3 | 15.0 | 26.4 | 93% / 100% | -11.9 | 26.2 | 112.6 | 58% / 98% |
| goldak | transition | 15 | 0 | -34.8 | 34.8 | 39.0 | 33% / 93% | -31.2 | 31.2 | 21.1 | 47% / 93% |

### Hofmann, spot 50 um

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 175 | 0 | +31.0 | 34.5 | 51.9 | 51% / 98% | +57.5 | 63.0 | 60.0 | 46% / 83% |
| rosenthal | balling-flagged | 74 | 0 | +41.4 | 41.7 | 56.6 | 38% / 96% | +89.7 | 94.2 | 78.6 | 42% / 72% |
| rosenthal | conduction | 9 | 0 | -18.1 | 19.3 | 15.9 | 78% / 100% | +11.7 | 21.0 | 8.9 | 78% / 89% |
| rosenthal | keyhole | 51 | 0 | +44.0 | 44.0 | 65.7 | 29% / 100% | +28.3 | 37.0 | 53.5 | 51% / 96% |
| rosenthal | transition | 41 | 0 | +6.8 | 13.3 | 16.9 | 95% / 100% | +45.9 | 48.2 | 24.6 | 41% / 85% |
| eagar-tsai | all | 175 | 0 | +0.5 | 12.5 | 20.5 | 94% / 100% | +24.4 | 42.4 | 51.3 | 65% / 89% |
| eagar-tsai | balling-flagged | 74 | 0 | +2.9 | 15.1 | 25.3 | 89% / 100% | +53.7 | 67.1 | 64.3 | 58% / 77% |
| eagar-tsai | conduction | 9 | 0 | +1.7 | 11.4 | 9.1 | 89% / 100% | +15.6 | 24.3 | 9.0 | 78% / 89% |
| eagar-tsai | keyhole | 51 | 0 | +3.3 | 10.3 | 17.3 | 98% / 100% | +5.0 | 23.6 | 52.3 | 69% / 100% |
| eagar-tsai | transition | 41 | 0 | -7.5 | 11.0 | 15.5 | 98% / 100% | -2.5 | 25.1 | 18.2 | 68% / 95% |
| goldak | all | 175 | 0 | -2.8 | 13.2 | 21.1 | 94% / 100% | +26.1 | 43.1 | 51.3 | 66% / 89% |
| goldak | balling-flagged | 74 | 0 | +0.4 | 15.0 | 25.5 | 91% / 100% | +53.9 | 67.2 | 64.3 | 58% / 77% |
| goldak | conduction | 9 | 0 | -9.6 | 13.8 | 11.6 | 100% / 100% | +27.6 | 35.2 | 9.7 | 78% / 89% |
| goldak | keyhole | 51 | 0 | +1.2 | 10.4 | 17.1 | 98% / 100% | +5.0 | 23.6 | 52.3 | 69% / 100% |
| goldak | transition | 41 | 0 | -12.0 | 13.2 | 18.2 | 95% / 100% | +1.7 | 25.7 | 17.9 | 73% / 95% |

### Hofmann, spot 80 um

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 186 | 1 | +13.9 | 26.5 | 57.9 | 63% / 99% | +63.6 | 67.1 | 67.0 | 37% / 77% |
| rosenthal | balling-flagged | 59 | 0 | +12.8 | 18.1 | 32.5 | 86% / 100% | +117.6 | 118.2 | 82.7 | 5% / 51% |
| rosenthal | conduction | 25 | 1 | -29.9 | 29.9 | 35.5 | 52% / 96% | +32.3 | 35.5 | 10.3 | 60% / 96% |
| rosenthal | keyhole | 55 | 0 | +43.3 | 43.3 | 94.8 | 22% / 98% | +34.0 | 40.6 | 80.7 | 56% / 89% |
| rosenthal | transition | 47 | 0 | +4.4 | 15.6 | 27.5 | 87% / 100% | +47.1 | 50.9 | 39.1 | 40% / 87% |
| eagar-tsai | all | 187 | 0 | -3.8 | 10.3 | 24.1 | 96% / 100% | +21.6 | 37.2 | 49.2 | 62% / 91% |
| eagar-tsai | balling-flagged | 59 | 0 | -7.1 | 11.8 | 28.7 | 93% / 100% | +46.9 | 54.9 | 44.4 | 47% / 83% |
| eagar-tsai | conduction | 26 | 0 | -8.1 | 11.0 | 16.7 | 96% / 100% | +31.2 | 33.8 | 10.2 | 65% / 96% |
| eagar-tsai | keyhole | 55 | 0 | +3.4 | 9.0 | 25.7 | 96% / 100% | +7.3 | 25.7 | 71.1 | 73% / 96% |
| eagar-tsai | transition | 47 | 0 | -5.5 | 9.6 | 18.5 | 98% / 100% | +1.3 | 30.4 | 34.5 | 64% / 91% |
| goldak | all | 186 | 1 | -9.4 | 13.5 | 27.9 | 90% / 100% | +27.1 | 40.6 | 49.4 | 58% / 90% |
| goldak | balling-flagged | 59 | 0 | -12.3 | 14.3 | 32.6 | 88% / 100% | +51.7 | 57.2 | 44.5 | 42% / 83% |
| goldak | conduction | 25 | 1 | -23.3 | 23.7 | 29.5 | 68% / 100% | +50.7 | 51.7 | 13.9 | 48% / 92% |
| goldak | keyhole | 55 | 0 | +1.0 | 9.5 | 25.4 | 96% / 100% | +7.3 | 25.7 | 71.1 | 73% / 96% |
| goldak | transition | 47 | 0 | -10.8 | 12.0 | 23.2 | 96% / 100% | +6.7 | 31.4 | 33.5 | 66% / 89% |

### Hofmann, spot 110 um

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 161 | 0 | -1.2 | 22.3 | 50.5 | 75% / 99% | +57.0 | 58.9 | 58.8 | 40% / 86% |
| rosenthal | balling-flagged | 45 | 0 | -7.3 | 18.5 | 35.9 | 87% / 98% | +94.4 | 94.5 | 58.6 | 9% / 73% |
| rosenthal | conduction | 37 | 0 | -30.1 | 30.4 | 46.8 | 46% / 100% | +27.9 | 30.4 | 14.0 | 70% / 95% |
| rosenthal | keyhole | 24 | 0 | +33.2 | 33.2 | 89.6 | 50% / 100% | +33.4 | 38.1 | 92.2 | 54% / 96% |
| rosenthal | transition | 55 | 0 | +8.2 | 15.3 | 38.0 | 95% / 100% | +56.4 | 58.0 | 58.9 | 40% / 85% |
| eagar-tsai | all | 161 | 0 | -6.8 | 10.5 | 24.2 | 99% / 100% | +18.4 | 33.2 | 40.1 | 65% / 92% |
| eagar-tsai | balling-flagged | 45 | 0 | -8.2 | 12.6 | 27.4 | 100% / 100% | +40.7 | 48.0 | 26.6 | 56% / 82% |
| eagar-tsai | conduction | 37 | 0 | -6.7 | 11.7 | 20.4 | 100% / 100% | +26.1 | 28.4 | 13.8 | 70% / 95% |
| eagar-tsai | keyhole | 24 | 0 | -2.4 | 7.3 | 24.4 | 100% / 100% | +3.5 | 20.2 | 72.9 | 71% / 100% |
| eagar-tsai | transition | 55 | 0 | -7.7 | 9.3 | 23.7 | 98% / 100% | +1.5 | 30.1 | 40.9 | 67% / 95% |
| goldak | all | 161 | 0 | -15.5 | 16.7 | 34.8 | 86% / 100% | +28.7 | 41.0 | 40.6 | 58% / 91% |
| goldak | balling-flagged | 45 | 0 | -18.1 | 18.7 | 38.3 | 89% / 100% | +55.4 | 58.6 | 28.5 | 53% / 78% |
| goldak | conduction | 37 | 0 | -23.5 | 24.4 | 38.9 | 62% / 100% | +45.4 | 47.1 | 18.3 | 41% / 92% |
| goldak | keyhole | 24 | 0 | -5.1 | 8.5 | 27.4 | 100% / 100% | +3.5 | 20.2 | 72.9 | 71% / 100% |
| goldak | transition | 55 | 0 | -12.5 | 13.5 | 31.5 | 95% / 100% | +6.6 | 31.5 | 40.2 | 69% / 96% |

### Hofmann, spot 140 um

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 148 | 6 | -13.1 | 23.1 | 56.1 | 70% / 99% | +41.6 | 44.6 | 44.9 | 45% / 92% |
| rosenthal | balling-flagged | 38 | 0 | -17.7 | 20.0 | 45.4 | 74% / 100% | +58.0 | 58.6 | 41.8 | 21% / 89% |
| rosenthal | conduction | 55 | 6 | -32.2 | 32.2 | 63.5 | 49% / 98% | +44.1 | 46.9 | 18.9 | 47% / 89% |
| rosenthal | keyhole | 7 | 0 | +31.5 | 31.5 | 105.0 | 57% / 100% | +29.1 | 34.0 | 117.2 | 57% / 100% |
| rosenthal | transition | 48 | 0 | +5.8 | 13.8 | 43.2 | 94% / 100% | +27.7 | 32.4 | 49.4 | 60% / 96% |
| eagar-tsai | all | 154 | 0 | -7.4 | 9.6 | 27.1 | 98% / 100% | +16.6 | 33.9 | 43.6 | 58% / 93% |
| eagar-tsai | balling-flagged | 38 | 0 | -8.0 | 10.1 | 28.7 | 100% / 100% | +25.2 | 33.0 | 21.7 | 55% / 97% |
| eagar-tsai | conduction | 61 | 0 | -8.1 | 10.9 | 27.1 | 95% / 100% | +38.8 | 41.1 | 17.5 | 57% / 89% |
| eagar-tsai | keyhole | 7 | 0 | -3.6 | 8.9 | 33.4 | 100% / 100% | +1.2 | 27.1 | 94.2 | 71% / 100% |
| eagar-tsai | transition | 48 | 0 | -6.6 | 7.5 | 24.5 | 100% / 100% | -16.1 | 26.5 | 63.5 | 58% / 94% |
| goldak | all | 151 | 3 | -19.4 | 19.6 | 46.0 | 78% / 99% | +31.3 | 45.7 | 44.9 | 44% / 89% |
| goldak | balling-flagged | 38 | 0 | -19.9 | 19.9 | 46.2 | 87% / 100% | +42.4 | 46.4 | 26.3 | 45% / 87% |
| goldak | conduction | 58 | 3 | -26.9 | 26.9 | 54.1 | 52% / 97% | +62.5 | 63.5 | 24.7 | 24% / 83% |
| goldak | keyhole | 7 | 0 | -6.2 | 9.2 | 38.0 | 100% / 100% | +1.2 | 27.1 | 94.2 | 71% / 100% |
| goldak | transition | 48 | 0 | -11.8 | 12.0 | 34.8 | 100% / 100% | -10.9 | 26.4 | 61.2 | 62% / 96% |

**Powder-layer breakdowns below:** the kernels ignore powder-layer thickness (identical predictions at 0/30/60 um, see `assumptions.layer_um`), so any trend with powder-layer thickness in these tables is in the measurements only, not a kernel result.

### Hofmann, powder layer 0 um

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 204 | 6 | -1.2 | 26.7 | 49.5 | 57% / 100% | +48.1 | 48.5 | 54.4 | 45% / 88% |
| rosenthal | balling-flagged | 38 | 0 | +11.2 | 20.8 | 34.5 | 74% / 100% | +81.6 | 81.7 | 74.3 | 5% / 76% |
| rosenthal | conduction | 67 | 6 | -33.7 | 33.7 | 55.5 | 31% / 99% | +18.4 | 18.6 | 8.7 | 82% / 99% |
| rosenthal | keyhole | 41 | 0 | +36.6 | 36.6 | 68.7 | 34% / 100% | +47.7 | 49.2 | 77.8 | 46% / 83% |
| rosenthal | transition | 58 | 0 | +1.6 | 15.3 | 30.8 | 91% / 100% | +60.9 | 60.9 | 49.1 | 26% / 86% |
| eagar-tsai | all | 210 | 0 | -7.7 | 11.2 | 24.8 | 97% / 100% | +16.4 | 23.6 | 32.3 | 80% / 95% |
| eagar-tsai | balling-flagged | 38 | 0 | -10.6 | 13.3 | 28.6 | 95% / 100% | +29.8 | 37.5 | 46.1 | 63% / 87% |
| eagar-tsai | conduction | 73 | 0 | -9.2 | 11.8 | 24.3 | 97% / 100% | +15.3 | 15.6 | 7.5 | 89% / 99% |
| eagar-tsai | keyhole | 41 | 0 | -1.5 | 7.9 | 19.0 | 100% / 100% | +19.8 | 27.7 | 49.8 | 73% / 98% |
| eagar-tsai | transition | 58 | 0 | -8.2 | 11.2 | 26.3 | 95% / 100% | +6.6 | 21.5 | 23.5 | 84% / 95% |
| goldak | all | 206 | 4 | -16.9 | 18.5 | 37.9 | 77% / 99% | +25.4 | 30.6 | 33.3 | 66% / 95% |
| goldak | balling-flagged | 38 | 0 | -15.4 | 16.9 | 35.9 | 89% / 100% | +33.6 | 36.9 | 46.0 | 61% / 87% |
| goldak | conduction | 69 | 4 | -28.2 | 28.2 | 48.7 | 45% / 97% | +34.4 | 34.4 | 13.8 | 51% / 99% |
| goldak | keyhole | 41 | 0 | -3.6 | 8.8 | 21.4 | 100% / 100% | +19.8 | 27.7 | 49.8 | 73% / 98% |
| goldak | transition | 58 | 0 | -13.7 | 14.7 | 33.4 | 90% / 100% | +13.4 | 23.8 | 23.9 | 81% / 95% |

### Hofmann, powder layer 30 um

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 231 | 1 | +6.0 | 26.5 | 51.5 | 67% / 98% | +57.1 | 62.8 | 52.7 | 39% / 82% |
| rosenthal | balling-flagged | 91 | 0 | +8.2 | 28.9 | 49.2 | 67% / 96% | +84.7 | 87.3 | 64.4 | 25% / 69% |
| rosenthal | conduction | 43 | 1 | -28.3 | 28.5 | 49.2 | 63% / 98% | +65.1 | 69.8 | 20.5 | 21% / 81% |
| rosenthal | keyhole | 36 | 0 | +41.8 | 41.8 | 81.2 | 25% / 100% | +20.0 | 31.9 | 66.4 | 67% / 100% |
| rosenthal | transition | 61 | 0 | +5.9 | 12.3 | 28.8 | 95% / 100% | +32.2 | 39.7 | 37.6 | 54% / 92% |
| eagar-tsai | all | 232 | 0 | -3.9 | 11.7 | 25.1 | 96% / 100% | +24.1 | 44.4 | 48.0 | 48% / 87% |
| eagar-tsai | balling-flagged | 91 | 0 | -3.6 | 15.0 | 31.4 | 92% / 100% | +41.1 | 51.4 | 41.4 | 52% / 81% |
| eagar-tsai | conduction | 44 | 0 | -5.7 | 11.2 | 22.0 | 93% / 100% | +63.1 | 67.2 | 20.1 | 23% / 82% |
| eagar-tsai | keyhole | 36 | 0 | +2.6 | 8.2 | 18.1 | 100% / 100% | -5.6 | 24.3 | 75.4 | 58% / 100% |
| eagar-tsai | transition | 61 | 0 | -6.8 | 9.3 | 19.5 | 100% / 100% | -11.8 | 29.3 | 50.6 | 54% / 90% |
| goldak | all | 232 | 0 | -11.8 | 16.9 | 34.5 | 88% / 100% | +34.0 | 52.1 | 48.3 | 47% / 84% |
| goldak | balling-flagged | 91 | 0 | -11.8 | 20.4 | 40.4 | 81% / 100% | +51.4 | 59.8 | 42.3 | 47% / 79% |
| goldak | conduction | 44 | 0 | -21.8 | 22.6 | 40.7 | 73% / 100% | +87.4 | 89.9 | 26.5 | 14% / 73% |
| goldak | keyhole | 36 | 0 | +0.1 | 8.6 | 18.2 | 100% / 100% | -5.6 | 24.3 | 75.4 | 58% / 100% |
| goldak | transition | 61 | 0 | -11.7 | 12.7 | 26.6 | 100% / 100% | -7.2 | 29.7 | 48.5 | 62% / 90% |

### Hofmann, powder layer 60 um

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 235 | 0 | +20.1 | 27.4 | 60.5 | 68% / 100% | +60.5 | 64.5 | 67.7 | 43% / 83% |
| rosenthal | balling-flagged | 87 | 0 | +18.9 | 26.6 | 44.2 | 66% / 100% | +105.9 | 107.7 | 75.4 | 24% / 67% |
| rosenthal | conduction | 16 | 0 | -20.2 | 20.8 | 40.1 | 100% / 100% | +20.9 | 33.3 | 21.0 | 62% / 94% |
| rosenthal | keyhole | 60 | 0 | +43.9 | 43.9 | 96.0 | 33% / 98% | +27.4 | 35.1 | 81.4 | 52% / 97% |
| rosenthal | transition | 72 | 0 | +10.6 | 15.9 | 39.1 | 92% / 100% | +42.1 | 43.8 | 49.7 | 54% / 88% |
| eagar-tsai | all | 235 | 0 | -1.5 | 9.4 | 22.0 | 97% / 100% | +20.4 | 41.4 | 55.0 | 61% / 91% |
| eagar-tsai | balling-flagged | 87 | 0 | -1.7 | 10.3 | 21.4 | 97% / 100% | +53.6 | 63.4 | 52.0 | 53% / 84% |
| eagar-tsai | conduction | 16 | 0 | -1.2 | 8.1 | 15.3 | 100% / 100% | +24.5 | 35.1 | 21.3 | 62% / 88% |
| eagar-tsai | keyhole | 60 | 0 | +4.0 | 10.5 | 28.0 | 95% / 100% | +2.4 | 21.3 | 70.9 | 77% / 98% |
| eagar-tsai | transition | 72 | 0 | -5.8 | 7.7 | 17.7 | 100% / 100% | -5.5 | 32.7 | 48.1 | 57% / 96% |
| goldak | all | 235 | 0 | -6.2 | 11.6 | 26.5 | 97% / 100% | +24.8 | 43.5 | 55.0 | 60% / 90% |
| goldak | balling-flagged | 87 | 0 | -7.0 | 12.1 | 26.4 | 97% / 100% | +59.6 | 67.8 | 52.8 | 49% / 79% |
| goldak | conduction | 16 | 0 | -12.2 | 14.7 | 27.9 | 100% / 100% | +37.8 | 44.1 | 24.4 | 44% / 81% |
| goldak | keyhole | 60 | 0 | +1.6 | 10.8 | 28.2 | 95% / 100% | +2.4 | 21.3 | 70.9 | 77% / 98% |
| goldak | transition | 72 | 0 | -10.3 | 11.0 | 24.7 | 99% / 100% | -1.5 | 32.5 | 46.9 | 61% / 97% |

## Absorptivity sensitivity (SENSITIVITY, not a calibration)

SENSITIVITY, not a calibrated value: conduction-regime rows (regime assigned at the repo's default absorptivity), absorptivity_IR overridden uniformly via prop_overrides; the absorptivity actually acting in a physical track is unknown.

Conduction rows: 141.

| kernel | a=0.30 W MAPE % | a=0.40 W MAPE % | a=0.50 W MAPE % | a=0.60 W MAPE % | a=0.30 D MAPE % | a=0.40 D MAPE % | a=0.50 D MAPE % | a=0.60 D MAPE % | a=0.30 n | a=0.40 n | a=0.50 n | a=0.60 n |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | 42.2 | 32.0 | 22.3 | 17.2 | 30.0 | 40.1 | 67.7 | 108.5 | 122 | 132 | 139 | 141 |
| eagar-tsai | 18.8 | 12.4 | 10.0 | 11.5 | 27.5 | 36.9 | 56.5 | 74.8 | 141 | 141 | 141 | 141 |
| goldak | 36.8 | 26.4 | 18.5 | 14.5 | 35.9 | 57.3 | 77.0 | 96.1 | 123 | 134 | 139 | 141 |

Included row counts vary with assumed absorptivity: each column uses only rows where the kernel resolves an extent. These are different evaluation subsets; lower width error can accompany higher depth error. Sensitivity, not calibration.

## Wave 2 datasets (2026-10-06)

Wave 2 (2026-10-06): new open measured datasets run through the unchanged screening kernels; comparison, not validation. Per-dataset kernel x regime tables (regime = the repo's screening classifier) with cluster-bootstrap intervals:

### Wave 2 scorecard: ku-leuven-316l-2021

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 44 | 0 | +57.7 | 57.7 | 93.0 | 11% / 98% | -8.4 | 44.0 | 218.9 | 25% / 82% |
| rosenthal | keyhole | 40 | 0 | +59.6 | 59.6 | 97.2 | 12% / 98% | -18.2 | 39.5 | 229.3 | 28% / 82% |
| rosenthal | transition | 4 | 0 | +38.9 | 38.9 | 27.9 | 0% / 100% | +88.8 | 88.8 | 36.0 | 0% / 75% |
| rosenthal | common | 44 | 0 | +57.7 | 57.7 | 93.0 | 11% / 98% | -8.4 | 44.0 | 218.9 | 25% / 82% |
| eagar-tsai | all | 44 | 0 | +12.2 | 16.7 | 30.4 | 80% / 100% | -12.9 | 29.0 | 158.4 | 43% / 100% |
| eagar-tsai | keyhole | 40 | 0 | +12.7 | 17.7 | 31.9 | 78% / 100% | -17.6 | 28.5 | 166.1 | 45% / 100% |
| eagar-tsai | transition | 4 | 0 | +7.0 | 7.0 | 5.9 | 100% / 100% | +33.5 | 33.5 | 16.3 | 25% / 100% |
| eagar-tsai | common | 44 | 0 | +12.2 | 16.7 | 30.4 | 80% / 100% | -12.9 | 29.0 | 158.4 | 43% / 100% |
| goldak | all | 44 | 0 | +11.0 | 16.1 | 29.9 | 82% / 100% | -12.9 | 29.0 | 158.4 | 43% / 100% |
| goldak | keyhole | 40 | 0 | +11.8 | 17.4 | 31.4 | 80% / 100% | -17.6 | 28.5 | 166.1 | 45% / 100% |
| goldak | transition | 4 | 0 | +3.3 | 3.6 | 4.0 | 100% / 100% | +33.5 | 33.5 | 16.3 | 25% / 100% |
| goldak | common | 44 | 0 | +11.0 | 16.1 | 29.9 | 82% / 100% | -12.9 | 29.0 | 158.4 | 43% / 100% |

| kernel | regime | n | parameter sets | W bias % CI95 | W MAPE % CI95 | D bias % CI95 | D MAPE % CI95 |
|---|---|---|---|---|---|---|---|
| rosenthal | all | 44 | 44 | [50.7, 64.5] | [50.7, 64.5] | [-22.7, 8.2] | [36.8, 51.8] |
| rosenthal | keyhole | 40 | 40 | [51.9, 67.0] | [51.9, 67.0] | [-30.5, -4.4] | [33.9, 46.0] |
| rosenthal | transition | 4 | 4 | [34.0, 46.1] | [34.0, 46.1] | [66.3, 121.2] | [66.3, 121.2] |
| rosenthal | common | 44 | 44 | [50.7, 64.5] | [50.7, 64.5] | [-22.7, 8.2] | [36.8, 51.8] |
| eagar-tsai | all | 44 | 44 | [7.6, 16.8] | [13.4, 20.1] | [-21.5, -3.5] | [24.9, 33.0] |
| eagar-tsai | keyhole | 40 | 40 | [7.4, 17.8] | [14.0, 21.0] | [-25.3, -9.1] | [24.7, 32.4] |
| eagar-tsai | transition | 4 | 4 | [3.2, 14.2] | [3.2, 14.2] | [15.0, 50.0] | [15.0, 50.0] |
| eagar-tsai | common | 44 | 44 | [7.6, 16.8] | [13.4, 20.1] | [-21.5, -3.5] | [24.9, 33.0] |
| goldak | all | 44 | 44 | [6.3, 15.7] | [12.8, 19.5] | [-21.5, -3.5] | [24.9, 33.0] |
| goldak | keyhole | 40 | 40 | [6.2, 16.9] | [13.9, 20.6] | [-25.3, -9.1] | [24.7, 32.4] |
| goldak | transition | 4 | 4 | [-0.3, 9.9] | [0.3, 9.9] | [15.0, 50.0] | [15.0, 50.0] |
| goldak | common | 44 | 44 | [6.3, 15.7] | [12.8, 19.5] | [-21.5, -3.5] | [24.9, 33.0] |

### Wave 2 scorecard: ku-leuven-ti64-2021

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 14 | 0 | +37.0 | 37.0 | 39.5 | 29% / 100% | +66.8 | 69.0 | 41.2 | 36% / 50% |
| rosenthal | keyhole | 11 | 0 | +39.4 | 39.4 | 43.5 | 18% / 100% | +50.0 | 52.8 | 41.9 | 45% / 64% |
| rosenthal | transition | 3 | 0 | +28.1 | 28.1 | 19.2 | 67% / 100% | +128.3 | 128.3 | 38.5 | 0% / 0% |
| rosenthal | common | 14 | 0 | +37.0 | 37.0 | 39.5 | 29% / 100% | +66.8 | 69.0 | 41.2 | 36% / 50% |
| eagar-tsai | all | 14 | 0 | -7.8 | 8.4 | 9.1 | 100% / 100% | +21.2 | 28.6 | 22.2 | 57% / 100% |
| eagar-tsai | keyhole | 11 | 0 | -8.2 | 8.9 | 10.0 | 100% / 100% | +13.2 | 22.7 | 23.5 | 64% / 100% |
| eagar-tsai | transition | 3 | 0 | -6.5 | 6.5 | 4.4 | 100% / 100% | +50.6 | 50.6 | 16.6 | 33% / 100% |
| eagar-tsai | common | 14 | 0 | -7.8 | 8.4 | 9.1 | 100% / 100% | +21.2 | 28.6 | 22.2 | 57% / 100% |
| goldak | all | 14 | 0 | -10.6 | 11.0 | 11.1 | 100% / 100% | +21.2 | 28.6 | 22.2 | 57% / 100% |
| goldak | keyhole | 11 | 0 | -10.4 | 10.9 | 11.9 | 100% / 100% | +13.2 | 22.7 | 23.5 | 64% / 100% |
| goldak | transition | 3 | 0 | -11.1 | 11.1 | 7.5 | 100% / 100% | +50.6 | 50.6 | 16.6 | 33% / 100% |
| goldak | common | 14 | 0 | -10.6 | 11.0 | 11.1 | 100% / 100% | +21.2 | 28.6 | 22.2 | 57% / 100% |

| kernel | regime | n | parameter sets | W bias % CI95 | W MAPE % CI95 | D bias % CI95 | D MAPE % CI95 |
|---|---|---|---|---|---|---|---|
| rosenthal | all | 14 | 14 | [31.8, 43.0] | [31.8, 43.0] | [38.0, 93.7] | [41.5, 94.8] |
| rosenthal | keyhole | 11 | 11 | [33.3, 46.2] | [33.3, 46.2] | [22.2, 77.5] | [27.3, 78.6] |
| rosenthal | transition | 3 | 3 | [23.7, 32.3] | [23.7, 32.3] | [102.2, 163.4] | [102.2, 163.4] |
| rosenthal | common | 14 | 14 | [31.8, 43.0] | [31.8, 43.0] | [38.0, 93.7] | [41.5, 94.8] |
| eagar-tsai | all | 14 | 14 | [-10.7, -4.9] | [6.2, 10.7] | [5.1, 37.0] | [16.7, 40.8] |
| eagar-tsai | keyhole | 11 | 11 | [-11.4, -4.5] | [6.3, 11.7] | [-2.7, 29.5] | [10.7, 34.4] |
| eagar-tsai | transition | 3 | 3 | [-7.6, -5.6] | [5.6, 7.6] | [18.6, 72.2] | [18.6, 72.2] |
| eagar-tsai | common | 14 | 14 | [-10.7, -4.9] | [6.2, 10.7] | [5.1, 37.0] | [16.7, 40.8] |
| goldak | all | 14 | 14 | [-13.4, -7.4] | [8.5, 13.5] | [5.1, 37.0] | [16.7, 40.8] |
| goldak | keyhole | 11 | 11 | [-13.9, -6.5] | [7.8, 14.0] | [-2.7, 29.5] | [10.7, 34.4] |
| goldak | transition | 3 | 3 | [-12.7, -9.9] | [9.9, 12.7] | [18.6, 72.2] | [18.6, 72.2] |
| goldak | common | 14 | 14 | [-13.4, -7.4] | [8.5, 13.5] | [5.1, 37.0] | [16.7, 40.8] |

### Wave 2 scorecard: lane-in625-2020

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 18 | 5 | -18.6 | 18.6 | 26.8 | 100% / 100% | -6.3 | 28.0 | 27.6 | 67% / 100% |
| rosenthal | conduction | 12 | 5 | -22.6 | 22.6 | 30.8 | 100% / 100% | +5.2 | 27.2 | 13.9 | 67% / 100% |
| rosenthal | transition | 6 | 0 | -10.4 | 10.4 | 15.9 | 100% / 100% | -29.4 | 29.4 | 43.6 | 67% / 100% |
| rosenthal | common | 18 | 5 | -18.6 | 18.6 | 26.8 | 100% / 100% | -6.3 | 28.0 | 27.6 | 67% / 100% |
| eagar-tsai | all | 23 | 0 | +15.3 | 20.1 | 27.0 | 78% / 100% | -14.2 | 25.2 | 37.2 | 57% / 87% |
| eagar-tsai | conduction | 17 | 0 | +23.9 | 23.9 | 29.6 | 71% / 100% | -1.0 | 15.9 | 11.1 | 76% / 100% |
| eagar-tsai | transition | 6 | 0 | -9.1 | 9.1 | 17.6 | 100% / 100% | -51.7 | 51.7 | 70.4 | 0% / 50% |
| eagar-tsai | common | 18 | 5 | +9.7 | 15.8 | 23.0 | 94% / 100% | -18.0 | 31.8 | 42.0 | 44% / 83% |
| goldak | all | 18 | 5 | -16.1 | 16.1 | 24.3 | 100% / 100% | -2.0 | 39.1 | 39.7 | 22% / 89% |
| goldak | conduction | 12 | 5 | -15.1 | 15.1 | 21.7 | 100% / 100% | +20.2 | 35.5 | 15.8 | 33% / 100% |
| goldak | transition | 6 | 0 | -18.1 | 18.1 | 28.8 | 100% / 100% | -46.3 | 46.3 | 65.0 | 0% / 67% |
| goldak | common | 18 | 5 | -16.1 | 16.1 | 24.3 | 100% / 100% | -2.0 | 39.1 | 39.7 | 22% / 89% |

| kernel | regime | n | parameter sets | W bias % CI95 | W MAPE % CI95 | D bias % CI95 | D MAPE % CI95 |
|---|---|---|---|---|---|---|---|
| rosenthal | all | 18 | 5 | [-23.8, -12.0] | [12.0, 23.8] | [-31.8, 16.9] | [23.8, 32.4] |
| rosenthal | conduction | 12 | 3 | [-26.0, -16.7] | [16.7, 26.0] | [-33.0, 24.7] | [24.0, 33.0] |
| rosenthal | transition | 6 | 2 | [-11.1, -9.8] | [9.8, 11.1] | [-35.8, -23.1] | [23.1, 35.8] |
| rosenthal | common | 18 | 5 | [-23.8, -12.0] | [12.0, 23.8] | [-31.8, 16.9] | [23.8, 32.4] |
| eagar-tsai | all | 23 | 6 | [0.5, 26.9] | [11.5, 28.6] | [-37.8, 5.9] | [10.8, 42.0] |
| eagar-tsai | conduction | 17 | 4 | [15.0, 31.8] | [15.0, 31.8] | [-23.3, 18.0] | [5.5, 28.5] |
| eagar-tsai | transition | 6 | 2 | [-14.1, -4.2] | [4.2, 14.1] | [-58.2, -45.1] | [45.1, 58.2] |
| eagar-tsai | common | 18 | 5 | [-4.9, 20.0] | [9.3, 22.5] | [-47.4, 7.5] | [17.3, 47.4] |
| goldak | all | 18 | 5 | [-19.6, -11.7] | [11.7, 19.6] | [-40.5, 30.0] | [30.0, 47.9] |
| goldak | conduction | 12 | 3 | [-20.3, -7.8] | [7.8, 20.3] | [-23.1, 44.6] | [23.1, 44.6] |
| goldak | transition | 6 | 2 | [-20.3, -15.9] | [15.9, 20.3] | [-54.5, -38.1] | [38.1, 54.5] |
| goldak | common | 18 | 5 | [-19.6, -11.7] | [11.7, 19.6] | [-40.5, 30.0] | [30.0, 47.9] |

### SENSITIVITY on an unresolved input, not a fit: KU Leuven rows re-run with beam diameter 75 um (the 37.5 um value read as a radius)

### ku-leuven-316l-2021 at beam diameter 75 um

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 44 | 0 | +44.4 | 49.8 | 90.0 | 34% / 98% | -45.0 | 45.2 | 254.0 | 18% / 61% |
| rosenthal | conduction | 8 | 0 | -11.3 | 11.5 | 13.4 | 100% / 100% | -34.6 | 35.4 | 38.2 | 50% / 75% |
| rosenthal | keyhole | 25 | 0 | +72.4 | 72.4 | 116.0 | 0% / 96% | -50.6 | 50.6 | 329.9 | 4% / 48% |
| rosenthal | transition | 11 | 0 | +21.1 | 26.4 | 41.0 | 64% / 100% | -39.9 | 39.9 | 98.8 | 27% / 82% |
| rosenthal | common | 44 | 0 | +44.4 | 49.8 | 90.0 | 34% / 98% | -45.0 | 45.2 | 254.0 | 18% / 61% |
| eagar-tsai | all | 44 | 0 | +16.2 | 19.2 | 32.5 | 77% / 100% | -55.3 | 55.3 | 286.4 | 9% / 18% |
| eagar-tsai | conduction | 8 | 0 | +13.6 | 14.7 | 13.2 | 88% / 100% | -34.3 | 34.3 | 37.1 | 50% / 75% |
| eagar-tsai | keyhole | 25 | 0 | +24.2 | 24.2 | 41.2 | 64% / 100% | -59.8 | 59.8 | 368.5 | 0% / 4% |
| eagar-tsai | transition | 11 | 0 | -0.3 | 10.9 | 15.6 | 100% / 100% | -60.5 | 60.5 | 136.2 | 0% / 9% |
| eagar-tsai | common | 44 | 0 | +16.2 | 19.2 | 32.5 | 77% / 100% | -55.3 | 55.3 | 286.4 | 9% / 18% |
| goldak | all | 44 | 0 | +10.5 | 16.3 | 30.0 | 82% / 100% | -53.3 | 54.1 | 286.3 | 11% / 20% |
| goldak | conduction | 8 | 0 | -2.5 | 6.7 | 7.3 | 100% / 100% | -25.4 | 29.7 | 34.1 | 62% / 75% |
| goldak | keyhole | 25 | 0 | +21.5 | 21.5 | 37.8 | 68% / 100% | -59.8 | 59.8 | 368.5 | 0% / 4% |
| goldak | transition | 11 | 0 | -5.1 | 11.3 | 17.7 | 100% / 100% | -58.9 | 58.9 | 135.2 | 0% / 18% |
| goldak | common | 44 | 0 | +10.5 | 16.3 | 30.0 | 82% / 100% | -53.3 | 54.1 | 286.3 | 11% / 20% |

### ku-leuven-ti64-2021 at beam diameter 75 um

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 14 | 0 | +0.2 | 22.1 | 25.6 | 93% / 100% | -30.9 | 31.1 | 46.6 | 29% / 93% |
| rosenthal | conduction | 7 | 0 | -21.9 | 21.9 | 19.0 | 100% / 100% | -29.7 | 30.1 | 28.1 | 43% / 86% |
| rosenthal | transition | 7 | 0 | +22.3 | 22.3 | 30.8 | 86% / 100% | -32.1 | 32.1 | 59.6 | 14% / 100% |
| rosenthal | common | 14 | 0 | +0.2 | 22.1 | 25.6 | 93% / 100% | -30.9 | 31.1 | 46.6 | 29% / 93% |
| eagar-tsai | all | 14 | 0 | +3.9 | 7.6 | 7.5 | 100% / 100% | -47.4 | 47.4 | 72.5 | 21% / 50% |
| eagar-tsai | conduction | 7 | 0 | +7.0 | 10.8 | 9.0 | 100% / 100% | -33.6 | 33.6 | 28.4 | 43% / 86% |
| eagar-tsai | transition | 7 | 0 | +0.9 | 4.3 | 5.6 | 100% / 100% | -61.3 | 61.3 | 98.5 | 0% / 14% |
| eagar-tsai | common | 14 | 0 | +3.9 | 7.6 | 7.5 | 100% / 100% | -47.4 | 47.4 | 72.5 | 21% / 50% |
| goldak | all | 14 | 0 | -11.8 | 12.1 | 12.1 | 100% / 100% | -39.7 | 41.5 | 70.4 | 36% / 50% |
| goldak | conduction | 7 | 0 | -15.8 | 15.8 | 14.0 | 100% / 100% | -21.3 | 25.0 | 25.2 | 71% / 86% |
| goldak | transition | 7 | 0 | -7.8 | 8.5 | 9.8 | 100% / 100% | -58.1 | 58.1 | 96.3 | 0% / 14% |
| goldak | common | 14 | 0 | -11.8 | 12.1 | 12.1 | 100% / 100% | -39.7 | 41.5 | 70.4 | 36% / 50% |

### SENSITIVITY on an unresolved input, not a fit: Lane AMMT rows re-run at the nominal case power from the paper text (150 W case A, 195 W cases B/C) instead of the Table 3 power (137.9/179.2 W)

### Lane AMMT at nominal power (13 rows)

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 8 | 5 | -21.5 | 21.5 | 30.2 | 100% / 100% | +31.4 | 31.4 | 12.4 | 25% / 100% |
| rosenthal | conduction | 8 | 5 | -21.5 | 21.5 | 30.2 | 100% / 100% | +31.4 | 31.4 | 12.4 | 25% / 100% |
| rosenthal | common | 8 | 5 | -21.5 | 21.5 | 30.2 | 100% / 100% | +31.4 | 31.4 | 12.4 | 25% / 100% |
| eagar-tsai | all | 13 | 0 | +30.5 | 30.5 | 37.4 | 46% / 100% | +17.2 | 17.2 | 7.8 | 92% / 100% |
| eagar-tsai | conduction | 13 | 0 | +30.5 | 30.5 | 37.4 | 46% / 100% | +17.2 | 17.2 | 7.8 | 92% / 100% |
| eagar-tsai | common | 8 | 5 | +24.6 | 24.6 | 33.7 | 75% / 100% | +23.4 | 23.4 | 9.8 | 88% / 100% |
| goldak | all | 8 | 5 | -13.3 | 13.3 | 18.9 | 100% / 100% | +51.2 | 51.2 | 20.4 | 0% / 100% |
| goldak | conduction | 8 | 5 | -13.3 | 13.3 | 18.9 | 100% / 100% | +51.2 | 51.2 | 20.4 | 0% / 100% |
| goldak | common | 8 | 5 | -13.3 | 13.3 | 18.9 | 100% / 100% | +51.2 | 51.2 | 20.4 | 0% / 100% |

Sensitivity re-runs: 213 solver calls, 213 flat-plate calls (solver calls of the two wave 2 sensitivity re-runs, not included in absorption.solverCalls; flatPlateCalls counts those calls whose result reports absorptionModel 'flat-plate').

### KU Leuven published regime label vs screening classifier

rows: KU Leuven authors' published label; columns: the repo's screening classifier at the primary inputs. Counts only; the published label is not a measured regime boundary.

| published / screening | keyhole | transition |
|---|---|---|
| conduction | 2 | 7 |
| keyhole | 41 | 0 |
| transition | 8 | 0 |

### Lane 2020 Table 4 class summary (published, transcribed)

| class | width um (N, Umean) | depth um (N, Umean) | length um (N, Umean) | cooling rate 1290-1190 C/s (N, Umean) | cooling-rate use |
|---|---|---|---|---|---|
| AMMT-A | 148 (9, 1.07) | 42 (9, 0.49) | 300 (19, 0.50) | 1.16E+06 (19, 6.15E+04) | do-not-use (same AMMT-20us values as Table 3, footnote c) |
| AMMT-B | 123 (9, 1.87) | 36 (9, 0.56) | 359 (10, 3.69) | 1.08E+06 (10, 1.86E+05) | do-not-use (same AMMT-20us values as Table 3, footnote c) |
| AMMT-C | 106 (12, 0.37) | 30 (12, 0.16) | 370 (7, 7.72) | 1.90E+06 (7, 2.09E+05) | do-not-use (same AMMT-20us values as Table 3, footnote c) |
| CBM-A | 171 (9, 0.82) | 151 (9, 5.75) | 659 (129, 0.47) | 6.20E+05 (129, 6.16E+03) | exemplar, not reference (paper conclusions) |
| CBM-B | 133 (9, 0.50) | 91 (9, 0.52) | 780 (59, 0.50) | 9.35E+05 (59, 1.82E+04) | exemplar, not reference (paper conclusions) |
| CBM-C | 100 (12, 0.48) | 60 (12, 0.16) | 754 (52, 0.68) | 1.28E+06 (52, 5.29E+04) | exemplar, not reference (paper conclusions) |

Umean is the standard uncertainty of the mean as labelled in Table 4 (Tables 5-7 give the uncertainty budgets for length, width and depth). Per the Table 4 caption, AMMT length and cooling rate come from the AMMT-20 us tracks only, so the AMMT class cooling rates are the same AMMT-20 us values that Table 3 footnote c says should not be used; they are flagged do-not-use. The paper calls all cooling rates exemplar, not reference data.

### Reference target: nist-amb2022-03-thermal-2022 (thermal targets (IN718 single tracks))

NIST AM-Bench, 'AMB2022-03 Benchmark Measurements and Challenge Results' (Measurement and Result Descriptions v1.0, 2022): Table 1 (process cases), Table 2 (TTAM, TSCR, TLCR), Table 3 (TTCR, supplementary), page 2 and 4. Evidence kind: published measurement (thermography-derived, table transcription). Source sha256 `dea3feddec2bc23281ae86c6fd9cee4d0a934a4304501fe0c038f24c7dbc9db0` (1195056 B, retrieved 2026-10-06); committed table sha256 `296b526f49fd484cb482c9f3db733ecd62283ad50eb6e529750a0b30f2f81426`.

| case | power_W | speed_mm_s | d4sigma_um | TTAM_ms | TSCR_C_s | TLCR_C_s | TTCR_C_s |
|---|---|---|---|---|---|---|---|
| 0 | 285 | 960 | 67 | 1.22 | 699000 | 414000 | 193000 |
| 1.1 | 285 | 960 | 49 | 1.3 | 732000 | 406000 | 138000 |
| 1.2 | 285 | 960 | 82 | 1.04 | 511000 | 365000 | 193000 |
| 2.1 | 285 | 1200 | 67 | 0.896 | 785000 | 506000 | 301000 |
| 2.2 | 285 | 800 | 67 | 1.59 | 611000 | 325000 | 146000 |
| 3.1 | 325 | 960 | 67 | 1.38 | 705000 | 381000 | 157000 |
| 3.2 | 245 | 960 | 67 | 1.03 | 749000 | 433000 | 232000 |

- caveat: Thermography of bare IN718 single tracks; each value is the mean of three tracks over 30 centerline pixels at a nominally steady-state location (page 2).
- caveat: Processing assumptions stated on page 2: no undercooling, and emissivity set so the apparent solidification inflection equals the IN718 solidus/liquidus midpoint. The TTAM challenge definition on page 1 gives that midpoint as 'assumed to be 1298 C'; the explicit 'Ttrans = 1298 C' with emissivity 0.5 on page 7 belongs to the pad PTAM/PSCR processing. Page 3 notes the measurement error in TAM and SCR may be greatest at the largest spot size (case 1.2).
- caveat: TTCR is listed as supplementary data 'for reference', not a challenge quantity (Table 3); its definition is in the separate challenge-description document, which was not transcribed here.
- caveat: Same seven cases as the IN718 optical width/depth record already in the app (NIST mds2-2718 / AMB2022-03 Table 4); process parameters agree with lpbf_nist_in718_comparison.CASE_PROCESS.

**Comparison: unavailable.** No like-for-like model comparison exists in the app for these quantities. The screening kernels report solidificationKinetics.coolingRate_K_s as G x R at their solidification-front points, not the surface centerline cooling rate just below the solidus (TSCR) or above the liquidus (TLCR), and no reviewed operator converts a kernel melt-pool length into a time above 1298 C at the surface centerline (TTAM). Adding such an operator is a model change that needs its own review; nothing was computed here.

### Reference target: simonds-316l-2018 (absorptance targets (316L stationary spot welds))

B. J. Simonds et al., 'Time-Resolved Absorptance and Melt Pool Dynamics during Intense Laser Irradiation of a Metal', Phys. Rev. Applied 10, 044061 (2018), doi:10.1103/PhysRevApplied.10.044061, PMC7047776, Table III (integrating-sphere optical results). Evidence kind: published measurement (table transcription). Source sha256 `aaf9a603e57e95d37c7db39cbceda30cef7a6edf78f5b8626628aa68f95e86f8` (127169 B, retrieved 2026-10-06); committed table sha256 `e5fbaeb037371935c167d3e0e1740a348427313c886f7aab2ee439ee3c789db0`.

| E_in_J | avg_irradiance_MW_cm2 | W_weld_um | L_weld_um | E_abs_J | eta_coupling | time_to_melt_ms | time_to_keyhole_ms |
|---|---|---|---|---|---|---|---|
| 1.2 | 0.17 | 304 | 156 | 0.378 | 0.31 | 0.6 | - |
| 2.05 | 0.29 | 335 | 232 | 0.64 | 0.31 | 0.25 | - |
| 2.92 | 0.412 | 346 | 310 | 1.02 | 0.35 | 0.11 | 2.1 |
| 3.1 | 0.439 | 418 | 343 | 1.55 | 0.5 | 0.068 | 1.5 |
| 3.27 | 0.462 | 468 | 374 | 1.794 | 0.55 | 0.036 | 0.91 |
| 3.45 | 0.489 | 556 | 417 | 2.209 | 0.64 | 0.064 | 0.57 |
| 3.61 | 0.511 | 633 | 472 | 2.535 | 0.7 | 0.064 | 0.52 |
| 3.78 | 0.535 | 631 | 495 | 2.62 | 0.69 | 0.024 | 0.46 |
| 4.63 | 0.655 | 786 | 679 | 3.58 | 0.77 | 0.044 | 0.32 |
| 6.26 | 0.889 | 836 | 996 | 5.37 | 0.86 | 0.024 | 0.14 |

- caveat: Stationary 10 ms laser spot welds (1070 nm, 303 um top-hat, full width at 1/e^2), polished SRM 1155a disc (RMS roughness 79 +- 20 nm), no powder, no scanning: not a scan-track coupling value.
- caveat: eta_coupling is the average coupling efficiency over the weld (E_abs / E_in) from the integrating sphere; time-to-keyhole is defined in the paper as the time absorptance reaches 0.40 after the initial rise; '-' (no keyhole reached) is stored as blank.
- caveat: The Table III caption names W_weld width and L_weld 'length' without defining the direction; keyhole rows have L > W, so L may be a penetration length. It is stored but not used.
- caveat: Power-meter uncertainty 3 % (stated); per-row uncertainties are not in Table III.

**Comparison: unavailable.** The app has no stationary-spot (non-scanning) absorptance model: the kernels take a moving source and a constant flat-plate absorptivity_IR (316L 0.42, estimated), so there is no like-for-like prediction of a 10 ms, 303 um top-hat spot's average coupling efficiency. Not computed.

## Reference transient (bare plate, low power)

This block depends on wall-clock budgets (total and per case): on a slower or busier host cases can turn into 'not-run (budget)', so it is not guaranteed to reproduce; `--reuse-reference` copies the block of an earlier record instead of re-running it. This record's block was reused from a record with sha256 `3437be3732c892fe222812421dc63416cb5b9dc3a8b562695d329d9ec0139fac` (LF-normalised).

Hofmann rows with t_powder = 0 (bare plate) and P <= 100 W (26 rows); all other rows are not run with the reference transient.
Completed 17, boiling stop 9, not run (budget) 0 of 26. sourcePenetration_um = 40 is an arbitrary, unvalidated choice for the bare-plate volumetric absorption depth; mesh 20 um is coarse relative to the 50-140 um spots and the result is not mesh-converged: every completed case has depth <= 2 cells, so its width/depth are cell-quantised (meshLimited = true) and carry almost no information about the measured track; a completed width of 0 means no resolved liquid extent. completed/boiling-stop is the reference transient's own validity stop; the widths/depths are a model comparison, not validation. Rows beyond the budget were skipped, not estimated.

| row | P W | v mm/s | d um | status | W pred | W meas | D pred | D meas |
|---|---|---|---|---|---|---|---|---|
| hofmann-0047 | 75 | 1050 | 50 | completed (mesh-limited) | 39.5 | 72.8 | 19.7 | 25.7 |
| hofmann-0083 | 100 | 600 | 110 | completed (mesh-limited) | 98.9 | 121.2 | 39.6 | 35.2 |
| hofmann-0102 | 100 | 300 | 80 | boiling-stop | - | 140.1 | - | 54.8 |
| hofmann-0156 | 75 | 750 | 80 | completed (mesh-limited) | 40.0 | 99.8 | 20.0 | 25.6 |
| hofmann-0164 | 50 | 600 | 80 | completed (mesh-limited) | 40.0 | 86.0 | 20.0 | 18.0 |
| hofmann-0241 | 50 | 900 | 50 | completed (mesh-limited) | 39.5 | 66.8 | 19.7 | 22.0 |
| hofmann-0245 | 100 | 900 | 50 | boiling-stop | - | 77.9 | - | 36.6 |
| hofmann-0269 | 100 | 300 | 80 | boiling-stop | - | 124.4 | - | 50.0 |
| hofmann-0301 | 100 | 1200 | 80 | completed (mesh-limited) | 40.0 | 104.9 | 20.0 | 21.6 |
| hofmann-0326 | 50 | 300 | 50 | boiling-stop | - | 80.8 | - | 33.4 |
| hofmann-0341 | 100 | 1200 | 50 | boiling-stop | - | 67.2 | - | 29.2 |
| hofmann-0346 | 100 | 1500 | 50 | completed (mesh-limited) | 39.5 | 69.9 | 19.7 | 26.1 |
| hofmann-0409 | 100 | 900 | 80 | completed (mesh-limited) | 80.0 | 87.6 | 40.0 | 30.3 |
| hofmann-0412 | 50 | 300 | 140 | completed (mesh-limited) | 60.0 | 112.9 | 20.0 | 14.9 |
| hofmann-0432 | 100 | 900 | 110 | completed (mesh-limited) | 59.4 | 107.1 | 19.8 | 24.1 |
| hofmann-0446 | 75 | 750 | 50 | boiling-stop | - | 69.0 | - | 29.8 |
| hofmann-0467 | 50 | 600 | 80 | completed (mesh-limited) | 40.0 | 88.2 | 20.0 | 18.0 |
| hofmann-0508 | 100 | 600 | 50 | boiling-stop | - | 92.7 | - | 53.3 |
| hofmann-0529 | 100 | 1050 | 80 | completed (mesh-limited) | 40.0 | 101.7 | 20.0 | 27.9 |
| hofmann-0541 | 50 | 300 | 110 | completed (mesh-limited) | 59.4 | 115.9 | 39.6 | 22.2 |
| hofmann-0544 | 50 | 450 | 50 | completed (mesh-limited) | 39.5 | 74.8 | 39.5 | 26.8 |
| hofmann-0563 | 100 | 600 | 140 | completed (mesh-limited) | 100.0 | 130.1 | 40.0 | 26.4 |
| hofmann-0606 | 100 | 450 | 50 | boiling-stop | - | 123.3 | - | 84.7 |
| hofmann-0608 | 50 | 1050 | 80 | completed (mesh-limited) | 0.0 | 71.1 | 0.0 | 14.6 |
| hofmann-0613 | 50 | 900 | 50 | completed (mesh-limited) | 39.5 | 52.4 | 19.7 | 20.9 |
| hofmann-0618 | 100 | 600 | 80 | boiling-stop | - | 96.1 | - | 38.1 |
