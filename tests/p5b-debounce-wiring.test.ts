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
  assert.equal(signature.trim(), 'metalId, betaA, betaC, i0Corr, ePit, eCorr, referenceElectrode');
  assert.doesNotMatch(signature, /coatingType/);
  assert.doesNotMatch(text.slice(text.indexOf('const runPythonSimulation'), text.indexOf('// Debounced, visibility-gated')), /coatingType/);
});

