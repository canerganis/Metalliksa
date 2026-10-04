import { randomUUID } from 'node:crypto';
import { mkdir, open, link, unlink, readdir, readFile, stat, type FileHandle } from 'node:fs/promises';
import path from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { parseResearchSnapshot } from '../src/utils/researchRegistry';
import type { ResearchSnapshot } from '../src/types/research';

export interface ResearchRegistryEnvelope {
  registryId: string;
  revision: number;
  savedAt: string | null;
  snapshot: ResearchSnapshot;
}

export class ResearchRegistryError extends Error {
  constructor(public status: number, message: string, public current?: ResearchRegistryEnvelope) { super(message); }
}

const emptySnapshot = (): ResearchSnapshot => ({ schemaVersion: 1, briefs: [], sources: [], findings: [], integrations: [], feedback: [] });
const MAX_FILE_BYTES = 10 * 1024 * 1024 + 1024;
const revisionName = (revision: number) => `revision-${String(revision).padStart(12, '0')}.json`;
const isCode = (error: unknown, code: string) => (error as NodeJS.ErrnoException)?.code === code;
/** Bound for retrying a transiently denied lock unlink on Windows (see release()). */
const LOCK_RELEASE_RETRY_MS = 1000;

/** One local, unauthenticated registry. Committed revision files are never rewritten.
 * All instances must use this same directory on a filesystem supporting atomic hard links.
 * A crash-left lock deliberately blocks access: an operator must inspect it before recovery.
 */
export class ResearchEvidenceRegistry {
  constructor(readonly directory = process.env.RESEARCH_REGISTRY_DIR || path.join(process.cwd(), '.research-registry'), private readonly lockTimeoutMs = 2000) {}

  private async locked<T>(operation: () => Promise<T>): Promise<T> {
    await mkdir(this.directory, { recursive: true });
    const lockPath = path.join(this.directory, '.write-lock');
    const deadline = Date.now() + this.lockTimeoutMs;
    let lock: FileHandle;
    let sawContention = false;
    while (true) {
      try { lock = await open(lockPath, 'wx', 0o600); break; }
      catch (error) {
        // Windows: an exclusive create racing another holder's release (its unlink has set the delete
        // disposition but not yet closed the handle) fails with EPERM (STATUS_DELETE_PENDING), not EEXIST.
        // That is contention: retry it within the same deadline. A persistent EPERM with no other holder ever
        // seen is a real permission failure and is rethrown unchanged once the deadline passes; after EEXIST
        // contention the deadline is reported as busy, like a lock that stayed held.
        const releasing = process.platform === 'win32' && isCode(error, 'EPERM');
        if (!isCode(error, 'EEXIST') && !releasing) throw error;
        if (isCode(error, 'EEXIST')) sawContention = true;
        if (Date.now() >= deadline) {
          if (releasing && !sawContention) throw error;
          throw new ResearchRegistryError(503, 'Research registry is busy or requires lock recovery. Retry; no data was replaced.');
        }
        await delay(25);
      }
    }
    try {
      await lock.writeFile(JSON.stringify({ pid: process.pid, acquiredAt: new Date().toISOString() }));
      await lock.sync();
      return await operation();
    } finally {
      await this.release(lock, lockPath);
    }
  }

  /** Release never throws: by the time it runs a save may already be committed (its revision file is
   * linked), and reporting that save as failed would invite a duplicate retry. A failed close still unlinks.
   * On Windows an antivirus or indexer handle can briefly deny the unlink (EPERM/EBUSY/EACCES); it is retried
   * for up to LOCK_RELEASE_RETRY_MS. If the lock still cannot be removed it is logged and left in place: later
   * requests then answer 503 "busy or requires lock recovery" until an operator removes .write-lock, the same
   * documented path as a crash-left lock. Nothing is reset or overwritten. */
  private async release(lock: FileHandle, lockPath: string): Promise<void> {
    try { await lock.close(); }
    catch (error) { console.error('[ResearchRegistry] Closing the write lock failed; removing it anyway:', error); }
    const deadline = Date.now() + LOCK_RELEASE_RETRY_MS;
    while (true) {
      try { await unlink(lockPath); return; }
      catch (error) {
        if (isCode(error, 'ENOENT')) return;
        const transient = process.platform === 'win32' && ['EPERM', 'EBUSY', 'EACCES'].some(code => isCode(error, code));
        if (transient && Date.now() < deadline) { await delay(25); continue; }
        console.error('[ResearchRegistry] The write lock could not be removed; requests will report the registry as busy until an operator removes .write-lock:', error);
        return;
      }
    }
  }

  private async publish(envelope: ResearchRegistryEnvelope): Promise<void> {
    const temporary = path.join(this.directory, `.pending-${randomUUID()}`);
    const file = await open(temporary, 'wx', 0o600);
    try {
      await file.writeFile(JSON.stringify(envelope));
      await file.sync();
    } finally { await file.close(); }
    try {
      // Unlike rename, link fails if the revision already exists, and publishes only
      // a complete, synced inode. A failed write cannot expose partial committed JSON.
      await link(temporary, path.join(this.directory, revisionName(envelope.revision)));
      // POSIX directory sync makes the new name durable. Windows does not expose
      // directory fsync through Node; file contents are still flushed before linking.
      if (process.platform !== 'win32') {
        const directory = await open(this.directory, 'r');
        try { await directory.sync(); } finally { await directory.close(); }
      }
    } finally { await unlink(temporary); }
  }

  private async scan(requestedRevision?: number): Promise<{ current: ResearchRegistryEnvelope; selected?: ResearchRegistryEnvelope; revisions: { revision: number; savedAt: string }[] }> {
    const entries = await readdir(this.directory);
    const names = entries.filter(name => name.startsWith('revision-')).sort();
    if (!names.length) {
      // Pending files indicate an interrupted initial write. Do not silently invent
      // a new identity when potentially recoverable registry data already exists.
      if (entries.some(name => name.startsWith('.pending-'))) throw new ResearchRegistryError(503, 'Research registry initialization was interrupted. Storage recovery is required.');
      const initial: ResearchRegistryEnvelope = { registryId: randomUUID(), revision: 0, savedAt: null, snapshot: emptySnapshot() };
      await this.publish(initial);
      return { current: initial, selected: requestedRevision === 0 ? initial : undefined, revisions: [] };
    }
    let current: ResearchRegistryEnvelope | undefined;
    let selected: ResearchRegistryEnvelope | undefined;
    const revisions: { revision: number; savedAt: string }[] = [];
    try {
      for (let index = 0; index < names.length; index++) {
        if (names[index] !== revisionName(index)) throw new Error('Missing or unexpected revision file');
        const filename = path.join(this.directory, names[index]);
        const info = await stat(filename);
        if (!info.isFile() || info.size > MAX_FILE_BYTES) throw new Error('Invalid revision file size');
        const value = JSON.parse(await readFile(filename, 'utf8'));
        if (!value || typeof value !== 'object' || typeof value.registryId !== 'string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value.registryId) || value.revision !== index
          || (index === 0 ? value.savedAt !== null : typeof value.savedAt !== 'string' || !Number.isFinite(Date.parse(value.savedAt)))
          || (index > 0 && value.registryId !== current!.registryId)) throw new Error('Invalid revision envelope');
        const snapshot = parseResearchSnapshot(value.snapshot);
        if (index === 0 && JSON.stringify(snapshot) !== JSON.stringify(emptySnapshot())) throw new Error('Invalid initial revision');
        current = { registryId: value.registryId, revision: index, savedAt: value.savedAt, snapshot };
        if (index === requestedRevision) selected = current;
        if (index > 0) revisions.push({ revision: index, savedAt: value.savedAt });
      }
    } catch {
      throw new ResearchRegistryError(503, 'Research registry storage is invalid or unreadable. Existing files were preserved; operator recovery is required.');
    }
    // Validate every historical file, but retain at most the current/requested
    // snapshots instead of multiplying snapshot memory by revision count.
    return { current: current!, selected, revisions };
  }

  current(): Promise<ResearchRegistryEnvelope> { return this.locked(async () => (await this.scan()).current); }

  history(): Promise<{ registryId: string; revisions: { revision: number; savedAt: string }[] }> {
    return this.locked(async () => {
      const { current, revisions } = await this.scan();
      return { registryId: current.registryId, revisions };
    });
  }

  revision(revision: number): Promise<ResearchRegistryEnvelope> {
    return this.locked(async () => {
      const version = (await this.scan(revision)).selected;
      if (!version) throw new ResearchRegistryError(404, 'Research registry revision was not found.');
      return version;
    });
  }

  save(registryId: unknown, expectedRevision: unknown, value: unknown): Promise<ResearchRegistryEnvelope> {
    if (typeof registryId !== 'string' || !registryId || typeof expectedRevision !== 'number' || !Number.isSafeInteger(expectedRevision) || expectedRevision < 0 || expectedRevision >= Number.MAX_SAFE_INTEGER) {
      return Promise.reject(new ResearchRegistryError(400, 'registryId must be a nonempty string and expectedRevision a nonnegative safe integer.'));
    }
    let snapshot: ResearchSnapshot;
    try { snapshot = parseResearchSnapshot(value); }
    catch (error) { return Promise.reject(new ResearchRegistryError(400, (error as Error).message)); }
    // A snapshot is captured before entering the asynchronous lock; callers cannot
    // mutate it while another writer is active.
    snapshot = structuredClone(snapshot);
    if (Buffer.byteLength(JSON.stringify(snapshot)) > MAX_FILE_BYTES - 1024) return Promise.reject(new ResearchRegistryError(413, 'Research registry snapshot exceeds the 10 MB limit.'));
    return this.locked(async () => {
      const current = (await this.scan()).current;
      if (current.registryId !== registryId || current.revision !== expectedRevision) throw new ResearchRegistryError(409, 'Research registry changed. Load the current revision before saving again.', current);
      const next: ResearchRegistryEnvelope = { registryId, revision: current.revision + 1, savedAt: new Date().toISOString(), snapshot };
      await this.publish(next);
      return next;
    });
  }
}
