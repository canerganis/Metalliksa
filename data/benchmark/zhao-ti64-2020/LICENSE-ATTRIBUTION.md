# Attribution and source

C. Zhao, N. D. Parab, X. Li, K. Fezzaa, W. Tan, A. D. Rollett, T. Sun, "Critical instability at moving keyhole tip
generates porosity in laser melting", Science 370 (2020) 1080-1086, doi:10.1126/science.abd1587.

Licence: (c) 2020 The Authors, some rights reserved; exclusive licensee AAAS. Only numbers digitized from Figs. 1A,
2A, 2B are stored, each row with its figure locator; article and figures not redistributed.

Source read: maintainer-supplied PDF `zhao2020.pdf`, 1,039,762 bytes, SHA-256
7aa2a6f96f83cfb4546c6cfbf7d0792a51aadaa2909c811bf54b3382694bb384, read 2026-10-07. Not committed.

Files:

- `fig1a_porosity_boundary_digitized.csv` (20 rows): keyhole-porosity boundary markers (9 bare plate, 11 powder bed)
  with the boundary keyhole depth from Fig. 2A/2B (19 rows). Read uncertainty 4 W, 4 mm/s, 6 um.
- `fig1a_pore_markers_digitized.csv` (35 rows): P-V conditions with a maximum-pore-size marker (pores observed) for
  the bare plate and/or the powder bed.

Ti-6Al-4V, ~400 um plate, ~105 um powder layer, ~100 um spot (taken as 1/e^2 diameter; assumption). The energy
density definition is in the SI (not available).

Loader: `python/lpbf_keyhole_literature.py` (SHA-256 pinned, locator and `digitized` flag on every row). Report: `docs/LPBF_KEYHOLE_BENCHMARK_2026-10-07.*`; notes: `docs/LPBF_KEYHOLE_LITERATURE_NOTES_2026-10-07.md`.
Evidence kind: published measurement / published relation. Comparison only; not experimental validation and not in the calibration training set.
