import assert from 'node:assert/strict';
import { existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { test, type TestContext } from 'node:test';
import express from 'express';
import { createLpbfSourcesRouter } from '../routes/lpbfSources';
import { LpbfSourceArchiveService } from '../server/lpbfSourceArchiveService';
import { LpbfArtifactStore } from '../server/lpbfArtifactStore';
import { nistIn718CatalogEntry } from '../server/lpbfSourceCatalog';

async function fixture(t: TestContext) {
  const directory = mkdtempSync(path.join(tmpdir(), 'lpbf-source-http-'));
  const input = path.join(directory, 'input'); mkdirSync(input); writeFileSync(path.join(input, 'sample'), 'abc');
  const document = { schemaVersion: 1, datasetId: 'synthetic', materialId: 'in718', processScope: 'bare-plate',
    source: { url: 'https://example.org/data', citation: 'Synthetic HTTP test', version: '1', terms: null, termsMissingReason: 'Not reviewed' },
    artifacts: [{ relativePath: 'sample', byteSize: 3, sha256: 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad', sourceUrl: 'https://example.org/data' }],
    sourceContext: { temperature_conversion: null } };
  const documentFile = path.join(input, 'document.json'); writeFileSync(documentFile, JSON.stringify(document));
  const storageRoot = path.join(directory, 'storage');
  const service = new LpbfSourceArchiveService(storageRoot, [{ datasetId: 'synthetic', title: 'Synthetic HTTP test', sourceRoot: input,
    loadDocument: () => JSON.parse(readFileSync(documentFile, 'utf8')) }]);
  const app = express(); app.use(createLpbfSourcesRouter(service));
  const server = app.listen(0, '127.0.0.1'); await new Promise<void>(resolve => server.once('listening', resolve));
  const base = `http://127.0.0.1:${(server.address() as { port: number }).port}/api/lpbf/sources`;
  t.after(async () => { await new Promise<void>(resolve => server.close(() => resolve())); rmSync(directory, { recursive: true, force: true }); });
  const post = (suffix: string, body = {}, headers = {}) => fetch(base + suffix, { method: 'POST', headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(body) });
  return { base, post, storageRoot, document, documentFile, input, service };
}

test('source API previews without storage writes then imports a hash-bound source revision', async t => {
  const f = await fixture(t);
  assert.equal((await (await fetch(f.base)).json()).sources[0].datasetId, 'synthetic');
  const previewResponse = await f.post('/synthetic/preview'); assert.equal(previewResponse.status, 200);
  const preview = await previewResponse.json();
  assert.equal(preview.expectedRevision, 0); assert.equal(preview.artifactCount, 1);
  assert.equal(existsSync(f.storageRoot), false);
  const body = { expectedRevision: 0, documentSha256: preview.documentSha256 };
  const response = await f.post('/synthetic/import', body); assert.equal(response.status, 200);
  const imported = await response.json(); assert.equal(imported.revision.revision, 1);
  assert.equal(imported.revision.document.sourceContext.temperature_conversion, null);
  assert.equal((await f.post('/synthetic/import', body)).status, 409);
  const record = await (await fetch(f.base + '/synthetic')).json();
  assert.equal(record.current.artifactIntegrity, 'not-verified');
  const verified = await (await f.post('/synthetic/verify')).json();
  assert.equal(verified.artifactIntegrity, 'verified-now'); assert.equal(verified.revision, 1);
  const stored = await new LpbfArtifactStore(path.join(f.storageRoot, 'artifacts')).verify(f.document.artifacts[0]);
  writeFileSync(stored.path, 'bad');
  const failed = await f.post('/synthetic/verify'); assert.equal(failed.status, 503);
  assert.doesNotMatch(JSON.stringify(await failed.json()), /[A-Z]:\\/);
});

test('source API lists retained revisions and resolves an exact historical revision', async t => {
  const f = await fixture(t);
  const firstPreview = await (await f.post('/synthetic/preview')).json();
  const first = await (await f.post('/synthetic/import', { expectedRevision: 0, documentSha256: firstPreview.documentSha256 })).json();
  f.document.source.version = '2'; writeFileSync(f.documentFile, JSON.stringify(f.document));
  const secondPreview = await (await f.post('/synthetic/preview')).json();
  const second = await (await f.post('/synthetic/import', { expectedRevision: 1, documentSha256: secondPreview.documentSha256 })).json();

  const page = await (await fetch(`${f.base}/synthetic/revisions?offset=0&limit=1`)).json();
  assert.equal(page.datasetId, 'synthetic'); assert.equal(page.offset, 0); assert.equal(page.limit, 1);
  assert.equal(page.hasMore, true); assert.equal(page.revisions.length, 1);
  assert.equal(page.revisions[0].revision, 1); assert.equal(page.revisions[0].documentSha256, first.revision.documentSha256);
  assert.equal(page.revisions[0].materialId, 'in718'); assert.equal('document' in page.revisions[0], false);
  const exact = await (await fetch(`${f.base}/synthetic/revisions/1`)).json();
  assert.equal(exact.revision.document.source.version, '1');
  assert.equal(exact.revision.documentSha256, first.revision.documentSha256);
  const latest = await (await fetch(`${f.base}/synthetic/revisions?offset=1&limit=1`)).json();
  assert.equal(latest.hasMore, false); assert.equal(latest.revisions[0].revision, second.revision.revision);
  assert.equal((await fetch(`${f.base}/synthetic/revisions/3`)).status, 404);
  assert.equal((await fetch(`${f.base}/synthetic/revisions/0`)).status, 400);
  assert.equal((await fetch(`${f.base}/synthetic/revisions?offset=-1`)).status, 400);
  assert.equal((await fetch(`${f.base}/synthetic`)).status, 200, 'legacy current endpoint remains available');
});

test('changed source metadata and changed input bytes invalidate preview before import', async t => {
  const f = await fixture(t);
  const preview = await (await f.post('/synthetic/preview')).json();
  f.document.source.version = '2'; writeFileSync(f.documentFile, JSON.stringify(f.document));
  assert.equal((await f.post('/synthetic/import', { expectedRevision: 0, documentSha256: preview.documentSha256 })).status, 409);
  assert.equal(existsSync(f.storageRoot), false);
  const fresh = await (await f.post('/synthetic/preview')).json(); writeFileSync(path.join(f.input, 'sample'), 'bad');
  assert.equal((await f.post('/synthetic/import', { expectedRevision: 0, documentSha256: fresh.documentSha256 })).status, 503);
  const state = await (await fetch(f.base + '/synthetic')).json(); assert.equal(state.current, null);
});

test('source routes reject unknown IDs, client paths, cross-origin requests and oversized bodies', async t => {
  const f = await fixture(t);
  assert.equal((await f.post('/unknown/preview')).status, 404);
  assert.equal((await f.post('/synthetic/preview', { sourceRoot: 'C:/private' })).status, 400);
  assert.equal((await f.post('/synthetic/preview', {}, { Origin: 'https://other.example' })).status, 403);
  assert.equal((await f.post('/synthetic/preview', {}, { 'Sec-Fetch-Site': 'cross-site' })).status, 403);
  assert.equal((await f.post('/synthetic/import', { expectedRevision: -1, documentSha256: 'bad' })).status, 400);
  assert.equal((await f.post('/synthetic/preview', { value: 'a'.repeat(17000) })).status, 413);
  assert.equal(existsSync(f.storageRoot), false);
});

test('overlapping archive work is refused while one operation owns the service', async t => {
  const f = await fixture(t);
  const first = f.service.preview('synthetic');
  await assert.rejects(f.service.preview('synthetic'), /already running/i);
  await first;
  assert.equal((await f.service.preview('synthetic')).artifactCount, 1);
});

test('NIST catalog adapter preserves unknown measurements and rejects mismatched README context', t => {
  const root = path.resolve('data/benchmark/nist-amb2022-03');
  const entry = nistIn718CatalogEntry(root);
  const document = entry.loadDocument() as { materialId: string; processScope: string; sourceContext: any };
  assert.equal(document.materialId, 'in718'); assert.equal(document.processScope, 'bare-plate');
  assert.equal(document.sourceContext.measurement.temperature_conversion, null);
  assert.equal(document.sourceContext.thermal_validation_ready, false);
  const directory = mkdtempSync(path.join(tmpdir(), 'nist-catalog-'));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  writeFileSync(path.join(directory, 'manifest.json'), readFileSync(path.join(root, 'manifest.json')));
  const context = JSON.parse(readFileSync(path.join(root, 'source-context.json'), 'utf8'));
  context.readme.sha256 = 'f'.repeat(64);
  writeFileSync(path.join(directory, 'source-context.json'), JSON.stringify(context));
  assert.throws(() => nistIn718CatalogEntry(directory).loadDocument(), /fingerprint mismatch/i);
});

test('NIST catalog binds HDF5 review to every reviewed source fingerprint', t => {
  const root = path.resolve('data/benchmark/nist-amb2022-03');
  const directory = mkdtempSync(path.join(tmpdir(), 'nist-review-'));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  const manifest = JSON.parse(readFileSync(path.join(root, 'manifest.json'), 'utf8'));
  const context = JSON.parse(readFileSync(path.join(root, 'source-context.json'), 'utf8'));
  context.hdf5_review = { artifacts: manifest.files.filter((file: any) => file.kind !== 'readme')
    .map((file: any) => ({ path: file.path, sha256: file.sha256, source_url: file.source_url })) };
  writeFileSync(path.join(directory, 'manifest.json'), JSON.stringify(manifest));
  writeFileSync(path.join(directory, 'source-context.json'), JSON.stringify(context));
  assert.doesNotThrow(() => nistIn718CatalogEntry(directory).loadDocument());
  context.hdf5_review.artifacts[0].sha256 = 'e'.repeat(64);
  writeFileSync(path.join(directory, 'source-context.json'), JSON.stringify(context));
  assert.throws(() => nistIn718CatalogEntry(directory).loadDocument(), /HDF5.*fingerprint/i);
});
