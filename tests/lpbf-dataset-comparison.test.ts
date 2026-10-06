// Loader contract for docs/LPBF_DATASET_COMPARISON_2026-10-05.json (schema lpbf-dataset-comparison-1).
// The fixture is test data only; the app never imports it.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import {
  absorptivityMapeByValue,
  absorptivitySensitivityCells,
  checkedDatasetComparison,
} from '../src/data/lpbfDatasetComparison';
import { deletePath, setPath } from './support/jsonPath';

const fixture = (): unknown => JSON.parse(readFileSync('tests/fixtures/lpbf-dataset-comparison.sample.json', 'utf8'));
const real = (): unknown => JSON.parse(readFileSync('docs/LPBF_DATASET_COMPARISON_2026-10-05.json', 'utf8'));

test('loader accepts the schema-conformant fixture and the committed record', () => {
  const doc = checkedDatasetComparison(fixture());
  assert.equal(doc.schema, 'lpbf-dataset-comparison-1');
  assert.equal(doc.rows.length, 12);
  assert.equal(doc.datasets.length, 2);
  assert.deepEqual([...doc.kernels], ['rosenthal', 'eagar-tsai', 'goldak']);
  assert.equal(doc.honesty.experimentalValidation, false);
  assert.ok(doc.rows.some((r) => Object.values(r.predictions).some((p) => !p.included && p.extentStatus !== 'computed')));
  const committed = checkedDatasetComparison(real());
  assert.equal(committed.rows.length, committed.datasets.reduce((total, dataset) => total + dataset.rows, 0));
  assert.ok(Array.isArray(committed.datasets[0].notes));
});

test('absorptivity series is read as carried (array, or object keyed "0.3" or "0.30")', () => {
  const doc = checkedDatasetComparison(fixture());
  assert.deepEqual(absorptivityMapeByValue(doc, 'goldak'), [22.5, 13.3, 10.2, 13.8]);
  const keyed = fixture();
  setPath(keyed, ['absorptivitySensitivity', 'goldak'], { width_mape_pct_by_value: { '0.3': 1, '0.4': 2, '0.5': 3, '0.6': 4 } });
  assert.deepEqual(absorptivityMapeByValue(checkedDatasetComparison(keyed), 'goldak'), [1, 2, 3, 4]);
  const padded = fixture();
  setPath(padded, ['absorptivitySensitivity', 'goldak'], { width_mape_pct_by_value: { '0.30': 1, '0.40': 2, '0.50': 3, '0.60': 4 } });
  assert.deepEqual(absorptivityMapeByValue(checkedDatasetComparison(padded), 'goldak'), [1, 2, 3, 4]);
  assert.equal(absorptivityMapeByValue(doc, 'nope'), null);
});

test('real record: every sensitivity cell resolves (producer keys are "0.30", "0.40", ...)', () => {
  const doc = checkedDatasetComparison(real());
  for (const kernel of doc.kernels) {
    const cells = absorptivitySensitivityCells(doc, kernel);
    assert.ok(cells, kernel);
    assert.equal(cells.length, 4);
    for (const c of cells) {
      assert.notEqual(c.widthMape, null, `${kernel} ${c.value} width`);
      assert.notEqual(c.depthMape, null, `${kernel} ${c.value} depth`);
      assert.notEqual(c.nIncluded, null, `${kernel} ${c.value} n`);
    }
  }
  const rosenthal = absorptivitySensitivityCells(doc, 'rosenthal');
  assert.equal(rosenthal?.[0].widthMape, 49.8761);
  assert.equal(rosenthal?.[0].nIncluded, 15);
});

test('loader rejects a wrong schema, non-objects and missing required keys', () => {
  assert.throws(() => {
    const doc = fixture();
    setPath(doc, ['schema'], 'lpbf-dataset-comparison-2');
    checkedDatasetComparison(doc);
  }, /schema/);
  assert.throws(() => checkedDatasetComparison(null), /not an object/);
  assert.throws(() => checkedDatasetComparison([]), /not an object/);
  for (const key of ['honesty', 'rows', 'summary', 'datasets', 'kernels', 'absorptivitySensitivity', 'regimeFilter']) {
    const doc = fixture();
    deletePath(doc, [key]);
    assert.throws(() => checkedDatasetComparison(doc), new RegExp(`missing required key "${key}"`));
  }
});

test('loader rejects a missing honesty flag or experimentalValidation other than false', () => {
  const noFlag = fixture();
  deletePath(noFlag, ['honesty', 'experimentalValidation']);
  assert.throws(() => checkedDatasetComparison(noFlag), /experimentalValidation must be exactly false/);
  const validated = fixture();
  setPath(validated, ['honesty', 'experimentalValidation'], true);
  assert.throws(() => checkedDatasetComparison(validated), /experimentalValidation must be exactly false/);
  const noStatement = fixture();
  setPath(noStatement, ['honesty', 'statement'], '');
  assert.throws(() => checkedDatasetComparison(noStatement), /honesty\.statement/);
});

test('loader rejects rows that cannot be traced to a dataset or lack the included flag', () => {
  const orphan = fixture();
  setPath(orphan, ['rows', 0, 'dataset'], 'unknown-dataset');
  assert.throws(() => checkedDatasetComparison(orphan), /unknown dataset/);
  const noIncluded = fixture();
  deletePath(noIncluded, ['rows', 0, 'predictions', 'goldak', 'included']);
  assert.throws(() => checkedDatasetComparison(noIncluded), /included/);
});

const REJECT = /lpbf dataset comparison record rejected: /;

test('loader validates every field the view consumes, with a clear message', () => {
  const cases: ReadonlyArray<readonly [string, (doc: unknown) => void, RegExp]> = [
    ['regimeFilter.rule', (d) => setPath(d, ['regimeFilter', 'rule'], 7), /regimeFilter\.rule/],
    ['dataset doi', (d) => deletePath(d, ['datasets', 0, 'doi']), /datasets\[0\]\.doi/],
    ['dataset license', (d) => setPath(d, ['datasets', 1, 'license'], ''), /datasets\[1\]\.license/],
    ['dataset sha256', (d) => deletePath(d, ['datasets', 0, 'sha256']), /datasets\[0\]\.sha256/],
    ['dataset rows', (d) => setPath(d, ['datasets', 0, 'rows'], 'many'), /datasets\[0\]\.rows/],
    ['dataset notes string', (d) => setPath(d, ['datasets', 0, 'notes'], 'a string'), /datasets\[0\]\.notes is not an array of strings/],
    ['dataset notes entry', (d) => setPath(d, ['datasets', 0, 'notes'], ['ok', 3]), /datasets\[0\]\.notes/],
    ['row measured width', (d) => setPath(d, ['rows', 2, 'measured', 'width_um'], 'unknown'), /rows\[2\]\.measured\.width_um/],
    ['row measured depth', (d) => setPath(d, ['rows', 1, 'measured', 'depth_um'], Number.NaN), /rows\[1\]\.measured\.depth_um/],
    ['row missing kernel', (d) => deletePath(d, ['rows', 3, 'predictions', 'goldak']), /rows\[3\]\.predictions has no entry for declared kernel goldak/],
    ['row extentStatus', (d) => setPath(d, ['rows', 0, 'predictions', 'goldak', 'extentStatus'], 1), /extentStatus/],
    ['summary kernel missing', (d) => deletePath(d, ['summary', 'goldak']), /summary has no entry for declared kernel goldak/],
    ['summary n', (d) => setPath(d, ['summary', 'rosenthal', 'conduction', 'n'], '5'), /summary\.rosenthal\.conduction\.n/],
    ['summary stat non-finite', (d) => setPath(d, ['summary', 'rosenthal', 'conduction', 'width', 'mape_pct'], null), /summary\.rosenthal\.conduction\.width\.mape_pct/],
    ['summary fraction > 1', (d) => setPath(d, ['summary', 'rosenthal', 'conduction', 'depth', 'within30pct'], 55), /within30pct is not a fraction in \[0, 1\]/],
    ['summary width undefined', (d) => deletePath(d, ['summary', 'rosenthal', 'conduction', 'width']), /missing width or depth/],
    ['summary ci malformed', (d) => setPath(d, ['summary', 'rosenthal', 'conduction', 'width', 'mape_pct_ci95'], [1]), /mape_pct_ci95/],
    ['limits not strings', (d) => setPath(d, ['limits'], [1]), /limits/],
  ];
  for (const [name, mutate, message] of cases) {
    const doc = fixture();
    mutate(doc);
    assert.throws(() => checkedDatasetComparison(doc), message, name);
    assert.throws(() => checkedDatasetComparison(doc), REJECT, name);
  }
});

test('loader accepts a null width or depth slot', () => {
  const doc = fixture();
  setPath(doc, ['summary', 'rosenthal', 'conduction', 'width'], null);
  setPath(doc, ['summary', 'rosenthal', 'conduction', 'depth'], null);
  const checked = checkedDatasetComparison(doc);
  assert.equal(checked.summary.rosenthal.conduction.width, null);
});

test('loader accepts rows with unreported measured extents', () => {
  const doc = fixture();
  setPath(doc, ['rows', 0, 'measured', 'width_um'], null);
  setPath(doc, ['rows', 0, 'measured', 'depth_um'], null);
  const checked = checkedDatasetComparison(doc);
  assert.equal(checked.rows[0].measured.width_um, null);
  assert.equal(checked.rows[0].measured.depth_um, null);
});

test('loader accepts compact rows with a dataset-wide excluded prediction status', () => {
  const doc = fixture();
  deletePath(doc, ['rows', 0, 'predictions']);
  setPath(doc, ['rows', 0, 'predictionExclusion'], 'excluded: input unavailable');
  const checked = checkedDatasetComparison(doc);
  assert.equal(checked.rows[0].predictionExclusion, 'excluded: input unavailable');
});
