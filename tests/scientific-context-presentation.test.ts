import assert from 'node:assert/strict';
import test from 'node:test';
import type { ActiveSpecimenState } from '../src/store/useMaterialSpecimenStore';
import { buildScientificContext } from '../src/utils/scientificContext';

test('LPBF context does not present heuristic conductivity as a solver input', () => {
  const specimen = {
    name: 'Ni alloy fixture',
    baseMetal: 'Ni',
    lpbf: {
      laserPower_W: 60,
      scanSpeed_mms: 1200,
      hatch_um: 100,
      layer_um: 40,
      thermalConductivity_k_WmK: 9,
      preheatTemp_C: 25,
    },
    xrd: { crystalSystem: 'FCC' },
  } as ActiveSpecimenState;
  const context = buildScientificContext('3d-distortion-lab', specimen);
  const conductivity = context.variables.find(value => value.toLowerCase().includes('conductivity'));
  assert.ok(conductivity);
  assert.doesNotMatch(conductivity, /9\s*W\/m/);
  assert.match(conductivity, /temperature-dependent/i);
  assert.match(conductivity, /executed material table/i);
});
