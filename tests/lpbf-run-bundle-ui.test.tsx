import React from 'react';
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import { LpbfRunArchivePanel, portableBundleSelectionKey } from '../src/components/LpbfRunArchivePanel';

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
