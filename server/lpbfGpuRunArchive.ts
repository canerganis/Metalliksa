/** Integrity and numerical evidence gate for a bound GPU-pilot archive. */
import { PARITY_TARGETS, validateGpuPilotNumerics } from './lpbfGpuPilotNumerics';
import { readGpuPilotArtifactsFromManifest, type GpuPilotArtifactResolver } from './lpbfGpuPilotArtifacts';
import { validateGpuPilotRunIdentity } from './lpbfGpuRunIdentity';
import { parseGpuPilotJob } from '../src/services/lpbfSimulationService';

export function validateGpuPilotArchiveMetadata(result: unknown, runId: string) {
  validateGpuPilotRunIdentity(result);
  if (!result || typeof result !== 'object' || Array.isArray(result)) throw new Error('Invalid GPU pilot archive result');
  const value = result as Record<string, unknown>;
  const settings = value.settings;
  if (!settings || typeof settings !== 'object' || Array.isArray(settings)) throw new Error('Invalid GPU pilot settings');
  const parsed = settings as Record<string, unknown>;
  parseGpuPilotJob({ id: runId, status: 'completed', progress: 1, log: '', error: null,
    requestSummary: { jobType: 'gpu-thermal-pilot', backend: parsed.backend, mode: parsed.mode,
      material: parsed.material, ...(parsed.executionEngine === 'warp' ? { executionEngine: 'warp' } : {}) }, result: value });
  return value;
}

export async function verifyGpuPilotArchive(result: unknown, runId: string, resolve: GpuPilotArtifactResolver) {
  const value = validateGpuPilotArchiveMetadata(result, runId);
  const decoded = await readGpuPilotArtifactsFromManifest(value.artifacts, value.gpuFieldArtifacts, resolve);
  return validateGpuPilotNumerics(value, decoded, PARITY_TARGETS);
}
