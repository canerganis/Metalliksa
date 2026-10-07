import React from 'react';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import { LpbfKeyholeBenchmarkPanel } from '../src/components/LpbfKeyholeBenchmarkPanel';
import { checkedLpbfKeyholeBenchmark } from '../src/data/lpbfKeyholeBenchmark';

const source = JSON.parse(readFileSync('docs/LPBF_KEYHOLE_BENCHMARK_2026-10-07.view.json', 'utf8'));
const benchmark = checkedLpbfKeyholeBenchmark(source);
const render = (document: typeof benchmark | null) => renderToStaticMarkup(<LpbfKeyholeBenchmarkPanel document={document} />);

test('renders sources, matrix, depth, porosity, threshold and honesty from the view record', () => {
  const html = render(benchmark);
  for (const text of ['Cunningham et al. (2019)', 'Zhao et al. (2020)', '10.1126/science.aav4687', '0.652', '0.634']) {
    assert.ok(html.includes(text), text);
  }
  assert.ok(html.includes('Rows ingested (all sources)'));
  assert.ok(html.includes('<strong>149</strong>'));
  assert.doesNotMatch(html, /digitized rows/i);
  assert.ok(html.includes('depth MAPE (%)'));
  for (const v of ['44.8', '79.4', '63.8', '30.5']) assert.ok(html.includes(v), v);
  assert.ok(html.includes('19/35'));
  assert.ok(html.includes('min 15.000 / median 24.942 / max 62.424 (n = 20)'));
  assert.ok(html.includes('min 17.293 / median 17.662 / max 20.005 (n = 9)'));
  assert.ok(html.includes('<strong>30.0</strong>'));
  assert.ok(html.includes('not experimental validation'));
  assert.ok(html.includes('A planned physics update is proposed; see the evidence note'));
  assert.ok(html.includes('docs/LPBF_KEYHOLE_THRESHOLD_EVIDENCE_2026-10-07.md'));
  assert.doesNotMatch(html, /King/);
  assert.match(html, /<caption/);
  assert.match(html, /scope="col"/);
  assert.match(html, /scope="row"/);
});

test('missing fields render as not reported without NaN, undefined or a crash', () => {
  const bad = /NaN|undefined|null|planned physics update/;
  const bare = render(checkedLpbfKeyholeBenchmark({ schema: source.schema }));
  assert.ok(bare.includes('not reported'));
  assert.doesNotMatch(bare, bad);
  const partial = render(checkedLpbfKeyholeBenchmark({
    ...source,
    depth: { cunningham95: 1 },
    porosity: {},
    keyholeThreshold: {},
    physicsBumpProposed: false,
    regimeConfusion: { ...source.regimeConfusion, accuracy: undefined },
  }));
  assert.ok(partial.includes('not reported'));
  assert.doesNotMatch(partial, bad);
  assert.ok(render(null).includes('not reported'));
});
