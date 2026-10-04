import test from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import ts from 'typescript';
import { MODULE_CONTRACTS } from '../src/modules/registry';
import { repoRoot } from './support/importGraph';
import { beyondCeiling, readCeiling } from './support/ceiling';

// Phase 7 slice 1, static part of the route-authority check (design 7 section 5). Every HTTP
// handler declared in routes/*.ts must either serve a registry operation route or be listed in
// routes/AUTHORITY_ALLOWLIST.json with a reason. Separately, a handler that answers with literal
// numbers/booleans while calling nothing that could be an authority (python runner, worker,
// provider, service) is flagged as canned; today's offenders sit in a ratcheted baseline.
// This is a heuristic; the dynamic nonce sentinel test is later work.

const METHODS = new Set(['get', 'post', 'put', 'delete', 'patch']);
// Calls that cannot be an authority: request/response plumbing and value helpers.
const INERT_ROOTS = new Set(['res', 'req', 'JSON', 'String', 'Number', 'Boolean', 'Math', 'Array', 'Object', 'Buffer',
  'console', 'Date', 'parseInt', 'parseFloat', 'isFinite', 'denyIfAirgapped', 'airgapDenyPayload', 'isAirgappedFromEnv']);
const INERT_METHODS = new Set(['filter', 'map', 'includes', 'toLowerCase', 'toUpperCase', 'trim', 'slice', 'startsWith',
  'endsWith', 'match', 'some', 'every', 'find', 'join', 'split', 'replace', 'push', 'toFixed', 'toString', 'status',
  'json', 'send', 'set', 'setHeader', 'get', 'has', 'end', 'type']);

export interface RouteHandler { key: string; file: string; line: number; canned: boolean }

function rootIdentifier(expression: ts.Expression): string | undefined {
  let current: ts.Expression = expression;
  while (ts.isPropertyAccessExpression(current) || ts.isElementAccessExpression(current) || ts.isCallExpression(current)
    || ts.isNonNullExpression(current) || ts.isParenthesizedExpression(current)) {
    current = current.expression;
  }
  return ts.isIdentifier(current) ? current.text : undefined;
}

function isLiteralClaim(node: ts.Expression): boolean {
  return ts.isNumericLiteral(node) || node.kind === ts.SyntaxKind.TrueKeyword || node.kind === ts.SyntaxKind.FalseKeyword
    || (ts.isPrefixUnaryExpression(node) && ts.isNumericLiteral(node.operand));
}

/** True when the handler answers with literal numbers/booleans and calls nothing that could be an authority. */
export function isCanned(handlerNodes: readonly ts.Node[]): boolean {
  let literalResponse = false;
  let authorityCall = false;
  const visit = (node: ts.Node) => {
    if (ts.isCallExpression(node)) {
      const callee = node.expression;
      const method = ts.isPropertyAccessExpression(callee) ? callee.name.text : undefined;
      const root = rootIdentifier(callee);
      const inert = (root !== undefined && INERT_ROOTS.has(root)) || (method !== undefined && INERT_METHODS.has(method));
      if (!inert) authorityCall = true;
      if (method === 'json' || method === 'send') {
        for (const argument of node.arguments) {
          if (!ts.isObjectLiteralExpression(argument)) continue;
          const keys = argument.properties.map(property => property.name && ts.isIdentifier(property.name) ? property.name.text : '');
          if (keys.includes('error')) continue; // Error envelopes are not results.
          if (argument.properties.some(property => ts.isPropertyAssignment(property) && isLiteralClaim(property.initializer))) literalResponse = true;
        }
      }
    }
    ts.forEachChild(node, visit);
  };
  handlerNodes.forEach(visit);
  return literalResponse && !authorityCall;
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
  const handlers: RouteHandler[] = [];
  const add = (method: string, paths: string[], node: ts.Node, body: readonly ts.Node[]) => {
    const line = source.getLineAndCharacterOfPosition(node.getStart()).line + 1;
    const canned = isCanned(body);
    for (const route of paths) if (route.startsWith('/api/')) handlers.push({ key: `${method.toUpperCase()} ${route}`, file, line, canned });
  };
  const visit = (node: ts.Node) => {
    // router.get('/api/x', handler) / router.post(['/a', '/b'], ...) / router.get(`${prefix}/y`, ...)
    if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression) && METHODS.has(node.expression.name.text)
      && node.arguments.length >= 2) {
      const paths = routePaths(node.arguments[0], constants);
      if (paths) add(node.expression.name.text, paths, node, node.arguments.slice(1));
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

interface Allowlist { unbound: Record<string, string>; cannedBaseline: Record<string, string> }
interface AllowlistCeiling { unbound: ReadonlySet<string>; cannedBaseline: ReadonlySet<string> }

const routeFiles = readdirSync(path.join(repoRoot, 'routes')).filter(name => /\.ts$/.test(name)).sort();
const handlers = routeFiles.flatMap(name => routeHandlers(`routes/${name}`, readFileSync(path.join(repoRoot, 'routes', name), 'utf8')));
const allowlist = JSON.parse(readFileSync(path.join(repoRoot, 'routes/AUTHORITY_ALLOWLIST.json'), 'utf8')) as Allowlist;
const ceiling: AllowlistCeiling = readCeiling('routes/AUTHORITY_ALLOWLIST.ceiling.json', 'unbound', 'cannedBaseline');
const operationRoutes = new Set(MODULE_CONTRACTS.flatMap(contract => contract.operations.map(operation => operation.route)).filter(Boolean) as string[]);
const routeOf = (key: string) => key.slice(key.indexOf(' ') + 1);
const where = (handler: RouteHandler) => `${handler.key} (${handler.file}:${handler.line})`;

/** Pure allowlist decision over parsed handlers; every list must come back empty. */
export function allowlistDecision(found: RouteHandler[], bound: ReadonlySet<string>, live: Allowlist, limit: AllowlistCeiling) {
  const keys = new Set(found.map(handler => handler.key));
  const cannedKeys = new Set(found.filter(handler => handler.canned).map(handler => handler.key));
  return {
    missingUnbound: found.filter(handler => !bound.has(routeOf(handler.key)) && !live.unbound[handler.key]?.trim()).map(where),
    staleUnbound: Object.keys(live.unbound).filter(key => !keys.has(key) || bound.has(routeOf(key))),
    grownCanned: found.filter(handler => handler.canned && !live.cannedBaseline[handler.key]?.trim()).map(where),
    staleCanned: Object.keys(live.cannedBaseline).filter(key => !cannedKeys.has(key)),
    beyondCeiling: [...beyondCeiling(Object.keys(live.unbound), limit.unbound).map(key => `unbound: ${key}`),
      ...beyondCeiling(Object.keys(live.cannedBaseline), limit.cannedBaseline).map(key => `cannedBaseline: ${key}`)],
  };
}

test('the static parser finds direct, aliased, prefixed and table-driven handlers', () => {
  const keys = new Set(handlers.map(handler => handler.key));
  for (const key of ['GET /api/python/status', 'POST /api/calphad/minimize', 'GET /api/lpbf/runs/:runId',
    'POST /api/python/lpbf-keyhole-raytracing', 'GET /api/research/search', 'POST /api/consult']) {
    assert.ok(keys.has(key), `parser missed ${key}`);
  }
  assert.ok(handlers.length > 60, `expected the full route surface, found ${handlers.length}`);
});

test('canned-result heuristic flags literal answers without an authority call and spares dispatching handlers', () => {
  const sample = `
    r.post('/api/canned', async (_req, res) => res.json({ qualified: true, safetyMarginPct: 18.5 }));
    r.post('/api/dispatch', (req, res) => handlePythonDispatch('python/x.py', req.body, res));
    r.post('/api/worker', async (req, res) => { const data = await lpbfWorker.request('x', req.body); res.json({ ok: true, data }); });
    r.post('/api/error', (req, res) => res.status(400).json({ error: 'bad', success: false }));`;
  const parsed = new Map(routeHandlers('sample.ts', sample).map(handler => [handler.key, handler.canned]));
  assert.deepEqual(Object.fromEntries(parsed), {
    'POST /api/canned': true, 'POST /api/dispatch': false, 'POST /api/worker': false, 'POST /api/error': false,
  });
});

test('mutation: a new canned route plus matching allowlist entries still fails', () => {
  const [canned] = routeHandlers('routes/newCanned.ts', `r.post('/api/new-canned', async (_req, res) => res.json({ qualified: true }));`);
  const live: Allowlist = {
    unbound: { ...allowlist.unbound, [canned.key]: 'sneaked in' },
    cannedBaseline: { ...allowlist.cannedBaseline, [canned.key]: 'sneaked in' },
  };
  const decision = allowlistDecision([...handlers, canned], operationRoutes, live, ceiling);
  assert.deepEqual(decision.missingUnbound, []);
  assert.deepEqual(decision.grownCanned, []);
  assert.deepEqual(decision.beyondCeiling, ['unbound: POST /api/new-canned', 'cannedBaseline: POST /api/new-canned']);
  // Removing entries stays allowed (only the stale check then asks for cleanup).
  const shrunk = allowlistDecision(handlers, operationRoutes, { unbound: {}, cannedBaseline: {} }, ceiling);
  assert.deepEqual(shrunk.beyondCeiling, []);
});

test('every routes/*.ts handler is bound to a registry operation or allowlisted with a reason', () => {
  const decision = allowlistDecision(handlers, operationRoutes, allowlist, ceiling);
  assert.deepEqual(decision.beyondCeiling, [], `Allowlist entries ${decision.beyondCeiling.join(', ')} are not in routes/AUTHORITY_ALLOWLIST.ceiling.json: bind the route to an authority instead.`);
  assert.deepEqual(decision.missingUnbound, [], `Unbound handler(s) ${decision.missingUnbound.join(', ')}: bind them to a registry operation route or allowlist them with a reason.`);
  assert.deepEqual(decision.staleUnbound, [], `Allowlist entries ${decision.staleUnbound.join(', ')} are bound or gone: remove them.`);
});

test('every registry operation route is served by a routes/*.ts handler', () => {
  const served = new Set(handlers.map(handler => routeOf(handler.key)));
  const dangling = [...operationRoutes].filter(route => !served.has(route));
  assert.deepEqual(dangling, [], `Registry operation route(s) without a handler: ${dangling.join(', ')}`);
});

test('canned-result handlers never grow beyond the ratcheted baseline', () => {
  const decision = allowlistDecision(handlers, operationRoutes, allowlist, ceiling);
  console.log(`Canned-result baseline (${Object.keys(allowlist.cannedBaseline).length}):\n${Object.entries(allowlist.cannedBaseline).map(([key, reason]) => `  ${key} - ${reason}`).join('\n')}`);
  assert.deepEqual(decision.grownCanned, [], `New canned-result handler(s) ${decision.grownCanned.join(', ')}: call an authority (python runner, worker, provider) instead of returning literals.`);
  assert.deepEqual(decision.staleCanned, [], `Canned baseline entries ${decision.staleCanned.join(', ')} no longer match: remove them (the baseline only shrinks).`);
});
