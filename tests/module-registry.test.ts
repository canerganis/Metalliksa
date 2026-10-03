import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { MODULES } from '../src/data/workspaces';
import { EVIDENCE_TYPES } from '../src/types/research';
import type { ModuleRegistryDocument } from '../src/generated/moduleRegistry';

// Reads only the committed JSON emitted by python/module_registry.py, so Node CI never needs Python.
const registry = JSON.parse(readFileSync(new URL('../src/generated/moduleRegistry.json', import.meta.url), 'utf8')) as ModuleRegistryDocument;

// Ratchet: Phase 7 step 0 generated one legacy contract per listed module. Migration may only
// lower this number. Raising it needs an explicit edit here and maintainer review.
const LEGACY_CEILING = 37;

test('legacy contracts cover exactly the modules listed in workspaces.ts', () => {
  const legacy = registry.contracts.filter(contract => contract.migrationState === 'legacy');
  assert.equal(registry.contracts.length, MODULES.length);
  assert.deepEqual(registry.contracts.map(contract => contract.id), MODULES.map(module => module.id));
  assert.equal(legacy.length, MODULES.length);
  assert.ok(legacy.length <= LEGACY_CEILING, `legacy count ${legacy.length} exceeds ratchet ${LEGACY_CEILING}`);
});

test('registry ids are unique and next links resolve', () => {
  const ids = new Set(registry.contracts.map(contract => contract.id));
  assert.equal(ids.size, registry.contracts.length);
  for (const contract of registry.contracts) assert.ok(ids.has(contract.next), `${contract.id} -> ${contract.next}`);
});

test('evidence vocabulary is the research.ts list plus run states', () => {
  const vocabulary = registry.vocabulary;
  assert.deepEqual(vocabulary.evidenceTypes, [...EVIDENCE_TYPES]);
  assert.deepEqual(vocabulary.runStates, ['unvalidated', 'inconclusive', 'unavailable', 'outside-validity-domain']);
  assert.deepEqual(vocabulary.maturity, ['Research', 'Preview']);
});

test('legacy contracts keep the pending-oracle cap and forbid every claim key', () => {
  const forbidden = registry.vocabulary.forbiddenClaimKeys;
  for (const contract of registry.contracts.filter(item => item.migrationState === 'legacy')) {
    assert.equal(contract.tests.oracle.status, 'pending', contract.id);
    assert.equal(contract.evidence.ceiling, registry.vocabulary.pendingOracleCeiling, contract.id);
    assert.deepEqual(contract.evidence.emits, [], contract.id);
    assert.deepEqual(contract.evidence.forbiddenClaims, forbidden, contract.id);
    assert.ok(['Research', 'Preview'].includes(contract.maturity), contract.id);
    assert.equal(contract.navigation, 'listed', contract.id);
  }
});
