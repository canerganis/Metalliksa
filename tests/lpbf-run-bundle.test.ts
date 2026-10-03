import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync, unlinkSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { test, type TestContext } from 'node:test';
import { DatabaseSync } from 'node:sqlite';
import { LpbfRunRepository } from '../server/lpbfRunRepository';
import { LpbfSourceRepository } from '../server/lpbfSourceRepository';
import { LpbfArtifactStore } from '../server/lpbfArtifactStore';
import { importRun } from '../server/lpbfRunImport';
import { backupRunBundle, restoreRunBundle, verifyRunBundle } from '../server/lpbfRunBundle';
import { createRunBundleTar } from '../server/lpbfRunBundleTar';
import { LpbfRunBundleService } from '../server/lpbfRunBundleService';

const sha = (value: string) => createHash('sha256').update(value).digest('hex');
function bundleV2Campaign(runRecords: any[], sourceBinding: any) {
  const tracks = runRecords.map(record => {
    const runIdentity = { runId: record.document.runId, runDocumentSha256: record.documentSha256,
      resultArtifact: { path: 'capture/result.json', sha256: sha(`result-${record.document.runId}`), size_bytes: 100 },
      inputSha256: sha(`input-${record.document.runId}`), materialSha256: sha(`material-${record.document.runId}`),
      materialId: 'in718', materialRevisionSha256: sha(`revision-${record.document.runId}`),
      coreContract: { schemaVersion: 1, modelId: 'thermal-v1', solverId: 'solver-v1', actualBackend: 'cpu' } };
    const observations = [4.9, 6.0].map((distance, index) => ({ sectionId: ['x-4p9mm', 'x-6p0mm'][index],
      coordinateFrame: 'scan-start-relative', scanDirection: '+X', distanceFromScanStart_mm: distance,
      surfaceZ_m: 0, status: 'thermal-proxy', geometry: { width_um: 100, depth_um: 80 },
      operator: { sectionOperatorId: 'bare-plate-corridor-accepted-peak-x-linear-section-v1',
        interpolationOperatorId: index ? 'exact-cell-center' : 'linear-interpolation-between-accepted-peak-temperature-planes-v1',
        contourOperatorId: 'linear-liquidus-crossings-between-cell-centers-v1', evidenceClass: 'thermal-proxy-only' },
      provenance: { sourceBinding: structuredClone(sourceBinding), runIdentity: structuredClone(runIdentity) } }));
    return { simulatedTrackId: `sim-${record.document.runId}`, experimentalTrackId: null,
      replicateKind: 'reproducibility-execution', runIdentity, observations };
  });
  const campaign = { schemaVersion: 2, kind: 'lpbf-nist-amb2022-03-proxy-campaign', benchmark: 'AMB2022-03-TMPG',
    campaignId: sha(JSON.stringify({ schemaVersion: 2, runIds: runRecords.map(run => run.document.runId), caseNumber: '0',
      revision: sourceBinding.revision, doc: sourceBinding.documentSha256 })).slice(0, 32), caseNumber: '0',
    sourceBinding: structuredClone(sourceBinding), beamInputDeclaration: { status: 'published-source-declared', definition: 'D4sigma',
      value_um: 67, mappingStatus: 'conditional-ideal-Gaussian', measuredProfileMatched: false,
      sourceBinding: structuredClone(sourceBinding) },
    claimBoundary: { resultKind: 'thermal-proxy-screening', validationStatus: 'unvalidated',
      experimentalValidation: false, opticalOperatorMatched: false },
    samplingPlan: { coordinateFrame: 'scan-start-relative', scanDirection: '+X', sectionPositions_mm: [4.9, 6.0],
      expectedTrackCount: 3, expectedObservationCount: 6,
      replicateSemantics: 'reproducibility-evidence-not-independent-replicates' }, tracks };
  return campaign;
}
async function fixture(t: TestContext) {
  const root = mkdtempSync(path.join(tmpdir(), 'lpbf-run-bundle-'));
  const runs = new LpbfRunRepository(path.join(root, 'runs.sqlite'));
  const sources = new LpbfSourceRepository(path.join(root, 'sources.sqlite'));
  t.after(() => { runs.close(); sources.close(); rmSync(root, { recursive: true, force: true }); });
  const runStore = new LpbfArtifactStore(path.join(root, 'run-store'));
  const sourceStore = new LpbfArtifactStore(path.join(root, 'source-store'));
  const input = path.join(root, 'input'); mkdirSync(input);
  writeFileSync(path.join(input, 'raw'), 'raw');
  const sourceRef = { relativePath: 'raw', sha256: sha('raw'), byteSize: 3, sourceUrl: 'https://example.org/raw' };
  const source = { schemaVersion: 1, datasetId: 'synthetic', materialId: 'in718', processScope: 'unknown',
    source: { url: 'https://example.org/source', citation: 'Synthetic test only', version: '1', terms: null, termsMissingReason: 'Unknown' },
    artifacts: [sourceRef], sourceContext: { conversion: null } };
  await sourceStore.putFile(input, 'raw', sourceRef);
  const v1 = sources.save(source, 0); source.source.version = '2'; sources.save(source, 1);
  const job = path.join(root, 'job'); mkdirSync(job); mkdirSync(path.join(job, 'case'));
  writeFileSync(path.join(job, 'case/empty'), ''); writeFileSync(path.join(job, 'peak-field.npz'), 'abc');
  const result = { schemaVersion: 1, requestedMode: 'screening', effectiveMode: 'screening',
    fallbackReason: null, validationStatus: 'unvalidated', productionReady: false, confidence: 'low',
    settings: { backend: 'auto', power_W: 0 }, solver: { id: 'synthetic-contract-test', version: '1' },
    material: { name: 'Synthetic', quality: 'synthetic', source: 'Unit test only' },
    label: 'Screening', regime: 'test', mainRisk: 'test', recommendation: 'test', riskScope: 'test',
    metrics: { width_um: 0, depth_um: 0, length_um: 0 }, assumptions: ['Synthetic only'],
    analyticalComparison: { goldak: { width_um: 0, depth_um: 0, length_um: 0 } },
    provenance: { executionRuntime: null },
    artifacts: [{ path: 'case/empty', size_bytes: 0, sha256: sha('') }, { path: 'peak-field.npz', size_bytes: 3, sha256: sha('abc') }] };
  const capture = { schemaVersion: 1, jobId: 'a'.repeat(32), resultJson: JSON.stringify(result),
    inputJson: JSON.stringify(result.settings), materialJson: JSON.stringify(result.material), contractStatus: 'legacy-unbound' };
  writeFileSync(path.join(job, 'result.json'), capture.resultJson);
  const link = { datasetId: 'synthetic', revision: 1, documentSha256: v1.documentSha256 };
  const record = await importRun(runs, runStore, capture, [link], sources, job);
  const bundle = path.join(root, 'bundle');
  const backup = () => backupRunBundle(runs, runStore, sources, sourceStore, bundle);
  return { root, runs, sources, runStore, sourceStore, record, sourceRef, bundle, backup };
}

async function addV2Campaign(f: Awaited<ReturnType<typeof fixture>>) {
  const table4Bytes = readFileSync('data/benchmark/nist-amb2022-03-optical/table4-aggregate-v2.json');
  const table4Artifact = { relativePath: 'table4-aggregate-v2.json',
    sha256: createHash('sha256').update(table4Bytes).digest('hex'), byteSize: table4Bytes.length,
    sourceUrl: 'https://www.nist.gov/document/am-bench-amb2022-03-measurement-and-result-descriptions-v10' };
  const input = path.join(f.root, 'table4-input'); mkdirSync(input);
  writeFileSync(path.join(input, table4Artifact.relativePath), table4Bytes);
  await f.sourceStore.putFile(input, table4Artifact.relativePath, table4Artifact);
  const table4Source = { schemaVersion: 1, datasetId: 'nist-amb2022-03-optical-table4-local-v1', materialId: 'in718',
    processScope: 'bare-plate', source: { url: 'https://doi.org/10.18434/mds2-2718', citation: 'NIST AMB2022-03',
      version: 'Table 4 transcription', terms: null, termsMissingReason: 'Unknown' }, artifacts: [table4Artifact], sourceContext: null };
  const revision = f.sources.save(table4Source, 0);
  const table4Link = { datasetId: table4Source.datasetId, revision: revision.revision, documentSha256: revision.documentSha256 };
  const runRecords = [];
  for (const id of ['b'.repeat(32), 'c'.repeat(32), 'd'.repeat(32)]) {
    const document = structuredClone(f.record.document);
    document.runId = document.capture.jobId = id;
    document.sources.push(table4Link);
    runRecords.push(f.runs.save(document));
  }
  const binding = { ...table4Link, artifactPath: table4Artifact.relativePath, artifactSha256: table4Artifact.sha256,
    artifactSizeBytes: table4Artifact.byteSize, caseNumber: '0' };
  const campaign = bundleV2Campaign(runRecords, binding);
  f.runs.saveProxyCampaign(campaign);
  return campaign;
}

function mutateBundledV2Campaign(bundle: string, mutate: (document: any) => void) {
  const db = new DatabaseSync(path.join(bundle, 'runs.sqlite'));
  const row = db.prepare('SELECT document_json FROM lpbf_proxy_campaigns').all()
    .find(item => JSON.parse(String(item.document_json)).schemaVersion === 2)!;
  const document = JSON.parse(String(row.document_json)); mutate(document);
  document.campaignId = sha(JSON.stringify({ schemaVersion: 2,
    runIds: document.tracks.map((track: any) => track.runIdentity.runId), caseNumber: document.caseNumber,
    revision: document.sourceBinding.revision, doc: document.sourceBinding.documentSha256 })).slice(0, 32);
  const documentJson = JSON.stringify(document);
  db.prepare('UPDATE lpbf_proxy_campaigns SET campaign_id=?, document_json=?, document_sha256=? WHERE campaign_id=?')
    .run(document.campaignId, documentJson, sha(documentJson), JSON.parse(String(row.document_json)).campaignId);
  db.close();
  const manifestPath = path.join(bundle, 'bundle.json'), manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  const metadata = readFileSync(path.join(bundle, 'runs.sqlite'));
  manifest.metadata = { sha256: createHash('sha256').update(metadata).digest('hex'), byteSize: metadata.length };
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
}

test('full bundle independently restores exact run and historical source revision with all bytes', async t => {
  const f = await fixture(t), manifest = await f.backup();
  assert.equal(manifest.runCount, 1); assert.equal(manifest.artifactCount, 2);
  assert.equal(manifest.sourceLinkCount, 1);
  writeFileSync((await f.runStore.verify({ sha256: sha('abc'), byteSize: 3 })).path, 'bad');
  writeFileSync((await f.sourceStore.verify(f.sourceRef)).path, 'bad');
  const destination = path.join(f.root, 'restored'); await restoreRunBundle(f.bundle, destination);
  const runs = new LpbfRunRepository(path.join(destination, 'runs.sqlite'), { readOnly: true });
  const sources = new LpbfSourceRepository(path.join(destination, 'sources/metadata.sqlite'), { readOnly: true });
  try {
    assert.deepEqual(runs.get(f.record.document.runId), f.record);
    assert.equal(sources.current('synthetic')!.revision, 2);
    assert.equal(sources.revision('synthetic', 1)!.documentSha256, f.record.document.sources[0].documentSha256);
    assert.equal(sources.revision('synthetic', 1)!.evidenceStatus, 'unreviewed-source-archive');
    assert.equal(sources.current('synthetic')!.document.sourceContext!.conversion, null);
  } finally { runs.close(); sources.close(); }
  const store = new LpbfArtifactStore(path.join(destination, 'artifacts'), { readOnly: true });
  assert.equal(readFileSync((await store.verify({ sha256: sha('abc'), byteSize: 3 })).path, 'utf8'), 'abc');
  await store.verify({ sha256: sha(''), byteSize: 0 });
  const before = readFileSync(path.join(destination, 'bundle.json'));
  await assert.rejects(restoreRunBundle(f.bundle, destination), /exist/i);
  assert.deepEqual(readFileSync(path.join(destination, 'bundle.json')), before);
});

test('bundle snapshots and restores immutable six-proxy campaign run references', async t => {
  const f = await fixture(t);
  const table4Path = 'data/benchmark/nist-amb2022-03-optical/table4-aggregate-v2.json';
  const table4Bytes = readFileSync(table4Path);
  const table4Artifact = { relativePath: 'table4-aggregate-v2.json',
    sha256: createHash('sha256').update(table4Bytes).digest('hex'), byteSize: table4Bytes.length,
    sourceUrl: 'https://www.nist.gov/document/am-bench-amb2022-03-measurement-and-result-descriptions-v10' };
  const table4Input = path.join(f.root, 'table4-input'); mkdirSync(table4Input);
  writeFileSync(path.join(table4Input, table4Artifact.relativePath), table4Bytes);
  await f.sourceStore.putFile(table4Input, table4Artifact.relativePath, table4Artifact);
  const table4Source = { schemaVersion: 1, datasetId: 'nist-amb2022-03-optical-table4-local-v1', materialId: 'in718',
    processScope: 'bare-plate', source: { url: 'https://doi.org/10.18434/mds2-2718', citation: 'NIST AMB2022-03',
      version: 'Table 4 transcription', terms: null, termsMissingReason: 'Unknown' },
    artifacts: [table4Artifact], sourceContext: null };
  const table4Revision = f.sources.save(table4Source, 0);
  const table4Link = { datasetId: table4Source.datasetId, revision: table4Revision.revision,
    documentSha256: table4Revision.documentSha256 };
  const runRecords = [];
  for (const id of ['b'.repeat(32), 'c'.repeat(32), 'd'.repeat(32)]) {
    const document = structuredClone(f.record.document);
    document.runId = document.capture.jobId = id;
    document.sources.push(table4Link);
    runRecords.push(f.runs.save(document));
  }
  const binding = { datasetId: 'synthetic', revision: 1, documentSha256: f.record.document.sources[0].documentSha256,
    artifactPath: 'raw', artifactSha256: sha('raw'), artifactSizeBytes: 3, caseNumber: '2.1' };
  const campaign = { schemaVersion: 1, kind: 'lpbf-nist-amb2022-03-proxy-campaign', campaignId: '9'.repeat(32),
    benchmark: 'AMB2022-03-TMPG', caseNumber: '2.1', sourceBinding: binding, tracks: runRecords.map(record => ({
      runIdentity: { runId: record.document.runId, runDocumentSha256: record.documentSha256 },
    })) };
  f.runs.saveProxyCampaign(campaign);
  const v2Binding = { ...table4Link, artifactPath: table4Artifact.relativePath, artifactSha256: table4Artifact.sha256,
    artifactSizeBytes: table4Artifact.byteSize, caseNumber: '0' };
  const v2 = bundleV2Campaign(runRecords, v2Binding);
  f.runs.saveProxyCampaign(v2);
  const manifest = await f.backup();
  assert.equal(manifest.schemaVersion, 2);
  assert.equal(manifest.campaignCount, 2);
  const destination = path.join(f.root, 'campaign-restored');
  await restoreRunBundle(f.bundle, destination);
  const restored = new LpbfRunRepository(path.join(destination, 'runs.sqlite'), { readOnly: true });
  try {
    const record = restored.getProxyCampaign(campaign.campaignId)!;
    assert.deepEqual(record.document, campaign);
    assert.deepEqual(restored.getProxyCampaign(v2.campaignId)!.document, v2);
    assert.equal([...restored.allProxyCampaigns()].length, 2);
  } finally { restored.close(); }

  const completion = path.join(f.bundle, 'bundle.json');
  const original = readFileSync(completion);
  const legacy = JSON.parse(original.toString('utf8'));
  legacy.schemaVersion = 1; delete legacy.campaignCount;
  writeFileSync(completion, JSON.stringify(legacy));
  await assert.rejects(verifyRunBundle(f.bundle), /counts mismatch/i);
  const rejected = path.join(f.root, 'legacy-campaign-rejected');
  await assert.rejects(restoreRunBundle(f.bundle, rejected), /counts mismatch/i);
  assert.equal(existsSync(rejected), false);
  writeFileSync(completion, original);

  const invalid = structuredClone(campaign);
  invalid.campaignId = '8'.repeat(32);
  invalid.tracks[0].runIdentity.runDocumentSha256 = sha('mixed provenance');
  assert.throws(() => f.runs.saveProxyCampaign(invalid), /run reference mismatch/i);
});

test('recomputed v2 campaign and bundle hashes cannot conceal forged claims or incomplete nested data', async t => {
  const cases: Array<[string, (document: any) => void]> = [
    ['true evidence flags', document => { document.claimBoundary.experimentalValidation = true; }],
    ['validated label', document => { document.claimBoundary.validationStatus = 'validated'; }],
    ['missing observations', document => { delete document.tracks[0].observations; }],
    ['extra nested field', document => { document.tracks[0].observations[0].geometry.clientNote = 'forged'; }],
  ];
  for (const [label, mutate] of cases) {
    const f = await fixture(t);
    await addV2Campaign(f);
    await f.backup();
    const db = new DatabaseSync(path.join(f.bundle, 'runs.sqlite'));
    const row = db.prepare('SELECT document_json FROM lpbf_proxy_campaigns').all()
      .find(item => JSON.parse(String(item.document_json)).schemaVersion === 2)!;
    const document = JSON.parse(String(row.document_json)); mutate(document);
    const documentJson = JSON.stringify(document);
    db.prepare('UPDATE lpbf_proxy_campaigns SET document_json=?, document_sha256=? WHERE campaign_id=?')
      .run(documentJson, sha(documentJson), document.campaignId);
    db.close();
    const manifestPath = path.join(f.bundle, 'bundle.json');
    const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
    const metadata = readFileSync(path.join(f.bundle, 'runs.sqlite'));
    manifest.metadata = { sha256: createHash('sha256').update(metadata).digest('hex'), byteSize: metadata.length };
    writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
    await assert.rejects(verifyRunBundle(f.bundle), /proxy campaign|metadata integrity/i, label);
    const destination = path.join(f.root, 'rejected-restore');
    await assert.rejects(restoreRunBundle(f.bundle, destination), /proxy campaign|metadata integrity/i, label);
    assert.equal(existsSync(destination), false, label);
  }

  const f = await fixture(t);
  await addV2Campaign(f); await f.backup();
  const db = new DatabaseSync(path.join(f.bundle, 'runs.sqlite'));
  const row = db.prepare('SELECT document_json FROM lpbf_proxy_campaigns').all()
    .find(item => JSON.parse(String(item.document_json)).schemaVersion === 2)!;
  const document = JSON.parse(String(row.document_json)); document.claimBoundary.opticalOperatorMatched = true;
  const documentJson = JSON.stringify(document);
  db.prepare('UPDATE lpbf_proxy_campaigns SET document_json=?, document_sha256=? WHERE campaign_id=?')
    .run(documentJson, sha(documentJson), document.campaignId);
  db.close();
  const manifestPath = path.join(f.bundle, 'bundle.json'), manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  const metadata = readFileSync(path.join(f.bundle, 'runs.sqlite'));
  manifest.metadata = { sha256: createHash('sha256').update(metadata).digest('hex'), byteSize: metadata.length };
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  const service = new LpbfRunBundleService(path.join(f.root, 'live-runs'), path.join(f.root, 'live-sources'), path.join(f.root, 'imports'));
  await assert.rejects(service.importPortable(await createRunBundleTar(f.bundle)), /portable run bundle integrity verification failed/i);
});

test('v2 campaign restore rejects missing Table 4 revisions and mismatched artifacts', async t => {
  const cases: Array<[string, RegExp, (document: any) => void]> = [
    ['missing revision', /source artifact binding mismatch/i, document => {
      document.sourceBinding.revision = 99;
      document.beamInputDeclaration.sourceBinding.revision = 99;
      for (const track of document.tracks) for (const observation of track.observations) observation.provenance.sourceBinding.revision = 99;
    }],
    ['mismatched artifact', /proxy campaign metadata integrity/i, document => {
      document.sourceBinding.artifactSha256 = sha('missing table4 artifact');
      document.beamInputDeclaration.sourceBinding.artifactSha256 = document.sourceBinding.artifactSha256;
      for (const track of document.tracks) for (const observation of track.observations)
        observation.provenance.sourceBinding.artifactSha256 = document.sourceBinding.artifactSha256;
    }],
  ];
  for (const [label, expected, mutate] of cases) {
    const f = await fixture(t); await addV2Campaign(f); await f.backup();
    mutateBundledV2Campaign(f.bundle, mutate);
    const destination = path.join(f.root, 'rejected-restore');
    await assert.rejects(restoreRunBundle(f.bundle, destination), expected, label);
    assert.equal(existsSync(destination), false, label);
  }
});

test('missing or corrupted run/source objects prevent restore before destination creation', async t => {
  for (const which of ['run', 'source'] as const) for (const missing of [false, true]) {
    const f = await fixture(t); await f.backup();
    const store = new LpbfArtifactStore(path.join(f.bundle, which === 'run' ? 'artifacts' : 'sources/artifacts'), { readOnly: true });
    const object = await store.verify(which === 'run' ? { sha256: sha('abc'), byteSize: 3 } : f.sourceRef);
    if (missing) unlinkSync(object.path); else writeFileSync(object.path, 'bad');
    const destination = path.join(f.root, 'restored');
    await assert.rejects(restoreRunBundle(f.bundle, destination)); assert.equal(existsSync(destination), false);
  }
});

test('backup failures leave no top-level completion and preserve live data', async t => {
  for (const which of ['run', 'source', 'link'] as const) {
    const f = await fixture(t);
    if (which === 'link') {
      const d = structuredClone(f.record.document); d.runId = d.capture.jobId = 'b'.repeat(32);
      d.sources[0].documentSha256 = sha('wrong'); f.runs.save(d);
    } else {
      const store = which === 'run' ? f.runStore : f.sourceStore;
      writeFileSync((await store.verify(which === 'run' ? { sha256: sha('abc'), byteSize: 3 } : f.sourceRef)).path, 'bad');
    }
    await assert.rejects(f.backup()); assert.equal(existsSync(path.join(f.bundle, 'bundle.json')), false);
    assert.deepEqual(f.runs.get(f.record.document.runId), f.record);
  }
});

test('both SQLite snapshots reject sidecars; metadata and completion hashes/counts are checked', async t => {
  for (const file of ['runs.sqlite-wal', 'runs.sqlite-shm', 'runs.sqlite-journal',
    'sources/metadata.sqlite-wal', 'sources/metadata.sqlite-shm', 'sources/metadata.sqlite-journal',
    'runs.sqlite', 'sources/metadata.sqlite', 'sources/bundle.json', 'bundle.json']) {
    const f = await fixture(t); await f.backup();
    if (file === 'bundle.json') {
      const m = JSON.parse(readFileSync(path.join(f.bundle, file), 'utf8')); m.runCount++;
      writeFileSync(path.join(f.bundle, file), JSON.stringify(m));
    } else writeFileSync(path.join(f.bundle, file), 'bad');
    await assert.rejects(verifyRunBundle(f.bundle));
  }
});

test('linked roots and nested source directories are rejected', async t => {
  const f = await fixture(t); await f.backup();
  const alias = path.join(f.root, 'alias'); symlinkSync(f.bundle, alias, 'junction');
  await assert.rejects(verifyRunBundle(alias), /link/i);
  await assert.rejects(backupRunBundle(f.runs, f.runStore, f.sources, f.sourceStore, path.join(alias, 'new')), /link/i);
  const f2 = await fixture(t); mkdirSync(f2.bundle);
  symlinkSync(path.join(f.bundle, 'sources'), path.join(f2.bundle, 'sources'), 'junction');
  writeFileSync(path.join(f2.bundle, 'runs.sqlite'), readFileSync(path.join(f.bundle, 'runs.sqlite')));
  writeFileSync(path.join(f2.bundle, 'bundle.json'), readFileSync(path.join(f.bundle, 'bundle.json')));
  await assert.rejects(verifyRunBundle(f2.bundle), /link/i);
});

test('run snapshot precedes source snapshot; later runs stay out and historical links stay exact', async t => {
  const f = await fixture(t), original = f.sources.backupMetadata.bind(f.sources);
  f.sources.backupMetadata = async directory => {
    assert.equal(existsSync(path.join(f.bundle, 'runs.sqlite')), true);
    const late = structuredClone(f.record.document); late.runId = late.capture.jobId = 'b'.repeat(32);
    f.runs.save(late);
    const source = f.sources.current('synthetic')!.document; source.source.version = '3';
    f.sources.save(source, 2);
    return original(directory);
  };
  const manifest = await f.backup(); assert.equal(manifest.runCount, 1);
  assert.equal([...f.runs.allRuns()].length, 2);
  await verifyRunBundle(f.bundle);
  const snapshot = new LpbfSourceRepository(path.join(f.bundle, 'sources/metadata.sqlite'), { readOnly: true });
  try {
    assert.equal(snapshot.current('synthetic')!.revision, 3);
    assert.equal(snapshot.revision('synthetic', 1)!.documentSha256, f.record.document.sources[0].documentSha256);
  } finally { snapshot.close(); }
});

test('bundle verification rejects every unreferenced file before restore creates a destination', async t => {
  for (const relative of ['unexpected.json', `artifacts/objects/ee/${'e'.repeat(64)}`,
    `sources/artifacts/objects/ff/${'f'.repeat(64)}`]) {
    const f = await fixture(t); await f.backup();
    const completion = readFileSync(path.join(f.bundle, 'bundle.json'));
    const extra = path.join(f.bundle, relative);
    mkdirSync(path.dirname(extra), { recursive: true });
    writeFileSync(extra, 'not a referenced or hash-verified payload');
    await assert.rejects(verifyRunBundle(f.bundle), /inventory|unexpected/i);
    const destination = path.join(f.root, 'rejected-restore');
    await assert.rejects(restoreRunBundle(f.bundle, destination), /inventory|unexpected/i);
    assert.equal(existsSync(destination), false);
    assert.deepEqual(readFileSync(path.join(f.bundle, 'bundle.json')), completion);
    assert.deepEqual(f.runs.get(f.record.document.runId), f.record);
  }
});

test('all frozen source revisions retain their objects even when a run links an older revision', async t => {
  const f = await fixture(t);
  const raw = path.join(f.root, 'later-source'); mkdirSync(raw);
  writeFileSync(path.join(raw, 'later'), 'later source bytes');
  const ref = { relativePath: 'later', sha256: sha('later source bytes'), byteSize: 18,
    sourceUrl: 'https://example.org/later' };
  await f.sourceStore.putFile(raw, 'later', ref);
  const document = structuredClone(f.sources.current('synthetic')!.document);
  document.artifacts = [ref]; document.source.version = '3';
  f.sources.save(document, 2);
  await f.backup(); await verifyRunBundle(f.bundle);
  const destination = path.join(f.root, 'superset-restored');
  await restoreRunBundle(f.bundle, destination);
  const store = new LpbfArtifactStore(path.join(destination, 'sources/artifacts'), { readOnly: true });
  assert.equal(readFileSync((await store.verify(ref)).path, 'utf8'), 'later source bytes');
});

test('legacy v1 completion remains readable without changing archived record bytes', async t => {
  const f = await fixture(t); await f.backup();
  const file = path.join(f.bundle, 'bundle.json');
  const manifest = JSON.parse(readFileSync(file, 'utf8'));
  manifest.schemaVersion = 1; delete manifest.campaignCount;
  writeFileSync(file, JSON.stringify(manifest));
  const before = readFileSync(file);
  assert.equal((await verifyRunBundle(f.bundle)).schemaVersion, 1);
  const destination = path.join(f.root, 'legacy-restored');
  await restoreRunBundle(f.bundle, destination);
  const runs = new LpbfRunRepository(path.join(destination, 'runs.sqlite'), { readOnly: true });
  try { assert.deepEqual(runs.get(f.record.document.runId), f.record); }
  finally { runs.close(); }
  assert.deepEqual(readFileSync(file), before);
});

test('unreferenced linked directories are rejected by the complete inventory', async t => {
  const f = await fixture(t); await f.backup();
  const outside = path.join(f.root, 'outside'); mkdirSync(outside);
  symlinkSync(outside, path.join(f.bundle, 'unreferenced-link'), 'junction');
  await assert.rejects(verifyRunBundle(f.bundle), /link|inventory/i);
});
