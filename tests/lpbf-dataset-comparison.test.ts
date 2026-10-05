// Loader contract for docs/LPBF_DATASET_COMPARISON_2026-10-05.json (schema lpbf-dataset-comparison-1).
// The fixture is test data only; the app never imports it.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { absorptivityMapeByValue, checkedDatasetComparison } from '../src/data/lpbfDatasetComparison';

const fixture = (): Record<string, any> =>
  JSON.parse(readFileSync('tests/fixtures/lpbf-dataset-comparison.sample.json', 'utf8'));

test('loader accepts the schema-conformant fixture', () => {
  const doc = checkedDatasetComparison(fixture());
  assert.equal(doc.schema, 'lpbf-dataset-comparison-1');
  assert.equal(doc.rows.length, 12);
  assert.equal(doc.datasets.length, 2);
  assert.deepEqual([...doc.kernels], ['rosenthal', 'eagar-tsai', 'goldak']);
  assert.equal(doc.honesty.experimentalValidation, false);
  assert.ok(doc.rows.some((r) => Object.values(r.predictions).some((p) => !p.included && p.extentStatus !== 'computed')));
});

test('absorptivity series is read as carried (array or keyed object)', () => {
  const doc = checkedDatasetComparison(fixture());
  assert.deepEqual(absorptivityMapeByValue(doc, 'goldak'), [22.5, 13.3, 10.2, 13.8]);
  const keyed = fixture();
  keyed.absorptivitySensitivity.goldak = { width_mape_pct_by_value: { '0.3': 1, '0.4': 2, '0.5': 3, '0.6': 4 } };
  assert.deepEqual(absorptivityMapeByValue(checkedDatasetComparison(keyed), 'goldak'), [1, 2, 3, 4]);
  assert.equal(absorptivityMapeByValue(doc, 'nope'), null);
});

test('loader rejects a wrong schema, non-objects and missing required keys', () => {
  assert.throws(() => checkedDatasetComparison({ ...fixture(), schema: 'lpbf-dataset-comparison-2' }), /schema/);
  assert.throws(() => checkedDatasetComparison(null), /not an object/);
  assert.throws(() => checkedDatasetComparison([]), /not an object/);
  for (const key of ['honesty', 'rows', 'summary', 'datasets', 'kernels', 'absorptivitySensitivity', 'regimeFilter']) {
    const doc = fixture();
    delete doc[key];
    assert.throws(() => checkedDatasetComparison(doc), new RegExp(`missing required key "${key}"`));
  }
});

test('loader rejects a missing honesty flag or experimentalValidation other than false', () => {
  const noFlag = fixture();
  delete noFlag.honesty.experimentalValidation;
  assert.throws(() => checkedDatasetComparison(noFlag), /experimentalValidation must be exactly false/);
  const validated = fixture();
  validated.honesty.experimentalValidation = true;
  assert.throws(() => checkedDatasetComparison(validated), /experimentalValidation must be exactly false/);
  const noStatement = fixture();
  noStatement.honesty.statement = '';
  assert.throws(() => checkedDatasetComparison(noStatement), /honesty\.statement/);
});

test('loader rejects rows that cannot be traced to a dataset or lack the included flag', () => {
  const orphan = fixture();
  orphan.rows[0].dataset = 'unknown-dataset';
  assert.throws(() => checkedDatasetComparison(orphan), /unknown dataset/);
  const noIncluded = fixture();
  delete noIncluded.rows[0].predictions.goldak.included;
  assert.throws(() => checkedDatasetComparison(noIncluded), /included/);
});
