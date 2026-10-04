/** Immutable run snapshots. Integrity checks are not scientific validation. */
import { createHash } from 'node:crypto';
import { mkdirSync } from 'node:fs';
import path from 'node:path';
import { isDeepStrictEqual } from 'node:util';
import { DatabaseSync, backup } from 'node:sqlite';
import { parseIn625BareplateJob, parseSimulationJob } from '../src/services/lpbfSimulationService';
import { artifactRelativePath } from './lpbfArtifactStore';
import { canonicalBuildJobIdentity, canonicalBuildJobMaterialSnapshot } from '../src/utils/lpbfBuildJobIdentity';
import { strictJsonEqual } from './lpbfBoundJson';
import { validateGpuPilotArchiveMetadata } from './lpbfGpuRunArchive';
import { deriveProxyCampaignRunBinding } from './lpbfProxyCampaignBinding';

export interface RunCapture {
  schemaVersion: 1; jobId: string; resultJson: string; inputJson: string; materialJson: string;
  contractStatus: 'core-v1-bound' | 'legacy-unbound' | 'gpu-pilot-v1-bound' | 'gpu-pilot-v2-warp-bound';
  runKind?: RunKind;
}
export type RunKind = 'analytical-screening' | 'build-screening' | 'transient-thermal' | 'bounded-material-screening' | 'gpu-thermal-pilot' | 'legacy-unspecified';
export interface RunSourceLink { datasetId: string; revision: number; documentSha256: string }
export interface RunDocument { schemaVersion: 1; runId: string; capture: RunCapture; sources: RunSourceLink[] }
export interface RunRecord { document: RunDocument; documentSha256: string; createdAt: string; evidenceStatus: 'unvalidated-model'; runKind: RunKind }
export interface ProxyCampaignRecord { campaignId: string; document: Record<string, any>; documentSha256: string; createdAt: string }
const MAX_BYTES = 32 * 1024 * 1024;
const NIST_TABLE4_DATASET_ID = 'nist-amb2022-03-optical-table4-local-v1';
const NIST_TABLE4_ARTIFACT_PATH = 'table4-aggregate-v2.json';
const NIST_TABLE4_ARTIFACT_SHA256 = 'd1b36dfa2e01a3537093c481e249ce52df6b8879c1c67480ddb9aa10799133da';
const NIST_TABLE4_ARTIFACT_SIZE = 4321;
const digest = (text: string) => createHash('sha256').update(text).digest('hex');
const hash = (value: unknown) => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
function keys(value: any, fields: string[], optional: string[] = []) {
  if (!value || typeof value !== 'object' || Array.isArray(value)
    || Object.keys(value).length < fields.length || Object.keys(value).length > fields.length + optional.length
    || fields.some(key => !Object.hasOwn(value, key))
    || Object.keys(value).some(key => !fields.includes(key) && !optional.includes(key))) throw new Error('Invalid run fields');
}
function finite(value: unknown, depth = 0): void {
  if (depth > 48) throw new Error('Run JSON too deeply nested');
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return;
  if (typeof value === 'number' && Number.isFinite(value)) return;
  if (Array.isArray(value)) { value.forEach(v => finite(v, depth + 1)); return; }
  if (value && typeof value === 'object' && Object.getPrototypeOf(value) === Object.prototype) {
    Object.values(value).forEach(v => finite(v, depth + 1)); return;
  }
  throw new Error('Run requires finite JSON values');
}
function snapshot(value: unknown): any {
  if (typeof value !== 'string' || Buffer.byteLength(value) > MAX_BYTES / 2) throw new Error('Invalid run snapshot size');
  const parsed = JSON.parse(value); finite(parsed); return parsed;
}

export function validateRunDocument(raw: unknown): RunDocument {
  finite(raw);
  const json = JSON.stringify(raw);
  if (Buffer.byteLength(json) > MAX_BYTES) throw new Error('Run document too large');
  const d = JSON.parse(json);
  keys(d, ['schemaVersion', 'runId', 'capture', 'sources']);
  if (!d.capture || typeof d.capture !== 'object' || Array.isArray(d.capture)) throw new Error('Invalid run fields');
  const captureFields = Object.keys(d.capture);
  if (captureFields.length !== 6 && captureFields.length !== 7
    || ['schemaVersion', 'jobId', 'resultJson', 'inputJson', 'materialJson', 'contractStatus']
      .some(key => !Object.hasOwn(d.capture, key))
    || captureFields.some(key => !['schemaVersion', 'jobId', 'resultJson', 'inputJson', 'materialJson', 'contractStatus', 'runKind'].includes(key))) {
    throw new Error('Invalid run fields');
  }
  const c = d.capture;
  if (d.schemaVersion !== 1 || c.schemaVersion !== 1 || typeof d.runId !== 'string'
    || !/^[a-f0-9]{32}$/.test(d.runId) || d.runId !== c.jobId) throw new Error('Invalid run identity');
  const result = snapshot(c.resultJson);
  const capturedRunKind = result.runKind === undefined ? 'legacy-unspecified' : result.runKind;
  const gpuPilot = capturedRunKind === 'gpu-thermal-pilot';
  const settings = result.settings;
  const resolvedPhysics = result.resolvedPhysics ?? result.coreContract?.resolvedPhysics;
  const analyticalScreening = settings?.mode === 'screening' && resolvedPhysics?.transient === false;
  if (typeof capturedRunKind !== 'string'
    || !['analytical-screening', 'build-screening', 'transient-thermal', 'bounded-material-screening', 'gpu-thermal-pilot', 'legacy-unspecified'].includes(capturedRunKind)
    || (result.runKind === undefined) !== (c.runKind === undefined)
    || (c.runKind !== undefined && c.runKind !== capturedRunKind)
    || (capturedRunKind === 'build-screening' && result.settings?.jobType !== 'build-job')
    || (capturedRunKind === 'analytical-screening' && !analyticalScreening)
    || (capturedRunKind === 'transient-thermal'
      && (!['transient-thermal', undefined].includes(result.settings?.jobType) || analyticalScreening))
    || (capturedRunKind === 'bounded-material-screening'
      && (result.settings?.jobType !== 'in625-bareplate-field' || result.jobType !== 'in625-bareplate-field'))) {
    throw new Error('Invalid captured run classification');
  }
  if (gpuPilot) {
    validateGpuPilotArchiveMetadata(result, c.jobId);
    const serialized = (result.gpuRunContract as Record<string, any>).serializedInputs;
    const innerCapture = (result.gpuRunContract as Record<string, any>).capture;
    if (c.runKind !== 'gpu-thermal-pilot'
      || !['gpu-pilot-v1-bound', 'gpu-pilot-v2-warp-bound'].includes(c.contractStatus)
      || !innerCapture || c.contractStatus !== innerCapture.contractStatus
      || c.inputJson !== serialized.requestJson || c.materialJson !== serialized.materialJson
      || !strictJsonEqual(snapshot(c.inputJson), result.settings)
      || !strictJsonEqual(snapshot(c.materialJson), result.material)) {
      throw new Error('GPU run capture snapshot identity mismatch');
    }
  } else if (c.contractStatus === 'gpu-pilot-v1-bound' || c.contractStatus === 'gpu-pilot-v2-warp-bound') {
    throw new Error('GPU pilot contract status is only valid for a GPU pilot run');
  }
  // Older v1 build-job archives may predate the effective-property snapshot.
  // When any part of the newer binding is present, require and verify the full
  // binding so an archived snapshot cannot be edited independently of its hash.
  if (capturedRunKind === 'build-screening'
    && ['materialPropertySnapshot', 'materialPropertySha256', 'buildJobIdentity']
      .some(field => Object.hasOwn(result, field))) {
    const snapshotValue = result.materialPropertySnapshot;
    const identity = result.buildJobIdentity;
    if (!snapshotValue || typeof snapshotValue !== 'object' || Array.isArray(snapshotValue)
      || !hash(result.materialPropertySha256)
      || !identity || typeof identity !== 'object' || Array.isArray(identity)
      || identity.schemaVersion !== 1 || identity.alloyId !== result.alloyId
      || identity.modelId !== result.modelId || identity.solverRevision !== result.solverRevision
      || identity.materialPropertySchemaVersion !== result.materialPropertySchemaVersion
      || identity.materialPropertyRevision !== result.materialPropertyRevision
      || identity.materialPropertySha256 !== result.materialPropertySha256
      || snapshotValue.alloyId !== result.alloyId
      || snapshotValue.schemaVersion !== result.materialPropertySchemaVersion
      || digest(canonicalBuildJobMaterialSnapshot(snapshotValue)) !== result.materialPropertySha256
      || !hash(identity.sha256)
      || digest(canonicalBuildJobIdentity(identity)) !== identity.sha256) {
      throw new Error('Run build-job material snapshot hash binding mismatch');
    }
  }
  if (!gpuPilot && !result.verdict) { // Not a build-job
    const job = { id: c.jobId, status: 'completed', progress: 1, log: '', error: null, result };
    if (result.jobType === 'in625-bareplate-field') {
      // Reconstitute the worker queue envelope expected by the public job parser.
      // The archive capture stores the authenticated result/settings snapshots,
      // not the transient queue requestSummary wrapper.
      parseIn625BareplateJob({ ...job, requestSummary: result.settings });
    }
    else parseSimulationJob(job);
  }
  if (!gpuPilot && (!isDeepStrictEqual(snapshot(c.inputJson), result.settings)
    || !isDeepStrictEqual(snapshot(c.materialJson), result.material))) throw new Error('Run snapshot identity mismatch');
  const bound = Object.hasOwn(result, 'coreContract');
  if (!gpuPilot && c.contractStatus !== (bound ? 'core-v1-bound' : 'legacy-unbound')) throw new Error('Invalid run contract status');
  // Hash Python's exact serialized bytes, not a JavaScript serialization of its numbers.
  if (!gpuPilot && bound && (digest(c.inputJson) !== result.coreContract.inputSha256
    || digest(c.materialJson) !== result.coreContract.materialSha256)) throw new Error('Run core hash binding mismatch');
  if (!Array.isArray(result.artifacts) || result.artifacts.length > 10000) throw new Error('Missing full run artifact manifest');
  const names = new Set<string>();
  for (const ref of result.artifacts) {
    keys(ref, ['path', 'size_bytes', 'sha256']); artifactRelativePath(ref.path);
    if (names.has(ref.path.toLowerCase()) || ['result.json', 'result.tmp', 'progress.log'].includes(ref.path)
      || !hash(ref.sha256) || !Number.isSafeInteger(ref.size_bytes) || ref.size_bytes < 0) throw new Error('Invalid run artifact manifest');
    names.add(ref.path.toLowerCase());
  }
  if (!Array.isArray(d.sources) || d.sources.length > 100) throw new Error('Invalid run source links');
  const links = new Set<string>();
  for (const link of d.sources) {
    keys(link, ['datasetId', 'revision', 'documentSha256']);
    if (typeof link.datasetId !== 'string' || !/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$/.test(link.datasetId)
      || !Number.isSafeInteger(link.revision) || link.revision < 1 || !hash(link.documentSha256)
      || links.has(`${link.datasetId}:${link.revision}`)) throw new Error('Invalid or duplicate source link');
    links.add(`${link.datasetId}:${link.revision}`);
  }
  return d;
}

function decode(row: any): RunRecord {
  try {
    if (typeof row.document_json !== 'string' || Buffer.byteLength(row.document_json) > MAX_BYTES
      || digest(row.document_json) !== row.document_sha256 || typeof row.created_at !== 'string'
      || !Number.isFinite(Date.parse(row.created_at))) throw new Error('Invalid row');
    const document = validateRunDocument(JSON.parse(row.document_json));
    if (document.runId !== row.run_id) throw new Error('Identity mismatch');
    return { document, documentSha256: row.document_sha256, createdAt: row.created_at,
      evidenceStatus: 'unvalidated-model', runKind: document.capture.runKind ?? 'legacy-unspecified' };
  } catch { throw new Error('Run metadata integrity failed; existing records preserved'); }
}

function validateProxyCampaignDocument(raw: unknown): Record<string, any> {
  let document: any;
  try {
    const json = JSON.stringify(raw);
    if (!json || Buffer.byteLength(json) > MAX_BYTES) throw new Error('Campaign too large');
    document = JSON.parse(json);
  } catch { throw new Error('Invalid proxy campaign document'); }
  if (!document || typeof document !== 'object' || Array.isArray(document)
    || ![1, 2].includes(document.schemaVersion) || document.kind !== 'lpbf-nist-amb2022-03-proxy-campaign'
    || typeof document.campaignId !== 'string' || !/^[a-f0-9]{32}$/.test(document.campaignId)
    || !Array.isArray(document.tracks) || document.tracks.length !== 3) throw new Error('Invalid proxy campaign document');
  if (document.schemaVersion === 1 && Object.hasOwn(document, 'beamInputDeclaration')) {
    throw new Error('Invalid v1 proxy campaign: beamInputDeclaration is v2-only');
  }
  if (document.schemaVersion === 2) {
    try {
      keys(document, ['schemaVersion', 'kind', 'campaignId', 'benchmark', 'caseNumber', 'sourceBinding',
        'beamInputDeclaration', 'claimBoundary', 'samplingPlan', 'tracks']);
    } catch { throw new Error('Invalid v2 proxy campaign fields'); }
  }
  const ids = new Set<string>();
  for (const track of document.tracks) {
    const identity = track?.runIdentity;
    if (!identity || typeof identity.runId !== 'string' || !/^[a-f0-9]{32}$/.test(identity.runId)
      || typeof identity.runDocumentSha256 !== 'string' || !/^[a-f0-9]{64}$/.test(identity.runDocumentSha256)
      || ids.has(identity.runId)) throw new Error('Invalid or duplicate campaign run reference');
    ids.add(identity.runId);
  }
  if (document.schemaVersion === 2) {
    const declaration = document.beamInputDeclaration;
    try {
      keys(declaration, ['status', 'definition', 'value_um', 'mappingStatus', 'measuredProfileMatched', 'sourceBinding']);
      keys(document.sourceBinding, ['datasetId', 'revision', 'documentSha256', 'artifactPath', 'artifactSha256', 'artifactSizeBytes', 'caseNumber']);
    } catch { throw new Error('Invalid v2 proxy campaign source binding or beam input declaration fields'); }
    const sourceBinding = document.sourceBinding;
    if (declaration.status !== 'published-source-declared' || declaration.definition !== 'D4sigma'
      || typeof declaration.value_um !== 'number' || !Number.isFinite(declaration.value_um) || declaration.value_um <= 0
      || declaration.mappingStatus !== 'conditional-ideal-Gaussian' || declaration.measuredProfileMatched !== false
      || !isDeepStrictEqual(declaration.sourceBinding, document.sourceBinding)
      || document.benchmark !== 'AMB2022-03-TMPG' || document.caseNumber !== '0'
      || sourceBinding.caseNumber !== document.caseNumber
      || sourceBinding.datasetId !== NIST_TABLE4_DATASET_ID
      || sourceBinding.artifactPath !== NIST_TABLE4_ARTIFACT_PATH
      || sourceBinding.artifactSha256 !== NIST_TABLE4_ARTIFACT_SHA256
      || sourceBinding.artifactSizeBytes !== NIST_TABLE4_ARTIFACT_SIZE
      || declaration.value_um !== 67
      || !Number.isSafeInteger(sourceBinding.revision) || sourceBinding.revision < 1
      || !hash(sourceBinding.documentSha256) || !hash(sourceBinding.artifactSha256)
      || !Number.isSafeInteger(sourceBinding.artifactSizeBytes) || sourceBinding.artifactSizeBytes <= 0
      || Object.hasOwn(sourceBinding, 'experimentalTrackIds')) {
      throw new Error('Invalid v2 proxy campaign beam input declaration');
    }
    const expectedId = digest(JSON.stringify({ schemaVersion: 2, runIds: document.tracks.map((track: any) => track.runIdentity.runId),
      caseNumber: document.caseNumber, revision: document.sourceBinding.revision, doc: document.sourceBinding.documentSha256 })).slice(0, 32);
    if (document.campaignId !== expectedId) throw new Error('Invalid v2 proxy campaign identity');
    const schemaError = (message: string): never => { throw new Error(`Invalid v2 proxy campaign ${message}`); };
    try {
      keys(document.claimBoundary, ['resultKind', 'validationStatus', 'experimentalValidation', 'opticalOperatorMatched']);
    } catch { schemaError('claim boundary fields'); }
    if (document.claimBoundary.resultKind !== 'thermal-proxy-screening'
      || document.claimBoundary.validationStatus !== 'unvalidated'
      || document.claimBoundary.experimentalValidation !== false
      || document.claimBoundary.opticalOperatorMatched !== false) schemaError('claim boundary or evidence flags');
    try { keys(document.samplingPlan, ['coordinateFrame', 'scanDirection', 'sectionPositions_mm',
      'expectedTrackCount', 'expectedObservationCount', 'replicateSemantics']); }
    catch { schemaError('sampling plan fields'); }
    if (document.samplingPlan.coordinateFrame !== 'scan-start-relative' || document.samplingPlan.scanDirection !== '+X'
      || !Array.isArray(document.samplingPlan.sectionPositions_mm)
      || !isDeepStrictEqual(document.samplingPlan.sectionPositions_mm, [4.9, 6.0])
      || document.samplingPlan.expectedTrackCount !== 3 || document.samplingPlan.expectedObservationCount !== 6
      || document.samplingPlan.replicateSemantics !== 'reproducibility-evidence-not-independent-replicates') {
      schemaError('sampling plan values or reproducibility semantics');
    }
    for (const [trackIndex, track] of document.tracks.entries()) {
      try { keys(track, ['simulatedTrackId', 'experimentalTrackId', 'replicateKind', 'runIdentity', 'observations']); }
      catch { schemaError(`track ${trackIndex} fields`); }
      if (typeof track.simulatedTrackId !== 'string' || !track.simulatedTrackId.trim()
        || track.experimentalTrackId !== null || track.replicateKind !== 'reproducibility-execution') {
        schemaError(`track ${trackIndex} identity or reproducibility kind`);
      }
      const identity = track.runIdentity;
      try { keys(identity, ['runId', 'runDocumentSha256', 'resultArtifact', 'inputSha256', 'executedSettings', 'materialSha256',
        'materialId', 'materialRevisionSha256', 'coreContract']); }
      catch { schemaError(`track ${trackIndex} run identity fields`); }
      if (track.simulatedTrackId !== `sim-${identity.runId}`) schemaError(`track ${trackIndex} simulated track binding`);
      try { keys(identity.resultArtifact, ['path', 'sha256', 'size_bytes']); }
      catch { schemaError(`track ${trackIndex} result artifact fields`); }
      if (identity.resultArtifact.path !== 'capture/result.json' || !hash(identity.resultArtifact.sha256)
        || !Number.isSafeInteger(identity.resultArtifact.size_bytes) || identity.resultArtifact.size_bytes <= 0
        || !hash(identity.inputSha256) || !identity.executedSettings || typeof identity.executedSettings !== 'object'
        || Array.isArray(identity.executedSettings) || !Number.isFinite(identity.executedSettings.beamDiameter_um)
        || identity.executedSettings.beamDiameter_um <= 0 || !hash(identity.materialSha256)
        || typeof identity.materialId !== 'string' || !identity.materialId.trim()
        || !hash(identity.materialRevisionSha256)) schemaError(`track ${trackIndex} run identity values`);
      try { keys(identity.coreContract, ['schemaVersion', 'modelId', 'solverId', 'actualBackend']); }
      catch { schemaError(`track ${trackIndex} core contract fields`); }
      if (identity.coreContract.schemaVersion !== 1 || typeof identity.coreContract.modelId !== 'string'
        || !identity.coreContract.modelId.trim() || typeof identity.coreContract.solverId !== 'string'
        || !identity.coreContract.solverId.trim() || typeof identity.coreContract.actualBackend !== 'string'
        || !identity.coreContract.actualBackend.trim()) schemaError(`track ${trackIndex} core contract values`);
      if (!Array.isArray(track.observations) || track.observations.length !== 2) schemaError(`track ${trackIndex} observations missing or incomplete`);
      for (const [observationIndex, observation] of track.observations.entries()) {
        try { keys(observation, ['sectionId', 'coordinateFrame', 'scanDirection', 'distanceFromScanStart_mm', 'surfaceZ_m',
          'status', 'geometry', 'operator', 'provenance']); }
        catch { schemaError(`track ${trackIndex} observation ${observationIndex} fields`); }
        if (observation.sectionId !== ['x-4p9mm', 'x-6p0mm'][observationIndex]
          || observation.coordinateFrame !== 'scan-start-relative' || observation.scanDirection !== '+X'
          || observation.distanceFromScanStart_mm !== [4.9, 6.0][observationIndex]
          || observation.surfaceZ_m !== 0 || observation.status !== 'thermal-proxy') {
          schemaError(`track ${trackIndex} observation ${observationIndex} values`);
        }
        try { keys(observation.geometry, ['width_um', 'depth_um']); }
        catch { schemaError(`track ${trackIndex} observation ${observationIndex} geometry fields`); }
        if (typeof observation.geometry.width_um !== 'number' || !Number.isFinite(observation.geometry.width_um)
          || observation.geometry.width_um <= 0 || typeof observation.geometry.depth_um !== 'number'
          || !Number.isFinite(observation.geometry.depth_um) || observation.geometry.depth_um <= 0) {
          schemaError(`track ${trackIndex} observation ${observationIndex} geometry values`);
        }
        try { keys(observation.operator, ['sectionOperatorId', 'interpolationOperatorId', 'contourOperatorId', 'evidenceClass']); }
        catch { schemaError(`track ${trackIndex} observation ${observationIndex} operator fields`); }
        if (observation.operator.sectionOperatorId !== 'bare-plate-corridor-accepted-peak-x-linear-section-v1'
          || !['exact-cell-center', 'linear-interpolation-between-accepted-peak-temperature-planes-v1'].includes(observation.operator.interpolationOperatorId)
          || observation.operator.contourOperatorId !== 'linear-liquidus-crossings-between-cell-centers-v1'
          || observation.operator.evidenceClass !== 'thermal-proxy-only') schemaError(`track ${trackIndex} observation ${observationIndex} operator values`);
        try { keys(observation.provenance, ['sourceBinding', 'runIdentity']); }
        catch { schemaError(`track ${trackIndex} observation ${observationIndex} provenance fields`); }
        if (!isDeepStrictEqual(observation.provenance.sourceBinding, sourceBinding)
          || !isDeepStrictEqual(observation.provenance.runIdentity, identity)) schemaError(`track ${trackIndex} observation ${observationIndex} provenance binding`);
      }
    }
    if (document.samplingPlan.expectedTrackCount !== document.tracks.length
      || document.samplingPlan.expectedObservationCount !== document.tracks.reduce((total: number, track: any) => total + track.observations.length, 0)) {
      schemaError('sampling plan observation counts');
    }
  }
  return document;
}

function decodeProxyCampaign(row: any): ProxyCampaignRecord {
  try {
    if (typeof row.document_json !== 'string' || Buffer.byteLength(row.document_json) > MAX_BYTES
      || digest(row.document_json) !== row.document_sha256 || typeof row.created_at !== 'string'
      || !Number.isFinite(Date.parse(row.created_at))) throw new Error('Invalid row');
    const document = validateProxyCampaignDocument(JSON.parse(row.document_json));
    if (document.campaignId !== row.campaign_id) throw new Error('Identity mismatch');
    return { campaignId: row.campaign_id, document, documentSha256: row.document_sha256, createdAt: row.created_at };
  } catch { throw new Error('Proxy campaign metadata integrity failed; existing records preserved'); }
}

export class LpbfRunRepository {
  private readonly db: DatabaseSync;
  private closed = false;
  private backingUp = false;
  constructor(readonly filename: string, options: { readOnly?: boolean } = {}) {
    this.db = new DatabaseSync(filename, { readOnly: options.readOnly ?? false });
    try {
      const version = this.db.prepare('PRAGMA user_version').get()!.user_version;
      if (version === 0) {
        if (options.readOnly || this.db.prepare("SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").get()) throw new Error('Unrecognized run database');
        this.db.exec(`BEGIN IMMEDIATE;
          CREATE TABLE lpbf_runs (run_id TEXT PRIMARY KEY, document_json TEXT NOT NULL,
            document_sha256 TEXT NOT NULL, created_at TEXT NOT NULL) STRICT;
          CREATE TABLE lpbf_metadata (kind TEXT PRIMARY KEY) STRICT;
          INSERT INTO lpbf_metadata VALUES ('metalliksa-lpbf-runs-v1');
          CREATE TABLE lpbf_proxy_campaigns (campaign_id TEXT PRIMARY KEY, document_json TEXT NOT NULL,
            document_sha256 TEXT NOT NULL, created_at TEXT NOT NULL) STRICT;
          PRAGMA user_version=2; COMMIT;`);
      } else if (version === 1) {
        if (options.readOnly) {
          // A portable v1 archive remains readable without changing its bytes.
        } else this.db.exec(`BEGIN IMMEDIATE;
          CREATE TABLE lpbf_proxy_campaigns (campaign_id TEXT PRIMARY KEY, document_json TEXT NOT NULL,
            document_sha256 TEXT NOT NULL, created_at TEXT NOT NULL) STRICT;
          PRAGMA user_version=2; COMMIT;`);
      } else if (version !== 2) throw new Error('Unsupported run database version');
      if (this.db.prepare('SELECT kind FROM lpbf_metadata').get()?.kind !== 'metalliksa-lpbf-runs-v1') throw new Error('Invalid run database identity');
      if (options.readOnly) {
        if (this.db.prepare('PRAGMA integrity_check').get()!.integrity_check !== 'ok') throw new Error('Run database integrity failed');
      } else this.db.exec('PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; PRAGMA busy_timeout=250; PRAGMA max_page_count=262144;');
    } catch (error) { this.db.close(); throw error; }
  }
  close() {
    if (this.backingUp) throw new Error('Run backup in progress');
    if (!this.closed) { this.db.close(); this.closed = true; }
  }
  get(runId: string): RunRecord | null {
    if (!/^[a-f0-9]{32}$/.test(runId)) throw new Error('Invalid run id');
    const row = this.db.prepare('SELECT * FROM lpbf_runs WHERE run_id=?').get(runId);
    return row ? decode(row) : null;
  }
  *allRuns(): Generator<RunRecord> {
    for (const row of this.db.prepare('SELECT * FROM lpbf_runs ORDER BY run_id').iterate()) yield decode(row);
  }
  getProxyCampaign(campaignId: string): ProxyCampaignRecord | null {
    if (!/^[a-f0-9]{32}$/.test(campaignId)) throw new Error('Invalid campaign id');
    if (Number(this.db.prepare('PRAGMA user_version').get()!.user_version) < 2) return null;
    const row = this.db.prepare('SELECT * FROM lpbf_proxy_campaigns WHERE campaign_id=?').get(campaignId);
    return row ? decodeProxyCampaign(row) : null;
  }
  *allProxyCampaigns(): Generator<ProxyCampaignRecord> {
    if (Number(this.db.prepare('PRAGMA user_version').get()!.user_version) < 2) return;
    for (const row of this.db.prepare('SELECT * FROM lpbf_proxy_campaigns ORDER BY campaign_id').iterate()) yield decodeProxyCampaign(row);
  }
  saveProxyCampaign(raw: unknown): ProxyCampaignRecord {
    if (this.backingUp) throw new Error('Run backup in progress');
    const document = validateProxyCampaignDocument(raw), json = JSON.stringify(document);
    if (Number(this.db.prepare('PRAGMA user_version').get()!.user_version) < 2) throw new Error('Campaign storage requires writable v2 migration');
    this.db.exec('BEGIN IMMEDIATE');
    try {
      if (this.getProxyCampaign(document.campaignId)) throw new Error('Campaign identity conflict; immutable record already exists');
      for (const track of document.tracks) {
        const identity = track.runIdentity;
        const run = this.get(identity.runId);
        if (!run || run.documentSha256 !== identity.runDocumentSha256) throw new Error('Campaign archived run reference mismatch');
        if (document.schemaVersion === 2) {
          const derived = deriveProxyCampaignRunBinding(run, document.sourceBinding);
          if (!derived || !isDeepStrictEqual(identity, derived.runIdentity)
            || !isDeepStrictEqual(track.observations, derived.observations)) {
            throw new Error('Campaign archived run provenance or section binding mismatch');
          }
        }
      }
      const createdAt = new Date().toISOString(), documentSha256 = digest(json);
      this.db.prepare('INSERT INTO lpbf_proxy_campaigns VALUES (?, ?, ?, ?)').run(document.campaignId, json, documentSha256, createdAt);
      this.db.exec('COMMIT');
      return { campaignId: document.campaignId, document, documentSha256, createdAt };
    } catch (error) { this.db.exec('ROLLBACK'); throw error; }
  }
  /** Metadata-only boundary; importRun performs source and byte checks first. */
  save(raw: unknown): RunRecord {
    if (this.backingUp) throw new Error('Run backup in progress');
    const document = validateRunDocument(raw), json = JSON.stringify(document);
    this.db.exec('BEGIN IMMEDIATE');
    try {
      if (this.get(document.runId)) throw new Error('Run identity conflict; immutable record already exists');
      const createdAt = new Date().toISOString(), documentSha256 = digest(json);
      this.db.prepare('INSERT INTO lpbf_runs VALUES (?, ?, ?, ?)').run(document.runId, json, documentSha256, createdAt);
      this.db.exec('COMMIT'); return { document, documentSha256, createdAt,
        evidenceStatus: 'unvalidated-model', runKind: document.capture.runKind ?? 'legacy-unspecified' };
    } catch (error) { this.db.exec('ROLLBACK'); throw error; }
  }
  async backupMetadata(directory: string): Promise<{ path: string; artifactPayloadsIncluded: false }> {
    if (this.closed || this.backingUp) throw new Error('Run repository closed or backing up');
    mkdirSync(directory); this.backingUp = true;
    const filename = path.join(directory, 'runs.sqlite');
    try {
      await backup(this.db, filename);
      const copied = new DatabaseSync(filename);
      try { copied.exec('PRAGMA journal_mode=DELETE'); } finally { copied.close(); }
      const check = new LpbfRunRepository(filename, { readOnly: true });
      try { for (const record of check.allRuns()) void record; } finally { check.close(); }
      return { path: filename, artifactPayloadsIncluded: false };
    } finally { this.backingUp = false; }
  }
}
