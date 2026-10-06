import assert from 'node:assert/strict';
import { test } from 'node:test';
import { persistSourceId, sourceRevisionSelectionForHistory, sourceSelectionForCatalog } from '../src/components/LpbfSourceArchivePanel';
import type { LpbfSourceRevision } from '../src/types/lpbfSource';
import type { SourceRevisionSummary } from '../src/services/lpbfSourceService';

const sourceRevision = (revision: number, documentSha256: string): LpbfSourceRevision & Pick<SourceRevisionSummary, 'materialId' | 'processScope'> => ({
  materialId: 'in718', processScope: 'bare-plate',
  revision, createdAt: `2026-09-2${revision}T00:00:00Z`,
  document: { schemaVersion: 1, datasetId: 'nist-amb2022-03-workbook-v1', materialId: 'in718', processScope: 'bare-plate',
    source: { url: 'https://example.org/source', citation: 'Test fixture', version: String(revision), terms: null, termsMissingReason: 'Unknown' },
    artifacts: [{ relativePath: 'source.bin', sha256: 'c'.repeat(64), byteSize: 1, sourceUrl: 'https://example.org/source.bin' }], sourceContext: null },
  documentSha256, evidenceStatus: 'unreviewed-source-archive', artifactIntegrity: 'not-verified',
});

test('source archive restores a saved selection only while the catalog still contains that source', () => {
  const catalog = ['nist-amb2022-03-optical-table4-local-v1', 'nist-amb2022-03-workbook-v1'];
  assert.equal(sourceSelectionForCatalog(catalog, catalog[1]), catalog[1]);
  assert.equal(sourceSelectionForCatalog(catalog, 'deleted-source'), catalog[0]);
  assert.equal(sourceSelectionForCatalog(catalog, null), catalog[0]);
  assert.equal(sourceSelectionForCatalog([], catalog[1]), '');
});

test('an empty source catalog does not erase the last persisted source selection', () => {
  const originalWindow = globalThis.window;
  const stored = new Map<string, string>([['metalliksa.lpbf.sourceArchive.selectedDataset.v1', 'nist-amb2022-03-workbook-v1']]);
  Object.defineProperty(globalThis, 'window', { configurable: true, value: {
    localStorage: {
      getItem: (key: string) => stored.get(key) ?? null,
      setItem: (key: string, value: string) => stored.set(key, value),
    },
  } as unknown as Window });
  try {
    persistSourceId('');
    assert.equal(stored.get('metalliksa.lpbf.sourceArchive.selectedDataset.v1'), 'nist-amb2022-03-workbook-v1');
    persistSourceId('nist-amb2022-03-optical-table4-local-v1');
    assert.equal(stored.get('metalliksa.lpbf.sourceArchive.selectedDataset.v1'), 'nist-amb2022-03-optical-table4-local-v1');
  } finally {
    if (originalWindow === undefined) Reflect.deleteProperty(globalThis, 'window');
    else Object.defineProperty(globalThis, 'window', { configurable: true, value: originalWindow });
  }
});

test('source archive restores exact retained revision and never silently substitutes a different identity', () => {
  const first = sourceRevision(1, 'a'.repeat(64));
  const second = sourceRevision(2, 'b'.repeat(64));
  assert.equal(sourceRevisionSelectionForHistory([first, second], null), second);
  assert.equal(sourceRevisionSelectionForHistory([first, second], { revision: 1, documentSha256: first.documentSha256 }), first);
  assert.equal(sourceRevisionSelectionForHistory([first, second], { revision: 1, documentSha256: 'f'.repeat(64) }), null);
  assert.equal(sourceRevisionSelectionForHistory([], { revision: 1, documentSha256: first.documentSha256 }), null);
});
