/** Versioned source metadata only. Artifact bytes and scientific review are separate gates. */
import { createHash } from 'node:crypto';
import { mkdirSync } from 'node:fs';
import path from 'node:path';
import { DatabaseSync, backup } from 'node:sqlite';
import { artifactRelativePath } from './lpbfArtifactStore';

import type { LpbfSourceDocument, LpbfSourceRevision } from '../src/types/lpbfSource';
export type { LpbfSourceDocument, LpbfSourceRevision } from '../src/types/lpbfSource';

const MAX_BYTES = 1024 * 1024;
const digest = (text: string) => createHash('sha256').update(text).digest('hex');
function text(value: unknown): value is string { return typeof value === 'string' && value.trim().length > 0; }
function keys(value: any, expected: string[]) {
  if (!value || typeof value !== 'object' || Array.isArray(value)
    || Object.keys(value).length !== expected.length || expected.some(key => !Object.hasOwn(value, key))) {
    throw new Error('Invalid source metadata fields');
  }
}
function jsonValue(value: unknown, depth = 0): void {
  if (depth > 32) throw new Error('Source context is too deeply nested');
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return;
  if (typeof value === 'number' && Number.isFinite(value)) return;
  if (Array.isArray(value)) { value.forEach(item => jsonValue(item, depth + 1)); return; }
  if (value && typeof value === 'object' && Object.getPrototypeOf(value) === Object.prototype) {
    Object.values(value).forEach(item => jsonValue(item, depth + 1)); return;
  }
  throw new Error('Source metadata must contain finite JSON values');
}
function https(value: unknown) {
  if (!text(value)) throw new Error('Source URL is required');
  const url = new URL(value);
  if (url.protocol !== 'https:' || url.username || url.password) throw new Error('Source URL must be HTTPS without credentials');
}
function identifier(value: unknown) {
  if (typeof value !== 'string' || !/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$/.test(value)) throw new Error('Invalid dataset id');
}
function documentJson(raw: unknown): string {
  jsonValue(raw);
  const serialized = JSON.stringify(raw);
  if (Buffer.byteLength(serialized) > MAX_BYTES) throw new Error('Source metadata exceeds 1 MiB');
  const value = JSON.parse(serialized);
  keys(value, ['schemaVersion', 'datasetId', 'materialId', 'processScope', 'source', 'artifacts', 'sourceContext']);
  identifier(value.datasetId);
  if (value.schemaVersion !== 1 || !['ti6al4v', 'ss316l', 'alsi10mg', 'in718', 'in625'].includes(value.materialId)
    || !['bare-plate', 'powder-bed', 'unknown', 'material-characterization'].includes(value.processScope)) throw new Error('Unsupported source archive schema, material or process scope');
  keys(value.source, ['url', 'citation', 'version', 'terms', 'termsMissingReason']);
  https(value.source.url);
  if (!text(value.source.citation) || !text(value.source.version)) throw new Error('Source citation and version are required');
  if (!(value.source.terms === null ? text(value.source.termsMissingReason)
    : text(value.source.terms) && value.source.termsMissingReason === null)) throw new Error('Source terms or an explicit missing reason are required');
  if (!Array.isArray(value.artifacts) || !value.artifacts.length || value.artifacts.length > 1000) throw new Error('Expected 1 to 1000 artifact references');
  const paths = new Set<string>();
  for (const artifact of value.artifacts) {
    keys(artifact, ['relativePath', 'sha256', 'byteSize', 'sourceUrl']);
    const name = artifact.relativePath;
    artifactRelativePath(name);
    if (!text(name) || name.length > 512 || /[\\:\x00-\x1f]/.test(name)
      || name.split('/').some(part => !part || part === '.' || part === '..') || paths.has(name.toLowerCase())) throw new Error('Invalid or duplicate artifact path');
    paths.add(name.toLowerCase());
    if (typeof artifact.sha256 !== 'string' || !/^[0-9a-f]{64}$/.test(artifact.sha256)
      || !Number.isSafeInteger(artifact.byteSize) || artifact.byteSize <= 0) throw new Error('Invalid artifact hash or byte size');
    https(artifact.sourceUrl);
  }
  if (value.sourceContext !== null && (typeof value.sourceContext !== 'object' || Array.isArray(value.sourceContext))) throw new Error('Source context must be an object or null');
  return serialized;
}

/** Validate and detach caller-owned data before asynchronous import work. */
export function validateSourceDocument(raw: unknown): LpbfSourceDocument {
  return JSON.parse(documentJson(raw)) as LpbfSourceDocument;
}

function decode(row: any): LpbfSourceRevision {
  try {
    if (typeof row.document_json !== 'string' || Buffer.byteLength(row.document_json) > MAX_BYTES
      || digest(row.document_json) !== row.document_sha256 || !Number.isSafeInteger(row.revision) || row.revision < 1
      || typeof row.created_at !== 'string' || !Number.isFinite(Date.parse(row.created_at))) throw new Error('Invalid record');
    const document = JSON.parse(documentJson(JSON.parse(row.document_json))) as LpbfSourceDocument;
    if (document.datasetId !== row.dataset_id) throw new Error('Dataset identity mismatch');
    return { revision: row.revision, createdAt: row.created_at, document,
      documentSha256: row.document_sha256, evidenceStatus: 'unreviewed-source-archive', artifactIntegrity: 'not-verified' };
  } catch { throw new Error('Source metadata integrity check failed; existing records were preserved'); }
}

export class LpbfSourceRepository {
  private readonly db: DatabaseSync;
  private closed = false;
  private backingUp = false;

  /** Explicit path only: constructing this repository never migrates a legacy store. */
  constructor(readonly filename: string, options: { readOnly?: boolean } = {}) {
    this.db = new DatabaseSync(filename, { readOnly: options.readOnly ?? false });
    try {
      const version = this.db.prepare('PRAGMA user_version').get()!.user_version;
      if (version === 0) {
        if (options.readOnly) throw new Error('Unrecognized read-only database');
        if (this.db.prepare("SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").get()) throw new Error('Unrecognized existing database');
        this.db.exec(`BEGIN IMMEDIATE;
          CREATE TABLE lpbf_source_revisions (
            dataset_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision > 0),
            document_json TEXT NOT NULL, document_sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
            PRIMARY KEY(dataset_id, revision)) STRICT;
          CREATE TABLE lpbf_metadata (kind TEXT PRIMARY KEY) STRICT;
          INSERT INTO lpbf_metadata VALUES ('metalliksa-lpbf-sources-v1');
          PRAGMA user_version=1; COMMIT;`);
      } else if (version !== 1) throw new Error('Unsupported LPBF source database version');
      if (this.db.prepare('SELECT kind FROM lpbf_metadata').get()?.kind !== 'metalliksa-lpbf-sources-v1') throw new Error('Unrecognized database identity');
      if (options.readOnly) {
        if (this.db.prepare('PRAGMA integrity_check').get()!.integrity_check !== 'ok') throw new Error('Metadata integrity check failed');
      } else this.db.exec('PRAGMA foreign_keys=ON; PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; PRAGMA busy_timeout=250; PRAGMA max_page_count=262144;');
    } catch (error) { this.db.close(); throw error; }
  }

  close() {
    if (this.backingUp) throw new Error('Metadata backup is in progress');
    if (!this.closed) { this.db.close(); this.closed = true; }
  }

  current(datasetId: string): LpbfSourceRevision | null {
    identifier(datasetId);
    const row = this.db.prepare('SELECT * FROM lpbf_source_revisions WHERE dataset_id=? ORDER BY revision DESC LIMIT 1').get(datasetId);
    return row ? decode(row) : null;
  }

  revision(datasetId: string, revision: number): LpbfSourceRevision | null {
    identifier(datasetId);
    if (!Number.isSafeInteger(revision) || revision < 1) throw new Error('Invalid revision');
    const row = this.db.prepare('SELECT * FROM lpbf_source_revisions WHERE dataset_id=? AND revision=?').get(datasetId, revision);
    return row ? decode(row) : null;
  }

  history(datasetId: string, offset = 0, limit = 100): LpbfSourceRevision[] {
    identifier(datasetId);
    if (!Number.isSafeInteger(offset) || offset < 0 || !Number.isSafeInteger(limit) || limit < 1 || limit > 100) throw new Error('Invalid history pagination');
    return this.db.prepare('SELECT * FROM lpbf_source_revisions WHERE dataset_id=? ORDER BY revision LIMIT ? OFFSET ?').all(datasetId, limit, offset).map(decode);
  }

  /** Stream every historical revision from a fixed backup snapshot. */
  *allRevisions(): Generator<LpbfSourceRevision> {
    for (const row of this.db.prepare('SELECT * FROM lpbf_source_revisions ORDER BY dataset_id, revision').iterate()) yield decode(row);
  }

  save(raw: unknown, expectedRevision: number): LpbfSourceRevision {
    if (this.backingUp) throw new Error('Metadata backup is in progress');
    if (!Number.isSafeInteger(expectedRevision) || expectedRevision < 0 || expectedRevision >= Number.MAX_SAFE_INTEGER) throw new Error('Invalid expected revision');
    const serialized = documentJson(raw);
    const document = JSON.parse(serialized) as LpbfSourceDocument;
    this.db.exec('BEGIN IMMEDIATE');
    try {
      const current = this.current(document.datasetId);
      if ((current?.revision ?? 0) !== expectedRevision) throw new Error('Source revision conflict; reload current metadata');
      const revision = expectedRevision + 1;
      const createdAt = new Date().toISOString();
      this.db.prepare('INSERT INTO lpbf_source_revisions VALUES (?, ?, ?, ?, ?)')
        .run(document.datasetId, revision, serialized, digest(serialized), createdAt);
      this.db.exec('COMMIT');
      return { revision, createdAt, document, documentSha256: digest(serialized),
        evidenceStatus: 'unreviewed-source-archive', artifactIntegrity: 'not-verified' };
    } catch (error) { this.db.exec('ROLLBACK'); throw error; }
  }

  async backupMetadata(directory: string): Promise<{ path: string; artifactPayloadsIncluded: false }> {
    if (this.closed || this.backingUp) throw new Error('Metadata repository is closed or backing up');
    // Exclusive directory creation prevents the backup API from replacing any existing file.
    mkdirSync(directory);
    this.backingUp = true;
    const filename = path.join(directory, 'metadata.sqlite');
    try {
      await backup(this.db, filename);
      const restored = new DatabaseSync(filename);
      try {
        // Only the newly created backup is changed. A portable snapshot must not
        // depend on (or create on read) unhashed WAL/SHM sidecar state.
        restored.exec('PRAGMA journal_mode=DELETE');
        if (restored.prepare('PRAGMA integrity_check').get()!.integrity_check !== 'ok') throw new Error('Backup integrity check failed');
        for (const row of restored.prepare('SELECT * FROM lpbf_source_revisions').iterate()) decode(row);
      } finally { restored.close(); }
      return { path: filename, artifactPayloadsIncluded: false };
    } finally { this.backingUp = false; }
  }
}
