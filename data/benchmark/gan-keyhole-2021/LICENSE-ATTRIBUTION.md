# Attribution and source

Z. Gan, O. L. Kafka, N. Parab, C. Zhao, L. Fang, O. Heinonen, T. Sun, W. K. Liu, "Universal scaling laws of keyhole
stability and porosity in 3D printing of metals", Nat. Commun. 12 (2021) 2379, doi:10.1038/s41467-021-22704-0.

Licence: CC BY 4.0 (article). Values transcribed with locators; article not redistributed.

Source read: maintainer-supplied PDF `gan2021.pdf`, 1,642,516 bytes, SHA-256
85dc767c0a91020f97119cc53139b9718e2f3523a5e30ddb4ce6ccb36ad0b074, read 2026-10-07. Not committed.

Files:

- `printed_cases.csv` (5 rows, `digitized=false`): Al6061 cases whose P, V and Ke are printed in Fig. 2 and the Fig. 1b/1c
  captions; spot from the Fig. 1a legend. Al6061 is not an app material (labels only).

The relations (Eqs. 1, 2, 5-9) are in `../keyhole-reference-relations-2026/published_relations.csv`. Supplementary
Data 1 (all Fig. 1a keyhole depths) and Gan's property set were not available. Gan's Ti-6Al-4V points are Cunningham
2019 data and are not ingested.

Loader: `python/lpbf_keyhole_literature.py` (SHA-256 pinned, locator and `digitized` flag on every row). Report: `docs/LPBF_KEYHOLE_BENCHMARK_2026-10-07.*`; notes: `docs/LPBF_KEYHOLE_LITERATURE_NOTES_2026-10-07.md`.
Evidence kind: published measurement / published relation. Comparison only; not experimental validation and not in the calibration training set.
