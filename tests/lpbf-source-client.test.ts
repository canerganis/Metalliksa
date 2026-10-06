import assert from 'node:assert/strict';
import { test } from 'node:test';
import { allSourceRevisions, sourceAction, sourceRevision, sourceRevisionHistory, type SourcePreview, type LpbfSourceRevision } from '../src/services/lpbfSourceService';

const id = 'nist-mds2-2716';
const hash = 'a'.repeat(64);
const document = { schemaVersion: 1, datasetId: id, materialId: 'in718', processScope: 'bare-plate',
  source: { url: 'https://example.org/source', citation: 'Test fixture', version: '1', terms: null, termsMissingReason: 'Unknown' },
  artifacts: [{ relativePath: 'signal.bin', sha256: hash, byteSize: 12, sourceUrl: 'https://example.org/signal' }],
  sourceContext: { measurement: { temperature_conversion: null } } } as const;
const revision: LpbfSourceRevision = { revision: 2, createdAt: '2026-09-21T00:00:00Z',
  document: { ...document, artifacts: [...document.artifacts] }, documentSha256: hash,
  evidenceStatus: 'unreviewed-source-archive', artifactIntegrity: 'not-verified' };
const preview: SourcePreview = { document: revision.document, documentSha256: hash, expectedRevision: 1,
  artifactCount: 1, byteSize: 12, evidenceStatus: 'unreviewed-source-archive', artifactIntegrity: 'verified-at-dry-run' };

function responses(t: any, values: Array<{ body: unknown; status?: number }>) {
  const calls: { url: string; init?: RequestInit }[] = [];
  t.mock.method(globalThis, 'fetch', async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    const next = values.shift();
    assert.ok(next, 'Unexpected request');
    return new Response(JSON.stringify(next.body), { status: next.status ?? 200 });
  });
  return calls;
}
test('import sends only preview identity and preserves unknown measurement values', async t => {
  const calls = responses(t, [{ body: { revision, artifactCount: 1, byteSize: 12, artifactIntegrity: 'verified-at-import' } },
    { body: { current: revision } }]);
  const result = await sourceAction(id, 'import', new AbortController().signal, preview);
  assert.equal(result.imported, true);
  assert.deepEqual(JSON.parse(calls[0].init!.body as string), { expectedRevision: 1, documentSha256: hash });
  assert.equal(result.current?.document.sourceContext?.measurement && (result.current.document.sourceContext.measurement as any).temperature_conversion, null);
  assert.equal(result.current?.artifactIntegrity, 'not-verified');
  assert.equal(result.current?.evidenceStatus, 'unreviewed-source-archive');
});
test('fresh verification is rejected when current revision changes before refresh', async t => {
  responses(t, [{ body: { datasetId: id, revision: 1, documentSha256: hash, verifiedAt: '2026-09-21T01:00:00Z',
    artifactIntegrity: 'verified-now', evidenceStatus: 'unreviewed-source-archive' } }, { body: { current: revision } }]);
  await assert.rejects(sourceAction(id, 'verify', new AbortController().signal), /changed/i);
});
test('preview is invalidated by concurrent metadata revision', async t => {
  responses(t, [{ body: preview }, { body: { current: revision } }]);
  await assert.rejects(sourceAction(id, 'preview', new AbortController().signal), /changed/i);
});
test('IN625 screening source preview is accepted without upgrading its evidence status', async t => {
  const in625Id = 'in625-bareplate-screening-local-v1';
  const in625Document = { ...document, artifacts: [...document.artifacts], datasetId: in625Id, materialId: 'in625' as const,
    sourceContext: { evidence_status: 'unreviewed-source-archive', density_assumption: { lot_matched: false } } };
  const in625Preview: SourcePreview = { document: in625Document, documentSha256: hash, expectedRevision: 0,
    artifactCount: 1, byteSize: 12, evidenceStatus: 'unreviewed-source-archive', artifactIntegrity: 'verified-at-dry-run' };
  responses(t, [{ body: in625Preview }, { body: { current: null } }]);
  const result = await sourceAction(in625Id, 'preview', new AbortController().signal);
  assert.equal(result.preview?.document.materialId, 'in625');
  assert.equal(result.preview?.evidenceStatus, 'unreviewed-source-archive');
  assert.equal(result.preview?.document.sourceContext?.evidence_status, 'unreviewed-source-archive');
});
test('HTTP failure exposes actionable status and never returns cached success', async t => {
  responses(t, [{ body: { error: 'Source or stored revision changed.' }, status: 409 }]);
  await assert.rejects(sourceAction(id, 'import', new AbortController().signal, preview), /409.*[Pp]review/);
});
test('wrong dataset and invalid integrity claims cannot become success', async t => {
  responses(t, [{ body: { current: { ...revision, document: { ...revision.document, datasetId: 'other' } } } }]);
  await assert.rejects(sourceAction(id, 'current', new AbortController().signal), /invalid|identity/i);
});

test('source revision history is paginated and every exact document hash is checked', async t => {
  const first = { ...revision, revision: 1, document: { ...revision.document, source: { ...revision.document.source, version: '1' } } };
  const second = revision;
  const summary = (value: LpbfSourceRevision) => ({ revision: value.revision, createdAt: value.createdAt,
    documentSha256: value.documentSha256, evidenceStatus: value.evidenceStatus, artifactIntegrity: value.artifactIntegrity,
    materialId: value.document.materialId, processScope: value.document.processScope });
  const calls = responses(t, [
    { body: { datasetId: id, offset: 0, limit: 1, revisions: [summary(first)], hasMore: true } },
    { body: { datasetId: id, revision: second } },
  ]);
  const page = await sourceRevisionHistory(id, new AbortController().signal, 0, 1);
  assert.equal(page.hasMore, true); assert.equal(page.revisions[0].revision, 1);
  assert.equal((await sourceRevision(id, 2, new AbortController().signal)).revision, 2);
  assert.match(calls[0].url, /\/revisions\?offset=0&limit=1$/);
  assert.match(calls[1].url, /\/revisions\/2$/);
});

test('all retained source revisions are collected and a corrupt history identity fails closed', async t => {
  const summary = (value: LpbfSourceRevision) => ({ revision: value.revision, createdAt: value.createdAt,
    documentSha256: value.documentSha256, evidenceStatus: value.evidenceStatus, artifactIntegrity: value.artifactIntegrity,
    materialId: value.document.materialId, processScope: value.document.processScope });
  const firstPage = Array.from({ length: 100 }, (_, index) => summary({ ...revision, revision: index + 1 }));
  const last = summary({ ...revision, revision: 101 });
  const calls = responses(t, [
    { body: { datasetId: id, offset: 0, limit: 100, revisions: firstPage, hasMore: true } },
    { body: { datasetId: id, offset: 100, limit: 100, revisions: [last], hasMore: false } },
  ]);
  const all = await allSourceRevisions(id, new AbortController().signal);
  assert.equal(all.length, 101); assert.equal(all[0].revision, 1); assert.equal(all[100].revision, 101);
  assert.equal(calls.length, 2);

  responses(t, [{ body: { datasetId: id, offset: 0, limit: 100,
    revisions: [{ revision: revision.revision, createdAt: revision.createdAt, documentSha256: 'bad',
      evidenceStatus: revision.evidenceStatus, artifactIntegrity: revision.artifactIntegrity,
      materialId: revision.document.materialId, processScope: revision.document.processScope }], hasMore: false } }]);
  await assert.rejects(sourceRevisionHistory(id, new AbortController().signal), /invalid|identity/i);
});
