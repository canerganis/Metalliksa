import assert from 'node:assert/strict';
import test from 'node:test';
import express from 'express';
import { lpbfSimulationRouter } from '../routes/lpbfSimulation';
import { lpbfWorker } from '../server/lpbfWorkerBridge';

test('repeat endpoint opts into a fresh execution without modifying submitted physics input', async () => {
  const app = express(); app.use(express.json()); app.use(lpbfSimulationRouter);
  const server = app.listen(0, '127.0.0.1');
  await new Promise<void>(resolve => server.once('listening', resolve));
  const original = lpbfWorker.request;
  const payload = { mode: 'standard', alloyId: 'in718', power_W: 200, velocity_mm_s: 800 };
  const address = server.address() as { port: number };
  try {
    lpbfWorker.request = async (method, input) => {
      assert.equal(method, 'submit-repeat');
      assert.deepEqual(input, payload);
      return { id: 'a'.repeat(32), status: 'queued', cacheHit: false };
    };
    const accepted = await fetch(`http://127.0.0.1:${address.port}/api/lpbf/jobs/repeat`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    });
    assert.equal(accepted.status, 202);
    assert.equal((await accepted.json()).cacheHit, false);
  } finally {
    lpbfWorker.request = original;
    await new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
  }
});
