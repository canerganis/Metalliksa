import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { parseBoundedJson, strictJsonEqual } from '../server/lpbfBoundJson';
import { validateGpuPilotRunIdentity } from '../server/lpbfGpuRunIdentity';
import { localGpuPilotArtifactResolver, readGpuPilotArtifactsFromManifest } from '../server/lpbfGpuPilotArtifacts';
import { computeGpuPilotEnthalpyIntegral, expectedGpuPilotScanEnd_s, PARITY_TARGETS,
  stableGpuPilotNorm, validateGpuPilotNumerics } from '../server/lpbfGpuPilotNumerics';

const fixtureRoot = path.resolve('docs/LPBF_GPU_NATIVE_WORKER_ACCEPTANCE_RETRY_2026-09-27/2bcb01e5799041ec9458a947506d491f');
const resultFile = path.join(fixtureRoot, 'result.json');
function fixture() { return parseBoundedJson(readFileSync(resultFile, 'utf8')).value as any; }
function sha(value: string) { return createHash('sha256').update(Buffer.from(value, 'utf8')).digest('hex'); }
function copy<T>(value: T): T { return structuredClone(value); }
function failedField(result: any) {
  result.gpuPilot.comparisons.finalSampling.status = 'failed';
  const field = result.gpuPilot.comparisons.finalTemperatureField;
  field.status = 'failed'; field.reason = 'Archived CPU/GPU sampling grids differ.';
  delete field.relativeRiseL2; delete field.relativeRiseMax;
  result.gpuPilot.status = 'failed';
}
function nextUp(value: number) {
  const bytes = new ArrayBuffer(8), view = new DataView(bytes);
  view.setFloat64(0, value);
  view.setBigUint64(0, view.getBigUint64(0) + 1n);
  return view.getFloat64(0);
}

test('bounded JSON rejects duplicates, non-finite values, excessive depth, and noncanonical Python tokens', () => {
  assert.throws(() => parseBoundedJson('{"a":1,"\\u0061":2}'));
  assert.throws(() => parseBoundedJson('{"x":1e999}'));
  assert.throws(() => parseBoundedJson('9007199254740993'));
  assert.throws(() => parseBoundedJson(`${'['.repeat(130)}0${']'.repeat(130)}`));
  const parsed = parseBoundedJson('{ "z":1.0, "a":"a" }');
  assert.equal(parsed.pythonCompactJson(), '{"a":"a","z":1.0}');
  assert.equal(parseBoundedJson('{"large":1e+20,"small":1e-06,"float":1.0}')
    .pythonCompactJson(), '{"float":1.0,"large":1e+20,"small":1e-06}');
  assert.throws(() => parseBoundedJson('{"float":1.00}').pythonCompactJson());
  assert.equal(parseBoundedJson('{"integer":9007199254740991}').pythonCompactJson(), '{"integer":9007199254740991}');
  assert.throws(() => parseBoundedJson('{"name":"\\u0049nconel"}').pythonCompactJson());
  assert.throws(() => parseBoundedJson('{"latentHeat":2.7e5}').pythonCompactJson());
  assert.equal(strictJsonEqual(true, 1), false);
  assert.equal(strictJsonEqual({ n: 1 }, { n: 1.0 }), true);
});

test('actual bound GPU result retains exact strings and validates historical CPU/material core hashes', () => {
  const result = fixture();
  const identity = validateGpuPilotRunIdentity(result);
  assert.equal(identity.hashes.requestHash, result.provenance.inputHash);
  const reordered = copy(result);
  const request = JSON.parse(reordered.gpuRunContract.serializedInputs.requestJson);
  reordered.gpuRunContract.serializedInputs.requestJson = ` ${JSON.stringify(request, Object.keys(request).sort(), 1)} `;
  const requestHash = sha(reordered.gpuRunContract.serializedInputs.requestJson);
  reordered.gpuRunContract.hashes.requestHash = requestHash;
  reordered.provenance.inputHash = requestHash;
  reordered.gpuRunContract.serializedInputs.materialJson = ` ${reordered.gpuRunContract.serializedInputs.materialJson} `;
  reordered.gpuRunContract.hashes.materialHash = sha(reordered.gpuRunContract.serializedInputs.materialJson);
  assert.doesNotThrow(() => validateGpuPilotRunIdentity(reordered));
  const escapedString = copy(result);
  escapedString.gpuRunContract.serializedInputs.materialJson = escapedString.gpuRunContract.serializedInputs.materialJson
    .replace('"name": "Inconel 718"', '"name": "\\u0049nconel 718"');
  escapedString.gpuRunContract.hashes.materialHash = sha(escapedString.gpuRunContract.serializedInputs.materialJson);
  assert.throws(() => validateGpuPilotRunIdentity(escapedString), /invalid or over-budget/i);
  const alternateFloat = copy(result);
  alternateFloat.gpuRunContract.serializedInputs.materialJson = alternateFloat.gpuRunContract.serializedInputs.materialJson
    .replace('"latentHeat_J_kg": 270000.0', '"latentHeat_J_kg": 2.7e5');
  alternateFloat.gpuRunContract.hashes.materialHash = sha(alternateFloat.gpuRunContract.serializedInputs.materialJson);
  assert.throws(() => validateGpuPilotRunIdentity(alternateFloat), /invalid or over-budget/i);
  const roundedInteger = copy(result);
  roundedInteger.gpuRunContract.serializedInputs.requestJson = roundedInteger.gpuRunContract.serializedInputs.requestJson
    .replace('"power_W": 60', '"power_W": 9007199254740993');
  roundedInteger.gpuRunContract.hashes.requestHash = sha(roundedInteger.gpuRunContract.serializedInputs.requestJson);
  roundedInteger.provenance.inputHash = roundedInteger.gpuRunContract.hashes.requestHash;
  assert.throws(() => validateGpuPilotRunIdentity(roundedInteger), /invalid or over-budget/i);
  reordered.gpuRunContract.hashes.requestHash = '0'.repeat(64);
  assert.throws(() => validateGpuPilotRunIdentity(reordered), /detached|hash/i);
});

test('actual manifest accepts additional captured files but rejects field path case mismatch', async () => {
  const result = fixture();
  const manifest = copy(result.artifacts);
  manifest.push({ path: 'additional-evidence.bin', size_bytes: 0, sha256: sha(Buffer.alloc(0).toString()) });
  const states = await readGpuPilotArtifactsFromManifest(manifest, result.gpuFieldArtifacts, localGpuPilotArtifactResolver(fixtureRoot));
  assert.equal(states.cpu.arrays.coordinates_m.length, 1210 * 3);
  const altered = copy(manifest);
  const target = altered.find((entry: any) => entry.path === 'gpu-pilot/cpu-temperature_K.f64le.bin');
  target.path = target.path.toUpperCase();
  await assert.rejects(readGpuPilotArtifactsFromManifest(altered, result.gpuFieldArtifacts,
    localGpuPilotArtifactResolver(fixtureRoot)), /manifest/i);
});

test('actual bound GPU byte fields recompute parity summaries without changing stored threshold decisions', async () => {
  const result = fixture();
  validateGpuPilotRunIdentity(result);
  const states = await readGpuPilotArtifactsFromManifest(result.artifacts, result.gpuFieldArtifacts,
    localGpuPilotArtifactResolver(fixtureRoot));
  assert.equal(validateGpuPilotNumerics(result, states, PARITY_TARGETS).status, 'pass');
  const altered = copy(result), moved = copy(states);
  moved.gpu.arrays.coordinates_m[0] = 1e-4;
  failedField(altered);
  assert.equal(validateGpuPilotNumerics(altered, moved, PARITY_TARGETS).temperatureField.normsRecomputed, false);
  const threshold = copy(result);
  threshold.gpuPilot.comparisons.finalTemperatureField.relativeRiseL2 = .01;
  threshold.gpuPilot.comparisons.finalTemperatureField.relativeRiseMax = 0;
  threshold.gpuPilot.comparisons.finalTemperatureField.status = 'pass';
  assert.throws(() => validateGpuPilotNumerics(threshold, states, PARITY_TARGETS), /norms conflict/i);
});

test('numeric helper reports grid mismatch without norms, leaves timestep order to the reader, and checks cancellation safely', async () => {
  const result = fixture();
  const states = await readGpuPilotArtifactsFromManifest(result.artifacts, result.gpuFieldArtifacts,
    localGpuPilotArtifactResolver(fixtureRoot));
  const mismatched = copy(result), mismatchStates = copy(states);
  const nonzeroCoordinate = mismatchStates.gpu.arrays.coordinates_m.findIndex(value => value !== 0);
  assert.ok(nonzeroCoordinate >= 0);
  mismatchStates.gpu.arrays.coordinates_m[nonzeroCoordinate] = nextUp(mismatchStates.gpu.arrays.coordinates_m[nonzeroCoordinate]);
  failedField(mismatched);
  assert.equal(validateGpuPilotNumerics(mismatched, mismatchStates, PARITY_TARGETS).temperatureField.normsRecomputed, false);
  const oneUlp = copy(states), oneUlpResult = copy(result);
  oneUlp.gpu.arrays.coordinates_m[0] = nextUp(oneUlp.gpu.arrays.coordinates_m[0]);
  failedField(oneUlpResult);
  assert.equal(validateGpuPilotNumerics(oneUlpResult, oneUlp, PARITY_TARGETS).temperatureField.normsRecomputed, false);
  const reordered = copy(states);
  reordered.cpu.arrays.accepted_dt_s.reverse();
  assert.equal(validateGpuPilotNumerics(result, reordered, PARITY_TARGETS).status, 'pass');
  const signedZero = copy(states);
  const zeroIndex = signedZero.cpu.arrays.coordinates_m.findIndex(value => value === 0);
  assert.ok(zeroIndex >= 0);
  signedZero.cpu.arrays.coordinates_m[zeroIndex] = -0;
  signedZero.gpu.arrays.coordinates_m[zeroIndex] = 0;
  assert.equal(validateGpuPilotNumerics(result, signedZero, PARITY_TARGETS).status, 'pass');
  const staleScalar = copy(result);
  staleScalar.gpuPilot.comparisons.input_J.relativeDifference = nextUp(staleScalar.gpuPilot.comparisons.input_J.relativeDifference);
  assert.throws(() => validateGpuPilotNumerics(staleScalar, states, PARITY_TARGETS), /input_J comparison mismatch/i);
  const cancellation = computeGpuPilotEnthalpyIntegral(new Float64Array([1e12, 1, -1e12, 1]), 1e-18);
  assert.equal(cancellation.integral, 2e-18);
  assert.throws(() => computeGpuPilotEnthalpyIntegral(new Float64Array([1e-308]), 1e-308), /underflow/i);
  assert.equal(computeGpuPilotEnthalpyIntegral(new Float64Array([0, 0]), 1e-18).integral, 0);
  assert.equal(stableGpuPilotNorm(new Float64Array([1e200, 0])), 1e200);
});

test('stored norm thresholds are exact while recomputed norms use only an integrity envelope', async () => {
  const result = fixture();
  const states = await readGpuPilotArtifactsFromManifest(result.artifacts, result.gpuFieldArtifacts,
    localGpuPilotArtifactResolver(fixtureRoot));
  const near = copy(states), archived = copy(result), t0 = near.cpu.metadata.initial_temperature_K;
  near.cpu.arrays.temperature_K.fill(t0); near.gpu.arrays.temperature_K.fill(t0);
  near.cpu.arrays.temperature_K[0] = t0 + 1000;
  near.gpu.arrays.temperature_K[0] = nextUp(t0 + 1010);
  archived.gpuPilot.comparisons.finalTemperatureField.relativeRiseL2 = .01;
  archived.gpuPilot.comparisons.finalTemperatureField.relativeRiseMax = .01;
  assert.equal(validateGpuPilotNumerics(archived, near, PARITY_TARGETS).status, 'pass');
  archived.gpuPilot.comparisons.finalTemperatureField.relativeRiseMax = nextUp(.01);
  archived.gpuPilot.comparisons.finalTemperatureField.status = 'failed';
  archived.gpuPilot.status = 'failed';
  assert.equal(validateGpuPilotNumerics(archived, near, PARITY_TARGETS).status, 'failed');
});

test('different valid accepted step counts remain a failed, norm-free parity result', async () => {
  const result = fixture();
  const states = await readGpuPilotArtifactsFromManifest(result.artifacts, result.gpuFieldArtifacts,
    localGpuPilotArtifactResolver(fixtureRoot));
  const changed = copy(result), decoded = copy(states), steps = 933;
  const time = decoded.gpu.metadata.time_s, dt = time / steps;
  decoded.gpu.metadata.steps = steps;
  decoded.gpu.arrays.accepted_dt_s = new Float64Array(steps).fill(dt);
  changed.gpuFieldArtifacts.states.gpu.steps = steps;
  changed.discretization.steps = steps; changed.discretization.minimumDt_s = dt;
  changed.discretization.maximumDt_s = dt; changed.discretization.meanDt_s = dt;
  changed.gpuPilot.comparisons.finalSampling.gpuSteps = steps;
  failedField(changed);
  const proof = validateGpuPilotNumerics(changed, decoded, PARITY_TARGETS);
  assert.equal(proof.status, 'failed');
  assert.equal(proof.temperatureField.normsRecomputed, false);
});

test('different cell counts and final observer times become failed results without fabricated norms', async () => {
  const result = fixture();
  const states = await readGpuPilotArtifactsFromManifest(result.artifacts, result.gpuFieldArtifacts,
    localGpuPilotArtifactResolver(fixtureRoot));
  const cellResult = copy(result), cellStates = copy(states), cells = 1209;
  const backend = 'gpu' as const;
  cellStates[backend].metadata.cells = cells;
  cellStates[backend].arrays.coordinates_m = cellStates[backend].arrays.coordinates_m.slice(0, cells * 3);
  cellStates[backend].arrays.temperature_K = cellStates[backend].arrays.temperature_K.slice(0, cells);
  cellStates[backend].arrays.enthalpy_J_m3 = cellStates[backend].arrays.enthalpy_J_m3.slice(0, cells);
  cellStates[backend].arrays.density_kg_m3 = cellStates[backend].arrays.density_kg_m3.slice(0, cells);
  cellResult.gpuFieldArtifacts.states[backend].cells = cells;
  cellResult.discretization.cells = cells;
  const stored = cellResult.gpuPilot.comparisons.stored_J;
  for (const backend of ['cpu', 'gpu'] as const) {
    stored[backend] = computeGpuPilotEnthalpyIntegral(cellStates[backend].arrays.enthalpy_J_m3,
      cellStates[backend].metadata.cell_volume_m3).integral;
  }
  cellResult.energyBalance.stored_J = stored.gpu;
  stored.relativeDifference = Math.abs(stored.cpu - stored.gpu) / Math.max(Math.abs(stored.cpu), 1e-30);
  stored.status = stored.relativeDifference <= PARITY_TARGETS.integralRelativeMax ? 'pass' : 'failed';
  failedField(cellResult);
  assert.equal(validateGpuPilotNumerics(cellResult, cellStates, PARITY_TARGETS).temperatureField.normsRecomputed, false);

  const timeResult = copy(result), timeStates = copy(states);
  timeResult.gpuPilot.comparisons.finalSampling.cpuFrameTime_s = 0.0001865;
  failedField(timeResult);
  assert.equal(validateGpuPilotNumerics(timeResult, timeStates, PARITY_TARGETS).temperatureField.normsRecomputed, false);
});

test('boolean numeric impostors and malformed scalar reports fail even on an archived failed run', async () => {
  const result = fixture();
  const states = await readGpuPilotArtifactsFromManifest(result.artifacts, result.gpuFieldArtifacts,
    localGpuPilotArtifactResolver(fixtureRoot));
  const badDifference = copy(result);
  badDifference.gpuPilot.comparisons.input_J.relativeDifference = false;
  assert.throws(() => validateGpuPilotNumerics(badDifference, states, PARITY_TARGETS), /relative difference/i);
  const badTarget = copy(result);
  badTarget.gpuPilot.targets.widthDepthAbsoluteCellsMax = true;
  assert.throws(() => validateGpuPilotNumerics(badTarget, states, PARITY_TARGETS), /targets differ/i);
  const failedScalar = copy(result);
  failedScalar.gpuPilot.comparisons.peakTemperature_K.gpu = 1900;
  failedScalar.gpuPilot.comparisons.peakTemperature_K.relativeDifference =
    Math.abs(failedScalar.gpuPilot.comparisons.peakTemperature_K.cpu - 1900)
      / Math.abs(failedScalar.gpuPilot.comparisons.peakTemperature_K.cpu);
  failedScalar.gpuPilot.comparisons.peakTemperature_K.status = 'failed';
  failedScalar.metrics.peakTemperature_K = 1900;
  failedScalar.gpuPilot.status = 'failed';
  assert.equal(validateGpuPilotNumerics(failedScalar, states, PARITY_TARGETS).status, 'failed');
  failedScalar.gpuPilot.comparisons.input_J.relativeDifference = .125;
  assert.throws(() => validateGpuPilotNumerics(failedScalar, states, PARITY_TARGETS), /input_J comparison mismatch/i);
});

test('one-cell geometry threshold is inclusive and signed-zero dimensions are inconclusive', async () => {
  const result = fixture();
  const states = await readGpuPilotArtifactsFromManifest(result.artifacts, result.gpuFieldArtifacts,
    localGpuPilotArtifactResolver(fixtureRoot));
  const edge = copy(result), width = edge.gpuPilot.comparisons.width_um;
  width.cpu = 40; width.gpu = 80; width.absoluteDifference_um = 40;
  edge.metrics.width_um = 80;
  assert.equal(validateGpuPilotNumerics(edge, states, PARITY_TARGETS).status, 'pass');
  width.gpu = nextUp(80); width.absoluteDifference_um = width.gpu - width.cpu;
  edge.metrics.width_um = width.gpu; width.status = 'failed'; edge.gpuPilot.status = 'failed';
  assert.equal(validateGpuPilotNumerics(edge, states, PARITY_TARGETS).status, 'failed');
  const zero = copy(result);
  for (const key of ['width_um', 'depth_um', 'length_um']) {
    zero.metrics[key] = 0;
    zero.gpuPilot.comparisons[key] = { cpu: -0, gpu: 0, absoluteDifference_um: 0, status: 'inconclusive' };
  }
  zero.gpuPilot.status = 'inconclusive';
  assert.equal(validateGpuPilotNumerics(zero, states, PARITY_TARGETS).status, 'inconclusive');
});

test('expected end includes every segment dwell and final cooling for meander and island grids', () => {
  const meander = expectedGpuPilotScanEnd_s({ layers: 2, tracks: 3, trackLength_um: 250, speed_mm_s: 1000,
    dwell_s: 10e-6, cooling_s: 20e-6, strategy: 'meander', stripeWidth_um: 100, hatch_um: 40 });
  assert.ok(Math.abs(meander - 1.58e-3) < 1e-18);
  const island = expectedGpuPilotScanEnd_s({ layers: 1, tracks: 6, trackLength_um: 250, speed_mm_s: 1000,
    dwell_s: 10e-6, cooling_s: 20e-6, strategy: 'island', islandSize_um: 100, hatch_um: 50 });
  assert.ok(Math.abs(island - 1.7e-3) < 1e-18);
  const partialIslandRow = expectedGpuPilotScanEnd_s({ preheat_C: 80, trackLength_um: 250, speed_mm_s: 1000,
    layers: 2, scanAngle_deg: 0, layerRotation_deg: 67, tracks: 3, strategy: 'island', hatch_um: 40,
    stripeWidth_um: 500, islandSize_um: 100, dwell_s: 10e-6, cooling_s: 20e-6 });
  assert.ok(Math.abs(partialIslandRow - 1.7e-3) < 1e-18);
  assert.throws(() => expectedGpuPilotScanEnd_s({ layers: 1, tracks: 1, trackLength_um: 200,
    speed_mm_s: 1, dwell_s: 0, cooling_s: 0, strategy: 'island', islandSize_um: Number.MIN_VALUE, hatch_um: 100 }));
});
