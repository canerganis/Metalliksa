# Keyhole literature ingestion notes (wave 5d, 2026-10-07)

Ingestion record for `python/lpbf_keyhole_literature.py` and the report `docs/LPBF_KEYHOLE_BENCHMARK_2026-10-07.*`.
Evidence note and bump proposal: `docs/LPBF_KEYHOLE_THRESHOLD_EVIDENCE_2026-10-07.md`.

## Sources read (maintainer-supplied PDFs, not committed)

| paper | file, bytes, SHA-256 | taken | rows | kind | SI needed |
|---|---|---|---|---|---|
| Cunningham 2019, Science 363, 849 | cunningham2019.pdf, 658815 | Fig. 3B/3C vapor-depression depth; Fig. 3A blue/red lines | 69 + 2 | digitized | yes: beam definition, fig. S2, plate data |
| Zhao 2020, Science 370, 1080 | zhao2020.pdf, 1039762 | Fig. 1A boundary (+ Fig. 2A/2B depth); Fig. 1A pore markers | 20 + 35 | digitized | yes: E definition, beam profile |
| Gan 2021, Nat. Commun. 12, 2379 (CC BY) | gan2021.pdf, 1642516 | Eqs. 1, 2, 5-9; 5 Al6061 cases printed in Figs. 1-2 | 5 | printed | yes: Supplementary Data 1 (all Fig. 1a depths) and property set |
| Huang 2022, Nat. Commun. 13, 1170 (CC BY) | huang2022.pdf, 3063398 | Fig. 1b fit, thresholds, hm values; 6 Al7A77/Al regime labels | 6 | printed | yes: Supplementary Table 3 (beta, liquid properties) |
| Hann 2011, J. Phys. D 44, 445401 | hann2011.pdf, 1211406 | Eq. 4, Table 2 ratios, depth relation as printed; Tables 3-4 welds | 14 | printed | none exists |

Full SHA-256 of each PDF copy is in the loader provenance (`source.sha256`) and in each
`data/benchmark/<dataset>/LICENSE-ATTRIBUTION.md`. The 18 published relations are in
`data/benchmark/keyhole-reference-relations-2026/published_relations.csv` (each with a locator).

## Double counting

- Gan 2021 Fig. 1a Ti-6Al-4V points are Cunningham 2019 (Gan ref. 2): Fig. 1a was not digitized at all.
- Huang 2022 Fig. 1b / 2 Ti-6Al-4V points are Cunningham 2019 and Zhao 2020 (Huang refs. 25, 16); IN718/SS304 points
  are from other groups: none were taken from Huang.
- Gan's eta_m for Ti-6Al-4V is Ye et al. 2019 Am, which is already in the repo (`ye-2019-absorptivity`, 0.26) and is
  read from there, not re-transcribed.
- Cunningham and Zhao share the APS beamline/group but are different campaigns, spots and quantities; no P-V-spot
  triple occurs in both (checked by test).

## Digitization method

Figures are embedded 300 ppi JPEG rasters (extracted with `pdfimages`, not committed). Axes were calibrated on the
detected tick marks (pixel columns/rows with long dark runs); values were read on zoomed crops with an overlaid data
grid and checked by re-plotting the read points on the figure.

- Cunningham Fig. 3B/3C: value = marker centre; SD = half error-bar span only where the bar is visible beyond the
  marker. Read uncertainty 4 um (6 um in crowded clusters at 156/208/260/312/416 W), power 3 W.
- Cunningham Fig. 3A lines: least-squares straight line through the coloured line pixels (residual SD 0.4 W blue,
  1.2 W red); read uncertainty 4 W. Blue: P = 0.04691 v + 96.25; red: P = 0.08448 v + 102.13 (W, mm/s), 95 um.
- Zhao Fig. 1A: marker centres, 4 W / 4 mm/s; Fig. 2A/2B depths 6 um. Boundary depths were matched by value between
  Fig. 2A (vs V) and Fig. 2B (vs P). Inconsistency recorded: Fig. 2 has a bare point at ~375 mm/s / 128 W with no
  Fig. 1A circle, and the Fig. 1A circle at ~222 mm/s / 82 W has no Fig. 2 depth.

## Things found in the papers that do not add up

- Hann 2011 p. 4 depth relation as printed (sqrt(dH/hs - 1); sqrt(dH/hs - 10) above Hv) reproduces only 3 of the 14
  printed Table 3/4 (dH/hs, delta*) pairs within the claimed 10% (e.g. dH/hs 27.4: relation 4.2 vs printed 12.5).
  Recorded; not used for any verdict.
- Gan's keyhole number cannot be reproduced without the SI property set: with the app's Ti-6Al-4V properties Eq. 2
  over-predicts the Cunningham depths 2.4-4.9x (Ke factor needed 0.26-0.45).

## Not done

- KU Leuven 316L/Ti64 regime labels (already in the repo) were not added to this benchmark; they should be part of
  any threshold bump.
- No UI was wired. `docs/LPBF_KEYHOLE_BENCHMARK_2026-10-07.view.json` is a read-only summary a scorecard or the
  process-window view could show later (label: literature comparison, screening only).

## Added with the keyhole-regime bump

- Cunningham Supplementary Materials read (`aav4687_cunningham_sm.pdf`, SM pp. 2-5): 1/e^2 spot, Fig. 3A red line = melt-pool
  transition at d/w ~ 0.5, "at higher velocities, even the deep vapor depressions become more stable" (p. 5).
- Gan 2021 SI and Supplementary Data 1/2 read: Data 1 Ti-6Al-4V rows (71) are ingested as
  `data/benchmark/gan-keyhole-2021/supplementary_data1_ti64.csv` (cross-check only); SI Eqs. 23/37 define r0 as the 1/e^2
  radius; Data 2 lists r0 = 75 um for the 140 um cases (inconsistent with Data 1).
- King et al. 2014 accepted manuscript (OSTI 1502044, LLNL-JRNL-642426): Table 3 constants and the 30 +/- 4 threshold are
  now a primary-source row in `published_relations.csv` (`king2014-keyhole-threshold-316l`).

