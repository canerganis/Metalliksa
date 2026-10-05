# LPBF process map: 316L Stainless Steel, beam 80 um (2026-10-05)

**Process-map sweep of screening kernels; not experimental validation; estimated material laws; flat-plate absorptivity assumed; non-computed cells are marked, never filled.**

Schema `lpbf-process-map-1`; implementation fingerprint `11b04b8fa3de1a6b2cf46afb67e6c439f05ca9d0ab2affec92f1e5b239eb3359`. Honesty: screening kernels only; not experimental validation; estimated material laws; absorptivity assumed (flat-plate, not measured); regime labels are an a-priori normalised-enthalpy index, not the kernels' own result; non-computed cells carry no width/depth information. `experimentalValidation` = false.

Inputs: layer 30 um, hatch 100 um, preheat 20 C; 19 powers (50-500 W) x 15 speeds (200-1600 mm/s); kernels rosenthal, eagar-tsai, goldak.

## Regime rule

Screening classifier, not the papers' regime definition. Inputs: normalised enthalpy dH/h_s = eta*P / (rho*cp_s*max(50, T_liq-T0)*sqrt(pi*alpha_s*v*r^3)) (same form as lpbf_thermal_solver.py, flat-plate absorptivity_IR of the material authority, solid k/cp, r = d/2) and the dataset's own balling flag. balling == 1 -> 'balling-flagged' (Hofmann only); otherwise dH/h_s < 15 -> 'conduction', 15 <= dH/h_s < 30 -> 'transition', >= 30 -> 'keyhole'. Measured D/W is recorded next to the label but not used for it.

Table legend: **C** conduction, **T** transition, **K** keyhole (normalised-enthalpy index, same for all kernels); a trailing `*` marks a cell whose kernel extentStatus is not `computed` (no width/depth information). Rows are power, columns are scan speed (mm/s).

## Kernel rosenthal

| P W \ v mm/s | 200 | 300 | 400 | 500 | 600 | 700 | 800 | 900 | 1000 | 1100 | 1200 | 1300 | 1400 | 1500 | 1600 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 500 | K | K | K | K | K | K | K | K | K | K | K | K | K* | K* | K* |
| 475 | K | K | K | K | K | K | K | K | K | K | K | K | K* | K* | K* |
| 450 | K | K | K | K | K | K | K | K | K | K | K | K | K* | K* | T* |
| 425 | K | K | K | K | K | K | K | K | K | K | K | K | K* | T* | T* |
| 400 | K | K | K | K | K | K | K | K | K | K | K | T* | T* | T* | T* |
| 375 | K | K | K | K | K | K | K | K | K | K | T | T* | T* | T* | T* |
| 350 | K | K | K | K | K | K | K | K | T | T | T | T* | T* | T* | T* |
| 325 | K | K | K | K | K | K | K | T | T | T | T | T* | T* | T* | T* |
| 300 | K | K | K | K | K | K | T | T | T | T | T* | T* | T* | T* | T* |
| 275 | K | K | K | K | T | T | T | T | T | T | T* | T* | T* | T* | T* |
| 250 | K | K | K | T | T | T | T | T | T | T* | T* | T* | T* | T* | T* |
| 225 | K | K | T | T | T | T | T | T | T | T* | T* | T* | T* | T* | C* |
| 200 | K | K | T | T | T | T | T | T | T* | T* | T* | C* | C* | C* | C* |
| 175 | K | T | T | T | T | T | T | T* | C* | C* | C* | C* | C* | C* | C* |
| 150 | T | T | T | T | T | T | C* | C* | C* | C* | C* | C* | C* | C* | C* |
| 125 | T | T | T | C | C | C* | C* | C* | C* | C* | C* | C* | C* | C* | C* |
| 100 | T | T | C | C | C* | C* | C* | C* | C* | C* | C* | C* | C* | C* | C* |
| 75 | C | C | C | C | C* | C* | C* | C* | C* | C* | C* | C* | C* | C* | C* |
| 50 | C | C | C* | C* | C* | C* | C* | C* | C* | C* | C* | C* | C* | C* | C* |

Heuristic zone: 119 of 285 cells not computed (heuristic-width-fallback: 119); 166 computed. Regime-label changes between neighbouring cells: 48.

## Kernel eagar-tsai

| P W \ v mm/s | 200 | 300 | 400 | 500 | 600 | 700 | 800 | 900 | 1000 | 1100 | 1200 | 1300 | 1400 | 1500 | 1600 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 500 | K | K | K | K | K | K | K | K | K | K | K | K | K | K | K |
| 475 | K | K | K | K | K | K | K | K | K | K | K | K | K | K | K |
| 450 | K | K | K | K | K | K | K | K | K | K | K | K | K | K | T |
| 425 | K | K | K | K | K | K | K | K | K | K | K | K | K | T | T |
| 400 | K | K | K | K | K | K | K | K | K | K | K | T | T | T | T |
| 375 | K | K | K | K | K | K | K | K | K | K | T | T | T | T | T |
| 350 | K | K | K | K | K | K | K | K | T | T | T | T | T | T | T |
| 325 | K | K | K | K | K | K | K | T | T | T | T | T | T | T | T |
| 300 | K | K | K | K | K | K | T | T | T | T | T | T | T | T | T |
| 275 | K | K | K | K | T | T | T | T | T | T | T | T | T | T | T |
| 250 | K | K | K | T | T | T | T | T | T | T | T | T | T | T | T |
| 225 | K | K | T | T | T | T | T | T | T | T | T | T | T | T | C |
| 200 | K | K | T | T | T | T | T | T | T | T | T | C | C | C | C |
| 175 | K | T | T | T | T | T | T | T | C | C | C | C | C | C | C |
| 150 | T | T | T | T | T | T | C | C | C | C | C | C | C | C | C |
| 125 | T | T | T | C | C | C | C | C | C | C | C | C | C | C | C |
| 100 | T | T | C | C | C | C | C | C | C | C | C | C | C | C | C |
| 75 | C | C | C | C | C | C | C | C | C | C | C | C | C | C | C |
| 50 | C | C | C | C | C | C | C | C | C | C | C | C | C | C | C |

Heuristic zone: 0 of 285 cells not computed (none); 285 computed. Regime-label changes between neighbouring cells: 48.

## Kernel goldak

| P W \ v mm/s | 200 | 300 | 400 | 500 | 600 | 700 | 800 | 900 | 1000 | 1100 | 1200 | 1300 | 1400 | 1500 | 1600 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 500 | K | K | K | K | K | K | K | K | K | K | K | K | K | K | K |
| 475 | K | K | K | K | K | K | K | K | K | K | K | K | K | K | K |
| 450 | K | K | K | K | K | K | K | K | K | K | K | K | K | K | T |
| 425 | K | K | K | K | K | K | K | K | K | K | K | K | K | T | T |
| 400 | K | K | K | K | K | K | K | K | K | K | K | T | T | T | T |
| 375 | K | K | K | K | K | K | K | K | K | K | T | T | T | T | T |
| 350 | K | K | K | K | K | K | K | K | T | T | T | T | T | T | T |
| 325 | K | K | K | K | K | K | K | T | T | T | T | T | T | T | T |
| 300 | K | K | K | K | K | K | T | T | T | T | T | T | T | T | T |
| 275 | K | K | K | K | T | T | T | T | T | T | T | T | T | T | T |
| 250 | K | K | K | T | T | T | T | T | T | T | T | T | T | T | T |
| 225 | K | K | T | T | T | T | T | T | T | T | T | T | T | T | C |
| 200 | K | K | T | T | T | T | T | T | T | T | T | C | C | C | C |
| 175 | K | T | T | T | T | T | T | T | C | C | C | C | C | C | C |
| 150 | T | T | T | T | T | T | C | C | C | C | C | C | C | C | C |
| 125 | T | T | T | C | C | C | C | C | C | C | C | C | C | C | C |
| 100 | T | T | C | C | C | C | C | C | C | C | C | C | C | C | C |
| 75 | C | C | C | C | C | C | C | C | C | C | C | C* | C* | C* | C* |
| 50 | C | C | C | C | C | C* | C* | C* | C* | C* | C* | C* | C* | C* | C* |

Heuristic zone: 14 of 285 cells not computed (heuristic-width-fallback: 13, width-floor-applied: 1); 271 computed. Regime-label changes between neighbouring cells: 48.

## Heuristic-zone counts

| kernel | cells | computed | not computed | by extentStatus |
|---|---|---|---|---|
| rosenthal | 285 | 166 | 119 | heuristic-width-fallback: 119 |
| eagar-tsai | 285 | 285 | 0 | - |
| goldak | 285 | 271 | 14 | heuristic-width-fallback: 13, width-floor-applied: 1 |

## Regime boundaries

Neighbouring grid cells whose regime label differs (JSON `regimeBoundaries`; resolution = grid step; derived from labels, not fitted). Counts by unordered label pair:

| kernel | changes | by pair |
|---|---|---|
| rosenthal | 48 | conduction-transition: 21, keyhole-transition: 27 |
| eagar-tsai | 48 | conduction-transition: 21, keyhole-transition: 27 |
| goldak | 48 | conduction-transition: 21, keyhole-transition: 27 |

The boundary sets are identical for all kernels: the label is a kernel-independent index.

## Dataset overlay

187 published single-track rows with the same material and beam diameter within 1 um (measured, not predicted; no uncertainty model; not on the grid).

Regime labels of the overlay rows: balling-flagged 59, conduction 26, keyhole 55, transition 47.

| regime | n | P range W | v range mm/s | median D/W | min D/W | max D/W |
|---|---|---|---|---|---|---|
| balling-flagged | 59 | 100-500 | 600-1500 | 0.45 | 0.11 | 0.95 |
| conduction | 26 | 50-200 | 450-1500 | 0.27 | 0.12 | 0.42 |
| keyhole | 55 | 200-500 | 300-900 | 1.14 | 0.43 | 2.85 |
| transition | 47 | 100-325 | 300-1500 | 0.48 | 0.21 | 1.09 |

Rows flagged as balling in the dataset: 59 (labelled `balling-flagged`, which the grid cannot produce). Every row with its measured width/depth is in JSON `overlay[]`.

## Absorption path

Path: **flat-plate** (pinned: True). sys.modules['powder_bed_raytracer'] = None is set in the main process and in every worker before lpbf_thermal_solver is imported, so the solver's `from powder_bed_raytracer import ...` raises ImportError and its except branch (flat-plate absorptivity) is taken; the solver is not edited. Absorptivity by material: 316L 0.42. Fallback warnings captured: 855 of 855 solver calls.

flat-plate absorptivity_IR; the GPU powder ray tracer was not used. fallbackWarnings counts the solver's 'GPU Powder Bed Ray Tracing failed' messages (captured, not suppressed): with the pin it fires once per solver call (solverCalls), which confirms the flat-plate branch was the realized path.

## Limits

- Screening kernels (Rosenthal, Eagar-Tsai, Goldak) of calculate_meltpool_physics; nothing here is experimental validation.
- Flat-plate absorptivity assumed (flat-plate; 316L 0.42); the absorptivity acting in a physical track is unknown and the GPU powder ray tracer is not used.
- The kernels have no powder-layer dependence: width, depth and length are identical for any layer thickness; layer and hatch enter only the lack-of-fusion / defect screens carried per cell.
- Regime labels are an a-priori normalised-enthalpy index (lpbf_public_datasets.classify_regime, thresholds 15 and 30), identical for all kernels; they are not a kernel result and not the papers' regime definition. 'balling-flagged' cannot occur in the map (it needs a dataset flag).
- Regime boundaries are neighbouring-grid-cell label changes (resolution = grid step), not fitted or interpolated curves.
- Non-computed cells (extentStatus other than 'computed') carry no width/depth information: the values stored are the solver's heuristic fallback / floor and must not be read as a prediction. Counts per kernel: rosenthal 119 of 285; eagar-tsai 0 of 285; goldak 14 of 285.
- Lack-of-fusion, keyhole-porosity and balling entries are the solver's own screens carried as returned, including on non-computed cells; no criterion is added here.
- Overlay rows (187) are published single-track measurements (powder layers as in the dataset) matched by material and beam diameter only; they are not on the grid, carry no uncertainty model, and are shown next to the map, not compared with it.
