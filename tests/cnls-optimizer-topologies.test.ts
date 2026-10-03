import assert from 'node:assert/strict';
import { test } from 'node:test';
import { applyParametersToTopology, evalTopologyImpedance, evaluateKramersKronig, extractAdjustableParameters,
  runAsyncAutoFit, runCNLSFit } from '../src/utils/cnlsOptimizer';
import type { CircuitElement, CircuitTopology } from '../src/components/EquivalentCircuitBuilder';
import type { ExperimentalEISDataset } from '../src/types/eisData';

// Note: runCNLSFit is a retired stub and runAsyncAutoFit delegates to the Python API, so Randles parameter
// recovery cannot be exercised client-side. These tests cover the local forward model and parameter plumbing.

const el = (id: string, type: CircuitElement['type'], value: number, exponent?: number): CircuitElement =>
  ({ id, type, name: id, label: id, value, unit: type === 'R' ? 'Ohm' : 'F', ...(exponent === undefined ? {} : { exponent }), isFixed: false, description: '' });

const randles = (): CircuitTopology => ({
  id: 'randles', name: 'Randles', description: '', category: 'custom', cdcNotation: 'R(RC)',
  branches: [
    { id: 'b1', name: 'Series', connection: 'series', elements: [el('Rs', 'R', 5)] },
    { id: 'b2', name: 'Interface', connection: 'parallel', elements: [el('Rct', 'R', 100), el('Cdl', 'C', 2e-5)] },
  ],
});

const randlesCpe = (): CircuitTopology => ({
  ...randles(),
  branches: [
    randles().branches[0],
    { id: 'b2', name: 'Interface', connection: 'parallel', elements: [el('Rct', 'R', 100), el('Qdl', 'CPE', 3e-5, 0.85)] },
  ],
});

const dataset: ExperimentalEISDataset = {
  id: 'd', name: 'd', source: 'csv', description: '',
  points: [1e5, 1e3, 10].map((f) => ({ frequency: f, zReal: 10, zImag: -1, minusZImag: 1, zMag: Math.hypot(10, 1), phaseDeg: -5.7 })),
};

test('Randles forward model matches Rs + Rct/(1 + jw Rct C) over six decades', () => {
  const [Rs, Rct, C] = [5, 100, 2e-5];
  for (const f of [0.01, 1, 100, 1e4, 1e6]) {
    const w = 2 * Math.PI * f, d = 1 + (w * Rct * C) ** 2;
    const z = evalTopologyImpedance(randles(), w);
    assert.ok(Math.abs(z.re - (Rs + Rct / d)) < 1e-9 * (Rs + Rct), `re at ${f} Hz`);
    assert.ok(Math.abs(z.im + (w * Rct * Rct * C) / d) < 1e-9 * (Rs + Rct), `im at ${f} Hz`);
  }
});

test('Randles with a CPE matches the closed form with (jw)^n', () => {
  const [Rs, Rct, Q, n] = [5, 100, 3e-5, 0.85];
  for (const f of [0.1, 10, 1e3, 1e5]) {
    const w = 2 * Math.PI * f;
    const yRe = 1 / Rct + Q * Math.pow(w, n) * Math.cos((n * Math.PI) / 2);
    const yIm = Q * Math.pow(w, n) * Math.sin((n * Math.PI) / 2);
    const m = yRe * yRe + yIm * yIm;
    const z = evalTopologyImpedance(randlesCpe(), w);
    assert.ok(Math.abs(z.re - (Rs + yRe / m)) < 1e-9 * (Rs + Rct));
    assert.ok(Math.abs(z.im + yIm / m) < 1e-9 * (Rs + Rct));
  }
});

test('Randles limits: high frequency tends to Rs, low frequency to Rs + Rct', () => {
  const hi = evalTopologyImpedance(randles(), 2 * Math.PI * 1e9);
  const lo = evalTopologyImpedance(randles(), 2 * Math.PI * 1e-5);
  assert.ok(Math.abs(hi.re - 5) < 1e-3);
  assert.ok(Math.abs(lo.re - 105) < 1e-3);
});

test('extractAdjustableParameters lists one value per element plus an exponent for each CPE', () => {
  const params = extractAdjustableParameters(randlesCpe());
  assert.deepEqual(params.map((p) => `${p.elementId}:${p.field}`), ['Rs:value', 'Rct:value', 'Qdl:value', 'Qdl:exponent']);
  for (const p of params) {
    assert.equal(p.isFixed, false);
    assert.equal(p.value, p.initialValue);
    assert.ok(p.lowerBound > 0 && p.lowerBound < p.upperBound);
    assert.ok(p.value >= p.lowerBound && p.value <= p.upperBound, `${p.elementId} initial value inside bounds`);
  }
  const exponent = params.find((p) => p.field === 'exponent')!;
  assert.equal(exponent.value, 0.85);
  assert.equal(exponent.upperBound, 1);
});

test('applyParametersToTopology with unchanged parameters reproduces the topology without mutating it', () => {
  const base = randlesCpe();
  const snapshot = JSON.stringify(base);
  const applied = applyParametersToTopology(base, extractAdjustableParameters(base));
  assert.deepEqual(applied, base);
  assert.notEqual(applied, base);
  assert.equal(JSON.stringify(base), snapshot);
});

test('applyParametersToTopology writes new values and clamps to parameter bounds', () => {
  const base = randles();
  const params = extractAdjustableParameters(base);
  params.find((p) => p.elementId === 'Rct')!.value = 250;
  params.find((p) => p.elementId === 'Rs')!.value = 1e12;
  const applied = applyParametersToTopology(base, params);
  const rct = applied.branches[1].elements.find((e) => e.id === 'Rct')!;
  const rs = applied.branches[0].elements[0];
  assert.equal(rct.value, 250);
  assert.equal(rs.value, params.find((p) => p.elementId === 'Rs')!.upperBound);
  assert.equal(base.branches[1].elements[0].value, 100, 'source topology is untouched');
});

test('applyParametersToTopology ignores parameters that point at unknown branches or elements', () => {
  const base = randles();
  const params = extractAdjustableParameters(base).map((p) => ({ ...p, branchId: 'missing', value: 1 }));
  assert.deepEqual(applyParametersToTopology(base, params), base);
});

test('evaluateKramersKronig reports unavailable rather than inventing a validation score', () => {
  const kk = evaluateKramersKronig(dataset);
  assert.equal(kk.isValid, null);
  assert.equal(kk.score, null);
  assert.equal(kk.meanResidualPct, null);
  assert.equal(kk.maxResidualPct, null);
  assert.equal(kk.assessment, 'Unavailable');
});

test('the retired client-side CNLS fit throws instead of returning a fabricated fit', () => {
  assert.throws(() => runCNLSFit(randles(), dataset), /Python fitting service/);
});

test('runAsyncAutoFit surfaces a backend HTTP error and posts the topology parameters', async () => {
  const original = globalThis.fetch;
  let body: { action?: string; parameters?: unknown[] } = {};
  globalThis.fetch = (async (_url: unknown, init?: RequestInit) => {
    body = JSON.parse(String(init?.body));
    return { ok: false, status: 503 } as Response;
  }) as typeof fetch;
  try {
    await assert.rejects(() => runAsyncAutoFit(randles(), dataset), /HTTP 503/);
    assert.equal(body.action, 'auto_fit');
    assert.equal(body.parameters?.length, 3);
  } finally {
    globalThis.fetch = original;
  }
});
