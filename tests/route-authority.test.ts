import test from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
// Merge note: imports combine the p7-wave1 full-registry operations with the dead-surface `siteless` helper.
// Operations live in the full registry, which the app loads lazily (the eager core slice has none).
import { MODULE_REGISTRY, type ContractOperation } from '../src/generated/moduleRegistry';
import { routeHandlers, siteless, type RouteHandler } from './support/routeScan';

const MODULE_CONTRACTS = MODULE_REGISTRY.contracts;
import { repoRoot } from './support/importGraph';
import { beyondCeiling, beyondSiteCounts, readCeiling, readCeilingCounts } from './support/ceiling';

// Phase 7 slice 1, static part of the route-authority check (design 7 section 5). Every HTTP
// handler declared in routes/**, server/** or server.ts (discovery: tests/support/routeScan.ts)
// must either serve a registry operation route or be listed in
// routes/AUTHORITY_ALLOWLIST.json with a reason. Separately, a handler
// that answers with literal numbers/booleans (directly, via local or module constants, or nested)
// without calling a recognised authority (AUTHORITY_CALLEES) is flagged as canned; today's
// offenders sit in a ratcheted baseline. Handler shapes the parser cannot classify fail visibly
// unless allowlisted under "unclassified". All allowlists are capped by AUTHORITY_ALLOWLIST.ceiling.json.
// `use` mounts are keyed by site: file plus the ordinal of that path's mounts in the file
// ('USE /api/x (routes/a.ts#2)'), so one allowlist entry never covers a second mount at the same
// path; the ceiling caps them by path (siteless key) and by site count per path (unclassifiedSites).
// This is a heuristic; the dynamic nonce sentinel test is later work.

interface Allowlist { unbound: Record<string, string>; cannedBaseline: Record<string, string>; unclassified: Record<string, string> }
interface AllowlistCeiling { unbound: ReadonlySet<string>; cannedBaseline: ReadonlySet<string>; unclassified: ReadonlySet<string>; unclassifiedSites: ReadonlyMap<string, number> }

const read = (relative: string) => readFileSync(path.join(repoRoot, relative), 'utf8');
export function tsFiles(dir: string): string[] {
  return readdirSync(path.join(repoRoot, dir), { withFileTypes: true }).flatMap(entry => {
    const relative = `${dir}/${entry.name}`;
    if (entry.isDirectory()) return tsFiles(relative);
    return /\.ts$/.test(entry.name) && !entry.name.endsWith('.d.ts') ? [relative] : [];
  }).sort();
}
// Scope: routes/** (nested included), server/** and server.ts. Binding, canned and
// unclassified checks all apply to every scanned file.
export const SCANNED_FILES = [...tsFiles('routes'), ...tsFiles('server'), 'server.ts'];
const handlers = SCANNED_FILES.flatMap(file => routeHandlers(file, read(file), path.join(repoRoot, file)));
const serverHandlers: RouteHandler[] = [];
const allowlist = JSON.parse(read('routes/AUTHORITY_ALLOWLIST.json')) as Allowlist;
const ceiling: AllowlistCeiling = {
  ...readCeiling('routes/AUTHORITY_ALLOWLIST.ceiling.json', 'unbound', 'cannedBaseline', 'unclassified'),
  unclassifiedSites: readCeilingCounts('routes/AUTHORITY_ALLOWLIST.ceiling.json', 'unclassifiedSites'),
};
// Method-aware binding keys, e.g. 'DELETE /api/lpbf/jobs/:id' (same shape as RouteHandler.key).
const operationRoutes = new Set(MODULE_CONTRACTS.flatMap(contract => (contract.operations as readonly ContractOperation[])
  .flatMap(operation => operation.route === null ? [] : [`${operation.method} ${operation.route}`])));
const where = (handler: RouteHandler) => siteless(handler.key) !== handler.key ? handler.key : `${handler.key} (${handler.file}:${handler.line})`;

/** Pure allowlist decision over parsed handlers; every list must come back empty. */
export function allowlistDecision(found: RouteHandler[], scanned: RouteHandler[], bound: ReadonlySet<string>, live: Allowlist, limit: AllowlistCeiling) {
  const keys = new Set(found.map(handler => handler.key));
  const all = [...found, ...scanned];
  const cannedKeys = new Set(all.filter(handler => handler.canned).map(handler => handler.key));
  const unclassifiedKeys = new Set(all.filter(handler => handler.unclassified).map(handler => handler.key));
  return {
    missingUnbound: found.filter(handler => !handler.unclassified && !bound.has(handler.key) && !live.unbound[handler.key]?.trim()).map(where),
    staleUnbound: Object.keys(live.unbound).filter(key => !keys.has(key) || bound.has(key)),
    grownCanned: all.filter(handler => handler.canned && !live.cannedBaseline[handler.key]?.trim()).map(where),
    staleCanned: Object.keys(live.cannedBaseline).filter(key => !cannedKeys.has(key)),
    unclassified: all.filter(handler => handler.unclassified && !live.unclassified[handler.key]?.trim()).map(where),
    staleUnclassified: Object.keys(live.unclassified).filter(key => !unclassifiedKeys.has(key)),
    beyondCeiling: [...beyondCeiling(Object.keys(live.unbound), limit.unbound).map(key => `unbound: ${key}`),
      ...beyondCeiling(Object.keys(live.cannedBaseline), limit.cannedBaseline).map(key => `cannedBaseline: ${key}`),
      ...Object.keys(live.unclassified).filter(key => !limit.unclassified.has(siteless(key))).sort().map(key => `unclassified: ${key}`),
      ...beyondSiteCounts(Object.keys(live.unclassified).filter(key => siteless(key) !== key), siteless, limit.unclassifiedSites)
        .map(entry => `unclassified sites: ${entry}`)],
  };
}
const decision = allowlistDecision(handlers, serverHandlers, operationRoutes, allowlist, ceiling);

test('the static parser finds direct, aliased, prefixed and table-driven handlers', () => {
  const keys = new Set(handlers.map(handler => handler.key));
  for (const key of ['GET /api/python/status', 'POST /api/calphad/minimize', 'GET /api/lpbf/runs/:runId',
    'POST /api/python/lpbf-keyhole-raytracing', 'GET /api/research/search', 'POST /api/consult']) {
    assert.ok(keys.has(key), `parser missed ${key}`);
  }
  assert.ok(handlers.length > 60, `expected the full route surface, found ${handlers.length}`);
  for (const key of ['GET /api/health', 'GET /api/runtime-config', 'ALL /api/*']) assert.ok(keys.has(key), `parser missed ${key}`);
  assert.ok([...keys].some(key => siteless(key) === 'USE /api/lpbf/sources' && key.includes('(routes/lpbfSources.ts#')), 'parser missed the USE /api/lpbf/sources mount');
  // The scope walks nested directories (tests/support proves recursion) and includes server/**.
  assert.ok(tsFiles('tests').includes('tests/support/routeScan.ts'));
  assert.ok(SCANNED_FILES.includes('server/security.ts') && SCANNED_FILES.includes('server.ts'));
});

test('mutation: every route-registration evasion form is discovered', () => {
  const sample = [
    "api.post('/api/any-receiver', (req, res) => res.json({ v: 1 }));",
    "this.router.get('/api/this-router', (req, res) => res.json({ v: 1 }));",
    "router['post']('/api/element-access', (req, res) => res.json({ v: 1 }));",
    "router.route('/api/route-chain').get((req, res) => res.json({ v: 1 }));",
    "const r = router.route('/api/route-var'); r.put((req, res) => res.json({ v: 1 }));",
    "router.all('/api/all', (req, res) => res.json({ v: 1 }));",
    "router.use('/api/use', (req, res) => res.json({ v: 1 }));",
    "const ROWS = [['post', '/api/table-const']]; for (const [m, p] of ROWS) router[m](p, (req, res) => res.json({ v: 1 }));",
    "function a() { const prefix = '/api/a'; router.get(`${prefix}/x`, (req, res) => res.json({ v: 1 })); }",
    "function b() { const prefix = '/api/b'; router.get(`${prefix}/x`, (req, res) => res.json({ v: 1 })); }",
    "db.prepare('SELECT 1').get(id, rev);",
    "router.get(dynamic(), (req, res) => res.json({ v: 1 }));",
    "router[verb]('/api/computed-method', handler);",
    "for (const [m, p] of [[verb, '/api/table-dynamic-method']]) router[m](p, h);",
    "const stray = [['get', '/api/stray-row']];",
    "router.get((req, res) => res.json({ v: 1 }));",
    "router.route(base + suffix).get(h);",
  ].join('\n');
  const found = routeHandlers('evasion.ts', sample);
  const resolved = Object.fromEntries(found.filter(handler => !handler.key.startsWith('UNRESOLVED')).map(handler => [handler.key, handler.canned]));
  assert.deepEqual(resolved, {
    'POST /api/any-receiver': true, 'GET /api/this-router': true, 'POST /api/element-access': true,
    'GET /api/route-chain': true, 'PUT /api/route-var': true, 'ALL /api/all': true, 'USE /api/use (evasion.ts#1)': true,
    'POST /api/table-const': true, 'GET /api/a/x': true, 'GET /api/b/x': true,
  });
  assert.ok(found.find(handler => handler.key === 'USE /api/use (evasion.ts#1)')!.unclassified, 'use-mounted /api handlers must be allowlisted');
  const unresolvedLines = found.filter(handler => handler.key.startsWith('UNRESOLVED')).map(handler => handler.line).sort((x, y) => x - y);
  assert.deepEqual(unresolvedLines, [12, 13, 14, 15, 16, 17]);
});

test('canned-result heuristic needs a recognised authority and follows variables and nesting', () => {
  const sample = `
    router.post('/api/canned', async (_req, res) => res.json({ qualified: true, safetyMarginPct: 18.5 }));
    router.post('/api/dispatch', (req, res) => handlePythonDispatch('python/x.py', req.body, res));
    router.post('/api/worker', async (req, res) => { const data = await lpbfWorker.request('x', req.body); res.json({ ok: true, data }); });
    router.post('/api/error', (req, res) => res.status(400).json({ error: 'bad', success: false }));
    router.post('/api/helper', (req, res) => { const x = normalize(req.body); res.json({ qualified: true, x }); });
    router.post('/api/variable', (req, res) => { const result = { margin: 18.5 }; res.json(result); });
    router.post('/api/shorthand', (req, res) => { const qualified = true; res.json({ qualified }); });
    router.post('/api/nested', (req, res) => res.json({ data: { findings: [{ passed: true }] } }));
    router.post('/api/strings', (req, res) => res.json({ status: 'ok', note: String(req.body) }));
    router.post('/api/opaque', namedHandler);
    router.get(computePath(), (req, res) => res.json({ a: 1 }));
    const CATALOG = [{ id: 'x', bandGap_eV: 1.2 }];
    router.get('/api/catalog', (req, res) => { let rows = CATALOG; rows = rows.filter(r => r.id === req.query.id); res.json({ success: true, data: rows }); });
    router.delete('/api/ack', (req, res) => { items.splice(0); res.json({ success: true, count: items.length }); });`;
  const parsed = Object.fromEntries(routeHandlers('sample.ts', sample).map(handler => [handler.key, handler.unclassified ? 'unclassified' : handler.canned]));
  assert.deepEqual(parsed, {
    'POST /api/canned': true, 'POST /api/dispatch': false, 'POST /api/worker': false, 'POST /api/error': false,
    'POST /api/helper': true, 'POST /api/variable': true, 'POST /api/shorthand': true, 'POST /api/nested': true,
    'POST /api/strings': false, 'POST /api/opaque': 'unclassified',
    'UNRESOLVED sample.ts: router.get(computePath(), (req, res) => res.json({ a: 1 }))': 'unclassified',
    'GET /api/catalog': true, 'DELETE /api/ack': false,
  });
});

const cannedOf = (sample: string, absPath: string | null = null) =>
  Object.fromEntries(routeHandlers('sample.ts', sample, absPath).map(handler => [handler.key, handler.canned]));

test('mutation: every literal-hiding form is still canned', () => {
  const sample = [
    "const RESULT = { v: 1 }; const CATALOG = [{ id: 'x', gap: 1.2 }]; const TABLE = { gap: 1.2 };",
    "function canned() { return { margin: 18.5 }; } const make = () => ({ q: true });",
    "router.post('/api/ack-number', (req, res) => res.json({ success: 1 }));",
    "router.post('/api/ack-boolean', (req, res) => res.json({ success: true, ok: false }));",
    "router.post('/api/error-null', (req, res) => res.json({ error: null, qualified: true }));",
    "router.post('/api/error-undefined', (req, res) => res.json({ error: undefined, v: 1 }));",
    "router.post('/api/error-real', (req, res) => res.status(500).json({ error: String(req.body), v: 1 }));",
    "router.post('/api/end-stringify', (req, res) => res.end(JSON.stringify({ qualified: true })));",
    "router.post('/api/send-stringify-const', (req, res) => res.send(JSON.stringify(RESULT)));",
    "router.post('/api/jsonp', (req, res) => res.jsonp({ v: 1 }));",
    "router.post('/api/ternary', (req, res) => res.json({ v: req.body.x ? 1 : 2 }));",
    "router.post('/api/nullish', (req, res) => res.json({ v: req.body.x ?? 1 }));",
    "router.post('/api/or', (req, res) => res.json({ v: req.body.x || true }));",
    "router.post('/api/helper-fn', (req, res) => res.json(canned()));",
    "router.post('/api/helper-arrow', (req, res) => res.json(make()));",
    "router.post('/api/assign', (req, res) => res.json(Object.assign({}, { v: 1 })));",
    "router.post('/api/index', (req, res) => res.json(CATALOG[0]));",
    "router.post('/api/field', (req, res) => res.json({ gap: TABLE.gap }));",
    "router.post('/api/filter', (req, res) => res.json({ data: CATALOG.filter(row => row.id === req.query.id) }));",
    "router.post('/api/arithmetic', (req, res) => res.json({ limit: 16 * 1024 }));",
    "router.post('/api/runtime', (req, res) => res.json({ count: req.body.items.length, value: req.body.x * 2 }));",
  ].join('\n');
  assert.deepEqual(cannedOf(sample), {
    'POST /api/ack-number': true, 'POST /api/ack-boolean': false, 'POST /api/error-null': true,
    'POST /api/error-undefined': true, 'POST /api/error-real': false, 'POST /api/end-stringify': true,
    'POST /api/send-stringify-const': true, 'POST /api/jsonp': true, 'POST /api/ternary': true, 'POST /api/nullish': true,
    'POST /api/or': true, 'POST /api/helper-fn': true, 'POST /api/helper-arrow': true, 'POST /api/assign': true,
    'POST /api/index': true, 'POST /api/field': true, 'POST /api/filter': true, 'POST /api/arithmetic': true,
    'POST /api/runtime': false,
  });
});

test('mutation: literals moved into an imported module are still canned', () => {
  const sample = [
    "import { CANNED_RESULT, CANNED_LIMIT, cannedHelper } from './route-canned-module';",
    "router.post('/api/imported-const', (req, res) => res.json(CANNED_RESULT));",
    "router.post('/api/imported-arith', (req, res) => res.json({ limit: CANNED_LIMIT }));",
    "router.post('/api/imported-helper', (req, res) => res.json(cannedHelper()));",
  ].join('\n');
  assert.deepEqual(cannedOf(sample, path.join(repoRoot, 'tests/fixtures/sample-route.ts')), {
    'POST /api/imported-const': true, 'POST /api/imported-arith': true, 'POST /api/imported-helper': true,
  });
});

test('mutation: namespace, default and helper-object imports are followed', () => {
  const sample = [
    "import * as Canned from './route-canned-module';",
    "import cannedDefault, { CANNED_HELPERS } from './route-canned-module';",
    "import cannedDefaultFunction from './route-canned-default';",
    "import * as Orchestrator from '../../server/processOrchestrator.ts';",
    "const H = { make: () => ({ v: 1 }), build() { return { ok: 2 }; }, fine: () => ({ note: 'x' }) };",
    "router.post('/api/ns-const', (req, res) => res.json(Canned.CANNED_RESULT));",
    "router.post('/api/ns-field', (req, res) => res.json({ limit: Canned.CANNED_LIMIT }));",
    "router.post('/api/ns-helper', (req, res) => res.json(Canned.cannedHelper()));",
    "router.post('/api/ns-method', (req, res) => res.json(Canned.CANNED_HELPERS.build()));",
    "router.post('/api/default-alias', (req, res) => res.json(cannedDefault()));",
    "router.post('/api/default-function', (req, res) => res.json(cannedDefaultFunction()));",
    "router.post('/api/imported-method', (req, res) => res.json(CANNED_HELPERS.make()));",
    "router.post('/api/imported-method-decl', (req, res) => res.json(CANNED_HELPERS.build()));",
    "router.post('/api/local-arrow-method', (req, res) => res.json(H.make()));",
    "router.post('/api/local-method', (req, res) => res.json(H.build()));",
    "router.post('/api/local-method-strings', (req, res) => res.json(H.fine()));",
    "router.post('/api/ns-authority', async (req, res) => res.json({ v: 1, out: await Orchestrator.runPythonScript('x', {}) }));",
  ].join('\n');
  assert.deepEqual(cannedOf(sample, path.join(repoRoot, 'tests/fixtures/sample-route.ts')), {
    'POST /api/ns-const': true, 'POST /api/ns-field': true, 'POST /api/ns-helper': true, 'POST /api/ns-method': true,
    'POST /api/default-alias': true, 'POST /api/default-function': true, 'POST /api/imported-method': true,
    'POST /api/imported-method-decl': true, 'POST /api/local-arrow-method': true, 'POST /api/local-method': true,
    'POST /api/local-method-strings': false, 'POST /api/ns-authority': false,
  });
});

test('mutation: falsy error values, res.write and catch fallbacks do not hide literals', () => {
  const sample = [
    "import { runPythonScript } from '../server/processOrchestrator.ts';",
    "const NO_ERROR = '';",
    "router.post('/api/error-false', (req, res) => res.json({ error: false, qualified: true }));",
    "router.post('/api/error-empty', (req, res) => res.json({ error: '', v: 1 }));",
    "router.post('/api/error-zero', (req, res) => res.json({ error: 0, v: 1 }));",
    "router.post('/api/error-const', (req, res) => res.json({ error: NO_ERROR, v: 1 }));",
    "router.post('/api/error-message', (req, res) => res.status(500).json({ error: 'failed', v: 1 }));",
    "router.post('/api/write', (req, res) => { res.write(JSON.stringify({ v: 1 })); res.end(); });",
    "router.post('/api/catch-fallback', async (req, res) => { try { res.json(await runPythonScript('x', {})); } catch { res.json({ margin: 18.5 }); } });",
    "router.post('/api/promise-fallback', (req, res) => { runPythonScript('x', {}).then(out => res.json(out)).catch(() => res.json({ margin: 18.5 })); });",
    "router.post('/api/then-fallback', (req, res) => { runPythonScript('x', {}).then(out => res.json(out), () => res.json({ margin: 18.5 })); });",
    "router.post('/api/catch-error', async (req, res) => { try { res.json(await runPythonScript('x', {})); } catch (e) { res.status(500).json({ error: String(e), v: 1 }); } });",
    "router.post('/api/catch-retry', async (req, res) => { try { res.json(await runPythonScript('x', {})); } catch { res.json({ v: 1, out: await runPythonScript('y', {}) }); } });",
    "router.post('/api/authority-in-catch-only', async (req, res) => { try { JSON.parse(req.body); } catch { await runPythonScript('x', {}); } res.json({ v: 1 }); });",
    "router.post('/api/authority-in-rejection-only', (req, res) => { Promise.resolve().catch(() => runPythonScript('x', {})); res.json({ v: 1 }); });",
    "router.post('/api/missing-result', async (req, res) => { const out = await runPythonScript('x', {}).catch(() => null); if (!out) return res.json({ margin: 18.5 }); res.json(out); });",
    "router.post('/api/missing-result-null', async (req, res) => { const out = await runPythonScript('x', {}); if (out == null) { res.json({ margin: 18.5 }); return; } res.json(out); });",
    "router.post('/api/missing-result-else', async (req, res) => { let out; try { out = await runPythonScript('x', {}); } catch {} if (out) res.json(out); else res.json({ margin: 18.5 }); });",
    "router.post('/api/missing-result-ternary', async (req, res) => { const out = await runPythonScript('x', {}); return out !== undefined ? res.json(out) : res.json({ margin: 18.5 }); });",
    "router.post('/api/missing-result-error', async (req, res) => { const out = await runPythonScript('x', {}).catch(() => null); if (!out) return res.status(502).json({ error: 'python failed' }); res.json({ ...out, cached: false }); });",
    "router.post('/api/present-result', async (req, res) => { const out = await runPythonScript('x', {}); if (!out.ok) return res.status(400).json({ error: out.message }); res.json({ v: 1, out }); });",
  ].join('\n');
  assert.deepEqual(cannedOf(sample), {
    'POST /api/error-false': true, 'POST /api/error-empty': true, 'POST /api/error-zero': true, 'POST /api/error-const': true,
    'POST /api/error-message': false, 'POST /api/write': true, 'POST /api/catch-fallback': true,
    'POST /api/promise-fallback': true, 'POST /api/then-fallback': true, 'POST /api/catch-error': false,
    'POST /api/catch-retry': false, 'POST /api/authority-in-catch-only': true, 'POST /api/authority-in-rejection-only': true,
    'POST /api/missing-result': true, 'POST /api/missing-result-null': true, 'POST /api/missing-result-else': true,
    'POST /api/missing-result-ternary': true, 'POST /api/missing-result-error': false, 'POST /api/present-result': false,
  });
});

test('mutation: objects filled after their declaration are still judged', () => {
  const sample = [
    "const SHARED = {}; SHARED.margin = 18.5;",
    "router.post('/api/fill-local', (req, res) => { const r = {}; r.v = 1; res.json(r); });",
    "router.post('/api/fill-element', (req, res) => { const r: any = {}; r['qualified'] = true; res.json({ data: r }); });",
    "router.post('/api/fill-nested', (req, res) => { const r = { data: {} }; r.data.v = 1; res.json(r); });",
    "router.post('/api/fill-assign', (req, res) => { const r = {}; Object.assign(r, { v: 1 }); res.json(r); });",
    "router.post('/api/fill-module', (req, res) => res.json(SHARED));",
    "router.post('/api/fill-runtime', (req, res) => { const r: any = {}; r.count = req.body.items.length; r.success = true; res.json(r); });",
    "router.post('/api/fill-error', (req, res) => { const r: any = { v: 1 }; r.error = String(req.body); res.status(400).json(r); });",
  ].join('\n');
  assert.deepEqual(cannedOf(sample), {
    'POST /api/fill-local': true, 'POST /api/fill-element': true, 'POST /api/fill-nested': true, 'POST /api/fill-assign': true,
    'POST /api/fill-module': true, 'POST /api/fill-runtime': false, 'POST /api/fill-error': false,
  });
});

test('mutation: invoker, options/head and relative sub-router registrations are discovered', () => {
  const sample = [
    "router.post.call(router, '/api/call', (req, res) => res.json({ v: 1 }));",
    "router.put.apply(router, ['/api/apply', (req, res) => res.json({ v: 1 })]);",
    "router.patch.bind(router, '/api/bind-now')((req, res) => res.json({ v: 1 }));",
    "const post = router.post.bind(router); post('/api/bind-alias', (req, res) => res.json({ v: 1 }));",
    "router.options('/api/options', (req, res) => res.json({ v: 1 }));",
    "router.head('/api/head', (req, res) => res.json({ v: 1 }));",
    "const sub = Router(); sub.get('/relative', (req, res) => res.json({ v: 1 })); sub.post('/', (req, res) => res.json({ note: 'x' }));",
    "router.use('/api/mounted', sub);",
    "register(router.get.bind(router));",
    "router.delete.apply(router, args);",
    "router[verb].call(router, '/api/computed-call', h);",
    "app.get('/login', (req, res) => res.json({ v: 1 }));",
  ].join('\n');
  const found = routeHandlers('invokers.ts', sample);
  const resolved = Object.fromEntries(found.filter(handler => !handler.key.startsWith('UNRESOLVED')).map(handler => [handler.key, handler.canned]));
  assert.deepEqual(resolved, {
    'POST /api/call': true, 'PUT /api/apply': true, 'PATCH /api/bind-now': true, 'POST /api/bind-alias': true,
    'OPTIONS /api/options': true, 'HEAD /api/head': true, 'USE /api/mounted (invokers.ts#1)': false,
    'GET /api/mounted/relative': true, 'POST /api/mounted': false,
  });
  assert.equal(found.find(handler => handler.key === 'GET /api/mounted/relative')!.line, 7);
  const unresolvedLines = found.filter(handler => handler.key.startsWith('UNRESOLVED')).map(handler => handler.line).sort((x, y) => x - y);
  assert.deepEqual(unresolvedLines, [9, 10, 11]);
});

test('regression: factory-built and nested sub-router mounts fail visibly as unclassified', () => {
  const sample = [
    "function makeRouter() { const r = Router(); r.post('/canned', (req, res) => res.json({ v: 1 })); return r; }",
    "app.use('/api/factory-call', makeRouter());",
    "const built = makeRouter(); app.use('/api/factory-var', built);",
    "const outer = Router(); const inner = Router(); inner.post('/deep', (req, res) => res.json({ v: 1 }));",
    "outer.use('/inner', inner);",
    "app.use('/api/nested', outer);",
  ].join('\n');
  const found = routeHandlers('routes/factory.ts', sample);
  assert.deepEqual(Object.fromEntries(found.map(handler => [handler.key, handler.unclassified])), {
    'USE /api/factory-call (routes/factory.ts#1)': true, 'USE /api/factory-var (routes/factory.ts#1)': true,
    'USE /api/nested (routes/factory.ts#1)': true, 'USE /api/nested/inner (routes/factory.ts#1)': true,
  });
  // The routes inside cannot be followed statically, so none of the mounts passes unallowlisted.
  assert.deepEqual(allowlistDecision([...handlers, ...found], serverHandlers, operationRoutes, allowlist, ceiling).unclassified, [
    'USE /api/factory-call (routes/factory.ts#1)', 'USE /api/factory-var (routes/factory.ts#1)',
    'USE /api/nested (routes/factory.ts#1)', 'USE /api/nested/inner (routes/factory.ts#1)',
  ]);
});

test('mutation: an imported sub-router mounted under /api is reported under the joined path', () => {
  const sample = [
    "import { cannedSubRouter } from './route-sub-router';",
    "import defaultSubRouter from './route-sub-router';",
    "app.use('/api/sub', cannedSubRouter);",
    "app.use('/api/default-sub', defaultSubRouter);",
  ].join('\n');
  const found = routeHandlers('tests/fixtures/sample-route.ts', sample, path.join(repoRoot, 'tests/fixtures/sample-route.ts'));
  assert.deepEqual(Object.fromEntries(found.map(handler => [handler.key, handler.canned])), {
    'USE /api/sub (tests/fixtures/sample-route.ts#1)': false, 'USE /api/default-sub (tests/fixtures/sample-route.ts#1)': false,
    'POST /api/sub/canned': true, 'GET /api/sub': false, 'POST /api/default-sub/canned': true, 'GET /api/default-sub': false,
  });
  const canned = found.find(handler => handler.key === 'POST /api/sub/canned')!;
  assert.deepEqual([canned.file, canned.line], ['tests/fixtures/route-sub-router.ts', 7]);
});

test('mutation: use mounts are keyed by file and per-path ordinal, not by line', () => {
  const sample = ["router.use('/api/a', guard);", '', "router.use('/api/b', guard);", "router.use('/api/a', bodyError);"].join('\n');
  const keys = routeHandlers('routes/mounts.ts', sample).map(handler => handler.key);
  assert.deepEqual(keys, ['USE /api/a (routes/mounts.ts#1)', 'USE /api/b (routes/mounts.ts#1)', 'USE /api/a (routes/mounts.ts#2)']);
  // Moving the mounts down (an unrelated edit above them) keeps the keys.
  assert.deepEqual(routeHandlers('routes/mounts.ts', '// a new comment\n\n' + sample).map(handler => handler.key), keys);
  assert.deepEqual(keys.map(siteless), ['USE /api/a', 'USE /api/b', 'USE /api/a']);
});

test('mutation: a second mount at an allowlisted USE path needs its own site entry within the site count', () => {
  const extra = routeHandlers('routes/otherMount.ts', `router.use('/api/lpbf', subRouter);`);
  assert.deepEqual(extra.map(handler => handler.key), ['USE /api/lpbf (routes/otherMount.ts#1)']);
  assert.deepEqual(allowlistDecision([...handlers, ...extra], serverHandlers, operationRoutes, allowlist, ceiling).unclassified,
    ['USE /api/lpbf (routes/otherMount.ts#1)']);
  // Allowlisting the second /api/lpbf site exceeds the ceiling's site count for that path...
  const second = allowlistDecision([...handlers, ...extra], serverHandlers, operationRoutes,
    { ...allowlist, unclassified: { ...allowlist.unclassified, 'USE /api/lpbf (routes/otherMount.ts#1)': 'sneaked in' } }, ceiling);
  assert.deepEqual([second.unclassified, second.beyondCeiling], [[], ['unclassified sites: USE /api/lpbf (2 > 1 sites)']]);
  // ...moving a site to another file within the count is fine...
  const moved = { ...allowlist.unclassified };
  delete moved['USE /api/lpbf (routes/lpbfSimulation.ts#1)'];
  assert.deepEqual(allowlistDecision(handlers, serverHandlers, operationRoutes,
    { ...allowlist, unclassified: { ...moved, 'USE /api/lpbf (routes/otherMount.ts#1)': 'moved' } }, ceiling).beyondCeiling, []);
  // ...and a mount at a path the ceiling does not hold stays beyond it.
  const fresh = routeHandlers('routes/otherMount.ts', `router.use('/api/fresh', subRouter);`);
  const sneaked = allowlistDecision([...handlers, ...fresh], serverHandlers, operationRoutes,
    { ...allowlist, unclassified: { ...allowlist.unclassified, 'USE /api/fresh (routes/otherMount.ts#1)': 'sneaked in' } }, ceiling);
  assert.deepEqual(sneaked.beyondCeiling, ['unclassified: USE /api/fresh (routes/otherMount.ts#1)',
    'unclassified sites: USE /api/fresh (1 > 0 sites)']);
});

test('the site-count ceiling only covers unclassified ceiling paths', () => {
  assert.deepEqual([...ceiling.unclassifiedSites.keys()].filter(entry => !ceiling.unclassified.has(entry)), []);
});

test('mutation: look-alike authorities do not count; recognised imports and injected services do', () => {
  const spoofed = [
    "const lpbfWorker = { request: async () => ({}) };",
    "function handlePythonDispatch() { return 1; }",
    "const service = { list: () => [] };",
    "router.post('/api/fake-worker', async (req, res) => { await lpbfWorker.request('x'); res.json({ v: 1 }); });",
    "router.post('/api/fake-dispatch', (req, res) => { handlePythonDispatch(); res.json({ v: 1 }); });",
    "router.post('/api/fake-service', (req, res) => { service.list(); res.json({ v: 1 }); });",
    "router.post('/api/bare-fetch', async (req, res) => { await fetch('https://example.invalid'); res.json({ v: 1 }); });",
    "router.post('/api/any-registry', (req, res) => { registry.save(); res.json({ v: 1 }); });",
  ].join('\n');
  assert.deepEqual(cannedOf(spoofed), {
    'POST /api/fake-worker': true, 'POST /api/fake-dispatch': true, 'POST /api/fake-service': true,
    'POST /api/bare-fetch': true, 'POST /api/any-registry': true,
  });
  const genuine = [
    "import { lpbfWorker } from '../server/lpbfWorkerBridge';",
    "import { runPythonScript } from '../server/processOrchestrator.ts';",
    "import { LpbfRunArchiveService } from '../server/lpbfRunArchiveService';",
    "import { researchSearchUrl } from '../server/researchSearch';",
    "const deps = { runPythonScript };",
    "async function handlePythonDispatch(script, res) { const out = await deps.runPythonScript(script, {}); res.json(out); }",
    "router.post('/api/worker', async (req, res) => { const data = await lpbfWorker.request('x'); res.json({ v: 1, data }); });",
    "router.post('/api/deps', async (req, res) => { await deps.runPythonScript('x', {}); res.json({ v: 1 }); });",
    "router.post('/api/dispatch', (req, res) => { handlePythonDispatch('x', res); res.json({ v: 1 }); });",
    "export function create(service = new LpbfRunArchiveService()) { const router = Router(); router.get('/api/archive', async (req, res) => { await service.list(); res.json({ v: 1 }); }); }",
    "router.get('/api/search', async (req, res) => { const url = researchSearchUrl(req.query.q); await fetch(url); res.json({ v: 1 }); });",
  ].join('\n');
  assert.deepEqual(cannedOf(genuine), {
    'POST /api/worker': false, 'POST /api/deps': false, 'POST /api/dispatch': false, 'GET /api/archive': false, 'GET /api/search': false,
  });
});

test('mutation: a new canned route plus matching allowlist entries still fails', () => {
  const [canned] = routeHandlers('routes/newCanned.ts', `router.post('/api/new-canned', async (_req, res) => res.json({ qualified: true }));`);
  const live: Allowlist = {
    ...allowlist,
    unbound: { ...allowlist.unbound, [canned.key]: 'sneaked in' },
    cannedBaseline: { ...allowlist.cannedBaseline, [canned.key]: 'sneaked in' },
  };
  const result = allowlistDecision([...handlers, canned], serverHandlers, operationRoutes, live, ceiling);
  assert.deepEqual(result.missingUnbound, []);
  assert.deepEqual(result.grownCanned, []);
  assert.deepEqual(result.beyondCeiling, ['unbound: POST /api/new-canned', 'cannedBaseline: POST /api/new-canned']);
  // Removing entries stays allowed (only the stale checks then ask for cleanup).
  assert.deepEqual(allowlistDecision(handlers, serverHandlers, operationRoutes, { unbound: {}, cannedBaseline: {}, unclassified: {} }, ceiling).beyondCeiling, []);
});

test('mutation: an unclassifiable handler fails visibly unless allowlisted within the ceiling', () => {
  const opaque = routeHandlers('routes/opaque.ts', `router.post('/api/opaque', namedHandler);`);
  const result = allowlistDecision([...handlers, ...opaque], serverHandlers, operationRoutes, allowlist, ceiling);
  assert.deepEqual(result.unclassified, ['POST /api/opaque (routes/opaque.ts:1)']);
  const sneaked = allowlistDecision([...handlers, ...opaque], serverHandlers, operationRoutes,
    { ...allowlist, unclassified: { ...allowlist.unclassified, 'POST /api/opaque': 'sneaked in' } }, ceiling);
  assert.deepEqual(sneaked.beyondCeiling, ['unclassified: POST /api/opaque']);
});

test('every handler is classifiable or allowlisted as unclassified with a reason', () => {
  assert.deepEqual(decision.unclassified, [], `Handler(s) ${decision.unclassified.join(', ')} cannot be classified statically: use an inline handler or allowlist them under "unclassified" with a reason.`);
  assert.deepEqual(decision.staleUnclassified, [], `Unclassified entries ${decision.staleUnclassified.join(', ')} no longer match: remove them.`);
});

test('every routes/*.ts handler is bound to a registry operation or allowlisted with a reason', () => {
  assert.deepEqual(decision.beyondCeiling, [], `Allowlist entries ${decision.beyondCeiling.join(', ')} are not in routes/AUTHORITY_ALLOWLIST.ceiling.json: bind the route to an authority instead.`);
  assert.deepEqual(decision.missingUnbound, [], `Unbound handler(s) ${decision.missingUnbound.join(', ')}: bind them to a registry operation route or allowlist them with a reason.`);
  assert.deepEqual(decision.staleUnbound, [], `Allowlist entries ${decision.staleUnbound.join(', ')} are bound or gone: remove them.`);
});

test('every registry operation route is served by a routes/*.ts handler', () => {
  const served = new Set(handlers.map(handler => handler.key));
  const dangling = [...operationRoutes].filter(route => !served.has(route));
  assert.deepEqual(dangling, [], `Registry operation route(s) without a handler: ${dangling.join(', ')}`);
});

test('no registry operation is bound to a canned-result handler', () => {
  const boundCanned = [...handlers, ...serverHandlers].filter(handler => handler.canned && operationRoutes.has(handler.key)).map(where);
  assert.deepEqual(boundCanned, [], `Canned handler(s) ${boundCanned.join(', ')} must not back a registry operation: record them as legacyNotes.`);
  const evidence = MODULE_CONTRACTS.filter(contract => ['experimental-data', 'traceability'].includes(contract.id));
  assert.deepEqual(evidence.map(contract => contract.operations.length), [0, 0], 'EvidenceWorkspace dispatches no request; record store reads as legacyNotes');
});

test('canned-result handlers never grow beyond the ratcheted baseline', () => {
  console.log(`Canned-result baseline (${Object.keys(allowlist.cannedBaseline).length}):\n${Object.entries(allowlist.cannedBaseline).map(([key, reason]) => `  ${key} - ${reason}`).join('\n')}`);
  assert.deepEqual(decision.grownCanned, [], `New canned-result handler(s) ${decision.grownCanned.join(', ')}: call an authority (python runner, worker, provider) instead of returning literals.`);
  assert.deepEqual(decision.staleCanned, [], `Canned baseline entries ${decision.staleCanned.join(', ')} no longer match: remove them (the baseline only shrinks).`);
});
