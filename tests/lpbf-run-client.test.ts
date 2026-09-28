import assert from 'node:assert/strict';
import { test } from 'node:test';
import { compareNistOpticalRun, exportRunBundle, getRun, importRun, listRuns, previewRun, restoreRunBundle,
  verifyRunBundle } from '../src/services/lpbfRunArchiveClient';

const jobId = 'a'.repeat(32);
const hash = 'b'.repeat(64);
const capture = { schemaVersion: 1, jobId,
  resultJson: JSON.stringify({ settings: { power: 200 }, material: { id: 'in718' }, artifacts: [] }),
  inputJson: JSON.stringify({ power: 200 }), materialJson: JSON.stringify({ id: 'in718' }),
  contractStatus: 'legacy-unbound' } as const;
const document = { schemaVersion: 1, runId: jobId, capture, sources: [] } as const;
const source = { datasetId: 'source-1', revision: 1, documentSha256: 'c'.repeat(64) };
const boundDocument = { ...document, sources: [source] };
const record = { document, documentSha256: hash, createdAt: '2026-09-23T00:00:00Z',
  evidenceStatus: 'unvalidated-model', sourceBindingStatus: 'legacy-unlinked', runKind: 'legacy-unspecified' } as const;
const signal = new AbortController().signal;

function respond(t: any, body: unknown) {
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(body)));
}

test('run endpoints accept the server capture identity and unvalidated model status', async t => {
  respond(t, record);
  assert.deepEqual(await getRun(jobId, signal), record);
});

test('run client accepts and preserves analytical screening kind', async t => {
  const settings = { mode: 'screening' };
  const material = { id: 'in718' };
  const resultJson = JSON.stringify({ runKind: 'analytical-screening', settings, material, artifacts: [] });
  const analytical = { ...record, runKind: 'analytical-screening' as const,
    document: { ...document, capture: { ...capture, resultJson, inputJson: JSON.stringify(settings),
      materialJson: JSON.stringify(material), runKind: 'analytical-screening' as const } } };
  respond(t, analytical);
  assert.equal((await getRun(jobId, signal)).runKind, 'analytical-screening');
});

test('run client rejects stale document identity', async t => {
  respond(t, { ...record, document: { ...document, capture: { ...capture, jobId: 'c'.repeat(32) } } });
  await assert.rejects(getRun(jobId, signal), /invalid/i);
});

test('run client rejects a claimed validation status', async t => {
  respond(t, { ...record, evidenceStatus: 'experimentally-validated' });
  await assert.rejects(getRun(jobId, signal), /invalid/i);
});

test('run client rejects a source binding status inconsistent with its document', async t => {
  respond(t, { ...record, sourceBindingStatus: 'exact-revision-bound' });
  await assert.rejects(getRun(jobId, signal), /invalid/i);
});

test('run client preserves unresolved source links without claiming a verified revision', async t => {
  respond(t, { ...record, document: boundDocument, sourceBindingStatus: 'unverified-source-link' });
  assert.equal((await getRun(jobId, signal)).sourceBindingStatus, 'unverified-source-link');
});

test('run list accepts current server rows', async t => {
  respond(t, [{ runId: jobId, createdAt: record.createdAt, evidenceStatus: record.evidenceStatus,
    sourceBindingStatus: record.sourceBindingStatus, runKind: record.runKind }]);
  assert.equal((await listRuns(signal))[0].runId, jobId);
});

test('run list requires the server evidence status', async t => {
  respond(t, [{ runId: jobId, createdAt: record.createdAt, evidenceStatus: 'unreviewed-run-archive',
    sourceBindingStatus: record.sourceBindingStatus, runKind: record.runKind }]);
  await assert.rejects(listRuns(signal), /invalid/i);
});

test('run list requires a recognized source binding status', async t => {
  respond(t, [{ runId: jobId, createdAt: record.createdAt, evidenceStatus: record.evidenceStatus,
    sourceBindingStatus: 'unspecified', runKind: record.runKind }]);
  await assert.rejects(listRuns(signal), /invalid/i);
});

test('preview and import match the requested job and archive contract', async t => {
  respond(t, { document: boundDocument, artifactCount: 0, byteSize: 0, artifactIntegrity: 'verified-at-dry-run',
    sourceBindingStatus: 'exact-revision-bound',
    quota: { totalArchiveSizeBytes: 0, maxArchiveSizeBytes: 100, approachingLimit: false } });
  assert.equal((await previewRun(jobId, [source], signal)).sourceBindingStatus, 'exact-revision-bound');
  t.mock.restoreAll();
  respond(t, { ...record, document: boundDocument, sourceBindingStatus: 'exact-revision-bound' });
  assert.equal((await importRun(jobId, [source], signal)).document.capture.jobId, jobId);
});

test('import cannot report success for a different job', async t => {
  respond(t, { ...record, document: { ...document, runId: 'c'.repeat(32), capture: { ...capture, jobId: 'c'.repeat(32) } } });
  await assert.rejects(importRun(jobId, [], signal), /invalid/i);
});

test('preview rejects a response bound to another source revision', async t => {
  respond(t, { document: boundDocument, artifactCount: 0, byteSize: 0,
    artifactIntegrity: 'verified-at-dry-run', sourceBindingStatus: 'exact-revision-bound',
    quota: { totalArchiveSizeBytes: 0, maxArchiveSizeBytes: 100, approachingLimit: false } });
  await assert.rejects(previewRun(jobId, [{ ...source, revision: 2 }], signal), /invalid/i);
});

const bundleId = 'd'.repeat(32);
const restoreId = 'e'.repeat(32);
const manifest = { schemaVersion: 1, kind: 'metalliksa-lpbf-run-bundle',
  metadata: { sha256: hash, byteSize: 100 }, sourceBundle: { sha256: 'c'.repeat(64), byteSize: 200 },
  runCount: 2, artifactCount: 3, sourceLinkCount: 1 };

test('bundle export, verify and isolated restore use empty JSON bodies and exact IDs', async t => {
  const requests: { url: string; init: RequestInit }[] = [];
  t.mock.method(globalThis, 'fetch', async (url: string, init: RequestInit) => {
    requests.push({ url, init });
    const result = requests.length === 1 ? { bundleId, storage: 'server-local-directory', manifest }
      : requests.length === 2 ? { bundleId, storage: 'server-local-directory', verified: true, manifest }
      : { bundleId, restoreId, storage: 'server-local-directory', verified: true, manifest };
    return new Response(JSON.stringify(result));
  });
  assert.equal((await exportRunBundle(signal)).manifest.runCount, 2);
  assert.equal((await verifyRunBundle(bundleId, signal)).verified, true);
  assert.equal((await restoreRunBundle(bundleId, signal)).restoreId, restoreId);
  assert.deepEqual(requests.map(request => request.url), [
    '/api/lpbf/runs/bundles/export', `/api/lpbf/runs/bundles/${bundleId}/verify`,
    `/api/lpbf/runs/bundles/${bundleId}/restore`,
  ]);
  assert.ok(requests.every(request => request.init.method === 'POST'
    && request.init.body === '{}' && (request.init.headers as Record<string, string>)['Content-Type'] === 'application/json'));
});

test('bundle client accepts v2 manifests with campaign counts while retaining v1 support', async t => {
  const v2 = { ...manifest, schemaVersion: 2, campaignCount: 3 };
  respond(t, { bundleId, storage: 'server-local-directory', manifest: v2 });
  const result = await exportRunBundle(signal);
  assert.equal(result.manifest.schemaVersion, 2);
  assert.equal(result.manifest.campaignCount, 3);
  t.mock.restoreAll();
  respond(t, { bundleId, storage: 'server-local-directory', manifest: { ...v2, campaignCount: -1 } });
  await assert.rejects(exportRunBundle(signal), /invalid/i);
});

test('bundle client rejects malformed manifest, false verification and a different bundle ID', async t => {
  respond(t, { bundleId, storage: 'server-local-directory', manifest: { ...manifest, runCount: -1 } });
  await assert.rejects(exportRunBundle(signal), /invalid/i);
  t.mock.restoreAll();
  respond(t, { bundleId, storage: 'server-local-directory', verified: false, manifest });
  await assert.rejects(verifyRunBundle(bundleId, signal), /invalid/i);
  t.mock.restoreAll();
  respond(t, { bundleId: 'f'.repeat(32), restoreId, storage: 'server-local-directory', verified: true, manifest });
  await assert.rejects(restoreRunBundle(bundleId, signal), /invalid/i);
});

test('bundle integrity failure exposes HTTP status and does not report success', async t => {
  t.mock.method(globalThis, 'fetch', async () => new Response(
    JSON.stringify({ error: 'Run bundle integrity verification failed.' }), { status: 409 }));
  await assert.rejects(verifyRunBundle(bundleId, signal), /409.*integrity verification failed/i);
  await assert.rejects(restoreRunBundle(bundleId, signal), /409.*integrity verification failed/i);
});

test('bundle client rejects invalid IDs before a network request', async t => {
  const fetchMock = t.mock.method(globalThis, 'fetch', async () => { throw new Error('Unexpected request'); });
  await assert.rejects(verifyRunBundle('../unsafe', signal), /valid 32-character bundle ID/i);
  assert.equal(fetchMock.mock.callCount(), 0);
});

const opticalLink = { datasetId: 'nist-amb2022-03-optical-table4-local-v1',
  revision: 2, documentSha256: 'e'.repeat(64) };
const opticalRun = { ...record, document: { ...document, sources: [opticalLink] },
  sourceBindingStatus: 'exact-revision-bound' } as const;
const opticalBinding = { ...opticalLink, sourceDatasetId: 'nist-mds2-2718',
  artifactSha256: 'd1b36dfa2e01a3537093c481e249ce52df6b8879c1c67480ddb9aa10799133da' };
const opticalReport = { schemaVersion: 1, benchmark: 'AMB2022-03-TMPG', caseNumber: '0',
  status: 'unavailable', validationStatus: 'unvalidated',
  reference: { doi: '10.18434/mds2-2718', results: 'https://www.nist.gov/results',
    resultsLocator: 'Table 4', methods: 'https://www.nist.gov/methods',
    measurement: 'six optical sections', archiveKind: 'local transcription' },
  sourceBinding: opticalBinding, reasons: ['Optical operator is unavailable.'], errors: null };

test('NIST client posts only a case number and binds the reply to the selected run and revision', async t => {
  const fetchMock = t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(opticalReport)));
  const result = await compareNistOpticalRun(opticalRun, '0', signal);
  assert.equal(result.errors, null);
  const [url, init] = fetchMock.mock.calls[0].arguments as [string, RequestInit];
  assert.equal(url, `/api/lpbf/runs/${jobId}/nist-comparison`);
  assert.equal(init.method, 'POST');
  assert.deepEqual(JSON.parse(init.body as string), { caseNumber: '0' });
});

test('NIST client selects the isolated restored run endpoint and rejects invalid restore identity', async t => {
  const fetchMock = t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(opticalReport)));
  const result = await compareNistOpticalRun(opticalRun, '0', signal, restoreId);
  assert.equal(result.validationStatus, 'unvalidated');
  const [url, init] = fetchMock.mock.calls[0].arguments as [string, RequestInit];
  assert.equal(url, `/api/lpbf/runs/bundles/restores/${restoreId}/runs/${jobId}/nist-comparison`);
  assert.deepEqual(JSON.parse(init.body as string), { caseNumber: '0' });
  await assert.rejects(compareNistOpticalRun(opticalRun, '0', signal, '../unsafe'), /valid archived run/i);
  assert.equal(fetchMock.mock.callCount(), 1);
});

test('NIST client rejects stale case, source binding and numeric unavailable output', async t => {
  for (const bad of [
    { ...opticalReport, caseNumber: '1.1' },
    { ...opticalReport, sourceBinding: { ...opticalBinding, revision: 3 } },
    { ...opticalReport, sourceBinding: null, errors: { width: { absolute_um: 1 } } },
    { ...opticalReport, validationStatus: 'experimentally-validated' },
  ]) {
    respond(t, bad);
    await assert.rejects(compareNistOpticalRun(opticalRun, '0', signal), /invalid/i);
    t.mock.restoreAll();
  }
});

test('NIST client accepts only finite, consistent unvalidated screening errors', async t => {
  const error = { signed_um: -2, absolute_um: 2, measuredMean_um: 100,
    publishedStdDev_um: 4, model_um: 98 };
  const comparable = { ...opticalReport, status: 'comparable-screening', reasons: [],
    errors: { width: error, depth: { ...error, signed_um: 3, absolute_um: 3, model_um: 103 } } };
  respond(t, comparable);
  assert.equal((await compareNistOpticalRun(opticalRun, '0', signal)).status, 'comparable-screening');
  t.mock.restoreAll();
  respond(t, { ...comparable, errors: { ...comparable.errors, width: { ...error, absolute_um: -2 } } });
  await assert.rejects(compareNistOpticalRun(opticalRun, '0', signal), /invalid/i);
});
