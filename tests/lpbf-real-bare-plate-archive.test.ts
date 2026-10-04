// Producer-shaped regression tests for completed bare-plate results.
//
// Fixture provenance (no hand-built result fields):
// - fixtures/lpbf-real-bare-plate-100W-capture.json is the unmodified return value of
//   python/lpbf_run_capture.py capture_run() on the real completed job
//   7ec9dc57c4c14a40b98a0cbfd722d21d (Inconel 718, 100 W, 960 mm/s, standard mode,
//   surfaceMode bare-plate, barePlateGeometry rectangular-corridor; NOT NIST case 0).
//   Its resultJson is byte-identical to that job's result.json, and its inputJson and
//   materialJson are the Python-serialized bytes bound by coreContract.
// - fixtures/lpbf-real-bare-plate-100W-section-fields.npz is that job's real
//   rectangular-corridor-section-fields.npz artifact (4998 bytes).
//
// The Python producer (python/lpbf_simulation.py) emits null for three keys on every
// bare-plate run: analyticalComparison (line 880), fieldOverlapDiagnostics (lines 524/769)
// and geometricDefectScreen (line 1091). This change only accepts the analyticalComparison
// null. The other two are still rejected by parseSimulationJob ("Invalid field overlap
// diagnostics", "Invalid geometric defect screening"); they are a separate, unfixed
// producer/consumer mismatch, so the unmodified real run is recorded as a todo below and the
// passing archive test removes exactly those two keys (BARE_PLATE_UNFIXED_NULLS).
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { copyFileSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { test, type TestContext } from 'node:test';
import { parseSimulationJob } from '../src/services/lpbfSimulationService';
import { LpbfRunRepository, validateRunDocument, type RunCapture } from '../server/lpbfRunRepository';
import { dryRunRunImport, importRun } from '../server/lpbfRunImport';
import { LpbfArtifactStore } from '../server/lpbfArtifactStore';
import { LpbfSourceRepository } from '../server/lpbfSourceRepository';

const fixtures = path.join(path.dirname(fileURLToPath(import.meta.url)), 'fixtures');
const NPZ = 'rectangular-corridor-section-fields.npz';
const BARE_PLATE_UNFIXED_NULLS = ['fieldOverlapDiagnostics', 'geometricDefectScreen'];
const realCapture = (): RunCapture => JSON.parse(readFileSync(path.join(fixtures, 'lpbf-real-bare-plate-100W-capture.json'), 'utf8'));
const realResult = () => JSON.parse(realCapture().resultJson);
/** Real result minus only the two separately tracked bare-plate nulls. */
function realResultWithoutUnfixedNulls() {
  const result = realResult();
  for (const key of BARE_PLATE_UNFIXED_NULLS) { assert.equal(result[key], null); delete result[key]; }
  return result;
}
const completed = (result: unknown) => ({ id: realCapture().jobId, status: 'completed', progress: 1, log: '', error: null, result });
const notResultContract = (error: unknown) => error instanceof Error && !/Invalid LPBF result contract/.test(error.message);

test('fixture is the real producer output for a bare-plate run with a null analytical comparison', () => {
  const capture = realCapture(), result = JSON.parse(capture.resultJson);
  assert.equal(capture.jobId, '7ec9dc57c4c14a40b98a0cbfd722d21d');
  assert.equal(capture.contractStatus, 'core-v1-bound');
  assert.equal(capture.runKind, 'transient-thermal');
  assert.equal(result.settings.surfaceMode, 'bare-plate');
  assert.equal(result.settings.barePlateGeometry, 'rectangular-corridor');
  assert.equal(result.analyticalComparison, null);
  const digest = (text: string) => createHash('sha256').update(text).digest('hex');
  assert.equal(digest(capture.inputJson), result.coreContract.inputSha256);
  assert.equal(digest(capture.materialJson), result.coreContract.materialSha256);
});

test('the real bare-plate null analytical comparison passes the result contract check', () => {
  // Unmodified real result: the result contract check passes; parsing then stops at the
  // separately tracked fieldOverlapDiagnostics null.
  assert.throws(() => parseSimulationJob(completed(realResult())), notResultContract);
  const parsed = parseSimulationJob(completed(realResultWithoutUnfixedNulls()));
  assert.equal(parsed.status, 'completed');
  assert.equal(parsed.result?.analyticalComparison, null);
  assert.equal((parsed.result?.settings as unknown as Record<string, unknown> | undefined)?.surfaceMode, 'bare-plate');
});

test('a null analytical comparison is still rejected unless settings.surfaceMode is exactly bare-plate', () => {
  for (const surfaceMode of ['powder-layer', 'Bare-Plate', 'bare-plate ', '', null, undefined]) {
    const result = realResultWithoutUnfixedNulls();
    if (surfaceMode === undefined) delete result.settings.surfaceMode; else result.settings.surfaceMode = surfaceMode;
    assert.throws(() => parseSimulationJob(completed(result)), /Invalid LPBF result contract/, String(surfaceMode));
  }
  const noSettings = realResultWithoutUnfixedNulls(); delete noSettings.settings;
  assert.throws(() => parseSimulationJob(completed(noSettings)), /Invalid LPBF result contract/);
});

test('malformed analytical comparisons are still rejected for bare-plate results', () => {
  const valid = { width_um: 1, depth_um: 1, length_um: 1 };
  for (const analyticalComparison of [undefined, 'null', 0, false, [], [valid], { goldak: null },
    { goldak: { ...valid, width_um: -1 } }, { goldak: { ...valid, depth_um: 'x' } }, { goldak: { width_um: 1, depth_um: 1 } }]) {
    const result = realResultWithoutUnfixedNulls();
    if (analyticalComparison === undefined) delete result.analyticalComparison;
    else result.analyticalComparison = analyticalComparison;
    assert.throws(() => parseSimulationJob(completed(result)), /Invalid LPBF result contract/, JSON.stringify(analyticalComparison));
  }
  const withMap = realResultWithoutUnfixedNulls(); withMap.analyticalComparison = { goldak: valid };
  assert.equal(parseSimulationJob(completed(withMap)).status, 'completed');
});

async function importBarePlate(t: TestContext, mutate: (result: Record<string, unknown>) => void) {
  const root = mkdtempSync(path.join(tmpdir(), 'lpbf-real-bare-plate-'));
  const repository = new LpbfRunRepository(path.join(root, 'runs.sqlite'));
  const sources = new LpbfSourceRepository(path.join(root, 'sources.sqlite'));
  const store = new LpbfArtifactStore(path.join(root, 'store'));
  t.after(() => { repository.close(); sources.close(); rmSync(root, { recursive: true, force: true }); });
  // Manifest reduction: the real manifest lists ~6 MB of field frames, SVGs and peak fields
  // that are not checked in, so it keeps just the real section-field NPZ entry (real path,
  // size and SHA-256). The bound inputJson/materialJson bytes are the real captured bytes.
  const capture = realCapture(), result = JSON.parse(capture.resultJson);
  result.artifacts = result.artifacts.filter((artifact: { path: string }) => artifact.path === NPZ);
  assert.equal(result.artifacts.length, 1);
  mutate(result);
  capture.resultJson = JSON.stringify(result);
  const job = path.join(root, 'job'); mkdirSync(job);
  copyFileSync(path.join(fixtures, 'lpbf-real-bare-plate-100W-section-fields.npz'), path.join(job, NPZ));
  writeFileSync(path.join(job, 'result.json'), capture.resultJson);

  const preview = await dryRunRunImport(capture, [], sources, job);
  assert.equal(preview.artifactCount, 1);
  assert.equal(repository.get(capture.jobId), null);
  const saved = await importRun(repository, store, capture, [], sources, job);
  assert.equal(saved.runKind, 'transient-thermal');
  assert.equal(saved.document.capture.contractStatus, 'core-v1-bound');
  assert.equal(JSON.parse(repository.get(capture.jobId)!.document.capture.resultJson).analyticalComparison, null);
}

test('a run built from the real bare-plate capture imports through the repository import path', async t => {
  await importBarePlate(t, result => { for (const key of BARE_PLATE_UNFIXED_NULLS) delete result[key]; });
});

test('the unmodified real bare-plate capture archives', {
  todo: 'blocked by the separate fieldOverlapDiagnostics/geometricDefectScreen bare-plate null mismatch',
}, async t => {
  const capture = realCapture();
  validateRunDocument({ schemaVersion: 1, runId: capture.jobId, capture, sources: [] });
  await importBarePlate(t, () => {});
});
