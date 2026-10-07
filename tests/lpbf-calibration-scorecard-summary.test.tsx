import React from 'react';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import test from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import { LpbfCalibrationScorecardLab } from '../src/components/LpbfCalibrationScorecardLab';
import { checkedCalibrationScorecard, statusCounts, type LpbfCalibrationScorecardDocument } from '../src/data/lpbfCalibrationScorecard';
import { errorWord, summarizeScorecard, SUMMARY_LEGEND } from '../src/data/lpbfCalibrationScorecardSummary';

const VIEW = 'docs/LPBF_CALIBRATION_SCORECARD_2026-10-07.view.json';
const FIXTURE = 'tests/fixtures/lpbf-calibration-scorecard.sample.json';
const load = (path: string) => checkedCalibrationScorecard(JSON.parse(readFileSync(path, 'utf8')));
const clone = (d: LpbfCalibrationScorecardDocument) => JSON.parse(JSON.stringify(d));
const render = (d: LpbfCalibrationScorecardDocument | null) => renderToStaticMarkup(<LpbfCalibrationScorecardLab document={d} />);
const real = existsSync(VIEW) ? load(VIEW) : null;
const itemText = (d: LpbfCalibrationScorecardDocument, id: string) => summarizeScorecard(d).items.find((i) => i.id === id)?.text ?? '';

// Resolves a dotted/indexed source path such as "headline[1].headline.equalSourceWeight.mapeDefault" in the record.
function readField(doc: unknown, path: string): unknown {
  let cur: unknown = doc;
  for (const m of path.matchAll(/\["([^"]+)"\]|\[(\d+)\]|([^.[\]]+)/g)) cur = (cur as Record<string, unknown> | undefined)?.[m[1] ?? m[2] ?? m[3]];
  return cur;
}

test('every number in the summary text equals the record field it cites (1 dp)', { skip: real === null }, () => {
  const doc = real as LpbfCalibrationScorecardDocument;
  const summary = summarizeScorecard(doc);
  let checked = 0;
  for (const it of summary.items) {
    for (const n of it.numbers) {
      const path = n.source.split(' (')[0];
      if (path === 'headline[].status' || path === 'headline.length') {
        assert.equal(n.display, String(path === 'headline.length' ? doc.headline.length : statusCounts(doc).enabled));
      } else {
        const v = readField(doc, path);
        assert.equal(typeof v, 'number', `${it.id}: ${n.source}`);
        const shown = path.endsWith('.accuracy') ? `${((v as number) * 100).toFixed(1)} %` : path.includes('Factor') ? (v as number).toFixed(2) : path.endsWith('.n') ? String(v) : `${(v as number).toFixed(1)} %`;
        assert.equal(n.display, shown, `${it.id}: ${n.source}`);
      }
      assert.ok(it.text.includes(n.display));
      checked += 1;
    }
  }
  assert.ok(checked > 15, `only ${checked} numbers checked`);
});

test('best held-out accuracy is the lowest default MAPE per quantity (width Ti-6Al-4V 13.6, depth Ti-6Al-4V 32.6)', { skip: real === null }, () => {
  const doc = real as LpbfCalibrationScorecardDocument;
  // Task text expected 316L 13.7 for width, but the record has Ti-6Al-4V 13.5609 < 316L 13.7193: the rule (lowest) wins.
  assert.match(itemText(doc, 'best-width'), /Eagar-Tsai, Ti-6Al-4V, 13\.6 %/);
  assert.equal(doc.headline[0].headline!.equalSourceWeight.mapeDefault!.toFixed(1), '13.7');
  assert.ok(doc.headline[2].headline!.equalSourceWeight.mapeDefault! < doc.headline[0].headline!.equalSourceWeight.mapeDefault!);
  assert.match(itemText(doc, 'best-depth'), /Eagar-Tsai, Ti-6Al-4V, 32\.6 %/);
  assert.match(itemText(doc, 'best-width'), /\(lower error\)/);
  assert.match(itemText(doc, 'best-depth'), /\(moderate\)/);
});

test('failure items: depth range, Rosenthal ranges, N01 default-rung factors per kernel, regime accuracy range with n', { skip: real === null }, () => {
  const doc = real as LpbfCalibrationScorecardDocument;
  assert.match(itemText(doc, 'fail-depth'), /32\.6 % \(moderate\) to 55\.2 % \(high\)/);
  assert.match(itemText(doc, 'fail-rosenthal-width'), /41\.9 % \(high\) to 44\.6 % \(high\)/);
  assert.match(itemText(doc, 'fail-rosenthal-depth'), /51\.6 % \(high\) to 55\.2 % \(high\)/);
  for (const [i, n] of doc.n01.entries()) {
    const text = itemText(doc, `fail-n01-${n.kernel}`);
    assert.ok(text.includes(`width x${n.rungs.default.widthFactor!.toFixed(2)}`), `n01[${i}]`);
    assert.ok(text.includes(`depth x${n.rungs.default.depthFactor!.toFixed(2)}`));
  }
  assert.match(itemText(doc, 'fail-regime'), /28\.6 % .*n = 14\).* to 84\.1 % .*n = 44\)/);
});

test('alloys with only no-data rows are listed as not covered; notes are carried', { skip: real === null }, () => {
  const doc = real as LpbfCalibrationScorecardDocument;
  const text = itemText(doc, 'not-covered');
  assert.ok(text.includes('Inconel 718') && text.includes('AlSi10Mg'));
  assert.ok(!text.includes('Inconel 625'), 'a rejected alloy with a source is not "no data"');
  assert.deepEqual(summarizeScorecard(doc).notes, doc.notes);
});

test('enabled = 0 gives the no-calibrated-mode sentence; an enabled cell reports the served value', { skip: real === null }, () => {
  const doc = real as LpbfCalibrationScorecardDocument;
  assert.equal(statusCounts(doc).enabled, 0);
  assert.equal(itemText(doc, 'calibration'), '0 of 30 cells passed the gate, so calibrated mode is not offered; all results are unchanged screening output');
  assert.doesNotMatch(itemText(doc, 'best-width'), /served by enabled cell/);

  const on = clone(doc);
  on.headline[2].status = 'enabled'; // eagar-tsai Ti-6Al-4V width: default 13.6, served 14.7 in the record
  const withEnabled = checkedCalibrationScorecard(on);
  assert.match(itemText(withEnabled, 'calibration'), /^1 of 30 cells passed the gate; calibrated mode is offered only for those cells/);
  assert.match(itemText(withEnabled, 'best-width'), /served by enabled cell Eagar-Tsai, Ti-6Al-4V: 14\.7 %/);
});

test('all-null headlines give "no held-out errors available" and no fabricated ranges', () => {
  const doc = clone(load(FIXTURE));
  for (const r of doc.headline) r.headline = null;
  const summary = summarizeScorecard(checkedCalibrationScorecard(doc));
  const ids = summary.items.map((i) => i.id);
  assert.match(summary.items.find((i) => i.id === 'best-width')!.text, /no held-out errors available/);
  assert.match(summary.items.find((i) => i.id === 'best-depth')!.text, /no held-out errors available/);
  assert.ok(!ids.includes('fail-depth') && !ids.includes('fail-rosenthal-width'));
});

test('markup: summary precedes the gate-outcome table, legend and Detailed tables heading present, N01 card visible', { skip: real === null }, () => {
  const html = render(real);
  const summaryAt = html.indexOf('data-testid="plain-summary"');
  assert.ok(summaryAt > 0);
  assert.ok(html.indexOf('In plain language') < html.indexOf('Gate outcome'));
  assert.ok(summaryAt < html.indexOf('data-testid="headline-table"'));
  assert.ok(html.indexOf('data-testid="n01-card"') < html.indexOf('Detailed tables'));
  assert.ok(html.includes('data-testid="summary-legend"'));
  assert.ok(html.includes(SUMMARY_LEGEND.replace('<', '&lt;').replace('>', '&gt;')));
  assert.match(html, /<h2[^>]*id="detailed-tables"[^>]*>Detailed tables<\/h2>/);
  assert.match(html, /<button type="button"[^>]*>Jump to details<\/button>/);
  assert.ok(!html.includes('href="#detailed-tables"'), 'hash links would leave the module: the app routes on the hash');
  assert.ok(html.indexOf('Detailed tables') < html.indexOf('Gate outcome'));
  assert.ok(html.includes('<strong data-source="headline[2].headline.equalSourceWeight.mapeDefault"'));
  assert.doesNotMatch(html.replace(/not validation|not experimental validation|no validation|not a validation criterion/gi, ''), /\bvalidated\b/i);
});

test('smoke record keeps its marker; null record keeps the empty state without a summary', () => {
  const smoke = clone(load(FIXTURE));
  smoke.quick = true;
  assert.ok(render(checkedCalibrationScorecard(smoke)).includes('SMOKE RUN: not a record'));
  const none = render(null);
  assert.ok(none.includes('data-testid="no-scorecard-record"'));
  assert.ok(!none.includes('plain-summary') && !none.includes('In plain language'));
});

test('error words use the stated bands', () => {
  assert.equal(errorWord(19.9), 'lower error');
  assert.equal(errorWord(20), 'moderate');
  assert.equal(errorWord(35), 'moderate');
  assert.equal(errorWord(35.1), 'high');
});
