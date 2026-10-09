/**
 * Pure helpers for the LPBF G/R solidification map card (python/lpbf_gr_solidification.py is the result authority).
 *
 * This module validates the shape and honesty flags of the engine response and provides view helpers (metric
 * extraction, colour scales, aria labels). It computes no physics: every G, R, band and bound shown by the view is
 * read from the response. Screening only, not validation.
 */
import type {
  GrCell,
  GrCellBody,
  GrCellStatus,
  GrSolidificationResponse,
} from "../services/lpbfGrSolidificationService";

export { moveCell } from "./lpbfProcessWindow";

export const GR_CELL_STATUSES: readonly GrCellStatus[] = ["available", "screening-fallback", "degenerate-floor", "unavailable", "error"];
export const GR_MIN_AXIS = 2;
export const GR_MAX_AXIS = 15;
export const GR_MAX_CELLS = 225;
export const GR_SCHEMA = "lpbf-gr-solidification-1";
export const GR_HATCH_PATTERN_ID = "gr-keyhole-hatch";

export type GrMetric = "goverr" | "cooling" | "laves" | "band";

export interface GrMetricSpec {
  readonly id: GrMetric;
  readonly label: string;
  readonly unit: string;
  readonly categorical: boolean;
  readonly log10: boolean;
}

export const METRICS: readonly GrMetricSpec[] = [
  { id: "goverr", label: "G/R at the median rear-arc point", unit: "log10 (K s/m^2)", categorical: false, log10: true },
  { id: "cooling", label: "Cooling rate G*R (median of the front samples)", unit: "log10 (K/s)", categorical: false, log10: true },
  { id: "laves", label: "Laves bound, trapping-adjusted (sampled arc)", unit: "fraction of liquid", categorical: false, log10: false },
  { id: "band", label: "Hunt G/R band at the median point", unit: "band", categorical: true, log10: false },
];

/** Statuses whose derived numbers are a computed result. Others are drawn as outlined empty cells. */
export function isComputedStatus(status: GrCellStatus): boolean {
  return status === "available" || status === "screening-fallback";
}

/** True when the cell lies outside the conduction regime of the G/R field (engine regimeNote, e.g. keyhole). */
export function isOutsideRegime(cell: GrCellBody): boolean {
  return typeof cell.regimeNote === "string" && cell.regimeNote.length > 0;
}

/** Numeric metric value of a cell (already log10 where the metric says so), or null when there is none. Never 0 for a missing value. */
export function metricValue(cell: GrCellBody, metric: GrMetric): number | null {
  if (!isComputedStatus(cell.status)) return null;
  switch (metric) {
    case "goverr": {
      const v = cell.front.median?.GoverR_K_s_m2;
      return typeof v === "number" && Number.isFinite(v) && v > 0 ? Math.log10(v) : null;
    }
    case "cooling": {
      const v = cell.front.median?.coolingRate_K_s;
      return typeof v === "number" && Number.isFinite(v) && v > 0 ? Math.log10(v) : null;
    }
    case "laves": {
      const f = cell.laves.status === "available" ? cell.laves.sampledArcUpperBound?.f : undefined;
      return typeof f === "number" && Number.isFinite(f) ? f : null;
    }
    case "band":
      return null;
  }
}

/** Categorical Hunt band label of the median point, or null. */
export function bandValue(cell: GrCellBody): string | null {
  if (!isComputedStatus(cell.status)) return null;
  return cell.morphology.bands.median ?? null;
}

// ---------------------------------------------------------------------------------------------------------
// Colour scales (colour-blind safe: a viridis-style sequential ramp and the Okabe-Ito palette for categories)
// ---------------------------------------------------------------------------------------------------------
export const SEQUENTIAL_STOPS: readonly string[] = ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"];

export interface GrCellStyle {
  readonly fill: string;
  readonly stroke: string;
  readonly textColor: string;
  readonly outlined: boolean;
  readonly noValue: boolean;
}

/** Style of a cell that has no value to show: outlined and empty, never the low end of the scale. */
export const NO_VALUE_STYLE: GrCellStyle = { fill: "none", stroke: "#94a3b8", textColor: "#cbd5e1", outlined: true, noValue: true };

const hexToRgb = (hex: string): [number, number, number] => [
  parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16),
];
const rgbToHex = (rgb: number[]): string => `#${rgb.map(c => Math.round(c).toString(16).padStart(2, "0")).join("")}`;

/** Position t in [0, 1] on the sequential ramp (piecewise linear between the 5 stops). */
export function sequentialColor(t: number): string {
  const x = Math.min(1, Math.max(0, t)) * (SEQUENTIAL_STOPS.length - 1);
  const i = Math.min(SEQUENTIAL_STOPS.length - 2, Math.floor(x));
  const f = x - i;
  const a = hexToRgb(SEQUENTIAL_STOPS[i]);
  const b = hexToRgb(SEQUENTIAL_STOPS[i + 1]);
  return rgbToHex([0, 1, 2].map(k => a[k] + (b[k] - a[k]) * f));
}

const luminance = (hex: string): number => {
  const [r, g, b] = hexToRgb(hex).map(c => c / 255);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const readableText = (fill: string): string => (luminance(fill) > 0.45 ? "#0f172a" : "#f8fafc");

export const BAND_COLORS: Readonly<Record<string, string>> = {
  "Planar (Hunt G/R screening)": "#56B4E9",
  "Cellular (Hunt G/R screening)": "#009E73",
  "Columnar dendritic (Hunt G/R screening)": "#E69F00",
  "Mixed / equiaxed tendency (Hunt G/R screening)": "#CC79A7",
};
export const BAND_LETTERS: Readonly<Record<string, string>> = {
  "Planar (Hunt G/R screening)": "P",
  "Cellular (Hunt G/R screening)": "C",
  "Columnar dendritic (Hunt G/R screening)": "D",
  "Mixed / equiaxed tendency (Hunt G/R screening)": "E",
};

export interface ScaleRange { min: number; max: number }

/** Min and max of a numeric metric over a response's cells (null when no cell has a value). */
export function metricRange(cells: readonly GrCellBody[], metric: GrMetric): ScaleRange | null {
  let min = Infinity;
  let max = -Infinity;
  for (const cell of cells) {
    const v = metricValue(cell, metric);
    if (v === null) continue;
    if (v < min) min = v;
    if (v > max) max = v;
  }
  return Number.isFinite(min) ? { min, max } : null;
}

/** Fill, stroke and text colour for a numeric metric value. null maps to NO_VALUE_STYLE. */
export function scaleStyle(value: number | null, range: ScaleRange | null): GrCellStyle {
  if (value === null || !Number.isFinite(value) || range === null) return NO_VALUE_STYLE;
  const t = range.max > range.min ? (value - range.min) / (range.max - range.min) : 0.5;
  const fill = sequentialColor(t);
  return { fill, stroke: "#0f172a", textColor: readableText(fill), outlined: false, noValue: false };
}

export function bandStyle(band: string | null): GrCellStyle {
  if (band === null) return NO_VALUE_STYLE;
  const fill = BAND_COLORS[band];
  if (!fill) return NO_VALUE_STYLE;
  return { fill, stroke: "#0f172a", textColor: readableText(fill), outlined: false, noValue: false };
}

export function cellStyle(cell: GrCellBody, metric: GrMetric, range: ScaleRange | null): GrCellStyle {
  return metric === "band" ? bandStyle(bandValue(cell)) : scaleStyle(metricValue(cell, metric), range);
}

/** Short in-cell text: the status letter for cells without a value, the band letter for the categorical metric. */
export function cellGlyph(cell: GrCellBody, metric: GrMetric): string {
  if (cell.status === "error") return "!";
  if (cell.status === "unavailable") return "-";
  if (cell.status === "degenerate-floor") return "F";
  if (metric === "band") {
    const band = bandValue(cell);
    return band ? (BAND_LETTERS[band] ?? "") : "";
  }
  return metricValue(cell, metric) === null ? "-" : "";
}

export const STATUS_LABELS: Readonly<Record<GrCellStatus, string>> = {
  available: "Computed",
  "screening-fallback": "Fallback heuristic (median only)",
  "degenerate-floor": "Solver floor, not a computed result",
  unavailable: "Unavailable",
  error: "Solver error",
};

export function formatSci(value: number | null | undefined, digits = 3): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toExponential(digits) : "not available";
}

export function formatMetric(value: number | null, metric: GrMetric): string {
  if (value === null) return "no value";
  return metric === "laves" ? value.toFixed(4) : value.toFixed(2);
}

export function cellAriaLabel(cell: GrCellBody & { power_W: number; speed_mm_s: number }, metric: GrMetric): string {
  const base = `Power ${cell.power_W} W, speed ${cell.speed_mm_s} mm/s: ${STATUS_LABELS[cell.status]}`;
  const value = metric === "band" ? bandValue(cell) : metricValue(cell, metric);
  const shown = value === null ? "no value" : typeof value === "string" ? value : formatMetric(value, metric);
  const outside = isOutsideRegime(cell) ? ", outside the conduction regime (keyhole)" : "";
  return `${base}, ${metric}: ${shown}${outside}`;
}

// ---------------------------------------------------------------------------------------------------------
// Response validator
// ---------------------------------------------------------------------------------------------------------
const fail = (reason: string): never => { throw new Error(`lpbf G/R solidification response rejected: ${reason}`); };
const isObject = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === "object" && !Array.isArray(v);
const isFiniteNumber = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isNumberOrNull = (v: unknown) => v === null || isFiniteNumber(v);
const isStringOrNull = (v: unknown) => v === null || typeof v === "string";

function checkLocation(where: string, loc: unknown): void {
  if (loc === null) return;
  if (!isObject(loc)) return fail(`${where} is not an object or null`);
  for (const key of ["G_K_m", "R_m_s", "GoverR_K_s_m2", "GtimesR_K_s"]) {
    if (!isNumberOrNull(loc[key])) return fail(`${where}.${key} is not a number or null`);
  }
  if (!isStringOrNull(loc.huntBand)) return fail(`${where}.huntBand invalid`);
}

function checkBody(where: string, body: unknown): void {
  if (!isObject(body)) return fail(`${where} is not an object`);
  if (typeof body.status !== "string" || !(GR_CELL_STATUSES as readonly string[]).includes(body.status)) {
    return fail(`${where} has unknown status ${JSON.stringify(body.status)}`);
  }
  if (!isStringOrNull(body.reason) || !isStringOrNull(body.regimeNote) || !isStringOrNull(body.regime)) return fail(`${where} text fields invalid`);
  if (body.status !== "available" && (typeof body.reason !== "string" || !body.reason)) {
    return fail(`${where} has status ${String(body.status)} without a reason`);
  }
  const front = body.front;
  if (!isObject(front)) return fail(`${where}.front missing`);
  for (const loc of ["median", "bottom", "tail"]) checkLocation(`${where}.front.${loc}`, front[loc]);
  if (typeof front.coolingBasis !== "string") return fail(`${where}.front.coolingBasis missing`);
  const cet = body.cet;
  if (!isObject(cet) || (cet.status !== "available" && cet.status !== "unavailable")) {
    return fail(`${where}.cet.status must be "available" or "unavailable"`);
  }
  if (cet.status === "unavailable" && (typeof cet.reason !== "string" || !cet.reason)) return fail(`${where}.cet is unavailable without a reason`);
  const laves = body.laves;
  if (!isObject(laves) || (laves.status !== "available" && laves.status !== "unavailable")) return fail(`${where}.laves.status invalid`);
  if (laves.status === "available") {
    const ub = laves.sampledArcUpperBound;
    if (!isObject(ub) || !isFiniteNumber(ub.f) || !isFiniteNumber(laves.equilibriumKBound)) return fail(`${where}.laves bound missing`);
  } else if (typeof laves.reason !== "string" || !laves.reason) {
    return fail(`${where}.laves is unavailable without a reason`);
  }
  const morphology = body.morphology;
  if (!isObject(morphology) || typeof morphology.label !== "string" || !isObject(morphology.bands)) return fail(`${where}.morphology invalid`);
  const centreline = body.rosenthalCenterline;
  if (!isObject(centreline) || (centreline.status !== "available" && centreline.status !== "unavailable")) return fail(`${where}.rosenthalCenterline invalid`);
}

export function checkedGrSolidification(raw: unknown): GrSolidificationResponse {
  if (!isObject(raw)) return fail("not an object");
  if (raw.success !== true) return fail("success is not true");
  const evidence = raw.evidence;
  if (!isObject(evidence)) return fail("missing evidence");
  if (evidence.kind !== "screening-only") return fail(`evidence.kind must be "screening-only" (got ${JSON.stringify(evidence.kind)})`);
  if (evidence.experimentalValidation !== false) return fail("evidence.experimentalValidation must be exactly false");
  if (typeof evidence.statement !== "string" || !evidence.statement) return fail("evidence.statement missing");
  if (raw.schema !== GR_SCHEMA) return fail(`schema must be ${GR_SCHEMA}`);
  if (raw.mode !== "point" && raw.mode !== "map") return fail("mode invalid");
  if (raw.alloyId !== "in718" && raw.alloyId !== "in625") return fail("alloyId invalid");
  const request = raw.request;
  if (!isObject(request)) return fail("missing request echo");
  for (const key of ["beamDiameter_um", "layer_um", "hatch_um", "preheatTemp_C"]) {
    if (!isFiniteNumber(request[key])) return fail(`request.${key} is not a number`);
  }
  const provenance = raw.provenance;
  if (!isObject(provenance) || typeof provenance.solidificationModelId !== "string" || typeof provenance.buildJobSolverRevision !== "string") {
    return fail("missing provenance");
  }
  if (!Array.isArray(raw.limits) || !raw.limits.every(x => typeof x === "string")) return fail("limits missing");
  const cet = raw.cet;
  if (!isObject(cet) || typeof cet.equation !== "string" || typeof cet.equationVerified !== "boolean") return fail("cet criterion view missing");
  const constants = cet.constantsStatus;
  if (!isObject(constants) || (constants.status !== "available" && constants.status !== "unavailable")) return fail("cet.constantsStatus invalid");
  const laves = raw.laves;
  if (!isObject(laves) || !isFiniteNumber(laves.equilibriumKBound) || !Array.isArray(laves.V_D_m_s)) return fail("laves summary missing");
  if (!isFiniteNumber(raw.computeMs)) return fail("computeMs missing");

  let bodies: unknown[];
  if (raw.mode === "point") {
    if (raw.point === undefined) return fail("point missing");
    checkBody("point", raw.point);
    bodies = [raw.point];
  } else {
    const grid = raw.grid;
    if (!isObject(grid)) return fail("missing grid");
    const powers = grid.powers_W;
    const speeds = grid.speeds_mm_s;
    if (!Array.isArray(powers) || !powers.every(isFiniteNumber)) return fail("grid.powers_W invalid");
    if (!Array.isArray(speeds) || !speeds.every(isFiniteNumber)) return fail("grid.speeds_mm_s invalid");
    const nP = powers.length;
    const nV = speeds.length;
    if (nP < GR_MIN_AXIS || nP > GR_MAX_AXIS || nV < GR_MIN_AXIS || nV > GR_MAX_AXIS) return fail(`axis lengths ${nP} x ${nV} out of range`);
    if (grid.nP !== nP || grid.nV !== nV || grid.nCells !== nP * nV) return fail("grid.nP/nV/nCells do not match the axes");
    if (nP * nV > GR_MAX_CELLS) return fail("more than 225 cells");
    const increasing = (a: number[]) => a.every((x, i) => i === 0 || x > a[i - 1]);
    if (!increasing(powers) || !increasing(speeds)) return fail("axes must be strictly increasing");
    const cells = raw.cells;
    if (!Array.isArray(cells) || cells.length !== nP * nV) return fail(`cell count ${Array.isArray(cells) ? cells.length : "n/a"} does not equal ${nP} x ${nV}`);
    cells.forEach((cell: unknown, index: number) => {
      const where = `cells[${index}]`;
      checkBody(where, cell);
      const c = cell as Record<string, unknown>;
      if (c.iP !== Math.floor(index / nV) || c.iV !== index % nV) fail(`${where} index does not match its position`);
      if (c.power_W !== powers[c.iP as number] || c.speed_mm_s !== speeds[c.iV as number]) fail(`${where} P/v does not match the grid axes`);
    });
    bodies = cells;
  }
  const counts = raw.counts;
  if (!isObject(counts)) return fail("missing counts");
  for (const status of GR_CELL_STATUSES) {
    const n = bodies.filter(b => (b as Record<string, unknown>).status === status).length;
    if (counts[status] !== n) return fail(`counts.${status} (${String(counts[status])}) does not match the cells (${n})`);
  }
  return raw as unknown as GrSolidificationResponse;
}

export function cellAt(response: GrSolidificationResponse, iP: number, iV: number): GrCell {
  const cells = response.cells ?? [];
  const nV = response.grid?.nV ?? 0;
  return cells[iP * nV + iV];
}
