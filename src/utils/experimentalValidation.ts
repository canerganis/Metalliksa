/**
 * Pure helpers for the Melt Pool vs Measurements panel: aggregation per scan velocity, overlay gating and residuals.
 * Nothing here interpolates or invents values; unavailable results say why.
 */
export interface MeasuredRow { power_W: number | null; velocity_mms: number | null; width_um: number | null; depth_um: number | null }
export interface Stat { mean: number; sd: number | null; min: number; max: number; n: number }
export interface VelocityAggregate { velocity_mms: number; width: Stat | null; depth: Stat | null }

/** Dataset scope the overlay is allowed to compare against. */
export const CMU_OVERLAY_SCOPE = {
  material: 'ti6al4v',
  power_W: 370,
  powerTolerance_W: 5,
  /** Manufacturer-reported spot of the Miner et al. fatigue-coupon build (Addit. Manuf. 2024, sec. 2.2), not stated in the CSV itself. */
  beamDiameter_um: 100,
  beamTolerance_um: 5,
} as const;

const norm = (s: unknown) => String(s ?? '').toLowerCase().replace(/[^a-z0-9]/g, '');

function stat(values: number[]): Stat | null {
  if (!values.length) return null;
  const n = values.length;
  const mean = values.reduce((a, b) => a + b, 0) / n;
  const sd = n > 1 ? Math.sqrt(values.reduce((a, b) => a + (b - mean) ** 2, 0) / (n - 1)) : null;
  return { mean, sd, min: Math.min(...values), max: Math.max(...values), n };
}

/** Rows with a null (missing) quantity are excluded from that quantity only; nothing is imputed. */
export function aggregateByVelocity(rows: MeasuredRow[]): VelocityAggregate[] {
  const groups = new Map<number, MeasuredRow[]>();
  for (const row of rows) {
    if (row.velocity_mms == null || !Number.isFinite(row.velocity_mms)) continue;
    groups.set(row.velocity_mms, [...(groups.get(row.velocity_mms) ?? []), row]);
  }
  const finite = (v: number | null): v is number => v != null && Number.isFinite(v);
  return [...groups.entries()].sort((a, b) => a[0] - b[0]).map(([velocity_mms, group]) => ({
    velocity_mms,
    width: stat(group.map(r => r.width_um).filter(finite)),
    depth: stat(group.map(r => r.depth_um).filter(finite)),
  }));
}

export interface OverlayGate { eligible: boolean; reasons: string[] }

/** The simulation may be drawn against the CMU measurements only when material, power and beam diameter all match the dataset scope. */
export function overlayGate(input: { material?: unknown; power_W?: unknown; beamDiameter_um?: unknown } | undefined): OverlayGate {
  const s = CMU_OVERLAY_SCOPE;
  const reasons: string[] = [];
  if (!input) return { eligible: false, reasons: ['No simulation result is available.'] };
  if (norm(input.material) !== s.material) reasons.push(`Material is ${String(input.material ?? 'unknown')}; the measurements are Ti-6Al-4V.`);
  if (typeof input.power_W !== 'number' || !Number.isFinite(input.power_W) || Math.abs(input.power_W - s.power_W) > s.powerTolerance_W) {
    reasons.push(`Laser power is ${String(input.power_W ?? 'unknown')} W; the measurements are at ${s.power_W} W (±${s.powerTolerance_W} W).`);
  }
  if (typeof input.beamDiameter_um !== 'number' || !Number.isFinite(input.beamDiameter_um) || Math.abs(input.beamDiameter_um - s.beamDiameter_um) > s.beamTolerance_um) {
    reasons.push(`Beam diameter is ${String(input.beamDiameter_um ?? 'unknown')} µm; the cited build used a ${s.beamDiameter_um} µm spot (±${s.beamTolerance_um} µm).`);
  }
  return { eligible: reasons.length === 0, reasons };
}

export interface ResidualQuantity { simulated: number; measuredMean: number; residual: number; sd: number | null; n: number; withinRange: boolean }
export interface Residual {
  available: boolean;
  /** Why the residual is unavailable. */
  reason?: string;
  velocity_mms?: number;
  width?: ResidualQuantity; depth?: ResidualQuantity;
}

function quantity(simulated: unknown, s: Stat | null): ResidualQuantity | undefined {
  if (!s || typeof simulated !== 'number' || !Number.isFinite(simulated)) return undefined;
  return { simulated, measuredMean: s.mean, residual: simulated - s.mean, sd: s.sd, n: s.n, withinRange: simulated >= s.min && simulated <= s.max };
}

/** Residual (simulated minus measured mean) only at a velocity that has measurements; no interpolation. */
export function residualAt(aggregates: VelocityAggregate[], speed_mm_s: unknown, metrics: { width_um?: unknown; depth_um?: unknown } | undefined): Residual {
  if (typeof speed_mm_s !== 'number' || !Number.isFinite(speed_mm_s) || !metrics) return { available: false, reason: 'No simulated speed or metrics.' };
  const hit = aggregates.find(a => Math.abs(a.velocity_mms - speed_mm_s) <= 1e-6 * Math.max(1, Math.abs(speed_mm_s)));
  if (!hit) return { available: false, reason: `No measurements at ${speed_mm_s} mm/s; values are not interpolated between velocities.` };
  const width = quantity(metrics.width_um, hit.width), depth = quantity(metrics.depth_um, hit.depth);
  if (!width && !depth) return { available: false, reason: 'Measurements at this velocity lack width and depth values.' };
  return { available: true, velocity_mms: hit.velocity_mms, width, depth };
}
