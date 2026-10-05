import assert from 'node:assert/strict';
import test from 'node:test';
import { useMaterialSpecimenStore, type ActiveSpecimenState } from '../src/store/useMaterialSpecimenStore';
import { buildScientificContext } from '../src/utils/scientificContext';

test('Elastic Constants context describes form inputs independently of the shared specimen', () => {
  const defaultSpecimen = useMaterialSpecimenStore.getInitialState().activeSpecimen;
  const specimen: ActiveSpecimenState = {
    ...defaultSpecimen,
    name: 'Shared IN718 fixture', composition: { Ni: 52, Cr: 19 }, density_gcm3: 8.2,
    freezingRange_C: 80,
    lpbf: { ...defaultSpecimen.lpbf, laserPower_W: 280, scanSpeed_mms: 940, hatch_um: 100, layer_um: 40 },
  };
  const otherSpecimen: ActiveSpecimenState = {
    ...specimen, name: 'Different aluminium fixture', composition: { Al: 100 }, density_gcm3: 2.7,
    lpbf: { ...specimen.lpbf, laserPower_W: 500, scanSpeed_mms: 1600 },
  };
  const context = buildScientificContext('materials-project', specimen);
  assert.deepEqual(context, buildScientificContext('materials-project', otherSpecimen));
  assert.equal(context.title, 'Elastic Constants input context');
  const text = [context.observation, context.mechanism, ...context.variables,
    context.interpretation, context.limitation].join(' ');
  assert.match(text, /form.*C_ij.*K\/G/i);
  assert.match(text, /optional.*density.*composition/i);
  assert.match(text, /shared specimen.*process parameters.*not automatically/i);
  assert.match(text, /Voigt-Reuss-Hill/);
  assert.match(text, /Born.*mechanical.*not.*phase stability/i);
  assert.match(text, /before.*Calculate Elasticity.*no.*result/i);
  assert.match(text, /not.*validation claim/i);
  assert.doesNotMatch(text, /Shared IN718 fixture|280 W|8\.2 g\/cm|predicted behavior/i);

  // Unrelated modules retain the existing specimen-driven generic presentation.
  const generic = buildScientificContext('database', specimen);
  assert.equal(generic.title, 'Scientific interpretation for this module');
  assert.match(generic.observation, /Shared IN718 fixture; 280 W/);
  assert.deepEqual(generic.variables, [
    'Composition: Ni 52%, Cr 19%', 'Density: 8.2 g/cm³', 'Solidification range: 80 °C',
  ]);
});

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
