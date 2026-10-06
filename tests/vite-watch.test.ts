import assert from 'node:assert/strict';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { test } from 'node:test';
import { createServer } from 'vite';

test('Vite watches application edits without reacting to generated LPBF evidence', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'metalliksa-vite-watch-'));
  const source = path.join(root, 'src/probe.ts');
  const generated = [
    'graft/probe.md',
    '.tmp-lpbf-ui-accept/probe.json',
    '.lpbf-runs/probe.json',
    '.warp-cache/probe.bin',
    'docs/probe.partial.json',
  ].map(file => path.join(root, file));
  const oldDisableHmr = process.env.DISABLE_HMR;
  delete process.env.DISABLE_HMR;
  let server: Awaited<ReturnType<typeof createServer>> | undefined;
  try {
    for (const file of [source, ...generated]) {
      await mkdir(path.dirname(file), { recursive: true });
      await writeFile(file, 'initial');
    }
    server = await createServer({
      configFile: path.resolve('vite.config.ts'),
      root,
      logLevel: 'silent',
      server: { middlewareMode: true, hmr: false },
    });
    const watchedSource = () => Object.entries(server!.watcher.getWatched()).some(
      ([directory, names]) => path.resolve(directory) === path.dirname(source) && names.includes('probe.ts'),
    );
    const readyDeadline = Date.now() + 5000;
    while (!watchedSource() && Date.now() < readyDeadline) await delay(25);
    assert.ok(watchedSource(), 'application source watcher must become ready');

    const changes: string[] = [];
    server.watcher.on('change', file => changes.push(path.resolve(file)));
    for (const file of [...generated, source]) await writeFile(file, 'updated');
    const eventDeadline = Date.now() + 5000;
    while (!changes.includes(source) && Date.now() < eventDeadline) await delay(25);
    assert.ok(changes.includes(source), 'real application edits must remain watched');
    await delay(200);
    assert.deepEqual(changes.filter(file => generated.includes(file)), [],
      'generated graph, run, cache and partial-report writes must not trigger reload work');
  } finally {
    await server?.close();
    if (oldDisableHmr === undefined) delete process.env.DISABLE_HMR;
    else process.env.DISABLE_HMR = oldDisableHmr;
    // Only remove this test-created directory, never a caller-supplied path.
    assert.equal(path.dirname(root), path.resolve(tmpdir()));
    assert.ok(path.basename(root).startsWith('metalliksa-vite-watch-'));
    await rm(root, { recursive: true, force: true });
  }
});
