# Attribution and license

The compact condition table is derived from `Data_Inconel718.csv` in the KU Leuven Figshare record
https://doi.org/10.6084/m9.figshare.15035706.v1, which is marked CC0.

The source has 48 numbered conditions. It uses comma decimal separators for measured dimensions and contains
ragged model/summary columns; only sample number, power, speed, source `w exp`, source `d exp`, and a numeric
sample count where present are retained. The source CSV does not state width/depth units, and the paper's
half-width measurement wording does not resolve whether `w exp` is half-width or full width. The loader
preserves source dimension values without assigning `um`; comparison rows are explicitly excluded from
numeric kernel statistics until those semantics are resolved.

Source file SHA-256: `Data_Inconel718.csv`
029f5c6992bd261891b30966d3bcc01ff327cd2cf1c7a6963e94de075766e1e5.

Please attribute: KU Leuven, IN718 melt-pool measurements, Figshare,
https://doi.org/10.6084/m9.figshare.15035706.v1. Comparison only; not experimental validation.
