/**
 * Typed, read-only loader for the Python-generated LPBF dataset comparison record
 * (docs/LPBF_DATASET_COMPARISON_2026-10-05.json, schema "lpbf-dataset-comparison-1").
 *
 * Python is the result authority: every number the Dataset Comparison lab shows (predictions,
 * bias/MAPE/RMSE, within-band share, the absorptivity bracket) is read from that JSON. This module
 * validates shape and honesty flags only; it computes no physics and no statistics.
 * It is a comparison against published single-track measurements, not experimental validation.
 */

export const LPBF_DATASET_COMPARISON_SCHEMA = "lpbf-dataset-comparison-1";

export type ComparisonKernelId = "rosenthal" | "eagar-tsai" | "goldak";
export const COMPARISON_KERNEL_IDS: readonly ComparisonKernelId[] = ["rosenthal", "eagar-tsai", "goldak"];

export interface ComparisonDataset {
  readonly id: string;
  readonly doi: string;
  readonly license: string;
  readonly url: string;
  readonly sha256: string;
  readonly rows: number;
  readonly citation: string;
  /** caveat strings, one per statement (the record carries an array) */
  readonly notes: readonly string[];
}

export interface ComparisonKernelPrediction {
  readonly width_um: number | null;
  readonly depth_um: number | null;
  readonly length_um?: number | null;
  readonly extentStatus: string;
  readonly included: boolean;
  readonly extentNote?: string | null;
}

export interface ComparisonRow {
  readonly dataset: string;
  readonly rowId: string;
  readonly inputs: {
    readonly material: string;
    readonly power_W: number;
    readonly speed_mm_s: number;
    readonly beamDiameter_um: number;
    readonly layer_um: number;
    readonly preheat_C: number;
  };
  readonly measured: {
    readonly width_um: number;
    readonly depth_um: number;
    readonly area_um2?: number | null;
    readonly balling?: boolean | number | null;
  };
  readonly regime: { readonly label: string; readonly normalizedEnthalpy?: number; readonly dOverW?: number };
  readonly predictions: Readonly<Record<string, ComparisonKernelPrediction>>;
}

export interface ComparisonErrorStats {
  readonly bias_pct: number;
  readonly mape_pct: number;
  readonly rmse_um: number;
  /** fraction in [0, 1] (the record stores fractions; the view renders percents) */
  readonly within30pct: number;
  readonly withinFactor2?: number;
  /** optional 95 % interval [lo, hi] written by the producer */
  readonly bias_pct_ci95?: readonly [number, number];
  readonly mape_pct_ci95?: readonly [number, number];
}

export interface ComparisonSummaryCell {
  readonly n: number;
  readonly nExcluded: number;
  /** null: empty slot (no included rows) */
  readonly width: ComparisonErrorStats | null;
  readonly depth: ComparisonErrorStats | null;
}

export interface LpbfDatasetComparisonDocument {
  readonly schema: typeof LPBF_DATASET_COMPARISON_SCHEMA;
  readonly generatedAt: string;
  readonly implementationHash: string;
  readonly datasets: readonly ComparisonDataset[];
  readonly regimeFilter: { readonly rule: string; readonly parameters?: Readonly<Record<string, unknown>> };
  readonly kernels: readonly string[];
  readonly rows: readonly ComparisonRow[];
  readonly summary: Readonly<Record<string, Readonly<Record<string, ComparisonSummaryCell>>>>;
  readonly absorptivitySensitivity: {
    readonly values: readonly number[];
    readonly label?: string;
  } & Readonly<Record<string, unknown>>;
  readonly referenceTransient?: { readonly rows?: readonly unknown[]; readonly note?: string };
  readonly honesty: { readonly statement: string; readonly experimentalValidation: false };
  /** optional producer-written limitation statements */
  readonly limits?: readonly string[];
  /** optional absorption path description */
  readonly absorption?: { readonly path?: string; readonly pinned?: unknown } & Readonly<Record<string, unknown>>;
}

const REQUIRED_KEYS = [
  "generatedAt", "implementationHash", "datasets", "regimeFilter", "kernels", "rows", "summary",
  "absorptivitySensitivity", "honesty",
] as const;

function fail(reason: string): never {
  throw new Error(`lpbf dataset comparison record rejected: ${reason}`);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function checkFinite(value: unknown, where: string): void {
  if (!isFiniteNumber(value)) fail(`${where} is not a finite number`);
}

function checkString(value: unknown, where: string): void {
  if (typeof value !== "string" || value.length === 0) fail(`${where} is not a non-empty string`);
}

function checkInterval(value: unknown, where: string): void {
  if (value === undefined) return;
  if (!Array.isArray(value) || value.length !== 2 || !isFiniteNumber(value[0]) || !isFiniteNumber(value[1])) {
    fail(`${where} is not a [lo, hi] pair of finite numbers`);
  }
}

function checkStats(stats: unknown, where: string): void {
  if (stats === null) return; // empty slot: the view shows "no included rows"
  if (!isRecord(stats)) fail(`${where} is neither a stats object nor null`);
  for (const key of ["bias_pct", "mape_pct", "rmse_um"] as const) checkFinite(stats[key], `${where}.${key}`);
  for (const key of ["within30pct", "withinFactor2"] as const) {
    const v = stats[key];
    if (key === "withinFactor2" && v === undefined) continue;
    if (!isFiniteNumber(v) || v < 0 || v > 1) fail(`${where}.${key} is not a fraction in [0, 1]`);
  }
  checkInterval(stats.bias_pct_ci95, `${where}.bias_pct_ci95`);
  checkInterval(stats.mape_pct_ci95, `${where}.mape_pct_ci95`);
}

export function checkedDatasetComparison(document: unknown): LpbfDatasetComparisonDocument {
  if (!isRecord(document)) fail("not an object");
  if (document.schema !== LPBF_DATASET_COMPARISON_SCHEMA) {
    fail(`schema ${String(document.schema)} is not the supported ${LPBF_DATASET_COMPARISON_SCHEMA}`);
  }
  for (const key of REQUIRED_KEYS) {
    if (document[key] === undefined || document[key] === null) fail(`missing required key "${key}"`);
  }
  const honesty = document.honesty;
  if (!isRecord(honesty) || typeof honesty.statement !== "string" || honesty.statement.length === 0) {
    fail("honesty.statement is missing");
  }
  if (honesty.experimentalValidation !== false) fail("honesty.experimentalValidation must be exactly false");
  if (!Array.isArray(document.datasets)) fail("datasets is not an array");
  if (!Array.isArray(document.kernels) || document.kernels.length === 0 || !document.kernels.every((k) => typeof k === "string")) {
    fail("kernels is not a non-empty array of strings");
  }
  const kernels = document.kernels as string[];
  if (!Array.isArray(document.rows)) fail("rows is not an array");
  if (!isRecord(document.summary)) fail("summary is not an object");
  if (!isRecord(document.regimeFilter)) fail("regimeFilter is not an object");
  checkString(document.regimeFilter.rule, "regimeFilter.rule");
  const absorptivity = document.absorptivitySensitivity;
  if (!isRecord(absorptivity) || !Array.isArray(absorptivity.values)) fail("absorptivitySensitivity.values is missing");
  if (!absorptivity.values.every(isFiniteNumber)) fail("absorptivitySensitivity.values has a non-finite entry");
  if (document.limits !== undefined && (!Array.isArray(document.limits) || !document.limits.every((l) => typeof l === "string"))) {
    fail("limits is not an array of strings");
  }
  if (document.absorption !== undefined && !isRecord(document.absorption)) fail("absorption is not an object");

  document.datasets.forEach((d, index) => {
    const where = `datasets[${index}]`;
    if (!isRecord(d)) fail(`${where} is not an object`);
    for (const key of ["id", "doi", "license", "sha256", "citation"] as const) checkString(d[key], `${where}.${key}`);
    checkFinite(d.rows, `${where}.rows`);
    if (!Array.isArray(d.notes) || !d.notes.every((n) => typeof n === "string")) {
      fail(`${where}.notes is not an array of strings`);
    }
  });

  for (const [kernel, byRegime] of Object.entries(document.summary)) {
    if (!isRecord(byRegime)) fail(`summary.${kernel} is not an object`);
    for (const [regime, cell] of Object.entries(byRegime)) {
      const where = `summary.${kernel}.${regime}`;
      if (!isRecord(cell)) fail(`${where} is not an object`);
      checkFinite(cell.n, `${where}.n`);
      checkFinite(cell.nExcluded, `${where}.nExcluded`);
      if (!("width" in cell) || !("depth" in cell)) fail(`${where} is missing width or depth`);
      checkStats(cell.width, `${where}.width`);
      checkStats(cell.depth, `${where}.depth`);
    }
  }
  for (const kernel of kernels) {
    if (!isRecord(document.summary[kernel])) fail(`summary has no entry for declared kernel ${kernel}`);
  }

  const datasetIds = new Set(document.datasets.map((d) => (isRecord(d) ? d.id : undefined)));
  document.rows.forEach((row, index) => {
    if (!isRecord(row) || !isRecord(row.inputs) || !isRecord(row.measured) || !isRecord(row.regime) || !isRecord(row.predictions)) {
      fail(`rows[${index}] is missing inputs, measured, regime or predictions`);
    }
    if (!datasetIds.has(row.dataset)) fail(`rows[${index}] names unknown dataset ${String(row.dataset)}`);
    checkFinite(row.measured.width_um, `rows[${index}].measured.width_um`);
    checkFinite(row.measured.depth_um, `rows[${index}].measured.depth_um`);
    checkString(row.regime.label, `rows[${index}].regime.label`);
    for (const kernel of kernels) {
      if (!(kernel in row.predictions)) fail(`rows[${index}].predictions has no entry for declared kernel ${kernel}`);
    }
    for (const [kernel, prediction] of Object.entries(row.predictions)) {
      if (!isRecord(prediction) || typeof prediction.included !== "boolean" || typeof prediction.extentStatus !== "string") {
        fail(`rows[${index}].predictions.${kernel} needs boolean included and string extentStatus`);
      }
    }
  });
  return document as unknown as LpbfDatasetComparisonDocument;
}

const KEY_TOLERANCE = 1e-9;

/** Series carried as an array (aligned with values) or as an object keyed by a numeric string ("0.30" or "0.3"). */
function seriesByValue(series: unknown, values: readonly number[]): readonly (number | null)[] | null {
  if (Array.isArray(series)) return series.map((v) => (isFiniteNumber(v) ? v : null));
  if (!isRecord(series)) return null;
  const parsed = Object.entries(series).map(([key, v]) => [Number(key), v] as const);
  return values.map((value) => {
    const hit = parsed.find(([k]) => Number.isFinite(k) && Math.abs(k - value) <= KEY_TOLERANCE);
    return hit && isFiniteNumber(hit[1]) ? hit[1] : null;
  });
}

/** Per-kernel width MAPE by absorptivity value, as carried by the record. */
export function absorptivityMapeByValue(
  document: LpbfDatasetComparisonDocument,
  kernel: string,
): readonly (number | null)[] | null {
  const entry = document.absorptivitySensitivity[kernel];
  if (!isRecord(entry)) return null;
  return seriesByValue(entry.width_mape_pct_by_value, document.absorptivitySensitivity.values);
}

export interface AbsorptivitySensitivityCell {
  readonly value: number;
  readonly widthMape: number | null;
  readonly depthMape: number | null;
  readonly nIncluded: number | null;
}

/** Width MAPE, depth MAPE and included row count per absorptivity value for one kernel. */
export function absorptivitySensitivityCells(
  document: LpbfDatasetComparisonDocument,
  kernel: string,
): readonly AbsorptivitySensitivityCell[] | null {
  const entry = document.absorptivitySensitivity[kernel];
  if (!isRecord(entry)) return null;
  const values = document.absorptivitySensitivity.values;
  const width = seriesByValue(entry.width_mape_pct_by_value, values);
  if (width === null) return null;
  const depth = seriesByValue(entry.depth_mape_pct_by_value, values);
  const n = seriesByValue(entry.n_included_by_value, values);
  return values.map((value, i) => ({
    value,
    widthMape: width[i] ?? null,
    depthMape: depth?.[i] ?? null,
    nIncluded: n?.[i] ?? null,
  }));
}
