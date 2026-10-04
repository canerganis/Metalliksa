import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { MODULES } from '../src/data/workspaces';
import { EVIDENCE_TYPES } from '../src/types/research';
import { MODULE_REGISTRY, type ModuleRegistryDocument } from '../src/generated/moduleRegistry';

// Reads only the committed JSON emitted by python/module_registry.py, so Node CI never needs Python.
const registry = JSON.parse(readFileSync(new URL('../src/generated/moduleRegistry.json', import.meta.url), 'utf8')) as ModuleRegistryDocument;

// Ratchet: Phase 7 step 0 generated one legacy contract per listed module. Migration may only
// lower this number. Raising it needs an explicit edit here and maintainer review.
const LEGACY_CEILING = 35;

test('contracts cover exactly the modules listed in workspaces.ts and legacy never grows', () => {
  const legacy = registry.contracts.filter(contract => contract.migrationState === 'legacy');
  const ids = registry.contracts.map(contract => contract.id);
  assert.equal(ids.length, MODULES.length);
  assert.deepEqual(new Set(ids), new Set(MODULES.map(module => module.id)));
  assert.ok(legacy.length <= LEGACY_CEILING, `legacy count ${legacy.length} exceeds ratchet ${LEGACY_CEILING}`);
});

test('generated TypeScript registry equals the committed JSON', () => {
  assert.deepEqual(MODULE_REGISTRY, registry);
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

test('contracted pilots stay bounded: no emitted status, screening-only ceiling, every claim forbidden', () => {
  const contracted = registry.contracts.filter(contract => contract.migrationState === 'contracted');
  assert.deepEqual(contracted.map(contract => contract.id), ['keyhole-raytracing', 'uq-lab']);
  for (const contract of contracted) {
    assert.deepEqual(contract.evidence.emits, [], contract.id);
    assert.equal(contract.evidence.ceiling, 'screening-only', contract.id);
    assert.deepEqual(contract.evidence.forbiddenClaims, registry.vocabulary.forbiddenClaimKeys, contract.id);
    assert.ok(contract.sourceRefs.length > 0, contract.id);
    assert.equal(contract.tests.docs, `docs/modules/${contract.id}.md`);
    for (const operation of contract.operations) {
      assert.equal(operation.output?.statusKey, null, `${contract.id}: output carries no evidence status`);
      assert.ok(operation.input.length > 0, contract.id);
      assert.notEqual(operation.authority.timeoutMs, null, contract.id);
    }
  }
});
