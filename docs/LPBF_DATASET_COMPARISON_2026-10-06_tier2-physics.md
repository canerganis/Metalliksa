# LPBF dataset comparison (2026-10-06)

**Comparison of screening kernels against published single-track measurements; not experimental validation; estimated material laws; absorptivity assumed.**

Schema `lpbf-dataset-comparison-1`; implementation fingerprint `ddd8358abd68652f4ff0dfd20fb50fcee200826021bd70f511aacce42265c932`; quick mode: False. Honesty: comparison, not validation; screening kernels; estimated material laws; absorptivity assumed (not measured); published single-track measurements, no replicate or uncertainty model; a failing comparison is reported, not fitted away. `experimentalValidation` = false.

Slim view record `LPBF_DATASET_COMPARISON_2026-10-06_tier2-physics.view.json` (this record minus `breakdowns` and `referenceTransient.rows`; sha256 of its LF bytes `50dbfbf90fd48d30e7e75d6c10d67071b1c5043f139b7fecee1afb4054910683`).

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

- Kernels are compared on different included subsets (rows with extentStatus == 'computed'): pooled n = rosenthal 679 of 1431, eagar-tsai 757 of 1431, goldak 745 of 1431. Only summary.<kernel>.common (n = 679, the rows where all kernels are computed) is a like-for-like comparison; pooled and per-regime figures of different kernels are not.
- Rosenthal conduction statistics rest on 77 of 141 conduction rows: they are selected by the kernel's own output (only rows where Rosenthal resolves an extent without heuristic fallback, search-box limitation or the 0.55 x beam-diameter width floor are 'computed'), so they describe the rows it can resolve, not the regime.
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
| rosenthal | all | 679 | 752 | +9.5 | 30.8 | 61.1 | 56% / 94% | +40.6 | 50.3 | 66.8 | 51% / 87% |
| rosenthal | balling-flagged | 202 | 14 | +8.1 | 27.8 | 50.0 | 61% / 95% | +79.2 | 83.2 | 68.5 | 33% / 75% |
| rosenthal | conduction | 77 | 64 | -43.3 | 43.3 | 70.6 | 8% / 71% | -1.2 | 26.3 | 16.6 | 75% / 96% |
| rosenthal | keyhole | 194 | 0 | +44.7 | 44.7 | 85.3 | 34% / 98% | +25.1 | 37.7 | 94.3 | 55% / 93% |
| rosenthal | transition | 206 | 0 | -2.5 | 15.9 | 33.8 | 91% / 99% | +33.1 | 38.9 | 40.3 | 55% / 90% |
| rosenthal | unclassified-missing-process-input | 0 | 626 | - | - | - | - | - | - | - | - |
| rosenthal | unclassified-source-dimensions-unresolved | 0 | 48 | - | - | - | - | - | - | - | - |
| rosenthal | common | 679 | 752 | +9.5 | 30.8 | 61.1 | 56% / 94% | +40.6 | 50.3 | 66.8 | 51% / 87% |
| eagar-tsai | all | 757 | 674 | -10.2 | 13.9 | 29.1 | 94% / 100% | +12.0 | 34.4 | 54.1 | 63% / 91% |
| eagar-tsai | balling-flagged | 216 | 0 | -10.1 | 14.6 | 31.9 | 92% / 100% | +38.8 | 51.2 | 46.7 | 56% / 83% |
| eagar-tsai | conduction | 141 | 0 | -12.3 | 14.6 | 26.7 | 94% / 100% | +20.8 | 30.0 | 13.6 | 73% / 91% |
| eagar-tsai | keyhole | 194 | 0 | -4.0 | 11.2 | 25.1 | 98% / 100% | +0.4 | 24.7 | 82.8 | 67% / 98% |
| eagar-tsai | transition | 206 | 0 | -14.7 | 15.3 | 30.9 | 92% / 100% | -11.2 | 29.0 | 43.4 | 61% / 92% |
| eagar-tsai | unclassified-missing-process-input | 0 | 626 | - | - | - | - | - | - | - | - |
| eagar-tsai | unclassified-source-dimensions-unresolved | 0 | 48 | - | - | - | - | - | - | - | - |
| eagar-tsai | common | 679 | 752 | -10.0 | 13.8 | 29.4 | 94% / 100% | +9.3 | 34.0 | 57.0 | 63% / 92% |
| goldak | all | 745 | 686 | -17.7 | 20.2 | 39.9 | 80% / 99% | +18.8 | 38.2 | 54.5 | 60% / 91% |
| goldak | balling-flagged | 215 | 1 | -17.3 | 20.4 | 41.7 | 78% / 100% | +45.6 | 54.8 | 47.1 | 53% / 83% |
| goldak | conduction | 130 | 11 | -30.5 | 30.6 | 50.6 | 50% / 98% | +41.8 | 46.4 | 17.5 | 51% / 88% |
| goldak | keyhole | 194 | 0 | -6.6 | 12.5 | 27.9 | 98% / 100% | +0.4 | 24.7 | 82.8 | 67% / 98% |
| goldak | transition | 206 | 0 | -20.5 | 20.6 | 39.9 | 84% / 100% | -6.4 | 28.6 | 42.2 | 66% / 93% |
| goldak | unclassified-missing-process-input | 0 | 626 | - | - | - | - | - | - | - | - |
| goldak | unclassified-source-dimensions-unresolved | 0 | 48 | - | - | - | - | - | - | - | - |
| goldak | common | 679 | 752 | -15.9 | 18.6 | 37.9 | 85% / 100% | +14.2 | 35.6 | 56.8 | 62% / 92% |

### Cluster-bootstrap 95 % intervals (pooled summary cells)

Distinct parameter sets (dataset, power, speed, beam diameter, layer) resampled with replacement, 1000 replicates, `random.Random(0)`, percentile 2.5/97.5; replicates of one set stay together. The intervals cover this resampling only (no measurement uncertainty, no material-law uncertainty); they are in JSON `summary.<kernel>.<regime>.<width|depth>.{bias_pct_ci95, mape_pct_ci95, n_parameterSets}`.

| kernel | regime | n | parameter sets | W bias % CI95 | W MAPE % CI95 | D bias % CI95 | D MAPE % CI95 |
|---|---|---|---|---|---|---|---|
| rosenthal | all | 679 | 631 | [6.5, 12.2] | [29.0, 32.6] | [35.4, 45.9] | [45.7, 55.3] |
| rosenthal | balling-flagged | 202 | 201 | [3.1, 12.8] | [24.4, 31.0] | [66.3, 94.3] | [70.5, 98.0] |
| rosenthal | conduction | 77 | 70 | [-45.8, -40.6] | [40.6, 45.8] | [-9.1, 7.2] | [20.5, 32.7] |
| rosenthal | keyhole | 194 | 185 | [41.2, 48.3] | [41.3, 48.3] | [18.8, 31.1] | [33.2, 42.4] |
| rosenthal | transition | 206 | 185 | [-5.3, 0.2] | [14.2, 17.5] | [26.7, 39.7] | [33.4, 44.6] |
| rosenthal | common | 679 | 631 | [6.5, 12.2] | [29.0, 32.6] | [35.4, 45.9] | [45.7, 55.3] |
| eagar-tsai | all | 757 | 703 | [-11.1, -9.3] | [13.3, 14.6] | [7.9, 16.3] | [31.0, 38.2] |
| eagar-tsai | balling-flagged | 216 | 215 | [-12.1, -8.3] | [13.3, 15.8] | [28.6, 50.0] | [42.0, 61.8] |
| eagar-tsai | conduction | 141 | 128 | [-14.2, -10.5] | [13.3, 16.0] | [12.9, 28.9] | [23.1, 37.2] |
| eagar-tsai | keyhole | 194 | 185 | [-5.7, -2.1] | [10.2, 12.2] | [-4.1, 4.8] | [22.0, 27.3] |
| eagar-tsai | transition | 206 | 185 | [-16.1, -13.4] | [14.1, 16.5] | [-16.2, -6.6] | [25.8, 32.4] |
| eagar-tsai | common | 679 | 631 | [-10.9, -9.0] | [13.1, 14.5] | [4.7, 13.6] | [30.3, 37.6] |
| goldak | all | 745 | 691 | [-18.8, -16.6] | [19.3, 21.0] | [14.5, 23.2] | [34.7, 41.9] |
| goldak | balling-flagged | 215 | 214 | [-19.3, -15.2] | [18.9, 21.9] | [35.3, 56.9] | [45.9, 65.4] |
| goldak | conduction | 130 | 117 | [-32.5, -28.3] | [28.6, 32.6] | [32.4, 52.0] | [37.2, 56.5] |
| goldak | keyhole | 194 | 185 | [-8.3, -4.7] | [11.3, 13.5] | [-4.1, 4.8] | [22.0, 27.3] |
| goldak | transition | 206 | 185 | [-21.9, -19.2] | [19.3, 21.9] | [-11.5, -1.6] | [25.0, 32.1] |
| goldak | common | 679 | 631 | [-17.0, -14.9] | [17.8, 19.4] | [9.7, 18.6] | [31.8, 39.5] |

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
| rosenthal | all | 604 | 73 | +5.9 | 28.1 | 57.2 | 60% / 95% | +44.5 | 52.0 | 58.2 | 50% / 87% |
| rosenthal | balling-flagged | 202 | 14 | +8.1 | 27.8 | 50.0 | 61% / 95% | +79.2 | 83.2 | 68.5 | 33% / 75% |
| rosenthal | conduction | 74 | 59 | -42.8 | 42.8 | 71.4 | 8% / 74% | +0.5 | 25.1 | 14.1 | 77% / 99% |
| rosenthal | keyhole | 137 | 0 | +38.3 | 38.3 | 79.8 | 41% / 99% | +29.1 | 36.6 | 74.1 | 56% / 94% |
| rosenthal | transition | 191 | 0 | -0.9 | 15.3 | 33.9 | 93% / 100% | +35.7 | 40.5 | 41.6 | 54% / 90% |
| eagar-tsai | all | 677 | 0 | -10.5 | 13.5 | 29.4 | 96% / 100% | +14.5 | 34.3 | 46.7 | 65% / 91% |
| eagar-tsai | balling-flagged | 216 | 0 | -10.1 | 14.6 | 31.9 | 92% / 100% | +38.8 | 51.2 | 46.7 | 56% / 83% |
| eagar-tsai | conduction | 133 | 0 | -11.9 | 14.0 | 27.1 | 96% / 100% | +18.3 | 25.9 | 12.3 | 77% / 95% |
| eagar-tsai | keyhole | 137 | 0 | -5.6 | 10.4 | 25.9 | 99% / 100% | +5.5 | 24.0 | 66.6 | 71% / 99% |
| eagar-tsai | transition | 191 | 0 | -13.3 | 14.0 | 30.3 | 97% / 100% | -9.1 | 28.4 | 44.6 | 63% / 93% |
| goldak | all | 665 | 12 | -18.2 | 20.1 | 41.0 | 81% / 100% | +21.7 | 38.3 | 47.1 | 61% / 91% |
| goldak | balling-flagged | 215 | 1 | -17.3 | 20.4 | 41.7 | 78% / 100% | +45.6 | 54.8 | 47.1 | 53% / 83% |
| goldak | conduction | 122 | 11 | -29.8 | 30.0 | 51.7 | 52% / 98% | +38.3 | 41.0 | 16.7 | 53% / 92% |
| goldak | keyhole | 137 | 0 | -8.2 | 12.0 | 29.4 | 99% / 100% | +5.5 | 24.0 | 66.6 | 71% / 99% |
| goldak | transition | 191 | 0 | -19.0 | 19.2 | 39.6 | 90% / 100% | -4.2 | 28.1 | 43.3 | 67% / 94% |

### Dataset ku-leuven-316l-2021

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 44 | 0 | +56.2 | 56.2 | 91.8 | 16% / 100% | -9.5 | 43.4 | 219.6 | 23% / 82% |
| rosenthal | keyhole | 40 | 0 | +58.4 | 58.4 | 95.9 | 15% / 100% | -18.8 | 39.4 | 230.1 | 25% / 82% |
| rosenthal | transition | 4 | 0 | +34.3 | 34.3 | 24.7 | 25% / 100% | +83.7 | 83.7 | 34.0 | 0% / 75% |
| eagar-tsai | all | 44 | 0 | +3.7 | 12.5 | 22.5 | 98% / 100% | -12.9 | 29.0 | 158.4 | 43% / 100% |
| eagar-tsai | keyhole | 40 | 0 | +4.2 | 13.2 | 23.6 | 98% / 100% | -17.6 | 28.5 | 166.1 | 45% / 100% |
| eagar-tsai | transition | 4 | 0 | -0.9 | 5.5 | 4.0 | 100% / 100% | +33.5 | 33.5 | 16.3 | 25% / 100% |
| goldak | all | 44 | 0 | +2.4 | 12.6 | 22.5 | 98% / 100% | -12.9 | 29.0 | 158.4 | 43% / 100% |
| goldak | keyhole | 40 | 0 | +3.1 | 13.2 | 23.5 | 98% / 100% | -17.6 | 28.5 | 166.1 | 45% / 100% |
| goldak | transition | 4 | 0 | -5.1 | 7.1 | 5.5 | 100% / 100% | +33.5 | 33.5 | 16.3 | 25% / 100% |

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
| rosenthal | all | 14 | 0 | +33.7 | 33.7 | 37.3 | 50% / 100% | +62.8 | 65.2 | 39.3 | 43% / 57% |
| rosenthal | keyhole | 11 | 0 | +36.8 | 36.8 | 41.3 | 36% / 100% | +47.4 | 50.5 | 40.2 | 55% / 64% |
| rosenthal | transition | 3 | 0 | +22.2 | 22.2 | 15.3 | 100% / 100% | +119.2 | 119.2 | 35.8 | 0% / 33% |
| eagar-tsai | all | 14 | 0 | -13.7 | 13.7 | 13.9 | 100% / 100% | +21.2 | 28.6 | 22.2 | 57% / 100% |
| eagar-tsai | keyhole | 11 | 0 | -14.1 | 14.1 | 15.1 | 100% / 100% | +13.2 | 22.7 | 23.5 | 64% / 100% |
| eagar-tsai | transition | 3 | 0 | -12.2 | 12.2 | 8.2 | 100% / 100% | +50.6 | 50.6 | 16.6 | 33% / 100% |
| goldak | all | 14 | 0 | -16.6 | 16.6 | 16.2 | 100% / 100% | +21.2 | 28.6 | 22.2 | 57% / 100% |
| goldak | keyhole | 11 | 0 | -16.5 | 16.5 | 17.3 | 100% / 100% | +13.2 | 22.7 | 23.5 | 64% / 100% |
| goldak | transition | 3 | 0 | -17.2 | 17.2 | 11.6 | 100% / 100% | +50.6 | 50.6 | 16.6 | 33% / 100% |

### Dataset lane-in625-2020

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 6 | 17 | -23.2 | 23.2 | 34.6 | 100% / 100% | -38.5 | 38.5 | 51.9 | 0% / 100% |
| rosenthal | conduction | 0 | 17 | - | - | - | - | - | - | - | - |
| rosenthal | transition | 6 | 0 | -23.2 | 23.2 | 34.6 | 100% / 100% | -38.5 | 38.5 | 51.9 | 0% / 100% |
| eagar-tsai | all | 23 | 0 | +7.8 | 15.5 | 21.8 | 100% / 100% | -26.4 | 27.5 | 40.5 | 57% / 74% |
| eagar-tsai | conduction | 17 | 0 | +15.8 | 15.8 | 20.1 | 100% / 100% | -15.6 | 17.1 | 12.7 | 76% / 100% |
| eagar-tsai | transition | 6 | 0 | -14.9 | 14.9 | 26.0 | 100% / 100% | -57.1 | 57.1 | 76.4 | 0% / 0% |
| goldak | all | 14 | 9 | -24.2 | 24.2 | 36.6 | 86% / 100% | -24.1 | 37.6 | 47.7 | 29% / 79% |
| goldak | conduction | 8 | 9 | -22.7 | 22.7 | 32.8 | 75% / 100% | -3.5 | 27.2 | 14.9 | 50% / 100% |
| goldak | transition | 6 | 0 | -26.2 | 26.2 | 41.2 | 100% / 100% | -51.5 | 51.5 | 70.8 | 0% / 50% |

### Dataset totis-ti64-2021

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 75 | 5 | +38.9 | 52.7 | 86.4 | 28% / 88% | +9.9 | 36.6 | 114.5 | 56% / 89% |
| rosenthal | conduction | 3 | 5 | -56.1 | 56.1 | 47.1 | 0% / 0% | -42.1 | 55.5 | 45.9 | 33% / 33% |
| rosenthal | keyhole | 57 | 0 | +60.1 | 60.2 | 97.1 | 18% / 95% | +15.4 | 40.4 | 130.7 | 53% / 91% |
| rosenthal | transition | 15 | 0 | -22.9 | 23.5 | 31.9 | 73% / 80% | -0.7 | 18.4 | 14.4 | 73% / 93% |
| eagar-tsai | all | 80 | 0 | -8.1 | 18.1 | 26.1 | 80% / 100% | -9.3 | 35.4 | 96.0 | 49% / 89% |
| eagar-tsai | conduction | 8 | 0 | -18.9 | 25.4 | 19.9 | 62% / 100% | +62.4 | 96.7 | 27.0 | 12% / 38% |
| eagar-tsai | keyhole | 57 | 0 | -0.1 | 13.1 | 23.2 | 96% / 100% | -11.9 | 26.2 | 112.6 | 58% / 98% |
| eagar-tsai | transition | 15 | 0 | -33.0 | 33.0 | 37.2 | 27% / 100% | -37.7 | 37.7 | 23.7 | 33% / 80% |
| goldak | all | 80 | 0 | -13.3 | 21.1 | 29.3 | 71% / 98% | -5.3 | 37.8 | 95.9 | 51% / 89% |
| goldak | conduction | 8 | 0 | -39.9 | 39.9 | 30.8 | 12% / 88% | +95.8 | 128.1 | 26.3 | 12% / 25% |
| goldak | keyhole | 57 | 0 | -2.7 | 13.6 | 23.9 | 95% / 100% | -11.9 | 26.2 | 112.6 | 58% / 98% |
| goldak | transition | 15 | 0 | -39.4 | 39.4 | 43.7 | 13% / 93% | -34.0 | 34.0 | 22.2 | 47% / 87% |

### Hofmann, spot 50 um

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 175 | 0 | +26.6 | 33.2 | 49.8 | 51% / 98% | +52.7 | 59.8 | 58.4 | 49% / 85% |
| rosenthal | balling-flagged | 74 | 0 | +38.1 | 38.7 | 53.8 | 42% / 96% | +86.0 | 90.9 | 76.7 | 45% / 74% |
| rosenthal | conduction | 9 | 0 | -33.8 | 33.8 | 25.5 | 33% / 89% | -7.1 | 25.0 | 9.8 | 78% / 100% |
| rosenthal | keyhole | 51 | 0 | +41.4 | 41.4 | 63.1 | 33% / 100% | +26.2 | 35.4 | 52.3 | 53% / 96% |
| rosenthal | transition | 41 | 0 | +0.7 | 13.0 | 16.3 | 93% / 100% | +38.7 | 41.8 | 22.3 | 46% / 88% |
| eagar-tsai | all | 175 | 0 | -6.8 | 13.4 | 21.6 | 94% / 100% | +22.5 | 42.2 | 51.4 | 65% / 89% |
| eagar-tsai | balling-flagged | 74 | 0 | -4.6 | 14.9 | 26.3 | 89% / 100% | +53.6 | 67.2 | 64.4 | 58% / 76% |
| eagar-tsai | conduction | 9 | 0 | -4.4 | 12.4 | 10.1 | 100% / 100% | +4.1 | 20.2 | 9.1 | 78% / 100% |
| eagar-tsai | keyhole | 51 | 0 | -4.5 | 10.2 | 15.9 | 100% / 100% | +5.0 | 23.6 | 52.3 | 69% / 100% |
| eagar-tsai | transition | 41 | 0 | -14.2 | 15.0 | 20.3 | 95% / 100% | -7.9 | 24.8 | 18.9 | 71% / 95% |
| goldak | all | 175 | 0 | -10.5 | 15.5 | 23.6 | 91% / 100% | +24.1 | 42.4 | 51.3 | 66% / 89% |
| goldak | balling-flagged | 74 | 0 | -7.3 | 15.9 | 27.6 | 86% / 100% | +53.7 | 67.1 | 64.4 | 58% / 77% |
| goldak | conduction | 9 | 0 | -17.8 | 19.1 | 15.7 | 89% / 100% | +16.3 | 25.1 | 9.0 | 78% / 89% |
| goldak | keyhole | 51 | 0 | -6.8 | 11.2 | 17.5 | 100% / 100% | +5.0 | 23.6 | 52.3 | 69% / 100% |
| goldak | transition | 41 | 0 | -19.3 | 19.5 | 24.0 | 90% / 100% | -3.8 | 24.8 | 18.3 | 76% / 95% |

### Hofmann, spot 80 um

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 177 | 10 | +9.3 | 26.7 | 57.6 | 63% / 96% | +54.8 | 61.5 | 65.3 | 43% / 80% |
| rosenthal | balling-flagged | 58 | 1 | +6.2 | 15.6 | 28.9 | 86% / 100% | +105.1 | 106.6 | 78.1 | 12% / 60% |
| rosenthal | conduction | 17 | 9 | -45.4 | 45.4 | 55.1 | 6% / 65% | +6.1 | 32.1 | 10.0 | 71% / 94% |
| rosenthal | keyhole | 55 | 0 | +40.4 | 40.4 | 90.1 | 36% / 98% | +31.6 | 38.6 | 78.4 | 58% / 89% |
| rosenthal | transition | 47 | 0 | -3.3 | 17.4 | 29.2 | 87% / 100% | +37.5 | 43.4 | 35.8 | 53% / 89% |
| eagar-tsai | all | 187 | 0 | -10.3 | 12.9 | 27.6 | 94% / 100% | +17.0 | 35.7 | 49.4 | 62% / 90% |
| eagar-tsai | balling-flagged | 59 | 0 | -13.2 | 15.0 | 34.8 | 88% / 100% | +43.0 | 52.9 | 44.4 | 47% / 83% |
| eagar-tsai | conduction | 26 | 0 | -12.9 | 13.7 | 19.8 | 92% / 100% | +17.6 | 26.3 | 8.5 | 73% / 96% |
| eagar-tsai | keyhole | 55 | 0 | -4.3 | 10.4 | 24.5 | 98% / 100% | +7.3 | 25.7 | 71.1 | 73% / 96% |
| eagar-tsai | transition | 47 | 0 | -12.1 | 12.8 | 24.6 | 96% / 100% | -4.7 | 30.9 | 35.4 | 60% / 89% |
| goldak | all | 186 | 1 | -16.7 | 18.4 | 33.9 | 84% / 99% | +22.4 | 38.0 | 49.4 | 61% / 91% |
| goldak | balling-flagged | 59 | 0 | -19.1 | 19.7 | 40.1 | 81% / 100% | +47.7 | 55.3 | 44.4 | 47% / 83% |
| goldak | conduction | 25 | 1 | -30.2 | 30.2 | 35.8 | 52% / 96% | +36.9 | 39.3 | 11.2 | 56% / 96% |
| goldak | keyhole | 55 | 0 | -6.9 | 11.9 | 27.0 | 98% / 100% | +7.3 | 25.7 | 71.1 | 73% / 96% |
| goldak | transition | 47 | 0 | -18.1 | 18.1 | 31.5 | 87% / 100% | +0.7 | 30.0 | 34.6 | 66% / 91% |

### Hofmann, spot 110 um

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 140 | 21 | -5.7 | 24.2 | 55.2 | 70% / 92% | +41.3 | 48.4 | 57.5 | 49% / 89% |
| rosenthal | balling-flagged | 39 | 6 | -15.7 | 22.7 | 46.5 | 74% / 90% | +66.2 | 68.8 | 54.8 | 26% / 82% |
| rosenthal | conduction | 22 | 15 | -43.5 | 43.5 | 69.8 | 9% / 68% | -4.7 | 22.2 | 15.4 | 82% / 100% |
| rosenthal | keyhole | 24 | 0 | +29.8 | 29.8 | 81.8 | 62% / 100% | +30.5 | 35.6 | 87.8 | 58% / 100% |
| rosenthal | transition | 55 | 0 | +1.2 | 15.2 | 36.9 | 95% / 100% | +46.9 | 50.0 | 53.3 | 47% / 85% |
| eagar-tsai | all | 161 | 0 | -12.5 | 14.2 | 31.9 | 98% / 100% | +10.8 | 29.6 | 40.2 | 66% / 93% |
| eagar-tsai | balling-flagged | 45 | 0 | -13.1 | 15.1 | 33.4 | 96% / 100% | +30.0 | 43.2 | 26.2 | 53% / 84% |
| eagar-tsai | conduction | 37 | 0 | -11.5 | 14.1 | 24.3 | 100% / 100% | +13.1 | 19.5 | 12.0 | 76% / 97% |
| eagar-tsai | keyhole | 24 | 0 | -9.6 | 10.9 | 34.6 | 100% / 100% | +3.5 | 20.2 | 72.9 | 71% / 100% |
| eagar-tsai | transition | 55 | 0 | -14.1 | 15.0 | 34.0 | 98% / 100% | -3.3 | 29.3 | 41.9 | 67% / 95% |
| goldak | all | 158 | 3 | -21.9 | 22.3 | 45.1 | 75% / 100% | +19.8 | 34.6 | 40.7 | 64% / 92% |
| goldak | balling-flagged | 44 | 1 | -24.0 | 24.0 | 47.2 | 68% / 100% | +41.6 | 47.9 | 27.3 | 57% / 84% |
| goldak | conduction | 35 | 2 | -29.5 | 29.8 | 46.9 | 49% / 100% | +32.2 | 34.3 | 15.3 | 63% / 94% |
| goldak | keyhole | 24 | 0 | -12.5 | 13.3 | 40.5 | 100% / 100% | +3.5 | 20.2 | 72.9 | 71% / 100% |
| goldak | transition | 55 | 0 | -19.5 | 20.0 | 44.0 | 87% / 100% | +1.5 | 30.3 | 41.1 | 67% / 95% |

### Hofmann, spot 140 um

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 112 | 42 | -17.6 | 26.9 | 68.5 | 56% / 92% | +19.1 | 29.3 | 45.4 | 65% / 96% |
| rosenthal | balling-flagged | 31 | 7 | -30.1 | 30.7 | 71.3 | 42% / 87% | +30.9 | 39.1 | 36.0 | 52% / 94% |
| rosenthal | conduction | 26 | 35 | -43.6 | 43.6 | 90.3 | 0% / 81% | +3.7 | 23.1 | 16.4 | 77% / 100% |
| rosenthal | keyhole | 7 | 0 | +28.3 | 28.3 | 94.7 | 57% / 100% | +26.6 | 32.6 | 112.8 | 57% / 100% |
| rosenthal | transition | 48 | 0 | -2.1 | 15.2 | 44.2 | 96% / 100% | +18.7 | 25.9 | 44.3 | 69% / 96% |
| eagar-tsai | all | 154 | 0 | -12.6 | 13.4 | 35.7 | 98% / 100% | +6.3 | 28.7 | 44.2 | 68% / 94% |
| eagar-tsai | balling-flagged | 38 | 0 | -12.3 | 12.8 | 35.3 | 100% / 100% | +13.8 | 27.2 | 20.8 | 68% / 97% |
| eagar-tsai | conduction | 61 | 0 | -12.9 | 14.3 | 32.5 | 95% / 100% | +23.8 | 30.6 | 14.2 | 79% / 92% |
| eagar-tsai | keyhole | 7 | 0 | -10.8 | 10.9 | 49.7 | 100% / 100% | +1.2 | 27.1 | 94.2 | 71% / 100% |
| eagar-tsai | transition | 48 | 0 | -12.8 | 13.0 | 37.3 | 100% / 100% | -21.1 | 27.7 | 66.1 | 54% / 92% |
| goldak | all | 146 | 8 | -25.3 | 25.3 | 57.7 | 71% / 99% | +19.8 | 37.7 | 45.4 | 51% / 92% |
| goldak | balling-flagged | 38 | 0 | -26.2 | 26.2 | 57.4 | 66% / 100% | +31.1 | 37.8 | 23.2 | 50% / 95% |
| goldak | conduction | 53 | 8 | -31.9 | 31.9 | 63.6 | 49% / 98% | +46.7 | 48.9 | 20.5 | 42% / 89% |
| goldak | keyhole | 7 | 0 | -13.7 | 13.7 | 57.4 | 100% / 100% | +1.2 | 27.1 | 94.2 | 71% / 100% |
| goldak | transition | 48 | 0 | -18.9 | 18.9 | 50.6 | 96% / 100% | -16.1 | 26.8 | 63.9 | 60% / 94% |

**Powder-layer breakdowns below:** the kernels ignore powder-layer thickness (identical predictions at 0/30/60 um, see `assumptions.layer_um`), so any trend with powder-layer thickness in these tables is in the measurements only, not a kernel result.

### Hofmann, powder layer 0 um

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 166 | 44 | -1.1 | 27.8 | 53.6 | 59% / 91% | +42.3 | 49.0 | 56.1 | 46% / 87% |
| rosenthal | balling-flagged | 38 | 0 | +4.1 | 22.4 | 39.5 | 68% / 97% | +71.3 | 73.0 | 69.6 | 16% / 79% |
| rosenthal | conduction | 29 | 44 | -46.1 | 46.1 | 76.4 | 10% / 52% | -13.0 | 19.8 | 9.0 | 97% / 100% |
| rosenthal | keyhole | 41 | 0 | +33.9 | 33.9 | 64.3 | 49% / 100% | +45.1 | 46.8 | 74.4 | 46% / 85% |
| rosenthal | transition | 58 | 0 | -6.8 | 17.9 | 36.9 | 84% / 100% | +48.9 | 49.3 | 43.5 | 41% / 86% |
| eagar-tsai | all | 210 | 0 | -13.4 | 14.6 | 31.2 | 95% / 100% | +9.8 | 21.7 | 32.3 | 83% / 95% |
| eagar-tsai | balling-flagged | 38 | 0 | -16.3 | 16.8 | 35.6 | 89% / 100% | +27.1 | 39.7 | 46.4 | 61% / 87% |
| eagar-tsai | conduction | 73 | 0 | -13.8 | 15.2 | 28.8 | 96% / 100% | +2.8 | 9.2 | 5.2 | 97% / 99% |
| eagar-tsai | keyhole | 41 | 0 | -8.8 | 10.8 | 27.2 | 100% / 100% | +19.8 | 27.7 | 49.8 | 73% / 98% |
| eagar-tsai | transition | 58 | 0 | -14.2 | 15.1 | 33.5 | 93% / 100% | +0.1 | 21.4 | 23.8 | 86% / 95% |
| goldak | all | 201 | 9 | -23.1 | 23.5 | 45.9 | 65% / 100% | +18.6 | 25.7 | 33.2 | 77% / 95% |
| goldak | balling-flagged | 38 | 0 | -21.9 | 21.9 | 44.6 | 66% / 100% | +30.8 | 37.2 | 46.1 | 63% / 87% |
| goldak | conduction | 64 | 9 | -33.6 | 33.6 | 56.0 | 33% / 98% | +21.4 | 21.4 | 9.9 | 78% / 98% |
| goldak | keyhole | 41 | 0 | -11.2 | 12.6 | 31.2 | 100% / 100% | +19.8 | 27.7 | 49.8 | 73% / 98% |
| goldak | transition | 58 | 0 | -20.7 | 21.1 | 42.9 | 76% / 100% | +6.8 | 21.6 | 23.6 | 88% / 95% |

### Hofmann, powder layer 30 um

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 203 | 29 | +2.9 | 28.9 | 56.1 | 59% / 94% | +38.2 | 47.7 | 52.2 | 55% / 88% |
| rosenthal | balling-flagged | 77 | 14 | +6.9 | 31.3 | 56.6 | 61% / 90% | +67.8 | 73.7 | 65.0 | 44% / 74% |
| rosenthal | conduction | 29 | 15 | -43.2 | 43.2 | 68.3 | 3% / 83% | +14.4 | 28.9 | 12.7 | 62% / 97% |
| rosenthal | keyhole | 36 | 0 | +38.8 | 38.8 | 76.1 | 33% / 100% | +17.6 | 30.6 | 64.9 | 67% / 100% |
| rosenthal | transition | 61 | 0 | -1.3 | 13.2 | 28.2 | 97% / 100% | +24.1 | 34.0 | 34.4 | 59% / 95% |
| eagar-tsai | all | 232 | 0 | -10.0 | 14.1 | 30.3 | 94% / 100% | +16.8 | 39.7 | 48.4 | 54% / 87% |
| eagar-tsai | balling-flagged | 91 | 0 | -9.4 | 16.5 | 35.7 | 88% / 100% | +34.1 | 46.7 | 41.4 | 57% / 82% |
| eagar-tsai | conduction | 44 | 0 | -10.7 | 13.3 | 26.3 | 95% / 100% | +46.1 | 52.0 | 16.1 | 43% / 86% |
| eagar-tsai | keyhole | 36 | 0 | -5.1 | 9.0 | 19.1 | 100% / 100% | -5.6 | 24.3 | 75.4 | 58% / 100% |
| eagar-tsai | transition | 61 | 0 | -13.3 | 14.1 | 29.6 | 100% / 100% | -17.0 | 29.5 | 52.9 | 56% / 87% |
| goldak | all | 229 | 3 | -18.6 | 21.3 | 42.4 | 81% / 100% | +25.3 | 45.7 | 48.7 | 48% / 87% |
| goldak | balling-flagged | 90 | 1 | -18.3 | 23.9 | 47.3 | 71% / 100% | +42.9 | 52.9 | 42.0 | 50% / 82% |
| goldak | conduction | 42 | 2 | -27.9 | 28.2 | 48.6 | 64% / 98% | +68.8 | 72.8 | 22.0 | 17% / 83% |
| goldak | keyhole | 36 | 0 | -7.8 | 10.3 | 22.8 | 100% / 100% | -5.6 | 24.3 | 75.4 | 58% / 100% |
| goldak | transition | 61 | 0 | -18.9 | 19.1 | 38.8 | 95% / 100% | -12.4 | 29.0 | 51.0 | 61% / 90% |

### Hofmann, powder layer 60 um

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 235 | 0 | +13.4 | 27.5 | 60.4 | 62% / 99% | +51.4 | 57.9 | 64.1 | 49% / 86% |
| rosenthal | balling-flagged | 87 | 0 | +10.9 | 27.0 | 47.8 | 57% / 98% | +92.8 | 96.0 | 70.9 | 30% / 74% |
| rosenthal | conduction | 16 | 0 | -36.1 | 36.1 | 67.2 | 12% / 100% | -0.3 | 27.9 | 22.0 | 69% / 100% |
| rosenthal | keyhole | 60 | 0 | +41.0 | 41.0 | 90.8 | 40% / 98% | +25.1 | 33.2 | 78.8 | 57% / 97% |
| rosenthal | transition | 72 | 0 | +4.3 | 14.9 | 35.7 | 96% / 100% | +34.9 | 39.0 | 45.5 | 60% / 88% |
| eagar-tsai | all | 235 | 0 | -8.3 | 11.8 | 26.7 | 98% / 100% | +16.5 | 40.3 | 55.2 | 60% / 92% |
| eagar-tsai | balling-flagged | 87 | 0 | -8.1 | 11.7 | 25.4 | 98% / 100% | +48.8 | 61.1 | 51.7 | 53% / 83% |
| eagar-tsai | conduction | 16 | 0 | -6.9 | 10.3 | 20.3 | 100% / 100% | +12.3 | 30.8 | 20.7 | 75% / 100% |
| eagar-tsai | keyhole | 60 | 0 | -3.8 | 11.1 | 28.3 | 98% / 100% | +2.4 | 21.3 | 70.9 | 77% / 98% |
| eagar-tsai | transition | 72 | 0 | -12.6 | 12.9 | 28.2 | 99% / 100% | -9.9 | 33.0 | 49.4 | 50% / 96% |
| goldak | all | 235 | 0 | -13.7 | 16.0 | 34.7 | 95% / 100% | +20.7 | 41.7 | 55.1 | 60% / 91% |
| goldak | balling-flagged | 87 | 0 | -14.3 | 16.2 | 33.4 | 90% / 100% | +54.7 | 64.3 | 52.2 | 53% / 83% |
| goldak | conduction | 16 | 0 | -20.0 | 20.7 | 39.8 | 100% / 100% | +25.9 | 35.8 | 21.6 | 50% / 88% |
| goldak | keyhole | 60 | 0 | -6.4 | 12.5 | 31.5 | 98% / 100% | +2.4 | 21.3 | 70.9 | 77% / 98% |
| goldak | transition | 72 | 0 | -17.6 | 17.6 | 37.5 | 97% / 100% | -6.2 | 32.7 | 48.3 | 56% / 96% |

## Absorptivity sensitivity (SENSITIVITY, not a calibration)

SENSITIVITY, not a calibrated value: conduction-regime rows (regime assigned at the repo's default absorptivity), absorptivity_IR overridden uniformly via prop_overrides; the absorptivity actually acting in a physical track is unknown.

Conduction rows: 141.

| kernel | a=0.30 W MAPE % | a=0.40 W MAPE % | a=0.50 W MAPE % | a=0.60 W MAPE % | a=0.30 D MAPE % | a=0.40 D MAPE % | a=0.50 D MAPE % | a=0.60 D MAPE % | a=0.30 n | a=0.40 n | a=0.50 n | a=0.60 n |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | 54.3 | 44.9 | 32.8 | 23.3 | 34.4 | 27.2 | 41.2 | 83.0 | 33 | 74 | 95 | 113 |
| eagar-tsai | 22.9 | 15.5 | 11.4 | 9.9 | 29.4 | 29.5 | 42.5 | 59.1 | 140 | 141 | 141 | 141 |
| goldak | 41.7 | 32.2 | 24.1 | 17.6 | 30.4 | 43.8 | 63.2 | 79.7 | 106 | 130 | 137 | 139 |

Included row counts vary with assumed absorptivity: each column uses only rows where the kernel resolves an extent. These are different evaluation subsets; lower width error can accompany higher depth error. Sensitivity, not calibration.

## Wave 2 datasets (2026-10-06)

Wave 2 (2026-10-06): new open measured datasets run through the unchanged screening kernels; comparison, not validation. Per-dataset kernel x regime tables (regime = the repo's screening classifier) with cluster-bootstrap intervals:

### Wave 2 scorecard: ku-leuven-316l-2021

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 44 | 0 | +56.2 | 56.2 | 91.8 | 16% / 100% | -9.5 | 43.4 | 219.6 | 23% / 82% |
| rosenthal | keyhole | 40 | 0 | +58.4 | 58.4 | 95.9 | 15% / 100% | -18.8 | 39.4 | 230.1 | 25% / 82% |
| rosenthal | transition | 4 | 0 | +34.3 | 34.3 | 24.7 | 25% / 100% | +83.7 | 83.7 | 34.0 | 0% / 75% |
| rosenthal | common | 44 | 0 | +56.2 | 56.2 | 91.8 | 16% / 100% | -9.5 | 43.4 | 219.6 | 23% / 82% |
| eagar-tsai | all | 44 | 0 | +3.7 | 12.5 | 22.5 | 98% / 100% | -12.9 | 29.0 | 158.4 | 43% / 100% |
| eagar-tsai | keyhole | 40 | 0 | +4.2 | 13.2 | 23.6 | 98% / 100% | -17.6 | 28.5 | 166.1 | 45% / 100% |
| eagar-tsai | transition | 4 | 0 | -0.9 | 5.5 | 4.0 | 100% / 100% | +33.5 | 33.5 | 16.3 | 25% / 100% |
| eagar-tsai | common | 44 | 0 | +3.7 | 12.5 | 22.5 | 98% / 100% | -12.9 | 29.0 | 158.4 | 43% / 100% |
| goldak | all | 44 | 0 | +2.4 | 12.6 | 22.5 | 98% / 100% | -12.9 | 29.0 | 158.4 | 43% / 100% |
| goldak | keyhole | 40 | 0 | +3.1 | 13.2 | 23.5 | 98% / 100% | -17.6 | 28.5 | 166.1 | 45% / 100% |
| goldak | transition | 4 | 0 | -5.1 | 7.1 | 5.5 | 100% / 100% | +33.5 | 33.5 | 16.3 | 25% / 100% |
| goldak | common | 44 | 0 | +2.4 | 12.6 | 22.5 | 98% / 100% | -12.9 | 29.0 | 158.4 | 43% / 100% |

| kernel | regime | n | parameter sets | W bias % CI95 | W MAPE % CI95 | D bias % CI95 | D MAPE % CI95 |
|---|---|---|---|---|---|---|---|
| rosenthal | all | 44 | 44 | [49.1, 63.2] | [49.1, 63.2] | [-23.3, 6.6] | [36.4, 50.9] |
| rosenthal | keyhole | 40 | 40 | [50.6, 65.9] | [50.6, 65.9] | [-31.0, -5.3] | [33.8, 45.7] |
| rosenthal | transition | 4 | 4 | [29.6, 40.8] | [29.6, 40.8] | [61.9, 114.5] | [61.9, 114.5] |
| rosenthal | common | 44 | 44 | [49.1, 63.2] | [49.1, 63.2] | [-23.3, 6.6] | [36.4, 50.9] |
| eagar-tsai | all | 44 | 44 | [-0.5, 7.9] | [9.9, 15.2] | [-21.5, -3.5] | [24.9, 33.0] |
| eagar-tsai | keyhole | 40 | 40 | [-0.8, 8.9] | [10.4, 15.9] | [-25.3, -9.1] | [24.7, 32.4] |
| eagar-tsai | transition | 4 | 4 | [-4.5, 5.8] | [4.1, 8.0] | [15.0, 50.0] | [15.0, 50.0] |
| eagar-tsai | common | 44 | 44 | [-0.5, 7.9] | [9.9, 15.2] | [-21.5, -3.5] | [24.9, 33.0] |
| goldak | all | 44 | 44 | [-2.0, 6.8] | [10.0, 15.3] | [-21.5, -3.5] | [24.9, 33.0] |
| goldak | keyhole | 40 | 40 | [-2.0, 8.0] | [10.3, 16.0] | [-25.3, -9.1] | [24.7, 32.4] |
| goldak | transition | 4 | 4 | [-8.5, 1.1] | [5.1, 8.5] | [15.0, 50.0] | [15.0, 50.0] |
| goldak | common | 44 | 44 | [-2.0, 6.8] | [10.0, 15.3] | [-21.5, -3.5] | [24.9, 33.0] |

### Wave 2 scorecard: ku-leuven-ti64-2021

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 14 | 0 | +33.7 | 33.7 | 37.3 | 50% / 100% | +62.8 | 65.2 | 39.3 | 43% / 57% |
| rosenthal | keyhole | 11 | 0 | +36.8 | 36.8 | 41.3 | 36% / 100% | +47.4 | 50.5 | 40.2 | 55% / 64% |
| rosenthal | transition | 3 | 0 | +22.2 | 22.2 | 15.3 | 100% / 100% | +119.2 | 119.2 | 35.8 | 0% / 33% |
| rosenthal | common | 14 | 0 | +33.7 | 33.7 | 37.3 | 50% / 100% | +62.8 | 65.2 | 39.3 | 43% / 57% |
| eagar-tsai | all | 14 | 0 | -13.7 | 13.7 | 13.9 | 100% / 100% | +21.2 | 28.6 | 22.2 | 57% / 100% |
| eagar-tsai | keyhole | 11 | 0 | -14.1 | 14.1 | 15.1 | 100% / 100% | +13.2 | 22.7 | 23.5 | 64% / 100% |
| eagar-tsai | transition | 3 | 0 | -12.2 | 12.2 | 8.2 | 100% / 100% | +50.6 | 50.6 | 16.6 | 33% / 100% |
| eagar-tsai | common | 14 | 0 | -13.7 | 13.7 | 13.9 | 100% / 100% | +21.2 | 28.6 | 22.2 | 57% / 100% |
| goldak | all | 14 | 0 | -16.6 | 16.6 | 16.2 | 100% / 100% | +21.2 | 28.6 | 22.2 | 57% / 100% |
| goldak | keyhole | 11 | 0 | -16.5 | 16.5 | 17.3 | 100% / 100% | +13.2 | 22.7 | 23.5 | 64% / 100% |
| goldak | transition | 3 | 0 | -17.2 | 17.2 | 11.6 | 100% / 100% | +50.6 | 50.6 | 16.6 | 33% / 100% |
| goldak | common | 14 | 0 | -16.6 | 16.6 | 16.2 | 100% / 100% | +21.2 | 28.6 | 22.2 | 57% / 100% |

| kernel | regime | n | parameter sets | W bias % CI95 | W MAPE % CI95 | D bias % CI95 | D MAPE % CI95 |
|---|---|---|---|---|---|---|---|
| rosenthal | all | 14 | 14 | [28.0, 40.4] | [28.0, 40.4] | [35.5, 88.3] | [39.5, 89.5] |
| rosenthal | keyhole | 11 | 11 | [30.6, 44.0] | [30.6, 44.0] | [20.7, 74.2] | [25.8, 75.0] |
| rosenthal | transition | 3 | 3 | [16.9, 27.1] | [16.9, 27.1] | [92.9, 152.9] | [92.9, 152.9] |
| rosenthal | common | 14 | 14 | [28.0, 40.4] | [28.0, 40.4] | [35.5, 88.3] | [39.5, 89.5] |
| eagar-tsai | all | 14 | 14 | [-16.3, -10.9] | [10.9, 16.3] | [5.1, 37.0] | [16.7, 40.8] |
| eagar-tsai | keyhole | 11 | 11 | [-17.0, -10.6] | [10.6, 17.0] | [-2.7, 29.5] | [10.7, 34.4] |
| eagar-tsai | transition | 3 | 3 | [-13.1, -11.4] | [11.4, 13.1] | [18.6, 72.2] | [18.6, 72.2] |
| eagar-tsai | common | 14 | 14 | [-16.3, -10.9] | [10.9, 16.3] | [5.1, 37.0] | [16.7, 40.8] |
| goldak | all | 14 | 14 | [-19.3, -13.6] | [13.6, 19.3] | [5.1, 37.0] | [16.7, 40.8] |
| goldak | keyhole | 11 | 11 | [-19.8, -12.7] | [12.7, 19.8] | [-2.7, 29.5] | [10.7, 34.4] |
| goldak | transition | 3 | 3 | [-18.7, -16.0] | [16.0, 18.7] | [18.6, 72.2] | [18.6, 72.2] |
| goldak | common | 14 | 14 | [-19.3, -13.6] | [13.6, 19.3] | [5.1, 37.0] | [16.7, 40.8] |

### Wave 2 scorecard: lane-in625-2020

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 6 | 17 | -23.2 | 23.2 | 34.6 | 100% / 100% | -38.5 | 38.5 | 51.9 | 0% / 100% |
| rosenthal | conduction | 0 | 17 | - | - | - | - | - | - | - | - |
| rosenthal | transition | 6 | 0 | -23.2 | 23.2 | 34.6 | 100% / 100% | -38.5 | 38.5 | 51.9 | 0% / 100% |
| rosenthal | common | 6 | 17 | -23.2 | 23.2 | 34.6 | 100% / 100% | -38.5 | 38.5 | 51.9 | 0% / 100% |
| eagar-tsai | all | 23 | 0 | +7.8 | 15.5 | 21.8 | 100% / 100% | -26.4 | 27.5 | 40.5 | 57% / 74% |
| eagar-tsai | conduction | 17 | 0 | +15.8 | 15.8 | 20.1 | 100% / 100% | -15.6 | 17.1 | 12.7 | 76% / 100% |
| eagar-tsai | transition | 6 | 0 | -14.9 | 14.9 | 26.0 | 100% / 100% | -57.1 | 57.1 | 76.4 | 0% / 0% |
| eagar-tsai | common | 6 | 17 | -14.9 | 14.9 | 26.0 | 100% / 100% | -57.1 | 57.1 | 76.4 | 0% / 0% |
| goldak | all | 14 | 9 | -24.2 | 24.2 | 36.6 | 86% / 100% | -24.1 | 37.6 | 47.7 | 29% / 79% |
| goldak | conduction | 8 | 9 | -22.7 | 22.7 | 32.8 | 75% / 100% | -3.5 | 27.2 | 14.9 | 50% / 100% |
| goldak | transition | 6 | 0 | -26.2 | 26.2 | 41.2 | 100% / 100% | -51.5 | 51.5 | 70.8 | 0% / 50% |
| goldak | common | 6 | 17 | -26.2 | 26.2 | 41.2 | 100% / 100% | -51.5 | 51.5 | 70.8 | 0% / 50% |

| kernel | regime | n | parameter sets | W bias % CI95 | W MAPE % CI95 | D bias % CI95 | D MAPE % CI95 |
|---|---|---|---|---|---|---|---|
| rosenthal | all | 6 | 2 | [-27.8, -18.6] | [18.6, 27.8] | [-41.2, -35.9] | [35.9, 41.2] |
| rosenthal | transition | 6 | 2 | [-27.8, -18.6] | [18.6, 27.8] | [-41.2, -35.9] | [35.9, 41.2] |
| rosenthal | common | 6 | 2 | [-27.8, -18.6] | [18.6, 27.8] | [-41.2, -35.9] | [35.9, 41.2] |
| eagar-tsai | all | 23 | 6 | [-6.2, 18.1] | [9.6, 21.3] | [-45.6, -9.7] | [12.7, 45.6] |
| eagar-tsai | conduction | 17 | 4 | [8.3, 22.4] | [8.3, 22.4] | [-33.1, 0.7] | [4.1, 33.1] |
| eagar-tsai | transition | 6 | 2 | [-20.1, -9.6] | [9.6, 20.1] | [-62.9, -51.2] | [51.2, 62.9] |
| eagar-tsai | common | 6 | 2 | [-20.1, -9.6] | [9.6, 20.1] | [-62.9, -51.2] | [51.2, 62.9] |
| goldak | all | 14 | 4 | [-28.8, -18.8] | [18.8, 28.8] | [-51.5, 10.1] | [27.2, 51.5] |
| goldak | conduction | 8 | 2 | [-28.9, -16.4] | [16.4, 28.9] | [-30.7, 23.7] | [23.7, 30.7] |
| goldak | transition | 6 | 2 | [-28.5, -24.0] | [24.0, 28.5] | [-59.0, -44.0] | [44.0, 59.0] |
| goldak | common | 6 | 2 | [-28.5, -24.0] | [24.0, 28.5] | [-59.0, -44.0] | [44.0, 59.0] |

### SENSITIVITY on an unresolved input, not a fit: KU Leuven rows re-run with beam diameter 75 um (the 37.5 um value read as a radius)

### ku-leuven-316l-2021 at beam diameter 75 um

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 42 | 2 | +40.0 | 52.4 | 88.6 | 21% / 100% | -49.7 | 49.7 | 263.5 | 2% / 48% |
| rosenthal | conduction | 6 | 2 | -32.6 | 32.6 | 30.7 | 33% / 100% | -53.6 | 53.6 | 49.0 | 0% / 50% |
| rosenthal | keyhole | 25 | 0 | +68.8 | 68.8 | 111.1 | 0% / 100% | -51.5 | 51.5 | 333.7 | 4% / 32% |
| rosenthal | transition | 11 | 0 | +14.1 | 25.8 | 37.2 | 64% / 100% | -43.3 | 43.3 | 103.3 | 0% / 82% |
| rosenthal | common | 42 | 2 | +40.0 | 52.4 | 88.6 | 21% / 100% | -49.7 | 49.7 | 263.5 | 2% / 48% |
| eagar-tsai | all | 44 | 0 | +8.2 | 13.9 | 23.5 | 93% / 100% | -56.9 | 56.9 | 286.7 | 2% / 14% |
| eagar-tsai | conduction | 8 | 0 | +7.6 | 12.9 | 11.0 | 88% / 100% | -40.9 | 40.9 | 40.3 | 12% / 62% |
| eagar-tsai | keyhole | 25 | 0 | +15.1 | 15.5 | 28.2 | 92% / 100% | -59.8 | 59.8 | 368.5 | 0% / 4% |
| eagar-tsai | transition | 11 | 0 | -7.2 | 10.9 | 17.5 | 100% / 100% | -62.2 | 62.2 | 137.5 | 0% / 0% |
| eagar-tsai | common | 42 | 2 | +7.5 | 13.4 | 23.8 | 95% / 100% | -58.4 | 58.4 | 293.4 | 0% / 10% |
| goldak | all | 44 | 0 | +1.7 | 13.0 | 22.7 | 100% / 100% | -54.9 | 55.2 | 286.5 | 11% / 18% |
| goldak | conduction | 8 | 0 | -11.1 | 11.3 | 13.1 | 100% / 100% | -32.0 | 33.7 | 37.0 | 62% / 75% |
| goldak | keyhole | 25 | 0 | +12.2 | 13.5 | 25.0 | 100% / 100% | -59.8 | 59.8 | 368.5 | 0% / 4% |
| goldak | transition | 11 | 0 | -12.6 | 13.1 | 22.8 | 100% / 100% | -60.5 | 60.5 | 136.3 | 0% / 9% |
| goldak | common | 42 | 2 | +2.1 | 13.3 | 23.2 | 100% / 100% | -57.0 | 57.0 | 293.2 | 7% / 14% |

### ku-leuven-ti64-2021 at beam diameter 75 um

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 10 | 4 | -6.3 | 24.1 | 32.0 | 60% / 90% | -44.9 | 44.9 | 60.8 | 10% / 70% |
| rosenthal | conduction | 3 | 4 | -46.6 | 46.6 | 44.8 | 0% / 67% | -60.9 | 60.9 | 49.2 | 0% / 0% |
| rosenthal | transition | 7 | 0 | +11.0 | 14.5 | 24.4 | 86% / 100% | -38.1 | 38.1 | 65.1 | 14% / 100% |
| rosenthal | common | 10 | 4 | -6.3 | 24.1 | 32.0 | 60% / 90% | -44.9 | 44.9 | 60.8 | 10% / 70% |
| eagar-tsai | all | 14 | 0 | -0.7 | 7.6 | 7.9 | 100% / 100% | -51.3 | 51.3 | 73.8 | 7% / 50% |
| eagar-tsai | conduction | 7 | 0 | +2.5 | 10.0 | 8.4 | 100% / 100% | -39.5 | 39.5 | 30.6 | 14% / 86% |
| eagar-tsai | transition | 7 | 0 | -3.9 | 5.2 | 7.5 | 100% / 100% | -63.1 | 63.1 | 99.8 | 0% / 14% |
| eagar-tsai | common | 10 | 4 | -5.3 | 6.2 | 7.9 | 100% / 100% | -59.6 | 59.6 | 87.0 | 0% / 30% |
| goldak | all | 14 | 0 | -18.2 | 18.2 | 17.5 | 100% / 100% | -43.8 | 44.3 | 71.8 | 29% / 50% |
| goldak | conduction | 7 | 0 | -22.2 | 22.2 | 19.1 | 100% / 100% | -27.4 | 28.5 | 27.1 | 57% / 86% |
| goldak | transition | 7 | 0 | -14.1 | 14.1 | 15.8 | 100% / 100% | -60.1 | 60.1 | 97.9 | 0% / 14% |
| goldak | common | 10 | 4 | -17.4 | 17.4 | 18.7 | 100% / 100% | -55.3 | 55.3 | 84.9 | 0% / 30% |

### SENSITIVITY on an unresolved input, not a fit: Lane AMMT rows re-run at the nominal case power from the paper text (150 W case A, 195 W cases B/C) instead of the Table 3 power (137.9/179.2 W)

### Lane AMMT at nominal power (13 rows)

| kernel | regime | n | excluded | W bias % | W MAPE % | W RMSE um | W within +-30% / x0.5-2 | D bias % | D MAPE % | D RMSE um | D within +-30% / x0.5-2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rosenthal | all | 0 | 13 | - | - | - | - | - | - | - | - |
| rosenthal | conduction | 0 | 13 | - | - | - | - | - | - | - | - |
| rosenthal | common | 0 | 13 | - | - | - | - | - | - | - | - |
| eagar-tsai | all | 13 | 0 | +21.8 | 21.8 | 27.1 | 69% / 100% | -0.1 | 8.1 | 3.3 | 100% / 100% |
| eagar-tsai | conduction | 13 | 0 | +21.8 | 21.8 | 27.1 | 69% / 100% | -0.1 | 8.1 | 3.3 | 100% / 100% |
| eagar-tsai | common | 0 | 13 | - | - | - | - | - | - | - | - |
| goldak | all | 4 | 9 | -23.6 | 23.6 | 35.3 | 100% / 100% | +33.1 | 33.1 | 14.1 | 25% / 100% |
| goldak | conduction | 4 | 9 | -23.6 | 23.6 | 35.3 | 100% / 100% | +33.1 | 33.1 | 14.1 | 25% / 100% |
| goldak | common | 0 | 13 | - | - | - | - | - | - | - | - |

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
