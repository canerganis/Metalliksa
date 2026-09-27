/** Historical, bounded identity checks for a captured CUDA thermal-pilot result. */
import { createHash } from 'node:crypto';
import { parseBoundedJson, strictJsonEqual, type BoundedJsonDocument } from './lpbfBoundJson';

const SHA = /^[a-f0-9]{64}$/;
const CORE_MODEL = 'stationary-enthalpy-conduction-layer-conforming-v1';
const CORE_UNITS = { power: 'W', speed: 'mm/s', length: 'um', preheat: 'degC', temperature: 'K',
  internalLength: 'm', time: 's', energy: 'J', beamDiameter: '1/e2-intensity' };
const CORE_PHYSICS = { conduction: true, transient: true, latentHeat: true, momentum: false,
  freeSurface: false, evaporation: false };
const HASH_KEYS = ['requestHash', 'materialHash', 'cpuInputHash', 'cpuResolvedSettingsHash', 'implementationHash'];
const INPUT_KEYS = ['requestJson', 'materialJson', 'cpuInputJson', 'cpuResolvedSettingsJson'];

function record(value: unknown, name: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`Invalid GPU archive ${name}`);
  return value as Record<string, unknown>;
}
function exactKeys(value: Record<string, unknown>, keys: readonly string[], name: string) {
  if (Object.keys(value).length !== keys.length || keys.some(key => !Object.hasOwn(value, key))) {
    throw new Error(`Invalid GPU archive ${name} shape`);
  }
}
function hash(value: unknown, name: string): asserts value is string {
  if (typeof value !== 'string' || !SHA.test(value)) throw new Error(`Invalid GPU archive ${name}`);
}
function digest(value: string): string { return createHash('sha256').update(Buffer.from(value, 'utf8')).digest('hex'); }
function requireSame(a: unknown, b: unknown, message: string) {
  if (!strictJsonEqual(a, b)) throw new Error(message);
}
function parseInput(value: unknown, hashes: Record<string, unknown>, inputKey: string, hashKey: string): BoundedJsonDocument {
  if (typeof value !== 'string') throw new Error(`Missing GPU archive ${inputKey}`);
  const expected = hashes[hashKey]; hash(expected, hashKey);
  if (digest(value) !== expected) throw new Error(`GPU archive ${inputKey} hash mismatch`);
  return parseBoundedJson(value);
}

export interface GpuPilotRunIdentity {
  request: Record<string, unknown>;
  material: Record<string, unknown>;
  cpuInput: Record<string, unknown>;
  cpuResolvedSettings: Record<string, unknown>;
  hashes: Record<string, string>;
}

/** Validates only recorded identities. It deliberately does not consult today's registries or defaults. */
export function validateGpuPilotRunIdentity(value: unknown): GpuPilotRunIdentity {
  const result = record(value, 'result');
  if (result.jobType !== 'gpu-thermal-pilot' || result.schemaVersion !== 1 || Object.hasOwn(result, 'coreContract')
    || result.requestedMode !== 'standard' || result.effectiveMode !== 'gpu-pilot'
    || result.validationStatus !== 'unvalidated' || result.productionReady !== false
    || typeof result.label !== 'string' || !result.label.trim()) {
    throw new Error('Invalid bound GPU archive result');
  }
  const contract = record(result.gpuRunContract, 'run contract');
  exactKeys(contract, ['schemaVersion', 'runKind', 'capture', 'serializedInputs', 'hashes'], 'run contract');
  if (contract.schemaVersion !== 1 || contract.runKind !== 'gpu-thermal-pilot') throw new Error('Unsupported GPU run contract');
  const capture = record(contract.capture, 'capture binding');
  exactKeys(capture, ['contractStatus', 'modelId', 'backend', 'device', 'dtype'], 'capture binding');
  const solver = record(result.solver, 'solver');
  const settings = record(result.settings, 'settings');
  const provenance = record(result.provenance, 'provenance');
  const evidence = record(provenance.deviceEvidence, 'device evidence');
  if (capture.contractStatus !== 'gpu-pilot-v1-bound' || capture.modelId !== CORE_MODEL
    || typeof capture.backend !== 'string' || !/^cuda:\d+$/.test(capture.backend)
    || capture.backend !== settings.backend || capture.backend !== solver.actualBackend
    || capture.backend !== evidence.selected || capture.backend !== evidence.thermalEvolution
    || capture.backend !== capture.device || capture.dtype !== 'float64'
    || solver.id !== 'enthalpy-fv-6-cuda-pilot-1' || solver.dtype !== 'float64' || solver.modelId !== CORE_MODEL
    || solver.thermalEvolutionDevice !== capture.backend) throw new Error('GPU run capture binding mismatch');

  const serialized = record(contract.serializedInputs, 'serialized inputs');
  exactKeys(serialized, INPUT_KEYS, 'serialized inputs');
  const hashesRaw = record(contract.hashes, 'hashes');
  exactKeys(hashesRaw, HASH_KEYS, 'hashes');
  for (const key of HASH_KEYS) hash(hashesRaw[key], key);
  const hashes = hashesRaw as Record<string, string>;
  if (hashes.implementationHash !== provenance.implementationHash
    || hashes.requestHash !== provenance.inputHash
    || provenance.materialVersion !== record(result.material, 'material').version
    || typeof provenance.createdAt !== 'string' || !Number.isFinite(Date.parse(provenance.createdAt))) {
    throw new Error('GPU archived provenance is detached from input hashes');
  }
  if (typeof evidence.name !== 'string' || !evidence.name.trim() || typeof evidence.torch !== 'string' || !evidence.torch.trim()
    || typeof evidence.cudaRuntime !== 'string' || !evidence.cudaRuntime.trim()
    || !Array.isArray(evidence.computeCapability) || evidence.computeCapability.length !== 2
    || evidence.computeCapability.some(value => !Number.isSafeInteger(value) || (value as number) < 0)
    || evidence.synchronizedAfterSolve !== true || typeof evidence.sourceIntegration !== 'string' || !evidence.sourceIntegration
    || typeof evidence.sourceTimestepLimiter !== 'string' || !evidence.sourceTimestepLimiter) {
    throw new Error('Invalid GPU archived device evidence');
  }
  const requestDoc = parseInput(serialized.requestJson, hashes, 'requestJson', 'requestHash');
  const materialDoc = parseInput(serialized.materialJson, hashes, 'materialJson', 'materialHash');
  const cpuInputDoc = parseInput(serialized.cpuInputJson, hashes, 'cpuInputJson', 'cpuInputHash');
  const cpuResolvedDoc = parseInput(serialized.cpuResolvedSettingsJson, hashes, 'cpuResolvedSettingsJson', 'cpuResolvedSettingsHash');
  const request = record(requestDoc.value, 'request snapshot');
  const material = record(materialDoc.value, 'material snapshot');
  const cpuInput = record(cpuInputDoc.value, 'CPU input snapshot');
  const cpuResolvedSettings = record(cpuResolvedDoc.value, 'resolved CPU settings');
  requireSame(request, settings, 'GPU request snapshot differs from executed settings');
  requireSame(material, result.material, 'GPU material snapshot differs from executed material');
  const expectedCpuInput = { ...request };
  delete expectedCpuInput.jobType;
  expectedCpuInput.backend = 'reference';
  requireSame(cpuInput, expectedCpuInput, 'GPU CPU reference input is detached from request');
  requireSame(cpuResolvedSettings, cpuInput, 'GPU CPU resolved settings are not the captured fixed point');

  const revision = material.materialRevisionSha256;
  hash(revision, 'material revision');
  if (digest(materialDoc.pythonCompactJson({ omitTopLevelKey: 'materialRevisionSha256' })) !== revision) {
    throw new Error('GPU archived material revision hash mismatch');
  }
  const cpu = record(record(result.gpuPilot, 'parity summary').cpu, 'CPU summary');
  const core = record(cpu.coreContract, 'nested CPU core contract');
  const requiredCore = ['schemaVersion', 'modelId', 'actualBackend', 'requestedBackend', 'effectiveMode', 'solverId',
    'inputSha256', 'materialSha256', 'units', 'resolvedPhysics', 'evidenceClass'];
  exactKeys(core, requiredCore, 'nested CPU core contract');
  if (core.schemaVersion !== 1 || core.modelId !== CORE_MODEL || core.actualBackend !== 'numpy-reference'
    || core.requestedBackend !== 'reference' || core.effectiveMode !== 'standard' || core.solverId !== 'enthalpy-fv-6'
    || core.evidenceClass !== 'unvalidated-model' || !strictJsonEqual(core.units, CORE_UNITS)
    || !strictJsonEqual(core.resolvedPhysics, CORE_PHYSICS)) throw new Error('GPU nested CPU model contract mismatch');
  if (digest(cpuResolvedDoc.pythonCompactJson()) !== core.inputSha256
    || digest(materialDoc.pythonCompactJson()) !== core.materialSha256) throw new Error('GPU nested CPU core hash mismatch');
  const cpuSolver = record(cpu.solver, 'CPU solver');
  if (cpuSolver.id !== core.solverId) throw new Error('GPU nested CPU solver id mismatch');
  const cpuMaterial = record(cpu.material, 'CPU material summary');
  for (const key of ['name', 'materialId', 'materialRevisionSha256', 'version']) {
    if (cpuMaterial[key] !== material[key]) throw new Error(`GPU CPU material ${key} mismatch`);
  }
  requireSame(cpu.resolvedSettings, cpuResolvedSettings, 'GPU CPU resolved summary detached from captured inputs');
  return { request, material, cpuInput, cpuResolvedSettings, hashes };
}
