import assert from 'node:assert/strict';
import test from 'node:test';
import { parseRawEDSFile } from '../src/utils/edsParser';

test('imported delimited counts require declared energy units and do not invent metadata/background', () => {
  const parsed = parseRawEDSFile('Energy (keV),Counts\n0.25,12\n0.50,28\n0.75,9', 'spectrum.csv');

  assert.equal(parsed.beamEnergyKv, undefined);
  assert.equal(parsed.liveTimeSec, undefined);
  assert.equal(parsed.deadTimePct, undefined);
  assert.equal(parsed.energyCalibrationSource, 'Delimited source-declared energy unit');
  assert.deepEqual(parsed.points.map(point => [point.energyKeV, point.counts, point.background, point.netCounts]), [
    [0.25, 12, 0, 12], [0.5, 28, 0, 28], [0.75, 9, 0, 9],
  ]);
});

test('delimited channel values without declared energy units are rejected', () => {
  assert.throws(() => parseRawEDSFile('0,12\n1,28\n2,9', 'channels.csv'), /must declare an energy unit/);
});

test('EMSA acquisition metadata is preserved only when present in the source', () => {
  const parsed = parseRawEDSFile([
    '#FORMAT: EMSA/MAS Spectral Data File',
    '#NPOINTS: 5',
    '#XPERCHAN: 10',
    '#OFFSET: 0',
    '#XUNITS: eV',
    '#BEAMKV: 20',
    '#LIVETIME: 30',
    '#REALTIME: 32',
    '#SPECTRUM:',
    '1, 2, 3, 4, 5',
  ].join('\n'), 'spectrum.emsa');

  assert.equal(parsed.beamEnergyKv, 20);
  assert.equal(parsed.liveTimeSec, 30);
  assert.equal(parsed.deadTimePct, 6.25);
});

test('EMSA channel spacing cannot default when source calibration is absent', () => {
  assert.throws(() => parseRawEDSFile([
    '#FORMAT: EMSA/MAS Spectral Data File',
    '#NPOINTS: 2',
    '#OFFSET: 0',
    '#XUNITS: eV',
    '#SPECTRUM:',
    '1, 2',
  ].join('\n'), 'uncalibrated.emsa'), /missing source-declared XPERCHAN/);
});

test('opaque binary SPC bytes are not assigned an assumed 15 keV axis', () => {
  assert.throws(() => parseRawEDSFile(new ArrayBuffer(4096), 'opaque.spc'), /calibration metadata is not decoded/);
});

test('delimited fractional energies and counts are preserved exactly', () => {
  const parsed = parseRawEDSFile(
    '#ENERGY_UNIT: keV\n0.123456,12.375\n0.234567,9.625',
    'fractional.csv',
  );

  assert.deepEqual(parsed.points.map(point => [point.energyKeV, point.counts, point.netCounts]), [
    [0.123456, 12.375, 12.375],
    [0.234567, 9.625, 9.625],
  ]);
});

test('EMSA fractional calibrated energies and counts are preserved exactly', () => {
  const parsed = parseRawEDSFile([
    '#FORMAT: EMSA/MAS Spectral Data File',
    '#NPOINTS: 2',
    '#XPERCHAN: 0.000001',
    '#OFFSET: 0.123456',
    '#XUNITS: keV',
    '#SPECTRUM:',
    '12.375, 9.625',
  ].join('\n'), 'fractional.emsa');

  assert.deepEqual(parsed.points.map(point => [point.energyKeV, point.counts, point.netCounts]), [
    [0.123456, 12.375, 12.375],
    [0.123457, 9.625, 9.625],
  ]);
});

test('delimited energy and count tokens must be finite, complete, and nonnegative', () => {
  const invalid = [
    '0.25keV,12',
    '0.25,12counts',
    '1e309,12',
    '0.25,1e309',
    '0.25,-1',
  ];
  for (const row of invalid) {
    assert.throws(
      () => parseRawEDSFile(`#ENERGY_UNIT: keV\n${row}\n0.5,3`, 'invalid.csv'),
      `expected delimited row ${JSON.stringify(row)} to be rejected`,
    );
  }
});

test('EMSA calibration and count tokens must be finite, complete, and nonnegative', () => {
  const source = (xPerChan: string, counts: string, offset = '0.1') => [
    '#FORMAT: EMSA/MAS Spectral Data File',
    '#NPOINTS: 2',
    `#XPERCHAN: ${xPerChan}`,
    `#OFFSET: ${offset}`,
    '#XUNITS: keV',
    '#SPECTRUM:',
    counts,
  ].join('\n');
  const invalid = [
    source('0.01keV', '12, 3'),
    source('1e309', '12, 3'),
    source('0.01', '12, 3', '0.1keV'),
    source('1e308', '12, 3', '1e308'),
    source('0.01', '12counts, 3'),
    source('0.01', '1e309, 3'),
    source('0.01', '-1, 3'),
  ];

  for (const content of invalid) {
    assert.throws(
      () => parseRawEDSFile(content, 'invalid.emsa'),
      `expected invalid EMSA source ${JSON.stringify(content)} to be rejected`,
    );
  }
});

test('acquisition metadata preserves signed notation and rejects malformed values in both formats', () => {
  const emsa = (metadata: string) => [
    '#FORMAT: EMSA/MAS Spectral Data File', '#NPOINTS: 2',
    '#XPERCHAN: 0.01', '#OFFSET: 0', '#XUNITS: keV',
    metadata, '#SPECTRUM:', '12, 3',
  ].join('\n');
  const delimited = (metadata: string) => `${metadata}\nEnergy (keV),Counts\n0.25,12\n0.5,3`;
  for (const source of [emsa, delimited]) {
    const parsed = parseRawEDSFile(source('#BEAMKV: +1e1\n#LIVE_TIME: 3e1\n#REAL_TIME: 3.2e1\n#DEAD_TIME: 0'), 'metadata.txt');
    assert.equal(parsed.beamEnergyKv, 10);
    assert.equal(parsed.liveTimeSec, 30);
    assert.equal(parsed.deadTimePct, 0);
    for (const tag of ['BEAMKV', 'LIVETIME', 'REALTIME', 'DEADTIME']) {
      for (const value of ['-15', '12suffix', 'NaN', 'Infinity', '1e309', '']) {
        assert.throws(() => parseRawEDSFile(source(`#${tag}: ${value}`), 'invalid-metadata.txt'), `${tag}: ${value}`);
      }
    }
    for (const tag of ['BEAMKV', 'LIVETIME', 'REALTIME']) {
      assert.throws(() => parseRawEDSFile(source(`#${tag}: 0`), 'invalid-metadata.txt'));
    }
    assert.throws(() => parseRawEDSFile(source('#DEADTIME: 100.01'), 'invalid-metadata.txt'));
  }
});

test('finite negative EMSA offsets preserve the source-declared channel axis', () => {
  const parsed = parseRawEDSFile([
    '#FORMAT: EMSA/MAS Spectral Data File', '#NPOINTS: 2',
    '#XPERCHAN: 0.01', '#OFFSET: -0.01', '#XUNITS: keV',
    '#SPECTRUM:', '12, 3',
  ].join('\n'), 'negative-offset.emsa');
  assert.deepEqual(parsed.points.map(point => point.energyKeV), [-0.01, 0]);
});

test('delimited numeric rows reject missing columns and empty explicit fields', () => {
  for (const row of ['0.4', 'NaN', '0.25,,12', ',12', '0.25,', '0.25,12,', '0.25;;12', '0.25\t\t12']) {
    assert.throws(() => parseRawEDSFile(`Energy (keV),Counts\n0.1,2\n${row}\n0.5,3`, 'missing-field.csv'), `row ${JSON.stringify(row)}`);
  }
  for (const row of ['0.25, 12', '0.25; 12', '0.25\t12', '0.25    12']) {
    assert.deepEqual(parseRawEDSFile(`Energy (keV),Counts\n${row}`, 'valid-delimited.txt').points.map(point => [point.energyKeV, point.counts]), [[0.25, 12]]);
  }
});
