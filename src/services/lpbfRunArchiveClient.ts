import type { RunRecord, RunSourceLink, RunDocument, RunSourceBindingStatus, RunKind,
  NistOpticalCaseNumber, NistOpticalReport, NistProxyBeamInputDeclaration,
  NistProxyCampaignSourceBinding } from '../types/lpbfRun';
import { parseGpuPilotJob } from './lpbfSimulationService';
import { MELT_POOL_LITERATURE_CASES } from '../data/meltPoolLiteratureCases';

export interface RunPreview {
  document: RunDocument;
  artifactCount: number;
  byteSize: number;
  artifactIntegrity: 'verified-at-dry-run';
  sourceBindingStatus: 'exact-revision-bound';
  quota: {
    totalArchiveSizeBytes: number;
    maxArchiveSizeBytes: number;
    approachingLimit: boolean;
  };
}

export type RunArchiveList = { runId: string; createdAt: string; evidenceStatus: 'unvalidated-model'; sourceBindingStatus: RunSourceBindingStatus; runKind: RunKind }[];

export interface RunBundleManifest {
  schemaVersion: 1 | 2;
  kind: 'metalliksa-lpbf-run-bundle';
  metadata: { sha256: string; byteSize: number };
  sourceBundle: { sha256: string; byteSize: number };
  runCount: number;
  artifactCount: number;
  sourceLinkCount: number;
  campaignCount?: number;
}

export interface ExportedRunBundle {
  bundleId: string;
  storage: 'server-local-directory';
  manifest: RunBundleManifest;
  verified?: true;
  restoreId?: string;
}

export interface VerifiedRunBundle extends ExportedRunBundle { verified: true }
export interface RestoredRunBundle extends VerifiedRunBundle { restoreId: string }
export interface ImportedRunBundle extends VerifiedRunBundle { importId: string }

interface NistProxyCampaignShared {
  kind: 'lpbf-nist-amb2022-03-proxy-campaign';
  campaignId: string;
  benchmark: 'AMB2022-03-TMPG';
  caseNumber: NistOpticalCaseNumber;
  sourceBinding: NistProxyCampaignSourceBinding;
  claimBoundary: { resultKind: 'thermal-proxy-screening'; validationStatus: 'unvalidated'; experimentalValidation: false; opticalOperatorMatched: false };
}

interface NistProxySamplingPlan<ReplicateSemantics extends string> {
  coordinateFrame: 'scan-start-relative';
  scanDirection: '+X';
  sectionPositions_mm: [4.9, 6.0];
  expectedTrackCount: 3;
  expectedObservationCount: 6;
  replicateSemantics: ReplicateSemantics;
}

interface NistProxyTrack<ReplicateKind extends string, Identity extends NistProxyRunIdentity = NistProxyRunIdentity> {
    simulatedTrackId: string;
    experimentalTrackId: null;
    replicateKind: ReplicateKind;
    runIdentity: Identity;
    observations: { sectionId: 'x-4p9mm' | 'x-6p0mm'; coordinateFrame: 'scan-start-relative'; scanDirection: '+X';
      distanceFromScanStart_mm: 4.9 | 6.0; surfaceZ_m: 0; status: 'thermal-proxy';
      geometry: { width_um: number; depth_um: number };
      operator: { sectionOperatorId: string; interpolationOperatorId: string; contourOperatorId: string; evidenceClass: 'thermal-proxy-only' };
      provenance: { sourceBinding: NistProxyCampaign['sourceBinding']; runIdentity: Identity } }[];
}

export type NistProxyCampaign = NistProxyCampaignShared & (
  { schemaVersion: 1; beamInputDeclaration?: never;
    samplingPlan: NistProxySamplingPlan<'independent-computational-runs-only'>;
    tracks: NistProxyTrack<'independent-computational-run'>[] }
  | { schemaVersion: 2; beamInputDeclaration: NistProxyBeamInputDeclaration;
    samplingPlan: NistProxySamplingPlan<'reproducibility-evidence-not-independent-replicates'>;
    tracks: NistProxyTrack<'reproducibility-execution', NistProxyRunIdentityV2>[] }
);

export interface NistProxyRunIdentity {
  runId: string;
  runDocumentSha256: string;
  resultArtifact: { path: 'capture/result.json'; sha256: string; size_bytes: number };
  inputSha256: string;
  materialSha256: string;
  materialId: string;
  materialRevisionSha256: string;
  coreContract: { schemaVersion: number; modelId: string; solverId: string; actualBackend: string };
}

export interface NistProxyRunIdentityV2 extends NistProxyRunIdentity {
  executedSettings: Record<string, unknown> & { beamDiameter_um: number };
}

export interface NistProxyCampaignValidation {
  schemaVersion: 1;
  kind: 'lpbf-nist-amb2022-03-proxy-campaign-validation';
  campaignId: string | null;
  status: 'unavailable' | 'proxy-screening-only';
  validationStatus: 'unvalidated';
  experimentalValidation: false;
  numericalConvergenceStatus: 'not-evaluated';
  comparisonResiduals: null;
  observationCount: 6 | null;
  reasons: string[];
}

export interface NistProxyCampaignRecord { campaignId: string; document: NistProxyCampaign; documentSha256: string; createdAt: string }
export interface NistProxyCampaignPreview { campaign: NistProxyCampaign | null; validation: NistProxyCampaignValidation; previewSha256?: string }
export interface NistProxyCampaignCreate extends NistProxyCampaignPreview { record?: NistProxyCampaignRecord }

const invalid = () => new Error('Invalid run archive response. Reload before retrying.');
const object = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value);
const jobId = (value: unknown): value is string => typeof value === 'string' && /^[a-f0-9]{32}$/.test(value);
const sha = (value: unknown): value is string => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const bundleId = (value: unknown): value is string => typeof value === 'string' && /^[a-f0-9]{32}$/.test(value);
const count = (value: unknown): value is number => Number.isSafeInteger(value) && (value as number) >= 0;
const date = (value: unknown): value is string => typeof value === 'string' && Number.isFinite(Date.parse(value));
const bindingStatus = (value: unknown): value is RunSourceBindingStatus =>
  value === 'exact-revision-bound' || value === 'legacy-unlinked' || value === 'unverified-source-link';
const runKind = (value: unknown): value is RunKind =>
  value === 'analytical-screening' || value === 'build-screening'
  || value === 'transient-thermal' || value === 'bounded-material-screening'
  || value === 'gpu-thermal-pilot' || value === 'legacy-unspecified';
const opticalCases = new Set<string>(['0', '1.1', '1.2', '2.1', '2.2', '3.1', '3.2']);
const opticalDatasetId = 'nist-amb2022-03-optical-table4-local-v1';
const opticalArtifactSha = 'd1b36dfa2e01a3537093c481e249ce52df6b8879c1c67480ddb9aa10799133da';
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const sameSources = (actual: RunSourceLink[], expected: RunSourceLink[]) =>
  actual.length === expected.length && actual.every((source, index) =>
    source.datasetId === expected[index].datasetId
    && source.revision === expected[index].revision
    && source.documentSha256 === expected[index].documentSha256);

function documentIdentity(value: unknown, expectedJobId?: string): asserts value is RunDocument {
  if (!object(value) || value.schemaVersion !== 1 || !jobId(value.runId)
    || !object(value.capture) || value.capture.schemaVersion !== 1
    || !jobId(value.capture.jobId) || value.runId !== value.capture.jobId
    || (expectedJobId !== undefined && value.runId !== expectedJobId)
    || !['core-v1-bound', 'legacy-unbound', 'gpu-pilot-v1-bound', 'gpu-pilot-v2-warp-bound'].includes(value.capture.contractStatus as string)
    || (value.capture.runKind !== undefined && !runKind(value.capture.runKind))
    || !['resultJson', 'inputJson', 'materialJson'].every(field => typeof value.capture[field] === 'string')
    || !Array.isArray(value.sources) || value.sources.some(source => !object(source)
      || typeof source.datasetId !== 'string' || !/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$/.test(source.datasetId)
      || !Number.isSafeInteger(source.revision) || (source.revision as number) < 1 || !sha(source.documentSha256))) throw invalid();
  try {
    const result: unknown = JSON.parse(value.capture.resultJson as string);
    JSON.parse(value.capture.inputJson as string); JSON.parse(value.capture.materialJson as string);
    const capturedKind = object(result) && result.runKind === undefined ? 'legacy-unspecified'
      : object(result) ? result.runKind : undefined;
    if (!runKind(capturedKind) || (value.capture.runKind !== undefined && value.capture.runKind !== capturedKind)
      || (value.capture.runKind === undefined) !== (capturedKind === 'legacy-unspecified' && object(result) && result.runKind === undefined)) throw invalid();
    if (capturedKind === 'gpu-thermal-pilot') {
      const contractVersion = object(result) && object(result.gpuRunContract)
        ? result.gpuRunContract.schemaVersion : undefined;
      const expectedStatus = contractVersion === 2 ? 'gpu-pilot-v2-warp-bound' : 'gpu-pilot-v1-bound';
      if (value.capture.runKind !== capturedKind || value.capture.contractStatus !== expectedStatus
        || !object(result) || Object.hasOwn(result, 'coreContract') || !object(result.gpuRunContract)
        || !object(result.gpuRunContract.serializedInputs)
        || value.capture.inputJson !== result.gpuRunContract.serializedInputs.requestJson
        || value.capture.materialJson !== result.gpuRunContract.serializedInputs.materialJson) throw invalid();
      const settings = object(result.settings) ? result.settings : {};
      parseGpuPilotJob({ id: value.capture.jobId, status: 'completed', progress: 1, log: '', error: null,
        requestSummary: { jobType: 'gpu-thermal-pilot', backend: settings.backend, mode: settings.mode,
          material: settings.material, ...(settings.executionEngine === 'warp' ? { executionEngine: 'warp' } : {}) }, result });
    } else if (value.capture.contractStatus === 'gpu-pilot-v1-bound'
      || value.capture.contractStatus === 'gpu-pilot-v2-warp-bound') throw invalid();
  } catch { throw invalid(); }
}

function recordIdentity(value: unknown, expectedJobId: string): asserts value is RunRecord {
  if (!object(value)) throw invalid();
  documentIdentity(value.document, expectedJobId);
  if (!sha(value.documentSha256) || !date(value.createdAt) || value.evidenceStatus !== 'unvalidated-model'
    || !runKind(value.runKind)
    || value.runKind !== (value.document.capture.runKind ?? 'legacy-unspecified')
    || !bindingStatus(value.sourceBindingStatus)
    || (value.document.sources.length === 0 && value.sourceBindingStatus !== 'legacy-unlinked')
    || (value.document.sources.length > 0 && value.sourceBindingStatus === 'legacy-unlinked')) throw invalid();
}

async function request(path: string, signal: AbortSignal, body?: object) {
  const response = await fetch(`/api/lpbf/runs${path}`, { signal, cache: 'no-store',
    ...(body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}) });
  if (!response.ok) {
    throw new Error(`Run archive request failed (${response.status}).`);
  }
  return response.json();
}

function bundleManifest(value: unknown): asserts value is RunBundleManifest {
  if (!object(value) || ![1, 2].includes(value.schemaVersion as number) || value.kind !== 'metalliksa-lpbf-run-bundle'
    || Object.keys(value).sort().join(',') !== (value.schemaVersion === 1
      ? 'artifactCount,kind,metadata,runCount,schemaVersion,sourceBundle,sourceLinkCount'
      : 'artifactCount,campaignCount,kind,metadata,runCount,schemaVersion,sourceBundle,sourceLinkCount')
    || !object(value.metadata) || !sha(value.metadata.sha256) || !count(value.metadata.byteSize)
    || !object(value.sourceBundle) || !sha(value.sourceBundle.sha256) || !count(value.sourceBundle.byteSize)
    || !count(value.runCount) || !count(value.artifactCount) || !count(value.sourceLinkCount)
    || (value.schemaVersion === 2 && !count(value.campaignCount))) throw invalid();
}

async function bundleRequest(path: string, signal: AbortSignal): Promise<unknown> {
  const response = await fetch(`/api/lpbf/runs/bundles${path}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
    signal, cache: 'no-store',
  });
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail = object(body) && typeof body.error === 'string' ? ` ${body.error}` : '';
    throw new Error(`Run bundle request failed (${response.status}).${detail}`);
  }
  return response.json();
}

function exportedBundle(value: unknown, expectedId?: string): asserts value is ExportedRunBundle {
  if (!object(value) || !bundleId(value.bundleId) || value.storage !== 'server-local-directory'
    || (expectedId !== undefined && value.bundleId !== expectedId)) throw invalid();
  bundleManifest(value.manifest);
}

export async function exportRunBundle(signal: AbortSignal): Promise<ExportedRunBundle> {
  const result: unknown = await bundleRequest('/export', signal);
  exportedBundle(result);
  return result;
}

export async function verifyRunBundle(id: string, signal: AbortSignal): Promise<VerifiedRunBundle> {
  if (!bundleId(id)) throw new Error('Enter a valid 32-character bundle ID.');
  const result: unknown = await bundleRequest(`/${id}/verify`, signal);
  exportedBundle(result, id);
  if (result.verified !== true) throw invalid();
  return result as VerifiedRunBundle;
}

export async function restoreRunBundle(id: string, signal: AbortSignal): Promise<RestoredRunBundle> {
  if (!bundleId(id)) throw new Error('Enter a valid 32-character bundle ID.');
  const result: unknown = await bundleRequest(`/${id}/restore`, signal);
  exportedBundle(result, id);
  if (result.verified !== true || !bundleId(result.restoreId)) throw invalid();
  return result as RestoredRunBundle;
}

function portableBundle(value: unknown): asserts value is ImportedRunBundle {
  if (!object(value) || !bundleId(value.importId) || value.storage !== 'server-local-directory' || value.verified !== true) throw invalid();
  bundleManifest(value.manifest);
}

export function downloadRunBundle(id: string): void {
  if (!bundleId(id)) throw new Error('Invalid run bundle ID.');
  const anchor = document.createElement('a');
  anchor.href = `/api/lpbf/runs/bundles/${id}/download`; anchor.download = `metalliksa-lpbf-run-bundle-${id}.tar`;
  document.body.append(anchor); anchor.click(); anchor.remove();
}

export async function importRunBundle(file: File, signal: AbortSignal): Promise<ImportedRunBundle> {
  const response = await fetch('/api/lpbf/runs/bundles/import', {
    method: 'POST', headers: { 'Content-Type': 'application/x-tar' }, body: file, signal, cache: 'no-store',
  });
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail = object(body) && typeof body.error === 'string' ? ` ${body.error}` : '';
    throw new Error(`Run bundle verification failed (${response.status}).${detail}`);
  }
  const result: unknown = await response.json();
  portableBundle(result);
  return result;
}

export async function restoreImportedRunBundle(id: string, signal: AbortSignal): Promise<RestoredRunBundle> {
  if (!bundleId(id)) throw new Error('Invalid imported run bundle ID.');
  const result: unknown = await bundleRequest(`/imports/${id}/restore`, signal);
  if (!object(result) || !bundleId(result.bundleId) || !bundleId(result.restoreId) || result.verified !== true
    || result.storage !== 'server-local-directory') throw invalid();
  bundleManifest(result.manifest);
  return result as unknown as RestoredRunBundle;
}

export async function listRestoredRuns(restoreId: string, signal: AbortSignal): Promise<RunArchiveList> {
  if (!bundleId(restoreId)) throw new Error('Invalid restored bundle ID.');
  const response = await fetch(`/api/lpbf/runs/bundles/restores/${restoreId}/runs`, { signal, cache: 'no-store' });
  if (!response.ok) throw new Error(`Restored run list failed (${response.status}).`);
  const result: unknown = await response.json();
  if (!Array.isArray(result) || result.some(item => !object(item) || !jobId(item.runId) || !date(item.createdAt)
    || item.evidenceStatus !== 'unvalidated-model' || !runKind(item.runKind) || !bindingStatus(item.sourceBindingStatus))) throw invalid();
  return result;
}

export async function getRestoredRun(restoreId: string, runId: string, signal: AbortSignal): Promise<RunRecord> {
  if (!bundleId(restoreId) || !jobId(runId)) throw new Error('Invalid restored run identity.');
  const response = await fetch(`/api/lpbf/runs/bundles/restores/${restoreId}/runs/${runId}`, { signal, cache: 'no-store' });
  if (!response.ok) throw new Error(`Restored run could not be opened (${response.status}).`);
  const result: unknown = await response.json();
  recordIdentity(result, runId);
  if (!object(result) || !bindingStatus(result.sourceBindingStatus)) throw invalid();
  return result as RunRecord;
}

export async function listRuns(signal: AbortSignal): Promise<RunArchiveList> {
  const result: unknown = await request('', signal);
  if (!Array.isArray(result) || result.some(item => !object(item) || !jobId(item.runId)
    || !date(item.createdAt) || item.evidenceStatus !== 'unvalidated-model'
    || !runKind(item.runKind)
    || !bindingStatus(item.sourceBindingStatus))) throw invalid();
  return result;
}

export async function listNistProxyCampaigns(signal: AbortSignal): Promise<NistProxyCampaignRecord[]> {
  const result: unknown = await request('/proxy-campaigns', signal);
  if (!Array.isArray(result)) throw invalid();
  for (const record of result) {
    if (!object(record) || !exactKeys(record, 'campaignId,createdAt,document,documentSha256')
      || !campaignId(record.campaignId) || !sha(record.documentSha256) || !date(record.createdAt)
      || !object(record.document) || !Array.isArray(record.document.tracks)) throw invalid();
    const runIds = record.document.tracks.map(track => object(track) && object(track.runIdentity)
      ? track.runIdentity.runId : null);
    if (runIds.length !== 3 || runIds.some(id => !jobId(id))
      || record.campaignId !== record.document.campaignId
      || !opticalCases.has(String(record.document.caseNumber))) throw invalid();
    proxyCampaign(record.document, runIds as string[], record.document.caseNumber as NistOpticalCaseNumber);
  }
  return result as NistProxyCampaignRecord[];
}

export async function getRun(runId: string, signal: AbortSignal): Promise<RunRecord> {
  const result: unknown = await request(`/${encodeURIComponent(runId)}`, signal);
  recordIdentity(result, runId);
  return result;
}

function opticalError(value: unknown): boolean {
  if (!object(value) || !finite(value.signed_um) || !finite(value.absolute_um)
    || !finite(value.measuredMean_um) || !finite(value.publishedStdDev_um) || !finite(value.model_um)
    || value.absolute_um < 0 || value.measuredMean_um <= 0 || value.publishedStdDev_um <= 0
    || value.model_um <= 0) return false;
  return Math.abs(value.absolute_um - Math.abs(value.signed_um)) < 1e-6
    && Math.abs(value.model_um - value.measuredMean_um - value.signed_um) < 1e-6;
}

function opticalReport(value: unknown, run: RunRecord, caseNumber: NistOpticalCaseNumber): asserts value is NistOpticalReport {
  if (!object(value) || value.schemaVersion !== 1 || value.benchmark !== 'AMB2022-03-TMPG'
    || value.caseNumber !== caseNumber || value.validationStatus !== 'unvalidated'
    || !['unavailable', 'comparable-screening'].includes(value.status as string)
    || !object(value.reference) || value.reference.doi !== '10.18434/mds2-2718'
    || typeof value.reference.results !== 'string' || typeof value.reference.methods !== 'string'
    || !Array.isArray(value.reasons) || value.reasons.some(reason => typeof reason !== 'string' || !reason.trim())) throw invalid();
  if (value.sourceBinding !== null) {
    const source = value.sourceBinding;
    if (!object(source) || source.datasetId !== opticalDatasetId || source.sourceDatasetId !== 'nist-mds2-2718'
      || source.artifactSha256 !== opticalArtifactSha || !Number.isSafeInteger(source.revision)
      || !sha(source.documentSha256)
      || !run.document.sources.some(link => link.datasetId === source.datasetId
        && link.revision === source.revision && link.documentSha256 === source.documentSha256)) throw invalid();
  }
  if (value.status === 'unavailable') {
    if (value.errors !== null || value.reasons.length === 0) throw invalid();
  } else if (value.reasons.length !== 0 || value.sourceBinding === null || !object(value.errors)
    || !opticalError(value.errors.width) || !opticalError(value.errors.depth)) throw invalid();
}

export async function compareNistOpticalRun(run: RunRecord, caseNumber: NistOpticalCaseNumber,
  signal: AbortSignal, restoreId?: string): Promise<NistOpticalReport> {
  if (!jobId(run.document.runId) || !opticalCases.has(caseNumber) || (restoreId !== undefined && !bundleId(restoreId))) {
    throw new Error('Select a valid archived run, restored bundle and Table 4 case.');
  }
  const route = restoreId ? `/bundles/restores/${restoreId}/runs/${run.document.runId}/nist-comparison`
    : `/${run.document.runId}/nist-comparison`;
  const result: unknown = await request(route, signal, { caseNumber });
  opticalReport(result, run, caseNumber);
  return result;
}

export async function previewRun(jobId: string, sources: RunSourceLink[], signal: AbortSignal): Promise<RunPreview> {
  const result: unknown = await request('/preview', signal, { jobId, sources });
  if (!object(result)) throw invalid();
  documentIdentity(result.document, jobId);
  if (result.sourceBindingStatus !== 'exact-revision-bound' || result.document.sources.length === 0
    || !sameSources(result.document.sources, sources)
    || result.artifactIntegrity !== 'verified-at-dry-run' || !count(result.artifactCount)
    || !count(result.byteSize) || !object(result.quota)
    || !count(result.quota.totalArchiveSizeBytes) || !count(result.quota.maxArchiveSizeBytes)
    || result.quota.maxArchiveSizeBytes < result.quota.totalArchiveSizeBytes
    || typeof result.quota.approachingLimit !== 'boolean') throw invalid();
  return result as unknown as RunPreview;
}

export async function importRun(jobId: string, sources: RunSourceLink[], signal: AbortSignal): Promise<RunRecord> {
  const result: unknown = await request('/import', signal, { jobId, sources });
  recordIdentity(result, jobId);
  if (!sameSources(result.document.sources, sources)) throw invalid();
  return result;
}

const campaignId = (value: unknown): value is string => typeof value === 'string' && /^[a-f0-9]{32}$/.test(value);
const exactKeys = (value: Record<string, unknown>, expected: string) => Object.keys(value).sort().join(',') === expected;

function proxyRunIdentity(value: unknown, expectedRunId: string, schemaVersion: 1 | 2,
  expectedCase: NistOpticalCaseNumber): value is NistProxyRunIdentity | NistProxyRunIdentityV2 {
  const expectedKeys = schemaVersion === 2
    ? 'coreContract,executedSettings,inputSha256,materialId,materialRevisionSha256,materialSha256,resultArtifact,runDocumentSha256,runId'
    : 'coreContract,inputSha256,materialId,materialRevisionSha256,materialSha256,resultArtifact,runDocumentSha256,runId';
  return object(value) && exactKeys(value, expectedKeys)
    && value.runId === expectedRunId && sha(value.runDocumentSha256) && sha(value.inputSha256)
    && sha(value.materialSha256) && sha(value.materialRevisionSha256) && typeof value.materialId === 'string'
    && object(value.resultArtifact) && exactKeys(value.resultArtifact, 'path,sha256,size_bytes')
    && value.resultArtifact.path === 'capture/result.json' && sha(value.resultArtifact.sha256)
    && Number.isSafeInteger(value.resultArtifact.size_bytes) && (value.resultArtifact.size_bytes as number) >= 0
    && object(value.coreContract) && exactKeys(value.coreContract, 'actualBackend,modelId,schemaVersion,solverId')
    && Number.isSafeInteger(value.coreContract.schemaVersion) && typeof value.coreContract.modelId === 'string'
    && typeof value.coreContract.solverId === 'string' && typeof value.coreContract.actualBackend === 'string'
    && (schemaVersion === 1 || (object(value.executedSettings) && finite(value.executedSettings.beamDiameter_um)
      && value.executedSettings.beamDiameter_um === MELT_POOL_LITERATURE_CASES.find(
        item => item.id === `nist-amb2022-03-${expectedCase}`)?.beamDiameter_um));
}

function proxyCampaignValidation(value: unknown): asserts value is NistProxyCampaignValidation {
  if (!object(value) || value.schemaVersion !== 1 || value.kind !== 'lpbf-nist-amb2022-03-proxy-campaign-validation'
    || Object.keys(value).sort().join(',') !== 'campaignId,comparisonResiduals,experimentalValidation,kind,numericalConvergenceStatus,observationCount,reasons,schemaVersion,status,validationStatus'
    || (value.campaignId !== null && !campaignId(value.campaignId))
    || !['unavailable', 'proxy-screening-only'].includes(value.status as string)
    || value.validationStatus !== 'unvalidated' || value.experimentalValidation !== false
    || value.numericalConvergenceStatus !== 'not-evaluated' || value.comparisonResiduals !== null
    || !Array.isArray(value.reasons) || value.reasons.some(reason => typeof reason !== 'string' || !reason.trim())) throw invalid();
  if (value.status === 'proxy-screening-only') {
    if (value.observationCount !== 6 || value.reasons.length !== 0) throw invalid();
  } else if (value.observationCount !== null || value.reasons.length === 0) throw invalid();
}

function proxyCampaign(value: unknown, expectedRunIds: string[], expectedCase: NistOpticalCaseNumber): asserts value is NistProxyCampaign {
  const expectedKeys = value && typeof value === 'object' && (value as Record<string, unknown>).schemaVersion === 2
    ? 'beamInputDeclaration,benchmark,campaignId,caseNumber,claimBoundary,kind,samplingPlan,schemaVersion,sourceBinding,tracks'
    : 'benchmark,campaignId,caseNumber,claimBoundary,kind,samplingPlan,schemaVersion,sourceBinding,tracks';
  if (!object(value) || ![1, 2].includes(value.schemaVersion as number) || value.kind !== 'lpbf-nist-amb2022-03-proxy-campaign'
    || Object.keys(value).sort().join(',') !== expectedKeys
    || !campaignId(value.campaignId) || value.benchmark !== 'AMB2022-03-TMPG' || value.caseNumber !== expectedCase
    || !object(value.sourceBinding) || !exactKeys(value.sourceBinding, 'artifactPath,artifactSha256,artifactSizeBytes,caseNumber,datasetId,documentSha256,revision')
    || value.sourceBinding.datasetId !== opticalDatasetId
    || !Number.isSafeInteger(value.sourceBinding.revision) || (value.sourceBinding.revision as number) < 1
    || !sha(value.sourceBinding.documentSha256) || value.sourceBinding.artifactPath !== 'table4-aggregate-v2.json'
    || value.sourceBinding.artifactSha256 !== opticalArtifactSha || value.sourceBinding.artifactSizeBytes !== 4321
    || value.sourceBinding.caseNumber !== expectedCase
    || (value.schemaVersion === 2 && (!object(value.beamInputDeclaration)
      || !exactKeys(value.beamInputDeclaration, 'definition,mappingStatus,measuredProfileMatched,sourceBinding,status,value_um')
      || value.beamInputDeclaration.status !== 'published-source-declared'
      || value.beamInputDeclaration.definition !== 'D4sigma'
      || !finite(value.beamInputDeclaration.value_um)
      || value.beamInputDeclaration.value_um !== MELT_POOL_LITERATURE_CASES.find(item => item.id === `nist-amb2022-03-${expectedCase}`)?.beamDiameter_um
      || value.beamInputDeclaration.mappingStatus !== 'conditional-ideal-Gaussian'
      || value.beamInputDeclaration.measuredProfileMatched !== false
      || !object(value.beamInputDeclaration.sourceBinding)
      || !exactKeys(value.beamInputDeclaration.sourceBinding, 'artifactPath,artifactSha256,artifactSizeBytes,caseNumber,datasetId,documentSha256,revision')
      || !sameProxySourceBinding(value.beamInputDeclaration.sourceBinding, value.sourceBinding)))
    || !object(value.claimBoundary) || !exactKeys(value.claimBoundary, 'experimentalValidation,opticalOperatorMatched,resultKind,validationStatus')
    || value.claimBoundary.resultKind !== 'thermal-proxy-screening'
    || value.claimBoundary.validationStatus !== 'unvalidated' || value.claimBoundary.experimentalValidation !== false
    || value.claimBoundary.opticalOperatorMatched !== false
    || !object(value.samplingPlan) || !exactKeys(value.samplingPlan, 'coordinateFrame,expectedObservationCount,expectedTrackCount,replicateSemantics,scanDirection,sectionPositions_mm')
    || value.samplingPlan.coordinateFrame !== 'scan-start-relative'
    || value.samplingPlan.scanDirection !== '+X' || !Array.isArray(value.samplingPlan.sectionPositions_mm)
    || value.samplingPlan.sectionPositions_mm.length !== 2 || value.samplingPlan.sectionPositions_mm[0] !== 4.9
    || value.samplingPlan.sectionPositions_mm[1] !== 6 || value.samplingPlan.expectedTrackCount !== 3
    || value.samplingPlan.expectedObservationCount !== 6
    || value.samplingPlan.replicateSemantics !== (value.schemaVersion === 1
      ? 'independent-computational-runs-only' : 'reproducibility-evidence-not-independent-replicates')
    || !Array.isArray(value.tracks) || value.tracks.length !== 3) throw invalid();
  const seen = new Set<string>();
  for (let index = 0; index < value.tracks.length; index++) {
    const track = value.tracks[index];
    if (!object(track) || !exactKeys(track, 'experimentalTrackId,observations,replicateKind,runIdentity,simulatedTrackId')
      || track.simulatedTrackId !== `sim-${expectedRunIds[index]}` || track.experimentalTrackId !== null
      || track.replicateKind !== (value.schemaVersion === 1 ? 'independent-computational-run' : 'reproducibility-execution')
      || !proxyRunIdentity(track.runIdentity, expectedRunIds[index], value.schemaVersion as 1 | 2, expectedCase)
      || seen.has(track.runIdentity.runId) || !Array.isArray(track.observations) || track.observations.length !== 2) throw invalid();
    seen.add(track.runIdentity.runId);
    const sections = new Set<string>();
    for (const observation of track.observations) {
      if (!object(observation) || !exactKeys(observation, 'coordinateFrame,distanceFromScanStart_mm,geometry,operator,provenance,scanDirection,sectionId,status,surfaceZ_m')
        || !['x-4p9mm', 'x-6p0mm'].includes(observation.sectionId as string)
        || observation.coordinateFrame !== 'scan-start-relative' || observation.scanDirection !== '+X' || observation.surfaceZ_m !== 0
        || sections.has(observation.sectionId as string) || observation.status !== 'thermal-proxy'
        || observation.distanceFromScanStart_mm !== (observation.sectionId === 'x-4p9mm' ? 4.9 : 6)
        || !object(observation.geometry) || !exactKeys(observation.geometry, 'depth_um,width_um')
        || !finite(observation.geometry.width_um) || observation.geometry.width_um <= 0
        || !finite(observation.geometry.depth_um) || observation.geometry.depth_um <= 0
        || !object(observation.operator) || !exactKeys(observation.operator, 'contourOperatorId,evidenceClass,interpolationOperatorId,sectionOperatorId')
        || typeof observation.operator.sectionOperatorId !== 'string' || typeof observation.operator.interpolationOperatorId !== 'string'
        || typeof observation.operator.contourOperatorId !== 'string' || observation.operator.evidenceClass !== 'thermal-proxy-only'
        || !object(observation.provenance) || !exactKeys(observation.provenance, 'runIdentity,sourceBinding')
        || JSON.stringify(observation.provenance.sourceBinding) !== JSON.stringify(value.sourceBinding)
        || JSON.stringify(observation.provenance.runIdentity) !== JSON.stringify(track.runIdentity)) throw invalid();
      sections.add(observation.sectionId as string);
    }
    if (!sections.has('x-4p9mm') || !sections.has('x-6p0mm')) throw invalid();
  }
}

function sameProxySourceBinding(left: Record<string, unknown>, right: Record<string, unknown>): boolean {
  return ['datasetId', 'revision', 'documentSha256', 'artifactPath', 'artifactSha256', 'artifactSizeBytes', 'caseNumber']
    .every(key => left[key] === right[key]);
}

function proxyCampaignPreview(value: unknown, expectedRunIds: string[], expectedCase: NistOpticalCaseNumber): asserts value is NistProxyCampaignPreview {
  if (!object(value)) throw invalid();
  proxyCampaignValidation(value.validation);
  if (value.campaign === null) {
    if (value.validation.status !== 'unavailable' || value.validation.campaignId !== null || value.previewSha256 !== undefined) throw invalid();
    return;
  }
  if (value.validation.status !== 'proxy-screening-only' || value.validation.campaignId !== value.campaign.campaignId
    || !sha(value.previewSha256)) throw invalid();
  proxyCampaign(value.campaign, expectedRunIds, expectedCase);
}

function campaignRequestInputs(runIds: string[], caseNumber: NistOpticalCaseNumber) {
  if (!Array.isArray(runIds) || runIds.length !== 3 || runIds.some(id => !jobId(id))
    || new Set(runIds).size !== 3 || !opticalCases.has(caseNumber)) {
    throw new Error('Select three distinct archived run IDs and a valid Table 4 case.');
  }
}

export async function previewNistProxyCampaign(runIds: string[], caseNumber: NistOpticalCaseNumber,
  signal: AbortSignal): Promise<NistProxyCampaignPreview> {
  campaignRequestInputs(runIds, caseNumber);
  const result: unknown = await request('/proxy-campaigns/preview', signal, { runIds, caseNumber });
  proxyCampaignPreview(result, runIds, caseNumber);
  return result;
}

export async function createNistProxyCampaign(runIds: string[], caseNumber: NistOpticalCaseNumber,
  previewSha256: string, signal: AbortSignal): Promise<NistProxyCampaignCreate> {
  campaignRequestInputs(runIds, caseNumber);
  if (!sha(previewSha256)) throw new Error('Preview the archived runs before saving the campaign.');
  const result: unknown = await request('/proxy-campaigns', signal, { runIds, caseNumber, previewSha256 });
  proxyCampaignPreview(result, runIds, caseNumber);
  const response = result as NistProxyCampaignCreate;
  if (response.campaign !== null) {
    if (response.previewSha256 !== previewSha256 || !object(response.record)
      || !exactKeys(response.record, 'campaignId,createdAt,document,documentSha256')) throw invalid();
    const record = response.record;
    if (record.campaignId !== response.campaign.campaignId || !sha(record.documentSha256) || !date(record.createdAt)) throw invalid();
    proxyCampaign(record.document, runIds, caseNumber);
    if (record.document.campaignId !== response.campaign.campaignId
      || JSON.stringify(record.document) !== JSON.stringify(response.campaign)) throw invalid();
  } else if (response.record !== undefined) throw invalid();
  return response;
}
