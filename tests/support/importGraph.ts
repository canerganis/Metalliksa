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

/** Module specifiers a source file depends on at runtime (static, re-export and literal dynamic imports). */
export function importSpecifiers(file: string, text: string = readFileSync(file, 'utf8')): string[] {
  const kind = file.endsWith('.tsx') ? ts.ScriptKind.TSX : file.endsWith('.ts') ? ts.ScriptKind.TS : ts.ScriptKind.JS;
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.ES2022, true, kind);
  const specifiers: string[] = [];
  const visit = (node: ts.Node) => {
    if ((ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) && node.moduleSpecifier && ts.isStringLiteral(node.moduleSpecifier)) {
      if (!isTypeOnly(node)) specifiers.push(node.moduleSpecifier.text);
    } else if (ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword) {
      const [argument] = node.arguments;
      if (argument && (ts.isStringLiteral(argument) || ts.isNoSubstitutionTemplateLiteral(argument))) specifiers.push(argument.text);
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
