// The UI reads alloy numbers only from src/generated/lpbfMaterialAuthority.json, a projection of
// python/four_alloy_materials.py written by scripts/emit-lpbf-material-authority.py. These tests pin
// (1) the committed JSON against the live Python authority and a byte-identical regeneration, and
// (2) every TS consumer against the JSON, so neither side can drift. Python side of the same check:
// python/test_lpbf_material_authority_json.py.
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { getHostPython } from '../server/pythonRuntime';
import {
  LPBF_MATERIAL_AUTHORITY, authorityThermal, authorityPvWindow, celsiusToKelvin,
  solidificationMaterialInputs, transientGpuMaterialInputs,
} from '../src/data/lpbfMaterialAuthority';
import {
  ALLOY_THERMAL_PROPERTIES, alloyThermalConstants, calculateNormalizedEnthalpy, classifyProcessRegime,
  type LPBFAlloyId,
} from '../src/types/lpbfDataFoundation';
import { LITERATURE_PV_WINDOWS } from '../src/utils/lpbfFourAlloySchema';

const FOUR = ['ti6al4v', 'ss316l', 'alsi10mg', 'in718'] as const;
const GENERATED = 'src/generated/lpbfMaterialAuthority.json';

function runPython(args: string[]) {
  const python = getHostPython();
  return spawnSync(python.cmd, [...python.prefix, '-B', ...args], {
    cwd: process.cwd(), encoding: 'utf8', windowsHide: true, maxBuffer: 4 * 1024 * 1024,
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
  });
}

test('committed JSON is byte-identical to a fresh regeneration (generator --check)', () => {
  const run = runPython(['scripts/emit-lpbf-material-authority.py', '--check']);
  assert.ifError(run.error);
  assert.equal(run.status, 0, `generated file is stale or the generator failed: ${run.stderr}`);
});

test('committed JSON equals the live Python authority (read without the generator)', () => {
  const code = [
    'import json, sys', 'sys.path.insert(0, "python")',
    'import four_alloy_materials as f',
    'from lpbf_thermal_solver import SECONDARY_THERMOPHYSICAL_DB as S',
    'db = f.four_alloy_thermophysical_db()',
    'print(json.dumps({"ids": list(f.FOUR_ALLOY_IDS),',
    '  "thermal": {a: db[f.THERMAL_NAME[a]] for a in f.FOUR_ALLOY_IDS},',
    '  "pv": f.LITERATURE_PV_WINDOWS, "in625": S["Inconel 625"]}, allow_nan=False))',
  ].join('\n');
  const run = runPython(['-c', code]);
  assert.ifError(run.error);
  assert.equal(run.status, 0, run.stderr);
  const live = JSON.parse(run.stdout);
  const committed = JSON.parse(readFileSync(GENERATED, 'utf8'));
  assert.deepEqual(committed.alloyIds, live.ids);
  assert.deepEqual(committed.alloyIds, [...FOUR]);
  for (const id of FOUR) {
    assert.deepEqual(committed.alloys[id].thermal, live.thermal[id], `${id} thermal`);
    assert.deepEqual(committed.alloys[id].literaturePvWindow, live.pv[id], `${id} P-v box`);
    assert.equal(committed.alloys[id].quality, 'estimated', `${id} keeps the authority label`);
  }
  assert.deepEqual(committed.secondary.in625.thermal, live.in625);
});

test('ALLOY_THERMAL_PROPERTIES and calculateNormalizedEnthalpy read the authority', () => {
  for (const id of [...FOUR, 'in625'] as const) {
    const t = authorityThermal(id);
    const c = ALLOY_THERMAL_PROPERTIES[id];
    assert.equal(c.meltingPoint_C, t.liquidus_C, id);
    assert.equal(c.density_kg_m3, t.density_kg_m3, id);
    assert.equal(c.specificHeat_J_kgK, t.specific_heat_J_kgK, id);
    assert.equal(c.thermalConductivity_W_mK, t.thermal_conductivity_W_mK, id);
    assert.equal(c.defaultAbsorptivity, t.absorptivity_IR, id);
    assert.equal(c.thermalDiffusivity_m2_s, t.thermal_conductivity_W_mK / (t.density_kg_m3 * t.specific_heat_J_kgK), id);
    assert.equal(c.enthalpyOfMelting_hs_J_m3, t.density_kg_m3 * t.specific_heat_J_kgK * t.liquidus_C, id);
  }
  // Explicit absorptivity (as the reference datasets pass it): same formula, authority constants.
  const c = ALLOY_THERMAL_PROPERTIES.in718;
  const expected = (0.4 * 285) / (c.enthalpyOfMelting_hs_J_m3 * Math.sqrt(Math.PI * c.thermalDiffusivity_m2_s * 0.96 * (40e-6) ** 3));
  assert.equal(calculateNormalizedEnthalpy(285, 960, 80, 'in718', 0.4), Number(expected.toFixed(2)));
});

test('unknown alloy is unavailable: no silent Ti-6Al-4V (or any) surrogate', () => {
  const unknown = 'cocrmo' as unknown as LPBFAlloyId;
  assert.throws(() => calculateNormalizedEnthalpy(200, 800, 80, unknown), /Unknown LPBF alloy "cocrmo"/);
  assert.throws(() => classifyProcessRegime(60, 200, 800, unknown), /Unknown LPBF alloy "cocrmo"/);
  assert.throws(() => alloyThermalConstants('toString' as unknown as LPBFAlloyId), /Unknown LPBF alloy/);
  assert.throws(() => authorityThermal('cocrmo'), /no surrogate alloy/);
  assert.throws(() => authorityPvWindow('in625'), /no surrogate alloy/);
});

test('lpbfFourAlloySchema P-v boxes equal the authority; IN625 stays TS-local', () => {
  for (const id of FOUR) {
    const { powerMin_W, powerMax_W, speedMin_mm_s, speedMax_mm_s } = LITERATURE_PV_WINDOWS[id];
    assert.deepEqual({ powerMin_W, powerMax_W, speedMin_mm_s, speedMax_mm_s }, LPBF_MATERIAL_AUTHORITY.alloys[id].literaturePvWindow, id);
    assert.ok(LITERATURE_PV_WINDOWS[id].sources.length > 0, `${id} keeps its sources`);
  }
  assert.equal(LITERATURE_PV_WINDOWS.in625.powerMax_W, 350);
});

test('GPU lab and solidification lab inputs equal the authority (°C -> K only)', () => {
  for (const id of FOUR) {
    const t = LPBF_MATERIAL_AUTHORITY.alloys[id].thermal;
    assert.deepEqual(transientGpuMaterialInputs(id), {
      rho: t.density_kg_m3, L_f: t.latent_heat_fusion_J_kg,
      T_solidus: celsiusToKelvin(t.solidus_C), T_liquidus: celsiusToKelvin(t.liquidus_C),
      cp_solid: t.specific_heat_J_kgK, cp_liquid: t.specific_heat_liquid_J_kgK,
      k_solid: t.thermal_conductivity_W_mK, k_liquid: t.thermal_conductivity_liquid_W_mK,
    }, id);
    assert.deepEqual(solidificationMaterialInputs(id), {
      k_WmK: t.thermal_conductivity_W_mK, liquidus_K: celsiusToKelvin(t.liquidus_C), absorptivity: t.absorptivity_IR,
    }, id);
  }
  assert.equal(celsiusToKelvin(1336), 1609.15);
  assert.equal(celsiusToKelvin(595), 868.15);
});

test('the four consumer files hold no alloy-property literals', () => {
  const property = /\b(rho|L_f|T_solidus|T_liquidus|cp_solid|cp_liquid|k_solid|k_liquid|k_WmK|liquidus_K|absorptivity|meltingPoint_C|density_kg_m3|specificHeat_J_kgK|thermalConductivity_W_mK|thermalDiffusivity_m2_s|enthalpyOfMelting_hs_J_m3|defaultAbsorptivity|powerMin_W|powerMax_W|speedMin_mm_s|speedMax_mm_s)\s*:\s*-?\d/;
  const files: Record<string, RegExp | null> = {
    'src/types/lpbfDataFoundation.ts': null,
    'src/components/TransientEnthalpy3DGPULab.tsx': null,
    'src/components/SolidificationMicrostructureLab.tsx': null,
    // The labelled TS-local IN625 box is the only allowed literal block.
    'src/utils/lpbfFourAlloySchema.ts': /const IN625_PV_WINDOW_TS_LOCAL[\s\S]*?\n};\n/,
  };
  for (const [file, allowed] of Object.entries(files)) {
    let text = readFileSync(file, 'utf8').replace(/\r\n/g, '\n');
    if (allowed) {
      assert.match(text, allowed, `${file}: expected the labelled TS-local block`);
      text = text.replace(allowed, '');
    }
    const hit = text.split('\n').find(line => property.test(line));
    assert.equal(hit, undefined, `${file} holds an alloy-property literal: ${hit}`);
  }
});
