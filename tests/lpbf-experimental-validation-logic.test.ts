// Fixture origin: hand-written rows in the CMU MTMeasurements.csv column layout (header per python/cmu_ti64_import.py).
// They are synthetic test inputs for the logic only, not CMU measurements.
import test from 'node:test';
import assert from 'node:assert/strict';
import { parseCmuMeasurementsCsv } from '../server/cmuMeasurements';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { aggregateByVelocity, overlayGate, residualAt, describePowers, MEASURED_DEPTH_LABEL, DEPTH_NOT_COMPARABLE_REASON, type MeasuredRow } from '../src/utils/experimentalValidation';
import { DepthRow } from '../src/components/ExperimentalValidationLab';

const csv = ['Slice,Orientation (degrees),Power (W),Velocity (mm/s),Width (um),Depth (um),Cap (um)',
  '1,0,370,800,100,50,10', '2,0,370,800,120,70,12', '3,90,370,1000,90,-1,8', '4,90,370,1000,110,40,9'].join('\r\n');

test('parser locates columns by header, maps -1 to null, rejects missing columns', () => {
  const rows = parseCmuMeasurementsCsv(csv);
  assert.equal(rows.length, 4);
  assert.equal(rows[2].depth_um, null);
  assert.equal(rows[0].power_W, 370);
  assert.throws(() => parseCmuMeasurementsCsv('Slice,Velocity (mm/s)\n1,2'), /Orientation|Power/);
  // ST layout without Power must not silently parse as multi-track.
  assert.throws(() => parseCmuMeasurementsCsv('Slice,Orientation (degrees),Velocity (mm/s),Width (um),Depth (um),Cap (um)\n1,0,800,1,2,3'), /Power/);
});

test('per-velocity mean and sample sd; missing values excluded per quantity', () => {
  const agg = aggregateByVelocity(parseCmuMeasurementsCsv(csv));
  assert.deepEqual(agg.map(a => a.velocity_mms), [800, 1000]);
  assert.equal(agg[0].width!.mean, 110);
  assert.ok(Math.abs(agg[0].width!.sd! - Math.sqrt(200)) < 1e-9);
  assert.equal(agg[1].depth!.n, 1);
  assert.equal(agg[1].depth!.sd, null);
});

test('overlay gate requires material, power and beam diameter', () => {
  const ok = { material: 'Ti-6Al-4V', power_W: 370, beamDiameter_um: 100 };
  assert.equal(overlayGate(ok).eligible, true);
  assert.equal(overlayGate({ ...ok, material: 'in718' }).eligible, false);
  assert.equal(overlayGate({ ...ok, power_W: 300 }).eligible, false);
  assert.equal(overlayGate({ ...ok, beamDiameter_um: 80 }).eligible, false);
  assert.equal(overlayGate({ ...ok, material: 'ti6al4v' }).eligible, true);
  assert.equal(overlayGate(undefined).eligible, false);
  assert.equal(overlayGate({ ...ok, material: 'in718', beamDiameter_um: 80 }).reasons.length, 2);
});

test('residual only at measured velocities, no interpolation', () => {
  const agg = aggregateByVelocity(parseCmuMeasurementsCsv(csv));
  const r = residualAt(agg, 800, { width_um: 130, depth_um: 55 });
  assert.equal(r.available, true);
  assert.equal(r.width!.residual, 20);
  assert.equal(r.width!.withinRange, false);
  // Depth is context only: remelt depth (cap excluded) is not the simulated melt-pool depth, so no residual exists.
  assert.equal('residual' in r.depth!, false);
  assert.equal(r.depth!.measuredMean, 60);
  const none = residualAt(agg, 900, { width_um: 1, depth_um: 1 });
  assert.equal(none.available, false);
  assert.match(none.reason!, /not interpolated/);
});

test('heading power text is derived from the rows, not hard-coded', () => {
  assert.equal(describePowers(parseCmuMeasurementsCsv(csv)), 'all rows 370 W');
  assert.match(describePowers([{ power_W: 300, velocity_mms: 1, width_um: 1, depth_um: 1 }, { power_W: 370, velocity_mms: 1, width_um: 1, depth_um: 1 }]), /mixed powers: 300, 370 W/);
  assert.equal(describePowers([]), 'power not recorded');
});

test('depth row is labelled remelt depth (cap excluded) and carries no residual', () => {
  const agg = aggregateByVelocity(parseCmuMeasurementsCsv(csv));
  const r = residualAt(agg, 800, { width_um: 130, depth_um: 55 });
  const html = renderToStaticMarkup(React.createElement('table', null, React.createElement('tbody', null, React.createElement(DepthRow, { q: r.depth }))));
  assert.ok(html.includes(MEASURED_DEPTH_LABEL));
  assert.ok(html.includes('Remelt depth (cap excluded)'));
  assert.ok(html.includes('Not comparable'));
  assert.match(DEPTH_NOT_COMPARABLE_REASON, /quantity definitions differ/);
  assert.doesNotMatch(html, /[+-]\d+\.\d µm<\/td>/);
});

test('component source has no hard-coded power claim, renders unresolved scope and an empty-result state', () => {
  const src = readFileSync('src/components/ExperimentalValidationLab.tsx', 'utf8');
  assert.doesNotMatch(src, /all rows 370 W/);
  assert.match(src, /unresolved\.join/);
  assert.match(src, /No measurement rows were returned/);
  assert.match(src, /!loaded/);
});

// Fixture origin: data/benchmark/cmu-ti64-2026/mt_measurements.csv, the repo's pinned import of CMU MTMeasurements.csv
// (DOI 10.1184/R1/25696293.v1, CC BY 4.0), SHA-256 pinned in python/lpbf_public_datasets.py (CMU_MT_TABLE_SHA256).
const MT_TABLE = 'data/benchmark/cmu-ti64-2026/mt_measurements.csv';
const MT_SHA256 = 'd8d318fd673c69ad250a9d44cc7b37b71d3706cde7ad93539049454aedf09c57';
test('real pinned CMU MT table: hash, single power, per-velocity n and means', { skip: existsSync(MT_TABLE) ? false : `${MT_TABLE} is not present in this checkout` }, () => {
  const raw = readFileSync(MT_TABLE);
  assert.equal(createHash('sha256').update(raw).digest('hex'), MT_SHA256);
  const lines = raw.toString('utf8').split(/\r?\n/).filter(l => l.trim());
  const header = lines[0].split(',');
  const col = (name: string) => { const i = header.indexOf(name); assert.ok(i >= 0, name); return i; };
  const rows: MeasuredRow[] = lines.slice(1).map(l => { const p = l.split(','); return { power_W: Number(p[col('power_W')]), velocity_mms: Number(p[col('speed_mm_s')]), width_um: Number(p[col('width_um')]), depth_um: Number(p[col('depth_um')]) }; });
  assert.equal(rows.length, 410);
  assert.ok(rows.every(r => r.power_W === 370), 'all rows are 370 W');
  assert.equal(describePowers(rows), 'all rows 370 W');
  const agg = aggregateByVelocity(rows);
  assert.deepEqual(agg.map(a => a.velocity_mms), [1300, 1350, 1400, 1450, 1500, 1550, 1600, 1650, 1700]);
  assert.deepEqual(agg.map(a => a.width!.n), [46, 45, 45, 45, 45, 46, 46, 46, 46]);
  assert.ok(Math.abs(agg[0].width!.mean - 242.44586956521738) < 1e-9);
  assert.ok(Math.abs(agg[0].depth!.mean - 189.4463043478261) < 1e-9);
  assert.ok(Math.abs(agg[8].depth!.mean - 127.347) < 1e-9);
});
