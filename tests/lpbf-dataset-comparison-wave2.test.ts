// Loader contract for the 2026-10-06 comparison record (wave 2 open datasets). The UI still reads the
// 2026-10-05 view record (src/data/lpbfDatasetComparisonRecord.ts hardcodes that path); this test only checks
// that the new record is schema-compatible, honest and self-consistent. It is not wired into the view.
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { test } from 'node:test';
import { checkedDatasetComparison } from '../src/data/lpbfDatasetComparison';

const RECORD = 'docs/LPBF_DATASET_COMPARISON_2026-10-06.json';
const VIEW = 'docs/LPBF_DATASET_COMPARISON_2026-10-06.view.json';
const missing = !existsSync(RECORD) || !existsSync(VIEW);
const skip = missing ? `${RECORD} or its view record is not present in this checkout` : false;

test('2026-10-06 record and view pass the loader and keep validation flags false', { skip }, () => {
  const raw = JSON.parse(readFileSync(RECORD, 'utf8'));
  const doc = checkedDatasetComparison(raw);
  assert.equal(doc.generatedAt, '2026-10-06');
  assert.equal(doc.honesty.experimentalValidation, false);
  assert.equal(raw.wave2.evidence.experimentalValidation, false);
  assert.equal(raw.wave2.evidence.opticalOperatorMatched, false);
  assert.equal(doc.rows.length, doc.datasets.reduce((total, dataset) => total + dataset.rows, 0));
  for (const id of ['ku-leuven-316l-2021', 'ku-leuven-ti64-2021', 'lane-in625-2020']) {
    assert.ok(doc.datasets.some((d) => d.id === id), id);
  }
  for (const target of raw.wave2.referenceTargets) {
    assert.equal(target.comparison.status, 'unavailable');
    assert.ok(target.comparison.reason.length > 80);
  }
  const view = checkedDatasetComparison(JSON.parse(readFileSync(VIEW, 'utf8')));
  assert.equal(view.generatedAt, '2026-10-06');
});
