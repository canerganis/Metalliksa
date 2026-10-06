# Attribution and source

`table3_absorptance.csv` transcribes Table III ("Optical results from integrating-sphere measurements") of

B. J. Simonds, J. Sowards, J. Hadler, E. Pfeif, B. Wilthan, J. Tanner, C. Harris, P. Williams, J. Lehman,
"Time-Resolved Absorptance and Melt Pool Dynamics during Intense Laser Irradiation of a Metal",
Physical Review Applied 10, 044061 (2018), doi:10.1103/PhysRevApplied.10.044061, PubMed Central PMC7047776
(author manuscript NIHMS1541713).

Source read: the PMC JATS XML from
https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id=7047776, retrieved 2026-10-06,
127,169 bytes, SHA-256 aaf9a603e57e95d37c7db39cbceda30cef7a6edf78f5b8626628aa68f95e86f8 (two fetches
returned identical bytes). Not committed. `python/lpbf_public_datasets.py::build_simonds_table()` regenerates
the CSV from it and refuses an XML with another hash.

Licence: the manuscript's acknowledgments state "This work of the U.S. Government is not subject to U.S.
copyright."

Columns: E_in (J), average irradiance (MW/cm^2), W_weld (um), L_weld (um), E_abs (J), eta_coupling,
time-to-melt (ms), time-to-keyhole (ms). The table's "–" (no keyhole) is stored as blank.

Scope: 316L stainless steel NIST SRM 1155a, polished discs (RMS roughness 79 +- 20 nm), stationary 10 ms
spot welds, 1070 nm, 303 um top-hat spot (full width at 1/e^2), no powder, no scanning. eta_coupling is the
weld-average coupling efficiency from the integrating sphere. The caption does not define the direction of
L_weld; it is stored but not used.

Evidence kind: published measurement (table transcription). The app has no stationary-spot absorptance
model, so the comparison record marks the model comparison unavailable with the reason.
