import assert from 'node:assert/strict';
import { test } from 'node:test';
import { sourceSelectionForCatalog } from '../src/components/LpbfSourceArchivePanel';

test('source archive restores a saved selection only while the catalog still contains that source', () => {
  const catalog = ['nist-amb2022-03-optical-table4-local-v1', 'nist-amb2022-03-workbook-v1'];
  assert.equal(sourceSelectionForCatalog(catalog, catalog[1]), catalog[1]);
  assert.equal(sourceSelectionForCatalog(catalog, 'deleted-source'), catalog[0]);
  assert.equal(sourceSelectionForCatalog(catalog, null), catalog[0]);
  assert.equal(sourceSelectionForCatalog([], catalog[1]), '');
});
