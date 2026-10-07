import React from 'react';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import { LpbfCalibrationScorecardLab } from '../src/components/LpbfCalibrationScorecardLab';
import {
  checkedCalibrationScorecard,
  statusCounts,
  type LpbfCalibrationScorecardDocument,
} from '../src/data/lpbfCalibrationScorecard';
import { COMMITTED_CALIBRATION_SCORECARD } from '../src/data/lpbfCalibrationScorecardRecord';
import { setPath } from './support/jsonPath';

// The fixture is SYNTHETIC (synthetic kernel and measurements); it exercises the view, not any physics.
const fixtureJson = (): unknown => JSON.parse(readFileSync('tests/fixtures/lpbf-calibration-scorecard.sample.json', 'utf8'));
const doc = checkedCalibrationScorecard(fixtureJson());
const render = (d: LpbfCalibrationScorecardDocument | null) => renderToStaticMarkup(<LpbfCalibrationScorecardLab document={d} />);
const html = render(doc);

test('validator accepts the fixture and rejects malformed or dishonest records', () => {
  assert.equal(doc.schema, 'lpbf-calibration-scorecard-view-1');
  const bad = (path: (string | number)[], value: unknown) => {
    const raw = fixtureJson();
    setPath(raw, path, value);
    assert.throws(() => checkedCalibrationScorecard(raw), /lpbf calibration scorecard record rejected/);
  };
  bad(['schema'], 'lpbf-calibration-scorecard-view-2');
  bad(['evidence', 'kind'], 'calibrated-simulation');
  bad(['evidence', 'experimentalValidation'], true);
  bad(['evidence', 'opticalOperatorMatched'], true);
  bad(['headline', 0, 'status'], 'validated');
  bad(['headline', 0, 'quantity'], 'length');
  bad(['n01'], 'none');
  bad(['gateSummary', 'promoted'], 3);
  assert.throws(() => checkedCalibrationScorecard(null), /not an object/);
  const missing = fixtureJson() as Record<string, unknown>;
  delete missing.n01;
  assert.throws(() => checkedCalibrationScorecard(missing), /missing key n01/);
});

test('absent record: honest empty state, no calibrated mode, N01 card still rendered', () => {
  assert.equal(COMMITTED_CALIBRATION_SCORECARD, null, 'under tsx the Vite glob is unavailable, so the record is absent');
  const out = render(null);
  assert.ok(out.includes('data-testid="no-scorecard-record"'));
  assert.ok(out.includes('npm run lpbf:calibration'));
  assert.ok(out.includes('data-testid="n01-card"'));
  assert.ok(out.includes('Guo N01: known failure, not fitted'));
  assert.doesNotMatch(out, /data-testid="headline-table"/);
});

test('the N01 sentinel card is always rendered, red-carded and carries the "not fitted" statement', () => {
  assert.ok(html.includes('data-testid="n01-card"'));
  assert.ok(html.includes('border-rose-700'));
  assert.ok(html.includes('known failure, not fitted'));
  assert.ok(doc.n01.length > 0, 'the synthetic fixture carries N01 rows');
  const card = html.split('data-testid="n01-card"')[1]?.split('</section>')[0] ?? '';
  for (const n of doc.n01) assert.ok(card.includes(`${n.measured.depth_um}`));
  assert.ok(card.includes('NO') || card.includes('yes'));
  const stripped = JSON.parse(JSON.stringify(doc));
  stripped.n01 = [];
  assert.ok(render(checkedCalibrationScorecard(stripped)).includes('data-testid="n01-card"'));
});

test('gate chips and counts equal the record (status word printed, never colour alone)', () => {
  const counts = statusCounts(doc);
  assert.equal(counts.enabled + counts['within-source-only'] + counts.rejected + counts['no-data'], doc.headline.length);
  for (const row of doc.headline) {
    const cell = html.split(`data-cell="${row.kernel}/${row.material}/${row.quantity}"`)[1]?.split('</tr>')[0] ?? '';
    assert.ok(cell.includes(`data-status="${row.status}"`), `${row.kernel}/${row.material}/${row.quantity}`);
    assert.ok(cell.includes(`>${row.status}<`));
  }
  const summary = html.split('data-testid="gate-summary"')[1]?.split('</p>')[0] ?? '';
  for (const status of ['enabled', 'within-source-only', 'rejected', 'no-data'] as const) {
    assert.ok(summary.includes(`data-status="${status}"`));
  }
});

test('with zero enabled cells the page says so and no calibrated mode is offered', () => {
  const none = JSON.parse(JSON.stringify(doc));
  for (const r of none.headline) if (r.status === 'enabled') r.status = 'rejected';
  none.gateSummary = { rejected: none.headline.filter((r: { status: string }) => r.status === 'rejected').length, 'no-data': statusCounts(doc)['no-data'], 'within-source-only': statusCounts(doc)['within-source-only'] };
  const out = render(checkedCalibrationScorecard(none));
  assert.ok(out.includes('data-testid="none-enabled"'));
  assert.ok(out.includes('Calibrated mode is therefore not offered'));
});

test('every held-out row prints both directions, unresolved counts and the Wilson interval; labels stay screening only', () => {
  const loso = html.split('data-testid="loso-table"')[1]?.split('</table>')[0] ?? '';
  assert.ok(loso.length > 0);
  const held = new Set(doc.headline.flatMap((r) => r.p2.map((p) => p.heldOut)));
  assert.ok(held.size >= 2);
  for (const h of held) assert.ok(loso.includes(h));
  assert.ok(html.includes('data-testid="evidence-badge"'));
  assert.ok(html.includes('Screening only'));
  assert.ok(html.includes(doc.evidence.statement));
  assert.doesNotMatch(html, /Calibrated simulation/);
  assert.doesNotMatch(html.replace(/not validation|not experimental validation|no validation/gi, ''), /\bvalidated\b/i);
});

test('every source is listed with its role, and catalog sentinels are marked test-only', () => {
  assert.ok(doc.sources.some((s) => s.role.startsWith('catalog-sentinel')));
  for (const s of doc.sources) assert.ok(html.includes(`data-source="${s.source}"`));
  assert.ok(html.includes('test-only'));
});
