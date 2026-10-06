# Secondary research modules — deferred by user, 2026-09-21

The user's primary target is LPBF engines and the database supplying them.
Keep secondary modules available, but do not make their complete repair a gate
for LPBF progress. Investigate them only if a concrete dependency affects LPBF.
The user proposed splitting the application. Immediate organization is two work
streams; separate repositories or deployments have not been implemented.
Latest user decision reverses the earlier prohibition: build a shared LPBF core.
Keep model identities, assumptions and tests explicit. Secondary modules remain
deferred; their integration into the LPBF core is not a current requirement.

## Completed checkpoint before reprioritization

Python synthetic recovery contract: 0159cdf. UI continuation routes displayed
synthetic points through Python autofit, rejects missing/failed reports and stale
responses, and removes arbitrary recovery grades and synchronous client fitting.
Unit133, lint and build passed. Real browser benchmark, eight-level sweep,
HTTP503, incomplete report, delayed reply, topology replacement, keyboard export
and lifecycle10 checks passed. These are synthetic software/numerical checks.

## Deferred findings

- EIS built-in datasets and exports: misleading laboratory/instrument provenance;
  related SOH/DRT/Tafel interpretations need bounded scientific review.
- CNLS/physical validation static ASTM/K-K banners and legacy Voigt stationarity
  screening remain unverified. No certification or stationarity claim is accepted.
- Noise presets/simulator wording and per-model browser analytical spectra need
  a validity audit. Scientific sampling is legitimate but not measured evidence.
- EDS AI error fallback/compliance and heat-treatment empirical claims remain
  research limitations. Revisit materialDataPipeline only if used by LPBF inputs.
- Deferred EIS optimizer input/global-budget extremes and null render consumers.

### Weak and Dummy Physics Engines (Non-LPBF)
- `marangoni_pore_instability_solver.py`: deleted 2026-10-04 (no UI consumer).
- `powder_packer.py` & `powder_bed_raytracer.py`: Replaces deterministic DEM with `random.triangular`/`np.random.uniform` sphere spawning.
- `cnls_fitting_solver.py` (`inverse_alloy_optimizer.py` deleted 2026-10-04): Genetic/Evolutionary algorithms rely on basic `random.uniform`/`gauss` mutations.
- `stochastic_uq_mmpds_solver.py`: Uses standard pseudo-random draws instead of relying entirely on deterministic QMC (Sobol).
- `src/services/pythonComputationService.ts`: Invokes `random()` to fabricate defect geometry (diameter, sphericity, position) dynamically when fluid/mushy zones are detected.
- `src/components/uqLabData.ts` & `src/utils/monteCarloEngine.ts`: Frontend relies on raw `Math.random()` to generate mock mechanical properties (elongation, microstrain, crystallite size).
- `tafelParser.ts` & `eisFileParser.ts`: Injects "pseudo-random Gaussian noise" directly during file ingestion instead of using raw instrumentation data.

Do not restart this list automatically when continuing the LPBF master plan.
