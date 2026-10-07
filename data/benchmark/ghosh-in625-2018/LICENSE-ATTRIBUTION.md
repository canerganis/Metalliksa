# Attribution and source

S. Ghosh, L. Ma, L. E. Levine, R. E. Ricker, M. R. Stoudt, J. C. Heigel, J. E. Guyer, "Single-Track Melt-Pool
Measurements and Microstructures in Inconel 625", JOM 70 (2018) 1011-1016, doi:10.1007/s11837-018-2771-x.

Licence: (c) 2018 The Minerals, Metals & Materials Society. Values transcribed from the published article;
article not redistributed. Only numbers are copied, each row with its figure locator.

Source read: maintainer-supplied PDF `ghosh2018.pdf`, 853,758 bytes, SHA-256
b89cd530b173102b00e090b09880b1b5b4ab3b5c558570fe302de329cd29bf0a, read 2026-10-07. Not committed.

Files (loader: `python/lpbf_literature_datasets.py`, SHA-256 pinned):

- `fig1_tracks.csv` (7 rows, `digitized=false`): width w and depth h are the numbers printed below each
  cross-section image in Fig. 1 (not read off an axis). Stated SD about 1 um (p. 2). Power per case from the
  Fig. 2 power groups (case 1 = 49 W, 2-4 = 122 W, 5-7 = 195 W); speed from the image position on the Fig. 1
  scan-speed axis (200 / 500 / 800 mm/s). The text confirms case 5 (195 W, 200 mm/s) and case 7 (195 W, 800 mm/s).
- `fig2_length_digitized.csv` (7 rows, `digitized=true`): experimental melt-pool length columns of Fig. 2
  (thermography from the paper's ref. 4, Heigel and Lane, MSEC 2017). Read from the embedded 300 ppi raster: y axis
  calibrated on the gridlines (0.0 mm at pixel row 662, 1.2 mm at row 57); value = error-bar midpoint, which equals
  the bar top within 2 um; SD = half the error-bar span. Read uncertainty about 5 um.

Experiment: bare IN625 plate 25.4 x 25.4 x 3.2 mm, 400 grit, annealed 870 C / 1 h; seven 4 mm tracks on a
commercial LPBF machine; CLSM cross-sections at the track centre after an aqua regia etch. No powder.

Assumptions and open points:

- The experimental spot size is not stated. The loader uses 140 um (the paper's FE model 1/e^2 radius of 70 um,
  its ref. 20) as `beamDiameter_um`; this is an assumption. Lane et al. 2020 give D4sigma 100 um for the NIST
  EOS M270 (CBM). `load_ghosh_in625(beam_diameter_um=...)` overrides it.
- Preheat not stated (20 C assumed). Case 5 is described as the onset of keyholing.
- Case 7 (195 W, 800 mm/s): width 133 um and length ~0.82 mm agree with Lane 2020 CBM case B, but the depth 38 um
  is far below Lane's 91 um. Neither paper explains this; recorded, not resolved.

Overlap: these are not the AMB2018-02 tracks of `lane-in625-amb2018-02/` (different campaign, plate and track
set), so nothing is double-counted. Same laboratory, so not independent in machine/operator terms.

Evidence kind: published measurement. Comparison only; not experimental validation and not in the calibration
training set.
