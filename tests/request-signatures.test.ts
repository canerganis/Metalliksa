import test from 'node:test';
import assert from 'node:assert/strict';
import { buildPourbaixRequest, pourbaixRequestSignature, type PourbaixRequestInputs } from '../src/utils/pourbaixRequest';
import { buildSlicerPayload, slicerRequestSignature, type SlicerRequestInputs } from '../src/utils/slicerRequest';
import { createDebouncedLatestTask } from '../src/utils/debouncedLatestTask';

const pour: PourbaixRequestInputs = {
  primaryElement: 'Fe', temperature_C: 25, ionActivity: 1e-6, chlorideActivity: 0.1,
  experimentalPoints: [{ id: 'p1', name: 'P', pH: 7, potential_V: 0.1, refElectrode: 'SHE' as any }],
};

test('Pourbaix signature changes for every request body field and ignores solver enrichment', () => {
  const base = pourbaixRequestSignature(pour);
  const variants: Record<string, PourbaixRequestInputs> = {
    element: { ...pour, primaryElement: 'Ni' },
    temperature_C: { ...pour, temperature_C: 40 },
    ionActivity_log10: { ...pour, ionActivity: 1e-4 },
    chloride_ppm: { ...pour, chlorideActivity: 0.5 },
    experimentalPoints: { ...pour, experimentalPoints: [{ ...pour.experimentalPoints[0], pH: 8 }] },
  };
  const bodyKeys = Object.keys(buildPourbaixRequest(pour)).sort();
  assert.deepEqual(Object.keys(variants).sort(), bodyKeys, 'every request body field must have a variant');
  for (const [field, inputs] of Object.entries(variants)) assert.notEqual(pourbaixRequestSignature(inputs), base, field);
  // same count, different point content (the old length-only signature missed this)
  assert.notEqual(pourbaixRequestSignature({ ...pour, experimentalPoints: [{ ...pour.experimentalPoints[0], potential_V: 0.2 }] }), base);
  // solver-derived enrichment must not change the signature (no feedback loop)
  const enriched = { ...pour, experimentalPoints: [{ ...pour.experimentalPoints[0], regime: 'Passive', riskLevel: 'Caution' as const, mechanismId: 'm', potential_V_SHE: 0.3 }] };
  assert.equal(pourbaixRequestSignature(enriched), base);
});

const sl: Omit<SlicerRequestInputs, 'customTriangles'> = {
  preset: 'custom', material: 'Inconel 718', laserPower_W: 285, scanSpeed_mms: 960, layerThickness_um: 40,
  hatchSpacing_um: 110, recoatTimePerLayer_s: 9.5, hatchStrategy: 'meander_67', cadAssetName: 'a.stl', triangleCountNative: 100,
};

test('slicer signature covers every payload field', () => {
  const sig = (o: Partial<typeof sl> = {}, geometryId: string | null = 'g1') => slicerRequestSignature({ ...sl, ...o, geometryId });
  const base = sig();
  const payloadKeys = Object.keys(buildSlicerPayload({ ...sl, customTriangles: null })).sort();
  const variants: Record<string, string> = {
    preset: sig({ preset: 'bracket-demo' }), material: sig({ material: 'Ti-6Al-4V' }),
    laserPower_W: sig({ laserPower_W: 300 }), scanSpeed_mms: sig({ scanSpeed_mms: 1000 }),
    layerThickness_um: sig({ layerThickness_um: 50 }), hatchSpacing_um: sig({ hatchSpacing_um: 100 }),
    recoatTimePerLayer_s: sig({ recoatTimePerLayer_s: 10 }), hatchStrategy: sig({ hatchStrategy: 'meander_90' }),
    customTriangles: sig({}, 'g2'), cadAssetName: sig({ cadAssetName: 'b.stl' }), triangleCountNative: sig({ triangleCountNative: 200 }),
  };
  assert.deepEqual(Object.keys(variants).sort(), payloadKeys);
  for (const [field, s] of Object.entries(variants)) assert.notEqual(s, base, field);
});

test('debounce delay may be a getter read at schedule time', t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  let delay = 100; const calls: string[] = [];
  const task = createDebouncedLatestTask({ delayMs: () => delay, run: async sig => { calls.push(sig); } });
  delay = 300; task.schedule('a');
  t.mock.timers.tick(299); assert.equal(calls.length, 0);
  t.mock.timers.tick(1); assert.deepEqual(calls, ['a']);
});
