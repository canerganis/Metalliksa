# PREDECLARED: Fabbro 2020 generalized piston model (GPM) as a research depth module

Written and committed before any evaluation run. Branch `research/depth`, module
`python/lpbf_depth_research/fabbro_piston.py` (analytic, single process, no frozen file touched). Results go to
`docs/research/RESULTS.md`, section "Fabbro piston energy balance". Candidate B of Astra's critique
(`codex-astra-depth.md` 2B).

## Model (Fabbro, Appl. Sci. 2020, 10, 1487, doi 10.3390/app10041487, Appendix A, Eqs. A1-A12 with Eqs. 8-9)

Half-cone keyhole front of depth e and spot diameter d, front inclination alpha, R = e/d = 1/tan(alpha) (Eq. 8),
stationary front Vd = Vw cos(alpha) (Eq. 9). Only the first impact of the vertical beam is counted (no reflected-beam
contribution), exactly as in the appendix.

* A1  melt film  delta0 = kappa_m Y(Ts) / Vd,  Y = ln(1 + rho_m Cp_m (Ts - Tm) / (rho_s Cp_s (Tm - T0) + rho_s Lm))
* A2  mass       0.5 rho_s Vw (d + 2 delta0) e = rho_m Vm delta0 e + rho_m Vv Sv,  Sv = (1.5 pi / 4) d^2 / sin(alpha)
* A3  energy     A_F(alpha) P = Pm + Pvap + Pcond + Pkin
* A4  Fresnel    unpolarised A_F at incidence pi/2 - alpha, n = 3.6, k = 5.0 (steel at 1.06 um, Dausinger & Shen 1993,
      as Fabbro)
* A5  Pm   = rho_m Vm delta0 e [Cp_s (Tm - T0) + Lm + Cp_m (Ts - T*)],  T* = 0.5 (Tm + Ts)
* A6  Pvap = rho_m Vv Sv [Cp_s (Tm - T0) + Lm + Cp_m (Ts - Tm) + Lv]
* A8  Pcond = K_s (Tm - T0) [0.5 m0 (Vw d / 2 kappa_s)(1 + 2 delta0 / d) + n0] e,  m0 = n0 = 2.3
* A9  Pkin = rho_m Vm delta0 e Vm^2 / 2
* A10 Vm = sqrt(2 (Pr - Pamb) / rho_m),  Pr = 0.5 (1 + beta) Pcc,  beta = 0.2,  Pamb = P0 = 1e5 Pa
* A11 Pcc = P0 exp(c (1 - Tv0 / Ts)),  c = Lv Mw / (R Tv0)  (the printed "exp -c(1 - Tv0/Ts)" is read as the
      Clausius-Clapeyron form that gives Pcc > P0 for Ts > Tv0; otherwise no recoil above Tv0 is possible)
* A12 rho_m Vv = (1 - beta) sqrt(Mw / (2 pi R Ts)) Pcc

Solution: for a given surface temperature Ts > Tth (Pr(Tth) = Pamb), A2 with A1 and Eq. 9 gives cos(alpha) in closed
form; then delta0, R, e, A_F, the four power terms and P = Pabs / A_F. The incident power for a requested R, or the R
for a given P, is found by bisection on Ts (P(Ts) is checked to be monotonic on the solved interval). Mass and energy
residuals are recomputed independently of the solve and reported for every row.

## Step 1: reproduction of Fabbro's own published results (must pass before any dataset is touched)

Fabbro's Ti-6Al-4V set (Appendix A, last paragraph): rho_s = rho_m = 4200 kg/m3, Tm = 1950 K, Tv0 = 3500 K,
Lm = 2.85e5 J/kg, Lv = 9.8e6 J/kg, kappa_s = kappa_m = 8.5e-6 m2/s, c = 15.8. Cp is NOT printed; it is inferred from
his own fitted constants a1 = n1 K (Tv - T0) and b1 = m1 K (Tv - T0) / (2 kappa) with (m1, n1) = (2.1, 2.2) and
T0 = 300 K, which both give K = 30 W/mK, i.e. Cp = K / (rho kappa) = 840 J/kgK (Cp_s = Cp_m). Mw = c R Tv0 / Lv =
0.047 kg/mol. Sensitivity to Cp in 700-1000 J/kgK is reported.

Targets and tolerances (declared now):

| id | published value (locator) | tolerance | required |
|---|---|---|---|
| R1 | A_F(alpha = pi/4) = 0.32 (Sec. 3.3) | +-0.01 | yes |
| R2 | Tth = 1.041 Tv0 (Appendix A remark) | +-1 % | report |
| R3 | 9-point threshold grid d = 60/120/180 um, Vw = 0.25/0.5/1 m/s: A_F(1) Pt / d = a1 + b1 Vw d with a1 = 2.1e5 W/m, b1 = 1.2e10 J/m3 (Eq. 11, Fig. 5) | b1 +-20 %, a1 +-40 % | yes |
| R4 | Fig. 4 (d = 120 um): Pt(R = 1) read as 240 / 340 / 600 W at 0.25 / 0.5 / 1 m/s; R(P) linear (Eq. 10) | Pt +-15 %, r^2 > 0.98 | yes |
| R5 | power shares (Sec. 3.3): Pcond 30-45 %, Pvap 20-35 %, Pfus 30-40 %, Pkin < 0.1 % over the grid, R 0.5-2.5 | ranges widened by 10 points; Pkin < 0.5 % | yes |
| R6 | 0.31 < A_F(R) < 0.36 over the grid (Sec. 3.3) | 0.30-0.37 | report |
| R7 | Appendix remark: d = 300 um, Vw = 0.05 m/s, R = 2.5 at P = 1200 W (1 bar) and 571 W (0.01 bar, Tv0 = 2780 K); Vw = 0.5 m/s: 3700 W at both pressures; Ts = 3600 K, recoil = 2 bar, Vm = 6 m/s at the 0.5 m/s case | P +-20 %, Ts +-5 %, recoil and Vm +-30 % | yes (P), report (rest) |
| R8 | Fig. 7 Delta Vm / Vw read at R = 0.5 and 2.5: Vw 0.25 m/s: 1.4-2.3 (60 um), 2.1-3.2 (120), 2.6-4.5 (180); 0.5 m/s: 2.0-3.3, 3.2-5.8, 4.5-7.4; 1 m/s: 3.3-5.7, 5.8-9.4, 7.4-12.7 | +-25 % | report |

If any required target fails, stop: report the mismatch and do not run the dataset evaluation.

## Step 2: evaluation (frozen before the run)

**Beam diameter convention.** Fabbro's GPM uses a uniform spot; Sec. 3.4 states that for a Gaussian beam the
diameter "defined at about half maximum intensity" must be used (56 um for Cunningham's 95 um 1/e2 spot). Primary:
d_eff = sqrt(ln 2 / 2) d_1/e2 = 0.5887 d_1/e2 (NIST D4sigma = 1/e2 for a Gaussian). The depth is e = R d_eff.
Secondary (reported only): d_eff = d_1/e2.

**Applicability scope.** Fabbro: half-cone front, R from 0.5 to 3 (Secs. 3.1, 3.3; Appendix A: 2D conduction valid for
R > ~0.5). In scope: 0.5 <= e_meas / d_eff <= 3 for sets with a measured vapour depth; 0.5 <= R_pred <= 3 for melt-depth
sets (no measured vapour depth). Out-of-scope rows are listed and never counted as success. Rows below the model's
depression threshold (P < P*) predict e = 0 and are reported as such.

**Properties (per alloy, from the app's material authority `four_alloy_materials.py`, `screening_props` lookup).**
Solid: density_kg_m3, thermal_conductivity_W_mK, specific_heat_J_kgK; liquid: density_liquid_kg_m3,
thermal_conductivity_liquid_W_mK, specific_heat_liquid_J_kgK; Tm = liquidus_C; Tv0 = boiling_C; Lm, Lv, Mw as stored.
The vapour constants (boiling_C, latent_heat_vap_J_kg, M_molar_kg_mol) carry no per-property provenance entry in
PROPERTY_PROVENANCE; they are used as the app's authority values and flagged as such. Optical constants: steel
n = 3.6, k = 5.0 for every alloy, as Fabbro did (no alloy-specific 1.06 um constants with a Crossref-verified DOI are
in the repo; none is invented). A sensitivity sweep n in {2.5, 3.6, 5.0}, k in {3, 5, 7} is reported.
Variants: P-EFF (primary) solid conduction values replaced by the app's effective screening convention
k_s' = (k_s + k_l)/2, Cp_s' = (Cp_s + Cp_l)/2 (the C0 kernel convention, closest to Fabbro's "mean thermophysical
properties"); P-SL (secondary) solid room-temperature values as stored; P-FAB (Ti-6Al-4V only) Fabbro's own set.
T0 = row preheat.

**Sets.**
* Cunningham 2019, 95 um (46 rows) and 140 um (23 rows): vapour-depression depth (`load_cunningham_depths`).
* Gan 2021 Supplementary Data 1 Ti-6Al-4V (71 rows): the same experiments; reported, never counted.
* Zhao 2020 boundary, bare (8 rows with depth) and powder (11 rows): keyhole depth (`load_zhao_boundary`). Powder
  rows are outside the bare-plate model and reported separately.
* NIST AMB2022-03 IN718 (7 rows, `table4-aggregate-v2.json`): bound e_pred <= measured melt depth.
* Hofmann 2026 316L bare plate (layer 0), keyhole band dH/hs >= 20 and balling = 0: bound e_pred <= melt depth;
  30 / 60 um layers reported with the datum shift 0.6 t subtracted from e_pred (secondary).
* KU Leuven 2021 316L rows with publishedRegime = keyhole (37): bound; Ti-6Al-4V keyhole rows (4) reported only.

**Metrics.** Per set: n, n in scope, MAPE and median pred/meas ratio on in-scope rows, bias; bound violations
(e_pred > measured melt depth) counted on all rows and on in-scope rows. Energy residual |A_F P - sum P_i| / (A_F P) and
mass residual |LHS - RHS| / LHS of A2 recomputed for every solved row.

**Baselines in the same script, same rows.** App Fabbro (`fabbro_keyhole.fabbro_keyhole_depth_m`, d = 1/e2, app
room-temperature props, flat absorptivity_IR, dH/hs ramp 15->30) and its FWHM variant (d = 0.5887 d_1/e2), identical
to K0 and K1-r30 of the D-3a report.

**Gate (Astra 2B).** Every solved row: energy and mass residuals < 1 %. In-scope vapour-depth MAPE <= 35 % and median
ratio 0.80-1.25 per independent vapour set (Cunningham 95, Cunningham 140, Zhao bare). NIST: 0/7 bound violations.
Melt-depth MAPE <= 20 % applies only if the module is proposed as the Ni/Fe melt-depth operator; it is not proposed
here, so that item is N/A and only the bound is gated. Out of scope is not success. Pass/fail is reported per set.
