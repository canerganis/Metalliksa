import React from 'react';
import assert from 'node:assert/strict';
import { renderToStaticMarkup } from 'react-dom/server';
import { SourceLoadStatus } from '../src/components/ExperimentalValidationLab';
import { sourceMeasurements, SourceNotImportedError } from '../src/services/lpbfSourceService';

const realFetch = globalThis.fetch;
const stub = (status: number) => { globalThis.fetch = (async () => new Response('{}', { status })) as typeof fetch; };
const signal = new AbortController().signal;

try {
  stub(404);
  await assert.rejects(sourceMeasurements('cmu-ti64-meltpool-v1', signal), (e: unknown) => e instanceof SourceNotImportedError && /not imported/.test((e as Error).message));
  stub(500);
  await assert.rejects(sourceMeasurements('cmu-ti64-meltpool-v1', signal), (e: unknown) => !(e instanceof SourceNotImportedError) && (e as Error).message === 'Failed to load experimental measurements');
} finally { globalThis.fetch = realFetch; }

const notImported = renderToStaticMarkup(<SourceLoadStatus error={{ message: 'x', notImported: true }} />);
assert.match(notImported, /not imported in this installation/);
assert.match(notImported, /Source Archive panel/);
assert.match(notImported, /Experimental Comparison/);
assert.doesNotMatch(notImported, /Failed to load/);
const failed = renderToStaticMarkup(<SourceLoadStatus error={{ message: 'Failed to load experimental measurements', notImported: false }} />);
assert.match(failed, /Failed to load experimental data: Failed to load experimental measurements/);
assert.doesNotMatch(failed, /not imported/);
console.log('PASS: not-imported vs real-error source messaging');
