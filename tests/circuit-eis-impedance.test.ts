import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { CircuitTopology, CircuitElement } from '../src/components/EquivalentCircuitBuilder';

// The component module transitively imports plotly.js, which expects a browser global named `self`.
// Provide the minimal shim before a dynamic import so the pure impedance code can run under Node.
const g = globalThis as Record<string, unknown>;
if (typeof g.self === 'undefined') g.self = globalThis;
if (typeof g.window === 'undefined') g.window = globalThis;
if (typeof g.document === 'undefined') {
  const stub: unknown = new Proxy(function () {}, {
    get: (_t, k) => (k === Symbol.toPrimitive ? () => '' : k === 'length' ? 0 : stub),
    apply: () => stub,
    construct: () => stub as object,
  });
  g.document = stub;
  for (const name of ['DOMParser', 'XMLSerializer', 'Element', 'HTMLElement', 'Node', 'Image', 'MutationObserver', 'getComputedStyle', 'matchMedia', 'requestAnimationFrame', 'addEventListener']) {
    if (typeof g[name] === 'undefined') g[name] = function () { return stub; };
  }
}
const { calculateCircuitEIS } = await import('../src/components/EquivalentCircuitBuilder');

const el = (type: CircuitElement['type'], value: number, exponent?: number): CircuitElement =>
  ({ id: type, type, name: type, label: type, value, unit: '', exponent, isFixed: false, description: '' });
const topo = (branches: CircuitTopology['branches']): CircuitTopology =>
  ({ id: 't', name: 't', category: 'custom', description: '', cdcNotation: '', branches });

test('series resistor gives a purely real, frequency-independent impedance', () => {
  const pts = calculateCircuitEIS(topo([{ id: 'b', name: 'b', connection: 'series', elements: [el('R', 25)] }]), 0.1, 1e4, 5);
  assert.ok(pts.length >= 20);
  for (const p of pts) {
    assert.ok(Math.abs(p.zReal - 25) < 1e-3);
    assert.ok(Math.abs(p.zImag) < 1e-3);
  }
});

test('output is sorted from high to low frequency', () => {
  const pts = calculateCircuitEIS(topo([{ id: 'b', name: 'b', connection: 'series', elements: [el('R', 1)] }]), 1, 1e3, 10);
  for (let i = 1; i < pts.length; i++) assert.ok(pts[i - 1].frequency >= pts[i].frequency);
});

test('R||C branch matches the closed form Z = R / (1 + jwRC)', () => {
  const R = 100, C = 1e-5;
  const pts = calculateCircuitEIS(topo([{ id: 'b', name: 'b', connection: 'parallel', elements: [el('R', R), el('C', C)] }]), 1, 1e5, 8);
  for (const p of pts) {
    const w = p.omega, d = 1 + (w * R * C) ** 2;
    assert.ok(Math.abs(p.zReal - R / d) < 2e-3, `re at ${p.frequency}`);
    assert.ok(Math.abs(p.zImag - (-w * R * R * C) / d) < 2e-3, `im at ${p.frequency}`);
  }
});

test('R + CPE with n=1 equals R + capacitor of the same value', () => {
  const Q = 2e-4, R = 10;
  const a = calculateCircuitEIS(topo([{ id: 'b', name: 'b', connection: 'series', elements: [el('R', R), el('CPE', Q, 1)] }]), 1, 1e4, 6);
  const b = calculateCircuitEIS(topo([{ id: 'b', name: 'b', connection: 'series', elements: [el('R', R), el('C', Q)] }]), 1, 1e4, 6);
  assert.equal(a.length, b.length);
  a.forEach((p, i) => {
    assert.ok(Math.abs(p.zReal - b[i].zReal) < 1e-3);
    assert.ok(Math.abs(p.zImag - b[i].zImag) < 1e-3);
  });
});
