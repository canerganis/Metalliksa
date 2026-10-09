# Regime-dependent absorptivity: results (2026-10-09)

**Screening (literature estimate): regime-dependent absorptivity law, not validation.** Screening evaluation, not validation. experimentalValidation=false, validationStatus=unvalidated, productionReady=false.

## Decision: FAIL

Reason: at least one kernel FAILs, verdicts identical across the grid.

Computed mechanically from the pre-registered rule (`docs/research/PREDECLARED_regime_absorptivity_2026-10-09.md`, Amendment 1 commit `fe30687d`). Only arm A0 can produce PASS; no result text claims the law improves depth on every source.

## Kernel verdict by reading (arm A0)

| kernel | ku37.5|gh140|published|table3 | ku37.5|gh140|published|nominal | ku37.5|gh140|layer|table3 | ku37.5|gh140|layer|nominal | ku37.5|gh100|published|table3 | ku37.5|gh100|published|nominal | ku37.5|gh100|layer|table3 | ku37.5|gh100|layer|nominal | ku75|gh140|published|table3 | ku75|gh140|published|nominal | ku75|gh140|layer|table3 | ku75|gh140|layer|nominal | ku75|gh100|published|table3 | ku75|gh100|published|nominal | ku75|gh100|layer|table3 | ku75|gh100|layer|nominal |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| eagar-tsai | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| goldak | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| rosenthal | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |

## Criteria, primary reading `ku37.5|gh140|published|table3`

| kernel | E | T | C1 | C2 | C3 | C4 | C5 | C6 | verdict |
|---|---|---|---|---|---|---|---|---|---|
| eagar-tsai | 4 | 4 | FAIL | FAIL | FAIL | FAIL | pass | pass | FAIL |
| goldak | 4 | 4 | FAIL | FAIL | FAIL | FAIL | pass | pass | FAIL |
| rosenthal | 4 | 4 | FAIL | pass | pass | pass | FAIL | pass | FAIL |

## Depth and width, arm A0 against the baseline, primary reading `ku37.5|gh140|published|table3`

| kernel | source | quantity | n (P) | clusters | MAPE base | MAPE A0 | skill | CI95 | bias base | bias A0 |
|---|---|---|---|---|---|---|---|---|---|---|
| eagar-tsai | ghosh-in625-2018 | depth | 1 | 1 | 0.077 | 0.204 | -1.643 | [-1.643, -1.643] | -0.077 | 0.204 |
| eagar-tsai | ghosh-in625-2018 | width | 1 | 1 | 0.114 | 0.111 | 0.024 | [0.024, 0.024] | -0.114 | 0.111 |
| eagar-tsai | hofmann-316l-2026 | depth | 513 | 373 | 0.355 | 0.368 | -0.038 | [-0.064, -0.013] | 0.147 | 0.217 |
| eagar-tsai | hofmann-316l-2026 | width | 328 | 248 | 0.092 | 0.210 | -1.279 | [-1.536, -1.062] | -0.032 | 0.190 |
| eagar-tsai | ku-leuven-316l-2021 | depth | 44 | 44 | 0.290 | 0.291 | -0.003 | [-0.010, 0.000] | -0.129 | -0.128 |
| eagar-tsai | ku-leuven-ti64-2021 | depth | 14 | 14 | 0.286 | 0.290 | -0.012 | [-0.047, 0.000] | 0.212 | 0.216 |
| eagar-tsai | lane-in625-2020 | depth | 6 | 2 | 0.517 | 0.422 | 0.183 | [0.170, 0.199] | -0.517 | -0.422 |
| eagar-tsai | lane-in625-2020 | width | 6 | 2 | 0.091 | 0.032 | 0.646 | [-0.105, 0.870] | -0.091 | 0.032 |
| eagar-tsai | totis-ti64-2021 | depth | 72 | 72 | 0.280 | 0.255 | 0.091 | [0.043, 0.145] | -0.168 | -0.142 |
| goldak | ghosh-in625-2018 | depth | 1 | 1 | 0.013 | 0.260 | -19.214 | [-19.214, -19.214] | -0.013 | 0.260 |
| goldak | ghosh-in625-2018 | width | 1 | 1 | 0.166 | 0.071 | 0.570 | [0.570, 0.570] | -0.166 | 0.071 |
| goldak | hofmann-316l-2026 | depth | 513 | 373 | 0.365 | 0.388 | -0.065 | [-0.092, -0.039] | 0.181 | 0.251 |
| goldak | hofmann-316l-2026 | width | 328 | 248 | 0.114 | 0.194 | -0.706 | [-0.915, -0.524] | -0.070 | 0.159 |
| goldak | ku-leuven-316l-2021 | depth | 44 | 44 | 0.290 | 0.292 | -0.007 | [-0.023, 0.000] | -0.129 | -0.127 |
| goldak | ku-leuven-ti64-2021 | depth | 14 | 14 | 0.286 | 0.294 | -0.025 | [-0.100, 0.000] | 0.212 | 0.219 |
| goldak | lane-in625-2020 | depth | 6 | 2 | 0.463 | 0.372 | 0.196 | [0.175, 0.225] | -0.463 | -0.372 |
| goldak | lane-in625-2020 | width | 6 | 2 | 0.181 | 0.033 | 0.815 | [0.772, 0.848] | -0.181 | -0.033 |
| goldak | totis-ti64-2021 | depth | 72 | 72 | 0.272 | 0.247 | 0.091 | [0.044, 0.147] | -0.159 | -0.133 |
| rosenthal | ghosh-in625-2018 | depth | 1 | 1 | 0.598 | 0.509 | 0.149 | [0.149, 0.149] | 0.598 | 0.509 |
| rosenthal | ghosh-in625-2018 | width | 1 | 1 | 0.020 | 0.037 | -0.902 | [-0.902, -0.902] | 0.020 | -0.037 |
| rosenthal | hofmann-316l-2026 | depth | 513 | 373 | 0.636 | 0.504 | 0.207 | [0.193, 0.221] | 0.599 | 0.420 |
| rosenthal | hofmann-316l-2026 | width | 328 | 248 | 0.257 | 0.140 | 0.455 | [0.425, 0.483] | 0.209 | 0.067 |
| rosenthal | ku-leuven-316l-2021 | depth | 44 | 44 | 0.440 | 0.453 | -0.028 | [-0.139, 0.065] | -0.084 | -0.223 |
| rosenthal | ku-leuven-ti64-2021 | depth | 14 | 14 | 0.690 | 0.523 | 0.241 | [0.166, 0.335] | 0.668 | 0.454 |
| rosenthal | lane-in625-2020 | depth | 6 | 2 | 0.294 | 0.312 | -0.059 | [-0.060, -0.057] | -0.294 | -0.312 |
| rosenthal | lane-in625-2020 | width | 6 | 2 | 0.104 | 0.126 | -0.211 | [-0.306, -0.128] | -0.104 | -0.126 |
| rosenthal | totis-ti64-2021 | depth | 72 | 72 | 0.375 | 0.323 | 0.139 | [0.041, 0.210] | 0.156 | 0.008 |

## Pooled significance endpoints (C2 depth, C3 width), arm A0, primary reading

- eagar-tsai: pooled depth skill 0.007 CI95 [-0.009, 0.022]; pooled width skill -1.279 CI95 [-1.536, -1.062]
- goldak: pooled depth skill -0.006 CI95 [-0.026, 0.011]; pooled width skill -0.706 CI95 [-0.915, -0.524]
- rosenthal: pooled depth skill 0.158 CI95 [0.123, 0.190]; pooled width skill 0.455 CI95 [0.425, 0.483]

## Arms against the same rule (reported; only A0 can produce PASS)

| arm | eagar-tsai | goldak | rosenthal |
|---|---|---|---|
| A0 | FAIL | FAIL | FAIL |
| F | FAIL | FAIL | FAIL |
| G | FAIL | FAIL | FAIL |
| K | FAIL | FAIL | FAIL |
| S1 | FAIL | FAIL | FAIL |
| S2 | FAIL | FAIL | FAIL |
| S3 | FAIL | FAIL | FAIL |
| S4 | FAIL | FAIL | FAIL |

## Diagnostics (not in the verdict)

- D2 absorptance shape (Trapp 316L discs, digitized): n=39, MAE law 0.122, MAE flat 0.42 0.176
- D3 envelope: A(H) in [0.350, 0.700], inside [0.25, 0.80]: True
- D4 conduction identity: pass (0 violations)
- Parity (stage 2): pass, 2304 kernel inputs, max rel err 0.00e+00
- D1 containment, D5 Cunningham regime agreement, D6 Trapp geometry, D7 ungated widths and the catalog sentinels are in the JSON record.

  - D1 eagar-tsai:A0: 0.065 of 46
  - D1 eagar-tsai:baseline: 0.043 of 46
  - D1 goldak:A0: 0.109 of 46
  - D1 goldak:baseline: 0.043 of 46
  - D1 rosenthal:A0: 0.326 of 46
  - D1 rosenthal:baseline: 0.609 of 46
  - D5 eagar-tsai:A0: accuracy 0.717 (n=46), non-boundary 0.727 (n=44)
  - D5 eagar-tsai:baseline: accuracy 0.804 (n=46), non-boundary 0.818 (n=44)
  - D5 goldak:A0: accuracy 0.674 (n=46), non-boundary 0.705 (n=44)
  - D5 goldak:baseline: accuracy 0.848 (n=46), non-boundary 0.864 (n=44)
  - D5 rosenthal:A0: accuracy 0.935 (n=46), non-boundary 0.932 (n=44)
  - D5 rosenthal:baseline: accuracy 0.935 (n=46), non-boundary 0.932 (n=44)

## Provenance

- config sha256 `8d629929370d8fdf2f60a3d4de72f3ccc77290c0eee58cc5ad8f230edaba91f9`; pre-registration LF sha256 `ccc365f120cbe29c98997aa6b1d9d3e3eeb795359ab9631ac534100e112d76f4`
- repo commit `8855df839f88851f9d1b4c708771fbc4a1110427`; frozen implementation fingerprint `ec7e1f7a6606e937e448fefe97549b49a7ddfe7b95376b93867ae007b0c12555`
- stage-1 record sha256 `a8aceee09eee93e91940660b29ec61197647dc107afe972eb1a2fe3c5caac44d`; stage-2 record sha256 `0e6160bc9d3b5d39714b3766aa37e8be92b69b453503bb97ae415632a83bf27b`
- bootstrap B=1000, seed 0; lane axis active: True; grid readings: 16
- dataset table sha256s: cunningham-ti64-2019 `223583bb6eead835ebbc0071fae0619408617bacf616790f9226267dacf34a03`; ghosh-in625-2018 `79ee2d58b26c56dc88eadd5b1b0f73fb8f33e1b50a8f5eb73ac37d20e8487ce2`; hofmann-316l-2026 `d4bbc7a60b536118586f44b64beb0fa20f94133f6d1a8d0fdcf726003720c3d8`; ku-leuven-316l-2021 `e031aead71bf64c70a35ae05d64c0c576d33c2ae757a1e5bda68b5da532ac831`; ku-leuven-ti64-2021 `e031aead71bf64c70a35ae05d64c0c576d33c2ae757a1e5bda68b5da532ac831`; lane-in625-2020 `32fe10fb8606a49cdc59e1e3753b40e6be9ea9751dae9ec8ac95c217e6d16179`; totis-ti64-2021 `3b5794f3a25a5f67fa0d8d1ab006834205ef820b046c24deb15836025825d623`; trapp-316l-2017 `3a7bc34d75bb09bf41771331d116ce5d7e5ca0b7251aeb4d1e45c1e066a4ce7f`

## What this does not show

- It is a screening comparison on published single tracks, not validation. No evidence label is promoted.
- Totis width is reported only (the open text of Vaglio 2020 does not print the W definition); KU Leuven width is reported only.
- Inconel 718 and AlSi10Mg have no eligible held-out source; this evaluation says nothing about them.
- Default kernels only: interaction with the calibration layer is out of scope.
