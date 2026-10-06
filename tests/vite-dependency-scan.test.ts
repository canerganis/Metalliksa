import assert from 'node:assert/strict';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { optimizeDeps, resolveConfig } from 'vite';

test('dependency scanning follows application imports without crawling unrelated HTML documents', { timeout: 20000 }, async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'metalliksa-vite-deps-'));
  const files: Record<string, string> = {
    'index.html': '<script type="module" src="/src/main.js"></script>',
    'src/main.js': 'import { value } from "application-scan-probe"; console.log(value);',
    'node_modules/application-scan-probe/package.json': JSON.stringify({
      name: 'application-scan-probe', version: '1.0.0', type: 'module', exports: './index.js',
    }),
    'node_modules/application-scan-probe/index.js': 'export const value = 42;',
    'spparks/doc/unrelated.html': '<script type="module">import "missing-doc-only-dependency";</script>',
    'tests/unrelated.html': '<script type="module">import "missing-test-only-dependency";</script>',
  };
  try {
    for (const [relative, content] of Object.entries(files)) {
      const file = path.join(root, relative);
      await mkdir(path.dirname(file), { recursive: true });
      await writeFile(file, content);
    }
    const config = await resolveConfig({
      configFile: path.resolve('vite.config.ts'),
      root,
      cacheDir: path.join(root, '.vite'),
      logLevel: 'silent',
    }, 'serve');
    const result = await optimizeDeps(config, true, true);
    assert.ok(result.optimized['application-scan-probe'], 'real application dependencies must still be scanned and optimized');
    assert.equal(result.optimized['missing-doc-only-dependency'], undefined);
    assert.equal(result.optimized['missing-test-only-dependency'], undefined);
  } finally {
    assert.equal(path.dirname(root), path.resolve(tmpdir()));
    assert.ok(path.basename(root).startsWith('metalliksa-vite-deps-'));
    await rm(root, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 });
  }
});
