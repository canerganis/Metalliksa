import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import express from 'express';
import { createLpbfSourcesRouter } from '../routes/lpbfSources';
import { LpbfSourceArchiveService } from '../server/lpbfSourceArchiveService';
import { nistMds22525AbsorptanceCatalogEntry } from '../server/lpbfSourceCatalog';

const datasetRoot = path.resolve('data/benchmark/nist-mds2-2525-ti64-absorptance');
const officialRoot = path.join(datasetRoot, 'official');
const sourceId = 'nist-mds2-2525-ti64-absorptance-v1';
const sha = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex');

/** Copy official/ and derived/ into a temp dataset directory with the same layout. */
function copyDataset(t: { after: (fn: () => void) => void }) {
  const dataset = mkdtempSync(path.join(tmpdir(), 'lpbf-nist-2525-'));
  t.after(() => rmSync(dataset, { recursive: true, force: true }));
  for (const directory of ['official', 'derived']) {
    mkdirSync(path.join(dataset, directory));
    for (const name of readdirSync(path.join(datasetRoot, directory))) {
      copyFileSync(path.join(datasetRoot, directory, name), path.join(dataset, directory, name));
    }
  }
  return dataset;
}

test('NIST mds2-2525 absorptance source loads with pinned identity, observations and caveats', () => {
  const manifest = JSON.parse(readFileSync(path.join(officialRoot, 'manifest.json'), 'utf8'));
  const document = nistMds22525AbsorptanceCatalogEntry(officialRoot).loadDocument() as any;
  assert.equal(document.datasetId, sourceId);
  assert.equal(document.materialId, 'ti6al4v');
  assert.equal(document.processScope, 'bare-plate');
  assert.equal(document.source.url, 'https://doi.org/10.18434/mds2-2525');
  assert.equal(document.source.version, '1.3.2');
  assert.equal(document.source.terms, 'NIST Open License: https://www.nist.gov/open/license');
  assert.equal(document.source.termsMissingReason, null);
  assert.equal(document.sourceContext.split, 'unassigned');
  assert.equal(document.artifacts.length, manifest.files.length + 1);
  for (const file of manifest.files) {
    const bytes = readFileSync(path.join(officialRoot, file.path));
    assert.equal(file.bytes, bytes.length);
    assert.equal(file.sha256, sha(bytes));
    assert.ok(document.artifacts.some((item: any) => item.relativePath === `official/${file.path}`
      && item.sha256 === file.sha256 && item.byteSize === file.bytes && item.sourceUrl === file.source_url));
  }
  const derivedBytes = readFileSync(path.join(datasetRoot, 'derived', 'ti64-spot-absorptance-summary-v1.json'));
  assert.equal(manifest.derived_tables[0].sha256, sha(derivedBytes));
  assert.equal(manifest.derived_tables[0].bytes, derivedBytes.length);
  const derivedArtifact = document.artifacts.find((item: any) => item.relativePath.startsWith('derived/'));
  assert.equal(derivedArtifact.sha256, sha(derivedBytes));
  assert.equal(derivedArtifact.sourceUrl, 'https://doi.org/10.18434/mds2-2525');
  assert.equal(document.sourceContext.locally_derived_artifacts[0].published_by_nist, false);

  const observations = document.sourceContext.observations as any[];
  assert.equal(observations.length, 10);
  assert.ok(observations.every(row => row.measured === true && row.comparable_to_app_models === false));
  const ti64 = observations.filter(row => row.material.startsWith('Ti-6Al-4V'));
  assert.equal(ti64.length, 2);
  assert.ok(Math.abs(ti64[0].value - 32.5) < 0.5);
  assert.ok(ti64[1].value > 60 && ti64[1].value < 66);
  assert.ok(ti64.every(row => row.derived_locally === true && /not NIST-published|not NIST-published phase/.test(row.window_definition)));
  const aluminium = observations.filter(row => row.material === 'aluminium (NIST SRM 1241c)');
  assert.equal(aluminium.length, 8);
  assert.ok(aluminium.every(row => typeof row.comparable_reason === 'string' && row.comparable_reason.length > 0));
  const find = (label: RegExp) => aluminium.find(row => label.test(row.label));
  assert.deepEqual([find(/spot, average absorptance before/)?.value, find(/spot, average absorptance before/)?.std_dev], [23.9, 0.3]);
  assert.deepEqual([find(/spot, average absorptance during/)?.value, find(/spot, average absorptance during/)?.std_dev], [64.1, 3.9]);
  assert.deepEqual([find(/spot, solidification/)?.value, find(/spot, solidification/)?.std_dev], [0.46, 0.03]);
  assert.deepEqual([find(/scan, average absorptance before/)?.value, find(/scan, average absorptance before/)?.std_dev], [23.8, 0.08]);
  assert.deepEqual([find(/scan, average absorptance during/)?.value, find(/scan, average absorptance during/)?.std_dev], [43.3, 1.5]);
  assert.deepEqual([find(/maximum melt-pool depth/)?.value, find(/maximum melt-pool depth/)?.std_dev], [88.8, 0.4]);
  assert.deepEqual([find(/maximum melt-pool width/)?.value, find(/maximum melt-pool width/)?.std_dev], [326, 16.08]);
  assert.deepEqual([find(/scan, solidification/)?.value, find(/scan, solidification/)?.std_dev], [0.191, 0.019]);

  const unresolved = (document.sourceContext.unresolved as string[]).join('\n');
  assert.match(unresolved, /SRM 1241c/);
  assert.match(unresolved, /scan CSV and the absorption uncertainty PDF were not acquired/);
  assert.match(unresolved, /thin polished bare coupon, not on a powder bed/);
  assert.match(unresolved, /does not solve keyhole geometry/);
  assert.match(unresolved, /experimentalValidation stays false/);
  assert.match(document.sourceContext.measurement.quantity, /integrating sphere/);
  assert.ok(new LpbfSourceArchiveService().catalog().sources.some(item => item.datasetId === sourceId));
});

test('NIST mds2-2525 lists the two absent files as unavailable with their official hashes', () => {
  const document = nistMds22525AbsorptanceCatalogEntry(officialRoot).loadDocument() as any;
  const unavailable = document.sourceContext.unavailable_files as any[];
  assert.deepEqual(unavailable.map(item => [item.file, item.status, item.sha256, item.bytes]), [
    ['Scan on Bare Metal_Calibrated Absorption Data.csv', 'unavailable',
      '1c64f24e84c274d9f9ae27fb09e79b86cda2fda5bee4b67da3567c8a59ca499d', 6657476],
    ['Absorption_Uncertainty_Analysis.pdf', 'unavailable',
      '98ead678e3a8f6696650302dbf29660f2a886a62ba677453dd130c222755e28d', 388131],
  ]);
  assert.ok(unavailable.every(item => /timed out/.test(item.reason)));
  assert.ok(document.artifacts.every((item: any) => !/Scan on Bare Metal|Absorption_Uncertainty/.test(item.relativePath)));
});

test('NIST mds2-2525 rejects a tampered manifest copy', t => {
  const dataset = copyDataset(t);
  const manifestPath = path.join(dataset, 'official', 'manifest.json');
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  manifest.experiment.pulse_duration_ms = 3.0;
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  assert.throws(() => nistMds22525AbsorptanceCatalogEntry(path.join(dataset, 'official')).loadDocument(),
    /manifest SHA-256 mismatch/i);
});

test('NIST mds2-2525 rejects a changed CSV byte', t => {
  const dataset = copyDataset(t);
  const csv = path.join(dataset, 'official', 'Al_Spot_AA_ASR_Results.csv');
  const bytes = readFileSync(csv);
  bytes[bytes.length - 3] ^= 1;
  writeFileSync(csv, bytes);
  assert.throws(() => nistMds22525AbsorptanceCatalogEntry(path.join(dataset, 'official')).loadDocument(),
    /integrity mismatch/i);
});

test('NIST mds2-2525 rejects a changed derived summary', t => {
  const dataset = copyDataset(t);
  const derived = path.join(dataset, 'derived', 'ti64-spot-absorptance-summary-v1.json');
  const bytes = readFileSync(derived);
  bytes[bytes.length - 3] ^= 1;
  writeFileSync(derived, bytes);
  assert.throws(() => nistMds22525AbsorptanceCatalogEntry(path.join(dataset, 'official')).loadDocument(),
    /derived summary SHA-256 mismatch/i);
});

test('NIST mds2-2525 previews, imports and verifies in the persistent source API', async t => {
  const storage = mkdtempSync(path.join(tmpdir(), 'lpbf-nist-2525-source-store-'));
  t.after(() => rmSync(storage, { recursive: true, force: true }));
  const service = new LpbfSourceArchiveService(storage, [nistMds22525AbsorptanceCatalogEntry(officialRoot)]);
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
  assert.equal(preview.artifactCount, 10);
  assert.equal(preview.document.sourceContext.observations.length, 10);
  assert.equal(preview.evidenceStatus, 'unreviewed-source-archive');
  const imported = await (await post('import', { expectedRevision: 0, documentSha256: preview.documentSha256 })).json();
  assert.equal(imported.revision.revision, 1);
  const verified = await (await post('verify')).json();
  assert.equal(verified.artifactIntegrity, 'verified-now');
  assert.equal(verified.datasetId, sourceId);
});
