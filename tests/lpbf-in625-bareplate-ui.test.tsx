import React from 'react';
import assert from 'node:assert/strict';
import test from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import { compareTemperatureFields, In625BareplatePanel } from '../src/components/In625BareplatePanel';

test('IN625 bare-plate screen states its limited scope and offers explicit CPU and CUDA runs', () => {
  const html = renderToStaticMarkup(<In625BareplatePanel />);
  for (const text of ['IN625 bare-plate thermal screen', '273.15–1623.15 K model range',
    'Constant density 8440 kg/m³', 'No powder, melt-pool flow, optical coupling, evaporation, or experimental validation',
    'Run CPU screen', 'Run CUDA screen', 'There is no CPU fallback', 'CPU and CUDA runs are separate jobs']) {
    assert.ok(html.includes(text), text);
  }
  assert.match(html, /aria-label="IN625 CUDA device"/);
  assert.match(html, /pattern="cuda:\[0-9\]\+"/);
  assert.match(html, /aria-label="Cells Y"[^>]*value="12"/);
  assert.match(html, /aria-label="Scan Y · m"[^>]*value="0\.0015"/);
});

test('IN625 downloaded CPU/CUDA fields produce visible comparison metrics', () => {
  const comparison = compareTemperatureFields(
    { shapeXYZ: [2, 1, 1], temperaturesK: new Float64Array([300, 302]) },
    { shapeXYZ: [2, 1, 1], temperaturesK: new Float64Array([301, 300]) },
  );
  assert.equal(comparison.cells, 2);
  assert.equal(comparison.maxAbsoluteDifferenceK, 2);
  assert.equal(comparison.rmsDifferenceK, Math.sqrt(2.5));
  assert.throws(() => compareTemperatureFields(
    { shapeXYZ: [2, 1, 1], temperaturesK: new Float64Array([300, 302]) },
    { shapeXYZ: [1, 2, 1], temperaturesK: new Float64Array([301, 300]) },
  ), /dimensions differ/);
});
