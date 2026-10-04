/** Canonical mapping from captured thermal-run evidence to campaign identity. */
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { LpbfArtifactStore } from './lpbfArtifactStore';
import type { RunRecord } from './lpbfRunRepository';
import { getHostPython } from './pythonRuntime';

const SECTION_IDS = ['x-4p9mm', 'x-6p0mm'];
const SECTION_RECORD_IDS = ['single-line-x-4p9mm', 'single-line-x-6p0mm'];
const SECTION_DISTANCES = [4.9, 6.0];
const SECTION_OPERATOR = 'bare-plate-corridor-accepted-peak-x-linear-section-v1';
const CONTOUR_OPERATOR = 'linear-liquidus-crossings-between-cell-centers-v1';
const SECTION_FIELD_PATH = 'rectangular-corridor-section-fields.npz';
const SECTION_FIELD_BINDING = 'accepted-step-maximum-per-source-X-plane';
const MAX_SECTION_FIELD_BYTES = 32 * 1024 * 1024;
const PYTHON_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../python');
const sha = (value: string | Buffer) => createHash('sha256').update(value).digest('hex');

export function rederiveProxyCampaignSections(result: unknown, bytes: Buffer): Promise<any> {
  return new Promise((resolve, reject) => {
    let python;
    try { python = getHostPython(); }
    catch { reject(new Error('Host Python is unavailable for NPZ re-derivation.')); return; }
    const code = [
      'import json,sys',
      `sys.path.insert(0,${JSON.stringify(PYTHON_ROOT)})`,
      'try:',
      ' from lpbf_nist_proxy_sections import rederive_rectangular_corridor_sections',
      ' from lpbf_nist_proxy_sections import SectionArtifactError',
      ' header=json.loads(sys.stdin.buffer.readline())',
      ' payload=sys.stdin.buffer.read()',
      ' answer=rederive_rectangular_corridor_sections(payload,header["result"])',
      ' print(json.dumps(answer,allow_nan=False))',
      'except SectionArtifactError as exc:',
      ' print(json.dumps({"status":"unavailable","reason":str(exc)}))',
    ].join('\n');
    const child = spawn(python.cmd, [...python.prefix, '-c', code], { cwd: path.resolve(), windowsHide: true, shell: false, stdio: 'pipe' });
    let stdout = '', stderr = '', done = false;
    const fail = (error: Error) => { if (!done) { done = true; clearTimeout(timer); reject(error); } };
    const timer = setTimeout(() => { child.kill(); fail(new Error('Python NPZ re-derivation timed out.')); }, 15000);
    child.stdout.on('data', chunk => { stdout += chunk.toString(); if (stdout.length > 256 * 1024) { child.kill(); fail(new Error('Python NPZ re-derivation response is too large.')); } });
    child.stderr.on('data', chunk => { stderr = (stderr + chunk.toString()).slice(-2048); });
    child.on('error', () => fail(new Error('Python NPZ re-derivation reader is unavailable.')));
    child.on('close', code => {
      if (done) return;
      if (code !== 0) { fail(new Error(stderr.includes('No module named') ? 'Python NPZ re-derivation reader or dependency is unavailable.' : 'Python NPZ re-derivation failed.')); return; }
      try { const answer = JSON.parse(stdout); done = true; clearTimeout(timer); resolve(answer); }
      catch { fail(new Error('Python NPZ re-derivation returned an invalid response.')); }
    });
    child.stdin.on('error', () => fail(new Error('Could not send verified NPZ bytes to Python.')));
    child.stdin.write(`${JSON.stringify({ result })}\n`);
    child.stdin.end(bytes);
  });
}

export async function validateArchivedProxySections(result: any, store: LpbfArtifactStore,
  reader: (result: unknown, bytes: Buffer) => Promise<any> = rederiveProxyCampaignSections): Promise<string | null> {
  const descriptor = result?.barePlateSectionFieldArtifact;
  if (descriptor?.schemaVersion !== 1 || descriptor?.status !== 'captured'
    || descriptor?.path !== SECTION_FIELD_PATH || descriptor?.binding !== SECTION_FIELD_BINDING) {
    return 'Archived run lacks the exact captured section-field artifact descriptor.';
  }
  if (!Array.isArray(result?.artifacts)) return 'Archived run artifact manifest is missing.';
  const matches = result.artifacts.filter((item: any) => item?.path === SECTION_FIELD_PATH);
  if (matches.length !== 1) return 'Archived run manifest must contain exactly one section-field artifact entry.';
  const artifact = matches[0];
  if (typeof artifact.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(artifact.sha256)
    || !Number.isSafeInteger(artifact.size_bytes) || artifact.size_bytes <= 0
    || artifact.size_bytes > MAX_SECTION_FIELD_BYTES) {
    return 'Archived section-field artifact manifest has an invalid identity or exceeds the compressed-byte budget.';
  }
  try {
    const verified = await store.verify({ sha256: artifact.sha256, byteSize: artifact.size_bytes });
    const bytes = readFileSync(verified.path);
    if (bytes.length !== artifact.size_bytes || sha(bytes) !== artifact.sha256) {
      return 'Archived section-field artifact bytes changed or failed SHA-256 verification after store verification.';
    }
    const answer = await reader(result, bytes);
    if (answer?.status !== 'validated') {
      return typeof answer?.reason === 'string' ? answer.reason : 'Archived section-field artifact could not re-derive both thermal-proxy sections.';
    }
    return null;
  } catch (error) {
    return error instanceof Error && error.message ? `Archived section-field artifact verification failed: ${error.message}`
      : 'Archived section-field artifact verification failed with a non-Error exception.';
  }
}

export function deriveProxyCampaignRunBinding(record: RunRecord, sourceBinding: unknown): {
  runIdentity: Record<string, any>; observations: any[];
} | null {
  const capture = record?.document?.capture;
  if (!capture || capture.contractStatus !== 'core-v1-bound' || record.runKind !== 'transient-thermal') return null;
  let result: any;
  try { result = JSON.parse(capture.resultJson); } catch { return null; }
  const core = result?.coreContract, material = result?.material;
  const settings = result?.settings || {};
  if (!core || !material || !settings || typeof settings !== 'object' || Array.isArray(settings)
    || !core.inputSha256 || !core.materialSha256 || !material.materialRevisionSha256
    || core.modelId !== 'stationary-enthalpy-conduction-v1'
    || core.actualBackend !== 'numpy-reference' || result.effectiveMode !== 'standard'
    || material.materialId !== 'in718' || settings.surfaceMode !== 'bare-plate' || settings.tracks !== 1
    || settings.layers !== 1 || settings.trackLength_um !== 10000 || settings.scanAngle_deg !== 0
    || !Number.isFinite(settings.beamDiameter_um) || !Array.isArray(result.scanPath)
    || !Array.isArray(result.barePlateSectionObservations)) return null;
  const derived = runCampaignIdentity(record, result, result.barePlateSectionObservations, sourceBinding);
  return derived;
}

function runCampaignIdentity(record: RunRecord, result: any, observations: any[], sourceBinding: any) {
  const core = result.coreContract, material = result.material;
  if (!core || !material || !Array.isArray(observations) || observations.length !== 2) return null;
  const scanStartX = result.scanPath?.[0]?.start?.[0];
  if (!Number.isFinite(scanStartX)) return null;
  const captureBytes = Buffer.from(record.document.capture.resultJson, 'utf8');
  const runIdentity = {
    runId: record.document.runId,
    runDocumentSha256: record.documentSha256,
    resultArtifact: { path: 'capture/result.json', sha256: sha(captureBytes), size_bytes: captureBytes.length },
    inputSha256: core.inputSha256,
    materialSha256: core.materialSha256,
    materialId: material.materialId,
    materialRevisionSha256: material.materialRevisionSha256,
    executedSettings: JSON.parse(JSON.stringify(result.settings)),
    coreContract: { schemaVersion: core.schemaVersion, modelId: core.modelId,
      solverId: core.solverId, actualBackend: core.actualBackend },
  };
  const converted = [];
  for (let index = 0; index < SECTION_IDS.length; index++) {
    const sample = observations.find(item => item?.recordId === SECTION_RECORD_IDS[index]);
    if (!sample || sample.status !== 'thermal-proxy' || !Number.isFinite(sample.width_um)
      || !Number.isFinite(sample.depth_um) || sample.width_um <= 0 || sample.depth_um <= 0) return null;
    const interp = sample.interpolationOperator;
    const expectedX = scanStartX + SECTION_DISTANCES[index] * 1e-3;
    const close = (left: unknown, right: number, tolerance = 1e-12) =>
      typeof left === 'number' && Number.isFinite(left) && Math.abs(left - right) <= tolerance;
    if (sample.operator !== SECTION_OPERATOR
      || sample.scanLineScope !== 'one simulated +X track; not experimental repeats'
      || !close(sample.distanceFromScanStart_mm, SECTION_DISTANCES[index], 1e-9)
      || !close(sample.scanStartX_m, scanStartX)
      || !close(sample.xCoordinate_m, expectedX)
      || sample.temporalAggregation !== 'accepted-step maximum per source X plane, then spatially interpolated'
      || sample.contourOperator !== CONTOUR_OPERATOR
      || !Number.isSafeInteger(sample.sampleCells) || sample.sampleCells < 1
      || sample.evidenceScope !== 'Numerical thermal proxy; no etched-boundary or experimental validation; one simulated line only'
      || !Array.isArray(sample.sourcePlaneIndices) || !Array.isArray(sample.sourcePlaneX_m)
      || !Array.isArray(sample.sourcePlaneX_um)
      || sample.sourcePlaneIndices.some((value: unknown) => !Number.isSafeInteger(value) || Number(value) < 0)
      || sample.sourcePlaneX_m.some((value: unknown) => typeof value !== 'number' || !Number.isFinite(value))
      || sample.sourcePlaneX_um.some((value: unknown) => typeof value !== 'number' || !Number.isFinite(value))) return null;
    if (interp === 'exact-cell-center') {
      if (sample.sourcePlaneIndices.length !== 1 || sample.sourcePlaneX_m.length !== 1
        || sample.sourcePlaneX_um.length !== 1 || sample.interpolationFraction !== 0
        || !close(sample.sourcePlaneX_m[0], expectedX)
        || !close(sample.sourcePlaneX_um[0], expectedX * 1e6, 1e-6)) return null;
    } else if (interp === 'linear-interpolation-between-accepted-peak-temperature-planes-v1') {
      if (sample.sourcePlaneIndices.length !== 2 || sample.sourcePlaneX_m.length !== 2
        || sample.sourcePlaneX_um.length !== 2
        || sample.sourcePlaneIndices[1] !== sample.sourcePlaneIndices[0] + 1
        || sample.sourcePlaneX_m[0] > expectedX || sample.sourcePlaneX_m[1] < expectedX
        || sample.sourcePlaneX_m[0] >= sample.sourcePlaneX_m[1]
        || typeof sample.interpolationFraction !== 'number' || !Number.isFinite(sample.interpolationFraction)
        || sample.interpolationFraction < 0 || sample.interpolationFraction > 1
        || !close(sample.sourcePlaneX_m[0] + (sample.sourcePlaneX_m[1] - sample.sourcePlaneX_m[0])
          * sample.interpolationFraction, expectedX)
        || !close(sample.sourcePlaneX_um[0], sample.sourcePlaneX_m[0] * 1e6, 1e-6)
        || !close(sample.sourcePlaneX_um[1], sample.sourcePlaneX_m[1] * 1e6, 1e-6)) return null;
    } else return null;
    converted.push({ sectionId: SECTION_IDS[index], coordinateFrame: 'scan-start-relative', scanDirection: '+X',
      distanceFromScanStart_mm: sample.distanceFromScanStart_mm, surfaceZ_m: 0, status: 'thermal-proxy',
      geometry: { width_um: sample.width_um, depth_um: sample.depth_um },
      operator: { sectionOperatorId: SECTION_OPERATOR, interpolationOperatorId: interp,
        contourOperatorId: CONTOUR_OPERATOR, evidenceClass: 'thermal-proxy-only' },
      provenance: { sourceBinding, runIdentity } });
  }
  return { runIdentity, observations: converted };
}
