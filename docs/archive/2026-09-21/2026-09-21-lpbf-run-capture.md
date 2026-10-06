# LPBF Run Capture Implementation Plan

> For agentic workers: use superpowers:executing-plans, sequential native execution.

**Goal:** Persist immutable completed thermal runs with complete output bytes and
exact source revision links in an isolated repository before HTTP/UI integration.
**Architecture:** Existing Python Queue verifies results and exports a bounded
capture. Node preserves Python-encoded snapshots, verifies hashes and source
identities, reuses LpbfArtifactStore, then atomically publishes immutable metadata.
**Tech Stack:** Existing Python, TypeScript, Node24 SQLite; no dependencies.
**Spec:** docs/LPBF_SHARED_CORE_CONTRACT.md.

## Constraints and execution ledger

Phase0 OPEN. No science upgrade, live migration, push or second queue. Legacy
absence explicitly legacy-unbound; malformed present contracts fail. Only trusted
server code supplies filesystem roots; no HTTP endpoint in this first package.
Ruling: continue expressly authorized native LOCAL checkout, no agents. Plan
review is self-review; user already authorized continued implementation.
Preflight: capture uses Python compact sorted JSON strings; Node hashes those
exact bytes, never reserializes numbers to assert Python contract equality.

## Review focus

Execution ledger: Task1 capture module absent RED → Python5PASS including actual
Queue execution; core identity8PASS. Task2 repository absent RED → Node6PASS,
then self-review result-file drift regression RED (missing rejection) →7PASS.
Final affected storage21PASS/strictTS PASS. Actual40W worker66files322352bytes,
import and metadata restore PASS; old numerical peak2119.81011401591 unchanged.
Generic artifact store now permits valid zero-byte objects, with empty-hash
verification; source metadata still requires positive source payload sizes.
Final review: self-review, native no-agents instruction preserved. No HTTP/UI
claim. Windows temp/spawn restrictions required scoped test/build escalation.
No automatic approval rejection. Ruling: retain all external changes after user
confirmed the other task stopped; do not adopt or stage unrelated edits.

- Missing, extra, duplicate, empty and nested output files: full manifest or fail.
- Source revised after preview: exact historical revision remains bound.
- Changed files after preview: import rechecks and creates no completed record.
- Mutated result/material/input: hashes and detached snapshots must disagree.
- Legacy runtime unavailable: preserve null, never describe capture host as executor.

### Task 1: Python completed-job capture

Files: python/lpbf_run_capture.py, python/test_lpbf_run_capture.py,
python/lpbf_worker.py.
Interface: capture_run(folder, job_id) returns schemaVersion/jobId/resultJson/
inputJson/materialJson/contractStatus; all output refs remain inside resultJson.
- [ ] Write real screening-result tests: byte drift, nested output, omitted output,
  unsafe/link paths and changed contract fail; legacy remains explicit.
- [ ] Run `.runtime/lpbf-win-py312/Scripts/python.exe -B python/test_lpbf_run_capture.py` RED.
- [ ] Implement capture using enforce_thermal_balances and streamed SHA256;
  `json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)`.
- [ ] Add Queue.capture(id), completed-only; RPC accepts job ID only. New executor
  records sys.executable/platform/Python/NumPy versions in provenance; older
  results retain missing runtime. Run capture/core/queue regressions GREEN.

### Task 2: Immutable repository and import

Files: server/lpbfRunRepository.ts, server/lpbfRunImport.ts,
tests/lpbf-run-repository.test.ts.
Interface: LpbfRunRepository(filename).save(document), get(runId), allRuns(),
backupMetadata(newDirectory); dryRunRunImport(capture,links,sources,root),
importRun(repository,store,capture,links,sources,root).
- [ ] Test isolated save/reopen/conflict/corruption/metadata restore; exact old
  source revision; all-byte failure before publication; immutable caller copies.
- [ ] Run `node --import tsx --test tests/lpbf-run-repository.test.ts` RED.
- [ ] Validate bounded JSON, parseSimulationJob, exact snapshot equality and
  contract SHA strings, source identities, unique safe full manifest paths.
  Publish only after `store.putFile` and `store.verify` succeed for every ref.
  SQLite immutable primary-key insert rejects repeats; reads revalidate hash/schema.
- [ ] Run focused storage/capture tests, strict TS/lint/build and real worker
  capture→Node import/reopen. Check diff and commit owned paths.

### Following package

Full source+run bundle restore, then bounded job-ID API and history UI with actual
browser checks. These are separate acceptance packages, not implied by metadata
backup or by this plan completing. Continue the overall goal after this package.
