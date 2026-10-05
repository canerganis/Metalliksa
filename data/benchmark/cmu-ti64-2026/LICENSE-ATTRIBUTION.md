# Attribution and license

The compact ST and MT measurement tables are derived from the CMU KiltHub record
https://doi.org/10.1184/R1/25696293.v1, licensed CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/).

`st_measurements.csv` and `mt_measurements.csv` preserve the source fields in compact CSV form. ST has no
power column; no power is inferred. Neither source table reports beam diameter, layer thickness, preheat, or
absorptivity. The loader retains the observations, while the comparison harness excludes them from kernel
predictions whenever required inputs are missing. `Slice` is an index and not evidence of independent builds.

Source file SHA-256: `STMeasurements.csv` 2e6db89484a91b8c8c5112bc1f68dbe7388dfddea19d92428e4ae160e0372e5c;
`MTMeasurements.csv` 871a915a3850754af3174c2cd14295d3351ab745bed4f3a9a4bc31d8dd693743.

Please attribute: CMU KiltHub, Ti-6Al-4V melt-pool variability measurements,
https://doi.org/10.1184/R1/25696293.v1. Comparison only; not experimental validation.
