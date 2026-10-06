import assert from 'node:assert/strict';
import test from 'node:test';
import express from 'express';
import { lpbfSimulationRouter } from '../routes/lpbfSimulation';
import { lpbfWorker } from '../server/lpbfWorkerBridge';

test('existing job API forwards explicit CUDA pilot selection and exposes unavailable device', async () => {
  const app = express(); app.use(express.json()); app.use(lpbfSimulationRouter);
  const server = app.listen(0, '127.0.0.1');
  await new Promise<void>(resolve => server.once('listening', resolve));
  const original = lpbfWorker.request;
  const payload = { jobType: 'gpu-thermal-pilot', backend: 'cuda:0',
    mode: 'standard', material: 'Inconel 718', tracks: 1, layers: 1 };
  const address = server.address() as { port: number };
  const url = `http://127.0.0.1:${address.port}/api/lpbf/jobs`;
  try {
    lpbfWorker.request = async (method, input) => {
      assert.equal(method, 'submit'); assert.deepEqual(input, payload);
      return { id: 'a'.repeat(32), status: 'queued',
        requestSummary: { jobType: payload.jobType, backend: payload.backend } };
    };
    const accepted = await fetch(url, { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    assert.equal(accepted.status, 202);
    assert.equal((await accepted.json()).requestSummary.backend, 'cuda:0');
    lpbfWorker.request = async (method, input) => {
      assert.equal(method, 'submit'); assert.deepEqual(input, payload);
      throw new Error('CUDA device cuda:0 unavailable; no CPU fallback');
    };
    const unavailable = await fetch(url, { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    assert.equal(unavailable.status, 400);
    assert.deepEqual(await unavailable.json(),
      { error: 'CUDA device cuda:0 unavailable; no CPU fallback' });
  } finally {
    lpbfWorker.request = original;
    await new Promise<void>((resolve, reject) =>
      server.close(error => error ? reject(error) : resolve()));
  }
});
