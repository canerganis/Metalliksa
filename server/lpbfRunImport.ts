/** Server-internal capture import. Roots must never be supplied by HTTP clients. */
import { lstatSync, readdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { artifactDirectory, LpbfArtifactStore, verifyLocalArtifact } from './lpbfArtifactStore';
import { LpbfSourceRepository } from './lpbfSourceRepository';
import { LpbfRunRepository, validateRunDocument, type RunCapture, type RunDocument, type RunSourceLink } from './lpbfRunRepository';
import { localGpuPilotArtifactResolver, storeGpuPilotArtifactResolver } from './lpbfGpuPilotArtifacts';
import { verifyGpuPilotArchive } from './lpbfGpuRunArchive';

async function verifyGpuRun(document: RunDocument, resolve: Parameters<typeof verifyGpuPilotArchive>[2]) {
  const result = JSON.parse(document.capture.resultJson);
  if (document.capture.runKind === 'gpu-thermal-pilot') await verifyGpuPilotArchive(result, document.runId, resolve);
}

export function runArtifacts(document: RunDocument): { relativePath: string; sha256: string; byteSize: number }[] {
  return JSON.parse(document.capture.resultJson).artifacts.map((a: { path: string; sha256: string; size_bytes: number }) =>
    ({ relativePath: a.path, sha256: a.sha256, byteSize: a.size_bytes }));
}
function verifyResultFile(root: string, document: RunDocument) {
  const bytes = document.capture.resultJson;
  return verifyLocalArtifact(root, 'result.json', {
    sha256: createHash('sha256').update(bytes).digest('hex'), byteSize: Buffer.byteLength(bytes),
  });
}
function sourcesExist(document: RunDocument, sources: LpbfSourceRepository) {
  for (const link of document.sources) {
    const revision = sources.revision(link.datasetId, link.revision);
    if (!revision || revision.documentSha256 !== link.documentSha256) throw new Error('Run source revision identity mismatch');
  }
}
function completeManifest(root: string, document: RunDocument) {
  const base = artifactDirectory(root), actual: string[] = [];
  const visit = (relative: string) => {
    for (const name of readdirSync(path.join(base, relative))) {
      const item = relative ? `${relative}/${name}` : name;
      const stat = lstatSync(path.join(base, item));
      if (stat.isSymbolicLink()) throw new Error('Run manifest contains link');
      if (stat.isDirectory()) visit(item);
      else if (!stat.isFile()) throw new Error('Run manifest contains non-regular file');
      else if (!['result.json', 'result.tmp', 'progress.log'].includes(item)) actual.push(item);
    }
  };
  visit('');
  if (JSON.stringify(actual.sort()) !== JSON.stringify(runArtifacts(document).map(a => a.relativePath).sort())) throw new Error('Run manifest does not cover all output files');
}
export async function dryRunRunImport(capture: RunCapture | unknown, links: RunSourceLink[] | unknown,
  sources: LpbfSourceRepository, root: string) {
  const document = validateRunDocument({ schemaVersion: 1, runId: (capture as RunCapture)?.jobId, capture, sources: links });
  sourcesExist(document, sources); completeManifest(root, document);
  await verifyResultFile(root, document);
  let byteSize = 0;
  for (const ref of runArtifacts(document)) {
    await verifyLocalArtifact(root, ref.relativePath, ref); byteSize += ref.byteSize;
    if (!Number.isSafeInteger(byteSize)) throw new Error('Run artifact size overflow');
  }
  await verifyGpuRun(document, localGpuPilotArtifactResolver(root));
  return { document, artifactCount: runArtifacts(document).length, byteSize, artifactIntegrity: 'verified-at-dry-run' as const };
}
export async function importRun(repository: LpbfRunRepository, store: LpbfArtifactStore,
  capture: RunCapture | unknown, links: RunSourceLink[] | unknown, sources: LpbfSourceRepository, root: string) {
  const preview = await dryRunRunImport(capture, links, sources, root);
  for (const ref of runArtifacts(preview.document)) await store.putFile(root, ref.relativePath, ref);
  for (const ref of runArtifacts(preview.document)) await store.verify(ref);
  sourcesExist(preview.document, sources); completeManifest(root, preview.document);
  await verifyResultFile(root, preview.document);
  await verifyGpuRun(preview.document, storeGpuPilotArtifactResolver(store));
  return repository.save(preview.document);
}
