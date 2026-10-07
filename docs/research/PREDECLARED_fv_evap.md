# Pre-declared evaluation: FV reference transient + surface evaporative cooling (research fork)

Written and committed BEFORE any case of this evaluation was run (2026-10-07, Fable, branch `research/depth`,
base main 5f7e6cdf). Code lives in `python/lpbf_depth_research/` (not part of the frozen closure
`lpbf_simulation.IMPLEMENTATION_SOURCE_FILES`; the frozen modules are imported read-only, never edited).
Only `evap_properties.py` was executed before this file (to derive the IN625/IN718 constants and run the
method checks quoted in §1); no thermal case was run.

## 0. Problem being tested

The frozen enthalpy-FV solver (`enthalpy-fv-6`) has no evaporation physics: the boiling enthalpy is a validity
stop, so in the earlier reference arm 14/32 Hofmann mesh-check runs ended in "boiling-stop", and the only arm
that completes ("cap") clips T at T_boil, keeps the excess enthalpy in the cell and multiplies the liquid
conductivity by an uncited 2.2. 20 µm is also not mesh-converged (W/D change up to one 20 µm cell at 10 µm).
Astra's critique (`codex-astra-depth.md`): the measurement operator (first most-liquid instant) is not an
etched section (ever-melted envelope), and the 40 µm volumetric source is not a surface Gaussian flux.

## 1. Physics added (sourced; nothing fitted)

Evaporative heat sink on the top active cell of every column (surface = z = 0 for bare rows, powder top for
powder rows), explicit in time, included in the row-sum stability bound:

- Mass flux (Hertz-Knudsen-Langmuir / Anisimov with recondensation):
  `m_dot = (1 - beta_R) sqrt(M / (2 pi R T)) P_sat(T)` — Gan 2021 SI Eq. 12 high-intensity branch
  (DOI 10.1038/s41467-021-22704-0); same form as Fabbro 2020 Eq. A12 (DOI 10.3390/app10041487), both citing
  Knight 1979 / Anisimov. `beta_R = 0.18` from Gan 2021 SI Supplementary Table 2 (i.e. net factor 0.82).
  The flux is applied at every surface temperature (no low-intensity polynomial bridge as in Gan Eq. 12;
  below T_b it is small and the choice is conservative towards more cooling).
- Saturation pressure (Clausius-Clapeyron): `P_sat = P_atm exp[M L_v / (R T_b) (1 - T_b/T)]`, Gan 2021 SI
  Eq. 13 = Fabbro 2020 Eq. A11, `P_atm = 1e5 Pa`, `R = 8.314 J/(mol K)`.
- Heat sink: `q = L_v m_dot` [W/m²], Gan 2021 SI Eq. 31. No vapour sensible heat, no surface recession,
  no recoil pressure, no keyhole cavity (recoil-driven flow is OUT OF SCOPE: stated).
- Above the boiling enthalpy the material enthalpy table is extended with the last tabulated (liquid) cp and
  k held constant up to 2 T_b (an extrapolation of the frozen straight-line law, stated); the only validity
  stop of the evaporation arms is T > 2 T_b or a non-finite enthalpy. No temperature cap, k multiplier 1.0.

Alloy constants (DOIs Crossref-verified 2026-10-07; details in `evap_properties.py`):

| alloy | T_b [K] | L_v [J/kg] | M [g/mol] | source |
|---|---|---|---|---|
| 316L | 3122 | 6.336e6 | 56 | Gan 2021 SI Table 1 (SS316). Alternative on record, not run: Kim 1975 ANL-75-55 (DOI 10.2172/4152287) 3090 K, 1770 cal/g = 7.41e6 J/kg |
| Ti-6Al-4V | 3560 | 9.255e6 | 48 | Gan 2021 SI Table 1 (Ti64) |
| IN718 | 3120 | 6.470e6 (derived) | 57.9 (derived) | T_b: Knapp 2019 Table 1 (DOI 10.1016/j.addma.2018.12.001); L_v, M: mass-weighted additivity over Knapp Table 3 (composition + elemental dH_vap), the Kim 1975 rule |
| IN625 | 3107 (derived) | 6.464e6 (derived) | 59.6 (derived) | composition Lass 2017 Table I (DOI 10.1007/s11661-017-4304-6); elemental data Knapp 2019 Table 3; T_b = Raoult-ideal mixture pressure reaching 1 atm |

Method check of the derivation (run before this declaration, `evap_properties.method_checks()`): the Raoult
boiling point of IN718 from the same elemental data is 3084 K vs Knapp's 3120 K (−1.2 %); of 316L (Kim's
composition) 3089 K vs Kim's 3090 K; the additivity L_v of 316L is 6.21e6 vs Gan's 6.34e6 and Kim's 7.41e6.
These are not fit parameters; they bound the derived IN625 numbers at roughly ±2 % (T_b) and ±20 % (L_v).

Heat source options (research fork of `lpbf_core_physics.integrated_source`): (a) `surface-flux`: the
absorbed Gaussian (1/e² radius, Eagar-Tsai 1983 Eqs. 6, 9-11 form) deposited in the top active cell of each
column only (cell-integrated in x, y; same two-point/adaptive Gauss time quadrature as the frozen source);
(b) `volumetric`: the frozen half-Gaussian depth profile (40 µm penetration on bare rows, layer depth on
powder rows) unchanged. Everything else (domain, cubic grid, explicit Euler, harmonic conduction,
isothermal bottom, convection + radiation top loss, powder slab with packing 0.55 and k-ratio 0.12, enthalpy
inversion, scan path, cooling 0.5 ms) is the frozen algorithm copied into `fv_evap.py`.

Measurement operators (all reported; the primary one is fixed here):
- PRIMARY `env-mid`: ever-melted envelope (time-union of T >= T_liquidus over accepted steps) on the YZ
  plane nearest the +X track midpoint; width = widest extent at any depth; depth = deepest cell below
  z = 0 (plate datum) + dx/2. Used for bare AND powder rows (powder rows: cells in the slab lie above z = 0,
  so the depth is already in the plate datum; width includes the slab).
- `env-full`: the same envelope over the whole domain (max extents anywhere along the track).
- `peak`: the frozen operator (first instant with the most liquid cells; depth from the model surface,
  converted to the plate datum by subtracting the layer thickness).
- `cavity-mid`: ever T >= T_b region on the mid plane (depth below z = 0): the vapour-cavity proxy of a
  conduction solver; compared to Cunningham's measured vapour depth and used for the NIST bound.

## 2. Arms, mesh, subset

Arms (20 µm requested mesh, track 600 µm, maxDt 1e-6 s, preheat per row, flat absorptivity of the frozen
registry 0.42 / 0.35 / 0.38 and Mills-route IN625 0.40 — unchanged, so property/absorptivity choices are
not re-opened here):
- `evap-sf`  : evaporation + surface flux, k multiplier 1, no cap, no boiling stop. THE candidate.
- `evap-v40` : evaporation + frozen volumetric source (isolates the source-geometry effect).
- `ref-sf`   : frozen physics (boiling validity stop) + surface flux.
- `ref-v40`  : frozen physics + frozen source, i.e. the reference arm of the earlier evaluation, re-run on
               the same rows in the fork so boiling-stop counts are like-for-like.

Mesh: all arms at 20 µm on the subset. `evap-sf` additionally at 10 µm on the convergence subset: the FIRST
row (by rowId) of these strata: Hofmann bare × 4 bands, Hofmann 30 µm cond<15 and >=30, Totis cond<15 and
>=30, Lane cond<15, NIST >=30, Trapp cond<15, KU 316L >=30 (13 runs). 5 µm: `evap-sf` on 3 shallow cases
(Hofmann bare cond<15 first, Totis cond<15 first, Trapp cond<15 first) with the track length reduced in
the sequence 600 → 400 → 300 → 200 µm until the cell count is ≤ 1.2e6 (the fork's memory bound; the frozen
600 000-cell guard is not applied in the fork — stated); the 20 and 10 µm runs of those 3 cases are REPEATED
at that same track length so the 20→10→5 comparison is like-for-like. Convergence call per case:
|Δ| of W and D between 10 and 5 µm ≤ 5 % (Astra's C gate). Runs that do not finish are "unfinished".

Subset (stratified, deterministic): non-balling rows of the pre-declared sets in
`depth_tdep_results.json` (863 rows; balling-flagged Hofmann rows excluded as before; KU rows at the 60 µm
layer as before). Strata = source × layer × ΔH/hs band (cond<15, 15-20, 20-30, >=30). Per stratum take 3 rows
= the first, middle and last by rowId (all rows when the stratum has ≤ 3). Sources: Hofmann bare/30/60 µm,
Totis 25 µm, KU 316L, KU Ti64, Lane IN625, Ghosh IN625, Trapp 316L (0.5 mm disc, semi-infinite domain:
declared), NIST AMB2022-03 IN718 — 84 rows. Cunningham 2019 vapour-depth rows (Ti64 bare, 95 and 140 µm
spots): first, middle, last of each set by rowId — 6 rows, `cavity-mid` vs measured vapour depth only.
Nothing is fitted on any row, so every row is held out.

Comparator ("best analytic kernel"): on the IDENTICAL rows each arm completed, the depth MAPE of
Eagar-Tsai C0, Goldak C0 and Rosenthal C0 (Fabbro F0 floor included, as served; from
`depth_tdep_results.json`), powder rows converted with the earlier reports' assumption D − 0.6·t; the best
kernel = lowest equal-source-weight depth MAPE. Equal-source weight = mean over sources of the per-source
MAPE (sources with ≥ 3 completed rows).

## 3. Gate (all must hold for `evap-sf`, operator `env-mid`)

1. equal-source-weight depth MAPE ≥ 5 points lower than the best analytic kernel on the identical rows;
2. no source's depth MAPE worse than that kernel's by > 5 points;
3. no source's width MAPE worse than that kernel's by > 2 points;
4. NIST vapour/melt bound: `cavity-mid` depth ≤ measured melt depth on every NIST row of the subset;
5. mesh: W and D change 10 → 5 µm ≤ 5 % on every 5 µm case that finished;
6. energy balance on every completed case: |absorbed − (conducted out at the bottom + stored + convection
   + radiation + evaporated)| / absorbed ≤ 1 %.

A completed-row fraction lower than the kernels' is reported; superiority is never claimed on the completed
rows alone when the completion fraction drops (Astra's condition).

## 4. Resources

At most 4 worker processes (the maintainer's `fv_depth_eval` run and other work share the machine), wall
time recorded per case, no case killed; target total runtime < 3 h. Results checkpointed to
`docs/research/fv_evap_results.json` every few cases.

## 5. Prediction before running

Evaporative cooling at T ≈ 1.1 T_b removes of order 1e9 W/m², a few per cent of the absorbed peak intensity
(1e10–3e10 W/m²) of the keyhole-band rows; the surface temperature of the evaporation arms will therefore
rise to 1.2–1.5 T_b in the ≥ 20 bands instead of stopping. Without a cavity the solver has no mechanism to
carry the absorbed energy to depth, so `evap-sf` will UNDER-predict depth in the 20-30 and ≥ 30 bands by more
than the kernels (which carry the Fabbro floor), and will be comparable to the kernels in cond<15 and
15-20 (cell-quantised at 20 µm). The surface flux makes pools shallower and hotter than the 40 µm source.
Expected gate verdict: FAIL on criterion 1 and 2 (KU 316L, Totis, NIST ≥ 30), with energy balance and the
NIST bound passing. Boiling-stops: `ref-sf` ≥ `ref-v40` ≥ the earlier 14/32 rate on the ≥ 15 bands; the
evaporation arms complete everything unless T exceeds 2 T_b. Evaporated energy fraction: < 10 % of the
absorbed energy on every row (Gan 2021 Fig. 3 reports total losses ≈ 10 %). Mesh: 10 → 5 µm change > 5 % on
at least one of the 3 shallow cases (pools 1–3 cells deep at 20 µm).
