/** Read exact numerical artifacts; this is integrity verification, not validation. */
import { createHash } from 'node:crypto';
import { open } from 'node:fs/promises';
import { artifactRelativePath, LpbfArtifactStore, verifyLocalArtifact, type ArtifactIdentity } from './lpbfArtifactStore';
import { GPU_ARTIFACT_UNITS, parseGpuPilotArtifactDescriptor,
  type GpuArtifactQuantity, type GpuArtifactState } from '../src/types/lpbfGpuArtifacts';

export interface ReadGpuPilotState {
  metadata: GpuArtifactState;
  arrays: Record<GpuArtifactQuantity, Float64Array>;
}

export interface GpuPilotManifestEntry extends ArtifactIdentity { path: string }
export type GpuPilotArtifactResolver = (entry: GpuPilotManifestEntry) => Promise<string>;
const MAX_MANIFEST_FILES = 10_000;
const MAX_MANIFEST_BYTES = 256 * 1024 * 1024;

/** Validate the complete bound manifest; field refs are a subset, not the whole archive. */
export function validateGpuPilotManifest(raw: unknown, descriptorRaw: unknown): Map<string, GpuPilotManifestEntry> {
  if (!Array.isArray(raw) || raw.length < 1 || raw.length > MAX_MANIFEST_FILES) throw new Error('Invalid GPU archive manifest count');
  const descriptor = parseGpuPilotArtifactDescriptor(descriptorRaw);
  const byExactPath = new Map<string, GpuPilotManifestEntry>(), folded = new Set<string>();
  let total = 0;
  for (const item of raw) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) throw new Error('Invalid GPU archive manifest entry');
    const entry = item as Record<string, unknown>;
    if (Object.keys(entry).length !== 3 || !Object.hasOwn(entry, 'path') || !Object.hasOwn(entry, 'sha256')
      || !Object.hasOwn(entry, 'size_bytes') || typeof entry.path !== 'string'
      || typeof entry.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(entry.sha256)
      || !Number.isSafeInteger(entry.size_bytes) || (entry.size_bytes as number) < 0) throw new Error('Invalid GPU archive manifest entry');
    const relative = artifactRelativePath(entry.path);
    const lower = relative.toLocaleLowerCase('en-US');
    if (folded.has(lower)) throw new Error('Duplicate GPU archive manifest path');
    folded.add(lower);
    total += entry.size_bytes as number;
    if (!Number.isSafeInteger(total) || total > MAX_MANIFEST_BYTES) throw new Error('GPU archive manifest exceeds byte budget');
    byExactPath.set(relative, { path: relative, sha256: entry.sha256, byteSize: entry.size_bytes as number });
  }
  for (const backend of ['cpu', 'gpu'] as const) {
    for (const ref of Object.values(descriptor.states[backend].fields)) {
      const found = byExactPath.get(ref.path);
      if (!found || found.sha256 !== ref.sha256 || found.byteSize !== ref.size_bytes) {
        throw new Error('GPU field reference is detached from the complete manifest');
      }
    }
  }
  return byExactPath;
}

export function localGpuPilotArtifactResolver(root: string): GpuPilotArtifactResolver {
  return async entry => (await verifyLocalArtifact(root, entry.path, entry)).path;
}

export function storeGpuPilotArtifactResolver(store: LpbfArtifactStore): GpuPilotArtifactResolver {
  return async entry => (await store.verify(entry)).path;
}

function ulp(value: number): number {
  const buffer = new ArrayBuffer(8), view = new DataView(buffer);
  view.setFloat64(0, value);
  const exponent = (view.getUint32(0) >>> 20) & 0x7ff;
  return exponent === 0 ? Number.MIN_VALUE : 2 ** (exponent - 1023 - 52);
}

/** Read only the declared byte budget, even if a verified file subsequently grows. */
export async function readGpuPilotArtifactBytes(filename: string, ref: ArtifactIdentity): Promise<Buffer> {
  if (!Number.isSafeInteger(ref.byteSize) || ref.byteSize < 0 || ref.byteSize > 50 * 1024 * 1024
    || !/^[a-f0-9]{64}$/.test(ref.sha256)) throw new Error('Invalid GPU pilot artifact byte budget');
  const file = await open(filename, 'r');
  try {
    const before = await file.stat();
    if (!before.isFile() || before.size !== ref.byteSize) throw new Error('GPU pilot artifact size changed before decoding');
    const bytes = Buffer.alloc(ref.byteSize);
    let received = 0;
    while (received < bytes.length) {
      const { bytesRead } = await file.read(bytes, received, bytes.length - received, null);
      if (!bytesRead) break;
      received += bytesRead;
    }
    const extra = await file.read(Buffer.alloc(1), 0, 1, null);
    const after = await file.stat();
    if (received !== ref.byteSize || extra.bytesRead || after.size !== ref.byteSize
      || after.mtimeMs !== before.mtimeMs || createHash('sha256').update(bytes).digest('hex') !== ref.sha256) {
      throw new Error('GPU pilot artifact bytes changed during decoding');
    }
    return bytes;
  } finally { await file.close(); }
}

export async function readGpuPilotArtifacts(root: string, raw: unknown): Promise<Record<'cpu' | 'gpu', ReadGpuPilotState>> {
  return readGpuPilotArtifactsUsing(raw, localGpuPilotArtifactResolver(root));
}

/** Resolve archive objects through one shared resolver, then bind the second bounded read to its hash. */
export async function readGpuPilotArtifactsFromManifest(
  manifest: unknown, rawDescriptor: unknown, resolve: GpuPilotArtifactResolver
): Promise<Record<'cpu' | 'gpu', ReadGpuPilotState>> {
  const refs = validateGpuPilotManifest(manifest, rawDescriptor);
  return readGpuPilotArtifactsUsing(rawDescriptor, async requested => {
    const entry = refs.get(requested.path);
    if (!entry || entry.sha256 !== requested.sha256 || entry.byteSize !== requested.byteSize) {
      throw new Error('GPU field reference does not exactly match manifest path');
    }
    return resolve(entry);
  });
}

async function readGpuPilotArtifactsUsing(raw: unknown, resolve: GpuPilotArtifactResolver): Promise<Record<'cpu' | 'gpu', ReadGpuPilotState>> {
  const descriptor = structuredClone(parseGpuPilotArtifactDescriptor(raw));
  const result = {} as Record<'cpu' | 'gpu', ReadGpuPilotState>;
  for (const backend of ['cpu', 'gpu'] as const) {
    const metadata = descriptor.states[backend];
    const arrays = {} as Record<GpuArtifactQuantity, Float64Array>;
    for (const quantity of Object.keys(GPU_ARTIFACT_UNITS) as GpuArtifactQuantity[]) {
      const ref = metadata.fields[quantity];
      const identity = { sha256: ref.sha256, byteSize: ref.size_bytes };
      const resolvedPath = await resolve({ path: ref.path, ...identity });
      const bytes = await readGpuPilotArtifactBytes(resolvedPath, identity);
      const values = new Float64Array(bytes.length / 8);
      for (let i = 0; i < values.length; i++) {
        const value = bytes.readDoubleLE(i * 8);
        if (!Number.isFinite(value) || (['temperature_K', 'density_kg_m3', 'accepted_dt_s'].includes(quantity) && value <= 0)) {
          throw new Error(`Invalid GPU pilot ${quantity} value`);
        }
        values[i] = value;
      }
      arrays[quantity] = values;
    }
    // Replay the recorded model clock in accepted-step order. A compensated sum
    // has different accumulated rounding and cannot be checked using only the
    // solver's final endpoint-snap allowance. Never modify recorded dt values.
    let elapsed = 0;
    for (const dt of arrays.accepted_dt_s) {
      const next = elapsed + dt;
      if (elapsed >= metadata.time_s || next <= elapsed) {
        throw new Error('GPU pilot accepted timestep does not advance the unfinished model clock');
      }
      elapsed = next;
    }
    const allowance = Math.min(1e-14, 2 * ulp(metadata.time_s) * metadata.steps);
    if (!Number.isFinite(elapsed) || Math.abs(elapsed - metadata.time_s) > allowance) {
      throw new Error('GPU pilot accepted timestep sum does not match final time');
    }
    result[backend] = { metadata, arrays };
  }
  return result;
}
