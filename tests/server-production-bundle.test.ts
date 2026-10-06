/**
 * Regression guard for the documented production launch path (`npm run build` then `npm start`,
 * i.e. `node dist/server.cjs`). esbuild's --format=cjs output replaces import.meta with an empty
 * object, so a server module that calls fileURLToPath(import.meta.url) at load time crashed the
 * bundle before it could listen, while the tsx dev server (ESM) worked. This test bundles server.ts
 * with the esbuild flags read from package.json's build script, starts the bundle on a free loopback
 * port and requires /api/health and the SPA fallback to answer.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn, spawnSync, type ChildProcess } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { build, type BuildOptions } from 'esbuild';
import { resolvePythonRoot, startupLayoutError } from '../server/pythonRoot.ts';
import { getHostPython } from '../server/pythonRuntime.ts';

const repoRoot = fileURLToPath(new URL('..', import.meta.url));

/** The esbuild half of `npm run build`, translated flag by flag. Unknown flags fail loudly. */
function serverBundleOptions(outfile: string): BuildOptions {
  const script: string = JSON.parse(readFileSync(path.join(repoRoot, 'package.json'), 'utf8')).scripts.build;
  const match = /(?:^|&&)\s*esbuild\s+([^&]+)$/.exec(script);
  assert.ok(match, `package.json build script has no trailing esbuild command: ${script}`);
  const [entry, ...flags] = match[1].trim().split(/\s+/);
  assert.equal(entry, 'server.ts');
  const options: BuildOptions = { entryPoints: [path.join(repoRoot, entry)], absWorkingDir: repoRoot, logLevel: 'silent', outfile };
  let scriptOutfile: string | undefined;
  for (const flag of flags) {
    const [name, value] = flag.split('=');
    if (name === '--bundle') options.bundle = true;
    else if (name === '--platform') options.platform = value as BuildOptions['platform'];
    else if (name === '--format') options.format = value as BuildOptions['format'];
    else if (name === '--packages') options.packages = value as BuildOptions['packages'];
    else if (name === '--sourcemap' && value === undefined) options.sourcemap = true;
    else if (name === '--outfile') scriptOutfile = value;
    else throw new Error(`Unhandled esbuild flag '${flag}' in the build script; extend tests/server-production-bundle.test.ts.`);
  }
  assert.equal(scriptOutfile, 'dist/server.cjs');
  assert.equal(options.format, 'cjs');
  return options;
}

function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address() as net.AddressInfo;
      server.close(() => resolve(port));
    });
  });
}

/** Kill the server and anything it spawned (the Python supervisor starts a worker at load). */
function killTree(child: ChildProcess): Promise<void> {
  if (child.exitCode !== null || child.signalCode !== null || child.pid === undefined) return Promise.resolve();
  const exited = new Promise<void>((resolve) => child.once('exit', () => resolve()));
  if (process.platform === 'win32') {
    spawnSync('taskkill', ['/pid', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' });
  } else {
    try { process.kill(-child.pid, 'SIGKILL'); } catch { child.kill('SIGKILL'); }
  }
  // The server handles SIGTERM itself, so only a hard kill is used; never wait forever.
  return Promise.race([exited, new Promise<void>((resolve) => setTimeout(resolve, 5000).unref())]);
}

test('startupLayoutError requires python/persistent_ipc_service.py, and dist/index.html in production', () => {
  const app = path.resolve(os.tmpdir(), 'metalliksa-app');
  const ipc = path.join(app, 'python', 'persistent_ipc_service.py');
  const index = path.join(app, 'dist', 'index.html');
  const has = (...files: string[]) => (file: string) => files.includes(file);
  assert.equal(startupLayoutError(app, true, has(ipc, index)), null);
  assert.equal(startupLayoutError(app, false, has(ipc)), null);
  const prod = startupLayoutError(app, true, has(ipc));
  assert.match(prod ?? '', /application root/);
  assert.ok(prod?.includes(index) && !prod.includes(ipc), prod ?? '');
  const dev = startupLayoutError(app, false, has());
  assert.ok(dev?.includes(ipc) && !dev.includes(index), dev ?? '');
  assert.equal(startupLayoutError(repoRoot, false), null);
});

test('the production bundle exits with a clear message, before starting Python, outside an application root', { timeout: 60_000 }, async () => {
  const work = mkdtempSync(path.join(os.tmpdir(), 'metalliksa-prod-layout-'));
  try {
    const outfile = path.join(work, 'bundle', 'server.cjs');
    await build(serverBundleOptions(outfile));
    const app = path.join(work, 'app');
    mkdirSync(app);
    const env: NodeJS.ProcessEnv = { ...process.env, NODE_ENV: 'production', NODE_PATH: path.join(repoRoot, 'node_modules'),
      PORT: String(await freePort()), METALLIKSA_HOST: '127.0.0.1' };
    const run = spawnSync(process.execPath, [outfile], { cwd: app, env, encoding: 'utf8', timeout: 30_000, windowsHide: true });
    assert.equal(run.status, 1, `${run.stdout}\n${run.stderr}`);
    assert.match(run.stderr, /Start the server from the application root/);
    assert.ok(run.stderr.includes(path.join('python', 'persistent_ipc_service.py')), run.stderr);
    assert.ok(run.stderr.includes(path.join('dist', 'index.html')), run.stderr);
    assert.doesNotMatch(run.stdout, /Python-Supervisor/);
  } finally {
    rmSync(work, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  }
});

test('resolvePythonRoot anchors python/ on the working directory', () => {
  const app = path.resolve(os.tmpdir(), 'metalliksa-app');
  assert.equal(resolvePythonRoot(app), path.join(app, 'python'));
  // Under the tsx dev server and this test runner the working directory is the repository root,
  // which is where the proxy-campaign services' Python modules live.
  assert.equal(resolvePythonRoot(), path.join(repoRoot, 'python'));
  for (const module of ['lpbf_nist_proxy_campaign.py', 'lpbf_nist_proxy_sections.py']) {
    assert.ok(existsSync(path.join(resolvePythonRoot(), module)), module);
  }
});

/** Start the bundle; `listening` resolves once it listens on `port` and rejects if it exits first. */
function startBundle(outfile: string, cwd: string, env: NodeJS.ProcessEnv, port: number) {
  const child = spawn(process.execPath, [outfile], { cwd, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'],
    detached: process.platform !== 'win32' });
  let output = '';
  child.stdout!.on('data', (chunk) => { output += chunk; });
  child.stderr!.on('data', (chunk) => { output += chunk; });
  const listening = new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`bundle did not start listening within 20 s:\n${output}`)), 20_000);
    child.stdout!.on('data', () => {
      if (output.includes(`running on http://127.0.0.1:${port}`)) { clearTimeout(timer); resolve(); }
    });
    child.once('exit', (code, signal) => {
      clearTimeout(timer);
      reject(new Error(`bundle exited during load (code=${code}, signal=${signal}):\n${output}`));
    });
  });
  return { child, listening, output: () => output };
}

test('the production server bundle (esbuild CJS, as in npm run build) loads and serves /api/health', { timeout: 90_000 }, async (t) => {
  const work = mkdtempSync(path.join(os.tmpdir(), 'metalliksa-prod-bundle-'));
  let child: ChildProcess | undefined;
  try {
    // The bundle checks run on every host, before anything that needs Python.
    const outfile = path.join(work, 'bundle', 'server.cjs');
    const result = await build(serverBundleOptions(outfile));
    const importMetaWarnings = result.warnings.filter((w) => w.text.includes('import.meta'));
    assert.deepEqual(importMetaWarnings.map((w) => `${w.location?.file}:${w.location?.line} ${w.text}`), [],
      'import.meta is empty in --format=cjs output; derive paths from process.cwd() (see server/pythonRoot.ts)');
    assert.doesNotMatch(readFileSync(outfile, 'utf8'), /\bimport_meta\d*\b/);

    // Loading the bundle needs a host Python (the Python supervisor resolves one at load). Skip only on a
    // developer host without any Python; under CI, or with an explicit but broken METALLIX_PYTHON, fail.
    let python: { cmd: string; prefix: string[] };
    try { python = getHostPython(); } catch (error) {
      const message = `no host Python (the bundled server's Python supervisor needs one at load): ${(error as Error).message}`;
      if (process.env.CI || process.env.METALLIX_PYTHON) assert.fail(message);
      t.skip(message);
      return;
    }

    // An isolated application root: dist/index.html for the SPA fallback, data roots under it, no .env,
    // and a stub python/persistent_ipc_service.py that exits at once instead of binding a port.
    const app = path.join(work, 'app');
    mkdirSync(path.join(app, 'dist'), { recursive: true });
    writeFileSync(path.join(app, 'dist', 'index.html'), '<!doctype html><title>bundle-smoke</title><div id="root"></div>');
    mkdirSync(path.join(app, 'python'));
    writeFileSync(path.join(app, 'python', 'persistent_ipc_service.py'), 'raise SystemExit(0)\n');
    const env: NodeJS.ProcessEnv = { ...process.env };
    for (const key of ['METALLIKSA_TOKEN', 'METALLIKSA_TRUST_PROXY', 'METALLIX_IPC_HOST']) delete env[key];
    Object.assign(env, {
      NODE_ENV: 'production', METALLIKSA_HOST: '127.0.0.1', AIRGAPPED: '1',
      METALLIX_IPC_SOCK: path.join(work, 'ipc.sock'),
      // --packages=external: the bundle requires express, vite, ... from the repository's node_modules.
      NODE_PATH: path.join(repoRoot, 'node_modules'),
      METALLIKSA_LPBF_SOURCE_ROOT: path.join(app, 'data', 'sources'), METALLIKSA_LPBF_RUN_ROOT: path.join(app, 'data', 'runs'),
      METALLIKSA_LPBF_BUNDLE_ROOT: path.join(app, 'data', 'bundles'), METALLIKSA_JOB_ROOT: path.join(app, 'data', 'jobs'),
      RESEARCH_REGISTRY_DIR: path.join(app, 'data', 'registry'),
    });
    // A single-executable interpreter (for example a project .venv found from the repository root)
    // is passed explicitly because the child's working directory has no .venv.
    if (python.prefix.length === 0) env.METALLIX_PYTHON = python.cmd;

    // freePort() releases its probe socket before the child binds, so another process can take the port
    // in between: retry with fresh ports when the bundle reports EADDRINUSE.
    let port = 0;
    for (let attempt = 1; ; attempt++) {
      port = await freePort();
      env.PORT = String(port);
      env.METALLIX_IPC_PORT = String(await freePort());
      const started = startBundle(outfile, app, env, port);
      child = started.child;
      try {
        await started.listening;
        break;
      } catch (error) {
        await killTree(child);
        if (attempt < 3 && /EADDRINUSE/.test(started.output())) continue;
        throw error;
      }
    }

    const health = await fetch(`http://127.0.0.1:${port}/api/health`);
    assert.equal(health.status, 200);
    const body = await health.json();
    assert.equal(body.status, 'ok');
    assert.equal(body.airgapped, true);

    const spa = await fetch(`http://127.0.0.1:${port}/some/client/route`);
    assert.equal(spa.status, 200);
    assert.match(await spa.text(), /bundle-smoke/);
  } finally {
    if (child) await killTree(child);
    rmSync(work, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  }
});
