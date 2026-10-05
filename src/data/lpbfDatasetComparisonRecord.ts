/// <reference types="vite/client" />
/**
 * The committed comparison record, if any. Vite inlines docs/LPBF_DATASET_COMPARISON_2026-10-05.json
 * when it exists; when the file is absent the glob is empty and the lab shows an honest
 * "no comparison record committed yet" state. Outside Vite (tests under tsx) the glob is unavailable
 * and the record is treated as absent; tests pass documents to the lab explicitly.
 */
import { checkedDatasetComparison, type LpbfDatasetComparisonDocument } from "./lpbfDatasetComparison";

let modules: Record<string, unknown> = {};
try {
  modules = import.meta.glob("../../docs/LPBF_DATASET_COMPARISON_2026-10-05.json", { eager: true, import: "default" });
} catch {
  modules = {};
}

const raw = Object.values(modules)[0];

/** null when no record is committed; throws (loudly) when a committed record is malformed. */
export const COMMITTED_DATASET_COMPARISON: LpbfDatasetComparisonDocument | null =
  raw === undefined ? null : checkedDatasetComparison(raw);
