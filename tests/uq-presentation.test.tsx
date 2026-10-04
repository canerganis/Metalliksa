import assert from 'node:assert/strict';
import test from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { AEROSPACE_MATERIAL_DATASETS, computeMMPDSEmpiricalStats, type MaterialDataset } from '../src/components/uqLabData';
import { CouponSummary, CouponWorksheet, UQ_MODEL_STATUS_LABEL, UqModelStatusNote, couponReportRows, couponWorksheetText } from '../src/components/UqCouponReport';
import { readFileSync } from 'node:fs';
import { createUqRunSession } from '../src/utils/uqRunSession';

const dataset: MaterialDataset = { ...AEROSPACE_MATERIAL_DATASETS[0], couponSource: 'uploaded', coupons: [0, 1, 2].map(i => ({ id: `test-${i}`, specimenNumber: `S${i}`, heatLotId: '', testTempC: null, yieldStrengthMPa: 100 + 10 * i, utsMPa: 200 + 20 * i, elongationPct: 3 + i, reductionOfAreaPct: null, testStandard: '', evidenceOrigin: 'unknown' })) };

test('worksheet uses every actual coupon property and preserves its unit and unverified scope', () => {
  const rows = couponReportRows(dataset);
  assert.deepEqual(rows.map(r => [r.key, r.unit, r.stats.mean]), [['yieldStrength','MPa',110],['uts','MPa',220],['elongation','%',4]]);
  const text = couponWorksheetText(dataset);
  assert.match(text, /Yield strength \(MPa\): n=3; mean=110.0/);
  assert.match(text, /Ultimate tensile strength \(MPa\): n=3; mean=220.0/);
  assert.match(text, /Elongation \(%\): n=3; mean=4.0/);
  assert.match(text, /Normality not tested/); assert.match(text, /independent verification/);
  assert.doesNotMatch(text, /Gaussian \(p|production batches|Certified|1\.48|1\.52/);
  const markup = renderToStaticMarkup(<CouponWorksheet dataset={dataset} onCopy={() => {}} notification={null} />);
  assert.match(markup, /110\.0/); assert.match(markup, /220\.0/); assert.doesNotMatch(markup, /NaN|Infinity/);
});

test('empty and constant coupons never render passing evidence or a manufactured process index', () => {
  for (const values of [[], [100], [100,100,100]]) {
    const markup = renderToStaticMarkup(<CouponSummary stats={computeMMPDSEmpiricalStats(values, 50)} unit="MPa" synthetic={false} />);
    assert.match(markup, /Not assessed/); assert.match(markup, /Not tested/);
    assert.doesNotMatch(markup, /NaN|Infinity|high Cpk|Gaussian/);
    if (!values.length) assert.doesNotMatch(markup, /100\.0%/);
  }
  assert.match(couponWorksheetText({ ...dataset, coupons: dataset.coupons.map(c => ({ ...c, evidenceOrigin: 'synthetic' })) }), /Synthetic teaching coupons/);
});

test('the Sobol view labels the strength model as illustrative and shows the solver modelStatus when present', () => {
  assert.equal(UQ_MODEL_STATUS_LABEL, 'Illustrative strength model, not calibrated (see modelStatus)');
  const bare = renderToStaticMarkup(<UqModelStatusNote />);
  assert.match(bare, /Illustrative strength model, not calibrated/);
  const full = renderToStaticMarkup(<UqModelStatusNote modelStatus="Illustrative, not calibrated: toy model." />);
  assert.match(full, /Illustrative strength model, not calibrated/); assert.match(full, /toy model/);
  // The label is rendered by UQLab next to the Sobol table, fed from the response provenance,
  // and the solver really emits that note.
  const lab = readFileSync(new URL('../src/components/UQLab.tsx', import.meta.url), 'utf8');
  assert.match(lab, /<UqModelStatusNote modelStatus=\{uqResult\.provenance\?\.modelStatus\} \/>/);
  const solver = readFileSync(new URL('../python/stochastic_uq_mmpds_solver.py', import.meta.url), 'utf8');
  assert.match(solver, /"modelStatus": "Illustrative, not calibrated/);
});

test('late UQ success and failure cannot overwrite a newer run or its loading state', async () => {
  const session = createUqRunSession<string>(), received: {loading:boolean;result:string|null;error:string|null}[] = [];
  let oldResolve!: (value:string)=>void, newResolve!: (value:string)=>void;
  const old = session.run(() => new Promise(resolve => { oldResolve = resolve; }), s => received.push(s));
  const next = session.run(() => new Promise(resolve => { newResolve = resolve; }), s => received.push(s));
  oldResolve('old'); await old; assert.equal(received.at(-1)?.loading, true);
  newResolve('current'); await next; assert.equal(received.at(-1)?.result,'current');
  let reject!: (error:Error)=>void;
  const failing = session.run(() => new Promise((_resolve, no) => { reject = no; }), s => received.push(s));
  session.invalidate(); reject(new Error('old failure')); await failing; assert.equal(received.at(-1)?.error, null);
  await session.run(async () => { throw new Error('current failure'); }, s => received.push(s));
  assert.equal(received.at(-1)?.result, null); assert.equal(received.at(-1)?.error, 'current failure');
});
