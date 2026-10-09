import assert from 'node:assert/strict';
import fs from 'node:fs';
import { test } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { DEMO_REPO_URL, demoBannerText, fingerprintPrefix } from '../src/demo/demoGate.ts';
import { DemoBanner } from '../src/demo/demoBanner.tsx';

const read = (path: string) => fs.readFileSync(new URL(`../${path}`, import.meta.url), 'utf8').replace(/\r\n/g, '\n');

const INDEX = {
  appVersion: '0.1.0',
  gitCommit: 'd0f9795',
  fingerprint: 'ec7e1f7a6606e937e448fefe97549b49a7ddfe7b95376b93867ae007b0c12555',
};
const EXACT = 'Static snapshot of version 0.1.0 (d0f9795), computed offline. Not live solver output.';

test('the banner sentence is exact and takes version and commit from the index', () => {
  assert.equal(demoBannerText(INDEX), EXACT);
});

test('a missing index field is shown as unknown, never as an invented value', () => {
  assert.equal(demoBannerText(null), 'Static snapshot of version unknown, computed offline. Not live solver output.');
  assert.equal(demoBannerText({ appVersion: '0.1.0' }), 'Static snapshot of version 0.1.0, computed offline. Not live solver output.');
  assert.equal(demoBannerText({ appVersion: 7, gitCommit: '' }), 'Static snapshot of version unknown, computed offline. Not live solver output.');
});

test('the hover fingerprint is the first eight characters of the recorded fingerprint', () => {
  assert.equal(fingerprintPrefix(INDEX), 'ec7e1f7a');
  assert.equal(fingerprintPrefix(null), 'unknown');
});

test('the rendered banner carries the exact sentence, the repository link and the fingerprint hover text', () => {
  const html = renderToStaticMarkup(<DemoBanner info={INDEX} />);
  assert.ok(html.includes(EXACT), 'exact sentence');
  assert.ok(html.includes(`href="${DEMO_REPO_URL}"`), 'repository link');
  assert.ok(html.includes('title="Recorded fingerprint ec7e1f7a"'), 'fingerprint hover');
  assert.ok(html.includes('data-testid="demo-banner"'));
});

test('the banner has no dismiss control', () => {
  const html = renderToStaticMarkup(<DemoBanner info={INDEX} />);
  assert.ok(!/<button/i.test(html), 'no button');
  assert.ok(!/dismiss|close/i.test(html), 'no dismiss text');
});

test('App mounts the banner outside the module area, behind the demo flag', () => {
  const app = read('src/App.tsx');
  const mount = app.indexOf('{IS_STATIC_DEMO && <DemoBanner />}');
  assert.ok(mount > 0, 'banner mount present');
  assert.equal(app.split('<DemoBanner').length, 2, 'mounted once');
  const moduleArea = app.indexOf('<div className="flex flex-col lg:flex-row">');
  assert.ok(moduleArea > mount, 'banner renders before the module area, so no module can hide it');
});

test('the new demo strings and the banner source use no dash punctuation', () => {
  const dash = /[–—]| - /;
  assert.ok(!dash.test(EXACT));
  assert.ok(!dash.test(demoBannerText(null)));
  for (const path of ['src/demo/demoBanner.tsx']) assert.ok(!dash.test(read(path)), `${path} has dash punctuation`);
  const gate = read('src/demo/demoGate.ts');
  const bannerPart = gate.slice(gate.indexOf('DEMO_REPO_URL'));
  assert.ok(!dash.test(bannerPart), 'demoGate banner section has dash punctuation');
});
