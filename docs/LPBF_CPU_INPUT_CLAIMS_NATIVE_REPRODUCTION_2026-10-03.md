# LPBF V1 input-claims candidate: native-environment reproduction

**Date:** 2026-10-03
**Frozen candidate:** `ec3a5fcbeb1c5aa1b250ed31a4e812796c5d17ce`
**Result:** native dependency installation, lint, and build exited 0. The final neutral-temp unit run reported 371 passed, 1 skipped, 0 failed. This is bounded software reproduction evidence, not full V1, browser/UI, experimental, or production validation.

## Candidate identity and environment

The tested checkout is `.runtime/v1-input-claims-native-20261003`, a separate frozen candidate archive. Its 1,579-file mapping matches the source manifest whose original `snapshot` field names `.runtime/v1-input-claims-20261003`; the native runtime root is recorded separately in the preflight and guard evidence. The manifest file SHA-256 is `4573e2295d8d9721700c177adf39826f9a956c24cee3b524a9ce3b8eb3a6c1a2`. Pre/post guards around install, lint, and the final neutral-temp lint/unit/build all report 1,579 expected files and no mismatches. The source tree was not restored or edited to obtain a passing result.

The native preflight recorded Node `v24.20.0`, npm `11.19.0`, and reused Python `3.12.10` with NumPy `2.2.6` and pydantic `2.13.5`; `pip check` and a Python import/version smoke check exited 0. The Python environment was reused, not newly created. Native preflight recorded sandbox-network/offline/proxy variables as absent and `globalOrProxyConfigurationChanged=false`; no proxy or install-script policy override was applied.

## Installation and first unit run

`npm ci --offline=false --no-audit --no-fund` exited 0 in `135.031` seconds and added 850 packages. npm warned that `three-mesh-bvh@0.7.8` is deprecated due to Three.js version incompatibility. It also warned that install scripts for nine package entries were not covered by `allowScripts`; no approval-policy changes were made. The raw log is retained in support.

The first lint exited 0 in `23.141` seconds. The first unit run exited 1 in `55.157` seconds: 372 tests, 370 passed, 1 failed, 1 skipped. The single failure was `tests/vite-watch.test.ts` (`application source watcher must become ready`). This failed result remains recorded; it was not replaced or removed. Build was not run in that initial sequence.

## Final neutral-temp sequence

A separate sequence set a fresh neutral `TEMP`/`TMP`, reused the already-installed dependency tree, and did **not** run another npm install. Its runner source was byte-identical to the recovered helper (SHA-256 `edbd890bd139fb33269851b82e99798eeeaa49bd640f0557f29b8bd985ae7e69`); the bounded static review in the support package returned GO. Each command had a recorded pre- and post-source guard.

| Gate | Outcome | Elapsed | Evidence |
|---|---:|---:|---|
| `npm run lint` | exit 0 | 21.375 s | `neutral-lint.log`, exit record, pre/post guards |
| `npm run test:unit` | 371 passed, 1 skipped, 0 failed; exit 0 | 49.255 s | `neutral-unit.log`, exit record, pre/post guards |
| `npm run build` | exit 0 | 128.645 s | `neutral-build.log`, exit record, pre/post guards |

The build completed but emitted the Vite warning that some minified chunks exceed 500 kB; the largest shown was the Three.js module at 734.16 kB. The successful npm install log also retains its deprecation and `allowScripts` warnings. These warnings are reported, not suppressed.

## Limits

This record establishes a successful install plus these candidate software gates under the stated native Windows environment and neutral temp path. It does not establish browser interaction, cancellation/stale-result behavior, all V1 requirements, experimental validation, or production readiness. The initial watcher failure and final neutral-temp PASS are both retained as distinct outcomes. The support SHA-256 inventory covers every copied evidence file except the inventory itself.
