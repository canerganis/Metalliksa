import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { test, type TestContext } from 'node:test';
import { DatabaseSync } from 'node:sqlite';
import { LpbfRunRepository, validateRunDocument } from '../server/lpbfRunRepository';
import { LpbfNistProxyCampaignService } from '../server/lpbfNistProxyCampaignService';
import { dryRunRunImport, importRun } from '../server/lpbfRunImport';
import { LpbfArtifactStore } from '../server/lpbfArtifactStore';
import { LpbfSourceRepository } from '../server/lpbfSourceRepository';
import { canonicalBuildJobIdentity, canonicalBuildJobMaterialSnapshot } from '../src/utils/lpbfBuildJobIdentity';

const sha = (value: string) => createHash('sha256').update(value).digest('hex');
function capture(runKind?: 'analytical-screening' | 'build-screening' | 'transient-thermal') {
  const result: any = { schemaVersion: 1, requestedMode: 'screening', effectiveMode: 'screening',
    fallbackReason: null, validationStatus: 'unvalidated', productionReady: false, confidence: 'low',
    settings: { backend: 'auto', power_W: 0 }, solver: { id: 'synthetic-contract-test', version: '1' },
    material: { name: 'Synthetic', quality: 'synthetic', source: 'Unit test only' },
    label: 'Screening', regime: 'test', mainRisk: 'test', recommendation: 'test', riskScope: 'test',
    metrics: { width_um: 0, depth_um: 0, length_um: 0 }, assumptions: ['Synthetic only'],
    analyticalComparison: { goldak: { width_um: 0, depth_um: 0, length_um: 0 } },
    provenance: { executionRuntime: null },
    artifacts: [{ path: 'case/empty', size_bytes: 0, sha256: sha('') },
      { path: 'peak-field.npz', size_bytes: 3, sha256: sha('abc') }] };
  if (runKind) {
    result['runKind'] = runKind;
    if (runKind === 'build-screening') {
      result['settings']['jobType'] = 'build-job';
      result['verdict'] = 'screening-only';
    }
    if (runKind === 'analytical-screening') {
      result['settings']['mode'] = 'screening';
      result['resolvedPhysics'] = { transient: false };
    }
  }
  return { schemaVersion: 1, jobId: 'a'.repeat(32), resultJson: JSON.stringify(result),
    inputJson: JSON.stringify(result.settings), materialJson: JSON.stringify(result.material),
    contractStatus: 'legacy-unbound', ...(runKind ? { runKind } : {}) };
}
function fixture(t: TestContext) {
  const root = mkdtempSync(path.join(tmpdir(), 'lpbf-run-test-'));
  const repository = new LpbfRunRepository(path.join(root, 'runs.sqlite'));
  const sources = new LpbfSourceRepository(path.join(root, 'sources.sqlite'));
  const store = new LpbfArtifactStore(path.join(root, 'store'));
  const job = path.join(root, 'job'); mkdirSync(job); mkdirSync(path.join(job, 'case'));
  writeFileSync(path.join(job, 'case/empty'), ''); writeFileSync(path.join(job, 'peak-field.npz'), 'abc');
  writeFileSync(path.join(job, 'result.json'), capture().resultJson);
  const handles = [repository];
  t.after(() => { handles.forEach(r => r.close()); sources.close(); rmSync(root, { recursive: true, force: true }); });
  return { root, repository, sources, store, job, handles };
}

test('dry run writes nothing; full import preserves empty/nested bytes and detached legacy snapshots', async t => {
  const f = fixture(t), raw = capture();
  const preview = await dryRunRunImport(raw, [], f.sources, f.job);
  assert.equal(preview.artifactCount, 2);
  assert.equal(f.repository.get(raw.jobId), null);
  const saved = await importRun(f.repository, f.store, raw, [], f.sources, f.job);
  assert.equal(saved.document.capture.contractStatus, 'legacy-unbound');
  assert.equal(saved.evidenceStatus, 'unvalidated-model');
  raw.materialJson = '{}';
  assert.notEqual(f.repository.get(raw.jobId)!.document.capture.materialJson, '{}');
  assert.equal((await f.store.verify({ sha256: sha(''), byteSize: 0 })).byteSize, 0);
  await assert.rejects(importRun(f.repository, f.store, capture(), [], f.sources, f.job), /conflict/i);
});

test('classification follows captured result identity through preview and import; old v1 records read as unspecified', async t => {
  const f = fixture(t), raw = capture('build-screening');
  writeFileSync(path.join(f.job, 'result.json'), raw.resultJson);
  const preview = await dryRunRunImport(raw, [], f.sources, f.job);
  assert.equal(preview.document.capture.runKind, 'build-screening');
  const saved = await importRun(f.repository, f.store, raw, [], f.sources, f.job);
  assert.equal(saved.runKind, 'build-screening');
  assert.equal(f.repository.get(raw.jobId)?.runKind, 'build-screening');

  const analytical = capture('analytical-screening');
  analytical.jobId = 'd'.repeat(32);
  writeFileSync(path.join(f.job, 'result.json'), analytical.resultJson);
  const analyticalPreview = await dryRunRunImport(analytical, [], f.sources, f.job);
  assert.equal(analyticalPreview.document.capture.runKind, 'analytical-screening');
  const analyticalSaved = await importRun(f.repository, f.store, analytical, [], f.sources, f.job);
  assert.equal(analyticalSaved.runKind, 'analytical-screening');
  assert.equal(f.repository.get(analytical.jobId)?.runKind, 'analytical-screening');

  const misclassified = JSON.parse(analytical.resultJson);
  misclassified.runKind = 'transient-thermal';
  assert.throws(() => validateRunDocument({ schemaVersion: 1, runId: 'c'.repeat(32),
    capture: { ...analytical, jobId: 'c'.repeat(32), resultJson: JSON.stringify(misclassified), runKind: 'transient-thermal' },
    sources: [] }), /classification/i);

  const legacyCapture = capture();
  const legacyResult = JSON.parse(legacyCapture.resultJson); delete legacyResult.runKind;
  legacyCapture.resultJson = JSON.stringify(legacyResult);
  const oldDocument = { schemaVersion: 1 as const, runId: 'b'.repeat(32),
    capture: { ...legacyCapture, jobId: 'b'.repeat(32) }, sources: [] };
  const oldSaved = f.repository.save(oldDocument);
  assert.equal(oldSaved.runKind, 'legacy-unspecified');
  assert.equal(Object.hasOwn(oldSaved.document.capture, 'runKind'), false);
  assert.equal(f.repository.get(oldSaved.document.runId)?.runKind, 'legacy-unspecified');
});

test('build-job archive verifies Python-compatible material snapshot and identity hashes', () => {
  const raw = capture('build-screening'), result = JSON.parse(raw.resultJson);
  Object.assign(result, {
    alloyId: 'in718', modelId: 'lpbf-build-job-v1', solverRevision: 'solver-v1',
    materialPropertySchemaVersion: 1, materialPropertyRevision: 'build-job-effective-properties-v1',
    materialPropertySnapshot: { schemaVersion: 1, alloyId: 'in718',
      thermal: { base: 'Ni', liquidus_C: 1336.0, thermal_expansion_1_K: 13e-6 },
      slicer: { density_gcm3: 8.19 } },
  });
  result.materialPropertySha256 = sha(canonicalBuildJobMaterialSnapshot(result.materialPropertySnapshot));
  const identityPayload = { schemaVersion: 1, alloyId: result.alloyId, modelId: result.modelId,
    solverRevision: result.solverRevision, materialPropertySchemaVersion: result.materialPropertySchemaVersion,
    materialPropertyRevision: result.materialPropertyRevision, materialPropertySha256: result.materialPropertySha256 };
  result.buildJobIdentity = { ...identityPayload,
    sha256: sha(canonicalBuildJobIdentity({ ...identityPayload, sha256: '' })) };
  raw.resultJson = JSON.stringify(result);
  const valid = { schemaVersion: 1, runId: raw.jobId, capture: raw, sources: [] };
  assert.doesNotThrow(() => validateRunDocument(valid));

  result.materialPropertySnapshot.thermal.liquidus_C = 1400.0;
  raw.resultJson = JSON.stringify(result);
  assert.throws(() => validateRunDocument(valid), /material snapshot hash binding/i);

  // V1 archives captured before effective-property snapshots remain readable.
  const legacy = capture('build-screening');
  assert.doesNotThrow(() => validateRunDocument({ schemaVersion: 1, runId: legacy.jobId,
    capture: legacy, sources: [] }));
});

test('reopen and metadata-only restore preserve hashes; tampered rows fail', async t => {
  const f = fixture(t);
  const saved = await importRun(f.repository, f.store, capture(), [], f.sources, f.job);
  const backup = await f.repository.backupMetadata(path.join(f.root, 'backup'));
  assert.equal(backup.artifactPayloadsIncluded, false);
  const restored = new LpbfRunRepository(backup.path, { readOnly: true }); f.handles.push(restored);
  assert.deepEqual(restored.get(saved.document.runId), saved);
  const other = new LpbfRunRepository(f.repository.filename); f.handles.push(other);
  assert.throws(() => other.save(saved.document), /conflict/i);
  const db = new DatabaseSync(f.repository.filename);
  db.exec("UPDATE lpbf_runs SET document_json='{}'"); db.close();
  assert.throws(() => f.repository.get(saved.document.runId), /integrity/i);
});

test('writable v1 database receives the explicit v2 campaign-table migration without changing run rows', t => {
  const root = mkdtempSync(path.join(tmpdir(), 'lpbf-run-v1-migration-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const filename = path.join(root, 'runs.sqlite'), legacy = new DatabaseSync(filename);
  legacy.exec(`CREATE TABLE lpbf_runs (run_id TEXT PRIMARY KEY, document_json TEXT NOT NULL,
    document_sha256 TEXT NOT NULL, created_at TEXT NOT NULL) STRICT;
    CREATE TABLE lpbf_metadata (kind TEXT PRIMARY KEY) STRICT;
    INSERT INTO lpbf_metadata VALUES ('metalliksa-lpbf-runs-v1'); PRAGMA user_version=1;`);
  legacy.close();
  const repository = new LpbfRunRepository(filename);
  try {
    const migrated = new DatabaseSync(filename, { readOnly: true });
    try { assert.equal(migrated.prepare('PRAGMA user_version').get()!.user_version, 2); }
    finally { migrated.close(); }
    assert.deepEqual([...repository.allRuns()], []);
    assert.deepEqual([...repository.allProxyCampaigns()], []);
  } finally { repository.close(); }
});

test('saved proxy campaigns list in creation order and reject broken archived references', async t => {
  const root = mkdtempSync(path.join(tmpdir(), 'lpbf-campaign-list-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const runRoot = path.join(root, 'runs'); mkdirSync(runRoot);
  const filename = path.join(runRoot, 'runs.sqlite');
  const repository = new LpbfRunRepository(filename);
  const sourceBinding = { datasetId: 'nist-fixture', revision: 1, documentSha256: sha('source') };
  const v2SourceBinding = { datasetId: 'nist-amb2022-03-optical-table4-local-v1', revision: 1,
    documentSha256: sha('verified table source'), artifactPath: 'table4-aggregate-v2.json',
    artifactSha256: 'd1b36dfa2e01a3537093c481e249ce52df6b8879c1c67480ddb9aa10799133da',
    artifactSizeBytes: 4321, caseNumber: '0' };
  const runIds = ['a', 'b', 'c'].map(value => value.repeat(32));
  const runs = runIds.map(id => {
    const raw = capture('transient-thermal'); raw.jobId = id;
    return repository.save({ schemaVersion: 1, runId: id, capture: raw, sources: [sourceBinding,
      { datasetId: v2SourceBinding.datasetId, revision: v2SourceBinding.revision,
        documentSha256: v2SourceBinding.documentSha256 }] });
  });
  const campaign = { schemaVersion: 1, kind: 'lpbf-nist-amb2022-03-proxy-campaign',
    campaignId: 'e'.repeat(32), sourceBinding,
    tracks: runs.map(run => ({ runIdentity: { runId: run.document.runId, runDocumentSha256: run.documentSha256 } })) };
  repository.saveProxyCampaign(campaign);
  const v2 = { schemaVersion: 2, kind: 'lpbf-nist-amb2022-03-proxy-campaign', benchmark: 'AMB2022-03-TMPG',
    campaignId: sha(JSON.stringify({ schemaVersion: 2, runIds: runs.map(run => run.document.runId), caseNumber: '0',
      revision: 1, doc: v2SourceBinding.documentSha256 })).slice(0, 32), caseNumber: '0', sourceBinding: v2SourceBinding,
    beamInputDeclaration: { status: 'published-source-declared', definition: 'D4sigma', value_um: 67,
      mappingStatus: 'conditional-ideal-Gaussian', measuredProfileMatched: false, sourceBinding: v2SourceBinding },
    claimBoundary: { resultKind: 'thermal-proxy-screening', validationStatus: 'unvalidated',
      experimentalValidation: false, opticalOperatorMatched: false },
    samplingPlan: { replicateSemantics: 'reproducibility-evidence-not-independent-replicates' },
    tracks: runs.map(run => ({ replicateKind: 'reproducibility-execution',
      runIdentity: { runId: run.document.runId, runDocumentSha256: run.documentSha256 } })) };
  repository.saveProxyCampaign(v2);
  for (const mutate of [
    (doc: any) => { doc.beamInputDeclaration.value_um = 72; },
    (doc: any) => { doc.beamInputDeclaration.sourceBinding.documentSha256 = sha('other'); },
    (doc: any) => { doc.beamInputDeclaration.status = 'measured'; },
    (doc: any) => { doc.beamInputDeclaration.measuredProfileMatched = true; },
    (doc: any) => { doc.beamInputDeclaration.clientNote = 'forged'; },
  ]) {
    const invalid = structuredClone(v2); mutate(invalid);
    assert.throws(() => repository.saveProxyCampaign(invalid), /v2 proxy campaign/i);
  }
  repository.close();

  const service = new LpbfNistProxyCampaignService(runRoot, path.join(root, 'sources'));
  const listed = await service.list();
  assert.equal(listed.length, 2);
  assert.deepEqual(new Set(listed.map(item => item.campaignId)), new Set([campaign.campaignId, v2.campaignId]));
  assert.equal(listed.find(item => item.campaignId === campaign.campaignId)!.documentSha256, sha(JSON.stringify(campaign)));
  assert.equal(listed.find(item => item.campaignId === v2.campaignId)!.documentSha256, sha(JSON.stringify(v2)));

  const db = new DatabaseSync(filename);
  const changed = JSON.parse(String(db.prepare('SELECT document_json FROM lpbf_proxy_campaigns WHERE campaign_id=?').get(campaign.campaignId)!.document_json));
  changed.tracks[0].runIdentity.runDocumentSha256 = 'f'.repeat(64);
  const documentJson = JSON.stringify(changed);
  db.prepare('UPDATE lpbf_proxy_campaigns SET document_json=?, document_sha256=? WHERE campaign_id=?').run(documentJson, sha(documentJson), campaign.campaignId);
  db.close();
  await assert.rejects(service.list(), /reference integrity/i);
});

test('missing/changed bytes and extra files never publish a completed record', async t => {
  const f = fixture(t);
  await dryRunRunImport(capture(), [], f.sources, f.job);
  writeFileSync(path.join(f.job, 'peak-field.npz'), 'bad');
  await assert.rejects(importRun(f.repository, f.store, capture(), [], f.sources, f.job), /integrity/i);
  assert.equal(f.repository.get(capture().jobId), null);
  writeFileSync(path.join(f.job, 'peak-field.npz'), 'abc'); writeFileSync(path.join(f.job, 'extra'), 'x');
  await assert.rejects(dryRunRunImport(capture(), [], f.sources, f.job), /manifest/i);
});

test('exact historical source links survive newer revisions; missing or changed hash fails', async t => {
  const f = fixture(t);
  const source = { schemaVersion: 1, datasetId: 'fixture', materialId: 'in718', processScope: 'unknown',
    source: { url: 'https://example.org/source', citation: 'Synthetic', version: '1', terms: null, termsMissingReason: 'Unknown' },
    artifacts: [{ relativePath: 'raw', sha256: sha('raw'), byteSize: 3, sourceUrl: 'https://example.org/raw' }], sourceContext: null };
  const v1 = f.sources.save(source, 0); source.source.version = '2'; f.sources.save(source, 1);
  const link = { datasetId: 'fixture', revision: 1, documentSha256: v1.documentSha256 };
  const saved = await importRun(f.repository, f.store, capture(), [link], f.sources, f.job);
  assert.deepEqual(saved.document.sources, [link]);
  assert.equal(f.sources.revision('fixture', 1)!.evidenceStatus, 'unreviewed-source-archive');
  for (const bad of [{ ...link, revision: 3 }, { ...link, documentSha256: sha('bad') }])
    await assert.rejects(dryRunRunImport(capture(), [bad], f.sources, f.job), /source/i);
});

test('invalid snapshots, duplicate paths, false bound status and nonfinite values fail', () => {
  const document = () => ({ schemaVersion: 1, runId: 'a'.repeat(32), capture: capture(), sources: [] });
  for (const change of [
    d => { d.capture.inputJson = '{}'; }, d => { d.capture.contractStatus = 'core-v1-bound'; },
    d => { d.runId = '../bad'; }, d => { d.science = 'validated'; },
    d => { const r = JSON.parse(d.capture.resultJson); r.artifacts.push(r.artifacts[0]); d.capture.resultJson = JSON.stringify(r); },
    d => { const r = JSON.parse(d.capture.resultJson); r.artifacts[0].path = '../bad'; d.capture.resultJson = JSON.stringify(r); },
    d => { d.capture.resultJson = d.capture.resultJson.replace('"power_W":0', '"power_W":1e999'); },
  ] as Array<(d: any) => void>) { const d = document(); change(d); assert.throws(() => validateRunDocument(d)); }
});

test('bound snapshots hash Python number spelling verbatim and reject rewritten bytes', () => {
  const raw = capture(), result = JSON.parse(raw.resultJson);
  raw.inputJson = '{"backend":"auto","power_W":0.0}';
  result.solver.id = 'rosenthal+goldak';
  result.coreContract = { schemaVersion: 1, modelId: 'analytical-conduction-screening-v1',
    actualBackend: 'analytical', requestedBackend: 'auto', effectiveMode: 'screening', solverId: 'rosenthal+goldak',
    inputSha256: sha(raw.inputJson), materialSha256: sha(raw.materialJson), evidenceClass: 'unvalidated-model',
    units: { power: 'W', speed: 'mm/s', length: 'um', preheat: 'degC', temperature: 'K', internalLength: 'm', time: 's', energy: 'J', beamDiameter: '1/e2-intensity' },
    resolvedPhysics: { conduction: true, transient: false, latentHeat: false, momentum: false, freeSurface: false, evaporation: false } };
  raw.resultJson = JSON.stringify(result); raw.contractStatus = 'core-v1-bound';
  const document = { schemaVersion: 1, runId: raw.jobId, capture: raw, sources: [] };
  assert.doesNotThrow(() => validateRunDocument(document));
  raw.inputJson = JSON.stringify(result.settings);
  assert.throws(() => validateRunDocument(document), /hash binding/i);
});

test('result file drift after capture is rejected before import', async t => {
  const f = fixture(t);
  await dryRunRunImport(capture(), [], f.sources, f.job);
  writeFileSync(path.join(f.job, 'result.json'), '{}');
  await assert.rejects(importRun(f.repository, f.store, capture(), [], f.sources, f.job), /integrity/i);
  assert.equal(f.repository.get(capture().jobId), null);
});
