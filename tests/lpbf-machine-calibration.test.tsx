import React from 'react';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import {
  CalibratedMeltpoolPanel,
  MachineCalibrationSection,
  MachineResultView,
} from '../src/components/3d-distortion-lab/CalibratedMeltpoolPanel';
import { MachineTileLine } from '../src/components/3d-distortion-lab/MachineTileLine';
import { ExperimentPlanView } from '../src/components/LpbfExperimentPlanPanel';
import {
  MACHINE_BADGE_CALIBRATED,
  MACHINE_BADGE_SCREENING,
  MACHINE_PRIVACY_SENTENCE,
  machineEvidenceBadge,
  machineReportLines,
  machineTileLine,
  parseMachineCalibratedResult,
  parseMissingMethodFields,
  parseMachineCalibrationStatus,
  type MachineArtefactSummary,
  type MachineCalibratedBlock,
  type MachineCalibrationStatus,
} from '../src/data/lpbfMachineCalibration';
import { LPBF_EXPERIMENT_PLAN_LABEL, checkedExperimentPlan, measurementTemplateCsv } from '../src/data/lpbfExperimentPlan';
import { pythonComputationService } from '../src/services/pythonComputationService';
import { useMaterialSpecimenStore } from '../src/store/useMaterialSpecimenStore';
import { LPBF_ENGINEERING_DEFAULTS, type LpbfEngineeringState } from '../src/store/useLpbfEngineeringStore';
import { createLpbfQualificationReport } from '../src/utils/lpbfQualificationReport';
import { buildLpbfRunReportHtml } from '../src/utils/lpbfRunReport';

// SYNTHETIC fixtures that exercise presentation and the label rule only. No number here is a physical result.
const MATERIAL = '316L Stainless Steel';
const request = { laserPower_W: 200, scanSpeed_mm_s: 900, beamDiameter_um: 80, preheatTemp_C: 20, layerThickness_um: 30, hatchSpacing_um: 100 };
const SHA = 'c'.repeat(64);

const cell = (kernel: string, status: string, extra: Record<string, unknown> = {}) => ({
  kernel, quantity: 'depth', status, evidenceKind: 'screening-only', evidenceScope: null, evidenceLabel: 'Screening only',
  missingMethodFields: [], reasonText: [], ...extra,
});
const artefactDoc = (extra: Record<string, unknown> = {}) => ({
  machineCalibrationId: 'mc-0123456789ab', userSourceId: 'user-abc', contentSha256: SHA, material: MATERIAL, generatedAt: '2026-10-09T00:00:00Z',
  nTracks: 6, state: 'ready', experimentalValidation: false,
  cells: [
    cell('rosenthal', 'served', { evidenceKind: 'calibrated-simulation', evidenceScope: 'this machine, user data' }),
    cell('eagar-tsai', 'not-eligible', { reasonText: ['machine calibration is not offered for Eagar-Tsai depth'] }),
    cell('goldak', 'refused', { reasonText: ['factorOutOfRange: the fitted factor is outside 1/3..3'] }),
  ],
  ...extra,
});
const statusOf = (...docs: Record<string, unknown>[]): MachineCalibrationStatus => parseMachineCalibrationStatus({ success: true, artefacts: docs });
const ready = statusOf(artefactDoc());

const servedBlock = (extra: Partial<MachineCalibratedBlock> = {}): MachineCalibratedBlock => ({
  available: true, machineCalibrationId: 'mc-0123456789ab', status: 'served', depth_um: 96, depthBand_um: [55, 165], factor: 0.8,
  evidenceKind: 'calibrated-simulation', evidenceScope: 'this machine, user data', missingMethodFields: [], reasonText: [],
  experimentalValidation: false, usedForBuildJobVerdict: false, ...extra,
});
const artefact = (): MachineArtefactSummary => ready.artefacts[0];

const ID = 'mc-0123456789ab';
const section = (status: MachineCalibrationStatus | null, heatSource: 'goldak' | 'eagar-tsai' | 'rosenthal' = 'rosenthal', material = MATERIAL, selectedId: string | null = null) =>
  renderToStaticMarkup(<MachineCalibrationSection heatSource={heatSource} material={material} request={request} status={status} selectedId={selectedId} />);

test('selector is hidden (not greyed out) without a ready artefact for this alloy', () => {
  for (const status of [null, statusOf(), statusOf({ ...artefactDoc(), state: 'stale' }), ready]) {
    const out = section(status, 'rosenthal', status === ready ? 'Ti-6Al-4V' : MATERIAL);
    assert.equal(out, '', 'renders nothing at all');
  }
  const panel = renderToStaticMarkup(<CalibratedMeltpoolPanel heatSource="rosenthal" material={MATERIAL} request={request} summary={null} machineStatus={statusOf()} />);
  assert.doesNotMatch(panel, /machine-select|Machine calibration \(user data\)/);
});

test('selector appears with an artefact, defaults to none and shows no result until chosen', () => {
  const out = section(ready);
  assert.match(out, /data-testid="machine-select"/);
  assert.match(out, /Machine calibration \(user data\)/);
  assert.match(out, /None \(screening only\)/);
  assert.match(out, /mc-0123456789ab · user-abc · 6 tracks/);
  assert.doesNotMatch(out, /data-testid="machine-result"/);
  assert.doesNotMatch(out, /<select[^>]* disabled/);
});

test('served cell: value, factor, 80 % band "not a tolerance", calibrated badge, privacy sentence', () => {
  const out = renderToStaticMarkup(<MachineResultView artefact={artefact()} kernel="rosenthal" block={servedBlock()} screeningDepth={120} />);
  assert.match(out, /data-testid="machine-depth"[^>]*>96\.0 µm/);
  assert.match(out, /factor 0\.800/);
  assert.match(out, /80 % band: \[55, 165\] µm \(not a tolerance\)/);
  assert.match(out, /Screening depth, unchanged \(flat-plate basis used by the machine fit\): 120\.0 µm/);
  assert.ok(out.includes(MACHINE_BADGE_CALIBRATED));
  assert.ok(out.includes(MACHINE_PRIVACY_SENTENCE.replace(/&/g, '&amp;')));
  assert.match(out, /not an absorptivity/);
  assert.doesNotMatch(out, /machine-missing-fields/);
  assert.doesNotMatch(out, /[Vv]alidated(?! simulation)/);
});

test('served cell with missing method fields is screening only and lists the fields', () => {
  const block = servedBlock({ evidenceKind: 'screening-only', evidenceScope: null, missingMethodFields: parseMissingMethodFields([{ trackIds: ['t1'], fields: ['depthDatum', 'replicates'] }]) });
  const out = renderToStaticMarkup(<MachineResultView artefact={artefact()} kernel="rosenthal" block={block} screeningDepth={120} />);
  assert.ok(out.includes(MACHINE_BADGE_SCREENING));
  assert.ok(!out.includes(MACHINE_BADGE_CALIBRATED));
  assert.match(out, /data-testid="machine-missing-fields"[^>]*>[^<]*depth datum, replicates/);
  assert.match(out, /data-testid="machine-depth"/, 'the value is still shown');
});

test('label rule: calibrated badge only for a served, complete, scoped block; never from a refused cell', () => {
  const ok = servedBlock();
  assert.equal(machineEvidenceBadge(ok), MACHINE_BADGE_CALIBRATED);
  assert.equal(machineEvidenceBadge({ ...ok, available: false }), MACHINE_BADGE_SCREENING);
  assert.equal(machineEvidenceBadge({ ...ok, evidenceScope: 'global' }), MACHINE_BADGE_SCREENING);
  assert.equal(machineEvidenceBadge({ ...ok, evidenceScope: null }), MACHINE_BADGE_SCREENING);
  assert.equal(machineEvidenceBadge({ ...ok, missingMethodFields: parseMissingMethodFields([{ trackIds: ['t1'], fields: ['depthDatum'] }]) }), MACHINE_BADGE_SCREENING);
  assert.equal(machineEvidenceBadge({ ...ok, evidenceKind: 'screening-only' }), MACHINE_BADGE_SCREENING);
  assert.equal(machineEvidenceBadge({ ...ok, experimentalValidation: true }), MACHINE_BADGE_SCREENING);
  assert.equal(machineEvidenceBadge({ ...ok, evidenceKind: 'validated' }), MACHINE_BADGE_SCREENING);
});

test('screening line states the flat-plate basis in both the served and the refused branch', () => {
  const label = 'Screening depth, unchanged (flat-plate basis used by the machine fit): 120.0 µm';
  const served = renderToStaticMarkup(<MachineResultView artefact={artefact()} kernel="rosenthal" block={servedBlock()} screeningDepth={120} />);
  assert.ok(served.includes(label));
  const refused = renderToStaticMarkup(<MachineResultView artefact={artefact()} kernel="goldak" block={servedBlock({ available: false, depth_um: null, status: 'refused' })} screeningDepth={120} />);
  assert.match(refused, /data-testid="machine-refused"/);
  assert.ok(refused.includes(label));
});

test('refused and not-eligible cells show their reasons and the screening badge', () => {
  for (const [kernel, reason] of [['goldak', 'factorOutOfRange'], ['eagar-tsai', 'not offered for Eagar-Tsai']] as const) {
    const out = section(ready, kernel, MATERIAL, ID);
    assert.match(out, /data-testid="machine-refused"/);
    assert.ok(out.includes(reason), reason);
    assert.ok(out.includes(MACHINE_BADGE_SCREENING));
    assert.doesNotMatch(out, /data-testid="machine-depth"/);
  }
});

test('parsers drop stale, malformed and path-like entries and never invent a served value', () => {
  const status = parseMachineCalibrationStatus({
    success: true,
    artefacts: [artefactDoc(), { ...artefactDoc(), state: 'stale' }, { ...artefactDoc(), machineCalibrationId: '../../etc/passwd' }, 'junk'],
  });
  assert.equal(status.artefacts.length, 1);
  assert.equal(status.skipped, 3);
  assert.deepEqual(parseMachineCalibrationStatus({ success: false }).artefacts, []);
  assert.equal(parseMachineCalibratedResult({ nothing: true }), null);
  const parsed = parseMachineCalibratedResult({ screening: {}, machineCalibrated: { available: true, depth_um: 'x', depthBand_um: [1], experimentalValidation: true } });
  assert.equal(parsed!.machineCalibrated.depth_um, null);
  assert.equal(parsed!.machineCalibrated.depthBand_um, null);
  assert.equal(parsed!.experimentalValidation, false);
});

test('Build Job tile: calibrated depth is a second line next to, never instead of, the screening value', () => {
  assert.match(machineTileLine(servedBlock(), 120)!, /^Machine depth 96\.0 µm \(screening 120\.0 µm\) · Calibrated simulation/);
  assert.equal(machineTileLine(servedBlock({ available: false }), 120), null);
  assert.equal(machineTileLine(null, 120), null);
  assert.equal(renderToStaticMarkup(<MachineTileLine material={MATERIAL} request={request} screeningDepth={120} status={ready} selectedId={null} />), '', 'no line without a selection');
  const served = renderToStaticMarkup(<MachineTileLine material={MATERIAL} request={request} screeningDepth={120} status={ready} selectedId={ID} />);
  assert.match(served, /data-testid="machine-tile-line"/);
  const refusedStatus = statusOf(artefactDoc({ cells: [cell('rosenthal', 'refused', { reasonText: ['uniformSign: mixed residuals'] })] }));
  assert.match(renderToStaticMarkup(<MachineTileLine material={MATERIAL} request={request} screeningDepth={120} status={refusedStatus} selectedId={ID} />), /Machine depth not served: uniformSign/);
  const src = readFileSync('src/components/3d-distortion-lab/IndustrialLPBFDecisionLab.tsx', 'utf8');
  assert.match(src, /value=\{`\$\{thermal\.meltPoolGeometry\.width_um\}×\$\{thermal\.meltPoolGeometry\.depth_um\}`\}/, 'the tile value is still the screening W×D');
  assert.match(src, /sub=\{<MachineTileLine/);
  assert.doesNotMatch(src, /machineCalibrated.*verdict|verdict.*machineCalibrated/i);
});

test('service sends the artefact id (never a path) and reads the status with GET', async () => {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  const realFetch = globalThis.fetch;
  globalThis.fetch = (async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    const body = url.endsWith('/status')
      ? { success: true, artefacts: [artefactDoc()] }
      : { success: true, screening: { meltPoolGeometry: { depth_um: 120 } }, machineCalibrated: servedBlock(), experimentalValidation: false };
    return new Response(JSON.stringify(body), { status: 200 });
  }) as typeof fetch;
  try {
    const status = await pythonComputationService.getLpbfMachineCalibrationStatus();
    assert.equal(status.artefacts.length, 1);
    const result = await pythonComputationService.solveLPBFMachineCalibratedMeltpool({ ...request, material: MATERIAL, heatSource: 'rosenthal', machineCalibration: 'mc-0123456789ab' });
    assert.equal(result.machineCalibrated.depth_um, 96);
    assert.equal(calls[0].url, '/api/python/lpbf-machine-calibration/status');
    assert.equal(calls[0].init?.method, 'GET');
    assert.equal(calls[1].url, '/api/python/lpbf-machine-calibrated-meltpool');
    assert.equal(JSON.parse(String(calls[1].init?.body)).machineCalibration, 'mc-0123456789ab');
  } finally {
    globalThis.fetch = realFetch;
  }
});

test('default Melt Pool and Build Job paths do not touch machine calibration (source guard)', () => {
  const lab = readFileSync('src/components/3d-distortion-lab/MeltPool3DCrossSectionLab.tsx', 'utf8');
  assert.doesNotMatch(lab, /MachineCalibrated|lpbf-machine-calibr/);
  const store = readFileSync('src/store/useLpbfBuildJobStore.ts', 'utf8');
  assert.doesNotMatch(store, /machineCalibration/);
  const hook = readFileSync('src/components/3d-distortion-lab/useMachineDepth.ts', 'utf8');
  assert.doesNotMatch(hook, /localStorage|sessionStorage/);
  assert.match(hook, /if \(!artefact\) \{ setResult\(null\)/, 'no request without a selected artefact');
});

// ---- run report ---------------------------------------------------------------------------------------------------
const CREATED = '2026-01-02T03:04:05.000Z';
const engineering = (): LpbfEngineeringState => ({ settings: { ...LPBF_ENGINEERING_DEFAULTS }, mode: 'standard', job: undefined, error: '', busy: false, material: '', properties: '', measurements: '', specimen: '', uncertainty: '', holdout: 'unknown', width: '', depth: '', source: '', submittedSignature: '', resultSignature: '', submittedInput: undefined });
const baseReport = () => createLpbfQualificationReport(
  useMaterialSpecimenStore.getState().activeSpecimen,
  { buildId: 'B-1', machine: 'M1', powderLot: 'L1', powderCondition: '', heatTreatment: '', measurementMethod: '', notes: '' },
  engineering(), null, [],
);

test('run report prints a Machine calibration (user data) block only when one is supplied', () => {
  const report = baseReport();
  const without = buildLpbfRunReportHtml(report, { buildJob: null }, { createdAt: CREATED, dossierSha256: null });
  assert.doesNotMatch(without, /Machine calibration \(user data\)/);
  assert.equal(without, buildLpbfRunReportHtml(report, { buildJob: null, machineCalibration: null }, { createdAt: CREATED, dossierSha256: null }));
  const input = { artefact: artefact(), kernel: 'rosenthal', block: servedBlock({ missingMethodFields: parseMissingMethodFields([{ trackIds: ['t1'], fields: ['depthDatum'] }]), evidenceKind: 'screening-only', evidenceScope: null }), screeningDepth_um: 120 };
  const html = buildLpbfRunReportHtml(report, { buildJob: null, machineCalibration: input }, { createdAt: CREATED, dossierSha256: null });
  assert.match(html, /Machine calibration \(user data\)/);
  assert.ok(html.includes('mc-0123456789ab') && html.includes(SHA));
  assert.match(html, /80 % band \(not a tolerance\)/);
  assert.match(html, /Screening only \(experimental validation: false\)/);
  assert.match(html, /Missing method fields[\s\S]*depth datum/);
  assert.match(html, /Screening depth \(unchanged\)/);
  assert.match(html, /never uses this depth/);
  const dossier = /id="dossier-data">([\s\S]*?)<\/script>/.exec(html)![1];
  assert.ok(!dossier.includes('mc-0123456789ab'), 'display only: not part of the hashed dossier');
  assert.ok(machineReportLines(input).length >= 8);
});

// ---- experiment plan ----------------------------------------------------------------------------------------------
const planPoint = (n: number) => ({
  trackId: `T0${n}`, rank: n, power_W: 100 * n, speed_mm_s: 400 * n, beamDiameter_um: 100, layer_um: 40, preheat_C: 80, regimeClass: 'conduction',
  score: {
    total: 1, base: 1, disagreement: { raw: 0.2, sdLnW: 0.1, sdLnD: 0.3, nResolvedKernels: 3 },
    intervalWidth: { lnHiOverLo: null, note: 'none' },
    coverage: { regimeClass: 'conduction', nearestDistanceStd: 1, classUnderCovered: false, value: 0.5 },
  },
  layout: { printOrder: n, x_start_mm: 3, x_end_mm: 13, y_mm: 3 * n },
});
const FIT = 'python -B python/tools/lpbf_machine_calibration.py fit --user-source .runtime/user-calibration/user-<your-id>/rows.json --out-dir .runtime/machine-calibration/user-<your-id>';
const plan = (machine: boolean) => checkedExperimentPlan({
  schema: 'lpbf-next-experiment-plan-1', label: LPBF_EXPERIMENT_PLAN_LABEL, evidenceKind: 'screening-only', material: MATERIAL, configSha256: SHA,
  calibration: { available: false, reason: 'synthetic' }, intervalWidth: { lnHiOverLo: null, note: 'none' },
  plate: { x_mm: 100, y_mm: 60, pitch_mm: 3, trackLength_mm: 10, edgeMargin_mm: 3 },
  points: [planPoint(1), planPoint(2)],
  commands: ['python -B python/tools/lpbf_next_experiment.py import --plan <plan-dir>/plan.json', ...(machine ? [FIT] : [])],
  limits: 'a proposal',
  ...(machine ? { purpose: 'machine-calibration', warnings: ['regime coverage is below the soft target'], methodColumns: ['depthDatum', 'beamDiameterDefinition', 'measuredPowerW', 'crossSectionLocation', 'replicates'] } : {}),
});

test('plan view gains the fit command, warnings and method columns only for purpose machine-calibration', () => {
  const plain = renderToStaticMarkup(<ExperimentPlanView plan={plan(false)} />);
  assert.doesNotMatch(plain, /plan-fit-command|plan-machine-calibration/);
  assert.doesNotMatch(plain, /lpbf_machine_calibration/);
  const machine = renderToStaticMarkup(<ExperimentPlanView plan={plan(true)} />);
  assert.match(machine, /data-testid="plan-fit-command"[^>]*>python -B python\/tools\/lpbf_machine_calibration\.py fit/);
  assert.match(machine, /regime coverage is below the soft target/);
  assert.match(machine, /depthDatum, beamDiameterDefinition/);
  assert.match(machine, /not validation/);
  const header = (csv: string) => csv.split('\n')[0];
  assert.equal(header(measurementTemplateCsv(plan(false))), 'track_id,power_W,speed_mm_s,spot_um,width_um,depth_um,notes');
  assert.equal(header(measurementTemplateCsv(plan(true))), 'track_id,power_W,speed_mm_s,spot_um,width_um,depth_um,notes,depthDatum,beamDiameterDefinition,measuredPowerW,crossSectionLocation,replicates');
  assert.throws(() => checkedExperimentPlan({ ...JSON.parse(JSON.stringify(plan(true))), purpose: 'other' }), /purpose/);
});

test('Python-shaped missingMethodFields survive parsing and the panel lists them', () => {
  const raw = { screening: {}, machineCalibrated: { ...servedBlock(), evidenceKind: 'screening-only', evidenceScope: null,
    missingMethodFields: [{ trackIds: ['t2'], fields: ['replicates', 'depthDatum'] }, { trackIds: ['t1', 't3'], fields: ['depthDatum', 'measuredPowerW'] }] } };
  const parsed = parseMachineCalibratedResult(raw);
  assert.deepEqual(parsed?.machineCalibrated.missingMethodFields, ['depthDatum', 'measuredPowerW', 'replicates']);
  const out = renderToStaticMarkup(<MachineResultView artefact={artefact()} kernel="rosenthal" block={parsed!.machineCalibrated} screeningDepth={120} />);
  assert.ok(out.includes(MACHINE_BADGE_SCREENING));
  assert.match(out, /data-testid="machine-missing-fields"[^>]*>[^<]*depth datum[^<]*replicates/);
});
