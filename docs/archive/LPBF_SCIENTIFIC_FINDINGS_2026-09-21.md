# LPBF scientific evidence findings

Bounded follow-up to LPBF_CORE_BASELINE_2026-09-21.md, not an exhaustive science
audit. User explicitly requested LPBF-only common core/database work and removal
of unscientific behavior. Initial audit remains open.

## Repaired: fabricated experimental comparison

Before repair, ExperimentalValidationLab sent fixed Ti64/250W/1000mm/s and
PDAS1.5um/keyhole depth120um irrespective of active run. Its measured inputs were
prefilled1.6/150. These were not computed predictions or user measurements.
lpbf_experimental_validation returned `validated` even with zero metric pairs,
assigned EBSD/CT method labels, and used undocumented15/20percent cutoffs to claim
pass/high/moderate agreement. Old Phase tests asserted those false semantics.

The UI now states comparison unavailable because no run/source dataset is bound.
It has no substitute constants, measurement defaults or execute control. It
explains the shared stationary thermal core does not resolve PDAS/keyhole depth.
Independent models and reviewed measurement operators remain necessary.

The existing specialist API now requires explicit material/process/source and at
least one finite paired metric. Missing/boolean/string/nonfinite/negative values
fail; relative error requires a positive measured denominator. Returned numbers
are descriptive absolute and relative errors only. Status is comparison-only,
validationStatus unvalidated, productionReady false, every metric review and
overallMatch unknown even for exact agreement. Source text is caller-supplied,
sourceIntegrity not-verified; UUID is a transient comparison receipt, not a
persisted provenance chain. No acceptance thresholds are manufactured.

## Evidence

Python Phase tests: old behavior12FAIL+1error →5PASS. UI render regression
RED→PASS; lint and buildPASS36.60s. Real Node route→bridge→Python on3197:
equal synthetic pair comparison-only/unvalidated/unknown; empty body400. Saved
.runtime/phase0-audit/evidence-api-01a0c383.json.
Actual browser rendered the compiled real component using production CSS;
Tab/Enter unmount/remount and readable layout passed. This was the isolated
`tests/lpbf-evidence-browser.html` harness, not a claim that the full app's
unrelated EIS/UQ paths work. Vite middleware initially stalled; standalone
esbuild compiled the same component and served it locally for the successful
check. No browser-generated simulated metrics were used.

## Remaining LPBF gates

- Fullrun/source bundles and user-facing selection must bind exact run/source
  revisions, material/process identity, metric definition and uncertainty.
- NIST digital signal conversion remains null/unreviewed; source hashes do not
  qualify calibration. No inferred emissivity/equation repair.
- Strong40/20um thermal mesh sensitivity remains unresolved; conservation is not
  convergence or experimental validation.
- Old GPU flow prototype remains scientifically distinct from the CPU thermal
  core; no automatic backend equivalence or route enabling.
- Powder worker packing wiring and other specialist assumptions remain the
  bounded baseline's open audit items. External writer modified powder_packer,
  powder_bed_raytracer and marangoni_pore_instability_solver during this session;
  user stopped that task. Those changes were preserved and not certified here.
