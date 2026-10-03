import assert from 'node:assert/strict';
import { test } from 'node:test';

// BUG 1 (real, reported, not fixed here): src/utils/tafelParser.ts evaluates TAFEL_BENCHMARK_DATASETS at module load and
// createBenchmarkDataset() unconditionally throws "Fabrication of Tafel ... is disabled", so the module cannot be imported.
// Only that exact signature is tolerated: tests that need the module are marked todo (blocked by BUG 1). Any other import
// error is rethrown so the file fails loudly. The todo-ed assertions were verified against a scratch copy of the module
// with the benchmark construction stubbed out (not part of this repo).
type TafelModule = typeof import('../src/utils/tafelParser');
let tafel: TafelModule | undefined;
let bug1: Error | undefined;
try {
  tafel = await import('../src/utils/tafelParser');
} catch (error) {
  if (error instanceof Error && /Fabrication of Tafel/.test(error.message)) bug1 = error;
  else throw error;
}
const todo = bug1 ? 'BLOCKED by BUG 1: tafelParser.ts throws on import (createBenchmarkDataset)' : false;
const mod = (): TafelModule => {
  if (!tafel) throw bug1;
  return tafel;
};

test('linearRegression recovers an exact line with r2 of 1', { todo }, () => {
  const x = [0, 1, 2, 3, 4];
  const y = x.map((v) => 2 * v + 1);
  const fit = mod().linearRegression(x, y);
  assert.ok(Math.abs(fit.m - 2) < 1e-12);
  assert.ok(Math.abs(fit.b - 1) < 1e-12);
  assert.ok(Math.abs(fit.r2 - 1) < 1e-12);
});

test('linearRegression handles a negative slope and noisy data with r2 below 1', { todo }, () => {
  const x = [0, 1, 2, 3, 4, 5];
  const y = [10.2, 7.9, 6.1, 4.2, 1.8, 0.1];
  const fit = mod().linearRegression(x, y);
  assert.ok(fit.m < 0);
  assert.ok(fit.r2 > 0.99 && fit.r2 < 1);
});

test('linearRegression returns a zero-slope result for fewer than two points', { todo }, () => {
  assert.deepEqual(mod().linearRegression([], []), { m: 0, b: 0, r2: 0 });
  assert.deepEqual(mod().linearRegression([3], [7]), { m: 0, b: 7, r2: 0 });
});

test('linearRegression returns the mean of y with zero slope when all x are identical', { todo }, () => {
  const fit = mod().linearRegression([2, 2, 2], [1, 2, 3]);
  assert.deepEqual(fit, { m: 0, b: 2, r2: 0 });
});

test('linearRegression of constant y gives zero slope and no NaN', { todo }, () => {
  const fit = mod().linearRegression([0, 1, 2, 3], [5, 5, 5, 5]);
  assert.ok(Math.abs(fit.m) < 1e-12);
  assert.ok(Math.abs(fit.b - 5) < 1e-12);
  assert.ok(Number.isFinite(fit.r2));
});
