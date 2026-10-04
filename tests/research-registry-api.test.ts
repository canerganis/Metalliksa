import assert from 'node:assert/strict';
import { test } from 'node:test';
import fsPromises, { mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { syncBuiltinESMExports } from 'node:module';
import os from 'node:os';
import path from 'node:path';
import express from 'express';
import { createResearchRegistryRouter } from '../routes/researchRegistry';
import { ResearchEvidenceRegistry, ResearchRegistryError } from '../server/researchEvidenceRegistry';

const empty = () => ({ schemaVersion: 1, briefs: [], sources: [], findings: [], integrations: [], feedback: [] });
// Contract fixture only: this is a research question, not experimental evidence.
const fixture = () => ({ ...empty(), briefs: [{ id: 'brief-fixture', question: 'Synthetic server contract fixture?', alloy: 'Fixture', process: 'Fixture', method: 'Fixture', dataType: 'Fixture', createdAt: '2026-09-13T00:00:00.000Z' }] });
async function start(directory: string, lockTimeout = 2000) {
  const app = express();
  app.use(createResearchRegistryRouter(new ResearchEvidenceRegistry(directory, lockTimeout)));
  // Match production ordering: a larger downstream parser cannot bypass 10 MB.
  app.use(express.json({ limit: '50mb' }));
  const server = app.listen(0, '127.0.0.1');
  await new Promise<void>(resolve => server.once('listening', resolve));
  const origin = `http://127.0.0.1:${(server.address() as { port: number }).port}`;
  const url = `${origin}/api/research/registry`;
  return {
    url, origin,
    get: (suffix = '') => fetch(`${url}${suffix}`),
    put: (body: unknown, headers: Record<string, string> = {}) => fetch(url, { method: 'PUT', headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(body) }),
    close: () => new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve())),
  };
}

test('server registry persists identity, immutable versions and history across router restarts', async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'research-registry-api-'));
  let api = await start(directory);
  try {
    const response = await api.get(); assert.equal(response.status, 200); assert.equal(response.headers.get('cache-control'), 'no-store');
    const initial = await response.json();
    assert.equal(typeof initial.registryId, 'string'); assert.equal(initial.revision, 0); assert.equal(initial.savedAt, null); assert.deepEqual(initial.snapshot, empty());
    assert.deepEqual((await (await api.get('/history')).json()).revisions, []);
    let saved = await api.put({ registryId: initial.registryId, expectedRevision: 0, snapshot: { ...fixture(), hydrationStatus: 'not a schema field' } }, { origin: api.origin });
    assert.equal(saved.status, 200);
    const first = await saved.json(); assert.equal(first.revision, 1); assert.equal(typeof first.savedAt, 'string'); assert.deepEqual(first.snapshot, fixture());
    const immutablePath = path.join(directory, 'revision-000000000001.json');
    const immutableBytes = await readFile(immutablePath, 'utf8');
    await api.close(); api = await start(directory);
    assert.deepEqual(await (await api.get()).json(), first);
    saved = await api.put({ registryId: first.registryId, expectedRevision: 1, snapshot: empty() }); assert.equal(saved.status, 200);
    const second = await saved.json(); assert.equal(second.revision, 2);
    assert.equal(await readFile(immutablePath, 'utf8'), immutableBytes);
    assert.deepEqual(await (await api.get('/revisions/1')).json(), first);
    assert.deepEqual(await (await api.get('/revisions/0')).json(), initial);
    assert.deepEqual(await (await api.get('/history')).json(), { registryId: initial.registryId, revisions: [{ revision: 1, savedAt: first.savedAt }, { revision: 2, savedAt: second.savedAt }] });
    assert.equal((await api.get('/revisions/3')).status, 404);
    for (const revision of ['-1', '1.0', '01', '9007199254740992', 'abc']) assert.equal((await api.get(`/revisions/${revision}`)).status, 400);
  } finally { await api.close(); await rm(directory, { recursive: true, force: true }); }
});

test('separate registry instances serialize concurrent writers and reject stale identities', async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'research-registry-race-'));
  const a = await start(directory), b = await start(directory);
  try {
    const [first, other] = await Promise.all([a.get().then(r => r.json()), b.get().then(r => r.json())]);
    assert.equal(first.registryId, other.registryId);
    const responses = await Promise.all([a.put({ registryId: first.registryId, expectedRevision: 0, snapshot: fixture() }), b.put({ registryId: first.registryId, expectedRevision: 0, snapshot: empty() })]);
    assert.deepEqual(responses.map(r => r.status).sort(), [200, 409]);
    const winner = await responses.find(r => r.status === 200)!.json();
    const conflict = await responses.find(r => r.status === 409)!.json();
    assert.deepEqual(conflict.current, winner);
    const oldIdentity = await a.put({ registryId: 'another-registry', expectedRevision: 1, snapshot: empty() });
    assert.equal(oldIdentity.status, 409); assert.deepEqual((await oldIdentity.json()).current, winner);
    assert.equal((await readdir(directory)).filter(name => name.startsWith('revision-')).length, 2);
  } finally { await Promise.all([a.close(), b.close()]); await rm(directory, { recursive: true, force: true }); }
});

test('a Windows lock release race (EPERM from the exclusive create) is retried as contention; a persistent EPERM still fails', async t => {
  // On Windows, open(lock, 'wx') while another holder's unlink is completing fails with EPERM (delete pending)
  // instead of EEXIST; measured with four processes cycling one lock file, about 1 % of contended attempts.
  // That window cannot be scheduled from a test, so its observable result is injected at the fs boundary.
  const directory = await mkdtemp(path.join(os.tmpdir(), 'research-registry-eperm-'));
  const lockPath = path.join(directory, '.write-lock');
  const platform = Object.getOwnPropertyDescriptor(process, 'platform')!;
  const realOpen = fsPromises.open;
  let failNext = 0, injected = 0;
  t.mock.method(fsPromises, 'open', async (...args: Parameters<typeof realOpen>) => {
    if (args[0] === lockPath && args[1] === 'wx' && failNext !== 0) {
      failNext -= 1; injected += 1;
      throw Object.assign(new Error(`EPERM: operation not permitted, open '${lockPath}'`), { code: 'EPERM', syscall: 'open', path: lockPath });
    }
    return realOpen(...args);
  });
  syncBuiltinESMExports();
  const setPlatform = (value: string) => Object.defineProperty(process, 'platform', { ...platform, value });
  try {
    setPlatform('win32');
    failNext = 3;
    assert.equal((await new ResearchEvidenceRegistry(directory, 2000).current()).revision, 0);
    assert.equal(injected, 3, 'every transient EPERM was retried, then the lock was acquired');

    failNext = -1; injected = 0;
    await assert.rejects(new ResearchEvidenceRegistry(directory, 100).current(),
      error => (error as NodeJS.ErrnoException).code === 'EPERM' && !(error instanceof ResearchRegistryError));
    assert.ok(injected > 1, 'a persistent EPERM is retried until the lock deadline, then surfaced unchanged');

    setPlatform('linux');
    injected = 0;
    await assert.rejects(new ResearchEvidenceRegistry(directory, 2000).current(), error => (error as NodeJS.ErrnoException).code === 'EPERM');
    assert.equal(injected, 1, 'outside Windows EPERM is a permission failure and is not retried');
  } finally {
    Object.defineProperty(process, 'platform', platform);
    t.mock.restoreAll();
    syncBuiltinESMExports();
    await rm(directory, { recursive: true, force: true });
  }
});

test('registry validates body, source integrity and browser mutation origin without modifying saved data', async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'research-registry-invalid-'));
  const api = await start(directory);
  try {
    const initial = await (await api.get()).json();
    const body = { registryId: initial.registryId, expectedRevision: 0, snapshot: fixture() };
    for (const patch of [{ expectedRevision: '0' }, { expectedRevision: null }, { expectedRevision: -1 }, { expectedRevision: 0.5 }, { registryId: 123 }, { registryId: '' }, { snapshot: null }, { snapshot: { ...empty(), schemaVersion: 2 } }, { snapshot: { ...fixture(), sources: [{ id: 'orphan' }] } }]) {
      const result = await api.put({ ...body, ...patch }); assert.equal(result.status, 400); assert.equal(typeof (await result.json()).error, 'string');
    }
    assert.equal((await api.put(body, { origin: 'https://other.example' })).status, 403);
    assert.equal((await api.put(body, { origin: 'null' })).status, 403);
    assert.equal((await api.put(body, { 'sec-fetch-site': 'cross-site' })).status, 403);
    assert.equal((await api.put(body, { 'Content-Type': 'text/plain' })).status, 415);
    assert.equal((await fetch(api.url, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: '{broken' })).status, 400);
    assert.equal((await api.put({ ...body, oversized: 'x'.repeat(10 * 1024 * 1024) })).status, 413);
    assert.deepEqual(await (await api.get()).json(), initial);
  } finally { await api.close(); await rm(directory, { recursive: true, force: true }); }
});

test('corrupt or missing versions fail closed for read and write, preserving original bytes', async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'research-registry-corrupt-'));
  const api = await start(directory);
  try {
    const initial = await (await api.get()).json();
    const body = { registryId: initial.registryId, expectedRevision: 0, snapshot: fixture() };
    assert.equal((await api.put(body)).status, 200);
    const version = path.join(directory, 'revision-000000000001.json');
    await writeFile(version, '{partial corruption fixture');
    for (const suffix of ['', '/history', '/revisions/0']) assert.equal((await api.get(suffix)).status, 503);
    assert.equal((await api.put({ ...body, expectedRevision: 1 })).status, 503);
    assert.equal(await readFile(version, 'utf8'), '{partial corruption fixture');
    await rm(path.join(directory, 'revision-000000000000.json'));
    assert.equal((await api.get()).status, 503);
    assert.deepEqual((await readdir(directory)).sort(), ['revision-000000000001.json']);
  } finally { await api.close(); await rm(directory, { recursive: true, force: true }); }
});

test('abandoned locks, interrupted initialization and filesystem failures are explicit and never reset', async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'research-registry-failure-'));
  const api = await start(directory, 40);
  let blocked: Awaited<ReturnType<typeof start>> | undefined;
  try {
    await writeFile(path.join(directory, '.write-lock'), 'abandoned fixture lock');
    assert.equal((await api.get()).status, 503);
    assert.equal(await readFile(path.join(directory, '.write-lock'), 'utf8'), 'abandoned fixture lock');
    await rm(path.join(directory, '.write-lock'));
    await writeFile(path.join(directory, '.pending-fixture'), 'incomplete initial write');
    assert.equal((await api.get()).status, 503);
    assert.deepEqual(await readdir(directory), ['.pending-fixture']);
    const file = path.join(directory, 'not-a-directory'); await writeFile(file, 'preserve');
    blocked = await start(file);
    assert.equal((await blocked.get()).status, 503); assert.equal(await readFile(file, 'utf8'), 'preserve');
  } finally { await api.close(); await blocked?.close(); await rm(directory, { recursive: true, force: true }); }
});
