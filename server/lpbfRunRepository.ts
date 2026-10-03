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
function keys(value: any, fields: string[]) {
  if (!value || typeof value !== 'object' || Array.isArray(value)
    || Object.keys(value).length !== fields.length || fields.some(key => !Object.hasOwn(value, key))) throw new Error('Invalid run fields');
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
    } catch { throw new Error('Invalid v2 proxy campaign beam input declaration'); }
    if (declaration.status !== 'published-source-declared' || declaration.definition !== 'D4sigma'
      || typeof declaration.value_um !== 'number' || !Number.isFinite(declaration.value_um) || declaration.value_um <= 0
      || declaration.mappingStatus !== 'conditional-ideal-Gaussian' || declaration.measuredProfileMatched !== false
      || !isDeepStrictEqual(declaration.sourceBinding, document.sourceBinding)
      || document.benchmark !== 'AMB2022-03-TMPG' || document.caseNumber !== '0'
      || document.sourceBinding.caseNumber !== document.caseNumber
      || document.sourceBinding.datasetId !== NIST_TABLE4_DATASET_ID
      || document.sourceBinding.artifactPath !== NIST_TABLE4_ARTIFACT_PATH
      || document.sourceBinding.artifactSha256 !== NIST_TABLE4_ARTIFACT_SHA256
      || document.sourceBinding.artifactSizeBytes !== NIST_TABLE4_ARTIFACT_SIZE
      || declaration.value_um !== 67
      || !Number.isSafeInteger(document.sourceBinding.revision) || document.sourceBinding.revision < 1
      || !hash(document.sourceBinding.documentSha256) || !hash(document.sourceBinding.artifactSha256)
      || !Number.isSafeInteger(document.sourceBinding.artifactSizeBytes) || document.sourceBinding.artifactSizeBytes <= 0) {
      throw new Error('Invalid v2 proxy campaign beam input declaration');
    }
    const expectedId = digest(JSON.stringify({ schemaVersion: 2, runIds: document.tracks.map((track: any) => track.runIdentity.runId),
      caseNumber: document.caseNumber, revision: document.sourceBinding.revision, doc: document.sourceBinding.documentSha256 })).slice(0, 32);
    if (document.campaignId !== expectedId) throw new Error('Invalid v2 proxy campaign identity');
    if (document.samplingPlan?.replicateSemantics !== 'reproducibility-evidence-not-independent-replicates'
      || document.tracks.some((track: any) => track.replicateKind !== 'reproducibility-execution')) {
      throw new Error('Invalid v2 proxy campaign reproducibility semantics');
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
