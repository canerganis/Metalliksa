// Records the static demo snapshots from a running local engine (docs/DEMO_STATIC_DESIGN.md section 4).
//
//   npm run demo:snapshots -- [--engine http://127.0.0.1:3000] [--out demo/snapshots] [--allow-dirty]
//   npm run demo:snapshots -- --determinism      (records twice into temp dirs, fails unless the files are byte-identical)
//
// Run with tsx (the npm script does): the canonical key comes from src/demo/demoKey.ts, the same file the browser uses.
// Reads the fingerprint pin file and never writes it. Writes only under the output directory.
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { gzipSync } from 'node:zlib';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { requestKey } from '../../src/demo/demoKey.ts';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
export const BUDGET = { totalRawBytes: 6 * 1024 * 1024, totalGzipBytes: 1.5 * 1024 * 1024, fileRawBytes: 1024 * 1024 };
const EPOCH_ISO = '1970-01-01T00:00:00+00:00';

export function sortKeys(value) {
  if (Array.isArray(value)) return value.map(sortKeys);
  if (value && typeof value === 'object') {
    const out = {};
    for (const k of Object.keys(value).sort()) if (value[k] !== undefined) out[k] = sortKeys(value[k]);
    return out;
  }
  return value;
}
const stable = value => JSON.stringify(sortKeys(value)) + '\n';
const sha256 = data => createHash('sha256').update(data).digest('hex');
const fail = message => { throw new Error(message); };

/** Visits every object in a JSON tree. */
function walk(value, visit) {
  if (Array.isArray(value)) value.forEach(v => walk(v, visit));
  else if (value && typeof value === 'object') {
    visit(value);
    for (const k of Object.keys(value)) walk(value[k], visit);
  }
}

/**
 * Removes the only run-to-run differences the engine puts in a response (wall-clock durations, creation times,
 * cache bookkeeping, per-run ids) and local machine paths. Every touched field is listed in the snapshot under
 * `normalised`, so a reader sees what differs from the raw engine output. Result numbers and labels are never touched.
 */
export function normaliseResponse(kind, response) {
  const touched = new Set();
  const copy = JSON.parse(JSON.stringify(response));
  walk(copy, obj => {
    for (const k of ['computeMs', 'computeTimeMs']) if (k in obj) { obj[k] = 0; touched.add(`${k}=0`); }
    if ('originalComputeMs' in obj) { delete obj.originalComputeMs; touched.add('originalComputeMs removed'); }
  });
  if (kind === 'process-window' && copy.cache && typeof copy.cache === 'object') {
    copy.cache = { hit: false, key: copy.cache.key, scope: copy.cache.scope };
    touched.add('cache.hit=false and cache.stored removed');
  }
  if (kind === 'job') {
    const oldId = copy.id;
    // The app only accepts job ids of 32 lower case hex characters (parseSimulationJob), so the id is the cache key prefix.
    const newId = String(copy.cache_key).slice(0, 32);
    copy.created = 0; touched.add('created=0');
    copy.cacheHit = false; touched.add('cacheHit=false');
    if (copy.result?.provenance) {
      copy.result.provenance.createdAt = EPOCH_ISO; touched.add('result.provenance.createdAt=epoch');
      if ('runtime_s' in copy.result.provenance) { copy.result.provenance.runtime_s = 0; touched.add('result.provenance.runtime_s=0'); }
      const rt = copy.result.provenance.executionRuntime;
      if (rt && typeof rt === 'object') {
        if ('executable' in rt) { rt.executable = 'redacted-local-path'; touched.add('executionRuntime.executable redacted'); }
        if ('platform' in rt) { rt.platform = 'redacted-local-host'; touched.add('executionRuntime.platform redacted'); }
      }
    }
    touched.add('id=cache_key[0:32]');
    const text = JSON.stringify(copy).split(oldId).join(newId);
    return { response: JSON.parse(text), normalised: [...touched].sort(), jobId: newId };
  }
  return { response: copy, normalised: [...touched].sort() };
}

const LOCAL_PATH = /[A-Za-z]:\\\\|[A-Za-z]:\/Users|\/Users\/|\/home\/[a-z]/;
function assertSafe(label, text) {
  const hit = text.match(LOCAL_PATH);
  if (hit) fail(`${label}: response still contains a local path ("${hit[0]}"); add it to the normalisation.`);
}
/** Counts experimentalValidation fields and fails on any that is not exactly false. */
export function assertEvidence(label, response) {
  let count = 0;
  walk(response, obj => {
    if ('experimentalValidation' in obj) {
      count++;
      if (obj.experimentalValidation !== false) fail(`${label}: experimentalValidation is ${JSON.stringify(obj.experimentalValidation)}; it must be false everywhere.`);
    }
  });
  return count;
}
function findHashes(response) {
  const found = new Set();
  walk(response, obj => { if (typeof obj.implementationHash === 'string') found.add(obj.implementationHash); });
  return [...found];
}

async function postJson(engine, p, body) {
  const res = await fetch(engine + p, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const text = await res.text();
  let json; try { json = JSON.parse(text); } catch { fail(`${p}: non-JSON answer (HTTP ${res.status})`); }
  if (!res.ok) fail(`${p}: HTTP ${res.status}: ${text.slice(0, 200)}`);
  return json;
}
async function runJob(engine, p, body, timeoutMs = 180000) {
  const started = await postJson(engine, p, body);
  if (!started.id) fail(`${p}: no job id returned`);
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const res = await fetch(`${engine}${p}/${encodeURIComponent(started.id)}`);
    const job = await res.json();
    if (job.status === 'completed') return job;
    if (['failed', 'cancelled', 'timed_out'].includes(job.status)) fail(`${p}: job ${job.status}: ${job.error ?? ''}`);
    if (Date.now() > deadline) fail(`${p}: job did not finish in ${timeoutMs} ms`);
    await new Promise(r => setTimeout(r, 400));
  }
}

function gitInfo() {
  const git = args => execFileSync('git', args, { cwd: root, encoding: 'utf8' }).trim();
  return { commit: git(['rev-parse', '--short=7', 'HEAD']), dirty: git(['status', '--porcelain', '--untracked-files=no']) };
}

export async function record({ engine, outDir, allowDirty, generatedAt }) {
  const spec = JSON.parse(readFileSync(path.join(root, 'scripts/demo/demo-requests.json'), 'utf8'));
  const excluded = spec.excludedFields;
  const pkg = JSON.parse(readFileSync(path.join(root, 'package.json'), 'utf8'));
  const pin = readFileSync(path.join(root, 'python/lpbf_implementation_fingerprint.expected'), 'utf8').trim();
  const git = gitInfo();
  if (git.dirty && !allowDirty) fail(`Tracked files have uncommitted changes; commit first or pass --allow-dirty.\n${git.dirty}`);

  const records = [];
  const seenHashes = new Set();
  for (const r of spec.requests) {
    const label = `${r.method} ${r.path} (${r.label})`;
    const request = { method: r.method, path: r.path, ...(r.body !== undefined ? { body: r.body } : {}), label: r.label, group: r.group };
    if (r.source === 'fixture') {
      records.push({ key: requestKey(r.method, r.path, '', undefined, excluded), request, response: r.fixture, normalised: [], label });
    } else if (r.source === 'engine') {
      const kind = r.path.endsWith('lpbf-process-window') ? 'process-window' : 'engine';
      const raw = await postJson(engine, r.path, r.body);
      if (kind === 'process-window' && raw.success !== true) fail(`${label}: engine reported failure`);
      findHashes(raw).forEach(h => seenHashes.add(h));
      const { response, normalised } = normaliseResponse(kind, raw);
      records.push({ key: requestKey(r.method, r.path, '', r.body, excluded), request, response, normalised, label });
    } else if (r.source === 'engine-job') {
      const raw = await runJob(engine, r.path, r.body);
      findHashes(raw).forEach(h => seenHashes.add(h));
      const { response, normalised, jobId } = normaliseResponse('job', raw);
      records.push({ key: requestKey(r.method, r.path, '', r.body, excluded), request, response, normalised, label });
      const getPath = `${r.path}/${jobId}`;
      records.push({ key: requestKey('GET', getPath, '', undefined, excluded), label: `${label} final state`,
        request: { method: 'GET', path: getPath, label: `${r.label} final state`, group: r.group }, response, normalised });
    } else fail(`${label}: unknown source ${r.source}`);
  }

  // Fingerprint: every implementation hash the engine reported must equal the pin the repo checks (read only).
  if (seenHashes.size === 0) fail('The engine reported no implementation hash; cannot verify the fingerprint.');
  for (const h of seenHashes) {
    if (h !== pin) fail(`Engine implementation hash ${h.slice(0, 12)} differs from python/lpbf_implementation_fingerprint.expected (${pin.slice(0, 12)}). Not recording.`);
  }

  const entries = {}; const files = {};
  let evidenceFields = 0;
  for (const rec of records) {
    const body = stable({ request: rec.request, response: rec.response, normalised: rec.normalised,
      recordedWith: { appVersion: pkg.version, fingerprint: pin } });
    assertSafe(rec.label, body);
    evidenceFields += assertEvidence(rec.label, rec.response);
    const file = sha256(rec.key).slice(0, 16) + '.json';
    if (files[file] && files[file] !== body) fail(`${rec.label}: two different snapshots map to ${file}`);
    entries[rec.key] = file; files[file] = body;
  }

  let raw = 0, gz = 0;
  for (const [file, body] of Object.entries(files)) {
    const bytes = Buffer.byteLength(body);
    if (bytes > BUDGET.fileRawBytes) fail(`${file} is ${bytes} bytes; one file may be at most ${BUDGET.fileRawBytes}.`);
    raw += bytes; gz += gzipSync(body).length;
  }
  if (raw > BUDGET.totalRawBytes) fail(`Snapshots are ${raw} bytes raw; budget ${BUDGET.totalRawBytes}.`);
  if (gz > BUDGET.totalGzipBytes) fail(`Snapshots are ${gz} bytes gzip; budget ${BUDGET.totalGzipBytes}.`);

  // Nothing is written before every check above passed.
  mkdirSync(outDir, { recursive: true });
  const indexPath = path.join(outDir, 'index.json');
  const index = { format: 1, appVersion: pkg.version, gitCommit: git.commit, fingerprint: pin, generatedAt, entries: sortKeys(entries) };
  // A rerun that changes nothing keeps the earlier generatedAt, so the committed index stays stable.
  if (existsSync(indexPath)) {
    try {
      const old = JSON.parse(readFileSync(indexPath, 'utf8'));
      if (stable({ ...old, generatedAt: '' }) === stable({ ...index, generatedAt: '' })) index.generatedAt = old.generatedAt;
    } catch { /* unreadable old index: write a fresh one */ }
  }
  for (const f of readdirSync(outDir)) if (f.endsWith('.json')) rmSync(path.join(outDir, f));
  for (const [file, body] of Object.entries(files)) writeFileSync(path.join(outDir, file), body);
  writeFileSync(indexPath, stable(index));
  const manifestFiles = {};
  for (const name of [...Object.keys(files), 'index.json'].sort()) {
    const data = readFileSync(path.join(outDir, name));
    manifestFiles[name] = { bytes: data.length, sha256: sha256(data) };
  }
  writeFileSync(path.join(outDir, 'manifest.json'), stable({ format: 1, files: manifestFiles, totals: { snapshotFiles: Object.keys(files).length, rawBytes: raw, gzipBytes: gz } }));
  return { count: records.length, raw, gz, evidenceFields, outDir, files: Object.keys(files) };
}

function parseArgs(argv) {
  const opts = { engine: 'http://127.0.0.1:3000', out: path.join(root, 'demo', 'snapshots'), allowDirty: false, determinism: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--engine') opts.engine = argv[++i];
    else if (a === '--out') opts.out = path.resolve(argv[++i]);
    else if (a === '--allow-dirty') opts.allowDirty = true;
    else if (a === '--determinism') opts.determinism = true;
    else fail(`Unknown argument ${a}`);
  }
  opts.engine = opts.engine.replace(/\/$/, '');
  return opts;
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  const now = process.env.SOURCE_DATE_EPOCH ? new Date(Number(process.env.SOURCE_DATE_EPOCH) * 1000).toISOString() : new Date().toISOString();
  if (opts.determinism) {
    const dirs = [mkdtempSync(path.join(os.tmpdir(), 'demo-snap-a-')), mkdtempSync(path.join(os.tmpdir(), 'demo-snap-b-'))];
    try {
      for (const d of dirs) await record({ engine: opts.engine, outDir: d, allowDirty: opts.allowDirty, generatedAt: '1970-01-01T00:00:00.000Z' });
      const [a, b] = dirs.map(d => readdirSync(d).sort());
      if (JSON.stringify(a) !== JSON.stringify(b)) fail('The two runs wrote different file lists.');
      const diff = a.filter(f => !readFileSync(path.join(dirs[0], f)).equals(readFileSync(path.join(dirs[1], f))));
      if (diff.length) fail(`Not byte-identical across two runs: ${diff.join(', ')}`);
      console.log(`Determinism check passed: ${a.length} files, byte-identical across two runs.`);
    } finally { for (const d of dirs) rmSync(d, { recursive: true, force: true }); }
    return;
  }
  const result = await record({ engine: opts.engine, outDir: opts.out, allowDirty: opts.allowDirty, generatedAt: now });
  console.log(`Recorded ${result.count} requests into ${path.relative(root, result.outDir) || '.'}: ${result.files.length} files, ${result.raw} bytes raw, ${result.gz} bytes gzip, ${result.evidenceFields} experimentalValidation fields (all false).`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(err => { console.error(err instanceof Error ? err.message : err); process.exit(1); });
}
