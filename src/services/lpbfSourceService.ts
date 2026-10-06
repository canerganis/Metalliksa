import type { LpbfSourceDocument, LpbfSourceRevision } from '../types/lpbfSource';

export type { LpbfSourceDocument, LpbfSourceRevision };
export interface SourcePreview {
  document: LpbfSourceDocument; documentSha256: string; expectedRevision: number;
  artifactCount: number; byteSize: number;
  evidenceStatus: 'unreviewed-source-archive'; artifactIntegrity: 'verified-at-dry-run';
}
export interface SourceVerification {
  datasetId: string; revision: number; documentSha256: string; verifiedAt: string;
  evidenceStatus: 'unreviewed-source-archive'; artifactIntegrity: 'verified-now';
}
export interface SourceSnapshot {
  current: LpbfSourceRevision | null;
  preview?: SourcePreview;
  verification?: SourceVerification;
  imported?: boolean;
}
export interface SourceRevisionPage {
  datasetId: string; offset: number; limit: number; revisions: SourceRevisionSummary[]; hasMore: boolean;
}
export interface SourceRevisionSummary {
  revision: number; createdAt: string; documentSha256: string;
  evidenceStatus: 'unreviewed-source-archive'; artifactIntegrity: 'not-verified';
  materialId: LpbfSourceDocument['materialId']; processScope: LpbfSourceDocument['processScope'];
}
export type SourceAction = 'current' | 'preview' | 'import' | 'verify';

async function request(path: string, signal: AbortSignal, body?: object) {
  const response = await fetch(`/api/lpbf/sources${path}`, { signal, cache: 'no-store',
    ...(body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}) });
  if (!response.ok) {
    const guidance = response.status === 409 ? 'Preview again; the source changed or another operation is running.'
      : 'Source archive unavailable. Reload to inspect the current record before retrying.';
    throw new Error(`Source archive request failed (${response.status}). ${guidance}`);
  }
  return response.json();
}
const invalid = () => new Error('Invalid source archive response or dataset identity. Reload before retrying.');
const sha = (value: unknown) => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
const count = (value: unknown) => Number.isSafeInteger(value) && (value as number) >= 0;
function documentIdentity(document: LpbfSourceDocument, datasetId: string) {
  if (!document || document.datasetId !== datasetId || document.schemaVersion !== 1
    || !['ti6al4v', 'ss316l', 'alsi10mg', 'in718', 'in625'].includes(document.materialId)
    || !['bare-plate', 'powder-bed', 'unknown', 'material-characterization'].includes(document.processScope)
    || !document.source || typeof document.source.citation !== 'string'
    || !Array.isArray(document.artifacts) || !document.artifacts.length) throw invalid();
}
function revisionIdentity(value: LpbfSourceRevision, datasetId: string) {
  if (!value || !count(value.revision) || value.revision < 1 || !sha(value.documentSha256)
    || value.evidenceStatus !== 'unreviewed-source-archive' || value.artifactIntegrity !== 'not-verified') throw invalid();
  documentIdentity(value.document, datasetId);
}
export async function sourceCatalog(signal: AbortSignal): Promise<{ datasetId: string; title: string }[]> {
  const result = await request('', signal);
  if (!Array.isArray(result?.sources) || result.sources.some((item: any) =>
    typeof item?.title !== 'string' || typeof item?.datasetId !== 'string' || !/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$/.test(item.datasetId))) throw invalid();
  return result.sources;
}

export async function sourceRevisionHistory(datasetId: string, signal: AbortSignal,
  offset = 0, limit = 100): Promise<SourceRevisionPage> {
  if (!/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$/.test(datasetId)
    || !Number.isSafeInteger(offset) || offset < 0 || !Number.isSafeInteger(limit) || limit < 1 || limit > 100) throw invalid();
  const result = await request(`/${encodeURIComponent(datasetId)}/revisions?offset=${offset}&limit=${limit}`, signal);
  if (!result || result.datasetId !== datasetId || result.offset !== offset || result.limit !== limit
    || !Array.isArray(result.revisions) || typeof result.hasMore !== 'boolean') throw invalid();
  result.revisions.forEach((revision: SourceRevisionSummary) => {
    if (!revision || !Number.isSafeInteger(revision.revision) || revision.revision < 1
      || typeof revision.createdAt !== 'string' || !Number.isFinite(Date.parse(revision.createdAt))
      || !sha(revision.documentSha256) || revision.evidenceStatus !== 'unreviewed-source-archive'
      || revision.artifactIntegrity !== 'not-verified'
      || !['ti6al4v', 'ss316l', 'alsi10mg', 'in718', 'in625'].includes(revision.materialId)
      || !['bare-plate', 'powder-bed', 'unknown', 'material-characterization'].includes(revision.processScope)) throw invalid();
  });
  if (result.revisions.length > limit || (result.hasMore && result.revisions.length !== limit)) throw invalid();
  return result as SourceRevisionPage;
}

export async function sourceRevision(datasetId: string, revision: number, signal: AbortSignal): Promise<LpbfSourceRevision> {
  if (!/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$/.test(datasetId) || !Number.isSafeInteger(revision) || revision < 1) throw invalid();
  const result = await request(`/${encodeURIComponent(datasetId)}/revisions/${revision}`, signal);
  if (!result || result.datasetId !== datasetId) throw invalid();
  revisionIdentity(result.revision, datasetId);
  if (result.revision.revision !== revision) throw invalid();
  return result.revision;
}

export async function allSourceRevisions(datasetId: string, signal: AbortSignal): Promise<SourceRevisionSummary[]> {
  const revisions: SourceRevisionSummary[] = [];
  for (let offset = 0; ; offset += 100) {
    const page = await sourceRevisionHistory(datasetId, signal, offset, 100);
    revisions.push(...page.revisions);
    if (!page.hasMore) return revisions;
    if (!page.revisions.length) throw invalid();
  }
}

export async function sourceAction(datasetId: string, action: SourceAction,
  signal: AbortSignal, preview?: SourcePreview): Promise<SourceSnapshot> {
  const path = `/${encodeURIComponent(datasetId)}`;
  if (action === 'import' && (!preview || preview.document.datasetId !== datasetId
    || !sha(preview.documentSha256) || !count(preview.expectedRevision))) throw invalid();
  const result = action === 'current' ? null : await request(`${path}/${action}`, signal,
    action === 'import' ? { expectedRevision: preview!.expectedRevision, documentSha256: preview!.documentSha256 } : {});
  const response = await request(path, signal);
  if (!response || !Object.hasOwn(response, 'current')) throw invalid();
  const current: LpbfSourceRevision | null = response.current;
  if (current !== null) revisionIdentity(current, datasetId);
  const snapshot: SourceSnapshot = { current };
  if (action === 'preview') {
    documentIdentity(result?.document, datasetId);
    if (!sha(result.documentSha256) || !count(result.expectedRevision)
      || !count(result.artifactCount) || !count(result.byteSize)
      || result.artifactCount !== result.document.artifacts.length
      || result.artifactIntegrity !== 'verified-at-dry-run' || result.evidenceStatus !== 'unreviewed-source-archive') throw invalid();
    if (result.expectedRevision !== (current?.revision ?? 0)) throw new Error('Stored revision changed. Preview again.');
    snapshot.preview = result;
  }
  if (action === 'import' || action === 'verify') {
    const identity = action === 'import' ? result?.revision : result;
    if (action === 'import') revisionIdentity(identity, datasetId);
    if (!identity || (action === 'verify' && (identity.datasetId !== datasetId
      || identity.artifactIntegrity !== 'verified-now' || identity.evidenceStatus !== 'unreviewed-source-archive'
      || typeof identity.verifiedAt !== 'string' || !Number.isFinite(Date.parse(identity.verifiedAt))))) throw invalid();
    if (!current || identity.revision !== current.revision || identity.documentSha256 !== current.documentSha256) {
      throw new Error('Stored revision changed during the operation. Reload and verify again.');
    }
    if (action === 'import') {
      if (result.artifactIntegrity !== 'verified-at-import' || identity.documentSha256 !== preview!.documentSha256
        || identity.revision !== preview!.expectedRevision + 1) throw invalid();
      snapshot.imported = true;
    } else snapshot.verification = result;
  }
  return snapshot;
}

export class SourceNotImportedError extends Error {
  readonly datasetId: string;
  constructor(datasetId: string) {
    super(`Source ${datasetId} is not imported in this installation`);
    this.name = 'SourceNotImportedError';
    this.datasetId = datasetId;
  }
}

export async function sourceMeasurements(datasetId: string, signal: AbortSignal): Promise<{datasetId:string; data:any[]; scope?: { trackScope?: string; file?: string; rationale?: string; unresolved?: readonly string[] }}> {
  const response = await fetch(`/api/lpbf/sources/${encodeURIComponent(datasetId)}/measurements`, { signal, cache: 'no-store' });
  if (response.status === 404) throw new SourceNotImportedError(datasetId);
  if (!response.ok) throw new Error('Failed to load experimental measurements');
  return response.json();
}
