import React from 'react';
import assert from 'node:assert/strict';
import test from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import { CancelledRunNotice, LpbfEngineeringSimulation } from '../src/components/3d-distortion-lab/LpbfEngineeringSimulation';

test('fresh computational run record is opt-in and disabled until the exact input has completed', () => {
  const html = renderToStaticMarkup(<LpbfEngineeringSimulation input={{
    material: 'Inconel 718', power_W: 60, speed_mm_s: 1200,
    beamDiameter_um: 80, preheat_C: 25, layer_um: 80, hatch_um: 100,
  }}/>);
  assert.match(html, /aria-label="Create a fresh computational run record"[^>]*type="checkbox"[^>]*disabled=""/);
  assert.match(html, /Available after this exact input finishes/);
  assert.match(html, /does not represent an experimental or physical repeat/);
  assert.match(html, /default submission remains deduplicated/);
});

test('cancelled run explains that no result can be archived or exported', () => {
  const cancelled = renderToStaticMarkup(<CancelledRunNotice status="cancelled"/>);
  assert.match(cancelled, /role="status"/);
  assert.match(cancelled, /Run cancelled\. No completed result is available, so this run cannot be archived or exported\./);
  assert.equal(renderToStaticMarkup(<CancelledRunNotice status="completed"/>), '');
});
