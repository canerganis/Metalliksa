import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { MODULES } from '../src/data/workspaces';

// Golden snapshot of the hand-written MODULES list, captured at 464806f BEFORE MODULES was
// derived from the module registry (Phase 7 slice 1). Navigation must not change visibly:
// ids, order, labels, workspace, maturity (scope), description and next stay identical.
const golden = JSON.parse(readFileSync(new URL('./fixtures/modules-nav-golden.json', import.meta.url), 'utf8')) as Array<{
  id: string; workspace: string; label: string; scope: string; description: string; next: string;
}>;

test('MODULES equals the pre-registry golden navigation list (ids, order, labels, workspace, maturity)', () => {
  const current = MODULES.map(m => ({ id: m.id, workspace: m.workspace, label: m.label, scope: m.scope, description: m.description, next: m.next }));
  assert.equal(golden.length, 32);
  assert.deepEqual(current, golden);
});
