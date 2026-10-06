import assert from 'node:assert/strict';
import { test } from 'node:test';
import express from 'express';
import { createLpbfRunsRouter } from '../routes/lpbfRuns';

test('proxy campaign API derives evidence server-side and rejects client measurements', async t => {
  const calls: Array<{ method: string; args: unknown[] }> = [];
  const result = { campaign: null, validation: { status: 'unavailable', comparisonResiduals: null,
    experimentalValidation: false, validationStatus: 'unvalidated' } };
  const campaigns = {
    list: async () => { calls.push({ method: 'list', args: [] }); return []; },
    preview: async (...args: unknown[]) => { calls.push({ method: 'preview', args }); return result; },
    create: async (...args: unknown[]) => { calls.push({ method: 'create', args }); return result; },
  };
  const app = express();
  app.use(createLpbfRunsRouter(undefined, undefined, undefined, campaigns as any));
  const server = app.listen(0, '127.0.0.1');
  t.after(() => new Promise<void>(resolve => server.close(() => resolve())));
  await new Promise<void>(resolve => server.once('listening', resolve));
  const address = server.address();
  assert.ok(address && typeof address !== 'string');
  const endpoint = `http://127.0.0.1:${address.port}/api/lpbf/runs/proxy-campaigns`;
  const runIds = ['a'.repeat(32), 'b'.repeat(32), 'c'.repeat(32)];
  const listed = await fetch(endpoint, { cache: 'no-store' });
  assert.equal(listed.status, 200);
  assert.deepEqual(await listed.json(), []);
  assert.deepEqual(calls.pop(), { method: 'list', args: [] });
  async function post(url: string, body: unknown) {
    const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body) });
    return { status: response.status, body: await response.json() };
  }

  const preview = await post(`${endpoint}/preview`, { runIds, caseNumber: 'Case 1' });
  assert.equal(preview.status, 200);
  assert.deepEqual(calls.pop(), { method: 'preview', args: [runIds, 'Case 1'] });
  for (const injected of [
    { residuals: [0] }, { opticalMeasurements: [{ width_um: 1 }] },
    { validationStatus: 'validated' }, { resultJson: '{}' },
  ]) {
    const response = await post(`${endpoint}/preview`, { runIds, caseNumber: 'Case 1', ...injected });
    assert.equal(response.status, 400);
  }
  assert.equal(calls.length, 0, 'rejected preview bodies never reach the campaign service');

  const create = await post(endpoint, { runIds, caseNumber: 'Case 1', previewSha256: 'd'.repeat(64) });
  assert.equal(create.status, 200);
  assert.deepEqual(calls.pop(), { method: 'create', args: [runIds, 'Case 1', 'd'.repeat(64)] });
  for (const injected of [
    { residuals: [0] }, { opticalMeasurements: [{ width_um: 1 }] },
    { validationStatus: 'validated' }, { resultJson: '{}' },
  ]) {
    const response = await post(endpoint, { runIds, caseNumber: 'Case 1', previewSha256: 'd'.repeat(64), ...injected });
    assert.equal(response.status, 400);
  }
  assert.equal(calls.length, 0, 'rejected create bodies never reach the campaign service');
});
