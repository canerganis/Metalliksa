import test from 'node:test';
import assert from 'node:assert/strict';
import { createElasticityRequestGate } from '../src/utils/elasticityRequestGate';

test('the first request is current immediately, without a React state update', () => {
  const gate = createElasticityRequestGate();
  const first = gate.begin();
  assert.equal(gate.isCurrent(first), true);
});

test('editing away and back to identical inputs cannot revive an old request', () => {
  const gate = createElasticityRequestGate();
  const firstA = gate.begin();
  gate.invalidate();
  gate.invalidate();
  const secondA = gate.begin();
  assert.equal(gate.isCurrent(firstA), false);
  assert.equal(gate.isCurrent(secondA), true);
});

test('a newer request excludes both old success and old error callbacks', () => {
  const gate = createElasticityRequestGate();
  const old = gate.begin();
  const latest = gate.begin();
  let result = 'pending';
  if (gate.isCurrent(old)) result = 'old success';
  if (gate.isCurrent(old)) result = 'old error';
  assert.equal(result, 'pending');
  if (gate.isCurrent(latest)) result = 'latest';
  assert.equal(result, 'latest');
});

test('cleanup invalidates pending work and permits a new request after remount', () => {
  const gate = createElasticityRequestGate();
  const old = gate.begin();
  gate.invalidate();
  assert.equal(gate.isCurrent(old), false);
  const next = gate.begin();
  assert.equal(gate.isCurrent(next), true);
});
