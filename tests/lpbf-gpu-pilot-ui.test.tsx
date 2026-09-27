import React from 'react';
import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { renderToStaticMarkup } from 'react-dom/server';
import { GpuPilotExecutedInputSummary, LpbfEngineeringSimulation } from '../src/components/3d-distortion-lab/LpbfEngineeringSimulation';
import { buildGpuPilotInput, type GpuPilotInput } from '../src/services/lpbfSimulationService';

test('engineering screen keeps the CUDA pilot visibly separate from standard CPU results', () => {
  const html = renderToStaticMarkup(<LpbfEngineeringSimulation input={{
    material: 'Inconel 718', power_W: 60, speed_mm_s: 1200,
    beamDiameter_um: 80, preheat_C: 25, layer_um: 80, hatch_um: 100,
  }}/>);
  for (const text of ['CUDA thermal parity pilot', 'Run CUDA parity pilot',
    'Explicit CUDA device', 'Numerical CPU/GPU parity only',
    'Experimental validation and qualification are unavailable',
    'Permanent archive export and restoration remain unavailable', 'Run simulation']) {
    assert.ok(html.includes(text), text);
  }
  assert.match(html, /aria-label="CUDA device"/);
  assert.ok(html.includes('pattern="cuda:[0-9]+"'));
  assert.match(html, /type="submit"/);
});

test('saved CUDA results show their executed inputs and label changed current controls', () => {
  const actual = JSON.parse(readFileSync(new URL(
    '../docs/LPBF_GPU_NATIVE_WORKER_ACCEPTANCE_RETRY_2026-09-27/2bcb01e5799041ec9458a947506d491f/result.json',
    import.meta.url), 'utf8')) as { settings: GpuPilotInput };
  const saved = actual.settings;
  const input = { material: 'Inconel 718', power_W: 60, speed_mm_s: 1200,
    beamDiameter_um: 80, preheat_C: 80, layer_um: 80, hatch_um: 100 };
  const current = buildGpuPilotInput(input, {
    mesh_um: 40, maxDt_s: 2e-7, tracks: 1, layers: 1, trackLength_um: 200,
    stripeWidth_um: 500, islandSize_um: 200, cooling_s: 2e-5, dwell_s: 0,
    scanAngle_deg: 0, layerRotation_deg: 67, timeout_s: 300, packingFraction: .55,
    powderConductivityRatio: .12, convection_W_m2K: 20,
  }, 'cuda:0', 'Inconel 718', 'stripe');
  const matching = renderToStaticMarkup(<GpuPilotExecutedInputSummary
    saved={saved} current={current} bound/>);
  assert.match(matching, /Inputs used by this saved CUDA job/);
  assert.match(matching, /Mesh spacing · µm/);
  assert.match(matching, />40</);
  assert.match(matching, /Stripe width · µm/);
  assert.match(matching, /Island size · µm/);
  assert.match(matching, /Bare-plate geometry/);
  assert.match(matching, /Absorptivity/);
  assert.match(matching, /Omitted\/defaulted fields are not compared/);

  const changed = buildGpuPilotInput(input, {
    mesh_um: 20, maxDt_s: 2e-7, tracks: 1, layers: 1, trackLength_um: 200,
    stripeWidth_um: 500, islandSize_um: 200, cooling_s: 2e-5, dwell_s: 0,
    scanAngle_deg: 0, layerRotation_deg: 67, timeout_s: 300, packingFraction: .55,
    powderConductivityRatio: .12, convection_W_m2K: 20,
  }, 'cuda:0', 'Inconel 718', 'stripe');
  const stale = renderToStaticMarkup(<GpuPilotExecutedInputSummary
    saved={saved} current={changed} bound/>);
  assert.match(stale, /Current submitted fields differ from this saved result: mesh_um/);
  assert.match(stale, /displayed result still belongs to the saved run/);
  assert.match(stale, />40</);

  const legacy = renderToStaticMarkup(<GpuPilotExecutedInputSummary
    saved={saved} current={changed} bound={false}/>);
  assert.match(legacy, /no exact request binding/);
});
