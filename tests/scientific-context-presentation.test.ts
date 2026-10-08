import assert from 'node:assert/strict';
import test from 'node:test';
import { useMaterialSpecimenStore, type ActiveSpecimenState } from '../src/store/useMaterialSpecimenStore';
import { buildScientificContext, hasScientificContext } from '../src/utils/scientificContext';

test('modules without module-specific context fall back to the generic default', () => {
  const defaultSpecimen = useMaterialSpecimenStore.getInitialState().activeSpecimen;
  const specimen: ActiveSpecimenState = {
    ...defaultSpecimen,
    name: 'Shared IN718 fixture', composition: { Ni: 52, Cr: 19 }, density_gcm3: 8.2,
    freezingRange_C: 80,
    lpbf: { ...defaultSpecimen.lpbf, laserPower_W: 280, scanSpeed_mms: 940, hatch_um: 100, layer_um: 40 },
  };
  // Unrelated modules fall to the generic default text, but the panel is hidden there (hasScientificContext).
  assert.equal(hasScientificContext('database'), false);
  const generic = buildScientificContext('database', specimen);
  assert.equal(generic.title, 'Scientific interpretation for this module');
  assert.match(generic.observation, /Shared IN718 fixture; 280 W/);
  assert.deepEqual(generic.variables, [
    // Density is recomputed from the shown composition (52/8.908 + 19/7.19), not the fixture's stored 8.2.
    'Composition: Ni 52%, Cr 19%', 'Density (inverse rule of mixtures, wt.%): 8.373 g/cm³', 'Solidification range: unavailable (not computed from composition)',
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
  assert.equal(title('research-hub'), 'Evidence chain for any claim');
  for (const id of ['database'] as const) {
    assert.notEqual(title(id), microstructure, `${id} must not show the LPBF microstructure context`);
    assert.equal(title(id), 'Scientific interpretation for this module', id);
    assert.equal(hasScientificContext(id), false, `${id} must not render the LPBF-number default panel`);
  }
});

test('phase and evidence contexts never print specimen liquidus, solidus or yield numbers', () => {
  const specimen = {
    name: 'Ni alloy fixture', baseMetal: 'Ni', unit: 'wt%', sourceTab: 'database',
    composition: { Ni: 52, Cr: 19 }, density_gcm3: 8.19, freezingRange_C: 80, yieldStrength_25C_MPa: 1000,
    liquidus_C: 1336, solidus_C: 1260, solvus_C: 900, stablePhases: ['FCC'],
    lpbf: { laserPower_W: 280, scanSpeed_mms: 940, hatch_um: 100, layer_um: 40, thermalConductivity_k_WmK: 11, preheatTemp_C: 80, processSeed: 7 },
    xrd: { crystalSystem: 'FCC', spaceGroup: 'Fm-3m' },
  } as unknown as ActiveSpecimenState;
  for (const id of ['phase-diagram', 'research-hub', 'database'] as const) {
    const vars = buildScientificContext(id, specimen).variables.join(' ');
    assert.doesNotMatch(vars, /1336|1260|900|1000 MPa|80 °C/, id);
  }
  assert.match(buildScientificContext('phase-diagram', specimen).variables.join(' '), /Liquidus \/ solidus \/ solvus: unavailable/);
});

test('generic context density is unavailable (no 8.0 g/cm³ fallback) for an element without a tabulated density', () => {
  const specimen = useMaterialSpecimenStore.getInitialState().activeSpecimen;
  const withOxygen: ActiveSpecimenState = {
    ...specimen,
    unit: 'wt_pct',
    composition: { Ti: 89.8, Al: 6, V: 4, O: 0.2 },
  };
  const line = buildScientificContext('database', withOxygen).variables.find((v) => v.startsWith('Density'));
  assert.ok(line);
  assert.match(line, /^Density: unavailable \(no tabulated elemental density for O\.\)$/);
  assert.doesNotMatch(line, /\d+(\.\d+)? g\/cm³/);

  const tabulated: ActiveSpecimenState = { ...withOxygen, composition: { Ni: 100 } };
  const computed = buildScientificContext('database', tabulated).variables.find((v) => v.startsWith('Density'));
  assert.equal(computed, 'Density (inverse rule of mixtures, wt.%): 8.908 g/cm³');

  const atomic = buildScientificContext('database', { ...tabulated, unit: 'at_pct' }).variables.find((v) => v.startsWith('Density'));
  assert.match(atomic ?? '', /^Density: unavailable/);
});

test('the context panel is not labelled live and renders nothing for modules without a module-specific text', async () => {
  const { readFileSync } = await import('node:fs');
  const { renderToStaticMarkup } = await import('react-dom/server');
  const React = await import('react');
  const { ScientificContextPanel } = await import('../src/components/ScientificContextPanel');
  const source = readFileSync('src/components/ScientificContextPanel.tsx', 'utf8');
  assert.doesNotMatch(source, /live interpretation/i);
  const specimen = { name: 'x', composition: { Ni: 52 }, density_gcm3: 8, freezingRange_C: 80, lpbf: { laserPower_W: 1, scanSpeed_mms: 1, hatch_um: 1, layer_um: 1 }, stablePhases: [], xrd: {} } as unknown as ActiveSpecimenState;
  assert.equal(renderToStaticMarkup(React.createElement(ScientificContextPanel, { moduleId: 'database', specimen })), '');
});
