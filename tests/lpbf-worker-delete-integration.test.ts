import assert from 'node:assert/strict';
import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import { once } from 'node:events';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import express from 'express';
import { lpbfSimulationRouter } from '../routes/lpbfSimulation';
import { lpbfWorker, LpbfWorkerBridge } from '../server/lpbfWorkerBridge';
import { getHostPython } from '../server/pythonRuntime';

const python = getHostPython();

test('HTTP DELETE waits for the real worker RPC to terminate and reap its execution child', { timeout: 30000 }, async t => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'metalliksa-lpbf-delete-'));
  const priorJobRoot = process.env.METALLIKSA_JOB_ROOT;
  process.env.METALLIKSA_JOB_ROOT = path.join(root, 'jobs');
  const repoPython = path.resolve('python');
  const pidFile = path.join(root, 'execution-child.pid');
  const fixtureScript = path.join(root, 'worker_fixture.py');
  const childCode = `from pathlib import Path; import os,time; Path(${JSON.stringify(pidFile)}).write_text(str(os.getpid())); time.sleep(120)`;
  await writeFile(fixtureScript, [
    'import sys',
    `sys.path.insert(0, ${JSON.stringify(repoPython)})`,
    'import lpbf_worker',
    'from pathlib import Path',
    'original_spawn = lpbf_worker._spawn_execution_child',
    'def spawn_test_child(command, log):',
    `    return original_spawn([sys.executable, '-c', ${JSON.stringify(childCode)}], log)`,
    'lpbf_worker._spawn_execution_child = spawn_test_child',
    'lpbf_worker.main()',
  ].join('\n'));

  const workerChildren: ChildProcessWithoutNullStreams[] = [];
  const bridge = new LpbfWorkerBridge({
    startupTimeoutMs: 15000,
    requestTimeoutMs: 15000,
    command: () => ({ cmd: python.cmd, args: [...python.prefix, '-u', fixtureScript] }),
    spawn: command => {
      const child = spawn(command.cmd, command.args, { stdio: 'pipe', windowsHide: true });
      workerChildren.push(child);
      return child;
    },
  });
  t.mock.method(lpbfWorker, 'request', bridge.request.bind(bridge));

  const app = express();
  app.use(express.json());
  app.use(lpbfSimulationRouter);
  const server = app.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const address = server.address() as { port: number };
  const baseUrl = `http://127.0.0.1:${address.port}`;

  try {
    const submittedResponse = await fetch(`${baseUrl}/api/lpbf/jobs`, {
      method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ jobType: 'build-job' }),
    });
    assert.equal(submittedResponse.status, 202);
    const submitted = await submittedResponse.json() as { id: string; status: string };
    assert.ok(submitted.id);

    const deadline = Date.now() + 10000;
    let childPid: number | undefined;
    while (!childPid && Date.now() < deadline) {
      try { childPid = Number((await readFile(pidFile, 'utf8')).trim()); }
      catch { await new Promise(resolve => setTimeout(resolve, 50)); }
    }
    assert.ok(childPid, 'real worker did not start its execution child');
    assert.equal(Number.isSafeInteger(childPid), true);
    process.kill(childPid, 0);

    const cancelledResponse = await fetch(`${baseUrl}/api/lpbf/jobs/${submitted.id}`, { method: 'DELETE' });
    assert.equal(cancelledResponse.status, 200);
    const cancelled = await cancelledResponse.json() as { id: string; status: string };
    assert.equal(cancelled.id, submitted.id);
    assert.equal(cancelled.status, 'cancelled');
    assert.throws(() => process.kill(childPid!, 0), error => (error as NodeJS.ErrnoException).code === 'ESRCH',
      'HTTP cancellation returned before the execution child exited');
  } finally {
    server.closeAllConnections();
    await new Promise<void>(resolve => server.close(() => resolve()));
    bridge.close();
    await Promise.all(workerChildren.map(async child => {
      if (child.exitCode !== null || child.signalCode !== null || !child.pid) return;
      const closed = once(child, 'close');
      child.kill();
      await closed;
    }));
    if (priorJobRoot === undefined) delete process.env.METALLIKSA_JOB_ROOT;
    else process.env.METALLIKSA_JOB_ROOT = priorJobRoot;
    await rm(root, { recursive: true, force: true });
  }
});
