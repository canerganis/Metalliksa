import assert from 'node:assert/strict';
import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import { once } from 'node:events';
import path from 'node:path';
import { test } from 'node:test';
import express from 'express';
import { LpbfWorkerBridge, LpbfWorkerUnavailableError, lpbfWorker } from '../server/lpbfWorkerBridge';
import { lpbfSimulationRouter } from '../routes/lpbfSimulation';

// Synthetic protocol process: exercises real pipes, timers and exits without Python/GPU work.
const protocol = `
const readline = require('node:readline');
const delay = Number(process.argv[1]);
const mode = process.argv[2];
if (mode === 'exit') process.exit(7);
let ready = false;
const send = value => console.log(JSON.stringify(value));
readline.createInterface({input: process.stdin}).on('line', line => {
  const request = JSON.parse(line);
  if (request.method === 'capabilities' && !ready) {
    if (mode === 'never-ready') return;
    setTimeout(() => { ready = true; send({id:request.id,data:{ready:true,pid:process.pid}}); }, delay);
    return;
  }
  if (mode === 'stuck') return;
  if (!ready) return send({id:request.id,error:'request sent before readiness'});
  if (request.method === 'hang') return;
  if (request.method === 'exit') return process.exit(9);
  if (request.method === 'invalid') return send({id:request.id,error:'invalid input'});
  send({id:request.id,data:{method:request.method,payload:request.payload,pid:process.pid}});
});`;

function fixture(options: {
  delayMs?: number;
  startupTimeoutMs?: number;
  requestTimeoutMs?: number;
  command?: (fallback: boolean, launchCount: number) => { cmd: string; mode?: string };
} = {}) {
  const commands: string[] = [];
  const children: ChildProcessWithoutNullStreams[] = [];
  let markReady: () => void;
  const ready = new Promise<void>(resolve => { markReady = resolve; });
  const bridge = new LpbfWorkerBridge({
    startupTimeoutMs: options.startupTimeoutMs ?? 3000,
    requestTimeoutMs: options.requestTimeoutMs ?? 2000,
    command: fallback => {
      const command = options.command?.(fallback, commands.length) ?? { cmd: 'native-python', mode: 'normal' };
      return { cmd: command.cmd, args: [String(options.delayMs ?? 20), command.mode ?? 'normal'] };
    },
    spawn: command => {
      commands.push(command.cmd);
      const child = command.cmd === 'missing-python'
        ? spawn(path.resolve('__missing_python_readiness_fixture__.exe'), [], { stdio: 'pipe', windowsHide: true })
        : spawn(process.execPath, ['-e', protocol, ...command.args], { stdio: 'pipe', windowsHide: true });
      children.push(child);
      child.stdout.on('data', data => { if (String(data).includes('"ready":true')) markReady(); });
      return child;
    },
  });
  async function cleanup() {
    bridge.close();
    await Promise.all(children.filter(child => child.pid && child.exitCode === null && child.signalCode === null).map(async child => {
      const closed = once(child, 'close');
      child.kill();
      await closed;
    }));
  }
  return { bridge, commands, children, ready, cleanup };
}

test('the default spawn passes a command environment to the worker, else the process environment', { timeout: 10000 }, async () => {
  const echo = `require('node:readline').createInterface({input: process.stdin}).on('line', line => {
    const request = JSON.parse(line);
    console.log(JSON.stringify({id: request.id, data: {probe: process.env.LPBF_ENV_PROBE ?? null}}));
  });`;
  for (const [env, expected] of [[{ ...process.env, LPBF_ENV_PROBE: 'from-command' }, 'from-command'], [undefined, null]] as const) {
    const bridge = new LpbfWorkerBridge({ startupTimeoutMs: 5000, requestTimeoutMs: 8000,
      command: () => ({ cmd: process.execPath, args: ['-e', echo], ...(env ? { env } : {}) }) });
    try { assert.deepEqual(await bridge.request('get'), { probe: expected }); }
    finally { bridge.close(); }
  }
});

test('concurrent cold requests wait for one readiness handshake before sending RPCs', { timeout: 10000 }, async () => {
  const instance = fixture({ delayMs: 150 });
  try {
    const results = await Promise.all(['get', 'estimate', 'submit'].map(method => instance.bridge.request(method, { selected: true }))) as any[];
    assert.deepEqual(instance.commands, ['native-python']);
    assert.deepEqual(results.map(result => result.method), ['get', 'estimate', 'submit']);
    assert.equal(new Set(results.map(result => result.pid)).size, 1);
  } finally { await instance.cleanup(); }
});

test('slow readiness returns recoverable HTTP503 and later uses the same healthy process', { timeout: 10000 }, async t => {
  const instance = fixture({ delayMs: 250, requestTimeoutMs: 60 });
  t.mock.method(lpbfWorker, 'request', instance.bridge.request.bind(instance.bridge));
  const app = express(); app.use(lpbfSimulationRouter);
  const server = app.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const address = server.address() as { port: number };
  try {
    const initial = await fetch(`http://127.0.0.1:${address.port}/api/lpbf/jobs/example`);
    assert.equal(initial.status, 503);
    assert.equal(initial.headers.get('retry-after'), '1');
    assert.equal((await initial.json()).code, 'LPBF_WORKER_STARTING');
    assert.equal(instance.children[0].killed, false, 'caller deadline must not kill a healthy startup');
    await instance.ready;
    const recovered = await fetch(`http://127.0.0.1:${address.port}/api/lpbf/jobs/example`);
    assert.equal(recovered.status, 200);
    assert.equal((await recovered.json()).method, 'get');
    assert.deepEqual(instance.commands, ['native-python']);
  } finally {
    server.closeAllConnections();
    await new Promise<void>(resolve => server.close(() => resolve()));
    await instance.cleanup();
  }
});

test('explicit native startup exit rejects all waiters without retrying the same command', { timeout: 10000 }, async () => {
  const instance = fixture({ command: () => ({ cmd: 'native-python', mode: 'exit' }) });
  try {
    const results = await Promise.allSettled([instance.bridge.request('get'), instance.bridge.request('estimate')]);
    for (const result of results) {
      assert.equal(result.status, 'rejected');
      if (result.status === 'rejected') {
        assert.ok(result.reason instanceof LpbfWorkerUnavailableError);
        assert.match(result.reason.message, /exited \(7\)/);
      }
    }
    assert.deepEqual(instance.commands, ['native-python']);
  } finally { await instance.cleanup(); }
});

test('failed native spawn is reported without duplicate launch or retained pending request', { timeout: 10000 }, async () => {
  const instance = fixture({ command: (_fallback, launches) => ({ cmd: launches === 0 ? 'missing-python' : 'native-python' }) });
  try {
    await assert.rejects(instance.bridge.request('get'), error => error instanceof LpbfWorkerUnavailableError && /ENOENT/.test(error.message));
    assert.deepEqual(instance.commands, ['missing-python']);
    assert.equal((await instance.bridge.request('get') as any).method, 'get');
    assert.deepEqual(instance.commands, ['missing-python', 'native-python']);
  } finally { await instance.cleanup(); }
});

test('a failed actual WSL command falls back once to the host command', { timeout: 10000 }, async () => {
  const instance = fixture({ command: fallback => fallback
    ? { cmd: 'native-python' } : { cmd: 'wsl.exe', mode: 'exit' } });
  try {
    assert.equal((await instance.bridge.request('get') as any).method, 'get');
    assert.deepEqual(instance.commands, ['wsl.exe', 'native-python']);
    assert.equal(instance.children[0].exitCode, 7);
  } finally { await instance.cleanup(); }
});

test('bounded background readiness failure can be retried by a later caller', { timeout: 10000 }, async () => {
  // The startup bound applies to every launch. The never-ready launch is rejected by it at any value, but the
  // retry launch is a cold Node start whose handshake must also finish inside it: with 500 ms it failed under
  // full-suite load with "LPBF worker RPC timeout" from the startup capabilities RPC. Use the fixture's cold-start
  // bound (3000 ms) and keep the caller deadline above it, so the first caller observes the bounded startup
  // failure itself rather than its own deadline ("still starting").
  const instance = fixture({ startupTimeoutMs: 3000, requestTimeoutMs: 6000, command: (_fallback, launches) => ({
    cmd: 'native-python', mode: launches === 0 ? 'never-ready' : 'normal',
  }) });
  try {
    await assert.rejects(instance.bridge.request('get'), error => error instanceof LpbfWorkerUnavailableError && /timeout/.test(error.message));
    assert.equal(instance.children[0].killed, true);
    assert.equal((await instance.bridge.request('get') as any).method, 'get');
    assert.deepEqual(instance.commands, ['native-python', 'native-python']);
  } finally { await instance.cleanup(); }
});

test('exit after readiness rejects pending RPCs and a subsequent request starts a new process', { timeout: 10000 }, async () => {
  const instance = fixture();
  try {
    await instance.bridge.request('get');
    const results = await Promise.allSettled([instance.bridge.request('hang'), instance.bridge.request('exit')]);
    assert.ok(results.every(result => result.status === 'rejected' && result.reason instanceof LpbfWorkerUnavailableError));
    assert.equal((await instance.bridge.request('get') as any).method, 'get');
    assert.equal(instance.commands.length, 2);
  } finally { await instance.cleanup(); }
});

test('closing during WSL readiness does not launch an unsolicited fallback', { timeout: 10000 }, async () => {
  const instance = fixture({ delayMs: 200, command: () => ({ cmd: 'wsl.exe' }) });
  const pending = instance.bridge.request('get');
  instance.bridge.close();
  try {
    await assert.rejects(pending, /closed/);
    assert.deepEqual(instance.commands, ['wsl.exe']);
  } finally { await instance.cleanup(); }
});

test('stdin EPIPE becomes a recoverable HTTP503, kills the unhealthy child, and waits before restart', { timeout: 10000 }, async t => {
  const instance = fixture({ command: (_fallback, launches) => ({ cmd: 'native-python', mode: launches === 0 ? 'stuck' : 'normal' }) });
  t.mock.method(lpbfWorker, 'request', instance.bridge.request.bind(instance.bridge));
  const app = express(); app.use(lpbfSimulationRouter);
  const server = app.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const address = server.address() as { port: number };
  const pending = instance.bridge.request('hang');
  void pending.catch(() => {});
  await instance.ready;
  try {
    const responsePromise = fetch(`http://127.0.0.1:${address.port}/api/lpbf/jobs/example`);
    const child = instance.children[0];
    const originalWrite = child.stdin.write.bind(child.stdin);
    let requestSent!: () => void;
    const sent = new Promise<void>(resolve => { requestSent = resolve; });
    child.stdin.write = ((chunk: any, ...args: any[]) => {
      if (String(chunk).includes('"method":"get"')) {
        requestSent();
        const callback = args.find(argument => typeof argument === 'function');
        queueMicrotask(() => callback?.(Object.assign(new Error('fixture EPIPE'), { code: 'EPIPE' })));
        return false;
      }
      return (originalWrite as any)(chunk, ...args);
    }) as typeof child.stdin.write;
    await sent;
    const response = await responsePromise;
    assert.equal(response.status, 503);
    assert.equal(response.headers.get('retry-after'), '1');
    assert.equal((await response.json()).code, 'LPBF_WORKER_UNAVAILABLE');
    await assert.rejects(pending, error => error instanceof LpbfWorkerUnavailableError);
    assert.equal(child.killed, true);
    const recovered = await instance.bridge.request('get') as any;
    assert.equal(recovered.method, 'get');
    assert.equal(instance.commands.length, 2);
  } finally {
    server.closeAllConnections();
    await new Promise<void>(resolve => server.close(() => resolve()));
    await instance.cleanup();
  }
});

test('a request invalidated by close cannot be sent to the replacement worker', { timeout: 10000 }, async () => {
  const instance = fixture({ delayMs: 100 });
  try {
    const stale = instance.bridge.request('old-request');
    instance.bridge.close();
    const fresh = instance.bridge.request('new-request');
    await assert.rejects(stale, /closed|invalidated/);
    assert.equal((await fresh as any).method, 'new-request');
    assert.equal(instance.commands.length, 2);
  } finally { await instance.cleanup(); }
});

test('a retry waits for terminal child exit and close invalidates waiters before replacement launch', { timeout: 10000 }, async () => {
  const instance = fixture({ requestTimeoutMs: 1000 });
  let restoreKill = () => {};
  let killRequested = false;
  try {
    await instance.bridge.request('get');
    const child = instance.children[0];
    const kill = child.kill.bind(child);
    child.kill = (() => { killRequested = true; return true; }) as typeof child.kill;
    restoreKill = () => { child.kill = kill as typeof child.kill; };
    child.stdin.emit('error', Object.assign(new Error('fixture EPIPE'), { code: 'EPIPE' }));

    await assert.rejects(instance.bridge.request('get'), error =>
      error instanceof LpbfWorkerUnavailableError && error.code === 'LPBF_WORKER_STARTING');
    assert.deepEqual(instance.commands, ['native-python'], 'do not launch while the old child has not exited');
    assert.equal(killRequested, true);

    const stale = instance.bridge.request('old-request');
    instance.bridge.close();
    instance.bridge.close();
    restoreKill();
    const closed = once(child, 'close');
    kill();
    await closed;
    await assert.rejects(stale, /closed|invalidated/);
    assert.deepEqual(instance.commands, ['native-python'], 'invalidated waiter must not launch a replacement');

    assert.equal((await instance.bridge.request('get') as any).method, 'get');
    assert.equal(instance.commands.length, 2);
  } finally {
    restoreKill();
    await instance.cleanup();
  }
});
