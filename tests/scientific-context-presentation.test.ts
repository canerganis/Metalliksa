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

test('each module family gets its own context; unrelated modules never fall into the microstructure text', () => {
  const specimen = {
    name: 'Ni alloy fixture', baseMetal: 'Ni', unit: 'wt%', sourceTab: 'database',
    composition: { Ni: 52, Cr: 19 }, density_gcm3: 8.19, freezingRange_C: 80, yieldStrength_25C_MPa: 1000,
    liquidus_C: 1336, solidus_C: 1260, solvus_C: 900, stablePhases: ['FCC'],
    lpbf: { laserPower_W: 280, scanSpeed_mms: 940, hatch_um: 100, layer_um: 40, thermalConductivity_k_WmK: 11, preheatTemp_C: 80, processSeed: 7 },
    xrd: { crystalSystem: 'FCC', spaceGroup: 'Fm-3m' },
  } as unknown as ActiveSpecimenState;
  const title = (id: Parameters<typeof buildScientificContext>[0]) => buildScientificContext(id, specimen).title;
  const microstructure = 'How thermal history changes microstructure';
  assert.equal(title('phase-diagram'), microstructure);
  assert.equal(title('ttt-cct-kinetics'), microstructure);
  assert.equal(title('eds-lab'), 'From signal to microstructural claim');
  assert.equal(title('research-hub'), 'Evidence chain for any claim');
  for (const id of ['electrochem-suite', 'database', 'calculators', 'copilot'] as const) {
    assert.notEqual(title(id), microstructure, `${id} must not show the LPBF microstructure context`);
    assert.equal(title(id), 'Scientific interpretation for this module', id);
  }
});
