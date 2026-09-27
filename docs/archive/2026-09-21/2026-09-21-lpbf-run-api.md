# LPBF run archive API

Spec: LPBF_SHARED_CORE_CONTRACT.md and LPBF_RUN_ARCHIVE.md.
Owner01a0c399; baseline d7dc7e4; native sequential/self-review, no agents.

## Contract

One existing worker queue; new INTERNAL archive-capture RPC returns completed
capture plus server-only absolute worker root/platform. Bridge maps same-host
paths directly; Windows maps Linux /mnt/<drive>/ roots to that Windows drive.
Linux-native WSL paths are explicitly unavailable to Windows archive capture
in this first adapter (configure a shared drive job root); never guess a path.
Full byte/result checks protect mapping consistency. No path or raw capture in
HTTP request, and no root in response. Preserve existing public artifact allowlist.

GET /api/lpbf/runs lists bounded summaries; GET /:jobId retrieves immutable record.
POST /:jobId/preview takes exact sources[]; POST /:jobId/import takes sources[]
and expectedDocumentSha256 from preview. Capture and all run/source bytes checked
fresh; changed preview conflicts. Existing run ID never overwritten. POST verify
checks archived run bytes and exact linked source revisions/bytes with timestamp.
Missing source archive allowed only with no links; no fabricated revision.
Single in-flight archive operation rejects overlap, not a second compute queue.
16KiB strict JSON/same-origin, safe generic backend errors, no client paths.

## Tasks

1. Pure path adapter + bridge/internal worker RPC tests RED/GREEN. Existing capture
   and python-runtime tests preserved. Only trusted server sees root.
2. Isolated HTTP/service tests: preview no run storage, immutable import/list/get,
   stale hash/corrupt bytes/missing source/invalid fields/overlap reject. Tests
   use real repositories/bytes and an injected capture boundary, no fake science.
3. Integrate router before large-body parser; ignore default .lpbf-runs. Run
   combined archive/API, strictTS/lint/build and actual worker HTTP smoke.
4. Commit only owned paths and record exact evidence/next UI package.

## Ledger

Preflight: existing run importer validates source identity, API additionally
checks source bytes. Worker supplies filesystem root only over internal RPC.
CBM18Sep stale/changed in all relevant files; direct reads used. Root mapping
must follow worker-reported platform, not assume Windows/WSL environment parity.
Ruling: Linux-native WSL roots on Windows fail explicitly instead of introducing
UNC mounts or accepting a client mapping. Shared /mnt drive default works.
No numerical equations changed. Phase0 OPEN; UI and shared physics follow.
