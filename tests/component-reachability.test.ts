import test from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { MODULE_CONTRACTS } from '../src/modules/registry';
import { reachableFrom, rel, repoRoot } from './support/importGraph';

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

/** Pure ratchet decision: which unreachable files are new, and which allowlist entries are stale. */
export function ratchet(unreachable: string[], sharedPaths: string[], baselinePaths: string[]) {
  const allowed = new Set([...sharedPaths, ...baselinePaths]);
  const unreachableSet = new Set(unreachable);
  return {
    grown: unreachable.filter(file => !allowed.has(file)),
    staleBaseline: baselinePaths.filter(file => !unreachableSet.has(file)),
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
  for (const contract of MODULE_CONTRACTS) assert.ok(reachable.has(contract.view.component), contract.id);
  assert.ok(components.length > 50, 'expected the component tree to be scanned');
});

test('SHARED.json entries exist and carry an owner and a reason', () => {
  for (const entry of shared) {
    assert.ok(components.includes(entry.path), `SHARED.json: ${entry.path} is not a component file`);
    assert.ok(entry.owner?.trim(), `SHARED.json: ${entry.path} needs an owner`);
    assert.ok(entry.reason?.trim(), `SHARED.json: ${entry.path} needs a reason`);
    assert.ok(!baseline.some(item => item.path === entry.path), `${entry.path} is both shared and baseline`);
  }
});

test('ratchet logic flags growth and stale baseline entries', () => {
  assert.deepEqual(ratchet(['a', 'b'], [], ['a', 'b']), { grown: [], staleBaseline: [] });
  assert.deepEqual(ratchet(['a', 'b', 'c'], ['c'], ['a', 'b']), { grown: [], staleBaseline: [] });
  assert.deepEqual(ratchet(['a', 'new'], [], ['a']).grown, ['new']);
  assert.deepEqual(ratchet(['a'], [], ['a', 'gone']).staleBaseline, ['gone']);
});

test('every component is reachable, shared, or in the shrinking unreachable baseline', () => {
  const { grown, staleBaseline } = ratchet(unreachable, shared.map(entry => entry.path), baseline.map(entry => entry.path));
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
