import React from 'react';
import test from 'node:test';
import assert from 'node:assert/strict';
import { renderToStaticMarkup } from 'react-dom/server';
import { WorkspaceVisibility } from '../src/components/WorkspaceVisibility';
import { createVisibleLoop, startFrameLoop, useVisibleAnimationFrame, type FrameScheduler } from '../src/hooks/useVisibleAnimationFrame';
import { createVisibleInterval, startInterval, useVisibleInterval, type IntervalScheduler } from '../src/hooks/useVisibleInterval';
import { createVisibleAbort, createVisibleAbortScope, useVisibleAbortSignal } from '../src/hooks/useVisibleAbortSignal';

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

test('loop controller: hide cancels, show restarts, unmount cleans up', () => {
  const { scheduler, tick, pending } = fakeFrames();
  let calls = 0;
  const loop = createVisibleLoop(() => { calls++; }, scheduler);
  loop.start();
  tick();
  assert.equal(calls, 1);
  loop.stop(); // hidden
  assert.equal(pending.size, 0);
  assert.equal(loop.running, false);
  loop.start(); // visible again
  tick();
  assert.equal(calls, 2);
  loop.stop(); // unmount
  assert.equal(pending.size, 0);
});

test('loop controller: StrictMode double start/stop never leaks a second loop', () => {
  const { scheduler, pending } = fakeFrames();
  const loop = createVisibleLoop(() => {}, scheduler);
  loop.start(); loop.stop(); loop.start();
  assert.equal(pending.size, 1);
  loop.start();
  assert.equal(pending.size, 1);
  loop.stop(); loop.stop();
  assert.equal(pending.size, 0);
});

test('loop controller: callback changes through a ref do not restart the loop', () => {
  const { scheduler, tick, pending } = fakeFrames();
  const seen: string[] = [];
  const ref = { current: () => { seen.push('a'); } };
  const loop = createVisibleLoop(() => ref.current(), scheduler);
  loop.start();
  tick();
  ref.current = () => { seen.push('b'); };
  assert.equal(pending.size, 1);
  assert.equal(loop.running, true);
  tick();
  assert.deepEqual(seen, ['a', 'b']);
  loop.stop();
});

function fakeIntervals() {
  const live = new Map<object, () => void>();
  const scheduler: IntervalScheduler = {
    set: (cb) => { const h = {}; live.set(h, cb); return h; },
    clear: (h) => { live.delete(h as object); },
  };
  return { scheduler, live };
}

test('interval controller: hide clears, show restarts, unmount cleans up', () => {
  const { scheduler, live } = fakeIntervals();
  let calls = 0;
  const interval = createVisibleInterval(() => { calls++; }, 50, scheduler);
  interval.start();
  [...live.values()][0]();
  assert.equal(calls, 1);
  interval.stop();
  assert.equal(live.size, 0);
  interval.start();
  assert.equal(live.size, 1);
  interval.stop();
  assert.equal(live.size, 0);
});

test('interval controller: StrictMode double start/stop and ref callback swap keep one timer', () => {
  const { scheduler, live } = fakeIntervals();
  const seen: string[] = [];
  const ref = { current: () => { seen.push('a'); } };
  const interval = createVisibleInterval(() => ref.current(), 50, scheduler);
  interval.start(); interval.stop(); interval.start(); interval.start();
  assert.equal(live.size, 1);
  const timer = [...live.keys()][0];
  [...live.values()][0]();
  ref.current = () => { seen.push('b'); };
  assert.equal([...live.keys()][0], timer);
  [...live.values()][0]();
  assert.deepEqual(seen, ['a', 'b']);
  interval.stop(); interval.stop();
  assert.equal(live.size, 0);
});

test('abort controller: publishes a live signal, aborts on hide, replaces it on show', () => {
  const published: Array<AbortSignal | null> = [];
  const abort = createVisibleAbort((s) => { published.push(s); });
  abort.show();
  const first = published[0]!;
  assert.equal(first.aborted, false);
  abort.hide();
  assert.equal(first.aborted, true);
  assert.equal(published[1], null);
  abort.show();
  const second = published[2]!;
  assert.notEqual(second, first);
  assert.equal(second.aborted, false);
});

test('abort controller: unmount cleanup aborts without publishing; double show reuses the signal', () => {
  const published: Array<AbortSignal | null> = [];
  const abort = createVisibleAbort((s) => { published.push(s); });
  abort.show(); abort.show();
  assert.equal(published[0], published[1]);
  abort.hide(false);
  assert.equal(published[0]!.aborted, true);
  assert.equal(published.length, 2);
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
