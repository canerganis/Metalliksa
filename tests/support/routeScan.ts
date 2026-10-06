// Static route discovery and canned-result classification for tests/route-authority.test.ts
// (Phase 7 slice 1). Discovery reports, never skips: any .get/.post/.put/.delete/.patch/.all/
// .options/.head/.use/.route call (any receiver, element access included, also through
// .call/.apply/.bind) or route table row that mentions '/api' and cannot be resolved becomes
// an UNRESOLVED entry that must be allowlisted. Relative routes of a sub-router mounted under
// an /api prefix (same file or imported) are reported under the joined path.
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import { rel, resolveImport } from './importGraph';

const HANDLER_METHODS = new Set(['get', 'post', 'put', 'delete', 'patch', 'all', 'options', 'head']);
// Every method name that registers a route or a mount.
const ROUTE_VERBS = new Set([...HANDLER_METHODS, 'use', 'route']);
// Function.prototype invokers that register a route indirectly: router.post.call(router, ...).
const INVOKERS = new Set(['call', 'apply', 'bind']);

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

// --- Canned-result classification (review fix round 2, item 4; p7 re-audit follow-ups) ------
//
// A handler is canned when a response sink (res.json/send/jsonp/end/write) receives a value with
// a literal number/boolean claim and no RECOGNISED authority call covers that response. Literals
// are followed through handler locals (including `r.v = 1` / Object.assign(r, ...) fills of a
// declared object), lexical/module constants, constants and helper functions imported from other
// repository modules (named, default and namespace imports), methods of constant helper objects
// (`H.make()`), ternaries and ??/||/&&, Object.assign, JSON.stringify, `X.field` / `X[0]` /
// `X.filter(...)` reads of constant values, and nesting. Fallbacks are a catch block, a promise
// .catch / .then rejection callback, and the branch taken when an authority result is missing
// (`if (!out)`, `out == null`, the else of `if (out)`, `out ? ... : <here>`). A response is
// covered only by an authority call in the same innermost fallback (or by one outside every
// fallback when the response is outside every fallback): a successful-path authority call does
// not excuse a canned fallback, and an authority call inside a fallback does not excuse a canned
// response outside it.

// Authorities recognised by import origin. A local object or function with the same name does
// not count.
const AUTHORITY_IMPORTS: Readonly<Record<string, RegExp>> = {
  runPythonScript: /\/server\/processOrchestrator(\.ts)?$/,
  pythonIPCSupervisor: /\/server\/processOrchestrator(\.ts)?$/,
  lpbfWorker: /\/server\/lpbfWorkerBridge(\.ts)?$/,
  generateGpt6Response: /\/server\/openaiService(\.ts)?$/,
};
// Injected archive/registry services: recognised only when the receiver is a parameter or
// constant initialised with `new <Class>()` and the class is imported from server/.
const INJECTED_SERVICE_CLASSES = new Set(['LpbfRunArchiveService', 'LpbfRunBundleService', 'LpbfNistComparisonService',
  'LpbfNistProxyCampaignService', 'LpbfSourceArchiveService', 'ResearchEvidenceRegistry']);
// fetch() counts only for the Crossref literature provider URL builder.
const PROVIDER_URL_BUILDERS: Readonly<Record<string, RegExp>> = { researchSearchUrl: /\/server\/researchSearch(\.ts)?$/ };
const RESPONSE_SINKS = new Set(['json', 'send', 'jsonp', 'end', 'write']);
// Request acknowledgements: only a literal boolean under these keys is transport status.
const ACK_KEYS = new Set(['success', 'ok']);

interface FileContext {
  source: ts.SourceFile;
  absPath: string | null;
  declarations: Map<string, ts.Expression>;
  functions: Map<string, ts.FunctionLikeDeclaration>;
  // imported is the exported name, 'default' for a default import or '*' for a namespace import.
  imports: Map<string, { specifier: string; imported: string }>;
}
type Resolved = { kind: 'value'; node: ts.Expression; ctx: FileContext } | { kind: 'function'; node: ts.FunctionLikeDeclaration; ctx: FileContext };

const contextCache = new Map<string, FileContext>();
const hasDefaultModifier = (node: ts.Node) => !!ts.canHaveModifiers(node) && !!ts.getModifiers(node)?.some(modifier => modifier.kind === ts.SyntaxKind.DefaultKeyword);

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
    if (ts.isFunctionDeclaration(node) && node.parent === source && hasDefaultModifier(node)) ctx.functions.set('default', node);
    if (ts.isExportAssignment(node) && !node.isExportEquals) {
      const value = node.expression;
      if (ts.isArrowFunction(value) || ts.isFunctionExpression(value)) ctx.functions.set('default', value);
      else ctx.declarations.set('default', value);
    }
    if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier) && node.importClause) {
      const specifier = node.moduleSpecifier.text;
      const { name, namedBindings } = node.importClause;
      if (name) ctx.imports.set(name.text, { specifier, imported: 'default' });
      if (namedBindings && ts.isNamespaceImport(namedBindings)) ctx.imports.set(namedBindings.name.text, { specifier, imported: '*' });
      if (namedBindings && ts.isNamedImports(namedBindings)) {
        for (const element of namedBindings.elements) {
          ctx.imports.set(element.name.text, { specifier, imported: (element.propertyName ?? element.name).text });
        }
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  if (cache && absPath) contextCache.set(absPath, ctx);
  return ctx;
}

function loadContext(target: string): FileContext {
  const cached = contextCache.get(target);
  if (cached) return cached;
  const source = ts.createSourceFile(target, readFileSync(target, 'utf8'), ts.ScriptTarget.ES2022, true, target.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  return fileContext(source, target);
}

function importedContext(ctx: FileContext, name: string): { ctx: FileContext; imported: string } | undefined {
  const binding = ctx.imports.get(name);
  if (!binding || !ctx.absPath) return undefined;
  const target = resolveImport(binding.specifier, ctx.absPath);
  if (!target || !/\.(ts|tsx)$/.test(target)) return undefined;
  return { ctx: loadContext(target), imported: binding.imported };
}

const importMatches = (ctx: FileContext, name: string, pattern: RegExp | undefined) => {
  const binding = ctx.imports.get(name);
  return !!binding && !!pattern && pattern.test(binding.specifier.replace(/^\.\.?/, ''));
};

function unwrap(node: ts.Expression): ts.Expression {
  let current = node;
  while (ts.isParenthesizedExpression(current) || ts.isAsExpression(current) || ts.isSatisfiesExpression(current)
    || ts.isNonNullExpression(current) || ts.isTypeAssertionExpression(current)) current = current.expression;
  return current;
}

const propertyNameText = (name: ts.PropertyName): string | undefined =>
  ts.isIdentifier(name) || ts.isStringLiteral(name) || ts.isNumericLiteral(name) || ts.isNoSubstitutionTemplateLiteral(name) ? name.text : undefined;

/** An exported binding of ``target``: function, value, or an exported alias followed once more. */
function exportedBinding(target: FileContext, exported: string, depth: number): Resolved | undefined {
  const fn = target.functions.get(exported);
  if (fn) return { kind: 'function', node: fn, ctx: target };
  const value = target.declarations.get(exported);
  if (!value) return undefined;
  // `export default canned` / `const alias = canned`: follow the identifier inside the target.
  if (ts.isIdentifier(value) && depth < 6) return resolveName(value.text, value, target, new Map(), depth + 1) ?? { kind: 'value', node: value, ctx: target };
  return { kind: 'value', node: value, ctx: target };
}

function resolveName(name: string, at: ts.Node, ctx: FileContext, locals: Map<string, ts.Expression>, depth = 0): Resolved | undefined {
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
  if (imported && imported.imported !== '*') return exportedBinding(imported.ctx, imported.imported, depth);
  return undefined;
}

/** `NS.member` of a namespace import (`import * as NS from './x'`), resolved in the target module. */
function namespaceMember(ctx: FileContext, name: string, member: string): Resolved | undefined {
  const imported = importedContext(ctx, name);
  return imported?.imported === '*' ? exportedBinding(imported.ctx, member, 0) : undefined;
}

/**
 * `X.member` where X is a namespace import or (a member chain ending in) a constant object
 * literal: `H.make`, `NS.HELPERS.build`, `const H = { make() {...} }`.
 */
function resolveMember(object: ts.Expression, member: string, ctx: FileContext, locals: Map<string, ts.Expression>): Resolved | undefined {
  const target = unwrap(object);
  if (ts.isIdentifier(target)) {
    const fromNamespace = namespaceMember(ctx, target.text, member);
    if (fromNamespace) return fromNamespace;
  }
  const owner = ts.isIdentifier(target) ? resolveName(target.text, target, ctx, locals)
    : ts.isPropertyAccessExpression(target) ? resolveMember(target.expression, target.name.text, ctx, locals) : undefined;
  if (owner?.kind !== 'value') return undefined;
  const value = unwrap(owner.node);
  if (!ts.isObjectLiteralExpression(value)) return undefined;
  for (const property of value.properties) {
    if (!property.name || propertyNameText(property.name) !== member) continue;
    if (ts.isMethodDeclaration(property)) return { kind: 'function', node: property, ctx: owner.ctx };
    if (ts.isPropertyAssignment(property)) {
      const initializer = unwrap(property.initializer);
      return ts.isArrowFunction(initializer) || ts.isFunctionExpression(initializer)
        ? { kind: 'function', node: initializer, ctx: owner.ctx } : { kind: 'value', node: property.initializer, ctx: owner.ctx };
    }
    if (ts.isShorthandPropertyAssignment(property)) return resolveName(property.name.text, property.name, owner.ctx, owner.ctx === ctx ? locals : new Map());
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

const isBooleanLiteral = (node: ts.Expression) => node.kind === ts.SyntaxKind.TrueKeyword || node.kind === ts.SyntaxKind.FalseKeyword;

/** null, undefined, void x, false, '' and 0 (also through constants): an error value that is not an error. */
function isFalsyValue(node: ts.Expression, ctx: FileContext, locals: Map<string, ts.Expression>, depth = 0): boolean {
  const value = unwrap(node);
  if (value.kind === ts.SyntaxKind.NullKeyword || value.kind === ts.SyntaxKind.FalseKeyword || ts.isVoidExpression(value)) return true;
  if (ts.isStringLiteralLike(value)) return value.text === '';
  if (ts.isNumericLiteral(value)) return Number(value.text) === 0;
  if (ts.isIdentifier(value)) {
    if (value.text === 'undefined') return true;
    const resolved = depth < 6 ? resolveName(value.text, value, ctx, locals) : undefined;
    return resolved?.kind === 'value' && isFalsyValue(resolved.node, resolved.ctx, resolved.ctx === ctx ? locals : new Map(), depth + 1);
  }
  return false;
}

function chainRoot(node: ts.Expression): ts.Expression {
  let current = node;
  while (ts.isPropertyAccessExpression(current) || ts.isElementAccessExpression(current) || ts.isNonNullExpression(current) || ts.isParenthesizedExpression(current)) current = current.expression;
  return current;
}

/** Name of the first member read off ``root`` in a property chain (`NS.A.b` -> 'A'). */
function firstMember(node: ts.Expression, root: ts.Expression): string | undefined {
  let current: ts.Expression = node;
  while (ts.isPropertyAccessExpression(current) || ts.isElementAccessExpression(current) || ts.isNonNullExpression(current) || ts.isParenthesizedExpression(current)) {
    if ((ts.isPropertyAccessExpression(current) || ts.isElementAccessExpression(current)) && unwrap(current.expression) === root) {
      if (ts.isPropertyAccessExpression(current)) return current.name.text;
      return ts.isStringLiteralLike(current.argumentExpression) ? current.argumentExpression.text : undefined;
    }
    current = current.expression;
  }
  return undefined;
}

// `const r = {}; r.v = 1; r['w'] = true; Object.assign(r, {...})`: values written into a
// declared object after its declaration (within the declaring function or file).
interface Fill { key: string | undefined; value: ts.Expression }
const fillCache = new WeakMap<ts.Node, Fill[]>();

function fillsOf(declared: ts.Expression): Fill[] {
  const declaration = declared.parent;
  if (!declaration || !ts.isVariableDeclaration(declaration) || declaration.initializer !== declared || !ts.isIdentifier(declaration.name)) return [];
  const name = declaration.name.text;
  const cached = fillCache.get(declaration);
  if (cached) return cached;
  let scope: ts.Node = declaration;
  while (scope.parent && !ts.isFunctionLike(scope) && !ts.isSourceFile(scope)) scope = scope.parent;
  const fills: Fill[] = [];
  const isTarget = (node: ts.Expression) => { const root = unwrap(node); return ts.isIdentifier(root) && root.text === name; };
  const visit = (node: ts.Node) => {
    if (ts.isBinaryExpression(node) && node.operatorToken.kind >= ts.SyntaxKind.FirstAssignment && node.operatorToken.kind <= ts.SyntaxKind.LastAssignment
      && (ts.isPropertyAccessExpression(node.left) || ts.isElementAccessExpression(node.left)) && isTarget(chainRoot(node.left))) {
      const direct = isTarget(node.left.expression);
      const key = !direct ? undefined : ts.isPropertyAccessExpression(node.left) ? node.left.name.text
        : ts.isStringLiteralLike(node.left.argumentExpression) ? node.left.argumentExpression.text : undefined;
      fills.push({ key, value: node.right });
    }
    if (ts.isCallExpression(node) && calleeText(node.expression) === 'Object.assign' && node.arguments.length > 1 && isTarget(node.arguments[0])) {
      for (const source of node.arguments.slice(1)) fills.push({ key: undefined, value: ts.isSpreadElement(source) ? source.expression : source });
    }
    ts.forEachChild(node, visit);
  };
  visit(scope);
  fillCache.set(declaration, fills);
  return fills;
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
    if (resolved?.kind !== 'value') return false;
    const scope = resolved.ctx === ctx ? locals : new Map<string, ts.Expression>();
    const fills = fillsOf(resolved.node);
    // A real error written into the object makes it an error envelope, as in an object literal.
    if (fills.some(fill => fill.key === 'error' && !isFalsyValue(fill.value, resolved.ctx, scope))) return false;
    return hasLiteralClaim(resolved.node, resolved.ctx, scope, seen)
      || fills.some(fill => !(fill.key && ACK_KEYS.has(fill.key) && isBooleanLiteral(fill.value)) && hasLiteralClaim(fill.value, resolved.ctx, scope, seen));
  }
  if (ts.isArrayLiteralExpression(node)) {
    return node.elements.some(element => hasLiteralClaim(ts.isSpreadElement(element) ? element.expression : element, ctx, locals, seen));
  }
  if (ts.isObjectLiteralExpression(node)) {
    const error = node.properties.find(property => property.name && propertyNameText(property.name) === 'error');
    // An error envelope needs a real error value; `error: null | undefined | false | '' | 0`
    // (directly or through a constant) does not hide a result.
    const errorValue = error && ts.isShorthandPropertyAssignment(error) ? error.name : error && ts.isPropertyAssignment(error) ? error.initializer : undefined;
    if (errorValue && !isFalsyValue(errorValue, ctx, locals)) return false;
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
    // X.field / X[0] of a constant value: judge the constant. NS.CONST of a namespace import:
    // judge the imported constant.
    const root = chainRoot(node);
    if (!ts.isIdentifier(root)) return false;
    const member = firstMember(node, root);
    const fromNamespace = member === undefined ? undefined : namespaceMember(ctx, root.text, member);
    if (fromNamespace) return fromNamespace.kind === 'value' && hasLiteralClaim(fromNamespace.node, fromNamespace.ctx, new Map(), seen);
    return hasLiteralClaim(root, ctx, locals, seen);
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
      // H.make() of a helper object / NS.helper() of a namespace import: judge what it returns.
      const method = resolveMember(node.expression.expression, node.expression.name.text, ctx, locals);
      if (method?.kind === 'function') return returnedExpressions(method.node).some(value => hasLiteralClaim(value, method.ctx, new Map(), seen));
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
  // NS.runPythonScript(...) through `import * as NS from '../server/processOrchestrator'`.
  if (member && ctx.imports.get(root)?.imported === '*' && importMatches(ctx, root, AUTHORITY_IMPORTS[member])) return true;
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

/** A promise rejection callback: `p.catch(fn)` or the second argument of `p.then(ok, fn)`. */
function isRejectionCallback(node: ts.Node): boolean {
  if (!isFunctionLike(node) || !ts.isCallExpression(node.parent) || !ts.isPropertyAccessExpression(node.parent.expression)) return false;
  const name = node.parent.expression.name.text;
  const index = node.parent.arguments.indexOf(node as ts.Expression);
  return (name === 'catch' && index === 0) || (name === 'then' && index === 1);
}

/** True when a response answers with literal numbers/booleans and no recognised authority call covers it. */
export function isCanned(handlerNodes: readonly ts.Node[], ctx: FileContext): boolean {
  const locals = new Map<string, ts.Expression>();
  const responses: { value: ts.Expression; at: ts.Node }[] = [];
  const authorities: ts.Node[] = [];
  const visit = (node: ts.Node) => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) locals.set(node.name.text, node.initializer);
    if (ts.isCallExpression(node)) {
      if (isRecognisedAuthority(node, ctx, locals)) authorities.push(node);
      if (ts.isPropertyAccessExpression(node.expression) && RESPONSE_SINKS.has(node.expression.name.text)) responses.push(...node.arguments.map(value => ({ value, at: node })));
    }
    ts.forEachChild(node, visit);
  };
  handlerNodes.forEach(visit);
  const roots = new Set(handlerNodes);
  const inside = (node: ts.Node, region: ts.Node) => { for (let current: ts.Node | undefined = node; current; current = current.parent) if (current === region) return true; return false; };
  // Variables holding an authority result: `const out = await run()...` or `out = await run()`.
  const authorityValued = new Set<string>();
  for (const [name, initializer] of locals) if (authorities.some(call => inside(call, initializer))) authorityValued.add(name);
  const findAssignments = (node: ts.Node) => {
    if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.EqualsToken && ts.isIdentifier(node.left)
      && authorities.some(call => inside(call, node.right))) authorityValued.add(node.left.text);
    ts.forEachChild(node, findAssignments);
  };
  handlerNodes.forEach(findAssignments);
  const subject = (expression: ts.Expression) => { const root = chainRoot(unwrap(expression)); return ts.isIdentifier(root) && authorityValued.has(root.text); };
  const isNullish = (expression: ts.Expression) => { const value = unwrap(expression); return value.kind === ts.SyntaxKind.NullKeyword || (ts.isIdentifier(value) && value.text === 'undefined'); };
  /** `!out`, `out == null`, `out === undefined`: the authority result is missing. */
  const testsMissing = (condition: ts.Expression): boolean => {
    const value = unwrap(condition);
    if (ts.isPrefixUnaryExpression(value) && value.operator === ts.SyntaxKind.ExclamationToken) return subject(value.operand);
    if (ts.isBinaryExpression(value) && [ts.SyntaxKind.EqualsEqualsToken, ts.SyntaxKind.EqualsEqualsEqualsToken].includes(value.operatorToken.kind)) {
      return (isNullish(value.right) && subject(value.left)) || (isNullish(value.left) && subject(value.right));
    }
    return false;
  };
  /** `out`, `out != null`, `out !== undefined`: the authority result is present. */
  const testsPresent = (condition: ts.Expression): boolean => {
    const value = unwrap(condition);
    if (ts.isBinaryExpression(value) && [ts.SyntaxKind.ExclamationEqualsToken, ts.SyntaxKind.ExclamationEqualsEqualsToken].includes(value.operatorToken.kind)) {
      return (isNullish(value.right) && subject(value.left)) || (isNullish(value.left) && subject(value.right));
    }
    return !ts.isBinaryExpression(value) && !ts.isPrefixUnaryExpression(value) && subject(value);
  };
  /** The branch taken when an authority result is missing: `if (!out) <here>` / `if (out) ... else <here>` / `out ? x : <here>`. */
  const isMissingResultBranch = (node: ts.Node): boolean => {
    const parent = node.parent;
    if (ts.isIfStatement(parent)) {
      return (parent.thenStatement === node && testsMissing(parent.expression)) || (parent.elseStatement === node && testsPresent(parent.expression));
    }
    if (ts.isConditionalExpression(parent)) {
      return (parent.whenTrue === node && testsMissing(parent.condition)) || (parent.whenFalse === node && testsPresent(parent.condition));
    }
    return false;
  };
  // Innermost fallback around a node within the handler: a catch block, a promise rejection
  // callback, or the branch taken when an authority result is missing.
  const fallbackOf = (node: ts.Node): ts.Node | undefined => {
    for (let current: ts.Node | undefined = node; current && !roots.has(current); current = current.parent) {
      if (ts.isCatchClause(current) || isRejectionCallback(current) || isMissingResultBranch(current)) return current;
    }
    return undefined;
  };
  // A response is covered only by an authority call in the same innermost fallback (or, for a
  // response outside every fallback, by an authority call that is also outside every fallback).
  const covered = (at: ts.Node) => {
    const fallback = fallbackOf(at);
    return authorities.some(call => fallbackOf(call) === fallback);
  };
  return responses.some(response => !covered(response.at) && hasLiteralClaim(response.value, ctx, locals));
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

/** Mount prefix + sub-router route ('/api/x' + '/y' -> '/api/x/y'; '/' -> '/api/x'). */
export function joinRoute(prefix: string, route: string): string {
  if (route === '' || route === '/') return prefix;
  return `${prefix.replace(/\/+$/, '')}${route.startsWith('/') ? '' : '/'}${route}`;
}

/**
 * Allowlist key of a handler: method and path. A `use` mount is also keyed by its site: file
 * plus the ordinal of that path's mounts within the file ('USE /api/x (routes/a.ts#2)'), which
 * survives unrelated edits that move lines.
 */
const handlerKey = (method: string, route: string, file: string, ordinal: number) =>
  method === 'use' ? `USE ${route} (${file}#${ordinal})` : `${method.toUpperCase()} ${route}`;

/** The site-independent part of a key: 'USE /api/x (routes/a.ts#2)' -> 'USE /api/x'. */
export const siteless = (key: string) => key.replace(/ \([^()]+#\d+\)$/, '');

// A route registered with a non-/api path on a named receiver; reported only when that receiver
// is mounted under an /api prefix.
interface RelativeRoute { receiver: string; method: string; route: string; file: string; line: number; ordinal: number; canned: boolean; unclassified: boolean }
interface Mount { prefixes: string[]; name: string }
interface Scan { handlers: RouteHandler[]; relative: RelativeRoute[]; mounts: Mount[]; ctx: FileContext }
type RouteCall = { method: string; receiver: ts.Expression; args: readonly ts.Expression[]; anchor: ts.Node };

function scanFile(file: string, text: string, absPath: string | null): Scan {
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.ES2022, true, ts.ScriptKind.TS);
  const declarations = fileContext(source, absPath, false);
  const handlers: RouteHandler[] = [];
  const relative: RelativeRoute[] = [];
  const mounts: Mount[] = [];
  const tableLoops = new Set<ts.Node>();
  const tableRows = new Set<ts.Node>();
  const lineOf = (node: ts.Node) => source.getLineAndCharacterOfPosition(node.getStart()).line + 1;
  const unresolved = (node: ts.Node) => {
    const snippet = node.getText().replace(/\s+/g, ' ').slice(0, 80);
    handlers.push({ key: `UNRESOLVED ${file}: ${snippet}`, file, line: lineOf(node), canned: false, unclassified: true });
  };
  const add = (method: string, paths: string[], node: ts.Node, bodies: readonly ts.Node[] | null, forceUnclassified = false, receiver?: ts.Expression) => {
    const unclassified = forceUnclassified || bodies === null;
    const canned = bodies !== null && isCanned(bodies, declarations);
    const line = lineOf(node);
    const owner = receiver && ts.isIdentifier(unwrap(receiver)) ? (unwrap(receiver) as ts.Identifier).text : undefined;
    for (const route of paths) {
      const ordinal = method === 'use' ? nextOrdinal(route) : 0;
      if (route.startsWith('/api')) handlers.push({ key: handlerKey(method, route, file, ordinal), file, line, canned, unclassified });
      else if (owner) relative.push({ receiver: owner, method, route, file, line, ordinal, canned, unclassified });
    }
  };
  // n-th `use` mount of the same path in this file, in source order.
  const useOrdinals = new Map<string, number>();
  function nextOrdinal(route: string): number {
    const next = (useOrdinals.get(route) ?? 0) + 1;
    useOrdinals.set(route, next);
    return next;
  }
  const routeChainPath = (receiver: ts.Expression): ts.Expression | undefined => {
    // router.route('/api/x').get(h)  or  const r = router.route('/api/x'); r.get(h)
    let target: ts.Expression | undefined = receiver;
    if (ts.isIdentifier(receiver)) target = resolveDeclaration(receiver.text, receiver);
    if (target && ts.isCallExpression(target) && routeMethod(target.expression) === 'route' && target.arguments.length) return target.arguments[0];
    return undefined;
  };

  // Pass 0: `const post = router.post.bind(router, ...)` aliases; calls of the alias are routes.
  const bindAliases = new Map<string, { method: string; receiver: ts.Expression; bound: readonly ts.Expression[] }>();
  const boundTarget = (call: ts.CallExpression) => {
    if (routeMethod(call.expression) !== 'bind' || !(ts.isPropertyAccessExpression(call.expression) || ts.isElementAccessExpression(call.expression))) return undefined;
    const bound = call.expression.expression;
    if (!ts.isPropertyAccessExpression(bound) && !ts.isElementAccessExpression(bound)) return undefined;
    const method = routeMethod(bound);
    return method && (ROUTE_VERBS.has(method) || method === '?') ? { method, receiver: bound.expression, bound: call.arguments.slice(1) } : undefined;
  };
  const findAliases = (node: ts.Node) => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer && ts.isCallExpression(node.initializer)) {
      const target = boundTarget(node.initializer);
      if (target) bindAliases.set(node.name.text, target);
    }
    ts.forEachChild(node, findAliases);
  };
  findAliases(source);

  /**
   * The route call a CallExpression makes: direct (`r.get(...)`), through an invoker
   * (`r.get.call(r, ...)`, `.apply(r, [...])`, `.bind(r, ...)(...)`) or a bind alias; 'unresolved'
   * for an invoker form that cannot be followed; undefined when it is no route call.
   */
  const routeCall = (node: ts.CallExpression): RouteCall | 'unresolved' | 'alias' | undefined => {
    if (ts.isIdentifier(node.expression) && bindAliases.has(node.expression.text)) {
      const alias = bindAliases.get(node.expression.text)!;
      return { method: alias.method, receiver: alias.receiver, args: [...alias.bound, ...node.arguments], anchor: node };
    }
    const method = routeMethod(node.expression);
    if (!method || !(ts.isPropertyAccessExpression(node.expression) || ts.isElementAccessExpression(node.expression))) return undefined;
    const receiver = node.expression.expression;
    if (INVOKERS.has(method) && (ts.isPropertyAccessExpression(receiver) || ts.isElementAccessExpression(receiver))) {
      const inner = routeMethod(receiver);
      if (inner && (ROUTE_VERBS.has(inner) || inner === '?')) {
        const target = receiver.expression;
        if (method === 'call') return { method: inner, receiver: target, args: node.arguments.slice(1), anchor: node };
        if (method === 'apply') {
          const list = node.arguments[1];
          return list && ts.isArrayLiteralExpression(list) && !list.elements.some(ts.isSpreadElement)
            ? { method: inner, receiver: target, args: list.elements, anchor: node } : 'unresolved';
        }
        const parent = node.parent;
        if (ts.isCallExpression(parent) && parent.expression === node) {
          return { method: inner, receiver: target, args: [...node.arguments.slice(1), ...parent.arguments], anchor: parent };
        }
        if (ts.isVariableDeclaration(parent) && parent.initializer === node && ts.isIdentifier(parent.name)) return 'alias';
        return 'unresolved'; // A bound route method escaping static view (passed on, stored in an object, ...).
      }
    }
    return { method, receiver, args: node.arguments, anchor: node };
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

  const handleRouteCall = ({ method, receiver, args, anchor }: RouteCall) => {
    if (method === '?') {
      if (!insideTableLoop(anchor) && (args.length >= 2 || args.some(mentionsApi))) unresolved(anchor);
    } else if (HANDLER_METHODS.has(method)) {
      const chained = routeChainPath(receiver);
      if (chained) {
        const paths = resolveStrings(chained);
        if (paths) add(method, paths, anchor, handlerBodies(args), false, receiver); else unresolved(anchor);
      } else if (args.length >= 2) {
        const paths = resolveStrings(args[0]);
        if (paths === null && isStatementObject(receiver)) { /* SQL statement .get/.all(params): not a route. */ }
        else if (paths === null) unresolved(anchor);
        else add(method, paths, anchor, handlerBodies(args.slice(1)), false, receiver);
      } else if (args.length === 1 && isFunctionLike(args[0])) {
        unresolved(anchor); // A handler registered without a resolvable path.
      }
    } else if (method === 'use' && args.length) {
      const paths = resolveStrings(args[0]);
      const apiPaths = paths?.filter(value => value.startsWith('/api')) ?? [];
      if (args.some(mentionsApi) || apiPaths.length) {
        if (!paths) { unresolved(anchor); return; }
        add('use', paths, anchor, handlerBodies(args.slice(1)), true, receiver);
        for (const mounted of args.slice(1)) {
          const target = unwrap(mounted);
          if (ts.isIdentifier(target) && apiPaths.length) mounts.push({ prefixes: apiPaths, name: target.text });
        }
      } else if (paths) {
        add('use', paths, anchor, handlerBodies(args.slice(1)), true, receiver); // relative mount of a sub-router
      }
    } else if (method === 'route' && args.length && mentionsApi(args[0]) && resolveStrings(args[0]) === null) {
      unresolved(anchor);
    }
  };

  // Pass 2: route calls on any receiver, and stray route tables.
  const visit = (node: ts.Node) => {
    if (ts.isArrayLiteralExpression(node) && !tableRows.has(node) && node.elements.length >= 2
      && node.elements.some(element => ts.isStringLiteralLike(element) && HANDLER_METHODS.has(element.text.toLowerCase()))
      && node.elements.some(element => ts.isStringLiteralLike(element) && element.text.startsWith('/api'))) {
      unresolved(node); // A [method, '/api/...'] row outside a recognised loop.
    }
    if (ts.isCallExpression(node)) {
      const call = routeCall(node);
      if (call === 'unresolved') unresolved(node);
      else if (call && call !== 'alias') handleRouteCall(call);
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return { handlers, relative, mounts, ctx: declarations };
}

/** Relative routes registered on ``exported`` in the module ``specifier`` imported by ``ctx``. */
function importedRelativeRoutes(ctx: FileContext, name: string): RelativeRoute[] {
  const binding = ctx.imports.get(name);
  if (!binding || binding.imported === '*' || !ctx.absPath) return [];
  const target = resolveImport(binding.specifier, ctx.absPath);
  if (!target || !/\.(ts|tsx)$/.test(target)) return [];
  const scan = scanFile(rel(target), readFileSync(target, 'utf8'), target);
  let exported = binding.imported;
  const aliased = exported === 'default' ? scan.ctx.declarations.get('default') : undefined;
  if (aliased && ts.isIdentifier(aliased)) exported = aliased.text;
  return scan.relative.filter(route => route.receiver === exported);
}

/** ``file`` is repo-relative; a file outside the repo (synthetic samples) resolves no imports. */
export function routeHandlers(file: string, text: string, absPath: string | null = null): RouteHandler[] {
  const scan = scanFile(file, text, absPath);
  const handlers = [...scan.handlers];
  for (const mount of scan.mounts) {
    const local = scan.relative.filter(route => route.receiver === mount.name);
    const routes = local.length ? local : importedRelativeRoutes(scan.ctx, mount.name);
    for (const prefix of mount.prefixes) {
      for (const route of routes) {
        const joined = joinRoute(prefix, route.route);
        handlers.push({ key: handlerKey(route.method, joined, route.file, route.ordinal), file: route.file, line: route.line, canned: route.canned, unclassified: route.unclassified });
      }
    }
  }
  return handlers;
}
