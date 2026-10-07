/* eslint-disable @typescript-eslint/no-explicit-any */
import React from 'react';
import assert from 'node:assert/strict';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import test from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import { LpbfCalibrationScorecardLab } from '../src/components/LpbfCalibrationScorecardLab';
import { LpbfLeaderboardPanel } from '../src/components/LpbfLeaderboardPanel';
import {
  checkedLeaderboard, groupRows, nextSort, sortRows, SORT_KEYS,
  type LeaderboardCell, type LeaderboardEntry, type LpbfLeaderboardDocument,
} from '../src/data/lpbfLeaderboard';

// Self-contained fixture: no committed record is required. One built-in kernel (the baseline) and one local
// submission that declares it trained on a source, so one excluded row is rendered.
const SHA_B = 'a'.repeat(64);
const SHA_S = 'b'.repeat(64);
const cell = (source: string, extra: Partial<LeaderboardCell>, quantity: 'width' | 'depth' = 'width'): LeaderboardCell => ({
  material: '316L Stainless Steel', quantity, heldOutSource: source, status: 'scored', nRows: 40, nSets: 12, nResolved: 40,
  unresolved: 0, mapePct: 20, meanAbsLn: 0.18, mapeUnresolvedAsFailPct: 20, skill: 0, skillCi95: [0, 0], coverage90: null, ...extra,
});
const prov = { manifestSha256: 'c'.repeat(64), implementationHash: 'd'.repeat(64), baselineKernel: 'rosenthal' };
const builtin: LeaderboardEntry = {
  id: 'builtin:rosenthal', kind: 'built-in-kernel', name: 'Rosenthal screening kernel', version: 'frozen-default-eta',
  author: 'Metalliksa frozen screening kernels', description: 'frozen kernel', url: '', trainedOnSources: [],
  provenance: { ...prov, kernel: 'rosenthal', predictionsSha256: SHA_B },
  cells: [cell('hofmann-316l-2026', { mapePct: 13.8 }), cell('ku-leuven-316l-2021', { mapePct: 11.4, nRows: 44 })],
  sentinels: [cell('guo-316l-2024', { mapePct: 43, nRows: 4 })],
};
const submission: LeaderboardEntry = {
  id: 'submission:my-model-1-0', kind: 'local-submission', name: 'My model', version: '1.0', author: 'A. Tester',
  description: 'fixture', url: 'example.org/my-model', trainedOnSources: ['ku-leuven-316l-2021'],
  provenance: { ...prov, submissionCsvSha256: SHA_S, metaSha256: 'e'.repeat(64) },
  cells: [
    cell('hofmann-316l-2026', { mapePct: 9.5, skill: 0.31, skillCi95: [0.2, 0.4], unresolved: 3, coverage90: { k: 30, n: 40, coverage: 0.75, wilson95: [0.6, 0.86] } }),
    { material: '316L Stainless Steel', quantity: 'width', heldOutSource: 'ku-leuven-316l-2021', status: 'excluded-trained-on', nRows: 44, nSets: 44, reason: 'trained on this source' },
  ],
  sentinels: [cell('guo-316l-2024', { mapePct: 30, nRows: 4 })],
};
const FIXTURE: LpbfLeaderboardDocument = {
  schema: 'lpbf-leaderboard-1', generatedAt: '2026-10-07', implementationHash: 'd'.repeat(64), configSha256: 'f'.repeat(64),
  manifestSha256: 'c'.repeat(64),
  evidence: { kind: 'screening-only', statement: 'Screening benchmark: not validation', experimentalValidation: false, labelPromotionProposed: 'none' },
  honesty: 'screening benchmark; scores are never combined into one cross-material rank',
  calibratedRung: { enabledCells: 0, note: 'No calibration cell is enabled by the gate, so no calibrated entry exists' },
  entries: [builtin, submission],
};
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const render = (d: LpbfLeaderboardDocument | null, props: Partial<React.ComponentProps<typeof LpbfLeaderboardPanel>> = {}) =>
  renderToStaticMarkup(<LpbfLeaderboardPanel document={d} {...props} />);
const mainBlock = (html: string) => html.split('<details')[0];
const rowOrder = (html: string) => [...mainBlock(html).matchAll(/<tr data-testid="leaderboard-(?:row|excluded)"[\s\S]*?<div class="font-medium text-slate-900">([^<]+)<\/div>/g)].map((m) => m[1]);

test('absent record shows an honest empty state, no table and no entries', () => {
  const html = render(null);
  assert.match(html, /data-testid="no-leaderboard-record"/);
  assert.match(html, /No leaderboard record committed yet/);
  assert.match(html, /Screening benchmark/);
  assert.doesNotMatch(html, /<table/);
  assert.doesNotMatch(html, /leaderboard-row/);
});

test('fixture with one built-in and one submission renders per-material tables with provenance and a Screening label', () => {
  const html = render(FIXTURE);
  assert.match(html, /Screening benchmark/);
  assert.match(html, /not validation/);
  assert.match(html, /built-in kernel/);
  assert.match(html, /local submission/);
  assert.match(html, new RegExp(`<code title="${SHA_B}">${'a'.repeat(12)}</code>`));
  assert.match(html, new RegExp(`<code title="${SHA_S}">${'b'.repeat(12)}</code>`));
  assert.match(html, /URL \(text only\): <span>example\.org\/my-model<\/span>/);
  assert.doesNotMatch(html, /<a [^>]*example\.org/);
  assert.match(html, /316L Stainless Steel, melt-pool width/);
  assert.match(html, /0\.31 \[0\.20, 0\.40\]/);
  assert.match(html, /0\.75 \(30\/40\) \[0\.60, 0\.86\]/);
  assert.match(html, /n\/a \(no intervals given\)/);
  assert.match(html, /this entry is the baseline/);
  assert.equal([...mainBlock(html).matchAll(/data-testid="leaderboard-row"/g)].length, 3, 'two built-in rows and one scored submission row');
  assert.equal([...mainBlock(html).matchAll(/data-testid="leaderboard-excluded"/g)].length, 1);
  assert.match(html, /Excluded: the submission declares it trained on this source/);
  // sentinels are a separate, labelled block
  assert.match(html, /Catalog sentinels \(used during physics development, not blind\)/);
  assert.match(html, /data-testid="leaderboard-sentinel-group"/);
  // never one cross-material rank, no demo entry
  assert.doesNotMatch(html, /overall rank|global rank|demo|fake/i);
  assert.equal([...html.matchAll(/data-testid="leaderboard-group"/g)].length, 1);
});

test('column headers are keyboard-operable buttons with aria-sort', () => {
  const html = render(FIXTURE);
  const group = html.split('data-testid="leaderboard-group"')[1].split('</thead>')[0];
  const buttons = [...group.matchAll(/<button type="button" data-sort-key="([a-zA-Z]+)"/g)].map((m) => m[1]);
  assert.deepEqual(buttons, [...SORT_KEYS]);
  assert.match(group, /<th scope="col" aria-sort="ascending"[^>]*><button type="button" data-sort-key="mapePct"/);
  assert.equal([...group.matchAll(/aria-sort="none"/g)].length, SORT_KEYS.length - 1);
  assert.match(group, /focus-visible:ring-2/);
});

test('sorting: header press toggles direction, excluded and missing values stay last, order follows initialSort', () => {
  const rows = groupRows(FIXTURE)[0].rows;
  const state = nextSort({ key: 'mapePct', dir: 'asc' }, 'skill');
  assert.deepEqual(state, { key: 'skill', dir: 'asc' });
  assert.deepEqual(nextSort(state, 'skill'), { key: 'skill', dir: 'desc' });
  const asc = sortRows(rows, { key: 'mapePct', dir: 'asc' }).map((r) => `${r.entryName}|${r.cell.heldOutSource}`);
  assert.deepEqual(asc, [
    'My model|hofmann-316l-2026', 'Rosenthal screening kernel|ku-leuven-316l-2021', 'Rosenthal screening kernel|hofmann-316l-2026',
    'My model|ku-leuven-316l-2021',
  ]);
  const desc = sortRows(rows, { key: 'mapePct', dir: 'desc' }).map((r) => r.entryName);
  assert.equal(desc.at(-1), 'My model', 'the excluded row is last in both directions');
  assert.equal(sortRows(rows, { key: 'mapePct', dir: 'desc' }).at(-1)?.cell.status, 'excluded-trained-on');
  assert.deepEqual(rowOrder(render(FIXTURE, { initialSort: { key: 'mapePct', dir: 'asc' } })),
    ['My model', 'Rosenthal screening kernel', 'Rosenthal screening kernel', 'My model']);
  assert.deepEqual(rowOrder(render(FIXTURE, { initialSort: { key: 'entry', dir: 'desc' } })),
    ['Rosenthal screening kernel', 'Rosenthal screening kernel', 'My model', 'My model']);
  assert.match(render(FIXTURE, { initialSort: { key: 'unresolved', dir: 'desc' } }), /aria-sort="descending"[^>]*><button type="button" data-sort-key="unresolved"/);
  // a missing value sorts after present values in both directions
  const withNull = clone(rows);
  (withNull[0] as { cell: LeaderboardCell }).cell = { ...withNull[0].cell, skill: null, skillCi95: null };
  for (const dir of ['asc', 'desc'] as const) {
    assert.equal(sortRows(withNull, { key: 'skill', dir }).filter((r) => r.cell.status === 'scored').at(-1)?.cell.skill, null);
  }
});

test('record validation rejects dishonest or malformed documents', () => {
  assert.doesNotThrow(() => checkedLeaderboard(clone(FIXTURE)));
  const bad = (mut: (d: Record<string, any>) => void) => { const d = clone(FIXTURE); mut(d); return () => checkedLeaderboard(d); };
  assert.throws(bad((d) => { d.evidence.kind = 'validated'; }), /screening-only/);
  assert.throws(bad((d) => { d.evidence.experimentalValidation = true; }), /experimentalValidation/);
  assert.throws(bad((d) => { d.schema = 'x'; }), /schema/);
  assert.throws(bad((d) => { d.entries[1].id = d.entries[0].id; }), /duplicate/);
  assert.throws(bad((d) => { d.entries[0].kind = 'official'; }), /kind/);
  assert.throws(bad((d) => { d.entries[0].cells[0].mapePct = Number.NaN; }), /finite/);
  assert.throws(bad((d) => { d.entries[0].cells[0].status = 'passed'; }), /status/);
});

test('the scorecard lab mounts the leaderboard as one section at its end (absent record)', () => {
  const html = renderToStaticMarkup(<LpbfCalibrationScorecardLab document={null} />);
  assert.equal([...html.matchAll(/data-testid="leaderboard"/g)].length, 1);
  assert.ok(html.lastIndexOf('data-testid="leaderboard"') > html.indexOf('data-testid="no-scorecard-record"'));
});

test('a committed leaderboard record, when present, is valid, screening-only and has no calibrated entry while none is enabled', () => {
  const files = readdirSync('docs').filter((f) => /^LPBF_LEADERBOARD_.*\.json$/.test(f)).sort();
  if (files.length === 0) return;
  const path = `docs/${files.at(-1)}`;
  assert.ok(existsSync(path));
  const doc = checkedLeaderboard(JSON.parse(readFileSync(path, 'utf8')));
  assert.equal(doc.evidence.kind, 'screening-only');
  assert.equal(doc.calibratedRung.enabledCells, 0);
  assert.deepEqual(doc.entries.filter((e) => e.kind === 'built-in-kernel').map((e) => e.id).sort(), ['builtin:eagar-tsai', 'builtin:goldak', 'builtin:rosenthal']);
  const html = render(doc);
  assert.match(html, /Screening benchmark/);
  assert.equal([...html.matchAll(/data-testid="leaderboard-group"/g)].length, 6, 'three alloys x width/depth, one table each');
});
