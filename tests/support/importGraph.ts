// Static import graph over repository TypeScript sources, built with the TypeScript compiler
// (Phase 7 slice 1). Follows `import`, `export ... from`, `import type` and string-literal
// dynamic `import()`/`lazy(() => import(...))`; resolution uses the tsconfig module options.
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

export const repoRoot = fileURLToPath(new URL('../..', import.meta.url));

const compilerOptions: ts.CompilerOptions = {
  module: ts.ModuleKind.ESNext,
  moduleResolution: ts.ModuleResolutionKind.Bundler,
  allowImportingTsExtensions: true,
  allowJs: true,
  jsx: ts.JsxEmit.ReactJSX,
  baseUrl: repoRoot,
  paths: { '@/*': ['./*'] },
};

const host: ts.ModuleResolutionHost = {
  fileExists: existsSync,
  readFile: file => readFileSync(file, 'utf8'),
};

/** Repo-relative POSIX path. */
export function rel(file: string): string {
  return path.relative(repoRoot, file).split(path.sep).join('/');
}

/**
 * True for declarations erased at compile time: `import type ...`, `export type ... from`, and
 * imports/re-exports whose every named binding is marked `type` (with no default binding).
 * Side-effect imports (`import './x'`) are kept. Imports used only in type positions without the
 * `type` keyword are not detected.
 */
export function isTypeOnly(node: ts.ImportDeclaration | ts.ExportDeclaration): boolean {
  if (ts.isExportDeclaration(node)) {
    if (node.isTypeOnly) return true;
    return !!node.exportClause && ts.isNamedExports(node.exportClause) && node.exportClause.elements.length > 0
      && node.exportClause.elements.every(element => element.isTypeOnly);
  }
  const clause = node.importClause;
  if (!clause) return false;
  if (clause.isTypeOnly) return true;
  if (clause.name) return false;
  const bindings = clause.namedBindings;
  return !!bindings && ts.isNamedImports(bindings) && bindings.elements.length > 0 && bindings.elements.every(element => element.isTypeOnly);
}

/** Names referenced in value positions anywhere in the file outside import declarations. */
function valueReferences(source: ts.SourceFile): Set<string> {
  const names = new Set<string>();
  const isDeclarationName = (node: ts.Identifier) => {
    const parent = node.parent;
    return (ts.isPropertyAccessExpression(parent) && parent.name === node)
      || (ts.isPropertyAssignment(parent) && parent.name === node)
      || ((ts.isVariableDeclaration(parent) || ts.isFunctionDeclaration(parent) || ts.isClassDeclaration(parent)
        || ts.isParameter(parent) || ts.isBindingElement(parent) || ts.isMethodDeclaration(parent)
        || ts.isPropertyDeclaration(parent) || ts.isPropertySignature(parent)) && parent.name === node)
      || (ts.isJsxAttribute(parent) && parent.name === node);
  };
  const visit = (node: ts.Node, inType: boolean) => {
    if (ts.isImportDeclaration(node)) return;
    // `class A extends Base<T>` (declaration or expression): Base is evaluated at runtime even
    // though the parser models it as an ExpressionWithTypeArguments (a type node); only the
    // type arguments are erased. Interface `extends` stays erased via the interface itself.
    if (ts.isExpressionWithTypeArguments(node) && ts.isHeritageClause(node.parent) && node.parent.token === ts.SyntaxKind.ExtendsKeyword
      && (ts.isClassDeclaration(node.parent.parent) || ts.isClassExpression(node.parent.parent))) {
      visit(node.expression, inType);
      node.typeArguments?.forEach(argument => visit(argument, true));
      return;
    }
    // Type positions are erased; `typeof X` in a type is erased too.
    const typePosition = inType || ts.isTypeNode(node) || ts.isInterfaceDeclaration(node) || ts.isTypeAliasDeclaration(node)
      || (ts.isHeritageClause(node) && node.token === ts.SyntaxKind.ImplementsKeyword);
    if (ts.isExportSpecifier(node)) {
      if (!node.isTypeOnly && !(node.parent.parent as ts.ExportDeclaration).isTypeOnly) names.add((node.propertyName ?? node.name).text);
      return;
    }
    if (!typePosition && ts.isIdentifier(node) && !isDeclarationName(node)) names.add(node.text);
    ts.forEachChild(node, child => visit(child, typePosition));
  };
  visit(source, false);
  return names;
}

/** Local names bound by an import declaration (default, namespace and non-type named bindings). */
function importedNames(node: ts.ImportDeclaration): string[] {
  const clause = node.importClause;
  if (!clause) return [];
  const names = clause.name ? [clause.name.text] : [];
  const bindings = clause.namedBindings;
  if (bindings && ts.isNamespaceImport(bindings)) names.push(bindings.name.text);
  if (bindings && ts.isNamedImports(bindings)) names.push(...bindings.elements.filter(element => !element.isTypeOnly).map(element => element.name.text));
  return names;
}

/** `const X = lazy(() => import('./y'))`: the variable name, or undefined for other dynamic imports. */
function lazyBindingName(call: ts.CallExpression): string | undefined {
  for (let node: ts.Node = call.parent; node; node = node.parent) {
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'lazy') {
      const declaration = node.parent;
      return ts.isVariableDeclaration(declaration) && ts.isIdentifier(declaration.name) ? declaration.name.text : undefined;
    }
    if (ts.isSourceFile(node) || ts.isBlock(node) && !ts.isArrowFunction(node.parent)) return undefined;
  }
  return undefined;
}

/**
 * Module specifiers a source file depends on at runtime: static imports with at least one
 * binding used as a value (or side-effect imports), value re-exports, and literal dynamic
 * imports; a `lazy(() => import())` whose component is never referenced is not an edge.
 */
export function importSpecifiers(file: string, text: string = readFileSync(file, 'utf8')): string[] {
  const kind = file.endsWith('.tsx') ? ts.ScriptKind.TSX : file.endsWith('.ts') ? ts.ScriptKind.TS : ts.ScriptKind.JS;
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.ES2022, true, kind);
  const used = valueReferences(source);
  const specifiers: string[] = [];
  const visit = (node: ts.Node) => {
    if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) {
      const names = importedNames(node);
      const sideEffectOnly = !node.importClause;
      if (!isTypeOnly(node) && (sideEffectOnly || names.some(name => used.has(name)))) specifiers.push(node.moduleSpecifier.text);
    } else if (ts.isExportDeclaration(node) && node.moduleSpecifier && ts.isStringLiteral(node.moduleSpecifier)) {
      if (!isTypeOnly(node)) specifiers.push(node.moduleSpecifier.text);
    } else if (ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword) {
      const [argument] = node.arguments;
      const lazyName = lazyBindingName(node);
      const rendered = lazyName === undefined || used.has(lazyName);
      if (rendered && argument && (ts.isStringLiteral(argument) || ts.isNoSubstitutionTemplateLiteral(argument))) specifiers.push(argument.text);
    } else if (ts.isImportEqualsDeclaration(node) && ts.isExternalModuleReference(node.moduleReference)
      && ts.isStringLiteral(node.moduleReference.expression)) {
      specifiers.push(node.moduleReference.expression.text);
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return specifiers;
}
/** Absolute path of a resolved repository source, or null for packages and assets. */
export function resolveImport(specifier: string, fromFile: string): string | null {
  const resolved = ts.resolveModuleName(specifier, fromFile, compilerOptions, host).resolvedModule;
  if (!resolved || resolved.isExternalLibraryImport) return null;
  const file = path.resolve(resolved.resolvedFileName);
  if (file.includes(`${path.sep}node_modules${path.sep}`) || file.endsWith('.d.ts')) return null;
  return file;
}

/** Every repository source reachable from the given roots (roots included). */
export function reachableFrom(roots: string[]): Set<string> {
  const seen = new Set<string>();
  const queue = roots.map(root => path.resolve(repoRoot, root));
  while (queue.length) {
    const file = queue.pop()!;
    if (seen.has(file)) continue;
    seen.add(file);
    for (const specifier of importSpecifiers(file)) {
      const target = resolveImport(specifier, file);
      if (target && !seen.has(target)) queue.push(target);
    }
  }
  return seen;
}
