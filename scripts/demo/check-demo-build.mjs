// Checks a finished demo build (docs/DEMO_STATIC_DESIGN.md sections 7, 8 and 9). Run after `npm run build:demo`.
// Usage: node scripts/demo/check-demo-build.mjs [--out dist-demo] [--base /metalliksa/] [--normal dist]
// Exit code 1 on any failure. Prints every failed check, not only the first.
import { createHash } from 'node:crypto';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const args = process.argv.slice(2);
const opt = (name, fallback) => { const i = args.indexOf(name); return i >= 0 && args[i + 1] ? args[i + 1] : fallback; };
const outDir = path.resolve(root, opt('--out', 'dist-demo'));
const normalDir = path.resolve(root, opt('--normal', 'dist'));
const base = opt('--base', process.env.VITE_BASE_PATH || '/metalliksa/');
const snapshotSrc = path.join(root, 'demo', 'snapshots');

const GZIP_BUDGET = 12 * 1024 * 1024; // excluding vendor-* chunks, which scripts/bundle-budgets.json already budgets
const BANNER_PARTS = ['Static snapshot of version', 'computed offline. Not live solver output.'];
const ROOT_ABSOLUTE = ['demo-snapshots', 'images', 'stls', 'icon\\.svg', 'manifest\\.json'];

const failures = [];
const fail = (msg) => failures.push(msg);
const ok = (msg) => console.log(`ok   ${msg}`);

function walk(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) out.push(...walk(full)); else out.push(full);
  }
  return out;
}
const rel = (file, from) => path.relative(from, file).split(path.sep).join('/');
const isText = (file) => /\.(html|js|css|json|svg|mjs)$/.test(file);

if (!existsSync(outDir)) {
  console.error(`FAIL ${rel(outDir, root)} does not exist. Run npm run build:demo first.`);
  process.exit(1);
}
const files = walk(outDir);

// 1. index.html under the base path.
const indexPath = path.join(outDir, 'index.html');
if (!existsSync(indexPath)) fail('index.html missing');
else {
  const html = readFileSync(indexPath, 'utf8');
  const refs = [...html.matchAll(/(?:src|href)="([^"]+)"/g)].map((m) => m[1]).filter((u) => u.startsWith('/'));
  const bad = refs.filter((u) => !u.startsWith(base));
  if (refs.length === 0) fail('index.html has no asset references');
  else if (bad.length) fail(`index.html has root-absolute URLs outside the base ${base}: ${bad.join(', ')}`);
  else ok(`index.html asset URLs all start with ${base} (${refs.length})`);
}

// 2. No root-absolute runtime paths in the output (section 8).
const rootAbs = new RegExp('["\'`]/(?:' + ROOT_ABSOLUTE.join('|') + ')');
const hits = [];
for (const file of files.filter(isText)) {
  if (rel(file, outDir).startsWith('demo-snapshots/')) continue; // recorded response bodies are data
  const m = readFileSync(file, 'utf8').match(rootAbs);
  if (m) hits.push(`${rel(file, outDir)} (${m[0]})`);
}
if (hits.length) fail(`root-absolute asset paths in the build: ${hits.join('; ')}`);
else ok('no root-absolute /demo-snapshots, /images, /stls, /icon.svg or /manifest.json paths');

// 3. manifest.json start_url, scope and icons follow the base.
const manifestPath = path.join(outDir, 'manifest.json');
if (existsSync(manifestPath)) {
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  const urls = [manifest.start_url, manifest.scope, ...(manifest.icons ?? []).map((i) => i.src)].filter(Boolean);
  const bad = urls.filter((u) => u.startsWith('/') && !u.startsWith(base));
  if (bad.length) fail(`manifest.json URLs outside the base: ${bad.join(', ')}`); else ok('manifest.json URLs follow the base');
}

// 4. Banner string is in the bundle.
const jsText = files.filter((f) => f.endsWith('.js')).map((f) => readFileSync(f, 'utf8')).join('\n');
const missingBanner = BANNER_PARTS.filter((p) => !jsText.includes(p));
if (missingBanner.length) fail(`banner text missing from the JS bundle: ${missingBanner.join(' | ')}`); else ok('banner text present');

// 5. Network literals: the app may only call same-origin /api/ (served by demoFetch) and static files.
//    The app chunks call /api/ in many services, so a literal "/api/" cannot be forbidden; what is forbidden is any
//    absolute localhost or API-host URL and any WebSocket or EventSource.
const netHits = [];
for (const file of files.filter((f) => f.endsWith('.js'))) {
  const name = rel(file, outDir);
  if (/(^|\/)vendor-/.test(name)) continue;
  const text = readFileSync(file, 'utf8');
  for (const m of text.matchAll(/https?:\/\/(?:localhost|127\.0\.0\.1|\[::1\]|[a-z0-9.-]*api[a-z0-9.-]*)[^"'`\s)]*/gi)) netHits.push(`${name}: ${m[0]}`);
  if (/new\s+WebSocket\(|new\s+EventSource\(/.test(text)) netHits.push(`${name}: WebSocket or EventSource`);
}
if (netHits.length) fail(`external or local network literals in app chunks: ${netHits.slice(0, 8).join('; ')}`);
else ok('no localhost, API host, WebSocket or EventSource literals in app chunks');

// 6. The demo fetch seam is in the bundle (its miss error kind is unique to it).
if (!jsText.includes('demo-snapshot-missing')) fail('demoFetch (demo-snapshot-missing) not found in the demo bundle'); else ok('demoFetch present');

// 7. Snapshot manifest hashes match what was copied.
const snapDir = path.join(outDir, 'demo-snapshots');
const manifestFile = path.join(snapDir, 'manifest.json');
if (!existsSync(manifestFile)) fail('demo-snapshots/manifest.json missing from the build');
else {
  const man = JSON.parse(readFileSync(manifestFile, 'utf8'));
  const listed = Object.keys(man.files ?? {});
  let bad = 0;
  for (const name of listed) {
    const p = path.join(snapDir, name);
    if (!existsSync(p)) { fail(`snapshot ${name} listed but not copied`); bad++; continue; }
    const buf = readFileSync(p);
    if (createHash('sha256').update(buf).digest('hex') !== man.files[name].sha256) { fail(`snapshot ${name} sha256 does not match the manifest`); bad++; }
    else if (buf.length !== man.files[name].bytes) { fail(`snapshot ${name} byte size does not match the manifest`); bad++; }
  }
  const onDisk = readdirSync(snapDir).filter((n) => n !== 'manifest.json' && n !== 'index.json');
  const extra = onDisk.filter((n) => !listed.includes(n));
  if (extra.length) fail(`snapshot files not in the manifest: ${extra.join(', ')}`);
  if (!existsSync(path.join(snapDir, 'index.json'))) fail('demo-snapshots/index.json missing');
  const srcManifest = path.join(snapshotSrc, 'manifest.json');
  if (existsSync(srcManifest) && readFileSync(srcManifest, 'utf8') !== readFileSync(manifestFile, 'utf8')) fail('copied manifest differs from demo/snapshots/manifest.json');
  if (!bad && !extra.length) ok(`snapshot manifest hashes match (${listed.length} files)`);
}

// 8. Size budget: gzip of everything except vendor-* chunks.
let gz = 0;
for (const file of files) {
  if (/(^|\/)vendor-/.test(rel(file, outDir))) continue;
  gz += gzipSync(readFileSync(file)).length;
}
if (gz > GZIP_BUDGET) fail(`dist-demo gzip ${gz} bytes exceeds ${GZIP_BUDGET} (excluding vendor-*)`);
else ok(`dist-demo gzip ${(gz / 1024).toFixed(0)} KiB within ${(GZIP_BUDGET / 1024 / 1024).toFixed(0)} MiB (excluding vendor-*)`);

// 9. The normal build, if present, carries no demo snapshots or demo code.
if (existsSync(normalDir) && normalDir !== outDir) {
  const normal = walk(normalDir);
  const snap = normal.filter((f) => rel(f, normalDir).includes('demo-snapshots'));
  if (snap.length) fail(`normal build contains demo-snapshots paths: ${snap.map((f) => rel(f, normalDir)).slice(0, 5).join(', ')}`);
  const leaked = normal.filter((f) => f.endsWith('.js') && readFileSync(f, 'utf8').includes('demo-snapshot-missing'));
  if (leaked.length) fail(`normal build contains demo code: ${leaked.map((f) => rel(f, normalDir)).join(', ')}`);
  if (!snap.length && !leaked.length) ok(`${rel(normalDir, root)}/ has no demo-snapshots path and no demo code`);
} else {
  console.log(`skip ${rel(normalDir, root)}/ not present, normal-build isolation not checked here`);
}

if (failures.length) {
  console.error(`\n${failures.length} check(s) failed:`);
  for (const f of failures) console.error(`FAIL ${f}`);
  process.exit(1);
}
console.log('\nAll demo build checks passed.');
