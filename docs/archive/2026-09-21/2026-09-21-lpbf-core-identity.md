# LPBF Core Identity Implementation Plan

> For agentic workers: use superpowers:executing-plans, sequential native execution.

**Goal:** Bind new thermal results to explicit model/backend, resolved material
and input identities before persistence integration.

**Architecture:** A small pure Python contract module is called by the existing
solver and evidence boundary. Existing numerical functions, queue and cache key
remain authoritative. The TypeScript response type documents the optional field.

**Tech Stack:** Existing Python3.12/NumPy, TypeScript; no added dependencies.

**Spec:** `docs/LPBF_SHARED_CORE_CONTRACT.md`.

## Execution ledger — owner01a0c36f

Baseline b9567c6. Task1 and Task2 implemented together as one interface package;
current application git log records its final commit. Preflight: Python keys,
allowlisted models and units match the TypeScript consumer; no numeric adapter
duplication. Ruling: preserve the expressly requested shared LOCAL checkout and
use this ledger/standard commands instead of shell-helper worktree automation.
No subagents; no external changes reverted. Self-review only.

Task1 RED:10 assertion failures plus absent module; missing bindings and changed
inputs not rejected. GREEN:7 then8tests after real Queue restore/cache test.
Current Windows engineering25PASS/1skip, source7PASS/1skip. Current WSL
8core+26engineering+8source+5peak+7overlap=54PASS, no skips.40W pre/post parity:
six numerical sections and all64artifact SHA256s identical. Real Python result
passes TypeScript parser unchanged. Logs `.runtime/phase0-audit/core-*01a0c36f*`.

Task2 RED: missing expected exception for malformed contract (after Node spawn
EPERM was removed with scoped permission). GREEN focused parser/diagnostics6PASS.
Strict targeted TS initially found existing lackOfFusion narrowing loss in a
callback; introduced a stable local reference, unchanged logic; strictTS nowPASS.
Full unit initially167PASS, lint/buildPASS. OTHER writer later edited UQ/import
paths: latest full150tests=147PASS/3FAIL, named uq-coupon-csv, uq-empirical,
uq-presentation (uqLabData import-time throw). Those paths are preserved and not
part of this commit. Latest lint/buildPASS37.97s (existing chunk warning).
Ruling: deliver bounded LPBF package with explicit shared-tree failure; do not
overwrite concurrent unrelated UQ work to manufacture a green overall result.

Remaining goal: run/experiment persistence and shared physics extraction; Phase0
still OPEN. The steps below record the implemented task design; execution results
above are authoritative about actual passes and the remaining integration issue.

## Global constraints

- Phase0 OPEN; no later-phase or experimental acceptance.
- Keep model IDs, source conditions and current numerical tolerances.
- No installation, push, live migration or secondary-module changes.
- Legacy absence remains legacy; contract present but invalid must fail.
- Source archive metadata is not a complete run database.

## Review focus

- Backend auto must report actual execution, not requested capability.
- Mutated material tables/settings must invalidate binding on restore.
- High-fidelity fallback must remain analytical and unvalidated.
- Null/unknown/forged contracts must not become legacy by truthiness.
- Existing numerical metrics and artifact payloads must not change.

### Task 1: Pure contract and regression

Files: create `python/lpbf_core_contract.py`,
`python/test_lpbf_core_contract.py`; modify `python/lpbf_simulation.py` and
`python/lpbf_evidence.py`. Own only these paths and checkpoint documentation.

Interfaces: `build_core_contract(settings, material, solver_id, effective_mode)`
returns the exact dictionary in the spec;
`enforce_core_contract(result)` accepts legacy absence, otherwise recomputes and
compares. It raises ValueError for identity or contract mismatch.

- [ ] Add regression using a real screening result and a40W standard melt run:

```python
result = run({'mode': 'standard', 'backend': 'reference', 'power_W': 40,
              'mesh_um': 40, 'trackLength_um': 200, 'cooling_s': .0001, 'dwell_s': 0})
assert result['coreContract']['actualBackend'] == 'numpy-reference'
changed = copy.deepcopy(result)
changed['material']['table'][0][2] += 1
with self.assertRaises(ValueError):
    enforce_thermal_balances(changed)
```

- [ ] Run `.runtime/lpbf-win-py312/Scripts/python.exe -B python/test_lpbf_core_contract.py`;
  record failure because contract/binding is absent before implementation.
- [ ] Implement canonical hash with
  `hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')).hexdigest()`.
  Build the strict allowlist mapping, explicit units/physics, and reject invalid
  thermal requested/actual backend combinations.
- [ ] Set `result['coreContract'] = build_core_contract(...)` immediately before
  existing `enforce_thermal_balances(result)`. At the start of that boundary call
  `enforce_core_contract(result)` even for analytical results.
- [ ] Tests cover sorted-key hash stability, property/input drift, version/units/
  flags/evidence forgery, explicit-null rejection, true legacy absence, auto backend
  selection and high-fidelity fallback. OpenFOAM mapping is a pure contract fixture,
  not a claim of runtime execution. Unknown solver/mode combinations raise.
- [ ] Compare actual40W metrics to the saved pre-change profile with tight numerical
  tolerance; run engineering and heat-source suites. Update docs/PROOF and commit
  only named changes after diff/staged review.

### Task 2: Consumer boundary and persistence preparation

Files: `src/services/lpbfSimulationService.ts`, `tests/lpbf-contract.test.ts`.
Add a `CoreContract` type matching v1 and optional field on `SimulationResult`.
Use synchronous structural validation at the existing response boundary; Python
remains the SHA binding authority. Client parsing cannot claim cryptographic
verification merely from64hex strings. Check model/backend/mode/solver agreement,
unit/physics literals and field shape; preserve exact returned hashes.

- [ ] Add malformed core-contract fixtures to existing parseSimulationJob tests;
  verify failure before implementation, retaining a legacy fixture without field.
- [ ] Add strict optional-field parsing using `r.coreContract !== undefined` and
  reject null, unknown model/backend, altered units/physics and identity mismatch.
- [ ] Run targeted TypeScript tests, full unit/lint/build. No UI markup change;
  actual browser check is required when the later run-history UI is introduced.
- [ ] Commit and record the next run-record schema/import/restore package. Draft
  its detailed plan against the source repository API immediately before coding;
  do not infer Phase1 acceptance from this preparatory contract package.
