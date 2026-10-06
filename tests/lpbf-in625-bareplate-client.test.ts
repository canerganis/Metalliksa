import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import test from 'node:test';
import { buildIn625BareplateInput } from '../src/components/In625BareplatePanel';
import {
  fetchIn625BareplateTemperatureField, in625BareplateApi, parseIn625BareplateJob, parseGpuPilotJob, parseSimulationJob,
  type In625BareplateInput, type In625BareplateResult,
} from '../src/services/lpbfSimulationService';

const sha = 'a'.repeat(64);
const config = {
  shapeXYZ: [4, 3, 2] as [number, number, number],
  cellSizeM: [0.00025, 0.00025, 0.00025] as [number, number, number],
  initialTemperatureK: 298.15, dtS: 1e-5, steps: 2,
  absorbedPowerW: 20, spotSigmaM: 0.0004, scanStartXM: 0.0005,
  scanYM: 0.000375, scanVelocityXMS: 0,
};
const material = {
  schemaVersion: 1, materialId: 'in625', name: 'Inconel 625', version: '1',
  materialRevisionSha256: sha, temperatureCoverage_K: [273.15, 1623.15],
  validationStatus: 'unvalidated-literature-model-screening',
};
const makeJob = (backend: 'cpu' | 'cuda:0' = 'cuda:0') => {
  const input: In625BareplateInput = { jobType: 'in625-bareplate-field', backend, config };
  return {
    id: 'b'.repeat(32), status: 'completed', progress: 1, log: '', error: null,
    requestSummary: { jobType: 'in625-bareplate-field', backend },
    result: {
      schemaVersion: 1, jobType: 'in625-bareplate-field', runKind: 'bounded-material-screening',
      requestedMode: 'screening', effectiveMode: 'screening', fallbackReason: null,
      settings: input, material,
      solver: { id: 'in625-bareplate-field-v1', modelId: 'in625-bareplate-enthalpy-conduction-v1',
        revision: '1', actualBackend: backend, device: backend, dtype: 'float64' },
      validationStatus: 'unvalidated-literature-model-screening', productionReady: false,
      confidence: 'low', label: 'IN625 bare-substrate conduction screening',
      modelScope: '3D bounded enthalpy conduction on bare substrate; all faces adiabatic.',
      metrics: { cells: 24, peakTemperature_K: 298.151, finalTime_s: 2e-5,
        finalEnthalpy_J: 0.1, energyResidual_J: 1e-15, minimumSourceCaptureFraction: .99 },
      energyHistory: [{ time_s: 1e-5, totalEnthalpy_J: .1, peakTemperature_K: 298.151, energyResidual_J: 1e-15 },
        { time_s: 2e-5, totalEnthalpy_J: .2, peakTemperature_K: 298.152, energyResidual_J: 1e-15 }],
      energyBalance: { input_J: .0004, losses_J: 0, stored_J: .0004, relativeError: 0, scope: 'adiabatic enthalpy accounting' },
      field: { artifact: 'in625-temperature-field-f64le.bin', shapeXYZ: config.shapeXYZ,
        dtype: 'float64', encoding: 'little-endian', byteOrder: 'little-endian',
        arrayOrder: 'z,y,x', sha256: 'c'.repeat(64), scope: 'final cell-centered temperature field only; no interface interpolation' },
      numericalDiagnostics: { sourceCaptureFractionMinimum: .99, temperatureBounds_K: [273.15, 1623.15],
        density_kg_m3: 8440, densityBasis: 'constant supplier bulletin assumption; not lot-matched' },
      provenance: { inputSha256: sha, implementationIdentity: { modelId: 'in625-bareplate-enthalpy-conduction-v1',
        solverRevision: '1', materialRevisionSha256: sha, backend, device: backend },
        deviceEvidence: { selected: backend, thermalEvolution: backend, noCpuFallback: true,
          name: backend === 'cpu' ? 'NumPy CPU' : 'GPU', index: backend === 'cpu' ? null : 0,
          synchronizedAfterSolve: true } },
      artifacts: [{ path: 'in625-temperature-field-f64le.bin', size_bytes: 24 * 8, sha256: 'c'.repeat(64) }],
      assumptions: ['Density is a constant supplier-bulletin assumption.', 'No experimental validation.'],
    },
  };
};

test('IN625 panel builds only the explicit worker fields even if restored config has stale extras', () => {
  const configWithLegacyFields = { ...config, mode: 'standard', material: 'Inconel 718' } as typeof config;
  assert.deepEqual(buildIn625BareplateInput(configWithLegacyFields, 'cpu'), {
    jobType: 'in625-bareplate-field', backend: 'cpu', config,
  });
});

test('IN625 bare-plate uses a distinct parser and validates model, material, device and field identity', () => {
  assert.equal(parseIn625BareplateJob(makeJob()).result?.solver.modelId, 'in625-bareplate-enthalpy-conduction-v1');
  assert.equal(parseIn625BareplateJob(makeJob('cpu')).result?.solver.actualBackend, 'cpu');
  assert.throws(() => parseSimulationJob(makeJob()));
  assert.throws(() => parseGpuPilotJob(makeJob()));

  const wrongModel = structuredClone(makeJob()); wrongModel.result.solver.modelId = 'stationary-enthalpy-conduction-v1';
  assert.throws(() => parseIn625BareplateJob(wrongModel), /identity/);
  const wrongMaterial = structuredClone(makeJob()); wrongMaterial.result.material.materialRevisionSha256 = 'd'.repeat(64);
  assert.throws(() => parseIn625BareplateJob(wrongMaterial), /identity/);
  const wrongDevice = structuredClone(makeJob()); wrongDevice.result.provenance.deviceEvidence.selected = 'cpu';
  assert.throws(() => parseIn625BareplateJob(wrongDevice), /identity/);
  const wrongField = structuredClone(makeJob()); wrongField.result.field.shapeXYZ = [3, 3, 2];
  assert.throws(() => parseIn625BareplateJob(wrongField), /identity|Inconsistent/);
  const falseExperiment = structuredClone(makeJob()); falseExperiment.result.validationStatus = 'validated';
  assert.throws(() => parseIn625BareplateJob(falseExperiment), /identity/);
});

test('IN625 bare-plate API sends only its explicit contract and preserves unavailable-CUDA errors', async () => {
  const original = globalThis.fetch;
  const input: In625BareplateInput = { jobType: 'in625-bareplate-field', backend: 'cuda:0', config };
  try {
    globalThis.fetch = async (url, init) => {
      assert.equal(url, '/api/lpbf/jobs');
      assert.equal(init?.method, 'POST');
      assert.deepEqual(JSON.parse(String(init?.body)), input);
      return new Response(JSON.stringify(makeJob('cuda:0')), { status: 202, headers: { 'Content-Type': 'application/json' } });
    };
    assert.equal((await in625BareplateApi.submit(input)).requestSummary.backend, 'cuda:0');
    globalThis.fetch = async () => new Response(JSON.stringify({ error: 'CUDA is unavailable; explicit CUDA path cannot run' }),
      { status: 400, headers: { 'Content-Type': 'application/json' } });
    await assert.rejects(() => in625BareplateApi.submit(input), /explicit CUDA path cannot run/);
  } finally { globalThis.fetch = original; }
});

test('IN625 field download verifies manifest bytes and decodes little-endian temperatures', async () => {
  const original = globalThis.fetch;
  const values = Array.from({ length: 24 }, (_, index) => 300 + index / 10);
  const bytes = new Uint8Array(values.length * Float64Array.BYTES_PER_ELEMENT);
  const view = new DataView(bytes.buffer);
  values.forEach((value, index) => view.setFloat64(index * Float64Array.BYTES_PER_ELEMENT, value, true));
  const digest = createHash('sha256').update(bytes).digest('hex');
  const job = makeJob('cpu');
  job.result.field.sha256 = digest;
  job.result.artifacts[0].sha256 = digest;
  try {
    globalThis.fetch = async (url) => {
      assert.equal(url, '/api/lpbf/jobs/' + 'b'.repeat(32) + '/artifacts/in625-temperature-field-f64le.bin');
      return new Response(bytes, { status: 200, headers: { 'Content-Type': 'application/octet-stream' } });
    };
    const result = job.result as unknown as In625BareplateResult;
    const field = await fetchIn625BareplateTemperatureField('b'.repeat(32), result);
    assert.deepEqual([...field.temperaturesK], values);
    assert.equal(field.sha256, digest);
    globalThis.fetch = async () => new Response(bytes,
      { status: 200, headers: { 'Content-Type': 'application/octet-stream' } });
    job.result.field.sha256 = 'd'.repeat(64);
    job.result.artifacts[0].sha256 = 'd'.repeat(64);
    await assert.rejects(() => fetchIn625BareplateTemperatureField('b'.repeat(32), result), /SHA-256 mismatch/);
    globalThis.fetch = async () => new Response(bytes,
      { status: 200, headers: { 'Content-Type': 'application/json' } });
    await assert.rejects(() => fetchIn625BareplateTemperatureField('b'.repeat(32), result), /content type/);
  } finally { globalThis.fetch = original; }
});
