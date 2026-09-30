import React from 'react';
import assert from 'node:assert/strict';
import test from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import { EngineeringRoadmapPanel } from '../src/components/EngineeringRoadmapPanel';
import { engineeringRoadmap, MILESTONES, summarizeRoadmap, summarizeEngineeringGates, type EngineeringTask } from '../src/data/engineeringRoadmap';
const task = (id = 'A01'): EngineeringTask => ({ id, title: 'Fixture', weight: 5, dependencies: [], acceptance: 'Fixture acceptance', milestones: [], blocker: null, nextAction: 'Review' });
const milestones = MILESTONES.map(m => ({ id: m.id, evidence: 'Synthetic test evidence', reviewer: 'Test reviewer', date: '2026-09-15' }));

test('customer and commercial gates cannot bypass any unaccepted K2 module', () => {
  for (const missing of ['E02', 'E03', 'E04', 'F01']) {
    const items = engineeringRoadmap.map(item => ({ id: item.id, accepted: item.id !== missing }));
    const gates = summarizeEngineeringGates(items);
    assert.deepEqual(gates.map(gate => gate.accepted), [true, true, false, false, false]);
    assert.deepEqual(gates[2].missingTasks, [missing]);
    assert.deepEqual(gates[3].pendingPredecessors, ['K2']);
    assert.deepEqual(gates[4].pendingPredecessors, ['K2', 'K3']);
  }
  assert.ok(summarizeEngineeringGates(engineeringRoadmap.map(item => ({ id: item.id, accepted: true }))).every(gate => gate.accepted));
  assert.ok(summarizeEngineeringGates([]).every(gate => !gate.accepted));
});
test('weighted earned work and accepted scope stay separate', () => {
  const a = task(), b = task('A02'); a.milestones = milestones.slice(0, 3);
  const summary = summarizeRoadmap([a, b]);
  assert.equal(summary.earned, 37.5); assert.equal(summary.remaining, 62.5); assert.equal(summary.acceptedCount, 0);
  a.milestones = milestones; b.dependencies = ['A01']; b.milestones = milestones;
  assert.equal(summarizeRoadmap([a, b]).acceptedPercent, 100);
  a.milestones = milestones.slice(0, 2);
  assert.throws(() => summarizeRoadmap([a, b]), /Acceptance blocked/);
});
test('out-of-order, duplicate, unproven or invalid evidence cannot earn credit', () => {
  for (const bad of [[milestones[1]], [milestones[0], milestones[0]], [{ ...milestones[0], evidence: ' ' }], [{ ...milestones[0], date: '2026-02-30' }]]) {
    assert.throws(() => summarizeRoadmap([{ ...task(), milestones: bad }]));
  }
  assert.throws(() => summarizeRoadmap([{ ...task(), milestones, blocker: 'Missing approval' }]), /Acceptance blocked/);
  assert.throws(() => summarizeRoadmap([task(), task()]), /Duplicate/);
  assert.throws(() => summarizeRoadmap([{ ...task(), dependencies: ['missing'] }]), /Unknown/);
  assert.throws(() => summarizeRoadmap([{ ...task(), dependencies: ['A02'] }, { ...task('A02'), dependencies: ['A01'] }]), /Cyclic/);
  assert.throws(() => summarizeRoadmap([{ ...task(), weight: NaN }]));
});
test('real roadmap and UI expose all 20 packages, gates, evidence limits and remaining work', () => {
  assert.equal(engineeringRoadmap.length, 20);
  summarizeRoadmap(engineeringRoadmap);
  const html = renderToStaticMarkup(<EngineeringRoadmapPanel/>);
  for (const card of engineeringRoadmap) assert.ok(html.includes(card.id));
  for (const phrase of ['remaining', 'K0', 'K4', 'Deferred qualification backlog', 'V1 Research Workstation release is active', 'does not establish scientific validation', 'Acceptance prerequisites', 'Next:']) assert.ok(html.includes(phrase));
});
