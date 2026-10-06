import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildElasticityInput,
  SYMMETRY_FIELDS,
  type ElasticityFormState,
} from '../src/utils/elasticityInput';

function makeForm(overrides: Partial<ElasticityFormState> = {}): ElasticityFormState {
  return {
    input_mode: 'custom',
    crystal_system: 'cubic',
    cij: { c11: '240', c12: '-12.5', c44: '116' },
    k_vrh: '',
    g_vrh: '',
    density: '',
    formula: '',
    molar_mass: '',
    atoms_per_formula_unit: '',
    ...overrides,
  };
}

function isoForm(overrides: Partial<ElasticityFormState> = {}): ElasticityFormState {
  return makeForm({ input_mode: 'isotropic', crystal_system: 'isotropic', cij: {}, k_vrh: '170', g_vrh: '80', ...overrides });
}

const FULL_VALUES: Record<string, string> = {
  c11: '300', c22: '310', c33: '320', c12: '50', c13: '60', c23: '70',
  c14: '10', c44: '100', c55: '110', c66: '120',
};

function cijFor(system: string, drop?: string): Record<string, string> {
  const cij: Record<string, string> = {};
  for (const f of SYMMETRY_FIELDS[system]) {
    if (f !== drop) cij[f] = FULL_VALUES[f];
  }
  return cij;
}

test('SYMMETRY_FIELDS defines required independent constants per symmetry', () => {
  assert.deepEqual([...SYMMETRY_FIELDS.cubic].sort(), ['c11', 'c12', 'c44']);
  assert.ok(SYMMETRY_FIELDS.trigonal.includes('c14'));
  assert.ok(!SYMMETRY_FIELDS.hexagonal.includes('c14'));
  assert.deepEqual(
    [...SYMMETRY_FIELDS.orthorhombic].sort(),
    ['c11', 'c12', 'c13', 'c22', 'c23', 'c33', 'c44', 'c55', 'c66'],
  );
  assert.deepEqual([...SYMMETRY_FIELDS.tetragonal].sort(), ['c11', 'c12', 'c13', 'c33', 'c44', 'c66']);
  assert.deepEqual([...SYMMETRY_FIELDS.hexagonal].sort(), ['c11', 'c12', 'c13', 'c33', 'c44']);
});

test('empty custom form is invalid', () => {
  assert.throws(() => buildElasticityInput(makeForm({ cij: {} })));
  assert.throws(() => buildElasticityInput(makeForm({ cij: { c11: '', c12: '', c44: '' } })));
});

test('empty isotropic K/G is invalid', () => {
  assert.throws(() => buildElasticityInput(isoForm({ k_vrh: '', g_vrh: '' })));
  assert.throws(() => buildElasticityInput(isoForm({ k_vrh: '', g_vrh: '80' })));
  assert.throws(() => buildElasticityInput(isoForm({ k_vrh: '170', g_vrh: '   ' })));
});

test('custom cubic passes exact GPa values and allows negative off-diagonal', () => {
  const out = buildElasticityInput(makeForm());
  assert.equal(out.input_mode, 'custom');
  assert.equal(out.crystal_system, 'cubic');
  assert.deepEqual(out.custom_c_ij, { c11: 240, c12: -12.5, c44: 116 });
});

test('custom cubic missing c44 is invalid', () => {
  assert.throws(() => buildElasticityInput(makeForm({ cij: { c11: '240', c12: '10' } })));
  assert.throws(() => buildElasticityInput(makeForm({ cij: { c11: '240', c12: '10', c44: ' ' } })));
});

test('zero or negative diagonal constants are invalid', () => {
  for (const bad of ['0', '-5']) {
    assert.throws(() => buildElasticityInput(makeForm({ cij: { c11: bad, c12: '10', c44: '100' } })));
    assert.throws(() => buildElasticityInput(makeForm({ cij: { c11: '240', c12: '10', c44: bad } })));
  }
});

test('NaN, Infinity and non-numeric values are rejected', () => {
  for (const bad of ['NaN', 'Infinity', '-Infinity', 'abc']) {
    assert.throws(() => buildElasticityInput(makeForm({ cij: { c11: bad, c12: '10', c44: '100' } })));
    assert.throws(() => buildElasticityInput(makeForm({ cij: { c11: '240', c12: bad, c44: '100' } })));
  }
});

test('trigonal requires c14', () => {
  assert.throws(() =>
    buildElasticityInput(makeForm({ crystal_system: 'trigonal', cij: cijFor('trigonal', 'c14') })),
  );
  const out = buildElasticityInput(makeForm({ crystal_system: 'trigonal', cij: cijFor('trigonal') }));
  assert.equal(out.custom_c_ij.c14, 10);
});

test('orthorhombic requires all nine independent fields', () => {
  for (const f of SYMMETRY_FIELDS.orthorhombic) {
    assert.throws(
      () => buildElasticityInput(makeForm({ crystal_system: 'orthorhombic', cij: cijFor('orthorhombic', f) })),
      undefined,
      `missing ${f} should be invalid`,
    );
  }
  const out = buildElasticityInput(makeForm({ crystal_system: 'orthorhombic', cij: cijFor('orthorhombic') }));
  assert.equal(out.custom_c_ij.c22, 310);
  assert.equal(out.custom_c_ij.c55, 110);
  assert.equal(out.custom_c_ij.c23, 70);
});

test('custom mode with isotropic symmetry must supply c11 and c12', () => {
  assert.throws(() => buildElasticityInput(makeForm({ crystal_system: 'isotropic', cij: {} })));
  assert.throws(() => buildElasticityInput(makeForm({ crystal_system: 'isotropic', cij: { c11: '200' } })));
  assert.throws(() => buildElasticityInput(makeForm({ crystal_system: 'isotropic', cij: { c12: '50' } })));
  const out = buildElasticityInput(makeForm({ crystal_system: 'isotropic', cij: { c11: '200', c12: '50' } }));
  assert.equal(out.crystal_system, 'isotropic');
  assert.deepEqual(out.custom_c_ij, { c11: 200, c12: 50 });
});

test('isotropic K/G must be finite and positive', () => {
  for (const bad of ['0', '-1', 'NaN', 'Infinity', 'x']) {
    assert.throws(() => buildElasticityInput(isoForm({ k_vrh: bad })));
    assert.throws(() => buildElasticityInput(isoForm({ g_vrh: bad })));
  }
});

test('isotropic mode forces isotropic symmetry and passes K/G', () => {
  const out = buildElasticityInput(isoForm({ crystal_system: 'hexagonal' }));
  assert.equal(out.input_mode, 'isotropic');
  assert.equal(out.crystal_system, 'isotropic');
  assert.equal(out.k_vrh, 170);
  assert.equal(out.g_vrh, 80);
});

test('stale cij is omitted from isotropic payload', () => {
  const out = buildElasticityInput(isoForm({ cij: { c11: '999', c12: '1', c44: '5' } }));
  assert.ok(!('custom_c_ij' in out));
  assert.ok(!('cij' in out));
  assert.ok(!JSON.stringify(out).includes('999'));
});

test('blank optional density, formula and basis keys are omitted, not zero', () => {
  for (const out of [
    buildElasticityInput(makeForm({ density: '  ', formula: '   ', molar_mass: ' ', atoms_per_formula_unit: '' })),
    buildElasticityInput(isoForm({ density: '', formula: '' })),
  ]) {
    assert.ok(!('density' in out));
    assert.ok(!('formula' in out));
    assert.ok(!('molar_mass' in out));
    assert.ok(!('atoms_per_formula_unit' in out));
  }
});

test('formula is trimmed raw string with no library input', () => {
  const out = buildElasticityInput(makeForm({ formula: '  Ti6Al4V  ' }));
  assert.equal(out.formula, 'Ti6Al4V');
  assert.ok(!('library' in out));
  assert.ok(!('library_id' in out));
  assert.ok(!('alloy' in out));
});

test('optional density must be positive and finite', () => {
  assert.equal(buildElasticityInput(makeForm({ density: '4.43' })).density, 4.43);
  for (const bad of ['0', '-1', 'NaN', 'Infinity', 'abc']) {
    assert.throws(() => buildElasticityInput(makeForm({ density: bad })));
  }
});

test('molar mass and atoms per formula unit must be paired and positive', () => {
  const out = buildElasticityInput(makeForm({ molar_mass: '55.8', atoms_per_formula_unit: '2' }));
  assert.equal(out.molar_mass, 55.8);
  assert.equal(out.atoms_per_formula_unit, 2);
  assert.throws(() => buildElasticityInput(makeForm({ molar_mass: '55.8' })));
  assert.throws(() => buildElasticityInput(makeForm({ atoms_per_formula_unit: '2' })));
  for (const bad of ['0', '-3', 'NaN', 'Infinity']) {
    assert.throws(() => buildElasticityInput(makeForm({ molar_mass: bad, atoms_per_formula_unit: '2' })));
    assert.throws(() => buildElasticityInput(makeForm({ molar_mass: '55.8', atoms_per_formula_unit: bad })));
  }
});

test('basis fields also apply in isotropic mode', () => {
  const out = buildElasticityInput(isoForm({ density: '7.8', molar_mass: '55.8', atoms_per_formula_unit: '1' }));
  assert.equal(out.density, 7.8);
  assert.equal(out.molar_mass, 55.8);
  assert.equal(out.atoms_per_formula_unit, 1);
});

test('does not mutate the form', () => {
  const form = makeForm({ formula: ' Fe ', density: '7.8', molar_mass: '55.8', atoms_per_formula_unit: '1' });
  const snapshot = structuredClone(form);
  buildElasticityInput(form);
  assert.deepEqual(form, snapshot);

  const iso = isoForm({ cij: { c11: '1' }, formula: ' x ' });
  const isoSnapshot = structuredClone(iso);
  buildElasticityInput(iso);
  assert.deepEqual(iso, isoSnapshot);
});
