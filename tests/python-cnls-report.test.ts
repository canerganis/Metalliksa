import assert from 'node:assert/strict';
import { test } from 'node:test';
import { normalizePythonCnlsReport } from '../src/utils/pythonCnlsReport';
import type { CircuitTopology } from '../src/components/EquivalentCircuitBuilder';
import type { ExperimentalEISDataset } from '../src/types/eisData';
import { runAsyncAutoFit } from '../src/utils/cnlsOptimizer';

const topology: CircuitTopology = { id: 'fixture', name: 'Synthetic resistor', description: '', category: 'custom', cdcNotation: 'R', branches: [
  { id: 'b1', name: 'Series', connection: 'series', elements: [{ id: 'r1', name: 'R1', label: 'Resistance', description: 'Resistance element.', type: 'R', value: 3, unit: 'Ω', isFixed: false }] },
] };
const dataset: ExperimentalEISDataset = { id: 'fixture', name: 'Synthetic', source: 'csv', description: '', points: [{frequency:10, zReal:2, minusZImag:0, zImag:0, zMag:2, phaseDeg:0}] };
const response = {
  success: true, reducedChiSquare: 0, rSquared: 0, iterations: 0, computeTimeMs: 0,
  parameters: [{ elementId: 'r1', field: 'value', paramName: 'R1', paramType: 'R', unit: 'Ω', initialValue: 3, fittedValue: 2, stdError: 0, percentError: 0, isFixed: false }],
  residuals: [{ frequency: 10, logFreq: 1, expZReal: 2, expMinusZImag: 0, calcZReal: 2, calcMinusZImag: 0, resZRealPct: 0, resZImagPct: 0 }],
  kramersKronig: { isValid: false, score: 0, meanResidualPct: 0, maxResidualPct: 0, assessment: 'Synthetic fixture' },
};
const inputParams = [{ branchId: 'b1', elementId: 'r1', field: 'value' as const, lowerBound: 0, upperBound: 10 }];

test('fitted topology used by preview and Apply contains returned values without mutating initial input', () => {
  const report = normalizePythonCnlsReport(response, topology, dataset, 'unit', inputParams);
  assert.equal(report.topology.branches[0].elements[0].value, 2);
  assert.equal(topology.branches[0].elements[0].value, 3);
});

test('Python CNLS normalization preserves zero metrics, calculates RMSE and does not invent convergence', () => {
  const report = normalizePythonCnlsReport(response, topology, dataset, 'modulus', inputParams);
  assert.equal(report.reducedChiSquare, 0);
  assert.equal(report.rSquared, 0);
  assert.equal(report.executionTimeMs, 0);
  assert.equal(report.iterations, 0);
  assert.equal(report.rmse, 0);
  assert.equal(report.converged, false);
  assert.equal(report.parameters[0].branchId, 'b1');
  assert.equal(report.parameters[0].fittedValue, 2);
});

test('incomplete Python CNLS response is rejected, not repaired with plausible metrics', () => {
  for (const field of ['reducedChiSquare', 'rSquared', 'computeTimeMs', 'parameters', 'residuals']) {
    assert.throws(() => normalizePythonCnlsReport({ ...response, [field]: undefined }, topology, dataset, 'modulus', inputParams), /CNLS/);
  }
});

test('explicitly unavailable uncertainty and K-K assessment survive normalization', () => {
  const report = normalizePythonCnlsReport({ ...response, rSquared: null,
    parameters: response.parameters.map(p => ({...p, stdError:null, percentError:null})),
    kramersKronig: {...response.kramersKronig, isValid:null, score:null},
  }, topology, dataset, 'unit', inputParams);
  assert.equal(report.rSquared, null);
  assert.equal(report.parameters[0].stdError, null);
  assert.equal(report.kramersKronig.isValid, null);
});

test('missing, duplicate and mismatched rows cannot become a current CNLS fit', () => {
  for (const changed of [
    {parameters:[...response.parameters, ...response.parameters]},
    {residuals:[]}, {residuals:[{...response.residuals[0], frequency:99}]},
    {residuals:[{...response.residuals[0], expZReal:3}]},
    {parameters:[{...response.parameters[0], fittedValue:100}]},
  ]) assert.throws(() => normalizePythonCnlsReport({...response,...changed}, topology, dataset, 'unit', inputParams), /CNLS/);
});

test('async Python autofit rejects HTTP and partial reports instead of falling back', async () => {
  const originalFetch = globalThis.fetch;
  const params = [{...inputParams[0], paramName:'R1', paramType:'R', value:3, initialValue:3, unit:'Ω', isFixed:false}];
  try {
    globalThis.fetch = async () => new Response('{"error":"controlled failure"}', {status:503});
    await assert.rejects(runAsyncAutoFit(topology, dataset, params), /HTTP 503/);
    globalThis.fetch = async () => Response.json({success:true});
    await assert.rejects(runAsyncAutoFit(topology, dataset, params), /CNLS/);
    globalThis.fetch = async () => Response.json(response);
    const fit = await runAsyncAutoFit(topology, dataset, params);
    assert.equal(fit.reducedChiSquare, 0);
    assert.equal(fit.executionTimeMs, 0);
  } finally { globalThis.fetch = originalFetch; }
});
