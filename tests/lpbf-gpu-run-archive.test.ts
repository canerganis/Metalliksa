import assert from 'node:assert/strict';
import { cpSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { test } from 'node:test';
import { LpbfArtifactStore } from '../server/lpbfArtifactStore';
import { verifyRunBundle, backupRunBundle, restoreRunBundle } from '../server/lpbfRunBundle';
import { LpbfRunArchiveService } from '../server/lpbfRunArchiveService';
import { LpbfNistComparisonService } from '../server/lpbfNistComparisonService';
import { dryRunRunImport, importRun } from '../server/lpbfRunImport';
import { LpbfRunRepository, validateRunDocument, type RunCapture } from '../server/lpbfRunRepository';
import { LpbfSourceRepository } from '../server/lpbfSourceRepository';

const actual = path.resolve('docs/LPBF_GPU_NATIVE_WORKER_ACCEPTANCE_RETRY_2026-09-27/2bcb01e5799041ec9458a947506d491f');

function setup() {
  const root = mkdtempSync(path.resolve('.tmp-gpu-run-archive-'));
  const job = path.join(root, 'job'); cpSync(actual, job, { recursive: true });
  const runRoot = path.join(root, 'live-runs'); mkdirSync(runRoot);
  const repository = new LpbfRunRepository(path.join(runRoot, 'runs.sqlite'));
  const sources = new LpbfSourceRepository(path.join(root, 'sources.sqlite'));
  const store = new LpbfArtifactStore(path.join(runRoot, 'artifacts'));
  const sourceStore = new LpbfArtifactStore(path.join(root, 'source-artifacts'));
  const resultJson = readFileSync(path.join(job, 'result.json'), 'utf8');
  const result = JSON.parse(resultJson);
  const inputs = result.gpuRunContract.serializedInputs;
  const capture: RunCapture = { schemaVersion: 1, jobId: path.basename(actual), resultJson,
    inputJson: inputs.requestJson, materialJson: inputs.materialJson,
    contractStatus: 'gpu-pilot-v1-bound' as const, runKind: 'gpu-thermal-pilot' as const };
  return { root, runRoot, job, repository, sources, store, sourceStore, result, capture };
}

function makeStructuralWarpV2Fixture(f: ReturnType<typeof setup>) {
  // This is a schema-routing fixture, not a Warp execution or physics result.
  // It reuses the captured numerical bytes solely to exercise the archive lifecycle.
  const c = f.result.gpuRunContract;
  const requestJson = c.serializedInputs.requestJson.replace(
    '"jobType": "gpu-thermal-pilot"',
    '"executionEngine": "warp", "jobType": "gpu-thermal-pilot"');
  assert.notEqual(requestJson, c.serializedInputs.requestJson);
  f.result.settings.executionEngine = 'warp';
  c.schemaVersion = 2;
  c.capture.contractStatus = 'gpu-pilot-v2-warp-bound';
  c.capture.engineId = 'warp';
  c.serializedInputs.requestJson = requestJson;
  c.hashes.requestHash = createHash('sha256').update(requestJson).digest('hex');
  f.result.provenance.inputHash = c.hashes.requestHash;
  f.result.provenance.deviceEvidence.engineId = 'warp';
  f.result.provenance.deviceEvidence.warp = 'synthetic-schema-fixture';
  f.result.provenance.deviceEvidence.warpCudaToolkitVersion = '12.9';
  f.result.provenance.deviceEvidence.cudaDriverVersion = '13.4';
  delete f.result.provenance.deviceEvidence.cudaRuntime;
  delete f.result.provenance.deviceEvidence.torch;
  f.result.solver.id = 'enthalpy-fv-6-warp-candidate-1';
  const resultJson = JSON.stringify(f.result);
  writeFileSync(path.join(f.job, 'result.json'), resultJson);
  f.capture = { ...f.capture, resultJson, inputJson: requestJson,
    contractStatus: 'gpu-pilot-v2-warp-bound' as const };
}

test('actual bound GPU run imports only after full bytes and numerical evidence, then rechecks on read and bundle restore', async t => {
  const f = setup();
  t.after(() => { f.repository.close(); f.sources.close(); rmSync(f.root, { recursive: true, force: true }); });
  const document = validateRunDocument({ schemaVersion: 1, runId: f.capture.jobId, capture: f.capture, sources: [] });
  assert.equal(document.capture.runKind, 'gpu-thermal-pilot');
  const preview = await dryRunRunImport(f.capture, [], f.sources, f.job);
  assert.equal(preview.artifactCount, 12);
  const saved = await importRun(f.repository, f.store, f.capture, [], f.sources, f.job);
  assert.equal(saved.runKind, 'gpu-thermal-pilot');
  assert.equal(saved.document.capture.contractStatus, 'gpu-pilot-v1-bound');
  assert.equal(Object.hasOwn(JSON.parse(saved.document.capture.resultJson), 'coreContract'), false);

  const service = new LpbfRunArchiveService(f.runRoot, path.join(f.root, 'sources-live'));
  assert.equal((await service.getVerified(f.capture.jobId)).runKind, 'gpu-thermal-pilot');
  const gpuField = f.result.gpuFieldArtifacts.states.gpu.fields.temperature_K;
  const stored = await f.store.verify({ sha256: gpuField.sha256, byteSize: gpuField.size_bytes });
  const originalBytes = readFileSync(stored.path), alteredBytes = Buffer.from(originalBytes); alteredBytes[0] ^= 1;
  writeFileSync(stored.path, alteredBytes);
  await assert.rejects(service.getVerified(f.capture.jobId), /GPU pilot field archive integrity/i);
  writeFileSync(stored.path, originalBytes);
  const nist = new LpbfNistComparisonService(f.runRoot, path.join(f.root, 'sources-live'));
  const nistResult = await nist.compare(f.capture.jobId, '0') as { status: string; reasons: string[] };
  assert.equal(nistResult.status, 'unavailable');
  assert.match(nistResult.reasons.join(' '), /GPU thermal-pilot archives/i);

  const bundle = await backupRunBundle(f.repository, f.store, f.sources, f.sourceStore, path.join(f.root, 'bundle'));
  assert.equal((await verifyRunBundle(path.join(f.root, 'bundle'))).runCount, 1);
  const restored = path.join(f.root, 'restored');
  await restoreRunBundle(path.join(f.root, 'bundle'), restored);
  assert.equal((await verifyRunBundle(restored)).artifactCount, bundle.artifactCount);
  const bundleStore = new LpbfArtifactStore(path.join(f.root, 'bundle', 'artifacts'), { readOnly: true });
  const bundledField = await bundleStore.verify({ sha256: gpuField.sha256, byteSize: gpuField.size_bytes });
  const bundleBytes = readFileSync(bundledField.path); bundleBytes[0] ^= 1; writeFileSync(bundledField.path, bundleBytes);
  await assert.rejects(verifyRunBundle(path.join(f.root, 'bundle')), /integrity|GPU pilot/i);

  const altered = { ...f.capture, inputJson: `${f.capture.inputJson} ` };
  await assert.rejects(dryRunRunImport(altered, [], f.sources, f.job), /GPU run capture snapshot identity mismatch/i);
});

test('Warp v2 archive status survives the same import, verified read, bundle export and restore lifecycle', async t => {
  const f = setup(); makeStructuralWarpV2Fixture(f);
  t.after(() => { f.repository.close(); f.sources.close(); rmSync(f.root, { recursive: true, force: true }); });
  const document = validateRunDocument({ schemaVersion: 1, runId: f.capture.jobId, capture: f.capture, sources: [] });
  assert.equal(document.capture.contractStatus, 'gpu-pilot-v2-warp-bound');
  const preview = await dryRunRunImport(f.capture, [], f.sources, f.job);
  assert.equal(preview.artifactCount, 12);
  const saved = await importRun(f.repository, f.store, f.capture, [], f.sources, f.job);
  assert.equal(saved.document.capture.contractStatus, 'gpu-pilot-v2-warp-bound');
  const service = new LpbfRunArchiveService(f.runRoot, path.join(f.root, 'sources-live'));
  assert.equal((await service.getVerified(f.capture.jobId)).document.capture.contractStatus, 'gpu-pilot-v2-warp-bound');
  const bundle = await backupRunBundle(f.repository, f.store, f.sources, f.sourceStore, path.join(f.root, 'bundle'));
  assert.equal((await verifyRunBundle(path.join(f.root, 'bundle'))).runCount, 1);
  const restored = path.join(f.root, 'restored');
  await restoreRunBundle(path.join(f.root, 'bundle'), restored);
  assert.equal((await verifyRunBundle(restored)).artifactCount, bundle.artifactCount);
  const restoredStore = new LpbfArtifactStore(path.join(restored, 'artifacts'), { readOnly: true });
  const restoredRepository = new LpbfRunRepository(path.join(restored, 'runs.sqlite'), { readOnly: true });
  assert.equal(restoredRepository.get(f.capture.jobId)?.document.capture.contractStatus, 'gpu-pilot-v2-warp-bound');
  assert.equal((await restoredStore.verify({ sha256: f.result.gpuFieldArtifacts.states.gpu.fields.temperature_K.sha256,
    byteSize: f.result.gpuFieldArtifacts.states.gpu.fields.temperature_K.size_bytes })).byteSize,
  f.result.gpuFieldArtifacts.states.gpu.fields.temperature_K.size_bytes);
  restoredRepository.close();
});

test('GPU archive metadata cannot borrow a top-level CPU core contract or CPU capture status', t => {
  const f = setup();
  t.after(() => { f.repository.close(); f.sources.close(); rmSync(f.root, { recursive: true, force: true }); });
  const wrongStatus = { ...f.capture, contractStatus: 'core-v1-bound' };
  assert.throws(() => validateRunDocument({ schemaVersion: 1, runId: f.capture.jobId, capture: wrongStatus, sources: [] }), /GPU run capture/i);
  const result = { ...f.result, coreContract: f.result.gpuPilot.cpu.coreContract };
  const borrowedCore = { ...f.capture, resultJson: JSON.stringify(result) };
  assert.throws(() => validateRunDocument({ schemaVersion: 1, runId: f.capture.jobId, capture: borrowedCore, sources: [] }), /bound GPU archive result/i);

  const falselyExperimental = { ...f.result, gpuPilot: { ...f.result.gpuPilot, experimentalValidation: true } };
  assert.throws(() => validateRunDocument({ schemaVersion: 1, runId: f.capture.jobId,
    capture: { ...f.capture, resultJson: JSON.stringify(falselyExperimental) }, sources: [] }), /CUDA pilot|GPU/i);
  const detachedDevice = structuredClone(f.result);
  detachedDevice.solver.sourceIntegrationDevice = 'cuda:1';
  assert.throws(() => validateRunDocument({ schemaVersion: 1, runId: f.capture.jobId,
    capture: { ...f.capture, resultJson: JSON.stringify(detachedDevice) }, sources: [] }), /CUDA pilot|GPU/i);
});

test('GPU archive capture status must match the inner v1 or Warp v2 contract in both directions', t => {
  const torch = setup();
  const warp = setup(); makeStructuralWarpV2Fixture(warp);
  t.after(() => {
    torch.repository.close(); torch.sources.close(); rmSync(torch.root, { recursive: true, force: true });
    warp.repository.close(); warp.sources.close(); rmSync(warp.root, { recursive: true, force: true });
  });
  assert.throws(() => validateRunDocument({ schemaVersion: 1, runId: torch.capture.jobId,
    capture: { ...torch.capture, contractStatus: 'gpu-pilot-v2-warp-bound' }, sources: [] }), /GPU run capture/i);
  assert.throws(() => validateRunDocument({ schemaVersion: 1, runId: warp.capture.jobId,
    capture: { ...warp.capture, contractStatus: 'gpu-pilot-v1-bound' }, sources: [] }), /GPU run capture/i);
});

test('GPU field corruption is rejected before archive import', async t => {
  const f = setup();
  t.after(() => { f.repository.close(); f.sources.close(); rmSync(f.root, { recursive: true, force: true }); });
  const field = f.result.gpuFieldArtifacts.states.gpu.fields.temperature_K.path;
  const filename = path.join(f.job, ...field.split('/'));
  const bytes = readFileSync(filename); bytes[0] ^= 1; writeFileSync(filename, bytes);
  await assert.rejects(dryRunRunImport(f.capture, [], f.sources, f.job), /integrity|changed|numerical/i);
});
