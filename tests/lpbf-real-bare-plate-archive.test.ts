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
// The Python producer (python/lpbf_simulation.py) emits null for exactly three keys on every
// bare-plate run (bare = surfaceMode == "bare-plate"): analyticalComparison (line 889),
// fieldOverlapDiagnostics (lines 529/778) and geometricDefectScreen (line 1084). The consumer
// accepts those nulls only when settings.surfaceMode is exactly "bare-plate".
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { copyFileSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';
import { parseSimulationJob } from '../src/services/lpbfSimulationService';
import { LpbfRunRepository, validateRunDocument, type RunCapture } from '../server/lpbfRunRepository';
import { dryRunRunImport, importRun } from '../server/lpbfRunImport';
import { LpbfArtifactStore } from '../server/lpbfArtifactStore';
import { LpbfSourceRepository } from '../server/lpbfSourceRepository';

const fixtures = path.join(path.dirname(fileURLToPath(import.meta.url)), 'fixtures');
const NPZ = 'rectangular-corridor-section-fields.npz';
const BARE_PLATE_NULLS = {
  analyticalComparison: /Invalid LPBF result contract/,
  fieldOverlapDiagnostics: /Invalid field overlap diagnostics/,
  geometricDefectScreen: /Invalid geometric defect screening/,
} as const;
const realCapture = (): RunCapture => JSON.parse(readFileSync(path.join(fixtures, 'lpbf-real-bare-plate-100W-capture.json'), 'utf8'));
const realResult = () => JSON.parse(realCapture().resultJson);
const completed = (result: unknown) => ({ id: realCapture().jobId, status: 'completed', progress: 1, log: '', error: null, result });

test('fixture is the real producer output for a bare-plate run', () => {
  const capture = realCapture(), result = JSON.parse(capture.resultJson);
  assert.equal(capture.jobId, '7ec9dc57c4c14a40b98a0cbfd722d21d');
  assert.equal(capture.contractStatus, 'core-v1-bound');
  assert.equal(capture.runKind, 'transient-thermal');
  assert.equal(result.settings.surfaceMode, 'bare-plate');
  assert.equal(result.settings.barePlateGeometry, 'rectangular-corridor');
  for (const key of Object.keys(BARE_PLATE_NULLS)) assert.equal(result[key], null, key);
  const digest = (text: string) => createHash('sha256').update(text).digest('hex');
  assert.equal(digest(capture.inputJson), result.coreContract.inputSha256);
  assert.equal(digest(capture.materialJson), result.coreContract.materialSha256);
});

test('the unmodified real bare-plate result parses', () => {
  const parsed = parseSimulationJob(completed(realResult()));
  assert.equal(parsed.status, 'completed');
  assert.equal(parsed.result?.analyticalComparison, null);
  assert.equal(parsed.result?.fieldOverlapDiagnostics, null);
  assert.equal(parsed.result?.geometricDefectScreen, null);
});

for (const [key, error] of Object.entries(BARE_PLATE_NULLS)) {
  test(`${key}: null is rejected unless settings.surfaceMode is exactly bare-plate`, () => {
    for (const surfaceMode of ['powder-layer', 'Bare-Plate', 'bare-plate ', '', null, undefined]) {
      const result = realResult();
      // Give the other bare-plate-null fields valid non-null shapes so only `key` is tested.
      if (key !== 'analyticalComparison') result.analyticalComparison = { goldak: { width_um: 1, depth_um: 1, length_um: 1 } };
      if (key !== 'fieldOverlapDiagnostics') delete result.fieldOverlapDiagnostics;
      if (key !== 'geometricDefectScreen') delete result.geometricDefectScreen;
      if (surfaceMode === undefined) delete result.settings.surfaceMode; else result.settings.surfaceMode = surfaceMode;
      assert.throws(() => parseSimulationJob(completed(result)), error, `${key} ${String(surfaceMode)}`);
    }
  });
}

test('malformed analytical comparisons are still rejected for bare-plate results (missing key included)', () => {
  const valid = { width_um: 1, depth_um: 1, length_um: 1 };
  for (const analyticalComparison of [undefined, 'null', 0, false, [], [valid], { goldak: null },
    { goldak: { ...valid, width_um: -1 } }, { goldak: { ...valid, depth_um: 'x' } }, { goldak: { width_um: 1, depth_um: 1 } }]) {
    const result = realResult();
    if (analyticalComparison === undefined) delete result.analyticalComparison;
    else result.analyticalComparison = analyticalComparison;
    assert.throws(() => parseSimulationJob(completed(result)), /Invalid LPBF result contract/, JSON.stringify(analyticalComparison));
  }
  const withMap = realResult(); withMap.analyticalComparison = { goldak: valid };
  assert.equal(parseSimulationJob(completed(withMap)).status, 'completed');
});

test('malformed field overlap diagnostics are still rejected for bare-plate results', () => {
  for (const fieldOverlapDiagnostics of ['null', 0, false, [], {}, { modelId: 'field-inter-track-overlap-v1' }]) {
    const result = realResult(); result.fieldOverlapDiagnostics = fieldOverlapDiagnostics;
    assert.throws(() => parseSimulationJob(completed(result)), /Invalid field overlap diagnostics/, JSON.stringify(fieldOverlapDiagnostics));
  }
});

test('malformed geometric defect screens are still rejected for bare-plate results', () => {
  for (const geometricDefectScreen of ['null', 0, false, [], {}, { modelId: 'elliptic-overlap-screening-v1' }]) {
    const result = realResult(); result.geometricDefectScreen = geometricDefectScreen;
    assert.throws(() => parseSimulationJob(completed(result)), /Invalid geometric defect screening/, JSON.stringify(geometricDefectScreen));
  }
});

test('the unmodified real capture passes archive document validation', () => {
  const capture = realCapture();
  const document = validateRunDocument({ schemaVersion: 1, runId: capture.jobId, capture, sources: [] });
  assert.equal(document.capture.resultJson, realCapture().resultJson);
});

test('the real bare-plate capture archives through the repository import path', async t => {
  const root = mkdtempSync(path.join(tmpdir(), 'lpbf-real-bare-plate-'));
  const repository = new LpbfRunRepository(path.join(root, 'runs.sqlite'));
  const sources = new LpbfSourceRepository(path.join(root, 'sources.sqlite'));
  const store = new LpbfArtifactStore(path.join(root, 'store'));
  t.after(() => { repository.close(); sources.close(); rmSync(root, { recursive: true, force: true }); });
  // Manifest reduction only: the real manifest lists ~6 MB of field frames, SVGs and peak
  // fields that are not checked in, so the artifact list keeps just the real section-field
  // NPZ entry (real path, size and SHA-256). Every other result key and value, including the
  // three bare-plate nulls, and the bound inputJson/materialJson bytes are the real ones.
  const capture = realCapture(), result = JSON.parse(capture.resultJson);
  result.artifacts = result.artifacts.filter((artifact: { path: string }) => artifact.path === NPZ);
  assert.equal(result.artifacts.length, 1);
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
  const stored = JSON.parse(repository.get(capture.jobId)!.document.capture.resultJson);
  for (const key of Object.keys(BARE_PLATE_NULLS)) assert.equal(stored[key], null, key);
});
