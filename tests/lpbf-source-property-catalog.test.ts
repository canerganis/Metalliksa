import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { copyFileSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import express from 'express';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { in625GeorgiaTechPropertyCatalogEntry, in625NasaPropertyCatalogEntry } from '../server/lpbfPropertySourceCatalog';
import { LpbfSourceArchiveService } from '../server/lpbfSourceArchiveService';
import { LpbfSourceRepository } from '../server/lpbfSourceRepository';
import { LpbfArtifactStore } from '../server/lpbfArtifactStore';
import { backupSourceBundle, restoreSourceBundle } from '../server/lpbfSourceBundle';
import { createLpbfSourcesRouter } from '../routes/lpbfSources';
import { sourceAction, sourceCatalog } from '../src/services/lpbfSourceService';
import { SourceConditions } from '../src/components/LpbfSourceArchivePanel';

const entries = () => [in625GeorgiaTechPropertyCatalogEntry(), in625NasaPropertyCatalogEntry()];

test('property catalogs bind original bytes and distinguish evidence from material admission', () => {
  const catalog = new LpbfSourceArchiveService().catalog().sources;
  for (const entry of entries()) {
    const document = entry.loadDocument();
    assert.ok(catalog.some(item => item.datasetId === document.datasetId));
    assert.equal(document.processScope, 'material-characterization');
    assert.equal(document.materialId, 'in625');
    assert.equal(document.sourceContext!.model_admission, false);
    assert.equal(document.sourceContext!.runtime_source_validity_range_K, null);
    assert.equal(document.sourceContext!.experimental_validation, 'unvalidated');
    assert.equal(document.sourceContext!.melt_pool_comparison_eligible, false);
    for (const artifact of document.artifacts) {
      const bytes = readFileSync(path.join(entry.sourceRoot, artifact.relativePath));
      assert.equal(bytes.length, artifact.byteSize);
      assert.equal(createHash('sha256').update(bytes).digest('hex'), artifact.sha256);
    }
    // Mutating a returned record cannot promote the next catalog document.
    document.sourceContext!.model_admission = true;
    assert.equal(entry.loadDocument().sourceContext!.model_admission, false);
  }
});

test('property catalog rejects replaced bytes even when a local manifest claims the new hash', t => {
  const root = mkdtempSync(path.join(tmpdir(), 'lpbf-property-source-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const original = in625GeorgiaTechPropertyCatalogEntry();
  const document = original.loadDocument();
  for (const artifact of document.artifacts) copyFileSync(path.join(original.sourceRoot, artifact.relativePath), path.join(root, artifact.relativePath));
  const entry = in625GeorgiaTechPropertyCatalogEntry(root);
  assert.doesNotThrow(() => entry.loadDocument());
  const target = path.join(root, document.artifacts[0].relativePath);
  const bytes = readFileSync(target); bytes[bytes.length - 1] ^= 1; writeFileSync(target, bytes);
  writeFileSync(path.join(root, 'candidate-acquisition-2026-09-27.json'), JSON.stringify({
    sources: [{ ...document.artifacts[0], sha256: createHash('sha256').update(bytes).digest('hex') }], admission: 'validated',
  }));
  assert.throws(() => entry.loadDocument(), /hash mismatch/);
});

test('real property sources round-trip through client, HTTP API, revision store and source bundle', async t => {
  const root = mkdtempSync(path.join(tmpdir(), 'lpbf-property-roundtrip-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const storage = path.join(root, 'store');
  const service = new LpbfSourceArchiveService(storage, entries());
  const app = express(); app.use(createLpbfSourcesRouter(service));
  const server = app.listen(0, '127.0.0.1');
  await new Promise<void>(resolve => server.once('listening', resolve));
  const base = `http://127.0.0.1:${(server.address() as { port: number }).port}`;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = ((input, init) => originalFetch(typeof input === 'string' && input.startsWith('/') ? `${base}${input}` : input, init)) as typeof fetch;
  try {
    const signal = new AbortController().signal;
    assert.deepEqual((await sourceCatalog(signal)).map(row => row.datasetId), entries().map(row => row.datasetId));
    for (const entry of entries()) {
      const { preview } = await sourceAction(entry.datasetId, 'preview', signal);
      assert.equal(preview!.expectedRevision, 0);
      assert.equal(preview!.document.processScope, 'material-characterization');
      const imported = await sourceAction(entry.datasetId, 'import', signal, preview);
      assert.equal(imported.current!.revision, 1);
      assert.equal(imported.current!.evidenceStatus, 'unreviewed-source-archive');
      assert.equal(imported.current!.documentSha256, preview!.documentSha256);
      const verified = await sourceAction(entry.datasetId, 'verify', signal);
      assert.equal(verified.verification!.artifactIntegrity, 'verified-now');
      const reloaded = await sourceAction(entry.datasetId, 'current', signal);
      assert.deepEqual(reloaded.current, imported.current);
      const freshService = new LpbfSourceArchiveService(storage, entries());
      assert.deepEqual(freshService.current(entry.datasetId).current, imported.current);
      assert.deepEqual(freshService.measurements(entry.datasetId).data, []); // Never fabricate melt-pool measurements.
    }
  } finally {
    globalThis.fetch = originalFetch;
    await new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
  }
  const repository = new LpbfSourceRepository(path.join(storage, 'metadata.sqlite'), { readOnly: true });
  try {
    const bundle = path.join(root, 'bundle');
    await backupSourceBundle(repository, new LpbfArtifactStore(path.join(storage, 'artifacts')), bundle);
    const restored = path.join(root, 'restored');
    await restoreSourceBundle(bundle, restored);
    const recovered = new LpbfSourceRepository(path.join(restored, 'metadata.sqlite'), { readOnly: true });
    try {
      for (const entry of entries()) {
        assert.deepEqual(recovered.current(entry.datasetId), repository.current(entry.datasetId));
        for (const artifact of recovered.current(entry.datasetId)!.document.artifacts) {
          await new LpbfArtifactStore(path.join(restored, 'artifacts')).verify(artifact);
        }
      }
    } finally { recovered.close(); }
  } finally { repository.close(); }
});

test('property source UI shows property provenance and missing ranges without camera or optical claims', () => {
  for (const entry of entries()) {
    const markup = renderToStaticMarkup(React.createElement(SourceConditions, { document: entry.loadDocument(), preview: true }));
    assert.match(markup, /Thermophysical property evidence/);
    assert.match(markup, /unverified candidate for material admission/);
    assert.doesNotMatch(markup, /Raw camera signal|Published optical measurements|Beam diameter convention/);
    if (entry.datasetId.includes('georgia')) {
      assert.match(markup, /533.15–1273.15 K/);
      assert.match(markup, /Derived from diffusivity/);
      assert.match(markup, /95% confidence/);
    } else {
      assert.match(markup, /Not established; no extrapolation/);
      assert.match(markup, /DK 15344B/);
      assert.match(markup, /equation conventions unresolved/);
    }
  }
});
