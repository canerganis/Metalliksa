# LPBF full run and source bundle

Spec: LPBF_SHARED_CORE_CONTRACT.md; execution: native sequential TDD.
Owner: 01a0c399-42df-72b0-9872-1010354f2d9a. Baseline b8b1f7f.

## Contract and decisions

Backup to an exclusively created directory: runs.sqlite, run artifact store,
and a nested existing source bundle. Snapshot runs FIRST, then sources. Validate
every exact historical source link against the frozen source database. Include
all source revisions/bytes in that source snapshot (a deliberate superset of
linked revisions); preserve revision numbers, timestamps and unreviewed status.
No live overwrite, installation, HTTP paths or new queue. Completion manifest
last, binding both SQLite metadata and the nested source completion manifest.
Hash integrity is not a signature or scientific qualification. Phase0 OPEN.

Ruling: reuse the source-only bundle unchanged, including all its revisions,
rather than invent a second source serialization. Cost: larger backups. Run and
source stores may be separate. Same LOCAL checkout and self-review per user's
explicit continuation/no-agent instruction; preserve all external dirty paths.
Pre-flight: run snapshot consumes exact source revision/hash; nested source
snapshot preserves every revision, so later current revisions cannot replace links.

## Task 1: full bundle and isolated restore

Own server/lpbfRunBundle.ts and tests/lpbf-run-bundle.test.ts.
- Write tests for independent round trip with old revision/new current revision,
  nested/empty run artifacts and unchanged result strings/hash/timestamps.
- Reject missing/corrupt run/source bytes, wrong/missing source links, metadata
  tampering, sidecars, linked paths and counts. No completion on failure.
- Verify before restore creates destination; reject existing target unchanged.
- Run node --import tsx --test tests/lpbf-run-bundle.test.ts RED then GREEN.
- Run existing run/source/artifact suites and strict TypeScript/lint.
- Exercise actual archived CPU run with isolated source revision and byte store.
- Review owned diff, update archive/STATUS, commit only owned paths.

## Ledger

Startup: CBM generation2026-09-18T15:50:24Z has no tracked coverage for all seven
relevant files; graph lookup zero results. Read exact source/tests instead.
Targeted memory recall returned no matches; supplied checkpoint and current source
are the working evidence. No numerical or experimental claim introduced.

Task1 complete: missing module RED -> six bundle tests GREEN; combined existing
storage/source/run suites33PASS. Strict targetedTS/app lintPASS. Initial sandbox
Node spawnEPERM resolved by scoped test escalation; no approval rejection.
Real prior CPU66files + NIST3files550398609bytes/two source revisions roundtrip
PASS; isolated pilot links revision1, result JSON exact. Original stores unchanged.
Graft bounded refresh7files82nodes280edges in .runtime/graft-run-bundle.
Self-review: full source snapshot is documented, completion follows verification,
run/source timestamps preserved, hashes are not signatures, no live overwrite.
Global diff-check reports preexisting UQ trailing whitespace; owned diff clean.
Ruling: no app build necessary for this internal module (not yet imported into
server); strict compilation and actual Node execution cover its runtime boundary.
No full-suite green claim; historical unrelated EIS/UQ failures remain out of scope.

Next package after acceptance: bounded job-ID archive API/UI with explicit
Node/WSL root mapping and current-input identity; actual browser verification.
Then shared physics seams and remaining LPBF scientific audit. Overall work open.
