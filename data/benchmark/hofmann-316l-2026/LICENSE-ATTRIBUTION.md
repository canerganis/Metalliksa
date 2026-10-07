# Attribution and license

`meltpool_geometry.csv` is a re-formatted copy of `MeltpoolGeometryData.csv` from the Zenodo record
https://zenodo.org/records/16979848 (DOI 10.5281/zenodo.16979848, v1, 2025-08-28), licensed
**CC BY 4.0** (https://creativecommons.org/licenses/by/4.0/).

Changes made: the source header (a single quoted pseudo-field) was replaced by plain column names
`index,P_laser_W,v_scan_mm_s,d_laser_mm,t_powder_um,weld_width_um,penetration_depth_um,molten_area_um2,balling`;
all 677 data rows are copied verbatim as text. The source header labels the area column `[um]`; the values are um^2.

Source file: 29,660 bytes, MD5 2c107f3ac12cd38a0f1eb9f75a469000, SHA-256
5dd0629b3add839997fd54c3e4d89f90c1f2e4e5e717bede2c72e0c58cefd417.

Please cite: Hofmann et al., melt-pool geometry data for 316L single tracks (Aconity Midi), Zenodo,
doi:10.5281/zenodo.16979848; associated paper Hofmann et al., Materials & Design 262 (2026) 115459,
doi:10.1016/j.matdes.2026.115459.

Depth datum and spot definition (settled from the associated paper, Hofmann et al. 2026, Fig. 2 and Sec. 2.1-2.2):
`penetration_depth_um` is measured from the original substrate surface (the powder/substrate interface) down to the
melt-pool bottom, and `weld_width_um` is taken at that same level (Fig. 2, right, "Schematic melt pool
parametrisation"); for `t_powder_um` > 0 the consolidated layer above the datum is NOT part of the depth. The laser is
a 500 W single-mode Gaussian source with a 50 um focus diameter, defocused to 80/110/140 um (Sec. 2.1, Table 2); the
paper does not state the diameter definition, so 1/e^2 remains an assumption. Powder: D10/D50/D90 = 17.5/30.4/46.6 um
(Table 1), layers of 0/30/60 um set with thickness gauges; the packing density is not stated. The data file is unchanged
by this note (its SHA-256 pin is unaffected).

These are measured values from a third party. They are used in this repository only to COMPARE screening
kernels (`python/tools/lpbf_dataset_comparison.py`); this is not experimental validation.
