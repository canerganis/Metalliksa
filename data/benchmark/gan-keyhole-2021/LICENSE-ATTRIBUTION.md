# Attribution and source

Z. Gan, O. L. Kafka, N. Parab, C. Zhao, L. Fang, O. Heinonen, T. Sun, W. K. Liu, "Universal scaling laws of keyhole
stability and porosity in 3D printing of metals", Nat. Commun. 12 (2021) 2379, doi:10.1038/s41467-021-22704-0.

Licence: CC BY 4.0 (article). Values transcribed with locators; article not redistributed.

Source read: maintainer-supplied PDF `gan2021.pdf`, 1,642,516 bytes, SHA-256
85dc767c0a91020f97119cc53139b9718e2f3523a5e30ddb4ce6ccb36ad0b074, read 2026-10-07. Not committed.

Files:

- `printed_cases.csv` (5 rows, `digitized=false`): Al6061 cases whose P, V and Ke are printed in Fig. 2 and the Fig. 1b/1c
  captions; spot from the Fig. 1a legend. Al6061 is not an app material (labels only).

- `supplementary_data1_ti64.csv` (71 rows, `digitized=false`): the Ti-6Al-4V rows of Supplementary Data 1 as published
  (P, eta, V, d, r0, Gan Table 1 properties, keyhole depth e, length, tan(theta); SI units), copied from
  `gan2021_data1.xlsx` (18,260 bytes, SHA-256 b52d9173eb3a63983dd87c56b2720abd419a200e9594b863218de13da6a7597a, read
  2026-10-07, Nat. Commun. supplementary data, CC BY 4.0; the xlsx is not committed). These are the Cunningham 2019
  Ti-6Al-4V cases (Gan ref. 2): a cross-check of the digitized Cunningham depths and of Gan Eq. (2), never a second
  dataset. Supplementary Data 2 lists r0 = 75 um for the 140 um cases (Data 1 and the SI Eqs. 23/37 give r0 = 70 um =
  d/2): a Gan-internal inconsistency, recorded and not used.

The relations (Eqs. 1, 2, 5-9) are in `../keyhole-reference-relations-2026/published_relations.csv`. Gan's
Al6061 block of Supplementary Data 1 is not ingested. Gan's Ti-6Al-4V points are Cunningham
2019 data and are not ingested.

Loader: `python/lpbf_keyhole_literature.py` (SHA-256 pinned, locator and `digitized` flag on every row). Report: `docs/LPBF_KEYHOLE_BENCHMARK_2026-10-07.*`; notes: `docs/LPBF_KEYHOLE_LITERATURE_NOTES_2026-10-07.md`.
Evidence kind: published measurement / published relation. Comparison only; not experimental validation and not in the calibration training set.
