import React from 'react';
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import { LpbfRunArchivePanel, persistRunSelectionForBundle, portableBundleSelectionKey,
  restoreRunSelectionForBundle } from '../src/components/LpbfRunArchivePanel';

test('portable bundle picker is visible and gates upload until a file is selected', () => {
  const html = renderToStaticMarkup(React.createElement(LpbfRunArchivePanel));
  assert.match(html, /aria-label="Run bundle file"/);
  assert.match(html, /accept="\.tar,application\/x-tar"/);
  assert.match(html, /<button[^>]*disabled=""[^>]*>Upload and verify bundle<\/button>/);
  assert.doesNotMatch(html, /aria-label="Run bundle file"[^>]*class="[^"]*hidden/);
});

test('a new portable bundle selection invalidates prior import state even when file metadata collides', () => {
  const first = { name: 'evidence.tar', size: 1024, lastModified: 100 };
  const replacement = { ...first };
  assert.equal(portableBundleSelectionKey(first, 4), portableBundleSelectionKey(replacement, 4));
  assert.notEqual(portableBundleSelectionKey(first, 4), portableBundleSelectionKey(replacement, 5));
  assert.notEqual(portableBundleSelectionKey(first, 4), portableBundleSelectionKey(null, 5));
});

test('a restored bundle run selection survives reload and is scoped to its verified restore', () => {
  const restoreId = 'a'.repeat(32), otherRestoreId = 'b'.repeat(32);
  const firstRun = '1'.repeat(32), secondRun = '2'.repeat(32), missingRun = '3'.repeat(32);
  const values = new Map<string, string>();
  const storage = {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value); },
  };
  const getStorage = () => storage;

  assert.equal(restoreRunSelectionForBundle(restoreId, [firstRun, secondRun], getStorage), firstRun);
  persistRunSelectionForBundle(restoreId, secondRun, getStorage);
  assert.equal(restoreRunSelectionForBundle(restoreId, [firstRun, secondRun], getStorage), secondRun);
  assert.equal(restoreRunSelectionForBundle(otherRestoreId, [firstRun, secondRun], getStorage), firstRun);

  persistRunSelectionForBundle(restoreId, missingRun, getStorage);
  assert.equal(restoreRunSelectionForBundle(restoreId, [firstRun], getStorage), firstRun);
  assert.equal(restoreRunSelectionForBundle('invalid-restore-id', [firstRun, secondRun], getStorage), firstRun);

  const readOnlyStorage = {
    getItem: () => secondRun,
    setItem: () => { throw new DOMException('Storage is unavailable.', 'SecurityError'); },
  };
  assert.equal(restoreRunSelectionForBundle(restoreId, [firstRun, secondRun], () => readOnlyStorage), secondRun);
});
