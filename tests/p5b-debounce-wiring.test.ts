import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// Source-contract checks (no DOM test environment in the unit suite): they fail if the wiring is reverted.
const src = (path: string) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8').replace(/\r\n/g, '\n');

test('slicer uses the debounced latest-task hook with an abortable request', () => {
  for (const file of [
    'src/components/3d-distortion-lab/BasicSTLSlicerLab.tsx',
  ]) {
    const text = src(file);
    assert.match(text, /useDebouncedLatestTask\(/, `${file} must debounce through the shared controller`);
    assert.doesNotMatch(text, /setTimeout\(\s*\(\)\s*=>\s*\{?\s*(void\s+)?(runPython|dispatchPython)/, `${file} must not hand-roll a timer`);
  }
  assert.match(src('src/components/3d-distortion-lab/BasicSTLSlicerLab.tsx'), /AbortSignal\.any\(\[signal/);
});
