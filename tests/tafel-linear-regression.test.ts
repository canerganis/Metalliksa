import assert from 'node:assert/strict';
import { test } from 'node:test';

// BUG 1 (fixed in Phase 6a step b): src/utils/tafelParser.ts used to build TAFEL_BENCHMARK_DATASETS at module load
// through createBenchmarkDataset(), which always throws, so the module could not be imported and these tests were todo.
// The module is imported directly now: a regression fails this file loudly instead of turning tests into todos.
import * as tafel from '../src/utils/tafelParser';

const mod = () => tafel;

test('linearRegression recovers an exact line with r2 of 1', () => {
  const x = [0, 1, 2, 3, 4];
  const y = x.map((v) => 2 * v + 1);
  const fit = mod().linearRegression(x, y);
  assert.ok(Math.abs(fit.m - 2) < 1e-12);
  assert.ok(Math.abs(fit.b - 1) < 1e-12);
  assert.ok(Math.abs(fit.r2 - 1) < 1e-12);
});

test('linearRegression handles a negative slope and noisy data with r2 below 1', () => {
  const x = [0, 1, 2, 3, 4, 5];
  const y = [10.2, 7.9, 6.1, 4.2, 1.8, 0.1];
  const fit = mod().linearRegression(x, y);
  assert.ok(fit.m < 0);
  assert.ok(fit.r2 > 0.99 && fit.r2 < 1);
});

test('linearRegression returns a zero-slope result for fewer than two points', () => {
  assert.deepEqual(mod().linearRegression([], []), { m: 0, b: 0, r2: 0 });
  assert.deepEqual(mod().linearRegression([3], [7]), { m: 0, b: 7, r2: 0 });
});

test('linearRegression returns the mean of y with zero slope when all x are identical', () => {
  const fit = mod().linearRegression([2, 2, 2], [1, 2, 3]);
  assert.deepEqual(fit, { m: 0, b: 2, r2: 0 });
});

test('linearRegression of constant y gives zero slope and no NaN', () => {
  const fit = mod().linearRegression([0, 1, 2, 3], [5, 5, 5, 5]);
  assert.ok(Math.abs(fit.m) < 1e-12);
  assert.ok(Math.abs(fit.b - 5) < 1e-12);
  assert.ok(Number.isFinite(fit.r2));
});
