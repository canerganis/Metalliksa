import assert from 'node:assert/strict';
import { test } from 'node:test';

// BUG 1 (fixed in Phase 6a step b): src/utils/tafelParser.ts used to build TAFEL_BENCHMARK_DATASETS at module load
// through createBenchmarkDataset(), which always throws, so the module could not be imported and these tests were todo.
// The module is imported directly now: a regression fails this file loudly instead of turning tests into todos.
import * as tafel from '../src/utils/tafelParser';

const mod = () => tafel;

/** Three-column CSV (time, potential, current) with a unit-bearing header and 12 data rows. */
function csv(extraHeader = ''): string {
  const rows = ['Time (s),Potential (V),Current (mA)'];
  for (let i = 0; i < 12; i++) rows.push(`${i},${(-0.3 + i * 0.01).toFixed(3)},${(0.001 * (i + 1)).toFixed(4)}`);
  return extraHeader + rows.join('\n');
}

test('REFERENCE_ELECTRODES lists the documented offsets versus SHE', () => {
  const refs = mod().REFERENCE_ELECTRODES;
  assert.equal(refs.SHE.offsetVsSHE, 0);
  assert.equal(refs.SCE.offsetVsSHE, 0.241);
  assert.equal(refs['Ag/AgCl'].offsetVsSHE, 0.197);
  assert.equal(refs.MSE.offsetVsSHE, 0.64);
  assert.equal(refs.Custom.offsetVsSHE, 0);
});

test('parseTafelFile reads a CSV with a mA unit header and converts to uA/cm2 by area', () => {
  const ds = mod().parseTafelFile(csv(), 'run_1.csv', 2);
  assert.equal(ds.points.length, 12);
  assert.equal(ds.points[0].currentUnit, 'mA');
  assert.equal(ds.points[0].potential, -0.3);
  // 0.001 mA = 1 uA, divided by 2 cm2
  assert.ok(Math.abs(ds.points[0].currentDensity_uA_cm2 - 0.5) < 1e-9);
  assert.ok(Math.abs(ds.points[0].logCurrentDensity - Math.log10(0.5)) < 1e-9);
  assert.equal(ds.metadata.electrodeAreaCm2, 2);
  assert.equal(ds.name, 'run 1');
  assert.equal(ds.sourceFilename, 'run_1.csv');
});

test('parseTafelFile keeps the sign of the current in signedCurrentDensity', () => {
  const rows = ['Time (s),Potential (V),Current (A)'];
  for (let i = 0; i < 12; i++) rows.push(`${i},${(-0.3 + i * 0.01).toFixed(3)},${i < 6 ? '-' : ''}0.000001`);
  const ds = mod().parseTafelFile(rows.join('\n'), 'signed.csv');
  assert.ok(ds.points[0].signedCurrentDensity_uA_cm2 < 0);
  assert.ok(ds.points[11].signedCurrentDensity_uA_cm2 > 0);
  assert.ok(ds.points[0].currentDensity_uA_cm2 > 0);
});

test('parseTafelFile defaults to the SCE offset and adds it to potentialSHE', () => {
  const ds = mod().parseTafelFile(csv(), 'x.csv');
  assert.equal(ds.metadata.referenceElectrode, 'SCE');
  assert.equal(ds.metadata.refOffsetVsSHE, 0.241);
  assert.ok(Math.abs((ds.points[0].potentialSHE ?? NaN) - (-0.3 + 0.241)) < 1e-9);
});

test('parseTafelFile picks up an Ag/AgCl reference from the header and applies its offset', () => {
  const ds = mod().parseTafelFile(csv('# Reference electrode: Ag/AgCl\n'), 'x.csv');
  assert.equal(ds.metadata.referenceElectrode, 'Ag/AgCl');
  assert.equal(ds.metadata.refOffsetVsSHE, 0.197);
  assert.ok(Math.abs((ds.points[0].potentialSHE ?? NaN) - (-0.3 + 0.197)) < 1e-9);
});

test('parseTafelFile rejects empty content and files with too few points', () => {
  assert.throws(() => mod().parseTafelFile('   \n'), /empty/);
  assert.throws(() => mod().parseTafelFile('Potential (V),Current (A),Time\n-0.3,1e-6,0\n'), /sufficient/);
});

// BUG 2 regression: a single comma can delimit two columns, not just a decimal fraction.
test('parseTafelFile accepts a plain two-column comma CSV', () => {
  const rows = ['Potential (V),Current (A)'];
  for (let i = 0; i < 12; i++) rows.push(`${(-0.3 + i * 0.01).toFixed(3)},${(1e-6 * (i + 1)).toExponential(3)}`);
  const ds = mod().parseTafelFile(rows.join('\n'), 'two_col.csv');
  assert.equal(ds.points.length, 12);
  assert.equal(ds.points[0].potential, -0.3);
  assert.equal(ds.points[0].currentRaw, 1e-6);
  assert.equal(ds.points[11].currentRaw, 12e-6);
});

for (const delimiter of [',', ', ', ';', '\t', '   ', ' ']) {
  test(`parseTafelFile distinguishes decimal commas from ${JSON.stringify(delimiter)} column delimiters`, () => {
    const decimalComma = delimiter !== ',' && delimiter !== ', ';
    // Whitespace headers avoid spaces within labels; CSV headers retain unit labels.
    const rows = [delimiter.trim() ? `Potential (V)${delimiter}Current (mA)` : `E(V)${delimiter}I(mA)`];
    for (let i = 0; i < 12; i++) {
      const potential = (-0.3 + i * 0.01).toFixed(3);
      const current = (i < 6 ? -0.001 : 0.002).toFixed(3);
      rows.push([potential, current].map(value => decimalComma ? value.replace('.', ',') : value).join(delimiter));
    }
    const ds = mod().parseTafelFile(rows.join('\n'), 'delimiters.csv', 2);
    assert.equal(ds.points.length, 12);
    assert.equal(ds.points[0].potential, -0.3);
    assert.equal(ds.points[11].potential, -0.19);
    assert.equal(ds.points[0].currentUnit, 'mA');
    assert.equal(ds.points[0].currentRaw, -0.001);
    assert.equal(ds.points[0].signedCurrentDensity_uA_cm2, -0.5);
    assert.equal(ds.points[11].signedCurrentDensity_uA_cm2, 1);
  });
}

test('parseTafelFile preserves a lone decimal comma in whitespace-separated scientific data without a header', () => {
  const rows = Array.from({ length: 12 }, (_, i) => `${(-0.3 + i * 0.01).toFixed(3).replace('.', ',')} -1e-6`);
  const ds = mod().parseTafelFile(rows.join('\n'), 'no_header.txt');
  assert.equal(ds.points.length, 12);
  assert.equal(ds.points[0].potential, -0.3);
  assert.equal(ds.points[0].currentRaw, -1e-6);
});

for (const [unit, current, density] of [['A', '-1e-6', -0.5], ['mA', '-0.001', -0.5], ['uA', '-1', -0.5], ['nA', '-1', -0.0005]] as const) {
  test(`parseTafelFile reads integer potentials in spaced two-column CSV with ${unit} currents`, () => {
    const rows = [`Potential (V), Current (${unit})`, ...Array.from({ length: 12 }, () => `-1, ${current}`)];
    const ds = mod().parseTafelFile(rows.join('\n'), 'integer.csv', 2);
    assert.equal(ds.points.length, 12);
    assert.equal(ds.points[0].potential, -1);
    assert.equal(ds.points[0].currentUnit, unit);
    assert.equal(ds.points[0].signedCurrentDensity_uA_cm2, density);
  });
}

// BUG 1 regression guard: the module imports and no longer exports a benchmark list or a curve-fabrication helper
// (both were removed: no measured benchmark curves are bundled, and PRNG-noise curves must not stand in for them).
test('tafelParser module imports without a benchmark list or curve-fabrication helper', () => {
  for (const name of ['TAFEL_BENCHMARK_DATASETS', 'createBenchmarkDataset']) {
    assert.equal(name in tafel, false, `${name} must not be exported`);
  }
  assert.equal(typeof tafel.autoFitTafel, 'function');
});
