# LPBF V1 input-claims candidate: install attempts

**Date:** 2026-10-03
**Candidate under test:** `ec3a5fcbeb1c5aa1b250ed31a4e812796c5d17ce`
**Result:** this record covers two historical attempts, both blocked during dependency installation. Lint, unit tests, and build were not run within these attempts.

## Scope and source identity

This record covers only the two historical clean dependency installation attempts for the frozen input-claims candidate. The candidate is a Git archive of `ec3a5fcbeb1c5aa1b250ed31a4e812796c5d17ce`, with a 1,579-file SHA-256 manifest whose raw file hash is `4573e2295d8d9721700c177adf39826f9a956c24cee3b524a9ce3b8eb3a6c1a2`. The original manifest names `.runtime/v1-input-claims-20261003` as its snapshot root. The second attempt used a separate archive at `.runtime/v1-input-claims-online-20261003`; the manifest mapping was reused unchanged, and its root is recorded separately in the online snapshot and source-after-install guard records. Do not interpret the original manifest's `snapshot` field as the second archive's root.

Before and after each install attempt, all 1,579 candidate source files matched the same manifest with zero mismatches. The online archive also had zero extra files. These are source-integrity checks; they do not demonstrate a successful install or any runtime/test acceptance.

## Attempt 1: offline install

Command: `npm ci --offline --no-audit --no-fund`
Runtime: Node `v24.20.0`, npm `11.19.0`; pinned Python `3.12.10`, NumPy `2.2.6`, pydantic `2.13.5`; `PYTHONDONTWRITEBYTECODE=1`.
Outcome: exit 1 after `141.0748332` seconds. npm reported `ENOTCACHED` for `https://registry.npmjs.org/yallist` because no cached response was available. Cleanup emitted `EPERM` warnings. No network retry was made. Post-attempt observation recorded no `node_modules` or `dist` in that offline snapshot; cleanup was not attempted.

## Attempt 2: network-assisted install

Command: `npm ci --offline=false --no-audit --no-fund` in a newly extracted candidate snapshot. The environment had `NPM_CONFIG_OFFLINE=true`; the explicit command-line `--offline=false` requested the network-assisted install. No npm script/native install policy was changed. Runtime versions and non-secret environment values are in `online-runtime.json`.

Outcome: exit 1 after `89.571241` seconds. npm attempted to fetch `zustand-5.0.15.tgz` from `registry.npmjs.org`, then reported `ECONNREFUSED 127.0.0.1:9` (the configured proxy endpoint). npm cleanup emitted `EPERM` warnings and left a partial `node_modules` tree. The npm process/session completed; no cleanup or retry was performed. The post-attempt source guard still passed for all 1,579 files.

## Validation boundary

Neither historical attempt reached a completed `npm ci`; therefore `npm run lint`, `npm run test:unit`, and `npm run build` were **not run within these two attempts**. The frozen package scripts are `lint: tsc --noEmit`, `test:unit: tsx --test tests/*.test.ts tests/*.test.tsx`, and `build: vite build && esbuild ...`. The candidate `package.json` has no `packageManager` field, and the repo has no `.npmrc`. No script-policy override was introduced. This evidence establishes two install failures, not candidate acceptance, product behavior, or a successful build. A separate native-environment reproduction is being tracked separately; its results are outside this record and pending at the time of this update.

The original offline failure and subsequent network-assisted failure remain separate outcomes. The partial online `node_modules` is retained as observed ignored output; this report does not treat it as a usable install. The associated SHA-256 inventory covers every copied support file except the inventory file itself.
