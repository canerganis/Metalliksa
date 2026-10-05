import assert from 'node:assert/strict';
import { test } from 'node:test';
import * as tafel from '../src/utils/tafelParser';

// Synthetic CSV fixtures characterize header handling, not native instrument-file compatibility.
// Legacy magnitude/column heuristics below are not scientific validation; inferred units are not verified units.

function generateRows(n: number, potFn: (i: number) => number, curFn: (i: number) => number): string {
  const rows: string[] = [];
  for (let i = 0; i < n; i++) {
    rows.push(`${potFn(i).toFixed(4)},${curFn(i).toExponential(4)}`);
  }
  return rows.join('\n');
}

test('Synthetic CSV: recognizes EC-Lab header signature and legacy NHE-to-SHE normalization', () => {
  const header = `
EC-Lab ASCII File
Nb header lines : 5
Scan Rate: 10 mV/s
Reference: NHE
Potential (V), Current (mA)
  `.trim() + '\n';
  const csv = header + generateRows(12, i => -0.5 + i * 0.01, i => 0.1 + i * 0.01);
  const ds = tafel.parseTafelFile(csv, 'data.csv');
  assert.equal(ds.sourceInstrument, 'biologic');
  assert.equal(ds.metadata.scanRateMv_s, 10);
  assert.equal(ds.metadata.referenceElectrode, 'SHE');
  assert.equal(ds.metadata.refOffsetVsSHE, 0);
  assert.equal(ds.points[0].potentialSHE, ds.points[0].potential);
});

test('Synthetic CSV: recognizes Gamry header signature and V/s scan rate conversion', () => {
  const header = `
EXPLAIN
TAG\tGAMRY
CURVE\tTABLE
d(E)/dt\t0.05 V/s
Vf (V), Im (A)
  `.trim() + '\n';
  const csv = header + generateRows(12, i => -0.5 + i * 0.01, i => 1e-6);
  const ds = tafel.parseTafelFile(csv, 'data.csv');
  assert.equal(ds.sourceInstrument, 'gamry');
  assert.equal(ds.metadata.scanRateMv_s, 50);
});

test('Synthetic CSV: recognizes Autolab/NOVA and VersaStudio header signatures', () => {
  const autolabDs = tafel.parseTafelFile('Autolab NOVA data\nPotential (V), Current (A)\n' + generateRows(12, i => -0.5 + i * 0.01, i => 1), 'data.csv');
  assert.equal(autolabDs.sourceInstrument, 'autolab');

  const parDs = tafel.parseTafelFile('VersaStudio\nPotential (V), Current (A)\n' + generateRows(12, i => -0.5 + i * 0.01, i => 1), 'data.csv');
  assert.equal(parDs.sourceInstrument, 'par');
});

test('Edge: Skips malformed rows, comments, and empty lines', () => {
  const csv = `
Potential (V), Current (A)
// this is a comment
-0.5, 1e-6
# another comment
-0.49, 1.1e-6

; ini style comment
-0.48, 1.2e-6
garbage, text, here
-0.47, 1.3e-6
-0.46, 1.4e-6
-0.45, 1.5e-6
-0.44, 1.6e-6
-0.43, 1.7e-6
-0.42, 1.8e-6
-0.41, 1.9e-6
-0.40, 2.0e-6
-0.39, 2.1e-6
  `.trim();
  const ds = tafel.parseTafelFile(csv, 'comments.csv');
  assert.equal(ds.points.length, 12);
  assert.equal(ds.points[0].potential, -0.5);
  assert.equal(ds.points[11].potential, -0.39);
});

test('Explicit current-density header bypasses area normalization', () => {
  const csv = `
E (V), I (mA/cm2)
-0.5, 2.5
-0.4, 3.0
-0.3, 3.5
-0.2, 4.0
-0.1, 4.5
0.0, 5.0
0.1, 5.5
0.2, 6.0
0.3, 6.5
0.4, 7.0
0.5, 7.5
0.6, 8.0
  `.trim();
  const ds = tafel.parseTafelFile(csv, 'density.csv', 10); // Custom area 10 is ignored
  assert.equal(ds.points[0].currentUnit, 'mA');
  assert.equal(ds.points[0].currentDensity_uA_cm2, 2500); // 2.5 mA = 2500 uA
});

test('Legacy heuristic characterization: unitless values well above10 inferred as uA', () => {
  const csv = `Potential, Current\n` + generateRows(12, i => -0.5 + i * 0.05, i => 15.0 + i);
  const ds = tafel.parseTafelFile(csv, 'infer_ua.csv');
  assert.equal(ds.points[0].currentUnit, 'uA');
  assert.equal(ds.points[0].currentDensity_uA_cm2, 15.0);
});

test('Legacy heuristic characterization: unitless values between0.05and10 inferred as mA', () => {
  const csv = `Potential, Current\n` + generateRows(12, i => -0.5 + i * 0.05, i => 0.10 + i * 0.01);
  const ds = tafel.parseTafelFile(csv, 'infer_ma.csv');
  assert.equal(ds.points[0].currentUnit, 'mA');
  assert.equal(ds.points[0].currentDensity_uA_cm2, 100.0); // 0.1 mA = 100 uA
});

test('Legacy heuristic characterization: unitless values well below0.05 inferred as A', () => {
  const csv = `Potential, Current\n` + generateRows(12, i => -0.5 + i * 0.05, i => 0.01 + i * 0.001);
  const ds = tafel.parseTafelFile(csv, 'infer_a.csv');
  assert.equal(ds.points[0].currentUnit, 'A');
  assert.equal(ds.points[0].currentDensity_uA_cm2, 10000.0); // 0.01 A = 10000 uA
});

test('Legacy heuristic characterization: headerless current-first sample uses column swap', () => {
  const csv = `
6.0, -2.0
6.1, -1.9
6.2, -1.8
6.3, -1.7
6.4, -1.6
6.5, -1.5
6.6, -1.4
6.7, -1.3
6.8, -1.2
6.9, -1.1
7.0, -1.0
7.1, -0.9
  `.trim();
  const ds = tafel.parseTafelFile(csv, 'swapped.csv');
  assert.equal(ds.points[0].potential, -2.0);
  assert.equal(ds.points[0].currentRaw, 6.0);
  assert.equal(ds.points[11].potential, -0.9);
  assert.equal(ds.points[11].currentRaw, 7.1);
});

test('Edge: Parses space-separated values with decimal commas and scientific notation', () => {
  const csv = `
E I
-0,5 1,1e-6
-0,4 1,2e-6
-0,3 1,3e-6
-0,2 1,4e-6
-0,1 1,5e-6
0,0 1,6e-6
0,1 1,7e-6
0,2 1,8e-6
0,3 1,9e-6
0,4 2,0e-6
0,5 2,1e-6
0,6 2,2e-6
  `.trim();
  const ds = tafel.parseTafelFile(csv, 'euro_scientific.txt');
  assert.equal(ds.points[0].potential, -0.5);
  assert.equal(ds.points[0].currentRaw, 1.1e-6);
  assert.equal(ds.points[11].potential, 0.6);
  assert.equal(ds.points[11].currentRaw, 2.2e-6);
});
