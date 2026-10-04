import assert from 'node:assert/strict';
import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import { once } from 'node:events';
import { access, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import express from 'express';
import { createLpbfRunsRouter } from '../routes/lpbfRuns';
import { lpbfSimulationRouter } from '../routes/lpbfSimulation';
import { LpbfRunArchiveService } from '../server/lpbfRunArchiveService';
import { LpbfRunBundleService } from '../server/lpbfRunBundleService';
import { LpbfSourceArchiveService } from '../server/lpbfSourceArchiveService';
import { nistOpticalTable4CatalogEntry } from '../server/lpbfSourceCatalog';
import { lpbfWorker, LpbfWorkerBridge } from '../server/lpbfWorkerBridge';
import { getHostPython } from '../server/pythonRuntime';

// Crash-recovery acceptance: the real python/lpbf_worker.py is SIGKILLed while a job is running and the
// bridge restarts it against the same job root (persisted sqlite queue + job directories). The solver child
// is replaced by a stub (same technique as lpbf-worker-delete-integration.test.ts) that leaves partial,
// unverified output files behind and then blocks, so the "running with partial output" state is deterministic.
const python = getHostPython();
const exists = (file: string) => access(file).then(() => true, () => false);
const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));
const alive = (pid: number) => { try { process.kill(pid, 0); return true; } catch { return false; } };

test('a worker SIGKILLed mid-job restarts with the job failed, partial files unpresented, and archive refusing it', { timeout: 120000 }, async t => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'metalliksa-lpbf-crash-'));
  const priorJobRoot = process.env.METALLIKSA_JOB_ROOT;
  const jobRoot = path.join(root, 'jobs');
  process.env.METALLIKSA_JOB_ROOT = jobRoot;
  const repoPython = path.resolve('python');
  const fixtureScript = path.join(root, 'worker_fixture.py');
  // argv[1] is the job folder. Two files that the worker lists as partial candidates, a truncated result.tmp
  // (what a crash during result publication leaves), then a pid marker and a long sleep.
  const childCode = [
    'import os,sys,time',
    'from pathlib import Path',
    'f=Path(sys.argv[1])',
    "(f/'field-frame-000.bin').write_bytes(b'partial-unverified')",
    "(f/'peak-field.npz').write_bytes(b'partial-unverified-2')",
    "(f/'result.tmp').write_text('{\"truncated\":')",
    "(f/'stub.pid').write_text(str(os.getpid()))",
    'time.sleep(120)',
  ].join('\n');
  await writeFile(fixtureScript, [
    'import sys',
    `sys.path.insert(0, ${JSON.stringify(repoPython)})`,
    'import lpbf_worker',
    'original_spawn = lpbf_worker._spawn_execution_child',
    'def spawn_test_child(command, log):',
    `    return original_spawn([sys.executable, '-c', ${JSON.stringify(childCode)}, command[-1]], log)`,
    'lpbf_worker._spawn_execution_child = spawn_test_child',
    'lpbf_worker.main()',
  ].join('\n'));

  const workerChildren: ChildProcessWithoutNullStreams[] = [];
  const bridge = new LpbfWorkerBridge({
    startupTimeoutMs: 20000, requestTimeoutMs: 20000,
    command: () => ({ cmd: python.cmd, args: [...python.prefix, '-u', fixtureScript] }),
    spawn: command => {
      const child = spawn(command.cmd, command.args, { stdio: 'pipe', windowsHide: true });
      workerChildren.push(child);
      return child;
    },
  });
  t.mock.method(lpbfWorker, 'request', bridge.request.bind(bridge));

  const sourceRoot = path.join(root, 'sources');
  const catalogEntry = nistOpticalTable4CatalogEntry();
  const sources = new LpbfSourceArchiveService(sourceRoot, [catalogEntry]);
  const preview = await sources.preview(catalogEntry.datasetId);
  const imported = await sources.import(catalogEntry.datasetId, preview.expectedRevision, preview.documentSha256);
  const links = [{ datasetId: catalogEntry.datasetId, revision: imported.revision.revision }];
  const runRoot = path.join(root, 'runs');

  const app = express();
  app.use(express.json());
  app.use(lpbfSimulationRouter);
  app.use(createLpbfRunsRouter(new LpbfRunArchiveService(runRoot, sourceRoot),
    new LpbfRunBundleService(runRoot, sourceRoot, path.join(root, 'bundles'))));
  const server = app.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const baseUrl = `http://127.0.0.1:${(server.address() as { port: number }).port}`;
  const json = async (method: string, url: string, body?: unknown) => {
    const response = await fetch(`${baseUrl}${url}`, { method, headers: { 'content-type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
    const text = await response.text();
    assert.ok(!text.includes(root), `no local path in ${text}`);
    let parsed: any; try { parsed = JSON.parse(text); } catch { parsed = text; }
    return { status: response.status, body: parsed };
  };
  const stubPids: number[] = [];

  try {
    // 1. Submit; wait until the stub solver child is running and has left partial output behind.
    const submitted = await json('POST', '/api/lpbf/jobs', { jobType: 'build-job' });
    assert.equal(submitted.status, 202, JSON.stringify(submitted.body));
    const jobId: string = submitted.body.id;
    const folder = path.join(jobRoot, jobId);
    const deadline = Date.now() + 30000;
    while (!(await exists(path.join(folder, 'stub.pid'))) && Date.now() < deadline) await sleep(50);
    stubPids.push(Number((await readFile(path.join(folder, 'stub.pid'), 'utf8')).trim()));
    const before = await json('GET', `/api/lpbf/jobs/${jobId}`);
    assert.equal(before.body.status, 'running', JSON.stringify(before.body));
    assert.equal(before.body.result, undefined);

    // 2. Crash: SIGKILL the real worker process (no graceful shutdown, no status write).
    assert.equal(workerChildren.length, 1);
    const crashed = workerChildren[0];
    const exited = once(crashed, 'exit');
    crashed.kill('SIGKILL');
    await exited;
    assert.ok(crashed.signalCode === 'SIGKILL' || crashed.exitCode !== 0, 'worker did not exit cleanly');
    // Nothing could publish a result.
    assert.equal(await exists(path.join(folder, 'result.json')), false);

    // 3. Recovery: the next request restarts the worker on the same job root (retry while it starts).
    let after: { status: number; body: any } | undefined;
    const recoverBy = Date.now() + 40000;
    while (Date.now() < recoverBy) {
      after = await json('GET', `/api/lpbf/jobs/${jobId}`);
      if (after.status === 200) break;
      assert.equal(after.status, 503, JSON.stringify(after.body)); // worker transport/startup, never a result
      await sleep(250);
    }
    assert.equal(after?.status, 200, 'worker restarted and answered');
    assert.equal(workerChildren.length >= 2, true, 'bridge started a new worker process');

    // 4. The job is failed (never completed); no result is attached; partial files are only inventoried as unverified.
    const job = after!.body;
    assert.equal(job.status, 'failed');
    assert.equal(job.error, 'Worker restarted during execution');
    assert.equal('result' in job, false, 'no result for a crashed job');
    assert.ok(job.progress < 1, `progress ${job.progress}`);
    assert.deepEqual(job.partialArtifacts, { status: 'retained-unverified', fileCount: 2, totalBytes: 'partial-unverified'.length + 'partial-unverified-2'.length });
    for (const name of ['field-frame-000.bin', 'temperature-slice.svg', 'result.tmp', 'result.json', 'stub.pid']) {
      const artifact = await json('GET', `/api/lpbf/jobs/${jobId}/artifacts/${name}`);
      assert.equal(artifact.status, 400, `${name}: ${JSON.stringify(artifact.body)}`);
      assert.equal(artifact.body.error, 'Artifact unavailable');
    }

    // 5. Archive refuses the job, imports nothing and the run history stays empty.
    for (const action of ['/preview', '/import']) {
      const refused = await json('POST', `/api/lpbf/runs${action}`, { jobId, sources: links });
      assert.equal(refused.status, 409, `${action}: ${JSON.stringify(refused.body)}`);
      assert.equal(refused.body.error, 'Only completed jobs can be archived.');
    }
    assert.deepEqual((await json('GET', '/api/lpbf/runs')).body, []);

    // 6. The failed record is not reused as a cached result: the same input starts a new, non-completed job.
    const again = await json('POST', '/api/lpbf/jobs', { jobType: 'build-job' });
    assert.equal(again.status, 202, JSON.stringify(again.body));
    assert.notEqual(again.body.id, jobId);
    assert.notEqual(again.body.status, 'completed');
    assert.notEqual(again.body.cacheHit, true);
    const cancelled = await json('DELETE', `/api/lpbf/jobs/${again.body.id}`);
    assert.equal(cancelled.status, 200);
    assert.equal((await json('GET', `/api/lpbf/jobs/${jobId}`)).body.status, 'failed', 'the crashed job stays failed');
  } finally {
    server.closeAllConnections();
    await new Promise<void>(resolve => server.close(() => resolve()));
    bridge.close();
    try {
      await Promise.all(workerChildren.map(async child => {
        if (child.exitCode !== null || child.signalCode !== null || !child.pid) return;
        const closed = once(child, 'close');
        child.kill();
        await closed;
      }));
      // The stub solver child may outlive a SIGKILLed worker on platforms without a Job Object; never leak it.
      for (const pid of stubPids) { if (alive(pid)) { try { process.kill(pid, 'SIGKILL'); } catch { /* already gone */ } } }
      await sleep(200);
    } finally {
      if (priorJobRoot === undefined) delete process.env.METALLIKSA_JOB_ROOT;
      else process.env.METALLIKSA_JOB_ROOT = priorJobRoot;
      await rm(root, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 });
    }
  }
});
