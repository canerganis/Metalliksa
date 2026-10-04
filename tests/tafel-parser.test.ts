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

// BUG 2 (real, independent of BUG 1): splitLineToTokens only splits on a comma when the line has more than two
// comma-separated parts, so a plain two-column comma CSV (Potential,Current) is rejected as having no data.
// Confirmed against a scratch copy with BUG 1 stubbed out. Stays todo after BUG 1 is fixed.
test('parseTafelFile accepts a plain two-column comma CSV', { todo: 'BUG 2: splitLineToTokens does not split two-column comma CSV lines' }, () => {
  const rows = ['Potential (V),Current (A)'];
  for (let i = 0; i < 12; i++) rows.push(`${(-0.3 + i * 0.01).toFixed(3)},${(1e-6 * (i + 1)).toExponential(3)}`);
  const ds = mod().parseTafelFile(rows.join('\n'), 'two_col.csv');
  assert.equal(ds.points.length, 12);
});

// BUG 1 regression guard: the module imports, lists no fabricated benchmark curves, and the fabrication helper still refuses.
test('tafelParser module imports without fabricating benchmark curves', () => {
  assert.deepEqual(tafel.TAFEL_BENCHMARK_DATASETS, []);
  assert.throws(() => tafel.createBenchmarkDataset({} as Parameters<typeof tafel.createBenchmarkDataset>[0]),
    /Fabrication of Tafel potentiodynamic polarization curves via PRNG noise is disabled/);
});
