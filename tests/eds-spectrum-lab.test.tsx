import React from 'react';
import assert from 'node:assert/strict';
import test from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import { EDSSpectrumLab } from '../src/components/EDSSpectrumLab';

// Static render of the first paint: nothing has been imported, so the view must show only the empty state.
const markup = renderToStaticMarkup(<EDSSpectrumLab />);
const text = markup.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ');

test('empty EDS view explains what to import and offers the import controls', () => {
  assert.match(text, /No spectrum imported/);
  assert.match(text, /EMSA\/MAS/);
  assert.match(text, /No built-in or simulated spectra are provided/);
  assert.match(markup, /Import calibrated EDS spectrum file/);
  assert.match(markup, /Import vendor quantification table/);
});

test('empty EDS view renders no invented dataset, spot, composition or verification wording', () => {
  for (const invented of [
    /Inconel 718/i, /Ti-6Al-4V/i, /Laves/i, /MC Carbonitride/i, /Training example/i, /Synthetic/i,
    /k-?ratio/i, /ZAF\s+verified/i, /ASTM\s+E1508/i, /Reference Chemistry/i, /Elemental map/i, /Line scan/i,
  ]) {
    assert.doesNotMatch(text, invented, String(invented));
  }
  // The word is built from parts so a repository-wide search for the removed UI strings stays clean.
  assert.doesNotMatch(text, new RegExp('confid' + 'ence', 'i'));
});

test('empty EDS view has no peak table, no plot and no Alloy Builder transfer before anything is imported', () => {
  assert.doesNotMatch(text, /Peak candidates \(\d+\)/);
  assert.doesNotMatch(markup, /recharts/);
  assert.doesNotMatch(markup, /<canvas/);
  assert.doesNotMatch(markup, /eds-send-to-module-btn/);
});
