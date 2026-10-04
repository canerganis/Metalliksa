import test from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import ts from 'typescript';
import { MODULE_CONTRACTS, type ContractOperation } from '../src/modules/registry';
import { repoRoot } from './support/importGraph';
import { beyondCeiling, readCeiling } from './support/ceiling';

// Phase 7 slice 1, static part of the route-authority check (design 7 section 5). Every HTTP
// handler declared in routes/*.ts must either serve a registry operation route or be listed in
// routes/AUTHORITY_ALLOWLIST.json with a reason. Separately, a handler (routes/*.ts and server.ts)
// that answers with literal numbers/booleans (directly, via local or module constants, or nested)
// without calling a recognised authority (AUTHORITY_CALLEES) is flagged as canned; today's
// offenders sit in a ratcheted baseline. Handler shapes the parser cannot classify fail visibly
// unless allowlisted under "unclassified". All allowlists are capped by AUTHORITY_ALLOWLIST.ceiling.json.
// This is a heuristic; the dynamic nonce sentinel test is later work.

const METHODS = new Set(['get', 'post', 'put', 'delete', 'patch']);
const ROUTER_OBJECT = /^(app|router|\w+Router)$/;

// Recognised authority dispatch: the python runners, the LPBF worker, the AI/literature providers,
// and the injected archive/registry services. Any other call does NOT count as an authority, so a
// handler that answers with literals and only calls helpers is canned.
const AUTHORITY_CALLEES: readonly RegExp[] = [
  /^(physicsDeps\.|characterizationDeps\.)?runPythonScript$/, /^handlePythonDispatch$/, /^pythonIPCSupervisor\.\w+$/,
  /^lpbfWorker\.\w+$/, /^generateGpt6Response$/, /^fetch$/, /^collectApprovedSource$/,
  /^(service|bundles|comparison|campaigns|registry)\.\w+$/,
];

export interface RouteHandler { key: string; file: string; line: number; canned: boolean; unclassified: boolean }

function calleeText(expression: ts.Expression): string {
  if (ts.isIdentifier(expression)) return expression.text;
  if (ts.isPropertyAccessExpression(expression)) return `${calleeText(expression.expression)}.${expression.name.text}`;
  if (ts.isParenthesizedExpression(expression) || ts.isNonNullExpression(expression)) return calleeText(expression.expression);
  return '?';
}

function isLiteralClaim(node: ts.Expression): boolean {
  return ts.isNumericLiteral(node) || node.kind === ts.SyntaxKind.TrueKeyword || node.kind === ts.SyntaxKind.FalseKeyword
    || (ts.isPrefixUnaryExpression(node) && ts.isNumericLiteral(node.operand));
}

// Request acknowledgements (`success: true`, `ok: true`) are transport status, not result values.
const ACK_KEYS = new Set(['success', 'ok']);

/** Variable initializers declared anywhere in a file (module constants such as hard-coded catalogs). */
function fileDeclarations(source: ts.SourceFile): Map<string, ts.Expression> {
  const declarations = new Map<string, ts.Expression>();
  const visit = (node: ts.Node) => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer && !declarations.has(node.name.text)) {
      declarations.set(node.name.text, node.initializer);
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return declarations;
}

/** Literal number/boolean claims in a response value, following local/module constants and nesting. */
function hasLiteralClaim(node: ts.Expression, locals: Map<string, ts.Expression>, seen = new Set<string>()): boolean {
  if (isLiteralClaim(node)) return true;
  if (ts.isParenthesizedExpression(node) || ts.isAsExpression(node) || ts.isSatisfiesExpression(node)) return hasLiteralClaim(node.expression, locals, seen);
  if (ts.isIdentifier(node)) {
    const value = locals.get(node.text);
    if (!value || seen.has(node.text)) return false;
    seen.add(node.text);
    return hasLiteralClaim(value, locals, seen);
  }
  if (ts.isArrayLiteralExpression(node)) return node.elements.some(element => hasLiteralClaim(element as ts.Expression, locals, seen));
  if (ts.isObjectLiteralExpression(node)) {
    const keys = node.properties.map(property => property.name && ts.isIdentifier(property.name) ? property.name.text : '');
    if (keys.includes('error')) return false; // Error envelopes are not results.
    return node.properties.some(property =>
      (ts.isPropertyAssignment(property) && !(ts.isIdentifier(property.name) && ACK_KEYS.has(property.name.text))
        && hasLiteralClaim(property.initializer, locals, seen))
      || (ts.isShorthandPropertyAssignment(property) && hasLiteralClaim(property.name, locals, seen))
      || (ts.isSpreadAssignment(property) && hasLiteralClaim(property.expression, locals, seen)));
  }
  return false;
}

/** True when the handler answers with literal numbers/booleans and calls no recognised authority. */
export function isCanned(handlerNodes: readonly ts.Node[], moduleDeclarations: ReadonlyMap<string, ts.Expression> = new Map()): boolean {
  const locals = new Map<string, ts.Expression>(moduleDeclarations);
  const responses: ts.Expression[] = [];
  let authorityCall = false;
  const visit = (node: ts.Node) => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) locals.set(node.name.text, node.initializer);
    if (ts.isCallExpression(node)) {
      const callee = calleeText(node.expression);
      if (AUTHORITY_CALLEES.some(pattern => pattern.test(callee))) authorityCall = true;
      if (ts.isPropertyAccessExpression(node.expression) && ['json', 'send'].includes(node.expression.name.text)) responses.push(...node.arguments);
    }
    ts.forEachChild(node, visit);
  };
  handlerNodes.forEach(visit);
  return !authorityCall && responses.some(response => hasLiteralClaim(response, locals));
}

/** Function bodies the classifier can analyse, or null when the handler shape is not recognised. */
function handlerBodies(args: readonly ts.Expression[]): ts.Node[] | null {
  const bodies: ts.Node[] = [];
  for (const argument of args) {
    if (ts.isArrowFunction(argument) || ts.isFunctionExpression(argument)) bodies.push(argument);
    else if (ts.isCallExpression(argument) && argument.arguments.some(inner => ts.isArrowFunction(inner) || ts.isFunctionExpression(inner))) bodies.push(argument);
  }
  return bodies.length ? bodies : null;
}

function stringConstants(source: ts.SourceFile): Map<string, string> {
  const constants = new Map<string, string>();
  const visit = (node: ts.Node) => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer && ts.isStringLiteralLike(node.initializer)) {
      constants.set(node.name.text, node.initializer.text);
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return constants;
}

function routePaths(node: ts.Expression, constants: Map<string, string>): string[] | null {
  if (ts.isStringLiteralLike(node)) return [node.text];
  if (ts.isIdentifier(node)) return constants.has(node.text) ? [constants.get(node.text)!] : null;
  if (ts.isArrayLiteralExpression(node)) {
    const parts = node.elements.map(element => routePaths(element as ts.Expression, constants));
    return parts.every(Boolean) ? parts.flat() as string[] : null;
  }
  if (ts.isTemplateExpression(node)) {
    let text = node.head.text;
    for (const span of node.templateSpans) {
      if (!ts.isIdentifier(span.expression) || !constants.has(span.expression.text)) return null;
      text += constants.get(span.expression.text)! + span.literal.text;
    }
    return [text];
  }
  return null;
}

export function routeHandlers(file: string, text: string): RouteHandler[] {
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.ES2022, true, ts.ScriptKind.TS);
  const constants = stringConstants(source);
  const declarations = fileDeclarations(source);
  const handlers: RouteHandler[] = [];
  const lineOf = (node: ts.Node) => source.getLineAndCharacterOfPosition(node.getStart()).line + 1;
  const add = (method: string, paths: string[], node: ts.Node, bodies: readonly ts.Node[] | null) => {
    const unclassified = bodies === null;
    const canned = !unclassified && isCanned(bodies, declarations);
    for (const route of paths) if (route.startsWith('/api/')) handlers.push({ key: `${method.toUpperCase()} ${route}`, file, line: lineOf(node), canned, unclassified });
  };
  const visit = (node: ts.Node) => {
    // router.get('/api/x', handler) / router.post(['/a', '/b'], ...) / router.get(`${prefix}/y`, ...)
    if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression) && METHODS.has(node.expression.name.text)
      && node.arguments.length >= 2 && ROUTER_OBJECT.test(calleeText(node.expression.expression))) {
      const paths = routePaths(node.arguments[0], constants);
      // A route whose path cannot be resolved statically is reported, never skipped.
      if (paths) add(node.expression.name.text, paths, node, handlerBodies(node.arguments.slice(1)));
      else handlers.push({ key: `UNRESOLVED ${file}:${lineOf(node)}`, file, line: lineOf(node), canned: false, unclassified: true });
    }
    // for (const [method, route, rpc] of [["get", "/api/...", "rpc"], ...]) router[method](route, handler)
    if (ts.isForOfStatement(node)) {
      let table: ts.Expression = node.expression;
      while (ts.isAsExpression(table) || ts.isSatisfiesExpression(table)) table = table.expression;
      if (ts.isArrayLiteralExpression(table)) {
        for (const row of table.elements) {
          if (!ts.isArrayLiteralExpression(row) || row.elements.length < 2) continue;
          const [method, route] = row.elements;
          if (ts.isStringLiteralLike(method) && METHODS.has(method.text) && ts.isStringLiteralLike(route)) add(method.text, [route.text], row, [node.statement]);
        }
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return handlers;
}

interface Allowlist { unbound: Record<string, string>; cannedBaseline: Record<string, string>; unclassified: Record<string, string> }
interface AllowlistCeiling { unbound: ReadonlySet<string>; cannedBaseline: ReadonlySet<string>; unclassified: ReadonlySet<string> }

const read = (relative: string) => readFileSync(path.join(repoRoot, relative), 'utf8');
const routeFiles = readdirSync(path.join(repoRoot, 'routes')).filter(name => /\.ts$/.test(name)).sort();
// Binding is checked for routes/*.ts; canned/unclassified detection also covers server.ts.
const handlers = routeFiles.flatMap(name => routeHandlers(`routes/${name}`, read(`routes/${name}`)));
const serverHandlers = routeHandlers('server.ts', read('server.ts'));
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
  assert.deepEqual(serverHandlers.map(handler => handler.key).sort(), ['GET /api/health', 'GET /api/runtime-config']);
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
    'POST /api/strings': false, 'POST /api/opaque': 'unclassified', 'UNRESOLVED sample.ts:12': 'unclassified',
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
