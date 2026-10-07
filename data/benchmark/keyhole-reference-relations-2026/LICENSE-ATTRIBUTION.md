# Published keyhole relations (transcribed)

`published_relations.csv` (19 rows, `digitized=false`): relations and fitted constants with a locator each, from Gan
et al. 2021 (CC BY 4.0), Huang et al. 2022 (CC BY 4.0), Hann et al. 2011, Cunningham et al. 2019 and Zhao et al. 2020.
Sources, hashes and licences are in the sibling dataset folders. One row is a secondary citation (King et al. 2014
316L threshold as cited by Huang p. 3) and says so; one row (`king2014-keyhole-threshold-316l`) is the primary King et al. 2014
Table 3 constants and the 30 +/- 4 threshold, read from the accepted manuscript (OSTI 1502044, LLNL-JRNL-642426) on 2026-10-07.

Loader: `python/lpbf_keyhole_literature.py` (SHA-256 pinned, locator and `digitized` flag on every row). Report: `docs/LPBF_KEYHOLE_BENCHMARK_2026-10-07.*`; notes: `docs/LPBF_KEYHOLE_LITERATURE_NOTES_2026-10-07.md`.
Evidence kind: published measurement / published relation. Comparison only; not experimental validation and not in the calibration training set.
