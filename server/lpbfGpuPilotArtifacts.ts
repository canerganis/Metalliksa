/** Read exact numerical artifacts; this is integrity verification, not validation. */
import { createHash } from 'node:crypto';
import { open } from 'node:fs/promises';
import { verifyLocalArtifact, type ArtifactIdentity } from './lpbfArtifactStore';
import { GPU_ARTIFACT_UNITS, parseGpuPilotArtifactDescriptor,
  type GpuArtifactQuantity, type GpuArtifactState } from '../src/types/lpbfGpuArtifacts';

export interface ReadGpuPilotState {
  metadata: GpuArtifactState;
  arrays: Record<GpuArtifactQuantity, Float64Array>;
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
  const descriptor = structuredClone(parseGpuPilotArtifactDescriptor(raw));
  const result = {} as Record<'cpu' | 'gpu', ReadGpuPilotState>;
  for (const backend of ['cpu', 'gpu'] as const) {
    const metadata = descriptor.states[backend];
    const arrays = {} as Record<GpuArtifactQuantity, Float64Array>;
    for (const quantity of Object.keys(GPU_ARTIFACT_UNITS) as GpuArtifactQuantity[]) {
      const ref = metadata.fields[quantity];
      const verified = await verifyLocalArtifact(root, ref.path, { sha256: ref.sha256, byteSize: ref.size_bytes });
      const bytes = await readGpuPilotArtifactBytes(verified.path, { sha256: ref.sha256, byteSize: ref.size_bytes });
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
