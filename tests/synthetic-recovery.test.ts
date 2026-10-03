import assert from 'node:assert/strict';
import { test } from 'node:test';
import { buildSyntheticDataset, computeCleanSpectrum, injectSyntheticNoise, evaluateAutoFitRobustness,
  DEFAULT_SYNTHETIC_NOISE_CONFIG as defaults, runNoiseSweepStressTest } from '../src/utils/syntheticEISNoiseGenerator';
import { runAsyncAutoFit, runCNLSFit, extractAdjustableParameters, evaluateKramersKronig } from '../src/utils/cnlsOptimizer';
import type { CircuitTopology } from '../src/components/EquivalentCircuitBuilder';
import type { CNLSFitReport } from '../src/types/eisData';

const topology: CircuitTopology = { id:'r', name:'Synthetic resistor', description:'', category:'custom', cdcNotation:'R',
  branches:[{id:'b', name:'Series', connection:'series', elements:[{id:'R', name:'R', label:'R', description:'Resistance element.', type:'R', value:20, unit:'Ohm', isFixed:false}]}] };
const clean = computeCleanSpectrum(topology, [100,10,1]);
const config = {...defaults, randomSeed:37};
const points = injectSyntheticNoise(clean, config);
const dataset = buildSyntheticDataset(points, topology, config);

test('synthetic dataset records seed and config without invented measurement conditions', () => {
  assert.equal(dataset.metadata?.dataOrigin, 'synthetic');
  assert.equal(dataset.metadata?.noiseConfig.randomSeed, 37);
  for (const key of ['temperatureC','potentialV','acAmplitudeMv','electrodeAreaCm2']) assert.equal(dataset.metadata?.[key], undefined);
  assert.deepEqual(injectSyntheticNoise(clean, config), points);
});

test('missing recovery is unavailable, never ground truth, NaN or arbitrary failure score', () => {
  const report = {parameters:[], topology, dataset, rSquared:null, converged:false} as CNLSFitReport;
  const result = evaluateAutoFitRobustness(topology, points, config, report);
  for (const key of ['recoveredValue','stdError','absError','pctError','isReliable']) assert.equal(result.parameterErrors[0][key], null, key);
  for (const key of ['meanAbsolutePctError','maxAbsolutePctError','robustnessScore','robustnessGrade']) assert.equal(result[key], null, key);
  assert.equal(result.linKKStationarity.isStationary, null);
  assert.equal(result.inductanceDeembedded.detectedInductance_uH, null);
  assert.equal(result.inductanceDeembedded.recoveredTrueRs, null);
});

test('unvalidated synchronous solver and client KK cannot claim scientific results', () => {
  assert.throws(() => runCNLSFit(topology, dataset), /Python/);
  const kk = evaluateKramersKronig(dataset);
  assert.equal(kk.isValid, null);
  assert.equal(kk.score, null);
  assert.equal(kk.meanResidualPct, null);
});

test('observed recovery preserves actual errors, undefined percentages and unavailable uncertainty', () => {
  const report = {parameters:[{elementId:'R', field:'value', fittedValue:22, stdError:null}],
    topology, dataset, rSquared:-2, converged:false} as CNLSFitReport;
  const result = evaluateAutoFitRobustness(topology, points, config, report);
  assert.equal(result.parameterErrors[0].absError, 2);
  assert.equal(result.meanAbsolutePctError, 10);
  assert.equal(result.parameterErrors[0].stdError, null);
  assert.equal(result.parameterErrors[0].isReliable, null);
  assert.equal(result.rSquared, -2);
  const zero = structuredClone(topology);
  zero.branches[0].elements[0].value = 0;
  const missingPercentage = evaluateAutoFitRobustness(zero, points, config, report);
  assert.equal(missingPercentage.parameterErrors[0].absError, 22);
  assert.equal(missingPercentage.parameterErrors[0].pctError, null);
  assert.equal(missingPercentage.meanAbsolutePctError, null);
});

test('an already invalidated noise sweep starts no Python computation', async () => {
  const original = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => { calls++; throw new Error('Unexpected request'); };
  const controller = new AbortController(); controller.abort();
  try {
    await assert.rejects(runNoiseSweepStressTest(topology, clean, config, [1,2], 'modulus', {signal:controller.signal}), /abort/i);
    assert.equal(calls, 0);
  } finally { globalThis.fetch = original; }
});

test('autofit sends the exact displayed spectrum with configured options and abort signal', async () => {
  const original = globalThis.fetch;
  const abort = new AbortController();
  let body: any, receivedSignal: any;
  globalThis.fetch = async (_url, init) => {
    body = JSON.parse(String(init?.body)); receivedSignal = init?.signal;
    return new Response('{}', {status:503});
  };
  try {
    await assert.rejects(runAsyncAutoFit(topology, dataset, undefined, 'modulus', 3,
      {signal:abort.signal, populationSize:5, polishLM:false, randomSeed:37}), /HTTP 503/);
    assert.deepEqual(body.points, dataset.points);
    assert.equal(body.populationSize, 5);
    assert.equal(body.polishLM, false);
    assert.equal(body.randomSeed, 37);
    assert.equal(receivedSignal, abort.signal);
  } finally { globalThis.fetch = original; }
});

test('noise sweep rejects a failed Python fit without a client success fallback', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response('{}', {status:503});
  try {
    await assert.rejects(async () => await runNoiseSweepStressTest(topology, clean, config, [0.1]), /HTTP 503/);
  } finally { globalThis.fetch = original; }
});
