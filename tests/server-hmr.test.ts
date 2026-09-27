import assert from 'node:assert/strict';
import { once } from 'node:events';
import { createServer, type Server } from 'node:http';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import express from 'express';
import { attachDevelopmentMiddleware } from '../server/devMiddleware';

type DevelopmentServer = Awaited<ReturnType<typeof attachDevelopmentMiddleware>>;

async function withFixture(run: () => Promise<void>) {
  const previousDirectory = process.cwd();
  const root = await mkdtemp(path.join(tmpdir(), 'metalliksa-hmr-'));
  try {
    await writeFile(path.join(root, 'index.html'), '<!doctype html><title>HMR integration fixture</title>');
    // Avoid scanning the live application's imports and sharing its optimizer cache.
    process.chdir(root);
    await run();
  } finally {
    process.chdir(previousDirectory);
    assert.equal(path.dirname(root), path.resolve(tmpdir()));
    assert.ok(path.basename(root).startsWith('metalliksa-hmr-'));
    // Windows can release closed watcher handles just after Vite.close resolves.
    await rm(root, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 });
  }
}

async function startInstance() {
  const app = express();
  app.get('/health', (_req, res) => res.json({ ok: true }));
  const http = createServer(app);
  const vite = await attachDevelopmentMiddleware(app, http);
  try {
    http.listen(0, '127.0.0.1');
    await once(http, 'listening');
    const address = http.address();
    assert.ok(address && typeof address !== 'string');
    return { http, vite, port: address.port };
  } catch (error) {
    await closeInstance({ http, vite });
    throw error;
  }
}

async function closeInstance(instance: { http: Server; vite: DevelopmentServer }) {
  await instance.vite.close();
  if (instance.http.listening) {
    await new Promise<void>((resolve, reject) => instance.http.close(error => error ? reject(error) : resolve()));
  }
}

function nextMessage(socket: WebSocket): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('HMR message timed out')), 5000);
    socket.addEventListener('message', event => {
      clearTimeout(timer);
      resolve(JSON.parse(String(event.data)));
    }, { once: true });
    socket.addEventListener('error', () => {
      clearTimeout(timer);
      reject(new Error('HMR websocket failed'));
    }, { once: true });
  });
}

test('two development instances serve HMR on their own HTTP ports', { timeout: 20000 }, async () => withFixture(async () => {
  const previous = process.env.DISABLE_HMR;
  delete process.env.DISABLE_HMR;
  const instances: Awaited<ReturnType<typeof startInstance>>[] = [];
  const sockets: WebSocket[] = [];
  try {
    instances.push(await startInstance());
    instances.push(await startInstance());
    assert.notEqual(instances[0].port, instances[1].port);
    for (const instance of instances) {
      assert.ok(instance.http.listenerCount('upgrade') > 0, 'HMR must attach to the application HTTP server');
      assert.deepEqual(await (await fetch(`http://127.0.0.1:${instance.port}/health`)).json(), { ok: true });
      const socket = new WebSocket(`ws://127.0.0.1:${instance.port}/`, 'vite-hmr');
      sockets.push(socket);
      assert.deepEqual(await nextMessage(socket), { type: 'connected' });
    }
    // A broadcast from each instance must reach only its corresponding socket.
    const messages = sockets.map(nextMessage);
    instances.forEach((instance, index) => instance.vite.ws.send({
      type: 'custom', event: 'hmr-isolation-probe', data: index,
    }));
    assert.deepEqual(await Promise.all(messages), [0, 1].map(data => ({
      type: 'custom', event: 'hmr-isolation-probe', data,
    })));
  } finally {
    for (const socket of sockets) socket.close();
    for (const instance of instances) await closeInstance(instance);
    if (previous === undefined) delete process.env.DISABLE_HMR;
    else process.env.DISABLE_HMR = previous;
  }
}));

test('DISABLE_HMR keeps the HTTP server free of websocket upgrade handlers', { timeout: 20000 }, async () => withFixture(async () => {
  const previous = process.env.DISABLE_HMR;
  process.env.DISABLE_HMR = 'true';
  let instance: Awaited<ReturnType<typeof startInstance>> | undefined;
  try {
    instance = await startInstance();
    assert.equal(instance.vite.config.server.hmr, false);
    assert.equal(instance.vite.config.server.ws, false);
    assert.equal(instance.http.listenerCount('upgrade'), 0);
    assert.deepEqual(await (await fetch(`http://127.0.0.1:${instance.port}/health`)).json(), { ok: true });
  } finally {
    if (instance) await closeInstance(instance);
    if (previous === undefined) delete process.env.DISABLE_HMR;
    else process.env.DISABLE_HMR = previous;
  }
}));
