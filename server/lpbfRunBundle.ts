/** Full immutable run/source archive. Integrity is not scientific validation.
 * All paths are trusted server configuration; no live restore or HTTP paths.
 */
import { createHash } from 'node:crypto';
import { createReadStream, lstatSync, readFileSync, readdirSync } from 'node:fs';
import { open } from 'node:fs/promises';
import path from 'node:path';
import { artifactDirectory, LpbfArtifactStore, verifyLocalArtifact, type ArtifactIdentity } from './lpbfArtifactStore';
import { LpbfRunRepository } from './lpbfRunRepository';
import { runArtifacts } from './lpbfRunImport';
import { LpbfSourceRepository } from './lpbfSourceRepository';
import { backupSourceBundle, verifySourceBundle } from './lpbfSourceBundle';
import { storeGpuPilotArtifactResolver } from './lpbfGpuPilotArtifacts';
import { verifyGpuPilotArchive } from './lpbfGpuRunArchive';

export interface RunBundleManifest {
  schemaVersion: 1 | 2;
  kind: 'metalliksa-lpbf-run-bundle';
  metadata: ArtifactIdentity;
  sourceBundle: ArtifactIdentity;
  runCount: number;
  artifactCount: number;
  sourceLinkCount: number;
  campaignCount?: number;
}

async function fileIdentity(root: string, relative: string): Promise<ArtifactIdentity> {
  artifactDirectory(path.dirname(path.join(root, relative)));
  const filename = path.join(root, relative), stat = lstatSync(filename);
  if (stat.isSymbolicLink() || !stat.isFile()) throw new Error('Bundle file must not be a link');
  const hash = createHash('sha256'); let byteSize = 0;
  for await (const bytes of createReadStream(filename)) { hash.update(bytes); byteSize += bytes.length; }
  const ref = { sha256: hash.digest('hex'), byteSize };
  await verifyLocalArtifact(root, relative, ref);
  return ref;
}

function noSidecars(root: string) {
  for (const suffix of ['-wal', '-shm', '-journal']) {
    try { lstatSync(path.join(root, `runs.sqlite${suffix}`)); }
    catch (error) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') continue; throw error; }
    throw new Error('Bundle SQLite sidecar state is not permitted');
  }
}

function readManifest(root: string): RunBundleManifest {
  const file = path.join(root, 'bundle.json'), stat = lstatSync(file);
  if (stat.isSymbolicLink() || !stat.isFile() || stat.size > 16384) throw new Error('Invalid run bundle manifest file');
  const m = JSON.parse(readFileSync(file, 'utf8'));
  const fields = Object.keys(m ?? {}).sort().join();
  if (!m || ![1, 2].includes(m.schemaVersion) || m.kind !== 'metalliksa-lpbf-run-bundle'
    || fields !== (m.schemaVersion === 1
      ? 'artifactCount,kind,metadata,runCount,schemaVersion,sourceBundle,sourceLinkCount'
      : 'artifactCount,campaignCount,kind,metadata,runCount,schemaVersion,sourceBundle,sourceLinkCount')
    || [m.runCount, m.artifactCount, m.sourceLinkCount, ...(m.schemaVersion === 2 ? [m.campaignCount] : [])]
      .some(n => !Number.isSafeInteger(n) || n < 0)) {
    throw new Error('Invalid run bundle manifest');
  }
  return m as RunBundleManifest;
}

/** Read ONLY frozen databases. A newer current revision never substitutes for a link. */
function references(root: string) {
  const runs = new LpbfRunRepository(path.join(root, 'runs.sqlite'), { readOnly: true });
  try {
    const sources = new LpbfSourceRepository(path.join(root, 'sources/metadata.sqlite'), { readOnly: true });
    try {
      const artifacts = new Map<string, ArtifactIdentity>();
      const sourceArtifacts = new Map<string, ArtifactIdentity>();
      // The source snapshot includes every frozen revision, not just run links.
      for (const revision of sources.allRevisions()) {
        for (const ref of revision.document.artifacts) {
          const prior = sourceArtifacts.get(ref.sha256);
          if (prior && prior.byteSize !== ref.byteSize) throw new Error('Conflicting source artifact sizes');
          sourceArtifacts.set(ref.sha256, { sha256: ref.sha256, byteSize: ref.byteSize });
        }
      }
      let runCount = 0, sourceLinkCount = 0;
      const gpuResults: { runId: string; result: unknown }[] = [];
      for (const record of runs.allRuns()) {
        runCount++;
        if (record.runKind === 'gpu-thermal-pilot') gpuResults.push({ runId: record.document.runId,
          result: JSON.parse(record.document.capture.resultJson) });
        for (const link of record.document.sources) {
          const revision = sources.revision(link.datasetId, link.revision);
          if (!revision || revision.documentSha256 !== link.documentSha256) throw new Error('Run source revision identity mismatch');
          sourceLinkCount++;
        }
        for (const ref of runArtifacts(record.document)) {
          const prior = artifacts.get(ref.sha256);
          if (prior && prior.byteSize !== ref.byteSize) throw new Error('Conflicting run artifact sizes');
          artifacts.set(ref.sha256, { sha256: ref.sha256, byteSize: ref.byteSize });
        }
      }
      let campaignCount = 0;
      for (const campaign of runs.allProxyCampaigns()) {
        campaignCount++;
        for (const track of campaign.document.tracks) {
          const identity = track.runIdentity;
          const referenced = runs.get(identity.runId);
          if (!referenced || referenced.documentSha256 !== identity.runDocumentSha256) {
            throw new Error('Campaign archived run reference mismatch');
          }
          if (!referenced.document.sources.some(link => link.datasetId === campaign.document.sourceBinding?.datasetId
            && link.revision === campaign.document.sourceBinding?.revision
            && link.documentSha256 === campaign.document.sourceBinding?.documentSha256)) {
            throw new Error('Campaign exact source revision is not bound by its archived run');
          }
        }
      }
      return { artifacts, sourceArtifacts, runCount, sourceLinkCount, campaignCount, gpuResults };
    } finally { sources.close(); }
  } finally { runs.close(); }
}

function verifyInventory(root: string, refs: ReturnType<typeof references>, completed: boolean) {
  const expected = new Set(['runs.sqlite', 'sources/metadata.sqlite', 'sources/bundle.json']);
  if (completed) expected.add('bundle.json');
  for (const [prefix, artifacts] of [['artifacts', refs.artifacts], ['sources/artifacts', refs.sourceArtifacts]] as const) {
    for (const ref of artifacts.values()) expected.add(`${prefix}/objects/${ref.sha256.slice(0, 2)}/${ref.sha256}`);
  }
  const visit = (relative: string) => {
    const directory = artifactDirectory(path.join(root, relative), false);
    for (const name of readdirSync(directory)) {
      const item = relative ? `${relative}/${name}` : name;
      const stat = lstatSync(path.join(root, item));
      if (stat.isSymbolicLink()) throw new Error('Bundle inventory contains a link');
      if (stat.isDirectory()) visit(item); // Empty staging/object directories carry no payload.
      else if (!stat.isFile()) throw new Error('Bundle inventory contains a non-regular file');
      else if (!expected.delete(item)) throw new Error(`Unexpected file in bundle inventory: ${item}`);
    }
  };
  visit('');
  if (expected.size) throw new Error('Bundle inventory is missing expected files');
}

async function verifyContents(root: string, manifest: RunBundleManifest, completed = true) {
  noSidecars(root);
  await verifyLocalArtifact(root, 'runs.sqlite', manifest.metadata);
  await verifyLocalArtifact(root, 'sources/bundle.json', manifest.sourceBundle);
  await verifySourceBundle(path.join(root, 'sources'));
  const refs = references(root);
  if (refs.runCount !== manifest.runCount || refs.sourceLinkCount !== manifest.sourceLinkCount
    || refs.artifacts.size !== manifest.artifactCount
    || (manifest.schemaVersion === 2 && refs.campaignCount !== manifest.campaignCount)
    || (manifest.schemaVersion === 1 && refs.campaignCount !== 0)) throw new Error('Run bundle metadata counts mismatch');
  const store = new LpbfArtifactStore(path.join(root, 'artifacts'), { readOnly: true });
  for (const ref of refs.artifacts.values()) await store.verify(ref);
  const resolver = storeGpuPilotArtifactResolver(store);
  for (const item of refs.gpuResults) await verifyGpuPilotArchive(item.result, item.runId, resolver);
  verifyInventory(root, refs, completed);
}

/** Snapshot runs first, then sources. Includes the full source snapshot as a superset
 * of exact referenced revisions. Failure leaves no top-level completion manifest.
 */
export async function backupRunBundle(runs: LpbfRunRepository, runStore: LpbfArtifactStore,
  sources: LpbfSourceRepository, sourceStore: LpbfArtifactStore, destination: string): Promise<RunBundleManifest> {
  const absolute = path.resolve(destination);
  const parent = artifactDirectory(path.dirname(absolute));
  const target = path.join(parent, path.basename(absolute));
  await runs.backupMetadata(target); // exclusive mkdir; preserves original row bytes/timestamps
  await backupSourceBundle(sources, sourceStore, path.join(target, 'sources'));
  const refs = references(target);
  const output = new LpbfArtifactStore(path.join(target, 'artifacts'));
  for (const ref of refs.artifacts.values()) {
    const input = await runStore.verify(ref);
    await output.putFile(runStore.root, path.relative(runStore.root, input.path).split(path.sep).join('/'), ref);
  }
  const manifest: RunBundleManifest = { schemaVersion: 2, kind: 'metalliksa-lpbf-run-bundle',
    metadata: await fileIdentity(target, 'runs.sqlite'), sourceBundle: await fileIdentity(target, 'sources/bundle.json'),
    runCount: refs.runCount, artifactCount: refs.artifacts.size, sourceLinkCount: refs.sourceLinkCount,
    campaignCount: refs.campaignCount };
  await verifyContents(target, manifest, false);
  const completion = await open(path.join(target, 'bundle.json'), 'wx', 0o600);
  try { await completion.writeFile(JSON.stringify(manifest, null, 2)); await completion.sync(); }
  finally { await completion.close(); }
  return manifest;
}

export async function verifyRunBundle(directory: string): Promise<RunBundleManifest> {
  const root = artifactDirectory(directory), manifest = readManifest(root);
  await verifyContents(root, manifest);
  return manifest;
}

/** Validate before creating the exclusive target. All copied bytes rechecked before
 * its completion; no restoration over a live store, no delete or metadata upgrade.
 */
export async function restoreRunBundle(directory: string, destination: string): Promise<RunBundleManifest> {
  await verifyRunBundle(directory);
  const root = artifactDirectory(directory);
  const runs = new LpbfRunRepository(path.join(root, 'runs.sqlite'), { readOnly: true });
  try {
    const sources = new LpbfSourceRepository(path.join(root, 'sources/metadata.sqlite'), { readOnly: true });
    try {
      return await backupRunBundle(runs, new LpbfArtifactStore(path.join(root, 'artifacts'), { readOnly: true }),
        sources, new LpbfArtifactStore(path.join(root, 'sources/artifacts'), { readOnly: true }), destination);
    } finally { sources.close(); }
  } finally { runs.close(); }
}
