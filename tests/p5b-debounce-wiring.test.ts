import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// Source-contract checks (no DOM test environment in the unit suite): they fail if the wiring is reverted.
const src = (path: string) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8').replace(/\r\n/g, '\n');

test('slicer, Pourbaix and corrosion EIS use the debounced latest-task hook with an abortable request', () => {
  for (const file of [
    'src/components/3d-distortion-lab/BasicSTLSlicerLab.tsx',
    'src/components/DynamicPourbaixStudio.tsx',
    'src/components/CorrosionEISKineticsStudio.tsx',
  ]) {
    const text = src(file);
    assert.match(text, /useDebouncedLatestTask\(/, `${file} must debounce through the shared controller`);
    assert.doesNotMatch(text, /setTimeout\(\s*\(\)\s*=>\s*\{?\s*(void\s+)?(runPython|dispatchPython)/, `${file} must not hand-roll a timer`);
  }
  assert.match(src('src/components/3d-distortion-lab/BasicSTLSlicerLab.tsx'), /AbortSignal\.any\(\[signal/);
  assert.match(src('src/components/DynamicPourbaixStudio.tsx'), /experimentalPoints \}\), signal\);/);
});

test('corrosion EIS signature only contains request inputs (coatingType is not sent)', () => {
  const text = src('src/components/CorrosionEISKineticsStudio.tsx');
  const signature = text.match(/corrosionInputSignature = JSON\.stringify\(\[([^\]]*)\]\)/)?.[1] ?? '';
  assert.match(signature, /metalId, betaA, betaC, i0Corr, ePit, e0, exposureDays/);
  assert.doesNotMatch(signature, /coatingType/);
  assert.doesNotMatch(text.slice(text.indexOf('const runPythonSimulation'), text.indexOf('// Debounced, visibility-gated')), /coatingType/);
});

test('micrograph diagnosis shows an honest indeterminate state, not simulated stage progress', () => {
  // The advisory description moved out of MicrographLab into its own component (micrograph rework).
  const text = src('src/components/MicrographAdvisoryDescription.tsx');
  assert.doesNotMatch(src('src/components/MicrographLab.tsx'), /setInterval|analysisStep|LOADING_STEPS|stepInterval/);
  assert.doesNotMatch(text, /setInterval|analysisStep|LOADING_STEPS|stepInterval/);
  assert.match(text, /Progress is not reported/);
});
