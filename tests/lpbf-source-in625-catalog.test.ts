import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import express from 'express';
import { createLpbfSourcesRouter } from '../routes/lpbfSources';
import { LpbfSourceArchiveService } from '../server/lpbfSourceArchiveService';
import { in625BareplateScreeningCatalogEntry } from '../server/lpbfSourceCatalog';

const sourceRoot = path.resolve('data/benchmark/in625-bareplate-screening');
const datasetId = 'in625-bareplate-screening-local-v1';
const thermalPath = 'in625-thermal-snapshot-v1.json';
const densityPath = 'density-assumption-v1.json';
const sha = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex');

test('IN625 catalog pins exact generated thermal snapshot and separate fixed density assumption', () => {
  const manifest = JSON.parse(readFileSync(path.join(sourceRoot, 'manifest.json'), 'utf8'));
  const context = JSON.parse(readFileSync(path.join(sourceRoot, 'source-context.json'), 'utf8'));
  const thermalBytes = readFileSync(path.join(sourceRoot, thermalPath));
  const densityBytes = readFileSync(path.join(sourceRoot, densityPath));
  const thermal = JSON.parse(thermalBytes.toString('utf8'));
  const density = JSON.parse(densityBytes.toString('utf8'));
  const generated = JSON.parse(execFileSync('python', ['-c',
    'import json; from python.in625_thermal_material import in625_lpbf_thermal_snapshot; print(json.dumps(in625_lpbf_thermal_snapshot(), ensure_ascii=False, allow_nan=False))'],
    { cwd: path.resolve('.'), encoding: 'utf8' }));
  assert.deepEqual(thermal, generated);
  assert.equal(thermal.materialRevisionSha256, 'f47b07e4c8288b8c7177001f069a254be3410bace43ad5ea2f73168ac4466f07');
  assert.equal(manifest.files[0].bytes, thermalBytes.length);
  assert.equal(manifest.files[0].sha256, sha(thermalBytes));
  assert.equal(manifest.files[1].bytes, densityBytes.length);
  assert.equal(manifest.files[1].sha256, sha(densityBytes));
  assert.equal(density.density_kg_m3, 8440);
  assert.equal(density.kind, 'fixed-supplier-bulletin-density-assumption');
  assert.match(density.assumption, /not measured on, or matched to, a material lot/i);
  assert.equal(context.evidence_status, 'unreviewed-source-archive');
  assert.equal(context.thermal_model.artifact_is_raw_publisher_data, false);
  assert.equal(context.density_assumption.fixed, true);
  assert.equal(context.density_assumption.lot_matched, false);
  assert.equal(context.density_assumption.measured_for_this_model, false);
  assert.match(context.thermal_model.scope_limit, /not P7 full-transient admission, build-job support/i);

  const document = in625BareplateScreeningCatalogEntry(sourceRoot).loadDocument() as any;
  assert.equal(document.datasetId, datasetId);
  assert.equal(document.materialId, 'in625');
  assert.equal(document.sourceContext.evidence_status, 'unreviewed-source-archive');
  assert.deepEqual(document.artifacts.map((item: any) => [item.relativePath, item.sha256]), [
    [thermalPath, sha(thermalBytes)], [densityPath, sha(densityBytes)],
  ]);
  assert.ok(new LpbfSourceArchiveService().catalog().sources.some(item => item.datasetId === datasetId));
});

test('IN625 catalog rejects modified artifact bytes, changed revision and inflated admission claims', t => {
  const directory = mkdtempSync(path.join(tmpdir(), 'lpbf-in625-catalog-'));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  for (const name of ['manifest.json', 'source-context.json', thermalPath, densityPath]) {
    writeFileSync(path.join(directory, name), readFileSync(path.join(sourceRoot, name)));
  }
  const entry = in625BareplateScreeningCatalogEntry(directory);
  assert.doesNotThrow(() => entry.loadDocument());
  writeFileSync(path.join(directory, thermalPath), Buffer.concat([readFileSync(path.join(directory, thermalPath)), Buffer.from(' ')]));
  assert.throws(() => entry.loadDocument(), /size mismatch|hash mismatch/i);
  writeFileSync(path.join(directory, thermalPath), readFileSync(path.join(sourceRoot, thermalPath)));
  const context = JSON.parse(readFileSync(path.join(directory, 'source-context.json'), 'utf8'));
  context.density_assumption.lot_matched = true;
  writeFileSync(path.join(directory, 'source-context.json'), JSON.stringify(context));
  assert.throws(() => entry.loadDocument(), /content identity mismatch/i);
});

test('IN625 screening source previews, imports and verifies as an unreviewed revision', async t => {
  const storage = mkdtempSync(path.join(tmpdir(), 'lpbf-in625-store-'));
  t.after(() => rmSync(storage, { recursive: true, force: true }));
  const service = new LpbfSourceArchiveService(storage, [in625BareplateScreeningCatalogEntry(sourceRoot)]);
  const app = express(); app.use(createLpbfSourcesRouter(service));
  const server = app.listen(0, '127.0.0.1');
  await new Promise<void>(resolve => server.once('listening', resolve));
  t.after(() => new Promise<void>(resolve => server.close(() => resolve())));
  const base = `http://127.0.0.1:${(server.address() as { port: number }).port}/api/lpbf/sources`;
  const post = (suffix: string, body = {}) => fetch(`${base}/${datasetId}/${suffix}`,
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const catalog = await (await fetch(base)).json();
  assert.deepEqual(catalog.sources.map((item: any) => item.datasetId), [datasetId]);
  const previewResponse = await post('preview');
  assert.equal(previewResponse.status, 200);
  const preview = await previewResponse.json();
  assert.equal(preview.expectedRevision, 0);
  assert.equal(preview.artifactCount, 2);
  assert.equal(preview.evidenceStatus, 'unreviewed-source-archive');
  assert.equal(preview.document.materialId, 'in625');
  assert.equal(preview.document.sourceContext.density_assumption.lot_matched, false);
  const importedResponse = await post('import', { expectedRevision: 0, documentSha256: preview.documentSha256 });
  assert.equal(importedResponse.status, 200);
  const imported = await importedResponse.json();
  assert.equal(imported.revision.revision, 1);
  assert.equal(imported.revision.evidenceStatus, 'unreviewed-source-archive');
  assert.equal(imported.revision.document.materialId, 'in625');
  assert.equal((await post('import', { expectedRevision: 0, documentSha256: preview.documentSha256 })).status, 409);
  const verifiedResponse = await post('verify');
  assert.equal(verifiedResponse.status, 200);
  const verified = await verifiedResponse.json();
  assert.equal(verified.revision, 1);
  assert.equal(verified.artifactIntegrity, 'verified-now');
  assert.equal(verified.evidenceStatus, 'unreviewed-source-archive');
});
