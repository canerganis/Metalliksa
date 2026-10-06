import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { test, type TestContext } from 'node:test';
import { DatabaseSync } from 'node:sqlite';
import { LpbfSourceRepository } from '../server/lpbfSourceRepository';
import type { LpbfSourceDocument } from '../src/types/lpbfSource';

const document = () => ({
  schemaVersion: 1 as const, datasetId: 'synthetic-test', materialId: 'in718' as const,
  processScope: 'bare-plate' as const,
  source: { url: 'https://example.org/fixture', citation: 'Synthetic test only', version: '1',
    terms: null, termsMissingReason: 'Not reviewed' },
  artifacts: [{ relativePath: 'raw/fixture.json', sha256: 'a'.repeat(64), byteSize: 12,
    sourceUrl: 'https://example.org/fixture.json' }],
  sourceContext: { signalUnit: null, commandedPower_W: 0 },
});

function fixture(t: TestContext) {
  const directory = mkdtempSync(path.join(tmpdir(), 'metalliksa-source-test-'));
  const filename = path.join(directory, 'metadata.sqlite');
  const store = new LpbfSourceRepository(filename);
  const stores = [store];
  t.after(() => {
    for (const item of stores) item.close();
    rmSync(directory, { recursive: true, force: true });
  });
  return { directory, filename, store, stores };
}

test('source archive retains immutable history and null/zero across reopen', t => {
  const { filename, store, stores } = fixture(t);
  const first = store.save(document(), 0);
  assert.equal(first.revision, 1);
  assert.equal(first.evidenceStatus, 'unreviewed-source-archive');
  assert.equal(first.artifactIntegrity, 'not-verified');
  const changed = document(); changed.source.version = '2';
  store.save(changed, 1);
  assert.equal(store.revision('synthetic-test', 1)!.document.source.version, '1');
  store.close();
  const reopened = new LpbfSourceRepository(filename); stores.push(reopened);
  assert.equal(reopened.current('synthetic-test')!.document.source.version, '2');
  assert.deepEqual(reopened.current('synthetic-test')!.document.sourceContext,
    { signalUnit: null, commandedPower_W: 0 });
  assert.deepEqual(reopened.history('synthetic-test').map(r => r.revision), [1, 2]);
});

test('IN625 screening source identity is retained as an unreviewed source archive', t => {
  const { store } = fixture(t);
  const input = document() as Omit<ReturnType<typeof document>, 'materialId'> & { materialId: LpbfSourceDocument['materialId'] }; input.datasetId = 'in625-bareplate-screening-local-v1'; input.materialId = 'in625';
  const saved = store.save(input, 0);
  assert.equal(saved.document.materialId, 'in625');
  assert.equal(saved.evidenceStatus, 'unreviewed-source-archive');
  assert.equal(saved.artifactIntegrity, 'not-verified');
  assert.equal(store.current(input.datasetId)?.document.materialId, 'in625');
});

test('stale writer conflicts without replacing current or historical source metadata', t => {
  const { store, filename, stores } = fixture(t);
  const other = new LpbfSourceRepository(filename); stores.push(other);
  store.save(document(), 0);
  assert.throws(() => other.save(document(), 0), /revision conflict/i);
  assert.equal(store.history('synthetic-test').length, 1);
  other.save(document(), 1);
  assert.throws(() => store.save(document(), 1), /revision conflict/i);
  assert.equal(store.current('synthetic-test')!.revision, 2);
});

test('invalid source metadata cannot create a revision or claim measured evidence', t => {
  const { store } = fixture(t);
  for (const mutate of [
    d => { d.materialId = 'unknown'; },
    d => { d.materialId = 'in718x'; },
    d => { d.source.termsMissingReason = null; },
    d => { d.artifacts[0].relativePath = '../outside'; },
    d => { d.artifacts[0].relativePath = 'C:/outside'; },
    d => { d.artifacts[0].sha256 = 'bad'; },
    d => { d.artifacts[0].byteSize = NaN; },
    d => { d.artifacts.push({ ...d.artifacts[0] }); },
    d => { d.sourceContext.value = Infinity; },
    d => { d.evidenceStatus = 'experimentally-validated'; },
  ]) {
    const invalid: any = document(); mutate(invalid);
    assert.throws(() => store.save(invalid, 0));
  }
  assert.equal(store.current('synthetic-test'), null);
});

test('modified stored JSON fails integrity checks instead of returning a trusted record', t => {
  const { store, filename } = fixture(t);
  store.save(document(), 0);
  const db = new DatabaseSync(filename);
  try { db.exec("UPDATE lpbf_source_revisions SET document_json='{}'"); }
  finally { db.close(); }
  assert.throws(() => store.current('synthetic-test'), /integrity/i);
});

test('metadata backup opens independently and refuses an existing destination', async t => {
  const { store, directory, stores } = fixture(t);
  store.save(document(), 0);
  const destination = path.join(directory, 'backup');
  const saved = await store.backupMetadata(destination);
  assert.equal(saved.artifactPayloadsIncluded, false);
  const changed = document(); changed.source.version = '2'; store.save(changed, 1);
  const restored = new LpbfSourceRepository(saved.path); stores.push(restored);
  assert.equal(restored.current('synthetic-test')!.document.source.version, '1');
  await assert.rejects(store.backupMetadata(destination), /exist/i);
  assert.equal(restored.current('synthetic-test')!.revision, 1);
});

test('an unrelated existing database is rejected without adding application tables', t => {
  const directory = mkdtempSync(path.join(tmpdir(), 'metalliksa-foreign-test-'));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  const filename = path.join(directory, 'foreign.sqlite');
  const db = new DatabaseSync(filename);
  try {
    db.exec('CREATE TABLE user_data(value TEXT); INSERT INTO user_data VALUES (\'keep\')');
    assert.throws(() => new LpbfSourceRepository(filename), /unrecognized/i);
    assert.equal(db.prepare('SELECT value FROM user_data').get()!.value, 'keep');
    assert.equal(db.prepare("SELECT count(*) AS n FROM sqlite_master WHERE name LIKE 'lpbf_%'").get()!.n, 0);
  } finally { db.close(); }
});
