# Attribution and source

D. B. Hann, J. Iammi, J. Folkes, "A simple methodology for predicting laser-weld properties from material and laser
parameters", J. Phys. D: Appl. Phys. 44 (2011) 445401, doi:10.1088/0022-3727/44/44/445401.

Licence: (c) 2011 IOP Publishing Ltd. Values transcribed from printed tables with locators; article not redistributed.

Source read: maintainer-supplied PDF `hann2011.pdf`, 1,211,406 bytes, SHA-256
c00854f896f1e21ff81e750d77df0c191621782ff4c6846a471b933665fc84cc, read 2026-10-07. Not committed.

Files:

- `tables3_4_welds.csv` (14 rows, `digitized=false`): AISI 304 bead-on-plate welds (a)-(n): P, U, fibre diameter,
  focus diameter (p. 2 text), printed dH/hs and delta* = depth/sigma. Welding scale; not an app material.

The printed depth relation (p. 4) does not reproduce these printed pairs (3 of 14 within the claimed 10%); recorded.

Loader: `python/lpbf_keyhole_literature.py` (SHA-256 pinned, locator and `digitized` flag on every row). Report: `docs/LPBF_KEYHOLE_BENCHMARK_2026-10-07.*`; notes: `docs/LPBF_KEYHOLE_LITERATURE_NOTES_2026-10-07.md`.
Evidence kind: published measurement / published relation. Comparison only; not experimental validation and not in the calibration training set.
