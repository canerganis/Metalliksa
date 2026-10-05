# LPBF source archive storage

The server storage modules preserve source metadata and original files separately.
They provide an isolated source archive, without migrating the existing application
store or including simulation runs.

## Local application API

The catalog currently exposes only `nist-mds2-2716` from the configured local
`data/benchmark/nist-amb2022-03` archive. No downloads occur. Missing or corrupt
files produce an unavailable response; no substitute data is generated.

| Method and path | Contract |
| --- | --- |
| GET `/api/lpbf/sources` | Catalog IDs/titles, no host filesystem paths |
| GET `/api/lpbf/sources/:datasetId` | Current immutable metadata or null; bytes not checked |
| POST `/api/lpbf/sources/:datasetId/preview` | Body `{}`; validate all source files without storage writes; return document SHA256 and expectedRevision |
| POST `/api/lpbf/sources/:datasetId/import` | Body `{documentSha256, expectedRevision}` from preview; revalidate metadata identity and all files before publication |
| POST `/api/lpbf/sources/:datasetId/verify` | Body `{}`; fresh archived-byte check bound to returned revision/hash/time |

POST requires JSON, a same-origin browser request and at most16KiB. Unknown fields,
client paths/URLs/documents and unknown catalog IDs are rejected. One costly archive
operation runs per service instance; concurrent operations or stale previews return
409. Repository CAS also protects writers from separate processes. Storage/integrity
failures return503 without filesystem paths and preserve existing revisions.
`METALLIKSA_LPBF_SOURCE_ROOT` selects a server-owned directory; default `.lpbf-sources`
is ignored by Git. Catalog/current/preview do not initialize an absent archive.
The local server is not a multi-user authorization system.

The Experimental Comparison stage includes a source archive panel. It displays
source conditions, terms, unknown measurements, original file counts/bytes and
hashes. Preview enables an import bound to the returned hash and expected revision.
Fresh verification shows its exact revision, document hash and UTC check time.
Metadata reads do not imply verified bytes; no action upgrades scientific evidence.
Changing source or leaving the comparison stage discards pending UI replies;
aborting HTTP does not cancel an import already running on the server. Reload
after returning to inspect what was actually stored. Each new attempt clears prior
success, and revision drift during an operation is a visible error.

Simulation/qualification inputs are not changed by importing raw source files.
There is no HTTP backup/restore endpoint yet; programmatic backup/restore below
is available.

UI verification (2026-09-21):5 client regressions, full166unit, lint, strict client/
repository/test TypeScript and build PASS. Actual browser with compiled application
and real source router on127.0.0.1:3196: keyboard preview/import/verify of3IN718
files/550398609bytes; revision1/hash/time visible; injected503 clears old success;
20-second delayed preview discarded after leaving/reopening comparison. Tab order
and visual layout checked. Active specimen280W/940mm/s and empty width/depth fields
preserved. Isolated store `.runtime/lpbf-source-ui-01a0c35a`; no live migration.

API verification:5 focused regressions/full161unitPASS; lint, strict API TypeScript
and production build PASS (existing Vite large-chunk warning). Real production
server3195→local isolated archive imported3IN718 files/550398609bytes; fresh verify
returned revision1/document hash and stale import returned409. Report:
.runtime/phase0-audit/source-api-smoke-01a0c349.json. Test server/IPC stopped.

- `LpbfArtifactStore`: streams files through SHA256/size verification using a 1 MiB
  buffer. Objects live at `objects/<first-two-hash-characters>/<sha256>`. Private
  staging copies are flushed before exclusive hard-link publication. Input files
  are copied, never hard-linked. Existing objects are verified, never replaced.
- `dryRunSourceImport`: validates a detached metadata document and every local
  file without creating revisions or objects. Paths cannot traverse parents,
  junctions/symlinks, Windows devices, or alternate data streams.
- `importSource`: runs that validation again, stores every file, rechecks stored
  objects, then publishes an expected-revision-guarded SQLite revision. A failed
  late operation may leave verified unreferenced objects, never a partial revision.
- `backupSourceBundle`: captures SQLite first, copies all objects referenced by
  every historical revision, then writes the completion manifest. Backup SQLite
  uses DELETE journal mode, independent of WAL/SHM. Only new destinations work.
- `verifySourceBundle` and `restoreSourceBundle`: reject malformed, incomplete,
  corrupt, or sidecar-dependent bundles; restore validates before creating a new
  destination and rechecks copied bytes. Failed destinations are preserved for
  inspection, never recursively removed. Read-only inspection does not initialize
  a database or create artifact directories.

Bundle layout: `metadata.sqlite`, `artifacts/objects/...`, `bundle.json`.
The manifest hashes metadata; metadata hashes every artifact. This is accidental
corruption detection, not publisher authentication or a signature. Application
ownership/permissions must exclude hostile concurrent filesystem writers; portable
Node path checks do not provide an OS-level sandbox against that adversary.
Application immutability means the API never overwrites objects; external file
edits remain possible and are detected by verification. No automatic garbage
collection or legacy migration is implemented.

Metadata reads retain `artifactIntegrity: not-verified`. Successful import reports
`verified-at-import` separately, and dry-run reports `verified-at-dry-run`; neither
is a permanent guarantee about future bytes. Scientific evidence always remains
`unreviewed-source-archive`. Source terms, null units, missing reasons and process
scope survive the round trip unchanged.

## Verified local pilot, 2026-09-21

Node24.20.0; `nist-mds2-2716` IN718 archive: three files,550398609 bytes.
Dry-run, import, independent backup, verification and restore PASS. Portable pilot:
`.runtime/lpbf-source-archive-portable-01a0c349/report.json`; reproducible local driver:
`.runtime/lpbf-source-archive-pilot-01a0c349.ts` (pass a new destination as argv2).
Document SHA256 `cbf30982263b00f485f5380de0b0bf2293d73807a14159e14a4aaa470400be75`.
Final backup contains no SQLite sidecars. Full unit156PASS; strict server/new-test
TypeScript PASS. Regressions cover corruption, concurrent duplicate publication,
multi-chunk binary copy, junction escapes, import failure, immutable history,
independent restore, existing-destination refusal and SQLite sidecars.

HDF5 metadata was subsequently inspected in b0bd0bd. See
[the review](archive/2026-09-21/NIST_IN718_HDF5_REVIEW_2026-09-21.md) for digital-level units, source
conditions, thresholding and the malformed stored calibration expression.
Raw camera signal remains uncalibrated; thermal/powder-bed validation and phase
acceptance remain open. Updated metadata can be previewed/imported as a new source
revision; historical revisions retain their original review scope.
