import React from 'react';
import assert from 'node:assert/strict';
import { renderToStaticMarkup } from 'react-dom/server';
import { SourceLoadStatus, toLoadError } from '../src/components/ExperimentalValidationLab';
import { sourceMeasurements, SourceNotImportedError } from '../src/services/lpbfSourceService';

const realFetch = globalThis.fetch;
const stub = (status: number, body: object | string = {}) => { globalThis.fetch = (async () => new Response(typeof body === 'string' ? body : JSON.stringify(body), { status })) as typeof fetch; };
const signal = new AbortController().signal;

try {
  stub(404, { error: 'Source dataset has not been imported.' });
  await assert.rejects(sourceMeasurements('cmu-ti64-meltpool-v1', signal), (e: unknown) => e instanceof SourceNotImportedError && /not imported/.test((e as Error).message));
  stub(404, { error: 'Source dataset is not in the local catalog.' });
  await assert.rejects(sourceMeasurements('cmu-ti64-meltpool-v1', signal), (e: unknown) => !(e instanceof SourceNotImportedError) && (e as Error).message === 'Source dataset is not in the local catalog.');
  stub(404, 'not json');
  await assert.rejects(sourceMeasurements('cmu-ti64-meltpool-v1', signal), (e: unknown) => !(e instanceof SourceNotImportedError) && (e as Error).message === 'Failed to load experimental measurements');
  stub(500, { error: 'Source archive unavailable or integrity check failed.' });
  await assert.rejects(sourceMeasurements('cmu-ti64-meltpool-v1', signal), (e: unknown) => !(e instanceof SourceNotImportedError) && (e as Error).message === 'Source archive unavailable or integrity check failed.');
  stub(500);
  await assert.rejects(sourceMeasurements('cmu-ti64-meltpool-v1', signal), (e: unknown) => (e as Error).message === 'Failed to load experimental measurements');
} finally { globalThis.fetch = realFetch; }

const notImported = renderToStaticMarkup(<SourceLoadStatus error={{ message: 'x', notImported: true }} />);
assert.match(notImported, /not imported in this installation/);
assert.match(notImported, /Source Archive panel/);
assert.match(notImported, /Experimental Comparison/);
assert.match(notImported, /manifest\.json/);
assert.match(notImported, /raw\//);
assert.match(notImported, /Preview local source/);
assert.match(notImported, /CMU Single\/Multi-track Meltpool Dimensions/);
assert.equal(toLoadError(new SourceNotImportedError('x')).notImported, true);
assert.deepEqual(toLoadError(new Error('boom')), { message: 'boom', notImported: false });
assert.doesNotMatch(notImported, /Failed to load/);
const failed = renderToStaticMarkup(<SourceLoadStatus error={{ message: 'Failed to load experimental measurements', notImported: false }} />);
assert.match(failed, /Failed to load experimental data: Failed to load experimental measurements/);
assert.doesNotMatch(failed, /not imported/);
console.log('PASS: not-imported vs real-error source messaging');
