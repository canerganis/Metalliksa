// Static route discovery and canned-result classification for tests/route-authority.test.ts
// (Phase 7 slice 1). Discovery reports, never skips: any .get/.post/.put/.delete/.patch/.all/
// .use/.route call (any receiver, element access included) or route table row that mentions
// '/api' and cannot be resolved becomes an UNRESOLVED entry that must be allowlisted.
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import { resolveImport } from './importGraph';

const HANDLER_METHODS = new Set(['get', 'post', 'put', 'delete', 'patch', 'all']);

export interface RouteHandler { key: string; file: string; line: number; canned: boolean; unclassified: boolean }

export function calleeText(expression: ts.Expression): string {
  if (ts.isIdentifier(expression)) return expression.text;
  if (ts.isPropertyAccessExpression(expression)) return `${calleeText(expression.expression)}.${expression.name.text}`;
  if (expression.kind === ts.SyntaxKind.ThisKeyword) return 'this';
  if (ts.isParenthesizedExpression(expression) || ts.isNonNullExpression(expression)) return calleeText(expression.expression);
  return '?';
}

function isLiteralClaim(node: ts.Expression): boolean {
  return ts.isNumericLiteral(node) || node.kind === ts.SyntaxKind.TrueKeyword || node.kind === ts.SyntaxKind.FalseKeyword
    || (ts.isPrefixUnaryExpression(node) && ts.isNumericLiteral(node.operand));
}

// --- Canned-result classification (review fix round 2, item 4) ------------------------------
//
// A handler is canned when a response sink (res.json/send/jsonp/end) receives a value with a
// literal number/boolean claim and the handler calls no RECOGNISED authority. Literals are
// followed through handler locals, lexical/module constants, constants and helper functions
// imported from other repository modules, ternaries and ??/||/&&, Object.assign,
// JSON.stringify, `X.field` / `X[0]` / `X.filter(...)` reads of constant values, and nesting.

// Authorities recognised by import origin. A local object or function with the same name does
// not count.
const AUTHORITY_IMPORTS: Readonly<Record<string, RegExp>> = {
  runPythonScript: /\/server\/processOrchestrator(\.ts)?$/,
  pythonIPCSupervisor: /\/server\/processOrchestrator(\.ts)?$/,
  lpbfWorker: /\/server\/lpbfWorkerBridge(\.ts)?$/,
  generateGpt6Response: /\/server\/openaiService(\.ts)?$/,
  collectApprovedSource: /\/server\/approvedSourceCollector(\.ts)?$/,
};
// Injected archive/registry services: recognised only when the receiver is a parameter or
// constant initialised with `new <Class>()` and the class is imported from server/.
const INJECTED_SERVICE_CLASSES = new Set(['LpbfRunArchiveService', 'LpbfRunBundleService', 'LpbfNistComparisonService',
  'LpbfNistProxyCampaignService', 'LpbfSourceArchiveService', 'ResearchEvidenceRegistry']);
// fetch() counts only for the Crossref literature provider URL builder.
const PROVIDER_URL_BUILDERS: Readonly<Record<string, RegExp>> = { researchSearchUrl: /\/server\/researchSearch(\.ts)?$/ };
const RESPONSE_SINKS = new Set(['json', 'send', 'jsonp', 'end']);
// Request acknowledgements: only a literal boolean under these keys is transport status.
const ACK_KEYS = new Set(['success', 'ok']);

interface FileContext {
  source: ts.SourceFile;
  absPath: string | null;
  declarations: Map<string, ts.Expression>;
  functions: Map<string, ts.FunctionLikeDeclaration>;
  imports: Map<string, { specifier: string; imported: string }>;
}
type Resolved = { kind: 'value'; node: ts.Expression; ctx: FileContext } | { kind: 'function'; node: ts.FunctionLikeDeclaration; ctx: FileContext };

const contextCache = new Map<string, FileContext>();

export function fileContext(source: ts.SourceFile, absPath: string | null, cache = true): FileContext {
  if (cache && absPath && contextCache.has(absPath)) return contextCache.get(absPath)!;
  const ctx: FileContext = { source, absPath, declarations: new Map(), functions: new Map(), imports: new Map() };
  const visit = (node: ts.Node) => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) {
      const init = node.initializer;
      if (ts.isArrowFunction(init) || ts.isFunctionExpression(init)) { if (!ctx.functions.has(node.name.text)) ctx.functions.set(node.name.text, init); }
      else if (!ctx.declarations.has(node.name.text)) ctx.declarations.set(node.name.text, init);
    }
    if (ts.isFunctionDeclaration(node) && node.name && !ctx.functions.has(node.name.text)) ctx.functions.set(node.name.text, node);
    if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier) && node.importClause?.namedBindings
      && ts.isNamedImports(node.importClause.namedBindings)) {
      for (const element of node.importClause.namedBindings.elements) {
        ctx.imports.set(element.name.text, { specifier: node.moduleSpecifier.text, imported: (element.propertyName ?? element.name).text });
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  if (cache && absPath) contextCache.set(absPath, ctx);
  return ctx;
}

function importedContext(ctx: FileContext, name: string): { ctx: FileContext; imported: string } | undefined {
  const binding = ctx.imports.get(name);
  if (!binding || !ctx.absPath) return undefined;
  const target = resolveImport(binding.specifier, ctx.absPath);
  if (!target || !/\.(ts|tsx)$/.test(target)) return undefined;
  const source = ts.createSourceFile(target, readFileSync(target, 'utf8'), ts.ScriptTarget.ES2022, true, target.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  return { ctx: fileContext(source, target), imported: binding.imported };
}

const importMatches = (ctx: FileContext, name: string, pattern: RegExp | undefined) => {
  const binding = ctx.imports.get(name);
  return !!binding && !!pattern && pattern.test(binding.specifier.replace(/^\.\.?/, ''));
};

function resolveName(name: string, at: ts.Node, ctx: FileContext, locals: Map<string, ts.Expression>): Resolved | undefined {
  const local = locals.get(name);
  if (local) return { kind: 'value', node: local, ctx };
  if (at.getSourceFile() === ctx.source) {
    const lexical = resolveDeclaration(name, at);
    if (lexical) return ts.isArrowFunction(lexical) || ts.isFunctionExpression(lexical) ? { kind: 'function', node: lexical, ctx } : { kind: 'value', node: lexical, ctx };
  }
  const fn = ctx.functions.get(name);
  if (fn) return { kind: 'function', node: fn, ctx };
  const value = ctx.declarations.get(name);
  if (value) return { kind: 'value', node: value, ctx };
  const imported = importedContext(ctx, name);
  if (imported) {
    const target = imported.ctx;
    const importedFn = target.functions.get(imported.imported);
    if (importedFn) return { kind: 'function', node: importedFn, ctx: target };
    const importedValue = target.declarations.get(imported.imported);
    if (importedValue) return { kind: 'value', node: importedValue, ctx: target };
  }
  return undefined;
}

function returnedExpressions(fn: ts.FunctionLikeDeclaration): ts.Expression[] {
  if (fn.body && !ts.isBlock(fn.body)) return [fn.body as ts.Expression];
  const found: ts.Expression[] = [];
  const visit = (node: ts.Node) => {
    if (ts.isReturnStatement(node) && node.expression) found.push(node.expression);
    if (node !== fn && ts.isFunctionLike(node)) return; // nested functions return elsewhere
    ts.forEachChild(node, visit);
  };
  if (fn.body) visit(fn.body);
  return found;
}

const isNullish = (node: ts.Expression) => node.kind === ts.SyntaxKind.NullKeyword || (ts.isIdentifier(node) && node.text === 'undefined');
const isBooleanLiteral = (node: ts.Expression) => node.kind === ts.SyntaxKind.TrueKeyword || node.kind === ts.SyntaxKind.FalseKeyword;

function chainRoot(node: ts.Expression): ts.Expression {
  let current = node;
  while (ts.isPropertyAccessExpression(current) || ts.isElementAccessExpression(current) || ts.isNonNullExpression(current) || ts.isParenthesizedExpression(current)) current = current.expression;
  return current;
}

/** Literal number/boolean claims reachable from a response value. */
export function hasLiteralClaim(node: ts.Expression, ctx: FileContext, locals: Map<string, ts.Expression>, seen: Set<ts.Node> = new Set()): boolean {
  if (seen.has(node)) return false;
  seen.add(node);
  if (isLiteralClaim(node)) return true;
  if (ts.isParenthesizedExpression(node) || ts.isAsExpression(node) || ts.isSatisfiesExpression(node) || ts.isNonNullExpression(node)
    || ts.isAwaitExpression(node) || ts.isTypeAssertionExpression(node)) return hasLiteralClaim(node.expression, ctx, locals, seen);
  if (ts.isConditionalExpression(node)) return hasLiteralClaim(node.whenTrue, ctx, locals, seen) || hasLiteralClaim(node.whenFalse, ctx, locals, seen);
  if (ts.isBinaryExpression(node) && [ts.SyntaxKind.QuestionQuestionToken, ts.SyntaxKind.BarBarToken, ts.SyntaxKind.AmpersandAmpersandToken].includes(node.operatorToken.kind)) {
    return hasLiteralClaim(node.left, ctx, locals, seen) || hasLiteralClaim(node.right, ctx, locals, seen);
  }
  if (ts.isBinaryExpression(node) && [ts.SyntaxKind.AsteriskToken, ts.SyntaxKind.PlusToken, ts.SyntaxKind.MinusToken,
    ts.SyntaxKind.SlashToken, ts.SyntaxKind.AsteriskAsteriskToken].includes(node.operatorToken.kind)) {
    // Constant arithmetic (16 * 1024) is a literal; arithmetic on a runtime value is not.
    return hasLiteralClaim(node.left, ctx, locals, seen) && hasLiteralClaim(node.right, ctx, locals, seen);
  }
  if (ts.isIdentifier(node)) {
    const resolved = resolveName(node.text, node, ctx, locals);
    return resolved?.kind === 'value' ? hasLiteralClaim(resolved.node, resolved.ctx, resolved.ctx === ctx ? locals : new Map(), seen) : false;
  }
  if (ts.isArrayLiteralExpression(node)) {
    return node.elements.some(element => hasLiteralClaim(ts.isSpreadElement(element) ? element.expression : element, ctx, locals, seen));
  }
  if (ts.isObjectLiteralExpression(node)) {
    const error = node.properties.find(property => property.name && ts.isIdentifier(property.name) && property.name.text === 'error');
    // An error envelope needs a real (non-null) error value; `error: null` does not hide a result.
    if (error && (ts.isShorthandPropertyAssignment(error) || (ts.isPropertyAssignment(error) && !isNullish(error.initializer)))) return false;
    return node.properties.some(property => {
      if (ts.isPropertyAssignment(property)) {
        if (ts.isIdentifier(property.name) && ACK_KEYS.has(property.name.text) && isBooleanLiteral(property.initializer)) return false;
        return hasLiteralClaim(property.initializer, ctx, locals, seen);
      }
      if (ts.isShorthandPropertyAssignment(property)) return hasLiteralClaim(property.name, ctx, locals, seen);
      if (ts.isSpreadAssignment(property)) return hasLiteralClaim(property.expression, ctx, locals, seen);
      return false;
    });
  }
  if (ts.isPropertyAccessExpression(node) || ts.isElementAccessExpression(node)) {
    // X.field / X[0] of a constant value: judge the constant.
    const root = chainRoot(node);
    return ts.isIdentifier(root) ? hasLiteralClaim(root, ctx, locals, seen) : false;
  }
  if (ts.isCallExpression(node)) {
    const callee = calleeText(node.expression);
    if (callee === 'JSON.stringify' || callee === 'Object.assign') return node.arguments.some(argument => hasLiteralClaim(argument, ctx, locals, seen));
    if (ts.isIdentifier(node.expression)) {
      const resolved = resolveName(node.expression.text, node, ctx, locals);
      if (resolved?.kind === 'function') return returnedExpressions(resolved.node).some(value => hasLiteralClaim(value, resolved.ctx, new Map(), seen));
      return false;
    }
    if (ts.isPropertyAccessExpression(node.expression)) {
      // CATALOG.filter(...) / CATALOG.slice() on a constant value.
      const root = chainRoot(node.expression.expression);
      if (ts.isIdentifier(root)) {
        const resolved = resolveName(root.text, root, ctx, locals);
        if (resolved?.kind === 'value' && (ts.isArrayLiteralExpression(resolved.node) || ts.isObjectLiteralExpression(resolved.node))) {
          return hasLiteralClaim(resolved.node, resolved.ctx, new Map(), seen);
        }
      }
    }
  }
  return false;
}

/** True only for calls to the recognised authorities (see the tables above). */
export function isRecognisedAuthority(call: ts.CallExpression, ctx: FileContext, locals: Map<string, ts.Expression>, seen: Set<ts.Node> = new Set()): boolean {
  const callee = calleeText(call.expression);
  const [root, member] = callee.split('.');
  if (!root || root === '?') return false;
  if (importMatches(ctx, root, AUTHORITY_IMPORTS[root])) return true;
  if (root === 'fetch' && !member && call.arguments.length) {
    const urlArg = call.arguments[0];
    let url: ts.Expression | undefined = urlArg;
    if (ts.isIdentifier(urlArg)) { const resolved = resolveName(urlArg.text, urlArg, ctx, locals); url = resolved?.kind === 'value' ? resolved.node : undefined; }
    // `let url: URL; try { url = researchSearchUrl(q) }` — accept a recognised builder assigned to the variable.
    if (ts.isIdentifier(urlArg) && !url) {
      const fnScope = findEnclosingFunction(call);
      let assigned = false;
      const visit = (node: ts.Node) => {
        if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.EqualsToken && ts.isIdentifier(node.left) && node.left.text === urlArg.text
          && ts.isCallExpression(node.right) && ts.isIdentifier(node.right.expression) && importMatches(ctx, node.right.expression.text, PROVIDER_URL_BUILDERS[node.right.expression.text])) assigned = true;
        ts.forEachChild(node, visit);
      };
      if (fnScope) visit(fnScope);
      return assigned;
    }
    return !!url && ts.isCallExpression(url) && ts.isIdentifier(url.expression) && importMatches(ctx, url.expression.text, PROVIDER_URL_BUILDERS[url.expression.text]);
  }
  const resolved = resolveName(root, call, ctx, locals);
  if (!resolved) return false;
  if (resolved.kind === 'value') {
    let value = resolved.node;
    while (ts.isParenthesizedExpression(value) || ts.isAsExpression(value)) value = value.expression;
    // Injected service: `service = new LpbfRunArchiveService()` with the class imported from server/.
    if (member && ts.isNewExpression(value) && ts.isIdentifier(value.expression) && INJECTED_SERVICE_CLASSES.has(value.expression.text)
      && importMatches(resolved.ctx, value.expression.text, /\/server\//)) return true;
    // Dependency object: `const physicsDeps = { runPythonScript }` re-exposing a recognised import.
    if (member && ts.isObjectLiteralExpression(value)) {
      const property = value.properties.find(item => item.name && ts.isIdentifier(item.name) && item.name.text === member);
      const target = property && ts.isShorthandPropertyAssignment(property) ? property.name.text
        : property && ts.isPropertyAssignment(property) && ts.isIdentifier(property.initializer) ? property.initializer.text : undefined;
      return !!target && importMatches(resolved.ctx, target, AUTHORITY_IMPORTS[target]);
    }
    return false;
  }
  // A local helper (e.g. handlePythonDispatch) counts when its own body calls a recognised authority.
  if (seen.has(resolved.node)) return false;
  seen.add(resolved.node);
  let found = false;
  const visit = (node: ts.Node) => {
    if (found) return;
    if (ts.isCallExpression(node) && isRecognisedAuthority(node, resolved.ctx, new Map(), seen)) found = true;
    ts.forEachChild(node, visit);
  };
  if (resolved.node.body) visit(resolved.node.body);
  return found;
}

function findEnclosingFunction(node: ts.Node): ts.Node | undefined {
  for (let current = node.parent; current; current = current.parent) if (ts.isFunctionLike(current)) return current;
  return undefined;
}

/** True when the handler answers with literal numbers/booleans and calls no recognised authority. */
export function isCanned(handlerNodes: readonly ts.Node[], ctx: FileContext): boolean {
  const locals = new Map<string, ts.Expression>();
  const responses: ts.Expression[] = [];
  let authorityCall = false;
  const visit = (node: ts.Node) => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) locals.set(node.name.text, node.initializer);
    if (ts.isCallExpression(node)) {
      if (isRecognisedAuthority(node, ctx, locals)) authorityCall = true;
      if (ts.isPropertyAccessExpression(node.expression) && RESPONSE_SINKS.has(node.expression.name.text)) responses.push(...node.arguments);
    }
    ts.forEachChild(node, visit);
  };
  handlerNodes.forEach(visit);
  return !authorityCall && responses.some(response => hasLiteralClaim(response, ctx, locals));
}

const isFunctionLike = (node: ts.Node) => ts.isArrowFunction(node) || ts.isFunctionExpression(node);

/** Function bodies the classifier can analyse, or null when the handler shape is not recognised. */
function handlerBodies(args: readonly ts.Expression[]): ts.Node[] | null {
  const bodies: ts.Node[] = [];
  for (const argument of args) {
    if (isFunctionLike(argument)) bodies.push(argument);
    else if (ts.isCallExpression(argument) && argument.arguments.some(isFunctionLike)) bodies.push(argument);
  }
  return bodies.length ? bodies : null;
}

/** Nearest lexical declaration of ``name`` visible from ``from`` (block / function / file scope). */
function resolveDeclaration(name: string, from: ts.Node): ts.Expression | undefined {
  for (let scope: ts.Node | undefined = from.parent; scope; scope = scope.parent) {
    if (ts.isFunctionLike(scope)) {
      for (const parameter of scope.parameters) {
        if (ts.isIdentifier(parameter.name) && parameter.name.text === name) return parameter.initializer;
      }
    }
    const statements = (ts.isBlock(scope) || ts.isSourceFile(scope) || ts.isModuleBlock(scope) || ts.isCaseClause(scope) || ts.isDefaultClause(scope))
      ? scope.statements : undefined;
    if (!statements) continue;
    for (const statement of statements) {
      if (!ts.isVariableStatement(statement)) continue;
      for (const declaration of statement.declarationList.declarations) {
        if (ts.isIdentifier(declaration.name) && declaration.name.text === name) return declaration.initializer;
      }
    }
  }
  return undefined;
}

/** Statically known string values of a path expression, or null. */
export function resolveStrings(node: ts.Expression, depth = 0): string[] | null {
  if (depth > 8) return null;
  if (ts.isStringLiteralLike(node)) return [node.text];
  if (ts.isParenthesizedExpression(node) || ts.isAsExpression(node) || ts.isSatisfiesExpression(node)) return resolveStrings(node.expression, depth + 1);
  if (ts.isIdentifier(node)) {
    const value = resolveDeclaration(node.text, node);
    return value ? resolveStrings(value, depth + 1) : null;
  }
  if (ts.isArrayLiteralExpression(node)) {
    const parts = node.elements.map(element => resolveStrings(element as ts.Expression, depth + 1));
    return parts.every(Boolean) ? (parts as string[][]).flat() : null;
  }
  if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken) {
    const left = resolveStrings(node.left, depth + 1); const right = resolveStrings(node.right, depth + 1);
    return left?.length === 1 && right?.length === 1 ? [left[0] + right[0]] : null;
  }
  if (ts.isTemplateExpression(node)) {
    let text = node.head.text;
    for (const span of node.templateSpans) {
      const value = resolveStrings(span.expression, depth + 1);
      if (value?.length !== 1) return null;
      text += value[0] + span.literal.text;
    }
    return [text];
  }
  return null;
}

/** Route-call method name: `x.get`, `x['get']`; '?' for a computed key; undefined otherwise. */
function routeMethod(callee: ts.Expression): string | undefined {
  if (ts.isPropertyAccessExpression(callee)) return callee.name.text;
  if (ts.isElementAccessExpression(callee)) {
    return ts.isStringLiteralLike(callee.argumentExpression) ? callee.argumentExpression.text : '?';
  }
  return undefined;
}

const mentionsApi = (node: ts.Node) => node.getText().includes('/api');

/**
 * The only receiver exempt from path resolution: a prepared SQL statement
 * (`db.prepare(sql).get(a, b)` / `.all(...)`), recognised by the direct `.prepare(...)` call.
 */
function isStatementObject(receiver: ts.Expression): boolean {
  return ts.isCallExpression(receiver) && routeMethod(receiver.expression) === 'prepare';
}

/** ``file`` is repo-relative; a file outside the repo (synthetic samples) resolves no imports. */
export function routeHandlers(file: string, text: string, absPath: string | null = null): RouteHandler[] {
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.ES2022, true, ts.ScriptKind.TS);
  const declarations = fileContext(source, absPath, false);
  const handlers: RouteHandler[] = [];
  const tableLoops = new Set<ts.Node>();
  const tableRows = new Set<ts.Node>();
  const lineOf = (node: ts.Node) => source.getLineAndCharacterOfPosition(node.getStart()).line + 1;
  const unresolved = (node: ts.Node) => {
    const snippet = node.getText().replace(/\s+/g, ' ').slice(0, 80);
    handlers.push({ key: `UNRESOLVED ${file}: ${snippet}`, file, line: lineOf(node), canned: false, unclassified: true });
  };
  const add = (method: string, paths: string[], node: ts.Node, bodies: readonly ts.Node[] | null, forceUnclassified = false) => {
    const unclassified = forceUnclassified || bodies === null;
    const canned = bodies !== null && isCanned(bodies, declarations);
    for (const route of paths) {
      if (route.startsWith('/api')) handlers.push({ key: `${method.toUpperCase()} ${route}`, file, line: lineOf(node), canned, unclassified });
    }
  };
  const routeChainPath = (receiver: ts.Expression): ts.Expression | undefined => {
    // router.route('/api/x').get(h)  or  const r = router.route('/api/x'); r.get(h)
    let target: ts.Expression | undefined = receiver;
    if (ts.isIdentifier(receiver)) target = resolveDeclaration(receiver.text, receiver);
    if (target && ts.isCallExpression(target) && routeMethod(target.expression) === 'route' && target.arguments.length) return target.arguments[0];
    return undefined;
  };

  // Pass 1: table-driven loops: for (const [method, route] of [[...], ...] | TABLE) x[method](route, h)
  const findTables = (node: ts.Node) => {
    if (ts.isForOfStatement(node)) {
      let table: ts.Expression | undefined = node.expression;
      if (ts.isIdentifier(table)) table = resolveDeclaration(table.text, table);
      while (table && (ts.isAsExpression(table) || ts.isSatisfiesExpression(table))) table = table.expression;
      if (table && ts.isArrayLiteralExpression(table) && table.elements.some(row => ts.isArrayLiteralExpression(row) && mentionsApi(row))) {
        tableLoops.add(node.statement);
        for (const row of table.elements) {
          tableRows.add(row);
          if (!ts.isArrayLiteralExpression(row) || row.elements.length < 2) { if (mentionsApi(row)) unresolved(row); continue; }
          const [method, route] = row.elements;
          const paths = resolveStrings(route as ts.Expression);
          if (ts.isStringLiteralLike(method) && HANDLER_METHODS.has(method.text) && paths) add(method.text, paths, row, [node.statement]);
          else if (mentionsApi(row)) unresolved(row);
        }
      }
    }
    ts.forEachChild(node, findTables);
  };
  findTables(source);

  const insideTableLoop = (node: ts.Node) => { for (let n = node.parent; n; n = n.parent) if (tableLoops.has(n)) return true; return false; };

  // Pass 2: route calls on any receiver, and stray route tables.
  const visit = (node: ts.Node) => {
    if (ts.isArrayLiteralExpression(node) && !tableRows.has(node) && node.elements.length >= 2
      && node.elements.some(element => ts.isStringLiteralLike(element) && HANDLER_METHODS.has(element.text.toLowerCase()))
      && node.elements.some(element => ts.isStringLiteralLike(element) && element.text.startsWith('/api'))) {
      unresolved(node); // A [method, '/api/...'] row outside a recognised loop.
    }
    if (ts.isCallExpression(node)) {
      const method = routeMethod(node.expression);
      const receiver = ts.isPropertyAccessExpression(node.expression) || ts.isElementAccessExpression(node.expression) ? node.expression.expression : undefined;
      const args = node.arguments;
      if (method === '?') {
        if (!insideTableLoop(node) && (args.length >= 2 || args.some(mentionsApi))) unresolved(node);
      } else if (method && HANDLER_METHODS.has(method) && receiver) {
        const chained = routeChainPath(receiver);
        if (chained) {
          const paths = resolveStrings(chained);
          if (paths) add(method, paths, node, handlerBodies(args)); else unresolved(node);
        } else if (args.length >= 2) {
          const paths = resolveStrings(args[0]);
          if (paths === null && isStatementObject(receiver)) { /* SQL statement .get/.all(params): not a route. */ }
          else if (paths === null) unresolved(node);
          else add(method, paths, node, handlerBodies(args.slice(1)));
        } else if (args.length === 1 && isFunctionLike(args[0])) {
          unresolved(node); // A handler registered without a resolvable path.
        }
      } else if (method === 'use' && args.length && (args.some(mentionsApi) || resolveStrings(args[0])?.some(value => value.startsWith('/api')))) {
        const paths = resolveStrings(args[0]);
        if (paths) add('use', paths, node, handlerBodies(args.slice(1)), true); else unresolved(node);
      } else if (method === 'route' && args.length && mentionsApi(args[0]) && resolveStrings(args[0]) === null) {
        unresolved(node);
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return handlers;
}
