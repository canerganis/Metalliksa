import assert from 'node:assert/strict';
import fs from 'node:fs';
import { test } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MODULES, isModuleId } from '../src/data/workspaces';
import { LPBF_WORKFLOW_STAGES } from '../src/store/useLpbfWorkflowStore';
import { ModuleNav } from '../src/components/ModuleNav';
import {
  DEMO_LOCK, DEMO_UNAVAILABLE_LOCK, LOCKED_TITLE, UNAVAILABLE_TEXT, fingerprintStatus, hashModuleId, hiddenModuleRedirect, hidesCalibrationViews, visibleModules,
} from '../src/demo/demoGate.ts';
import { DEMO_MODULES, DEMO_PANELS, isDemoPanelShown } from '../src/demo/demoModules.ts';
import { DemoRedirectNote, DemoUnavailable } from '../src/demo/demoNotes.tsx';
import { DemoFingerprintGate } from '../src/demo/demoFingerprint.tsx';

const read = (path: string) => fs.readFileSync(new URL(`../${path}`, import.meta.url), 'utf8').replace(/\r\n/g, '\n');

test('every allowlisted module is a registry module, and the filter keeps exactly those', () => {
  for (const id of DEMO_MODULES) assert.ok(isModuleId(id), `${id} is not a registry module`);
  const shown = visibleModules(MODULES).map(m => m.id);
  assert.deepEqual([...shown].sort(), [...DEMO_MODULES].sort());
  assert.ok(MODULES.length > shown.length, 'some modules must be hidden');
});

test('the sidebar navigation built from the filtered list has no hidden module', () => {
  const shown = visibleModules(MODULES);
  const html = renderToStaticMarkup(<ModuleNav modules={shown} activeTab="3d-distortion-lab" activeWorkspace="lpbf" onNavigate={() => undefined} />);
  for (const module of MODULES) {
    const visible = DEMO_MODULES.includes(module.id);
    assert.equal(html.includes(`nav-desc-${module.id}"`) || html.includes(`>${module.label}<`), visible, `${module.id} nav presence`);
  }
});

test('the palette entry list built from the filtered list has no hidden module', () => {
  const ids = visibleModules(MODULES).map(m => m.id);
  for (const hidden of ['solidification-microstructure', 'phase-diagram', 'research-hub', 'database', 'experimental-validation']) {
    assert.ok(isModuleId(hidden), `${hidden} must stay a registry id for this test to mean something`);
    assert.ok(!ids.includes(hidden), `${hidden} leaked into the demo list`);
  }
});

test('a hash to a hidden module goes home; shown, home and unknown hashes are left alone', () => {
  for (const hidden of ['#/solidification-microstructure', '#/phase-diagram?tab=x', '#/research-hub/sub', '#database', '#/experimental-validation']) {
    assert.equal(hiddenModuleRedirect(hidden, isModuleId), '#/home', hidden);
  }
  for (const ok of ['#/lpbf-optimizer', '#/3d-distortion-lab?tab=x', '#/keyhole-raytracing', '', '#', '#/', '#/home', '#/not-a-module']) {
    assert.equal(hiddenModuleRedirect(ok, isModuleId), null, ok);
  }
  assert.equal(hashModuleId('#/lpbf-optimizer?tab=window'), 'lpbf-optimizer');
});

test('App runs the hidden-id redirect before it maps unknown hashes to 3d-distortion-lab', () => {
  const app = read('src/App.tsx');
  const initial = app.slice(app.indexOf('function initialTab()'), app.indexOf('export default function App'));
  assert.ok(initial.indexOf('demoRedirectHidden()') >= 0);
  assert.ok(initial.indexOf('demoRedirectHidden()') < initial.indexOf('moduleFromHash('), 'initial hash: redirect before module lookup');
  assert.ok(initial.indexOf('demoRedirectHidden()') < initial.indexOf("return '3d-distortion-lab'"), 'initial hash: redirect before the unknown-hash fallback');
  const onHash = app.slice(app.indexOf('const onHash = () => {'), app.indexOf('const onNavigate'));
  assert.ok(onHash.indexOf('demoRedirectHidden()') >= 0 && onHash.indexOf('demoRedirectHidden()') < onHash.indexOf('moduleFromHash('), 'hashchange: redirect first');
  assert.ok(app.includes('!demoAllowedModule(id)'), 'navigate() refuses hidden ids');
  assert.ok(app.includes('demoAllowedModule(resolveModuleId(localStorage'), 'a remembered hidden module is not restored');
});

test('App keeps the module-contract line anchor of the phase-diagram case', () => {
  const lines = read('src/App.tsx').split('\n');
  assert.equal(lines[198], "      case 'phase-diagram': return <PhaseDiagramViewer />;");
});

test('panel allowlist covers every 3d-distortion-lab stage plus the specialist lab, without overlap', () => {
  const panels = DEMO_PANELS['3d-distortion-lab'];
  const all = [...panels.shown, ...panels.unavailable];
  assert.equal(new Set(all).size, all.length, 'no panel is both shown and unavailable');
  assert.deepEqual([...all].sort(), [...LPBF_WORKFLOW_STAGES.map(s => s.id), 'specialists'].sort());
  assert.ok(isDemoPanelShown('3d-distortion-lab', 'melt-pool'));
  assert.ok(!isDemoPanelShown('3d-distortion-lab', 'build'));
  assert.ok(isDemoPanelShown('lpbf-optimizer', 'window'));
  assert.ok(!isDemoPanelShown('lpbf-optimizer', 'search'));
  assert.ok(!isDemoPanelShown('lpbf-optimizer', 'plan'));
  assert.ok(!isDemoPanelShown('phase-diagram', 'anything'));
});

test('lock props carry the exact disabled-control title', () => {
  assert.equal(LOCKED_TITLE, 'Recorded values only in the static demo.');
  assert.deepEqual({ ...DEMO_LOCK }, { disabled: true, title: 'Recorded values only in the static demo.' });
  assert.deepEqual({ ...DEMO_UNAVAILABLE_LOCK }, { disabled: true, title: 'Not available in the static demo.' });
});

test('locks are applied to the grid inputs and the shared process inputs', () => {
  const map = read('src/components/LpbfProcessWindowMap.tsx');
  for (const label of ['Power minimum (W)', 'Power maximum (W)', 'Power points', 'Speed minimum (mm/s)', 'Speed maximum (mm/s)', 'Speed points']) {
    assert.ok(map.includes(`<input {...lock} aria-label="${label}"`), label);
  }
  const workspace = read('src/components/LpbfEngineeringWorkspace.tsx');
  for (const marker of ['<select {...lock} aria-label="Load LPBF alloy preset"', '<input {...lock} aria-label={`${label} (${unit})`}', 'Scan strategy<select {...lock}', '<input {...lock} className={inputStyle} value={specimen.lpbf.specimenDoi}']) {
    assert.ok(workspace.includes(marker), marker);
  }
  assert.ok(workspace.includes('{...unavailable} onClick={exportReport}'));
  assert.ok(workspace.includes('{!IS_STATIC_DEMO&&<LpbfRunReportExport'));
});

test('unavailable note and redirect note render the exact English text', () => {
  assert.match(renderToStaticMarkup(<DemoUnavailable />), />Not available in the static demo\.</);
  assert.match(renderToStaticMarkup(<DemoUnavailable what="Build" />), />Build: Not available in the static demo\.</);
  assert.match(renderToStaticMarkup(<DemoRedirectNote />), /That module is not part of the static demo\./);
  assert.equal(UNAVAILABLE_TEXT, 'Not available in the static demo.');
});

test('fingerprint guard: match, mismatch and unknown', () => {
  const bundled = JSON.parse(read('data/calibration/lpbf-meltpool-error-bands-v1.summary.json')).implementationHash as string;
  const recorded = JSON.parse(read('demo/snapshots/index.json')).fingerprint as string;
  assert.equal(fingerprintStatus(recorded, bundled), 'match', 'committed snapshots must match the committed error bands');
  assert.equal(fingerprintStatus(bundled.toUpperCase(), bundled), 'match');
  assert.equal(fingerprintStatus('0'.repeat(64), bundled), 'mismatch');
  assert.equal(fingerprintStatus(bundled.slice(0, 8), bundled), 'mismatch', 'a prefix is not a match');
  for (const missing of [undefined, null, '', 5]) {
    assert.equal(fingerprintStatus(missing, bundled), 'unknown');
    assert.equal(fingerprintStatus(bundled, missing), 'unknown');
  }
  assert.equal(hidesCalibrationViews('mismatch'), true);
  assert.equal(hidesCalibrationViews('match'), false);
  assert.equal(hidesCalibrationViews('unknown'), false);
});

test('the fingerprint gate shows its children until a mismatch is proven', () => {
  const html = renderToStaticMarkup(<DemoFingerprintGate><p>process window</p></DemoFingerprintGate>);
  assert.match(html, /process window/);
  assert.doesNotMatch(html, /demo-fingerprint-mismatch/);
});

test('DemoLock renders a disabled fieldset around its controls', async () => {
  const { DemoLock } = await import('../src/demo/demoNotes.tsx');
  const html = renderToStaticMarkup(<DemoLock><input aria-label="x" /><button>Go</button></DemoLock>);
  assert.match(html, /^<fieldset[^>]*\bdisabled=""/);
  assert.match(html, /<input aria-label="x"\/><button>Go<\/button>/);
});

test('thermal simulation panel: recorded Quick Screening only, unrecorded sections locked', () => {
  const src = read('src/components/3d-distortion-lab/LpbfEngineeringSimulation.tsx');
  assert.ok(src.includes('IS_STATIC_DEMO&&m.id!=="screening"?DEMO_UNAVAILABLE_LOCK:{}'), 'non-screening modes are disabled');
  assert.ok(src.includes('if (IS_STATIC_DEMO && mode!=="screening") setMode("screening")'), 'mode is forced to the recorded one');
  assert.equal((src.match(/<Lock>/g) ?? []).length, 3, 'process settings, advanced controls and validation sections are locked');
  assert.ok(src.includes('{IS_STATIC_DEMO ? <DemoUnavailable what="CUDA thermal parity pilot" />'));
  assert.ok(src.includes('{IS_STATIC_DEMO ? <DemoUnavailable what="Bare-plate IN625 comparison" />'));
  assert.ok(src.includes('const Lock: React.ElementType = IS_STATIC_DEMO ? DemoLock : React.Fragment;'), 'a normal build renders a plain fragment');
});
