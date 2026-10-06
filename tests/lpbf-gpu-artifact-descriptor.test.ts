import assert from 'node:assert/strict';
import { test } from 'node:test';
import { GPU_ARTIFACT_UNITS, parseGpuPilotArtifactDescriptor } from '../src/types/lpbfGpuArtifacts';

// Synthetic metadata fixture only; no model solve or experimental observation.
function fixture() {
  const states = Object.fromEntries(['cpu', 'gpu'].map(backend => {
    const cells = backend === 'cpu' ? 2 : 3, steps = backend === 'cpu' ? 4 : 5;
    return [backend, { cells, steps, time_s: 1, initial_temperature_K: 300, cell_volume_m3: 1e-12,
      fields: Object.fromEntries(Object.entries(GPU_ARTIFACT_UNITS).map(([quantity, units]) => {
        const shape = quantity === 'coordinates_m' ? [cells, 3] : [quantity === 'accepted_dt_s' ? steps : cells];
        return [quantity, { path: `gpu-pilot/${backend}-${quantity}.f64le.bin`, units, shape,
          size_bytes: shape.reduce((product, n) => product * n, 8), sha256: 'a'.repeat(64) }];
      })) }];
  }));
  return { schemaVersion: 1, kind: 'lpbf-final-field-parity-evidence', encoding: 'float64-le', order: 'C',
    enthalpyReference: 'volumetric-excess-relative-to-initial-temperature', states };
}

test('GPU field descriptor retains both unmatched states without declaring parity', () => {
  const parsed = parseGpuPilotArtifactDescriptor(fixture());
  assert.equal(parsed.states.cpu.cells, 2);
  assert.equal(parsed.states.gpu.cells, 3);
  assert.equal(parsed.states.cpu.steps, 4);
  assert.equal(parsed.states.gpu.steps, 5);
  assert.equal(Object.hasOwn(parsed, 'validationStatus'), false);
});

test('GPU field descriptor rejects mismatched quantities, units, shape, resource bounds and paths', () => {
  const mutations: ((value: any) => void)[] = [
    v => { v.encoding = 'float32-le'; },
    v => { v.enthalpyReference = 'absolute-specific-enthalpy'; },
    v => { v.states.cpu.fields.enthalpy_J_m3.units = 'J/kg'; },
    v => { v.states.cpu.fields.coordinates_m.shape = [3, 2]; },
    v => { v.states.gpu.fields.accepted_dt_s.size_bytes = 8; },
    v => { v.states.gpu.fields.temperature_K.path = 'gpu-pilot/cpu-temperature_K.f64le.bin'; },
    v => { v.states.gpu.fields.temperature_K.path = '../temperature.bin'; },
    v => { v.states.cpu.fields.density_kg_m3.sha256 = 'unverified'; },
    v => { v.states.cpu.cells = 100001; },
    v => { v.states.gpu.steps = 250001; },
    v => { v.states.cpu.time_s = NaN; },
    v => { v.states.cpu.cell_volume_m3 = 0; },
    v => { v.states.cpu.initial_temperature_K = -1; },
    v => { delete v.states.cpu.fields.density_kg_m3; },
    v => { v.states.cpu.fields.extra = {}; },
    v => { v.schemaVersion = 2; },
  ];
  for (const mutate of mutations) {
    const value = fixture(); mutate(value);
    assert.throws(() => parseGpuPilotArtifactDescriptor(value), /artifact descriptor/);
  }
});
