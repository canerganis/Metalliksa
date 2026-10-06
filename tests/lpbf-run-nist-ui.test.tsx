import React from 'react';
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import { NistOpticalComparison, NistOpticalResult } from '../src/components/LpbfRunArchivePanel';
import type { NistOpticalReport, RunRecord } from '../src/types/lpbfRun';

const link = { datasetId: 'nist-amb2022-03-optical-table4-local-v1',
  revision: 2, documentSha256: 'a'.repeat(64) };
const record: RunRecord = { document: { schemaVersion: 1, runId: 'b'.repeat(32),
  capture: { schemaVersion: 1, jobId: 'b'.repeat(32), resultJson: '{}', inputJson: '{}',
    materialJson: '{}', contractStatus: 'core-v1-bound', runKind: 'analytical-screening' }, sources: [link] },
  documentSha256: 'c'.repeat(64), createdAt: '2026-09-23T00:00:00Z',
  evidenceStatus: 'unvalidated-model', sourceBindingStatus: 'exact-revision-bound', runKind: 'analytical-screening' };
const unavailable: NistOpticalReport = { schemaVersion: 1, benchmark: 'AMB2022-03-TMPG',
  caseNumber: '0', status: 'unavailable', validationStatus: 'unvalidated',
  reference: { doi: '10.18434/mds2-2718', results: '', resultsLocator: '', methods: '',
    measurement: '', archiveKind: '' }, sourceBinding: null,
  reasons: ['Measured beam profile unavailable.'], errors: null };

test('NIST run controls expose seven keyboard-selectable cases and exact archived binding', () => {
  const html = renderToStaticMarkup(<NistOpticalComparison record={record} />);
  assert.match(html, /aria-label="NIST Table 4 case"/);
  assert.equal((html.match(/<option/g) ?? []).length, 7);
  assert.match(html, /Compare archived run/);
  assert.match(html, /Run kind: analytical-screening/);
  assert.match(html, /revision 2/);
  assert.match(html, new RegExp(link.documentSha256));
  assert.match(html, /unvalidated/);
});

test('unavailable optical comparison renders reasons without error numbers', () => {
  const html = renderToStaticMarkup(<NistOpticalResult report={unavailable} />);
  assert.match(html, /Comparison unavailable/);
  assert.match(html, /Measured beam profile unavailable/);
  assert.doesNotMatch(html, /signed error|absolute error|published SD|µm/);
});

test('comparable optical screening shows signed errors and published SD as unvalidated', () => {
  const report: NistOpticalReport = { ...unavailable, status: 'comparable-screening', reasons: [],
    sourceBinding: { ...link, sourceDatasetId: 'nist-mds2-2718',
      artifactSha256: 'd1b36dfa2e01a3537093c481e249ce52df6b8879c1c67480ddb9aa10799133da' },
    errors: { width: { signed_um: -2, absolute_um: 2, measuredMean_um: 100,
      publishedStdDev_um: 4, model_um: 98 },
      depth: { signed_um: 3, absolute_um: 3, measuredMean_um: 120,
        publishedStdDev_um: 5, model_um: 123 } } };
  const html = renderToStaticMarkup(<NistOpticalResult report={report} />);
  assert.match(html, /Comparable screening result.*unvalidated/);
  assert.match(html, /signed error -2.00 µm/);
  assert.match(html, /published SD 4.00 µm/);
});
