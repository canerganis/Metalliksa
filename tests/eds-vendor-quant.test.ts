import assert from 'node:assert/strict';
import test from 'node:test';
import {
  importVendorQuant,
  isElementSymbol,
  parseVendorQuantText,
  vendorQuantTransferLabel,
} from '../src/utils/edsVendorQuant';

const FIXED_NOW = new Date('2026-10-04T12:00:00.000Z');
const META = { instrument: 'Test SEM 9000', software: 'VendorQuant 3.1', analysisType: 'spot' as const };
const SHA = 'a'.repeat(64);

const GOOD_CSV = [
  'Element,wt%,sigma',
  'Fe,68.2,0.4',
  'Cr,17.1,0.2',
  'Ni,12.0,0.3',
  'Mo,2.5,0.1',
].join('\n');

test('E5: a table totalling 99.8 wt% is accepted with provenance and a transfer label', () => {
  const result = parseVendorQuantText(GOOD_CSV, 'spot1.csv', SHA, META, FIXED_NOW);
  assert.equal(result.accepted, true);
  assert.deepEqual(result.errors, []);
  assert.deepEqual(result.warnings, []);
  assert.deepEqual(result.composition, { Fe: 68.2, Cr: 17.1, Ni: 12, Mo: 2.5 });
  assert.equal(result.rows[0].sigmaWeightPct, 0.4);
  assert.deepEqual(result.provenance, {
    fileName: 'spot1.csv', sha256: SHA, instrument: 'Test SEM 9000', software: 'VendorQuant 3.1',
    analysisType: 'spot', importedAt: '2026-10-04T12:00:00.000Z',
  });
  assert.equal(result.transferLabel, 'Measured locally by VendorQuant 3.1 on Test SEM 9000 (spot), not bulk composition');
  assert.equal(result.transferLabel, vendorQuantTransferLabel(result.provenance!));
});

test('E5: a total outside 95-105 wt% warns but is still accepted', () => {
  const low = parseVendorQuantText('Fe,60\nCr,20', 'low.csv', SHA, META, FIXED_NOW);
  assert.equal(low.accepted, true);
  assert.equal(low.warnings.length, 1);
  assert.match(low.warnings[0], /80\.00 wt%/);
  assert.deepEqual(low.composition, { Fe: 60, Cr: 20 });

  const high = parseVendorQuantText('Fe,70\nCr,40', 'high.csv', SHA, META, FIXED_NOW);
  assert.equal(high.accepted, true);
  assert.equal(high.warnings.length, 1);

  for (const text of ['Fe,95\n', 'Fe,105\n', 'Fe,100\n']) {
    assert.deepEqual(parseVendorQuantText(text, 'edge.csv', SHA, META, FIXED_NOW).warnings, [], text);
  }
});

test('E5: negative, NaN, non-numeric, over-100 wt% and unknown elements are rejected with row numbers, never dropped', () => {
  const text = [
    '# comment line',
    'Element,wt%',
    'Fe,70',
    'Cr,-1.5',
    'Ni,NaN',
    'Mo,abc',
    'Xx,5',
    'Ti,Infinity',
    'W,150',
    'Cu,10,not-a-number',
  ].join('\n');
  const result = parseVendorQuantText(text, 'bad.csv', SHA, META, FIXED_NOW);
  assert.equal(result.accepted, false);
  assert.deepEqual(result.composition, {});
  assert.equal(result.provenance, undefined);
  assert.equal(result.transferLabel, undefined);
  assert.deepEqual(result.errors.map(error => error.row), [4, 5, 6, 7, 8, 9, 10]);
  assert.match(result.errors[0].message, /negative/);
  assert.match(result.errors[1].message, /not a finite number/);
  assert.match(result.errors[3].message, /Unknown element symbol 'Xx'/);
  assert.match(result.errors[5].message, /above 100/);
  assert.match(result.errors[6].message, /Uncertainty/);
});

test('E5: duplicate elements and missing metadata are rejected', () => {
  const duplicate = parseVendorQuantText('Fe,60\nFe,40', 'dup.csv', SHA, META, FIXED_NOW);
  assert.equal(duplicate.accepted, false);
  assert.equal(duplicate.errors[0].row, 2);
  assert.match(duplicate.errors[0].message, /Duplicate element Fe/);

  const noMeta = parseVendorQuantText(GOOD_CSV, 'x.csv', SHA, {}, FIXED_NOW);
  assert.equal(noMeta.accepted, false);
  assert.deepEqual(noMeta.errors.map(error => error.row), [0, 0, 0]);
  assert.match(noMeta.errors.map(error => error.message).join(' '), /Instrument.*software.*Analysis type/i);

  const empty = parseVendorQuantText('# nothing\n', 'empty.csv', SHA, META, FIXED_NOW);
  assert.equal(empty.accepted, false);
  assert.match(empty.errors[0].message, /no element/);
});

test('metadata can come from header rows; form fields override them', () => {
  const text = ['# instrument: Header SEM', '# software: Header Soft 1', '# analysis_type: area', 'Fe;99;0.5'].join('\n');
  const fromHeader = parseVendorQuantText(text, 'h.csv', SHA, {}, FIXED_NOW);
  assert.equal(fromHeader.accepted, true);
  assert.equal(fromHeader.provenance?.analysisType, 'area');
  assert.equal(fromHeader.transferLabel, 'Measured locally by Header Soft 1 on Header SEM (area), not bulk composition');

  const overridden = parseVendorQuantText(text, 'h.csv', SHA, { instrument: 'Form SEM', analysisType: 'spot' }, FIXED_NOW);
  assert.equal(overridden.provenance?.instrument, 'Form SEM');
  assert.equal(overridden.provenance?.software, 'Header Soft 1');
  assert.equal(overridden.provenance?.analysisType, 'spot');
});

test('tab / whitespace delimiters, percent signs and plus-minus sigma are accepted; symbol case is normalised', () => {
  const result = parseVendorQuantText('Element\twt%\t+/-\nFE\t68.2%\t±0.4\nni 31 0.5', 'tab.txt', SHA, META, FIXED_NOW);
  assert.equal(result.accepted, true, JSON.stringify(result.errors));
  assert.deepEqual(result.composition, { Fe: 68.2, Ni: 31 });
  assert.equal(result.rows[0].sigmaWeightPct, 0.4);
});

test('element symbol check covers the periodic table', () => {
  for (const symbol of ['H', 'Fe', 'Og', 'W', 'Re']) assert.equal(isElementSymbol(symbol), true, symbol);
  for (const symbol of ['', 'Xx', 'fe', 'FE', 'D']) assert.equal(isElementSymbol(symbol), false, symbol);
});

test('importVendorQuant hashes the exact bytes it parsed', async () => {
  const bytes = new TextEncoder().encode('Fe,100\n').buffer as ArrayBuffer;
  const result = await importVendorQuant(bytes, 'one.csv', META, FIXED_NOW);
  assert.equal(result.accepted, true);
  // sha256sum of the 7 bytes "Fe,100" + LF, computed outside this code base.
  assert.equal(result.provenance!.sha256, 'e70c87928f50a4b8544ef4745640411518d0f8442af157deb85f8bdd7e7e214f');
  assert.equal(result.provenance!.fileName, 'one.csv');
});
