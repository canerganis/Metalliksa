# Contract fix round 3 handoff

## Change summary

Final implementation commit in `Metalliksa-1-orch-contract`: `fdf08b410553f39dcfbf8e2230957dc7b3a56bf4` (branch `orch/contract`). No push.

- V2 campaign run identities are derived from archived `result.json` captures and now include `executedSettings`, including `beamDiameter_um`. Campaign observations are re-derived from the capture and cross-checked against the archived NPZ section artifact. V1 handling remains on its legacy path.
- Bundle verification checks each campaign against the archived run and exact source revision/artifact. Verify, portable import, and restore reject rehashed forged campaign data; bundle errors are specific without returning filesystem paths.
- Current transcription prohibits `experimentalTrackIds` consistently in the client, TypeScript repository, and Python validator.
- Added independent client mutants, a Table 4 post-verify reread mutation, hostile-bundle positive control, source-artifact binding coverage, and verify/import/restore claim-flag coverage.

## Verification log

Agent-level checks below ran with Git `HEAD` `67d4a4acb6c4e09c0b25700281538e6ad3a10e81` while the shared worktree held uncommitted round-3 changes. They are intermediate evidence; final acceptance is the post-commit section.

### Client scope (agent C)

| Exact command | HEAD | Exit and result |
|---|---|---|
| `node_modules/.bin/tsx --test tests/lpbf-run-proxy-campaign-client.test.ts` | `67d4a4acb6c4e09c0b25700281538e6ad3a10e81` | 0; 9 passed, 0 failed |
| `npx tsc --noEmit` (before A/B edits landed) | `67d4a4acb6c4e09c0b25700281538e6ad3a10e81` | 0; empty output |
| `node_modules/.bin/tsx --test tests/lpbf-run-proxy-campaign-client.test.ts` (repeat) | `67d4a4acb6c4e09c0b25700281538e6ad3a10e81` | 0; 9 passed, 0 failed |
| `npx tsc --noEmit` (during A/B edits) | `67d4a4acb6c4e09c0b25700281538e6ad3a10e81` | 2; failed with 3 errors: missing `PYTHON_ROOT`, missing `spawn`, and a `Buffer<ArrayBufferLike>` passed to a `string` parameter in `tests/lpbf-run-bundle.test.ts:116` |
| `node_modules/.bin/tsx --test tests/lpbf-run-proxy-campaign-*.test.ts tests/lpbf-run-proxy-campaign-*.test.tsx` | `67d4a4acb6c4e09c0b25700281538e6ad3a10e81` | 0; 12 passed, 0 failed |
| `git diff --check -- src/services/lpbfRunArchiveClient.ts tests/lpbf-run-proxy-campaign-client.test.ts` | `67d4a4acb6c4e09c0b25700281538e6ad3a10e81` | 0; no output |

### Service and Python scope (agent B)

| Exact command | HEAD | Exit and result |
|---|---|---|
| `python -B -m unittest test_lpbf_nist_proxy_campaign` (cwd `python/`) | `67d4a4acb6c4e09c0b25700281538e6ad3a10e81` | 0; 24 tests, OK |
| `node_modules/.bin/tsx --test tests/lpbf-nist-comparison-api.test.ts` (first refactor attempt) | `67d4a4acb6c4e09c0b25700281538e6ad3a10e81` | 1; 0 passed, 1 failed; missing `PYTHON_ROOT` |
| `node_modules/.bin/tsx --test tests/lpbf-nist-comparison-api.test.ts` (second refactor attempt) | `67d4a4acb6c4e09c0b25700281538e6ad3a10e81` | 1; 0 passed, 1 failed; missing `spawn` import |
| `node_modules/.bin/tsx --test tests/lpbf-nist-comparison-api.test.ts` (after fixes) | `67d4a4acb6c4e09c0b25700281538e6ad3a10e81` | 0; 1 passed, 0 failed; includes Table 4 reread mutation |
| `python -B -m unittest test_lpbf_nist_proxy_campaign` (repeat) | `67d4a4acb6c4e09c0b25700281538e6ad3a10e81` | 0; 24 tests, OK |
| `git diff --check -- server/lpbfProxyCampaignBinding.ts server/lpbfNistProxyCampaignService.ts python/lpbf_nist_proxy_campaign.py python/test_lpbf_nist_proxy_campaign.py tests/lpbf-nist-comparison-api.test.ts` | `67d4a4acb6c4e09c0b25700281538e6ad3a10e81` | 0; no whitespace errors |

The Table 4 test changes JSON whitespace after successful artifact-store verification, preserves byte size and parsed case-0 data, and expects the reread hash guard to reject it.

### Provenance and bundle scope (agent A)

| Exact command | HEAD | Exit and result |
|---|---|---|
| `node_modules/.bin/tsx --test tests/lpbf-run-bundle.test.ts` (two pre-fixture-fix runs) | `67d4a4acb6c4e09c0b25700281538e6ad3a10e81` | 1 each; each run 10 passed, 4 failed; first had unrelated fake eligible runs, second had invalid capture-mode/core/audit fixtures; fixtures were corrected |
| `node_modules/.bin/tsx --test --test-name-pattern="no-op rehashed" tests/lpbf-run-bundle.test.ts` | `67d4a4acb6c4e09c0b25700281538e6ad3a10e81` | 0; 1 passed, 0 failed |
| `node_modules/.bin/tsx --test --test-name-pattern="HTTP verify, restore" tests/lpbf-run-bundle-api.test.ts` | `67d4a4acb6c4e09c0b25700281538e6ad3a10e81` | 0; 1 passed, 0 failed |
| `node_modules/.bin/tsx --test tests/lpbf-run-bundle.test.ts tests/lpbf-run-bundle-api.test.ts tests/lpbf-run-repository.test.ts` (first combined run) | `67d4a4acb6c4e09c0b25700281538e6ad3a10e81` | 1; 31 passed, 1 failed; artifact-identity mutant did not mirror provenance, so schema rejected before the archived-run check |
| `node_modules/.bin/tsx --test tests/lpbf-run-bundle.test.ts tests/lpbf-run-bundle-api.test.ts tests/lpbf-run-repository.test.ts` (final scoped run) | `67d4a4acb6c4e09c0b25700281538e6ad3a10e81` | 0; 32 passed, 0 failed |
| `git diff --check -- server/lpbfRunRepository.ts server/lpbfRunBundle.ts server/lpbfRunBundleService.ts tests/lpbf-run-repository.test.ts tests/lpbf-run-bundle.test.ts tests/lpbf-run-bundle-api.test.ts` | `67d4a4acb6c4e09c0b25700281538e6ad3a10e81` | 0; no output |

Coverage includes a no-op rehashed positive control; distinct forged validation, optical-operator, and experimental-validation flags; forged identity/settings/geometry; direct verify/restore and portable import; HTTP verify/restore/import; exact bundle-source artifact binding; and the unchanged V1 restore path.

### Post-commit acceptance

The following ran after the final implementation commit, with the exact SHA recorded at each command start:

| Exact command | HEAD | Exit and result |
|---|---|---|
| `npx tsc --noEmit` (first implementation commit) | `5a1dffde07ef729367005a9f8d02d1876be64ab1` | 1; four TypeScript errors in bundle test SHA helper parameter types |
| `npx tsc --noEmit` (after type fix, final implementation commit) | `fdf08b410553f39dcfbf8e2230957dc7b3a56bf4` | 0; **real output was empty** (no stdout/stderr) |
| `node_modules/.bin/tsx --test tests/lpbf-*.test.ts tests/lpbf-*.test.tsx` (first full run) | `fdf08b410553f39dcfbf8e2230957dc7b3a56bf4` | 1; 256 tests, 254 passed, 1 failed, 1 skipped. `lpbf-run-workflow-roundtrip.test.ts` saw a transient Build Job `disk I/O error` |
| `node_modules/.bin/tsx --test --test-name-pattern="LPBF source select" tests/lpbf-run-workflow-roundtrip.test.ts` | `fdf08b410553f39dcfbf8e2230957dc7b3a56bf4` | 0; 1 passed, 0 failed |
| `node_modules/.bin/tsx --test tests/lpbf-*.test.ts tests/lpbf-*.test.tsx` (full rerun) | `fdf08b410553f39dcfbf8e2230957dc7b3a56bf4` | 0; 256 tests, 255 passed, 0 failed, 1 skipped |
| `python -B -m unittest test_lpbf_nist_proxy_campaign test_lpbf_bare_plate` (cwd `python/`) | `fdf08b410553f39dcfbf8e2230957dc7b3a56bf4` | 0; 46 tests, OK |

The TS suite emitted expected test logs about unavailable browser storage and intentionally corrupted source artifacts. It passed on rerun; the one skipped test remains skipped.

Tracked bytecode changed by the TS tests was restored with explicit `git checkout -- python/__pycache__/<path>` paths. No tracked `python/__pycache__` changes remained afterward.

The implementation checkout still has pre-existing user edits in `.claude/` and `.cursor/`; they were not staged or committed. The outer workspace also had unrelated dirty files; only this handoff was staged there. No push was made.
