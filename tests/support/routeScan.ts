// Static route discovery and canned-result classification for tests/route-authority.test.ts
// (Phase 7 slice 1). Discovery reports, never skips: any .get/.post/.put/.delete/.patch/.all/
// .use/.route call (any receiver, element access included) or route table row that mentions
// '/api' and cannot be resolved becomes an UNRESOLVED entry that must be allowlisted.
import ts from 'typescript';

const HANDLER_METHODS = new Set(['get', 'post', 'put', 'delete', 'patch', 'all']);

// Recognised authority dispatch: the python runners, the LPBF worker, the AI/literature providers,
// and the injected archive/registry services. Any other call does NOT count as an authority, so a
// handler that answers with literals and only calls helpers is canned.
const AUTHORITY_CALLEES: readonly RegExp[] = [
  /^(physicsDeps\.|characterizationDeps\.)?runPythonScript$/, /^handlePythonDispatch$/, /^pythonIPCSupervisor\.\w+$/,
  /^lpbfWorker\.\w+$/, /^generateGpt6Response$/, /^fetch$/, /^collectApprovedSource$/,
  /^(service|bundles|comparison|campaigns|registry)\.\w+$/,
];

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

export function routeHandlers(file: string, text: string): RouteHandler[] {
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.ES2022, true, ts.ScriptKind.TS);
  const declarations = fileDeclarations(source);
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
