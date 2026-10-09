import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { ENGINE_POLL_DELAYS_MS, startEngineReadyPoll } from '../src/utils/engineStatusPoll';

// Header badge: the daemon finishes starting after the first status check, so the shell re-polls until ready.
type Status = { online: boolean };

function harness(answers: boolean[], hidden = false) {
  const timers: Array<{ fn: () => void; ms: number; live: boolean }> = [];
  const seen: boolean[] = [];
  const visibility: Array<() => void> = [];
  const state = { hidden, checks: 0 };
  const stop = startEngineReadyPoll<Status>({
    check: async () => ({ online: answers[Math.min(state.checks++, answers.length - 1)] }),
    onStatus: (s) => seen.push(s.online),
    setTimer: (fn, ms) => { const t = { fn, ms, live: true }; timers.push(t); return t; },
    clearTimer: (h) => { (h as { live: boolean }).live = false; },
    isHidden: () => state.hidden,
    onVisibilityChange: (cb) => { visibility.push(cb); return () => { visibility.length = 0; }; },
  });
  const tick = async () => { const t = timers.filter((x) => x.live).pop(); assert.ok(t, 'a timer is pending'); t.live = false; t.fn(); await Promise.resolve(); await Promise.resolve(); return t.ms; };
  return { stop, timers, seen, visibility, state, tick };
}

test('re-polls with growing delays and stops once the engine is online', async () => {
  const h = harness([false, false, true]);
  assert.equal(await h.tick(), ENGINE_POLL_DELAYS_MS[0]);
  assert.equal(await h.tick(), ENGINE_POLL_DELAYS_MS[1]);
  assert.equal(await h.tick(), ENGINE_POLL_DELAYS_MS[2]);
  assert.deepEqual(h.seen, [false, false, true]);
  assert.equal(h.timers.filter((t) => t.live).length, 0, 'no further timer after ready');
  assert.equal(h.state.checks, 3);
});

test('gives up after the last delay when the engine never comes up', async () => {
  const h = harness([false]);
  for (let i = 0; i < ENGINE_POLL_DELAYS_MS.length; i++) await h.tick();
  assert.equal(h.state.checks, ENGINE_POLL_DELAYS_MS.length);
  assert.equal(h.timers.filter((t) => t.live).length, 0);
});

test('does not check while the tab is hidden and resumes when it is visible again', async () => {
  const h = harness([true], true);
  await h.tick();
  assert.equal(h.state.checks, 0);
  assert.deepEqual(h.seen, []);
  h.state.hidden = false;
  h.visibility[0]();
  await Promise.resolve(); await Promise.resolve();
  assert.equal(h.state.checks, 1);
  assert.deepEqual(h.seen, [true]);
});

test('stop() cancels the pending timer', () => {
  const h = harness([false]);
  h.stop();
  assert.equal(h.timers.filter((t) => t.live).length, 0);
});

test('the app shell wires the poll to the badge status', () => {
  const src = readFileSync('src/App.tsx', 'utf8');
  assert.match(src, /startEngineReadyPoll\(/);
  assert.match(src, /onStatus: \(next\) => \{ setStatus\(next\)/);
});
