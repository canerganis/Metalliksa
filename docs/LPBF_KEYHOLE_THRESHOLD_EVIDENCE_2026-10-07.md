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
  standard deviation (I ~ exp(-r^2/2 sigma^2), i.e. sigma = r/2) and hs = rho c Tm, so for the same case King's index
  is about 2^1.5 = 2.8x the app's (the code comment in `lpbf_thermal_solver.py` already says the thresholds are
  "applied to this convention as a screening proxy").

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

## Open points that limit the evidence

- Supplementary materials (beam definition, plate thickness, Zhao's E definition, Gan Supplementary Data 1 and
  property set, Huang Supplementary Table 3) were not available. Spot = 1/e^2 diameter is an assumption; if the
  published spot were D4sigma of a non-Gaussian profile, the index shifts by (d_true/d)^-1.5.
- Gan's Eq. 2 with app properties over-predicts the depths by 2.4-4.9x; the Ke factor that would fit is 0.26-0.45
  (property set and/or r0 convention). Gan's relations are therefore not usable quantitatively until the SI is read.
- Hann 2011's printed depth relation does not reproduce Hann's own Table 3/4 pairs (3 of 14 within the claimed 10%),
  so Hann is used only for its vaporization-enthalpy transition (Ti-6Al-4V Hv/hs = 12.34), which on the Cunningham
  cases calls almost everything keyhole (not-keyhole recall 1/5).
