/** Final spatial fields and accepted steps; these records do not establish validity. */
export const GPU_ARTIFACT_UNITS = {
  coordinates_m: 'm', temperature_K: 'K', enthalpy_J_m3: 'J/m^3',
  density_kg_m3: 'kg/m^3', accepted_dt_s: 's',
} as const;
export type GpuArtifactQuantity = keyof typeof GPU_ARTIFACT_UNITS;
export interface GpuFieldArtifact {
  path: string; shape: number[]; units: string; size_bytes: number; sha256: string;
}
export interface GpuArtifactState {
  cells: number; steps: number; time_s: number;
  initial_temperature_K: number; cell_volume_m3: number;
  fields: Record<GpuArtifactQuantity, GpuFieldArtifact>;
}
export interface GpuPilotArtifactDescriptor {
  schemaVersion: 1;
  kind: 'lpbf-final-field-parity-evidence';
  encoding: 'float64-le'; order: 'C';
  enthalpyReference: 'volumetric-excess-relative-to-initial-temperature';
  states: { cpu: GpuArtifactState; gpu: GpuArtifactState };
}

const invalid = () => new Error('Invalid GPU pilot field artifact descriptor');
function record(value: unknown, fields: readonly string[]): asserts value is Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)
    || Object.keys(value).length !== fields.length
    || fields.some(key => !Object.hasOwn(value, key))) throw invalid();
}
const positive = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value) && value > 0;
const count = (value: unknown, maximum: number): value is number =>
  positive(value) && Number.isSafeInteger(value) && value <= maximum;

/** Validate versioned metadata only. Callers must also verify the artifact bytes. */
export function parseGpuPilotArtifactDescriptor(value: unknown): GpuPilotArtifactDescriptor {
  record(value, ['schemaVersion', 'kind', 'encoding', 'order', 'enthalpyReference', 'states']);
  if (value.schemaVersion !== 1 || value.kind !== 'lpbf-final-field-parity-evidence'
    || value.encoding !== 'float64-le' || value.order !== 'C'
    || value.enthalpyReference !== 'volumetric-excess-relative-to-initial-temperature') throw invalid();
  record(value.states, ['cpu', 'gpu']);
  let total = 0;
  for (const backend of ['cpu', 'gpu'] as const) {
    const state = value.states[backend];
    record(state, ['cells', 'steps', 'time_s', 'initial_temperature_K', 'cell_volume_m3', 'fields']);
    if (!count(state.cells, 100_000) || !count(state.steps, 250_000)
      || !positive(state.time_s) || !positive(state.initial_temperature_K)
      || !positive(state.cell_volume_m3)) throw invalid();
    record(state.fields, Object.keys(GPU_ARTIFACT_UNITS));
    for (const quantity of Object.keys(GPU_ARTIFACT_UNITS) as GpuArtifactQuantity[]) {
      const ref = state.fields[quantity];
      record(ref, ['path', 'shape', 'units', 'size_bytes', 'sha256']);
      const shape = quantity === 'coordinates_m' ? [state.cells, 3]
        : [quantity === 'accepted_dt_s' ? state.steps : state.cells];
      const byteSize = shape.reduce((product, n) => product * n, 8);
      if (ref.path !== `gpu-pilot/${backend}-${quantity}.f64le.bin`
        || ref.units !== GPU_ARTIFACT_UNITS[quantity]
        || !Array.isArray(ref.shape) || ref.shape.length !== shape.length
        || ref.shape.some((n, i) => n !== shape[i]) || ref.size_bytes !== byteSize
        || typeof ref.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(ref.sha256)) throw invalid();
      total += byteSize;
    }
  }
  if (total > 50 * 1024 * 1024) throw invalid();
  // Different grids/step counts are valid records of failed numerical parity.
  // This metadata parser never upgrades their numerical or experimental status.
  return value as unknown as GpuPilotArtifactDescriptor;
}
