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
import { nistMds22525AbsorptanceCatalogEntry } from '../server/lpbfSourceCatalog';
import type { LpbfSourceDocument } from '../src/types/lpbfSource';
import { SourceConditions } from '../src/components/LpbfSourceArchivePanel';

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
  assert.match(ti64[0].comparable_reason, /screening comparison/);
  assert.match(ti64[1].comparable_reason, /does not solve keyhole geometry/);
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
  const measurement = document.sourceContext.measurement;
  assert.match(measurement.beam_diameter_definition, /1\/e\^2 diameter 122\.5 ± 3\.0 µm/);
  assert.equal(measurement.temperature_conversion, null);
  assert.match(measurement.temperature_conversion_missing_reason, /^Not applicable: integrating-sphere/);
  assert.match(measurement.repeat_group_rule, /spot solidification rate is the average of 2 measurements/);
  assert.equal(find(/spot, solidification/)?.n, 2);
  assert.ok(aluminium.filter(row => !/spot, solidification/.test(row.label)).every(row => row.n === 3));
  assert.ok(aluminium.every(row => row.derived_locally === false));
  const nerdm = (document.sourceContext.locally_derived_artifacts as any[])
    .find(item => item.path === 'official/nerdm-record-mds2-2525.json');
  assert.equal(nerdm?.published_by_nist, false);
  assert.match(nerdm.note, /local re-serialisation/);
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

test('NIST mds2-2525 lists out-of-scope record components as not archived, never as artifacts', () => {
  const document = nistMds22525AbsorptanceCatalogEntry(officialRoot).loadDocument() as any;
  const record = JSON.parse(readFileSync(path.join(officialRoot, 'nerdm-record-mds2-2525.json'), 'utf8'));
  const notArchived = document.sourceContext.not_archived_components.components as any[];
  const archived = new Set((JSON.parse(readFileSync(path.join(officialRoot, 'manifest.json'), 'utf8')).files as any[])
    .map(item => item.path));
  const absent = new Set((document.sourceContext.unavailable_files as any[]).map(item => item.file));
  const recordFiles = (record.components as any[]).filter(item => item.filepath);
  assert.equal(recordFiles.length, archived.size - 1 + absent.size + notArchived.length);
  for (const component of recordFiles) {
    if (archived.has(component.filepath) || absent.has(component.filepath)) continue;
    const listed = notArchived.find(item => item.path === component.filepath);
    assert.ok(listed, component.filepath);
    assert.equal(listed.sha256, component.checksum.hash);
    assert.equal(listed.bytes, component.size);
  }
  assert.ok(document.artifacts.every((item: any) => !notArchived.some(entry => item.relativePath.endsWith(entry.path))));
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

test('NIST mds2-2525 source UI shows absorptance rows by material, without camera or optical-table claims', () => {
  const document = nistMds22525AbsorptanceCatalogEntry(officialRoot).loadDocument() as LpbfSourceDocument;
  const markup = renderToStaticMarkup(React.createElement(SourceConditions, { document, preview: true }));
  assert.doesNotMatch(markup, /Raw camera signal|Published optical measurements/);
  assert.match(markup, /NIST measured laser absorptance \(integrating sphere\)/);
  assert.match(markup, /This is not validation/);
  assert.match(markup, /Published and locally windowed absorptance observations/);
  assert.match(markup, /Ti-6Al-4V rows only; aluminium NIST SRM 1241c/);
  assert.match(markup, /32\.47 % ± 1\.451 %/);
  assert.match(markup, /88\.8 micrometer ± 0\.4 micrometer/);
  assert.match(markup, /Derived locally, window 0\.05–0\.8 ms from first laser-on/);
  assert.match(markup, /1\/e\^2 diameter 122\.5/);
  assert.match(markup, /Not applicable: integrating-sphere/);
  assert.doesNotMatch(markup, /Temperature conversion<\/dt><dd class="mt-1">Unknown|Beam diameter convention<\/dt><dd class="mt-1">Unknown/);
  const table = markup.slice(markup.indexOf('Published and locally windowed absorptance observations'));
  const rows = [...table.slice(0, table.indexOf('</table>')).matchAll(/<tr class="border-b border-slate-800">(.*?)<\/tr>/g)].map(match => match[1]);
  assert.equal(rows.length, 10);
  assert.equal(rows.filter(row => row.includes('aluminium (NIST SRM 1241c)')).length, 8);
  assert.equal(rows.filter(row => row.includes('Ti-6Al-4V (NIST SRM 654b)')).length, 2);
  for (const row of rows) {
    const cells = [...row.matchAll(/<td[^>]*>(.*?)<\/td>/g)].map(match => match[1]);
    assert.equal(cells.length, 5);
    assert.ok(cells.every(cell => !/^Unknown/.test(cell)), row);
  }
  assert.ok(rows.filter(row => row.includes('SRM 1241c')).every(row => row.includes('NIST-published table value')));
});
