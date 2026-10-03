import React from 'react';
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import { NistProxyCampaign } from '../src/components/LpbfRunArchivePanel';
import type { RunArchiveList } from '../src/services/lpbfRunArchiveClient';

const runs: RunArchiveList = ['a', 'b', 'c'].map((letter, index) => ({
  runId: letter.repeat(32), createdAt: `2026-09-2${index + 3}T00:00:00.000Z`, evidenceStatus: 'unvalidated-model',
  sourceBindingStatus: 'exact-revision-bound', runKind: 'transient-thermal',
}));

test('proxy campaign UI collects exactly three archived runs and a case without measurement fields', () => {
  const html = renderToStaticMarkup(<NistProxyCampaign runs={runs} />);
  assert.match(html, /six-section thermal proxy campaign/);
  assert.match(html, /Proxy screening only/);
  assert.match(html, /unvalidated/);
  assert.match(html, /published nominal diameter adopted as a declared Gaussian model input/i);
  assert.match(html, /aria-label="Archived thermal run 1"/);
  assert.match(html, /aria-label="Archived thermal run 2"/);
  assert.match(html, /aria-label="Archived thermal run 3"/);
  assert.match(html, /aria-label="NIST proxy campaign case"/);
  assert.match(html, /Preview proxy campaign/);
  assert.match(html, /Archive proxy campaign/);
  assert.doesNotMatch(html, /<input|Measured mean|Signed error|published SD/);
});

test('proxy campaign UI requests three archived transient runs before enabling its flow', () => {
  const html = renderToStaticMarkup(<NistProxyCampaign runs={runs.slice(0, 2)} />);
  assert.match(html, /Three archived transient-thermal runs are required/);
  assert.doesNotMatch(html, /Preview proxy campaign|Archive proxy campaign|Archived thermal run 1/);
});
