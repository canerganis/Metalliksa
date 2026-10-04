import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync, unlinkSync, symlinkSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
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
import { deriveProxyCampaignRunBinding } from '../server/lpbfProxyCampaignBinding';
import { getHostPython } from '../server/pythonRuntime';

const sha = (value: string | Buffer) => createHash('sha256').update(value).digest('hex');
function bundleV2Campaign(runRecords: any[], sourceBinding: any) {
  const tracks = runRecords.map(record => {
    const binding = deriveProxyCampaignRunBinding(record, sourceBinding);
    assert.ok(binding, 'positive v2 fixtures must bind to an eligible captured run');
    return { simulatedTrackId: `sim-${record.document.runId}`, experimentalTrackId: null,
      replicateKind: 'reproducibility-execution', ...structuredClone(binding) };
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

function proxySectionFixture(): { bytes: Buffer; observations: any[] } {
  const python = getHostPython();
  const code = [
    'import base64,json,sys,tempfile', 'from pathlib import Path', 'import numpy as np',
    'sys.path.insert(0,"python")',
    'from lpbf_peak import rectangular_corridor_section_samples,rectangular_corridor_section_observations,write_rectangular_corridor_section_field_artifact',
    'mesh=.001; axis_x=-.005+np.arange(11,dtype=np.float64)*mesh',
    'axis_y=np.arange(-.004,.0041,mesh,dtype=np.float64); z=np.arange(-.004,.0001,mesh,dtype=np.float64)',
    'requests=rectangular_corridor_section_samples(axis_x,-.005,.01); fields={}',
    'for index in sorted({i for row in requests for i in row["sourcePlaneIndices"]}):',
    ' field=np.full((len(axis_y),len(z)),300.,dtype=np.float64); field[(np.abs(axis_y)<=.001)[:,None]&((z>=-.003)&(z<=-.001))[None,:]]=1800.; fields[index]=field',
    'observations=rectangular_corridor_section_observations(axis_y,z,fields,requests,mesh,1600.)',
    'with tempfile.TemporaryDirectory() as directory:',
    ' target=Path(directory)/"rectangular-corridor-section-fields.npz"',
    ' write_rectangular_corridor_section_field_artifact(target,axis_x,axis_y,z,observations,fields,mesh,1600.,17)',
    ' print(json.dumps({"bytes":base64.b64encode(target.read_bytes()).decode("ascii"),"observations":observations},allow_nan=False))',
  ].join('\n');
  const generated = spawnSync(python.cmd, [...python.prefix, '-B', '-c', code], { encoding: 'utf8', windowsHide: true,
    cwd: process.cwd(), maxBuffer: 4 * 1024 * 1024 });
  if (generated.error || generated.status !== 0) throw generated.error || new Error(`Could not create proxy NPZ fixture: ${generated.stderr}`);
  const parsed = JSON.parse(generated.stdout);
  return { bytes: Buffer.from(parsed.bytes, 'base64'), observations: parsed.observations };
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

async function addV2Campaign(f: Awaited<ReturnType<typeof fixture>>, alterSourceArtifact = false) {
  const originalTable4Bytes = readFileSync('data/benchmark/nist-amb2022-03-optical/table4-aggregate-v2.json');
  const table4Bytes = alterSourceArtifact
    ? Buffer.from(originalTable4Bytes.toString('utf8').replace('\n', '\r'), 'utf8') : originalTable4Bytes;
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
  const sectionFixture = proxySectionFixture();
  const sectionJob = path.join(f.root, 'proxy-sections'); mkdirSync(sectionJob);
  writeFileSync(path.join(sectionJob, 'rectangular-corridor-section-fields.npz'), sectionFixture.bytes);
  const sectionArtifact = { relativePath: 'rectangular-corridor-section-fields.npz', sha256: sha(sectionFixture.bytes),
    byteSize: sectionFixture.bytes.length };
  await f.runStore.putFile(sectionJob, sectionArtifact.relativePath, sectionArtifact);
  const runRecords = [];
  for (const id of ['b'.repeat(32), 'c'.repeat(32), 'd'.repeat(32)]) {
    const document = structuredClone(f.record.document);
    document.runId = document.capture.jobId = id;
    document.sources.push(table4Link);
    const settings = { backend: 'auto', power_W: 500, speed_mm_s: 1000, beamDiameter_um: 67, preheat_C: 23.5,
      surfaceMode: 'bare-plate', tracks: 1, layers: 1, trackLength_um: 10000, scanAngle_deg: 0, mesh_um: 1000 };
    const material = { materialId: 'in718', materialRevisionSha256: sha(`proxy-material-revision-${id}`),
      name: 'Inconel 718', quality: 'literature', source: 'synthetic service fixture', liquidus_K: 1600 };
    const inputJson = JSON.stringify(settings), materialJson = JSON.stringify(material);
    const result = { ...JSON.parse(f.record.document.capture.resultJson), schemaVersion: 1, runKind: 'transient-thermal',
      requestedMode: 'standard', effectiveMode: 'standard', fallbackReason: null,
      settings, material, solver: { id: 'enthalpy-fv-6', version: 'fixture' },
      artifacts: [{ path: sectionArtifact.relativePath, sha256: sectionArtifact.sha256, size_bytes: sectionArtifact.byteSize }],
      discretization: { cells: 1000, mesh_m: .001, steps: 17 },
      energyBalance: { input_J: 0, losses_J: 0, stored_J: 0, relativeError: 0 },
      massBalance: { initial_kg: 0, deposited_kg: 0, final_kg: 0, relativeError: 0, scope: 'synthetic fixture' },
      phaseAudit: { activeVolume_m3: 0, liquidVolume_m3: 0, solidVolume_m3: 0,
        minFraction: 0, maxFraction: 0, scope: 'synthetic fixture' },
      barePlateSectionFieldArtifact: { schemaVersion: 1, status: 'captured',
        path: 'rectangular-corridor-section-fields.npz', binding: 'accepted-step-maximum-per-source-X-plane' },
      coreContract: { schemaVersion: 1, modelId: 'stationary-enthalpy-conduction-v1', actualBackend: 'numpy-reference',
        requestedBackend: 'auto', effectiveMode: 'standard', solverId: 'enthalpy-fv-6',
        inputSha256: sha(inputJson), materialSha256: sha(materialJson),
        units: { power: 'W', speed: 'mm/s', length: 'um', preheat: 'degC', temperature: 'K',
          internalLength: 'm', time: 's', energy: 'J', beamDiameter: '1/e2-intensity' },
        resolvedPhysics: { conduction: true, transient: true, latentHeat: true, momentum: false, freeSurface: false, evaporation: false },
        evidenceClass: 'unvalidated-model' },
      scanPath: [{ start: [-.005, 0], end: [.005, 0], start_s: 0, end_s: .01 }],
      barePlateSectionObservations: sectionFixture.observations };
    document.capture = { schemaVersion: 1, jobId: id, resultJson: JSON.stringify(result), inputJson, materialJson,
      contractStatus: 'core-v1-bound', runKind: 'transient-thermal' };
    document.capture.runKind = 'transient-thermal';
    runRecords.push(f.runs.save(document));
  }
  const binding = { ...table4Link, artifactPath: table4Artifact.relativePath, artifactSha256: table4Artifact.sha256,
    artifactSizeBytes: table4Artifact.byteSize, caseNumber: '0' };
  if (alterSourceArtifact) {
    binding.artifactSha256 = 'd1b36dfa2e01a3537093c481e249ce52df6b8879c1c67480ddb9aa10799133da';
    binding.artifactSizeBytes = 4321;
  }
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
  const runRecords = [];
  const binding = { datasetId: 'synthetic', revision: 1, documentSha256: f.record.document.sources[0].documentSha256,
    artifactPath: 'raw', artifactSha256: sha('raw'), artifactSizeBytes: 3, caseNumber: '2.1' };
  for (const id of ['1'.repeat(32), '2'.repeat(32), '3'.repeat(32)]) {
    const document = structuredClone(f.record.document);
    document.runId = document.capture.jobId = id;
    runRecords.push(f.runs.save(document));
  }
  const campaign = { schemaVersion: 1, kind: 'lpbf-nist-amb2022-03-proxy-campaign', campaignId: '9'.repeat(32),
    benchmark: 'AMB2022-03-TMPG', caseNumber: '2.1', sourceBinding: binding, tracks: runRecords.map(record => ({
      runIdentity: { runId: record.document.runId, runDocumentSha256: record.documentSha256 },
    })) };
  f.runs.saveProxyCampaign(campaign);
  const v2 = await addV2Campaign(f);
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
    ['optical operator claim', document => { document.claimBoundary.opticalOperatorMatched = true; }],
    ['missing observations', document => { delete document.tracks[0].observations; }],
    ['extra nested field', document => { document.tracks[0].observations[0].geometry.clientNote = 'forged'; }],
    ['forged result artifact identity', document => {
      document.tracks[0].runIdentity.resultArtifact.sha256 = sha('forged result');
      for (const observation of document.tracks[0].observations) observation.provenance.runIdentity = structuredClone(document.tracks[0].runIdentity);
    }],
    ['forged executed settings', document => { document.tracks[0].runIdentity.executedSettings.beamDiameter_um = 68; }],
    ['forged captured geometry', document => { document.tracks[0].observations[0].geometry.width_um += 1; }],
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
    await assert.rejects(verifyRunBundle(f.bundle), /campaign|metadata integrity/i, label);
    const destination = path.join(f.root, 'rejected-restore');
    await assert.rejects(restoreRunBundle(f.bundle, destination), /campaign|metadata integrity/i, label);
    assert.equal(existsSync(destination), false, label);
    const service = new LpbfRunBundleService(path.join(f.root, 'live-runs'), path.join(f.root, 'live-sources'), path.join(f.root, 'imports'));
    await assert.rejects(service.importPortable(await createRunBundleTar(f.bundle)), /campaign/i, label);
  }
});

test('no-op rehashed v2 bundle mutation remains verifiable and restorable', async t => {
  const f = await fixture(t); await addV2Campaign(f); await f.backup();
  mutateBundledV2Campaign(f.bundle, () => {});
  await verifyRunBundle(f.bundle);
  const destination = path.join(f.root, 'no-op-restored');
  await restoreRunBundle(f.bundle, destination);
  const restored = new LpbfRunRepository(path.join(destination, 'runs.sqlite'), { readOnly: true });
  try { assert.equal([...restored.allProxyCampaigns()].filter(item => item.document.schemaVersion === 2).length, 1); }
  finally { restored.close(); }
});

test('bundle binding rejects a parseable same-size Table 4 artifact with a different revision SHA', async t => {
  const f = await fixture(t);
  await addV2Campaign(f, true);
  const table4 = readFileSync('data/benchmark/nist-amb2022-03-optical/table4-aggregate-v2.json');
  const altered = Buffer.from(table4.toString('utf8').replace('\n', '\r'), 'utf8');
  assert.equal(altered.length, table4.length);
  assert.doesNotThrow(() => JSON.parse(altered.toString('utf8')));
  assert.notEqual(sha(altered), sha(table4));
  await assert.rejects(f.backup(), /Campaign Table 4 source artifact binding mismatch/);
  assert.equal(existsSync(path.join(f.bundle, 'bundle.json')), false);
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
