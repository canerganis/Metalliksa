# Attribution and source

R. Cunningham, C. Zhao, N. Parab, C. Kantzos, J. Pauza, K. Fezzaa, T. Sun, A. D. Rollett, "Keyhole threshold and
morphology in laser melting revealed by ultrahigh-speed x-ray imaging", Science 363 (2019) 849-852,
doi:10.1126/science.aav4687.

Licence: (c) 2019 The Authors, some rights reserved; exclusive licensee AAAS. Only numbers digitized from Fig. 3 are
stored, each row with its figure locator; article and figures not redistributed.

Source read: maintainer-supplied PDF `cunningham2019.pdf`, 658,815 bytes, SHA-256
995151c40f0ca70a525b0fde2fc0fd067ae6cb52aa4943c5d89e67cd683f3fe4, read 2026-10-07. Not committed.

Files:

- `fig3bc_vapor_depth_digitized.csv` (69 rows, `digitized=true`): Ti-6Al-4V bare plate vapor-depression depth vs
  power, per scan speed, 95 um (Fig. 3B, 46) and 140 um (Fig. 3C, 23) spots. Marker centre; SD = half error-bar span
  where visible; read uncertainty 4-6 um, power 3 W.
- `fig3a_transition_lines_digitized.csv` (2 rows, `digitized=true`): straight-line fits of the blue (vapor-depression
  transition) and red (melt-pool transition) dashed lines of Fig. 3A (95 um spot).

Supplementary materials (methods, beam definition, fig. S2) were not available: spot = 1/e^2 diameter and 20 C are
assumptions. Gan 2021 and Huang 2022 re-plot these data; they are not ingested again.

Loader: `python/lpbf_keyhole_literature.py` (SHA-256 pinned, locator and `digitized` flag on every row). Report: `docs/LPBF_KEYHOLE_BENCHMARK_2026-10-07.*`; notes: `docs/LPBF_KEYHOLE_LITERATURE_NOTES_2026-10-07.md`.
Evidence kind: published measurement / published relation. Comparison only; not experimental validation and not in the calibration training set.
