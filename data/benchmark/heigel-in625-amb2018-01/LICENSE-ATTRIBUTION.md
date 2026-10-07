# Attribution and source

J. C. Heigel, B. M. Lane, L. E. Levine, "In Situ Measurements of Melt-Pool Length and Cooling Rate During 3D Builds
of the Metal AM-Bench Artifacts", Integrating Materials and Manufacturing Innovation 9 (2020) 31-53,
doi:10.1007/s40192-020-00170-8 (AM-Bench AMB2018-01).

Licence: the article states it is a U.S. government work whose text is not subject to copyright protection in the
United States. Values transcribed from the published article; article not redistributed.

Source read: maintainer-supplied PDF `heigel2020.pdf`, 13,025,592 bytes, SHA-256
6b34fd0cf31a23d40520059b4c17aafc65ea0245d57477190c944b9a9428a34e, read 2026-10-07. Not committed.

`table2_cooling_rates.csv` (10 rows, `digitized=false`): Table 2, cooling-rate summary per feature (bridge; large
L7, medium L9 and small L8 legs) and layer pair, for odd and even layers: number of pixels n, mean, median and SD
in C/s. Values copied as published (thousands separators removed from n); checked against a 220 dpi render.

Definitions (paper text): cooling rate = (1290 C - 1000 C) divided by the time between the two true-temperature
crossings of a pixel, using the bare-plate solidus emissivity 0.221 from Lane et al.; SD is the root sum square of
the average measurement uncertainty and the pixel-to-pixel spread (Table 2 footnote). Build: EOS M270, IN625,
infill 195 W / 800 mm/s, D4sigma 100 um, 0.1 mm hatch, 20 um layers; odd layers scan along X, even layers along Y
(0.48-13 ms reheat gaps). The caption does not say whether the histograms come from Build 1 or Build 2.

Not transcribed: melt-pool lengths (figure-only heat maps and scatter, Figs. 11-12, a time-based per-pixel length),
Table 1 (build log) and Table 3 (thermocouple positions).

Evidence kind: published measurement (thermography-derived, table transcription). Thermal reference target for 3D
builds; not melt-pool geometry and not comparable like-for-like with the screening kernels' G x R.
