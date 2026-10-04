import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createVisiblePoller, type TimeoutScheduler } from '../src/hooks/useVisiblePolling';

function fakeTimers() {
  let next = 1;
  const pending = new Map<number, { cb: () => void; ms: number }>();
  const scheduler: TimeoutScheduler = {
    set: (cb, ms) => { const id = next++; pending.set(id, { cb, ms }); return id; },
    clear: (id) => { pending.delete(id as number); },
  };
  const fire = () => { const [id, t] = [...pending][0]; pending.delete(id); t.cb(); };
  return { scheduler, pending, fire };
}
const flush = () => new Promise<void>((resolve) => setImmediate(resolve));

test('poller: no polling while hidden (stopped), resumes immediately on show', async () => {
  const { scheduler, pending, fire } = fakeTimers();
  let polls = 0;
  const poller = createVisiblePoller(async () => { polls++; return 1500; }, scheduler);
  poller.start(1500);
  assert.equal(pending.size, 1);
  fire(); await flush();
  assert.equal(polls, 1);
  assert.equal(pending.size, 1);
  poller.stop(); // module hidden
  assert.equal(pending.size, 0);
  assert.equal(poller.running, false);
  await flush();
  assert.equal(polls, 1, 'hidden: no further polls');
  poller.start(0); // visible again: catch up at once
  assert.equal([...pending.values()][0].ms, 0);
  fire(); await flush();
  assert.equal(polls, 2);
  poller.stop();
});

test('poller: a response in flight when hidden is dropped and never reschedules', async () => {
  const { scheduler, pending, fire } = fakeTimers();
  let release: (n: number | null) => void = () => {};
  const lives: boolean[] = [];
  const poller = createVisiblePoller((isLive) => new Promise<number | null>((resolve) => {
    release = (n) => { lives.push(isLive()); resolve(n); };
  }), scheduler);
  poller.start(10);
  fire();
  poller.stop(); // hidden while the request is outstanding
  release(1500);
  await flush();
  assert.deepEqual(lives, [false]);
  assert.equal(pending.size, 0);
});

test('poller: terminal status (null) stops polling; errors are the step\'s retry decision', async () => {
  const { scheduler, pending, fire } = fakeTimers();
  const delays: Array<number | null> = [3000, null];
  const poller = createVisiblePoller(async () => delays.shift() ?? null, scheduler);
  poller.start(1500);
  fire(); await flush();
  assert.equal([...pending.values()][0].ms, 3000);
  fire(); await flush();
  assert.equal(pending.size, 0);
  assert.equal(poller.running, false);
});

test('poller: a throwing step ends the loop instead of leaking timers; start is idempotent', async () => {
  const { scheduler, pending, fire } = fakeTimers();
  const poller = createVisiblePoller(async () => { throw new Error('boom'); }, scheduler);
  poller.start(5); poller.start(5);
  assert.equal(pending.size, 1);
  fire(); await flush();
  assert.equal(pending.size, 0);
});

test('poller: restart after stop does not let the old in-flight step reschedule a second timer', async () => {
  const { scheduler, pending, fire } = fakeTimers();
  const resolvers: Array<(n: number | null) => void> = [];
  const poller = createVisiblePoller(() => new Promise<number | null>((resolve) => { resolvers.push(resolve); }), scheduler);
  poller.start(1);
  fire();
  poller.stop();
  poller.start(0);
  fire();
  resolvers[0](1500); // stale
  await flush();
  assert.equal(pending.size, 0);
  resolvers[1](1500); // current
  await flush();
  assert.equal(pending.size, 1);
  poller.stop();
});

// Source guards: every module render/poll loop must go through the visibility hooks, so a hidden module
// (App.tsx keeps visited modules mounted with `hidden`) cannot tick. These fail if a raw loop is reintroduced.
const read = (file: string) => readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8');
const gated: Array<[string, RegExp]> = [
  ['components/3d-distortion-lab/MeltPool3DCrossSectionLab.tsx', /useVisibleAnimationFrame\(/],
  ['components/3d-distortion-lab/ResolvedThermalViewer.tsx', /useVisibleAnimationFrame\(/],
  ['components/WebGLSpectrometerCanvas.tsx', /useVisibleAnimationFrame\(/],
  ['components/LaserMeltPoolThermalMap.tsx', /useVisibleInterval\(/],
  ['components/3d-distortion-lab/LpbfEngineeringSimulation.tsx', /useVisiblePolling\(/],
  ['components/3d-distortion-lab/LpbfEngineeringSimulation.tsx', /useVisibleInterval\(/],
  ['components/In625BareplatePanel.tsx', /useVisiblePolling\(/],
];
for (const [file, hook] of gated) {
  test(`${file} drives its loop through a visibility hook`, () => {
    const source = read(file);
    assert.match(source, hook);
    assert.doesNotMatch(source, /requestAnimationFrame\s*\(/, 'raw requestAnimationFrame loop');
    assert.doesNotMatch(source, /setInterval\s*\(/, 'raw setInterval loop');
  });
}

test('no job polling timer is left outside the visibility-aware poller in the gated panels', () => {
  for (const file of ['components/In625BareplatePanel.tsx', 'components/3d-distortion-lab/LpbfEngineeringSimulation.tsx']) {
    assert.doesNotMatch(read(file), /setTimeout\(poll/, file);
  }
});
