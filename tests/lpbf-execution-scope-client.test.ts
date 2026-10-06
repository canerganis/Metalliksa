import assert from 'node:assert/strict';
import test from 'node:test';
import { simulationApi } from '../src/services/lpbfSimulationService';

test('simulation client keeps ordinary caching by default and exposes explicit repeat scope', async () => {
  const original = globalThis.fetch;
  const urls: string[] = [];
  const payload = { mode: 'standard', alloyId: 'in718', power_W: 200 };
  globalThis.fetch = async (url, init) => {
    urls.push(String(url));
    assert.equal(init?.method, 'POST');
    assert.deepEqual(JSON.parse(String(init?.body)), payload);
    return new Response(JSON.stringify({ id: 'a'.repeat(32), status: 'queued', progress: 0,
      log: '', error: null, cacheHit: false }), { status: 202, headers: { 'Content-Type': 'application/json' } });
  };
  try {
    await simulationApi.submit(payload as never);
    await simulationApi.submit(payload as never, { executionScope: 'repeat' });
    assert.deepEqual(urls, ['/api/lpbf/jobs', '/api/lpbf/jobs/repeat']);
  } finally { globalThis.fetch = original; }
});
