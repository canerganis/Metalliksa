import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
import { parseMeasurementPayload, measurementSubmission } from '../src/components/3d-distortion-lab/LpbfEngineeringSimulation';
import type { SimulationInput } from '../src/services/lpbfSimulationService';

const input: SimulationInput = { material: 'Inconel 718', mode: 'calibration', power_W: 60, speed_mm_s: 1200, beamDiameter_um: 80, preheat_C: 200, layer_um: 20, hatch_um: 100, tracks: 1, layers: 1, trackLength_um: 600, strategy: 'meander', scanAngle_deg: 0, layerRotation_deg: 67, dwell_s: .0002, packingFraction: .55, stripeWidth_um: 500, islandSize_um: 200, absorptivity: .35, emissivity: .4, powderConductivityRatio: .12, convection_W_m2K: 20, cooling_s: .0005 };
const { mode: _mode, ...vector } = input;
const row = { width_um: 110, depth_um: 35, source: 'Synthetic submission fixture only', uncertainty_um: { width_um: 2, depth_um: 3 }, independentHoldout: false };
const emptyDraft = { width: '', depth: '', source: '', specimen: '', uncertainty: '', holdout: 'unknown' };
const parse = (value: unknown) => parseMeasurementPayload(JSON.stringify([value]), input, 'meander');

test('conditionless replicate stays conditionless in the actual submission builder', () => {
  const parsed = parse(row);
  assert.equal(parsed.status, 'valid');
  assert.equal(parsed.missingProcessVectorCount, 1);
  assert.equal(Object.hasOwn(parsed.measurements![0], 'processVector'), false);
  assert.deepEqual(measurementSubmission(input, JSON.stringify([row]), emptyDraft, 'meander'), [row]);
});

test('all 22 explicitly supplied conditions survive submission exactly', () => {
  assert.equal(Object.keys(vector).length, 22);
  const supplied = { ...row, processVector: vector };
  assert.deepEqual(measurementSubmission(input, JSON.stringify([supplied]), emptyDraft, 'meander'), [supplied]);
  const unresolvedOptics = { ...input, absorptivity: undefined, emissivity: undefined };
  assert.deepEqual(measurementSubmission(unresolvedOptics, JSON.stringify([supplied]), emptyDraft, 'meander'), [supplied]);
});

test('the frontend fixture covers exactly the current backend condition keys', () => {
  const backend = readFileSync(new URL('../python/lpbf_evidence.py', import.meta.url), 'utf8');
  const definition = backend.match(/PROCESS_KEYS = \(([\s\S]*?)\)/);
  assert.ok(definition);
  const keys = [...definition[1].matchAll(/"([^"]+)"/g)].map(match => match[1]);
  assert.deepEqual(Object.keys(vector).sort(), keys.sort());
});

test('partial or malformed conditions are actionable errors, never filled or dropped', () => {
  for (const processVector of [{}, { power_W: 60 }, null, [], 'current', { ...vector, extra: 1 }, { ...vector, power_W: '60' }, { ...vector, tracks: true }, { ...vector, material: '' }, { ...vector, strategy: 3 }]) {
    const parsed = parse({ ...row, processVector });
    assert.equal(parsed.status, 'invalid', JSON.stringify(processVector));
    assert.match(parsed.errors.join(' '), /processVector/);
    assert.throws(() => measurementSubmission(input, JSON.stringify([{ ...row, processVector }]), emptyDraft, 'meander'), /processVector/);
  }
});

test('explicit mismatching conditions are preserved for worker rejection', () => {
  const supplied = { ...row, processVector: { ...vector, power_W: 61 } };
  const parsed = parse(supplied);
  assert.equal(parsed.mismatchedCount, 1);
  assert.deepEqual(measurementSubmission(input, JSON.stringify([supplied]), emptyDraft, 'meander'), [supplied]);
});

test('manual dimensions preserve user evidence without inventing conditions', () => {
  const submitted = measurementSubmission(input, '', { width: '110', depth: '35', source: row.source, specimen: 'Specimen A', uncertainty: '2', holdout: 'yes' }, 'meander');
  assert.deepEqual(submitted, [{ width_um: 110, depth_um: 35, source: `${row.source} · Specimen A`, uncertainty_um: { width_um: 2, depth_um: 2 }, independentHoldout: true }]);
});

test('manual values require finite positive dimensions and nonnegative uncertainty', () => {
  const draft = { width: '110', depth: '35', source: row.source, specimen: '', uncertainty: '', holdout: 'unknown' };
  for (const width of ['NaN', 'Infinity', '-1', '0']) assert.throws(() => measurementSubmission(input, '', { ...draft, width }, 'meander'), /positive/);
  for (const uncertainty of ['NaN', 'Infinity', '-1']) assert.throws(() => measurementSubmission(input, '', { ...draft, uncertainty }, 'meander'), /uncertainty/);
  assert.throws(() => measurementSubmission(input, '', emptyDraft, 'meander'), /requires/);
  assert.equal(measurementSubmission({ ...input, mode: 'standard' }, '', emptyDraft, 'meander'), undefined);
});

test('replicate dimensions and uncertainty must be supplied as finite JSON numbers', () => {
  for (const value of [true, '110', null, [], {}, 0, -1, NaN, Infinity]) {
    for (const key of ['width_um', 'depth_um']) {
      const supplied = { ...row, [key]: value };
      assert.equal(parse(supplied).status, 'invalid', `${key}: ${JSON.stringify(value)}`);
      assert.throws(() => measurementSubmission(input, JSON.stringify([supplied]), emptyDraft, 'meander'), /positive finite/);
    }
  }
  for (const value of [false, '2', null, [], {}, -1, NaN, Infinity]) {
    for (const key of ['width_um', 'depth_um']) {
      const supplied = { ...row, uncertainty_um: { ...row.uncertainty_um, [key]: value } };
      assert.equal(parse(supplied).status, 'invalid', `uncertainty ${key}: ${JSON.stringify(value)}`);
      assert.throws(() => measurementSubmission(input, JSON.stringify([supplied]), emptyDraft, 'meander'), /nonnegative finite/);
    }
  }
  const supplied = { ...row, uncertainty_um: { width_um: 0, depth_um: 0 }, independentHoldout: true };
  assert.deepEqual(measurementSubmission(input, JSON.stringify([supplied]), emptyDraft, 'meander'), [supplied]);
});

test('the real component submit path uses the tested builder', () => {
  const source = readFileSync(new URL('../src/components/3d-distortion-lab/LpbfEngineeringSimulation.tsx', import.meta.url), 'utf8');
  assert.match(source, /p\.measurements\s*=\s*measurementSubmission\(p,measurements,/);
  assert.doesNotMatch(source, /process vectors are matched and ready/);
  assert.match(source, /Manual dimensions have no measurement conditions/);
});

test('unknown replicate fields are rejected with their names rather than dropped', () => {
  for (const fields of [{ measurementDate: '2026-10-03' }, { widht_um: 120 }, { specimenId: 'A', uncertainty_units: 'um' }]) {
    const supplied = { ...row, ...fields };
    const parsed = parse(supplied);
    assert.equal(parsed.status, 'invalid');
    for (const key of Object.keys(fields)) assert.ok(parsed.errors.some(error => error.includes(key)), key);
    assert.throws(() => measurementSubmission(input, JSON.stringify([supplied]), emptyDraft, 'meander'), /unknown fields/);
  }
});

test('uncertainty accepts exactly width and depth and rejects extra field names', () => {
  const supplied = { ...row, uncertainty_um: { ...row.uncertainty_um, units: 'um', confidence: .95 } };
  const parsed = parse(supplied);
  assert.equal(parsed.status, 'invalid');
  assert.match(parsed.errors.join(' '), /uncertainty_um.*units.*confidence/);
  assert.throws(() => measurementSubmission(input, JSON.stringify([supplied]), emptyDraft, 'meander'), /uncertainty_um/);
  assert.equal(parse({ ...row, uncertainty_um: { width_um: 2 } }).status, 'invalid');
});

test('supported mixed-condition batches preserve every supplied known value', () => {
  const rows = [row, { width_um: 113, depth_um: 38, source: 'Second synthetic specimen', processVector: vector, uncertainty_um: { width_um: 0, depth_um: 4 }, independentHoldout: true }];
  const parsed = parseMeasurementPayload(JSON.stringify(rows), input, 'meander');
  assert.equal(parsed.status, 'valid');
  assert.equal(parsed.count, 2);
  assert.equal(parsed.missingProcessVectorCount, 1);
  assert.equal(parsed.mismatchedCount, 0);
  assert.deepEqual(measurementSubmission(input, JSON.stringify(rows), emptyDraft, 'meander'), rows);
});
