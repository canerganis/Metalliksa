import React from 'react';
import test from 'node:test';
import assert from 'node:assert/strict';
import { renderToStaticMarkup } from 'react-dom/server';
import { WorkspaceVisibility } from '../src/components/WorkspaceVisibility';
import { startFrameLoop, useVisibleAnimationFrame, type FrameScheduler } from '../src/hooks/useVisibleAnimationFrame';
import { startInterval, useVisibleInterval, type IntervalScheduler } from '../src/hooks/useVisibleInterval';
import { createVisibleAbortScope, useVisibleAbortSignal } from '../src/hooks/useVisibleAbortSignal';

function fakeFrames() {
  let next = 1;
  const pending = new Map<number, () => void>();
  const scheduler: FrameScheduler = {
    request: (cb) => { const id = next++; pending.set(id, cb); return id; },
    cancel: (id) => { pending.delete(id); },
  };
  const tick = () => { const [id, cb] = [...pending][0]; pending.delete(id); cb(); };
  return { scheduler, tick, pending };
}

test('frame loop runs, reschedules, and stops on cancel', () => {
  const { scheduler, tick, pending } = fakeFrames();
  let calls = 0;
  const stop = startFrameLoop(() => { calls++; }, scheduler);
  tick(); tick();
  assert.equal(calls, 2);
  assert.equal(pending.size, 1);
  stop();
  assert.equal(pending.size, 0);
});

test('frame loop does not reschedule when stopped from inside the callback', () => {
  const { scheduler, tick, pending } = fakeFrames();
  let stop = () => {};
  stop = startFrameLoop(() => stop(), scheduler);
  tick();
  assert.equal(pending.size, 0);
});

test('interval starts and clears through its scheduler', () => {
  const live = new Set<unknown>();
  const scheduler: IntervalScheduler = { set: () => { const h = {}; live.add(h); return h; }, clear: (h) => { live.delete(h); } };
  const stop = startInterval(() => {}, 100, scheduler);
  assert.equal(live.size, 1);
  stop();
  assert.equal(live.size, 0);
});

test('abort scope aborts when hidden and issues a fresh signal when shown again', () => {
  const scope = createVisibleAbortScope();
  const first = scope.show();
  assert.equal(scope.show(), first);
  scope.hide();
  assert.equal(first.aborted, true);
  const second = scope.show();
  assert.notEqual(second, first);
  assert.equal(second.aborted, false);
});

test('hooks render safely under server rendering in visible and hidden workspaces', () => {
  function Probe() {
    useVisibleAnimationFrame(() => { throw new Error('effects never run on the server'); });
    useVisibleInterval(() => { throw new Error('effects never run on the server'); }, 10);
    const signal = useVisibleAbortSignal();
    return <output>{signal ? 'signal' : 'none'}</output>;
  }
  for (const visible of [true, false]) {
    assert.equal(renderToStaticMarkup(<WorkspaceVisibility visible={visible}><Probe /></WorkspaceVisibility>), '<output>none</output>');
  }
});
