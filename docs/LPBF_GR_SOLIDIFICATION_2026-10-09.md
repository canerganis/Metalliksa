# LPBF melt-pool G/R coupled to solidification (screening)

Date: 2026-10-09. Status: screening only. `evidence: {kind: "screening-only", experimentalValidation: false}` on every output. Nothing here is a validated result, a measurement or a grain-structure prediction.

Files: `python/lpbf_gr_solidification.py` (coupling, point and map entry points), `python/lpbf_cet_screening.py` (CET equation and constants registry), `src/components/GrSolidificationMapCard.tsx` (UI card in the Solidification atlas), route `POST /api/python/lpbf-gr-solidification`.

## 1. What is coupled and where each number comes from

| Quantity | Source |
|---|---|
| G, R, G*R along the rear liquidus arc (bottom, median, tail) | Copied from the frozen Rosenthal screening solver (`calculate_meltpool_physics` -> `solidification_front`), through `project_build_job_microstructure`. No second estimate. |
| Hunt G/R band | `solidification_front.hunt_morphology(max(1, G / max(1e-6, R)))`, the same guard as the frozen code. Thresholds 1e10, 5e8, 1e7 K s/m^2 are uncalibrated. |
| Rosenthal trailing-centreline reference | Computed in the new module from copied inputs (E2). |
| CET band | E3, constants unavailable for IN718 and IN625 (section 3). |
| Trapping-adjusted Laves bound | E4, reusing `aziz_partition_coefficient` and `scheil_eutectic_fraction` from `lpbf_solidification_segregation`. |

Equations:

* E1, front G and R (copied). G = |grad T| at liquidus samples, R = v n_x cos(theta) for n_x > 0, Tdot = G R. Hunt 1984, DOI 10.1016/0025-5416(84)90201-5. `median.coolingRate_K_s` is the solver's median of the per-sample G*R, not G_median * R_median (`coolingBasis` says so).
* E2, Rosenthal 1946 point source on the trailing surface axis (x < 0, y = z = 0), where r + x = 0 so the exponential factor is 1: T - T0 = P / (2 pi k |x|). Hence x_tail = P / (2 pi k dT) with dT = T_liq - T0, and G = P / (2 pi k x_tail^2) = 2 pi k dT^2 / P. G does not depend on alpha or v. n_x = 1, so R = v cos(theta), and Tdot = G R. Inputs: P = `fieldPower_W`, k = `effectiveConductivity_W_mK`, T_liq from the alloy table, T0 = preheat, theta = 0. It is a pure point-source surface-centreline reference, a different location from the solver's tail sample (which sits at depth on the rear arc), and it is not regularised.
* E3, CET criterion, Gäumann form of Hunt 1984 with nucleation undercooling neglected: G^n / V = a [ (1/(n+1)) (-4 pi N0 / (3 ln(1 - phi)))^(1/3) ]^n, so G_crit(V, phi) = (a V)^(1/n) / (n + 1) (-4 pi N0 / (3 ln(1 - phi)))^(1/3). phi_columnar = 0.0066 and phi_equiaxed = 0.49 (Hunt). G >= G_crit(V, 0.0066) is columnar, G <= G_crit(V, 0.49) is equiaxed, between is mixed. V is the local R. Source: M. Gäumann, C. Bezençon, P. Canalis, W. Kurz, Acta Mater. 49 (2001) 1051-1062, DOI 10.1016/S1359-6454(00)00367-0.
* E4, Aziz trapping k(V) = (k_e + V/V_D) / (1 + V/V_D) (Ghosh et al. 2017 Eq. 12) and binary Scheil f_e = (C_e / C_0)^(1/(k-1)) (Dupont 1996 Eq. 5, Dupont 1998). Binary C = 0 constants: IN718 k 0.45, C_e 23.1 wt%, nominal Nb 5.125 wt%; IN625 k 0.51, C_e 18.9 wt%, nominal Nb 3.65 wt%. V_D is 0.23 and 0.31 m/s.

## 2. Two pinned worked cases

Hand case, `rosenthal_centerline_tail(200 W, 20 W/mK, 1250 C, 0 C, 1.0 m/s)`:

| Quantity | Value |
|---|---|
| x_tail | 1273.2395 um (= 200 / (2 pi 20 1250) m) |
| G | 981747.7042 K/m (= 2 pi 20 1250^2 / 200) |
| R, G/R, G*R | 1.0 m/s, 981747.7042, 981747.7042 |

The test cross-checks this against the frozen `rosenthal_temperature_C` (T = 1250 C at x_tail for alpha 5e-6 and 1e-5, central-difference gradient equal to G within relative 1e-6).

IN718, 285 W, 960 mm/s, beam 80 um, layer 40 um, hatch 110 um, preheat 80 C (keyhole regime in this model, status `available`):

| Point | G (K/m) | R (m/s) | G/R (K s/m^2) | G*R (K/s) | Hunt band |
|---|---|---|---|---|---|
| bottom | 23048024 | 0.014 | 1.6462874e9 | 322672.3 | Cellular |
| median | 12135115 | 0.0684 | 1.774140e8 | 830457 (solver median) | Columnar dendritic |
| tail | 3939882 | 0.2318 | 1.6996903e7 | 913264.6 | Columnar dendritic |
| Rosenthal centreline (P 210.05 W, k 20.2, dT 1256) | 953208.3 | 0.96 | 992925.3 | 915080.0 | not banded |

Laves (fraction of the liquid): equilibrium-k bound 0.0647. Sampled-arc upper bound 0.0572 at the bottom point (R 0.014, V_D 0.31). At the tail 0.0041 to 0.0084; at the median 0.0287 to 0.0354 (matches `docs/LPBF_SCHEIL_LAVES_2026-10-07.md`).

These pins move only with a frozen-solver bump.

## 3. CET status

The equation form comes from Gäumann 2001. The DOI was confirmed against a Crossref-cited record; the paper was not read for this design. `EQUATION_VERIFIED` is `False` and `EQUATION_LOCATOR` is `None` until the maintainer reads the PDF and fills in the equation number.

No CET constants (a, n, N0) are shipped for IN718 or IN625. Their registry status is `unavailable`, with a reason: Gäumann 2001 gives constants for CMSX-4 only, and no published constants are known for IN625. Every cell therefore reports `cet.status == "unavailable"`, and the morphology basis stays `hunt-g-over-r-screening`. The functions `critical_gradient_K_m`, `cet_band` and `cet_block(constants_override=...)` are tested with SYNTHETIC constants only; they are test values, not alloy data.

Candidate IN718 sources for the maintainer, both electron-beam melting and neither read yet. Their N0 is process-specific.

* M. Haines, A. Plotkowski, C.L. Frederick, E.J. Schwalbach, S.S. Babu, Comput. Mater. Sci. (2018), CET sensitivity analysis for Ni superalloys in EBM. OSTI 1474534.
* N. Raghavan et al., Acta Mater. (2016), IN718 EBM grain morphology. OSTI 1252143.

## 4. Limits

* The conduction field has no Marangoni flow.
* Keyhole cells are outside the regime; the default IN718 window is mostly keyhole in this model. The map hatches them and the engine sets `regimeNote`.
* Only three rear-arc points (bottom, median, tail) are reported; the sampler skips the ends of the arc.
* R tends to 0 at the pool bottom, so the trapping bound holds only for the sampled arc. Over the whole boundary the bound is the equilibrium-k value.
* Values are copied after the solver's rounding.
* The Rosenthal reference sits at a different location from the solver's tail sample.
* Remelting by later tracks and layers and epitaxial columnar growth are not modelled; in LPBF they usually dominate over CET.
* Nucleation undercooling is neglected in the Gäumann form; N0 depends on the process.
* IN625 thermal properties are a legacy estimate (`legacy-estimated-secondary`, unvalidated). The Laves versus NbC identity is not established (C88, D96).
* The Laves numbers extrapolate weld-calibrated formulas.
* No experimental comparison.

## 5. Frozen files untouched

No file in `lpbf_simulation.IMPLEMENTATION_SOURCE_FILES`, `python/lpbf_implementation_fingerprint.expected` or `python/golden/lpbf_parity/` was changed, and the new modules are not in that list. `BUILD_JOB_SOLVER_REVISION` is unchanged and no build-job output changes. The only edit to an existing physics-adjacent module is `binary_laves_inputs`, appended at the end of `lpbf_solidification_segregation.py` without touching existing lines. The fingerprint tests and the segregation pin tests are green (see the commit message for the exact run).
