# Attribution and source

`tables2_3_thermal.csv` transcribes NIST AM-Bench "AMB2022-03 Benchmark Measurements and Challenge Results"
(Measurement and Result Descriptions v1.0, "Last updated on 07/21/2022"):

- Table 1 (page 2): case number, laser power, scan speed, D4sigma spot size.
- Table 2 (page 4): TTAM [s], TSCR [C/s], TLCR [C/s].
- Table 3 (page 4): TTCR [C/s], listed as supplementary data "for reference", not a challenge quantity.

Source: https://www.nist.gov/system/files/documents/2022/07/27/AMB2022-03Measurement%20and%20%20Result%20Descriptions_v1.0.pdf
retrieved 2026-10-06 (www.nist.gov host, not data.nist.gov), 1,195,056 bytes, `%PDF-1.7`, SHA-256
dea3feddec2bc23281ae86c6fd9cee4d0a934a4304501fe0c038f24c7dbc9db0. The PDF is not committed.
`python/lpbf_public_datasets.py::build_nist_thermal_table()` regenerates the CSV from it (optional `pypdf`)
and refuses a PDF with another hash.

Licence: not stated on the document. It is a NIST publication; US public domain is an inference, not confirmed.

Processing assumptions stated in the document (page 2): values come from 30 centerline pixels at a nominally
steady-state location and are the mean of three tracks; no undercooling is assumed; the emissivity is set so
that the apparent solidification inflection equals the IN718 solidus/liquidus midpoint. The TTAM challenge
definition (page 1) gives that midpoint as "assumed to be 1 298 C"; the explicit "Ttrans = 1298 C" with
emissivity 0.5 (page 7) belongs to the pad PTAM/PSCR processing. Page 3 warns that TAM and SCR errors may be
largest at the largest spot size (case 1.2).

These are the same seven cases as the IN718 optical geometry record already in the app (mds2-2718 /
AMB2022-03 Table 4).

Evidence kind: published measurement (thermography-derived, table transcription). No like-for-like model
comparison exists in the app for these quantities; the comparison record marks it unavailable with the reason.
