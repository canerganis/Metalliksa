import assert from 'node:assert/strict';
import { test } from 'node:test';
import { exportDatasetToCSV, parseBioLogicMpt, parseDelimitedEIS, parseEISFile, parseGamryFile } from '../src/utils/eisFileParser';
import type { ExperimentalEISDataset } from '../src/types/eisData';

const near = (a: number, b: number, rel = 1e-6) => Math.abs(a - b) <= rel * Math.max(1, Math.abs(b));

const MPT = [
  'EC-Lab ASCII FILE',
  'Nb header lines : 6',
  'Potentiostatic Electrochemical Impedance Spectroscopy',
  'Run on channel : 1',
  '',
  'freq/Hz\tRe(Z)/Ohm\t-Im(Z)/Ohm\t|Z|/Ohm\tPhase(Z)/deg',
  '1.0000E+01\t12.0\t3.0\t12.369\t-14.036',
  '1.0000E+05\t10.0\t0.5\t10.012\t-2.862',
  '1.0000E+03\t11.0\t2.0\t11.180\t-10.305',
].join('\n');

const DTA = [
  'EXPLAIN',
  'TAG\tEISPOT',
  'TITLE\tLABEL\tPotentiostatic EIS\tTest',
  'ZCURVE\tTABLE\t3',
  '\tPt\tTime\tFreq\tZreal\tZimag\tZsig\tZmod\tZphz\tIdc\tVdc\tIERange',
  '\t#\ts\tHz\tohm\tohm\tV\tohm\tdeg\tA\tV\t#',
  '\t0\t0.1\t100000\t10.0\t-0.5\t0.0\t10.012\t-2.862\t0\t0\t5',
  '\t1\t0.2\t1000\t11.0\t-2.0\t0.0\t11.180\t-10.305\t0\t0\t5',
  '\t2\t0.3\t10\t12.0\t-3.0\t0.0\t12.369\t-14.036\t0\t0\t5',
].join('\n');

test('BioLogic mpt fixture parses to frequency-sorted points with the -Im(Z) convention', () => {
  const ds = parseBioLogicMpt(MPT, 'cell_a.mpt');
  assert.equal(ds.source, 'biologic');
  assert.equal(ds.sourceFilename, 'cell_a.mpt');
  assert.equal(ds.name, 'cell_a');
  assert.deepEqual(ds.points.map((p) => p.frequency), [1e5, 1e3, 10]);
  assert.deepEqual(ds.points.map((p) => p.zReal), [10, 11, 12]);
  for (const p of ds.points) {
    assert.ok(p.zImag < 0, 'capacitive Im(Z) is negative');
    assert.ok(near(p.minusZImag, -p.zImag));
    assert.ok(near(p.zMag, Math.hypot(p.zReal, p.zImag), 1e-9));
  }
  assert.ok(near(ds.points[0].zImag, -0.5));
});

test('BioLogic mpt parsing does not invent measurement metadata', () => {
  const ds = parseBioLogicMpt(MPT, 'cell_a.mpt');
  assert.equal(ds.metadata, undefined);
});

test('Gamry dta fixture parses Zreal/Zimag columns by header and skips the units row', () => {
  const ds = parseGamryFile(DTA, 'cell_b.dta');
  assert.equal(ds.source, 'gamry');
  assert.equal(ds.points.length, 3);
  assert.deepEqual(ds.points.map((p) => p.frequency), [1e5, 1e3, 10]);
  assert.deepEqual(ds.points.map((p) => p.zReal), [10, 11, 12]);
  assert.deepEqual(ds.points.map((p) => p.zImag), [-0.5, -2, -3]);
  assert.ok(ds.points.every((p) => p.minusZImag > 0));
});

test('Gamry dta parsing does not invent measurement metadata', () => {
  assert.equal(parseGamryFile(DTA, 'cell_b.dta').metadata, undefined);
});

test('parseEISFile routes by extension and content signature', () => {
  assert.equal(parseEISFile(MPT, 'a.mpt').source, 'biologic');
  assert.equal(parseEISFile(DTA, 'b.dta').source, 'gamry');
});

test('parseEISFile reads a JSON points dataset and keeps supplied metadata only', () => {
  const json = JSON.stringify({ name: 'j', points: [{ frequency: 100, zReal: 5, zImag: -1 }, { frequency: 10, zReal: 6, zImag: -2 }] });
  const ds = parseEISFile(json, 'j.json');
  assert.equal(ds.points.length, 2);
  assert.equal(ds.metadata, undefined);
  assert.ok(near(ds.points[0].minusZImag, 1));
});

test('parseDelimitedEIS rejects empty input and files without usable rows', () => {
  assert.throws(() => parseDelimitedEIS('   \n\n'), /Empty data file/);
  assert.throws(() => parseDelimitedEIS('freq,zreal,zimag\nabc,def,ghi\n'), /Could not extract/);
});

test('exportDatasetToCSV -> parseDelimitedEIS round trip preserves every point', () => {
  const points = [1e5, 3.1623e3, 100, 1, 0.01].map((f, i) => {
    const zReal = 10 + 5 * i, zImag = -(0.5 + 3 * i);
    return { frequency: f, zReal, zImag, minusZImag: -zImag, zMag: Math.hypot(zReal, zImag), phaseDeg: (Math.atan2(zImag, zReal) * 180) / Math.PI };
  });
  const original: ExperimentalEISDataset = { id: 'x', name: 'x', source: 'csv', description: 'x', points };
  const parsed = parseDelimitedEIS(exportDatasetToCSV(original), 'round_trip.csv');
  assert.equal(parsed.points.length, points.length);
  assert.equal(parsed.source, 'csv');
  assert.equal(parsed.metadata, undefined);
  points.forEach((p, i) => {
    const q = parsed.points[i];
    assert.ok(near(q.frequency, p.frequency, 1e-6), `freq ${i}`);
    assert.ok(near(q.zReal, p.zReal, 1e-6), `zReal ${i}`);
    assert.ok(near(q.zImag, p.zImag, 1e-6), `zImag ${i}`);
    assert.ok(near(q.minusZImag, p.minusZImag, 1e-6), `minusZImag ${i}`);
  });
});

test('exportDatasetToCSV writes the documented header and one row per point', () => {
  const csv = exportDatasetToCSV({ id: 'x', name: 'x', source: 'csv', description: '', points: [
    { frequency: 10, zReal: 1, zImag: -1, minusZImag: 1, zMag: Math.SQRT2, phaseDeg: -45 },
  ] });
  const lines = csv.split('\n');
  assert.equal(lines[0], 'Frequency_Hz,Z_Real_Ohm,Minus_Z_Imag_Ohm,Z_Imag_Ohm,Z_Magnitude_Ohm,Phase_Deg');
  assert.equal(lines.length, 2);
  assert.equal(lines[1].split(',').length, 6);
});
