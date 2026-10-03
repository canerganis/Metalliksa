// Gzip bundle size ratchet check. Usage: node scripts/check-bundle-size.mjs [distDir]
//
// scripts/bundle-budgets.json maps an asset-name pattern to
//   { "baseline": <KB gzip>, "target": <KB gzip | null> }
// - baseline: the ratchet. The script FAILS when an asset exceeds it. Lower it
//   whenever a build gets smaller; never raise it without a reason.
// - target: the aspirational budget. It is printed next to the baseline and
//   reported as "over target" but never fails the check.
// The first matching rule wins (".css" rules first, then specific names, then "*").
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import {fileURLToPath} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const distDir = path.resolve(process.argv[2] ?? path.join(here, '..', 'dist'));
const assetsDir = path.join(distDir, 'assets');
const budgets = JSON.parse(fs.readFileSync(path.join(here, 'bundle-budgets.json'), 'utf8'));

if (!fs.existsSync(assetsDir)) {
  console.error(`No assets directory at ${assetsDir}. Run "vite build" first.`);
  process.exit(1);
}

const globToRegExp = (glob) =>
  new RegExp('^' + glob.split('*').map((p) => p.replace(/[.+?^${}()|[\]\\]/g, '\\$&')).join('.*') + '$');
const rules = Object.entries(budgets)
  .filter(([pattern]) => !pattern.startsWith('_'))
  .map(([pattern, spec]) => ({pattern, baseline: spec.baseline, target: spec.target ?? null, re: globToRegExp(pattern)}));

const ordered = [
  ...rules.filter((r) => r.pattern.endsWith('.css')),
  ...rules.filter((r) => !r.pattern.endsWith('.css') && r.pattern !== '*'),
  ...rules.filter((r) => r.pattern === '*'),
];

const files = fs.readdirSync(assetsDir).filter((f) => /\.(js|css)$/.test(f));
const rows = files.map((file) => {
  const buf = fs.readFileSync(path.join(assetsDir, file));
  const gzipKb = zlib.gzipSync(buf, {level: 9}).length / 1024;
  const stem = file.replace(/\.(js|css)$/, '');
  const rule = ordered.find((r) => r.re.test(file) || (r.pattern.endsWith('-*') && r.re.test(stem)));
  return {file, rawKb: buf.length / 1024, gzipKb, baseline: rule?.baseline, target: rule?.target ?? null};
}).sort((a, b) => b.gzipKb - a.gzipKb);

const pad = (s, n) => String(s).padEnd(n);
console.log(`${pad('file', 44)}${pad('raw KB', 10)}${pad('gzip KB', 10)}${pad('baseline', 10)}${pad('target', 8)}status`);
let failed = 0;
let overTarget = 0;
for (const r of rows) {
  const overBaseline = r.baseline !== undefined && r.gzipKb > r.baseline;
  const missTarget = r.target !== null && r.gzipKb > r.target;
  if (overBaseline) failed++;
  if (missTarget) overTarget++;
  const status = overBaseline ? 'FAIL' : missTarget ? 'ok (over target)' : 'ok';
  console.log(`${pad(r.file, 44)}${pad(r.rawKb.toFixed(1), 10)}${pad(r.gzipKb.toFixed(1), 10)}${pad(r.baseline ?? '-', 10)}${pad(r.target ?? '-', 8)}${status}`);
}
if (overTarget) console.log(`\n${overTarget} asset(s) are above their aspirational target (informational only).`);
if (failed) {
  console.error(`\n${failed} asset(s) exceed their gzip baseline.`);
  process.exit(1);
}
console.log('\nAll assets within baseline.');
