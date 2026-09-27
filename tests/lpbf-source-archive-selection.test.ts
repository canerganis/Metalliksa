import assert from 'node:assert/strict';
import { test } from 'node:test';
import { persistSourceId, sourceSelectionForCatalog } from '../src/components/LpbfSourceArchivePanel';

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
