# Attribution and source

`table3_tracks.csv` and `table4_summary.csv` are transcriptions of Tables 3 and 4 of

B. Lane, J. Heigel, R. Ricker, I. Zhirnov, V. Khromschenko, J. Weaver, T. Phan, M. Stoudt, S. Mekhontsev,
L. Levine, "Measurements of melt pool geometry and cooling rates of individual laser traces on IN625 bare
plates", Integrating Materials and Manufacturing Innovation 9(1) (2020), doi:10.1007/s40192-020-00169-1,
PubMed Central PMC8194244 (author manuscript NIHMS1686029). AM-Bench test AMB2018-02.

Source read: the PMC JATS XML from
https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id=8194244, retrieved 2026-10-06,
185,979 bytes, SHA-256 19757c67b91aeee5b4575722482103649dc98d03167bced14d64244f5313b460 (two fetches
returned identical bytes). The XML is not committed. `python/lpbf_public_datasets.py::build_lane_tables()`
regenerates both CSVs from it and refuses an XML with another hash.

Licence: none is stated. The PMC permissions text says the file "is available for text mining" and may be
used under fair use. The authors are NIST staff, but the retrieved XML carries no explicit US-government-work
statement. Only numeric table values are transcribed, with this citation.

Transcription rules: values are copied as published strings. Footnote markers are moved to `footnotes`:
`a` (AMMT case C emittance 0.519 assumed, sigma not available), `b` (AMMT 1290-1000 C cooling rate not
reported, blank), `c` (AMMT cooling rates "should not be used, but are printed here for reference").
`cooling_rate_use` is `do-not-use (Table 3 footnote c)` for every AMMT row; CBM rows are `exemplar, not
reference (paper conclusions)`. `table4_summary.csv` carries the same flag per class: Table 4 takes AMMT length
and cooling rate from the AMMT-20 us tracks only (Table 4 caption), so the AMMT-A/B/C cooling rates are the
same values Table 3 footnote c marks as not to be used (`do-not-use (same AMMT-20us values as Table 3,
footnote c)`); Table 4 itself cites no footnote for them. This column is added, not published. `nominal_case_power_W` is the case power in the paper text (A 150 W, B/C 195 W).

Open question, not resolved: the Fig. 2 caption says "Laser power values indicated are the applied laser
power"; Table 3 lists 137.9/179.2 W for the AMMT cases and the Section 2 case definitions give 150/195 W.
Whether these are applied vs commanded powers is not stated explicitly, and the Fig. 2 image was not read.
Kernel inputs use the Table 3 value; a nominal-power re-run is reported as a sensitivity.

Columns: Table 3 "Cross Section (um)" appears twice; the first is width, the second depth (the CBM track
means reproduce Table 4 Class Width / Class Depth). Each track has N = 3 microscopy measurements; sigma is
their spread, not an uncertainty. Table 4 `*_Umean` is the standard uncertainty of the mean (it matches the
"Standard Uncertainty of the Mean" rows of Tables 5-7).

Evidence kind: published measurement (table transcription). Comparison only; not experimental validation.
