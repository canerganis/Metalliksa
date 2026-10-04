import React from 'react';
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { renderToStaticMarkup } from 'react-dom/server';
import { EvidenceBadge, evidenceBadgeView } from '../src/components/sdk/EvidenceBadge';
import { MODULE_CONTRACTS, MODULE_REGISTRY_CORE as MODULE_REGISTRY, type EvidenceType, type RegisteredContract } from '../src/modules/registry';

const EVIDENCE_TYPES = MODULE_REGISTRY.vocabulary.evidenceTypes as readonly EvidenceType[];
// Lower index = stronger claim (python/module_contract.py EVIDENCE_RANK).
const rank = (type: string) => EVIDENCE_TYPES.indexOf(type as EvidenceType);
const LABELS = ['Measured', 'Validated simulation', 'Calibrated simulation', 'Literature estimate', 'Screening only', 'Unresolved'];
const read = (path: string) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

test('the badge shows exactly the contract ceiling and no stronger evidence class', () => {
  const contracted = MODULE_CONTRACTS.filter(contract => contract.migrationState === 'contracted');
  assert.deepEqual(contracted.map(contract => contract.id), ['keyhole-raytracing', 'uq-lab']);
  for (const contract of contracted) {
    const html = renderToStaticMarkup(<EvidenceBadge moduleId={contract.id} />);
    const ceiling = contract.evidence.ceiling;
    assert.match(html, new RegExp(`data-evidence-ceiling="${ceiling}"`), contract.id);
    assert.match(html, new RegExp(`data-oracle="${contract.tests.oracle.status}"`), contract.id);
    assert.ok(html.includes(`Ceiling: ${LABELS[rank(ceiling)]}`), contract.id);
    for (const stronger of LABELS.slice(0, rank(ceiling))) assert.ok(!html.includes(stronger), `${contract.id} shows ${stronger}`);
    assert.ok(!/qualified|certified|validated|airworthy/i.test(html.replace(/not a validation claim/, '')), contract.id);
  }
});

test('callers cannot raise the ceiling: the badge has no evidence input', () => {
  // @ts-expect-error EvidenceBadge accepts only a module id; a ceiling prop is a type error.
  const html = renderToStaticMarkup(<EvidenceBadge moduleId="uq-lab" ceiling="measured" status="validated-simulation" />);
  assert.match(html, /data-evidence-ceiling="screening-only"/);
  assert.ok(!html.includes('Measured') && !html.includes('Validated simulation'));
  // Legacy and unknown modules render nothing rather than a placeholder claim.
  for (const contract of MODULE_CONTRACTS.filter(item => item.migrationState === 'legacy')) {
    assert.equal(renderToStaticMarkup(<EvidenceBadge moduleId={contract.id} />), '', contract.id);
  }
  assert.equal(renderToStaticMarkup(<EvidenceBadge moduleId="not-a-module" />), '');
});

test('the view is a pure projection of whatever ceiling the contract holds', () => {
  const base = MODULE_CONTRACTS.find(contract => contract.id === 'keyhole-raytracing') as RegisteredContract;
  for (const ceiling of EVIDENCE_TYPES) {
    const contract = { ...base, evidence: { ...base.evidence, ceiling } } as RegisteredContract;
    const view = evidenceBadgeView(contract);
    assert.equal(view?.ceiling, ceiling);
    assert.ok(view?.text.startsWith(`Ceiling: ${LABELS[rank(ceiling)]} ·`), ceiling);
  }
  const pending = { ...base, tests: { ...base.tests, oracle: { status: 'pending', ref: null } } } as unknown as RegisteredContract;
  assert.match(evidenceBadgeView(pending)?.title ?? '', /Oracle pending/);
  assert.equal(evidenceBadgeView({ ...base, migrationState: 'legacy' } as unknown as RegisteredContract), null);
});

test('the badge reads only the committed contract (no store, service or fetch)', () => {
  const source = read('src/components/sdk/EvidenceBadge.tsx');
  const imports = [...source.matchAll(/from '([^']+)'/g)].map(match => match[1]);
  assert.deepEqual(imports, ['react', '../../modules/registry']);
  assert.ok(!/fetch\(|useStore|Service/.test(source));
});

test('App.tsx renders the badge right after the maturity badge in the module header', () => {
  const app = read('src/App.tsx');
  assert.match(app, /\{activeModule\.scope\}<\/span><EvidenceBadge moduleId=\{activeModule\.id\} \/>/);
});
