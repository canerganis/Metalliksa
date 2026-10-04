import assert from 'node:assert/strict';
import type { ChildProcessWithoutNullStreams } from 'node:child_process';
import { EventEmitter } from 'node:events';
import { PassThrough } from 'node:stream';
import { test } from 'node:test';
import { LpbfWorkerBridge } from '../server/lpbfWorkerBridge';

// Fake child process: no real pipes or timers beyond the bridge's own stop logic.
function fakeChild(pid: number, options: { exitOnTerm: boolean }) {
  const emitter = new EventEmitter() as EventEmitter & Record<string, unknown>;
  const kills: Array<string | undefined> = [];
  emitter.pid = pid;
  emitter.exitCode = null;
  emitter.signalCode = null;
  emitter.stdout = new PassThrough();
  emitter.stderr = new PassThrough();
  emitter.stdin = new PassThrough();
  emitter.kill = (signal?: string) => {
    kills.push(signal);
    if (signal === 'SIGKILL' || options.exitOnTerm) {
      emitter.exitCode = 0;
      setImmediate(() => emitter.emit('close', 0));
    }
    return true;
  };
  return { child: emitter as unknown as ChildProcessWithoutNullStreams, kills };
}

test('stopTracked stops a new child while another child stop is in flight', async () => {
  const bridge = new LpbfWorkerBridge();
  const stuck = fakeChild(101, { exitOnTerm: false });
  const fresh = fakeChild(102, { exitOnTerm: true });
  const tracked = bridge as unknown as { stopTracked(child: ChildProcessWithoutNullStreams): Promise<void> };
  const first = tracked.stopTracked(stuck.child);
  await tracked.stopTracked(fresh.child);
  assert.deepEqual(fresh.kills, [undefined], 'the second child must receive its own kill');
  assert.equal(tracked.stopTracked(stuck.child), first, 'repeat stop of the same child shares one promise');
  await first;
});

test('non-JSON stdout is kept as a bounded diagnostic in the exit error', async () => {
  const { child } = fakeChild(103, { exitOnTerm: true });
  const bridge = new LpbfWorkerBridge({
    command: () => ({ cmd: 'native-python', args: [] }),
    spawn: () => child,
  });
  const request = bridge.request('ping');
  setImmediate(() => {
    for (let i = 0; i < 30; i++) (child.stdout as unknown as PassThrough).write(`banner line ${i}\n`);
    (child.stderr as unknown as PassThrough).write('stderr text');
    setTimeout(() => { (child as unknown as Record<string, unknown>).exitCode = 3; child.emit('exit', 3); }, 20);
  });
  await assert.rejects(request, (error: Error) => {
    assert.match(error.message, /LPBF worker exited \(3\): stderr text/);
    assert.match(error.message, /non-JSON stdout: .*banner line 29/);
    assert.doesNotMatch(error.message, /banner line 9\b/);
    return true;
  });
  bridge.close();
});

test('oversized non-JSON stdout line is capped at 500 characters in the diagnostic', async () => {
  const { child } = fakeChild(104, { exitOnTerm: true });
  const bridge = new LpbfWorkerBridge({
    command: () => ({ cmd: 'native-python', args: [] }),
    spawn: () => child,
  });
  const request = bridge.request('ping');
  setImmediate(() => {
    (child.stdout as unknown as PassThrough).write(`${'x'.repeat(2000)}\n`);
    setTimeout(() => { (child as unknown as Record<string, unknown>).exitCode = 3; child.emit('exit', 3); }, 20);
  });
  await assert.rejects(request, (error: Error) => {
    const run = error.message.match(/x+/g)?.sort((a, b) => b.length - a.length)[0] ?? '';
    assert.ok(run.length > 0 && run.length <= 500, `oversized line kept ${run.length} chars`);
    return true;
  });
  bridge.close();
});

test('only the last 20 non-JSON stdout lines are kept', async () => {
  const { child } = fakeChild(105, { exitOnTerm: true });
  const bridge = new LpbfWorkerBridge({
    command: () => ({ cmd: 'native-python', args: [] }),
    spawn: () => child,
  });
  const request = bridge.request('ping');
  setImmediate(() => {
    for (let i = 0; i < 25; i++) (child.stdout as unknown as PassThrough).write(`noise-${i}-end\n`);
    setTimeout(() => { (child as unknown as Record<string, unknown>).exitCode = 3; child.emit('exit', 3); }, 20);
  });
  await assert.rejects(request, (error: Error) => {
    const kept = error.message.match(/noise-\d+-end/g) ?? [];
    assert.equal(kept.length, 20);
    assert.equal(kept[0], 'noise-5-end');
    assert.equal(kept[19], 'noise-24-end');
    return true;
  });
  bridge.close();
});
