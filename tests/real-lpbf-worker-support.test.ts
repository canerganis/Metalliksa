import assert from 'node:assert/strict';
import { test } from 'node:test';
import { LpbfWorkerUnavailableError, lpbfWorker } from '../server/lpbfWorkerBridge';
import { runCleanupSteps, waitForRealWorker } from './support/realLpbfWorker';

// Test-support contracts for the real-worker tests; the bridge is mocked, no worker is started.

test('warm-up retries STARTING and caller-deadline errors, but nothing else', async t => {
  const replies: unknown[] = [
    new LpbfWorkerUnavailableError('LPBF worker is still starting. Retry shortly.', 'LPBF_WORKER_STARTING'),
    new LpbfWorkerUnavailableError('LPBF worker request deadline exceeded'),
    { ready: true },
  ];
  t.mock.method(lpbfWorker, 'request', async () => {
    const reply = replies.shift();
    if (reply instanceof Error) throw reply;
    return reply;
  });
  assert.deepEqual(await waitForRealWorker(Date.now() + 10_000), { ready: true });

  const exited = new LpbfWorkerUnavailableError('LPBF worker exited (1): boom');
  t.mock.method(lpbfWorker, 'request', async () => { throw exited; });
  await assert.rejects(waitForRealWorker(Date.now() + 10_000), error => error === exited);
});

test('a warm-up attempt is capped at the remaining warm-up budget', async t => {
  t.mock.method(lpbfWorker, 'request', () => new Promise(() => {}));
  const started = Date.now();
  await assert.rejects(waitForRealWorker(Date.now() + 100), /not ready within the warm-up deadline/);
  assert.ok(Date.now() - started < 5000, 'a hanging request does not extend the warm-up past its deadline');
});

test('cleanup runs every step after a failure and then fails loudly', async () => {
  const ran: string[] = [];
  const stuck = new Error('LPBF worker did not exit within 10 s of close()');
  await assert.rejects(runCleanupSteps([
    () => { ran.push('stop'); throw stuck; },
    () => { ran.push('env'); },
    async () => { ran.push('server'); },
    async () => { ran.push('root'); },
  ]), error => error === stuck);
  assert.deepEqual(ran, ['stop', 'env', 'server', 'root']);

  await assert.rejects(runCleanupSteps([() => { throw new Error('a'); }, () => { throw new Error('b'); }]),
    error => error instanceof AggregateError && error.errors.length === 2);
  await runCleanupSteps([() => undefined]);
});
