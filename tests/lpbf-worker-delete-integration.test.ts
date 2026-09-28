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

async function killAndWaitForRecordedTestProcess(pid: number) {
  try { process.kill(pid, 'SIGKILL'); }
  catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'ESRCH') throw error;
  }
  const deadline = Date.now() + 5000;
  while (Date.now() < deadline) {
    try { process.kill(pid, 0); }
    catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ESRCH') return;
      throw error;
    }
    await new Promise(resolve => setTimeout(resolve, 25));
  }
  assert.fail(`test-owned process ${pid} did not exit during bounded cleanup`);
}

test('HTTP DELETE waits for the real worker RPC to terminate and reap its execution child', { timeout: 30000 }, async t => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'metalliksa-lpbf-delete-'));
  const priorJobRoot = process.env.METALLIKSA_JOB_ROOT;
  process.env.METALLIKSA_JOB_ROOT = path.join(root, 'jobs');
  const repoPython = path.resolve('python');
  const pidFile = path.join(root, 'execution-child.pid');
  const descendantPidFile = path.join(root, 'execution-grandchild.pid');
  const orphanArtifact = path.join(root, 'orphan-result.json');
  const fixtureScript = path.join(root, 'worker_fixture.py');
  const descendantCode = `from pathlib import Path; import time; time.sleep(15); Path(${JSON.stringify(orphanArtifact)}).write_text('{}')`;
  const childCode = `from pathlib import Path; import os,subprocess,sys,time; Path(${JSON.stringify(pidFile)}).write_text(str(os.getpid())); d=subprocess.Popen([sys.executable,'-c',${JSON.stringify(descendantCode)}]); Path(${JSON.stringify(descendantPidFile)}).write_text(str(d.pid)); time.sleep(120)`;
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
  let childPid: number | undefined;
  let descendantPid: number | undefined;

  try {
    const submittedResponse = await fetch(`${baseUrl}/api/lpbf/jobs`, {
      method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ jobType: 'build-job' }),
    });
    assert.equal(submittedResponse.status, 202);
    const submitted = await submittedResponse.json() as { id: string; status: string };
    assert.ok(submitted.id);

    const deadline = Date.now() + 10000;
    while ((!childPid || !descendantPid) && Date.now() < deadline) {
      try { childPid = Number((await readFile(pidFile, 'utf8')).trim()); }
      catch { await new Promise(resolve => setTimeout(resolve, 50)); }
      try { descendantPid = Number((await readFile(descendantPidFile, 'utf8')).trim()); }
      catch { await new Promise(resolve => setTimeout(resolve, 50)); }
    }
    assert.ok(childPid && descendantPid, 'real worker did not start its execution child and descendant');
    assert.equal(Number.isSafeInteger(childPid) && childPid > 0, true);
    assert.equal(Number.isSafeInteger(descendantPid) && descendantPid > 0, true);
    process.kill(childPid, 0);
    process.kill(descendantPid, 0);

    const cancelledResponse = await fetch(`${baseUrl}/api/lpbf/jobs/${submitted.id}`, { method: 'DELETE' });
    assert.equal(cancelledResponse.status, 200);
    const cancelled = await cancelledResponse.json() as { id: string; status: string };
    assert.equal(cancelled.id, submitted.id);
    assert.equal(cancelled.status, 'cancelled');
    assert.throws(() => process.kill(childPid!, 0), error => (error as NodeJS.ErrnoException).code === 'ESRCH',
      'HTTP cancellation returned before the execution child exited');
    assert.throws(() => process.kill(descendantPid!, 0), error => (error as NodeJS.ErrnoException).code === 'ESRCH',
      'HTTP cancellation returned before the execution descendant exited');
    await assert.rejects(readFile(orphanArtifact), { code: 'ENOENT' });
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
      const cleanup = await Promise.allSettled([descendantPid, childPid]
        .filter((pid): pid is number => Number.isSafeInteger(pid) && pid > 0)
        .map(killAndWaitForRecordedTestProcess));
      const failedCleanup = cleanup.filter(result => result.status === 'rejected');
      assert.equal(failedCleanup.length, 0, failedCleanup.map(result => String(result.reason)).join('; '));
    } finally {
      if (priorJobRoot === undefined) delete process.env.METALLIKSA_JOB_ROOT;
      else process.env.METALLIKSA_JOB_ROOT = priorJobRoot;
      await rm(root, { recursive: true, force: true });
    }
  }
});
