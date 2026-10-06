import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import express from 'express';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createLpbfSourcesRouter } from '../routes/lpbfSources';
import { LpbfSourceArchiveService } from '../server/lpbfSourceArchiveService';
import { nistIn718CatalogEntry, nistIn718ThermographyDerivedCatalogEntry } from '../server/lpbfSourceCatalog';
import type { LpbfSourceDocument } from '../src/types/lpbfSource';
import { SourceConditions } from '../src/components/LpbfSourceArchivePanel';

// Fixtures: the committed files under data/benchmark/nist-amb2022-03 (derived table and manifest written by
// python/lpbf_nist_mds2_2716_thermography.py from the hash-pinned NIST HDF5 files; NERDm record re-serialised
// from the NIST RMM query). The raw HDF5 files are not needed by these tests.
const datasetRoot = path.resolve('data/benchmark/nist-amb2022-03');
const derivedRoot = path.join(datasetRoot, 'derived');
const sourceId = 'nist-mds2-2716-thermography-signal-v1';
const sha = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex');

/** Copy the committed derived/, official/ and the source manifest into a temp dataset directory. */
function copyDataset(t: { after: (fn: () => void) => void }) {
  const dataset = mkdtempSync(path.join(tmpdir(), 'lpbf-nist-2716-'));
  t.after(() => rmSync(dataset, { recursive: true, force: true }));
  for (const directory of ['official', 'derived']) {
    mkdirSync(path.join(dataset, directory));
    for (const name of readdirSync(path.join(datasetRoot, directory))) {
      copyFileSync(path.join(datasetRoot, directory, name), path.join(dataset, directory, name));
    }
  }
  copyFileSync(path.join(datasetRoot, 'manifest.json'), path.join(dataset, 'manifest.json'));
  return dataset;
}

test('NIST mds2-2716 thermography metrics load with pinned identity and no temperature', () => {
  const document = nistIn718ThermographyDerivedCatalogEntry(derivedRoot).loadDocument() as any;
  assert.equal(document.datasetId, sourceId);
  assert.equal(document.materialId, 'in718');
  assert.equal(document.processScope, 'bare-plate');
  assert.equal(document.source.url, 'https://doi.org/10.18434/mds2-2716');
  assert.equal(document.source.version, '1.3.1');
  assert.equal(document.source.terms, 'NIST Open License: https://www.nist.gov/open/license');
  // The citation shown in the UI is built from the committed NERDm record: all authors in record order, exact title.
  const nerdm = JSON.parse(readFileSync(path.join(datasetRoot, 'official/nerdm-record-mds2-2716.json'), 'utf8'));
  const citation: string = document.source.citation;
  assert.ok(citation.includes(nerdm.title), 'citation carries the exact NERDm title');
  assert.ok(!citation.includes('et al.'));
  const positions = nerdm.authors.map((author: any) => citation.indexOf(`${author.familyName}, `));
  assert.deepEqual(nerdm.authors.map((author: any) => author.familyName), ['Deisenroth', 'Mekhontsev', 'Lane', 'Weaver', 'Yeung']);
  assert.ok(positions.every((position: number) => position >= 0));
  assert.deepEqual([...positions].sort((a: number, b: number) => a - b), positions);
  assert.match(citation, /Version 1\.3\.1; first released 2022-07-15/);
  assert.ok(citation.endsWith('https://doi.org/10.18434/mds2-2716'));
  assert.match(document.sourceContext.headline, /^Signal-unit metrics only, not validation/);
  for (const artifact of document.artifacts) {
    const bytes = readFileSync(path.join(datasetRoot, artifact.relativePath));
    assert.equal(artifact.byteSize, bytes.length, artifact.relativePath);
    assert.equal(artifact.sha256, sha(bytes), artifact.relativePath);
  }
  assert.deepEqual(document.artifacts.map((item: any) => item.relativePath),
    ['derived/thermography-signal-metrics-v1.json', 'official/nerdm-record-mds2-2716.json']);
  const context = document.sourceContext;
  assert.equal(context.measurement.temperature_conversion, null);
  assert.match(context.measurement.temperature_conversion_missing_reason, /emissivity/);
  assert.equal(context.split, 'unassigned');
  assert.equal(context.thermal_validation_ready, false);
  assert.ok(context.raw_inputs.every((input: any) => input.committed === false));
  assert.ok(context.unavailable_quantities.length > 0);
  assert.ok(context.unavailable_quantities.every((item: any) => item.status === 'unavailable' && item.reason.length > 0));
  assert.ok(context.unresolved.some((item: string) => /Pixel pitch .* inferred/.test(item)));
  assert.doesNotMatch(JSON.stringify(document), /"experimentalValidation":true|"opticalOperatorMatched":true|"status":"compared"/);
  assert.ok(new LpbfSourceArchiveService().catalog().sources.some(item => item.datasetId === sourceId));
});

test('NIST mds2-2716 derived input pins equal the existing raw source manifest and the NERDm record', () => {
  const derived = JSON.parse(readFileSync(path.join(derivedRoot, 'manifest.json'), 'utf8'));
  const sourceDocument = nistIn718CatalogEntry(datasetRoot).loadDocument() as any;
  const raw = new Map(sourceDocument.artifacts.map((item: any) => [path.posix.basename(item.relativePath), item]));
  const nerdm = JSON.parse(readFileSync(path.join(datasetRoot, 'official', 'nerdm-record-mds2-2716.json'), 'utf8'));
  const published = new Map((nerdm.components as any[]).filter(item => item.checksum?.hash)
    .map(item => [path.posix.basename(item.filepath).replace(/^2716_/, ''), item]));
  assert.equal(derived.inputs.length, 3);
  for (const input of derived.inputs) {
    const archived = raw.get(input.name) as any;
    assert.ok(archived, input.name);
    assert.equal(archived.byteSize, input.bytes);
    assert.equal(archived.sha256, input.sha256);
    const record = published.get(input.name) as any;
    assert.equal(record.size, input.bytes);
    assert.equal(record.checksum.hash, input.sha256);
  }
});

test('NIST mds2-2716 rejects a changed derived manifest', t => {
  const dataset = copyDataset(t);
  const manifestPath = path.join(dataset, 'derived', 'manifest.json');
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  manifest.evidence.experimentalValidation = true;
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 1) + '\n');
  assert.throws(() => nistIn718ThermographyDerivedCatalogEntry(path.join(dataset, 'derived')).loadDocument(),
    /derived manifest SHA-256 mismatch/);
});

test('NIST mds2-2716 rejects a changed derived table byte', t => {
  const dataset = copyDataset(t);
  const file = path.join(dataset, 'derived', 'thermography-signal-metrics-v1.json');
  const bytes = readFileSync(file);
  bytes[bytes.length - 5] ^= 1;
  writeFileSync(file, bytes);
  assert.throws(() => nistIn718ThermographyDerivedCatalogEntry(path.join(dataset, 'derived')).loadDocument(),
    /derived table SHA-256 mismatch/);
});

test('NIST mds2-2716 rejects a truncated derived table by size', t => {
  const dataset = copyDataset(t);
  const file = path.join(dataset, 'derived', 'thermography-signal-metrics-v1.json');
  writeFileSync(file, readFileSync(file).subarray(1));
  assert.throws(() => nistIn718ThermographyDerivedCatalogEntry(path.join(dataset, 'derived')).loadDocument(),
    /Invalid NIST mds2-2716 derived table file/);
});

test('NIST mds2-2716 rejects a source manifest whose raw pin disagrees', t => {
  const dataset = copyDataset(t);
  const manifestPath = path.join(dataset, 'manifest.json');
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  manifest.files.find((file: any) => file.path.endsWith('StaringCamera_Signal.h5')).sha256 = '0'.repeat(64);
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  assert.throws(() => nistIn718ThermographyDerivedCatalogEntry(path.join(dataset, 'derived')).loadDocument(),
    /input pin mismatch/);
});

test('NIST mds2-2716 rejects a changed NERDm record', t => {
  const dataset = copyDataset(t);
  const file = path.join(dataset, 'official', 'nerdm-record-mds2-2716.json');
  const bytes = readFileSync(file);
  bytes[10] ^= 1;
  writeFileSync(file, bytes);
  assert.throws(() => nistIn718ThermographyDerivedCatalogEntry(path.join(dataset, 'derived')).loadDocument(),
    /NERDm record SHA-256 mismatch/);
});

test('NIST mds2-2716 thermography metrics preview, import and verify in the source API', async t => {
  const storage = mkdtempSync(path.join(tmpdir(), 'lpbf-nist-2716-source-store-'));
  t.after(() => rmSync(storage, { recursive: true, force: true }));
  const service = new LpbfSourceArchiveService(storage, [nistIn718ThermographyDerivedCatalogEntry(derivedRoot)]);
  const app = express(); app.use(createLpbfSourcesRouter(service));
  const server = app.listen(0, '127.0.0.1');
  await new Promise<void>(resolve => server.once('listening', resolve));
  t.after(() => new Promise<void>(resolve => server.close(() => resolve())));
  const base = `http://127.0.0.1:${(server.address() as { port: number }).port}/api/lpbf/sources`;
  const post = (suffix: string, body = {}) => fetch(`${base}/${sourceId}/${suffix}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const previewResponse = await post('preview');
  assert.equal(previewResponse.status, 200);
  const preview = await previewResponse.json();
  assert.equal(preview.artifactCount, 2);
  assert.equal(preview.evidenceStatus, 'unreviewed-source-archive');
  const imported = await (await post('import', { expectedRevision: 0, documentSha256: preview.documentSha256 })).json();
  assert.equal(imported.revision.revision, 1);
  const verified = await (await post('verify')).json();
  assert.equal(verified.artifactIntegrity, 'verified-now');
});

test('NIST mds2-2716 source UI states raw camera signal and the missing temperature conversion', () => {
  const document = nistIn718ThermographyDerivedCatalogEntry(derivedRoot).loadDocument() as LpbfSourceDocument;
  const markup = renderToStaticMarkup(React.createElement(SourceConditions, { document, preview: true }));
  assert.match(markup, /Raw camera signal is not measured temperature/);
  assert.match(markup, /digital levels \(DL\)/);
  assert.match(markup, /No temperature conversion executed/);
  assert.match(markup, /D4s \(literal HDF5 spot_size_measure\)/);
  assert.doesNotMatch(markup, /Temperature conversion<\/dt><dd class="mt-1">[0-9]/);
});
