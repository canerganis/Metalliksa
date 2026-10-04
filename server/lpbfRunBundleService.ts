import { randomUUID } from 'node:crypto';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { artifactDirectory, LpbfArtifactStore } from './lpbfArtifactStore';
import { LpbfRunArchiveError } from './lpbfRunArchiveService';
import { backupRunBundle, restoreRunBundle, verifyRunBundle } from './lpbfRunBundle';
import { LpbfRunRepository } from './lpbfRunRepository';
import { LpbfSourceRepository } from './lpbfSourceRepository';
import { createRunBundleTar, extractRunBundleTar } from './lpbfRunBundleTar';
import type { Readable } from 'node:stream';

const ID = /^[0-9a-f]{32}$/;

function overlaps(a: string, b: string): boolean {
  const relative = path.relative(a, b);
  return !relative || (!relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative));
}

function safeBundleError(error: unknown, action: 'verify' | 'restore' | 'import'): string {
  const message = error instanceof Error ? error.message : '';
  if (/Campaign Table 4 source artifact binding mismatch/.test(message)) return 'Run bundle campaign source binding verification failed.';
  if (/Campaign archived run provenance binding mismatch/.test(message)) return 'Run bundle campaign execution provenance verification failed.';
  if (/Campaign captured section geometry or observations binding mismatch|Campaign captured section artifact verification failed/.test(message)) {
    return 'Run bundle campaign section evidence verification failed.';
  }
  if (/Proxy campaign metadata integrity failed/.test(message)) return 'Run bundle campaign metadata verification failed.';
  if (action === 'import') return 'Portable run bundle integrity verification failed.';
  return action === 'restore' ? 'Run bundle restore integrity verification failed.' : 'Run bundle integrity verification failed.';
}

/** Bundles and restored copies remain server-local and separate from live stores. */
export class LpbfRunBundleService {
  private readonly runRoot: string;
  private readonly sourceRoot: string;
  private readonly bundleRoot: string;

  constructor(
    runRoot = process.env.METALLIKSA_LPBF_RUN_ROOT || '.lpbf-runs',
    sourceRoot = process.env.METALLIKSA_LPBF_SOURCE_ROOT || '.lpbf-sources',
    bundleRoot = process.env.METALLIKSA_LPBF_BUNDLE_ROOT || '.lpbf-run-bundles',
    private readonly newId: () => string = () => randomUUID().replaceAll('-', ''),
  ) {
    this.runRoot = path.resolve(runRoot);
    this.sourceRoot = path.resolve(sourceRoot);
    this.bundleRoot = path.resolve(bundleRoot);
    if ([this.runRoot, this.sourceRoot].some(root => overlaps(root, this.bundleRoot) || overlaps(this.bundleRoot, root))) {
      throw new Error('Bundle root must be separate from live LPBF stores');
    }
  }

  private id(value: string): string {
    if (!ID.test(value)) throw new LpbfRunArchiveError(400, 'Invalid bundle ID.');
    return value;
  }

  private directory(kind: 'exports' | 'imports' | 'restores', create: boolean): string {
    return artifactDirectory(path.join(this.bundleRoot, kind), create);
  }

  private exported(bundleId: string): string {
    const id = this.id(bundleId);
    if (!existsSync(path.join(this.bundleRoot, 'exports'))) throw new LpbfRunArchiveError(404, 'Run bundle not found.');
    const target = path.join(this.directory('exports', false), id);
    if (!existsSync(target)) throw new LpbfRunArchiveError(404, 'Run bundle not found.');
    return target;
  }

  private imported(bundleId: string): string {
    const id = this.id(bundleId);
    if (!existsSync(path.join(this.bundleRoot, 'imports'))) throw new LpbfRunArchiveError(404, 'Imported run bundle not found.');
    const target = path.join(this.directory('imports', false), id);
    if (!existsSync(target)) throw new LpbfRunArchiveError(404, 'Imported run bundle not found.');
    return target;
  }

  async export() {
    const bundleId = this.id(this.newId());
    const target = path.join(this.directory('exports', true), bundleId);
    if (existsSync(target)) throw new LpbfRunArchiveError(409, 'Run bundle ID already exists.');
    const runRoot = artifactDirectory(this.runRoot);
    const sourceRoot = artifactDirectory(this.sourceRoot);
    const runs = new LpbfRunRepository(path.join(runRoot, 'runs.sqlite'), { readOnly: true });
    try {
      const sources = new LpbfSourceRepository(path.join(sourceRoot, 'metadata.sqlite'), { readOnly: true });
      try {
        await backupRunBundle(runs, new LpbfArtifactStore(path.join(runRoot, 'artifacts'), { readOnly: true }),
          sources, new LpbfArtifactStore(path.join(sourceRoot, 'artifacts'), { readOnly: true }), target);
      } finally { sources.close(); }
    } finally { runs.close(); }
    const manifest = await verifyRunBundle(target);
    return { bundleId, storage: 'server-local-directory' as const, manifest };
  }

  async verify(bundleId: string) {
    const target = this.exported(bundleId);
    try {
      const manifest = await verifyRunBundle(target);
      return { bundleId, storage: 'server-local-directory' as const, verified: true, manifest };
    } catch (error) {
      throw new LpbfRunArchiveError(409, safeBundleError(error, 'verify'));
    }
  }

  async download(bundleId: string): Promise<Readable> {
    const source = this.exported(bundleId);
    try { await verifyRunBundle(source); }
    catch (error) { throw new LpbfRunArchiveError(409, safeBundleError(error, 'verify')); }
    return createRunBundleTar(source);
  }

  async importPortable(stream: Readable) {
    const importId = this.id(this.newId());
    const destination = path.join(this.directory('imports', true), importId);
    if (existsSync(destination)) throw new LpbfRunArchiveError(409, 'Imported bundle ID already exists.');
    let extracted = false;
    try {
      await extractRunBundleTar(stream, destination);
      extracted = true;
      const manifest = await verifyRunBundle(destination);
      return { importId, storage: 'server-local-directory' as const, verified: true as const, manifest };
    } catch (error) {
      // Extraction only creates this newly allocated directory under the isolated bundle root.
      if (extracted) {
        const { rm } = await import('node:fs/promises');
        await rm(destination, { recursive: true, force: true });
      }
      if (error instanceof LpbfRunArchiveError) throw error;
      throw new LpbfRunArchiveError(409, safeBundleError(error, 'import'));
    }
  }

  async restoreImported(bundleId: string) {
    const source = this.imported(bundleId);
    return this.restoreFrom(source);
  }

  private async restoreFrom(source: string) {
    try { await verifyRunBundle(source); }
    catch (error) { throw new LpbfRunArchiveError(409, safeBundleError(error, 'restore')); }
    const restoreId = this.id(this.newId());
    const destination = path.join(this.directory('restores', true), restoreId);
    if (existsSync(destination)) throw new LpbfRunArchiveError(409, 'Restore ID already exists.');
    try {
      await restoreRunBundle(source, destination);
      const manifest = await verifyRunBundle(destination);
      return { bundleId: path.basename(source), restoreId, storage: 'server-local-directory' as const, verified: true as const, manifest };
    } catch (error) {
      throw new LpbfRunArchiveError(409, safeBundleError(error, 'restore'));
    }
  }

  async restore(bundleId: string) {
    const source = this.exported(bundleId);
    return this.restoreFrom(source);
  }

  async listRestoredRuns(restoreId: string) {
    const root = this.restored(restoreId);
    try { await verifyRunBundle(root); }
    catch { throw new LpbfRunArchiveError(409, 'Restored run bundle integrity verification failed.'); }
    const repository = new LpbfRunRepository(path.join(root, 'runs.sqlite'), { readOnly: true });
    try { return [...repository.allRuns()].map(record => ({ runId: record.document.runId, createdAt: record.createdAt,
      evidenceStatus: record.evidenceStatus, sourceBindingStatus: record.document.sources.length ? 'exact-revision-bound' as const : 'legacy-unlinked' as const,
      runKind: record.runKind })); }
    finally { repository.close(); }
  }

  async getRestoredRun(restoreId: string, runId: string) {
    const root = this.restored(restoreId);
    try { await verifyRunBundle(root); }
    catch { throw new LpbfRunArchiveError(409, 'Restored run bundle integrity verification failed.'); }
    const repository = new LpbfRunRepository(path.join(root, 'runs.sqlite'), { readOnly: true });
    try {
      const record = repository.get(runId);
      if (!record) throw new LpbfRunArchiveError(404, 'Restored run not found.');
      return { ...record, sourceBindingStatus: record.document.sources.length ? 'exact-revision-bound' as const : 'legacy-unlinked' as const };
    } finally { repository.close(); }
  }

  async restoredComparisonRoots(restoreId: string) {
    const runRoot = this.restored(restoreId);
    try { await verifyRunBundle(runRoot); }
    catch { throw new LpbfRunArchiveError(409, 'Restored run bundle integrity verification failed.'); }
    return { runRoot, sourceRoot: path.join(runRoot, 'sources') };
  }

  private restored(restoreId: string): string {
    const id = this.id(restoreId);
    if (!existsSync(path.join(this.bundleRoot, 'restores'))) throw new LpbfRunArchiveError(404, 'Restored run bundle not found.');
    const target = path.join(this.directory('restores', false), id);
    if (!existsSync(target)) throw new LpbfRunArchiveError(404, 'Restored run bundle not found.');
    return target;
  }
}
