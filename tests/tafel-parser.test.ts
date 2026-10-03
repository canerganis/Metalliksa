import assert from 'node:assert/strict';
import { test } from 'node:test';

// BUG 1 (real, reported, not fixed here): src/utils/tafelParser.ts evaluates TAFEL_BENCHMARK_DATASETS at module load and
// createBenchmarkDataset() unconditionally throws "Fabrication of Tafel ... is disabled", so the module cannot be imported.
// Only that exact signature is tolerated: tests that need the module are marked todo (blocked by BUG 1). Any other import
// error is rethrown so the file fails loudly. The todo-ed assertions were verified against a scratch copy of the module
// with the benchmark construction stubbed out (not part of this repo).
type TafelModule = typeof import('../src/utils/tafelParser');
let tafel: TafelModule | undefined;
let bug1: Error | undefined;
try {
  tafel = await import('../src/utils/tafelParser');
} catch (error) {
  if (error instanceof Error && /Fabrication of Tafel/.test(error.message)) bug1 = error;
  else throw error;
}
const todo = bug1 ? 'BLOCKED by BUG 1: tafelParser.ts throws on import (createBenchmarkDataset)' : false;
const mod = (): TafelModule => {
  if (!tafel) throw bug1;
  return tafel;
};

/** Three-column CSV (time, potential, current) with a unit-bearing header and 12 data rows. */
function csv(extraHeader = ''): string {
  const rows = ['Time (s),Potential (V),Current (mA)'];
  for (let i = 0; i < 12; i++) rows.push(`${i},${(-0.3 + i * 0.01).toFixed(3)},${(0.001 * (i + 1)).toFixed(4)}`);
  return extraHeader + rows.join('\n');
}

test('REFERENCE_ELECTRODES lists the documented offsets versus SHE', { todo }, () => {
  const refs = mod().REFERENCE_ELECTRODES;
  assert.equal(refs.SHE.offsetVsSHE, 0);
  assert.equal(refs.SCE.offsetVsSHE, 0.241);
  assert.equal(refs['Ag/AgCl'].offsetVsSHE, 0.197);
  assert.equal(refs.MSE.offsetVsSHE, 0.64);
  assert.equal(refs.Custom.offsetVsSHE, 0);
});

test('parseTafelFile reads a CSV with a mA unit header and converts to uA/cm2 by area', { todo }, () => {
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

test('parseTafelFile keeps the sign of the current in signedCurrentDensity', { todo }, () => {
  const rows = ['Time (s),Potential (V),Current (A)'];
  for (let i = 0; i < 12; i++) rows.push(`${i},${(-0.3 + i * 0.01).toFixed(3)},${i < 6 ? '-' : ''}0.000001`);
  const ds = mod().parseTafelFile(rows.join('\n'), 'signed.csv');
  assert.ok(ds.points[0].signedCurrentDensity_uA_cm2 < 0);
  assert.ok(ds.points[11].signedCurrentDensity_uA_cm2 > 0);
  assert.ok(ds.points[0].currentDensity_uA_cm2 > 0);
});

test('parseTafelFile defaults to the SCE offset and adds it to potentialSHE', { todo }, () => {
  const ds = mod().parseTafelFile(csv(), 'x.csv');
  assert.equal(ds.metadata.referenceElectrode, 'SCE');
  assert.equal(ds.metadata.refOffsetVsSHE, 0.241);
  assert.ok(Math.abs((ds.points[0].potentialSHE ?? NaN) - (-0.3 + 0.241)) < 1e-9);
});

test('parseTafelFile picks up an Ag/AgCl reference from the header and applies its offset', { todo }, () => {
  const ds = mod().parseTafelFile(csv('# Reference electrode: Ag/AgCl\n'), 'x.csv');
  assert.equal(ds.metadata.referenceElectrode, 'Ag/AgCl');
  assert.equal(ds.metadata.refOffsetVsSHE, 0.197);
  assert.ok(Math.abs((ds.points[0].potentialSHE ?? NaN) - (-0.3 + 0.197)) < 1e-9);
});

test('parseTafelFile rejects empty content and files with too few points', { todo }, () => {
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

// Documents BUG 1 itself: becomes a passing todo (reported by node:test) once the module imports again.
test('tafelParser module can be imported', { todo: 'BUG 1: tafelParser.ts throws on import (createBenchmarkDataset)' }, () => {
  assert.equal(bug1, undefined, bug1?.message);
});
