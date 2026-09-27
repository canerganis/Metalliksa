/** Pure checks over captured GPU-pilot arrays and their archived summaries. */
import { strictJsonEqual } from './lpbfBoundJson';
import type { ReadGpuPilotState } from './lpbfGpuPilotArtifacts';

const BACKENDS = ['cpu', 'gpu'] as const;
const COMPARISONS = ['finalSampling', 'finalTemperatureField', 'peakTemperature_K', 'input_J', 'losses_J', 'stored_J',
  'width_um', 'depth_um', 'length_um', 'volume_um3'] as const;
const MAX_CELLS = 100_000, MAX_STEPS = 250_000;
export const PARITY_TARGETS = Object.freeze({ integralRelativeMax: .01, widthDepthAbsoluteCellsMax: 1,
  fieldRiseL2RelativeMax: .01, fieldRiseMaxRelativeMax: .01, peakMeltVolumeRelativeMax: .01,
  source: 'docs/DIGITAL_TWIN_MASTER_PLAN_2026-09-21.md#11' });

function fail(message: string): never { throw new Error(message); }
function obj(value: unknown, name: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return fail(`Invalid GPU pilot ${name}`);
  return value as Record<string, unknown>;
}
function num(value: unknown, name: string, kind: 'finite'|'positive'|'nonnegative' = 'finite'): number {
  if (typeof value !== 'number' || !Number.isFinite(value) || (kind === 'positive' && value <= 0)
    || (kind === 'nonnegative' && value < 0)) return fail(`Invalid GPU pilot ${name}`);
  return value;
}
function count(value: unknown, max: number, name: string): number {
  if (!Number.isSafeInteger(value) || (value as number) < 1 || (value as number) > max) return fail(`Invalid GPU pilot ${name}`);
  return value as number;
}
function gamma(k: number): number {
  const product = k * 2 ** -53;
  if (product >= 1) return fail('GPU pilot roundoff bound exceeds float64 support');
  return product / (1 - product);
}
function close(actual: number, expected: number, rel = 1e-12, abs = 0): boolean {
  return Math.abs(actual - expected) <= Math.max(abs, rel * Math.max(Math.abs(actual), Math.abs(expected)));
}
function finiteArray(value: unknown, n: number, name: string, positive = false): Float64Array {
  if (!(value instanceof Float64Array) || value.length !== n) return fail(`Invalid GPU pilot decoded ${name}`);
  for (const v of value) if (!Number.isFinite(v) || (positive && v <= 0)) return fail(`Invalid GPU pilot decoded ${name}`);
  return value;
}
export function stableGpuPilotNorm(values: Float64Array): number {
  let scale = 0;
  for (const value of values) scale = Math.max(scale, Math.abs(value));
  if (!scale) return 0;
  // Neumaier accumulation of normalized squares avoids overflow and limits reduction error.
  let sum = 0, correction = 0;
  for (const value of values) {
    const term = (value / scale) ** 2;
    const next = sum + term;
    correction += Math.abs(sum) >= Math.abs(term) ? (sum - next) + term : (term - next) + sum;
    sum = next;
  }
  const result = scale * Math.sqrt(sum + correction);
  if (!Number.isFinite(result) || result === 0) return fail('Unsupported overflow or underflow in GPU pilot field norm');
  return result;
}
function roundoffEqual(stored: number, computed: number, cells: number): boolean {
  if (stored === 0 && computed === 0) return true;
  const scale = Math.max(Math.abs(stored), Math.abs(computed));
  const g = gamma(4 * cells + 32), bound = (2 * g / (1 - g)) * scale;
  if (scale > 0 && (!Number.isFinite(bound) || bound === 0)) return fail('Unsupported GPU pilot norm bound');
  return Math.abs(stored - computed) <= bound;
}

export function expectedGpuPilotScanEnd_s(settingsValue: unknown): number {
  const settings = obj(settingsValue, 'settings');
  const layers = count(settings.layers, 1000, 'layer'), tracks = count(settings.tracks, 100_000, 'track');
  const trackLength = num(settings.trackLength_um, 'trackLength_um', 'positive');
  const speed = num(settings.speed_mm_s, 'speed_mm_s', 'positive');
  const dwell = num(settings.dwell_s, 'dwell_s', 'nonnegative'), cooling = num(settings.cooling_s, 'cooling_s', 'nonnegative');
  const strategy = settings.strategy;
  let segments = 0;
  if (strategy === 'island') {
    const island = num(settings.islandSize_um, 'islandSize_um', 'positive');
    const hatch = num(settings.hatch_um, 'hatch_um', 'positive');
    const acrossRaw = Math.trunc(island / hatch);
    if (!Number.isFinite(acrossRaw) || acrossRaw > MAX_CELLS) return fail('GPU pilot island scan grouping exceeds the bound');
    const across = Math.max(1, acrossRaw);
    const columns = Math.ceil(trackLength / island);
    if (!Number.isSafeInteger(columns) || columns < 1 || layers * tracks * columns > MAX_STEPS) {
      return fail('GPU pilot island scan segment count exceeds the bound');
    }
    segments = Math.ceil(tracks / across) * columns * across;
    // A partial final row still contains only its remaining tracks.
    const completeRows = Math.floor(tracks / across), remainder = tracks % across;
    segments = (completeRows * across + remainder) * columns;
  } else {
    segments = tracks;
  }
  const length = trackLength * 1e-6, velocity = speed * 1e-3;
  let time = 0;
    if (strategy === 'island') {
    const island = num(settings.islandSize_um, 'islandSize_um', 'positive');
    const hatch = num(settings.hatch_um, 'hatch_um', 'positive');
    const across = Math.max(1, Math.trunc(island / hatch));
    const columns = Math.ceil(trackLength / island);
    for (let layer = 0; layer < layers; layer++) {
      for (let row = 0; row < tracks; row += across) {
        const rows = Math.min(tracks, row + across) - row;
        for (let col = 0; col < columns; col++) for (let track = 0; track < rows; track++) {
          const a = -length / 2 + col * length / columns;
          const b = a + length / columns;
          time += (b - a) / velocity;
          time += dwell;
        }
      }
    }
  } else {
    const stripe = num(settings.stripeWidth_um, 'stripeWidth_um', 'positive');
    const hatch = num(settings.hatch_um, 'hatch_um', 'positive');
    // scan_segments appends one full-length segment for each track on each layer.
    if (layers * tracks > MAX_STEPS) return fail('GPU pilot scan segment count exceeds the bound');
    for (let layer = 0; layer < layers; layer++) for (let track = 0; track < tracks; track++) {
      void stripe; void hatch;
      time += length / velocity;
      time += dwell;
    }
  }
  const end = time + cooling;
  if (!Number.isFinite(end) || end <= 0 || segments < 1) return fail('Invalid GPU pilot expected scan end');
  return end;
}

export function computeGpuPilotEnthalpyIntegral(enthalpy: Float64Array, volume: number) {
  if (!(enthalpy instanceof Float64Array) || !Number.isFinite(volume) || volume <= 0 || enthalpy.length < 1 || enthalpy.length > MAX_CELLS) {
    return fail('Invalid GPU pilot enthalpy integral inputs');
  }
  // Compensated sum gives the same cancellation-resistant intent as math.fsum.
  let total = 0, correction = 0, absolute = 0, absoluteCorrection = 0;
  for (const value of enthalpy) {
    if (!Number.isFinite(value)) return fail('Invalid GPU pilot enthalpy integral inputs');
    const next = total + value;
    correction += Math.abs(total) >= Math.abs(value) ? (total - next) + value : (value - next) + total;
    total = next;
    const av = Math.abs(value), an = absolute + av;
    absoluteCorrection += Math.abs(absolute) >= av ? (absolute - an) + av : (av - an) + absolute;
    absolute = an;
  }
  total += correction; absolute += absoluteCorrection;
  const integral = total * volume, absIntegral = absolute * volume;
  if (!Number.isFinite(integral) || !Number.isFinite(absIntegral) || (total !== 0 && integral === 0)
    || (absolute !== 0 && absIntegral === 0)) return fail('Unsupported overflow or underflow in GPU pilot enthalpy integral');
  const cells = enthalpy.length;
  const tolerance = 2 * gamma(cells + 2) * absIntegral / (1 - gamma(cells - 1));
  if (absIntegral > 0 && (!Number.isFinite(tolerance) || tolerance === 0)) return fail('Unsupported GPU pilot enthalpy bound');
  return { integral, tolerance };
}

/** Validate captured fields and summaries without solver, CUDA, registries, or new physics. */
export function validateGpuPilotNumerics(resultValue: unknown, decodedValue: unknown, targetsValue: unknown) {
  const result = obj(resultValue, 'result'), decoded = obj(decodedValue, 'decoded states');
  const targetMap = obj(targetsValue, 'frozen targets');
  if (Object.keys(decoded).length !== 2 || BACKENDS.some(key => !Object.hasOwn(decoded, key))) return fail('GPU pilot decoded states must contain CPU and GPU');
  const keys = ['integralRelativeMax', 'widthDepthAbsoluteCellsMax', 'fieldRiseL2RelativeMax', 'fieldRiseMaxRelativeMax', 'peakMeltVolumeRelativeMax'];
  const frozen = Object.fromEntries(keys.map(key => [key, num(targetMap[key], `target ${key}`, 'nonnegative')])) as Record<string, number>;
  if (typeof targetMap.source !== 'string' || !targetMap.source) return fail('GPU pilot target source is missing');
  const pilot = obj(result.gpuPilot, 'parity report');
  if (!strictJsonEqual(pilot.targets, targetMap)) return fail('GPU pilot stored targets differ from frozen targets');
  const descriptor = obj(result.gpuFieldArtifacts, 'field descriptor'), descriptorStates = obj(descriptor.states, 'descriptor states');
  const normalized = {} as Record<'cpu'|'gpu', {coordinates: Float64Array; temperature: Float64Array; enthalpy: Float64Array; density: Float64Array; dt: Float64Array; cells: number; steps: number; time: number; t0: number; volume: number}>;
  const summaries = {} as Record<'cpu'|'gpu', {cells: number; steps: number; mesh: number; minDt: number; maxDt: number; meanDt: number; time: number; volume: number}>;
  for (const backend of BACKENDS) {
    const state = obj(decoded[backend], `${backend} fields`) as unknown as ReadGpuPilotState;
    const meta = obj(descriptorStates[backend], `${backend} descriptor`);
    const cells = count(meta.cells, MAX_CELLS, `${backend} descriptor cells`), steps = count(meta.steps, MAX_STEPS, `${backend} descriptor steps`);
    const arrays = state.arrays;
    if (!arrays || typeof arrays !== 'object') return fail(`Invalid ${backend} arrays`);
    const coordinates = finiteArray(arrays.coordinates_m, cells * 3, `${backend} coordinates`);
    const temperature = finiteArray(arrays.temperature_K, cells, `${backend} temperature`, true);
    const enthalpy = finiteArray(arrays.enthalpy_J_m3, cells, `${backend} enthalpy`);
    const density = finiteArray(arrays.density_kg_m3, cells, `${backend} density`, true);
    const dt = finiteArray(arrays.accepted_dt_s, steps, `${backend} accepted dt`, true);
    for (const key of ['cells', 'steps', 'time_s', 'initial_temperature_K', 'cell_volume_m3'] as const) {
      if (state.metadata[key] !== meta[key]) return fail(`GPU pilot ${backend} field metadata changed`);
    }
    const time = num(meta.time_s, `${backend} time`, 'positive'), t0 = num(meta.initial_temperature_K, `${backend} T0`, 'positive');
    const volume = num(meta.cell_volume_m3, `${backend} volume`, 'positive');
    normalized[backend] = { coordinates, temperature, enthalpy, density, dt, cells, steps, time, t0, volume };
    const summary = backend === 'gpu' ? obj(result.discretization, 'GPU discretization')
      : obj(obj(pilot.cpu, 'CPU summary').discretization, 'CPU discretization');
    const scells = count(summary.cells, MAX_CELLS, `${backend} summary cells`), ssteps = count(summary.steps, MAX_STEPS, `${backend} summary steps`);
    const mesh = num(summary.mesh_m, `${backend} mesh`, 'positive'), expectedVolume = mesh * mesh * mesh;
    if (!Number.isFinite(expectedVolume) || expectedVolume === 0 || !close(volume, expectedVolume, 1e-12, 1e-30)
      || scells !== cells || ssteps !== steps) return fail(`GPU pilot ${backend} field counts or volume conflict with summary`);
    const settings = obj(result.settings, 'settings'), preheat = num(settings.preheat_C, 'preheat_C') + 273.15;
    if (!close(t0, preheat, 1e-12, 1e-12) || !close(time, num(summary.meanDt_s, 'meanDt_s', 'positive') * steps, 1e-12, 1e-14)) {
      return fail(`GPU pilot ${backend} preheat or final time conflicts with settings`);
    }
    let minDt = Infinity, maxDt = 0;
    for (const value of dt) { minDt = Math.min(minDt, value); maxDt = Math.max(maxDt, value); }
    for (const [key, actual] of [['minimumDt_s', minDt], ['maximumDt_s', maxDt]] as const) {
      if (Object.hasOwn(summary, key) && !close(num(summary[key], key, 'positive'), actual)) return fail(`GPU pilot ${backend} ${key} changed`);
    }
    const meanDt = time / steps;
    if (!close(num(summary.meanDt_s, 'meanDt_s', 'positive'), meanDt, 1e-12, 1e-14)) return fail(`GPU pilot ${backend} accepted timestep mean changed`);
    summaries[backend] = { cells, steps, mesh, minDt, maxDt, meanDt, time, volume: expectedVolume };
  }
  const comparisons = obj(pilot.comparisons, 'comparisons');
  if (Object.keys(comparisons).length !== COMPARISONS.length || COMPARISONS.some(k => !Object.hasOwn(comparisons, k))) return fail('GPU pilot comparisons incomplete');
  const energies: Record<string, {integral_J:number; stored_J:number; roundoffTolerance_J:number}> = {};
  const storedItem = obj(comparisons.stored_J, 'stored energy comparison');
  for (const backend of BACKENDS) {
    const computed = computeGpuPilotEnthalpyIntegral(normalized[backend].enthalpy, normalized[backend].volume);
    const stored = num(storedItem[backend], `${backend} stored energy`);
    if (Math.abs(computed.integral - stored) > computed.tolerance) return fail(`GPU pilot ${backend} enthalpy integral conflicts with stored energy`);
    energies[backend] = { integral_J: computed.integral, stored_J: stored, roundoffTolerance_J: computed.tolerance };
  }
  const sampling = obj(comparisons.finalSampling, 'final sampling');
  const cpuTime = num(sampling.cpuFinalTime_s, 'CPU final time', 'positive'), frameTime = num(sampling.cpuFrameTime_s, 'CPU frame time', 'positive');
  const gpuTime = num(sampling.gpuFinalTime_s, 'GPU final time', 'positive'), expectedEnd = expectedGpuPilotScanEnd_s(result.settings);
  const storedEnd = num(sampling.expectedEnd_s, 'expected end', 'positive');
  const cpuSteps = count(sampling.cpuSteps, MAX_STEPS, 'CPU report steps'), gpuSteps = count(sampling.gpuSteps, MAX_STEPS, 'GPU report steps');
  const cellCount = count(sampling.cellCount, MAX_CELLS, 'reported cells');
  if (!close(storedEnd, expectedEnd, 1e-12, 1e-14) || cpuTime !== summaries.cpu.time || gpuTime !== summaries.gpu.time
    || cpuSteps !== summaries.cpu.steps || gpuSteps !== summaries.gpu.steps || cellCount !== summaries.cpu.cells) return fail('GPU pilot sampling summary conflicts with fields');
  const aligned = summaries.cpu.cells === summaries.gpu.cells && summaries.cpu.steps === summaries.gpu.steps
    && close(summaries.cpu.mesh, summaries.gpu.mesh) && close(cpuTime, frameTime, 1e-12, 1e-14)
    && close(cpuTime, expectedEnd, 1e-12, 1e-14) && close(gpuTime, cpuTime, 1e-12, 1e-14)
    && normalized.cpu.coordinates.length === normalized.gpu.coordinates.length
    && normalized.cpu.coordinates.every((v, i) => Object.is(v, normalized.gpu.coordinates[i]) || v === normalized.gpu.coordinates[i]);
  const samplingStatus = aligned ? 'pass' : 'failed';
  if (sampling.status !== samplingStatus) return fail('GPU pilot sampling status conflicts with fields');
  const field = obj(comparisons.finalTemperatureField, 'field comparison');
  let fieldDiagnostic: Record<string, unknown>;
  if (!aligned) {
    if (field.status !== 'failed' || typeof field.reason !== 'string' || !field.reason.trim()
      || Object.hasOwn(field, 'relativeRiseL2') || Object.hasOwn(field, 'relativeRiseMax')) return fail('Misaligned field report has fabricated norms');
    fieldDiagnostic = { status: 'failed', normsRecomputed: false };
  } else {
    const t0 = normalized.cpu.t0, difference = new Float64Array(normalized.cpu.cells), rise = new Float64Array(normalized.cpu.cells);
    let maxDifference = 0, maxRise = 0;
    for (let i = 0; i < difference.length; i++) {
      difference[i] = normalized.gpu.temperature[i] - normalized.cpu.temperature[i];
      rise[i] = normalized.cpu.temperature[i] - t0;
      maxDifference = Math.max(maxDifference, Math.abs(difference[i])); maxRise = Math.max(maxRise, Math.abs(rise[i]));
    }
    const l2 = stableGpuPilotNorm(difference) / Math.max(stableGpuPilotNorm(rise), 1), maximum = maxDifference / Math.max(maxRise, 1);
    if (!Number.isFinite(l2) || !Number.isFinite(maximum)) return fail('Unsupported GPU pilot temperature parity');
    const storedL2 = num(field.relativeRiseL2, 'relativeRiseL2', 'nonnegative'), storedMax = num(field.relativeRiseMax, 'relativeRiseMax', 'nonnegative');
    if (!roundoffEqual(storedL2, l2, summaries.cpu.cells) || !roundoffEqual(storedMax, maximum, summaries.cpu.cells)) return fail('Stored GPU pilot norms conflict with fields');
    const status = storedL2 <= frozen.fieldRiseL2RelativeMax && storedMax <= frozen.fieldRiseMaxRelativeMax ? 'pass' : 'failed';
    if (field.status !== status) return fail('GPU pilot field status conflicts with stored norm thresholds');
    fieldDiagnostic = { status, normsRecomputed: true, relativeRiseL2: l2, relativeRiseMax: maximum };
  }
  const metrics = obj(result.metrics, 'metrics'), energyBalance = obj(result.energyBalance, 'energy balance');
  const statuses: string[] = [samplingStatus, String(field.status)], scalarDiagnostics: Record<string, unknown> = {};
  for (const key of ['peakTemperature_K', 'input_J', 'losses_J', 'stored_J']) {
    const item = obj(comparisons[key], `${key} comparison`), cpu = num(item.cpu, `${key} CPU`, 'nonnegative'), gpu = num(item.gpu, `${key} GPU`, 'nonnegative');
    const displayed = num(key.endsWith('_J') ? energyBalance[key] : metrics[key], `displayed ${key}`, 'nonnegative');
    if (gpu !== displayed) return fail(`GPU pilot ${key} display binding mismatch`);
    const difference = Math.abs(cpu - gpu) / Math.max(Math.abs(cpu), 1e-30), reported = num(item.relativeDifference, `${key} relative difference`, 'nonnegative');
    const status = difference <= frozen.integralRelativeMax ? 'pass' : 'failed';
    if (!Number.isFinite(difference) || reported !== difference || item.status !== status) return fail(`GPU pilot ${key} comparison mismatch`);
    statuses.push(status); scalarDiagnostics[key] = { cpu, gpu, relativeDifference: difference, status };
  }
  const meshUm = summaries.gpu.mesh * 1e6;
  for (const key of ['width_um', 'depth_um', 'length_um']) {
    const item = obj(comparisons[key], `${key} comparison`), cpu = num(item.cpu, `${key} CPU`, 'nonnegative'), gpu = num(item.gpu, `${key} GPU`, 'nonnegative');
    if (gpu !== num(metrics[key], `displayed ${key}`, 'nonnegative')) return fail(`GPU pilot ${key} display binding mismatch`);
    const difference = Math.abs(cpu - gpu), status = cpu === 0 && gpu === 0 ? 'inconclusive'
      : difference <= frozen.widthDepthAbsoluteCellsMax * meshUm ? 'pass' : 'failed';
    if (num(item.absoluteDifference_um, `${key} difference`, 'nonnegative') !== difference || item.status !== status) return fail(`GPU pilot ${key} comparison mismatch`);
    statuses.push(status); scalarDiagnostics[key] = { cpu, gpu, absoluteDifference_um: difference, status };
  }
  {
    const item = obj(comparisons.volume_um3, 'volume comparison'), cpu = num(item.cpu, 'volume CPU', 'nonnegative'), gpu = num(item.gpu, 'volume GPU', 'nonnegative');
    if (gpu !== num(metrics.volume_um3, 'displayed volume', 'nonnegative')) return fail('GPU pilot volume display binding mismatch');
    const difference = Math.abs(cpu - gpu) / Math.max(Math.abs(cpu), 1e-30), status = cpu === 0 && gpu === 0 ? 'inconclusive'
      : difference <= frozen.peakMeltVolumeRelativeMax ? 'pass' : 'failed';
    if (num(item.relativeDifference, 'volume relative difference', 'nonnegative') !== difference || item.status !== status) return fail('GPU pilot volume comparison mismatch');
    statuses.push(status); scalarDiagnostics.volume_um3 = { cpu, gpu, relativeDifference: difference, status };
  }
  const overall = statuses.includes('failed') ? 'failed' : statuses.includes('inconclusive') ? 'inconclusive' : 'pass';
  if (pilot.status !== overall) return fail('GPU pilot overall status mismatch');
  return { status: overall, samplingAligned: aligned,
    states: { cpu: { ...summaries.cpu, ...energies.cpu }, gpu: { ...summaries.gpu, ...energies.gpu } },
    temperatureField: fieldDiagnostic, scalarComparisons: scalarDiagnostics };
}
