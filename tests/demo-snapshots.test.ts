import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { createDemoFetch } from '../src/demo/demoFetch.ts';
import { DEFAULT_EXCLUDED_FIELDS, requestKey } from '../src/demo/demoKey.ts';
import { assertEvidence, normaliseResponse, sortKeys, BUDGET } from '../scripts/demo/generate-demo-snapshots.mjs';

const root = path.resolve(import.meta.dirname, '..');
const snapDir = path.join(root, 'demo', 'snapshots');
const readJson = (p: string) => JSON.parse(readFileSync(p, 'utf8'));
const spec = readJson(path.join(root, 'scripts', 'demo', 'demo-requests.json')) as {
  excludedFields: string[];
  requests: { method: string; path: string; body?: unknown; fixture?: unknown; source: string }[];
};

// Shared key fixture: ten requests and the keys both the generator and the browser must produce.
const KEY_FIXTURE: { args: [string, string, string, unknown]; key: string }[] = [
  { args: ['post', '/api/x', '', { b: 1, a: 2 }], key: 'POST /api/x {"a":2,"b":1}' },
  { args: ['POST', '/api/x', '', { a: 2, b: 1 }], key: 'POST /api/x {"a":2,"b":1}' },
  { args: ['POST', '/api/x', '', { a: 2, b: 1, requestId: 'r1' }], key: 'POST /api/x {"a":2,"b":1}' },
  { args: ['POST', '/api/x', '', { a: { nonce: 'n', z: 1 }, clientTimestamp: 5 }], key: 'POST /api/x {"a":{"z":1}}' },
  { args: ['GET', '/api/health', '', undefined], key: 'GET /api/health' },
  { args: ['GET', '/api/health', '', null], key: 'GET /api/health' },
  { args: ['GET', '/api/q', '?b=2&a=1', undefined], key: 'GET /api/q?a=1&b=2' },
  { args: ['POST', '/api/x', '', { list: [{ y: 1, x: 2 }, undefined], n: -0 }], key: 'POST /api/x {"list":[{"x":2,"y":1},null],"n":0}' },
  { args: ['POST', '/api/x', '', { v: 285, s: 960.5, idempotencyKey: 'k', jobId: 'j', runId: 'r' }], key: 'POST /api/x {"s":960.5,"v":285}' },
  { args: ['POST', '/api/x', '', { nan: Number.NaN, t: true, s: 'text' }], key: 'POST /api/x {"nan":null,"s":"text","t":true}' },
];

test('key fixture: ten requests give the expected keys', () => {
  for (const { args, key } of KEY_FIXTURE) assert.equal(requestKey(...args), key);
});

test('two requests that differ only in the excluded fields give the same key', () => {
  const base = { alloyId: 'in718', power: 285, nested: { speed: 960 } };
  const noisy = { ...base, requestId: 'a', clientRequestId: 'b', clientTimestamp: 1, jobId: 'c', runId: 'd', nonce: 'e', idempotencyKey: 'f', nested: { speed: 960, nonce: 'z' } };
  assert.equal(requestKey('POST', '/api/lpbf/jobs', '', base), requestKey('POST', '/api/lpbf/jobs', '', noisy));
});

test('demo-requests.json lists exactly the runtime exclusion list', () => {
  assert.deepEqual([...spec.excludedFields].sort(), [...DEFAULT_EXCLUDED_FIELDS].sort());
});

test('every recorded request body is keyed by the same function the browser uses', () => {
  const index = readJson(path.join(snapDir, 'index.json')) as { entries: Record<string, string> };
  for (const r of spec.requests) {
    const key = requestKey(r.method, r.path, '', r.body, spec.excludedFields);
    assert.ok(index.entries[key], `no snapshot entry for ${key.slice(0, 80)}`);
  }
});

test('committed snapshots: manifest hashes and sizes match the files', () => {
  const manifest = readJson(path.join(snapDir, 'manifest.json')) as { files: Record<string, { bytes: number; sha256: string }> };
  const onDisk = readdirSync(snapDir).filter(f => f.endsWith('.json') && f !== 'manifest.json').sort();
  assert.deepEqual(Object.keys(manifest.files).sort(), onDisk);
  for (const [name, meta] of Object.entries(manifest.files)) {
    const data = readFileSync(path.join(snapDir, name));
    assert.equal(data.length, meta.bytes, name);
    assert.equal(createHash('sha256').update(data).digest('hex'), meta.sha256, name);
  }
});

test('committed snapshots: size budget, provenance and experimentalValidation false everywhere', () => {
  const index = readJson(path.join(snapDir, 'index.json')) as { format: number; appVersion: string; gitCommit: string; fingerprint: string; entries: Record<string, string> };
  const pin = readFileSync(path.join(root, 'python', 'lpbf_implementation_fingerprint.expected'), 'utf8').trim();
  assert.equal(index.format, 1);
  assert.equal(index.fingerprint, pin);
  assert.match(index.gitCommit, /^[0-9a-f]{7,}$/);
  assert.equal(index.appVersion, readJson(path.join(root, 'package.json')).version);
  let total = 0, fields = 0;
  for (const file of new Set(Object.values(index.entries))) {
    const raw = readFileSync(path.join(snapDir, file), 'utf8');
    assert.ok(raw.length <= BUDGET.fileRawBytes, file);
    total += raw.length;
    const snap = JSON.parse(raw);
    assert.equal(snap.recordedWith.fingerprint, pin);
    fields += assertEvidence(file, snap.response);
    assert.doesNotMatch(raw, /[A-Za-z]:\\\\|\/Users\/|\/home\/[a-z]/, `${file} leaks a local path`);
  }
  assert.ok(total <= BUDGET.totalRawBytes);
  assert.ok(fields > 0, 'expected at least one experimentalValidation field in the recorded responses');
});

test('assertEvidence rejects a non-false experimentalValidation at any depth', () => {
  assert.equal(assertEvidence('ok', { a: { experimentalValidation: false }, b: [{ experimentalValidation: false }] }), 2);
  assert.throws(() => assertEvidence('bad', { a: [{ experimentalValidation: true }] }), /must be false/);
  assert.throws(() => assertEvidence('bad', { experimentalValidation: 'false' }), /must be false/);
});

test('normaliseResponse removes only the run-specific fields and lists them', () => {
  const win = { success: true, computeMs: 3293.7, originalComputeMs: 9, cache: { hit: true, key: 'k', scope: 's', stored: true }, grid: { n: 7 } };
  const { response, normalised } = normaliseResponse('process-window', win);
  assert.deepEqual(response, { success: true, computeMs: 0, cache: { hit: false, key: 'k', scope: 's' }, grid: { n: 7 } });
  assert.ok(normalised.length >= 2);
  assert.equal(win.computeMs, 3293.7, 'input is not mutated');

  const job = {
    id: 'abc', cache_key: 'f'.repeat(64), status: 'completed', created: 1791577547.7, cacheHit: true,
    result: {
      provenance: { createdAt: '2026-10-09T20:25:50+00:00', runtime_s: 1.6, inputHash: 'h', executionRuntime: { executable: 'C:\\Users\\x\\python.exe', python: '3.12.10', platform: 'Windows-11', numpy: '2.2.6' } },
      metrics: { width_um: 100.5 }, artifacts: [{ path: '/api/lpbf/jobs/abc/artifacts/input.json' }],
    },
  };
  const out = normaliseResponse('job', job);
  assert.equal(out.jobId, 'demo-ffffffffffffffff');
  assert.equal(out.response.id, out.jobId);
  assert.equal(out.response.created, 0);
  assert.equal(out.response.result.metrics.width_um, 100.5, 'result numbers are never touched');
  assert.equal(out.response.result.provenance.executionRuntime.python, '3.12.10');
  assert.equal(out.response.result.provenance.executionRuntime.executable, 'redacted-local-path');
  assert.match(out.response.result.artifacts[0].path, /demo-ffffffffffffffff/);
});

test('sortKeys gives stable output and drops undefined', () => {
  assert.equal(JSON.stringify(sortKeys({ b: 1, a: { d: undefined, c: [{ z: 1, y: 2 }] } })), '{"a":{"c":[{"y":2,"z":1}]},"b":1}');
});

/** Replays the committed snapshots through the browser fetch wrapper with the exact recorded bodies. */
function replayWorld() {
  const nativeFetch = (async (input: RequestInfo | URL) => {
    const url = String(input);
    const prefix = '/metalliksa/demo-snapshots/';
    if (!url.startsWith(prefix)) return new Response('x', { status: 404 });
    try { return new Response(readFileSync(path.join(snapDir, url.slice(prefix.length)), 'utf8'), { status: 200 }); }
    catch { return new Response('missing', { status: 404 }); }
  }) as typeof fetch;
  return createDemoFetch({ baseUrl: '/metalliksa/', nativeFetch, origin: 'https://example.test' });
}

test('replay: the guided NIST IN718 chain is answered from the committed snapshots', async () => {
  const demoFetch = replayWorld();
  const post = (body: unknown) => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  for (const r of spec.requests.filter(x => x.source !== 'fixture')) {
    // Add the per-call fields a client may generate; they must not change the lookup.
    const body = { ...(r.body as object), requestId: 'client-1', clientTimestamp: 123 };
    const res = await demoFetch(r.path, post(body));
    assert.equal(res.status, 200, r.path);
    const json = await res.json();
    if (r.path === '/api/lpbf/jobs') {
      assert.equal(json.status, 'completed');
      const polled = await demoFetch(`/api/lpbf/jobs/${json.id}`);
      assert.equal(polled.status, 200);
      assert.equal((await polled.json()).status, 'completed');
    }
    if (r.path === '/api/python/lpbf-process-window') assert.equal(json.success, true);
  }
  for (const r of spec.requests.filter(x => x.source === 'fixture')) {
    const res = await demoFetch(r.path);
    assert.equal(res.status, 200, r.path);
    assert.deepEqual(await res.json(), r.fixture);
  }
});

test('replay: a changed power or speed is a miss with the static demo message, never a neighbour', async () => {
  const demoFetch = replayWorld();
  const window = spec.requests.find(r => r.path === '/api/python/lpbf-process-window')!;
  const res = await demoFetch(window.path, { method: 'POST', body: JSON.stringify({ ...(window.body as object), powers: [286] }) });
  assert.equal(res.status, 404);
  assert.equal((await res.json()).errorKind, 'demo-snapshot-missing');
  const job = spec.requests.find(r => r.path === '/api/lpbf/jobs')!;
  const miss = await demoFetch(job.path, { method: 'POST', body: JSON.stringify({ ...(job.body as object), power_W: 286 }) });
  assert.equal(miss.status, 404);
});

test('the runtime-config fixture sets staticDemo and leaves airgapped alone', () => {
  const fixture = spec.requests.find(r => r.path === '/api/runtime-config')!.fixture as Record<string, unknown>;
  assert.equal(fixture.staticDemo, true);
  assert.equal(fixture.airgapped, false);
});
