import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import { existsSync, mkdtempSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { test, type TestContext } from 'node:test';
import express from 'express';
import { createLpbfRunsRouter } from '../routes/lpbfRuns';
import { LpbfArtifactStore } from '../server/lpbfArtifactStore';
import { LpbfRunArchiveService } from '../server/lpbfRunArchiveService';
import { LpbfRunBundleService } from '../server/lpbfRunBundleService';
import { importRun } from '../server/lpbfRunImport';
import { LpbfRunRepository } from '../server/lpbfRunRepository';
import { LpbfSourceRepository } from '../server/lpbfSourceRepository';
import { createRunBundleTar } from '../server/lpbfRunBundleTar';

const sha = (value: string) => createHash('sha256').update(value).digest('hex');

async function addV2Campaign(f: any) {
  const bytes = readFileSync('data/benchmark/nist-amb2022-03-optical/table4-aggregate-v2.json');
  const artifact = { relativePath: 'table4-aggregate-v2.json', sha256: createHash('sha256').update(bytes).digest('hex'),
    byteSize: bytes.length, sourceUrl: 'https://www.nist.gov/document/am-bench-amb2022-03-measurement-and-result-descriptions-v10' };
  const input = path.join(f.root, 'table4-input'); mkdirSync(input); writeFileSync(path.join(input, artifact.relativePath), bytes);
  await f.sourceStore.putFile(input, artifact.relativePath, artifact);
  const source = { schemaVersion: 1, datasetId: 'nist-amb2022-03-optical-table4-local-v1', materialId: 'in718', processScope: 'bare-plate',
    source: { url: 'https://doi.org/10.18434/mds2-2718', citation: 'NIST AMB2022-03', version: 'Table 4 transcription',
      terms: null, termsMissingReason: 'Unknown' }, artifacts: [artifact], sourceContext: null };
  const revision = f.sources.save(source, 0);
  const sourceLink = { datasetId: source.datasetId, revision: revision.revision, documentSha256: revision.documentSha256 };
  const records = [];
  for (const id of ['b'.repeat(32), 'c'.repeat(32), 'd'.repeat(32)]) {
    const document = structuredClone(f.record.document); document.runId = document.capture.jobId = id; document.sources.push(sourceLink);
    records.push(f.runs.save(document));
  }
  const binding = { ...sourceLink, artifactPath: artifact.relativePath, artifactSha256: artifact.sha256,
    artifactSizeBytes: artifact.byteSize, caseNumber: '0' };
  const tracks = records.map(record => {
    const runIdentity = { runId: record.document.runId, runDocumentSha256: record.documentSha256,
      resultArtifact: { path: 'capture/result.json', sha256: sha(`result-${record.document.runId}`), size_bytes: 100 },
      inputSha256: sha(`input-${record.document.runId}`), materialSha256: sha(`material-${record.document.runId}`),
      materialId: 'in718', materialRevisionSha256: sha(`material-revision-${record.document.runId}`),
      coreContract: { schemaVersion: 1, modelId: 'thermal-v1', solverId: 'solver-v1', actualBackend: 'cpu' } };
    const observations = [4.9, 6.0].map((distance, index) => ({ sectionId: ['x-4p9mm', 'x-6p0mm'][index],
      coordinateFrame: 'scan-start-relative', scanDirection: '+X', distanceFromScanStart_mm: distance,
      surfaceZ_m: 0, status: 'thermal-proxy', geometry: { width_um: 100, depth_um: 80 },
      operator: { sectionOperatorId: 'bare-plate-corridor-accepted-peak-x-linear-section-v1',
        interpolationOperatorId: index ? 'exact-cell-center' : 'linear-interpolation-between-accepted-peak-temperature-planes-v1',
        contourOperatorId: 'linear-liquidus-crossings-between-cell-centers-v1', evidenceClass: 'thermal-proxy-only' },
      provenance: { sourceBinding: structuredClone(binding), runIdentity: structuredClone(runIdentity) } }));
    return { simulatedTrackId: `sim-${record.document.runId}`, experimentalTrackId: null,
      replicateKind: 'reproducibility-execution', runIdentity, observations };
  });
  const campaign = { schemaVersion: 2, kind: 'lpbf-nist-amb2022-03-proxy-campaign', benchmark: 'AMB2022-03-TMPG',
    campaignId: sha(JSON.stringify({ schemaVersion: 2, runIds: records.map(record => record.document.runId), caseNumber: '0',
      revision: binding.revision, doc: binding.documentSha256 })).slice(0, 32), caseNumber: '0', sourceBinding: binding,
    beamInputDeclaration: { status: 'published-source-declared', definition: 'D4sigma', value_um: 67,
      mappingStatus: 'conditional-ideal-Gaussian', measuredProfileMatched: false, sourceBinding: structuredClone(binding) },
    claimBoundary: { resultKind: 'thermal-proxy-screening', validationStatus: 'unvalidated', experimentalValidation: false, opticalOperatorMatched: false },
    samplingPlan: { coordinateFrame: 'scan-start-relative', scanDirection: '+X', sectionPositions_mm: [4.9, 6.0],
      expectedTrackCount: 3, expectedObservationCount: 6,
      replicateSemantics: 'reproducibility-evidence-not-independent-replicates' }, tracks };
  f.runs.saveProxyCampaign(campaign);
}

async function fixture(t: TestContext) {
  const root = mkdtempSync(path.join(tmpdir(), 'lpbf-run-bundle-api-'));
  const runRoot = path.join(root, 'live-runs'), sourceRoot = path.join(root, 'live-sources');
  const bundleRoot = path.join(root, 'bundles');
  mkdirSync(runRoot); mkdirSync(sourceRoot);
  const runs = new LpbfRunRepository(path.join(runRoot, 'runs.sqlite'));
  const sources = new LpbfSourceRepository(path.join(sourceRoot, 'metadata.sqlite'));
  t.after(() => { runs.close(); sources.close(); rmSync(root, { recursive: true, force: true }); });
  const runStore = new LpbfArtifactStore(path.join(runRoot, 'artifacts'));
  const sourceStore = new LpbfArtifactStore(path.join(sourceRoot, 'artifacts'));
  const input = path.join(root, 'input'); mkdirSync(input);
  writeFileSync(path.join(input, 'raw'), 'raw');
  const sourceRef = { relativePath: 'raw', sha256: sha('raw'), byteSize: 3, sourceUrl: 'https://example.org/raw' };
  const source = { schemaVersion: 1, datasetId: 'synthetic', materialId: 'in718', processScope: 'unknown',
    source: { url: 'https://example.org/source', citation: 'Synthetic test only', version: '1', terms: null, termsMissingReason: 'Unknown' },
    artifacts: [sourceRef], sourceContext: { conversion: null } };
  await sourceStore.putFile(input, 'raw', sourceRef);
  const revision = sources.save(source, 0);
  source.source.version = '2'; sources.save(source, 1);
  const job = path.join(root, 'job'); mkdirSync(job);
  writeFileSync(path.join(job, 'field.bin'), 'abc');
  const result = { schemaVersion: 1, runKind: 'analytical-screening', requestedMode: 'screening', effectiveMode: 'screening',
    fallbackReason: null, validationStatus: 'unvalidated', productionReady: false, confidence: 'low',
    settings: { backend: 'auto', mode: 'screening', power_W: 0 },
    resolvedPhysics: { transient: false }, solver: { id: 'synthetic-contract-test', version: '1' },
    material: { name: 'Synthetic', quality: 'synthetic', source: 'Unit test only' },
    label: 'Screening', regime: 'test', mainRisk: 'test', recommendation: 'test', riskScope: 'test',
    metrics: { width_um: 0, depth_um: 0, length_um: 0 }, assumptions: ['Synthetic only'],
    analyticalComparison: { goldak: { width_um: 0, depth_um: 0, length_um: 0 } },
    provenance: { executionRuntime: null }, artifacts: [{ path: 'field.bin', size_bytes: 3, sha256: sha('abc') }] };
  const capture = { schemaVersion: 1, jobId: 'a'.repeat(32), resultJson: JSON.stringify(result),
    inputJson: JSON.stringify(result.settings), materialJson: JSON.stringify(result.material), contractStatus: 'legacy-unbound',
    runKind: 'analytical-screening' as const };
  writeFileSync(path.join(job, 'result.json'), capture.resultJson);
  const record = await importRun(runs, runStore, capture,
    [{ datasetId: 'synthetic', revision: 1, documentSha256: revision.documentSha256 }], sources, job);

  const bundles = new LpbfRunBundleService(runRoot, sourceRoot, bundleRoot);
  const app = express(); app.use(createLpbfRunsRouter(new LpbfRunArchiveService(runRoot, sourceRoot), bundles));
  const server = app.listen(0, '127.0.0.1');
  t.after(() => server.close());
  await new Promise<void>(resolve => server.once('listening', resolve));
  const address = server.address(); assert.ok(address && typeof address !== 'string');
  const endpoint = `http://127.0.0.1:${address.port}/api/lpbf/runs/bundles`;
  const post = async (action: string, body: unknown = {}, headers: Record<string, string> = {}) => {
    const response = await fetch(`${endpoint}/${action}`, { method: 'POST',
      headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(body) });
    return { status: response.status, body: await response.json() };
  };
  return { root, runRoot, sourceRoot, bundleRoot, endpoint, runs, sources, runStore, sourceStore,
    record, sourceRef, bundles, post };
}

test('HTTP export, verify and isolated restore preserve live bytes and historical links', async t => {
  const f = await fixture(t);
  const beforeRuns = readFileSync(path.join(f.runRoot, 'runs.sqlite'));
  const beforeSources = readFileSync(path.join(f.sourceRoot, 'metadata.sqlite'));
  const exported = await f.post('export');
  assert.equal(exported.status, 200);
  assert.match(exported.body.bundleId, /^[0-9a-f]{32}$/);
  assert.equal(exported.body.storage, 'server-local-directory');
  assert.equal(exported.body.manifest.runCount, 1);
  assert.equal(exported.body.manifest.sourceLinkCount, 1);
  assert.equal(JSON.stringify(exported.body).includes(f.root), false);
  const bundleId = exported.body.bundleId as string;
  assert.equal((await f.post(`${bundleId}/verify`)).body.verified, true);
  const restored = await f.post(`${bundleId}/restore`);
  assert.equal(restored.status, 200);
  assert.equal(restored.body.verified, true);
  assert.match(restored.body.restoreId, /^[0-9a-f]{32}$/);
  assert.equal(JSON.stringify(restored.body).includes(f.root), false);
  const restoredRoot = path.join(f.bundleRoot, 'restores', restored.body.restoreId);
  const restoredRuns = new LpbfRunRepository(path.join(restoredRoot, 'runs.sqlite'), { readOnly: true });
  const restoredSources = new LpbfSourceRepository(path.join(restoredRoot, 'sources/metadata.sqlite'), { readOnly: true });
  try {
  assert.deepEqual(restoredRuns.get(f.record.document.runId), f.record);
    assert.equal(restoredRuns.get(f.record.document.runId)?.runKind, 'analytical-screening');
    assert.equal(restoredSources.revision('synthetic', 1)?.documentSha256, f.record.document.sources[0].documentSha256);
    assert.equal(restoredSources.current('synthetic')?.revision, 2);
  } finally { restoredRuns.close(); restoredSources.close(); }
  const restoredStore = new LpbfArtifactStore(path.join(restoredRoot, 'artifacts'), { readOnly: true });
  assert.equal(readFileSync((await restoredStore.verify({ sha256: sha('abc'), byteSize: 3 })).path, 'utf8'), 'abc');
  assert.deepEqual(readFileSync(path.join(f.runRoot, 'runs.sqlite')), beforeRuns);
  assert.deepEqual(readFileSync(path.join(f.sourceRoot, 'metadata.sqlite')), beforeSources);
  assert.equal(readFileSync((await f.sourceStore.verify(f.sourceRef)).path, 'utf8'), 'raw');
});

test('portable tar round-trip verifies, restores in isolation, and exposes restored run records', async t => {
  const f = await fixture(t);
  const beforeRuns = readFileSync(path.join(f.runRoot, 'runs.sqlite'));
  const beforeSources = readFileSync(path.join(f.sourceRoot, 'metadata.sqlite'));
  const exported = await f.post('export'); assert.equal(exported.status, 200);
  const id = exported.body.bundleId as string;
  const downloaded = await fetch(`${f.endpoint}/${id}/download`);
  assert.equal(downloaded.status, 200);
  assert.match(downloaded.headers.get('content-type') ?? '', /application\/x-tar/);
  const bytes = new Uint8Array(await downloaded.arrayBuffer());
  assert.ok(bytes.length > 1024);
  const uploaded = await fetch(`${f.endpoint}/import`, { method: 'POST',
    headers: { 'Content-Type': 'application/x-tar' }, body: bytes });
  assert.equal(uploaded.status, 200);
  const imported = await uploaded.json() as { importId: string; verified: boolean; manifest: { runCount: number; sourceLinkCount: number } };
  assert.match(imported.importId, /^[0-9a-f]{32}$/);
  assert.equal(imported.verified, true);
  assert.equal(imported.manifest.runCount, 1);
  assert.equal(imported.manifest.sourceLinkCount, 1);

  const restoredResponse = await fetch(`${f.endpoint}/imports/${imported.importId}/restore`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
  });
  assert.equal(restoredResponse.status, 200);
  const restored = await restoredResponse.json() as { restoreId: string; verified: boolean };
  assert.match(restored.restoreId, /^[0-9a-f]{32}$/);
  assert.equal(restored.verified, true);
  const listResponse = await fetch(`${f.endpoint}/restores/${restored.restoreId}/runs`);
  assert.equal(listResponse.status, 200);
  assert.deepEqual(await listResponse.json(), [{ runId: f.record.document.runId, createdAt: f.record.createdAt,
    evidenceStatus: 'unvalidated-model', sourceBindingStatus: 'exact-revision-bound', runKind: 'analytical-screening' }]);
  const recordResponse = await fetch(`${f.endpoint}/restores/${restored.restoreId}/runs/${f.record.document.runId}`);
  assert.equal(recordResponse.status, 200);
  const restoredRecord = await recordResponse.json() as typeof f.record;
  assert.deepEqual(restoredRecord.document, f.record.document);
  assert.equal(restoredRecord.documentSha256, f.record.documentSha256);
  const comparisonResponse = await fetch(`${f.endpoint}/restores/${restored.restoreId}/runs/${f.record.document.runId}/nist-comparison`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ caseNumber: '0' }),
  });
  assert.equal(comparisonResponse.status, 200);
  const comparison = await comparisonResponse.json() as { status: string; validationStatus: string; errors: unknown; reasons: string[] };
  assert.equal(comparison.status, 'unavailable');
  assert.equal(comparison.validationStatus, 'unvalidated');
  assert.equal(comparison.errors, null);
  assert.match(comparison.reasons.join(' '), /analytical screening/i);
  assert.deepEqual(readFileSync(path.join(f.runRoot, 'runs.sqlite')), beforeRuns);
  assert.deepEqual(readFileSync(path.join(f.sourceRoot, 'metadata.sqlite')), beforeSources);
});

test('portable HTTP import rejects a recomputed bundle carrying forged v2 evidence flags', async t => {
  const f = await fixture(t); await addV2Campaign(f);
  const exported = await f.bundles.export();
  const bundlePath = path.join(f.bundleRoot, 'exports', exported.bundleId);
  const db = new DatabaseSync(path.join(bundlePath, 'runs.sqlite'));
  const row = db.prepare('SELECT campaign_id, document_json FROM lpbf_proxy_campaigns').all()
    .map(value => ({ ...value, document: JSON.parse(String(value.document_json)) }))
    .find(value => value.document.schemaVersion === 2)!;
  row.document.claimBoundary.opticalOperatorMatched = true;
  const documentJson = JSON.stringify(row.document);
  db.prepare('UPDATE lpbf_proxy_campaigns SET document_json=?, document_sha256=? WHERE campaign_id=?')
    .run(documentJson, sha(documentJson), row.campaign_id);
  db.close();
  const manifestPath = path.join(bundlePath, 'bundle.json'), manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  const metadata = readFileSync(path.join(bundlePath, 'runs.sqlite'));
  manifest.metadata = { sha256: createHash('sha256').update(metadata).digest('hex'), byteSize: metadata.length };
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  const chunks: Buffer[] = [];
  for await (const chunk of await createRunBundleTar(bundlePath)) chunks.push(Buffer.from(chunk));
  const response = await fetch(`${f.endpoint}/import`, { method: 'POST',
    headers: { 'Content-Type': 'application/x-tar' }, body: Buffer.concat(chunks) });
  assert.equal(response.status, 409);
  assert.match((await response.json()).error, /integrity verification failed/i);
  assert.deepEqual(readdirSync(path.join(f.bundleRoot, 'imports')), []);
});

test('HTTP rejects corrupted bundles before restore and accepts no filesystem path', async t => {
  const f = await fixture(t);
  const exported = await f.post('export'); assert.equal(exported.status, 200);
  const id = exported.body.bundleId as string;
  assert.equal((await f.post('export', { destination: f.runRoot })).status, 400);
  assert.equal((await f.post(`${id}/restore`, { destination: f.runRoot })).status, 400);
  assert.equal((await f.post('..%2F..%2Flive-runs/verify')).status, 400);
  assert.equal((await f.post(`${'f'.repeat(32)}/verify`)).status, 404);
  writeFileSync(path.join(f.bundleRoot, 'exports', id, 'bundle.json'), 'bad');
  assert.equal((await f.post(`${id}/verify`)).status, 409);
  assert.equal((await f.post(`${id}/restore`)).status, 409);
  assert.equal(existsSync(path.join(f.bundleRoot, 'restores')), false);
  assert.equal(existsSync(path.join(f.runRoot, 'bundle.json')), false);
  assert.deepEqual(f.runs.get(f.record.document.runId), f.record);
});

test('generated ID collisions cannot overwrite a bundle or restored copy', async t => {
  const f = await fixture(t);
  const id = 'b'.repeat(32);
  const fixed = new LpbfRunBundleService(f.runRoot, f.sourceRoot, f.bundleRoot, () => id);
  const first = await fixed.export();
  const original = readFileSync(path.join(f.bundleRoot, 'exports', id, 'bundle.json'));
  await assert.rejects(fixed.export(), /already exists/i);
  const restored = await fixed.restore(first.bundleId);
  assert.equal(restored.restoreId, id);
  await assert.rejects(fixed.restore(first.bundleId), /already exists/i);
  assert.deepEqual(readFileSync(path.join(f.bundleRoot, 'exports', id, 'bundle.json')), original);
  assert.deepEqual(f.runs.get(f.record.document.runId), f.record);
});

test('bundle API retains router write guards and disjoint storage roots', async t => {
  const f = await fixture(t);
  assert.equal((await f.post(`${'f'.repeat(32)}/verify`)).status, 404);
  assert.throws(() => new LpbfRunBundleService(f.runRoot, f.sourceRoot, path.join(f.runRoot, 'bundles')),
    /separate from live/i);
  const prior = process.env.METALLIKSA_READ_ONLY;
  process.env.METALLIKSA_READ_ONLY = 'true';
  try {
    assert.equal((await f.post('export')).status, 403);
    assert.equal((await fetch(`${f.endpoint}/import`, { method: 'POST',
      headers: { 'Content-Type': 'application/x-tar' }, body: Buffer.alloc(1024) })).status, 403);
  }
  finally {
    if (prior === undefined) delete process.env.METALLIKSA_READ_ONLY;
    else process.env.METALLIKSA_READ_ONLY = prior;
  }
  assert.equal((await f.post('export', {}, { Origin: 'https://evil.example' })).status, 403);
  assert.equal((await fetch(`${f.endpoint}/import`, { method: 'POST',
    headers: { 'Content-Type': 'application/x-tar', Origin: 'https://evil.example' }, body: Buffer.alloc(1024) })).status, 403);
  assert.equal(existsSync(f.bundleRoot), false);
});
