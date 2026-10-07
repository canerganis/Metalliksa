# Depth research results (branch research/depth)

Each section records one pre-declared experiment, including failures. Nothing here is served by the app.

## Fabbro piston energy balance

Pre-declaration: `PREDECLARED_fabbro_piston.md` (commit 5fdbf431). Module: `python/lpbf_depth_research/fabbro_piston.py`,
tests `test_fabbro_piston.py` (13 tests, self-contained, 0.3 s). Run: `python python/lpbf_depth_research/fabbro_piston.py
--reproduce --evaluate` (7.6 s single process). Date 2026-10-07.

### Verdict in one paragraph

Fabbro's generalized piston model (Appendix A, Eqs. A1-A12) is reproduced from the paper's own constants: Eq. 11
constants a1 = 2.12e5 W/m (published 2.1e5), b1 = 1.196e10 J/m3 (1.2e10), m1 = 2.12 (2.1), n1 = 2.21 (2.2); Fig. 4
thresholds within 3 %; the 300 um appendix remark within 2 % (1 bar, 0.05 m/s) and 7 % (0.5 m/s). Energy and mass
residuals are at round-off (max 4e-11) on every evaluated row. Against the data the result depends on the solid
property set far more than on anything else in the model: with the app's material authority (pre-declared primary
P-EFF, FWHM convention) the in-scope vapour depth is over-predicted by +33 % on Cunningham 95 um (MAPE 38 %) and
+97 % on 140 um (MAPE 98 %), and the vapour depth exceeds the measured IN718 melt depth in 7/7 NIST rows: the gate
FAILS for the pre-declared primary on every gated set except Zhao bare (n = 4 in scope, ratio 1.01, MAPE 5 %). With
Fabbro's own Ti-6Al-4V set (P-FAB: K_s = 30 W/mK instead of the app's 14.8) the Cunningham 95 um set passes
(in-scope ratio 1.03, MAPE 12 %, n = 20; all 46 rows 0.95 / 17 %), 140 um still fails (1.56 / 57 %) and Zhao bare
fails on the ratio (0.72 / 31 %). So the model, as published, works for Ti-6Al-4V at Fabbro's own property values on
the one set Fabbro himself analysed, and nowhere else that was tested. It is not proposed as a Ni/Fe operator.

### Step 1: reproduction of Fabbro 2020 (Ti-6Al-4V set of Appendix A, Cp = 840 J/kgK inferred, T0 = 300 K)

| id | published | computed | tolerance | result |
|---|---|---|---|---|
| R1 A_F(pi/4), steel n 3.6 k 5.0 | 0.32 | 0.321 | +-0.01 | PASS |
| R2 Tth / Tv0 | 1.041 | 1.0334 | +-1 % | PASS (0.7 % low; exact closed form with c = 15.8, beta = 0.2) |
| R3 Eq. 11 fit on the 9-point grid: a1 / b1 | 2.1e5 W/m / 1.2e10 J/m3 | 2.123e5 / 1.196e10 (r2 0.990) | a1 +-40 %, b1 +-20 % | PASS |
| R3 m1 / n1 | 2.1 / 2.2 | 2.12 / 2.21 | derived | PASS |
| R4 Fig. 4, d = 120 um, Pt(R = 1) at 0.25 / 0.5 / 1 m/s | 240 / 340 / 600 W (read) | 234 / 334 / 590 W | +-15 % | PASS |
| R4 R(P) linearity (Eq. 10), r2 | linear | 0.998 / 0.998 / 0.997; P' = 76 / 88 / 106 W | > 0.98 | PASS |
| R5 shares over the grid, R 0.5-2.5: Pcond / Pvap / Pfus / Pkin | 30-45 / 20-35 / 30-40 / < 0.1 % | 31-52 / 13-40 / 26-43 / < 0.05 % | ranges +-10 pts, Pkin < 0.5 % | PASS (extremes 7 pts wider than the narrated ranges) |
| R6 A_F(R) over the grid | 0.31-0.36 | 0.313-0.368 | 0.30-0.37 | PASS |
| R7 d = 300 um, Vw = 0.05 m/s, R = 2.5, 1 bar | 1200 W | 1216 W | +-20 % | PASS |
| R7 same at 0.01 bar (Tv0 = 2780 K) | 571 W | 570 W (ambient 0.01 bar, vapour curve unchanged); 583 W (curve re-anchored at 2780 K) | +-20 % | PASS (both readings) |
| R7 Vw = 0.5 m/s, 1 bar / 0.01 bar | 3700 / 3700 W | 3950 / 3483 W | +-20 % | PASS (+7 % / -6 %) |
| R7 Ts / recoil / Vm at 0.5 m/s, 1 bar | 3600 K / 2 bar / 6 m/s | 3754 K / 1.75 bar / 5.97 m/s | 5 / 30 / 30 % | PASS |
| R8 Fig. 7 Delta Vm / Vw = Vm/Vw - 1 at R = 0.5 and 2.5, nine (Vw, d) | e.g. 1 m/s, 180 um: 7.4-12.7; 0.25 m/s, 60 um: 1.4-2.3 | 6.0-11.6; 0.4-1.1 | +-25 % | FAIL as labelled: every one of the 18 points sits 1.0 +- 0.3 below the reading (median offset 1.0). The figure evidently plots Vm/Vw, not Vm/Vw - 1 (Eq. 15 and the mass balance give Vm/Vw - 1 = 0.5 d/delta0, which is what the module returns). Pinned in the test so it is not silently "fixed". |

Cp sensitivity (not printed by Fabbro): Cp 700 / 840 / 1000 J/kgK gives a1 1.71 / 2.12 / 2.58e5 and b1 1.06 / 1.20 / 1.35e10:
only the inferred 840 J/kgK (K = 30 W/mK) reproduces both constants, which is the consistency argument used to
infer it. Required targets R1, R3, R4, R5, R7 all pass, so the evaluation was run.

### Properties and conventions used in the evaluation

| set | rho_s / rho_m kg/m3 | K_s W/mK (kappa_s m2/s) | kappa_m m2/s | Tm K | Tv0 K | Lm / Lv MJ/kg | Mw kg/mol | c |
|---|---|---|---|---|---|---|---|---|
| P-FAB Ti-6Al-4V (Fabbro App. A; Cp 840 inferred) | 4200 / 4200 | 30.0 (8.5e-6) | 8.5e-6 | 1950 | 3500 | 0.285 / 9.8 | 0.0469 (from c) | 15.8 |
| P-EFF Ti-6Al-4V (app authority, (k_s+k_l)/2, (Cp_s+Cp_l)/2) | 4430 / 3950 | 14.8 (4.9e-6) | 7.0e-6 | 1933 | 3560 | 0.29 / 8.9 | 0.0459 | 13.8 |
| P-SL Ti-6Al-4V (app authority, room-temperature solid) | 4430 / 3950 | 6.7 (2.9e-6) | 7.0e-6 | 1933 | 3560 | 0.29 / 8.9 | 0.0459 | 13.8 |
| P-EFF 316L | 7990 / 6980 | 23.6 (4.6e-6) | 5.7e-6 | 1673 | 3087 | 0.27 / 6.25 | 0.0554 | 13.5 |
| P-SL 316L | 7990 / 6980 | 16.3 (4.1e-6) | 5.7e-6 | 1673 | 3087 | 0.27 / 6.25 | 0.0554 | 13.5 |
| P-EFF IN718 | 8190 / 7450 | 20.2 (4.2e-6) | 5.3e-6 | 1609 | 3123 | 0.27 / 6.4 | 0.0587 | 14.5 |
| P-SL IN718 | 8190 / 7450 | 11.4 (3.2e-6) | 5.3e-6 | 1609 | 3123 | 0.27 / 6.4 | 0.0587 | 14.5 |

* Source of the app values: `four_alloy_materials.py` `_THERMAL` (the material authority) via `screening_props`. The
  vapour constants there (boiling_C, latent_heat_vap_J_kg, M_molar_kg_mol) have no entry in PROPERTY_PROVENANCE, so they
  are the app's authority values, not independently cited here. Cross-check against the sibling module
  `evap_properties.py` (Crossref-verified sources, same branch): Ti-6Al-4V Tv 3560 K / Lv 9.255e6 (Gan 2021 SI Table 1)
  vs app 3560 K / 8.9e6 (-4 % Lv); 316L Tv 3090 K (Kim 1975) or 3122 K (Gan) / Lv 6.336e6 vs app 3087 K / 6.25e6;
  IN718 Tv 3120 K (Knapp 2019) vs app 3123 K. Lv enters only Pvap (median share 10-20 % of Pabs) and c, so these
  differences move the depth by a few per cent, far below the property-set effect below.
* Optical constants: steel n = 3.6, k = 5.0 at 1.06 um for every alloy, exactly as Fabbro. No alloy-specific
  1.06 um (n, k) with a Crossref-verified DOI is in the repo and none was invented. Sensitivity (Fabbro Ti64 set,
  95 um 1/e2, 250 W, 0.8 m/s, FWHM): A_F(pi/4) spans 0.17 (n 2.5, k 7) to 0.48 (n 3.6, k 3) and the depth 64 to 199 um
  around the steel value 143 um, i.e. the unknown alloy optics alone is a factor ~2 on the depth. This is a declared
  gap, not a tuned input.
* Beam convention: primary d_eff = 0.5887 x d_1/e2 (Fabbro Sec. 3.4, "defined at about half maximum intensity";
  NIST D4sigma = 1/e2). Secondary d_eff = d_1/e2, reported only. e = R d_eff.
* Scope: 0.5 <= e_meas / d_eff <= 3 for vapour-depth sets; 0.5 <= R_pred <= 3 for melt-depth sets. T0 = row preheat.
* Baselines on the same rows: app Fabbro (`fabbro_keyhole_depth_m`, d = 1/e2, app room-temperature props, flat
  absorptivity_IR, ramp 15->30) and its FWHM variant. Whole-set values reproduce the D-3a report exactly (Cunningham
  95: 0.62 / 45 % and 1.00 / 26 %; 140: 0.12 / 79 % and 0.20 / 73 %; Zhao bare 0.35 / 64 % and 0.54 / 44 %).

### Step 3: evaluation, pre-declared primary (P-EFF, d_eff = FWHM)

Cells: n, median pred/meas, MAPE %, bias %. "In scope" per the scope rule above. Bound = e_pred > measured melt depth.
Max energy residual 3.4e-11, max mass residual 1.4e-11 (gate < 1 %: PASS).

| set | n | in scope | GPM in-scope | GPM all rows | app 1/e2 in-scope | app FWHM in-scope | R_meas med | R_pred med | Pvap share | bound viol. all / in-scope (app 1/e2 / app FWHM) | gate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Cunningham 95 um | 46 | 20 | n20 1.33 / 38 / +38 | n46 1.15 / 29 / +28 | 0.44 / 57 / -57 | 0.71 / 42 / -32 | 3.44 | 4.09 | 15 % | | FAIL (ratio > 1.25, MAPE > 35) |
| Cunningham 140 um | 23 | 14 | n14 1.97 / 98 / +98 | n23 2.16 / 141 / +141 | 0.30 / 66 / -66 | 0.49 / 56 / -46 | 0.64 | 1.56 | 20 % | | FAIL |
| Gan data1 95 (same experiments, not counted) | 48 | 20 | n20 1.32 / 46 / +46 | n48 1.15 / 40 / +39 | 0.38 / 62 | 0.60 / 44 | 3.09 | 3.90 | 15 % | | (not counted) |
| Gan data1 140 (same experiments, not counted) | 23 | 14 | n14 2.03 / 102 / +102 | n23 2.33 / 158 / +158 | 0.30 / 66 | 0.50 / 55 | 0.63 | 1.55 | 20 % | | (not counted) |
| Zhao bare | 8 | 4 | n4 1.01 / 5 / -3 | n8 1.01 / 4 / -2 | 0.12 / 88 / -88 | 0.19 / 82 / -82 | 2.85 | 2.91 | 16 % | | PASS (n = 4) |
| Zhao powder (powder bed, reported only) | 11 | 4 | n4 2.09 / 114 / +114 | n11 1.62 / 166 / +166 | 0.66 / 38 | 1.02 / 48 | 2.72 | 4.34 | 15 % | | (bare-plate model; reported) |
| NIST AMB2022-03 IN718 (melt bound) | 7 | 0 | - | n7 1.36 / 31 / +31 (vapour vs melt depth) | - | - | 3.54 | 4.82 | 11 % | 7/7 / 0/0 (0 / 7) | FAIL (7/7) and out of scope (R_pred 3.1-8.1) |
| Hofmann 316L bare, keyhole band (melt bound) | 71 | 10 | n10 1.90 / 109 / +109 | n71 1.74 / 85 / +85 | 0.65 / 33 | 1.02 / 19 | 2.51 | 4.98 | 10 % | 69/71 / 10/10 (32 / 65) | FAIL (bound) |
| Hofmann 30 um layer, keyhole band (datum -18 um) | 73 | 8 | n8 1.34 / 46 / +46 | n73 1.31 / 41 / +32 | 0.50 / 49 | 0.77 / 22 | 3.11 | 4.46 | 10 % | 54/73 / 8/8 (17 / 47) | secondary; FAIL |
| Hofmann 60 um layer, keyhole band (datum -36 um) | 105 | 3 | n3 1.28 / 33 / +33 | n105 1.21 / 36 / +29 | 0.60 / 40 | 0.94 / 16 | 3.36 | 4.94 | 11 % | 81/105 / 3/3 (37 / 83) | secondary; FAIL |
| KU Leuven 316L keyhole (melt bound) | 37 | 0 | - | n37 0.76 / 33 / -15 | - | - | 20.1 | 14.4 | 6 % | 9/37 / 0/0 (4 / 19) | out of scope (37.5 um spot, R_meas median 20) |
| KU Leuven Ti64 keyhole (reported only) | 4 | 0 | - | n4 1.23 / 21 / +21 | - | - | 8.1 | 9.9 | 8 % | 3/4 / 0/0 (0 / 4) | out of scope |

In-scope fraction of the primary run: Cunningham 95 um 20/46, 140 um 14/23, Zhao bare 4/8, NIST 0/7, Hofmann bare
10/71, KU 316L 0/37. With the FWHM convention most of Cunningham's 95 um rows have e_meas / d_eff > 3, i.e. the set
Fabbro himself analysed in Sec. 3.4 is mostly above the scope he states in Secs. 3.1-3.3; the model's error there is
nevertheless small (rows with R_meas > 3: ratio 1.05-1.08 under P-EFF, 0.88-0.90 under P-FAB), and the in-scope
over-prediction is concentrated at R_meas 1-3 (ratio 1.31-1.39 under P-EFF, 0.97-1.09 under P-FAB).

### Property-set and beam-convention variants (gated sets only)

| variant | Cunningham 95 in-scope (n) | Cunningham 140 in-scope (n) | Zhao bare in-scope (n) | NIST bound viol. / in scope | Hofmann bare bound viol. / in scope |
|---|---|---|---|---|---|
| P-EFF, FWHM (primary) | 1.33 / 38 (20) | 1.97 / 98 (14) | 1.01 / 5 (4) | 7/7 / 0 | 69/71 / 10 |
| P-SL, FWHM | 1.66 / 73 (20) | 2.46 / 147 (14) | 1.30 / 25 (4) | 7/7 / 0 | 71/71 / 3 |
| P-FAB, FWHM (Fabbro's Ti64 set) | 1.03 / 12 (20); all rows 0.95 / 17 (46) | 1.56 / 57 (14); all 1.86 / 93 | 0.72 / 31 (4); all 0.75 / 26 | n/a | n/a |
| P-EFF, 1/e2 | 0.60 / 38 (33) | 0.84 / 16 (9); all 1.06 / 25 | 0.51 / 51 (5) | 0/7 / 6 (ratio to melt depth 0.67 / 33) | 28/71 / 58 (0.97 / 23) |
| P-SL, 1/e2 | 0.73 / 25 (33) | 1.01 / 11 (9); all 1.26 / 40 | 0.63 / 39 (5) | 0/7 / 6 (0.83 / 17) | 55/71 / 52 |
| P-FAB, 1/e2 | 0.51 / 48 (33) | 0.70 / 29 (9) | 0.39 / 64 (5) | n/a | n/a |

Gate per set (pre-declared primary P-EFF / FWHM): residuals PASS; Cunningham 95 FAIL; Cunningham 140 FAIL; Zhao bare
PASS (n = 4); NIST 0/7 FAIL (7/7 and out of scope); melt-depth MAPE N/A (not proposed). Where it passes outside the
primary: Cunningham 95 under P-FAB / FWHM (1.03 / 12 %, n 20; all rows 0.95 / 17 %); Cunningham 140 under P-EFF /
1/e2 (0.84 / 16 %, n 9 of 23) and P-SL / 1/e2 (1.01 / 11 %, n 9) but those are the non-primary convention and only the
9 rows with 0.5 <= R <= 3 on the 1/e2 diameter; NIST 0/7 only with the 1/e2 convention (vapour depth 0.67-0.83 of the
melt depth), which Fabbro's own Sec. 3.4 argues against for a Gaussian beam.

### What the run says

1. The energy balance closes and the published case reproduces, so the implementation is not the problem. The
   spread between property variants (Cunningham 95 in-scope ratio 1.03 -> 1.33 -> 1.66 for K_s = 30 -> 14.8 -> 6.7
   W/mK) is the dominant term: Pcond carries 30-50 % of the absorbed power and scales with K_s (Tm - T0). Fabbro's
   "mean" Ti-6Al-4V conductivity is 2x the app's effective value and 4.5x its room-temperature value; the app has
   no sourced high-temperature conductivity for the keyhole wall, and none is asserted here.
2. Cunningham 140 um is the low-aspect regime (R_meas median 0.64 on the FWHM diameter) and fails under every
   variant (ratio 1.56-2.5 with FWHM): the model gives R_pred 0.7-1.3 where 0.3-0.6 is measured at 400-1000 mm/s.
   This is the regime Astra flagged as a scope error for the cylindrical model; the half-cone model does not fix it.
3. For Ni/Fe the FWHM convention puts the vapour depth above the measured melt depth in 7/7 NIST and 69/71 Hofmann
   bare keyhole-band rows (R_pred 3-8, outside scope); the 1/e2 convention gives physically ordered values
   (vapour 0.67 of melt depth on NIST, 0/7 violations) but is the convention Fabbro argues against, and it is not
   the pre-declared primary. No Ni/Fe claim is made.
4. Vapour share of the absorbed power is 10-20 % on every set (Fabbro's own grid: 13-40 %), so the "missing
   evaporation loss" needed for the NIST rows (Astra: ~28.5 % of effective power) is not what this model delivers
   either; the model's depth is set by the conduction term and the front angle, not by Pvap.
5. Fig. 7 of the paper is mislabelled by a constant 1.0 (it plots Vm/Vw). Recorded, not corrected.

Failures recorded: gate FAIL on the pre-declared primary for Cunningham 95, Cunningham 140, NIST and Hofmann bare;
pass only on Zhao bare (n = 4). Pass under Fabbro's own Ti-6Al-4V constants on Cunningham 95 only. Not proposed for
the served depth path in any alloy.

Commits: 5fdbf431 (pre-declaration), 572d2fc7 (module + tests), this file.
