# UQ evidence and calculation boundaries

The UQ lab is a screening worksheet and model exploration tool. Imported records are user-supplied and unverified; generated coupons remain synthetic, including after CSV export and reimport. Neither source establishes qualification or a reviewed MMPDS handbook allowable.

## Coupon records

CSV requires explicit yield strength (MPa), ultimate tensile strength (MPa), and elongation (%) columns. Every required value must be finite. Missing lot, orientation, test temperature, reduction of area, hardness and traceability remain absent; the importer never synthesizes them. Invalid input is rejected as a whole and preserves existing coupons. Quoted fields, escaped quotes, leading metadata and BOM are supported. Unknown or duplicate headers and ragged rows are rejected. The parser bounds input to 2 million characters, 10,000 rows and 32,000 characters per cell; the UI additionally rejects files over 5 MB.

Export preserves record identity, optional blanks, zero values and evidence origin. Text cells use a reversible apostrophe-v1 encoding to avoid spreadsheet formula interpretation. Files without origin metadata import as unknown, not measured. Uploads and edits remain session-only; export before reloading.

The worksheet calculates yield, UTS and elongation separately from their own columns with their own units and selected minima. Those minima are reference context whose applicability to imported rows is unverified. Cpl is the descriptive lower-specification index (mean minus minimum)/(3 times sample SD). Observed conformance is the supplied-row fraction above the minimum, not a population failure probability. Missing or degenerate statistics remain unavailable.

## Empirical tolerance calculations

Normality is **not tested**. Skewness and kurtosis do not supply an Anderson–Darling p-value. No allowable confidence interval or standard error is invented. Normal-model lower tolerance limits, where available, use the approximate Natrella formula described by [NIST](https://www.itl.nist.gov/div898/handbook/prc/section2/prc263.htm), with independent normal observations assumed. They are not exact noncentral-t factors or certified MMPDS values. Small samples can differ materially from the exact result: NIST's n=6, 90% coverage, 99% confidence example gives approximate 5.2808 versus exact 4.4111. Unsupported inputs return unavailable. The actual [Anderson–Darling test](https://www.itl.nist.gov/div898/handbook/eda/section3/eda3e.htm) would require a separately implemented, calibrated test.

## Propagated model samples

The existing custom Sobol sampler applies a digital shift, skips the origin and accepts arbitrary sample counts. Balanced-net guarantees are not claimed; see the restrictions documented for [Sobol sampling](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.qmc.Sobol.html). Centered L2 discrepancy is a point-set diagnostic on at most the first 150 points, compared with one seeded pseudo-random set. It is not measured estimator error, speedup, variance reduction or effective sample size; those outputs remain null.

QMC allowable standard errors and confidence intervals are unavailable without independent randomized replicates. The solver no longer accepts pseudo-random sampling (removed in f9ae3e4) and the UQ-Lab UI no longer offers it; the former iid-normal pseudo-random approximation is therefore not reachable through the API or UI. Existing propagated property means, sample spread, histograms and normal-model bound estimates are preserved; this work does not validate the material response law.

Sensitivity uses seeded Monte Carlo A/B pick-freeze samples for the actual supplied chemistry and cooling/aging distributions. First-order centered Saltelli and total-order Jansen estimates are raw, without clipping or normalization; finite-sample values may fall outside [0,1]. Zero output variance makes indices unavailable. Inputs are assumed independent; composition closure/correlation is not modeled. These are model sensitivity estimates without confidence intervals, not experimental causal evidence. The [SciPy sensitivity documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.sobol_indices.html) describes the estimator framework; this implementation is local and does not claim SciPy validation.

## Verification

- `npm run test:unit`: 79 passing tests, including CSV round trips/rejection/provenance, numerical edge cases, published NIST factors, property identity and asynchronous stale-result protection.
- `py -3 python/test_stochastic_uq_evidence.py`: 8 passing regressions for unavailable claims, unchanged seed-42/500-draw descriptive baselines, actual chemistry, raw sensitivity, zero variance, dimension limits and discrepancy.
- `npm run lint` and `npm run build`: required final checks; execution evidence is recorded in `PROOF.md`.
- Production browser: a synthetic three-row CSV gives yield mean 110 MPa, UTS mean 220 MPa and elongation mean 4%. Missing lot information stays unknown. An invalid UTS upload shows an error and preserves all three previous coupons. AlSi10Mg sensitivity uses the selected composition and exposes unnormalized estimates.

Software regressions and synthetic fixtures are not experimental metallurgy validation. Existing LPBF benchmark failures and measurement gaps remain unchanged.
