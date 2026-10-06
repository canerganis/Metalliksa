// Fixture origin: hand-written rows in the CMU MTMeasurements.csv column layout (header per python/cmu_ti64_import.py).
// They are synthetic test inputs for the logic only, not CMU measurements.
import test from 'node:test';
import assert from 'node:assert/strict';
import { parseCmuMeasurementsCsv } from '../server/cmuMeasurements';
import { aggregateByVelocity, overlayGate, residualAt } from '../src/utils/experimentalValidation';

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
  assert.equal(r.depth!.withinRange, true);
  const none = residualAt(agg, 900, { width_um: 1, depth_um: 1 });
  assert.equal(none.available, false);
  assert.match(none.reason!, /not interpolated/);
});
