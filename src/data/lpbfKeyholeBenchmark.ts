/// <reference types="vite/client" />

export const LPBF_KEYHOLE_BENCHMARK_SCHEMA = "lpbf-keyhole-benchmark-view-1";

export interface LpbfKeyholeBenchmark {
  readonly schema: string;
  readonly generatedAt?: string;
  readonly label?: string;
  readonly readOnly?: boolean;
  readonly sources?: readonly { readonly id?: string; readonly doi?: string; readonly rows?: number }[];
  readonly regimeConfusion?: {
    readonly accuracy?: number;
    readonly keyholeRecall?: number;
    readonly matrix?: Readonly<Record<string, Readonly<Record<string, number>>>>;
    readonly n?: number;
    readonly rule?: string;
  };
  readonly depth?: Readonly<Record<string, number>>;
  readonly keyholeThreshold?: { readonly app?: number; readonly appIndexAtPublishedKeyholeLine?: LpbfKeyholeSpread };
  readonly porosity?: { readonly zhaoPoreCasesFlaggedHigh?: string; readonly appIndexAlongPublishedPorosityBoundary?: LpbfKeyholeSpread };
  readonly honesty?: string;
  readonly physicsBumpProposed?: boolean;
  readonly evidenceNote?: string;
}

export interface LpbfKeyholeSpread {
  readonly min?: number;
  readonly median?: number;
  readonly max?: number;
  readonly n?: number;
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function finiteOrMissing(value: unknown, where: string): number | undefined {
  if (value === undefined || value === null) return undefined;
  if (typeof value !== "number" || !Number.isFinite(value)) throw new Error(`LPBF keyhole benchmark rejected: ${where} is not finite`);
  return value;
}

export function checkedLpbfKeyholeBenchmark(value: unknown): LpbfKeyholeBenchmark {
  if (!record(value)) throw new Error("LPBF keyhole benchmark rejected: not an object");
  if (typeof value.schema !== "string" || !value.schema.startsWith("lpbf-keyhole-benchmark-view-")) throw new Error(`LPBF keyhole benchmark rejected: schema ${String(value.schema)}`);
  if (value.sources !== undefined && !Array.isArray(value.sources)) throw new Error("LPBF keyhole benchmark rejected: sources is not an array");
  for (const [index, source] of (Array.isArray(value.sources) ? value.sources : []).entries()) {
    if (!record(source)) throw new Error(`LPBF keyhole benchmark rejected: sources[${index}] is malformed`);
    finiteOrMissing(source.rows, `sources[${index}].rows`);
  }
  if (value.regimeConfusion !== undefined && !record(value.regimeConfusion)) throw new Error("LPBF keyhole benchmark rejected: regimeConfusion is malformed");
  const confusion = record(value.regimeConfusion) ? value.regimeConfusion : {};
  finiteOrMissing(confusion.accuracy, "regimeConfusion.accuracy");
  finiteOrMissing(confusion.keyholeRecall, "regimeConfusion.keyholeRecall");
  if (confusion.matrix !== undefined && !record(confusion.matrix)) throw new Error("LPBF keyhole benchmark rejected: regimeConfusion.matrix is malformed");
  for (const [row, cells] of Object.entries(record(confusion.matrix) ? confusion.matrix : {})) {
    if (!record(cells)) throw new Error(`LPBF keyhole benchmark rejected: matrix.${row} is malformed`);
    for (const [column, count] of Object.entries(cells)) {
      if (typeof count !== "number" || !Number.isFinite(count)) throw new Error(`LPBF keyhole benchmark rejected: matrix.${row}.${column} is not finite`);
    }
  }
  return value as unknown as LpbfKeyholeBenchmark;
}

let modules: Record<string, unknown> = {};
try {
  modules = import.meta.glob("../../docs/LPBF_KEYHOLE_BENCHMARK_*.view.json", { eager: true, import: "default" });
} catch {
  modules = {};
}

const newestKey = Object.keys(modules).sort().at(-1);
export const COMMITTED_LPBF_KEYHOLE_BENCHMARK: LpbfKeyholeBenchmark | null =
  newestKey === undefined ? null : checkedLpbfKeyholeBenchmark(modules[newestKey]);
