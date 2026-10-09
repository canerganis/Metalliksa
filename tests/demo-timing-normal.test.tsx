import assert from 'node:assert/strict';
import { test } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

// IS_STATIC_DEMO reads this global once, at module load, so it is set before the dynamic imports.
// __STATIC_DEMO__ is left undefined: normal (non-demo) behaviour.

const DEMO = false;
const job = {
  id: 'a'.repeat(32), status: 'completed', progress: 1, log: '', error: null, cacheHit: false,
  result: { material: { name: 'IN625' }, metrics: {}, solver: { id: 'x' }, provenance: { runtime_s: 0 }, label: 'x' },
};

test('process window status line (normal mode)', async () => {
  const { ProcessWindowResultStatus } = await import('../src/components/LpbfProcessWindowMap.tsx');
  const result = { computeMs: 0, grid: { nCells: 121 }, cache: { hit: false } } as never;
  const html = renderToStaticMarkup(<ProcessWindowResultStatus result={result} source="computed" stale={false} />);
  if (DEMO) {
    assert.ok(html.includes('Recorded snapshot (121 cells); compute time not recorded.'), html);
    assert.ok(!html.includes('Computed in'), html);
  } else {
    assert.ok(html.includes('Computed in 0 ms (121 cells).'), html);
  }
});

test('result header job time and cache status (normal mode)', async () => {
  const { ResultHeader } = await import('../src/components/3d-distortion-lab/LpbfResultPresentation.tsx');
  const html = renderToStaticMarkup(<ResultHeader job={job as never} material="IN625" availability="n/a" stale={false} elapsed={0} cancel={() => {}} cancelling={false} />);
  if (DEMO) {
    assert.ok(html.includes('Not recorded (static snapshot)'), html);
    assert.ok(html.includes('Recorded snapshot'), html);
    assert.ok(!html.includes('solver execution') && !html.includes('New computation'), html);
  } else {
    assert.ok(html.includes('0 s solver execution'), html);
    assert.ok(html.includes('New computation'), html);
  }
});
