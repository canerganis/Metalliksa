import React from 'react';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import { ExperimentPlanView, LpbfExperimentPlanPanel } from '../src/components/LpbfExperimentPlanPanel';
import { LpbfBayesianOptimizerLab } from '../src/components/LpbfBayesianOptimizerLab';
import {
  checkedExperimentPlan,
  measurementTemplateCsv,
  parseExperimentPlan,
  plateLayoutCsv,
  printPlanCsv,
  LPBF_EXPERIMENT_PLAN_LABEL,
} from '../src/data/lpbfExperimentPlan';
import { setPath } from './support/jsonPath';

// SYNTHETIC two-track plan that only exercises the loader and the view (the real plan comes from Python).
const SHA = 'a'.repeat(64);
const point = (n: number, order: number, x: number) => ({
  trackId: `T0${n}`, rank: n, power_W: 100 * n, speed_mm_s: 400 * n, beamDiameter_um: 100, layer_um: 40, preheat_C: 80,
  regimeClass: 'conduction',
  score: {
    total: 1.5 / n, base: 1.5 / n, weights: { disagreement: 1, interval: 0.5, coverage: 1 },
    disagreement: { raw: 0.2, sdLnW: 0.1, sdLnD: 0.3, normalised: 1, nResolvedKernels: 3, resolvedKernels: ['eagar-tsai', 'goldak', 'rosenthal'] },
    intervalWidth: { lnHiOverLo: null, term: null, note: 'no enabled calibration cell with a 90 % interval for 316L Stainless Steel: interval width is null and contributes nothing to the score' },
    coverage: { regimeClass: 'conduction', classTrainingSets: 3, minSetsPerClass: 8, classUnderCovered: true, nearestDistanceStd: 1.2, value: 0.7 },
  },
  layout: { printOrder: order, x_start_mm: x, x_end_mm: x + 10, y_mm: 3 },
});
const fixture = (): Record<string, unknown> => ({
  schema: 'lpbf-next-experiment-plan-1', label: LPBF_EXPERIMENT_PLAN_LABEL, evidenceKind: 'screening-only',
  material: '316L Stainless Steel', configSha256: SHA,
  calibration: { available: true, calibrationId: 'synthetic', contentSha256: SHA, configSha256: SHA, implementationHash: SHA },
  intervalWidth: { lnHiOverLo: null, note: 'no enabled calibration cell with a 90 % interval for 316L Stainless Steel: interval width is null' },
  plate: { x_mm: 100, y_mm: 60, pitch_mm: 3, trackLength_mm: 10, edgeMargin_mm: 3 },
  points: [point(1, 2, 3), point(2, 1, 16)],
  commands: ['python -B python/tools/lpbf_next_experiment.py import --plan <plan-dir>/plan.json'],
  limits: 'a proposal ranked by kernel disagreement; it is not a print recommendation',
});

test('validator accepts a well-formed plan and rejects malformed or dishonest ones', () => {
  const plan = checkedExperimentPlan(fixture());
  assert.equal(plan.points.length, 2);
  const bad = (path: (string | number)[], value: unknown) => {
    const raw = fixture();
    setPath(raw, path, value);
    assert.throws(() => checkedExperimentPlan(raw), /lpbf experiment plan rejected/, JSON.stringify(path));
  };
  bad(['schema'], 'lpbf-next-experiment-plan-2');
  bad(['label'], 'Recommended print parameters');
  bad(['evidenceKind'], 'validated-simulation');
  bad(['configSha256'], 'abc');
  bad(['points'], []);
  bad(['points', 0, 'power_W'], 'high');
  bad(['points', 0, 'speed_mm_s'], -5);
  bad(['points', 0, 'regimeClass'], 'melted');
  bad(['points', 1, 'trackId'], 'T01');
  bad(['points', 0, 'layout', 'y_mm'], null);
  bad(['points', 0, 'score', 'total'], Number.NaN);
  bad(['plate', 'x_mm'], 0);
  bad(['calibration', 'available'], 'yes');
  bad(['commands'], [3]);
  const missing = fixture();
  delete missing.points;
  assert.throws(() => checkedExperimentPlan(missing), /points must be a non-empty array/);
  const unavailable = fixture();
  unavailable.calibration = { available: false };
  assert.throws(() => checkedExperimentPlan(unavailable), /calibration.reason/);
  assert.throws(() => checkedExperimentPlan(null), /not an object/);
  assert.throws(() => parseExperimentPlan('{not json'), /not valid JSON/);
  assert.equal(parseExperimentPlan(JSON.stringify(fixture())).material, '316L Stainless Steel');
  const tooMany = fixture();
  tooMany.points = Array.from({ length: 49 }, (_, i) => ({ ...point(1, i + 1, 3), trackId: `T${i}` }));
  assert.throws(() => checkedExperimentPlan(tooMany), /more than 48 points/);
});

test('CSV generation: columns, print order, blank measurement cells, quoting', () => {
  const plan = checkedExperimentPlan(fixture());
  const print = printPlanCsv(plan).trim().split('\n');
  assert.equal(print[0], 'print_order,track_id,rank,power_W,speed_mm_s,spot_um,layer_um,preheat_C,regime_class,note');
  assert.equal(print.length, 3);
  assert.ok(print[1].startsWith('1,T02,2,200,800,100,40,80,conduction,'), 'rows follow the print order');
  assert.ok(print[1].includes('not a print recommendation'));
  const layout = plateLayoutCsv(plan).trim().split('\n');
  assert.equal(layout[0], 'print_order,track_id,x_start_mm,x_end_mm,y_mm,power_W,speed_mm_s,spot_um');
  assert.equal(layout[1], '1,T02,16,26,3,200,800,100');
  const tpl = measurementTemplateCsv(plan).trim().split('\n');
  assert.equal(tpl[0], 'track_id,power_W,speed_mm_s,spot_um,width_um,depth_um,notes');
  assert.equal(tpl[1], 'T02,200,800,100,,,');
  assert.equal(tpl[2], 'T01,100,400,100,,,');
  const quoted = fixture();
  (quoted.points as Array<Record<string, unknown>>)[0].trackId = 'T,"1"';
  assert.ok(measurementTemplateCsv(checkedExperimentPlan(quoted)).includes('"T,""1"""'));
});

test('view shows the label, the table, an accessible plate svg, downloads and commands; interval null is stated', () => {
  const out = renderToStaticMarkup(<ExperimentPlanView plan={checkedExperimentPlan(fixture())} />);
  assert.ok(out.includes('data-testid="plan-table"'));
  assert.ok(out.includes('data-testid="plate-svg"'));
  assert.match(out, /aria-label="Plate layout, 100 by 60 millimetres, 2 proposed tracks"/);
  assert.ok(out.includes('Download print_plan.csv'));
  assert.ok(out.includes('Download plate_layout.csv'));
  assert.ok(out.includes('Download measurement_template.csv'));
  assert.ok(out.includes('data-testid="plan-commands"'));
  assert.ok(out.includes('n/a (no enabled cell)'));
  assert.ok(out.includes('not available (null)'));
  assert.ok(out.includes('class under-covered'));
  assert.ok(out.includes('Measured (user-supplied)'));
  assert.doesNotMatch(out, /Validated|Calibrated simulation/);
});

test('empty panel: label, creation command and a labelled file input; no plan, no error', () => {
  const out = renderToStaticMarkup(<LpbfExperimentPlanPanel />);
  assert.ok(out.includes(LPBF_EXPERIMENT_PLAN_LABEL));
  assert.ok(out.includes('data-testid="no-plan"'));
  assert.ok(out.includes('data-testid="make-plan-command"'));
  assert.match(out, /<label[^>]*>[\s\S]*Load plan\.json[\s\S]*<input type="file"/);
  assert.ok(!out.includes('data-testid="plan-error"'));
});

test('the lab has a third, keyboard-reachable tab wired with the existing tablist pattern', () => {
  const out = renderToStaticMarkup(<LpbfBayesianOptimizerLab />);
  assert.match(out, /role="tablist"/);
  assert.equal((out.match(/role="tab"/g) ?? []).length, 3);
  assert.match(out, /id="pps-tab-plan"[^>]*aria-selected="false"[^>]*aria-controls="pps-panel-plan"[^>]*tabindex="-1"/);
  assert.match(out, /id="pps-tab-window"[^>]*aria-selected="true"[^>]*tabindex="0"/);
  assert.ok(out.includes('Plan experiments'));
  assert.match(out, /id="pps-panel-plan"[^>]*aria-labelledby="pps-tab-plan"[^>]*hidden/);
  // arrow keys, Home and End move through ALL tabs (the handler walks LAB_TABS, which now holds three)
  const src = readFileSync('src/components/LpbfBayesianOptimizerLab.tsx', 'utf8');
  assert.match(src, /\{ id: "plan", label: "Plan experiments" \}/);
  assert.match(src, /event\.key === "ArrowRight"[\s\S]*event\.key === "ArrowLeft"[\s\S]*event\.key === "Home"[\s\S]*event\.key === "End"/);
  assert.match(src, /visited\.has\("plan"\) && \(IS_STATIC_DEMO \? <DemoUnavailable what="Plan experiments" \/> : <LpbfExperimentPlanPanel \/>\)/);
});

test('the panel loads the file in the browser only: no network, worker or solver service', () => {
  for (const file of ['src/components/LpbfExperimentPlanPanel.tsx', 'src/data/lpbfExperimentPlan.ts']) {
    const src = readFileSync(file, 'utf8');
    assert.doesNotMatch(src, /\bfetch\s*\(|XMLHttpRequest|new Worker|pythonComputationService|WebSocket|sendBeacon/, file);
  }
});
