import test from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { MODULE_CONTRACTS, type ContractOperation } from '../src/modules/registry';
import { routeHandlers, type RouteHandler } from './support/routeScan';
import { repoRoot } from './support/importGraph';
import { beyondCeiling, readCeiling } from './support/ceiling';

// Phase 7 slice 1, static part of the route-authority check (design 7 section 5). Every HTTP
// handler declared in routes/**, server/** or server.ts (discovery: tests/support/routeScan.ts)
// must either serve a registry operation route or be listed in
// routes/AUTHORITY_ALLOWLIST.json with a reason. Separately, a handler
// that answers with literal numbers/booleans (directly, via local or module constants, or nested)
// without calling a recognised authority (AUTHORITY_CALLEES) is flagged as canned; today's
// offenders sit in a ratcheted baseline. Handler shapes the parser cannot classify fail visibly
// unless allowlisted under "unclassified". All allowlists are capped by AUTHORITY_ALLOWLIST.ceiling.json.
// This is a heuristic; the dynamic nonce sentinel test is later work.

interface Allowlist { unbound: Record<string, string>; cannedBaseline: Record<string, string>; unclassified: Record<string, string> }
interface AllowlistCeiling { unbound: ReadonlySet<string>; cannedBaseline: ReadonlySet<string>; unclassified: ReadonlySet<string> }

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
const handlers = SCANNED_FILES.flatMap(file => routeHandlers(file, read(file)));
const serverHandlers: RouteHandler[] = [];
const allowlist = JSON.parse(read('routes/AUTHORITY_ALLOWLIST.json')) as Allowlist;
const ceiling: AllowlistCeiling = readCeiling('routes/AUTHORITY_ALLOWLIST.ceiling.json', 'unbound', 'cannedBaseline', 'unclassified');
// Method-aware binding keys, e.g. 'DELETE /api/lpbf/jobs/:id' (same shape as RouteHandler.key).
const operationRoutes = new Set(MODULE_CONTRACTS.flatMap(contract => (contract.operations as readonly ContractOperation[])
  .flatMap(operation => operation.route === null ? [] : [`${operation.method} ${operation.route}`])));
const where = (handler: RouteHandler) => `${handler.key} (${handler.file}:${handler.line})`;

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
      ...beyondCeiling(Object.keys(live.unclassified), limit.unclassified).map(key => `unclassified: ${key}`)],
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
  for (const key of ['GET /api/health', 'GET /api/runtime-config', 'ALL /api/*', 'USE /api/lpbf/sources']) assert.ok(keys.has(key), `parser missed ${key}`);
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
    'GET /api/route-chain': true, 'PUT /api/route-var': true, 'ALL /api/all': true, 'USE /api/use': true,
    'POST /api/table-const': true, 'GET /api/a/x': true, 'GET /api/b/x': true,
  });
  assert.ok(found.find(handler => handler.key === 'USE /api/use')!.unclassified, 'use-mounted /api handlers must be allowlisted');
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
