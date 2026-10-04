import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { MODULE_CONTRACTS } from '../src/modules/registry';
import { importSpecifiers, reachableFrom, rel, repoRoot } from './support/importGraph';
import { beyondCeiling, readCeiling } from './support/ceiling';

// Phase 7 slice 1: every file under src/components/** must be reachable through static or
// lazy imports from the app entry (src/main.tsx -> src/App.tsx) or a registered module view,
// or be declared in src/components/SHARED.json (owner + reason). Today's orphans are held in
// src/components/UNREACHABLE_BASELINE.json, which may only shrink.

interface SharedEntry { path: string; owner: string; reason: string }
interface BaselineEntry { path: string; note: string }

const readJson = <T>(relative: string): T => JSON.parse(readFileSync(path.join(repoRoot, relative), 'utf8')) as T;
const shared = readJson<{ files: SharedEntry[] }>('src/components/SHARED.json').files;
const baseline = readJson<{ files: BaselineEntry[] }>('src/components/UNREACHABLE_BASELINE.json').files;

const ENTRY_POINTS = ['src/main.tsx', 'src/App.tsx'];
const CODE_FILE = /\.(ts|tsx|js|jsx)$/;

function componentFiles(): string[] {
  const walk = (dir: string): string[] => readdirSync(dir).flatMap(name => {
    const full = path.join(dir, name);
    return statSync(full).isDirectory() ? walk(full) : [full];
  });
  return walk(path.join(repoRoot, 'src/components')).map(rel).filter(file => CODE_FILE.test(file)).sort();
}

const ceilings = {
  baseline: readCeiling('src/components/UNREACHABLE_BASELINE.ceiling.json', 'paths').paths,
  shared: readCeiling('src/components/SHARED.ceiling.json', 'paths').paths,
};

/**
 * Pure ratchet decision: unreachable files not allowed by the live lists, stale baseline entries,
 * and live entries that exceed the immutable ceilings (an orphan "allowed" by also adding a
 * baseline entry still fails here).
 */
export function ratchet(unreachable: string[], sharedPaths: string[], baselinePaths: string[],
  ceiling: { baseline: ReadonlySet<string>; shared: ReadonlySet<string> } = ceilings) {
  const allowed = new Set([...sharedPaths, ...baselinePaths]);
  const unreachableSet = new Set(unreachable);
  return {
    grown: unreachable.filter(file => !allowed.has(file)),
    staleBaseline: baselinePaths.filter(file => !unreachableSet.has(file)),
    beyondCeiling: [...beyondCeiling(baselinePaths, ceiling.baseline), ...beyondCeiling(sharedPaths, ceiling.shared)],
  };
}

const roots = [...ENTRY_POINTS, ...MODULE_CONTRACTS.map(contract => contract.view.component)];
const reachable = new Set([...reachableFrom(roots)].map(rel));
const components = componentFiles();
const unreachable = components.filter(file => !reachable.has(file));

test('the import graph follows lazy view imports from App.tsx and registered views', () => {
  const fromApp = new Set([...reachableFrom(['src/App.tsx'])].map(rel));
  // Lazy-only target of App.tsx and a static child of a registered view.
  assert.ok(fromApp.has('src/components/LpbfEngineeringWorkspace.tsx'));
  assert.ok(fromApp.has('src/components/WorkspaceVisibility.tsx'));
  assert.ok(components.length > 50, 'expected the component tree to be scanned');
});

test('every registered view is reachable from the app entry alone, not only as its own root', () => {
  const fromEntry = new Set([...reachableFrom(ENTRY_POINTS)].map(rel));
  const missing = MODULE_CONTRACTS.filter(contract => !fromEntry.has(contract.view.component)).map(contract => `${contract.id}: ${contract.view.component}`);
  assert.deepEqual(missing, [], `Registered view(s) not imported from src/main.tsx or src/App.tsx: ${missing.join(', ')}`);
});

test('type-only and erased imports are not runtime edges', () => {
  const sample = [
    "import type { A } from './typeOnly';",
    "import { type B, type C } from './allTypeSpecifiers';",
    "import { type D, value } from './mixed';",
    "import Default, { type E } from './defaultPlusType';",
    "import './sideEffect';",
    "export type { F } from './reexportType';",
    "export { type G } from './reexportTypeSpecifier';",
    "export { H } from './reexportValue';",
    "const Lazy = lazy(() => import('./lazyTarget'));",
    "export const view = <Lazy value={value} other={Default} />;",
  ].join('\n');
  assert.deepEqual(importSpecifiers('sample.tsx', sample),
    ['./mixed', './defaultPlusType', './sideEffect', './reexportValue', './lazyTarget']);
});

test('mutation: imports whose bindings are unused or only used as types are not runtime edges', () => {
  const sample = [
    "import { Unused } from './unusedValue';",
    "import { OnlyType } from './typeUsage';",
    "import { Queried } from './typeofUsage';",
    "import * as NsUnused from './namespaceUnused';",
    "import { Rendered } from './jsxUsage';",
    "import { Called } from './callUsage';",
    "import { Reexported } from './localReexport';",
    "const Never = lazy(() => import('./lazyNeverRendered'));",
    "const Shown = lazy(() => import('./lazyRendered'));",
    "let a: OnlyType; type T = typeof Queried; interface I { x: OnlyType }",
    "const obj = { Unused: 1 }; obj.Unused;",
    "export const v = <Shown><Rendered /></Shown>;",
    "Called();",
    "export { Reexported };",
  ].join('\n');
  assert.deepEqual(importSpecifiers('sample.tsx', sample), ['./jsxUsage', './callUsage', './localReexport', './lazyRendered']);
});

test('SHARED.json entries exist and carry an owner and a reason', () => {
  for (const entry of shared) {
    assert.ok(components.includes(entry.path), `SHARED.json: ${entry.path} is not a component file`);
    assert.ok(entry.owner?.trim(), `SHARED.json: ${entry.path} needs an owner`);
    assert.ok(entry.reason?.trim(), `SHARED.json: ${entry.path} needs a reason`);
    assert.ok(!baseline.some(item => item.path === entry.path), `${entry.path} is both shared and baseline`);
  }
});

test('ratchet logic flags growth, stale entries and allowlist growth past the ceiling', () => {
  const ceiling = { baseline: new Set(['a', 'b', 'gone']), shared: new Set(['c']) };
  assert.deepEqual(ratchet(['a', 'b'], [], ['a', 'b'], ceiling), { grown: [], staleBaseline: [], beyondCeiling: [] });
  assert.deepEqual(ratchet(['a', 'b', 'c'], ['c'], ['a', 'b'], ceiling), { grown: [], staleBaseline: [], beyondCeiling: [] });
  assert.deepEqual(ratchet(['a', 'new'], [], ['a'], ceiling).grown, ['new']);
  assert.deepEqual(ratchet(['a'], [], ['a', 'gone'], ceiling).staleBaseline, ['gone']);
  // Removing entries stays allowed.
  assert.deepEqual(ratchet(['a'], [], ['a'], ceiling).beyondCeiling, []);
});

test('mutation: a new orphan plus a matching baseline (or shared) entry still fails', () => {
  const ceiling = { baseline: new Set(['a']), shared: new Set<string>() };
  const viaBaseline = ratchet(['a', 'src/components/NewOrphan.tsx'], [], ['a', 'src/components/NewOrphan.tsx'], ceiling);
  assert.deepEqual(viaBaseline.grown, []);
  assert.deepEqual(viaBaseline.beyondCeiling, ['src/components/NewOrphan.tsx']);
  const viaShared = ratchet(['a', 'src/components/NewOrphan.tsx'], ['src/components/NewOrphan.tsx'], ['a'], ceiling);
  assert.deepEqual(viaShared.beyondCeiling, ['src/components/NewOrphan.tsx']);
  // Against the committed ceilings too.
  assert.deepEqual(ratchet(['src/components/NewOrphan.tsx'], [], ['src/components/NewOrphan.tsx']).beyondCeiling, ['src/components/NewOrphan.tsx']);
});

// Support code outside src/components: features (if present), utils, services, hooks.
const SUPPORT_DIRS = ['src/features', 'src/utils', 'src/services', 'src/hooks'];
const supportBaseline = readJson<{ files: BaselineEntry[] }>('src/UNREACHABLE_SUPPORT_BASELINE.json').files;
const supportCeiling = readCeiling('src/UNREACHABLE_SUPPORT_BASELINE.ceiling.json', 'paths').paths;

function supportFiles(): string[] {
  const walk = (dir: string): string[] => readdirSync(dir).flatMap(name => {
    const full = path.join(dir, name);
    return statSync(full).isDirectory() ? walk(full) : [full];
  });
  return SUPPORT_DIRS.filter(dir => existsSync(path.join(repoRoot, dir)))
    .flatMap(dir => walk(path.join(repoRoot, dir))).map(rel).filter(file => CODE_FILE.test(file) && !file.endsWith('.d.ts')).sort();
}

test('every support module (utils/services/hooks/features) is reachable or in its shrinking baseline', () => {
  const files = supportFiles();
  const orphans = files.filter(file => !reachable.has(file));
  const result = ratchet(orphans, [], supportBaseline.map(entry => entry.path), { baseline: supportCeiling, shared: new Set() });
  console.log(`Support-module scan: ${files.length} files, ${orphans.length} unreachable (baseline ${supportBaseline.length}).`);
  assert.ok(files.length > 40, 'expected src/utils, src/services and src/hooks to be scanned');
  assert.deepEqual(result.beyondCeiling, [], `Support baseline entries ${result.beyondCeiling.join(', ')} exceed src/UNREACHABLE_SUPPORT_BASELINE.ceiling.json.`);
  assert.deepEqual(result.grown, [], `New unreachable support module(s) ${result.grown.join(', ')}: import them from a registered view or delete them.`);
  assert.deepEqual(result.staleBaseline, [], `Support baseline entries ${result.staleBaseline.join(', ')} are reachable again or deleted: remove them.`);
});

test('mutation: a new support orphan plus a matching support-baseline entry still fails', () => {
  const sneaked = 'src/utils/newOrphan.ts';
  const result = ratchet([sneaked], [], [sneaked], { baseline: supportCeiling, shared: new Set() });
  assert.deepEqual(result.beyondCeiling, [sneaked]);
});

test('every component is reachable, shared, or in the shrinking unreachable baseline', () => {
  const { grown, staleBaseline, beyondCeiling: overCeiling } = ratchet(unreachable, shared.map(entry => entry.path), baseline.map(entry => entry.path));
  assert.deepEqual(overCeiling, [], `Allowlist entries ${overCeiling.join(', ')} are not in the immutable *.ceiling.json allowance: wire the file into a view or delete it instead of allowlisting it.`);
  const checklist = baseline.filter(entry => unreachable.includes(entry.path));
  const lines = checklist.map(entry => {
    const loc = readFileSync(path.join(repoRoot, entry.path), 'utf8').split(/\r?\n/).length;
    return `  [ ] ${entry.path} (${loc} lines) - ${entry.note}`;
  });
  console.log([
    `Unreachable-component baseline: ${checklist.length} file(s), ${checklist.reduce((sum, entry) => sum + readFileSync(path.join(repoRoot, entry.path), 'utf8').split(/\r?\n/).length, 0)} lines.`,
    'Shrink-to-delete checklist (each deletion needs user approval; then drop the entry from UNREACHABLE_BASELINE.json):',
    ...lines,
  ].join('\n'));
  assert.deepEqual(grown, [], `New unreachable component file(s) ${grown.join(', ')}: wire them into a registered view, add them to SHARED.json with owner+reason, or delete them. Do not grow UNREACHABLE_BASELINE.json.`);
  assert.deepEqual(staleBaseline, [], `Baseline entries ${staleBaseline.join(', ')} are reachable again or deleted: remove them from UNREACHABLE_BASELINE.json (the ratchet only shrinks).`);
});
