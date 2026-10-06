import assert from 'node:assert/strict';
import { mkdtempSync } from 'node:fs';
import { once } from 'node:events';
import path from 'node:path';
import { test } from 'node:test';
import express from 'express';
import type { Server } from 'node:http';
import { createLpbfRunsRouter } from '../routes/lpbfRuns';
import { LpbfRunArchiveService } from '../server/lpbfRunArchiveService';
import { LpbfRunBundleService } from '../server/lpbfRunBundleService';
import { LpbfSourceArchiveService } from '../server/lpbfSourceArchiveService';
import { nistOpticalTable4CatalogEntry } from '../server/lpbfSourceCatalog';
import { lpbfWorker } from '../server/lpbfWorkerBridge';
import { isolateWorkerJobRoot, removeWorkerTestRoot, runCleanupSteps, stopRealWorker, waitForRealWorker } from './support/realLpbfWorker';

// Phase 2 D9: archiving a cancelled job through the real worker and the real route used to answer
// 503 "Run archive unavailable or integrity check failed." It is a client error.

test('archiving a cancelled, unknown or malformed job returns a specific 4xx without paths', async t => {
  const root = mkdtempSync(path.join(process.cwd(), '.tmp-lpbf-archive-incomplete-'));
  const restoreJobRoot = isolateWorkerJobRoot(path.join(root, 'jobs'));
  let server: Server | undefined;
  // Every step runs even if an earlier one fails, so a stuck worker is a loud failure, not a leaked env or root.
  t.after(() => runCleanupSteps([
    stopRealWorker,
    restoreJobRoot,
    () => server && new Promise<void>(resolve => server!.close(() => resolve())),
    () => removeWorkerTestRoot(root),
  ]));

  const sourceRoot = path.join(root, 'sources');
  const catalogEntry = nistOpticalTable4CatalogEntry();
  const sources = new LpbfSourceArchiveService(sourceRoot, [catalogEntry]);
  const preview = await sources.preview(catalogEntry.datasetId);
  const imported = await sources.import(catalogEntry.datasetId, preview.expectedRevision, preview.documentSha256);
  const links = [{ datasetId: catalogEntry.datasetId, revision: imported.revision.revision }];

  const runRoot = path.join(root, 'runs');
  const app = express();
  app.use(createLpbfRunsRouter(new LpbfRunArchiveService(runRoot, sourceRoot),
    new LpbfRunBundleService(runRoot, sourceRoot, path.join(root, 'bundles'))));
  server = app.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const address = server.address();
  assert.ok(address && typeof address !== 'string');
  const base = `http://127.0.0.1:${address.port}/api/lpbf/runs`;
  const post = async (suffix: string, body: unknown) => {
    const response = await fetch(`${base}${suffix}`, { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const text = await response.text();
    assert.ok(!text.includes(root) && !/[A-Za-z]:\\|\/jobs\//.test(text), `no local path in ${text}`);
    return { status: response.status, body: JSON.parse(text) as { error?: string } };
  };

  await waitForRealWorker(Date.now() + 90_000);
  // Submit and cancel are two separate RPCs and the worker executes concurrently, so a job can in principle finish first (cancel keeps a
  // completed status). The 3 mm powder-layer track (the validator maximum) makes that very unlikely; to remove the remaining timing dependence
  // we retry with a distinct input (no cache hit) until a cancel actually lands, and fail loudly if it never does.
  let submission: { id: string } | undefined;
  for (let attempt = 0; attempt < 5 && !submission; attempt += 1) {
    const candidate = await lpbfWorker.request('submit', {
      mode: 'standard', backend: 'reference', material: 'Inconel 718', power_W: 60 + attempt,
      speed_mm_s: 1200, beamDiameter_um: 80, preheat_C: 200, layer_um: 40,
      mesh_um: 20, maxDt_s: 0.000001, trackLength_um: 3000, tracks: 1, layers: 1,
      surfaceMode: 'powder-layer', cooling_s: 0.0005, dwell_s: 0.0002,
    }) as { id: string };
    const outcome = await lpbfWorker.request('cancel', candidate.id) as { status: string };
    if (outcome.status === 'cancelled') submission = candidate;
  }
  assert.ok(submission, 'a job was cancelled before completing within 5 attempts');

  for (const action of ['/preview', '/import']) {
    const rejected = await post(action, { jobId: submission.id, sources: links });
    assert.equal(rejected.status, 409, `${action}: ${JSON.stringify(rejected.body)}`);
    assert.equal(rejected.body.error, 'Only completed jobs can be archived.');
    const unknown = await post(action, { jobId: 'f'.repeat(32), sources: links });
    assert.equal(unknown.status, 404, JSON.stringify(unknown.body));
    assert.equal(unknown.body.error, 'Job not found.');
    const malformed = await post(action, { jobId: 'not-a-job', sources: links });
    assert.equal(malformed.status, 400, JSON.stringify(malformed.body));
    assert.equal(malformed.body.error, 'Invalid job id.');
  }
  const list = await (await fetch(base)).json() as unknown[];
  assert.deepEqual(list, [], 'nothing was archived');
});
