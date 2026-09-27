import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { parseGpuPilotJob, parseSimulationJob, gpuPilotApi, buildGpuPilotInput } from '../src/services/lpbfSimulationService';

test('CUDA pilot request includes only CPU validator fields and preserves the shared process', () => {
  const input = { material: '316L', power_W: 40, speed_mm_s: 850, beamDiameter_um: 80,
    preheat_C: 80, layer_um: 40, hatch_um: 100, measurements: [{ width_um: 1, depth_um: 1, source: 'test' }],
    legacyField: 'must not reach worker' };
  const settings = { mesh_um: 20, maxDt_s: 1e-6, trackLength_um: 600,
    backend: 'openfoam-thermal' as const, study: 'mesh' as const, tracks: 4, layers: 3,
    legacySetting: 'must not reach worker' };
  const pilot = buildGpuPilotInput(input, settings, 'cuda:0', '316L', 'meander');
  assert.equal(pilot.jobType, 'gpu-thermal-pilot');
  assert.equal(pilot.backend, 'cuda:0');
  assert.equal(pilot.mode, 'standard');
  assert.equal(pilot.study, 'none');
  assert.equal(pilot.tracks, 1);
  assert.equal(pilot.layers, 1);
  assert.equal(pilot.power_W, 40);
  assert.equal(pilot.speed_mm_s, 850);
  assert.equal(pilot.mesh_um, 20);
  assert.equal(pilot.maxDt_s, 1e-6);
  assert.equal(pilot.trackLength_um, 600);
  assert.equal(pilot.powderGridPolicy, 'layer-conforming');
  for (const key of ['legacyField', 'legacySetting', 'measurements']) {
    assert.ok(!(key in pilot), key);
  }
});

const sha = 'a'.repeat(64);
const targets = { integralRelativeMax: .01, widthDepthAbsoluteCellsMax: 1,
  fieldRiseL2RelativeMax: .01, fieldRiseMaxRelativeMax: .01,
  peakMeltVolumeRelativeMax: .01, source: 'docs/DIGITAL_TWIN_MASTER_PLAN_2026-09-21.md#11' };
const comparisons = Object.fromEntries(['finalSampling', 'finalTemperatureField', 'peakTemperature_K',
  'input_J', 'losses_J', 'stored_J', 'width_um', 'depth_um', 'length_um', 'volume_um3']
  .map(key => [key, { status: 'pass', cpu: 1, gpu: 1, relativeDifference: 0,
    relativeRiseL2: 0, relativeRiseMax: 0 }]));
for (const [key, value] of Object.entries({ peakTemperature_K: 1800, input_J: 1,
  losses_J: .2, stored_J: .8, width_um: 40, depth_um: 40, length_um: 100, volume_um3: 1000 })) {
  comparisons[key] = { ...comparisons[key], cpu: value, gpu: value };
}
const completed = {
  id: 'b'.repeat(32), status: 'completed', progress: 1, log: '', error: null,
  requestSummary: { jobType: 'gpu-thermal-pilot', backend: 'cuda:0', mode: 'standard', material: 'Inconel 718' },
  result: {
    schemaVersion: 1, jobType: 'gpu-thermal-pilot', requestedMode: 'standard', effectiveMode: 'gpu-pilot',
    validationStatus: 'unvalidated', productionReady: false, label: 'Unvalidated CUDA thermal parity pilot',
    settings: { jobType: 'gpu-thermal-pilot', backend: 'cuda:0', mode: 'standard',
      study: 'none', surfaceMode: 'powder-layer', powderGridPolicy: 'layer-conforming', tracks: 1, layers: 1 },
    solver: { id: 'enthalpy-fv-6-cuda-pilot-1', modelId: 'stationary-enthalpy-conduction-layer-conforming-v1',
      actualBackend: 'cuda:0', thermalEvolutionDevice: 'cuda:0',
      sourceIntegrationDevice: 'cpu', sourceTimestepLimiterDevice: 'cpu', dtype: 'float64' },
    material: { name: 'Inconel 718', materialId: 'in718', materialRevisionSha256: sha, version: '1' },
    metrics: { width_um: 40, depth_um: 40, length_um: 100, volume_um3: 1000, peakTemperature_K: 1800 },
    energyBalance: { input_J: 1, losses_J: .2, stored_J: .8, relativeError: 0 },
    discretization: { cells: 1210, mesh_m: 40e-6, minimumDt_s: 1e-7,
      maximumDt_s: 2e-7, meanDt_s: 2e-7, steps: 934 },
    gpuPilot: { status: 'pass', scope: 'same-model CPU/GPU numerical parity only',
      experimentalValidation: false, targets,
      cpu: { solver: { id: 'enthalpy-fv-6' },
        coreContract: { modelId: 'stationary-enthalpy-conduction-layer-conforming-v1', actualBackend: 'numpy-reference' },
        material: { materialRevisionSha256: sha },
        discretization: { cells: 1210, steps: 934, mesh_m: 40e-6 } },
      comparisons },
    provenance: { inputHash: sha, implementationHash: sha, materialVersion: '1', createdAt: '2026-09-23T00:00:00Z',
      deviceEvidence: { selected: 'cuda:0', name: 'NVIDIA GeForce RTX 4060 Laptop GPU',
        computeCapability: [8, 9], torch: '2.14', cudaRuntime: '12.6',
        thermalEvolution: 'cuda:0', sourceIntegration: 'cpu', sourceTimestepLimiter: 'cpu',
        synchronizedAfterSolve: true } },
    artifacts: [],
  },
};
const clone = () => structuredClone(completed);
const boundArchive = JSON.parse(readFileSync(new URL('../docs/LPBF_GPU_BOUND_ARCHIVE_ACCEPTANCE_2026-09-27/result.json', import.meta.url), 'utf8'));
const boundClone = () => ({ ...clone(), result: structuredClone(boundArchive) });

test('GPU pilot has its own parser and cannot be presented as standard LPBF evidence', () => {
  assert.equal(parseGpuPilotJob(clone()).result?.gpuPilot.status, 'pass');
  assert.throws(() => parseSimulationJob(clone()));
  const wrongBackend = clone(); wrongBackend.result.solver.actualBackend = 'numpy-reference';
  assert.throws(() => parseGpuPilotJob(wrongBackend), /identity/);
  const falseFieldPass = clone(); falseFieldPass.result.gpuPilot.comparisons.finalTemperatureField.relativeRiseL2 = .2;
  assert.throws(() => parseGpuPilotJob(falseFieldPass), /field parity/);
  const movedTarget = clone(); movedTarget.result.gpuPilot.targets.fieldRiseL2RelativeMax = .2;
  assert.throws(() => parseGpuPilotJob(movedTarget), /frozen parity targets/);
  const fakeExperiment = clone(); fakeExperiment.result.gpuPilot.experimentalValidation = true;
  assert.throws(() => parseGpuPilotJob(fakeExperiment), /identity/);
});

test('GPU client accepts the versioned bound archive while keeping its CPU core nested', () => {
  const response = boundClone();
  assert.equal(parseGpuPilotJob(response).result?.gpuRunContract?.runKind, 'gpu-thermal-pilot');
  assert.equal(parseGpuPilotJob(response).result?.gpuFieldArtifacts?.kind, 'lpbf-final-field-parity-evidence');
  assert.throws(() => parseSimulationJob(response));
  assert.equal(parseGpuPilotJob(clone()).result?.artifacts.length, 0);
});

test('GPU client rejects partial, malformed, or detached bound archive metadata', () => {
  const bad: Array<(response: any) => void> = [
    response => { response.result.gpuRunContract = null; },
    response => { delete response.result.gpuFieldArtifacts; },
    response => { response.result.coreContract = {}; },
    response => { response.result.gpuRunContract.capture.dtype = 'float32'; },
    response => { response.result.gpuRunContract.hashes.implementationHash = '0'.repeat(64); },
    response => { response.result.gpuRunContract.hashes.requestHash = '0'.repeat(64); },
    response => { response.result.gpuRunContract.hashes.requestHash = 'bad'; },
    response => { response.result.gpuRunContract.serializedInputs.requestJson = '{"changed":true}'; },
    response => { response.result.artifacts = response.result.artifacts.filter((item: any) => !item.path.includes('cpu-coordinates')); },
    response => { response.result.artifacts.push({ ...response.result.artifacts[0], path: '../escape.bin' }); },
    response => { response.result.artifacts.push({ ...response.result.artifacts[0], path: 'extra\u0000.json' }); },
    response => {
      const entry = response.result.artifacts.find((item: any) => item.path === 'gpu-pilot/cpu-temperature_K.f64le.bin');
      entry.path = entry.path.toUpperCase(); entry.sha256 = '0'.repeat(64);
    },
    response => { response.result.gpuFieldArtifacts.states.gpu.fields.temperature_K.sha256 = '0'.repeat(64); },
  ];
  for (const change of bad) {
    const response = boundClone(); change(response);
    assert.throws(() => parseGpuPilotJob(response));
  }
});

test('GPU pilot parser binds CPU or selected CUDA source and limiter devices', () => {
  const legacyCpu = clone();
  delete legacyCpu.result.provenance.deviceEvidence.sourceTimestepLimiter;
  assert.equal(parseGpuPilotJob(legacyCpu).result?.solver.sourceIntegrationDevice, 'cpu');

  const cudaSource = clone();
  cudaSource.result.solver.sourceIntegrationDevice = 'cuda:0';
  cudaSource.result.solver.sourceTimestepLimiterDevice = 'cuda:0';
  cudaSource.result.provenance.deviceEvidence.sourceIntegration = 'cuda:0';
  cudaSource.result.provenance.deviceEvidence.sourceTimestepLimiter = 'cuda:0';
  assert.equal(parseGpuPilotJob(cudaSource).result?.solver.sourceIntegrationDevice, 'cuda:0');

  const wrongDevice = structuredClone(cudaSource);
  wrongDevice.result.solver.sourceIntegrationDevice = 'cuda:1';
  wrongDevice.result.solver.sourceTimestepLimiterDevice = 'cuda:1';
  wrongDevice.result.provenance.deviceEvidence.sourceIntegration = 'cuda:1';
  wrongDevice.result.provenance.deviceEvidence.sourceTimestepLimiter = 'cuda:1';
  assert.throws(() => parseGpuPilotJob(wrongDevice), /identity/);

  const mismatchedLimiter = structuredClone(cudaSource);
  mismatchedLimiter.result.solver.sourceTimestepLimiterDevice = 'cpu';
  assert.throws(() => parseGpuPilotJob(mismatchedLimiter), /identity/);

  const invalidDevice = structuredClone(cudaSource);
  invalidDevice.result.provenance.deviceEvidence.sourceIntegration = 'cuda:bad';
  assert.throws(() => parseGpuPilotJob(invalidDevice), /identity/);
});

test('GPU pilot rejects parity scalars detached from the displayed result', () => {
  for (const key of ['peakTemperature_K', 'width_um', 'depth_um', 'length_um', 'volume_um3']) {
    const response = clone();
    response.result.metrics[key] *= 2;
    assert.throws(() => parseGpuPilotJob(response), /parity.*binding/, key);
  }
  const energy = clone();
  energy.result.energyBalance.input_J *= 2;
  energy.result.energyBalance.losses_J *= 2;
  energy.result.energyBalance.stored_J *= 2;
  assert.throws(() => parseGpuPilotJob(energy), /parity.*binding/);
  const failed = clone();
  failed.result.gpuPilot.status = 'failed';
  failed.result.gpuPilot.comparisons.finalTemperatureField.status = 'failed';
  failed.result.metrics.width_um *= 2;
  assert.throws(() => parseGpuPilotJob(failed), /parity.*binding/);
});

test('GPU pilot requires usable implementation and runtime provenance', () => {
  for (const change of [
    (r: any) => { delete r.provenance.inputHash; },
    (r: any) => { r.provenance.implementationHash = 'missing'; },
    (r: any) => { r.provenance.materialVersion = 'different'; },
    (r: any) => { r.provenance.createdAt = 'unknown'; },
    (r: any) => { delete r.provenance.deviceEvidence.torch; },
    (r: any) => { r.provenance.deviceEvidence.cudaRuntime = ''; },
    (r: any) => { r.provenance.deviceEvidence.computeCapability = [8]; },
  ]) {
    const response = clone(); change(response.result);
    assert.throws(() => parseGpuPilotJob(response), /identity/);
  }
});

test('GPU pilot client uses the existing job API and preserves explicit CUDA errors', async () => {
  const original = globalThis.fetch;
  const input = { jobType: 'gpu-thermal-pilot', backend: 'cuda:0', mode: 'standard',
    surfaceMode: 'powder-layer', study: 'none', tracks: 1, layers: 1,
    material: 'Inconel 718', power_W: 60, speed_mm_s: 1200,
    beamDiameter_um: 80, preheat_C: 25, layer_um: 80, hatch_um: 100 } as const;
  try {
    globalThis.fetch = async (url, init) => {
      assert.equal(url, '/api/lpbf/jobs');
      assert.equal(init?.method, 'POST');
      assert.deepEqual(JSON.parse(String(init?.body)), input);
      return new Response(JSON.stringify({ ...completed, status: 'queued', progress: 0, result: undefined }),
        { status: 202, headers: { 'Content-Type': 'application/json' } });
    };
    assert.equal((await gpuPilotApi.submit(input)).requestSummary.backend, 'cuda:0');
    globalThis.fetch = async () => new Response(JSON.stringify({ error: 'CUDA device cuda:0 unavailable; no CPU fallback' }),
      { status: 400, headers: { 'Content-Type': 'application/json' } });
    await assert.rejects(() => gpuPilotApi.submit(input), /no CPU fallback/);
  } finally { globalThis.fetch = original; }
});
