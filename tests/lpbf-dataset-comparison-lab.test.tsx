import React from 'react';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import { LpbfDatasetComparisonLab } from '../src/components/3d-distortion-lab/LpbfDatasetComparisonLab';
import { checkedDatasetComparison } from '../src/data/lpbfDatasetComparison';

const doc = checkedDatasetComparison(JSON.parse(readFileSync('tests/fixtures/lpbf-dataset-comparison.sample.json', 'utf8')));
const html = renderToStaticMarkup(<LpbfDatasetComparisonLab document={doc} />);

test('header carries the honesty statement verbatim and the provenance block', () => {
  assert.ok(html.includes(doc.honesty.statement));
  for (const d of doc.datasets) {
    assert.ok(html.includes(d.sha256));
    assert.ok(html.includes(d.license));
    assert.ok(html.includes(d.citation));
    assert.ok(html.includes(`href="https://doi.org/${d.doi}"`));
    assert.ok(html.includes(`Rows in dataset: ${d.rows}`));
  }
});

test('excluded rows are counted for the first kernel and drawn hollow', () => {
  const kernel = doc.kernels[0];
  const excluded = doc.rows.filter((r) => !r.predictions[kernel].included);
  assert.ok(excluded.length > 0);
  const statuses = Array.from(new Set(excluded.map((r) => r.predictions[kernel].extentStatus)));
  assert.ok(html.includes(`${excluded.length} excluded: extentStatus ${statuses.join(', ')}`));
  // Both scatters (width, depth) draw the hollow marker; rows with null depth are skipped, so check the width plot count.
  const hollow = (html.match(/data-point="excluded"/g) ?? []).length;
  assert.ok(hollow >= 1 && hollow <= 2 * excluded.length);
  assert.ok(html.includes('Excluded, extentStatus '));
});

test('summary tiles equal the fixture values and the sensitivity row is labelled', () => {
  const kernel = doc.kernels[0];
  for (const [regime, cell] of Object.entries(doc.summary[kernel])) {
    const tile = html.split(`data-summary="${kernel}/${regime}"`)[1]?.split('data-summary=')[0] ?? '';
    assert.ok(tile.length > 0, `tile ${regime}`);
    for (const stat of [cell.width, cell.depth]) {
      assert.ok(tile.includes(`${stat.bias_pct} %`));
      assert.ok(tile.includes(`${stat.mape_pct} %`));
      assert.ok(tile.includes(`${stat.rmse_um} µm`));
      assert.ok(tile.includes(`${Math.round(stat.within30pct * 1000) / 10} %`), `within30pct rendered as percent of the fraction ${stat.within30pct}`);
      assert.ok(stat.within30pct <= 1, 'fixture stores fractions like the real record');
    }
  }
  assert.ok(html.includes('sensitivity, not calibration'));
  assert.ok(html.includes('Sensitivity, not calibration'));
  assert.ok(html.includes('13.3'));
});

test('kernel selector and regime chips are present', () => {
  assert.match(html, /aria-label="Kernel"/);
  for (const k of ['Rosenthal', 'Eagar–Tsai v2', 'Goldak v3']) assert.ok(html.includes(k));
  assert.match(html, /aria-pressed="true"[^>]*>conduction</);
  assert.match(html, /aria-pressed="true"[^>]*>transition</);
});

test('the page never claims validation', () => {
  assert.doesNotMatch(html, /validated/i);
});

test('absent record renders the honest message and no scatter', () => {
  const empty = renderToStaticMarkup(<LpbfDatasetComparisonLab document={null} />);
  assert.match(empty, /No comparison record committed yet/);
  assert.doesNotMatch(empty, /<svg[^>]*role="img"/);
  assert.doesNotMatch(empty, /validated/i);
});
