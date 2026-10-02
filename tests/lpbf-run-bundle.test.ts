import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync, unlinkSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { test, type TestContext } from 'node:test';
import { LpbfRunRepository } from '../server/lpbfRunRepository';
import { LpbfSourceRepository } from '../server/lpbfSourceRepository';
import { LpbfArtifactStore } from '../server/lpbfArtifactStore';
import { importRun } from '../server/lpbfRunImport';
import { backupRunBundle, restoreRunBundle, verifyRunBundle } from '../server/lpbfRunBundle';

const sha = (value: string) => createHash('sha256').update(value).digest('hex');
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
  const runRecords = [f.record];
  for (const id of ['b'.repeat(32), 'c'.repeat(32)]) {
    const document = structuredClone(f.record.document);
    document.runId = document.capture.jobId = id;
    runRecords.push(f.runs.save(document));
  }
  const binding = { datasetId: 'synthetic', revision: 1, documentSha256: f.record.document.sources[0].documentSha256,
    artifactPath: 'raw', artifactSha256: sha('raw'), artifactSizeBytes: 3, caseNumber: '2.1' };
  const campaign = { schemaVersion: 1, kind: 'lpbf-nist-amb2022-03-proxy-campaign', campaignId: '9'.repeat(32),
    benchmark: 'AMB2022-03-TMPG', caseNumber: '2.1', sourceBinding: binding, tracks: runRecords.map(record => ({
      runIdentity: { runId: record.document.runId, runDocumentSha256: record.documentSha256 },
    })) };
  f.runs.saveProxyCampaign(campaign);
  const manifest = await f.backup();
  assert.equal(manifest.schemaVersion, 2);
  assert.equal(manifest.campaignCount, 1);
  const destination = path.join(f.root, 'campaign-restored');
  await restoreRunBundle(f.bundle, destination);
  const restored = new LpbfRunRepository(path.join(destination, 'runs.sqlite'), { readOnly: true });
  try {
    const record = restored.getProxyCampaign(campaign.campaignId)!;
    assert.deepEqual(record.document, campaign);
    assert.equal([...restored.allProxyCampaigns()].length, 1);
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
