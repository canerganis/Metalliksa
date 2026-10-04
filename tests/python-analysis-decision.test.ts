import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { shouldRequestAnalysis } from '../src/hooks/usePythonAnalysis';

const done = (key: string) => ({ key, pending: false, error: null });

test('A -> B -> A: retained state belongs to B, so A must be requested again', () => {
  // A finished, then B replaced the retained state (still pending); user returns to A.
  assert.equal(shouldRequestAnalysis(true, true, 'A', { key: 'B', pending: true, error: null }), true);
  assert.equal(shouldRequestAnalysis(true, true, 'A', done('B')), true);
});

test('gated: finished identical input is skipped, hidden is skipped, failed is retried', () => {
  assert.equal(shouldRequestAnalysis(true, true, 'A', done('A')), false);
  assert.equal(shouldRequestAnalysis(true, false, 'A', null), false);
  assert.equal(shouldRequestAnalysis(true, true, 'A', { key: 'A', pending: false, error: 'x' }), true);
  assert.equal(shouldRequestAnalysis(true, true, 'A', { key: 'A', pending: true, error: null }), true);
});

test('ungated callers always request and never depend on visibility', () => {
  assert.equal(shouldRequestAnalysis(false, false, 'A', done('A')), true);
  const text = readFileSync(new URL('../src/hooks/usePythonAnalysis.ts', import.meta.url), 'utf8');
  assert.match(text, /const effectVisible = gated \? visible : true;/);
  assert.match(text, /\[url, body, key, decode, gated, debounceMs, effectVisible\]/);
});

test('elapsed time starts when the request is sent, not before the debounce', () => {
  const text = readFileSync(new URL('../src/hooks/usePythonAnalysis.ts', import.meta.url), 'utf8');
  assert.match(text, /const send = \(\) => \{ const start = performance\.now\(\);/);
});
