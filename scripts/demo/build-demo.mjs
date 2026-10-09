// Builds the static GitHub Pages demo into dist-demo/ (docs/DEMO_STATIC_DESIGN.md sections 2 and 8).
// Snapshots live in demo/snapshots/ (outside public/, so a normal build never copies them) and are
// copied into dist-demo/demo-snapshots/ here and nowhere else.
import { spawnSync } from 'node:child_process';
import { cpSync, existsSync, rmSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const viteBin = path.join(root, 'node_modules', 'vite', 'bin', 'vite.js');
const outDir = path.join(root, 'dist-demo');
const snapshots = path.join(root, 'demo', 'snapshots');

const result = spawnSync(process.execPath, [viteBin, 'build', '--mode', 'demo'], {
  cwd: root,
  stdio: 'inherit',
  env: { ...process.env, VITE_STATIC_DEMO: '1', VITE_BASE_PATH: process.env.VITE_BASE_PATH || '/metalliksa/' },
});
if (result.status !== 0) process.exit(result.status ?? 1);

const target = path.join(outDir, 'demo-snapshots');
rmSync(target, { recursive: true, force: true });
if (existsSync(snapshots)) {
  cpSync(snapshots, target, { recursive: true });
  console.log('Copied demo/snapshots to dist-demo/demo-snapshots');
} else {
  console.warn('demo/snapshots does not exist: dist-demo has no snapshots (every API call will report "Not available in the static demo.").');
}
