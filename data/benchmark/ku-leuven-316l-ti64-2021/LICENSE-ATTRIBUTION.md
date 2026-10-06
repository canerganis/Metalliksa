# Attribution and license

`source/` holds four unmodified CSV files downloaded on 2026-10-06 from Figshare. Each item is marked
**CC0** (Figshare API `license.name`), uploaded by Viktor Coen (KU Leuven), published 2021-07-22. They are
committed because they are small (25,897 bytes in total) and the tests check them byte for byte.

| File | Figshare DOI | Download URL | Bytes | MD5 (Figshare) | SHA-256 (local) |
|---|---|---|---|---|---|
| `Data Stainless Steel 316L (1).csv` (raw sections) | 10.6084/m9.figshare.15035733.v1 | https://ndownloader.figshare.com/files/28914423 | 13265 | a8a7a365dcf26ac3480181c87dd4f510 | 3f740254deb645fa2c27f64686bc47d1e606a49a8d457a8046516c121a46a13b |
| `Data Stainless Steel 316L (2).csv` (processed) | 10.6084/m9.figshare.15035703.v1 | https://ndownloader.figshare.com/files/28914396 | 6127 | 43b448c9f5d78560f209ebb18666745c | 9d55aca22193e8bb9f5a5656497a0abbb987d1b2b2cd091d21b4a25764fc9225 |
| `Data Ti-6Al-4V (1).csv` (raw sections) | 10.6084/m9.figshare.15035709.v1 | https://ndownloader.figshare.com/files/28914390 | 4746 | f03ed22aa39c0ba98107a94d6030043a | 2bac87febd59c8ea8022e088cb308026bbedbfd0c627c03c05df2a0747c59705 |
| `Data Ti-6Al-4V (2).csv` (processed) | 10.6084/m9.figshare.15035712.v2 | https://ndownloader.figshare.com/files/28914477 | 1759 | 12815f222f8b2d49ebe8288906191e73 | 62ceb073a80d4b6b4e524d94cc88e07b8cabc3e54f3cab252d82ca7a90c3ad98 |

The local MD5 of every file equals the Figshare `computed_md5`.

`conditions.csv` is derived by `python/lpbf_public_datasets.py::build_ku_wave2_table()` from those files:

- From each processed `(2)` file only `Sample`, `P`, `v`, `w exp`, `d exp`, `R exp` and `melting regime` are
  read, located by header name. The `w model`, `d model`, `R model` and `* error` columns are analytical-model
  outputs and are excluded. The trailing `nb. of samples` column belongs to the file's regime-summary block,
  not to a row, and is not used.
- `raw_sections_n`, `raw_mean_width_um` and `raw_mean_depth_um` are computed here from the raw `(1)` file
  (sections that have both a depth and a width). For 316L they equal `w exp` / `d exp`; for Ti-6Al-4V they
  differ by a few micrometres, so the authors' processing is not fully reproduced.
- Units: every raw section row carries the unit cell `µm`. Width operator: the raw header says `Width`; the
  authors' `R = d/w` and their keyhole threshold `R > 1` imply full width (an inference; the article was
  not read).
- 316L conditions 41, 42, 47 and 48 (600 W at 400, 500, 1000 and 1100 mm/s) are blank in the processed
  file and are not compared.

Evidence kind: published measurement (measured cross-sections). Not used to fit anything.

Not established here: the beam diameter. The kernels are run at 37.5 um, the value the repo's 2026-10-05
KU Leuven IN718 record attributes to the paper. The article itself (Coen, Goossens, Van Hooreweder,
J. Mater. Process. Technol. 304 (2022) 117547, doi:10.1016/j.jmatprotec.2022.117547) returned HTTP 403, so
diameter vs radius and the beam definition are unverified. A 75 um re-run is reported as a sensitivity.
Powder layer, preheat and absorptivity are not stated in these files. The 2026-10-05 KU Leuven IN718 record cites a
60 um powder layer from the Coen article; that article could not be read here (HTTP 403), so no layer is carried
over (the screening kernels ignore layer thickness, so there is no numeric effect).

Please attribute: V. Coen, KU Leuven, melt-pool measurements of SS316L and Ti-6Al-4V, Figshare (CC0), DOIs
above; manuscript doi:10.1016/j.jmatprotec.2022.117547. Comparison only; not experimental validation.
