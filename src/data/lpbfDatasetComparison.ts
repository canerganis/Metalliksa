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
  readonly notes?: string;
}

export interface ComparisonKernelPrediction {
  readonly width_um: number | null;
  readonly depth_um: number | null;
  readonly length_um?: number | null;
  readonly extentStatus: string;
  readonly included: boolean;
  readonly extentNote?: string;
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
    readonly width_um: number | null;
    readonly depth_um: number | null;
    readonly area_um2?: number | null;
    readonly balling?: boolean | null;
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
}

export interface ComparisonSummaryCell {
  readonly n: number;
  readonly nExcluded: number;
  readonly width: ComparisonErrorStats;
  readonly depth: ComparisonErrorStats;
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
  } & Readonly<Record<string, unknown>>;
  readonly referenceTransient?: { readonly rows?: readonly unknown[]; readonly note?: string };
  readonly honesty: { readonly statement: string; readonly experimentalValidation: false };
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
  if (!Array.isArray(document.kernels)) fail("kernels is not an array");
  if (!Array.isArray(document.rows)) fail("rows is not an array");
  if (!isRecord(document.summary)) fail("summary is not an object");
  const absorptivity = document.absorptivitySensitivity;
  if (!isRecord(absorptivity) || !Array.isArray(absorptivity.values)) fail("absorptivitySensitivity.values is missing");
  const datasetIds = new Set(document.datasets.map((d) => (isRecord(d) ? d.id : undefined)));
  document.rows.forEach((row, index) => {
    if (!isRecord(row) || !isRecord(row.inputs) || !isRecord(row.measured) || !isRecord(row.regime) || !isRecord(row.predictions)) {
      fail(`rows[${index}] is missing inputs, measured, regime or predictions`);
    }
    if (!datasetIds.has(row.dataset)) fail(`rows[${index}] names unknown dataset ${String(row.dataset)}`);
    for (const [kernel, prediction] of Object.entries(row.predictions)) {
      if (!isRecord(prediction) || typeof prediction.included !== "boolean" || typeof prediction.extentStatus !== "string") {
        fail(`rows[${index}].predictions.${kernel} needs boolean included and string extentStatus`);
      }
    }
  });
  return document as unknown as LpbfDatasetComparisonDocument;
}

/** Per-kernel width MAPE by absorptivity value, as carried by the record (array aligned with values, or object keyed by value). */
export function absorptivityMapeByValue(
  document: LpbfDatasetComparisonDocument,
  kernel: string,
): readonly (number | null)[] | null {
  const entry = document.absorptivitySensitivity[kernel];
  if (!isRecord(entry)) return null;
  const series = entry.width_mape_pct_by_value;
  if (Array.isArray(series)) return series.map((v) => (typeof v === "number" ? v : null));
  if (isRecord(series)) {
    return document.absorptivitySensitivity.values.map((value) => {
      const v = series[String(value)];
      return typeof v === "number" ? v : null;
    });
  }
  return null;
}
