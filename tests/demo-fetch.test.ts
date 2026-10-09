import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createDemoFetch, MISSING_KIND, WRITE_REFUSED_KIND } from '../src/demo/demoFetch.ts';
import { canonicalJson, requestKey } from '../src/demo/demoKey.ts';
import { DEMO_MODULES, isDemoModule } from '../src/demo/demoModules.ts';

const ORIGIN = 'https://example.test';
const BASE = '/metalliksa/';

/** Fixture world: a tiny snapshot store served by a fake native fetch that records every URL it is asked for. */
function world(entries: Record<string, { file: string; response: unknown }>, options: { indexOk?: boolean } = {}) {
  const calls: string[] = [];
  const nativeFetch = (async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    calls.push(url);
    if (url === `${BASE}demo-snapshots/index.json`) {
      if (options.indexOk === false) return new Response('nope', { status: 404 });
      const map: Record<string, string> = {};
      for (const [key, value] of Object.entries(entries)) map[key] = value.file;
      return new Response(JSON.stringify({ format: 1, entries: map }), { status: 200 });
    }
    for (const value of Object.values(entries)) {
      if (url === `${BASE}demo-snapshots/${value.file}`) {
        return new Response(JSON.stringify({ request: {}, response: value.response }), { status: 200 });
      }
    }
    return new Response('passthrough', { status: 200 });
  }) as typeof fetch;
  const demoFetch = createDemoFetch({ baseUrl: BASE, nativeFetch, origin: ORIGIN });
  return { demoFetch, calls };
}

const post = (body: unknown) => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

test('a recorded request returns the recorded body', async () => {
  const key = requestKey('POST', '/api/python/lpbf-process-window', '', { power: 285, speed: 960 });
  const { demoFetch } = world({ [key]: { file: 'a1.json', response: { cells: [1, 2, 3], experimentalValidation: false } } });
  const res = await demoFetch('/api/python/lpbf-process-window', post({ speed: 960, power: 285 }));
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { cells: [1, 2, 3], experimentalValidation: false });
});

test('the key does not depend on object key order, and ignores client generated fields', async () => {
  const a = requestKey('POST', '/api/x', '', { b: 1, a: { d: 2, c: 3 }, requestId: 'r1', nested: { nonce: 'n' } });
  const b = requestKey('POST', '/api/x', '', { nested: {}, a: { c: 3, d: 2 }, b: 1, requestId: 'r2' });
  assert.equal(a, b);
  assert.notEqual(a, requestKey('POST', '/api/x', '', { b: 2, a: { c: 3, d: 2 }, nested: {} }));
  assert.equal(canonicalJson({ z: undefined, y: -0, w: Number.NaN }), '{"w":null,"y":0}');
});

test('a request with a different value than recorded misses; there is no nearest neighbour', async () => {
  const key = requestKey('POST', '/api/python/lpbf-process-window', '', { power: 285 });
  const { demoFetch } = world({ [key]: { file: 'a1.json', response: { ok: true } } });
  const res = await demoFetch('/api/python/lpbf-process-window', post({ power: 286 }));
  assert.equal(res.status, 404);
  const body = await res.json();
  assert.equal(body.errorKind, MISSING_KIND);
  assert.match(body.error, /Not available in the static demo\./);
});

test('a missing or unreadable index makes every api call a miss', async () => {
  const { demoFetch } = world({}, { indexOk: false });
  const res = await demoFetch('/api/health');
  assert.equal(res.status, 404);
  assert.equal((await res.json()).errorKind, MISSING_KIND);
});

test('write methods are refused and never reach the network', async () => {
  const { demoFetch, calls } = world({});
  for (const method of ['PUT', 'PATCH', 'DELETE']) {
    const res = await demoFetch('/api/research-registry/records/1', { method });
    assert.equal(res.status, 405);
    assert.equal((await res.json()).errorKind, WRITE_REFUSED_KIND);
  }
  assert.deepEqual(calls, []);
});

test('an unrecorded POST (a write or a new job body) is a miss', async () => {
  const { demoFetch } = world({});
  const res = await demoFetch('/api/lpbf/jobs', post({ jobType: 'build-job', power_W: 100 }));
  assert.equal(res.status, 404);
  assert.equal((await res.json()).errorKind, MISSING_KIND);
});

test('GET with a query string is keyed on the sorted query', async () => {
  const key = requestKey('GET', '/api/lpbf/jobs/job-1', '?b=2&a=1', undefined);
  const { demoFetch } = world({ [key]: { file: 'j.json', response: { status: 'completed' } } });
  const res = await demoFetch('/api/lpbf/jobs/job-1?a=1&b=2');
  assert.deepEqual(await res.json(), { status: 'completed' });
});

test('non api and cross origin requests go to the native fetch', async () => {
  const { demoFetch, calls } = world({});
  await demoFetch('/metalliksa/images/x.png');
  await demoFetch('https://other.test/api/health');
  assert.deepEqual(calls, [`/metalliksa/images/x.png`, 'https://other.test/api/health']);
});

test('the demo module allowlist names the shown modules only', () => {
  assert.ok(DEMO_MODULES.includes('lpbf-optimizer'));
  assert.ok(isDemoModule('lpbf-calibration-scorecard'));
  for (const hidden of ['solidification-microstructure', 'phase-diagram', 'research-hub', 'database', 'experimental-validation']) {
    assert.equal(isDemoModule(hidden), false);
  }
});
