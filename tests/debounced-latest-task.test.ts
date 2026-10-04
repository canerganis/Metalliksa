import test from 'node:test';
import assert from 'node:assert/strict';
import { createDebouncedLatestTask } from '../src/utils/debouncedLatestTask';

function harness() {
  const calls: Array<{ sig: string; signal: AbortSignal; resolve: (v: boolean) => void }> = [];
  const task = createDebouncedLatestTask({
    delayMs: 100,
    run: (sig, signal) => new Promise<boolean>(resolve => { calls.push({ sig, signal, resolve }); }),
  });
  return { calls, task };
}
const flush = () => new Promise<void>(r => setImmediate(r));

test('burst of schedules computes only the last signature after the quiet period', t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const { calls, task } = harness();
  task.schedule('a'); t.mock.timers.tick(60);
  task.schedule('b'); t.mock.timers.tick(60);
  task.schedule('c');
  assert.equal(calls.length, 0);
  t.mock.timers.tick(99);
  assert.equal(calls.length, 0);
  t.mock.timers.tick(1);
  assert.deepEqual(calls.map(c => c.sig), ['c']);
});

test('same signature is not rescheduled while pending, running or after completing', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const { calls, task } = harness();
  task.schedule('a'); task.schedule('a');
  t.mock.timers.tick(100);
  task.schedule('a');
  assert.equal(calls.length, 1);
  calls[0].resolve(true);
  await flush();
  task.schedule('a');
  t.mock.timers.tick(500);
  assert.equal(calls.length, 1, 'completed identical input must not recompute');
});

test('a new signature aborts the in-flight run and the last input is computed', t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const { calls, task } = harness();
  task.schedule('a'); t.mock.timers.tick(100);
  assert.equal(calls[0].signal.aborted, false);
  task.schedule('b');
  assert.equal(calls[0].signal.aborted, true, 'superseded run is aborted');
  t.mock.timers.tick(100);
  assert.deepEqual(calls.map(c => c.sig), ['a', 'b']);
  assert.equal(calls[1].signal.aborted, false);
});

test('suspend (hidden) stops pending and in-flight work, keeps completed result, resume recomputes only unfinished', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const { calls, task } = harness();
  task.schedule('a');
  task.suspend();
  t.mock.timers.tick(1000);
  assert.equal(calls.length, 0, 'hidden: debounce timer cleared');
  task.schedule('a'); t.mock.timers.tick(100);
  task.suspend();
  assert.equal(calls[0].signal.aborted, true, 'hidden: in-flight aborted');
  task.schedule('a'); t.mock.timers.tick(100);
  assert.equal(calls.length, 2, 'unfinished work restarts when visible again');
  calls[1].resolve(true); await flush();
  task.suspend(); task.schedule('a'); t.mock.timers.tick(1000);
  assert.equal(calls.length, 2, 'completed result survives hide/show');
});

test('failed or unpublished run is retried on next schedule; runNow flushes the debounce and reruns', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const { calls, task } = harness();
  task.schedule('a'); t.mock.timers.tick(100);
  calls[0].resolve(false); await flush();
  task.schedule('a'); t.mock.timers.tick(100);
  assert.equal(calls.length, 2);
  calls[1].resolve(true); await flush();
  task.runNow('a');
  assert.equal(calls.length, 3, 'runNow reruns a completed signature immediately');
  task.cancel();
  assert.equal(calls[2].signal.aborted, true);
});
