# LPBF comparison evidence repair

> Use superpowers:executing-plans, native sequential execution; no agents.

**Goal:** Stop fixed synthetic predictions and unchecked arithmetic from being
presented as experimental validation.
**Architecture:** Fail closed in the unbound UI. Backend may compare explicitly
supplied finite numeric pairs, labelled comparison-only/unvalidated, without
pass thresholds, material/process defaults or implied source verification.
**Spec:** LPBF_SHARED_CORE_CONTRACT.md and LPBF_CORE_BASELINE_2026-09-21.md.
**Tech stack:** Existing Python/React/TypeScript; no dependency change.

## Scope and review focus

Only LPBF. No edits to the externally modified pythonComputationService module;
backend retains its existing broad response shape (all metrics review,
overallMatch unknown) with extra explicit evidence fields. The unbound UI no
longer consumes this service. Future bound comparison has a separate contract.
Review: empty metrics, nonfinite/bool/negative data, zero denominator, fabricated
source/method defaults, tight numerical agreement mistaken for validation.

### Task 1: honest arithmetic boundary

Files: python/lpbf_experimental_validation.py and python/test_phase10.py.
- [ ] Tests require `status == 'comparison-only'`, `validationStatus == 'unvalidated'`,
  `overallMatch == 'unknown'`, metric status review even at zero error.
- [ ] Missing pairs, missing material/process/source and nonfinite/bool/negative
  values raise ValueError. Relative error requires positive measured denominator.
- [ ] Run `.runtime/lpbf-win-py312/Scripts/python.exe -B python/test_phase10.py` RED.
- [ ] Replace heuristic15/20percent pass rules with descriptive absolute/relative
  error; source label comes from caller, explicitly not verified. Run GREEN.

### Task 2: remove fixed-result UI

Files: src/components/ExperimentalValidationLab.tsx and
tests/lpbf-experimental-evidence.test.tsx.
- [ ] Render test rejects fabricated numeric inputs and Run Traceability Pipeline;
  requires Comparison unavailable, exact source revision and completed run context.
- [ ] Run `node --import tsx --test tests/lpbf-experimental-evidence.test.tsx` RED.
- [ ] Replace unbound form with a clear missing-evidence panel. State that PDAS
  and keyhole depth are not shared thermal-core outputs; no substituted constants.
- [ ] Run focused test/lint/build and actual browser rendering/navigation checks.
  Update bounded findings and commit only owned files.

## Ledger

Task1: RED12failures+1error → GREEN5tests. Task2: RED missing unavailable message
→ GREEN1presentationtest. Current lint/buildPASS36.60s. ActualAPI exactmatch
comparison-only/unvalidated/unknown and emptyrequest400. Browser compiled real
component visual+Tab/Enter leave/returnPASS. Vite middleware stalled; ruling:
use esbuild compiled component/productionCSS on same isolated endpoint rather
than change application Vite config. Cost: does not verify full App mounting.
Self-review: limits explicitly visible; no evidence or thresholds fabricated.
External service file not modified; response retains compatible broad fields.

Preflight: no new shared service types; old broad response shape retained without
false qualification. User authorized LPBF-only scientific repair and stopped
other writer. Self-review under native/no-agents instruction.
