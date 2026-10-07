# Attribution and source

J. Trapp, A. M. Rubenchik, G. Guss, M. J. Matthews, "In situ absorptivity measurements of metallic powders during
laser powder-bed fusion additive manufacturing", Applied Materials Today 9 (2017) 341-349,
doi:10.1016/j.apmt.2017.08.006.

Licence: CC BY 4.0 (open access, stated on the article). Values transcribed from the published article; article
not redistributed. Only numbers are copied, each row with its figure locator.

Source read: maintainer-supplied PDF `trapp2017.pdf`, 2,797,820 bytes, SHA-256
f305411d5746e27a1049b3c894ea1f82884b282d97d69110012894617baa3c06, read 2026-10-07. Not committed.

All values are DIGITIZED (`digitized=true`) from the embedded 300 ppi JPEG figures: axes calibrated on the
detected tick marks; symbol centroids located with colour masks plus morphological erosion (lines and error bars
removed); overlapping symbols resolved from zoomed crops and flagged. Pixel scales: Fig. 3(a) 92.3 px per 0.1
absorptivity, 1.29 px/um (right axis), 1.74 px/W; Fig. 4 97.7 px per 0.1, 1.54 px/W; Fig. 6(a) 85.5 px per 0.1,
4.13 px/W; Fig. 6(b) 86.3 px per 0.1, 1.36 px/W; Fig. 7 88.7 px per 0.1, 1.50 px/W. The same 316L series read from
different figures agree within 0.002 absorptivity (Fig. 3(a) vs Fig. 4 at 500 mm/s; Figs. 4, 6(b) and 7 at
1500 mm/s). Stated read uncertainty: 0.005 absorptivity (0.008 for overlapping symbols), 0.5-1.5 W, 3 um.

Files (loader: `python/lpbf_literature_datasets.py`, SHA-256 pinned):

- `fig3a_tracks_digitized.csv` (11 rows): 316L bare-disc track width (open circles) and depth (filled circles) at
  500 mm/s vs power, right axis of Fig. 3(a). No depth symbol is plotted at 117 W (blank). `power_label_W` is the
  power printed under the Fig. 3(b) cross-sections where one exists. These are the melt-pool rows.
- `absorptivity_digitized.csv` (107 rows, seven series): effective absorptivity vs power. 316L bare disc at 100
  (Fig. 6(a)), 500 (Fig. 4) and 1500 mm/s (Fig. 6(b)); 316L with a 100 um powder layer at 100 (Fig. 6(a)) and
  1500 mm/s (Fig. 6(b)); W and Al 1100 discs at 1500 mm/s (Fig. 7). The four 316L 1500 mm/s points marked
  "initially penetrated disc" in Fig. 4 are flagged. Absorptivity reference data, not melt-pool rows. Literature
  points drawn at P = 0 are not measurements of this work and are excluded. Error bars (two repeats) are not
  digitized.

Experiment: 10 mm discs laser-cut from 0.5 mm rolled 316L and W sheet and 0.6 mm Al 1100 sheet, on a porous
alumina holder (not a semi-infinite plate); 1070 nm cw Yb fibre laser, Gaussian 60 +- 5 um 1/e^2 diameter, argon
flow; absorptivity from calorimetry (energy to heat the disc divided by P l / v), mean of two measurements.
Powder: Concept Laser 316L, mean 29.9 um, 100 um layer set by a cup rim.

Evidence kind: published measurement, digitized from figures. Reference data only; it does not validate the
kernels' constant absorptivity_IR and is not a calibration target.
