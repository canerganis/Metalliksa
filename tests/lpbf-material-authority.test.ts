// The UI reads alloy numbers only from src/generated/lpbfMaterialAuthority.json, a projection of
// python/four_alloy_materials.py written by scripts/emit-lpbf-material-authority.py. These tests pin
// (1) the committed JSON against the live Python authority and a byte-identical regeneration,
// (2) every TS consumer, including each lab's dropdown label -> alloy mapping and the exact RPC payload,
// against the JSON, and (3) that the UI computes no normalized enthalpy of its own. Python side of the
// same check: python/test_lpbf_material_authority_json.py.
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { getHostPython } from '../server/pythonRuntime';
import {
  LPBF_MATERIAL_AUTHORITY, LPBF_MATERIAL_AUTHORITY_SCHEMA_VERSION, authorityPvWindow, authorityThermal,
  authorityThermalProvenance, celsiusToKelvin, checkedAuthorityDocument, solidificationMaterialInputs,
  type AuthorityAlloyId, type LpbfMaterialAuthorityDocument,
} from '../src/data/lpbfMaterialAuthority';
import * as foundation from '../src/types/lpbfDataFoundation';
import { ALLOY_THERMAL_PROPERTIES, alloyThermalConstants, classifyProcessRegime, type LPBFAlloyId } from '../src/types/lpbfDataFoundation';
import { LITERATURE_PV_WINDOWS } from '../src/utils/lpbfFourAlloySchema';
import { MASTER_LPBF_REFERENCE_DATASETS } from '../src/data/lpbfReferenceDatasets';
import { findNearestLiteratureRecord } from '../src/utils/lpbfIndustrialDecision';
import { GPU_LAB_MATERIALS, transientGpuRequest, type GpuLabParams } from '../src/components/TransientEnthalpy3DGPULab';
import { SOLIDIFICATION_PRESETS, solidificationPresetInputs, solidificationRequest } from '../src/components/SolidificationMicrostructureLab';

const FOUR = ['ti6al4v', 'ss316l', 'alsi10mg', 'in718'] as const;
const GENERATED = 'src/generated/lpbfMaterialAuthority.json';
// Expected dropdown label -> alloy id, written out independently of the components.
const GPU_LABELS: Record<string, AuthorityAlloyId> = { 'Ti-6Al-4V': 'ti6al4v', IN718: 'in718', '316L': 'ss316l', AlSi10Mg: 'alsi10mg' };
const SOLIDIFICATION_LABELS: Record<string, AuthorityAlloyId> = { 'Inconel 718': 'in718', 'Ti-6Al-4V': 'ti6al4v', AlSi10Mg: 'alsi10mg', '316L SS': 'ss316l' };

function runPython(args: string[]) {
  const python = getHostPython();
  return spawnSync(python.cmd, [...python.prefix, '-B', ...args], {
    cwd: process.cwd(), encoding: 'utf8', windowsHide: true, maxBuffer: 4 * 1024 * 1024,
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
  });
}

interface LivePython {
  ids: string[]; authority: string; authoritySchemaVersion: number;
  thermal: Record<string, unknown>; slicerThermal: Record<string, unknown>; pv: Record<string, unknown>;
  thermalName: Record<string, string>; slicerName: Record<string, string>; sha: Record<string, string>;
  evidence: Record<string, { quality: string; source: string }>;
  in625: { latent_heat_fusion_J_kg: number; boiling_C: number; absorptivity_IR: number };
  in625Catalog: { quality: string; note: string };
  in625Other: { latent: number[]; boiling_K: number; absorptivity: number };
  resolved: Record<string, string | null>;
}
let liveCache: LivePython | undefined;
/** The authority read straight from the Python modules (not through the generator). */
function live(): LivePython {
  if (liveCache) return liveCache;
  const labels = JSON.stringify([...Object.keys(GPU_LABELS), ...Object.keys(SOLIDIFICATION_LABELS)]);
  const code = [
    'import json, sys', 'sys.path.insert(0, "python")',
    'import four_alloy_materials as f, in625_thermal_material as m, lpbf_material_registry as r',
    'from lpbf_thermal_solver import SECONDARY_THERMOPHYSICAL_DB as S',
    'db = f.four_alloy_thermophysical_db()',
    'cat = next(c for c in r.catalog() if c["name"] == "Inconel 625")',
    'print(json.dumps({"ids": list(f.FOUR_ALLOY_IDS), "authority": f.MATERIAL_AUTHORITY,',
    '  "authoritySchemaVersion": f.MATERIAL_AUTHORITY_SCHEMA_VERSION,',
    '  "thermal": {a: db[f.THERMAL_NAME[a]] for a in f.FOUR_ALLOY_IDS},',
    '  "slicerThermal": {a: db[f.SLICER_NAME[a]] for a in f.FOUR_ALLOY_IDS},',
    '  "thermalName": f.THERMAL_NAME, "slicerName": f.SLICER_NAME,',
    '  "sha": {a: f.canonical_material_source(a)[1] for a in f.FOUR_ALLOY_IDS},',
    '  "evidence": {a: {k: r.material(f.THERMAL_NAME[a])[k] for k in ("quality", "source")} for a in f.FOUR_ALLOY_IDS},',
    '  "pv": f.LITERATURE_PV_WINDOWS, "in625": S["Inconel 625"], "in625Catalog": cat,',
    '  "in625Other": {"latent": [m.LATENT_HEAT_J_KG, m.IN625_LATENT_HEAT_FUSION_MILLS_J_KG], "boiling_K": m.IN625_BOILING_K, "absorptivity": m.IN625_ABSORPTIVITY_IR},',
    `  "resolved": {l: f.resolve_alloy_id(l) for l in ${labels}}}, allow_nan=False))`,
  ].join('\n');
  const run = runPython(['-c', code]);
  assert.ifError(run.error);
  assert.equal(run.status, 0, run.stderr);
  liveCache = JSON.parse(run.stdout) as LivePython;
  return liveCache;
}

test('committed JSON is byte-identical to a fresh regeneration (generator --check)', () => {
  const run = runPython(['scripts/emit-lpbf-material-authority.py', '--check']);
  assert.ifError(run.error);
  assert.equal(run.status, 0, `generated file is stale or the generator failed: ${run.stderr}`);
});

test('committed JSON equals the live Python authority (read without the generator)', () => {
  const py = live();
  const committed = JSON.parse(readFileSync(GENERATED, 'utf8')) as LpbfMaterialAuthorityDocument;
  assert.equal(committed.schemaVersion, LPBF_MATERIAL_AUTHORITY_SCHEMA_VERSION);
  assert.equal(committed.authority, `python/${py.authority}`);
  assert.equal(committed.authoritySchemaVersion, py.authoritySchemaVersion);
  assert.deepEqual(committed.alloyIds, py.ids);
  assert.deepEqual(committed.alloyIds, [...FOUR]);
  for (const id of FOUR) {
    const entry = committed.alloys[id];
    assert.deepEqual(entry.thermal, py.thermal[id], `${id} thermal`);
    assert.deepEqual(entry.thermal, py.slicerThermal[id], `${id} thermal under the slicer name`);
    assert.deepEqual(entry.literaturePvWindow, py.pv[id], `${id} P-v box`);
    assert.equal(entry.thermalName, py.thermalName[id], `${id} thermalName`);
    assert.equal(entry.slicerName, py.slicerName[id], `${id} slicerName`);
    assert.equal(entry.canonicalSourceSha256, py.sha[id], `${id} canonical source digest`);
    assert.equal(entry.quality, py.evidence[id].quality, `${id} quality`);
    assert.equal(entry.quality, 'estimated', `${id} keeps the authority label`);
    assert.equal(entry.source, py.evidence[id].source, `${id} source`);
  }
  const in625 = committed.secondary.in625;
  assert.deepEqual(in625.thermal, py.in625);
  assert.equal(in625.quality, 'secondary-unreconciled');
  assert.equal(in625.registryCatalogQuality, py.in625Catalog.quality);
  assert.equal(in625.registryCatalogNote, py.in625Catalog.note);
  const values = (quantity: string) => in625.unreconciledPythonValues.find(v => v.quantity === quantity)?.values.map(v => v.value);
  assert.deepEqual(values('latent heat of fusion'), [py.in625.latent_heat_fusion_J_kg, ...py.in625Other.latent]);
  assert.deepEqual(values('boiling point'), [py.in625.boiling_C, Number((py.in625Other.boiling_K - 273.15).toFixed(2))]);
  assert.deepEqual(values('IR absorptivity'), [py.in625.absorptivity_IR, py.in625Other.absorptivity]);
  assert.match(in625.note, /290000 vs 290000 vs 227000 J\/kg/);
  assert.match(in625.note, /2880 vs 2900 C/);
});

test('accessor refuses an unsupported schemaVersion and labels every row it serves', () => {
  assert.throws(() => checkedAuthorityDocument({ ...LPBF_MATERIAL_AUTHORITY, schemaVersion: 2 }), /schemaVersion 2 is not the supported 1/);
  assert.throws(() => checkedAuthorityDocument(null), /schemaVersion undefined/);
  for (const id of FOUR) assert.equal(authorityThermalProvenance(id).quality, 'estimated');
  assert.equal(authorityThermalProvenance('in625').quality, 'secondary-unreconciled');
  assert.throws(() => authorityThermalProvenance('cocrmo'), /no surrogate alloy/);
});

test('ALLOY_THERMAL_PROPERTIES reads the authority; the UI computes no normalized enthalpy', () => {
  for (const id of [...FOUR, 'in625'] as const) {
    const t = authorityThermal(id);
    const c = ALLOY_THERMAL_PROPERTIES[id];
    assert.equal(c.meltingPoint_C, t.liquidus_C, id);
    assert.equal(c.density_kg_m3, t.density_kg_m3, id);
    assert.equal(c.specificHeat_J_kgK, t.specific_heat_J_kgK, id);
    assert.equal(c.thermalConductivity_W_mK, t.thermal_conductivity_W_mK, id);
    assert.equal(c.defaultAbsorptivity, t.absorptivity_IR, id);
    assert.deepEqual(Object.keys(c).sort(), ['defaultAbsorptivity', 'density_kg_m3', 'keyholeVedThreshold_J_mm3', 'lofVedThreshold_J_mm3', 'meltingPoint_C', 'specificHeat_J_kgK', 'thermalConductivity_W_mK'], id);
  }
  assert.equal('calculateNormalizedEnthalpy' in foundation, false);
  for (const record of Object.values(MASTER_LPBF_REFERENCE_DATASETS).flat()) {
    assert.equal(record.params.derived.normalizedEnthalpy_dH_hs, undefined, record.id);
  }
});

test('literature nearest match ranks only by P, v, h, t and peak intensity (no TS/Python ΔH mix)', () => {
  const pool = MASTER_LPBF_REFERENCE_DATASETS.in718;
  const [P, v, h, t, d] = [285, 960, 110, 40, 80];
  const liveI0 = foundation.calculatePeakLaserIntensity(P, d);
  const distance = (r: (typeof pool)[number]) => {
    const p = r.params;
    return Math.abs(p.laserPower_W - P) / P + Math.abs(p.scanSpeed_mm_s - v) / v + Math.abs(p.hatchSpacing_um - h) / h
      + Math.abs(p.layerThickness_um - t) / t + Math.abs(p.derived.peakLaserIntensity_MW_cm2 - liveI0) / Math.max(1, liveI0);
  };
  const expected = pool.reduce((best, r) => (distance(r) < distance(best) ? r : best));
  const match = findNearestLiteratureRecord('in718', P, v, h, t, { beamDiameter_um: d });
  assert.equal(match?.record.id, expected.id);
  assert.equal(match?.distance, distance(expected));
  // A live ΔH/h_s (as the decision lab used to pass) has no effect: the field is gone from the API.
  const withDh = findNearestLiteratureRecord('in718', P, v, h, t, { beamDiameter_um: d, normalizedEnthalpy: 99 } as never);
  assert.deepEqual(withDh, match);
});

test('no TS file computes or ranks by normalized enthalpy', () => {
  const files: string[] = [];
  const walk = (dir: string) => {
    for (const name of readdirSync(dir)) {
      const full = path.join(dir, name);
      if (statSync(full).isDirectory()) walk(full);
      else if (/\.tsx?$/.test(name)) files.push(full);
    }
  };
  walk('src');
  for (const file of files) {
    const text = readFileSync(file, 'utf8');
    const hit = text.match(/\bcalculateNormalizedEnthalpy\s*[(<]|enthalpyOfMelting_hs|normalizedEnthalpy_dH_hs\s*:\s*[a-zA-Z0-9]/);
    assert.equal(hit?.[0], undefined, `${file} computes or assigns a TS normalized enthalpy`);
  }
});

test('unknown alloy or preset is unavailable: no silent surrogate', () => {
  const unknown = 'cocrmo' as unknown as LPBFAlloyId;
  assert.throws(() => classifyProcessRegime(60, 200, 800, unknown), /Unknown LPBF alloy "cocrmo"/);
  assert.throws(() => alloyThermalConstants('toString' as unknown as LPBFAlloyId), /Unknown LPBF alloy/);
  assert.throws(() => authorityThermal('cocrmo'), /no surrogate alloy/);
  assert.throws(() => authorityPvWindow('in625'), /no surrogate alloy/);
  assert.throws(() => solidificationPresetInputs('Inconel 625'), /Unknown material preset "Inconel 625"/);
  assert.throws(() => solidificationPresetInputs('toString'), /Unknown material preset/);
  assert.throws(() => transientGpuRequest({ ...gpuParams('IN718'), material: 'IN625' as never }), /Unknown material preset "IN625"/);
});

test('lpbfFourAlloySchema P-v boxes equal the authority; IN625 stays TS-local', () => {
  for (const id of FOUR) {
    const { powerMin_W, powerMax_W, speedMin_mm_s, speedMax_mm_s } = LITERATURE_PV_WINDOWS[id];
    assert.deepEqual({ powerMin_W, powerMax_W, speedMin_mm_s, speedMax_mm_s }, LPBF_MATERIAL_AUTHORITY.alloys[id].literaturePvWindow, id);
    assert.ok(LITERATURE_PV_WINDOWS[id].sources.length > 0, `${id} keeps its sources`);
  }
  assert.equal(LITERATURE_PV_WINDOWS.in625.powerMax_W, 350);
});

/** A label names its alloy: Python's own resolver agrees, or (where it has no alias) the label's words equal a Python name. */
function assertLabelNamesAlloy(label: string, id: AuthorityAlloyId) {
  const resolved = live().resolved[label];
  if (resolved !== null) { assert.equal(resolved, id, `Python resolve_alloy_id(${label})`); return; }
  const words = (s: string) => s.toLowerCase().split(/[\s-]+/).filter(Boolean).sort().join(' ');
  const entry = LPBF_MATERIAL_AUTHORITY.alloys[id];
  assert.ok([entry.thermalName, entry.slicerName].some(name => words(name) === words(label)), `${label} does not name ${entry.thermalName}/${entry.slicerName}`);
}

function gpuParams(material: string): GpuLabParams {
  return { nx: 64, ny: 64, nz: 32, dx: 2, dy: 2, dz: 2, power_W: 200, T_preheat_K: 300, material: material as GpuLabParams['material'] };
}

test('GPU lab: each dropdown label maps to its alloy and the payload carries the alloy id and no material numbers', () => {
  assert.deepEqual({ ...GPU_LAB_MATERIALS }, GPU_LABELS);
  for (const [label, id] of Object.entries(GPU_LABELS)) {
    assertLabelNamesAlloy(label, id);
    const request = transientGpuRequest(gpuParams(label));
    assert.equal(request.alloyId, id, label);
    // Python (four_alloy_materials) is the only material authority for this RPC: no alloy numbers are sent.
    for (const key of ['rho', 'L_f', 'T_solidus', 'T_liquidus', 'Lv', 'Rs', 'Tv', 'cp_solid', 'cp_liquid', 'k_solid', 'k_liquid']) {
      assert.ok(!(key in request), `${label} request must not carry ${key}`);
    }
  }
  // The component hands this builder's output to the service unchanged.
  const source = readFileSync('src/components/TransientEnthalpy3DGPULab.tsx', 'utf8');
  assert.match(source, /computeTransient3DGPU\(transientGpuRequest\(params\)\)/);
  assert.equal(source.match(/computeTransient3DGPU\(/g)?.length, 1);
});

test('Solidification lab: each preset label maps to its alloy and the payload carries the authority row', () => {
  assert.deepEqual({ ...SOLIDIFICATION_PRESETS }, SOLIDIFICATION_LABELS);
  const process = { power_W: 285, speed_mm_s: 960, hatch_um: 110, layerThickness_um: 40 };
  for (const [label, id] of Object.entries(SOLIDIFICATION_LABELS)) {
    assertLabelNamesAlloy(label, id);
    const t = LPBF_MATERIAL_AUTHORITY.alloys[id].thermal;
    const expected = { k_WmK: t.thermal_conductivity_W_mK, liquidus_K: celsiusToKelvin(t.liquidus_C), absorptivity: t.absorptivity_IR };
    assert.deepEqual(solidificationPresetInputs(label), expected, label);
    assert.deepEqual(solidificationMaterialInputs(id), expected, label);
    assert.deepEqual(solidificationRequest(label, process), { params: process, material: expected }, label);
  }
  const source = readFileSync('src/components/SolidificationMicrostructureLab.tsx', 'utf8');
  assert.match(source, /computeSolidificationMicrostructure\(solidificationRequest\(selectedAlloy,/);
  assert.match(source, /const alloyProps = solidificationPresetInputs\(selectedAlloy\);/);
  assert.equal(celsiusToKelvin(1336), 1609.15);
  assert.equal(celsiusToKelvin(595), 868.15);
});

test('the consumer files hold no alloy-property literals, named numeric constants or numeric tables', () => {
  const property = /\b(rho|L_f|T_solidus|T_liquidus|cp_solid|cp_liquid|k_solid|k_liquid|k_WmK|liquidus_K|absorptivity|meltingPoint_C|density_kg_m3|specificHeat_J_kgK|thermalConductivity_W_mK|thermalDiffusivity_m2_s|enthalpyOfMelting_hs_J_m3|defaultAbsorptivity|powerMin_W|powerMax_W|speedMin_mm_s|speedMax_mm_s|Tm|Tl|Ts)\s*:\s*-?\d/;
  const namedConstant = /^\s*(export\s+)?(const|let|var)\s+\w+\s*(:[^=]+)?=\s*-?\d/;
  const numericTable = /\[\s*-?[\d.]+(e-?\d+)?\s*(,\s*-?[\d.]+(e-?\d+)?\s*){2,}\]/;
  // Allowed: the labelled TS-local IN625 box, orientation angles and a chart bar radius.
  const files: Record<string, { block?: RegExp; lines?: string[] }> = {
    'src/types/lpbfDataFoundation.ts': {},
    'src/components/TransientEnthalpy3DGPULab.tsx': {},
    'src/components/SolidificationMicrostructureLab.tsx': { lines: ['radius={[7, 7, 2, 2]}'] },
    'src/utils/lpbfFourAlloySchema.ts': { block: /const IN625_PV_WINDOW_TS_LOCAL[\s\S]*?\n};\n/, lines: ['([0, 45, 90] as const)'] },
    'src/data/lpbfMaterialAuthority.ts': { lines: ['export const LPBF_MATERIAL_AUTHORITY_SCHEMA_VERSION = 1;'] },
  };
  for (const [file, allowed] of Object.entries(files)) {
    let text = readFileSync(file, 'utf8').replace(/\r\n/g, '\n');
    if (allowed.block) {
      assert.match(text, allowed.block, `${file}: expected the labelled TS-local block`);
      text = text.replace(allowed.block, '');
    }
    const hits = text.split('\n').filter(line => (property.test(line) || namedConstant.test(line) || numericTable.test(line))
      && !(allowed.lines ?? []).some(ok => line.includes(ok)));
    assert.deepEqual(hits, [], `${file} holds alloy-like numeric literals`);
  }
});
