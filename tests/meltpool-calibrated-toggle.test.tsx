import React from 'react';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import test from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import {
  CalibratedMeltpoolPanel,
  CalibratedResultView,
  shouldRequestCalibrated,
  SCORECARD_HASH,
} from '../src/components/3d-distortion-lab/CalibratedMeltpoolPanel';
import {
  COMMITTED_CALIBRATION_ARTEFACT,
  enabledCellsFor,
  summarizeCalibrationArtefact,
  type CalibrationArtefactSummary,
} from '../src/data/lpbfCalibrationArtefact';
import type { LPBFCalibratedMeltpoolResult } from '../src/services/pythonComputationService';

const request = { laserPower_W: 200, scanSpeed_mm_s: 900, beamDiameter_um: 80, preheatTemp_C: 20, layerThickness_um: 30, hatchSpacing_um: 100 };
const noCells: CalibrationArtefactSummary = {
  calibrationId: 'synthetic',
  cells: [{ kernel: 'eagar-tsai', material: '316L Stainless Steel', quantity: 'width', status: 'within-source-only' },
    { kernel: 'eagar-tsai', material: '316L Stainless Steel', quantity: 'depth', status: 'rejected' }],
};
// SYNTHETIC summary with one enabled cell: exercises the control, not any physics.
const oneEnabled: CalibrationArtefactSummary = {
  calibrationId: 'synthetic',
  cells: [{ kernel: 'eagar-tsai', material: '316L Stainless Steel', quantity: 'width', status: 'enabled' },
    { kernel: 'eagar-tsai', material: '316L Stainless Steel', quantity: 'depth', status: 'rejected' }],
};
const panel = (summary: CalibrationArtefactSummary | null, heatSource: 'goldak' | 'eagar-tsai' | 'rosenthal' = 'eagar-tsai') =>
  renderToStaticMarkup(<CalibratedMeltpoolPanel heatSource={heatSource} material="316L Stainless Steel" request={request} summary={summary} />);

test('no enabled cell: the toggle is NOT rendered (hidden, never greyed out); the scorecard link stays', () => {
  for (const s of [null, noCells]) {
    const out = panel(s);
    assert.doesNotMatch(out, /data-testid="calibrated-toggle"/);
    assert.doesNotMatch(out, /disabled/);
    assert.doesNotMatch(out, /type="checkbox"/);
    assert.ok(out.includes('data-testid="calibration-link-only"'));
    assert.ok(out.includes(`href="${SCORECARD_HASH}"`));
  }
});

test('the toggle exists only for the kernel and alloy that own an enabled cell, and is OFF by default', () => {
  const on = panel(oneEnabled);
  assert.ok(on.includes('data-testid="calibrated-toggle"'));
  assert.doesNotMatch(on, /checked=""/);
  assert.doesNotMatch(on, /data-testid="calibrated-result"/);
  assert.doesNotMatch(panel(oneEnabled, 'goldak'), /data-testid="calibrated-toggle"/);
  assert.equal(enabledCellsFor(oneEnabled, 'eagar-tsai', '316L Stainless Steel').length, 1);
  assert.equal(enabledCellsFor(oneEnabled, 'eagar-tsai', 'Ti-6Al-4V').length, 0);
});

test('a calibrated request is issued only when opted in AND an enabled cell exists', () => {
  assert.equal(shouldRequestCalibrated(false, 1), false);
  assert.equal(shouldRequestCalibrated(true, 0), false);
  assert.equal(shouldRequestCalibrated(true, 1), true);
});

test('OFF issues the old request only: the lab never calls the calibrated service and the panel calls it only when active (source guard)', () => {
  const lab = readFileSync('src/components/3d-distortion-lab/MeltPool3DCrossSectionLab.tsx', 'utf8');
  assert.ok(lab.includes('solveLPBFThermalPhysics'));
  assert.doesNotMatch(lab, /solveLPBFCalibratedMeltpool/);
  const src = readFileSync('src/components/3d-distortion-lab/CalibratedMeltpoolPanel.tsx', 'utf8');
  assert.equal((src.match(/\.solveLPBFCalibratedMeltpool\(/g) ?? []).length, 1);
  assert.match(src, /if \(!active\) \{ setResult\(null\); setError\(null\); return; \}/);
  assert.match(src, /useState\(false\); \/\/ default OFF/);
  assert.doesNotMatch(src, /localStorage|sessionStorage/);
  const service = readFileSync('src/services/pythonComputationService.ts', 'utf8');
  assert.match(service, /fetch\("\/api\/python\/lpbf-calibrated-meltpool"/);
  assert.match(service, /fetch\("\/api\/python\/lpbf-thermal-solver"/);
});

const widthOnly: LPBFCalibratedMeltpoolResult = {
  screening: {} as never,
  evidenceKind: 'screening-only',
  calibrated: {
    available: true, width_um: 151.2, depth_um: null, width_pi90_um: [124, 184], depthReason: 'cell status rejected: not served',
    regimeLabel: 'keyhole', depthOverWidth: null,
    depthOverWidthReason: 'only one quantity is served: no depth/width, length/width, regime or aspect ratio is derived from a mix of calibrated and screening values',
  },
  calibration: {
    calibrationId: 'synthetic', contentSha256: '0'.repeat(64), fittedOn: ['hofmann-316l-2026 (677 rows)', 'ku-leuven-316l-2021 (44 rows)'],
    heldOutScore: { width: 'ku-leuven-316l-2021: MAPE 16.6 -> 12.0 % (n=44 rows, 44 sets), skill CI95 [0.05, 0.40]; rung selected in training only' },
    evidenceKind: 'screening-only', label: 'Screening only: calibrated mode (not validation)',
  },
  outsideTrainingEnvelope: false, envelopeNotes: [],
};

test('only W served: no D/W, L/W or aspect ratio is derived; badge, fitted-on sources, held-out line and scorecard link are present', () => {
  const out = renderToStaticMarkup(<CalibratedResultView result={widthOnly} />);
  assert.ok(out.includes('data-testid="calibrated-badge"') && out.includes('Screening only'));
  assert.ok(out.includes('Screening only (not validation)'));
  assert.ok(out.includes('hofmann-316l-2026 (677 rows)') && out.includes('ku-leuven-316l-2021 (44 rows)'));
  assert.ok(out.includes('rung selected in training only'));
  assert.ok(out.includes(`href="${SCORECARD_HASH}"`) && out.includes('Open scorecard'));
  assert.ok(out.includes('PI 90 %: [124, 184] µm'));
  const ratio = out.split('data-testid="cal-ratio"')[1]?.split('</div>')[0] ?? '';
  assert.ok(ratio.includes('—') && !/\d\.\d\d/.test(ratio.replace(/<[^>]*>/g, '').replace(/aspect ratio/g, '')), ratio);
  const aspect = out.split('data-testid="cal-aspect"')[1]?.split('</div>')[0] ?? '';
  assert.ok(aspect.includes('—'));
  const depth = out.split('data-testid="cal-depth"')[1]?.split('</strong>')[0] ?? '';
  assert.ok(depth.includes('—') && depth.includes('not served'));
  assert.ok(out.includes('Regime label (screening, at the default absorptivity, unchanged)'));
  assert.doesNotMatch(out, /Calibrated simulation/);
});

test('both served: D/W is shown; outside the envelope the numbers are greyed with the reason', () => {
  const both: LPBFCalibratedMeltpoolResult = {
    ...widthOnly,
    calibrated: { ...widthOnly.calibrated, depth_um: 90.5, depthOverWidth: 0.6, depthOverWidthReason: null },
    outsideTrainingEnvelope: true, envelopeNotes: ['power 900 outside the training range [100, 350]'],
  };
  const out = renderToStaticMarkup(<CalibratedResultView result={both} />);
  assert.ok((out.split('data-testid="cal-ratio"')[1] ?? '').includes('0.60'));
  assert.ok(out.includes('opacity-50'));
  assert.ok(out.includes('data-testid="envelope-warning"') && out.includes('power 900 outside the training range'));
});

test('unavailable artefact: the unavailable reason is shown instead of numbers', () => {
  const stale: LPBFCalibratedMeltpoolResult = { ...widthOnly, calibrated: { available: false, reason: 'calibration stale for this physics version', width_um: null, depth_um: null }, calibration: null };
  const out = renderToStaticMarkup(<CalibratedResultView result={stale} />);
  assert.ok(out.includes('calibration stale for this physics version'));
  assert.doesNotMatch(out, /data-testid="cal-width"/);
});

test('the committed artefact (if present) drives the control: zero enabled cells means no toggle anywhere', () => {
  const path = 'data/calibration/lpbf-meltpool-calibration-v1.json';
  if (!existsSync(path)) return; // absent artefact: nothing to assert (the control is hidden by construction)
  const summary = summarizeCalibrationArtefact(JSON.parse(readFileSync(path, 'utf8')));
  assert.ok(summary, 'artefact must parse');
  assert.equal(COMMITTED_CALIBRATION_ARTEFACT, null, 'under tsx the Vite glob is unavailable');
  const enabled = summary.cells.filter((c) => c.status === 'enabled');
  for (const kernel of ['goldak', 'eagar-tsai', 'rosenthal'] as const) {
    for (const material of ['316L Stainless Steel', 'Ti-6Al-4V', 'Inconel 625', 'Inconel 718']) {
      const out = renderToStaticMarkup(<CalibratedMeltpoolPanel heatSource={kernel} material={material} request={request} summary={summary} />);
      const has = enabled.some((c) => c.kernel === kernel && c.material === material);
      assert.equal(out.includes('data-testid="calibrated-toggle"'), has, `${kernel}/${material}`);
    }
  }
});

test('a PI 90 % wider than x2.5 is labelled not informative for each served quantity (R6/R11)', () => {
  const wide: LPBFCalibratedMeltpoolResult = {
    ...widthOnly,
    calibrated: { ...widthOnly.calibrated, depth_um: 90, depth_pi90_um: [30, 260], depth_pi90_notInformative: true,
      width_pi90_notInformative: false, depthReason: undefined },
  };
  const out = renderToStaticMarkup(<CalibratedResultView result={wide} />);
  assert.ok(out.includes('data-testid="cal-depth-not-informative"') && out.includes('not informative: wider than ×2.5'));
  assert.doesNotMatch(out, /data-testid="cal-width-not-informative"/);
  const narrow = renderToStaticMarkup(<CalibratedResultView result={widthOnly} />);
  assert.doesNotMatch(narrow, /not informative/);
});
