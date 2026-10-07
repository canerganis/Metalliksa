# Evidence note: the app's keyhole thresholds vs published Ti-6Al-4V x-ray data (2026-10-07)

**Proposal for a planned physics bump. Nothing was changed.** The thresholds live in frozen files
(`python/lpbf_thermal_solver.py`, `python/fabbro_keyhole.py`, both in `lpbf_simulation.IMPLEMENTATION_SOURCE_FILES`)
and are mirrored in `python/lpbf_public_datasets.py` (process-map label) and in UI text
(`src/components/3d-distortion-lab/IndustrialLPBFDecisionLab.tsx` `normalizedEnthalpy < 30`,
`MeltPool3DCrossSectionLab.tsx` "15 / 30" copy). A change needs a fingerprint bump, golden review and maintainer
sign-off.

Numbers below come from `docs/LPBF_KEYHOLE_BENCHMARK_2026-10-07.json` (tool `python/tools/lpbf_keyhole_benchmark.py`,
data `python/lpbf_keyhole_literature.py`). The measured values are DIGITIZED from published figures (read
uncertainty about 4 W / 4 um per point); the app index uses the app's estimated Ti-6Al-4V properties and flat
absorptivity 0.35, 20 C preheat, spot = 1/e^2 diameter (assumed). This is a comparison, not validation.

## What the app does today

- Index: dH/hs = A P / (rho cp (T_liq - T0) sqrt(pi alpha v r^3)), r = 1/e^2 radius, flat absorptivity.
- Regime: < 15 conduction, 15-30 transition, >= 30 keyhole (process map and solver).
- keyholePorosityRisk: the same bands (Negligible / Low-Moderate / High).
- Keyhole depth: Fabbro 2020 eq. 2 with the flat absorptivity, scaled by a 15 -> 30 ramp (0 below 15).
- The 15/30 values are King et al. 2014 (316L) numbers, applied to a different convention: King's sigma is the Gaussian
  standard deviation (I ~ exp(-r^2/2 sigma^2), i.e. sigma = r/2) and hs = rho c Tm. Correction (keyhole-regime bump
  spec): the sigma term alone is 2^1.5 = 2.8x, but the property terms cancel about half of it; for 316L with the app
  properties the full ratio is H_King / H_app = **1.351** (A 0.4 vs 0.42, hs_K = 1.2e6 J/kg vs rho cp (T_liq - T0),
  D_K = 5.38e-6 m2/s vs the app's solid alpha), so King's 30 +/- 4 is **22.2 (19.3-25.2)** in the app convention, conditional on the app absorptivity, 20 C preheat and the app property set. (The
  code comment in `lpbf_thermal_solver.py` said the thresholds were "applied to this convention as a screening proxy";
  that was true before the bump.)

## Finding 1: the keyhole threshold 30 is too high for Ti-6Al-4V (95 um spot)

Cunningham et al. 2019, Fig. 3A (red line: above it is the keyhole domain; blue line: below it is the conduction
domain), digitized as straight lines and evaluated with the app index at 400-1200 mm/s:

| line | app dH/hs along the line (min / median / max) | app threshold |
|---|---|---|
| blue (conduction limit) | 12.96 / 13.92 / 16.93 | 15 (agrees within about +/-15%) |
| red (keyhole domain) | 17.29 / 17.66 / 20.01 | 30 |

At fixed speed the app needs 1.50x (400 mm/s) to 1.74x (1200 mm/s) the power of the published keyhole line before it
says "keyhole". On the 46 Fig. 3B cases (labels from the lines) the app's 15/30 rule gets 30/46 (0.65); 15 of the 41
reported-keyhole cases are called "transition" (26/41 keyhole recall). Excluding the 2 cases within the read
uncertainty of a line changes nothing material (30/44). The 0.5 D/W King indicator on the Rosenthal melt pool does
better on the same cases (43/46), which shows the regime information is in the kernels but not in the index cut.

Not a fit: one alloy, one beam size, one group, labels from lines drawn by the authors from a stationary-beam
experiment. The red line is a melt-pool transition (aspect ratio ~0.5, text p. 1), the same physical criterion King
used for 316L, so the comparison is like-for-like in meaning. The KU Leuven 316L/Ti64 regime labels already in the repo
were not used here and should be part of the bump check.

## Finding 2: no single threshold on this index describes the keyhole-porosity boundary

Zhao et al. 2020, Fig. 1A (Ti-6Al-4V, ~100 um, bare plate and powder bed):

- The app index ON the published porosity boundary runs from 15.0 (222 mm/s, 82 W) to 62.4 (600 mm/s, 561 W),
  a factor of 4; median 24.9. 9 of 20 boundary points are already >= 30, i.e. the app says "High" on the boundary
  itself, and therefore also on the stable side just beyond it at high power-velocity.
- Of 35 P-V conditions where pores were observed, the app calls 19 "High" and 16 "Low-Moderate" (index 15-30); none
  "Negligible". The 16 not flagged are all the pore conditions at <= 202 W (155-445 mm/s, index 16.2-27.6), the
  low power-velocity range where Zhao reports the boundary becomes sensitive to speed.
- The published single-number alternatives, evaluated with app properties, do not collapse the boundary either:
  Gan Ke 14-70 along the boundary; Huang's dH/hm*Lth* (beta = Ye 2019 Am 0.26, hm = 6.26 J/mm3) 3.0-8.8 versus
  Huang's own Ti-6Al-4V threshold 8 +/- 3. Zhao's own scaling (d_c ~ V^6, d_c ~ P, an energy-density threshold
  ~3.7 MJ/m2 at low PV) says the boundary is a curve in P-V, not an iso-enthalpy line.

## Finding 3: the keyhole depth is under-predicted

Against the measured vapor-depression depth:

- Fabbro depth (`keyholeModel.fabbroDepth_um`), 95 um: 46/46 under, median ratio 0.62, MAPE 44.8%;
  140 um: 23/23 under, median ratio 0.12 (most cases are below index 15, where the ramp sets the depth to 0, while
  Cunningham shows a vapor depression under essentially all conditions); Zhao bare-plate boundary: 8/8 under,
  median ratio 0.35.
- The Eagar-Tsai melt-pool depth is shallower than the measured vapor depression in 44/46 Cunningham 95 um cases,
  which cannot be physical (the melt pool contains the depression). Rosenthal is about equal to the vapor depth
  (median ratio 1.04), so it is also too shallow as a melt-pool depth in keyhole mode.

## Proposed planned bump (not implemented)

1. Keyhole-mode threshold: replace the 316L King value 30 by a value derived in the app's own convention from
   regime-labelled data; Ti-6Al-4V here gives about 18 (17.3-20.0). Do not carry it to other alloys without data
   (use the KU Leuven 316L/Ti64 regime labels and NIST/Ghosh IN625 tracks). Alternatively switch the index to King's
   sigma convention and keep King's numbers for 316L only. Keep 15 as the conduction limit (supported here).
2. keyholePorosityRisk: decouple it from the regime index. Options: a P-V boundary fitted per alloy (Zhao-type), or
   "unresolved" outside alloys with porosity-labelled data. A single index cut misclassifies in both directions.
3. Keyhole depth: the flat-absorptivity Fabbro depth and the 0-below-15 ramp under-predict the depression. Options:
   keyhole absorptivity A(R) (Fabbro's own form), or drop the ramp and report the depression depth with its error
   band from this benchmark.
4. Bump procedure: fingerprint bump of the frozen files, golden re-pin with intent, process-map and dataset-comparison
   regeneration, UI copy (`< 30`, "15 / 30"), and this benchmark re-run as the acceptance check (target: the app index
   at the Cunningham red line within the chosen threshold +/- read uncertainty; Zhao pore cases reported, not tuned).

## Resolution (keyhole-regime bump, 2026-10-07)

Implemented as the planned physics bump `keyhole-regime` (bump record under `docs/LPBF_IMPLEMENTATION_BUMP_2026-10-07_keyhole-regime.*`): the
regime keyhole-mode threshold moved 30 -> 20 in the app convention as a **provisional screening choice, not a derived exact threshold** (inside the overlap of King 316L 19.3-25.2 and the Cunningham red-line values along speed 17.3-20.0, a range, not a confidence interval; Cunningham and Gan data are the derivation inputs, not independent validation; the held-out Hofmann/Totis checks and the benchmark v2 record are in
`LPBF_KEYHOLE_BENCHMARK_2026-10-07_keyhole-regime.*`); `keyholePorosityRisk` is decoupled from the regime index (same
numeric gate, labels Negligible / Possible / High, 15-30 advisory in the build job); the Fabbro depth formula is
unchanged (no tested variant passes the cross-material bounds, text only; the cause of the Fabbro under-prediction is not resolved, candidate mechanisms are listed in `FABBRO_BASIS`: beam-diameter convention into Fabbro's uniform model, model validity range / deep cylindrical keyhole, flat keyhole absorptivity, no vaporisation sink); calibration v2 keeps 15/30 (preregistered).
Labels are unchanged: `experimentalValidation=false`, `validationStatus=unvalidated`, `productionReady=false`.

## Open points that limit the evidence (settled by the keyhole-regime bump, with sources)

| question | answer | source |
|---|---|---|
| Cunningham spot convention | 1/e^2 diameter. SM p. 2: single-mode fibre laser "providing Gaussian beam profiles", focal spot ~56 um (1/e^2), larger spots by defocusing; Eq. S1 uses the 1/e^2 diameter. | `aav4687_cunningham_sm.pdf` pp. 2-3 |
| Same, independent | Gan 2021 Supplementary Data 1 lists the Cunningham Ti-6Al-4V cases with d = 95 um, r0 = 48 um and d = 140 um, r0 = 70 um; SI Eqs. 23/37 define r0 by exp(-2 r^2/r0^2), so r0 = d/2 (the app's r). Data 2 lists r0 = 75 um for 140 um: Gan-internal inconsistency, recorded. | `gan2021_data1/2.xlsx`, `gan2021_SI.pdf` |
| Benchmark spot assumption right? | Yes; no benchmark row is re-derived for the spot. The "assumption" wording stays only for Zhao (SI unavailable). | |
| Fig. 3A red line meaning | SM Figs. S2/S3: blue = vapor-depression transition, red = melt-pool transition "around d/w = 0.5" (stationary beam). Same criterion as King 2014 (depth > half-width). | SM pp. 3-4 |
| Digitization quality | Gan Data 1 Ti-6Al-4V depths vs our digitized Fig. 3B/3C: 69/69 rows matched, digitized minus Gan median +0.8 um, mean abs 2.5 um, max 20.4 um. | benchmark v2 `ganData1Check` |
| Gan Ke offset (needed factor 0.26-0.45) | Property set, not r0: with Gan Supplementary Table 1 properties and per-case eta, Gan Eq. 2 reproduces Cunningham depths in-sample (95 um: median ratio 0.95; 140 um: 0.96); held-out Zhao bare boundary 0.71, powder 1.45. | designer check |
| King Table 3 | A = 0.4, rho = 7.98 printed with the unit kg/m3 (rendered page image of the accepted manuscript, verified) = physically 7.98 g/cm3, so **7980 kg/m3 is a unit correction, not as printed**; hs = 1.2e6 J/kg (Rai 2007), D = 5.38e-6 m2/s, sigma from I = I0 exp(-r^2/2 sigma^2) (D4sigma = 4 sigma); threshold 30 +/- 4 (transition ~26-34). | King 2014 accepted MS Table 3, Section 3.2.1 fn. 3-4, Section 5 |

Still open: Zhao's SI (E definition, beam profile) and Huang Supplementary Table 3 were not available.

Original open points (before the SM and Gan Data read):

- Supplementary materials (beam definition, plate thickness, Zhao's E definition, Gan Supplementary Data 1 and
  property set, Huang Supplementary Table 3) were not available. Spot = 1/e^2 diameter was an assumption (now
  confirmed for Cunningham, see above); if the
  published spot were D4sigma of a non-Gaussian profile, the index shifts by (d_true/d)^-1.5.
- Gan's Eq. 2 with app properties over-predicts the depths by 2.4-4.9x; the Ke factor that would fit is 0.26-0.45
  (property set and/or r0 convention). Gan's relations are therefore not usable quantitatively until the SI is read.
- Hann 2011's printed depth relation does not reproduce Hann's own Table 3/4 pairs (3 of 14 within the claimed 10%),
  so Hann is used only for its vaporization-enthalpy transition (Ti-6Al-4V Hv/hs = 12.34), which on the Cunningham
  cases calls almost everything keyhole (not-keyhole recall 1/5).
